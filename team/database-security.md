# 数据库安全与结构同步

## SQL 注入防护

| 层级 | 做法 |
|------|------|
| 业务 API | **一律**使用 SQLAlchemy `select()` / ORM，用户输入只出现在 `.where(列 == 值)` 或绑定参数中 |
| 书城搜索 | `repo/store_repo.py` 对 `query` 做 `escape_like_pattern`，避免 `%` `_` 被当作通配符 |
| 迁移/脚本 | 动态表名/列名必须经 `common/db_safety.assert_safe_table_name` / `assert_safe_identifier` |
| 禁止 | 将请求参数、文件名等拼进 `text(f"...")` 或裸 `execute` 字符串 |

工具模块：`backend/common/db_safety.py`

## 防误删库 / 整表清空

| 操作 | 防护 |
|------|------|
| `store_repo.clear_catalog()` | 调用前 `assert_destructive_db_allowed()` |
| `tests_mysql` 的 `wipe_*` | 同上，仅 `you_where_test` 等测试库或 `ALLOW_DESTRUCTIVE_DB=1` |
| `migrate_sqlite_to_mysql.py` | 白名单表 + 破坏性库检查 |
| 生产 `you_where` | **默认禁止** 无 WHERE 的全表 `delete()` |

显式放开（慎用）：

```env
ALLOW_DESTRUCTIVE_DB=1
```

## 应用启动与 DDL

- `app_main.create_app()` 仅 `Base.metadata.create_all()`，**不会** `drop_all` 或删库。
- 结构变更走 `scripts/apply_schema_updates.py` 或 `scripts/mysql_init.sql`，DDL 为仓库内写死语句，并经 `assert_static_ddl_sql` 检查禁止 `DROP DATABASE` 等片段。

## 结构同步（模型 ↔ 数据库）

真相来源：`backend/common/models.py`

```bash
cd backend
python scripts/apply_schema_updates.py
# 结束时会打印 Schema sync check: OK / 差异列表
```

新环境 MySQL 推荐：

```bash
mysql ... < scripts/mysql_init.sql
# 或 docker-entrypoint 已挂载该文件
```

若 `Schema sync check` 报缺少列，在预发执行 `apply_schema_updates` 后再发版 API。

## 审计清单（发版前）

1. 新增 SQL 是否仍用 ORM/Core 参数绑定？
2. 是否新增 `text(f"...{user_input}")`？（应拒绝合入）
3. 脚本是否可能在生产库上 `DELETE` 全表？
4. `models.py` 变更后是否已跑 `apply_schema_updates` 并看到 sync OK？
