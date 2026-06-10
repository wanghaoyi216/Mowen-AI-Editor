# Novel AI Editor - AI 任务优化提示词

> **用途**: 提供给 AI Agent 的完整任务上下文和优化提示词  
> **版本**: v1.0  
> **更新日期**: 2026-06-01

---

## 一、项目上下文

### 1.1 项目简介

你正在为一个 **全链路自动化 AI 小说创作系统** 进行开发和优化。该系统通过 AI 驱动的方式实现从关键词生成到章节导出的完整小说创作流程。

### 1.2 项目位置

```
d:\Study\novel_ai_editer\
├── backend/              # FastAPI 后端（Python 3.12）
├── frontend/             # React + Vite 前端（TypeScript）
├── docker-compose.yml    # Docker Compose 编排
└── docs/                 # 项目文档
    ├── PRD.md            # 产品需求文档
    └── ARCHITECTURE.md   # 技术架构文档
```

### 1.3 当前状态

| 模块 | 状态 | 备注 |
|------|------|------|
| 前端大屏指挥中心 | ✅ 完成 | 6 个可视化 Tab，项目创建/选择/启动全流程 |
| 后端基础 API | ✅ 完成 | 项目管理、任务管理、章节管理等 |
| AI 服务集成 | ✅ 完成 | OpenRouter 客户端、工作流编排、上下文管理器 |
| Docker 部署 | ✅ 完成 | 5 个容器（frontend, backend, postgres, neo4j, redis） |
| 工作流链式执行器 | ⏳ 进行中 | 需要完整实现 |
| 确认引擎 | ⏳ 进行中 | 需要完整实现 |

### 1.4 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 19, TypeScript, Vite 6, ECharts 5, D3.js 7, Lucide |
| 后端 | FastAPI, SQLAlchemy 2, LangGraph, asyncpg, Redis |
| 数据库 | PostgreSQL (pgvector), Neo4j, Redis |
| AI | OpenRouter API (多模型支持) |
| 部署 | Docker Compose |

---

## 二、核心任务清单

### 任务 1：修复前端 Mock 数据（已完成）

**问题**：右侧业务流程面板和所有可视化 Tab 使用了硬编码的 Mock 数据，没有对接真实 API。

**解决方案**：
- `CommandCenter/index.tsx`：重写 `handleCreateProject` 和 `handleStartCreation` 调用真实 API
- `TopControlBar.tsx`：集成 `ProjectContext`，从 API 加载项目列表
- 所有 `VisualizationTab*.tsx`：移除 Mock 数据，改为 API 驱动 + 空状态占位

### 任务 2：新建项目前端不显示（已完成）

**问题**：`handleCreateProject` 仅 `console.log`，未调用创建接口。

**解决方案**：调用 `apiCreateProject()` 创建真实项目，创建成功后刷新项目列表并选中新项目。

### 任务 3：AI 上下文管理模块（已完成）

**问题**：AI 上下文长度有限，需要在有限 Token 预算内帮助 AI 快速拾起记忆。

**解决方案**：创建 `context_manager.py`，实现分层记忆（持久层 3000 tokens + 摘要层 5000 tokens + 活跃层 10000 tokens），Redis 缓存，Token 预算控制。

### 任务 4：工作流链式执行器（待开发）

**文件**：`backend/app/services/workflow_chain_executor.py`

**需求**：
- 实现 wf-01→02→03→04 自动链式触发
- 支持依赖关系检查（如世界观构建完成后再触发剧情规划）
- 支持阶段状态更新
- 集成确认引擎，在确认模式下暂停等待用户批准

### 任务 5：确认引擎（待开发）

**文件**：`backend/app/services/confirmation_engine.py`

**需求**：
- 实现 Human-in-the-Loop 阶段确认逻辑
- 支持确认点创建、批准、跳过
- 支持运行模式切换（自动 ↔ 确认）
- 集成到工作流执行器中

---

## 三、AI 优化提示词

### 3.1 通用开发提示词

```
你是一个资深的 AI 应用开发工程师，熟悉以下技术栈：
- Python (FastAPI, SQLAlchemy, LangGraph, asyncpg)
- React (TypeScript, Vite, ECharts, D3.js)
- PostgreSQL (pgvector), Neo4j, Redis
- Docker Compose

请根据以下要求完成任务：
1. 阅读相关文件的现有代码，理解其设计意图和代码风格
2. 保持与现有代码一致的编码风格和架构模式
3. 优先使用现有的 Schema、模型和服务函数
4. 添加中文注释说明关键逻辑
5. 完成后验证代码可以正常编译/运行
```

