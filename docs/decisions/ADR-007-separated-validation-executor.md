# ADR-007: Executor de validación separado

## Context

El backend necesita validar código no confiable, pero montar el socket Docker en
ese servicio le otorgaría control del host de contenedores.

## Decision

El backend envía un archive efímero y una fase de validación a un servicio
interno `executor`. Solo el executor monta `/var/run/docker.sock`. El executor
elige argv desde `validation-profiles.yaml`, prepara un volumen Docker temporal
CPU, memoria y PIDs, y usuario no root.

## Consequences

El backend no puede lanzar contenedores ni acceder al socket Docker. El executor
es un componente privilegiado, no publica puertos al host y elimina contenedor y
volumen temporal al terminar. Si no puede comunicarse con Docker, la evidencia
de validación queda inconclusa; no existe fallback a subprocess local.

## Alternatives

Montar el socket Docker en el backend fue rechazado por ampliar innecesariamente
su superficie de privilegios. Ejecutar tests locales fue rechazado porque el
código del PR no es confiable.
