# 2026-05-31 章节设计与章节草稿生成实施记录

## 本轮目标

把趋势资产、角色、剧情线、世界观真正接入章节设计与章节草稿生成流程。

## 本轮完成内容

1. 新增 `ChapterPlan` 模型。
2. 新增章节设计服务：
   - 聚合 PlotLine
   - 聚合 Character
   - 聚合 Worldbook
   - 聚合 TrendExploration
   - 通过 OpenRouter 生成章节设计稿和 beat sheet
3. 新增章节草稿生成服务：
   - 读取章节设计稿
   - 读取资产摘要
   - 通过 OpenRouter 生成章节草稿
4. 新增章节接口：
   - `GET /projects/{project_id}/chapters/{chapter_id}`
   - `POST /projects/{project_id}/chapters/{chapter_id}/design`
   - `POST /projects/{project_id}/chapters/{chapter_id}/generate`
5. 前端新增 Chapter Workbench：
   - 选择章节
   - 输入设计指导
   - 生成章节设计
   - 输入文风提示
   - 生成章节草稿
   - 展示设计稿和草稿内容

## 当前意义

这一步非常关键，因为现在系统第一次具备了：

1. 搜索结果映射出的资产
2. 章节设计
3. 模型生成章节草稿

三者之间的真实连接。

也就是说，项目已经从“资料管理系统”变成了“开始能实际产出章节草稿的创作系统”。

## 当前限制

1. 章节设计目前仍是单次生成，没有版本化和差异对比。
2. 草稿生成后还没有修订链。
3. 章节设计和草稿内容还未同步进 Neo4j 图谱层。
4. 章节生成目前还没有显式任务化接入 ReAct 运行态。

## 下一步建议

1. 将章节设计与章节生成纳入任务流和步骤运行态
2. 将 ChapterPlan / StoryEvent / Character-Event / PlotLine 同步到 Neo4j
3. 为章节草稿增加修订和一致性检查
4. 增加章节设计版本与草稿版本管理
