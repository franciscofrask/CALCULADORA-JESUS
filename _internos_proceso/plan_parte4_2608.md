# Parte 4 (puntos 120 al 143) - plan por fases

Fuente: artifact «Para el equipo · parte 4», cerrado el 26 de agosto. Son **24 puntos**
(120 a 143) y siguen a la parte 3, que terminó en el 119. Tres pantallas distintas:

| | Puntos | Dónde |
|---|---|---|
| Dentro de una comida | 120-129 | `components/nutrition/MealCard.jsx` (la tarjeta abierta) |
| La calibración progresiva | 130-136 | `ContadorFamilia.jsx` + `backend/calibracion_dia.py` + datos |
| El buscador de alimentos | 137-143 | `pages/FoodSearchPage.jsx` + `backend/routes/calculator.py` |

**La regla de color no cambia**, y lo dice él mismo. Lo único que cambia:

> Dentro de una comida **sí van decimales**, arriba y abajo. Es la pantalla donde se afina.
> En el resto de la app, redondos.

Y el corte de abajo (punto 122): **por debajo de 1 g la palabra es «cuadrado»**.
Su tabla, literal: `0 → cuadrado · −0,2 → cuadrado · −0,7 → cuadrado · −1,4 → válido −1,4 ·
+2,3 → válido +2,3 · −4,5 → faltan 4,5`.

Eso se resuelve en `lib/estadoDelMacro`, que ya existe de la parte 2: hay que añadirle un
modo «dentro de la comida» con decimales y con el suelo de 1 g. Un sitio, no cinco.

---

## Lo que hay que saber antes de empezar

**Tres cosas que no son de diseño y que él encontró probando.** Van marcadas abajo:

- **135** · el buscador de dentro de la comida **no aplica la calibración**, así que el
  número que ves al elegir no es el que queda. Confirmado en el código: ni
  `GET /calculator/search` ni `POST /calculator/macros-efectivos` reciben el acumulado del
  día; la calibración llega después, cuando `NutritionPage` reenvía el día a
  `POST /calculator/calibrar-dia` y **sobrescribe** lo que ya se había pintado.
- **136** · hay **datos del catálogo que se contradicen** (cacahuete natural genérico dice
  una cosa y el de Hacendado otra, y los dos pasan el tercio). Eso no lo arregla ningún
  texto: es limpieza de `db.foods`.
- **129** · **Vaciar y la papelera no preguntan**. La papelera además **no ofrece
  deshacer**, mientras que «Vaciar», que es más destructivo, sí lo ofrece durante 8 s. Y
  hay un tercer camino que borra sin avisar: bajar la cantidad por debajo del mínimo
  (`NutritionPage.jsx:1404`).

**Y una nota suya que no es código:** el punto 132 dice que **el manual técnico está mal**
(dice que las comidas anteriores no se recalculan, y sí se recalculan). Hay que corregir el
manual, no el código.

**Tres vocabularios para lo mismo.** «Su proteína te cuenta a la mitad»
(`ContadorFamilia`), el toast de cruce de tramo (`NutritionPage.jsx:1191`) y «Su proteína
no te cuenta» (`calculator.py:321`, y solo sale en el Buscador). Los puntos 133 y 134
obligan a unificarlos.

---

# FASE 1 · Los números de la comida (120, 121, 122, 123)

**Qué pasa hoy.** El desglose por macro existe y está bien calculado, pero vive **detrás de
un «ver detalles» en gris** (`MealCard.jsx:245-248`, `lg:hidden`): en el móvil está oculto
por defecto. Y lo que enseña es `54/63,5 g` con un chip al lado, no el formato de los demás
números de la app.

**Qué se hace**
- **120**: que salga **siempre**, con el formato de la casa: número, punto, palabra y barra.
  Fuera «ver detalles». Y con eso se va el estado agregado de la cabecera cuando la comida
  está abierta: para saber qué falta ya no hay que sumar cuatro líneas de cabeza.
- **121**: **decimales aquí**, arriba y abajo: `30,5 · 11 · 6,5` y `faltan 4,5`.
- **122**: por debajo de 1 g, «cuadrado». Un modo nuevo en `lib/estadoDelMacro`.
- **123**: el objetivo se queda arriba, pequeño: `Objetivo · 35 · 10 · 15`. Es la única
  referencia fija de la pantalla. (Ya está así desde la parte 3; hay que comprobarlo.)

**Ficheros:** `MealCard.jsx`, `lib/estadoDelMacro.js`.
**Riesgo:** medio. Toca el mismo motor que Inicio y la cabecera de Nutrición, así que el
modo nuevo tiene que ser explícito y no cambiar a los que ya lo usan.

---

