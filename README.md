# TODO 小程序企业化主线说明

## 项目主线
- 后端唯一入口：`backend/app_main.py`
- API 主版本：`/api/v2`
- 数据库：MySQL（默认）

## 快速启动（后端）
1. 配置环境变量：`DB_BACKEND=mysql`、`MYSQL_HOST`、`MYSQL_PORT`、`MYSQL_USER`、`MYSQL_PASSWORD`、`MYSQL_DB`
2. 配置微信登录环境变量：`WECHAT_APP_ID`、`WECHAT_APP_SECRET`
3. 如需真实打卡提醒投递，配置订阅消息模板：`WECHAT_REMINDER_TEMPLATE_ID`
4. 初始化表结构：`python backend/scripts/init_mysql_schema.py`
5. 已有数据库升级结构：`python backend/scripts/apply_schema_updates.py`
6. 启动服务：`backend/start.bat`
7. 订阅消息调度任务：进入 `backend` 后由 cron/计划任务周期执行 `python scripts/dispatch_reminders.py`

## 快速验证
- 后端主链回归：进入 `backend` 后执行 `pytest test_v2_core_reading.py test_v2_store_reading.py test_v2_e2e_flow.py test_v2_profile.py -q`
- 前端状态一致性：在项目根目录执行 `node scripts/check_frontend_state.js`
- REST 接口落地矩阵：见 `team/api-rest-migration.md`
- 小程序功能与页面流转检查：见 `team/user-flow-check.md`

## 阿里云 Docker 部署
- 部署说明：见 `backend/deploy_guide.md`。
- 当前未备案域名 `www.nizaina.com` 在大陆云服务器会被拦截，开发联调先使用 `http://47.99.240.126:18080/api/v2`。
- Windows 一键同步并部署：`powershell -ExecutionPolicy Bypass -File backend\scripts\sync_to_aliyun.ps1 -Server 47.99.240.126 -User root`
- 云端手动部署：进入 `/opt/you-where-backend` 后执行 `sudo sh scripts/cloud_deploy.sh`。
- 正式小程序上线前仍必须补齐“已备案域名 + HTTPS + 微信后台 request 合法域名”。

## 登录能力
- 小程序首页提供微信一键登录与手机号登录两种入口。
- 真实微信登录和手机号登录依赖后端环境变量 `WECHAT_APP_ID`、`WECHAT_APP_SECRET`。
- 本地开发者工具或本地 API 地址会发送 `debug_open_id`，用于不接入微信后台时联调。
- 手机号登录使用小程序 `getPhoneNumber` 返回的 `code`，后端通过微信 `getuserphonenumber` 接口换取手机号。
- 测试用户不展示在小程序界面；如需本地绑定测试，可在后端测试环境启用 `ENABLE_TEST_USERS=1` 后调用 `POST /api/v2/auth/test-login`。
- 测试用户会和真实用户一样写入 `users`、`sessions`，绑定后写入正式配对链路；MySQL/生产环境默认关闭测试用户入口。
- 云端开发如只需要让真实用户绑定测试用户，可执行 `docker compose exec backend python scripts/seed_test_users.py` 写入隐藏测试用户；固定共读码为 `900001` / `900002`。

## 书城能力
- 书城默认使用本地中文分类书库，支持国外名著、历史、心学、玄学术数、中医经络、国学经典等分类。
- `GET /api/v2/store/books` 支持 `query`、`page`、`category` 查询参数。
- Gutendex 外部英文书库同步默认关闭；如确需开启，设置环境变量 `STORE_ENABLE_NETWORK=1`。

## 打卡提醒
- 前端保存提醒时会在存在 `WECHAT_REMINDER_TEMPLATE_ID` 的情况下申请微信订阅消息授权。
- 后端 `/api/v2/users/me/reminder-config` 会返回投递状态、模板 ID 和用户可读提示。
- `backend/scripts/dispatch_reminders.py` 负责按用户时区、提醒时间和每日幂等日志发送订阅消息。
- 微信模板字段需与脚本中的 `thing1`、`time2`、`thing3` 保持一致；如果实际模板字段不同，需要先调整脚本再上线。

## 目录约定
- `backend/api/v2`：接口层
- `backend/service`：业务层
- `backend/repo`：数据访问层
- `backend/common`：公共基础设施
- `services/api`：小程序 API 领域模块，统一由 `services/api.js` 汇总导出
- `scripts`：小程序侧轻量验证脚本
- `services`：小程序 API 调用聚合

## 编码说明
- 仓库文本文件统一按 `UTF-8` 维护。
- 在 Windows PowerShell 中直接执行 `Get-Content 文件名` 可能会把 UTF-8 中文误读为本地编码，表现为乱码。
- 建议读取命令改为：`Get-Content -Encoding utf8 文件名`
- 当前项目已增加 `.editorconfig` 约束，后续新增或修改文本文件时应继续保持 `UTF-8`。
