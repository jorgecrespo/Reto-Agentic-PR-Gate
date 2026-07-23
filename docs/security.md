# Modelo de seguridad

GitHub es solo lectura. Tokens y API keys permanecen en variables de entorno del
backend, no se guardan en SQLite ni se exponen por rutas de configuración. Antes
del LLM, el contexto excluye paths sensibles, redacta patrones conocidos y bloquea
un secreto en el diff. El contenido del repositorio se trata como datos; sus
instrucciones no habilitan herramientas ni comandos.

Código no confiable solo puede ejecutarse con `DockerRunner`: red deshabilitada,
usuario no root, mounts mínimos, CPU/memoria/PID limitados, timeout externo,
`/tmp` efímero, sin socket Docker ni secretos, y argv administrado. El modelo no
proporciona el comando. Si Docker falta o falla, el resultado es
`INCONCLUSIVE`, nunca una ejecución local silenciosa.

Los Dockerfiles ejecutan procesos de aplicación no root. Compose aplica
`no-new-privileges`, elimina capabilities, usa filesystem de solo lectura donde
es viable y define healthchecks. Estas propiedades deben verificarse con Docker
en el ambiente de entrega; no son evidencia de aislamiento mientras el daemon no
se haya ejecutado.

Retención: se guardan IDs, SHA, decisiones, extractos limitados, parches y
resultados de validación. No se guardan repositorios clonados, `.env`, variables
de entorno, claves, tokens ni razonamiento interno. La redacción es defensa en
profundidad, no garantía de detección total; secretos no deben entrar al sistema.
