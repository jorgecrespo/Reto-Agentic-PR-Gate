from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
    select,
)
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

_SECRET = re.compile(r"(?:api[_-]?key|token|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_-]{16,}", re.I)


def _redact(value: str) -> str:
    return _SECRET.sub("[REDACTED_SECRET]", value)


class Base(DeclarativeBase):
    pass


class PullRequestRecord(Base):
    __tablename__ = "pull_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner: Mapped[str] = mapped_column(String(100), nullable=False)
    repository: Mapped[str] = mapped_column(String(100), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    url: Mapped[str] = mapped_column(String(2048), unique=True, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(100), nullable=True)


class PullRequestSnapshotRecord(Base):
    __tablename__ = "pr_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    pull_request_id: Mapped[str] = mapped_column(ForeignKey("pull_requests.id"), index=True)
    base_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    head_sha: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    draft: Mapped[bool] = mapped_column(Boolean, nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class AnalysisRecord(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("pr_snapshots.id"), index=True, nullable=True
    )
    pull_request_url: Mapped[str] = mapped_column(String(2048), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    model_profile_id: Mapped[str] = mapped_column(String(100))
    validation_profile_id: Mapped[str] = mapped_column(String(100))
    policy_version: Mapped[str] = mapped_column(String(32), default="1.0.1")
    prompt_version: Mapped[str] = mapped_column(String(32), default="v1")
    head_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    report_json: Mapped[str] = mapped_column(Text, default="{}")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Float, nullable=True)

    @property
    def created_at(self) -> datetime:
        return self.started_at


class FindingRecord(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    analysis_run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    impact: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)


class CandidateFixRecord(Base):
    __tablename__ = "candidate_fixes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    finding_id: Mapped[str] = mapped_column(ForeignKey("findings.id"), index=True)
    patch: Mapped[str] = mapped_column(Text, nullable=False)
    regression_test_patch: Mapped[str] = mapped_column(Text, nullable=False)
    patch_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)


class ValidationRecord(Base):
    __tablename__ = "validation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    analysis_run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), index=True)
    phase: Mapped[str] = mapped_column(String(64))
    command_name: Mapped[str] = mapped_column(String(100))
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stdout_excerpt: Mapped[str] = mapped_column(Text)
    stderr_excerpt: Mapped[str] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timed_out: Mapped[bool] = mapped_column(Boolean, default=False)
    infrastructure_error: Mapped[bool] = mapped_column(Boolean, default=False)
    result: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class AcceptanceEvaluationRecord(Base):
    __tablename__ = "acceptance_evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    analysis_run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), index=True)
    criterion_id: Mapped[str] = mapped_column(String(100), nullable=False)
    criterion_text: Mapped[str] = mapped_column(Text, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False)


class RunEventRecord(Base):
    __tablename__ = "run_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    analysis_run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    node: Mapped[str] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class GateDecisionRecord(Base):
    __tablename__ = "gate_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    analysis_run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), index=True)
    status: Mapped[str] = mapped_column(String(32))
    target_stage: Mapped[str] = mapped_column(String(32), default="QA")
    policy_version: Mapped[str] = mapped_column(String(32))
    summary: Mapped[str] = mapped_column(Text)
    reasons_json: Mapped[str] = mapped_column(Text)
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    required_actions_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class AnalysisStore:
    def __init__(self, database_url: str | None = None) -> None:
        self._url: str = database_url or os.environ.get(
            "DATABASE_URL", "sqlite:///./data/pr_gate_v2.db"
        )
        if self._url.startswith("sqlite:///./"):
            Path(self._url.removeprefix("sqlite:///./")).parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(
            self._url,
            connect_args={"check_same_thread": False} if self._url.startswith("sqlite") else {},
        )
        if self._url.startswith("sqlite"):
            event.listen(self._engine, "connect", self._enable_sqlite_foreign_keys)
        self._upgrade_schema()

    @staticmethod
    def _enable_sqlite_foreign_keys(dbapi_connection: sqlite3.Connection, _: object) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    def _upgrade_schema(self) -> None:
        config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
        config.set_main_option(
            "script_location", str(Path(__file__).resolve().parents[3] / "migrations")
        )
        config.set_main_option("sqlalchemy.url", self._url)
        try:
            command.upgrade(config, "head")
        except OperationalError as error:
            if "already exists" in str(error).lower():
                raise RuntimeError(
                    "La base de datos existente no está administrada por Alembic. "
                    "Migrela explícitamente o configure una base de datos nueva."
                ) from error
            raise

    def create(
        self, pull_request_url: str, model_profile_id: str, validation_profile_id: str
    ) -> AnalysisRecord:
        record = AnalysisRecord(
            id=str(uuid.uuid4()),
            pull_request_url=pull_request_url,
            status="PENDING",
            model_profile_id=model_profile_id,
            validation_profile_id=validation_profile_id,
        )
        with Session(self._engine) as session:
            session.add(record)
            session.commit()
            session.refresh(record)
            session.expunge(record)
        return record

    def find_active(
        self, pull_request_url: str, model_profile_id: str, validation_profile_id: str
    ) -> AnalysisRecord | None:
        with Session(self._engine) as session:
            record = session.scalar(
                select(AnalysisRecord)
                .where(
                    AnalysisRecord.pull_request_url == pull_request_url,
                    AnalysisRecord.model_profile_id == model_profile_id,
                    AnalysisRecord.validation_profile_id == validation_profile_id,
                    AnalysisRecord.status.in_(("PENDING", "RUNNING")),
                )
                .order_by(AnalysisRecord.started_at.desc())
            )
            if record is not None:
                session.expunge(record)
            return record

    def mark_running(self, analysis_id: str) -> None:
        with Session(self._engine) as session:
            record = session.get(AnalysisRecord, analysis_id)
            if record is not None and record.status == "PENDING":
                record.status = "RUNNING"
                session.commit()

    def mark_orphaned(self) -> int:
        """Close runs left active by a process restart; in-process tasks cannot be resumed."""
        with Session(self._engine) as session:
            records = list(
                session.scalars(
                    select(AnalysisRecord).where(AnalysisRecord.status.in_(("PENDING", "RUNNING")))
                )
            )
            for record in records:
                record.status = "INCONCLUSIVE"
                record.error_message = "La aplicación se reinició antes de terminar el análisis."
                record.finished_at = datetime.now(UTC)
            session.commit()
            return len(records)

    def get(self, analysis_id: str) -> AnalysisRecord | None:
        with Session(self._engine) as session:
            record = session.get(AnalysisRecord, analysis_id)
            if record is not None:
                session.expunge(record)
            return record

    def save_snapshot(
        self,
        analysis_id: str,
        owner: str,
        repository: str,
        number: int,
        url: str,
        base_sha: str,
        head_sha: str,
        draft: bool,
        metadata: Mapping[str, object],
        title: str | None = None,
        author: str | None = None,
    ) -> str:
        with Session(self._engine) as session:
            pull_request = session.scalar(
                select(PullRequestRecord).where(PullRequestRecord.url == url)
            )
            if pull_request is None:
                pull_request = PullRequestRecord(
                    id=str(uuid.uuid4()),
                    owner=owner,
                    repository=repository,
                    number=number,
                    url=url,
                    title=title,
                    author=author,
                )
                session.add(pull_request)
            snapshot_id = str(uuid.uuid4())
            session.add(
                PullRequestSnapshotRecord(
                    id=snapshot_id,
                    pull_request_id=pull_request.id,
                    base_sha=base_sha,
                    head_sha=head_sha,
                    draft=draft,
                    metadata_json=_redact(json.dumps(metadata)),
                )
            )
            analysis = session.get(AnalysisRecord, analysis_id)
            if analysis is None:
                raise ValueError("El análisis no existe.")
            analysis.snapshot_id = snapshot_id
            analysis.head_sha = head_sha
            session.commit()
        return snapshot_id

    def save_finding(self, analysis_id: str, finding: Mapping[str, object]) -> str:
        finding_id = str(uuid.uuid4())
        record = FindingRecord(
            id=finding_id,
            analysis_run_id=analysis_id,
            category=str(finding["category"]),
            severity=str(finding["severity"]),
            title=_redact(str(finding["title"])),
            file_path=_redact(str(finding["file_path"])),
            start_line=int(str(finding["start_line"])),
            end_line=int(str(finding["end_line"])),
            evidence_excerpt=_redact(str(finding["evidence_excerpt"])),
            explanation=_redact(str(finding["explanation"])),
            impact=_redact(str(finding["impact"])),
            recommendation=_redact(str(finding["recommended_action"])),
            confidence=float(str(finding["confidence"])),
        )
        with Session(self._engine) as session:
            session.add(record)
            session.commit()
        return finding_id

    def save_candidate_fix(
        self,
        finding_id: str,
        patch: str,
        regression_test_patch: str,
        patch_hash: str,
        status: str,
    ) -> str:
        fix_id = str(uuid.uuid4())
        with Session(self._engine) as session:
            session.add(
                CandidateFixRecord(
                    id=fix_id,
                    finding_id=finding_id,
                    patch=patch,
                    regression_test_patch=regression_test_patch,
                    patch_hash=patch_hash,
                    status=status,
                )
            )
            session.commit()
        return fix_id

    def save_acceptance_evaluation(
        self,
        analysis_id: str,
        criterion_id: str,
        criterion_text: str,
        required: bool,
        status: str,
        evidence: Sequence[Mapping[str, object]],
    ) -> None:
        with Session(self._engine) as session:
            session.add(
                AcceptanceEvaluationRecord(
                    id=str(uuid.uuid4()),
                    analysis_run_id=analysis_id,
                    criterion_id=criterion_id,
                    criterion_text=criterion_text,
                    required=required,
                    status=status,
                    evidence_json=json.dumps(list(evidence)),
                )
            )
            session.commit()

    def list(
        self, limit: int = 50, offset: int = 0, status: str | None = None
    ) -> list[AnalysisRecord]:
        with Session(self._engine) as session:
            statement = select(AnalysisRecord).order_by(AnalysisRecord.started_at.desc())
            if status is not None:
                statement = statement.where(AnalysisRecord.status == status)
            records = list(session.scalars(statement.limit(limit).offset(offset)))
            for record in records:
                session.expunge(record)
            return records

    def finish(
        self,
        analysis_id: str,
        status: str,
        report: Mapping[str, object],
        error: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        estimated_cost: float | None = None,
    ) -> None:
        with Session(self._engine) as session:
            record = session.get(AnalysisRecord, analysis_id)
            if record is None:
                return
            record.status = status
            head_sha = report.get("head_sha")
            record.head_sha = head_sha if isinstance(head_sha, str) else None
            record.report_json = _redact(json.dumps(report))
            record.error_message = error
            record.input_tokens = input_tokens
            record.output_tokens = output_tokens
            record.estimated_cost = estimated_cost
            record.finished_at = datetime.now(UTC)
            started_at = record.started_at
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=UTC)
            record.duration_ms = int((record.finished_at - started_at).total_seconds() * 1000)
            session.commit()

    def save_validation(self, analysis_id: str, phase: str, result: object) -> None:
        record = ValidationRecord(
            id=str(uuid.uuid4()),
            analysis_run_id=analysis_id,
            phase=phase,
            command_name=str(getattr(result, "command_name", phase)),
            exit_code=getattr(result, "exit_code", None),
            stdout_excerpt=_redact(str(getattr(result, "stdout", "")))[:8000],
            stderr_excerpt=_redact(str(getattr(result, "stderr", "")))[:8000],
            timed_out=bool(getattr(result, "timed_out", False)),
            infrastructure_error=bool(getattr(result, "infrastructure_error", False)),
        )
        with Session(self._engine) as session:
            session.add(record)
            session.commit()

    def add_event(self, analysis_id: str, sequence: int, node: str, message: str) -> None:
        with Session(self._engine) as session:
            session.add(
                RunEventRecord(
                    id=str(uuid.uuid4()),
                    analysis_run_id=analysis_id,
                    sequence=sequence,
                    node=node,
                    message=message,
                )
            )
            session.commit()

    def save_gate_decision(
        self,
        analysis_id: str,
        status: str,
        policy_version: str,
        summary: str,
        reasons: Sequence[Mapping[str, str]],
    ) -> None:
        with Session(self._engine) as session:
            session.add(
                GateDecisionRecord(
                    id=str(uuid.uuid4()),
                    analysis_run_id=analysis_id,
                    status=status,
                    policy_version=policy_version,
                    summary=summary,
                    reasons_json=json.dumps(list(reasons)),
                )
            )
            session.commit()

    def events(self, analysis_id: str) -> Sequence[RunEventRecord]:
        with Session(self._engine) as session:
            rows = list(
                session.scalars(
                    select(RunEventRecord)
                    .where(RunEventRecord.analysis_run_id == analysis_id)
                    .order_by(RunEventRecord.sequence)
                )
            )
            for row in rows:
                session.expunge(row)
            return rows

    def report(self, analysis_id: str) -> dict[str, object] | None:
        with Session(self._engine) as session:
            analysis = session.get(AnalysisRecord, analysis_id)
            if analysis is None:
                return None
            return {
                "analysis": json.loads(analysis.report_json),
                "findings": [
                    {
                        "id": finding.id,
                        "severity": finding.severity,
                        "title": finding.title,
                        "file_path": finding.file_path,
                    }
                    for finding in session.scalars(
                        select(FindingRecord).where(FindingRecord.analysis_run_id == analysis_id)
                    )
                ],
                "acceptance_criteria": [
                    {
                        "id": evaluation.criterion_id,
                        "status": evaluation.status,
                        "evidence": json.loads(evaluation.evidence_json),
                    }
                    for evaluation in session.scalars(
                        select(AcceptanceEvaluationRecord).where(
                            AcceptanceEvaluationRecord.analysis_run_id == analysis_id
                        )
                    )
                ],
            }
