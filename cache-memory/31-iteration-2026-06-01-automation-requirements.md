# 31 - Novel AI Editor 全链路自动化 AI 小说创作系统 · 需求规格说明书

> 日期：2026-06-01
> 版本：v1.0
> 状态：待执行
> 关联项目：Novel AI Editor（novel_ai_editer）

---

## 一、项目定位与核心理念

本项目定位为 **AI 全自动小说创作操作系统（Creative OS）**。核心理念是：**AI 是执行主体，人类是超参数设定者与观察者**。整个业务流程由 AI 自主决策、自主执行，人类的角色从"参与者"退化为"监督者与建议者"。

**核心原则**：
- AI 自主搜索、自主分析、自主决策、自主写作、自主导出。
- 人类仅设定超参数和观察进度，不参与中间创作决策。
- 全链路执行轨迹完整可追溯，图数据库写入必须经过 AI 分析。

---

## 二、图数据库（Neo4j）可视化效果优化

### 2.1 当前状态
现有基于 SVG 的简单圆形节点 + 直线边的图表展示（`frontend/src/components/GraphStudioView.tsx`），节点按圆形等距排列，缺少交互与视觉层次。

### 2.2 可视化引擎升级
1. 将当前 SVG 静态图替换为 **D3.js Force-Directed Graph（力导向图）** 或 **vis-network** 或 **Cytoscape.js** 等专业图可视化库。
2. 实现以下特效：
   - **力导向布局**：节点自动分散，相关节点聚拢，无关节点推开。
   - **节点分级渲染**：按实体类型（角色/剧情线/事件/章节/世界观条目）使用不同颜色、形状、图标和大小。
   - **边分级渲染**：按关系类型（父子/敌对/同盟/恋爱/包含/触发等）使用不同颜色、粗细、虚线/实线。
   - **节点悬停高亮**：鼠标悬停时高亮该节点及其一度邻居，其余节点半透明。
   - **点击展开/折叠**：点击节点展示详细信息面板（实体属性、关联列表）。
   - **缩放与平移**：支持滚轮缩放和拖拽平移。
   - **动画过渡**：新增/删除节点时带有平滑动画。

### 2.3 筛选与搜索
1. 图谱类型筛选器保持现有 6 种（mixed / character / plot / event / chapter / worldbook）。
2. 新增**全文搜索框**：输入关键词实时高亮匹配节点。
3. 新增**关系强度筛选**：按 intensity 范围过滤边。

### 2.4 快捷键与导出
1. 支持 Ctrl+Z / Ctrl+Y 撤销/重做视图操作。
2. 支持导出图谱为 PNG / SVG 图片。

### 2.5 技术选型建议
- **推荐**：D3.js v7 + d3-force 物理引擎，自定义 SVG 渲染（最灵活，与现有 SVG 体系兼容）。
- **备选**：vis-network（基于 vis.js，上手快但定制性一般）。
- **备选**：Cytoscape.js（功能强大但包体积较大）。

---

## 三、AI Agent 编排框架：LangGraph + ReAct + Plan-and-Execute

### 3.1 当前状态
已有基础 ReAct 五阶段执行器（`backend/app/services/react_executor_service.py`），但这是硬编码的状态流转，没有真正的 AI 决策循环。

### 3.2 引入 LangGraph 作为编排引擎
1. 在后端引入 `langgraph` Python 库（`pip install langgraph`）。
2. 定义 **StateGraph** 作为所有 workflow 的基座，替代当前硬编码的 `step_specs` 列表。
3. 状态对象需包含：
   - `messages`：对话历史（System / Human / AI / Tool 消息）。
   - `project_context`：当前项目的全部上下文（角色、剧情线、章节、世界观）。
   - `task_output`：当前任务产出。
   - `tool_calls`：工具调用记录（JSON 格式，含工具名、输入、输出、耗时）。
   - `next_action`：LLM 决定的下一步动作。
   - `error_log`：错误记录。
   - `interrupted`：是否触发人类中断。

