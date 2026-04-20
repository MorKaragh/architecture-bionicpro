# BionicPRO Architecture Course

Краткая инструкция для запуска реализации Task1 (SSO hardening + BFF).

## Что реализовано

- `bionicpro-auth` (BFF): login/callback/logout, хранение сессии в cookie, refresh access token, ротация `session_id`.
- `report-api`: защищенный endpoint `/reports`, проверка JWT по JWKS Keycloak (подпись + `iss` из `KEYCLOAK_EXPECTED_ISS`).
- `frontend`: работает только через `bionicpro-auth` cookie (без хранения токенов Keycloak в браузере).
- `Keycloak`: realm импортируется из `keycloak/realm-export.json`, настроены клиенты и PKCE, **обязательный TOTP (OTP)**: в потоке `forms` после пароля идёт шаг `auth-otp-form`; для новых пользователей включено required action **Configure OTP** (`defaultAction`).
- `OpenLDAP`: пользователи и группы в `ldap/config.ldif` (база `dc=bionicpro,dc=local`). В Keycloak включена федерация **ldap-bionicpro** (`ldap://ldap:389`), маппинг групп LDAP `cn=user` / `cn=prothetic_user` → realm roles `user` / `prothetic_user`. После `make reset-keycloak` при первом входе LDAP-пользователь импортируется автоматически; при необходимости синхронизация: **User federation → ldap-bionicpro → Synchronize all users**.
- **`profile-api` + PostgreSQL (`app_db`)**: таблица профилей пользователя; после входа BFF забирает **UserInfo** Keycloak и сохраняет JSON; для пользователей с атрибутами Яндекса показывается страница **согласия** `/auth/yandex-consent`, затем фиксируется `consent_given_at`.
- **Яндекс ID**: образ Keycloak собирается с JAR **[keycloak-russian-providers](https://github.com/playa-ru/keycloak-russian-providers)** (`ru.playa.keycloak:keycloak-russian-providers:26.0.0.rsp`) и его runtime-зависимостями **`json-path` / `json-smart` / `accessors-smart`** (см. `keycloak/Dockerfile`) — иначе при маппинге атрибутов возможен `NoClassDefFoundError: com.jayway.jsonpath.JsonPath`. Провайдер **`yandex`** (OAuth2 к API Яндекса, без навязывания scope `openid`). Настройка: `scripts/configure_yandex_idp.py` / `make configure-yandex`. Redirect URI в кабинете Яндекса: `http://localhost:8080/realms/reports-realm/broker/yandex/endpoint` (при другом хосте замените префикс на свой `KEYCLOAK_PUBLIC_URL`).

## Быстрый старт

```bash
make up
```

Сервисы:

- Frontend: `http://localhost:3000`
- bionicpro-auth: `http://localhost:8000`
- report-api: `http://localhost:8001`
- profile-api: `http://localhost:8002`
- Keycloak: `http://localhost:8080` (admin/admin)
- LDAP: `ldap://localhost:389`

## Быстрая проверка

```bash
make smoke
```

Если менялся `keycloak/realm-export.json`, а Keycloak уже был запущен ранее, примените пересоздание dev-данных realm:

```bash
make reset-keycloak
```

### Яндекс ID (Keycloak + приложение OAuth)

1. В [Яндекс OAuth](https://oauth.yandex.ru/) создайте приложение, укажите **Callback URL** (редирект):  
   `http://localhost:8080/realms/reports-realm/broker/yandex/endpoint`
2. Поднимите стек: `make up`.
3. Экспортируйте секреты и выполните (с хоста, Keycloak уже слушает `8080`):

```bash
export YANDEX_CLIENT_ID="..."
export YANDEX_CLIENT_SECRET="..."
make configure-yandex
```

Скрипт создаёт IdP с alias `yandex`, маппит поля `id` и `login` в атрибуты пользователя `yandex_id` / `yandex_login` и добавляет protocol mapper на клиент `bionicpro-auth`, чтобы эти поля попадали в UserInfo.

4. На странице входа Keycloak появится кнопка **«Яндекс»** (под формой логина/пароля). После входа (и TOTP) при первом логине через Яндекс BFF может перенаправить на **`/auth/yandex-consent`** — подтвердите сохранение профиля.

**Кнопки нет?**

- После **`make reset-keycloak`** база Keycloak пересоздаётся, провайдеры из скрипта **сбрасываются** — выполните снова: `export YANDEX_CLIENT_...` и **`make configure-yandex`** (дождитесь готовности Keycloak на `8080`).
- Убедитесь, что скрипт завершился с кодом **0** и в консоли есть строка `Провайдер в Keycloak: ... enabled= True`.
- Смотрите страницу логина **именно realm `reports-realm`** (она открывается при «Login via bionicpro-auth»), не консоль `master`.
- В админке Keycloak: **Identity providers → yandex → включён**, опция вроде *Hide on login page* должна быть **выключена**.
- Ошибка Яндекса **`invalid_scope`** при типе провайдера OpenID Connect в Keycloak: встроенный OIDC-брокер добавляет `openid`; для Яндекса используется провайдер **`yandex`** из `keycloak-russian-providers` (см. `keycloak/Dockerfile`). После смены образа выполните `docker compose up -d --build` и снова `make configure-yandex`.
- После редиректа с Яндекса **`Unexpected error when authenticating with identity provider`**: провайдер ожидает непустой **`default_email`** в ответе `login.yandex.ru/info`. В скрипте задаётся **`defaultScope`: `login:info login:email`**; в [кабинете приложения](https://oauth.yandex.ru/) в разделе доступов должны быть включены **логин/ФИО** и **адрес электронной почты**. Перезапустите `make configure-yandex` и повторите вход. Детали смотрите в логах: `docker compose logs keycloak --tail=100`.

## Логин-поток

1. Откройте `http://localhost:3000`.
2. Нажмите `Login via bionicpro-auth`.
3. Войдите в Keycloak: `user1 / password123` **или** LDAP `john.doe / password`. При **первом** входе после `make reset-keycloak` Keycloak попросит **настроить OTP** (QR в Google Authenticator / FreeOTP / Microsoft Authenticator), затем ввести одноразовый код.
4. После callback вернёт на frontend; кнопка `Download Report` получит отчёт через BFF.

## Важные замечания

- Для локальной разработки cookie выставляется с `SESSION_COOKIE_SECURE=false` (иначе браузер по HTTP не примет cookie).  
  В production нужно `true` и HTTPS.
- В `bionicpro-auth` разделены URL Keycloak: `KEYCLOAK_PUBLIC_URL` (для браузерных redirect, обычно `http://localhost:8080`) и `KEYCLOAK_INTERNAL_URL` (для сервер-сервер запросов, обычно `http://keycloak:8080`).
- Политика OTP (алгоритм, окно, период) задана в realm (`otpPolicy*` в `realm-export.json`).
- Секреты Яндекса не коммитьте; для продакшена вынесите `PROFILE_API_SECRET` и пароли БД из `docker-compose.yaml` в env-файлы.
