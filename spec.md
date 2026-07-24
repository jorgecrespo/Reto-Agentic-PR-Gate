# spec.md

## 1. Identificación

**Nombre de trabajo:** Agentic PR Gate  
**Tipo:** prototipo full stack para reto técnico  
**Transición evaluada:** Pull Request -> QA  
**Entrada principal:** URL de pull request de GitHub  
**Backend:** Python, FastAPI y LangGraph  
**Frontend:** React 19 con TypeScript  
**Persistencia:** SQLite  
**LLM:** proveedor y modelo seleccionables mediante configuración del servidor

---

## 2. Contexto

Un equipo mantiene storefronts de e-commerce. Las revisiones son lentas e inconsistentes, ciertos bugs se descubren tarde y no existe evidencia uniforme para determinar si un cambio está listo para QA.

El producto debe demostrar dos capacidades:

1. **Detectar un problema en el código, proponer una corrección y validarla.**
2. **Decidir, mediante criterios explícitos, si el cambio está listo para avanzar a QA.**

La solución debe ser económica, razonablemente rápida, cuidadosa con la privacidad del código y reproducible por otra persona.

---

## 3. Objetivo del producto

Dada la URL de un PR de GitHub, el sistema debe:

1. recuperar el cambio y su contexto relevante;
2. analizar el cambio con asistencia de un LLM;
3. detectar al menos un problema concreto cuando exista evidencia suficiente;
4. proponer un parche y un test de regresión;
5. validar la propuesta en workspaces aislados;
6. recopilar evidencia determinística;
7. aplicar una política versionada;
8. emitir una decisión `READY`, `CONDITIONAL`, `BLOCKED` o `INCONCLUSIVE`;
9. persistir el análisis;
10. presentar el resultado en una interfaz web.

---

## 4. Usuarios

### 4.1 Desarrollador

Quiere entender:

- qué problema se detectó;
- dónde está;
- por qué importa;
- cómo podría corregirse;
- qué debe hacer para desbloquear el PR.

### 4.2 Revisor técnico o TPO

Quiere saber:

- qué controles se ejecutaron;
- cuáles pasaron o fallaron;
- qué riesgos quedan;
- si existe evidencia suficiente para enviar el cambio a QA.

### 4.3 Responsable del piloto

Quiere observar:

- duración;
- modelo usado;
- costo estimado;
- errores;
- limitaciones;
- consistencia de las decisiones.

---

## 5. Supuestos del MVP

- El PR pertenece a GitHub.com.
- El repositorio usa Git.
- La demo principal analiza código Python del mini e-commerce incluido en el repositorio.
- Los comandos de validación se eligen de perfiles administrados, no desde el PR ni desde el LLM.
- El sistema no modifica GitHub.
- El sistema no despliega a QA; solamente recomienda si el PR puede avanzar.
- Los proveedores LLM disponibles se configuran en el backend.
- Las API keys no se ingresan desde el navegador.
- El análisis se fija al `head_sha` recibido al comenzar.
- Para validar código se dispone de Docker en el entorno de ejecución.

---

## 6. Fuera de alcance

- Merge automático.
- Comentarios automáticos en GitHub.
- Creación automática de commits.
- Despliegue real.
- Autenticación empresarial.
- Soporte garantizado para cualquier lenguaje.
- Análisis de monorepos de tamaño empresarial.
- Revisión exhaustiva de arquitectura.
- Detección completa de vulnerabilidades.
- Decisión autónoma de producción.
- Aprendizaje continuo del modelo.
- Entrenamiento o fine-tuning.
- Sistema multi-tenant.

---

## 7. Entrada principal

### 7.1 Solicitud de análisis

```json
{
  "pull_request_url": "https://github.com/org/repo/pull/42",
  "model_profile_id": "openai-small",
  "validation_profile_id": "python-demo",
  "acceptance_criteria": [
    {
      "id": "AC-1",
      "text": "El total de la orden debe usar el precio vigente del catálogo",
      "required": true
    }
  ]
}
```

### 7.2 Datos obtenidos desde GitHub

Como mínimo:

- owner;
- repository;
- PR number;
- title;
- body;
- author;
- draft;
- state;
- base ref y SHA;
- head ref y SHA;
- commits;
- archivos modificados;
- additions/deletions;
- patch o diff;
- checks disponibles;
- URL de clonación.

### 7.3 Configuración administrada

#### Perfil de modelo

