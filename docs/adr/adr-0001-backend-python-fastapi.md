---
title: "ADR-0001: Backend con Python y FastAPI"
status: "Accepted"
date: "2026-10-27"
authors: "Integrante A"
deciders: "Integrante A, Integrante B, Integrante C"
tags: ["architecture", "decision", "backend"]
supersedes: ""
superseded_by: ""
---

# ADR-0001: Backend con Python y FastAPI

## Status

Proposed | **Accepted** | Rejected | Superseded | Deprecated

Decisión D-02 del plan, aprobada en la reunión del equipo del 2026-10-27.

## Context

La ticketera se construye con un microservicio por bounded context (`catalog`, `sales` y `payments` en el
esqueleto; `recommendation`, `search` y `sales-queue` en etapas posteriores). Todos los servicios de backend
necesitan el mismo lenguaje y framework para que el equipo de tres personas pueda revisar el código de los
demás y explicar cualquier parte del sistema en las entrevistas individuales (RB-14).

El método de trabajo impone restricciones concretas: el contrato OpenAPI se acuerda antes del código
(*contract-first*, D-28) y un *contract test* lo compara con el que genera el servicio (D-24); el dominio se
testea sin levantar servicios (arquitectura hexagonal, D-17); y todo corre dentro de Docker Compose (RB-09,
D-12).

## Decision Drivers

- **DRV-001**: El contrato OpenAPI del servicio debe poder compararse automáticamente con el acordado (D-24).
- **DRV-002**: TDD con tests unitarios rápidos del dominio, sin base de datos (sección 3.4 del plan).
- **DRV-003**: Un único ecosistema de herramientas para todos los servicios de backend (D-15).
- **DRV-004**: Cada servicio se construye y ejecuta en su propio contenedor (RB-09, D-05).

## Decision

Los microservicios de backend se escriben en **Python con FastAPI y Pydantic**, con las herramientas de D-15:
uv para dependencias, SQLAlchemy 2 y Alembic para persistencia y migraciones, Ruff para lint y formato, mypy
para type check, y pytest con pytest-cov para los tests.

FastAPI queda confinado a la capa `api/` de cada servicio; el dominio no lo importa (ADR-0005).

## Consequences

### Positive

- **POS-001**: FastAPI genera el OpenAPI a partir de los routers y los esquemas Pydantic, lo que permite el
  *contract test* de D-24 sin mantener la especificación a mano en dos lugares.
- **POS-002**: Pydantic valida la entrada en el borde del servicio, antes de que llegue a la aplicación.
- **POS-003**: El mismo stack en todos los servicios facilita la revisión cruzada (6.1) y la transferencia de
  conocimiento entre integrantes.

### Negative

- **NEG-001**: Python tiene tipado dinámico; la seguridad de tipos depende de mypy en la CI (D-15).
- **NEG-002**: El repositorio usa dos lenguajes: TypeScript en el frontend (D-01) y Python en el backend.
- **NEG-003**: Mantener FastAPI fuera del dominio requiere disciplina; se verifica con import-linter (D-33).

## Confirmation

- **CNF-001**: Cada servicio de backend tiene `pyproject.toml` y `Dockerfile`, y su `GET /health` responde a
  través del gateway en la prueba de humo de la CI (6.4).
- **CNF-002**: El *contract test* de D-24 es un check obligatorio desde el primer change e1 con endpoints.
- **CNF-003**: Lint (Ruff), type check (mypy) y tests (pytest) corren en la CI para cada servicio.

## Alternatives Considered

### NestJS

- **ALT-001**: **Description**: Framework de backend sobre Node.js y TypeScript.
- **ALT-002**: **Rejection Reason**: Habría unificado el lenguaje con el frontend, pero el equipo eligió para
  el backend el stack de Python de D-15, y el *contract test* de D-24 se definió contra el OpenAPI que genera
  FastAPI.

### Spring Boot

- **ALT-003**: **Description**: Framework de backend sobre Java y la JVM.
- **ALT-004**: **Rejection Reason**: Agrega la JVM y un ecosistema de herramientas distinto del aprobado en
  D-15, sin cubrir ningún criterio de decisión mejor que FastAPI.

## Implementation Notes

- **IMP-001**: El bootstrap crea el esqueleto de `catalog` (grupo 3, Integrante B) y de `sales` y `payments`
  (grupos 5 y 6, Integrante C) con estructura hexagonal vacía y `GET /health`.
- **IMP-002**: El entorno virtual de Python vive en `/opt/venv` dentro de la imagen, fuera del bind mount del
  código (sección 4.4 del plan).
- **IMP-003**: El esqueleto de referencia (Alembic, reglas en `AGENTS.md`, import-linter) lo fija el design de
  `e1-idempotent-purchase` (D-33).

## References

- **REF-001**: [ADR-0004](adr-0004-contenedor-y-base-logica-por-servicio.md) y
  [ADR-0005](adr-0005-arquitectura-hexagonal.md).
- **REF-002**: `docs/PLAN.md`, secciones 4.3, 4.4 y 5.1 (D-02, D-15, D-24); acta de la reunión del equipo del
  2026-10-27.
- **REF-003**: Documentación de FastAPI: <https://fastapi.tiangolo.com/>.
