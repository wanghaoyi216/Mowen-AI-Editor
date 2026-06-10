# Novel AI Editor — 技术架构文档

> **版本**: v1.1  
> **更新日期**: 2026-06-03  
> **受众**: 新入职工程师 / 架构评审 / 跨团队协作

本文档面向首次接触项目的工程师，目标是在 30 分钟内讲清楚"项目是什么、代码长什么样、请求是怎么跑完一条主链路的"。

---

## 一、项目概述

Novel AI Editor 是一套 **AI 驱动的小说创作全链路自动化系统**。用户在前端给定一个题材、体量和初始 prompt，系统会按 **"规划 → 逐章创作 → 一致性审查"** 三阶段自动产出可读的长篇草稿。后端使用 Python 3.12 + FastAPI，编排 AI 工作流、聚合多种数据库（PostgreSQL / Neo4j / Redis），通过 OpenAI 兼容接口调用 NVIDIA 等 LLM 服务；前端使用 React 19 + Vite，提供"大屏指挥中心"风格的 8 阶段可视化面板。

整个项目采用 **Docker Compose 一键拉起**，5 个服务容器（postgres、redis、neo4j、backend、frontend）即可完成全栈运行。

---

## 二、系统分层

整个系统被刻意拆成 4 层，每层只依赖下一层，单层可独立替换 / 灰度发布。

```
┌──────────────────────────────────────────────────────────────┐
│  ① 前端层 (Frontend)                                          │
│  React 19 + Vite + TypeScript                                 │
│  ECharts / D3 / Lucide / React Context                       │
│  → 与用户交互、状态管理、可视化                                 │
└──────────────────────────┬───────────────────────────────────┘
                           │  HTTP/JSON  (Vite Proxy /api → :8000)
┌──────────────────────────▼───────────────────────────────────┐
│  ② API 层 (FastAPI, :8000, 前缀 /api/v1)                      │
│  路由模块: projects / tasks / chapters / confirmations /     │
│           openrouter / health                                  │
│  → 入参校验 (Pydantic)、OpenAPI 文档生成、统一响应包装         │
└──────────────────────────┬───────────────────────────────────┘
                           │  内部函数调用
┌──────────────────────────▼───────────────────────────────────┐
│  ③ 服务层 (Services)                                          │
│  - novel_orchestrator_service  编排器（3 阶段调度）            │
│  - chapter_task_service        章节循环执行                   │
│  - confirmation_engine          Human-in-the-Loop             │
│  - openrouter_service           AI 调用封装 (OpenAI 兼容)     │
│  - degradation_manager          降级 / 重试 / 退避             │
│  - cancellation_registry       取消注册表（线程安全）          │
│  - rate_limiter                滑动窗口限流 (Redis)           │
│  - task_runtime_service        任务运行时状态 (Redis 缓存)    │
│  → 业务规则、状态机、AI 调用、并发控制                          │
└──────────┬───────────────┬─────────────────┬─────────────────┘
           │               │                 │
┌──────────▼─────┐ ┌───────▼──────┐ ┌────────▼────────┐
│ ④-1 PostgreSQL │ │ ④-2 Neo4j    │ │ ④-3 Redis       │
│  业务数据        │ │  实体关系图   │ │ 缓存 + 限流 + 取消 │
│  JSONB + 全文    │ │  Cypher      │ │ TTL 1h ~ 24h    │
└────────────────┘ └──────────────┘ └─────────────────┘
```

### 2.1 各层职责一句话

| 层 | 选型 | 职责边界 |
|----|------|----------|
| 前端 | React 19 + Vite | UI 渲染、本地状态、轮询任务进度 |
| API | FastAPI | 路由、Pydantic 校验、Swagger 文档、依赖注入 |
| 服务 | Python asyncio | 编排、AI 调用、限流、重试、取消、上下文管理 |
| 数据 | PG + Neo4j + Redis | 业务持久化、知识图谱、缓存与限流计数 |

---

## 三、三阶段架构（核心流程图）

整个创作过程是单向流水线，每一阶段都会把产物落库，下一阶段从库中读取。

