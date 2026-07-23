Buenos días. El proyecto que desarrollé se llama **Agentic PR Gate** y tiene como objetivo asistir técnicamente la validación de cambios de código antes de que un pull request avance a la etapa de QA.

Para definir el alcance, elegí dos de las capacidades propuestas en el reto. La primera es detectar un problema en el código, proponer una corrección y validar que esa corrección realmente funcione. La segunda es decidir, mediante criterios explícitos, si el cambio está listo para avanzar a la siguiente etapa.

Elegí estas dos capacidades porque juntas permiten demostrar un flujo completo. El sistema no se limita a generar una observación sobre el código. Detecta un problema, propone una solución, obtiene evidencia ejecutando pruebas y finalmente utiliza esa evidencia para tomar una decisión trazable.

La entrada principal del sistema es la URL de un pull request de GitHub. A partir de esa URL, el backend recupera la descripción del PR, los commits, los archivos modificados, el diff, los criterios de aceptación proporcionados por el usuario y el SHA exacto de la versión analizada.

Registrar el SHA es importante porque garantiza que el informe corresponde a una versión concreta del cambio. Si el pull request es modificado durante el análisis, el sistema no lo aprueba silenciosamente, sino que informa que la evaluación quedó desactualizada.

El backend está desarrollado en Python con FastAPI y LangGraph. Utilicé LangGraph para representar el proceso como un workflow dirigido, con estados y etapas claramente definidas. No se trata de un agente completamente autónomo, porque en este caso consideré más importante que el comportamiento fuera previsible, auditable y fácil de probar.

El flujo comienza validando la solicitud y obteniendo el pull request. Luego construye un contexto acotado con el diff, los archivos modificados, los tests relacionados y la documentación relevante.

Antes de enviar información al modelo, el sistema excluye archivos sensibles, limita el tamaño del contexto y detecta posibles secretos. La idea es no enviar todo el repositorio sin necesidad, tanto para reducir costo y latencia como para disminuir la exposición de código.

El proveedor de LLM es configurable. El frontend permite seleccionar entre los perfiles habilitados por el backend, mientras que las claves permanecen únicamente en variables de entorno del servidor.

La arquitectura no depende directamente de un proveedor específico. Existe una interfaz común para analizar el cambio y proponer una corrección, por lo que se puede utilizar Gemini, OpenAI, Anthropic, OpenRouter u otro proveedor mediante un adaptador.

Para la demostración utilizaría un modelo disponible mediante una capa gratuita. Esto permite operar el prototipo sin costo, aunque documento que una modalidad gratuita no sería necesariamente adecuada para código empresarial sensible. En un entorno productivo habría que utilizar un proveedor aprobado por la organización, una modalidad contractual privada o infraestructura propia.

El escenario de prueba utiliza una pequeña aplicación de e-commerce. En el pull request defectuoso, el servicio de creación de órdenes calcula el total utilizando el precio recibido desde el frontend.

Esto representa una vulnerabilidad porque un cliente podría modificar el request y comprar un producto a un precio arbitrario.

El agente analiza el cambio y genera un hallazgo estructurado que contiene el archivo, las líneas afectadas, la severidad, el impacto, la evidencia y una recomendación concreta.

Después propone una corrección: obtener el producto desde el repositorio interno y utilizar el precio almacenado en el catálogo, en lugar de confiar en el precio enviado por el cliente.

También propone un test de regresión. El test envía un producto cuyo precio real es cien, pero intenta comprarlo indicando un precio de uno. El comportamiento esperado es que el total se calcule utilizando el valor real del catálogo.

La validación se realiza en dos workspaces temporales.

En el workspace baseline se agrega únicamente el nuevo test, sin aplicar la corrección. El test debe fallar y demostrar que el problema existe.

En el workspace candidate se aplican la corrección y el test. Luego se ejecutan el test específico, la suite completa, el linter y los controles de seguridad configurados.

Para considerar validada la corrección, no alcanza con que el test nuevo pase. También debe pasar la suite completa, para reducir el riesgo de introducir una regresión.

La ejecución del código se hace en un contenedor aislado, sin acceso a la red, sin secretos, con límites de tiempo, memoria y CPU. Además, los comandos ejecutados provienen de una lista previamente configurada. El modelo nunca puede inventar un comando y ejecutarlo directamente.

Una decisión central del diseño fue separar las responsabilidades.

El modelo de lenguaje analiza el código y propone una hipótesis de solución. Pytest y las demás herramientas generan evidencia objetiva. Finalmente, un motor de políticas determinístico decide si el cambio puede avanzar.

El quality gate evalúa la transición de pull request a QA y puede devolver cuatro estados.

**READY** significa que existe evidencia suficiente y no hay bloqueos.

**CONDITIONAL** significa que el cambio podría avanzar, pero existe una advertencia o condición concreta.

**BLOCKED** significa que se incumple una regla obligatoria, por ejemplo porque existen tests fallidos, un hallazgo crítico o un criterio de aceptación incumplido.

**INCONCLUSIVE** significa que no fue posible obtener suficiente evidencia. Por ejemplo, si no pudieron ejecutarse los tests o si el modelo no devolvió una respuesta válida.

Este último estado es especialmente importante porque evita confundir ausencia de evidencia con aprobación. Si un control obligatorio no pudo ejecutarse, el sistema nunca devuelve READY.

Las políticas están definidas fuera del prompt y se encuentran versionadas. Esto permite saber exactamente qué reglas se utilizaron y modificarlas sin cambiar el comportamiento del modelo.

El resultado completo queda almacenado en SQLite. Se registra el pull request, el SHA, el modelo utilizado, la versión del prompt, la política aplicada, los hallazgos, el parche, los resultados de las pruebas, la duración, el consumo de tokens y la decisión final.

El frontend está desarrollado con React 19 y TypeScript. Desde la interfaz se puede iniciar el análisis, observar su progreso y consultar un informe que muestra el hallazgo, la corrección propuesta, el test de regresión, la comparación antes y después, los criterios de aceptación y las razones específicas de la decisión.

El sistema funciona en modo de solo lectura sobre GitHub. No realiza merge, no hace push, no publica comentarios y no despliega automáticamente a QA. Su función es asistir a la decisión y producir evidencia. La autoridad final continúa estando en una persona.

En términos de las condiciones del reto, busqué equilibrar cuatro aspectos.

Para controlar el costo, reduzco el contexto y limito la cantidad de llamadas al modelo.

Para mejorar el tiempo de respuesta, utilizo un workflow acotado y ejecuto solamente las herramientas necesarias.

Para proteger la privacidad, excluyo secretos, envío contexto mínimo y no guardo credenciales.

Y para facilitar la operación, el proyecto puede ejecutarse mediante Docker Compose y cuenta con documentación paso a paso.

La principal conclusión del proyecto es que un agente de IA no debería aprobar código solamente porque puede producir una explicación convincente.

El enfoque que propongo es que la inteligencia artificial formule una hipótesis, las herramientas tradicionales produzcan evidencia y una política explícita determine si el cambio está listo para avanzar.

De esta manera, el sistema no reemplaza al desarrollador o al revisor técnico. Les permite trabajar con mayor velocidad, consistencia y trazabilidad.
