-- 你在哪里 / you-where MySQL 初始化脚本
-- 与 backend/common/models.py 对齐（22 张表）。
-- 新环境：先建库 you_where，再执行本脚本；或使用 apply_schema_updates.py（create_all + 增量补丁）。
-- 真相来源：models.py > 本文件 > apply_schema_updates 增量列

-- ========== 1. 账号与会话 ==========

CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(64) PRIMARY KEY,
    open_id VARCHAR(128) NOT NULL,
    phone_number VARCHAR(32) NULL,
    nickname VARCHAR(64) NOT NULL,
    avatar VARCHAR(512) NOT NULL DEFAULT '',
    join_code VARCHAR(16) NOT NULL,
    agreement_accepted_at VARCHAR(64) NULL,
    created_at VARCHAR(64) NOT NULL,
    reader_options TEXT NULL,
    UNIQUE KEY uq_users_open_id (open_id),
    UNIQUE KEY uq_users_join_code (join_code),
    UNIQUE KEY uq_users_phone_number (phone_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sessions (
    token VARCHAR(256) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    expires_at VARCHAR(64) NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    KEY idx_sessions_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ========== 2. 双人关系 ==========

CREATE TABLE IF NOT EXISTS pairs (
    pair_id VARCHAR(64) PRIMARY KEY,
    user_a_id VARCHAR(64) NOT NULL,
    user_b_id VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    KEY idx_pairs_user_a (user_a_id, status),
    KEY idx_pairs_user_b (user_b_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS active_pair_locks (
    user_id VARCHAR(64) PRIMARY KEY,
    pair_id VARCHAR(64) NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    KEY idx_active_pair_locks_pair (pair_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ========== 3. 共读业务 ==========

CREATE TABLE IF NOT EXISTS books (
    book_id VARCHAR(64) PRIMARY KEY,
    pair_id VARCHAR(64) NOT NULL,
    title VARCHAR(200) NOT NULL,
    author VARCHAR(200) NOT NULL DEFAULT '',
    total_pages INT NOT NULL,
    status VARCHAR(32) NOT NULL,
    catalog_id VARCHAR(64) NULL,
    created_by VARCHAR(64) NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    finished_at VARCHAR(64) NULL,
    KEY idx_books_pair_id (pair_id),
    KEY idx_books_catalog_id (catalog_id),
    KEY idx_books_pair_status (pair_id, status),
    KEY idx_books_pair_created (pair_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS active_book_locks (
    pair_id VARCHAR(64) PRIMARY KEY,
    book_id VARCHAR(64) NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    KEY idx_active_book_locks_book (book_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS book_read_progress (
    user_id VARCHAR(64) NOT NULL,
    book_id VARCHAR(64) NOT NULL,
    last_page INT NOT NULL DEFAULT 1,
    updated_at VARCHAR(64) NOT NULL,
    PRIMARY KEY (user_id, book_id),
    KEY idx_book_read_progress_book (book_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS book_switch_requests (
    request_id VARCHAR(64) PRIMARY KEY,
    pair_id VARCHAR(64) NOT NULL,
    requested_by VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    from_book_id VARCHAR(64) NULL,
    catalog_id VARCHAR(64) NULL,
    title VARCHAR(200) NOT NULL,
    author VARCHAR(200) NOT NULL DEFAULT '',
    total_pages INT NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    responded_at VARCHAR(64) NULL,
    responded_by VARCHAR(64) NULL,
    KEY idx_book_switch_pair_id (pair_id),
    KEY idx_book_switch_requested_by (requested_by),
    KEY idx_book_switch_pair_status (pair_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS entries (
    entry_id VARCHAR(64) PRIMARY KEY,
    book_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    page INT NOT NULL,
    note_content TEXT NOT NULL,
    quote_text TEXT NULL,
    created_at VARCHAR(64) NOT NULL,
    client_request_id VARCHAR(128) NULL,
    KEY idx_entries_book_id (book_id),
    KEY idx_entries_user_id (user_id),
    KEY idx_entries_book_created (book_id, created_at),
    KEY idx_entries_book_user_page (book_id, user_id, page),
    UNIQUE KEY uq_entries_idempotent (book_id, user_id, client_request_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS replies (
    reply_id VARCHAR(64) PRIMARY KEY,
    entry_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    content TEXT NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    KEY idx_replies_entry_id (entry_id),
    KEY idx_replies_entry_created (entry_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS read_marks (
    user_id VARCHAR(64) NOT NULL,
    book_id VARCHAR(64) NOT NULL,
    last_read_at VARCHAR(64) NOT NULL,
    PRIMARY KEY (user_id, book_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ========== 4. 书城 / 内容目录 ==========

CREATE TABLE IF NOT EXISTS catalog_books (
    catalog_id VARCHAR(64) PRIMARY KEY,
    source VARCHAR(32) NOT NULL,
    source_book_id VARCHAR(64) NOT NULL,
    title VARCHAR(200) NOT NULL,
    author VARCHAR(200) NOT NULL DEFAULT '',
    language VARCHAR(32) NOT NULL DEFAULT '',
    cover_url VARCHAR(512) NOT NULL DEFAULT '',
    detail_url VARCHAR(512) NOT NULL DEFAULT '',
    text_url VARCHAR(512) NOT NULL DEFAULT '',
    owner_user_id VARCHAR(64) NULL,
    douban_rating VARCHAR(16) NULL,
    store_category VARCHAR(32) NULL,
    placeholder_pages INT NULL,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    KEY idx_catalog_owner (owner_user_id),
    KEY idx_catalog_store_category (store_category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS catalog_contents (
    catalog_id VARCHAR(64) PRIMARY KEY,
    content_text LONGTEXT NOT NULL,
    content_len INT NOT NULL,
    page_size_chars INT NOT NULL,
    total_pages INT NOT NULL,
    etag VARCHAR(128) NULL,
    last_fetched_at VARCHAR(64) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS catalog_read_progress (
    user_id VARCHAR(64) NOT NULL,
    catalog_id VARCHAR(64) NOT NULL,
    last_page INT NOT NULL DEFAULT 1,
    updated_at VARCHAR(64) NOT NULL,
    PRIMARY KEY (user_id, catalog_id),
    KEY idx_catalog_read_progress_catalog (catalog_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS catalog_favorites (
    user_id VARCHAR(64) NOT NULL,
    catalog_id VARCHAR(64) NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    PRIMARY KEY (user_id, catalog_id),
    KEY idx_catalog_favorites_user_created (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS catalog_reader_marks (
    user_id VARCHAR(64) NOT NULL,
    catalog_id VARCHAR(64) NOT NULL,
    page INT NOT NULL,
    para_index INT NOT NULL,
    style VARCHAR(16) NOT NULL,
    note TEXT NOT NULL,
    text_snap VARCHAR(512) NOT NULL DEFAULT '',
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    PRIMARY KEY (user_id, catalog_id, page, para_index),
    KEY idx_catalog_reader_marks_catalog_user (catalog_id, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ========== 5. 个人设置与运营 ==========

CREATE TABLE IF NOT EXISTS reading_goals (
    user_id VARCHAR(64) PRIMARY KEY,
    period_days INT NOT NULL DEFAULT 30,
    target_books INT NOT NULL DEFAULT 1,
    target_days INT NOT NULL DEFAULT 20,
    updated_at VARCHAR(64) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS reminder_configs (
    user_id VARCHAR(64) PRIMARY KEY,
    enabled INT NOT NULL DEFAULT 1,
    remind_time VARCHAR(8) NOT NULL DEFAULT '21:00',
    timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai',
    updated_at VARCHAR(64) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS reminder_delivery_logs (
    delivery_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    delivery_date VARCHAR(16) NOT NULL,
    status VARCHAR(32) NOT NULL,
    error_message TEXT NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    UNIQUE KEY uq_reminder_delivery_daily (user_id, delivery_date),
    KEY idx_reminder_delivery_user_id (user_id),
    KEY idx_reminder_delivery_user_created (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS feed_posts (
    post_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    entry_id VARCHAR(64) NOT NULL,
    book_title VARCHAR(200) NOT NULL DEFAULT '',
    excerpt TEXT NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'published',
    created_at VARCHAR(64) NOT NULL,
    UNIQUE KEY uq_feed_posts_entry (entry_id),
    KEY idx_feed_posts_created (created_at),
    KEY idx_feed_posts_user (user_id),
    KEY idx_feed_posts_book_title (book_title)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS feed_comments (
    comment_id VARCHAR(64) PRIMARY KEY,
    post_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    content TEXT NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    KEY idx_feed_comments_post_created (post_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ugc_reports (
    report_id VARCHAR(64) PRIMARY KEY,
    reporter_user_id VARCHAR(64) NOT NULL,
    target_type VARCHAR(32) NOT NULL,
    target_id VARCHAR(64) NOT NULL DEFAULT '',
    target_user_id VARCHAR(64) NULL,
    reason_code VARCHAR(32) NOT NULL,
    description TEXT NOT NULL,
    content_snapshot TEXT NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    created_at VARCHAR(64) NOT NULL,
    KEY idx_ugc_reports_created (created_at),
    KEY idx_ugc_reports_reporter (reporter_user_id),
    KEY idx_ugc_reports_target (target_type, target_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
