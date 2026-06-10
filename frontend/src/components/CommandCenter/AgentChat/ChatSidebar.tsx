import { useEffect, useState } from 'react';
import { Folder, MessageSquare, Plus, ChevronLeft, ChevronRight, FolderPlus } from 'lucide-react';
import { fetchProjects, fetchAITasks } from '../../../lib/api';
import type { Project, AITask } from '../../../types';
import './AgentChat.css';

type ChatSidebarProps = {
  currentProjectId: number | null;
  currentTaskId: number | null;
  onProjectSelect: (projectId: number) => void;
  onTaskSelect: (taskId: number) => void;
  onCreateProject: () => void;
  onCreateTask?: () => void;
  collapsed: boolean;
  onToggleCollapsed: () => void;
};

export function ChatSidebar({
  currentProjectId,
  currentTaskId,
  onProjectSelect,
  onTaskSelect,
  onCreateProject,
  onCreateTask,
  collapsed,
  onToggleCollapsed,
}: ChatSidebarProps) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [tasks, setTasks] = useState<AITask[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        setLoading(true);
        const list = await fetchProjects();
        if (mounted) setProjects(Array.isArray(list) ? list : []);
      } catch (e) {
        console.error('Failed to load projects:', e);
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    if (currentProjectId == null) {
      setTasks([]);
      return;
    }
    let mounted = true;
    (async () => {
      try {
        const list = await fetchAITasks(currentProjectId);
        if (mounted) {
          const sorted = [...list].sort(
            (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
          );
          setTasks(sorted);
        }
      } catch (e) {
        console.error('Failed to load tasks:', e);
      }
    })();
    return () => { mounted = false; };
  }, [currentProjectId]);

  if (collapsed) {
    return (
      <div className="chat-sidebar chat-sidebar-collapsed">
        <button className="chat-sidebar-toggle" onClick={onToggleCollapsed} title="展开侧边栏">
          <ChevronRight size={16} />
        </button>
        <div className="chat-sidebar-collapsed-icons">
          <button title="新建项目" onClick={onCreateProject}><FolderPlus size={18} /></button>
          {projects.slice(0, 8).map((p) => (
            <button
              key={p.id}
              title={p.name}
              className={currentProjectId === p.id ? 'active' : ''}
              onClick={() => onProjectSelect(p.id)}
            >
              <Folder size={18} />
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="chat-sidebar">
      <div className="chat-sidebar-brand">
        <img src="/logo.svg" alt="墨问" className="chat-sidebar-brand-logo" />
        <div className="chat-sidebar-brand-text">
          <span className="chat-sidebar-brand-name">墨问</span>
          <span className="chat-sidebar-brand-sub">Novel AI Editor</span>
        </div>
      </div>
      <div className="chat-sidebar-header">
        <button className="chat-sidebar-toggle" onClick={onToggleCollapsed} title="折叠侧边栏">
          <ChevronLeft size={16} />
        </button>
        <button className="chat-sidebar-new-project" onClick={onCreateProject}>
          <Plus size={14} />
          <span>新建项目</span>
        </button>
      </div>

      <div className="chat-sidebar-section">
        <div className="chat-sidebar-section-title">
          <Folder size={12} />
          <span>项目</span>
        </div>
        {loading && <div className="chat-sidebar-empty">加载中...</div>}
        {!loading && projects.length === 0 && (
          <div className="chat-sidebar-empty">暂无项目</div>
        )}
        {projects.map((p) => (
          <button
            key={p.id}
            className={`chat-sidebar-item ${currentProjectId === p.id ? 'active' : ''}`}
            onClick={() => onProjectSelect(p.id)}
          >
            <Folder size={14} />
            <span className="chat-sidebar-item-text">{p.name}</span>
          </button>
        ))}
      </div>

      {currentProjectId != null && (
        <div className="chat-sidebar-section">
          <div className="chat-sidebar-section-title">
            <MessageSquare size={12} />
            <span>对话</span>
            {onCreateTask && (
              <button
                type="button"
                className="chat-sidebar-section-action"
                onClick={onCreateTask}
                title="新建对话"
                aria-label="新建对话"
              >
                <Plus size={12} />
              </button>
            )}
          </div>
          {tasks.length === 0 && (
            <div className="chat-sidebar-empty">暂无任务</div>
          )}
          {tasks.map((t) => {
            const isActive = currentTaskId === t.id;
            const statusColor =
              t.status === 'completed'
                ? '#10b981'
                : t.status === 'running'
                ? '#8b5cf6'    // 紫色（淡雅水墨风）
                : t.status === 'failed'
                ? '#f87171'
                : '#a78bfa'; // 淡紫（淡雅水墨风）
            const createdLabel = (() => {
              try {
                return new Date(t.created_at).toLocaleString('zh-CN', {
                  month: 'numeric',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                });
              } catch {
                return '';
              }
            })();
            return (
              <button
                key={t.id}
                className={`chat-sidebar-item chat-sidebar-task ${isActive ? 'active' : ''}`}
                onClick={() => onTaskSelect(t.id)}
                title={t.title || `任务 #${t.id}`}
              >
                <span
                  className="chat-sidebar-task-dot"
                  style={{ background: statusColor }}
                  aria-hidden="true"
                />
                <span className="chat-sidebar-item-text">
                  <span className="chat-sidebar-task-title">{t.title || `任务 #${t.id}`}</span>
                  <span className="chat-sidebar-task-meta">
                    {createdLabel}
                    {t.chapter_id != null ? ` · 第 ${t.chapter_id} 章` : ''}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
