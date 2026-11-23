# Grupo 8 · Integrante A (edupiray) · 2026-11-23

Clon limpio de main en 34b84d0, en ~/dev/onboarding-grupo-8/ticketera-clean (WSL), proyecto de Compose
ticketera-clean, con .env copiado de .env.example sin cambios. Máquina: WSL con 15851 MiB y 16 CPUs según docker info
(integrante B: 2852 MiB y 4 CPUs), sin .wslconfig; Docker 29.9.2, Compose 5.6.1. Las imágenes base ya estaban en la
máquina, así que el build (--no-cache, 35 s) no incluye descargarlas como le pasaría a un integrante nuevo. El stack del
repositorio de trabajo se detuvo con down sin -v para liberar los puertos; sus volúmenes no se tocaron.

| Tarea | Resultado | Evidencia |
|---|---|---|
| 8.1 | **Cumple a medias**: los 10 contenedores sanos a los 101 s del primer up, sin intervención. El primer up --wait terminó con exit 1 a los 72 s porque el healthcheck de alloy no tiene start_period (su primera línea de log salió 58 s después de iniciar). Ningún servicio depende de alloy, así que, a diferencia del caso de la base de datos del integrante B, no se canceló nada; el segundo up --wait fue solo una comprobación (3 s), sin reinicio. Las rutas responden 200. | 8.1-arranque.txt |
| 8.2 | **Cumple**: los tres servicios en Disponible y ningún error de CORS (los tres ERR_ABORTED son la primera tanda de pedidos, cancelada por StrictMode de React); la consola de administración abre con las credenciales del .env. Navegador: Playwright 1.65.0 con Chromium 158. | 8.2-*.png, 8.2-navegador.txt |
| 8.3 | **Cumple**: backend servido en 3,1 a 3,9 s (5 de 5) y frontend en 0,0 a 0,1 s (5 de 5). Los tests corren con docker compose (catalog 149 passed, 1 skipped; frontend 7 passed) sin dependencias del proyecto en el host, y no crean archivos de root. | 8.3-recarga-y-tests.txt |
| 8.4 | **Cumple**: un reinicio simple (exit 0 en 61 s) conserva la marca en la base y el usuario del realm. down -v borra solo los volúmenes del clon (los tres del repositorio de trabajo conservan su CreatedAt); el up siguiente (exit 0 en 81 s) recrea las cuatro bases y el realm, con sus roles y usuarios de prueba, sin las marcas. | 8.4-reinicio-y-recreacion.txt |
| 8.5 | **Pendiente**: ciclo de /opsx:onboard en ~/dev/openspec-sandbox, fuera de ticketera; se registrará en un comentario de la issue #13. | — |

## Hallazgos

Sin propuesta de arreglo: decide el equipo.

1. **El healthcheck de alloy no tiene start_period** (8.1). En el primer arranque, Alloy escribió su primera línea 58 s
   después de iniciar; con interval 10s y retries 3 quedó unhealthy y up --wait terminó con exit 1. Es la misma clase de
   problema que #24 para la base de datos. La demora de 58 s se dio solo en el primer arranque, justo después del
   build; después de down -v, alloy estaba sano 10 s después de iniciar. En el reinicio simple y después de down -v,
   up --wait terminó con exit 0.
2. **En el primer arranque, Alloy no envió ningún log a Loki** (hallazgo-alloy-sin-envio-a-loki.txt). Loki quedó sin
   etiquetas; Alloy pasó a unhealthy por su cuenta a más tardar 13,5 min después de iniciar, con CPU de 105 a 887 % y la
   memoria en 113,7 a 116,7 MiB de su límite de 128 MiB (salvo una lectura de 44,25 MiB), y descartó un lote al
   enviar a Loki. Se descartó la causa supuesta al principio, el filtro de proyecto: Compose define COMPOSE_PROJECT_NAME
   con el nombre del proyecto, así que el filtro ya era ticketera-clean. No se repitió en el reinicio simple ni después
   de down -v (15 min cada uno; en los dos, Loki con etiquetas). Corresponde a e1-request-log (integrante B).
   - Verificado: el GOMEMLIMIT que fija Alloy (120795955 bytes = 115,2 MiB) es el 90 % de mem_limit 128m, como dice su
     documentación.
   - Verificado: la memoria de alloy se acercó a su límite de 128 MiB aun estando sano. A los 899 s del reinicio simple
     llegó a 126,3 MiB (98,7 % de mem_limit, por encima del GOMEMLIMIT), sano y enviando a Loki.
   - docker stats informa la memoria del contenedor (incluye parte de la caché de archivos y memoria del runtime de Go
     fuera del heap), no el heap de Go: que la meseta coincida con el GOMEMLIMIT es solo un indicio.
   - Hipótesis no verificada: el recolector de basura de Go corre sin parar con el heap pegado al GOMEMLIMIT.

## Notas

- 8.3: desde #54 el gateway exige un token en /api/catalog/openapi.json, así que el tiempo del backend se midió
  consultando /openapi.json dentro del contenedor catalog, no por el gateway como el integrante B.
- 8.3: el único elemento de root en el clon es frontend/node_modules, un directorio vacío que Docker creó en el primer
  up como punto de montaje del volumen anónimo; Git lo ignora.
- 8.4: la ejecución se hizo en dos tramos, porque el primero se detuvo desde fuera mientras esperaba una muestra; el
  archivo lo indica.
