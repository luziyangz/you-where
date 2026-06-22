# 对话记录

## 记录规则
- 仅记录与项目推进直接相关的关键对话、决策、风险、阻塞和结论。
- 每轮计划结束后必须更新本文件，并同步更新 `待办.md` 与 `已办.md`。
- 如果同一问题重复出现 3 次及以上，必须同步登记到 `team/error-log.md`。

## 2026-04-26
- 用户要求接手并治理一个结构混乱的原生微信小程序项目，范围覆盖前端小程序与 Python 后端。
- 用户要求建立团队式协作机制，包括 `Agent.md`、产品/开发/测试三个子角色、共享 memory、hooks、规则、错误记录以及对话/待办/已办三类持续记录。
- 当前首轮目标确定为：
  1. 盘点项目结构与主流程。
  2. 建立协作规范与共享记忆文件。
  3. 制定并落地第一轮精简方案。
  4. 在不破坏主链路的前提下做首轮清理与验证。
- 当前已确认的仓库现状：
  1. 根目录为原生微信小程序主体，`backend` 为 FastAPI 后端。
  2. `backend/service` 与 `backend/repo` 目前几乎为空壳，存在“约定分层”和“实际实现”脱节问题。
  3. `pages/index` 与 `pages/logs` 不在 `app.json` 注册页中，疑似模板残留。
  4. 仓库内部分中文文档和源码注释存在编码显示混乱问题，需要纳入治理。
- 当前首轮风险结论：
  1. 现在可以先做文档治理与明显无引用残留清理。
  2. 大范围后端重构暂不应立即进行，需先补充结构基线和验证手段。
- 本轮已执行动作：
  1. 新建 `Agent.md`、`team/shared-memory.md`、`team/hooks.md`、`team/error-log.md`、`team/current-plan.md` 以及三个角色规则文件。
  2. 重写 `record.md`、`待办.md`、`已办.md`，建立持续更新机制。
  3. 删除明确无引用的模板残留页面：`pages/index`、`pages/logs`。
  4. 删除未被仓库主流程引用的历史二进制文件：`backend/docker-compose-linux-x86_64`。
  5. 修复前端自定义 Tab 选中态错误：
     - `pages/home/index.js` 从 `selected: 0` 改为 `selected: 1`
     - `pages/profile/index.js` 从 `selected: 1` 改为 `selected: 3`
  6. 执行后端回归测试：`pytest test_v2_core_reading.py test_v2_store_reading.py test_v2_e2e_flow.py test_v2_profile.py -q`，结果 `9 passed`。
- 产品角色结论摘要：
  1. 当前产品主闭环已形成：登录 -> 绑定伙伴 -> 选书/建书 -> 记录进度/笔记 -> 回复互动 -> 完成归档。
  2. 首页、结伴页、进度页职责存在重叠，提醒功能目前只有配置没有闭环。
  3. 邀请分享、新手引导、完读仪式感、异常恢复策略仍然缺失。
- 开发角色结论摘要：
  1. 后端真实业务集中在 router，`service/repo` 为空壳，README 与实现不一致。
  2. 并发、外部依赖、编码、迁移体系、状态管理都有明显技术债。
  3. 首轮应先稳住结构边界与编码治理，再进入大重构。
- 测试角色结论摘要：
  1. 当前只有后端 happy path 自动化测试，没有小程序端测试。
  2. 高风险区域是“登录/绑定/建书/进度/回复”这条双人共读主链。
  3. 需要补充负向、并发、MySQL 集成、真机和弱网测试。

## 2026-04-26 第二轮
- 本轮目标：补强后端主链负向/边界测试，并修复已经确认的真实问题。
- 本轮完成的代码改进：
  1. 修复 `backend/api/v2/store_reading.py` 的书城分页逻辑，`/api/v2/store/books?page=N` 现在会正确使用 `offset + limit`，不再重复返回第一页数据。
  2. 修复 `backend/api/v2/profile.py` 的个人统计口径，已解绑(`unbound`)关系下的历史完读统计仍会保留，阅读页数统计也不再错误归零。
- 本轮新增的自动化测试：
  1. `backend/test_v2_core_reading.py`
     - 新增自绑拦截、无效共读码拦截测试。
  2. `backend/test_v2_store_reading.py`
     - 新增书城分页偏移测试。
     - 新增未解锁笔记不可回复测试。
     - 修复测试夹具未清理 `Book/Entry` 导致跨用例串数据的问题。
  3. `backend/test_v2_profile.py`
     - 新增已解绑关系下个人统计仍保留历史数据的测试。
- 本轮暴露并解决的问题：
  1. 新增“锁定笔记不可回复”测试时，发现 `test_v2_store_reading.py` 的 fixture 没有清理 `Book/Entry`，导致函数级测试相互污染。
  2. 已通过补充清理逻辑解决，测试基线恢复可信。
- 本轮验证结果：
  - 执行 `pytest test_v2_core_reading.py test_v2_store_reading.py test_v2_e2e_flow.py test_v2_profile.py -q`
  - 结果：`13 passed`

## 2026-04-26 第三轮
- 本轮目标：先建立编码治理基线，再沉淀页面/API 功能矩阵，并补一项真正的并发一致性兜底。
- 本轮完成的工程治理：
  1. 新增 `.editorconfig`，统一约束项目文本文件使用 `UTF-8`。
  2. 更新 `README.md`，明确 Windows PowerShell 读取 UTF-8 文件时应使用 `Get-Content -Encoding utf8`。
  3. 确认当前仓库多数中文乱码属于“终端读取方式问题”，不是源码内容本身损坏。
- 本轮新增文档：
  1. `team/feature-matrix.md`
     - 完成“页面 -> 前端 API -> 后端接口 -> 当前状态”的功能矩阵。
     - 明确了 `home` / `partner` 绑定职责重复、`/me` 与 `/profile/me` 双轨、提醒仅有配置无闭环等问题。
- 本轮完成的后端一致性增强：
  1. `backend/api/v2/store_reading.py`
     - 为 `create_entry` 增加 `IntegrityError` 兜底。
     - 在并发重放相同 `client_request_id` 时，若命中数据库唯一约束，接口会回退为幂等成功响应，而不是直接抛 500。
- 本轮新增自动化测试：
  1. `backend/test_v2_store_reading.py`
     - 新增 `test_create_entry_is_idempotent_under_concurrent_replay`
     - 使用并发请求验证相同 `client_request_id` 只会生成 1 条记录
- 本轮验证结果：
  - 执行 `pytest test_v2_store_reading.py -q`，结果 `5 passed`
  - 执行 `pytest test_v2_core_reading.py test_v2_store_reading.py test_v2_e2e_flow.py test_v2_profile.py -q`
  - 结果：`14 passed`
- 本轮未完成但已明确的后续项：
  1. 继续补绑定与建书的并发场景测试。
  2. 继续推进前端状态一致性治理。

## 2026-04-26 第四轮
- 本轮目标：继续按顺序补“绑定并发”和“建书并发”的测试与兜底，不跳步。
- 本轮完成的实现：
  1. 新增 `backend/common/locks.py`
     - 提供命名锁能力，用于同进程内按业务键串行化高风险写操作。
  2. `backend/api/v2/core_reading.py`
     - 为 `pair_bind` 增加基于用户 ID 的命名锁。
     - 在锁内对两侧用户执行 `with_for_update()` 行锁复查。
     - 并发绑定时保证“只有一个请求成功创建关系，其他请求回到业务错误而不是重复创建”。
  3. `backend/api/v2/store_reading.py`
     - 为 `create_book` 增加基于 `pair_id` 的命名锁。
     - 在锁内对当前 `Pair` 执行 `with_for_update()` 行锁复查。
     - 并发建书时保证“同一对伙伴同时只能成功创建一本在读书”。
- 本轮新增自动化测试：
  1. `backend/test_v2_core_reading.py`
     - 新增 `test_pair_bind_allows_only_one_success_under_concurrency`
  2. `backend/test_v2_store_reading.py`
     - 新增 `test_create_book_allows_only_one_success_under_concurrency`
- 本轮验证结果：
  - 执行 `pytest test_v2_core_reading.py -q`，结果 `4 passed`
  - 执行 `pytest test_v2_store_reading.py -q`，结果 `6 passed`
  - 执行 `pytest test_v2_core_reading.py test_v2_store_reading.py test_v2_e2e_flow.py test_v2_profile.py -q`
  - 结果：`16 passed`
- 本轮结论：
  1. 双人共读主链里最核心的三类写并发风险已补到：
     - 绑定并发
     - 建书并发
     - 记进度幂等并发
  2. 当前实现采用“进程内命名锁 + MySQL 行锁复查”的双层兜底。
  3. 本地 sqlite 测试环境主要依赖命名锁；生产 MySQL 环境同时具备数据库行锁兜底。

