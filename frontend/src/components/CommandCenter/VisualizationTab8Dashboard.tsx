import { useMemo } from 'react';

// ============================================================================
// Types
// ============================================================================
export type NovelStats = {
  title: string;
  totalWords: number;
  totalChapters: number;
  completedChapters: number;
};

export type ChapterStatItem = {
  chapterNo: number;
  wordCount: number;
  status: string;
};

export type CharacterFrequencyItem = {
  name: string;
  count: number;
};

export type ConsistencyScore = {
  character: number;
  plot: number;
  world: number;
  pacing: number;
  style: number;
};

export type GenreDistributionItem = {
  genre: string;
  count: number;
};

type VisualizationTab8DashboardProps = {
  novelStats: NovelStats;
  chapterStats: ChapterStatItem[];
  characterFrequency: CharacterFrequencyItem[];
  consistency: ConsistencyScore;
  genreDistribution: GenreDistributionItem[];
  /** Optional: 任务耗时直方图（AI 章节生成） */
  latencyHist?: Array<{ bucket: string; count: number }>;
  /** Optional: 0-100 当前进度 */
  progressPercent?: number;
  /** Optional: 平均 AI 任务时延（ms） */
  avgLatencyMs?: number;
  /** Optional: accumulated writing time in seconds, used for "累计耗时" KPI */
  totalDurationSeconds?: number;
};

// ============================================================================
// Theme tokens (water-ink / light purple palette, aligned with CommandCenter)
// ============================================================================
import { colors } from './styles';

const theme = {
  bg: colors.background,
  cardBg: colors.inkCardStrong,
  cardBorder: colors.border,
  cardBorderHover: 'rgba(124, 58, 237, 0.45)',
  text: colors.text,
  textSecondary: colors.textSecondary,
  textMuted: colors.textSecondary,
  accent: colors.accent,
  success: colors.success,
  warning: colors.warning,
  error: colors.error,
  purple: colors.paused,
  pink: '#f472b6',
  cyan: '#7c3aed',
  lime: '#a78bfa',
  orange: colors.warning,
  gridLine: 'rgba(58, 38, 107, 0.12)',
  skeleton: 'rgba(124, 58, 237, 0.06)',
  skeletonShine: 'rgba(124, 58, 237, 0.16)',
};

const palette = [
  colors.accent,
  colors.paused,
  '#c4b5fd',
  colors.success,
  '#f472b6',
  colors.warning,
  '#a78bfa',
  colors.error,
];

const fontStack =
  "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', Roboto, sans-serif";

// ============================================================================
// Utilities
// ============================================================================
function formatNumber(n: number): string {
  if (!Number.isFinite(n)) return '0';
  if (Math.abs(n) >= 10000) return `${(n / 10000).toFixed(1)}万`;
  return n.toLocaleString('zh-CN');
}

function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return '0 秒';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h} 小时 ${m} 分`;
  if (m > 0) return `${m} 分 ${s} 秒`;
  return `${s} 秒`;
}

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function describeArc(cx: number, cy: number, r: number, startAngle: number, endAngle: number) {
  const start = polarToCartesian(cx, cy, r, endAngle);
  const end = polarToCartesian(cx, cy, r, startAngle);
  const largeArc = endAngle - startAngle <= 180 ? '0' : '1';
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 0 ${end.x} ${end.y}`;
}

function isDataEmpty(props: VisualizationTab8DashboardProps): boolean {
  return (
    !props.novelStats &&
    (!props.chapterStats || props.chapterStats.length === 0) &&
    (!props.characterFrequency || props.characterFrequency.length === 0) &&
    (!props.genreDistribution || props.genreDistribution.length === 0)
  );
}

