# v2-overhaul-polish-3：四 Tab 修复 + 三列可拖拽 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 Tab5/6/7/8 的"白屏/布局问题"，让知识图谱和故事脉络图占满整个空间，驾驶舱布局更舒展，并实现三列（左侧栏 / 中间对话 / 右侧可视化）的手动拖拽分隔条。

**Architecture:**
1. CSS 层修复：`min-height: 0` 链 + `command-center-body` 改 grid/flex 比例 + 拖拽分隔条组件
2. Tab5/Tab7 修复：确保 d3 容器填满父级 + 调整 force 参数避免节点聚集
3. Tab6 修复：Hooks 调用顺序违规 → useMemo 提到顶部 + ECharts markPoint 兼容性
4. Tab8 修复：图表尺寸收缩 + 网格从 3 列降到 2 列 + 间距加大
5. 三列可拖拽：新建 `ResizableSplitter` 组件 + 在 index.tsx 中插两条分隔条 + 用 localStorage 持久化

**Tech Stack:** React 19 + TypeScript + CSS Modules + d3 + ECharts + lucide-react

**前置知识（不熟悉的请先读）：**
- [CommandCenter.css](file:///d:/Study/novel_ai_editer/frontend/src/components/CommandCenter/CommandCenter.css) (line 1-90) - 当前三栏布局
- [index.tsx](file:///d:/Study/novel_ai_editer/frontend/src/components/CommandCenter/index.tsx) (line 580-655) - 渲染根节点
- [VisualizationTab5Entity.tsx](file:///d:/Study/novel_ai_editer/frontend/src/components/CommandCenter/VisualizationTab5Entity.tsx) (line 438-451) - ResizeObserver 实现
- [VisualizationTab6Stats.tsx](file:///d:/Study/novel_ai_editer/frontend/src/components/CommandCenter/VisualizationTab6Stats.tsx) (line 105-141) - 早返回 + useMemo 违规

---

## File Structure

### 新增文件

| 路径 | 职责 |
|---|---|
| `frontend/src/components/CommandCenter/ResizableSplitter.tsx` | 可拖拽竖直分隔条组件，承载 onResize 回调 |
| `frontend/src/components/CommandCenter/ResizableSplitter.css` | 分隔条样式（hover 高亮 + drag cursor） |
| `frontend/src/hooks/useResizableLayout.ts` | 自定义 hook：管理 leftWidth / centerRatio 状态 + localStorage 持久化 |
| `frontend/src/hooks/useElementSize.ts` | 通用 ResizeObserver hook（复用于 d3 容器） |

### 修改文件

| 路径 | 修改内容 |
|---|---|
| `frontend/src/components/CommandCenter/CommandCenter.css` | `.command-center-body` 改为 grid（用 `grid-template-columns: var(--left-w) 1fr var(--right-w)`）；`.cc-main-content` 加 `min-height: 0`；`.cc-main-panel` 加 `min-height: 0`；`.command-center-viz` 加 `min-height: 0` |
| `frontend/src/components/CommandCenter/index.tsx` | 把 `<div className="command-center-body">` 改用 `useResizableLayout`，在两列间插入 `<ResizableSplitter>` |
| `frontend/src/components/CommandCenter/VisualizationTab5Entity.tsx` | 改用 `useElementSize`；去掉外层 `<div height: 100%>` 改用 d3 forceBounds；确保 SVG 真正撑满 |
| `frontend/src/components/CommandCenter/VisualizationTab7StoryArc.tsx` | 同 Tab5 |
| `frontend/src/components/CommandCenter/VisualizationTab6Stats.tsx` | useMemo 提到顶部；删除 `markPoint`；加更明确的 loading 态 |
| `frontend/src/components/CommandCenter/VisualizationTab8Dashboard.tsx` | KPI 网格从 4 列降到 auto-fit 150px；图表网格从 3 列降到 2 列；间距从 12px → 16px；图表高度自适应 |

---

## Task 1：基础设施 - 通用 useElementSize hook

**Files:**
- Create: `frontend/src/hooks/useElementSize.ts`

- [ ] **Step 1: 创建 useElementSize hook**

```typescript
// frontend/src/hooks/useElementSize.ts
import { useEffect, useState, useLayoutEffect, type RefObject } from 'react';

export interface Size {
  width: number;
  height: number;
}

/**
 * 监听 ref 指向元素的尺寸变化，返回 width/height。
 * 首次同步使用 useLayoutEffect 避免 0 延迟闪烁。
 */
export function useElementSize<T extends HTMLElement>(
  ref: RefObject<T | null>
): Size {
  const [size, setSize] = useState<Size>({ width: 0, height: 0 });

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;

    // 首次同步
    const rect = el.getBoundingClientRect();
    setSize({ width: rect.width, height: rect.height });

    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        setSize({ width, height });
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);

  return size;
}
```

- [ ] **Step 2: 验证 TypeScript 编译**

```bash
docker exec novel-ai-editor-frontend npx tsc --noEmit -p tsconfig.json 2>&1 | head -30
```

预期：无非 TS 错误（如果 hooks 目录不在 include 列表中，错误仅限路径不影响运行）。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/hooks/useElementSize.ts
git commit -m "feat(cc): add useElementSize hook for ResizeObserver encapsulation"
```

---

## Task 2：基础设施 - useResizableLayout hook

**Files:**
- Create: `frontend/src/hooks/useResizableLayout.ts`

- [ ] **Step 1: 创建 useResizableLayout hook**

```typescript
// frontend/src/hooks/useResizableLayout.ts
import { useState, useCallback, useEffect } from 'react';

const STORAGE_KEY = 'cc.layout.v1';

interface PersistedLayout {
  leftWidth: number;     // 240 - 400
  centerWidth: number;   // 400 - 1200
  rightWidth: number;    // 400 - 1200
}

const DEFAULTS: PersistedLayout = {
  leftWidth: 260,
  centerWidth: 720,
  rightWidth: 560,
};

const MIN = { left: 200, center: 360, right: 360 };
const MAX = { left: 420, center: 1200, right: 1400 };

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function load(): PersistedLayout {
  if (typeof window === 'undefined') return DEFAULTS;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    const parsed = JSON.parse(raw) as Partial<PersistedLayout>;
    return {
      leftWidth: clamp(parsed.leftWidth ?? DEFAULTS.leftWidth, MIN.left, MAX.left),
      centerWidth: clamp(parsed.centerWidth ?? DEFAULTS.centerWidth, MIN.center, MAX.center),
      rightWidth: clamp(parsed.rightWidth ?? DEFAULTS.rightWidth, MIN.right, MAX.right),
    };
  } catch {
    return DEFAULTS;
  }
}

export interface UseResizableLayoutApi {
  leftWidth: number;
  centerWidth: number;
  rightWidth: number;
  /** 拖左侧分隔条 (chat sidebar <-> center) */
  onResizeLeft: (delta: number) => void;
  /** 拖右侧分隔条 (center <-> visualization) */
  onResizeRight: (delta: number) => void;
  /** 双重置 */
  reset: () => void;
}

export function useResizableLayout(): UseResizableLayoutApi {
  const [layout, setLayout] = useState<PersistedLayout>(load);

  // 持久化
  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(layout));
    } catch {
      // ignore quota errors
    }
  }, [layout]);

  const onResizeLeft = useCallback((delta: number) => {
    setLayout((prev) => {
      const newLeft = clamp(prev.leftWidth + delta, MIN.left, MAX.left);
      // 左侧增加多少，中间就减少多少（保持总宽不变）
      const actualDelta = newLeft - prev.leftWidth;
      const newCenter = clamp(prev.centerWidth - actualDelta, MIN.center, MAX.center);
      return { ...prev, leftWidth: newLeft, centerWidth: newCenter };
    });
  }, []);

  const onResizeRight = useCallback((delta: number) => {
    setLayout((prev) => {
      const newRight = clamp(prev.rightWidth + delta, MIN.right, MAX.right);
      const actualDelta = newRight - prev.rightWidth;
      const newCenter = clamp(prev.centerWidth - actualDelta, MIN.center, MAX.center);
      return { ...prev, rightWidth: newRight, centerWidth: newCenter };
    });
  }, []);

  const reset = useCallback(() => {
    setLayout(DEFAULTS);
  }, []);

  return {
    leftWidth: layout.leftWidth,
    centerWidth: layout.centerWidth,
    rightWidth: layout.rightWidth,
    onResizeLeft,
    onResizeRight,
    reset,
  };
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/hooks/useResizableLayout.ts
git commit -m "feat(cc): add useResizableLayout hook with localStorage persistence"
```

---

## Task 3：基础设施 - ResizableSplitter 组件

**Files:**
- Create: `frontend/src/components/CommandCenter/ResizableSplitter.tsx`
- Create: `frontend/src/components/CommandCenter/ResizableSplitter.css`

- [ ] **Step 1: 创建 ResizableSplitter.tsx**

```tsx
// frontend/src/components/CommandCenter/ResizableSplitter.tsx
import { useCallback, useEffect, useRef, useState } from 'react';
import './ResizableSplitter.css';

