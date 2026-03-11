"""
Обработчики команд и сообщений бота
"""
from datetime import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery
from aiogram.enums import ParseMode

from database import db
from models import User
from logger_config import logger

# Создаем роутер для обработчиков
router = Router()

# Твоё приглашение
INVITE_MESSAGE = (
    "Приветствую, я основатель трансформационного челленджа внутри Telegram, "
    "300 ПИНКОВ @pinkov300_bot\n"
    "Для тех, кто устал от мотивации и хочет жить на полную.\n"
    "Кстати, твои данные:"
)

# Инструкция для команды /help
HELP_MESSAGE = (
    "📚 Как узнать ID:\n\n"
    "• Отправь мне любое сообщение — покажу твой ID\n"
    "• Перешли сообщение друга — покажу его ID\n\n"
    "🔥 Основной проект: @pinkov300_bot"
)

# Условия использования
# Условия использования
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

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Только приветствие и ID"""
    user = message.from_user
    
    if not user:
        return
    
    # Сохраняем пользователя в БД
    db_user = User.from_telegram_user(user)
    await db.add_or_update_user(db_user)
    
    logger.info(f"Новый пользователь: {user.id}")
    
    # Отправляем приглашение
    await message.answer(INVITE_MESSAGE)
    
    # Отправляем ID в формате HTML для удобного копирования
    await message.answer(
        f"🆔 Твой ID: <code>{user.id}</code>",
        parse_mode=ParseMode.HTML
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Инструкция по использованию"""
    await message.answer(HELP_MESSAGE)

@router.message(Command("terms"))
async def cmd_terms(message: Message):
    """Условия использования"""
    await message.answer(TERMS_MESSAGE, parse_mode=ParseMode.MARKDOWN)

@router.message(Command("donate"))
async def cmd_donate(message: Message):
    """Команда для донатов звёздами Telegram"""
    
    # Создаем клавиатуру с вариантами доната
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="⭐ 30 звёзд", 
                callback_data="donate_30"
            ),
            InlineKeyboardButton(
                text="⭐ 100 звёзд", 
                callback_data="donate_100"
            )
        ],
        [
            InlineKeyboardButton(
                text="⭐ 300 звёзд", 
                callback_data="donate_300"
            ),
            InlineKeyboardButton(
                text="⭐ 1000 звёзд", 
                callback_data="donate_1000"
            )
        ]
    ])
    
    await message.answer(
        "🌟 Поддержать проект\n\n"
        "Вы можете отправить донат в звёздах Telegram, чтобы поддержать развитие бота.\n\n"
        "Выберите сумму:", 
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("donate_"))
async def process_donate(callback_query):
    """Обработка выбора суммы доната"""
    
    # Получаем сумму из callback_data
    amount = int(callback_query.data.split("_")[1])
    
    # Создаем счет для оплаты звёздами
    prices = [LabeledPrice(label="XTR", amount=amount)]
    
    await callback_query.message.answer_invoice(
        title="Поддержка проекта",
        description=f"Донат {amount} звёзд для поддержки бота",
        prices=prices,
        provider_token="",  # Для звёзд Telegram оставляем пустым
        payload=f"donate_{amount}",
        currency="XTR",  # Валюта для звёзд Telegram
        start_parameter="donate"
    )
    
    await callback_query.answer()
@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    """Подтверждение платежа"""
    await pre_checkout_query.answer(ok=True)

@router.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    """Обработка успешного платежа"""
    
    if not message.successful_payment:
        return
    
    payment_info = message.successful_payment
    amount = payment_info.total_amount if payment_info else 0
    
    await message.answer(
        f"✅ Спасибо за поддержку!\n"
        f"Вы отправили {amount} звёзд.\n\n"
        "Ваша помощь помогает развивать бота! 🌟"
    )
    
    # Сохраняем информацию о донате в БД (опционально)
    user = message.from_user
    if user:
        logger.info(f"Пользователь {user.id} отправил донат {amount} звёзд")

@router.message()
async def handle_message(message: Message):
    """
    На ЛЮБОЕ сообщение - приглашение + ID
    """
    user = message.from_user
    chat = message.chat
    
    if not user or not chat:
        return
    
    # Сохраняем пользователя в БД
    db_user = User.from_telegram_user(user)
    await db.add_or_update_user(db_user)
    
    # Сохраняем чат
    await db.add_or_update_chat(chat)
    
    # Сохраняем сообщение
    await db.save_message(message, user.id, chat.id)
    
    logger.info(f"Сообщение от {user.id}")
    
    # ВСЕГДА отправляем приглашение первым сообщением
    await message.answer(INVITE_MESSAGE)
    
    # Формируем ответ с ID (в HTML формате для удобного копирования)
    response_parts = [f"🆔 Твой ID: <code>{user.id}</code>"]
    
    # Если чат (группа) - показываем ID чата
    if chat.type != "private":
        response_parts.append(f"🏠 ID чата: <code>{chat.id}</code>")
    
    # Если это пересланное сообщение - показываем ID автора
    if message.forward_from:
        forward_user = message.forward_from
        # У пересланных сообщений ID всегда доступен, даже если скрыт
        response_parts.append(f"🔄 ID автора: <code>{forward_user.id}</code>")
        logger.info(f"Пересланное сообщение от {forward_user.id}")
    elif message.forward_from_chat:
        # Если переслано из канала или группы
        forward_chat = message.forward_from_chat
        response_parts.append(f"📢 Переслано из канала/группы: <code>{forward_chat.id}</code>")
    elif message.forward_sender_name:
        # Если пользователь скрыл свой ID при пересылке
        response_parts.append("🔒 Пользователь скрыл свой ID при пересылке")
    
    # Если это ответ на сообщение - показываем ID автора
    if message.reply_to_message and message.reply_to_message.from_user:
        reply_user = message.reply_to_message.from_user
        if reply_user.id != user.id:
            response_parts.append(f"💬 ID автора: <code>{reply_user.id}</code>")
            logger.info(f"Ответ на сообщение от {reply_user.id}")
    elif message.reply_to_message and message.reply_to_message.forward_sender_name:
        # Если в ответе пользователь скрыл ID
        response_parts.append("🔒 Пользователь, на которого вы ответили, скрыл свой ID")
    
    # Объединяем все части ответа
    response = "\n".join(response_parts)
    
    # Отправляем ID вторым сообщением
    try:
        await message.answer(response, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Ошибка при отправке: {e}")
        # Если ошибка с HTML - отправляем без форматирования
        clean_response = response.replace('<code>', '').replace('</code>', '')
        await message.answer(clean_response)