// frontend/src/components/CommandCenter/ResizableSplitter.tsx
import { useCallback, useEffect, useRef, useState } from 'react';
import './ResizableSplitter.css';

interface ResizableSplitterProps {
  /** 拖动时的回调，参数为累计像素 delta（向右为正） */
  onDrag: (delta: number) => void;
  /** 鼠标按下事件回调，可选，用于在拖动时禁用文本选择 */
  onDragStart?: () => void;
  onDragEnd?: () => void;
  /** ARIA label */
  ariaLabel?: string;
}

export function ResizableSplitter({
  onDrag,
  onDragStart,
  onDragEnd,
  ariaLabel = '拖动调整列宽',
}: ResizableSplitterProps) {
  const startXRef = useRef<number>(0);
  const lastDeltaRef = useRef<number>(0);
  const [isDragging, setIsDragging] = useState(false);

  const handlePointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.currentTarget.setPointerCapture(e.pointerId);
      startXRef.current = e.clientX;
      lastDeltaRef.current = 0;
      setIsDragging(true);
      onDragStart?.();
    },
    [onDragStart]
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!isDragging) return;
      const delta = e.clientX - startXRef.current;
      const incremental = delta - lastDeltaRef.current;
      lastDeltaRef.current = delta;
      onDrag(incremental);
    },
    [isDragging, onDrag]
  );

  const stopDrag = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!isDragging) return;
      e.currentTarget.releasePointerCapture(e.pointerId);
      setIsDragging(false);
      lastDeltaRef.current = 0;
      onDragEnd?.();
    },
    [isDragging, onDragEnd]
  );

  useEffect(() => {
    if (!isDragging) return;
    const handleGlobalPointerUp = () => setIsDragging(false);
    window.addEventListener('pointerup', handleGlobalPointerUp);
    return () => window.removeEventListener('pointerup', handleGlobalPointerUp);
  }, [isDragging]);

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={ariaLabel}
      className={`cc-splitter ${isDragging ? 'cc-splitter-active' : ''}`}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={stopDrag}
      onPointerCancel={stopDrag}
    >
      <span className="cc-splitter-grip" />
    </div>
  );
}
