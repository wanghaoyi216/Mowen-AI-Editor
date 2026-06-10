// frontend/src/hooks/useResizableLayout.ts
import { useState, useCallback, useEffect } from 'react';

const STORAGE_KEY = 'cc.layout.v1';

interface PersistedLayout {
  leftWidth: number;     // 240 - 400
  centerWidth: number;   // 400 - 1200
  rightWidth: number;    // 400 - 1200
}

const DEFAULTS: PersistedLayout = {
  leftWidth: 260,
  centerWidth: 720,
  rightWidth: 560,
};

const MIN = { left: 200, center: 360, right: 360 };
const MAX = { left: 420, center: 1200, right: 1400 };

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function load(): PersistedLayout {
  if (typeof window === 'undefined') return DEFAULTS;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    const parsed = JSON.parse(raw) as Partial<PersistedLayout>;
    return {
      leftWidth: clamp(parsed.leftWidth ?? DEFAULTS.leftWidth, MIN.left, MAX.left),
      centerWidth: clamp(parsed.centerWidth ?? DEFAULTS.centerWidth, MIN.center, MAX.center),
      rightWidth: clamp(parsed.rightWidth ?? DEFAULTS.rightWidth, MIN.right, MAX.right),
    };
  } catch {
    return DEFAULTS;
  }
}

export interface UseResizableLayoutApi {
  leftWidth: number;
  centerWidth: number;
  rightWidth: number;
  /** 拖左侧分隔条 (chat sidebar <-> center) */
  onResizeLeft: (delta: number) => void;
  /** 拖右侧分隔条 (center <-> visualization) */
  onResizeRight: (delta: number) => void;
  /** 双重置 */
  reset: () => void;
}

export function useResizableLayout(): UseResizableLayoutApi {
  const [layout, setLayout] = useState<PersistedLayout>(load);

  // 持久化
  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(layout));
    } catch {
      // ignore quota errors
    }
  }, [layout]);

  const onResizeLeft = useCallback((delta: number) => {
    setLayout((prev) => {
      const newLeft = clamp(prev.leftWidth + delta, MIN.left, MAX.left);
      // 左侧增加多少，中间就减少多少（保持总宽不变）
      const actualDelta = newLeft - prev.leftWidth;
      const newCenter = clamp(prev.centerWidth - actualDelta, MIN.center, MAX.center);
      return { ...prev, leftWidth: newLeft, centerWidth: newCenter };
    });
  }, []);

  const onResizeRight = useCallback((delta: number) => {
    setLayout((prev) => {
      // 右侧拖动条语义：拖右 = 中间变宽，右栏变窄（向鼠标方向收）
      const newRight = clamp(prev.rightWidth - delta, MIN.right, MAX.right);
      const actualDelta = prev.rightWidth - newRight; // 实际改变量（带符号）
      const newCenter = clamp(prev.centerWidth + actualDelta, MIN.center, MAX.center);
      return { ...prev, rightWidth: newRight, centerWidth: newCenter };
    });
  }, []);

  const reset = useCallback(() => {
    setLayout(DEFAULTS);
  }, []);

  return {
    leftWidth: layout.leftWidth,
    centerWidth: layout.centerWidth,
    rightWidth: layout.rightWidth,
    onResizeLeft,
    onResizeRight,
    reset,
  };
}
