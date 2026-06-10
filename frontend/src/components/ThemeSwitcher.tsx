/**
 * 主题切换面板
 * --------------------------------------------------------------
 * · 缩略图网格：展示 6 张预设 + 用户上传主题
 * · 选中态：金色描边 + 缩放
 * · 上传按钮：点击触发 <input type="file" accept="image/*">
 * · 自定义主题：可删除（悬停显示 ✕）
 * · 重置按钮：清空所有自定义主题
 */
import { useRef, useState, type ChangeEvent } from 'react';
import { Palette, Upload, X, RotateCcw, Loader2, ImagePlus } from 'lucide-react';
import { useTheme, type Theme } from '../contexts/ThemeContext';
import './ThemeSwitcher.css';

export function ThemeSwitcher() {
  const { theme, themes, setTheme, uploadTheme, removeTheme, resetThemes, analyzing } = useTheme();
  const [open, setOpen] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // 点击外部关闭
  function handleBackdropClick(e: React.MouseEvent) {
    if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
      setOpen(false);
    }
  }

  async function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ''; // 允许重复选择同一文件
    if (!file) return;
    setUploadError(null);
    try {
      await uploadTheme(file);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : '上传失败');
    }
  }

  return (
    <div className="cc-theme-switcher" ref={containerRef} onClick={handleBackdropClick}>
      <button
        type="button"
        className="cc-theme-switcher-trigger cc-btn cc-btn-ghost"
        onClick={() => setOpen((v) => !v)}
        title="切换主题"
        aria-label="切换主题"
      >
        <Palette size={15} />
        <span className="cc-theme-switcher-trigger-text">主题</span>
        <span
          className="cc-theme-switcher-dot"
          style={{ background: theme.palette.primary }}
          aria-hidden
        />
      </button>

      {open && (
        <div className="cc-theme-panel" role="dialog" aria-label="主题切换">
          <div className="cc-theme-panel-header">
            <div className="cc-theme-panel-title">
              <Palette size={16} />
              主题风格
            </div>
            <button
              type="button"
              className="cc-theme-panel-reset"
              onClick={() => {
                if (window.confirm('确定要清除所有自定义主题吗？')) {
                  resetThemes();
                }
              }}
              title="清除所有自定义主题"
            >
              <RotateCcw size={12} />
              重置
            </button>
          </div>

          <div className="cc-theme-panel-subtitle">
            选择一张水墨背景图作为主题，前端会自动分析图片主色并应用到按钮 / 边框。
          </div>

          <div className="cc-theme-grid">
            {themes.map((t) => (
              <ThemeCard
                key={t.id}
                theme={t}
                selected={t.id === theme.id}
                onSelect={() => setTheme(t.id)}
                onRemove={t.mode === 'custom' ? () => removeTheme(t.id) : undefined}
              />
            ))}

            {/* 上传按钮 */}
            <button
              type="button"
              className="cc-theme-card cc-theme-upload-card"
              onClick={() => fileRef.current?.click()}
              disabled={analyzing}
            >
              {analyzing ? <Loader2 size={24} className="cc-spin" /> : <ImagePlus size={24} />}
              <span className="cc-theme-upload-label">
                {analyzing ? '分析中…' : '上传我的背景'}
              </span>
              <span className="cc-theme-upload-hint">jpg / png / webp</span>
            </button>
          </div>

          {uploadError && (
            <div className="cc-theme-error" role="alert">
              ⚠ {uploadError}
            </div>
          )}

          <div className="cc-theme-panel-footer">
            <span>当前：</span>
            <strong>{theme.name}</strong>
            <span
              className="cc-theme-color-strip"
              style={{ background: `linear-gradient(90deg, ${theme.palette.colors.join(', ')})` }}
              title={theme.palette.colors.join(' · ')}
            />
          </div>

          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            onChange={handleFileChange}
            style={{ display: 'none' }}
          />
        </div>
      )}
    </div>
  );
}

function ThemeCard({
  theme,
  selected,
  onSelect,
  onRemove,
}: {
  theme: Theme;
  selected: boolean;
  onSelect: () => void;
  onRemove?: () => void;
}) {
  return (
    <div
      className={`cc-theme-card ${selected ? 'is-selected' : ''}`}
      onClick={onSelect}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect();
        }
      }}
    >
      <div
        className="cc-theme-card-bg"
        style={{ backgroundImage: `url("${theme.imageUrl}")` }}
      >
        <div
          className="cc-theme-card-overlay"
          style={{
            background: `linear-gradient(180deg, ${theme.palette.primarySoft} 0%, ${theme.palette.primarySoft} 100%)`,
          }}
        />
        {selected && (
          <div className="cc-theme-card-check" style={{ background: theme.palette.primary }}>
            ✓
          </div>
        )}
        {onRemove && (
          <button
            type="button"
            className="cc-theme-card-remove"
            onClick={(e) => {
              e.stopPropagation();
              onRemove();
            }}
            title="删除此自定义主题"
            aria-label="删除此自定义主题"
          >
            <X size={12} />
          </button>
        )}
      </div>
      <div className="cc-theme-card-name" title={theme.name}>
        {theme.name}
      </div>
      <div className="cc-theme-card-colorbar">
        {theme.palette.colors.slice(0, 4).map((c, i) => (
          <span key={i} style={{ background: c }} title={c} />
        ))}
      </div>
    </div>
  );
}
