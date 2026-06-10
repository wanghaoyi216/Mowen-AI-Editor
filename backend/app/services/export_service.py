from __future__ import annotations

import json
import re
import shutil
import zipfile
from base64 import b64decode
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_task import AITask, TaskStep
from app.models.chapter import Chapter
from app.models.character import Character
from app.models.character_relationship import CharacterRelationship
from app.models.plot_line import PlotLine
from app.models.project import NovelProject
from app.models.worldbook_entry import WorldbookEntry
from app.services.graph_service import get_project_graph


EXPORT_ROOT = Path(__file__).resolve().parents[3] / "exports"


def _safe_name(value: str) -> str:
    normalized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip().strip(".")
    return normalized or "untitled"


def _format_dt(value: datetime | None) -> str:
    if value is None:
        value = datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return _format_dt(value)
    return value


def _model_dict(item: Any) -> dict[str, Any]:
    return {column.name: _jsonable(getattr(item, column.name)) for column in item.__table__.columns}


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def _yaml_list(name: str, items: list[str]) -> list[str]:
    lines = [f"{name}:"]
    if not items:
        lines.append("  []")
        return lines
    lines.extend(f"  - {_yaml_scalar(item)}" for item in items)
    return lines


def _chapter_front_matter(chapter: Chapter, characters: list[Character], plot_lines: list[PlotLine]) -> str:
    lines = [
        "---",
        f"chapter_no: {chapter.chapter_no}",
        f"title: {_yaml_scalar(chapter.title)}",
        f"word_count: {chapter.word_count}",
        f"created_at: {_yaml_scalar(_format_dt(chapter.created_at))}",
        *_yaml_list("characters", [item.name for item in characters]),
        *_yaml_list("plot_lines", [item.title for item in plot_lines]),
        "---",
        "",
    ]
    return "\n".join(lines)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_workflow_logs(db: Session, project_id: int, workflow_logs_dir: Path) -> None:
    workflow_map = {
        "wf-01_trend_inspiration": ["trend", "trend_exploration"],
        "wf-02_worldbuilding": ["asset", "world", "character"],
        "wf-03_outline_planning": ["outline", "design"],
        "wf-04_chapter_writing": ["chapter", "draft", "revision", "consistency"],
        "wf-05_entity_extraction": ["extract", "graph"],
    }
    tasks = list(db.scalars(select(AITask).where(AITask.project_id == project_id).order_by(AITask.created_at.asc())))
    steps_by_task: dict[int, list[TaskStep]] = {}
    if tasks:
        task_ids = [task.id for task in tasks]
        steps = list(db.scalars(select(TaskStep).where(TaskStep.task_id.in_(task_ids)).order_by(TaskStep.step_no.asc())))
        for step in steps:
            steps_by_task.setdefault(step.task_id, []).append(step)

    for folder_name, markers in workflow_map.items():
        folder = workflow_logs_dir / folder_name
        folder.mkdir(parents=True, exist_ok=True)
        matched_tasks = [
            task
            for task in tasks
            if any(marker in f"{task.task_type} {task.module_type} {task.title}".lower() for marker in markers)
        ]
        plan_lines = [f"# {folder_name}", ""]
        trace_lines = [f"# {folder_name} trace", ""]
        if not matched_tasks:
            plan_lines.append("No tasks matched this workflow yet.")
            trace_lines.append("No trace records yet.")
        for task in matched_tasks:
            plan_lines.extend([f"## Task #{task.id}: {task.title}", "", task.plan_text or "No plan text.", ""])
            trace_lines.extend(
                [
                    f"## Task #{task.id}: {task.title}",
                    "",
                    f"- status: {task.status}",
                    f"- started_at: {_format_dt(task.started_at)}",
                    f"- finished_at: {_format_dt(task.finished_at)}",
                    "",
                    "### Steps",
                    "",
                ]
            )
            for step in steps_by_task.get(task.id, []):
                trace_lines.append(f"- {step.step_no}. {step.step_name} / {step.react_state} / {step.status}")
            if task.reasoning_trace:
                trace_lines.extend(["", "### Reasoning Trace", "", "```json", task.reasoning_trace, "```"])
            if task.tool_trace:
                trace_lines.extend(["", "### Tool Trace", "", "```json", task.tool_trace, "```"])
            trace_lines.append("")
        (folder / "plan.md").write_text("\n".join(plan_lines), encoding="utf-8")
        (folder / "trace.md").write_text("\n".join(trace_lines), encoding="utf-8")


