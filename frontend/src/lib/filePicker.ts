// frontend/src/lib/filePicker.ts
// -------------------------------------------------------------------------
// 原生"另存为"对话框封装：优先用 window.showSaveFilePicker（Chromium 系
// Chrome/Edge/Opera 已稳定支持），让用户**主动选择**保存的文件夹与文件名。
// 浏览器不支持时降级为 <a download>，落到默认下载目录。
//
// 用户体验：点导出 → 弹菜单选格式 → 弹原生保存框 → 选好位置 → 文件直接
// 写到该位置。比"创建项目时输入导出路径"更直观，且每次都能换位置。
// -------------------------------------------------------------------------

export type SaveMode = "native" | "fallback";

export interface SaveBlobOptions {
  /** 默认文件名（含扩展名），如 "第01章_开篇.md" */
  suggestedName: string;
  /** 文件 MIME / 扩展名白名单，用于原生对话框的过滤器 */
  types?: Array<{ description?: string; accept: Record<string, string[]> }>;
  /** 描述文本（用于弹窗日志） */
  description?: string;
}

export interface SaveBlobResult {
  /** 实际写入方式 */
  mode: SaveMode;
  /** 用户最终保存的文件名（原生模式下由用户改写） */
  filename: string;
  /** 取消保存时为 true */
  cancelled: boolean;
}

/** 当前浏览器是否支持原生 showSaveFilePicker */
export function hasNativeSaveDialog(): boolean {
  return typeof window !== "undefined" && typeof (window as any).showSaveFilePicker === "function";
}

/**
 * 把 Blob 通过浏览器原生"另存为"对话框写到用户选定的位置。
 * 不支持时自动降级为 <a download>。
 *
 * @throws 当用户在原生对话框中取消时不抛错，返回 cancelled=true。
 * @throws 当其他错误（如权限被拒、磁盘满）时抛出。
 */
export async function saveBlobAs(blob: Blob, opts: SaveBlobOptions): Promise<SaveBlobResult> {
  if (hasNativeSaveDialog()) {
    try {
      const picker = (window as any).showSaveFilePicker as (options: any) => Promise<FileSystemFileHandle>;
      const handle = await picker({
        suggestedName: opts.suggestedName,
        types: opts.types,
        excludeAcceptAllOption: false,
      });
      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
      return {
        mode: "native",
        filename: handle.name || opts.suggestedName,
        cancelled: false,
      };
    } catch (err) {
      // 用户在原生对话框点"取消" -> err.name === "AbortError"
      if (err && (err as any).name === "AbortError") {
        return { mode: "native", filename: opts.suggestedName, cancelled: true };
      }
      // 其他错误（权限/Quota）-> 降级到 <a download>，但保留错误日志
      console.warn("[filePicker] showSaveFilePicker 失败，降级到 <a download>:", err);
    }
  }
  // 降级：<a download>，浏览器决定默认下载目录
  fallbackDownload(blob, opts.suggestedName);
  return { mode: "fallback", filename: opts.suggestedName, cancelled: false };
}

function fallbackDownload(blob: Blob, filename: string): void {
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  // 1s 后释放 URL（避免大文件回放时内存堆积）
  setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}

/** 根据扩展名推断 MIME，避免每次手写 */
export function guessMime(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  switch (ext) {
    case "md":
    case "markdown":
      return "text/markdown";
    case "txt":
      return "text/plain";
    case "docx":
      return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    case "pdf":
      return "application/pdf";
    case "zip":
      return "application/zip";
    case "json":
      return "application/json";
    case "html":
    case "htm":
      return "text/html";
    default:
      return "application/octet-stream";
  }
}

/** 给定文件名 + MIME，构造原生对话框用的 accept 规则 */
export function makeAcceptTypes(filename: string, mime?: string): Array<{ description: string; accept: Record<string, string[]> }> {
  const finalMime = mime ?? guessMime(filename);
  const ext = "." + (filename.split(".").pop() ?? "");
  return [{ description: `${finalMime} (${ext})`, accept: { [finalMime]: [ext] } }];
}
