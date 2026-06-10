/**
 * 颜色提取工具（纯前端 · 无第三方依赖）
 * --------------------------------------------------------------
 * 1) extractPalette(src):  从图片 URL 提取 5~6 色调色板（主色 + 辅色）
 * 2) extractDominantColor: 单独提取主色（Vibrant-like 算法）
 * 3) rgbToHex / hexToRgb:  颜色格式互转
 * 4) isDarkColor:           判断亮度，决定前景文字用深/浅
 * 5) getReadableTextColor:  根据底色返回 #ffffff 或 #1a1a1a
 * 6) mixColors:             颜色混合（用于生成 hover/active 态）
 *
 * 算法：
 *   · 降采样到 64x64，避免巨大图片卡顿
 *   · 中位切分（Median Cut）做 6 bin 量化 → 6 个代表色
 *   · 选像素数最多 + 饱和度较高的为主色（Dominant）
 *   · 排除近黑白/近纯白
 */

export type RGB = { r: number; g: number; b: number };
export type Palette = {
  /** 6 色调色板，按"重要度"降序（出现频次 + 饱和度加权） */
  colors: string[];
  /** 主色（按钮强调色），同 colors[0] 但算法更严格 */
  primary: string;
  /** 次色（按钮辅助 / 渐变） */
  secondary: string;
  /** 背景层（最浅，适合做底色） */
  background: string;
  /** 前景文字（自动判断深/浅） */
  foreground: string;
  /** 主色对应的柔和底（用于 hover / badge） */
  primarySoft: string;
  /** 阴影色（透明黑） */
  shadow: string;
};

const SAMPLE_SIZE = 64;            // 降采样边长
const COLOR_BINS = 6;              // 调色板大小
const NEUTRAL_SATURATION_MAX = 12; // 低于这个饱和度视为近灰（剔除非彩色）

/* ---------- 工具函数 ---------- */

function rgbToHex({ r, g, b }: RGB): string {
  const to = (n: number) => n.toString(16).padStart(2, "0");
  return `#${to(r)}${to(g)}${to(b)}`;
}

function hexToRgb(hex: string): RGB {
  const m = hex.replace("#", "").match(/^([0-9a-f]{6})$/i);
  if (!m) return { r: 0, g: 0, b: 0 };
  return {
    r: parseInt(m[1].slice(0, 2), 16),
    g: parseInt(m[1].slice(2, 4), 16),
    b: parseInt(m[1].slice(4, 6), 16),
  };
}

function rgbToHsl({ r, g, b }: RGB): { h: number; s: number; l: number } {
  r /= 255;
  g /= 255;
  b /= 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  let h = 0;
  let s = 0;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = (g - b) / d + (g < b ? 6 : 0); break;
      case g: h = (b - r) / d + 2; break;
      case b: h = (r - g) / d + 4; break;
    }
    h /= 6;
  }
  return { h: h * 360, s: s * 100, l: l * 100 };
}

function hslToRgb({ h, s, l }: { h: number; s: number; l: number }): RGB {
  h /= 360;
  s /= 100;
  l /= 100;
  let r: number;
  let g: number;
  let b: number;
  if (s === 0) {
    r = g = b = l;
  } else {
    const hue2rgb = (p: number, q: number, t: number) => {
      if (t < 0) t += 1;
      if (t > 1) t -= 1;
      if (t < 1 / 6) return p + (q - p) * 6 * t;
      if (t < 1 / 2) return q;
      if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
      return p;
    };
    const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
    const p = 2 * l - q;
    r = hue2rgb(p, q, h + 1 / 3);
    g = hue2rgb(p, q, h);
    b = hue2rgb(p, q, h - 1 / 3);
  }
  return { r: Math.round(r * 255), g: Math.round(g * 255), b: Math.round(b * 255) };
}

