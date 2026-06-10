import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";

import { useProjectContext } from "../context/ProjectContext";
import {
  controlTaskRuntime,
  fetchTaskRuntime,
  fetchTaskSteps,
  fetchTasks,
} from "../lib/api";
import type { AITask, TaskRuntimeState } from "../types";

function calcElapsed(startedAt?: string | null): string {
  if (!startedAt) return "--:--";
  const start = new Date(startedAt).getTime();
  const diff = Date.now() - start;
  if (diff < 0) return "--:--";
  const mins = Math.floor(diff / 60000);
  const secs = Math.floor((diff % 60000) / 1000);
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

export function GlobalStatusBar() {
  const { selectedProjectId, selectedProject } = useProjectContext();
  const location = useLocation();
  const [activeTask, setActiveTask] = useState<AITask | null>(null);
  const [runtime, setRuntime] = useState<TaskRuntimeState | null>(null);
  const [steps, setSteps] = useState<number>(0);
  const [completedSteps, setCompletedSteps] = useState<number>(0);
  const [controlLoading, setControlLoading] = useState<"pause" | "resume" | "stop" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState("--:--");
  const pollingRef = useRef<number | null>(null);
  const mountedRef = useRef(true);

  const progress = steps > 0 ? Math.round((completedSteps / steps) * 100) : 0;
  const isRunning = runtime?.status === "running" || activeTask?.status === "running";
  const isPaused = runtime?.status === "paused";
  const isStopped = runtime?.status === "stopped";
  const shouldShowBar = isRunning || isPaused || !!activeTask;

  const loadRunningTask = useCallback(async () => {
    if (!selectedProjectId) return;
    try {
      const taskList = await fetchTasks(selectedProjectId);
      const runningTask = taskList.find((t) => t.status === "running" || t.status === "paused" || t.status === "interrupted");
      if (!mountedRef.current) return;
      if (!runningTask) {
        setActiveTask(null);
        setRuntime(null);
        setSteps(0);
        setCompletedSteps(0);
        return;
      }
      setActiveTask(runningTask);
      const rt = await fetchTaskRuntime(selectedProjectId, runningTask.id);
      if (!mountedRef.current) return;
      setRuntime(rt);

      try {
        const stepList = await fetchTaskSteps(selectedProjectId, runningTask.id);
        if (!mountedRef.current) return;
        setSteps(stepList.length);
        setCompletedSteps(stepList.filter((s) => s.status === "completed").length);
      } catch {
        // ignore step load errors
      }
    } catch (e) {
      if (mountedRef.current) setError(e instanceof Error ? e.message : "加载失败");
    }
  }, [selectedProjectId]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  useEffect(() => {
    void loadRunningTask();
  }, [loadRunningTask]);

  useEffect(() => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    if (activeTask) {
      pollingRef.current = window.setInterval(() => {
        void loadRunningTask();
        setElapsed(calcElapsed(activeTask.started_at));
      }, 2000);
    }
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [activeTask, loadRunningTask]);

  useEffect(() => {
    setElapsed(calcElapsed(activeTask?.started_at ?? null));
    const timer = window.setInterval(() => {
      setElapsed(calcElapsed(activeTask?.started_at ?? null));
    }, 1000);
    return () => clearInterval(timer);
  }, [activeTask?.started_at]);

  async function handleControl(action: "pause" | "resume" | "stop") {
    if (!selectedProjectId || !activeTask) return;
    setControlLoading(action);
    setError(null);
    try {
      const nextRuntime = await controlTaskRuntime(selectedProjectId, activeTask.id, action);
      setRuntime(nextRuntime);
      setActiveTask((cur) => (cur ? { ...cur, status: nextRuntime.status } : cur));
    } catch (e) {
      setError(e instanceof Error ? e.message : "控制失败");
    } finally {
      setControlLoading(null);
    }
  }

  if (!shouldShowBar) return null;
  if (location.pathname === "/workflow-monitor") return null;

  return (
    <div className="global-status-bar">
      <div className="global-status-bar-content">
        <div className="gsb-left">
          <span className="gsb-pulse" />
          <span className="gsb-project-name">{selectedProject?.name ?? "项目"}</span>
          <span className="gsb-task-name">{activeTask?.title ?? "无任务"}</span>
          <span className="gsb-step-info">{runtime?.current_step ?? activeTask?.module_type ?? "--"}</span>
        </div>
        <div className="gsb-center">
          <span className="gsb-progress-text">{progress}%</span>
          <div className="gsb-progress-track">
            <div className="gsb-progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <span className="gsb-steps">{completedSteps}/{steps}</span>
        </div>
        <div className="gsb-right">
          <span className="gsb-elapsed">{elapsed}</span>
          <button
            type="button"
            className="gsb-btn gsb-btn-pause"
            onClick={() => void handleControl("pause")}
            disabled={!isRunning || controlLoading !== null}
          >
            暂停
          </button>
          <button
            type="button"
            className="gsb-btn gsb-btn-resume"
            onClick={() => void handleControl("resume")}
            disabled={!isPaused || controlLoading !== null}
          >
            继续
          </button>
          <button
            type="button"
            className="gsb-btn gsb-btn-stop"
            onClick={() => void handleControl("stop")}
            disabled={isStopped || controlLoading !== null}
          >
            停止
          </button>
        </div>
      </div>
      {error ? <div className="gsb-error">{error}</div> : null}
    </div>
  );
}
