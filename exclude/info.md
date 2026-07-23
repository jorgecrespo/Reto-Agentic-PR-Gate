# Guía rápida del proyecto

Este documento describe el árbol relevante del repositorio y las clases, funciones y rutas definidas actualmente. Se excluyen artefactos generados (`.venv/`, `node_modules/`, `dist/`, caches y la base SQLite local).

## Árbol

```text
.
├── AGENTS.md                         # Reglas de trabajo del agente
├── spec.md                           # Requisitos del producto
├── plan.md                           # Plan arquitectónico
├── tasks.md                          # Backlog y milestones
├── README.md                         # Instalación, ejecución y validación
├── info.md                           # Esta guía
├── .env.example                      # Variables de entorno no sensibles
├── .editorconfig                     # Convenciones de formato
├── .gitignore                        # Archivos excluidos de Git
├── docker-compose.yml                # Servicios backend, frontend y runner
├── config/
│   ├── models.example.yaml           # Perfil OpenAI habilitable
│   ├── validation-profiles.yaml      # Comandos allowlist de validación
│   └── policies/qa-gate-v1.yaml      # Reglas versionadas del gate
├── docs/
│   ├── architecture.md               # Resumen de capas
│   ├── security.md                   # Modelo de seguridad
│   └── decisions/                    # ADRs principales
├── backend/
│   ├── pyproject.toml                # Dependencias y tooling Python
│   ├── Dockerfile                    # Imagen de la API
│   ├── runner.Dockerfile             # Imagen aislada pytest/ruff
│   ├── src/pr_gate/
│   │   ├── main.py                   # FastAPI y orquestación HTTP
│   │   ├── domain/
│   │   │   ├── types.py              # Value objects y datos del gate
│   │   │   └── gate.py               # Motor de política puro
│   │   ├── application/
│   │   │   ├── models.py             # Contratos Pydantic
│   │   │   └── workflow.py           # Contexto, LLM y validación candidate
│   │   ├── graph/builder.py          # Grafo LangGraph mínimo
│   │   └── infrastructure/
│   │       ├── database.py           # SQLite/SQLAlchemy
│   │       ├── github.py             # GitHub REST read-only
│   │       ├── llm.py                # Adaptador OpenAI
│   │       ├── patches.py            # Validación de unified diffs
│   │       ├── runner.py             # Sandbox Docker
│   │       └── workspaces.py         # Snapshots y workspaces efímeros
│   └── tests/
│       ├── unit/                     # Gate, API, parser, graph, DB y contexto
│       └── integration/              # Runner Docker
├── frontend/
│   ├── package.json                  # Dependencias y scripts Vite
│   ├── Dockerfile                    # Build y publicación estática
│   └── src/
│       ├── main.tsx                  # React, rutas y consultas HTTP
│       └── styles.css                # Estilos de la interfaz
└── examples/demo_ecommerce/
    ├── app/domain.py                 # Productos y repositorio
    ├── app/orders.py                 # Cálculo seguro de órdenes
    └── tests/test_orders.py          # Regresión de manipulación de precio
```

## Backend

### `backend/src/pr_gate/domain/types.py`

- `class DecisionStatus(StrEnum)`: estados finales permitidos: `READY`, `CONDITIONAL`, `BLOCKED` e `INCONCLUSIVE`.
- `class RuleOutcome(StrEnum)`: resultado individual de una regla: `PASS`, `FAIL` o `UNKNOWN`.
- `class Severity(StrEnum)`: severidades aceptadas para hallazgos.
- `class AcceptanceStatus(StrEnum)`: resultado de un criterio de aceptación.
- `class PullRequestRef`: referencia normalizada de un PR GitHub.
  - `parse(cls, raw_url: str) -> PullRequestRef`: valida y descompone una URL `github.com/{owner}/{repo}/pull/{number}`.
- `class GateFacts`: conjunto inmutable de hechos verificados que consume el gate.
- `class GateRuleResult`: resultado y evidencia asociada a una regla de política.
- `class GateDecision`: decisión final con reglas evaluadas.
  - `blocking_reasons -> tuple[GateRuleResult, ...]`: devuelve las reglas que fallaron.
  - `not_evaluated_rules -> tuple[GateRuleResult, ...]`: devuelve las reglas sin evidencia suficiente.

