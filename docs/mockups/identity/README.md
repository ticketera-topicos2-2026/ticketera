# Mockups de `e1-identity-access`

Mockups de baja fidelidad de las pantallas de autenticación (change `e1-identity-access`, tarea 1.18; D-28), con la
identidad GoPass (D-38): paleta y tipografías Plus Jakarta Sans e Inter. Guían las pantallas del grupo 2 del change.
Los datos son los de los usuarios de prueba del realm (`test-client`, `test-admin`), para que coincidan con lo que
se ve al probar.

| Pantalla | Ruta | Quién la ve | Specs |
|---|---|---|---|
| [Encabezado](01-encabezado.png) | Todas | Cualquiera: sin sesión, «Iniciar sesión»; con sesión, nombre, rol y «Cerrar sesión» | `identity/user-authentication`: The frontend shows who is signed in |
| [Inicio de sesión](02-inicio-de-sesion.png) | `/account` → servicio de identidad → `/signin-callback` → `/account` | Quien no tiene sesión | `identity/user-authentication`: A person signs in through the identity service (los tres escenarios) |
| [Mi cuenta](03-mi-cuenta.png) | `/account` | Cualquier rol, con sesión | `identity/user-authentication`: Pages are guarded by session; The "My account" page shows the signed-in user |
| [Acceso denegado](04-acceso-denegado.png) | La de la página pedida | Con sesión y sin el rol que pide la página | `identity/user-authentication`: Pages are guarded by role |

Notas de diseño:

- La página de inicio de sesión es de Keycloak, con su propio tema; GoPass solo pone el nombre del realm. Sale en
  inglés porque el realm no habilita otros idiomas. La contraseña nunca pasa por el frontend.
- Solo se muestra el rol de plataforma (`ADMIN`, `EVENT_OWNER` o `CLIENT`), nunca los roles propios del servicio de
  identidad, como `offline_access`.
- El acceso denegado se muestra en lugar de la página, en la misma dirección, y esa página no llama a su API. Sin
  sesión, la misma página lleva al inicio de sesión. El permiso real lo verifica cada servicio (`403`).
- La franja oscura al pie de cada imagen es una nota del mockup, no parte de la interfaz.

## Fuente y cómo regenerar las imágenes

Cada PNG sale de su HTML en `src/`, con los estilos compartidos de `../catalog/src/gopass.css` y los propios de
`src/identity.css`. El alto de cada captura está en su `<meta name="mockup-height">`. Las tipografías se cargan de
Google Fonts, así que hace falta conexión. Para ver una pantalla alcanza con abrir su HTML en el navegador.

Las imágenes se generan como las del catálogo: con Chrome en modo *headless*, 1440 px de ancho (ver
[el README del catálogo](../catalog/README.md)). Se volvió a probar en un contenedor con
`chromedp/headless-shell:157.0.8103.27`, en una máquina con 16 GiB: Chrome no terminaba la captura, ni con red ni
sin ella, así que sigue sin ser una opción.
