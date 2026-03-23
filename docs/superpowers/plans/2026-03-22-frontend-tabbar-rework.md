# 前端界面及底部状态栏调整 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 调整小程序底部状态栏为“伙伴、共读、加号/笔记、书城、我的”，并新增伙伴界面和书城界面，调整共读（原书架）界面的未绑定状态显示。

**Architecture:** 
- 修改 `app.json` 和 `custom-tab-bar` 组件以支持新的 5 个 Tab（4 个页面 + 1 个中间按钮）。
- 新增 `pages/partner/index`（伙伴）页面，处理绑定前和绑定后的状态（双人头像、绑定天数、解绑等）。
- 调整 `pages/home/index`（共读）页面，处理未绑定时的显示逻辑。
- 新增 `pages/bookstore/index`（书城）页面，提供基础的书城 UI。
- 中间的加号按钮改为钢笔/笔记样式的图标，提升质感。

**Tech Stack:** 微信小程序原生开发 (WXML, WXSS, JS)

---

### Task 1: 更新全局配置与自定义 TabBar

**Files:**
- Modify: `app.json`
- Modify: `custom-tab-bar/index.js`
- Modify: `custom-tab-bar/index.wxml`
- Modify: `custom-tab-bar/index.wxss`

- [ ] **Step 1: 更新 `app.json` 添加新页面**
  在 `pages` 数组中添加 `"pages/partner/index"` 和 `"pages/bookstore/index"`。
  在 `tabBar.list` 中更新为 4 个页面（伙伴、共读、书城、我的）。

- [ ] **Step 2: 更新 `custom-tab-bar/index.js`**
  修改 `data.list`，包含 4 个 Tab 的配置（路径、文本、图标）。

- [ ] **Step 3: 更新 `custom-tab-bar/index.wxml` 和 `index.wxss`**
  调整中间按钮的样式，将其从普通的加号改为一个“钢笔/笔记”的图标（可以使用 CSS 绘制或引入 icon）。

### Task 2: 创建“伙伴”页面 (Partner)

**Files:**
- Create: `pages/partner/index.js`
- Create: `pages/partner/index.wxml`
- Create: `pages/partner/index.wxss`
- Create: `pages/partner/index.json`

- [ ] **Step 1: 初始化页面文件**
  创建基本的页面结构和配置文件。

- [ ] **Step 2: 编写 WXML 结构 (绑定前 vs 绑定后)**
  - **绑定前**：显示输入邀请码、扫一扫绑定的界面。
  - **绑定后**：显示两人的头像（中间有连接线或心形）、绑定天数统计、以及“解除绑定”的按钮。

- [ ] **Step 3: 编写 WXSS 样式**
  美化双人头像的展示区域和绑定天数的排版，确保界面温馨、有质感。

- [ ] **Step 4: 编写 JS 逻辑**
  模拟绑定状态的切换（可以通过 `data.isBound` 控制），处理解绑的点击事件提示。

### Task 3: 调整“共读”页面 (原书架)

**Files:**
- Modify: `pages/home/index.wxml`
- Modify: `pages/home/index.js`

- [ ] **Step 1: 增加未绑定状态的 UI**
  在 `pages/home/index.wxml` 中，根据绑定状态（如 `hasPartner`）决定显示内容。如果未绑定，显示一个引导提示：“您还未绑定伙伴，快去寻找书搭子一起共读吧！”，并提供一个跳转到“伙伴”页面的按钮。

- [ ] **Step 2: 更新 JS 逻辑**
  确保在 `onShow` 时正确读取全局或本地的绑定状态，更新视图。

### Task 4: 创建“书城”页面 (Bookstore)

**Files:**
- Create: `pages/bookstore/index.js`
- Create: `pages/bookstore/index.wxml`
- Create: `pages/bookstore/index.wxss`
- Create: `pages/bookstore/index.json`

- [ ] **Step 1: 初始化书城页面**
  创建基本的页面结构。

- [ ] **Step 2: 编写书城静态 UI**
  包含一个顶部搜索框、分类导航（如：推荐、小说、文学等）、以及一个书籍列表（封面、书名、作者、简介）。

- [ ] **Step 3: 添加样式**
  完成书城的排版，确保与整体小程序的简约风格一致。

### Task 5: 中间按钮（笔记/钢笔）交互优化

**Files:**
- Modify: `custom-tab-bar/index.js`

- [ ] **Step 1: 完善点击事件**
  当点击中间的钢笔/笔记按钮时，触发全局的记笔记或发布动态的弹窗/页面跳转。确保在所有 Tab 页下点击都能正确响应。
