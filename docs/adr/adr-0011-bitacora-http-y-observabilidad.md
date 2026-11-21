---
title: "ADR-0011: Bitácora HTTP y observabilidad"
status: "Proposed"
date: "2026-11-20"
authors: "Integrante B"
deciders: "Integrante A, Integrante B, Integrante C"
tags: ["architecture", "decision", "observability", "logging", "gateway", "security"]
supersedes: ""
superseded_by: ""
---

# ADR-0011: Bitácora HTTP y observabilidad

## Status

**Proposed** | Accepted | Rejected | Superseded | Deprecated

Decisión D-23 del plan, aprobada en la reunión del equipo del 2026-10-27, que dejó para este ADR la retención y
los campos excluidos. Este ADR también registra una excepción a DS-13 de `project-bootstrap`. Pasa a Accepted
cuando se integre el pull request del grupo 4 de `e1-request-log`, con la aprobación de A y C. El número se fija
al integrarlo, como acordó el equipo en la revisión de #32; ADR-0007 a ADR-0010 están reservados por
`e1-identity-access` y `e1-idempotent-purchase`.

## Context

DT-03 pide desde la Etapa I una bitácora de solicitudes HTTP con medición de tiempos en todos los servicios, y
PLAN 4.6 fija el orden del middleware: iniciar el timer, procesar la autenticación, ejecutar el endpoint,
registrar método, ruta, usuario, código de estado y duración, y devolver la respuesta. Los rechazos de
autenticación también se registran. Antes de este cambio, cada servicio escribía solo la línea de acceso de
Uvicorn, sin usuario, con la ruta cruda y el query string, y nada vinculaba una solicitud del gateway con la misma
solicitud dentro del servicio. Las Etapas II y III (cache, colas, prueba de estrés) necesitan medir su efecto.

Hechos que enmarcan la decisión:

- El gateway NGINX es el único punto de entrada ([ADR-0003](adr-0003-api-gateway-nginx.md)). Desde
  `e1-identity-access` valida el token con `auth_request` y reenvía el encabezado `Authorization` sin cambios; los
  servicios decodifican el token y toman el `sub`.
- Los servicios son FastAPI con arquitectura hexagonal ([ADR-0005](adr-0005-arquitectura-hexagonal.md)), y cada
  uno se construye desde su propia carpeta, con su propio lockfile
  ([ADR-0004](adr-0004-contenedor-y-base-logica-por-servicio.md)).
- Todo corre en contenedores, sin dependencias en el host (D-12), con imágenes ancladas por digest (DS-25).
  DS-13 dice que ningún contenedor monta `/var/run/docker.sock`, y la prueba de humo exige que todos corran sin
  root.