## 2026-04-26 第五轮
- 本轮目标：解决剩余状态一致性问题，并开始收敛 `home / partner / progress` 的职责边界。
- 本轮完成的状态一致性治理：
  1. `app.js`
     - 新增 `syncUser`、`syncPair`、`syncCurrentBook`、`syncReadingContext`
     - 统一全局状态写入口，避免页面继续直接散写 `app.globalData`
  2. `pages/partner/index.js`
     - 页面切回时改为在 `onShow` 主动刷新关系数据
     - 增加未登录场景下的本地状态清空
     - 改为使用 `fetchMe + fetchCurrentPair`，避免只依赖陈旧的 `app.globalData.user`
  3. `pages/profile/index.js`
     - 改为通过 `app.syncReadingContext / app.syncUser` 写入全局状态
  4. `pages/progress/index.js`
     - 改为优先通过 `fetchHome` 获取最新 `user / pair / currentBook`
     - 不再只依赖 `app.globalData` 中可能过期的用户与伙伴信息
     - 支持 `open_composer=1` 参数，用于从首页跳转后直接打开记录弹窗
- 本轮完成的职责收敛：
  1. `pages/home/index.js`
     - 删除首页中的绑定逻辑和解绑逻辑
     - 删除首页中的“写笔记/记一笔”弹窗和写入逻辑
     - 首页现在只保留：
       - 登录入口
       - 去伙伴页
       - 创建书籍
       - 查看进度
  2. `pages/home/index.wxml`
     - 把原先依赖占位字段的“笔记预览区”替换为稳定的动作入口
     - 把伙伴管理收敛到伙伴页
  3. `pages/progress/index.js`
     - 成为笔记流、回复、写入和更新进度的唯一详细操作页
- 本轮解决的问题：
  1. 在调整 `partner` 页刷新时，暴露出 `loadPairData -> onShow -> loadPairData` 的递归风险
  2. 已通过拆出 `updateNavigationState()` 修复，没有逃避，也没有保留隐患
- 本轮验证结果：
  - 执行后端回归：`pytest test_v2_core_reading.py test_v2_store_reading.py test_v2_e2e_flow.py test_v2_profile.py -q`
  - 结果：`16 passed`
  - 执行前端 JS 装载检查：`app.js`、`pages/home/index.js`、`pages/partner/index.js`、`pages/progress/index.js`、`pages/profile/index.js`
  - 结果：`ok`

## 2026-04-26 第六轮
- 本轮目标：继续解决 `book-detail / reader` 与首页、进度页之间的状态回流问题。
- 本轮完成的修改：
  1. `pages/book-detail/index.js`
     - 新增 `syncHomeContext()`
     - 页面展示时会同步最新 `user / pair / currentBook`
     - 点击“加入共读”前会再次刷新上下文，避免用旧状态直接发起创建
     - 若未绑定伙伴，会直接引导去伙伴页，而不是等后端返回失败
     - 若当前已有正在共读的书，会直接引导去进度页，而不是重复创建
  2. `pages/reader/index.js`
     - 新增 `syncHomeContext()`
     - 同步进度前后都会刷新 `user / pair / currentBook`
     - 同步成功后会把最新 `currentBook` 回写全局，减少返回其他页面后的脏读
- 本轮验证结果：
  - 前端 JS 装载检查：`app.js`、`pages/home/index.js`、`pages/partner/index.js`、`pages/progress/index.js`、`pages/profile/index.js`、`pages/book-detail/index.js`、`pages/reader/index.js`
  - 结果：`ok`
  - 后端回归：`pytest test_v2_core_reading.py test_v2_store_reading.py test_v2_e2e_flow.py test_v2_profile.py -q`
  - 结果：`16 passed`

## 2026-04-26 第七轮
- 本轮目标：继续收口 `app.globalData` 状态一致性，解决伙伴页遗漏 `current_book` 回写的问题。
- 本轮完成的修改：
  1. `app.js`
     - 增强 `syncReadingContext`
     - 当调用方只传 `pair` 且 `pair` 内含 `current_book` 时，会自动同步到 `globalData.currentBook`
     - 当 `pair` 为空时，会同步清空 `globalData.currentBook`
  2. `pages/partner/index.js`
     - `loadPairData()` 改为统一走 `app.syncReadingContext({ user, pair })`
     - 不再出现“伙伴页已经拿到当前共读书，但全局状态仍为空”的漏写
     - `updateNavigationState()` 补充同步 `hasBook`
- 本轮暴露并解决的问题：
  1. 伙伴页虽然调用了 `/pair/current`，但此前只把 `pair` 写回全局，没有把 `pair.current_book` 一并回写，导致：
     - 重启后如果先从伙伴页进入，`app.globalData.currentBook` 可能长期为空
     - 依赖全局状态判断的页面会出现“明明有在读书，UI 却按无书处理”的错态
  2. 前端验证脚本首次执行时，暴露出本机 `node -` 默认按 ESM 解释、且 CommonJS 下无顶层 `await` 的执行环境差异。
     - 已改用 `node --input-type=commonjs` + 异步 IIFE 解决
     - 该问题属于本地验证脚本环境问题，不是业务代码缺陷
- 本轮验证结果：
  - 执行针对性状态验证脚本：结果 `ok`
  - 执行前端关键 JS 装载检查：结果 `ok`
  - 执行后端回归：`pytest test_v2_core_reading.py test_v2_store_reading.py test_v2_e2e_flow.py test_v2_profile.py -q`
  - 结果：`16 passed`

## 2026-04-26 第八轮
- 本轮目标：尽最大可能解决当前已确认的真实问题，包括前端状态测试、多实例并发兜底、书城外部依赖、目标反馈和提醒定位。
- 本轮完成的后端稳定性增强：
  1. 新增 `active_pair_locks`
     - 用 `user_id` 主键约束同一用户只能存在一个活跃配对锁。
     - `pair_bind` 成功时写入两侧用户锁。
     - `pair_unbind` 时释放配对锁。
  2. 新增 `active_book_locks`
     - 用 `pair_id` 主键约束同一配对只能存在一本当前在读书。
     - `create_book` 成功时写入在读书锁。
     - 双方完读归档或解绑时释放在读书锁。
  3. 书城 Gutendex 外部依赖新增轻量熔断：
     - 连续失败后短时间内跳过外部请求。
     - 保持本地缓存降级可用，并返回 `network_error / network_skipped` 状态。
- 本轮完成的前端与产品改进：
  1. 新增 `scripts/check_frontend_state.js`
     - 固化 `pair.current_book -> app.globalData.currentBook` 的状态一致性验证。
     - 同时装载关键页面 JS，降低语法和依赖漏改风险。
  2. 阅读目标接口与页面增强：
     - `/profile/goals` 返回周期完成度。
     - `pages/reading-goal` 展示完成书籍和打卡天数进度。
  3. 提醒接口与页面增强：
     - `/profile/reminders` 返回 `delivery_status` 和 `delivery_message`。
     - `pages/reminder` 明确展示当前为配置保存状态，真实微信订阅消息投递尚未接入。
- 本轮同步的文档：
  1. 更新 `team/feature-matrix.md`，同步最新页面职责和接口使用关系。
  2. 更新 `README.md`，新增后端回归和前端状态脚本命令。
  3. 更新 `待办.md` 与 `已办.md`，区分已解决项和仍需后续交付的订阅消息/首页目标展示。
- 本轮验证结果：
  - 前端状态一致性脚本：`node scripts/check_frontend_state.js`，结果 `frontend state check ok`
  - 后端回归：`pytest test_v2_core_reading.py test_v2_store_reading.py test_v2_e2e_flow.py test_v2_profile.py -q`
  - 结果：`18 passed`
- 本轮仍未完全解决的问题：
  1. 微信订阅消息投递闭环需要模板 ID、订阅授权、调度任务和发送凭证，本轮只能完成配置状态透明化，不能伪造真实投递。
  2. `service/repo` 分层仍未落地，后续需要按业务域逐步拆分，不能一次性大拆。
  3. 仍缺少真机、弱网、MySQL 实例级集成测试和压测结果。

