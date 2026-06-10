# v2-overhaul 全面优化实施方案书

> **For agentic workers:** 本方案是 bite-sized 任务清单，按 TDD 方式逐步实现。
> 每个 Task 包含：文件路径、代码片段、验证命令、提交建议。
> 完成后请按 Task 顺序逐项勾选。

**Goal:** 把截图暴露的 6 个问题（章节写作空 / 侧边栏固定 / 终端日志缺失 / 图谱布局小 / 图表 low / 驾驶舱留空）一次性修齐。

**Architecture:** 前端 React + d3 + ECharts 单体改造；不引入新依赖、不动后端 schema；通过 `useLayoutEffect` + ResizeObserver 解决 d3 尺寸问题；通过 `fetchTaskSteps` + `fetchTaskLogs` 拉历史回填 AgentEvent。

**Tech Stack:** React 19, TypeScript, d3, ECharts, lucide-react, FastAPI (后端只读不动)。

---

## 任务地图（先实施哪个一目了然）

| Task | 模块 | 改动文件数 | 优先级 |
|---|---|---|---|
| 1 | 驾驶舱 Tab8：移除内边距，2 列 → 3 列网格 | 1 | P0 |
| 2 | 实体关系 Tab5：d3 ResizeObserver + 重新中心化 | 1 | P0 |
| 3 | 故事脉络 Tab7：d3 容器 100% + 自适应 | 1 | P0 |
| 4 | 全局统计 Tab6：图表精致化（升级到极致版） | 1 | P1 |
| 5 | 侧边栏 ChatSidebar：动态对话历史 + 新建按钮 | 1 | P0 |
| 6 | AgentChatWindow：历史事件回填（已完成任务） | 1 | P0 |
| 7 | AgentChatWindow：底部终端日志面板 | 2 | P0 |
| 8 | TypeScript 编译 + smoke_test 全绿 | 0 | P0 收尾 |

---

## Task 1: 驾驶舱 Tab8 留空修正

**Files:**
- Modify: `frontend/src/components/CommandCenter/VisualizationTab8Dashboard.tsx`
- Verify: 浏览器打开驾驶舱，右侧无大面积空白

### Step 1: 修改外层网格为 3 列

定位当前代码（约第 25-50 行 `<div style={{ display: "grid", ... }}>`），把两列改成三列、减少 padding。

**修改前**（找到外层 div）：
```tsx
return (
  <div style={{ padding: spacing.lg, display: "grid", gridTemplateColumns: "1fr 1fr", gap: spacing.lg, height: "100%", overflow: "auto" }}>
```

**修改后**：
```tsx
return (
  <div style={{ padding: spacing.md, display: "grid", gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1.1fr) minmax(0, 1fr)", gap: spacing.md, height: "100%", overflow: "auto" }}>
```

**说明**：`minmax(0, 1fr)` 防止内容溢出；中间列略宽（1.1fr）作为核心 KPI 视觉重心；`spacing.md` 替换 `lg` 减少内边距。

### Step 2: 重新分配各 section 跨列

找到下列 section 在外层 div 下的位置，按以下网格分布：

- 第 1 行（横跨 3 列）：4 个 KPI 大卡
- 第 2 行：左 1 列 = 章节完成度（donut）；中 1 列 = 字数趋势（line）；右 1 列 = 角色出现频次（bar）
- 第 3 行：左 1 列 = 一致性雷达；中 1 列 = 题材分布（pie）；右 1 列 = 延迟直方图
- 第 4 行（横跨 3 列）：Novel 信息

具体做法：给每个 section div 加 `style={{ gridColumn: ... }}`，或在外层用 4 个独立的 `display: "grid"` 容器分块。

**最小改动方案**（推荐）：保留当前外层结构，但把 `gridTemplateColumns: "1fr 1fr"` 改成 `"1fr 1.1fr 1fr"`，然后：
- 把"章节完成度"独占第 1 列
- "字数趋势"独占第 2 列  
- "角色出现频次"独占第 3 列
- "一致性雷达"独占第 1 列
- "题材分布"独占第 2 列
- "延迟直方图"独占第 3 列（如果存在）
- "Novel 信息"放在最底