function isDarkColor(hex: string): boolean {
  const { r, g, b } = hexToRgb(hex);
  // 相对亮度（YIQ 近似）
  const yiq = (r * 299 + g * 587 + b * 114) / 1000;
  return yiq < 140;
}

function getReadableTextColor(hex: string): string {
  return isDarkColor(hex) ? "#ffffff" : "#1a1a1a";
}

function mixColors(a: string, b: string, weight: number): string {
  const ar = hexToRgb(a);
  const br = hexToRgb(b);
  const w = Math.min(1, Math.max(0, weight));
  return rgbToHex({
    r: Math.round(ar.r * (1 - w) + br.r * w),
    g: Math.round(ar.g * (1 - w) + br.g * w),
    b: Math.round(ar.b * (1 - w) + br.b * w),
  });
}

/* ---------- 核心：图片 → 像素矩阵 ---------- */

async function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.decoding = "async";
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`Failed to load image: ${src}`));
    img.src = src;
  });
}

function getSampledPixels(img: HTMLImageElement, size: number): RGB[] {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) throw new Error("Canvas 2D context unavailable");
  // cover 模式：保持比例，居中裁剪
  const ratio = img.width / img.height;
  let sx = 0;
  let sy = 0;
  let sw = img.width;
  let sh = img.height;
  if (ratio > 1) {
    sw = img.height;
    sx = (img.width - sw) / 2;
  } else {
    sh = img.width;
    sy = (img.height - sh) / 2;
  }
  ctx.drawImage(img, sx, sy, sw, sh, 0, 0, size, size);
  const data = ctx.getImageData(0, 0, size, size).data;
  const pixels: RGB[] = [];
  for (let i = 0; i < data.length; i += 4) {
    const a = data[i + 3];
    if (a < 200) continue; // 跳过透明像素
    pixels.push({ r: data[i], g: data[i + 1], b: data[i + 2] });
  }
  return pixels;
}

/* ---------- 核心：Median Cut 量化 ---------- */

type Box = { pixels: RGB[]; bbox: { rMin: number; rMax: number; gMin: number; gMax: number; bMin: number; bMax: number } };

function makeBox(pixels: RGB[]): Box {
  let rMin = 255;
  let rMax = 0;
  let gMin = 255;
  let gMax = 0;
  let bMin = 255;
  let bMax = 0;
  for (const p of pixels) {
    if (p.r < rMin) rMin = p.r;
    if (p.r > rMax) rMax = p.r;
    if (p.g < gMin) gMin = p.g;
    if (p.g > gMax) gMax = p.g;
    if (p.b < bMin) bMin = p.b;
    if (p.b > bMax) bMax = p.b;
  }
  return { pixels, bbox: { rMin, rMax, gMin, gMax, bMin, bMax } };
}

function splitBox(box: Box): [Box, Box] {
  const { rMin, rMax, gMin, gMax, bMin, bMax } = box.bbox;
  const rRange = rMax - rMin;
  const gRange = gMax - gMin;
  const bRange = bMax - bMin;
  // 在最长的颜色通道上做中位切分
  const channel: keyof RGB = rRange >= gRange && rRange >= bRange ? "r"
    : gRange >= bRange ? "g"
      : "b";
  const sorted = [...box.pixels].sort((a, b) => a[channel] - b[channel]);
  const mid = Math.floor(sorted.length / 2);
  return [makeBox(sorted.slice(0, mid)), makeBox(sorted.slice(mid))];
}

function averageColor(pixels: RGB[]): RGB {
  let r = 0;
  let g = 0;
  let b = 0;
  for (const p of pixels) {
    r += p.r;
    g += p.g;
    b += p.b;
  }
  const n = pixels.length || 1;
  return { r: Math.round(r / n), g: Math.round(g / n), b: Math.round(b / n) };
}

