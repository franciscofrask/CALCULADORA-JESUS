# Nutrición, parte 3 (puntos 105 al 119) - plan por fases

Fuente: artifact «Para el equipo · parte 3», cerrado el 25 de agosto.
Son 15 puntos (105 a 119) sobre **la pantalla de Nutrición**, y siguen la numeración de la
parte 2, que terminó en el 104.

**La regla que ordena la pantalla, con sus palabras:**

> Inicio es cómo vas. Nutrición es lo que llevas creado.
> Cada pantalla enseña un solo número y siempre el mismo.

Y una frase que ahorra media fase: **«el color, el margen de 4 y las palabras son los
mismos de la parte 2»**. O sea que `frontend/src/lib/estadoDelMacro.js`, que se escribió
para el Inicio, es también el de aquí.

## Dónde cae todo

| Fichero | Qué tiene |
|---|---|
| `frontend/src/pages/NutritionPage.jsx` (2.963 líneas) | la pantalla entera: cabecera, botonera, montaje de la lista |
| `frontend/src/components/nutrition/DayHeader.jsx` | los tres números, el titular que cambia solo, y 3 de las 5 líneas que se van |
| `frontend/src/components/nutrition/MealCard.jsx` (771) | la tarjeta de cada comida: nombre, macros, estado |
| `frontend/src/lib/estadoDelMacro.js` | la regla de color de la parte 2, ya escrita |
| `frontend/src/lib/exceso.js` | `MARGEN = 4` y `margenDe()` |

## Lo que hay que saber antes de empezar

**Hoy conviven CUATRO vocabularios de estado en esta pantalla**, y esa es la razón de
fondo de casi todo lo que Jesús señala:

1. `getMealStatus` / `getDayStatus` (`NutritionPage.jsx:1104` y `:2260`) - margen `margenDe()`
2. `estadoDeLaComida` (`MealCard.jsx:32`) - los textos «Te falta» / «Cuadrada»
3. `macroState` (`MealCard.jsx:155`) - por macro, y aquí **quedarse corto se pinta ROJO**
4. Los **4 g escritos a mano** dentro de `DayHeader.jsx:175, 244, 292`

Más dos librerías paralelas que esta pantalla no usa (`estadoMacros`, `estadoDelMacro`).
El punto 116 es, de hecho, la orden de unificarlos.

**Y el amarillo se va de la app** (punto 116). Hoy hay tres:
`text-amber-*` del «Te falta» (`MealCard.jsx:46`), el punto `bg-amber-400`
(`DaySummary.jsx:31`) y el candado del volcado (`MealCard.jsx:475`). Los dos primeros son
estado y se van; **el candado NO es estado**, así que ese se queda salvo que él diga.

---

# FASE 1 · Una sola pestaña: Dieta (105, 106, 107, 108)

Es la regla de fondo, y de ella sale el sitio para lo demás.

**Qué pasa hoy.** El titular de arriba lo decide `DayHeader.jsx:179-181` y **cambia solo**:
`cuadrado ? 'Día cuadrado' : nadaPuesto ? 'Hoy tienes que comer' : pasado ? 'Te has
pasado' : 'Te queda por comer hoy'`. Cuatro frases distintas en el mismo hueco, y ninguna
dice cuál de los cuatro números estás mirando. Además ese titular es **solo móvil**
(`lg:hidden`), y el escritorio enseña otra cosa completamente distinta: tres barras de 1 px
con «Te faltan N de X» (`DayHeader.jsx:284-320`).

**Qué se hace**
- **105**: fuera cualquier resto de las cuatro vistas en esta pantalla. Las pestañas de
  verdad no están aquí (viven en Inicio), pero sí está el `VistaComidasSelector` (Lista y
  detalle / Pestañas / Todo seguido), que es otra cosa: **eso no lo toca el punto**, y se
  queda. Lo que hay que comprobar es que no queda ningún cambio de criterio.
- **106**: un solo número, siempre **Dieta**: lo que llevas creado, haya día o no. Fuera
  el titular que rota.
- **107**: los números, grandes como en Inicio (mismo tamaño y mismo estirado: la clase
  `.numero-grande` de `index.css` y `text-[34px] sm:text-[40px]`). Debajo, **«Lo que llevas
  creado»**. Cabe porque se quitan las pestañas y el interruptor.
- **108**: aquí el peri **no lleva interruptor**. Ya sale en la lista como una línea más
  («Post · 40 · 50»), y verlo dentro o fuera es una pregunta de Macros, que está en Inicio.

**Riesgo:** medio-alto. Hay que unificar la versión móvil y la de escritorio del bloque de
números, que hoy son dos diseños distintos.

---

# FASE 2 · Las comidas de la lista (114, 115, 116, 117)

El grueso, y donde se reutiliza el motor de la parte 2.

**Qué pasa hoy**
- El nombre se corta a «COMID…» por el `truncate` de `MealCard.jsx:469` con `text-2xl` en
  móvil, compitiendo en el mismo flex con el estado, el Auto/Manual (`:503`) y el chevron.
- Y **desaparece del todo** cuando la comida se pasa: `excesoTapaElNombre`
  (`MealCard.jsx:363`) le mete un `hidden lg:block`, y en el móvil queda solo el cuadrito
  «C1». Eso es lo que Jesús ve como «tres de cada cuatro salen sólo con el cuadrito».
- Los macros llevan letras y decimales: «52,5P · 10H · 15G» (`MealCard.jsx:536-544`).
- El estado sale en amarillo y **no dice ni de qué ni cuánto**: «Te falta», a secas
  (`MealCard.jsx:46` y `:495`).

**Qué se hace**
- **114**: todas con su nombre, siempre, también cuando se pasa. Hay que sacar el
  Auto/Manual de esa línea o bajar el tamaño del nombre en móvil.