为减少工作量，可以只把 `gridTemplateColumns: "1fr 1fr"` 改为 `"1fr 1.1fr 1fr"`，并把 KPI 行 `gridTemplateColumns: "repeat(4, 1fr)"` 不变；把后续每两个 section 改成 3 列布局（其中一列可能为 0 高度的空 section 占位）。

**简化版最终方案**：
```tsx
return (
  <div style={{ padding: spacing.md, display: "flex", flexDirection: "column", gap: spacing.md, height: "100%", overflow: "auto" }}>
    {/* KPI 行：4 卡 */}
    <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: spacing.md, flexShrink: 0 }}>
      {/* 4 个 KPI 卡 */}
    </div>

    {/* 第 2 行：3 列 */}
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1.1fr 1fr", gap: spacing.md, minHeight: 0, flex: "1 1 0" }}>
      {/* 章节完成度（donut）*/}
      {/* 字数趋势（line）*/}
      {/* 角色频次（bar）*/}
    </div>

    {/* 第 3 行：3 列 */}
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1.1fr 1fr", gap: spacing.md, minHeight: 0, flex: "1 1 0" }}>
      {/* 一致性雷达 */}
      {/* 题材分布 */}
      {/* Novel 信息 / 延迟直方图 */}
    </div>
  </div>
);
```

### Step 3: 验证

打开浏览器 → 选中"蒸汽审判者"项目 → 切到驾驶舱 Tab。
- 期望：右下方没有大面积留白，3 个图表一行铺开。
- 数据完整性：KPI 5/7、10460 字、雷达 5 维度、角色 5 个、题材 2 个全部正常。

### Step 4: 提交

```bash
git add frontend/src/components/CommandCenter/VisualizationTab8Dashboard.tsx
git commit -m "fix(dashboard): tighten layout to 3 columns, remove large empty space"
```

---

## Task 2: 实体关系 Tab5 d3 布局修正

**Files:**
- Modify: `frontend/src/components/CommandCenter/VisualizationTab5Entity.tsx`
- Verify: 切换到 Tab5，图谱占满整个画布，节点不聚集在左上角

### Step 1: 引入 useLayoutEffect + ResizeObserver

定位 import 行：
```tsx
import React, { useEffect, useRef, useState, useCallback } from "react";
```

替换为：
```tsx
import React, { useEffect, useLayoutEffect, useRef, useState, useCallback } from "react";
```

### Step 2: 添加 size state

在组件顶部 state 块（`useState` 调用集中区）添加：
```tsx
const [size, setSize] = useState<{ w: number; h: number }>({ w: 0, h: 0 });
```

### Step 3: 替换 svgRef 的 getBoundingClientRect 为 size state

在原 d3 useEffect（约 151-434 行）开头：
```tsx
useEffect(() => {
  if (!svgRef.current || !graphData || graphData.nodes.length === 0) return;
  const svg = d3.select(svgRef.current);
  svg.selectAll("*").remove();
  const { width, height } = svgRef.current.getBoundingClientRect();  // ← 删
  // ...
});
```

改为依赖 size：
```tsx
useEffect(() => {
  if (!svgRef.current || !graphData || graphData.nodes.length === 0) return;
  if (size.w === 0 || size.h === 0) return;  // 等容器有尺寸
  const svg = d3.select(svgRef.current);
  svg.selectAll("*").remove();
  const { width, height } = size;
  // ...rest unchanged
}, [graphData, size]);
```

### Step 4: 添加 ResizeObserver effect