- Hay máquinas del equipo con unos 3 GiB para WSL o 6 GiB de RAM en total, donde el sistema ya arrancaba con
  dificultad (#24).
- El repositorio es público y el entorno es local: no hay producción.

## Decision Drivers

- **DRV-001**: Seguir una solicitud desde el gateway hasta el servicio con un solo identificador.
- **DRV-002**: Medir la duración de cada solicitud en el gateway y en el servicio, comparable entre etapas.
- **DRV-003**: Que la bitácora no pueda contener tokens, encabezados, cuerpos ni datos personales o de pago
  (OWASP ASVS V7, OWASP API Security Top 10).
- **DRV-004**: Consultar la bitácora en un lugar, sin instalar nada en el host (D-12).
- **DRV-005**: Que la observabilidad no se vuelva una dependencia de la aplicación ni ahogue a las máquinas chicas.
- **DRV-006**: Que un cliente no pueda falsificar el identificador ni inyectar líneas en la bitácora.

## Decision

1. **Una línea JSON por solicitud, en la salida estándar**, con un conjunto fijo de campos en inglés:
   - servicios: `timestamp`, `service`, `correlation_id`, `method`, `route`, `status`, `duration_seconds` y
     `user_id`;
   - gateway: `timestamp`, `service` (`gateway`), `correlation_id`, `method`, `path`, `status`,
     `duration_seconds` y `client_address`.

   La línea se arma desde cero con esos campos (lista cerrada, no lista de exclusión). **Campos excluidos**:
   tokens de acceso, de ID y de refresco; los encabezados `Authorization` y `Cookie` y cualquier otro encabezado;
   el query string; los cuerpos de solicitud y respuesta; los datos de pago. Los servicios registran la plantilla
   de la ruta (`/events/{event_id}/orders`), no la ruta pedida. La duración va en segundos, con precisión de
   milisegundos, porque NGINX solo da `$request_time` en segundos. Los schemas compartidos son
   `tests/platform/gateway-log.schema.json` y `tests/platform/request-log.schema.json`.
2. **El *correlation id* lo genera siempre el gateway**, con `$request_id` (32 caracteres hexadecimales al azar).
   Lo manda al servicio y lo devuelve al cliente en `X-Correlation-ID`, también en las respuestas que da el propio
   gateway. El valor que mande un cliente se reemplaza siempre. Un servicio solo acepta un valor de exactamente 32
   caracteres hexadecimales en minúscula; cualquier otro se registra como `null`.
3. **Un middleware ASGI por servicio**, `api/request_log.py`, agregado al final de `create_app`, mide la solicitud
   completa. El usuario es el `sub` que el adaptador de autenticación guarda en `request.state.user_id`; el
   middleware nunca lee el token. Cada servicio tiene su propia copia, y los schemas compartidos garantizan la misma
   línea en todos. Uvicorn corre con `--no-access-log`.
4. **Recolección con Alloy, Loki y Grafana:**
   - **Alloy** lee la salida de los contenedores de este proyecto de Compose por el socket de Docker, montado en
     solo lectura, y le pone una sola etiqueta, `service`.
   - **Loki** guarda las líneas en un volumen.
   - **Grafana** las consulta. Se publica solo en `127.0.0.1`, con credenciales de `.env`, sin acceso anónimo, y
     con la fuente de datos y el dashboard aprovisionados desde archivos.

   Las tres imágenes van ancladas por digest. La de Loki se extiende con el binario estático de BusyBox para su
   healthcheck, porque la oficial no trae herramientas.
5. **Retención de 7 días** en Loki, aplicada por el compactor, con datos en el volumen `ticketera-loki-data`.
6. **La observabilidad es prescindible:** ningún contenedor de la aplicación depende de Loki, Alloy ni Grafana, y
   los tres tienen límites de memoria (256, 128 y 384 MiB; 768 MiB en total). Arrancan con el `docker compose up`
   normal (RB-09) y se pueden parar sin afectar al sistema.
7. **Excepción a DS-13:** Alloy monta el socket de Docker y corre como root, porque el socket lo exige. La
   excepción se acota así:
   - `user: "0:0"` explícito y sin capacidades (`cap_drop: ALL`), así que root no puede saltarse los permisos de
     archivos;
   - `no-new-privileges`, sin puertos publicados y solo en la red `observability`;
   - la prueba de humo permite root solo para `alloy`.

   Es el único contenedor del sistema que corre como root.

## Consequences

### Positive

- **POS-001**: Una solicitud se sigue de punta a punta con un id: `docker compose logs`, o el panel del dashboard
  donde se pega el *correlation id*.
- **POS-002**: Las duraciones del gateway y de cada servicio quedan medidas y graficadas por percentiles; las
  Etapas II y III comparan antes y después con la misma consulta.
- **POS-003**: Con la lista cerrada de campos, un encabezado o un campo nuevo nunca llega a la bitácora sin un
  cambio explícito del schema. Los tests verifican que no aparezcan tokens, cookies, query strings ni cuerpos.
- **POS-004**: Un cliente no puede elegir su *correlation id* ni inyectar líneas: el gateway reemplaza el valor,
  NGINX escapa con `escape=json` y los servicios validan el formato.
- **POS-005**: Los rechazos quedan registrados en los dos niveles: el `401`, `404`, `421` y `502` del gateway, y
  el `401` y `403` de los servicios.

### Negative

- **NEG-001**: Alloy con el socket de Docker, aun en solo lectura y sin capacidades, puede usar toda la API de
  Docker: si se compromete, controla el host de Docker. Se acepta porque el entorno es local y de desarrollo, y es
  una excepción explícita a DS-13.
- **NEG-002**: Tres contenedores más (hasta 768 MiB) y una prueba de humo más larga, de 1 min 53 s a 2 min 43 s en
  la CI. En máquinas de 6 GiB, el sistema completo deja poca memoria libre; la solución documentada es parar los
  tres.
- **NEG-003**: Cada servicio tiene su copia del middleware, unas 100 líneas. Los schemas compartidos y los mismos
  tests evitan que se separen, pero un cambio de formato toca los tres servicios.
- **NEG-004**: La línea del usuario depende de que cada adaptador de autenticación guarde el `sub`; un servicio
  que lo olvide registra `null`.
- **NEG-005**: Los healthchecks de los contenedores también dejan su línea, con `correlation_id: null`; el
  dashboard los filtra por esa razón.

## Confirmation

- **CNF-001**: `tests/platform/test_log_line_schemas.py` valida los schemas y su verificador; los tests unitarios y
  de aceptación de cada servicio verifican los campos, la plantilla de la ruta, los estados, el usuario, la
  duración, el *correlation id* y la ausencia de datos sensibles.
- **CNF-002**: La prueba de humo de la CI verifica:
  - un *correlation id* en las respuestas `200`, `404`, `421` y `502`, distinto en 50 solicitudes concurrentes,
    que reemplaza al falsificado y que el servicio recibe;
  - una línea válida contra el schema en el gateway y en cada servicio, con el mismo id;
  - que no queden líneas de Uvicorn ni tokens en la bitácora;
  - que una solicitud se encuentre en Loki por su id en menos de 15 s;
  - que Grafana rechace la visita anónima;
  - los límites de memoria;
  - que el sistema siga respondiendo con los tres contenedores de recolección parados.
- **CNF-003**: `tests/platform/test_loki_config.py` verifica la retención de 168 horas.
- **CNF-004**: Un pull request que agregue un campo a la línea tiene que cambiar el schema compartido; uno que
  agregue otro contenedor como root tiene que cambiar `ROOT_ALLOWED_SERVICES` y este ADR.

## Alternatives Considered

### Escribir la bitácora en PostgreSQL desde cada handler (alternativa de D-23)

- **ALT-001**: **Description**: Cada endpoint inserta una fila por solicitud en la base de su servicio.
- **ALT-002**: **Rejection Reason**: Agrega una escritura a cada solicitud y a cada handler, mezcla la bitácora con
  los datos de negocio y no cubre las solicitudes que el gateway rechaza. D-23 la rechazó.

### OpenTelemetry completo (alternativa de D-23)

- **ALT-003**: **Description**: Trazas distribuidas, spans y métricas con OpenTelemetry y un colector.
- **ALT-004**: **Rejection Reason**: Más piezas y más configuración que lo que pide DT-03; en la Etapa I ningún
  servicio llama a otro, así que no hay trazas que distribuir. D-23 la rechazó; puede volver en una etapa
  posterior con su propio ADR.

### Solo `docker compose logs` (alternativa de D-23)

- **ALT-005**: **Description**: Las líneas JSON sin recolector: se leen con `docker compose logs`.
- **ALT-006**: **Rejection Reason**: No permite consultar por campos, agregar por servicio ni calcular percentiles,
  que las Etapas II y III necesitan. D-23 la rechazó; sigue funcionando como respaldo cuando se paran los tres
  contenedores.

### Driver de logs GELF de cada servicio hacia Alloy

- **ALT-007**: **Description**: Cada servicio usa el driver `gelf` de Docker, que viene incorporado, y manda sus
  líneas por UDP a Alloy, publicado en `127.0.0.1`. Alloy corre sin root y sin socket.
- **ALT-008**: **Rejection Reason**: Mantiene DS-13 y se probó en Docker Desktop, pero agrega un bloque `logging`
  a cada servicio y un cuarto puerto publicado, y faltaba probar cómo llega la etiqueta del servicio. El equipo
  eligió el socket con la excepción. Queda como camino de mejora si la excepción deja de ser aceptable.

### Socket proxy

- **ALT-009**: **Description**: Un contenedor que expone solo las llamadas de lectura de contenedores y logs de la
  API de Docker; Alloy le habla a él.
- **ALT-010**: **Rejection Reason**: Una imagen más que anclar y correr, y el proxy también monta el socket como
  root, así que no elimina la excepción: la traslada. Queda como camino de mejora junto con GELF.

### Plugin de Loki para Docker

- **ALT-011**: **Description**: El driver de logs `loki` como plugin de Docker.
- **ALT-012**: **Rejection Reason**: Se instala en el Docker de cada integrante, fuera del repositorio, contra D-12.

### Paquete Python compartido para el middleware

- **ALT-013**: **Description**: Un paquete común instalado por los tres servicios.
- **ALT-014**: **Rejection Reason**: Cada servicio se construye desde su carpeta con su lockfile (ADR-0004); una
  ruta compartida rompe los dos y acopla los releases de servicios independientes.

## Implementation Notes

- **IMP-001**: Change `e1-request-log`: el grupo 1 (gateway, #37), el grupo 2 (`catalog` y `payments`, #38), el
  grupo 3 (`sales`, después de la implementación de `e1-idempotent-purchase`) y el grupo 4 (recolección, #39).
- **IMP-002**: Alloy guarda sus posiciones de lectura en el volumen `ticketera-alloy-data` montado en
  `/alloy-data`, porque root sin capacidades no puede entrar en el `/var/lib/alloy` de la imagen; busca
  contenedores nuevos cada 5 s.
- **IMP-003**: Un servicio nuevo copia el middleware, usa `--no-access-log` y se suma a `REQUEST_LOG_SERVICES` de
  la prueba de humo (`CONTRIBUTE.md`, «Cómo agregar un servicio»).
- **IMP-004**: Si la excepción a DS-13 deja de ser aceptable, se reemplaza la recolección por GELF (ALT-007) y un
  ADR nuevo reemplaza al punto 7 de este.

## References

- **REF-001**: `docs/PLAN.md`: DT-03 (sección 2.3), sección 4.6 y D-23 (sección 5); acta de la reunión del equipo
  del 2026-10-27.
- **REF-002**: `openspec/changes/e1-request-log/` (proposal, specs, design RL-01 a RL-17, tasks); design de
  `e1-identity-access` (IA-08, contrato de claims); design de `project-bootstrap` (DS-12, DS-13, DS-18, DS-25).
- **REF-003**: [ADR-0003](adr-0003-api-gateway-nginx.md), [ADR-0004](adr-0004-contenedor-y-base-logica-por-servicio.md),
  [ADR-0005](adr-0005-arquitectura-hexagonal.md).
- **REF-004**: OWASP ASVS, capítulo V7 (manejo de errores y registro); OWASP API Security Top 10.