// ============================================================================
// Global CSS (keyframes + glassmorphism utilities) injected once
// ============================================================================
const STYLE_ID = 'v8-dashboard-styles';
function ensureGlobalStyles() {
  if (typeof document === 'undefined') return;
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = `
    @keyframes v8-fade-in-up {
      from { opacity: 0; transform: translateY(8px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes v8-skeleton {
      0%   { background-position: -200px 0; }
      100% { background-position: calc(200px + 100%) 0; }
    }
    @keyframes v8-spin {
      to { transform: rotate(360deg); }
    }
    .v8-card {
      background: ${theme.cardBg};
      border: 1px solid ${theme.cardBorder};
      border-radius: 12px;
      padding: 20px;
      backdrop-filter: blur(10px);
      -webkit-backdrop-filter: blur(10px);
      box-shadow: 0 1px 2px rgba(0,0,0,0.18), inset 0 1px 0 rgba(255,255,255,0.02);
      transition: box-shadow 220ms ease, border-color 220ms ease, transform 220ms ease;
      animation: v8-fade-in-up 360ms ease both;
      /* 修复内容溢出：让子图表（BarChart/RadarChart/DonutChart 等）必须按容器尺寸自适应，
         不再让 bar 列表把卡片"顶"出去。 */
      display: flex;
      flex-direction: column;
      overflow: hidden;
      min-height: 0;
    }
    .v8-card:hover {
      box-shadow: 0 8px 24px rgba(0,0,0,0.4), 0 0 0 1px ${theme.cardBorderHover};
      border-color: ${theme.cardBorderHover};
      transform: translateY(-1px);
    }
    .v8-skeleton-block {
      background: linear-gradient(90deg, ${theme.skeleton} 0%, ${theme.skeletonShine} 50%, ${theme.skeleton} 100%);
      background-size: 200px 100%;
      background-repeat: no-repeat;
      animation: v8-skeleton 1.4s ease-in-out infinite;
      border-radius: 6px;
    }
    .v8-spinner {
      width: 18px; height: 18px;
      border: 2px solid rgba(59,130,246,0.25);
      border-top-color: ${theme.accent};
      border-radius: 50%;
      animation: v8-spin 0.8s linear infinite;
    }
  `;
  document.head.appendChild(style);
}

// ============================================================================
// Shared UI atoms
// ============================================================================
function CardHeader({
  title,
  subtitle,
  delay = 0,
}: {
  title: string;
  subtitle?: string;
  delay?: number;
}) {
  return (
    <div style={{ marginBottom: 12, animationDelay: `${delay}ms` }}>
      <div
        style={{
          fontSize: 14,
          color: theme.textSecondary,
          fontWeight: 600,
          letterSpacing: 0.3,
        }}
      >
        {title}
      </div>
      {subtitle && (
        <div style={{ fontSize: 11, color: theme.textMuted, marginTop: 2 }}>{subtitle}</div>
      )}
    </div>
  );
}

function Skeleton({ height = 160, delay = 0 }: { height?: number; delay?: number }) {
  return (
    <div
      className="v8-skeleton-block"
      style={{ height, width: '100%', animationDelay: `${delay}ms` }}
    />
  );
}

function EmptyHint({ text = '暂无数据' }: { text?: string }) {
  return (
    <div
      style={{
        height: 160,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: theme.textMuted,
        fontSize: 12,
        border: `1px dashed ${theme.cardBorder}`,
        borderRadius: 8,
      }}
    >
      {text}
    </div>
  );
}

