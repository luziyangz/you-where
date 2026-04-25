-- 你在哪页 MySQL 初始化脚本
-- 说明：用于创建 v2 重构所需核心表和索引。

CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(64) PRIMARY KEY,
    open_id VARCHAR(128) NOT NULL UNIQUE,
    nickname VARCHAR(64) NOT NULL,
    avatar VARCHAR(512) NOT NULL DEFAULT '',
    join_code VARCHAR(16) NOT NULL UNIQUE,
    agreement_accepted_at VARCHAR(64) NULL,
    created_at VARCHAR(64) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sessions (
    token VARCHAR(256) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    expires_at VARCHAR(64) NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    KEY idx_sessions_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

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

CREATE TABLE IF NOT EXISTS books (
    book_id VARCHAR(64) PRIMARY KEY,
    pair_id VARCHAR(64) NOT NULL,
    title VARCHAR(200) NOT NULL,
    author VARCHAR(200) NOT NULL DEFAULT '',
    total_pages INT NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_by VARCHAR(64) NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    finished_at VARCHAR(64) NULL,
    KEY idx_books_pair_status (pair_id, status),
    KEY idx_books_pair_created (pair_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS entries (
    entry_id VARCHAR(64) PRIMARY KEY,
    book_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    page INT NOT NULL,
    note_content TEXT NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    client_request_id VARCHAR(128) NULL,
    KEY idx_entries_book_user (book_id, user_id),
    KEY idx_entries_book_time (book_id, created_at),
    KEY idx_entries_book_user_page (book_id, user_id, page),
    UNIQUE KEY uq_entries_idempotent (book_id, user_id, client_request_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS replies (
    reply_id VARCHAR(64) PRIMARY KEY,
    entry_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    content TEXT NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    KEY idx_replies_entry (entry_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS read_marks (
    user_id VARCHAR(64) NOT NULL,
    book_id VARCHAR(64) NOT NULL,
    last_read_at VARCHAR(64) NOT NULL,
    PRIMARY KEY (user_id, book_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
