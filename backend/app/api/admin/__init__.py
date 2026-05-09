"""Административный API — агрегация всех роутеров /api/admin/*."""

from fastapi import APIRouter, Depends

from app.api.deps import require_admin
from app.api.admin.health import router as health_router
from app.api.admin.logs import router as logs_router
from app.api.admin.scheduler import router as scheduler_router
from app.api.admin.parser import router as parser_router
from app.api.admin.users import router as users_router
from app.api.admin.lots import router as lots_router
from app.api.admin.outbox import router as outbox_router
from app.api.admin.bot import router as bot_router
from app.api.admin.db_console import router as db_router
from app.api.admin.digest import router as digest_router

admin_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)

admin_router.include_router(health_router)
admin_router.include_router(logs_router)
admin_router.include_router(scheduler_router)
admin_router.include_router(parser_router)
admin_router.include_router(users_router)
admin_router.include_router(lots_router)
admin_router.include_router(outbox_router)
admin_router.include_router(bot_router)
admin_router.include_router(db_router)
admin_router.include_router(digest_router)
