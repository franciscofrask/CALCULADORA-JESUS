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

### Punto 3 - La regla del tercio va ANTES de calibrar · CERRADO

**Lo que se pide.** La proteína del cereal o del pan solo cuenta si supera un tercio de sus
hidratos; la de los frutos secos, solo si supera un tercio de su grasa. Ese filtro se decide
antes de aplicar la calibración del día, no después.

**Cómo estaba.** El orden ya era el correcto dentro del motor de calibración
(`backend/calibracion_dia.py`): el tercio se mide sobre los macros por 100 g del alimento, que
no dependen del tramo, y solo después se aplica el 0 / 50 / 100 % del acumulado del día. Se
comprobó con números: unas almendras de 21 g de proteína y 54 de grasa pasan el filtro
(21 > 18) y en el tramo del 50 % dan 10,5 g de proteína. Si el orden estuviera invertido, se
calibraría primero a 10,5 y luego se preguntaría si 10,5 supera 18, que no, y la proteína caería
a cero. Esa es exactamente la diferencia que avisaba el documento.

**Lo que sí había que arreglar: el orden se podía romper desde fuera.** El filtro se medía
sobre el alimento tal y como llegara, y hay otra regla en la app, heredada de la calculadora
antigua, que pone a cero los macros que no cuentan según *su* criterio, que no es el mismo. Las
dos no coinciden: se compararon sobre el catálogo entero y **discrepan en 69 alimentos** (39
cereales y panes, 30 frutos secos). Con las almendras, por ejemplo, la regla heredada pone la
proteína a cero y el criterio de Jesús la deja contar. Así que si alguien pasaba a la
calibración un alimento por el que ya había pasado esa regla, el tercio leía un cero y la
proteína se perdía. Se verificó que ocurría: las almendras pasaban de 21 g de proteína a 0.

Ahora la regla heredada guarda los macros de etiqueta antes de tocar nada, y la calibración
mide el tercio sobre esos. El resultado es el mismo llegue el alimento crudo o ya procesado, así
que el orden ya no depende de que cada llamador acierte. Queda fijado con tests.

**Comprobado en la app real**, con el navegador y la app en marcha: al añadir 22 g de almendras
crudas a la Comida 1, la ficha del alimento muestra sus 5,1 g de proteína de etiqueta y la
comida cuenta 2,5 g, que es la mitad, porque 22 g de frutos secos caen en el tramo del 50 %.
Es decir, el filtro se pasó primero y el tramo escaló después. Si el orden estuviera invertido,
la comida contaría 0.

**Una cosa que conviene saber, aunque no es un fallo.** Mientras se está montando la comida, el
buscador enseña los macros con el criterio heredado (a las almendras les pone 0 de proteína),
y al guardar pasan a contar 2,5 g. El buscador no conoce el acumulado del día hasta que el
alimento aterriza en una comida, así que ese salto es esperable, pero al cliente le puede
chocar ver un número en el buscador y otro distinto un segundo después.

**Y una grieta que se cerró de paso.** La calibración la hace el servidor, y la pantalla la
pedía tras cada cambio; si esa llamada fallaba, se conservaban los macros anteriores **sin
avisar de nada**, y esos números sin calibrar son los que se guardan y los que salen en el PDF.
Ahora se reintenta una vez y, si aun así falla, sale un aviso en la barra de estado que permite
reintentar a mano.

---

### Punto 4 - Redondear las cantidades a múltiplos · CERRADO

**Lo que se pide.** Los números que se le dan a un cliente son redondos: unidades enteras o
medias, verduras y bebidas vegetales de 50 en 50, salsas y todo lo demás de 5 en 5, y los
macros del día con la proteína y la grasa enteras y los hidratos de 5 en 5. Redondeando al
salir, no durante el cálculo.

**Cómo estaba.** Había tres criterios de redondeo distintos conviviendo, y ninguno hacía lo
que pide Jesús:

- El del buscador, heredado de la calculadora antigua, que sí redondea las verduras y las
  bebidas vegetales de 50 en 50 y las salsas de 5 en 5 (eso ya coincidía), pero para todo lo
  demás usa un paso de **1 gramo**. De ahí los 223 g de pechuga y los 42 g de proteína en polvo.
- El de los menús del recetario, con otra tabla propia (pan de 10 en 10, carnes de 25 en 25,
  huevos de 55 en 55).
- El afinado fino que cuadra los menús, que no redondea nada y dejaba los 182,5 · 120,1 · 62,8.

**Lo que se ha hecho.** Un módulo nuevo, `backend/redondeo_salida.py`, con la regla de Jesús y
nada más, aplicado en los cuatro sitios por donde una cantidad llega al cliente: el buscador,
el añadir un alimento, los menús del recetario y la biblioteca de menús. Los motores siguen
calculando con la cantidad exacta; el redondeo va encima, justo antes de entregar el número, y
los macros se recalculan con la cantidad ya redondeada para que lo que se ve cuadre con lo que
suma.

Siempre a la baja, como en el código antiguo, porque pasarse hace que el alimento aporte más
de lo que queda en esa comida y quedarse corto lo absorbe el resto del menú. La función de la
calculadora antigua tenía un parámetro llamado `redondear` que en realidad significaba
"a la baja"; aquí eso va en el nombre de la función y explicado, que es lo que pedía el aviso.

Dos detalles que hubo que resolver por el camino. El primero: un paso de 50 no puede hacer
desaparecer un alimento del plato, así que 30 g de una verdura no se redondean a cero sino que
caen al múltiplo de 5, y si ni eso llega al mínimo del alimento se deja la cantidad como
venía. El segundo: en el buscador el **orden** de las sugerencias lo sigue decidiendo la
cantidad exacta del motor, no la redondeada, porque redondear antes de ordenar cambiaría qué
alimento sale el primero, y eso sí rompería la paridad con la calculadora antigua.

**Los macros del día ya cumplían la regla**, así que ahí no se ha tocado nada: el motor da la
proteína y la grasa enteras y los hidratos de 5 en 5, y el agente del ajuste mensual también.
Se revisaron los 232 clientes de la base y ninguno la incumple. Queda un test que lo vigila,
que es más útil que aplicar un redondeo donde no hace falta.

**Comprobado en la app real.** Aplicando la receta "Avena Fusion Cake" a la Comida 1 salen 45 g
de harina de avena, 30 de cacao, 50 de yogur, 20 de proteína, 200 de fresas, 5 de nueces y las
unidades enteras (1 huevo, 1 cucharadita de aceite, 1 Skyr). Por la API se generaron 40 menús y
**ninguna** cantidad quedó con decimales ni fuera de múltiplo. El cuadre no se resiente: los
menús siguen saliendo cuadrados y el error mayor respecto al objetivo es de 1,5 g.

---

## Pendientes que no dependen de nosotros

*(Se irán anotando aquí según aparezcan: decisiones de Jesús, datos que faltan o terceros.)*

**No tenemos el repositorio fuente de la calculadora antigua** (`jgl-calma-web-next`). En
`_calma_ref/` solo está el bundle compilado, que sirve para contrastar comportamiento pero no
para leer el código como lo describe el documento (nombres de fichero, números de línea y las
funciones a medio desminificar). Si Jesús quiere que revisemos algo concreto de ese código, hace
falta acceso al repositorio. Hasta ahora no ha hecho falta: el reparto se pudo portar y validar
contra el bundle.

**Los dos criterios del tercio no coinciden, y conviven.** La calculadora antigua tiene su
propia forma de decidir si la proteína de un cereal o de un fruto seco cuenta, y no es la del
tercio: sobre el catálogo entero discrepan en 69 alimentos. Hoy la app usa el criterio de Jesús
(el tercio) para lo que el cliente ve y guarda en su día, y el heredado en el buscador mientras
monta la comida y en las herramientas de menús. Funciona, pero significa que el mismo alimento
puede enseñar dos cifras de proteína distintas según dónde se mire. **Decide Jesús** si el
criterio del tercio debe sustituir al heredado también en esos sitios.

**Un test falla desde antes de tocar nada** (`test_search_foods_by_category`): al buscar por la
categoría de carnes aparece un "Caldo de cocido" que no es de esa categoría. Es un problema de
cómo está clasificado ese alimento en el catálogo, no del buscador.

**La proyección de composición corporal del código antiguo no está en nuestra app.** Calma
tiene un modelo que estima, semana a semana y por tramos de cuatro semanas, cuánta masa grasa y
cuánta masa libre de grasa cambia según el punto de partida, y con él valida si un objetivo de
peso es alcanzable en un plazo. Nosotros solo calculamos la composición actual. **Decide Jesús**
si eso debe existir en la app nueva; encajaría en el bloque H, que es de después del lunes.
