"""M5: Шаблон дайджеста для админки.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-09
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Создаёт singleton-таблицу для шаблона регулярного дайджеста."""
    op.create_table(
        "digest_template",
        sa.Column(
            "id",
            sa.SmallInteger,
            primary_key=True,
            server_default=sa.text("1"),
        ),
        sa.Column("template_text", sa.Text, nullable=False, server_default=sa.text("''")),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("id = 1", name="ck_digest_template_singleton"),
    )
    op.execute("INSERT INTO digest_template (id) VALUES (1) ON CONFLICT DO NOTHING")


def downgrade() -> None:
    """Удаляет таблицу шаблона дайджеста."""
    op.drop_table("digest_template")
