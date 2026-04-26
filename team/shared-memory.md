# Shared Memory

## 项目事实
- 项目类型：原生微信小程序 + Python FastAPI 后端
- 小程序主入口：`app.js`、`app.json`
- 后端主入口：`backend/app_main.py`
- 当前后端主 API 版本：`/api/v2`
- 当前数据层：SQLAlchemy；配置显示默认支持 MySQL，也兼容 SQLite 本地模式

## 当前业务主线
- 登录
- 绑定共读伙伴
- 创建共读书籍
- 记录阅读进度 / 笔记
- 查看进度与回复
- 查看个人信息、阅读历史、阅读目标、提醒配置
- 书城搜索、详情、分页阅读

## 已识别的结构问题
- `backend/service`、`backend/repo` 目录存在但尚未承接真实业务逻辑
- 部分中文文档与注释存在编码混乱
- 存在疑似模板残留页面：`pages/index`、`pages/logs`
- 存在历史归档目录：`archive/2026-03-26`
- 仓库中有疑似不应保留在主仓库根主线内的二进制文件：`backend/docker-compose-linux-x86_64`

## 当前治理策略
- 第一阶段只做“低风险、可验证”的治理：
  - 建立协作机制
  - 清理明显无引用残留
  - 建立计划与记录制度
  - 运行现有后端测试验证主链路
- 第二阶段再进入结构重构与能力增强：
  - 前后端契约梳理
  - 分层重整
  - 稳定性与并发治理
  - 自动化测试补强

## 团队协作约束
- 一切改动以不破坏主链路为前提
- 先计划后实施
- 每轮结束必须同步 `record.md`、`待办.md`、`已办.md`

## 2026-04-26 首轮结果
- 已完成治理骨架搭建
- 已清理模板残留页面 `pages/index`、`pages/logs`
- 已删除历史二进制噪音文件 `backend/docker-compose-linux-x86_64`
- 已修复前端自定义 Tab 选中态错误
- 后端回归测试通过：`9 passed`

## 2026-04-26 第二轮结果
- 已修复书城分页偏移问题
- 已修复个人统计对 `unbound` 历史关系的口径问题
- 已新增主链负向/边界测试
- 已修复 `backend/test_v2_store_reading.py` 的测试数据污染问题
- 第二轮后端回归通过：`13 passed`

## 编码结论
- 当前仓库主文本文件内容本身大多是正常 `UTF-8`。
- 之前看到的大部分中文乱码，根因是 Windows PowerShell 默认读取方式把 UTF-8 当成本地编码解释。
- 后续在终端读取文本文件时，统一使用 `Get-Content -Encoding utf8`。
- 项目已新增 `.editorconfig`，把文本编码约束固定为 `UTF-8`。

## 2026-04-26 第三轮结果
- 已新增 `team/feature-matrix.md`
- 已明确页面与接口的映射关系、重复职责与缺口
- 已为 `create_entry` 增加并发幂等冲突兜底
- 已新增并发重放测试，验证相同 `client_request_id` 只生成 1 条记录
- 第三轮后端回归通过：`14 passed`

## 2026-04-26 第四轮结果
- 已为 `pair_bind` 增加并发防重兜底
- 已为 `create_book` 增加并发防重兜底
- 已新增绑定并发与建书并发测试
- 第四轮后端回归通过：`16 passed`

## 2026-04-26 第五轮结果
- 已建立统一的 `app.globalData` 写入口
- `home / partner / progress` 的职责边界已开始收敛
- `home` 不再承担绑定和详细笔记写入
- `progress` 成为详细进度与笔记操作页
- `partner` 改为页面回流时主动刷新数据
- 前端关键 JS 装载检查通过

## 2026-04-26 第六轮结果
- `book-detail` 与 `reader` 已接入上下文同步
- 加书前与同步进度前后的状态回流已收口一轮
- 前端扩展装载检查通过

## 2026-04-26 第七轮结果
- `syncReadingContext` 已支持从 `pair.current_book` 自动回写全局当前书籍
- `partner` 页已经接入统一状态入口，不再遗漏当前共读书回写
- 已确认这是 `app.globalData` 状态分散写入导致的重复性问题，并已记入错误记录
- 针对性状态校验脚本通过，后端回归继续保持 `16 passed`

## 2026-04-26 第八轮结果
- 已新增 `active_pair_locks` 和 `active_book_locks`，将活跃配对和当前在读书的并发约束推进到数据库层。
- 绑定、解绑、建书、双方完读归档链路已接入锁表创建与释放。
- 已新增 `scripts/check_frontend_state.js`，用于固定验证前端全局状态同步和关键页面装载。
- Gutendex 外部依赖已增加失败计数与轻量熔断，失败时继续降级使用本地缓存。
- 阅读目标已返回并展示周期完成度。
- 提醒功能已明确当前为配置保存状态，微信订阅消息投递仍需要后续接入模板、授权和调度。
- 第八轮验证：前端状态脚本通过，后端回归 `18 passed`。

