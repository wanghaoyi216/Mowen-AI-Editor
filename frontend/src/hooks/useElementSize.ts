// frontend/src/hooks/useElementSize.ts
// 采用 callback-ref 模式：当 ref.current 指向的 DOM 节点切换时
// （例如 React 在不同 return 分支里替换元素），ResizeObserver 会自动
// 重新订阅到新节点，避免"容器已换但观察的是旧节点 → size 永远 0"。
import { useCallback, useState, useLayoutEffect, useRef, type RefCallback } from 'react';

export interface Size {
  width: number;
  height: number;
}

export function useElementSize<T extends HTMLElement = HTMLElement>(): [
  Size,
  RefCallback<T | null>,
] {
  const [size, setSize] = useState<Size>({ width: 0, height: 0 });
  const roRef = useRef<ResizeObserver | null>(null);
  const timersRef = useRef<number[]>([]);
  const lastElRef = useRef<T | null>(null);

  const ensureObserver = useCallback(() => {
    if (roRef.current) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        setSize((prev) =>
          prev.width === width && prev.height === height
            ? prev
            : { width, height }
        );
      }
    });
    roRef.current = ro;
  }, []);

  const measure = useCallback((el: T) => {
    const rect = el.getBoundingClientRect();
    setSize((prev) =>
      prev.width === rect.width && prev.height === rect.height
        ? prev
        : { width: rect.width, height: rect.height }
    );
  }, []);

  // callback ref：每当 DOM 节点变化（挂载 / 替换）时调用
  const setRef: RefCallback<T | null> = useCallback(
    (el: T | null) => {
      // 清掉旧的订阅与兜底计时器
      if (lastElRef.current && roRef.current) {
        try { roRef.current.unobserve(lastElRef.current); } catch { /* ignore */ }
      }
      timersRef.current.forEach((t) => window.clearTimeout(t));
      timersRef.current = [];
      lastElRef.current = el;

      if (!el) return;
      ensureObserver();

      // 首次同步：立刻测量（避免 layout 已完成但 RO 还没回调）
      measure(el);
      roRef.current?.observe(el);

      // 双兜底：某些浏览器在 tab 隐藏 / 折叠侧边栏后 RO 首次回调延迟。
      // 挂载后 100ms / 300ms 主动重测，尽早把 0 尺寸纠正为真实尺寸。
      const t1 = window.setTimeout(() => { if (lastElRef.current) measure(lastElRef.current); }, 100);
      const t2 = window.setTimeout(() => { if (lastElRef.current) measure(lastElRef.current); }, 300);
      timersRef.current = [t1, t2];
    },
    [ensureObserver, measure],
  );

  // 组件卸载时释放
  useLayoutEffect(() => {
    return () => {
      timersRef.current.forEach((t) => window.clearTimeout(t));
      timersRef.current = [];
      if (roRef.current) {
        roRef.current.disconnect();
        roRef.current = null;
      }
      lastElRef.current = null;
    };
  }, []);

  return [size, setRef];
}
