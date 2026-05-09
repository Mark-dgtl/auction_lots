"""Экспорт всех ORM-моделей приложения.

Импортируется в alembic/env.py для регистрации метаданных.
"""

from app.models.admin_audit_log import AdminAuditLog
from app.models.bot_heartbeat import BotHeartbeat
from app.models.category import Category
from app.models.digest_template import DigestTemplate
from app.models.favorite import Favorite
from app.models.lot import Lot
from app.models.notification_log import NotificationLog
from app.models.outbox import Outbox
from app.models.parser_run import ParserRun
from app.models.refresh_token import RefreshToken
from app.models.region import Region
from app.models.saved_filter import SavedFilter
from app.models.user import User

__all__ = [
    "AdminAuditLog",
    "BotHeartbeat",
    "Category",
    "DigestTemplate",
    "Favorite",
    "Lot",
    "NotificationLog",
    "Outbox",
    "ParserRun",
    "RefreshToken",
    "Region",
    "SavedFilter",
    "User",
]
