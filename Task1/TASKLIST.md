# Task1 — План выполнения (чек-лист)

Состояние на сессию: **SSO + BFF + отчёт + LDAP + TOTP + profile-api + сценарий Яндекс ID (IdP через скрипт, БД профиля)**. Ниже — что уже закрыто и что осталось.

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
- [ ] Финальный проход: схема ↔ код (имена сервисов, порты 3000 / 8000 / 8001 / 8002 / 8080).

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
- [x] В Keycloak: User Federation **ldap-bionicpro** (`ldap://ldap:389`, `ou=People,dc=bionicpro,dc=local`), тест входа (например `john.doe` / `password`).
- [x] Маппинг ролей: LDAP groups `cn=user`, `cn=prothetic_user` → realm roles `user`, `prothetic_user` (mapper `realm-roles-from-ldap-groups` в импорте `realm-export.json`).

---

## 5) Задача 5 — MFA (OTP)

- [x] В `realm-export.json`: политика OTP (`otpPolicy*`), required action `CONFIGURE_TOTP` с `defaultAction: true`, в потоке **Authentication → forms** после пароля добавлен обязательный шаг **OTP Form** (`auth-otp-form` вместо только conditional OTP).
- [x] Локальные пользователи (`user1`, `user2`, `admin1`) с required action `CONFIGURE_TOTP` в импорте; LDAP-пользователи получают default required actions при создании.
- [ ] Ручная проверка: Google Authenticator / FreeOTP — один полный вход и отчёт через фронт.

---

## 6) Задача 6 — Яндекс ID

- [x] Identity Provider в Keycloak: `scripts/configure_yandex_idp.py` / `make configure-yandex` (env `YANDEX_CLIENT_ID`, `YANDEX_CLIENT_SECRET`); redirect в кабинете Яндекса: `http://localhost:8080/realms/reports-realm/broker/yandex/endpoint`.
- [x] Сохранение профиля: `profile-api` + `app_db` (PostgreSQL), upsert из `bionicpro-auth` по UserInfo; страница согласия `/auth/yandex-consent`, колонка `consent_given_at`.
- [ ] Ручная проверка с реальными ключами Яндекса и входом через кнопку Yandex на форме Keycloak.

---

## 7) Финальная проверка перед сдачей

- [x] Smoke: `make smoke` (с ретраями Keycloak).
- [x] Сценарий: логин → отчёт JSON с `report_owner` = пользователь Keycloak.
- [ ] Logout и повторная проверка, что без сессии отчёт недоступен.
- [ ] Ручная проверка: Яндекс-вход (ключи в кабинете) и при необходимости повтор MFA/отчёта.
- [ ] Текст для отчёта курса: 1–2 абзаца про BFF, PKCE, cookie, ротацию сессии.

---

## Подсказки для следующей сессии

1. **Смена `realm-export.json` не подхватывается** — Keycloak пишет «Realm already exists». Использовать `make reset-keycloak` (очистка volume через alpine-контейнер в `Makefile`).
2. **401 на отчёте** — чаще всего не пересобран `report-api` после смены проверки токена; реже не совпал `iss` → задать `KEYCLOAK_EXPECTED_ISS` для `report-api`.
3. **Редирект на `keycloak:8080`** — в браузере должен быть только `KEYCLOAK_PUBLIC_URL` (`http://localhost:8080`).
4. **Яндекс ID**: после `export YANDEX_CLIENT_ID / YANDEX_CLIENT_SECRET` выполнить `make configure-yandex` (Keycloak должен слушать `localhost:8080`). Данные профиля — в PostgreSQL `app_db`, том `./postgres-app-data`.
5. **Если LDAP не применился после рестарта** — проверьте, что в `ldap/config.ldif` используется база `dc=bionicpro,dc=local` (должна совпадать с `LDAP_DOMAIN=bionicpro.local`), затем `make reset-keycloak`.
6. **LDAP-пользователи не появились в Keycloak** — выполните в UI: *User federation → ldap-bionicpro → Synchronize all users* (или дождитесь первого логина пользователя).
7. **Task2+** — заменить демо-тело `/reports` в `report-api` на чтение из ClickHouse после появления витрины и Airflow.
