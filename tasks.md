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

- [x] Crear estructura `backend/`, `frontend/`, `config/`, `examples/`, `docs/` y `scripts/`.
- [x] Agregar `.gitignore`, `.editorconfig` y `.env.example`.
- [x] Crear README inicial con estado del proyecto.
- [x] Verificar que no se versionan secretos.

**Terminado cuando:** la estructura existe, Git está limpio y los archivos de gobierno están en la raíz. [x]

## T-002 — Registrar decisiones iniciales

- [x] Crear `docs/decisions/ADR-001-workflow-langgraph.md`.
- [x] Crear `ADR-002-deterministic-gate.md`.
- [x] Crear `ADR-003-read-only-github.md`.
- [x] Crear `ADR-004-sandbox-runner.md`.
- [x] Crear `ADR-005-configurable-llm.md`.

**Terminado cuando:** cada ADR incluye contexto, decisión, consecuencias y alternativas descartadas. [x]

## T-003 — Definir versiones y lockfiles

- [x] Elegir Python 3.12.
- [x] Elegir versiones vigentes de FastAPI, LangGraph, Pydantic, SQLAlchemy y Alembic.
- [x] Elegir React 19.x, TypeScript y Vite.
- [x] Configurar lockfiles.
- [x] Documentar cualquier dependencia multi-proveedor.
- [x] Agregar herramienta de auditoría de dependencias.

**Terminado cuando:** instalaciones reproducibles funcionan en una máquina limpia o contenedor. [x]

### Milestone M0

- [x] Proyecto inicial reproducible.
- [x] Decisiones principales documentadas.

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

- [x] Crear enums de severidad, validación y decisión.
- [x] Crear entidades inmutables donde corresponda.
- [x] Crear value objects para URL, SHA y versión.
- [x] Agregar validaciones.

**Tests:** casos válidos e inválidos.

## T-021 — Implementar parser de URL de GitHub PR

- [x] Aceptar solo formato esperado.
- [x] Extraer owner, repo y number.
- [x] Rechazar hosts y paths inválidos.
- [x] Normalizar URL.

**Tests:** públicos, privados, URL con query, URL inválida y path traversal.

## T-022 — Diseñar facts del gate

- [x] Crear `GateFacts`.
- [x] Crear `GateRuleResult`.
- [x] Crear `GateDecision`.
- [x] Definir `PASS`, `FAIL`, `UNKNOWN`.

## T-023 — Implementar política determinística v1

- [x] Implementar reglas GATE-001 a GATE-015.
- [x] Implementar precedencia.
- [x] Devolver evidence IDs.
- [x] Devolver acciones requeridas.
- [x] No importar LLM ni infraestructura.

**Tests obligatorios:**

- [x] READY.
- [x] CONDITIONAL.
- [x] BLOCKED.
- [x] INCONCLUSIVE.
- [x] tests no ejecutados nunca produce READY.
- [x] hallazgo crítico produce BLOCKED.
- [x] criterio obligatorio unknown produce INCONCLUSIVE.
- [x] secreto produce BLOCKED.

## T-024 — Cargar política YAML

- [x] Definir schema.
- [x] Validar IDs únicos.
- [x] Calcular checksum y versión.
- [x] Fallar al iniciar si la política es inválida.

### Milestone M2

- [x] El gate funciona sin LLM, GitHub ni DB.
- [x] Cobertura alta sobre reglas críticas.

---

# M3 — SQLite y repositorios

## T-030 — Configurar SQLAlchemy y Alembic

- [x] Crear engine SQLite.
- [x] Activar foreign keys.
- [x] Crear session management.
- [x] Crear migración inicial.

## T-031 — Crear tablas

- [x] `pull_requests`.
- [x] `pr_snapshots`.
- [x] `analysis_runs`.
- [x] `findings`.
- [x] `candidate_fixes`.
- [x] `validation_runs`.
- [x] `acceptance_evaluations`.
- [x] `gate_decisions`.
- [x] `run_events`.

