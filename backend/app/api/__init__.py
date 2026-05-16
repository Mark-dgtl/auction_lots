"""Корневой API-роутер приложения.

Агрегирует все дочерние роутеры с префиксом /api.
"""

from fastapi import APIRouter, Depends

from app.api.auth import router as auth_router
from app.api.deps import get_current_user
from app.api.favorites import router as favorites_router
from app.api.filters import router as filters_router
from app.api.internal import router as internal_router
from app.api.lots import router as lots_router
from app.api.media import router as media_router
from app.api.meta import router as meta_router
from app.api.notifications import router as notifications_router
from app.api.telegram import router as telegram_router
from app.api.admin import admin_router
from app.models.user import User
from app.schemas.auth import MeResponse

api_router = APIRouter(prefix="/api")

api_router.include_router(auth_router)
api_router.include_router(lots_router)
api_router.include_router(media_router)
api_router.include_router(favorites_router)
api_router.include_router(filters_router)
api_router.include_router(telegram_router)
api_router.include_router(notifications_router)
api_router.include_router(meta_router)
api_router.include_router(internal_router)
api_router.include_router(admin_router)


@api_router.get("/me", response_model=MeResponse, tags=["auth"])
async def get_me(user: User = Depends(get_current_user)) -> MeResponse:
    """Возвращает данные текущего авторизованного пользователя.

    Args:
        user: Текущий пользователь из Bearer-токена.

    Returns:
        Объект MeResponse с полями id, email, telegram_linked, digest_time.
    """
    return MeResponse(
        id=user.id,
        email=str(user.email),
        telegram_linked=user.telegram_user_id is not None,
        digest_time=str(user.digest_time)[:5] if user.digest_time else None,
        is_admin=user.is_admin,
    )
