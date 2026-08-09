# AI 产品机会日报生成器

这个目录从实时公开来源生成每日快照，再把结构化 JSON 同时渲染为：

- `YYYY-MM-DD.html`：可点击、可筛选、响应式完整日报
- `YYYY-MM-DD.png`：1080×1440 竖版视觉封面
- `latest.html` / `latest.png`：始终指向最新生成结果
- `index.html`：GitHub Pages 与目录访问使用的默认首页，与 `latest.html` 同步

## 实时生成今天的日报

```bash
python3 run_report.py
```

这条命令会依次：

1. 读取 GitHub Trending Daily / Weekly、GitHub Repository / Release API 与 Product Hunt 公开 Feed。
2. 保存 `snapshots/YYYY-MM-DD/` 原始响应与标准化快照。
3. 生成 `YYYY-MM-DD.json`、HTML、PNG，并更新 `latest.html` / `latest.png`。

可选设置 `GITHUB_TOKEN` 提升 GitHub API 限额；Product Hunt 公开 Feed 不需要令牌，但不提供票数和精确日榜排名，这一缺口会显示在报告中。

### 全新环境首次运行

克隆仓库后，先安装截图依赖，再执行日报编排器：

```bash
git clone https://github.com/qihanqiu980-gif/ai-product-opportunity.git
cd ai-product-opportunity
npm ci
npx playwright install chromium
python3 run_report.py
```

以后手动生成当天日报只需要：

```bash
python3 run_report.py
```

如果只需要 JSON 和 HTML、不需要 PNG 封面，可以运行：

```bash
python3 run_report.py --no-capture
```

## GitHub Actions 每日自动生成

仓库内置 `.github/workflows/daily-report.yml`：

- 每天北京时间 08:15 自动实时采集。
- 自动生成当天 JSON、HTML、PNG、原始快照并更新 `index.html`、`latest.html`、`latest.png`。
- 截图阶段会检查最小字号、横向溢出、封面尺寸和控制台错误；检查失败时不会提交错误产物。
- 成功后由 `github-actions[bot]` 自动提交并推送到 `main`，随后 GitHub Pages 自动发布。
- 也可以在 GitHub 仓库的 `Actions` 页面手动运行 `Generate daily AI opportunity report`。

工作流使用 GitHub 自动提供的 `GITHUB_TOKEN`，不需要保存个人访问令牌。定时任务属于 GitHub 仓库，而不是本地 Git；单纯复制到电脑不会在电脑上自动定时运行。Fork 或复制到另一个 GitHub 仓库后，GitHub 出于安全原因可能要求仓库所有者首次启用 Actions，并需要为新仓库单独启用 Pages。

## 使用 Codex 在电脑上定时生成

不使用 GitHub Actions 也可以自动生成日报，可以把仓库克隆到自己的电脑，再让 Codex 桌面端的定时任务每天在本地项目中执行生成脚本。

### 1. 克隆并完成首次运行

```bash
git clone https://github.com/qihanqiu980-gif/ai-product-opportunity.git
cd ai-product-opportunity
npm ci
npx playwright install chromium
python3 run_report.py
```

首次运行成功后，把 `ai-product-opportunity` 文件夹添加为 Codex 项目。

### 2. 创建 Codex 定时任务

在 Codex 中创建每天北京时间 08:15 运行的项目定时任务，建议选择直接在本地项目中运行。可以使用下面的任务说明：

```text
在当前 AI 产品机会日报项目中执行每日更新：

1. 执行 git pull --ff-only 获取远程更新。
2. 执行 npm ci，确保截图依赖与锁文件一致。
3. 执行 python3 run_report.py。
4. 确认当天 HTML、JSON、PNG、采集快照以及 latest 文件生成成功。
5. 如果配置了可写的远程仓库并且存在文件变化，执行 git add -A，创建当日日报提交并推送到 main；没有变化时不要创建空提交。
6. 如果采集、质量检查、提交或推送失败，保留错误信息并通知用户，不要覆盖已有的成功日报。
```

