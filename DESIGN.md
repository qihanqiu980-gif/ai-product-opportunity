---
name: Signal Brief
description: 一张每天更新的 AI 产品机会判断界面
colors:
  paper: "oklch(1 0 0)"
  cool-canvas: "oklch(0.975 0.006 240)"
  signal-green: "oklch(0.49 0.14 160)"
  signal-mint: "oklch(0.78 0.10 160)"
  source-blue: "oklch(0.54 0.18 250)"
  ink: "oklch(0.19 0.018 245)"
  muted-ink: "oklch(0.49 0.022 245)"
  demo-ink: "oklch(0.42 0.11 62)"
  on-dark: "oklch(0.84 0.012 245)"
  on-dark-strong: "oklch(0.88 0.01 245)"
  on-dark-muted: "oklch(0.72 0.01 245)"
  cover-muted: "oklch(0.78 0.01 245)"
  hairline: "oklch(0.90 0.012 240)"
rounded:
  micro: "2px"
  xs: "4px"
  tag: "6px"
  sm: "8px"
  md: "12px"
  lg: "16px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  2xl: "32px"
  3xl: "48px"
---

# Design System: Signal Brief

## 1. Overview

**Creative North Star: "编辑部的晨间信号台"**

这是一个给产品经理使用的工作界面，不是宣传页。整体像一份经过编辑判断的财经晨报：纯白纸面、清晰的栏线、少量高辨识度颜色，以及能够快速横向比较的密集信息行。视觉节奏由标题、留白、编号和细线建立，阴影与装饰只在交互反馈中出现。

界面明确拒绝纯文本消息换皮、等权卡片瀑布、紫蓝 AI 渐变和玻璃拟态。视觉重点必须来自真实数据、判断优先级和可点击的下一步。

**Key Characteristics:**

- 编辑式层级，先结论后证据
- 产品界面的熟悉感与稳定密度
- 绿色代表机会判断，蓝色代表来源与链接
- 大面积纯白，低色量，清晰细线
- 同一数据适配桌面完整报告与 1080×1440 竖版封面

## 2. Colors

采用 Restrained 策略：纯白承担画布，苔藓绿表达机会与优先级，钴蓝只用于来源、链接和信息状态。

### Primary

- **Signal Green** (`oklch(0.49 0.14 160)`): 机会评分、主操作、选中状态和关键结论。

### Secondary

- **Source Blue** (`oklch(0.54 0.18 250)`): GitHub / Product Hunt 来源、外链与信息状态。

### Neutral

- **Paper** (`oklch(1 0 0)`): 页面主背景。
- **Cool Canvas** (`oklch(0.975 0.006 240)`): 工具栏、摘要区和弱分组背景。
- **Ink** (`oklch(0.19 0.018 245)`): 正文和标题。
- **Muted Ink** (`oklch(0.49 0.022 245)`): 辅助说明。
- **Hairline** (`oklch(0.90 0.012 240)`): 表格与区域分隔。

**The Signal Rarity Rule.** Signal Green 在任一屏幕上的面积不超过约 10%，它的稀缺性就是优先级。

## 3. Typography

**Display Font:** system-ui, `-apple-system`, "PingFang SC", "Microsoft YaHei", sans-serif  
**Body Font:** 与 Display 相同  
**Label/Mono Font:** ui-monospace, "SFMono-Regular", Menlo, monospace

**Character:** 统一的系统字体保证中文稳定、加载即时。层级通过字重、字号、行高与留白建立，不依赖展示字体。

### Hierarchy

- **Display** (750, 44px, 1.08): 日报主标题，仅出现一次。
- **Headline** (700, 28px, 1.2): 核心判断与主要章节。
- **Title** (650, 18px, 1.35): 项目名与次级章节。
- **Body** (400, 1rem / 16px, 1.68): 说明与分析，长段落控制在 72ch 内。
- **Label** (650, 0.9375rem / 15px, 0.06em): 来源、状态、编号和辅助元数据的最小字号，英文可大写，中文不强制大写。

**The 15px Floor Rule.** 页面与封面的任何可见文字不得小于 0.9375rem（默认根字号下为 15px）。渲染器在生成 HTML 时统一把字体像素值转换为 rem，并自动抬升低于该下限的声明。

**The Two-Second Rule.** 模糊视线时仍应在两秒内看见日报标题、今日判断和第一优先项目。

