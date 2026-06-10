export type GraphNode = {
  id: string;
  entity_id: number;
  label: string;
  type: string;
  meta: {
    alias?: string | null;
    role_type?: string | null;
    status?: string | null;
    category?: string | null;
    source_type?: string | null;
    source_ref?: string | null;
    plot_type?: string | null;
    priority?: number | null;
    event_type?: string | null;
    impact_level?: number | null;
    chapter_no?: number | null;
    selected_model?: string | null;
  };
};

export type GraphRelationship = {
  id: string;
  source: string;
  target: string;
  type: string;
  meta: {
    intensity?: number | null;
    status?: string | null;
    note?: string | null;
  };
};

export type GraphPayload = {
  project_id: number;
  graph_type?: string;
  filters: {
    chapter_id?: number | null;
    character_id?: number | null;
    book_id?: number | null;
  };
  source?: string;
  generated_at?: string | null;
  hint?: string | null;
  nodes: GraphNode[];
  relationships: GraphRelationship[];
};

export type Project = {
  id: number;
  name: string;
  genre?: string | null;
  theme?: string | null;
  target_audience?: string | null;
  writing_style?: string | null;
  tone?: string | null;
  language?: string | null;
  min_words_per_chapter?: number | null;
  max_words_per_chapter?: number | null;
  target_chapters?: number | null;
  summary?: string | null;
  world_setting?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type ProjectCreatePayload = {
  name: string;
  genre?: string | null;
  theme?: string | null;
  target_audience?: string | null;
  writing_style?: string | null;
  tone?: string | null;
  language?: string | null;
  min_words_per_chapter?: number | null;
  max_words_per_chapter?: number | null;
  target_chapters?: number | null;
  summary?: string | null;
  world_setting?: string | null;
  status?: string;
  /** 用户指定的导出根目录（绝对路径，可选）。为空时后端使用默认 EXPORT_ROOT。 */
  export_root_path?: string | null;
};

export type ProjectUpdatePayload = Partial<ProjectCreatePayload>;

export type Character = {
  id: number;
  project_id: number;
  book_id?: number | null;
  name: string;
  alias?: string | null;
  role_type?: string | null;
  gender?: string | null;
  age?: number | null;
  identity?: string | null;
  personality?: string | null;
  motivation?: string | null;
  goal?: string | null;
  fear?: string | null;
  secret?: string | null;
  background?: string | null;
  appearance?: string | null;
  status: string;
  arc_summary?: string | null;
  created_at: string;
  updated_at: string;
};

export type CharacterCreatePayload = {
  name: string;
  alias?: string | null;
  role_type?: string | null;
  gender?: string | null;
  age?: number | null;
  identity?: string | null;
  personality?: string | null;
  motivation?: string | null;
  goal?: string | null;
  fear?: string | null;
  secret?: string | null;
  background?: string | null;
  appearance?: string | null;
  status?: string;
  arc_summary?: string | null;
};

export type CharacterUpdatePayload = Partial<CharacterCreatePayload>;

export type PlotLine = {
  id: number;
  project_id: number;
  book_id?: number | null;
  chapter_id?: number | null;
  title: string;
  plot_type: string;
  summary?: string | null;
  goal?: string | null;
  conflict?: string | null;
  stakes?: string | null;
  start_phase?: string | null;
  end_phase?: string | null;
  status: string;
  priority: number;
  scene_order?: number;
  created_at: string;
  updated_at: string;
};

export type PlotLineCreatePayload = {
  title: string;
  plot_type?: string;
  summary?: string | null;
  goal?: string | null;
  conflict?: string | null;
  stakes?: string | null;
  start_phase?: string | null;
  end_phase?: string | null;
  status?: string;
  priority?: number;
  book_id?: number | null;
  chapter_id?: number | null;
  scene_order?: number;
};

export type PlotLineUpdatePayload = Partial<PlotLineCreatePayload>;

export type StoryEvent = {
  id: number;
  project_id: number;
  book_id?: number | null;
  plot_line_id?: number | null;
  chapter_id?: number | null;
  title: string;
  event_type: string;
  summary?: string | null;
  trigger_condition?: string | null;
  expected_outcome?: string | null;
  impact_level: number;
  status: string;
  created_at: string;
  updated_at: string;
};

export type CharacterEventParticipation = {
  id: number;
  project_id: number;
  book_id?: number | null;
  character_id: number;
  event_id: number;
  role_type: string;
  impact_score: number;
  note?: string | null;
  created_at: string;
  updated_at: string;
};

export type TaskRuntimeState = {
  task_id: number;
  project_id: number;
  status: string;
  current_step?: string | null;
  message?: string | null;
};

export type TaskStepRuntimeState = {
  task_id: number;
  project_id: number;
  step_no: number;
  step_name: string;
  status: string;
  react_state: string;
  message?: string | null;
};

export type AITask = {
  id: number;
  project_id: number;
  chapter_id?: number | null;
  plot_line_id?: number | null;
  task_type: string;
  module_type: string;
  title: string;
  input_payload?: string | null;
  plan_text?: string | null;
  reasoning_trace?: string | null;
  tool_trace?: string | null;
  output_payload?: string | null;
  status: string;
  error_message?: string | null;
  current_step_index?: number | null;
  started_at?: string | null;
  finished_at?: string | null;
  created_at: string;
};

export type TaskLog = {
  id: number;
  task_id: number;
  step_no: number | null;
  log_type: string;
  message: string;
  payload: string | null;
  created_at: string;
};

export type TaskStep = {
  id: number;
  task_id: number;
  step_no: number;
  step_name: string;
  step_type: string;
  react_state: string;
  input_payload?: string | null;
  output_payload?: string | null;
  tool_name?: string | null;
  status: string;
  error_message?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
};

export type TrendExploration = {
  id: number;
  project_id: number;
  title: string;
  source_scope?: string | null;
  query_text: string;
  raw_findings?: string | null;
  extracted_topics?: string | null;
  extracted_tags?: string | null;
  suggested_directions?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type WorldbookEntry = {
  id: number;
  project_id: number;
  book_id?: number | null;
  title: string;
  category: string;
  content: string;
  source_type?: string | null;
  source_ref?: string | null;
  created_at: string;
  updated_at: string;
};

export type WorldbookEntryCreatePayload = {
  book_id?: number | null;
  title: string;
  category?: string;
  content: string;
  source_type?: string | null;
  source_ref?: string | null;
};

export type WorldbookEntryUpdatePayload = Partial<WorldbookEntryCreatePayload>;

export type Chapter = {
  id: number;
  project_id: number;
  book_id?: number | null;
  chapter_no: number;
  title: string;
  summary?: string | null;
  objective?: string | null;
  conflict?: string | null;
  status: string;
  draft_content?: string | null;
  final_content?: string | null;
  word_count: number;
  /** 兼容字段：部分后端序列化层可能返回 camelCase 形态 */
  wordCount?: number;
  version: number;
  created_at: string;
  updated_at: string;
};

export type ChapterCreatePayload = {
  book_id?: number | null;
  chapter_no: number;
  title: string;
  summary?: string | null;
  objective?: string | null;
  conflict?: string | null;
  status?: string;
  draft_content?: string | null;
  final_content?: string | null;
  word_count?: number;
  version?: number;
};

export type ChapterPlan = {
  id: number;
  project_id: number;
  book_id?: number | null;
  chapter_id: number;
  plot_line_id?: number | null;
  title: string;
  design_brief: string;
  beat_sheet: string;
  asset_summary: string;
  selected_model?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type ChapterVersion = {
  id: number;
  project_id: number;
  chapter_id: number;
  version_no: number;
  operation_type: string;
  instruction?: string | null;
  consistency_report?: string | null;
  content: string;
  summary?: string | null;
  selected_model?: string | null;
  created_at: string;
};

export type EntityExtractionSummary = {
  added_entities: number;
  updated_entities: number;
  added_relationships: number;
  updated_relationships: number;
  characters: string[];
  worldbook_entries: string[];
  relationships: string[];
};

export type WorkflowStepDefinition = {
  step_no: number;
  name: string;
  objective: string;
  expected_output: string;
  tool_hints: string[];
};

export type WorkflowDefinition = {
  workflow_id: string;
  name: string;
  trigger: string;
  description: string;
  dependencies: string[];
  output: string;
  steps: WorkflowStepDefinition[];
};

export type AutoNovelWorkflowResult = {
  task: AITask;
  trend: TrendExploration;
  chapter: Chapter;
  version: ChapterVersion;
  consistency_report: string;
  consistency_model: string;
  rewrite_model: string;
  entity_extraction: EntityExtractionSummary;
  plot_lines: PlotLine[];
  characters: Character[];
  worldbook_entries: WorldbookEntry[];
};

export type AutoNovelWorkflowTaskResult = {
  task: AITask;
  steps?: TaskStep[];
};

export type FileInfo = {
  path: string;
  name: string;
  size: number;
  modified_at: string;
  file_type: string;
};

export type FileListResponse = {
  files: FileInfo[];
  total: number;
};

export type FileContentResponse = {
  path: string;
  content: string;
  metadata: Record<string, unknown>;
};

export type AgentEvent = {
  event_id?: number;
  event_type:
    | 'phase_start'
    | 'phase_end'
    | 'step_start'
    | 'step_end'
    | 'tool_call'
    | 'tool_result'
    | 'tool_error'
    | 'thinking'
    | 'text_delta'
    | 'user_message'
    | 'assistant_ack'
    | 'error'
    | 'done'
    | 'heartbeat'
    | string;
  task_id: number;
  phase?: string;
  step?: string;
  data?: Record<string, any>;
  timestamp?: string;
};

export type AgentToolErrorData = {
  tool?: string;
  error_code?: string;
  remediation?: string;
  severity?: 'warning' | 'error';
  [key: string]: any;
};
