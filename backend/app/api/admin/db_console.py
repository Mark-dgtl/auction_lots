"""Эндпоинты /api/admin/db/* — консоль базы данных."""

import hashlib
import logging
import time as _time
from typing import Any, Callable, Optional

import sqlparse
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.errors import BadRequest, RequestTimeout
from app.db.session import get_db
from app.models.user import User
from app.services.audit_service import get_audit_writer

router = APIRouter()
logger = logging.getLogger("app.admin.db_console")

# Белый список наших таблиц
ALLOWED_TABLES = {
    "users",
    "lots",
    "favorites",
    "saved_filters",
    "outbox",
    "parser_runs",
    "admin_audit_log",
    "bot_heartbeat",
    "notification_log",
    "refresh_tokens",
    "regions",
    "categories",
}

# DDL-типы, запрещённые всегда
FORBIDDEN_TYPES = {
    "CREATE", "DROP", "ALTER", "TRUNCATE", "GRANT", "REVOKE",
    "VACUUM", "REFRESH", "COPY",
}

REPORTS: dict[str, dict] = {
    "users_with_telegram": {
        "id": "users_with_telegram",
        "title": "Пользователи с привязанным Telegram",
        "sql": "SELECT id, email, telegram_user_id, created_at FROM users WHERE telegram_user_id IS NOT NULL ORDER BY created_at DESC",
    },
    "top_lots_by_favorites": {
        "id": "top_lots_by_favorites",
        "title": "Топ-20 лотов по добавлению в избранное",
        "sql": (
            "SELECT l.id, l.title, l.source, COUNT(f.lot_id) AS favorites_count "
            "FROM lots l JOIN favorites f ON l.id = f.lot_id "
            "GROUP BY l.id, l.title, l.source "
            "ORDER BY favorites_count DESC LIMIT 20"
        ),
    },
    "outbox_failed_24h": {
        "id": "outbox_failed_24h",
        "title": "Ошибки доставки за сутки",
        "sql": (
            "SELECT o.id, u.email, o.text, o.attempt_count, o.last_error, o.created_at "
            "FROM outbox o JOIN users u ON o.user_id = u.id "
            "WHERE o.status = 'failed' AND o.created_at >= now() - interval '24 hours' "
            "ORDER BY o.created_at DESC"
        ),
    },
    "parser_runs_summary": {
        "id": "parser_runs_summary",
        "title": "Агрегация запусков парсера за 7 дней",
        "sql": (
            "SELECT source, status, COUNT(*) AS runs, SUM(lots_new) AS total_new "
            "FROM parser_runs "
            "WHERE started_at >= now() - interval '7 days' "
            "GROUP BY source, status ORDER BY source, status"
        ),
    },
    "daily_signups_30d": {
        "id": "daily_signups_30d",
        "title": "Регистрации по дням за 30 дней",
        "sql": (
            "SELECT date_trunc('day', created_at) AS day, COUNT(*) AS signups "
            "FROM users "
            "WHERE created_at >= now() - interval '30 days' "
            "GROUP BY day ORDER BY day"
        ),
    },
}


class QueryBody(BaseModel):
    """Тело POST /api/admin/db/query."""

    sql: str
    mode: str = "readonly"
    confirm: Optional[bool] = None


