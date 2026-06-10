# Novel AI Editor — API 速查表

> **版本**: v1.1  
> **更新日期**: 2026-06-03  
> **目标读者**: 前端开发者 / API 集成方

本文档列出后端所有高频端点，每个端点均包含用途、请求示例（curl）和响应示例（JSON）。

---

## 一、快速开始

| 项 | 值 |
|----|----|
| Base URL | `http://localhost:8000/api/v1` |
| Swagger UI | `http://localhost:8000/api/v1/docs` |
| ReDoc | `http://localhost:8000/api/v1/redoc` |
| OpenAPI JSON | `http://localhost:8000/api/v1/openapi.json` |
| Content-Type | `application/json` |
| 统一响应 | `ApiResponse<T> = { success, message, data, meta? }` |

> **所有响应都被 `ApiResponse[T]` 包装**，所以 `data` 字段才是真正的业务负载。

---

## 二、端点速查表

| 方法 | 路径 | 用途 | Tag |
|------|------|------|-----|
| GET  | `/health` | 存活探针 | Health |
| GET  | `/health/detailed` | 各依赖状态详情 | Health |
| GET  | `/health/metrics` | Prometheus 指标 | Health |
| GET  | `/health/rate-limit` | 限流剩余配额 | Health |
| GET  | `/health/tasks` | 任务状态统计 | Health |
| GET  | `/health/database` | DB 连接池状态 | Health |
| GET  | `/projects/{id}/tasks` | 列出项目下所有任务 | Tasks |
| POST | `/projects/{id}/tasks` | 创建一个新任务（不执行） | Tasks |
| DELETE | `/projects/{id}/tasks/{task_id}` | 删除任务 | Tasks |
| POST | `/projects/{id}/tasks/execute-react` | 执行 ReAct 任务 | Tasks |
| POST | `/projects/{id}/tasks/execute-trend-react` | 执行 Trend+ReAct 任务 | Tasks |
| POST | `/projects/{id}/tasks/execute-auto-novel-workflow` | 执行全自动三阶段任务 | Tasks |
| GET  | `/projects/{id}/tasks/{task_id}` | 查询单个任务详情 | Tasks |
| GET  | `/projects/{id}/tasks/{task_id}/steps` | 查询任务步骤 | Tasks |
| GET  | `/projects/{id}/tasks/{task_id}/runtime` | 读取任务运行时状态 | Tasks |
| POST | `/projects/{id}/tasks/{task_id}/runtime` | 写任务运行时状态 | Tasks |
| **POST** 🔥 | **`/projects/{id}/tasks/{task_id}/cancel`** | **取消任务** | **Tasks** |
| **POST** 🔥 | **`/projects/{id}/tasks/{task_id}/resume`** | **从检查点恢复** | **Tasks** |
| GET  | `/projects/{id}/tasks/models` | 可用模型列表 | Tasks |
| GET  | `/projects/{id}/tasks/concurrency` | 并发槽位状态 | Tasks |
| **GET** 🔥 | **`/projects/{id}/tasks/llm-stats`** | **LLM 调用统计** | **Tasks** |
| POST | `/projects/{id}/tasks/{task_id}/control` | 任务运行时控制（pause/resume/...） | Tasks |
| GET  | `/projects/{id}/tasks/{task_id}/step-runtime` | 步骤级运行时状态 | Tasks |
| GET  | `/projects/{id}/tasks/{task_id}/logs` | 任务日志 | Tasks |

> 🔥 红色标记 = 本次新增的 3 个端点（来自 Task 4/5/6）。

---

## 三、本次新增端点详解（标红 🔥）

### 🔥 POST /projects/{id}/tasks/{task_id}/cancel

**用途**：设置取消标志，后台线程在每章 LLM 调用前检测到后 `break` 循环。**幂等**，重复点击不会报错。

**请求示例**：

```bash
curl -X POST http://localhost:8000/api/v1/projects/1/tasks/1/cancel
```

**响应示例**：

```json
{
  "success": true,
  "message": "task cancellation requested",
  "data": {
    "task_id": 1,
    "previous_status": "running",
    "new_status": "cancelling"
  }
}
```

---

### 🔥 POST /projects/{id}/tasks/{task_id}/resume

