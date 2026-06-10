# 2026-05-31 章节任务化与图谱深化实施记录

## 本轮目标

1. 将章节设计与章节生成纳入任务流和步骤运行态
2. 继续深化章节相关图谱结构

## 本轮完成内容

1. 新增 `chapter_task_service`。
2. 章节设计现在支持任务化执行：
   - `POST /projects/{project_id}/chapters/{chapter_id}/design-task`
3. 章节草稿生成现在支持任务化执行：
   - `POST /projects/{project_id}/chapters/{chapter_id}/generate-task`
4. 任务化章节链会：
   - 创建任务
   - 创建步骤
   - 更新任务运行态
   - 更新步骤运行态
5. 图谱 fallback 新增 `ChapterPlan` 节点。
6. 图谱新增关系：
   - `Chapter -> ChapterPlan`
   - `PlotLine -> ChapterPlan`
7. 修复了图谱服务中事件边在错误循环里生成的 bug。
8. 前端 Chapter Workbench 改为优先走任务化章节设计/章节生成接口。
9. 前端现在会展示最近一次章节任务的 `task_id`。

## 当前意义

章节工作流现在不再是普通同步调用，而是正式进入任务体系。这意味着：

1. 章节设计可以追踪
2. 章节生成可以追踪
3. 步骤状态可以追踪
4. 后续一致性检查和修订链也有了正确挂点

## 当前仍未完成

1. 章节任务还没有和 Task Runtime 面板自动联动展示。
2. ChapterPlan / PlotLine / Event / Character-Event 还未写入 Neo4j 主图。
3. 章节修订链和一致性检查还未落地。

## 下一步建议

1. 将 ChapterPlan / PlotLine / Event / Character-Event 正式同步到 Neo4j
2. 为章节草稿增加一致性检查任务
3. 为章节设计和草稿增加版本化
4. 让前端任务流中心联动章节任务详情