def export_project_files(db: Session, project_id: int, export_root: Path | None = None) -> dict[str, Any]:
    project = db.get(NovelProject, project_id)
    if project is None:
        raise ValueError("Project not found")

    root = export_root or EXPORT_ROOT
    project_dir = root / _safe_name(project.name)
    if project_dir.exists():
        shutil.rmtree(project_dir)
    chapters_dir = project_dir / "chapters"
    assets_dir = project_dir / "assets"
    workflow_logs_dir = project_dir / "workflow_logs"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)
    workflow_logs_dir.mkdir(parents=True, exist_ok=True)

    chapters = list(db.scalars(select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.chapter_no.asc())))
    characters = list(db.scalars(select(Character).where(Character.project_id == project_id).order_by(Character.id.asc())))
    relationships = list(
        db.scalars(select(CharacterRelationship).where(CharacterRelationship.project_id == project_id).order_by(CharacterRelationship.id.asc()))
    )
    plot_lines = list(db.scalars(select(PlotLine).where(PlotLine.project_id == project_id).order_by(PlotLine.priority.desc())))
    worldbook = list(
        db.scalars(select(WorldbookEntry).where(WorldbookEntry.project_id == project_id).order_by(WorldbookEntry.updated_at.desc()))
    )

    chapter_files: list[str] = []
    whole_book_parts: list[str] = []
    for chapter in chapters:
        content = chapter.final_content or chapter.draft_content or ""
        front_matter = _chapter_front_matter(chapter, characters, plot_lines)
        markdown = f"{front_matter}# {chapter.title}\n\n{content.strip()}\n"
        filename = f"第{chapter.chapter_no:02d}章_{_safe_name(chapter.title)}.md"
        path = chapters_dir / filename
        path.write_text(markdown, encoding="utf-8")
        chapter_files.append(str(path))
        whole_book_parts.append(markdown)

    whole_book_path = project_dir / f"{_safe_name(project.name)}_全本.md"
    whole_book_path.write_text("\n\n".join(whole_book_parts), encoding="utf-8")

    _write_json(assets_dir / "characters.json", [_model_dict(item) for item in characters])
    _write_json(assets_dir / "relationships.json", [_model_dict(item) for item in relationships])
    _write_json(assets_dir / "plot_lines.json", [_model_dict(item) for item in plot_lines])
    _write_json(assets_dir / "worldbook.json", [_model_dict(item) for item in worldbook])
    _write_json(assets_dir / "story_entity_graph.json", get_project_graph(db, project_id, graph_type="story_entity"))
    _write_json(assets_dir / "task_workflow_graph.json", get_project_graph(db, project_id, graph_type="task_workflow"))
    _write_json(assets_dir / "chapter_structure_graph.json", get_project_graph(db, project_id, graph_type="chapter_structure"))
    _write_json(assets_dir / "worldbook_graph.json", get_project_graph(db, project_id, graph_type="worldbook"))
    _write_json(assets_dir / "graph_export.json", get_project_graph(db, project_id, graph_type="story_entity"))
    placeholder_png = assets_dir / "graph_export.png"
    placeholder_png.write_bytes(
        b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/lxWR2wAAAABJRU5ErkJggg==")
    )

    _write_workflow_logs(db, project_id, workflow_logs_dir)

    return {
        "project_id": project_id,
        "project_name": project.name,
        "export_dir": str(project_dir),
        "whole_book": str(whole_book_path),
        "chapter_files": chapter_files,
        "assets_dir": str(assets_dir),
        "workflow_logs_dir": str(workflow_logs_dir),
    }


