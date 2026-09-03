# Plan · «Al pulsar "Aplicar" en una favorita» (Jesús, 3-09-2026)

Artifact: https://claude.ai/code/artifact/e4915db7-c1bf-46bc-a6e4-273916982ac5
Leído entero el 3-09-2026 (pie: «3 de septiembre de 2026»).

> **ESTADO 3-09: HECHO Y COMPROBADO. Sin desplegar.**
> Todos los puntos de abajo están implementados y verificados en el navegador a **1280 y a
> 390**, con el guion `_guia/_verificar_aplicar_favorita_0309.js` (25 comprobaciones por
> ancho, todas en verde) y capturas en `_guia/_favorita_0309/`.
> Queda pendiente **la decisión 1** (¿lleva Cancelar el caso 3?): implementado CON Cancelar.
> Y una pregunta suelta para Francisco, al final del fichero.

Fichero que manda casi todo: `frontend/src/components/nutrition/FavoritesModal.jsx`.
Fichero de apoyo: `frontend/src/pages/NutritionPage.jsx` (`applyDietFavorite`, línea 2170;
`diaVacio`, línea 2988; el `<FavoritesModal .../>`, línea 3623).

---

## Lo que el documento da por bueno y ya está en la app (verificar, no tocar)

| # | Lo que dice | Dónde está | Estado |
|---|---|---|---|
| A1 | La app mira dos cosas: si el día ya tiene comidas y si la favorita es del mismo tipo | `handleApplyClick` (FavoritesModal:87) | YA |
| A2 | Cada una añade su frase | panel `confirmId` (FavoritesModal:184-196) | YA |
| A3 | Las frases van siempre antes de los botones | mismo bloque | YA |
| A4 | Orden: primero lo que se pierde, después el tipo de día | `!diaVacio` primero, `favTipo !== tipoDia` después | YA |
| B1 | Caso 1 (día vacío + mismo tipo): sin aviso, se aplica y ya | FavoritesModal:89-92 | YA |
| E2 | Caso 4: los botones son los del caso 2, según el sentido | rama `favTipo !== tipoDia` | YA |
| F5a | Cancelar cierra el aviso y deja en la lista, no cierra las favoritas | `setConfirmId(null)` (FavoritesModal:223) | YA |
| F5b | Volver a pulsar Aplicar en esa favorita también cierra el aviso | toggle en `handleApplyClick` | YA |

---

## Lo que hay que cambiar

### Bloque 1 · Los literales del caso 2 y 4 (tipo de día)

| # | Hoy | Debe decir |
|---|---|---|
| C1 | «Esta favorita se guardó en día de **entreno** y hoy es día de **descanso**.» | «Esta favorita es de día de entreno; hoy tienes descanso.» |
| C2 | (la misma frase al revés) | «Esta favorita es de día de descanso; hoy tienes entreno.» |
| C3 | «Adaptar a mi día de hoy (descanso)» | «Aplicar y adaptar a mi día de hoy» (sin paréntesis, igual en los dos sentidos) |
| C4 | «El intra/post se quitará porque en descanso no hay periworkout.» | «el intra y el post se quitan» |
| C5 | «El peri quedará vacío: podrás añadirlo con "Sugiéreme un menú".» | «se añaden el intra y el post, que tendrás que rellenar» |
| C6 | «Aplicar como se guardó (**cambia** el día a entreno)» | «Aplicar como se guardó (**pasa** el día a entreno)» |
| C8 | Las dos palabras del tipo de día van en negrita | En la maqueta la frase va toda del mismo peso: quitar el `font-bold` |

Nota de C4/C5: la línea gris va **entre** el primer botón y el segundo, que es donde ya está.

### Bloque 2 · El caso 3 (día con comidas, mismo tipo)

| # | Hoy | Debe decir |
|---|---|---|
| D1 | «Este día ya tiene comidas. **Al aplicar la favorita se reemplazan.**» | «Este día ya tiene 3 comidas. Al aplicar la favorita se borran y se quedan las de la favorita.» (sin negrita, y con el número real) |
| D2 | Botón «Aplicar y reemplazar» | Botón «Aplicar» |

### Bloque 3 · El número de comidas (detalle 1)

