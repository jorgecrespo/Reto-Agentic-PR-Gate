# AGENTS.md

## 1. Propósito

Este archivo define cómo debe trabajar OpenCode dentro de este repositorio.

El objetivo del proyecto es construir un prototipo funcional para el reto técnico **Full Stack Engineer · IA Agéntica**. El sistema analizará un pull request de GitHub y demostrará estas dos capacidades:

1. Detectar un problema en el código, proponer una corrección y validarla.
2. Decidir, mediante criterios explícitos y trazables, si el cambio está listo para avanzar de **Pull Request a QA**.

El producto debe priorizar criterio de ingeniería, reproducibilidad, seguridad, trazabilidad y claridad. No debe convertirse en una plataforma genérica de code review ni intentar cubrir todo el SDLC.

---

## 2. Orden de autoridad

Antes de modificar código, leer en este orden:

1. `AGENTS.md`
2. `spec.md`
3. `plan.md`
4. `tasks.md`
5. Código, tests y documentación existentes

En caso de contradicción:

- `spec.md` define **qué debe hacer el producto**.
- `plan.md` define **cómo debe implementarse**.
- `tasks.md` define **el orden de ejecución**.
- `AGENTS.md` define **cómo debe trabajar el agente de desarrollo**.

No cambiar requisitos funcionales para simplificar una implementación sin documentar la desviación.

---

## 3. Forma de trabajo obligatoria

Para cada tarea:

1. Inspeccionar el estado actual del repositorio.
2. Identificar archivos afectados, dependencias y tests existentes.
3. Explicar brevemente el enfoque antes de modificar.
4. Implementar el cambio mínimo necesario.
5. Agregar o actualizar tests.
6. Ejecutar los controles relevantes.
7. Corregir fallos antes de continuar.
8. Actualizar `tasks.md` solamente cuando la tarea cumpla su definición de terminado.
9. Registrar decisiones no triviales en el README.

No instalar dependencias ni modificar configuración global sin comprobar antes que sean necesarias.

No hacer refactors no relacionados con la tarea actual.

No ocultar errores con fallbacks silenciosos.

---

## 4. Principios de implementación

### 4.1 Alcance controlado

El MVP analiza una URL de pull request de GitHub y produce una propuesta. No debe:

- hacer merge;
- hacer push;
- aprobar el PR en GitHub;
- publicar comentarios automáticamente;
- desplegar a QA;
- ejecutar comandos elegidos libremente por el LLM;
- afirmar que una corrección funciona sin evidencia de ejecución.

Todas las operaciones contra GitHub son de solo lectura en el MVP.

### 4.2 Separar IA de lógica determinística

El LLM puede:

- analizar el diff y el contexto;
- formular un hallazgo;
- proponer un parche;
- proponer un test de regresión;
- relacionar el cambio con criterios de aceptación;
- producir explicaciones estructuradas.

El LLM no puede decidir por sí solo:

- si un comando se ejecuta;
- qué comando del sistema ejecutar;
- si una prueba pasó;
- si un parche se aplicó correctamente;
- si el cambio está listo para QA.

Esas decisiones deben surgir de herramientas determinísticas y del motor de políticas.

### 4.3 Evidencia antes que confianza

Toda conclusión debe apuntar a evidencia:

- archivo y rango de líneas;
- fragmento relevante;
- resultado de una herramienta;
- exit code;
- test fallido o aprobado;
- criterio de aceptación;
- regla del gate.

No inventar archivos, líneas, resultados de tests ni estados de GitHub.

Cuando falte evidencia, usar `INCONCLUSIVE`, no `READY`.

### 4.4 Salidas estructuradas

Toda salida del LLM que alimente lógica posterior debe validarse con modelos Pydantic.

No parsear respuestas mediante expresiones regulares frágiles si puede usarse JSON estructurado.

No almacenar ni mostrar razonamiento interno extenso. Solicitar y conservar únicamente:

- conclusión;
- evidencia;
- justificación breve;
- confianza;
- riesgos;
- acción recomendada.

---

## 5. Invariantes arquitectónicas

Mantener estas fronteras:

- `domain/`: entidades y reglas puras, sin FastAPI, SQLite, GitHub ni LLM.
- `application/`: casos de uso y orquestación.
- `infrastructure/`: GitHub, SQLite, LLM, Docker/subprocess y otros adaptadores.
- `api/`: rutas HTTP, validación y serialización.
- `graph/`: estado, nodos y construcción de LangGraph.
- `frontend/`: aplicación React independiente.

La lógica del quality gate debe ser una función determinística testeable sin LLM ni base de datos.

Los nodos de LangGraph deben ser pequeños, nombrados y testeables de forma aislada.

No introducir un framework adicional de agentes salvo que resuelva una necesidad documentada.

---

## 6. Backend

### Stack objetivo

- Python 3.12
- FastAPI
- LangGraph Graph API
- Pydantic v2
- SQLAlchemy 2
- Alembic
- SQLite
- HTTPX
- proveedor LLM configurable mediante una abstracción propia y un adaptador compatible con múltiples proveedores
- pytest
- Ruff
- mypy o pyright
- Docker para ejecución aislada de código no confiable

### Reglas

- Usar type hints en interfaces públicas.
- Evitar diccionarios sin tipo en el dominio.
- Usar IDs UUID.
- Guardar timestamps en UTC.
- No mezclar modelos ORM con modelos de dominio.
- No exponer stack traces al frontend.
- Usar errores tipados.
- Hacer idempotente el inicio de un análisis cuando sea posible.
- Asociar cada ejecución con `analysis_id`, `repository`, `pr_number`, `base_sha`, `head_sha`, `policy_version`, `prompt_version` y `model_id`.

---

## 7. LangGraph

Modelar un workflow predominantemente dirigido, no un agente autónomo de navegación libre.

El grafo debe usar estado tipado y nodos explícitos. Flujo esperado:

1. `validate_request`
2. `fetch_pull_request`
3. `prepare_workspaces`
4. `build_context`
5. `scan_context`
6. `analyze_change`
7. `generate_candidate_fix`
8. `validate_patch_shape`
9. `run_baseline_regression`
10. `run_candidate_validation`
11. `evaluate_acceptance_criteria`
12. `apply_quality_gate`
13. `persist_report`
14. `finalize`

Usar ramas condicionales para:

- entrada inválida;
- PR inaccesible;
- contexto inseguro;
- ausencia de hallazgo;
- parche inválido;
- infraestructura de tests no disponible;
- validación fallida;
- finalización correcta.

Persistir checkpoints de LangGraph solamente si aportan recuperación real. No confundir los checkpoints del grafo con la persistencia de negocio. La fuente de verdad de los análisis terminados es la base de datos de la aplicación.

---

## 8. Integración con LLM

### Configuración

Los proveedores y modelos disponibles se configuran del lado servidor. El frontend selecciona un `model_profile_id`; nunca recibe ni envía API keys.

Variables sensibles:

- solamente en variables de entorno o secret manager;
- nunca en SQLite;
- nunca en logs;
- nunca en respuestas HTTP;
- nunca en fixtures versionados.

### Abstracción

Definir un protocolo similar a:

```python
class LLMGateway(Protocol):
    async def analyze_change(self, request: AnalysisPrompt) -> AnalysisOutput: ...
    async def propose_fix(self, request: FixPrompt) -> FixOutput: ...
```

La aplicación no debe depender directamente de un proveedor concreto.

### Robustez

- Configurar timeout.
- Limitar reintentos.
- Registrar uso de tokens cuando el proveedor lo exponga.
- Registrar costo estimado sin bloquear si no puede calcularse.
- Validar outputs con Pydantic.
- No reintentar indefinidamente.
- No enviar el repositorio completo por defecto.
- Redactar posibles secretos antes de formar el prompt.

---

## 9. GitHub

La entrada principal es una URL de PR:

```text
https://github.com/{owner}/{repo}/pull/{number}
```

El adaptador debe recuperar, como mínimo:

- owner;
- repositorio;
- número;
- título;
- descripción;
- estado draft;
- autor;
- base SHA;
- head SHA;
- archivos modificados;
- patches/diff disponibles;
- commits;
- checks consultables;
- datos necesarios para clonar o descargar el código.

Reglas:

- Token con permisos mínimos y solo lectura.
- Soportar repositorios públicos sin token cuando GitHub lo permita.
- Manejar rate limits y errores de autorización.
- Fijar el análisis al `head_sha`; no analizar una referencia mutable sin registrarla.
- Verificar límites de tamaño y cantidad de archivos.
- No seguir submódulos ni descargar Git LFS en el MVP.
- Rechazar o marcar `INCONCLUSIVE` los PRs cuyo diff no pueda recuperarse de forma íntegra.

---

## 10. Ejecución de código no confiable

El código de un PR puede ser malicioso.

Por defecto, ejecutar tests en un contenedor efímero con:

- red deshabilitada;
- usuario no root;
- CPU y memoria limitadas;
- timeout;
- filesystem temporal;
- sin montar secretos;
- sin montar el socket de Docker;
- sin acceso de escritura al repositorio original;
- lista cerrada de comandos permitidos.

El LLM nunca proporciona el comando ejecutable.

Los comandos se obtienen de una configuración administrada, por ejemplo:

```yaml
validation_profiles:
  python-demo:
    test_command: ["python", "-m", "pytest", "-q"]
    lint_command: ["ruff", "check", "."]
```

Si se implementa un runner local para desarrollo, debe estar deshabilitado por defecto y mostrar una advertencia explícita.

---

## 11. Quality gate

La transición evaluada es:

```text
Pull Request -> QA
```

Estados permitidos:

- `READY`
- `CONDITIONAL`
- `BLOCKED`
- `INCONCLUSIVE`

La política debe estar versionada y separada del prompt.

Reglas mínimas:

- tests obligatorios ejecutados;
- tests obligatorios aprobados;
- ausencia de hallazgos críticos;
- ausencia de secretos;
- criterios de aceptación obligatorios evaluados;
- parche aplicable;
- test de regresión que falle antes y pase después para considerar validada la corrección;
- análisis fijado al SHA actual del PR.

El gate debe devolver razones, evidencia, controles no ejecutados y acciones necesarias.

---

## 12. SQLite

Persistir:

- PRs observados;
- snapshots por SHA;
- ejecuciones;
- configuración no sensible del modelo elegido;
- hallazgos;
- parches propuestos;
- resultados de comandos;
- evaluaciones de criterios;
- decisiones del gate;
- eventos resumidos de ejecución.

No persistir:

- tokens de GitHub;
- API keys;
- variables de entorno;
- repositorios clonados;
- archivos `.env`;
- razonamiento interno del modelo;
- código completo salvo que `spec.md` lo requiera expresamente.

Usar migraciones Alembic desde el comienzo.

---

## 13. Frontend

### Stack

- React 19
- TypeScript estricto
- Vite
- React Router
- TanStack Query
- CSS simple y mantenible

### Reglas

- La UI debe priorizar evidencia, no efectos visuales.
- Representar claramente estados de carga, error y vacío.
- No asumir que `FAILED` significa hallazgo funcional.
- Mostrar diferencia entre `BLOCKED` e `INCONCLUSIVE`.
- Escapar todo contenido proveniente del repositorio.
- No usar `dangerouslySetInnerHTML`.
- No exponer secretos.
- No implementar autenticación completa en el MVP.
- Mantener componentes presentacionales separados de acceso a API.
- No duplicar tipos manualmente si pueden generarse desde OpenAPI.

Pantallas mínimas:

1. Inicio de análisis.
2. Progreso.
3. Informe.
4. Historial.
5. Configuración visible de modelos y política, solo lectura.

---

## 14. Testing

### Backend

Incluir:

- tests unitarios del motor de políticas;
- tests unitarios de parsers de URL;
- tests del constructor de contexto;
- tests de validación de outputs LLM;
- tests de nodos LangGraph;
- tests de repositorios SQLite;
- tests de API;
- tests de integración con GitHub simulado;
- tests del runner con comandos inocuos;
- golden tests de reportes estructurados cuando aporte valor.

### Frontend

Incluir:

- tests de componentes críticos;
- tests de estados READY/BLOCKED/INCONCLUSIVE;
- tests del formulario;
- tests de la navegación;
- al menos un flujo E2E de análisis simulado.

### Demo e-commerce

Debe contener tests que permitan demostrar:

- el test de regresión falla sobre el cambio defectuoso;
- la corrección propuesta evita la manipulación de precios;
- la suite pasa después de la corrección;
- un cambio seguro obtiene `READY`.

---

## 15. Calidad mínima antes de cerrar una tarea

Ejecutar, según corresponda:

```bash
ruff check .
ruff format --check .
mypy backend
pytest
npm run lint
npm run typecheck
npm run test
npm run build
```

No marcar una tarea como terminada si:

- hay tests relevantes fallando;
- la compilación falla;
- quedaron TODOs necesarios para la funcionalidad;
- no existe manejo de error;
- la documentación quedó desactualizada.

---

## 16. Documentación

El README es el documento único del proyecto. Mantener en él:

- requisitos, incluido Docker corriendo;
- arranque con un solo comando Docker e instalación para desarrollo;
- uso, claves opcionales y reset de la base para demo;
- resumen de arquitectura, modelo de seguridad y política del gate;
- variables de entorno;
- guía breve para agregar proveedores;
- troubleshooting y limitaciones;
- guía de demo en `scripts/create_demo_prs.md`.

Toda afirmación de performance, costo o cobertura debe provenir de una medición.

---

## 17. Prohibiciones

No:

- ejecutar comandos generados por el LLM;
- hacer push, merge o comentarios automáticos;
- almacenar secretos;
- exponer prompts con código sensible en logs;
- aprobar un cambio si faltó una validación obligatoria;
- usar el LLM como único quality gate;
- capturar excepciones con `except Exception: pass`;
- agregar dependencias sin uso;
- afirmar compatibilidad con un proveedor no probado;
- usar mocks en la demo final para ocultar un flujo principal incompleto;
- sacrificar seguridad para conseguir una demo visual.

---

## 18. Definición global de terminado

El proyecto está terminado cuando:

1. Recibe una URL de PR válida.
2. Recupera y fija el análisis al SHA del PR.
3. Construye contexto acotado y seguro.
4. Detecta el problema intencional del ejemplo.
5. Propone un parche y un test.
6. Demuestra que el test falla antes y pasa después.
7. Ejecuta la suite completa sobre la corrección.
8. Produce una decisión trazable para PR -> QA.
9. Persiste el resultado en SQLite.
10. Muestra el informe desde React.
11. Puede ejecutarse siguiendo el README.
12. Tiene una demo reproducible con al menos un caso `BLOCKED` y uno `READY`.
