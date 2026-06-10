import { useState, useCallback, useEffect, useRef } from 'react';
import { X, Sparkles, History, Trash2, Loader2, Zap, XCircle, Cpu, BookPlus, BookText } from 'lucide-react';
import { colors, spacing, borderRadius } from './styles';
import { fetchAITasks, deleteAITask, cancelAITask, fetchAvailableModelsTyped, fetchBooks, createBook, type Book } from '../../lib/api';
import type { AITask } from '../../types';
import type { ModelsInfo } from '../../lib/api';

// 组件属性定义
type ModalStartCreationProps = {
  visible: boolean;
  onClose: () => void;
  onStart: (payload: Record<string, unknown>) => void;
  projectName?: string;
  projectId?: number | null;
};

// 历史任务类型
type HistoryTask = AITask & {
  stepCount: number;
  completedSteps: number;
};

// 状态标签映射
const statusLabels: Record<string, string> = {
  pending: '等待中',
  running: '运行中',
  cancelling: '取消中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
};

// 状态颜色映射
const statusColorMap: Record<string, string> = {
  pending: colors.idle,
  running: colors.warning,
  cancelling: '#f59e0b',
  completed: colors.success,
  failed: '#ef4444',
  cancelled: colors.textSecondary,
};

// 时间戳格式化函数
function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return '未知';
  const d = new Date(iso);
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

// 全自动流程步骤
const autoWorkflowSteps = [
  '热点扫描与题材分析',
  '故事脉络构思',
  '角色和世界观设计',
  '章节内容生成',
  '一致性检查和修订',
];