**用途**：从 `task_checkpoints.last_chapter_no + 1` 续写。**仅 `failed` / `cancelled` 状态可 resume**，`completed` 状态会返回 400。

**请求示例**：

```bash
curl -X POST http://localhost:8000/api/v1/projects/1/tasks/1/resume
```

**响应示例**（202 Accepted）：

```json
{
  "success": true,
  "message": "task resumed from checkpoint",
  "data": {
    "task_id": 1,
    "resumed_from_chapter": 6,
    "status": "running"
  }
}
```

---

### 🔥 GET /projects/{id}/tasks/llm-stats

**用途**：聚合 `rate_limiter` 计数器，返回全局 LLM 调用统计。

**请求示例**：

```bash
curl http://localhost:8000/api/v1/projects/1/tasks/llm-stats
```

**响应示例**：

```json
{
  "success": true,
  "message": "llm call statistics",
  "data": {
    "total_calls": 87,
    "total_tokens": 124500,
    "avg_latency_ms": 1820,
    "failure_count": 2,
    "by_model": {
      "minimaxai/minimax-m2.7": 70,
      "meta/llama-3.1-70b-instruct": 17
    },
    "window": {
      "since": "2026-06-03T10:00:00Z",
      "until": "2026-06-03T10:30:00Z"
    }
  }
}
```

---

## 四、健康检查端点（详细）

### GET /health

**用途**：最简存活探针。

**请求示例**：

```bash
curl http://localhost:8000/api/v1/health
```

**响应示例**：

```json
{ "success": true, "message": "ok", "data": { "status": "ok" } }
```

---

### GET /health/detailed

**用途**：返回各依赖（PG / Redis / Neo4j）独立状态。

**响应示例**：

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

---

### GET /health/metrics

**用途**：Prometheus 文本格式指标，可被 Prometheus / Grafana 抓取。

**响应示例**：

```
# HELP novel_tasks_total Total tasks grouped by status
# TYPE novel_tasks_total counter
novel_tasks_total{status="completed"} 12
novel_tasks_total{status="running"} 1
```

---

### GET /health/rate-limit

**用途**：查看滑动窗口限流剩余配额。

**响应示例**：

```json
{
  "success": true,
  "message": "rate limit snapshot",
  "data": { "limit": 40, "remaining": 31, "window_seconds": 60 }
}
```

---

### GET /health/tasks

**用途**：按状态聚合任务计数。

**响应示例**：

```json
{
  "success": true,
  "message": "task statistics",
  "data": {
    "pending": 0, "running": 1, "completed": 12,
    "failed": 0, "cancelled": 1
  }
}
```

---

### GET /health/database

**用途**：PostgreSQL 连接池详情。

**响应示例**：

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

## 五、任务管理端点（详细）

### GET /projects/{id}/tasks

**用途**：列出项目的所有任务。

**请求示例**：

```bash
curl http://localhost:8000/api/v1/projects/1/tasks
```

**响应示例**：

```json
{
  "success": true,
  "message": "tasks listed",
  "data": [
    { "id": 1, "task_type": "auto_novel_workflow", "status": "running", "title": "仙剑奇侠 · 自动创作" },
    { "id": 2, "task_type": "react", "status": "completed", "title": "世界观测试" }
  ]
}
```

---

### POST /projects/{id}/tasks

**用途**：创建一个空任务（不执行）。

**请求示例**：

```bash
curl -X POST http://localhost:8000/api/v1/projects/1/tasks \
  -H "Content-Type: application/json" \
  -d '{ "task_type": "react", "title": "测试任务" }'
```

**响应示例**：

```json
{
  "success": true,
  "message": "task created",
  "data": { "id": 3, "task_type": "react", "status": "pending", "title": "测试任务" }
}
```

---

### DELETE /projects/{id}/tasks/{task_id}

**用途**：删除任务及其关联数据。

**请求示例**：

```bash
curl -X DELETE http://localhost:8000/api/v1/projects/1/tasks/3
```

**响应示例**：

```json
{ "success": true, "message": "task deleted", "data": { "task_id": 3 } }
```

---

### POST /projects/{id}/tasks/execute-react

**用途**：执行一次 ReAct 风格的 AI 任务。

