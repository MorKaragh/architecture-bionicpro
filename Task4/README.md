# Task4: CDC и разделение нагрузки CRM

## Что сделано

- Реализован CDC-поток изменений CRM: `PostgreSQL (CRM) -> Debezium -> Kafka`.
- Настроен приём CDC в ClickHouse через `KafkaEngine`.
- Подготовлена витрина отчётности в ClickHouse с объединением данных через `MaterializedView`.
- `report-api` переведён на чтение новой витрины `reports.user_report_mart_cdc`.
- Поток телеметрии вынесен в отдельную агрегированную таблицу `reports.telemetry_agg_mart`, которая обновляется Airflow.

## Где лежит

- Диаграмма (draw.io): [`Task4_cdc_architecture.drawio.xml`](./Task4_cdc_architecture.drawio.xml)
- Диаграмма (PNG): [`diagram.png`](./diagram.png)
- DDL ClickHouse (CDC + витрина): [`../clickhouse/initdb/002_cdc_pipeline.sql`](../clickhouse/initdb/002_cdc_pipeline.sql)
- Конфиг Debezium-коннектора: [`../debezium/crm-connector.json`](../debezium/crm-connector.json)
- DAG Airflow (телеметрия): [`../airflow/dags/bionicpro_report_mart_dag.py`](../airflow/dags/bionicpro_report_mart_dag.py)
- API чтения отчёта: [`../report-api/app/main.py`](../report-api/app/main.py)

## Диаграмма

![Task4 CDC diagram](./diagram.png)
