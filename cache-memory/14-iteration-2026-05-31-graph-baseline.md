# 2026-05-31 图谱闭环实施记录

## 本轮目标

建立“角色数据 -> 角色关系 -> 图谱接口 -> 前端图谱展示”的最小闭环。

## 本轮完成内容

1. 新增角色关系表 `character_relationships`。
2. 图谱接口从占位改为项目级真实接口：
   - `GET /api/v1/projects/{project_id}/graph`
   - `POST /api/v1/projects/{project_id}/graph/relationships`
3. 新增 Neo4j 客户端能力：
   - 连接可用性探测
   - 角色节点 upsert
   - 角色关系 upsert
   - 项目级角色图谱读取
4. 新增 SQLite fallback 机制：
   - Neo4j 不可用时，仍从本地关系表返回图谱数据
5. 创建角色时自动尝试同步到 Neo4j。
6. 创建角色关系时自动尝试同步到 Neo4j。
7. 前端 Graph Studio 改为真实调用图谱 API。
8. 前端新增最小图谱可视化 SVG 渲染。
9. 新增演示种子脚本 `backend/scripts/seed_demo.py`。

## 当前运行方式

### 后端

1. `pip install -r backend/requirements.txt`
2. `uvicorn app.main:app --reload`

### 演示数据

1. `cd backend`
2. `python scripts/seed_demo.py`

### 前端

1. `cd frontend`
2. `npm install`
3. `npm run dev`

## 当前行为说明

1. 如果 Neo4j 已启动且凭据正确，角色和关系会同步到 Neo4j。
2. 如果 Neo4j 未启动，图谱仍可通过 SQLite fallback 展示。
3. 前端默认读取项目 ID `1` 的图谱。

## 本轮价值

1. 图谱已从“概念设计”升级为“可运行的实际模块”。
2. 前后端对图谱的接口边界已固定。
3. 后续可在不改接口的情况下继续把图谱扩展到事件、章节、剧情线。

## 下一步建议

1. 增加角色关系更新与删除接口。
2. 扩展图谱节点到 `Chapter`、`PlotLine`、`Event`。
3. 增加章节相关图谱过滤逻辑。
4. 在图谱点击节点后联动右侧详情面板。
5. 将 AI 任务流与图谱事件节点关联。