### 3.3 ReAct 循环实现
1. 实现标准的 **ReAct（Reasoning + Acting）** 循环：
   - **Thought**：AI 思考当前状态，决定下一步做什么（LLM 生成）。
   - **Action**：AI 调用对应的 Tool。
   - **Observation**：Tool 返回结果，注入到消息历史。
   - **Repeat**：循环执行直到 AI 输出 `FINISH` 或达到最大步数（默认 20 步，可配置）。
2. **工具注册机制**：所有工具通过 LangGraph 的 `ToolNode` 注册，AI 可以自主选择调用哪个工具。
3. 工具类型定义：

| 工具类型 | 工具名称 | 功能 |
|---------|---------|------|
| 搜索类 | `web_search` | 搜索网络热点小说、作者信息、写作风格 |
| 搜索类 | `web_scrape` | 抓取指定 URL 的页面内容 |
| LLM 类 | `llm_generate` | 调用 OpenRouter LLM 生成内容 |
| 图谱类 | `query_graph` | 查询 Neo4j 图数据库（角色/剧情线/事件等） |
| 图谱类 | `upsert_entity` | 插入或更新图数据库中的实体 |
| 图谱类 | `upsert_relationship` | 插入或更新图数据库中的关系 |
| 数据库类 | `query_sqlite` | 查询 SQLite 中的业务数据 |
| 文件类 | `export_chapter_md` | 将章节内容导出为 .md 文件 |
| 文件类 | `export_project_archive` | 导出整个项目的压缩包 |
| 分析类 | `extract_entities` | 从文本中提取实体和关系 |
| 分析类 | `check_consistency` | 检查章节内容的一致性 |

### 3.4 Plan-and-Execute 模式实现
1. 在 ReAct 之上增加 **Plan-and-Execute** 层：
   - **Planner Agent**：接收总体任务目标，产出分步骤执行计划（plan_text），每一步有明确的 objective 和 expected_output。
   - **Executor Agent**：逐步骤执行计划，每个步骤内部走 ReAct 循环。
   - **Replanner Agent**：每个步骤执行完毕后，检查当前产出是否满足目标，必要时重新规划剩余步骤。
2. 三个 Agent 通过 LangGraph 的条件边（ConditionalEdge）串联。

### 3.5 核心 Workflow 定义
必须实现以下 5 条核心 workflow，每条 workflow 对应一个独立的 LangGraph StateGraph：

#### WF-01：热点发现与灵感生成
- **触发时机**：项目创建后或人类手动触发。
- **输入**：超参数（theme, writing_style 等）。
- **执行步骤**：
  1. **Plan**：Planner Agent 规划搜索策略（搜索哪些平台、关键词组合）。
  2. **Search**：AI 自主决定搜索关键词，调用 `web_search`。
  3. **Scrape**：AI 自主选择高价值页面，调用 `web_scrape`。
  4. **Analyze**：AI 提取写作风格、故事逻辑、主线剧情结构，调用 `llm_generate`。
  5. **Suggest**：AI 生成灵感报告和方向建议。
  6. **Store**：AI 将灵感报告存入 worldbook，调用 `upsert_entity`。
- **输出**：灵感报告 → worldbook 条目。

#### WF-02：世界观与角色构建
- **触发时机**：WF-01 完成后自动触发。
- **输入**：灵感报告（worldbook 数据）。
- **执行步骤**：
  1. **Plan**：Planner Agent 规划世界观设计方案。
  2. **Design World**：AI 设计世界观（地点、规则、力量体系等），调用 `llm_generate` + `upsert_entity`。
  3. **Design Characters**：AI 创建角色（含性格/动机/关系），调用 `llm_generate` + `upsert_entity`。
  4. **Design Plots**：AI 设计剧情线（主线/支线），调用 `llm_generate` + `upsert_entity`。
  5. **Build Relationships**：AI 构建角色关系网络，调用 `upsert_relationship`。
- **输出**：世界观实体、角色实体、剧情线实体、关系 → Neo4j + SQLite。

