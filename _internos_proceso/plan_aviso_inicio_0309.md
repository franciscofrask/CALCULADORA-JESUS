# Plan · «Cómo abre Inicio» (Jesús, 3-09-2026)

Artifact: https://claude.ai/code/artifact/865cf38a-1d2b-493a-8abd-8899ebc0d364
Leído entero el 3-09 (pie: «Los colores son los tuyos: verde #22C55E, naranja #FF5A2E.
3 de septiembre de 2026»). Siete bloques. Tema: dónde va el aviso de la dieta sin
terminar, qué sale en cada pestaña de «Tu dieta hoy» y de qué color, «aplicando la regla
que ya estaba escrita, sin inventar ninguna nueva».

Fichero que manda casi todo: `frontend/src/components/inicio/TuDietaHoy.jsx`.
Apoyos: `lib/estadoDelMacro.js` (ya centraliza palabra/color/barra) y quizá
`ClientDashboard.jsx`.

---

## ⚠ EL CHOQUE QUE HAY QUE DECIDIR ANTES DE TOCAR

El doc dice (bloque 01): «Abre en Llevas, como ahora». **Pero desde el 2-09 Inicio abre
en Dieta por decisión de Francisco** (memoria `decisiones-francisco-0209-extras-e-inicio`,
commit fa1b910, EN PROD). Jesús escribió sobre un estado desactualizado (el del doc 1.1
del 1-09). La serie completa de la pestaña de entrada: Macros (27-08) → Llevas (1-09) →
Dieta (Francisco 2-09) → ¿Llevas otra vez? (Jesús 3-09, de pasada).

Ojo: **el bloque 02 entero del doc se disuelve si se mantiene la apertura en Dieta** — su
única pega («el que abre en Llevas y no toca Dieta no ve el aviso, el punto de 7 px es
pequeño») no existe si Dieta es la pestaña de entrada. Abrir en Dieta es MEJOR para el
propósito del propio doc.

**Propuesta**: mantener la apertura en Dieta (decisión de Francisco, posterior y
deliberada; el doc no la está decidiendo, la da por sentada mal) e implementar todo lo
demás. El punto rojo sirve para quien navega a otra pestaña. DECÍRSELO a Jesús.

## La otra discrepancia: la palabra

Las maquetas dicen «cuadrado (+1)» / «cuadrado (+2)» dentro del margen. **La decisión de
Francisco del mismo 3-09 (posterior al artifact) es «válido (+1)»** — cuadrado solo
exacto — y ya está implementada en toda la app. Se implementa con «válido»; la maqueta
quedó desfasada en esa palabra. Decirlo.

---

## Lo que pide, bloque a bloque, contra el código actual

### 01 · El aviso dentro de la pestaña Dieta
- Caja ROJA dentro de la pestaña Dieta: «⚠ Te faltan 12 g de hidratos por meter» +
  botón rojo «Terminarla» + «×». Va ENCIMA de los números de Dieta.
- HOY: no existe ninguna caja; solo el punto naranja en la pestaña (TuDietaHoy:409-413,
  `dieta-no-cuadra`). La línea vieja «A tu dieta le faltan...» se quitó el 2-09.
- El rojo queda FUERA de la regla de colores a propósito: «faltar 12 g no es un estado de
  la dieta, es algo que tienes sin terminar. Otro color, otra cosa.»
- El texto: «Te faltan X g de <macro> por meter» (¿y si faltan varios? el doc solo
  enseña uno; criterio propuesto: el que más falta, como `de_donde_bajo`).

### 02 · El punto de la pestaña: ROJO fuerte, no naranja
- HOY: `bg-orange-400` (TuDietaHoy:412). Cambiar a rojo fuerte (p.ej. `bg-red-500`), que
  no se pierda contra el fondo del selector. Nota: si mantiene la apertura en Dieta, este
  bloque pierde su urgencia pero el cambio de color sigue valiendo.
- Vigilancia que pide Jesús: «si en dos semanas la gente sigue sin cuadrar el día, ahí es
  donde hay que mirar» — apuntarlo como pendiente de observación, no de código.

### 03 · Comportamiento
- «×» quita la caja **por ese día, no para siempre** (persistencia local por fecha, tipo
  `almacenLocal` con clave por usuario+fecha) y **el punto se queda**.
- Al terminar la dieta (los tres dentro del margen): caja y punto desaparecen **solos**.
  (El punto ya lo hace vía `dietaNoCuadra`; la caja heredará la misma condición.)
- Botón **«Terminarla», no «Verlo»**: te lleva a arreglarlo. «Como ya estás en Dieta, te
  baja directo a la comida donde falta» — scroll al desglose por comidas de la pestaña
  Dieta de Inicio, a la primera comida con falta (o a Nutrición con `?comida=` si el
  desglose no identifica cuál falta; mirar qué permite el desglose actual).
- OJO al margen: `dietaNoCuadra` usa hoy `MARGEN = 5` local (línea 368) con `>5`. Tras la
  decisión «1-4 plano inclusivo» de hoy, unificar: fuera el 5 local, usar MARGEN de
  lib/exceso con `> 4`. (Es además coherente con el doc: la caja sale cuando la dieta no
  llega «aplicando la regla ya escrita».)

