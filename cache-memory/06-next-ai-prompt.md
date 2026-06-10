# 下一位 AI 的任务提示词

你现在接手的项目是一个智能 AI 自动小说编辑器，技术栈为 React + FastAPI，架构要求轻量级，同时支持 Neo4j 图谱能力。

## 你的工作方式要求

1. 必须先阅读 `cache-memory` 下的全部核心文档。
2. 必须先输出 step-by-step 计划，再执行。
3. 必须采用 ReAct + Plan-and-Execute + Extraction 模式。
4. 每完成一个功能，都必须更新以下文档：
   - `cache-memory/07-issues-log.md`
   - `cache-memory/08-solutions-log.md`
   - `cache-memory/09-learnings.md`
   - `cache-memory/10-reusable-details.md`
   - `cache-memory/00-master-plan.md`
5. 必须优先从后端逻辑出发，确认数据结构、API、业务约束，再做前端。
6. 必须保证所有新代码与已有设计一致，如果发现不一致，先修正文档再实现。

## 当前上下文

已完成：

1. 产品设计文档
2. 数据库设计文档
3. API 设计文档
4. 业务逻辑反思文档
5. 详细任务执行方案书

当前优先任务：

1. 为章节版本增加 diff/compare 展示，并联动任务中心查看修订链
2. 将 WorldbookEntry 正式同步到 Neo4j，并接入 mixed graph 前端展示
3. 为趋势映射结果增加去重、评分与模型辅助清洗
4. 补全一键式编排工作流：
   - 趋势探索
   - 资产映射
   - 章节设计
   - 草稿生成
   - 一致性检查
   - 一致性修订
5. 将 Alembic 融入容器启动流程，并做完整 Docker 联调验证

## 执行要求

每次做一个明确功能，遵循下面格式：

### 1. Plan

- 明确目标
- 明确输入输出
- 明确依赖
- 明确验证方式

### 2. Act

- 进行代码实现
- 进行必要测试
- 记录结果

### 3. Extract

- 抽取可复用 Prompt
- 抽取业务约束
- 抽取潜在风险
- 抽取下一步建议

## 当前建议首先执行的功能

“先把章节修订链做成可视化版本比较能力，再继续补 WorldbookEntry 到 Neo4j 的同步与展示。”