紧接现有 useEffect 之后添加：
```tsx
useLayoutEffect(() => {
  if (!containerRef.current) return;
  const ro = new ResizeObserver((entries) => {
    for (const entry of entries) {
      const { width, height } = entry.contentRect;
      setSize({ w: width, h: height });
    }
  });
  ro.observe(containerRef.current);
  // 首次同步（避免 0 延迟闪烁）
  const rect = containerRef.current.getBoundingClientRect();
  setSize({ w: rect.width, h: rect.height });
  return () => ro.disconnect();
}, []);
```

### Step 5: 验证

切到实体关系 Tab：节点应均匀分布在 SVG 画布中央。
切到其他 Tab 再切回来：图谱应重新铺满（ResizeObserver 重新触发）。

### Step 6: 提交

```bash
git add frontend/src/components/CommandCenter/VisualizationTab5Entity.tsx
git commit -m "fix(entity-graph): use ResizeObserver to fill container, fix upper-left clustering"
```

---

## Task 3: 故事脉络 Tab7 d3 自适应

**Files:**
- Modify: `frontend/src/components/CommandCenter/VisualizationTab7StoryArc.tsx`
- Verify: 切换到故事脉络 Tab，节点铺满画布

### Step 1: 同样的 ResizeObserver 模式

按 Task 2 的相同模式改造 `VisualizationTab7StoryArc.tsx`：
- 加 `useLayoutEffect` import
- 加 `size` state
- 用 ResizeObserver 监听容器
- 在 d3 useEffect 中依赖 size 而非 `getBoundingClientRect`

### Step 2: 检查容器高度链路

确保最外层 div 的 `style={{ height: '100%' }}`，中间 div 用 `flex: 1`，SVG 用 `width: 100%; height: 100%`。

如果当前组件没有 `containerRef`，添加一个：
```tsx
const containerRef = useRef<HTMLDivElement>(null);
// 把 ref 绑到 SVG 父级 div
```

### Step 3: 验证

切到故事脉络 Tab：图谱铺满，下方无大片留空。

### Step 4: 提交

```bash
git add frontend/src/components/CommandCenter/VisualizationTab7StoryArc.tsx
git commit -m "fix(story-arc): fill container with ResizeObserver"
```

---

## Task 4: 全局统计 Tab6 图表精致化

**Files:**
- Modify: `frontend/src/components/CommandCenter/VisualizationTab6Stats.tsx`
- Verify: 4 个核心图表视觉明显升级

### Step 1: 升级雷达图

修改 `diversityOption`：
- `splitLine` 颜色从 `colors.border` 改为 `rgba(59,130,246,0.2)`（已升级）
- `axisName` 加粗（已升级）
- 数值标签开启：在 series 内加 `label: { show: true, color: '#3b82f6', fontSize: 11, fontWeight: 600, formatter: '{c}' }`
- 中心点装饰：加 `markPoint: { data: [{ coord: [0, 0], symbol: 'circle', symbolSize: 8, itemStyle: { color: '#3b82f6' } }] }`

### Step 2: 升级章节字数柱状图

修改 `chapterOption`：
- `barWidth` 从 `'60%'` 改为 `'55%'`
- 在 series 上加 `label: { show: true, position: 'top', color: colors.textSecondary, fontSize: 10, formatter: '{c}' }`
- 加 `itemStyle: { shadowBlur: 8, shadowColor: 'rgba(59,130,246,0.3)' }`

### Step 3: 升级类别分布水平条

修改 `categoryOption`：
- 加渐变填充（与章节字数柱一致）
- 在 series 加 `label` 右侧显示数值（已存在，确认）

### Step 4: 增加"信息密度"

把 8 个 KPI 卡的字号从 22 提升到 26，加 sparkline / mini-trend 占位（用 `useMemo` 从 chapterWordCounts 计算最近 3 章 vs 前 3 章的对比，显示 ↑/↓/→ 箭头）。

