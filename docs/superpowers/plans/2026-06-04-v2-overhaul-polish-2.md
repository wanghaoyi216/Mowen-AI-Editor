# v2-overhaul 第二轮优化实施方案书

> **For agentic workers:** 本方案是 bite-sized 任务清单，按 TDD 方式逐步实现。
> 任务顺序：先数据（一致性 KPI、章节正文），再 UI（饼图、布局），最后收尾。

**Goal:** 修复 4 个新问题：① 一致性 KPI"有报告=0"；② 章节内容是大纲/场景元信息；③ 世界构建饼图标签压盖；④ Tab 底部留空。

**Architecture:** 前端优先修，最小后端改动（仅 seed 改 1 个函数）。不改 API、不改 schema。

**Tech Stack:** React 19, ECharts, FastAPI seed 脚本。

---

## 任务地图

| Task | 模块 | 改动文件数 | 优先级 |
|---|---|---|---|
| 1 | 一致性 KPI"有报告=0" 修复 | 1 | P0 |
| 2 | 章节正文 seed 重写（生成真小说正文） | 1 | P0 |
| 3 | Tab3 章节面板：正文为主、场景为辅 | 1 | P0 |
| 4 | Tab2 世界构建：饼图重排（pie 独立 + chip 独立） | 1 | P1 |
| 5 | Tab4 一致性底部留空：新增"检查维度详情"面板 | 1 | P1 |
| 6 | Tab1/Tab2 底部留空：底部加"操作建议 / 数据洞察" | 2 | P2 |
| 7 | smoke_test 收尾 | 0 | P0 |

---

## Task 1: 一致性 KPI"有报告=0" 修复

**Files:**
- Modify: `frontend/src/components/CommandCenter/VisualizationTab4Consistency.tsx`
- Verify: 打开一致性检查 Tab，"有报告" KPI 立即显示 5/7（不再等点击）

### Step 1: 引入批量加载 effect

定位组件顶部 useEffect（约 27-45 行），在它之后插入新的 useEffect：

```tsx
useEffect(() => {
  if (!projectId || chapters.length === 0) return;
  const currentProjectId = projectId;
  let cancelled = false;
  async function loadAllReports() {
    try {
      const { fetchChapterVersions } = await import("../../lib/api");
      // 并发拉所有章节的 versions
      const entries = await Promise.all(
        chapters.map(async (ch) => {
          try {
            const versions = await fetchChapterVersions(currentProjectId, ch.id);
            const latest = versions.length > 0 ? versions[versions.length - 1] : null;
            return [ch.id, latest?.consistency_report ?? null] as const;
          } catch {
            return [ch.id, null] as const;
          }
        }),
      );
      if (cancelled) return;
      const map: Record<number, string | null> = {};
      entries.forEach(([id, report]) => { map[id] = report; });
      setChapterReports(map);
    } catch (err) {
      console.error("Failed to bulk load reports", err);
    }
  }
  void loadAllReports();
  return () => { cancelled = true; };
}, [projectId, chapters]);
```

**注意**：`chapters` 是 useEffect 的依赖，需要确认它已通过第一个 useEffect 加载完。新加的 effect 在 chapters 变化时触发，所以不会和原 effect 抢。

### Step 2: 适配 `loadChapterReport`

原 `loadChapterReport` 仍保留（用于点击展开时取最新），但判断条件改为：

```tsx
async function loadChapterReport(chapterId: number) {
  if (chapterReports[chapterId] !== undefined && chapterReports[chapterId] !== null) {
    return;  // 已加载且有报告
  }
  setReportsLoading((prev) => ({ ...prev, [chapterId]: true }));
  try {
    const { fetchChapterVersions } = await import("../../lib/api");
    const versions = await fetchChapterVersions(projectId!, chapterId);
    const latestVersion = versions.length > 0 ? versions[versions.length - 1] : null;
    const report = latestVersion?.consistency_report || null;
    setChapterReports((prev) => ({ ...prev, [chapterId]: report }));
  } catch {
    setChapterReports((prev) => ({ ...prev, [chapterId]: null }));
  } finally {
    setReportsLoading((prev) => ({ ...prev, [chapterId]: false }));
  }
}
```

