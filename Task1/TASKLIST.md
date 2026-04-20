# Task1 — План выполнения (чек-лист)

Состояние на сессию: **основной контур SSO + BFF + демо-отчёт работает** (`make up`, логин `user1`, кнопка отчёта возвращает JSON). Ниже — что уже закрыто и что осталось.

---

## 0) Подготовка и фиксация текущего состояния

- [x] Финальная схема: `Task1/BionicPRO_C4_model.drawio.xml` (и экспорт PNG при необходимости).
- [x] В репозитории: единый `docker-compose.yaml`, `Makefile`, `scripts/task1-smoke.sh`, `README.md`.
- [x] В `.gitignore` добавлены backup draw.io (`.$*.bkp`).
- [ ] Перед сдачей курса: убрать из коммита лишние `.bkp`, проверить опечатки на схеме (iOS, Airflow и т.д.).

---

## 1) Задача 1 — Архитектурное решение и C4

- [x] На схеме отражены BFF, Keycloak, внешние учётные системы, витрина/ETL (по вашей финальной версии).
- [x] Политика: токены IdP не во фронте; сессия через cookie (согласовано с реализацией).
- [ ] Финальный проход: схема ↔ код (имена сервисов, порты 3000 / 8000 / 8080 / 8001).

---

## 2) Задача 2 — PKCE

- [x] Клиент `bionicpro-auth` в Keycloak: Authorization Code + PKCE (`S256`), обмен кода на сервере (`bionicpro-auth`).
- [x] Фронт не использует `keycloak-js`; редирект на `/auth/login` BFF.
- [ ] Убедиться в админке Keycloak, что у клиента `bionicpro-auth` включён нужный flow и redirect `http://localhost:8000/auth/callback` (после любого `reset-keycloak`).

---

## 3) Задача 3 — `bionicpro-auth` и сессии

- [x] Сервис `bionicpro-auth` (FastAPI): `/auth/login`, `/auth/callback`, `/auth/me`, `/auth/logout`, прокси `GET /reports` → `report-api`.
- [x] Токены не отдаются в браузер; сессия: cookie `HttpOnly`, локально `Secure=false`, `SameSite=lax`.
- [x] Хранение `access`/`refresh` в памяти процесса, привязка к `session_id`; обновление access по `refresh`; ротация session id на `/auth/me` и `/reports`.
- [x] `state` + PKCE verifier в коротких HttpOnly-cookie (устойчивый OAuth callback).
- [x] CORS для `FRONTEND_BASE_URL` + `credentials`.
- [x] Разделение URL Keycloak: `KEYCLOAK_PUBLIC_URL` (браузер) / `KEYCLOAK_INTERNAL_URL` (сервер).
- [x] `report-api`: проверка JWT по JWKS (не introspection), переменная `KEYCLOAK_EXPECTED_ISS` при смене хоста.
- [ ] Production: Redis/шифрование для refresh, `Secure=true`, HTTPS; при необходимости вынести секреты из compose.

---

## 4) Задача 4 — LDAP

- [x] Контейнер `ldap` в `docker-compose`, данные из `ldap/config.ldif`.
- [ ] В Keycloak: User Federation → LDAP (хост `ldap`, порт 389), тест входа LDAP-пользователем.
- [ ] Маппинг ролей представительств (как в задании).

---

## 5) Задача 5 — MFA (OTP)

- [ ] В `realm-export.json` есть задел (required action `CONFIGURE_TOTP`); нужно довести в админке: OTP policy, обязательность для realm/потока.
- [ ] Проверка входа с Google Authenticator / FreeOTP.

---

## 6) Задача 6 — Яндекс ID

- [ ] Identity Provider в Keycloak + приложение в кабинете Яндекса (`client_id` / `secret`, redirect).
- [ ] Согласие на профиль + сохранение полей в БД (отдельный сервис/таблица).

---

## 7) Финальная проверка перед сдачей

- [x] Smoke: `make smoke` (с ретраями Keycloak).
- [x] Сценарий: логин → отчёт JSON с `report_owner` = пользователь Keycloak.
- [ ] Logout и повторная проверка, что без сессии отчёт недоступен.
- [ ] LDAP, MFA, Яндекс — по подпунктам выше.
- [ ] Текст для отчёта курса: 1–2 абзаца про BFF, PKCE, cookie, ротацию сессии.

---

## Подсказки для следующей сессии

1. **Смена `realm-export.json` не подхватывается** — Keycloak пишет «Realm already exists». Использовать `make reset-keycloak` (очистка volume через alpine-контейнер в `Makefile`).
2. **401 на отчёте** — чаще всего не пересобран `report-api` после смены проверки токена; реже не совпал `iss` → задать `KEYCLOAK_EXPECTED_ISS` для `report-api`.
3. **Редирект на `keycloak:8080`** — в браузере должен быть только `KEYCLOAK_PUBLIC_URL` (`http://localhost:8080`).
4. **Следующий логичный шаг по Task1** — LDAP federation в UI Keycloak, затем MFA, затем Яндекс + БД профиля.
5. **Task2+** — заменить демо-тело `/reports` в `report-api` на чтение из ClickHouse после появления витрины и Airflow.
