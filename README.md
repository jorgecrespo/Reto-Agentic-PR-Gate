# Agentic PR Gate

Prototipo para decidir de forma trazable la transición **Pull Request -> QA**.
El LLM propone hallazgos y parches estructurados; las herramientas y la política
determinística aportan evidencia y emiten `READY`, `CONDITIONAL`, `BLOCKED` o
`INCONCLUSIVE`. No hace push, merge, reviews ni comentarios en GitHub.

## Estado verificable

El flujo implementado valida URLs, consulta GitHub en modo lectura, construye
contexto acotado, valida salidas LLM, aplica límites al parche y persiste
resultados. El ejemplo de e-commerce en `examples/demo_ecommerce/` sirve como
base de código para PRs de GitHub; la única forma de probar el prototipo es con
una URL de PR de GitHub.

## Qué entrega un análisis

El informe explica la decisión, no solo el estado final. Incluye la trazabilidad
del PR y SHA analizado, hallazgos con evidencia, corrección y test propuestos
cuando aplican, resultados de validación, reglas del gate, controles omitidos y
acciones necesarias para avanzar.

Los secretos nunca se muestran: el informe solo conserva evidencia segura como
archivo, línea y tipo de patrón. Cuando el LLM o el runner no se ejecutan, el
informe indica la causa; en ese caso no presenta tokens o costo como disponibles.

## Requisitos

- Python 3.12 y `uv`.
- Node 22 y npm.
- Docker Compose para levantar los servicios y para validación aislada.
- `OPENAI_API_KEY` solo para análisis LLM real.
- `GITHUB_TOKEN` de solo lectura solo para repositorios privados o límites de API.

## Instalación local

```bash
cp .env.example .env
./scripts/setup.sh
./scripts/migrate.sh
```

Configure las claves exclusivamente en `.env`; nunca las añada a YAML, SQLite o
un formulario web. Para desarrollo sin contenedores, ejecute en terminales
separadas:

```bash
uv run --project backend uvicorn pr_gate.main:app --reload
npm --prefix frontend run dev
```

La UI queda en `http://localhost:5173` y la API en `http://localhost:8000`.

## Docker Compose

```bash
./scripts/run.sh
```

Compose construye backend, frontend, executor y la imagen de runner. El backend
no monta el socket Docker. Solo el executor interno recibe archives efímeros y
monta ese socket para crear el runner con red deshabilitada, usuario no root,
filesystem de solo lectura y límites de recursos. El executor no publica puertos
al host; los servicios tienen capacidades Linux eliminadas y `no-new-privileges`.
El volumen `pr-gate-data` conserva SQLite. `./scripts/cleanup.sh` destruye ese
volumen y por tanto los informes persistidos.

No se afirma aquí que una imagen se haya construido o que Docker esté disponible:
ejecute `docker compose config` y `./scripts/run.sh` en el entorno destino antes
de considerar esta vía operativa.

## Controles

```bash
./scripts/test.sh
```

Incluye formato, lint, tipos y tests backend; lint, tipos, tests y build frontend.
Los tests de integración Docker se omiten automáticamente si el daemon no está
operativo.

## Configuración y proveedores

`config/models.example.yaml` define perfiles de servidor y solo referencia el
nombre de una variable de entorno. `config/validation-profiles.yaml` fija argv,
paths y timeout; el LLM no puede elegir comandos. Actualmente el adaptador
configurado es OpenAI-compatible para el perfil `openai-small`; no se declara
compatibilidad de otros proveedores sin un adaptador y contract tests.

## Troubleshooting

- `uv` o npm ausente: instale las versiones indicadas en requisitos y repita setup.
- DB heredada sin Alembic: use una ruta nueva mediante `DATABASE_URL` o migre la
  base explícitamente; el servicio no la sobrescribe.
- Docker no disponible: la validación de código no debe degradar a ejecución local;
  el análisis debe terminar `INCONCLUSIVE`.
- `401`, `403` o rate limit de GitHub: compruebe URL, acceso del token de solo
  lectura y espere el reset indicado por GitHub.
- Error de proveedor LLM: compruebe `OPENAI_API_KEY` solo en el entorno backend;
  los errores no deben incluir la clave.

## Documentación

- `docs/architecture.md`: componentes, datos y fronteras.
- `docs/security.md`: modelo de amenazas y retención.
- `docs/providers.md`: contrato y alta de proveedores.
- `docs/limitations.md`: límites y bloqueos operativos actuales.
- `scripts/create_demo_prs.md`: guía para recrear PRs de demostración en un fork.
- `docs/challenge-decision-document.md`: documento de entrega y uso transparente de IA.
