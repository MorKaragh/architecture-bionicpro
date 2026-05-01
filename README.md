# BionicPRO: архитектура и реализация

Проект реализует единый защищённый контур доступа к отчётам пользователей протезов: аутентификация через Keycloak и BFF, подготовка отчётных витрин, кэширование отчётов в S3/CDN и CDC-поток CRM.

## Статус выполнения

- Выполнено: **Task1, Task2, Task3, Task4**
- Каждое следующее задание расширяет архитектуру предыдущего.

## Кратко о проекте

- `frontend` работает только через `bionicpro-auth` cookie-сессию (без токенов IdP в браузере).
- `bionicpro-auth` реализует PKCE, хранение сессии, refresh токена и проксирование `/reports`.
- `report-api` читает отчётные данные из ClickHouse и использует cache-aside в MinIO.
- `cdn` (Nginx) раздаёт отчёты из MinIO с `proxy_cache`; внешняя ссылка для фронта проходит через BFF (`/reports-cache/*`) для сохранения защищённого контура.
- `Airflow` обновляет витрины по расписанию; CRM-изменения доставляются через Debezium/Kafka/ClickHouse MV.

## Подробности по заданиям

| Задание | Статус | Что реализовано | Подробности |
|---|---|---|---|
| Task1 | ✅ | Безопасная аутентификация, BFF, LDAP, MFA, Яндекс ID | [`Task1/README.md`](./Task1/README.md) |
| Task2 | ✅ | Сервис отчётов и витрина данных (OLAP + Airflow) | [`Task2/README.md`](./Task2/README.md) |
| Task3 | ✅ | S3/MinIO + CDN (Nginx) для снижения нагрузки на OLAP | [`Task3/README.md`](./Task3/README.md) |
| Task4 | ✅ | CDC CRM через Debezium/Kafka и витрина `user_report_mart_cdc` | [`Task4/README.md`](./Task4/README.md) |

## Схемы по заданиям

### Task1

![Task1 diagram](./Task1/BionicPRO_C4_model.drawio.png)

### Task2

![Task2 diagram](./Task2/diagram.png)

### Task3

![Task3 diagram](./Task3/diagram.png)

### Task4

![Task4 diagram](./Task4/diagram.png)

## Быстрый запуск

```bash
make up
```

Чистый старт (сброс локальных томов данных, как после `git clone`): `make up-clean`.

## Быстрая проверка

```bash
make smoke
```

## Операционные проверки

- Яндекс IdP: после `make up` выполнить `python3 scripts/configure_yandex_idp.py`, затем проверить вход через Яндекс в UI.
- CDC-цепочка: проверить путь `Postgres (crm.*) -> Debezium -> Kafka -> ClickHouse (KafkaEngine/MV) -> report-api`.