interface ResizableSplitterProps {
  /** 拖动时的回调，参数为累计像素 delta（向右为正） */
  onDrag: (delta: number) => void;
  /** 鼠标按下事件回调，可选，用于在拖动时禁用文本选择 */
  onDragStart?: () => void;
  onDragEnd?: () => void;
  /** ARIA label */
  ariaLabel?: string;
}

export function ResizableSplitter({
  onDrag,
  onDragStart,
  onDragEnd,
  ariaLabel = '拖动调整列宽',
}: ResizableSplitterProps) {
  const startXRef = useRef<number>(0);
  const lastDeltaRef = useRef<number>(0);
  const [isDragging, setIsDragging] = useState(false);

  const handlePointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.currentTarget.setPointerCapture(e.pointerId);
      startXRef.current = e.clientX;
      lastDeltaRef.current = 0;
      setIsDragging(true);
      onDragStart?.();
    },
    [onDragStart]
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!isDragging) return;
      const delta = e.clientX - startXRef.current;
      const incremental = delta - lastDeltaRef.current;
      lastDeltaRef.current = delta;
      onDrag(incremental);
    },
    [isDragging, onDrag]
  );

  const stopDrag = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!isDragging) return;
      e.currentTarget.releasePointerCapture(e.pointerId);
      setIsDragging(false);
      lastDeltaRef.current = 0;
      onDragEnd?.();
    },
    [isDragging, onDragEnd]
  );

  useEffect(() => {
    if (!isDragging) return;
    const handleGlobalPointerUp = () => setIsDragging(false);
    window.addEventListener('pointerup', handleGlobalPointerUp);
    return () => window.removeEventListener('pointerup', handleGlobalPointerUp);
  }, [isDragging]);

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={ariaLabel}
      className={`cc-splitter ${isDragging ? 'cc-splitter-active' : ''}`}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={stopDrag}
      onPointerCancel={stopDrag}
    >
      <span className="cc-splitter-grip" />
    </div>
  );
}
```

- [ ] **Step 2: 创建 ResizableSplitter.css**

```css
/* frontend/src/components/CommandCenter/ResizableSplitter.css */
.cc-splitter {
  flex: 0 0 6px;
  width: 6px;
  cursor: col-resize;
  position: relative;
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  user-select: none;
  z-index: 5;
  transition: background 150ms ease;
}

