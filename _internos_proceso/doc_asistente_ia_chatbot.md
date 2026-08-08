# El asistente de IA (chatbot) de nutrición: documentación completa

Fecha del análisis: 2026-08-02. Solo lectura, no se ha modificado nada.

Ficheros cubiertos (leídos enteros):
- `frontend/src/pages/ChatbotPage.jsx` (1102 líneas)
- `frontend/src/components/nutrition/ChatDayOverview.jsx`
- `frontend/src/components/nutrition/ChatMealSummary.jsx`
- `frontend/src/components/nutrition/ChatSuggestions.jsx`
- `backend/chatbot.py` (3504 líneas, el fichero principal)
- `backend/routes/chatbot.py` (408 líneas)
- `backend/llm_client.py` (78 líneas)

Ficheros de apoyo consultados para entender referencias del código anterior:
- `backend/calculator.py` (categorías CALMA, límites de cantidad)
- `backend/macro_distribution.py` (distribución de macros por comida)
- `backend/core/database.py` (índices de Mongo, TTL)

---

## 0. Arquitectura general

El chatbot es, a propósito, un **motor determinista con un LLM de apoyo muy acotado**. La IA (OpenAI, modelo `gpt-4.1-mini` por defecto) NO decide macros, cantidades ni qué alimento es cuál: solo hace dos trabajos muy concretos:

1. **Extraer alimentos** de una frase en lenguaje natural (`extract_foods`, usado poco directamente; lo normal es el router).
2. **Clasificar la intención** del mensaje del usuario y extraer sus datos (`understand`, el "router de intenciones").

Toda la matemática (macros, cantidades, topes, calibración progresiva, desambiguación, búsqueda) la hace código Python puro en `backend/chatbot.py`. Esto está comentado explícitamente en el código: *"El LLM SOLO extrae alimentos"* (línea 1040) y *"Router con LLM: clasifica la INTENCIÓN del mensaje... El LLM solo interpreta el lenguaje; el código hace toda la matemática"* (línea 2932).

La clase central es `NutritionChatbot` (`backend/chatbot.py:79`). Cada sesión de chat es una instancia de esta clase, con todo su estado en el diccionario `self.state` (JSON puro), que se persiste en Mongo (colección `chatbot_sessions`) tras cada interacción y se rehidrata al principio de cada petición (ver punto 10).

Las rutas HTTP (`backend/routes/chatbot.py`) son finas: cada endpoint crea/recupera el chatbot de la sesión, llama a un método de `NutritionChatbot`, guarda el estado y devuelve JSON. El frontend (`ChatbotPage.jsx`) es quien decide cómo pintar cada tipo de respuesta.

---

## 1. El flujo completo de una conversación

### 1.1 Arranque: `POST /api/chatbot/start` (`backend/routes/chatbot.py:33-87`)

El usuario pulsa "Empezar" en la pantalla inicial (`ChatbotPage.jsx:892-899`). Esto llama a `startChat()` (línea 168), que hace `POST /api/chatbot/start`.

El backend:
1. Crea un `session_id` con el formato `chat_<user_id>_<YYYYMMDDHHMMSS>` (línea 37). Este formato es importante: es la base de la seguridad (ver punto 10).
2. Carga el perfil del cliente (`db.client_profiles`) y de ahí saca sus macros por defecto: `macros_training`, `macros_rest`, `macros_periworkout`. Si no hay perfil, usa unos valores por defecto fijos (160P/50H/40G entreno, etc., líneas 61-70).
3. Crea la instancia `NutritionChatbot` con `get_or_create_chatbot`.
4. Carga las preferencias de comida y alimentos evitados del perfil (`chatbot.set_preferences`, línea 76-80), que se usarán después para filtrar sugerencias.
5. Guarda la sesión en Mongo.
6. Devuelve `session_id` y un mensaje de bienvenida (el mensaje real que se muestra lo pone el frontend, ver abajo).

En el frontend, `startChat()` fija `step = 'config'`, `configStage = 'date'` y muestra: *"¡Hola! Soy tu asistente de nutrición. ¿Para qué día quieres montar la dieta?"* (línea 184). Nótese que el mensaje de bienvenida que devuelve el backend (línea 86, *"¿Hoy es día de entrenamiento o descanso?"*) NO se usa; el frontend pone su propio texto y arranca con la pregunta de la fecha, no la del tipo de día.

### 1.2 La configuración conversacional (subfases de `step === 'config'`)

Toda esta fase vive en el frontend, en `submitConfig()` (`ChatbotPage.jsx:193-289`), y NO llama al backend hasta el final (excepto el paso `date` que es puramente local). Es un flujo híbrido: cada pregunta tiene botones (pulsables) Y admite texto libre tecleado, ambos pasan por la misma función `submitConfig`.

**Subfase `date`** (línea 197-208):
- Pregunta: *"¿Para qué día quieres montar la dieta?"*
- Botones: "Hoy" (valor `hoy`), "Mañana" (valor `manana`).
- Texto libre admitido: fecha ISO `YYYY-MM-DD`, o formato `D/M` o `D/M/YYYY` (función `parseTargetDate`, línea 141-159). Si no reconoce el formato, repregunta: *"No entendí la fecha. Dime 'Hoy', 'Mañana' o una fecha como 2026-07-01."*
- Al resolver la fecha, pasa a la subfase `tipo` con: *"¿Es día de entrenamiento o de descanso?"*

**Subfase `tipo`** (línea 211-224):
- Botones: "Día de Entrenamiento" (`entrenamiento`), "Día de Descanso" (`descanso`).
- Texto libre: reconoce por substring "entren" o "descan" (insensible a acentos, vía `stripAccents`). Si no cuadra ninguno, repregunta.
- Pasa a `comidas` con: *"¿Cuántas comidas vas a hacer, 3 o 4?"*

**Subfase `comidas`** (línea 226-245):
- Botones: "3 comidas" (`3`), "4 comidas" (`4`), "Bloque único" (`bloque unico`).
- Texto libre: reconoce "bloque"/"unic"/"una comida"/el literal `1` como bloque único (`n=1`, `isSingle=true`); si el texto contiene "3" es 3 comidas, si contiene "4" es 4 comidas.
- **Bifurcación importante**: si `tipoDia === 'entrenamiento'`, pasa a la subfase `peri` (pregunta por el manejo del peri-entreno). Si es día de descanso, se salta esa pregunta y llama directamente a `configureDay(tipoDia, n, 'sin_peri', 1, isSingle)` porque en descanso no hay entreno y por tanto no hay peri-entreno que gestionar.

**Subfase `peri`** (solo en día de entrenamiento) (línea 247-271):
- Pregunta: *"¿Cómo gestionas el peri-entreno (Intra/Post)?"*
- Botones: "Intra + Post" (`intra_post`), "Solo Post" (`solo_post`), "Solo Intra" (`solo_intra`), "Sin peri" (`sin_peri`).
- Texto libre: combinaciones de "intra"/"post"/"sin"/"nada"/"ningun" resuelven a la opción correspondiente (con reglas de prioridad: si contiene ambas palabras "intra" y "post" es `intra_post`; "solo"+"post" es `solo_post`; etc.)
- **Bifurcación**: si es bloque único (`singleMeal`), las comidas peri van DESPUÉS de la comida única, así que no hace falta preguntar el momento del entreno: llama directamente a `configureDay`. Si no es bloque único, pasa a la subfase `momento`.

