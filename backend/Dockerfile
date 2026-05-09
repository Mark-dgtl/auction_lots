FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
 && rm -rf /var/lib/apt/lists/*

COPY parser /app/parser
# editable: при volume ./parser:/app/parser на сервере подхватываются изменения без rebuild
RUN pip install -e /app/parser

COPY backend /app/backend
WORKDIR /app/backend
RUN pip install -e .

EXPOSE 8000
