# Pendientes

Este documento registra trabajo que no debe declararse terminado sin evidencia
adicional. El detalle operativo sigue en `tasks.md`.

## Validaciones externas

- Ejecutar un análisis real contra un pull request de GitHub accesible en modo
  solo lectura.
- Configurar un proveedor LLM mediante una variable de entorno y verificar un
  análisis estructurado end-to-end.
- Documentar un segundo perfil/proveedor y sus pruebas contractuales.
- Ejecutar diez análisis controlados y registrar detección, parche aplicable,
  validación, decisión, latencia, tokens, costo y falsos positivos.

## Sandbox y validación

- Ejecutar el flujo integrado que aplica un parche al workspace candidate y
  demostrar fail-before/pass-after a través del `DockerRunner`.
- Completar pruebas de seguridad del runner: lectura de variables de entorno,
  fork bomb limitado, timeout, traversal, comando no permitido y archivo grande.
- Verificar la clasificación de errores de importación, sintaxis y dependencias
  contra ejecuciones reales del runner.

## GitHub y contexto

- Ampliar pruebas simuladas de GitHub para paginación, 401/403/404, repositorio
  privado sin token y cambio de SHA durante el análisis.
- Completar el selector de contexto con imports locales, tests relacionados y
  documentación inmediata; conservar el presupuesto y la evidencia actual.
- Evaluar si se requiere una integración especializada de detección de secretos.

## Calidad y operabilidad

- Medir duración por nodo, tokens, costo y métricas agregadas de resultados.
- Probar concurrencia, locks de SQLite y aislamiento simultáneo de workspaces.
- Completar revisión de privacidad de base de datos, logs, frontend y artefactos.
- Ejecutar los flujos E2E pendientes: `BLOCKED`, `READY`, `INCONCLUSIVE`,
  historial, reinicio y selector de modelo.
- Preparar el guion de presentación y ensayar fallos de GitHub, LLM, Docker,
  PR actualizado y output inválido.

## Auditoría de entrega

- Confirmar que los PRs de demostración sean accesibles.
- Verificar que el documento de decisión se mantenga dentro de cinco páginas.
- Ejecutar la auditoría final descrita en T-144 de `tasks.md`.
