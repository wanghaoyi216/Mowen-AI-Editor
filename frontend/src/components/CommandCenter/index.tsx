import { useState, useEffect, useRef, useCallback } from 'react';
import { useProjectContext } from '../../context/ProjectContext';
import { useResizableLayout } from '../../hooks/useResizableLayout';
import { ResizableSplitter } from './ResizableSplitter';
import { TopControlBar } from './TopControlBar';
import { MainVisualizationPanel } from './MainVisualizationPanel';
import { ModalCreateProject } from './ModalCreateProject';
import { ModalStartCreation } from './ModalStartCreation';
import { ChatSidebar } from './AgentChat/ChatSidebar';
import { AgentChatWindow } from './AgentChat/AgentChatWindow';
import {
  createProject as apiCreateProject,
  createAITask,
  fetchAITasks,
  fetchTaskSteps,
  fetchTaskLogs,
  listProjectFiles,
  fetchChapters,
  fetchTask,
  controlTaskRuntime,
  resumeAITask,
  cancelAITask,
} from '../../lib/api';
import type { TaskStep, TaskLog, Chapter, AITask } from '../../types';
import './CommandCenter.css';
import './AgentChat/AgentChat.css';

/**
 * 任务 V19: 重写 CommandCenter 为 Trae 风格三栏布局
 * 240px / 60% / 40% - 左侧 ChatSidebar / 中间 AgentChatWindow / 右侧 MainVisualizationPanel
 *
 * 保留 v1 实现的所有状态管理逻辑：
 * - doPoll：3s 轮询拉取任务进度
 * - hydrateRecentTask：项目切换时恢复最近任务
 * - 任务运行时长计时器
 * - 错误状态恢复
 */

type Stage = {
  key: string;
  name: string;
  status: string;
  duration: string;
  progress: number;
  detail?: string;
};

type LogEntry = {
  id: number;
  timestamp: string;
  tool: string;
  status: string;
  summary: string;
  stepName: string;
  duration: string;
  isNew: boolean;
  startedAt?: string | null;
};

type AIGeneratedFile = {
  id: string;
  path: string;
  name: string;
  type: string;
  size: string;
  createdAt: string;
  content?: string;
};

type NovelStats = {
  title: string;
  totalWords: number;
  totalChapters: number;
  completedChapters: number;
};

