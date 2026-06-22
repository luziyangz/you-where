# MySQL 全表业务实现与压测 rollout 计划

> 目标：**18 张业务表**均有可验证的业务路径；生产使用 MySQL；每阶段「实现 → MySQL 集成测 → k6 压测」不跳步。

## 执行顺序

| 阶段 | 域 | 表 | 实现/补齐 | MySQL 测试 | k6 压测 |
|------|-----|-----|-----------|------------|---------|
| 0 | 基础设施 | 全部 | `mysql_init.sql`、`tests_mysql/`、`docker-compose.test.yml` | 连通 + 建表 | — |
| 1 | 账号会话 | `users`, `sessions` | 登录、资料、token | `tests_mysql/test_phase1_account.py` | `loadtest/phase1_auth.js` |
| 2 | 双人关系 | `pairs`, `active_pair_locks` | 绑定/解绑/锁 | `test_phase2_pair.py` | `loadtest/phase2_pair.js` |
| 3 | 共读核心 | `books`, `active_book_locks`, `book_switch_requests`, `entries`, `replies`, `read_marks` | 三态、换书、未读 | `test_phase3_reading.py` | `loadtest/phase3_reading.js` |
| 4 | 书城 | `catalog_*` 六表 | 导入/阅读/收藏/划重点 | `test_phase4_catalog.py` | `loadtest/phase4_store.js` |
| 5 | 运营设置 | `reading_goals`, `reminder_configs`, `reminder_delivery_logs` | 目标统计 + 投递日志 | `test_phase5_settings.py` | `loadtest/phase5_settings.js` |
| 6 | 全量 | 19 表 | 回归脚本 | `run_mysql_regression.*` 全 pytest | `run_loadtest_all.*` |

## 本地命令

```bash
# 启动测试用 MySQL（端口 3307，库 you_where_test）
cd backend
docker compose -f docker-compose.test.yml up -d

# MySQL 集成测试（仅 tests_mysql 目录）
./scripts/run_mysql_regression.sh

# 压测（需先拿到 TOKEN、BOOK_ID、CATALOG_ID）
./scripts/run_loadtest_all.sh
```

## 验收标准

- `tests_mysql/` 全绿（连接生产同版 MySQL 8 + utf8mb4）
- k6 各阶段：`http_req_failed < 1%`，`p(95) < 800ms`（局域网/预发）
- `team/database-schema.md` 业务规则与代码一致

## 当前实现状态（2026-05-22）

| 项 | 状态 |
|----|------|
| `tests_mysql/` 阶段 0–5 + 表覆盖登记 | 已实现 |
| `scripts/run_mysql_regression.*`、`check_mysql_test_env.py` | 已实现 |
| `scripts/loadtest/phase1–5.js` + `run_loadtest_all.*` | 已实现 |
| `reminder_delivery_logs` | `reminder_delivery_service` + `dispatch_reminders.py` |
| 本机 MySQL 实测全绿 | **已通过**（13 项 `tests_mysql/`，含导入/解绑/reader_options） |
| 解绑业务规则 | `delete_current_pair` 将在读书标 `switched` |
| k6 分阶段压测记录 | **待执行** |

### 测试 skip 说明（非云部署导致）

集成测默认连 **本机 127.0.0.1:3307** 测试库，与云 API 无关。若 `pytest tests_mysql/` 大量 skip，通常是 **本机 Docker Desktop 未启动** 或测试容器未 up。运行 `python scripts/check_mysql_test_env.py` 诊断。