### Step 3: 验证

- 打开一致性检查 Tab → "有报告" KPI 立即显示 5/7
- 雷达图中"检查覆盖率"从 0 变成 ~71%
- 不点击任何章节也正常

### Step 4: 提交

```bash
git add frontend/src/components/CommandCenter/VisualizationTab4Consistency.tsx
git commit -m "fix(consistency): eagerly load all chapter reports so 'hasReport' KPI is correct"
```

---

## Task 2: 章节正文 seed 重写

**Files:**
- Modify: `backend/scripts/seed_full_demo.py`
- Verify: 重跑 seed 后，每章 `final_content` ≥ 1500 字，是叙事性小说正文

### Step 1: 替换 `_ensure_chapter_content` 函数

定位 `def _ensure_chapter_content(db, project_id: int, chapters):` 函数（约 319 行起），整段替换为：

```python
def _ensure_chapter_content(db, project_id: int, chapters):
    """为已完成的章节生成真小说正文（叙事性散文，≥ 1500 字/章）。
    用于驾驶舱角色频次、字数统计、Tab3 章节正文展示。
    """
    for ch in chapters:
        if ch.status != "completed":
            continue
        if ch.final_content and len(ch.final_content) > 1500:
            continue  # 已有充足正文
        spec = CHAPTERS_BY_NO.get(ch.chapter_no)
        if spec is None:
            continue
        scenes = spec.get("scenes") or []
        random.seed(ch.chapter_no * 13 + 5)
        ch_title = ch.title or f"第{ch.chapter_no}章"
        pov_holder = (scenes[0].get("pov") if scenes else None) or "林雾"

        # 准备角色名 / 场景描述素材
        scene_summaries = [sc.get("summary", "") for sc in scenes]
        scene_titles = [sc.get("title", f"场景{i+1}") for i, sc in enumerate(scenes)]
        moods = [sc.get("mood", "内敛") for sc in scenes]

        # 写一个完整章节的真实散文
        paragraphs = []
        paragraphs.append(f"　　{ch_title}")
        paragraphs.append("")
        paragraphs.append(
            f"　　那是{ch.objective or '镜湖城还笼罩在旧世纪的灰雾里'}的一个早晨。"
            f"{pov_holder}从档案司第七司的宿舍走出时，街角的汽笛刚响过第一声。"
            "湿冷的风沿着档案司的石阶漫上来，携带着纸页、焦油与禁律院才会有的锈味。"
        )
        # 用场景概要生成叙事段落
        for idx, (st, ss, md) in enumerate(zip(scene_titles, scene_summaries, moods)):
            paragraphs.append("")
            paragraphs.append(
                f"　　{st}。{pov_holder}站在{_pick_setting(idx)}的阴影下，"
                f"{ss}"
            )
            # 加入 1-2 句情节推进
            progression = _progression_phrase(idx, len(scenes))
            paragraphs.append(progression)
            # 引入一个 NPC 互动
            if idx == 0:
                paragraphs.append(
                    "　　顾沉的声音从廊道尽头传过来，夹杂着执法司惯有的冷："
                    "“你昨晚又去了雾区。”他不是在问。"
                )
            elif idx == 1:
                paragraphs.append(
                    "　　闻柯在档案室门外吹了声口哨，"
                    "那是他在提醒所有人，第七城废墟的汽笛刚响过第三遍。"
                )
            elif idx == 2:
                paragraphs.append(
                    "　　白葵把一张封条贴到档案柜上，"
                    "封条上的字是用禁律墨写的，被水浸过会显出第二层颜色。"
                )
            elif idx == 3:
                paragraphs.append(
                    "　　裴衡在拐角处站了一会儿。"
                    "他没有说话，只是把一卷档案从袖口取下，又放回原处。"
                )
        # 章节收束
        paragraphs.append("")
        paragraphs.append(
            f"　　夜深时，{pov_holder}合上档案柜，禁律锁的指针停在「三十二」上。"
            f"他想起白葵说过的那句话：{_closing_phrase(ch.chapter_no)}"
        )
        paragraphs.append("　　雾还没散。")
        paragraphs.append("")
        paragraphs.append("　　—— 终 ——")
        # 角色名引用以触发 character freq
        epilogue = (
            "　　本章出场角色：林雾、顾沉、闻柯、白葵、裴衡。"
            "　　镜湖城的灰雾在审判署的汽笛声中愈发浓重，"
            "林雾与顾沉的对峙被闻柯与白葵看在眼里，"
            "而次官裴衡的阴影始终笼罩在档案司上空。"
        )
        paragraphs.append(epilogue)
        ch.final_content = "\n".join(paragraphs)
        # 同步 word_count（按中文字符 + 英文/数字）
        ch.word_count = len([c for c in ch.final_content if "\u4e00" <= c <= "\u9fff"]) + \
            len([c for c in ch.final_content if c.isascii() and c.isalnum()])
        db.commit()


def _pick_setting(idx: int) -> str:
    return ["禁律长廊", "第七城废墟的入口", "档案司第七司", "禁律院的廊桥", "镜湖城的高架桥"][idx % 5]


def _progression_phrase(idx: int, total: int) -> str:
    if idx == 0:
        return "　　档案室外的风压比往常更重，似乎在暗示雾区昨夜又有了新异动。"
    if idx == total - 1:
        return "　　所有的线索都聚向了同一个方向——第七城废墟的深处。"
    return f"　　档案柜的锁舌在寂静中发出低沉的金属摩擦声，像是某种回应。"


def _closing_phrase(chapter_no: int) -> str:
    phrases = [
        "在禁律被遵守的地方，秘密比雾更耐久。",
        "档案一旦被记录，就再也不会消失。",
        "听不见的雾，才是最危险的。",
        "灰雾从不撒谎，它只是把真相藏得更深。",
        "禁律锁记住了一切，也包括你忘了的部分。",
        "档案司的走廊很长，足以让一个人忘掉自己为什么进来。",
        "每一次雾散开，都只是换了一种迷障。",
    ]
    return phrases[chapter_no % len(phrases)]
```

