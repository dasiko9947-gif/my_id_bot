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
        # Токен бота (обязательный параметр)
        self.BOT_TOKEN: str = os.getenv('BOT_TOKEN', '')
        
        # Уровень логирования
        self.LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
        
        # ID администратора (опционально)
        admin_id = os.getenv('ADMIN_ID')
        self.ADMIN_ID: Optional[int] = int(admin_id) if admin_id and admin_id.isdigit() else None
    
    def validate(self) -> bool:
        """Проверка наличия обязательных параметров"""
        if not self.BOT_TOKEN:
            raise ValueError(
                "BOT_TOKEN не найден в .env файле!\n"
                "Скопируйте .env.example в .env и укажите ваш токен."
            )
        return True

# Создаем экземпляр конфигурации
config = Config()