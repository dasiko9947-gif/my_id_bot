"""
Обработчики команд и сообщений бота
"""
from datetime import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    InaccessibleMessage,
)
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import db
from models import User
from logger_config import logger
from config import config
from payments import yookassa

# Создаем роутер для обработчиков
router = Router()


# ===== Хелперы =====

async def safe_edit_message(
    callback: CallbackQuery,
    text: str,
    reply_markup=None,
    parse_mode=None,
) -> bool:
    """
    Безопасное редактирование сообщения.
    Возвращает True, если удалось отредактировать, иначе False.
    """
    if not callback.message or isinstance(callback.message, InaccessibleMessage):
        return False
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        return True
    except Exception as e:
        logger.warning(f"Не удалось отредактировать сообщение: {e}")
        return False


# ===== Тексты =====

INVITE_MESSAGE = (
    "Попробуй лучший VPN с обходом БЕЛЫХ СПИСКОВ\n"
    "300 ПИНКОВ VPN — @VPN_300_bot\n\n"
    "Кстати, твои данные:"
)

HELP_MESSAGE = (
    "📚 Как узнать ID:\n\n"
    "• Отправь мне любое сообщение — покажу твой ID\n"
    "• Перешли сообщение друга — покажу его ID\n"
    "• Поддержать проект: /donate\n\n"
    "🔥 Основной проект: @pinkov300_bot"
)

TERMS_MESSAGE = (
    "📋 **Обработка данных в боте**\n\n"
    "🤖 Этот бот помогает определить числовой идентификатор (ID) Telegram-аккаунтов.\n\n"
    "📊 **Что сохраняется:**\n"
    "• Только числовые ID пользователей, которые писали боту\n"
    "• Это нужно для технических уведомлений и новостей о проекте\n\n"
    "🔒 **Что НЕ сохраняется:**\n"
    "• Имена и фамилии\n"
    "• Сообщения и переписка\n"
    "• Фото, видео и другие файлы\n"
    "• Номера телефонов\n\n"
    "✅ Используя бота, вы соглашаетесь с хранением вашего ID для получения служебных сообщений.\n"
)


# ===== FSM =====

class DonateStates(StatesGroup):
    waiting_for_amount = State()


# ===== Команды =====

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Только приветствие и ID"""
    user = message.from_user
    if not user:
        return

    db_user = User.from_telegram_user(user)
    await db.add_or_update_user(db_user)

    logger.info(f"Новый пользователь: {user.id}")

    await message.answer(INVITE_MESSAGE)
    await message.answer(
        f"🆔 Твой ID: <code>{user.id}</code>",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Инструкция по использованию"""
    await message.answer(HELP_MESSAGE)


@router.message(Command("terms"))
async def cmd_terms(message: Message):
    """Условия использования"""
    await message.answer(TERMS_MESSAGE, parse_mode=ParseMode.MARKDOWN)


# ===== ДОНАТЫ =====

@router.message(Command("donate"))
async def cmd_donate(message: Message):
    """Команда для донатов через ЮKassa"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 100 ₽", callback_data="yookassa_100"),
            InlineKeyboardButton(text="💰 300 ₽", callback_data="yookassa_300"),
        ],
        [
            InlineKeyboardButton(text="💰 500 ₽", callback_data="yookassa_500"),
            InlineKeyboardButton(text="💰 1000 ₽", callback_data="yookassa_1000"),
        ],
        [
            InlineKeyboardButton(
                text="✏️ Другая сумма", callback_data="yookassa_custom"
            ),
        ],
    ])

    await message.answer(
        "🌟 **Поддержать проект**\n\n"
        "Вы можете отправить донат через ЮKassa — это поможет развитию бота.\n\n"
        "💳 Принимаем карты, СБП, ЮMoney и другие способы.\n\n"
        "Выберите сумму:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN,
    )


@router.callback_query(F.data.startswith("yookassa_"))
async def process_yookassa_donate(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора суммы доната"""
    if not callback.from_user or not callback.data:
        await callback.answer()
        return

    action = callback.data.replace("yookassa_", "")

    if action == "custom":
        custom_text = (
            "✏️ Введите сумму в рублях (например: 250)\n\n"
            "Минимум: 50 ₽, максимум: 50000 ₽"
        )
        if callback.message and not isinstance(callback.message, InaccessibleMessage):
            await callback.message.answer(custom_text)
        elif callback.bot:
            await callback.bot.send_message(
                chat_id=callback.from_user.id,
                text=custom_text,
            )
        await state.set_state(DonateStates.waiting_for_amount)
        await callback.answer()
        return

    try:
        amount = int(action)
    except ValueError:
        await callback.answer("❌ Неверная сумма", show_alert=True)
        return

    await _create_and_send_payment(callback, amount)
    await callback.answer()


