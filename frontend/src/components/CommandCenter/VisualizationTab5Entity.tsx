import React, { useEffect, useLayoutEffect, useRef, useState, useCallback, useMemo } from "react";
import * as d3 from "d3";
import * as echarts from "echarts";
import { colors } from "./styles";
import { GraphTypeSelector, type GraphType } from "./GraphTypeSelector";
import { useElementSize } from "../../hooks/useElementSize";
import { fetchBooks, generateKnowledgeGraph, type Book } from "../../lib/api";

interface VisualizationTab5EntityProps {
  projectId?: number;
  reloadToken?: number;
}

const typeColors: Record<string, string> = {
  "character": "#a78bfa",
  "worldbook": "#7c3aed",
  "worldbook_entry": "#7c3aed",
  "plot_line": "#8b5cf6",
  "event": "#c4b5fd",
  "story_event": "#c4b5fd",
  "story_arc": "#a78bfa",
  "theme": "#f472b6",
  "chapter": "#a78bfa",
  "chapter_plan": "#c4b5fd",
  "location": "#a78bfa",
  "organization": "#f472b6",
};

const typeLabels: Record<string, string> = {
  "character": "角色",
  "worldbook": "世界观",
  "worldbook_entry": "世界观",
  "plot_line": "剧情线",
  "story_arc": "故事弧线",
  "story_event": "事件",
  "event": "事件",
  "theme": "主题",
  "chapter": "章节",
  "chapter_plan": "章节规划",
  "location": "地点",
  "organization": "组织",
};

// Shape mapping: which types get which shape
function getNodeType(d: GraphNodeDatum): string {
  const t = d.type.toLowerCase();
  if (t === "character") return "character";
  if (t === "plot_line" || t === "story_arc") return "plotline";
  if (t === "event" || t === "story_event") return "event";
  if (t === "worldbook" || t === "worldbook_entry" || t === "theme") return "worldbook";
  if (t === "chapter" || t === "chapter_plan") return "chapter";
  return "default"; // circle for unknown
}

// 关系类型中文化映射 —— 后端目前存的是英文枚举值（hierarchy/romance/...）
// 一些数据可能是中文或带下划线，这里统一映射成中文标签
const RELATION_LABELS_CN: Record<string, string> = {
  hierarchy: "层级",
  romance: "爱情",
  mentorship: "师徒",
  friendship: "友谊",
  rivalry: "对立",
  ally: "盟友",
  enemy: "敌对",
  family: "血缘",
  parent_child: "亲子",
  siblings: "兄妹",
  couple: "情侣",
  member_of: "成员",
  belongs_to: "所属",
  located_in: "位于",
  participates_in: "参与",
  participant: "参与",
  co_commemorate_event: "共祭事件",
  co_appears_event: "共同出场",
  co_appears: "共同出场",
  conflicts_with: "冲突",
  causes: "引发",
  follows: "续接",
  foreshadows: "伏笔",
  resolves: "化解",
  relates_to: "关联",
  references: "引用",
  similar_to: "类似",
  inspired_by: "灵感",
  controls: "控制",
  owns: "持有",
  derived_from: "源自",
  derived_to: "衍生",
  is_a: "归属",
  part_of: "属于",
  character_friendship: "角色友谊",
  character_rivalry: "角色对立",
  character_family: "家族",
  character_mentorship: "师徒",
  character_romance: "角色爱情",
};

function relationLabel(raw: string | null | undefined): string {
  if (!raw) return "";
  const key = raw.toLowerCase();
  if (RELATION_LABELS_CN[key]) return RELATION_LABELS_CN[key];
  // 已经是中文则原样；否则返回原 key
  return /[\u4e00-\u9fa5]/.test(raw) ? raw : raw;
}

function getNodeRadius(d: GraphNodeDatum): number {
  const priority = (d.meta as any)?.priority || 1;
  return Math.max(priority * 3 + 8, 12);
}

function truncate(s: string, max: number): string {
  return s.length > max ? s.slice(0, max - 1) + "\u2026" : s;
}

// Generate points for a regular polygon centered at (0,0)
function polygonPoints(sides: number, r: number): string {
  const pts: string[] = [];
  for (let i = 0; i < sides; i++) {
    const angle = (Math.PI * 2 * i) / sides - Math.PI / 2;
    pts.push(`${(r * Math.cos(angle)).toFixed(2)},${(r * Math.sin(angle)).toFixed(2)}`);
  }
  return pts.join(" ");
}

interface GraphData {
  nodes: GraphNodeDatum[];
  links: d3.SimulationLinkDatum<GraphNodeDatum>[];
}

type GraphNodeDatum = d3.SimulationNodeDatum & {
  id: string;
  name: string;
  type: string;
  meta?: Record<string, unknown> | null;
};

function graphSnapshot(nodes: GraphNodeDatum[], links: d3.SimulationLinkDatum<GraphNodeDatum>[]): string {
  return JSON.stringify({
    nodes: nodes.map((n) => ({ id: n.id, name: n.name, type: n.type, meta: n.meta })),
    links: links.map((l: any) => ({
      source: typeof l.source === "string" ? l.source : l.source?.id,
      target: typeof l.target === "string" ? l.target : l.target?.id,
      type: l.type,
      intensity: l.intensity,
    })),
  });
}

