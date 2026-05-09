"""CLI для ручной проверки парсеров и интеграции с backend.

Примеры использования:

.. code-block:: shell

    python -m parser.cli run efrsb --limit 20
    python -m parser.cli run torgi_gov --limit 20 --category real_estate
    python -m parser.cli run torgi_gov --limit 5 --region 77 --price-from 100000

На stdout выводится JSON-массив :class:`~parser.base.ParsedLot`
(``model_dump(mode="json")``). Кодировка — UTF-8, ``ensure_ascii=False``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from decimal import Decimal
from typing import Iterable

from parser.base import BaseSource, ParseFilters, ParsedLot
from parser.sources.efrsb import EfrsbSource
from parser.sources.torgi import TorgiSource


_SOURCES: dict[str, type[BaseSource]] = {
    EfrsbSource.name: EfrsbSource,
    TorgiSource.name: TorgiSource,
}


def _build_parser() -> argparse.ArgumentParser:
    """Создаёт argparse-парсер CLI."""
    p = argparse.ArgumentParser(
        prog="parser",
        description="Запуск парсеров торговых площадок.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Запустить парсер одного источника.")
    run.add_argument(
        "source",
        choices=sorted(_SOURCES),
        help="Идентификатор источника.",
    )
    run.add_argument(
        "--limit", type=int, default=20, help="Максимальное число лотов."
    )
    run.add_argument(
        "--category",
        type=str,
        default=None,
        help="Slug категории (real_estate, vehicle, ...).",
    )
    run.add_argument(
        "--region", type=str, default=None, help="Код или имя региона."
    )
    run.add_argument(
        "--query", type=str, default=None, help="Поисковая строка."
    )
    run.add_argument(
        "--price-from", type=Decimal, default=None, dest="price_from"
    )
    run.add_argument(
        "--price-to", type=Decimal, default=None, dest="price_to"
    )
    run.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    return p


async def _run(args: argparse.Namespace) -> int:
    """Запускает указанный источник и печатает JSON-массив."""
    source_cls = _SOURCES[args.source]
    source = source_cls()
    filters = ParseFilters(
        query=args.query,
        category=args.category,
        region=args.region,
        price_from=args.price_from,
        price_to=args.price_to,
    )

    log = logging.getLogger("parser.cli")
    results: list[ParsedLot] = []
    try:
        async for lot in source.fetch_lots(filters=filters, limit=args.limit):
            results.append(lot)
    except Exception as exc:  # noqa: BLE001
        # Полный traceback — только в DEBUG, иначе коротко.
        if log.isEnabledFor(logging.DEBUG):
            log.exception("Источник %s завершился с ошибкой", args.source)
        else:
            log.error("Источник %s завершился с ошибкой: %s", args.source, exc)
        return 1

    _dump_json(results)
    return 0


def _dump_json(lots: Iterable[ParsedLot]) -> None:
    """Сериализует ``ParsedLot`` в stdout как JSON-массив."""
    payload = [lot.model_dump(mode="json") for lot in lots]
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    sys.stdout.flush()


def main(argv: list[str] | None = None) -> int:
    """Точка входа CLI. Возвращает код выхода процесса."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger().setLevel(args.log_level)

    if args.command == "run":
        return asyncio.run(_run(args))

    parser.error(f"Неизвестная команда: {args.command}")
    return 2  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
