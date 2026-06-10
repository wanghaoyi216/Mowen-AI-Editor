# 32 - 迭代：创作约束真正落地（字数/风格/题材/不跑题）

> 日期：2026-06-07
> 状态：已完成并通过测试（backend 52 passed / frontend 4 passed / tsc 0 error）

## 一、问题诊断（根因）

之前版本最严重的问题不是前端"假数据"，而是 **AI 根本没有遵守用户设定**：

1. `NovelProject` 存了 `writing_style` / `tone` / `genre` / `theme` /
   `target_audience`，但这些字段**从未被拼进任何生成 prompt**
   （`plan_novel_outline` / `writer_node` / `generate_chapter_draft` /
   `revise_chapter_draft` / 一致性检查全都没注入）。
2. 字数用 `len(content)`（含标点空格的字符数），且 **word_target 只在 prompt 里
   提了一句、从不强制**——没有"过短就续写"的闭环，AI 也无从得知当前已写多少字。
3. 项目根本没有"单章字数区间 / 目标章节数"字段；`ModalCreateProject` 收集了
   字数/章节数却被 schema 静默丢弃（extra=ignore）。
4. `creator_temperature` / `controller_temperature` 定义了但从未使用，温度恒为 0.7。
5. 前端可视化其实**全是真实 API 驱动**（D3 + ECharts，DB 来源），"看起来假"是因为
   后端数据稀疏 + 仪表盘空态用的是"永久骨架屏"。

## 二、本轮改动

### 后端
- **新增 `app/services/writing_constraints_service.py`**：
  - `count_words`：CJK 按字、拉丁按词的字数统计（替代 `len`）。
  - `load_project_constraints`：读项目约束，缺失给兜底，不抛异常。
  - `build_constraint_block` / `build_word_budget_line`：把题材/风格/基调/受众/
    主题/字数预算/当前字数/不跑题约束渲染成中文指令块。
- **`NovelProject` + schema + 迁移**：新增 `language` /
  `min_words_per_chapter` / `max_words_per_chapter` / `target_chapters`
  （迁移 `20260607_0001_project_writing_constraints`，幂等、方言安全）。
- **`openrouter_service`**：`generate_with_openrouter` 增加
  `temperature` / `max_tokens` / `role`（creator/controller→对应温度）；
  仅在显式提供时下传，兼容旧测试桩。
- **`chapter_ai_service`**：plan/draft/revise/一致性 prompt 全部注入约束块；
  字数用 `count_words`；新增 `_enforce_word_target`——草稿不足目标 80% 时
  回灌"当前字数/还差多少"驱动模型**无缝续写**（最多 2 轮，带回声去重）。
- **`novel_orchestrator_service`**：planner prompt 注入约束 + 每章字数区间提示；
  每章 `word_target` 夹到项目区间内。
- **`chapter_loop_service.writer_node`**：注入约束块 + `_enforce_writer_word_target`
  续写补足；`word_count` 统一走 `count_words`。
- **`chapter_consistency_service`**：要求模型输出
  `角色: x | 剧情: x | 世界: x | 节奏: x | 风格: x` 数值评分，
  使仪表盘五维雷达图成为真实数据。

### 前端
- `ModalCreateProject`：新增"作品风格 / 情感基调 / 目标读者 / 每章最少/最多字数"，
  并改用 `min_words_per_chapter` / `max_words_per_chapter` 等真实字段名。
- `CommandCenter.handleCreateProject`：透传全部新约束字段到 `createProject`。
- `CommandCenter.handleStartCreation`：自动创作的 `word_target` 改为按项目字数
  区间中点推导（不再硬编码 1800），`style_hint` 兜底用项目 `writing_style`。
- `types.ts`：`Project` / `ProjectCreatePayload` 补全新字段。
- `VisualizationTab8Dashboard`：空态从"永久骨架屏"改为明确的"暂无创作数据"提示。

## 三、验证
- 新增 `tests/test_writing_constraints.py`（5 例）：字数统计、约束块渲染、
  draft 注入约束、字数强制续写。
- 扩展 `tests/test_projects_api.py`：项目创建/读取round-trip新约束字段。
- 全量：backend `52 passed`，frontend `4 passed`，`tsc --noEmit` 0 error。

## 四、下一步建议
1. Phase 3 Novel Reviewer 仍是占位（`novel_orchestrator_service` TODO），可接入
   全文一致性 AI 审查并产出数值评分。
2. `creator/controller` 温度已可用，可针对"创作 vs 结构化抽取"进一步调参。
3. 可在前端"项目设置"里允许运行中调整字数区间（后端 schema 已支持 PATCH）。
