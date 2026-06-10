# 数据库与图谱设计

## 1. 总体设计

采用混合存储：

1. SQLite/PostgreSQL 负责事务型数据和后台配置。
2. Neo4j 负责人物关系、事件关系、势力关系、剧情依赖关系。
3. 文件系统负责缓存文档、Prompt、日志快照和导出稿件。

MVP 推荐：

1. 开发环境使用 SQLite + Neo4j。
2. 生产环境切换 PostgreSQL + Neo4j。

## 2. 关系型数据库表设计

### 2.1 novel_projects

- `id`
- `name`
- `genre`
- `theme`
- `target_audience`
- `writing_style`
- `tone`
- `summary`
- `world_setting`
- `constraints_json`
- `status`
- `created_at`
- `updated_at`

### 2.2 project_settings

- `id`
- `project_id`
- `llm_provider`
- `model_name`
- `temperature`
- `max_tokens`
- `enable_web_research`
- `enable_graph_sync`
- `agent_mode`
- `prompt_preset`
- `created_at`
- `updated_at`

### 2.3 characters

- `id`
- `project_id`
- `name`
- `alias`
- `role_type`
- `gender`
- `age`
- `identity`
- `personality`
- `motivation`
- `goal`
- `fear`
- `secret`
- `background`
- `appearance`
- `status`
- `arc_summary`
- `meta_json`
- `created_at`
- `updated_at`

### 2.4 worldbooks

- `id`
- `project_id`
- `title`
- `category`
- `content`
- `source_type`
- `source_ref`
- `tags_json`
- `created_at`
- `updated_at`

### 2.5 plot_lines

- `id`
- `project_id`
- `title`
- `plot_type`
- `summary`
- `goal`
- `conflict`
- `stakes`
- `start_phase`
- `end_phase`
- `status`
- `priority`
- `created_at`
- `updated_at`

### 2.6 plot_nodes

- `id`
- `project_id`
- `plot_line_id`
- `title`
- `node_type`
- `summary`
- `trigger_condition`
- `expected_outcome`
- `sequence_no`
- `chapter_id`
- `created_at`
- `updated_at`

### 2.7 chapters

- `id`
- `project_id`
- `chapter_no`
- `title`
- `summary`
- `objective`
- `conflict`
- `pov_character_id`
- `status`
- `draft_content`
- `final_content`
- `word_count`
- `version`
- `created_at`
- `updated_at`

### 2.8 chapter_versions

- `id`
- `chapter_id`
- `version_no`
- `content`
- `change_note`
- `created_at`

### 2.9 chapter_plans

- `id`
- `project_id`
- `chapter_id`
- `plan_type`
- `goal`
- `conflict`
- `beats_json`
- `constraints_json`
- `references_json`
- `created_at`
- `updated_at`

### 2.10 research_documents

- `id`
- `project_id`
- `title`
- `source_url`
- `source_type`
- `raw_content`
- `extracted_content`
- `keywords_json`
- `relevance_score`
- `created_at`

### 2.11 trend_explorations

- `id`
- `project_id`
- `title`
- `source_scope`
- `query_text`
- `raw_findings`
- `extracted_topics`
- `extracted_tags`
- `suggested_directions`
- `status`
- `created_at`
- `updated_at`

### 2.12 ai_tasks

- `id`
- `project_id`
- `chapter_id`
- `plot_line_id`
- `task_type`
- `module_type`
- `title`
- `input_payload`
- `plan_text`
- `reasoning_trace`
- `tool_trace`
- `output_payload`
- `status`
- `error_message`
- `started_at`
- `finished_at`
- `created_at`

### 2.13 task_steps

- `id`
- `task_id`
- `step_no`
- `step_name`
- `step_type`
- `react_state`
- `input_payload`
- `output_payload`
- `tool_name`
- `status`
- `error_message`
- `started_at`
- `finished_at`

### 2.14 task_logs

- `id`
- `task_id`
- `log_type`
- `message`
- `payload`
- `created_at`

### 2.15 prompt_templates

- `id`
- `name`
- `scene`
- `system_prompt`
- `user_prompt_template`
- `variables_json`
- `version`
- `created_at`
- `updated_at`

### 2.16 memory_records

- `id`
- `project_id`
- `memory_type`
- `title`
- `content`
- `source_task_id`
- `importance`
- `tags_json`
- `created_at`
- `updated_at`

## 3. Neo4j 图谱设计

## 3.1 节点类型

1. `Character`
2. `Faction`
3. `Event`
4. `PlotLine`
5. `Location`
6. `Artifact`
7. `Rule`
8. `Chapter`

## 3.2 关系类型

1. `:KNOWS`
2. `:ALLY_OF`
3. `:ENEMY_OF`
4. `:LOVES`
5. `:HATES`
6. `:BELONGS_TO`
7. `:TRIGGERS`
8. `:PARTICIPATES_IN`
9. `:AFFECTS`
10. `:LOCATED_IN`
11. `:CONSTRAINS`

## 3.3 图谱约束建议

1. 角色名称在项目内唯一。
2. 事件节点绑定项目 ID。
3. 每条关系必须带 `project_id`。
4. 关系可以包含 `intensity`、`status`、`note`、`updated_at`。

## 4. 数据流原则

1. 结构化源数据先入关系库。
2. 关系视图同步到 Neo4j。
3. AI 生成内容必须带来源任务 ID。
4. 研究资料与抽取结果分开存储，方便复盘。
