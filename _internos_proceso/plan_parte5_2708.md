# Plan de trabajo · «Para el equipo · parte 5» (puntos 144 a 178)

> **ESTADO 27-08, final del día: HECHO Y COMPROBADO EN EL NAVEGADOR, sin desplegar.**
> Los 34 puntos que se podían hacer están cerrados (bloques C, A, D y B, en ese orden).
> El **174 sigue bloqueado** y hay **cuatro cosas que contestar** — todo al final de este
> documento, en «Lo que queda».
> Guiones de comprobación: `_guia/_bloque_c_2708.js`, `_bloque_a_2708.js`, `_bloque_d_2708.js`,
> `_bloque_b_2708.js`, `_bloque_b_circuito_2708.js` y `_p178_grasa_2708.js`.

Fuente: `C:\Users\Administrador\Desktop\Para el equipo · parte 5.html` (27-08-2026).
Sigue a la parte 4, que cerró en el 143. Son **35 puntos** en tres pantallas.

Antes de tocar nada dejo aquí el diagnóstico de cada bloque, porque en tres de ellos el
punto no es lo que parece: hay un dato que no existe en la base, una regla que ya se
discutió el 25-08 y una frase aprobada que contradice a otra frase aprobada.

---

## Reparto en cuatro bloques (ficheros disjuntos, salvo un cruce)

| Bloque | Puntos | Ficheros |
|---|---|---|
| **A · El buscador** | 144, 145-160 | `frontend/src/pages/FoodSearchPage.jsx` · `backend/routes/calculator.py` (`/foods-listado`, `_que_te_cuenta`) |
| **B · Solicitar alimento** | 161-169 | `frontend/src/components/nutrition/SuggestFoodModal.jsx` · `backend/routes/calculator.py` (`/suggest-food`) · `backend/models/common.py` · `frontend/src/pages/AdminFoodSuggestionsPage.jsx` |
| **C · Inicio** | 170-178 | `frontend/src/components/inicio/TuDietaHoy.jsx` · `frontend/src/pages/ClientDashboard.jsx` · `frontend/src/components/nutrition/ExtrasDelDia.jsx` · `frontend/src/index.css` · `public/index.html` |
| **D · El vacío dentro de una comida** | 144 (mitad) | `frontend/src/components/nutrition/BuildMealModal.jsx` |

**El cruce**: A y B tocan los dos `backend/routes/calculator.py`, pero en funciones
distintas y separadas por 1.200 líneas (`/foods-listado` en la 349, `/suggest-food` en la
1603). Si van en paralelo, cada uno se queda en su función y no se toca el fichero entero.

---

## BLOQUE A · El buscador (144, 145-160)

### Lo que ya está en el servidor y no hay que inventar

`GET /calculator/foods-listado` ya devuelve **`cantidad_minima`** y **`sugerencia`**
(`calculator.py:409-410`). El punto 148 dice que la cantidad mínima «está en CALMA y falta
en la app»: falta en la **pantalla**, no en el servidor. Es trabajo de front, salvo la
frase, que hay que reescribir.

### Diagnóstico punto a punto

**145 · Cuatro líneas a la izquierda.** Hoy `FoodRow` es un `flex` con los macros en un
`sm:text-right` a la derecha (`FoodSearchPage.jsx:133-159`). Se rehace la fila entera en
cuatro líneas apiladas. Es el punto que más código mueve del bloque.

**146 · «Por cuánto es» debajo del nombre.** El dato viaja (`racion`, `unidades`), hoy sale
el último (`línea 152-154`) y dice «por cada unidad de 63g» → pasa a «por unidad, de 63 g».

**147 · Las frases de «te cuenta».** Reescribir `_que_te_cuenta` en `calculator.py:439`.
Hoy da «Te cuenta grasa.» / «Te cuentan los tres.» / «No te cuenta nada: come lo que
quieras.». Tiene que dar:
- `Te cuenta todo` — cuentan todos los que **tiene** (el huevo: P y G, sin H, y las dos cuentan). Hoy eso da «Te cuentan los tres», que es falso para el huevo.
- `Te cuenta solo la grasa / solo la proteína / solo el hidrato` — tiene más de uno y cuenta ese.
- `Te cuenta la proteína y la grasa` — tiene tres, cuentan dos.
- `No te cuenta nada` — sin los dos puntos ni la coletilla.
- Con calibración: `Te cuenta la grasa`, **sin el «solo»** (`se_calibra` ya entra como parámetro).

