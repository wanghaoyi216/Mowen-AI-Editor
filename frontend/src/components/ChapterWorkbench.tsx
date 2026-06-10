import { useEffect, useState } from "react";

import {
  designChapterTask,
  exportChapterAs,
  exportChapterHierarchy,
  fetchChapterVersions,
  fetchChapters,
  generateChapterDraftTask,
  reviseChapterDraftTask,
  runChapterConsistencyCheck,
} from "../lib/api";
import type { Chapter, ChapterPlan, ChapterVersion } from "../types";
import { MarkdownRenderer } from "./CommandCenter/MarkdownRenderer";
import { TaskRuntimePanel } from "./TaskRuntimePanel";
import { ExportMenu, type ExportActionOption } from "./ExportMenu";
import type { ChapterExportFormat } from "../lib/api";

const DEFAULT_GUIDANCE = "由 AI 根据项目设定、章节上下文和剧情复杂度自主规划章节设计。";
const DEFAULT_STYLE_HINT = "由 AI 根据项目 writing_style、tone 和已有章节自动选择叙事风格。";
const DEFAULT_REVISION_FOCUS = "由 AI 根据一致性报告、角色动机和世界规则自动决定修订重点。";

function buildComparisonPreview(currentDraft: string, previousContent: string) {
  const currentParts = currentDraft.split(/\n+/).filter(Boolean);
  const previousParts = previousContent.split(/\n+/).filter(Boolean);
  const changes: Array<{ kind: "changed" | "added" | "removed"; current?: string; previous?: string }> = [];
  const max = Math.max(currentParts.length, previousParts.length);

  for (let index = 0; index < max; index += 1) {
    const current = currentParts[index];
    const previous = previousParts[index];
    if (current && previous && current !== previous) {
      changes.push({ kind: "changed", current, previous });
    } else if (current && !previous) {
      changes.push({ kind: "added", current });
    } else if (!current && previous) {
      changes.push({ kind: "removed", previous });
    }
    if (changes.length >= 8) {
      break;
    }
  }

  return changes;
}

