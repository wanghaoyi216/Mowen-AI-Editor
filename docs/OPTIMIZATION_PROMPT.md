# Novel AI Editor 全面优化提示词

> 直接复制以下内容发送给其他 AI 继续执行

---

你是 Novel AI Editor（AI 驱动的小说创作全链路自动化系统）的高级全栈工程师。

## 项目背景

### 系统架构
- **部署**：Docker Compose（`docker-compose.yml` 位于项目根目录 `d:\Study\novel_ai_editer\`）
- **前端**：React 18 + TypeScript + Vite，端口 5173
- **后端**：Python 3.11 + FastAPI，端口 8000
- **数据库**：PostgreSQL 15（结构化数据）+ Neo4j 5（实体关系图）+ Redis 7（缓存）
- **AI 服务**：NVIDIA API（兼容 OpenAI 格式，`https://integrate.api.nvidia.com/v1`）

### 关键目录
```
d:\Study\novel_ai_editer\
├── backend/
│   ├── app/
│   │   ├── models.py              # SQLAlchemy 数据模型
│   │   ├── services/
│   │   │   ├── workflow_orchestration_service.py  # 工作流编排（7步流程）
│   │   │   ├── openrouter_service.py              # AI 调用服务（NVIDIA API）
│   │   │   ├── react_executor_service.py          # ReAct 执行器
│   │   │   ├── chapter_ai_service.py              # 章节 AI 生成
│   │   │   └── export_service.py                  # 导出服务
│   │   ├── api/routes/
│   │   │   ├── tasks.py           # 任务 API（异步后台执行）
│   │   │   ├── chapters.py        # 章节 API
│   │   │   └── exports.py         # 导出 API
│   │   ├── graph/client.py        # Neo4j 客户端
│   │   └── core/config.py         # Pydantic Settings 配置
├── frontend/
│   ├── src/
│   │   ├── components/CommandCenter/
│   │   │   ├── index.tsx          # 主控制面板
│   │   │   ├── VisualizationTab1-6.tsx  # 可视化 Tab1-6
│   │   │   ├── RightConfirmationPanel.tsx # 右侧确认面板
│   │   │   ├── BottomLogStream.tsx       # 底部日志流
│   │   │   ├── LeftFlowPanel.tsx         # 左侧流程面板
│   │   │   ├── GraphTypeSelector.tsx     # 图表类型选择器
│   │   │   ├── ModalStartCreation.tsx    # 启动创作弹窗
│   │   │   └── CommandCenter.css         # 样式（已做响应式适配）
│   │   ├── lib/api.ts             # API 调用封装
│   │   └── types.ts               # TypeScript 类型定义
├── docker-compose.yml
└── backend/.env                   # 环境变量
```

### 当前已完成状态
1. ✅ 数据库清理脚本（清空测试数据）
2. ✅ 前端响应式布局（窄屏三栏堆叠）
3. ✅ 可视化图表下拉选择框（Tab5 支持切换图表类型）
4. ✅ 后端异步工作流（后台线程执行，前端可轮询状态）
5. ✅ NVIDIA API 集成（替换 OpenRouter）
6. ✅ Markdown 渲染（章节内容使用 react-markdown）
7. ✅ 导出功能（单章 .md 和全项目 .zip）

### 当前 Docker 状态
所有容器正在运行：
- `novel-ai-editor-backend`（端口 8000）
- `novel-ai-editor-frontend`（端口 5173）
- `novel-ai-editor-postgres`（端口 5433）
- `novel-ai-editor-neo4j`（端口 7475, 7688）
- `novel-ai-editor-redis`（端口 6381）

## 核心业务需求

### 需求 1：AI 全自动创作模式（当前最高优先级）

**问题**：当前需要用户填写任务表单（主题、查询文本、风格提示等），效率低。

**要求**：
1. 用户只需点击"启动创作"，AI 自动完成全流程：
   - AI 自主搜索热门题材（Tavily API）
   - AI 分析当前市场趋势（哪些风格读者更喜欢）
   - AI 自行确定小说主题、风格、篇幅
   - AI 生成完整故事脉络（主线、重要节点、略写）
   - AI 拆分任务模块（章节规划）
   - SubAgent 并行填充章节内容
   - AI 自我检查（字数达标、内容扣题、一致性）
   - 达到阈值（如 80 分）后自动提交

2. 简化流程：
   - 移除 ModalStartCreation 中的表单
   - 改为只需输入"一句话主题"（可选）
   - 留空则 AI 完全自主决定

**修改文件**：
- `frontend/src/components/CommandCenter/ModalStartCreation.tsx` — 简化表单
- `backend/app/api/routes/tasks.py` — 支持无参数创建任务
- `backend/app/services/workflow_orchestration_service.py` — AI 自主决策逻辑

### 需求 2：动态 ReAct 模式可视化

**问题**：前端无法实时看到 AI 每一步的执行状态。

**要求**：
1. 每个 AI 调用都显示执行状态，例如：
   ```
   《XXX》小说：
   ├─ AI 正在思考确定小说主题... ✓
   ├─ AI 正在调用网络搜索工具确定小说脉络... ✓
   │   └─ Tavily 搜索工具已调用（查询 3 次）
   ├─ AI 正在构思人物和情节... ✓
   ├─ AI 正在调用图数据库存入人物关系数据... ✓
   │   └─ Neo4j 批量导入工具已调用（12 个节点，18 条边）
   ├─ AI 正在书写小说主题脉络... ✓
   ├─ AI 唤起了三个 SubAgent 分头填充章节内容：
   │   ├─ SubAgent1 正在书写第一章节的内容... ✓
   │   ├─ SubAgent2 正在书写第二章节的内容... ⏳
   │   └─ SubAgent3 正在书写第三章节的内容... ⏳
   ├─ AI 正在检查一致性... ✓
   └─ AI 正在修订章节... ⏳
   ```

