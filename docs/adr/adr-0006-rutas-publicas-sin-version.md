---
title: "ADR-0006: Rutas públicas sin versión"
status: "Accepted"
date: "2026-11-15"
authors: "Integrante A"
deciders: "Integrante A, Integrante B, Integrante C"
tags: ["architecture", "decision", "gateway", "api"]
supersedes: ""
superseded_by: ""
---

# ADR-0006: Rutas públicas sin versión

## Status

Proposed | **Accepted** | Rejected | Superseded | Deprecated

Decisión D-29 del plan, aprobada en la reunión del equipo del 2026-10-27. Este ADR registra la resolución de
sus puntos abiertos.

## Context

El API gateway ([ADR-0003](adr-0003-api-gateway-nginx.md), DS-07) es el único punto de entrada a la API, y hay
que fijar la forma de sus rutas públicas. La Clase 7 (diapositivas 13 y 14) muestra rutas versionadas como
`/api/v1/eventos`, y el plan propuso primero `/api/v1/<servicio>/`. La reunión del equipo del 2026-10-27
adoptó la alternativa, rutas sin versión. El acta registra el resultado, pero no el motivo, y deja dos puntos
abiertos: si «sin versión» significa «nunca» o «hasta que aparezca una v2», y qué se hace si cambia un
contrato.

Hechos que enmarcan la decisión:

- El proyecto es un monorepo.
- El único consumidor de la API es el frontend del propio equipo, en el mismo repositorio.
- Los contratos se especifican en OpenSpec y se verifican con tests de API y *contract tests* (D-24).
- El gateway tiene un archivo de rutas por servicio en `infra/gateway/routes/`.

## Decision Drivers

- **DRV-001**: Rutas públicas simples y uniformes, con la misma forma para todos los servicios.
- **DRV-002**: Un único consumidor, que cambia en el mismo pull request que la API; no hay clientes externos
  que sostener mientras migran.
- **DRV-003**: Los contratos ya se controlan con OpenSpec y con los tests de API y de contrato de la CI (D-24).
- **DRV-004**: Un archivo de rutas por servicio, fácil de revisar en un pull request (ADR-0003).

## Decision

Las rutas públicas son **`/api/<servicio>/`, sin versión**. El gateway quita el prefijo antes de reenviar la
petición al servicio.

Resolución de los puntos abiertos:

1. «Sin versión» significa que las rutas públicas no llevan versión en todo el proyecto, no «hasta que
   aparezca una v2».
2. Los cambios de contrato no se resuelven por adelantado. Si aparece uno, el equipo decide en ese momento
   cómo tratarlo; si la solución necesita una versión en la ruta, un ADR nuevo reemplaza a este.

## Consequences

### Positive

- **POS-001**: Una regla única en el gateway: un bloque `/api/<servicio>/` por servicio, en su propio archivo
  de rutas.
- **POS-002**: No hay que mantener dos versiones de un endpoint en paralelo; el frontend y la API cambian
  juntos en el mismo pull request, y los tests de API y de contrato detectan la ruptura en la CI (D-24).
- **POS-003**: Los servicios no llevan el prefijo público ni una versión en sus rutas; el prefijo lo resuelve
  el gateway.

### Negative

- **NEG-001**: Un cambio incompatible en un contrato no tiene un mecanismo previsto: exige una decisión del
  equipo en ese momento y, si necesita versión en la ruta, un ADR nuevo.
- **NEG-002**: Si aparece un consumidor fuera del repositorio, no hay forma de sostener la versión anterior de
  un contrato mientras ese consumidor migra.
- **NEG-003**: El proyecto se aparta del ejemplo de la Clase 7; quien lo lea con ese material como referencia
  necesita este ADR para entender la diferencia.

## Confirmation

- **CNF-001**: La prueba de humo de la CI verifica `/api/<servicio>/health`, sin versión, a través del
  gateway.
- **CNF-002**: Los archivos de rutas de `infra/gateway/routes/` no tienen versión en ninguna ruta.
- **CNF-003**: Un pull request que agregue una versión a una ruta pública necesita un ADR nuevo que reemplace
  a este.

## Alternatives Considered

### `/api/v1/<servicio>/` (propuesta original)

- **ALT-001**: **Description**: El mismo esquema por servicio, con la versión en la ruta, como propuso el plan.
- **ALT-002**: **Rejection Reason**: La reunión adoptó la alternativa sin versión y el acta no registra el
  motivo. Análisis del trade-off, que no es un motivo declarado por el equipo: la versión en la ruta permite
  sostener dos versiones de un contrato en paralelo, algo útil cuando hay consumidores externos que migran a
  su ritmo; con un único consumidor en el mismo repositorio, que cambia en el mismo pull request, ese
  beneficio no se usa y la versión queda como un segmento fijo en todas las rutas.

### Rutas por recurso, como `/api/v1/eventos` (diapositiva 14)

- **ALT-003**: **Description**: Rutas públicas por recurso, con versión y sin el nombre del servicio, como en
  la diapositiva 14 de la Clase 7.
- **ALT-004**: **Rejection Reason**: La decisión adopta `/api/<servicio>/`, la forma que ya fija ADR-0003.
  Análisis: con rutas por recurso, el gateway necesita una regla por recurso en lugar de una por servicio, y
  cada recurso nuevo cambia su configuración; además, la ruta lleva versión, como en la alternativa anterior.

### Versión en un header

- **ALT-005**: **Description**: Rutas sin versión, con la versión del contrato en un header (un media type
  versionado en `Accept` o un header propio).
- **ALT-006**: **Rejection Reason**: Análisis: agrega negociación de versión en el gateway o en los servicios
  para un único consumidor que no la necesita. Queda como una opción más si aparece un cambio de contrato
  (punto 2 de la decisión).

## Implementation Notes

- **IMP-001**: El grupo 2 del bootstrap crea el gateway y su estructura de rutas; cada servicio agrega su
  archivo de rutas en los grupos 3 a 6, sin versión (DS-07).
- **IMP-002**: Cada servicio fija `root_path` con su prefijo público, para que su OpenAPI muestre las rutas
  públicas (DS-11).
- **IMP-003**: Si un cambio de contrato necesita versión en la ruta, se escribe un ADR nuevo y este pasa a
  Superseded.

## References

- **REF-001**: [ADR-0003](adr-0003-api-gateway-nginx.md).
- **REF-002**: `docs/PLAN.md`, secciones 5.1 (D-24, D-29) y 5.3; acta de la reunión del equipo del
  2026-10-27.
- **REF-003**: Design de `project-bootstrap`, DS-07 y DS-11; Clase 7, diapositivas 13 y 14.