```yaml
id: openai-small
provider: openai
model: provider/model-name
temperature: 0
timeout_seconds: 60
max_retries: 2
enabled: true
```

#### Perfil de validación

```yaml
id: python-demo
allowed_paths:
  - app/**
  - tests/**
test_command:
  - python
  - -m
  - pytest
  - -q
lint_command:
  - ruff
  - check
  - .
timeout_seconds: 120
network_enabled: false
```

No guardar secretos en estos perfiles.

---

## 8. Flujo funcional

```text
Usuario ingresa PR
        |
        v
Validación y lectura de GitHub
        |
        v
Snapshot fijo por head SHA
        |
        v
Selección y saneamiento de contexto
        |
        v
Análisis estructurado con LLM
        |
        v
Hallazgo + parche + test propuesto
        |
        v
Test nuevo sobre código original
        |
        +-- debe fallar y reproducir el problema
        |
        v
Parche + test sobre workspace corregido
        |
        +-- deben pasar el test y la suite
        |
        v
Evaluación de criterios de aceptación
        |
        v
Motor de quality gate
        |
        v
Informe persistido y mostrado
```

---

## 9. Requisitos funcionales

### FR-001 — Crear análisis

El usuario puede ingresar una URL de PR, seleccionar un perfil de modelo y comenzar un análisis.

### FR-002 — Validar URL

El sistema valida que la URL tenga formato GitHub PR. Una URL inválida devuelve un error accionable.

### FR-003 — Obtener PR

El sistema obtiene metadata, SHAs, archivos, diff y checks disponibles mediante la API de GitHub.

### FR-004 — Fijar snapshot

Toda ejecución queda asociada al `head_sha` original. Si el PR cambia durante el análisis, el informe debe indicar que existe una versión más nueva.

### FR-005 — Limitar alcance

El sistema aplica límites configurables:

- cantidad máxima de archivos;
- tamaño total del diff;
- extensiones permitidas;
- paths permitidos;
- tamaño máximo por archivo;
- exclusión de binarios.

Cuando no pueda analizar con integridad, devuelve `INCONCLUSIVE`.

### FR-006 — Preparar workspaces

El sistema prepara dos copias efímeras del código:

- baseline: código del PR sin corrección;
- candidate: código del PR con corrección propuesta.

Ninguna modificación se aplica al repositorio original.

### FR-007 — Construir contexto

El contexto incluye:

- descripción del PR;
- criterios de aceptación;
- diff;
- contenido acotado de archivos modificados;
- imports o dependencias directas;
- tests relacionados;
- convenciones del proyecto cuando estén disponibles.

### FR-008 — Sanear contexto

Antes de enviar contenido al LLM, el sistema:

- excluye archivos sensibles;
- detecta patrones de secretos;
- redacta valores sospechosos;
- evita enviar `.env`, llaves, certificados y binarios;
- registra hashes y nombres de archivos, no secretos.

### FR-009 — Seleccionar LLM

El usuario puede elegir entre los perfiles habilitados informados por el backend.

El backend debe exponer un contrato que permita agregar proveedores sin modificar el dominio.

### FR-010 — Analizar cambio

El LLM devuelve una estructura validada con:

- resumen;
- hallazgos;
- categoría;
- severidad;
- archivo;
- líneas o fragmento;
- explicación;
- impacto;
- evidencia;
- confianza;
- acción recomendada.

### FR-011 — Proponer corrección

Para un hallazgo seleccionado, el sistema propone:

- archivos a modificar;
- parche unified diff;
- explicación breve;
- supuestos;
- test de regresión;
- archivos afectados;
- comandos de validación solicitados del perfil, no del LLM.

### FR-012 — Validar parche

Antes de ejecutarlo:

- debe ser un diff válido;
- solo puede modificar paths permitidos;
- no puede modificar configuración de infraestructura del runner;
- no puede escribir fuera del workspace;
- no puede incluir archivos binarios;
- no puede agregar secretos evidentes.

### FR-013 — Probar reproducción

El test de regresión propuesto se aplica al baseline sin la corrección.

Para considerar que el test reproduce el problema:

- el test debe ejecutarse;
- debe fallar;
- el fallo debe corresponder a la aserción del comportamiento esperado;
- no debe fallar por importación, sintaxis o infraestructura.

### FR-014 — Probar corrección

En el workspace candidate se aplican:

1. parche de código;
2. test de regresión;
3. validaciones administradas.

Para considerar validada la corrección:

