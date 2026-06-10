import React, { useEffect, useRef, useState, useCallback, useMemo } from "react";
import * as d3 from "d3";
import * as echarts from "echarts";
import { colors } from "./styles";
import { useElementSize } from "../../hooks/useElementSize";
import { fetchBooks, type Book, type StoryArcNode, type StoryArcEdge, type StoryArcNodeType } from "../../lib/api";
import "./VisualizationTab7StoryArc.css";

// ─── Type definitions ──────────────────────────────────────────────

// StoryArcNode / StoryArcEdge / StoryArcNodeType 已在 lib/api 中统一导出
// 这里只 import，不再重复定义。
// eslint-disable-next-line @typescript-eslint/no-unused-vars
type _UseApiTypes = StoryArcNode | StoryArcEdge;

export type StoryArcRelation =
  | "sequel_to"
  | "leads_to"
  | "conflicts_with"
  | "resolves";

export interface StoryArcStats {
  chapters: number;
  plotLines: number;
  plans: number;
  scenes?: number;
  emotionalArc?: Record<string, number>;
  wordCountByChapter?: Array<{ chapterNo: number; wordCount: number }>;
  orphanScenes?: number;
  generatedAt?: string;
  version?: number;
}

interface VisualizationTab7StoryArcProps {
  nodes: StoryArcNode[];
  edges: StoryArcEdge[];
  /** Optional: 章节 / 剧情线 / 大纲条目统计。空时静默忽略。 */
  stats?: StoryArcStats;
  /** Optional: 传入 projectId 时，组件内部加载书籍列表并展示过滤下拉 */
  projectId?: number;
  /** Optional: 当前选中的 bookId（受控） */
  currentBookId?: number | null;
  /** Optional: 切换 book 时回调（受控时使用） */
  onBookChange?: (bookId: number | null) => void;
  /** Optional: 书籍列表（受控时由父组件传入，避免重复请求） */
  books?: Book[];
  /** Optional: 书籍加载状态 */
  booksLoading?: boolean;
}

// ─── Constants ─────────────────────────────────────────────────────

const TYPE_COLORS: Record<StoryArcNodeType, string> = {
  chapter: "#a78bfa",
  climax: "#c4b5fd",
  turning_point: "#f472b6",
  conflict: colors.error,
  ending: colors.success,
  scene: "#7c3aed",
  plot_line: "#8b5cf6",
};

const TYPE_LABELS: Record<StoryArcNodeType, string> = {
  chapter: "章节",
  climax: "高潮",
  turning_point: "转折点",
  conflict: "冲突",
  ending: "结局",
  scene: "场景",
  plot_line: "剧情线",
};

const RELATION_LABELS: Record<StoryArcRelation, string> = {
  sequel_to: "续接",
  leads_to: "引向",
  conflicts_with: "冲突",
  resolves: "化解",
};

const CLUSTER_THRESHOLD = 200;

// ─── Shape generation helpers ──────────────────────────────────────

/** Generate points for a regular n-gon centered at (0,0). */
function polygonPoints(sides: number, r: number): string {
  const pts: string[] = [];
  for (let i = 0; i < sides; i++) {
    const angle = (Math.PI * 2 * i) / sides - Math.PI / 2;
    pts.push(`${(r * Math.cos(angle)).toFixed(2)},${(r * Math.sin(angle)).toFixed(2)}`);
  }
  return pts.join(" ");
}

/** Five-pointed star centered at (0,0). */
function starPoints(outer: number, inner: number, points = 5): string {
  const pts: string[] = [];
  const step = Math.PI / points;
  for (let i = 0; i < points * 2; i++) {
    const r = i % 2 === 0 ? outer : inner;
    const angle = i * step - Math.PI / 2;
    pts.push(`${(r * Math.cos(angle)).toFixed(2)},${(r * Math.sin(angle)).toFixed(2)}`);
  }
  return pts.join(" ");
}

/** Rounded-rect path with given corner radius. */
function roundedRectPath(x: number, y: number, w: number, h: number, r: number): string {
  const rr = Math.min(r, w / 2, h / 2);
  return `M${x - w / 2 + rr},${y - h / 2}
          H${x + w / 2 - rr}
          Q${x + w / 2},${y - h / 2} ${x + w / 2},${y - h / 2 + rr}
          V${y + h / 2 - rr}
          Q${x + w / 2},${y + h / 2} ${x + w / 2 - rr},${y + h / 2}
          H${x - w / 2 + rr}
          Q${x - w / 2},${y + h / 2} ${x - w / 2},${y + h / 2 - rr}
          V${y - h / 2 + rr}
          Q${x - w / 2},${y - h / 2} ${x - w / 2 + rr},${y - h / 2} Z`;
}

function truncate(s: string, max: number): string {
  return s.length > max ? s.slice(0, max - 1) + "\u2026" : s;
}

// ─── Internal node/edge types used by d3 force simulation ──────────

type SimNode = d3.SimulationNodeDatum & {
  id: string;
  type: StoryArcNodeType;
  label: string;
  chapterNo?: number | null;
  theme?: string;
  radius: number;
  clusterId?: string;
};

type SimLink = d3.SimulationLinkDatum<SimNode> & {
  relation: StoryArcRelation;
  weight: number;
};

// ─── Component ─────────────────────────────────────────────────────

