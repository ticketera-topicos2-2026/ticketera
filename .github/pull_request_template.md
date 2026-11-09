## Resumen

<!-- Qué cambia y por qué, en español. El título del pull request va en inglés con Conventional Commits. -->

## Issue

<!--
Una de estas opciones (D-20, D-37):
- Closes #n            (resuelve la issue; para un change de OpenSpec, en el pull request de implementación)
- Refs #n              (pull request de planificación de un change de OpenSpec)
- Sin issue: cambio menor, porque ...
-->

## Uso de IA

<!--
Obligatorio (RB-05). Qué copilotos usaste y para qué (por ejemplo: «Claude Code: borrador de los tests y del
endpoint; revisé y ajusté el código»), o «No se usó IA». Sin esta sección completa el pull request no se aprueba.
-->

## Cómo probarlo

<!-- Comandos o pasos para verificar el cambio, siempre dentro de los contenedores (D-12). -->

## Checklist

- [ ] La rama se llama `feature/<change-o-tema>` (RB-01).
- [ ] El título sigue Conventional Commits, en inglés: `tipo(alcance): resumen` (DS-21).
- [ ] Si cambia comportamiento, el commit `test(...)` en rojo está antes del `feat(...)` o `fix(...)` (RB-12).
- [ ] La descripción referencia la issue con `Closes #n` o `Refs #n`, o explica por qué no hay issue (D-20, D-37).
- [ ] La sección «Uso de IA» está completa (RB-05).
- [ ] No incluye secretos ni el archivo `.env` (RB-02).