## T-032 — Implementar repositorios

- [x] Crear interfaces.
- [x] Crear adaptadores SQLAlchemy.
- [x] Implementar creación de análisis.
- [x] Implementar guardado incremental.
- [x] Implementar informe agregado.
- [x] Implementar historial paginado.

## T-033 — Probar persistencia

- [x] Migración desde cero.
- [x] CRUD de análisis.
- [x] rollback ante error.
- [x] historial tras recrear aplicación.
- [x] no persistencia de secretos.

### Milestone M3

- [x] Informe completo puede persistirse y recuperarse.

---

# M4 — LangGraph vertical slice con fakes

## T-040 — Crear estado del grafo

- [x] Definir `AnalysisState`.
- [x] Usar estructuras serializables.
- [x] Definir errores tipados.
- [x] Definir eventos acumulables.

## T-041 — Crear puertos y fakes

- [x] `PullRequestProvider`.
- [x] `LLMGateway`.
- [x] `SandboxRunner`.
- [x] `AnalysisRepository`.
- [x] `EventPublisher`.
- [x] Implementaciones fake determinísticas.

## T-042 — Crear nodos mínimos

- [x] `validate_request`.
- [x] `fetch_pull_request`.
- [x] `analyze_change`.
- [x] `generate_candidate_fix`.
- [x] `run_baseline_regression`.
- [x] `run_candidate_validation`.
- [x] `apply_quality_gate`.
- [x] `persist_report`.
- [x] `finalize`.

## T-043 — Construir grafo y routing

- [x] Camino exitoso.
- [x] Entrada inválida.
- [x] GitHub inaccesible.
- [x] No finding.
- [x] Patch inválido.
- [x] Infraestructura fallida.
- [x] Limpieza final.

## T-044 — Probar grafo

- [x] Caso READY fake.
- [x] Caso BLOCKED fake.
- [x] Caso INCONCLUSIVE fake.
- [x] Eventos en orden.
- [x] Persistencia final.
- [x] Nodos unitarios.

### Milestone M4

- [x] Un análisis fake recorre backend completo y queda persistido.

---

# M5 — API y frontend vertical slice

## T-050 — Crear API de configuración

 - [x] `GET /config/models`.
 - [x] `GET /config/validation-profiles`.
 - [x] `GET /config/policy`.
 - [x] No exponer variables secretas.

## T-051 — Crear API de análisis

 - [x] `POST /analyses`.
 - [x] `GET /analyses`.
 - [x] `GET /analyses/{id}`.
 - [x] errores RFC 7807 o formato consistente.
 - [x] respuesta `202 Accepted`.

## T-052 — Gestionar ejecución en background

 - [x] Crear servicio de ejecución.
 - [x] Detectar runs huérfanos al iniciar.
 - [x] Evitar duplicados accidentales.
 - [x] Propagar correlation ID.

## T-053 — Implementar eventos

 - [x] Guardar eventos.
 - [x] Exponer SSE.
 - [x] Agregar polling fallback.
 - [x] Limitar reconexiones.

## T-054 — Generar tipos frontend

 - [x] Exponer OpenAPI.
 - [x] Generar cliente o tipos.
 - [x] Evitar duplicación manual.

## T-055 — Pantalla de nuevo análisis

 - [x] URL.
 - [x] selector de modelo.
 - [x] perfil de validación.
 - [x] editor de criterios.
 - [x] validaciones.
 - [x] mensajes de error.

## T-056 — Pantalla de progreso

 - [x] Etapa actual.
 - [x] eventos resumidos.
 - [x] estados loading/error.
 - [x] reconexión.
 - [x] redirección al informe final.

## T-057 — Pantalla de informe

 - [x] banner de decisión.
 - [x] hallazgos.
 - [x] parche.
 - [x] before/after.
 - [x] criterios.
 - [x] reglas.
 - [x] métricas.
 - [x] limitaciones.

## T-058 — Historial

 - [x] listado.
 - [x] filtros básicos.
 - [x] navegación a informe.
 - [x] estado vacío.

