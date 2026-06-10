// frontend/src/components/ExportMenu.tsx
// -------------------------------------------------------------------------
// 统一"导出"弹出菜单。点按钮 → 弹菜单 → 选格式/选项 → 走原生"另存为"。
// -------------------------------------------------------------------------
import React, { useEffect, useRef, useState } from "react";
import { Download, ChevronDown, Check, FileText, FileType2, FileCode, Archive, Loader2 } from "lucide-react";
import { colors } from "./CommandCenter/styles";
import { hasNativeSaveDialog } from "../lib/filePicker";

export type ExportFormat = "md" | "docx" | "pdf" | "txt" | "zip" | "json";

export interface ExportFormatOption<F extends ExportFormat = ExportFormat> {
  format: F;
  label: string;
  description?: string;
  Icon?: React.ComponentType<{ size?: number; className?: string }>;
}

export interface ExportActionOption<F extends ExportFormat = ExportFormat> extends ExportFormatOption<F> {
  /** 默认推荐/自动选中 */
  default?: boolean;
}

export interface ExportMenuProps<F extends ExportFormat = ExportFormat> {
  /** 触发按钮文案（带下拉箭头） */
  label?: string;
  /** 备选格式 / 动作列表 */
  options: ExportActionOption<F>[];
  /** 用户点某项时触发；返回 Blob 由本组件写入用户选择的位置 */
  onExport: (format: F) => Promise<{ blob: Blob; filename: string }>;
  /** 触发按钮 disabled 状态 */
  disabled?: boolean;
  /** 任意导出进行中（覆盖所有选项） */
  busy?: boolean;
  /** 自定义按钮 className */
  buttonClassName?: string;
  /** 自定义菜单位置：'down-left' (默认) / 'down-right' / 'up-left' / 'up-right' */
  placement?: "down-left" | "down-right" | "up-left" | "up-right";
  /** 暴露给父组件的"打开/关闭"事件，用于 Tooltip 同步 */
  onOpenChange?: (open: boolean) => void;
}

const DEFAULT_ICONS: Record<ExportFormat, React.ComponentType<{ size?: number; className?: string }>> = {
  md: FileText,
  txt: FileText,
  docx: FileType2,
  pdf: FileType2,
  zip: Archive,
  json: FileCode,
};

