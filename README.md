# Agentic PR Gate

Prototipo para decidir de forma trazable la transición **Pull Request -> QA**.
El LLM propone hallazgos y parches estructurados; las herramientas y la política
determinística aportan evidencia y emiten `READY`, `CONDITIONAL`, `BLOCKED` o
`INCONCLUSIVE`. No hace push, merge, reviews ni comentarios en GitHub.

## Requisitos

- **Docker con Docker Compose y el daemon de Docker corriendo.** Es el único
  requisito para usar el prototipo: la validación del código del PR se ejecuta
  en contenedores efímeros creados por el propio servicio, por lo que Docker
  debe estar activo antes de arrancar. Verifíquelo con `docker info`.
- Opcional: `GEMINI_API_KEY` para el perfil Gemini por defecto, `OPENAI_API_KEY`
  para el perfil OpenAI y `GITHUB_TOKEN` de solo lectura para repositorios
  privados o límites de API. Sin claves el sistema arranca igual y cada
  análisis termina `INCONCLUSIVE` con la razón visible en el informe.

## Uso

```bash
docker compose up --build
```

Un solo comando. Cuando termine la construcción, abra `http://localhost:5173`,
pegue la URL de un pull request de GitHub
(`https://github.com/{owner}/{repo}/pull/{number}`), seleccione el perfil de
modelo y el de validación, y siga el progreso hasta el informe. Gemini aparece
como opción por defecto. La única forma de probar el prototipo es con una URL
de PR de GitHub.

En el primer arranque la base SQLite se crea vacía y se migra automáticamente;
no hay pasos de instalación ni de migración manual. El volumen `pr-gate-data`
conserva los informes entre reinicios. Para volver a una base vacía (por
ejemplo, antes de una demo):

```bash
docker compose down -v
```

Atención: ese comando destruye el volumen y, por tanto, todos los informes
persistidos.

### Claves (opcional)

```bash
cp .env.example .env
# edite .env y complete GEMINI_API_KEY, OPENAI_API_KEY y/o GITHUB_TOKEN
docker compose up --build
```

Las claves se leen únicamente del entorno; nunca se guardan en SQLite, YAML,
logs ni respuestas HTTP.

## Qué entrega un análisis

El informe explica la decisión, no solo el estado final. Incluye la trazabilidad
del PR y SHA analizado, hallazgos con evidencia, corrección y test propuestos
cuando aplican, resultados de validación, reglas del gate, controles omitidos y
acciones necesarias para avanzar.

Los secretos nunca se muestran: el informe solo conserva evidencia segura como
archivo, línea y tipo de patrón. Cuando el LLM o el runner no se ejecutan, el
informe indica la causa; en ese caso no presenta tokens o costo como disponibles.

## Cómo funciona

Compose construye cuatro servicios: frontend (nginx publicado en `:5173`, que
proxifica `/api/` al backend), backend (FastAPI en `:8000`, con el workflow
LangGraph y la política determinística), un executor interno y la imagen de
runner. El backend no monta el socket Docker: solo el executor recibe archives
efímeros y monta ese socket para crear el runner con red deshabilitada, usuario
no root, filesystem de solo lectura y límites de recursos. El executor no
publica puertos al host; los servicios tienen capacidades Linux eliminadas y
`no-new-privileges`. Los comandos de validación salen de
`config/validation-profiles.yaml`; el LLM nunca elige qué se ejecuta.

## Configuración y proveedores

`config/models.example.yaml` define perfiles de servidor y solo referencia el
nombre de una variable de entorno. `config/validation-profiles.yaml` fija argv,
paths y timeout. Actualmente hay perfiles para Gemini y OpenAI; Gemini queda
primero en la lista y por eso es el valor seleccionado por defecto en la UI.

## Troubleshooting

- Docker no disponible o daemon caído: la validación de código no degrada a
  ejecución local; el análisis termina `INCONCLUSIVE`. Compruebe con
  `docker info` que el daemon responde y repita `docker compose up --build`.
- `401`, `403` o rate limit de GitHub: compruebe la URL, el acceso del token de
  solo lectura y espere el reset indicado por GitHub.
- Error de proveedor LLM: compruebe `GEMINI_API_KEY` u `OPENAI_API_KEY` solo en
  el entorno backend; los errores no incluyen la clave.
- DB heredada sin Alembic: borre el volumen con `docker compose down -v` o use
  una ruta nueva mediante `DATABASE_URL`; el servicio no sobrescribe bases
  ajenas.

## Demo

`scripts/create_demo_prs.md` describe cómo recrear en un fork descartable los
tres PRs de demostración (`BLOCKED`, `READY` e `INCONCLUSIVE`).

## Desarrollo (sin Docker)

Requisitos adicionales: Python 3.12 con `uv` y Node 22 con npm.

```bash
./scripts/setup.sh
uv run --project backend uvicorn pr_gate.main:app --reload
npm --prefix frontend run dev
```

La UI de desarrollo queda en `http://localhost:5173` y la API en
`http://localhost:8000`.

## Controles

```bash
./scripts/test.sh
```

Incluye formato, lint, tipos y tests backend; lint, tipos, tests y build
frontend. Los tests de integración Docker se omiten automáticamente si el
daemon no está operativo.