## 2026-04-26 第九轮
- 本轮目标：优化功能体验，完成“初次进入必须登录”与“结伴页共读码/二维码/扫码绑定完善”。
- 本轮完成的登录能力：
  1. 后端新增 `POST /api/v2/auth/phone-login`
     - 支持通过微信手机号授权 `code` 换取手机号并登录。
     - 支持本地调试 `debug_phone_number`。
     - 用户模型新增 `phone_number` 字段。
  2. 后端微信登录修正：
     - 真实环境不再用临时 hash 冒充 openid。
     - 未配置 `WECHAT_APP_ID / WECHAT_APP_SECRET` 时会明确报错。
     - 开发者工具或本地 API 地址仍支持 `debug_open_id`。
  3. 前端新增手机号登录：
     - 首页和我的页均支持微信一键登录与手机号登录。
     - 手机号登录使用 `open-type="getPhoneNumber"`。
  4. 新增登录门禁：
     - `utils/auth-gate.js`
     - 书城、结伴、书籍详情、阅读器、进度、阅读历史、目标、提醒、设置等主业务页未登录时回到首页登录。
- 本轮完成的结伴页增强：
  1. 未绑定和已绑定状态均展示自己的共读码。
  2. 共读码支持一键复制。
  3. 共读二维码继续使用统一协议：`youzainaye://pair/bind?join_code=xxxxxx`。
  4. 扫一扫绑定会解析纯数字、URL/scheme、路径、JSON 等多种格式，并拦截自绑。
- 本轮新增验证：
  1. 后端新增手机号登录测试。
  2. 前端状态脚本新增微信登录、手机号登录、二维码协议解析、复制共读码断言。
- 本轮验证结果：
  - 前端状态脚本：`node scripts/check_frontend_state.js`，结果 `frontend state check ok`
  - 后端回归：`pytest test_v2_core_reading.py test_v2_store_reading.py test_v2_e2e_flow.py test_v2_profile.py -q`
  - 结果：`19 passed`
- 仍需后续真机确认：
  1. 手机号登录必须在微信真机或正式开发者工具中验证 `getPhoneNumber` 授权弹窗。
  2. 二维码图片依赖外部二维码服务，正式上线需确认微信后台 downloadFile/image 合法域名配置，或改为本地/后端生成二维码。

## 2026-04-26 第十轮
- 本轮目标：将结伴页二维码从外部服务改为后端/本地生成，优先采用小程序本地 canvas 生成，减少外部依赖和域名配置风险。
- 本轮完成的修改：
  1. 新增 `utils/qrcode.js`
     - 本地生成 QR Code Version 4-L 矩阵。
     - 支持当前绑定协议：`youzainaye://pair/bind?join_code=xxxxxx`。
  2. `pages/partner/index.js`
     - 改为调用 `createQrMatrix()` 生成二维码矩阵。
     - 使用 `wx.createCanvasContext` 在本地 canvas 绘制二维码。
     - 新增二维码预览与保存到相册逻辑。
     - 不再生成 `api.qrserver.com` 外部图片 URL。
  3. `pages/partner/index.wxml`
     - 将二维码 `<image>` 替换为 `<canvas>`。
     - 增加“预览 / 保存”操作。
  4. `scripts/check_frontend_state.js`
     - 增加 canvas stub。
     - 增加 QR 矩阵长度、结伴页二维码状态验证。
- 本轮暴露并修复的问题：
  1. 第一版 QR 生成器能画出图形，但 OpenCV 无法解码。
  2. 定位为 Reed-Solomon 校验码生成错误。
  3. 已修正校验多项式算法，并用 OpenCV 成功解码出原始绑定协议。
- 本轮验证结果：
  - OpenCV 解码验证：输出 `youzainaye://pair/bind?join_code=123456`
  - 前端状态脚本：`node scripts/check_frontend_state.js`，结果 `frontend state check ok`
  - 后端回归：`pytest test_v2_core_reading.py test_v2_store_reading.py test_v2_e2e_flow.py test_v2_profile.py -q`
  - 结果：`19 passed`
- 仍需后续真机确认：
  1. 微信真机扫码识别 canvas 生成二维码。
  2. 保存二维码到相册时的相册权限授权流程。

## 2026-04-26 第十一轮
- 本轮目标：继续补齐可在本地闭环的功能优化，优先完成个人页目标反馈与提醒订阅/调度基础设施。
- 本轮完成的个人页优化：
  1. `pages/profile` 接入 `/api/v2/profile/goals`。
  2. 个人页新增“共读目标”卡片，展示完成书籍与打卡天数进度。
  3. 登录退出状态会同步重置目标进度，避免旧用户数据残留。
- 本轮完成的提醒链路：
  1. 后端新增 `WECHAT_REMINDER_TEMPLATE_ID` 配置。
  2. `/profile/reminders` 返回 `delivery_status`、`delivery_message` 和 `template_id`。
  3. 提醒页保存前调用 `wx.requestSubscribeMessage` 申请订阅授权。
  4. 用户拒绝或授权失败时，仍保存提醒偏好，并明确提示“需授权”。
  5. 新增 `ReminderDeliveryLog` 与 `reminder_delivery_logs` 表，按 `user_id + delivery_date` 做每日幂等。
  6. 新增 `backend/scripts/dispatch_reminders.py`，用于 cron/计划任务按用户时区和提醒时间发送微信订阅消息。
  7. 更新 MySQL 初始化脚本，补齐阅读目标、提醒配置、提醒投递日志表。
- 本轮暴露并记录的问题：
  1. 真实微信订阅消息必须依赖微信后台模板 ID、模板字段和用户授权，无法在本地伪造完整闭环。
  2. 当前调度脚本内置模板字段为 `thing1`、`time2`、`thing3`，生产模板字段不一致时必须调整脚本后再上线。
  3. 真机 `requestSubscribeMessage` 授权弹窗、实际投递结果仍需微信真机与正式模板验证。
- 本轮验证结果：
  - 前端状态脚本：`node scripts/check_frontend_state.js`，结果 `frontend state check ok`
  - 后端语法检查：`python -m py_compile backend/api/v2/reminders.py backend/common/models.py backend/common/config.py backend/scripts/dispatch_reminders.py`
  - 后端回归：`pytest test_v2_core_reading.py test_v2_store_reading.py test_v2_e2e_flow.py test_v2_profile.py -q`
  - 结果：`20 passed`
  - 调度脚本缺失环境变量验证：输出 `Reminder dispatch skipped, missing env: WECHAT_APP_ID, WECHAT_APP_SECRET, WECHAT_REMINDER_TEMPLATE_ID`
- 后续必须推进：
  1. 在微信后台确认真实订阅消息模板字段，并同步调整调度脚本 `data` 字段。
  2. 在服务器部署计划任务，周期执行 `python scripts/dispatch_reminders.py`。
  3. 真机验证订阅授权弹窗、消息投递、canvas 二维码扫码和保存相册权限。

## 2026-04-26 第十二轮
- 本轮目标：提升接口 REST 规范性和维护友好度，采用兼容迁移方式处理，避免直接破坏旧小程序调用。
- 本轮完成的后端接口改造：
  1. 新增 `backend/api/v2/rest_aliases.py`。
  2. 新增当前用户资源路径：
     - `GET /api/v2/users/me`
     - `PUT /api/v2/users/me`
     - `GET /api/v2/users/me/profile`
     - `GET /api/v2/users/me/stats`
     - `GET /api/v2/users/me/reading-history`
     - `GET|PUT /api/v2/users/me/reading-goal`
     - `GET|PUT /api/v2/users/me/reminder-config`
  3. 新增当前配对资源路径：
     - `GET /api/v2/pairs/current`
     - `POST /api/v2/pairs`
     - `DELETE /api/v2/pairs/current`
  4. 新增阅读资源路径：
     - `GET /api/v2/pairs/current/books/current`
     - `POST /api/v2/books/{book_id}/entries`
     - `PUT /api/v2/books/{book_id}/read-mark`
  5. 旧路径全部保留，作为兼容迁移期入口。
- 本轮完成的前端维护性改造：
  1. `services/api.js` 保持原统一导出，页面无需改引用。
  2. 内部拆分为：
     - `services/api/base.js`
     - `services/api/auth.js`
     - `services/api/pair.js`
     - `services/api/profile.js`
     - `services/api/reading.js`
     - `services/api/store.js`
  3. 前端 API 新调用已优先切到 REST 兼容路径。
- 本轮完成的文档：
  1. 新增 `team/api-rest-migration.md`，记录新旧接口映射、迁移原则和未完成项。
  2. 更新 `team/feature-matrix.md`，同步页面和前端 API 的新路径。
  3. 更新 `README.md`，加入 REST 兼容迁移矩阵入口。
- 本轮新增测试：
  1. 用户与配对 REST 兼容路径测试。
  2. 阅读主链 REST 兼容路径测试。
  3. 个人资料、统计、历史、目标和提醒 REST 兼容路径测试。