Y desaparece la cola «Su proteína no te cuenta» (líneas 460-465): el «solo» ya lo dice.
Ojo al singular **«el hidrato»**, que hoy es «hidratos» en `_NOMBRE_MACRO`.

**148 y 149 · El mínimo y el «necesitas», en la misma línea.**
`cantidad_minima()` (`calma_suggest.py:269`) devuelve **unidades** si el alimento va por
unidades y **gramos** si va a granel. La frase se arma así:
- por gramos → `Desde 50 g · necesitas 9 P · 5,5 H · 5,5 G`
- por unidades → `Desde 1 unidad` / `Desde media <nombre>`

**El agujero del 149**: el nombre de la unidad (tarrina, hamburguesa, lata, yogur) **no
existe como campo en `db.foods`**. Medido contra producción: de **1.131** alimentos por
unidades, **482 (43 %)** no llevan ninguna palabra de unidad reconocible en el nombre
(«Mousse proteica chocolate (Milbona)», «Zero Bar (BiotechUSA)», «Quesitos light»).

Pero el problema real es mucho más pequeño de lo que parece: **solo 142 de los 1.131 tienen
el mínimo en MEDIA unidad**, y son justo los del ejemplo (hamburguesas, tarrinas al minuto,
brazos y bizcochos de My Fitness Meals, y lo que caiga en la categoría 11.1). Y en los tres
ejemplos del artifact el nombre de la unidad **solo aparece cuando dice «media»**:
«desde media hamburguesa», «desde media tarrina», y para el huevo —que va por unidad
entera— pone **«desde 1 unidad»**, no «desde 1 huevo».

→ **Decisión propuesta**: unidad entera siempre `Desde 1 unidad`; media unidad, el nombre
sacado del nombre del alimento con una lista corta, y `media unidad` de reserva. Con 142
fichas la lista se puede revisar a mano una vez y se acabó. Hay tres raros dentro de esas
142 —`Ciruela Claudia`, `Nectarina`, `Ensalada de la casa (Hacendado)`— que hay que mirar:
«media ciruela» suena mal y probablemente entren por la categoría 11.1.

**150 · Los que no aportan macros.** `sugerencia` da hoy «Siempre puede ser sugerido» →
`Desde 50 g · siempre cabe`. Y el filtro de `FoodSearchPage.jsx:376`, «Verduras libres» →
**«No aportan macros»**. El mínimo no es fijo (100 en bebidas, 10 en salsas, 50 en lechuga)
y eso ya sale bien de `cantidad_minima`.

**151 · El kétchup zero.** No hay que tocar nada: `macros_reales` ya viaja solo cuando
`eff != orig` (`calculator.py:407-408`). El kétchup tiene macros y no le cuentan → los
lleva. La lechuga no tiene → no los lleva. La regla ya está bien; lo que cambia es dónde se
pintan (punto 154).

**152 · El nombre abre la ficha, la web tiene su botón.** Hoy el nombre de una marca es un
`<a href>` naranja subrayado (`líneas 123-130`) y el de un genérico no abre nada. Pasa a:
nombre = abre la ficha (los dos casos), sin subrayado; y a la derecha `GENÉRICO` o
`Ver web ↗`. Esto obliga a **abrir la ficha de cualquier alimento**, no solo de los que
llevan punto: hoy el desplegable solo existe si hay `calibracion` (`línea 179`).

**153 · Una categoría, no cuatro.** Hoy `cats.join(' | ')` pinta las cuatro
(`línea 162`). **Trampa comprobada contra producción**: «quedarse la primera» falla en
**35 de 3.219 fichas**, donde el primer trozo es una etiqueta transversal y no una
categoría — `Muesli proteico (Micros) → YA | 7.1.3`, `Harina de espelta (Hacendado) →
POL | 7.2.3`, `Picatostes (Hacendado) → SNA | YA | 8.4`. La regla buena es **la primera
que sea numérica**, con la primera cualquiera de reserva.

**154 · Al abrir: los reales y la calibración.** Los `macros_reales` bajan al detalle
(hoy en la lista, `líneas 146-151`) y con ellos los tres tramos. La categoría no se repite
dentro.