export function ChapterWorkbench({ projectId }: { projectId: number | null }) {
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [selectedChapterId, setSelectedChapterId] = useState<number | null>(null);
  const [chapterPlan, setChapterPlan] = useState<ChapterPlan | null>(null);
  const [chapterDraft, setChapterDraft] = useState<Chapter | null>(null);
  const [chapterVersions, setChapterVersions] = useState<ChapterVersion[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastTaskId, setLastTaskId] = useState<number | null>(null);
  const [consistencyReport, setConsistencyReport] = useState<string | null>(null);
  const [consistencyModel, setConsistencyModel] = useState<string | null>(null);
  const [rewriteModel, setRewriteModel] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportMessage, setExportMessage] = useState<string | null>(null);

  async function loadChapters() {
    if (!projectId) {
      setChapters([]);
      setSelectedChapterId(null);
      setChapterDraft(null);
      return;
    }
    const items = await fetchChapters(projectId);
    setChapters(items);
    if (!selectedChapterId && items.length > 0) {
      setSelectedChapterId(items[0].id);
      setChapterDraft(items[0]);
    } else if (selectedChapterId) {
      const current = items.find((item) => item.id === selectedChapterId) ?? null;
      setChapterDraft(current);
    }
  }

  async function loadVersions(chapterId: number) {
    if (!projectId) {
      setChapterVersions([]);
      setSelectedVersionId(null);
      return;
    }
    const items = await fetchChapterVersions(projectId, chapterId);
    setChapterVersions(items);
    if (items.length > 0 && !selectedVersionId) {
      setSelectedVersionId(items[0].id);
    } else if (selectedVersionId && !items.some((item) => item.id === selectedVersionId)) {
      setSelectedVersionId(items[0]?.id ?? null);
    }
  }

  useEffect(() => {
    void loadChapters().catch((loadError) => {
      setError(loadError instanceof Error ? loadError.message : "Unknown error");
    });
  }, [projectId]);

  useEffect(() => {
    if (!selectedChapterId) {
      setChapterVersions([]);
      setSelectedVersionId(null);
      return;
    }
    void loadVersions(selectedChapterId).catch((loadError) => {
      setError(loadError instanceof Error ? loadError.message : "Unknown error");
    });
  }, [projectId, selectedChapterId]);

  async function handleDesign() {
    if (!selectedChapterId || !projectId) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await designChapterTask(projectId, selectedChapterId, { guidance: DEFAULT_GUIDANCE });
      setLastTaskId(result.task_id);
      setChapterPlan(result.plan);
      await loadChapters();
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  async function handleGenerate() {
    if (!selectedChapterId || !projectId) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await generateChapterDraftTask(projectId, selectedChapterId, {
        styleHint: DEFAULT_STYLE_HINT,
        wordTarget: 1800,
      });
      setLastTaskId(result.task_id);
      setChapterDraft(result.chapter);
      await loadChapters();
      await loadVersions(selectedChapterId);
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  async function handleConsistencyCheck() {
    if (!selectedChapterId || !projectId) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await runChapterConsistencyCheck(projectId, selectedChapterId);
      setLastTaskId(result.task_id);
      setConsistencyModel(result.model);
      setConsistencyReport(result.report);
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  async function handleRevision() {
    if (!selectedChapterId || !projectId) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await reviseChapterDraftTask(projectId, selectedChapterId, {
        revisionFocus: DEFAULT_REVISION_FOCUS,
        styleHint: DEFAULT_STYLE_HINT,
        wordTarget: 1800,
      });
      setLastTaskId(result.task_id);
      setChapterDraft(result.chapter);
      setConsistencyReport(result.consistency_report);
      setConsistencyModel(result.consistency_model);
      setRewriteModel(result.rewrite_model);
      await loadChapters();
      await loadVersions(selectedChapterId);
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  // 章节导出选项：md / docx / pdf / txt
  const chapterExportOptions: ExportActionOption<ChapterExportFormat>[] = [
    { format: "md",   label: "Markdown (.md)",   description: "纯文本 + Markdown 标记，体积最小", default: true },
    { format: "docx", label: "Word 文档 (.docx)", description: "Microsoft Word 原生格式" },
    { format: "pdf",  label: "PDF 文档 (.pdf)",  description: "排版固定，跨平台阅读" },
    { format: "txt",  label: "纯文本 (.txt)",    description: "无任何格式标记" },
  ];

  // 整书导出选项：ZIP 层级
  const projectExportOptions: ExportActionOption<"zip">[] = [
    { format: "zip", label: "整书层级 ZIP", description: "按 项目/任务/章节/小节/内容.md 层级结构打包", default: true },
  ];

  async function handleExportChapter(fmt: ChapterExportFormat): Promise<{ blob: Blob; filename: string }> {
    if (!selectedChapterId || !projectId || !chapterDraft) {
      throw new Error("请先选择章节");
    }
    const blob = await exportChapterAs(projectId, selectedChapterId, fmt);
    const safeTitle = (chapterDraft.title || "未命名")
      .replace(/[<>:"/\\|?*]/g, "_")
      .trim() || "未命名";
    const filename = `第${chapterDraft.chapter_no.toString().padStart(2, "0")}章_${safeTitle}.${fmt}`;
    return { blob, filename };
  }

  async function handleExportProjectFiles(_fmt: "zip"): Promise<{ blob: Blob; filename: string }> {
    if (!projectId) throw new Error("请先选择项目");
    const result = await exportChapterHierarchy(projectId);
    return { blob: result.blob, filename: result.filename };
  }

  // 兼容旧 message 显示：现在改由 ExportMenu 内部反馈条控制
  // 这里保留导出 busy 状态以便按钮 disabled
  const anyExportBusy = exporting;


  const selectedVersion = chapterVersions.find((item) => item.id === selectedVersionId) ?? chapterVersions[0] ?? null;
  const comparisonRows =
    chapterDraft?.draft_content && selectedVersion
      ? buildComparisonPreview(chapterDraft.draft_content, selectedVersion.content)
      : [];

  return (
    <section className="panel-grid">
      <article className="panel">
        <div className="panel-header">
          <h2>章节工作台</h2>
          <span>OpenRouter Chapter Flow</span>
        </div>
        <div className="toolbar">
          <label className="field grow">
            <span>章节选择</span>
            <select
              value={selectedChapterId ?? ""}
              onChange={(event) => setSelectedChapterId(Number(event.target.value) || null)}
            >
              <option value="">请选择章节</option>
              {chapters.map((chapter) => (
                <option key={chapter.id} value={chapter.id}>
                  {chapter.chapter_no}. {chapter.title}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="readonly-grid">
          <div className="readonly-field">
            <span>章节生成策略</span>
            <strong>{DEFAULT_GUIDANCE}</strong>
          </div>
          <div className="readonly-field">
            <span>文风选择</span>
            <strong>{DEFAULT_STYLE_HINT}</strong>
          </div>
          <div className="readonly-field">
            <span>修订重点</span>
            <strong>{DEFAULT_REVISION_FOCUS}</strong>
          </div>
          <div className="readonly-field">
            <span>人类权限</span>
            <strong>仅观察与启动任务；章节大纲、正文和修订由 AI 自主决策。</strong>
          </div>
        </div>
        <div className="toolbar">
          <button type="button" onClick={() => void handleDesign()} disabled={busy || !selectedChapterId}>
            {busy ? "处理中..." : "生成章节设计"}
          </button>
          <button type="button" onClick={() => void handleGenerate()} disabled={busy || !selectedChapterId}>
            {busy ? "处理中..." : "生成章节草稿"}
          </button>
          <button type="button" onClick={() => void handleConsistencyCheck()} disabled={busy || !selectedChapterId}>
            {busy ? "处理中..." : "一致性检查"}
          </button>
          <button type="button" onClick={() => void handleRevision()} disabled={busy || !selectedChapterId}>
            {busy ? "处理中..." : "一致性修订"}
          </button>
          <ExportMenu<ChapterExportFormat>
            label="导出当前章节"
            options={chapterExportOptions}
            onExport={handleExportChapter}
            disabled={!selectedChapterId || !chapterDraft}
            busy={anyExportBusy}
          />
          <ExportMenu<"zip">
            label="导出整书"
            options={projectExportOptions}
            onExport={handleExportProjectFiles}
            disabled={!projectId}
            busy={anyExportBusy}
            placement="up-left"
          />
        </div>
        {error ? <p className="hero-copy">执行失败：{error}</p> : null}
        {exportMessage ? <p className="hero-copy">{exportMessage}</p> : null}
        {!projectId ? <p className="hero-copy">请先在仪表盘选择项目。</p> : null}
        <div className="graph-list">
          {lastTaskId ? (
            <div className="task-item">
              <div>
                <strong>最近章节任务</strong>
                <p>task_id: {lastTaskId}</p>
              </div>
              <span className="badge badge-进行中">task</span>
            </div>
          ) : null}
          {chapters.map((chapter) => (
            <div className="task-item" key={chapter.id}>
              <div>
                <strong>
                  {chapter.chapter_no}. {chapter.title}
                </strong>
                <p>
                  {chapter.status} / word_count: {chapter.word_count}
                </p>
              </div>
              <span className="badge badge-完成">v{chapter.version}</span>
            </div>
          ))}
        </div>
        {chapterVersions.length > 0 ? (
          <div className="graph-list">
            {chapterVersions.map((version) => (
              <button
                type="button"
                className={`task-item selectable-card${version.id === selectedVersionId ? " selected-card" : ""}`}
                key={version.id}
                onClick={() => setSelectedVersionId(version.id)}
              >
                <div>
                  <strong>
                    v{version.version_no} / {version.operation_type}
                  </strong>
                  <p>{version.selected_model ?? "unknown model"}</p>
                </div>
                <span className="badge badge-完成">history</span>
              </button>
            ))}
          </div>
        ) : null}
      </article>

      <article className="panel parchment">
        <div className="panel-header">
          <h2>设计与草稿</h2>
          <span>Plan + Draft + Diff</span>
        </div>
        {chapterPlan ? (
          <div className="chapter-card">
            <strong>{chapterPlan.title}</strong>
            <p>{chapterPlan.design_brief}</p>
            <p>{chapterPlan.beat_sheet}</p>
            <p>model: {chapterPlan.selected_model ?? "unknown"}</p>
          </div>
        ) : (
          <p className="hero-copy">还没有章节设计稿。先执行“生成章节设计”。</p>
        )}
        <div className="comparison-grid">
          <div className="chapter-card">
            <strong>当前草稿</strong>
            <MarkdownRenderer content={chapterDraft?.final_content || chapterDraft?.draft_content || "还没有章节草稿。"} maxHeight={520} />
          </div>
          <div className="chapter-card">
            <strong>历史版本</strong>
            <MarkdownRenderer content={selectedVersion?.content ?? "还没有可对比的历史版本。"} maxHeight={520} />
          </div>
        </div>
        {comparisonRows.length > 0 ? (
          <div className="chapter-card">
            <strong>版本差异预览</strong>
            <div className="diff-list">
              {comparisonRows.map((item, index) => (
                <div className={`diff-row diff-${item.kind}`} key={`${item.kind}-${index}`}>
                  <p>旧版本：{item.previous ?? "无"}</p>
                  <p>当前稿：{item.current ?? "无"}</p>
                </div>
              ))}
            </div>
          </div>
        ) : null}
        {consistencyReport ? (
          <div className="chapter-card">
            <strong>一致性检查报告</strong>
            <p>model: {consistencyModel ?? "unknown"}</p>
            {rewriteModel ? <p>rewrite: {rewriteModel}</p> : null}
            <MarkdownRenderer content={consistencyReport} maxHeight={360} />
          </div>
        ) : null}
      </article>

      {selectedChapterId ? <TaskRuntimePanel projectId={projectId} initialChapterId={selectedChapterId} initialTaskId={lastTaskId} /> : null}
    </section>
  );
}
