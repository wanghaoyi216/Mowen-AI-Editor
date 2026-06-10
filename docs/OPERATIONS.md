# Novel AI Editor — 运维手册

> **版本**: v1.1  
> **更新日期**: 2026-06-03  
> **目标读者**: 第一次接手的运维 / 二次开发者

本文档面向"今天就要让系统跑起来 + 出问题能自查"的运维同学。预计 5 分钟可完成首次启动，15 分钟可完成常见故障定位。

---

## 一、环境变量清单

环境变量定义于 `backend/app/core/config.py`（Pydantic Settings）。下面按"必填 / 推荐 / 可选"三类列出，**所有变量都从 `backend/.env` 读取**。

### 1.1 必填（缺失则 AI 功能不可用）

| 变量 | 示例值 | 说明 |
|------|--------|------|
| `NVIDIA_API_KEY` | `nvapi-...` | **NVIDIA NIM** 平台 token。无它则所有 LLM 调用都会 401。 |
| `NVIDIA_BASE_URL` | `https://integrate.api.nvidia.com/v1` | NVIDIA NIM 端点（OpenAI 兼容） |

> 项目统一走英伟达 NIM 端点。key 必须是 `nvapi-` 开头，`sk-or-v1-` 开头是 OpenRouter 平台的 key，会被 NVIDIA 拒绝。

### 1.2 推荐（生产环境必改）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `POSTGRES_PASSWORD` | `novel_ai_password` | PostgreSQL root 密码，对应 `DATABASE_URL` 中的 user/pass。 |
| `NEO4J_AUTH` | `neo4j/password` | Neo4j 用户名/密码，对应 `NEO4J_USER` / `NEO4J_PASSWORD`。 |
| `REDIS_URL` | `redis://redis:6379/0` | Redis 连接串，建议加上密码。 |

### 1.3 可选（有合理默认值）

| 变量 | 默认值 | 含义 |
|------|--------|------|
| `APP_NAME` | `Novel AI Editor API` | OpenAPI 标题 |
| `APP_VERSION` | `0.1.0` | 启动时打印到 banner |
| `API_V1_PREFIX` | `/api/v1` | 所有 API 前缀 |
| `DATABASE_URL` | `postgresql+psycopg://...` | 主库连接串 |
| `NVIDIA_BASE_URL` | `https://integrate.api.nvidia.com/v1` | NVIDIA NIM 端点（OpenAI 兼容） |
| `NVIDIA_PRIMARY_MODEL` | `minimaxai/minimax-m2.7` | 主调用模型 |
| `NVIDIA_FALLBACK_MODELS` | `minimaxai/minimax-m2.7,meta/llama-3.1-70b-instruct` | fallback 链，逗号分隔 |
| `LLM_REQUEST_TIMEOUT_SECONDS` | `300` | 单次 LLM 调用的 HTTP 超时（秒） |
| `EXTERNAL_REQUEST_TIMEOUT_SECONDS` | `120` | 其它外部 HTTP 调用超时 |
| `EXTERNAL_REQUEST_RETRIES` | `5` | 通用外部调用重试次数 |
| `RATE_LIMIT_CALLS_PER_MINUTE` | `40` | Redis 滑动窗口限流阈值 |
| `TASK_RUNTIME_CACHE_TTL_SECONDS` | `3600` | 任务运行时状态在 Redis 的 TTL |
| `CREATOR_MODEL` | `minimaxai/minimax-m2.7` | 开放 AI 创作模型 |
| `CONTROLLER_MODEL` | `minimaxai/minimax-m2.7` | 严格 AI 控制模型 |
| `EMBEDDING_MODEL` | `nvidia/embed-qa-4` | Embedding 模型（预留） |
| `CREATOR_TEMPERATURE` | `1.0` | 创作模型默认温度 |
| `CONTROLLER_TEMPERATURE` | `0.4` | 控制模型默认温度 |
| `SIMILARITY_THRESHOLD` | `0.85` | 内容相似度阈值（AI Diversity Engine） |
| `STYLE_DIVERSITY_THRESHOLD` | `0.8` | 风格多样性阈值 |
| `FIRECRAWL_KEY` | （空） | Trend 阶段抓取网页用，可选 |
| `TAVILY_KEY` | （空） | Trend 阶段搜索用，可选 |