| # | Qué |
|---|---|
| F1a | El aviso tiene que decir el número: «Este día ya tiene **3** comidas». Hoy el modal no recibe ese dato: solo le llega `diaVacio`. Hay que pasarle desde `NutritionPage` cuántas comidas montadas tiene el día abierto. |
| F1b | Singular de verdad: «1 comida», no «1 comidas». |
| F1c | El intra y el post **no cuentan** como comidas (regla de la casa desde el 31-08, ya aplicada en el contador de la lista de favoritas): se cuentan solo `C1..Cn` con alimentos. |
| F1d | **Caso borde**: un día que solo tiene el intra o el post montado no está vacío, pero tiene 0 comidas, y diría «Este día ya tiene 0 comidas». Hay que nombrarlo por su nombre: «Este día ya tiene el intra y el post.» / «...el intra.» / «...el post.» |

Cálculo, en `NutritionPage`, al lado del `diaVacio` que ya existe (línea 2988):

```js
const montadas = Object.entries(mealsData || {})
    .filter(([, m]) => (m?.alimentos || []).length > 0).map(([k]) => k);
const comidasDelDia = montadas.filter(k => /^C\d+$/.test(k)).length;
const periDelDia   = montadas.filter(k => k === 'Intra' || k === 'Post');
```

y se le pasan al `<FavoritesModal>` como props nuevas.

### Bloque 4 · La línea gris cambia con el sentido (detalle 2)

| # | Qué |
|---|---|
| F2a | Texto: ya cubierto en C4 y C5. |
| F2b | **Comportamiento a comprobar en la app**: de entreno a descanso el peri se quita; de descanso a entreno se añade **vacío, con sus macros y sin alimentos**. En el código esto sale de `descartar_sin_objetivo: adaptar` + `ordenDeComidas` con el `tipoDia`/`opcionPeri` de hoy (NutritionPage:2215 y 2230). Sobre el papel cuadra; hay que verlo con captura, que es la prueba. |
| F2c | «La app no se inventa qué meter dentro»: confirmar que al añadir el peri vacío no se dispara ninguna sugerencia automática. |

### Bloque 5 · El día queda sin cuadrar y no se avisa aparte (detalle 3)

| # | Qué |
|---|---|
| F3a | De descanso a entreno el día queda sin cuadrar porque el intra y el post están vacíos. **No se avisa aparte**: bastan el punto naranja de la pestaña y la barra a medias. Comprobar que efectivamente no sale ningún aviso extra de «sin cuadrar» por esa vía (el filtro de `cortas` ya excluye Intra/Post, NutritionPage:2267). |
| F3b | Quitar de la línea gris el «podrás añadirlo con "Sugiéreme un menú"»: el documento lo sustituye por «que tendrás que rellenar». |
| F3c | Comprobar con captura que el punto naranja de la pestaña y la barra a medias salen de verdad en ese estado. Si no salieran, el arreglo es ese, no un aviso nuevo. |

### Bloque 6 · Los botones y el Cancelar (detalle 4)

| # | Qué |
|---|---|
| F4a | Los dos que aplican son botones; el primero relleno en naranja (el recomendado), el segundo solo con el borde. **Ya es así**: verificar con captura. |
| F4b | Cancelar es un enlace en gris, **sin caja**. Hoy es un `<button>` sin fondo pero centrado a todo el ancho; en la maqueta va alineado a la izquierda y subrayado. Ajustar. |

### Bloque 7 · Arrastres

| # | Qué |
|---|---|
| G1 | Los avisos de después de aplicar siguen con la voz vieja: «El intra/post se ha quitado porque hoy no hay periworkout» (NutritionPage:2279) y «El peri ha quedado vacío: la favorita no lo traía. Añádelo con "Sugiéreme un menú"» (NutritionPage:2308). Alinearlos con «el intra y el post» y quitar el puntero a «Sugiéreme un menú», que el documento ya no usa. |
| G2 | `_guia/GUIA-COMPLETA-12EN12.md:645` cita los literales viejos («Adaptar a mi día de hoy»). Actualizar. |
| G3 | «Repetir un día» (`DiaVacio` → `repetirDiaReciente`, NutritionPage:2342) usa el mismo motor pero **sin panel**: aplica en cuanto se pulsa, con el chip «Encaja»/«Se adapta» como único aviso. Ese camino solo existe en día vacío, así que no choca con el caso 1, pero el caso 2 (día vacío + otro tipo) **sí** pide aviso y ahí no lo hay. El documento habla solo de «Aplicar en una favorita», así que **no se toca**, pero queda dicho. |
| G4 | Ningún punto numerado anterior fijaba estos literales (buscado en `_internos_proceso`): no hay contradicción con documentos previos. |

---

## Las tres cosas que hay que decidir

