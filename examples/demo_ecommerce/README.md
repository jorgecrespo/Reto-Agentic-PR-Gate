# Demo e-commerce local

Los escenarios son fixtures locales para demostrar el flujo sin afirmar que se
consultaron PRs reales de GitHub.

- `scenarios/defective`: baseline con el defecto intencional. Su test de regresión
  falla porque cobra `unit_price` del request.
- `scenarios/candidate`: corrección esperada. Obtiene el precio de catálogo y su
  suite pasa.
- `scenarios/safe`: cambio seguro pequeño, `description` opcional para productos.
- `scenarios/inconclusive.json`: validación obligatoria no disponible; por política
  el resultado esperado es `INCONCLUSIVE`, nunca `READY`.

Ejecutar `./scripts/demo.sh` desde la raíz. El script verifica códigos de salida
reales de pytest para los tres escenarios que ejecutan código y presenta el caso
inconcluso como fixture declarativo.