**Subfase `momento`** (solo si NO es bloque único y hay peri) (línea 273-289):
- Pregunta: *"¿Cuándo entrenas?"*
- Botones dinámicos: "En ayunas" (`ayunas`) + "Después de comida N" por cada comida menos la última (`Array.from({ length: Math.max(1, numComidas - 1) }...)`, línea 965-967). Con 3 comidas hay botones para C1 y C2; con 4, para C1, C2 y C3.
- Texto libre: si contiene "ayun" → momento 0; si contiene "3"/"2"/"1" → ese número (en ese orden de prioridad, así que "comida 13" cogería el 3 antes que el 1, aunque es un caso raro).
- Al resolver, llama a `configureDay(tipoDia, numComidas, opcionPeri, m, singleMeal)`.

### 1.3 `POST /api/chatbot/configure` (`backend/routes/chatbot.py:89-135`)

Este es el único paso de la configuración que sí toca el backend. Llama a `chatbot.configure_day(...)` (`backend/chatbot.py:139-180`), que:

1. Guarda `tipo_dia`, `num_comidas` (fuerza a 1 si `single_meal`), `momento_entreno`, `opcion_peri`, `single_meal` en el estado.
2. Cambia `state["step"]` a `"building_meal"` y `comida_actual` a 1.
3. Llama a `distribuir_macros(...)` (`backend/macro_distribution.py:300`) con los macros del usuario (de perfil o por defecto) y toda la configuración del día. Esta función devuelve un diccionario con:
   - `comidas`: `{"C1": {P,H,G}, "C2": {...}, ...}` — el objetivo de cada comida principal.
   - `periworkout`: `{"Intra": {P,H,G}, "Post": {P,H,G}}` si aplica.
   - `resumen`: totales del día (`P_total`, `H_total`, `G_total`).
4. Construye `meal_order` con `_build_meal_order()` (`backend/chatbot.py:182-210`): la lista ordenada de claves de comida a montar, con las peri intercaladas en la posición del `momento_entreno`. Por ejemplo, con 4 comidas, `intra_post` y `momento_entreno=2`, el orden es `["C1", "C2", "Intra", "Post", "C3", "C4"]`. En bloque único, las peri siempre van al final (`idx = len(base)`).

La ruta construye el mensaje de bienvenida a la comida ("Perfecto, día de entrenamiento con 4 comidas (más 2 peri-entreno). Vamos con Comida 1. Tu objetivo es: ..."), y devuelve `distribucion`, `comida_actual`, `meal_nombre`, `objetivo`, `day_overview` y el `mensaje`.

El frontend recibe esto en `configureDay()` (`ChatbotPage.jsx:306-339`), fija `step = 'building_meal'` y a partir de ahí entra en el bucle normal de chat.

### 1.4 El bucle de montar comidas (`step === 'building_meal'`)

Cada mensaje del usuario que teclea en el input (o pulsando una sugerencia) va a `POST /api/chatbot/message` (`backend/routes/chatbot.py:137-162`), que llama a `chatbot.process_message(user_input)` — el corazón del sistema, descrito en el punto 3.

Además hay tres botones fijos bajo el input (línea 1038-1066 de `ChatbotPage.jsx`):
- **"Guardar y siguiente"** → `completeMeal()` → `POST /api/chatbot/complete-meal`.
- **"Sugerir alimentos"** → `requestSuggestions()` → `POST /api/chatbot/suggest-foods`.
- **"Resumen del día"** → pinta localmente `formatDayOverview(dayOverview)` sin llamar al backend (usa los datos que ya tiene en memoria).

### 1.5 Completar una comida: `POST /api/chatbot/complete-meal` (`backend/routes/chatbot.py:222-280`)

Llama a `chatbot.complete_current_meal()` (`backend/chatbot.py:908-942`):
- Si la comida está vacía, devuelve error: *"No puedes guardar una comida vacía. Dime qué quieres comer primero."*
- Si no, la marca como guardada (`saved_meals`) y avanza a la siguiente comida PENDIENTE (no necesariamente la siguiente en orden: si el usuario había vuelto atrás a editar una ya guardada, al completarla de nuevo salta a la próxima que aún no esté guardada, nunca repite una ya hecha).
- Si ya no quedan comidas pendientes, `step` pasa a `"complete"`.

La ruta añade un aviso si la comida se guarda sin cuadrar (margen de 4g): *"⚠️ Ojo: Comida 2 quedó sin cuadrar (faltan 12 g de proteína)."* o *"⚠️ En Comida 2 te pasas 8 g de grasa."*

Cuando el día se completa, el frontend guarda `daySummary` y muestra el resumen final con botones "Volcar a mi dieta" y "Exportar PDF" (`renderDaySummary`, línea 769-833).

Cada vez que se completa una comida (`completeMeal` en el frontend, línea 511-551), se llama también a `syncToDiet()` (línea 555-592), que vuelca automáticamente el progreso en la pestaña de Nutrición (`db.diets`) del día destino. La primera vez que hay algo que sobrescribir, pregunta al usuario con un diálogo de confirmación; a partir de ahí recuerda la decisión (`autoSyncRef`) durante toda la sesión de navegador (persistido en `sessionStorage`).

### 1.6 Volcar y exportar

- **`saveToDiet()`** (frontend, línea 712-767) → `POST /api/chatbot/save-to-diet` (`backend/routes/chatbot.py:303-360`): exporta `comidas_completadas` al formato de `db.diets` (vía `export_to_diet_comidas`) y los objetivos por comida (`export_distribution_targets`), y hace upsert en la colección de dietas. Si ese día ya tenía alimentos y no se ha forzado, devuelve `needs_confirmation` para que el frontend pida confirmación antes de sobrescribir.
- **`exportToPDF()`** → `GET /api/chatbot/export-pdf` (`backend/routes/chatbot.py:381-407`): genera un PDF con `pdf_generator.generate_diet_pdf` a partir de `chatbot.get_day_summary()`.

---

## 2. Cómo monta una comida: qué puede pedir el usuario

El usuario simplemente escribe lo que quiere comer en lenguaje natural. Ejemplos que el sistema entiende (todos pasan primero por el router de intenciones, ver punto 3, que los clasifica como `add`):