### 3.2 后端开发提示词

```
你是 Novel AI Editor 后端开发专家。

## 项目背景
- 框架：FastAPI + SQLAlchemy + LangGraph
- 数据库：PostgreSQL (pgvector) + Neo4j + Redis
- AI 服务：OpenRouter API（支持多模型）

## 开发约定
- 路由文件位于 `backend/app/api/routes/`
- 服务文件位于 `backend/app/services/`
- Schema 定义在 `backend/app/schemas/`
- 数据库模型在 `backend/app/db/models.py`
- 所有 API 响应使用 `ApiResponse[T]` 泛型格式
- 数据库操作使用 `Depends(get_db_session)` 注入会话
- 异步操作使用 `async/await` 模式

## 关键配置
- 数据库 URL: `postgresql+asyncpg://novel:novel_password@postgres:5432/novel_db`
- Redis URL: `redis://:novel_redis_password@redis:6379/0`
- OpenRouter Base URL: `https://openrouter.ai/api/v1`
- 双 AI 温度策略：严格 AI (0.3-0.5), 开放 AI (0.8-1.2)

## AI 上下文管理
- 最大上下文: 32,000 tokens
- 分层记忆：持久层 3000 + 摘要层 5000 + 活跃层 10000
- Redis 缓存 TTL: 1h (上下文), 24h (摘要/Token 统计)
- 文件：`backend/app/services/context_manager.py`
```

### 3.3 前端开发提示词

```
你是 Novel AI Editor 前端开发专家。

## 项目背景
- 框架：React 19 + TypeScript + Vite 6
- 可视化：Apache ECharts 5 + D3.js 7
- 图标：Lucide React
- 唯一界面：大屏指挥中心 (CommandCenter)

## 开发约定
- 组件位于 `frontend/src/components/CommandCenter/`
- API 请求封装在 `frontend/src/lib/api.ts`
- 类型定义在 `frontend/src/types.ts`
- 状态管理使用 React Context (`ProjectContext`)
- 样式使用 `CommandCenter.css` + `styles.ts` 设计 Token
- Vite Proxy 代理 `/api` → `http://backend:8000`

## 核心交互流程
1. 用户选择/创建项目 → 更新 `selectedProjectId`
2. 点击「启动创作」→ 弹出模态框 → 调用 AI 工作流 API
3. 工作流运行中 → 每 3s 轮询任务状态 → 更新左侧流程面板
4. 可视化 Tab → 各 Tab 独立调用对应 API → 渲染图表
5. 确认模式 → 右侧面板显示确认点 → 用户批准/跳过

## 设计原则
- 不使用 Mock 数据，所有数据来自真实 API
- API 无数据时显示友好空状态提示
- 深色主题，高级大气，大屏展示
- 模态框交互（弹出 → 填写 → 确认 → 收起）
```

### 3.4 数据库开发提示词

```
你是 Novel AI Editor 数据库开发专家。

## 数据库类型
- PostgreSQL (pgvector/pg16): 关系型数据 + 向量存储
- Neo4j (5-community): 实体关系图
- Redis (7-alpine): 缓存 + 会话状态

## Alembic 迁移约定
- 迁移文件位于 `backend/migrations/versions/`
- 版本链：`001_initial` → `002_add_confirmation_and_diversity` → ...
- 新迁移必须指定正确的 `down_revision` 指向已存在的上游版本
- 表名使用复数形式（如 `novel_projects`, `ai_tasks`）
- 外键引用必须使用正确的表名

## 核心表结构
- `novel_projects`: 小说项目
- `ai_tasks`: AI 任务（含工作流状态）
- `ai_task_steps`: 任务步骤
- `chapters`: 章节
- `characters`: 角色
- `content_embeddings`: 内容嵌入向量 (pgvector)
- `confirmation_points`: 确认点
- `worldbook_entries`: 世界观条目
- `trend_explorations`: 趋势探索

