import { useState, useEffect, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { colors, spacing, borderRadius } from './styles';
import {
  BarChart3, TrendingUp, Target, Users, Compass, Sparkles, BookOpen, Hash, CheckCircle2, Clock,
} from 'lucide-react';
import {
  fetchChapters,
  fetchWorldbookEntries,
  fetchTrendExplorations,
  fetchCharacters,
} from '../../lib/api';
import type { Chapter, WorldbookEntry, TrendExploration, Character } from '../../types';

type VisualizationTab6StatsProps = {
  projectId?: number;
};

type ProjectStats = {
  totalWords: number;
  chapterCount: number;
  completedChapters: number;
  worldbookEntries: number;
  characterCount: number;
  trendCount: number;
  avgChapterWords: number;
  completionRate: number;
  hasAnyData: boolean;
  chapterWordCounts: { chapterNo: number; title: string; wordCount: number; status: string }[];
  worldbookByCategory: { category: string; count: number }[];
};

const CATEGORY_LABEL: Record<string, string> = {
  setting: '世界设定',
  organization: '势力组织',
  character: '角色',
  item: '物品',
  location: '地点',
  other: '其他',
};

const CATEGORY_COLOR: Record<string, string> = {
  setting: '#7c3aed',
  organization: '#8b5cf6',
  character: '#a78bfa',
  item: '#c4b5fd',
  location: '#a78bfa',
  other: colors.idle,
};

export function VisualizationTab6Stats({ projectId }: VisualizationTab6StatsProps) {
  const [stats, setStats] = useState<ProjectStats | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    setLoading(true);
    Promise.all([
      fetchChapters(projectId as number),
      fetchWorldbookEntries(projectId as number),
      fetchTrendExplorations(projectId as number),
      fetchCharacters(projectId as number),
    ]).then(([chapters, worldbook, trends, characters]) => {
      if (cancelled) return;
      // 字段名兼容：后端 SQLAlchemy Mapped 使用 snake_case (word_count)，
      // 但部分接口序列化后可能用 camelCase (wordCount)，这里双兜底
      const wc = (ch: any) => ch.word_count ?? ch.wordCount ?? 0;
      const totalWords = chapters.reduce((sum, ch) => sum + wc(ch), 0);
      // 后端实际枚举：planned / drafted / completed（兼容历史 finalized）
      const completedChapters = chapters.filter(
        ch => ch.status === 'completed' || ch.status === 'drafted' || ch.status === 'finalized'
      ).length;
      const chapterWordCounts = chapters
        .sort((a, b) => (a.chapter_no || 0) - (b.chapter_no || 0))
        .map(ch => ({
          chapterNo: ch.chapter_no,
          title: ch.title,
          wordCount: wc(ch),
          status: ch.status,
        }));

      const categoryCount: Record<string, number> = {};
      worldbook.forEach(entry => {
        const cat = entry.category || 'other';
        categoryCount[cat] = (categoryCount[cat] || 0) + 1;
      });
      const worldbookByCategory = Object.entries(categoryCount).map(([category, count]) => ({ category, count }));

      setStats({
        totalWords,
        chapterCount: chapters.length,
        completedChapters,
        worldbookEntries: worldbook.length,
        characterCount: characters.length,
        trendCount: trends.length,
        avgChapterWords: chapters.length > 0 ? Math.round(totalWords / chapters.length) : 0,
        completionRate: chapters.length > 0 ? Math.round((completedChapters / chapters.length) * 100) : 0,
        hasAnyData: chapters.length + worldbook.length + trends.length + characters.length > 0,
        chapterWordCounts,
        worldbookByCategory,
      });
    }).catch((err) => {
      console.error('Failed to load stats:', err);
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [projectId]);

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

  if (loading) {
    return (
      <div style={{ padding: 24, textAlign: 'center', color: colors.textSecondary }}>
        正在加载统计数据…
      </div>
    );
  }

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

  const maxAssetCount = Math.max(stats.worldbookEntries, stats.characterCount, stats.trendCount, 1);
  const maxChapterWords = Math.max(...stats.chapterWordCounts.map((item) => item.wordCount), stats.avgChapterWords, 1);

  // 多维评分雷达
  const diversityIndicators = [
    { name: '章节完成度', max: 100 },
    { name: '世界观构建', max: 100 },
    { name: '角色丰富度', max: 100 },
    { name: '热点探索', max: 100 },
    { name: '字数达标率', max: 100 },
  ];
  const radarValues = [
    stats.completionRate,
    Math.round((stats.worldbookEntries / maxAssetCount) * 100),
    Math.round((stats.characterCount / maxAssetCount) * 100),
    Math.round((stats.trendCount / maxAssetCount) * 100),
    stats.chapterCount > 0 ? Math.round((stats.avgChapterWords / maxChapterWords) * 100) : 0,
  ];
  const diversityOption = {
    backgroundColor: 'transparent',
    tooltip: {},
    radar: {
      indicator: diversityIndicators,
      shape: 'polygon' as const,
      splitNumber: 5,
      axisName: { color: colors.text, fontSize: 11, fontWeight: 600 },
      splitLine: { lineStyle: { color: 'rgba(58,38,107,0.08)' } },
      splitArea: { areaStyle: { color: ['rgba(124,58,237,0.04)', 'rgba(124,58,237,0.01)'] } },
      axisLine: { lineStyle: { color: colors.border } },
    },
    series: [{
      type: 'radar' as const,
      label: { show: true, color: colors.accent, fontSize: 11, fontWeight: 600, formatter: '{c}' },
      data: [{
        value: radarValues,
        name: '项目进度评分',
        areaStyle: {
          color: { type: 'linear' as const, x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(124,58,237,0.45)' },
              { offset: 1, color: 'rgba(124,58,237,0.05)' },
            ] },
        },
        lineStyle: { color: colors.accent, width: 2 },
        itemStyle: { color: colors.accent },
        symbol: 'circle',
        symbolSize: 6,
      }],
    }],
  };

  // 章节字数柱状图（带状态着色）
  const chapterOption = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' as const,
      backgroundColor: 'rgba(255,255,255,0.95)',
      borderColor: 'rgba(58,38,107,0.12)',
      textStyle: { color: colors.text },
      formatter: (params: any) => {
        const p = params[0];
        const idx = p.dataIndex;
        const ch = stats.chapterWordCounts[idx];
        if (!ch) return '';
        const statusMap: Record<string, string> = { completed: '已完成', in_progress: '进行中', planned: '未开始' };
        return `<b>第 ${ch.chapterNo} 章</b><br/>${ch.title}<br/>${ch.wordCount} 字 · ${statusMap[ch.status] || ch.status}`;
      },
    },
    grid: { top: 18, bottom: 28, left: 44, right: 16 },
    xAxis: {
      type: 'category' as const,
      data: stats.chapterWordCounts.map(ch => `Ch.${ch.chapterNo || ''}`),
      axisLine: { lineStyle: { color: colors.border } },
      axisLabel: { color: colors.textSecondary, fontSize: 10 },
    },
    yAxis: {
      type: 'value' as const,
      axisLine: { lineStyle: { color: colors.border } },
      axisLabel: { color: colors.textSecondary, fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(58,38,107,0.08)' } },
    },
    series: [{
      data: stats.chapterWordCounts.map((ch) => {
        const colorMap: Record<string, string> = {
          completed: colors.success, in_progress: colors.warning, planned: colors.idle,
        };
        const baseColor = colorMap[ch.status] || colors.accent;
        return {
          value: ch.wordCount,
          itemStyle: {
            color: { type: 'linear' as const, x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [{ offset: 0, color: baseColor }, { offset: 1, color: `${baseColor}50` }] },
            borderRadius: [4, 4, 0, 0],
            shadowBlur: 8,
            shadowColor: 'rgba(124,58,237,0.3)',
          },
        };
      }),
      type: 'bar' as const,
      barWidth: '55%',
      label: { show: true, position: 'top' as const, color: colors.textSecondary, fontSize: 10, formatter: '{c}' },
      markLine: {
        symbol: 'none',
        data: [{ yAxis: stats.avgChapterWords, label: { formatter: `均值 ${stats.avgChapterWords}`, color: colors.warning, fontSize: 10 }, lineStyle: { color: colors.warning, type: 'dashed' as const } }],
      },
    }],
  };

  // 世界观类别堆叠条
  const sortedCategories = stats.worldbookByCategory.sort((a, b) => b.count - a.count);
  const categoryOption = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' as const, axisPointer: { type: 'shadow' as const },
      backgroundColor: 'rgba(255,255,255,0.95)',
      borderColor: 'rgba(58,38,107,0.12)',
      textStyle: { color: colors.text },
    },
    grid: { top: 12, right: 24, bottom: 12, left: 90 },
    xAxis: { type: 'value' as const, show: false,
      splitLine: { lineStyle: { color: 'rgba(58,38,107,0.08)' } },
    },
    yAxis: {
      type: 'category' as const,
      data: sortedCategories.map(c => CATEGORY_LABEL[c.category] || c.category).reverse(),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: colors.textSecondary, fontSize: 11 },
    },
    series: [{
      type: 'bar' as const,
      data: sortedCategories.map((c) => {
        const baseColor = CATEGORY_COLOR[c.category] || colors.idle;
        return {
          value: c.count,
          itemStyle: {
            color: { type: 'linear' as const, x: 0, y: 0, x2: 1, y2: 0,
              colorStops: [
                { offset: 0, color: `${baseColor}55` },
                { offset: 1, color: baseColor },
              ] },
            borderRadius: [0, 4, 4, 0],
            shadowBlur: 6,
            shadowColor: 'rgba(124,58,237,0.25)',
          },
        };
      }).reverse(),
      barWidth: 14,
      label: { show: true, position: 'right' as const, color: colors.textSecondary, fontSize: 10, fontWeight: 600, formatter: '{c} 条' },
    }],
  };

  return (
    <div className="cc-viz-panel" style={{ flex: 1, minHeight: 0, height: '100%', padding: spacing.md, display: 'flex', flexDirection: 'column', gap: spacing.md, overflow: 'auto' }}>
      {/* 顶部 KPI 行 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: spacing.sm, flexShrink: 0 }}>
        <KpiTile
          label="已完成章节" value={`${stats.completedChapters}/${stats.chapterCount}`}
          accent={colors.success} icon={<CheckCircle2 size={14} />}
          progress={stats.completionRate}
        />
        <KpiTile
          label="总字数" value={stats.totalWords.toLocaleString()}
          accent={colors.accent} icon={<Hash size={14} />}
          delta={chapterDelta}
        />
        <KpiTile
          label="平均章节字数" value={stats.avgChapterWords.toLocaleString()}
          accent={colors.paused} icon={<TrendingUp size={14} />}
          delta={chapterDelta}
        />
        <KpiTile
          label="世界观条目" value={stats.worldbookEntries}
          accent="#8b5cf6" icon={<BookOpen size={14} />}
        />
        <KpiTile
          label="角色数量" value={stats.characterCount}
          accent="#a78bfa" icon={<Users size={14} />}
        />
        <KpiTile
          label="热点探索" value={stats.trendCount}
          accent="#c4b5fd" icon={<Compass size={14} />}
        />
        <KpiTile
          label="待处理章节" value={stats.chapterCount - stats.completedChapters}
          accent={colors.idle} icon={<Clock size={14} />}
        />
        <KpiTile
          label="完成率" value={`${stats.completionRate}%`}
          accent={colors.accent} icon={<Target size={14} />}
          progress={stats.completionRate}
        />
      </div>

      {/* 项目进度评分 */}
      <SectionCard
        title="项目进度评分" icon={<Sparkles size={14} />}
        sub="综合章节完成度、世界观、角色、热点探索、字数达标率五个维度"
      >
        <ReactECharts option={diversityOption} style={{ height: 280 }} />
      </SectionCard>

      {/* 章节字数分布 + 世界观类别 —— 始终占位，避免空数据时右侧留白 */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: spacing.md }}>
        <SectionCard
          title="章节字数分布" icon={<BarChart3 size={14} />}
          sub={stats.chapterWordCounts.length > 0
            ? `紫色虚线为平均字数 ${stats.avgChapterWords}`
            : '暂无章节数据'}
          legend={[
            { color: colors.success, label: '已完成' },
            { color: colors.warning, label: '进行中' },
            { color: colors.idle, label: '未开始' },
          ]}
        >
          {stats.chapterWordCounts.length > 0 ? (
            <ReactECharts option={chapterOption} style={{ height: 220 }} />
          ) : (
            <EmptyChartHint
              height={220}
              text="运行章节写作后展示各章字数"
              icon={<BarChart3 size={28} />}
            />
          )}
        </SectionCard>
        <SectionCard
          title="世界观类别分布" icon={<BookOpen size={14} />}
          sub={stats.worldbookByCategory.length > 0
            ? `共 ${stats.worldbookEntries} 条`
            : '暂无世界观数据'}
        >
          {stats.worldbookByCategory.length > 0 ? (
            <ReactECharts option={categoryOption} style={{ height: 220 }} />
          ) : (
            <EmptyChartHint
              height={220}
              text="构建世界观后展示分类分布"
              icon={<BookOpen size={28} />}
            />
          )}
        </SectionCard>
      </div>
    </div>
  );
}

