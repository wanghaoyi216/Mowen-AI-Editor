# Novel AI Editor - 部署与运维文档

> **版本**: v1.0  
> **更新日期**: 2026-06-01

---

## 一、环境要求

### 1.1 硬件要求

| 资源 | 最低配置 | 推荐配置 |
|------|----------|----------|
| CPU | 4 核 | 8 核 |
| 内存 | 8 GB | 16 GB |
| 磁盘 | 20 GB | 50 GB SSD |
| 网络 | 需要访问 OpenRouter API | 稳定的互联网连接 |

### 1.2 软件要求

| 软件 | 版本 | 用途 |
|------|------|------|
| Docker | 24.0+ | 容器运行时 |
| Docker Compose | 2.20+ | 容器编排 |
| Git | 2.40+ | 版本控制 |

---

## 二、部署步骤

### 2.1 克隆项目

```bash
git clone <repository-url>
cd novel_ai_editer
```

### 2.2 配置环境变量

```bash
cd backend
cp .env.example .env
```

编辑 `.env` 文件，填入必要配置：

```ini
APP_NAME=Novel AI Editor API
APP_VERSION=0.1.0
API_V1_PREFIX=/api/v1
DEBUG=true

DATABASE_URL=postgresql+asyncpg://novel:novel_password@postgres:5432/novel_db
DATABASE_SYNC_URL=postgresql+psycopg://novel:novel_password@postgres:5432/novel_db

REDIS_URL=redis://:novel_redis_password@redis:6379/0

NEO4J_URI=bolt://neo4j:7687
NEO4J_DATABASE=neo4j
NEO4J_USER=neo4j
NEO4J_PASSWORD=novel_neo4j_password

FIRECRAWL_KEY=
TAVILY_KEY=
NVIDIA_API_KEY=nvapi-YOUR_API_KEY_HERE
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
```

> **重要**: `NVIDIA_API_KEY` 是必须配置的项目（`nvapi-` 开头），否则 AI 功能无法使用。

### 2.3 构建并启动容器

```bash
cd ..
docker compose up -d --build
```

### 2.4 验证服务状态

```bash
docker compose ps
```

预期输出（所有服务状态为 `healthy/running`）：

```
NAME                       IMAGE                      STATUS
novel-ai-editor-backend    novel_ai_editer-backend    Up (healthy)
novel-ai-editor-frontend   novel_ai_editer-frontend   Up
novel-ai-editor-neo4j      neo4j:5-community          Up (healthy)
novel-ai-editor-postgres   pgvector/pgvector:pg16     Up (healthy)
novel-ai-editor-redis      redis:7-alpine             Up (healthy)
```

### 2.5 检查数据库迁移

```bash
docker exec novel-ai-editor-backend alembic current
```

预期输出应显示最新迁移版本（如 `20260601_0004 (head)`）。

### 2.6 验证 API 连通性

```bash
curl http://localhost:8000/health
# 预期返回: {"status":"ok"}
```

---

## 三、日常运维

### 3.1 查看服务状态

```bash
# 所有容器状态
docker compose ps

# 后端服务日志
docker logs novel-ai-editor-backend --tail 50 -f

# 前端服务日志
docker logs novel-ai-editor-frontend --tail 20 -f

# PostgreSQL 日志
docker logs novel-ai-editor-postgres --tail 20
```

### 3.2 重启服务

```bash
# 重启单个服务
docker compose restart backend

# 重启所有服务
docker compose restart
```

### 3.3 重新构建服务

```bash
# 重新构建后端（修改 Python 代码后）
docker compose up -d --build backend

# 重新构建前端（修改 package.json 后）
docker compose up -d --build frontend

# 重新构建所有服务
docker compose up -d --build
```

### 3.4 数据库操作

```bash
# 查看当前迁移版本
docker exec novel-ai-editor-backend alembic current

# 升级到最新版本
docker exec novel-ai-editor-backend alembic upgrade head

# 回退一个版本
docker exec novel-ai-editor-backend alembic downgrade -1

# 连接 PostgreSQL
docker exec -it novel-ai-editor-postgres psql -U novel -d novel_db
```

### 3.5 Redis 操作

```bash
# 连接 Redis
docker exec -it novel-ai-editor-redis redis-cli -a novel_redis_password

# 查看 AI 上下文缓存
docker exec novel-ai-editor-redis redis-cli -a novel_redis_password "KEYS context:*"

# 清除所有缓存
docker exec novel-ai-editor-redis redis-cli -a novel_redis_password "FLUSHDB"
```

### 3.6 清理日志和临时数据

```bash
# 清理 Docker 未使用的资源
docker system prune -a

# 清理容器日志
truncate -s 0 $(docker inspect --format='{{.LogPath}}' novel-ai-editor-backend)
```

---

## 四、故障排查

### 4.1 后端无法启动

```bash
# 1. 查看完整日志
docker logs novel-ai-editor-backend --tail 100

# 2. 检查环境变量
docker exec novel-ai-editor-backend env | grep OPENROUTER

# 3. 检查数据库连接
docker exec novel-ai-editor-backend python -c "
from app.db.base import engine
import asyncio
async def test():
    async with engine.connect() as conn:
        print('DB connected!')
asyncio.run(test())
"

# 4. 重新构建
docker compose up -d --build backend
```

### 4.2 前端无法访问

