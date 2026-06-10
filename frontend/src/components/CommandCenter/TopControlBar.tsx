import React, { useEffect, useState } from 'react';
import {
  FolderPlus,
  Play,
  Pause,
  PlayCircle,
  Square,
  RotateCcw,
  Download,
  CheckCircle,
  AlertCircle,
  Activity,
  LogOut,
  User as UserIcon,
  ChevronDown,
} from 'lucide-react';
import { colors, spacing, borderRadius } from './styles';
import { useProjectContext } from '../../context/ProjectContext';
import { useAuth } from '../../context/AuthContext';
import { fetchTaskConcurrencyTyped, exportChapterHierarchy } from '../../lib/api';
import { ExportMenu, type ExportActionOption } from '../ExportMenu';
import { ThemeSwitcher } from '../ThemeSwitcher';

const statusConfig: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
  idle: { color: colors.idle, icon: <Square size={14} color={colors.idle} />, label: '待启动' },
  running: { color: colors.executing, icon: <CheckCircle size={14} color={colors.executing} />, label: '运行中' },
  paused: { color: colors.paused, icon: <AlertCircle size={14} color={colors.paused} />, label: '已暂停' },
  completed: { color: colors.success, icon: <CheckCircle size={14} color={colors.success} />, label: '已完成' },
  error: { color: colors.error, icon: <AlertCircle size={14} color={colors.error} />, label: '异常' },
};

// Task 2: 并发徽章配色
const CONCURRENCY_SATURATED = '#f59e0b'; // 满载琥珀色
const CONCURRENCY_HEALTHY = '#10b981';   // 健康绿色

type TopControlBarProps = {
  onShowCreate: () => void;
  onShowStart: () => void;
  taskStatus: string;
  currentStage: number;
  onProjectChange: (projectId: number | null) => void;
  onTaskControl?: (action: 'pause' | 'resume' | 'stop' | 'retry') => void;
  controlLoading?: 'pause' | 'resume' | 'stop' | 'retry' | null;
  // Task 3: 任务运行时长（秒），可选
  elapsedSeconds?: number;
};

// Task 2: 内部并发状态
type ConcurrencyState = {
  current: number;
  max: number;
  slots: number;
};