export function VisualizationTab7StoryArc({
  nodes,
  edges,
  stats,
  projectId,
  currentBookId,
  onBookChange,
  books: booksProp,
  booksLoading: booksLoadingProp,
}: VisualizationTab7StoryArcProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  // ⬇️ 用 callback-ref，替代原先普通 ref —— 解决"容器元素被替换后观察丢失"
  const [size, setGraphContainerRef] = useElementSize<HTMLDivElement>();
  const stageChartRef = useRef<HTMLDivElement>(null);
  const emotionChartRef = useRef<HTMLDivElement>(null);
  const wordChartRef = useRef<HTMLDivElement>(null);
  const emotionChartInstance = useRef<any>(null);
  const wordChartInstance = useRef<any>(null);
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; content: string } | null>(null);
  const [legendOpen, setLegendOpen] = useState(true);
  const [zoomLevel, setZoomLevel] = useState(1);
  // Task 8: 书籍过滤（受控 / 非受控二选一）
  const [internalBooks, setInternalBooks] = useState<Book[]>([]);
  const [internalBooksLoading, setInternalBooksLoading] = useState(false);
  const [internalBookId, setInternalBookId] = useState<number | null>(null);

  // 统一受控/非受控状态
  const isControlled = currentBookId !== undefined;
  const books = booksProp ?? internalBooks;
  const booksLoading = booksLoadingProp ?? internalBooksLoading;
  const effectiveBookId = isControlled ? currentBookId : internalBookId;
  const setEffectiveBookId = useCallback(
    (v: number | null) => {
      if (isControlled) {
        onBookChange?.(v);
      } else {
        setInternalBookId(v);
      }
    },
    [isControlled, onBookChange],
  );

  // 非受控模式：自己加载书籍
  useEffect(() => {
    if (isControlled || !projectId) return;
    let cancelled = false;
    async function load() {
      setInternalBooksLoading(true);
      try {
        const list = await fetchBooks(projectId as number);
        if (cancelled) return;
        setInternalBooks(list);
        setInternalBookId((prev) => {
          if (prev != null && list.some((b) => b.id === prev)) {
            return prev;
          }
          return list.length > 0 ? list[0].id : null;
        });
      } catch {
        if (!cancelled) setInternalBooks([]);
      } finally {
        if (!cancelled) setInternalBooksLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, isControlled]);

  const sizeRef = useRef<{ width: number; height: number }>({ width: 0, height: 0 });
  useEffect(() => {
    sizeRef.current = { width: size.width, height: size.height };
  }, [size]);

  // 额外的"warning"色：colors.warning 在 styles.ts 中未定义，这里兜底
  const warningColor = (colors as any).warning ?? "#d97706";

  // clusterMap 同理：内容稳定时引用变化不应触发 d3 重建
  const clusterMapRef = useRef<Map<string, StoryArcNode[]>>(new Map());
  const simulationRef = useRef<d3.Simulation<SimNode, SimLink> | null>(null);
  const rootRef = useRef<d3.Selection<SVGGElement, unknown, null, undefined> | null>(null);
  // 复用上一次 d3 init 创建的 selection，避免数据更新时销毁/重建 DOM 节点
  // （重建会让用户感觉"每隔一秒回到原本效果"——节点位置被重置回中心）
  const linkSelRef = useRef<d3.Selection<SVGPathElement, SimLink, SVGGElement, unknown> | null>(null);
  const edgeLabelSelRef = useRef<d3.Selection<SVGTextElement, SimLink, SVGGElement, unknown> | null>(null);
  const nodeSelRef = useRef<d3.Selection<SVGGElement, SimNode, SVGGElement, unknown> | null>(null);

  // ── Stable data view + cluster collapsing for large graphs ──────
  const { simNodes, simLinks, isClustered, clusterMap } = useMemo(() => {
    const radMap: Record<StoryArcNodeType, number> = {
      chapter: 16,
      climax: 20,
      turning_point: 18,
      conflict: 17,
      ending: 22,
      scene: 9,
      plot_line: 14,
    };

    let workingNodes: SimNode[] = nodes.map((n) => ({
      id: n.id,
      type: n.type,
      label: n.label,
      chapterNo: n.chapterNo,
      theme: n.theme,
      radius: radMap[n.type] ?? 16,
    }));

    let workingLinks: SimLink[] = edges.map((e) => ({
      source: e.source,
      target: e.target,
      relation: e.relation,
      weight: e.weight ?? 1,
    }));

    let clustered = false;
    const map: Map<string, StoryArcNode[]> = new Map();

    if (workingNodes.length > CLUSTER_THRESHOLD) {
      clustered = true;
      // Group by type into a fixed number of clusters per type
      const PER_CLUSTER = 50;
      const grouped: Record<string, SimNode[]> = {};
      workingNodes.forEach((n) => {
        grouped[n.type] = grouped[n.type] || [];
        grouped[n.type].push(n);
      });

      const clusteredNodes: SimNode[] = [];
      const idRemap: Record<string, string> = {};

      Object.entries(grouped).forEach(([type, list]) => {
        if (list.length <= PER_CLUSTER) {
          list.forEach((n) => {
            clusteredNodes.push(n);
            idRemap[n.id] = n.id;
            map.set(n.id, [{
              id: n.id,
              type: n.type,
              label: n.label,
              chapterNo: n.chapterNo,
              theme: n.theme,
            }]);
          });
        } else {
          const bucketCount = Math.ceil(list.length / PER_CLUSTER);
          for (let i = 0; i < bucketCount; i++) {
            const slice = list.slice(i * PER_CLUSTER, (i + 1) * PER_CLUSTER);
            const cid = `cluster-${type}-${i}`;
            const clusterNode: SimNode = {
              id: cid,
              type: type as StoryArcNodeType,
              label: `${TYPE_LABELS[type as StoryArcNodeType]} #${i + 1} (${slice.length})`,
              radius: 26,
              clusterId: cid,
            };
            clusteredNodes.push(clusterNode);
            idRemap[cid] = cid;
            map.set(cid, slice.map((n) => ({
              id: n.id,
              type: n.type,
              label: n.label,
              chapterNo: n.chapterNo,
              theme: n.theme,
            })));
            slice.forEach((n) => {
              idRemap[n.id] = cid;
            });
          }
        }
      });

      // Remap links: collapse intra-cluster links, keep inter-cluster ones
      const linkKeys = new Set<string>();
      const newLinks: SimLink[] = [];
      workingLinks.forEach((l) => {
        const s = idRemap[l.source as string];
        const t = idRemap[l.target as string];
        if (!s || !t) return;
        if (s === t) return; // intra-cluster, hide
        const key = [s, t].sort().join("|||") + "::" + l.relation;
        if (linkKeys.has(key)) return;
        linkKeys.add(key);
        newLinks.push({ source: s, target: t, relation: l.relation, weight: l.weight });
      });
      workingNodes = clusteredNodes;
      workingLinks = newLinks;
    }

    return {
      simNodes: workingNodes,
      simLinks: workingLinks,
      isClustered: clustered,
      clusterMap: map,
    };
  }, [nodes, edges]);

  const hasData = nodes.length > 0;

  // ── Analysis: degree-based key events + top-3 plot threads ──────
  const { keyEvents, threads } = useMemo(() => {
    const degree = new Map<string, number>();
    nodes.forEach((n) => degree.set(n.id, 0));
    edges.forEach((e) => {
      degree.set(e.source, (degree.get(e.source) || 0) + 1);
      degree.set(e.target, (degree.get(e.target) || 0) + 1);
    });
    const sorted = [...nodes]
      .map((n) => ({ ...n, degree: degree.get(n.id) || 0 }))
      .sort((a, b) => b.degree - a.degree);
    const top5 = sorted.slice(0, 5);
    const top3 = sorted.slice(0, 3);
    const threadTexts = top3.map((n) => {
      const related = edges.filter((e) => e.source === n.id || e.target === n.id);
      const typeLabel = TYPE_LABELS[n.type] || n.type;
      return `${n.label || n.id} · ${typeLabel} · 关联 ${related.length} 条关系 (degree ${n.degree})`;
    });
    return { keyEvents: top5, threads: threadTexts };
  }, [nodes, edges]);

  // ── Stage distribution ECharts bar chart ───────────────────────
  // 关键修复：保持 chart 实例复用，setOption 增量更新；不再每次 dispose/init
  const stageChartInstance = useRef<echarts.ECharts | null>(null);
  useEffect(() => {
    if (!stageChartRef.current) return;
    if (!stageChartInstance.current) {
      stageChartInstance.current = echarts.init(stageChartRef.current);
    }
    const chart = stageChartInstance.current;
    if (!hasData) {
      chart.clear();
      return;
    }

    // 统计各 type 的节点数
    const stageCount: Record<string, number> = {};
    nodes.forEach((n) => {
      const t = n.type || "未分类";
      stageCount[t] = (stageCount[t] || 0) + 1;
    });
    // 按 TYPE_LABELS 顺序稳定展示（已知类型优先），未识别归为"未分类"
    const orderedKeys: string[] = [];
    (Object.keys(TYPE_LABELS) as StoryArcNodeType[]).forEach((k) => {
      if (stageCount[k]) orderedKeys.push(k);
    });
    if (stageCount["未分类"]) orderedKeys.push("未分类");
    const entries = orderedKeys.map((k) => [k, stageCount[k]] as [string, number]);

    chart.setOption(
      {
        backgroundColor: 'transparent',
        grid: { top: 8, right: 24, bottom: 8, left: 72, containLabel: false },
        xAxis: {
          type: "value",
          show: false,
        },
        yAxis: {
          type: "category",
          data: entries.map(([k]) => TYPE_LABELS[k as StoryArcNodeType] || k).reverse(),
          axisLabel: { color: colors.textSecondary, fontSize: 11 },
          axisLine: { show: false },
          axisTick: { show: false },
        },
        series: [
          {
            type: "bar",
            data: entries.map(([_, v]) => v).reverse(),
            itemStyle: {
              color: (params: any) => {
                const label = entries[entries.length - 1 - params.dataIndex]?.[0];
                return TYPE_COLORS[label as StoryArcNodeType] || "#7c3aed";
              },
              borderRadius: [0, 3, 3, 0],
            },
            label: {
              show: true,
              position: "right",
              color: colors.textSecondary,
              fontSize: 11,
            },
            barWidth: 12,
          },
        ],
        tooltip: { trigger: "item", backgroundColor: "rgba(255,255,255,0.95)", borderColor: "rgba(58,38,107,0.12)", textStyle: { color: colors.text } },
      },
      { notMerge: false, lazyUpdate: true },
    );

    const handleResize = () => chart.resize();
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      // 组件卸载时才 dispose
    };
  }, [nodes, hasData]);

  useEffect(() => {
    return () => {
      stageChartInstance.current?.dispose();
      stageChartInstance.current = null;
    };
  }, []);

  // ── Emotion distribution ECharts bar chart (SubTask 1.6) ────────
  useEffect(() => {
    if (!emotionChartRef.current) return;
    if (!stats?.emotionalArc || Object.keys(stats.emotionalArc).length === 0) {
      if (emotionChartInstance.current) {
        emotionChartInstance.current.dispose();
        emotionChartInstance.current = null;
      }
      return;
    }

    if (!emotionChartInstance.current) {
      emotionChartInstance.current = echarts.init(emotionChartRef.current);
    }

    const arcColors: Record<string, string> = {
      '悲怆': colors.textSecondary,
      '激昂': '#ef4444',
      '舒缓': '#10b981',
      '起伏': '#f59e0b',
    };

    const data = Object.entries(stats.emotionalArc).map(([name, value]) => ({
      name,
      value,
      itemStyle: { color: arcColors[name] || '#7c3aed' },
    }));

    emotionChartInstance.current.setOption({
      backgroundColor: 'transparent',
      grid: { top: 5, bottom: 5, left: 50, right: 30 },
      xAxis: {
        type: 'value',
        show: false,
      },
      yAxis: {
        type: 'category',
        data: data.map((d) => d.name),
        axisLabel: { color: colors.textSecondary, fontSize: 10 },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      series: [
        {
          type: 'bar',
          data,
          barWidth: 12,
          itemStyle: { borderRadius: [0, 3, 3, 0] },
          label: {
            show: true,
            position: 'right',
            color: colors.text,
            fontSize: 10,
          },
        },
      ],
      tooltip: { trigger: 'item', backgroundColor: 'rgba(255,255,255,0.95)', borderColor: 'rgba(58,38,107,0.12)', textStyle: { color: colors.text } },
    });

    const handleResize = () => emotionChartInstance.current?.resize();
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [stats?.emotionalArc]);

  // ── Word count by chapter ECharts line chart (SubTask 1.7) ──────
  useEffect(() => {
    if (!wordChartRef.current) return;
    if (!stats?.wordCountByChapter || stats.wordCountByChapter.length === 0) {
      if (wordChartInstance.current) {
        wordChartInstance.current.dispose();
        wordChartInstance.current = null;
      }
      return;
    }

    if (!wordChartInstance.current) {
      wordChartInstance.current = echarts.init(wordChartRef.current);
    }

    const sorted = [...stats.wordCountByChapter].sort((a, b) => a.chapterNo - b.chapterNo);
    const chapterData = sorted.map((d) => d.chapterNo);
    const wordData = sorted.map((d) => d.wordCount);

    wordChartInstance.current.setOption({
      backgroundColor: 'transparent',
      grid: { top: 8, bottom: 22, left: 32, right: 8 },
      xAxis: {
        type: 'category',
        data: chapterData,
        axisLabel: { color: 'colors.textSecondary', fontSize: 9 },
        axisLine: { lineStyle: { color: 'rgba(58,38,107,0.2)' } },
        axisTick: { show: false },
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: 'colors.textSecondary', fontSize: 9 },
        splitLine: { lineStyle: { color: 'rgba(58,38,107,0.08)' } },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      series: [
        {
          type: 'line',
          data: wordData,
          smooth: true,
          symbol: 'circle',
          symbolSize: 5,
          itemStyle: { color: colors.accent },
          lineStyle: { color: colors.accent, width: 2 },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(124, 58, 237, 0.35)' },
                { offset: 1, color: 'rgba(124, 58, 237, 0.02)' },
              ],
            },
          },
        },
      ],
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(255,255,255,0.95)',
        borderColor: 'rgba(58,38,107,0.12)',
        textStyle: { color: colors.text },
        formatter: (params: any) => {
          const p = Array.isArray(params) ? params[0] : params;
          return `第${p.axisValue}章：${p.data} 字`;
        },
      },
    });

    const handleResize = () => wordChartInstance.current?.resize();
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [stats?.wordCountByChapter]);

  // ── Zoom controls ──────────────────────────────────────────────
  const zoomIn = useCallback(() => {
    if (svgRef.current && zoomRef.current) {
      d3.select(svgRef.current).transition().duration(300).call(zoomRef.current.scaleBy, 1.4);
    }
  }, []);

  const zoomOut = useCallback(() => {
    if (svgRef.current && zoomRef.current) {
      d3.select(svgRef.current).transition().duration(300).call(zoomRef.current.scaleBy, 1 / 1.4);
    }
  }, []);

  const zoomReset = useCallback(() => {
    if (svgRef.current && zoomRef.current) {
      d3.select(svgRef.current).transition().duration(500).call(zoomRef.current.transform, d3.zoomIdentity);
    }
  }, []);

  // ── D3 init effect：在容器有尺寸 + 有数据时跑，建好 svg/defs/simulation/selection
  // 之后数据更新走下面那个 update effect，**复用** simulation + selection，不重建 DOM。
  // 依赖：hasData 切换 OR 容器尺寸从 0 变 >0 —— 任意一个变化都触发重新初始化。
  useEffect(() => {
    if (!svgRef.current || !hasData) return;
    const { width: rw, height: rh } = sizeRef.current;
    if (rw === 0 || rh === 0) return; // 等容器有尺寸

    clusterMapRef.current = clusterMap;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const W = rw;
    const H = rh;

    // ── Defs (gradients, filters, markers) ──────────────────────
    const defs = svg.append("defs");

    // Glow filter using feGaussianBlur + feMerge (per requirement)
    const glow = defs.append("filter")
      .attr("id", "viz7-node-glow")
      .attr("x", "-60%").attr("y", "-60%")
      .attr("width", "220%").attr("height", "220%");
    glow.append("feGaussianBlur")
      .attr("in", "SourceGraphic")
      .attr("stdDeviation", 3)
      .attr("result", "blur");
    const merge = glow.append("feMerge");
    merge.append("feMergeNode").attr("in", "blur");
    merge.append("feMergeNode").attr("in", "SourceGraphic");

    // Stronger glow for hover
    const glowHover = defs.append("filter")
      .attr("id", "viz7-node-glow-hover")
      .attr("x", "-80%").attr("y", "-80%")
      .attr("width", "260%").attr("height", "260%");
    glowHover.append("feGaussianBlur")
      .attr("in", "SourceGraphic")
      .attr("stdDeviation", 6)
      .attr("result", "blur");
    const mergeH = glowHover.append("feMerge");
    mergeH.append("feMergeNode").attr("in", "blur");
    mergeH.append("feMergeNode").attr("in", "SourceGraphic");

    // Text shadow filter
    const textShadow = defs.append("filter")
      .attr("id", "viz7-text-shadow")
      .attr("x", "-20%").attr("y", "-20%")
      .attr("width", "140%").attr("height", "140%");
    textShadow.append("feGaussianBlur")
      .attr("in", "SourceAlpha")
      .attr("stdDeviation", 1.5)
      .attr("result", "blur");
    const textMerge = textShadow.append("feMerge");
    textMerge.append("feMergeNode").attr("in", "blur");
    textMerge.append("feMergeNode").attr("in", "SourceGraphic");

    // Grid background
    const grid = defs.append("pattern")
      .attr("id", "viz7-grid").attr("width", 40).attr("height", 40)
      .attr("patternUnits", "userSpaceOnUse");
    grid.append("path").attr("d", "M 40 0 L 0 0 0 40")
      .attr("fill", "none").attr("stroke", "rgba(124,58,237,0.18)")
      .attr("stroke-opacity", 0.25).attr("stroke-width", 0.5);

    // Per-type radial gradient
    Object.entries(TYPE_COLORS).forEach(([type, color]) => {
      const grad = defs.append("radialGradient")
        .attr("id", `viz7-grad-${type}`)
        .attr("cx", "35%").attr("cy", "35%").attr("r", "65%");
      grad.append("stop").attr("offset", "0%")
        .attr("stop-color", d3.color(color)!.brighter(1.2).formatHex());
      grad.append("stop").attr("offset", "100%")
        .attr("stop-color", color);
    });

    // Per-pair linear gradient for edges
    const linkPairSet = new Set<string>();
    simLinks.forEach((l) => {
      const sNode = simNodes.find((n) => n.id === (typeof l.source === "string" ? l.source : (l.source as SimNode).id));
      const tNode = simNodes.find((n) => n.id === (typeof l.target === "string" ? l.target : (l.target as SimNode).id));
      if (!sNode || !tNode) return;
      const key = `${sNode.type}__${tNode.type}`;
      if (linkPairSet.has(key)) return;
      linkPairSet.add(key);
      const lg = defs.append("linearGradient")
        .attr("id", `viz7-link-${sNode.type}-${tNode.type}`)
        .attr("gradientUnits", "userSpaceOnUse");
      lg.append("stop").attr("offset", "0%").attr("stop-color", TYPE_COLORS[sNode.type]);
      lg.append("stop").attr("offset", "100%").attr("stop-color", TYPE_COLORS[tNode.type]);
    });

    // Arrow markers per target type
    Object.entries(TYPE_COLORS).forEach(([type, color]) => {
      const marker = defs.append("marker")
        .attr("id", `viz7-arrow-${type}`)
        .attr("viewBox", "0 -5 10 10")
        .attr("refX", 10).attr("refY", 0)
        .attr("markerWidth", 6).attr("markerHeight", 6)
        .attr("orient", "auto");
      marker.append("path")
        .attr("d", "M0,-4L8,0L0,4")
        .attr("fill", color);
    });

    // ── Root container for zoom/pan ─────────────────────────────
    const root = svg.append("g");
    rootRef.current = root;
    root.append("rect")
      .attr("x", -W * 3).attr("y", -H * 3)
      .attr("width", W * 7).attr("height", H * 7)
      .attr("fill", "url(#viz7-grid)");

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 4])
      .on("zoom", (event) => {
        root.attr("transform", event.transform.toString());
        setZoomLevel(event.transform.k);
      });
    zoomRef.current = zoom;
    svg.call(zoom);

    // ── Force simulation ────────────────────────────────────────
    const simulation = d3.forceSimulation<SimNode>(simNodes)
      .force("link", d3.forceLink<SimNode, SimLink>(simLinks).id((d) => d.id).distance(140))
      .force("charge", d3.forceManyBody().strength(-450))
      .force("center", d3.forceCenter(W / 2, H / 2))
      .force("collision", d3.forceCollide<SimNode>().radius((d) => d.radius + 6))
      .force("x", d3.forceX<SimNode>(W / 2).strength(0.05))
      .force("y", d3.forceY<SimNode>(H / 2).strength(0.05));
    simulationRef.current = simulation;

    // ── Edges ───────────────────────────────────────────────────
    const linkSel = root.append("g")
      .attr("class", "viz7-links")
      .selectAll<SVGPathElement, SimLink>("path")
      .data(simLinks)
      .join("path")
      .attr("fill", "none")
      .attr("stroke", (d) => {
        const sNode = simNodes.find((n) => n.id === (typeof d.source === "string" ? d.source : (d.source as SimNode).id));
        const tNode = simNodes.find((n) => n.id === (typeof d.target === "string" ? d.target : (d.target as SimNode).id));
        if (!sNode || !tNode) return colors.textSecondary;
        return `url(#viz7-link-${sNode.type}-${tNode.type})`;
      })
      .attr("stroke-opacity", 0.65)
      .attr("stroke-width", (d) => Math.sqrt(d.weight || 1) * 1.76)
      .attr("marker-end", (d) => {
        const tNode = simNodes.find((n) => n.id === (typeof d.target === "string" ? d.target : (d.target as SimNode).id));
        return tNode ? `url(#viz7-arrow-${tNode.type})` : "";
      })
      .style("cursor", "pointer");
    linkSelRef.current = linkSel;

    const edgeLabelSel = root.append("g")
      .attr("class", "viz7-edge-labels")
      .selectAll<SVGTextElement, SimLink>("text")
      .data(simLinks)
      .join("text")
      .text((d) => RELATION_LABELS[d.relation] || d.relation)
      .attr("fill", colors.textSecondary)
      .attr("font-size", 10)
      .attr("font-weight", 500)
      .attr("text-anchor", "middle")
      .attr("dy", -6)
      .attr("filter", "url(#viz7-text-shadow)")
      .style("pointer-events", "none")
      .style("opacity", 0.75);
    edgeLabelSelRef.current = edgeLabelSel;

    // ── Nodes ───────────────────────────────────────────────────
    const nodeSel = root.append("g")
      .attr("class", "viz7-nodes")
      .selectAll<SVGGElement, SimNode>("g")
      .data(simNodes, (d) => d.id)
      .join("g")
      .style("cursor", "grab");
    nodeSelRef.current = nodeSel;

    // Drag
    const drag = d3.drag<SVGGElement, SimNode>()
      .on("start", (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x; d.fy = d.y;
      })
      .on("drag", (event, d) => { d.fx = event.x; d.fy = event.y; })
      .on("end", (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null; d.fy = null;
      });
    nodeSel.call(drag);

    // Shape per type
    nodeSel.each(function (d) {
      const g = d3.select(this);
      const r = d.radius;
      const gradId = `viz7-grad-${d.type}`;
      // stroke 用深紫（colors.text），在浅紫背景下清晰可见
      // —— 之前用 colors.background（浅紫）会与画布融为一体
      const strokeColor = colors.text;

      switch (d.type) {
        case "chapter": {
          // Rounded rectangle
          g.append("path")
            .attr("d", roundedRectPath(0, 0, r * 2.2, r * 1.4, 5))
            .attr("fill", `url(#${gradId})`)
            .attr("stroke", strokeColor)
            .attr("stroke-width", 2.2)
            .attr("filter", "url(#viz7-node-glow)");
          break;
        }
        case "climax": {
          // Hexagon
          g.append("polygon")
            .attr("points", polygonPoints(6, r))
            .attr("fill", `url(#${gradId})`)
            .attr("stroke", strokeColor)
            .attr("stroke-width", 2.2)
            .attr("filter", "url(#viz7-node-glow)");
          break;
        }
        case "turning_point": {
          // Diamond
          g.append("polygon")
            .attr("points", `0,${-r} ${r},0 0,${r} ${-r},0`)
            .attr("fill", `url(#${gradId})`)
            .attr("stroke", strokeColor)
            .attr("stroke-width", 2.2)
            .attr("filter", "url(#viz7-node-glow)");
          break;
        }
        case "conflict": {
          // Triangle
          g.append("polygon")
            .attr("points", `0,${-r} ${r * 0.95},${r * 0.85} ${-r * 0.95},${r * 0.85}`)
            .attr("fill", `url(#${gradId})`)
            .attr("stroke", strokeColor)
            .attr("stroke-width", 2.2)
            .attr("filter", "url(#viz7-node-glow)");
          break;
        }
        case "ending": {
          // 5-pointed star
          g.append("polygon")
            .attr("points", starPoints(r, r * 0.45, 5))
            .attr("fill", `url(#${gradId})`)
            .attr("stroke", strokeColor)
            .attr("stroke-width", 2.2)
            .attr("filter", "url(#viz7-node-glow)");
          break;
        }
        case "scene": {
          // Small circle with stroke
          g.append("circle")
            .attr("r", r)
            .attr("fill", `url(#${gradId})`)
            .attr("stroke", strokeColor)
            .attr("stroke-width", 2.2)
            .attr("filter", "url(#viz7-node-glow)");
          break;
        }
        case "plot_line": {
          // Square (剧情线) —— 之前完全没 case 导致 191 个 plot_line 节点无 shape 渲染，图谱看起来是空的
          g.append("rect")
            .attr("x", -r)
            .attr("y", -r)
            .attr("width", r * 2)
            .attr("height", r * 2)
            .attr("rx", 3)
            .attr("fill", `url(#${gradId})`)
            .attr("stroke", strokeColor)
            .attr("stroke-width", 2.2)
            .attr("filter", "url(#viz7-node-glow)");
          break;
        }
        default: {
          // 兜底：未识别的类型画圆，避免节点不可见
          g.append("circle")
            .attr("r", r)
            .attr("fill", `url(#${gradId})`)
            .attr("stroke", strokeColor)
            .attr("stroke-width", 2.2)
            .attr("filter", "url(#viz7-node-glow)");
          break;
        }
      }
    });

    // Labels
    nodeSel.append("text")
      .text((d) => truncate(d.label, 18))
      .attr("x", (d) => d.radius + 8)
      .attr("y", 4)
      .attr("fill", colors.text)
      .attr("font-size", 12)
      .attr("font-weight", 600)
      .attr("filter", "url(#viz7-text-shadow)")
      .style("pointer-events", "none");

    // Chapter number badge (top-right of label)
    nodeSel.filter(function (d: any) { return d.chapterNo != null; })
      .append("text")
      .text((d: any) => `Ch.${d.chapterNo}`)
      .attr("x", (d: any) => -d.radius - 4)
      .attr("y", (d: any) => -d.radius - 4)
      .attr("fill", colors.text)
      .attr("font-size", 9)
      .attr("font-weight", 700)
      .attr("text-anchor", "end")
      .attr("filter", "url(#viz7-text-shadow)")
      .style("pointer-events", "none");

    // Cluster count badge
    if (isClustered) {
      nodeSel.filter(function (d: any) { return !!d.clusterId; })
        .append("text")
        .text(function (d: any) {
          const members = clusterMapRef.current.get(d.id);
          return members ? `×${members.length}` : "";
        })
        .attr("x", 0)
        .attr("y", 4)
        .attr("fill", colors.text)
        .attr("font-size", 11)
        .attr("font-weight", 700)
        .attr("text-anchor", "middle")
        .attr("filter", "url(#viz7-text-shadow)")
        .style("pointer-events", "none");
    }

    // ── Hover interactions ──────────────────────────────────────
    nodeSel
      .on("mouseenter", function (event, d) {
        d3.select(this).select("circle, polygon, path, rect")
          .interrupt()
          .transition().duration(180)
          .attr("filter", "url(#viz7-node-glow-hover)")
          .attr("transform", "scale(1.2)");

        // Build tooltip content
        const members = clusterMapRef.current.get(d.id);
        const memberList = members && members.length > 0
          ? `<div class="viz7-tooltip-row"><span class="viz7-tooltip-label">包含节点:</span> ${members.length}</div>`
          : "";
        const themeRow = d.theme
          ? `<div class="viz7-tooltip-row"><span class="viz7-tooltip-label">主题:</span> ${d.theme}</div>`
          : "";
        const chapterRow = d.chapterNo != null
          ? `<div class="viz7-tooltip-row"><span class="viz7-tooltip-label">章节:</span> Ch.${d.chapterNo}</div>`
          : "";
        const typeLabel = TYPE_LABELS[d.type] || d.type;

        setTooltip({
          x: event.clientX,
          y: event.clientY,
          content: `<strong>${d.label}</strong>
            <div class="viz7-tooltip-row"><span class="viz7-tooltip-label">类型:</span> ${typeLabel}</div>
            ${chapterRow}
            ${themeRow}
            ${memberList}
            <div class="viz7-tooltip-row"><span class="viz7-tooltip-label">ID:</span> ${d.id}</div>`,
        });
      })
      .on("mousemove", function (event) {
        setTooltip((prev) => prev ? { ...prev, x: event.clientX, y: event.clientY } : null);
      })
      .on("mouseleave", function () {
        d3.select(this).select("circle, polygon, path, rect")
          .interrupt()
          .transition().duration(180)
          .attr("filter", "url(#viz7-node-glow)")
          .attr("transform", "scale(1)");
        setTooltip(null);
      });

    // Edge hover
    linkSel
      .on("mouseenter", function () {
        linkSel.transition().duration(150).attr("stroke-opacity", 0.15);
        edgeLabelSel.transition().duration(150).style("opacity", 0.15);
        d3.select(this).transition().duration(150)
          .attr("stroke-opacity", 1).attr("stroke-width", 3.85);
      })
      .on("mouseleave", function () {
        linkSel.transition().duration(150).attr("stroke-opacity", 0.65);
        edgeLabelSel.transition().duration(150).style("opacity", 0.75);
        d3.select(this).transition().duration(150)
          .attr("stroke-opacity", 0.65)
          .attr("stroke-width", function (d: any) { return Math.sqrt(d.weight || 1) * 1.76; });
      });

    // ── Tick ────────────────────────────────────────────────────
    simulation.on("tick", () => {
      linkSel.attr("d", (d) => {
        const sx = (d.source as SimNode).x ?? 0;
        const sy = (d.source as SimNode).y ?? 0;
        const tx = (d.target as SimNode).x ?? 0;
        const ty = (d.target as SimNode).y ?? 0;
        return `M${sx},${sy}L${tx},${ty}`;
      });
      edgeLabelSel
        .attr("x", (d) => (((d.source as SimNode).x ?? 0) + ((d.target as SimNode).x ?? 0)) / 2)
        .attr("y", (d) => (((d.source as SimNode).y ?? 0) + ((d.target as SimNode).y ?? 0)) / 2);
      nodeSel.attr("transform", (d) => `translate(${d.x ?? 0},${d.y ?? 0})`);
    });

    return () => {
      simulation.stop();
      simulationRef.current = null;
      rootRef.current = null;
      linkSelRef.current = null;
      edgeLabelSelRef.current = null;
      nodeSelRef.current = null;
    };
    // init effect 依赖 hasData + 容器尺寸；尺寸从 0 变 >0 时也会重新跑。
    // 数据/集群状态变化由下面 update effect 处理。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasData, size.width, size.height]);

  // ── D3 update effect：simNodes/simLinks/isClustered 变化时复用 sim 实例，
  // 只更新 simulation 的 nodes/links，然后 alpha(0.5).restart() 软重启。
  // 用 join() 在已有 selection 上做 enter/update/exit，不销毁 DOM。
  useEffect(() => {
    const sim = simulationRef.current;
    if (!sim) return; // 还没 init 或已经被 unmount

    // 1) 更新 simulation 数据
    sim.nodes(simNodes);
    const linkForce = sim.force("link") as d3.ForceLink<SimNode, SimLink> | undefined;
    if (linkForce) {
      linkForce.links(simLinks);
    }

    // 2) 在已有 selection 上 join（key = id），避免销毁旧节点 DOM
    const prevLinkSel = linkSelRef.current;
    const prevEdgeLabelSel = edgeLabelSelRef.current;
    const prevNodeSel = nodeSelRef.current;
    const root = rootRef.current;
    if (!prevLinkSel || !prevEdgeLabelSel || !prevNodeSel || !root) return;

    // Links: 重绑 data + 重新挂事件（attr 由 tick 回调统一更新）
    prevLinkSel
      .data(simLinks, (d: any) => {
        const s = typeof d.source === "string" ? d.source : d.source.id;
        const t = typeof d.target === "string" ? d.target : d.target.id;
        return `${s}|||${t}|||${d.relation}`;
      })
      .join(
        (enter) =>
          enter.append("path")
            .attr("fill", "none")
            .attr("stroke-opacity", 0.65)
            .attr("marker-end", (d) => {
              const tNode = simNodes.find((n) => n.id === (typeof d.target === "string" ? d.target : (d.target as SimNode).id));
              return tNode ? `url(#viz7-arrow-${tNode.type})` : "";
            })
            .style("cursor", "pointer"),
        (update) => update,
        (exit) => exit.remove(),
      );

    // Edge labels
    prevEdgeLabelSel
      .data(simLinks, (d: any) => {
        const s = typeof d.source === "string" ? d.source : d.source.id;
        const t = typeof d.target === "string" ? d.target : d.target.id;
        return `${s}|||${t}|||${d.relation}`;
      })
      .join(
        (enter) =>
          enter.append("text")
            .text((d: SimLink) => RELATION_LABELS[d.relation] || d.relation)
            .attr("fill", colors.textSecondary)
            .attr("font-size", 10)
            .attr("font-weight", 500)
            .attr("text-anchor", "middle")
            .attr("dy", -6)
            .attr("filter", "url(#viz7-text-shadow)")
            .style("pointer-events", "none")
            .style("opacity", 0.75),
        (update) => update,
        (exit) => exit.remove(),
      );

    // Nodes: enter 创建新 shape；update 保留（位置由 tick 统一改）
    prevNodeSel
      .data(simNodes, (d) => d.id)
      .join(
        (enter) => {
          const g = enter.append("g").style("cursor", "grab");
          g.each(function (d) {
            const nodeG = d3.select(this);
            const r = d.radius;
            const gradId = `viz7-grad-${d.type}`;
            switch (d.type) {
              case "chapter":
                nodeG.append("path")
                  .attr("d", roundedRectPath(0, 0, r * 2.2, r * 1.4, 5))
                  .attr("fill", `url(#${gradId})`)
                  .attr("stroke", colors.background)
                  .attr("stroke-width", 2.2)
                  .attr("filter", "url(#viz7-node-glow)");
                break;
              case "climax":
                nodeG.append("polygon")
                  .attr("points", polygonPoints(6, r))
                  .attr("fill", `url(#${gradId})`)
                  .attr("stroke", colors.background)
                  .attr("stroke-width", 2.2)
                  .attr("filter", "url(#viz7-node-glow)");
                break;
              case "turning_point":
                nodeG.append("polygon")
                  .attr("points", `0,${-r} ${r},0 0,${r} ${-r},0`)
                  .attr("fill", `url(#${gradId})`)
                  .attr("stroke", colors.background)
                  .attr("stroke-width", 2.2)
                  .attr("filter", "url(#viz7-node-glow)");
                break;
              case "conflict":
                nodeG.append("polygon")
                  .attr("points", `0,${-r} ${r * 0.95},${r * 0.85} ${-r * 0.95},${r * 0.85}`)
                  .attr("fill", `url(#${gradId})`)
                  .attr("stroke", colors.background)
                  .attr("stroke-width", 2.2)
                  .attr("filter", "url(#viz7-node-glow)");
                break;
              case "ending":
                nodeG.append("polygon")
                  .attr("points", starPoints(r, r * 0.45, 5))
                  .attr("fill", `url(#${gradId})`)
                  .attr("stroke", colors.background)
                  .attr("stroke-width", 2.2)
                  .attr("filter", "url(#viz7-node-glow)");
                break;
              case "scene":
                nodeG.append("circle")
                  .attr("r", r)
                  .attr("fill", `url(#${gradId})`)
                  .attr("stroke", colors.background)
                  .attr("stroke-width", 2.2)
                  .attr("filter", "url(#viz7-node-glow)");
                break;
              case "plot_line":
                nodeG.append("rect")
                  .attr("x", -r)
                  .attr("y", -r)
                  .attr("width", r * 2)
                  .attr("height", r * 2)
                  .attr("rx", 3)
                  .attr("fill", `url(#${gradId})`)
                  .attr("stroke", colors.background)
                  .attr("stroke-width", 2.2)
                  .attr("filter", "url(#viz7-node-glow)");
                break;
              default:
                // 兜底：未识别的类型画圆（用 colors.text 深紫描边，浅紫背景下可见）
                nodeG.append("circle")
                  .attr("r", r)
                  .attr("fill", `url(#${gradId})`)
                  .attr("stroke", colors.text)
                  .attr("stroke-width", 2.2)
                  .attr("filter", "url(#viz7-node-glow)");
                break;
            }
          });
          // Labels
          g.append("text")
            .text((d) => truncate(d.label, 18))
            .attr("x", (d) => d.radius + 8)
            .attr("y", 4)
            .attr("fill", colors.text)
            .attr("font-size", 12)
            .attr("font-weight", 600)
            .attr("filter", "url(#viz7-text-shadow)")
            .style("pointer-events", "none");
          // Chapter badge
          g.filter(function (d: any) { return d.chapterNo != null; })
            .append("text")
            .text((d: any) => `Ch.${d.chapterNo}`)
            .attr("x", (d: any) => -d.radius - 4)
            .attr("y", (d: any) => -d.radius - 4)
            .attr("fill", colors.text)
            .attr("font-size", 9)
            .attr("font-weight", 700)
            .attr("text-anchor", "end")
            .attr("filter", "url(#viz7-text-shadow)")
            .style("pointer-events", "none");
          // Cluster count badge
          if (isClustered) {
            g.filter(function (d: any) { return !!d.clusterId; })
              .append("text")
              .text(function (d: any) {
                const members = clusterMapRef.current.get(d.id);
                return members ? `×${members.length}` : "";
              })
              .attr("x", 0)
              .attr("y", 4)
              .attr("fill", colors.text)
              .attr("font-size", 11)
              .attr("font-weight", 700)
              .attr("text-anchor", "middle")
              .attr("filter", "url(#viz7-text-shadow)")
              .style("pointer-events", "none");
          }
          return g;
        },
        (update) => update,
        (exit) => exit.remove(),
      );

    // 3) 软重启 simulation —— 不从中心散开（alpha 1.0 → 0.5 让现有位置小幅调整）
    sim.alpha(0.5).restart();
  }, [simNodes, simLinks, isClustered]);

  // 独立监听尺寸变化：仅 update force center + restart，不重建 d3。
  // 第一次（rw=0 → rw>0）已经在 d3 useEffect 早返回里跳过，所以这里
  // 只关心 size 数值真正变化的情况。
  useEffect(() => {
    const sim = simulationRef.current;
    if (!sim) return;
    const { width, height } = size;
    if (width <= 0 || height <= 0) return;
    const cx = width / 2;
    const cy = height / 2;
    const fc = sim.force("center") as d3.ForceCenter<SimNode> | undefined;
    if (fc) fc.x(cx).y(cy);
    const fx = sim.force("x") as d3.ForceX<SimNode> | undefined;
    if (fx) fx.x(cx);
    const fy = sim.force("y") as d3.ForceY<SimNode> | undefined;
    if (fy) fy.y(cy);
    sim.alpha(0.4).restart();
  }, [size]);

  // ── Render: empty state ───────────────────────────────────────
  if (!hasData) {
    return (
      <div className="viz7-root" style={{ flex: 1, minHeight: 0, width: '100%' }}>
        <div className="viz7-toolbar">
          <div className="viz7-toolbar-left">
            <span className="viz7-toolbar-stats">故事脉络视图</span>
            {/* Task 8: 书籍选择器（empty state 也展示，方便切换） */}
            {projectId !== undefined && (
              <select
                value={effectiveBookId == null ? '' : String(effectiveBookId)}
                onChange={(e) => {
                  const v = e.target.value;
                  setEffectiveBookId(v ? Number(v) : null);
                }}
                disabled={booksLoading || books.length === 0}
                title="当前 book"
                style={{
                  marginLeft: 12,
                  padding: '4px 8px',
                  fontSize: 12,
                  background: colors.inkCard,
                  color: colors.text,
                  border: `1px solid ${colors.border}`,
                  borderRadius: 4,
                  outline: 'none',
                  cursor: booksLoading || books.length === 0 ? 'not-allowed' : 'pointer',
                }}
              >
                {booksLoading ? (
                  <option value="">加载书籍中…</option>
                ) : books.length === 0 ? (
                  <option value="">（无书籍）</option>
                ) : (
                  <>
                    <option value="">全部书籍</option>
                    {books.map((b) => (
                      <option key={b.id} value={String(b.id)}>{b.name}</option>
                    ))}
                  </>
                )}
              </select>
            )}
          </div>
        </div>
        <div
          ref={setGraphContainerRef}
          className="viz7-graph-area"
          style={{ flex: 1, minHeight: 0 }}
        >
          <div className="viz7-empty">
            <div className="viz7-empty-icon">📖</div>
            <div className="viz7-empty-title">暂无故事脉络数据</div>
            <div className="viz7-empty-hint">
              AI 完成大纲规划后,将以有向无环图(DAG)展示章节、高潮、转折点、冲突、结局之间的关系。
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Render: with data ─────────────────────────────────────────
  const presentTypes = useMemo(() => {
    const set = new Set<StoryArcNodeType>();
    nodes.forEach((n) => set.add(n.type));
    return Array.from(set);
  }, [nodes]);

  const presentRelations = useMemo(() => {
    const set = new Set<StoryArcRelation>();
    edges.forEach((e) => set.add(e.relation));
    return Array.from(set);
  }, [edges]);

  // Task A2.1 — 容器尺寸降级分支：当 size 仍为 0（getBoundingClientRect 返回 0
  // 或 ResizeObserver 首次回调延迟）时，渲染骨架屏（紫色毛笔字"故事脉络" +
  // 3 个跳动的墨点），等尺寸恢复后自动重绘。
  if (size.width <= 0 || size.height <= 0) {
    return (
      <div className="viz7-root" style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', width: '100%' }}>
        <div className="viz7-toolbar">
          <div className="viz7-toolbar-left">
            <span className="viz7-toolbar-stats">故事脉络视图</span>
          </div>
        </div>
        <div
          ref={setGraphContainerRef}
          className="viz7-graph-area"
          style={{ flex: 2, minHeight: 0 }}
        >
          <div className="viz7-skeleton">
            <div className="viz7-skeleton-title">故事脉络</div>
            <div className="viz7-skeleton-dots" aria-label="加载中">
              <span className="viz7-skeleton-dot" />
              <span className="viz7-skeleton-dot" />
              <span className="viz7-skeleton-dot" />
            </div>
            <div className="viz7-skeleton-hint">布局中…</div>
          </div>
        </div>
        <div
          className="viz7-analysis-skeleton"
          style={{
            flex: 1,
            minHeight: 0,
            display: 'flex',
            borderTop: '1px solid rgba(58, 38, 107, 0.12)',
            background: 'rgba(255, 255, 255, 0.4)',
          }}
        >
          <div className="viz7-analysis-skeleton-panel" />
          <div className="viz7-analysis-skeleton-panel" />
          <div className="viz7-analysis-skeleton-panel" />
        </div>
      </div>
    );
  }

  return (
    <div className="viz7-root" style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', width: '100%' }}>
      {/* Toolbar */}
      <div className="viz7-toolbar">
        <div className="viz7-toolbar-left">
          <span className="viz7-toolbar-stats">
            故事脉络 ·
            <strong> {nodes.length} </strong>节点 ·
            <strong> {edges.length} </strong>关系
            {stats && (
              <span style={{ marginLeft: 8, color: colors.textSecondary, fontSize: 11 }}>
                （{stats.chapters} 章 · {stats.plotLines} 剧情线 · {stats.plans} 大纲）
              </span>
            )}
            {isClustered && <span style={{ marginLeft: 6, color: warningColor }}>(已聚合并并)</span>}
          </span>
          {/* Task 8: 书籍选择器 */}
          {projectId !== undefined && (
            <select
              value={effectiveBookId == null ? '' : String(effectiveBookId)}
              onChange={(e) => {
                const v = e.target.value;
                setEffectiveBookId(v ? Number(v) : null);
              }}
              disabled={booksLoading || books.length === 0}
              title="当前 book"
              style={{
                marginLeft: 12,
                padding: '4px 8px',
                fontSize: 12,
                background: colors.inkCard,
                color: colors.text,
                border: `1px solid ${colors.border}`,
                borderRadius: 4,
                outline: 'none',
                cursor: booksLoading || books.length === 0 ? 'not-allowed' : 'pointer',
              }}
            >
              {booksLoading ? (
                <option value="">加载书籍中…</option>
              ) : books.length === 0 ? (
                <option value="">（无书籍）</option>
              ) : (
                <>
                  <option value="">全部书籍</option>
                  {books.map((b) => (
                    <option key={b.id} value={String(b.id)}>{b.name}</option>
                  ))}
                </>
              )}
            </select>
          )}
        </div>
        <div className="viz7-mini-legend">
          {presentTypes.map((t) => (
            <div key={t} className="viz7-mini-legend-item">
              <span className="viz7-mini-legend-dot" style={{ background: TYPE_COLORS[t], boxShadow: `0 0 6px ${TYPE_COLORS[t]}88` }} />
              {TYPE_LABELS[t]}
            </div>
          ))}
          <button
            className="viz7-legend-toggle"
            onClick={() => setLegendOpen(!legendOpen)}
            title={legendOpen ? "收起图例" : "展开图例"}
          >
            {legendOpen ? "▶" : "◀"} 图例
          </button>
        </div>
      </div>

      {/* Graph area (flex: 2) — 故事脉络图 */}
      <div
        ref={setGraphContainerRef}
        className="viz7-graph-area"
        style={{ flex: 2, minHeight: 0 }}
      >
        <svg ref={svgRef} className="viz7-svg" />

        {/* Zoom controls */}
        <div className="viz7-zoom-controls">
          <button className="viz7-zoom-btn" onClick={zoomIn} title="放大">+</button>
          <div className="viz7-zoom-label">{Math.round(zoomLevel * 100)}%</div>
          <button className="viz7-zoom-btn" onClick={zoomOut} title="缩小">−</button>
          <button className="viz7-zoom-btn viz7-zoom-btn-reset" onClick={zoomReset} title="重置缩放">⟲</button>
        </div>

        {/* Tooltip */}
        {tooltip && (
          <div
            className="viz7-tooltip"
            dangerouslySetInnerHTML={{ __html: tooltip.content }}
            style={{ position: 'fixed', left: tooltip.x + 14, top: tooltip.y - 10 }}
          />
        )}

        {/* Collapsible legend panel */}
        <div
          className="viz7-legend"
          style={{
            width: legendOpen ? 240 : 0,
            height: legendOpen ? 'auto' : 0,
          }}
        >
          {legendOpen && (
            <div className="viz7-legend-content">
              <div className="viz7-legend-title">
                <span>图例 · 故事脉络</span>
                <button className="viz7-legend-close" onClick={() => setLegendOpen(false)} title="关闭">×</button>
              </div>

              {/* Node types with shape swatches */}
              <div className="viz7-legend-section-title">节点类型 / 形状</div>
              {presentTypes.map((t) => {
                const count = nodes.filter((n) => n.type === t).length;
                return (
                  <div key={t} className="viz7-legend-row">
                    <svg className="viz7-legend-shape" width="18" height="18" viewBox="-10 -10 20 20">
                      {renderLegendShape(t)}
                    </svg>
                    <span>{TYPE_LABELS[t]}</span>
                    <span className="viz7-legend-row-count">{count}</span>
                  </div>
                );
              })}

              {/* Relation types */}
              {presentRelations.length > 0 && (
                <>
                  <div className="viz7-legend-section-title">关系类型</div>
                  {presentRelations.map((r) => (
                    <div key={r} className="viz7-legend-row">
                      <svg width="28" height="10">
                        <defs>
                          <linearGradient id={`viz7-legend-grad-${r}`} x1="0" x2="1" y1="0" y2="0">
                            <stop offset="0%" stopColor={colors.accent} />
                            <stop offset="100%" stopColor={colors.paused} />
                          </linearGradient>
                        </defs>
                        <line x1="0" y1="5" x2="22" y2="5" stroke={`url(#viz7-legend-grad-${r})`} strokeWidth="2" />
                        <polygon points="20,2 25,5 20,8" fill={colors.textSecondary} />
                      </svg>
                      <span>{RELATION_LABELS[r]}</span>
                      <span className="viz7-legend-row-count">
                        {edges.filter((e) => e.relation === r).length}
                      </span>
                    </div>
                  ))}
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Analysis panel (flex: 1) — 阶段分布 + 关键转折点 + 主要情节线索 */}
      <div
        style={{
          flex: 1,
          minHeight: 0,
          display: 'flex',
          borderTop: '1px solid rgba(58, 38, 107, 0.12)',
          background: 'rgba(255, 255, 255, 0.4)',
        }}
      >
        {/* 左：事件阶段分布 */}
        <div
          style={{
            flex: 1,
            padding: 12,
            overflow: 'auto',
            borderRight: '1px solid rgba(58, 38, 107, 0.12)',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <div style={{ fontSize: 22, fontWeight: 400, color: 'colors.text', marginBottom: 8, fontFamily: 'var(--font-title)', letterSpacing: '0.02em' }}>
            事件阶段分布
          </div>
          <div
            ref={stageChartRef}
            style={{ width: '100%', flex: 1, minHeight: 0 }}
          />
          <div
            ref={emotionChartRef}
            className="viz7-emotion-chart"
            style={{ width: '100%', height: 100, marginTop: 6 }}
          />
        </div>

        {/* 中：Top 5 关键转折点 */}
        <div
          style={{
            flex: 1,
            padding: 12,
            overflow: 'auto',
            borderRight: '1px solid rgba(58, 38, 107, 0.12)',
          }}
        >
          <div style={{ fontSize: 22, fontWeight: 400, color: 'colors.text', marginBottom: 8, fontFamily: 'var(--font-title)', letterSpacing: '0.02em' }}>
            关键转折点 · Top 5
          </div>
          {keyEvents.length === 0 ? (
            <div style={{ fontSize: 11, color: colors.textSecondary, padding: '4px 0' }}>
              暂无数据
            </div>
          ) : (
            keyEvents.map((n, i) => {
              const typeColor = TYPE_COLORS[n.type] || colors.accent;
              const typeLabel = TYPE_LABELS[n.type] || n.type;
              return (
                <div
                  key={n.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    padding: '4px 0',
                    fontSize: 12,
                    gap: 6,
                  }}
                >
                  <span style={{ width: 18, color: 'colors.textSecondary', flexShrink: 0 }}>{i + 1}.</span>
                  <span
                    style={{
                      width: 4,
                      height: 14,
                      borderRadius: 2,
                      background: typeColor,
                      flexShrink: 0,
                    }}
                  />
                  <span
                    style={{
                      flex: 1,
                      color: colors.text,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                    title={n.label || n.id}
                  >
                    {n.label || n.id}
                  </span>
                  <span style={{ fontSize: 10, color: 'colors.textSecondary', flexShrink: 0 }}>
                    {typeLabel} · d{n.degree}
                  </span>
                </div>
              );
            })
          )}
          <div
            ref={wordChartRef}
            className="viz7-word-chart"
            style={{ width: '100%', height: 100, marginTop: 8 }}
          />
        </div>

        {/* 右：3 条主要情节线索 */}
        <div
          style={{
            flex: 1,
            padding: 12,
            overflow: 'auto',
          }}
        >
          <div style={{ fontSize: 22, fontWeight: 400, color: 'colors.text', marginBottom: 8, fontFamily: 'var(--font-title)', letterSpacing: '0.02em' }}>
            主要情节线索
          </div>
          {threads.length === 0 ? (
            <div style={{ fontSize: 11, color: 'colors.textSecondary', padding: '4px 0' }}>
              暂无数据
            </div>
          ) : (
            threads.map((t, i) => (
              <div
                key={i}
                style={{ padding: '6px 0', fontSize: 12, color: 'colors.text', lineHeight: 1.5 }}
              >
                <div style={{ color: '#7c3aed', marginBottom: 2, fontWeight: 600 }}>
                  线 {i + 1}
                </div>
                <div>{t}</div>
              </div>
            ))
          )}
          {/* SubTask 1.8: 图谱统计汇总卡 */}
          <div
            className="viz7-summary-card"
            style={{
              marginTop: 12,
              padding: '10px 12px',
              background: 'rgba(124, 58, 237, 0.06)',
              border: '1px solid rgba(124, 58, 237, 0.25)',
              borderRadius: 8,
            }}
          >
            <div style={{ fontSize: 12, fontWeight: 600, color: 'colors.text', marginBottom: 8 }}>
              图谱统计
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, fontSize: 11 }}>
              <div style={{ color: 'colors.textSecondary' }}>总节点</div>
              <div style={{ color: colors.text, textAlign: 'right', fontWeight: 600 }}>
                {nodes?.length || 0}
              </div>
              <div style={{ color: 'colors.textSecondary' }}>总关系</div>
              <div style={{ color: 'colors.text', textAlign: 'right', fontWeight: 600 }}>
                {edges?.length || 0}
              </div>
              <div style={{ color: 'colors.textSecondary' }}>跨章节连接</div>
              <div style={{ color: 'colors.text', textAlign: 'right', fontWeight: 600 }}>
                {(() => {
                  const nodeMap = new Map((nodes || []).map((n) => [n.id, n]));
                  return (edges || []).filter((e) => {
                    const s = nodeMap.get(e.source);
                    const t = nodeMap.get(e.target);
                    if (!s || !t) return false;
                    if (e.relation !== 'sequel_to' && e.relation !== 'leads_to') return false;
                    return (s.chapterNo ?? -1) !== (t.chapterNo ?? -1);
                  }).length;
                })()}
              </div>
              <div style={{ color: 'colors.textSecondary' }}>平均度数</div>
              <div style={{ color: 'colors.text', textAlign: 'right', fontWeight: 600 }}>
                {(() => {
                  const n = (nodes || []).length;
                  if (n === 0) return '0.0';
                  const degreeMap = new Map<string, number>();
                  (edges || []).forEach((e) => {
                    degreeMap.set(e.source, (degreeMap.get(e.source) || 0) + 1);
                    degreeMap.set(e.target, (degreeMap.get(e.target) || 0) + 1);
                  });
                  const totalDeg = Array.from(degreeMap.values()).reduce((a, b) => a + b, 0);
                  return (totalDeg / n).toFixed(1);
                })()}
              </div>
              <div style={{ color: 'colors.textSecondary' }}>包含书籍</div>
              <div style={{ color: 'colors.text', textAlign: 'right', fontWeight: 600 }}>
                {(() => {
                  const set = new Set<number>();
                  (nodes || []).forEach((n) => {
                    if (n.chapterNo != null) set.add(n.chapterNo);
                  });
                  return set.size;
                })()}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Inline legend shape renderer ──────────────────────────────────
function renderLegendShape(type: StoryArcNodeType): React.ReactNode {
  const color = TYPE_COLORS[type];
  const r = 7;
  switch (type) {
    case "chapter":
      return <rect x={-r} y={-r * 0.6} width={r * 2} height={r * 1.2} rx={2} fill={color} />;
    case "climax":
      return <polygon points={polygonPoints(6, r)} fill={color} />;
    case "turning_point":
      return <polygon points={`0,${-r} ${r},0 0,${r} ${-r},0`} fill={color} />;
    case "conflict":
      return <polygon points={`0,${-r} ${r * 0.95},${r * 0.85} ${-r * 0.95},${r * 0.85}`} fill={color} />;
    case "ending":
      return <polygon points={starPoints(r, r * 0.45, 5)} fill={color} />;
    case "scene":
      return <circle r={r} fill={color} />;
    case "plot_line":
      return <rect x={-r} y={-r} width={r * 2} height={r * 2} rx={2} fill={color} />;
  }
}

export default VisualizationTab7StoryArc;
