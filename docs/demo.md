# Demo local y PRs opcionales

La demo comprobable del repositorio no depende de GitHub, un proveedor LLM ni
Docker. `scripts/demo.sh` ejecuta fixtures locales y verifica el código de salida
de pytest: el baseline defectuoso falla por la aserción de precio, el candidate
corregido pasa, y el cambio seguro pasa. El caso inconcluso está declarado en un
fixture porque representa una validación obligatoria que no se ejecutó.

Esto no sustituye un análisis end-to-end. En particular, no debe presentarse como
evidencia de que GitHub, Docker o un LLM real funcionaron en este entorno.

## Ramas opcionales

`scripts/create_demo_prs.md` documenta nombres, títulos, cuerpos y criterios
para crear tres PRs en un fork. No hay URLs de PRs versionadas ni se crean ramas,
commits o PRs automáticamente. Al ejecutar contra un PR real, registre la URL,
SHA, perfil, hora y resultado en la evidencia de la presentación.

## Guion

1. Mostrar la política y la diferencia entre `BLOCKED` e `INCONCLUSIVE`.
2. Ejecutar la fixture defectuosa y mostrar su fallo de aserción.
3. Ejecutar candidate y mostrar la corrección de precio de catálogo.
4. Ejecutar el escenario seguro.
5. Mostrar el fixture inconcluso y explicar que un control obligatorio ausente no
   puede producir `READY`.
6. Si hay credenciales y Docker operativos, repetir con un PR propio accesible,
   sin afirmar éxito hasta conservar el informe persistido.
