import { useState, useCallback } from 'react';
import { X, BookOpen, Tag, Hash, Settings, Zap, FileText } from 'lucide-react';
import { colors, spacing, borderRadius } from './styles';

type ModalCreateProjectProps = {
  visible: boolean;
  onClose: () => void;
  onCreate: (payload: Record<string, unknown>) => void;
};

const genreOptions = ['玄幻', '都市', '科幻', '悬疑', '奇幻', '历史', '武侠', '言情', '其他'];
const styleOptions = ['网文爽文', '严肃文学', '轻小说', '悬疑推理', '硬核科幻', '古风权谋', '黑暗致郁', '热血少年'];
const toneOptions = ['热血', '轻松搞笑', '虐心', '黑暗', '治愈', '悬疑紧张', '史诗厚重'];
const audienceOptions = ['全年龄', '男性向', '女性向', '青少年', '成人向'];

export function ModalCreateProject({ visible, onClose, onCreate }: ModalCreateProjectProps) {
  const [name, setName] = useState('');
  const [genre, setGenre] = useState('');
  const [theme, setTheme] = useState('');
  const [writingStyle, setWritingStyle] = useState('');
  const [tone, setTone] = useState('');
  const [targetAudience, setTargetAudience] = useState('全年龄');
  const [targetChapters, setTargetChapters] = useState(20);
  const [minWords, setMinWords] = useState(2000);
  const [maxWords, setMaxWords] = useState(4000);
  const [mode, setMode] = useState<'auto' | 'confirm'>('auto');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleBackdropClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (e.target === e.currentTarget) onClose();
    },
    [onClose],
  );

  function handleCancel() {
    setName('');
    setGenre('');
    setTheme('');
    setWritingStyle('');
    setTone('');
    setTargetAudience('全年龄');
    setTargetChapters(20);
    setMinWords(2000);
    setMaxWords(4000);
    setMode('auto');
    setNotes('');
    setError(null);
    onClose();
  }

  function handleCreate() {
    if (!name.trim()) {
      setError('项目名称不能为空');
      return;
    }
    if (minWords > maxWords) {
      setError('每章最少字数不能大于最多字数');
      return;
    }
    onCreate({
      name: name.trim(),
      genre: genre || null,
      theme: theme.trim() || null,
      writing_style: writingStyle || null,
      tone: tone || null,
      target_audience: targetAudience || null,
      target_chapters: targetChapters,
      min_words_per_chapter: minWords,
      max_words_per_chapter: maxWords,
      mode,
      notes: notes.trim() || null,
    });
    handleCancel();
  }

  if (!visible) return null;

  return (
    <div className="cc-modal-backdrop" onClick={handleBackdropClick}>
      <div className="cc-modal">
        <div className="cc-modal-header">
          <div className="cc-modal-title">
            <BookOpen size={18} color={colors.accent} />
            <h3>新建创作项目</h3>
          </div>
          <button type="button" className="cc-btn cc-btn-close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="cc-modal-body">
          <div className="cc-form-group">
            <label className="cc-label">
              <Tag size={13} />
              项目名称
              <span className="cc-required">*</span>
            </label>
            <input
              type="text"
              placeholder="为你的小说项目起个名字"
              value={name}
              onChange={(e) => { setName(e.target.value); setError(null); }}
              maxLength={100}
            />
          </div>

          <div className="cc-form-grid">
            <div className="cc-form-group">
              <label className="cc-label">
                <Settings size={13} />
                小说风格
              </label>
              <select value={genre} onChange={(e) => setGenre(e.target.value)}>
                <option value="">选择风格</option>
                {genreOptions.map((g) => (
                  <option key={g} value={g}>{g}</option>
                ))}
              </select>
            </div>

            <div className="cc-form-group">
              <label className="cc-label">
                <Hash size={13} />
                目标章节数
              </label>
              <input
                type="number"
                min={1}
                max={1000}
                value={targetChapters}
                onChange={(e) => setTargetChapters(Number(e.target.value))}
              />
            </div>
          </div>

          <div className="cc-form-group">
            <label className="cc-label">
              <FileText size={13} />
              主题关键词
            </label>
            <input
              type="text"
              placeholder="例如：成长、权力、救赎"
              value={theme}
              onChange={(e) => setTheme(e.target.value)}
              maxLength={200}
            />
          </div>

          <div className="cc-form-grid">
            <div className="cc-form-group">
              <label className="cc-label">
                <Settings size={13} />
                作品风格
              </label>
              <select value={writingStyle} onChange={(e) => setWritingStyle(e.target.value)}>
                <option value="">选择风格</option>
                {styleOptions.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>

            <div className="cc-form-group">
              <label className="cc-label">
                <Zap size={13} />
                情感基调
              </label>
              <select value={tone} onChange={(e) => setTone(e.target.value)}>
                <option value="">选择基调</option>
                {toneOptions.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="cc-form-group">
            <label className="cc-label">
              <Settings size={13} />
              目标读者
            </label>
            <select value={targetAudience} onChange={(e) => setTargetAudience(e.target.value)}>
              {audienceOptions.map((a) => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
          </div>

          <div className="cc-form-grid">
            <div className="cc-form-group">
              <label className="cc-label">
                <Hash size={13} />
                每章最少字数
              </label>
              <input
                type="number"
                min={200}
                max={50000}
                step={100}
                value={minWords}
                onChange={(e) => setMinWords(Number(e.target.value))}
              />
            </div>

            <div className="cc-form-group">
              <label className="cc-label">
                <Hash size={13} />
                每章最多字数
              </label>
              <input
                type="number"
                min={200}
                max={50000}
                step={100}
                value={maxWords}
                onChange={(e) => setMaxWords(Number(e.target.value))}
              />
            </div>
          </div>
          <div style={{ fontSize: 12, color: colors.textSecondary, marginTop: -4, marginBottom: 8 }}>
            AI 将严格把每章字数控制在 {minWords}–{maxWords} 字区间内，不足会自动续写补足。
          </div>

          <div className="cc-form-group">
            <label className="cc-label">
              <Zap size={13} />
              运行模式
            </label>
            <div className="cc-radio-group">
              <label className="cc-radio">
                <input
                  type="radio"
                  name="mode"
                  checked={mode === 'auto'}
                  onChange={() => setMode('auto')}
                />
                <span>全自动模式</span>
                <small>AI 自动执行所有流程</small>
              </label>
              <label className="cc-radio">
                <input
                  type="radio"
                  name="mode"
                  checked={mode === 'confirm'}
                  onChange={() => setMode('confirm')}
                />
                <span>多阶段确认</span>
                <small>关键阶段需人工确认</small>
              </label>
            </div>
          </div>

          {/* 原"内容导出位置"输入框已移除：现在导出时由用户在原生"另存为"
              对话框里**即时**选择保存位置，不再需要提前在创建项目时规划路径。 */}

          <div className="cc-form-group">
            <label className="cc-label">
              <FileText size={13} />
              附加说明
              <span className="cc-optional">(可选)</span>
            </label>
            <textarea
              placeholder="补充你的创作偏好、特殊要求或世界观设定..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
            />
          </div>

          {error && <p className="cc-error">{error}</p>}
        </div>

        <div className="cc-modal-footer">
          <button type="button" className="cc-btn cc-btn-ghost" onClick={handleCancel}>
            取消
          </button>
          <button type="button" className="cc-btn cc-btn-primary" onClick={handleCreate}>
            确认创建
          </button>
        </div>
      </div>
    </div>
  );
}
