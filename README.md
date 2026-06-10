<div align="center">

# 墨问 · Novel AI Editor

**让 AI 落墨成卷，为你写百万字江山**

一款全链路自动化的 AI 小说创作工作台。从一个题材关键词出发，系统会按"规划 → 逐章创作 → 一致性审查"三阶段自动产出可读的长篇草稿，内置热点探索、世界观构建、角色图谱、剧情编排、章节写作、实体提取、Human-in-the-Loop 确认和导出归档完整链路。

[English](#) · [快速上手](#-快速上手) · [界面预览](#-界面预览) · [架构设计](docs/ARCHITECTURE.md) · [贡献指南](#-贡献指南)

</div>

<div align="center">

![GitHub stars](https://img.shields.io/github/stars/yourname/novel-ai-editer?style=flat-square)
![GitHub forks](https://img.shields.io/github/forks/yourname/novel-ai-editer?style=flat-square)
![GitHub issues](https://img.shields.io/github/issues/yourname/novel-ai-editer?style=flat-square)
![GitHub license](https://img.shields.io/github/license/yourname/novel-ai-editer?style=flat-square)
![Docker pulls](https://img.shields.io/docker/pulls/yourname/novel-ai-editer?style=flat-square)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)

![Made with React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white&style=flat-square)
![Made with FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white&style=flat-square)
![Powered by MySQL](https://img.shields.io/badge/MySQL-8.4-4479A1?logo=mysql&logoColor=white&style=flat-square)
![Powered by Neo4j](https://img.shields.io/badge/Neo4j-5.24-018bff?logo=neo4j&logoColor=white&style=flat-square)
![Docker ready](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white&style=flat-square)
![TypeScript](https://img.shields.io/badge/TypeScript-5.8-3178C6?logo=typescript&logoColor=white&style=flat-square)

</div>

---

## ✨ 项目亮点

| 模块 | 能力 | 一句话价值 |
| ---- | ---- | ---------- |
| 🎨 **水墨主题系统** | 6 张内置水墨图 + 自定义上传 + 实时主色提取 | 切一次主题，整个 UI（背景 / 按钮 / 边框 / 卡片）颜色都跟着变 |
| 🤖 **全链路 AI 编排** | 热点 → 世界观 → 角色图谱 → 剧情规划 → 章节写作 → 一致性检查 | 给一个题材 + 初始 prompt，AI 自动跑完全流程 |
| 🛑 **Human-in-the-Loop** | 关键节点（确认点）可暂停人工审批 | 不想全自动？随时介入把控方向 |
| 🕸️ **知识图谱** | Neo4j 存角色关系 / 实体关系 / 故事事件 | 跨章节自动保持人物关系一致性 |
| 📊 **大屏指挥中心** | 8 阶段工作流 + 8 个可视化 Tab | 单一屏幕看清 AI 创作全过程 |
| 🔁 **多模型降级链** | NVIDIA NIM + 自定义 fallback 链 | 主模型挂掉自动切备，主线任务不中断 |
| 🐳 **Docker 一键拉起** | 4 个服务（web/api/mysql/neo4j）编排 | 5 分钟从克隆到能用 |

---

## 📸 界面预览

> 以下截图全部由 [scripts/capture_e2e.py](scripts/capture_e2e.py) 真实操作（注册→建项目→切主题→切 Tab）后由 Playwright + 系统 Edge headless 抓取，分辨率 1920×1080。

### 1. 用户流程（真实操作截图）

| # | 步骤 | 截图 |
| - | ---- | ---- |
| 1 | 登录页（水墨紫主题） | ![Login](docs/screenshots/01-login.png) |
| 2 | 切换到"注册" tab | ![Register Tab](docs/screenshots/02-register-tab.png) |
| 3 | 填写注册信息 | ![Register Filled](docs/screenshots/03-register-filled.png) |
| 4 | 注册成功，进入主系统 | ![Home](docs/screenshots/04-home-after-register.png) |
| 5 | 新建创作项目（弹窗） | ![New Project](docs/screenshots/05-new-project-modal.png) |
| 6 | 填写项目名称 + 主题关键词 | ![New Project Filled](docs/screenshots/06-new-project-filled.png) |
| 7 | 项目创建完成 | ![Project Created](docs/screenshots/07-after-create-project.png) |
| 8 | 主题切换面板（6 张主题 + 上传） | ![Theme Switcher](docs/screenshots/08-theme-switcher.png) |
| 11 | 启动 AI 创作（多模型 + fallback 链） | ![Start Creation](docs/screenshots/11-start-creation-modal.png) |

### 2. 三套主题对比（同一界面，不同主题）

| 主题 | 配色 | 截图 |
| ---- | ---- | ---- |
| 墨问·默认 | 紫罗兰（毛笔书法） | ![Default](docs/screenshots/10-theme-mowen-default.png) |
| 宁静·远景 | 青碧玉 | ![Cyan](docs/screenshots/09-theme-cyan-jade.png) |
| 秋枫·霞谷 | 朱砂红 | ![Vermilion](docs/screenshots/21-theme-vermilion.png) |

### 3. 大屏指挥中心 · 8 个可视化 Tab

| Tab | 用途 | 截图 |
| --- | ---- | ---- |
| **热点探索** | 联网搜索题材热点 + 趋势分析 | ![](docs/screenshots/12-tab-热点探索.png) |
| **世界构建** | 自动生成世界观设定、势力、地理 | ![](docs/screenshots/13-tab-世界构建.png) |
| **章节写作** | 章节状态、字数、进度一目了然 | ![](docs/screenshots/14-tab-章节写作.png) |
| **一致性检查** | 5 维雷达图 + 角色/剧情一致性评分 | ![](docs/screenshots/15-tab-一致性检查.png) |
| **故事图谱** | D3 力导向图，5 类节点（角色/剧情/事件/世界观/主题） | ![](docs/screenshots/16-tab-故事图谱.png) |
| **故事脉络** | Story Arc 故事线展开 + 节点关系 | ![](docs/screenshots/17-tab-故事脉络.png) |
| **全局统计** | 实时 KPI、字数趋势、章节完成率 | ![](docs/screenshots/18-tab-全局统计.png) |
| **故事总览** | 仪表盘 + 创作指导建议 | ![](docs/screenshots/19-tab-故事总览.png) |

### 4. 后端 API 文档

![API Docs](docs/screenshots/03-api-docs.png)

### 5. Neo4j Browser（关系图谱）

![Neo4j](docs/screenshots/04-neo4j.png)

> 6 张内置主题的高清原图（含水墨山水、登录页专属）位于 `frontend/public/themes/`，可直接拖到浏览器看完整效果。

---

## 🏗️ 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│  ① 前端层  React 19 + Vite + TypeScript                       │
│     ECharts / D3 / Lucide / React Context                     │
│     水墨主题系统 · 大屏指挥中心 · 8 阶段工作流面板              │
└──────────────────────────┬───────────────────────────────────┘
                           │  HTTP/JSON  (Nginx 反代 /api → :8000)
┌──────────────────────────▼───────────────────────────────────┐
│  ② API 层  FastAPI (Python 3.12, :8000)                      │
│     路由: projects / tasks / chapters / characters /         │
│           graph / worldbook / trends / workflow / openrouter │
│     → Pydantic 校验 · OpenAPI 文档 · 统一响应包装              │
└──────────────────────────┬───────────────────────────────────┘
                           │  内部函数调用
┌──────────────────────────▼───────────────────────────────────┐
│  ③ 服务层  Python asyncio                                      │
│     novel_orchestrator_service   编排器（3 阶段调度）           │
│     chapter_task_service         章节循环执行                  │
│     confirmation_engine          Human-in-the-Loop            │
│     openrouter_service           LLM 调用封装 (OpenAI 兼容)    │
│     degradation_service          降级 / 重试 / 退避            │
│     rate_limiter                 滑动窗口限流 (Redis)          │
│     task_runtime_service         任务运行时状态 (Redis 缓存)   │
│     theme_context                前端主题上下文（React 端）    │
└────────┬───────────────┬──────────────────┬──────────────────┘
         │               │                  │
┌────────▼─────┐ ┌───────▼──────┐ ┌─────────▼────────┐
│ ④-1 MySQL    │ │ ④-2 Neo4j    │ │ ④-3 LLM Gateway  │
│  业务数据      │ │  实体关系图   │ │ NVIDIA NIM (主)   │
│  utf8mb4      │ │  Cypher 查询 │ │ + 自定义 Fallback │
└──────────────┘ └──────────────┘ └──────────────────┘
```

> 📖 完整架构设计、模块依赖、数据流 → [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## 🚀 快速上手

> **前置要求**：Docker 24.0+ 与 Docker Compose 2.20+。其他都不需要，连 Python 都不用装。

### 1. 克隆仓库

```bash
git clone https://github.com/yourname/novel-ai-editer.git
cd novel-ai-editer
```

### 2. 准备 LLM 凭证

复制环境变量模板，填入你的 NVIDIA NIM 平台 token（[免费申请](https://build.nvidia.com/)）：

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env，至少填这一行：
#   NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxx
```

> 如果你想用 OpenAI / Anthropic / 其他 OpenAI 兼容端点，把 `NVIDIA_BASE_URL` 改成对应地址，并把 `NVIDIA_API_KEY` 换成对应平台的 key 即可。所有 LLM 字段都以 `NVIDIA_` 开头只是因为我们主用 NVIDIA NIM。

### 3. 一键启动

```bash
docker compose up -d --build
```

等待 1-2 分钟（首次构建需要装依赖），直到 4 个容器都 healthy：

```bash
docker compose ps
# 期望看到 4 个 (healthy)：
#   novel_ai_web    → http://localhost:8080
#   novel_ai_api    → http://localhost:8000
#   novel_ai_mysql  → 内网 3306 / 主机 3307
#   novel_ai_neo4j  → http://localhost:7474
```

### 4. 访问

| 地址 | 说明 |
| ---- | ---- |
| <http://localhost:8080> | 前端主界面（注册 / 登录） |
| <http://localhost:8000/api/v1/docs> | 后端 Swagger 文档 |
| <http://localhost:7474> | Neo4j Browser（账号 `neo4j` / 密码见 `.env`） |

### 5. 重建 / 回滚

**Windows PowerShell**：
```powershell
powershell -ExecutionPolicy Bypass -File scripts/rebuild.ps1
powershell -ExecutionPolicy Bypass -File scripts/rollback.ps1
```

**Linux / macOS**：
```bash
bash scripts/rebuild.sh
bash scripts/rollback.sh
```

### 6. 重新生成 README 截图

需要 Python 3.10+ 和 Playwright：

```bash
pip install playwright
python -m playwright install chromium
python scripts/capture_e2e.py    # 20+ 张核心流程截图
python scripts/capture_extra.py # 主题对比 + AI 聊天补充
```

> 脚本默认调用系统 Edge（`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`），
> 避免下载 200MB+ 的 chromium。需要在 Linux/macOS 上跑时把 `EDGE` 常量改成自己的路径。

---

## 🎨 主题系统

水墨主题是本项目最具特色的功能，6 张内置主题 + 任意自定义上传。

### 工作原理

```
  用户选主题 / 上传图片
            │
            ▼
  ┌─────────────────────┐
  │ Median Cut 量化取色  │  ←  src/lib/colorExtractor.ts
  │ 饱和度/亮度评分排序   │     零依赖，纯 Canvas
  └──────────┬──────────┘
             │
             ▼  Palette { primary, secondary, primarySoft, secondaryLight, colors[5] }
             │
  ┌──────────▼──────────────────────────────┐
  │ ThemeContext.applyPaletteToRoot()        │  ←  src/contexts/ThemeContext.tsx
  │ 写入 :root 的 CSS 变量（约 50 个）         │
  │   --theme-primary / --theme-secondary    │
  │   --theme-primary-{04,05,06,08,10,12,    │
  │     15,18,20,22,25,30,35,40,50}          │   15 个 alpha 级别
  │   --theme-secondary-{05...50}            │
  │   --theme-bg-image / --theme-bg-blur     │
  │   --ink-deep / --ink-deep-mid / --ink-   │
  │     deep-strong + 全部 --cc-* 兼容变量    │
  └──────────┬──────────────────────────────┘
             │
             ▼
       整个 UI 立刻换色
```

### 6 套内置主题

| 主题 | 主色 | 适用场景 |
| ---- | ---- | -------- |
| **墨问·默认** | 紫罗兰 #7c3aed | 通用，长篇创作 |
| **墨问·登录页** | 紫罗兰 + 楼阁 | 登录页专属 |
| **宁静·远景** | 青碧玉 #4f9a8c | 仙侠、修真 |
| **月林·空竹** | 冷月青 #5a7c8a | 古风、悬疑 |
| **梦幻·山水** | 紫蓝 #8b5cf6 | 玄幻、奇幻 |
| **秋枫·霞谷** | 朱砂红 #c0392b | 历史、权谋、爱情 |

### 自定义上传

点右上角"主题"按钮 → 点最后一张 "上传我的背景" 卡片 → 选一张图（jpg / png / webp）→ 系统会：

1. 把图片编码成 dataURL 持久化到 localStorage（`novel-ai.theme.v1`）
2. Canvas 提取 5 个主色（Median Cut 算法）
3. 立刻应用到 UI
4. 重新进入页面也会保留

### 颜色提取算法

`colorExtractor.ts` 实现的是**带权 Median Cut**：

- 用 Canvas 读取像素，丢弃透明像素和过亮 / 过暗像素
- 迭代地把当前最大色差桶二分（最多 7 层 → 128 个桶）
- 合并相邻相近桶
- 按 `饱和度 × 0.6 + 亮度适配度 × 0.4` 评分排序
- 输出 5 个最具代表性的颜色

零依赖、~150 行 TS、可在 jsdom 里跑单元测试。

---

## 🛠️ 技术栈

### 前端

| 选型 | 用途 |
| ---- | ---- |
| **React 19** | UI 框架 |
| **Vite 6** | 构建 / HMR |
| **TypeScript 5.8** | 类型系统 |
| **React Router 7** | 路由 |
| **ECharts 5** + **D3 7** | 数据可视化（雷达图、力导向图、词云、折线图） |
| **react-markdown** + **react-syntax-highlighter** | AI 回复的 Markdown 渲染 |
| **lucide-react** | 图标库 |
| **Vitest** + **Testing Library** | 单元测试（jsdom） |

### 后端

| 选型 | 用途 |
| ---- | ---- |
| **FastAPI 0.115** | Web 框架 |
| **SQLAlchemy 2 (async)** | ORM |
| **Pydantic v2** | 数据校验 / 配置 |
| **Alembic** | 数据库迁移 |
| **aiomysql** | MySQL 异步驱动 |
| **Neo4j Python Driver** | 图数据库驱动 |
| **Redis 5** | 缓存 + 限流 + 取消注册 |
| **httpx** | 异步 HTTP 客户端（调 LLM / 搜索） |
| **pytest** | 单元测试 / 集成测试 |

### 基础设施

| 选型 | 用途 |
| ---- | ---- |
| **Docker Compose** | 4 服务编排（web/api/mysql/neo4j） |
| **Nginx** | 前端静态托管 + `/api` 反代 |
| **GitHub Actions**（可选） | CI/CD |

---

## 📂 项目结构

```
novel-ai-editer/
├── frontend/                 # React 19 + Vite 前端
│   ├── src/
│   │   ├── components/       # 业务组件（CommandCenter / ThemeSwitcher / …）
│   │   ├── contexts/         # React Context（Theme / Auth / Project）
│   │   ├── lib/              # 工具（colorExtractor / api / auth）
│   │   ├── pages/            # 路由级页面
│   │   └── styles.css        # 全局 CSS（含 :root 主题变量定义）
│   └── public/themes/        # 6 张内置主题背景图
│
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── api/routes/       # 路由模块（projects/tasks/chapters/…）
│   │   ├── core/             # 配置 / 安全 / 弹性（degradation）
│   │   ├── db/               # ORM 模型 / 会话
│   │   ├── graph/            # Neo4j 客户端
│   │   ├── integrations/     # 外部 API 客户端（OpenAI 兼容 / Tavily / Firecrawl）
│   │   ├── models/           # SQLAlchemy 模型
│   │   ├── schemas/          # Pydantic 模型
│   │   └── services/         # 业务逻辑（编排器 / 确认引擎 / 限流 / 任务运行时）
│   ├── migrations/           # Alembic 数据库迁移
│   ├── scripts/              # 维护脚本（seed / smoke test / 数据修复）
│   └── tests/                # pytest 单元测试
│
├── docs/                     # 项目文档
│   ├── PRD.md                # 产品需求文档
│   ├── ARCHITECTURE.md       # 技术架构（30 分钟读懂项目）
│   ├── DEPLOYMENT.md         # 部署指南
│   ├── OPERATIONS.md         # 运维手册
│   ├── API_CHEATSHEET.md     # API 速查表
│   ├── AI_PROMPTS.md         # 提示词工程笔记
│   └── screenshots/          # README 引用截图（自动生成）
│
├── cache-memory/             # 项目内"开发记忆"（计划 / 风险 / 复盘 / 迭代日志）
│
├── scripts/                  # 跨语言工具脚本
│   ├── rebuild.ps1 / .sh     # 重建镜像
│   ├── rollback.ps1 / .sh    # 回滚版本
│   ├── screenshot.ps1        # 截 README 展示图（Edge headless）
│   ├── capture_e2e.py        # E2E 流程截图（注册→建项目→主题→Tab）
│   ├── capture_extra.py      # 主题对比 + 启动创作弹窗
│   └── capture_10_20.py      # 补拍脚本
│
├── docker-compose.yml        # 4 服务编排
├── .env.example              # 环境变量模板
└── README.md                 # 你正在读的这份
```

---

## 🧪 本地开发（不用 Docker）

### 后端

```bash
cd backend
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，至少填 NVIDIA_API_KEY
uvicorn app.main:app --reload
```

### 前端

```bash
cd frontend
npm install
npm run dev
# 浏览器打开 http://localhost:5173
```

> 前端 `VITE_API_BASE_URL` 默认指向 `/api/v1`（Nginx 反代），如果直接 `npm run dev` 跑，Vite 会自动 proxy 到 `http://localhost:8000`。

### 测试

```bash
# 后端
cd backend && pytest

# 前端
cd frontend && npm test
```

---

## 📚 进阶阅读

| 文档 | 适合谁 | 内容 |
| ---- | ------ | ---- |
| [PRD.md](docs/PRD.md) | 产品 / 项目经理 | 功能矩阵、用户画像、迭代路线 |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | 新入职工程师 | 30 分钟读懂系统分层 + 三阶段主链路 |
| [API_CHEATSHEET.md](docs/API_CHEATSHEET.md) | 前端 / 集成方 | 所有高频 REST 端点 + curl 示例 |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | 运维 | 部署步骤 / 资源评估 / 域名 / TLS |
| [OPERATIONS.md](docs/OPERATIONS.md) | 运维 / 二次开发 | 5 分钟启动 + 15 分钟排错 |
| [AI_PROMPTS.md](docs/AI_PROMPTS.md) | AI 工程师 | 系统提示词演进 + Few-shot 案例 |
| [OPTIMIZATION_PROMPT.md](docs/OPTIMIZATION_PROMPT.md) | 调优者 | 性能 / 成本 / 质量调优提示词 |
| [screenshot-guide.md](docs/screenshot-guide.md) | 维护者 | README 截图的采集方法 |

---

## 🤝 贡献指南

我们非常欢迎 PR / Issue / Discussion！

### 提 PR 之前

1. Fork 仓库，创建特性分支：`git checkout -b feat/your-feature`
2. 遵循现有代码风格（前端 ESLint + Prettier，后端 Black + isort）
3. 跑测试：`cd backend && pytest` / `cd frontend && npm test`
4. 写清晰的 commit message（推荐 [Conventional Commits](https://www.conventionalcommits.org/)）
5. 在 PR 描述里说清楚：动机 / 实现思路 / 测试情况 / 截图（UI 类改动）

### 提 Issue 时

- Bug 报告：环境（OS / Docker 版本 / 浏览器）+ 复现步骤 + 期望行为 + 实际行为 + 日志
- 功能建议：使用场景 + 为什么现有功能不够用 + 你期望的交互

### 路线图（Roadmap）

- [ ] 章节协作编辑（多人光标）
- [ ] AI 自动配图（基于章节内容生成封面）
- [ ] 移动端适配
- [ ] i18n 完整英文版本
- [ ] WebSocket 流式输出优化（断点续传）

> 想认领任意一个？欢迎开 Issue 标注 `I want to work on this`。

---

## 🛡️ 安全说明

⚠️ **本项目默认配置包含演示用密码与密钥，部署到公网前务必修改！**

### 必改项

| 项 | 在哪儿 | 生成方式 |
| -- | ------ | -------- |
| `SECRET_KEY` | `backend/.env` | `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `MYSQL_PASSWORD` | `docker-compose.yml` | 强随机字符串 |
| `NEO4J_AUTH` | `docker-compose.yml` | `neo4j/<强密码>` |
| `NVIDIA_API_KEY` | `backend/.env` | NVIDIA 平台个人 token |

### 不要把 `.env` 提交进 Git

`.env` 已在 `.gitignore` 中，但请养成习惯：本地调试用 `.env`、仓库里只保留 `.env.example` 占位。

### 发现安全漏洞

请 **不要** 公开提 Issue，邮件联系维护者（见 [docs/OPERATIONS.md](docs/OPERATIONS.md)），我们会在 24 小时内响应。

---

## 📜 License

[MIT](LICENSE) · 你可以自由使用、修改、分发本项目（包括商业用途），但请保留版权声明。

> 第三方依赖各自遵循其原始 License（详见 `package.json` / `requirements.txt` 的 `license` 字段）。

---

## 🙏 致谢

- 灵感来源：传统中式水墨画审美 + 现代 AI 工程实践
- LLM Gateway：[NVIDIA NIM](https://build.nvidia.com/) 提供 OpenAI 兼容的免费模型层
- 可视化：[Apache ECharts](https://echarts.apache.org/) + [D3.js](https://d3js.org/)
- 图谱：[Neo4j](https://neo4j.com/) Community Edition
- 图标：[Lucide](https://lucide.dev/)
- 字体：[Ma Shan Zheng](https://fonts.google.com/specimen/Ma+Shan+Zheng) (毛笔) + [Noto Serif SC](https://fonts.google.com/noto/specimen/Noto+Serif+SC) (思源宋体)

---

<div align="center">

**如果这个项目对你有帮助，请点一个 ⭐ Star！**

Made with 🖌️ & ☕ by [yourname](https://github.com/yourname)

</div>