@router.get("/db/tables")
async def list_tables(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    """Возвращает список таблиц с оценкой числа строк."""
    result = await db.execute(
        text(
            "SELECT relname AS name, reltuples::BIGINT AS rows_estimate "
            "FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relkind = 'r' "
            "ORDER BY relname"
        )
    )
    items = [
        {"name": row.name, "rows_estimate": row.rows_estimate}
        for row in result
        if row.name in ALLOWED_TABLES
    ]
    return {"items": items}


@router.get("/db/tables/{table_name}")
async def get_table_rows(
    table_name: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    """Возвращает строки таблицы (строгий whitelist имён)."""
    if table_name not in ALLOWED_TABLES:
        raise BadRequest(f"Таблица '{table_name}' не в белом списке", code="INVALID_SQL")

    result = await db.execute(
        text(f'SELECT * FROM "{table_name}" LIMIT :limit OFFSET :offset'),
        {"limit": limit, "offset": offset},
    )
    rows = result.fetchall()
    columns = list(result.keys())

    total_row = await db.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
    total = total_row.scalar() or 0

    return {
        "columns": columns,
        "rows": [list(r) for r in rows],
        "total": total,
    }


@router.get("/db/reports")
async def list_reports(
    admin: User = Depends(require_admin),
) -> dict:
    """Возвращает список встроенных отчётов."""
    return {
        "items": [
            {"id": r["id"], "title": r["title"], "sql": r["sql"]}
            for r in REPORTS.values()
        ]
    }


@router.post("/db/reports/{report_id}/run")
async def run_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
    audit: Callable = Depends(get_audit_writer),
) -> dict:
    """Выполняет встроенный отчёт."""
    report = REPORTS.get(report_id)
    if not report:
        from app.core.errors import NotFound
        raise NotFound("Отчёт не найден")

    return await _execute_query(db, report["sql"], mode="readonly", audit=audit, admin=admin)


@router.post("/db/query")
async def execute_query(
    body: QueryBody,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
    audit: Callable = Depends(get_audit_writer),
) -> dict:
    """Выполняет произвольный SQL-запрос.

    В режиме readonly разрешены только SELECT.
    В режиме danger разрешены DML (INSERT/UPDATE/DELETE) при confirm=true.
    DDL запрещён всегда.
    """
    sql = body.sql.strip()
    if not sql:
        raise BadRequest("SQL не может быть пустым", code="INVALID_SQL")

    # Парсим через sqlparse
    statements = sqlparse.parse(sql)
    if not statements or not any(str(s).strip() for s in statements):
        raise BadRequest("Не удалось распознать SQL-запрос", code="INVALID_SQL")

    for stmt in statements:
        stmt_type = (stmt.get_type() or "").upper()
        sql_up = str(stmt).upper().strip()

        # DDL запрещён всегда — проверяем и по типу, и по началу строки
        for forbidden in FORBIDDEN_TYPES:
            if stmt_type == forbidden or sql_up.startswith(forbidden):
                raise BadRequest(
                    f"Тип запроса '{forbidden}' запрещён",
                    code="INVALID_SQL",
                )

        if body.mode == "readonly":
            # Разрешены только SELECT и WITH
            is_select = sql_up.startswith("SELECT") or sql_up.startswith("WITH")
            is_dml = stmt_type in ("INSERT", "UPDATE", "DELETE") or any(
                sql_up.startswith(t) for t in ("INSERT", "UPDATE", "DELETE")
            )
            if is_dml or (not is_select and stmt_type not in ("SELECT", "WITH", "UNKNOWN", None, "")):
                raise BadRequest(
                    f"В режиме readonly разрешён только SELECT, получен: {stmt_type or sql_up[:20]}",
                    code="INVALID_SQL",
                )
        elif body.mode == "danger":
            is_dml = stmt_type in ("INSERT", "UPDATE", "DELETE") or any(
                sql_up.startswith(t) for t in ("INSERT", "UPDATE", "DELETE")
            )
            if is_dml:
                if not body.confirm:
                    raise BadRequest(
                        "DML в режиме danger требует confirm=true",
                        code="DML_NOT_CONFIRMED",
                    )
            elif stmt_type not in ("SELECT", "WITH", "UNKNOWN", None, ""):
                if not sql_up.startswith("SELECT") and not sql_up.startswith("WITH"):
                    raise BadRequest(
                        f"Тип запроса '{stmt_type}' не разрешён в режиме danger",
                        code="INVALID_SQL",
                    )

    return await _execute_query(db, sql, mode=body.mode, audit=audit, admin=admin)


async def _execute_query(
    db: AsyncSession,
    sql: str,
    mode: str,
    audit: Callable,
    admin: User,
) -> dict:
    """Выполняет SQL с ограничениями по времени и возвращает QueryResult."""
    sql_fingerprint = hashlib.sha256(sql.encode()).hexdigest()[:16]

    # Для SELECT без LIMIT — оборачиваем
    is_select = sql.upper().strip().startswith(("SELECT", "WITH"))
    has_limit = "limit" in sql.lower()
    wrapped = False
    exec_sql = sql
    if is_select and not has_limit:
        exec_sql = f"SELECT * FROM ({sql}) _sub LIMIT 500"
        wrapped = True

    t0 = _time.monotonic()
    truncated = False
    is_postgresql = _is_pg(db)
    try:
        async with db.begin_nested():
            if is_postgresql:
                await db.execute(text("SET LOCAL statement_timeout = '5s'"))
                await db.execute(text("SET LOCAL idle_in_transaction_session_timeout = '5s'"))
            result = await db.execute(text(exec_sql))
            rows = result.fetchall() if result.returns_rows else []
            columns = list(result.keys()) if result.returns_rows else []
    except Exception as exc:
        exc_str = str(exc)
        if "statement timeout" in exc_str.lower() or "canceling statement" in exc_str.lower():
            raise RequestTimeout("Превышено время выполнения запроса")
        raise

    elapsed_ms = round((_time.monotonic() - t0) * 1000)

    if wrapped and len(rows) == 500:
        truncated = True

    row_count = len(rows)

    await audit(
        "DB_QUERY",
        target_type="sql",
        target_id=sql_fingerprint,
        payload={
            "mode": mode,
            "statements_count": len(sqlparse.parse(sql)),
            "elapsed_ms": elapsed_ms,
            "row_count": row_count,
            "truncated": truncated,
            "sql_preview": sql[:300],
        },
    )
    await db.commit()

    serializable_rows = []
    for row in rows:
        serializable_rows.append([_serialize_val(v) for v in row])

    return {
        "columns": columns,
        "rows": serializable_rows,
        "row_count": row_count,
        "elapsed_ms": elapsed_ms,
        "truncated": truncated,
    }


def _is_pg(db: AsyncSession) -> bool:
    """Определяет, используется ли PostgreSQL."""
    try:
        return db.sync_session.get_bind().dialect.name == "postgresql"
    except Exception:
        return False


def _serialize_val(v: Any) -> Any:
    """Сериализует значение ячейки в JSON-совместимый формат."""
    if v is None:
        return None
    if isinstance(v, (int, float, bool, str)):
        return v
    from decimal import Decimal
    if isinstance(v, Decimal):
        return str(v)
    from datetime import datetime, date
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return str(v)
