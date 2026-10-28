---
title: "ADR-0003: NGINX como API gateway"
status: "Accepted"
date: "2026-10-27"
authors: "Integrante A"
deciders: "Integrante A, Integrante B, Integrante C"
tags: ["architecture", "decision", "gateway"]
supersedes: ""
superseded_by: ""
---

# ADR-0003: NGINX como API gateway

## Status

Proposed | **Accepted** | Rejected | Superseded | Deprecated

Decisión D-04 del plan, aprobada en la reunión del equipo del 2026-10-27.

## Context

Los microservicios corren en la red interna de Docker y no se exponen al host. El sistema necesita un único
punto de entrada a la API que enrute `/api/<servicio>/` hacia cada servicio (sin versión en la ruta, D-29) y
hacia Keycloak, y que aplique CORS con un único origen permitido, el frontend (DS-09).

El gateway también tiene responsabilidades transversales aprobadas: generar siempre el *correlation id* de
la bitácora HTTP (D-23) y, desde `e1-identity-access`, validar los tokens (sección 7.3 del plan).

## Decision Drivers

- **DRV-001**: Un único punto de entrada a la API; los servicios no publican puertos.
- **DRV-002**: Enrutamiento declarativo, versionado en el repositorio y reproducible en la CI.
- **DRV-003**: Responsabilidades transversales en un solo lugar: CORS, *correlation id* y validación de tokens.
- **DRV-004**: Un contenedor liviano que se levanta con el resto del sistema (RB-09).

## Decision

El API gateway es **NGINX**, con la imagen oficial y su configuración en `./infra/gateway` (bind mount). Solo
`gateway` y `frontend` publican puertos, y solo en `127.0.0.1`. El gateway expone `/api/catalog`, `/api/sales`
y `/api/payments`, una ruta hacia Keycloak, y CORS con el frontend como único origen.

## Consequences

### Positive

- **POS-001**: Los servicios quedan fuera del alcance del host; la superficie expuesta se reduce al gateway y
  al frontend.
- **POS-002**: Las rutas viven en un archivo de configuración versionado, fácil de revisar en un PR.
- **POS-003**: El *correlation id* lo genera siempre el gateway, nunca el cliente, y llega a todos los
  servicios (D-23).

### Negative

- **NEG-001**: NGINX de código abierto no valida JWT de forma nativa (el módulo `auth_jwt` es de NGINX Plus);
  el mecanismo de validación de tokens se define en el design de `e1-identity-access`.
- **NEG-002**: No tiene API de administración ni plugins como un API gateway dedicado; cada cambio de rutas es
  un cambio de configuración y un reinicio o recarga del contenedor.
- **NEG-003**: El gateway es un punto único de falla para toda la API.

## Confirmation

- **CNF-001**: La prueba de humo de la CI verifica que cada `/health` responde a través del gateway (6.4).
- **CNF-002**: En `docker-compose.yml`, solo `gateway` y `frontend` publican puertos, y en `127.0.0.1`.
- **CNF-003**: Desde el primer change e1 con endpoints, los tests de API corren en la CI contra el gateway (D-24).

## Alternatives Considered

### Kong

- **ALT-001**: **Description**: API gateway construido sobre NGINX, con plugins (autenticación, rate limiting)
  y API de administración.
- **ALT-002**: **Rejection Reason**: Agrega su propio modelo de configuración y más componentes de los que la
  Etapa I necesita para enrutar a pocos servicios.

### Traefik

- **ALT-003**: **Description**: Proxy inverso que descubre las rutas a partir de etiquetas de los contenedores.
- **ALT-004**: **Rejection Reason**: Las rutas quedarían repartidas en las etiquetas de `docker-compose.yml`
  en lugar de concentrarse en la configuración de `infra/gateway`.

## Implementation Notes

- **IMP-001**: Las rutas y CORS se crean en el grupo 2 del bootstrap (Integrante A); el ADR de D-29 (rutas
  sin versión) se escribe en ese mismo grupo.
- **IMP-002**: La generación del *correlation id* entra con `e1-request-log` (Integrante B).
- **IMP-003**: La validación de tokens entra con `e1-identity-access` (Integrante A).

## References

- **REF-001**: [ADR-0002](adr-0002-identidad-keycloak.md) y
  [ADR-0004](adr-0004-contenedor-y-base-logica-por-servicio.md).
- **REF-002**: `docs/PLAN.md`, secciones 4.2, 4.4, 4.6, 7.1.1 y 5.1 (D-04); acta de la reunión del equipo del
  2026-10-27.
- **REF-003**: Documentación de NGINX: <https://nginx.org/en/docs/>.
