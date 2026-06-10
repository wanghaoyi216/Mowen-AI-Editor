import { useEffect, useState } from "react";

import {
  executeAutoNovelWorkflow,
  executeTrendExploration,
  fetchTrendExplorations,
  fetchWorldbookEntries,
} from "../lib/api";
import type { AITask, Character, PlotLine, TrendExploration, WorldbookEntry } from "../types";

type TrendWorkbenchProps = {
  projectId: number | null;
};

type TrendTopic = {
  rank?: number;
  title: string;
  insight?: string;
  url?: string;
  score?: number | null;
};

type TrendDirection = {
  title: string;
  premise?: string;
  conflict?: string;
  source_url?: string;
};

type TrendRawFindings = {
  sources?: Array<{
    title?: string;
    url?: string;
    snippet?: string;
    score?: number | null;
  }>;
};

function parseJsonArray<T>(raw: string | null | undefined, fallbackMapper: (item: unknown) => T | null): T[] {
  if (!raw) {
    return [];
  }
  try {
    const value = JSON.parse(raw) as unknown;
    return Array.isArray(value) ? value.map(fallbackMapper).filter((item): item is T => item !== null) : [];
  } catch {
    return [];
  }
}

function parseTrendTopics(raw: string | null | undefined): TrendTopic[] {
  return parseJsonArray<TrendTopic>(raw, (item) => {
    if (typeof item === "string") {
      return { title: item };
    }
    if (item && typeof item === "object") {
      const value = item as Partial<TrendTopic>;
      return value.title ? { title: value.title, insight: value.insight, url: value.url, score: value.score } : null;
    }
    return null;
  });
}

function parseTrendDirections(raw: string | null | undefined): TrendDirection[] {
  return parseJsonArray<TrendDirection>(raw, (item) => {
    if (typeof item === "string") {
      return { title: item };
    }
    if (item && typeof item === "object") {
      const value = item as Partial<TrendDirection>;
      return value.title ? { title: value.title, premise: value.premise, conflict: value.conflict, source_url: value.source_url } : null;
    }
    return null;
  });
}

function parseTrendTags(raw: string | null | undefined): string[] {
  return parseJsonArray<string>(raw, (item) => (typeof item === "string" ? item : null));
}

function parseRawFindings(raw: string | null | undefined): TrendRawFindings {
  if (!raw) {
    return {};
  }
  try {
    const value = JSON.parse(raw) as TrendRawFindings;
    return value && typeof value === "object" ? value : {};
  } catch {
    return {};
  }
}