### 04 · Las barras siguen el estado (punto 83) y el número grande NUNCA se colorea
- Número: YA va en blanco (`text-foreground`, punto 75) ✓ nada que hacer.
- Barra: el color YA se pinta con `fondoDelMacro(lectura.barra.color)` (TuDietaHoy:489)
  — gris por debajo, verde resuelto, naranja pasado ✓. VERIFICAR EN PANTALLA que de
  verdad se ve así (el doc dice «hoy son grises siempre»; si Jesús las ve grises, o mira
  una build vieja o hay un caso en que `barra.color` llega null — comprobar con comidas
  marcadas de verdad, no dar por hecho).

### 05 · Las cuatro pestañas, una a una
- Macros: objetivo, sin color nunca y SIN BARRA → ya (leerMacro vista macros barra null) ✓.
- Dieta: cortos sin color, dentro del margen en verde → ya vía leerMacro ✓ (la palabra
  será «válido (+1)», ver discrepancia).
- Llevas: sin color por debajo, «N comidas marcadas» → ya ✓.
- Falta: «para llegar» y «cuadrado» al llegar (punto 95) → ya ✓ («válido» dentro del
  margen tras el cambio de hoy — coherente con el espíritu).
- Todo esto VERIFICARLO en pantalla pestaña a pestaña, no darlo por hecho.

### 06 · Llevas al final del día
- Al empezar: ceros sin color + «Todavía no has marcado nada. Marca abajo lo que vayas
  comiendo.» → ya existe (TuDietaHoy:423-432) ✓ verificar.
- Al terminar: «ya lo tienes» verde / «válido (+2)» verde / «sobran 11» naranja + barra
  del color → mecánica ya en leerMacro; verificar con un día marcado entero.

### 07 · Las dos de la lista de comidas
- **La línea de las hechas dice QUÉ llevas**: «3 hechas · ocultas — Ver» pasa a
  «3 hechas 151P · 107H · 49G — Ver» (los macros de lo marcado, redondos). HOY: solo
  «· ocultas» (grep «ocultas» en TuDietaHoy, zona del punto 1 del doc 21-08 y
  `verHechas`). El dato ya existe (`llevas` acumulado).
- **La marca del Post**: la barra naranja izquierda sin leyenda pasa a un chip con la
  palabra «AHORA» (naranja, esquina superior izquierda de la tarjeta). HOY: borde/barra
  naranja sin texto. Localizar dónde se pinta la marca de «comida de ahora» en las filas.

### Pie
- Colores de la casa: verde #22C55E, naranja #FF5A2E (ya son los de Tailwind ok/pasado —
  verificar equivalencia de tokens, no hardcodear).

---

## Orden de trabajo propuesto

1. Preguntar/confirmar con Francisco el choque de la pestaña de entrada (Dieta vs
   Llevas). Implementar mientras con Dieta (su decisión).
2. La caja roja + «Terminarla» + «×» por día + punto rojo (bloques 01-03), con el margen
   unificado a `> MARGEN`.
3. Bloque 07 (línea de hechas con macros + chip AHORA).
4. Verificación en pantalla de 04/05/06 (que ya deberían cumplirse) con capturas, y
   arreglar lo que no cumpla.
5. Tests: los de `estadoMacros`/`exceso` ya corren; añadir el caso del aviso si hay
   fichero de tests de Inicio; capturas 1280 + 390.

## Estado

**Bloques 01, 02 y 03 HECHOS Y COMPROBADOS** (commit `959f198`, en GitHub sin desplegar).
El **07 queda pendiente** por decisión de Francisco. Lo mide, punto por punto,
`node _guia/_probar_como_abre_inicio.js`: **16 de 18**, y los 2 que faltan son el 07.

- [x] 01 · La caja roja dentro de Dieta, con «Terminarla» y la «×».
- [x] 02 · El punto de la pestaña en rojo (`bg-red-500`), blanco sobre la pestaña activa.
- [x] 03 · La «×» se lleva la caja y deja el punto, y solo por ese día; «Terminarla» lleva
      a la primera comida corta; al cuadrar, caja y punto se van solos.
- [x] El margen local de 5 g, fuera: ahora el `MARGEN` de `lib/exceso`.
- [x] 04, 05 y 06 · Ya se cumplían, y se comprobó en pantalla en vez de darlo por hecho:
      número siempre en blanco, barras gris/verde/naranja según el estado (verde
      `rgb(34,197,94)` = #22C55E y naranja `rgb(255,90,46)` = #FF5A2E, los del pie de su
      documento), las cuatro pestañas con su palabra, y Llevas al empezar y al llegar.
- [ ] 07 · La línea de las hechas con sus macros y la marca de la fila.

### Tres cosas que decidió Francisco al cerrarlo

1. **Se mantiene la apertura en Dieta.** Medido: abre en Dieta. Con eso el bloque 02 pierde
   su pega (nadie se queda sin ver el aviso), pero el punto en rojo se hace igual.
2. **«válido», no «cuadrado»**, dentro del margen. Sus maquetas dicen «cuadrado (+1)» y la
   decisión del mismo 3-09 es posterior.
3. **El 07 espera**, y hay un motivo que decirle: esa barra naranja **no marca «la comida de
   ahora», marca el peri**, y la llevan DOS filas a la vez (el intra y el post). Llamarla
   «AHORA» sería mentir; si lo que quiere es la palabra, la palabra es otra.

### Una que salió al hacerlo

El número del aviso tenía que salir de **los números que él lee**, no del desvío exacto:
con 193,4 de 200,9 el desvío redondea a 8 y debajo pone «faltan 7». Es la regla del punto
80, la que ya cumplía `leerMacro`, y el aviso se la había saltado. La prueba lo caza en ese
medio gramo a propósito.
