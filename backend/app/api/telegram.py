"""Роутер Telegram-интеграции."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.telegram import TelegramLinkResponse
from app.services.telegram_service import TelegramService

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/link", response_model=TelegramLinkResponse)
async def generate_link(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TelegramLinkResponse:
    """Генерирует one-time deep-link для привязки Telegram-аккаунта.

    Токен действителен 1 час. Предыдущий токен перезаписывается.
    """
    svc = TelegramService(db)
    return await svc.generate_link(user.id)


@router.post("/unlink", status_code=204)
async def unlink_telegram(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Отвязывает Telegram-аккаунт от текущего пользователя."""
    svc = TelegramService(db)
    await svc.unlink(user.id)