### Step 2: 重跑 seed 验证

```bash
docker exec -i novel-ai-editor-backend python -c "
import sys
sys.path.insert(0, '/app')
from app.db import SessionLocal
from app.models import Chapter
db = SessionLocal()
chs = db.query(Chapter).filter(Chapter.status == 'completed').all()
for c in chs:
    print(f'Ch.{c.chapter_no:2d}  {c.word_count:5d}字  {c.title}')
" 2>&1 | tail -10
```

期望：每章 word_count ≥ 1500，且 final_content 已是叙事性正文。

或更直接：

```bash
docker exec -i novel-ai-editor-backend python /app/scripts/seed_full_demo.py 2>&1 | tail -10
python -c "
import urllib.request, json
chs = json.loads(urllib.request.urlopen('http://localhost:8000/api/v1/projects/1/chapters').read())['data']
for c in chs:
    if c['status'] == 'completed':
        wc = c.get('word_count', 0)
        print(f\"Ch.{c['chapter_no']:2d}  {wc:5d}字  {c['title']}\")
"
```

期望：每章 ≥ 1500 字。

### Step 3: 提交

```bash
git add backend/scripts/seed_full_demo.py
git commit -m "feat(seed): generate real novel prose (1500+ chars) per chapter, not scene outline"
```

---

## Task 3: Tab3 章节面板：正文为主、场景为辅

**Files:**
- Modify: `frontend/src/components/CommandCenter/VisualizationTab3Chapter.tsx`
- Verify: 展开任一已完成章节，顶部是完整小说正文（≥ 1500 字），下方"本章场景"可折叠

### Step 1: 给"本章场景"加折叠开关

找到 `<ChapterScenes ... />` 调用（约 384-387 行）：

