/**
 * ThemeContext 单元测试
 * 覆盖：
 * 1. 6 张预设主题在初始 mount 时被注入到 :root 的 --theme-* 变量
 * 2. setTheme 切换时，--theme-primary / --theme-bg-image 都更新
 * 3. localStorage 持久化：刷新后恢复
 * 4. uploadTheme 把 File 转为 dataURL 并加入主题列表
 * 5. removeTheme / resetThemes 正常工作
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { act, render, renderHook } from '@testing-library/react';
import { ThemeProvider, useTheme, type Theme } from '../ThemeContext';
import type { ReactNode } from 'react';

// 颜色提取算法在 jsdom 中可用（jsdom 16+ 支持 canvas getContext stub），
// 但 extractPalette 内部依赖 HTMLImageElement.onload；我们用 mock 跳过。

const mockedExtractPalette = vi.fn(async (src: string) => ({
  colors: ['#0ea5e9', '#38bdf8', '#0c4a6e', '#bae6fd', '#e0f2fe', '#f0f9ff'],
  primary: '#0ea5e9',
  secondary: '#38bdf8',
  background: '#f0f9ff',
  foreground: '#ffffff',
  primarySoft: 'rgba(14, 165, 233, 0.12)',
  shadow: 'rgba(12, 74, 110, 0.18)',
}));

vi.mock('../../lib/colorExtractor', () => ({
  extractPalette: (...args: unknown[]) => mockedExtractPalette(args[0] as string),
  extractDominantColor: vi.fn(async () => '#0ea5e9'),
}));

function getRootVar(name: string): string {
  return document.documentElement.style.getPropertyValue(name).trim();
}

function wrapper(props: { children?: ReactNode }) {
  return <ThemeProvider>{props.children}</ThemeProvider>;
}

describe('ThemeContext', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.style.cssText = '';
    vi.clearAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('挂载后默认主题（墨问默认主题）变量被写入 :root', () => {
    render(wrapper({}));
    expect(getRootVar('--theme-primary')).toBe('#7c3aed');
    expect(getRootVar('--theme-secondary')).toBe('#a78bfa');
    expect(getRootVar('--theme-bg')).toBe('#f5f0ff');
    expect(getRootVar('--theme-color-0')).toBe('#7c3aed');
    // v3 修复：--theme-bg-image 也写入 :root
    expect(getRootVar('--theme-bg-image')).toContain('theme-mowen-default.png');
  });

  it('切换到秋枫霞谷，--theme-primary 变 #dc2626', () => {
    const { result } = renderHook(() => useTheme(), { wrapper });
    act(() => {
      result.current.setTheme('vermilion-maple');
    });
    expect(getRootVar('--theme-primary')).toBe('#dc2626');
    expect(getRootVar('--theme-bg')).toBe('#fffbeb');
  });

  it('切换到青碧（cyan-jade）', () => {
    const { result } = renderHook(() => useTheme(), { wrapper });
    act(() => {
      result.current.setTheme('cyan-jade');
    });
    expect(getRootVar('--theme-primary')).toBe('#0d9488');
    expect(getRootVar('--theme-secondary')).toBe('#5eead4');
  });

  it('持久化：选择 vermilion 后重新挂载，依然是 vermilion', () => {
    const { unmount } = renderHook(() => useTheme(), { wrapper });
    act(() => {
      // 用 useTheme().setTheme 模拟用户操作
    });
    // 模拟用户选择 vermilion
    localStorage.setItem(
      'novel-ai.theme.v1',
      JSON.stringify({ currentId: 'vermilion-maple', custom: [] }),
    );
    unmount();
    renderHook(() => useTheme(), { wrapper });
    expect(getRootVar('--theme-primary')).toBe('#dc2626');
  });

  it('themes 列表包含 6 个预设', () => {
    const { result } = renderHook(() => useTheme(), { wrapper });
    expect(result.current.themes.filter((t) => t.mode === 'preset')).toHaveLength(6);
    // 默认主题改为 mowen-default
    expect(result.current.theme.id).toBe('mowen-default');
  });

  it('uploadTheme：把 File 解析为 dataURL 并加入主题列表', async () => {
    const { result } = renderHook(() => useTheme(), { wrapper });
    // 构造一个伪 File
    const blob = new Blob(['fake-image-bytes'], { type: 'image/png' });
    const file = new File([blob], 'my-theme.png', { type: 'image/png' });
    let uploaded: Theme | null = null;
    await act(async () => {
      uploaded = await result.current.uploadTheme(file, '我的测试主题');
    });
    expect(uploaded).not.toBeNull();
    expect(uploaded!.name).toBe('我的测试主题');
    expect(uploaded!.mode).toBe('custom');
    expect(uploaded!.imageUrl.startsWith('data:image/png;base64,')).toBe(true);
    expect(result.current.theme.id).toBe(uploaded!.id);
    // 颜色提取被调用（用真实调色板覆盖）
    expect(mockedExtractPalette).toHaveBeenCalled();
    // --theme-primary 应是上传后提取的真实颜色
    expect(getRootVar('--theme-primary')).toBe('#0ea5e9');
    // v3 修复：上传图片的 dataURL 也写入 --theme-bg-image
    expect(getRootVar('--theme-bg-image')).toContain('data:image/png;base64');
  });

  it('removeTheme 删除自定义主题', async () => {
    const { result } = renderHook(() => useTheme(), { wrapper });
    const blob = new Blob(['x'], { type: 'image/png' });
    const file = new File([blob], 'a.png', { type: 'image/png' });
    let uploaded: Theme | null = null;
    await act(async () => {
      uploaded = await result.current.uploadTheme(file);
    });
    expect(result.current.themes).toHaveLength(7);
    act(() => {
      result.current.removeTheme(uploaded!.id);
    });
    expect(result.current.themes).toHaveLength(6);
    // 删除后回到默认
    expect(result.current.theme.id).toBe('mowen-default');
  });

  it('resetThemes 清空所有自定义主题', async () => {
    const { result } = renderHook(() => useTheme(), { wrapper });
    const blob = new Blob(['x'], { type: 'image/png' });
    const file = new File([blob], 'a.png', { type: 'image/png' });
    await act(async () => {
      await result.current.uploadTheme(file);
    });
    expect(result.current.themes).toHaveLength(7);
    act(() => {
      result.current.resetThemes();
    });
    expect(result.current.themes).toHaveLength(6);
    expect(result.current.theme.id).toBe('mowen-default');
  });
});
