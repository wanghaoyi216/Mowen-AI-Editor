import type {
  AITask,
  AutoNovelWorkflowTaskResult,
  CharacterEventParticipation,
  Chapter,
  ChapterPlan,
  ChapterVersion,
  FileContentResponse,
  FileInfo,
  FileListResponse,
  GraphPayload,
  PlotLine,
  PlotLineCreatePayload,
  PlotLineUpdatePayload,
  Project,
  ProjectCreatePayload,
  ProjectUpdatePayload,
  StoryEvent,
  TaskRuntimeState,
  TaskStep,
  TaskStepRuntimeState,
  TaskLog,
  TrendExploration,
  WorldbookEntry,
  WorldbookEntryCreatePayload,
  WorldbookEntryUpdatePayload,
  Character,
  CharacterCreatePayload,
  CharacterUpdatePayload,
  ChapterCreatePayload,
  EntityExtractionSummary,
  WorkflowDefinition,
} from "../types";
import { loadAuthSession } from "./auth";
import { saveBlobAs, makeAcceptTypes } from "./filePicker";

function resolveApiBaseUrl(): string {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && typeof envUrl === "string" && envUrl.trim() !== "") {
    return envUrl.trim();
  }

  // Use relative path so Vite proxy can forward requests to backend
  // In Docker: /api -> http://backend:8000/api (via Vite proxy)
  // In local dev without proxy: use absolute URL
  return "";
}

const API_BASE_URL = resolveApiBaseUrl();

function buildUrl(path: string): string {
  if (API_BASE_URL) {
    return `${API_BASE_URL}${path}`;
  }
  // Relative path with /api/v1 prefix so Vite proxy can forward to backend
  // Vite proxy rule: /api/* -> http://backend:8000/api/*
  return `/api/v1${path}`;
}

const DEFAULT_REQUEST_TIMEOUT_MS = 8000;
const LONG_REQUEST_TIMEOUT_MS = 90000;
const WORKFLOW_REQUEST_TIMEOUT_MS = 180000;

export function getApiBaseUrl(): string {
  return API_BASE_URL || "/api/v1";
}

export function logApiConfig(): void {
  // 仅在开发模式下打印
  if (import.meta.env.DEV) {
    console.log(
      `[API] 当前使用的 API 基础 URL: ${API_BASE_URL}`,
    );
    console.log(
      `[API] 环境变量 VITE_API_BASE_URL: ${import.meta.env.VITE_API_BASE_URL ?? "(未设置)"}`,
    );
  }
}

logApiConfig();

type ApiResponse<T> = {
  success: boolean;
  message: string;
  data: T;
  meta?: Record<string, unknown>;
};

function getErrorDetail(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string") {
    return detail;
  }
  const message = (payload as { message?: unknown }).message;
  return typeof message === "string" && message ? message : null;
}

async function apiFetch(
  url: string,
  label: string,
  init?: RequestInit,
  options?: { timeoutMs?: number; timeoutMessage?: string },
): Promise<Response> {
  const controller = new AbortController();
  const timeoutMs = options?.timeoutMs ?? DEFAULT_REQUEST_TIMEOUT_MS;
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(
        `${label}: ${options?.timeoutMessage ?? `请求超过 ${Math.round(timeoutMs / 1000)} 秒，后端仍未返回`}`,
      );
    }
    throw new Error(`${label}: 无法连接后端，请先启动 http://127.0.0.1:8000`);
  } finally {
    window.clearTimeout(timeoutId);
  }
}

async function requestJson<T>(
  url: string,
  label: string,
  init?: RequestInit,
  options?: { timeoutMs?: number; timeoutMessage?: string },
): Promise<ApiResponse<T>> {
  const session = loadAuthSession();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> || {}),
  };
  if (session?.token) {
    headers["Authorization"] = `Bearer ${session.token}`;
  }
  const response = await apiFetch(url, label, { ...init, headers }, options);

  if (!response.ok) {
    let detail: string | null = null;
    try {
      detail = getErrorDetail(await response.json());
    } catch {
      detail = null;
    }
    throw new Error(detail ? `${label}: ${detail}` : `${label}: ${response.status}`);
  }
  return (await response.json()) as ApiResponse<T>;
}

async function authedFetch(
  url: string,
  label: string,
  init?: RequestInit,
  options?: { timeoutMs?: number; timeoutMessage?: string },
): Promise<Response> {
  const session = loadAuthSession();
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> || {}),
  };
  if (session?.token) {
    headers["Authorization"] = `Bearer ${session.token}`;
  }
  return apiFetch(url, label, { ...init, headers }, options);
}

export async function fetchProjectGraph(
  projectId: number,
  options?: { graphType?: string; chapterId?: number | null; bookId?: number | null },
): Promise<GraphPayload> {
  const params = new URLSearchParams();
  if (options?.graphType) {
    params.set("graph_type", options.graphType);
  }
  if (options?.chapterId) {
    params.set("chapter_id", String(options.chapterId));
  }
  if (options?.bookId) {
    params.set("book_id", String(options.bookId));
  }

  const query = params.toString();
  const url = buildUrl(`/projects/${projectId}/graph${query ? `?${query}` : ""}`);
  const response = await authedFetch(url, "Graph request failed");
  if (!response.ok) {
    throw new Error(`Graph request failed: ${response.status}`);
  }

  const payload = (await response.json()) as ApiResponse<GraphPayload>;
  return payload.data;
}

