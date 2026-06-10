# 截图采集指南

> README 中的公开截图（登录页 / API 文档 / 主题预览）用 `scripts/screenshot.ps1` 自动完成。
> 登录后的"大屏指挥中心"截图需要手动操作（带登录态 + 真实项目数据），下面是详细步骤。

---

## 🎯 你能拍到的"含金量最高"页面

| # | 页面 | URL | 推荐触发动作 |
| - | ---- | -- | ------------ |
| 1 | **登录页** | `/login` | 默认就是 — `01-login.png` |
| 2 | **空状态首页** | `/` | 首次登录、还没建项目 |
| 3 | **项目列表** | `/` | 已建 ≥ 1 个项目 |
| 4 | **指挥中心 · 总览** | `/projects/{id}` | 进入任一项目 |
| 5 | **新建项目弹窗** | 同上 | 点顶部"新建" |
| 6 | **启动创作弹窗** | 同上 | 点"启动创作" |
| 7 | **Tab 1 · 热点探索** | 同上 | 选 Tab 1 |
| 8 | **Tab 2 · 世界构建** | 同上 | 选 Tab 2 |
| 9 | **Tab 3 · 章节写作** | 同上 | 选 Tab 3 |
| 10 | **Tab 4 · 一致性** | 同上 | 选 Tab 4 |
| 11 | **Tab 5 · 实体关系图** | 同上 | 选 Tab 5（D3 力导向图） |
| 12 | **Tab 6 · 全局统计** | 同上 | 选 Tab 6 |
| 13 | **AI 聊天面板** | 同上 | 点底部"AI 助手"展开 |
| 14 | **主题切换面板** | 同上 | 点右上角"主题"按钮 |
| 15 | **后端 API 文档** | `/api/v1/docs` | `03-api-docs.png` |
| 16 | **Neo4j Browser** | `localhost:7474` | `04-neo4j.png` |

---

## 📐 推荐参数

| 项 | 值 |
| -- | -- |
| **分辨率** | 1920 × 1080（README 主图） |
| **缩放比** | 浏览器 100%（不要放大否则文字发虚） |
| **背景主题** | "墨问默认主题"（紫色水墨）做主图，切换"青碧玉" / "朱砂霞"做对比图 |
| **数据状态** | 至少 1 个项目 + 1 个章节（否则 Tab 3/4/5/6 是空状态） |

---

## 🛠️ 拍摄方法

### 方案 A：浏览器自带的截图（最简单）

1. Chrome / Edge 打开目标页面
2. 调好窗口大小（F12 → 设备工具栏关掉，选 Responsive → 1920×1080）
3. `Ctrl + Shift + P` → 输入 "screenshot" → 选 "Capture full size screenshot" 或 "Capture screenshot"

### 方案 B：PowerShell + Edge headless（推荐批量）

```powershell
# 单张
$edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$url = "http://localhost:8080/projects/2"
$out = "D:\Study\novel_ai_editer\docs\screenshots\04-project-detail.png"
$args = @(
    "--headless=new",
    "--disable-gpu",
    "--no-sandbox",
    "--hide-scrollbars",
    "--window-size=1920,1080",
    "--screenshot=`"$out`"",
    "--virtual-time-budget=10000",
    "`"$url`""
)
Start-Process -FilePath $edge -ArgumentList $args -NoNewWindow -Wait
```

### 方案 C：自动批量脚本（需要登录态）

> Edge headless 不支持从命令行预置 localStorage，所以**登录态必须靠 dev_user_data_dir 持久化**：

```powershell
# 第一步：手动登录一次，让 Edge 把 Cookie/localStorage 写进 profile 目录
$profile = "D:\System_Temp\edge-profile"
# 把 $profile 加到 Start-Process 的 --user-data-dir="$profile" 参数里

# 第二步：用同一 profile 跑 headless 截图，所有已登录态自动生效
$args = @(
    "--headless=new",
    "--user-data-dir=`"$profile`"",
    "--disable-gpu",
    "--no-sandbox",
    "--hide-scrollbars",
    "--window-size=1920,1080",
    "--screenshot=`"$out`"",
    "--virtual-time-budget=10000",
    "`"$url`""
)
Start-Process -FilePath $edge -ArgumentList $args -NoNewWindow -Wait
```

---

## 🎨 主题对比图拍摄建议

为了展示主题系统效果，**强烈建议拍 6 张同一页面 + 6 个主题的对比图**：

1. 选最复杂的 Tab 5（实体关系图）作为底图
2. 依次点 6 张主题卡片，每次等 ~500ms 颜色过渡完
3. 用 Windows 自带 `Snipping Tool` 录视频模式 → 切主题 → 录下"瞬间变色"的 GIF
4. 放 README 当 hero 动画

---

## 📦 把截图放哪儿

所有截图统一放 `docs/screenshots/`，命名规范：

- `01-login.png` — 公开页
- `03-api-docs.png` — 公开页
- `04-neo4j.png` — 公开页
- `theme-XX-xxx.png` — 主题缩略图
- `flow-01-empty-home.png` — 流程截图（按编号）
- `flow-02-new-project-modal.png`
- `flow-03-command-center.png`
- ...

> 截图记得 **commit 进来** —— README 直接引用相对路径才能在 GitHub 渲染。