- **Alimentos sin cantidad**: "pollo y arroz", "quiero tortilla de claras y pan" → se autodimensionan contra lo que falta de la comida.
- **Alimentos con cantidad en gramos**: "150g de pavo", "pon 80 g de arroz" → se respeta la cantidad tal cual (sin tope ni recorte), igual que en la calculadora manual.
- **Alimentos con cantidad en unidades**: "4 huevos", "2 huevos" → se convierten a gramos multiplicando por la ración del alimento.
- **Medidas caseras**, convertidas por el extractor del LLM a gramos (línea 1067-1069 de `chatbot.py`, dentro del prompt de `extract_foods`, aunque en la práctica el que se usa es el router `understand`, que sigue las mismas reglas del prompt): "un cazo/scoop de proteína" → 30 g; "una cucharada de aceite/crema" → 10 g; "un puñado de frutos secos" → 30 g; "un chorrito de aceite" → 5 g; "un vaso de leche" → 250 g; "medio/media X" → 0.5 unidades.
- **Cambios de cantidad sobre lo ya puesto**: "baja las almendras a 26 g", "sube el pollo a 200", "cambia el arroz a 100g" → intención `add` con la cantidad FINAL (nunca `remove`/`clear`); el router tiene instrucciones explícitas de tratarlas así (línea 2961-2964).
- **Incrementos** ("pon un huevo más", "agrega otro huevo", "ponme más claras") frente a **fijar el total** ("deja los huevos en 2", "pon el arroz a 80g", "2 huevos"): esta distinción NO la hace el LLM (es "inestable" según el comentario de la línea 1991-1993), sino un conjunto de expresiones regulares deterministas en código: `_RE_SET_TOTAL`, `_RE_INCREMENTO`, `_RE_INCREMENTO_FUERTE` (líneas 2001-2006). En gramos solo se considera incremento con marca fuerte ("añade 20 g más"); en unidades basta "un/una/otro/más".
- **Negaciones excluidas**: "sin pan", "no quiero pescado", "nada de arroz" — esos alimentos NUNCA se añaden. Además, el propio mensaje del usuario se escanea con una expresión regular (línea 3105-3110) para memorizar palabras evitadas ("sin X" → X pasa a `avoided_keywords` para el resto de la sesión, con una lista de excepciones tipo "nada", "nunca", "duda"...).
- **Decrementos**: "quita 100 gramos de la avena", "2 huevos menos", "quita un huevo" → reducen la cantidad existente o eliminan el alimento si queda casi a cero (ver `_intento_decremento`, línea 2029).
- **Multiplicadores**: "la mitad de zumo", "el doble del arroz", "que el zumo sea la mitad" → `_intento_multiplicador` (línea 2139), que aplica el factor sobre la cantidad ya puesta de ese alimento.
- **Reemplazos**: "cambia el pollo por pavo", "en vez de pollo ponme atún" → `_intento_reemplazo` (línea 2103): quita el viejo y añade el nuevo, con las conversiones de cantidad si las hay.
- **Ajustes sobre "lo último puesto" sin nombrarlo**: "ponlo en 2", "que sean 150 g", "añade 20 g más" → `_intento_ajuste_ultimo` (línea 2183), que actúa sobre el último alimento de la lista.
- **Mensajes mixtos** (mismo alimento en la misma frase): "agrega un huevo y quita uno" → `_intento_mixto` (línea 2206) calcula el neto (aquí, 0: se queda igual) para no hacer dos operaciones contradictorias.
- **Peticiones de macro genérico**: "una grasa", "algo de proteína" → NO es un alimento concreto; el sistema elige uno real que quepa (ver `_pick_food_for_macro`, punto 8).
- **Alimentos fritos/rebozados/empanados**: se avisa de que el catálogo cuenta el alimento base, y que si se ha hecho frito hay que apuntar el aceite aparte (línea 2403-2419).

Cuando hay varios alimentos en una misma frase y ninguno trae cantidad explícita, el reparto entre ellos NO es "todo lo que quepa de cada uno": se usa `meal_builder.build_meal` (importado en la línea 2376 y 2538) para repartir de forma equilibrada entre lo que falta.

---

## 3. El router de intenciones

### 3.1 Cómo funciona `understand()` (`backend/chatbot.py:2931-3081`)

Antes de llamar al router LLM, `process_message()` (línea 3083) intenta resolver el mensaje de forma **completamente determinista**, en este orden de prioridad:

1. **¿Es una elección de una lista de opciones pendiente?** (`_match_option_pick`, ver punto 4). Si el bot acaba de ofrecer sugerencias o una desambiguación y el usuario responde "la 1", "el segundo", "salmón"... se resuelve aquí sin llamar al LLM.
2. Se registran palabras "evitadas" mencionadas de pasada ("sin X").
3. Se llama al router LLM (`understand`).
4. Si `step == "complete"` (día ya cerrado) y la intención no es de solo lectura, se bloquea la mutación salvo que se indique una comida concreta a reabrir ("edita la comida 2").
5. Una batería de detectores deterministas por regex tiene **prioridad sobre el intent del LLM** para los casos que el router clasifica mal: `_intento_quitar_todo`, `_intento_mixto`, `_intento_decremento`, `_intento_reemplazo`, `_intento_multiplicador`, `_intento_ajuste_ultimo` (líneas 3140-3232). El comentario del código lo explica: *"Operaciones deterministas que el router interpreta mal... tienen PRIORIDAD sobre el intent del LLM (que p.ej. malclasifica 'agrega X y quita Y' como pregunta)"*.
6. Solo si nada de lo anterior aplica, se despacha según el `intent` que devolvió el LLM.

### 3.2 El prompt del router (línea 2935-3015)

El router recibe el texto del usuario y debe devolver JSON puro:
```json
{"intent": "add|suggest|complete|remove|clear|status|summary|rebalance|goto|list|question|none",
 "foods": [{"nombre": "...", "cantidad": <número o null>, "unidad": "g"|"ud"|null, "busqueda": "..."}],
 "remove": "<alimento a quitar o null>",
 "goto": <número, "post", "intra", "ultima", "actual" o null>,
 "macro": "P"|"H"|"G"|null,
 "marca": "<marca pedida o null>",
 "termino": "<tipo de alimento del que pide MÁS opciones, o null>"}
```

### 3.3 Las 12 intenciones y qué hace cada una

| Intención | Qué significa | Ejemplos literales del prompt/código | Qué ejecuta el backend |
|---|---|---|---|
| **add** | Dice qué alimentos quiere comer/añadir, O cambia una cantidad ya puesta | "quiero tortilla de claras y pan", "pon 80 g de arroz", "cambia el arroz a 100g", "baja las almendras a 26 g" | `add_foods(foods)` (punto 2) |
| **suggest** | Pide que el asistente elija/recomiende, sin nombrar un alimento concreto | "qué me sugieres", "dame opciones", "qué pongo", "sugiéreme grasas", "recomiéndame algo de FullGas", "hay otras opciones de tostadas?" | `suggest_foods_for_current_meal()` o `_mas_opciones_termino()` (punto 8) |
| **complete** | Guardar/cerrar la comida actual y pasar a la siguiente | "siguiente", "guardar y siguiente", "ya está, la dejo así" | Responde `{"action": "complete_request"}`; el frontend llama a `completeMeal()` |
| **remove** | Quitar del todo un alimento ya añadido, SIN cantidad final | "borra las aceitunas", "quita el arroz de la comida 2" | `remove_food_by_name()` |
| **clear** | Vaciar TODA una comida | "vacía la comida 1", "borra el post-entreno", "empieza de cero" | `clear_meal(goto_idx)` |
| **status** | Pide los números de cómo va (solo cifras) | "qué me falta", "cuántos macros quedan", "cómo voy" | Devuelve `meals_status` con el texto de restante del día y de la comida actual |
| **summary** | Resumen del día completo | — | `{"action": "summary", "day_overview": ...}` |
| **rebalance** | Recalcular/cuadrar las cantidades de lo que YA hay, sin cambiar los alimentos | "cuadra las cantidades", "reparte mejor" | `rebalance_current_meal()` (punto siguiente) |
| **goto** | Ir a una comida concreta para verla/editarla | "vamos a la comida 2", "edita la comida 3", "abre el post-entreno", "edita la última" | `go_to_meal(goto_idx)` |
| **list** | Ver/listar el contenido de las comidas | "qué comidas tengo", "lístame la comida 1", "qué llevo en la comida 2" | `list_meals_text()`, con `vista: "dia"` para que el frontend pinte `ChatDayOverview` |
| **question** | Dudas de nutrición o cualquier pregunta que espera una respuesta en texto | "¿por qué el arroz cuenta como hidrato?", "¿cuántas calorías llevo?", "lo mismo que ayer" (no hay historial → question) | `answer_question()` (punto 9) |
| **none** | Saludo o mensaje ininteligible | "hola", "gracias" | Cae en el flujo de "no reconocí ningún alimento" al final de `process_message` |