def _resolve_project_dir(project_id: int, db: Session, export_root: Path | None = None) -> Path:
    """解析项目导出目录，若不存在则抛出异常"""
    project = db.get(NovelProject, project_id)
    if project is None:
        raise ValueError("Project not found")
    root = export_root or EXPORT_ROOT
    project_dir = root / _safe_name(project.name)
    if not project_dir.exists():
        raise ValueError("Project export directory not found. Please export files first.")
    return project_dir


def _classify_file_type(file_path: Path) -> str:
    """根据文件路径判断文件类型"""
    parts = file_path.parts
    if "chapters" in parts:
        return "chapter"
    if "assets" in parts:
        return "asset"
    if "workflow_logs" in parts:
        return "log"
    if file_path.suffix == ".zip":
        return "archive"
    return "other"


_CORE_FILE_TYPES = {"chapter", "asset"}


def _resolve_project_file(project_id: int, file_path: str, db: Session, export_root: Path | None = None) -> tuple[Path, Path]:
    """
    安全地解析项目内文件路径，返回 (project_dir, resolved_file)。
    包含路径遍历防护。
    """
    project_dir = _resolve_project_dir(project_id, db, export_root)

    # 路径遍历防护：确保最终路径在 project_dir 内部
    cleaned = Path(file_path).as_posix().lstrip("/")
    resolved = (project_dir / cleaned).resolve()
    if not str(resolved).startswith(str(project_dir.resolve())):
        raise ValueError("Invalid file path: path traversal detected")
    if not resolved.exists():
        raise ValueError("File not found")
    return project_dir, resolved


def list_project_files(
    db: Session,
    project_id: int,
    file_type: str | None = None,
    export_root: Path | None = None,
) -> list[dict[str, Any]]:
    """列出项目所有生成的文件，支持按类型过滤"""
    project_dir = _resolve_project_dir(project_id, db, export_root)

    files: list[dict[str, Any]] = []
    for path in sorted(project_dir.rglob("*")):
        if not path.is_file():
            continue

        ft = _classify_file_type(path)
        if file_type and ft != file_type:
            continue

        rel = path.relative_to(project_dir)
        stat = path.stat()
        files.append(
            {
                "path": rel.as_posix(),
                "name": path.name,
                "size": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                "file_type": ft,
            }
        )

    return files


def get_project_file_content(
    db: Session,
    project_id: int,
    file_path: str,
    export_root: Path | None = None,
) -> dict[str, Any]:
    """获取文件内容和元数据"""
    project_dir, resolved = _resolve_project_file(project_id, file_path, db, export_root)

    ft = _classify_file_type(resolved)
    rel = resolved.relative_to(project_dir)
    stat = resolved.stat()

    # 仅支持文本文件读取
    if resolved.suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".zip"}:
        content = f"[binary file, size={stat.st_size} bytes]"
    else:
        content = resolved.read_text(encoding="utf-8")

    metadata: dict[str, Any] = {
        "size": stat.st_size,
        "modified_at": _format_dt(datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)),
        "file_type": ft,
        "mime_type": "text/plain",
    }

    return {
        "path": rel.as_posix(),
        "content": content,
        "metadata": metadata,
    }


def delete_project_file(
    db: Session,
    project_id: int,
    file_path: str,
    export_root: Path | None = None,
) -> dict[str, Any]:
    """
    删除指定文件。
    仅允许删除非核心文件（log, archive, other），核心文件（chapter, asset）不允许删除。
    """
    project_dir, resolved = _resolve_project_file(project_id, file_path, db, export_root)

    ft = _classify_file_type(resolved)
    if ft in _CORE_FILE_TYPES:
        raise ValueError(f"Cannot delete core file of type '{ft}'. Only logs, archives and other files can be deleted.")

    rel = resolved.relative_to(project_dir)
    resolved.unlink()

    return {
        "deleted": rel.as_posix(),
        "file_type": ft,
    }


