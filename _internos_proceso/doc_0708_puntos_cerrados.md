# Documento del 7 de agosto - puntos cerrados

Registro de los puntos del documento *"PARA FRANCISCO - Todo lo que hay que hacer"* (7 de
agosto de 2026) que se van cerrando. Por cada uno: qué método se pide, cómo funcionaba antes,
un ejemplo de cada caso y qué queda pendiente si depende de alguien más.

---

## Bloque A - El motor de macros

### Punto 1 - Los escenarios de reparto de hidratos · CERRADO

**Lo que decía el documento.** Un día de entreno con el entreno después de la Comida 1 y 65 g
de hidratos debe repartirlos 22,5 · 22,5 · 10 · 10. La app daba 19 · 19 · 14 · 14, y de ahí la
conclusión de que "los escenarios no se están aplicando".

**Lo que se comprobó.** Los escenarios sí se aplicaban, y las tablas eran correctas. Se
contrastó nuestro `backend/macro_distribution.py` contra la función `pe()` de la calculadora
antigua, extraída del bundle original (`_calma_ref/utils_.ac9d7b60.js`), y coinciden en todo:

- Las tablas de **proteína** y **grasa** por momento de entreno (la `z` de Calma).
- La tabla del tramo **100-150 g** (la `J`: 36 / 18 / 10 / 36 rotada).
- La tabla de **más de 150 g** (la `W`: 30 / 20 / 20 / 30 rotada).
- Los **cinco tramos** de hidratos, incluido el detalle de que por debajo de 30 g todo va a la
  comida de después, y que entre 30 y 50 g los 10 g se asignan por `comida % 4 == momento`
  (lo que hace que entrenando en ayunas esos 10 g caigan en la Comida 4; intencionado y
  confirmado por Jesús el 7 de agosto).
- El perientreno: intra 20 % de la proteína y 30 % de los hidratos, post 80 % y 70 %.
- El día de descanso: todo a partes iguales.

Esa paridad queda fijada en `backend/tests/test_reparto_calma_paridad.py`, que reimplementa
`pe()` de Calma y compara comida a comida en 64 combinaciones (16 valores de hidratos × 4
momentos de entreno), más los cinco tramos con los números del propio documento.

**Cuál era el fallo de verdad.** Estaba en el perientreno, no en las tablas. La app tiene
cuatro modos de peri, y dos de ellos no existen en Calma: `sin_peri` (el cliente no toma nada
en el entreno) y `solo_intra` (solo toma intra). En esos dos modos el presupuesto de peri que
el cliente no se bebe se lo come en las comidas, y **se le sumaba a partes iguales a las cuatro
comidas después de haber repartido**. Ese reparto plano deshacía la forma que acababan de dar
las tablas: cuanto más peri, más se aplanaba el día.

**El arreglo.** Ese presupuesto entra ahora en el total del día **antes** de repartir, así que
el tramo de hidratos y los porcentajes de las tablas se aplican sobre lo que de verdad va a las
comidas. Lo que come el cliente en total no cambia; cambia cómo se reparte.

**El caso del documento, con números.** Cliente con 50 g de hidratos en el día de entreno y
15 g asignados de perientreno (que son, además, los valores por defecto del asistente cuando el
cliente todavía no tiene macros), entrenando después de la Comida 1, en modo "sin peri". El día
tiene 65 g de hidratos en las comidas:

| | Comida 1 | Comida 2 | Comida 3 | Comida 4 |
|---|---|---|---|---|
| Antes | 18,8 | 18,8 | 13,8 | 13,8 |
| Ahora | **22,5** | **22,5** | **10** | **10** |

Los 18,8 y 13,8 son los 19 · 19 · 14 · 14 que vio Jesús en pantalla, y los 22,5 · 22,5 · 10 · 10
son exactamente lo que pide el documento: 65 g está en el tramo de 50 a 100, luego (65 − 20) ÷ 2
para las dos comidas cercanas al entreno y 10 g para las dos lejanas.

En modo "solo intra" el mismo caso pasa de 17,4 · 17,4 · 12,4 · 12,4 a 19,9 · 19,9 · 10 · 10.
En los modos "intra + post" y "solo post" **no cambia nada**, porque ahí el peri va aparte y
nunca tocó las comidas: 15 · 15 · 10 · 10 antes y ahora.

**Dónde está el cambio.** `backend/macro_distribution.py`, en `distribuir_macros`. El reparto
vive en un solo sitio: la pantalla de Nutrición, el asistente y el PDF de la dieta llaman todos
a esta misma función, así que el arreglo llega a los tres a la vez.

**Comprobado en la app.** Con el cliente demo, llamando a `/api/calculator/distribute` con el
backend en marcha. En "sin peri" pasó de 63,5 · 63,5 · 46,5 · 46,5 a 66 · 66 · 44 · 44, que es
el 30 / 30 / 20 / 20 de la tabla de más de 150 g. En "intra + post" siguió dando lo mismo que
antes. Los 52 tests del propio motor, los 24 del perientreno y los 19 de paridad con Calma
siguen pasando, más los 141 nuevos.

**Sin pendientes.** El detalle de los 10 g en la Comida 4 entrenando en ayunas se dejó como
está, por indicación expresa de Jesús.

**En producción desde el 7 de agosto** (commit `c080f07`). Se subió solo `macro_distribution.py`,
que es el único fichero de ejecución que cambia, para no arrastrar el trabajo en curso del
asistente. Comprobado dentro del pod: en modo "sin peri" da 22,5 · 22,5 · 10 · 10 y en
"intra + post" sigue dando 15 · 15 · 10 · 10, y la web y la API responden.

---

## Pendientes que no dependen de nosotros

*(Se irán anotando aquí según aparezcan: decisiones de Jesús, datos que faltan o terceros.)*

Ninguno todavía.
