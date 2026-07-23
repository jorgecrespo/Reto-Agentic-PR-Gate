from __future__ import annotations

import os
from pathlib import Path

_database_path = Path(__file__).resolve().parent / ".test-pr-gate.db"
_database_path.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{_database_path}"
