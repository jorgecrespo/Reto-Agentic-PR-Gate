# tasks.md

## Uso de este archivo

- Ejecutar tareas en orden salvo que una dependencia indique lo contrario.
- Marcar `[x]` únicamente cuando se cumpla la definición de terminado.
- No comenzar una fase si su milestone anterior está incompleto.
- Registrar bloqueos y decisiones debajo de la tarea correspondiente.
- Mantener el alcance definido en `spec.md`.

---

# M0 — Preparación y decisiones

## T-001 — Inicializar monorepo

- [ ] Crear estructura `backend/`, `frontend/`, `config/`, `examples/`, `docs/` y `scripts/`.
- [ ] Agregar `.gitignore`, `.editorconfig` y `.env.example`.
- [ ] Crear README inicial con estado del proyecto.
- [ ] Verificar que no se versionan secretos.

**Terminado cuando:** la estructura existe, Git está limpio y los archivos de gobierno están en la raíz.

## T-002 — Registrar decisiones iniciales

- [x] Crear `docs/decisions/ADR-001-workflow-langgraph.md`.
- [x] Crear `ADR-002-deterministic-gate.md`.
- [x] Crear `ADR-003-read-only-github.md`.
- [x] Crear `ADR-004-sandbox-runner.md`.
- [x] Crear `ADR-005-configurable-llm.md`.

**Terminado cuando:** cada ADR incluye contexto, decisión, consecuencias y alternativas descartadas. [x]

## T-003 — Definir versiones y lockfiles

- [ ] Elegir Python 3.12.
- [ ] Elegir versiones vigentes de FastAPI, LangGraph, Pydantic, SQLAlchemy y Alembic.
- [ ] Elegir React 19.x, TypeScript y Vite.
- [ ] Configurar lockfiles.
- [ ] Documentar cualquier dependencia multi-proveedor.
- [ ] Agregar herramienta de auditoría de dependencias.

**Terminado cuando:** instalaciones reproducibles funcionan en una máquina limpia o contenedor.

### Milestone M0

- [ ] Proyecto inicial reproducible.
- [ ] Decisiones principales documentadas.

---

# M1 — Tooling y CI

## T-010 — Configurar backend

- [x] Crear `pyproject.toml`.
- [x] Configurar Ruff.
- [x] Configurar mypy o pyright.
- [x] Configurar pytest y coverage.
- [x] Crear aplicación FastAPI mínima.
- [x] Agregar `/health/live` y `/health/ready`.

**Tests:** health endpoints y configuración importable.

## T-011 — Configurar frontend

- [x] Crear Vite + React 19 + TypeScript.
- [x] Activar TypeScript estricto.
- [x] Configurar ESLint.
- [x] Configurar Vitest y React Testing Library.
- [x] Configurar React Router y TanStack Query.
- [x] Crear layout mínimo.

**Tests:** render de la app y navegación básica.

## T-012 — Configurar CI

- [x] Backend lint.
- [x] Backend typecheck.
- [x] Backend tests.
- [x] Frontend lint.
- [x] Frontend typecheck.
- [x] Frontend tests.
- [x] Frontend build.
- [x] Auditoría básica de dependencias.

**Terminado cuando:** CI pasa sin secretos ni credenciales reales.

### Milestone M1

- [x] Backend y frontend compilan.
- [x] CI completamente verde.

---

# M2 — Dominio y quality gate

## T-020 — Modelar dominio

- [ ] Crear enums de severidad, validación y decisión.
- [ ] Crear entidades inmutables donde corresponda.
- [ ] Crear value objects para URL, SHA y versión.
- [ ] Agregar validaciones.

**Tests:** casos válidos e inválidos.

## T-021 — Implementar parser de URL de GitHub PR

- [ ] Aceptar solo formato esperado.
- [ ] Extraer owner, repo y number.
- [ ] Rechazar hosts y paths inválidos.
- [ ] Normalizar URL.

