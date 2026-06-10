import { FormEvent, useEffect, useMemo, useState } from "react";

import { useProjectContext } from "../context/ProjectContext";
import { createProject, deleteProject, updateProject } from "../lib/api";
import type { ProjectCreatePayload } from "../types";

const emptyProjectForm: ProjectCreatePayload = {
  name: "",
  genre: "",
  theme: "",
  target_audience: "",
  writing_style: "",
  tone: "",
  summary: "",
  world_setting: "",
  status: "draft",
};

export function ProjectOverviewPanel() {
  const { projects, selectedProject, selectedProjectId, setSelectedProjectId, loading, error, reload } =
    useProjectContext();
  const [form, setForm] = useState<ProjectCreatePayload>(emptyProjectForm);
  const [editForm, setEditForm] = useState<ProjectCreatePayload>(emptyProjectForm);
  const [creating, setCreating] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [editError, setEditError] = useState<string | null>(null);

  const summary = useMemo(
    () => [
      { label: "项目总数", value: String(projects.length) },
      { label: "当前项目", value: selectedProject?.name ?? "未选择" },
      { label: "项目状态", value: selectedProject?.status ?? "unknown" },
    ],
    [projects.length, selectedProject?.name, selectedProject?.status],
  );

  useEffect(() => {
    if (!selectedProject) {
      setEditForm(emptyProjectForm);
      return;
    }
    setEditForm({
      name: selectedProject.name,
      genre: selectedProject.genre ?? "",
      theme: selectedProject.theme ?? "",
      target_audience: selectedProject.target_audience ?? "",
      writing_style: selectedProject.writing_style ?? "",
      tone: selectedProject.tone ?? "",
      summary: selectedProject.summary ?? "",
      world_setting: selectedProject.world_setting ?? "",
      status: selectedProject.status,
    });
  }, [selectedProject]);

  async function handleCreateProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = form.name.trim();
    if (!name) {
      setCreateError("项目名不能为空");
      return;
    }

    setCreating(true);
    setCreateError(null);
    try {
      const project = await createProject({
        name,
        genre: form.genre?.trim() || null,
        theme: form.theme?.trim() || null,
        target_audience: form.target_audience?.trim() || null,
        writing_style: form.writing_style?.trim() || null,
        tone: form.tone?.trim() || null,
        summary: form.summary?.trim() || null,
        world_setting: form.world_setting?.trim() || null,
        status: "draft",
      });
      setSelectedProjectId(project.id);
      setForm(emptyProjectForm);
      reload();
    } catch (submitError) {
      setCreateError(submitError instanceof Error ? submitError.message : "创建项目失败");
    } finally {
      setCreating(false);
    }
  }

  async function handleUpdateProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProjectId) {
      setEditError("请先选择项目");
      return;
    }
    const name = editForm.name.trim();
    if (!name) {
      setEditError("项目名不能为空");
      return;
    }

    setUpdating(true);
    setEditError(null);
    try {
      await updateProject(selectedProjectId, {
        name,
        genre: editForm.genre?.trim() || null,
        theme: editForm.theme?.trim() || null,
        target_audience: editForm.target_audience?.trim() || null,
        writing_style: editForm.writing_style?.trim() || null,
        tone: editForm.tone?.trim() || null,
        summary: editForm.summary?.trim() || null,
        world_setting: editForm.world_setting?.trim() || null,
        status: editForm.status?.trim() || "draft",
      });
      reload();
    } catch (submitError) {
      setEditError(submitError instanceof Error ? submitError.message : "更新项目失败");
    } finally {
      setUpdating(false);
    }
  }

  async function handleDeleteProject() {
    if (!selectedProjectId || deleting) {
      return;
    }
    const confirmed = window.confirm("确定删除当前项目及其关联数据吗？此操作无法撤销。");
    if (!confirmed) {
      return;
    }
    setDeleting(true);
    setEditError(null);
    try {
      await deleteProject(selectedProjectId);
      setSelectedProjectId(null);
      reload();
    } catch (deleteError) {
      setEditError(deleteError instanceof Error ? deleteError.message : "删除项目失败");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <>
      {/* C1.4 书架 hero section — 山水水墨画.png + 暗化渐变 + 浮动梅花 */}
      <section className="cc-bookshelf-hero" aria-label="书架头图">
        <div className="cc-bookshelf-hero-bg" aria-hidden="true">
          {/* 山水水墨画系统背景图 */}
          <div
            className="cc-bookshelf-hero-img"
            style={{ backgroundImage: "url('/decor/system-bg.png')" }}
          />
          {/* 极淡墨纹 SVG（feTurbulence 噪点 + multiply 混合） */}
          <svg className="cc-ink-noise" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
            <filter id="hero-ink-noise-filter">
              <feTurbulence type="fractalNoise" baseFrequency="0.65" numOctaves="3" seed="2"/>
              <feColorMatrix values="0 0 0 0 0.16  0 0 0 0 0.10  0 0 0 0 0.29  0 0 0 0.5 0"/>
            </filter>
            <rect width="100%" height="100%" filter="url(#hero-ink-noise-filter)" opacity="0.05"/>
          </svg>
          {/* 远山装饰（点缀层） */}
          <svg viewBox="0 0 1920 280" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <linearGradient id="hero-far" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#a78bfa" stop-opacity="0.22"/>
                <stop offset="100%" stop-color="#7c3aed" stop-opacity="0.35"/>
              </linearGradient>
              <linearGradient id="hero-near" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#6b3fa0" stop-opacity="0.32"/>
                <stop offset="100%" stop-color="#3a266b" stop-opacity="0.55"/>
              </linearGradient>
              <radialGradient id="hero-haze">
                <stop offset="0%" stop-color="#fff" stop-opacity="0.7"/>
                <stop offset="100%" stop-color="#fff" stop-opacity="0"/>
              </radialGradient>
            </defs>
            {/* 远山 */}
            <path d="M 0 180 L 250 130 L 500 160 L 800 110 L 1100 150 L 1400 120 L 1700 170 L 1920 140 L 1920 280 L 0 280 Z" fill="url(#hero-far)"/>
            {/* 近山 */}
            <path d="M 0 220 L 300 190 L 600 215 L 900 185 L 1200 210 L 1500 190 L 1920 215 L 1920 280 L 0 280 Z" fill="url(#hero-near)"/>
            {/* 云雾 */}
            <ellipse cx="400" cy="160" rx="220" ry="30" fill="url(#hero-haze)"/>
            <ellipse cx="1300" cy="120" rx="260" ry="32" fill="url(#hero-haze)"/>
            {/* 楼阁剪影 */}
            <g transform="translate(1500, 130)" fill="#3a266b" opacity="0.5">
              <rect x="0" y="20" width="60" height="50"/>
              <polygon points="-8,20 68,20 52,4 8,4"/>
              <rect x="15" y="-12" width="30" height="16"/>
              <polygon points="8,-12 52,-12 36,-26 24,-26"/>
            </g>
          </svg>
        </div>

        {/* 浮动梅花 5 朵 */}
        <span className="cc-bookshelf-plum" style={{ top: "30px",  left: "8%" }}  aria-hidden="true">
          <svg width="20" height="20" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
            <circle cx="10" cy="10" r="8" fill="#ec4899" opacity="0.75"/>
            <circle cx="10" cy="10" r="3" fill="#fce7f3"/>
          </svg>
        </span>
        <span className="cc-bookshelf-plum cc-plum-2" style={{ top: "80px",  left: "20%" }} aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
            <circle cx="10" cy="10" r="6" fill="#ec4899" opacity="0.7"/>
            <circle cx="10" cy="10" r="2" fill="#fce7f3"/>
          </svg>
        </span>
        <span className="cc-bookshelf-plum cc-plum-3" style={{ top: "60px",  right: "22%" }} aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
            <circle cx="10" cy="10" r="7" fill="#ec4899" opacity="0.7"/>
            <circle cx="10" cy="10" r="3" fill="#fce7f3"/>
          </svg>
        </span>
        <span className="cc-bookshelf-plum cc-plum-4" style={{ top: "140px", left: "32%" }} aria-hidden="true">
          <svg width="14" height="14" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
            <circle cx="10" cy="10" r="5" fill="#ec4899" opacity="0.65"/>
            <circle cx="10" cy="10" r="2" fill="#fce7f3"/>
          </svg>
        </span>
        <span className="cc-bookshelf-plum cc-plum-5" style={{ top: "110px", right: "10%" }} aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
            <circle cx="10" cy="10" r="6" fill="#ec4899" opacity="0.7"/>
            <circle cx="10" cy="10" r="2" fill="#fce7f3"/>
          </svg>
        </span>

        <div className="cc-bookshelf-hero-content">
          <div>
            <h1 className="cc-bookshelf-hero-title">我的书架</h1>
            <p className="cc-bookshelf-hero-subtitle">My Bookshelf · 收纳每一次灵感</p>
          </div>
        </div>
      </section>

      <article className="hero-card workbench-hero">
      <div className="hero-main">
        <p className="eyebrow">Project Control</p>
        <h1>小说项目工作台</h1>
        <p className="hero-copy">
          从创建项目开始，把题材、主题、世界设定和后续章节任务放到同一个业务入口里。
        </p>

        <div className="toolbar">
          <label className="field grow">
            <span>当前项目</span>
            <select
              value={selectedProjectId ?? ""}
              onChange={(event) => {
                const value = event.target.value;
                setSelectedProjectId(value ? Number(value) : null);
              }}
              disabled={loading || projects.length === 0}
            >
              {projects.length === 0 ? <option value="">暂无项目，请先创建</option> : null}
              {projects.map((project) => (
                <option value={project.id} key={project.id}>
                  #{project.id} · {project.name}
                </option>
              ))}
            </select>
          </label>
          <button type="button" onClick={reload} disabled={loading}>
            {loading ? "刷新中..." : "刷新项目"}
          </button>
        </div>

        {error ? <p className="alert-text">项目加载失败：{error}</p> : null}
        {selectedProject ? (
          <div className="project-brief">
            <strong>{selectedProject.name}</strong>
            <p>
              {selectedProject.genre ?? "未设定题材"} / {selectedProject.theme ?? "未设定主题"} /{" "}
              {selectedProject.target_audience ?? "未设定受众"}
            </p>
            <p>{selectedProject.summary ?? "暂无项目摘要，建议先补齐创作目标和主要卖点。"}</p>
          </div>
        ) : (
          <div className="project-brief empty-brief">
            <strong>还没有可用项目</strong>
            <p>创建第一个项目后，热点探索、角色图谱、剧情设计和章节工作台才有明确上下文。</p>
          </div>
        )}

        <div className="stat-row">
          {summary.map((item) => (
            <div className="stat-card" key={item.label}>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
        </div>

        {selectedProject ? (
          <form className="project-edit-form" onSubmit={(event) => void handleUpdateProject(event)}>
            <div className="panel-header">
              <h2>编辑项目</h2>
              <span>Update / Delete</span>
            </div>
            <label className="field">
              <span>项目名</span>
              <input
                value={editForm.name}
                onChange={(event) => setEditForm((value) => ({ ...value, name: event.target.value }))}
                maxLength={200}
                required
              />
            </label>
            <div className="form-grid">
              <label className="field">
                <span>题材</span>
                <input
                  value={editForm.genre ?? ""}
                  onChange={(event) => setEditForm((value) => ({ ...value, genre: event.target.value }))}
                  maxLength={100}
                />
              </label>
              <label className="field">
                <span>状态</span>
                <input
                  value={editForm.status ?? ""}
                  onChange={(event) => setEditForm((value) => ({ ...value, status: event.target.value }))}
                  maxLength={50}
                />
              </label>
            </div>
            <label className="field">
              <span>一句话摘要</span>
              <textarea
                value={editForm.summary ?? ""}
                onChange={(event) => setEditForm((value) => ({ ...value, summary: event.target.value }))}
                rows={3}
              />
            </label>
            <label className="field">
              <span>世界设定</span>
              <textarea
                value={editForm.world_setting ?? ""}
                onChange={(event) => setEditForm((value) => ({ ...value, world_setting: event.target.value }))}
                rows={3}
              />
            </label>
            {editError ? <p className="alert-text">{editError}</p> : null}
            <div className="toolbar">
              <button type="submit" disabled={updating || deleting}>
                {updating ? "保存中..." : "保存修改"}
              </button>
              <button type="button" className="danger-button" onClick={() => void handleDeleteProject()} disabled={deleting}>
                {deleting ? "删除中..." : "删除项目"}
              </button>
            </div>
          </form>
        ) : null}
      </div>

      <form className="project-form" onSubmit={(event) => void handleCreateProject(event)}>
        <div className="panel-header">
          <h2>创建项目</h2>
          <span>Project API</span>
        </div>
        <label className="field">
          <span>项目名</span>
          <input
            value={form.name}
            onChange={(event) => setForm((value) => ({ ...value, name: event.target.value }))}
            placeholder="例如：星港遗梦"
            maxLength={200}
            required
          />
        </label>
        <div className="form-grid">
          <label className="field">
            <span>题材</span>
            <input
              value={form.genre ?? ""}
              onChange={(event) => setForm((value) => ({ ...value, genre: event.target.value }))}
              placeholder="科幻 / 悬疑 / 都市"
              maxLength={100}
            />
          </label>
          <label className="field">
            <span>主题</span>
            <input
              value={form.theme ?? ""}
              onChange={(event) => setForm((value) => ({ ...value, theme: event.target.value }))}
              placeholder="成长、权力、救赎"
              maxLength={200}
            />
          </label>
        </div>
        <div className="form-grid">
          <label className="field">
            <span>目标读者</span>
            <input
              value={form.target_audience ?? ""}
              onChange={(event) => setForm((value) => ({ ...value, target_audience: event.target.value }))}
              placeholder="男频 / 女频 / 青年读者"
              maxLength={100}
            />
          </label>
          <label className="field">
            <span>文风</span>
            <input
              value={form.writing_style ?? ""}
              onChange={(event) => setForm((value) => ({ ...value, writing_style: event.target.value }))}
              placeholder="冷峻、轻松、群像"
              maxLength={100}
            />
          </label>
        </div>
        <label className="field">
          <span>一句话摘要</span>
          <textarea
            value={form.summary ?? ""}
            onChange={(event) => setForm((value) => ({ ...value, summary: event.target.value }))}
            placeholder="主角、核心冲突、故事承诺"
            rows={3}
          />
        </label>
        <label className="field">
          <span>世界设定</span>
          <textarea
            value={form.world_setting ?? ""}
            onChange={(event) => setForm((value) => ({ ...value, world_setting: event.target.value }))}
            placeholder="时代、地点、规则、关键势力"
            rows={3}
          />
        </label>
        {createError ? <p className="alert-text">{createError}</p> : null}
        <button type="submit" disabled={creating}>
          {creating ? "创建中..." : "创建并进入项目"}
        </button>
      </form>
    </article>
    </>
  );
}
