# Security model

The service reads GitHub only. API keys remain in backend environment variables and are not persisted or returned by configuration routes. Before a model is invoked, the workflow excludes sensitive paths and redacts matching secret patterns. A secret detected in the supplied diff blocks further LLM processing.

Untrusted code may only run in `DockerRunner`: network disabled, read-only mount, non-root user, CPU/memory/PID limits, external timeout, ephemeral `/tmp`, no Docker socket, and an administratively selected argv. Docker absence is an infrastructure failure, which maps to `INCONCLUSIVE`.
