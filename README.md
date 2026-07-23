# Agentic PR Gate

Prototipo para decidir de forma trazable la transición **Pull Request -> QA**.
El LLM propone hallazgos y parches estructurados; las herramientas y la política
determinística aportan evidencia y emiten `READY`, `CONDITIONAL`, `BLOCKED` o
`INCONCLUSIVE`. No hace push, merge, reviews ni comentarios en GitHub.

## Estado verificable

El flujo implementado valida URLs, consulta GitHub en modo lectura, construye
contexto acotado, valida salidas LLM, aplica límites al parche y persiste
resultados. La demo de e-commerce incluida es **local y basada en fixtures**:
no afirma que exista ni consulta un PR real de GitHub. La validación completa de
un PR real y las métricas de diez ejecuciones requieren Docker, credenciales y
una ejecución posterior documentada.

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

Compose construye backend, frontend y la imagen de runner. Backend y runner
corren como usuarios no root; los servicios tienen filesystem de solo lectura
donde aplica, capacidades Linux eliminadas, `no-new-privileges` y healthchecks.
El volumen `pr-gate-data` conserva SQLite. `./scripts/cleanup.sh` destruye ese
volumen y por tanto los informes persistidos.

No se afirma aquí que una imagen se haya construido o que Docker esté disponible:
ejecute `docker compose config` y `./scripts/run.sh` en el entorno destino antes
de considerar esta vía operativa.

## Demo reproducible local

```bash
./scripts/demo.sh
```

El script verifica tres escenarios con fixtures locales:

| Escenario | Evidencia ejecutada | Resultado esperado |
| --- | --- | --- |
| Defectuoso | El test de regresión falla por cobrar el precio del request | `BLOCKED` antes de mitigar |
| Candidate | El test y la suite pasan con precio de catálogo | Corrección validada |
| Seguro | La suite del cambio pequeño pasa | `READY` cuando el gate recibe controles completos |
| Inconcluso | Runner obligatorio declarado no disponible | `INCONCLUSIVE` |

El estado del último caso es una representación de política, no una ejecución de
Docker. Consulte `examples/demo_ecommerce/README.md` y
`scripts/create_demo_prs.md` para recrear ramas/PRs manualmente en un fork.

## Controles

```bash
./scripts/test.sh
```

Incluye formato, lint, tipos y tests backend; lint, tipos, tests y build frontend.
Los tests de integración Docker se omiten automáticamente si el daemon no está
operativo. Ejecute además `./scripts/demo.sh` para la evidencia local de la demo.

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
- `docs/demo.md`: escenarios, evidencia y ramas opcionales.
- `docs/challenge-decision-document.md`: documento de entrega y uso transparente de IA.
