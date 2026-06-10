"""initial schema

Revision ID: 20260531_0001
Revises: 
Create Date: 2026-05-31 00:00:01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260531_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "novel_projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("genre", sa.String(length=100), nullable=True),
        sa.Column("theme", sa.String(length=200), nullable=True),
        sa.Column("target_audience", sa.String(length=100), nullable=True),
        sa.Column("writing_style", sa.String(length=100), nullable=True),
        sa.Column("tone", sa.String(length=100), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("world_setting", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_novel_projects_id", "novel_projects", ["id"])
    op.create_index("ix_novel_projects_name", "novel_projects", ["name"])

    op.create_table(
        "characters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("novel_projects.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("alias", sa.String(length=200), nullable=True),
        sa.Column("role_type", sa.String(length=100), nullable=True),
        sa.Column("gender", sa.String(length=50), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("identity", sa.String(length=200), nullable=True),
        sa.Column("personality", sa.Text(), nullable=True),
        sa.Column("motivation", sa.Text(), nullable=True),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("fear", sa.Text(), nullable=True),
        sa.Column("secret", sa.Text(), nullable=True),
        sa.Column("background", sa.Text(), nullable=True),
        sa.Column("appearance", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("arc_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_characters_id", "characters", ["id"])
    op.create_index("ix_characters_name", "characters", ["name"])
    op.create_index("ix_characters_project_id", "characters", ["project_id"])

    op.create_table(
        "chapters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("novel_projects.id"), nullable=False),
        sa.Column("chapter_no", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("conflict", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("draft_content", sa.Text(), nullable=True),
        sa.Column("final_content", sa.Text(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_chapters_id", "chapters", ["id"])
    op.create_index("ix_chapters_project_id", "chapters", ["project_id"])

    op.create_table(
        "plot_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("novel_projects.id"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("plot_type", sa.String(length=100), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("conflict", sa.Text(), nullable=True),
        sa.Column("stakes", sa.Text(), nullable=True),
        sa.Column("start_phase", sa.String(length=100), nullable=True),
        sa.Column("end_phase", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_plot_lines_id", "plot_lines", ["id"])
    op.create_index("ix_plot_lines_project_id", "plot_lines", ["project_id"])
    op.create_index("ix_plot_lines_title", "plot_lines", ["title"])

    op.create_table(
        "chapter_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("novel_projects.id"), nullable=False),
        sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("chapters.id"), nullable=False),
        sa.Column("plot_line_id", sa.Integer(), sa.ForeignKey("plot_lines.id"), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("design_brief", sa.Text(), nullable=False),
        sa.Column("beat_sheet", sa.Text(), nullable=False),
        sa.Column("asset_summary", sa.Text(), nullable=False),
        sa.Column("selected_model", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_chapter_plans_id", "chapter_plans", ["id"])
    op.create_index("ix_chapter_plans_project_id", "chapter_plans", ["project_id"])
    op.create_index("ix_chapter_plans_chapter_id", "chapter_plans", ["chapter_id"])
    op.create_index("ix_chapter_plans_plot_line_id", "chapter_plans", ["plot_line_id"])

    op.create_table(
        "story_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("novel_projects.id"), nullable=False),
        sa.Column("plot_line_id", sa.Integer(), sa.ForeignKey("plot_lines.id"), nullable=True),
        sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("chapters.id"), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("trigger_condition", sa.Text(), nullable=True),
        sa.Column("expected_outcome", sa.Text(), nullable=True),
        sa.Column("impact_level", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_story_events_id", "story_events", ["id"])
    op.create_index("ix_story_events_project_id", "story_events", ["project_id"])
    op.create_index("ix_story_events_plot_line_id", "story_events", ["plot_line_id"])
    op.create_index("ix_story_events_chapter_id", "story_events", ["chapter_id"])
    op.create_index("ix_story_events_title", "story_events", ["title"])

    op.create_table(
        "character_relationships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("novel_projects.id"), nullable=False),
        sa.Column("source_character_id", sa.Integer(), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("target_character_id", sa.Integer(), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("relation_type", sa.String(length=100), nullable=False),
        sa.Column("intensity", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_character_relationships_id", "character_relationships", ["id"])
    op.create_index("ix_character_relationships_project_id", "character_relationships", ["project_id"])
    op.create_index("ix_character_relationships_source_character_id", "character_relationships", ["source_character_id"])
    op.create_index("ix_character_relationships_target_character_id", "character_relationships", ["target_character_id"])
    op.create_index("ix_character_relationships_relation_type", "character_relationships", ["relation_type"])

    op.create_table(
        "character_event_participations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("novel_projects.id"), nullable=False),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("story_events.id"), nullable=False),
        sa.Column("role_type", sa.String(length=100), nullable=False),
        sa.Column("impact_score", sa.Float(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_character_event_participations_id", "character_event_participations", ["id"])
    op.create_index("ix_character_event_participations_project_id", "character_event_participations", ["project_id"])
    op.create_index("ix_character_event_participations_character_id", "character_event_participations", ["character_id"])
    op.create_index("ix_character_event_participations_event_id", "character_event_participations", ["event_id"])

    op.create_table(
        "worldbook_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("novel_projects.id"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=100), nullable=True),
        sa.Column("source_ref", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_worldbook_entries_id", "worldbook_entries", ["id"])
    op.create_index("ix_worldbook_entries_project_id", "worldbook_entries", ["project_id"])
    op.create_index("ix_worldbook_entries_title", "worldbook_entries", ["title"])

    op.create_table(
        "trend_explorations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("novel_projects.id"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("source_scope", sa.String(length=100), nullable=True),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("raw_findings", sa.Text(), nullable=True),
        sa.Column("extracted_topics", sa.Text(), nullable=True),
        sa.Column("extracted_tags", sa.Text(), nullable=True),
        sa.Column("suggested_directions", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_trend_explorations_id", "trend_explorations", ["id"])
    op.create_index("ix_trend_explorations_project_id", "trend_explorations", ["project_id"])

    op.create_table(
        "ai_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("novel_projects.id"), nullable=False),
        sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("chapters.id"), nullable=True),
        sa.Column("plot_line_id", sa.Integer(), nullable=True),
        sa.Column("task_type", sa.String(length=100), nullable=False),
        sa.Column("module_type", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("input_payload", sa.Text(), nullable=True),
        sa.Column("plan_text", sa.Text(), nullable=True),
        sa.Column("reasoning_trace", sa.Text(), nullable=True),
        sa.Column("tool_trace", sa.Text(), nullable=True),
        sa.Column("output_payload", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_tasks_id", "ai_tasks", ["id"])
    op.create_index("ix_ai_tasks_project_id", "ai_tasks", ["project_id"])
    op.create_index("ix_ai_tasks_chapter_id", "ai_tasks", ["chapter_id"])
    op.create_index("ix_ai_tasks_task_type", "ai_tasks", ["task_type"])
    op.create_index("ix_ai_tasks_module_type", "ai_tasks", ["module_type"])

    op.create_table(
        "task_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("ai_tasks.id"), nullable=False),
        sa.Column("step_no", sa.Integer(), nullable=False),
        sa.Column("step_name", sa.String(length=200), nullable=False),
        sa.Column("step_type", sa.String(length=100), nullable=False),
        sa.Column("react_state", sa.String(length=100), nullable=False),
        sa.Column("input_payload", sa.Text(), nullable=True),
        sa.Column("output_payload", sa.Text(), nullable=True),
        sa.Column("tool_name", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_task_steps_id", "task_steps", ["id"])
    op.create_index("ix_task_steps_task_id", "task_steps", ["task_id"])

    op.create_table(
        "task_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("ai_tasks.id"), nullable=False),
        sa.Column("log_type", sa.String(length=100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_task_logs_id", "task_logs", ["id"])
    op.create_index("ix_task_logs_task_id", "task_logs", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_chapter_plans_plot_line_id", table_name="chapter_plans")
    op.drop_index("ix_chapter_plans_chapter_id", table_name="chapter_plans")
    op.drop_index("ix_chapter_plans_project_id", table_name="chapter_plans")
    op.drop_index("ix_chapter_plans_id", table_name="chapter_plans")
    op.drop_table("chapter_plans")

    op.drop_index("ix_worldbook_entries_title", table_name="worldbook_entries")
    op.drop_index("ix_worldbook_entries_project_id", table_name="worldbook_entries")
    op.drop_index("ix_worldbook_entries_id", table_name="worldbook_entries")
    op.drop_table("worldbook_entries")

    op.drop_index("ix_character_event_participations_event_id", table_name="character_event_participations")
    op.drop_index("ix_character_event_participations_character_id", table_name="character_event_participations")
    op.drop_index("ix_character_event_participations_project_id", table_name="character_event_participations")
    op.drop_index("ix_character_event_participations_id", table_name="character_event_participations")
    op.drop_table("character_event_participations")

    op.drop_index("ix_task_logs_task_id", table_name="task_logs")
    op.drop_index("ix_task_logs_id", table_name="task_logs")
    op.drop_table("task_logs")

    op.drop_index("ix_task_steps_task_id", table_name="task_steps")
    op.drop_index("ix_task_steps_id", table_name="task_steps")
    op.drop_table("task_steps")

    op.drop_index("ix_ai_tasks_module_type", table_name="ai_tasks")
    op.drop_index("ix_ai_tasks_task_type", table_name="ai_tasks")
    op.drop_index("ix_ai_tasks_chapter_id", table_name="ai_tasks")
    op.drop_index("ix_ai_tasks_project_id", table_name="ai_tasks")
    op.drop_index("ix_ai_tasks_id", table_name="ai_tasks")
    op.drop_table("ai_tasks")

    op.drop_index("ix_trend_explorations_project_id", table_name="trend_explorations")
    op.drop_index("ix_trend_explorations_id", table_name="trend_explorations")
    op.drop_table("trend_explorations")

    op.drop_index("ix_character_relationships_relation_type", table_name="character_relationships")
    op.drop_index("ix_character_relationships_target_character_id", table_name="character_relationships")
    op.drop_index("ix_character_relationships_source_character_id", table_name="character_relationships")
    op.drop_index("ix_character_relationships_project_id", table_name="character_relationships")
    op.drop_index("ix_character_relationships_id", table_name="character_relationships")
    op.drop_table("character_relationships")

    op.drop_index("ix_story_events_title", table_name="story_events")
    op.drop_index("ix_story_events_chapter_id", table_name="story_events")
    op.drop_index("ix_story_events_plot_line_id", table_name="story_events")
    op.drop_index("ix_story_events_project_id", table_name="story_events")
    op.drop_index("ix_story_events_id", table_name="story_events")
    op.drop_table("story_events")

    op.drop_index("ix_plot_lines_title", table_name="plot_lines")
    op.drop_index("ix_plot_lines_project_id", table_name="plot_lines")
    op.drop_index("ix_plot_lines_id", table_name="plot_lines")
    op.drop_table("plot_lines")

    op.drop_index("ix_chapters_project_id", table_name="chapters")
    op.drop_index("ix_chapters_id", table_name="chapters")
    op.drop_table("chapters")

    op.drop_index("ix_characters_project_id", table_name="characters")
    op.drop_index("ix_characters_name", table_name="characters")
    op.drop_index("ix_characters_id", table_name="characters")
    op.drop_table("characters")

    op.drop_index("ix_novel_projects_name", table_name="novel_projects")
    op.drop_index("ix_novel_projects_id", table_name="novel_projects")
    op.drop_table("novel_projects")
