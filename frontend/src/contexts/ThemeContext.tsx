/**
 * 主题系统 Context
 * --------------------------------------------------------------
 * 职责：
 * 1) 维护预设主题（6 张水墨图）+ 用户自定义主题
 * 2) 持久化：localStorage("novel-ai.theme.v1")
 * 3) 切换主题：把调色板写入 :root 上的 --theme-* 变量
 * 4) 自定义上传：FileReader → dataURL → 提取调色板 → 注入主题
 *
 * 设计要点：
 * - 6 张预设主题的内置调色板是"合理推测"（不依赖异步取色），保证首屏即有正确主题
 * - 用户上传时：先存 dataURL，立刻取色后用真实颜色覆盖预设；分析失败则回退到内建
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { extractPalette, type Palette } from "../lib/colorExtractor";

/* ----------------- 类型 ----------------- */

export type ThemeId =
  | "mowen-login"
  | "cyan-jade"
  | "shanshui"
  | "moonlit-bamboo"
  | "dreamy-ink"
  | "vermilion-maple"
  | string; // 用户自定义主题允许任意 id

export type ThemeMode = "preset" | "custom";

export type Theme = {
  id: ThemeId;
  name: string;
  /** 背景图 URL（预设：/themes/*.png；自定义：dataURL） */
  imageUrl: string;
  /** 主题类型 */
  mode: ThemeMode;
  /** 调色板（注入到 --theme-* CSS 变量） */
  palette: Palette;
  /** 用户上传时间戳（毫秒） */
  createdAt?: number;
};

type ThemeContextValue = {
  /** 当前主题 */
  theme: Theme;
  /** 所有可选主题（含预设 + 用户上传） */
  themes: Theme[];
  /** 切换主题 */
  setTheme: (id: ThemeId) => void;
  /** 上传自定义图片作为新主题 */
  uploadTheme: (file: File, name?: string) => Promise<Theme>;
  /** 删除自定义主题 */
  removeTheme: (id: ThemeId) => void;
  /** 重置为预设 */
  resetThemes: () => void;
  /** 正在分析图片 */
  analyzing: boolean;
};

/* ----------------- 预设主题（6 张） ----------------- */

/**
 * 6 张图经图片分析后的人工推荐调色板（按"水墨意境"对应色彩氛围推测）：
 * - 墨问登录页：紫墨
 * - 宁静远景：青碧玉
 * - 山水水墨画：墨白
 * - 月林空竹：墨白 + 冷月青
 * - 梦幻山水：紫蓝
 * - 秋枫霞谷：朱砂霞
 */
const PRESET_PALETTES: Record<string, Omit<Theme, "id" | "name" | "imageUrl" | "mode" | "createdAt">> = {
  "mowen-login": {
    palette: {
      colors: ["#7c3aed", "#a78bfa", "#ec4899", "#4c1d95", "#ede4ff", "#f5f0ff"],
      primary: "#7c3aed",
      secondary: "#a78bfa",
      background: "#f5f0ff",
      foreground: "#ffffff",
      primarySoft: "rgba(124, 58, 237, 0.12)",
      shadow: "rgba(58, 38, 107, 0.18)",
    },
  },
  "cyan-jade": {
    palette: {
      colors: ["#0d9488", "#5eead4", "#134e4a", "#2dd4bf", "#ecfeff", "#f0fdfa"],
      primary: "#0d9488",
      secondary: "#5eead4",
      background: "#f0fdfa",
      foreground: "#ffffff",
      primarySoft: "rgba(13, 148, 136, 0.12)",
      shadow: "rgba(19, 78, 74, 0.18)",
    },
  },
  "shanshui": {
    palette: {
      colors: ["#475569", "#94a3b8", "#cbd5e1", "#1e293b", "#f1f5f9", "#f8fafc"],
      primary: "#475569",
      secondary: "#64748b",
      background: "#f8fafc",
      foreground: "#ffffff",
      primarySoft: "rgba(71, 85, 105, 0.12)",
      shadow: "rgba(30, 41, 59, 0.18)",
    },
  },
  "moonlit-bamboo": {
    palette: {
      colors: ["#1e3a5f", "#60a5fa", "#0f172a", "#93c5fd", "#eff6ff", "#f8fafc"],
      primary: "#1e3a5f",
      secondary: "#60a5fa",
      background: "#f8fafc",
      foreground: "#ffffff",
      primarySoft: "rgba(30, 58, 95, 0.12)",
      shadow: "rgba(15, 23, 42, 0.18)",
    },
  },
  "dreamy-ink": {
    palette: {
      colors: ["#6366f1", "#a78bfa", "#312e81", "#818cf8", "#eef2ff", "#f5f3ff"],
      primary: "#6366f1",
      secondary: "#a78bfa",
      background: "#f5f3ff",
      foreground: "#ffffff",
      primarySoft: "rgba(99, 102, 241, 0.12)",
      shadow: "rgba(49, 46, 129, 0.18)",
    },
  },
  "vermilion-maple": {
    palette: {
      colors: ["#dc2626", "#f97316", "#7c2d12", "#fb923c", "#fff7ed", "#fffbeb"],
      primary: "#dc2626",
      secondary: "#f97316",
      background: "#fffbeb",
      foreground: "#ffffff",
      primarySoft: "rgba(220, 38, 38, 0.12)",
      shadow: "rgba(124, 45, 18, 0.18)",
    },
  },
};