// ============================================================================
// 1) Donut: Chapter Completion
// ============================================================================
function DonutChart({
  data,
  delay = 0,
}: {
  data: { label: string; value: number; color: string }[];
  delay?: number;
}) {
  const size = 220;
  const cx = size / 2;
  const cy = size / 2;
  const r = 80;
  const stroke = 28;
  const total = data.reduce((sum, d) => sum + d.value, 0);

  if (total === 0) return <EmptyHint text="暂无章节数据" />;

  let cumulative = 0;
  const arcs = data.map((d) => {
    const portion = d.value / total;
    const startAngle = cumulative * 360;
    const endAngle = (cumulative + portion) * 360 - 0.5; // small gap
    cumulative += portion;
    if (endAngle <= startAngle) return null;
    return { ...d, startAngle, endAngle };
  }).filter(Boolean) as (typeof data[0] & { startAngle: number; endAngle: number })[];

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        animationDelay: `${delay}ms`,
        // 适配 v8-card 的 flex column：自身撑满剩余高度，避免图表把卡片撑爆
        flex: 1,
        minHeight: 0,
        overflow: 'hidden',
      }}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label="章节完成度环形图"
        style={{ flexShrink: 0 }}
      >
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={theme.gridLine} strokeWidth={stroke} />
        {arcs.map((a, i) => (
          <path
            key={i}
            d={describeArc(cx, cy, r, a.startAngle, a.endAngle)}
            fill="none"
            stroke={a.color}
            strokeWidth={stroke}
            strokeLinecap="round"
            style={{
              transition: 'all 400ms ease',
              filter: 'drop-shadow(0 0 6px rgba(124, 58, 237, 0.18))',
            }}
          />
        ))}
        <text
          x={cx}
          y={cy - 4}
          textAnchor="middle"
          fill={theme.text}
          fontSize={28}
          fontWeight={700}
          fontFamily={fontStack}
        >
          {total}
        </text>
        <text
          x={cx}
          y={cy + 16}
          textAnchor="middle"
          fill={theme.textSecondary}
          fontSize={11}
          fontFamily={fontStack}
        >
          章节总数
        </text>
      </svg>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: 1, minWidth: 0, overflow: 'hidden' }}>
        {data.map((d) => (
          <div
            key={d.label}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              fontSize: 12,
              color: theme.text,
            }}
          >
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: 2,
                background: d.color,
                flexShrink: 0,
                boxShadow: `0 0 6px ${d.color}55`,
              }}
            />
            <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {d.label}
            </span>
            <span style={{ color: theme.textSecondary, fontVariantNumeric: 'tabular-nums' }}>
              {d.value} ({total > 0 ? Math.round((d.value / total) * 100) : 0}%)
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================================================
// 2) Line: Word Count Trend per Chapter
// ============================================================================
function LineChart({
  data,
  delay = 0,
}: {
  data: { chapterNo: number; wordCount: number; status: string }[];
  delay?: number;
}) {
  const width = 520;
  const height = 220;
  const padding = { top: 16, right: 16, bottom: 32, left: 48 };

  if (data.length === 0) return <EmptyHint text="暂无字数数据" />;

  const sorted = useMemo(
    () => [...data].sort((a, b) => a.chapterNo - b.chapterNo),
    [data],
  );

  const maxY = Math.max(...sorted.map((d) => d.wordCount), 1) * 1.15;
  const innerW = width - padding.left - padding.right;
  const innerH = height - padding.top - padding.bottom;

  const xStep = sorted.length > 1 ? innerW / (sorted.length - 1) : 0;
  const points = sorted.map((d, i) => {
    const x = padding.left + i * xStep;
    const y = padding.top + innerH - (d.wordCount / maxY) * innerH;
    return { x, y, ...d };
  });

  const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
  const areaPath =
    `${linePath} L ${points[points.length - 1].x} ${padding.top + innerH} ` +
    `L ${points[0].x} ${padding.top + innerH} Z`;

  const yTicks = 4;
  const yGridLines = Array.from({ length: yTicks + 1 }, (_, i) => i);

  return (
    <div
      style={{
        animationDelay: `${delay}ms`,
        // 适配 v8-card flex column：撑满剩余高度并允许 SVG 自适应
        flex: 1,
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
    <svg
      width="100%"
      height="100%"
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label="字数趋势折线图"
      style={{ animationDelay: `${delay}ms`, display: 'block', flex: 1, minHeight: 0 }}
    >
      <defs>
        <linearGradient id="v8-line-area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={theme.accent} stopOpacity="0.45" />
          <stop offset="100%" stopColor={theme.accent} stopOpacity="0" />
        </linearGradient>
      </defs>

      {yGridLines.map((i) => {
        const y = padding.top + innerH - (i / yTicks) * innerH;
        return (
          <g key={i}>
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={y}
              y2={y}
              stroke={theme.gridLine}
              strokeDasharray="3 3"
            />
            <text
              x={padding.left - 6}
              y={y + 3}
              textAnchor="end"
              fontSize={10}
              fill={theme.textMuted}
              fontFamily={fontStack}
            >
              {formatNumber(Math.round((i / yTicks) * maxY))}
            </text>
          </g>
        );
      })}

      <path d={areaPath} fill="url(#v8-line-area)" />
      <path
        d={linePath}
        fill="none"
        stroke={theme.accent}
        strokeWidth={2}
        strokeLinejoin="round"
        strokeLinecap="round"
        style={{ filter: 'drop-shadow(0 0 4px rgba(59,130,246,0.4))' }}
      />

      {points.map((p, i) => {
        const fill =
          p.status === 'completed' ? theme.success :
          p.status === 'failed' ? theme.error :
          theme.warning;
        return (
          <g key={i}>
            <circle
              cx={p.x}
              cy={p.y}
              r={3.5}
              fill={fill}
              stroke={theme.bg}
              strokeWidth={1.5}
            />
          </g>
        );
      })}

      {points.map((p, i) => {
        const showLabel = sorted.length <= 20 || i % Math.ceil(sorted.length / 20) === 0;
        if (!showLabel) return null;
        return (
          <text
            key={`xl-${i}`}
            x={p.x}
            y={height - padding.bottom + 16}
            textAnchor="middle"
            fontSize={10}
            fill={theme.textMuted}
            fontFamily={fontStack}
          >
            {p.chapterNo}
          </text>
        );
      })}
    </svg>
    </div>
  );
}

// ============================================================================
// 3) Bar: Top 10 Character Frequency
// ============================================================================
function BarChart({
  data,
  delay = 0,
}: {
  data: { name: string; count: number }[];
  delay?: number;
}) {
  if (data.length === 0) return <EmptyHint text="暂无角色数据" />;

  const top = data.slice(0, 10);
  const max = Math.max(...top.map((d) => d.count), 1);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        animationDelay: `${delay}ms`,
        // 父 v8-card 是 flex column，让 BarChart 撑满剩余空间并允许滚动，避免溢出
        flex: 1,
        minHeight: 0,
        overflowY: 'auto',
      }}
    >
      {top.map((d, i) => {
        const pct = (d.count / max) * 100;
        const color = palette[i % palette.length];
        return (
          <div key={`${d.name}-${i}`} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div
              style={{
                width: 64,
                fontSize: 12,
                color: theme.text,
                textAlign: 'right',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
              title={d.name}
            >
              {d.name}
            </div>
            <div
              style={{
                flex: 1,
                height: 16,
                background: 'rgba(124, 58, 237, 0.08)',
                borderRadius: 4,
                overflow: 'hidden',
                position: 'relative',
              }}
            >
              <div
                style={{
                  width: `${pct}%`,
                  height: '100%',
                  background: `linear-gradient(90deg, ${color}cc, ${color})`,
                  borderRadius: 4,
                  transition: 'width 600ms ease',
                  boxShadow: `0 0 8px ${color}55`,
                }}
              />
            </div>
            <div
              style={{
                width: 44,
                fontSize: 12,
                color: theme.textSecondary,
                textAlign: 'right',
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {d.count}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ============================================================================
// 4) Radar: Consistency
// ============================================================================
function RadarChart({
  scores,
  delay = 0,
}: {
  scores: { character: number; plot: number; world: number; pacing: number; style: number };
  delay?: number;
}) {
  const size = 260;
  const cx = size / 2;
  const cy = size / 2;
  const radius = 90;
  const levels = 4;

  const axes = [
    { key: 'character', label: '角色一致性' },
    { key: 'plot', label: '剧情一致性' },
    { key: 'world', label: '世界观一致性' },
    { key: 'pacing', label: '节奏' },
    { key: 'style', label: '风格' },
  ];

  const angleFor = (i: number) => (i * 360) / axes.length;
  const pointFor = (value: number, i: number) => {
    const r = (Math.max(0, Math.min(100, value)) / 100) * radius;
    return polarToCartesian(cx, cy, r, angleFor(i));
  };

  const polyPoints = axes
    .map((a, i) => {
      const p = pointFor(scores[a.key as keyof typeof scores] ?? 0, i);
      return `${p.x},${p.y}`;
    })
    .join(' ');

  return (
    <div
      style={{
        animationDelay: `${delay}ms`,
        // 适配 v8-card flex column：撑满剩余高度并让 SVG 居中自适应
        flex: 1,
        minHeight: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'hidden',
      }}
    >
    <svg
      width="100%"
      height="100%"
      viewBox={`0 0 ${size} ${size}`}
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label="一致性雷达图"
      style={{ animationDelay: `${delay}ms`, display: 'block', maxWidth: '100%', maxHeight: '100%' }}
    >
      {Array.from({ length: levels }, (_, lvl) => {
        const r = ((lvl + 1) / levels) * radius;
        const pts = axes
          .map((_, i) => {
            const p = polarToCartesian(cx, cy, r, angleFor(i));
            return `${p.x},${p.y}`;
          })
          .join(' ');
        return (
          <polygon
            key={lvl}
            points={pts}
            fill={lvl % 2 === 0 ? 'rgba(124, 58, 237, 0.06)' : 'rgba(124, 58, 237, 0.12)'}
            stroke={theme.gridLine}
            strokeWidth={1}
          />
        );
      })}

      {axes.map((_, i) => {
        const p = polarToCartesian(cx, cy, radius, angleFor(i));
        return (
          <line
            key={`ax-${i}`}
            x1={cx}
            y1={cy}
            x2={p.x}
            y2={p.y}
            stroke={theme.gridLine}
            strokeWidth={1}
          />
        );
      })}

      <polygon
        points={polyPoints}
        fill={theme.accent}
        fillOpacity={0.22}
        stroke={theme.accent}
        strokeWidth={2}
        strokeLinejoin="round"
        style={{ filter: 'drop-shadow(0 0 6px rgba(124,58,237,0.45))' }}
      />

      {axes.map((a, i) => {
        const p = pointFor(scores[a.key as keyof typeof scores] ?? 0, i);
        return (
          <circle
            key={`pt-${a.key}`}
            cx={p.x}
            cy={p.y}
            r={3.5}
            fill={theme.accent}
            stroke={theme.bg}
            strokeWidth={1.5}
          />
        );
      })}

      {axes.map((a, i) => {
        const labelP = polarToCartesian(cx, cy, radius + 16, angleFor(i));
        return (
          <text
            key={`lb-${a.key}`}
            x={labelP.x}
            y={labelP.y}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize={11}
            fill={theme.textSecondary}
            fontFamily={fontStack}
          >
            {a.label}
          </text>
        );
      })}

      <text
        x={cx}
        y={cy - 2}
        textAnchor="middle"
        fontSize={20}
        fontWeight={700}
        fill={theme.text}
        fontFamily={fontStack}
      >
        {Math.round(
          (scores.character + scores.plot + scores.world + scores.pacing + scores.style) / 5,
        )}
      </text>
      <text
        x={cx}
        y={cy + 14}
        textAnchor="middle"
        fontSize={10}
        fill={theme.textMuted}
        fontFamily={fontStack}
      >
        综合评分
      </text>
    </svg>
    </div>
  );
}

// ============================================================================
// 5) Pie: Genre Distribution
// ============================================================================
function PieChart({
  data,
  delay = 0,
}: {
  data: { genre: string; count: number }[];
  delay?: number;
}) {
  const size = 220;
  const cx = size / 2;
  const cy = size / 2;
  const r = 80;
  const innerR = 50;

  if (data.length === 0) return <EmptyHint text="暂无题材数据" />;

  const total = data.reduce((sum, d) => sum + d.count, 0);
  if (total === 0) return <EmptyHint text="暂无题材数据" />;

  let cumulative = 0;
  const slices = data.map((d, i) => {
    const portion = d.count / total;
    const startAngle = cumulative * 360;
    const endAngle = (cumulative + portion) * 360;
    cumulative += portion;

    const startOuter = polarToCartesian(cx, cy, r, endAngle);
    const endOuter = polarToCartesian(cx, cy, r, startAngle);
    const startInner = polarToCartesian(cx, cy, innerR, endAngle);
    const endInner = polarToCartesian(cx, cy, innerR, startAngle);
    const largeArc = endAngle - startAngle > 180 ? 1 : 0;

    const path =
      portion >= 0.999
        ? // Full circle special case
          `M ${cx - r} ${cy} A ${r} ${r} 0 1 1 ${cx + r} ${cy} A ${r} ${r} 0 1 1 ${cx - r} ${cy} ` +
          `M ${cx - innerR} ${cy} A ${innerR} ${innerR} 0 1 0 ${cx + innerR} ${cy} ` +
          `A ${innerR} ${innerR} 0 1 0 ${cx - innerR} ${cy} Z`
        : `M ${startOuter.x} ${startOuter.y} ` +
          `A ${r} ${r} 0 ${largeArc} 1 ${endOuter.x} ${endOuter.y} ` +
          `L ${startInner.x} ${startInner.y} ` +
          `A ${innerR} ${innerR} 0 ${largeArc} 0 ${endInner.x} ${endInner.y} Z`;

    return { path, color: palette[i % palette.length], label: d.genre, count: d.count, percent: portion };
  });

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        animationDelay: `${delay}ms`,
        // 适配 v8-card flex column：撑满剩余高度
        flex: 1,
        minHeight: 0,
        overflow: 'hidden',
      }}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label="题材分布饼图"
        style={{ flexShrink: 0 }}
      >
        {slices.map((s, i) => (
          <path
            key={i}
            d={s.path}
            fill={s.color}
            stroke={theme.bg}
            strokeWidth={1.5}
            style={{ transition: 'opacity 200ms ease', filter: `drop-shadow(0 0 4px ${s.color}55)` }}
          />
        ))}
        <text
          x={cx}
          y={cy - 2}
          textAnchor="middle"
          fontSize={20}
          fontWeight={700}
          fill={theme.text}
          fontFamily={fontStack}
        >
          {total}
        </text>
        <text
          x={cx}
          y={cy + 14}
          textAnchor="middle"
          fontSize={10}
          fill={theme.textMuted}
          fontFamily={fontStack}
        >
          题材章节
        </text>
      </svg>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1, minWidth: 0, overflow: 'hidden' }}>
        {data.map((d, i) => (
          <div
            key={d.genre}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              fontSize: 12,
              color: theme.text,
            }}
          >
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: 2,
                background: palette[i % palette.length],
                flexShrink: 0,
              }}
            />
            <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {d.genre}
            </span>
            <span style={{ color: theme.textSecondary, fontVariantNumeric: 'tabular-nums' }}>
              {d.count} ({Math.round((d.count / total) * 100)}%)
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================================================
// KPI Card
// ============================================================================
// 6) Latency histogram (small bar list)
// ============================================================================
function LatencyBars({
  data,
  delay = 0,
}: {
  data: Array<{ bucket: string; count: number }>;
  delay?: number;
}) {
  if (!data || data.length === 0) return <EmptyHint text="暂无耗时数据" />;
  const total = data.reduce((s, d) => s + d.count, 0);
  if (total === 0) return <EmptyHint text="暂无耗时数据" />;
  const max = Math.max(...data.map((d) => d.count), 1);
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        animationDelay: `${delay}ms`,
        // 适配 v8-card flex column
        flex: 1,
        minHeight: 0,
        overflowY: 'auto',
      }}
    >
      {data.map((d) => {
        const pct = (d.count / max) * 100;
        const percentOfTotal = total > 0 ? Math.round((d.count / total) * 100) : 0;
        return (
          <div key={d.bucket} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 56, fontSize: 11, color: theme.text, textAlign: 'right' }}>
              {d.bucket}
            </div>
            <div
              style={{
                flex: 1,
                height: 12,
                background: 'rgba(124, 58, 237, 0.08)',
                borderRadius: 4,
                overflow: 'hidden',
                position: 'relative',
              }}
            >
              <div
                style={{
                  width: `${pct}%`,
                  height: '100%',
                  background: `linear-gradient(90deg, ${theme.cyan}cc, ${theme.cyan})`,
                  borderRadius: 4,
                  transition: 'width 600ms ease',
                  boxShadow: `0 0 6px ${theme.cyan}55`,
                }}
              />
            </div>
            <div
              style={{
                width: 64,
                fontSize: 11,
                color: theme.textSecondary,
                textAlign: 'right',
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {d.count} ({percentOfTotal}%)
            </div>
          </div>
        );
      })}
    </div>
  );
}
function KpiCard({
  label,
  value,
  unit,
  accentColor,
  delay,
}: {
  label: string;
  value: string;
  unit?: string;
  accentColor: string;
  delay: number;
}) {
  return (
    <div
      className="v8-card"
      style={{
        flex: 1,
        minWidth: 160,
        animationDelay: `${delay}ms`,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: 3,
          height: '100%',
          background: `linear-gradient(180deg, ${accentColor}, transparent)`,
        }}
      />
      <div
        style={{
          fontSize: 12,
          color: theme.textSecondary,
          fontWeight: 600,
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 28,
          fontWeight: 700,
          color: theme.text,
          fontFamily: fontStack,
          letterSpacing: -0.5,
          lineHeight: 1.1,
        }}
      >
        {value}
        {unit && (
          <span style={{ fontSize: 13, color: theme.textMuted, marginLeft: 4, fontWeight: 500 }}>
            {unit}
          </span>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================
export function VisualizationTab8Dashboard({
  novelStats,
  chapterStats,
  characterFrequency,
  consistency,
  genreDistribution,
  latencyHist,
  progressPercent,
  avgLatencyMs,
  totalDurationSeconds = 0,
}: VisualizationTab8DashboardProps) {
  ensureGlobalStyles();

  const empty = useMemo(() => {
    return (
      (!novelStats || novelStats.totalChapters === 0) &&
      (!chapterStats || chapterStats.length === 0) &&
      (!characterFrequency || characterFrequency.length === 0) &&
      (!genreDistribution || genreDistribution.length === 0)
    );
  }, [novelStats, chapterStats, characterFrequency, genreDistribution]);

  // ----- KPI computations -----
  const safeNovel = novelStats ?? {
    title: '未命名小说',
    totalWords: 0,
    totalChapters: 0,
    completedChapters: 0,
  };

  const progress =
    typeof progressPercent === 'number'
      ? progressPercent
      : safeNovel.totalChapters > 0
        ? Math.round((safeNovel.completedChapters / safeNovel.totalChapters) * 100)
        : 0;

  // ----- Donut data -----
  const statusBuckets = useMemo(() => {
    const map: Record<string, number> = {
      completed: 0,
      failed: 0,
      pending: 0,
    };
    (chapterStats || []).forEach((c) => {
      const s = (c.status || '').toLowerCase();
      if (s === 'completed' || s === 'finalized' || s === 'done') map.completed += 1;
      else if (s === 'failed' || s === 'error') map.failed += 1;
      else map.pending += 1;
    });
    return map;
  }, [chapterStats]);

  const donutData = [
    { label: '已完成', value: statusBuckets.completed, color: theme.success },
    { label: '撰写中', value: statusBuckets.pending, color: theme.warning },
    { label: '失败', value: statusBuckets.failed, color: theme.error },
  ];
  const totalChaptersFromStats = donutData.reduce((s, d) => s + d.value, 0);

  // ----- Top 10 characters -----
  const topCharacters = useMemo(
    () =>
      [...(characterFrequency || [])]
        .sort((a, b) => b.count - a.count)
        .slice(0, 10),
    [characterFrequency],
  );

  if (empty) {
    return (
      <div
        className="cc-viz-panel"
        style={{
          padding: 12,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          minHeight: '100%',
          fontFamily: fontStack,
        }}
      >
        <div
          style={{
            fontSize: 24,
            fontWeight: 700,
            color: theme.text,
            letterSpacing: -0.5,
          }}
        >
          小说创作仪表盘
        </div>
        <div
          className="v8-card"
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 10,
            padding: '56px 24px',
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: 40, lineHeight: 1 }}>📊</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: theme.text }}>
            暂无创作数据
          </div>
          <div style={{ fontSize: 13, color: theme.textSecondary, maxWidth: 420, lineHeight: 1.6 }}>
            启动 AI 全自动创作后，这里会实时汇总：累计字数、章节进度、角色出场频次、
            五维一致性评分与题材分布等真实指标。
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className="cc-viz-panel"
      style={{
        flex: 1,
        minHeight: 0,
        height: '100%',
        padding: 16,
        display: 'flex',
        flexDirection: 'column',
        gap: 14,
        fontFamily: fontStack,
      }}
    >
      {/* Header */}
      <div style={{ animation: 'v8-fade-in-up 360ms ease both' }}>
        <div
          style={{
            fontSize: 22,
            fontWeight: 700,
            color: theme.text,
            letterSpacing: -0.5,
          }}
        >
          {safeNovel.title || '小说创作仪表盘'}
        </div>
        <div
          style={{
            fontSize: 14,
            color: theme.textSecondary,
            marginTop: 4,
          }}
        >
          多维度数据一览 · 实时洞察创作状态
        </div>
      </div>

      {/* KPI cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: 14,
        }}
      >
        <KpiCard
          label="总字数"
          value={formatNumber(safeNovel.totalWords)}
          accentColor={theme.accent}
          delay={0}
        />
        <KpiCard
          label="已完成章节"
          value={`${safeNovel.completedChapters}`}
          unit={`/ ${safeNovel.totalChapters}`}
          accentColor={theme.success}
          delay={60}
        />
        <KpiCard
          label="累计耗时"
          value={formatDuration(totalDurationSeconds)}
          accentColor={theme.purple}
          delay={120}
        />
        <KpiCard
          label="当前进度"
          value={`${progress}`}
          unit="%"
          accentColor={theme.warning}
          delay={180}
        />
      </div>

      {/* Chart grid - 两列布局，每张图都有更大空间 */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)',
          gap: 14,
        }}
      >
        {/* Donut */}
        <div className="v8-card" style={{ animationDelay: '240ms', minHeight: 320 }}>
          <CardHeader
            title="章节完成度"
            subtitle={`共 ${totalChaptersFromStats} 章`}
            delay={240}
          />
          <DonutChart data={donutData} delay={240} />
        </div>

        {/* Line */}
        <div className="v8-card" style={{ animationDelay: '300ms', minHeight: 320 }}>
          <CardHeader
            title="字数趋势"
            subtitle="每章字数随章节号变化"
            delay={300}
          />
          <LineChart data={chapterStats || []} delay={300} />
        </div>

        {/* Bar */}
        <div className="v8-card" style={{ animationDelay: '360ms', minHeight: 320 }}>
          <CardHeader
            title="角色出现频次"
            subtitle="TOP 10 角色"
            delay={360}
          />
          <BarChart data={topCharacters} delay={360} />
        </div>

        {/* Radar */}
        <div className="v8-card" style={{ animationDelay: '420ms', minHeight: 320 }}>
          <CardHeader
            title="一致性检查"
            subtitle="五维评分（0-100）"
            delay={420}
          />
          <RadarChart scores={consistency} delay={420} />
        </div>

        {/* Pie */}
        <div className="v8-card" style={{ animationDelay: '480ms', minHeight: 320 }}>
          <CardHeader
            title="题材分布"
            subtitle="每种题材章节数"
            delay={480}
          />
          <PieChart data={genreDistribution || []} delay={480} />
        </div>

        {/* Latency histogram (only when data available) */}
        {latencyHist && latencyHist.length > 0 && (
          <div className="v8-card" style={{ animationDelay: '540ms', minHeight: 320 }}>
            <CardHeader
              title="AI 任务耗时分布"
              subtitle={
                typeof avgLatencyMs === 'number'
                  ? `平均 ${(avgLatencyMs / 1000).toFixed(1)} 秒`
                  : '按耗时分桶统计'
              }
              delay={540}
            />
            <LatencyBars data={latencyHist} delay={540} />
          </div>
        )}
      </div>
    </div>
  );
}

export default VisualizationTab8Dashboard;