export function VisualizationTab5Entity({ projectId, reloadToken = 0 }: VisualizationTab5EntityProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const typeChartRef = useRef<HTMLDivElement>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [graphType, setGraphType] = useState<GraphType>("story_entity");
  const [legendOpen, setLegendOpen] = useState(true);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; content: string } | null>(null);
  // Task 8: 书籍过滤
  const [books, setBooks] = useState<Book[]>([]);
  const [booksLoading, setBooksLoading] = useState(false);
  const [currentBookId, setCurrentBookId] = useState<number | null>(null);
  const [generating, setGenerating] = useState(false);
  const [genMsg, setGenMsg] = useState<string | null>(null);
  const [localReload, setLocalReload] = useState(0);
  // A1.1: 顶部 toolbar 显示图谱来源 / 类型 / 生成时间
  const [graphSource, setGraphSource] = useState<string | null>(null);
  const [graphTypeLabel, setGraphTypeLabel] = useState<string | null>(null);
  const [graphGeneratedAt, setGraphGeneratedAt] = useState<string | null>(null);
  // A1.4: 后端返回的 hint，用于切换空状态文案
  const [emptyHint, setEmptyHint] = useState<string | null>(null);
  // 按节点类型过滤；"all" 表示不过滤（综合图），否则只显示该类型 + 1 跳邻居的节点和边
  const [activeTypeFilter, setActiveTypeFilter] = useState<string>("all");
  const graphSnapshotRef = useRef("");

  const handleGenerateGraph = useCallback(async () => {
    if (!projectId || generating) return;
    setGenerating(true);
    setGenMsg("AI 正在分析角色 / 剧情，构建人物关系与事件网络…");
    try {
      const res = await generateKnowledgeGraph(projectId);
      if (res.status === "completed") {
        setGenMsg(
          `已生成：${res.added_relationships ?? 0} 条关系、${res.added_events ?? 0} 个事件、${res.added_arcs ?? 0} 条弧线`,
        );
      } else if (res.status === "skipped") {
        setGenMsg("项目暂无角色 / 剧情资产，请先创建项目并启动 AI 创作。");
      } else {
        setGenMsg("生成未完成，请稍后重试。");
      }
      graphSnapshotRef.current = "";
      // 明确不修改 graphData,避免后续误改；让 effect 通过 localReload 重跑去拉取最新数据
      setGraphData((prev) => prev); // no-op
      setLocalReload((x) => x + 1);
    } catch (e) {
      setGenMsg(e instanceof Error ? e.message : "故事图谱生成失败");
    } finally {
      setGenerating(false);
    }
  }, [projectId, generating]);
  // 用统一 hook 监听图谱区尺寸（不再监听整个 Tab，避免分析面板占掉高度）
  const [size, setContainerRef] = useElementSize<HTMLDivElement>();
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);

  // Task 8: 加载当前 project 的 books
  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    async function loadBooks() {
      setBooksLoading(true);
      try {
        const list = await fetchBooks(projectId as number);
        if (cancelled) return;
        setBooks(list);
        setCurrentBookId((prev) => {
          if (prev != null) return prev;
          return list.length > 0 ? list[0].id : null;
        });
      } catch {
        if (!cancelled) setBooks([]);
      } finally {
        if (!cancelled) setBooksLoading(false);
      }
    }
    void loadBooks();
    return () => { cancelled = true; };
  }, [projectId]);

  // 按节点类型过滤 + 保留 1 跳邻居 + 关系中文化标签
  const filteredGraphData = useMemo<GraphData | null>(() => {
    if (!graphData) return null;
    if (activeTypeFilter === "all") {
      return graphData;
    }
    const targetType = activeTypeFilter;
    // 找出"主类型节点"和它们的 1 跳邻居
    const targetIds = new Set(
      graphData.nodes.filter((n) => n.type === targetType).map((n) => n.id),
    );
    const neighborIds = new Set(targetIds);
    (graphData.links as any[]).forEach((l: any) => {
      const src = typeof l.source === "string" ? l.source : (l.source as GraphNodeDatum).id;
      const tgt = typeof l.target === "string" ? l.target : (l.target as GraphNodeDatum).id;
      if (targetIds.has(src)) neighborIds.add(tgt);
      if (targetIds.has(tgt)) neighborIds.add(src);
    });
    const filteredNodes = graphData.nodes.filter((n) => neighborIds.has(n.id));
    const filteredLinks = (graphData.links as any[]).filter((l: any) => {
      const src = typeof l.source === "string" ? l.source : (l.source as GraphNodeDatum).id;
      const tgt = typeof l.target === "string" ? l.target : (l.target as GraphNodeDatum).id;
      return neighborIds.has(src) && neighborIds.has(tgt);
    });
    return { nodes: filteredNodes, links: filteredLinks };
  }, [graphData, activeTypeFilter]);

  // 中心性分析：节点度数（关联边数）—— 基于过滤后数据计算
  const analysis = useMemo(() => {
    if (!filteredGraphData) return { topConnected: [] as Array<GraphNodeDatum & { degree: number }>, isolated: [] as GraphNodeDatum[], typeCount: {} as Record<string, number> };
    const nodes = filteredGraphData.nodes;
    const links = filteredGraphData.links;
    const degree = new Map<string, number>();
    nodes.forEach((n) => degree.set(n.id, 0));
    (links as any[]).forEach((l: any) => {
      const src = typeof l.source === "string" ? l.source : (l.source as GraphNodeDatum).id;
      const tgt = typeof l.target === "string" ? l.target : (l.target as GraphNodeDatum).id;
      degree.set(src, (degree.get(src) || 0) + 1);
      degree.set(tgt, (degree.get(tgt) || 0) + 1);
    });
    const topConnected = [...nodes]
      .map((n) => ({ ...n, degree: degree.get(n.id) || 0 }))
      .sort((a, b) => b.degree - a.degree)
      .slice(0, 5);
    const isolated = nodes.filter((n) => (degree.get(n.id) || 0) === 0);
    const typeCount: Record<string, number> = {};
    nodes.forEach((n) => {
      const t = n.type || "未知";
      typeCount[t] = (typeCount[t] || 0) + 1;
    });
    return { topConnected, isolated, typeCount };
  }, [filteredGraphData]);

  const topConnected = analysis.topConnected;
  const isolated = analysis.isolated;
  const typeCount = analysis.typeCount;

  useEffect(() => {
    if (!projectId) return;
    const currentProjectId = projectId;
    const currentGraphType = graphType;
    const currentBook = currentBookId;
    let cancelled = false;
    async function load() {
      setLoading((graphData?.nodes.length ?? 0) === 0);
      try {
        const { fetchProjectGraph } = await import("../../lib/api");
        const data = await fetchProjectGraph(currentProjectId, { graphType: currentGraphType, bookId: currentBook });
        if (!cancelled) {
          // A1.1: 顶部 toolbar 读取图谱来源 / 类型 / 生成时间
          setGraphSource(data?.source ?? null);
          setGraphTypeLabel(data?.graph_type ?? currentGraphType ?? null);
          setGraphGeneratedAt(data?.generated_at ?? null);
          // A1.4: 读取后端 hint 用于切换空状态文案
          setEmptyHint(data?.hint ?? null);
          // 不在前端截断节点：与 d3.forceLink 配对时若关系 source/target
          // 引用到被截掉的节点，会抛 "node not found: <id>" 异常。
          // 改为：保留全部节点 + 丢弃指向不存在端点的悬空关系。
          const rawNodes = (data.nodes || []).map((n: any) => ({
            id: n.id,
            name: n.label,
            type: n.type,
            meta: n.meta,
          }));
          const nodeIdSet = new Set<string>(rawNodes.map((n: { id: string }) => n.id));
          const allLinks = (data.relationships || []).map((r: any) => ({
            source: r.source,
            target: r.target,
            type: r.type,
            intensity: r.meta?.intensity || 1,
          }));
          const links = allLinks.filter((l: { source: string; target: string }) =>
            nodeIdSet.has(l.source) && nodeIdSet.has(l.target),
          );
          if (allLinks.length !== links.length && typeof console !== "undefined") {
            console.warn(
              `[KnowledgeGraph] 过滤了 ${allLinks.length - links.length} 条悬空关系（source/target 不在节点集合中）`,
            );
          }
          const nodes = rawNodes;
          const snapshot = graphSnapshot(nodes, links);
          if (snapshot === graphSnapshotRef.current) {
            return;
          }
          graphSnapshotRef.current = snapshot;
          if (nodes.length > 0) {
            setGraphData({ nodes, links });
          } else {
            setGraphData(null);
          }
        }
      } catch {
        if (!cancelled) {
          setGraphData(null);
          setGraphSource(null);
          setGraphTypeLabel(null);
          setGraphGeneratedAt(null);
          setEmptyHint(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [projectId, graphType, currentBookId, reloadToken, localReload]);

  const zoomIn = useCallback(() => {
    if (svgRef.current && zoomRef.current) {
      d3.select(svgRef.current).transition().duration(300).call(zoomRef.current.scaleBy, 1.4);
    }
  }, []);

  const zoomOut = useCallback(() => {
    if (svgRef.current && zoomRef.current) {
      d3.select(svgRef.current).transition().duration(300).call(zoomRef.current.scaleBy, 0.7);
    }
  }, []);

  const zoomReset = useCallback(() => {
    if (svgRef.current && zoomRef.current) {
      d3.select(svgRef.current).transition().duration(500).call(zoomRef.current.transform, d3.zoomIdentity);
    }
  }, []);

  useEffect(() => {
    if (!svgRef.current || !filteredGraphData || filteredGraphData.nodes.length === 0) return;
    // 优先用 ResizeObserver 的 size state；若尚未回调，退化为 getBoundingClientRect
    let renderWidth = size.width;
    let renderHeight = size.height;
    if (renderWidth === 0 || renderHeight === 0) return; // 容器还没尺寸，放弃本轮渲染

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const { width, height } = { width: renderWidth, height: renderHeight };
    // 使用过滤后的数据（按 activeTypeFilter + 1 跳邻居 + 关系中文化后的图）
    const linkData = filteredGraphData.links;
    const nodeData = filteredGraphData.nodes;

    // ── SVG defs ──────────────────────────────────────────────
    const defs = svg.append("defs");

    // Glow filter
    const glowFilter = defs.append("filter").attr("id", "node-glow").attr("x", "-50%").attr("y", "-50%").attr("width", "200%").attr("height", "200%");
    glowFilter.append("feDropShadow").attr("dx", 0).attr("dy", 0).attr("stdDeviation", 4).attr("flood-color", "#7c3aed").attr("flood-opacity", 0.5);

    // Node hover filter (stronger glow)
    const hoverFilter = defs.append("filter").attr("id", "node-glow-hover").attr("x", "-50%").attr("y", "-50%").attr("width", "200%").attr("height", "200%");
    hoverFilter.append("feDropShadow").attr("dx", 0).attr("dy", 0).attr("stdDeviation", 8).attr("flood-color", "#7c3aed").attr("flood-opacity", 0.8);

    // Text shadow filter
    const textShadow = defs.append("filter").attr("id", "text-shadow").attr("x", "-20%").attr("y", "-20%").attr("width", "140%").attr("height", "140%");
    textShadow.append("feDropShadow").attr("dx", 0).attr("dy", 1).attr("stdDeviation", 2).attr("flood-color", "#000").attr("flood-opacity", 0.8);

    // Grid pattern for background
    const gridPattern = defs.append("pattern").attr("id", "grid-bg").attr("width", 40).attr("height", 40).attr("patternUnits", "userSpaceOnUse");
    gridPattern.append("path").attr("d", "M 40 0 L 0 0 0 40").attr("fill", "none").attr("stroke", "rgba(124, 58, 237, 0.18)").attr("stroke-opacity", 0.6).attr("stroke-width", 0.5);

    // Arrow marker (default)
    defs.append("marker")
      .attr("id", "arrow-default")
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 20)
      .attr("refY", 0)
      .attr("markerWidth", 6)
      .attr("markerHeight", 6)
      .attr("orient", "auto")
      .append("path")
      .attr("d", "M0,-4L8,0L0,4")
      .attr("fill", colors.textSecondary);

    // Arrow markers per color (dynamically created below)

    // Radial gradients per type
    const usedTypes = [...new Set(nodeData.map((n) => n.type))];
    usedTypes.forEach((type) => {
      const c = typeColors[type] || colors.textSecondary;
      const grad = defs.append("radialGradient")
        .attr("id", `grad-${type.replace(/[^a-zA-Z]/g, "_")}`)
        .attr("cx", "35%").attr("cy", "35%").attr("r", "65%");
      grad.append("stop").attr("offset", "0%").attr("stop-color", d3.color(c)!.brighter(1.2).formatHex());
      grad.append("stop").attr("offset", "100%").attr("stop-color", c);
    });

    // Line gradients for each unique link color pair
    // 注意：必须在 d3.forceLink 运行 *之前* 计算 key，
    // 否则 link.source/link.target 还是字符串 ID，下面的 GraphNodeDatum 解构会失败
    const nodeById: Record<string, GraphNodeDatum> = {};
    nodeData.forEach((n) => { nodeById[n.id] = n; });
    const resolveTypeColor = (raw: any): string | null => {
      if (raw == null) return null;
      const node = typeof raw === "string" ? nodeById[raw] : (raw as GraphNodeDatum);
      if (!node) return null;
      return typeColors[node.type] || colors.textSecondary;
    };
    const linkColorSet = new Set<string>();
    linkData.forEach((link: any) => {
      const src = resolveTypeColor(link.source);
      const tgt = resolveTypeColor(link.target);
      if (src && tgt) {
        // 排序后拼接保证与 linkGroup stroke 的 url(#...) 完全一致
        const key = [src, tgt].sort().join("_");
        if (!linkColorSet.has(key)) {
          linkColorSet.add(key);
          const lg = defs.append("linearGradient").attr("id", `link-grad-${key.replace(/[^a-zA-Z]/g, "_")}`).attr("gradientUnits", "userSpaceOnUse");
          lg.append("stop").attr("offset", "0%").attr("stop-color", src);
          lg.append("stop").attr("offset", "100%").attr("stop-color", tgt);
        }
      }
    });

    // ── Main container group ──────────────────────────────────
    const container = svg.append("g");

    // Background grid rect
    container.append("rect")
      .attr("x", -width * 2)
      .attr("y", -height * 2)
      .attr("width", width * 5)
      .attr("height", height * 5)
      .attr("fill", "url(#grid-bg)");

    // ── Zoom behavior ─────────────────────────────────────────
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 4])
      .on("zoom", (event) => {
        container.attr("transform", event.transform.toString());
      });

    zoomRef.current = zoom;
    svg.call(zoom);

    // ── Force simulation ──────────────────────────────────────
    const simulation = d3.forceSimulation(nodeData)
      .force("link", d3.forceLink(linkData).id((d: any) => d.id).distance(Math.min(180, width / 6)))
      .force("charge", d3.forceManyBody().strength(-600))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("x", d3.forceX(width / 2).strength(0.05))
      .force("y", d3.forceY(height / 2).strength(0.05))
      .force("collision", d3.forceCollide().radius(50));

    // ── Compute edge curvature for multi-edges ───────────────
    const edgeCount: Record<string, number> = {};
    (linkData as any[]).forEach((l: any) => {
      const sid = typeof l.source === "string" ? l.source : (l.source as GraphNodeDatum).id;
      const tid = typeof l.target === "string" ? l.target : (l.target as GraphNodeDatum).id;
      const key = [sid, tid].sort().join("|||");
      edgeCount[key] = (edgeCount[key] || 0) + 1;
    });
    const edgeIndex: Record<string, number> = {};
    (linkData as any[]).forEach((l: any) => {
      const sid = typeof l.source === "string" ? l.source : (l.source as GraphNodeDatum).id;
      const tid = typeof l.target === "string" ? l.target : (l.target as GraphNodeDatum).id;
      const key = [sid, tid].sort().join("|||");
      edgeIndex[key] = (edgeIndex[key] || 0) + 1;
      (l as any)._edgeIndex = edgeIndex[key];
      (l as any)._edgeTotal = edgeCount[key];
    });

    // ── Edges (as curved paths) ───────────────────────────────
    const linkGroup = container
      .append("g")
      .selectAll("path")
      .data(linkData)
      .join("path")
      .attr("fill", "none")
      .attr("stroke", (d: any) => {
        // forceLink 跑过后 d.source/target 已是 node 对象；用 resolveTypeColor 同时兼容两种形态
        const src = resolveTypeColor(d.source);
        const tgt = resolveTypeColor(d.target);
        if (src && tgt) {
          // 排序后拼接，保证与 defs 的 id 完全对应
          const key = [src, tgt].sort().join("_");
          return `url(#link-grad-${key.replace(/[^a-zA-Z]/g, "_")})`;
        }
        return colors.textSecondary;
      })
      .attr("stroke-opacity", 0.6)
      .attr("stroke-width", (d: any) => Math.sqrt(d.intensity || 1) * 1.65)
      .style("cursor", "pointer");

    // Edge labels
    const edgeLabelGroup = container
      .append("g")
      .selectAll("text")
      .data(linkData)
      .join("text")
      .text((d: any) => truncate(relationLabel(d.type), 20))
      .attr("fill", colors.textSecondary)
      .attr("font-size", 9)
      .attr("font-weight", 500)
      .attr("text-anchor", "middle")
      .attr("dy", -5)
      .attr("filter", "url(#text-shadow)")
      .style("pointer-events", "none")
      .style("opacity", 0.7);

    // ── Nodes ─────────────────────────────────────────────────
    const nodeGroup = container
      .append("g")
      .selectAll("g")
      .data(nodeData)
      .join("g")
      .style("cursor", "grab") as d3.Selection<SVGGElement, GraphNodeDatum, SVGGElement, unknown>;

    const dragBehavior = d3.drag<SVGGElement, GraphNodeDatum>()
      .on("start", (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on("drag", (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on("end", (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      });

    nodeGroup.call(dragBehavior);

    // Node shapes
    nodeGroup.each(function (d) {
      const g = d3.select(this);
      const r = getNodeRadius(d);
      const shape = getNodeType(d);
      const gradId = `grad-${d.type.replace(/[^a-zA-Z]/g, "_")}`;

      if (shape === "character") {
        g.append("circle").attr("r", r).attr("fill", `url(#${gradId})`).attr("stroke", colors.background).attr("stroke-width", 2.2).attr("filter", "url(#node-glow)");
      } else if (shape === "plotline") {
        const w = r * 2, h = r * 1.2;
        g.append("rect").attr("x", -w / 2).attr("y", -h / 2).attr("width", w).attr("height", h).attr("rx", 6).attr("fill", `url(#${gradId})`).attr("stroke", colors.background).attr("stroke-width", 2.2).attr("filter", "url(#node-glow)");
      } else if (shape === "event") {
        g.append("polygon").attr("points", `0,${-r} ${r},0 0,${r} ${-r},0`).attr("fill", `url(#${gradId})`).attr("stroke", colors.background).attr("stroke-width", 2.2).attr("filter", "url(#node-glow)");
      } else if (shape === "worldbook") {
        g.append("polygon").attr("points", polygonPoints(6, r)).attr("fill", `url(#${gradId})`).attr("stroke", colors.background).attr("stroke-width", 2.2).attr("filter", "url(#node-glow)");
      } else if (shape === "chapter") {
        g.append("polygon").attr("points", `0,${-r} ${r},${r} ${-r},${r}`).attr("fill", `url(#${gradId})`).attr("stroke", colors.background).attr("stroke-width", 2.2).attr("filter", "url(#node-glow)");
      } else {
        g.append("circle").attr("r", r).attr("fill", `url(#${gradId})`).attr("stroke", colors.background).attr("stroke-width", 2.2).attr("filter", "url(#node-glow)");
      }
    });

    // Node labels
    nodeGroup
      .append("text")
      .text((d) => d.name)
      .attr("x", (d) => {
        const shape = getNodeType(d);
        if (shape === "character" || shape === "default") return getNodeRadius(d) + 6;
        return getNodeRadius(d) + 8;
      })
      .attr("y", 4)
      .attr("fill", colors.text)
      .attr("font-size", (d) => {
        const priority = (d.meta as any)?.priority || 1;
        return Math.max(priority + 10, 10);
      })
      .attr("font-weight", (d) => ((d.meta as any)?.priority || 1) >= 3 ? 700 : 500)
      .attr("filter", "url(#text-shadow)")
      .style("pointer-events", "none");

    // ── Hover interactions ────────────────────────────────────
    nodeGroup
      .on("mouseenter", function (event, d) {
        d3.select(this).select("circle, rect, polygon")
          .transition().duration(150)
          .attr("filter", "url(#node-glow-hover)")
          .attr("transform", "scale(1.2)");
        setTooltip({
          x: event.pageX,
          y: event.pageY,
          content: `<strong>${d.name}</strong><br/>类型: ${typeLabels[d.type] || d.type}<br/>ID: ${d.id}`,
        });
      })
      .on("mousemove", function (event) {
        setTooltip((prev) => prev ? { ...prev, x: event.pageX, y: event.pageY } : null);
      })
      .on("mouseleave", function () {
        d3.select(this).select("circle, rect, polygon")
          .transition().duration(150)
          .attr("filter", "url(#node-glow)")
          .attr("transform", "scale(1)");
        setTooltip(null);
      });

    // Edge hover
    linkGroup
      .on("mouseenter", function () {
        linkGroup.transition().duration(150).attr("stroke-opacity", 0.12);
        edgeLabelGroup.transition().duration(150).style("opacity", 0.1);
        d3.select(this).transition().duration(150).attr("stroke-opacity", 1).attr("stroke-width", 3.3);
      })
      .on("mouseleave", function () {
        linkGroup.transition().duration(150).attr("stroke-opacity", 0.6);
        edgeLabelGroup.transition().duration(150).style("opacity", 0.7);
        d3.select(this).transition().duration(150).attr("stroke-opacity", 0.6).attr("stroke-width", (l: any) => Math.sqrt(l.intensity || 1) * 1.65);
      });

    // ── Tick ──────────────────────────────────────────────────
    simulation.on("tick", () => {
      linkGroup.attr("d", (d: any) => {
        const sx = (d.source as any).x;
        const sy = (d.source as any).y;
        const tx = (d.target as any).x;
        const ty = (d.target as any).y;
        const total = d._edgeTotal || 1;
        if (total <= 1) return `M${sx},${sy}L${tx},${ty}`;
        // Curved path for multi-edges
        const idx = d._edgeIndex || 1;
        const dx = tx - sx;
        const dy = ty - sy;
        const dr = Math.sqrt(dx * dx + dy * dy) * 0.8;
        const sweep = idx % 2 === 0 ? 1 : 0;
        return `M${sx},${sy}A${dr},${dr} 0 0,${sweep} ${tx},${ty}`;
      });

      edgeLabelGroup
        .attr("x", (d: any) => ((d.source as any).x + (d.target as any).x) / 2)
        .attr("y", (d: any) => ((d.source as any).y + (d.target as any).y) / 2);

      nodeGroup.attr("transform", (d) => `translate(${d.x},${d.y})`);
    });

    return () => {
      simulation.stop();
    };
  }, [filteredGraphData, size]);

  // 节点类型分布 mini chart
  useEffect(() => {
    if (!typeChartRef.current) return;
    const entries = Object.entries(typeCount).sort((a, b) => b[1] - a[1]);
    if (entries.length === 0) return;

    const chart = echarts.init(typeChartRef.current);
    chart.setOption({
      backgroundColor: 'transparent',
      grid: { top: 8, right: 24, bottom: 8, left: 80 },
      xAxis: { type: "value", show: false },
      yAxis: {
        type: "category",
        data: entries.map(([k]) => typeLabels[k] || k),
        axisLabel: { color: colors.textSecondary, fontSize: 11 },
        axisLine: { show: false },
        axisTick: { show: false },
        inverse: true,
      },
      series: [{
        type: "bar",
        data: entries.map(([type, v]) => ({
          value: v,
          itemStyle: { color: typeColors[type] || colors.accent, borderRadius: [0, 3, 3, 0] },
        })),
        label: { show: true, position: "right", color: colors.text, fontSize: 11 },
        barWidth: 12,
      }],
      tooltip: { trigger: "item", backgroundColor: "rgba(255,255,255,0.95)", borderColor: "rgba(58,38,107,0.12)", textStyle: { color: colors.text } },
    });

    const handleResize = () => chart.resize();
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      chart.dispose();
    };
  }, [typeCount]);

  if (loading) {
    return <div style={{ padding: 40, textAlign: 'center', color: colors.textSecondary }}>加载实体关系数据中...</div>;
  }

  if (!graphData || graphData.nodes.length === 0) {
    // A1.2: 5 类节点说明（角色 / 剧情线 / 事件 / 世界观 / 主题），颜色用浅紫系
    const nodeKinds: Array<{ key: string; label: string; desc: string; color: string; svg: React.ReactNode }> = [
      {
        key: "character",
        label: "角色",
        desc: "Character — 主角 / 配角 / 反派",
        color: "#a78bfa",
        svg: <svg width="18" height="18" viewBox="0 0 18 18"><circle cx="9" cy="9" r="7" fill="#a78bfa" stroke="#7c3aed" strokeWidth="1" /></svg>,
      },
      {
        key: "plotline",
        label: "剧情线",
        desc: "PlotLine — 主线 / 支线 / 暗线",
        color: "#a78bfa",
        svg: <svg width="18" height="18" viewBox="0 0 18 18"><rect x="2" y="5" width="14" height="8" rx="2" fill="#a78bfa" stroke="#7c3aed" strokeWidth="1" /></svg>,
      },
      {
        key: "event",
        label: "事件",
        desc: "StoryEvent — 关键转折 / 高潮",
        color: "#c4b5fd",
        svg: <svg width="18" height="18" viewBox="0 0 18 18"><polygon points="9,2 16,9 9,16 2,9" fill="#c4b5fd" stroke="#7c3aed" strokeWidth="1" /></svg>,
      },
      {
        key: "worldbook",
        label: "世界观",
        desc: "Worldbook — 设定 / 地点 / 派系",
        color: "#c4b5fd",
        svg: <svg width="18" height="18" viewBox="0 0 18 18"><polygon points="9,2 15,5.5 15,12.5 9,16 3,12.5 3,5.5" fill="#c4b5fd" stroke="#7c3aed" strokeWidth="1" /></svg>,
      },
      {
        key: "theme",
        label: "主题",
        desc: "Theme — 核心命题 / 情感基调",
        color: "#a78bfa",
        svg: <svg width="18" height="18" viewBox="0 0 18 18"><polygon points="9,2 16,16 2,16" fill="#a78bfa" stroke="#7c3aed" strokeWidth="1" /></svg>,
      },
    ];
    // A1.3 / A1.4: 根据 hint 与 currentBookId 切换提示语
    const isBookEmpty = emptyHint === "empty_book" || (currentBookId != null && emptyHint == null);

    // 不同 graph_type 的空状态文案，避免「故事图谱/事件/世界观/章节」共用一段笼统话术
    const typeEmptyCopy: Record<string, { headline: string; desc: string; cta: string }> = {
      story_entity: {
        headline: isBookEmpty ? "当前选中的书籍下暂无图谱数据" : "暂无故事图谱数据",
        desc: isBookEmpty
          ? "请尝试切换其他书籍，或在切换为「全部书籍」后点击下方按钮让 AI 基于项目资产构建图谱。"
          : "故事图谱由 AI 分析角色、剧情与世界观自动生成人物关系、故事弧线与事件网络。点击下方按钮立即让 AI 基于当前项目资产构建图谱。",
        cta: "✨ 生成故事图谱",
      },
      character: {
        headline: isBookEmpty ? "当前书籍下暂无人物关系" : "暂无人物关系数据",
        desc: "在「人物 / 关系」菜单中先创建角色，并使用 RELATED_TO 类型连线，节点会自动出现在这里。",
        cta: "前往人物管理",
      },
      plot_line: {
        headline: isBookEmpty ? "当前书籍下尚无剧情线" : "暂无剧情线数据",
        desc: "在「剧情线」菜单中创建 PlotLine（主线 / 支线 / 暗线），AI 写完章节后还会自动补全节拍与从属关系。",
        cta: "前往剧情线管理",
      },
      story_arc: {
        headline: "故事脉络由 AI 写完章节时自动规范化生成",
        desc:
          "AI 完成每一章正文后会在后台触发一次 story_graph_generation 任务，扫描角色 / 剧情 / 世界观并写入 StoryArc / StoryTheme / StoryEvent 节点。如需立即生成，可点击下方按钮。",
        cta: "✨ 立即生成故事脉络",
      },
      event: {
        headline: isBookEmpty ? "当前书籍下暂无事件" : "暂无事件数据",
        desc: "AI 写完章节时会自动抽取关键事件写入 StoryEvent；也可在「事件」菜单中手动维护。",
        cta: "✨ 让 AI 抽取关键事件",
      },
      worldbook: {
        headline: isBookEmpty ? "当前书籍下暂无世界观条目" : "暂无世界观条目",
        desc: "在「世界观」菜单中创建 WorldbookEntry 设定条目（地点 / 派系 / 规则等），节点会出现在这里。",
        cta: "前往世界观管理",
      },
      chapter_plan: {
        headline: isBookEmpty ? "当前书籍下暂无章节结构" : "暂无章节结构",
        desc: "在「章节」菜单中创建章节后，节点会按 PRECEDES 顺序边自动串联，并展示其 ChapterPlan 大纲。",
        cta: "前往章节管理",
      },
    };
    const copy = typeEmptyCopy[graphType] || typeEmptyCopy.story_entity;
    const emptyHeadline = copy.headline;
    const emptyDesc = copy.desc;
    const ctaLabel = copy.cta;
    return (
      <div style={{ padding: 40, textAlign: 'center', color: colors.textSecondary, height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ maxWidth: 480, width: '100%' }}>
          <img src="/hero-illustration.svg" alt="knowledge graph" style={{ width: 220, opacity: 0.95, marginBottom: 12 }} />
          <div style={{ fontSize: 16, marginBottom: 8, color: colors.text }}>{emptyHeadline}</div>
          <div style={{ fontSize: 13, lineHeight: 1.6, marginBottom: 16 }}>
            {emptyDesc}
          </div>

          {/* A1.2: 5 类节点说明列表（带 inline SVG 图标） */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
            gap: 8,
            marginBottom: 18,
            textAlign: 'left',
          }}>
            {nodeKinds.map((k) => (
              <div
                key={k.key}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '6px 10px',
                  borderRadius: 6,
                  background: 'rgba(167, 139, 250, 0.08)',
                  border: '1px solid rgba(167, 139, 250, 0.2)',
                }}
              >
                {k.svg}
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: colors.text }}>{k.label}</span>
                  <span style={{ fontSize: 10, color: colors.textSecondary }}>{k.desc}</span>
                </div>
              </div>
            ))}
          </div>

          {/* 是否显示「AI 生成」主按钮：仅 story_entity / story_arc / event 三类支持。
              其余类型（character / plot_line / worldbook / chapter_plan）需要用户去对应菜单手动创建。 */}
          {(graphType === "story_entity" || graphType === "story_arc" || graphType === "event") ? (
            <button
              onClick={handleGenerateGraph}
              disabled={generating || !projectId}
              style={{
                padding: '10px 22px', fontSize: 13, fontWeight: 600,
                color: '#fff', cursor: generating ? 'not-supported' : 'pointer',
                border: 'none', borderRadius: 8,
                background: generating ? 'rgba(167,139,250,0.5)' : 'linear-gradient(135deg,#a78bfa,#7c3aed,#8b5cf6)',
                boxShadow: '0 6px 18px rgba(124, 58, 237, 0.25)',
              }}
            >
              {generating ? '正在构建故事图谱…' : ctaLabel}
            </button>
          ) : (
            <div style={{ fontSize: 12, color: colors.textSecondary }}>
              💡 该视图依赖手动维护的资产，请前往对应菜单创建后再回到这里查看。
            </div>
          )}
          {genMsg && <div style={{ fontSize: 12, marginTop: 12, color: colors.textSecondary }}>{genMsg}</div>}

          {/* A1.3: 切到具体 book 时追加更具体的引导 */}
          {isBookEmpty && (
            <div style={{ fontSize: 12, marginTop: 14, padding: '8px 12px', borderRadius: 6, background: 'rgba(167, 139, 250, 0.06)', border: '1px dashed rgba(167, 139, 250, 0.3)', color: colors.textSecondary, textAlign: 'left' }}>
              💡 当前选中的书籍下暂无图谱数据，请切换书籍或点击「生成故事图谱」。
            </div>
          )}
        </div>
      </div>
    );
  }

  const presentTypes = [...new Set(graphData.nodes.map((n: any) => n.type))];
  const presentRelTypes = [...new Set((graphData.links as any[]).map((l: any) => l.type).filter(Boolean))];

  // Shape-to-type legend mapping
  const shapeLegend = [
    { shape: "circle", label: "角色 (Character)", color: "#a78bfa" },
    { shape: "rect", label: "剧情线/故事弧线 (PlotLine/StoryArc)", color: "#8b5cf6" },
    { shape: "diamond", label: "事件 (Event)", color: "#c4b5fd" },
    { shape: "hexagon", label: "世界观/主题 (Worldbook/Theme)", color: "#7c3aed" },
    { shape: "triangle", label: "章节 (Chapter)", color: "#a78bfa" },
  ];

  return (
    <div className="cc-viz-panel" style={{ flex: 1, minHeight: 360, height: '100%', display: 'flex', flexDirection: 'column', width: '100%', gap: 0, overflow: 'hidden' }}>
      {/* Toolbar */}
      <div style={{ padding: '8px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: `1px solid ${colors.border}` }}>
        <div className="cc-graph-toolbar">
          <GraphTypeSelector value={graphType} onChange={setGraphType} />
          {/* Task 8: 书籍选择器 */}
          <select
            value={currentBookId == null ? '' : String(currentBookId)}
            onChange={(e) => {
              const v = e.target.value;
              setCurrentBookId(v ? Number(v) : null);
            }}
            disabled={booksLoading || books.length === 0}
            title="当前 book"
            style={{
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
          <span style={{ fontSize: 11, color: colors.textSecondary }}>
            {graphData.nodes.length} 个实体, {(graphData.links as any[]).length} 条关系
          </span>
          <button
            onClick={handleGenerateGraph}
            disabled={generating}
            title="让 AI 重新分析并补全人物关系 / 事件网络"
            style={{
              padding: '4px 10px', fontSize: 11, fontWeight: 600, color: '#fff',
              border: 'none', borderRadius: 5, cursor: generating ? 'not-allowed' : 'pointer',
              background: generating ? 'rgba(167,139,250,0.5)' : 'linear-gradient(135deg,#a78bfa,#7c3aed)',
            }}
          >
            {generating ? '生成中…' : '✨ 重建图谱'}
          </button>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* A1.1: 顶部 toolbar 显示 图谱来源 / 类型 / 生成时间 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {graphSource && (
              <span
                title={`数据来源：${graphSource}`}
                style={{
                  fontSize: 10, fontWeight: 600,
                  padding: '2px 8px', borderRadius: 999,
                  background: 'rgba(167, 139, 250, 0.12)',
                  border: '1px solid rgba(167, 139, 250, 0.3)',
                  color: '#c4b5fd',
                  whiteSpace: 'nowrap',
                }}
              >
                图谱来源：{graphSource}
              </span>
            )}
            {graphTypeLabel && (
              <span
                title={`图谱类型：${graphTypeLabel}`}
                style={{
                  fontSize: 10, fontWeight: 600,
                  padding: '2px 8px', borderRadius: 999,
                  background: 'rgba(124, 58, 237, 0.12)',
                  border: '1px solid rgba(124, 58, 237, 0.3)',
                  color: colors.textSecondary,
                  whiteSpace: 'nowrap',
                }}
              >
                类型：{graphTypeLabel}
              </span>
            )}
            {graphGeneratedAt && (
              <span
                title={`生成时间：${graphGeneratedAt}`}
                style={{
                  fontSize: 10, fontWeight: 500,
                  padding: '2px 8px', borderRadius: 999,
                  background: 'rgba(124, 58, 237, 0.06)',
                  border: '1px solid rgba(124, 58, 237, 0.2)',
                  color: colors.textSecondary,
                  whiteSpace: 'nowrap',
                }}
              >
                生成时间：{graphGeneratedAt}
              </span>
            )}
          </div>
          {/* Mini legend */}
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {presentTypes.slice(0, 5).map((type) => (
              <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: colors.textSecondary }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: typeColors[type] || colors.textSecondary, display: 'inline-block' }} />
                {typeLabels[type] || type}
              </div>
            ))}
          </div>
          {/* Legend toggle */}
          <button
            className="cc-btn cc-btn-icon"
            onClick={() => setLegendOpen(!legendOpen)}
            title={legendOpen ? "收起图例" : "展开图例"}
            style={{ fontSize: 14, padding: '4px 8px' }}
          >
            {legendOpen ? "\u25C0" : "\u25B6"}
          </button>
        </div>
      </div>

      {/* Graph area (2/3) */}
      <div ref={setContainerRef} style={{ flex: 2, minHeight: 0, position: 'relative', background: colors.background, overflow: 'hidden' }}>
        <svg ref={svgRef} width="100%" height="100%" style={{ background: colors.background }} />

        {/* Zoom controls */}
        <div style={{ position: 'absolute', bottom: 16, left: 16, display: 'flex', flexDirection: 'column', gap: 4 }}>
          <button className="cc-btn cc-btn-icon" onClick={zoomIn} title="放大" style={{ fontSize: 16, padding: '6px 10px' }}>+</button>
          <button className="cc-btn cc-btn-icon" onClick={zoomOut} title="缩小" style={{ fontSize: 16, padding: '6px 10px' }}>-</button>
          <button className="cc-btn cc-btn-icon" onClick={zoomReset} title="重置缩放" style={{ fontSize: 11, padding: '4px 8px' }}>⟲</button>
        </div>

        {/* Tooltip */}
        {tooltip && (
          <div
            className="cc-graph-tooltip"
            dangerouslySetInnerHTML={{ __html: tooltip.content }}
            style={{
              position: 'fixed',
              left: tooltip.x + 14,
              top: tooltip.y - 10,
              background: colors.inkCardStrong,
              border: `1px solid ${colors.border}`,
              borderRadius: 8,
              padding: '8px 12px',
              fontSize: 12,
              color: colors.text,
              lineHeight: 1.6,
              boxShadow: '0 8px 24px rgba(124, 58, 237, 0.15)',
              pointerEvents: 'none',
              zIndex: 9999,
              maxWidth: 260,
            }}
          />
        )}

        {/* Collapsible legend panel */}
        <div className={`cc-graph-legend ${legendOpen ? 'cc-graph-legend-open' : ''}`} style={{
          position: 'absolute',
          top: 12,
          right: 12,
          background: colors.inkCardStrong,
          border: `1px solid ${colors.border}`,
          borderRadius: 10,
          width: legendOpen ? 220 : 36,
          transition: 'width 250ms ease',
          overflow: 'hidden',
          backdropFilter: 'blur(8px)',
        }}>
          {legendOpen && (
            <div style={{ padding: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: colors.text, marginBottom: 10 }}>图例</div>

              {/* Node types */}
              <div style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>节点类型</div>
                {presentTypes.map((type) => (
                  <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, fontSize: 11, color: colors.textSecondary }}>
                    <span style={{ width: 12, height: 12, borderRadius: '50%', background: typeColors[type] || colors.textSecondary, display: 'inline-block', boxShadow: `0 0 6px ${typeColors[type] || colors.textSecondary}55` }} />
                    <span>{typeLabels[type] || type}</span>
                    <span style={{ marginLeft: 'auto', fontSize: 10, opacity: 0.6 }}>{graphData.nodes.filter((n: any) => n.type === type).length}</span>
                  </div>
                ))}
              </div>

              {/* Shapes */}
              <div style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>节点形状</div>
                {shapeLegend.map((s) => (
                  <div key={s.shape} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, fontSize: 10, color: colors.textSecondary }}>
                    <svg width="14" height="14">
                      {s.shape === "circle" && <circle cx="7" cy="7" r="5" fill={s.color} />}
                      {s.shape === "rect" && <rect x="2" y="4" width="10" height="6" rx="2" fill={s.color} />}
                      {s.shape === "diamond" && <polygon points="7,1 12,7 7,13 2,7" fill={s.color} />}
                      {s.shape === "hexagon" && <polygon points="7,1 12.5,4 12.5,10 7,13 1.5,10 1.5,4" fill={s.color} />}
                      {s.shape === "triangle" && <polygon points="7,1 13,13 1,13" fill={s.color} />}
                    </svg>
                    {s.label}
                  </div>
                ))}
              </div>

              {/* Relationship types */}
              {presentRelTypes.length > 0 && (
                <div>
                  <div style={{ fontSize: 10, fontWeight: 700, color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>关系类型</div>
                  {presentRelTypes.map((rel: string) => (
                    <div key={rel} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3, fontSize: 10, color: colors.textSecondary }}>
                      <svg width="24" height="10"><line x1="0" y1="5" x2="20" y2="5" stroke={colors.textSecondary} strokeWidth="1.5" /><polygon points="18,2 22,5 18,8" fill={colors.textSecondary} /></svg>
                      {truncate(relationLabel(rel), 18)}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Analysis panel (1/3) */}
      <div style={{ flex: 1, minHeight: 0, display: 'flex', borderTop: `1px solid ${colors.border}`, background: colors.inkCard }}>
        {/* Left: node type distribution */}
        <div style={{ flex: 1, padding: 12, overflow: 'auto', borderRight: `1px solid ${colors.border}`, display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
            <div style={{ fontSize: 22, fontWeight: 400, color: colors.text, fontFamily: 'var(--font-title)', letterSpacing: '0.02em' }}>节点类型分布</div>
            <div style={{ fontSize: 11, color: colors.textSecondary }}>
              共 {filteredGraphData?.nodes.length ?? 0} 节点 / {(filteredGraphData?.links as any[] | undefined)?.length ?? 0} 边 / {Object.keys(typeCount).length} 类型
            </div>
          </div>
          {/* 分类过滤条 —— 点击类型徽章切换过滤（"全部"清除过滤）*/}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
            <button
              type="button"
              onClick={() => setActiveTypeFilter("all")}
              style={{
                fontSize: 11, padding: '3px 8px', borderRadius: 12, cursor: 'pointer',
                border: `1px solid ${activeTypeFilter === "all" ? colors.accent : colors.border}`,
                background: activeTypeFilter === "all" ? 'rgba(124, 58, 237, 0.12)' : 'transparent',
                color: activeTypeFilter === "all" ? colors.accent : colors.textSecondary,
                fontWeight: activeTypeFilter === "all" ? 600 : 400,
              }}
            >
              全部
            </button>
            {Object.entries(typeCount)
              .sort((a, b) => b[1] - a[1])
              .map(([type, count]) => {
                const isActive = activeTypeFilter === type;
                return (
                  <button
                    key={type}
                    type="button"
                    onClick={() => setActiveTypeFilter(isActive ? "all" : type)}
                    style={{
                      fontSize: 11, padding: '3px 8px', borderRadius: 12, cursor: 'pointer',
                      border: `1px solid ${isActive ? colors.accent : colors.border}`,
                      background: isActive ? 'rgba(124, 58, 237, 0.12)' : 'transparent',
                      color: isActive ? colors.accent : colors.textSecondary,
                      fontWeight: isActive ? 600 : 400,
                      display: 'inline-flex', alignItems: 'center', gap: 4,
                    }}
                  >
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: typeColors[type] || colors.textSecondary, display: 'inline-block' }} />
                    {typeLabels[type] || type} · {count}
                  </button>
                );
              })}
          </div>
          <div ref={typeChartRef} style={{ width: '100%', flex: 1, minHeight: 0 }} />
        </div>

        {/* Right: Top 5 + warnings + suggestions */}
        <div style={{ flex: 1.5, padding: 12, overflow: 'auto' }}>
          <div style={{ fontSize: 22, fontWeight: 400, color: colors.text, marginBottom: 8, fontFamily: 'var(--font-title)', letterSpacing: '0.02em' }}>高连接度实体 Top 5</div>
          {topConnected.length === 0 && (
            <div style={{ fontSize: 12, color: colors.textSecondary, padding: '8px 0' }}>暂无数据</div>
          )}
          {topConnected.map((n, i) => (
            <div key={n.id} style={{ display: 'flex', alignItems: 'center', padding: '4px 0', fontSize: 12 }}>
              <span style={{ width: 18, color: colors.textSecondary }}>{i + 1}.</span>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: typeColors[n.type] || colors.textSecondary, marginRight: 6, display: 'inline-block' }} />
              <span style={{ flex: 1, color: colors.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{n.name || n.id}</span>
              <span style={{ color: colors.accent, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{n.degree}</span>
            </div>
          ))}

          {isolated.length > 0 && (
            <div style={{ marginTop: 12, padding: 8, background: 'rgba(217, 119, 6, 0.08)', borderLeft: `2px solid ${colors.warning}`, fontSize: 12, color: colors.warning, borderRadius: 4 }}>
              ⚠ 有 {isolated.length} 个孤立节点：{isolated.slice(0, 3).map((n) => n.name).join('、')}{isolated.length > 3 ? '…' : ''}
            </div>
          )}

          {topConnected.length >= 2 && topConnected[0].degree >= 3 && (
            <div style={{ marginTop: 8, padding: 8, background: 'rgba(124, 58, 237, 0.08)', borderLeft: `2px solid ${colors.accent}`, fontSize: 12, color: colors.textSecondary, borderRadius: 4 }}>
              💡 建议：「{topConnected[0].name}」是核心枢纽（连接 {topConnected[0].degree} 个关系），可考虑添加更多支线剧情
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