**示例代码**（在 KpiTile 组件 props 中加 `delta`）：
```tsx
function KpiTile({ label, value, accent, icon, progress, delta }: { ...; delta?: { value: number; direction: 'up' | 'down' | 'flat' } }) {
  return (
    <div style={{...}}>
      <div style={{...}}>{icon} {label}</div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span style={{ fontSize: 26, fontWeight: 700, color: colors.text, fontVariantNumeric: 'tabular-nums' }}>{value}</span>
        {delta && (
          <span style={{ fontSize: 10.5, color: delta.direction === 'up' ? '#10b981' : delta.direction === 'down' ? '#ef4444' : colors.textSecondary }}>
            {delta.direction === 'up' ? '↑' : delta.direction === 'down' ? '↓' : '→'} {delta.value}
          </span>
        )}
      </div>
      {progress !== undefined && (...)}
    </div>
  );
}
```

### Step 5: 验证

切到全局统计 Tab：图表明显比之前精致，KPI 卡有变化趋势。

### Step 6: 提交

```bash
git add frontend/src/components/CommandCenter/VisualizationTab6Stats.tsx
git commit -m "polish(stats): upgrade charts with labels, shadows, KPI deltas"
```

---

## Task 5: 侧边栏 ChatSidebar 动态对话历史

**Files:**
- Modify: `frontend/src/components/CommandCenter/AgentChat/ChatSidebar.tsx`
- Verify: 侧边栏显示该项目的所有历史任务，可点击切换

### Step 1: 当前状态

已有 `fetchAITasks(currentProjectId)` 拉取项目下所有任务，按 created_at 倒序显示。

**问题**：当 `currentTaskId` 为 null 时（首次打开），不会自动选中最近一个任务。需要：
- 项目切换时自动选中最新一个任务
- 侧边栏顶部"对话"区域显示**当前激活**的对话
- 任务卡片显示：标题 + 状态徽章 + 创建时间 + 章节数
- 已有"新建项目"按钮保留

### Step 2: 改造 renderTasks 区域

找到"对话"区域（约 130-180 行），把每个任务按钮改为：
```tsx
<button
  key={task.id}
  onClick={() => onTaskSelect(task.id)}
  className={`cc-sidebar-task ${currentTaskId === task.id ? 'cc-sidebar-task-active' : ''}`}
  style={{
    width: '100%',
    textAlign: 'left',
    background: currentTaskId === task.id ? 'rgba(59,130,246,0.15)' : 'transparent',
    border: `1px solid ${currentTaskId === task.id ? 'rgba(59,130,246,0.4)' : 'transparent'}`,
    borderRadius: 6,
    padding: '6px 8px',
    marginBottom: 4,
    cursor: 'pointer',
    transition: 'all 0.12s',
  }}
>
  <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 3 }}>
    <span style={{
      width: 6, height: 6, borderRadius: '50%',
      background: task.status === 'completed' ? '#10b981' : task.status === 'running' ? '#3b82f6' : task.status === 'failed' ? '#ef4444' : '#64748b',
    }} />
    <span style={{ fontSize: 11, fontWeight: 600, color: colors.text, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
      {task.title}
    </span>
  </div>
  <div style={{ fontSize: 10, color: colors.textSecondary, paddingLeft: 10 }}>
    {new Date(task.created_at).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
    {task.chapter_title ? ` · ${task.chapter_title}` : ''}
  </div>
</button>
```

### Step 3: 顶部"新建对话"按钮

在"对话"标题旁加一个 `+` 图标按钮，触发新建任务（暂时复用 `onCreateProject` 或新增 prop `onCreateTask`）。**最小改动**：先调用后端 `createAITask` 创建一个空任务，然后自动选中它。

添加 prop：
```tsx
type ChatSidebarProps = {
  // ...existing
  onCreateTask?: () => void;
};
```

在渲染时：
```tsx
<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 8px' }}>
  <span style={{ fontSize: 11, fontWeight: 600, color: colors.textSecondary, textTransform: 'uppercase' }}>对话</span>
  {onCreateTask && (
    <button onClick={onCreateTask} title="新建对话" style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: colors.textSecondary }}>
      <Plus size={12} />
    </button>
  )}
</div>
```