**Tests:** públicos, privados, URL con query, URL inválida y path traversal.

## T-022 — Diseñar facts del gate

- [ ] Crear `GateFacts`.
- [ ] Crear `GateRuleResult`.
- [ ] Crear `GateDecision`.
- [ ] Definir `PASS`, `FAIL`, `UNKNOWN`.

## T-023 — Implementar política determinística v1

- [ ] Implementar reglas GATE-001 a GATE-015.
- [ ] Implementar precedencia.
- [ ] Devolver evidence IDs.
- [ ] Devolver acciones requeridas.
- [ ] No importar LLM ni infraestructura.

**Tests obligatorios:**

- [ ] READY.
- [ ] CONDITIONAL.
- [ ] BLOCKED.
- [ ] INCONCLUSIVE.
- [ ] tests no ejecutados nunca produce READY.
- [ ] hallazgo crítico produce BLOCKED.
- [ ] criterio obligatorio unknown produce INCONCLUSIVE.
- [ ] secreto produce BLOCKED.

## T-024 — Cargar política YAML

- [ ] Definir schema.
- [ ] Validar IDs únicos.
- [ ] Calcular checksum y versión.
- [ ] Fallar al iniciar si la política es inválida.

### Milestone M2

- [ ] El gate funciona sin LLM, GitHub ni DB.
- [ ] Cobertura alta sobre reglas críticas.

---

# M3 — SQLite y repositorios

## T-030 — Configurar SQLAlchemy y Alembic

- [ ] Crear engine SQLite.
- [ ] Activar foreign keys.
- [ ] Crear session management.
- [ ] Crear migración inicial.

## T-031 — Crear tablas

- [ ] `pull_requests`.
- [ ] `pr_snapshots`.
- [ ] `analysis_runs`.
- [ ] `findings`.
- [ ] `candidate_fixes`.
- [ ] `validation_runs`.
- [ ] `acceptance_evaluations`.
- [ ] `gate_decisions`.
- [ ] `run_events`.

## T-032 — Implementar repositorios

- [ ] Crear interfaces.
- [ ] Crear adaptadores SQLAlchemy.
- [ ] Implementar creación de análisis.
- [ ] Implementar guardado incremental.
- [ ] Implementar informe agregado.
- [ ] Implementar historial paginado.

## T-033 — Probar persistencia

- [ ] Migración desde cero.
- [ ] CRUD de análisis.
- [ ] rollback ante error.
- [ ] historial tras recrear aplicación.
- [ ] no persistencia de secretos.

### Milestone M3

- [ ] Informe completo puede persistirse y recuperarse.

---

# M4 — LangGraph vertical slice con fakes

## T-040 — Crear estado del grafo

- [ ] Definir `AnalysisState`.
- [ ] Usar estructuras serializables.
- [ ] Definir errores tipados.
- [ ] Definir eventos acumulables.

## T-041 — Crear puertos y fakes

- [ ] `PullRequestProvider`.
- [ ] `LLMGateway`.
- [ ] `SandboxRunner`.
- [ ] `AnalysisRepository`.
- [ ] `EventPublisher`.
- [ ] Implementaciones fake determinísticas.

## T-042 — Crear nodos mínimos

- [ ] `validate_request`.
- [ ] `fetch_pull_request`.
- [ ] `analyze_change`.
- [ ] `generate_candidate_fix`.
- [ ] `run_baseline_regression`.
- [ ] `run_candidate_validation`.
- [ ] `apply_quality_gate`.
- [ ] `persist_report`.
- [ ] `finalize`.

## T-043 — Construir grafo y routing

- [ ] Camino exitoso.
- [ ] Entrada inválida.
- [ ] GitHub inaccesible.
- [ ] No finding.
- [ ] Patch inválido.
- [ ] Infraestructura fallida.
- [ ] Limpieza final.

## T-044 — Probar grafo

