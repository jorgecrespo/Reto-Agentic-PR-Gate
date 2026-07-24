from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.middleware.base import RequestResponseEndpoint

from pr_gate.application.execution import AnalysisExecutionService
from pr_gate.application.models import CreateAnalysisInput
from pr_gate.domain.types import PullRequestRef
from pr_gate.graph.builder import build_graph
from pr_gate.graph.runtime import build_runtime_dependencies
from pr_gate.infrastructure.config import ModelProfile, load_model_profiles, load_policy
from pr_gate.infrastructure.database import AnalysisStore
from pr_gate.infrastructure.github import GitHubError
from pr_gate.infrastructure.llm import LLMError
from pr_gate.observability import configure_logging


def _project_root() -> Path:
    for directory in Path(__file__).resolve().parents:
        if (directory / "config").is_dir():
            return directory
    raise RuntimeError("No se encontró el directorio de configuración del proyecto.")


ROOT = _project_root()
STORE = AnalysisStore()
EXECUTIONS = AnalysisExecutionService()
configure_logging()
LOGGER = logging.getLogger("pr_gate")


def _load_yaml(relative_path: str) -> dict[str, Any]:
    with (ROOT / relative_path).open() as stream:
        loaded = yaml.safe_load(stream)
    if not isinstance(loaded, dict):
        raise RuntimeError(f"Configuración inválida: {relative_path}")
    return loaded


def _problem(status_code: int, title: str, detail: str, request: Request) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "type": f"https://pr-gate.local/problems/{title.lower().replace(' ', '-')}",
            "title": title,
            "status": status_code,
            "detail": detail,
            "instance": request.url.path,
        },
        media_type="application/problem+json",
    )


def _configured_profile(config_path: str, key: str, profile_id: str) -> dict[str, Any] | None:
    profiles = _load_yaml(config_path).get(key, [])
    if not isinstance(profiles, list):
        return None
    profile = next(
        (item for item in profiles if isinstance(item, dict) and item.get("id") == profile_id), None
    )
    return profile if isinstance(profile, dict) else None


def _model_profile(profile_id: str) -> ModelProfile | None:
    profiles = load_model_profiles(ROOT / "config/models.example.yaml").models
    return next(
        (profile for profile in profiles if profile.id == profile_id and profile.enabled), None
    )


async def _run_analysis(analysis_id: str, request: CreateAnalysisInput) -> None:
    STORE.mark_running(analysis_id)
    STORE.add_event(analysis_id, 0, "queued", "Análisis aceptado y en espera de ejecución.")
    try:
        profile = _configured_profile(
            "config/validation-profiles.yaml", "validation_profiles", request.validation_profile_id
        )
        if profile is None:
            raise ValueError("El perfil de validación seleccionado no existe.")
        model_profile = _model_profile(request.model_profile_id)
        if model_profile is None:
            raise ValueError("El perfil de modelo seleccionado no está disponible.")
        dependencies = build_runtime_dependencies(STORE, profile, model_profile)
        graph = build_graph(dependencies)
        try:
            await graph.ainvoke(
                {
                    "analysis_id": analysis_id,
                    "request": {
                        "pull_request_url": request.pull_request_url,
                        "model_profile_id": request.model_profile_id,
                        "validation_profile_id": request.validation_profile_id,
                        "acceptance_criteria": [
                            item.model_dump() for item in request.acceptance_criteria
                        ],
                    },
                }
            )
        finally:
            await dependencies.workspaces.cleanup(None, None)
    except (ValueError, GitHubError) as error:
        STORE.finish(
            analysis_id,
            "INCONCLUSIVE",
            _inconclusive_report(analysis_id, request, str(error)),
            str(error),
        )
        STORE.add_event(
            analysis_id, 9999, "finalize", "Análisis finalizado sin evidencia suficiente."
        )
    except LLMError as error:
        STORE.finish(
            analysis_id,
            "INCONCLUSIVE",
            _inconclusive_report(analysis_id, request, str(error)),
            str(error),
        )
        STORE.add_event(
            analysis_id, 9999, "finalize", f"Análisis finalizado por error del LLM: {error.code}."
        )
    except Exception as error:
        STORE.finish(
            analysis_id,
            "INCONCLUSIVE",
            _inconclusive_report(analysis_id, request, f"Error interno de análisis: {error}"),
            f"Error interno de análisis: {error}",
        )
        STORE.add_event(analysis_id, 9999, "finalize", "Análisis finalizado por un error interno.")


