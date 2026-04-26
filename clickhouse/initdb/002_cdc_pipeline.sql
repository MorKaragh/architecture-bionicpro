CREATE TABLE IF NOT EXISTS reports.crm_clients_cdc_queue
(
    raw_message String
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:29092',
    kafka_topic_list = 'bionicpro.crm.clients',
    kafka_group_name = 'clickhouse-crm-cdc',
    kafka_format = 'JSONAsString',
    kafka_num_consumers = 1,
    kafka_handle_error_mode = 'stream';

CREATE TABLE IF NOT EXISTS reports.crm_clients_current
(
    id Int64,
    user_key String,
    segment String,
    full_name String,
    updated_at DateTime64(3, 'UTC'),
    deleted UInt8
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (user_key, id);

CREATE MATERIALIZED VIEW IF NOT EXISTS reports.mv_cdc_crm_clients_to_current
TO reports.crm_clients_current
AS
WITH
    JSONExtractRaw(raw_message, 'payload') AS payload,
    JSONExtractString(payload, 'op') AS op,
    if(op = 'd', JSONExtractRaw(payload, 'before'), JSONExtractRaw(payload, 'after')) AS state
SELECT
    toInt64OrZero(JSONExtractString(state, 'id')) AS id,
    JSONExtractString(state, 'user_key') AS user_key,
    coalesce(JSONExtractString(state, 'segment'), '') AS segment,
    coalesce(JSONExtractString(state, 'full_name'), '') AS full_name,
    now64(3) AS updated_at,
    if(op = 'd', 1, 0) AS deleted
FROM reports.crm_clients_cdc_queue
WHERE op IN ('c', 'u', 'r', 'd')
  AND state != ''
  AND JSONExtractString(state, 'user_key') != '';

CREATE TABLE IF NOT EXISTS reports.telemetry_agg_mart
(
    user_key String,
    prosthesis_uptime_hours Float64,
    training_sessions UInt32,
    battery_cycles UInt32,
    data_as_of DateTime64(3, 'UTC')
)
ENGINE = MergeTree
ORDER BY user_key;

CREATE TABLE IF NOT EXISTS reports.user_report_mart_cdc
(
    user_key String,
    prosthesis_uptime_hours Float64,
    training_sessions UInt32,
    battery_cycles UInt32,
    crm_segment String,
    data_as_of DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(data_as_of)
ORDER BY user_key;

CREATE MATERIALIZED VIEW IF NOT EXISTS reports.mv_telemetry_to_user_report_mart_cdc
TO reports.user_report_mart_cdc
AS
SELECT
    t.user_key AS user_key,
    t.prosthesis_uptime_hours AS prosthesis_uptime_hours,
    t.training_sessions AS training_sessions,
    t.battery_cycles AS battery_cycles,
    coalesce(c.crm_segment, 'unknown') AS crm_segment,
    t.data_as_of AS data_as_of
FROM reports.telemetry_agg_mart AS t
LEFT JOIN
(
    SELECT
        user_key,
        argMax(segment, updated_at) AS crm_segment
    FROM reports.crm_clients_current
    WHERE deleted = 0
    GROUP BY user_key
) AS c
ON c.user_key = t.user_key;

CREATE MATERIALIZED VIEW IF NOT EXISTS reports.mv_crm_to_user_report_mart_cdc
TO reports.user_report_mart_cdc
AS
SELECT
    c.user_key AS user_key,
    coalesce(t.prosthesis_uptime_hours, 0.0) AS prosthesis_uptime_hours,
    toUInt32(coalesce(t.training_sessions, 0)) AS training_sessions,
    toUInt32(coalesce(t.battery_cycles, 0)) AS battery_cycles,
    c.crm_segment AS crm_segment,
    now64(3) AS data_as_of
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
        argMax(battery_cycles, data_as_of) AS battery_cycles
    FROM reports.telemetry_agg_mart
    GROUP BY user_key
) AS t
ON t.user_key = c.user_key;
