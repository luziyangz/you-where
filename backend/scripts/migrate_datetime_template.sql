-- 时间字段迁移模板（未执行 — 实施前阅读 datetime_migration_eval.md）
-- 按表单次执行；生产前在从库验证 STR_TO_DATE 结果。

-- USE you_where;

-- ========== 示例：books ==========
-- ALTER TABLE books ADD COLUMN created_at_dt DATETIME(3) NULL AFTER created_at;
-- UPDATE books SET created_at_dt = STR_TO_DATE(
--   REPLACE(REPLACE(created_at, 'T', ' '), 'Z', ''),
--   '%Y-%m-%d %H:%i:%s'
-- ) WHERE created_at IS NOT NULL AND LENGTH(created_at) >= 19;
-- -- 校验: SELECT COUNT(*) FROM books WHERE created_at IS NOT NULL AND created_at_dt IS NULL;
-- -- ALTER TABLE books DROP COLUMN created_at;
-- -- ALTER TABLE books CHANGE created_at_dt created_at DATETIME(3) NOT NULL;

-- 其余表见 datetime_migration_eval.md 第 2 节表清单，复制上述模式逐表处理。
