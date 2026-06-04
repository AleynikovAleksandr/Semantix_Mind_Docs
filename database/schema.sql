-- =============================================
-- Document Processing System — DDL
-- Соответствует SQLAlchemy моделям проекта
-- =============================================

-- =============================================
-- РАСШИРЕНИЯ
-- =============================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- нечёткий поиск по тексту
CREATE EXTENSION IF NOT EXISTS vector;    -- pgvector: семантический поиск


-- =============================================
-- 1. ПОЛЬЗОВАТЕЛИ
-- Модель: app/models/user.py → class User
-- =============================================
CREATE TABLE IF NOT EXISTS users (
    id               SERIAL PRIMARY KEY,
    email            VARCHAR(255) UNIQUE NOT NULL,
    hashed_password  VARCHAR(255) NOT NULL,
    full_name        VARCHAR(255),
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    is_superuser     BOOLEAN NOT NULL DEFAULT FALSE,
    rate_limit       INTEGER NOT NULL DEFAULT 100,
    last_login_at    TIMESTAMP WITH TIME ZONE,
    created_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);


-- =============================================
-- 2. API КЛЮЧИ
-- Модель: app/models/api_key.py → class APIKey
-- =============================================
CREATE TABLE IF NOT EXISTS api_keys (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name         VARCHAR(255) NOT NULL,
    key_hash     VARCHAR(255) UNIQUE NOT NULL,
    key_prefix   VARCHAR(20) NOT NULL,
    permissions  JSONB NOT NULL DEFAULT '{"read": true, "write": true, "delete": false}',
    expires_at   TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_keys_user_id   ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash  ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_user_active ON api_keys(user_id, is_active);


-- =============================================
-- 3. ФАЙЛЫ (метаданные загруженных файлов)
-- Модель: app/models/document.py → class File
-- =============================================
CREATE TABLE IF NOT EXISTS files (
    id            SERIAL PRIMARY KEY,
    original_name VARCHAR(500) NOT NULL,
    stored_name   VARCHAR(500) UNIQUE NOT NULL,
    file_path     VARCHAR(1000) NOT NULL,
    file_size     INTEGER NOT NULL,         -- байты
    mime_type     VARCHAR(100) NOT NULL,
    created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);


-- =============================================
-- 4. ДОКУМЕНТЫ
-- Модель: app/models/document.py → class Document
-- =============================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'document_status') THEN
        CREATE TYPE document_status AS ENUM (
            'uploaded',
            'processing',
            'processed',
            'error'
        );
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS documents (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    file_id         INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    status          document_status NOT NULL DEFAULT 'uploaded',
    celery_task_id  VARCHAR(255),
    page_count      INTEGER,
    processing_time FLOAT,                  -- секунды
    error_message   VARCHAR(2000),
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_documents_user_id     ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_documents_status      ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_user_status ON documents(user_id, status);


-- =============================================
-- 5. ОБРАБОТАННЫЕ ТЕКСТЫ (1:1 с документом)
-- Модель: app/models/processed_text.py → class ProcessedText
-- =============================================
CREATE TABLE IF NOT EXISTS processed_texts (
    id             SERIAL PRIMARY KEY,
    document_id    INTEGER UNIQUE NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    raw_text       TEXT,                    -- текст после OCR (сырой)
    cleaned_text   TEXT,                    -- после очистки
    ocr_confidence FLOAT,                   -- уверенность OCR 0–100
    created_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_processed_texts_document_id ON processed_texts(document_id);


-- =============================================
-- 6. ТЕМЫ ДОКУМЕНТА
-- Модель: app/models/theme.py → class DocumentTheme
-- ВАЖНО: в SQLAlchemy используется суррогатный id,
-- но для поиска нужен (document_id, theme_index) — добавляем
-- =============================================
CREATE TABLE IF NOT EXISTS document_themes (
    id           SERIAL PRIMARY KEY,
    document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    theme_label  VARCHAR(500) NOT NULL,
    keywords     TEXT,                       -- JSON-строка со списком ключевых слов
    "order"      INTEGER NOT NULL DEFAULT 0, -- порядковый номер темы (theme_index)
    confidence   FLOAT,
    UNIQUE (document_id, "order")            -- уникальность темы внутри документа
);

CREATE INDEX IF NOT EXISTS idx_document_themes_document_id   ON document_themes(document_id);
CREATE INDEX IF NOT EXISTS idx_document_themes_document_order ON document_themes(document_id, "order");
CREATE INDEX IF NOT EXISTS idx_document_themes_name_trgm
    ON document_themes USING GIN (theme_label gin_trgm_ops);


-- =============================================
-- 7. СЕГМЕНТЫ ТЕМ
-- Модель: app/models/theme.py → class TopicSegment
-- =============================================
CREATE TABLE IF NOT EXISTS topic_segments (
    id           SERIAL PRIMARY KEY,
    theme_id     INTEGER NOT NULL REFERENCES document_themes(id) ON DELETE CASCADE,
    segment_text TEXT NOT NULL,
    start_char   INTEGER,
    end_char     INTEGER,
    "order"      INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_topic_segments_theme_id    ON topic_segments(theme_id);
CREATE INDEX IF NOT EXISTS idx_topic_segments_theme_order ON topic_segments(theme_id, "order");


-- =============================================
-- 8. ЖУРНАЛ ЗАПРОСОВ
-- Модель: app/models/request_log.py → class RequestLog
-- =============================================
CREATE TABLE IF NOT EXISTS request_logs (
    id               SERIAL PRIMARY KEY,
    user_id          INTEGER REFERENCES users(id) ON DELETE SET NULL,
    endpoint         VARCHAR(500) NOT NULL,
    method           VARCHAR(10) NOT NULL,
    status_code      INTEGER NOT NULL,
    response_time_ms FLOAT,
    ip_address       VARCHAR(50),
    created_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_request_logs_user_id ON request_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_request_logs_created ON request_logs(created_at DESC);


-- =============================================
-- 9. ПОЛНОТЕКСТОВЫЙ ПОИСК ПО ДОКУМЕНТАМ
-- GET /api/search/text?q=...
-- =============================================
CREATE TABLE IF NOT EXISTS document_search_index (
    document_id   INTEGER PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
    search_vector TSVECTOR           -- заполняется после OCR в Celery worker
);

-- GIN индекс — быстрый полнотекстовый поиск
CREATE INDEX IF NOT EXISTS idx_document_search_gin
    ON document_search_index USING GIN(search_vector);


-- =============================================
-- 10. ПОИСК ПО ТЕМАМ (полнотекстовый + семантический)
-- GET /api/search/text?q=...   → использует search_vector
-- GET /api/search/semantic?q=... → использует embedding
-- =============================================
CREATE TABLE IF NOT EXISTS topic_search_index (
    -- ссылка на тему через суррогатный id (соответствует нашей ORM модели)
    theme_id      INTEGER PRIMARY KEY REFERENCES document_themes(id) ON DELETE CASCADE,
    document_id   INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    search_vector TSVECTOR,          -- для полнотекстового поиска
    keywords      TEXT[],            -- массив ключевых слов
    embedding     VECTOR(384)        -- вектор эмбеддингов (384 = MiniLM, 768 = mpnet/bert)
);

-- GIN индекс — полнотекстовый поиск по темам
CREATE INDEX IF NOT EXISTS idx_topic_search_gin
    ON topic_search_index USING GIN(search_vector);

-- HNSW индекс — быстрый приближённый поиск по косинусному расстоянию
CREATE INDEX IF NOT EXISTS idx_topic_embedding_hnsw
    ON topic_search_index USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_topic_search_document_id
    ON topic_search_index(document_id);


-- =============================================
-- 11. ИСТОРИЯ ЭКСПОРТОВ
-- (из оригинальной SQL схемы, дополнение)
-- =============================================
CREATE TABLE IF NOT EXISTS user_responses (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER REFERENCES users(id) ON DELETE CASCADE,
    document_id   INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    response_text TEXT,
    created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_responses_user     ON user_responses(user_id);
CREATE INDEX IF NOT EXISTS idx_user_responses_document ON user_responses(document_id);


-- =============================================
-- ТРИГГЕР: auto-update updated_at
-- =============================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS trg_documents_updated_at ON documents;
CREATE TRIGGER trg_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- =============================================
-- КОММЕНТАРИИ
-- =============================================
COMMENT ON TABLE users                IS 'Пользователи системы';
COMMENT ON TABLE api_keys             IS 'API ключи пользователей (JWT альтернатива)';
COMMENT ON TABLE files                IS 'Метаданные загруженных файлов';
COMMENT ON TABLE documents            IS 'Документы, привязанные к пользователю и файлу';
COMMENT ON TABLE processed_texts      IS 'OCR-текст документа (сырой и очищенный), 1:1 с documents';
COMMENT ON TABLE document_themes      IS 'Темы документа, выделенные NLP. order = theme_index';
COMMENT ON TABLE topic_segments       IS 'Текстовые сегменты внутри темы';
COMMENT ON TABLE request_logs         IS 'Журнал HTTP запросов';
COMMENT ON TABLE document_search_index IS 'FTS индекс по тексту документа (tsvector)';
COMMENT ON TABLE topic_search_index   IS 'FTS + векторный индекс по темам (tsvector + pgvector)';
COMMENT ON TABLE user_responses       IS 'История экспортов результатов пользователями';

COMMENT ON COLUMN topic_search_index.embedding IS 'Вектор 384-мерный (MiniLM) или 768-мерный (BERT/mpnet)';
COMMENT ON COLUMN document_themes."order"      IS 'Порядковый номер темы в документе (theme_index)';