.cc-splitter::before {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(148, 163, 184, 0.06);
  transition: background 150ms ease;
}

.cc-splitter:hover::before,
.cc-splitter-active::before {
  background: rgba(59, 130, 246, 0.18);
}

.cc-splitter-grip {
  position: relative;
  z-index: 1;
  width: 2px;
  height: 28px;
  background: rgba(148, 163, 184, 0.4);
  border-radius: 1px;
  transition: background 150ms ease, height 150ms ease;
}

.cc-splitter:hover .cc-splitter-grip,
.cc-splitter-active .cc-splitter-grip {
  background: rgba(59, 130, 246, 0.8);
  height: 40px;
}

.cc-splitter-active {
  cursor: grabbing;
}

body.dragging-cc-splitter {
  cursor: col-resize !important;
  user-select: none !important;
}
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/CommandCenter/ResizableSplitter.tsx frontend/src/components/CommandCenter/ResizableSplitter.css
git commit -m "feat(cc): add ResizableSplitter component with pointer events"
```

---

## Task 4：CommandCenter 集成 - 三列拖拽

**Files:**
- Modify: `frontend/src/components/CommandCenter/index.tsx:212-214, 233, 580-655`
- Modify: `frontend/src/components/CommandCenter/CommandCenter.css:16-39`

- [ ] **Step 1: 在 index.tsx 中加入拖拽 hook**

修改 `index.tsx` 第 213 行附近（`useProjectContext` 调用之后）：

```typescript
import { useProjectContext } from '../../context/ProjectContext';
// ...
import { useResizableLayout } from '../../hooks/useResizableLayout';
import { ResizableSplitter } from './ResizableSplitter';
```

然后在 `function CommandCenter() {` 内部（约 215 行）添加：

```typescript
  // === v3 新增：三列可拖拽布局 ===
  const { leftWidth, centerWidth, rightWidth, onResizeLeft, onResizeRight } = useResizableLayout();
```

- [ ] **Step 2: 修改 body 布局 JSX**

把第 593-638 行的 `<div className="command-center-body">` 内容替换为：

```tsx
      {/* 三栏布局：左 / 中 / 右，均可拖拽 */}
      <div
        className="command-center-body"
        style={{
          gridTemplateColumns: `${leftWidth}px 6px minmax(${Math.max(centerWidth, 360)}px, 1fr) 6px ${rightWidth}px`,
        }}
      >
        <ChatSidebar
          currentProjectId={selectedProjectId}
          currentTaskId={activeTaskId}
          onProjectSelect={handleProjectChange}
          onTaskSelect={handleTaskSelect}
          onCreateProject={() => setShowCreateModal(true)}
          onCreateTask={handleCreateTask}
          collapsed={sidebarCollapsed}
          onToggleCollapsed={() => setSidebarCollapsed((prev) => !prev)}
        />
        <ResizableSplitter
          ariaLabel="调整左侧栏宽度"
          onDrag={onResizeLeft}
        />
        <div className="command-center-main">
          {selectedProjectId && activeTaskId ? (
            <AgentChatWindow
              projectId={selectedProjectId}
              taskId={activeTaskId}
              taskTitle={activeTask?.title}
              taskStatus={activeTask?.status || 'idle'}
              onTaskChange={() => {
                void doPoll();
              }}
            />
          ) : (
            <div className="command-center-empty">
              <h2>开始你的 AI 小说创作之旅</h2>
              <p>在左侧选择一个项目和对话，或点击下方"启动创作"开始新任务</p>
              <button
                type="button"
                className="primary-button"
                onClick={() => setShowStartModal(true)}
              >
                启动创作
              </button>
            </div>
          )}
        </div>
        <ResizableSplitter
          ariaLabel="调整右侧可视化栏宽度"
          onDrag={onResizeRight}
        />
        <div className="command-center-viz">
          <MainVisualizationPanel
            currentStage={currentStage}
            projectId={selectedProjectId ?? undefined}
          />
        </div>
      </div>
```

- [ ] **Step 3: 修改 CSS 让 body 改用 grid**

修改 [CommandCenter.css](file:///d:/Study/novel_ai_editer/frontend/src/components/CommandCenter/CommandCenter.css#L16-L39)：

```css
.command-center-body {
  flex: 1;
  display: grid;
  /* gridTemplateColumns 已在 index.tsx 通过 inline style 注入 */
  grid-template-rows: 1fr;
  overflow: hidden;
  min-height: 0;
  align-items: stretch;
}

.command-center-main {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  border-right: 1px solid rgba(148, 163, 184, 0.1);
  background: rgba(10, 14, 23, 0.4);
}

.command-center-viz {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.cc-main-panel {
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.cc-main-content {
  flex: 1;
  min-height: 0;        /* 关键：允许 flex 收缩 */
  overflow: auto;
  padding: var(--cc-space-md, 16px);
  display: flex;
  flex-direction: column;
}
```

- [ ] **Step 4: 验证拖拽 HMR 后无报错**

```bash
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:5173/
docker exec novel-ai-editor-frontend npx tsc --noEmit -p tsconfig.json 2>&1 | head -30
```

预期：HTTP 200，TS 错误 ≤ 0（无新增）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/CommandCenter/index.tsx frontend/src/components/CommandCenter/CommandCenter.css
git commit -m "feat(cc): wire up 3-column resizable layout with localStorage persistence"
```

---

## Task 5：Tab5 知识图谱 - 撑满高度

**Files:**
- Modify: `frontend/src/components/CommandCenter/VisualizationTab5Entity.tsx:82-130, 152, 480-560`

- [ ] **Step 1: 把内部 useLayoutEffect 改用 useElementSize hook**

修改 `VisualizationTab5Entity.tsx` 第 84 行附近：

```tsx
import { useElementSize } from '../../hooks/useElementSize';
```

然后在 `function VisualizationTab5Entity` 内部第 84-91 行（hooks 声明区），修改 `size` state 为 hook：

```tsx
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [graphType, setGraphType] = useState<GraphType>("story_entity");
  const [legendOpen, setLegendOpen] = useState(true);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; content: string } | null>(null);
  // 用统一 hook 监听容器尺寸
  const size = useElementSize(containerRef);
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);
```

- [ ] **Step 2: 删除原 useLayoutEffect**

删除第 438-451 行的 useLayoutEffect（已用 useElementSize 替代）。

- [ ] **Step 3: 调整 d3 force 参数让节点分布更均匀**

修改第 243-248 行的 force 仿真：

```ts
    // ── Force simulation ──────────────────────────────────────
    const simulation = d3.forceSimulation(graphData.nodes)
      .force("link", d3.forceLink(graphData.links).id((d: any) => d.id).distance(Math.min(180, width / 6)))
      .force("charge", d3.forceManyBody().strength(-600))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("x", d3.forceX(width / 2).strength(0.05))
      .force("y", d3.forceY(height / 2).strength(0.05))
      .force("collision", d3.forceCollide().radius(50));
```

- [ ] **Step 4: 修改容器高度从 100% → 显式 full**

修改第 481 行（`<div ref={containerRef}>`）：

```tsx
  return (
    <div ref={containerRef} style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', width: '100%' }}>
```

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/CommandCenter/VisualizationTab5Entity.tsx
git commit -m "fix(visualization): Tab5 知识图谱填满容器 + 调整 d3 force 参数"
```

---

## Task 6：Tab7 故事脉络 - 撑满高度

**Files:**
- Modify: `frontend/src/components/CommandCenter/VisualizationTab7StoryArc.tsx` (同 Tab5 套路)

- [ ] **Step 1: 找到容器 ref 和 size state**

```bash
grep -n "containerRef\|setSize\|useLayoutEffect\|ResizeObserver\|width={\|height={" frontend/src/components/CommandCenter/VisualizationTab7StoryArc.tsx | head -30
```

- [ ] **Step 2: 复用 useElementSize hook（与 Tab5 同样模式）**

具体改动同 Task 5，确保：
- 删除原 useLayoutEffect/ResizeObserver
- 改用 `const size = useElementSize(containerRef);`
- 容器从 `height: 100%` 改为 `flex: 1; min-height: 0; width: 100%`
- d3 force 加 `forceX`/`forceY` 弱力

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/CommandCenter/VisualizationTab7StoryArc.tsx
git commit -m "fix(visualization): Tab7 故事脉络填满容器"
```

---

## Task 7：Tab6 全局统计 - 修白屏 + Hooks 顺序

**Files:**
- Modify: `frontend/src/components/CommandCenter/VisualizationTab6Stats.tsx:105-141, 168-193`

- [ ] **Step 1: 把 useMemo 移到早返回之前**

修改 [VisualizationTab6Stats.tsx](file:///d:/Study/novel_ai_editer/frontend/src/components/CommandCenter/VisualizationTab6Stats.tsx#L105-L141)，把 useMemo 提到顶部（在第 102 行 `useEffect` 之后，第 105 行 `if (loading)` 之前）：

```tsx
  // 必须在早返回前定义，否则会违反 Hooks 规则
  const chapterDelta = useMemo(() => {
    if (!stats) return undefined;
    const counts = stats.chapterWordCounts.map((c) => c.wordCount);
    if (counts.length < 4) return undefined;
    const recent = counts.slice(-3);
    const previous = counts.slice(-6, -3);
    if (previous.length === 0) return undefined;
    const recentAvg = recent.reduce((s, v) => s + v, 0) / recent.length;
    const previousAvg = previous.reduce((s, v) => s + v, 0) / previous.length;
    if (previousAvg === 0) return undefined;
    const pct = Math.round(((recentAvg - previousAvg) / previousAvg) * 100);
    if (pct > 0) return { value: pct, direction: 'up' as const };
    if (pct < 0) return { value: Math.abs(pct), direction: 'down' as const };
    return { value: 0, direction: 'flat' as const };
  }, [stats]);
```

然后删除原来第 127-140 行的旧 `chapterDelta` useMemo。

- [ ] **Step 2: 删除有问题的 markPoint**

修改 [VisualizationTab6Stats.tsx](file:///d:/Study/novel_ai_editer/frontend/src/components/CommandCenter/VisualizationTab6Stats.tsx#L168-L193)，把 `diversityOption` 中的 markPoint 段删除：

```tsx
    series: [{
      type: 'radar' as const,
      label: { show: true, color: '#3b82f6', fontSize: 11, fontWeight: 600, formatter: '{c}' },
      data: [{
        value: radarValues,
        name: '项目进度评分',
        areaStyle: {
          color: { type: 'linear' as const, x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(59,130,246,0.45)' },
              { offset: 1, color: 'rgba(59,130,246,0.05)' },
            ] },
        },
        lineStyle: { color: '#3b82f6', width: 2 },
        itemStyle: { color: '#3b82f6' },
        symbol: 'circle',
        symbolSize: 6,
      }],
    }],
```

- [ ] **Step 3: 给空数据态加更明确的提示**

修改第 113-121 行的空态：

```tsx
  if (!stats) {
    return (
      <div style={{ padding: 32, textAlign: 'center', color: colors.textSecondary }}>
        正在加载统计数据…
      </div>
    );
  }

  if (!stats.hasAnyData) {
    return (
      <div style={{ padding: 32, textAlign: 'center', color: colors.textSecondary, height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
        <BarChart3 size={36} style={{ opacity: 0.4 }} />
        <div style={{ fontSize: 16 }}>暂无统计数据</div>
        <div style={{ fontSize: 12, opacity: 0.8 }}>请先选择项目并完成 AI 创作（章节 / 角色 / 世界观 / 热点探索）</div>
      </div>
    );
  }
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/CommandCenter/VisualizationTab6Stats.tsx
git commit -m "fix(visualization): Tab6 修 Hooks 顺序 + 移除 markPoint + 改进空态"
```

---

## Task 8：Tab8 驾驶舱 - 减少密度

**Files:**
- Modify: `frontend/src/components/CommandCenter/VisualizationTab8Dashboard.tsx:1126-1236`

- [ ] **Step 1: 调宽 KPI grid + 调小字号**

修改 [VisualizationTab8Dashboard.tsx](file:///d:/Study/novel_ai_editer/frontend/src/components/CommandCenter/VisualizationTab8Dashboard.tsx#L1128-L1133)：

```tsx
      {/* KPI cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: 14,
        }}
      >
```

- [ ] **Step 2: 图表网格从 3 列降到 2 列 + 加大间距**

修改 [VisualizationTab8Dashboard.tsx](file:///d:/Study/novel_ai_editer/frontend/src/components/CommandCenter/VisualizationTab8Dashboard.tsx#L1164-L1169)：

```tsx
      {/* Chart grid - 两列布局，每张图都有更大空间 */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)',
          gap: 14,
        }}
      >
```

- [ ] **Step 3: 单图高度自适应 + 加 minHeight**

给每个 `.v8-card` 包裹图表的 div 增加 `minHeight: 280`，把饼图/雷达/直方图等高度统一（修改第 1172, 1182, 1192, 1202, 1212, 1222 行的 v8-card）：

```tsx
        <div className="v8-card" style={{ animationDelay: '240ms', minHeight: 320 }}>
```

（每个图表卡片都加 `minHeight: 320`）

- [ ] **Step 4: 减小标题字号和内边距**

修改 padding 从 12 → 16，标题从 24 → 22：

```tsx
      style={{
        padding: 16,
        display: 'flex',
        flexDirection: 'column',
        gap: 14,
        background: theme.bg,
        minHeight: '100%',
        fontFamily: fontStack,
      }}
```

标题：

```tsx
      <div style={{ animation: 'v8-fade-in-up 360ms ease both' }}>
        <div
          style={{
            fontSize: 22,
            fontWeight: 700,
            color: theme.text,
            letterSpacing: -0.4,
          }}
        >
```

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/CommandCenter/VisualizationTab8Dashboard.tsx
git commit -m "refactor(visualization): Tab8 驾驶舱改为 2 列布局 + 加大卡片最小高度"
```

---

## Task 9：验证 + 浏览器硬刷新

**Files:** N/A

- [ ] **Step 1: 重启 frontend 容器清 Vite 缓存**

```bash
docker restart novel-ai-editor-frontend
sleep 5
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:5173/
```

预期：HTTP 200。

- [ ] **Step 2: 验证所有 8 个 Tab 都能加载**

打开浏览器（http://localhost:5173/）：

1. **Tab 5 实体关系** - 节点应均匀分布占满整个右侧栏高度
2. **Tab 6 全局统计** - 不再白屏，KPI 行 + 雷达图 + 双柱图正常显示
3. **Tab 7 故事脉络** - 节点均匀分布占满整个高度
4. **Tab 8 驾驶舱** - 2 列布局，6 张卡片各占 320px 高度，整体更舒展
5. **拖拽测试** - 鼠标 hover 在 ChatSidebar 与对话窗口之间的竖条，应出现蓝色高亮 grip，拖动可改变列宽；刷新页面后宽度保持（localStorage）

- [ ] **Step 3: 浏览器硬刷新（如仍有问题）**

`Ctrl+Shift+R`（Mac: `Cmd+Shift+R`）

- [ ] **Step 4: 最终提交（如果有后续小修）**

```bash
git add -A
git commit -m "chore: polish-3 final tweaks after manual verification"
```

---

## Self-Review

**1. Spec coverage:**
- ✅ Tab5/6/7/8 白屏 / 布局 → Task 5/6/7
- ✅ 知识图谱占满高度 → Task 5
- ✅ 驾驶舱拥挤 → Task 8
- ✅ 三列可拖拽 → Task 3/4
- ✅ 浏览器硬刷新 → Task 9

**2. Placeholder scan:** 无 "TODO" / "TBD" / "fill in details"。

**3. Type consistency:** `useResizableLayout` 返回字段名 (`leftWidth`/`centerWidth`/`rightWidth`) 在 Task 2 定义、Task 4 消费一致。
