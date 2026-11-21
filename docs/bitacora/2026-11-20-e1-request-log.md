# 2026-11-20 · e1-request-log: bitácora HTTP y observabilidad

- **Autor**: Ariel Bulacio (Integrante B)
- **Issue / pull request**: #34 · planificación #36 · gateway #37 · servicios #38 · recolección y documentación #39

## Qué se hizo

- **Planificación (#36)**: proposal, cinco specs (`request-correlation`, `request-log`, `log-collection`, y deltas de
  `api-gateway` y `local-environment`), design con las decisiones RL-01 a RL-17 y tasks en seis grupos.
- **Grupo 1, gateway (#37)**:
  - Log de acceso `ticketera_json` con `escape=json`: una línea por solicitud, sin query string ni encabezados.
  - *Correlation id* con `$request_id` en `X-Correlation-ID`, hacia el servicio y de vuelta en toda respuesta.
  - Schemas compartidos de las dos líneas y su verificador `scripts/check_log_lines.py`, solo con la biblioteca
    estándar.
  - Una ruta de prueba que da un `502` inmediato contra un puerto cerrado del contenedor `echo`.
- **Grupo 2, servicios (#38)**: middleware ASGI `api/request_log.py` en `catalog` y `payments`, con tests
  unitarios y de aceptación, y Uvicorn con `--no-access-log`. `check_cors` de la prueba de humo pasó a seguir las
  solicitudes por su *correlation id*, porque ya no hay marcadores en el query string del log de Uvicorn.
- **Grupo 4, recolección (#39)**:
  - Loki 3.7.10, con una imagen derivada que le agrega BusyBox para el healthcheck, y 7 días de retención.
  - Alloy v1.22.0, que lee los logs por el socket de Docker.
  - Grafana 13.3.1, con la fuente de datos y el dashboard «Request log» aprovisionados.
  - Límites de memoria y checks de humo, incluido uno que para los tres y comprueba que el sistema siga
    respondiendo.
- **Grupo 6**: [ADR-0011](../adr/adr-0011-bitacora-http-y-observabilidad.md), la sección «Bitácora de solicitudes
  y Grafana» de `CONTRIBUTE.md`, las reglas de la bitácora en `AGENTS.md` y esta entrada.

## Decisiones tomadas

- D-23: se resolvieron sus puntos abiertos en el ADR-0011:
  - **Retención:** 7 días.
  - **Campos excluidos:** tokens, encabezados (`Authorization` y `Cookie` incluidos), query string, cuerpos y datos
    de pago. La línea usa una lista cerrada de campos.
- **Excepción a DS-13 (propuesta, pendiente de aprobación de A y C en #39):** Alloy monta el socket de Docker en
  solo lectura y corre como root, sin capacidades, sin puertos publicados y solo en la red `observability`. Se
  evaluó como alternativa el driver de logs GELF de Docker por UDP: funciona en Docker Desktop y mantiene DS-13,
  pero suma un bloque `logging` por servicio y un puerto publicado más. Queda como camino de mejora.
- **Imagen derivada de Loki (RL-17):** la imagen oficial es distroless y no puede tener healthcheck. Como el
  proyecto la construye, el job `quality` le exige las etiquetas `ticketera.*`, y las tres corren `loki
  -verify-config`.
- **Memoria:** Loki 256 MiB, Alloy 128 MiB y Grafana 384 MiB (768 MiB en total). El primer reparto (320, 128 y
  256) dejaba a Grafana cerca de su límite y su reinicio superaba el tiempo del healthcheck.

## Evidencia

- CI en verde: #37 (run 44828150290), #38 (run 44831279565) y #39 (run 44840320535), con los tres checks.
- Prueba de humo local: 62 pasan, 0 fallan y 1 salteado (el `401`, hasta que se integre el control de acceso de
  #30).
- Medición de la tarea 4.5:
  - job `smoke-test` de la CI: 1 min 53 s sin la recolección y 2 min 43 s con ella, lejos del límite de 15 minutos;
  - memoria con el sistema en marcha: Loki ~100 MiB, Alloy ~90 MiB, Grafana ~210 MiB.
- Ejemplo de seguimiento de una solicitud: la línea del gateway y la de `payments` comparten
  `correlation_id: 76b34a2c0bc9293c37c041f0d753edc5`.

### Hallazgos

- **`pipefail` y `grep --quiet`.** En la prueba de humo, `docker compose logs | grep --quiet` puede dar un falso
  negativo: `grep` cierra el pipe al encontrar la coincidencia, `docker` recibe SIGPIPE y el pipeline falla. Afectaba
  a `service_log_contains` y a `check_cors` del bootstrap. Ahora el log se lee antes de buscar.
- **Root sin capacidades.** Root con `cap_drop: ALL` no puede entrar en directorios de otro usuario: Alloy no podía
  crear `/var/lib/alloy/data` (de su usuario 473, modo 770). Sus datos van al volumen montado en `/alloy-data`.
- **Descubrimiento de Alloy.** Por defecto revisa los contenedores cada 60 s. En la CI, el gateway arranca después
  de Alloy, porque espera a Keycloak, y su línea no llegaba a Loki en 15 s. Se bajó a 5 s.
- **Máquinas chicas.** En una máquina de 5,9 GiB de RAM, con el sistema completo quedan menos de 0,5 GiB libres.
  Las corridas repetidas de la prueba de humo, que para y arranca los tres contenedores, dejaron a WSL sin
  responder (`WSAETIMEDOUT`). Es el mismo problema de #24: `CONTRIBUTE.md` documenta cómo parar Loki, Alloy y
  Grafana.
- El servicio `echo` (traefik/whoami, en Go) imprime los nombres de encabezado en forma canónica:
  `X-Correlation-Id`.

## Verificaciones del 2026-11-21

- **Dashboard (4.3).** Con tráfico a través del gateway, cada consulta del dashboard «Request log», ejecutada con
  la API de Grafana, devolvió datos: solicitudes por servicio (3 series), por clase de status (2xx y 4xx),
  percentiles p50, p95 y p99 por servicio, y el panel de logs con las 2 líneas (gateway y `catalog`) de un
  *correlation id* elegido.
- **Reinicio limpio (4.4).** Un *correlation id* que Loki tenía antes de `docker compose down -v` da 0 líneas
  después de `up`, el volumen de Loki se volvió a crear y las líneas posteriores se recolectan (1701 de 9
  servicios).
- **Hallazgos en una máquina de 6 GiB:**
  - el arranque en frío después de `down -v` (reimportación del realm y migraciones de Grafana) no llegó a
    estado sano en 15 minutos; con datos existentes, el sistema completo tardó unos 4 minutos y medio;
  - con el arranque saturando la CPU, Alloy perdió la conexión con la API de Docker y dejó de recolectar hasta
    que se lo reinició; su healthcheck lo marca `unhealthy`, pero Compose no reinicia contenedores por eso.
    `CONTRIBUTE.md` documenta cómo recuperarlo y cómo levantar la recolección después del resto;
  - después de reiniciar Alloy, una línea apareció dos veces en Loki (lectura repetida al retomar).

## Pendientes

- 4.3: la captura del dashboard en `evidencia/e1-request-log/` (hace falta un navegador con sesión iniciada en
  Grafana). Lo demás está verificado (ver «Verificaciones del 2026-11-21»).
- Grupo 3, `sales`: empieza cuando se integre la implementación de `e1-idempotent-purchase` (#32). El adaptador de
  autenticación de C tiene que guardar el `sub` en `request.state.user_id`.
- Grupo 5: la colección de Bruno de `tests/api/platform/`, cuando exista el runner de D-24.
- Integrar en orden: #36 → #37 → #38 → #39, con rebase sobre `main` entre cada uno.

## Uso de IA

Claude Code (Claude Opus 5.5) redactó la planificación, escribió los tests (primero en rojo) y la implementación,
corrió las pruebas en Docker, investigó las imágenes de Loki, Alloy y Grafana, probó la alternativa GELF y redactó
el ADR, la documentación y esta entrada. Elegí la excepción del socket frente a GELF y revisé los artefactos.