#### WF-03：章节大纲规划
- **触发时机**：WF-02 完成后自动触发。
- **输入**：世界观 + 角色 + 剧情线数据。
- **执行步骤**：
  1. **Plan**：Planner Agent 决定章节总数和叙事策略（顺序写或跳写）。
  2. **Outline Per Chapter**：AI 为每个章节生成设计概要（design_brief）和节拍表（beat_sheet）。
  3. **Link Plots**：AI 将章节与剧情线关联，决定章节顺序。
  4. **Store Outlines**：AI 将所有章节大纲存入数据库。
- **输出**：ChapterPlan 记录列表。

#### WF-04：章节写作执行
- **触发时机**：WF-03 完成后自动触发，或人类手动触发（可指定章节范围）。
- **输入**：章节大纲。
- **执行步骤**：
  1. **Plan Writing Strategy**：AI 决定写作策略（逐章顺序 / 主干先写 / 混合）。
  2. **Generate Draft**：AI 生成章节初稿，调用 `llm_generate`。
  3. **Consistency Check**：AI 将初稿与已有章节对比，调用 `check_consistency`，输出 consistency_report。
  4. **Revise**：AI 根据一致性报告修订，调用 `llm_generate` 生成 final_content。
  5. **Extract Entities**：AI 从 final_content 提取新实体/关系，调用 `extract_entities`。
  6. **Store to Neo4j**：AI 将提取的实体/关系入库，调用 `upsert_entity` + `upsert_relationship`。
  7. **Export MD**：AI 将章节导出为 .md 文件，调用 `export_chapter_md`。
  8. **Repeat**：循环执行直到所有章节完成。
- **输出**：章节正文 + 一致性报告 + 图数据库更新 + .md 文件。

#### WF-05：实体关系提取与图入库
- **触发时机**：贯穿 WF-01 至 WF-04，每产生新内容即触发。
- **输入**：任意文本（热点分析报告 / 角色设计 / 章节正文）。
- **执行步骤**：
  1. **Extract**：AI 调用 `extract_entities` 从文本提取实体和关系。
  2. **Deduplicate**：AI 对比已有实体，决定新增还是更新。
  3. **Upsert**：AI 调用 `upsert_entity` + `upsert_relationship` 写入图数据库。
  4. **Log**：记录 TaskLog，log_type 为 `graph_mutation`。
- **输出**：入库结果摘要（新增/更新的实体和关系数量）。

---

## 四、AI 自主决策链

### 4.1 人类角色重新定义
1. **人类不参与内容创作决策**：不决定搜索什么关键词、不决定写什么情节、不决定角色关系。
2. **人类只做三件事**：
   - **任务启动前**：设定超参数。
   - **任务执行中**：观察进度（通过监控台）。
   - **可选介入**：当 AI 遇到阻塞或 Ambiguity 时，AI 主动向人类提问，人类给予方向性建议。

### 4.2 AI 自主决策示例
| 阶段 | AI 自主决策内容 |
|------|----------------|
| 搜索阶段 | 搜索关键词、搜索平台、抓取哪些页面、分析哪些维度 |
| 分析阶段 | 从搜索结果中提取哪些写作风格要素、故事逻辑模式、主线剧情结构 |
| 设计阶段 | 世界观设定细节、角色性格和背景、剧情线走向 |
| 写作阶段 | 章节长度、叙事节奏、POV 切换、伏笔埋设、写作策略选择 |
| 图入库阶段 | 从文本中提取哪些实体和关系，无需人工预定义 schema |

### 4.3 人类介入触发条件（Interrupt）
1. AI 在以下情况应暂停并向人类提问（通过 Interrupt 机制）：
   - 超参数不明确（如用户未指定小说风格）。
   - 两个以上可行方向难以抉择（如：都市异能 vs 都市重生）。
   - 外部工具调用连续失败 3 次以上。
2. 人类的回答应为建议性质（如"偏向悬疑风格"），而非具体指令。

---

## 五、AI 自主写作模块详细设计

### 5.1 写作策略
AI 可自主选择两种写作策略，或混合使用：
- **逐章节顺序写作**：从第 1 章到第 N 章线性推进。适用于剧情线性推进、伏笔较少的小说。
- **主干先写法（Skeleton-First）**：先写关键情节点（重大转折、高潮、结局），再回填过渡章节和细节。适用于剧情复杂、支线众多的小说。
- 策略选择由 AI 根据剧情复杂度自主决定，并在 plan_text 中记录。

