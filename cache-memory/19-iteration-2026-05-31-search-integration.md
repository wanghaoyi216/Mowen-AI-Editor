# 2026-05-31 搜索工具接入与热点探索执行器实施记录

## 本轮目标

1. 安全接入 Tavily 和 Firecrawl
2. 实现真实联网的热点探索执行器
3. 将热点探索执行器接入 ReAct 执行链

## 本轮完成内容

1. 新增 Tavily 客户端封装。
2. 新增 Firecrawl 客户端封装。
3. 配置层新增：
   - `FIRECRAWL_KEY`
   - `TAVILY_KEY`
4. Docker Compose 支持将上述环境变量透传给 backend。
5. 新增趋势探索执行请求模型。
6. `trend_service` 新增真实联网执行逻辑：
   - Tavily 搜索
   - Firecrawl 抓取
   - 基础 topics / tags / directions 抽取
7. 新增趋势探索执行接口：
   - `POST /projects/{project_id}/trend-explorations/execute`
8. 新增趋势探索 ReAct 执行接口：
   - `POST /projects/{project_id}/tasks/execute-trend-react`

## 安全边界

1. 本轮没有读取或回显你的密钥内容。
2. 代码只通过运行时环境变量取值。
3. 仓库内没有写入任何真实密钥。

## 当前意义

这是项目第一次接入“真实联网能力”，不再只是内部结构模拟。现在热点探索已经可以成为真正的 AI 工作流输入源。

## 当前限制

1. 当前的 topics / tags / directions 抽取还是轻量级规则抽取。
2. 还没有把搜索结果进一步映射到世界观、角色、剧情线自动设计。
3. Firecrawl 抓取结果目前是原样存档，尚未做更深层信息清洗。

## 下一步建议

1. 把热点探索结果结构化映射到 PlotLine / Character / Worldbook 设计输入
2. 为 Trend ReAct 执行链增加真正的抽取与总结步骤
3. 将搜索结果摘要接入章节设计和故事方向建议
4. 把 PlotLine / Event / Chapter / Character-Event 继续同步到 Neo4j
