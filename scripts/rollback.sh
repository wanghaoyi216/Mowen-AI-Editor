#!/bin/bash
# Novel AI Editor: 一键回滚 (Linux/macOS)
# 用 git checkout HEAD~1 回滚到上一版本并重建
set -e
cd "$(dirname "$0")/.."

echo "===== Novel AI Editor: 回滚到上一版本 ====="
if [ ! -d .git ]; then
  echo "错误：未检测到 .git 目录" >&2
  exit 1
fi

echo "当前 HEAD: $(git rev-parse --short HEAD)"
git checkout HEAD~1
echo "回滚到: $(git rev-parse --short HEAD)"

docker compose build --no-cache frontend backend
docker compose up -d
echo "===== 回滚完成 ====="
