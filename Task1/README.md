# Task1: Безопасная аутентификация и контур доступа

Текущая реализация отражает срез Task1; в следующих заданиях архитектура расширяется и эволюционирует (витрина отчётности, S3/CDN, CDC-контур).

## Что сделано

- Реализован BFF `bionicpro-auth`: OAuth2 Authorization Code + PKCE (`S256`) на сервере, хранение сессии в `HttpOnly` cookie, refresh access token и ротация `session_id`.
- Убран обмен токенами IdP на фронтенде: `frontend` работает через cookie-сессию BFF.
- Защищён `report-api`: валидация JWT через JWKS Keycloak.
- Подключен OpenLDAP и настроена федерация в Keycloak с маппингом групп в роли.
- Включена обязательная OTP/MFA-аутентификация в Keycloak.
- Добавлен вход через Яндекс ID (Identity Brokering) и сценарий согласия на сохранение профиля пользователя.

## Важно для запуска

- Для локального dev-стенда используется `SESSION_COOKIE_SECURE=false`, так как запуск идёт по `http://localhost` (без TLS).
- Для защищённого контура (prod/демо по HTTPS) нужно включать `SESSION_COOKIE_SECURE=true`.
- Настройка Яндекс IdP выполняется отдельным шагом после старта Keycloak: `python3 scripts/configure_yandex_idp.py`.

## Где лежит

- Диаграмма (draw.io): [`BionicPRO_C4_model.drawio.xml`](./BionicPRO_C4_model.drawio.xml)
- Диаграмма (PNG): [`BionicPRO_C4_model.drawio.png`](./BionicPRO_C4_model.drawio.png)
- BFF аутентификации и сессий: [`../bionicpro-auth/app/main.py`](../bionicpro-auth/app/main.py)
- API отчётов (проверка JWT): [`../report-api/app/main.py`](../report-api/app/main.py)
- Конфигурация realm/OTP/клиентов: [`../keycloak/realm-export.json`](../keycloak/realm-export.json)
- LDAP-конфигурация пользователей и групп: [`../ldap/config.ldif`](../ldap/config.ldif)
- Скрипт конфигурации Яндекс ID: [`../scripts/configure_yandex_idp.py`](../scripts/configure_yandex_idp.py)
- Инфраструктура сервисов: [`../docker-compose.yaml`](../docker-compose.yaml)

## Диаграмма

![Task1 security architecture diagram](./BionicPRO_C4_model.drawio.png)
