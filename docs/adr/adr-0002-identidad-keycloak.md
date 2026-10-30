---
title: "ADR-0002: Identidad con Keycloak"
status: "Accepted"
date: "2026-10-27"
authors: "Integrante A"
deciders: "Integrante A, Integrante B, Integrante C"
tags: ["architecture", "decision", "identity", "security"]
supersedes: ""
superseded_by: ""
---

# ADR-0002: Identidad con Keycloak

## Status

Proposed | **Accepted** | Rejected | Superseded | Deprecated

Decisión D-03 del plan, aprobada en la reunión del equipo del 2026-10-27.

## Context

La Etapa I exige autenticación, y el sistema tiene tres roles con permisos distintos: `ADMIN`, `EVENT_OWNER`
y `CLIENT` (sección 1.1 del plan). El contexto `identity` es un subdominio **genérico**: no diferencia al
sistema, y conviene reutilizar una solución existente en lugar de construirla (sección 3.2).

El repositorio es público (RB-02) y la seguridad se alinea con OWASP ASVS y OWASP API Security Top 10. Todo
el sistema se levanta con un único `docker compose up` (RB-09).

## Decision Drivers

- **DRV-001**: `identity` es un subdominio genérico; el esfuerzo del equipo va al núcleo (`sales`).
- **DRV-002**: Control de acceso por rol (RBAC) con los tres roles del lenguaje ubicuo.
- **DRV-003**: Estándares abiertos (OAuth 2.0 / OpenID Connect) con tokens JWT que el gateway y los servicios
  pueden validar.
- **DRV-004**: No guardar contraseñas ni secretos en código propio de un repositorio público.
- **DRV-005**: El servicio de identidad se levanta como un contenedor más del Compose.

## Decision

La identidad se delega en **Keycloak** (OAuth 2.0 / OIDC, RBAC), en el contenedor `identity` con la imagen
oficial. El realm `ticketera`, con los roles `ADMIN`, `EVENT_OWNER` y `CLIENT`, se define en `infra/keycloak`
y se importa al arrancar. Keycloak usa su propia base lógica (`keycloak`) dentro del contenedor de PostgreSQL
(ADR-0004).

Los servicios identifican al usuario por el `sub` del JWT del realm `ticketera` (D-28); la bitácora HTTP
registra ese mismo `sub` (D-23).

## Consequences

### Positive

- **POS-001**: El equipo no implementa ni mantiene almacenamiento de credenciales, login ni emisión de tokens.
- **POS-002**: Los roles se gestionan en el realm, y los tokens siguen un estándar que el gateway y los
  servicios validan sin código de identidad propio.
- **POS-003**: La definición del realm está versionada en el repositorio y se reproduce en cada máquina y en
  la CI.

### Negative

- **NEG-001**: Keycloak es un contenedor pesado; los servicios que dependen de él esperan a que esté sano
  (`depends_on` con `condition: service_healthy`), lo que alarga el arranque.
- **NEG-002**: El realm exportado debe mantenerse sincronizado con los cambios hechos en la consola.
- **NEG-003**: El equipo debe aprender la configuración de Keycloak (realm, clientes, roles y flujos de OIDC).

## Confirmation

- **CNF-001**: En el esqueleto andante, `identity` queda sano y el realm importado tiene los tres roles
  (sección 7.1.1 del plan).
- **CNF-002**: Desde `e1-identity-access`, los tests de API (D-24) cubren solicitudes con y sin token y los
  escenarios de rol (403), que se escriben cuando entra el JWT (D-28).

## Alternatives Considered

### Servicio de identidad propio en FastAPI con JWT

- **ALT-001**: **Description**: Un microservicio del equipo que registra usuarios, guarda credenciales y emite
  JWT con los roles.
- **ALT-002**: **Rejection Reason**: Descartado en la reunión del 2026-10-27. Implica construir y asegurar un
  subdominio genérico (almacenamiento de contraseñas, login, emisión y revocación de tokens) fuera del núcleo
  del sistema y con más riesgo de seguridad en un repositorio público.

## Implementation Notes

- **IMP-001**: El contenedor `identity`, el realm y la ruta del gateway hacia Keycloak se crean en el grupo 2
  del bootstrap (Integrante A).
- **IMP-002**: La validación de tokens en el gateway y las rutas protegidas del frontend van en
  `e1-identity-access` (Integrante A).
- **IMP-003**: Las credenciales de Keycloak y la contraseña del usuario de prueba del realm van en `.env`, nunca
  en el repositorio (D-28, punto abierto d).

## References

- **REF-001**: [ADR-0003](adr-0003-api-gateway-nginx.md) y
  [ADR-0004](adr-0004-contenedor-y-base-logica-por-servicio.md).
- **REF-002**: `docs/PLAN.md`, secciones 1.1, 3.2, 4.1, 4.4 y 5.1 (D-03); acta de la reunión del equipo del
  2026-10-27.
- **REF-003**: Documentación de Keycloak: <https://www.keycloak.org/documentation>; OWASP ASVS.
