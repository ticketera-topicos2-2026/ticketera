---
title: "ADR-0007: Pago en Etapa II (D-25)"
status: "Accepted"
date: "2026-11-21"
authors: "Gustavo (Integrante C)"
deciders: "Integrante A, Integrante B, Integrante C"
tags: ["architecture", "decision", "sales", "payments"]
supersedes: ""
superseded_by: ""
---

# ADR-0007: Pago en Etapa II (D-25)

## Status

Proposed | **Accepted** | Rejected | Superseded | Deprecated

Decisión D-25 de `docs/PLAN.md`.

## Context

En la Etapa I (`e1-idempotent-purchase`), el foco arquitectónico está puesto en la reserva concurrente de asientos, la emisión de entradas y la garantía de idempotencia en el servicio `sales`. La integración con pasarelas de pago y la gestión del ciclo de vida de cobros pertenecen al subdominio genérico de pagos (`payments`), el cual será implementado en la Etapa II.

## Decision

- En la Etapa I, la compra en `sales` pasa atómicamente de la validación y bloqueo de asientos a la confirmación de la orden y emisión de entradas en una única transacción de base de datos.
- No se incorpora pasarela de pago simulada ni estado intermedio de pago en `sales` durante la Etapa I.
- La delegación asíncrona de pagos hacia `services/payments/` se incorporará formalmente en la Etapa II según lo planificado.

## Consequences

- Simplifica el diseño transaccional de `sales` aislando el mecanismo de idempotencia y concurrencia.
- Permite validar el flujo de compra extremo a extremo sin acoplamiento prematuro con servicios externos de pago.