正式定时运行前，先在普通 Codex 任务中测试一次这段说明，确认网络、文件写入和 Git 推送权限正常。Codex 定时任务会使用当前默认沙箱权限；如果权限不允许访问网络、修改项目文件或执行 Git 推送，相关步骤会失败。

根据 [OpenAI 官方 Codex 定时任务文档](https://learn.chatgpt.com/codex/automations)，操作本地项目时必须满足：

- 朋友的电脑保持开机且没有进入会阻止任务运行的休眠状态。
- Codex/ChatGPT 桌面应用保持运行。
- 本地项目目录仍然存在，并且网络连接可用。
- 如果需要自动推送，Git 必须已经登录有写入权限的 GitHub 账号。

### 3. 选择是否推送到远程仓库

如果只需要在朋友电脑上生成日报，不需要修改 Git 远程地址，生成结果会保存在本地项目目录中。但朋友直接克隆本仓库后，默认 `origin` 指向 `qihanqiu980-gif/ai-product-opportunity`；没有该仓库写入权限时，自动推送会失败。

如果朋友希望推送到自己的 GitHub 仓库，应先在自己的账号下创建一个空仓库，然后执行：

```bash
git remote set-url origin https://github.com/FRIEND_USERNAME/ai-product-opportunity.git
git push -u origin main
```

把 `FRIEND_USERNAME` 替换为朋友的 GitHub 用户名。若还要提供公开网页，需要在朋友的新仓库中单独启用 GitHub Pages：`main` 分支、`/(root)` 目录。

### 两种自动化方式的区别

| 方式 | 执行位置 | 电脑需要开机 | 适合场景 |
| --- | --- | --- | --- |
| GitHub Actions | GitHub 云端运行器 | 不需要 | 长期稳定地生成、提交并发布公开日报 |
| Codex 定时任务 | 朋友的本地电脑 | 需要，桌面应用也需运行 | 本地保存，或使用朋友电脑上的 Git 凭据推送 |

`git clone` 只负责复制项目文件；真正的自动运行仍需要一次性创建 Codex 定时任务。设置完成后，后续每日生成不需要人工执行命令。

## 指定日期与历史回放

```bash
python3 run_report.py --date 2026-08-08
python3 run_report.py --date 2026-08-07 --mode replay
```

- 今天：执行实时采集并覆盖当天快照。
- 过去日期：只能从当天已经保存的 `snapshots/YYYY-MM-DD/snapshot.json` 精确回放。
- 没有快照的历史日期会明确失败。GitHub Trending 没有官方任意历史日期接口，系统不会用今天的数据伪装成昨天。
- 回放历史报告不会覆盖 `latest.html` / `latest.png`。
- 每份生成的 HTML 顶部都会列出当前目录中实际存在的历史日报日期；选择日期即可打开对应的 `YYYY-MM-DD.html`，不会跳转到未生成的日期。每天实时生成后，编排器会同步刷新已有历史 HTML 的日期列表。

## 分步生成

```bash
python3 render_report.py --input 2026-08-08.json
node capture-report.mjs --html 2026-08-08.html --png 2026-08-08.png
```

HTML 生成不依赖第三方包。截图脚本优先使用当前 Node 环境中的 Playwright；若没有，会尝试 Codex 桌面端的 bundled workspace runtime，并使用本机 Chrome 完成 PNG 截图。

也可以只采集 JSON：

```bash
python3 collect_report.py --date today
```

JSON 顶层字段参考当天生成文件。每个 GitHub / Product Hunt 项目包含三条独立轴线：

- `novelty`：GitHub 仓库创建时间、Product Hunt 发布时间与本地首次捕获日期。
- `momentum`：Trending 周期新增 Star、榜单位置或公开 Feed 位置。
- `change`：Release、明确发布或普通活跃证据；普通 push 不自动算重要更新。

所有判断型内容必须可追溯：`brief`、`trendSignals`、`opportunity` 和 `crossOpportunities` 中的每一项都要包含 `sources` 数组，每个来源使用 `{ "label": "来源名", "url": "原始页面" }`。生成器会拒绝缺少可点击依据的日报。
