import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  TrendingUp,
  Globe,
  FileText,
  ShieldCheck,
  Network,
  BarChart3,
  GitBranch,
  LayoutDashboard,
} from 'lucide-react';
import { colors, spacing, borderRadius } from './styles';
import { VisualizationTab1Trends } from './VisualizationTab1Trends';
import { VisualizationTab2World } from './VisualizationTab2World';
import { VisualizationTab3Chapter } from './VisualizationTab3Chapter';
import { VisualizationTab4Consistency } from './VisualizationTab4Consistency';
import { VisualizationTab5Entity } from './VisualizationTab5Entity';
import { VisualizationTab6Stats } from './VisualizationTab6Stats';
import { VisualizationTab7StoryArc } from './VisualizationTab7StoryArc';
import { VisualizationTab8Dashboard } from './VisualizationTab8Dashboard';
import {
  fetchStoryArc,
  fetchDashboard,
  fetchBooks,
  type Book,
  type StoryArcPayload,
  type DashboardPayload,
  type StoryArcNode,
  type StoryArcEdge,
} from '../../lib/api';
import VisualizationEmptyState from './VisualizationEmptyState';

const tabs = [
  { key: 'trend', label: '热点探索', icon: TrendingUp },
  { key: 'world', label: '世界构建', icon: Globe },
  { key: 'chapter', label: '章节写作', icon: FileText },
  { key: 'consistency', label: '一致性检查', icon: ShieldCheck },
  { key: 'entity', label: '故事图谱', icon: Network },
  { key: 'story_arc', label: '故事脉络', icon: GitBranch },
  { key: 'stats', label: '全局统计', icon: BarChart3 },
  { key: 'dashboard', label: '故事总览', icon: LayoutDashboard },
];

type MainVisualizationPanelProps = {
  currentStage: number;
  projectId?: number;
  activeTaskId?: number | null;
  taskStatus?: string;
};

function PlaceholderView({ title, icon }: { title: string; icon: React.ReactNode }) {
  return <VisualizationEmptyState tabName={title} icon={icon} />;
}

// Task A3: 错误 banner + 重试按钮。区分网络 / 5xx / 4xx 三类错误。
function ErrorBanner({
  error,
  onRetry,
  retryLabel = "重试",
}: {
  error: string;
  onRetry?: () => void;
  retryLabel?: string;
}) {
  let displayMsg = error;
  let bannerStyle: React.CSSProperties = {
    border: '1px solid #ec4899',
    background: 'rgba(236, 72, 153, 0.08)',
    color: '#9d174d',
  };
  if (/failed to fetch|无法连接|network/i.test(error)) {
    displayMsg = `无法连接后端（${error}）。请检查后端服务是否启动。`;
  } else if (/5\d{2}/.test(error)) {
    displayMsg = `后端服务异常：${error}`;
    bannerStyle = {
      ...bannerStyle,
      background: 'rgba(220, 38, 38, 0.08)',
      border: '1px solid #dc2626',
      color: '#991b1b',
    };
  } else if (/4\d{2}/.test(error)) {
    displayMsg = `请求参数错误：${error}`;
  }
  return (
    <div
      style={{
        ...bannerStyle,
        padding: '10px 14px',
        borderRadius: 8,
        marginBottom: 12,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        fontSize: 13,
      }}
    >
      <span style={{ flex: 1 }}>⚠️ {displayMsg}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            padding: '4px 12px',
            background: 'rgba(255, 255, 255, 0.8)',
            border: '1px solid currentColor',
            borderRadius: 6,
            color: 'inherit',
            cursor: 'pointer',
            fontSize: 12,
            fontWeight: 600,
          }}
        >
          {retryLabel}
        </button>
      )}
    </div>
  );
}

const EMPTY_STORY_ARC: StoryArcPayload = {
  nodes: [] as StoryArcNode[],
  edges: [] as StoryArcEdge[],
  stats: { chapters: 0, plotLines: 0, plans: 0 },
};

const EMPTY_DASHBOARD: DashboardPayload = {
  kpi: {
    completedChapters: 0,
    totalChapters: 0,
    totalWords: 0,
    avgLatencyMs: 0,
    totalDurationSeconds: 0,
    progressPercent: 0,
  },
  chapterProgress: [],
  wordCountBar: [],
  latencyHist: [],
  characterFreq: [],
  consistencyRadar: { character: 0, plot: 0, world: 0, pacing: 0, style: 0 },
  genreDistribution: [],
  novel: null,
};

function stableJson(value: unknown): string {
  return JSON.stringify(value);
}