### 5.2 章节生成流程（每章内部子步骤）
每章写作内部执行以下 5 个子步骤：
1. **章节设计（ChapterPlan）**：AI 产出 design_brief（设计概要）、beat_sheet（节拍表）、asset_summary（用到的角色/场景/伏笔）。
2. **初稿生成（Draft）**：AI 调用 LLM 生成 draft_content。
3. **一致性检查（Consistency Check）**：AI 将初稿与已有章节、角色设定、时间线对比，输出 consistency_report。
4. **修订润色（Revision）**：AI 根据一致性报告修改草稿，输出 final_content。
5. **实体提取（Entity Extraction）**：AI 从 final_content 中提取新出现的实体/关系，推送到图数据库。

### 5.3 版本管理
1. 每次修订生成一个新 ChapterVersion 记录。
2. operation_type 包括：draft / consistency_check / revision。
3. 保留 selected_model，便于回溯和审计。

---

## 六、.md 导出与文件存储方案

### 6.1 导出格式
每一章的 final_content 使用 Markdown 格式导出为 `.md` 文件。Markdown 文件头包含 YAML Front Matter：

```yaml
---
chapter_no: 1
title: "第一章标题"
word_count: 3500
created_at: "2026-06-01T10:00:00+08:00"
characters:
  - 张三
  - 李四
plot_lines:
  - 主线A
  - 支线B
---
```

### 6.2 文件存储结构
导出目录结构如下：

```
exports/
└── {项目名称}/
    ├── {项目名称}_全本.md             # 全本合并文件（WF-04 全部章节完成后自动生成）
    ├── chapters/
    │   ├── 第01章_{章节标题}.md
    │   ├── 第02章_{章节标题}.md
    │   └── ...
    ├── assets/
    │   ├── characters.json            # 角色数据导出
    │   ├── relationships.json         # 关系数据导出
    │   ├── plot_lines.json            # 剧情线导出
    │   ├── worldbook.json             # 世界观导出
    │   └── graph_export.png           # 图谱截图
    └── workflow_logs/
        ├── wf-01_trend_inspiration/
        │   ├── plan.md                # Workflow 任务计划
        │   └── trace.md               # Workflow 执行轨迹（含工具调用日志）
        ├── wf-02_worldbuilding/
        │   └── ...
        ├── wf-03_outline_planning/
        │   └── ...
        ├── wf-04_chapter_writing/
        │   └── ...
        └── wf-05_entity_extraction/
            └── ...
```

### 6.3 导出触发方式
1. **自动导出**：每个 Workflow 完成后自动将产出物写入对应目录。
2. **手动导出**：前端提供"一键导出全部"按钮，调用 `export_project_archive`，打包 zip 下载。

---

## 七、前端功能重构：从编辑器到监控台（Observer Dashboard）

> **核心理念**：前端不再是内容编辑器，而是 **AI 业务执行情况的实时可视化监控台**。

### 7.1 保留并增强的现有页面
1. **仪表盘（/）**：项目概览 + 数据统计（增强为显示 AI 执行摘要）。
2. **图谱工作室（/graph-studio）**：升级为 D3.js 交互力导向图（见第二章）。

### 7.2 重构为只读展示的页面
以下页面改造为只读展示，人类无法手动增删改内容：
1. **热点探索（/trends）**：展示 AI 搜索到的热点、分析结果、灵感方向。
2. **角色图谱（/characters）**：展示 AI 创建的角色列表及关系图。
3. **剧情设计（/plots）**：展示 AI 规划的剧情线。
4. **章节工作台（/chapters）**：展示 AI 写作的章节列表、内容预览、版本历史。

### 7.3 新增核心页面：工作流监控台（/workflow-monitor）
这是整个系统的**核心前端页面**，替代当前的 TaskRuntimePanel。必须包含以下 6 个功能区域：

