# 2026-05-31 步骤运行态与混合图谱实施记录

## 本轮目标

1. 让任务步骤拥有独立运行态
2. 让图谱从单一人物关系扩展到剧情线、事件、章节节点

## 本轮完成内容

1. 新增任务步骤运行态模型：
   - `TaskStepStatusUpdate`
   - `TaskStepRuntimeState`
2. 新增 Redis 任务步骤运行态能力：
   - 写入步骤运行态
   - 读取全部步骤运行态
3. 新增任务步骤接口：
   - `POST /projects/{project_id}/tasks/{task_id}/steps`
   - `GET /projects/{project_id}/tasks/{task_id}/step-runtime`
   - `POST /projects/{project_id}/tasks/{task_id}/step-runtime`
4. 创建任务步骤时自动写入 Redis 初始运行态。
5. 图谱查询由单一角色图扩展为混合图：
   - `character`
   - `plot_line`
   - `story_event`
   - `chapter`
6. 图谱接口支持 `graph_type=mixed|character|plot|event|chapter`
7. 前端 Graph Studio 可切换图谱类型并展示不同节点类型。

## 当前能力提升

### 任务系统

现在任务系统已经具备：

1. 任务级运行态
2. 步骤级运行态
3. 任务历史持久化
4. 步骤历史持久化

这意味着后续实现 ReAct 执行器时，可以把：

- Plan
- Reason
- Act
- Observe
- Extract

都落成明确步骤，并同步到数据库和 Redis。

### 图谱系统

现在图谱不再只适合展示人物关系，而是已经能表达：

1. 剧情线包含哪些事件
2. 章节包含哪些事件
3. 项目内有哪些剧情节点

这为后续“故事走向可视化”和“章节影响分析”打下了结构基础。

## 当前仍未完成

1. 图谱中还没有真正的 Character -> Event 参与关系。
2. PlotLine / Event / Chapter 还未同步到 Neo4j。
3. ReAct 执行器还未自动驱动步骤状态流转。
4. 热点探索联网执行器仍未实现。

## 下一步建议

1. 定义 Character 与 Event 的参与关系表
2. 将 PlotLine / Event / Chapter 也同步到 Neo4j
3. 开始实现 ReAct Planner / Executor 的最小执行链
4. 将热点探索模块接入真实联网抓取与抽取
