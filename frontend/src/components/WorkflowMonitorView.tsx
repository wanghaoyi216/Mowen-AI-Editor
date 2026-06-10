import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useProjectContext } from "../context/ProjectContext";
import {
  controlTaskRuntime,
  fetchTaskRuntime,
  fetchTasks,
  fetchTaskSteps,
  fetchWorkflows,
} from "../lib/api";
import type { AITask, TaskRuntimeState, TaskStep, TaskStepRuntimeState, WorkflowDefinition } from "../types";

type ToolTraceItem = {
  tool_name?: string;
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
  status?: string;
  duration_ms?: number;
  timestamp?: string;
};

type ReasoningTraceItem = {
  role?: string;
  content?: string;
};

const fallbackWorkflowPositions: Record<string, { x: number; y: number }> = {
  "wf-01": { x: 12, y: 46 },
  "wf-02": { x: 32, y: 20 },
  "wf-03": { x: 52, y: 46 },
  "wf-04": { x: 72, y: 20 },
  "wf-05": { x: 52, y: 76 },
};

function safeJsonArray<T>(raw?: string | null): T[] {
  if (!raw) {
    return [];
  }
  try {
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? (parsed as T[]) : [];
  } catch {
    return [];
  }
}

function detectWorkflowId(task: AITask | null) {
  const text = `${task?.task_type ?? ""} ${task?.module_type ?? ""} ${task?.title ?? ""}`.toLowerCase();
  const directWorkflowId = text.match(/wf-0[1-5]/)?.[0];
  if (directWorkflowId) {
    return directWorkflowId;
  }
  if (text.includes("trend")) {
    return "wf-01";
  }
  if (text.includes("asset") || text.includes("world") || text.includes("character")) {
    return "wf-02";
  }
  if (text.includes("outline") || text.includes("design")) {
    return "wf-03";
  }
  if (text.includes("chapter") || text.includes("revision") || text.includes("draft")) {
    return "wf-04";
  }
  if (text.includes("extract") || text.includes("graph")) {
    return "wf-05";
  }
  return "wf-01";
}

function toolClass(toolName?: string) {
  if (!toolName) {
    return "tool-other";
  }
  if (toolName.includes("search") || toolName.includes("scrape")) {
    return "tool-search";
  }
  if (toolName.includes("llm")) {
    return "tool-llm";
  }
  if (toolName.includes("graph") || toolName.includes("entity") || toolName.includes("relationship")) {
    return "tool-graph";
  }
  if (toolName.includes("export")) {
    return "tool-file";
  }
  return "tool-other";
}

function shortJson(value: unknown) {
  if (value == null) {
    return "none";
  }
  const text = typeof value === "string" ? value : JSON.stringify(value);
  return text.length > 180 ? `${text.slice(0, 180)}...` : text;
}

function mapStatusLabel(status?: string | null) {
  if (status === "completed") return "完成";
  if (status === "running") return "进行中";
  if (status === "failed") return "失败";
  if (status === "interrupted") return "中断";
  return "待执行";
}