export function TrendWorkbench({ projectId }: TrendWorkbenchProps) {
  const [title, setTitle] = useState("热门题材探索");
  const [query, setQuery] = useState("2026 热门网络小说题材 趋势 爆款 标签");
  const [chapterTitle, setChapterTitle] = useState("第 1 章·自动生成开场");
  const [designGuidance, setDesignGuidance] = useState("强化悬念、建立世界规则、压缩说明性段落。");
  const [styleHint, setStyleHint] = useState("紧张克制、带镜头感、情绪缓慢升高。");
  const [revisionFocus, setRevisionFocus] = useState("优先修复人物动机与世界规则一致性，并增强结尾钩子。");
  const [trends, setTrends] = useState<TrendExploration[]>([]);
  const [worldbookEntries, setWorldbookEntries] = useState<WorldbookEntry[]>([]);
  const [mappedPlots, setMappedPlots] = useState<PlotLine[]>([]);
  const [mappedCharacters, setMappedCharacters] = useState<Character[]>([]);
  const [mappedWorldbook, setMappedWorldbook] = useState<WorldbookEntry[]>([]);
  const [workflowTask, setWorkflowTask] = useState<AITask | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function loadBase() {
    if (!projectId) {
      setTrends([]);
      setWorldbookEntries([]);
      return;
    }
    const [trendItems, worldbookItems] = await Promise.all([
      fetchTrendExplorations(projectId),
      fetchWorldbookEntries(projectId),
    ]);
    setTrends(trendItems);
    setWorldbookEntries(worldbookItems);
  }

  useEffect(() => {
    void loadBase().catch((loadError) => {
      setError(loadError instanceof Error ? loadError.message : "Unknown error");
    });
  }, [projectId]);

  async function handleExecuteTrend() {
    if (!projectId) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await executeTrendExploration(projectId, title, query);
      await loadBase();
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  async function handleExecuteWorkflow() {
    if (!projectId) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await executeAutoNovelWorkflow(projectId, {
        title,
        queryText: query,
        chapterNo: 1,
        chapterTitle,
        chapterSummary: "自动工作流生成的章节，用于快速建立题材方向与开场张力。",
        chapterObjective: "建立主角处境和当前章节冲突钩子。",
        chapterConflict: "角色目标与外部规则产生第一轮摩擦。",
        designGuidance,
        styleHint,
        revisionFocus,
        wordTarget: 1800,
      });
      setWorkflowTask(result.task);
      setMappedPlots([]);
      setMappedCharacters([]);
      setMappedWorldbook([]);
      await loadBase();
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel-grid">
      <article className="panel">
        <div className="panel-header">
          <h2>热点探索工作台</h2>
          <span>Tavily + Firecrawl + Workflow</span>
        </div>
        <div className="toolbar">
          <label className="field grow">
            <span>探索标题</span>
            <input value={title} onChange={(event) => setTitle(event.target.value)} />
          </label>
        </div>
        <label className="field grow">
          <span>搜索查询</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} />
        </label>
        <label className="field grow">
          <span>自动章节标题</span>
          <input value={chapterTitle} onChange={(event) => setChapterTitle(event.target.value)} />
        </label>
        <label className="field grow">
          <span>章节设计指导</span>
          <input value={designGuidance} onChange={(event) => setDesignGuidance(event.target.value)} />
        </label>
        <label className="field grow">
          <span>文风提示</span>
          <input value={styleHint} onChange={(event) => setStyleHint(event.target.value)} />
        </label>
        <label className="field grow">
          <span>修订重点</span>
          <input value={revisionFocus} onChange={(event) => setRevisionFocus(event.target.value)} />
        </label>
        <div className="toolbar">
          <button type="button" onClick={() => void handleExecuteTrend()} disabled={busy || !projectId}>
            {busy ? "执行中..." : "执行热点探索"}
          </button>
          <button type="button" onClick={() => void handleExecuteWorkflow()} disabled={busy || !projectId}>
            {busy ? "执行中..." : "一键自动创作流程"}
          </button>
        </div>
        {!projectId ? <p className="hero-copy">请先在仪表盘选择项目。</p> : null}
        {error ? <p className="alert-text">执行失败：{error}</p> : null}
        <div className="trend-list">
          {trends.map((trend) => (
            <TrendInsightCard
              key={trend.id}
              trend={trend}
            />
          ))}
          {!trends.length && projectId ? (
            <p className="hero-copy">还没有热点探索结果。执行一次探索后，这里会展示趋势洞察、标签、来源和可映射方向。</p>
          ) : null}
        </div>
      </article>

      <article className="panel parchment">
        <div className="panel-header">
          <h2>映射结果与自动产出</h2>
          <span>Plot / Character / Worldbook / Chapter</span>
        </div>
        {workflowTask ? (
          <div className="chapter-card">
            <strong>自动流程已启动</strong>
            <p>task: #{workflowTask.id}</p>
            <p>{workflowTask.plan_text ?? "正在后台执行，底部运行日志会持续刷新。"}</p>
          </div>
        ) : null}
        <AssetResultSection
          mappedPlots={mappedPlots}
          mappedCharacters={mappedCharacters}
          mappedWorldbook={mappedWorldbook}
          worldbookEntries={worldbookEntries}
        />
      </article>
    </section>
  );
}