```
┌──────────────┐
│ 用户启动创作  │   POST /projects/{id}/tasks/execute-auto-novel-workflow
└──────┬───────┘
       ↓
┌──────────────────────────┐
│ Phase 1: Novel Planner   │  ← AI 生成大纲 / 世界观 / 实体关系
│  - 趋势探索 (Trend)       │     调用 trend_react executor
│  - 世界观构建 (World)     │     落库: worldbook_entries
│  - 实体抽取 (Entity)      │     落库 Neo4j: Character / Location / Event
│  - 章节规划 (Chapter Plan)│     落库: chapter_plan
└──────┬───────────────────┘
       ↓
┌──────────────────────────┐
│ Phase 2: Chapter Loop    │  ← 逐章调用 SubAgent
│  ┌────┐ ┌────┐ ┌────┐    │
│  │Ch.1│→│Ch.2│→│Ch.3│...│
│  │    │ │    │ │    │    │  每次循环:
│  │ ✓  │ │ ✓  │ │ ✓  │    │   1. 检查取消信号
│  └────┘ └────┘ └────┘    │   2. 构建上下文 (ContextManager)
│                          │   3. 写章节内容
│  边界处理:                 │   4. 持久化 + 检查点
│   - 取消点 (Task 4)       │   5. 失败重试 1 次 (Task 7)
│   - 自动重试 (Task 7)     │
│   - 检查点保存 (Task 5)   │
└──────┬───────────────────┘
       ↓
┌──────────────────────────┐
│ Phase 3: Novel Reviewer  │  ← 一致性审查
│  - 角色行为一致性         │     跑 controller_model (低温度)
│  - 时间线一致性           │     生成 consistency_reports
│  - 风格漂移检测           │     可由人类确认 (confirmation_points)
│  - 生成审阅报告           │
└──────────────────────────┘
       ↓
  任务状态: completed
```

### 3.1 阶段产物落点

| 阶段 | 写入 PostgreSQL 表 | 写入 Neo4j 节点/边 | 写入 Redis Key |
|------|--------------------|---------------------|------------------|
| Phase 1 Planner | `trend_explorations`, `worldbook_entries`, `chapter_plan` | `Character`, `Location`, `Event`, `HAS_CHARACTER` 等 | `context:{pid}:active` |
| Phase 2 Chapter Loop | `chapters`, `ai_task_steps`, `task_checkpoints` | 视子流程而定 | `task:{tid}:state`, 取消标志 |
| Phase 3 Reviewer | `consistency_reports`, `confirmation_points` | — | 短期缓存 |

---

## 四、核心数据模型 ER 图

项目共 12 张业务表 + 3 个 Neo4j 节点族，下面只列主链路上的 **6 张核心表** 的关系。

```
┌────────────────┐         ┌────────────────────┐
│   projects     │ 1     * │     chapters       │
│────────────────│─────────│────────────────────│
│ id  (PK)       │         │ id  (PK)           │
│ name           │         │ project_id (FK)    │
│ genre          │         │ task_id   (FK, ?)  │
│ summary        │         │ chapter_no         │
│ target_chapters│         │ title              │
│ target_words   │         │ status             │
│ created_at     │         │ word_count         │
└────────┬───────┘         │ content            │
         │ 1               │ created_at         │
         │                 └─────────┬──────────┘
         │ *                         │ 1
┌────────▼────────┐         ┌───────▼──────────────┐
│  characters     │         │      ai_tasks        │
│────────────────│         │──────────────────────│
│ id (PK)        │         │ id (PK)              │
│ project_id (FK)│         │ project_id (FK)      │
│ name           │         │ task_type            │
│ role           │         │ status               │
│ profile (JSONB)│         │ title                │
│ created_at     │         │ current_step_index   │
└────────────────┘         │ started_at           │
                            │ finished_at          │
                            └───────┬──────────────┘
                                    │ 1
                                    │
                            ┌───────▼──────────────┐
                            │  task_checkpoints    │
                            │──────────────────────│
                            │ id (PK)              │
                            │ task_id (FK, UQ)     │
                            │ current_phase        │
                            │ completed_chapters   │
                            │ last_chapter_no      │
                            │ accumulated_context  │
                            │ updated_at           │
                            └──────────────────────┘

┌─────────────────────────┐
│  confirmation_requests  │
│─────────────────────────│
│ id (PK)                 │
│ task_id (FK)            │
│ workflow_id             │
│ point_id                │
│ status (pending/...)    │
│ payload (JSONB)         │
│ created_at              │
└─────────────────────────┘
```

