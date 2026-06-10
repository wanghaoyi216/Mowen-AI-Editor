import { useEffect, useMemo, useState } from "react";

import { useProjectContext } from "../context/ProjectContext";
import {
  fetchCharacters,
  fetchEventParticipations,
  fetchPlotLines,
  fetchStoryEvents,
  fetchTasks,
  fetchWorldbookEntries,
} from "../lib/api";
import type { AITask, Character, CharacterEventParticipation, PlotLine, StoryEvent, WorldbookEntry } from "../types";

type Mode = "characters" | "plots" | "memory";

type AssetState = {
  characters: Character[];
  plotLines: PlotLine[];
  events: StoryEvent[];
  participations: CharacterEventParticipation[];
  worldbookEntries: WorldbookEntry[];
  tasks: AITask[];
  loading: boolean;
  error: string | null;
};

function statusBadge(status: string) {
  if (status === "completed") {
    return "badge-完成";
  }
  if (status === "running") {
    return "badge-进行中";
  }
  return "badge-待执行";
}

function EmptyState({ label }: { label: string }) {
  return <p className="hero-copy">{label}</p>;
}

function ReadOnlyField({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div className="readonly-field">
      <span>{label}</span>
      <strong>{value === null || value === undefined || value === "" ? "暂无" : value}</strong>
    </div>
  );
}

