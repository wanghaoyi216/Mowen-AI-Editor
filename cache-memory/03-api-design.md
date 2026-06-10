# API 设计文档

## 1. API 风格

- REST 为主
- SSE/WebSocket 用于 AI 任务流式状态
- OpenAPI 自动生成

Base path:

- `/api/v1`

## 2. 项目管理

### `POST /projects`

创建小说项目

### `GET /projects`

查询项目列表

### `GET /projects/{project_id}`

查询项目详情

### `PATCH /projects/{project_id}`

更新项目信息

## 3. 角色管理

### `POST /projects/{project_id}/characters`

创建角色

### `GET /projects/{project_id}/characters`

获取角色列表

### `GET /projects/{project_id}/characters/{character_id}`

获取角色详情

### `PATCH /projects/{project_id}/characters/{character_id}`

更新角色

## 4. 图谱管理

### `GET /projects/{project_id}/graph`

获取图谱节点与关系

支持参数：

- `graph_type`
- `chapter_id`
- `character_id`

### `POST /projects/{project_id}/graph/relationships`

创建或更新人物关系

### `GET /projects/{project_id}/graph/chapters/{chapter_id}`

获取与某章节相关的图谱子图

## 5. 剧情管理

### `POST /projects/{project_id}/plot-lines`

创建剧情线

### `GET /projects/{project_id}/plot-lines`

获取剧情线列表

### `POST /projects/{project_id}/plot-lines/{plot_line_id}/nodes`

创建剧情节点

## 6. 章节管理

### `POST /projects/{project_id}/chapters`

创建章节规划

### `GET /projects/{project_id}/chapters`

获取章节列表

### `GET /projects/{project_id}/chapters/{chapter_id}`

获取章节详情

### `POST /projects/{project_id}/chapters/{chapter_id}/generate`

生成章节草稿

### `POST /projects/{project_id}/chapters/{chapter_id}/revise`

修订章节草稿

## 7. 联网研究

### `POST /projects/{project_id}/research`

发起联网资料研究任务

### `GET /projects/{project_id}/research-documents`

获取资料列表

## 8. 热点探索

### `POST /projects/{project_id}/trend-explorations`

发起热门题材探索

### `GET /projects/{project_id}/trend-explorations`

获取热点探索结果

## 9. AI 任务

### `POST /projects/{project_id}/tasks/plan`

为目标任务生成执行计划

### `POST /projects/{project_id}/tasks/execute`

执行 AI 任务

### `GET /projects/{project_id}/tasks`

获取任务列表

### `GET /projects/{project_id}/tasks/{task_id}`

获取任务详情与执行痕迹

### `GET /projects/{project_id}/tasks/{task_id}/steps`

获取任务步骤与 ReAct 状态流

### `GET /projects/{project_id}/task-flows`

按项目查询任务流概览

### `GET /projects/{project_id}/chapters/{chapter_id}/task-flows`

查询某章节相关任务流

## 10. 记忆管理

### `GET /projects/{project_id}/memory`

查询记忆条目

### `POST /projects/{project_id}/memory/extract`

从任务结果中抽取长期记忆

## 10. 推荐响应模型

统一响应结构：

- `success`
- `message`
- `data`
- `meta`

统一错误结构：

- `success`
- `error_code`
- `message`
- `details`
