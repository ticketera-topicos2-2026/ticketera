---
title: "ADR-0010: Validación de tokens en el gateway"
status: "Proposed"
date: "2026-11-23"
authors: "Integrante A"
deciders: "Integrante A, Integrante B, Integrante C"
tags: ["architecture", "decision", "identity", "gateway", "security"]
supersedes: ""
superseded_by: ""
---

# ADR-0010: Validación de tokens en el gateway

## Status

**Proposed** | Accepted | Rejected | Superseded | Deprecated

Decisión IA-01 del change `e1-identity-access`, que concreta la validación de tokens que el plan asigna al gateway
(sección 7.3; [ADR-0003](adr-0003-api-gateway-nginx.md), NEG-001). Pasa a Accepted cuando se integre el pull
request del backend de `e1-identity-access`, con la aprobación de B y C. Lleva el número ADR-0010, que ADR-0011
reservó para esta decisión.

## Context

El sistema se identifica con Keycloak ([ADR-0002](adr-0002-identidad-keycloak.md)) y expone la API solo a través
del gateway NGINX ([ADR-0003](adr-0003-api-gateway-nginx.md)). Antes de este cambio, el gateway reenviaba todas las
rutas sin verificar la identidad, y cada servicio tendría que validar el token por su cuenta.

Hechos que enmarcan la decisión:

- NGINX de código abierto no valida JWT de forma nativa: `auth_jwt` es de NGINX Plus (ADR-0003, NEG-001). La
  imagen oficial sí trae el módulo `auth_request`, que decide el acceso según el código de estado de una
  subsolicitud.
- Keycloak ofrece el endpoint `userinfo` de OpenID Connect: con un token válido, de una sesión activa y con el
  scope `openid`, responde `200`; con un token ausente, alterado, vencido o de una sesión cerrada, responde `401`
  (y `403` sin el scope `openid`).
- Los archivos de rutas se incluyen dentro del bloque `server` del gateway, así que una directiva de nivel
  servidor alcanza a todas las rutas, también a las que se agreguen después.
- NGINX resuelve cada upstream una sola vez, al arrancar (DS-07). Un contenedor detenido deja una dirección sin
  nada detrás: las conexiones vencen por tiempo en lugar de ser rechazadas.
- Los servicios son FastAPI con arquitectura hexagonal ([ADR-0005](adr-0005-arquitectura-hexagonal.md)) y
  necesitan saber quién llama (`sub`) y con qué roles de plataforma (`ADMIN`, `EVENT_OWNER`, `CLIENT`).
- El entorno es local, sin producción; solo `gateway` y `frontend` publican puertos, y solo en `127.0.0.1`.

## Decision Drivers

- **DRV-001**: Autenticar cada solicitud reenviada en un solo punto, de modo que una ruta nueva quede protegida
  sin declarar nada (seguro por defecto).
- **DRV-002**: Revocación inmediata: un token deja de servir apenas termina su sesión.
- **DRV-003**: Ninguna criptografía de tokens en el código del proyecto.
- **DRV-004**: Que el servicio de identidad sea una dependencia solo de las rutas protegidas: la salud de los
  servicios, las respuestas propias del gateway y la página de estado siguen funcionando si se cae.
- **DRV-005**: Mantener la imagen oficial de NGINX elegida en ADR-0003.
- **DRV-006**: Un contrato de claims estable que los changes de funcionalidades copien en sus specs.

## Decision

1. **El gateway valida cada solicitud protegida preguntándole a Keycloak.** El bloque `server` declara
   `auth_request /_auth;`, que heredan todas las rutas. `location = /_auth` es interna y llama a `userinfo` de
   Keycloak por su nombre interno, con el encabezado `Authorization` del cliente sin cambios, sin cuerpo, con
   `GET` y sin `Cookie` ni `Content-Type`. `auth_request` lee solo el código de estado; el cuerpo de `userinfo`
   nunca llega al cliente. NGINX no guarda en cache el resultado: cada solicitud se valida.
2. **Respuestas del gateway** (IA-04):
   - un encabezado `Authorization` que no es `Bearer <token>`, o ninguno, recibe `401` con
     `WWW-Authenticate: Bearer`, sin preguntarle a Keycloak;
   - todo 4xx de `userinfo` se responde `401`, con el desafío de Keycloak, para que un token rechazado nunca
     parezca una denegación por rol;
   - si Keycloak no responde, `502` (punto 4).
3. **Rutas públicas** (IA-03): solo `GET` y `HEAD` de `/api/<servicio>/health`, del catálogo público de
   `e1-event-catalog` (EC-03), y todo `/auth/`, que se excluye con `auth_request off`. La decisión se toma sobre
   el método y la URI cruda, con un patrón estricto; cualquier otra forma de escribir la ruta queda protegida.
