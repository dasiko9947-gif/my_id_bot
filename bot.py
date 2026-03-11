"""
Главный файл запуска Telegram бота
"""
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command

from config import config
from logger_config import logger
from handlers import router as main_router
from admin import admin_router  # Импортируем админ-роутер
from database import db

async def main() -> None:
    """Главная функция запуска бота"""
    
    # Проверяем конфигурацию
    try:
        config.validate()
    except ValueError as e:
        logger.error(f"Ошибка конфигурации: {e}")
        return
    
    logger.info("=" * 50)
    logger.info("Запуск Telegram ID Bot")
    logger.info(f"Уровень логирования: {config.LOG_LEVEL}")
    logger.info(f"ID администратора: {config.ADMIN_ID}")
    logger.info("=" * 50)
    
    # Инициализируем базу данных
    logger.info("Инициализация базы данных...")
    await db.init_db()
    
    # Получаем статистику
    stats = await db.get_users_by_status()
    logger.info(f"В базе данных: {stats['total']} пользователей")
    
    # Инициализируем бота
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        )
    )
    
    # Создаем диспетчер
    dp = Dispatcher()
    
    # ВАЖНО: Сначала подключаем админ-роутер (у него приоритет выше)
    dp.include_router(admin_router)
    # Потом основной роутер
    dp.include_router(main_router)
    
    # Пропускаем накопившиеся обновления
    await bot.delete_webhook(drop_pending_updates=True)
    
    logger.info("Бот успешно запущен и готов к работе!")
    
    # Уведомление администратора
    if config.ADMIN_ID:
        try:
            await bot.send_message(
                config.ADMIN_ID,
                f"✅ **Бот успешно запущен!**\n\n"
                f"📊 **Статистика:**\n"
                f"• Пользователей: {stats['total']}\n"
                f"• Активных: {stats['active']}\n"
                f"• За 24ч: +{stats['last_24h']}\n\n"
                f"👑 **Админ-панель:** /admin",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление администратору: {e}")
    
    # Запускаем поллинг
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Критическая ошибка при работе бота: {e}")
    finally:
        await bot.session.close()
        logger.info("Сессия бота закрыта")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем (Ctrl+C)")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")