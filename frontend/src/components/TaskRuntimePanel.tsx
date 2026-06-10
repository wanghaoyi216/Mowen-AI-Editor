import { useEffect, useMemo, useState } from "react";

import {
  controlTaskRuntime,
  executeWorkflow,
  fetchTask,
  fetchTaskRuntime,
  fetchTaskToolErrors,
  fetchTasks,
  fetchTaskStepRuntime,
  fetchTaskSteps,
  fetchWorkflows,
} from "../lib/api";
import type { AITask, TaskRuntimeState, TaskStep, TaskStepRuntimeState, WorkflowDefinition } from "../types";
import type { ToolError } from "../lib/api";

type TaskRuntimePanelProps = {
  projectId: number | null;
  initialChapterId?: number | null;
  initialTaskId?: number | null;
};

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

const workflowNodes = [
  { id: "wf-01", label: "WF-01", title: "热点发现", x: 12, y: 46 },
  { id: "wf-02", label: "WF-02", title: "世界构建", x: 32, y: 20 },
  { id: "wf-03", label: "WF-03", title: "大纲规划", x: 52, y: 46 },
  { id: "wf-04", label: "WF-04", title: "章节写作", x: 72, y: 20 },
  { id: "wf-05", label: "WF-05", title: "实体入库", x: 52, y: 76 },
];

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