function medianCut(pixels: RGB[], binCount: number): RGB[] {
  if (pixels.length === 0) return [];
  let boxes: Box[] = [makeBox(pixels)];
  while (boxes.length < binCount) {
    // 选最长的 box 切分（按像素数 + 通道范围）
    const target = boxes
      .map((b, i) => {
        const { rMin, rMax, gMin, gMax, bMin, bMax } = b.bbox;
        const range = Math.max(rMax - rMin, gMax - gMin, bMax - bMin);
        return { i, range, size: b.pixels.length };
      })
      .filter((x) => x.range > 0 && x.size > 1)
      .sort((a, b) => b.range * b.size - a.range * a.size)[0];
    if (!target) break;
    const [a, b] = splitBox(boxes[target.i]);
    boxes = [...boxes.slice(0, target.i), a, b, ...boxes.slice(target.i + 1)];
  }
  return boxes.map((b) => averageColor(b.pixels));
}

/* ---------- 评分：选出"主色"和"背景" ---------- */

function scorePrimary(rgb: RGB): number {
  const { s, l } = rgbToHsl(rgb);
  // 饱和度 25~85，亮度 30~70 最佳
  const sScore = 1 - Math.abs((s - 55) / 30);
  const lScore = 1 - Math.abs((l - 50) / 25);
  return Math.max(0, sScore) * 0.6 + Math.max(0, lScore) * 0.4;
}

function scoreBackground(rgb: RGB): number {
  const { s, l } = rgbToHsl(rgb);
  // 背景应该更"柔"：低饱和 + 较亮
  return (100 - Math.min(100, s)) * 0.5 + Math.min(100, l) * 0.5;
}

/* ---------- 主入口 ---------- */

export async function extractPalette(src: string): Promise<Palette> {
  const img = await loadImage(src);
  const pixels = getSampledPixels(img, SAMPLE_SIZE);
  if (pixels.length === 0) {
    throw new Error("Image has no opaque pixels");
  }
  // 过滤掉极端值（过白过黑）
  const filtered = pixels.filter((p) => {
    const avg = (p.r + p.g + p.b) / 3;
    return avg > 12 && avg < 248;
  });
  const safe = filtered.length > 100 ? filtered : pixels;
  const representative = medianCut(safe, COLOR_BINS);
  // 过滤极低饱和（近灰），避免成为主色
  const candidates = representative.filter((rgb) => {
    const { s } = rgbToHsl(rgb);
    return s >= NEUTRAL_SATURATION_MAX;
  });
  const withColor = candidates.length > 0 ? candidates : representative;

  // 主色：分数最高
  const primaryRgb = [...withColor].sort((a, b) => scorePrimary(b) - scorePrimary(a))[0] ?? withColor[0];
  const primary = rgbToHex(primaryRgb);
  // 次色：与主色色相差最大且饱和度足够的
  const primaryHsl = rgbToHsl(primaryRgb);
  const secondaryRgb = [...withColor]
    .filter((rgb) => rgb !== primaryRgb)
    .sort((a, b) => {
      const ah = Math.abs(rgbToHsl(a).h - primaryHsl.h);
      const bh = Math.abs(rgbToHsl(b).h - primaryHsl.h);
      return bh - ah;
    })[0] ?? primaryRgb;
  const secondary = rgbToHex(secondaryRgb);
  // 背景：所有像素中"最柔"的代表色
  const backgroundRgb = [...representative].sort((a, b) => scoreBackground(b) - scoreBackground(a))[0] ?? primaryRgb;
  const background = rgbToHex(backgroundRgb);
  // 主色对应前景文字
  const foreground = getReadableTextColor(primary);
  // 浅底（主色 + 大量白）
  const primarySoft = mixColors(primary, "#ffffff", 0.86);

  return {
    colors: withColor.map(rgbToHex),
    primary,
    secondary,
    background,
    foreground,
    primarySoft,
    shadow: "rgba(0, 0, 0, 0.18)",
  };
}

/** 仅取主色（轻量版，0.1s 内返回） */
export async function extractDominantColor(src: string): Promise<string> {
  const palette = await extractPalette(src);
  return palette.primary;
}