### 4.1 字段语义要点

| 表 | 关键字段 | 含义 |
|----|----------|------|
| `projects` | `summary` | 用户的初始一句话 prompt，是 Phase 1 的种子 |
| `chapters` | `status` | 枚举：`pending` / `writing` / `completed` / `failed` / `cancelled` |
| `ai_tasks` | `task_type` | 枚举：`react` / `trend_react` / `auto_novel_workflow` |
| `task_checkpoints` | `accumulated_context` | 已生成章节摘要 + 角色卡 + 世界观压缩串 |
| `confirmation_requests` | `status` | `pending` / `approved` / `rejected` / `skipped` |

---

## 五、关键技术决策（Trade-off 说明）

### 5.1 为什么用 FastAPI？

- **异步原生**：`async def` + `asyncio`，单进程可并发处理 LLM 长调用而不阻塞。
- **自动 OpenAPI**：访问 `/api/v1/docs` 即可拿到 Swagger UI，前端可直接对照开发。
- **Pydantic 强类型**：请求/响应模型即文档，减少字段拼写错误。
- **依赖注入**：`Depends(get_db_session)` 把 session 生命周期交给框架。

> 取舍：相比 Flask，FastAPI 的生态略小、长任务需要手动后台线程（`threading.Thread`），但对 AI 应用场景的契合度更高。

### 5.2 为什么用 PostgreSQL？

- **关系型 + JSONB**：既能存规范化表（chapters），又能存半结构化数据（世界观的 schema 经常变）。
- **pgvector 扩展潜力**：未来要做"和已有章节相似度检索"时无需换库。
- **事务保证**：任务状态变更 + 章节落库可放在同一事务里。

> 取舍：相比 MongoDB，PG 不擅长纯文档型场景，但本系统以关系为主。

### 5.3 为什么用 Neo4j？

- **实体关系查询优于关系数据库 JOIN**：Cypher 一行就能查到"主角认识的所有人最近三章做了什么事"。
- **可视化友好**：前端 Tab 5 直接渲染 graph 视图，无需手写 JOIN 转换。
- **面向 AI 检索**：知识图谱是 RAG 时代的事实库。

> 取舍：相比纯 SQL，Neo4j 增加一个运维组件、容量有限。仅用于实体 / 关系，不存章节正文。

### 5.4 为什么用 LangGraph（语义化状态机）？

> 当前实现以自定义 orchestrator 为主，但保留了 LangGraph 的引入空间。

- **可视化**：状态机可导出为 mermaid 图，便于审阅。
- **检查点**：LangGraph 原生支持断点恢复，与我们的 `task_checkpoints` 表语义契合。
- **工具调用**：tool 节点封装 LLM 调用，方便换模型 / 降级。

### 5.5 为什么用 Pydantic Settings？

- **类型安全**：`rate_limit_calls_per_minute: int = 40`，环境变量读错时立刻报错。
- **默认值兜底**：开发环境无需 `.env` 也能跑。
- **嵌套模型**：未来想给 AI 模型参数分组（creator / controller / embedding），可直接用子 Settings。

### 5.6 双 AI 温度策略

| 模型 | 温度 | 适用场景 | 代表模型 |
|------|------|----------|----------|
| 严格 AI (controller) | 0.3 - 0.5 | 一致性审查、角色设定、JSON 抽取 | `meta/llama-3.1-70b-instruct` |
| 开放 AI (creator) | 0.8 - 1.2 | 章节创作、情节生成、世界观 | 默认 `minimaxai/minimax-m2.7` |

---

## 六、章节循环细节（含取消 / 重试 / 检查点）

下面是单章执行 + 章节循环的伪代码，重点展示 **取消点 / 重试 / 检查点** 三处落点。

