"""
Модуль загрузки конфигурации из .env файла
"""
import os
from dotenv import load_dotenv
from typing import Optional

# Загружаем переменные окружения из .env файла
load_dotenv()


class Config:
    """Класс конфигурации бота"""

    def __init__(self):
        # ===== Telegram =====
        self.BOT_TOKEN: str = os.getenv('BOT_TOKEN', '')
        self.LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')

        admin_id = os.getenv('ADMIN_ID')
        self.ADMIN_ID: Optional[int] = (
            int(admin_id) if admin_id and admin_id.isdigit() else None
        )

        # ===== ЮKassa =====
        self.YOOKASSA_SHOP_ID: str = os.getenv('YOOKASSA_SHOP_ID', '')
        self.YOOKASSA_SECRET_KEY: str = os.getenv('YOOKASSA_SECRET_KEY', '')
        self.YOOKASSA_RETURN_URL: str = os.getenv(
            'YOOKASSA_RETURN_URL', 'https://t.me/'
        )
        self.YOOKASSA_TEST_MODE: bool = os.getenv('YOOKASSA_TEST_MODE', '0') == '1'

        # Логи для проверки
        print(f"✅ Загружен ADMIN_ID: {self.ADMIN_ID}")
        print(f"✅ ЮKassa Shop ID: {self.YOOKASSA_SHOP_ID or 'НЕ ЗАДАН'}")
        print(f"✅ ЮKassa режим: {'ТЕСТ' if self.YOOKASSA_TEST_MODE else 'LIVE'}")

    def validate(self) -> bool:
        """Проверка наличия обязательных параметров"""
        if not self.BOT_TOKEN:
            raise ValueError(
                "BOT_TOKEN не найден в .env файле!\n"
                "Скопируйте .env.example в .env и укажите ваш токен."
            )
        if not self.YOOKASSA_SHOP_ID or not self.YOOKASSA_SECRET_KEY:
            raise ValueError(
                "YOOKASSA_SHOP_ID или YOOKASSA_SECRET_KEY не найдены в .env!\n"
                "Получите их в личном кабинете ЮKassa."
            )
        return True


# Создаем экземпляр конфигурации
config = Config()