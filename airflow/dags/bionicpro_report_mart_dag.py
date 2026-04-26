"""
ETL: PostgreSQL (только телеметрия) → reports.telemetry_agg_mart в ClickHouse.
CRM больше не выгружается массово: CRM-данные поступают через CDC (Debezium → Kafka → ClickHouse).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import clickhouse_connect
import psycopg2
import psycopg2.extras
from airflow import DAG
from airflow.operators.python import PythonOperator


def run_mart_etl() -> None:
    host = os.environ["SOURCES_PG_HOST"]
    user = os.environ["SOURCES_PG_USER"]
    password = os.environ["SOURCES_PG_PASSWORD"]
    dbname = os.environ["SOURCES_PG_DB"]
    port = int(os.environ.get("SOURCES_PG_PORT", "5432"))

    pg = psycopg2.connect(
        host=host,
        user=user,
        password=password,
        dbname=dbname,
        port=port,
    )
    try:
        with pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    t.user_key,
                    COALESCE(SUM(t.uptime_hours), 0)::double precision AS uptime,
                    COALESCE(SUM(t.training_sessions), 0)::bigint AS sessions,
                    COALESCE(SUM(t.battery_cycles), 0)::bigint AS cycles
                FROM telemetry.daily_stats t
                GROUP BY t.user_key
                """
            )
            rows = cur.fetchall()
    finally:
        pg.close()

    now = datetime.now(timezone.utc)
    ch = clickhouse_connect.get_client(
        host=os.environ.get("CLICKHOUSE_HOST", "clickhouse"),
        port=int(os.environ.get("CLICKHOUSE_HTTP_PORT", "8123")),
        username=os.environ.get("CLICKHOUSE_USER", "default"),
        password=os.environ.get("CLICKHOUSE_PASSWORD", ""),
    )
    ch.command("TRUNCATE TABLE reports.telemetry_agg_mart")
    if not rows:
        return

    data = [
        (
            r["user_key"],
            float(r["uptime"]),
            int(r["sessions"]),
            int(r["cycles"]),
            now,
        )
        for r in rows
    ]
    ch.insert(
        "reports.telemetry_agg_mart",
        data,
        column_names=[
            "user_key",
            "prosthesis_uptime_hours",
            "training_sessions",
            "battery_cycles",
            "data_as_of",
        ],
    )


default_args = {
    "owner": "bionicpro",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="bionicpro_report_mart",
    default_args=default_args,
    description="Телеметрия → telemetry_agg_mart (CRM приходит в ClickHouse через Debezium CDC)",
    schedule=timedelta(minutes=5),
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["bionicpro", "reports", "etl"],
) as dag:
    PythonOperator(
        task_id="load_user_report_mart",
        python_callable=run_mart_etl,
    )
