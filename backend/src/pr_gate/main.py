from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from pr_gate.application.models import CreateAnalysisInput
from pr_gate.application.workflow import gather_evidence
from pr_gate.domain.gate import evaluate_quality_gate
from pr_gate.domain.types import GateFacts, PullRequestRef
from pr_gate.infrastructure.config import load_policy
from pr_gate.infrastructure.database import AnalysisStore
from pr_gate.infrastructure.github import GitHubClient, GitHubError

ROOT = Path(__file__).resolve().parents[3]
STORE = AnalysisStore()


class AnalysisCreated(BaseModel):
    analysis_id: str
    status: str


def _load_yaml(relative_path: str) -> dict[str, Any]:
    with (ROOT / relative_path).open() as stream:
        loaded = yaml.safe_load(stream)
    if not isinstance(loaded, dict):
        raise RuntimeError(f"Configuración inválida: {relative_path}")
    return loaded


async def _run_analysis(analysis_id: str, request: CreateAnalysisInput) -> None:
    try:
        STORE.add_event(analysis_id, 1, "validate_request", "Solicitud validada.")
        ref = PullRequestRef.parse(request.pull_request_url)
        STORE.add_event(analysis_id, 2, "fetch_pull_request", "Recuperando snapshot del PR.")
        snapshot = await GitHubClient().fetch_snapshot(ref)
        profiles = _load_yaml("config/validation-profiles.yaml").get("validation_profiles", [])
        profile = next(
            (
                item
                for item in profiles
                if isinstance(item, dict) and item.get("id") == request.validation_profile_id
            ),
            None,
        )
        if profile is None:
            raise ValueError("El perfil de validación seleccionado no existe.")
        evidence = await gather_evidence(snapshot, profile)
        STORE.add_event(analysis_id, 3, "workflow", "Evidencia de análisis recopilada.")
        for phase, result in {
            "baseline": evidence.validation.baseline,
            "candidate": evidence.validation.candidate,
            "suite": evidence.validation.suite,
            "lint": evidence.validation.lint,
        }.items():
            if result is not None:
                STORE.save_validation(analysis_id, phase, result)
        critical_findings = (
            sum(finding.severity == "critical" for finding in evidence.analysis.findings)
            if evidence.analysis
            else 0
        )
        criteria_evaluated = True if not request.acceptance_criteria else None
        try:
            head_sha_current = await GitHubClient().fetch_current_head_sha(ref) == snapshot.head_sha
        except GitHubError:
            head_sha_current = None
        decision = evaluate_quality_gate(
            GateFacts(
                head_sha_current=head_sha_current,
                context_complete=True,
                tests_executed=True if evidence.validation.suite is not None else None,
                tests_passed=evidence.validation.suite_passed,
                critical_findings=critical_findings,
                secrets_detected=evidence.secrets_detected,
                required_criteria_evaluated=criteria_evaluated,
                required_criteria_passed=criteria_evaluated,
                patch_applied=evidence.validation.patch_applied,
                regression_reproduced=evidence.validation.regression_reproduced,
                regression_fixed=evidence.validation.regression_fixed,
                suite_passed=evidence.validation.suite_passed,
                business_logic_changed=bool(evidence.analysis and evidence.analysis.findings),
                tests_changed=bool(
                    evidence.fix and any("test" in path for path in evidence.fix.modified_paths)
                ),
                pr_is_draft=snapshot.draft,
                no_newer_pr=head_sha_current,
            )
        )
        report: dict[str, object] = {
            "analysis_id": analysis_id,
            "head_sha": snapshot.head_sha,
            "title": snapshot.title,
            "decision": decision.status,
            "summary": decision.summary,
            "rules": [
                {"id": rule.rule_id, "outcome": rule.outcome, "message": rule.message}
                for rule in decision.rules
            ],
            "findings": evidence.analysis.model_dump() if evidence.analysis else None,
            "fix": evidence.fix.model_dump() if evidence.fix else None,
            "validations": {
                name: result.__dict__ if result else None
                for name, result in {
                    "baseline": evidence.validation.baseline,
                    "candidate": evidence.validation.candidate,
                    "suite": evidence.validation.suite,
                    "lint": evidence.validation.lint,
                }.items()
            },
            "acceptance_criteria": [
                {
                    "id": criterion.id,
                    "text": criterion.text,
                    "required": criterion.required,
                    "status": "NOT_EVALUATED",
                    "evidence": [],
                }
                for criterion in request.acceptance_criteria
            ],
            "limitations": list(evidence.limitations),
        }
        STORE.save_gate_decision(
            analysis_id,
            str(decision.status),
            decision.policy_version,
            decision.summary,
            [
                {"rule_id": rule.rule_id, "message": rule.message}
                for rule in decision.blocking_reasons
            ],
        )
        STORE.finish(analysis_id, decision.status, report)
        STORE.add_event(analysis_id, 4, "finalize", f"Análisis finalizado: {decision.status}.")
    except (ValueError, GitHubError) as error:
        STORE.finish(analysis_id, "INCONCLUSIVE", {}, str(error))
    except Exception as error:
        # Internal detail is not returned to clients; it remains an actionable failed run record.
        STORE.finish(
            analysis_id, "INCONCLUSIVE", {}, f"Error interno de análisis: {type(error).__name__}"
        )


