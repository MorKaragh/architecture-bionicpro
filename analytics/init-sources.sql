-- CRM и сырые данные телеметрии (источники для Airflow → витрина ClickHouse).
-- user_key сопоставляется с preferred_username в Keycloak (user1, user2, prothetic1, …).

CREATE SCHEMA IF NOT EXISTS crm;
CREATE SCHEMA IF NOT EXISTS telemetry;

CREATE TABLE IF NOT EXISTS crm.clients (
    id SERIAL PRIMARY KEY,
    user_key TEXT NOT NULL UNIQUE,
    segment TEXT NOT NULL,
    full_name TEXT
);

CREATE TABLE IF NOT EXISTS telemetry.daily_stats (
    id SERIAL PRIMARY KEY,
    user_key TEXT NOT NULL,
    stat_date DATE NOT NULL,
    uptime_hours NUMERIC(12, 2) NOT NULL DEFAULT 0,
    training_sessions INT NOT NULL DEFAULT 0,
    battery_cycles INT NOT NULL DEFAULT 0,
    UNIQUE (user_key, stat_date)
);

INSERT INTO crm.clients (user_key, segment, full_name) VALUES
    ('user1', 'premium', 'Test User One'),
    ('user2', 'standard', 'Test User Two'),
    ('prothetic1', 'standard', 'Prothetic Demo User')
ON CONFLICT (user_key) DO NOTHING;

INSERT INTO telemetry.daily_stats (user_key, stat_date, uptime_hours, training_sessions, battery_cycles) VALUES
    ('user1', CURRENT_DATE - 2, 5.5, 2, 4),
    ('user1', CURRENT_DATE - 1, 6.0, 3, 5),
    ('user2', CURRENT_DATE - 1, 3.0, 1, 2),
    ('prothetic1', CURRENT_DATE - 2, 3.5, 1, 2),
    ('prothetic1', CURRENT_DATE - 1, 4.25, 2, 3)
ON CONFLICT (user_key, stat_date) DO NOTHING;
