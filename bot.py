"""
Главный файл запуска Telegram бота
"""
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import config
from logger_config import logger
from handlers import router as main_router
from admin import admin_router
from database import db


async def main() -> None:
    """Главная функция запуска бота"""

    try:
        config.validate()
    except ValueError as e:
        logger.error(f"Ошибка конфигурации: {e}")
        return

    logger.info("=" * 50)
    logger.info("Запуск Telegram ID Bot")
    logger.info(f"Уровень логирования: {config.LOG_LEVEL}")
    logger.info(f"ID администратора: {config.ADMIN_ID}")
    logger.info(f"ЮKassa Shop ID: {config.YOOKASSA_SHOP_ID}")
    logger.info(f"ЮKassa режим: {'ТЕСТ' if config.YOOKASSA_TEST_MODE else 'LIVE'}")
    logger.info("=" * 50)

    logger.info("Инициализация базы данных...")
    await db.init_db()

    stats = await db.get_users_by_status()
    donations = await db.get_total_donations()
    logger.info(f"В базе данных: {stats['total']} пользователей")
    logger.info(f"Всего донатов: {donations['total']:.0f} ₽ ({donations['count']} шт.)")

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()

    # Админ-роутер первым (у него приоритет)
    dp.include_router(admin_router)
    dp.include_router(main_router)

    await bot.delete_webhook(drop_pending_updates=True)

    logger.info("✅ Бот успешно запущен и готов к работе!")

    # Уведомление админа о запуске (parse_mode уже установлен в DefaultBotProperties)
    if config.ADMIN_ID:
        try:
            await bot.send_message(
                config.ADMIN_ID,
                f"✅ <b>Бот успешно запущен!</b>\n\n"
                f"📊 <b>Статистика:</b>\n"
                f"• Пользователей: {stats['total']}\n"
                f"• Активных: {stats['active']}\n"
                f"• За 24ч: +{stats['last_24h']}\n\n"
                f"💰 <b>Донаты:</b>\n"
                f"• Сумма: {donations['total']:.0f} ₽\n"
                f"• Платежей: {donations['count']}\n\n"
                f"👑 <b>Админ-панель:</b> /admin",
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление администратору: {e}")

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