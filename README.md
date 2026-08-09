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
