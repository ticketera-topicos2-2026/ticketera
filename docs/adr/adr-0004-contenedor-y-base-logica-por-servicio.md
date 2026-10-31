---
title: "ADR-0004: Un contenedor y una base lógica por servicio"
status: "Accepted"
date: "2026-10-27"
authors: "Integrante A"
deciders: "Integrante A, Integrante B, Integrante C"
tags: ["architecture", "decision", "containers", "database"]
supersedes: ""
superseded_by: ""
---

# ADR-0004: Un contenedor y una base lógica por servicio

## Status

Proposed | **Accepted** | Rejected | Superseded | Deprecated

Decisiones D-05 y D-06 del plan, aprobadas en la reunión del equipo del 2026-10-27.

## Context

La consigna pide una arquitectura de microservicios con límites claros y despliegue independiente (DT-02),
con fronteras basadas en DDD (RB-13): cada bounded context es un microservicio. Todo el sistema se levanta con
un único `docker compose up`, y cada servicio tiene su volumen desde la carpeta donde se construye su código
(RB-09).

Cada servicio necesita sus propios datos sin que otro los lea. A la vez, el sistema corre en las máquinas de
tres integrantes y en la CI, donde los recursos son limitados.

## Decision Drivers

- **DRV-001**: Límites de servicio verificables y despliegue independiente (DT-02, RB-13).
- **DRV-002**: Ningún servicio lee los datos de otro.
- **DRV-003**: Un único `docker compose up` levanta todo el sistema (RB-09).
- **DRV-004**: Consumo de recursos razonable en las máquinas del equipo y en la CI.
- **DRV-005**: Reservar y crear la orden en una transacción local de `sales` (sección 4.1 del plan).

## Decision

**Un contenedor por microservicio** (D-05): `catalog`, `sales` y `payments`, además de `gateway`, `identity`,
`frontend` y `database`.

**Un único contenedor de PostgreSQL con una base lógica y credenciales exclusivas por servicio** (D-06):
`catalog`, `sales`, `payments` y `keycloak`, creadas por los scripts de `./infra/database` en el primer
arranque. Ningún servicio lee la base de otro: por ejemplo, `sales` tiene su propio inventario, con `event_id`
como *opaque reference*, y nunca lee la base de `catalog` (D-28).

La variante con Redis se resolvió en D-30: no hay Redis en la Etapa I.

## Consequences

### Positive

- **POS-001**: Cada servicio se construye, testea y reinicia por separado.
- **POS-002**: Las credenciales exclusivas impiden que un servicio acceda a los datos de otro.
- **POS-003**: Cada servicio evoluciona su esquema con sus propias migraciones (Alembic, D-15).
- **POS-004**: Un solo contenedor de PostgreSQL mantiene bajo el consumo de recursos.

### Negative

- **NEG-001**: El contenedor de PostgreSQL es un punto de falla y un recurso compartido por todos los servicios.
- **NEG-002**: El aislamiento de datos depende de las credenciales, no de una separación física.
- **NEG-003**: Sin consultas entre bases, algunos datos se duplican (el inventario de `sales`) y la
  sincronización entre servicios requiere eventos de integración desde la Etapa II.

## Confirmation

- **CNF-001**: `docker compose up --wait` deja todos los contenedores sanos en la CI (6.4).
- **CNF-002**: El `GET /health` de cada servicio informa su conexión a su propia base (sección 7.1.1 del plan).
- **CNF-003**: En la revisión de los scripts de `infra/database`, cada usuario tiene permisos solo sobre su base.

## Alternatives Considered

### Monolito modular en un contenedor

- **ALT-001**: **Description**: Un único proceso con un módulo por contexto.
- **ALT-002**: **Rejection Reason**: No cumple el requisito de microservicios con despliegue independiente
  (DT-02).

### Un contenedor de PostgreSQL por base

- **ALT-003**: **Description**: Un contenedor de base de datos para cada servicio.
- **ALT-004**: **Rejection Reason**: Multiplica los contenedores y los recursos en las máquinas del equipo y en
  la CI; el aislamiento que necesita el sistema ya lo dan las credenciales por servicio.

## Implementation Notes

- **IMP-001**: La imagen es `postgres:18-alpine`, anclada por digest, con el volumen `ticketera-db-data` en
  `/var/lib/postgresql` (D-34).
- **IMP-002**: El contenedor `database` no publica puertos; solo `gateway` y `frontend` lo hacen, en `127.0.0.1`.
- **IMP-003**: El código de cada servicio se monta como bind mount; el entorno virtual de Python vive en
  `/opt/venv` dentro de la imagen.

## References

- **REF-001**: [ADR-0001](adr-0001-backend-python-fastapi.md), [ADR-0002](adr-0002-identidad-keycloak.md) y
  [ADR-0005](adr-0005-arquitectura-hexagonal.md).
- **REF-002**: `docs/PLAN.md`, secciones 4.1, 4.4 y 5.1 (D-05, D-06, D-30, D-34); acta de la reunión del
  equipo del 2026-10-27.
- **REF-003**: Documentación de Docker Compose: <https://docs.docker.com/compose/>.