- [ ] Caso READY fake.
- [ ] Caso BLOCKED fake.
- [ ] Caso INCONCLUSIVE fake.
- [ ] Eventos en orden.
- [ ] Persistencia final.
- [ ] Nodos unitarios.

### Milestone M4

- [ ] Un análisis fake recorre backend completo y queda persistido.

---

# M5 — API y frontend vertical slice

## T-050 — Crear API de configuración

- [ ] `GET /config/models`.
- [ ] `GET /config/validation-profiles`.
- [ ] `GET /config/policy`.
- [ ] No exponer variables secretas.

## T-051 — Crear API de análisis

- [ ] `POST /analyses`.
- [ ] `GET /analyses`.
- [ ] `GET /analyses/{id}`.
- [ ] errores RFC 7807 o formato consistente.
- [ ] respuesta `202 Accepted`.

## T-052 — Gestionar ejecución en background

- [ ] Crear servicio de ejecución.
- [ ] Detectar runs huérfanos al iniciar.
- [ ] Evitar duplicados accidentales.
- [ ] Propagar correlation ID.

## T-053 — Implementar eventos

- [ ] Guardar eventos.
- [ ] Exponer SSE.
- [ ] Agregar polling fallback.
- [ ] Limitar reconexiones.

## T-054 — Generar tipos frontend

- [ ] Exponer OpenAPI.
- [ ] Generar cliente o tipos.
- [ ] Evitar duplicación manual.

## T-055 — Pantalla de nuevo análisis

- [ ] URL.
- [ ] selector de modelo.
- [ ] perfil de validación.
- [ ] editor de criterios.
- [ ] validaciones.
- [ ] mensajes de error.

## T-056 — Pantalla de progreso

- [ ] Etapa actual.
- [ ] eventos resumidos.
- [ ] estados loading/error.
- [ ] reconexión.
- [ ] redirección al informe final.

## T-057 — Pantalla de informe

- [ ] banner de decisión.
- [ ] hallazgos.
- [ ] parche.
- [ ] before/after.
- [ ] criterios.
- [ ] reglas.
- [ ] métricas.
- [ ] limitaciones.

## T-058 — Historial

- [ ] listado.
- [ ] filtros básicos.
- [ ] navegación a informe.
- [ ] estado vacío.

## T-059 — Tests frontend

- [ ] formulario.
- [ ] decisión BLOCKED.
- [ ] decisión INCONCLUSIVE.
- [ ] evidencia.
- [ ] flujo E2E simulado.

### Milestone M5

- [ ] Demo full stack funciona con adaptadores fake.

---

# M6 — GitHub real

## T-060 — Implementar cliente HTTPX

- [ ] headers de API.
- [ ] timeout.
- [ ] auth opcional.
- [ ] rate limit.
- [ ] retries acotados.
- [ ] error mapping.
- [ ] redacción de token.

## T-061 — Obtener snapshot

- [ ] PR.
- [ ] archivos paginados.
- [ ] commits.
- [ ] checks.
- [ ] base SHA.
- [ ] head SHA.
- [ ] draft.
- [ ] detección de diff truncado.

## T-062 — Descargar código por SHA

- [ ] archive o clone controlado.
- [ ] sin hooks.
- [ ] sin submódulos.
- [ ] sin LFS.
- [ ] checksum.
- [ ] limpieza.

## T-063 — Verificar actualidad

- [ ] consultar head SHA al finalizar.
- [ ] marcar PR actualizado.
- [ ] producir INCONCLUSIVE si cambió.

## T-064 — Tests GitHub

- [ ] respuestas simuladas.
- [ ] paginación.
- [ ] 401/403/404.
- [ ] rate limit.
- [ ] patch truncado.
- [ ] PR privado sin token.
- [ ] cambio de SHA.

### Milestone M6

- [ ] Un PR real puede ser ingerido de solo lectura.

---

# M7 — Contexto y seguridad previa al LLM

## T-070 — Implementar selector de archivos

