-- Демо-строки для отчётов: user_key = preferred_username в Keycloak.
-- Идемпотентно: безопасно вызывать на уже инициализированной sources_db.

INSERT INTO crm.clients (user_key, segment, full_name) VALUES
    ('prothetic1', 'standard', 'Prothetic Demo User')
ON CONFLICT (user_key) DO NOTHING;

INSERT INTO telemetry.daily_stats (user_key, stat_date, uptime_hours, training_sessions, battery_cycles) VALUES
    ('prothetic1', CURRENT_DATE - 2, 3.5, 1, 2),
    ('prothetic1', CURRENT_DATE - 1, 4.25, 2, 3)
ON CONFLICT (user_key, stat_date) DO NOTHING;