## 4. Elevation

默认无阴影，通过纯白、浅冷灰底、1px 细线和间距表达层级。只有可点击行在悬停时出现极轻的环境阴影，并同时改变边框或背景，避免把阴影当装饰。

### Shadow Vocabulary

- **Interactive Lift** (`0 12px 30px oklch(0.19 0.018 245 / 0.08)`): 仅用于可点击项目行的悬停反馈。

**The Flat-by-Default Rule.** 静态内容保持平面；深度只能作为交互状态反馈出现。

## 5. Components

### Buttons

- **Shape:** 8px 圆角，最小 44px 触控高度。
- **Primary:** Signal Green 填充、白色文字、横向 16px 内边距。
- **Hover / Focus:** 180ms 状态过渡；焦点使用 3px 半透明绿色外环。
- **Ghost:** 透明背景、Hairline 边框，悬停转为 Cool Canvas。

### Chips

- **Style:** 8px 圆角、浅色背景、15px 标签字，不使用胶囊形。
- **State:** 选中状态使用深色底与白字；未选中使用冷灰底与 Ink。

### Cards / Containers

- **Corner Style:** 12–16px，仅用于真正独立的摘要或机会判断。
- **Background:** Paper 或 Cool Canvas。
- **Shadow Strategy:** 默认无阴影。
- **Border:** 1px Hairline 全边框，不使用彩色粗侧边线。
- **Internal Padding:** 16 / 24 / 32px。

### Inputs / Fields

- **Style:** Paper 背景、1px Hairline、8px 圆角、44px 高度。
- **Focus:** Signal Green 边框与外环。
- **Error / Disabled:** 错误用文字与图标共同表达；禁用降低对比并移除指针反馈。

### Navigation

桌面端使用轻量顶部栏与页内索引；移动端索引变为横向可滚动导航。当前项由 Ink 加粗和细下划线共同表达。

顶部栏固定提供“历史日报”日期选择器，只展示实际已经生成 HTML 的日期。选择日期后直接进入对应日报；最新日期标记为“最新”，查看旧报告时当前项标记为“当前查看”。桌面端同时保留当前日期与采集状态，移动端优先保留品牌标识和日期选择器，交互高度不得低于 44px。

### Discovery Row

项目发现使用可比较的信息行，而不是独立卡片网格。桌面端按“项目 / 证据 / 机会”对齐，移动端重排为带字段标签的单列内容。

每个项目的证据列必须固定呈现三条独立轴线：

- **新鲜度**：仓库创建、Product Hunt 发布或首次捕获时间。
- **动量**：周期新增 Star、榜单位置或公开 Feed 位置。
- **实质变化**：Release 与明确发布优先；普通 push 只能表达活跃，不能自动标为重要更新。

状态标签使用“新仓库 / 近期发布 / 今日首次捕获 / 热度异动 / 重要更新 / 持续热门”等准确语义，不再用含义模糊的“新发现”覆盖所有项目。

### Evidence Links

所有判断型内容在正文后使用紧凑的“查看依据”链接组，允许一个判断对应多个原始来源。链接使用 Source Blue、6px 圆角和明确的外链箭头；深色机会面板使用白色文字与半透明边框，但保持同一组件语法。

## 6. Do's and Don'ts

### Do:

- **Do** 使用 4pt 基础间距尺度，并通过 8–12px 紧分组和 48–96px 章节间距建立节奏。
- **Do** 让原始链接、查询日期和去重状态始终可见或可展开。
- **Do** 为趋势、机会和交叉判断分别列出支撑它们的原始项目链接，而不是只在页面底部放一个总来源列表。
- **Do** 保证标签、链接、编号、图表说明和页脚文字均不小于 15px。
- **Do** 用编号、字重和留白表达优先级，颜色只作第二信号。
- **Do** 在 640px 与 960px 附近根据内容断点重组布局，而不是缩小所有文字。

### Don't:

- **Don't** 做成“纯 Markdown 长文”或“聊天消息截图的简单换皮”。
- **Don't** 使用“等权卡片堆叠”承载所有内容。
- **Don't** 使用“紫蓝渐变的通用 AI 仪表盘”或玻璃拟态。
- **Don't** 使用超过 1px 的彩色左右边框作为强调条。
- **Don't** 使用装饰性大数字、无意义图表或无法追溯的动态指标。