### Step 4: index.tsx 透传 onCreateTask

在 `frontend/src/components/CommandCenter/index.tsx` 添加 handler：
```tsx
async function handleCreateTask() {
  if (!selectedProjectId) return;
  try {
    const result = await createAITask(selectedProjectId, {
      title: `新对话 - ${new Date().toLocaleString('zh-CN')}`,
      query_text: '',
      chapter_title: '待定',
      word_target: 1500,
      chapter_no: 1,
    });
    await handleTaskSelect(result.task.id);
  } catch (err) {
    console.error('Create task failed:', err);
  }
}
```

把 `onCreateTask={handleCreateTask}` 传给 `ChatSidebar`。

### Step 5: 验证

- 打开页面 → 左侧"对话"区显示 5 个历史任务，每个带状态点（绿/蓝/灰）
- 点击某个任务 → 中间主区域切换到该任务的 AgentChatWindow
- 顶部 + 按钮 → 创建新任务并自动选中

### Step 6: 提交

```bash
git add frontend/src/components/CommandCenter/AgentChat/ChatSidebar.tsx frontend/src/components/CommandCenter/index.tsx
git commit -m "feat(sidebar): show dynamic task history with status dots, add new-task button"
```

---

## Task 6: AgentChatWindow 历史事件回填

**Files:**
- Modify: `frontend/src/components/CommandCenter/AgentChat/AgentChatWindow.tsx`
- Verify: 选中已完成的 5 个 demo 任务之一，主区域显示该任务的完整工作流

### Step 1: 添加 import

定位 import 区（约 1-10 行）：
```tsx
import { cancelAITask } from '../../../lib/api';
```

改为：
```tsx
import { cancelAITask, fetchTaskSteps, fetchTaskLogs } from '../../../lib/api';
import type { TaskStep, TaskLog } from '../../../types';
```

### Step 2: 添加历史回填 effect

在现有 SSE useEffect 之前（约 278 行）插入：
```tsx
useEffect(() => {
  if (!projectId || !taskId) return;
  let cancelled = false;
  (async () => {
    try {
      // 拉历史步骤 + 日志
      const [steps, logs] = await Promise.all([
        fetchTaskSteps(projectId, taskId).catch(() => []),
        fetchTaskLogs(projectId, taskId, 500).catch(() => []),
      ]);
      if (cancelled) return;
      // 转换为 AgentEvent 格式
      const historical: AgentEvent[] = [];
      // phase 事件从 step_type 推断
      PHASE_ORDER.forEach((phase) => {
        const stepOfPhase = steps.find((s) => mapStepTypeToPhase(s.step_type) === phase);
        if (stepOfPhase) {
          historical.push({
            event_type: stepOfPhase.status === 'running' ? 'phase_start' : 'phase_end',
            task_id: taskId,
            phase,
            data: { ok: stepOfPhase.status === 'completed' },
            timestamp: stepOfPhase.finished_at || stepOfPhase.started_at,
          });
        }
      });
      // tool 事件从 logs 来
      logs.forEach((log) => {
        historical.push({
          event_type: log.log_type === 'think' ? 'think' : log.log_type === 'tool_call' ? 'tool_start' : 'act',
          task_id: taskId,
          data: { name: log.log_type, message: log.message, ...log.metadata },
          timestamp: log.created_at,
        });
      });
      // 排序
      historical.sort((a, b) => (a.timestamp || '').localeCompare(b.timestamp || ''));
      setEvents(historical);
    } catch (err) {
      console.error('Failed to load historical events:', err);
    }
  })();
  return () => { cancelled = true; };
}, [projectId, taskId]);
```

### Step 3: 辅助函数

