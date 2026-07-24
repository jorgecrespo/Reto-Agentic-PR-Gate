# Generar PRs de demostración

Este documento describe 8 PRs manuales para probar el sistema con URLs reales de GitHub.
La base común es `examples/demo_ecommerce/`.

## Reglas comunes

- Crear todos los PRs desde el mismo SHA base.
- Abrir cada PR en GitHub, sin merges automáticos.
- Registrar la URL final de cada PR.
- No usar fixtures locales ni atajos fuera del flujo normal del sistema.

## PRs que deben dar `READY`

### PR 1: refactor sin cambio funcional

- Rama sugerida: `demo/ready-refactor-total`
- Cambio: extraer un helper puro en `app/orders.py` para calcular el total por ítem, sin cambiar el comportamiento.
- Ajuste: agregar o mover tests para cubrir el mismo resultado.
- Resultado esperado: `READY`
- Motivo: no hay hallazgo crítico, no se cambia la lógica de negocio y la suite sigue pasando.

### PR 2: cobertura adicional sin cambio funcional

- Rama sugerida: `demo/ready-add-coverage`
- Cambio: agregar un test nuevo en `tests/test_orders.py` para un caso válido adicional, por ejemplo múltiples ítems del mismo carrito.
- Ajuste: no modificar la lógica de negocio.
- Resultado esperado: `READY`
- Motivo: solo aumenta cobertura y evidencia; no introduce advertencias ni bloqueos.

## PRs que deben dar `CONDITIONAL`

### PR 3: cambio de lógica con PR en draft

- Rama sugerida: `demo/conditional-draft-business-change`
- Cambio: agregar una mejora real, por ejemplo un campo opcional nuevo en `app/domain.py` que no rompa la compatibilidad.
- Ajuste: crear el PR como `draft`.
- Resultado esperado: `CONDITIONAL`
- Motivo: la política marca `pr_is_draft` como advertencia aceptable.

### PR 4: cambio de negocio sin tests nuevos

- Rama sugerida: `demo/conditional-business-no-tests`
- Cambio: modificar la lógica de negocio, por ejemplo agregar un descuento simple o una regla extra de cálculo.
- Ajuste: no agregar ni actualizar tests en el mismo PR.
- Resultado esperado: `CONDITIONAL`
- Motivo: la política marca `business_logic_changed=true` y `tests_changed=false` como advertencia aceptable.

## PRs que deben dar `BLOCKED`

### PR 5: reintroducir el bug de precio

- Rama sugerida: `demo/blocked-client-price`
- Cambio: cambiar `app/orders.py` para volver a usar `item.unit_price` en lugar del precio del catálogo.
- Ajuste: conservar `tests/test_orders.py` como verificación del precio correcto.
- Resultado esperado: `BLOCKED`
- Motivo: aparece un hallazgo crítico y la regresión falla.

### PR 6: introducir un secreto en el código

- Rama sugerida: `demo/blocked-secret-leak`
- Cambio: agregar en el código o en una prueba una cadena con patrón de secreto sensible, por ejemplo una clave falsa con prefijo tipo `sk-...` o un bloque de clave privada de prueba.
- Ajuste: no intentar ocultarlo ni redactarlo dentro del PR.
- Resultado esperado: `BLOCKED`
- Motivo: el detector de secretos debe disparar el bloqueo.

## PRs que deben dar `INCONCLUSIVE`

### PR 7: cambiar el head SHA durante el análisis

- Rama sugerida: `demo/inconclusive-head-sha-change`
- Cambio: preparar un PR normal y, una vez iniciado el análisis, subir un commit adicional al mismo branch.
- Ajuste: el SHA analizado debe quedar desactualizado antes de finalizar.
- Resultado esperado: `INCONCLUSIVE`
- Motivo: el análisis no queda fijado al `head_sha` original.

### PR 8: diff o acceso no recuperable

- Rama sugerida: `demo/inconclusive-inaccessible-diff`
- Cambio: abrir el PR en un fork o repositorio al que el analizador no tenga acceso completo, o provocar que el diff no pueda recuperarse íntegramente.
- Ajuste: no convertirlo en un simple fallo funcional; la condición debe ser de evidencia incompleta.
- Resultado esperado: `INCONCLUSIVE`
- Motivo: falta evidencia suficiente para aprobar o bloquear con confianza.

## Registro final

Para cada PR, anotar:

- URL del PR
- SHA base
- SHA final
- resultado esperado
- resultado observado
- evidencia usada por el gate