1. **¿Lleva Cancelar el caso 3?** La maqueta del caso 3 enseña la frase y un solo botón «Aplicar», **sin Cancelar**; los casos 2 y 4 sí lo llevan. Y el detalle 5 habla de Cancelar en general.
   *Propuesta:* dejarlo. Es un aviso de borrado y quitarle la salida es peor; además el detalle 5 dice que volver a pulsar «Aplicar» también cierra el aviso, así que salida hay, pero un enlace explícito cuesta nada. **Se implementa con Cancelar salvo que digas lo contrario.**

2. **¿«Este día ya tiene 3 comidas» o «tus 3 comidas»?** La maqueta dice lo primero; el detalle 1 dice «"tus 3 comidas", no "esas comidas"», que es el principio (que se diga el número), no necesariamente el literal.
   *Propuesta:* el literal de la maqueta, que ya lleva el número. **Se implementa así.**

3. **El intra y el post no cuentan en el número.** Es la regla que ya se aplicó el 31-08 al contador de la lista de favoritas, por un fallo que reportó un cliente. Se mantiene, y por eso hace falta el caso borde F1d. **Se implementa así.**

---

## Cómo se comprueba (navegador, no scripts)

Cuenta `clientedemo@test.com` / `demo123`, fechas sueltas de diciembre como en
`_guia/_verificar_favoritas_3108.js`, que ya monta y limpia el escenario.

Los seis estados que hay que fotografiar, a 1280 y a 390:

1. Día vacío + favorita del mismo tipo → se aplica sin aviso.
2. Día vacío + favorita de entreno sobre día de descanso → frase, botón naranja, línea gris «el intra y el post se quitan», botón con borde, Cancelar.
3. Día vacío + favorita de descanso sobre día de entreno → línea gris «se añaden el intra y el post, que tendrás que rellenar», y después de aplicar: peri vacío con sus macros, punto naranja en la pestaña y barra a medias, sin aviso extra.
4. Día con 3 comidas + favorita del mismo tipo → «Este día ya tiene 3 comidas...» y botón «Aplicar».
5. Día con 1 comida + favorita de otro tipo → «1 comida» en singular y las dos frases seguidas, en orden.
6. Día con solo el intra montado + favorita de otro tipo → el caso borde F1d.

Más: Cancelar deja la lista de favoritas abierta; volver a pulsar Aplicar cierra el aviso.

## Lo que dejé como estaba, y por qué (para Francisco)

Al adaptar una favorita de descanso a un día de entreno sigue saliendo el aviso
**«Aplicada "X" adaptada a tu día de entreno, pero 3 comidas se quedan cortas de macros ·
Cuadrar ahora»**. El detalle 3 del documento dice que del día sin cuadrar «no hace falta
avisar aparte», pero ese aviso concreto habla de otra cosa (las cantidades de la favorita no
llegan a los macros de hoy, no el peri vacío) y viene validado del doc 57. **No lo toqué.**
Si quieres que en este camino tampoco salga, es una línea.

## Añadido el mismo 3-09: el fallo del cuadre (las almendras de Francisco)

Al aplicar «dieta 1» la comida quedaba «sobran 4,6 P» y «Cuadrar el día» decía «cuadrado»
sin mover un gramo. TRES causas, arregladas en tres rondas (todo en
`backend/routes/calculator.py`, refit_diet):

1. **Dos motores**: refit calculaba con la regla por categoría a secas y la pantalla con la
   calibración del día. Ahora todo el refit (aportes, mínimos, dimensionado, afinado y los
   macros devueltos) usa la calibración, con el campo nuevo `contexto_dia` para el «Cuadrar»
   de una comida.
2. **El suelo pesable de 20 g** (fallo 29) le prohibía bajar las almendras de 20 cuando 10 g
   cuadraban (Francisco lo hizo a mano). Ahora el pesable manda mientras alcance; si es lo
   único que impide cuadrar, se baja hasta el mínimo del catálogo. Y las bajadas redondean
   al múltiplo MÁS CERCANO (9,4 → 10), no a la baja.
3. **Solo se atendía al macro que MÁS se pasa**: si ese lo arreglaba el dimensionado (la
   proteína), la grasa clavada en los suelos quedaba sin tocar en los caminos de una sola
   llamada (favoritas). Ahora hay un barrido de los macros que sobran por detrás del peor.

4. **El afinado SUBÍA lo que ya venía bien**: su suelo pesable hacía `max(cantidad, 20)` y
   le inflaba a 20 g las almendras que la favorita traía en 10, metiendo grasa que la
   comida no absorbe. Ahora el suelo del afinado nunca sube por encima de la cantidad con
   la que el alimento ENTRÓ (10 g que el cliente ya pesa son pesables).