Reglas especiales del prompt que vale la pena citar:
- *"'terminar/completar/ajustar la comida' cuando PIDEN ayuda o sugerencias es 'suggest', NO 'complete'."*
- *"Listar o VER el contenido de las comidas es 'list', NO 'status' (status es SOLO cuánto falta)."*
- Si el mensaje mezcla quitar y añadir ("quítame el arroz y pon más pollo"): intent=`add`, con `remove` Y `foods` rellenos a la vez.
- Si añade y quita el MISMO alimento en la misma frase, se interpreta la intención final (no se añade).
- Correcciones ("te pedí un plátano GRANDE, no pequeño"): `add` con el correcto en `foods` y el equivocado en `remove`.
- Una marca NUNCA es un macro: "recomiéndame algo de FullGas" es `suggest` con `marca="FullGas"` y `macro=null` (el prompt insiste: *"'fullgas' NO es grasa"*).
- Distinción sutil de quién elige: *"si el que va a decir el alimento es ÉL ('quiero añadir un alimento')... NO es 'suggest': es 'add' con 'foods' vacío, para preguntarle cuál"*. Esto se refuerza en código con la regex `_RE_ADD_SIN_DECIR_QUE` (línea 1995-1999), que detecta frases tipo "quiero/voy a + añadir/meter/sugerir + algo/alimento/producto" y responde: *"Dime cuál quieres añadir... Si prefieres que elija yo, dime 'sugiéreme algo'."*

### 3.4 Reintentos y fallo del LLM

`understand()` reintenta hasta 2 veces si el LLM lanza una excepción (línea 3018-3030). Si tras los reintentos sigue fallando, devuelve `intent: "llm_fallo"`, y `process_message` responde explícitamente: *"Ahora mismo no he podido interpretar tu mensaje (fallo puntual del asistente). Escríbelo otra vez en unos segundos, o usa los botones de abajo."* — deliberadamente NO se trata como un "add vacío" para no confundir al usuario con un "comida actualizada" sin nada dentro.

### 3.5 Fallback final si nada encaja

Si el intent es `add`/`none` y el mensaje es corto (≤4 palabras) sin verbo reconocible, `process_message` intenta tratarlo directamente como el nombre de un alimento suelto (líneas 3373-3395): quita palabras de relleno ("otro", "más", "pon", "dame"...) y busca lo que queda; si hay match completo (todas las palabras significativas cubiertas y no es un "match parcial"), lo añade directamente. Si el mensaje tiene 4+ palabras y no se reconoce nada, se trata como una pregunta (`answer_question`). Si es cortísimo y no se reconoce nada, el mensaje final es:

> "No reconocí ningún alimento ahí. Dime qué quieres comer (p.ej. 'huevos, pan, claras'), o pregúntame '¿qué me falta?'. También puedes manejar las comidas por texto: 'edita la comida 2', 'lista la comida 1', 'vacía el post-entreno'. O pulsa 'Sugerir alimentos' o 'Guardar y siguiente'."

---

## 4. La desambiguación: "¿cuál de estos?"

### 4.1 Cuándo se dispara (`_opciones_ambiguas`, `backend/chatbot.py:1598-1754`)

Cuando el usuario pide un término GENÉRICO de una sola palabra significativa (p.ej. "lomo", "pavo") que en la base corresponde a alimentos de TIPOS realmente distintos (fiambre vs. pechuga fresca, embutido vs. salmón), el sistema NO adivina: ofrece una lista para elegir.

Condiciones para que se dispare (todas deben cumplirse):
1. El término tiene exactamente **1 palabra significativa** (sin preposiciones/artículos). Si el usuario ya concretó ("lomo embuchado", "lomo de salmón"), no se pregunta.
2. El término NO está en `_CANONICAL_TERMS`: la lista de términos con elección por defecto ya decidida en `query_mappings` (arroz→arroz blanco, atún, pollo→pechuga de pollo, tomate, etc.). El comentario del código explica por qué "pavo" se dejó FUERA de esa lista a propósito (petición del 2026-07-17): *"en la base hay tipos muy distintos (fiambre 2.1, pechuga fresca 2.2, jamón de pavo...) y el asistente debe OFRECER opciones, no plantar siempre el fiambre"* (línea 333-335).
3. Hay 2+ candidatos que contienen literalmente el término (o su raíz en otro género/número).
4. Ninguno de los candidatos es un "match parcial" (si la búsqueda ya fue floja, no se fuerza una elección).
5. NO existe un alimento que se llame EXACTAMENTE como lo pedido: si el usuario pide "bacon" y hay un alimento llamado literalmente "Bacon", esa es la respuesta directa, sin preguntar (esto corrigió un bug real: "bacon" sacaba solo productos "sabor bacon" con el "Bacon" real escondido porque no cabía en la comida por su mínimo de categoría).
6. Los candidatos pertenecen a **2 o más subfamilias distintas** (categoría a 2 niveles, p.ej. `2.1` fiambre vs `2.2` carne fresca). Si todos son de la misma subfamilia (p.ej. toda fruta fresca `11.1`), se autoelige sin preguntar.

### 4.2 Cómo ordena las opciones

El orden de las opciones sigue exactamente la misma lógica que el buscador de la calculadora manual (decisión explícita del 2026-07-17, comentario en línea 1655-1658: *"mismo motor (calma_suggest)... y misma ordenación por diferenciaDeMacros ascendente"*), y se aplica en tres niveles de prioridad (línea 1690-1706):

1. **`exacto`** (0 = mejor, 1 = peor): si el nombre del alimento contiene la palabra EXACTA pedida (en singular o plural, pero no en otro género), va primero. Ejemplo: pedir "tostadas" prioriza "Tostada sin gluten" sobre "Edamame tostado" (donde "tostado" es solo un adjetivo).
2. **`es_marca`** (2026-08-02, decisión reciente): 0 = genérico (sin URL en `db.foods`), 1 = de marca (con URL). Los genéricos van SIEMPRE antes que los de marca, dentro de su mismo bloque de relevancia. El comentario documenta el criterio: *"En la base, genérico = NO tiene URL... quien pide 'tostadas' quiere la tostada de toda la vida antes que la de una marca concreta"* (línea 1701-1703). Esto coincide con lo que ya sabía por memoria del usuario ("marca vs genérico en db.foods").
3. **`dif`** (diferencia de macros, `calma_suggest.diferencia_de_macros`): entre igualdad de los dos criterios anteriores, gana el que mejor cuadra con lo que falta de la comida.

Además, para no repetir 6 marcas del mismo alimento, agrupa las opciones por "tipo real" (las 2 primeras palabras significativas del nombre sin marca) y se queda solo con la mejor de cada grupo (`clave_tipo`, línea 1711-1721). Y garantiza que siempre aparezca al menos un genérico en la lista aunque el bloque de mayor relevancia esté lleno de marcas (línea 1734-1753): con "tostad" hay 48 opciones de marca y 3 genéricas; sin este hueco, "Pan tostado" nunca aparecería.

Máximo de opciones por defecto: 6 (`max_op=6`).

### 4.3 Con cantidad fijada por el usuario