export async function fetchProjects(): Promise<Project[]> {
  const payload = await requestJson<Project[]>(buildUrl("/projects"), "Projects request failed");
  return payload.data;
}

export async function createProject(payload: ProjectCreatePayload): Promise<Project> {
  const result = await requestJson<Project>(buildUrl("/projects"), "Project create request failed", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return result.data;
}

export async function exportChapter(projectId: number, chapterId: number): Promise<Blob> {
  const url = buildUrl(`/projects/${projectId}/chapters/${chapterId}/export`);
  const response = await apiFetch(url, "Chapter export request failed", {
    headers: { Accept: "text/markdown" },
  });
  if (!response.ok) {
    throw new Error(`Chapter export request failed: ${response.status}`);
  }
  return await response.blob();
}

// ---------------------------------------------------------------------------
// 章节导出（多格式：md | docx | pdf | txt）
// ---------------------------------------------------------------------------
export type ChapterExportFormat = "md" | "docx" | "pdf" | "txt";

export async function listChapterExportFormats(
  projectId: number,
  chapterId: number,
): Promise<ChapterExportFormat[]> {
  const result = await requestJson<{ formats: ChapterExportFormat[] }>(
    buildUrl(`/projects/${projectId}/chapters/${chapterId}/export/formats`),
    "List chapter export formats failed",
  );
  return result.data?.formats ?? ["md"];
}

export async function exportChapterAs(
  projectId: number,
  chapterId: number,
  format: ChapterExportFormat = "md",
): Promise<Blob> {
  const url = buildUrl(
    `/projects/${projectId}/chapters/${chapterId}/export?format=${encodeURIComponent(format)}`,
  );
  const response = await apiFetch(url, "Chapter export request failed", {
    headers: { Accept: "*/*" },
  });
  if (!response.ok) {
    throw new Error(`Chapter export request failed: ${response.status}`);
  }
  return await response.blob();
}

export function downloadBlob(blob: Blob, filename: string): void {
  // 走 filePicker：浏览器支持时弹原生"另存为"对话框由用户挑位置，
  // 不支持时降级为 <a download> 落到默认下载目录。
  // 这里用 void 忽略 Promise（下载流程为 fire-and-forget，错误由 picker 内部 console.warn）。
  void saveBlobAs(blob, { suggestedName: filename, types: makeAcceptTypes(filename) });
}

export async function exportProjectArchive(projectId: number): Promise<Blob> {
  const url = buildUrl(`/projects/${projectId}/exports/archive`);
  const response = await apiFetch(url, "Project export request failed", {
    headers: { Accept: "application/zip" },
  }, {
    timeoutMs: LONG_REQUEST_TIMEOUT_MS,
    timeoutMessage: "项目归档导出耗时过长，请稍后在 exports 目录查看",
  });
  if (!response.ok) {
    throw new Error(`Project export request failed: ${response.status}`);
  }
  return await response.blob();
}

/**
 * 按"项目→任务→章节→小节→每小节的内容.md"层级结构导出
 * 返回 Blob (ZIP) + 后端返回的 export 路径信息
 */
export interface ChapterHierarchyExport {
  blob: Blob;
  filename: string;
  exportDir: string;
  archivePath: string;
  taskTypes: string[];
  projectName: string;
}

export async function exportChapterHierarchy(
  projectId: number,
): Promise<ChapterHierarchyExport> {
  const url = buildUrl(`/projects/${projectId}/exports/chapter-hierarchy`);
  const response = await apiFetch(url, "Chapter hierarchy export request failed", {
    headers: { Accept: "application/zip" },
  }, {
    timeoutMs: LONG_REQUEST_TIMEOUT_MS,
    timeoutMessage: "章节层级导出耗时过长，请稍后在 exports 目录查看",
  });
  if (!response.ok) {
    throw new Error(`Chapter hierarchy export failed: ${response.status}`);
  }
  // 先用 HEAD 拿 Content-Disposition 不现实；直接用 response.headers 取
  // 然后再调一次 POST 拿 JSON 元数据（也可以用 baseUrl+path 直接 GET ZIP 链接）
  // 这里简化：从 blob URL 用 <a download> 触发下载
  const blob = await response.blob();
  const cd = response.headers.get("Content-Disposition") || "";
  const m = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(cd);
  const filename = m ? decodeURIComponent(m[1]) : `novel-export-${projectId}-${Date.now()}.zip`;
  return {
    blob,
    filename,
    exportDir: "",
    archivePath: "",
    taskTypes: [],
    projectName: "",
  };
}

export async function exportProjectFiles(projectId: number): Promise<{
  project_id: number;
  project_name: string;
  export_dir: string;
  whole_book: string;
  chapter_files: string[];
  assets_dir: string;
  workflow_logs_dir: string;
}> {
  const result = await requestJson<{
    project_id: number;
    project_name: string;
    export_dir: string;
    whole_book: string;
    chapter_files: string[];
    assets_dir: string;
    workflow_logs_dir: string;
  }>(
    buildUrl(`/projects/${projectId}/exports/files`),
    "Project files export request failed",
    { method: "POST" },
    {
      timeoutMs: LONG_REQUEST_TIMEOUT_MS,
      timeoutMessage: "项目文件导出耗时过长，请稍后刷新文件列表",
    },
  );
  return result.data;
}

export async function listProjectFiles(
  projectId: number,
  fileType?: string,
): Promise<FileInfo[]> {
  const params = new URLSearchParams();
  if (fileType) {
    params.set("file_type", fileType);
  }
  const query = params.toString();
  const response = await authedFetch(
    buildUrl(`/projects/${projectId}/files${query ? `?${query}` : ""}`),
    "List project files failed",
  );
  if (!response.ok) {
    throw new Error(`List project files failed: ${response.status}`);
  }
  const payload = (await response.json()) as ApiResponse<FileListResponse>;
  return payload.data.files;
}

export async function getProjectFileContent(
  projectId: number,
  filePath: string,
): Promise<FileContentResponse> {
  const encodedPath = filePath.split("/").map(encodeURIComponent).join("/");
  const response = await authedFetch(
    buildUrl(`/projects/${projectId}/files/${encodedPath}`),
    "Get project file content failed",
  );
  if (!response.ok) {
    throw new Error(`Get project file content failed: ${response.status}`);
  }
  const payload = (await response.json()) as ApiResponse<FileContentResponse>;
  return payload.data;
}

export async function updateProject(projectId: number, payload: ProjectUpdatePayload): Promise<Project> {
  const result = await requestJson<Project>(buildUrl(`/projects/${projectId}`), "Project update request failed", {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return result.data;
}

export async function deleteProject(projectId: number): Promise<void> {
  await requestJson<{ id: number }>(buildUrl(`/projects/${projectId}`), "Project delete request failed", {
    method: "DELETE",
  });
}

export async function fetchCharacters(projectId: number): Promise<Character[]> {
  const payload = await requestJson<Character[]>(
    buildUrl(`/projects/${projectId}/characters`),
    "Characters request failed",
  );
  return payload.data;
}

export async function createCharacter(projectId: number, payload: CharacterCreatePayload): Promise<Character> {
  const result = await requestJson<Character>(
    buildUrl(`/projects/${projectId}/characters`),
    "Character create request failed",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    },
  );
  return result.data;
}

export async function updateCharacter(
  projectId: number,
  characterId: number,
  payload: CharacterUpdatePayload,
): Promise<Character> {
  const result = await requestJson<Character>(
    buildUrl(`/projects/${projectId}/characters/${characterId}`),
    "Character update request failed",
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    },
  );
  return result.data;
}

export async function deleteCharacter(projectId: number, characterId: number): Promise<void> {
  await requestJson<{ id: number }>(
    buildUrl(`/projects/${projectId}/characters/${characterId}`),
    "Character delete request failed",
    {
      method: "DELETE",
    },
  );
}

export async function fetchPlotLines(projectId: number): Promise<PlotLine[]> {
  const response = await authedFetch(buildUrl(`/projects/${projectId}/plot-lines`), "Plot lines request failed");
  if (!response.ok) {
    throw new Error(`Plot lines request failed: ${response.status}`);
  }

  const payload = (await response.json()) as ApiResponse<PlotLine[]>;
  return payload.data;
}

export async function createPlotLine(projectId: number, payload: PlotLineCreatePayload): Promise<PlotLine> {
  const result = await requestJson<PlotLine>(
    buildUrl(`/projects/${projectId}/plot-lines`),
    "Plot line create request failed",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    },
  );
  return result.data;
}