## Docker 数据库连接
- PostgreSQL: `postgresql+asyncpg://novel:novel_password@postgres:5432/novel_db`
- Redis: `redis://:novel_redis_password@redis:6379/0`
- Neo4j: `bolt://neo4j:7687`
```

### 3.5 AI 模型调用提示词

```
你是 Novel AI Editor 的 AI 模型调度器。

## NVIDIA NIM 配置
- Base URL: `https://integrate.api.nvidia.com/v1`
- API Key: 通过环境变量 `NVIDIA_API_KEY` 配置（`nvapi-` 开头）

## 双 AI 策略

### 严格 AI（温度 0.3-0.5）
- 用途：逻辑推理、一致性检查、角色设定、剧情规划
- 推荐模型：`anthropic/claude-3.5-sonnet`, `openai/gpt-4o`
- 特点：输出稳定、逻辑严密、适合结构性任务

### 开放 AI（温度 0.8-1.2）
- 用途：创意写作、情节生成、世界观构建、关键词挖掘
- 推荐模型：`google/gemini-2.0-flash-exp:free`, `meta-llama/llama-3.1-405b-instruct`
- 特点：输出多样、创意丰富、适合创造性任务

## 上下文管理
- 使用 `context_manager.py` 构建分层记忆上下文
- 总 Token 预算不超过 32,000
- 优先携带持久层（项目设定 + 世界观 + 角色）
- 活跃层携带最近 3 章的完整内容
- 摘要层携带最多 30 章的压缩摘要

## 多样性保障
- 使用 `ai_diversity_engine.py` 进行反重复检测
- 生成新内容前，计算与已有内容的余弦相似度
- 相似度超过阈值时，调整提示词引导 AI 创作不同方向
```

---

## 四、常见错误排查

### 4.1 前端相关

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| `Failed to resolve import "echarts-for-react"` | 依赖未声明 | 在 `package.json` 中添加 `echarts` 和 `echarts-for-react` |
| `No matching export for import "App"` | 导入方式不匹配 | 默认导出用 `import App`，具名导出用 `import { App }` |
| 前端 404 / 无法连接后端 | Vite Proxy 未匹配路径 | 确保 API 请求路径以 `/api` 开头 |
| 新建项目不显示 | `handleCreateProject` 未调用 API | 调用 `apiCreateProject()` 后刷新列表 |

### 4.2 后端相关

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| `ModuleNotFoundError: No module named 'asyncpg'` | 依赖未安装 | 在 `requirements.txt` 添加 `asyncpg` 并重新构建 |
| `KeyError: '001'` (Alembic) | 迁移版本链断裂 | 修正 `down_revision` 指向已存在的上游版本 |
| `relation "projects" does not exist` | 表名错误 | 使用正确的表名 `novel_projects` |
| `Generic[T]` 语法错误 | 未继承 `Generic` | `class ApiResponse(BaseModel, Generic[T])` |

### 4.3 Docker 相关

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| `403 Forbidden` (镜像拉取) | Docker 镜像源被禁 | 等待恢复或切换镜像源 |
| 容器启动后立即退出 | 应用启动报错 | `docker logs <container>` 查看错误 |
| 前端代码修改不生效 | 容器使用构建时代码 | 本地 src 已挂载，`docker restart` 容器即可 |

---

## 五、验证清单

### 5.1 前端验证

- [ ] 访问 `http://localhost:5173` 正常加载大屏界面
- [ ] 点击「新建」可以创建项目并显示在项目选择器中
- [ ] 点击「启动创作」可以弹出模态框并提交任务
- [ ] 左侧流程面板状态随任务进度更新
- [ ] 所有可视化 Tab 在无数据时显示空状态提示
- [ ] 底部日志面板可以展开/收起
- [ ] AI 文件查看器可以弹出并显示文件列表

### 5.2 后端验证

- [ ] 访问 `http://localhost:8000/health` 返回 `{"status":"ok"}`
- [ ] 访问 `http://localhost:8000/api/v1/docs` 可以查看中文接口文档
- [ ] `GET /api/v1/projects` 返回项目列表
- [ ] `POST /api/v1/projects` 可以创建新项目
- [ ] `POST /api/v1/projects/{id}/tasks/execute-auto-novel-workflow` 可以启动工作流
- [ ] 所有 5 个容器状态为 `healthy/running`

### 5.3 AI 连通性验证

