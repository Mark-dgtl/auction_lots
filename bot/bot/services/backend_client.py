"""HTTP-клиент для взаимодействия бота с внутренним API backend."""

import logging
from typing import Any

import httpx

logger = logging.getLogger("bot.backend_client")


class BackendClient:
    """Клиент внутреннего API backend.

    Все запросы отправляются с заголовком X-Internal-Token.
    Контракт описан в docs/CONTRACTS.md §2.7.

    Args:
        base_url: Базовый URL backend без trailing slash.
        token: Значение INTERNAL_API_TOKEN.
        timeout: Таймаут одного HTTP-запроса в секундах.
    """

    def __init__(self, base_url: str, token: str, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"X-Internal-Token": token}
        self._timeout = timeout

    async def bind_telegram(
        self, link_token: str, telegram_user_id: int, chat_id: int
    ) -> bool:
        """Привязывает Telegram-аккаунт по one-time токену.

        Args:
            link_token: One-time токен из deep-link.
            telegram_user_id: Telegram user ID.
            chat_id: Telegram chat ID.

        Returns:
            True если привязка успешна, False если токен неверный или истёк.
        """
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.post(
                    f"{self._base_url}/api/internal/telegram/bind",
                    json={
                        "token": link_token,
                        "telegram_user_id": telegram_user_id,
                        "chat_id": chat_id,
                    },
                    headers=self._headers,
                )
                return resp.status_code == 200
            except httpx.RequestError as exc:
                logger.error("Ошибка соединения с backend при bind: %s", exc)
                return False

    async def get_outbox(self, limit: int = 50) -> list[dict[str, Any]]:
        """Получает список неотправленных сообщений из очереди.

        Args:
            limit: Максимальное число сообщений.

        Returns:
            Список словарей с полями id, chat_id, text, lot_ids,
            опционально parse_mode (см. §2.7 контракта).
        """
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.get(
                    f"{self._base_url}/api/internal/outbox",
                    params={"limit": limit},
                    headers=self._headers,
                )
                if resp.status_code == 200:
                    return resp.json().get("items", [])
            except httpx.RequestError as exc:
                logger.error("Ошибка соединения с backend при get_outbox: %s", exc)
        return []

    async def ack_outbox(
        self,
        msg_id: int,
        *,
        status: str = "sent",
        error: str | None = None,
    ) -> None:
        """Подтверждает обработку сообщения из outbox.

        Шлёт ``POST /api/internal/outbox/{id}/ack`` с телом
        ``{status, error?}``. Если ``status="failed"``, backend увеличит
        ``attempt_count`` и вернёт сообщение в очередь до 3 попыток.

        Args:
            msg_id: ID записи в таблице outbox.
            status: ``"sent"`` или ``"failed"``.
            error: Текст ошибки (только при ``status="failed"``).
        """
        body: dict[str, Any] = {"status": status}
        if error is not None:
            body["error"] = error
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                await client.post(
                    f"{self._base_url}/api/internal/outbox/{msg_id}/ack",
                    json=body,
                    headers=self._headers,
                )
            except httpx.RequestError as exc:
                logger.error("Ошибка соединения с backend при ack: %s", exc)

    async def post_heartbeat(
        self, polling_ok: bool, version: str | None = None
    ) -> None:
        """Шлёт heartbeat backend'у (см. §2.7).

        Endpoint: ``POST /api/internal/bot/heartbeat`` с телом
        ``{polling_ok: bool, version?: str}``. Ожидаемый ответ — 204.
        Любая ошибка сети/HTTP — пробрасывается как ``httpx.HTTPError``,
        вызывающая сторона сама решает что делать.

        Args:
            polling_ok: Флаг, что aiogram polling работает штатно.
            version: Опциональная версия бота (semver).

        Raises:
            httpx.HTTPError: При ошибке транспорта; вызывающий обязан
                поймать и продолжить цикл.
        """
        body: dict[str, Any] = {"polling_ok": polling_ok}
        if version is not None:
            body["version"] = version
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/api/internal/bot/heartbeat",
                json=body,
                headers=self._headers,
            )
            resp.raise_for_status()

    async def post_logs(self, records: list[dict[str, Any]]) -> None:
        """Отправляет батч лог-записей backend'у (см. §2.7).

        Endpoint: ``POST /api/internal/bot/log`` с телом
        ``{records: [{ts, level, name, message}, ...]}``.
        Контракт ограничивает батч 200 записями за вызов; вызывающая сторона
        обязана сама не превышать лимит.

        Args:
            records: Список словарей с полями ``ts`` (ISO-UTC),
                ``level`` (str), ``name`` (str), ``message`` (str).

        Raises:
            httpx.HTTPError: При ошибке транспорта; вызывающий обязан поймать.
        """
        if not records:
            return
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/api/internal/bot/log",
                json={"records": records},
                headers=self._headers,
            )
            resp.raise_for_status()
