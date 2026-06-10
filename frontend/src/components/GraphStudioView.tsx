import * as d3 from "d3";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { fetchProjectGraph } from "../lib/api";
import type { GraphNode, GraphPayload, GraphRelationship } from "../types";

const canvasWidth = 820;
const canvasHeight = 520;

type SimNode = GraphNode & d3.SimulationNodeDatum;
type SimLink = GraphRelationship & d3.SimulationLinkDatum<SimNode>;

const nodeTheme: Record<string, { color: string; shape: "circle" | "rect" | "diamond"; size: number; icon: string }> = {
  character: { color: "#2865c7", shape: "circle", size: 19, icon: "角" },
  task: { color: "#475569", shape: "rect", size: 18, icon: "任" },
  task_step: { color: "#64748b", shape: "circle", size: 15, icon: "步" },
  plot: { color: "#9a6a14", shape: "diamond", size: 18, icon: "线" },
  plot_line: { color: "#9a6a14", shape: "diamond", size: 18, icon: "线" },
  event: { color: "#aa3a3a", shape: "diamond", size: 17, icon: "事" },
  story_event: { color: "#aa3a3a", shape: "diamond", size: 17, icon: "事" },
  chapter: { color: "#17756a", shape: "rect", size: 18, icon: "章" },
  chapter_plan: { color: "#0f766e", shape: "rect", size: 16, icon: "规" },
  worldbook: { color: "#6f4bb8", shape: "rect", size: 17, icon: "世" },
  worldbook_entry: { color: "#6f4bb8", shape: "rect", size: 17, icon: "世" },
  mixed: { color: "#475569", shape: "circle", size: 16, icon: "点" },
};

const relationTheme: Record<string, { color: string; dashed: boolean }> = {
  enemy: { color: "#aa3a3a", dashed: true },
  ally: { color: "#17756a", dashed: false },
  romance: { color: "#c45a8c", dashed: false },
  parent: { color: "#9a6a14", dashed: false },
  contains: { color: "#2865c7", dashed: false },
  triggers: { color: "#aa3a3a", dashed: false },
};

function getNodeTheme(type: string) {
  return nodeTheme[type] ?? nodeTheme.mixed;
}

function getRelationTheme(type: string) {
  const normalized = type.toLowerCase();
  return relationTheme[normalized] ?? { color: "#64748b", dashed: normalized.includes("候选") || normalized.includes("关联") };
}

function relationshipIntensity(relationship: GraphRelationship) {
  const raw = relationship.meta.intensity;
  return typeof raw === "number" ? raw : 1;
}

function nodeMatches(node: GraphNode, keyword: string) {
  if (!keyword.trim()) {
    return true;
  }
  const haystack = `${node.label} ${node.type} ${Object.values(node.meta).join(" ")}`.toLowerCase();
  return haystack.includes(keyword.trim().toLowerCase());
}

function getNeighborSet(nodeId: string | null, relationships: GraphRelationship[]) {
  const ids = new Set<string>();
  if (!nodeId) {
    return ids;
  }
  ids.add(nodeId);
  relationships.forEach((relationship) => {
    if (relationship.source === nodeId) {
      ids.add(relationship.target);
    }
    if (relationship.target === nodeId) {
      ids.add(relationship.source);
    }
  });
  return ids;
}