**请求示例**：

```bash
curl -X POST http://localhost:8000/api/v1/projects/1/tasks/execute-react \
  -H "Content-Type: application/json" \
  -d '{ "initial_prompt": "生成一个赛博朋克世界观", "max_steps": 8 }'
```

**响应示例**：

```json
{
  "success": true,
  "message": "react task started",
  "data": { "task_id": 4, "status": "running" }
}
```

---

### POST /projects/{id}/tasks/execute-trend-react

**用途**：执行 Trend+ReAct 任务（先做热点探索，再 ReAct）。

**请求示例**：

```bash
curl -X POST http://localhost:8000/api/v1/projects/1/tasks/execute-trend-react \
  -H "Content-Type: application/json" \
  -d '{ "initial_prompt": "分析当下最热门的玄幻小说套路", "max_steps": 10 }'
```

**响应示例**：

```json
{
  "success": true,
  "message": "trend-react task started",
  "data": { "task_id": 5, "status": "running" }
}
```

---

### POST /projects/{id}/tasks/execute-auto-novel-workflow

**用途**：执行完整的"三阶段"自动工作流（Planner → Chapter Loop → Reviewer）。

**请求示例**：

```bash
curl -X POST http://localhost:8000/api/v1/projects/1/tasks/execute-auto-novel-workflow \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "auto",
    "initial_prompt": "一个都市悬疑故事，主角是退休刑警",
    "target_chapters": 20,
    "target_words_per_chapter": 2000
  }'
```

**响应示例**：

```json
{
  "success": true,
  "message": "auto workflow started",
  "data": { "task_id": 6, "status": "running", "phases": ["planner", "chapter_loop", "reviewer"] }
}
```

---

### GET /projects/{id}/tasks/{task_id}

**用途**：获取单个任务详情（status / current_step_index / started_at ...）。

**响应示例**：

```json
{
  "success": true,
  "message": "task detail",
  "data": {
    "id": 6,
    "task_type": "auto_novel_workflow",
    "status": "running",
    "current_step_index": 7,
    "started_at": "2026-06-03T10:15:23Z"
  }
}
```

---

### GET /projects/{id}/tasks/{task_id}/steps

**用途**：列出该任务所有步骤的执行结果。

**响应示例**：

```json
{
  "success": true,
  "message": "steps listed",
  "data": [
    { "id": 1, "name": "trend_exploration", "status": "completed" },
    { "id": 2, "name": "worldbook_build",   "status": "completed" },
    { "id": 3, "name": "chapter_loop",      "status": "running",  "progress": "5/20" }
  ]
}
```

---

### GET /projects/{id}/tasks/{task_id}/runtime

**用途**：读取任务运行时状态（Redis 缓存）。包含当前阶段、当前 chapter 等。

**响应示例**：

```json
{
  "success": true,
  "message": "runtime state",
  "data": {
    "task_id": 6,
    "current_phase": "chapter_loop",
    "current_chapter_no": 5,
    "started_at": "2026-06-03T10:15:23Z"
  }
}
```

---

### POST /projects/{id}/tasks/{task_id}/runtime

**用途**：手动写任务运行时状态（调试用）。

**请求示例**：

```bash
curl -X POST http://localhost:8000/api/v1/projects/1/tasks/6/runtime \
  -H "Content-Type: application/json" \
  -d '{ "current_phase": "reviewer", "current_chapter_no": 20 }'
```

---

### POST /projects/{id}/tasks/{task_id}/control

**用途**：向正在运行的任务发送控制信号（如 pause / throttle）。

**请求示例**：

```bash
curl -X POST http://localhost:8000/api/v1/projects/1/tasks/6/control \
  -H "Content-Type: application/json" \
  -d '{ "action": "pause" }'
```

**响应示例**：

```json
{ "success": true, "message": "control signal sent", "data": { "action": "pause", "applied": true } }
```

---

### GET /projects/{id}/tasks/{task_id}/step-runtime

**用途**：获取步骤级运行时状态。

**响应示例**：

```json
{
  "success": true,
  "message": "step runtime",
  "data": { "step_id": 3, "name": "chapter_loop", "status": "running", "progress": "5/20" }
}
```

