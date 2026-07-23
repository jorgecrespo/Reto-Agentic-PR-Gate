# Limitations

- A real end-to-end run requires `OPENAI_API_KEY` and a GitHub pull request URL accessible to the configured token.
- The prototype supports the `python-demo` validation profile only; the runner intentionally does not infer commands from repositories or model output.
- In-process background jobs do not survive a backend restart. Persisted completed reports remain available.
- The system recommends the PR-to-QA transition only. It never writes to GitHub, merges code, comments on PRs, or deploys software.
- Model output is non-deterministic. The policy decision is deterministic only for the collected facts.
