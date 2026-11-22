# 2026-11-21 · Etapa I: Implementación de Compra Idempotente (`e1-idempotent-purchase`)

- **Autor**: Gustavo Fuentes (Integrante C)
- **Issue / pull request**: #31 · rama `feature/e1-idempotent-purchase`

## Qué se hizo

- **Arquitectura Hexagonal (D-33)**: Se configuró `import-linter` en `services/sales/.importlinter` y el script de calidad `services/sales/bin/lint` garantizando 4 capas estrictas (`domain`, `application`, `infrastructure`, `api`).
- **Dominio Puro (TDD)**: Entidades `Seat`, `Order`, `Ticket` y objeto de valor `Money` (en centavos ARS) libres de dependencias de infraestructura.
- **Capa de Aplicación y Casos de Uso**:
  - `InitializeInventoryUseCase`: inicialización de inventario restringido por evento.
  - `GetAvailableSeatsUseCase`: consulta de asientos disponibles.
  - `PurchaseTicketsUseCase`: compra atómica con bloqueo pesimista ordenado (`find_by_seats_for_update`) y reserva previa de clave de idempotencia.
  - `GetOrderUseCase`: consulta de orden con protección BOLA (Broken Object Level Authorization, OWASP API1) devolviendo 404 a clientes no propietarios.
- **Persistencia en PostgreSQL 18 y Alembic**:
  - Migración `0001_sales_schema.py` con tablas `seats`, `orders`, `tickets` (con restricción `UNIQUE(event_id, seat_id)`) e `idempotency_keys` (`PRIMARY KEY (customer_id, key)`).
  - Repositorios SQLAlchemy `PostgresInventoryRepository`, `PostgresOrderRepository` y `PostgresIdempotencyStore`.
- **API REST y Controladores en FastAPI**:
  - Rutas bajo `/api/sales/` con decodificación de JWT perimeter trust (`sub`, `realm_access.roles`).
  - Validación de cabecera `Idempotency-Key` (400 Bad Request ante ausencia o UUID inválido, 422 ante payload mismatch).
- **Pruebas de Contrato y Colección Bruno (D-24)**:
  - `tests/test_openapi_contract.py` comparando el `openapi.yaml` versionado contra el OpenAPI generado en FastAPI.
  - Colección Bruno automatizada en `tests/api/sales/` con escenarios de inicialización, consulta, compra, replay de idempotencia y conflicto (409).
  - Script de aislamiento de servicio `tests/smoke/sales-isolation-test.sh` verificando operatividad ante caída de `catalog`.
- **Frontend (React 19 + Vitest)**:
  - Mockups de interfaz en `docs/mockups/sales/purchase_screens.md`.
  - Componente `PurchaseScreen.tsx` y suite de pruebas en `PurchaseScreen.test.tsx` cubriendo selección de asientos, cálculo de precios y envío de `Idempotency-Key`.
- **ADRs y Documentación**:
  - `ADR-0007`: Pago en Etapa II (D-25).
  - `ADR-0008`: Concurrencia e Idempotencia en PostgreSQL (D-30).
  - `ADR-0009`: Pruebas de API y Contrato con Bruno (D-24).
  - Actualización de `AGENTS.md` y `CONTRIBUTE.md`.