Si el usuario dijo "150g de pavo", las opciones se calculan a ESA cantidad exacta (sin dimensionado automático), llevan `cantidad_fija: true` y `cantidad_g`, y al elegir una se respeta tal cual (`add_food_by_id`, punto siguiente).

### 4.4 Elegir una opción

Cuando hay una lista de opciones pendiente (`state["last_options"]`), el sistema intercepta el mensaje ANTES del router LLM con `_match_option_pick()` (línea 1818-1875), determinista:
- Número: "la 1", "2" → opción por posición.
- Ordinal: "el segundo", "primera" (diccionario `_ORDINALES`).
- "Último"/"última".
- Por nombre: si todas las palabras del mensaje están contenidas en el nombre de UNA sola opción ("salmón" → "Lomo de salmón").
- Se filtran palabras de relleno (`_PICK_FILLER`: "el", "quiero", "dame", "porfa", "vale"...) y se excluyen mensajes que en realidad piden otra acción (`_NO_PICK`: "comida", "edita", "guarda", "post", "intra"...), para que "vacía la 1" no se confunda con elegir la opción 1.
- Si el número está fuera de rango ("la 9" con 6 opciones), devuelve `("range", n)` y el bot avisa manteniendo la lista viva para reelegir.

"Más opciones del mismo tipo" (`_mas_opciones_termino`, línea 1756-1794): si el usuario pide "otras" sin decir de qué, se hereda el `last_termino` de la lista SOLO si sigue en pantalla sin elegir (si ya se completó una elección o pasaron comidas, no se hereda). Si no quedan más opciones nuevas de ese tipo, el bot lo dice honestamente y ofrece salidas: *"No me quedan más opciones de X que cuadren con lo que te falta. ¿Quieres que te sugiera otra cosa parecida, o prefieres decirme tú qué te apetece?"*

---

## 5. Interpretación al vocabulario del catálogo

### 5.1 El mapeo `query_mappings` (`search_foods`, línea 322-424)

Un diccionario fijo, hardcodeado en Python, que traduce términos coloquiales a cómo se llaman los alimentos en `db.foods`. Ejemplos: "huevos"→"huevos enteros L", "pollo"→"pechuga de pollo", "avena"→"copos de avena", "pan"→"pan de barra", "patata"→"patata cocida", "queso batido"→"queso fresco batido 0%", "tortitas"→"tortita de arroz", "cacahuete"→"crema de cacahuete". También cubre typos y regionalismos frecuentes: "wevos"/"webos"/"uevos"/"guevos"→huevos, "keso"→queso, "abena"→avena, "palta"→aguacate, "frutilla"→fresas, "durazno"→melocotón.

Este mapeo SOLO se aplica cuando la consulta tiene **una única palabra significativa** (línea 435-442): si hubiera varias, "leche de avena" acabaría secuestrado por el mapeo de "leche"→leche de vaca. Con varias palabras, se busca la frase tal cual.

Los términos de este diccionario se guardan en `NutritionChatbot._CANONICAL_TERMS` (línea 427) y sirven también para decidir cuándo NO desambiguar (punto 4.1).

### 5.2 El mapeo dinámico del router LLM: campo `busqueda`

Aparte del diccionario fijo, el router (`understand`) devuelve para cada alimento un campo `busqueda`: *"cómo se llamaría eso en una tabla de alimentos"* (línea 2939-2957). Ejemplos del propio prompt: "tostadas"→"pan tostado", "cereales"→"copos de maíz", "fiambre"→"jamón de york", "pasta"→"macarrones", "refresco"→"bebida de cola", "embutido"→"chorizo". Esto cubre casos que el diccionario fijo no anticipa.

Dos reglas explícitas que el prompt impone al LLM:
- Si lo que dijo el usuario YA es como se llamaría en la tabla ("pechuga de pollo", "arroz blanco", "huevos"), `busqueda` va a `null`: no hay nada que traducir.
- **NO se traducen a propósito los términos ambiguos**: "pavo", "lomo", "filete", "queso", "yogur" se dejan tal cual con `busqueda: null`, porque son justo los términos que el sistema quiere PREGUNTAR al usuario (punto 4); traducirlos de antemano le quitaría la elección.

### 5.3 Cómo se aplica esa traducción (`buscar_con_interpretacion`, línea 265-296)

El orden es deliberado y está documentado en el propio código: *"Lo que el usuario escribe manda"*.
1. Se busca primero lo que el usuario dijo literalmente.
2. Solo si esa búsqueda no da nada, o da un "match parcial" (coincidencia floja), se prueba la traducción (`interpretacion`/`busqueda`).
3. Si la traducción encuentra algo limpio, se usa, pero se marca con `_interpretado` para que el sistema avise al usuario en el mensaje final: *""tostadas" lo tengo como "Pan tostado"."* (línea 2347) — nunca se hace el cambio en silencio.

Esta doble vía evita que una traducción del LLM se adelante a un match directo que ya existe: si el usuario pide "arroz" y ya hay "Arroz blanco" en el catálogo, la traducción nunca llega a intervenir.

---

## 6. Búsqueda por raíz y tolerancia fonética

### 6.1 Búsqueda por raíz: género y número (`_raiz`, `_regex_raiz`, línea 1329-1357)

`_raiz(palabra)` calcula la raíz de una palabra en español quitando plural y la vocal final, de forma deliberadamente conservadora: quita "es" si la palabra queda con más de 4 letras, o "s" si queda con más de 3; luego, si termina en "a" u "o" y queda con más de 4 letras, quita esa vocal también. Si la raíz resultante queda con menos de 4 letras, devuelve cadena vacía (para no emparejar de más: "pavo"→"pav" no es válido).

Así, "tostadas", "tostada", "tostado" y "tostados" caen todos en la raíz "tostad". `_regex_raiz` construye el patrón `\btostad(s|a|o|as|os|es)?\b` para casar cualquier género/número.

Esto se usa en dos sitios:
- En `search_foods`, como "Paso 2b" (línea 502-515): SOLO para consultas de una única palabra significativa, se amplía la búsqueda con este patrón, sumando 35 puntos de relevancia (por debajo de cualquier coincidencia literal, para que "tostadas" nunca adelante a algo que empiece literalmente por "tostada").
- En `_opciones_ambiguas` (línea 1622-1625), para que "tostadas" arrastre también "Pan tostado" a la lista de candidatos a desambiguar.

### 6.2 Tolerancia fonética: seseo y escritura rápida (`_clave_fonetica`, línea 1359-1381)

Convierte un texto a "cómo suena" para comparar nombres escritos deprisa o con seseo. El comentario lo explica con el ejemplo real: *"La mitad de España sesea y en el móvil se escribe rápido: 'sumo' por 'zumo', 'cosido' por 'cocido', 'berengena' por 'berenjena'. Comparando por escrito, un cliente que pedía 'la mitad de sumo' recibía 'sumo: no encontrado' aunque tenía el zumo delante en la lista"* (línea 1362-1366).

Transformaciones aplicadas, en orden:
1. Quita acentos.
2. `qu`→`k`, `gue`→`ge`, `gui`→`gi`.
3. `c` seguida de `e`/`i` → `s` (seseo de "cena", "cine").
4. `z`→`s` (seseo de "zumo"→"sumo"), `ll`→`y` (yeísmo), `v`→`b`, `h` se elimina.
5. `y`→`i`, `c`→`k` (para que "aceite"/"aceyte" den igual).
6. Colapsa letras dobles consecutivas a una sola (para que "arrós"="aros").

