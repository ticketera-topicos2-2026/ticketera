# 2026-11-23 · e1-identity-access: backend (grupo 1)

- **Autor**: Eduardo Piray (Integrante A)
- **Issue / pull request**: #28 · pull request del backend #54, rama `feature/e1-identity-access-backend`;
  incluye el grupo 5 de `e1-event-catalog` (#35)

## Qué se hizo

El grupo 1 del change `e1-identity-access`: el realm, la validación de tokens en el gateway y sus pruebas. Cada
tarea en rojo tiene su commit `test(...)` antes del `feat(...)` que la pone en verde.

- **Comprobación de secretos del realm (1.1, 1.2, 1.28; IA-12):** lee los objetos `credentials` campo por campo,
  así que acepta una contraseña `${TEST_USER_*_PASSWORD}` y rechaza un hash exportado. La 1.28 fijó con tests tres
  casos que no tenían: texto alrededor del marcador, una credencial sin `value` y un `value` vacío o nulo.
- **Realm (1.3 a 1.7, 1.23 a 1.26; IA-10, IA-11, IA-18):**
  - el cliente público `ticketera-frontend`, con código de autorización y PKCE `S256`;
  - el cliente `ticketera-api-tests`, solo para pruebas, con usuario y contraseña y tokens de 60 s;
  - `admin-cli` sin acceso directo con contraseña;
  - cuatro usuarios de prueba, uno por rol de plataforma y un segundo `EVENT_OWNER` para las pruebas de
    propiedad, con sus contraseñas en `.env`;
  - `KC_PROXY_HEADERS=xforwarded` en el servicio de identidad.
- **Validación de tokens en el gateway (1.8 a 1.10; IA-01 a IA-04, IA-09):** `auth_request` a nivel de servidor
  contra `userinfo` de Keycloak. Sin un `Bearer` válido, `401` con `WWW-Authenticate: Bearer`; todo 4xx de
  `userinfo` se responde `401`. Rutas públicas: `GET` y `HEAD` de `/api/<servicio>/health` y todo `/auth/`, con un
  patrón estricto sobre la URI cruda.
- **Rutas públicas del catálogo (grupo 5 de `e1-event-catalog`, con `Refs #35`):** el catálogo público, sin token
  (EC-03).
- **Tokens reales en las herramientas (1.24, 1.27):** `tests/api/run.sh` y `tests/smoke/measure-catalog-latency.sh`
  piden tokens a `ticketera-api-tests` en lugar de usar tokens sin firmar.
- **Servicio de identidad caído (1.11, 1.12; IA-05, IA-06):** conexión en 1 s y lectura en 3 s hacia Keycloak, y
  `error_page 500 502 504 =502` a nivel de servidor; los archivos de rutas de `catalog`, `sales` y `payments` ya no
  declaran `error_page` ni su `proxy_connect_timeout`.
- **CORS del preflight (1.13, 1.14, 1.29; IA-07):** `Access-Control-Allow-Methods` y `Access-Control-Allow-Headers`
  solo en la respuesta a un preflight.
- **Tokens fuera de los registros del gateway (1.15, 1.16; IA-08):** `error_log ... crit` (ver «Hallazgos»).
- **Documentación (1.18 a 1.20):** los mockups de baja fidelidad en `docs/mockups/identity/`, el ADR-0010 y la
  sección «Usuarios de prueba y tokens» de `CONTRIBUTE.md`; y esta entrada.

## Decisiones tomadas

- **ADR-0010, validación de tokens en el gateway** (IA-01): propuesto, pasa a aceptado con la aprobación del pull
  request. Lleva el número que ADR-0011 reservó para esta decisión.
- **El manejo del 502 va a nivel de servidor** (IA-06), en la plantilla del gateway: cierra el pendiente del
  grupo 3.
- **Replanificación de las tareas de registros** (commit `docs(identity)` antes de la 1.15): la sonda de la 1.15
  mostró que `ticketera_json` de `e1-request-log` ya deja fuera el query string, así que la 1.16 quedó en el nivel
  del registro de errores.
- **Dos tareas nuevas:** la 1.28 (casos de credenciales sin test) y la 1.29 (guarda de regresión del CORS).

## Evidencia

Prueba de humo con el overlay `echo` y `--require-echo`. «Rojo» es la corrida con los tests nuevos antes del
cambio que los pone en verde.

- **Realm y gateway (1.1 a 1.10):** después de recrear el realm, prueba de humo 51 pasaron, 3 omitidas (sin el
  overlay). Tras integrar `main` (#37 a #53) y mandar un token en dos comprobaciones de `e1-request-log`, 122 de 122.
- **Segundo `EVENT_OWNER` y rutas del catálogo:** 125 de 125, y 135 de 135 con el grupo 5 de `e1-event-catalog`.
  Bruno de `catalog`, 13 de 13; latencia del catálogo público, p95 de 13 ms.
- **Servicio de identidad caído:**
  - rojo (1.11): 145 pasaron y 4 fallaron, en 191 s. Las cuatro fallas son las de `502`: detenido y pausado, sin
    respuesta en el tope de 10 s;
  - verde (1.12): 149 de 149, en 156 s. `502` en 1,0 s con el servicio detenido y en 3,0 s pausado;
  - controles: con `catalog` detenido, su salud responde `502` en 3,0 s, y un `500` real de un servicio sigue
    llegando como `500`.
- **CORS:**
  - rojo (1.13): 152 pasaron y 2 fallaron (`Allow-Methods` y `Allow-Headers`);
  - verde (1.14): 154 de 154;
  - controles negativos: un `GET` común no lleva esos encabezados, y un preflight de otro origen no recibe
    `Access-Control-Allow-Origin`.
- **Tokens en los registros:**
  - sonda (1.15): ningún token llega al registro de acceso, pero sí a cuatro líneas `[error]` del registro de
    errores;
  - rojo (1.15): 157 pasaron y 3 fallaron, los tres casos con un upstream que falla;
  - verde (1.16): 160 de 160, en 168 s, sin ninguna línea del registro de errores en toda la corrida. Un error de
    configuración sigue apareciendo al arrancar (`[emerg]` con `nginx -t`).
- **Mutaciones:** los tests de la 1.28 fallan con tres copias alteradas de la comprobación de secretos (una solo en
  el camino de las credenciales, que los tests anteriores no detectaban); la guarda de la 1.29 falla con un gateway
  de encabezados estáticos, que las comprobaciones anteriores no detectaban.
- **Corrida final local de la 1.17**, sobre un sistema limpio (`docker compose down -v` y `up --wait`):

  | Paso | Resultado | Tiempo |
  |---|---|---|
  | `tests/api/run.sh sales`, primero, con la base recién creada | 5 de 5 solicitudes, 10 de 10 aserciones | 23 s |
  | `tests/platform`, en el contenedor | 54 tests, OK | 9 s |
  | `tests/platform/database-isolation.sh` | 10 de 10 | 6 s |
  | Prueba de humo | 161 de 161; `502` en 1,0 s detenido y 3,0 s pausado | 174 s |
  | `tests/api/run.sh catalog` y `platform` | 13 de 13 y 2 de 2 | 22 s y 25 s |
  | Latencia del catálogo público, al final | p50 de 12 ms, p95 de 15 ms (límite 300 ms) | 8 s |

  La CI de #54 completó la verificación de la 1.17, en la
  [ejecución 45170591103](https://github.com/ticketera-topicos2-2026/ticketera/actions/runs/45170591103)
  sobre `cf695e3`: `openspec-validate` (15 s), `quality` (1 min 58 s) y `smoke-test` (4 min 16 s) en verde, 4 min
  21 s en total, dentro de los 15 minutos. Después de integrar, la CI de `main` (`24ce957`) también pasó, en 4 min
  20 s.

### Hallazgos

- **Tokens en el registro de errores del gateway.** NGINX escribe en el registro de errores, con nivel `error`, la
  línea de la solicitud con su query string y, si falla un upstream, también su dirección con el query string. La
  sonda de la 1.15 encontró ahí el token de un `?access_token=` cuando se rechaza la conexión y cuando el servicio
  de identidad está detenido, y el token de ID de `id_token_hint` en un cierre de sesión con el servicio de
  identidad detenido. El registro de acceso estaba limpio. Se resolvió con `error_log ... crit` (1.16); el registro
  de acceso sigue anotando cada `502`.
- **El servicio de identidad es un punto único de falla** de las rutas protegidas, acotado a `502` en menos de 4 s
  (ADR-0010, NEG-002).

## Pendientes

- **Grupos 2 y 3 del change:** el frontend y el cierre, en sus propios pull requests.
- **Limitaciones conocidas:**
  - NGINX resuelve cada servicio solo al arrancar (DS-07): si un contenedor vuelve con otra dirección, el gateway
    responde `502` hasta que se reinicia. En las pruebas el servicio de identidad volvió con la misma.
  - Un servicio colgado (que acepta la conexión y no responde) tarda 60 s en recibir `502`: las rutas de los
    servicios conservan el `proxy_read_timeout` por defecto; solo el servicio de identidad tiene 3 s.
  - El test 10 de la colección de Bruno de `catalog` falla después del script de latencia, hasta el siguiente
    `down -v`: el catálogo público ordena por `starts_at` y los 100 eventos del script dejan afuera al evento
    nuevo. Avisado a Ariel; no se cambió acá.
- **Para el responsable de `e1-request-log`:** en `tests/smoke/request-log-checks.sh` quedan un comentario y una
  rama de omisión que ya no se usan (cerca de la línea 80), y `tests/smoke/log-collection-checks.sh` corta el
  script si falla `docker` (línea 139).

### Mensaje al equipo (1.22)

Enviado el 23/11/2026 al grupo de WhatsApp del equipo, después de integrar #54:

> Ya está integrado el PR #54 (identidad). Para que les siga andando el entorno:
> 1. `git switch main && git pull`
> 2. Agregar al `.env` las 4 líneas `TEST_USER_*_PASSWORD` de `.env.example`
> 3. `docker compose down -v` y `docker compose up -d --wait` (borra las bases)
>
> Los pasos detallados están en CONTRIBUTE.md, «Usuarios de prueba y tokens». Si `up --wait` falla con alloy
> unhealthy: `docker compose restart alloy`.

### Para Ariel y Gustavo

- **Las cuatro líneas `TEST_USER_*_PASSWORD`:** sin ellas, `docker compose up` se detiene. Agregalas desde
  `.env.example` y recreá el realm con `docker compose down -v` (borra las bases y el realm). Los pasos, con el
  cuidado de no duplicar ni pegar líneas, están en `CONTRIBUTE.md`, «Usuarios de prueba y tokens».
- **Alloy en un arranque en frío:** si `up --wait` falla con `ticketera-alloy-1` en `unhealthy`, corré
  `docker compose restart alloy`.
- **Test 10 de `catalog`:** si falla después del script de latencia, es la limitación de arriba; un `down -v` lo
  deja en verde.
- **Tokens:** `tests/api/run.sh` ya pide tokens reales para los cuatro usuarios; una colección nueva usa
  `adminToken`, `ownerToken`, `otherOwnerToken` y `clientToken`. Para una prueba a mano, `CONTRIBUTE.md` explica
  cómo pedir un token sin dejar la contraseña ni el token en la línea de comandos.

## Uso de IA

Claude Code (Claude Opus 5.5) redactó cada cambio primero en un borrador fuera del repositorio y corrió la
verificación en contenedores:
- comprobaciones positivas y negativas;
- controles que prueban que un test no pasa por ausencia;
- mutaciones de la comprobación de secretos y del gateway;
- las sondas de la 1.15.

Antes de escribir un archivo me mostró el diff completo. Después de copiarlo, comprobó su sha256 contra el
borrador. Aprobé cada cambio, y cada commit lo hice yo. También redactó esta entrada, que revisé.

Además usé Claude (claude.ai) como segundo revisor: antes de aprobar, revisé con él cada plan, diff y resultado de
verificación, y redacté con su ayuda los prompts para Claude Code. Algunos ajustes salieron de esa revisión, como
cubrir el caso de Keycloak pausado en la 1.11 y comprobar en la 1.15 que los mensajes de error no imprimieran
tokens.