@asynccontextmanager
async def lifespan(_: FastAPI) -> Any:
    yield


app = FastAPI(title="Agentic PR Gate", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def ready() -> dict[str, str]:
    load_policy(ROOT / "config/policies/qa-gate-v1.yaml")
    return {"status": "ok"}


@app.get("/api/v1/config/models")
def models() -> dict[str, object]:
    config = _load_yaml("config/models.example.yaml")
    profiles: object = config.get("models", [])
    if not isinstance(profiles, list):
        raise RuntimeError("La configuración de modelos es inválida.")
    safe_profiles = [
        {key: value for key, value in profile.items() if key != "api_key_env"}
        for profile in profiles
        if isinstance(profile, dict)
    ]
    return {"models": safe_profiles}


@app.get("/api/v1/config/validation-profiles")
def validation_profiles() -> dict[str, object]:
    return _load_yaml("config/validation-profiles.yaml")


@app.get("/api/v1/config/policy")
def policy() -> dict[str, object]:
    loaded = load_policy(ROOT / "config/policies/qa-gate-v1.yaml")
    return {**loaded.policy.model_dump(), "checksum": loaded.checksum}


@app.post("/api/v1/analyses", status_code=status.HTTP_202_ACCEPTED, response_model=AnalysisCreated)
async def create_analysis(request: CreateAnalysisInput, response: Response) -> AnalysisCreated:
    try:
        PullRequestRef.parse(request.pull_request_url)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    record = STORE.create(
        request.pull_request_url, request.model_profile_id, request.validation_profile_id
    )
    asyncio.create_task(_run_analysis(record.id, request))
    response.headers["Location"] = f"/api/v1/analyses/{record.id}"
    return AnalysisCreated(analysis_id=record.id, status=record.status)


@app.get("/api/v1/analyses")
def list_analyses() -> list[dict[str, object]]:
    return [
        {
            "id": record.id,
            "url": record.pull_request_url,
            "status": record.status,
            "created_at": record.created_at,
        }
        for record in STORE.list()
    ]


@app.get("/api/v1/analyses/{analysis_id}")
def get_analysis(analysis_id: str) -> dict[str, object]:
    record = STORE.get(analysis_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Análisis no encontrado.")
    return {
        "id": record.id,
        "status": record.status,
        "report": json.loads(record.report_json),
        "error": record.error_message,
        "created_at": record.created_at,
        "finished_at": record.finished_at,
    }


@app.get("/api/v1/analyses/{analysis_id}/stream")
async def stream_analysis(analysis_id: str) -> StreamingResponse:
    if STORE.get(analysis_id) is None:
        raise HTTPException(status_code=404, detail="Análisis no encontrado.")

    async def events() -> AsyncIterator[str]:
        sent_events = 0
        while True:
            record = STORE.get(analysis_id)
            if record is None:
                yield 'event: error\ndata: {"message":"Análisis no encontrado."}\n\n'
                return
            events = STORE.events(analysis_id)
            for event in events[sent_events:]:
                payload = json.dumps({"node": event.node, "message": event.message})
                yield f"event: progress\ndata: {payload}\n\n"
            sent_events = len(events)
            if record.finished_at is not None:
                yield "event: complete\ndata: {}\n\n"
                return
            await asyncio.sleep(1)

    return StreamingResponse(events(), media_type="text/event-stream")
