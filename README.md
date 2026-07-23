# Agentic PR Gate

Prototype for a traceable Pull Request to QA quality gate. The LLM proposes findings and patches; deterministic tools and a policy engine decide the status.

## Status

The current vertical flow validates PR URLs, reads GitHub, builds a bounded context, asks the configured OpenAI profile for structured output, validates candidate patches in separate workspaces, and runs administratively configured commands in Docker.

## Run locally

Requirements: Python 3.12, Node 22, Docker, and an OpenAI API key for real analysis.

```bash
cp .env.example .env
# Set OPENAI_API_KEY in .env; GITHUB_TOKEN is optional for public PRs.
cd backend && uv sync --all-groups && uv run uvicorn pr_gate.main:app --reload
cd frontend && npm install && npm run dev
```

Build the runner image once before a real validation:

```bash
docker build --file backend/runner.Dockerfile --tag pr-gate-runner:latest .
```

The frontend runs at `http://localhost:5173` and the backend at `http://localhost:8000`.

## Validate

```bash
cd backend
uv run ruff format --check .
uv run ruff check .
uv run pytest
uv run mypy src
cd ../frontend
npm run lint && npm run typecheck && npm run build
```

## Safety boundaries

- GitHub access is read-only.
- API keys are server-side environment variables only.
- PR code is intended to run only in an ephemeral Docker sandbox with networking disabled.
- A missing sandbox results in `INCONCLUSIVE`, never an unsafe local execution.

## Further documentation

- `docs/architecture.md`: layers and workflow boundaries.
- `docs/security.md`: threat mitigations and runner restrictions.
- `docs/providers.md`: model adapter contract.
- `docs/limitations.md`: current prototype limitations.
- `exclude/info.md`: file tree and function/class reference.
