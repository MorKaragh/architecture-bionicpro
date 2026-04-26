# Расширение Keycloak: провайдеры Яндекс/VK/… из ru.playa.keycloak:keycloak-russian-providers
# (OAuth2 без принудительного scope openid — см. README / Task1).
FROM quay.io/keycloak/keycloak:26.0.7

USER root
# Провайдеры (Яндекс и др.)
ADD --chown=keycloak:keycloak \
  https://repo1.maven.org/maven2/ru/playa/keycloak/keycloak-russian-providers/26.0.0.rsp/keycloak-russian-providers-26.0.0.rsp.jar \
  /opt/keycloak/providers/keycloak-russian-providers.jar
# Runtime-зависимости russian-providers (в POM есть, в fat-jar не зашиты) — иначе ClassNotFoundException: JsonPath
ADD --chown=keycloak:keycloak \
  https://repo1.maven.org/maven2/com/jayway/jsonpath/json-path/2.9.0/json-path-2.9.0.jar \
  /opt/keycloak/providers/json-path.jar
ADD --chown=keycloak:keycloak \
  https://repo1.maven.org/maven2/net/minidev/json-smart/2.5.0/json-smart-2.5.0.jar \
  /opt/keycloak/providers/json-smart.jar
ADD --chown=keycloak:keycloak \
  https://repo1.maven.org/maven2/net/minidev/accessors-smart/2.5.0/accessors-smart-2.5.0.jar \
  /opt/keycloak/providers/accessors-smart.jar

USER keycloak
RUN /opt/keycloak/bin/kc.sh build