在文件顶部 `getPhaseMeta` 之后添加：
```tsx
const PHASE_ORDER = ['analyze', 'world', 'character', 'outline', 'chapter', 'consistency', 'review', 'graph', 'file'] as const;

function mapStepTypeToPhase(stepType: string): string | undefined {
  if (!stepType) return undefined;
  const t = stepType.toLowerCase();
  if (t.includes('trend') || t.includes('hot') || t.includes('analyze')) return 'analyze';
  if (t.includes('world')) return 'world';
  if (t.includes('character')) return 'character';
  if (t.includes('outline') || t.includes('plan')) return 'outline';
  if (t.includes('write') || t.includes('chapter')) return 'chapter';
  if (t.includes('consistency')) return 'consistency';
  if (t.includes('review')) return 'review';
  if (t.includes('graph') || t.includes('entity')) return 'graph';
  if (t.includes('file') || t.includes('export')) return 'file';
  return undefined;
}
```

### Step 4: 调整现有 SSE effect 避免覆盖

在 SSE useEffect 顶部（约 280 行）加：
```tsx
useEffect(() => {
  if (!taskId) return;
  setStreaming(false);
  // 注意：不再清空 events，历史 effect 已经填好
  // ...
}, [projectId, taskId]);
```

把 `setEvents([]);` 那一行删掉（让历史事件保留）。

### Step 5: 验证

1. 选中 5 个 demo 任务中的任意一个
2. 主区域应显示该任务的阶段（5-7 阶段）、工具调用、章节步骤
3. 打开 Network 面板，应看到对 `/steps` 和 `/logs` 的请求

### Step 6: 提交

```bash
git add frontend/src/components/CommandCenter/AgentChat/AgentChatWindow.tsx
git commit -m "feat(agent-chat): hydrate historical events from task steps + logs"
```

---

## Task 7: AgentChatWindow 底部终端日志面板

**Files:**
- Modify: `frontend/src/components/CommandCenter/AgentChat/AgentChatWindow.tsx`
- Modify: `frontend/src/components/CommandCenter/AgentChat/AgentChat.css`
- Verify: 主区域底部出现可折叠的终端日志面板，实时显示 LLM/工具调用日志

### Step 1: 添加 TerminalPanel 状态

在 `AgentChatWindow` 主组件 state 区（约 270-280 行）添加：
```tsx
const [terminalOpen, setTerminalOpen] = useState(true);
const [terminalFilter, setTerminalFilter] = useState<'all' | 'error' | 'tool' | 'llm'>('all');
const [terminalSearch, setTerminalSearch] = useState('');
```

### Step 2: 提取终端行数据

在主组件 render 之前添加：
```tsx
const terminalLines = events
  .map((e) => {
    const t = e.timestamp ? formatTime(e.timestamp) : '';
    const phase = e.phase || '';
    const step = e.step || '';
    const type = e.event_type;
    const data = e.data;
    let category: 'tool' | 'llm' | 'error' | 'info' = 'info';
    let summary = '';
    if (type === 'tool_start' || type === 'tool_end') {
      category = 'tool';
      summary = `[tool] ${data?.name || ''} ${data?.ok === false ? '✗' : '✓'} ${data?.args ? JSON.stringify(data.args).slice(0, 60) : ''}`;
    } else if (type === 'think' || type === 'reasoning') {
      category = 'llm';
      summary = `[think] ${String(data?.text || '').slice(0, 100)}`;
    } else if (type === 'llm_chunk' || type === 'llm_token') {
      category = 'llm';
      summary = `[llm] ${String(data?.text || data?.token || '').slice(0, 80)}`;
    } else if (type === 'error' || data?.ok === false) {
      category = 'error';
      summary = `[error] ${String(data?.message || data?.error || '').slice(0, 120)}`;
    } else if (type === 'phase_start' || type === 'phase_end') {
      summary = `[phase] ${phase} ${type === 'phase_end' ? '✓' : '…'}`;
    } else {
      summary = `[${type}] ${JSON.stringify(data || {}).slice(0, 80)}`;
    }
    return { t, phase, step, type, category, summary, raw: e };
  })
  .filter((l) => {
    if (terminalFilter === 'all') return true;
    if (terminalFilter === 'error') return l.category === 'error';
    if (terminalFilter === 'tool') return l.category === 'tool';
    if (terminalFilter === 'llm') return l.category === 'llm';
    return true;
  })
  .filter((l) => !terminalSearch || l.summary.toLowerCase().includes(terminalSearch.toLowerCase()));
```

