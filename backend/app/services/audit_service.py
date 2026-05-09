"""Сервис записи аудит-лога административных действий."""

import logging
from typing import Any, Callable, Optional

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.admin_audit_log import AdminAuditLog
from app.models.user import User

logger = logging.getLogger("app.admin.audit")


async def write(
    session: AsyncSession,
    *,
    admin_user_id: Optional[int],
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    payload: Optional[dict] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """Записывает действие администратора в audit log.

    Args:
        session: Асинхронная сессия БД.
        admin_user_id: ID администратора, выполнившего действие.
        action: Код действия (USER_DELETE, DB_QUERY и т.д.).
        target_type: Тип объекта действия.
        target_id: ID объекта или fingerprint.
        payload: Дополнительные данные.
        ip: IP-адрес администратора.
        user_agent: User-Agent браузера.
    """
    entry = AdminAuditLog(
        admin_user_id=admin_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        payload=payload or {},
        ip=ip,
        user_agent=user_agent,
    )
    session.add(entry)
    await session.flush()
    logger.info(
        "Аудит: действие='%s' target_type='%s' target_id='%s' admin_id=%s",
        action,
        target_type,
        target_id,
        admin_user_id,
    )


def get_audit_writer(
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Callable:
    """Dependency для FastAPI — возвращает вызываемый хелпер записи аудита.

    Использование в роуте:
        audit = Depends(get_audit_writer)
        await audit("USER_DELETE", target_type="user", target_id=str(user_id))

    Args:
        request: Входящий HTTP-запрос (для IP и User-Agent).
        admin: Текущий администратор.
        db: Сессия БД.

    Returns:
        Корутина для записи аудита.
    """
    ip = request.client.host if request.client else None
    ua = request.headers.get("User-Agent")

    async def _audit(
        action: str,
        *,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        payload: Optional[dict] = None,
    ) -> None:
        await write(
            db,
            admin_user_id=admin.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            payload=payload,
            ip=ip,
            user_agent=ua,
        )

    return _audit
