"""
Модуль интеграции с ЮKassa для приёма платежей.
Документация: https://yookassa.ru/developers/api
"""
import uuid
import base64
import aiohttp
from typing import Optional, Dict, Any

from config import config
from logger_config import logger


YOOKASSA_API_URL = "https://api.yookassa.ru/v3/payments"


class YooKassaPayment:
    """Класс для работы с платежами ЮKassa"""

    def __init__(self):
        self.shop_id = config.YOOKASSA_SHOP_ID
        self.secret_key = config.YOOKASSA_SECRET_KEY
        self.return_url = config.YOOKASSA_RETURN_URL

    def _get_auth_header(self) -> str:
        """Формирование заголовка Basic Auth"""
        credentials = f"{self.shop_id}:{self.secret_key}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    async def create_payment(
        self,
        amount: float,
        description: str,
        user_id: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Создание платежа в ЮKassa.

        Args:
            amount: Сумма в рублях (например, 100.00)
            description: Описание платежа
            user_id: ID пользователя Telegram
            metadata: Дополнительные данные

        Returns:
            Dict с данными платежа или None при ошибке
        """
        idempotence_key = str(uuid.uuid4())

        payload = {
            "amount": {
                "value": f"{amount:.2f}",
                "currency": "RUB",
            },
            "capture": True,
            "confirmation": {
                "type": "redirect",
                "return_url": (
                    f"{self.return_url}?start=payment_success_{user_id}"
                ),
            },
            "description": description,
            "metadata": {
                "user_id": str(user_id),
                **(metadata or {}),
            },
            "receipt": {
                "customer": {
                    "email": f"user_{user_id}@example.com",
                },
                "items": [
                    {
                        "description": description[:128],
                        "quantity": "1.00",
                        "amount": {
                            "value": f"{amount:.2f}",
                            "currency": "RUB",
                        },
                        "vat_code": 1,
                        "payment_subject": "service",
                        "payment_mode": "full_payment",
                    }
                ],
            },
        }

        headers = {
            "Authorization": self._get_auth_header(),
            "Idempotence-Key": idempotence_key,
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    YOOKASSA_API_URL,
                    json=payload,
                    headers=headers,
                ) as response:
                    data = await response.json()

                    if response.status == 200:
                        logger.info(
                            f"✅ Платёж создан: {data.get('id')} на {amount}₽"
                        )
                        return data
                    else:
                        logger.error(
                            f"❌ Ошибка ЮKassa: {response.status} — {data}"
                        )
                        return None
        except Exception as e:
            logger.error(f"❌ Ошибка при создании платежа: {e}")
            return None

    async def check_payment(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """
        Проверка статуса платежа.

        Args:
            payment_id: ID платежа в ЮKassa

        Returns:
            Dict с данными платежа или None
        """
        headers = {
            "Authorization": self._get_auth_header(),
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{YOOKASSA_API_URL}/{payment_id}",
                    headers=headers,
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(
                            f"❌ Ошибка проверки платежа: {response.status}"
                        )
                        return None
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке платежа: {e}")
            return None


# Глобальный экземпляр
yookassa = YooKassaPayment()