export function GraphStudioView({ projectId }: { projectId: number | null }) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const graphGroupRef = useRef<SVGGElement | null>(null);
  const zoomBehaviorRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const [graphType, setGraphType] = useState("story_entity");
  const [reloadToken, setReloadToken] = useState(0);
  const [graph, setGraph] = useState<GraphPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [keyword, setKeyword] = useState("");
  const [minIntensity, setMinIntensity] = useState(0);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [nodePositions, setNodePositions] = useState<Record<string, { x: number; y: number }>>({});
  const [undoStack, setUndoStack] = useState<d3.ZoomTransform[]>([d3.zoomIdentity]);
  const [redoStack, setRedoStack] = useState<d3.ZoomTransform[]>([]);

  useEffect(() => {
    let cancelled = false;

    async function loadGraph() {
      if (!projectId) {
        setGraph(null);
        setLoading(false);
        setError("请先在仪表盘选择项目。");
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const payload = await fetchProjectGraph(projectId, { graphType });
        if (!cancelled) {
          setGraph(payload);
          setSelectedNodeId(null);
          setHoveredNodeId(null);
          setNodePositions({});
        }
      } catch (loadError) {
        if (!cancelled) {
          setGraph(null);
          setError(loadError instanceof Error ? loadError.message : "Unknown error");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadGraph();
    return () => {
      cancelled = true;
    };
  }, [projectId, graphType, reloadToken]);

  const filteredRelationships = useMemo(
    () => (graph?.relationships ?? []).filter((relationship) => relationshipIntensity(relationship) >= minIntensity),
    [graph?.relationships, minIntensity],
  );

  const connectedNodeIds = useMemo(() => {
    const ids = new Set<string>();
    filteredRelationships.forEach((relationship) => {
      ids.add(relationship.source);
      ids.add(relationship.target);
    });
    return ids;
  }, [filteredRelationships]);

  const filteredNodes = useMemo(() => {
    const nodes = graph?.nodes ?? [];
    return nodes.filter((node) => {
      const relationVisible = filteredRelationships.length === 0 || connectedNodeIds.has(node.id);
      return relationVisible && nodeMatches(node, keyword);
    });
  }, [connectedNodeIds, filteredRelationships.length, graph?.nodes, keyword]);

  const visibleNodeIds = useMemo(() => new Set(filteredNodes.map((node) => node.id)), [filteredNodes]);
  const visibleRelationships = useMemo(
    () =>
      filteredRelationships.filter(
        (relationship) => visibleNodeIds.has(relationship.source) && visibleNodeIds.has(relationship.target),
      ),
    [filteredRelationships, visibleNodeIds],
  );

  const activeNodeId = hoveredNodeId ?? selectedNodeId;
  const neighborSet = useMemo(() => getNeighborSet(activeNodeId, visibleRelationships), [activeNodeId, visibleRelationships]);
  const selectedNode = useMemo(
    () => filteredNodes.find((node) => node.id === selectedNodeId) ?? null,
    [filteredNodes, selectedNodeId],
  );
  const selectedRelationships = useMemo(
    () =>
      selectedNode
        ? visibleRelationships.filter(
            (relationship) => relationship.source === selectedNode.id || relationship.target === selectedNode.id,
          )
        : [],
    [selectedNode, visibleRelationships],
  );

  const applyZoom = useCallback((transform: d3.ZoomTransform, pushHistory = true) => {
    if (!svgRef.current || !zoomBehaviorRef.current) {
      return;
    }
    d3.select(svgRef.current).call(zoomBehaviorRef.current.transform, transform);
    if (pushHistory) {
      setUndoStack((items) => [...items.slice(-12), transform]);
      setRedoStack([]);
    }
  }, []);

  useEffect(() => {
    const svgElement = svgRef.current;
    const groupElement = graphGroupRef.current;
    if (!svgElement || !groupElement || filteredNodes.length === 0) {
      return;
    }

    const svg = d3.select(svgElement);
    const group = d3.select(groupElement);
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.35, 3.8])
      .on("zoom", (event) => {
        group.attr("transform", event.transform.toString());
      })
      .on("end", (event) => {
        setUndoStack((items) => {
          const last = items[items.length - 1];
          if (last && last.toString() === event.transform.toString()) {
            return items;
          }
          return [...items.slice(-12), event.transform];
        });
        setRedoStack([]);
      });
    zoomBehaviorRef.current = zoom;
    svg.call(zoom);

    const nodes: SimNode[] = filteredNodes.map((node) => ({
      ...node,
      x: nodePositions[node.id]?.x ?? canvasWidth / 2 + (Math.random() - 0.5) * 80,
      y: nodePositions[node.id]?.y ?? canvasHeight / 2 + (Math.random() - 0.5) * 80,
    }));
    const nodeById = new Map(nodes.map((node) => [node.id, node]));
    const links: SimLink[] = visibleRelationships
      .filter((relationship) => nodeById.has(relationship.source) && nodeById.has(relationship.target))
      .map((relationship) => ({ ...relationship, source: relationship.source, target: relationship.target }));

    const simulation = d3
      .forceSimulation(nodes)
      .force(
        "link",
        d3
          .forceLink<SimNode, SimLink>(links)
          .id((node) => node.id)
          .distance((link) => 120 - Math.min(relationshipIntensity(link), 8) * 7),
      )
      .force("charge", d3.forceManyBody().strength(-380))
      .force("center", d3.forceCenter(canvasWidth / 2, canvasHeight / 2))
      .force("collision", d3.forceCollide<SimNode>().radius((node) => getNodeTheme(node.type).size + 34));

    simulation.on("tick", () => {
      const nextPositions: Record<string, { x: number; y: number }> = {};
      nodes.forEach((node) => {
        nextPositions[node.id] = {
          x: Math.max(42, Math.min(canvasWidth - 42, node.x ?? canvasWidth / 2)),
          y: Math.max(42, Math.min(canvasHeight - 42, node.y ?? canvasHeight / 2)),
        };
      });
      setNodePositions(nextPositions);
    });

    return () => {
      simulation.stop();
      svg.on(".zoom", null);
    };
  }, [filteredNodes, nodePositions, visibleRelationships]);

  useEffect(() => {
    function handleKeydown(event: KeyboardEvent) {
      if (!event.ctrlKey) {
        return;
      }
      if (event.key.toLowerCase() === "z") {
        event.preventDefault();
        setUndoStack((items) => {
          if (items.length <= 1) {
            return items;
          }
          const current = items[items.length - 1];
          const previous = items[items.length - 2];
          setRedoStack((redoItems) => [...redoItems, current]);
          applyZoom(previous, false);
          return items.slice(0, -1);
        });
      }
      if (event.key.toLowerCase() === "y") {
        event.preventDefault();
        setRedoStack((items) => {
          const next = items[items.length - 1];
          if (!next) {
            return items;
          }
          setUndoStack((undoItems) => [...undoItems, next]);
          applyZoom(next, false);
          return items.slice(0, -1);
        });
      }
    }
    window.addEventListener("keydown", handleKeydown);
    return () => window.removeEventListener("keydown", handleKeydown);
  }, [applyZoom]);

  const exportSvg = useCallback(() => {
    if (!svgRef.current) {
      return;
    }
    const serializer = new XMLSerializer();
    const source = serializer.serializeToString(svgRef.current);
    const blob = new Blob([source], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `graph-studio-${graphType}.svg`;
    anchor.click();
    URL.revokeObjectURL(url);
  }, [graphType]);

  const exportPng = useCallback(() => {
    if (!svgRef.current) {
      return;
    }
    const serializer = new XMLSerializer();
    const source = serializer.serializeToString(svgRef.current);
    const image = new Image();
    const svgBlob = new Blob([source], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(svgBlob);
    image.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = canvasWidth;
      canvas.height = canvasHeight;
      const context = canvas.getContext("2d");
      if (context) {
        context.fillStyle = "#f8fafc";
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.drawImage(image, 0, 0);
        const anchor = document.createElement("a");
        anchor.href = canvas.toDataURL("image/png");
        anchor.download = `graph-studio-${graphType}.png`;
        anchor.click();
      }
      URL.revokeObjectURL(url);
    };
    image.src = url;
  }, [graphType]);

  return (
    <section className="graph-studio-layout">
      <article className="panel graph-panel">
        <div className="panel-header">
          <h2>Graph Studio</h2>
          <span>{graph?.source ? `Source: ${graph.source}` : "D3 Force Graph"}</span>
        </div>

        <div className="toolbar graph-toolbar">
          <label className="field">
            <span>图谱类型</span>
            <select value={graphType} onChange={(event) => setGraphType(event.target.value)}>
              <option value="story_entity">故事实体 / 人物关系</option>
              <option value="character">仅人物关系</option>
              <option value="plot">剧情线</option>
              <option value="event">事件</option>
              <option value="task_workflow">任务执行流</option>
              <option value="chapter_structure">章节结构</option>
              <option value="worldbook">世界书</option>
            </select>
          </label>
          <label className="field grow">
            <span>全文搜索</span>
            <input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="节点名称 / 类型 / 属性" />
          </label>
          <label className="field range-field">
            <span>关系强度 ≥ {minIntensity}</span>
            <input
              type="range"
              min={0}
              max={10}
              step={0.5}
              value={minIntensity}
              onChange={(event) => setMinIntensity(Number(event.target.value))}
            />
          </label>
          <button type="button" onClick={() => setReloadToken((value) => value + 1)}>
            刷新
          </button>
          <button type="button" onClick={exportPng} disabled={!graph || graph.nodes.length === 0}>
            PNG
          </button>
          <button type="button" onClick={exportSvg} disabled={!graph || graph.nodes.length === 0}>
            SVG
          </button>
        </div>

        <div className="graph-canvas force-graph-canvas">
          {loading ? <p className="empty-state">图谱加载中...</p> : null}
          {!loading && error ? <p className="empty-state">图谱加载失败：{error}</p> : null}
          {!loading && !error && graph && graph.nodes.length === 0 ? (
            <p className="empty-state">当前项目没有图谱数据。先创建角色与关系即可显示。</p>
          ) : null}
          {!loading && !error && graph && graph.nodes.length > 0 ? (
            <svg ref={svgRef} viewBox={`0 0 ${canvasWidth} ${canvasHeight}`} className="graph-svg force-graph-svg" role="img">
              <defs>
                <marker id="arrow-head" viewBox="0 -5 10 10" refX="14" refY="0" markerWidth="6" markerHeight="6" orient="auto">
                  <path d="M0,-5L10,0L0,5" fill="#64748b" />
                </marker>
              </defs>
              <g ref={graphGroupRef}>
                {visibleRelationships.map((relationship) => {
                  const source = nodePositions[relationship.source];
                  const target = nodePositions[relationship.target];
                  if (!source || !target) {
                    return null;
                  }
                  const theme = getRelationTheme(relationship.type);
                  const dimmed = activeNodeId ? !neighborSet.has(relationship.source) || !neighborSet.has(relationship.target) : false;
                  const midX = (source.x + target.x) / 2;
                  const midY = (source.y + target.y) / 2;
                  return (
                    <g key={relationship.id} className={`force-edge${dimmed ? " dimmed" : ""}`}>
                      <line
                        x1={source.x}
                        y1={source.y}
                        x2={target.x}
                        y2={target.y}
                        stroke={theme.color}
                        strokeWidth={1.4 + relationshipIntensity(relationship) * 0.35}
                        strokeDasharray={theme.dashed ? "6 5" : undefined}
                        markerEnd="url(#arrow-head)"
                      />
                      <text x={midX} y={midY} fill={theme.color}>
                        {relationship.type}
                      </text>
                    </g>
                  );
                })}
                {filteredNodes.map((node) => {
                  const position = nodePositions[node.id];
                  if (!position) {
                    return null;
                  }
                  const theme = getNodeTheme(node.type);
                  const matched = nodeMatches(node, keyword);
                  const dimmed = activeNodeId ? !neighborSet.has(node.id) : keyword.trim() ? !matched : false;
                  const selected = selectedNodeId === node.id;
                  return (
                    <g
                      key={node.id}
                      className={`force-node${dimmed ? " dimmed" : ""}${selected ? " selected" : ""}`}
                      transform={`translate(${position.x}, ${position.y})`}
                      onMouseEnter={() => setHoveredNodeId(node.id)}
                      onMouseLeave={() => setHoveredNodeId(null)}
                      onClick={() => setSelectedNodeId((current) => (current === node.id ? null : node.id))}
                    >
                      {theme.shape === "circle" ? (
                        <circle r={theme.size} fill={theme.color} />
                      ) : theme.shape === "rect" ? (
                        <rect x={-theme.size} y={-theme.size} width={theme.size * 2} height={theme.size * 2} rx="6" fill={theme.color} />
                      ) : (
                        <rect
                          x={-theme.size}
                          y={-theme.size}
                          width={theme.size * 2}
                          height={theme.size * 2}
                          transform="rotate(45)"
                          rx="4"
                          fill={theme.color}
                        />
                      )}
                      <text className="force-node-icon" textAnchor="middle" y="4">
                        {theme.icon}
                      </text>
                      <text className="force-node-label" textAnchor="middle" y={theme.size + 18}>
                        {node.label}
                      </text>
                    </g>
                  );
                })}
              </g>
            </svg>
          ) : null}
        </div>
      </article>

      <article className="panel graph-detail-panel">
        <div className="panel-header">
          <h2>图谱详情</h2>
          <span>Nodes & Relationships</span>
        </div>
        <div className="graph-meta">
          <div className="info-chip">节点 {filteredNodes.length}/{graph?.nodes.length ?? 0}</div>
          <div className="info-chip">关系 {visibleRelationships.length}/{graph?.relationships.length ?? 0}</div>
          <div className="info-chip">强度 ≥ {minIntensity}</div>
        </div>

        {selectedNode ? (
          <div className="graph-selection-card">
            <strong>{selectedNode.label}</strong>
            <p>{selectedNode.type}</p>
            <dl>
              {Object.entries(selectedNode.meta).map(([key, value]) =>
                value == null ? null : (
                  <div key={key}>
                    <dt>{key}</dt>
                    <dd>{String(value)}</dd>
                  </div>
                ),
              )}
            </dl>
            <h3>关联关系</h3>
            <div className="graph-list compact-list">
              {selectedRelationships.map((relationship) => (
                <div className="task-item" key={relationship.id}>
                  <div>
                    <strong>{relationship.type}</strong>
                    <p>{relationship.source} → {relationship.target}</p>
                  </div>
                  <span className="badge badge-进行中">{relationshipIntensity(relationship)}</span>
                </div>
              ))}
              {selectedRelationships.length === 0 ? <p className="empty-state">暂无一度关联。</p> : null}
            </div>
          </div>
        ) : (
          <p className="hero-copy">点击节点查看实体属性和一度关联。滚轮缩放，拖动画布平移，Ctrl+Z / Ctrl+Y 可撤销或重做视图变换。</p>
        )}

        <div className="graph-list">
          {filteredNodes.map((node) => (
            <button
              type="button"
              className={`task-item selectable-card${node.id === selectedNodeId ? " selected-card" : ""}`}
              key={node.id}
              onClick={() => setSelectedNodeId(node.id)}
            >
              <div>
                <strong>{node.label}</strong>
                <p>
                  {node.type} / {node.meta.status ?? node.meta.category ?? "unknown"}
                </p>
              </div>
              <span className="badge badge-完成">{node.type}</span>
            </button>
          ))}
          {visibleRelationships.map((relationship) => (
            <div className="task-item" key={relationship.id}>
              <div>
                <strong>{relationship.type}</strong>
                <p>{relationship.meta.note ?? `${relationship.source} → ${relationship.target}`}</p>
              </div>
              <span className="badge badge-进行中">{relationshipIntensity(relationship)}</span>
            </div>
          ))}
        </div>
      </article>
    </section>
  );
}
