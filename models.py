"""
Модели данных для базы данных
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class User:
    """Модель пользователя"""
    id: int  # Telegram ID
    username: Optional[str]
    first_name: str
    last_name: Optional[str]
    language_code: Optional[str]
    is_bot: bool
    first_seen: datetime
    last_seen: datetime
    is_active: bool = True
    
    @property
    def full_name(self) -> str:
        """Полное имя пользователя"""
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name
    
    @classmethod
    def from_telegram_user(cls, telegram_user, seen_time: Optional[datetime] = None):
        """Создание из объекта пользователя Telegram"""
        if seen_time is None:
            seen_time = datetime.now()
        
        # Безопасно получаем last_name (может быть None)
        last_name = telegram_user.last_name if hasattr(telegram_user, 'last_name') else None
        
        return cls(
            id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name or "",
            last_name=last_name,
            language_code=telegram_user.language_code,
            is_bot=telegram_user.is_bot,
            first_seen=seen_time,
            last_seen=seen_time
        )

@dataclass
class Chat:
    """Модель чата"""
    id: int
    type: str
    title: Optional[str]
    first_seen: datetime
    last_used: datetime

@dataclass
class Message:
    """Модель сообщения"""
    id: int
    user_id: int
    chat_id: int
    text: Optional[str]
    date: datetime
    is_forward: bool = False
    is_reply: bool = False