#!/bin/sh
set -e

echo "[backend] running alembic migrations..."
# 同时存在旧 PG 迁移链（archived，20260602_0004 引用了不存在的 20260601_0004）
# 与 MySQL 新基线时，显式升级到 MySQL 分支的最新版本，
# 避免 ``Multiple head revisions`` 报错。
alembic upgrade 20260610_0002_story_arcs_themes || alembic upgrade heads

echo "[backend] starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