function calcElapsed(startedAt?: string | null): string {
  if (!startedAt) return "--:--";
  const start = new Date(startedAt).getTime();
  const diff = Date.now() - start;
  if (diff < 0) return "--:--";
  const mins = Math.floor(diff / 60000);
  const secs = Math.floor((diff % 60000) / 1000);
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

export function WorkflowMonitorView() {
  const { selectedProjectId } = useProjectContext();
  const projectId = selectedProjectId;
  const [taskId, setTaskId] = useState<number | null>(null);
  const [tasks, setTasks] = useState<AITask[]>([]);
  const [task, setTask] = useState<AITask | null>(null);
  const [runtime, setRuntime] = useState<TaskRuntimeState | null>(null);
  const [steps, setSteps] = useState<TaskStep[]>([]);
  const [stepRuntime, setStepRuntime] = useState<TaskStepRuntimeState[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState("wf-01");
  const [toolFilter, setToolFilter] = useState("all");
  const [keyword, setKeyword] = useState("");
  const [humanInput, setHumanInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [controlLoading, setControlLoading] = useState<"pause" | "resume" | "stop" | null>(null);
  const [, setElapsedTimer] = useState(0);
  const pollingRef = useRef<number | null>(null);
  const mountedRef = useRef(true);

  const activeWorkflowId = useMemo(() => detectWorkflowId(task), [task]);
  const selectedWorkflow = workflows.find((w) => w.workflow_id === selectedWorkflowId) ?? workflows[0] ?? null;
  const stepRuntimeByNo = useMemo(() => new Map(stepRuntime.map((s) => [s.step_no, s])), [stepRuntime]);
  const toolTrace = useMemo(() => safeJsonArray<ToolTraceItem>(task?.tool_trace), [task?.tool_trace]);
  const reasoningTrace = useMemo(() => safeJsonArray<ReasoningTraceItem>(task?.reasoning_trace), [task?.reasoning_trace]);

  const completedSteps = useMemo(
    () => steps.filter((s) => (stepRuntimeByNo.get(s.step_no)?.status ?? s.status) === "completed").length,
    [steps, stepRuntimeByNo],
  );
  const progress = useMemo(
    () => (steps.length > 0 ? Math.round((completedSteps / steps.length) * 100) : 0),
    [completedSteps, steps.length],
  );
  const hasInterrupt = runtime?.status === "interrupted" || task?.status === "interrupted";
  const latestThought = useMemo(
    () => [...reasoningTrace].reverse().find((i) => i.role === "ai")?.content ?? "暂无 Thought",
    [reasoningTrace],
  );
  const latestAction = useMemo(() => [...toolTrace].reverse()[0] ?? null, [toolTrace]);
  const latestObservation = useMemo(
    () => [...reasoningTrace].reverse().find((i) => i.role === "tool")?.content ?? "暂无 Observation",
    [reasoningTrace],
  );
  const workflowNodesForView = useMemo(
    () =>
      workflows.length > 0
        ? workflows.map((w) => {
            const fb = fallbackWorkflowPositions[w.workflow_id] ?? { x: 50, y: 50 };
            return { id: w.workflow_id, label: w.workflow_id.toUpperCase(), title: w.name.slice(0, 6), x: fb.x, y: fb.y };
          })
        : [],
    [workflows],
  );

  const filteredToolTrace = useMemo(() => {
    return toolTrace.filter((item) => {
      const matchesType = toolFilter === "all" || toolClass(item.tool_name).includes(toolFilter);
      const searchText = `${item.tool_name ?? ""} ${shortJson(item.input)} ${shortJson(item.output)}`.toLowerCase();
      const matchesKeyword = !keyword || searchText.includes(keyword.toLowerCase());
      return matchesType && matchesKeyword;
    });
  }, [toolFilter, keyword, toolTrace]);

  const loadWorkflows = useCallback(async () => {
    if (!projectId) return;
    try {
      const items = await fetchWorkflows(projectId);
      if (mountedRef.current) {
        setWorkflows(items);
        setSelectedWorkflowId((cur) =>
          items.some((i) => i.workflow_id === cur) ? cur : items[0]?.workflow_id ?? "wf-01",
        );
      }
    } catch (e) {
      if (mountedRef.current) setError(e instanceof Error ? e.message : "加载 workflow 失败");
    }
  }, [projectId]);

  const loadTasks = useCallback(async () => {
    if (!projectId) return;
    try {
      const items = await fetchTasks(projectId);
      if (mountedRef.current) {
        setTasks(items);
        if (!taskId && items.length > 0) setTaskId(items[0].id);
      }
    } catch (e) {
      if (mountedRef.current) setError(e instanceof Error ? e.message : "加载任务列表失败");
    }
  }, [projectId, taskId]);

  const loadTaskDetail = useCallback(async () => {
    if (!projectId || !taskId) return;
    try {
      const [rtPayload, stepPayload] = await Promise.all([
        fetchTaskRuntime(projectId, taskId),
        fetchTaskSteps(projectId, taskId),
      ]);
      if (mountedRef.current) {
        setRuntime(rtPayload);
        setSteps(stepPayload);
      }
      const currentTask = tasks.find((t) => t.id === taskId) ?? null;
      if (currentTask) setTask(currentTask);
    } catch (e) {
      if (mountedRef.current) setError(e instanceof Error ? e.message : "加载任务详情失败");
    }
  }, [projectId, taskId, tasks]);

  const startPolling = useCallback(() => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    pollingRef.current = window.setInterval(() => {
      if (projectId && taskId) {
        void loadTaskDetail();
        setElapsedTimer((v) => v + 1);
      }
    }, 2000);
  }, [projectId, taskId, loadTaskDetail]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  useEffect(() => {
    void loadWorkflows();
  }, [loadWorkflows]);

  useEffect(() => {
    void loadTasks();
  }, [loadTasks]);

  useEffect(() => {
    void loadTaskDetail();
  }, [loadTaskDetail]);

  useEffect(() => {
    if (taskId) {
      startPolling();
    } else if (pollingRef.current) {
      clearInterval(pollingRef.current);
    }
  }, [taskId, startPolling]);

  async function handleControl(action: "pause" | "resume" | "stop") {
    if (!projectId || !taskId) return;
    setControlLoading(action);
    setError(null);
    try {
      const nextRuntime = await controlTaskRuntime(projectId, taskId, action);
      setRuntime(nextRuntime);
      setTask((cur) => (cur ? { ...cur, status: nextRuntime.status } : cur));
    } catch (e) {
      setError(e instanceof Error ? e.message : "控制失败");
    } finally {
      setControlLoading(null);
    }
  }

  return (
    <section className="workflow-monitor">
      <header className="workflow-status-bar">
        <div>
          <span className="status-pulse" />
          <strong>{task ? task.title : "无运行任务"}</strong>
          <small>{runtime?.current_step ?? task?.module_type ?? "workflow-monitor"}</small>
        </div>
        <div className="status-progress">
          <span>{progress}%</span>
          <div>
            <i style={{ width: `${progress}%` }} />
          </div>
          <span className="elapsed-time">{calcElapsed(task?.started_at)}</span>
        </div>
        <div className="status-actions">
          <button
            type="button"
            onClick={() => void handleControl("pause")}
            disabled={!task || controlLoading !== null || runtime?.status === "paused"}
          >
            暂停
          </button>
          <button
            type="button"
            onClick={() => void handleControl("resume")}
            disabled={!task || controlLoading !== null || runtime?.status === "running"}
          >
            继续
          </button>
          <button
            type="button"
            onClick={() => void handleControl("stop")}
            disabled={!task || controlLoading !== null || runtime?.status === "stopped"}
          >
            停止
          </button>
        </div>
      </header>

      <article className="panel workflow-selector-panel">
        <div className="toolbar">
          <label className="field grow">
            <span>任务选择</span>
            <select value={taskId ?? ""} onChange={(e) => setTaskId(e.target.value ? Number(e.target.value) : null)}>
              <option value="">请选择任务</option>
              {tasks.map((t) => (
                <option key={t.id} value={t.id}>
                  #{t.id} / {t.task_type} / {t.title}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Workflow</span>
            <select value={selectedWorkflowId} onChange={(e) => setSelectedWorkflowId(e.target.value)}>
              {workflows.map((w) => (
                <option key={w.workflow_id} value={w.workflow_id}>
                  {w.workflow_id.toUpperCase()} / {w.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        {selectedWorkflow ? (
          <div className="workflow-definition-strip">
            <span>{selectedWorkflow.trigger}</span>
            <strong>{selectedWorkflow.output}</strong>
          </div>
        ) : null}
        {error ? <p className="alert-text">加载失败：{error}</p> : null}
      </article>

      <div className="workflow-grid">
        <article className="panel workflow-graph-card">
          <div className="panel-header">
            <h2>Workflow 依赖图</h2>
            <span>{mapStatusLabel(runtime?.status ?? task?.status)}</span>
          </div>
          <div className="workflow-map" aria-label="workflow dependency graph">
            <svg viewBox="0 0 100 100" role="img">
              {workflows.flatMap((wf) =>
                wf.dependencies.map((dep) => {
                  const src = fallbackWorkflowPositions[dep];
                  const tgt = fallbackWorkflowPositions[wf.workflow_id];
                  if (!src || !tgt) return null;
                  return (
                    <line key={`${dep}-${wf.workflow_id}`} x1={src.x} y1={src.y} x2={tgt.x} y2={tgt.y} />
                  );
                }),
              )}
              {workflowNodesForView.map((node) => {
                const isActive = node.id === activeWorkflowId;
                const isDone = progress === 100 && isActive;
                return (
                  <g key={node.id} className={isActive ? "active" : isDone ? "done" : "pending"}>
                    <circle cx={node.x} cy={node.y} r="8" />
                    <text x={node.x} y={node.y + 1.5} textAnchor="middle">
                      {isDone ? "✓" : node.label.replace("WF-", "")}
                    </text>
                    <text x={node.x} y={node.y + 14} textAnchor="middle" className="workflow-map-title">
                      {node.title}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
        </article>

        <article className="panel workflow-stepper-card">
          <div className="panel-header">
            <h2>步骤进度</h2>
            <span>{completedSteps}/{steps.length}</span>
          </div>
          {steps.length === 0 && selectedWorkflow ? (
            <div className="workflow-definition-steps">
              {selectedWorkflow.steps.map((s) => (
                <div className="step-node step-pending" key={s.step_no}>
                  <span>{s.step_no}</span>
                  <strong>{s.name}</strong>
                  <p>{s.expected_output}</p>
                </div>
              ))}
            </div>
          ) : null}
          <div className="workflow-stepper">
            {steps.map((step) => {
              const state = stepRuntimeByNo.get(step.step_no);
              const status = state?.status ?? step.status;
              return (
                <div className={`step-node step-${status}`} key={step.id} title={state?.message ?? step.error_message ?? ""}>
                  <span>
                    {status === "completed" ? "✓" : status === "failed" ? "×" : status === "running" ? "⟳" : step.step_no}
                  </span>
                  <strong>{step.step_name}</strong>
                </div>
              );
            })}
            {steps.length === 0 ? <p className="empty-state">当前任务暂无步骤信息。</p> : null}
          </div>
        </article>

        <article className="panel workflow-log-card">
          <div className="panel-header">
            <h2>工具调用日志</h2>
            <span>{filteredToolTrace.length} 条</span>
          </div>
          <div className="toolbar compact-toolbar">
            <label className="field">
              <span>工具类型</span>
              <select value={toolFilter} onChange={(e) => setToolFilter(e.target.value)}>
                <option value="all">全部</option>
                <option value="search">搜索</option>
                <option value="llm">LLM</option>
                <option value="graph">图数据库</option>
                <option value="file">文件</option>
              </select>
            </label>
            <label className="field grow">
              <span>关键词</span>
              <input value={keyword} onChange={(e) => setKeyword(e.target.value)} />
            </label>
          </div>
          <div className="terminal-log">
            {filteredToolTrace.map((item, index) => (
              <details key={`${item.tool_name}-${item.timestamp}-${index}`} open={index === filteredToolTrace.length - 1}>
                <summary>
                  <span>{item.timestamp ? new Date(item.timestamp).toLocaleTimeString() : "--:--:--"}</span>
                  <b className={toolClass(item.tool_name)}>{item.tool_name ?? "unknown_tool"}</b>
                  <em className={`log-${item.status ?? "pending"}`}>{item.status ?? "pending"}</em>
                  <small>{item.duration_ms ?? 0}ms</small>
                </summary>
                <pre>{shortJson({ input: item.input, output: item.output })}</pre>
              </details>
            ))}
            {filteredToolTrace.length === 0 ? <p>暂无工具调用记录</p> : null}
          </div>
        </article>

        <article className="panel workflow-timeline-card">
          <div className="panel-header">
            <h2>AI 决策历史</h2>
            <span>{reasoningTrace.length} 条</span>
          </div>
          <div className="decision-timeline">
            {[...reasoningTrace].reverse().map((item, index) => (
              <details key={`${item.role}-${index}`} open={index < 3}>
                <summary>
                  <b>{item.role ?? "ai"}</b>
                  <span>#{reasoningTrace.length - index}</span>
                </summary>
                <p>{item.content ?? "no content"}</p>
              </details>
            ))}
            {reasoningTrace.length === 0 ? <p className="empty-state">暂无 AI 决策记录。</p> : null}
          </div>
        </article>

        <article className="panel workflow-detail-card">
          <div className="panel-header">
            <h2>业务详情</h2>
            <span>{runtime?.status ?? "idle"}</span>
          </div>
          <div className="detail-card">
            <strong>{task?.title ?? "暂无任务"}</strong>
            <p>{task?.plan_text ?? runtime?.message ?? "等待 AI 工作流启动"}</p>
          </div>
          <div className="react-triplet">
            <div className="thought-box">
              <span>Thought</span>
              <p>{latestThought}</p>
            </div>
            <div className="action-box">
              <span>Action</span>
              <p>{latestAction ? `${latestAction.tool_name}: ${shortJson(latestAction.input)}` : "暂无 Action"}</p>
            </div>
            <div className="observation-box">
              <span>Observation</span>
              <p>{latestObservation}</p>
            </div>
          </div>
        </article>

        <article className={`panel human-interrupt-card${hasInterrupt ? " interrupt-open" : ""}`}>
          <div className="panel-header">
            <h2>人类介入</h2>
            <span>{hasInterrupt ? "Interrupt" : "Standby"}</span>
          </div>
          {hasInterrupt ? (
            <p className="interrupt-question">{runtime?.message ?? task?.error_message ?? "AI 请求方向性建议"}</p>
          ) : null}
          <div className="interrupt-input-row">
            <input
              value={humanInput}
              onChange={(e) => setHumanInput(e.target.value)}
              placeholder="方向性建议"
              disabled={!hasInterrupt}
            />
            <button type="button" disabled={!hasInterrupt || !humanInput.trim()} onClick={() => setHumanInput("")}>
              提交建议
            </button>
          </div>
        </article>
      </div>
    </section>
  );
}
