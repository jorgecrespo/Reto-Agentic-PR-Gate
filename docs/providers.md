# Proveedores LLM

Los perfiles están en `config/models.example.yaml`. Solo se versiona el nombre de
la variable de entorno, nunca una credencial. La API devuelve metadatos seguros
del perfil y omite `api_key_env`.

Un adaptador debe implementar el contrato propio y devolver `AnalysisOutput` y
`FixOutput` Pydantic de `pr_gate.application.models`. Debe usar timeout, reintentos
acotados, JSON estructurado validado y errores resumidos sin claves, prompts ni
contenido sensible. Añada contract tests con fake antes de habilitarlo.

El perfil actual usa `OpenAILLMGateway` y `gpt-4.1-mini`. No se declara soporte
real de un segundo proveedor: hacerlo requiere adaptador, perfil documentado,
test seguro sin credenciales y una ejecución manual con credenciales autorizadas.