export async function updatePlotLine(
  projectId: number,
  plotLineId: number,
  payload: PlotLineUpdatePayload,
): Promise<PlotLine> {
  const result = await requestJson<PlotLine>(
    buildUrl(`/projects/${projectId}/plot-lines/${plotLineId}`),
    "Plot line update request failed",
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    },
  );
  return result.data;
}

export async function deletePlotLine(projectId: number, plotLineId: number): Promise<void> {
  await requestJson<{ id: number }>(
    buildUrl(`/projects/${projectId}/plot-lines/${plotLineId}`),
    "Plot line delete request failed",
    {
      method: "DELETE",
    },
  );
}

export async function fetchStoryEvents(projectId: number): Promise<StoryEvent[]> {
  const response = await authedFetch(buildUrl(`/projects/${projectId}/events`), "Story events request failed");
  if (!response.ok) {
    throw new Error(`Story events request failed: ${response.status}`);
  }

  const payload = (await response.json()) as ApiResponse<StoryEvent[]>;
  return payload.data;
}

export async function fetchEventParticipations(
  projectId: number,
): Promise<CharacterEventParticipation[]> {
  const response = await authedFetch(buildUrl(`/projects/${projectId}/event-participations`), "Event participations request failed");
  if (!response.ok) {
    throw new Error(`Event participations request failed: ${response.status}`);
  }

  const payload = (await response.json()) as ApiResponse<CharacterEventParticipation[]>;
  return payload.data;
}

