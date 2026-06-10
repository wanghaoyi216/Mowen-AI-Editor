import { useEffect, useRef, useState } from 'react';
import {
  Send, XCircle, Clock, Loader2, Brain, Wrench, FileText,
  CheckCircle2, AlertCircle, Sparkles, ListTodo, ChevronDown, ChevronRight,
  Network, Search, Cpu, BookOpen, Activity, BookText, Lightbulb,
  Pause, Play, User,
} from 'lucide-react';
import { MessageBubble } from './MessageBubble';
import { ToolCallCard } from './ToolCallCard';
import {
  cancelAITask, fetchTaskSteps, fetchTaskLogs, sendTaskMessage, controlTaskRuntime,
} from '../../../lib/api';
import type { TaskStep, TaskLog, AgentEvent as AgentEventType, AgentToolErrorData } from '../../../types';
import './AgentChat.css';

type AgentEvent = AgentEventType;

type AgentChatWindowProps = {
  projectId: number;
  taskId: number;
  taskTitle?: string;
  taskStatus: string;
  onTaskChange?: () => void;
};

// ─── 时长格式化 ─────────────────────────────────────────────
function formatDuration(ms: number): string {
  if (!ms || ms < 0) return '0s';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  const m = Math.floor(ms / 60000);
  const s = Math.round((ms % 60000) / 1000);
  return `${m}m ${s}s`;
}