## 2026-04-26 第九轮结果
- 首页和我的页已支持微信一键登录与手机号登录。
- 后端新增 `/auth/phone-login`，手机号登录走微信 `getuserphonenumber`，本地保留 debug 手机号路径。
- 正式环境微信登录必须配置 `WECHAT_APP_ID / WECHAT_APP_SECRET`，不再用临时 hash 冒充 openid。
- 主业务页已接入 `utils/auth-gate.js` 登录门禁，未登录回到首页。
- 结伴页未绑定和已绑定状态均展示自己的共读码和二维码。
- 扫码绑定支持解析纯数字、URL/scheme、路径、JSON 等格式，并拦截自绑。
- 第九轮验证：前端状态脚本通过，后端回归 `19 passed`。

## 2026-04-26 第十轮结果
- 结伴页二维码已从外部图片服务改为小程序本地 canvas 生成。
- 新增 `utils/qrcode.js`，生成绑定协议 QR 矩阵。
- 结伴页支持二维码预览和保存到相册。
- 第一版 QR 校验码不可解码的问题已暴露并修复，根因是 Reed-Solomon 校验码生成错误。
- 已用 OpenCV 解码验证本地二维码可还原 `youzainaye://pair/bind?join_code=123456`。
- 第十轮验证：前端状态脚本通过，后端回归 `19 passed`。

## 2026-04-26 第十一轮结果
- 个人页已接入阅读目标进度，展示完成书籍和打卡天数进度条。
- 提醒接口已返回 `delivery_status`、`delivery_message`、`template_id`。
- 提醒页保存前会在有模板 ID 时调用 `wx.requestSubscribeMessage`。
- 新增 `reminder_delivery_logs`，按用户和本地日期记录投递结果，避免同日重复推送。
- 新增 `backend/scripts/dispatch_reminders.py`，可由 cron/计划任务周期执行微信订阅消息投递。
- 已明确真实投递仍依赖微信后台模板字段、真机订阅授权和服务器调度，不能在本地伪造完成。
- 第十一轮验证：前端状态脚本通过，后端回归 `20 passed`，调度脚本缺省环境变量安全跳过。

## 2026-04-26 第十二轮结果
- 已新增 `backend/api/v2/rest_aliases.py`，在不删除旧接口的情况下提供 REST 友好兼容路径。
- 当前用户资源已收敛到 `/users/me` 子树，包括资料、统计、阅读历史、阅读目标和提醒配置。
- 当前配对资源已新增 `/pairs/current`、`POST /pairs`、`DELETE /pairs/current`。
- 阅读笔记创建已新增 `POST /books/{book_id}/entries`，已读标记新增 `PUT /books/{book_id}/read-mark`。
- 前端 `services/api.js` 已拆为领域模块，页面引用仍保持 `require('../../services/api')` 不变。
- 已新增 `team/api-rest-migration.md`，作为后续接口新增和旧接口废弃判断依据。
- 第十二轮验证：前端模块装载通过，前端状态脚本通过，后端回归 `23 passed`。
- 仍未完成严格 REST 状态码迁移，当前继续沿用统一 `200 + code` 响应包装。

## 2026-04-26 第十三轮结果
- 项目仍在本地开发阶段，已按用户要求取消旧接口兼容策略，直接下线旧动作式路径。
- 新增 `backend/repo/reading_repo.py`，承接用户、配对、书籍、笔记、目标、提醒相关数据访问。
- 新增 `backend/service/reading_service.py`，承接主链业务规则、并发锁、状态流转和错误码。
- `backend/api/v2/rest_aliases.py` 已改为真正调用 service/repo，不再包装旧 router 函数。
- `backend/api/v2/router.py` 不再挂载 `profile/history/goals/reminders` 旧路由。
- `core_reading.py` 对外只保留 auth 类路由；`store_reading.py` 对外只保留书城读取路由。
- 已新增旧入口 404 测试，确认 `/me`、`/profile/*`、`/pair/*`、`/entries`、`/books/current` 等旧路径不再注册。
- 第十三轮验证：前端状态脚本通过，后端回归 `24 passed`。