- el parche se aplica;
- el test de regresión pasa;
- la suite completa pasa;
- no aparecen errores de lint bloqueantes;
- no aparecen nuevos secretos.

### FR-015 — Evaluar aceptación

El sistema registra para cada criterio:

- `PASSED`;
- `FAILED`;
- `NOT_EVALUATED`;
- evidencia;
- fuente;
- confianza si intervino un LLM.

Un criterio obligatorio `NOT_EVALUATED` impide `READY`.

### FR-016 — Aplicar quality gate

El motor de políticas usa únicamente datos estructurados y resultados verificables.

### FR-017 — Mostrar progreso

La UI muestra el nodo o etapa actual sin exponer prompts ni razonamiento privado.

### FR-018 — Mostrar informe

El informe muestra:

- decisión;
- resumen;
- URL, título, SHA base y SHA analizado del PR;
- hallazgo;
- evidencia;
- parche;
- test;
- comparación before/after;
- validaciones;
- criterios;
- costo y latencia;
- modelo y versión de política;
- limitaciones;
- acciones para desbloquear.

Cada control no ejecutado debe indicar su causa. Si se detecta un secreto, el
informe muestra únicamente archivo, línea y tipo de patrón redactado; no muestra
el valor detectado. Si el LLM no se ejecutó, tokens y costo se reportan como no
aplicables junto con el motivo determinístico.

### FR-019 — Historial

El usuario puede consultar análisis anteriores almacenados en SQLite.

### FR-020 — Reanálisis

El usuario puede iniciar un nuevo análisis del mismo PR. Cada ejecución conserva su propio `head_sha` y resultados.

### FR-021 — Operación de solo lectura

El sistema no hace push, merge, review ni comentario en GitHub.

---

## 10. Política del gate

### 10.1 Estados

#### READY

El PR puede avanzar a QA según la política evaluada.

#### CONDITIONAL

No existe un bloqueo crítico, pero queda una condición explícita que debe aceptarse o resolverse.

#### BLOCKED

Existe al menos una regla bloqueante incumplida.

#### INCONCLUSIVE

No hay evidencia suficiente para aprobar o bloquear de forma confiable, o falló infraestructura requerida.

### 10.2 Reglas mínimas

| ID | Regla | Resultado si falla |
|---|---|---|
| GATE-001 | Análisis fijado al head SHA actual | INCONCLUSIVE |
| GATE-002 | Contexto mínimo disponible | INCONCLUSIVE |
| GATE-003 | Tests obligatorios ejecutados | INCONCLUSIVE |
| GATE-004 | Tests obligatorios aprobados | BLOCKED |
| GATE-005 | Cero hallazgos críticos sin mitigar | BLOCKED |
| GATE-006 | Cero secretos detectados | BLOCKED |
| GATE-007 | Criterios obligatorios evaluados | INCONCLUSIVE |
| GATE-008 | Criterios obligatorios aprobados | BLOCKED |
| GATE-009 | Parche aplicable | BLOCKED |
| GATE-010 | Test de regresión reproduce el problema | BLOCKED |
| GATE-011 | Test de regresión pasa con el parche | BLOCKED |
| GATE-012 | Suite completa pasa con el parche | BLOCKED |
| GATE-013 | Cambio de lógica de negocio con tests | CONDITIONAL |
| GATE-014 | PR no está en draft | CONDITIONAL |
| GATE-015 | No existe una versión nueva del PR | INCONCLUSIVE |

### 10.3 Precedencia

1. `BLOCKED` si `GATE-006` detecta un secreto, aunque controles posteriores no se ejecuten.
2. `INCONCLUSIVE` por imposibilidad de evaluar una regla obligatoria.
3. `BLOCKED` por otro incumplimiento comprobado.
4. `CONDITIONAL` por advertencias aceptables.
5. `READY` cuando no existe ninguna condición anterior.

Una misma ejecución puede listar blockers y warnings, pero el estado sigue la precedencia definida.

---

## 11. Contrato del hallazgo

```json
{
  "id": "uuid",
  "title": "Client-controlled product price",
  "category": "security",
  "severity": "critical",
  "file_path": "examples/demo_ecommerce/app/orders/service.py",
  "start_line": 18,
  "end_line": 18,
  "evidence_excerpt": "total += item.unit_price * item.quantity",
  "explanation": "El servicio confía en un precio controlado por el cliente.",
  "impact": "Permite comprar productos a un precio arbitrario.",
  "recommended_action": "Obtener el precio desde ProductRepository.",
  "confidence": 0.98
}
```