export async function fetchTaskRuntime(
  projectId: number,
  taskId: number,
): Promise<TaskRuntimeState | null> {
  const response = await authedFetch(buildUrl(`/projects/${projectId}/tasks/${taskId}/runtime`), "Task runtime request failed");
  if (!response.ok) {
    throw new Error(`Task runtime request failed: ${response.status}`);
  }

  const payload = (await response.json()) as ApiResponse<TaskRuntimeState | null>;
  return payload.data;
}

// ---------------------------------------------------------------------------
// 任务工具错误（B3）—— 编排链在工具返回 error_code 时累计的警告列表
// 后端：GET /projects/{id}/tasks/{task_id}/tool-errors
// ---------------------------------------------------------------------------
export type ToolError = {
  tool: string;
  error_code: string;
  remediation: string;
  phase?: string;
  severity?: string;
  timestamp?: string;
};

export type ToolErrorsResponse = {
  tool_errors: ToolError[];
  count: number;
};

export async function fetchTaskToolErrors(
  projectId: number,
  taskId: number,
): Promise<ToolErrorsResponse> {
  const response = await authedFetch(buildUrl(`/projects/${projectId}/tasks/${taskId}/tool-errors`), "Task tool errors request failed");
  if (!response.ok) {
    throw new Error(`Task tool errors request failed: ${response.status}`);
  }
  const payload = (await response.json()) as ApiResponse<ToolErrorsResponse>;
  return payload.data ?? { tool_errors: [], count: 0 };
}

export async function fetchTasks(projectId: number, chapterId?: number | null): Promise<AITask[]> {
  const params = new URLSearchParams();
  if (chapterId) {
    params.set("chapter_id", String(chapterId));
  }
  const query = params.toString();
  const response = await authedFetch(buildUrl(`/projects/${projectId}/tasks${query ? `?${query}` : ""}`), "Tasks request failed");
  if (!response.ok) {
    throw new Error(`Tasks request failed: ${response.status}`);
  }
  const payload = (await response.json()) as ApiResponse<AITask[]>;
  return payload.data;
}

export async function createAITask(
  projectId: number,
  payload: {
    title: string;
    query_text: string;
    chapter_id?: number | null;
    chapter_no?: number;
    chapter_title?: string;
    style_hint?: string;
    word_target?: number;
    book_id?: number | null;
  },
): Promise<AutoNovelWorkflowTaskResult> {
  const result = await requestJson<AutoNovelWorkflowTaskResult>(
    buildUrl(`/projects/${projectId}/tasks/execute-auto-novel-workflow`),
    "Create AI task failed",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: payload.title,
        query_text: payload.query_text,
        source_scope: "web",
        search_depth: "advanced",
        max_results: 5,
        chapter_id: payload.chapter_id ?? null,
        chapter_no: payload.chapter_no ?? 1,
        chapter_title: payload.chapter_title ?? "自动生成章节",
        style_hint: payload.style_hint ?? null,
        word_target: payload.word_target ?? 1800,
        book_id: payload.book_id ?? null,
      }),
    },
    { timeoutMs: WORKFLOW_REQUEST_TIMEOUT_MS, timeoutMessage: "AI 工作流启动超时，请检查 OpenRouter API Key 配置" },
  );
  return result.data;
}

export async function fetchAITasks(projectId: number): Promise<AITask[]> {
  return fetchTasks(projectId);
}

export async function deleteAITask(projectId: number, taskId: number): Promise<void> {
  await requestJson<{ id: number }>(
    buildUrl(`/projects/${projectId}/tasks/${taskId}`),
    "AI task delete request failed",
    {
      method: "DELETE",
    },
  );
}

export async function cancelAITask(projectId: number, taskId: number): Promise<unknown> {
  return requestJson<unknown>(
    buildUrl(`/projects/${projectId}/tasks/${taskId}/cancel`),
    "AI task cancel request failed",
    {
      method: "POST",
    },
  );
}

export async function sendTaskMessage(
  projectId: number,
  taskId: number,
  message: string,
): Promise<{ task_id: number; accepted: boolean; queued: boolean }> {
  const result = await requestJson<{ task_id: number; accepted: boolean; queued: boolean }>(
    buildUrl(`/projects/${projectId}/tasks/${taskId}/message`),
    "Send message failed",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    },
  );
  return result.data;
}

export async function generateKnowledgeGraph(projectId: number): Promise<{
  status: string;
  added_relationships?: number;
  added_events?: number;
  added_arcs?: number;
  added_themes?: number;
  model?: unknown;
  reason?: string;
}> {
  const result = await requestJson<{
    status: string;
    added_relationships?: number;
    added_events?: number;
    added_arcs?: number;
    added_themes?: number;
    model?: unknown;
    reason?: string;
  }>(
    buildUrl(`/projects/${projectId}/graph/generate`),
    "Generate knowledge graph failed",
    { method: "POST" },
    {
      timeoutMs: WORKFLOW_REQUEST_TIMEOUT_MS,
      timeoutMessage: "知识图谱生成耗时较长，请稍后在图谱页面刷新查看",
    },
  );
  return result.data;
}

export async function fetchAvailableModels(projectId: number): Promise<unknown> {
  return requestJson<unknown>(
    buildUrl(`/projects/${projectId}/tasks/models`),
    "Models list request failed",
  );
}