---

### GET /projects/{id}/tasks/{task_id}/logs

**用途**：获取任务日志（支持 `?since=...&limit=200`）。

**请求示例**：

```bash
curl "http://localhost:8000/api/v1/projects/1/tasks/6/logs?limit=50"
```

**响应示例**：

```json
{
  "success": true,
  "message": "logs fetched",
  "data": [
    { "ts": "2026-06-03T10:15:23Z", "level": "INFO", "msg": "planner started" },
    { "ts": "2026-06-03T10:18:01Z", "level": "INFO", "msg": "chapter 5 completed, 2034 words" }
  ]
}
```

---

## 六、模型与并发端点

### GET /projects/{id}/tasks/models

**用途**：列出当前可用的 LLM 模型（primary + fallback 链 + provider）。

**响应示例**：

```json
{
  "success": true,
  "message": "available models",
  "data": {
    "primary": "minimaxai/minimax-m2.7",
    "fallback": ["minimaxai/minimax-m2.7", "meta/llama-3.1-70b-instruct"],
    "provider": "nvidia"
  }
}
```

---

### GET /projects/{id}/tasks/concurrency

**用途**：查询当前并发槽位（`{current, max, slots}`）。前端徽章 `运行中 {current}/{max}` 数据源。

**响应示例**：

```json
{
  "success": true,
  "message": "concurrency status",
  "data": { "current": 1, "max": 1, "slots": [6] }
}
```

> `slots` 是当前正在运行的任务 ID 列表。`current >= max` 时前端应禁用"启动创作"按钮。

---

## 七、错误码参考

| HTTP | 含义 | 常见场景 |
|------|------|----------|
| **200** | 成功 | 正常 GET / POST / DELETE 响应 |
| **201** | 已创建 | `POST /projects` 新建项目 |
| **202** | 已接受（异步处理中） | `POST /tasks/{id}/resume` |
| **400** | 请求错误 | `resume` 一个 `completed` 任务、参数缺失 |
| **404** | 资源不存在 | 项目 ID / 任务 ID 不存在 |
| **409** | 状态冲突 | 对 `cancelled` 任务再次 `cancel`（已统一为 200） |
| **422** | 验证失败 | Pydantic 模型字段类型错误 |
| **500** | 服务器内部错误 | DB 异常、未捕获的 Python 异常 |
| **502** | 上游错误 | LLM 上游返回 502 |
| **504** | 网关超时 | LLM 调用 `LLM_REQUEST_TIMEOUT_SECONDS` 内未响应 |

### 7.1 常见错误体

```json
{
  "success": false,
  "message": "task not found",
  "data": null,
  "meta": { "task_id": 999 }
}
```

```json
{
  "success": false,
  "message": "validation error: target_chapters must be between 1 and 100",
  "data": null,
  "meta": { "field": "target_chapters" }
}
```

### 7.2 取消 / 恢复的特殊语义

| 操作 | 状态 | 行为 |
|------|------|------|
| 取消 `running` 任务 | → `cancelling` | 200 |
| 取消 `cancelling` 任务 | → `cancelling`（幂等） | 200 |
| 取消 `cancelled` 任务 | → `cancelled`（幂等） | 200 |
| 取消 `completed` 任务 | 拒绝 | 400 |
| 恢复 `failed` 任务 | → `running` | 202 |
| 恢复 `cancelled` 任务 | → `running` | 202 |
| 恢复 `running` 任务 | 拒绝 | 400 |
| 恢复 `completed` 任务 | 拒绝 | 400 |

---

## 八、调用建议

- **轮询节奏**：任务运行中前端每 **3s** 拉一次 `GET /tasks/{id}`；用 `GET /tasks/{id}/runtime` 拿更细的状态。
- **并发控制**：提交前先调 `GET /tasks/concurrency`，避免超过 `max`。
- **错误兜底**：所有 5xx 应自动 retry 一次，间隔 ≥ 3s。
- **取消幂等**：前端可放心地"乐观"先置 `cancelling`，再发请求。

---

> **相关文档**：[`docs/ARCHITECTURE.md`](./ARCHITECTURE.md)（架构）、[`docs/OPERATIONS.md`](./OPERATIONS.md)（运维）