// 占位卡：图表区无数据时显示，避免右侧/下方留白
function EmptyChartHint({
  height, text, icon,
}: {
  height: number; text: string; icon: React.ReactNode;
}) {
  return (
    <div style={{
      height,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 8,
      color: colors.textSecondary,
      background: 'rgba(124,58,237,0.03)',
      border: `1px dashed ${colors.border}`,
      borderRadius: borderRadius.sm,
    }}>
      <div style={{ opacity: 0.5 }}>{icon}</div>
      <div style={{ fontSize: 12 }}>{text}</div>
    </div>
  );
}

function KpiTile({
  label, value, accent, icon, progress, delta,
}: {
  label: string; value: number | string; accent: string;
  icon: React.ReactNode; progress?: number;
  delta?: { value: number; direction: 'up' | 'down' | 'flat' };
}) {
  const deltaColor = !delta
    ? colors.textSecondary
    : delta.direction === 'up' ? colors.success : delta.direction === 'down' ? colors.error : colors.textSecondary;
  const deltaArrow = !delta ? '' : delta.direction === 'up' ? '↑' : delta.direction === 'down' ? '↓' : '→';
  return (
    <div style={{
      background: colors.cardBackground,
      border: `1px solid ${colors.border}`,
      borderRadius: borderRadius.md,
      padding: '10px 12px',
      position: 'relative',
      overflow: 'hidden',
    }}>
      <div style={{ position: 'absolute', top: 0, left: 0, width: 3, height: '100%', background: `linear-gradient(180deg, ${accent}, transparent)` }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10.5, color: colors.textSecondary, marginBottom: 4 }}>
        <span style={{ color: accent }}>{icon}</span> {label}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span style={{ fontSize: 26, fontWeight: 700, color: colors.text, fontVariantNumeric: 'tabular-nums' }}>{value}</span>
        {delta && (
          <span style={{ fontSize: 10.5, color: deltaColor, fontWeight: 600 }}>
            {deltaArrow} {delta.value}%
          </span>
        )}
      </div>
      {typeof progress === 'number' && (
        <div style={{ marginTop: 6, height: 3, background: 'rgba(124,58,237,0.08)', borderRadius: 2, overflow: 'hidden' }}>
          <div style={{ width: `${progress}%`, height: '100%', background: accent, borderRadius: 2, transition: 'width 0.3s' }} />
        </div>
      )}
    </div>
  );
}

function SectionCard({
  title, icon, sub, legend, children,
}: {
  title: string;
  icon: React.ReactNode;
  sub?: string;
  legend?: { color: string; label: string }[];
  children: React.ReactNode;
}) {
  return (
    <div style={{
      background: colors.cardBackground,
      border: `1px solid ${colors.border}`,
      borderRadius: borderRadius.md,
      padding: 14,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <span style={{ color: colors.accent }}>{icon}</span>
        <span style={{ fontSize: 13, fontWeight: 700, color: colors.text }}>{title}</span>
        {legend && (
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 12 }}>
            {legend.map((l) => (
              <span key={l.label} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 10.5, color: colors.textSecondary }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: l.color }} />
                {l.label}
              </span>
            ))}
          </div>
        )}
      </div>
      {sub && <div style={{ fontSize: 11, color: colors.textSecondary, marginBottom: 8 }}>{sub}</div>}
      {children}
    </div>
  );
}