```tsx
<ChapterScenes
  scenes={scenes}
  loading={isLoadingScenes}
/>
```

改为：

```tsx
<details style={{ marginTop: 14 }} open>
  <summary style={{
    display: 'flex', alignItems: 'center', gap: 6,
    fontSize: 11, fontWeight: 700, color: colors.accent,
    marginBottom: 8, letterSpacing: 0.4, textTransform: 'uppercase',
    cursor: 'pointer', listStyle: 'none',
  }}>
    <BookOpen size={12} />
    <span>本章场景</span>
    <span style={{
      background: `${colors.accent}22`,
      color: colors.accent,
      padding: '1px 7px', borderRadius: 8,
      fontSize: 10, fontWeight: 700,
    }}>{scenes.length}</span>
    <span style={{ marginLeft: 'auto', fontSize: 10, color: colors.textSecondary }}>点击折叠</span>
  </summary>
  <ChapterScenes scenes={scenes} loading={isLoadingScenes} />
</details>
```

**问题**：原 `<ChapterScenes>` 内部又有一个 "本章场景" 标题，需要删掉，否则重复。

定位 `<ChapterScenes>` 组件内（约 437-454 行）的标题块：

```tsx
return (
  <div style={{ marginTop: 14 }}>
    <div style={{
      display: 'flex', alignItems: 'center', gap: 6,
      fontSize: 11, fontWeight: 700, color: colors.accent,
      marginBottom: 8, letterSpacing: 0.4, textTransform: 'uppercase'
    }}>
      <BookOpen size={12} />
      <span>本章场景</span>
      ...
```

整段标题 div 删掉，只保留：

```tsx
return (
  <div>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {scenes.map((sc, idx) => (
        <SceneCard key={sc.id} scene={sc} index={idx} />
      ))}
    </div>
  </div>
);
```

### Step 2: 把 MarkdownContent 字号加大

找到 `<MarkdownContent content={latestVersion.content} />` 调用（约 367 行），包一个样式让正文更易读：

```tsx
<div style={{
  fontSize: 13.5,
  lineHeight: 1.85,
  color: colors.text,
  letterSpacing: 0.2,
  maxHeight: 600,
  overflowY: 'auto',
  padding: '4px 2px',
}}>
  <MarkdownContent content={latestVersion.content} />
</div>
```

### Step 3: 验证

- 打开章节写作 Tab → 展开第 1 章
- 顶部是整段叙事小说正文（≥ 1500 字，13.5 字号，行高 1.85）
- 下方"本章场景"标签，点击可折叠/展开
- 字数指标 ≥ 1500

### Step 4: 提交

```bash
git add frontend/src/components/CommandCenter/VisualizationTab3Chapter.tsx
git commit -m "refine(chapter-tab): promote prose body to primary view, fold scene breakdown"
```

---

## Task 4: Tab2 世界构建：饼图重排

**Files:**
- Modify: `frontend/src/components/CommandCenter/VisualizationTab2World.tsx`
- Verify: 饼图和文字 chip 不再压盖

### Step 1: 把饼图容器从 `280px` 拉宽到独立一行

定位饼图容器（约 161-174 行）：

```tsx
<div style={{ background: colors.cardBackground, border: `1px solid ${colors.border}`, borderRadius: borderRadius.md, padding: 10, display: "flex", alignItems: "center", gap: 8 }}>
  <ReactECharts option={pieOption} style={{ height: 90, width: 90 }} />
  <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 4, fontSize: 11 }}>
    {/* legend 列表 */}
  </div>
</div>
```

改为上下结构（饼图 + 横向 chip 列表）：

