# Cómo contribuir

Guía del equipo para llevar un cambio desde una issue hasta `main`. Las reglas para los copilotos de IA están en
[`AGENTS.md`](AGENTS.md); el plan y las decisiones, en [`docs/PLAN.md`](docs/PLAN.md).

## Requisitos previos

En el host solo se instala lo siguiente; todo lo del proyecto corre en contenedores (D-12).

- **Windows con WSL 2** y una distribución de Linux (por ejemplo, Ubuntu).
- **Git**, instalado dentro de la distribución de WSL.
- **Docker Desktop** con el backend de WSL 2 y la integración activada para tu distribución
  (*Settings → Resources → WSL integration*). Comprobá desde WSL que `docker version` muestra el cliente y el
  servidor.
- **VS Code** con la extensión WSL, y el copiloto de IA que elijas, compatible con OpenSpec (D-10).
- **OpenSpec** 1.14.1 (con Node.js), la misma para los tres integrantes y la CI (PLAN 6.5, DS-18).
- **curl** 8.1 o posterior, que la prueba de humo exige en el host. Ubuntu 24.04 trae una versión suficiente;
  Ubuntu 22.04 no, y hay que actualizarla (`curl --version` la muestra).
- **GitHub CLI** (`gh`), opcional, para crear issues y pull requests desde la terminal.

### Identidad de Git

Configurá tu nombre y el correo vinculado a tu cuenta de GitHub (T-04). Como el repositorio es público, se
recomienda el correo privado de GitHub, `ID+usuario@users.noreply.github.com`, que aparece en
*Settings → Emails*:

```bash
git config --global user.name "Tu Nombre"
git config --global user.email "ID+usuario@users.noreply.github.com"
```

Comprobá el correo desde la carpeta del repositorio:

```bash
git config user.email
```

Si el correo no está vinculado a tu cuenta, GitHub no cuenta tus aportes.

### Dónde clonar

Cloná el repositorio **dentro del sistema de archivos de WSL**, bajo tu carpeta de usuario de Linux, nunca bajo
`/mnt/c` (DS-17). En `/mnt/c` los bind mounts son lentos y no llegan los eventos de archivos, así que la recarga
en vivo no funciona.

```bash
cd ~
mkdir -p dev && cd dev
git clone https://github.com/ticketera-topicos2-2026/ticketera.git
cd ticketera
code .
```

## Levantar el sistema

Todo corre en contenedores con `docker compose`, desde la raíz del repositorio (RB-09, D-12). Hoy el sistema tiene
tres servicios: `database`, `identity` (Keycloak) y `gateway` (NGINX); los grupos 3 a 6 agregan `catalog`, el
frontend, `sales` y `payments`.

### Primera vez

1. Copiá la plantilla de configuración. `.env` no se sube a Git; los valores de `.env.example` sirven tal cual en
   local:

   ```bash
   cp .env.example .env
   ```

2. Levantá el sistema y esperá a que todos los contenedores estén sanos:

   ```bash
   docker compose up -d --wait --wait-timeout 300
   ```

   La primera vez descarga las imágenes. Keycloak importa el realm antes de abrir sus puertos y su healthcheck
   tiene `start_period: 120s`, así que el comando puede tardar un par de minutos. Si falta una variable
   obligatoria, Compose se detiene antes de crear contenedores y la nombra: revisá que `.env` tenga todas las
   de `.env.example`.

3. Comprobá el resultado (con `GATEWAY_PORT=18080`, el valor de `.env.example`):

   - `docker compose ps` muestra `database`, `identity` y `gateway` en `healthy`.
   - <http://127.0.0.1:18080/healthz> responde `200`.
   - <http://localhost:18080/auth/realms/ticketera/.well-known/openid-configuration> devuelve el documento de
     descubrimiento del realm `ticketera`.
   - <http://localhost:18080/auth/admin/> abre la consola de administración; entrá con
     `KC_BOOTSTRAP_ADMIN_USERNAME` y `KC_BOOTSTRAP_ADMIN_PASSWORD` de `.env`.

El único puerto que se publica es el del gateway (`GATEWAY_PORT`), solo en `127.0.0.1`; la base de datos no
publica puerto y se usa con `docker compose exec` (DS-10). Para entrar a `psql`:

```bash
docker compose exec database sh -c 'psql -U "$POSTGRES_USER" -d postgres'
```

### Pruebas de la plataforma

