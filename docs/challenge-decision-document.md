# Documento de decisión del reto

## Problema y capacidad demostrada

Agentic PR Gate busca hacer trazable la decisión de avanzar un PR a QA. Separa la
hipótesis del modelo de la evidencia: el modelo puede señalar el uso inseguro de
un precio enviado por el cliente y proponer un parche; tests, runner y política
determinan el estado final. La demo local ilustra los tres resultados relevantes:
defecto bloqueante, cambio seguro y control obligatorio no ejecutado.

## Arquitectura

FastAPI recibe la solicitud y persiste ejecuciones SQLite. Un workflow dirigido
coordina GitHub de solo lectura, contexto limitado, gateway LLM, parches,
workspaces y runner. React muestra informes y eventos. `domain` conserva el gate
puro y testeable: no depende de FastAPI, SQLite, GitHub ni LLM.

## Decisiones y alternativas

- Workflow dirigido con LangGraph en vez de un agente libre: reduce superficie de
  ataque y permite rutas y eventos explícitos.
- Gate determinístico: evita que una explicación del LLM se convierta en una
  aprobación sin evidencia.
- SQLite y jobs en proceso: minimizan el alcance del prototipo; una cola y una DB
  multiusuario quedan fuera de alcance.
- Runner Docker con argv allowlisted y sin red: es preferible a ejecutar código
  del PR localmente.
- Fixtures locales de demo: permiten una prueba reproducible sin inventar URLs ni
  depender de servicios externos.

## Costo, latencia, privacidad y operación

El contexto se limita y el perfil usa un modelo económico, pero no hay una
medición observada para afirmar costo o latencia. SQLite persiste evidencia mínima
y no credenciales; workspaces son temporales. Logs JSON incluyen correlation ID y
metadatos de solicitudes, no cuerpos ni prompts completos. Docker Compose incluye
usuarios no root y healthchecks, pendientes de validación en un daemon real.

## Resultados, límites y siguientes pasos

La evidencia local valida fail-before/pass-after del precio y suites seguras. No
demuestra una corrida GitHub/LLM/Docker completa, diez ejecuciones ni métricas.
Siguientes pasos: completar el flujo de runner integrado, ejecutar los controles
de seguridad Docker, registrar diez corridas controladas y añadir un segundo
adaptador LLM con contract tests.

## Uso transparente de IA

Se usó IA asistiva para acelerar implementación y documentación. Las decisiones
de arquitectura, el alcance y la revisión de cambios corresponden al candidato.
Los outputs del modelo se validan con Pydantic y no deciden el gate; los resultados
que se afirman en la demo proceden de pytest local. No se persiste razonamiento
interno del modelo. Las limitaciones indicadas arriba continúan abiertas.
