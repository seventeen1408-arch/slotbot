-- PRO S2S Postback System Database Migration
-- Добавляет таблицы и поля для полной безопасности

-- ========== Таблица: click_tracking ==========
-- Отслеживание связи между пользователем и click_id
CREATE TABLE IF NOT EXISTS click_tracking (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    click_id VARCHAR(36) NOT NULL UNIQUE,
    partner_name VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_click_id (click_id),
    INDEX idx_user_id (user_id),
    INDEX idx_partner (partner_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ========== Таблица: postback_logs ==========
-- Логирование всех обработанных постбеков (Replay Attack Prevention)
CREATE TABLE IF NOT EXISTS postback_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id VARCHAR(36) NOT NULL UNIQUE,
    partner_name VARCHAR(50) NOT NULL,
    click_id VARCHAR(36),
    event_type VARCHAR(50) NOT NULL,
    amount DECIMAL(10, 2),
    currency VARCHAR(3) DEFAULT 'USD',
    user_id INT,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45),
    status VARCHAR(20) DEFAULT 'success',
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE KEY unique_event (event_id),
    INDEX idx_event_id (event_id),
    INDEX idx_partner (partner_name),
    INDEX idx_user_id (user_id),
    INDEX idx_processed_at (processed_at),
    INDEX idx_click_id (click_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ========== Таблица: postback_audit_logs ==========
-- Полный audit trail для всех операций (Audit Logging)
CREATE TABLE IF NOT EXISTS postback_audit_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    partner_name VARCHAR(50) NOT NULL,
    event_id VARCHAR(36),
    ip_address VARCHAR(45),
    action VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'success',
    details LONGTEXT,
    user_id INT,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_timestamp (timestamp),
    INDEX idx_partner (partner_name),
    INDEX idx_event_id (event_id),
    INDEX idx_action (action),
    INDEX idx_user_id (user_id),
    INDEX idx_timestamp_partner (timestamp, partner_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ========== Обновление таблицы: users ==========
-- Добавляем поля для отслеживания статуса пользователя

-- Проверить и добавить поле click_id
ALTER TABLE users ADD COLUMN IF NOT EXISTS click_id VARCHAR(36) UNIQUE AFTER id;

-- Проверить и добавить поле registered (в казино)
ALTER TABLE users ADD COLUMN IF NOT EXISTS registered BOOLEAN DEFAULT FALSE AFTER click_id;

-- Проверить и добавить поле first_deposited
ALTER TABLE users ADD COLUMN IF NOT EXISTS first_deposited BOOLEAN DEFAULT FALSE AFTER registered;

-- Проверить и добавить поле vip_until (дата окончания VIP)
ALTER TABLE users ADD COLUMN IF NOT EXISTS vip_until TIMESTAMP NULL AFTER first_deposited;

-- Проверить и добавить поле lifetime_value (общая сумма депозитов)
ALTER TABLE users ADD COLUMN IF NOT EXISTS lifetime_value DECIMAL(12, 2) DEFAULT 0 AFTER vip_until;

-- Проверить и добавить поле deposits_count (количество депозитов)
ALTER TABLE users ADD COLUMN IF NOT EXISTS deposits_count INT DEFAULT 0 AFTER lifetime_value;

-- Проверить и добавить поле last_postback_at
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_postback_at TIMESTAMP NULL AFTER deposits_count;

-- Создать индексы для оптимизации
CREATE INDEX IF NOT EXISTS idx_click_id ON users(click_id);
CREATE INDEX IF NOT EXISTS idx_registered ON users(registered);
CREATE INDEX IF NOT EXISTS idx_vip_until ON users(vip_until);
CREATE INDEX IF NOT EXISTS idx_lifetime_value ON users(lifetime_value);

-- ========== Таблица: postback_config ==========
-- Конфигурация партнеров и их IP адреса
CREATE TABLE IF NOT EXISTS postback_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    partner_name VARCHAR(50) NOT NULL UNIQUE,
    allowed_ips TEXT,
    secret_key_hash VARCHAR(255),
    rate_limit_per_minute INT DEFAULT 100,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_partner (partner_name),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ========== Таблица: postback_events ==========
-- История всех событий для аналитики
CREATE TABLE IF NOT EXISTS postback_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    partner_name VARCHAR(50),
    amount DECIMAL(10, 2),
    currency VARCHAR(3) DEFAULT 'USD',
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_event_type (event_type),
    INDEX idx_partner (partner_name),
    INDEX idx_created_at (created_at),
    INDEX idx_user_event (user_id, event_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ========== Вьюхи для аналитики ==========

-- Вьюха: Статистика по партнерам
CREATE OR REPLACE VIEW postback_partner_stats AS
SELECT 
    partner_name,
    COUNT(*) as total_events,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(DISTINCT CASE WHEN event_type = 'register' THEN user_id END) as registrations,
    COUNT(DISTINCT CASE WHEN event_type = 'first_deposit' THEN user_id END) as first_deposits,
    SUM(CASE WHEN event_type IN ('first_deposit', 'deposit') THEN amount ELSE 0 END) as total_deposits,
    AVG(CASE WHEN event_type IN ('first_deposit', 'deposit') THEN amount ELSE NULL END) as avg_deposit,
    MAX(processed_at) as last_event
FROM postback_logs
WHERE status = 'success'
GROUP BY partner_name;

-- Вьюха: Статистика по пользователям
CREATE OR REPLACE VIEW user_postback_stats AS
SELECT 
    u.id,
    u.username,
    u.click_id,
    u.registered,
    u.first_deposited,
    u.vip_until,
    u.lifetime_value,
    u.deposits_count,
    COUNT(DISTINCT pl.event_id) as total_postback_events,
    MAX(pl.processed_at) as last_postback
FROM users u
LEFT JOIN postback_logs pl ON u.id = pl.user_id
GROUP BY u.id;

-- ========== Индексы для оптимизации запросов ==========

-- Оптимизация поиска по timestamp
ALTER TABLE postback_logs ADD INDEX IF NOT EXISTS idx_processed_at_partner (processed_at, partner_name);

-- Оптимизация поиска по статусу
ALTER TABLE postback_logs ADD INDEX IF NOT EXISTS idx_status (status);

-- Оптимизация аудита
ALTER TABLE postback_audit_logs ADD INDEX IF NOT EXISTS idx_timestamp_action (timestamp, action);

-- ========== Процедуры для обслуживания ==========

-- Процедура: Очистка старых логов (старше 90 дней)
DELIMITER //
CREATE PROCEDURE IF NOT EXISTS cleanup_old_postback_logs()
BEGIN
    DELETE FROM postback_logs 
    WHERE processed_at < DATE_SUB(NOW(), INTERVAL 90 DAY);
    
    DELETE FROM postback_audit_logs 
    WHERE timestamp < DATE_SUB(NOW(), INTERVAL 90 DAY);
END //
DELIMITER ;

-- Процедура: Получить статистику по партнеру
DELIMITER //
CREATE PROCEDURE IF NOT EXISTS get_partner_stats(IN p_partner_name VARCHAR(50), IN p_days INT)
BEGIN
    SELECT 
        partner_name,
        COUNT(*) as total_events,
        COUNT(DISTINCT user_id) as unique_users,
        COUNT(DISTINCT CASE WHEN event_type = 'register' THEN user_id END) as registrations,
        COUNT(DISTINCT CASE WHEN event_type = 'first_deposit' THEN user_id END) as first_deposits,
        SUM(CASE WHEN event_type IN ('first_deposit', 'deposit') THEN amount ELSE 0 END) as total_deposits,
        AVG(CASE WHEN event_type IN ('first_deposit', 'deposit') THEN amount ELSE NULL END) as avg_deposit
    FROM postback_logs
    WHERE partner_name = p_partner_name
    AND processed_at >= DATE_SUB(NOW(), INTERVAL p_days DAY)
    AND status = 'success'
    GROUP BY partner_name;
END //
DELIMITER ;

-- ========== Инициализация конфигурации партнеров ==========

-- Добавить примеры партнеров (если не существуют)
INSERT IGNORE INTO postback_config (partner_name, allowed_ips, rate_limit_per_minute, is_active)
VALUES 
    ('1win', '1.2.3.4,5.6.7.8', 100, TRUE),
    ('stake', '10.11.12.13', 50, TRUE),
    ('roobet', '14.15.16.17', 200, TRUE),
    ('localhost', '127.0.0.1,::1', 1000, TRUE);

-- ========== Комментарии для документации ==========

-- click_tracking: Связывает пользователя Telegram с click_id партнера
-- Используется для идентификации пользователя при получении постбека

-- postback_logs: Логирует все обработанные постбеки
-- Используется для Replay Attack Prevention (idempotency)
-- Уникальный event_id гарантирует что событие обработано только один раз

-- postback_audit_logs: Полный audit trail всех операций
-- Используется для безопасности, отладки и соответствия требованиям

-- postback_config: Конфигурация партнеров
-- Хранит IP адреса, secret keys (хешированные), rate limits

-- postback_events: История событий для аналитики
-- Используется для статистики и анализа поведения пользователей
