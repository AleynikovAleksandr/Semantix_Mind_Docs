-- =============================================
-- Document Processing System — init script
-- 1) Подключение к maintenance БД
-- 2) Создание базы данных
-- 3) Переключение на неё
-- 4) Применение схемы и seed-данных
-- =============================================

-- Метод 1: подключение к системной БД postgres
\connect postgres;

-- Метод 2: создание базы данных
-- ВАЖНО: если база уже существует, команда вернёт ошибку "already exists".
-- Для повторного запуска используйте: DROP DATABASE docprocessing; CREATE DATABASE docprocessing;
CREATE DATABASE docprocessing;

-- Переключение на созданную БД
\connect docprocessing;

-- Подключаем полный CREATE-скрипт
\i database/schema.sql

-- Базовые данные (пример admin пользователя)
INSERT INTO users (email, hashed_password, full_name, is_active, is_superuser, rate_limit)
VALUES ('admin@semantix.local', '$2b$12$examplehashreplace', 'System Admin', TRUE, TRUE, 1000)
ON CONFLICT (email) DO NOTHING;
