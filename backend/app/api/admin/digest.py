"""Эндпоинты /api/admin/digest/* — шаблон и ручной запуск дайджеста."""

import logging
from typing import Callable

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.errors import AppError, ValidationFailed
from app.db.session import get_db
from app.models.user import User
from app.services.audit_service import get_audit_writer
from app.services.digest_service import DigestService

router = APIRouter()
logger = logging.getLogger("app.admin.digest")

_digest_running: bool = False


class DigestTemplateBody(BaseModel):
    """Тело PUT /api/admin/digest/template."""

    template: str


@router.get("/digest/template")
async def get_digest_template(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    """Возвращает активный шаблон регулярного дайджеста."""
    svc = DigestService(db)
    template = await svc.get_template()
    return {
        "template": template,
        "placeholders": ["{filter_name}", "{lots_count}", "{lots}"],
    }


@router.put("/digest/template")
async def put_digest_template(
    body: DigestTemplateBody,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
    audit: Callable = Depends(get_audit_writer),
) -> dict:
    """Сохраняет шаблон регулярного дайджеста."""
    svc = DigestService(db)
    try:
        template = await svc.update_template(body.template)
    except ValueError as exc:
        raise ValidationFailed(str(exc))

    await audit(
        "DIGEST_TEMPLATE_UPDATE",
        target_type="digest",
        target_id="template",
        payload={"template_len": len(template)},
    )
    await db.commit()
    logger.info("Администратор обновил шаблон дайджеста")
    return {"template": template}


@router.post("/digest/run-now")
async def run_digest_now(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
    audit: Callable = Depends(get_audit_writer),
) -> dict:
    """Запускает регулярный дайджест досрочно, вне временного окна."""
    global _digest_running
    if _digest_running:
        raise AppError("Дайджест уже выполняется", code="DIGEST_BUSY")

    _digest_running = True
    try:
        svc = DigestService(db)
        created = await svc.tick(force=True)
    finally:
        _digest_running = False

    await audit(
        "DIGEST_RUN_NOW",
        target_type="digest",
        payload={"created": created},
    )
    await db.commit()
    logger.info("Администратор запустил дайджест вручную: created=%d", created)
    return {"created": created}
