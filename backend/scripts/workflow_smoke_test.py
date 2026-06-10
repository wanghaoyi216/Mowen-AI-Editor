"""
自动创作工作流烟测脚本。
用于验证趋势搜索、章节规划、草稿、校验、修订和实体图谱入库链路。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import SessionLocal
from app.db import models  # noqa: F401
from app.schemas.workflow_orchestration import AutoNovelWorkflowRequest
from app.services.workflow_orchestration_service import execute_auto_novel_workflow


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", type=int, default=1)
    parser.add_argument("--word-target", type=int, default=300)
    args = parser.parse_args()

    payload = AutoNovelWorkflowRequest(
        title="AI连通性烟测任务",
        query_text="2026 中文网文 科幻 悬疑 热点",
        source_scope="web",
        search_depth="basic",
        max_results=2,
        chapter_no=1,
        chapter_title="雾港第一夜",
        chapter_summary="主角在异常雾港发现第一条失踪线索。",
        chapter_objective="建立悬疑氛围并引出核心规则。",
        chapter_conflict="主角必须在雾中找到线索，同时避免被未知系统标记。",
        design_guidance="保持紧凑节奏，强调规则怪谈与近未来技术感。",
        style_hint="中文小说正文，克制、悬疑、画面感强。",
        revision_focus="修正逻辑跳跃，增强人物动机。",
        word_target=args.word_target,
    )

    db = SessionLocal()
    try:
        result = execute_auto_novel_workflow(db, args.project_id, payload)
        task = result["task"]
        chapter = result["chapter"]
        version = result["version"]
        extraction = result["entity_extraction"]
        print("工作流烟测通过")
        print(f"task_id={task.id}, status={task.status}")
        print(f"chapter_id={chapter.id}, status={chapter.status}, word_count={chapter.word_count}")
        print(f"version_id={version.id}, model={version.selected_model}")
        print(
            "graph="
            f"entities+{extraction['added_entities']}, "
            f"relationships+{extraction['added_relationships']}"
        )
        return 0
    except Exception as exc:
        print(f"工作流烟测失败: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
