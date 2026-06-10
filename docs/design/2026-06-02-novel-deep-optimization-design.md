# Novel AI Editor 深度改造设计文档

**日期**: 2026-06-02  
**状态**: 待审批  
**版本**: v1.0

---

## 一、问题诊断

### 当前系统的核心缺陷

1. **线性单章创作**：9步工作流执行完后只生成一章（~4000字），无法持续创作
2. **AI 无自主决策权**：所有步骤都是硬编码的，AI 只是执行者而非规划者
3. **前端体验差**：日志区域不可拖动、字体太小、可视化图表缺乏美感、布局混乱
4. **细节问题**：热点探索结果标题显示"AI自主决定题材"而非实际小说题目

### 已具备的基础设施

- ✅ LangGraph StateGraph（ReAct + Plan-Execute-Replan 循环）
- ✅ WorkflowTool 注册表（11种工具：web_search、llm_generate、extract_entities等）
- ✅ Redis 运行时状态控制（暂停/停止/重试）
- ✅ Neo4j 图数据库（人物关系、故事脉络）
- ✅ ReAct 日志系统（think/act/observe/subagent）

---

## 二、设计方案

### 2.1 多章节循环创作引擎（后端核心）

#### 架构

```
Novel Orchestrator
├── Phase 1: Novel Planner（AI 宏观规划）
│   ├── 分析题材趋势 → 生成小说大纲
│   ├── 目标章节数（用户自定义 或 AI 自主决定）
│   │   ├── 用户选项：短篇(10-30章) / 中篇(30-100章) / 长篇(100-500章) / AI自主
│   │   └── AI 自主：根据题材复杂度、世界观广度、角色数量综合判断
│   ├── 每章主题规划
│   └── 角色弧线设计
│
├── Phase 2: Chapter Executor Loop（循环执行）
│   └── For each chapter until EOF:
│       ├── SubAgent 1: 人物设计（并行）
│       ├── SubAgent 2: 情节设计（并行）
│       ├── SubAgent 3: 世界观检查（并行）
│       ├── ReAct Loop: 章节创作
│       │   ├── Thought → Action → Observation
│       │   ├── 生成章节正文
│       │   └── 一致性检查 → 修订
│       └── 更新 Neo4j 故事脉络
│
└── Phase 3: Novel Reviewer（AI 审校）
    ├── 整体连贯性检查
    ├── 角色一致性验证
    └── 决定是否继续创作或完成（EOF）
```

#### 关键实现

**新增文件**：
- `backend/app/services/novel_orchestrator_service.py` - 总协调器
- `backend/app/services/chapter_loop_service.py` - 章节循环执行器

**核心逻辑**：
```python
def execute_full_novel_workflow(db, project_id, payload):
    # Phase 1: AI 规划整本小说大纲
    novel_outline = ai_plan_novel(db, project_id, payload)
    # novel_outline: {target_chapters: 120, chapters: [{no: 1, theme: "..."}, ...]}
    
    # Phase 2: 循环创作每章
    for chapter_plan in novel_outline["chapters"]:
        result = execute_chapter_loop(db, project_id, chapter_plan)
        if result["eof"]:  # AI 决定提前完成
            break
    
    # Phase 3: AI 审校
    review = ai_review_novel(db, project_id)
    return review
```

**章节循环内部**：
```python
def execute_chapter_loop(db, project_id, chapter_plan):
    # 使用 LangGraph DAG
    # SubAgent 并行：人物设计 + 情节设计 + 世界观检查
    # ReAct 循环：思考 → 生成 → 观察 → 修订
    # 降级策略：失败重试 3 次 → 简化模式 → 跳过
    pass
```

### 2.2 AI 自主决策工具链

#### NVIDIA API 速率限制

**约束**：NVIDIA API 官方限制为 **每分钟 40 次调用**（约 1.5 秒/次）。

**缓解策略**：
1. **请求队列 + 令牌桶**：使用 Redis 实现分布式速率限制器，控制请求频率 ≤ 40/min
2. **批量合并**：将多个小请求合并为一次 LLM 调用（如同时生成多个人物描述）
3. **SubAgent 串行化**：原本并行的 SubAgent 在到达速率上限时自动排队串行执行
4. **降级策略**：当检测到 429 Too Many Requests 时，自动等待 60 秒后重试
5. **本地缓存**：重复的查询（如相同角色的一致性检查）结果缓存，减少 API 调用

**实现**：
```python
# backend/app/services/rate_limiter.py
class NVIDIARateLimiter:
    """令牌桶速率限制器，限制 40 次/分钟"""
    MAX_CALLS_PER_MINUTE = 40
    
    async def acquire(self):
        # 从 Redis 获取当前分钟调用计数
        # 如果 >= 40，等待到下一分钟
        # 否则原子递增计数
        pass
```

#### 工具渐进式披露

AI 不是接收所有工具，而是根据当前任务阶段动态获取：