def update_project_file(
    db: Session,
    project_id: int,
    file_path: str,
    new_content: str,
    comment: str | None = None,
    export_root: Path | None = None,
) -> dict[str, Any]:
    """
    更新文件内容，仅限章节文件（chapter 类型）。
    将更新保存到文件并记录修改信息。
    """
    project_dir, resolved = _resolve_project_file(project_id, file_path, db, export_root)

    ft = _classify_file_type(resolved)
    if ft != "chapter":
        raise ValueError(f"Only chapter files can be updated. This file is of type '{ft}'.")

    old_stat = resolved.stat()
    old_size = old_stat.st_size

    # 写入新内容
    resolved.write_text(new_content, encoding="utf-8")

    new_stat = resolved.stat()

    return {
        "path": resolved.relative_to(project_dir).as_posix(),
        "old_size": old_size,
        "new_size": new_stat.st_size,
        "modified_at": _format_dt(datetime.fromtimestamp(new_stat.st_mtime, tz=timezone.utc)),
        "comment": comment,
    }


def export_project_archive(db: Session, project_id: int, export_root: Path | None = None) -> dict[str, Any]:
    result = export_project_files(db, project_id, export_root=export_root)
    project_dir = Path(result["export_dir"])
    zip_path = project_dir.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in project_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(project_dir.parent))
    return {**result, "archive_path": str(zip_path)}


# =============================================================================
# 按"项目 → 任务 → 章节 → 小节 → 每小节的内容.md"层级结构导出
# =============================================================================

# Markdown 二级标题（## xxx）作为小节切分点
_SECTION_HEADER_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _split_chapter_into_sections(content: str) -> list[tuple[str, str]]:
    """把章节内容按 ## 二级标题切成小节。返回 [(小节标题, 内容), ...]。
    若没有二级标题，则整章作为一个小节，前缀为'序章/正文'。
    """
    if not content or not content.strip():
        return [("正文", "")]
    matches = list(_SECTION_HEADER_RE.finditer(content))
    if not matches:
        return [("正文", content.strip())]
    sections: list[tuple[str, str]] = []
    if matches[0].start() > 0:
        # 首个二级标题之前的内容作为"序章"
        preamble = content[: matches[0].start()].strip()
        if preamble:
            sections.append(("序章", preamble))
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[start:end].strip()
        sections.append((title, body))
    return sections


def _resolve_export_root(db: Session, project: NovelProject) -> Path:
    """根据项目设置解析导出根目录。优先用 project.export_root_path，
    否则用后端默认 EXPORT_ROOT。
    """
    if project.export_root_path:
        p = Path(project.export_root_path).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        return p
    return EXPORT_ROOT


