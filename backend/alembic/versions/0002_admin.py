"""M4: Добавление административного функционала.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Добавляет поля для M4: пользователи, outbox, парсер, audit, heartbeat."""

    # ------------------------------------------------------------------
    # 1. ALTER users
    # ------------------------------------------------------------------
    op.add_column("users", sa.Column("full_name", sa.String(255), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "is_admin",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "is_blocked",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.execute(
        "CREATE INDEX users_is_admin_idx ON users (is_admin) WHERE is_admin = TRUE"
    )
    op.execute(
        "CREATE INDEX users_is_blocked_idx ON users (is_blocked) WHERE is_blocked = TRUE"
    )

    # ------------------------------------------------------------------
    # 2. ALTER outbox
    # ------------------------------------------------------------------
    op.add_column("outbox", sa.Column("parse_mode", sa.String(16), nullable=True))
    op.add_column(
        "outbox",
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "outbox",
        sa.Column(
            "attempt_count",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column("outbox", sa.Column("last_error", sa.Text, nullable=True))
    op.add_column(
        "outbox",
        sa.Column(
            "source",
            sa.String(16),
            nullable=False,
            server_default="digest",
        ),
    )

    # Бекфилл: сообщения, у которых sent_at заполнен → status = 'sent'
    op.execute("UPDATE outbox SET status = 'sent' WHERE sent_at IS NOT NULL")

    # Заменяем старый индекс на новые
    op.execute("DROP INDEX IF EXISTS outbox_unsent")
    op.execute(
        "CREATE INDEX outbox_pending_idx ON outbox (created_at) WHERE status = 'pending'"
    )
    op.execute(
        "CREATE INDEX outbox_status_idx ON outbox (status, created_at DESC)"
    )

    # ------------------------------------------------------------------
    # 3. ALTER parser_runs
    # ------------------------------------------------------------------
    op.add_column(
        "parser_runs",
        sa.Column(
            "triggered_by",
            sa.String(16),
            nullable=False,
            server_default="schedule",
        ),
    )
    op.add_column(
        "parser_runs",
        sa.Column(
            "triggered_by_user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.execute(
        "CREATE INDEX parser_runs_started_idx ON parser_runs (started_at DESC)"
    )

    # ------------------------------------------------------------------
    # 4. CREATE admin_audit_log
    # ------------------------------------------------------------------
    op.create_table(
        "admin_audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "admin_user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=True),
        sa.Column("target_id", sa.String(64), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.execute(
        "CREATE INDEX admin_audit_user_idx ON admin_audit_log (admin_user_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX admin_audit_action_idx ON admin_audit_log (action, created_at DESC)"
    )

    # ------------------------------------------------------------------
    # 5. CREATE bot_heartbeat
    # ------------------------------------------------------------------
    op.create_table(
        "bot_heartbeat",
        sa.Column(
            "id",
            sa.SmallInteger,
            primary_key=True,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "last_seen_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "polling_ok",
            sa.Boolean,
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("version", sa.String(32), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_bot_heartbeat_singleton"),
    )
    op.execute(
        "INSERT INTO bot_heartbeat (id) VALUES (1) ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    """Откатывает изменения M4."""
    op.drop_table("bot_heartbeat")
    op.drop_table("admin_audit_log")

    op.execute("DROP INDEX IF EXISTS parser_runs_started_idx")
    op.drop_column("parser_runs", "triggered_by_user_id")
    op.drop_column("parser_runs", "triggered_by")

    op.execute("DROP INDEX IF EXISTS outbox_status_idx")
    op.execute("DROP INDEX IF EXISTS outbox_pending_idx")
    op.execute(
        "CREATE INDEX outbox_unsent ON outbox (created_at) WHERE sent_at IS NULL"
    )
    op.drop_column("outbox", "source")
    op.drop_column("outbox", "last_error")
    op.drop_column("outbox", "attempt_count")
    op.drop_column("outbox", "status")
    op.drop_column("outbox", "parse_mode")

    op.execute("DROP INDEX IF EXISTS users_is_blocked_idx")
    op.execute("DROP INDEX IF EXISTS users_is_admin_idx")
    op.drop_column("users", "is_blocked")
    op.drop_column("users", "is_admin")
    op.drop_column("users", "full_name")
