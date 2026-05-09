"""Начальная миграция: расширения, таблицы, индексы, триггер, seed.

Revision ID: 0001
Revises:
Create Date: 2026-04-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Seed-данные
# ---------------------------------------------------------------------------

CATEGORIES = [
    ("real_estate", "Недвижимость"),
    ("vehicle", "Транспорт"),
    ("equipment", "Оборудование"),
    ("land", "Земельные участки"),
    ("rights", "Права требования"),
    ("securities", "Ценные бумаги"),
    ("inventory", "ТМЦ и материалы"),
    ("other", "Прочее"),
]

# Регионы РФ: коды ОКАТО (двузначный) + название.
# 40 — Санкт-Петербург (согласно контракту §1.4 пример),
# 45 — Москва, 66 — Свердловская область.
REGIONS = [
    ("01", "Республика Адыгея"),
    ("02", "Республика Башкортостан"),
    ("03", "Республика Бурятия"),
    ("04", "Республика Алтай"),
    ("05", "Республика Дагестан"),
    ("06", "Республика Ингушетия"),
    ("07", "Кабардино-Балкарская Республика"),
    ("08", "Республика Калмыкия"),
    ("09", "Карачаево-Черкесская Республика"),
    ("10", "Республика Карелия"),
    ("11", "Республика Коми"),
    ("12", "Республика Марий Эл"),
    ("13", "Республика Мордовия"),
    ("14", "Республика Саха (Якутия)"),
    ("15", "Республика Северная Осетия — Алания"),
    ("16", "Республика Татарстан"),
    ("17", "Республика Тыва"),
    ("18", "Удмуртская Республика"),
    ("19", "Республика Хакасия"),
    ("20", "Чеченская Республика"),
    ("21", "Чувашская Республика"),
    ("22", "Алтайский край"),
    ("23", "Краснодарский край"),
    ("24", "Красноярский край"),
    ("25", "Приморский край"),
    ("26", "Ставропольский край"),
    ("27", "Хабаровский край"),
    ("28", "Амурская область"),
    ("29", "Архангельская область"),
    ("30", "Астраханская область"),
    ("31", "Белгородская область"),
    ("32", "Брянская область"),
    ("33", "Владимирская область"),
    ("34", "Волгоградская область"),
    ("35", "Вологодская область"),
    ("36", "Воронежская область"),
    ("37", "Ивановская область"),
    ("38", "Иркутская область"),
    ("39", "Калининградская область"),
    ("40", "Санкт-Петербург"),
    ("41", "Камчатский край"),
    ("42", "Кемеровская область — Кузбасс"),
    ("43", "Кировская область"),
    ("44", "Костромская область"),
    ("45", "Москва"),
    ("46", "Курская область"),
    ("47", "Ленинградская область"),
    ("48", "Липецкая область"),
    ("49", "Магаданская область"),
    ("50", "Московская область"),
    ("51", "Мурманская область"),
    ("52", "Нижегородская область"),
    ("53", "Новгородская область"),
    ("54", "Новосибирская область"),
    ("55", "Омская область"),
    ("56", "Оренбургская область"),
    ("57", "Орловская область"),
    ("58", "Пензенская область"),
    ("59", "Пермский край"),
    ("60", "Псковская область"),
    ("61", "Ростовская область"),
    ("62", "Рязанская область"),
    ("63", "Самарская область"),
    ("64", "Саратовская область"),
    ("65", "Сахалинская область"),
    ("66", "Свердловская область"),
    ("67", "Смоленская область"),
    ("68", "Тамбовская область"),
    ("69", "Тверская область"),
    ("70", "Томская область"),
    ("71", "Тульская область"),
    ("72", "Тюменская область"),
    ("73", "Ульяновская область"),
    ("74", "Челябинская область"),
    ("75", "Забайкальский край"),
    ("76", "Ярославская область"),
    ("77", "Калужская область"),
    ("78", "Еврейская автономная область"),
    ("79", "Республика Крым"),
    ("80", "Севастополь"),
    ("83", "Ненецкий автономный округ"),
    ("84", "Карачаево-Черкесия (резерв)"),
    ("86", "Ханты-Мансийский АО — Югра"),
    ("87", "Чукотский автономный округ"),
    ("89", "Ямало-Ненецкий автономный округ"),
    ("99", "Прочее"),
]


def upgrade() -> None:
    """Создаёт все таблицы, расширения, индексы и наполняет справочники."""

    # ------------------------------------------------------------------
    # 1. Расширения PostgreSQL
    # ------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ------------------------------------------------------------------
    # 2. Таблица регионов
    # ------------------------------------------------------------------
    op.create_table(
        "regions",
        sa.Column("code", sa.String(8), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
    )

    # ------------------------------------------------------------------
    # 3. Таблица категорий
    # ------------------------------------------------------------------
    op.create_table(
        "categories",
        sa.Column("slug", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
    )

    # ------------------------------------------------------------------
    # 4. Таблица пользователей
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "email",
            postgresql.CITEXT(),
            nullable=False,
            unique=True,
        ),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger, unique=True, nullable=True),
        sa.Column("telegram_chat_id", sa.BigInteger, nullable=True),
        sa.Column(
            "telegram_link_token", sa.String(64), unique=True, nullable=True
        ),
        sa.Column(
            "telegram_token_expires_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column("digest_time", sa.Time, nullable=True),
        sa.Column(
            "digest_tz",
            sa.String(64),
            nullable=False,
            server_default="Europe/Moscow",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ------------------------------------------------------------------
    # 5. Таблица refresh-токенов
    # ------------------------------------------------------------------
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("jti", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # ------------------------------------------------------------------
    # 6. Таблица лотов
    # ------------------------------------------------------------------
    op.create_table(
        "lots",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_lot_id", sa.String(128), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "category",
            sa.String(32),
            sa.ForeignKey("categories.slug"),
            nullable=True,
        ),
        sa.Column(
            "region_code",
            sa.String(8),
            sa.ForeignKey("regions.code"),
            nullable=True,
        ),
        sa.Column("price", sa.Numeric(18, 2), nullable=True),
        sa.Column("price_step", sa.Numeric(18, 2), nullable=True),
        sa.Column("source_url", sa.Text, nullable=False),
        sa.Column("auction_date", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("status", sa.String(64), nullable=True),
        sa.Column(
            "images",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "raw",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("search_tsv", postgresql.TSVECTOR(), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("source", "source_lot_id", name="uq_lots_source"),
    )

    # Индексы для lots
    op.create_index(
        "lots_search_idx",
        "lots",
        ["search_tsv"],
        postgresql_using="gin",
    )
    op.create_index(
        "lots_title_trgm",
        "lots",
        ["title"],
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )
    op.create_index(
        "lots_filters_idx",
        "lots",
        ["category", "region_code", "price", "auction_date"],
    )
    op.create_index(
        "lots_first_seen",
        "lots",
        [sa.text("first_seen_at DESC")],
    )

    # ------------------------------------------------------------------
    # 7. Триггер обновления search_tsv
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE FUNCTION lots_search_tsv_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_tsv :=
                setweight(to_tsvector('russian', coalesce(NEW.title, '')), 'A') ||
                setweight(to_tsvector('russian', coalesce(NEW.description, '')), 'B');
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER lots_tsv_trigger
        BEFORE INSERT OR UPDATE ON lots
        FOR EACH ROW EXECUTE FUNCTION lots_search_tsv_update()
        """
    )

    # ------------------------------------------------------------------
    # 8. Таблица избранного
    # ------------------------------------------------------------------
    op.create_table(
        "favorites",
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "lot_id",
            sa.BigInteger,
            sa.ForeignKey("lots.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ------------------------------------------------------------------
    # 9. Таблица сохранённых фильтров
    # ------------------------------------------------------------------
    op.create_table(
        "saved_filters",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column(
            "filter",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column(
            "notify_enabled",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("saved_filters_user", "saved_filters", ["user_id"])

    # ------------------------------------------------------------------
    # 10. Журнал уведомлений
    # ------------------------------------------------------------------
    op.create_table(
        "notification_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "filter_id",
            sa.BigInteger,
            sa.ForeignKey("saved_filters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lot_id",
            sa.BigInteger,
            sa.ForeignKey("lots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sent_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "user_id", "filter_id", "lot_id", name="uq_notification_log"
        ),
    )

    # ------------------------------------------------------------------
    # 11. Очередь outbox
    # ------------------------------------------------------------------
    op.create_table(
        "outbox",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chat_id", sa.BigInteger, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column(
            "lot_ids",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.execute(
        "CREATE INDEX outbox_unsent ON outbox (created_at) WHERE sent_at IS NULL"
    )

    # ------------------------------------------------------------------
    # 12. Журнал запусков парсера
    # ------------------------------------------------------------------
    op.create_table(
        "parser_runs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="running",
        ),
        sa.Column(
            "lots_seen", sa.Integer, nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "lots_new", sa.Integer, nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "lots_updated",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("error", sa.Text, nullable=True),
    )

    # ------------------------------------------------------------------
    # 13. Seed: категории и регионы
    # ------------------------------------------------------------------
    categories_table = sa.table(
        "categories",
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
    )
    op.bulk_insert(
        categories_table,
        [{"slug": slug, "name": name} for slug, name in CATEGORIES],
    )

    regions_table = sa.table(
        "regions",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
    )
    op.bulk_insert(
        regions_table,
        [{"code": code, "name": name} for code, name in REGIONS],
    )


def downgrade() -> None:
    """Удаляет все объекты, созданные в upgrade."""
    op.drop_table("parser_runs")
    op.execute("DROP INDEX IF EXISTS outbox_unsent")
    op.drop_table("outbox")
    op.drop_table("notification_log")
    op.drop_index("saved_filters_user", table_name="saved_filters")
    op.drop_table("saved_filters")
    op.drop_table("favorites")
    op.execute("DROP TRIGGER IF EXISTS lots_tsv_trigger ON lots")
    op.execute("DROP FUNCTION IF EXISTS lots_search_tsv_update")
    op.drop_index("lots_first_seen", table_name="lots")
    op.drop_index("lots_filters_idx", table_name="lots")
    op.drop_index("lots_title_trgm", table_name="lots")
    op.drop_index("lots_search_idx", table_name="lots")
    op.drop_table("lots")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
    op.drop_table("categories")
    op.drop_table("regions")