### `backend/src/pr_gate/domain/gate.py`

- `_result(rule_id: str, value: bool | None, message: str) -> GateRuleResult`: transforma un booleano verificable en `PASS`, `FAIL` o `UNKNOWN`.
- `evaluate_quality_gate(facts: GateFacts, policy_version: str = "1.0.0") -> GateDecision`: evalúa GATE-001 a GATE-014 y aplica la precedencia `INCONCLUSIVE` > `BLOCKED` > `CONDITIONAL` > `READY`.

### `backend/src/pr_gate/application/models.py`

- `class AcceptanceCriterionInput(BaseModel)`: criterio recibido al iniciar un análisis.
- `class CreateAnalysisInput(BaseModel)`: body de `POST /api/v1/analyses`.
- `class FindingOutput(BaseModel)`: hallazgo estructurado que debe devolver el LLM.
- `class AnalysisOutput(BaseModel)`: resumen y lista de hallazgos del análisis LLM.
- `class FixOutput(BaseModel)`: parche de código, parche de regresión y paths modificados propuestos por el LLM.

### `backend/src/pr_gate/application/workflow.py`

- `class ValidationEvidence`: resultados determinísticos de baseline, candidate, suite y lint.
- `class WorkflowEvidence`: contexto, salida LLM, corrección, validaciones y limitaciones de una ejecución.
- `build_context(snapshot: PullRequestSnapshot, max_characters: int = 40_000) -> tuple[str, bool]`: prepara un contexto limitado, excluye paths sensibles y redacta secretos detectados.
- `run_candidate_validation(snapshot: PullRequestSnapshot, fix: FixOutput, profile: dict[str, Any]) -> ValidationEvidence`: valida los diffs, crea dos workspaces, aplica test/parche y ejecuta comandos administrados en Docker.
- `gather_evidence(snapshot: PullRequestSnapshot, profile: dict[str, Any]) -> WorkflowEvidence`: coordina saneamiento, análisis OpenAI, propuesta de fix y validación; devuelve limitaciones explícitas si no hay evidencia.

### `backend/src/pr_gate/graph/builder.py`

- `class AnalysisState(TypedDict)`: estado serializable usado por el grafo básico.
- `validate_request(state: AnalysisState) -> AnalysisState`: valida la URL de entrada y registra un error estructurado.
- `fetch_pull_request(state: AnalysisState) -> AnalysisState`: obtiene metadata y SHA del PR mediante GitHub.
- `apply_quality_gate(state: AnalysisState) -> AnalysisState`: aplica el gate usando hechos del estado.
- `route_after_validation(state: AnalysisState) -> str`: enruta una entrada inválida directamente al gate.
- `build_graph() -> Any`: construye y compila el `StateGraph` dirigido.

### `backend/src/pr_gate/infrastructure/github.py`

- `class GitHubError(RuntimeError)`: error seguro y accionable de GitHub.
- `class PullRequestSnapshot`: metadata inmutable del PR fijada a SHAs y archivos.
- `class GitHubClient`: adaptador HTTPX de solo lectura.
  - `__init__(self, token: str | None = None) -> None`: usa el token explícito o `GITHUB_TOKEN`.
  - `_headers(self) -> dict[str, str]`: crea headers de API y autenticación.
  - `fetch_snapshot(self, ref: PullRequestRef) -> PullRequestSnapshot`: obtiene PR y archivos paginados; rechaza diffs incompletos.
  - `fetch_current_head_sha(self, ref: PullRequestRef) -> str`: consulta el SHA actual para detectar cambios durante el análisis.

### `backend/src/pr_gate/infrastructure/llm.py`

