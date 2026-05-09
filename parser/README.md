# parser — парсер лотов торговых площадок

Пакет собирает лоты с двух источников и отдаёт их backend в едином формате
`ParsedLot` (Pydantic v2). Контракт лота зафиксирован в
[`docs/CONTRACTS.md`](../docs/CONTRACTS.md) §1 и в [`parser/base.py`](parser/base.py).

## Источники

| name         | URL                               | Транспорт                          |
| ------------ | --------------------------------- | ---------------------------------- |
| `efrsb`      | `bankrot.fedresurs.ru`            | JSON API (`/backend/trademsg/search`), HTML-fallback |
| `torgi_gov`  | `torgi.gov.ru`                    | JSON API (`/new/api/public/lotcards/search`)          |

Оба источника — только HTTP через `httpx.AsyncClient`. Никакого Playwright
на первом подходе; он может понадобиться только если Qrator на ЕФРСБ
полностью закроет API без сессионных cookies — в этом случае см.
комментарий-fallback в `parser/sources/efrsb.py`.

## Установка и тесты

```bash
cd parser
pip install -e ".[dev]"
pytest
```

Все сетевые обращения в тестах замоканы через `respx`, поэтому интернет
не нужен. Фикстуры — минимально-валидные JSON-ответы, собранные из реального
API (`fixtures/torgi/*.json`) и по документированной схеме ЕФРСБ
(`fixtures/efrsb/*.json`).

## CLI

```bash
# Стандартный прогон
python -m parser.cli run torgi_gov --limit 20

# С фильтрами
python -m parser.cli run torgi_gov --limit 5 --category real_estate --region 77

# Для EFRSB в боевом окружении
python -m parser.cli run efrsb --limit 20 --log-level DEBUG
```

На stdout — JSON-массив `ParsedLot` (`model_dump(mode="json")`).

Короткий алиас (после `pip install -e .`): `tenders-parser run torgi_gov --limit 5`.

## Архитектура

```
parser/
  parser/
    base.py           # ParsedLot, ParseFilters, BaseSource, CATEGORY_SLUGS
    normalizer.py     # parse_price, parse_datetime, normalize_whitespace,
                      # guess_category, parse_okato
    sources/
      efrsb.py        # EfrsbSource
      torgi.py        # TorgiSource
    cli.py            # argparse CLI
    __main__.py       # python -m parser
  fixtures/
    efrsb/*.json
    torgi/*.json
  tests/
    test_normalizer.py
    test_efrsb.py
    test_torgi.py
```

Ключевой принцип: **fetch отделён от парсинга, парсинг от нормализации**.
`_fetch_page` ничего не знает про `ParsedLot`, а `_build_lot` не делает
HTTP.

## Как добавить новый источник

1. В `parser/sources/` создать модуль `<name>.py` с классом, наследующим
   `BaseSource`. Обязательно задать `name: str`.
2. Реализовать `fetch_lots(...)` как `async def` с `yield` (асинхронный
   генератор). Страницы получать через `httpx.AsyncClient`, ретраи через
   `tenacity.AsyncRetrying` (3 попытки, экспоненциальный backoff на 5xx
   и `httpx.TransportError`).
3. Для нормализации использовать только функции из `parser.normalizer`.
   Категории — `CATEGORY_SLUGS`. Регион — `parse_okato`.
4. Зарегистрировать источник в `parser/cli.py::_SOURCES`.
5. Фикстуры — в `fixtures/<name>/`, тесты — в `tests/test_<name>.py`
   с моком `respx`.

## Контракт с backend

- Формат — `ParsedLot` (см. `parser/base.py`). Менять нельзя.
- Все `datetime` — timezone-aware UTC.
- Цены — `Decimal` в рублях.
- `region` — либо цифровой ОКАТО (2/5/8/11 цифр), либо строка-имя. Backend
  сам мапит имя через `LIKE` на свой справочник.
- `category` — slug из `CATEGORY_SLUGS` или `None`. Если источник отдал
  что-то неизвестное — мы возвращаем `None`, не выдумываем.
- `raw` всегда заполняется — там лежит весь исходный ответ источника.
  Backend может смотреть туда при разборе сложных случаев.

## Ограничения

- ЕФРСБ защищён Qrator. В боевом деплое понадобятся сессионные cookies
  (обычно одноразовый challenge при первом заходе). Сейчас источник
  гарантирует только корректное поведение на корректном JSON-ответе.
- `guess_category` — простая rule-based эвристика. Для тонких категорий
  (например, различать «оборудование» vs «инвентарь») лучше на бэкенде
  делать доклассификацию.
- Регионы из torgi возвращаются как `subjectRFCode` (цифровой код
  субъекта РФ, не путать с ОКАТО); у них формат «2 цифры» совпадает,
  но для 5/8/11-значных кодов ОКАТО такой подход даст только верхний
  уровень.