### 1.4 .env 示例（开发环境）

```ini
# backend/.env
APP_NAME=Novel AI Editor API
APP_VERSION=0.1.0
API_V1_PREFIX=/api/v1
DEBUG=true

DATABASE_URL=postgresql+psycopg://novel:novel_password@postgres:5432/novel_db
DATABASE_SYNC_URL=postgresql+psycopg://novel:novel_password@postgres:5432/novel_db

REDIS_URL=redis://:novel_redis_password@redis:6379/0

NEO4J_URI=bolt://neo4j:7687
NEO4J_DATABASE=neo4j
NEO4J_USER=neo4j
NEO4J_PASSWORD=novel_neo4j_password

NVIDIA_API_KEY=nvapi-YOUR_KEY_HERE
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_PRIMARY_MODEL=nvidia/nemotron-3-ultra-550b-a55b
NVIDIA_FALLBACK_MODELS=minimaxai/minimax-m2.7,meta/llama-3.1-70b-instruct

LLM_REQUEST_TIMEOUT_SECONDS=300
RATE_LIMIT_CALLS_PER_MINUTE=40
```

---

## 二、Docker 启动（首次）

### 2.1 Windows (PowerShell)

```powershell
# 1. 确保 docker CLI 在 PATH 中
$env:Path = "C:\Program Files\Docker\Docker\resources\bin;$env:Path"

# 2. 进入项目根目录
cd d:\Study\novel_ai_editer

# 3. 一键拉起（首次会自动 build 镜像）
docker compose up -d

# 4. 验证所有容器 healthy
docker compose ps
```

### 2.2 预期 `docker compose ps` 输出

```
NAME                       IMAGE                      STATUS
novel-ai-editor-backend    novel_ai_editer-backend    Up (healthy)
novel-ai-editor-frontend   novel_ai_editer-frontend   Up
novel-ai-editor-neo4j      neo4j:5-community          Up (healthy)
novel-ai-editor-postgres   pgvector/pgvector:pg16     Up (healthy)
novel-ai-editor-redis      redis:7-alpine             Up (healthy)
```

### 2.3 启动失败的快速排查

```powershell
# 查看后端启动日志（包含 alembic 迁移）
docker compose logs backend --tail 100

# 单独重启后端
docker compose restart backend

# 强制重建 backend（依赖或 Dockerfile 变更后）
docker compose up -d --build backend
```

---

## 三、Docker 重建（代码改动后）

### 3.1 后端 Python 代码改动

```powershell
# 方式 A：只 rebuild backend 镜像再 restart
docker compose up -d --build backend

# 方式 B：完全清掉再起
docker compose down backend
docker compose build --no-cache backend
docker compose up -d backend
```

> **Alembic 迁移**：修改了 `backend/app/db/models.py` 后必须新增迁移文件，否则 `docker compose up -d` 不会自动建表。

### 3.2 前端代码改动

```powershell
docker compose up -d --build frontend
```

> 浏览器侧需要按 **Ctrl + Shift + R** 强制刷新避开 Vite HMR 缓存。

### 3.3 配置（docker-compose.yml / Dockerfile）改动

```powershell
# 重启整套
docker compose down
docker compose up -d --build
```

### 3.4 清空数据库重新迁移

```powershell
# 警告：会删除所有数据
docker compose down -v
docker compose up -d --build
```

---

## 四、健康检查端点

后端启动后访问 `http://localhost:8000/api/v1/health/*` 系列。所有响应遵循 `ApiResponse[T]` 包装。

### 4.1 6 个端点速查表

