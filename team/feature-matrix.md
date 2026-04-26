# 功能矩阵

## 目标
- 明确“页面 -> 前端 API -> 后端接口 -> 当前状态”的映射关系。
- 识别重复职责、未使用接口、缺口和后续重构边界。

## 全局链路

| 模块 | 前端入口 | 前端实现 | 后端接口 | 当前状态 |
| --- | --- | --- | --- | --- |
| 登录与会话恢复 | `app.js` / `utils/auth.js` | `loginFlow`、`restoreSession`、`phoneLogin` | `POST /api/v2/auth/login`、`POST /api/v2/auth/phone-login`、`POST /api/v2/auth/accept-agreement` | 支持微信一键登录和手机号登录 |
| 登录门禁 | `utils/auth-gate.js` | `requireLogin` | 依赖本地会话与鉴权接口 | 主业务页已接入，未登录回到首页登录 |
| 登录失效处理 | `app.js` / `utils/request.js` | `handleAuthExpired` | 依赖所有鉴权接口的 `401` 返回 | 可用，已补前端状态一致性脚本 |
| API 基址选择 | `app.js` | `applyApiBaseUrlConfig` | 无 | 可用 |

## 页面矩阵

| 页面 | 主要职责 | 使用的前端 API | 对应后端接口 | 当前判断 |
| --- | --- | --- | --- | --- |
| `pages/home/index` | 登录入口、首页工作台、当前共读概览、创建手动书、跳转伙伴/进度 | `fetchHome`、`createBook` | `/home`、`/books` | 初次进入必须先登录，支持微信一键登录和手机号登录 |
| `pages/partner/index` | 共读伙伴信息、绑定/解绑、共读码、共读二维码、扫码绑定 | `fetchCurrentPair`、`fetchMe`、`bindPair`、`unbindPair` | `/pairs/current`、`/users/me`、`POST /pairs`、`DELETE /pairs/current` | 结伴主页面；复制码、二维码展示、扫码解析与绑定已接入 |
| `pages/bookstore/index` | 书城列表与搜索 | `storeSearchBooks` | `/store/books` | 主链核心页；已修复分页偏移问题 |
| `pages/book-detail/index` | 书籍详情、加入共读、跳转阅读器 | `storeGetBook`、`createBook` | `/store/books/{catalog_id}`、`/books` | 主链核心页 |
| `pages/reader/index` | 分页阅读、同步阅读进度 | `storeReadPage`、`fetchHome`、`createEntry` | `/store/books/{catalog_id}/read`、`/home`、`POST /books/{book_id}/entries` | 主链核心页；同步前后会刷新上下文 |
| `pages/progress/index` | 当前书进度、动态流、未读、回复、补记 | `fetchHome`、`fetchBookEntries`、`markBookEntriesRead`、`createEntry`、`replyEntry` | `/home`、`/books/{book_id}/entries`、`/books/{book_id}/read-mark`、`/entries/{entry_id}/replies` | 主链核心页；详细进度和笔记操作已收敛到本页 |
| `pages/profile/index` | 个人资料、统计、昵称修改、阅读目标进度 | `fetchProfileMe`、`fetchProfileStats`、`fetchReadingGoal`、`updateMe` | `/users/me/profile`、`/users/me/stats`、`/users/me/reading-goal`、`/users/me` | 可用；旧 `/profile/*` 与 `/me` 路径已下线 |
| `pages/reading-history/index` | 阅读历史分页 | `fetchReadingHistory` | `/users/me/reading-history` | 可用 |
| `pages/reading-goal/index` | 阅读目标设置与周期进度 | `fetchReadingGoal`、`saveReadingGoal` | `/users/me/reading-goal` | 可用；已返回并展示目标完成度 |
| `pages/reminder/index` | 提醒配置、订阅授权入口 | `fetchReminderConfig`、`saveReminderConfig` | `/users/me/reminder-config` | 已接入模板状态和授权入口；真实投递依赖调度脚本、微信模板和真机授权 |
| `pages/settings/index` | 跳转隐私、协议、关于页 | 无 | 无 | 静态导航页 |
| `pages/privacy-policy/index` | 隐私政策 | 无 | 无 | 静态页 |
| `pages/user-agreement/index` | 用户协议 | 无 | 无 | 静态页 |
| `pages/about-us/index` | 关于我们 | 无 | 无 | 静态页 |

## 前端 API 与使用情况

