# Cómo contribuir

Guía del equipo para llevar un cambio desde una issue hasta `main`. Las reglas para los copilotos de IA están en
[`AGENTS.md`](AGENTS.md); el plan y las decisiones, en [`docs/PLAN.md`](docs/PLAN.md). D-35, D-36 y D-37 son
propuestas del equipo que todavía se están votando.

## Requisitos previos

En el host solo se instala lo siguiente; todo lo del proyecto corre en contenedores (D-12).

- **Windows con WSL 2** y una distribución de Linux (por ejemplo, Ubuntu).
- **Git**, instalado dentro de la distribución de WSL.
- **Docker Desktop** con el backend de WSL 2 y la integración activada para tu distribución
  (*Settings → Resources → WSL integration*). Comprobá desde WSL que `docker version` muestra el cliente y el
  servidor.
- **VS Code** con la extensión WSL, y el copiloto de IA que elijas, compatible con OpenSpec (D-10).
- **OpenSpec** 1.14.1 (con Node.js), la misma para los tres integrantes y la CI (PLAN 6.5, DS-18).
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

Cómo levantar el sistema y resolver problemas frecuentes se agrega en las secciones de ejecución
(tarea 2.18 del change `project-bootstrap`).

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