def export_chapter_hierarchy(db: Session, project_id: int) -> dict[str, Any]:
    """按"项目 → 任务（task_type）→ 章节（chapter_no）→ 小节（## 标题）→ 每小节的内容.md"
    层级结构导出。

    目录布局：
    <root>/<项目名>/<任务分类>/<章节名>_<章节号>/<小节名>.md
    """
    project = db.get(NovelProject, project_id)
    if project is None:
        raise ValueError("Project not found")

    root = _resolve_export_root(db, project)
    project_dir = root / _safe_name(project.name)
    if project_dir.exists():
        shutil.rmtree(project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)

    chapters = list(
        db.scalars(
            select(Chapter)
            .where(Chapter.project_id == project_id)
            .order_by(Chapter.chapter_no.asc())
        )
    )
    if not chapters:
        raise ValueError("No chapters to export")

    # 任务分类：用 project_id 下的所有 AITask，按 task_type 分组
    tasks = list(
        db.scalars(
            select(AITask)
            .where(AITask.project_id == project_id)
            .order_by(AITask.created_at.asc())
        )
    )
    # task_type 优先：chapter_writer / consistency_check / outline_planning / ...
    # 同 task_type 内按时间顺序
    task_by_type: dict[str, list[AITask]] = {}
    for t in tasks:
        key = t.task_type or "其他任务"
        task_by_type.setdefault(key, []).append(t)

    # 章节 → 任务映射：用 task.module_type 关联
    # 这里简化：所有 chapter 归属 'chapter_writer' 任务；其他任务归为同名任务目录
    chapter_task_type = "chapter_writer"
    chapter_task_dir = project_dir / _safe_name(chapter_task_type)
    chapter_task_dir.mkdir(parents=True, exist_ok=True)

    chapter_files: list[str] = []
    whole_book_parts: list[str] = []

    for chapter in chapters:
        content = (chapter.final_content or chapter.draft_content or "").strip()
        sections = _split_chapter_into_sections(content)
        # 章节目录
        chap_dirname = f"第{chapter.chapter_no:02d}章_{_safe_name(chapter.title or '未命名')}"
        chap_dir = chapter_task_dir / chap_dirname
        chap_dir.mkdir(parents=True, exist_ok=True)
        # 章节总览 README.md
        readme_lines = [
            f"# 第{chapter.chapter_no}章 {chapter.title or '未命名'}",
            "",
            f"- 字数: {chapter.word_count}",
            f"- 状态: {chapter.status}",
            f"- 创建时间: {_format_dt(chapter.created_at)}",
            f"- 更新时间: {_format_dt(chapter.updated_at)}",
            "",
            f"## 小节列表（共 {len(sections)} 节）",
            "",
        ]
        section_files_in_chap: list[str] = []
        for idx, (sec_title, sec_body) in enumerate(sections, start=1):
            safe_sec = _safe_name(sec_title) or f"小节{idx:02d}"
            sec_filename = f"{idx:02d}_{safe_sec}.md"
            sec_path = chap_dir / sec_filename
            front_matter = [
                "---",
                f"chapter_no: {chapter.chapter_no}",
                f"chapter_title: {_yaml_scalar(chapter.title)}",
                f"section_no: {idx}",
                f"section_title: {_yaml_scalar(sec_title)}",
                f"word_count: {len(sec_body)}",
                "---",
                "",
            ]
            sec_md = "\n".join(front_matter) + f"# {sec_title}\n\n{sec_body}\n"
            sec_path.write_text(sec_md, encoding="utf-8")
            section_files_in_chap.append(sec_filename)
            readme_lines.append(f"- [{idx:02d}. {sec_title}](./{sec_filename})")
            whole_book_parts.append(sec_md)
        readme_lines.append("")
        (chap_dir / "README.md").write_text("\n".join(readme_lines), encoding="utf-8")
        chapter_files.append(str(chap_dir))
        # 全本文件
        whole_book_parts.append(f"\n\n---\n# 第{chapter.chapter_no}章 {chapter.title}\n\n")

    # 其他任务目录（每个 task_type 一个空文件夹，附 plan.md / trace.md 留档）
    for task_type, task_list in task_by_type.items():
        if task_type == chapter_task_type:
            continue
        other_dir = project_dir / _safe_name(task_type)
        other_dir.mkdir(parents=True, exist_ok=True)
        # 任务执行记录
        plan_lines = [f"# {task_type} 任务记录", ""]
        for tk in task_list:
            plan_lines.extend(
                [
                    f"## Task #{tk.id}: {tk.title}",
                    f"- status: {tk.status}",
                    f"- started_at: {_format_dt(tk.started_at)}",
                    f"- finished_at: {_format_dt(tk.finished_at)}",
                    "",
                    tk.plan_text or "(无 plan 文本)",
                    "",
                ]
            )
        (other_dir / "plan.md").write_text("\n".join(plan_lines), encoding="utf-8")

    # 全本
    whole_book_path = project_dir / f"{_safe_name(project.name)}_全本.md"
    whole_book_path.write_text("\n".join(whole_book_parts), encoding="utf-8")

    # ZIP
    zip_path = project_dir.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in project_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(project_dir.parent))

    return {
        "project_id": project_id,
        "project_name": project.name,
        "export_root": str(root),
        "project_dir": str(project_dir),
        "chapter_files": chapter_files,
        "whole_book": str(whole_book_path),
        "archive_path": str(zip_path),
        "task_types": sorted(task_by_type.keys()),
    }


