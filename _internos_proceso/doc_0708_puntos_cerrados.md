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

### Punto 2 - Los tres avisos sobre el código antiguo · CERRADO

Este punto no pedía construir nada: avisaba de tres defectos del código de la calculadora
antigua para que no se copiaran. Lo que se hizo fue comprobar, uno a uno, si se nos habían
colado, y blindar el nuestro para que no vuelvan a entrar.

**Aviso uno: el objeto de constantes que se escribe encima.** En el código antiguo,
`getMealsPortions` escribía sobre el propio objeto de porcentajes, así que una llamada se
llevaba lo que había dejado la anterior. Nuestro reparto no hace eso: las tablas son de solo
lectura y cada llamada construye su resultado desde cero. Queda fijado con dos tests nuevos, uno
que comprueba que dos llamadas iguales dan lo mismo aunque se intercale otra distinta, y otro
que verifica que las tablas siguen intactas después de recorrer todos los tramos y momentos.

Sobre el mismo patrón se auditó el resto del backend, porque el sitio donde de verdad podía
mordernos es el catálogo de alimentos: está cacheado en memoria y el motor le anota campos
encima. Ahí ya estaba resuelto: `get_all_foods_cached` devuelve una copia por petición.

**Aviso dos: la tabla por defecto que no cuadra** (133 % de hidratos y 80 % de grasas en el
código antiguo). No se copió, y ahora hay un test que recorre nuestras dos tablas y comprueba
que las tres columnas suman 100 % en los cuatro momentos de entreno. No tenemos ningún reparto
por defecto equivalente al suyo: el único valor de arranque que manejamos es el presupuesto de
perientreno de 35 P / 15 H, que sí se usa a propósito cuando el cliente todavía no lo tiene
asignado.

**Aviso tres: las funciones llamadas `unknown`.** No las podemos leer: de la calculadora
antigua solo tenemos el bundle compilado en `_calma_ref/`, no el repositorio fuente
(`jgl-calma-web-next`) donde alguien las dejó a medio desminificar. Sí se pudo identificar qué
hay en esa zona del código, y son cuatro funciones de composición corporal que proyectan, semana
a semana y en tramos de cuatro semanas, cuánta masa grasa y cuánta masa libre de grasa cambia
según el punto de partida de grasa corporal, más una que responde a si un objetivo de peso es
alcanzable en un plazo dado. **Nosotros no tenemos eso**: calculamos la composición de hoy
(`target_calculator.py`), pero no la proyección ni la validación del objetivo. Queda anotado
abajo como decisión, no como fallo, porque nadie ha pedido esa funcionalidad.

**De propina, un fallo que apareció mirando esto.** El momento de entreno indexa las tablas
directamente, así que cualquier valor fuera de 0 a 3 rompía el reparto con un error, y eso
llega a la pantalla de Nutrición como todos los objetivos por comida a cero. Ahora un valor
que no existe cae en "después de la Comida 1", que es el que ya asumían todas las rutas, y la
configuración devuelta dice cuál se usó de verdad. Con test.

---

## Pendientes que no dependen de nosotros

*(Se irán anotando aquí según aparezcan: decisiones de Jesús, datos que faltan o terceros.)*

**No tenemos el repositorio fuente de la calculadora antigua** (`jgl-calma-web-next`). En
`_calma_ref/` solo está el bundle compilado, que sirve para contrastar comportamiento pero no
para leer el código como lo describe el documento (nombres de fichero, números de línea y las
funciones a medio desminificar). Si Jesús quiere que revisemos algo concreto de ese código, hace
falta acceso al repositorio. Hasta ahora no ha hecho falta: el reparto se pudo portar y validar
contra el bundle.

**La proyección de composición corporal del código antiguo no está en nuestra app.** Calma
tiene un modelo que estima, semana a semana y por tramos de cuatro semanas, cuánta masa grasa y
cuánta masa libre de grasa cambia según el punto de partida, y con él valida si un objetivo de
peso es alcanzable en un plazo. Nosotros solo calculamos la composición actual. **Decide Jesús**
si eso debe existir en la app nueva; encajaría en el bloque H, que es de después del lunes.
