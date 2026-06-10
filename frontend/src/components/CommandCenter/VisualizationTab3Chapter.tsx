import React, { useEffect, useState } from "react";
import ReactECharts from "echarts-for-react";
import { Target, Zap, Users, BookOpen, ChevronDown, ChevronUp, Sparkles, MapPin, FileDown, Loader2, CheckCircle2 } from "lucide-react";
import type { Chapter, ChapterVersion } from "../../types";
import { colors } from "./styles";
import { MarkdownRenderer } from "./MarkdownRenderer";
import {
  exportChapterAs,
  fetchChapterScenes,
  type ChapterScene,
  type ChapterExportFormat,
} from "../../lib/api";
import { ExportMenu, type ExportActionOption } from "../ExportMenu";

interface VisualizationTab3ChapterProps {
  projectId?: number;
}

export function VisualizationTab3Chapter({ projectId }: VisualizationTab3ChapterProps) {
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedChapterId, setExpandedChapterId] = useState<number | null>(null);
  const [chapterVersions, setChapterVersions] = useState<Record<number, ChapterVersion[]>>({});
  const [versionsLoading, setVersionsLoading] = useState<Record<number, boolean>>({});
  const [exportingChapterId, setExportingChapterId] = useState<number | null>(null);
  const [scenesByChapter, setScenesByChapter] = useState<Record<number, ChapterScene[]>>({});
  const [scenesLoading, setScenesLoading] = useState<Record<number, boolean>>({});

  useEffect(() => {
    if (!projectId) return;
    const currentProjectId = projectId;
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const { fetchChapters } = await import("../../lib/api");
        const data = await fetchChapters(currentProjectId);
        if (!cancelled) setChapters(data);
      } catch {
        if (!cancelled) setChapters([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [projectId]);

  async function loadChapterVersions(chapterId: number) {
    if (chapterVersions[chapterId]) return;
    setVersionsLoading((prev) => ({ ...prev, [chapterId]: true }));
    try {
      const { fetchChapterVersions } = await import("../../lib/api");
      const versions = await fetchChapterVersions(projectId!, chapterId);
      setChapterVersions((prev) => ({ ...prev, [chapterId]: versions }));
    } catch {
      setChapterVersions((prev) => ({ ...prev, [chapterId]: [] }));
    } finally {
      setVersionsLoading((prev) => ({ ...prev, [chapterId]: false }));
    }
  }

  async function loadChapterScenes(chapterId: number) {
    if (scenesByChapter[chapterId]) return;
    setScenesLoading((prev) => ({ ...prev, [chapterId]: true }));
    try {
      const { scenes } = await fetchChapterScenes(projectId!, chapterId);
      setScenesByChapter((prev) => ({ ...prev, [chapterId]: scenes }));
    } catch {
      setScenesByChapter((prev) => ({ ...prev, [chapterId]: [] }));
    } finally {
      setScenesLoading((prev) => ({ ...prev, [chapterId]: false }));
    }
  }

  function toggleChapter(chapterId: number) {
    if (expandedChapterId === chapterId) {
      setExpandedChapterId(null);
    } else {
      setExpandedChapterId(chapterId);
      void loadChapterVersions(chapterId);
      void loadChapterScenes(chapterId);
    }
  }

  // 章节导出格式选项（与 ExportMenu 协作）
  const chapterExportOptions: ExportActionOption<ChapterExportFormat>[] = [
    { format: "md",   label: "Markdown", description: "纯文本 + Markdown 标记", default: true },
    { format: "docx", label: "Word 文档", description: "Microsoft Word 原生格式" },
    { format: "pdf",  label: "PDF",      description: "排版固定" },
    { format: "txt",  label: "TXT",      description: "无格式标记" },
  ];

  async function handleExportChapterMenu(chapter: Chapter, fmt: ChapterExportFormat): Promise<{ blob: Blob; filename: string }> {
    if (!projectId) throw new Error("项目未选择");
    const blob = await exportChapterAs(projectId, chapter.id, fmt);
    const safeTitle = (chapter.title || `chapter_${chapter.chapter_no || chapter.id}`)
      .replace(/[<>:"/\\|?*]/g, "_")
      .trim() || `chapter_${chapter.chapter_no || chapter.id}`;
    const filename = `第${String(chapter.chapter_no ?? chapter.id).padStart(2, "0")}章_${safeTitle}.${fmt}`;
    return { blob, filename };
  }

  if (loading) {
    return <div style={{ padding: 40, textAlign: 'center', color: colors.textSecondary }}>加载章节数据中...</div>;
  }

  if (chapters.length === 0) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: colors.textSecondary }}>
        <div style={{ fontSize: 16, marginBottom: 8 }}>暂无章节数据</div>
        <div style={{ fontSize: 13 }}>AI 执行章节写作后将显示字数趋势、状态分布和章节列表</div>
      </div>
    );
  }

  // 后端实际枚举：planned / drafted / completed
  // 前端历史曾用 drafting，这里兼容旧字段
  const statusColors: Record<string, string> = {
    completed: colors.success,
    drafted:   colors.warning,
    drafting:  colors.warning,   // 兼容旧字段
    planned:   colors.idle,
  };

  const statusLabels: Record<string, string> = {
    completed: "已完成",
    drafted:   "已起草",
    drafting:  "撰写中",         // 兼容旧字段
    planned:   "规划中",
  };

  const totalWords = chapters.reduce(
    (sum, c) => sum + (c.word_count ?? c.wordCount ?? 0), 0
  );
  const completedCount = chapters.filter(
    (c) => c.status === 'completed' || c.status === 'drafted'
  ).length;
  const avgWords = chapters.length > 0 ? Math.round(totalWords / chapters.length) : 0;

  const sortedChapters = [...chapters].sort((a, b) => (a.chapter_no || a.id) - (b.chapter_no || b.id));

  const lineOption = {
    backgroundColor: "transparent",
    tooltip: { trigger: 'axis' as const, formatter: (params: any) => {
      const item = params[0];
      const chapter = sortedChapters[item.dataIndex];
      const wc = chapter.word_count ?? chapter.wordCount ?? 0;
      return `第${chapter.chapter_no || chapter.id}章 - ${chapter.title || '未命名'}<br/>字数: ${wc.toLocaleString()}`;
    }},
    grid: { top: 20, bottom: 60, left: 60, right: 20 },
    xAxis: {
      type: 'category' as const,
      data: sortedChapters.map((c) => `第${c.chapter_no || c.id}章`),
      axisLine: { lineStyle: { color: colors.border } },
      axisLabel: { color: colors.textSecondary, rotate: 30, fontSize: 11 },
    },
    yAxis: {
      type: 'value' as const,
      name: '字数',
      axisLine: { lineStyle: { color: colors.border } },
      axisLabel: { color: colors.textSecondary, formatter: (v: number) => `${(v / 1000).toFixed(1)}k` },
      splitLine: { lineStyle: { color: colors.border } },
    },
    series: [{
      name: '字数',
      type: 'line' as const,
      data: sortedChapters.map((c) => c.word_count ?? c.wordCount ?? 0),
      smooth: true,
      areaStyle: {
        color: {
          type: 'linear' as const,
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(124, 58, 237, 0.4)' },
            { offset: 1, color: 'rgba(124, 58, 237, 0)' },
          ],
        },
      },
      itemStyle: { color: colors.accent },
      lineStyle: { width: 2, color: colors.accent },
    }],
  };

  const statusPieOption = {
    tooltip: { trigger: 'item' as const, formatter: '{b}: {c} 章 ({d}%)' },
    legend: { orient: 'vertical' as const, left: 'left', textStyle: { color: colors.textSecondary, fontSize: 11 } },
    series: [{
      type: 'pie' as const,
      radius: ['40%', '70%'],
      center: ['60%', '55%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 6, borderColor: colors.background, borderWidth: 2 },
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold', color: colors.text } },
      data: Object.entries(statusLabels).map(([key, label]) => ({
        value: chapters.filter((c) => c.status === key).length,
        name: label,
        itemStyle: { color: statusColors[key] || colors.textSecondary },
      })),
    }],
  };

  return (
    <div style={{ flex: 1, minHeight: 0, height: '100%', padding: 16, display: 'flex', flexDirection: 'column', gap: 16, overflow: 'auto' }}>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 120, background: colors.cardBackground, border: `1px solid ${colors.border}`, borderRadius: 8, padding: 12 }}>
          <div style={{ fontSize: 11, color: colors.textSecondary, marginBottom: 4 }}>总章节数</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: colors.text }}>{chapters.length}</div>
        </div>
        <div style={{ flex: 1, minWidth: 120, background: colors.cardBackground, border: `1px solid ${colors.border}`, borderRadius: 8, padding: 12 }}>
          <div style={{ fontSize: 11, color: colors.textSecondary, marginBottom: 4 }}>已完成</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: colors.success }}>{completedCount}</div>
        </div>
        <div style={{ flex: 1, minWidth: 120, background: colors.cardBackground, border: `1px solid ${colors.border}`, borderRadius: 8, padding: 12 }}>
          <div style={{ fontSize: 11, color: colors.textSecondary, marginBottom: 4 }}>总字数</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: colors.text }}>{totalWords.toLocaleString()}</div>
        </div>
        <div style={{ flex: 1, minWidth: 120, background: colors.cardBackground, border: `1px solid ${colors.border}`, borderRadius: 8, padding: 12 }}>
          <div style={{ fontSize: 11, color: colors.textSecondary, marginBottom: 4 }}>均章字数</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: colors.text }}>{avgWords.toLocaleString()}</div>
        </div>
      </div>

      <h3 style={{ margin: 0, fontSize: 14, color: colors.text }}>章节字数趋势</h3>
      <ReactECharts option={lineOption} style={{ height: 220 }} />

      <div style={{ display: 'flex', gap: 16 }}>
        <div style={{ flex: 1 }}>
          <h3 style={{ margin: '0 0 8px', fontSize: 14, color: colors.text }}>章节状态分布</h3>
          <ReactECharts option={statusPieOption} style={{ height: 220 }} />
        </div>
        <div style={{ flex: 1.5 }}>
          <h3 style={{ margin: '0 0 8px', fontSize: 14, color: colors.text }}>章节列表</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 400, overflow: 'auto' }}>
            {sortedChapters.map((c) => {
              const isExpanded = expandedChapterId === c.id;
              const versions = chapterVersions[c.id] || [];
              const latestVersion = versions.length > 0 ? versions[versions.length - 1] : null;
              const isLoadingVersions = versionsLoading[c.id];
              const isExporting = exportingChapterId === c.id;
              const scenes = scenesByChapter[c.id] || [];
              const isLoadingScenes = scenesLoading[c.id];

              return (
                <div key={c.id}>
                  <div
                    onClick={() => toggleChapter(c.id)}
                    style={{
                      background: colors.cardBackground,
                      border: `1px solid ${isExpanded ? colors.accent : colors.border}`,
                      borderLeft: isExpanded ? `3px solid ${colors.accent}` : undefined,
                      borderRadius: 8,
                      padding: 10,
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      cursor: 'pointer',
                      transition: 'all 0.15s',
                      boxShadow: isExpanded ? `0 0 0 1px ${colors.accent}33` : 'none',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span style={{
                        width: 8, height: 8, borderRadius: '50%',
                        background: statusColors[c.status] || colors.textSecondary,
                        display: 'inline-block',
                        boxShadow: `0 0 6px ${statusColors[c.status] || colors.textSecondary}`,
                      }} />
                      <span style={{
                        fontSize: 10, color: colors.textSecondary,
                        background: 'rgba(124, 58, 237, 0.08)',
                        padding: '1px 6px',
                        borderRadius: 4,
                        fontFamily: 'ui-monospace, monospace',
                        fontWeight: 600,
                      }}>
                        Ch.{(c.chapter_no || c.id).toString().padStart(2, '0')}
                      </span>
                      <span style={{ fontSize: 13, fontWeight: 600, color: colors.text }}>{c.title || `第${c.chapter_no || c.id}章`}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span style={{ fontSize: 11.5, color: colors.textSecondary, fontFamily: 'ui-monospace, monospace' }}>
                        {((c.word_count ?? c.wordCount ?? 0)).toLocaleString()} 字
                      </span>
                      <span style={{
                        fontSize: 10, color: statusColors[c.status] || colors.textSecondary,
                        background: `${statusColors[c.status] || colors.textSecondary}1a`,
                        padding: '1px 8px',
                        borderRadius: 8,
                        fontWeight: 600,
                      }}>
                        {statusLabels[c.status] || c.status}
                      </span>
                      {isExpanded
                        ? <ChevronUp size={12} color={colors.textSecondary} />
                        : <ChevronDown size={12} color={colors.textSecondary} />}
                    </div>
                  </div>

                  {isExpanded && (
                    <div style={{
                      marginLeft: 16,
                      marginTop: 4,
                      background: colors.inkCard,
                      border: `1px solid ${colors.border}`,
                      borderRadius: 8,
                      padding: 12,
                    }}>
                      {isLoadingVersions && (
                        <div style={{ fontSize: 12, color: colors.textSecondary, textAlign: 'center', padding: 8 }}>
                          加载内容中...
                        </div>
                      )}

                      {!isLoadingVersions && c.status === 'completed' && latestVersion && (
                        <div>
                          <div style={{ fontSize: 11, color: colors.textSecondary, marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span>最新版本 v{latestVersion.version_no} ({latestVersion.content?.length || 0} 字)</span>
                            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                              {latestVersion.consistency_report && (
                                <span style={{ color: colors.success }}>✓ 一致性检查已完成</span>
                              )}
                              {/* 导出：点按钮弹菜单选格式，弹原生保存对话框选位置 */}
                              <ExportMenu<ChapterExportFormat>
                                label="导出"
                                options={chapterExportOptions}
                                onExport={(fmt) => handleExportChapterMenu(c, fmt)}
                                disabled={isExporting}
                                busy={isExporting}
                                buttonClassName="viz3-export-btn"
                              />
                            </div>
                          </div>
                          <div style={{
                            fontSize: 13.5,
                            lineHeight: 1.85,
                            color: colors.text,
                            letterSpacing: 0.2,
                            maxHeight: 600,
                            overflowY: 'auto',
                            padding: '4px 2px',
                          }}>
                            <MarkdownContent content={latestVersion.content} />
                          </div>
                        </div>
                      )}

                      {!isLoadingVersions && c.status === 'completed' && versions.length === 0 && (
                        <div style={{ fontSize: 12, color: colors.textSecondary, textAlign: 'center', padding: 8 }}>
                          暂无版本内容
                        </div>
                      )}

                      {!isLoadingVersions && c.status !== 'completed' && (
                        <div style={{ fontSize: 12, color: colors.textSecondary, textAlign: 'center', padding: 8 }}>
                          {c.status === 'planned' ? '章节尚未开始写作' : '章节正在写作中...'}
                        </div>
                      )}

                      {/* 章节小结 (scenes) - 可折叠 */}
                      <details style={{ marginTop: 14 }} open>
                        <summary style={{
                          display: 'flex', alignItems: 'center', gap: 6,
                          fontSize: 11, fontWeight: 700, color: colors.accent,
                          marginBottom: 8, letterSpacing: 0.4, textTransform: 'uppercase',
                          cursor: 'pointer', listStyle: 'none',
                        }}>
                          <BookOpen size={12} />
                          <span>本章场景</span>
                          <span style={{
                            background: `${colors.accent}22`,
                            color: colors.accent,
                            padding: '1px 7px', borderRadius: 8,
                            fontSize: 10, fontWeight: 700,
                          }}>{scenes.length}</span>
                          <span style={{ marginLeft: 'auto', fontSize: 10, color: colors.textSecondary }}>点击折叠</span>
                        </summary>
                        <ChapterScenes
                          scenes={scenes}
                          loading={isLoadingScenes}
                        />
                      </details>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function ChapterScenes({
  scenes,
  loading,
}: {
  scenes: ChapterScene[];
  loading: boolean;
}) {
  if (loading) {
    return (
      <div style={{ marginTop: 14, display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: colors.textSecondary, padding: 8, justifyContent: 'center' }}>
        <span style={{
          width: 8, height: 8, borderRadius: '50%',
          background: colors.accent,
          animation: 'pulse 1.2s ease-in-out infinite'
        }} />
        加载本章场景…
      </div>
    );
  }
  if (scenes.length === 0) {
    return (
      <div style={{
        marginTop: 14,
        padding: 12,
        textAlign: 'center',
        fontSize: 11.5,
        color: colors.textSecondary,
        background: 'rgba(124, 58, 237, 0.06)',
        border: `1px dashed ${colors.border}`,
        borderRadius: 6,
      }}>
        <Sparkles size={13} style={{ verticalAlign: 'middle', marginRight: 4, color: '#fbbf24' }} />
        本章暂无场景拆分（AI 完成写作后会自动拆解 3-7 个场景）
      </div>
    );
  }
  return (
    <div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {scenes.map((sc, idx) => (
          <SceneCard key={sc.id} scene={sc} index={idx} />
        ))}
      </div>
    </div>
  );
}

function SceneCard({ scene, index }: { scene: ChapterScene; index: number }) {
  const [expanded, setExpanded] = useState(true);
  // 紫系情感色调（兼容既有业务色，状态色保留 warning/success 等）
  const sceneToneColors = ['#7c3aed', '#a78bfa', '#c4b5fd', '#8b5cf6', '#059669', '#06b6d4', '#d97706'];
  const toneColor = sceneToneColors[index % sceneToneColors.length];
  return (
    <div style={{
      background: `linear-gradient(135deg, ${toneColor}0d 0%, rgba(124, 58, 237, 0.05) 60%)`,
      border: `1px solid ${toneColor}33`,
      borderLeft: `3px solid ${toneColor}`,
      borderRadius: 6,
      padding: '8px 10px',
      transition: 'all 0.15s',
    }}>
      <div
        onClick={() => setExpanded((e) => !e)}
        style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: expanded ? 6 : 0, cursor: 'pointer' }}
      >
        <span style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 22, height: 22,
          borderRadius: 5,
          background: `${toneColor}26`,
          color: toneColor,
          fontSize: 10, fontWeight: 700,
          fontFamily: 'ui-monospace, monospace',
          flexShrink: 0,
        }}>
          {scene.scene_no}
        </span>
        <span style={{ fontSize: 12.5, color: colors.text, fontWeight: 600, flex: 1 }}>
          {scene.title}
        </span>
        {scene.emotional_tone && (
          <span style={{
            fontSize: 9.5,
            color: toneColor,
            background: `${toneColor}1a`,
            padding: '1px 6px',
            borderRadius: 8,
            fontWeight: 600,
            letterSpacing: 0.3,
          }}>
            {scene.emotional_tone}
          </span>
        )}
        {expanded ? <ChevronUp size={11} color={colors.textSecondary} /> : <ChevronDown size={11} color={colors.textSecondary} />}
      </div>
      {expanded && (
        <>
          {scene.summary && (
            <div style={{
              fontSize: 11.5, color: colors.textSecondary,
              lineHeight: 1.6, marginBottom: 6, paddingLeft: 30,
            }}>
              {scene.summary}
            </div>
          )}
          <div style={{
            display: 'flex', flexWrap: 'wrap', gap: 6,
            fontSize: 10.5, color: colors.textSecondary,
            paddingLeft: 30,
          }}>
            {scene.goal && <SceneChip icon={<Target size={9} />} label="目标" text={scene.goal} color="#10b981" />}
            {scene.conflict && <SceneChip icon={<Zap size={9} />} label="冲突" text={scene.conflict} color="#f59e0b" />}
            {scene.characters_present && scene.characters_present.length > 0 && (
              <SceneChip icon={<Users size={9} />} label="角色" text={scene.characters_present.join("、")} color={toneColor} />
            )}
            {scene.word_count != null && scene.word_count > 0 && (
              <SceneChip icon={<MapPin size={9} />} label="字数" text={`${scene.word_count}`} color={colors.idle} />
            )}
          </div>
        </>
      )}
    </div>
  );
}

function SceneChip({ icon, label, text, color }: { icon: React.ReactNode; label: string; text: string; color: string }) {
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 4,
      padding: '2px 6px',
      background: `${color}14`,
      border: `1px solid ${color}33`,
      borderRadius: 4,
      fontSize: 10,
      color: color === '#94a3b8' ? colors.textSecondary : color,
    }}>
      {icon}
      <span style={{ fontWeight: 600 }}>{label}：</span>
      <span style={{ color: colors.text }}>{text}</span>
    </span>
  );
}

function MarkdownContent({ content }: { content: string }) {
  const [expanded, setExpanded] = useState(false);

  if (!content) {
    return <div style={{ fontSize: 12, color: colors.textSecondary }}>无内容</div>;
  }

  return (
    <div>
      <MarkdownRenderer content={content} maxHeight={expanded ? 800 : 200} />
      {content.length > 500 && (
        <button
          onClick={() => setExpanded(!expanded)}
          style={{
            marginTop: 8,
            background: 'transparent',
            border: `1px solid ${colors.border}`,
            borderRadius: 4,
            padding: '4px 12px',
            fontSize: 12,
            color: colors.accent,
            cursor: 'pointer',
          }}
        >
          {expanded ? '收起' : `展开阅读全文 (${content.length} 字)`}
        </button>
      )}
    </div>
  );
}