export async function fetchTaskConcurrency(projectId: number): Promise<unknown> {
  return requestJson<unknown>(
    buildUrl(`/projects/${projectId}/tasks/concurrency`),
    "Concurrency status request failed",
  );
}

// === 类型化封装（Task 1 / Task 2） ===
// 后端返回结构化数据（详见 .trae/specs/comprehensive-assessment），下面提供类型化封装供 UI 直接消费。
export type ModelsInfo = {
  primary?: string | null;
  fallback_chain?: string[];
  provider?: string | null;
  features?: {
    rate_limit_per_minute?: number | null;
    [key: string]: unknown;
  };
  model_info?: Record<string, unknown>;
};

export type ConcurrencyInfo = {
  max_concurrent?: number;
  current_running?: number;
  current_pending?: number;
  available_slots?: number;
  by_status?: Record<string, number>;
};

// 类型化包装：在原有 fetchAvailableModels 之上做最小化结构校验。
export async function fetchAvailableModelsTyped(projectId: number): Promise<ModelsInfo | null> {
  try {
    const resp = await fetchAvailableModels(projectId);
    const payload = (resp as { data?: unknown }).data ?? resp;
    if (!payload || typeof payload !== "object") return null;
    return payload as ModelsInfo;
  } catch {
    return null;
  }
}

export async function fetchTaskConcurrencyTyped(projectId: number): Promise<ConcurrencyInfo | null> {
  try {
    const resp = await fetchTaskConcurrency(projectId);
    const payload = (resp as { data?: unknown }).data ?? resp;
    if (!payload || typeof payload !== "object") return null;
    return payload as ConcurrencyInfo;
  } catch {
    return null;
  }
}

export async function fetchTask(projectId: number, taskId: number): Promise<AITask | null> {
  const response = await authedFetch(buildUrl(`/projects/${projectId}/tasks/${taskId}`), "Task request failed");
  if (!response.ok) {
    throw new Error(`Task request failed: ${response.status}`);
  }
  const payload = (await response.json()) as ApiResponse<AITask | null>;
  return payload.data;
}

export async function fetchTaskSteps(projectId: number, taskId: number): Promise<TaskStep[]> {
  const response = await authedFetch(buildUrl(`/projects/${projectId}/tasks/${taskId}/steps`), "Task steps request failed");
  if (!response.ok) {
    throw new Error(`Task steps request failed: ${response.status}`);
  }
  const payload = (await response.json()) as ApiResponse<TaskStep[]>;
  return payload.data;
}

export async function fetchTaskLogs(projectId: number, taskId: number, limit: number = 200): Promise<TaskLog[]> {
  const response = await authedFetch(buildUrl(`/projects/${projectId}/tasks/${taskId}/logs?limit=${limit}`), "Task logs request failed");
  if (!response.ok) {
    throw new Error(`Task logs request failed: ${response.status}`);
  }
  const payload = (await response.json()) as ApiResponse<TaskLog[]>;
  return payload.data;
}

export async function fetchTaskStepRuntime(
  projectId: number,
  taskId: number,
): Promise<TaskStepRuntimeState[]> {
  const response = await authedFetch(buildUrl(`/projects/${projectId}/tasks/${taskId}/step-runtime`), "Task step runtime request failed");
  if (!response.ok) {
    throw new Error(`Task step runtime request failed: ${response.status}`);
  }

  const payload = (await response.json()) as ApiResponse<TaskStepRuntimeState[]>;
  return payload.data;
}

export async function controlTaskRuntime(
  projectId: number,
  taskId: number,
  action: "pause" | "resume" | "stop",
): Promise<TaskRuntimeState> {
  const result = await requestJson<TaskRuntimeState>(
    buildUrl(`/projects/${projectId}/tasks/${taskId}/control`),
    "Task control request failed",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ action }),
    },
  );
  return result.data;
}

export async function resumeAITask(projectId: number, taskId: number): Promise<unknown> {
  const result = await requestJson<unknown>(
    buildUrl(`/projects/${projectId}/tasks/${taskId}/resume`),
    "AI task resume request failed",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    },
  );
  return result.data;
}

export async function fetchTrendExplorations(projectId: number): Promise<TrendExploration[]> {
  const payload = await requestJson<TrendExploration[]>(
    buildUrl(`/projects/${projectId}/trend-explorations`),
    "Trend explorations request failed",
  );
  return payload.data;
}

export async function executeTrendExploration(projectId: number, title: string, queryText: string) {
  const payload = await requestJson<TrendExploration>(
    buildUrl(`/projects/${projectId}/trend-explorations/execute`),
    "Trend execute request failed",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        title,
        query_text: queryText,
        source_scope: "web",
        search_depth: "advanced",
        max_results: 5,
      }),
    },
    {
      timeoutMs: LONG_REQUEST_TIMEOUT_MS,
      timeoutMessage: "热点探索仍在等待外部搜索服务返回，请稍后重试或检查 Tavily/网络配置",
    },
  );
  return payload.data;
}