| 端点 | 用途 | 关键字段 |
|------|------|----------|
| `GET /health` | 存活探针 | `status: "ok"` |
| `GET /health/detailed` | 各依赖状态 | `postgres / redis / neo4j` 各自 `status` |
| `GET /health/metrics` | Prometheus 文本 | `task_total / chapter_total / llm_calls_total` |
| `GET /health/rate-limit` | 限流剩余配额 | `remaining / limit / window_seconds` |
| `GET /health/tasks` | 任务状态统计 | `pending / running / completed / failed / cancelled` 计数 |
| `GET /health/database` | DB 连接池 | `pool_size / checked_out / overflow` |

### 4.2 预期输出示例

**`GET /api/v1/health`**
```json
{ "success": true, "message": "ok", "data": { "status": "ok" } }
```

**`GET /api/v1/health/detailed`**
```json
{
  "success": true,
  "message": "detailed health",
  "data": {
    "status": "ok",
    "services": {
      "postgres": { "status": "ok", "latency_ms": 3 },
      "redis":    { "status": "ok", "latency_ms": 1 },
      "neo4j":    { "status": "ok", "latency_ms": 12 }
    }
  }
}
```

**`GET /api/v1/health/metrics`**
```
# HELP novel_tasks_total Total tasks grouped by status
# TYPE novel_tasks_total counter
novel_tasks_total{status="completed"} 12
novel_tasks_total{status="running"} 1
novel_tasks_total{status="failed"} 0
# HELP novel_llm_calls_total Total LLM calls grouped by model
# TYPE novel_llm_calls_total counter
novel_llm_calls_total{model="minimaxai/minimax-m2.7"} 87
```

**`GET /api/v1/health/rate-limit`**
```json
{
  "success": true,
  "message": "rate limit snapshot",
  "data": { "limit": 40, "remaining": 31, "window_seconds": 60 }
}
```

**`GET /api/v1/health/tasks`**
```json
{
  "success": true,
  "message": "task statistics",
  "data": {
    "pending": 0,
    "running": 1,
    "completed": 12,
    "failed": 0,
    "cancelled": 1
  }
}
```

**`GET /api/v1/health/database`**
```json
{
  "success": true,
  "message": "db pool status",
  "data": {
    "pool_size": 5,
    "checked_out": 1,
    "overflow": 0,
    "url": "postgresql+psycopg://novel:***@postgres:5432/novel_db"
  }
}
```

---

## 五、故障树（4 个常见问题）

### 5.1 LLM API 超时

**症状**：任务长时间卡在 `running`，日志出现 `ReadTimeout` / `ConnectError` / `502 Bad Gateway`。

**排查步骤**：

```powershell
# 1. 看具体超时配置
docker exec novel-ai-editor-backend env | grep -E "LLM_REQUEST|TIMEOUT"

# 2. 看是否被限流
curl http://localhost:8000/api/v1/health/rate-limit
# 若 remaining = 0：触发限流，fallback 链应自动接管
# 若剩余充足：进入步骤 3

# 3. 验证 key 有效性
docker exec novel-ai-editor-backend python -c "
from app.core.config import settings
print('key configured:', bool(settings.nvidia_api_key))
print('primary model:', settings.nvidia_primary_model)
"

# 4. 直接 ping 上游
docker exec novel-ai-editor-backend curl -I https://integrate.api.nvidia.com/v1
```

**修复**：

| 原因 | 修复 |
|------|------|
| `LLM_REQUEST_TIMEOUT_SECONDS` 太短 | 调到 `300` 或更高 |
| Key 失效 | 重新签发 `NVIDIA_API_KEY` 并 `docker compose restart backend` |
| 触发限流 | 等 60s 或提升 `RATE_LIMIT_CALLS_PER_MINUTE` |

### 5.2 任务卡住

**症状**：任务 `running` 状态超过 10 分钟无任何章节完成。

**排查步骤**：

```powershell
# 1. 看任务运行时
curl http://localhost:8000/api/v1/projects/1/tasks/1/runtime

# 2. 看限流
curl http://localhost:8000/api/v1/health/rate-limit

# 3. 看步骤
curl http://localhost:8000/api/v1/projects/1/tasks/1/steps

# 4. 看后端日志最近 100 行
docker compose logs backend --tail 100 | grep -i "error\|warn"
```