- `class LLMError(RuntimeError)`: representa una respuesta o configuración LLM no utilizable.
- `class OpenAILLMGateway`: adaptador OpenAI con JSON validado.
  - `__init__(self, model: str = "gpt-4.1-mini") -> None`: requiere `OPENAI_API_KEY` y crea el cliente con timeout/reintentos.
  - `analyze(self, context: str) -> AnalysisOutput`: solicita hallazgos JSON sobre contexto no confiable delimitado.
  - `propose_fix(self, context: str) -> FixOutput`: solicita patch y test de regresión JSON.
  - `_json(self, instructions: str, context: str) -> str`: llama Responses API y exige un objeto JSON.

### `backend/src/pr_gate/infrastructure/patches.py`

- `class PatchValidationError(ValueError)`: patch inválido o fuera de alcance.
- `validate_patch_shape(patch: str, allowed_prefixes: tuple[str, ...]) -> tuple[str, ...]`: exige unified diff, rechaza binarios/traversal y valida paths permitidos.

### `backend/src/pr_gate/infrastructure/runner.py`

- `class CommandResult`: exit code, output limitado, timeout y estado de infraestructura de un comando.
- `class DockerRunner`: ejecuta únicamente argv definido por configuración, nunca por el LLM.
  - `__init__(self, image: str = "pr-gate-runner:latest", timeout_seconds: int = 120) -> None`: configura imagen y timeout.
  - `run(self, workspace: Path, command_name: str, command: tuple[str, ...]) -> CommandResult`: ejecuta Docker sin red, no root, root filesystem read-only, `/tmp` temporal y límites de CPU/memoria/PIDs.

### `backend/src/pr_gate/infrastructure/workspaces.py`

- `class WorkspaceError(RuntimeError)`: error al preparar o aplicar en un workspace aislado.
- `class Workspaces`: paths raíz, baseline y candidate temporales.
- `class WorkspaceManager`: descarga y manipula snapshots sin tocar el repositorio original.
  - `prepare(self, snapshot: PullRequestSnapshot) -> Workspaces`: descarga zipball por SHA, verifica extracción y duplica baseline/candidate.
  - `_extract_archive(archive_path: Path, target: Path) -> Path`: evita zip-slip y localiza el directorio raíz del archive.
  - `apply_patch(workspace: Path, patch: str) -> bool`: valida con `git apply --check` y aplica el patch en el workspace.
  - `cleanup(workspaces: Workspaces | None) -> None`: elimina workspaces efímeros.

### `backend/src/pr_gate/infrastructure/database.py`

- `class Base(DeclarativeBase)`: base ORM SQLAlchemy.
- `class AnalysisRecord(Base)`: tabla `analysis_runs` con estado, perfil, SHA, reporte y timestamps.
- `class ValidationRecord(Base)`: tabla `validation_runs` con evidencia resumida por comando.
- `class AnalysisStore`: repositorio SQLite actual.
  - `__init__(self, database_url: str | None = None) -> None`: crea engine, directorio SQLite y tablas.
  - `create(self, pull_request_url: str, model_profile_id: str, validation_profile_id: str) -> AnalysisRecord`: persiste un análisis `PENDING`.
  - `get(self, analysis_id: str) -> AnalysisRecord | None`: recupera una ejecución.
  - `list(self) -> list[AnalysisRecord]`: lista ejecuciones recientes.
  - `finish(self, analysis_id: str, status: str, report: Mapping[str, object], error: str | None = None) -> None`: guarda decisión, reporte o error y hora final.
  - `save_validation(self, analysis_id: str, phase: str, result: object) -> None`: guarda extractos limitados del runner.

### `backend/src/pr_gate/main.py`

- `class AnalysisCreated(BaseModel)`: respuesta breve de creación asíncrona.
- `_load_yaml(relative_path: str) -> dict[str, Any]`: carga configuración YAML relativa a la raíz.
- `_run_analysis(analysis_id: str, request: CreateAnalysisInput) -> None`: tarea background que obtiene PR, genera evidencia, persiste validaciones, verifica SHA y calcula el gate.
- `lifespan(_: FastAPI) -> Any`: lifecycle actual de FastAPI.
- `live() -> dict[str, str]`: endpoint `GET /health/live`.
- `ready() -> dict[str, str]`: endpoint `GET /health/ready`.
- `models() -> dict[str, object]`: endpoint `GET /api/v1/config/models`; omite nombres de variables secretas.
- `validation_profiles() -> dict[str, object]`: endpoint de perfiles de validación.
- `policy() -> dict[str, object]`: endpoint de política configurada.
- `create_analysis(request: CreateAnalysisInput, response: Response) -> AnalysisCreated`: valida entrada, crea el run e inicia la tarea; responde `202`.
- `list_analyses() -> list[dict[str, object]]`: endpoint de historial.
- `get_analysis(analysis_id: str) -> dict[str, object]`: endpoint de informe persistido.
- `stream_analysis(analysis_id: str) -> StreamingResponse`: SSE que comunica cambios de estado hasta finalizar.