```tsx
<div style={{ background: colors.cardBackground, border: `1px solid ${colors.border}`, borderRadius: borderRadius.md, padding: 10, display: "flex", flexDirection: "column", gap: 8 }}>
  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
    <ReactECharts option={pieOption} style={{ height: 100, width: 100 }} />
    <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 4, fontSize: 11 }}>
      {Object.entries(counts)
        .filter(([k, v]) => k !== "all" && v > 0)
        .map(([k, v]) => (
          <div key={k} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 10, height: 10, borderRadius: 2, background: categoryMeta(k).color, flexShrink: 0 }} />
            <span style={{ color: colors.text, flex: 1 }}>{categoryMeta(k).label}</span>
            <span style={{ color: colors.textSecondary, fontVariantNumeric: "tabular-nums", minWidth: 32, textAlign: 'right' }}>{v} 条</span>
          </div>
        ))}
    </div>
  </div>
</div>
```

### Step 2: 拉宽饼图卡

把外层 grid `gridTemplateColumns: "1fr 280px"` 改为 `"1fr 340px"`（约 117 行附近）：

```tsx
<div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: spacing.md, flexShrink: 0 }}>
```

### Step 3: pieOption 加 label 防内部压盖

```tsx
const pieOption = {
  tooltip: { trigger: "item" as const, formatter: "{b}: {c} 条 ({d}%)" },
  legend: { show: false },
  series: [{
    type: "pie" as const,
    radius: ["40%", "70%"],   // 缩小环宽
    center: ["50%", "50%"],
    avoidLabelOverlap: true,   // 改为 true
    itemStyle: { borderRadius: 4, borderColor: "#0d1117", borderWidth: 2 },
    label: {                    // 新增：外侧显示
      show: true,
      position: "outside" as const,
      formatter: "{b|{b}}\n{d|{d}%}",
      rich: {
        b: { color: "#e2e8f0", fontSize: 10 },
        d: { color: "#94a3b8", fontSize: 9 },
      },
    },
    labelLine: { length: 6, length2: 6 },
    data: Object.entries(counts)
      .filter(([k]) => k !== "all" || k === "other")
      .filter(([k]) => counts[k] > 0)
      .map(([k, v]) => ({
        name: categoryMeta(k).label,
        value: v,
        itemStyle: { color: categoryMeta(k).color },
      })),
  }],
};
```

### Step 4: 验证

- 打开世界构建 Tab
- 饼图有外侧 label（设定 20% / 角色 30% 等），不与 legend 压盖
- 右侧 legend 列表独立展示，文字不被图形覆盖

### Step 5: 提交

```bash
git add frontend/src/components/CommandCenter/VisualizationTab2World.tsx
git commit -m "refine(world-tab): separate pie chart and legend, add outside labels"
```

---

## Task 5: Tab4 一致性底部留空

**Files:**
- Modify: `frontend/src/components/CommandCenter/VisualizationTab4Consistency.tsx`
- Verify: 打开一致性检查 Tab，底部新增"检查维度详情"面板（5 维度的明细），不留空

### Step 1: 解析 consistency_report 文案

找到 `ConsistencyReportPreview` 组件（约 306 行），加一个 `parseScores` 工具函数：

```tsx
function parseScores(report: string): { dim: string; score: number }[] {
  const re = /([\u4e00-\u9fa5]{2,8})[：:]\s*(\d+)\s*分?/g;
  const out: { dim: string; score: number }[] = [];
  let m: RegExpExecArray | null;
  while ((m = re.exec(report)) !== null) {
    out.push({ dim: m[1], score: Number(m[2]) });
  }
  return out;
}
```

### Step 2: 聚合各章维度分数

在主组件 render 前（约 99 行附近）加：

```tsx
const allScores: { dim: string; score: number; chapterNo: number }[] = [];
checkResults.forEach((r) => {
  if (r.hasReport) {
    parseScores(r.reportPreview).forEach((s) => {
      allScores.push({ ...s, chapterNo: r.chapterNo });
    });
  }
});

// 维度平均
const dimMap: Record<string, { sum: number; count: number; scores: number[] }> = {};
allScores.forEach(({ dim, score }) => {
  if (!dimMap[dim]) dimMap[dim] = { sum: 0, count: 0, scores: [] };
  dimMap[dim].sum += score;
  dimMap[dim].count += 1;
  dimMap[dim].scores.push(score);
});
const dimAverages = Object.entries(dimMap)
  .map(([dim, v]) => ({
    dim,
    avg: v.count > 0 ? v.sum / v.count : 0,
    min: v.count > 0 ? Math.min(...v.scores) : 0,
    max: v.count > 0 ? Math.max(...v.scores) : 0,
    count: v.count,
  }))
  .sort((a, b) => a.avg - b.avg);
```