**修复**：

```powershell
# 1. 取消任务
curl -X POST http://localhost:8000/api/v1/projects/1/tasks/1/cancel

# 2. 等待任务变 cancelled
curl http://localhost:8000/api/v1/projects/1/tasks/1

# 3. 从检查点续写
curl -X POST http://localhost:8000/api/v1/projects/1/tasks/1/resume
```

> 取消 + resume 是幂等的，可反复执行不会损坏数据。

### 5.3 容器重启后状态丢失

**症状**：`docker compose down && docker compose up -d` 后，任务 `running` 变回 `pending`，但 PG 中章节数对得上。

**原因**：任务运行时状态在内存 + Redis（短期），进程消失后丢失；持久化的 `task_checkpoints` 表还在。

**修复**：

```powershell
# 1. 列出失败 / 已取消任务
curl http://localhost:8000/api/v1/projects/1/tasks | python -m json.tool

# 2. 对每个需要恢复的任务调 resume
curl -X POST http://localhost:8000/api/v1/projects/1/tasks/1/resume
# → 返回 202 Accepted
# → 后台线程从 last_chapter_no + 1 续写
```

> 已在 `running` 状态但实际是僵尸进程的任务，建议先 `cancel` 再 `resume`。

### 5.4 DB 迁移失败

**症状**：`docker compose up -d` 时后端容器反复重启，错误信息含 `alembic.util.exc.CommandError` 或 `relation "xxx" does not exist`。

**排查步骤**：

```powershell
# 1. 查迁移相关日志
docker compose logs backend | grep -i migration

# 2. 查当前版本
docker exec novel-ai-editor-backend alembic current

# 3. 查历史
docker exec novel-ai-editor-backend alembic history
```

**修复**：

```powershell
# 方式 A：补到最新（最常见）
docker exec novel-ai-editor-backend alembic upgrade head

# 方式 B：回退一版再升级（怀疑中间版本有问题）
docker exec novel-ai-editor-backend alembic downgrade -1
docker exec novel-ai-editor-backend alembic upgrade head

# 方式 C：核弹选项（清空数据）
docker compose down -v
docker compose up -d --build
```

> 任何迁移失败都不会影响前端访问 Swagger UI；前端只关心后端是否 `/api/v1/health = ok`。

---

## 六、常用运维命令速查

| 场景 | 命令 |
|------|------|
| 看所有容器状态 | `docker compose ps` |
| 后端实时日志 | `docker compose logs backend -f` |
| 单独重启后端 | `docker compose restart backend` |
| 重建后端 | `docker compose up -d --build backend` |
| 进 PG 容器 | `docker exec -it novel-ai-editor-postgres psql -U novel -d novel_db` |
| 进 Redis 容器 | `docker exec -it novel-ai-editor-redis redis-cli` |
| 看 Redis 限流键 | `docker exec novel-ai-editor-redis redis-cli "KEYS rate_limit:*"` |
| 清 Redis 限流 | `docker exec novel-ai-editor-redis redis-cli "FLUSHDB"` |
| 看磁盘占用 | `docker system df` |
| 清理无用镜像 | `docker image prune -a` |

---

## 七、监控建议（生产环境）

> 项目当前版本（v1.1）自带 `/api/v1/health/metrics` Prometheus 端点，建议接入：

| 监控项 | 告警阈值 |
|--------|----------|
| `novel_tasks_total{status="failed"}` 5 分钟增长率 | > 3 |
| `novel_llm_calls_total{model="..."}` 速率 | 与 LLM 上游配额挂钩 |
| `/health/rate-limit` 的 `remaining` | < 5 持续 1 分钟 |
| `/health/database` 的 `checked_out / pool_size` | > 80% |
| 容器 `STATUS != healthy` | 持续 2 分钟 |

---

> **相关文档**：[`docs/ARCHITECTURE.md`](./ARCHITECTURE.md)（架构）、[`docs/API_CHEATSHEET.md`](./API_CHEATSHEET.md)（API 速查）
