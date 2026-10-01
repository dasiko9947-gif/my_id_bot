"""
Админ-панель для управления ботом
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode
from aiogram.types import InaccessibleMessage

from database import db
from logger_config import logger
from config import config

# Создаем роутер для админ-команд
admin_router = Router()

# ID администратора из конфига
ADMIN_ID = config.ADMIN_ID


class BroadcastStates(StatesGroup):
    waiting_for_message = State()
    confirming = State()


def is_admin(user_id: int) -> bool:
    if ADMIN_ID is None:
        return False
    return user_id == ADMIN_ID


def create_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Список пользователей", callback_data="admin_users_1")],
        [InlineKeyboardButton(text="📨 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📈 Активность", callback_data="admin_activity")],
        [InlineKeyboardButton(text="💰 Донаты", callback_data="admin_donations")],
    ])


def create_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
    ])


def create_broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Отправить", callback_data="broadcast_send"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel"),
        ]
    ])


async def safe_send_message(callback: CallbackQuery, text: str, reply_markup=None, parse_mode=None):
    try:
        if callback.bot and callback.from_user:
            await callback.bot.send_message(
                chat_id=callback.from_user.id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")


async def safe_edit_or_send(callback: CallbackQuery, text: str, reply_markup=None, parse_mode=None):
    try:
        if not callback.bot or not callback.from_user:
            return

        if callback.message and not isinstance(callback.message, InaccessibleMessage):
            try:
                await callback.message.edit_text(
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                )
                return
            except Exception as e:
                logger.warning(f"Не удалось отредактировать сообщение: {e}")

        await callback.bot.send_message(
            chat_id=callback.from_user.id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    except Exception as e:
        logger.error(f"Ошибка в safe_edit_or_send: {e}")


@admin_router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not message.from_user:
        return

    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return

    logger.info(f"Админ {message.from_user.id} открыл админ-панель")

    await message.answer(
        "👑 **Админ-панель**\n\nВыберите действие:",
        reply_markup=create_admin_keyboard(),
        parse_mode="Markdown",
    )


@admin_router.callback_query(F.data.startswith("admin_"))
async def admin_callback(callback: CallbackQuery, state: FSMContext):
    if not callback.from_user:
        await callback.answer()
        return

    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    if not callback.data:
        await callback.answer()
        return

    action = callback.data

    if action == "admin_stats":
        await show_statistics(callback)
    elif action.startswith("admin_users_"):
        try:
            parts = action.split("_")
            page = int(parts[2]) if len(parts) >= 3 else 1
            await show_users_list(callback, page)
        except (IndexError, ValueError):
            await show_users_list(callback, 1)
    elif action == "admin_broadcast":
        await start_broadcast(callback, state)
    elif action == "admin_activity":
        await show_activity(callback)
    elif action == "admin_donations":
        await show_donations(callback)
    elif action.startswith("admin_user_"):
        try:
            parts = action.split("_")
            if len(parts) >= 3:
                user_id = int(parts[2])
                await show_user_details(callback, user_id)
            else:
                await safe_edit_or_send(
                    callback, "❌ Ошибка: неверный ID", create_back_keyboard()
                )
        except (IndexError, ValueError):
            await safe_edit_or_send(
                callback, "❌ Ошибка: неверный ID", create_back_keyboard()
            )
    elif action == "admin_back":
        await safe_edit_or_send(
            callback,
            "👑 **Админ-панель**\n\nВыберите действие:",
            create_admin_keyboard(),
            "Markdown",
        )

    await callback.answer()


@admin_router.callback_query(F.data.startswith("broadcast_"))
async def broadcast_callback(callback: CallbackQuery, state: FSMContext):
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    action = callback.data
    if action == "broadcast_send":
        await send_broadcast(callback, state)
    elif action == "broadcast_cancel":
        await cancel_broadcast(callback, state)

    await callback.answer()


@admin_router.message(BroadcastStates.waiting_for_message)
async def get_broadcast_message(message: Message, state: FSMContext):
    if not message.from_user or not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return

    await state.update_data(broadcast_message=message)
    users = await db.get_all_active_users_for_broadcast()
    recipients_count = len(users)

    preview_text = (
        f"📨 **Предпросмотр рассылки**\n\n"
        f"Сообщение будет отправлено **{recipients_count}** пользователям.\n\n"
        f"**Текст сообщения:**\n{message.text or '[Медиа-сообщение]'}"
    )

    await message.answer(preview_text, parse_mode="Markdown")
    await message.answer(
        "Подтвердите отправку:",
        reply_markup=create_broadcast_confirm_keyboard(),
    )

    await state.set_state(BroadcastStates.confirming)


@admin_router.message(BroadcastStates.confirming)
async def handle_confirm_message(message: Message, state: FSMContext):
    if not message.from_user or not is_admin(message.from_user.id):
        return
    await message.answer(
        "Пожалуйста, используйте кнопки для подтверждения или отмены."
    )


async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_back")]
    ])

    await safe_edit_or_send(
        callback,
        "📨 **Создание рассылки**\n\n"
        "Отправьте сообщение, которое хотите разослать всем пользователям.\n\n"
        "Поддерживаются: текст, фото, видео, документы",
        keyboard,
        "Markdown",
    )
    await state.set_state(BroadcastStates.waiting_for_message)


async def send_broadcast(callback: CallbackQuery, state: FSMContext):
    if not callback.bot:
        await safe_edit_or_send(
            callback, "❌ Ошибка: бот не доступен", create_back_keyboard()
        )
        return

    data = await state.get_data()
    broadcast_message = data.get('broadcast_message')

    if not broadcast_message:
        await safe_edit_or_send(
            callback, "❌ Ошибка: сообщение не найдено", create_back_keyboard()
        )
        await state.clear()
        return

    users = await db.get_all_active_users_for_broadcast()
    total_users = len(users)

    await safe_edit_or_send(
        callback,
        f"📤 **Начинаю рассылку...**\n\n"
        f"Всего получателей: {total_users}\n"
        f"Прогресс: 0/{total_users}",
        None,
        "Markdown",
    )

    sent = 0
    failed = 0

    progress_message = None
    if callback.message and callback.bot:
        try:
            progress_message = await callback.bot.send_message(
                chat_id=callback.from_user.id,
                text=f"📤 **Рассылка в процессе...**\n\nПрогресс: 0/{total_users}",
            )
        except Exception:
            pass

    for user_id in users:
        try:
            await callback.bot.copy_message(
                chat_id=user_id,
                from_chat_id=broadcast_message.chat.id,
                message_id=broadcast_message.message_id,
                caption=broadcast_message.caption,
                parse_mode=ParseMode.HTML,
            )
            sent += 1

            if sent % 10 == 0 and progress_message:
                try:
                    await progress_message.edit_text(
                        f"📤 **Рассылка в процессе...**\n\n"
                        f"Всего получателей: {total_users}\n"
                        f"Прогресс: {sent}/{total_users}\n"
                        f"✅ Успешно: {sent}\n"
                        f"❌ Ошибок: {failed}"
                    )
                except Exception:
                    pass
        except Exception as e:
            failed += 1
            logger.error(f"Ошибка при отправке пользователю {user_id}: {e}")

    percent = sent / total_users * 100 if total_users > 0 else 0
    result_text = (
        f"📊 **Рассылка завершена!**\n\n"
        f"✅ Успешно отправлено: {sent}\n"
        f"❌ Не удалось отправить: {failed}\n"
        f"📊 Всего получателей: {total_users}\n\n"
        f"Процент доставки: {percent:.1f}%"
    )

    if progress_message:
        try:
            await progress_message.edit_text(
                result_text, reply_markup=create_back_keyboard()
            )
        except Exception:
            await safe_edit_or_send(callback, result_text, create_back_keyboard())
    else:
        await safe_edit_or_send(callback, result_text, create_back_keyboard())

    await state.clear()


async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    await safe_edit_or_send(
        callback, "❌ Рассылка отменена", create_back_keyboard()
    )
    await state.clear()


async def show_statistics(callback: CallbackQuery):
    stats = await db.get_users_by_status()
    donations = await db.get_total_donations()

    active_percent = (
        (stats['active'] / stats['total'] * 100) if stats['total'] > 0 else 0
    )

    text = (
        "📊 **Общая статистика**\n\n"
        f"👥 **Всего пользователей:** {stats['total']}\n"
        f"✅ **Активных:** {stats['active']}\n"
        f"❌ **Неактивных:** {stats['inactive']}\n"
        f"🤖 **Ботов:** {stats['bots']}\n\n"
        f"📅 **За 24 часа:** +{stats['last_24h']}\n"
        f"📆 **За неделю:** +{stats['last_week']}\n"
        f"🗓️ **За месяц:** +{stats['last_month']}\n\n"
        f"📈 **Активность:** {active_percent:.1f}%\n\n"
        f"💰 **Донаты:**\n"
        f"├ 💵 Сумма: {donations['total']:.0f} ₽\n"
        f"└ 🧾 Платежей: {donations['count']}"
    )

    await safe_edit_or_send(callback, text, create_back_keyboard(), "Markdown")


async def show_users_list(callback: CallbackQuery, page: int):
    data = await db.get_users_with_pagination(page, per_page=5)

    if not data['users']:
        await safe_edit_or_send(
            callback, "📭 Пользователей не найдено", create_back_keyboard()
        )
        return

    text = f"👥 **Список пользователей** (стр. {page}/{data['total_pages']})\n\n"

    for user in data['users']:
        status = "✅" if user['is_active'] else "❌"
        username = f"@{user['username']}" if user['username'] else "нет username"
        name = f"{user['first_name']} {user['last_name'] or ''}".strip()
        last_seen = user['last_seen'][:10] if user['last_seen'] else "неизвестно"

        text += f"{status} **ID:** `{user['id']}`\n"
        text += f"   👤 {name}\n"
        text += f"   🔗 {username}\n"
        text += f"   📅 {last_seen}\n\n"

    keyboard_buttons = []
    if page > 1:
        keyboard_buttons.append(
            InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_users_{page-1}")
        )
    if page < data['total_pages']:
        keyboard_buttons.append(
            InlineKeyboardButton(text="Вперед ▶️", callback_data=f"admin_users_{page+1}")
        )

    inline_keyboard = []
    if keyboard_buttons:
        inline_keyboard.append(keyboard_buttons)
    inline_keyboard.append(
        [InlineKeyboardButton(text="🔙 В админку", callback_data="admin_back")]
    )

    await safe_edit_or_send(
        callback, text, InlineKeyboardMarkup(inline_keyboard=inline_keyboard), "Markdown"
    )


async def show_user_details(callback: CallbackQuery, user_id: int):
    user = await db.get_user(user_id)
    if not user:
        await safe_edit_or_send(
            callback, "❌ Пользователь не найден", create_back_keyboard()
        )
        return

    first_seen = (
        user.first_seen.strftime("%Y-%m-%d %H:%M") if user.first_seen else "неизвестно"
    )
    last_seen = (
        user.last_seen.strftime("%Y-%m-%d %H:%M") if user.last_seen else "неизвестно"
    )

    text = (
        f"👤 **Детали пользователя**\n\n"
        f"🆔 **ID:** `{user.id}`\n"
        f"📝 **Имя:** {user.full_name}\n"
        f"🔗 **Username:** @{user.username or 'нет'}\n"
        f"🌍 **Язык:** {user.language_code or 'не указан'}\n"
        f"🤖 **Бот:** {'да' if user.is_bot else 'нет'}\n"
        f"✅ **Активен:** {'да' if user.is_active else 'нет'}\n\n"
        f"📅 **Первый вход:** {first_seen}\n"
        f"🕐 **Последний вход:** {last_seen}"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад к списку", callback_data="admin_users_1")],
        [InlineKeyboardButton(text="🔙 В админку", callback_data="admin_back")],
    ])

    await safe_edit_or_send(callback, text, keyboard, "Markdown")


async def show_activity(callback: CallbackQuery):
    stats = await db.get_users_by_status()
    total = stats['total']
    active = stats['active']

    scale_length = 20
    active_bars = int((active / total * scale_length)) if total > 0 else 0
    inactive_bars = scale_length - active_bars

    active_scale = "█" * active_bars
    inactive_scale = "░" * inactive_bars

    text = (
        "📈 **Активность пользователей**\n\n"
        f"📊 **Всего:** {total}\n"
        f"✅ **Активные:** {active}\n"
        f"❌ **Неактивные:** {stats['inactive']}\n\n"
        f"📅 **За 24 часа:** +{stats['last_24h']}\n"
        f"📆 **За неделю:** +{stats['last_week']}\n"
        f"🗓️ **За месяц:** +{stats['last_month']}\n\n"
        f"**Шкала активности:**\n"
        f"Активные: {active_scale}{inactive_scale}\n"
        f"({active}/{total})"
    )

    await safe_edit_or_send(callback, text, create_back_keyboard(), "Markdown")


async def show_donations(callback: CallbackQuery):
    """Показ статистики донатов"""
    stats = await db.get_total_donations()
    top_donors = await db.get_top_donors(limit=10)

    text = (
        "💰 **Статистика донатов**\n\n"
        f"💵 **Всего собрано:** {stats['total']:.0f} ₽\n"
        f"🧾 **Успешных платежей:** {stats['count']}\n\n"
    )

    if top_donors:
        text += "🏆 **Топ донатеров:**\n"
        for i, donor in enumerate(top_donors, 1):
            medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f"{i}."
            text += (
                f"{medal} `{donor['user_id']}` — "
                f"{donor['total']:.0f} ₽ ({donor['payments_count']} шт.)\n"
            )
    else:
        text += "Пока нет успешных донатов."

    await safe_edit_or_send(callback, text, create_back_keyboard(), "Markdown")


@admin_router.message(Command("stats"))
async def cmd_public_stats(message: Message):
    if not message.from_user:
        return

    stats = await db.get_users_by_status()

    text = (
        "📊 **Статистика бота**\n\n"
        f"👥 **Всего пользователей:** {stats['total']}\n"
        f"✅ **Активных:** {stats['active']}\n"
        f"📅 **За 24 часа:** +{stats['last_24h']}\n\n"
        "✨ Спасибо, что пользуетесь ботом!"
    )

    await message.answer(text, parse_mode="Markdown")