- 本轮验证结果：
  - 前端模块装载：`node -e "global.getApp=()=>({globalData:{apiBaseUrl:'http://localhost:8000'}}); require('./services/api.js'); console.log('api module ok')"`，结果 `api module ok`
  - 前端状态脚本：`node scripts/check_frontend_state.js`，结果 `frontend state check ok`
  - 后端回归：`pytest test_v2_core_reading.py test_v2_store_reading.py test_v2_e2e_flow.py test_v2_profile.py -q`
  - 结果：`23 passed`
- 本轮仍未完全解决的问题：
  1. 当前仍沿用统一 `200 + code` 响应包装，未切换到严格 REST 状态码。
  2. 旧动作式接口仍需保留迁移期，不能立即删除。
  3. 后端 router 仍承担较多业务逻辑，`service/repo` 分层尚未落地。
- 后续建议：
  1. 先增加旧接口调用统计，再根据小程序发版节奏确定废弃窗口。
  2. 制定 HTTP 状态码渐进策略。
  3. 继续推进 `service/repo` 分层，避免接口层继续膨胀。

## 2026-04-26 第十三轮
- 本轮目标：根据当前仍处于本地开发阶段的事实，取消旧接口兼容策略，直接落地 REST 路径和 service/repo 分层。
- 本轮完成的接口直改：
  1. 从对外路由中下线旧入口：
     - `GET /api/v2/me`
     - `PUT /api/v2/me`
     - `GET /api/v2/profile/*`
     - `POST /api/v2/pair/bind`
     - `POST /api/v2/pair/unbind`
     - `GET /api/v2/books/current`
     - `POST /api/v2/entries`
     - `POST /api/v2/books/{book_id}/entries/read`
  2. 保留并使用当前 REST 路径：
     - `/api/v2/users/me`
     - `/api/v2/users/me/profile`
     - `/api/v2/users/me/stats`
     - `/api/v2/users/me/reading-history`
     - `/api/v2/users/me/reading-goal`
     - `/api/v2/users/me/reminder-config`
     - `/api/v2/pairs/current`
     - `/api/v2/books/{book_id}/entries`
     - `/api/v2/books/{book_id}/read-mark`
- 本轮完成的分层落地：
  1. 新增 `backend/repo/reading_repo.py`
     - 承接用户、配对、书籍、笔记、目标、提醒相关数据库查询。
  2. 新增 `backend/service/reading_service.py`
     - 承接业务规则、并发锁、状态流转和错误码。
  3. `backend/api/v2/rest_aliases.py`
     - 只做参数接收、鉴权依赖和响应包装。
     - 不再调用旧 router 函数。
  4. `backend/api/v2/router.py`
     - 不再挂载 `profile/history/goals/reminders` 旧路由。
  5. `core_reading.py` 对外只保留 auth 类路由，`store_reading.py` 对外只保留书城读取路由。
- 本轮测试调整：
  1. 所有后端测试已切到新 REST 路径。
  2. 新增旧入口 404 测试，确认旧动作式路径不再注册。
  3. k6 压测脚本和测试环境文档已同步新笔记创建路径。
- 本轮暴露并修复的问题：
  1. Pydantic v2 对 `dict()` 给出弃用警告。
  2. 已改为 `_payload_dict()`，兼容 Pydantic v1/v2。
- 本轮验证结果：
  - 后端语法检查：`python -m py_compile backend/repo/reading_repo.py backend/service/reading_service.py backend/api/v2/rest_aliases.py backend/api/v2/router.py backend/api/v2/core_reading.py backend/api/v2/store_reading.py`
  - 前端模块装载：`api module ok`
  - 前端状态脚本：`frontend state check ok`
  - 后端回归：`pytest test_v2_core_reading.py test_v2_store_reading.py test_v2_e2e_flow.py test_v2_profile.py -q`
  - 结果：`24 passed`
- 后续建议：
  1. 继续将 `store_reading.py` 拆到 `store_service/store_repo`。
  2. 评估严格 HTTP 状态码策略。
  3. 真机验证新接口路径。

## 2026-04-26 第十四轮
- 本轮目标：继续处理未做流程，将书城链路完成 service/repo 分层，并确认正常使用小程序时功能与页面流转是否完整。
- 本轮完成的书城分层：
  1. 新增 `backend/repo/store_repo.py`
     - 承接书城目录、正文、分页查询、目录 upsert 和内置书写入。
  2. 新增 `backend/service/store_service.py`
     - 承接内置书种子、Gutendex 外部依赖、失败熔断、书籍简介、优质评价和阅读分页。
  3. 重写 `backend/api/v2/store_reading.py`
     - 只保留 `GET /store/books`、`GET /store/books/{catalog_id}`、`GET /store/books/{catalog_id}/read` 三个 router 入口。
  4. 更新 `backend/scripts/seed_store_books.py`
     - 改为调用 `store_service.seed_default_store_books`。
  5. 更新 `backend/test_v2_store_reading.py`
     - Gutendex monkeypatch 和熔断状态迁移到 `store_service`。
- 本轮完成的前端验证增强：
  1. `scripts/check_frontend_state.js` 新增真实 `services/api.js` 路径断言。
  2. 覆盖 `/users/me`、`/pairs/current`、`/books/{book_id}/entries`、`/books/{book_id}/read-mark`、`/store/books` 等新 REST 路径。
  3. 断言 `createEntry` 不再把 `book_id` 放在 body 中，而是使用路径参数。
- 本轮完成的产品/测试检查：
  1. 新增 `team/user-flow-check.md`。
  2. 检查用户主流程：
     - 初次登录
     - 结伴绑定
     - 共读码/二维码/扫码
     - 书城选书
     - 手动建书
     - 阅读同步
     - 进度补记
     - 动态回复
     - 阅读目标
     - 阅读历史
     - 提醒设置
     - 个人资料和退出登录
- 功能与流转结论：
  1. 本地开发环境下，MVP 主链功能已基本完整。
  2. 页面流转已覆盖“登录 -> 结伴 -> 选书/建书 -> 阅读 -> 记录进度 -> 查看进度/回复 -> 我的页管理”。
  3. 正式上线前仍不能宣称完整交付，因为以下能力必须真机或生产环境验证：
     - 微信手机号授权 `getPhoneNumber`
     - 本地 canvas 二维码被微信扫码识别
     - 保存二维码到相册权限
     - 微信订阅消息真实授权和投递
     - 服务器调度任务
     - MySQL 实例级迁移、弱网和并发压测
- 本轮验证结果：
  - 前端状态脚本：`node scripts/check_frontend_state.js`，结果 `frontend state check ok`
  - 前端模块装载：`api module ok`
  - 后端语法检查：`python -m py_compile backend/repo/store_repo.py backend/service/store_service.py backend/api/v2/store_reading.py backend/repo/reading_repo.py backend/service/reading_service.py backend/api/v2/rest_aliases.py`
  - 书城专项回归：`pytest test_v2_store_reading.py -q`
  - 结果：`8 passed`
  - 后端全量回归：`pytest test_v2_core_reading.py test_v2_store_reading.py test_v2_e2e_flow.py test_v2_profile.py -q`
  - 结果：`24 passed`
- 后续建议：
  1. 进入微信真机验收。
  2. 配置真实订阅消息模板与服务器计划任务。
  3. 做 MySQL 实例级验证和压测。
## 2026-04-26 第十五轮
- 本轮目标：修复未登录底部导航闪屏、书城英文/不可加入数据问题，并内嵌测试用户支持本地绑定验证。
- 已暴露并修复的问题：
  1. 未登录点击底部结伴、书城、我的时，原逻辑先 `switchTab` 再由页面登录门禁回退，导致闪屏。
  2. 书城默认可能混入 Gutendex 英文目录，部分目录没有本地正文，进入详情后加入共读会提示书籍不存在或正文不可用。
  3. 本地绑定测试缺少固定身份，测试人员需要反复走真实登录或临时 debug openid。
- 本轮完成：
  1. `custom-tab-bar/index.js` 在切换前检查登录态，未登录访问非首页 tab 只提示，不再切页。
  2. `backend/service/store_service.py` 扩展本地中文分类书库，覆盖国外名著、历史、心学、玄学术数、中医经络、国学经典。
  3. `/store/books` 支持 `category` 参数，并返回 `categories`、`category`、`category_label`、`has_more`。
  4. 默认关闭 Gutendex 外部同步，保留 `STORE_ENABLE_NETWORK=1` 作为显式开关，避免本地阶段继续混入英文不可加入数据。
  5. `pages/bookstore` 改为分类筛选和中文书库展示。
  6. `book-detail` 以本地正文是否存在判定 `has_text`，避免无正文目录被误判为可加入。
  7. 新增 `POST /api/v2/auth/test-login`，测试用户 A/B 固定共读码为 `900001` / `900002`。
  8. 首页和我的页增加测试用户 A/B 登录入口。
