CREATE DATABASE IF NOT EXISTS reports;

CREATE TABLE IF NOT EXISTS reports.user_report_mart
(
    user_key String,
    prosthesis_uptime_hours Float64,
    training_sessions UInt32,
    battery_cycles UInt32,
    crm_segment String,
    data_as_of DateTime64(3, 'UTC')
)
ENGINE = MergeTree
ORDER BY user_key;