Esta clave fonética SOLO se usa como **segunda pasada**, con menos puntuación que la coincidencia literal, dentro de `_match_meal_food_index` (línea 1383-1417), que es la función que busca qué alimento de la comida actual coincide con lo que el usuario ha nombrado para operaciones como quitar/ajustar cantidad. Es decir: la tolerancia fonética ayuda a **reconocer un alimento que ya está en la comida** cuando el usuario lo escribe mal ("quita el sumo" encuentra el zumo ya puesto), no amplía la búsqueda inicial en el catálogo completo.

---

## 7. Las cantidades

### 7.1 Cómo se interpretan las expresiones de cantidad

- **Gramos explícitos**: "150g", "150 gramos", "1,5 kg" (con coma o punto decimal; kg se convierte a gramos multiplicando por 1000). Parseado por `_parse_cantidad_spec` (línea 2115-2131) para reemplazos, y por el router LLM/`extract_foods` para el caso general.
- **Unidades**: "4 huevos", "2 huevos" → se interpretan como número de unidades, no gramos; se convierten multiplicando por la `racion` (peso de una unidad) del alimento en la base.
- **"La mitad"/"el doble"/"el triple"**: factor multiplicador sobre la cantidad YA puesta de ese alimento (`_intento_multiplicador`), nunca sobre un valor absoluto.
- **Números en palabras**: "un", "una", "dos", "tres", "cuatro", "cinco" (diccionario `_NUM_PALABRAS`, línea 2236).
- **Medidas vagas** ("un poco", "un puñado", "un vaso", "una cucharada", "una loncha", "un chorrito"...): el conjunto `_MEDIDAS_VAGAS` (línea 2008-2013) marca estas expresiones para que NO se traten como "1 unidad literal" — "un poco de arroz" no fija 1 unidad de arroz, se deja que se autodimensione contra lo que falta.

### 7.2 "Quita 100 gramos", decrementos y multiplicadores

`_intento_decremento` (línea 2029-2055) reconoce patrones como "quita 100 gramos de la avena", "2 huevos menos", "quita un huevo" (sin número explícito → 1 unidad del último). Distingue si la cantidad viene en gramos (`en_gramos=True`) o en unidades/porciones. `decrementar_alimento` (línea 2057-2088) resta esos gramos de lo que ya había; si el resultado queda casi a cero (menos del 40% de una unidad para alimentos por unidad, o menos de 4g para el resto), se elimina el alimento entero en vez de dejar una cantidad residual absurda.

### 7.3 Fijar vs incrementar (`set_food_quantity`, línea 1445-1513)

Método central para fijar manualmente una cantidad, con la misma filosofía que la calculadora manual: **NO topa por los macros restantes**, permite sobrepasar el objetivo si el usuario lo pide explícitamente. Si el alimento ya está en la comida, actualiza su cantidad; si no, lo añade con esa cantidad.

Con `incrementar=True`, suma la cantidad pedida a lo que ya hubiera de ese alimento, en vez de fijar el total.

**Tope de cordura**: si la cantidad resultante supera 5000 g (5 kg), se rechaza con `excesivo: True`, y el mensaje al usuario es: *"Esa cantidad no es realista (más de 5 kg). Dime una cantidad normal y lo añado."* (línea 2325).

**Aviso de cantidad "enorme"** (no rechazo, solo aviso): si la cantidad puesta manualmente supera 3 veces el `max_razonable` de ese alimento (ver 7.4), se avisa pero SE RESPETA porque lo ha pedido el usuario explícitamente: *"Ojo: 900g de Pechuga de pollo es una cantidad enorme (lo habitual es no pasar de 300 g). Lo dejo porque lo has pedido tú."* (línea 2318-2322).

### 7.4 Los topes razonables por categoría (`_get_max_cantidad_razonable`, línea 767-825)

Esto SOLO se aplica al **dimensionado automático** (cuando el usuario no da cantidad explícita), nunca a una cantidad que el usuario haya fijado a mano. El comentario lo dice explícitamente: *"para que las cantidades tengan sentido humano (no sugerir 266g de claras)"*.

Para alimentos por unidad (huevos, panes, yogures): tope de 3-4 unidades según categoría (panes: 4 unidades; huevos enteros: 3; yogures: 2; el resto: 3).

Para alimentos a granel, una tabla fija de límites en gramos, "calibrados con las cantidades que aparecen en las dietas reales de los clientes" (línea 788): claras 300g, huevos enteros 190g, embutidos/fiambres 150g, aves/vacuno/cerdo 300g, pescado 300g, proteína en polvo 60g, leche 400g, queso fresco batido 500g, yogures 250g, quesos 100g, cereales 120g, panes 150g, tubérculos 350g, legumbres 250g, frutas 300g, verduras 400g, salsas y condimentos solo 30g ("nunca son 'el plato'"), aceites 30g, frutos secos 60g, aguacate 150g, bebidas deportivas 500g, otras bebidas 400g, arroces/pasta en seco 150g. Default si no cuadra ninguna categoría: 300g.

---

## 8. Sugerencias por fases y filtrado en peri

### 8.1 Las fases (`suggest_foods_for_current_meal`, línea 2592-2776)

Sigue el mismo orden que la calculadora manual: **primero PROTEÍNA, luego HIDRATOS, luego GRASA** (comentario línea 2627: *"orden CALMA: proteína → hidratos → grasa"*). La fase se determina por el macro que más falta de la comida actual (con margen de 4g):
```
si restante[P] > 4: fase = proteína
elif restante[H] > 4: fase = hidratos
else: fase = grasa
```
Si el usuario ha pedido explícitamente un macro concreto ("sugiéreme grasas"), se respeta ese macro directamente (salvo que también haya pedido una marca, en cuyo caso manda la marca). Si el macro pedido ya está cubierto (restante ≤ 0), se le avisa: *"De grasa ya vas servido en esta comida (te pasas 8 g). ¿Quieres sugerencias de lo que sí falta?"*

Categorías CALMA por fase (de `calculator.py`):
- **Proteína** (`CATS_PROTEINA_PURAS`): categorías `1` (huevos), `2` (carnes), `3` (pescados), `4` (proteína en polvo), `5` (lácteos), `6` (soja), `28` (proteína vegetal).
- **Hidratos** (`CATS_HIDRATOS`): `21` (arroces), `8` (panes), `7` (cereales), `22` (pasta), `9` (tubérculos), `11` (frutas), `24` (bebidas vegetales).
- **Grasa** (`CATS_GRASAS + CATS_CUADRAR_GRASAS`): `17.1` (aceites), `17.6` (aguacate), `17.2.1/17.2.3/17.2.4` (frutos secos naturales), `17.4` (mantequilla), `42` y `17.1.1` (grasas de cuadre).

### 8.2 El filtrado en comidas peri (Intra/Post)

Si la comida actual es `Intra` o `Post` (`es_peri = key in ("Intra", "Post")`), NO se usan las categorías por fase: se usa `filtrar_por_tipo_comida(all_foods, "intra" o "post")` (`calculator.py:821-849`), que restringe a categorías específicas de cada momento:
- **Intra**: solo categorías `41` y `18` (`CATS_INTRA`) — bebidas deportivas y similares.
- **Post**: categorías `4, 5, 46, 7, 8, 11, 27, 24, 18, 19, 37, 36, 16` (`CATS_POST`) — proteína en polvo, lácteos, cereales, panes, frutas, bebidas, etc. (comida de recuperación).

