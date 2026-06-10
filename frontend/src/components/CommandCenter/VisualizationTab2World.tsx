import React, { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import {
  BookOpen, Bookmark, Users, MapPin, Sword, Box, ChevronRight, Search, Layers,
} from "lucide-react";
import { fetchWorldbookEntries } from "../../lib/api";
import { colors, spacing, borderRadius } from "./styles";

interface VisualizationTab2WorldProps {
  projectId?: number;
}

const CATEGORY_META: Record<string, { label: string; color: string; icon: React.ComponentType<{ size?: number; style?: React.CSSProperties }> }> = {
  setting:    { label: "设定",   color: "#a78bfa", icon: BookOpen },
  organization:{ label: "势力",   color: "#7c3aed", icon: Layers },
  character:  { label: "角色",   color: "#c4b5fd", icon: Users },
  item:       { label: "物品",   color: "#8b5cf6", icon: Sword },
  location:   { label: "地点",   color: "#a78bfa", icon: MapPin },
  other:      { label: "其他",   color: colors.idle, icon: Box },
};

function categoryMeta(key: string) {
  return CATEGORY_META[key] || CATEGORY_META.other;
}

export function VisualizationTab2World({ projectId }: VisualizationTab2WorldProps) {
  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [category, setCategory] = useState<string>("all");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const data = await fetchWorldbookEntries(projectId as number);
        if (!cancelled) {
          setEntries(data);
          if (data.length > 0) setSelectedId((prev) => prev ?? data[0].id);
        }
      } catch {
        if (!cancelled) setEntries([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [projectId]);

  const counts = useMemo(() => {
    const map: Record<string, number> = { all: entries.length };
    entries.forEach((e) => { map[e.category] = (map[e.category] || 0) + 1; });
    return map;
  }, [entries]);

  const filtered = useMemo(() => {
    return entries
      .filter((e) => category === "all" || e.category === category)
      .filter((e) => {
        if (!query.trim()) return true;
        const q = query.toLowerCase();
        return (
          e.title?.toLowerCase().includes(q) ||
          e.content?.toLowerCase().includes(q)
        );
      });
  }, [entries, category, query]);

  const selected = useMemo(
    () => entries.find((e) => e.id === selectedId) || filtered[0] || entries[0] || null,
    [entries, selectedId, filtered],
  );

  if (loading) {
    return (
      <div style={{ padding: spacing.xl, textAlign: "center", color: colors.textSecondary }}>
        加载世界书中…
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 12,
        padding: spacing.xl,
        color: colors.textSecondary,
      }}>
        <div style={{
          width: 72, height: 72, borderRadius: 16,
          display: "grid", placeItems: "center",
          background: "linear-gradient(135deg, rgba(124,58,237,0.12), rgba(139,92,246,0.06))",
          border: `1px solid ${colors.border}`,
        }}>
          <BookOpen size={32} style={{ color: colors.accent }} />
        </div>
        <div style={{ fontSize: 16, color: colors.text, fontWeight: 600 }}>暂无世界书数据</div>
        <div style={{ fontSize: 12, maxWidth: 380, lineHeight: 1.7, textAlign: "center" }}>
          AI 完成「构建世界观」阶段后，将自动写入设定 / 势力 / 角色 / 物品 / 地点等条目。
        </div>
        <div style={{
          marginTop: 8, fontSize: 11, padding: "4px 10px",
          borderRadius: 12, color: colors.accent,
          background: "rgba(124,58,237,0.08)", border: `1px solid rgba(124,58,237,0.2)`,
        }}>
          前往「AI 控制台」启动 world 阶段
        </div>
      </div>
    );
  }

  // 分类饼图
  const pieOption = {
    backgroundColor: "transparent",
    tooltip: { trigger: "item" as const, formatter: "{b}: {c} 条 ({d}%)" },
    legend: { show: false },
    series: [{
      type: "pie" as const,
      radius: ["40%", "70%"],
      center: ["50%", "50%"],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 4, borderColor: colors.background, borderWidth: 2 },
      label: {
        show: true,
        position: "outside" as const,
        formatter: "{b|{b}}\n{d|{d}%}",
        rich: {
          b: { color: colors.text, fontSize: 10 },
          d: { color: colors.textSecondary, fontSize: 9 },
        },
      },
      labelLine: { length: 6, length2: 6 },
      data: Object.entries(counts)
        .filter(([k]) => k !== "all")
        .filter(([k]) => counts[k] > 0)
        .map(([k, v]) => ({
          name: categoryMeta(k).label,
          value: v,
          itemStyle: { color: categoryMeta(k).color },
        })),
    }],
  };

  return (
    <div style={{ flex: 1, minHeight: 0, height: "100%", padding: spacing.md, display: "flex", flexDirection: "column", gap: spacing.md, overflow: "hidden" }}>
      {/* 顶部 KPI */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: spacing.sm, flexShrink: 0 }}>
        <KpiTile label="世界书条目" value={entries.length} accent={colors.accent} icon={<BookOpen size={14} />} />
        <KpiTile label="角色设定"   value={counts.character || 0}    accent="#a78bfa" icon={<Users size={14} />} />
        <KpiTile label="势力组织"   value={counts.organization || 0} accent="#7c3aed" icon={<Layers size={14} />} />
        <KpiTile label="场景地点"   value={counts.location || 0}     accent="#c4b5fd" icon={<MapPin size={14} />} />
        <KpiTile label="核心物品"   value={counts.item || 0}         accent="#8b5cf6" icon={<Sword size={14} />} />
        <KpiTile label="世界设定"   value={counts.setting || 0}      accent="#a78bfa" icon={<Bookmark size={14} />} />
      </div>

      {/* 分类筛选 + 饼图 */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: spacing.md, flexShrink: 0 }}>
        <div style={{ background: colors.cardBackground, border: `1px solid ${colors.border}`, borderRadius: borderRadius.md, padding: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: colors.textSecondary, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 }}>
            分类筛选
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            <Chip
              active={category === "all"}
              onClick={() => setCategory("all")}
              color="#64748b"
              count={entries.length}
            >全部</Chip>
            {Object.keys(CATEGORY_META).filter((k) => k !== "all" && k !== "other").map((k) => {
              const meta = categoryMeta(k);
              const Icon = meta.icon;
              const c = counts[k] || 0;
              if (c === 0) return null;
              return (
                <Chip
                  key={k}
                  active={category === k}
                  onClick={() => setCategory(k)}
                  color={meta.color}
                  count={c}
                  icon={<Icon size={10} />}
                >{meta.label}</Chip>
              );
            })}
          </div>
        </div>
        <div style={{ background: colors.cardBackground, border: `1px solid ${colors.border}`, borderRadius: borderRadius.md, padding: 10, display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <ReactECharts option={pieOption} style={{ height: 100, width: 100 }} />
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 4, fontSize: 11 }}>
              {Object.entries(counts)
                .filter(([k, v]) => k !== "all" && v > 0)
                .map(([k, v]) => (
                  <div key={k} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ width: 10, height: 10, borderRadius: 2, background: categoryMeta(k).color, flexShrink: 0 }} />
                    <span style={{ color: colors.text, flex: 1 }}>{categoryMeta(k).label}</span>
                    <span style={{ color: colors.textSecondary, fontVariantNumeric: "tabular-nums", minWidth: 32, textAlign: 'right' }}>{v} 条</span>
                  </div>
                ))}
            </div>
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: spacing.md, flex: 1, minHeight: 0 }}>
        {/* 左侧：列表 */}
        <div style={{ background: colors.cardBackground, border: `1px solid ${colors.border}`, borderRadius: borderRadius.md, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{ padding: "10px 12px", borderBottom: `1px solid ${colors.border}`, display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 700, color: colors.text }}>
              <Bookmark size={13} /> 条目列表（{filtered.length}）
            </div>
            <div style={{ position: "relative" }}>
              <Search size={11} style={{ position: "absolute", left: 8, top: 7, color: colors.textSecondary }} />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="搜索标题 / 内容关键词"
                style={{
                  width: "100%",
                  background: colors.inkCard,
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
                没有匹配的条目
              </div>
            )}
            {filtered.map((e) => {
              const meta = categoryMeta(e.category);
              const Icon = meta.icon;
              const isActive = selected?.id === e.id;
              return (
                <button
                  key={e.id}
                  onClick={() => setSelectedId(e.id)}
                  style={{
                    width: "100%",
                    textAlign: "left",
                    background: isActive ? colors.inkAccentSoft : "transparent",
                    border: `1px solid ${isActive ? "rgba(124, 58, 237, 0.35)" : "transparent"}`,
                    borderRadius: borderRadius.sm,
                    padding: "8px 10px",
                    marginBottom: 4,
                    cursor: "pointer",
                    transition: "all 0.12s",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                    <span style={{
                      width: 18, height: 18, borderRadius: 3,
                      background: meta.color, display: "flex", alignItems: "center", justifyContent: "center",
                      flexShrink: 0,
                    }}>
                      <Icon size={11} style={{ color: "#fff" }} />
                    </span>
                    <span style={{ fontSize: 12, fontWeight: 600, color: colors.text, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {e.title}
                    </span>
                    <ChevronRight size={11} style={{ color: isActive ? colors.accent : colors.textSecondary, flexShrink: 0 }} />
                  </div>
                  <div style={{ fontSize: 10.5, color: colors.textSecondary, lineHeight: 1.4, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                    {e.content}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* 右侧：详情 */}
        {selected ? (
          <div style={{ background: colors.cardBackground, border: `1px solid ${colors.border}`, borderRadius: borderRadius.md, display: "flex", flexDirection: "column", overflow: "hidden" }}>
            <div style={{ padding: "12px 16px", borderBottom: `1px solid ${colors.border}` }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                {(() => {
                  const meta = categoryMeta(selected.category);
                  const Icon = meta.icon;
                  return (
                    <span style={{
                      display: "inline-flex", alignItems: "center", gap: 4,
                      fontSize: 10, fontWeight: 600, color: "#fff",
                      background: meta.color, padding: "2px 8px", borderRadius: 10,
                    }}>
                      <Icon size={10} /> {meta.label}
                    </span>
                  );
                })()}
                {selected.source_type && (
                  <span style={{ fontSize: 10, color: colors.textSecondary, background: "rgba(148,163,184,0.12)", padding: "2px 8px", borderRadius: 10 }}>
                    {selected.source_type}
                  </span>
                )}
              </div>
              <div style={{ fontSize: 16, fontWeight: 700, color: colors.text }}>
                {selected.title}
              </div>
            </div>
            <div style={{ flex: 1, overflow: "auto", padding: 18 }}>
              <div style={{
                fontSize: 13,
                color: colors.text,
                lineHeight: 1.85,
                whiteSpace: "pre-wrap",
                letterSpacing: 0.2,
              }}>
                {selected.content}
              </div>
              {selected.source_ref && (
                <div style={{ marginTop: 18, paddingTop: 14, borderTop: `1px dashed ${colors.border}`, fontSize: 10.5, color: colors.textSecondary }}>
                  <span style={{ opacity: 0.7 }}>来源引用：</span>
                  <code style={{ background: colors.inkCard, padding: "1px 6px", borderRadius: 3, fontFamily: "monospace" }}>
                    {selected.source_ref}
                  </code>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div style={{ background: colors.cardBackground, border: `1px solid ${colors.border}`, borderRadius: borderRadius.md, display: "flex", alignItems: "center", justifyContent: "center", color: colors.textSecondary, fontSize: 12 }}>
            请选择左侧的条目查看完整内容
          </div>
        )}
      </div>

      {/* 底部：按角色归类的世界书引用（修复留空）*/}
      {(() => {
        const charNames = entries.filter(e => e.category === 'character').map(e => e.title.split('（')[0].trim());
        if (charNames.length === 0) return null;
        return (
          <div style={{ background: colors.cardBackground, border: `1px solid ${colors.border}`, borderRadius: borderRadius.md, padding: 12, flexShrink: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 700, color: colors.text, marginBottom: 10 }}>
              <Users size={12} /> 角色 × 世界书引用
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 8 }}>
              {charNames.slice(0, 8).map(name => {
                const refs = entries.filter(e =>
                  e.category !== 'character' && e.content?.includes(name)
                );
                return (
                  <div key={name} style={{
                    background: colors.inkCard,
                    border: `1px solid ${colors.border}`,
                    borderRadius: 6, padding: '6px 8px',
                  }}>
                    <div style={{ fontSize: 11.5, color: colors.text, fontWeight: 600, marginBottom: 4 }}>{name}</div>
                    <div style={{ fontSize: 10, color: colors.textSecondary, lineHeight: 1.5 }}>
                      出现在 {refs.length} 个条目中
                      {refs.length > 0 && (
                        <div style={{ marginTop: 3, display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                          {refs.slice(0, 3).map(r => (
                            <span key={r.id} style={{ background: 'rgba(124, 58, 237, 0.1)', color: colors.textSecondary, padding: '1px 5px', borderRadius: 3 }}>{r.title}</span>
                          ))}
                          {refs.length > 3 && <span style={{ color: colors.textSecondary }}>+{refs.length - 3}</span>}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })()}
    </div>
  );
}

function KpiTile({ label, value, accent, icon }: { label: string; value: number; accent: string; icon: React.ReactNode }) {
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
      <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 10.5, color: colors.textSecondary, marginBottom: 4 }}>
        <span style={{ color: accent }}>{icon}</span> {label}
      </div>
      <div style={{ fontSize: 22, fontWeight: 700, color: colors.text, fontVariantNumeric: "tabular-nums" }}>
        {value}
      </div>
    </div>
  );
}

function Chip({
  active, onClick, color, count, icon, children,
}: {
  active: boolean;
  onClick: () => void;
  color: string;
  count?: number;
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        display: "inline-flex", alignItems: "center", gap: 5,
        background: active ? `${color}25` : colors.inkCard,
        border: `1px solid ${active ? color : colors.border}`,
        color: active ? color : colors.textSecondary,
        padding: "4px 10px",
        borderRadius: 12,
        fontSize: 11.5,
        fontWeight: 500,
        cursor: "pointer",
        transition: "all 0.12s",
      }}
    >
      {icon}
      {children}
      {typeof count === "number" && (
        <span style={{ fontSize: 10, opacity: 0.85, fontVariantNumeric: "tabular-nums" }}>· {count}</span>
      )}
    </button>
  );
}