**155 · El mismo punto arriba y abajo.** Hoy son dos `span` distintos: la viñeta de la
leyenda (`línea 309`) y el de la lista (`línea 120`). Mismo tamaño y mismo color.

**156 · El orden de arriba abajo.** Hoy el campo de buscar está en la línea 317, después de
título, botón y tres párrafos. Pasa a: campo → filtros en **una fila de botones** (hoy son
seis líneas: dos etiquetas, dos `select` y dos redondeles) → leyenda → contador y
resultados → enlace de pedir al final.

**157 · La leyenda pierde los tramos.** Se caen las dos frases de tramos de las
`líneas 312-313`; se quedan qué es un genérico y qué significa el punto.

**158 · El botón de pedir, al final.** Hoy es lo primero, en `bg-brand-orange` y arriba a la
derecha (`líneas 279-285`). Baja al final de la lista y como enlace.

**159 · Tres cosas del texto de arriba.** `marcas` en negrita, guion en vez de dos puntos, y
la jerarquía de tamaños al revés (`text-sm` en la línea que menos dice, `text-xs` en las que
explican el método).

> **CONTRADICCIÓN entre dos puntos aprobados.** El 159 manda conservar el texto del punto
> 137, que hoy dice *«Las marcas llevan el nombre subrayado en naranja y tocando el nombre
> vas a su web»*. El 152 **quita el subrayado y quita ese gesto**. La frase se queda
> describiendo algo que ya no pasa.
> → **Lo cierro yo así**: *«Los **genéricos** son alimentos sin marca — pollo, arroz,
> almendras. Las **marcas** llevan «Ver web ↗»»*. Se lo digo a Jesús al entregar, no le
> bloqueo el punto por una frase.

**160 · Fuera los colores.** Quitar `MACRO_DEFS` con sus tres clases de color
(`líneas 86-92`): los números en el color del texto. Es el punto que cierra la regla de
color de la parte 4 (el color es estado, no tipo de macro).

**Y lo que Jesús deja apuntado**: los 19,3 H del *Arroz blanco (SOS)* los calculó él, no
salen de CALMA. Hay que comprobarlos en la base antes de darlos por buenos.

---

## BLOQUE B · Solicitar un alimento (161-169)

Hoy el formulario es `SuggestFoodModal.jsx`, 232 líneas, y **se queda corto en casi todo lo
que pide la parte 5**. Es el bloque con más obra nueva.

### Lo que ya existe

El **límite de 2 por semana ya está en el servidor** (`calculator.py:1624-1633`,
`WEEKLY_SUGGESTION_LIMIT`) y devuelve un 429. Lo que no existe es **decírselo antes**: para
pintar «Te quedan 2 peticiones esta semana» hace falta que el contador viaje. Es un `GET`
nuevo, o el dato colgado de una llamada que ya se haga.

### Lo que falta

**161 · Todo obligatorio.** Hoy solo se valida el nombre (`línea 84`) y las fotos salen
literalmente como *«opcionales, pero ayudan a la revisión»* (`línea 209`). Pasan a ser
obligatorias las dos, más los macros, más el enlace (o la casilla). Asterisco naranja,
botón gris y `Te faltan 3 campos por rellenar` debajo. **La validación hay que ponerla
también en el servidor**, no solo en la pantalla.

**162 · Cuatro bloques en este orden**: Qué es (nombre + foto frontal) · Los macros (foto
del reverso + por 100 g/unidad + números) · Cómo viene (lata) · De dónde sale (enlace).
Hoy los números van antes que las fotos.

**163 · «Foto del reverso o lateral»**, y los pies: «Que se vea el nombre del alimento» /
«Que se vea el valor nutricional».

**164 · Por 100 g o por unidad, y su peso.** Hoy es una **casilla** («Se toma por unidad
(pieza)», `línea 149`) y no se exige el peso salvo si se marca. Pasa a dos botones y, si es
por unidad, el peso es obligatorio y el título de abajo lo repite: «Anota los macros de esa
unidad de 125 g».