| 前端 API | 后端接口 | 当前使用页面 | 当前判断 |
| --- | --- | --- | --- |
| `fetchHome` | `GET /home` | `home`、`book-detail`、`reader`、`progress` | 在用 |
| `phoneLogin` | `POST /auth/phone-login` | `home`、`profile` | 在用；需配置微信 AppID/AppSecret 才能真实换取手机号 |
| `bindPair` | `POST /pairs` | `partner` | 在用 |
| `unbindPair` | `DELETE /pairs/current` | `partner` | 在用 |
| `createBook` | `POST /books` | `home`、`book-detail` | 在用 |
| `createEntry` | `POST /books/{book_id}/entries` | `progress`、`reader` | 在用；主链关键写接口 |
| `fetchCurrentBook` | `GET /pairs/current/books/current` | 无页面直接调用 | 已暴露但当前被 `fetchHome` 替代 |
| `fetchBookEntries` | `GET /books/{book_id}/entries` | `progress` | 在用 |
| `markBookEntriesRead` | `PUT /books/{book_id}/read-mark` | `progress` | 在用 |
| `replyEntry` | `POST /entries/{entry_id}/replies` | `progress` | 在用 |
| `storeSearchBooks` | `GET /store/books` | `bookstore` | 在用 |
| `storeGetBook` | `GET /store/books/{catalog_id}` | `book-detail` | 在用 |
| `storeReadPage` | `GET /store/books/{catalog_id}/read` | `reader` | 在用 |
| `fetchCurrentPair` | `GET /pairs/current` | `partner` | 在用 |
| `fetchProfileMe` | `GET /users/me/profile` | `profile` | 在用 |
| `fetchProfileStats` | `GET /users/me/stats` | `profile` | 在用 |
| `updateMe` | `PUT /users/me` | `profile` | 在用 |
| `fetchReadingHistory` | `GET /users/me/reading-history` | `reading-history` | 在用 |
| `fetchReadingGoal` | `GET /users/me/reading-goal` | `reading-goal`、`profile` | 在用 |
| `saveReadingGoal` | `PUT /users/me/reading-goal` | `reading-goal` | 在用 |
| `fetchReminderConfig` | `GET /users/me/reminder-config` | `reminder` | 在用 |
| `saveReminderConfig` | `PUT /users/me/reminder-config` | `reminder` | 在用 |
| `fetchMe` | `GET /users/me` | `partner` | 在用 |
| `fetchStats` | `GET /users/me/stats` | 无页面直接调用 | 已暴露但当前基本闲置 |
| `fetchBooks` | `GET /books` | 无页面直接调用 | 已暴露但当前未接入页面 |

## 已识别的重复与缺口

### 重复职责
- `home` 与 `partner` 的绑定/解绑职责已收敛到 `partner`。
- `createEntry` 写进度现在主要保留在 `progress` 与 `reader`，分别对应“手动记录”和“阅读器同步”。
- 后端旧路径曾存在两组“我的”接口语义，当前已从对外路由下线。
- 新前端调用已收敛到 `/users/me` 子树。

### 明显缺口
- 提醒已有模板配置、授权入口、调度脚本和投递日志，但真实闭环仍需生产模板字段、服务器计划任务和真机授权验证。
- 阅读目标已有周期进度反馈，已接入个人页，尚未接入首页展示。
- 分享链路还不完整，目前更偏“复制码/二维码”，不是完整的小程序分享闭环。
- 小程序端已有最小状态脚本，但还不是完整 UI 自动化测试。
- 接口仍未使用严格 REST 状态码，创建与删除类操作仍返回统一 `200 + code` 包装。

## 后续重构边界建议

### 第一优先级
- 保持 `home` 聚焦“当前共读状态 + 主 CTA”。
- 将前端状态一致性脚本纳入固定回归。
- 继续补强微信订阅提醒真机投递闭环与首页目标展示。

### 第二优先级
- 前端 `services/api.js` 按领域拆分：
  - `auth`
  - `pair`
  - `reading`
  - `store`
  - `profile`
- 后端同步收敛“我的”接口命名，消除双轨语义。

### 第三优先级
- 将本矩阵持续作为页面重构与接口清理的判断依据。

## 第十五轮补充
- 测试用户入口不得出现在小程序界面；后端仅保留测试环境 `POST /auth/test-login`，数据写入正式 `users/sessions/pairs` 链路。
- `storeSearchBooks` 当前调用 `GET /store/books?query=&page=1&category=...`，书城页使用分类筛选。
- `pages/bookstore/index` 当前职责扩展为“中文分类书库 + 搜索 + 进入详情”，不再依赖默认外部英文列表。
- `pages/book-detail/index` 的加入共读按钮以后端 `has_text` 为准，防止无正文目录进入建书流程。
- 底部 tabbar 当前承担第一层登录门禁：未登录时非首页 tab 不执行 `wx.switchTab`。
