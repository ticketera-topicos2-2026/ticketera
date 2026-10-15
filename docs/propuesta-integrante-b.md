# Propuesta Técnica y Decisiones — Integrante B

| Campo | Valor |
|---|---|
| Fecha | 2026-10-15 |
| Autor | Integrante B |
| Estado | Presentado al equipo |
| Herramientas de IA | Claude Code, Gemini (Antigravity IDE) |

---

## 1. Aprobación de Decisiones Pendientes (Sección 5 de PLAN.md)

Doy mi **visto bueno / aprobación** a las decisiones propuestas en el plan:
- **D-01 (Frontend):** React + TypeScript + Vite.
- **D-02 (Backend):** Python + FastAPI con arquitectura hexagonal (D-17).
- **D-03 (Identidad):** Keycloak con OIDC y roles `ADMIN`, `EVENT_OWNER`, `CLIENT`.
- **D-04 (Gateway):** NGINX como punto único de entrada.
- **D-06 (Base de datos):** Un contenedor PostgreSQL con una base lógica y credenciales exclusivas por servicio.
- **D-15 (Herramientas Python):** `uv`, `SQLAlchemy 2`, `Alembic`, `Ruff`, `mypy` y `pytest`.
- **D-16 (Frontend UI):** Propongo **Tailwind CSS + shadcn/ui** por su ligereza y flexibilidad para diseñar selectores de asientos interactivos.
- **D-10 (Copiloto de IA):** En mi caso utilizaré **Claude Code** y **Gemini** (en Antigravity IDE), ambos operando bajo las especificaciones de OpenSpec y las directivas de `AGENTS.md`.

---

## 2. Propuesta para el Contexto `catalog` y Frontend

- **Modelo Táctico de `catalog`:**
  - El agregado raíz será `Event`, soportando el ciclo de vida `DRAFT` -> `PUBLISHED` -> `SOLD_OUT` / `CANCELLED` / `FINISHED`.
  - El recinto (`Venue`) albergará sectores (`Sector`) divididos en `GENERAL_ADMISSION` (control por aforo total) y `SEATED` (butacas individuales con fila y número), resolviendo el desafío DF-02.
  - Se modelará la entidad `Performer` (artistas, oradores) para cumplir con el filtro de búsqueda DF-06.
- **Integración asíncrona:**
  - Al publicarse un evento, `catalog` emitirá el evento de integración `catalog.event.published`, permitiendo a `sales` inicializar el inventario sin acoplar las bases de datos.
- **Glosario de Lenguaje Ubicuo:**
  - Se redactó la propuesta inicial en `docs/domain/glossary.md` para revisión conjunta en el Event Storming.

---

## 3. Próximos pasos

- A la espera de que Integrante A complete los pasos 5 y 6 del Bootstrap (`AGENTS.md`, infra base de Compose y Gateway).
- En cuanto esté listo, tomo la tarea del **Paso 7 del Bootstrap**: creación del esqueleto de `catalog` (FastAPI con `GET /health`) y el `frontend` (React con panel de estado).