def export_hierarchical_markdown(db: Session, project_id: int, export_root: Path | None = None) -> dict[str, Any]:
    """
    按"书库→主题→风格→题目→章节→内容"层级结构导出 Markdown。
    """
    project = db.get(NovelProject, project_id)
    if project is None:
        raise ValueError("Project not found")

    root = export_root or EXPORT_ROOT
    library_dir = root / "书库"
    library_dir.mkdir(parents=True, exist_ok=True)

    # 主题目录：从项目名中提取主题（或使用项目名作为主题）
    topic = _safe_name(project.name) or "未命名主题"
    topic_dir = library_dir / topic
    topic_dir.mkdir(parents=True, exist_ok=True)

    # 风格目录：从项目中查找风格提示
    chapters = list(db.scalars(select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.chapter_no.asc())))
    plot_lines = list(db.scalars(select(PlotLine).where(PlotLine.project_id == project_id).order_by(PlotLine.priority.desc())))
    characters = list(db.scalars(select(Character).where(Character.project_id == project_id).order_by(Character.id.asc())))
    worldbook = list(
        db.scalars(select(WorldbookEntry).where(WorldbookEntry.project_id == project_id).order_by(WorldbookEntry.updated_at.desc()))
    )

    # 推断风格：从章节目标或第一个剧情线中获取
    style_name = "AI自主风格"
    if chapters and chapters[0].objective:
        style_name = _safe_name(chapters[0].objective[:30]) or style_name
    style_dir = topic_dir / style_name
    style_dir.mkdir(parents=True, exist_ok=True)

    # 题目目录：使用项目名
    title_dir = style_dir / _safe_name(project.name)
    title_dir.mkdir(parents=True, exist_ok=True)

    # 章节目录
    chapters_output_dir = title_dir / "章节"
    chapters_output_dir.mkdir(parents=True, exist_ok=True)

    chapter_files: list[str] = []
    whole_book_parts: list[str] = []

    # 章节索引文件
    index_lines = [f"# {project.name}", "", "## 章节目录", ""]
    for chapter in chapters:
        content = chapter.final_content or chapter.draft_content or ""
        front_matter = _chapter_front_matter(chapter, characters, plot_lines)
        markdown = f"{front_matter}# {chapter.title}\n\n{content.strip()}\n"
        filename = f"第{chapter.chapter_no:02d}章_{_safe_name(chapter.title)}.md"
        path = chapters_output_dir / filename
        path.write_text(markdown, encoding="utf-8")
        chapter_files.append(str(path))
        whole_book_parts.append(markdown)
        index_lines.append(f"- [{filename}](./{filename})")

    index_lines.append("")
    index_path = title_dir / "README.md"
    index_path.write_text("\n".join(index_lines), encoding="utf-8")

    # 全本文件
    whole_book_path = title_dir / f"{_safe_name(project.name)}_全本.md"
    whole_book_path.write_text("\n\n".join(whole_book_parts), encoding="utf-8")

    # 资产目录
    assets_output_dir = title_dir / "资产"
    assets_output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(assets_output_dir / "人物.json", [_model_dict(c) for c in characters])
    _write_json(assets_output_dir / "关系.json", [_model_dict(r) for r in db.scalars(
        select(CharacterRelationship).where(CharacterRelationship.project_id == project_id)
    )])
    _write_json(assets_output_dir / "剧情线.json", [_model_dict(p) for p in plot_lines])
    _write_json(assets_output_dir / "世界观.json", [_model_dict(w) for w in worldbook])

    # 生成 ZIP 归档
    zip_path = title_dir.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in title_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(library_dir))

    return {
        "project_id": project_id,
        "project_name": project.name,
        "library_dir": str(library_dir),
        "topic_dir": str(topic_dir),
        "style_dir": str(style_dir),
        "title_dir": str(title_dir),
        "export_dir": str(title_dir),
        "whole_book": str(whole_book_path),
        "chapter_files": chapter_files,
        "archive_path": str(zip_path),
    }