export async function executeAutoNovelWorkflow(
  projectId: number,
  payload: {
    title: string;
    queryText: string;
    chapterId?: number | null;
    chapterNo?: number;
    chapterTitle?: string;
    chapterSummary?: string | null;
    chapterObjective?: string | null;
    chapterConflict?: string | null;
    designGuidance?: string | null;
    styleHint?: string | null;
    revisionFocus?: string | null;
    wordTarget?: number;
    bookId?: number | null;
  },
): Promise<AutoNovelWorkflowTaskResult> {
  const result = await requestJson<AutoNovelWorkflowTaskResult>(
    buildUrl(`/projects/${projectId}/tasks/execute-auto-novel-workflow`),
    "Auto workflow request failed",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        title: payload.title,
        query_text: payload.queryText,
        source_scope: "web",
        search_depth: "advanced",
        max_results: 5,
        chapter_id: payload.chapterId ?? null,
        chapter_no: payload.chapterNo ?? 1,
        chapter_title: payload.chapterTitle ?? "自动生成章节",
        chapter_summary: payload.chapterSummary ?? null,
        chapter_objective: payload.chapterObjective ?? null,
        chapter_conflict: payload.chapterConflict ?? null,
        design_guidance: payload.designGuidance ?? null,
        style_hint: payload.styleHint ?? null,
        revision_focus: payload.revisionFocus ?? null,
        word_target: payload.wordTarget ?? 1800,
        book_id: payload.bookId ?? null,
      }),
    },
    {
      timeoutMs: WORKFLOW_REQUEST_TIMEOUT_MS,
      timeoutMessage: "一键自动创作流程耗时过长，请检查外部搜索和模型服务配置",
    },
  );
  return result.data;
}

export async function fetchWorkflows(projectId: number): Promise<WorkflowDefinition[]> {
  const payload = await requestJson<WorkflowDefinition[]>(
    buildUrl(`/projects/${projectId}/workflows`),
    "Workflows request failed",
  );
  return payload.data;
}

export async function executeWorkflow(
  projectId: number,
  workflowId: string,
  payload?: {
    objective?: string | null;
    maxSteps?: number;
    workflowExecutionId?: string | null;
    hyperparameters?: Record<string, unknown> | null;
  },
): Promise<{ workflow: WorkflowDefinition; task: AITask; steps: TaskStep[]; idempotent_replay: boolean }> {
  const result = await requestJson<{
    workflow: WorkflowDefinition;
    task: AITask;
    steps: TaskStep[];
    idempotent_replay: boolean;
  }>(
    buildUrl(`/projects/${projectId}/workflows/${workflowId}/execute`),
    "Workflow execute request failed",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        objective: payload?.objective ?? null,
        max_steps: payload?.maxSteps ?? 3,
        workflow_execution_id: payload?.workflowExecutionId ?? null,
        hyperparameters: payload?.hyperparameters ?? null,
      }),
    },
    {
      timeoutMs: WORKFLOW_REQUEST_TIMEOUT_MS,
      timeoutMessage: "Workflow 执行耗时过长，请检查外部服务配置或运行态状态",
    },
  );
  return result.data;
}

export async function mapTrendAssets(projectId: number, trendId: number): Promise<{
  trend: TrendExploration;
  plot_lines: PlotLine[];
  characters: Character[];
  worldbook_entries: WorldbookEntry[];
}> {
  const payload = await requestJson<{
    trend: TrendExploration;
    plot_lines: PlotLine[];
    characters: Character[];
    worldbook_entries: WorldbookEntry[];
  }>(
    buildUrl(`/projects/${projectId}/trend-explorations/map-assets`),
    "Trend map request failed",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        trend_id: trendId,
        create_plot_lines: true,
        create_character_candidates: true,
        create_worldbook_entries: true,
      }),
    },
  );
  return payload.data;
}

export async function fetchWorldbookEntries(projectId: number): Promise<WorldbookEntry[]> {
  const payload = await requestJson<WorldbookEntry[]>(
    buildUrl(`/projects/${projectId}/worldbook`),
    "Worldbook request failed",
  );
  return payload.data;
}

export async function createWorldbookEntry(
  projectId: number,
  payload: WorldbookEntryCreatePayload,
): Promise<WorldbookEntry> {
  const result = await requestJson<WorldbookEntry>(
    buildUrl(`/projects/${projectId}/worldbook`),
    "Worldbook create request failed",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    },
  );
  return result.data;
}

export async function updateWorldbookEntry(
  projectId: number,
  entryId: number,
  payload: WorldbookEntryUpdatePayload,
): Promise<WorldbookEntry> {
  const result = await requestJson<WorldbookEntry>(
    buildUrl(`/projects/${projectId}/worldbook/${entryId}`),
    "Worldbook update request failed",
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    },
  );
  return result.data;
}

export async function deleteWorldbookEntry(projectId: number, entryId: number): Promise<void> {
  await requestJson<{ id: number }>(
    buildUrl(`/projects/${projectId}/worldbook/${entryId}`),
    "Worldbook delete request failed",
    {
      method: "DELETE",
    },
  );
}

export async function fetchChapters(projectId: number): Promise<Chapter[]> {
  const response = await authedFetch(buildUrl(`/projects/${projectId}/chapters`), "Chapters request failed");
  if (!response.ok) {
    throw new Error(`Chapters request failed: ${response.status}`);
  }
  const payload = (await response.json()) as ApiResponse<Chapter[]>;
  return payload.data;
}

