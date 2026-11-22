# 2026-11-21 · e1-event-catalog: catálogo mínimo de eventos

- **Autor**: Ariel Bulacio (Integrante B)
- **Issue / pull request**: #35 · planificación #40 · mockups #41 · backend #43 · tests de API #44 · documentación (este)

## Qué se hizo

- **Planificación (#40)**:
  - proposal;
  - cuatro specs: `catalog/event-management`, `catalog/event-browsing`, `catalog/service-access` (el contrato de claims de #30, copiado tal cual) y un cambio en `platform/api-gateway`;
  - design con las decisiones EC-01 a EC-14;
  - tasks en nueve grupos.
- **Mockups (#41)**: cinco pantallas con la identidad GoPass en `docs/mockups/catalog/`: catálogo público, detalle, «Mis eventos», formulario y errores al publicar. Son HTML y CSS, exportados a PNG.
- **Backend (#43, grupos 1 a 4)**, sobre el esqueleto D-33 de #42 y con TDD (cada `test(...)` en rojo antes de su `feat(...)`):
  - **Dominio:** agregado `Event`, con zonas numeradas (ids de asiento `<zona>-<n>`) y no numeradas (capacidad), estados y versión.
  - **Aplicación:** `CatalogService`, que controla roles y propiedad.
  - **Persistencia:** migración Alembic y repositorios SQL con `UPDATE` condicional por versión, `SELECT … FOR UPDATE` al publicar y clave de idempotencia insertada primero.
  - **API:** catálogo público, que ignora los tokens, y gestión protegida.
  - **Contrato:** `openapi.yaml`, con su contract test.
- **Tests de API (#44, grupo 6)**:
  - el runner de D-24 (`tests/api/run.sh`, Bruno CLI 4.3.0 en el contenedor de Node de la CI, dentro de la red del gateway);
  - la colección `tests/api/catalog/`, con 13 solicitudes;
  - el script de latencia `tests/smoke/measure-catalog-latency.sh`.
- **Documentación (grupo 9)**: en `CONTRIBUTE.md`, cómo carga un `ADMIN` el inventario de `sales` con los ids del catálogo, y los comandos de prueba del catálogo; y esta entrada.

## Decisiones tomadas

- **Roles:** `EVENT_OWNER` crea, edita y publica sus propios eventos y `ADMIN` puede todo, como dice PLAN 1.1. La issue #35 decía «alta por `ADMIN`».
- **DF-02 entra en el modelo:** las zonas tienen modalidad; vender sigue siendo de `sales`.
- **Estados:** solo `DRAFT` y `PUBLISHED`, y un evento publicado no se edita. El resto espera al Event Storming.
- **Dos APIs (EC-02):** la pública ignora cualquier token, porque en una ruta pública el gateway no lo valida; los borradores solo se ven por la API de gestión.
- **Idempotencia del alta:** la tabla guarda el `event_id` y un reintento devuelve ese evento, porque el spec pide «el mismo evento», no la misma respuesta byte a byte. Se actualizó el design.
- **Healthcheck de `catalog`:** `start_period: 60s`. Con las migraciones al arrancar, en una máquina cargada el arranque superaba los 45 s que tolera la configuración por defecto.
- **Runner de Bruno:** no existía y se agregó uno mínimo. Usa tokens de prueba sin firmar hasta que existan los usuarios de prueba de #30.

## Evidencia

- **Tests del contenedor:** `docker compose run --rm catalog pytest`, 132 tests: unitarios, de integración contra PostgreSQL (con tres de concurrencia: ediciones simultáneas, publicación contra edición y diez altas con la misma clave), de aceptación y de contrato.
- **Calidad:** Ruff, mypy estricto e import-linter («Catalog hexagonal layers contract (D-33) KEPT»).
- **Pruebas del sistema:** prueba de humo 30 de 30 y aislamiento de bases 10 de 10. CI en verde en #43 y #44.
- **Bruno:** 13 solicitudes y 20 aserciones pasan. El runner devuelve 0 si todo pasa, 1 si falla una aserción y 2 si el uso es incorrecto.
- **Latencia del catálogo público** con 100 eventos publicados, en una máquina de 6 GiB con WSL 2: **p50 de 26 ms y p95 de 58 ms** (el límite del spec es 300 ms).
- **Flujo verificado a través del gateway:**
  - evento creado y publicado en el catálogo;
  - ids `PLATEA-1…3` cargados por un `ADMIN` en el inventario de `sales` (201);
  - `GET /api/sales/events/{id}/seats` los devuelve como `AVAILABLE`.

### Hallazgos

- **`sales/api/auth.py`:** con `SALES_AUTH_REQUIRED=false`, una solicitud sin token pasa como `anonymous` con los roles `ADMIN` y `CLIENT`. Si la variable llegara al contenedor que corre detrás del gateway, cualquiera tendría acceso total. Se avisó en #43; en `catalog` no se copió.
- **`tests/api/sales/bruno.json`** está en formato YAML y Bruno lo lee como JSON, así que la colección de `sales` no corre. Se avisó en #44, con el contenido correcto.
- **ADR:** el ADR-0007 que el design de #30 reservaba para la validación de tokens ya lo usó #42 (pago en la Etapa II). La validación de tokens va a usar otro número.
- **La máquina de 6 GiB** volvió a dejar a WSL sin responder con el sistema completo levantado. Los commits de esos momentos se hicieron con el git de Windows, cuidando la identidad del autor, los finales de línea y los permisos de ejecución.

## Pendientes

- **Grupo 5:** el patrón de rutas públicas del catálogo en el gateway. Espera el control de acceso de #30 (A revisa).
- **Grupo 8:** las pantallas de React, que son P2 y esperan la base GoPass y el inicio de sesión de #30.
- **Tokens del runner:** cuando se integre #30, el runner tiene que pedir tokens reales al cliente `ticketera-api-tests`.
- **Cobertura de D-18:** los servicios no tienen `pytest-cov`, así que no se mide.
- **Conflicto con #38:** la bitácora HTTP también toca `catalog/api/app.py` y el `command` de `catalog` en Compose. El que se integre segundo hace el rebase.
- **Puntos abiertos del modelo:**
  - S-03 (quién es un «participante») sigue pendiente de consulta; se usó la hipótesis del plan, quienes actúan en el evento.
  - El Event Storming puede cambiar los estados del evento y las reglas de edición, y el glosario puede corregir términos; un change posterior los suma sin romper estos endpoints.
- **Capturas de las pantallas:** van con el grupo 8. Por ahora están los mockups de #41.

## Uso de IA

Claude Code (Claude Opus 5.5) redactó la planificación, diseñó los mockups, escribió los tests (primero en rojo) y la implementación, armó el runner y la colección de Bruno, corrió todas las pruebas y redactó esta entrada. Tomé las decisiones de alcance (roles, DF-02, estados) y revisé los artefactos y los resultados.