5. **Las migajas también bajan y la app decide sola cuando no hay pregunta con sustancia**:
   el filtro de 4 g es para la pregunta, no para la bajada proporcional; y cuando
   `hay_que_preguntar` da None con sobra, ahora se baja de verdad (antes se fiaba del
   dimensionado, que solo reparte hacia arriba). El barrido cubre TODOS los macros.

Dos decisiones de Francisco del mismo día:
- **La palabra** (revierte la revisión del 2-09): «cuadrado» solo cuando está exacto;
  dentro del margen, «válido (+2,6)» en verde (la letra del 11.1); fuera, «faltan/sobran».
  En `lib/estadoDelMacro.js` y `BuildMealModal.jsx`.
- **El margen: 1-4 plano en todo** (elegido con el aviso de que el intra 5/9 vuelve a caber
  en él). Fuera el margen proporcional de `lib/exceso.margenDe` y `chatbot.margen_de`, y el
  estrechado por arriba de `comida_cuadrada`.

Y el hallazgo de fondo: **una comida puede NO poder cuadrar bajando** (la C4: los mínimos
curados suman 18 H sobre 10). Ahí la app pregunta «¿qué quito?» y decide el cliente; los
letreros de esa pregunta ya no dicen «lo bajé» sin haber bajado nada.

## Quinta pasada («sigue revisando hasta que quede lo más perfecto posible»)

- **Fronteras del margen alineadas**: con «de 1 a 4 es válido», el 4,0 exacto es válido en
  todos los sitios (`seExcede`, `MealCard`, `getMealStatus`, `BuildMealModal`); el exceso
  empieza pasado el 4. Tests de las libs del front: 34/34.
- **«Repetir un día» se juzgaba contra el día equivocado**: `para` descartaba fechas
  futuras (montar el 21-12 desde el 3-09 etiquetaba contra el descanso del 3-09, todo al
  revés) y en día sin guardar el tipo lo decidían dos reglas distintas (perfil en servidor,
  Entreno en pantalla). Ahora `para` acepta futuro (el techo de la lista sigue siendo hoy)
  y el front manda `tipo_destino` con lo que enseña el selector.
- Verificados en pantalla los caminos restantes: **repetir un día** (etiquetas coherentes y
  el aviso nuevo de «sobra aunque esté todo al mínimo» saliendo solo) y **adaptar
  entreno→descanso** (caso 4 del artifact con sus dos frases; peri fuera; «faltan» en
  blanco donde los topes impiden inflar, que es lo honesto).

Verificado en la pantalla: APLICAR la favorita deja C1 en **49,1 · 30 · 10,3, todo
«cuadrado»**, almendras en 10 g, y el día en 399 «válido (−1)» / 278 «válido (−2)» /
grasa sobran 6 (lo que queda vive en C4 y se dice). Detalle en la memoria
`refit-y-calibracion-dos-motores`.

## Sexta pasada: «úsala tú comida a comida» — echar lo que falta

Recorrida la dieta 1 comida a comida como usuario: el intra quedaba 54/60 H (bebida en
900; a 1.000 clavaba) y el post 134,8/140 (crema en 135). El redondeo siempre-a-la-baja y
los topes congelados dejaban las comidas cortas por menos de un paso, y el motor no tenía
el gesto de la mano: mirar cuánto falta y echarlo. Pase nuevo al final del refit: por
rondas, el macro que más falta elige al alimento que lo lleva y recibe de una vez los
gramos que faltan, redondeados a su paso al más cercano, sin pasar ningún macro de
objetivo+margen y con «pasarse pesa doble» para que el día no acumule los «+3».

Resultado en pantalla: Intra 40/60 EXACTOS, Post 161,2/139,5 cuadrado, C1–C3 verdes; los
«sobran 7» del día son la verdad estructural de C4. Tests: 72/73 del motor en verde — el
único rojo es el caso 32, el INTENCIONADO (contradicción caso 32 vs calibración, decisión
de Jesús pendiente); el caso 31 se actualizó al mecanismo real (macrosLine +
ContadorFamilia, comprobado en pantalla).

## Fichero por fichero

- `frontend/src/components/nutrition/FavoritesModal.jsx` - bloques 1, 2, 3, 6 y la decisión 1.
- `frontend/src/pages/NutritionPage.jsx` - el cálculo del bloque 3, los avisos de G1, y el
  `contexto_dia` del cuadre.
- `backend/routes/calculator.py` - el refit con la calibración del día (el fallo de las almendras).
- `frontend/src/pages/ClientDashboard.jsx` - la línea de la fecha del Inicio, que no se leía.
- `_guia/GUIA-COMPLETA-12EN12.md` - G2.
- `_guia/` - el guion de comprobación y las capturas.
