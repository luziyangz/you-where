# REST 接口落地矩阵

## 目标
- 本项目仍处于本地开发阶段，不再保留旧动作式接口兼容。
- 小程序前端统一调用更清晰的 REST 资源路径。
- 新 REST 路由必须走 `service -> repo -> models`，避免继续把业务逻辑堆在 router。

## 当前对外接口

| 能力 | 方法与路径 | 当前状态 |
| --- | --- | --- |
| 微信登录 | `POST /api/v2/auth/login` | 保留 |
| 手机号登录 | `POST /api/v2/auth/phone-login` | 保留 |
| 接受协议 | `POST /api/v2/auth/accept-agreement` | 保留 |
| 首页聚合 | `GET /api/v2/home` | 已走 service/repo |
| 当前用户 | `GET /api/v2/users/me` | 已走 REST 资源路径 |
| 更新当前用户 | `PUT /api/v2/users/me` | 已走 service/repo |
| 当前用户资料聚合 | `GET /api/v2/users/me/profile` | 已走 service/repo |
| 当前用户统计 | `GET /api/v2/users/me/stats` | 已走 service/repo |
| 阅读历史 | `GET /api/v2/users/me/reading-history` | 已走 service/repo |
| 阅读目标 | `GET /api/v2/users/me/reading-goal` | 已走 service/repo |
| 更新阅读目标 | `PUT /api/v2/users/me/reading-goal` | 已走 service/repo |
| 提醒配置 | `GET /api/v2/users/me/reminder-config` | 已走 service/repo |
| 更新提醒配置 | `PUT /api/v2/users/me/reminder-config` | 已走 service/repo |
| 当前配对 | `GET /api/v2/pairs/current` | 已走 service/repo |
| 创建配对 | `POST /api/v2/pairs` | 已走 service/repo |
| 解除当前配对 | `DELETE /api/v2/pairs/current` | 已走 service/repo |
| 书城列表 | `GET /api/v2/store/books` | 已走 store service/repo |
| 书城详情 | `GET /api/v2/store/books/{catalog_id}` | 已走 store service/repo |
| 书城阅读页 | `GET /api/v2/store/books/{catalog_id}/read` | 已走 store service/repo |
| 共读书列表 | `GET /api/v2/books` | 已走 service/repo |
| 创建共读书 | `POST /api/v2/books` | 已走 service/repo |
| 当前配对在读书 | `GET /api/v2/pairs/current/books/current` | 已走 service/repo |
| 阅读笔记列表 | `GET /api/v2/books/{book_id}/entries` | 已走 service/repo |
| 创建阅读笔记 | `POST /api/v2/books/{book_id}/entries` | 已走 service/repo |
| 更新已读标记 | `PUT /api/v2/books/{book_id}/read-mark` | 已走 service/repo |
| 回复笔记 | `POST /api/v2/entries/{entry_id}/replies` | 已走 service/repo |

## 已下线旧入口

| 旧路径 | 替代路径 |
| --- | --- |
| `GET /api/v2/me` | `GET /api/v2/users/me` |
| `PUT /api/v2/me` | `PUT /api/v2/users/me` |
| `GET /api/v2/profile/me` | `GET /api/v2/users/me/profile` |
| `GET /api/v2/profile/stats` | `GET /api/v2/users/me/stats` |
| `GET /api/v2/profile/history` | `GET /api/v2/users/me/reading-history` |
| `GET /api/v2/profile/goals` | `GET /api/v2/users/me/reading-goal` |
| `PUT /api/v2/profile/goals` | `PUT /api/v2/users/me/reading-goal` |
| `GET /api/v2/profile/reminders` | `GET /api/v2/users/me/reminder-config` |
| `PUT /api/v2/profile/reminders` | `PUT /api/v2/users/me/reminder-config` |
| `GET /api/v2/pair/current` | `GET /api/v2/pairs/current` |
| `POST /api/v2/pair/bind` | `POST /api/v2/pairs` |
| `POST /api/v2/pair/unbind` | `DELETE /api/v2/pairs/current` |
| `GET /api/v2/books/current` | `GET /api/v2/pairs/current/books/current` |
| `POST /api/v2/entries` | `POST /api/v2/books/{book_id}/entries` |
| `POST /api/v2/books/{book_id}/entries/read` | `PUT /api/v2/books/{book_id}/read-mark` |

## 分层落地
- Router：`backend/api/v2/rest_aliases.py` 只做参数接收、鉴权依赖、响应包装。
- Service：`backend/service/reading_service.py` 承担业务规则、状态流转、并发锁和错误码。
- Repo：`backend/repo/reading_repo.py` 承担 SQLAlchemy 查询与数据访问。
- Store Router：`backend/api/v2/store_reading.py` 只保留书城列表、详情、阅读页入口。
- Store Service：`backend/service/store_service.py` 承担内置书种子、Gutendex 外部依赖、熔断、详情评价和阅读分页。
- Store Repo：`backend/repo/store_repo.py` 承担书城目录和正文的数据访问。
- Model：`backend/common/models.py` 继续作为数据库模型定义。

## 前端落地
- `services/api.js` 保持统一导出，页面引用不变。
- 内部已拆分为：
  - `services/api/auth.js`
  - `services/api/pair.js`
  - `services/api/profile.js`
  - `services/api/reading.js`
  - `services/api/store.js`
  - `services/api/base.js`
- 前端所有新调用均已切到当前对外接口。

## 未完成项
- 登录类接口仍是动作语义，这是合理例外，后续可单独评估 OAuth 风格命名。
- HTTP 状态码仍沿用统一 `200 + code` 响应，尚未切换为 `201 Created`、`204 No Content` 等严格 REST 状态码。
- 书城已完成 service/repo 拆分。
- 本地测试登录 `POST /api/v2/auth/test-login` 属于后端测试环境辅助接口，不在小程序界面展示；MySQL/生产默认关闭，需 `ENABLE_TEST_USERS=1` 显式启用。
- 书城分类查询已通过 `GET /api/v2/store/books?category=...` 落地，仍保持资源集合查询语义。

## 验证
- 新 REST 路由主链回归：`25 passed`。
- 书城专项回归：`8 passed`。
- 已新增旧入口下线测试，确认旧动作式路径返回 `404`。
- 前端状态脚本：`frontend state check ok`。
