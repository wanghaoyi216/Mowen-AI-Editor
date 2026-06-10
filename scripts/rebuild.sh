#!/bin/bash
# Novel AI Editor: 一键重建 (Linux/macOS)
# 重建 frontend + backend 镜像并重启所有服务
set -e

echo "===== Novel AI Editor: 一键重建 ====="
cd "$(dirname "$0")/.."

echo "[1/4] 停止 frontend 和 backend 容器..."
docker compose stop frontend backend

echo "[2/4] 重建镜像（无缓存）..."
docker compose build --no-cache frontend backend

echo "[3/4] 启动所有服务..."
docker compose up -d

echo "[4/4] 等待健康检查..."
sleep 10
docker compose ps

echo "===== 重建完成 ====="
echo "前端: http://localhost:5173"
echo "后端: http://localhost:8000/api/v1/docs"