| 阶段 | 可用工具 | 预估调用次数 |
|------|---------|-------------|
| 规划 | web_search, llm_generate, query_graph | ~5-8 |
| 每章创作 | llm_generate, query_graph, extract_entities, check_consistency | ~15-25 |
| 每章修订 | llm_generate, check_consistency, query_sqlite | ~5-10 |
| 导出 | export_chapter_md, export_project_archive | ~2 |

**每章预估**：约 20-35 次 API 调用，按 40/min 限制，每章需 0.5-1 分钟。
**100 章预估**：约 50-60 分钟完成整本小说。

#### 工具 Schema 设计

每个工具包含：
- `name`: 工具名
- `description`: 功能描述（AI 理解用）
- `input_schema`: JSON Schema 输入格式
- `output_schema`: 输出格式
- `category`: 分类（search/llm/graph/file/analysis）

### 2.3 前端深度优化

#### 2.3.1 布局重构

**问题**：当前布局固定、不可拖动、字体太小

**方案**：
1. **AI 执行流程面板** - 改为可折叠、可拖动高度的面板
2. **底部日志区域** - 添加拖拽手柄，可调整位置（上移到中央或保持在底部）
3. **字体放大** - 表头从 11px → 13px，内容从 12px → 14px
4. **添加全局拖动条** - 日志区域可 resize: both

#### 2.3.2 可视化图表优化

**问题**：D3 力导向图过于简陋，缺乏美感

**方案**：
1. 引入 **Sigma.js** 或 **react-force-graph** 替代原生 D3
2. 添加节点分组动画、关系边渐变、悬停详情卡片
3. 深色主题优化：节点发光效果、关系线高亮
4. 图例面板：显示节点类型颜色映射

#### 2.3.3 细节修正

1. **热点探索标题** - 显示 AI 生成的小说题目而非"AI自主决定题材"
2. **任务完成后的标题更新** - AI 完成整本小说后，提取最佳标题写入 project.name
3. **章节导航** - 添加章节列表视图，支持跳转任意章节
4. **字数统计** - 显示总字数、章节平均字数

---

## 三、实施计划

### 阶段 1：多章节循环创作（后端）

| 步骤 | 内容 | 文件 |
|------|------|------|
| 1.1 | 创建 Novel Orchestrator 服务 | `novel_orchestrator_service.py` |
| 1.2 | 实现 AI 规划整本小说大纲 | AI prompt + 解析 |
| 1.3 | 实现章节循环执行器 | `chapter_loop_service.py` |
| 1.4 | 集成 SubAgent 并行执行 | LangGraph DAG |
| 1.5 | 添加降级策略和重试机制 | 失败处理 |
| 1.6 | 更新 API 端点 | `tasks.py` |

### 阶段 2：前端深度优化

| 步骤 | 内容 | 文件 |
|------|------|------|
| 2.1 | 重构布局（可拖动面板） | `CommandCenter.css` |
| 2.2 | 字体放大和间距优化 | CSS 全局 |
| 2.3 | 可视化图表美化 | `VisualizationTab5Entity.tsx` |
| 2.4 | 细节修正（标题、章节导航） | 多处 |
| 2.5 | 添加章节列表视图 | 新组件 |

### 阶段 3：集成测试

| 步骤 | 内容 |
|------|------|
| 3.1 | 端到端测试：启动创作 → 多章循环 → EOF |
| 3.2 | 前端 UI 测试：拖动、字体、可视化 |
| 3.3 | 错误处理测试：AI 失败重试、降级 |

---

## 四、数据流

```
用户输入主题 → AI Planner 生成大纲 → Chapter Loop 循环执行
                                        ↓
                                    每章: SubAgent 并行 → ReAct 创作 → 一致性检查 → 修订
                                        ↓
                                    更新 PostgreSQL（章节）+ Neo4j（关系图）+ 日志
                                        ↓
                                    AI Reviewer 审校 → 继续 or EOF
                                        ↓
                                    导出整本小说（Markdown + ZIP）
```

---

## 五、风险与缓解

| 风险 | 影响 | 缓解策略 |
|------|------|---------|
| NVIDIA API 40/min 限流 | 请求被拒绝 | 令牌桶限速 + 429 自动退避重试 |
| AI API 额度耗尽 | 创作中断 | 降级策略 + 断点续传 |
| 章节循环死循环 | 无限执行 | 最大章节数限制（默认 500，用户可设置） |
| 前端性能问题 | 卡顿 | 虚拟滚动 + 分页加载 |
| Neo4j 数据膨胀 | 查询慢 | 按 project_id 分区 + 索引优化 |
| 用户设置章节数过少 | 小说太短 | AI 建议最小章节数提醒 |

---

## 六、成功标准

- [ ] AI 能持续创作 50+ 章节（20 万字+），支持用户自定义目标章节数
- [ ] 每章字数 3000-5000 字
- [ ] NVIDIA API 速率限制合规（≤ 40 次/分钟），429 自动退避重试
- [ ] 前端面板可拖动、字体清晰可读
- [ ] 可视化图表美观、交互流畅
- [ ] 失败自动重试、断点续传
- [ ] 整本小说导出为 Markdown + ZIP
- [ ] 创作前用户可选择：短篇/中篇/长篇/AI自主决定
