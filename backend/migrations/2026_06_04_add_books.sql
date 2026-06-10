-- =============================================================================
-- Migration: 2026_06_04_add_books.sql
-- 目的：
--   1. 创建 books 表
--   2. 给 chapters / characters / character_relationships / plot_lines /
--      worldbook_entries 添加 book_id 外键（NULL 允许，索引）
--   3. 给每个已有 project 自动插入一个默认 book（"原项目名 - 默认书"）
--   4. 回填所有现有 content 表的 book_id 到对应 project 的默认 book
--   5. （幂等）-- 多次执行时不会重复建表/重复回填
-- =============================================================================

-- 1. 创建 books 表
CREATE TABLE IF NOT EXISTS books (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    project_id  INT          NOT NULL,
    name        VARCHAR(200) NOT NULL,
    description TEXT         NULL,
    order_index INT          NOT NULL DEFAULT 1,
    created_at  DATETIME     NULL,
    updated_at  DATETIME     NULL,
    INDEX ix_books_id (id),
    INDEX ix_books_project_id (project_id),
    CONSTRAINT fk_books_project
        FOREIGN KEY (project_id) REFERENCES novel_projects (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. 给各内容表加 book_id 列（已存在则跳过）
-- MySQL 8.0 不支持 "ADD COLUMN IF NOT EXISTS"，用 INFORMATION_SCHEMA 守护
SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'chapters'
          AND COLUMN_NAME = 'book_id') = 0,
    'ALTER TABLE chapters ADD COLUMN book_id INT NULL, ADD INDEX ix_chapters_book_id (book_id), ADD CONSTRAINT fk_chapters_book FOREIGN KEY (book_id) REFERENCES books (id)',
    'SELECT 1'
));
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'characters'
          AND COLUMN_NAME = 'book_id') = 0,
    'ALTER TABLE characters ADD COLUMN book_id INT NULL, ADD INDEX ix_characters_book_id (book_id), ADD CONSTRAINT fk_characters_book FOREIGN KEY (book_id) REFERENCES books (id)',
    'SELECT 1'
));
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'character_relationships'
          AND COLUMN_NAME = 'book_id') = 0,
    'ALTER TABLE character_relationships ADD COLUMN book_id INT NULL, ADD INDEX ix_character_relationships_book_id (book_id), ADD CONSTRAINT fk_character_relationships_book FOREIGN KEY (book_id) REFERENCES books (id)',
    'SELECT 1'
));
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'plot_lines'
          AND COLUMN_NAME = 'book_id') = 0,
    'ALTER TABLE plot_lines ADD COLUMN book_id INT NULL, ADD INDEX ix_plot_lines_book_id (book_id), ADD CONSTRAINT fk_plot_lines_book FOREIGN KEY (book_id) REFERENCES books (id)',
    'SELECT 1'
));
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'worldbook_entries'
          AND COLUMN_NAME = 'book_id') = 0,
    'ALTER TABLE worldbook_entries ADD COLUMN book_id INT NULL, ADD INDEX ix_worldbook_entries_book_id (book_id), ADD CONSTRAINT fk_worldbook_entries_book FOREIGN KEY (book_id) REFERENCES books (id)',
    'SELECT 1'
));
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 3. 给每个 project 自动创建一个默认 book（"原项目名 - 默认书"）
-- 幂等：跳过那些 project_id 已存在 book 的项目
INSERT INTO books (project_id, name, order_index, created_at, updated_at)
SELECT np.id, CONCAT(np.name, ' - 默认书'), 1, NOW(), NOW()
FROM novel_projects np
WHERE NOT EXISTS (
    SELECT 1 FROM books b WHERE b.project_id = np.id
);

-- 4. 回填：把所有 content 表的 book_id 设为该 project 的第一个 book
UPDATE chapters ch
JOIN (
    SELECT b.id, b.project_id
    FROM books b
    JOIN (
        SELECT project_id, MIN(order_index) AS min_order
        FROM books
        GROUP BY project_id
    ) m ON m.project_id = b.project_id AND m.min_order = b.order_index
) def ON def.project_id = ch.project_id
SET ch.book_id = def.id
WHERE ch.book_id IS NULL;

UPDATE characters c
JOIN (
    SELECT b.id, b.project_id
    FROM books b
    JOIN (
        SELECT project_id, MIN(order_index) AS min_order
        FROM books
        GROUP BY project_id
    ) m ON m.project_id = b.project_id AND m.min_order = b.order_index
) def ON def.project_id = c.project_id
SET c.book_id = def.id
WHERE c.book_id IS NULL;

UPDATE character_relationships cr
JOIN (
    SELECT b.id, b.project_id
    FROM books b
    JOIN (
        SELECT project_id, MIN(order_index) AS min_order
        FROM books
        GROUP BY project_id
    ) m ON m.project_id = b.project_id AND m.min_order = b.order_index
) def ON def.project_id = cr.project_id
SET cr.book_id = def.id
WHERE cr.book_id IS NULL;

UPDATE plot_lines pl
JOIN (
    SELECT b.id, b.project_id
    FROM books b
    JOIN (
        SELECT project_id, MIN(order_index) AS min_order
        FROM books
        GROUP BY project_id
    ) m ON m.project_id = b.project_id AND m.min_order = b.order_index
) def ON def.project_id = pl.project_id
SET pl.book_id = def.id
WHERE pl.book_id IS NULL;

UPDATE worldbook_entries we
JOIN (
    SELECT b.id, b.project_id
    FROM books b
    JOIN (
        SELECT project_id, MIN(order_index) AS min_order
        FROM books
        GROUP BY project_id
    ) m ON m.project_id = b.project_id AND m.min_order = b.order_index
) def ON def.project_id = we.project_id
SET we.book_id = def.id
WHERE we.book_id IS NULL;