function TrendInsightCard({
  trend,
}: {
  trend: TrendExploration;
}) {
  const topics = parseTrendTopics(trend.extracted_topics);
  const tags = parseTrendTags(trend.extracted_tags);
  const directions = parseTrendDirections(trend.suggested_directions);
  const rawFindings = parseRawFindings(trend.raw_findings);
  const sources = rawFindings.sources ?? [];

  return (
    <article className="trend-card">
      <div className="trend-card-header">
        <div>
          <strong>{trend.title}</strong>
          <p>{trend.query_text}</p>
        </div>
        <div className="trend-actions">
          <span className="badge badge-完成">{trend.status}</span>
        </div>
      </div>

      {tags.length ? (
        <div className="chip-row">
          {tags.slice(0, 12).map((tag) => (
            <span className="info-chip" key={tag}>
              {tag}
            </span>
          ))}
        </div>
      ) : null}

      <div className="insight-grid">
        <section>
          <h3>趋势洞察</h3>
          <div className="plain-stack">
            {topics.slice(0, 4).map((topic, index) => (
              <div className="insight-item" key={`${topic.title}-${index}`}>
                <strong>{topic.title}</strong>
                <p>{topic.insight ?? "暂无摘要"}</p>
                {topic.url ? (
                  <a href={topic.url} target="_blank" rel="noreferrer">
                    来源
                  </a>
                ) : null}
              </div>
            ))}
          </div>
        </section>
        <section>
          <h3>创作方向</h3>
          <div className="plain-stack">
            {directions.slice(0, 4).map((direction, index) => (
              <div className="insight-item" key={`${direction.title}-${index}`}>
                <strong>{direction.title}</strong>
                <p>{direction.premise ?? "暂无前提"}</p>
                <p>{direction.conflict ?? "暂无冲突设计"}</p>
              </div>
            ))}
          </div>
        </section>
      </div>

      {sources.length ? (
        <details className="source-details">
          <summary>来源证据 {sources.length}</summary>
          <div className="plain-stack">
            {sources.slice(0, 6).map((source, index) => (
              <div className="source-item" key={`${source.url ?? source.title}-${index}`}>
                <strong>{source.title ?? source.url ?? `来源 ${index + 1}`}</strong>
                <p>{source.snippet ?? "暂无摘要"}</p>
                {source.url ? (
                  <a href={source.url} target="_blank" rel="noreferrer">
                    打开来源
                  </a>
                ) : null}
              </div>
            ))}
          </div>
        </details>
      ) : null}
    </article>
  );
}

function AssetResultSection({
  mappedPlots,
  mappedCharacters,
  mappedWorldbook,
  worldbookEntries,
}: {
  mappedPlots: PlotLine[];
  mappedCharacters: Character[];
  mappedWorldbook: WorldbookEntry[];
  worldbookEntries: WorldbookEntry[];
}) {
  return (
    <>
      <div className="asset-summary">
        <div className="stat-card">
          <span>剧情线</span>
          <strong>{mappedPlots.length}</strong>
        </div>
        <div className="stat-card">
          <span>角色候选</span>
          <strong>{mappedCharacters.length}</strong>
        </div>
        <div className="stat-card">
          <span>设定条目</span>
          <strong>{mappedWorldbook.length}</strong>
        </div>
      </div>
      <div className="graph-list">
        {mappedPlots.map((item) => (
          <div className="task-item" key={`mapped-plot-${item.id}`}>
            <div>
              <strong>{item.title}</strong>
              <p>{item.summary ?? "暂无摘要"}</p>
            </div>
            <span className="badge badge-进行中">plot</span>
          </div>
        ))}
        {mappedCharacters.map((item) => (
          <div className="task-item" key={`mapped-character-${item.id}`}>
            <div>
              <strong>{item.name}</strong>
              <p>{item.arc_summary ?? "暂无角色弧线"}</p>
            </div>
            <span className="badge badge-完成">character</span>
          </div>
        ))}
        {mappedWorldbook.map((item) => (
          <div className="task-item" key={`mapped-worldbook-${item.id}`}>
            <div>
              <strong>{item.title}</strong>
              <p>{item.content}</p>
            </div>
            <span className="badge badge-待执行">worldbook</span>
          </div>
        ))}
        {!mappedPlots.length && !mappedCharacters.length && !mappedWorldbook.length ? (
          <p className="hero-copy">执行热点探索或一键流程后，这里会只读展示 AI 自动映射与章节生成结果。</p>
        ) : null}
      </div>
      <div className="graph-list">
        {worldbookEntries.map((item) => (
          <div className="task-item" key={`worldbook-${item.id}`}>
            <div>
              <strong>{item.title}</strong>
              <p>{item.category}</p>
            </div>
            <span className="badge badge-完成">saved</span>
          </div>
        ))}
      </div>
    </>
  );
}