La prueba de humo y la de aislamiento de la base de datos corren contra el sistema levantado, igual que en la CI.
La prueba de humo necesita `curl` 8.1 o posterior en el host y el archivo de prueba `tests/smoke/compose.echo.yml`,
que agrega un contenedor `echo` para las pruebas de reenvío de encabezados y que nunca forma parte del sistema
real:

```bash
export COMPOSE_FILE=docker-compose.yml:tests/smoke/compose.echo.yml
docker compose up -d --wait --wait-timeout 300
tests/smoke/smoke-test.sh --require-echo
tests/platform/database-isolation.sh
docker compose down
unset COMPOSE_FILE
```

`COMPOSE_FILE` queda definida en esa terminal. Cuando termines, ejecutá `unset COMPOSE_FILE` (o cerrá la terminal),
aunque una prueba falle antes de llegar a esa línea; si no, los `docker compose` siguientes levantan también el
servicio `echo`.

Cada script imprime una línea `PASS` o `FAIL` por comprobación y termina con código distinto de cero si alguna
falla. La comprobación de secretos del realm corre en un contenedor, como en la CI:

```bash
docker run --rm --network none --read-only --user "$(id -u):$(id -g)" -v "$PWD:/repo:ro" -w /repo \
  python:3.13-alpine@sha256:1e1f6334529d1fb26a2ef619d7cffb30a7c7d7cc1cc7338ebee283a58d1aeaca \
  python -I -B scripts/check_realm_secrets.py infra/keycloak/ticketera-realm.json
```

### Tests de API (Bruno)

Cada servicio tiene su colección de Bruno en `tests/api/<servicio>/` (D-24). `tests/api/run.sh` la corre contra el
sistema levantado, con Bruno CLI instalado desde `tests/api/package-lock.json` en el contenedor de Node de la CI,
sin instalar nada en el host:

```bash
docker compose up -d --wait
tests/api/run.sh catalog
```