#### 7.3.1 Workflow 依赖图
- 使用 D3.js 力导向图（与图谱工作室使用不同配色主题）。
- 显示 5 条 Workflow 及其依赖关系（WF-01 → WF-02 → WF-03 → WF-04，WF-05 横向贯穿）。
- 当前执行的 Workflow 高亮脉冲动画。
- 已完成的 Workflow 显示 ✓（绿色）。
- 失败的 Workflow 显示 ✗（红色）并显示错误摘要。
- 待执行的 Workflow 灰色半透明。

#### 7.3.2 步骤进度条（Stepper）
- 当前 Workflow 内各步骤的水平步进条。
- 已完成步骤：✓（绿色背景）。
- 执行中步骤：旋转加载动画（蓝色）。
- 待执行步骤：灰色。
- 失败步骤：✗（红色）并附带错误摘要 tooltip。

#### 7.3.3 工具调用日志面板
- 实时滚动的终端风格日志面板（终端黑底绿字或白底黑字风格）。
- 每条日志显示：
  - 时间戳（精确到毫秒）。
  - 工具名称（不同工具类型用不同颜色：搜索蓝色、LLM 紫色、图数据库橙色、文件导出绿色）。
  - 输入参数摘要（JSON 折叠显示，点击展开）。
  - 返回状态（成功绿色、失败红色、超时黄色）。
  - 耗时（毫秒）。
- 支持按工具类型过滤。
- 支持关键词搜索。

#### 7.3.4 正在执行的业务详情卡片
- 当前任务标题、描述、状态。
- 已执行时间（倒计时或正计时）。
- 当前 ReAct 循环信息：
  - **Thought**：AI 最近一次思考内容（紫色高亮框）。
  - **Action**：AI 最近一次工具调用（蓝色框）。
  - **Observation**：工具返回结果摘要（绿色框）。
- 一致性检查报告摘要（如有）。

#### 7.3.5 AI 决策历史时间线
- 按时间倒序展示 AI 做出的所有自主决策。
- 每条记录包含：时间戳、决策内容（含决策原因和结果）。
- 支持折叠/展开。
- 人类可以此了解 AI 的"思考过程"。

#### 7.3.6 人类介入区域
- 固定在面板底部的输入栏。
- 默认隐藏（折叠到底部）。
- 当 AI 发出 Interrupt 请求时自动展开。
- 显示 AI 提出的问题（黄色警告框包裹）。
- 人类输入建议后点击"提交建议"。
- 提交后 AI 继续执行。

### 7.4 全局顶部状态栏
固定在页面顶部的横条，始终可见：
- 当前正在运行的 Workflow 名称（带脉冲动画）。
- 总体进度百分比（所有章节完成度）。
- 已执行时间。
- 暂停 / 继续 / 停止 三个按钮：
  - **暂停**：AI 立即停止，但保留当前状态（可继续）。
  - **继续**：从暂停点恢复执行。
  - **停止**：终止整个 Workflow 链。
  - **注意**：人类可随时暂停/停止，但**无法修改 AI 已做出的创作决策**。

---

## 八、图数据智能入库管道（AI-Analyze-Before-Store）

### 8.1 实体关系提取 Agent
1. 新增 `EntityExtractionAgent`，基于 LangGraph 实现。
2. 触发时机：
   - 每章 final_content 生成后自动触发（WF-04 第 5 步）。
   - 网络搜索内容入库前自动触发（WF-01 第 4 步）。
3. 工作流程：
   - **Input**：一段文本（章节内容 / 搜索摘要）。
   - **AI 分析**：LLM 从文本中提取：
     - 新增角色实体（姓名、别名、身份、性格特征）。
     - 新增世界观实体（地点、规则、物品、概念）。
     - 新增/更新角色关系（关系类型、强度、备注）。
     - 新增/更新事件（事件类型、影响级别、关联章节）。
   - **去重与合并**：AI 对比已有实体，决定是新增还是更新。
   - **入库**：通过 `graph_service.py` 的现有函数写入 Neo4j + SQLite。
   - **返回**：入库结果摘要（新增/更新的实体和关系数量）。