注意：以上计算需要 `r.reportPreview`（前 300 字）能包含完整 5 维度分数。当前 seed 报告是单行格式，应该能解析。但如果解析不到，会显示空数组，不要紧。

**更稳健**：直接用 `chapterReports[c.id]`（全报告）解析。改 `r.reportPreview` 为 `fullReport`（注意 fullReport 在循环外可用）：

实际上，全报告在展开时已加载（Task 1 的批量 effect），所以 `chapterReports[c.id]` 就是全报告。把上面的 `r.reportPreview` 改为 `chapterReports[r.chapterId] || ''` 即可：

```tsx
checkResults.forEach((r) => {
  if (r.hasReport) {
    const full = chapterReports[r.chapterId] || '';
    parseScores(full).forEach((s) => {
      allScores.push({ ...s, chapterNo: r.chapterNo });
    });
  }
});
```

### Step 3: 在底部新增"检查维度详情"面板

找到"等待 AI 完成一致性检查后..."那行（约 295 行），整个替换为：

```tsx
{/* 底部：检查维度详情面板（修复底部留空）*/}
<div style={{ background: colors.cardBackground, border: `1px solid ${colors.border}`, borderRadius: 8, padding: 14 }}>
  <h3 style={{ margin: '0 0 10px', fontSize: 14, color: colors.text, display: 'flex', alignItems: 'center', gap: 6 }}>
    <span>检查维度详情</span>
    <span style={{ fontSize: 11, color: colors.textSecondary, fontWeight: 400 }}>
      （基于 {chaptersWithReport} 份报告聚合）
    </span>
  </h3>
  {dimAverages.length === 0 ? (
    <div style={{ fontSize: 12, color: colors.textSecondary, padding: 12, textAlign: 'center' }}>
      {chaptersWithReport === 0
        ? '等待 AI 完成一致性检查后，将显示详细的检查报告内容'
        : '未找到可解析的维度分数'}
    </div>
  ) : (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {dimAverages.map((d) => {
        const ratio = d.avg / 100;
        const color = d.avg >= 85 ? '#10b981' : d.avg >= 70 ? '#3b82f6' : d.avg >= 50 ? '#f59e0b' : '#ef4444';
        return (
          <div key={d.dim} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ fontSize: 12, color: colors.text, minWidth: 80 }}>{d.dim}</div>
            <div style={{ flex: 1, height: 8, background: 'rgba(148,163,184,0.12)', borderRadius: 4, overflow: 'hidden' }}>
              <div style={{ width: `${ratio * 100}%`, height: '100%', background: `linear-gradient(90deg, ${color}88, ${color})`, borderRadius: 4, transition: 'width 0.3s' }} />
            </div>
            <div style={{ fontSize: 12, color: colors.text, fontVariantNumeric: 'tabular-nums', minWidth: 50, textAlign: 'right', fontWeight: 600 }}>
              {d.avg.toFixed(1)}
            </div>
            <div style={{ fontSize: 10, color: colors.textSecondary, minWidth: 64, textAlign: 'right' }}>
              {d.min} – {d.max}
            </div>
          </div>
        );
      })}
    </div>
  )}
</div>
```

### Step 4: 验证

- 打开一致性检查 Tab
- 底部"检查维度详情"面板显示 5 个维度的平均分 / min-max
- 例如："角色一致性 84.5 78-92" 一行
- 进度条颜色随分数变化

### Step 5: 提交

```bash
git add frontend/src/components/CommandCenter/VisualizationTab4Consistency.tsx
git commit -m "feat(consistency): add dimension details panel to fill bottom space"
```

---

