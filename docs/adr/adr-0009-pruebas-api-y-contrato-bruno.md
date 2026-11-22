---
title: "ADR-0009: Pruebas de API y Contrato con Bruno (D-24)"
status: "Accepted"
date: "2026-11-21"
authors: "Gustavo (Integrante C)"
deciders: "Integrante A, Integrante B, Integrante C"
tags: ["architecture", "decision", "sales", "testing", "bruno", "openapi"]
supersedes: ""
superseded_by: ""
---

# ADR-0009: Pruebas de API y Contrato con Bruno (D-24)

## Status

Proposed | **Accepted** | Rejected | Superseded | Deprecated

Decisión D-24 de `docs/PLAN.md`.

## Context

Para verificar el cumplimiento de los contratos OpenAPI generados y permitir la ejecución automatizada de pruebas funcionales y de regresión desde la perspectiva de clientes externos a través del API Gateway, se requería una herramienta ligera,版本able en Git y ejecutable tanto localmente como en CI.

## Decision

- Se adopta la colección de Bruno (`.bru`) almacenada bajo control de versiones en `tests/api/<servicio>/` para pruebas de integración sobre el gateway.
- Se incorpora un test de contrato en pytest (`test_openapi_contract.py`) que valida la coherencia entre el `openapi.yaml` versionado y el esquema dinámico de FastAPI.

## Consequences

- Las especificaciones de prueba son legibles en texto plano y no dependen de servicios propietarios en la nube (como colecciones cerradas de Postman).
- Se previene la divergencia silenciosa entre el contrato OpenAPI publicado y la implementación de endpoints en FastAPI.