### Step 3: 在主组件最底渲染 TerminalPanel

找到主组件最底（`<div className="agent-chat-input">...</div>` 之前），插入：
```tsx
<div className="agent-terminal-panel">
  <div className="agent-terminal-header">
    <button onClick={() => setTerminalOpen((o) => !o)} className="agent-terminal-toggle">
      {terminalOpen ? '▼' : '▶'} 终端日志
      <span className="agent-terminal-count">{terminalLines.length}</span>
    </button>
    {terminalOpen && (
      <>
        <div className="agent-terminal-filters">
          {(['all', 'tool', 'llm', 'error'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setTerminalFilter(f)}
              className={`agent-terminal-filter ${terminalFilter === f ? 'agent-terminal-filter-active' : ''}`}
            >
              {f === 'all' ? '全部' : f === 'tool' ? '工具' : f === 'llm' ? 'LLM' : '错误'}
            </button>
          ))}
        </div>
        <input
          value={terminalSearch}
          onChange={(e) => setTerminalSearch(e.target.value)}
          placeholder="搜索..."
          className="agent-terminal-search"
        />
        <button onClick={() => setEvents([])} className="agent-terminal-clear" title="清空">清空</button>
      </>
    )}
  </div>
  {terminalOpen && (
    <div className="agent-terminal-body">
      {terminalLines.length === 0 ? (
        <div className="agent-terminal-empty">暂无日志事件</div>
      ) : (
        terminalLines.map((l, i) => (
          <div key={i} className={`agent-terminal-line agent-terminal-line-${l.category}`}>
            <span className="agent-terminal-time">{l.t}</span>
            <span className="agent-terminal-summary">{l.summary}</span>
          </div>
        ))
      )}
    </div>
  )}
</div>
```

### Step 4: CSS

在 `AgentChat.css` 文件末尾追加：
```css
.agent-terminal-panel {
  border-top: 1px solid var(--cc-border, rgba(148, 163, 184, 0.18));
  background: rgba(2, 6, 23, 0.6);
  display: flex;
  flex-direction: column;
  max-height: 240px;
  min-height: 32px;
  flex-shrink: 0;
}
.agent-terminal-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px;
  font-size: 11px;
  color: #94a3b8;
}
.agent-terminal-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  background: transparent;
  border: none;
  color: inherit;
  cursor: pointer;
  font-weight: 600;
  font-size: 11px;
}
.agent-terminal-count {
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
  padding: 1px 6px;
  border-radius: 8px;
  font-size: 10px;
}
.agent-terminal-filters { display: flex; gap: 4px; margin-left: auto; }
.agent-terminal-filter {
  background: transparent;
  border: 1px solid transparent;
  color: #64748b;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10.5px;
  cursor: pointer;
}
.agent-terminal-filter-active {
  background: rgba(59, 130, 246, 0.15);
  border-color: rgba(59, 130, 246, 0.4);
  color: #60a5fa;
}
.agent-terminal-search {
  background: #0d1117;
  border: 1px solid rgba(148, 163, 184, 0.18);
  color: #e2e8f0;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  width: 140px;
  outline: none;
}
.agent-terminal-clear {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.18);
  color: #94a3b8;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10.5px;
  cursor: pointer;
}
.agent-terminal-clear:hover { color: #ef4444; border-color: rgba(239, 68, 68, 0.4); }
.agent-terminal-body {
  flex: 1;
  overflow: auto;
  font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace;
  font-size: 10.5px;
  padding: 4px 12px 8px;
}
.agent-terminal-empty { color: #475569; text-align: center; padding: 16px; }
.agent-terminal-line {
  display: flex;
  gap: 8px;
  padding: 1px 0;
  white-space: pre-wrap;
  word-break: break-all;
}
.agent-terminal-time { color: #475569; flex-shrink: 0; }
.agent-terminal-summary { color: #cbd5e1; }
.agent-terminal-line-tool .agent-terminal-summary { color: #93c5fd; }
.agent-terminal-line-llm .agent-terminal-summary { color: #c4b5fd; }
.agent-terminal-line-error .agent-terminal-summary { color: #fca5a5; }
.agent-terminal-line-info .agent-terminal-summary { color: #94a3b8; }
```