- [ ] changed files.
- [ ] extensiones.
- [ ] paths permitidos.
- [ ] tests relacionados.
- [ ] imports locales.
- [ ] documentación inmediata.

## T-071 — Implementar presupuesto

- [ ] máximo de archivos.
- [ ] máximo total.
- [ ] máximo por archivo.
- [ ] prioridad.
- [ ] informe de exclusiones.

## T-072 — Numerar y hashear evidencia

- [ ] líneas estables.
- [ ] content hash.
- [ ] referencia archivo/línea.
- [ ] fragmentos.

## T-073 — Secret scanner

- [ ] patrones mínimos.
- [ ] integración opcional con herramienta especializada.
- [ ] redacción.
- [ ] bloqueo en diff.
- [ ] tests con falsos positivos conocidos.

## T-074 — Prompt-injection hardening

- [ ] delimitar código como datos.
- [ ] prohibir herramientas dinámicas.
- [ ] ignorar instrucciones contenidas en archivos.
- [ ] test con comentario malicioso en código.

### Milestone M7

- [ ] Context bundle acotado, explicable y saneado.

---

# M8 — LLM configurable

## T-080 — Definir schemas

- [ ] `AnalysisPrompt`.
- [ ] `AnalysisOutput`.
- [ ] `FindingOutput`.
- [ ] `FixPrompt`.
- [ ] `FixOutput`.
- [ ] validaciones estrictas.

## T-081 — Definir loader de perfiles

- [ ] YAML.
- [ ] IDs únicos.
- [ ] variables de entorno.
- [ ] perfiles habilitados.
- [ ] no exposición de keys.
- [ ] validación al iniciar.

## T-082 — Implementar gateway

- [ ] protocolo propio.
- [ ] adaptador multi-proveedor.
- [ ] fake.
- [ ] timeout.
- [ ] retries.
- [ ] usage.
- [ ] costo estimado.
- [ ] error mapping.

## T-083 — Versionar prompts

- [ ] análisis v1.
- [ ] corrección v1.
- [ ] instrucciones anti-invención.
- [ ] output JSON.
- [ ] evidencia obligatoria.
- [ ] no chain-of-thought persistido.

## T-084 — Manejar output inválido

- [ ] Pydantic.
- [ ] un reintento correctivo acotado.
- [ ] INCONCLUSIVE después del límite.
- [ ] guardar error resumido.

## T-085 — Contract tests de proveedores

- [ ] fake.
- [ ] al menos un proveedor real opcional.
- [ ] segundo perfil documentado.
- [ ] skip seguro sin credenciales.

### Milestone M8

- [ ] El modelo se selecciona desde la UI y produce hallazgos estructurados.

---

# M9 — Parches y runner

## T-090 — Crear workspaces

- [ ] baseline.
- [ ] candidate.
- [ ] paths temporales.
- [ ] cleanup.
- [ ] no escritura al original.

## T-091 — Validar unified diff

- [ ] parse.
- [ ] `git apply --check`.
- [ ] paths.
- [ ] tamaño.
- [ ] archivos protegidos.
- [ ] binarios.
- [ ] traversal.
- [ ] secret scan.

## T-092 — Separar parche y test

- [ ] source patch.
- [ ] regression patch.
- [ ] archivos afectados.
- [ ] hashes.

## T-093 — Crear validation profiles

- [ ] Python demo.
- [ ] comando de test dirigido.
- [ ] suite.
- [ ] lint.
- [ ] timeout.
- [ ] allowlist.

## T-094 — Implementar Docker runner

- [ ] network none.
- [ ] no root.
- [ ] límites CPU/memoria/PIDs.
- [ ] timeout externo.
- [ ] sin secrets.
- [ ] output truncado.
- [ ] exit code.
- [ ] cleanup.

## T-095 — Clasificar resultados

- [ ] assertion failure.
- [ ] syntax error.
- [ ] import error.
- [ ] dependency error.
- [ ] timeout.
- [ ] infrastructure error.
- [ ] pass.

