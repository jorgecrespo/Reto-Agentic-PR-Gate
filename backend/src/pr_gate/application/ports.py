from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class StoredAnalysis:
    id: str
    pull_request_url: str
    status: str
    report_json: str
    error_message: str | None
    created_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True)
class StoredEvent:
    node: str
    message: str


class AnalysisRepository(Protocol):
    """Persistence boundary for short-lived synchronous SQLAlchemy sessions."""

    def create(
        self, pull_request_url: str, model_profile_id: str, validation_profile_id: str
    ) -> StoredAnalysis: ...

    def get(self, analysis_id: str) -> StoredAnalysis | None: ...

    def list(self, limit: int = 50, offset: int = 0) -> list[StoredAnalysis]: ...

    def finish(
        self, analysis_id: str, status: str, report: Mapping[str, object], error: str | None = None
    ) -> None: ...

    def events(self, analysis_id: str) -> Sequence[StoredEvent]: ...

    def report(self, analysis_id: str) -> dict[str, object] | None: ...
