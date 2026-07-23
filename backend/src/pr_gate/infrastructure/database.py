from __future__ import annotations

import json
import os
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class AnalysisRecord(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    pull_request_url: Mapped[str] = mapped_column(String(2048), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    model_profile_id: Mapped[str] = mapped_column(String(100))
    validation_profile_id: Mapped[str] = mapped_column(String(100))
    head_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    report_json: Mapped[str] = mapped_column(Text, default="{}")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)


class ValidationRecord(Base):
    __tablename__ = "validation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    analysis_run_id: Mapped[str] = mapped_column(String(36), index=True)
    phase: Mapped[str] = mapped_column(String(64))
    command_name: Mapped[str] = mapped_column(String(100))
    exit_code: Mapped[int | None] = mapped_column(nullable=True)
    stdout_excerpt: Mapped[str] = mapped_column(Text)
    stderr_excerpt: Mapped[str] = mapped_column(Text)
    timed_out: Mapped[bool] = mapped_column(default=False)
    infrastructure_error: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))


class RunEventRecord(Base):
    __tablename__ = "run_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    analysis_run_id: Mapped[str] = mapped_column(String(36), index=True)
    sequence: Mapped[int] = mapped_column()
    node: Mapped[str] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))


class GateDecisionRecord(Base):
    __tablename__ = "gate_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    analysis_run_id: Mapped[str] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(32))
    policy_version: Mapped[str] = mapped_column(String(32))
    summary: Mapped[str] = mapped_column(Text)
    reasons_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))


class AnalysisStore:
    def __init__(self, database_url: str | None = None) -> None:
        url = database_url or os.environ.get("DATABASE_URL", "sqlite:///./data/pr_gate.db")
        if url.startswith("sqlite:///./"):
            Path(url.removeprefix("sqlite:///./")).parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(
            url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {}
        )
        Base.metadata.create_all(self._engine)

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

    def get(self, analysis_id: str) -> AnalysisRecord | None:
        with Session(self._engine) as session:
            record = session.get(AnalysisRecord, analysis_id)
            if record is not None:
                session.expunge(record)
            return record

    def list(self) -> list[AnalysisRecord]:
        with Session(self._engine) as session:
            records = list(
                session.scalars(select(AnalysisRecord).order_by(AnalysisRecord.created_at.desc()))
            )
            for record in records:
                session.expunge(record)
            return records

    def finish(
        self, analysis_id: str, status: str, report: Mapping[str, object], error: str | None = None
    ) -> None:
        with Session(self._engine) as session:
            record = session.get(AnalysisRecord, analysis_id)
            if record is None:
                return
            record.status = status
            head_sha = report.get("head_sha")
            record.head_sha = head_sha if isinstance(head_sha, str) else None
            record.report_json = json.dumps(report)
            record.error_message = error
            record.finished_at = datetime.now(UTC)
            session.commit()

    def save_validation(self, analysis_id: str, phase: str, result: object) -> None:
        """Persist only bounded excerpts from a deterministic runner result."""
        command_name = str(getattr(result, "command_name", phase))
        record = ValidationRecord(
            id=str(uuid.uuid4()),
            analysis_run_id=analysis_id,
            phase=phase,
            command_name=command_name,
            exit_code=getattr(result, "exit_code", None),
            stdout_excerpt=str(getattr(result, "stdout", ""))[:8000],
            stderr_excerpt=str(getattr(result, "stderr", ""))[:8000],
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