**165 · Las latas: campo nuevo.** Hoy hay `peso_tipo` (neto/escurrido) **siempre visible y
sin preguntar si es lata** (`líneas 162-179`). Hace falta un campo nuevo —«¿Viene en lata o
en conserva?»— y que `peso_tipo` solo se pregunte cuando diga que sí, y en forma de
«¿Esos 52 g son el peso escurrido?». Toca `models/common.py` (`FoodSuggestion`) y la
pantalla del admin, que tiene que ver el dato nuevo.

**166 · El enlace y la casilla «No tiene web».** El enlace ya existe y ya alimenta el
`Ver web ↗` del punto 152 — son el mismo dato. Falta hacerlo obligatorio y darle la salida
de la casilla para los genéricos.

**167 · El botón.** «Enviar sugerencia» → **«Solicitarlo»**, y de `bg-green-600`
(`línea 221`) a naranja. El verde significa «ese macro ya está resuelto» en el resto de la
app: es el tercer color fuera de sistema de este circuito, con el amarillo del 158 y el azul
del 160.

**168 y 169 · Los textos de arriba.** Entra el aviso con los plazos (viernes a las 10,
corte el martes) y se cae entero «El equipo lo revisará y, si procede, lo añadirá»
(`líneas 121-123`). Y «de la etiqueta» → «del envase» en los dos sitios donde sale
(`líneas 122 y 191`).

---

## BLOQUE C · La pantalla de Inicio (170-178)

**170 · Nada que hacer.** Ya abre en «Macros»: `TuDietaHoy.jsx:98`, `useState('macros')`.
Solo hay que verificarlo y dejar constancia.

**171 · «Marca lo que te vayas comiendo».** `TuDietaHoy.jsx:495`. Cambia el rótulo y de paso
cuadra con el «Marca abajo lo que vayas comiendo» de dentro de la pestaña Llevas.

**172 · Los números, 44 px y peso 850.** Hoy `text-[34px] sm:text-[40px]`
(`TuDietaHoy.jsx:409`, y lo mismo en `ClientDashboard.jsx:82`).

> **Esto ya se discutió el 25-08.** `index.css:140-145` lleva escrito: *«Mismo tipo y peso
> 700 — que es el que ya tenían, aunque el documento diga 850»*, y en su lugar se puso un
> `transform: scaleY(1.12) scaleX(0.9)`. Jesús lo vuelve a pedir, así que ahora se hace.
> **Pero el 850 no se puede pintar hoy**: `public/index.html:17` carga Inter en pesos
> estáticos `300;400;500;600;700;800`. Para tener 850 hay que pedir el rango variable
> (`Inter:wght@100..900`) y usar `font-variation-settings`. Es una línea. Y hay que decidir
> si el `transform` del 25-08 se queda o se va: con 44/850 encima, seguramente sobra.

**173 · Los números de las comidas, con letra.** `lineaMacros` en `TuDietaHoy.jsx:88`.
`32 · 19 · 6` → `32P · 19H · 6G`. `ExtrasDelDia.jsx:43` ya lo hace así, sirve de patrón.

**174 · BLOQUEADO. Los suplementos con las comidas.**
No es trabajo de pantalla: **el dato no existe**. En `models/supplements.py`, `ProtocolItem`
guarda `cuando` como **texto libre** («Todos los días, con el desayuno»). No hay ningún
campo que diga «este suplemento va con la Comida 3». Y sacarlo parseando el texto está
descartado por método.
Esto es la pregunta 99/118 que ya lleva abierta desde la parte 3 y la parte 4. Hasta que
Jesús diga cómo se asigna un suplemento a una comida —campo nuevo en el protocolo, lo más
probable— este punto no se puede hacer. **El resto del bloque C no depende de él.**

**175 y 176 · Extras.** «no estaba previsto» y bajar el tamaño del texto de ayuda.
`ExtrasDelDia.jsx`.

**177 · La frase del día, sin punto final.** `ClientDashboard.jsx:763`. El punto no está en
el código: viene **dentro del texto guardado** (`appSettings.frase_del_dia.texto`,
`línea 738`). Hay que decidir si se quita al pintar —un `replace` del punto final— o se
limpian las frases en la base (`backend/_cargar_frases.py`). **Recomiendo quitarlo al
pintar**: las frases las carga un script y las escribe gente, y así no vuelve a colarse.