type ChapterItem = {
  id: number;
  chapterNo: number;
  title: string;
  status: string;
  wordCount: number;
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTimestamp(isoString: string): string {
  const d = new Date(isoString);
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function formatDuration(startIso?: string | null, endIso?: string | null): string {
  if (!startIso) return '';
  const start = new Date(startIso).getTime();
  const end = endIso ? new Date(endIso).getTime() : Date.now();
  const diffSec = Math.max(0, Math.round((end - start) / 1000));
  if (diffSec < 60) return `${diffSec}s`;
  const min = Math.floor(diffSec / 60);
  const sec = diffSec % 60;
  return `${min}m${sec}s`;
}

function mapToolName(step: TaskStep): string {
  if (step.tool_name) return step.tool_name;
  const reactState = step.react_state?.toLowerCase() || '';
  if (reactState.includes('search')) return 'search';
  if (reactState.includes('graph')) return 'graph';
  if (reactState.includes('file')) return 'file';
  if (reactState.includes('llm') || reactState.includes('model')) return 'llm';
  switch (step.step_type) {
    case 'trend':
    case 'hot_scan':
    case 'keyword':
      return 'search';
    case 'graph_build':
    case 'entity_map':
      return 'graph';
    case 'write':
    case 'export':
    case 'file_gen':
      return 'file';
    case 'plan':
    case 'analyze':
    case 'build':
      return 'llm';
    default:
      return 'system';
  }
}

function mapStepToLogEntry(step: TaskStep, index: number, prevIds: Set<number>): LogEntry {
  const id = step.id ?? index + 1;
  return {
    id,
    timestamp: step.started_at ? formatTimestamp(step.started_at) : new Date().toLocaleTimeString('zh-CN'),
    tool: mapToolName(step),
    status: step.status ?? 'pending',
    summary: step.step_name || (step.output_payload ? step.output_payload.substring(0, 80) : ''),
    stepName: step.step_name || '',
    duration: formatDuration(step.started_at, step.finished_at),
    isNew: !prevIds.has(id),
    startedAt: step.started_at,
  };
}

function getStepProgress(status: string, startedAt?: string | null): number {
  if (status === 'completed') return 100;
  if (status === 'failed') return 0;
  if (status === 'running' && startedAt) {
    const elapsed = (Date.now() - new Date(startedAt).getTime()) / 1000;
    if (elapsed < 30) return 20 + Math.round(elapsed / 30 * 30);
    if (elapsed < 120) return 50 + Math.round((elapsed - 30) / 90 * 30);
    return Math.min(95, 80 + Math.round((elapsed - 120) / 300 * 15));
  }
  return 0;
}

function mapStepsToStages(steps: TaskStep[]): Stage[] {
  return [...steps]
    .sort((a, b) => (a.step_no ?? 0) - (b.step_no ?? 0))
    .map((step, index) => ({
      key: `${step.task_id}-${step.step_no}-${step.id ?? index}`,
      name: step.step_name || `Step ${step.step_no || index + 1}`,
      status: step.status || 'pending',
      duration: formatDuration(step.started_at, step.finished_at),
      progress: getStepProgress(step.status || 'pending', step.started_at),
      detail: step.output_payload || step.error_message || step.input_payload || undefined,
    }));
}

function mapTaskLogToLogEntry(log: TaskLog, index: number, prevIds: Set<number>): LogEntry {
  const id = log.id ?? index + 1;
  return {
    id,
    timestamp: log.created_at ? formatTimestamp(log.created_at) : new Date().toLocaleTimeString('zh-CN'),
    tool: mapLogTypeToTool(log.log_type),
    status: 'success',
    summary: log.message,
    stepName: log.step_no ? `步骤${log.step_no}` : '',
    duration: '-',
    isNew: !prevIds.has(id),
  };
}

function mapLogTypeToTool(logType: string): string {
  switch (logType) {
    case 'think': return 'llm';
    case 'act': return 'system';
    case 'observe': return 'file';
    case 'tool_call': return 'search';
    case 'subagent': return 'graph';
    default: return 'system';
  }
}

function mapFileInfoToAIGeneratedFile(file: { path: string; name: string; size: number; modified_at: string; file_type: string }, index: number): AIGeneratedFile {
  return {
    id: `${file.path}-${index}`,
    path: file.path,
    name: file.name,
    type: file.file_type,
    size: formatFileSize(file.size),
    createdAt: formatTimestamp(file.modified_at),
  };
}

// Task 3: 基于 started_at 计算已运行时长（秒）
function computeElapsed(startedAt: string | null | undefined): number {
  if (!startedAt) return 0;
  return Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000);
}

export function CommandCenter() {
  const { projects, selectedProjectId, selectedProject, setSelectedProjectId, reload: reloadProjects } = useProjectContext();

  // === v1 状态保留 ===
  const [taskStatus, setTaskStatus] = useState('idle');
  const [currentStage, setCurrentStage] = useState(0);
  const [mode, setMode] = useState<'auto' | 'confirm'>('auto');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showStartModal, setShowStartModal] = useState(false);
  const [stages, setStages] = useState<Stage[]>([]);
  const [activeTaskId, setActiveTaskId] = useState<number | null>(null);
  const [activeTask, setActiveTask] = useState<AITask | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [aiFiles, setAiFiles] = useState<AIGeneratedFile[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [failedStageIndex, setFailedStageIndex] = useState<number | null>(null);
  const [novelStats, setNovelStats] = useState<NovelStats | null>(null);
  const [chapters, setChapters] = useState<ChapterItem[]>([]);
  const [selectedChapterId, setSelectedChapterId] = useState<number | null>(null);
  const [controlLoading, setControlLoading] = useState<'pause' | 'resume' | 'stop' | 'retry' | null>(null);

  // === v2 新增：三栏布局 UI 状态 ===
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // === v3 新增：三列可拖拽布局 ===
  const { leftWidth, rightWidth, onResizeLeft, onResizeRight } = useResizableLayout();

  // === v1 ref 保留 ===
  const pollingRef = useRef<number | null>(null);
  const mountedRef = useRef(true);
  const prevLogIdsRef = useRef<Set<number>>(new Set());
  const activeTaskIdRef = useRef<number | null>(null);
  const activeTaskRef = useRef<AITask | null>(null);
  const selectedProjectIdRef = useRef<number | null>(null);

  activeTaskIdRef.current = activeTaskId;
  activeTaskRef.current = activeTask;
  selectedProjectIdRef.current = selectedProjectId ?? null;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  // === v1 保留：doPoll（3s 轮询拉取任务进度）===
  const doPoll = useCallback(async () => {
    const pid = selectedProjectIdRef.current;
    const tid = activeTaskIdRef.current;
    if (!pid || !tid) return;
    try {
      const [tasks, steps, files, taskLogs] = await Promise.all([
        fetchAITasks(pid),
        fetchTaskSteps(pid, tid),
        listProjectFiles(pid).catch(() => []),
        fetchTaskLogs(pid, tid, 200).catch(() => []),
      ]);
      if (!mountedRef.current) return;

      const task = tasks.find(t => t.id === tid);
      if (task) {
        const newStatus = task.status ?? 'idle';
        setTaskStatus(newStatus);
        setActiveTask(task);
        const sortedSteps = [...steps].sort((a, b) => (a.step_no ?? 0) - (b.step_no ?? 0));
        const activeStepIndex = sortedSteps.findIndex(s => s.status === 'running' || s.status === 'failed');
        const completedCount = steps.filter(s => s.status === 'completed').length;
        const stageIndex = activeStepIndex >= 0 ? activeStepIndex : Math.max(0, Math.min(completedCount, Math.max(sortedSteps.length - 1, 0)));
        setCurrentStage(stageIndex);

        if (newStatus === 'failed') {
          setErrorMessage(task.error_message || '任务执行失败');
          const failedIdx = steps.findIndex(s => s.status === 'failed');
          setFailedStageIndex(failedIdx >= 0 ? failedIdx : stageIndex);
        }

        setStages(mapStepsToStages(sortedSteps));
      }

      const completedTask = tasks.find(t => t.id === tid && t.status === 'completed');
      if (completedTask?.output_payload) {
        try {
          const output = JSON.parse(completedTask.output_payload);
          setNovelStats({
            title: output.novel_title || '',
            totalWords: output.total_words || 0,
            totalChapters: output.target_chapters || 0,
            completedChapters: output.chapters_count || 0,
          });
        } catch {
          // ignore parse errors
        }
      }

      const prevIds = prevLogIdsRef.current;
      const stepLogs = steps.map((step, index) => mapStepToLogEntry(step, index, prevIds));
      const reactLogs = taskLogs.map((log, index) => mapTaskLogToLogEntry(log, steps.length + index, prevIds));
      const allLogs = [...stepLogs, ...reactLogs].sort((a, b) => a.id - b.id);
      prevLogIdsRef.current = new Set([...steps.map((s, i) => s.id ?? i + 1), ...taskLogs.map((l, i) => l.id ?? steps.length + i + 1)]);
      setLogs(allLogs);

      const aiGeneratedFiles = files.map((file, index) => mapFileInfoToAIGeneratedFile(file, index));
      setAiFiles(aiGeneratedFiles);
    } catch {
      // ignore poll errors
    }
  }, []);

  // === v1 保留：轮询触发 ===
  useEffect(() => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    if (taskStatus === 'running' && activeTaskId) {
      void doPoll();
      pollingRef.current = window.setInterval(() => {
        void doPoll();
      }, 3000);
    }
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [taskStatus, activeTaskId, doPoll]);

  // === v1 保留：任务运行时长计时器 ===
  useEffect(() => {
    const ticking = taskStatus === 'running' || taskStatus === 'pending' || taskStatus === 'cancelling';
    if (!ticking) {
      return;
    }
    setElapsedSeconds(computeElapsed(activeTaskRef.current?.started_at));
    const id = window.setInterval(() => {
      setElapsedSeconds(computeElapsed(activeTaskRef.current?.started_at));
    }, 1000);
    return () => window.clearInterval(id);
  }, [taskStatus]);

  // === v1 保留：项目切换时拉取文件 / 恢复任务 / 拉取章节 ===
  useEffect(() => {
    if (selectedProjectId) {
      void pollProjectFiles();
      void hydrateRecentTask(selectedProjectId);
      void pollChapters();
    }
  }, [selectedProjectId]);

  // === v1 保留：hydrateRecentTask ===
  async function hydrateRecentTask(projectId: number) {
    if (activeTaskIdRef.current) return;
    try {
      const tasks = await fetchAITasks(projectId);
      if (!mountedRef.current) return;

      let recentTask = tasks.find((task) => task.status === 'running' || task.status === 'pending');

      if (!recentTask) {
        const sortedTasks = [...tasks].sort((a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        );
        const failedTask = sortedTasks.find((t) => t.status === 'failed');
        if (failedTask) {
          recentTask = failedTask;
        } else {
          // Task 5: 没有 running/pending/failed 时，回退到最新一个任务（含 completed）
          recentTask = sortedTasks[0];
        }
      }

      if (!recentTask || !mountedRef.current) return;

      activeTaskIdRef.current = recentTask.id;
      selectedProjectIdRef.current = projectId;
      setActiveTaskId(recentTask.id);
      setActiveTask(recentTask);
      setTaskStatus(recentTask.status ?? 'idle');
      setErrorMessage(recentTask.error_message ?? null);

      if (recentTask.status === 'failed') {
        await doPoll();
        return;
      }

      await doPoll();
    } catch {
      // ignore hydration errors
    }
  }

  // === v1 保留：pollProjectFiles ===
  async function pollProjectFiles() {
    if (!selectedProjectId) return;
    try {
      const files = await listProjectFiles(selectedProjectId);
      if (!mountedRef.current) return;
      const aiGeneratedFiles = files.map((file, index) => mapFileInfoToAIGeneratedFile(file, index));
      setAiFiles(aiGeneratedFiles);
    } catch {
      // ignore poll errors
    }
  }

  // === v1 保留：pollChapters ===
  async function pollChapters() {
    if (!selectedProjectId) return;
    try {
      const chaptersData = await fetchChapters(selectedProjectId);
      if (!mountedRef.current) return;
      const mappedChapters: ChapterItem[] = chaptersData.map((ch: Chapter) => ({
        id: ch.id,
        chapterNo: ch.chapter_no,
        title: ch.title,
        status: ch.status,
        wordCount: ch.word_count,
      }));
      setChapters(mappedChapters);

      const totalWords = chaptersData.reduce((sum, ch) => sum + ch.word_count, 0);
      const completedChapters = chaptersData.filter(ch => ch.status === 'completed').length;
      setNovelStats(prev => ({
        title: prev?.title || '',
        totalWords,
        totalChapters: chaptersData.length,
        completedChapters,
      }));
    } catch {
      // ignore poll errors
    }
  }

  function handleSelectChapter(chapterId: number | null) {
    setSelectedChapterId(chapterId);
  }

  // === v1 保留：创建项目 ===
  async function handleCreateProject(payload: Record<string, unknown>) {
    try {
      const asNum = (v: unknown, fallback: number): number => {
        const n = Number(v);
        return Number.isFinite(n) && n > 0 ? n : fallback;
      };
      const minWords = asNum(payload.min_words_per_chapter, 2000);
      const maxWords = Math.max(minWords, asNum(payload.max_words_per_chapter, 4000));
      const project = await apiCreateProject({
        name: payload.name as string,
        genre: (payload.genre as string) || null,
        theme: (payload.theme as string) || null,
        writing_style: (payload.writing_style as string) || null,
        tone: (payload.tone as string) || null,
        target_audience: (payload.target_audience as string) || null,
        min_words_per_chapter: minWords,
        max_words_per_chapter: maxWords,
        target_chapters:
          payload.target_chapters != null ? asNum(payload.target_chapters, 0) || null : null,
        summary: (payload.notes as string) || '',
      });
      reloadProjects();
      setSelectedProjectId(project.id);
      setShowCreateModal(false);
    } catch (err) {
      console.error('Create project failed:', err);
    }
  }

  // === v1 保留：启动创作 ===
  async function handleStartCreation(payload: Record<string, unknown>) {
    if (!selectedProjectId) return;
    try {
      const runMode = (payload.mode as 'auto' | 'confirm') ?? 'auto';
      setMode(runMode);
      setErrorMessage(null);
      setFailedStageIndex(null);
      // 由项目级字数区间推导单章目标字数（中点），让自动创作也遵守用户设定字数
      const minW = selectedProject?.min_words_per_chapter ?? 2000;
      const maxW = selectedProject?.max_words_per_chapter ?? 4000;
      const derivedWordTarget = Math.max(minW, Math.round((minW + maxW) / 2));
      const result = await createAITask(selectedProjectId, {
        title: (payload.topic as string) || 'AI 全自动创作',
        query_text: (payload.query_text as string) || '',
        chapter_title: '自动生成章节',
        style_hint: (payload.style_prompt as string) || selectedProject?.writing_style || undefined,
        word_target: derivedWordTarget,
        chapter_no: Number(payload.start_chapter) || 1,
        book_id: typeof payload.book_id === 'number' ? payload.book_id : null,
      });
      const task = result.task;
      setActiveTaskId(task.id);
      activeTaskIdRef.current = task.id;
      setActiveTask(task);
      if (result.steps?.length) {
        setStages(mapStepsToStages(result.steps));
        const runningIndex = result.steps.findIndex((step) => step.status === 'running' || step.status === 'failed');
        setCurrentStage(runningIndex >= 0 ? runningIndex : 0);
      } else {
        setStages([]);
        setCurrentStage(0);
      }
      setTaskStatus('running');
      setShowStartModal(false);
      void doPoll();
    } catch (err) {
      console.error('Start creation failed:', err);
      setTaskStatus('idle');
      setErrorMessage(err instanceof Error ? err.message : '启动创作失败');
    }
  }

  // === v1 保留：handleRetry / handleApprove / handleSkip ===
  function handleRetry() {
    setErrorMessage(null);
    setFailedStageIndex(null);
    setTaskStatus('idle');
    setStages([]);
    setLogs([]);
    setCurrentStage(0);
    setShowStartModal(true);
  }

  function handleApprove() {
    setTaskStatus('running');
    setCurrentStage((prev) => prev + 1);
    setStages((prev) =>
      prev.map((s, i) =>
        i === currentStage ? { ...s, status: 'completed', progress: 100 } : s
      ).map((s, i) =>
        i === currentStage + 1 ? { ...s, status: 'running', progress: 50 } : s
      )
    );
  }

  function handleSkip() {
    setCurrentStage((prev) => prev + 1);
  }

  async function handleTaskControl(action: 'pause' | 'resume' | 'stop' | 'retry') {
    if (!selectedProjectId || !activeTaskId) return;
    setControlLoading(action);
    setErrorMessage(null);
    try {
      if (action === 'pause') {
        await controlTaskRuntime(selectedProjectId, activeTaskId, 'pause');
        setTaskStatus('paused');
      } else if (action === 'stop') {
        await cancelAITask(selectedProjectId, activeTaskId);
        setTaskStatus('cancelling');
      } else {
        await resumeAITask(selectedProjectId, activeTaskId);
        setTaskStatus('running');
      }
      await doPoll();
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : '任务控制失败');
    } finally {
      setControlLoading(null);
    }
  }

  // === v2 新增：项目切换（从 TopControlBar / ChatSidebar 触发）===
  function handleProjectChange(pid: number | null) {
    setSelectedProjectId(pid);
    // 切换项目时清空活动任务状态，让 hydrateRecentTask 重新加载
    setActiveTaskId(null);
    setActiveTask(null);
    setStages([]);
    setLogs([]);
    setTaskStatus('idle');
    setErrorMessage(null);
    setCurrentStage(0);
    activeTaskIdRef.current = null;
  }

  // === v2 新增：从 ChatSidebar 选择任务 ===
  async function handleTaskSelect(tid: number | null) {
    if (tid == null) {
      setActiveTaskId(null);
      setActiveTask(null);
      activeTaskIdRef.current = null;
      return;
    }
    if (!selectedProjectId) return;
    setActiveTaskId(tid);
    activeTaskIdRef.current = tid;
    // 加载任务详情
    try {
      const task = await fetchTask(selectedProjectId, tid);
      if (task) {
        setActiveTask(task);
        setTaskStatus(task.status ?? 'idle');
        setErrorMessage(task.error_message ?? null);
        // 拉取步骤 / 日志以恢复显示
        void doPoll();
      }
    } catch (err) {
      console.error('Load task failed:', err);
    }
  }

  // === v2 新增：Task 5 从侧边栏 + 按钮新建任务 ===
  async function handleCreateTask() {
    if (!selectedProjectId) return;
    try {
      const result = await createAITask(selectedProjectId, {
        title: `新对话 - ${new Date().toLocaleString('zh-CN')}`,
        query_text: '',
        chapter_title: '待定',
        word_target: 1500,
        chapter_no: 1,
      });
      await handleTaskSelect(result.task.id);
    } catch (err) {
      console.error('Create task failed:', err);
    }
  }

  return (
    <div className="command-center-v2">
      {/* 顶部工具栏（保留 v1 控件） */}
      <TopControlBar
        onShowCreate={() => setShowCreateModal(true)}
        onShowStart={() => setShowStartModal(true)}
        taskStatus={taskStatus}
        currentStage={currentStage}
        onProjectChange={handleProjectChange}
        onTaskControl={handleTaskControl}
        controlLoading={controlLoading}
        elapsedSeconds={activeTask ? elapsedSeconds : undefined}
      />

      {/* 三栏布局：左 / 中 / 右，均可拖拽 */}
      <div
        className="command-center-body"
        style={{
          gridTemplateColumns: `${leftWidth}px 6px minmax(360px, 1fr) 6px ${rightWidth}px`,
        }}
      >
        <ChatSidebar
          currentProjectId={selectedProjectId}
          currentTaskId={activeTaskId}
          onProjectSelect={handleProjectChange}
          onTaskSelect={handleTaskSelect}
          onCreateProject={() => setShowCreateModal(true)}
          onCreateTask={handleCreateTask}
          collapsed={sidebarCollapsed}
          onToggleCollapsed={() => setSidebarCollapsed((prev) => !prev)}
        />
        <ResizableSplitter
          ariaLabel="调整左侧栏宽度"
          onDrag={onResizeLeft}
        />
        <div className="command-center-main">
          {selectedProjectId && activeTaskId ? (
            <AgentChatWindow
              projectId={selectedProjectId}
              taskId={activeTaskId}
              taskTitle={activeTask?.title}
              taskStatus={activeTask?.status || 'idle'}
              onTaskChange={() => {
                // 触发外层重新拉取任务状态
                void doPoll();
              }}
            />
          ) : (
            <div className="command-center-empty">
              <img src="/hero-illustration.svg" alt="Novel AI Editor" className="command-center-empty-art" />
              <h2>开始你的 AI 小说创作之旅</h2>
              <p>联网调研热门题材 · AI 逐章创作 · 实时故事图谱 · 作者随时介入引导</p>
              <button
                type="button"
                className="primary-button"
                onClick={() => setShowStartModal(true)}
              >
                ✨ 启动 AI 创作
              </button>
            </div>
          )}
        </div>
        <ResizableSplitter
          ariaLabel="调整右侧可视化栏宽度"
          onDrag={onResizeRight}
        />
        <div className="command-center-viz">
          <MainVisualizationPanel
            currentStage={currentStage}
            projectId={selectedProjectId ?? undefined}
            activeTaskId={activeTaskId}
            taskStatus={taskStatus}
          />
        </div>
      </div>

      {/* Modal 弹窗 */}
      <ModalCreateProject
        visible={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreate={handleCreateProject}
      />

      <ModalStartCreation
        visible={showStartModal}
        onClose={() => setShowStartModal(false)}
        onStart={handleStartCreation}
        projectName={selectedProject?.name}
        projectId={selectedProjectId}
      />
    </div>
  );
}
