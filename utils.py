"""
Вспомогательные функции для бота
"""
from typing import Optional, Dict, Any

def format_user_info(
    user_id: int,
    full_name: str,
    username: Optional[str] = None,
    additional_info: Optional[Dict[str, Any]] = None
) -> str:
    """
    Форматирование информации о пользователе
    
    Args:
        user_id: ID пользователя
        full_name: Полное имя
        username: Username (опционально)
        additional_info: Дополнительная информация
    
    Returns:
        str: Отформатированное сообщение
    """
    info = f"👤 **Информация о пользователе:**\n\n"
    info += f"🆔 **ID:** `{user_id}`\n"
    info += f"📝 **Имя:** {full_name}\n"
    
    if username:
        info += f"🔗 **Username:** @{username}\n"
    
    if additional_info:
        info += f"\n📌 **Дополнительно:**\n"
        for key, value in additional_info.items():
            info += f"• {key}: {value}\n"
    
    return info

def safe_getattr(obj, attr: str, default: Any = None) -> Any:
    """
    Безопасное получение атрибута объекта
    
    Args:
        obj: Объект
        attr: Имя атрибута
        default: Значение по умолчанию
    
    Returns:
        Any: Значение атрибута или default
    """
    if obj is None:
        return default
    return getattr(obj, attr, default)