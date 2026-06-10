// Task 10 - ConcurrencyBadge.test.tsx
// 覆盖 TopControlBar 中的并发可视化徽章：
//   1. 无任务运行时显示 `运行中 0/1`
//   2. 满载（1/1）时"启动创作"按钮 disabled
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { ProjectProvider } from '../../../context/ProjectContext';
import { ThemeProvider } from '../../../contexts/ThemeContext';
import { TopControlBar } from '../TopControlBar';

// 隔离所有后端请求：ProjectProvider 用 fetchProjects，TopControlBar 用
// fetchTaskConcurrencyTyped。其它可选 API 显式打桩避免触发真实网络。
vi.mock('../../../lib/api', () => ({
  fetchProjects: vi.fn(),
  fetchAvailableModelsTyped: vi.fn().mockResolvedValue(null),
  fetchTaskConcurrencyTyped: vi.fn(),
  fetchAITasks: vi.fn().mockResolvedValue([]),
  deleteAITask: vi.fn(),
  cancelAITask: vi.fn(),
  fetchChapters: vi.fn().mockResolvedValue([]),
  createProject: vi.fn(),
  createAITask: vi.fn(),
}));

// TopControlBar 依赖 useAuth / useTheme；测试只关心徽章，按需 mock 上下文。
vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, username: 'tester' },
    token: 'fake-token',
    loading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

import * as api from '../../../lib/api';
import type React from 'react';

describe('TopControlBar concurrency badge', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows 0/1 when no tasks running', async () => {
    // ProjectProvider 加载到 1 个项目，自动选中 #1
    (api.fetchProjects as any).mockResolvedValue([{ id: 1, name: '测试项目' }]);
    (api.fetchTaskConcurrencyTyped as any).mockResolvedValue({
      max_concurrent: 1,
      current_running: 0,
      current_pending: 0,
      available_slots: 1,
      by_status: {},
    });

    render(
      <ThemeProvider>
        <ProjectProvider>
          <TopControlBar
            onShowCreate={() => {}}
            onShowStart={() => {}}
            taskStatus="idle"
            currentStage={0}
            onProjectChange={() => {}}
          />
        </ProjectProvider>
      </ThemeProvider>,
    );

    // 等待 ProjectProvider 选中项目、并发拉取返回后徽章渲染
    await waitFor(
      () => {
        expect(screen.getByText(/0\/1/)).toBeInTheDocument();
      },
      { timeout: 3000 },
    );
  });

  it('disables start button when concurrency saturated', async () => {
    (api.fetchProjects as any).mockResolvedValue([{ id: 1, name: '测试项目' }]);
    (api.fetchTaskConcurrencyTyped as any).mockResolvedValue({
      max_concurrent: 1,
      current_running: 1,
      current_pending: 0,
      available_slots: 0,
      by_status: { running: 1 },
    });

    render(
      <ThemeProvider>
        <ProjectProvider>
          <TopControlBar
            onShowCreate={() => {}}
            onShowStart={() => {}}
            taskStatus="idle"
            currentStage={0}
            onProjectChange={() => {}}
          />
        </ProjectProvider>
      </ThemeProvider>,
    );

    await waitFor(
      () => {
        const startBtn = screen.getByText(/启动创作/);
        expect(startBtn).toBeDisabled();
      },
      { timeout: 3000 },
    );
  });
});