## Frontend

### `frontend/src/main.tsx`

- `request<T>(path: string, options?: RequestInit) -> Promise<T>`: cliente `fetch` que convierte errores HTTP en `Error`.
- `Header()`: navegación global y marca de operación solo lectura.
- `NewAnalysis()`: formulario para iniciar un análisis con URL de PR y perfiles iniciales.
- `Decision({ status }: { status: Status })`: badge visual accesible para un estado de gate.
- `Report()`: consulta el informe, hace polling cuando está `PENDING` y muestra reglas/evidencia.
- `Evidence({ title, value }: { title: string; value: unknown })`: representa JSON escapado de hallazgos, patch, validaciones o criterios.
- `History()`: lista análisis persistidos y enlaza al informe.
- `App()`: define las rutas `/`, `/analyses` y `/analyses/:id`.
- `createRoot(...).render(...)`: inicia React Router y TanStack Query.

### `frontend/src/styles.css`

No contiene funciones. Define la identidad visual, layout responsive, badges de estado y el visor `.evidence` de contenido escapado.

## Demo e-commerce

### `examples/demo_ecommerce/app/domain.py`

- `class Product`: producto con identificador, precio de catálogo y descripción opcional.
- `class OrderItemRequest`: item de request que incluye un precio no confiable enviado por cliente.
- `class ProductRepository`:
  - `__init__(self, products: list[Product]) -> None`: indexa productos por ID.
  - `get(self, product_id: str) -> Product | None`: obtiene el producto de catálogo.

### `examples/demo_ecommerce/app/orders.py`

- `create_order_total(items: list[OrderItemRequest], products: ProductRepository) -> Decimal`: valida cantidad y producto, y calcula el total usando siempre `product.price`, no `item.unit_price`.

### `examples/demo_ecommerce/tests/test_orders.py`

- `test_uses_catalog_price_not_client_price() -> None`: prueba de regresión que intenta enviar precio `1` para un producto de precio `100` y exige total `200`.

## Pruebas

- `tests/unit/test_gate.py`: precedencia y reglas principales del quality gate.
- `tests/unit/test_pull_request_ref.py`: URLs GitHub válidas e inválidas.
- `tests/unit/test_api.py`: health checks y rechazo de URL inválida.
- `tests/unit/test_graph.py`: routing del grafo mínimo.
- `tests/unit/test_patches.py`: aceptación y rechazo de unified diffs.
- `tests/unit/test_workflow.py`: redacción de secretos y exclusión de `.env`.
- `tests/unit/test_database.py`: persistencia básica de validaciones.
- `tests/integration/test_docker_runner.py`: sandbox Docker y bloqueo de red.

## Archivos declarativos y de operación

- `config/models.example.yaml`: declara `openai-small` con `gpt-4.1-mini` sin guardar la key.
- `config/validation-profiles.yaml`: define paths y comandos permitidos del perfil `python-demo`.
- `config/policies/qa-gate-v1.yaml`: lista reglas y estados esperados al fallar.
- `backend/pyproject.toml`: dependencias Python, Ruff, pytest y mypy.
- `backend/Dockerfile`: imagen que sirve FastAPI.
- `backend/runner.Dockerfile`: imagen no root con pytest y Ruff para código no confiable.
- `frontend/package.json`: scripts Vite, lint, build y typecheck.
- `frontend/Dockerfile`: build estático con Nginx.
- `docker-compose.yml`: composición de frontend, backend, volumen SQLite y construcción del runner.