## 2026-04-26 第十四轮结果
- 已新增 `backend/repo/store_repo.py`，书城目录和正文查询下沉到 repo 层。
- 已新增 `backend/service/store_service.py`，书城内置种子、Gutendex、熔断、详情评价和阅读分页下沉到 service 层。
- `backend/api/v2/store_reading.py` 已瘦身为列表、详情、阅读页 3 个 router 入口。
- `backend/scripts/seed_store_books.py` 已改为调用 `store_service.seed_default_store_books`。
- 前端状态脚本新增 REST 路径断言，确认前端 API 继续使用新路径。
- 新增 `team/user-flow-check.md`，完成正常使用小程序时的功能与页面流转检查。
- 第十四轮验证：前端状态脚本通过，书城专项回归 `8 passed`，后端全量回归 `24 passed`。
- 产品/测试结论：本地开发环境下 MVP 主链功能与页面流转基本完整；正式上线仍需真机授权、订阅消息真实投递、生产调度、MySQL 实例验证和压测。

## 2026-04-26 第十五轮结果
- 未登录底部导航闪屏根因是自定义 tabbar 先切页、页面再做登录门禁；现已前置到 `custom-tab-bar/index.js` 拦截。
- 书城默认数据源已切换为本地中文分类书库；Gutendex 外部同步默认关闭，仅在显式设置 `STORE_ENABLE_NETWORK=1` 时启用。
- `/store/books` 当前支持 `category` 参数，前端 `storeSearchBooks(query, page, category)` 已同步。
- 本地中文书库覆盖分类：国外名著、历史、心学、玄学术数、中医经络、国学经典。
- `book-detail` 的 `has_text` 以后端是否存在 `CatalogContent` 为准，避免无正文目录进入“加入共读”主链。
- 测试用户 A/B 不允许出现在小程序界面；前端测试入口已删除。
- 后端测试用户入口为 `POST /api/v2/auth/test-login`，仅在 `ENABLE_TEST_USERS=1` 或 SQLite 测试环境下启用。
- 测试用户会和真实用户一样写入 `users`、`sessions`，绑定后进入正式 `pairs` 链路；不再自动跳过协议确认状态。
- 第十五轮验证：前端状态脚本通过，书城专项回归 `8 passed`，后端全量回归 `25 passed`。

## 2026-04-26 第十七轮结果
- 后端 Docker 化部署已补齐：Dockerfile、Docker Compose、Nginx、容器 entrypoint、云端部署脚本和本地同步脚本。
- 当前阿里云联调入口规划为 `http://47.99.240.126:18080/api/v2`，健康检查为 `http://47.99.240.126:18080/health`。
- `www.nizaina.com` 未备案，不能作为当前正式访问入口；SSL 证书也不能直接解决 IP HTTPS 的证书域名不匹配问题。
- 云端脚本会配置 Docker 国内镜像源，并在首次部署时自动生成 MySQL 密码和 `.env`。
- 本轮未实际同步服务器，原因是尚未提供 SSH 用户、密码或密钥。
- 第十七轮验证：PowerShell 脚本语法通过，Compose YAML 解析通过，部署包内容检查通过，前端状态脚本通过，后端全量回归 `26 passed`。

## 2026-04-26 第十八轮结果
- 测试账号 A/B 固定共读码为 `900001` / `900002`，仅作为后端测试环境辅助能力，不在小程序界面展示。
- 结伴页二维码显示异常根因是 canvas CSS 使用 `rpx`，绘制坐标使用固定数值，导致显示尺寸与绘制尺寸不一致。
- 已将二维码 canvas 显示和绘制统一为 `128px`，预览/保存导出为 `512x512`。
- 共读码卡片已删除文字“复制”，只保留右上角复制图标。
- 第十八轮验证：前端状态脚本通过，后端全量回归 `26 passed`。

## 2026-04-26 第十九轮结果
- 云端真实用户输入 `900002` 返回“未找到对应用户”的根因是 MySQL 中没有隐藏测试用户 B。
- 已新增 `backend/scripts/seed_test_users.py`，用于把测试用户 A/B 显式写入真实 `users` 表。
- 测试用户固定共读码仍为 `900001` / `900002`。
- 云端开发可执行 `docker compose exec backend python scripts/seed_test_users.py --reset-active-pairs` 后再进行绑定测试。
- 新增 `SEED_TEST_USERS=1` 可选开关，但默认仍为 `0`，避免生产环境无意自动种子测试用户。
- 第十九轮验证：后端全量回归 `27 passed`，前端状态脚本通过。

## 下一轮优先级
- 获取 SSH 凭据并实际同步部署到 `47.99.240.126`
- 阿里云安全组放行 `18080/tcp` 并验证 `/health`
- 微信订阅消息真机授权与真实投递验证
- MySQL 实例级集成测试与并发压测
- 确认微信后台订阅模板字段并同步调度脚本
- 严格 HTTP 状态码规划