```python
async def execute_chapter_loop(project_id: int, task_id: int):
    checkpoint = load_checkpoint(task_id)
    start_chapter = (checkpoint.last_chapter_no or 0) + 1
    accumulated = checkpoint.accumulated_context or ""

    for chapter_no in range(start_chapter, target_chapters + 1):
        # === 取消点 (Task 4) ===
        if cancellation_registry.is_cancelled(task_id):
            log.info(f"[cancellation] cancel signal detected at chapter {chapter_no}")
            mark_chapter_status(chapter_no, "cancelled")
            break

        context = context_manager.build_context(accumulated, project_id)
        try:
            # === 重试包装 (Task 7) ===
            for attempt in (1, 2):
                try:
                    content = await openrouter_service.chat(
                        messages=build_prompt(chapter_no, context),
                    )
                    break
                except (httpx.ReadTimeout, httpx.ConnectError, httpx.HTTPStatusError) as e:
                    if 500 <= getattr(e, "status_code", 0) < 600 and attempt == 1:
                        degradation_mgr.record_failure(model=primary_model)
                        log.warning(f"chapter {chapter_no} failed, retrying once...")
                        await asyncio.sleep(2)
                        continue
                    raise

            save_chapter(chapter_no, content)
            accumulated = context_manager.append(accumulated, content)

            # === 检查点保存 (Task 5) ===
            save_checkpoint(task_id, {
                "current_phase": "chapter_loop",
                "completed_chapters": chapter_no,
                "last_chapter_no": chapter_no,
                "accumulated_context": accumulated,
            })

        except Exception as e:
            mark_chapter_status(chapter_no, "failed")
            mark_task_status(task_id, "failed")
            raise
    else:
        mark_task_status(task_id, "completed")
```

### 6.1 三处关键点对照

| 时机 | 行为 | 数据落点 |
|------|------|----------|
| 每章 LLM 调用前 | `cancellation_registry.is_cancelled(task_id)` 检查 | — |
| LLM 5xx / 超时 | 退避 2s 后重试 1 次，仍失败才 `failed` | `degradation_mgr` |
| 每章成功后 | 写 `task_checkpoints`（用于 resume） | PostgreSQL |

---

## 七、运维能力（Operations Features）

| 能力 | 入口 | 说明 |
|------|------|------|
| **取消注册表** | `POST /projects/{id}/tasks/{tid}/cancel` | 设置线程安全的取消标志，章节循环在下一章前检测到立即 break |
| **检查点恢复** | `POST /projects/{id}/tasks/{tid}/resume` | 任务 `failed` / `cancelled` 后从 `last_chapter_no + 1` 继续 |
| **健康检查** | `GET /api/v1/health/*` | 6 个端点分别检测：总状态、各依赖、Prometheus 指标、限流、任务统计、DB 连接池 |
| **滑动窗口限流** | `rate_limiter` (Redis) | 默认 40 calls / 分钟，触发时 `LLMService` 自动 fallback 到下一模型 |
| **降级管理** | `degradation_manager` | 记录每模型失败次数，触发熔断 / 切换 fallback |
| **任务运行时状态** | `GET /projects/{id}/tasks/{tid}/runtime` | Redis 缓存当前阶段、当前步骤、当前 chapter |
| **LLM 调用统计** | `GET /projects/{id}/tasks/llm-stats` | 返回 `total_calls / total_tokens / avg_latency_ms / by_model` |

### 7.1 取消信号的传播路径

```
前端点击"取消"
  → POST /tasks/{tid}/cancel
  → cancellation_registry.cancel(tid)  # 内存标志
  → 后台线程在每章 LLM 调用前 is_cancelled(tid) 返回 True
  → 章节状态置为 cancelled，break 循环
  → task.status 写回 cancelled
  → 前端轮询 GET /tasks/{tid} 看到 cancelled
```

> 详见 `docs/OPERATIONS.md` 的故障树章节。

---

## 八、扩展点与未完成项

| 模块 | 当前状态 | 下一步 |
|------|----------|--------|
| 取消粒度 | 章节边界 | 行级 / 工具调用级 |
| 检查点粒度 | 每章一次 | 每 200 token 一次 |
| 限流 | 滑动窗口 | 加入 burst 突发配额 |
| 上下文压缩 | 摘要层 | 引入 embedding 检索式上下文 |
| Reviewer | 占位 | 接入 Re-Act + 多 reviewer 投票 |

---

> **相关文档**：[`docs/OPERATIONS.md`](./OPERATIONS.md)（运维）、[`docs/API_CHEATSHEET.md`](./API_CHEATSHEET.md)（API 速查）、[`docs/PRD.md`](./PRD.md)（产品需求）
