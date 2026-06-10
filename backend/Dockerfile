# ─────────────────────────────────────────────────────────────────────────────
# Novel AI Editor · 后端 FastAPI 生产镜像
#   - 两阶段构建：第一阶段 pip 安装依赖；第二阶段仅含运行时
#   - 使用 uvicorn 启动，并在启动阶段执行 alembic 迁移
# ─────────────────────────────────────────────────────────────────────────────

# 阶段 1：pip install（把构建产物与运行时分离，减少体积）
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 安装需要编译的依赖的编译器（cryptography 等）
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libffi-dev \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt

# 阶段 2：运行时
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.local/bin:$PATH"

WORKDIR /app

# 把编译好的依赖从 builder 拷贝过来
COPY --from=builder /install /usr/local

# 拷贝代码 & 迁移脚本
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
COPY scripts ./scripts

RUN chmod +x /app/scripts/docker-entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=4 \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read(); sys.exit(0)" || exit 1

CMD ["/app/scripts/docker-entrypoint.sh"]