2. 技术实现（二选一）：
   - **方案 A**：WebSocket 实时推送（推荐）
   - **方案 B**：SSE (Server-Sent Events)
   - **方案 C**：增强轮询（当前使用，优化为 1 秒间隔 + 增量更新）

**修改文件**：
- `backend/app/services/workflow_orchestration_service.py` — 每步记录详细日志到 task_logs 表
- `backend/app/models.py` — 添加 TaskLog 模型（如果不存在）
- `backend/app/api/routes/tasks.py` — 新增 `/tasks/{id}/logs` 端点
- `frontend/src/lib/api.ts` — 添加 fetchTaskLogs API
- `frontend/src/components/CommandCenter/BottomLogStream.tsx` — 实时显示日志流

### 需求 3：Neo4j 实体关系图规范化

**问题**：当前 Neo4j 存储的是简单切片数据，不是 AI 整理的规范化故事脉络。

**要求**：
1. AI 生成的图数据必须是规范化的，包含：
   - **Character 节点**：姓名、身份、性格、背景、关系标签
   - **PlotLine 节点**：主线名称、重要节点列表、状态
   - **StoryEvent 节点**：事件描述、参与角色、影响
   - **WorldbookEntry 节点**：世界观设定、规则、地理等
   - **Chapter 节点**：章节号、标题、字数、状态
   - **关系边**：BELONGS_TO（角色归属）、PARTICIPATES_IN（参与事件）、RELATED_TO（人物关系）、INFLUENCES（影响剧情）等

2. 前端通过下拉框切换显示：
   - 综合图（全部实体和关系）
   - 人物关系图（仅 Character + 关系边）
   - 情节脉络图（PlotLine + StoryEvent）
   - 世界观图（WorldbookEntry）
   - 章节结构图（Chapter + ChapterPlan）

3. 确保不同小说的数据完全隔离（通过 project_id 属性）

**修改文件**：
- `backend/app/graph/client.py` — 规范化 Cypher 查询和图创建
- `backend/app/services/chapter_ai_service.py` — AI 生成图数据时规范化
- `frontend/src/components/CommandCenter/VisualizationTab5Entity.tsx` — 已添加下拉选择框，确保数据正确

### 需求 4：XXL-Job 定时任务（可选，提升系统可靠性）

**要求**：
1. 添加 MySQL 容器（独立于 PostgreSQL）
2. 添加 XXL-Job Admin 容器
3. 后端集成 XXL-Job SDK（Python 客户端或 HTTP API）
4. 定时任务场景：
   - AI 调用失败自动重试（最多 3 次，指数退避）
   - 定时唤起 AI 继续未完成任务
   - 上次调用结果摘要发送给 AI 进行下一步操作
   - 任务超时自动标记失败

**修改文件**：
- `docker-compose.yml` — 添加 MySQL + XXL-Job Admin 服务
- `backend/app/services/` — 新建 xxl_job_service.py

### 需求 5：本地 Markdown 目录导出

**要求**：
按照以下目录结构导出：
```
书库/
└── {小说主题}/
    └── {风格标签}/
        └── {小说题目}/
            ├── 00_大纲.md
            ├── 01_第一章_{标题}.md
            ├── 02_第二章_{标题}.md
            ├── ...
            ├── assets/
            │   ├── story_entity_graph.json
            │   ├── task_workflow_graph.json
            │   └── chapter_structure_graph.json
            └── README.md（小说信息、统计）
```

**修改文件**：
- `backend/app/services/export_service.py` — 实现目录结构导出

### 需求 6：分库分表策略（防止数据串台）

**要求**：
1. 每个项目的数据必须通过 `project_id` 严格隔离
2. 所有 API 端点必须校验 `project_id` 匹配
3. Neo4j 查询必须过滤 `project_id`
4. 前端下拉框只显示当前项目的数据

**验证**：
- 检查所有 API 端点是否包含 `project_id` 过滤
- 检查所有 Neo4j 查询是否包含 `{project_id: $project_id}` 条件
- 检查前端下拉框是否只查询当前项目

## 开发约定

1. **禁止 Mock 数据**：所有前端数据必须来自真实 API
2. **中文注释**：所有代码注释使用中文
3. **保持现有代码风格**：Python 使用 async/await，TypeScript 使用 hooks
4. **错误处理**：所有 AI 服务调用必须有 try/except + 降级策略
5. **Docker 测试**：修改后通过 `docker compose restart` 验证

## 执行顺序建议

1. **P0**：需求 1（全自动模式）+ 需求 2（ReAct 可视化）
2. **P1**：需求 3（Neo4j 规范化）+ 需求 6（数据隔离）
3. **P2**：需求 5（本地导出目录）
4. **P3**：需求 4（XXL-Job，可选）

## 验证清单

- [ ] 点击"启动创作"后 AI 自动完成全流程（无需填写表单）
- [ ] 前端实时显示每步执行状态（ReAct 模式）
- [ ] Neo4j 显示规范化的故事脉络图（非简单切片）
- [ ] 下拉框切换显示不同类型的图数据
- [ ] 不同项目数据完全隔离
- [ ] 导出文件符合目录结构要求
- [ ] 无 Mock 数据
- [ ] 所有 API 调用有错误处理和降级策略