export async function createChapter(projectId: number, payload: ChapterCreatePayload): Promise<Chapter> {
  const result = await requestJson<Chapter>(
    buildUrl(`/projects/${projectId}/chapters`),
    "Chapter create request failed",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        ...payload,
        status: payload.status ?? "planned",
        word_count: payload.word_count ?? 0,
        version: payload.version ?? 1,
      }),
    },
  );
  return result.data;
}

export async function fetchChapterVersions(projectId: number, chapterId: number): Promise<ChapterVersion[]> {
  const response = await authedFetch(buildUrl(`/projects/${projectId}/chapters/${chapterId}/versions`), "Chapter versions request failed");
  if (!response.ok) {
    throw new Error(`Chapter versions request failed: ${response.status}`);
  }
  const payload = (await response.json()) as ApiResponse<ChapterVersion[]>;
  return payload.data;
}

export async function designChapter(
  projectId: number,
  chapterId: number,
  payload?: { plotLineId?: number | null; guidance?: string | null },
): Promise<ChapterPlan> {
  const response = await authedFetch(buildUrl(`/projects/${projectId}/chapters/${chapterId}/design`), "Chapter design request failed", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      plot_line_id: payload?.plotLineId ?? null,
      guidance: payload?.guidance ?? null,
    }),
  });
  if (!response.ok) {
    throw new Error(`Chapter design request failed: ${response.status}`);
  }
  const result = (await response.json()) as ApiResponse<ChapterPlan>;
  return result.data;
}

export async function designChapterTask(
  projectId: number,
  chapterId: number,
  payload?: { plotLineId?: number | null; guidance?: string | null },
): Promise<{ task_id: number; plan: ChapterPlan }> {
  const response = await authedFetch(buildUrl(`/projects/${projectId}/chapters/${chapterId}/design-task`), "Chapter design task request failed", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      plot_line_id: payload?.plotLineId ?? null,
      guidance: payload?.guidance ?? null,
    }),
  });
  if (!response.ok) {
    throw new Error(`Chapter design task request failed: ${response.status}`);
  }
  const result = (await response.json()) as ApiResponse<{ task_id: number; plan: ChapterPlan }>;
  return result.data;
}

export async function generateChapterDraft(
  projectId: number,
  chapterId: number,
  payload?: { styleHint?: string | null; wordTarget?: number },
): Promise<Chapter> {
  const response = await authedFetch(buildUrl(`/projects/${projectId}/chapters/${chapterId}/generate`), "Chapter generate request failed", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      style_hint: payload?.styleHint ?? null,
      word_target: payload?.wordTarget ?? 1500,
    }),
  });
  if (!response.ok) {
    throw new Error(`Chapter generate request failed: ${response.status}`);
  }
  const result = (await response.json()) as ApiResponse<Chapter>;
  return result.data;
}

export async function generateChapterDraftTask(
  projectId: number,
  chapterId: number,
  payload?: { styleHint?: string | null; wordTarget?: number },
): Promise<{ task_id: number; chapter: Chapter }> {
  const response = await authedFetch(buildUrl(`/projects/${projectId}/chapters/${chapterId}/generate-task`), "Chapter generate task request failed", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      style_hint: payload?.styleHint ?? null,
      word_target: payload?.wordTarget ?? 1500,
    }),
  });
  if (!response.ok) {
    throw new Error(`Chapter generate task request failed: ${response.status}`);
  }
  const result = (await response.json()) as ApiResponse<{ task_id: number; chapter: Chapter }>;
  return result.data;
}

export async function runChapterConsistencyCheck(
  projectId: number,
  chapterId: number,
): Promise<{ task_id: number; model: string; report: string }> {
  const response = await authedFetch(
    buildUrl(`/projects/${projectId}/chapters/${chapterId}/consistency-check`),
    "Chapter consistency request failed",
    {
      method: "POST",
    },
  );
  if (!response.ok) {
    throw new Error(`Chapter consistency request failed: ${response.status}`);
  }
  const result = (await response.json()) as ApiResponse<{ task_id: number; model: string; report: string }>;
  return result.data;
}

export async function reviseChapterDraftTask(
  projectId: number,
  chapterId: number,
  payload?: { revisionFocus?: string | null; styleHint?: string | null; wordTarget?: number },
): Promise<{
  task_id: number;
  chapter: Chapter;
  version: ChapterVersion;
  consistency_report: string;
  consistency_model: string;
  rewrite_model: string;
  entity_extraction: EntityExtractionSummary;
}> {
  const response = await authedFetch(buildUrl(`/projects/${projectId}/chapters/${chapterId}/revise-task`), "Chapter revision task request failed", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      revision_focus: payload?.revisionFocus ?? null,
      style_hint: payload?.styleHint ?? null,
      word_target: payload?.wordTarget ?? 1500,
    }),
  });
  if (!response.ok) {
    throw new Error(`Chapter revision task request failed: ${response.status}`);
  }
  const result = (await response.json()) as ApiResponse<{
    task_id: number;
    chapter: Chapter;
    version: ChapterVersion;
    consistency_report: string;
    consistency_model: string;
    rewrite_model: string;
    entity_extraction: EntityExtractionSummary;
  }>;
  return result.data;
}

