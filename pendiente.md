# Pendientes

Este documento registra trabajo que no debe declararse terminado sin evidencia
adicional. El detalle operativo sigue en `tasks.md`.

## Verificación de los PRs de demostración

La matriz de ocho PRs no está validada completamente. Las ejecuciones se hicieron
contra URLs públicas reales y no se deben presentar como una demostración completa
de las dos capacidades hasta resolver los puntos siguientes.

| PR | Resultado esperado | Resultado observado | Estado de verificación |
| --- | --- | --- | --- |
| `#1` cambio de negocio sin tests | `CONDITIONAL` | `INCONCLUSIVE` por patches no aplicables | El LLM y executor corrieron; falta un patch aplicable. |
| `#2` cobertura adicional | `READY` | `INCONCLUSIVE` por patch inválido | El LLM y executor corrieron; falta un patch aplicable. |
| `#3` draft con cambio compatible | `CONDITIONAL` | `INCONCLUSIVE` | Sin error de infraestructura; revisar la decisión para este escenario. |
| `#4` refactor seguro | `READY` | `BLOCKED` | Revisar la regla o evidencia que bloquea el escenario esperado. |
| `#5` cambio de SHA | `INCONCLUSIVE` | `BLOCKED` | El `head_sha` no cambió durante el análisis; no verifica el escenario esperado. |
| `#6` secreto de prueba | `BLOCKED` | `BLOCKED` por `GATE-006` | Verificado: evidencia redactada, acciones y LLM omitido intencionalmente. |
| `#7` precio controlado por cliente | `BLOCKED` | `READY` para el candidate | Verificado fail-before/pass-after, suite y lint en executor; revisar si el informe debe exponer por separado el estado del PR original y el candidate. |
| `#8` diff inaccesible | `INCONCLUSIVE` | `INCONCLUSIVE` por patch no aplicable | El diff se recuperó; el escenario no genera evidencia incompleta. |

### Correcciones necesarias

- Mantener diagnóstico seguro del fallo LLM: tipo de contrato/proveedor y etapa,
  sin persistir prompt, código completo, API key ni razonamiento interno.
- Mejorar los casos en que el LLM propone patches no aplicables (`#1`, `#2`, `#8`)
  sin ampliar permisos ni aceptar cambios ambiguos.
- Separar en el informe el estado del PR original y la validación del candidate;
  `#7` demuestra que el candidate es seguro, pero el PR original contiene el defecto.
- Repetir `#5` mientras el `head_sha` cambia durante el análisis y confirmar que
  `GATE-015` aporta la evidencia del SHA desactualizado.
- Rediseñar `#8` para que GitHub entregue un diff incompleto, excesivo o
  inaccesible al adaptador, y confirmar que el resultado sea `INCONCLUSIVE` por
  recuperación de contexto, no por LLM.
- Registrar por PR: URL, SHA base, SHA analizado, resultado esperado/observado,
  hallazgo, parche, resultado baseline/candidate, suite, tokens/costo cuando el
  LLM se ejecute y causa de cualquier control omitido.

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
