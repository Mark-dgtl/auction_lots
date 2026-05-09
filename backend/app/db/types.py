"""Кросс-диалектные типы SQLAlchemy.

Позволяют использовать одни модели и для PostgreSQL, и для SQLite (тесты).
"""

from sqlalchemy import BigInteger, Integer

# Первичный ключ: BIGSERIAL в PostgreSQL, INTEGER в SQLite (нужен для ROWID autoincrement).
BigIntPK = Integer().with_variant(BigInteger(), "postgresql")

# Внешний ключ: то же самое — BIGINT в PG, INTEGER в SQLite.
BigIntFK = Integer().with_variant(BigInteger(), "postgresql")