function formatTime(iso?: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

// ─── 阶段的中文标签 ─────────────────────────────────────────
const PHASE_LABELS: Record<string, { title: string; icon: any; tone: string }> = {
  research:  { title: '联网调研题材', icon: Search, tone: '#22d3ee' },
  planner:   { title: '规划小说大纲', icon: ListTodo, tone: '#3b82f6' },
  chapter_loop: { title: '逐章创作正文', icon: BookOpen, tone: '#10b981' },
  reviewer:  { title: '审稿与故事图谱', icon: Network, tone: '#8b5cf6' },
  analyze:   { title: '解析主题与大纲', icon: Lightbulb, tone: '#fbbf24' },
  world:     { title: '构建世界观', icon: BookText, tone: '#06b6d4' },
  character: { title: '梳理角色与关系', icon: Network, tone: '#8b5cf6' },
  outline:   { title: '生成章节大纲', icon: ListTodo, tone: '#3b82f6' },
  chapter:   { title: '撰写章节正文', icon: BookOpen, tone: '#10b981' },
  consistency: { title: '一致性检查', icon: CheckCircle2, tone: '#06b6d4' },
  review:    { title: '审稿与润色', icon: Sparkles, tone: '#ec4899' },
  graph:     { title: '更新图谱状态', icon: Network, tone: '#8b5cf6' },
  file:      { title: '保存与导出', icon: FileText, tone: '#94a3b8' },
};

function getPhaseMeta(phase?: string) {
  if (!phase) return { title: phase || '执行', icon: Activity, tone: '#94a3b8' };
  return PHASE_LABELS[phase] ?? { title: phase, icon: Activity, tone: '#94a3b8' };
}

// ─── 阶段顺序 + step_type → phase 映射（用于历史回填）─────
const PHASE_ORDER = ['analyze', 'world', 'character', 'outline', 'chapter', 'consistency', 'review', 'graph', 'file'] as const;

function mapStepTypeToPhase(stepType: string): string | undefined {
  if (!stepType) return undefined;
  const t = stepType.toLowerCase();
  if (t.includes('trend') || t.includes('hot') || t.includes('analyze')) return 'analyze';
  if (t.includes('world')) return 'world';
  if (t.includes('character')) return 'character';
  if (t.includes('outline') || t.includes('plan')) return 'outline';
  if (t.includes('write') || t.includes('chapter')) return 'chapter';
  if (t.includes('consistency')) return 'consistency';
  if (t.includes('review')) return 'review';
  if (t.includes('graph') || t.includes('entity')) return 'graph';
  if (t.includes('file') || t.includes('export')) return 'file';
  return undefined;
}

// 解析 TaskLog.payload（JSON 字符串）成对象，失败时回退为 null
function parseLogPayload(raw: string | null | undefined): Record<string, any> | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

// ─── 工具图标映射 ─────────────────────────────────────────
const TOOL_ICONS: Record<string, any> = {
  search: Search,
  web_search: Search,
  query_neo4j: Network,
  build_knowledge_graph: Network,
  user_directive: User,
  file: FileText,
  llm: Cpu,
  llm_generate: Cpu,
  analyze: Brain,
  consistency: CheckCircle2,
  graph: Network,
  write: BookOpen,
  system: Wrench,
};

function getToolIcon(name: string) {
  return TOOL_ICONS[name] ?? Wrench;
}

// ─── 智能折叠的 JSON 块 ─────────────────────────────────────
function JsonBlock({ data, label }: { data: any; label: string }) {
  const [open, setOpen] = useState(false);
  if (data == null) return null;
  const preview = typeof data === 'object'
    ? Object.keys(data).slice(0, 3).map((k) => `${k}: ${JSON.stringify(data[k]).slice(0, 20)}`).join(', ')
    : String(data).slice(0, 80);
  return (
    <div className="agent-chat-json">
      <button className="agent-chat-json-toggle" onClick={() => setOpen((o) => !o)}>
        {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
        <span className="agent-chat-json-label">{label}</span>
        {!open && <span className="agent-chat-json-preview">{preview}…</span>}
      </button>
      {open && (
        <pre className="agent-chat-json-content">{JSON.stringify(data, null, 2)}</pre>
      )}
    </div>
  );
}

// ─── 工具错误 Toast（B2 任务：黄色提示，不阻断任务）────────────
type ToolErrorToastProps = {
  tool?: string;
  errorCode?: string;
  remediation?: string;
  severity?: 'warning' | 'error';
  timestamp?: string;
};

function ToolErrorToast({ tool, errorCode, remediation, severity, timestamp }: ToolErrorToastProps) {
  const isError = severity === 'error';
  return (
    <div
      className={`agent-event-toast agent-event-toast-${isError ? 'error' : 'warning'}`}
      role="status"
    >
      <span className="agent-event-toast-icon">{isError ? '⛔' : '⚠️'}</span>
      <div className="agent-event-toast-body">
        <div className="agent-event-toast-title">
          工具 {tool || 'unknown'} 跳过
          {errorCode && <span className="agent-event-toast-code">（{errorCode}）</span>}
        </div>
        {remediation && (
          <div className="agent-event-toast-hint">{remediation}</div>
        )}
        {timestamp && (
          <div className="agent-event-toast-time">{formatTime(timestamp)}</div>
        )}
      </div>
    </div>
  );
}

// ─── AI 思考块（think 事件）─────────────────────────────────
function ThinkingBlock({ events }: { events: AgentEvent[] }) {
  const thoughts = events.filter((e) => e.event_type === 'think' || e.event_type === 'reasoning');
  if (thoughts.length === 0) return null;
  const [open, setOpen] = useState(false);
  const latest = thoughts[thoughts.length - 1];
  return (
    <div className="agent-chat-thinking">
      <button className="agent-chat-thinking-header" onClick={() => setOpen((o) => !o)}>
        <Brain size={13} />
        <span>AI 思考过程</span>
        <span className="agent-chat-thinking-count">{thoughts.length} 条</span>
        {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
      </button>
      {!open && latest?.data?.text && (
        <div className="agent-chat-thinking-preview">
          {String(latest.data.text).slice(0, 140)}
          {String(latest.data.text).length > 140 ? '…' : ''}
        </div>
      )}
      {open && (
        <div className="agent-chat-thinking-body">
          {thoughts.map((t, i) => (
            <div key={`t-${i}`} className="agent-chat-thinking-item">
              <span className="agent-chat-thinking-time">{formatTime(t.timestamp)}</span>
              <span className="agent-chat-thinking-text">
                {t.data?.text || t.data?.message || JSON.stringify(t.data || {}).slice(0, 200)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── 工具调用（tool_call + tool_result 配对展示）────────────
type ToolRun = {
  id: string;
  name: string;
  args?: any;
  result?: any;
  status: 'pending' | 'running' | 'success' | 'failed';
  startedAt?: string;
  finishedAt?: string;
  latencyMs?: number;
  errorMessage?: string;
};

function pairToolEvents(events: AgentEvent[]): ToolRun[] {
  const runs: ToolRun[] = [];
  const openByName: Record<string, ToolRun> = {};
  events.forEach((e, i) => {
    if (e.event_type === 'tool_call') {
      const run: ToolRun = {
        id: `${i}-${e.event_id ?? ''}`,
        name: e.data?.tool || e.data?.name || 'tool',
        args: e.data?.args ?? e.data?.input ?? e.data,
        status: 'running',
        startedAt: e.timestamp,
      };
      runs.push(run);
      openByName[`${e.data?.tool}-${i}`] = run;
    } else if (e.event_type === 'tool_result') {
      // attach to the most recent running tool
      for (let i = runs.length - 1; i >= 0; i--) {
        if (runs[i].status === 'running') {
          runs[i].result = e.data?.result ?? e.data?.output ?? e.data;
          runs[i].status = e.data?.ok === false || e.data?.error ? 'failed' : 'success';
          runs[i].finishedAt = e.timestamp;
          runs[i].latencyMs = e.data?.latency_ms;
          runs[i].errorMessage = e.data?.error;
          break;
        }
      }
    }
  });
  return runs;
}

// ─── 阶段进度（phase_start / phase_end）────────────────────
type PhaseRun = {
  phase: string;
  status: 'running' | 'completed' | 'failed';
  startedAt?: string;
  finishedAt?: string;
  data?: any;
};

function pairPhaseEvents(events: AgentEvent[]): PhaseRun[] {
  const openByPhase: Record<string, PhaseRun> = {};
  const list: PhaseRun[] = [];
  events.forEach((e) => {
    if (e.event_type === 'phase_start') {
      const run: PhaseRun = {
        phase: e.phase || e.data?.phase || 'phase',
        status: 'running',
        startedAt: e.timestamp,
        data: e.data,
      };
      openByPhase[run.phase] = run;
      list.push(run);
    } else if (e.event_type === 'phase_end') {
      const phaseKey = e.phase || e.data?.phase;
      const ref = openByPhase[phaseKey];
      if (ref) {
        ref.status = e.data?.ok === false ? 'failed' : 'completed';
        ref.finishedAt = e.timestamp;
        ref.data = { ...ref.data, ...e.data };
      } else {
        list.push({
          phase: phaseKey,
          status: e.data?.ok === false ? 'failed' : 'completed',
          finishedAt: e.timestamp,
          data: e.data,
        });
      }
    }
  });
  return list;
}

// ─── 章节步骤（step_start / step_end）─────────────────────
type ChapterStep = {
  chapterNo?: number;
  title?: string;
  status: 'running' | 'completed' | 'failed';
  startedAt?: string;
  finishedAt?: string;
  wordCount?: number;
};

function pairChapterSteps(events: AgentEvent[]): ChapterStep[] {
  const openByNo: Record<number, ChapterStep> = {};
  const list: ChapterStep[] = [];
  events.forEach((e) => {
    const no = e.data?.chapter_no ?? e.data?.chapterNo;
    if (e.event_type === 'step_start' && no != null) {
      const step: ChapterStep = {
        chapterNo: no,
        title: e.data?.title,
        status: 'running',
        startedAt: e.timestamp,
      };
      openByNo[no] = step;
      list.push(step);
    } else if (e.event_type === 'step_end' && no != null) {
      const ref = openByNo[no];
      if (ref) {
        ref.status = e.data?.ok === false ? 'failed' : 'completed';
        ref.finishedAt = e.timestamp;
        ref.wordCount = e.data?.word_count ?? ref.wordCount;
      } else {
        list.push({
          chapterNo: no,
          status: e.data?.ok === false ? 'failed' : 'completed',
          finishedAt: e.timestamp,
          wordCount: e.data?.word_count,
        });
      }
    }
  });
  return list;
}

// ─── 实时输出卡片（text_delta 流式累积）─────────────────
type StreamingCard = {
  phase: string;
  agent?: string;
  text: string;
  isToolCalling: boolean;
  activeToolName?: string;
  startedAt: string;
  finishedAt?: string;
};

function StreamingOutputCard({ card }: { card: StreamingCard }) {
  return (
    <div className="agent-chat-streaming-card">
      <div className="agent-chat-streaming-header">
        {card.isToolCalling
          ? `🔧 调用 ${card.activeToolName ?? '工具'} 中`
          : `✍️ ${card.agent ?? card.phase} 正在输出`}
      </div>
      <div className="agent-chat-streaming-body">
        {card.text}
        <span className="agent-chat-typing-cursor" />
      </div>
    </div>
  );
}

function StreamingHistoryCard({ card }: { card: StreamingCard }) {
  return (
    <div className="agent-chat-streaming-card agent-chat-streaming-card--done">
      <div className="agent-chat-streaming-header">
        {`${card.agent ?? card.phase} · 完成`}
      </div>
      <div className="agent-chat-streaming-body">{card.text}</div>
    </div>
  );
}

// ─── 主组件 ─────────────────────────────────────────────
export function AgentChatWindow({ projectId, taskId, taskTitle, taskStatus, onTaskChange }: AgentChatWindowProps) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [inputText, setInputText] = useState('');
  const [showDetails, setShowDetails] = useState(true);
  const [terminalOpen, setTerminalOpen] = useState(true);
  const [terminalFilter, setTerminalFilter] = useState<'all' | 'error' | 'tool' | 'llm'>('all');
  const [terminalSearch, setTerminalSearch] = useState('');
  const [streamingCards, setStreamingCards] = useState<StreamingCard[]>([]);
  const [currentCard, setCurrentCard] = useState<StreamingCard | null>(null);
  const [autoFollow, setAutoFollow] = useState(true);
  const [sending, setSending] = useState(false);
  const [controlBusy, setControlBusy] = useState<'pause' | 'resume' | null>(null);
  const [localStatus, setLocalStatus] = useState<string>(taskStatus);
  const [chatMessages, setChatMessages] = useState<{ role: 'user' | 'assistant'; text: string; ts: string }[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    setLocalStatus(taskStatus);
  }, [taskStatus]);

  // ─── 历史事件回填（拉取已结束任务的 steps + logs）───
  useEffect(() => {
    if (!projectId || !taskId) return;
    let cancelled = false;
    (async () => {
      try {
        const [steps, logs] = await Promise.all([
          fetchTaskSteps(projectId, taskId).catch(() => [] as TaskStep[]),
          fetchTaskLogs(projectId, taskId, 500).catch(() => [] as TaskLog[]),
        ]);
        if (cancelled) return;
        const historical: AgentEvent[] = [];
        // phase 事件从 step_type 推断
        PHASE_ORDER.forEach((phase) => {
          const stepOfPhase = steps.find((s) => mapStepTypeToPhase(s.step_type) === phase);
          if (stepOfPhase) {
            historical.push({
              event_type: stepOfPhase.status === 'running' ? 'phase_start' : 'phase_end',
              task_id: taskId,
              phase,
              // 仅在 status === 'failed' 时标记 ok:false，pending/running/completed
              // 都不算 error；这样终端日志不再误显示 [error] 行
              data: { ok: stepOfPhase.status !== 'failed', step_no: stepOfPhase.step_no, step_name: stepOfPhase.step_name, step_status: stepOfPhase.status },
              timestamp: stepOfPhase.finished_at || stepOfPhase.started_at || undefined,
            });
          }
        });
        // tool 事件从 logs 来 —— 保留原始 log_type，避免与 SSE 推的 tool_call/tool_result 错乱
        logs.forEach((log) => {
          const meta = parseLogPayload(log.payload);
          historical.push({
            event_type: log.log_type,        // 直接用原 log_type
            task_id: taskId,
            data: { name: log.log_type, message: log.message, ...(meta || {}) },
            timestamp: log.created_at,
          });
        });
        // 排序
        historical.sort((a, b) => (a.timestamp || '').localeCompare(b.timestamp || ''));
        setEvents(historical);
      } catch (err) {
        console.error('Failed to load historical events:', err);
      }
    })();
    return () => { cancelled = true; };
  }, [projectId, taskId]);

  useEffect(() => {
    if (!taskId) return;
    setStreaming(false);
    setStreamingCards([]);
    setCurrentCard(null);
    // 注意：不再清空 events，历史 effect 已经填好

    const url = `/api/v1/projects/${projectId}/tasks/${taskId}/stream`;
    let es: EventSource | null = null;
    try {
      es = new EventSource(url);
    } catch (err) {
      console.error('Failed to create EventSource:', err);
      return;
    }
    eventSourceRef.current = es;

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as AgentEvent;
        if (data.event_type === 'done') {
          setStreaming(false);
          setLocalStatus('completed');
          es?.close();
          // 主动通知父组件重新拉取 task 状态，避免章节已落盘但前端仍显示"正在思考"
          onTaskChange?.();
          return;
        }
        if (data.event_type === 'heartbeat') return;
        if (data.event_type === 'user_message') {
          const text = data.data?.text ?? '';
          if (text) setChatMessages((prev) => {
            // 去重：handleSend 已乐观插入相同气泡时跳过
            if (prev.slice(-4).some((m) => m.role === 'user' && m.text === text)) return prev;
            return [...prev, { role: 'user' as const, text, ts: data.timestamp ?? new Date().toISOString() }];
          });
          return;
        }
        if (data.event_type === 'assistant_ack') {
          const text = data.data?.text ?? '';
          if (text) setChatMessages((prev) => [...prev, { role: 'assistant', text, ts: data.timestamp ?? new Date().toISOString() }]);
          return;
        }
        if (data.event_type === 'text_delta') {
          const delta = data.data?.delta ?? '';
          const phase = data.data?.phase ?? data.phase ?? 'unknown';
          const agent = data.data?.agent;
          setCurrentCard((prev) =>
            prev && prev.phase === phase
              ? { ...prev, text: prev.text + delta, agent: agent ?? prev.agent }
              : {
                  phase,
                  agent,
                  text: delta,
                  isToolCalling: false,
                  startedAt: data.timestamp ?? new Date().toISOString(),
                },
          );
          return;
        }
        if (data.event_type === 'tool_call') {
          const toolName = data.data?.name ?? data.data?.tool;
          setCurrentCard((prev) =>
            prev
              ? { ...prev, isToolCalling: true, activeToolName: toolName }
              : prev,
          );
        }
        if (data.event_type === 'tool_end' || data.event_type === 'tool_result') {
          setCurrentCard((prev) => (prev ? { ...prev, isToolCalling: false } : prev));
        }
        if (data.event_type === 'phase_start') {
          const phase = data.phase ?? data.data?.phase ?? 'phase';
          const agent = data.data?.agent;
          setCurrentCard({
            phase,
            agent,
            text: '',
            isToolCalling: false,
            startedAt: data.timestamp ?? new Date().toISOString(),
          });
          return;
        }
        if (data.event_type === 'phase_end') {
          setCurrentCard((prev) => {
            if (prev) {
              const finished: StreamingCard = { ...prev, finishedAt: data.timestamp ?? new Date().toISOString() };
              setStreamingCards((cards) => [...cards, finished]);
            }
            return null;
          });
          // 不返回，继续记录到 events
        }
        setEvents((prev) => [...prev, data]);
      } catch (err) {
        console.error('Failed to parse event:', err);
      }
    };

    es.onerror = () => {
      setStreaming(false);
      es?.close();
    };

    es.onopen = () => {
      setStreaming(true);
    };

    return () => {
      es?.close();
    };
  }, [projectId, taskId]);

  useEffect(() => {
    if (scrollRef.current && autoFollow) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events, currentCard, streamingCards, autoFollow]);

  function handleStreamScroll() {
    const el = scrollRef.current;
    if (!el) return;
    const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setAutoFollow(distanceToBottom < 80);
  }

  const handleCancel = async () => {
    try {
      await cancelAITask(projectId, taskId);
      onTaskChange?.();
    } catch (e) {
      console.error('Cancel failed:', e);
    }
  };

  const handlePause = async () => {
    setControlBusy('pause');
    try {
      await controlTaskRuntime(projectId, taskId, 'pause');
      setLocalStatus('paused');
      onTaskChange?.();
    } catch (e) {
      console.error('Pause failed:', e);
    } finally {
      setControlBusy(null);
    }
  };

  const handleResume = async () => {
    setControlBusy('resume');
    try {
      await controlTaskRuntime(projectId, taskId, 'resume');
      setLocalStatus('running');
      onTaskChange?.();
    } catch (e) {
      console.error('Resume failed:', e);
    } finally {
      setControlBusy(null);
    }
  };

  const handleSend = async () => {
    const text = inputText.trim();
    if (!text || sending) return;
    setSending(true);
    // 乐观显示用户气泡
    setChatMessages((prev) => [...prev, { role: 'user' as const, text, ts: new Date().toISOString() }]);
    setInputText('');
    try {
      const res = await sendTaskMessage(projectId, taskId, text);
      // 任务未运行时，SSE 已无活跃订阅者，需本地回执；运行中由 SSE 推送 ack
      if (!res.accepted) {
        setChatMessages((prev) => [
          ...prev,
          {
            role: 'assistant' as const,
            text: '已记录你的留言。该任务当前未在运行，启动 / 继续创作后将采纳。',
            ts: new Date().toISOString(),
          },
        ]);
      }
    } catch (e) {
      console.error('Send message failed:', e);
      setChatMessages((prev) => [
        ...prev,
        { role: 'assistant' as const, text: '消息发送失败，请稍后重试。', ts: new Date().toISOString() },
      ]);
    } finally {
      setSending(false);
    }
  };

  const isActive = localStatus === 'running' || localStatus === 'pending' || localStatus === 'paused';

  const phases = pairPhaseEvents(events);
  const tools = pairToolEvents(events);
  const steps = pairChapterSteps(events);
  const thinking = events.filter((e) => e.event_type === 'think' || e.event_type === 'reasoning');
  // B2 任务：提取 tool_error 事件用于黄色 toast
  const toolErrorEvents = events.filter((e) => e.event_type === 'tool_error');
  const totalLatencyMs = tools.reduce((sum, t) => sum + (t.latencyMs || 0), 0);
  const successCount = tools.filter((t) => t.status === 'success').length;
  const failedCount = tools.filter((t) => t.status === 'failed').length;
  const runningCount = tools.filter((t) => t.status === 'running').length;

  // ─── 终端日志面板数据 ───
  const terminalLines = events
    .map((e) => {
      const t = e.timestamp ? formatTime(e.timestamp) : '';
      const phase = e.phase || '';
      const step = e.step || '';
      const type = e.event_type;
      const data = e.data;
      let category: 'tool' | 'llm' | 'error' | 'info' = 'info';
      let summary = '';
      if (type === 'tool_start' || type === 'tool_end' || type === 'tool_call' || type === 'tool_result') {
        category = 'tool';
        const toolName = data?.name || data?.tool || '';
        const ok = data?.ok === false ? '✗' : '✓';
        const args = data?.args ?? data?.input;
        summary = `[tool] ${toolName} ${ok} ${args ? JSON.stringify(args).slice(0, 60) : ''}`;
      } else if (type === 'tool_error') {
        // B2 任务：tool_error 单独归类为 error 类，但黄色 toast 已在主区域提示
        category = 'error';
        summary = `[tool_error] ${data?.tool || ''} ${data?.error_code || ''} — ${String(data?.remediation || '').slice(0, 80)}`;
      } else if (type === 'think' || type === 'reasoning') {
        category = 'llm';
        summary = `[think] ${String(data?.text || '').slice(0, 100)}`;
      } else if (type === 'text_delta' || type === 'llm_chunk' || type === 'llm_token' || type === 'assistant_ack') {
        // 后端 SSE 主要推 text_delta / assistant_ack；与 llm_chunk 等显式 LLM 事件同等归类
        category = 'llm';
        const text = data?.delta ?? data?.text ?? data?.token ?? '';
        summary = `[llm] ${String(text).slice(0, 80)}`;
      } else if (type === 'error' || data?.ok === false) {
        category = 'error';
        summary = `[error] ${String(data?.message || data?.error || '').slice(0, 120)}`;
      } else if (type === 'phase_start' || type === 'phase_end') {
        // phase 失败阶段也归到 error，便于"错误"Tab 能看到失败
        if (type === 'phase_end' && data?.ok === false) {
          category = 'error';
          summary = `[error] 阶段 ${data?.phase || phase} 失败: ${String(data?.message || '').slice(0, 100)}`;
        } else {
          summary = `[phase] ${phase} ${type === 'phase_end' ? '✓' : '…'}`;
        }
      } else {
        summary = `[${type}] ${JSON.stringify(data || {}).slice(0, 80)}`;
      }
      return { t, phase, step, type, category, summary, raw: e };
    })
    .filter((l) => {
      if (terminalFilter === 'all') return true;
      if (terminalFilter === 'error') return l.category === 'error';
      if (terminalFilter === 'tool') return l.category === 'tool';
      if (terminalFilter === 'llm') return l.category === 'llm';
      return true;
    })
    .filter((l) => !terminalSearch || l.summary.toLowerCase().includes(terminalSearch.toLowerCase()));

  const statusText = localStatus === 'paused'
    ? '已暂停'
    : streaming
      ? '正在思考'
      : localStatus === 'running'
        ? '执行中'
        : localStatus === 'completed'
          ? '已完成'
          : localStatus === 'failed'
            ? '已失败'
            : localStatus === 'pending'
              ? '等待中'
              : '空闲';

  return (
    <div className="agent-chat-window">
      <div className="agent-chat-header">
        <div className="agent-chat-header-left">
          <div className="agent-chat-header-title">
            <Sparkles size={14} className="agent-chat-header-sparkle" />
            <h3>{taskTitle || `任务 #${taskId}`}</h3>
          </div>
          <div className="agent-chat-header-meta">
            <span className={`agent-chat-status agent-chat-status-${localStatus}`}>
              {streaming && <Loader2 size={11} className="spin" />}
              {statusText}
            </span>
            {phases.length > 0 && (
              <span className="agent-chat-header-chip">
                <Activity size={11} /> {phases.length} 阶段
              </span>
            )}
            {tools.length > 0 && (
              <span className="agent-chat-header-chip">
                <Wrench size={11} /> {tools.length} 工具调用
              </span>
            )}
            {toolErrorEvents.length > 0 && (
              <span
                className="agent-chat-header-chip agent-chat-header-chip-warning"
                title="工具调用异常（不阻断任务）"
              >
                ⚠️ {toolErrorEvents.length} 工具异常
              </span>
            )}
            {totalLatencyMs > 0 && (
              <span className="agent-chat-header-chip">
                <Clock size={11} /> 累计 {formatDuration(totalLatencyMs)}
              </span>
            )}
          </div>
        </div>
        <div className="agent-chat-header-right">
          <button
            className="agent-chat-toggle"
            onClick={() => setShowDetails((v) => !v)}
            title={showDetails ? '收起细节' : '展开细节'}
          >
            {showDetails ? '收起细节' : '展开细节'}
          </button>
          {(localStatus === 'running' || localStatus === 'pending') && (
            <button
              className="agent-chat-ctrl agent-chat-ctrl-pause"
              onClick={handlePause}
              disabled={controlBusy !== null}
              title="暂停 AI（停止当前操作）"
            >
              {controlBusy === 'pause' ? <Loader2 size={13} className="spin" /> : <Pause size={13} />}
              <span>暂停</span>
            </button>
          )}
          {localStatus === 'paused' && (
            <button
              className="agent-chat-ctrl agent-chat-ctrl-resume"
              onClick={handleResume}
              disabled={controlBusy !== null}
              title="继续 AI 输出"
            >
              {controlBusy === 'resume' ? <Loader2 size={13} className="spin" /> : <Play size={13} />}
              <span>继续</span>
            </button>
          )}
          {isActive && (
            <button className="agent-chat-cancel" onClick={handleCancel} title="终止任务">
              <XCircle size={13} />
              <span>终止</span>
            </button>
          )}
        </div>
      </div>

      <div className="agent-chat-stream" ref={scrollRef} onScroll={handleStreamScroll}>
        {events.length === 0 && !streaming && !currentCard && streamingCards.length === 0 && (
          <div className="agent-chat-empty">
            <div className="agent-chat-empty-illustration">
              <Sparkles size={36} />
            </div>
            <div className="agent-chat-empty-title">等待 AI 启动</div>
            <div className="agent-chat-empty-hint">
              任务开始后，AI 的思考过程、工具调用、章节进度等细节将在这里以时间线形式实时展示。
            </div>
          </div>
        )}

        {/* === 作者 ⇄ AI 对话气泡 === */}
        {chatMessages.length > 0 && (
          <div className="agent-chat-bubbles">
            {chatMessages.map((m, i) => (
              <div key={`msg-${i}-${m.ts}`} className={`agent-chat-bubble agent-chat-bubble-${m.role}`}>
                <div className="agent-chat-bubble-avatar">
                  {m.role === 'user' ? <User size={13} /> : <Sparkles size={13} />}
                </div>
                <div className="agent-chat-bubble-body">{m.text}</div>
              </div>
            ))}
          </div>
        )}

        {/* === Task 6: 实时输出卡片（流式累积 text_delta）== */}
        {currentCard && <StreamingOutputCard card={currentCard} />}
        {streamingCards.length > 0 && (
          <div className="agent-chat-streaming-history">
            {streamingCards.map((card, i) => (
              <StreamingHistoryCard key={`sc-${i}-${card.startedAt}`} card={card} />
            ))}
          </div>
        )}

        {/* === B2 任务：工具错误 Toast（黄色 / 不阻断） === */}
        {toolErrorEvents.length > 0 && (
          <div className="agent-chat-toast-list">
            {toolErrorEvents.map((e, i) => {
              const data = (e.data || {}) as AgentToolErrorData;
              return (
                <ToolErrorToast
                  key={`te-${e.event_id ?? i}-${e.timestamp ?? ''}`}
                  tool={data.tool}
                  errorCode={data.error_code}
                  remediation={data.remediation}
                  severity={(data.severity as 'warning' | 'error') || 'warning'}
                  timestamp={e.timestamp}
                />
              );
            })}
          </div>
        )}

        {showDetails && phases.length > 0 && (
          <div className="agent-chat-section">
            <div className="agent-chat-section-title">
              <Activity size={12} />
              <span>执行阶段</span>
            </div>
            <div className="agent-chat-phase-list">
              {phases.map((p, i) => {
                const meta = getPhaseMeta(p.phase);
                const Icon = meta.icon;
                const latency = p.finishedAt && p.startedAt
                  ? new Date(p.finishedAt).getTime() - new Date(p.startedAt).getTime()
                  : 0;
                return (
                  <div
                    key={`ph-${i}`}
                    className={`agent-chat-phase-item agent-chat-phase-${p.status}`}
                    style={{ borderLeftColor: meta.tone }}
                  >
                    <div className="agent-chat-phase-icon" style={{ background: meta.tone }}>
                      <Icon size={12} />
                    </div>
                    <div className="agent-chat-phase-body">
                      <div className="agent-chat-phase-label">{meta.title}</div>
                      <div className="agent-chat-phase-sub">
                        <span>{p.status === 'running' ? '执行中' : p.status === 'completed' ? '已完成' : '失败'}</span>
                        {p.data?.chapters && <span> · {p.data.chapters} 章</span>}
                        {latency > 0 && <span> · {formatDuration(latency)}</span>}
                      </div>
                    </div>
                    <div className="agent-chat-phase-time">{formatTime(p.finishedAt || p.startedAt)}</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {showDetails && steps.length > 0 && (
          <div className="agent-chat-section">
            <div className="agent-chat-section-title">
              <ListTodo size={12} />
              <span>章节进度</span>
            </div>
            <div className="agent-chat-step-list">
              {steps.map((s, i) => (
                <div key={`st-${i}`} className={`agent-chat-step-row agent-chat-step-${s.status}`}>
                  <span className="agent-chat-step-no">第 {s.chapterNo} 章</span>
                  {s.title && <span className="agent-chat-step-title">{s.title}</span>}
                  <span className="agent-chat-step-meta">
                    {s.status === 'running' && <Loader2 size={11} className="spin" />}
                    {s.status === 'completed' && <CheckCircle2 size={11} />}
                    {s.status === 'failed' && <AlertCircle size={11} />}
                    {s.status === 'running' ? '撰写中' : s.status === 'completed' ? `完成${s.wordCount ? ` · ${s.wordCount} 字` : ''}` : '失败'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {showDetails && tools.length > 0 && (
          <div className="agent-chat-section">
            <div className="agent-chat-section-title">
              <Wrench size={12} />
              <span>工具调用</span>
              <span className="agent-chat-section-count">
                {successCount > 0 && <span className="agent-chat-stat-success">{successCount} 成功</span>}
                {runningCount > 0 && <span className="agent-chat-stat-running">{runningCount} 进行中</span>}
                {failedCount > 0 && <span className="agent-chat-stat-failed">{failedCount} 失败</span>}
              </span>
            </div>
            <div className="agent-chat-tool-list">
              {tools.map((tool) => {
                const Icon = getToolIcon(tool.name);
                return (
                  <ToolCallCard
                    key={tool.id}
                    toolName={tool.name}
                    args={tool.args}
                    status={tool.status}
                    duration={tool.latencyMs ?? 0}
                    result={tool.result}
                    iconOverride={Icon}
                    errorMessage={tool.errorMessage}
                  />
                );
              })}
            </div>
          </div>
        )}

        {showDetails && <ThinkingBlock events={events} />}

        {events.length > 0 && (
          <div className="agent-chat-streaming-tip">
            <span className="agent-chat-streaming-dot" />
            <span>
              {streaming
                ? 'AI 正在持续输出…'
                : taskStatus === 'completed'
                  ? `任务已完成 · 共 ${events.length} 个事件`
                  : `已接收 ${events.length} 个事件`}
            </span>
          </div>
        )}
        {!autoFollow && (
          <button
            type="button"
            className="agent-chat-follow-btn"
            onClick={() => {
              setAutoFollow(true);
              requestAnimationFrame(() => {
                if (scrollRef.current) {
                  scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
                }
              });
            }}
          >
            跳到底部
          </button>
        )}
      </div>

      <div className="agent-terminal-panel">
        <div className="agent-terminal-header">
          <button onClick={() => setTerminalOpen((o) => !o)} className="agent-terminal-toggle">
            {terminalOpen ? '▼' : '▶'} 终端日志
            <span className="agent-terminal-count">{terminalLines.length}</span>
          </button>
          {terminalOpen && (
            <>
              <div className="agent-terminal-filters">
                {(['all', 'tool', 'llm', 'error'] as const).map((f) => (
                  <button
                    key={f}
                    onClick={() => setTerminalFilter(f)}
                    className={`agent-terminal-filter ${terminalFilter === f ? 'agent-terminal-filter-active' : ''}`}
                  >
                    {f === 'all' ? '全部' : f === 'tool' ? '工具' : f === 'llm' ? 'LLM' : '错误'}
                  </button>
                ))}
              </div>
              <input
                value={terminalSearch}
                onChange={(e) => setTerminalSearch(e.target.value)}
                placeholder="搜索..."
                className="agent-terminal-search"
              />
              <button onClick={() => setEvents([])} className="agent-terminal-clear" title="清空">清空</button>
            </>
          )}
        </div>
        {terminalOpen && (
          <div className="agent-terminal-body">
            {terminalLines.length === 0 ? (
              <div className="agent-terminal-empty">暂无日志事件</div>
            ) : (
              terminalLines.map((l, i) => (
                <div key={i} className={`agent-terminal-line agent-terminal-line-${l.category}`}>
                  <span className="agent-terminal-time">{l.t}</span>
                  <span className="agent-terminal-summary">{l.summary}</span>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      <div className="agent-chat-input">
        <textarea
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              void handleSend();
            }
          }}
          placeholder={
            isActive
              ? '给 AI 发送实时指示，引导后续章节创作（Enter 发送 / Shift+Enter 换行）'
              : '给 AI 留言（任务未运行时仅记录，启动 / 继续创作后生效）'
          }
          rows={2}
        />
        <button
          onClick={() => void handleSend()}
          disabled={sending || !inputText.trim()}
          title="发送消息给 AI"
        >
          {sending ? <Loader2 size={13} className="spin" /> : <Send size={13} />}
          <span>发送</span>
        </button>
      </div>
    </div>
  );
}