Este mismo filtro se reutiliza en `_pick_food_for_macro` (para peticiones de "una grasa"/"algo de proteína" genérico) y en el veto de categorías: en comidas normales se veta la lista completa `CATS_NO_PLATO` (salsas, dulces, fast food...); en peri, solo se veta la categoría `16` (salsas), porque cosas como Aquarius sí son legítimas en el intra aunque técnicamente parezcan "no plato" (comentario línea 2481-2482).

### 8.3 Diversidad, preferencias y evitados

- Se excluyen alimentos cuyo nombre contiene alguna `avoided_keywords` (memorizadas de "sin X" durante la conversación, o del perfil del cliente).
- Se excluyen categorías evitadas del perfil (`avoided_categories`, resuelto vía `AVOIDABLE_PREFIXES`).
- Las categorías preferidas del perfil (`food_preferences`) no EXCLUYEN nada, solo priorizan el orden (comentario línea 2666-2668: *"si el usuario no marcó 'arroces' igual debe ver arroz"*).
- Marca pedida ("algo de FullGas"): se busca en TODO el catálogo (no solo en la fase), porque una marca vende de todo. Si no hay nada de esa marca, se avisa en vez de colar otra cosa.
- Se agrupan los candidatos por categoría a 2 niveles (`coarse`) y dentro de cada grupo se cogen los 8 mejores por aporte al macro driver, se baraja aleatoriamente ese top-8 (para no repetir siempre lo mismo), y lo ya ofrecido antes en esta comida (`seen_sugg`) se manda al final de la lista, no se excluye del todo.
- Reparto round-robin entre "tipos" de alimento para dar variedad (pollo, carne, huevo, pescado... en vez de 6 tipos de pollo).
- Límite por defecto: 6 sugerencias.

### 8.4 Peticiones de macro genérico (`_pick_food_for_macro`, línea 2442-2503)

Cuando el usuario pide "una grasa"/"algo de proteína" sin nombrar alimento, el sistema elige uno real automáticamente (no pregunta). Usa el mismo universo de categorías por macro y el mismo filtrado de peri/evitados que las sugerencias. Entre los candidatos que quepan, prioriza el que MÁS aporta de ese macro; a igualdad de aporte (margen de 2g), prefiere el que necesita MENOS gramos ("comida de verdad, no medio litro de batido comercial", línea 2445-2446). Excluye siempre `CATS_NO_PLATO` (salsas, dulces, refrescos, fast food) aunque técnicamente aporten el macro pedido.

---

## 9. Qué pasa cuando NO encuentra algo o no sabe seguir

El sistema tiene varias respuestas de "no sé" pensadas para no dejar al usuario en un callejón sin salida, todas terminan con una pregunta o una alternativa concreta:

- **No encuentra el alimento en absoluto** (`_NO_LO_TENGO`, línea 1942-1943): *"No lo tengo con ese nombre. ¿Cómo lo llamas normalmente, o quieres que te sugiera algo parecido?"*
- **Match solo parcial** (coincidencia floja, tipo "filete de unicornio"→"Filete de pechuga empanado"): NO se añade en silencio. Se dice: *"No lo tengo en la base de datos. Lo más parecido que tengo es 'X'. Escríbelo si lo quieres."* — el usuario tiene que confirmarlo explícitamente.
- **Lo encuentra pero no cabe en lo que queda** (`_razon_no_cabe`, línea 1572-1592): en vez del críptico "Mínimo excede G restante", explica en lenguaje humano: *"Lo encontré, pero no cabe: su mínimo (150 g) aporta 42 g de grasa y en esta comida solo quedan 10 g de grasa"* (o "ya no queda nada").
- **No encuentra ninguna sugerencia que cuadre** (línea 2758-2767): dice qué falta exactamente y ofrece dos caminos: *"No encuentro nada que cuadre con lo que falta (35 g de proteína). ¿Te digo alimentos aunque se pasen un poco, o prefieres decirme tú qué te apetece?"*
- **Se acaban las opciones de un término al pedir "más de lo mismo"** (línea 1778-1784): *"No me quedan más opciones de tostadas que cuadren con lo que te falta. ¿Quieres que te sugiera otra cosa parecida, o prefieres decirme tú qué te apetece?"*
- **El reparto automático empeoraría lo que ya había** (`rebalance_current_meal`, línea 2551-2558): se detecta comparando el desvío antes/después contra el objetivo; si empeora, se restaura el estado anterior y se es honesto: *"Tus cantidades actuales ya están más cerca del objetivo que cualquier reparto que consigo con estos mismos alimentos, así que lo dejo como está. Para acercarte más, añade o cambia algún alimento."*
- **Cantidad fuera de rango realista**: rechaza con mensaje concreto pidiendo una cantidad normal (ver 7.3).
- **El usuario dice que quiere añadir algo sin decir qué**: se le pregunta cuál, ofreciendo la alternativa de que decida el bot (ver 3.3, `_RE_ADD_SIN_DECIR_QUE`).
- **El LLM del router falla tras reintentos**: se pide reintentar en unos segundos o usar los botones, en vez de fingir una actualización vacía.
- **Nada de lo anterior aplica y el mensaje es corto y sin alimentos reconocibles**: mensaje final con ejemplos concretos de qué se puede escribir (ver 3.5).

---

## 10. La persistencia de la sesión

### 10.1 Dónde vive el estado

Todo el estado de una conversación es el diccionario `self.state` de `NutritionChatbot` (JSON puro: tipo_dia, distribución, comidas_completadas, meal_order, last_options, avoided_keywords, etc. — ver la lista completa en `__init__`, línea 95-123). Se persiste en la colección `db.chatbot_sessions` de MongoDB.

### 10.2 Por qué se persiste en Mongo y no en memoria

El comentario del código lo explica directamente (línea 3468-3472): *"Todo el estado del bot vive en self.state (JSON puro): en cada petición se crea la instancia y se rehidrata desde Mongo, y la ruta guarda al terminar. Así la sesión sobrevive a reinicios del backend y funciona con varios workers (antes vivía en un dict en RAM y obligaba a --workers 1)."*

Es decir: antes el estado vivía en un diccionario Python en memoria del proceso, lo que rompía con más de un worker de Uvicorn/Gunicorn (cada worker tiene su propia memoria, así que una petición podía caer en un worker que no tenía la sesión) y se perdía por completo si el backend se reiniciaba (deploys, crashes). Persistir en Mongo soluciona ambos problemas: cualquier worker puede atender cualquier petición.

Funciones clave (`backend/chatbot.py:3448-3504`):
- `get_or_create_chatbot(session_id, db, user_macros)`: crea la instancia y, si existe un documento en Mongo con ese `session_id`, sobrescribe `chatbot.state` con lo persistido.
- `save_chatbot_session(chatbot)`: hace upsert de `{state: chatbot.state, updated_at: now}` — "última escritura gana" (no hay control de concurrencia optimista).
- `session_exists(session_id, db)`: comprueba si hay un documento con ese id (usado por el frontend al recargar la página, ver 10.4).
- `clear_session(session_id, db)`: borra el documento (usado por "Reiniciar").

### 10.3 TTL: caducidad automática a los 7 días

