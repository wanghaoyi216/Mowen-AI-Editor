# 2026-05-31 趋势探索结果映射到创作资产实施记录

## 本轮目标

把热点探索结果从“搜索结果存档”推进到“可直接服务小说创作的结构化资产”。

## 本轮完成内容

1. 新增 `WorldbookEntry` 模型。
2. 新增世界观条目接口：
   - `GET /projects/{project_id}/worldbook`
   - `POST /projects/{project_id}/worldbook`
3. 新增趋势资产映射请求模型。
4. 新增 `trend_asset_mapping_service`：
   - 从趋势探索结果生成 PlotLine
   - 从趋势探索结果生成角色候选
   - 从趋势探索结果生成 Worldbook 条目
5. 新增趋势资产映射接口：
   - `POST /projects/{project_id}/trend-explorations/map-assets`
6. 前端新增 Trend Workbench：
   - 执行热点探索
   - 显示趋势探索记录
   - 一键映射到剧情线、角色、世界观
   - 显示映射结果

## 当前意义

这是项目第一次让“搜索结果”直接变成“创作输入资产”，也就是：

1. 题材趋势 -> 剧情线候选
2. 题材趋势 -> 角色候选
3. 题材趋势 -> 世界观设定条目

这样后续章节设计就不需要只依赖人工输入或静态提示词，而可以基于系统生成的结构化资产。

## 当前限制

1. 当前映射仍是轻量规则映射，不是深层语义抽取。
2. 角色候选和剧情线候选还没有去重与相似度合并。
3. Worldbook 还未同步到图谱层。
4. 这些资产还未自动接入章节生成工作流。

## 下一步建议

1. 将 PlotLine / Event / Chapter / Character-Event / Worldbook 同步到 Neo4j
2. 用趋势探索结果自动生成章节设计输入
3. 为映射结果增加质量评分与去重逻辑
4. 让 ReAct 执行链在真实生成章节时自动读取这些资产