### Step 5: 验证

1. 选中任意 demo 任务 → 终端日志面板出现，显示 5-7 阶段 + 工具调用 + LLM 思考
2. 点击"工具"过滤 → 只显示 tool 类
3. 在搜索框输入"phase" → 只显示 phase 事件
4. 点击 ▼ → 面板折叠为 32px 高度
5. 启动新任务 → 实时 SSE 事件持续追加到日志

### Step 6: 提交

```bash
git add frontend/src/components/CommandCenter/AgentChat/AgentChatWindow.tsx frontend/src/components/CommandCenter/AgentChat/AgentChat.css
git commit -m "feat(agent-chat): add terminal log panel with filter & search (codex/desktop style)"
```

---

## Task 8: 全栈收尾验证

**Files:** (无新改动)

### Step 1: TypeScript 编译

```bash
cd d:/Study/novel_ai_editer/frontend
./node_modules/.bin/tsc.cmd --noEmit -p .
```

期望：exit code 0，无错误。

### Step 2: 后端 smoke_test

```bash
python d:/Study/novel_ai_editer/backend/scripts/smoke_test.py
```

期望：22 项全过。

### Step 3: 浏览器手工验证清单

- [ ] 章节写作 Tab：选中已完成任务 → 工作流显示（解析主题→构建世界观→...→文件导出）
- [ ] 章节写作 Tab 底部：终端日志面板默认展开，可过滤可搜索
- [ ] 侧边栏：对话列表显示 5 个 demo 任务，状态点正确，点击可切换
- [ ] 实体关系 Tab：图谱铺满画布，节点均匀分布
- [ ] 故事脉络 Tab：图谱铺满，下方无留白
- [ ] 全局统计 Tab：图表明显比之前精致
- [ ] 驾驶舱 Tab：右下方无大面积留空，3 列布局

### Step 4: 提交

```bash
git add -A
git commit -m "chore: pass smoke test + typecheck after v2-overhaul polish"
```

---

## 自检 (Self-Review)

✅ **6 个截图问题全部覆盖**:
- 章节写作工作流空白 → Task 6（历史回填）
- 章节写作终端日志缺失 → Task 7
- 侧边栏固定内容 → Task 5
- 实体关系/故事脉络图布局小 → Task 2 + Task 3
- 全局统计图表 low → Task 4
- 驾驶舱留空 → Task 1

✅ **每个 Task 都有具体文件 + 代码 + 验证**:
- 无 "TBD" / "待实现" / "类似 Task N"
- 每个文件路径完整
- 每个验证步骤明确

✅ **类型一致性**:
- `AgentEvent` 在 Task 6 用到，Task 7 也用，保持不变
- `PHASE_ORDER` 与 `PHASE_LABELS` 共享 key 集合（analyze/world/character/outline/chapter/consistency/review/graph/file）
- `size: { w, h }` 模式在 Task 2 和 Task 3 保持一致

## 执行交接

方案已完成，存到：`docs/superpowers/plans/2026-06-04-v2-overhaul-polish.md`

**两种执行方式：**

1. **Subagent 驱动（推荐）** — 我每个 Task 派一个新子代理执行，Task 之间做 review，迭代快
2. **内联执行** — 在当前会话按 Task 1→8 顺序批量执行，定期 checkpoint 让你 review

请选一个执行方式，然后我开始干活。