En `backend/core/database.py:82-83`:
```python
await _ensure("chatbot_sessions", "session_id", unique=True)
await _ensure("chatbot_sessions", "updated_at", expireAfterSeconds=7 * 24 * 3600)
```
Índice único en `session_id` (no puede haber dos documentos para la misma sesión) y un índice TTL sobre `updated_at` que expira el documento a los 7 días desde la última escritura (no desde la creación: cada `save_chatbot_session` actualiza `updated_at`, así que una sesión activa nunca caduca, solo las abandonadas). Esto evita acumular basura de conversaciones a medio empezar indefinidamente, sin necesitar un cron de limpieza manual.

Además, al cerrar sesión, el frontend llama a `DELETE /api/chatbot/sessions` (`backend/routes/chatbot.py:362-368`), que borra TODAS las sesiones de chatbot del usuario inmediatamente (por regex sobre el prefijo `chat_<uid>_`), sin esperar al TTL: *"la conversación caduca con el logout, no espera al TTL"*.

### 10.4 Seguridad: el `session_id` como control de acceso (IDOR cerrado)

El formato del `session_id` (`chat_<user_id>_<fecha-hora>`) no es solo cosmético: es la base de `_assert_session_owner` (`backend/routes/chatbot.py:23-31`), que en TODAS las rutas del chatbot comprueba que el `session_id` empiece por `chat_<uid_del_usuario_autenticado>_` antes de tocar nada. El comentario documenta que esto es un fix de seguridad: *"cierra el IDOR (un cliente no puede tocar la sesión de otro aunque conozca su id)"*. Esto coincide con lo mencionado en la auditoría de simulación de usuarios de la memoria del proyecto (IDOR chatbot, hallazgo pendiente que parece ya resuelto en este punto del código; convendría verificarlo contra la fecha de esa auditoría si hace falta confirmarlo).

### 10.5 Persistencia en el frontend (complementaria, no sustituye a Mongo)

El frontend guarda un snapshot en `sessionStorage` (clave `chatbot_session_state`, `ChatbotPage.jsx:13-17` y el `useEffect` de la línea 65-73) con todo el estado de UI (mensajes, step, targetDate, macrosRestantes, etc.). Esto sobrevive a recargar la pestaña o navegar dentro de la SPA, pero se borra al cerrar la pestaña del navegador (es `sessionStorage`, no `localStorage`).

Al montar la página, si hay una sesión persistida con `step` distinto de `init`, se comprueba contra el backend con `GET /api/chatbot/session-exists` (línea 77-109): si el backend dice que ya no existe (por ejemplo, caducó por el TTL, o el backend se reinició y de alguna forma se perdió — aunque con Mongo esto ya no debería pasar por reinicio), el frontend limpia todo y vuelve a `step: 'init'`, en vez de quedarse mostrando una conversación fantasma que ya no tiene backend detrás.

---

## 11. Modelo de IA y configuración

### 11.1 Modelo usado

`backend/llm_client.py:8`: `DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")`. Se lee de la variable de entorno `OPENAI_MODEL` (en `backend/.env`, según la nota de memoria del proyecto), y si no está definida, cae a `gpt-4.1-mini` por defecto.

Todas las llamadas del chatbot fijan explícitamente este modelo con `.with_model("openai", os.environ.get('OPENAI_MODEL', 'gpt-4.1-mini'))`, tanto en el constructor de `NutritionChatbot` (línea 133) como en `extract_foods` (línea 1085), `understand` (línea 3020) y `answer_question` (línea 2880). El parámetro `provider` ("openai") se ignora en la práctica: el comentario de `llm_client.py:26-31` aclara que siempre se usa OpenAI, se conserva la firma `(provider, model)` solo por compatibilidad con las llamadas existentes.

Según la memoria del proyecto, se descartó explícitamente `gpt-5-mini` porque razonaba ~5s por llamada; `gpt-4.1-mini` no es un modelo de razonamiento y responde más rápido, algo crítico porque el router y el extractor se llaman en CADA mensaje del usuario.

### 11.2 Dónde se configura

- Variable de entorno `OPENAI_MODEL` en `backend/.env`.
- Variable de entorno `OPENAI_API_KEY`, leída tanto en `LlmChat.__init__` (línea 18) como directamente en `NutritionChatbot.__init__` (`self.api_key = os.environ.get('OPENAI_API_KEY')`, línea 92).

### 11.3 Particularidades del cliente (`LlmChat`, `backend/llm_client.py`)

- `with_json_mode(enabled=True)` fuerza `response_format: {"type": "json_object"}` de la API de OpenAI — se usa en el constructor del chatbot, en `extract_foods` y en `understand` (todas las llamadas que esperan JSON estructurado), pero NO en `answer_question` (que devuelve texto libre para el usuario).
- Gestión de `max_tokens` según familia de modelo (línea 59-70): si el modelo empieza por "gpt-5", usa `max_completion_tokens=4096` y fuerza `reasoning_effort="minimal"` explícitamente — el comentario explica que esto evita "+5s de latencia y el coste de los reasoning tokens" en el router y las respuestas cortas, que no necesitan razonamiento profundo. Si es o1/o3/o4 (modelos de razonamiento), también usa `max_completion_tokens`. Para el resto (incluido `gpt-4.1-mini`, el que realmente se usa), usa el parámetro clásico `max_tokens=4096`.
- Cada llamada al router (`understand`) y al extractor (`extract_foods`) crea una instancia NUEVA de `LlmChat` (sin arrastrar historial de conversación) — cada mensaje del usuario se interpreta de forma aislada respecto al LLM; toda la "memoria" de la conversación vive en `self.state` (Python), no en el historial de mensajes del modelo.
- El `system_message` de la clase (`SYSTEM_PROMPT`, línea 37-72) describe un flujo de "build_meal"/"question"/"meal_complete" con JSON, pero en la práctica este prompt de más alto nivel casi no se usa: el flujo real está gobernado por `understand()` (el router) y sus propios prompts específicos por función, más el flujo determinista en Python. `SYSTEM_PROMPT` queda como el mensaje de sistema fijo del chat de la instancia (`self.chat`), pero las funciones que realmente hacen el trabajo (`extract_foods`, `understand`, `answer_question`) crean sus propios `LlmChat` con su propio `system_message` específico, ignorando `self.chat`.

---

## Notas adicionales de interés

- **Calibración progresiva del día** (`_recalibrar_dia`, línea 1907-1938; usa `calibracion_dia.calibrar_dia`): cada vez que se muta la comida (`_meal_response`, que es el punto de salida de TODA mutación), se recalcula la calibración de proteína vegetal sobre TODO el día en orden cronológico según `meal_order`, con los acumulados de cereales+panes y frutos secos. Esto significa que editar una comida puede cambiar los macros mostrados de comidas POSTERIORES (nunca de las anteriores, porque el tramo de cada comida solo depende de las que van antes). Esto es justo lo que describe la nota de memoria "Calibración progresiva por día".
- **Motor de conteo único**: todo el cálculo de macros pasa por `calma_suggest` (vía `calibracion_dia.macros_item_por_acumulado` para el motor base, y directamente `calma_suggest.macros_at`/`ajustar_cantidad` para dimensionado), nunca por `calma_engine` para contar macros — coincide con la nota de memoria "Motor de conteo unificado" (desde 31-07 todo cuenta por `calma_suggest`).
- El chatbot reutiliza expresamente el mismo motor y criterios de ordenación que la calculadora manual ("Lo hago yo") en varios puntos (desambiguación, orden genérico/marca, categorías por fase), como decisión explícita para que ambos caminos den resultados coherentes entre sí.
