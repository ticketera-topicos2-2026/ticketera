---
title: "ADR-0008: Concurrencia e Idempotencia en PostgreSQL (D-30)"
status: "Accepted"
date: "2026-11-21"
authors: "Gustavo (Integrante C)"
deciders: "Integrante A, Integrante B, Integrante C"
tags: ["architecture", "decision", "sales", "concurrency", "idempotency", "postgresql"]
supersedes: ""
superseded_by: ""
---

# ADR-0008: Concurrencia e Idempotencia en PostgreSQL (D-30)

## Status

Proposed | **Accepted** | Rejected | Superseded | Deprecated

Decisión D-30 de `docs/PLAN.md`.

## Context

La venta de entradas de alta concurrencia requiere evitar la sobreventa (*double booking*) y garantizar idempotencia estricta por cliente para prevenir cobros duplicados en caso de reintentos de red. Introducir Redis para locks distribuidos introduce riesgos de doble escritura (*dual-write*) y fallos parciales entre la caché y la base de datos relacional.

## Decision

- Se utiliza PostgreSQL bajo nivel de aislamiento `READ COMMITTED` como único árbitro de concurrencia e idempotencia.
- Se implementa bloqueo pesimista ordenado de filas de asientos (`SELECT ... FOR UPDATE ORDER BY seat_id`) para prevenir interbloqueos (*deadlocks*).
- La reserva de idempotencia se ejecuta al inicio de la transacción en la tabla `idempotency_keys` con clave primaria compuesta `(customer_id, key)` mediante `INSERT ... ON CONFLICT (customer_id, key) DO NOTHING`.
- Ante colisión concurrente, PostgreSQL pausa la segunda transacción en el bloqueo de fila nativo hasta que la primera complete (`COMMIT` o `ROLLBACK`). Al desbloquearse, si el hash coincide y el estado está confirmado, se realiza `ROLLBACK` y se retorna la respuesta almacenada (201). Si el hash difiere, se retorna `422 Unprocessable Entity`.

## Consequences

- Atomicidad absoluta sin necesidad de componentes de infraestructura adicionales (como Redis o Redlock).
- Resistencia garantizada a fallas de red y reintentos concurrentes transparentes para el cliente.
