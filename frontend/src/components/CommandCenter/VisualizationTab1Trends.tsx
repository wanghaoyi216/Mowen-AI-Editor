import React, { useEffect, useState, useMemo } from "react";
import ReactECharts from "echarts-for-react";
import {
  Tag, TrendingUp, Compass, Sparkles, ChevronRight, Search,
} from "lucide-react";
import { fetchTrendExplorations } from "../../lib/api";
import { colors, spacing, borderRadius } from "./styles";

interface VisualizationTab1TrendsProps {
  projectId?: number;
}

function parseJsonArray(value: unknown): any[] {
  if (Array.isArray(value)) return value;
  if (typeof value !== "string" || value.trim() === "") return [];
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

// 安全文本：替换数据库中可能存在的不可解码字符（之前 Tavily 截断在字节边界造成坏 UTF-8）
function safeText(s?: string | null): string {
  if (s == null) return "";
  return String(s).replace(/[\uFFFD\u0000-\u0008\u000B-\u001F]/g, "\u25A1");
}

function formatTime(iso?: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export function VisualizationTab1Trends({ projectId }: VisualizationTab1TrendsProps) {
  const [trends, setTrends] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const data = await fetchTrendExplorations(projectId as number);
        if (!cancelled) {
          setTrends(data);
          if (data.length > 0) setSelectedId((prev) => prev ?? data[0].id);
        }
      } catch {
        if (!cancelled) setTrends([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [projectId]);

  // 全部标签汇总
  const allTags = useMemo(() => {
    const map = new Map<string, number>();
    trends.forEach((t) => {
      parseJsonArray(t.extracted_tags).forEach((k: string) => {
        if (typeof k === "string" && k.trim()) {
          map.set(k, (map.get(k) || 0) + 1);
        }
      });
    });
    return Array.from(map.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 12)
      .map(([name, count]) => ({ name, count }));
  }, [trends]);

  // 7日趋势
  const last7Days = useMemo(() => {
    const days: { key: string; label: string; count: number }[] = [];
    const map: Record<string, number> = {};
    for (let i = 6; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      const key = d.toISOString().split("T")[0];
      const label = i === 0 ? "今天" : i === 1 ? "昨天" : `${i}天前`;
      days.push({ key, label, count: 0 });
      map[key] = 0;
    }
    trends.forEach((t) => {
      const date = t.created_at ? t.created_at.split("T")[0] : null;
      if (date && map[date] !== undefined) map[date]++;
    });
    return days.map((d) => ({ ...d, count: map[d.key] }));
  }, [trends]);

  // 过滤后的探索列表
  const filtered = useMemo(() => {
    if (!query.trim()) return trends;
    const q = query.toLowerCase();
    return trends.filter(
      (t) =>
        t.title?.toLowerCase().includes(q) ||
        t.query_text?.toLowerCase().includes(q) ||
        parseJsonArray(t.extracted_tags).some((k: string) => k.toLowerCase().includes(q)),
    );
  }, [trends, query]);

  const selected = useMemo(
    () => trends.find((t) => t.id === selectedId) || trends[0] || null,
    [trends, selectedId],
  );

  if (loading) {
    return (
      <div style={{ padding: spacing.xl, textAlign: "center", color: colors.textSecondary }}>
        加载趋势数据中…
      </div>
    );
  }

  if (trends.length === 0) {
    return (
      <div style={{ padding: spacing.xl, textAlign: "center", color: colors.textSecondary }}>
        <Compass size={32} style={{ opacity: 0.5, marginBottom: 8 }} />
        <div style={{ fontSize: 15, marginBottom: 6 }}>暂无热点探索数据</div>
        <div style={{ fontSize: 12 }}>AI 执行热点探索后将显示关键词分布、趋势时间线和探索结果</div>
      </div>
    );
  }

  // 标签水平条形图
  const tagBarOption = {
    tooltip: { trigger: "axis" as const, axisPointer: { type: "shadow" as const } },
    grid: { top: 10, right: 24, bottom: 10, left: 80, containLabel: false },
    xAxis: { type: "value" as const, show: false },
    yAxis: {
      type: "category" as const,
      data: allTags.map((t) => t.name).reverse(),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: colors.text, fontSize: 11 },
    },
    series: [{
      type: "bar" as const,
      data: allTags.map((t, i) => ({
        value: t.count,
        itemStyle: {
          color: { type: "linear" as const, x: 0, y: 0, x2: 1, y2: 0,
            colorStops: [
              { offset: 0, color: i < 3 ? "#f59e0b" : "#3b82f6" },
              { offset: 1, color: i < 3 ? "#fbbf24" : "#93c5fd" },
            ] },
          borderRadius: [0, 4, 4, 0],
        },
      })).reverse(),
      barWidth: 12,
      label: { show: true, position: "right" as const, color: colors.textSecondary, fontSize: 10, formatter: "{c} 次" },
    }],
  };

  // 7日趋势线
  const trendLineOption = {
    tooltip: { trigger: "axis" as const },
    grid: { top: 18, right: 16, bottom: 24, left: 36 },
    xAxis: {
      type: "category" as const,
      data: last7Days.map((d) => d.label),
      axisLine: { lineStyle: { color: colors.border } },
      axisLabel: { color: colors.textSecondary, fontSize: 10 },
    },
    yAxis: {
      type: "value" as const,
      minInterval: 1,
      axisLine: { lineStyle: { color: colors.border } },
      axisLabel: { color: colors.textSecondary, fontSize: 10 },
      splitLine: { lineStyle: { color: colors.border } },
    },
    series: [{
      data: last7Days.map((d) => d.count),
      type: "line" as const,
      smooth: true,
      symbol: "circle",
      symbolSize: 6,
      itemStyle: { color: colors.accent },
      lineStyle: { width: 2 },
      areaStyle: {
        color: { type: "linear" as const, x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: "rgba(59,130,246,0.35)" },
            { offset: 1, color: "rgba(59,130,246,0)" },
          ] },
      },
    }],
  };

  return (
    <div style={{ flex: 1, minHeight: 0, height: "100%", padding: spacing.md, display: "flex", flexDirection: "column", gap: spacing.md, overflow: "auto" }}>
      {/* 顶部指标条 */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: spacing.sm, flexShrink: 0 }}>
        <KpiTile label="探索次数" value={trends.length} accent={colors.accent} />
        <KpiTile label="累计标签" value={allTags.reduce((s, t) => s + t.count, 0)} accent={colors.paused} />
        <KpiTile label="唯一标签" value={allTags.length} accent="#a78bfa" />
        <KpiTile label="7日内新增" value={last7Days.reduce((s, d) => s + d.count, 0)} accent={colors.success} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: spacing.md, flex: 1, minHeight: 0 }}>
        {/* 左侧：探索列表 */}
        <div style={{ background: colors.cardBackground, border: `1px solid ${colors.border}`, borderRadius: borderRadius.md, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{ padding: "10px 12px", borderBottom: `1px solid ${colors.border}`, display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 700, color: colors.text }}>
              <Compass size={13} /> 探索列表
            </div>
            <div style={{ position: "relative" }}>
              <Search size={11} style={{ position: "absolute", left: 8, top: 7, color: colors.textSecondary }} />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="搜索标题 / 标签 / 关键词"
                style={{
                  width: "100%",
                  background: "#0d1117",
                  border: `1px solid ${colors.border}`,
                  borderRadius: borderRadius.sm,
                  padding: "6px 8px 6px 24px",
                  color: colors.text,
                  fontSize: 11,
                  outline: "none",
                }}
              />
            </div>
          </div>
          <div style={{ flex: 1, overflow: "auto", padding: 6 }}>
            {filtered.length === 0 && (
              <div style={{ padding: 16, fontSize: 11.5, color: colors.textSecondary, textAlign: "center" }}>
                没有匹配的探索
              </div>
            )}
            {filtered.map((t) => {
              const isActive = selected?.id === t.id;
              const tags = parseJsonArray(t.extracted_tags);
              return (
                <button
                  key={t.id}
                  onClick={() => setSelectedId(t.id)}
                  style={{
                    width: "100%",
                    textAlign: "left",
                    background: isActive ? "rgba(124,58,237,0.12)" : "transparent",
                    border: `1px solid ${isActive ? "rgba(124,58,237,0.35)" : "transparent"}`,
                    borderRadius: borderRadius.sm,
                    padding: "8px 10px",
                    marginBottom: 4,
                    cursor: "pointer",
                    transition: "all 0.12s",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 4 }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: colors.text, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {t.title}
                    </span>
                    <ChevronRight size={11} style={{ color: isActive ? colors.accent : colors.textSecondary, flexShrink: 0 }} />
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 4, flexWrap: "wrap", marginBottom: 4 }}>
                    {tags.slice(0, 3).map((tag: string, i: number) => (
                      <span key={i} style={{ fontSize: 9.5, color: "#fbbf24", background: "rgba(245,158,11,0.1)", padding: "1px 5px", borderRadius: 3 }}>
                        #{tag}
                      </span>
                    ))}
                    {tags.length > 3 && (
                      <span style={{ fontSize: 9.5, color: colors.textSecondary }}>+{tags.length - 3}</span>
                    )}
                  </div>
                  <div style={{ fontSize: 10, color: colors.textSecondary }}>{formatTime(t.created_at)}</div>
                </button>
              );
            })}
          </div>
        </div>

        {/* 右侧：详情 */}
        {selected ? (
          <div style={{ background: colors.cardBackground, border: `1px solid ${colors.border}`, borderRadius: borderRadius.md, display: "flex", flexDirection: "column", overflow: "hidden" }}>
            <div style={{ padding: "12px 16px", borderBottom: `1px solid ${colors.border}` }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: colors.text, marginBottom: 4 }}>
                {selected.title}
              </div>
              <div style={{ fontSize: 11, color: colors.textSecondary, display: "flex", gap: 8, alignItems: "center" }}>
                <span>{selected.source_scope || "—"}</span>
                <span>·</span>
                <span>{formatTime(selected.created_at)}</span>
                <span>·</span>
                <span style={{ color: selected.status === "completed" ? colors.success : colors.textSecondary }}>
                  {selected.status}
                </span>
              </div>
            </div>
            <div style={{ flex: 1, overflow: "auto", padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
              <Section icon={<Search size={12} />} title="查询关键词">
                <div style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                  {safeText(selected.query_text)}
                </div>
              </Section>

              {selected.raw_findings && (
                <Section icon={<TrendingUp size={12} />} title="调研发现">
                  <div style={{ fontSize: 12, color: colors.text, lineHeight: 1.7, whiteSpace: "pre-wrap" }}>
                    {safeText(selected.raw_findings)}
                  </div>
                </Section>
              )}

              {parseJsonArray(selected.extracted_topics).length > 0 && (
                <Section icon={<Sparkles size={12} />} title="核心洞察">
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {parseJsonArray(selected.extracted_topics).map((t: any, i: number) => (
                      <div key={i} style={{ padding: "6px 10px", background: "rgba(139,92,246,0.08)", border: "1px solid rgba(139,92,246,0.18)", borderRadius: 4, fontSize: 12, color: colors.text, lineHeight: 1.5 }}>
                        💡 {safeText(t.insight || t)}
                      </div>
                    ))}
                  </div>
                </Section>
              )}

              {parseJsonArray(selected.extracted_tags).length > 0 && (
                <Section icon={<Tag size={12} />} title="关键标签">
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {parseJsonArray(selected.extracted_tags).map((tag: string, i: number) => (
                      <span key={i} style={{ fontSize: 11, color: "#fbbf24", background: "rgba(245,158,11,0.12)", border: "1px solid rgba(245,158,11,0.25)", padding: "2px 8px", borderRadius: 10, fontWeight: 500 }}>
                        #{tag}
                      </span>
                    ))}
                  </div>
                </Section>
              )}

              {parseJsonArray(selected.suggested_directions).length > 0 && (
                <Section icon={<Compass size={12} />} title="建议方向">
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {parseJsonArray(selected.suggested_directions).map((d: any, i: number) => (
                      <div key={i} style={{ padding: "8px 10px", background: "rgba(124, 58, 237, 0.06)", border: "1px solid rgba(124, 58, 237, 0.2)", borderRadius: 4, fontSize: 12, color: colors.text, lineHeight: 1.5 }}>
                        📖 {d.premise || d}
                      </div>
                    ))}
                  </div>
                </Section>
              )}
            </div>
          </div>
        ) : (
          <div style={{ background: colors.cardBackground, border: `1px solid ${colors.border}`, borderRadius: borderRadius.md, display: "flex", alignItems: "center", justifyContent: "center", color: colors.textSecondary, fontSize: 12 }}>
            请选择左侧的探索项查看详情
          </div>
        )}
      </div>

      {/* 底部图表 */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: spacing.md, flexShrink: 0, height: 220 }}>
        <div style={{ background: colors.cardBackground, border: `1px solid ${colors.border}`, borderRadius: borderRadius.md, padding: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 600, color: colors.text, marginBottom: 6 }}>
            <Tag size={12} /> 高频标签 Top {allTags.length}
          </div>
          <ReactECharts option={tagBarOption} style={{ height: 170 }} />
        </div>
        <div style={{ background: colors.cardBackground, border: `1px solid ${colors.border}`, borderRadius: borderRadius.md, padding: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 600, color: colors.text, marginBottom: 6 }}>
            <TrendingUp size={12} /> 近 7 日探索频次
          </div>
          <ReactECharts option={trendLineOption} style={{ height: 170 }} />
        </div>
      </div>

      {/* 底部：AI 可执行的下一步建议（修复留空）*/}
      {selected && parseJsonArray(selected.suggested_directions).length > 0 && (
        <div style={{ background: colors.cardBackground, border: `1px solid ${colors.border}`, borderRadius: borderRadius.md, padding: 12, flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 700, color: colors.text, marginBottom: 8 }}>
            <Sparkles size={12} /> AI 可执行的下一步建议
            <span style={{ fontSize: 10, color: colors.textSecondary, fontWeight: 400, marginLeft: 'auto' }}>
              一键回填到章节大纲
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {parseJsonArray(selected.suggested_directions).map((d: any, i: number) => (
              <div key={i} style={{
                padding: '8px 10px',
                background: 'linear-gradient(135deg, rgba(59,130,246,0.08), rgba(139,92,246,0.05))',
                border: '1px solid rgba(59,130,246,0.18)',
                borderRadius: 6,
                display: 'flex', alignItems: 'center', gap: 8,
              }}>
                <span style={{ fontSize: 11, color: '#3b82f6', fontWeight: 600, minWidth: 18, flexShrink: 0 }}>{i + 1}.</span>
                <span style={{ fontSize: 12, color: colors.text, flex: 1, lineHeight: 1.5 }}>{safeText(d.premise || d)}</span>
                <button
                  style={{
                    background: 'transparent',
                    border: `1px solid ${colors.border}`,
                    borderRadius: 4,
                    padding: '2px 8px',
                    fontSize: 10.5,
                    color: colors.accent,
                    cursor: 'pointer',
                    flexShrink: 0,
                  }}
                  onClick={() => {
                    navigator.clipboard?.writeText(d.premise || String(d));
                  }}
                >复制</button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function KpiTile({ label, value, accent }: { label: string; value: number; accent: string }) {
  return (
    <div style={{
      background: colors.cardBackground,
      border: `1px solid ${colors.border}`,
      borderRadius: borderRadius.md,
      padding: "10px 12px",
      position: "relative",
      overflow: "hidden",
    }}>
      <div style={{ position: "absolute", top: 0, left: 0, width: 3, height: "100%", background: `linear-gradient(180deg, ${accent}, transparent)` }} />
      <div style={{ fontSize: 10.5, color: colors.textSecondary, marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color: colors.text, fontVariantNumeric: "tabular-nums" }}>
        {value}
      </div>
    </div>
  );
}

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, fontWeight: 700, color: colors.textSecondary, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 }}>
        {icon} {title}
      </div>
      {children}
    </div>
  );
}
