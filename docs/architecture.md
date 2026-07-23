# Architecture

`domain` contains immutable values and the pure quality gate. `application` contains validated use-case contracts and the evidence workflow. `infrastructure` owns HTTPX GitHub, OpenAI, SQLite, Docker, patch, workspace and configuration adapters. FastAPI exposes HTTP and React presents escaped structured evidence.

The workflow builds a bounded and redacted context, obtains structured LLM output, validates patch paths, creates two SHA-pinned workspaces, runs baseline/candidate validation in Docker, verifies the PR SHA again, and feeds only structured facts to the policy gate. The LangGraph graph currently covers request validation, GitHub retrieval and gate routing; it must remain the sole orchestration path as the remaining nodes are moved into it.

SQLite is accessed through SQLAlchemy. `backend/migrations/` contains the Alembic migration history; generated reports and bounded validation excerpts are retained while workspaces are deleted.
