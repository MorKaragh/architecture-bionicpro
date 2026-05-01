# BionicPRO — отчёт для ревью (Task1-Task4)

Ниже собраны скриншоты, подтверждающие выполнение заданий 1–4:

- проверка API/health и функциональных запросов;
- логин-контур (Keycloak, 2FA, Яндекс);
- отчёты через CDN (MISS/HIT);
- ETL/CDC (Airflow DAG и данные витрины).

---

## Task 1 — Auth / BFF / Keycloak

Демонстрируется:
- доступность auth-контура и базовых эндпоинтов;
- успешный вход через Keycloak;
- прохождение 2FA;
- дополнительный сценарий входа через Яндекс.

### API-запросы Task 1
![Task1 requests part 1](./report/task_1_requests_1.png)
![Task1 requests part 2](./report/task_1_requests_2.png)

### UI: логин и 2FA
![Login screen](./report/login_screen.png)
![2FA screen](./report/2FA_screen.png)

### UI: вход через Яндекс
![Yandex login step 1](./report/yandex_login_1.png)
![Yandex login step 2](./report/yandex_login_2.png)
![Yandex login step 3](./report/yandex_login_3.png)

---

## Task 2 — Report API и витрина данных

Демонстрируется:
- работоспособность запросов к отчетному API;
- наличие данных в витрине для формирования отчётов.

### API-запросы Task 2
![Task2 requests part 1](./report/task_2_requests_1.png)
![Task2 requests part 2](./report/task_2_requests_2.png)

---

## Task 3 — MinIO + CDN cache

Демонстрируется:
- получение отчёта по ссылке через CDN;
- кэширование отчёта (`MISS` на первом запросе, `HIT` на повторном).

### API-запросы Task 3
![Task3 requests](./report/task_3_requests_1.png)

### Проверка кэша CDN
![Cache miss](./report/cache_miss.png)
![Cache hit](./report/cache_hit.png)

---

## Task 4 — CDC / Kafka Connect / ClickHouse

Демонстрируется:
- работоспособность CDC-цепочки в запросах;
- актуализация витрины;
- успешные прогоны DAG в Airflow.

### API-запросы Task 4
![Task4 requests part 1](./report/task_4_requests_1.png)
![Task4 requests part 2](./report/task_4_requests_2.png)

### Airflow DAG
![DAG overview](./report/DAG_screen.png)
![DAG details](./report/DAG_details_screen.png)

---

## Дополнительно — стабильность smoke

Скриншот успешного smoke после запуска окружения:

![Smoke tests](./report/smoke_tests.png)