export function MainVisualizationPanel({ currentStage, projectId, activeTaskId, taskStatus }: MainVisualizationPanelProps) {
  const [activeTab, setActiveTab] = useState('trend');
  const [storyArc, setStoryArc] = useState<StoryArcPayload>(EMPTY_STORY_ARC);
  const [dashboard, setDashboard] = useState<DashboardPayload>(EMPTY_DASHBOARD);
  const [loadingStoryArc, setLoadingStoryArc] = useState(false);
  const [loadingDashboard, setLoadingDashboard] = useState(false);
  const [storyArcError, setStoryArcError] = useState<string | null>(null);
  const [dashboardError, setDashboardError] = useState<string | null>(null);
  // Task 8: 故事脉络（Tab7）按 book 过滤
  const [books, setBooks] = useState<Book[]>([]);
  const [booksLoading, setBooksLoading] = useState(false);
  const [storyArcBookId, setStoryArcBookId] = useState<number | null>(null);
  const [vizReloadToken, setVizReloadToken] = useState(0);
  // 用 ref 存储"上次给 Tab5 的 reload token"，避免 setState 触发整个 panel re-render。
  // 仅当 activeTab === 'entity' 时通过 ref 派发，避免非 entity tab 反复重渲染。
  const vizReloadTokenRef = useRef(0);
  const vizReloadTokenTickRef = useRef(0);
  const storyArcSnapshotRef = useRef('');
  const dashboardSnapshotRef = useRef('');

  // 把 Tab7 用的 nodes 数组做稳定包装：只在 storyArc 引用变化时新建，
  // 避免父组件轮询 re-render 产生新 array 引用导致 Tab7 d3 useEffect 重跑。
  const storyArcNodesForTab7 = useMemo(
    () => storyArc.nodes.map((n) => ({ ...n, chapterNo: n.chapterNo ?? undefined })),
    [storyArc]
  );

  useEffect(() => {
    if (currentStage >= 0 && currentStage <= 2) setActiveTab('trend');
    else if (currentStage >= 3 && currentStage <= 4) setActiveTab('world');
    else if (currentStage === 5) setActiveTab('chapter');
    else if (currentStage === 6) setActiveTab('consistency');
    else if (currentStage === 7) setActiveTab('stats');
  }, [currentStage]);

  // 加载当前 project 的 books（用于 Tab7 book 过滤）
  useEffect(() => {
    if (projectId == null) {
      setBooks([]);
      return;
    }
    let cancelled = false;
    async function load() {
      setBooksLoading(true);
      try {
        const list = await fetchBooks(projectId as number);
        if (cancelled) return;
        setBooks(list);
        // 关键：当前 bookId 必须属于新项目的 books 列表，否则置 null。
        // 避免"项目 2 选了 book=2 → 切到项目 1 时仍保留 book=2，
        // 导致后端按 book=2 过滤后无数据 → 故事脉络一片空白"。
        setStoryArcBookId((prev) => {
          if (prev != null && list.some((b) => b.id === prev)) {
            return prev;
          }
          return list.length > 0 ? list[0].id : null;
        });
      } catch {
        if (!cancelled) setBooks([]);
      } finally {
        if (!cancelled) setBooksLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [projectId]);

  // 拉取故事脉络（Tab7）—— 受 storyArcBookId 影响
  const loadStoryArc = useCallback(async () => {
    if (projectId == null) {
      setStoryArc(EMPTY_STORY_ARC);
      return;
    }
    setLoadingStoryArc(true);
    setStoryArcError(null);
    try {
      const data = await fetchStoryArc(projectId, storyArcBookId);
      const snapshot = stableJson(data);
      if (snapshot !== storyArcSnapshotRef.current) {
        storyArcSnapshotRef.current = snapshot;
        setStoryArc(data);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setStoryArcError(msg);
      setStoryArc(EMPTY_STORY_ARC);
    } finally {
      setLoadingStoryArc(false);
    }
  }, [projectId, storyArcBookId]);

  // 拉取故事总览（Tab8）
  const loadDashboard = useCallback(async () => {
    if (projectId == null) {
      setDashboard(EMPTY_DASHBOARD);
      return;
    }
    setLoadingDashboard(true);
    setDashboardError(null);
    try {
      const data = await fetchDashboard(projectId);
      const snapshot = stableJson(data);
      if (snapshot !== dashboardSnapshotRef.current) {
        dashboardSnapshotRef.current = snapshot;
        setDashboard(data);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setDashboardError(msg);
      setDashboard(EMPTY_DASHBOARD);
    } finally {
      setLoadingDashboard(false);
    }
  }, [projectId]);

  // 当 projectId / storyArcBookId 变化时立即拉取一次
  useEffect(() => {
    void loadStoryArc();
    void loadDashboard();
  }, [loadStoryArc, loadDashboard]);

  useEffect(() => {
    if (projectId == null || !activeTaskId || !['running', 'pending', 'cancelling'].includes(taskStatus ?? '')) {
      return;
    }
    // Tab7/8 在最外层轮询里走 snapshot 比对，引用未变就不触发重建；
    // Tab5 的 reloadToken 仅当用户停留在 entity tab 时递增，避免其它
    // tab 反复被 setState 强制重渲染（这是故事脉络模块闪烁的根因之一）。
    const id = window.setInterval(() => {
      void loadStoryArc();
      void loadDashboard();
      if (activeTab === 'entity') {
        setVizReloadToken((token) => token + 1);
      }
    }, 5000);
    return () => window.clearInterval(id);
  }, [projectId, activeTaskId, taskStatus, activeTab, loadStoryArc, loadDashboard]);

  const renderContent = () => {
    switch (activeTab) {
      case 'trend':
        return <VisualizationTab1Trends projectId={projectId} />;
      case 'world':
        return <VisualizationTab2World projectId={projectId} />;
      case 'chapter':
        return <VisualizationTab3Chapter projectId={projectId} />;
      case 'consistency':
        return <VisualizationTab4Consistency projectId={projectId} />;
      case 'entity':
        return <VisualizationTab5Entity projectId={projectId} reloadToken={vizReloadToken} />;
      case 'story_arc':
        return (
          <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', padding: spacing.lg, position: 'relative', boxSizing: 'border-box' }}>
            {loadingStoryArc && (
              <div style={{ position: 'absolute', top: spacing.sm, right: spacing.sm, color: colors.textSecondary, fontSize: 12 }}>
                加载中…
              </div>
            )}
            {storyArcError && (
              <ErrorBanner
                error={storyArcError}
                onRetry={() => void loadStoryArc()}
              />
            )}
            <VisualizationTab7StoryArc
              nodes={storyArcNodesForTab7}
              edges={storyArc.edges}
              stats={storyArc.stats}
              projectId={projectId ?? undefined}
              currentBookId={storyArcBookId}
              onBookChange={setStoryArcBookId}
              books={books}
              booksLoading={booksLoading}
            />
          </div>
        );
      case 'stats':
        return <VisualizationTab6Stats projectId={projectId} />;
      case 'dashboard':
        return (
          <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', padding: spacing.lg, position: 'relative', boxSizing: 'border-box' }}>
            {loadingDashboard && (
              <div style={{ position: 'absolute', top: spacing.sm, right: spacing.sm, color: colors.textSecondary, fontSize: 12 }}>
                加载中…
              </div>
            )}
            {dashboardError && (
              <ErrorBanner
                error={dashboardError}
                onRetry={() => void loadDashboard()}
              />
            )}
            <VisualizationTab8Dashboard
              novelStats={{
                title: dashboard.novel?.title ?? '',
                totalWords: dashboard.kpi.totalWords,
                totalChapters: dashboard.kpi.totalChapters,
                completedChapters: dashboard.kpi.completedChapters,
              }}
              chapterStats={dashboard.chapterProgress.map((c) => ({
                chapterNo: c.chapterNo,
                wordCount: c.wordCount,
                status: c.status,
              }))}
              characterFrequency={dashboard.characterFreq}
              consistency={dashboard.consistencyRadar}
              genreDistribution={dashboard.genreDistribution}
              latencyHist={dashboard.latencyHist}
              progressPercent={dashboard.kpi.progressPercent}
              avgLatencyMs={dashboard.kpi.avgLatencyMs}
              totalDurationSeconds={dashboard.kpi.totalDurationSeconds}
            />
          </div>
        );
      default:
        return <PlaceholderView title="视图未找到" icon={<BarChart3 size={40} color={colors.idle} />} />;
    }
  };

  return (
    <div className="cc-main-panel">
      <div className="cc-main-tabs">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.key}
              type="button"
              className={`cc-tab ${activeTab === tab.key ? 'cc-tab-active' : ''}`}
              onClick={() => {
                setActiveTab(tab.key);
                // Task A2.4 — 切到 story_arc tab 时立即强制拉取一次数据，
                // 不必等 5s 轮询。
                if (tab.key === 'story_arc') {
                  void loadStoryArc();
                }
              }}
            >
              <Icon size={15} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>
      <div className="cc-main-content">
        {renderContent()}
      </div>
    </div>
  );
}