- 本轮测试：
  - `node scripts/check_frontend_state.js`：`frontend state check ok`
  - `pytest test_v2_store_reading.py -q`：`8 passed`
  - `pytest -q`：`25 passed`
  - `git diff --check`：通过，仅有 CRLF 转换提示
- 当前仍需真机验证：
  1. 微信手机号授权弹窗和真实返回。
  2. 真机扫码识别本地 canvas 二维码。
  3. 保存二维码到相册权限。
  4. 微信订阅消息真实授权和投递。
  5. MySQL 实例级迁移、弱网和并发压测。
## 2026-04-26 第十六轮
- 本轮目标：按用户反馈修正测试用户方案，测试用户不出现在小程序界面，并且按真实用户注册后的数据保存路径入库。
- 已暴露并修复的问题：
  1. 上轮把测试用户 A/B 入口放在首页和我的页，违反“测试用户不应该出现在界面上”的产品边界。
  2. 前端存在 `testLogin` 与 `loginFlow({ method: 'test' })` 特殊路径，偏离真实小程序登录流程。
  3. 后端测试用户之前会自动写入 `agreement_accepted_at`，等于跳过真实注册后协议确认状态。
- 本轮完成：
  1. 删除首页和我的页测试用户 A/B 按钮、说明和样式。
  2. 删除前端 `utils/auth.js` 的 `testLogin` 和 `app.js` 的测试登录分支。
  3. 后端保留 `POST /api/v2/auth/test-login` 作为测试环境辅助入口，但新增 `ENABLE_TEST_USERS` 开关；SQLite 测试环境默认启用，MySQL/生产默认关闭。
  4. 测试用户仍通过 `_get_or_create_user` 写入 `users`，登录写入 `sessions`，绑定写入正式配对链路。
  5. 测试用户不再自动接受协议，返回 `need_agreement=true`，保持真实用户注册后的状态语义。
  6. 前端状态脚本增加断言，确保首页和我的页不包含测试用户入口。
- 本轮验证：
  - `node scripts/check_frontend_state.js`：`frontend state check ok`
  - `pytest test_v2_core_reading.py -q`：`9 passed`
  - `pytest -q`：`26 passed`
  - `git diff --check`：通过，仅有 CRLF 转换提示

## 2026-04-26 第十七轮
- 本轮目标：为后端补齐阿里云 Docker 化部署能力，支持通过 `47.99.240.126:18080` 做开发联调，并预留 SSL/Nginx 配置。
- 已暴露并处理的真实限制：
  1. `www.nizaina.com` 未备案，在大陆云服务器上会被拦截，不能作为正式小程序后端域名。
  2. SSL 证书绑定域名，不能直接用于 `https://47.99.240.126`，否则会出现证书域名不匹配。
  3. 当前没有阿里云 SSH 用户、密码或密钥，无法实际同步服务器；本轮只交付可执行脚本和命令，不伪装已经部署成功。
  4. 当前本机没有 Docker 和 `bash/sh`，无法本地执行 Docker Compose 真实构建和 shell 语法检查。
- 本轮完成：
  1. 更新 `backend/Dockerfile`，使用阿里云 apt/pip 镜像，安装运行依赖，非 root 用户运行后端。
  2. 更新 `backend/docker-compose.yml`，编排 MySQL、FastAPI 后端和 Nginx，默认暴露 `18080:80`，预留 `18443:443`。
  3. 新增 `backend/nginx/nginx.conf`、`backend/nginx/conf.d/api.conf` 和 `backend/nginx/conf.d/ssl.conf.example`。
  4. 新增 `backend/scripts/docker_entrypoint.sh`，容器启动时等待 MySQL 并执行结构更新。
  5. 新增 `backend/scripts/cloud_deploy.sh`，云端自动安装 Docker、配置国内镜像、生成 `.env`、构建启动并健康检查。
  6. 新增 `backend/scripts/sync_to_aliyun.ps1` 和 `backend/scripts/sync_to_aliyun.sh`，支持本地打包、上传和远程部署。
  7. 替换 `backend/deploy_guide.md`，给出阿里云安全组、同步命令、云端部署命令、SSL 限制和运维命令。
  8. 更新 `.gitignore` 与 `.dockerignore`，避免提交证书私钥、部署包、日志和本地环境文件。
  9. 更新 `README.md`，增加阿里云 Docker 部署入口。
- 本轮验证：
  - PowerShell 同步脚本语法：通过。
  - Docker Compose YAML 解析：通过。
  - 部署文档和脚本 UTF-8 读取：通过。
  - 部署包内容验证：通过，包含 `.env.example`、`docker-compose.yml`、`scripts/cloud_deploy.sh`。
  - `node scripts/check_frontend_state.js`：`frontend state check ok`
  - `pytest -q`：`26 passed`
- 后续必须执行：
  1. 在阿里云安全组放行 `18080/tcp`。
  2. 提供 SSH 用户和密钥或密码后执行同步脚本。
  3. 云端部署后访问 `http://47.99.240.126:18080/health` 做健康检查。
  4. 正式小程序上线前完成域名备案、HTTPS 和微信后台合法域名配置。

## 2026-04-26 第十七轮补充：公网健康检查排障
- 用户云端截图显示：
  1. `docker ps` 中 `you_where_mysql` 和 `you_where_backend` 均为 healthy，`you_where_nginx` 已启动。
  2. 服务器本机访问 `http://127.0.0.1:18080/health` 返回 `{"status":"ok"}`。
  3. 服务器本机访问 `http://47.99.240.126:18080/health` 出现超时，浏览器曾出现 `502 Bad Gateway`。
- 结论：
  1. 容器内部主链路已通，优先怀疑公网入站、安全组、系统防火墙或云厂商公网 IP 回环限制。
  2. 502 需要通过 Nginx 日志进一步区分是短暂 upstream 未就绪还是公网入口/代理层问题。
- 本轮补充：
  1. `backend/nginx/conf.d/api.conf` 新增 `/nginx-health`，用于区分 Nginx 自身可达与后端 upstream 可达。
  2. `backend/scripts/cloud_deploy.sh` 将本地健康检查和公网自检分开输出，避免只测 `127.0.0.1` 却显示公网 OK。
  3. `backend/deploy_guide.md` 增加 502/超时排查命令、安全组和系统防火墙处理说明。

## 2026-04-26 第十八轮
- 本轮目标：修正结伴页共读码卡片体验，解决二维码显示异常，并简化复制入口。
- 已确认事实：
  1. 后端测试账号 A/B 固定共读码分别为 `900001` 和 `900002`。
  2. 测试账号入口只在后端测试环境能力中存在，小程序界面不展示。
- 本轮完成：
  1. `pages/partner/index.wxml` 删除共读码旁边的“复制”文字按钮，只保留右上角复制图标。
  2. `pages/partner/index.wxss` 将二维码 canvas 从 `210rpx` 改为固定 `128px`，避免 rpx 显示尺寸与 canvas 绘制坐标不一致导致裁切。
  3. `pages/partner/index.js` 将二维码绘制尺寸统一为 `QR_CANVAS_SIZE=128`，预览/保存时导出为 `512x512`，保证分享图片清晰度。
  4. `scripts/check_frontend_state.js` 增加断言，防止结伴页再次出现 inline 复制按钮或 `210rpx` canvas 尺寸。
- 本轮验证：
  - `node scripts/check_frontend_state.js`：`frontend state check ok`
  - `pytest test_v2_core_reading.py -q`：`9 passed`
  - `pytest -q`：`26 passed`

## 2026-04-26 第十九轮
- 本轮目标：修复云端开发环境中输入测试用户共读码 `900002` 返回“未找到对应用户”的问题。
- 根因：
  1. 测试用户固定共读码只是后端测试能力定义，不会在 MySQL 生产/云端环境自动存在。
  2. 当前云端 `.env` 默认 `ENABLE_TEST_USERS=0`，所以 `/auth/test-login` 不会自动写入测试用户。
  3. 用户输入 `900002` 绑定时，`users` 表中没有该共读码，因此按真实业务返回 `40011`。