### 8.2 图数据版本追踪
1. 每次图数据库写入操作记录一条 `TaskLog`（已有表），log_type 为 `graph_mutation`。
2. 前端图谱页面显示"图谱更新时间"和"实体/关系变更摘要"。

---

## 九、人类超参数控制面板

### 9.1 项目级超参数（任务启动前必填）
在创建新项目时，AI 主动向人类询问以下超参数（通过 Interrupt 机制）：

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `theme` | string | 小说主题，如"都市异能""古装权谋""星际科幻" | 无（必填） |
| `writing_style` | string | 小说风格，如"严肃文学""轻小说""网文爽文""悬疑推理" | 无（必填） |
| `target_audience` | string | 目标读者，如"男性向""女性向""全年龄" | "全年龄" |
| `tone` | string | 基调，如"热血""虐心""轻松搞笑""黑暗" | 无 |
| `word_count_range` | [min, max] | 单章字数范围，AI 可在此区间自主调节 | [2000, 5000] |
| `total_chapters` | number 或 "auto" | 总章节数，固定数量或由 AI 自主决定 | "auto" |
| `model_preference` | string[] | 优先使用的 OpenRouter 模型关键词 | ["qwen", "deepseek"] |
| `language` | string | 写作语言，"zh-CN" / "en-US" | "zh-CN" |

### 9.2 项目执行中可调整的超参数
| 参数 | 生效时机 | 说明 |
|------|---------|------|
| `word_count_range` | 下一章生效 | 可随时调整 |
| `model_preference` | 下一个 LLM 调用生效 | 可随时调整 |
| Workflow 控制 | 立即生效 | 暂停/继续/停止 |

### 9.3 人类不可调整的内容
以下内容完全由 AI 自主决定，人类**不得**在前端直接修改：
- 角色设定、关系、性格、动机。
- 剧情线、事件、章节大纲。
- 章节正文内容。
- 世界观设定。
- 图数据库中的实体和关系。

---

## 十、全链路可靠性保障

### 10.1 错误处理机制
1. **工具调用失败**：单次失败自动重试（最多 3 次，间隔 2s/4s/8s 指数退避），3 次后触发 Interrupt 通知人类。
2. **LLM 调用失败**：自动切换到备用模型（通过 OpenRouter 的 fallback 机制），最多切换 3 次。
3. **图数据库写入失败**：先写入 SQLite 作为持久化保证，后续异步同步到 Neo4j。
4. **Redis 状态丢失**：定期从 PostgreSQL 重建运行时状态（每 60 秒同步一次）。

### 10.2 执行轨迹完整性
1. 所有 Task → TaskStep → TaskLog 形成完整的执行轨迹链。
2. 每一步 Tool 调用的输入/输出完整记录在 `tool_trace` 字段中（JSON 格式）。
3. 每次 LLM 调用的 prompt / completion 完整记录在 `reasoning_trace` 字段中。
4. 所有 Workflow 的计划、执行、结果完整写入 `cache-memory/workflow_logs/` 目录下的 .md 文件。

### 10.3 幂等性保证
1. Workflow 支持从中断点恢复执行（通过 Redis 运行时状态）。
2. 同一章节的重复执行不会创建重复数据（通过 `chapter_no` + `project_id` 联合唯一键查重）。
3. 图数据库的 upsert 操作（已有实现）保证重复执行不产生重复节点。
4. 每个 Workflow 在 Redis 中存储 `workflow_execution_id`，相同 ID 的重复触发直接返回已有结果。

### 10.4 监控告警
1. Workflow 执行时间超过阈值（如 30 分钟无进展）自动告警。
2. 连续 5 次 LLM 调用失败自动暂停并告警。
3. 告警通过前端顶部状态栏红色闪烁 + 日志面板红色条目展示。

---

## 十一、技术实现优先级