@router.message(DonateStates.waiting_for_amount)
async def handle_custom_amount(message: Message, state: FSMContext):
    """Обработка ввода произвольной суммы"""
    if not message.text or not message.from_user:
        return

    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите целое число, например: 250")
        return

    if amount < 50 or amount > 50000:
        await message.answer("❌ Сумма должна быть от 50 до 50000 ₽")
        return

    await state.clear()

    if not message.bot:
        return

    user_id = message.from_user.id
    await message.answer(f"💳 Создаю счёт на {amount} ₽...")

    payment = await yookassa.create_payment(
        amount=float(amount),
        description=f"Донат {amount} ₽ для поддержки бота",
        user_id=user_id,
    )

    if not payment:
        await message.answer("❌ Ошибка при создании платежа. Попробуйте позже.")
        return

    await db.save_payment(
        payment_id=payment['id'],
        user_id=user_id,
        amount=float(amount),
        description=f"Донат {amount} ₽",
        status="pending",
    )

    confirmation_url = payment.get('confirmation', {}).get('confirmation_url')
    if not confirmation_url:
        await message.answer("❌ Не удалось получить ссылку на оплату.")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", url=confirmation_url)],
        [InlineKeyboardButton(
            text="✅ Я оплатил", callback_data=f"check_{payment['id']}"
        )],
    ])

    await message.answer(
        f"💰 **Счёт на {amount} ₽ создан**\n\n"
        f"Нажмите кнопку ниже, чтобы перейти к оплате.\n"
        f"После оплаты вернитесь в бота и нажмите «✅ Я оплатил».",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN,
    )


async def _create_and_send_payment(callback: CallbackQuery, amount: int):
    """Создание платежа и отправка ссылки пользователю"""
    if not callback.from_user or not callback.bot:
        return

    user_id = callback.from_user.id

    payment = await yookassa.create_payment(
        amount=float(amount),
        description=f"Донат {amount} ₽ для поддержки бота",
        user_id=user_id,
    )

    if not payment:
        await callback.answer("❌ Ошибка при создании платежа", show_alert=True)
        return

    await db.save_payment(
        payment_id=payment['id'],
        user_id=user_id,
        amount=float(amount),
        description=f"Донат {amount} ₽",
        status="pending",
    )

    confirmation_url = payment.get('confirmation', {}).get('confirmation_url')
    if not confirmation_url:
        await callback.answer("❌ Не удалось получить ссылку", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", url=confirmation_url)],
        [InlineKeyboardButton(
            text="✅ Я оплатил", callback_data=f"check_{payment['id']}"
        )],
    ])

    await callback.bot.send_message(
        chat_id=user_id,
        text=(
            f"💰 **Счёт на {amount} ₽ создан**\n\n"
            f"Нажмите кнопку ниже, чтобы перейти к оплате.\n"
            f"После оплаты вернитесь в бота и нажмите «✅ Я оплатил»."
        ),
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN,
    )


@router.callback_query(F.data.startswith("check_"))
async def check_payment_callback(callback: CallbackQuery):
    """Проверка статуса платежа по кнопке «Я оплатил»"""
    if not callback.from_user or not callback.data:
        await callback.answer()
        return

    payment_id = callback.data.replace("check_", "")
    user_id = callback.from_user.id

    # Получаем данные платежа из БД
    payment_db = await db.get_payment(payment_id)

    if not payment_db:
        await callback.answer("❌ Платёж не найден", show_alert=True)
        return

    # Проверка, что платёж принадлежит этому пользователю
    if payment_db['user_id'] != user_id:
        await callback.answer("⛔ Это не ваш платёж", show_alert=True)
        return

    # Если уже оплачен
    if payment_db['status'] == 'succeeded':
        await callback.answer("✅ Платёж уже подтверждён. Спасибо!", show_alert=True)
        return

    # Показываем "проверяем..."
    await callback.answer("🔍 Проверяю платёж...")

    payment_data = await yookassa.check_payment(payment_id)

    if not payment_data:
        await callback.answer(
            "❌ Не удалось проверить платёж. Попробуйте позже.",
            show_alert=True,
        )
        return

    status = payment_data.get('status')

    if status == "succeeded":
        amount = float(payment_data.get('amount', {}).get('value', 0))

        await db.update_payment_status(payment_id, "succeeded")

        # ===== Красивое уведомление пользователю =====
        await _send_success_notification(callback, payment_id, amount)

        # ===== Уведомление админу =====
        await _notify_admin(callback, payment_id, amount, user_id)

        logger.info(
            f"💰 Пользователь {user_id} оплатил {amount}₽ (платёж {payment_id})"
        )

    elif status == "pending":
        await callback.answer(
            "⏳ Платёж ещё не подтверждён. Подождите минуту и попробуйте снова.",
            show_alert=True,
        )

    elif status == "canceled":
        await db.update_payment_status(payment_id, "canceled")
        await callback.answer("❌ Платёж отменён", show_alert=True)

        cancel_text = (
            "❌ Платёж отменён.\n\n"
            "Если это ошибка — попробуйте снова: /donate"
        )

        edited = await safe_edit_message(
            callback,
            text=cancel_text,
            parse_mode=ParseMode.MARKDOWN,
        )

        if not edited and callback.bot:
            try:
                await callback.bot.send_message(
                    chat_id=user_id,
                    text=cancel_text,
                    parse_mode=ParseMode.MARKDOWN,
                )
            except Exception as e:
                logger.warning(f"Не удалось отправить сообщение: {e}")

    else:
        await callback.answer(f"Статус: {status}", show_alert=True)