- 本轮完成：
  1. 新增 `backend/scripts/seed_test_users.py`，可显式把隐藏测试用户 A/B 写入真实 `users` 表。
  2. 脚本支持 `--reset-active-pairs`，用于重复测试时解除测试用户已有活跃绑定。
  3. `docker_entrypoint.sh` 增加可选 `SEED_TEST_USERS=1`，允许云端开发环境启动时自动补齐测试用户。
  4. `docker-compose.yml`、`.env.example`、`cloud_deploy.sh` 补齐 `SEED_TEST_USERS` 环境变量。
  5. `backend/test_v2_core_reading.py` 新增“真实用户绑定已种子测试用户 B”的回归测试。
  6. `backend/deploy_guide.md` 和 `README.md` 增加隐藏测试用户云端使用说明。
- 本轮验证：
  - `python -m py_compile backend/scripts/seed_test_users.py backend/scripts/apply_schema_updates.py`：通过
  - `pytest test_v2_core_reading.py -q`：`10 passed`
  - `pytest -q`：`27 passed`
  - `node scripts/check_frontend_state.js`：`frontend state check ok`

## 2026-04-27 协作规则补充
- 用户确认后续进入产品需求和 UI 优化讨论。
- 用户要求继续保持三类记录机制：
  1. `record.md`：记录关键对话、决策、问题暴露、结论。
  2. `待办.md`：记录待处理任务、风险、后续验证项。
  3. `已办.md`：记录已完成事项、验证结果、交付结论。
- 后续每次计划结束时必须更新上述三个文件。
- 更新记录文件时不需要把完整记录内容带入对话上下文，只需在必要时简要说明“记录已更新”。

## 2026-04-27 产品需求讨论：PRD v0.1
- 用户确认产品更偏“情侣/朋友共读”。
- 用户确认内容方向偏向心学、术数、中医经络、国学等特色内容。
- 用户确认当前结伴关系暂时只支持 2 人。
- 用户确认首页应强调和伙伴关系，而不是普通工具工作台。
- 用户确认商业化未来会考虑，但当前先专注产品打磨，不立即展开额度、价格和变现细节。
- 本轮完成 `team/PRD.md`，形成 PRD v0.1，覆盖产品定位、目标用户、核心流程、页面需求、验收标准、非功能要求和商业化预留边界。

## 2026-04-27 产品讨论节奏约束
- 用户要求产品讨论在 15 轮内结束。
- 当前设定最多 15 轮产品讨论，每轮只解决一个明确主题。
- 第 1 轮已完成：产品定位、内容方向、关系模型、PRD v0.1。
- 后续按首页、结伴页、书城、阅读互动、我的页、新用户引导、文案、视觉规范、状态设计、验收、指标、商业化预留、范围冻结、定稿计划推进。

## 2026-04-27 产品讨论节奏调整
- 用户确认产品讨论可以超过 15 轮，以便更细腻地讨论，但必须有结束范围。
- 当前调整为 18-24 轮内收束，最迟第 24 轮完成产品讨论定稿。
- 用户强调设计出来的产品不能有很重的 AI 味道。
- 后续 UI 讨论必须避免模板化、空泛渐变、堆功能卡片、无差异文案等 AI 感表现。
- 用户允许在需要时自动从网上加载 skill，例如 super-powers 类工作流技能。
- 已通过公开技能目录确认 `obra/superpowers` 生态中存在 brainstorming、writing-plans、systematic-debugging、verification-before-completion 等工作流技能；后续如确需安装，会优先选择可信来源并用于明确任务。

## 2026-04-27 产品讨论第 7 轮：新用户引导与登录前体验
- 用户认可登录前不能只是“请登录”，需要先解释双人共读价值。
- 登录前第一屏目标：让用户知道这是双人共读、适合亲近关系、愿意登录并邀请一个人。
- 推荐主文案为“和重要的人，一起读完一本书”。
- 登录前可展示轻量预览：双人进度卡片、特色书房方向、共读关系文案。
- 登录前不展示真实完整书城、复杂功能入口、业务 tab、测试用户入口、共读码/二维码、商业化 Banner。
- 新用户引导采用状态驱动，不做 3-5 页长教程。
- 状态路径为：未登录解释价值、已登录未绑定引导邀请、已绑定无书引导选书、已有书无笔记引导记录第一条进度。
- 结论已同步到 `team/PRD.md`。

## 2026-04-27 产品讨论第 8 轮：品牌文案语气
- 用户认可品牌文案语气方向。
- 品牌语气确定为：温柔、克制、有陪伴感，带一点东方气质，但不故作玄虚。
- 文案要避免 AI 味、强打卡压迫感、过度玄学和普通工具味。
- 文案要多使用“我们、一起、慢慢、留下、回应”等关系型表达。
- 产品名“你在哪里”可以保留，但建议增加副标题：
  1. 和重要的人一起共读
  2. 一本书，两个人慢慢读
- 后续页面文案检查标准为：是否像真人说的话、是否服务当前状态、是否有双人关系感、是否避免压力和玄虚、是否避免模板化 AI 表达。
- 结论已同步到 `team/PRD.md`。

## 2026-04-27 产品讨论第 9 轮：UI 视觉方向
- 本轮使用 `frontend-design` 技能原则作为参考，但落地约束为原生微信小程序 WXML/WXSS。
- 用户希望 UI 设计避免明显 AI 味，不能做模板化界面。
- 视觉方向确定为“温润纸感 + 东方书房 + 双人关系”。
- 不采用通用绿白工具小程序风格，也不采用厚重玄学装饰。
- 主色建议从微信绿转向纸米色、松烟墨、青瓷绿、朱砂红、暖灰等轻东方色彩系统。
- 字体策略保持小程序兼容性，不强行引入复杂字体；通过字号、字重、字距和数字样式建立气质。
- 组件原则为轻纸张卡片、弱阴影、单主 CTA、弱化危险操作、减少无意义图标和 emoji。
- 页面原则：首页是双人状态卡，结伴页绑定前/后分层，书城像主题书房，进度页像双人读书日记，我的页是共读资产管理。
- 结论已同步到 `team/PRD.md`。

## 2026-04-27 产品讨论第 10 轮：核心状态设计
- 用户认可产品体验应由状态驱动，而不是功能入口驱动。
- 核心状态统一为：未登录、已登录未绑定、已绑定无书、已绑定有书未记录、已绑定有书有动态、双方完读、异常/失败。
- 每个状态只保留一个主行动，空状态必须告诉用户下一步。
- 首页、结伴页、书城页、进度页、我的页后续需要共享同一套状态口径。
- 后续 UI 和文案不再使用通用“暂无数据”，异常态也要解释原因并保持温柔。
- 结论已同步到 `team/PRD.md`。

## 2026-04-27 产品讨论第 11 轮：验收标准与测试清单
- 用户认可后续 UI 改造不能只验收“功能可点”。
- 每个页面必须同时验收状态是否正确、主行动是否唯一、文案是否符合品牌语气、是否体现双人关系、异常是否给出下一步、是否避免 AI 味。
- 全局状态验收覆盖未登录、已登录未绑定、已绑定无书、有书未记录、有动态、双方完读。
- 页面验收覆盖首页、结伴页、书城页、进度页、我的页。
- 测试分为自动化回归、人工状态验收、真机验收三层。
- 产品验收红线包括：主空状态出现“暂无数据”、多个同权重主按钮、绑定后大面积展示二维码、首页功能九宫格、默认展示不可加入书籍、文案像 AI 模板、异常只显示接口错误。
- 结论已同步到 `team/PRD.md`。

## 2026-04-27 产品讨论第 12 轮：数据指标与产品效果评估
- 用户认可产品指标应围绕双人共读关系是否成立，而不是套普通 DAU、PV、点击率。
- 北极星指标确定为“有效共读关系数”。
- 有效共读关系定义为：两人已绑定，且创建了至少一本共读书，且双方都至少记录过一次进度或笔记。
- 关键漏斗为：登录、绑定、开始共读、首次记录、双向互动、完读归档。
- 第一阶段重点验证绑定成功率、绑定后开始共读率、首次记录率。
- 用户明确商业优化暂时不考虑，当前专注产品打磨。
- 商业化从下一轮议题降级为 PRD 中的“结构预留但不展开”。
- 结论已同步到 `team/PRD.md`。

## 2026-04-27 产品讨论第 13 轮：MVP 范围冻结
- 用户认可 MVP 范围冻结方向。
- 当前阶段目标确定为打磨核心闭环：登录 -> 结伴 -> 选书 -> 共读 -> 记录 -> 回应 -> 完读。
- 第一阶段 UI 改造范围冻结为：首页、结伴页、书城页、进度页、全局视觉变量与组件样式、核心状态文案统一。
- 我的页、阅读器、提醒页、历史页、设置页暂不做深度改版。
- 多人小组、公开社区、排行榜、复杂成就、AI 解读、付费会员、付费书单、课程、社群转化、复杂运营 Banner、完整数据看板、完整埋点、多端同步、管理员后台全部延期。
- 提醒、目标、历史、二维码、书城搜索保留基础能力但不深做。
- 结论已同步到 `team/PRD.md`。

