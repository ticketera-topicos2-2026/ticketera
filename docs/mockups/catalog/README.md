# Mockups de `e1-event-catalog`

Mockups de las pantallas del catálogo de eventos (change `e1-event-catalog`, tarea 7.1; D-28), con la identidad
GoPass (D-38): paleta y tipografías Plus Jakarta Sans e Inter. Los datos son ficticios. Las portadas son degradados
de la marca, no fotos.

| Pantalla | Ruta | Quién la ve | Specs |
|---|---|---|---|
| [Catálogo público](01-catalogo-publico.png) | `/events` | Cualquiera, sin sesión | `catalog/event-browsing`: lista, filtros por tipo y mes, paginación |
| [Detalle del evento](02-detalle-evento.png) | `/events/:eventId` | Cualquiera, sin sesión | `catalog/event-browsing`: evento publicado; zonas numeradas con sus ids de asiento `<zona>-<n>` |
| [Mis eventos](03-mis-eventos.png) | `/manage/events` | `EVENT_OWNER` (los suyos) y `ADMIN` (todos) | `catalog/event-management`: listado en los dos estados |
| [Formulario del evento](04-formulario-evento.png) | `/manage/events/:eventId` | Dueño del borrador y `ADMIN` | `catalog/event-management`: datos, sede, participantes, zonas de las dos modalidades, versión, publicar |
| [Errores al publicar](05-errores-publicacion.png) | `/manage/events/:eventId` | Dueño del borrador y `ADMIN` | `catalog/event-management`: `422` al publicar (sin zonas, fecha pasada) y `409` por versión vieja |

Notas de diseño:

- «Elegir asientos», en el detalle, lleva a la pantalla de compra de `e1-idempotent-purchase`. Los precios y la
  disponibilidad son de `sales`, no del catálogo.
- El catálogo público nunca muestra el dueño de un evento ni sus borradores. «Mis eventos» no aparece para un
  `CLIENT`.
- Un evento publicado no se edita en la Etapa I, así que su acción es «Ver en el catálogo».
- La franja oscura al pie de cada imagen es una nota del mockup (endpoint y reglas), no parte de la interfaz.

## Fuente y cómo regenerar las imágenes

Cada PNG sale de su HTML en `src/`, con los estilos compartidos de `src/gopass.css`. El alto de cada captura está
en su `<meta name="mockup-height">`. Las tipografías se cargan de Google Fonts, así que hace falta conexión.

Las imágenes se generaron con Chrome 157 en modo *headless*, en Windows, con 1440 px de ancho:

```bash
chrome --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
  --virtual-time-budget=8000 --window-size=1440,<alto> --screenshot=<nombre>.png file:///<ruta>/src/<nombre>.html
```

En Linux o WSL sirve el mismo comando con `google-chrome` o `chromium`. Para ver una pantalla alcanza con abrir su
HTML en el navegador.

Se probó generarlas en un contenedor con `chromedp/headless-shell:157.0.8103.27`, para no depender del navegador
del host. En una máquina con 6 GiB de RAM el proceso no terminaba, así que quedó pendiente; un navegador no es una
dependencia del proyecto (D-12).
