# Task2: Сервис отчётов и витрина данных

Текущая реализация отражает срез Task2; в следующих заданиях архитектура расширяется и эволюционирует (CDC-контур, S3/CDN и другие компоненты).

## Что сделано

- Подготовлена архитектурная схема контура отчётности: пользовательский запрос отчёта, API-слой, ETL-процесс и OLAP-витрина.
- Реализован ETL-процесс в Airflow с запуском по расписанию и загрузкой агрегированных данных в ClickHouse.
- Реализован endpoint `GET /reports` в `report-api` с чтением подготовленных данных из OLAP.
- Добавлено ограничение доступа: отчёт доступен только для текущего аутентифицированного пользователя.
- В UI добавлена кнопка получения отчёта через BFF (`bionicpro-auth`).

## Пояснение по эволюции архитектуры

- В последующих заданиях архитектура была расширена: CRM-часть перенесена в CDC-контур (`Debezium -> Kafka -> ClickHouse`), а Airflow оставлен для телеметрии.
- При этом контракт доступа для отчётов из Task2 сохранён: отчёт доступен только авторизованному пользователю и только по собственному `user_key`.

## Где лежит

- Диаграмма (draw.io): [`Task2_reporting_architecture.drawio.xml`](./Task2_reporting_architecture.drawio.xml)
- Диаграмма (PNG): [`diagram.png`](./diagram.png)
- DAG Airflow: [`../airflow/dags/bionicpro_report_mart_dag.py`](../airflow/dags/bionicpro_report_mart_dag.py)
- DDL витрины ClickHouse: [`../clickhouse/initdb/001_reports_mart.sql`](../clickhouse/initdb/001_reports_mart.sql)
- API чтения отчёта: [`../report-api/app/main.py`](../report-api/app/main.py)
- BFF-прокси отчёта: [`../bionicpro-auth/app/main.py`](../bionicpro-auth/app/main.py)
- UI-кнопка отчёта: [`../frontend/src/components/ReportPage.tsx`](../frontend/src/components/ReportPage.tsx)

## Диаграмма

![Task2 architecture diagram](./diagram.png)