function mapStatusLabel(status?: string | null) {
  if (status === "completed") {
    return "完成";
  }
  if (status === "running") {
    return "进行中";
  }
  if (status === "failed") {
    return "失败";
  }
  if (status === "interrupted") {
    return "中断";
  }
  return "待执行";
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

export function TaskRuntimePanel({
  projectId,
  initialChapterId = null,
  initialTaskId = null,
}: TaskRuntimePanelProps) {
  const [chapterId, setChapterId] = useState<number | null>(initialChapterId);
  const [taskId, setTaskId] = useState<number | null>(initialTaskId);
  const [tasks, setTasks] = useState<AITask[]>([]);
  const [task, setTask] = useState<AITask | null>(null);
  const [runtime, setRuntime] = useState<TaskRuntimeState | null>(null);
  const [steps, setSteps] = useState<TaskStep[]>([]);
  const [stepRuntime, setStepRuntime] = useState<TaskStepRuntimeState[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [toolFilter, setToolFilter] = useState("all");
  const [keyword, setKeyword] = useState("");
  const [humanInput, setHumanInput] = useState("");
  const [localControl, setLocalControl] = useState<"running" | "paused" | "stopped">("running");
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState("wf-01");
  const [workflowObjective, setWorkflowObjective] = useState("");
  const [workflowLoading, setWorkflowLoading] = useState(false);
  const [controlLoading, setControlLoading] = useState<"pause" | "resume" | "stop" | null>(null);
  // B3: 工具错误徽章 + popover
  const [toolErrorsMap, setToolErrorsMap] = useState<Record<number, ToolError[]>>({});
  const [popoverOpen, setPopoverOpen] = useState<number | null>(null);

  useEffect(() => {
    setChapterId(initialChapterId ?? null);
  }, [initialChapterId]);

  useEffect(() => {
    setTaskId(initialTaskId ?? null);
  }, [initialTaskId]);

  // B3: popover 在点击外部时自动关闭
  useEffect(() => {
    if (popoverOpen === null) {
      return;
    }
    function handleDocumentClick(event: MouseEvent) {
      const target = event.target;
      if (target instanceof Element) {
        if (target.closest(".cc-tool-error-badge") || target.closest(".cc-tool-error-popover")) {
          return;
        }
      }
      setPopoverOpen(null);
    }
    document.addEventListener("mousedown", handleDocumentClick);
    return () => {
      document.removeEventListener("mousedown", handleDocumentClick);
    };
  }, [popoverOpen]);

  useEffect(() => {
    let cancelled = false;

    async function loadWorkflows() {
      if (!projectId) {
        setWorkflows([]);
        return;
      }
      try {
        const items = await fetchWorkflows(projectId);
        if (!cancelled) {
          setWorkflows(items);
          setSelectedWorkflowId((current) =>
            items.some((item) => item.workflow_id === current) ? current : items[0]?.workflow_id ?? "wf-01",
          );
        }
      } catch (loadError) {
        if (!cancelled) {
          setWorkflows([]);
          setError(loadError instanceof Error ? loadError.message : "Unknown error");
        }
      }
    }

    void loadWorkflows();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    let cancelled = false;

    async function loadTasks() {
      if (!projectId) {
        setTasks([]);
        setTaskId(null);
        setTask(null);
        setRuntime(null);
        setSteps([]);
        setStepRuntime([]);
        return;
      }
      setError(null);
      try {
        const items = await fetchTasks(projectId, chapterId);
        if (cancelled) {
          return;
        }
        setTasks(items);
        if (items.length === 0) {
          setTaskId(null);
          setTask(null);
          setRuntime(null);
          setSteps([]);
          setStepRuntime([]);
          return;
        }

        const hasSelected = taskId ? items.some((item) => item.id === taskId) : false;
        if (!hasSelected) {
          setTaskId(items[0].id);
        }
      } catch (loadError) {
        if (!cancelled) {
          setTasks([]);
          setTask(null);
          setRuntime(null);
          setSteps([]);
          setStepRuntime([]);
          setError(loadError instanceof Error ? loadError.message : "Unknown error");
        }
      }
    }

    void loadTasks();
    return () => {
      cancelled = true;
    };
  }, [projectId, chapterId, taskId]);

  // B3: 拉取每个任务的 tool_errors 列表
  // - 拉取时机：running / completed / failed 三种状态都拉，方便任务进行中也
  //   能在条目右侧显示徽章；但徽章本身只在 completed 时显示（避免 running
  //   期间频繁闪烁重渲染）。
  // - 去重：已加载过的 taskId 不重复拉；任务列表变化时按需补齐。
  useEffect(() => {
    if (!projectId || tasks.length === 0) {
      return;
    }
    const targetTasks = tasks.filter(
      (t) => t.status === "running" || t.status === "completed" || t.status === "failed",
    );
    if (targetTasks.length === 0) {
      return;
    }

    let cancelled = false;
    Promise.all(
      targetTasks.map(async (t) => {
        try {
          const res = await fetchTaskToolErrors(t.project_id, t.id);
          if (cancelled) {
            return;
          }
          if (res.count > 0) {
            setToolErrorsMap((prev) => ({ ...prev, [t.id]: res.tool_errors }));
          } else {
            setToolErrorsMap((prev) => {
              if (!(t.id in prev)) {
                return prev;
              }
              const next = { ...prev };
              delete next[t.id];
              return next;
            });
          }
        } catch {
          // 静默：拉取失败不影响其它任务的徽章显示
        }
      }),
    );

    return () => {
      cancelled = true;
    };
  }, [projectId, tasks]);

  useEffect(() => {
    let cancelled = false;

    async function loadTaskDetail() {
      if (!taskId) {
        setTask(null);
        setRuntime(null);
        setSteps([]);
        setStepRuntime([]);
        return;
      }
      if (!projectId) {
        return;
      }

      setError(null);
      try {
        const [taskPayload, runtimePayload, stepPayload, stepRuntimePayload] = await Promise.all([
          fetchTask(projectId, taskId),
          fetchTaskRuntime(projectId, taskId),
          fetchTaskSteps(projectId, taskId),
          fetchTaskStepRuntime(projectId, taskId),
        ]);
        if (!cancelled) {
          setTask(taskPayload);
          setRuntime(runtimePayload);
          setSteps(stepPayload);
          setStepRuntime(stepRuntimePayload);
          setLocalControl(runtimePayload?.status === "running" ? "running" : "paused");
        }
      } catch (loadError) {
        if (!cancelled) {
          setTask(null);
          setRuntime(null);
          setSteps([]);
          setStepRuntime([]);
          setError(loadError instanceof Error ? loadError.message : "Unknown error");
        }
      }
    }

    void loadTaskDetail();
    return () => {
      cancelled = true;
    };
  }, [projectId, taskId]);

  const stepRuntimeByNo = useMemo(
    () => new Map(stepRuntime.map((item) => [item.step_no, item])),
    [stepRuntime],
  );
  const toolTrace = useMemo(() => safeJsonArray<ToolTraceItem>(task?.tool_trace), [task?.tool_trace]);
  const reasoningTrace = useMemo(
    () => safeJsonArray<ReasoningTraceItem>(task?.reasoning_trace),
    [task?.reasoning_trace],
  );
  const activeWorkflowId = detectWorkflowId(task);
  const selectedWorkflow = workflows.find((item) => item.workflow_id === selectedWorkflowId) ?? workflows[0] ?? null;
  const workflowNodesForView =
    workflows.length > 0
      ? workflows.map((item) => {
          const fallback = fallbackWorkflowPositions[item.workflow_id] ?? { x: 50, y: 50 };
          return {
            id: item.workflow_id,
            label: item.workflow_id.toUpperCase(),
            title: item.name.slice(0, 6),
            x: fallback.x,
            y: fallback.y,
          };
        })
      : workflowNodes;
  const completedSteps = steps.filter((step) => (stepRuntimeByNo.get(step.step_no)?.status ?? step.status) === "completed").length;
  const progress = steps.length > 0 ? Math.round((completedSteps / steps.length) * 100) : 0;
  const latestThought = [...reasoningTrace].reverse().find((item) => item.role === "ai")?.content ?? "暂无 Thought";
  const latestAction = [...toolTrace].reverse()[0];
  const latestObservation = [...reasoningTrace].reverse().find((item) => item.role === "tool")?.content ?? "暂无 Observation";
  const hasInterrupt = runtime?.status === "interrupted" || task?.status === "interrupted";

  const filteredToolTrace = toolTrace.filter((item) => {
    const matchesType = toolFilter === "all" || toolClass(item.tool_name).includes(toolFilter);
    const searchText = `${item.tool_name ?? ""} ${shortJson(item.input)} ${shortJson(item.output)}`.toLowerCase();
    const matchesKeyword = !keyword || searchText.includes(keyword.toLowerCase());
    return matchesType && matchesKeyword;
  });

  async function handleExecuteWorkflow() {
    if (!projectId || !selectedWorkflow) {
      return;
    }
    setWorkflowLoading(true);
    setError(null);
    try {
      const result = await executeWorkflow(projectId, selectedWorkflow.workflow_id, {
        objective: workflowObjective || selectedWorkflow.description,
        maxSteps: 3,
      });
      setTaskId(result.task.id);
      setTasks((items) => [result.task, ...items.filter((item) => item.id !== result.task.id)]);
      setTask(result.task);
      setSteps(result.steps);
    } catch (executeError) {
      setError(executeError instanceof Error ? executeError.message : "Unknown error");
    } finally {
      setWorkflowLoading(false);
    }
  }

  async function handleControl(action: "pause" | "resume" | "stop") {
    if (!projectId || !taskId) {
      return;
    }
    setControlLoading(action);
    setError(null);
    try {
      const nextRuntime = await controlTaskRuntime(projectId, taskId, action);
      setRuntime(nextRuntime);
      setLocalControl(nextRuntime.status === "running" ? "running" : nextRuntime.status === "stopped" ? "stopped" : "paused");
      setTask((current) => (current ? { ...current, status: nextRuntime.status } : current));
      setTasks((items) =>
        items.map((item) => (item.id === taskId ? { ...item, status: nextRuntime.status } : item)),
      );
    } catch (controlError) {
      setError(controlError instanceof Error ? controlError.message : "Unknown error");
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
        </div>
        <div className="status-actions">
          <button
            type="button"
            onClick={() => void handleControl("pause")}
            disabled={!task || controlLoading !== null || localControl === "paused"}
          >
            暂停
          </button>
          <button
            type="button"
            onClick={() => void handleControl("resume")}
            disabled={!task || controlLoading !== null || localControl === "running"}
          >
            继续
          </button>
          <button
            type="button"
            onClick={() => void handleControl("stop")}
            disabled={!task || controlLoading !== null || localControl === "stopped"}
          >
            停止
          </button>
        </div>
      </header>

      <article className="panel workflow-selector-panel">
        <div className="toolbar">
          <label className="field">
            <span>章节 ID</span>
            <input
              type="number"
              min={1}
              value={chapterId ?? ""}
              onChange={(event) => setChapterId(event.target.value ? Number(event.target.value) : null)}
            />
          </label>
          <label className="field grow">
            <span>任务选择</span>
            <select value={taskId ?? ""} onChange={(event) => setTaskId(Number(event.target.value) || null)}>
              <option value="">请选择任务</option>
              {tasks.map((item) => (
                <option key={item.id} value={item.id}>
                  #{item.id} / {item.task_type} / {item.title}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Workflow</span>
            <select value={selectedWorkflowId} onChange={(event) => setSelectedWorkflowId(event.target.value)}>
              {workflows.map((item) => (
                <option key={item.workflow_id} value={item.workflow_id}>
                  {item.workflow_id.toUpperCase()} / {item.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field grow">
            <span>执行目标</span>
            <input
              value={workflowObjective}
              onChange={(event) => setWorkflowObjective(event.target.value)}
              placeholder={selectedWorkflow?.description ?? "Workflow objective"}
            />
          </label>
          <button type="button" onClick={handleExecuteWorkflow} disabled={!projectId || !selectedWorkflow || workflowLoading}>
            {workflowLoading ? "执行中" : "执行 Workflow"}
          </button>
        </div>
        {selectedWorkflow ? (
          <div className="workflow-definition-strip">
            <span>{selectedWorkflow.trigger}</span>
            <strong>{selectedWorkflow.output}</strong>
          </div>
        ) : null}
        {error ? <p className="alert-text">加载失败：{error}</p> : null}
        {!projectId ? <p className="hero-copy">请先在仪表盘选择项目。</p> : null}
      </article>

      {/* B3: 任务条目列表 + 工具异常徽章 */}
      {tasks.length > 0 ? (
        <article className="panel workflow-task-list-panel">
          <div className="panel-header">
            <h2>任务条目</h2>
            <span>
              {tasks.length} 个 · {Object.values(toolErrorsMap).reduce((sum, items) => sum + items.length, 0)} 异常
            </span>
          </div>
          <ul className="workflow-task-list">
            {tasks.map((item) => {
              const isSelected = item.id === taskId;
              const errors = toolErrorsMap[item.id];
              const hasErrors = Boolean(errors && errors.length > 0);
              const isPopoverOpen = popoverOpen === item.id;
              return (
                <li
                  key={item.id}
                  className={`workflow-task-list-item status-${item.status ?? "unknown"}${isSelected ? " selected" : ""}`}
                >
                  <button
                    type="button"
                    className="workflow-task-list-row"
                    onClick={() => setTaskId(item.id)}
                    title={`#${item.id} / ${item.task_type} / ${item.title}`}
                  >
                    <span className="workflow-task-list-id">#{item.id}</span>
                    <span className="workflow-task-list-type">{item.task_type}</span>
                    <span className="workflow-task-list-title">{item.title}</span>
                    <span className={`workflow-task-list-status status-${item.status ?? "unknown"}`}>
                      {mapStatusLabel(item.status)}
                    </span>
                  </button>
                  {hasErrors && item.status === "completed" ? (
                    <span
                      className="cc-tool-error-badge"
                      onClick={(event) => {
                        event.stopPropagation();
                        setPopoverOpen(isPopoverOpen ? null : item.id);
                      }}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          event.stopPropagation();
                          setPopoverOpen(isPopoverOpen ? null : item.id);
                        }
                      }}
                    >
                      ⚠️ {errors.length} 工具异常
                      {isPopoverOpen ? (
                        <div className="cc-tool-error-popover" onClick={(event) => event.stopPropagation()}>
                          <div className="cc-tool-error-popover-header">任务 #{item.id} 工具异常详情</div>
                          {errors.length === 0 ? (
                            <p className="cc-tool-error-popover-empty">暂无异常</p>
                          ) : (
                            <table>
                              <thead>
                                <tr>
                                  <th>工具</th>
                                  <th>错误码</th>
                                  <th>建议</th>
                                </tr>
                              </thead>
                              <tbody>
                                {errors.map((err, idx) => (
                                  <tr key={`${err.tool}-${err.error_code}-${idx}`}>
                                    <td>{err.tool || "—"}</td>
                                    <td>
                                      <code>{err.error_code || "—"}</code>
                                    </td>
                                    <td>{err.remediation || "—"}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          )}
                          <div className="cc-tool-error-popover-footer">
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                setPopoverOpen(null);
                              }}
                            >
                              关闭
                            </button>
                          </div>
                        </div>
                      ) : null}
                    </span>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </article>
      ) : null}

      <div className="workflow-grid">
        <article className="panel workflow-graph-card">
          <div className="panel-header">
            <h2>Workflow 依赖图</h2>
            <span>{mapStatusLabel(runtime?.status ?? task?.status)}</span>
          </div>
          <div className="workflow-map" aria-label="workflow dependency graph">
            <svg viewBox="0 0 100 100" role="img">
              {(workflows.length > 0 ? workflows : []).flatMap((workflow) =>
                workflow.dependencies.map((dependency) => {
                  const source = fallbackWorkflowPositions[dependency];
                  const target = fallbackWorkflowPositions[workflow.workflow_id];
                  if (!source || !target) {
                    return null;
                  }
                  return (
                    <line
                      key={`${dependency}-${workflow.workflow_id}`}
                      x1={source.x}
                      y1={source.y}
                      x2={target.x}
                      y2={target.y}
                    />
                  );
                }),
              )}
              <line x1="52" y1="46" x2="52" y2="76" className="crossline" />
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
              {selectedWorkflow.steps.map((step) => (
                <div className="step-node step-pending" key={step.step_no}>
                  <span>{step.step_no}</span>
                  <strong>{step.name}</strong>
                  <p>{step.expected_output}</p>
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
                  <span>{status === "completed" ? "✓" : status === "failed" ? "×" : status === "running" ? "" : step.step_no}</span>
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
              <select value={toolFilter} onChange={(event) => setToolFilter(event.target.value)}>
                <option value="all">全部</option>
                <option value="search">搜索</option>
                <option value="llm">LLM</option>
                <option value="graph">图数据库</option>
                <option value="file">文件</option>
              </select>
            </label>
            <label className="field grow">
              <span>关键词</span>
              <input value={keyword} onChange={(event) => setKeyword(event.target.value)} />
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

        <article className="panel workflow-detail-card">
          <div className="panel-header">
            <h2>业务详情</h2>
            <span>{localControl}</span>
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

        <article className={`panel human-interrupt-card${hasInterrupt ? " interrupt-open" : ""}`}>
          <div className="panel-header">
            <h2>人类介入</h2>
            <span>{hasInterrupt ? "Interrupt" : "Standby"}</span>
          </div>
          {hasInterrupt ? <p className="interrupt-question">{runtime?.message ?? task?.error_message ?? "AI 请求方向性建议"}</p> : null}
          <div className="interrupt-input-row">
            <input
              value={humanInput}
              onChange={(event) => setHumanInput(event.target.value)}
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