def _inconclusive_report(
    analysis_id: str, request: CreateAnalysisInput, message: str
) -> dict[str, object]:
    return {
        "analysis_id": analysis_id,
        "decision": {
            "status": "INCONCLUSIVE",
            "summary": "El análisis no produjo evidencia suficiente.",
            "policy_version": "unknown",
            "rules": [],
            "blocking_reasons": [],
            "warnings": [],
            "not_evaluated_rules": [],
            "required_actions": ["Corregir la causa del fallo y ejecutar un nuevo análisis."],
        },
        "pull_request": {"url": request.pull_request_url, "modified_files": []},
        "acceptance_criteria": [
            {
                **item.model_dump(),
                "status": "NOT_EVALUATED",
                "evidence": [],
                "source": "NOT_EXECUTED",
                "reason": message,
            }
            for item in request.acceptance_criteria
        ],
        "execution": {
            "llm": {"status": "NOT_EXECUTED", "reason": message},
            "candidate_validation": {"status": "NOT_EXECUTED", "reason": message},
            "not_executed_controls": [],
        },
        "errors": [{"code": "ANALYSIS_INCONCLUSIVE", "message": message}],
        "finalized": True,
    }


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    STORE.mark_orphaned()
    yield
    await EXECUTIONS.stop()


app = FastAPI(title="Agentic PR Gate", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_request(request: Request, call_next: RequestResponseEndpoint) -> Response:
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    started = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = round((time.perf_counter() - started) * 1000)
    response.headers["X-Correlation-ID"] = correlation_id
    LOGGER.info(
        "http.request.completed",
        extra={
            "correlation_id": correlation_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


@app.exception_handler(HTTPException)
async def http_error(request: Request, error: HTTPException) -> JSONResponse:
    return _problem(error.status_code, "Request failed", str(error.detail), request)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
    detail = "; ".join(item["msg"] for item in error.errors())
    return _problem(422, "Invalid request", detail, request)


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def ready() -> dict[str, str]:
    load_policy(ROOT / "config/policies/qa-gate-v1.yaml")
    return {"status": "ok"}


@app.get("/api/v1/config/models")
def models() -> dict[str, object]:
    profiles = load_model_profiles(ROOT / "config/models.example.yaml").models
    return {
        "models": [
            profile.model_dump(exclude={"api_key_env"}) for profile in profiles if profile.enabled
        ]
    }


@app.get("/api/v1/config/validation-profiles")
def validation_profiles() -> dict[str, object]:
    profiles = _load_yaml("config/validation-profiles.yaml").get("validation_profiles", [])
    if not isinstance(profiles, list):
        raise RuntimeError("La configuración de perfiles es inválida.")
    # Commands and permitted paths are server-side enforcement details.
    return {
        "validation_profiles": [
            {"id": item.get("id")} for item in profiles if isinstance(item, dict)
        ]
    }


@app.get("/api/v1/config/policy")
def policy() -> dict[str, object]:
    loaded = load_policy(ROOT / "config/policies/qa-gate-v1.yaml")
    return {**loaded.policy.model_dump(), "checksum": loaded.checksum}


@app.post("/api/v1/analyses", status_code=status.HTTP_202_ACCEPTED)
async def create_analysis(request: CreateAnalysisInput, response: Response) -> dict[str, object]:
    try:
        PullRequestRef.parse(request.pull_request_url)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    model = _model_profile(request.model_profile_id)
    validation = _configured_profile(
        "config/validation-profiles.yaml", "validation_profiles", request.validation_profile_id
    )
    if model is None:
        raise HTTPException(422, "El perfil de modelo seleccionado no está disponible.")
    if validation is None:
        raise HTTPException(422, "El perfil de validación seleccionado no está disponible.")
    existing = STORE.find_active(
        request.pull_request_url, request.model_profile_id, request.validation_profile_id
    )
    if existing is not None:
        response.headers["Location"] = f"/api/v1/analyses/{existing.id}"
        response.headers["X-Correlation-ID"] = existing.id
        return {"analysis_id": existing.id, "status": existing.status, "deduplicated": True}
    record = STORE.create(
        request.pull_request_url, request.model_profile_id, request.validation_profile_id
    )
    EXECUTIONS.start(record.id, lambda analysis_id: _run_analysis(analysis_id, request))
    response.headers["Location"] = f"/api/v1/analyses/{record.id}"
    response.headers["X-Correlation-ID"] = record.id
    return {"analysis_id": record.id, "status": record.status, "deduplicated": False}


@app.get("/api/v1/analyses")
def list_analyses(
    status_filter: str | None = None, limit: int = 50, offset: int = 0
) -> dict[str, object]:
    limit = max(1, min(limit, 100))
    records = STORE.list(limit=limit, offset=max(offset, 0), status=status_filter)
    return {
        "items": [
            {
                "id": item.id,
                "pull_request_url": item.pull_request_url,
                "status": item.status,
                "model_profile_id": item.model_profile_id,
                "head_sha": item.head_sha,
                "created_at": item.created_at.isoformat(),
                "duration_ms": item.duration_ms,
            }
            for item in records
        ]
    }


@app.get("/api/v1/analyses/{analysis_id}")
def get_analysis(analysis_id: str) -> dict[str, object]:
    record = STORE.get(analysis_id)
    if record is None:
        raise HTTPException(404, "Análisis no encontrado.")
    return {
        "id": record.id,
        "status": record.status,
        "report": json.loads(record.report_json),
        "error": record.error_message,
        "created_at": record.created_at.isoformat(),
        "finished_at": record.finished_at.isoformat() if record.finished_at else None,
        "duration_ms": record.duration_ms,
        "input_tokens": record.input_tokens,
        "output_tokens": record.output_tokens,
        "estimated_cost": record.estimated_cost,
        "model_profile_id": record.model_profile_id,
        "validation_profile_id": record.validation_profile_id,
    }


@app.get("/api/v1/analyses/{analysis_id}/events")
def analysis_events(analysis_id: str) -> dict[str, object]:
    if STORE.get(analysis_id) is None:
        raise HTTPException(404, "Análisis no encontrado.")
    return {
        "items": [
            {
                "sequence": event.sequence,
                "node": event.node,
                "message": event.message,
                "created_at": event.created_at.isoformat(),
            }
            for event in STORE.events(analysis_id)
        ]
    }


@app.get("/api/v1/analyses/{analysis_id}/stream")
async def stream_analysis(analysis_id: str) -> StreamingResponse:
    if STORE.get(analysis_id) is None:
        raise HTTPException(404, "Análisis no encontrado.")

    async def events() -> AsyncIterator[str]:
        last_sequence = 0
        while True:
            record = STORE.get(analysis_id)
            if record is None:
                return
            for event in STORE.events(analysis_id):
                if event.sequence > last_sequence:
                    last_sequence = event.sequence
                    payload = json.dumps(
                        {"sequence": event.sequence, "node": event.node, "message": event.message}
                    )
                    yield f"event: progress\ndata: {payload}\n\n"
            if record.finished_at is not None:
                yield "event: complete\ndata: {}\n\n"
                return
            yield ": keepalive\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )
