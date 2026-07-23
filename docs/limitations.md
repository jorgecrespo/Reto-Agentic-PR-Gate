# Limitaciones y bloqueos operativos

- Un análisis real end-to-end requiere `OPENAI_API_KEY`, una URL GitHub accesible,
  un token de solo lectura cuando aplique y Docker operativo.
- Solo existe el perfil `python-demo`; no se infieren comandos desde repositorios
  ni respuestas del modelo.
- Los jobs en proceso no sobreviven reinicios. Los informes terminados sí quedan
  persistidos; los huérfanos se marcan `INCONCLUSIVE`.
- SQLite es para una instancia local. No hay cola distribuida, límite de
  concurrencia ni validación de locks bajo carga demostrada.
- La salida LLM no es determinista. El gate es determinista únicamente respecto
  de los facts recolectados.
- La demo versionada usa fixtures locales. El runner Docker y el stack Compose
  fueron verificados localmente, pero la demo no demuestra conectividad GitHub
  ni un proveedor LLM real.
- No se han ejecutado diez análisis controlados ni se reportan métricas de
  detección, latencia, tokens, costo o falsos positivos. Esas métricas permanecen
  pendientes y no deben presentarse como resultados.
- El sistema recomienda PR -> QA solamente; no escribe en GitHub, no hace merge,
  no publica comentarios y no despliega.