4. **Falla del servicio de identidad acotada** (IA-05, IA-06): conexión en 1 s y lectura en 3 s hacia Keycloak,
   y a nivel servidor `error_page 500 502 504 =502`, que convierte la falla de `auth_request` en `502`. Los
   archivos de rutas no declaran `error_page` ni `add_header`, para no perder lo que heredan del servidor.
5. **Los servicios confían en el token reenviado.** Reciben el mismo encabezado `Authorization` y leen `sub` y
   `realm_access.roles` decodificando el payload, sin verificar la firma ni llamar a Keycloak, y responden `401`
   si el payload no se puede decodificar. Solo toman en cuenta los tres roles de plataforma. El gateway no inyecta
   encabezados de identidad. La autorización por rol la hace cada servicio (`403`), no el gateway.

## Consequences

### Positive

- **POS-001**: Seguro por defecto: una ruta nueva queda protegida sin escribir nada; la prueba de humo lo verifica
  con una ruta de prueba agregada después.
- **POS-002**: Revocación inmediata: un token de una sesión cerrada recibe `401` en la solicitud siguiente, sin
  esperar a que venza.
- **POS-003**: Keycloak verifica firma, vencimiento y sesión; el proyecto no escribe ni mantiene JWKS, rotación de
  claves ni verificación RS256.
- **POS-004**: Se mantiene la imagen oficial de NGINX, sin módulos de terceros ni otra cadena de suministro.
- **POS-005**: Los servicios quedan simples: un decodificador del payload y un contrato de claims común, sin
  configuración de emisor ni de claves en cada uno.
- **POS-006**: Ante una caída del servicio de identidad, la falla se acota a las rutas protegidas: la salud de los
  servicios, `/healthz` y la página de estado siguen respondiendo.

### Negative

- **NEG-001**: Una llamada a `userinfo` por cada solicitud protegida: latencia agregada y carga sobre Keycloak. Se
  acepta para la Etapa I y se mide contra el objetivo de 30 ms (tarea 2.19 del change). Si no se cumple, el primer
  paso es un `upstream` con `keepalive` hacia Keycloak, y el siguiente, una cache de respuestas.
- **NEG-002**: El servicio de identidad es un punto único de falla para todas las rutas protegidas. Se acota con
  los tiempos de espera: con Keycloak detenido el gateway responde `502` en 1 s, y con Keycloak colgado, en 3 s;
  el peor caso queda por debajo de 4 s, dentro del límite de 5 s de la página de estado (DS-15).
- **NEG-003**: NGINX resuelve el nombre del servicio de identidad solo al arrancar (DS-07). Si el contenedor de
  Keycloak vuelve con otra dirección, el gateway sigue usando la vieja hasta que se reinicia, y responde `502`
  mientras tanto. En las pruebas el contenedor volvió con la misma dirección; la prueba de humo reinicia el gateway
  si no logra alcanzarlo. Queda como limitación conocida.
- **NEG-004**: Los servicios no verifican la firma. Un contenedor comprometido en la red interna podría mandarles
  tokens falsificados directamente. Se acepta como riesgo residual, acotado por la segmentación de redes (DS-23) y
  porque solo dos puertos se publican, en `127.0.0.1`.
- **NEG-005**: Un token en el query string llega al registro de errores de NGINX cuando falla un upstream, porque
  ese registro incluye la línea de la solicitud. Se resuelve con `error_log ... crit` (IA-08), a costa de perder el
  detalle de esas fallas; el registro de acceso sigue anotando cada `502`.
- **NEG-006**: La revocación inmediata depende de no tener cache: cualquier optimización futura que guarde
  respuestas de `userinfo` cambia este compromiso y necesita su propio análisis.

## Confirmation

- **CNF-001**: La prueba de humo de la CI (`tests/smoke/identity-checks.sh`) verifica:
  - `401` con desafío `Bearer` sin token, con un encabezado que no es `Bearer`, con un token alterado, con uno
    vencido, con uno de una sesión cerrada y con uno sin el scope `openid`;
  - que el token llega sin cambios al servicio, con cada rol de plataforma y con solicitudes concurrentes de dos
    usuarios;
  - las rutas públicas y las que solo se parecen a ellas, y una ruta de prueba agregada después;
  - con Keycloak detenido y pausado, `502` en menos de 5 s, con el tiempo medido, mientras la salud y `/healthz`
    siguen en `200`;
  - que ningún token llega a los registros del gateway.