const PRESET_THEMES: Theme[] = [
  {
    id: "mowen-login",
    name: "墨问 · 紫韵",
    imageUrl: "/themes/theme-mowen-login.png",
    mode: "preset",
    ...PRESET_PALETTES["mowen-login"],
  },
  {
    id: "cyan-jade",
    name: "宁静 · 远景",
    imageUrl: "/themes/theme-cyan-jade.png",
    mode: "preset",
    ...PRESET_PALETTES["cyan-jade"],
  },
  {
    id: "shanshui",
    name: "山水 · 水墨",
    imageUrl: "/themes/theme-shanshui.png",
    mode: "preset",
    ...PRESET_PALETTES["shanshui"],
  },
  {
    id: "moonlit-bamboo",
    name: "月林 · 空竹",
    imageUrl: "/themes/theme-moonlit-bamboo.png",
    mode: "preset",
    ...PRESET_PALETTES["moonlit-bamboo"],
  },
  {
    id: "dreamy-ink",
    name: "梦幻 · 山水",
    imageUrl: "/themes/theme-dreamy-ink.png",
    mode: "preset",
    ...PRESET_PALETTES["dreamy-ink"],
  },
  {
    id: "vermilion-maple",
    name: "秋枫 · 霞谷",
    imageUrl: "/themes/theme-vermilion-maple.png",
    mode: "preset",
    ...PRESET_PALETTES["vermilion-maple"],
  },
];

const DEFAULT_THEME_ID = "mowen-login";
const STORAGE_KEY = "novel-ai.theme.v1";
const CUSTOM_STORAGE_KEY = "novel-ai.theme.custom.v1";

type Persisted = {
  currentId: ThemeId;
  custom: Theme[];
};

/* ----------------- 工具：File → dataURL ----------------- */

function readFileAsDataURL(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(new Error("读取文件失败"));
    reader.readAsDataURL(file);
  });
}

/* ----------------- 把调色板写入 :root ----------------- */

function applyPaletteToRoot(palette: Palette) {
  const root = document.documentElement;
  root.style.setProperty("--theme-primary", palette.primary);
  root.style.setProperty("--theme-secondary", palette.secondary);
  root.style.setProperty("--theme-bg", palette.background);
  root.style.setProperty("--theme-fg", palette.foreground);
  root.style.setProperty("--theme-primary-soft", palette.primarySoft);
  root.style.setProperty("--theme-shadow", palette.shadow);
  // 衍生：更深的色（按钮按下）+ 更浅的色（hover）
  // 这里用 rgba 简化（直接复用主色 12% / 24% 透明）
  root.style.setProperty("--theme-primary-12", hexToRgba(palette.primary, 0.12));
  root.style.setProperty("--theme-primary-24", hexToRgba(palette.primary, 0.24));
  root.style.setProperty("--theme-primary-08", hexToRgba(palette.primary, 0.08));
  // 5 个色板（用于图表 / ECharts）
  palette.colors.forEach((c, i) => {
    root.style.setProperty(`--theme-color-${i}`, c);
  });
}

function clearPaletteOnRoot() {
  const root = document.documentElement;
  const keys = [
    "--theme-primary",
    "--theme-secondary",
    "--theme-bg",
    "--theme-fg",
    "--theme-primary-soft",
    "--theme-shadow",
    "--theme-primary-12",
    "--theme-primary-24",
    "--theme-primary-08",
  ];
  for (let i = 0; i < 8; i++) keys.push(`--theme-color-${i}`);
  keys.forEach((k) => root.style.removeProperty(k));
}

