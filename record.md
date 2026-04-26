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
