# Mockups de la Interfaz de Compra de Entradas (GoPass)

## 1. Selección de Asientos (`/events/:eventId/buy`)

```
+-----------------------------------------------------------------------------------+
|  [Logo GoPass]  Eventos  |  Mis Entradas                             (User: Juan) |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  <- Volver a Eventos                                                             |
|                                                                                   |
|  CONCIERTO DE ROCK NACIONAL 2026                                                  |
|  Estadio River Plate - 25 de Octubre, 2026 - 21:00 hs                             |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  |                                  ESCENARIO                                  |  |
|  +-----------------------------------------------------------------------------+  |
|                                                                                   |
|       [ A-1 (VIP) ]       [ A-2 (VIP) ]       [ A-3 (VIP) ]       [ A-4 (VIP) ]   |
|       $ 15.000,00         $ 15.000,00         $ 15.000,00         $ 15.000,00     |
|       [DISPONIBLE]        [DISPONIBLE]        [ OCUPADO ]         [ SELECCIONADO] |
|                                                                                   |
|       [ B-1 (GEN) ]       [ B-2 (GEN) ]       [ B-3 (GEN) ]       [ B-4 (GEN) ]   |
|       $ 7.500,00          $ 7.500,00          $ 7.500,00          $ 7.500,00      |
|       [DISPONIBLE]        [ SELECCIONADO]     [ OCUPADO ]         [DISPONIBLE]    |
|                                                                                   |
|  -------------------------------------------------------------------------------  |
|  Resumen de Compra:                                                               |
|  - Asiento A-4 (VIP): $ 15.000,00                                                 |
|  - Asiento B-2 (General): $ 7.500,00                                              |
|  TOTAL A PAGAR: $ 22.500,00 ARS                                                   |
|                                                                                   |
|  [ Confirmar Compra e Imprimir Tickets ] (Envía POST /orders con Idempotency-Key) |
+-----------------------------------------------------------------------------------+
```

## 2. Confirmación de Orden (`/orders/:orderId`)

```
+-----------------------------------------------------------------------------------+
|  [Logo GoPass]  Eventos  |  Mis Entradas                             (User: Juan) |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  ¡FELICITACIONES! TU COMPRA FUE CONFIRMADA EXITOSAMENTE                          |
|  Orden #ord-9a4f21bc                                                              |
|  Fecha: 21/11/2026 10:35 hs                                                       |
|  Total Pagado: $ 22.500,00 ARS                                                    |
|                                                                                   |
|  TUS TICKETS:                                                                     |
|  +-----------------------------------------------------------------------------+  |
|  | TICKET #tkt-102948                                              [ QR CODE ]  |  |
|  | Evento: Concierto de Rock Nacional 2026                                     |  |
|  | Asiento: A-4 (VIP)                                                          |  |
|  | Código de Validación: TCK-A-4-8F3A21                                        |  |
|  +-----------------------------------------------------------------------------+  |
|  +-----------------------------------------------------------------------------+  |
|  | TICKET #tkt-102949                                              [ QR CODE ]  |  |
|  | Evento: Concierto de Rock Nacional 2026                                     |  |
|  | Asiento: B-2 (General)                                                      |  |
|  | Código de Validación: TCK-B-2-9D1B54                                        |  |
|  +-----------------------------------------------------------------------------+  |
|                                                                                   |
|  [ Descargar Entradas PDF ]   [ Volver al Catálogo ]                              |
+-----------------------------------------------------------------------------------+
```
