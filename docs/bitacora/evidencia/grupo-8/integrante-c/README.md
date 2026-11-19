# Grupo 8 · Integrante C (gustavoandresfu) · 2026-11-19

Clon de main en ae38e02, en C:\GUS-PC\TP\ticketera, con .env configurado con puertos 15173 (frontend) y 18080 (gateway).
Máquina: Windows 11 · Docker Desktop (WSL2 engine Linux 6.6.87.2) · 15.53 GiB RAM · 12 CPUs.

| Tarea | Resultado | Evidencia |
|---|---|---|
| 8.1 | **Cumple**: build en 3.34 s; `docker compose up -d --wait --wait-timeout 300` exitoso en el primer intento en **61.9 s** (< 5 minutos). Los 7 contenedores saludables (`database`, `catalog`, `sales`, `payments`, `identity`, `frontend`, `gateway`). Todas las rutas responden 200. | `8.1-arranque.txt` |
| 8.2 | **Cumple**: los tres servicios en Disponible sin errores de CORS (ACAO: http://localhost:15173); la consola de administración de Keycloak abre y permite iniciar sesión con las credenciales de `.env` (`admin`). | `8.2-navegador.txt`, `8.2-*.png` |
| 8.3 | **Cumple**: el frontend se sirve en 0.12 s (con `VITE_USE_POLLING=true` en `.env` por DS-17); el backend en 2.56 s (ambos ampliamente bajo el límite de 10 s). Los tests corren con docker compose (`sales` 17 passed, `frontend` 7 passed) sin crear archivos de root. | `8.3-recarga-y-tests.txt` |
| 8.4 | **Cumple**: un reinicio simple (`down` y `up -d --wait` en 44.6 s) conserva la marca en la base de datos `sales` y el realm; `down -v` y `up -d --wait` recrea las 4 bases limpias y el realm en 59.7 s (primer intento). | `8.4-reinicio-y-recreacion.txt` |
| 8.5 | **Hecha**: práctica del ciclo de flujo de OpenSpec en sandbox independiente, de la propuesta al archivo. | Registrado en este reporte y en issue #13 |

