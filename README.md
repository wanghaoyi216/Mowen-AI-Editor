# Mowen AI Editor · 墨文 AI 编辑器

**LangGraph 多智能体编排 · Plan-and-Execute · ReAct 反思循环 · Neo4j 故事图谱**

[![GitHub stars](https://img.shields.io/github/stars/wanghaoyi216/Mowen-AI-Editor?style=for-the-badge&logo=github&color=ffb86c)](https://github.com/wanghaoyi216/Mowen-AI-Editor/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/wanghaoyi216/Mowen-AI-Editor?style=for-the-badge&logo=github&color=8be9fd)](https://github.com/wanghaoyi216/Mowen-AI-Editor/network)
[![License](https://img.shields.io/badge/license-MIT-ff79c6?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-50fa7b?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org)
[![TypeScript](https://img.shields.io/badge/typescript-5.8-3178c6?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61dafb?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.4.8-1e3a8a?style=for-the-badge)](https://github.com/langchain-ai/langgraph)

---

## ✨ 特性

| 🧠 长上下文 | 🔄 断点续跑 | 📡 实时事件流 | 🎨 6 套主题 | 🕸️ 知识图谱 |
|:---:|:---:|:---:|:---:|:---:|
| 1M token | checkpoint 持久化 | AgentEventBus SSE | 水墨风自定义 | Neo4j 关系网 |

---

## 🎯 核心亮点

### 1. LangGraph StateGraph + 并行 SubAgent

章节生成采用 **LangGraph StateGraph** 编排多个 SubAgent 并行执行：

![LangGraph 架构](https://mermaid.ink/img/mermaid.ink?encodeUrl?基类=0&format=png&height=400&src=flowchart LR subgraph Plan A["📋 Plan Chapter"] end subgraph SubAgents B["👤 Character Design"] C["📖 Plot Design"] D["🌍 Worldbook Check"] end subgraph Generation E["✍️ Draft"] F["🔍 Consistency Review"] G["🔄 Revise (ReAct Loop)"] H["💾 Store Chapter"] end A --> B A --> C A --> D B --> E C --> E D --> E E --> F F --failed--> G G --> E F --passed--> H)

- **并行 SubAgent**：角色设计、剧情设计、世界观一致性同时跑
- **ReAct 反思循环**：Draft → Review → Revise → Draft 循环直到通过
- **LangGraph StateGraph**：[chapter_loop_service.py](backend/app/services/chapter_loop_service.py)

### 2. Plan-and-Execute 工作流注册表

注册式设计，新增工作流只需改一处配置，无需改前端/路由：

| ID | 名称 | 说明 |
|---|---|---|
| `wf-01` | 热点搜索 | Plan → Search → Store |
| `wf-02` | 世界观设计 | Plan → Design → Store |
| `wf-03` | 章节规划 | Plan → Strategize → Store |
| `wf-04` | 写作策略 | Plan → Decide → Store |
| `wf-05` | 章节生成 | Plan → Draft → Revise → Store |

注册表：[workflow_registry_service.py](backend/app/services/workflow_registry_service.py)

### 3. 任务 Checkpoint + 断点续跑

[task_persistence_service.py](backend/app/services/task_persistence_service.py)

- 每次 LLM 调用前写 checkpoint 到 MySQL
- 进程崩溃 / 容器重启 / LLM 限流 → 自动标记 `paused`
- `POST /projects/tasks/cleanup-orphans` 运维兜底清理
- `POST /projects/{id}/tasks/{tid}/resume` 断点续跑

### 4. 多模型自动降级

[openrouter_client.py](backend/app/integrations/openrouter_client.py)

- Primary + 多个 Fallback 模型按序尝试
- **首字节超时**（主 10s / fallback 20s）+ **整体超时**双保险
- `FirstByteTimeout` 不重试，直接切下一个模型
- 模型 hang 死时 **20s 内** 自动切换

### 5. AgentEventBus 实时事件流

[agent_event_bus.py](backend/app/services/agent_event_bus.py)

- `tool_call` / `tool_result` — 联网搜索 / Neo4j 查询
- `thinking` — Reasoning 模型思考过程
- `text_delta` — 流式 token 实时推送

### 6. Neo4j 故事图谱

角色、事件、地点、势力的多对多关系网络；章节生成时自动查询前文节点作为上下文（解决 LLM 失忆问题）；前端用 [react-force-graph](https://github.com/vasturiano/react-force-graph) 渲染。

---

## 🏗️ 技术架构

```
Frontend (React 19) ──SSE/REST──> Backend (FastAPI + LangGraph)
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
              Novel Orchestrator  Chapter Loop    Workflow Registry
              (3-Phase)         (SubAgent DAG)   (5 Pre-defined WFs)
                    │                │                │
                    └────────────────┼────────────────┘
                                     ▼
                        OpenRouter Client (Primary + Fallback)
                                     │
                    ┌────────────────┴────────────────┐
                    ▼                ▼                ▼
                 MySQL 8.4        Neo4j 5.24        Redis 7
               业务+checkpoint    故事图谱          限流+缓存
```

详细分层见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

---

## 🚀 快速开始

### 环境要求

| 依赖 | 说明 |
|---|---|
| Docker Desktop 4.x+ | WSL2 backend |
| NVIDIA API Key | [build.nvidia.com](https://build.nvidia.com) 注册，免费 40 次/分钟 |
| 8GB+ 内存 | Neo4j 占大头 |

### 启动步骤

```bash
# 克隆
git clone https://github.com/wanghaoyi216/Mowen-AI-Editor.git
cd Mowen-AI-Editor

# 配置
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入 NVIDIA_API_KEY

# 启动 4 个服务
docker compose up -d
```

### 服务地址

| 服务 | 地址 |
|---|---|
| 前端 | http://localhost:5173 |
| 后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |
| Neo4j Browser | http://localhost:7474 |

### 默认账号

```
账号: text
密码: 123456
```

---

## 🧩 项目结构

```
backend/
├── app/
│   ├── api/routes/
│   │   ├── auth.py           # JWT 认证
│   │   ├── projects.py       # 项目 CRUD
│   │   ├── workflows.py      # 工作流执行入口
│   │   ├── tasks.py          # 任务管理 + resume + cleanup
│   │   └── chapters.py       # 章节 CRUD
│   ├── services/
│   │   ├── workflow_registry_service.py   # 5 套工作流注册
│   │   ├── novel_orchestrator_service.py # 3-Phase 主编排
│   │   ├── chapter_loop_service.py        # SubAgent DAG + ReAct
│   │   ├── ai_workflow_graph_service.py   # Plan-and-Execute
│   │   ├── task_persistence_service.py    # checkpoint + orphan
│   │   ├── agent_event_bus.py             # SSE 事件流
│   │   └── openrouter_service.py          # 模型候选 + fallback
│   ├── integrations/
│   │   └── openrouter_client.py           # absolute deadline
│   └── core/
│       ├── config.py         # Pydantic Settings
│       └── resilience.py     # with_retries + no_retry
frontend/
├── src/
│   ├── components/           # 主题切换 / 项目卡片
│   ├── pages/               # Login / Project / Chapter / Graph
│   ├── stores/              # Zustand: theme / auth / task
│   └── api/                 # axios + SSE 订阅
docs/
├── ARCHITECTURE.md
├── DEPLOYMENT.md
├── OPERATIONS.md
└── API_CHEATSHEET.md
```

---

## 🔌 API 速览

<details>
<summary>点击展开 14 个核心端点</summary>

| Method | Path | 用途 |
|---|---|---|
| `POST` | `/api/v1/auth/login` | 登录拿 JWT |
| `POST` | `/api/v1/auth/register` | 注册 |
| `GET` | `/api/v1/projects` | 列项目 |
| `POST` | `/api/v1/projects` | 新建项目 |
| `GET` | `/api/v1/projects/{id}/workflows` | 列工作流 |
| `POST` | `/api/v1/projects/{id}/workflows/{wid}/execute` | 执行工作流 |
| `GET` | `/api/v1/projects/{id}/tasks` | 列任务 |
| `GET` | `/api/v1/projects/{id}/tasks/{tid}` | 任务详情 |
| `GET` | `/api/v1/projects/{id}/tasks/{tid}/steps` | 步骤状态 |
| `POST` | `/api/v1/projects/{id}/tasks/{tid}/resume` | 断点续跑 |
| `POST` | `/api/v1/projects/tasks/cleanup-orphans` | 清理孤儿任务 |

完整 OpenAPI：[docs/openapi.json](docs/openapi.json) · `/docs`

</details>

---

## 🛠️ 排障

| 症状 | 解决方案 |
|---|---|
| 任务卡 `running` | `POST /cleanup-orphans` → 再 `resume` |
| AI 60s 无响应 | 日志搜 `absolute deadline exceeded`，已自动切 fallback |
| LLM 401/403 | 检查 `.env` 的 `NVIDIA_API_KEY` 是否过期 |
| Neo4j 连不上 | `docker logs novel_ai_neo4j`，首次启动需 30s+ |

更多：[docs/OPERATIONS.md](docs/OPERATIONS.md)

---

## 🗺️ 路线图

- [x] v1.0 — MVP：项目管理 + 单工作流 + LLM 调用
- [x] v1.1 — 6 套水墨主题 + 颜色提取 + 自定义上传
- [x] v1.2 — 任务断点续跑 + 多模型降级 + 实时事件流
- [ ] v2.0 — 多人协作 + 评论批注
- [ ] v2.1 — 章节自动配图（SDXL）
- [ ] v3.0 — 多语言小说

---

## 🤝 贡献

```bash
git clone https://github.com/wanghaoyi216/Mowen-AI-Editor.git
git checkout -b feat/your-feature
git commit -m "feat: add your feature"
git push origin feat/your-feature
# 然后开 Pull Request
```

---

## 📜 许可证

MIT License · 仅供学习研究使用

---

_Built with LangGraph · NVIDIA integrate API · Neo4j_