**178 · El descuadre de la grasa (40 aquí, 41 en Nutrición).**
Los dos números salen del mismo sitio (`reparto.resumen.G_total` en `TuDietaHoy.jsx:193`;
`dayTarget.G_total` en `NutritionPage.jsx:2261`), así que **no basta con mirar el código: si
las dos cuentas fueran idénticas, coincidirían**. Hay que reproducirlo en el navegador con
la ficha que lo dio, ver los dos valores en crudo, y solo entonces decidir dónde se corrige.
Es el único punto de la parte 5 que empieza por diagnóstico y no por decisión.

**Lo apuntado para más adelante** (Macros y Falta enseñan lo mismo hasta que se marca algo):
no se toca. Queda escrito y ya está.

---

## BLOQUE D · El vacío dentro de una comida (mitad del 144)

`BuildMealModal.jsx:1232-1239`. «No se encontraron alimentos» → el mismo texto de Alimentos.
Ojo: ahí hay **tres** mensajes de vacío distintos (buscando, frecuentes, categoría vacía) y
el punto solo habla del de buscar. Los otros dos se quedan.

---

## Decisiones que tomo yo (y se las cuento al entregar)

1. **Punto 153** — «la primera categoría» = la primera **numérica** (35 fichas de 3.219 se
   arreglan solas con eso).
2. **Punto 149** — unidad entera → «1 unidad»; media unidad → nombre del alimento, con
   «media unidad» de reserva. Coincide con los tres ejemplos del artifact.
3. **Punto 159 vs 152** — reescribo la frase de las marcas: «llevan «Ver web ↗»».
4. **Punto 177** — el punto final se quita al pintar, no en la base.
5. **Punto 172** — se carga Inter variable para poder dar el 850 de verdad.

## Lo que se pregunta a Jesús

1. **Punto 174** — cómo se dice que un suplemento va con la Comida 3. Es la misma pregunta
   99/118 que lleva abierta desde la parte 3. Bloquea el punto entero.
2. **Punto 149, los tres raros** — «media ciruela», «media nectarina», «media ensalada de la
   casa». Si son de la categoría 11.1 y no debían llevar mínimo de media unidad, es un dato,
   no una pantalla.
3. **Punto 144 en Alimentos** — «Puedes pedirlo desde Alimentos» dicho **dentro** de
   Alimentos suena raro. Él dice «igual en los dos sitios», así que lo hago literal y se lo
   apunto.

## Cómo se comprueba

Navegador contra la app real, las tres pantallas, teléfono y escritorio (Playwright en
`_guia/`, y la regla de siempre: encoger `#root` no prueba móvil).
- **Bloque A**: los **nueve alimentos del artifact** son la batería, y están escogidos para
  cubrir todos los casos (un macro, dos, todos, ninguno; con calibración y sin ella;
  genérico y marca; por gramos, por unidad y por media unidad). Se comprueban uno a uno
  contra los literales del documento.
- **Bloque B**: los **tres formularios del artifact** (por unidad, por 100 g, lata), más el
  429 del límite semanal y el guardado en la pantalla del admin.
- **Bloque C**: las cuatro pestañas a primera hora y con comidas marcadas.
- Tests: solo los ficheros que cubren lo tocado (`test_foods_paginacion_2308.py` y los del
  buscador). **Ningún rojo se da por «de otro».**

## Orden

1. **C** primero: son los cambios más pequeños y ninguno depende de nadie (menos el 174).
2. **A** y **D** después, juntos: D es una línea del mismo texto que A.
3. **B** el último: es el que trae campo nuevo en el modelo y toca la pantalla del admin.
4. Informe en artifact y **nada a producción sin que lo pida**.

---

# Lo que salió al hacerlo (27-08)

## Tres cosas que no estaban en el plan

**El 178 no era redondeo, y el fallo estaba en Nutrición.** La cabecera pintaba el número
grande de grasa con `dayMacros.G`, que **sí** lleva la del intra y el post, y lo comparaba
con un objetivo (`G_total`) que **no** la lleva: en el método el objetivo del peri no tiene
grasa. Creado y objetivo medían cosas distintas en la misma columna. El Inicio no tenía el
fallo -- allí lo montado sale de `servido_comidas`, que el servidor cuenta sin el peri --, así
que el bueno era el del Inicio. `mainG` ya existía y de él salía el estado del día; sólo se
pintaba el otro. El comentario del código decía «en grasa día y comidas coinciden: el peri no
lleva grasa», y en producción hay **27 días guardados que lo desmienten** (batidos con 2 a 4 g
de grasa). Arreglado en `DayHeader.jsx` y **reproducido antes y después**: con el arreglo
quitado, Nutrición decía 20 e Inicio 10; con él puesto, las dos dicen 10.