El runner comparte la red del gateway, así que las colecciones llaman a `http://localhost:8080/api/<servicio>`.
Les pasa los tokens `ownerToken`, `otherOwnerToken`, `adminToken` y `clientToken`, con un `sub` nuevo por corrida.
Por ahora son tokens de prueba sin firmar: sirven mientras el gateway no valide tokens. Cuando se integre el control
de acceso de `e1-identity-access` (#30), el runner tiene que pedir tokens reales al cliente `ticketera-api-tests`.

### Catálogo de eventos e inventario de `sales`

El catálogo (`e1-event-catalog`) describe la oferta y `sales` la vende: cada servicio tiene su base y ninguno lee
la del otro (D-06, D-28). En la Etapa I no hay eventos de integración, así que, después de publicar un evento, un
`ADMIN` carga a mano el inventario de `sales` con los mismos ids:

- el `event_id` de `sales` es el `id` del evento del catálogo;
- cada asiento de una zona numerada es un `seat_id` de la forma `<código de zona>-<n>`, como los devuelve
  `GET /api/catalog/events/{id}` en `zones[].seat_ids`;
- la `category` del asiento es el código de su zona; el precio lo decide `sales` (`price_centavos`, en ARS).

Por ejemplo, para un evento publicado con la zona numerada `PLATEA` de 3 asientos:

```bash
curl -X POST "http://localhost:18080/api/sales/events/<id del evento>/inventory" \
  -H "Authorization: Bearer <token de ADMIN>" -H 'Content-Type: application/json' -d '{"seats": [
    {"seat_id": "PLATEA-1", "category": "PLATEA", "price_centavos": 1500000},
    {"seat_id": "PLATEA-2", "category": "PLATEA", "price_centavos": 1500000},
    {"seat_id": "PLATEA-3", "category": "PLATEA", "price_centavos": 1500000}]}'
```

`GET /api/sales/events/<id>/seats` muestra después esos asientos como `AVAILABLE`. Las zonas no numeradas no se
cargan todavía: `sales` vende solo asientos numerados en la Etapa I. Desde la Etapa II, el evento de integración
`EventPublished` reemplaza esta carga manual.

Pruebas del catálogo, como en `sales`: `docker compose run --rm catalog pytest` (unitarias, de integración contra
PostgreSQL, de aceptación y de contrato), `docker compose run --rm catalog bin/lint` (Ruff e import-linter) y
`docker compose run --rm catalog mypy`. `catalog` aplica sus migraciones al arrancar (`bin/run`).

### Día a día

| Quiero... | Comando |
|---|---|
| Ver el estado | `docker compose ps` |
| Ver los logs de un servicio | `docker compose logs -f <servicio>` |
| Reconstruir las imágenes y renovar los volúmenes anónimos (por ejemplo, después de cambiar las dependencias de un servicio: evita un `node_modules` viejo) | `docker compose up -d --build -V` |
| Detener sin borrar datos | `docker compose down` |
| Reiniciar el gateway | `docker compose restart gateway` |
| Empezar de cero, borrando la base de datos y el realm | `docker compose down -v` |

`docker compose down -v` borra el volumen `ticketera-db-data`: las bases de todos los servicios y el realm
importado. Es el comando que hace falta cuando:

- cambió `infra/keycloak/ticketera-realm.json`: Keycloak importa el realm solo si no existe, así que un cambio
  no llega a un entorno que ya lo tiene;
- se agregó una base o un rol en `infra/database/`: el script de inicialización corre solo con el volumen vacío
  (DS-03);
- querés cambiar el administrador inicial de Keycloak (ver más abajo).

`docker compose restart gateway` es la solución cuando el gateway responde `502` después de recrear un servicio:
NGINX resuelve la dirección de cada servicio al arrancar, y un servicio recreado puede recibir otra IP (DS-07).

### Bitácora de solicitudes y Grafana

El gateway y cada servicio escriben una línea JSON por solicitud en su salida estándar (D-23, change
`e1-request-log`). El gateway genera un *correlation id* por solicitud: lo manda al servicio y lo devuelve en el
encabezado `X-Correlation-ID` de toda respuesta, así que la misma solicitud se sigue de punta a punta. Las líneas
nunca llevan tokens, encabezados, cuerpos ni el query string; los servicios registran la plantilla de la ruta
(`/events/{event_id}/orders`), no la ruta pedida.

Para seguir una solicitud desde la terminal:

```bash
id=$(curl -s -o /dev/null -D - http://localhost:18080/api/catalog/health | tr -d '\r' \
  | awk -F': ' 'tolower($1)=="x-correlation-id" {print $2}')
docker compose logs --no-log-prefix gateway catalog | grep "$id"
```

**Grafana.** Alloy recolecta la salida de todos los contenedores, Loki la guarda 7 días y Grafana la consulta. Grafana
abre en <http://localhost:3000> (`GRAFANA_PORT`, solo en `127.0.0.1`), con `GRAFANA_ADMIN_USER` y
`GRAFANA_ADMIN_PASSWORD` de `.env`; no hay acceso anónimo. Si tu `.env` es anterior a este cambio, agregale esas
tres variables desde `.env.example`: sin ellas, Compose se detiene y las nombra.

- *Dashboards → Ticketera → Request log*: solicitudes por servicio y por clase de status, percentiles 50, 95 y 99
  de la duración, y un panel con todas las líneas de un *correlation id* que pegás arriba, en «Correlation id».
  Solo cuenta las solicitudes que pasaron por el gateway; los healthchecks de los contenedores no llevan id.
- *Explore*, con la fuente de datos Loki, para consultas propias. Cada línea tiene la etiqueta `service` (el nombre
  del servicio de Compose) y los campos JSON se leen con `| json`, por ejemplo:

  ```logql
  {service="sales"} | json | status >= 500
  {service=~".+"} |= "<correlation id>"
  ```

**Máquinas con poca memoria.** Loki, Alloy y Grafana tienen límites de 256, 128 y 384 MiB (768 MiB en total), y
ningún servicio depende de ellos: si tu máquina no da abasto, paralos sin afectar al resto del sistema y volvé a
levantarlos cuando los necesites. Las líneas siguen disponibles en `docker compose logs`.

```bash
docker compose stop loki alloy grafana
docker compose up -d --wait loki alloy grafana
```

`docker compose down -v` también borra los volúmenes `ticketera-loki-data` y `ticketera-alloy-data`: Loki vuelve a
empezar vacío.

**Alloy queda `unhealthy` o no llegan líneas nuevas.** Si el arranque satura la máquina, el daemon de Docker
responde lento, Alloy pierde la conexión con su API («error while listing containers» en su log) y puede no
recuperarse solo. Con el sistema ya estable, reinicialo: `docker compose restart alloy`. En una máquina de 6 GiB
conviene además levantar primero el sistema sin la recolección y sumarla después:

```bash
docker compose up -d --wait database identity catalog sales payments frontend gateway
docker compose up -d --wait loki alloy grafana
```

Alloy es el único contenedor que corre como root: lee los logs por el socket de Docker, montado en solo lectura, y
no tiene capacidades, puertos publicados ni otra red que la de Loki. Es una excepción a DS-13, registrada en el ADR
de D-23.

### Cambios en el realm

El realm se define en `infra/keycloak/ticketera-realm.json` y no lleva secretos (DS-05, DS-20).

1. Hacé el cambio en la consola de administración (<http://localhost:18080/auth/admin/>).
2. Exportalo con *Realm settings → Action → Partial export*. No uses `kc.sh export`: su salida incluye usuarios
   y secretos.
3. Reemplazá cualquier secreto por un marcador `${NOMBRE}` y guardá el resultado en
   `infra/keycloak/ticketera-realm.json`.
4. Corré la comprobación de secretos del realm (comando de arriba). Falla y nombra el campo si queda un secreto
   literal.
5. Para ver el cambio en tu entorno: `docker compose down -v` y `docker compose up -d --wait`.

### Administrador inicial de Keycloak

Keycloak crea el administrador de `KC_BOOTSTRAP_ADMIN_USERNAME` y `KC_BOOTSTRAP_ADMIN_PASSWORD` solo en el primer
arranque, cuando todavía no existe el realm `master`. Cambiar esas variables en `.env` después no tiene efecto:
cambiá la contraseña en la consola o borrá el volumen con `docker compose down -v`. Es un administrador temporal
de desarrollo; un entorno real no se crea así.

### Cómo agregar un servicio

Cada servicio nuevo (grupos 3, 5 y 6) agrega su bloque a `docker-compose.yml` y su archivo de rutas, y la CI
deriva todo lo demás de `docker compose config`: no hay que editar el workflow.

**Etiquetas.** El servicio declara en `labels` el camino de salud y los tres comandos de verificación que el job
`quality` ejecuta con `docker compose run --rm <servicio>`:

- `ticketera.health-path`: la ruta de salud (por ejemplo, `/health`), que la prueba de humo pide a través del
  gateway en `/api/<servicio><ruta>`.
- `ticketera.lint`, `ticketera.typecheck` y `ticketera.test`: los comandos de lint, de verificación de tipos y de
  tests. El comando se separa por espacios y corre sin shell, así que no admite `&&`, tuberías ni comillas.

Un servicio con sección `build` al que le falte una etiqueta hace fallar `quality`, que nombra el servicio y la
etiqueta. Ejemplo:

```yaml
catalog:
  build: ./services/catalog
  labels:
    ticketera.health-path: /health
    ticketera.lint: ruff check .
    ticketera.typecheck: mypy
    ticketera.test: pytest
```

Probá cada comando en local antes del pull request, por ejemplo `docker compose run --rm catalog ruff check .`.
Para el frontend, los comandos de ESLint, `tsc --noEmit` y Vitest (por ejemplo `npx eslint .`,
`npx tsc --noEmit` y `npx vitest run`).

**Cobertura (D-18).** `domain` y `application` necesitan al menos 80 % de cobertura. `catalog` la mide con
`pytest-cov`: su etiqueta es `ticketera.test: pytest --cov`, y `[tool.coverage]` en su `pyproject.toml` fija las
capas, la cobertura de ramas, el mínimo (`fail_under = 80`) y el archivo de datos en `/tmp`, fuera de la carpeta
montada. Con eso el job `quality` falla si la cobertura baja. Para sumarlo a otro servicio, copiá esa sección
cambiando el nombre del paquete, agregá `pytest-cov` a sus dependencias de desarrollo y regenerá su lockfile con
`docker compose run --rm <servicio> uv lock`.

**Ruta del gateway.** Un archivo por servicio, `infra/gateway/routes/<servicio>.conf`, con un único `location`
que incluye los encabezados de reenvío. La barra final de `proxy_pass` quita el prefijo `/api/<servicio>/`, y la
ruta pública no lleva versión (ADR-0006):

```nginx
location /api/catalog/ {
    include snippets/forwarded-headers.conf;
    proxy_pass http://catalog:8000/;
}
```

Dos reglas para estos archivos:

- Un `location` de `infra/gateway/routes/` no declara `add_header`. CORS se resuelve a nivel de servidor en
  `infra/gateway/templates/default.conf.template`, y un `location` que declara su propio `add_header` deja de
  heredar esos encabezados.
- Cada ruta es un solo `location` que incluye `snippets/forwarded-headers.conf`.

**Bitácora de solicitudes.** Un servicio backend escribe su línea por solicitud (D-23):

- copiá `api/request_log.py` de otro servicio y agregá `RequestLogMiddleware` al final de `create_app`, con el
  nombre del servicio, para que envuelva el ruteo y los manejadores de excepciones;
- agregá `--no-access-log` al `command` de Uvicorn en `docker-compose.yml` y al `CMD` del Dockerfile;
- cuando el servicio autentique, su adaptador de autenticación guarda el `sub` aceptado en
  `request.state.user_id`; el middleware nunca lee el token;
- sumá el servicio a `REQUEST_LOG_SERVICES` en `tests/smoke/request-log-checks.sh`, y copiá los tests de
  `tests/unit/test_request_log.py` y `tests/acceptance/test_request_log_api.py`.

**`depends_on` del gateway.** NGINX resuelve cada servicio al arrancar, así que el gateway espera a que los
servicios a los que enruta estén sanos. Los grupos 3, 5 y 6 agregan su entrada al mismo `depends_on` del gateway
en `docker-compose.yml`, y esas líneas chocan entre pull requests. Antes de pedir la revisión, actualizá tu rama
con `main` y conservá las entradas de todos los servicios si hay conflicto:

```bash
git fetch
git merge origin/main
```

### Problemas frecuentes

**Base de datos: líneas `chmod: ... Operation not permitted` en el log.** Aparecen una vez en el primer arranque
(`/var/run/postgresql`) y dos en cada reinicio con datos (también `/var/lib/postgresql/18/docker`). Son
esperables: el contenedor corre con `cap_drop: [ALL]` y sin la capacidad `FOWNER`, el entrypoint ignora el error
y repite el `chmod` como usuario `postgres`, dueño de las dos carpetas (DS-13). No hay que corregir nada.

**Una carpeta montada aparece vacía dentro del contenedor.** Después de reiniciar el PC puede quedar un
contenedor creado pero nunca arrancado, que `docker compose up` reutiliza con la carpeta montada vacía: por
ejemplo, Keycloak queda `healthy` sin importar el realm y este responde `404`. Comprobalo con:

```bash
docker compose exec <servicio> ls <ruta>
```

Si la carpeta está vacía, recreá el contenedor sin borrar volúmenes:

```bash
docker compose up -d --force-recreate <servicio>
```

**`docker compose up --wait` termina por tiempo en `identity`.** Keycloak es lento al arrancar. Subí la memoria
de WSL en `%UserProfile%\.wslconfig` (por ejemplo, `memory=6GB` en la sección `[wsl2]`; es un ejemplo, ajustalo
a la memoria de tu máquina) y reiniciá WSL con `wsl --shutdown` desde PowerShell.

**Falta una variable o el puerto está ocupado.** Compose nombra la variable que falta: agregala a `.env` desde
`.env.example`. Si `GATEWAY_PORT` está en uso o Hyper-V lo tiene reservado
(`netsh interface ipv4 show excludedportrange protocol=tcp`, en PowerShell), elegí otro puerto en `.env` y
levantá de nuevo; `FRONTEND_ORIGIN` no cambia con el puerto del gateway.

**`docker` no se encuentra o no conecta desde WSL.** Activá la integración de Docker Desktop con tu distribución
(*Settings → Resources → WSL integration*) y comprobá `docker version`.

**El reloj de WSL se atrasa después de suspender el PC.** Los tokens firmados con una hora desfasada se
rechazan. Reiniciá WSL con `wsl --shutdown`; será relevante desde el primer change con autenticación.

**Error `/bin/sh^M` o `bad interpreter` en un script.** Terminaciones de línea CRLF: `.gitattributes` fuerza LF
en `*.sh`, `*.sql`, `*.conf`, `Dockerfile` y `*.json`. Cloná el repositorio dentro de WSL, no en `/mnt/c`, y
comprobá con `git ls-files --eol` que los archivos estén en `i/lf w/lf`.

**Los cambios de archivos no se ven en el contenedor o la recarga en vivo no funciona.** Casi siempre el
repositorio está bajo `/mnt/c`: en esa ruta los bind mounts son lentos y no llegan los eventos de archivos
(DS-17). Cloná dentro de WSL; el sondeo (*polling*) queda como alternativa que define el grupo del frontend.

## Flujo de trabajo

GitHub Flow: `main` siempre está protegida y todo cambio llega por pull request (RB-04, DS-21).

### 1. Issue

Abrí una issue antes de empezar (D-20, D-37) para:

- cada change de OpenSpec;
- cada grupo de tareas del bootstrap;
- refactorizaciones que tocan varios archivos;
- correcciones que cambian comportamiento;
- cambios en la CI, en Docker Compose o en configuración compartida.

El título va en inglés y el cuerpo en español (D-36).

No hace falta issue para erratas, redacción, formato, correcciones pedidas en una revisión o subas de versión
menores. En ese caso, el pull request lo dice: «Sin issue: cambio menor», con el motivo (D-37).

### 2. Rama

```bash
git switch main
git pull --ff-only
git switch -c feature/<change-o-tema>
```

- El nombre empieza siempre con `feature/`, por ejemplo `feature/e1-idempotent-purchase` (RB-01).
- Una rama contiene un grupo de tareas o una corrección.
- Nunca hagas push a la rama de otro integrante ni la borres. La única excepción es el push de prueba acordado en
  la tarea 1.12 del bootstrap (D-35).

### 3. Commits

- Mensajes en inglés con [Conventional Commits](https://www.conventionalcommits.org/): `tipo(alcance): resumen`,
  por ejemplo `feat(catalog): add health endpoint` (D-09).
- TDD: si el cambio modifica comportamiento, el commit `test(...)` con el test en rojo va antes del `feat(...)` o
  `fix(...)` que lo pone en verde (RB-12). GitHub conserva esos commits en la página del pull request aunque se
  integre con *squash*.
- Lint, type check y tests se ejecutan dentro de los contenedores, nunca en el host (D-12).

### 4. Pull request

```bash
git push -u origin feature/<change-o-tema>
```

Abrí el pull request hacia `main` y completá la plantilla:

- **Título** en inglés con Conventional Commits. Al integrar con *squash*, el título se convierte en el mensaje del
  commit en `main` (D-13, DS-21).
- **Descripción** en español (D-36), con `Closes #n` para cada issue que resuelve (D-20). En la planificación de
  un change de OpenSpec se usa `Refs #n`, y `Closes #n` en el pull request que lo implementa (D-37).
- **Uso de IA**: qué copilotos usaste y para qué, o que no usaste ninguno. Sin esta sección completa el pull
  request no se aprueba (RB-05).

### 5. Revisión

- `CODEOWNERS` pide la revisión automáticamente según la revisión cruzada de PLAN 6.1 (DS-21).
- Hace falta **una aprobación** de un integrante distinto del autor. Los cambios en `docs/PLAN.md`, `docs/domain/`
  y `openspec/config.yaml` los aprueban los otros dos integrantes (PLAN 6.1).
- El último push lo aprueba alguien distinto de quien lo hizo, y un commit nuevo invalida las aprobaciones
  anteriores (DS-21).
- Todas las conversaciones de la revisión tienen que quedar resueltas (DS-21).
- Los comentarios de revisión van en español (D-36). Una IA puede asistir en la revisión, pero aprueba una persona
  (PLAN 6.5).
- Revisar también es transferir conocimiento: cada integrante tiene que poder explicar el cambio (RB-14).

### 6. Merge

- Cuando el pull request está aprobado y la CI está en verde, **lo integra su autor**; quien revisa no hace el
  merge (D-35).
- El único método disponible es *squash and merge* (D-13).
- No hace falta actualizar la rama con `main` antes de integrar (DS-21). Si GitHub marca conflictos, se resuelven
  en tu rama:

  ```bash
  git fetch
  git merge origin/main
  ```

- GitHub borra la rama remota automáticamente después del merge (D-35, DS-21). Para borrar la local, usá `-D`:
  con *squash*, Git no reconoce sus commits como integrados y `-d` la rechaza.

  ```bash
  git switch main
  git pull --ff-only
  git fetch --prune
  git branch -D feature/<change-o-tema>
  ```

- Nadie puede saltear las reglas de `main`, ni siquiera un administrador. Si un merge rompe `main`, se revierte
  ese commit con un pull request nuevo (DS-21).

## Pruebas y Comandos de `sales`

Para el servicio `sales` (Core Domain, Etapa I):
- **Linting y reglas de arquitectura hexagonal**:
  ```bash
  docker compose run --rm sales bin/lint
  ```
- **Chequeo de tipos estáticos**:
  ```bash
  docker compose run --rm sales mypy
  ```
- **Tests unitarios, de integración y de contrato OpenAPI**:
  ```bash
  docker compose run --rm sales pytest
  ```
- **Migraciones de base de datos con Alembic**:
  ```bash
  docker compose run --rm sales alembic upgrade head
  ```

