// Task 10 - ModelBadge.test.tsx
// 覆盖 ModalStartCreation 中的模型选择器 UI：
//   1. primary 模型名（短名，去掉 provider 前缀）
//   2. provider 标签
//   3. rate_limit 徽章
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { ProjectProvider } from '../../../context/ProjectContext';
import { ModalStartCreation } from '../ModalStartCreation';

// 隔离所有后端请求：ProjectProvider 用 fetchProjects，ModalStartCreation 用
// fetchAvailableModelsTyped / fetchAITasks / deleteAITask / cancelAITask。
vi.mock('../../../lib/api', () => ({
  fetchProjects: vi.fn().mockResolvedValue([]),
  fetchAvailableModels: vi.fn(),
  fetchAvailableModelsTyped: vi.fn(),
  fetchAITasks: vi.fn().mockResolvedValue([]),
  deleteAITask: vi.fn(),
  cancelAITask: vi.fn(),
  fetchTaskConcurrencyTyped: vi.fn().mockResolvedValue({
    max_concurrent: 1,
    current_running: 0,
    current_pending: 0,
    available_slots: 1,
    by_status: {},
  }),
  fetchChapters: vi.fn().mockResolvedValue([]),
  createProject: vi.fn(),
  createAITask: vi.fn(),
}));

import * as api from '../../../lib/api';

describe('ModalStartCreation model badge', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('displays primary model short name when loaded', async () => {
    (api.fetchAvailableModelsTyped as any).mockResolvedValue({
      primary: 'minimaxai/minimax-m2.7',
      fallback_chain: ['meta/llama-3.1-70b-instruct'],
      provider: 'openrouter',
      features: {
        rate_limit_per_minute: 40,
        long_context_window: true,
        json_mode_supported: true,
        max_concurrent_tasks: 1,
      },
      model_info: {},
    });

    render(
      <ProjectProvider>
        <ModalStartCreation
          visible
          onClose={() => {}}
          onStart={() => {}}
          projectName="测试项目"
          projectId={1}
        />
      </ProjectProvider>,
    );

    // 断言 1：primary 短名（去掉 provider 前缀）
    await waitFor(
      () => {
        expect(screen.getByText(/minimax-m2\.7/i)).toBeInTheDocument();
      },
      { timeout: 3000 },
    );
  });

  it('displays provider label and rate limit badge', async () => {
    (api.fetchAvailableModelsTyped as any).mockResolvedValue({
      primary: 'minimaxai/minimax-m2.7',
      fallback_chain: ['meta/llama-3.1-70b-instruct'],
      provider: 'openrouter',
      features: {
        rate_limit_per_minute: 40,
        long_context_window: true,
        json_mode_supported: true,
        max_concurrent_tasks: 1,
      },
      model_info: {},
    });

    render(
      <ProjectProvider>
        <ModalStartCreation
          visible
          onClose={() => {}}
          onStart={() => {}}
          projectName="测试项目"
          projectId={2}
        />
      </ProjectProvider>,
    );

    // 断言 2 & 3：provider 标签 + 限流徽章
    await waitFor(
      () => {
        expect(screen.getByText('openrouter')).toBeInTheDocument();
        expect(screen.getByText(/40\/min/)).toBeInTheDocument();
      },
      { timeout: 3000 },
    );
  });
});
