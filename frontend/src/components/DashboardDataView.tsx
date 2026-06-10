import { useEffect, useState } from "react";

import { useProjectContext } from "../context/ProjectContext";
import {
  fetchCharacters,
  fetchChapters,
  fetchEventParticipations,
  fetchPlotLines,
  fetchStoryEvents,
  fetchTasks,
  fetchWorldbookEntries,
} from "../lib/api";
import type {
  AITask,
  Character,
  CharacterEventParticipation,
  Chapter,
  PlotLine,
  StoryEvent,
  WorldbookEntry,
} from "../types";

export function DashboardDataView() {
  const { projects, selectedProjectId } = useProjectContext();
  const [characters, setCharacters] = useState<Character[]>([]);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [plotLines, setPlotLines] = useState<PlotLine[]>([]);
  const [events, setEvents] = useState<StoryEvent[]>([]);
  const [participations, setParticipations] = useState<CharacterEventParticipation[]>([]);
  const [worldbookEntries, setWorldbookEntries] = useState<WorldbookEntry[]>([]);
  const [tasks, setTasks] = useState<AITask[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      if (!selectedProjectId) {
        setCharacters([]);
        setChapters([]);
        setPlotLines([]);
        setEvents([]);
        setParticipations([]);
        setWorldbookEntries([]);
        setTasks([]);
        return;
      }

      setLoading(true);
      setError(null);
      try {
        const [characterItems, chapterItems, plotItems, eventItems, participationItems, worldbookItems, taskItems] =
          await Promise.all([
            fetchCharacters(selectedProjectId),
            fetchChapters(selectedProjectId),
            fetchPlotLines(selectedProjectId),
            fetchStoryEvents(selectedProjectId),
            fetchEventParticipations(selectedProjectId),
            fetchWorldbookEntries(selectedProjectId),
            fetchTasks(selectedProjectId),
          ]);
        if (!cancelled) {
          setCharacters(characterItems);
          setChapters(chapterItems);
          setPlotLines(plotItems);
          setEvents(eventItems);
          setParticipations(participationItems);
          setWorldbookEntries(worldbookItems);
          setTasks(taskItems);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unknown error");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [selectedProjectId]);

  const totalWords = chapters.reduce((sum, chapter) => sum + chapter.word_count, 0);
  const completedTasks = tasks.filter((task) => task.status === "completed").length;
  const taskCompletionRate = tasks.length > 0 ? Math.round((completedTasks / tasks.length) * 100) : 0;

  return (
    <section className="panel-grid">
      <article className="panel">
        <div className="panel-header">
          <h2>项目仪表盘</h2>
          <span>Stats</span>
        </div>
        {!selectedProjectId ? <p className="hero-copy">选择或创建项目后，这里会显示核心创作统计。</p> : null}
        <div className="dashboard-stat-grid">
          <div className="stat-card">
            <span>章节数</span>
            <strong>{chapters.length}</strong>
          </div>
          <div className="stat-card">
            <span>角色数</span>
            <strong>{characters.length}</strong>
          </div>
          <div className="stat-card">
            <span>累计字数</span>
            <strong>{totalWords}</strong>
          </div>
          <div className="stat-card">
            <span>剧情线</span>
            <strong>{plotLines.length}</strong>
          </div>
          <div className="stat-card">
            <span>世界书条目</span>
            <strong>{worldbookEntries.length}</strong>
          </div>
          <div className="stat-card">
            <span>任务完成率</span>
            <strong>{taskCompletionRate}%</strong>
          </div>
        </div>
      </article>

      <article className="panel">
        <div className="panel-header">
          <h2>项目清单</h2>
          <span>Projects</span>
        </div>
        {loading ? <p className="hero-copy">正在加载项目数据...</p> : null}
        {error ? <p className="hero-copy">加载失败：{error}</p> : null}
        {!loading && !error && projects.length === 0 ? (
          <p className="hero-copy">当前还没有项目数据。请先在上方创建项目。</p>
        ) : null}
        <div className="graph-list">
          {projects.map((project) => (
            <div className="task-item" key={project.id}>
              <div>
                <strong>{project.name}</strong>
                <p>
                  {project.genre ?? "未设定题材"} / {project.status}
                </p>
              </div>
              <span className="badge badge-完成">#{project.id}</span>
            </div>
          ))}
        </div>
      </article>

      <article className="panel parchment">
        <div className="panel-header">
          <h2>剧情与事件</h2>
          <span>Selected Project</span>
        </div>
        {!selectedProjectId ? <p className="hero-copy">选择或创建项目后，这里会显示剧情线、事件和角色参与关系。</p> : null}
        <div className="graph-list">
          {plotLines.map((item) => (
            <div className="task-item" key={`plot-${item.id}`}>
              <div>
                <strong>{item.title}</strong>
                <p>{item.conflict ?? item.summary ?? "暂无剧情摘要"}</p>
              </div>
              <span className="badge badge-进行中">{item.plot_type}</span>
            </div>
          ))}
          {events.map((item) => (
            <div className="task-item" key={`event-${item.id}`}>
              <div>
                <strong>{item.title}</strong>
                <p>{item.summary ?? "暂无事件摘要"}</p>
              </div>
              <span className="badge badge-待执行">Lv {item.impact_level}</span>
            </div>
          ))}
          {participations.map((item) => (
            <div className="task-item" key={`participation-${item.id}`}>
              <div>
                <strong>
                  角色 {item.character_id} - 事件 {item.event_id}
                </strong>
                <p>{item.note ?? "暂无参与备注"}</p>
              </div>
              <span className="badge badge-完成">{item.role_type}</span>
            </div>
          ))}
        </div>
      </article>
    </section>
  );
}
