---
title: "ADR-0005: Arquitectura hexagonal en los servicios"
status: "Accepted"
date: "2026-10-27"
authors: "Integrante A"
deciders: "Integrante A, Integrante B, Integrante C"
tags: ["architecture", "decision", "hexagonal", "ddd"]
supersedes: ""
superseded_by: ""
---

# ADR-0005: Arquitectura hexagonal en los servicios

## Status

Proposed | **Accepted** | Rejected | Superseded | Deprecated

Decisión D-17 del plan, aprobada en la reunión del equipo del 2026-10-27. Incluye D-33 (esqueleto de
referencia de los servicios), que no lleva ADR propio.

## Context

El método del proyecto combina DDD táctico y TDD: el lazo interno de cada tarea son tests unitarios del
dominio y de la aplicación, sin base de datos (sección 3.4 del plan), con cobertura mínima del 80 % en
`domain` y `application` (D-18). El dominio de `sales` concentra el riesgo de doble venta y debe poder
testearse de forma aislada.

Los servicios cambian de adaptadores a lo largo de las etapas: PostgreSQL desde la Etapa I, mensajería con
RabbitMQ y la pasarela de pagos detrás de un `PaymentProvider` en la Etapa II (D-25). Además, los tres
integrantes trabajan en servicios distintos y en paralelo, y cada uno debe poder explicar el código de los
otros (RB-14).

## Decision Drivers

- **DRV-001**: Testear el dominio sin FastAPI ni base de datos (3.4, D-18).
- **DRV-002**: Modelar agregados, invariantes y eventos de dominio sin dependencias técnicas (DDD táctico).
- **DRV-003**: Reemplazar o agregar adaptadores sin tocar el dominio (Etapa II: mensajería y `PaymentProvider`).
- **DRV-004**: La misma estructura en todos los servicios, verificable de forma automática.

## Decision

Cada servicio usa **arquitectura hexagonal (puertos y adaptadores)** con cuatro capas:

- `domain/`: modelo puro (agregados, objetos de valor, eventos); sin imports de FastAPI ni de la base de datos.
- `application/`: casos de uso que orquestan el dominio a través de puertos (interfaces).
- `infrastructure/`: adaptadores (repositorios con SQLAlchemy, mensajería, clientes HTTP).
- `api/`: routers de FastAPI, esquemas Pydantic y middleware de bitácora.

Las dependencias apuntan hacia el dominio.

**Esqueleto de referencia (D-33).** Lo fija el `design.md` de `e1-idempotent-purchase`. Su implementación
inicializa Alembic, escribe las reglas en `AGENTS.md` y agrega import-linter al job quality. Los otros
servicios lo adoptan en su primer change de features; mientras tanto, los changes en paralelo siguen el
`design.md` ya integrado. El bootstrap no cambia: crea la estructura hexagonal vacía.

## Consequences

### Positive

- **POS-001**: Los tests unitarios del dominio y de la aplicación son rápidos y no levantan servicios.
- **POS-002**: Los adaptadores se reemplazan sin tocar el dominio; por ejemplo, el `PaymentProvider` de la
  Etapa II entra como un adaptador nuevo.
- **POS-003**: La misma estructura en todos los servicios facilita la revisión cruzada y la explicación del
  sistema en las entrevistas.

### Negative

- **NEG-001**: Más archivos y código de mapeo entre los modelos de persistencia y las entidades del dominio.
- **NEG-002**: Para operaciones simples (por ejemplo, un catálogo mínimo), las capas agregan trabajo sin
  mucha lógica que proteger.
- **NEG-003**: Hasta que cada servicio adopte el esqueleto de referencia, puede haber diferencias entre
  servicios.

## Confirmation

- **CNF-001**: import-linter en el job quality de la CI verifica las reglas de dependencia: `domain` no importa
  `application`, `infrastructure`, `api`, FastAPI ni SQLAlchemy (D-33).
- **CNF-002**: La cobertura mínima del 80 % en `domain` y `application` es un check de la CI (D-18).
- **CNF-003**: La revisión cruzada de cada PR comprueba que la estructura siga el esqueleto de referencia.

## Alternatives Considered

### Capas tradicionales (routers → servicios → modelos ORM)

- **ALT-001**: **Description**: Los routers llaman a servicios que trabajan directamente con los modelos del ORM.
- **ALT-002**: **Rejection Reason**: Acopla el dominio al ORM y a la base de datos: los tests de las reglas de
  negocio necesitan PostgreSQL, en contra del lazo unitario de la sección 3.4, y cambiar un adaptador obliga a
  tocar la lógica de negocio.

## Implementation Notes

- **IMP-001**: El bootstrap crea la estructura hexagonal vacía en `catalog`, `sales` y `payments`, con
  `GET /health`.
- **IMP-002**: El `design.md` de `e1-idempotent-purchase` (Integrante C) fija el esqueleto de referencia; queda
  pendiente la fecha de su integración, para que A y B lo tengan antes de arrancar sus changes.
- **IMP-003**: `catalog` y los demás servicios adoptan el esqueleto en su primer change de features.

## References

- **REF-001**: [ADR-0001](adr-0001-backend-python-fastapi.md) y
  [ADR-0004](adr-0004-contenedor-y-base-logica-por-servicio.md).
- **REF-002**: `docs/PLAN.md`, secciones 3.4, 4.3 y 5.1 (D-17, D-18, D-33); acta de la reunión del equipo del
  2026-10-27.
- **REF-003**: Alistair Cockburn, «Hexagonal Architecture» (puertos y adaptadores); documentación de
  import-linter: <https://import-linter.readthedocs.io/>.