**El 850 no se podía pintar.** `public/index.html` cargaba Inter en pesos estáticos hasta 800,
así que un 850 se redondeaba al 800 sin avisar. Ahora se pide el rango (`Inter:wght@300..900`)
y se comprueba en el navegador que la fuente de 850 existe de verdad
(`document.fonts.check('850 44px Inter')`). Se cayó el `transform: scaleX(0.9)` del 25-08, que
estaba ahí para adelgazar los números y ahora trabajaría contra el peso nuevo.

**El buscador iba justo de tiempo y se le hizo sitio.** El catálogo pesaba 1.644 KB y tardaba
2,69 s, con el tope de Jesús en 3 s. `sugerencia` -- una frase por alimento que ninguna
pantalla leía desde el 26-08 -- eran **224 KB**. Fuera: 1.420 KB y 2,61 s.

## Cuatro tests rojos, mirados uno a uno

Los cinco de `test_casos_E_motor_macros` que arrastrábamos: **tres se cerraron** y los dos que
quedan son de los que fallan a propósito porque esperan una decisión.

- `test_sale_como_come_lo_que_quieras` y `test_aun_asi_el_motor_le_asigna_un_minimo` esperaban
  50 g de mínimo para las verduras. Es el valor de Calma, y **Jesús lo subió a 100 el 15-08**.
  El test se había quedado con el heredado.
- `test_no_lo_deja_a_medias[51/76-calabacín]` **se puso rojo ese mismo día y nadie ató las dos
  cosas**: con el mínimo en 50, los 51 g bajaban a 50 y pasaba; con el mínimo en 100 no hay
  ningún múltiplo por debajo que valga, y `redondear_a_la_baja` devuelve la cantidad tal cual
  a propósito («falsearla sería peor que tener un número feo»). El test comprobaba media
  regla; ahora comprueba la entera.
- Siguen rojos, y los dos lo dicen en su propio texto: `test_la_linea_de_nutricion_tambien_lo_dice`
  (falla a propósito) y `test_la_proteina_tampoco_cuenta_al_calibrar_el_dia` (dos
  especificaciones suyas dicen cosas distintas). El de Suplementos de `test_casos_I` es de otro
  frente.

Y las dos pruebas que mandan una solicitud de alimento se actualizaron: desde el 161 las fotos
son obligatorias también en el servidor, así que una solicitud a medias ya no entra.

## Lo que queda

1. **Punto 174, BLOQUEADO** — los suplementos con las comidas. No es trabajo de pantalla: el
   dato no existe. En `models/supplements.py`, `ProtocolItem.cuando` es **texto libre** («con
   el desayuno») y no hay ningún campo que diga «este suplemento va con la Comida 3». Sacarlo
   parseando el texto está descartado por método. Es la pregunta 99/118, abierta desde la
   parte 3.
2. **Los dos mínimos de la maqueta** — el 148 los saca de CALMA y escribe «Almendras desde
   5 g» y «Lechuga desde 50 g», que son justo los dos que él cambió después: frutos secos a
   10 g el 07-08 y verduras a 100 g el 15-08 («los vegetales siempre que sugiera 100 gramos,
   no 50 por defecto»). **La app se queda con 10 y 100**, que es lo que decidió mirando la
   app, y la maqueta está hecha desde Calma. Ver `MINIMOS_JESUS` en `calma_suggest.py`.
3. **El 152 contra el 159** — el 159 manda conservar la frase que dice que las marcas van
   subrayadas y que tocando el nombre vas a su web; el 152 quita las dos cosas. Resuelto como
   «Las **marcas** llevan «Ver web ↗»».
4. **El 144 dentro de Alimentos** — «¿Sigue sin estar? Puedes pedirlo desde Alimentos» dicho
   estando ya en Alimentos suena raro. Se hizo literal porque él dice «igual en los dos sitios».

Y una que él mismo dejó apuntada y **ya está comprobada**: los **19,3 H del arroz blanco
(SOS)**, el único número que calculó a mano, salen correctos contra la base.