## T-059 — Tests frontend

 - [x] formulario.
 - [x] decisión BLOCKED.
 - [x] decisión INCONCLUSIVE.
 - [x] evidencia.
 - [x] flujo E2E simulado.

### Milestone M5

 - [x] Demo full stack funciona con adaptadores fake.

---

# M6 — GitHub real

## T-060 — Implementar cliente HTTPX

- [x] headers de API.
- [x] timeout.
- [x] auth opcional.
- [x] rate limit.
- [x] retries acotados.
- [x] error mapping.
- [x] redacción de token.

## T-061 — Obtener snapshot

- [x] PR.
- [x] archivos paginados.
- [x] commits.
- [x] checks.
- [x] base SHA.
- [x] head SHA.
- [x] draft.
- [x] detección de diff truncado.

## T-062 — Descargar código por SHA

- [x] archive o clone controlado.
- [x] sin hooks.
- [x] sin submódulos.
- [x] sin LFS.
- [x] checksum.
- [x] limpieza.

## T-063 — Verificar actualidad

- [x] consultar head SHA al finalizar.
- [x] marcar PR actualizado.
- [x] producir INCONCLUSIVE si cambió.

## T-064 — Tests GitHub

- [x] respuestas simuladas.
- [ ] paginación.
- [ ] 401/403/404.
- [x] rate limit.
- [x] patch truncado.
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

- [x] máximo de archivos.
- [x] máximo total.
- [x] máximo por archivo.
- [x] informe de exclusiones.

## T-072 — Numerar y hashear evidencia

- [x] líneas estables.
- [x] content hash.
- [x] referencia archivo/línea.
- [x] fragmentos.

## T-073 — Secret scanner

- [x] patrones mínimos.
- [ ] integración opcional con herramienta especializada.
- [x] redacción.
- [x] bloqueo en diff.

## T-074 — Prompt-injection hardening

- [x] delimitar código como datos.
- [ ] prohibir herramientas dinámicas.
- [x] ignorar instrucciones contenidas en archivos.
- [x] test con comentario malicioso en código.

### Milestone M7

- [ ] Context bundle acotado, explicable y saneado.

---

# M8 — LLM configurable

## T-080 — Definir schemas

- [x] `AnalysisPrompt`.
- [x] `AnalysisOutput`.
- [x] `FindingOutput`.
- [x] `FixPrompt`.
- [x] `FixOutput`.
- [x] validaciones estrictas.

## T-081 — Definir loader de perfiles

- [x] YAML.
- [x] IDs únicos.
- [x] variables de entorno.
- [x] perfiles habilitados.
- [x] no exposición de keys.
- [x] validación al iniciar.

## T-082 — Implementar gateway

- [x] protocolo propio.
- [ ] adaptador multi-proveedor.
- [x] fake.
- [x] timeout.
- [x] retries.
- [x] error mapping.

## T-083 — Versionar prompts

- [x] análisis v1.
- [x] corrección v1.
- [x] instrucciones anti-invención.
- [x] output JSON.
- [x] evidencia obligatoria.
- [x] no chain-of-thought persistido.

## T-084 — Manejar output inválido

- [x] Pydantic.
- [x] un reintento correctivo acotado.
- [x] INCONCLUSIVE después del límite.
- [x] guardar error resumido.

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

- [x] baseline.
- [x] candidate.
- [x] paths temporales.
- [x] cleanup.
- [x] no escritura al original.

## T-091 — Validar unified diff

- [x] parse.
- [x] `git apply --check`.
- [x] paths.
- [x] tamaño.
- [x] archivos protegidos.
- [x] binarios.
- [x] traversal.
- [x] secret scan.

## T-092 — Separar parche y test

- [x] source patch.
- [x] regression patch.
- [x] archivos afectados.
- [x] hashes.

## T-093 — Crear validation profiles

- [x] Python demo.
- [x] comando de test dirigido.
- [x] suite.
- [x] lint.
- [x] timeout.
- [x] allowlist.

