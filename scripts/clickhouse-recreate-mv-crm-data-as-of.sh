#!/usr/bin/env bash
# Одноразово для уже существующего тома clickhouse-data: пересоздать MV без now() в data_as_of.
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose exec -T clickhouse clickhouse-client --multiquery <<'SQL'
DROP VIEW IF EXISTS reports.mv_crm_to_user_report_mart_cdc;

CREATE MATERIALIZED VIEW reports.mv_crm_to_user_report_mart_cdc
TO reports.user_report_mart_cdc
AS
SELECT
    c.user_key AS user_key,
    coalesce(t.prosthesis_uptime_hours, 0.0) AS prosthesis_uptime_hours,
    toUInt32(coalesce(t.training_sessions, 0)) AS training_sessions,
    toUInt32(coalesce(t.battery_cycles, 0)) AS battery_cycles,
    c.crm_segment AS crm_segment,
    coalesce(t.telemetry_data_as_of, now64(3)) AS data_as_of
FROM
(
    SELECT
        user_key,
        argMax(segment, updated_at) AS crm_segment
    FROM reports.crm_clients_current
    WHERE deleted = 0
    GROUP BY user_key
) AS c
LEFT JOIN
(
    SELECT
        user_key,
        argMax(prosthesis_uptime_hours, data_as_of) AS prosthesis_uptime_hours,
        argMax(training_sessions, data_as_of) AS training_sessions,
        argMax(battery_cycles, data_as_of) AS battery_cycles,
        max(data_as_of) AS telemetry_data_as_of
    FROM reports.telemetry_agg_mart
    GROUP BY user_key
) AS t
ON t.user_key = c.user_key;
SQL

echo "reports.mv_crm_to_user_report_mart_cdc recreated."