async def _send_success_notification(
    callback: CallbackQuery, payment_id: str, amount: float
):
    """Красивое уведомление пользователю об успешной оплате"""
    if not callback.from_user or not callback.bot:
        return

    user = callback.from_user
    name = user.first_name or "друг"

    # Получаем общую статистику донатов
    total_stats = await db.get_total_donations()
    total_sum = total_stats.get('total', 0) or 0
    total_count = total_stats.get('count', 0) or 0

    # Считаем личную статистику пользователя
    user_payments = await db.get_user_payments(user.id)
    user_total = user_payments.get('total', 0) or 0
    user_count = user_payments.get('count', 0) or 0

    text = (
        f"🎉 <b>Спасибо за поддержку, {name}!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💚 Ваш донат успешно получен и уже помогает развитию бота.\n\n"
        f"📊 <b>Детали платежа:</b>\n"
        f"├ 💰 Сумма: <b>{amount:.0f} ₽</b>\n"
        f"├ 🆔 Платёж: <code>{payment_id[:16]}...</code>\n"
        f"└ ✅ Статус: <b>Оплачено</b>\n\n"
        f"👤 <b>Ваш вклад:</b>\n"
        f"├ 💵 Всего: <b>{user_total:.0f} ₽</b>\n"
        f"└ 🧾 Платежей: <b>{user_count}</b>\n\n"
        f"🌍 <b>Общая поддержка проекта:</b>\n"
        f"├ 💎 Собрано: <b>{total_sum:.0f} ₽</b>\n"
        f"└ 👥 Донатеров: <b>{total_count}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✨ Ваша поддержка мотивирует нас делать бота лучше!\n"
        f"🔥 Спасибо, что вы с нами ❤️"
    )

    # Пытаемся отредактировать сообщение с чеком
    edited = await safe_edit_message(
        callback,
        text=text,
        parse_mode=ParseMode.HTML,
    )
    if edited:
        return

    # Если не получилось — отправляем новое
    try:
        await callback.bot.send_message(
            chat_id=user.id,
            text=text,
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление: {e}")


async def _notify_admin(
    callback: CallbackQuery, payment_id: str, amount: float, user_id: int
):
    """Уведомление администратора о новом донате"""
    if not config.ADMIN_ID or not callback.bot:
        return

    user = callback.from_user
    if not user:
        return

    username = f"@{user.username}" if user.username else "нет username"
    name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "—"

    text = (
        f"💰 <b>Новый донат!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>От:</b> {name}\n"
        f"🔗 <b>Username:</b> {username}\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n\n"
        f"💵 <b>Сумма:</b> {amount:.0f} ₽\n"
        f"🧾 <b>Платёж:</b> <code>{payment_id}</code>\n"
        f"✅ <b>Статус:</b> succeeded"
    )

    try:
        await callback.bot.send_message(
            chat_id=config.ADMIN_ID,
            text=text,
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.warning(f"Не удалось уведомить админа: {e}")


# ===== ОБЩИЙ ОБРАБОТЧИК =====

@router.message()
async def handle_message(message: Message):
    """
    На ЛЮБОЕ сообщение - приглашение + ID (кроме команд)
    """
    if message.text and message.text.startswith('/'):
        logger.info(f"Игнорируем команду: {message.text}")
        return

    user = message.from_user
    chat = message.chat
    if not user or not chat:
        return

    db_user = User.from_telegram_user(user)
    await db.add_or_update_user(db_user)

    await db.add_or_update_chat(chat)
    await db.save_message(message, user.id, chat.id)

    logger.info(f"Сообщение от {user.id}")

    await message.answer(INVITE_MESSAGE)

    response_parts = [f"🆔 Твой ID: <code>{user.id}</code>"]

    if chat.type != "private":
        response_parts.append(f"🏠 ID чата: <code>{chat.id}</code>")

    if message.forward_from:
        forward_user = message.forward_from
        response_parts.append(f"🔄 ID автора: <code>{forward_user.id}</code>")
        logger.info(f"Пересланное сообщение от {forward_user.id}")
    elif message.forward_from_chat:
        forward_chat = message.forward_from_chat
        response_parts.append(
            f"📢 Переслано из канала/группы: <code>{forward_chat.id}</code>"
        )
    elif message.forward_sender_name:
        response_parts.append("🔒 Пользователь скрыл свой ID при пересылке")

    if message.reply_to_message and message.reply_to_message.from_user:
        reply_user = message.reply_to_message.from_user
        if reply_user.id != user.id:
            response_parts.append(f"💬 ID автора: <code>{reply_user.id}</code>")
            logger.info(f"Ответ на сообщение от {reply_user.id}")
    elif message.reply_to_message and message.reply_to_message.forward_sender_name:
        response_parts.append(
            "🔒 Пользователь, на которого вы ответили, скрыл свой ID"
        )

    response = "\n".join(response_parts)

    try:
        await message.answer(response, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Ошибка при отправке: {e}")
        clean_response = response.replace('<code>', '').replace('</code>', '')
        await message.answer(clean_response)