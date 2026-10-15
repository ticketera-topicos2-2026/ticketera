# Glosario del Lenguaje Ubicuo (Ubiquitous Language)

| Campo | Valor |
|---|---|
| Versión | 0.1.0 |
| Estado | Borrador propuesto por Integrante B |
| Fecha | 2026-10-15 |
| Responsable | Integrante B (consenso de equipo tras Event Storming) |
| Contexto relacionado | Todos los Bounded Contexts |

> **Regla de idioma (D-09):** El código, los modelos, las especificaciones de OpenSpec y los identificadores técnicos se escriben en **inglés**. Las explicaciones, definiciones del dominio y la documentación del equipo se escriben en **español**.

---

## 1. Actores y Roles (`identity`)

| Término en Inglés | Símbolo en Código | Definición en Español |
|---|---|---|
| **Admin** | `ADMIN` | Usuario con permisos de administración operativa de la plataforma. Configura parámetros globales y gestiona la aprobación o rechazo de solicitudes de devolución. |
| **Event Owner** | `EVENT_OWNER` | Productor u organizador que crea, parametriza sedes, sectores, precios y publica eventos para su comercialización. |
| **Client** | `CLIENT` | Usuario final que explora la cartelera de eventos, reserva ubicaciones, realiza compras simuladas y puede solicitar reembolsos de tickets. |

---

## 2. Catálogo de Eventos (`catalog`)

| Término en Inglés | Símbolo en Código | Definición en Español |
|---|---|---|
| **Event** | `Event` | Espectáculo o actividad pública programada en una fecha, horario y sede específicos, ofertada por un `EVENT_OWNER`. |
| **Event Status** | `EventStatus` | Estado del ciclo de vida del evento: `DRAFT` (borrador en edición), `PUBLISHED` (publicado y disponible), `SOLD_OUT` (agotado), `CANCELLED` (cancelado), `FINISHED` (concluido). |
| **Event Category** | `EventCategory` | Clasificación temática del evento (ej. `CONCERT`, `THEATER`, `SPORTS`, `CONFERENCE`). |
| **Venue** | `Venue` | Recinto o establecimiento físico donde se celebra el evento, con capacidad y distribución espacial definida. |
| **Sector** | `Sector` | Subdivisión espacial dentro de una sede con una tarifa y una modalidad de admisión fija (`SEATED` o `GENERAL_ADMISSION`). |
| **Seat** | `Seat` | Butaca o asiento numerado e individualizado (con fila y número) dentro de un sector con modalidad `SEATED`. |
| **General Admission** / **Zone** | `GeneralAdmission` / `Zone` | Área sin asientos numerados donde la admisión y disponibilidad se controlan exclusivamente por aforo o cupo total. |
| **Performer** / **Participant** | `Performer` / `Participant` | Artista, orador, banda o equipo deportivo que protagoniza el evento. Facilita la búsqueda por participantes (DF-06). |

---

## 3. Ventas y Disponibilidad (`sales`) — Núcleo (Core Domain)

| Término en Inglés | Símbolo en Código | Definición en Español |
|---|---|---|
| **Ticket Inventory** | `Inventory` | Registro de disponibilidad de cupos y butacas para un evento publicado. Se inicializa al recibir el evento `EventPublished`. |
| **Reservation** | `Reservation` | Bloqueo temporal con tiempo límite de expiración (TTL) sobre una o más ubicaciones (asientos o cupos de zona) mientras el cliente completa el pago. Evita la sobreventa. |
| **Reservation TTL** | `ReservationTTL` | Período de gracia (ej. 10 minutos) tras el cual una reserva no pagada expira automáticamente y sus asientos/cupos se liberan al inventario disponible. |
| **Order** | `Order` | Intención de compra formalizada por un `CLIENT`. Agrupa las reservas asociadas, el cálculo de precio y el estado del cobro. |
| **Order Status** | `OrderStatus` | Ciclo de la orden: `PENDING` (aguardando confirmación de pago), `CONFIRMED` (pagada y emitida), `EXPIRED` (tiempo límite agotado), `CANCELLED` (cancelada). |
| **Ticket** | `Ticket` | Comprobante digital de acceso emitido tras una orden confirmada. Asocia a un cliente con un evento y una ubicación específica (o acceso general). |
| **Idempotency Key** | `idempotency_key` | Identificador único emitido por el cliente o gateway para garantizar que reintentos de red no generen cobros ni órdenes duplicadas (DF-01). |
| **Refund Request** | `RefundRequest` | Solicitud formal iniciada por un cliente para anular un ticket y recibir el reembolso de su dinero (DF-03). |
| **Refund Status** | `RefundStatus` | Estado de la devolución: `REQUESTED` (solicitada), `APPROVED` (aprobada por ADMIN y reintegrada), `REJECTED` (rechazada). |

---

## 4. Pagos (`payments`)

| Término en Inglés | Símbolo en Código | Definición en Español |
|---|---|---|
| **Payment** | `Payment` | Transacción de cobro simulada para liquidar una `Order`. |
| **Payment Status** | `PaymentStatus` | Estado del procesamiento del pago: `PENDING`, `APPROVED`, `REJECTED`. |
| **Payment Simulation** | `PaymentSimulation` | Lógica mock que simula el comportamiento de una pasarela externa (aprobación inmediata, fallo intencional o latencia). |

---

## 5. Cola de Espera y Escalabilidad (`sales-queue` — Etapa III)

| Término en Inglés | Símbolo en Código | Definición en Español |
|---|---|---|
| **Waiting Room** | `WaitingRoom` | Sala de espera virtual activada en eventos masivos de alta demanda para contener la concurrencia directa sobre el catálogo y ventas. |
| **Queue Position** | `QueuePosition` | Lugar en turno asignado a un cliente dentro de la cola, notificado periódicamente mediante WebSocket o SSE. |
| **Turn Token** | `TurnToken` | Pase temporal que autoriza al usuario a ingresar a la pantalla de selección y reserva durante una ventana limitada de tiempo. |

---

## 6. Recomendaciones y Búsqueda (`recommendation` / `search` — Etapas II y III)

| Término en Inglés | Símbolo en Código | Definición en Español |
|---|---|---|
| **User Preference** | `UserPreference` | Géneros, categorías o artistas de preferencia explícita o inferida del cliente. |
| **Purchase History** | `PurchaseHistory` | Historial de eventos y entradas compradas previamente por un cliente, usado como insumo para el modelo de recomendación. |
| **Search Index** | `SearchIndex` | Estructura optimizada de consulta alimentada por eventos asíncronos para búsquedas rápidas por relevancia y texto libre. |