// ---------------------------------------------------------------------------
// 故事脉络 (Story Arc) —— Tab7 数据源
// ---------------------------------------------------------------------------
export type StoryArcNodeType =
  | "chapter"
  | "climax"
  | "turning_point"
  | "conflict"
  | "ending"
  | "scene"
  | "plot_line";

export type StoryArcNode = {
  id: string;
  type: StoryArcNodeType;
  label: string;
  chapterNo?: number | null;
  theme?: string;
  emotionalArc?: string;
  status?: string;
  wordCount?: number;
  plotLineId?: number;
  plotType?: string;
  sceneOrder?: number;
};

export type StoryArcEdge = {
  source: string;
  target: string;
  relation: "sequel_to" | "leads_to" | "conflicts_with" | "resolves";
  weight: number;
};

export type StoryArcStats = {
  chapters: number;
  plotLines: number;
  plans: number;
  scenes?: number;
  emotionalArc?: Record<string, number>;
  wordCountByChapter?: Array<{ chapterNo: number; wordCount: number }>;
  orphanScenes?: number;
  generatedAt?: string;
  version?: number;
};

export type StoryArcPayload = {
  // Task A2.3 — bookId 元字段（与请求参数一致），方便前端定位"book 错"还是"项目空"
  bookId?: number | null;
  nodes: StoryArcNode[];
  edges: StoryArcEdge[];
  stats: StoryArcStats;
};

export async function fetchStoryArc(projectId: number, bookId?: number | null): Promise<StoryArcPayload> {
  const params = new URLSearchParams();
  if (bookId) {
    params.set("book_id", String(bookId));
  }
  const query = params.toString();
  const url = buildUrl(`/projects/${projectId}/story-arc${query ? `?${query}` : ""}`);
  const response = await authedFetch(url, "Story arc request failed");
  if (!response.ok) {
    throw new Error(`Story arc request failed: ${response.status}`);
  }
  const payload = (await response.json()) as ApiResponse<StoryArcPayload>;
  return payload.data;
}

// ---------------------------------------------------------------------------
// Book 概念（Task 4/5/7/8）— 每个 project 下可有 ≥1 本书
// ---------------------------------------------------------------------------
export interface Book {
  id: number;
  project_id: number;
  name: string;
  description?: string;
  order_index: number;
  created_at: string;
  updated_at: string;
}

export async function fetchBooks(projectId: number): Promise<Book[]> {
  const result = await requestJson<Book[]>(
    buildUrl(`/projects/${projectId}/books`),
    "Books request failed",
  );
  const data = result.data as unknown;
  if (Array.isArray(data)) {
    return data as Book[];
  }
  if (data && typeof data === "object" && Array.isArray((data as { books?: unknown }).books)) {
    return (data as { books: Book[] }).books;
  }
  return [];
}

export async function createBook(
  projectId: number,
  name: string,
  description?: string,
): Promise<Book> {
  const result = await requestJson<Book>(
    buildUrl(`/projects/${projectId}/books`),
    "Book create request failed",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description }),
    },
  );
  return result.data;
}

// ---------------------------------------------------------------------------
// 驾驶舱 (Dashboard) —— Tab8 数据源
// ---------------------------------------------------------------------------
export type DashboardKpi = {
  completedChapters: number;
  totalChapters: number;
  totalWords: number;
  avgLatencyMs: number;
  totalDurationSeconds: number;
  progressPercent: number;
};

export type DashboardPayload = {
  kpi: DashboardKpi;
  chapterProgress: Array<{ chapterNo: number; status: string; wordCount: number }>;
  wordCountBar: Array<{ chapterNo: number; words: number }>;
  latencyHist: Array<{ bucket: string; count: number }>;
  characterFreq: Array<{ name: string; count: number }>;
  consistencyRadar: { character: number; plot: number; world: number; pacing: number; style: number };
  genreDistribution: Array<{ genre: string; count: number }>;
  novel: { id: number; title: string; genre: string } | null;
};

export async function fetchDashboard(projectId: number): Promise<DashboardPayload> {
  const response = await authedFetch(buildUrl(`/projects/${projectId}/dashboard`), "Dashboard request failed");
  if (!response.ok) {
    throw new Error(`Dashboard request failed: ${response.status}`);
  }
  const payload = (await response.json()) as ApiResponse<DashboardPayload>;
  return payload.data;
}

// ---------------------------------------------------------------------------
// 章节小结 (Chapter Scenes) —— 每章下的 3-7 个 scene
// ---------------------------------------------------------------------------
export type ChapterScene = {
  id: number;
  scene_no: number;
  title: string;
  summary: string | null;
  goal: string | null;
  conflict: string | null;
  characters_present: string[];
  emotional_tone: string | null;
  status: string;
  word_count?: number | null;
  pov?: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export async function fetchChapterScenes(
  projectId: number,
  chapterId: number,
): Promise<{ scenes: ChapterScene[]; total: number }> {
  const response = await authedFetch(
    buildUrl(`/projects/${projectId}/chapters/${chapterId}/scenes`),
    "Chapter scenes request failed",
  );
  if (!response.ok) {
    throw new Error(`Chapter scenes request failed: ${response.status}`);
  }
  const payload = (await response.json()) as ApiResponse<{ scenes: ChapterScene[]; total: number }>;
  return payload.data;
}
