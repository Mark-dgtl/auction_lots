"""Эндпоинты /api/admin/users/* — управление пользователями."""

import logging
from typing import Callable, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.errors import Conflict, NotFound
from app.db.session import get_db
from app.models.outbox import Outbox
from app.models.saved_filter import SavedFilter
from app.models.user import User
from app.services.audit_service import get_audit_writer

router = APIRouter()
logger = logging.getLogger("app.admin.users")


class PatchUserBody(BaseModel):
    """Тело PATCH /api/admin/users/{id}."""

    full_name: Optional[str] = None
    is_admin: Optional[bool] = None
    is_blocked: Optional[bool] = None
    digest_time: Optional[str] = None
    digest_tz: Optional[str] = None


def _user_to_dict(user: User, favorites_count: int = 0, filters_count: int = 0) -> dict:
    return {
        "id": user.id,
        "email": str(user.email),
        "full_name": user.full_name,
        "is_admin": user.is_admin,
        "is_blocked": user.is_blocked,
        "telegram_linked": user.telegram_user_id is not None,
        "telegram_user_id": user.telegram_user_id,
        "digest_time": str(user.digest_time)[:5] if user.digest_time else None,
        "digest_tz": user.digest_tz,
        "favorites_count": favorites_count,
        "filters_count": filters_count,
        "created_at": user.created_at.strftime("%Y-%m-%dT%H:%M:%SZ") if user.created_at else None,
    }


@router.get("/users")
async def list_users(
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    """Возвращает список пользователей с пагинацией и поиском."""
    stmt = select(User)
    if q:
        stmt = stmt.where(User.email.ilike(f"%{q}%"))

    total = await db.scalar(
        select(func.count()).select_from(stmt.subquery())
    ) or 0
    users = await db.scalars(
        stmt.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    from app.models.favorite import Favorite
    items = []
    for u in users.all():
        fav_count = await db.scalar(
            select(func.count()).select_from(Favorite).where(Favorite.user_id == u.id)
        ) or 0
        fil_count = await db.scalar(
            select(func.count()).select_from(SavedFilter).where(SavedFilter.user_id == u.id)
        ) or 0
        items.append(_user_to_dict(u, favorites_count=fav_count, filters_count=fil_count))

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    """Возвращает детальную информацию о пользователе."""
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise NotFound("Пользователь не найден")

    from app.models.favorite import Favorite
    fav_count = await db.scalar(
        select(func.count()).select_from(Favorite).where(Favorite.user_id == user_id)
    ) or 0
    fil_count = await db.scalar(
        select(func.count()).select_from(SavedFilter).where(SavedFilter.user_id == user_id)
    ) or 0

    # Recent outbox
    outbox_rows = await db.scalars(
        select(Outbox)
        .where(Outbox.user_id == user_id)
        .order_by(Outbox.created_at.desc())
        .limit(10)
    )
    recent_outbox = [
        {
            "id": o.id,
            "text": o.text[:100],
            "status": o.status,
            "created_at": o.created_at.strftime("%Y-%m-%dT%H:%M:%SZ") if o.created_at else None,
        }
        for o in outbox_rows.all()
    ]

    # Recent filters
    filter_rows = await db.scalars(
        select(SavedFilter)
        .where(SavedFilter.user_id == user_id)
        .order_by(SavedFilter.created_at.desc())
        .limit(5)
    )
    recent_filters = [
        {
            "id": f.id,
            "name": f.name,
            "notify_enabled": f.notify_enabled,
            "created_at": f.created_at.strftime("%Y-%m-%dT%H:%M:%SZ") if f.created_at else None,
        }
        for f in filter_rows.all()
    ]

    result = _user_to_dict(user, favorites_count=fav_count, filters_count=fil_count)
    result["recent_outbox"] = recent_outbox
    result["recent_filters"] = recent_filters
    return result


@router.patch("/users/{user_id}")
async def patch_user(
    user_id: int,
    body: PatchUserBody,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
    audit: Callable = Depends(get_audit_writer),
) -> dict:
    """Обновляет данные пользователя."""
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise NotFound("Пользователь не найден")

    # Защита: нельзя снять is_admin с самого себя
    if body.is_admin is False and user_id == admin.id:
        raise Conflict(
            "Нельзя снять права администратора с самого себя",
            code="ALREADY_ADMIN",
        )

    # Защита: нельзя снять is_admin с последнего администратора
    if body.is_admin is False and user.is_admin:
        admin_count = await db.scalar(
            select(func.count()).select_from(User).where(User.is_admin.is_(True))
        ) or 0
        if admin_count <= 1:
            raise Conflict(
                "Нельзя оставить систему без администратора",
                code="ALREADY_ADMIN",
            )

    if body.full_name is not None:
        user.full_name = body.full_name
    if body.is_admin is not None:
        user.is_admin = body.is_admin
    if body.is_blocked is not None:
        user.is_blocked = body.is_blocked
    if body.digest_tz is not None:
        user.digest_tz = body.digest_tz
    if body.digest_time is not None:
        from datetime import time as dt_time
        parts = body.digest_time.split(":")
        user.digest_time = dt_time(int(parts[0]), int(parts[1]))

    await db.commit()
    await db.refresh(user)

    await audit(
        "USER_PATCH",
        target_type="user",
        target_id=str(user_id),
        payload=body.model_dump(exclude_none=True),
    )
    await db.commit()
    logger.info("Администратор обновил пользователя id=%d", user_id)

    from app.models.favorite import Favorite
    fav_count = await db.scalar(
        select(func.count()).select_from(Favorite).where(Favorite.user_id == user_id)
    ) or 0
    fil_count = await db.scalar(
        select(func.count()).select_from(SavedFilter).where(SavedFilter.user_id == user_id)
    ) or 0
    return _user_to_dict(user, favorites_count=fav_count, filters_count=fil_count)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
    audit: Callable = Depends(get_audit_writer),
) -> None:
    """Удаляет пользователя."""
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise NotFound("Пользователь не найден")

    # Нельзя удалить самого себя или последнего администратора
    if user_id == admin.id:
        raise Conflict(
            "Нельзя удалить самого себя",
            code="ALREADY_ADMIN",
        )
    if user.is_admin:
        admin_count = await db.scalar(
            select(func.count()).select_from(User).where(User.is_admin.is_(True))
        ) or 0
        if admin_count <= 1:
            raise Conflict(
                "Нельзя оставить систему без администратора",
                code="ALREADY_ADMIN",
            )

    await audit("USER_DELETE", target_type="user", target_id=str(user_id))
    await db.delete(user)
    await db.commit()
    logger.info("Администратор удалил пользователя id=%d", user_id)


@router.post("/users/{user_id}/unlink-telegram", status_code=204)
async def unlink_telegram(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
    audit: Callable = Depends(get_audit_writer),
) -> None:
    """Отвязывает Telegram-аккаунт пользователя."""
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise NotFound("Пользователь не найден")

    user.telegram_user_id = None
    user.telegram_chat_id = None
    user.telegram_link_token = None
    user.telegram_token_expires_at = None
    await db.commit()

    await audit("USER_UNLINK_TELEGRAM", target_type="user", target_id=str(user_id))
    await db.commit()
    logger.info("Администратор отвязал Telegram пользователя id=%d", user_id)
