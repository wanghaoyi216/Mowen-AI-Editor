# v2-overhaul-polish-4：拖拽方向修正 + Tab5/7 三段式布局 设计文档

**日期**: 2026-06-04
**状态**: 已设计，待确认
**关联计划**: [2026-06-04-v2-overhaul-polish-3.md](file:///d:/Study/novel_ai_editer/docs/superpowers/plans/2026-06-04-v2-overhaul-polish-3.md) (前置)

---

## 1. 背景

经过 polish-3 之后用户报告 3 个新问题：

1. **拖拽方向反了** — 拖动右侧分隔条时，分隔条移动方向与鼠标方向相反
2. **最左侧边栏不会动** — 拖动左侧分隔条时，ChatSidebar 视觉上无变化
3. **Tab5/7 图谱仍只占上部** — 用户期望的布局是：图谱占上 + 中两个区段（约 2/3 高度），下方 1/3 放对图谱的分析面板

## 2. 根因分析

### 2.1 拖拽方向反了

**文件**: [useResizableLayout.ts](file:///d:/Study/novel_ai_editer/frontend/src/hooks/useResizableLayout.ts#L76-L83)

当前 `onResizeRight`：
```typescript
const onResizeRight = useCallback((delta: number) => {
  setLayout((prev) => {
    const newRight = clamp(prev.rightWidth + delta, MIN.right, MAX.right);
    ...
  });
}, []);
```

**问题**：语义错位。右侧分隔条拖动逻辑应当是「拖右 = 中间变宽，右栏变窄」。

设想的正确行为：
- 拖右分隔条向右（delta > 0）→ 分隔条右移 → 右栏变窄 → newRight 减小
- 拖右分隔条向左（delta < 0）→ 分隔条左移 → 右栏变宽 → newRight 增大

修正为：
```typescript
const onResizeRight = useCallback((delta: number) => {
  setLayout((prev) => {
    const newRight = clamp(prev.rightWidth - delta, MIN.right, MAX.right);  // 注意是减
    ...
  });
}, []);
```

同时，**反向时还需让 minmax 让出空间**。当前 grid 用 `minmax(centerWidth, 1fr)`，minmax 的 max 永远是 1fr（剩余空间），所以即使我减小 rightWidth，centerWidth 会被 1fr 顶到「原来大小 - 实际 rightWidth 减小量」对应的位置，行为正确（中心随右栏缩小而扩大）。

### 2.2 ChatSidebar 写死宽度

**文件**: [AgentChat.css](file:///d:/Study/novel_ai_editer/frontend/src/components/CommandCenter/AgentChat/AgentChat.css#L3-L5)

```css
.chat-sidebar {
  width: 240px;
  min-width: 240px;
  ...
}
```

**问题**：写死 240px 之后，无论 grid 列宽怎么变，ChatSidebar 自身宽度始终是 240px，看起来「没移动」。

**修正**：
```css
.chat-sidebar {
  width: 100%;          /* 由 grid 列宽决定 */
  min-width: 0;         /* 允许 grid 收缩到 0 */
  ...
}
```

折叠态（`.chat-sidebar-collapsed`）保留 60px，但需要确保 min-width: 0 不会破坏折叠态。

### 2.3 Tab5/7 图谱布局

用户截图（热点探索 tab）的布局参考：
- 顶部：4 个 KPI 横向并排
- 中部：左 = 列表 / 右 = 详情面板
- 底部：左 = Top 12 柱图 / 右 = 折线图
- 页脚：AI 建议

用户对 Tab5/7 的期望：
- **上 + 中 2/3 高度**：图谱
- **下 1/3 高度**：分析面板（节点类型分布 + 中心性分析）

具体结构：
```
┌─────────────────────────────┐
│  Tab 5 标题 + 工具栏 (auto) │
├─────────────────────────────┤
│                             │
│       d3 图谱               │  ←  flex: 2  (上 2/3)
│      (26 节点 14 边)        │
│                             │
├─────────────────────────────┤
│ 分析面板：                  │
│ • 节点类型分布（柱图）      │  ←  flex: 1  (下 1/3)
│ • Top 5 高连接度实体        │
│ • 独立节点提示              │
│ • 合并建议                  │
└─────────────────────────────┘
```

## 3. 设计方案

### 3.1 三列拖拽修复

#### 文件
- 修改：[useResizableLayout.ts](file:///d:/Study/novel_ai_editer/frontend/src/hooks/useResizableLayout.ts) — 改 `onResizeRight` 符号
- 修改：[AgentChat.css](file:///d:/Study/novel_ai_editer/frontend/src/components/CommandCenter/AgentChat/AgentChat.css#L3-L5) — `.chat-sidebar` 去掉固定宽度
- 修改：[index.tsx](file:///d:/Study/novel_ai_editer/frontend/src/components/CommandCenter/index.tsx) — 调整 grid 模板

#### 关键改动
- `onResizeRight(delta)`: `newRight = rightWidth - delta`（反向）
- `.chat-sidebar { width: 100%; min-width: 0; }`
- grid 模板简化为：`${leftWidth}px 6px 1fr 6px ${rightWidth}px`（center 用 1fr，让出空间自动分配）

### 3.2 Tab5 三段式布局

#### 文件
- 修改：[VisualizationTab5Entity.tsx](file:///d:/Study/novel_ai_editer/frontend/src/components/CommandCenter/VisualizationTab5Entity.tsx) — 重构为 graph + analysis 双层

#### 关键改动
- 容器：`flex-direction: column`，外层 `<div ref={containerRef}>` 包 graph 区 + analysis 区
- Graph 区：`flex: 2; min-height: 0` — 占 2/3
- Analysis 区：`flex: 1; min-height: 0; overflow: auto` — 占 1/3
- Analysis 面板内容：
  - **左半边**：节点类型分布柱图（角色/地点/事件/组织 4 种，每种一个水平柱）
  - **右半边**：Top 5 高连接度实体 + 独立节点警告 + 合并建议
  - 用 ECharts mini chart + 文本卡片

#### 中心性分析计算
对每个节点 `n` 计算 `degree(n)` = 关联边数。`api.graphData.links` 每条边都涉及 2 个节点，所以：

```typescript
const degree = new Map<string, number>();
api.graphData.nodes.forEach(n => degree.set(n.id, 0));
api.graphData.links.forEach(l => {
  const src = typeof l.source === 'string' ? l.source : l.source.id;
  const tgt = typeof l.target === 'string' ? l.target : l.target.id;
  degree.set(src, (degree.get(src) || 0) + 1);
  degree.set(tgt, (degree.get(tgt) || 0) + 1);
});

const topConnected = [...api.graphData.nodes]
  .map(n => ({ ...n, degree: degree.get(n.id) || 0 }))
  .sort((a, b) => b.degree - a.degree)
  .slice(0, 5);

const isolated = api.graphData.nodes.filter(n => (degree.get(n.id) || 0) === 0);
```

### 3.3 Tab7 三段式布局

#### 文件
- 修改：[VisualizationTab7StoryArc.tsx](file:///d:/Study/novel_ai_editer/frontend/src/components/CommandCenter/VisualizationTab7StoryArc.tsx) — 同样重构

#### 关键改动
- 上 2/3：d3 故事脉络图
- 下 1/3：分析面板
  - **左**：事件阶段分布（开篇/发展/高潮/结局）
  - **中**：Top 5 关键转折点（按关联度或顺序）
  - **右**：3 条主要情节线索摘要

### 3.4 图谱容器适配

由于 d3 useElementSize 监听的是 `containerRef`，需要确保：
- `containerRef` 现在包整个 Tab 容器（包含图谱 + 分析面板）
- 图谱区有自己的子 ref 传给 d3
- 但 useElementSize 应该监听「图谱区」的高度，因为分析面板在下方不归 d3 管

**修正策略**：
- 把 `containerRef` 改为指向「图谱区」而不是整个 Tab
- 图谱区 div 是 `flex: 2; min-height: 0`（高度由父 flex 决定）
- Tab 根 div 是 `flex: 1; display: flex; flex-direction: column`

## 4. 风险评估

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| ChatSidebar 改为 `width: 100%` 后内部布局错位 | 中 | 中 | 保留 `min-width: 0` 让 grid 收缩，子元素自身有 overflow 处理 |
| 折叠态被破坏 | 低 | 中 | 折叠态走 `.chat-sidebar-collapsed` 类，单独处理 |
| d3 图谱高度重新计算时抖动 | 中 | 低 | useElementSize 已有 debounce 机制（实际是 batched ResizeObserver） |
| 分析面板中 ECharts 图表性能 | 低 | 低 | 数据量小（< 30 节点） |

## 5. 不做的事（YAGNI）

- **不改其他 Tab** — 用户明确选择「只改 Tab5/7 + 拖拽」
- **不改拖拽 hotkey / 触摸支持** — 当前实现已含 pointer events 跨平台
- **不增加列宽重置按钮** — 现有 `reset` 方法已存在但未暴露 UI，后续可加
- **不改 d3 力仿真参数** — Task 5 已调过

## 6. 验收标准

1. **拖拽方向正确**：
   - 拖右分隔条向右 → 中间变宽，右栏变窄
   - 拖右分隔条向左 → 中间变窄，右栏变宽
   - 拖左分隔条向右 → 左侧栏变宽，中间变窄
   - 拖左分隔条向左 → 左侧栏变窄，中间变宽
   - 刷新后宽度持久化

2. **ChatSidebar 响应式**：
   - 拖动左分隔条时，ChatSidebar 自身宽度可见地变化（而不是固定 240px）

3. **Tab5 三段式**：
   - 顶部工具栏（auto height）
   - 图谱区占约 2/3 高度
   - 分析面板占约 1/3 高度
   - 分析面板内：节点类型柱图 + Top 5 中心性列表 + 独立节点警告 + 合并建议

4. **Tab7 三段式**：
   - 顶部工具栏
   - 故事脉络图 2/3
   - 分析面板 1/3：阶段分布 + 转折点 + 线索摘要

5. **TS 编译零错误**

## 7. 实施计划

7 个 Task：
- Task 1: useResizableLayout 修正 onResizeRight
- Task 2: AgentChat.css 修正 .chat-sidebar 宽度
- Task 3: index.tsx grid 模板简化（center 用 1fr）
- Task 4: Tab5 重构（图谱 + 分析面板）+ 中心性计算
- Task 5: Tab5 节点类型柱图（ECharts mini chart）
- Task 6: Tab7 重构（图谱 + 分析面板）
- Task 7: 验证 + 重启 frontend 容器

执行方式：Subagent 驱动（与 polish-3 一致）