// 历史任务视图组件（已简化，移除步骤展开功能）
function TaskHistoryView({ projectId }: { projectId: number }) {
  const [tasks, setTasks] = useState<HistoryTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingTaskId, setDeletingTaskId] = useState<number | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // 加载任务列表
  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const rawTasks = await fetchAITasks(projectId);
        if (!cancelled) {
          const enriched: HistoryTask[] = rawTasks.map((t) => ({
            ...t,
            stepCount: 0,
            completedSteps: 0,
          }));
          setTasks(enriched.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()));
        }
      } catch {
        if (!cancelled) setTasks([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [projectId]);

  // 处理删除按钮点击
  function handleDeleteClick(taskId: number) {
    setDeletingTaskId(taskId);
    setDeleteError(null);
  }

  // 确认删除
  async function handleDeleteConfirm() {
    if (!deletingTaskId) return;
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await deleteAITask(projectId, deletingTaskId);
      setTasks((prev) => prev.filter((t) => t.id !== deletingTaskId));
      setDeletingTaskId(null);
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : '删除失败，请稍后重试');
    } finally {
      setIsDeleting(false);
    }
  }

  // 取消删除
  function handleDeleteCancel() {
    setDeletingTaskId(null);
    setDeleteError(null);
  }

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: colors.textSecondary }}>
        加载历史任务中...
      </div>
    );
  }

  if (tasks.length === 0) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: colors.textSecondary }}>
        <div style={{ fontSize: 16, marginBottom: 8 }}>暂无历史任务</div>
        <div style={{ fontSize: 13 }}>开始第一次 AI 创作后，这里将显示任务历史</div>
      </div>
    );
  }

  return (
    <>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 400, overflow: 'auto' }}>
      {tasks.map((task) => (
        <div key={task.id} style={{ 
          background: colors.cardBackground, 
          border: `1px solid ${colors.border}`, 
          borderRadius: 8,
          padding: '10px 14px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: statusColorMap[task.status] || colors.idle, flexShrink: 0 }} />
            <div style={{ textAlign: 'left', minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: colors.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {task.title}
              </div>
              <div style={{ fontSize: 11, color: colors.textSecondary }}>
                {formatTimestamp(task.created_at)} · ID: {task.id}
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
            <span style={{ fontSize: 11, color: statusColorMap[task.status] }}>
              {statusLabels[task.status] || task.status}
            </span>
            {(task.status === 'running' || task.status === 'pending') && projectId && (
              <button
                type="button"
                onClick={async () => {
                  try {
                    await cancelAITask(projectId, task.id);
                    setTasks((prev) => prev.map((t) => t.id === task.id ? { ...t, status: 'cancelling' } : t));
                  } catch (err) {
                    setDeleteError(err instanceof Error ? err.message : '取消失败');
                  }
                }}
                style={{
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  padding: 4,
                  borderRadius: 4,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#f59e0b',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = '#f59e0b18';
                  e.currentTarget.style.color = '#d97706';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.color = '#f59e0b';
                }}
                title="取消此任务"
              >
                <XCircle size={14} />
              </button>
            )}
            <button
              type="button"
              onClick={() => handleDeleteClick(task.id)}
              style={{
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                padding: 4,
                borderRadius: 4,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#ef4444',
                transition: 'all 0.15s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = '#ef444418';
                e.currentTarget.style.color = '#dc2626';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
                e.currentTarget.style.color = '#ef4444';
              }}
              title="删除此任务"
            >
              <Trash2 size={14} />
            </button>
          </div>
        </div>
      ))}
    </div>

    {deletingTaskId && (
      <div style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.6)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}>
        <div style={{
          background: colors.cardBackground,
          border: `1px solid ${colors.border}`,
          borderRadius: 12,
          padding: 24,
          maxWidth: 400,
          width: '90%',
        }}>
          <h3 style={{ margin: '0 0 12px', fontSize: 16, fontWeight: 600, color: colors.text }}>
            确认删除任务
          </h3>
          <p style={{ margin: '0 0 16px', fontSize: 14, color: colors.textSecondary, lineHeight: 1.5 }}>
            确定删除此任务？此操作不可恢复。
          </p>
          {deleteError && (
            <div style={{
              padding: '8px 12px',
              background: '#ef444418',
              border: '1px solid #ef4444',
              borderRadius: 6,
              fontSize: 13,
              color: '#ef4444',
              marginBottom: 16,
            }}>
              {deleteError}
            </div>
          )}
          <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
            <button
              type="button"
              onClick={handleDeleteCancel}
              disabled={isDeleting}
              style={{
                padding: '8px 16px',
                background: 'transparent',
                border: `1px solid ${colors.border}`,
                borderRadius: 6,
                cursor: isDeleting ? 'not-allowed' : 'pointer',
                fontSize: 13,
                color: colors.textSecondary,
                opacity: isDeleting ? 0.5 : 1,
              }}
            >
              取消
            </button>
            <button
              type="button"
              onClick={handleDeleteConfirm}
              disabled={isDeleting}
              style={{
                padding: '8px 16px',
                background: isDeleting ? '#991b1b' : '#ef4444',
                border: 'none',
                borderRadius: 6,
                cursor: isDeleting ? 'not-allowed' : 'pointer',
                fontSize: 13,
                color: '#fff',
                fontWeight: 500,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                opacity: isDeleting ? 0.7 : 1,
                transition: 'all 0.15s',
              }}
              onMouseEnter={(e) => {
                if (!isDeleting) e.currentTarget.style.background = '#dc2626';
              }}
              onMouseLeave={(e) => {
                if (!isDeleting) e.currentTarget.style.background = '#ef4444';
              }}
            >
              {isDeleting ? (
                <>
                  <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
                  删除中...
                </>
              ) : (
                <>
                  <Trash2 size={14} />
                  确认删除
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    )}
  </>
  );
}

// 主模态框组件
export function ModalStartCreation({ visible, onClose, onStart, projectName, projectId }: ModalStartCreationProps) {
  const [activeTab, setActiveTab] = useState<'create' | 'history'>('create');
  const [topic, setTopic] = useState('');
  const [error, setError] = useState<string | null>(null);
  // Task 1: 当前模型信息（primary / fallback / provider / rate limit）
  const [models, setModels] = useState<ModelsInfo | null>(null);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsError, setModelsError] = useState(false);
  // Task 7: 书籍选择 / 新建
  const [books, setBooks] = useState<Book[]>([]);
  const [booksLoading, setBooksLoading] = useState(false);
  const [selectedBookId, setSelectedBookId] = useState<number | null>(null);
  const [creatingBook, setCreatingBook] = useState(false);
  const [bookCreateError, setBookCreateError] = useState<string | null>(null);
  const didOpenRef = useRef(false);

  // 模态框打开时重置状态
  useEffect(() => {
    if (visible) {
      setActiveTab('create');
      setTopic('');
      setError(null);
      setSelectedBookId(null);
      setBookCreateError(null);
      didOpenRef.current = true;
    }
  }, [visible]);

  // Task 7: 在"新建任务" Tab 打开时加载当前项目所有 books
  useEffect(() => {
    if (!visible || activeTab !== 'create' || !projectId) {
      return;
    }
    let cancelled = false;
    async function loadBooks() {
      setBooksLoading(true);
      try {
        const list = await fetchBooks(projectId as number);
        if (cancelled) return;
        setBooks(list);
        // 若没有选中过，则默认选中第一本
        if (list.length > 0) {
          setSelectedBookId((prev) => (prev == null ? list[0].id : prev));
        } else {
          setSelectedBookId(null);
        }
      } catch {
        if (!cancelled) setBooks([]);
      } finally {
        if (!cancelled) setBooksLoading(false);
      }
    }
    void loadBooks();
    return () => { cancelled = true; };
  }, [visible, activeTab, projectId]);

  // Task 7: 新建书
  const handleCreateBook = useCallback(async () => {
    if (!projectId || creatingBook) return;
    const name = window.prompt('请输入新书名', '新书');
    if (name == null) return;
    const trimmed = name.trim();
    if (!trimmed) {
      setBookCreateError('书名不能为空');
      return;
    }
    setCreatingBook(true);
    setBookCreateError(null);
    try {
      const book = await createBook(projectId, trimmed);
      setBooks((prev) => [...prev, book]);
      setSelectedBookId(book.id);
    } catch (err) {
      setBookCreateError(err instanceof Error ? err.message : '创建书失败');
    } finally {
      setCreatingBook(false);
    }
  }, [projectId, creatingBook]);

  // Task 1: 在"新建任务" Tab 打开时加载当前可用模型信息；加载失败时降级展示，不阻塞开始创作
  useEffect(() => {
    if (!visible || activeTab !== 'create' || !projectId) {
      return;
    }
    let cancelled = false;
    async function loadModels() {
      setModelsLoading(true);
      setModelsError(false);
      try {
        const info = await fetchAvailableModelsTyped(projectId as number);
        if (cancelled) return;
        if (info) {
          setModels(info);
        } else {
          setModels(null);
          setModelsError(true);
        }
      } catch {
        if (!cancelled) {
          setModels(null);
          setModelsError(true);
        }
      } finally {
        if (!cancelled) setModelsLoading(false);
      }
    }
    void loadModels();
    return () => { cancelled = true; };
  }, [visible, activeTab, projectId]);

  // 截取模型名最后一段（去除 provider 前缀），如 minimaxai/minimax-m2.7 -> minimax-m2.7
  function shortModelName(name?: string | null): string {
    if (!name) return '';
    const segments = name.split('/');
    return segments[segments.length - 1] || name;
  }

  // 从 model_info 字典里查主模型的元信息（context_window / best_for / speed）
  function readModelInfo(info: ModelsInfo | null): {
    contextWindow?: number;
    bestFor?: string[];
    speed?: string;
  } | null {
    if (!info || !info.primary) return null;
    const lookup = info.model_info?.[info.primary];
    if (!lookup || typeof lookup !== 'object') return null;
    const record = lookup as Record<string, unknown>;
    const contextWindow = typeof record.context_window === 'number' ? record.context_window : undefined;
    const bestFor = Array.isArray(record.best_for)
      ? (record.best_for.filter((x) => typeof x === 'string') as string[])
      : undefined;
    const speed = typeof record.speed === 'string' ? record.speed : undefined;
    if (!contextWindow && !bestFor && !speed) return null;
    return { contextWindow, bestFor, speed };
  }

  // 把 token 数转成人类友好的字符串（1M / 262K / 32K）
  function formatContextWindow(tokens?: number): string {
    if (!tokens || tokens <= 0) return '';
    if (tokens >= 1_000_000) {
      const m = tokens / 1_000_000;
      return `${m >= 10 ? Math.round(m) : m.toFixed(m >= 10 ? 0 : 1)}M`;
    }
    if (tokens >= 1_000) {
      return `${Math.round(tokens / 1_000)}K`;
    }
    return `${tokens}`;
  }

  // 背景点击关闭
  const handleBackdropClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (e.target === e.currentTarget) onClose();
    },
    [onClose],
  );

  // 取消操作
  function handleCancel() {
    setTopic('');
    setError(null);
    onClose();
  }

  // 开始创作 - 简化为全自动模式
  function handleStart() {
    const topicValue = topic.trim() || 'AI自主决定题材';

    onStart({
      topic: topicValue,
      query_text: topic.trim() || '当前热门网络小说题材趋势',
      mode: 'auto',
      // Task 7: 透传选中的 book_id（若已选择）
      book_id: selectedBookId,
    });
    handleCancel();
  }

  if (!visible) return null;

  return (
    <div className="cc-modal-backdrop" onClick={handleBackdropClick}>
      <div className="cc-modal cc-modal-wide">
        {/* 模态框头部 */}
        <div className="cc-modal-header">
          <div className="cc-modal-title">
            <Sparkles size={18} color={colors.warning} />
            <h3>启动 AI 创作</h3>
          </div>
          <button type="button" className="cc-btn cc-btn-close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {/* Tab 切换 */}
        <div style={{ display: 'flex', gap: 0, borderBottom: `1px solid ${colors.border}`, padding: '0 20px' }}>
          <button
            type="button"
            onClick={() => setActiveTab('create')}
            style={{
              flex: 1,
              padding: '10px 0',
              background: 'transparent',
              border: 'none',
              borderBottom: activeTab === 'create' ? `2px solid ${colors.accent}` : '2px solid transparent',
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: activeTab === 'create' ? 600 : 400,
              color: activeTab === 'create' ? colors.accent : colors.textSecondary,
              transition: 'all 0.15s',
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
              <Sparkles size={14} />
              新建任务
            </span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('history')}
            style={{
              flex: 1,
              padding: '10px 0',
              background: 'transparent',
              border: 'none',
              borderBottom: activeTab === 'history' ? `2px solid ${colors.accent}` : '2px solid transparent',
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: activeTab === 'history' ? 600 : 400,
              color: activeTab === 'history' ? colors.accent : colors.textSecondary,
              transition: 'all 0.15s',
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
              <History size={14} />
              历史任务
            </span>
          </button>
        </div>

        {activeTab === 'create' ? (
          <>
            <div className="cc-modal-body">
              {/* 项目信息 */}
              <div className="cc-modal-project-name">
                <span>项目：</span>
                <strong>{projectName ?? '未选择项目'}</strong>
              </div>

              {/* 全自动模式提示卡片 */}
              <div style={{
                background: `linear-gradient(135deg, ${colors.accent}10 0%, ${colors.warning}10 100%)`,
                border: `1px solid ${colors.accent}30`,
                borderRadius: 12,
                padding: 16,
                marginBottom: 16,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                  <Zap size={16} color={colors.accent} />
                  <span style={{ fontSize: 14, fontWeight: 600, color: colors.accent }}>
                    AI全自动创作模式
                  </span>
                </div>
                <div style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 1.6 }}>
                  系统将根据当前市场趋势自动完成：
                </div>
                <ul style={{ margin: '8px 0 0', padding: '0 0 0 20px', fontSize: 13, color: colors.textSecondary, lineHeight: 1.8 }}>
                  {autoWorkflowSteps.map((step, index) => (
                    <li key={index}>{step}</li>
                  ))}
                </ul>
              </div>

              {/* Task 1: 当前模型信息卡片 */}
              <div style={{
                background: `linear-gradient(135deg, ${colors.cardBackground} 0%, ${colors.cardBackgroundHover} 100%)`,
                border: `1px solid ${colors.border}`,
                borderRadius: 12,
                padding: 14,
                marginBottom: 16,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                  <Cpu size={15} color={colors.textSecondary} />
                  <span style={{ fontSize: 13, fontWeight: 600, color: colors.text }}>
                    当前模型信息
                  </span>
                </div>
                {modelsLoading ? (
                  <div style={{ fontSize: 12, color: colors.textSecondary }}>模型信息加载中…</div>
                ) : modelsError || !models ? (
                  <div style={{ fontSize: 12, color: colors.idle }}>模型信息不可用</div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {/* primary 模型名 + provider 标签 */}
                    {(() => {
                      const primaryInfo = readModelInfo(models);
                      return (
                        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                          <span style={{ fontSize: 12, color: colors.textSecondary }}>主模型</span>
                          <code style={{
                            fontSize: 12,
                            color: colors.text,
                            background: 'rgba(255,255,255,0.06)',
                            padding: '2px 8px',
                            borderRadius: 4,
                            fontFamily: 'Cascadia Code, SFMono-Regular, Consolas, monospace',
                          }}>
                            {shortModelName(models.primary) || '未配置'}
                          </code>
                          {models.provider && (
                            <span style={{
                              fontSize: 10,
                              color: colors.accent,
                              background: 'rgba(59,130,246,0.15)',
                              padding: '2px 8px',
                              borderRadius: 999,
                              fontWeight: 700,
                            }}>
                              {models.provider}
                            </span>
                          )}
                          {primaryInfo?.contextWindow ? (
                            <span
                              title={primaryInfo.bestFor ? `适用于：${primaryInfo.bestFor.join('、')}` : undefined}
                              style={{
                                fontSize: 10,
                                color: '#22d3ee',
                                background: 'rgba(34,211,238,0.12)',
                                padding: '2px 8px',
                                borderRadius: 999,
                                fontWeight: 700,
                              }}
                            >
                              上下文 {formatContextWindow(primaryInfo.contextWindow)}
                            </span>
                          ) : null}
                          {primaryInfo?.speed ? (
                            <span style={{
                              fontSize: 10,
                              color: colors.textSecondary,
                              background: 'rgba(255,255,255,0.04)',
                              padding: '2px 8px',
                              borderRadius: 999,
                              fontWeight: 700,
                            }}>
                              速度 {primaryInfo.speed}
                            </span>
                          ) : null}
                          {typeof models.features?.rate_limit_per_minute === 'number' && (
                            <span style={{
                              fontSize: 10,
                              color: colors.warning,
                              background: 'rgba(245,158,11,0.15)',
                              padding: '2px 8px',
                              borderRadius: 999,
                              fontWeight: 700,
                            }}>
                              限流 {models.features.rate_limit_per_minute}/min
                            </span>
                          )}
                        </div>
                      );
                    })()}
                    {/* fallback 链 */}
                    {Array.isArray(models.fallback_chain) && models.fallback_chain.length > 0 && (
                      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
                        <span style={{ fontSize: 12, color: colors.textSecondary }}>Fallback</span>
                        {models.fallback_chain.slice(0, 3).map((m, i) => {
                          const info = (models.model_info?.[m] ?? {}) as Record<string, unknown>;
                          const ctx = typeof info.context_window === 'number' ? info.context_window : null;
                          return (
                            <span key={`${m}-${i}`} style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: 4,
                              fontSize: 11,
                              color: colors.textSecondary,
                              background: 'rgba(255,255,255,0.04)',
                              border: `1px solid ${colors.border}`,
                              padding: '1px 6px',
                              borderRadius: 4,
                              fontFamily: 'Cascadia Code, SFMono-Regular, Consolas, monospace',
                            }}>
                              {shortModelName(m)}
                              {ctx ? (
                                <span style={{ color: '#22d3ee', fontWeight: 700 }}>
                                  · {formatContextWindow(ctx)}
                                </span>
                              ) : null}
                            </span>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* 一句话主题输入 */}
              <div className="cc-form-group">
                <label className="cc-label">
                  <Sparkles size={13} />
                  一句话主题描述
                  <span className="cc-optional">(可选 / 留空则AI自主决定)</span>
                </label>
                <input
                  type="text"
                  placeholder="例如：科幻悬疑小说 / 都市奇幻 / 留空由AI决定"
                  value={topic}
                  onChange={(e) => { setTopic(e.target.value); setError(null); }}
                  maxLength={100}
                  style={{ fontSize: 14 }}
                />
              </div>

              {/* Task 7: 书籍选择器 */}
              <div className="cc-form-group">
                <label className="cc-label">
                  <BookText size={13} />
                  选择书籍
                  <span className="cc-optional">
                    {books.length > 0 ? `（共 ${books.length} 本）` : '（当前项目下暂无书）'}
                  </span>
                </label>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <select
                    value={selectedBookId == null ? '' : String(selectedBookId)}
                    onChange={(e) => {
                      const v = e.target.value;
                      setSelectedBookId(v ? Number(v) : null);
                    }}
                    disabled={booksLoading || books.length === 0}
                    style={{
                      flex: 1,
                      padding: '8px 10px',
                      fontSize: 13,
                      background: 'rgba(30,41,59,0.6)',
                      color: colors.text,
                      border: `1px solid ${colors.border}`,
                      borderRadius: 6,
                      outline: 'none',
                      cursor: booksLoading || books.length === 0 ? 'not-allowed' : 'pointer',
                    }}
                  >
                    {booksLoading ? (
                      <option value="">加载中…</option>
                    ) : books.length === 0 ? (
                      <option value="">（无书可选择 — 请先新建）</option>
                    ) : (
                      <>
                        <option value="">— 请选择书籍 —</option>
                        {books.map((b) => (
                          <option key={b.id} value={String(b.id)}>
                            {b.name} #{b.id}
                          </option>
                        ))}
                      </>
                    )}
                  </select>
                  <button
                    type="button"
                    onClick={handleCreateBook}
                    disabled={creatingBook || !projectId}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                      padding: '8px 12px',
                      fontSize: 12,
                      background: 'rgba(99,102,241,0.18)',
                      border: '1px solid rgba(99,102,241,0.4)',
                      color: '#a5b4fc',
                      borderRadius: 6,
                      cursor: creatingBook || !projectId ? 'not-allowed' : 'pointer',
                      opacity: creatingBook ? 0.6 : 1,
                      whiteSpace: 'nowrap',
                    }}
                    title="新建一本书"
                  >
                    {creatingBook ? <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> : <BookPlus size={13} />}
                    新建书
                  </button>
                </div>
                {bookCreateError && (
                  <div style={{ marginTop: 6, fontSize: 12, color: '#fca5a5' }}>
                    {bookCreateError}
                  </div>
                )}
                {books.length > 0 && selectedBookId === null && (
                  <div style={{ marginTop: 6, fontSize: 12, color: '#fbbf24' }}>
                    ⚠ 请先选择一本书再开始创作。
                  </div>
                )}
              </div>

              {/* 错误提示 */}
              {error && <p className="cc-error">{error}</p>}
            </div>

            {/* 底部按钮 */}
            <div className="cc-modal-footer">
              <button type="button" className="cc-btn cc-btn-ghost" onClick={handleCancel}>
                取消
              </button>
              <button
                type="button"
                className="cc-btn cc-btn-primary cc-btn-start"
                onClick={handleStart}
                disabled={books.length > 0 && selectedBookId === null}
                title={books.length > 0 && selectedBookId === null ? '请先选择一本书' : undefined}
              >
                <Sparkles size={15} />
                开始创作
              </button>
            </div>
          </>
        ) : (
          <div className="cc-modal-body" style={{ paddingBottom: 20 }}>
            <div className="cc-modal-project-name" style={{ marginBottom: 12 }}>
              <span>项目：</span>
              <strong>{projectName ?? '未选择项目'}</strong>
            </div>
            {projectId ? (
              <TaskHistoryView projectId={projectId} />
            ) : (
              <div style={{ padding: 40, textAlign: 'center', color: colors.textSecondary }}>
                请先选择一个项目
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