- **115**: «53 · 10 · 15». Es el mismo `lineaMacros` que ya se escribió en Inicio: se sube
  a un sitio común y se usa en los dos.
- **116**: el estado, con **punto y palabra**, y con el vocabulario de la parte 2:
  `● cuadrada` verde · `● válido +2` verde · `● sobran 6 de grasa` naranja ·
  `● sin crear` naranja. Fuera el amarillo. Aquí entra `lib/estadoDelMacro`.
- **117**: la comida sin crear, **naranja entera**. «Lo que te pide algo se ve, lo que ya
  está se apaga», igual que en Inicio.

**Riesgo:** alto. `MealCard` la usan cinco montajes distintos (acordeón móvil, detalle de
escritorio, columna lateral, pestañas y continua), así que hay que mirar los cinco.

---

# FASE 3 · Las líneas que se van (109, 110, 112, 113)

Cuatro de las cinco. La quinta (111) va aparte porque no se borra: se muda.

- **109** · «Ya tienes cubiertos los hidratos y la grasa» → fuera.
  `DayHeader.jsx:230-255`. Los dos números ya salen en verde con «cuadrado» debajo.
- **110** · «perientreno 38/40P · 52/50H» → fuera. `DayHeader.jsx:359-363`. El peri ya
  está en la lista de comidas.
- **112** · «Cada alimento muestra lo que dice su etiqueta…» → fuera, **y con ella
  Método/Reales**. El aviso es `ModoMacros.jsx:79-84`; el selector,
  `NutritionPage.jsx:2595` (móvil) y `:2730` (escritorio); el ajuste se guarda en
  `localStorage` y en la ficha (`ajustesEnFicha.js`). **Ojo: quitar el ajuste toca la
  ficha del usuario**, no solo la pantalla.
- **113** · «4 comidas · tras comida 3 · solo post» → **se queda**, pero dentro del `···`.
  Hoy es un botón (`DayHeader.jsx:261`, y su gemelo de escritorio en `:138`).

**Riesgo:** bajo, salvo el 112, que es el único que se lleva una funcionalidad por delante.

---

# FASE 4 · El aviso de ficha, a Mi perfil (111)

«Macros provisionales · nos falta tu altura y revisa tu edad: el valor guardado no puede
ser» (`DayHeader.jsx:327-335`, la frase la arma `lib/datosDudosos.js:14`).

Son tres líneas de un problema de ficha metidas en la pantalla de comer. Se va a **Mi
perfil**, y en el menú queda **un punto naranja** para que se vea que hay algo pendiente.

Esto no es borrar: hay que llevar el aviso a `ProfilePage` y encender un distintivo en la
navegación (`BottomNav` y la barra lateral).

**Riesgo:** medio. Toca navegación, que es de todas las pantallas.

---

# FASE 5 · La cabecera, en dos botones (119)

**Qué pasa hoy** (`NutritionPage.jsx:2561-2588`): en escritorio hay cinco botones (PDF,
Copiar, Favoritas, Preferencias y el engranaje solo en <1024), y en móvil desaparecen
justo **PDF y Copiar** (`hidden sm:inline-flex`), que son los que se usan. Reaparecen
abajo del todo, después de las comidas (`renderActions()`, `:2507`), donde no los ve nadie.

**Qué se hace**: **PDF fuera y el resto dentro del `···`**, igual en móvil y en escritorio.
El menú `···` **no existe hoy** (no hay `MoreHorizontal` en toda la pantalla): hay que
hacerlo, y ahí caen Copiar, Favoritas, Preferencias, el resumen de configuración (113) y
lo que quede del engranaje.

**Riesgo:** bajo-medio. Es un componente nuevo, pero aislado.

---

# FASE 6 · Los suplementos, debajo de su comida (118)

**Es el mismo punto 99 de la parte 2, que quedó bloqueado.** Aquí lo repite con la misma
regla: «+ Creatina en la suya, + Omega 3 · NAC en la suya. El intra y el post no llevan».

Sigue sin existir el dato: no hay ningún campo que cuelgue un suplemento de una comida, ni
en Nutrición ni en Inicio ni en el backend. Con el vínculo decidido, se pinta en las dos
pantallas de una vez.

**Riesgo:** medio, y **bloqueada por decisión**.

---

# Lo que hay que preguntarle a Jesús

1. **El 112 se lleva Método/Reales entero.** El punto dice «fuera, con Método / Reales».
   Confirmar que quiere quitar el ajuste, no solo el aviso: hoy se guarda en la ficha del
   cliente y algunos lo tendrán puesto en «reales».
2. **El amarillo del candado.** El 116 dice que el amarillo desaparece de la app. Hay tres
   amarillos y dos son estado (se van), pero el tercero es el **candado del volcado**
   (`MealCard.jsx:475`), que no es estado. Doy por hecho que ese se queda.
3. **«Sin crear» en naranja** (116) confirma la regla que Francisco cerró el 26-08: por
   debajo también pinta naranja. Encaja, pero conviene decírselo.
4. **Suplementos (118 y 99)**: quién decide qué suplemento va en qué comida.

# Notas

- El punto 116 obliga de hecho a **unificar los cuatro vocabularios de estado** de esta
  pantalla en `lib/estadoDelMacro`. Eso es lo que hace la fase 2 grande, y es también lo
  que evita que la próxima pantalla vuelva a inventarse el suyo.
- `components/nutrition/MacroProgressBar.jsx` es **código muerto**: no lo importa nadie.
  Se puede borrar de paso.
- El artifact dice «las siete líneas de texto que se van» y luego enumera cinco puntos
  (109 a 113). Las cinco están localizadas; si él contaba siete es porque el aviso de
  macros provisionales ocupa tres renglones en el móvil.