# FASE 2 · Los controles de la comida (124, 125, 126, 127, 128)

Hoy hay **cinco controles a la vista**: Automático/Manual, ver detalles, Cuadrar, la
estrella y Vaciar.

- **124** · «Modo de cálculo» pasa a **«Ajuste de cantidades»**, con la etiqueta encima y
  `[Automático] [Manual]` debajo, como Entreno/Descanso. Y la frase que lo explica -- «Yo te
  ajusto las cantidades» -- **hoy solo se ve en escritorio** (`MealCard.jsx:608`, `lg`): esa
  era la explicación buena y la tapaban dos palabras de jerga.
- **125** · **Cuadrar**, ancho, en naranja, y con la frase debajo:
  «Te ajusto las cantidades sin pasarme de tus macros.»
  **Ojo:** él dice que esa frase «ya existe, es la del ratón encima». No es exacto: el
  `title` de hoy (`MealCard.jsx:783`) dice «Ajustar las cantidades a tus macros sin pasarse
  (respetando el mínimo de cada alimento)». La frase que él escribe **hay que escribirla**,
  y es mejor: está en primera persona y no habla de mínimos.
- **126** · La flecha de subir, la estrella y Vaciar, **dentro de un «···»** con tres
  entradas: Ordenar los alimentos · Guardar como favorita · **Vaciar la comida, en rojo**.
  Al tocar «Ordenar» aparecen las flechas y una barra naranja con **Listo**.
  El `MenuDeLaPantalla` de la parte 3 sirve casi tal cual; hay que añadirle el tono rojo
  para la entrada destructiva.
- **127** · La leyenda queda en **«−/+ = gramos»**. Fuera «↑ = prioridad», que hace pensar
  que Cuadrar reparte por ese orden, y no es verdad. Y fuera el número (1, 2, 3, 4) de
  debajo de cada flecha (`MealCard.jsx:317`).
- **128** · La flecha del primer alimento, apagada. **Esto ya está hecho**
  (`MealCard.jsx:313`, `disabled={idx === 0}` con `opacity-20`). Hay que comprobar en
  pantalla que se ve apagada de verdad: él dice que no.

**Ficheros:** `MealCard.jsx`, `MenuDeLaPantalla.jsx`.
**Riesgo:** medio. El modo «ordenar» es estado nuevo dentro de la tarjeta.

---

# FASE 3 · Vaciar y la papelera preguntan (129)

Pequeña, pero es la única que **protege datos**, así que va sola y pronto.

Hoy: la papelera borra un ingrediente **sin preguntar y sin deshacer**
(`NutritionPage.jsx:1482`); «Vaciar» no pregunta pero deja «Deshacer» 8 s
(`NutritionPage.jsx:1508`); y bajar la cantidad por debajo del mínimo **también borra**, sin
avisar (`NutritionPage.jsx:1404`).

Las dos que él nombra tienen que preguntar. El tercer camino no lo nombra: lo dejo escrito
para preguntárselo.

**Riesgo:** bajo.

---

# FASE 4 · Lo que dice la calibración (133, 134)

El cálculo **está bien y no se toca**: lo comprobó alimento por alimento. Lo que miente es
el cartel.

- **133** · Hoy el cartel le sale **a todos los frutos secos por igual**, aunque no pasen la
  puerta del tercio: las nueces (23 %) dicen «te cuenta entera» y aportan 0. Que salga
  **solo en los que llegan al tercio**. A los demás, una frase y para siempre: **«su
  proteína no te cuenta»**.
  La puerta ya existe en el backend (`calibracion_dia.py:128-137`), pero **el front no la
  conoce**: `ContadorFamilia` solo recibe `bloque` y `gramos`. Hay que hacer que el backend
  diga también si ese alimento **pasa el tercio**, y pintarlo con eso.
- **134** · Al que sí llega, decirle lo que gana. Hoy «te cuenta a la mitad» suena a castigo
  y no dice qué hacer. Queda:
  - `su proteína todavía no te cuenta · con 20 g te cuenta la mitad`
  - `vas por la mitad de su proteína · con 40 g te cuenta toda`
  - `te cuenta toda su proteína`
  Y **fuera el «X de Y g»**: la maqueta ya no lo lleva.

**Ficheros:** `ContadorFamilia.jsx`, `backend/routes/calculator.py` (el campo nuevo),
`backend/calibracion_dia.py` (exponer el tercio).
**Riesgo:** medio. Toca el contrato front-backend, pero no el cálculo.

---

# FASE 5 · El buscador de alimentos (137, 138, 139, 140, 141, 142, 143)