## T-096 — Baseline regression

- [ ] aplicar solo test.
- [ ] ejecutar dirigido.
- [ ] confirmar reproducción funcional.
- [ ] rechazar fallo irrelevante.

## T-097 — Candidate validation

- [ ] aplicar source patch.
- [ ] aplicar test.
- [ ] ejecutar dirigido.
- [ ] suite.
- [ ] lint.
- [ ] secret scan.

## T-098 — Tests de seguridad del runner

- [ ] intento de red.
- [ ] intento de leer env.
- [ ] fork bomb limitado.
- [ ] timeout.
- [ ] path traversal.
- [ ] comando no permitido.
- [ ] archivo enorme.

### Milestone M9

- [ ] Se demuestra fail-before/pass-after en sandbox.

---

# M10 — Criterios y gate integrado

## T-100 — Evaluar criterios de aceptación

- [ ] estado PASSED/FAILED/NOT_EVALUATED.
- [ ] evidencia.
- [ ] requerido/opcional.
- [ ] salida estructurada.
- [ ] tests.

## T-101 — Construir GateFacts

- [ ] GitHub.
- [ ] contexto.
- [ ] hallazgos.
- [ ] secretos.
- [ ] baseline.
- [ ] candidate.
- [ ] criterios.
- [ ] draft.
- [ ] SHA actual.

## T-102 — Aplicar gate real

- [ ] READY.
- [ ] CONDITIONAL.
- [ ] BLOCKED.
- [ ] INCONCLUSIVE.
- [ ] reasons.
- [ ] warnings.
- [ ] actions.
- [ ] evidence IDs.

## T-103 — Mostrar política y trazabilidad

- [ ] versión.
- [ ] checksum.
- [ ] reglas.
- [ ] resultados.
- [ ] controles no ejecutados.

### Milestone M10

- [ ] El informe decide PR -> QA de forma explicable.

---

# M11 — Demo e-commerce

## T-110 — Crear aplicación de ejemplo

- [ ] producto.
- [ ] repositorio.
- [ ] orden.
- [ ] cálculo.
- [ ] validaciones.
- [ ] fixtures.
- [ ] tests.

## T-111 — Crear cambio defectuoso

- [ ] usar precio del request.
- [ ] descripción de PR.
- [ ] criterios.
- [ ] confirmar que suite previa no detecta el defecto, si esa es la historia elegida.

## T-112 — Definir corrección esperada

- [ ] precio de catálogo.
- [ ] producto inexistente.
- [ ] cantidad positiva.
- [ ] test manipulado.

## T-113 — Crear PR seguro

- [ ] cambio pequeño.
- [ ] tests.
- [ ] resultado READY.

## T-114 — Crear caso inconcluso

- [ ] fallo controlado del runner o validación ausente.
- [ ] resultado INCONCLUSIVE.

## T-115 — Documentar creación de PRs

- [ ] ramas.
- [ ] commits.
- [ ] títulos.
- [ ] cuerpos.
- [ ] URLs o placeholders.
- [ ] forma de recrearlos.

### Milestone M11

- [ ] Existen tres escenarios reproducibles.

---

# M12 — Endurecimiento y calidad

## T-120 — Manejo integral de errores

- [ ] códigos estables.
- [ ] mensajes accionables.
- [ ] frontend.
- [ ] logs.
- [ ] no stack traces públicos.

## T-121 — Idempotencia y concurrencia

- [ ] doble click.
- [ ] análisis duplicado.
- [ ] aislamiento de workspaces.
- [ ] SQLite locks.
- [ ] límites de concurrencia.

## T-122 — Observabilidad

- [ ] logs JSON.
- [ ] correlation ID.
- [ ] duración por nodo.
- [ ] tokens.
- [ ] costo.
- [ ] métricas de resultados.

## T-123 — Performance