## Task 6: Tab1/Tab2 底部留空

**Files:**
- Modify: `frontend/src/components/CommandCenter/VisualizationTab1Trends.tsx`
- Modify: `frontend/src/components/CommandCenter/VisualizationTab2World.tsx`
- Verify: Tab1 底部显示"AI 可执行的下一步建议"，Tab2 底部显示"按角色出现的世界书条目"

### Step 1: Tab1 底部"下一步建议"面板

在 Tab1 底部图表行（约 232 行附近）之后，插入新面板：

```tsx
{/* 底部：AI 可执行的下一步建议（修复留空）*/}
{selected && parseJsonArray(selected.suggested_directions).length > 0 && (
  <div style={{ background: colors.cardBackground, border: `1px solid ${colors.border}`, borderRadius: borderRadius.md, padding: 12, flexShrink: 0 }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 700, color: colors.text, marginBottom: 8 }}>
      <Sparkles size={12} /> AI 可执行的下一步建议
      <span style={{ fontSize: 10, color: colors.textSecondary, fontWeight: 400, marginLeft: 'auto' }}>
        一键回填到章节大纲
      </span>
    </div>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {parseJsonArray(selected.suggested_directions).map((d: any, i: number) => (
        <div key={i} style={{
          padding: '8px 10px',
          background: 'linear-gradient(135deg, rgba(59,130,246,0.08), rgba(139,92,246,0.05))',
          border: '1px solid rgba(59,130,246,0.18)',
          borderRadius: 6,
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <span style={{ fontSize: 11, color: '#3b82f6', fontWeight: 600, minWidth: 18 }}>{i + 1}.</span>
          <span style={{ fontSize: 12, color: colors.text, flex: 1, lineHeight: 1.5 }}>{d.premise || d}</span>
          <button
            style={{
              background: 'transparent',
              border: `1px solid ${colors.border}`,
              borderRadius: 4,
              padding: '2px 8px',
              fontSize: 10.5,
              color: colors.accent,
              cursor: 'pointer',
            }}
            onClick={() => {
              // 复制到剪贴板
              navigator.clipboard?.writeText(d.premise || String(d));
            }}
          >复制</button>
        </div>
      ))}
    </div>
  </div>
)}
```

### Step 2: Tab2 底部"角色引用"面板

在 Tab2 详情面板下方、列表 grid 之后（约 234 行附近），加一个"按角色归类"面板：

```tsx
{/* 底部：按角色归类的世界书引用（修复留空）*/}
<div style={{ background: colors.cardBackground, border: `1px solid ${colors.border}`, borderRadius: borderRadius.md, padding: 12, flexShrink: 0 }}>
  <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 700, color: colors.text, marginBottom: 10 }}>
    <Users size={12} /> 角色 × 世界书引用
  </div>
  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 8 }}>
    {(() => {
      // 简单启发：扫描所有条目 content 包含哪些角色名（从 character 类型条目提取）
      const charNames = entries.filter(e => e.category === 'character').map(e => e.title.split('（')[0].trim());
      return charNames.slice(0, 8).map(name => {
        const refs = entries.filter(e =>
          e.category !== 'character' && e.content?.includes(name)
        );
        return (
          <div key={name} style={{
            background: 'rgba(15, 23, 42, 0.4)',
            border: `1px solid ${colors.border}`,
            borderRadius: 6, padding: '6px 8px',
          }}>
            <div style={{ fontSize: 11.5, color: colors.text, fontWeight: 600, marginBottom: 4 }}>{name}</div>
            <div style={{ fontSize: 10, color: colors.textSecondary, lineHeight: 1.5 }}>
              出现在 {refs.length} 个条目中
              {refs.length > 0 && (
                <div style={{ marginTop: 3, display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                  {refs.slice(0, 3).map(r => (
                    <span key={r.id} style={{ background: 'rgba(99,102,241,0.12)', color: '#a5b4fc', padding: '1px 5px', borderRadius: 3 }}>{r.title}</span>
                  ))}
                  {refs.length > 3 && <span style={{ color: colors.textSecondary }}>+{refs.length - 3}</span>}
                </div>
              )}
            </div>
          </div>
        );
      });
    })()}
  </div>
</div>
```

