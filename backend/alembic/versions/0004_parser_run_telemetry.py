"""M6: Телеметрия запусков парсера.

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-09
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Добавляет поля телеметрии в parser_runs."""
    op.add_column(
        "parser_runs",
        sa.Column("pages_fetched", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "parser_runs",
        sa.Column("expected_total_elements", sa.Integer(), nullable=True),
    )
    op.add_column(
        "parser_runs",
        sa.Column("yielded_total", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "parser_runs",
        sa.Column("skipped_invalid", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "parser_runs",
        sa.Column(
            "full_scan_completed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Удаляет поля телеметрии parser_runs."""
    op.drop_column("parser_runs", "full_scan_completed")
    op.drop_column("parser_runs", "skipped_invalid")
    op.drop_column("parser_runs", "yielded_total")
    op.drop_column("parser_runs", "expected_total_elements")
    op.drop_column("parser_runs", "pages_fetched")