export function ExportMenu<F extends ExportFormat = ExportFormat>({
  label = "导出",
  options,
  onExport,
  disabled = false,
  busy = false,
  buttonClassName,
  placement = "down-left",
  onOpenChange,
}: ExportMenuProps<F>) {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<F>(
    (options.find((o) => o.default)?.format ?? options[0]?.format) as F,
  );
  const [running, setRunning] = useState<F | null>(null);
  const [feedback, setFeedback] = useState<{ kind: "ok" | "err" | "info"; text: string } | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // 外部点击关闭
  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (!rootRef.current) return;
      if (!rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onEsc(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  useEffect(() => {
    onOpenChange?.(open);
  }, [open, onOpenChange]);

  // 反馈 3s 后自动消失
  useEffect(() => {
    if (!feedback) return;
    const t = setTimeout(() => setFeedback(null), 3000);
    return () => clearTimeout(t);
  }, [feedback]);

  async function handleConfirm() {
    if (disabled || busy) return;
    if (running) return;
    setRunning(selected);
    setFeedback({ kind: "info", text: "正在准备文件…" });
    try {
      const { blob, filename } = await onExport(selected);
      // 直接走 filePicker，让用户挑位置
      const { saveBlobAs, makeAcceptTypes } = await import("../lib/filePicker");
      const result = await saveBlobAs(blob, {
        suggestedName: filename,
        types: makeAcceptTypes(filename),
      });
      if (result.cancelled) {
        setFeedback({ kind: "info", text: "已取消保存" });
      } else if (result.mode === "native") {
        setFeedback({ kind: "ok", text: `已保存为：${result.filename}` });
      } else {
        setFeedback({ kind: "ok", text: "已下载到默认下载目录" });
      }
    } catch (err) {
      console.error("[ExportMenu] 导出失败:", err);
      setFeedback({ kind: "err", text: `导出失败：${(err as Error).message}` });
    } finally {
      setRunning(null);
    }
  }

  const nativeSupported = hasNativeSaveDialog();
  const placementClass = `em-placement-${placement}`;

  return (
    <div ref={rootRef} className="export-menu-root" data-open={open ? "1" : "0"}>
      <button
        type="button"
        className={buttonClassName ?? "export-menu-trigger"}
        onClick={() => !disabled && !busy && setOpen((v) => !v)}
        disabled={disabled || busy}
        aria-haspopup="menu"
        aria-expanded={open}
        title={nativeSupported ? "点击选择导出格式与位置" : "点击选择导出格式（浏览器不支持原生保存对话框，将下载到默认目录）"}
      >
        {busy || running ? <Loader2 size={14} className="spin" /> : <Download size={14} />}
        <span>{label}</span>
        <ChevronDown size={12} />
      </button>

      {open && (
        <div ref={menuRef} className={`export-menu-popover ${placementClass}`} role="menu">
          <div className="em-header">
            <span className="em-title">选择导出格式</span>
            <span className="em-hint">
              {nativeSupported ? "确认后将弹出保存对话框" : "将下载到浏览器默认下载目录"}
            </span>
          </div>
          <ul className="em-list" role="none">
            {options.map((opt) => {
              const Icon = opt.Icon ?? DEFAULT_ICONS[opt.format] ?? FileText;
              const isSelected = selected === opt.format;
              return (
                <li key={opt.format}>
                  <button
                    type="button"
                    role="menuitemradio"
                    aria-checked={isSelected}
                    className={`em-item ${isSelected ? "is-selected" : ""}`}
                    onClick={() => setSelected(opt.format)}
                    disabled={!!running}
                  >
                    <span className="em-item-icon"><Icon size={16} /></span>
                    <span className="em-item-body">
                      <span className="em-item-label">{opt.label}</span>
                      {opt.description && <span className="em-item-desc">{opt.description}</span>}
                    </span>
                    {isSelected && <Check size={14} className="em-item-check" />}
                  </button>
                </li>
              );
            })}
          </ul>
          <div className="em-footer">
            <button
              type="button"
              className="em-confirm"
              onClick={() => void handleConfirm()}
              disabled={!!running}
            >
              {running ? (
                <>
                  <Loader2 size={14} className="spin" /> 导出中…
                </>
              ) : (
                <>
                  <Download size={14} /> 保存到…
                </>
              )}
            </button>
          </div>
          {feedback && (
            <div className={`em-feedback em-feedback-${feedback.kind}`}>{feedback.text}</div>
          )}
        </div>
      )}

      {!open && feedback && (
        <div className={`export-menu-toast em-feedback-${feedback.kind}`}>{feedback.text}</div>
      )}
    </div>
  );
}

// 兜底样式（项目没有全局 CSS，就地注入）
// 由于 React 组件不便直接注入 <style>，这里把样式以全局样式表方式 export，
// 由 main.tsx / index.css 引入即可。
export const EXPORT_MENU_CSS = `
.export-menu-root {
  position: relative;
  display: inline-block;
}
.export-menu-trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid ${colors.border};
  background: ${colors.cardBackground};
  color: ${colors.text};
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, transform 0.05s;
}
.export-menu-trigger:hover:not(:disabled) {
  background: ${colors.cardBackgroundHover};
  border-color: ${colors.accent};
}
.export-menu-trigger:active:not(:disabled) {
  transform: translateY(1px);
}
.export-menu-trigger:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.export-menu-popover {
  position: absolute;
  z-index: 1000;
  min-width: 240px;
  background: #ffffff;
  border: 1px solid ${colors.border};
  border-radius: 10px;
  box-shadow: 0 10px 30px rgba(58, 38, 107, 0.18);
  padding: 8px 0 4px;
  color: ${colors.text};
  font-size: 13px;
  animation: em-fade-in 0.12s ease-out;
}
.em-placement-down-left { top: calc(100% + 6px); left: 0; }
.em-placement-down-right { top: calc(100% + 6px); right: 0; }
.em-placement-up-left { bottom: calc(100% + 6px); left: 0; }
.em-placement-up-right { bottom: calc(100% + 6px); right: 0; }
@keyframes em-fade-in {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}
.em-header {
  padding: 6px 14px 8px;
  border-bottom: 1px solid ${colors.border};
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.em-title { font-weight: 600; color: ${colors.text}; }
.em-hint { font-size: 11px; color: ${colors.textSecondary}; }
.em-list {
  list-style: none;
  margin: 4px 0;
  padding: 0;
  max-height: 280px;
  overflow-y: auto;
}
.em-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  background: transparent;
  border: 0;
  cursor: pointer;
  text-align: left;
  color: ${colors.text};
}
.em-item:hover:not(:disabled) { background: rgba(124, 58, 237, 0.06); }
.em-item.is-selected { background: rgba(124, 58, 237, 0.10); }
.em-item:disabled { opacity: 0.5; cursor: not-allowed; }
.em-item-icon {
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  background: rgba(124, 58, 237, 0.10);
  color: ${colors.accent};
  flex-shrink: 0;
}
.em-item-body { flex: 1; display: flex; flex-direction: column; gap: 1px; }
.em-item-label { font-size: 13px; font-weight: 500; }
.em-item-desc  { font-size: 11px; color: ${colors.textSecondary}; }
.em-item-check { color: ${colors.accent}; flex-shrink: 0; }
.em-footer {
  border-top: 1px solid ${colors.border};
  padding: 8px 10px 6px;
  display: flex;
  justify-content: stretch;
}
.em-confirm {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 7px 12px;
  border-radius: 7px;
  border: 0;
  background: ${colors.accent};
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.12s;
}
.em-confirm:hover:not(:disabled) { background: #6d28d9; }
.em-confirm:disabled { opacity: 0.6; cursor: not-allowed; }
.em-feedback {
  margin: 0 10px 6px;
  padding: 6px 8px;
  border-radius: 6px;
  font-size: 11px;
  line-height: 1.4;
}
.em-feedback-ok   { background: rgba(5, 150, 105, 0.12); color: #047857; }
.em-feedback-err  { background: rgba(220, 38, 38, 0.12); color: #b91c1c; }
.em-feedback-info { background: rgba(124, 58, 237, 0.10); color: ${colors.textSecondary}; }
.export-menu-toast {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 11px;
  white-space: nowrap;
  box-shadow: 0 4px 12px rgba(58, 38, 107, 0.15);
  z-index: 999;
}
.spin { animation: em-spin 0.8s linear infinite; }
@keyframes em-spin { to { transform: rotate(360deg); } }
`;