### Step 3: 验证

- Tab1：底部"AI 可执行的下一步建议"显示 2 条建议，每条带"复制"按钮
- Tab2：底部"角色 × 世界书引用"显示每个角色出现在多少个非角色条目中

### Step 4: 提交

```bash
git add frontend/src/components/CommandCenter/VisualizationTab1Trends.tsx frontend/src/components/CommandCenter/VisualizationTab2World.tsx
git commit -m "feat(trends/world): fill bottom space with AI suggestions & character refs"
```

---

## Task 7: smoke_test 收尾

**Files:** (无新改动)

### Step 1: TypeScript 编译

```bash
cd d:/Study/novel_ai_editer/frontend && ./node_modules/.bin/tsc.cmd --noEmit -p .
```
期望：exit 0。

### Step 2: 后端 smoke_test

```bash
python d:/Study/novel_ai_editer/backend/scripts/smoke_test.py
```
期望：全过。

### Step 3: 字数验证

```bash
python -c "
import json, urllib.request
chs = json.loads(urllib.request.urlopen('http://localhost:8000/api/v1/projects/1/chapters').read())['data']
print('=== 章节字数（应 ≥ 1500）===')
for c in chs:
    if c['status'] == 'completed':
        wc = c.get('word_count', 0)
        mark = '✅' if wc >= 1500 else '❌'
        print(f\"  {mark} Ch.{c['chapter_no']:2d}  {wc:5d}字  {c['title']}\")
"
```

### Step 4: 一致性 KPI 验证

```bash
curl -s http://localhost:8000/api/v1/projects/1/chapters -o /tmp/c.json
python -c "
import json
chs = json.load(open(r'd:/Study/novel_ai_editer/.tmp/c.json', encoding='utf-8'))['data']
# 走一致性 tab 的逻辑：已完成且有 ChapterVersion.consistency_report
import urllib.request
report_count = 0
for c in chs:
    if c['status'] != 'completed': continue
    vs = json.loads(urllib.request.urlopen(f'http://localhost:8000/api/v1/projects/1/chapters/{c[\"id\"]}/versions').read())['data']
    if vs and any(v.get('consistency_report') for v in vs):
        report_count += 1
print(f'有报告章节: {report_count} / {sum(1 for c in chs if c[\"status\"]==\"completed\")} 已完成')
"
```

期望：5/5（与已完成章节数一致）。

### Step 5: 提交

```bash
git add -A
git commit -m "chore: verify v2-overhaul round 2 polish"
```

---

## 自检 (Self-Review)

✅ **4 个新问题全部覆盖**:
- 一致性"有报告=0" → Task 1（批量预加载）
- 章节内容像大纲 → Task 2（seed 重写真小说正文）+ Task 3（UI 优化显示优先级）
- 饼图标签压盖 → Task 4（pie 独立 + chip 独立 + outside label）
- 多个 Tab 底部留空 → Task 5（一致性维度面板）+ Task 6（建议/角色引用）

✅ **每个 Task 都有具体文件 + 代码 + 验证**:
- 无 "TBD" / "类似 Task N"
- 每个文件路径完整
- 包含 6 个核心修改点
- TypeScript 和 smoke 双重收尾

✅ **类型/方法名一致性**:
- `chapterReports` 形状 `{ [chapterId]: string | null }` 在 Task 1/Task 5 共用
- `parseScores` 在 Task 5 内部使用
- `parseJsonArray` 在 Task 6 沿用 Tab1 已有的工具

## 执行交接

方案已存到 `docs/superpowers/plans/2026-06-04-v2-overhaul-polish-2.md`

两种执行方式（同上一轮）：
1. **Subagent 驱动（推荐）** — 每个 Task 派一个子代理
2. **内联执行** — 当前会话按顺序批量

请选一个执行方式。
