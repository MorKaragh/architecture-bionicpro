# BionicPRO Architecture Course

Краткая инструкция для запуска реализации Task1 (SSO hardening + BFF).

## Что реализовано

- `bionicpro-auth` (BFF): login/callback/logout, хранение сессии в cookie, refresh access token, ротация `session_id`.
- `report-api`: защищенный endpoint `/reports`, проверка JWT по JWKS Keycloak (подпись + `iss` из `KEYCLOAK_EXPECTED_ISS`).
- `frontend`: работает только через `bionicpro-auth` cookie (без хранения токенов Keycloak в браузере).
- `Keycloak`: realm импортируется из `keycloak/realm-export.json`, настроены клиенты и PKCE.
- `OpenLDAP`: поднимается в compose для сценариев LDAP-федерации.

## Быстрый старт

```bash
make up
```

Сервисы:

- Frontend: `http://localhost:3000`
- bionicpro-auth: `http://localhost:8000`
- report-api: `http://localhost:8001`
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

## Логин-поток

1. Откройте `http://localhost:3000`.
2. Нажмите `Login via bionicpro-auth`.
3. Войдите в Keycloak пользователем `user1 / password123`.
4. После callback вернет на frontend; кнопка `Download Report` получит отчет через BFF.

## Важные замечания

- Для локальной разработки cookie выставляется с `SESSION_COOKIE_SECURE=false` (иначе браузер по HTTP не примет cookie).  
  В production нужно `true` и HTTPS.
- В `bionicpro-auth` разделены URL Keycloak: `KEYCLOAK_PUBLIC_URL` (для браузерных redirect, обычно `http://localhost:8080`) и `KEYCLOAK_INTERNAL_URL` (для сервер-сервер запросов, обычно `http://keycloak:8080`).
- Включение LDAP federation, OTP и Яндекс ID в административном UI Keycloak требует дополнительной настройки и секретов провайдера.