- **CNF-002**: Una ruta pública nueva exige cambiar el patrón de `$is_public_request` en la plantilla del gateway,
  un cambio visible en la revisión del pull request (CODEOWNERS de `/infra/`).

## Alternatives Considered

### Verificación del JWT en NGINX con njs (WebCrypto)

- **ALT-001**: **Description**: Un script de njs dentro del gateway descarga el JWKS de Keycloak y verifica la
  firma RS256 y el vencimiento de cada token.
- **ALT-002**: **Rejection Reason**: El proyecto tendría que escribir y mantener la descarga, la cache y la
  rotación de claves y la verificación en JavaScript, y un token de una sesión cerrada seguiría siendo válido
  hasta vencer.

### OpenResty con `lua-resty-openidc`

- **ALT-003**: **Description**: Reemplazar NGINX por OpenResty y validar con una biblioteca OIDC en Lua.
- **ALT-004**: **Rejection Reason**: Reemplaza la imagen oficial elegida en ADR-0003: otra cadena de suministro y
  más superficie.

### Introspección de tokens (RFC 7662)

- **ALT-005**: **Description**: El gateway consulta el endpoint de introspección de Keycloak.
- **ALT-006**: **Rejection Reason**: Responde `200 {"active": false}` para un token inválido, y `auth_request` no
  puede leer el cuerpo; además necesita el secreto de un cliente confidencial en el gateway.

### Verificación con JWKS en cada servicio

- **ALT-007**: **Description**: Cada servicio verifica la firma del token con el JWKS de Keycloak.
- **ALT-008**: **Rejection Reason**: La misma verificación duplicada en tres o más servicios, cada uno con su
  configuración de JWKS y de emisor, y sin revocación. Es el camino de mejora hacia *zero trust* en una etapa
  posterior, y la mitigación de NEG-004; se sumaría a la validación en el gateway, con su propio ADR.

### `auth_jwt` de NGINX Plus

- **ALT-009**: **Description**: El módulo comercial de NGINX que valida JWT de forma nativa.
- **ALT-010**: **Rejection Reason**: Es comercial (ADR-0003, NEG-001).

### Cache de respuestas de `userinfo` en NGINX

- **ALT-011**: **Description**: Guardar en la cache de NGINX el resultado de `userinfo` por token durante unos
  segundos.
- **ALT-012**: **Rejection Reason**: Usa los tokens como claves de cache y demora la revocación. Es la
  optimización a probar si el costo de una llamada por solicitud importa (NEG-001).

## Implementation Notes

- **IMP-001**: Change `e1-identity-access`, grupo 1 (backend, Integrante A): la plantilla
  `infra/gateway/templates/default.conf.template` (validación, rutas públicas, `502`, CORS y nivel del registro
  de errores) y `infra/gateway/routes/identity.conf` (tiempos de espera de `/auth/`).
- **IMP-002**: El contrato de claims para los servicios está en el design del change (sección *Token-Claims
  Contract for Services*); cada change de funcionalidades lo copia en sus specs y lo prueba en sus endpoints.
- **IMP-003**: Un servicio nuevo solo agrega su archivo de rutas, sin `auth_request`, `error_page` ni
  `add_header`; queda protegido por la directiva del servidor. Se documenta en `CONTRIBUTE.md` (tarea 1.20 del
  change).
- **IMP-004**: Si la latencia de NEG-001 supera el objetivo, se abre una tarea de seguimiento para el `upstream`
  con `keepalive`; la cache o la verificación con JWKS en los servicios llevarían su propio ADR.

## References

- **REF-001**: [ADR-0002](adr-0002-identidad-keycloak.md), [ADR-0003](adr-0003-api-gateway-nginx.md) y
  [ADR-0005](adr-0005-arquitectura-hexagonal.md).
- **REF-002**: `openspec/changes/e1-identity-access/`: proposal, specs (`platform/api-gateway`,
  `identity/access-token`), design (IA-01 a IA-09, *Alternatives Considered*, *Security Threat Analysis*) y tasks;
  design de `project-bootstrap` (DS-07, DS-15, DS-23).
- **REF-003**: `docs/PLAN.md`, sección 7.3 y decisiones D-03 y D-04.
- **REF-004**: Módulo `ngx_http_auth_request_module` de NGINX:
  <https://nginx.org/en/docs/http/ngx_http_auth_request_module.html>; OpenID Connect Core 1.0, sección 5.3
  (UserInfo Endpoint); RFC 6750 (Bearer Token Usage); OWASP ASVS, capítulo V3 (gestión de sesiones) y OWASP API
  Security Top 10 (API2: autenticación rota).
