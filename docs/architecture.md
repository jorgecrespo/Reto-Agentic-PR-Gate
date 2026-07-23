# Arquitectura

`domain` contiene tipos inmutables y el quality gate puro. `application` define
casos de uso, contratos Pydantic y coordinación. `infrastructure` implementa
GitHub por HTTPX, SQLite/Alembic, LLM, parches, workspaces, Docker y configuración.
FastAPI expone HTTP/SSE; React solo presenta evidencia estructurada escapada.

El workflow fija el SHA, construye y redacta contexto, valida la salida LLM,
comprueba paths del parche, crea workspaces baseline/candidate y recoge resultados
de comandos administrados. Solo `GateFacts` estructurados llegan a la política.
El grafo es dirigido y no permite al modelo navegar herramientas ni decidir el
estado del gate. Las tareas de validación real end-to-end siguen siendo un bloqueo
operativo hasta ejecutarse con Docker.

SQLite usa SQLAlchemy y migraciones Alembic. Se retienen metadatos, decisiones,
parches y extractos limitados necesarios para el informe. Los workspaces efímeros
se eliminan al finalizar. Los jobs en proceso no sobreviven un reinicio: el inicio
marca los huérfanos como `INCONCLUSIVE` y conserva reportes terminados.

Los logs de solicitudes son JSON con `X-Correlation-ID`, método, path, estado y
duración. No contienen cuerpos, prompts completos ni secretos. La métrica por
nodo, tokens y costo depende de que el workflow real exponga esa evidencia; no se
debe inferir si falta.
