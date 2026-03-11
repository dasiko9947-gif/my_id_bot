"""
Настройка логирования для бота
"""
import logging
import sys
from datetime import datetime
from pathlib import Path

# Создаем директорию для логов, если её нет
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Имя файла лога с датой
LOG_FILE = LOG_DIR / f"bot_{datetime.now().strftime('%Y-%m-%d')}.log"

def setup_logger(name: str, level: str = "INFO") -> logging.Logger:
    """
    Настройка логгера с выводом в файл и консоль
    
    Args:
        name: Имя логгера
        level: Уровень логирования
    
    Returns:
        logging.Logger: Настроенный логгер
    """
    
    # Создаем логгер
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Формат логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Обработчик для файла
    file_handler = logging.FileHandler(
        LOG_FILE, 
        encoding='utf-8',
        mode='a'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Обработчик для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

# Создаем основной логгер приложения
logger = setup_logger("bot")