export function TopControlBar({
  onShowCreate,
  onShowStart,
  taskStatus,
  currentStage,
  onProjectChange,
  onTaskControl,
  controlLoading,
  elapsedSeconds,
}: TopControlBarProps) {
  const { projects, selectedProjectId } = useProjectContext();
  const { user, logout } = useAuth();
  const status = statusConfig[taskStatus] ?? statusConfig.idle;
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  const project = projects.find((p) => p.id === selectedProjectId) ?? null;

  // 导出选项：当前支持"整书层级 ZIP"，未来可加"项目归档/单章"等
  const exportOptions: ExportActionOption<'zip'>[] = [
    {
      format: 'zip',
      label: '整书层级 ZIP',
      description: '按 项目/任务/章节/小节/内容.md 层级结构打包',
      default: true,
    },
  ];

  // 用户点菜单中的格式后，弹原生保存对话框
  async function handleExportHierarchy(): Promise<{ blob: Blob; filename: string }> {
    if (!project) throw new Error('请先选择项目');
    const result = await exportChapterHierarchy(project.id);
    return { blob: result.blob, filename: result.filename };
  }

  // Task 2: 当前项目并发数
  const [concurrency, setConcurrency] = useState<ConcurrencyState | null>(null);

  // Task 2: 周期拉取（5s）项目并发状态；切换项目或卸载时清理
  useEffect(() => {
    if (!selectedProjectId) {
      setConcurrency(null);
      return;
    }
    let cancelled = false;
    async function load() {
      try {
        const info = await fetchTaskConcurrencyTyped(selectedProjectId as number);
        if (cancelled) return;
        if (info) {
          setConcurrency({
            current: info.current_running ?? 0,
            max: info.max_concurrent ?? 1,
            slots: info.available_slots ?? Math.max(0, (info.max_concurrent ?? 1) - (info.current_running ?? 0)),
          });
        } else {
          setConcurrency(null);
        }
      } catch {
        if (!cancelled) setConcurrency(null);
      }
    }
    void load();
    const id = window.setInterval(load, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [selectedProjectId]);

  // Task 2: 启动按钮禁用逻辑
  const saturated = !!concurrency && concurrency.current >= concurrency.max;
  const startDisabled = saturated || taskStatus === 'running' || !selectedProjectId;
  const startTitle = saturated
    ? '当前项目已达并发上限'
    : (!selectedProjectId
        ? '请先选择项目'
        : (taskStatus === 'running' ? '任务进行中' : '启动 AI 创作任务'));

  // Task 3: 格式化运行时长（MM:SS / HH:MM:SS）
  function formatElapsed(totalSec: number): string {
    const safe = Math.max(0, Math.floor(totalSec));
    const h = Math.floor(safe / 3600);
    const m = Math.floor((safe % 3600) / 60);
    const s = safe % 60;
    const pad = (n: number) => String(n).padStart(2, '0');
    if (h >= 1) {
      return `${pad(h)}:${pad(m)}:${pad(s)}`;
    }
    return `${pad(m)}:${pad(s)}`;
  }

  // Task 2: 渲染徽章文字
  let badgeText: string;
  let badgeColor: string;
  let badgeBg: string;
  let badgeBorder: string;
  if (!concurrency) {
    badgeText = `运行中 ?/${selectedProjectId ? '1' : '0'}`;
    badgeColor = colors.textSecondary;
    badgeBg = 'rgba(255,255,255,0.04)';
    badgeBorder = colors.border;
  } else if (concurrency.max <= 0) {
    badgeText = `运行中 ?/${concurrency.max}`;
    badgeColor = colors.textSecondary;
    badgeBg = 'rgba(255,255,255,0.04)';
    badgeBorder = colors.border;
  } else if (concurrency.current >= concurrency.max) {
    badgeText = `运行中 ${concurrency.current}/${concurrency.max}`;
    badgeColor = CONCURRENCY_SATURATED;
    badgeBg = 'rgba(245,158,11,0.12)';
    badgeBorder = 'rgba(245,158,11,0.35)';
  } else {
    badgeText = `运行中 ${concurrency.current}/${concurrency.max}`;
    badgeColor = CONCURRENCY_HEALTHY;
    badgeBg = 'rgba(16,185,129,0.12)';
    badgeBorder = 'rgba(16,185,129,0.35)';
  }

  return (
    <div className="cc-top-bar">
      <div className="cc-top-bar-content">
        <div className="cc-top-bar-left">
          <label className="cc-field">
            <span>项目</span>
            <select
              value={selectedProjectId ?? ''}
              onChange={(e) => onProjectChange(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="" disabled>
                {projects.length === 0 ? '暂无项目，请点击新建' : '选择项目'}
              </option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  #{p.id} · {p.name}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="cc-btn cc-btn-ghost" onClick={onShowCreate}>
            <FolderPlus size={16} />
            新建
          </button>
        </div>

        <div className="cc-top-bar-center">
          <button
            type="button"
            className="cc-btn cc-btn-primary"
            onClick={onShowStart}
            disabled={startDisabled}
            title={startTitle}
          >
            <Play size={16} />
            启动创作
          </button>
        </div>

        <div className="cc-top-bar-right">
          {/* Task 2: 并发可视化徽章 */}
          <div
            className="cc-status-indicator"
            title={concurrency ? `可用槽位 ${concurrency.slots}` : '并发信息加载中'}
            style={{
              border: `1px solid ${badgeBorder}`,
              background: badgeBg,
            }}
          >
            <Activity size={14} color={badgeColor} />
            <span className="cc-status-label" style={{ color: badgeColor }}>
              {badgeText}
            </span>
          </div>

          <div className="cc-status-indicator">
            <span className="cc-status-dot" style={{ backgroundColor: status.color }} />
            {status.icon}
            <span className="cc-status-label">{status.label}</span>
            <span className="cc-stage-badge">Stage {currentStage}</span>
          </div>

          {/* Task 3: 任务运行时长（运行时显示） */}
          {typeof elapsedSeconds === 'number' && elapsedSeconds > 0 && (
            <div
              className="cc-status-indicator"
              title="任务运行时长（基于 started_at 实时累加）"
            >
              <span className="cc-status-label" style={{ color: colors.textSecondary }}>
                运行时长
              </span>
              <span
                className="cc-stage-badge"
                style={{ background: 'transparent', color: colors.text, fontWeight: 700 }}
              >
                {formatElapsed(elapsedSeconds)}
              </span>
            </div>
          )}

          <div className="cc-control-btns">
            <button
              type="button"
              className="cc-btn cc-btn-icon"
              disabled={taskStatus !== 'running' || controlLoading != null}
              onClick={() => onTaskControl?.('pause')}
              title="暂停当前 AI 任务"
            >
              <Pause size={15} />
            </button>
            <button
              type="button"
              className="cc-btn cc-btn-icon"
              disabled={!['paused', 'failed', 'cancelled', 'partial', 'cancelling'].includes(taskStatus) || controlLoading != null}
              onClick={() => onTaskControl?.('resume')}
              title="从最近检查点继续 AI 任务"
            >
              <PlayCircle size={15} />
            </button>
            <button
              type="button"
              className="cc-btn cc-btn-icon"
              disabled={!['running', 'pending', 'paused', 'cancelling'].includes(taskStatus) || controlLoading != null}
              onClick={() => onTaskControl?.('stop')}
              title="请求停止当前 AI 任务"
            >
              <Square size={15} />
            </button>
            <button
              type="button"
              className="cc-btn cc-btn-icon"
              disabled={!['failed', 'cancelled', 'partial', 'paused'].includes(taskStatus) || controlLoading != null}
              onClick={() => onTaskControl?.('retry')}
              title="从检查点重试当前 AI 任务"
            >
              <RotateCcw size={15} />
            </button>
            <ExportMenu
              label="导出"
              options={exportOptions}
              onExport={handleExportHierarchy}
              disabled={!project}
              buttonClassName="cc-btn cc-btn-ghost cc-btn-export"
            />
          </div>

          {/* 主题切换按钮 */}
          <ThemeSwitcher />

          {/* 用户胶囊（登录后显示） */}
          {user && (
            <div className="cc-user-chip">
              <button
                type="button"
                className="cc-user-chip-btn"
                onClick={() => setUserMenuOpen((v) => !v)}
                title={user.display_name || user.username}
              >
                <div className="cc-user-avatar">
                  <UserIcon size={16} color="#fff" />
                </div>
                <span className="cc-user-name">{user.display_name || user.username}</span>
                <ChevronDown size={14} color={colors.textSecondary} />
              </button>
              {userMenuOpen && (
                <>
                  <div
                    className="cc-user-menu-backdrop"
                    onClick={() => setUserMenuOpen(false)}
                    aria-hidden="true"
                  />
                  <div className="cc-user-menu" role="menu">
                    <div className="cc-user-menu-header">
                      <div className="cc-user-menu-name">{user.display_name || user.username}</div>
                      {user.email && <div className="cc-user-menu-email">{user.email}</div>}
                      <div className="cc-user-menu-meta">@{user.username}</div>
                    </div>
                    <button
                      type="button"
                      className="cc-user-menu-item cc-user-menu-logout"
                      onClick={() => {
                        setUserMenuOpen(false);
                        logout();
                      }}
                    >
                      <LogOut size={15} />
                      退出登录
                    </button>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