```bash
# 1. 检查前端日志
docker logs novel-ai-editor-frontend --tail 30

# 2. 重启前端
docker compose restart frontend

# 3. 检查端口占用
netstat -ano | findstr "5173"

# 4. 强制重新构建
docker compose up -d --build frontend
```

### 4.3 AI 请求失败

```bash
# 1. 验证 API Key 配置
docker exec novel-ai-editor-backend python -c "
from app.core.config import settings
print(f'API Key configured: {bool(settings.nvidia_api_key)}')
"

# 2. 运行 AI 连通性测试
docker exec novel-ai-editor-backend python /app/scripts/test_ai_connectivity.py

# 3. 检查网络连接
docker exec novel-ai-editor-backend curl -I https://openrouter.ai/api/v1
```

### 4.4 数据库迁移失败

```bash
# 1. 查看迁移历史
docker exec novel-ai-editor-backend alembic history

# 2. 检查迁移文件是否有语法错误
docker exec novel-ai-editor-backend python -c "
import importlib
import os
migrations_dir = '/app/migrations/versions'
for f in sorted(os.listdir(migrations_dir)):
    if f.endswith('.py') and not f.startswith('__'):
        module_name = f[:-3]
        print(f'Checking {module_name}...')
        try:
            importlib.import_module(f'migrations.versions.{module_name}')
            print(f'  ✓ OK')
        except Exception as e:
            print(f'  ✗ Error: {e}')
"

# 3. 从指定版本重新迁移
docker exec novel-ai-editor-backend alembic downgrade base
docker exec novel-ai-editor-backend alembic upgrade head
```

### 4.5 Docker 镜像源问题

如果遇到 `403 Forbidden` 错误：

```bash
# 等待镜像源恢复后重试
docker compose up -d --build

# 或配置 Docker 镜像加速器
# 编辑 /etc/docker/daemon.json (Linux) 或 Docker Desktop Settings (Windows/Mac)
{
  "registry-mirrors": ["https://your-mirror-url"]
}
```

---

## 五、生产环境部署

### 5.1 安全配置

```ini
# .env 生产环境配置
DEBUG=false
API_V1_PREFIX=/api/v1

# 使用强密码
DATABASE_URL=postgresql+asyncpg://novel:<STRONG_PASSWORD>@postgres:5432/novel_db
REDIS_URL=redis://:<STRONG_PASSWORD>@redis:6379/0
NEO4J_PASSWORD=<STRONG_PASSWORD>

# 生产环境 CORS
# 在 backend/app/main.py 中修改
allow_origins=["https://your-domain.com"]
```

### 5.2 反向代理配置（Nginx 示例）

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5173;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 5.3 HTTPS 配置

```bash
# 使用 Let's Encrypt 获取免费证书
sudo certbot --nginx -d your-domain.com

# 自动续期
sudo certbot renew --dry-run
```

### 5.4 备份策略

```bash
# PostgreSQL 备份
docker exec novel-ai-editor-postgres pg_dump -U novel novel_db > backup_$(date +%Y%m%d).sql

# PostgreSQL 恢复
cat backup_20260601.sql | docker exec -i novel-ai-editor-postgres psql -U novel novel_db

# Redis 备份
docker exec novel-ai-editor-redis redis-cli -a novel_redis_password BGSAVE
docker cp novel-ai-editor-redis:/data/dump.rdb ./redis_backup_$(date +%Y%m%d).rdb
```

---

## 六、性能优化

### 6.1 数据库优化

```sql
-- 创建常用查询索引
CREATE INDEX idx_ai_tasks_project_id ON ai_tasks(project_id);
CREATE INDEX idx_chapters_project_id ON chapters(project_id);
CREATE INDEX idx_chapters_task_id ON chapters(task_id);
CREATE INDEX idx_content_embeddings_project_id ON content_embeddings(project_id);

-- 向量索引（使用 ivfflat）
CREATE INDEX ON content_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

### 6.2 Redis 缓存优化

```python
# 缓存热点查询结果
@cache(ttl=300)  # 5 分钟缓存
async def get_project(db, project_id):
    ...
```

### 6.3 前端性能优化

- 使用代码分割（Vite 默认启用）
- 图表组件使用 `React.memo` 避免不必要的重渲染
- 大量数据使用虚拟滚动

---

## 七、监控与告警

### 7.1 容器健康检查

```yaml
# docker-compose.yml 中的健康检查配置
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

### 7.2 日志聚合

```bash
# 查看所有服务日志
docker compose logs -f

# 仅查看后端错误日志
docker logs novel-ai-editor-backend 2>&1 | grep -i error
```

---

## 八、版本升级

### 8.1 升级步骤

```bash
# 1. 拉取最新代码
git pull

# 2. 停止当前服务
docker compose down

# 3. 重新构建并启动
docker compose up -d --build

# 4. 执行数据库迁移
docker exec novel-ai-editor-backend alembic upgrade head

# 5. 验证服务状态
docker compose ps
curl http://localhost:8000/health
```

### 8.2 回退步骤

```bash
# 1. 停止当前服务
docker compose down

# 2. 回退到上一个提交
git checkout <previous-commit-hash>

# 3. 重新构建并启动
docker compose up -d --build

# 4. 回退数据库迁移
docker exec novel-ai-editor-backend alembic downgrade <target-version>
```
