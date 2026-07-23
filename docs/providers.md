# Adding a model provider

Model profiles belong in `config/models.example.yaml`; credentials are referenced only by environment-variable name and are never returned by the API.

Implement a gateway adapter that returns the Pydantic `AnalysisOutput` and `FixOutput` contracts from `pr_gate.application.models`. The adapter must use timeouts, bounded retries, structured JSON validation, and must not expose provider errors or credentials to the frontend.

The included adapter is `OpenAILLMGateway` using `gpt-4.1-mini`. Add contract tests with a fake before enabling another provider.