- **137** · Arriba quedan **tres líneas**: la de siempre, una nueva que explica qué es un
  genérico -- «hoy no se dice en ningún sitio» -- y la de la calibración con sus tramos. Y
  **sale** «Ordenados por coincidencia con el nombre»: es verdad, pero nadie entra a buscar
  preguntándose el criterio de ordenación.
- **138** · Abajo, **solo un punto delante del nombre** en los que dependen de la cantidad.
  Cero texto añadido por alimento. Hoy los tres se ven igual.
- **139** · La ficha de los que llevan punto **se acorta**: «Te cuenta grasa» a secas. Deja
  de decir algo que solo es cierto si comes menos de 20 g. Toca `_que_te_cuenta`
  (`calculator.py:321-344`), que hoy añade las exclusiones siempre.
- **140** · **Al abrir el alimento, los tres tramos**, con el activo marcado.
  **Hoy no se puede abrir un alimento**: `FoodRow` no tiene `onClick` ni detalle ni modal.
  Hay que hacerlo.
- **141** · Lo que no se toca: «Te cuentan los tres» · «Su proteína no te cuenta» · «No te
  cuenta nada: come lo que quieras».
- **142** · **«En la etiqueta pone…» pasa a «Macros reales»**. Un genérico no tiene
  etiqueta: esos números salen de tabla de composición. Y se acorta a
  `Macros reales · 23 P · 4,8 H · 53,1 G`.
- **143** · Y el número de arriba pasa a llamarse **«Macros del método»**. Con eso cada
  alimento enseña sus dos números y dice cuál es cuál. Su regla, en una línea:
  > Donde hoy no pone nada, pone **Macros del método**. Donde hoy pone «En la etiqueta
  > pone», pone **Macros reales**. Y si de un alimento no tenemos los tres números, esa
  > segunda línea no aparece.

**Ficheros:** `FoodSearchPage.jsx`, `backend/routes/calculator.py`.
**Riesgo:** medio-alto. El 140 es pantalla nueva y el 139 toca un texto que hoy fijan tres
tests (`test_casos_E_motor_macros.py:187, 282, 316`).

---

# FASE 6 · Los dos hallazgos que no son de texto (135, 136)

Van juntas al final porque las dos son de fondo y ninguna es de diseño.

- **135** · **El buscador de dentro de la comida no aplica la calibración.** Añades 100 g de
  almendras y la proteína no se mueve; al guardar, pasa a contar los 23 g. Hay que pasarle
  el acumulado del día al modal y calcular con tramo, o avisar en el propio modal de que ese
  número va a cambiar. Es lo que la «puerta del autoajuste» de `MealCard` intenta explicar
  **a posteriori**: mejor no tener que explicarlo.
- **136** · **Datos contradictorios en el catálogo.** Cacahuete natural (26/52, 50 %) dice
  «ni su proteína ni sus hidratos te cuentan» y el de Hacendado (24,1/45,1, 53 %) dice «te
  cuenta proteína y grasa». Los dos pasan el tercio. Hay que **buscar todos los casos**, no
  solo esos dos, y arreglarlos en `db.foods` de producción con backup.

**Riesgo:** el 135, alto (toca el cálculo en vivo). El 136 es limpieza de datos en
producción, con backup y permiso.

---

# Lo que hay que preguntarle a Jesús

1. **El tercer camino que borra sin avisar** (129): bajar la cantidad por debajo del mínimo
   elimina el alimento. Él nombra Vaciar y la papelera. ¿Ese también pregunta?
2. **«Ver detalles» desaparece** (120), y con él desaparece en escritorio la única forma de
   ver `servido / objetivo` por macro. ¿Se pierde ese par de números o se queda en alguna
   parte?
3. **El punto del 138**: ¿el mismo naranja de «te has pasado» o uno propio? En su maqueta el
   punto de la lista es del color de acento.
4. **Los suplementos por comida** (118 y 99) siguen sin decidir de la parte 3.

# Notas

- La frase del 125 **no existe hoy** en el repo, aunque él diga que es la del ratón encima.
  Hay que escribirla tal cual la escribe él.
- El 128 (flecha del primero apagada) **ya está implementado**; lo que falla es que a
  `opacity-20` no se le ve apagada. Es cuestión de contraste, no de lógica.
- El botón se llama hoy **«Sugerir alimento»** y en su maqueta aparece como «Solicitar
  alimento» en un sitio y «Sugerir alimento» en otro. No hay punto numerado que lo cambie:
  se queda como está.
- «0 alimentos» **nunca se muestra** hoy (el recuento solo se pinta si hay resultados) y el
  vacío dice «Sin resultados», no «No se encontraron alimentos». Su maqueta propone un vacío
  más largo, pero tampoco hay punto numerado: se queda.