export function ProjectAssetsView({ mode }: { mode: Mode }) {
  const { selectedProjectId } = useProjectContext();
  const [state, setState] = useState<AssetState>({
    characters: [],
    plotLines: [],
    events: [],
    participations: [],
    worldbookEntries: [],
    tasks: [],
    loading: false,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;

    async function load() {
      if (!selectedProjectId) {
        setState((prev) => ({ ...prev, error: "当前没有可用项目。", loading: false }));
        return;
      }
      setState((prev) => ({ ...prev, loading: true, error: null }));
      try {
        const [characters, plotLines, events, participations, worldbookEntries, tasks] = await Promise.all([
          fetchCharacters(selectedProjectId),
          fetchPlotLines(selectedProjectId),
          fetchStoryEvents(selectedProjectId),
          fetchEventParticipations(selectedProjectId),
          fetchWorldbookEntries(selectedProjectId),
          fetchTasks(selectedProjectId),
        ]);
        if (!cancelled) {
          setState({
            characters,
            plotLines,
            events,
            participations,
            worldbookEntries,
            tasks,
            loading: false,
            error: null,
          });
        }
      } catch (error) {
        if (!cancelled) {
          setState((prev) => ({
            ...prev,
            loading: false,
            error: error instanceof Error ? error.message : "Unknown error",
          }));
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [selectedProjectId]);

  const derived = useMemo(() => {
    const runningTasks = state.tasks.filter((item) => item.status === "running").length;
    const completedTasks = state.tasks.filter((item) => item.status === "completed").length;
    return { runningTasks, completedTasks };
  }, [state.tasks]);

  if (!selectedProjectId) {
    return (
      <section className="panel-grid">
        <article className="panel">
          <p className="hero-copy">当前没有项目，请先创建项目后再查看数据。</p>
        </article>
      </section>
    );
  }

  if (mode === "characters") {
    return (
      <section className="panel-grid two-col">
        <article className="panel">
          <div className="panel-header">
            <h2>角色图谱</h2>
            <span>AI Readonly Assets</span>
          </div>
          {state.loading ? <p className="hero-copy">角色数据加载中...</p> : null}
          {state.error ? <p className="hero-copy">加载失败：{state.error}</p> : null}
          {!state.loading && !state.error && state.characters.length === 0 ? <EmptyState label="暂无角色数据。" /> : null}
          <div className="graph-list">
            {state.characters.map((character) => (
              <div className="character-sheet" key={character.id}>
                <div className="task-item">
                  <div>
                    <strong>{character.name}</strong>
                    <p>{character.arc_summary ?? character.background ?? "暂无角色弧线"}</p>
                  </div>
                  <span className={`badge ${statusBadge(character.status)}`}>{character.status}</span>
                </div>
                <div className="readonly-grid">
                  <ReadOnlyField label="别名" value={character.alias} />
                  <ReadOnlyField label="角色类型" value={character.role_type} />
                  <ReadOnlyField label="身份" value={character.identity} />
                  <ReadOnlyField label="目标" value={character.goal} />
                  <ReadOnlyField label="动机" value={character.motivation} />
                  <ReadOnlyField label="秘密" value={character.secret} />
                </div>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <div className="panel-header">
            <h2>关系参与</h2>
            <span>Event Participations</span>
          </div>
          <div className="graph-meta">
            <div className="info-chip">角色 {state.characters.length}</div>
            <div className="info-chip">参与关系 {state.participations.length}</div>
          </div>
          {!state.loading && state.participations.length === 0 ? <EmptyState label="暂无角色事件参与关系。" /> : null}
          <div className="graph-list">
            {state.participations.map((item) => (
              <div className="task-item" key={item.id}>
                <div>
                  <strong>
                    角色#{item.character_id} · 事件#{item.event_id}
                  </strong>
                  <p>{item.note ?? "暂无备注"}</p>
                </div>
                <span className="badge badge-进行中">{item.role_type}</span>
              </div>
            ))}
          </div>
        </article>
      </section>
    );
  }

  if (mode === "plots") {
    return (
      <section className="panel-grid two-col">
        <article className="panel">
          <div className="panel-header">
            <h2>剧情设计</h2>
            <span>AI Readonly Plot Lines</span>
          </div>
          {state.loading ? <p className="hero-copy">剧情数据加载中...</p> : null}
          {state.error ? <p className="hero-copy">加载失败：{state.error}</p> : null}
          {!state.loading && !state.error && state.plotLines.length === 0 ? <EmptyState label="暂无剧情线数据。" /> : null}
          <div className="graph-list">
            {state.plotLines.map((plot) => (
              <div className="task-item" key={plot.id}>
                <div>
                  <strong>{plot.title}</strong>
                  <p>{plot.summary ?? plot.conflict ?? "暂无剧情摘要"}</p>
                  <div className="chip-row">
                    <span className="info-chip">{plot.plot_type}</span>
                    <span className="info-chip">priority {plot.priority}</span>
                    <span className="info-chip">{plot.status}</span>
                  </div>
                </div>
                <span className="badge badge-完成">{plot.plot_type}</span>
              </div>
            ))}
          </div>
        </article>
        <article className="panel">
          <div className="panel-header">
            <h2>故事事件</h2>
            <span>Events API</span>
          </div>
          {!state.loading && state.events.length === 0 ? <EmptyState label="暂无故事事件。" /> : null}
          <div className="graph-list">
            {state.events.map((event) => (
              <div className="task-item" key={event.id}>
                <div>
                  <strong>{event.title}</strong>
                  <p>{event.summary ?? "暂无事件摘要"}</p>
                </div>
                <span className="badge badge-待执行">Lv {event.impact_level}</span>
              </div>
            ))}
          </div>
        </article>
      </section>
    );
  }

  return (
    <section className="panel-grid two-col">
      <article className="panel">
        <div className="panel-header">
          <h2>世界书记忆</h2>
          <span>AI Readonly Worldbook</span>
        </div>
        {state.loading ? <p className="hero-copy">记忆数据加载中...</p> : null}
        {state.error ? <p className="hero-copy">加载失败：{state.error}</p> : null}
        {!state.loading && !state.error && state.worldbookEntries.length === 0 ? (
          <EmptyState label="暂无 worldbook 记忆条目。" />
        ) : null}
        <div className="graph-list">
          {state.worldbookEntries.map((entry) => (
            <div className="task-item" key={entry.id}>
              <div>
                <strong>{entry.title}</strong>
                <p>{entry.content}</p>
                <div className="chip-row">
                  <span className="info-chip">{entry.category}</span>
                  <span className="info-chip">{entry.source_type ?? "source unknown"}</span>
                  <span className="info-chip">{entry.source_ref ?? "ref none"}</span>
                </div>
              </div>
              <span className="badge badge-完成">{entry.category}</span>
            </div>
          ))}
        </div>
      </article>
      <article className="panel">
        <div className="panel-header">
          <h2>ReAct 任务状态</h2>
          <span>Task Runtime Snapshot</span>
        </div>
        <div className="graph-meta">
          <div className="info-chip">运行中 {derived.runningTasks}</div>
          <div className="info-chip">已完成 {derived.completedTasks}</div>
          <div className="info-chip">总任务 {state.tasks.length}</div>
        </div>
        {!state.loading && state.tasks.length === 0 ? <EmptyState label="暂无 AI 任务记录。" /> : null}
        <div className="graph-list">
          {state.tasks.map((task) => (
            <div className="task-item" key={task.id}>
              <div>
                <strong>{task.title}</strong>
                <p>
                  {task.module_type} / chapter {task.chapter_id ?? "none"}
                </p>
              </div>
              <span className={`badge ${statusBadge(task.status)}`}>{task.status}</span>
            </div>
          ))}
        </div>
      </article>
    </section>
  );
}
