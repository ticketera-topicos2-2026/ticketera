# Grupo 8 · Integrante B (arielbulacio-coder) · 2026-11-18

Clon limpio de main en 229697a, en /home/asus/onboarding-grupo-8/ticketera-clean (WSL), con .env copiado de
.env.example sin cambios. Máquina: VM de WSL con 2852 MiB y 4 CPUs, sin .wslconfig; Docker 29.9.3, Compose 5.7.0.

| Tarea | Resultado | Evidencia |
|---|---|---|
| 8.1 | **No cumple**: build en 74 s; hicieron falta tres up --wait y unos 8 minutos. 1) database queda unhealthy en el primer arranque: los scripts de inicialización tardan 35 s y su healthcheck no tiene start_period. 2) identity tarda 208 s y supera start_period 120s. Después, todos sanos y las rutas responden 200. | 8.1-arranque.txt |
| 8.2 | **Cumple**: los tres servicios en Disponible, sin errores de CORS; la consola de administración abre con las credenciales de .env. | 8.2-*.png, 8.2-navegador.txt |
| 8.3 | **Cumple a medias**: el frontend se sirve en 3,1 s; el backend en 4,5 a 19,9 s (3 de 5 bajo 10 s), porque el proceso nuevo de Python tarda en arrancar con poca memoria. Los tests corren con docker compose (catalog 16 passed, frontend 7 passed) y no dejan archivos de root. | 8.3-recarga-y-tests.txt |
| 8.4 | **Cumple**: un reinicio conserva la marca en la base y el usuario del realm; down -v los borra y recrea las bases y el realm. El arranque después de down -v tardó unos 14 minutos y necesitó tres up. | 8.4-reinicio-y-recreacion.txt, 8.4-primer-intento.txt |
| 8.5 | Pendiente: lo hace Ariel con /opsx:onboard en ~/dev/openspec-sandbox. | — |