## 2026-04-27 产品讨论第 14 轮：PRD 定稿与 UI 改版执行计划
- 用户认可 PRD 定稿与 UI 改版执行计划。
- 产品讨论阶段收束，`team/PRD.md` 作为 PRD v1.0 执行基线。
- UI 改版执行顺序确定为：全局视觉基建、首页重构、结伴页重构、书城页重构、进度页重构、收口验证。
- 单页改造交付格式确定为：页面目标、覆盖状态、主 CTA、空状态文案、异常文案、修改文件、验证命令、剩余风险。
- 第一阶段不做：我的页深度重构、阅读器复杂重构、提醒页复杂重构、历史页复杂重构、商业化、多人小组、AI 解读。
- 首个实施任务确定为“建立全局视觉变量和首页 v1”。
- 后续新增产品想法进入延期清单，不打断第一阶段 UI 改造。

## 2026-04-27 产品讨论第 2 轮：首页信息架构
- 用户认可首页不应是功能菜单，而应是“我和伙伴的共读状态面板”。
- 首页按四种状态组织：未登录、已登录未绑定、已绑定无书、已绑定有在读书。
- 每种状态只保留一个主 CTA：登录、去结伴、去选书、记录进度。
- 用户进一步强调当前 UI 界面不合理，是后续优化重点。
- 用户指出绑定前和绑定后的界面存在重复，这是需要重点修复的问题。
- 下一轮进入结伴页信息架构与关系表达，重点解决绑定前/绑定后重复、视觉层级混乱、二维码/共读码卡片过重。

## 2026-04-27 产品讨论第 3 轮：结伴页信息架构
- 用户认可结伴页需要重构为绑定前/绑定后两套不同信息架构。
- 绑定前页面定位为工具型页面，核心任务是完成邀请和绑定。
- 绑定后页面定位为关系型页面，核心任务是展示和经营双人共读关系。
- 绑定前可强展示共读码、二维码、输入框、扫一扫。
- 绑定后应弱化二维码，不再让二维码占据主视觉。
- 绑定后应优先展示头像、昵称、结伴天数、当前共读书、双方进度和下一步行动。
- 结论已同步到 `team/PRD.md`。

## 2026-04-27 产品讨论第 4 轮：书城分类与内容策略
- 用户认可书城不应是普通全部书籍列表，而应是“适合两个人一起读的主题书房”。
- 书城分类从普通学科分类升级为“共读场景 + 主题气质”：
  1. 心性共修
  2. 国学经典
  3. 术数入门
  4. 经络养生
  5. 历史人物
  6. 双人共读
- 默认推荐优先展示有讨论空间、共同成长感、适合慢读、中文可读且内容完整的书。
- 不建议默认展示英文原文、无正文内容、过度工具化、过于晦涩且无导读、存在合规风险的术数材料。
- MVP 阶段书城建议每个分类 3-6 本精选书，总量控制在 20-30 本。
- 书籍卡片应突出“一句共读理由”“适合关系”“阅读节奏”，详情页应回答“为什么适合我们一起读”。
- 结论已同步到 `team/PRD.md`。

## 2026-04-27 产品讨论第 5 轮：阅读/进度页双人互动
- 用户认可阅读/进度页不应是“我的读书记录”，而应是“我们这本书读到哪里了，TA 最近留下了什么”。
- 页面核心价值是体现双人共读陪伴，而不是普通记录列表。
- 第一屏应优先展示当前书、双方进度对比、下一步行动、TA 最新动态。
- 双方进度展示应偏陪伴感，不制造强竞争。
- 笔记流应像双人共读日记，而不是公开评论区。
- 回复机制保持轻量，仅做单层回复。
- 双方完读后需要小仪式感：共读天数、笔记数量、归档、选下一本。
- 结论已同步到 `team/PRD.md`。

## 2026-04-27 产品讨论第 6 轮：我的页辅助定位
- 用户认可我的页不应是第二个首页，也不应抢伙伴共读主线。
- 我的页定位为“个人资料与共读资产管理”。
- 信息优先级确定为：个人资料、共读资产、阅读目标、阅读历史、提醒设置、设置/协议/关于。
- 阅读目标不应像 KPI，应表达为“给我们一个轻轻坚持的方向”。
- 阅读历史应表达为“双人记忆”，不是普通列表。
- 提醒应是温柔提醒，不做强打卡压迫。
- 当前阶段不在我的页放复杂会员入口、强运营 Banner 或测试用户入口。
- 结论已同步到 `team/PRD.md`。

## 2026-04-27 UI 实施第 1 轮：首页 v1 与全局视觉基线
- 本轮目标：按 PRD v1.0 首先落地“温润纸感 + 东方书房 + 双人关系”的全局视觉基线，并重构首页 v1。
- 本轮完成：
  1. `app.wxss` 重建全局色彩变量与基础按钮、卡片、弹窗样式，保留 `--me` / `--partner` 兼容已有页面。
  2. `pages/home/index.wxml` 按核心状态重构：首页覆盖未登录、已登录未绑定、已绑定无书、已绑定有书四种状态。
  3. 首页主 CTA 收敛为：登录、邀请伙伴、去主题书房选书、记录今天读到哪里。
  4. 登录前页面不再只是“请登录”，改为解释双人共读价值，并展示轻量双人关系预览。
  5. 已绑定无书状态的主入口改为“去主题书房选书”，手动添加降为次级能力。
  6. 已绑定有书状态展示双方页码、进度条和关系型提示文案，弱化普通工具入口。
  7. `pages/home/index.js` 增加书籍进度归一化、头像首字 fallback、去书城入口和记录今日入口。
- 本轮验证：
  - `node scripts/check_frontend_state.js`：通过，输出 `frontend state check ok`
  - `pytest -q`：通过，结果 `27 passed`
  - `git diff --check`：通过，仅有 Windows CRLF 转换提示
- 未完成/待人工确认：
  1. 需要在微信开发者工具中预览首页四种状态，确认视觉层级、按钮间距和底部 tabbar 遮挡。
  2. 需要真机确认字体 fallback、纸感背景、进度条显示和弹窗输入体验。
  3. 下一轮按计划进入结伴页 v1，重点解决绑定前/绑定后重复和二维码权重过高问题。

## 2026-04-27 UI 实施第 2 轮：一级导航重构与主链 UI 统一
- 用户反馈当前 UI 存在三个真实问题：
  1. AI 味过重，一眼像生成式模板。
  2. 修改后的页面与底部 Tab 导航割裂严重。
  3. 结伴页和共读页登录后职责重叠。
- 本轮产品/开发结论：
  1. 不能继续只改单页皮肤，必须先调整一级导航的信息架构。
  2. “结伴”不应继续作为一级 Tab，绑定前是工具任务，绑定后是关系管理，应该从首页/关系入口进入。
  3. 一级 Tab 重设为：共读、书房、日记、我的；底部中央按钮固定为“记一笔”。
- 本轮完成：
  1. `app.json` 更新 Tab 配置：移除 `partner` 一级 Tab，新增 `progress` 为“日记”一级 Tab。
  2. `custom-tab-bar` 重写为纸感悬浮导航，不再使用旧微信绿图标风格。
  3. `pages/home/index.js` 调整 Tab 选中态和跳转逻辑：伙伴页改为 `navigateTo`，日记页改为 `switchTab`，记录入口通过 `app.globalData.openProgressComposer` 跨 Tab 打开。
  4. `pages/partner` 重构为二级关系页：绑定前保留输入共读码、扫一扫、二维码分享；绑定后改为关系面板、当前共读书、下一步行动和低权重二维码入口。
  5. `pages/progress` 重构为“共读日记”页：统一纸感视觉、双人进度、记录行动卡、笔记流、防剧透文案和弹窗样式。
  6. `pages/bookstore/index.wxss` 同步纸感视觉，降低书房页与新首页/日记页的割裂。
  7. `pages/book-detail/index.js` 修正 partner/progress 页面跳转方式，适配新的 Tab 结构。
  8. `scripts/check_frontend_state.js` 更新 Tab 索引断言，匹配新的导航结构。
- 本轮验证：
  - `node scripts/check_frontend_state.js`：通过，输出 `frontend state check ok`
  - `pytest -q`：通过，结果 `27 passed`
  - `git diff --check`：通过，仅有 Windows CRLF 转换提示
