# Задание 1 — BionicPRO: SSO, BFF, LDAP, MFA, Яндекс ID

## Схема (C4)

![Диаграмма BionicPRO C4](./BionicPRO_C4_model.drawio.png)

Исходник: `BionicPRO_C4_model.drawio.xml` (draw.io).

## Что сделано

- **BFF `bionicpro-auth`**: OAuth2 Authorization Code + PKCE (`S256`), обмен кода на сервере; сессия в HttpOnly-cookie; refresh access token; ротация `session_id`; CORS к фронту.
- **`report-api`**: `/reports` за JWT (JWKS Keycloak), без токенов IdP во фронте.
- **`frontend`**: только cookie-сессия BFF, редирект на `/auth/login` BFF.
- **Keycloak** (`keycloak/realm-export.json` + образ с [keycloak-russian-providers](https://github.com/playa-ru/keycloak-russian-providers)): realm `reports-realm`, клиент `bionicpro-auth`, **обязательный OTP** после пароля.
- **OpenLDAP**: пользователи/группы из `ldap/config.ldif`, федерация в Keycloak, маппинг групп → роли `user` / `prothetic_user`.
- **`profile-api` + PostgreSQL `app_db`**: профиль после UserInfo; для Яндекса — страница согласия `/auth/yandex-consent`.
- **Яндекс ID**: провайдер `yandex`, настройка скриптом `scripts/configure_yandex_idp.py` (`make configure-yandex`).

Подробности запуска и переменных — в [README в корне репозитория](../README.md).

## Как повторить проверку (тестовый путь)

1. **Поднять стек** (из корня репозитория):

   ```bash
   make up
   ```

   Дождаться готовности сервисов на портах 3000, 8000–8002, 8080.

2. **Автоматическая проверка доступности**:

   ```bash
   make smoke
   ```

3. **Сценарий входа и отчёта (основной)**  
   - Открыть `http://localhost:3000` → **Login via bionicpro-auth**.  
   - Войти в Keycloak, например `user1` / `password123` или LDAP `john.doe` / `password`.  
   - При первом входе после сброса данных — настроить **TOTP** (приложение-аутентикатор), затем ввести код.  
   - На фронте нажать **Download Report** — должен прийти JSON отчёта (в теле — владелец = пользователь Keycloak).

4. **Logout**  
   - Выйти через сценарий фронта/BFF; повторный запрос отчёта без сессии не должен выдавать данные авторизованного пользователя.

5. **Яндекс ID (опционально, нужны ключи OAuth)**  
   - В кабинете [Яндекс OAuth](https://oauth.yandex.ru/) указать redirect:  
     `http://localhost:8080/realms/reports-realm/broker/yandex/endpoint`  
   - После `make up`:  
     `export YANDEX_CLIENT_ID=... YANDEX_CLIENT_SECRET=...` → **`make configure-yandex`**.  
   - Снова открыть логин realm → кнопка **Яндекс**; после входа при необходимости — страница согласия на сохранение профиля.

6. **Если менялся `keycloak/realm-export.json`**, а Keycloak уже был с данными: **`make reset-keycloak`**, затем снова `make up` и при использовании Яндекса — повторить п.5.
