import React, { useEffect, useState } from "react";
import ReactECharts from "echarts-for-react";
import type { Chapter } from "../../types";
import { colors } from "./styles";

interface VisualizationTab4ConsistencyProps {
  projectId?: number;
}

interface ConsistencyCheckResult {
  chapterId: number;
  chapterNo: number;
  title: string;
  hasReport: boolean;
  reportPreview: string;
  wordCount: number;
  status: string;
}

export function VisualizationTab4Consistency({ projectId }: VisualizationTab4ConsistencyProps) {
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loading, setLoading] = useState(false);
  const [chapterReports, setChapterReports] = useState<Record<number, string | null>>({});
  const [reportsLoading, setReportsLoading] = useState<Record<number, boolean>>({});
  const [expandedChapterId, setExpandedChapterId] = useState<number | null>(null);

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

  // 批量并发预加载所有章节的最新一致性报告，避免 KPI"有报告=0"
  useEffect(() => {
    if (!projectId || chapters.length === 0) return;
    const currentProjectId = projectId;
    let cancelled = false;
    async function loadAllReports() {
      try {
        const { fetchChapterVersions } = await import("../../lib/api");
        const entries = await Promise.all(
          chapters.map(async (ch) => {
            try {
              const versions = await fetchChapterVersions(currentProjectId, ch.id);
              const latest = versions.length > 0 ? versions[versions.length - 1] : null;
              return [ch.id, latest?.consistency_report ?? null] as const;
            } catch {
              return [ch.id, null] as const;
            }
          }),
        );
        if (cancelled) return;
        const map: Record<number, string | null> = {};
        entries.forEach(([id, report]) => { map[id] = report; });
        setChapterReports(map);
      } catch (err) {
        console.error("Failed to bulk load reports", err);
      }
    }
    void loadAllReports();
    return () => { cancelled = true; };
  }, [projectId, chapters]);

  async function loadChapterReport(chapterId: number) {
    const existing = chapterReports[chapterId];
    if (existing !== undefined && existing !== null) {
      return; // 已加载且有报告，跳过
    }
    setReportsLoading((prev) => ({ ...prev, [chapterId]: true }));
    try {
      const { fetchChapterVersions } = await import("../../lib/api");
      const versions = await fetchChapterVersions(projectId!, chapterId);
      const latestVersion = versions.length > 0 ? versions[versions.length - 1] : null;
      const report = latestVersion?.consistency_report || null;
      setChapterReports((prev) => ({ ...prev, [chapterId]: report }));
    } catch {
      setChapterReports((prev) => ({ ...prev, [chapterId]: null }));
    } finally {
      setReportsLoading((prev) => ({ ...prev, [chapterId]: false }));
    }
  }

  function toggleChapter(chapterId: number) {
    if (expandedChapterId === chapterId) {
      setExpandedChapterId(null);
    } else {
      setExpandedChapterId(chapterId);
      void loadChapterReport(chapterId);
    }
  }

  if (loading) {
    return <div style={{ padding: 40, textAlign: 'center', color: colors.textSecondary }}>加载章节数据中...</div>;
  }

  if (chapters.length === 0) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: colors.textSecondary }}>
        <div style={{ fontSize: 16, marginBottom: 8 }}>暂无一致性检查数据</div>
        <div style={{ fontSize: 13 }}>AI 执行章节写作并完成一致性检查后将显示综合评分和各项检查详情</div>
      </div>
    );
  }

  const checkResults: ConsistencyCheckResult[] = chapters.map((c) => {
    const report = chapterReports[c.id];
    const hasReport = report !== undefined && report !== null;
    // 字段名兼容：snake_case 优先
    const wc = (c.word_count ?? c.wordCount) || 0;
    return {
      chapterId: c.id,
      chapterNo: c.chapter_no || c.id,
      title: c.title || `第${c.chapter_no || c.id}章`,
      hasReport,
      reportPreview: hasReport ? report!.slice(0, 300) : '',
      wordCount: wc,
      status: c.status,
    };
  });

  const totalChapters = chapters.length;
  // 后端实际枚举：planned / drafted / completed（兼容历史 finalized）
  const completedChapters = chapters.filter(
    (c) => c.status === 'completed' || c.status === 'drafted' || c.status === 'finalized'
  ).length;
  const chaptersWithReport = checkResults.filter((r) => r.hasReport).length;
  const totalWords = chapters.reduce(
    (sum, c) => sum + (c.word_count ?? c.wordCount ?? 0), 0
  );
  const completionRate = totalChapters > 0 ? Math.round((completedChapters / totalChapters) * 100) : 0;

  const wordDistribution = buildWordDistribution(chapters);

  // 维度平均：用全报告（chapterReports）解析，不用 reportPreview（前 300 字）
  const allScores: { dim: string; score: number; chapterNo: number }[] = [];
  checkResults.forEach((r) => {
    if (r.hasReport) {
      const full = chapterReports[r.chapterId] || '';
      parseScores(full).forEach((s) => {
        allScores.push({ ...s, chapterNo: r.chapterNo });
      });
    }
  });

  const dimMap: Record<string, { sum: number; count: number; scores: number[] }> = {};
  allScores.forEach(({ dim, score }) => {
    if (!dimMap[dim]) dimMap[dim] = { sum: 0, count: 0, scores: [] };
    dimMap[dim].sum += score;
    dimMap[dim].count += 1;
    dimMap[dim].scores.push(score);
  });
  const dimAverages = Object.entries(dimMap)
    .map(([dim, v]) => ({
      dim,
      avg: v.count > 0 ? v.sum / v.count : 0,
      min: v.count > 0 ? Math.min(...v.scores) : 0,
      max: v.count > 0 ? Math.max(...v.scores) : 0,
      count: v.count,
    }))
    .sort((a, b) => a.avg - b.avg);

  const gaugeOption = {
    backgroundColor: 'transparent',
    series: [{
      type: 'gauge' as const,
      min: 0, max: 100,
      startAngle: 200, endAngle: -20,
      radius: '90%', center: ['50%', '60%'],
      progress: { show: true, width: 14, itemStyle: { color: completionRate >= 80 ? colors.success : completionRate >= 50 ? colors.warning : colors.error } },
      axisLine: { lineStyle: { width: 14, color: [[1, colors.border]] } },
      axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false },
      pointer: { show: false },
      detail: { valueAnimation: true, formatter: '{value}%', fontSize: 28, fontWeight: 700, color: colors.text, offsetCenter: [0, '10%'] },
      data: [{ value: completionRate }],
    }],
  };

  const distributionOption = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' as const, axisPointer: { type: 'shadow' as const } },
    grid: { top: 20, bottom: 40, left: 60, right: 20 },
    xAxis: {
      type: 'category' as const,
      data: wordDistribution.map((item) => item.label),
      axisLine: { lineStyle: { color: colors.border } },
      axisLabel: { color: colors.textSecondary, fontSize: 11 },
    },
    yAxis: {
      type: 'value' as const,
      name: '章节数',
      axisLine: { lineStyle: { color: colors.border } },
      axisLabel: { color: colors.textSecondary },
      splitLine: { lineStyle: { color: colors.border } },
    },
    series: [{
      type: 'bar' as const,
      data: wordDistribution.map((item, i) => ({
        value: item.count,
        itemStyle: { color: ['#a78bfa', colors.accent, colors.success, colors.warning, colors.error][i % 5], borderRadius: [4, 4, 0, 0] },
      })),
    }],
  };

  const radarOption = {
    backgroundColor: 'transparent',
    radar: {
      indicator: [
        { name: '章节完成度', max: 100 },
        { name: '检查覆盖率', max: 100 },
        { name: '内容完整性', max: 100 },
        { name: '字数均衡度', max: 100 },
        { name: '结构一致性', max: 100 },
      ],
      radius: '65%',
      axisName: { color: colors.textSecondary, fontSize: 11 },
      splitLine: { lineStyle: { color: colors.border } },
      splitArea: { areaStyle: { color: [colors.cardBackground, colors.background] } },
      axisLine: { lineStyle: { color: colors.border } },
    },
    series: [{
      type: 'radar' as const,
      data: [{
        value: [
          completionRate,
          totalChapters > 0 ? Math.round((chaptersWithReport / totalChapters) * 100) : 0,
          totalChapters > 0 ? Math.round((completedChapters / totalChapters) * 100) : 0,
          calculateWordBalance(chapters),
          calculateStructureConsistency(chapters),
        ],
        name: '一致性指标',
        areaStyle: { color: 'rgba(124, 58, 237, 0.3)' },
        lineStyle: { color: colors.accent },
        itemStyle: { color: colors.accent },
      }],
    }],
  };

  return (
    <div style={{ flex: 1, minHeight: 0, height: '100%', padding: 16, display: 'flex', flexDirection: 'column', gap: 16, overflow: 'auto' }}>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 100, background: colors.cardBackground, border: `1px solid ${colors.border}`, borderRadius: 8, padding: 12 }}>
          <div style={{ fontSize: 11, color: colors.textSecondary, marginBottom: 4 }}>总章节</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: colors.text }}>{totalChapters}</div>
        </div>
        <div style={{ flex: 1, minWidth: 100, background: colors.cardBackground, border: `1px solid ${colors.border}`, borderRadius: 8, padding: 12 }}>
          <div style={{ fontSize: 11, color: colors.textSecondary, marginBottom: 4 }}>已完成</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: colors.success }}>{completedChapters}</div>
        </div>
        <div style={{ flex: 1, minWidth: 100, background: colors.cardBackground, border: `1px solid ${colors.border}`, borderRadius: 8, padding: 12 }}>
          <div style={{ fontSize: 11, color: colors.textSecondary, marginBottom: 4 }}>有报告</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: colors.accent }}>{chaptersWithReport}</div>
        </div>
        <div style={{ flex: 1, minWidth: 100, background: colors.cardBackground, border: `1px solid ${colors.border}`, borderRadius: 8, padding: 12 }}>
          <div style={{ fontSize: 11, color: colors.textSecondary, marginBottom: 4 }}>总字数</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: colors.text }}>{totalWords.toLocaleString()}</div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 16 }}>
        <div style={{ flex: '0 0 200px' }}>
          <h3 style={{ margin: '0 0 8px', fontSize: 14, color: colors.text, textAlign: 'center' }}>章节完成率</h3>
          <ReactECharts option={gaugeOption} style={{ height: 200, width: '100%' }} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h3 style={{ margin: '0 0 8px', fontSize: 14, color: colors.text }}>一致性维度评估</h3>
          <ReactECharts option={radarOption} style={{ height: 200, width: '100%' }} />
        </div>
      </div>

      <div style={{ display: 'flex', gap: 16 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h3 style={{ margin: '0 0 8px', fontSize: 14, color: colors.text }}>章节字数分布</h3>
          <ReactECharts option={distributionOption} style={{ height: 180, width: '100%' }} />
        </div>
        <div style={{ flex: 1.5, minWidth: 0 }}>
          <h3 style={{ margin: '0 0 8px', fontSize: 14, color: colors.text }}>章节报告列表</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 180, overflow: 'auto' }}>
            {checkResults.map((r) => {
              const isExpanded = expandedChapterId === r.chapterId;
              const isLoadingReport = reportsLoading[r.chapterId];
              const fullReport = chapterReports[r.chapterId];

              return (
                <div key={r.chapterId}>
                  <div
                    onClick={() => toggleChapter(r.chapterId)}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '8px 10px',
                      background: colors.cardBackground,
                      borderRadius: 6,
                      border: `1px solid ${colors.border}`,
                      cursor: 'pointer',
                      transition: 'background 0.15s',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: r.hasReport ? colors.success : colors.idle, display: 'inline-block' }} />
                      <span style={{ fontSize: 12, color: colors.text }}>{r.title}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 11, color: colors.textSecondary }}>
                        {r.wordCount.toLocaleString()} 字
                      </span>
                      <span style={{ fontSize: 10, color: colors.textSecondary, transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.15s' }}>
                        ▼
                      </span>
                    </div>
                  </div>

                  {isExpanded && (
                    <div style={{
                      marginLeft: 12,
                      marginTop: 4,
                      marginBottom: 4,
                      background: colors.inkCard,
                      border: `1px solid ${colors.border}`,
                      borderRadius: 6,
                      padding: 10,
                    }}>
                      {isLoadingReport && (
                        <div style={{ fontSize: 12, color: colors.textSecondary, textAlign: 'center', padding: 8 }}>
                          加载报告中...
                        </div>
                      )}

                      {!isLoadingReport && fullReport && (
                        <ConsistencyReportPreview report={fullReport} />
                      )}

                      {!isLoadingReport && !fullReport && r.status === 'completed' && (
                        <div style={{ fontSize: 12, color: colors.textSecondary, textAlign: 'center', padding: 8 }}>
                          暂无一致性报告
                        </div>
                      )}

                      {!isLoadingReport && !fullReport && r.status !== 'completed' && (
                        <div style={{ fontSize: 12, color: colors.textSecondary, textAlign: 'center', padding: 8 }}>
                          章节未完成，暂无报告
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* 底部：检查维度详情面板（修复底部留空——即使没有报告也用可计算指标填充）*/}
      <div style={{ background: colors.cardBackground, border: `1px solid ${colors.border}`, borderRadius: 8, padding: 14 }}>
        <h3 style={{ margin: '0 0 10px', fontSize: 14, color: colors.text, display: 'flex', alignItems: 'center', gap: 6 }}>
          <span>检查维度详情</span>
          <span style={{ fontSize: 11, color: colors.textSecondary, fontWeight: 400 }}>
            {dimAverages.length > 0
              ? `（基于 ${chaptersWithReport} 份报告聚合）`
              : `（基于 ${totalChapters} 章节实时计算 · 等待 AI 一致性报告以获取细粒度评分）`}
          </span>
        </h3>
        {(() => {
          // 当 AI 报告维度不可解析时，退化用"实时计算"维度填充，避免面板留空
          const displayRows = dimAverages.length > 0
            ? dimAverages
            : (() => {
                const wq = chapters.map((c) => c.word_count ?? c.wordCount ?? 0).filter((w) => w > 0);
                const avgWords = wq.length > 0 ? Math.round(wq.reduce((s, v) => s + v, 0) / wq.length) : 0;
                const titled = chapters.filter((c) => c.title && c.title.trim() !== '').length;
                const titledRate = totalChapters > 0 ? Math.round((titled / totalChapters) * 100) : 0;
                return [
                  { dim: '章节完成度', avg: completionRate, min: completionRate, max: completionRate, count: totalChapters },
                  { dim: '内容完整性', avg: totalChapters > 0 ? Math.round((completedChapters / totalChapters) * 100) : 0, min: 0, max: 100, count: totalChapters },
                  { dim: '字数均衡度', avg: calculateWordBalance(chapters), min: 0, max: 100, count: wq.length },
                  { dim: '结构一致性', avg: calculateStructureConsistency(chapters), min: 0, max: 100, count: totalChapters },
                  { dim: '检查覆盖率', avg: totalChapters > 0 ? Math.round((chaptersWithReport / totalChapters) * 100) : 0, min: 0, max: 100, count: totalChapters },
                  { dim: '平均章节字数', avg: avgWords, min: wq.length > 0 ? Math.min(...wq) : 0, max: wq.length > 0 ? Math.max(...wq) : 0, count: wq.length },
                  { dim: '标题完备率', avg: titledRate, min: 0, max: 100, count: totalChapters },
                ];
              })();
          return (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {displayRows.map((d) => {
                // 平均章节字数不是 0-100 范围，按比例显示时不夹紧
                const isScore = d.dim !== '平均章节字数';
                const ratio = isScore ? Math.max(0, Math.min(100, d.avg)) / 100 : 0;
                const color = !isScore
                  ? colors.accent
                  : d.avg >= 85 ? colors.success : d.avg >= 70 ? colors.accent : d.avg >= 50 ? colors.warning : colors.error;
                return (
                  <div key={d.dim} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={{ fontSize: 12, color: colors.text, minWidth: 96 }}>{d.dim}</div>
                    {isScore ? (
                      <div style={{ flex: 1, height: 8, background: 'rgba(124, 58, 237, 0.08)', borderRadius: 4, overflow: 'hidden' }}>
                        <div style={{ width: `${ratio * 100}%`, height: '100%', background: `linear-gradient(90deg, ${color}88, ${color})`, borderRadius: 4, transition: 'width 0.3s' }} />
                      </div>
                    ) : (
                      <div style={{ flex: 1, fontSize: 11, color: colors.textSecondary, fontVariantNumeric: 'tabular-nums' }}>
                        范围 {d.min.toLocaleString()} – {d.max.toLocaleString()} 字
                      </div>
                    )}
                    <div style={{ fontSize: 12, color: colors.text, fontVariantNumeric: 'tabular-nums', minWidth: 60, textAlign: 'right', fontWeight: 600 }}>
                      {isScore ? `${d.avg.toFixed(0)}%` : `${d.avg.toLocaleString()} 字`}
                    </div>
                  </div>
                );
              })}
            </div>
          );
        })()}
      </div>
    </div>
  );
}

function ConsistencyReportPreview({ report }: { report: string }) {
  const [expanded, setExpanded] = useState(false);
  const maxLength = 300;
  const isLong = report.length > maxLength;
  const displayContent = expanded ? report : report.slice(0, maxLength);

  return (
    <div>
      <div style={{
        fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
        fontSize: 12,
        lineHeight: 1.6,
        color: colors.text,
        background: colors.inkCard,
        border: `1px solid ${colors.border}`,
        borderRadius: 4,
        padding: 10,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        maxHeight: expanded ? 'none' : 180,
        overflow: 'hidden',
      }}>
        {displayContent}
        {isLong && !expanded && (
          <span style={{ color: colors.textSecondary }}>...</span>
        )}
      </div>
      {isLong && (
        <button
          onClick={() => setExpanded(!expanded)}
          style={{
            marginTop: 6,
            background: 'transparent',
            border: `1px solid ${colors.border}`,
            borderRadius: 4,
            padding: '3px 10px',
            fontSize: 11,
            color: colors.accent,
            cursor: 'pointer',
          }}
        >
          {expanded ? '收起' : `展开完整报告 (${report.length} 字)`}
        </button>
      )}
    </div>
  );
}

function parseScores(report: string): { dim: string; score: number }[] {
  const re = /([\u4e00-\u9fa5]{2,8})[：:]\s*(\d+)\s*分?/g;
  const out: { dim: string; score: number }[] = [];
  let m: RegExpExecArray | null;
  while ((m = re.exec(report)) !== null) {
    out.push({ dim: m[1], score: Number(m[2]) });
  }
  return out;
}

function calculateWordBalance(chapters: Chapter[]): number {
  if (chapters.length < 2) return 100;
  // 字段名兼容
  const wordCounts = chapters.map((c) => c.word_count ?? c.wordCount ?? 0).filter((wc) => wc > 0);
  if (wordCounts.length < 2) return 50;
  const avg = wordCounts.reduce((s, v) => s + v, 0) / wordCounts.length;
  const variance = wordCounts.reduce((s, v) => s + Math.pow(v - avg, 2), 0) / wordCounts.length;
  const stdDev = Math.sqrt(variance);
  const cv = avg > 0 ? (stdDev / avg) * 100 : 0;
  return Math.max(0, Math.min(100, Math.round(100 - cv)));
}

function calculateStructureConsistency(chapters: Chapter[]): number {
  if (chapters.length === 0) return 0;
  // 兼容 drafted / finalized
  const completedCount = chapters.filter(
    (c) => c.status === 'completed' || c.status === 'drafted' || c.status === 'finalized'
  ).length;
  const hasTitles = chapters.filter((c) => c.title && c.title.trim() !== '').length;
  const hasSummaries = chapters.filter((c) => c.summary && c.summary.trim() !== '').length;
  const score = (completedCount / chapters.length) * 40 + (hasTitles / chapters.length) * 30 + (hasSummaries / chapters.length) * 30;
  return Math.round(score);
}

function buildWordDistribution(chapters: Chapter[]): { label: string; count: number }[] {
  const wordCounts = chapters.map((chapter) => chapter.word_count ?? chapter.wordCount ?? 0);
  const maxWords = Math.max(...wordCounts, 0);
  const bucketCount = Math.min(5, Math.max(1, chapters.length));
  const bucketSize = Math.max(1, Math.ceil(maxWords / bucketCount));
  const buckets = Array.from({ length: bucketCount }, (_, index) => {
    const start = index * bucketSize;
    const end = index === bucketCount - 1 ? Infinity : (index + 1) * bucketSize;
    return {
      start,
      end,
      label: end === Infinity ? `${start}+` : `${start}-${end}`,
      count: 0,
    };
  });

  wordCounts.forEach((wordCount) => {
    const bucket = buckets.find((item) => wordCount >= item.start && wordCount <= item.end) || buckets[buckets.length - 1];
    bucket.count += 1;
  });

  return buckets;
}
