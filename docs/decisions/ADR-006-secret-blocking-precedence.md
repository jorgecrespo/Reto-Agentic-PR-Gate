# ADR-006: Secret Detection Blocks Immediately

## Contexto

El escaneo de secretos ocurre antes de LLM, parches y validaciones de código. Si
detecta un secreto, esas etapas se omiten para no exponer el material sensible.

## Decisión

Un fallo de `GATE-006` produce `BLOCKED` incluso cuando los controles posteriores
no se ejecutaron y por ello permanecen en `UNKNOWN`.

## Consecuencia

El informe conserva los controles no ejecutados como evidencia adicional, pero la
decisión no se degrada a `INCONCLUSIVE`. La acción requerida es retirar y, cuando
corresponda, rotar el secreto antes de volver a analizar el PR.