- [ ] `.env` 中配置了有效的 `NVIDIA_API_KEY`（`nvapi-` 开头）
- [ ] 运行 `docker exec novel-ai-editor-backend python /app/scripts/test_ai_connectivity.py` 全部通过
- [ ] AI 模型列表可以正常获取
- [ ] 聊天补全请求可以收到响应

---

## 六、扩展任务提示词

### 6.1 添加新的可视化 Tab

```
请在 `frontend/src/components/CommandCenter/` 下创建新的可视化 Tab 组件。

要求：
1. 文件命名为 `VisualizationTab{N}{Name}.tsx`
2. 使用 `ReactECharts` 或 `d3` 进行图表渲染
3. 从 `api.ts` 调用对应 API 获取数据
4. 无数据时显示友好的空状态提示
5. 在 `MainVisualizationPanel.tsx` 中添加对应的 Tab 项和渲染逻辑
6. 使用 `colors` 设计 Token 保持视觉一致性
```

### 6.2 添加新的 API 端点

```
请在 `backend/app/api/routes/` 下添加新的 API 路由文件。

要求：
1. 使用 FastAPI 的 `APIRouter`
2. 所有响应使用 `ApiResponse[T]` 泛型格式
3. 在 `router.py` 中注册路由
4. 在 `main.py` 的 OpenAPI tags 中添加中文标签描述
5. 数据库操作使用 `Depends(get_db_session)`
6. 异常处理使用 `HTTPException`
```

### 6.3 添加新的数据库迁移

```
请创建新的 Alembic 迁移文件。

要求：
1. 文件位于 `backend/migrations/versions/`
2. 使用 `alembic revision --autogenerate -m "描述"` 生成
3. 确保 `down_revision` 指向最新的上游版本
4. 表名使用复数形式
5. 外键引用使用正确的表名
6. 向量字段使用 `pgvector` 的 `VECTOR` 类型
```

---

## 七、快速启动指南

### 7.1 环境准备

```bash
# 1. 配置环境变量
cd backend
cp .env.example .env
# 编辑 .env，填入你的 NVIDIA_API_KEY（nvapi- 开头）

# 2. 启动所有服务
cd ..
docker compose up -d

# 3. 验证服务状态
docker compose ps

# 4. 检查后端日志
docker logs novel-ai-editor-backend --tail 30

# 5. 检查前端日志
docker logs novel-ai-editor-frontend --tail 10
```

### 7.2 访问地址

| 服务 | URL | 说明 |
|------|-----|------|
| 前端大屏 | http://localhost:5173 | 主要操作界面 |
| 后端 API 文档 | http://localhost:8000/api/v1/docs | Swagger UI |
| 健康检查 | http://localhost:8000/health | 返回 `{"status":"ok"}` |
| PostgreSQL | localhost:5433 | 数据库 |
| Neo4j | localhost:7688 | 图数据库 |
| Redis | localhost:6380 | 缓存 |

### 7.3 测试 AI 连通性

```bash
docker exec novel-ai-editor-backend python /app/scripts/test_ai_connectivity.py
```

---

## 八、项目文件索引

### 8.1 关键文件

| 文件 | 路径 | 用途 |
|------|------|------|
| 前端主组件 | `frontend/src/components/CommandCenter/index.tsx` | 状态管理、API 调用 |
| 前端 API 封装 | `frontend/src/lib/api.ts` | 所有 API 请求函数 |
| 后端路由注册 | `backend/app/api/router.py` | API 路由注册 |
| 后端主入口 | `backend/app/main.py` | FastAPI 应用配置 |
| 后端配置 | `backend/app/core/config.py` | 环境变量加载 |
| AI 上下文管理 | `backend/app/services/context_manager.py` | 分层记忆构建 |
| 工作流编排 | `backend/app/services/workflow_orchestration_service.py` | AI 工作流执行 |
| OpenRouter 客户端 | `backend/app/integrations/openrouter_client.py` | AI 模型调用 |
| Docker 编排 | `docker-compose.yml` | 多服务容器配置 |

### 8.2 文档索引

| 文档 | 路径 | 用途 |
|------|------|------|
| 产品需求文档 | `docs/PRD.md` | 功能需求、用户画像、非功能需求 |
| 技术架构文档 | `docs/ARCHITECTURE.md` | 系统架构、目录结构、核心服务详解 |
| AI 任务优化提示词 | `docs/AI_PROMPTS.md` | 本文档，AI Agent 任务上下文 |