- [ ] medir contexto.
- [ ] medir GitHub.
- [ ] medir LLM.
- [ ] medir tests.
- [ ] establecer límites.

## T-124 — Privacidad

- [ ] revisar DB.
- [ ] revisar logs.
- [ ] revisar frontend.
- [ ] revisar artefactos.
- [ ] documentar retención.

## T-125 — Tests E2E

- [ ] BLOCKED.
- [ ] READY.
- [ ] INCONCLUSIVE.
- [ ] historial.
- [ ] reinicio.
- [ ] selector de modelo.

### Milestone M12

- [ ] Suite verde y riesgos principales mitigados.

---

# M13 — Operabilidad

## T-130 — Dockerfiles

- [ ] backend.
- [ ] frontend.
- [ ] runner image.
- [ ] usuarios no root.
- [ ] healthchecks.
- [ ] imágenes pequeñas.

## T-131 — Docker Compose

- [ ] backend.
- [ ] frontend.
- [ ] volumen SQLite.
- [ ] variables.
- [ ] red interna.
- [ ] healthchecks.

## T-132 — Scripts

- [ ] setup.
- [ ] migrate.
- [ ] run.
- [ ] test.
- [ ] demo.
- [ ] cleanup.

## T-133 — README

- [ ] requisitos.
- [ ] instalación.
- [ ] configuración.
- [ ] proveedores.
- [ ] GitHub token.
- [ ] demo paso a paso.
- [ ] tests.
- [ ] troubleshooting.
- [ ] limitaciones.

### Milestone M13

- [ ] Otra persona puede levantar el proyecto desde cero.

---

# M14 — Entrega del reto

## T-140 — Documento de decisiones

Máximo cinco páginas:

- [ ] problema y capacidades.
- [ ] arquitectura.
- [ ] decisiones y alternativas.
- [ ] costo, latencia, privacidad y operabilidad.
- [ ] resultados, limitaciones y próximos pasos.
- [ ] uso de IA.

## T-141 — Medición controlada

- [ ] ejecutar al menos diez análisis.
- [ ] registrar detección.
- [ ] patch apply.
- [ ] validación.
- [ ] decisión.
- [ ] latencia.
- [ ] costo.
- [ ] falsos positivos.

## T-142 — Preparar presentación

- [ ] contexto 3 min.
- [ ] arquitectura 4 min.
- [ ] demo 9 min.
- [ ] condiciones/riesgos 3 min.
- [ ] limitaciones 1 min.
- [ ] margen para preguntas.

## T-143 — Ensayar fallos

- [ ] GitHub no disponible.
- [ ] LLM no disponible.
- [ ] Docker no disponible.
- [ ] PR actualizado.
- [ ] output inválido.
- [ ] demo con informe previamente persistido sin simular resultados nuevos.

## T-144 — Auditoría final

- [ ] no secretos.
- [ ] CI verde.
- [ ] enlaces correctos.
- [ ] migraciones.
- [ ] Docker Compose.
- [ ] README desde cero.
- [ ] PRs accesibles.
- [ ] documento <= 5 páginas.
- [ ] todo el código crítico comprendido por el candidato.

### Milestone final

- [ ] El prototipo demuestra las dos capacidades seleccionadas.
- [ ] La demo es reproducible.
- [ ] La decisión es trazable.
- [ ] El candidato puede explicar cada decisión y limitación.

---

# Backlog posterior al reto

No implementar antes del milestone final:

- [ ] comentarios en GitHub con aprobación humana;
- [ ] GitHub App;
- [ ] colas distribuidas;
- [ ] PostgreSQL;
- [ ] despliegue Cloud Run;
- [ ] autenticación OAuth;
- [ ] soporte JavaScript/Java;
- [ ] políticas por equipo;
- [ ] dashboard de KPIs;
- [ ] feedback loop;
- [ ] evaluación comparativa de modelos;
- [ ] human override persistido;
- [ ] integración con Azure DevOps.