## T-094 — Implementar Docker runner

- [x] network none.
- [x] no root.
- [x] límites CPU/memoria/PIDs.
- [x] timeout externo.
- [x] sin secrets.
- [x] output truncado.
- [x] exit code.
- [x] cleanup.

## T-095 — Clasificar resultados

- [x] assertion failure.
- [x] syntax error.
- [x] import error.
- [x] dependency error.
- [x] timeout.
- [x] infrastructure error.
- [x] pass.

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

- [x] intento de red.
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

- [x] estado PASSED/FAILED/NOT_EVALUATED.
- [x] evidencia.
- [x] requerido/opcional.
- [x] salida estructurada.
- [x] tests.

## T-101 — Construir GateFacts

- [x] GitHub.
- [x] contexto.
- [x] hallazgos.
- [x] secretos.
- [x] baseline.
- [x] candidate.
- [x] criterios.
- [x] draft.
- [x] SHA actual.

## T-102 — Aplicar gate real

- [x] READY.
- [x] CONDITIONAL.
- [x] BLOCKED.
- [x] INCONCLUSIVE.
- [x] reasons.
- [x] warnings.
- [x] actions.
- [x] evidence IDs.

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

- [x] producto.
- [x] repositorio.
- [x] orden.
- [x] cálculo.
- [x] validaciones.
- [x] datos de prueba.
- [x] tests.

## T-111 — Crear cambio defectuoso

- [x] usar precio del request.
- [x] descripción de PR.
- [x] criterios.
- [ ] confirmar que suite previa no detecta el defecto, si esa es la historia elegida.

## T-112 — Definir corrección esperada

- [x] precio de catálogo.
- [x] producto inexistente.
- [x] cantidad positiva.
- [x] test manipulado.

## T-113 — Crear PR seguro

- [x] cambio pequeño.
- [x] tests.
- [ ] resultado READY.

## T-114 — Crear caso inconcluso

- [x] fallo controlado del runner o validación ausente.
- [ ] resultado INCONCLUSIVE.

## T-115 — Documentar creación de PRs

- [x] ramas.
- [x] commits.
- [x] títulos.
- [x] cuerpos.
- [x] URLs o placeholders.
- [x] forma de recrearlos.

### Milestone M11

- [ ] Existen tres PRs de demostración reproducibles.

**Bloqueo operativo:** faltan URLs reales de PR para cerrar la evidencia de los
tres casos de demostración. El flujo local alternativo fue eliminado para evitar
ambigüedad; el milestone sigue abierto hasta contar con PRs accesibles de GitHub.

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

- [x] logs JSON.
- [x] correlation ID.
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

- [x] backend.
- [x] frontend.
- [x] runner image.
- [x] usuarios no root.
- [x] healthchecks.
- [x] imágenes pequeñas.

## T-131 — Docker Compose

- [x] backend.
- [x] frontend.
- [x] volumen SQLite.
- [x] variables.
- [x] red interna.
- [x] healthchecks.

## T-132 — Scripts

- [x] setup.
- [x] migrate.
- [x] run.
- [x] test.
- [x] demo.
- [x] cleanup.

## T-133 — README

- [x] requisitos.
- [x] instalación.
- [x] configuración.
- [x] proveedores.
- [x] GitHub token.
- [x] demo paso a paso.
- [x] tests.
- [x] troubleshooting.
- [x] limitaciones.

### Milestone M13

- [x] Otra persona puede levantar el proyecto desde cero.

**Evidencia:** `docker compose build` y `docker compose up -d` completaron; los
healthchecks de backend y frontend respondieron correctamente antes del cierre.

---

# M14 — Entrega del reto

## T-140 — Documento de decisiones

Máximo cinco páginas:

- [x] problema y capacidades.
- [x] arquitectura.
- [x] decisiones y alternativas.
- [x] costo, latencia, privacidad y operabilidad.
- [x] resultados, limitaciones y próximos pasos.
- [x] uso de IA.

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
