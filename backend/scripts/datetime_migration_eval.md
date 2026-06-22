# VARCHAR 时间戳 → DATETIME 迁移评估

> 关联文档：[team/database-schema.md](../../team/database-schema.md) 第 7 节  
> 状态：**未实施**（建议 Phase 2，按需执行）

## 1. 现状

`backend/common/models.py` 中时间类字段普遍为 `String(64)`，存 UTC ISO8601 字符串（示例：`2026-05-22T08:30:00Z`）。

**优点**：与早期 SQLite 一致；应用层 `utc_now()` 直接写入；无时区转换歧义。  
**缺点**：无法使用 SQL 原生时间函数；索引范围查询需字符串比较；占用略大。

## 2. 影响范围统计

| 表 | 时间相关列 |
|----|------------|
| users | `agreement_accepted_at`, `created_at` |
| sessions | `expires_at`, `created_at` |
| pairs | `created_at`, `updated_at` |
| active_pair_locks | `created_at` |
| books | `created_at`, `finished_at` |
| active_book_locks | `created_at` |
| book_switch_requests | `created_at`, `responded_at` |
| entries | `created_at` |
| replies | `created_at` |
| read_marks | `last_read_at` |
| catalog_books | `created_at`, `updated_at` |
| catalog_contents | `last_fetched_at` |
| catalog_read_progress | `updated_at` |
| catalog_favorites | `created_at` |
| catalog_reader_marks | `created_at`, `updated_at` |
| reading_goals | `updated_at` |
| reminder_configs | `updated_at` |
| reminder_delivery_logs | `created_at` |

另：`reminder_delivery_logs.delivery_date` 为 `VARCHAR(16)` 日期键（`YYYY-MM-DD`），可保留或改为 `DATE`。

**不涉及时间列的表**：无（19 表中均有至少一个时间/日期字段，除纯内容表外）

## 3. 代码影响面

需同步修改（若迁移）：

- `backend/service/*` 中 `utc_now()` 写入与比较
- `backend/repo/*` 中按时间排序、过滤（`finished_at >= start_iso` 等）
- 测试 fixture 中硬编码 ISO 字符串
- API 响应 JSON（可继续对外输出 ISO 字符串，仅在 DB 层用 DATETIME）

估计改动文件：**15+**，回归测试：`test_v2_*`、`test_v2_store_reading.py`、`test_v2_profile.py`

## 4. 推荐策略

| 阶段 | 做法 |
|------|------|
| **现在** | 不迁移；文档化现状 |
| **新功能** | 新增表优先 `DATETIME(3) NULL` + 应用层统一转换 |
| **批量迁移** | 按表分批：`ALTER` + `UPDATE` 解析 ISO → DATETIME；每表单独回滚脚本 |

## 5. 单表示例迁移 SQL（草案，勿直接生产执行）

```sql
-- 示例：books.created_at
ALTER TABLE books ADD COLUMN created_at_dt DATETIME(3) NULL AFTER created_at;

UPDATE books SET created_at_dt = STR_TO_DATE(
  REPLACE(REPLACE(created_at, 'T', ' '), 'Z', ''),
  '%Y-%m-%d %H:%i:%s'
) WHERE created_at IS NOT NULL AND created_at != '';

-- 校验行数一致后：
-- ALTER TABLE books DROP COLUMN created_at;
-- ALTER TABLE books CHANGE created_at_dt created_at DATETIME(3) NOT NULL;
```

SQLite 开发库与 MySQL 生产语法不同，需 **按 dialect 分支** 或仅生产执行 MySQL 脚本。

## 6. 风险与回滚

| 风险 | 缓解 |
|------|------|
| 非法 ISO 字符串 | 迁移前 `SELECT` 抽查；脏数据先清洗 |
| 停机 | 大表用在线 DDL 或维护窗口 |
| 双写期不一致 | 短期双列 + 应用只写新列 |

回滚：保留 `created_at` 旧列直至验证通过；或从备份恢复。

## 7. 结论

- **不推荐** 在当前 MVP 阶段做全库时间类型切换。
- **推荐** 维持 VARCHAR；在 PRD 进入长期运营、需要复杂时间统计时再按表迁移。
- 若仅 MySQL 生产环境需要，可新建 `scripts/migrate_datetime_books.sql` 等分表脚本，本文件作为规范与检查清单。