| 优先级 | 模块 | 依赖关系 | 说明 |
|-------|------|---------|------|
| **P0** | LangGraph + ReAct + Plan-and-Execute 框架搭建 | 无 | 所有 Workflow 的基座，独立模块 |
| **P0** | 工具注册机制（10 类工具实现） | P0 框架 | AI 自主决策的基础能力 |
| **P0** | WF-01 热点发现与灵感生成 | P0 框架 + 工具 | 业务链路的起点 |
| **P0** | 前端工作流监控台（6 个功能区域 + 顶部状态栏） | P0 框架 | 核心监控页面 |
| **P1** | WF-02 世界观与角色构建 | WF-01 | 依赖 WF-01 的输出 |
| **P1** | WF-05 实体关系提取与图入库 | P0 框架 + 工具 | 贯穿全流程，独立可测试 |
| **P1** | 图数据库可视化升级（D3.js Force-Directed） | 无 | 独立模块，可并行开发 |
| **P2** | WF-03 章节大纲规划 | WF-02 | 依赖 WF-02 的输出 |
| **P2** | WF-04 章节写作执行 | WF-03 | 依赖 WF-03 的输出 |
| **P2** | .md 导出与文件存储 | WF-04 + WF-05 | 输出模块 |
| **P3** | 人类超参数控制面板 | P0 框架 | 交互入口，相对简单 |
| **P3** | 全链路测试与可靠性加固 | 全部 P0-P2 | 质量保障，可最后做 |

---

## 十二、验收标准

### 12.1 功能验收
- [ ] **全自动执行**：从"创建项目 + 设定超参数"到"AI 完成全部章节写作并导出 .md 文件"，全过程无需人类参与任何中间决策（除 Interrupt 触发外）。
- [ ] **图谱可视化**：前端图数据库展示具备力导向布局、节点/边差异化渲染、悬停高亮、点击展开、缩放平移等交互效果。
- [ ] **监控台完整性**：工作流监控台能实时看到 Workflow 执行状态、步骤进度（✓/✗/进行中）、工具调用日志、AI 决策历史、正在执行的业务详情。
- [ ] **数据一致性**：PostgreSQL + Neo4j + Redis 三者在每次 Workflow 完成后数据一致。
- [ ] **导出成果**：导出目录结构完整，.md 文件含 YAML Front Matter，可直接用于发布或二次编辑。

### 12.2 技术验收
- [ ] 所有 Workflow 通过 LangGraph StateGraph 实现，非硬编码状态机。
- [ ] 所有工具通过 LangGraph ToolNode 注册，AI 可自主选择调用。
- [ ] ReAct 循环中 AI 的 Thought / Action / Observation 完整记录在数据库中。
- [ ] Workflow 支持从中断点恢复（幂等性）。
- [ ] 前端每个组件在无后端数据时能正常渲染空态/加载态/错误态。

### 12.3 测试验收
- [ ] 每个 Workflow 有对应的集成测试用例（正常流程 + 异常流程）。
- [ ] 每个工具类函数有对应的单元测试。
- [ ] 前端每个页面/组件有渲染测试（Vitest + React Testing Library）。

---

## 十三、关键文件参考

| 文件路径 | 说明 |
|---------|------|
| `backend/app/services/react_executor_service.py` | 当前硬编码 ReAct 执行器，需要替换为 LangGraph |
| `backend/app/services/graph_service.py` | 现有图数据库同步服务，新增的工具函数基于此扩展 |
| `backend/app/services/task_service.py` | 任务创建服务，已完整 |
| `backend/app/services/task_runtime_service.py` | Redis 运行时状态，已完整 |
| `backend/app/models/ai_task.py` | AITask 和 TaskStep 数据模型 |
| `backend/app/schemas/ai_task.py` | Pydantic schemas |
| `backend/app/services/openrouter_service.py` | OpenRouter LLM 调用，已完整 |
| `frontend/src/components/GraphStudioView.tsx` | 当前 SVG 图谱，需升级为 D3.js |
| `frontend/src/components/TaskRuntimePanel.tsx` | 当前任务面板，需升级为完整工作流监控台 |
| `frontend/src/types.ts` | 前端 TypeScript 类型定义 |
| `frontend/src/App.tsx` | 前端路由配置 |
| `docker-compose.yml` | 包含 postgres / neo4j / redis / backend / frontend 服务 |