function hexToRgba(hex: string, alpha: number): string {
  const m = hex.replace("#", "").match(/^([0-9a-f]{6})$/i);
  if (!m) return `rgba(0,0,0,${alpha})`;
  const r = parseInt(m[1].slice(0, 2), 16);
  const g = parseInt(m[1].slice(2, 4), 16);
  const b = parseInt(m[1].slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/* ----------------- Context ----------------- */

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [currentId, setCurrentId] = useState<ThemeId>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as Persisted;
        return parsed.currentId ?? DEFAULT_THEME_ID;
      }
    } catch {
      /* ignore */
    }
    return DEFAULT_THEME_ID;
  });
  const [customThemes, setCustomThemes] = useState<Theme[]>(() => {
    try {
      const raw = localStorage.getItem(CUSTOM_STORAGE_KEY);
      if (raw) return JSON.parse(raw) as Theme[];
    } catch {
      /* ignore */
    }
    return [];
  });
  const [analyzing, setAnalyzing] = useState(false);
  const applyingRef = useRef(false);

  const themes = useMemo<Theme[]>(
    () => [...PRESET_THEMES, ...customThemes],
    [customThemes],
  );

  const theme = useMemo<Theme>(
    () => themes.find((t) => t.id === currentId) ?? themes[0] ?? PRESET_THEMES[0],
    [themes, currentId],
  );

  // 切换主题时立即把调色板写入 :root
  useEffect(() => {
    if (applyingRef.current) return;
    applyPaletteToRoot(theme.palette);
  }, [theme]);

  // 持久化
  useEffect(() => {
    const payload: Persisted = { currentId, custom: customThemes };
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
      localStorage.setItem(CUSTOM_STORAGE_KEY, JSON.stringify(customThemes));
    } catch {
      /* localStorage 可能满 / 隐私模式 */
    }
  }, [currentId, customThemes]);

  const setTheme = useCallback((id: ThemeId) => {
    setCurrentId(id);
  }, []);

  const uploadTheme = useCallback(async (file: File, name?: string): Promise<Theme> => {
    if (!file.type.startsWith("image/")) {
      throw new Error("只支持图片文件（jpg / png / webp）");
    }
    setAnalyzing(true);
    try {
      const dataUrl = await readFileAsDataURL(file);
      // 1) 立刻用"占位调色板"插一条（保证 UI 立即响应）
      const id = `custom-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      const fallbackPalette: Palette = {
        colors: ["#7c3aed", "#a78bfa", "#ec4899", "#4c1d95", "#ede4ff", "#f5f0ff"],
        primary: "#7c3aed",
        secondary: "#a78bfa",
        background: "#f5f0ff",
        foreground: "#ffffff",
        primarySoft: "rgba(124, 58, 237, 0.12)",
        shadow: "rgba(58, 38, 107, 0.18)",
      };
      const tempTheme: Theme = {
        id,
        name: name?.trim() || file.name.replace(/\.[^.]+$/, "") || "我的主题",
        imageUrl: dataUrl,
        mode: "custom",
        palette: fallbackPalette,
        createdAt: Date.now(),
      };
      setCustomThemes((prev) => [tempTheme, ...prev]);
      setCurrentId(id);
      // 2) 异步提取真实调色板，提取完成后覆盖
      try {
        applyingRef.current = true; // 暂停 useEffect 自动写
        const real = await extractPalette(dataUrl);
        setCustomThemes((prev) =>
          prev.map((t) => (t.id === id ? { ...t, palette: real } : t)),
        );
        setCurrentId(id); // 重新触发写入真实调色板
        // 微任务后让出
        await Promise.resolve();
        applyingRef.current = false;
        applyPaletteToRoot(real);
        return { ...tempTheme, palette: real };
      } catch (err) {
        applyingRef.current = false;
        console.warn("[theme] 颜色提取失败，使用默认调色板:", err);
        return tempTheme;
      }
    } finally {
      setAnalyzing(false);
    }
  }, []);

  const removeTheme = useCallback((id: ThemeId) => {
    setCustomThemes((prev) => prev.filter((t) => t.id !== id));
    setCurrentId((prev) => (prev === id ? DEFAULT_THEME_ID : prev));
  }, []);

  const resetThemes = useCallback(() => {
    setCustomThemes([]);
    setCurrentId(DEFAULT_THEME_ID);
    try {
      localStorage.removeItem(CUSTOM_STORAGE_KEY);
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo<ThemeContextValue>(
    () => ({ theme, themes, setTheme, uploadTheme, removeTheme, resetThemes, analyzing }),
    [theme, themes, setTheme, uploadTheme, removeTheme, resetThemes, analyzing],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}

/** 暴露给非 React 环境（如 console 调试） */
export const __THEME_DEBUG__ = { applyPaletteToRoot, clearPaletteOnRoot, PRESET_THEMES };
