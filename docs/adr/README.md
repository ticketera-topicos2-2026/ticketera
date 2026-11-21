# Architecture Decision Records

Registro de las decisiones de arquitectura del proyecto, según D-27 (`docs/PLAN.md`, sección 5).

- Un ADR por decisión de arquitectura importante, en `docs/adr/adr-NNNN-slug.md`, en español.
- Plantilla: la de la skill `create-architectural-decision-record`, más las secciones *Decision Drivers* y
  *Confirmation*.
- Solo lleva ADR una decisión que es difícil de revertir, sorprende sin contexto y salió de un trade-off real.
  Las decisiones de proceso quedan en el plan y en el acta.
- El ADR de una decisión se escribe dentro del change que la implementa, como una tarea de su `tasks.md`, y su
  `design.md` lo enlaza.

## Índice

| ADR | Título | Decisiones del plan | Estado | Fecha |
|---|---|---|---|---|
| [ADR-0001](adr-0001-backend-python-fastapi.md) | Backend con Python y FastAPI | D-02 | Accepted | 2026-10-27 |
| [ADR-0002](adr-0002-identidad-keycloak.md) | Identidad con Keycloak | D-03 | Accepted | 2026-10-27 |
| [ADR-0003](adr-0003-api-gateway-nginx.md) | NGINX como API gateway | D-04 | Accepted | 2026-10-27 |
| [ADR-0004](adr-0004-contenedor-y-base-logica-por-servicio.md) | Un contenedor y una base lógica por servicio | D-05, D-06 | Accepted | 2026-10-27 |
| [ADR-0005](adr-0005-arquitectura-hexagonal.md) | Arquitectura hexagonal en los servicios | D-17 (incluye D-33) | Accepted | 2026-10-27 |
| [ADR-0006](adr-0006-rutas-publicas-sin-version.md) | Rutas públicas sin versión | D-29 | Accepted | 2026-11-15 |
| [ADR-0011](adr-0011-bitacora-http-y-observabilidad.md) | Bitácora HTTP y observabilidad | D-23 (incluye una excepción a DS-13) | Proposed | 2026-11-20 |

## ADR previstos

Se escriben en el change que implementa cada decisión. La numeración se fija al escribirlos.

| Decisión | Change donde se escribe el ADR | Responsable |
|---|---|---|
| D-24 · Tests de API y contrato | El primer change e1 con endpoints | Su dueño |
| D-25 · Pago en la Etapa II | `e1-idempotent-purchase` | Integrante C |
| D-30 · Concurrencia e idempotencia sobre PostgreSQL | `e1-idempotent-purchase` | Integrante C |