No aceptar un hallazgo sin archivo o evidencia salvo que se marque explícitamente como limitación general.

---

## 12. Contrato de corrección

```json
{
  "finding_id": "uuid",
  "summary": "Use catalog price on order creation",
  "patch": "diff --git ...",
  "regression_test_patch": "diff --git ...",
  "modified_paths": [
    "examples/demo_ecommerce/app/orders/service.py",
    "examples/demo_ecommerce/tests/test_order_service.py"
  ],
  "assumptions": [
    "ProductRepository is the source of truth for current price"
  ]
}
```

---

## 13. Contrato de decisión

```json
{
  "status": "BLOCKED",
  "target_stage": "QA",
  "policy_version": "1.0.0",
  "summary": "El cambio no está listo para QA.",
  "blocking_reasons": [
    {
      "rule_id": "GATE-005",
      "message": "Existe un hallazgo crítico sin mitigar.",
      "evidence_ids": ["finding-uuid"]
    }
  ],
  "warnings": [],
  "passed_rules": ["GATE-001", "GATE-003"],
  "not_evaluated_rules": [],
  "required_actions": [
    "Aplicar la corrección propuesta y repetir la suite."
  ]
}
```

---

## 14. Persistencia

### 14.1 Entidades mínimas

#### `pull_requests`

- id
- owner
- repository
- number
- url
- title
- author

#### `pr_snapshots`

- id
- pull_request_id
- base_sha
- head_sha
- draft
- metadata_json
- created_at

#### `analysis_runs`

- id
- snapshot_id
- status
- model_profile_id
- policy_version
- prompt_version
- started_at
- finished_at
- duration_ms
- input_tokens
- output_tokens
- estimated_cost
- error_code
- error_message

#### `findings`

- id
- analysis_run_id
- category
- severity
- title
- file_path
- start_line
- end_line
- evidence_excerpt
- explanation
- impact
- recommendation
- confidence

#### `candidate_fixes`

- id
- finding_id
- patch
- regression_test_patch
- patch_hash
- status

#### `validation_runs`

- id
- analysis_run_id
- phase
- command_name
- exit_code
- stdout_excerpt
- stderr_excerpt
- duration_ms
- timed_out
- result

#### `acceptance_evaluations`

- id
- analysis_run_id
- criterion_id
- criterion_text
- required
- status
- evidence_json

#### `gate_decisions`

- id
- analysis_run_id
- status
- target_stage
- policy_version
- summary
- reasons_json
- warnings_json
- required_actions_json

#### `run_events`

- id
- analysis_run_id
- sequence
- event_type
- node
- message
- created_at

### 14.2 Privacidad

No guardar tokens, API keys, repositorios clonados ni razonamiento interno.

Guardar parches y extractos mínimos porque son necesarios para reproducir el informe. Documentar esta decisión.

---

## 15. API HTTP

### Configuración

- `GET /api/v1/config/models`
- `GET /api/v1/config/validation-profiles`
- `GET /api/v1/config/policy`

### Análisis

- `POST /api/v1/analyses`
- `GET /api/v1/analyses`
- `GET /api/v1/analyses/{analysis_id}`
- `GET /api/v1/analyses/{analysis_id}/events`
- `GET /api/v1/analyses/{analysis_id}/stream`

### Salud

- `GET /health/live`
- `GET /health/ready`

La creación devuelve `202 Accepted` con `analysis_id`.

El progreso puede implementarse mediante Server-Sent Events. Polling queda permitido como fallback.

---

## 16. Interfaz

### 16.1 Pantalla de nuevo análisis

Campos:

- URL del PR;
- modelo;
- perfil de validación;
- criterios de aceptación;
- botón de análisis;
- advertencia de solo lectura.

### 16.2 Pantalla de progreso

Mostrar etapas:

- GitHub;
- contexto;
- análisis;
- corrección;
- baseline;
- candidate;
- gate;
- persistencia.

### 16.3 Pantalla de informe

Secciones:

1. Decisión y etapa objetivo.
2. Resumen del PR: URL, título, SHA base, SHA analizado y estado draft.
3. Hallazgos.
4. Corrección propuesta.
5. Test de regresión.
6. Evidencia antes/después.
7. Suite y herramientas.
8. Criterios de aceptación.
9. Política aplicada con evidencia de cada regla.
10. Controles no ejecutados y su causa.
11. Costo, tokens y duración, o causa de no aplicación.
12. Limitaciones y acciones necesarias.

### 16.4 Historial

Tabla con:

- fecha;
- repositorio;
- PR;
- head SHA corto;
- modelo;
- decisión;
- duración;
- enlace al informe.

---

## 17. Requisitos no funcionales

### NFR-001 — Costo

Objetivo de demo: menos de USD 0,10 por análisis estándar con modelo económico.

Mostrar costo estimado; no prometer exactitud si el proveedor no entrega usage.

### NFR-002 — Latencia

Objetivo de demo: menos de 90 segundos excluyendo instalación inicial de la imagen de validación.

Registrar tiempos por etapa.

### NFR-003 — Seguridad

- GitHub token de solo lectura.
- API keys solo en backend.
- ejecución aislada;
- red deshabilitada durante tests;
- comandos allowlist;
- límites de recursos;
- saneamiento antes del LLM;
- ninguna escritura en GitHub.

### NFR-004 — Operabilidad

La aplicación debe levantarse mediante Docker Compose siguiendo el README.

### NFR-005 — Trazabilidad

Toda decisión debe incluir IDs de reglas y evidencia.

### NFR-006 — Reproducibilidad

Un análisis registra SHA, modelo, versión de prompt y política.

No se garantiza idéntica salida textual del LLM, pero sí el mismo conjunto de controles determinísticos.

### NFR-007 — Accesibilidad

La UI debe ser navegable por teclado y no depender exclusivamente de colores.

### NFR-008 — Observabilidad

Logs JSON con correlation ID y métricas básicas por nodo.

---

## 18. Demo e-commerce

El repositorio incluirá:

```text
examples/demo_ecommerce/
```

Funcionalidades mínimas:

- productos;
- repositorio de productos;
- creación de órdenes;
- cálculo de total;
- validación de cantidad;
- tests con pytest.

### PR defectuoso

Introduce el uso de `unit_price` proveniente del request.

Resultado esperado:

- hallazgo crítico;
- test de regresión falla antes;
- corrección usa precio del catálogo;
- test y suite pasan después;
- decisión antes de mitigar: `BLOCKED`;
- informe de corrección validada.

### PR seguro

Cambio pequeño con tests, por ejemplo agregar `description` opcional a producto.

Resultado esperado:

- sin hallazgos bloqueantes;
- suite aprobada;
- criterios aprobados;
- decisión: `READY`.

### Caso inconcluso

PR o perfil donde el runner no puede completar una validación obligatoria.

Resultado esperado:

- `INCONCLUSIVE`;
- nunca `READY`.

---

## 19. Criterios de aceptación del producto

### AC-PROD-001

Dada una URL válida de PR accesible, se crea un análisis asociado a su head SHA.

### AC-PROD-002

El sistema detecta el uso inseguro de precio controlado por cliente en el PR defectuoso.

### AC-PROD-003

El sistema genera un parche que usa el precio del catálogo.

### AC-PROD-004

El sistema genera un test que falla sobre baseline por el comportamiento funcional esperado, no por un error de infraestructura.

### AC-PROD-005

El test y la suite pasan sobre candidate.

### AC-PROD-006

La decisión `BLOCKED` incluye regla, evidencia y acción para desbloquear.

### AC-PROD-007

El PR seguro produce `READY`.

### AC-PROD-008

La falta de ejecución de tests obligatorios produce `INCONCLUSIVE`.

### AC-PROD-009

Los análisis quedan disponibles en el historial tras reiniciar la aplicación.

### AC-PROD-010

El usuario puede elegir un perfil de modelo configurado sin exponer credenciales.

### AC-PROD-011

Ningún comando devuelto por el LLM se ejecuta.

### AC-PROD-012

Otra persona puede ejecutar la demo siguiendo el README.

---

## 20. Métricas de evaluación de la demo

Registrar al menos diez ejecuciones controladas y reportar:

- tasa de detección del defecto conocido;
- tasa de parche aplicable;
- tasa de validación correcta;
- decisiones esperadas vs. obtenidas;
- latencia total y por etapa;
- tokens;
- costo estimado;
- fallos por proveedor;
- falsos positivos observados.

No presentar estas métricas como evidencia estadística general; son resultados del prototipo.

---

## 21. Transparencia sobre IA

El documento final debe declarar:

- qué código fue generado o asistido por IA;
- qué decisiones de diseño fueron tomadas por el candidato;
- qué outputs se validaron;
- qué limitaciones siguen abiertas;
- que el LLM propone, mientras las herramientas y la política aportan evidencia.