- 待人工验收：
  1. 微信开发者工具检查 Tab 页面切换：首页、书房、日记、我的。
  2. 从首页进入结伴页后，确认返回路径、扫码、二维码绘制和复制共读码。
  3. 点击底部中央“记一笔”时，分别验证未登录、未绑定、无书、有书四种状态。
  4. 真机确认底部悬浮 Tab 是否遮挡内容，特别是首页、书房列表和日记流底部。

## 2026-04-27 UI 实施第 3 轮：割裂修复、我的页重构与导航安全区
- 用户继续反馈 5 个问题：
  1. 我的页与其他 Tab 主题割裂。
  2. 绑定页面格局不合理，审美不足。
  3. 字体在元素框中不居中，主页和顶部导航栏割裂。
  4. 退出登录后的我的页登录界面与初入登录界面不统一。
  5. 底部导航栏与页面元素重叠，这是严重 bug。
- 本轮完成：
  1. `app.wxss` 增强全局 button 规则，去掉微信按钮默认 margin/padding/line-height 干扰，统一按钮文字垂直居中。
  2. 首页、书房、日记、我的四个一级 Tab 页统一增加底部安全留白，避免悬浮 Tab 遮挡内容。
  3. 新增/更新页面级 `index.json`，将首页、书房、日记、我的、结伴、书籍详情、阅读器、目标、历史、提醒、设置的导航栏背景统一为纸感色。
  4. `pages/profile` 完整重构为“共读资产”页，登录态和未登录态均使用同一套纸感视觉和产品叙事。
  5. 退出登录后同步清理我的页编辑状态、tabbar 的 `hasBook/hasPartner` 状态，并显示统一的未登录界面。
  6. `pages/partner` 绑定前重新分区为“让对方绑定我”和“我收到对方共读码”，增加关系预览卡，降低堆叠感。
  7. 结伴页按钮、危险操作按钮改为 flex 居中，修复文字在按钮中偏移的问题。
  8. 书籍详情、阅读器、阅读目标、提醒页低风险替换旧灰底和微信绿残留，减少跨页割裂。
- 本轮验证：
  - `node scripts/check_frontend_state.js`：通过，输出 `frontend state check ok`
  - `pytest -q`：通过，结果 `27 passed`
  - `git diff --check`：通过，仅有 Windows CRLF 转换提示
- 待人工验收：
  1. 微信开发者工具检查我的页登录前/登录后/退出登录后三种状态是否统一。
  2. 真机检查底部悬浮 Tab 是否仍遮挡首页、书房、日记、我的页底部内容。
  3. 真机检查结伴页二维码 canvas 是否仍正常绘制、预览和保存。
  4. 检查所有按钮文字是否垂直居中，尤其是绑定、扫一扫、退出登录、昵称弹窗保存按钮。

## 2026-05-07 UI 实施第 4 轮：书籍详情、Tab 图标、我的页顶部与阅读器
- 用户反馈本轮需继续调整：
  1. 书籍详情页“开始阅读 / 加入共读”按钮不美观。
  2. 底部导航栏不应继续使用“合 / 书 / 记 / 我”文字，应替换为图标。
  3. 我的页“我的 / 册”显示突兀，需要重新设计顶部。
  4. 阅读界面需要更像看书，并支持目录、阅读模式、翻页特效、字体调整、重点划线。
- 本轮完成：
  1. `custom-tab-bar` 将文字标识替换为 SVG mask 图标：首页、书房、日记、我的均使用真实图标；中央“记一笔”改为笔形图标。
  2. `pages/book-detail` 重构书籍详情视觉，将按钮改为主次行动卡：开始阅读、加入共读，补充行动说明。
  3. `pages/profile` 去掉突兀的“册”圆形印章，改为更克制的资产摘要 chip。
  4. `pages/reader` 重构为阅读器 v1：
     - 支持目录面板（当前基于页段生成，因后端暂无真实章节目录）。
     - 支持纸页、专注、夜读三种阅读模式。
     - 支持字号 A-/A+ 调整并持久化到本地。
     - 支持翻页动效。
     - 支持点击段落添加/取消重点划线，划线记录按书籍和页码保存在本地。
     - 保留同步进度能力。
- 已暴露的真实限制：
  1. 后端当前 `/store/books/{catalog_id}/read` 只按页返回正文，不返回章节目录，因此目录只能先按页段生成。
  2. 当前划线是段落级本地标记，不是精确到选中文字的富文本划线；后续若要精确划线，需要正文分词/选择范围和后端存储结构。
- 本轮验证：
  - `node scripts/check_frontend_state.js`：通过，输出 `frontend state check ok`
  - `pytest -q`：通过，结果 `27 passed`
  - `git diff --check`：通过，仅有 Windows CRLF 转换提示
- 待人工验收：
  1. 微信开发者工具检查 Tab 图标 mask 是否正常渲染。
  2. 真机检查书籍详情两个行动卡的点击区域和 loading 状态。
  3. 真机检查阅读器目录面板、设置面板、夜读模式、字号调整、段落划线和翻页动效。

## 2026-05-07 UI 实施第 5 轮：书籍详情溢出、阅读器手势与顶部留白
- 用户继续反馈：
  1. 书籍详情页“加入共读 / 开始阅读”分配不合理并超出屏幕。
  2. 阅读器需要像真实看书：单点屏幕翻页、左右滑翻页、上一页/下一页 tab，并且目录/字号等工具应隐藏，不影响翻页。
  3. 所有顶部导航栏距离不合理，书籍详情显示不全，需要调整布局。
- 本轮完成：
  1. 书籍详情页行动区改为纵向主次结构：
     - `加入共读` 作为主行动放在上方，占满宽度。
     - `开始阅读` 作为次行动放在下方，占满宽度。
     - 彻底移除双列按钮导致的窄屏溢出风险。
  2. 阅读器交互重构：
     - 左右滑动翻页。
     - 左侧区域单点上一页，右侧区域单点下一页。
     - 中间区域单点呼出/隐藏阅读工具。
     - 长按段落添加/取消重点划线，避免和单点翻页冲突。
     - 顶部信息栏、底部上一页/同步/下一页、目录和设置面板默认隐藏。
     - 目录改为左侧抽屉面板，不占用正文空间。
  3. 顶部留白调整：
     - 书籍详情页、阅读器、首页、结伴页、日记页、我的页、书房页顶部内容整体下移。
     - 避免内容贴近或被原生导航栏压住。
- 本轮验证：
  - `node scripts/check_frontend_state.js`：通过，输出 `frontend state check ok`
  - `pytest -q`：通过，结果 `27 passed`
  - `git diff --check`：通过，仅有 Windows CRLF 转换提示
- 当前阅读器手势约定：
  1. 左右滑：翻页。
  2. 左侧/右侧单点：上一页/下一页。
  3. 中间单点：显示或隐藏目录、字号、模式、同步等工具。
  4. 长按正文段落：重点划线。
- 待人工验收：
  1. 微信开发者工具确认书籍详情页行动区不再超出屏幕。
  2. 真机确认阅读器左右滑、左右单点、中间单点、长按划线不会互相冲突。
  3. 真机确认顶部导航栏与页面内容距离是否足够。

## 2026-05-07 UI 实施第 6 轮：书籍详情同行按钮与微信读书式阅读器
- 用户要求：
  1. `加入共读` 和 `开始阅读` 必须在同一行，并能在同一屏幕内显示。
  2. 阅读器继续参考微信读书实现方式。
- 本轮完成：
  1. 书籍详情行动区改为同一行等宽双按钮：
     - `开始阅读` 在左侧，作为次级行动。
     - `加入共读` 在右侧，作为主行动。
     - 使用 `minmax(0, 1fr)`、压缩内边距、副文案截断，避免窄屏溢出。
  2. 阅读器改为更接近微信读书的上下浮层模式：
     - 默认隐藏顶部书名栏和底部工具栏，优先展示正文。
     - 中间单点显示/隐藏顶部栏和底部栏。
     - 底部浮层集中展示阅读进度、上一页、同步进度、下一页、目录、设置。
     - 顶部浮层展示返回、书名、作者、目录和 Aa。
     - 左右点击和左右滑仍负责翻页。
     - 目录抽屉和设置面板避开底部浮层区域。
- 本轮验证：
  - `node scripts/check_frontend_state.js`：通过，输出 `frontend state check ok`
  - `pytest -q`：通过，结果 `27 passed`
  - `git diff --check`：通过，仅有 Windows CRLF 转换提示
- 待人工验收：
  1. 微信开发者工具检查书籍详情同行按钮在 375px/360px 宽度下是否不溢出。
  2. 真机检查阅读器轻点中间呼出工具、左右点击翻页、左右滑翻页是否符合预期。
  3. 真机检查底部浮层是否遮挡正文最后几行。
