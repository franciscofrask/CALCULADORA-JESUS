# Documento del 7 de agosto - puntos cerrados

Registro de los puntos del documento *"Todo lo que hay que hacer"* (7 de agosto de 2026) que se
van cerrando. Por cada uno: qué método se pide, cómo funcionaba antes, un ejemplo de cada caso
y qué queda pendiente si depende de alguien más.

> ## ⚠ El documento se actualizó y se RENUMERÓ
>
> La versión nueva reordena los bloques (ahora van de la A a la N, con los puntos 1 al 97) y
> mete puntos nuevos en medio, así que **la numeración de este registro es la vieja**. La
> equivalencia:
>
> | Aquí | Documento nuevo | | Aquí | Documento nuevo |
> |---|---|---|---|---|
> | 1 | 1 | | 11 | 13 |
> | 2 | 4 | | 12 | 14 |
> | 3 | 5 | | 13 | 15 |
> | 4 | 6 | | 14 | 16 |
> | 5 | 7 | | 15 | 17 |
> | 6 | 8 | | 16 | 18 |
> | 7 | 9 (remite al 30, antes al 20) | | 17 | 19 |
> | 8 | 10 | | 18 | 20 |
> | 9 | 11 | | 19 | 21 |
> | 10 | 12 | | | |
>
> **Lo que trae de nuevo la actualización, y ya está comprobado** (ver el bloque A de abajo):
> una tabla de prueba con 20 filas de valores exactos, dos puntos nuevos (el 2, tres comidas, y
> el 3, los cuatro modos de perientreno) y dos reglas nuevas en el del filtro del tercio.
>
> También avisa de algo importante: el código antiguo que Jesús leyó es la versión 1.1.0 y la
> que está en producción es la 1.9.0, ocho versiones más nueva. Cuando el documento diga que
> algo es un fallo del código antiguo, hay que comprobarlo contra la calculadora de verdad
> antes de darlo por bueno.

> **Todo lo de aquí está en producción desde el 7 de agosto por la noche** (hasta el commit
> `8421e3b`). Se desplegó el árbol completo del repositorio, no solo los ficheros tocados: el
> primer intento falló al construir el frontend porque producción venía de un despliegue viejo
> y le faltaba un fichero que las pantallas nuevas importan. Ese fallo no llegó a tocar la app
> (el rollout ni se lanzó y los pods siguieron sirviendo la versión anterior). Queda una copia
> de lo sobrescrito en `/opt/jg12/_backup_pre_0708/`.
>
> Lo que **no** se ha subido es el trabajo en curso del asistente, que sigue sin commitear en
> la máquina de Francisco: se desplegó desde git, no desde la carpeta de trabajo.

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

### Contraste con la actualización del documento (07-08, versión nueva) · TODO CUADRA

La versión actualizada trae una **tabla de prueba con 20 filas de valores exactos** para
verificar la implementación ("si tu implementación da estos números, está bien"). Se pasaron
las 20 y **salen las 20**, incluidas las siete filas de "en ayunas" que esa versión confirma
que la calculadora en producción sí aplica. Quedan como test, que es el mejor juez posible:
son sus números, no deducciones nuestras.

También aclara el tramo de 30 a 50 g: los 10 g se los lleva la comida del momento del entreno,
y Jesús confirma que esa lógica es la correcta. Nuestro reparto ya lo hacía así, y su propia
tabla lo corrobora (40 g en ayunas dan 30 · 0 · 0 · 10).

**Las cuatro tablas del documento coinciden con las nuestras**, las 16 filas: proteína, grasa,
la del tramo de 100 a 150 g y la de más de 150. Ya estaban verificadas contra el bundle de la
calculadora antigua; ahora también contra lo que Jesús tiene escrito, que es la otra fuente.

**Los números de cobertura del filtro no cuadran del todo, y se sabe por qué.** El documento
dice que de 377 cereales y panes solo entran 18, y que en frutos secos entran 46 de 63. Hoy
salen 398 cereales y panes con 16 que entran, y 64 frutos secos con 48. La diferencia es que
**el catálogo ha crecido** desde que él contó: 21 cereales y panes más y un fruto seco más. Las
proporciones se mantienen y su conclusión también: esto es, en la práctica, una regla de frutos
secos (entra el 75 % de ellos y solo el 4 % de los cereales y panes).

**Punto 2 nuevo · con 3 comidas no se aplica ningún escenario.** Ya era así: cada comida se
lleva un tercio de cada macro aunque sea día de entreno, y el perientreno se aplica igual.
Comprobado con cuatro cantidades de hidratos y los cuatro momentos de entreno.

**Punto 3 nuevo · los cuatro modos de perientreno.** Los cuatro cuadran con su tabla: intra +
post (20 %/30 % y 80 %/70 %), solo post (100 %), solo intra (25 %/35 % y el resto repartido) y
sin peri (todo repartido). Y ni el intra ni el post llevan grasa nunca, como dice el documento.

Todo eso queda fijado en `backend/tests/test_reparto_calma_paridad.py`.

Un detalle menor que salió de la tabla: el día de descanso reparte los hidratos a cuartos con
un redondeo de 0,1 g por comida, así que con cantidades que no se dividen entre cuatro (65 ÷ 4
= 16,25) se pierden 0,2 g del día. No se toca por eso: lo que se le enseña al cliente va
redondeado a múltiplos de 5, así que ni se ve.

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

### Punto 5 - Cantidades mínimas por categoría, y descartar por debajo · CERRADO EN PARTE

Este punto son dos cosas distintas, y solo una depende de nosotros.

**El mapa de mínimos ya estaba.** Están las 56 categorías con su mínimo, portadas de la
calculadora antigua (`backend/calma_suggest.py`, `Z_MIN`). De los cuatro valores que nombra el
documento, tres ya coincidían: aceites 5 g, verduras 50 g y bebidas vegetales 100 g. El de
frutos secos no (heredaban el 5 de la categoría de grasas y el documento pide 10), y ese sí se
ha corregido, en un sitio aparte del mapa portado para que se vea de un vistazo qué es decisión
de Jesús y qué viene heredado.

**Lo que no podemos hacer solos es repasar los 56 valores**, que es lo que el documento cifra
en media hora con él. Para que esa media hora sea de decidir y no de buscar, queda preparada la
tabla completa en `_internos_proceso/minimos_por_categoria_para_jesus.md`: cada categoría con
su nombre, el mínimo de hoy y una columna en blanco para el valor nuevo. El ejemplo que él pone
son los copos de avena, que salen a 10 g (una cucharada) porque la categoría de cereales tiene
ese mínimo.

**La regla de descarte sí era un fallo nuestro, y está arreglado.** El caso de los "Queso
Havarti · 0 ud" y "Huevos enteros M · 0 ud" se reprodujo con esos dos alimentos exactos: al
pedir añadirlos a una comida sin hueco, la app devolvía cantidad 0 y, encima, decía que cabían.
El motor usa el 0 para decir "no cabe ni a su cantidad mínima", pero la ruta lo entregaba como
si 0 fuese una cantidad. Y la pantalla, al ver un alimento con los tres macros a cero, lo
tomaba por un alimento libre (konjac, salsas zero, que sí pueden ir sin gastar macros) y lo
dejaba entrar igual. De ahí la línea a cero.

Ahora la ruta dice que no cabe y por qué, con el mínimo del alimento, y la pantalla lo descarta
avisando: "Queso Havarti no cabe: lo mínimo son 25 g y no queda hueco". Comprobado que los
alimentos libres siguen entrando (el konjac sin hueco sigue dando 1000 g) y que con hueco de
sobra el queso entra normal, a 125 g.

---

## Bloque B - Limpieza antes de que entre nadie

### Punto 6 - El cliente ve su propia etiqueta de riesgo · CERRADO

Era peor de lo que decía el documento. La pantalla de Check-ins del cliente pintaba una
tarjeta con su etiqueta ("Saludable" / "Atención" / "En riesgo") **y el motivo debajo**, y esos
motivos los calcula la misma función que usa el panel del entrenador: "Baja automática por
fallos de pago", "Pago atrasado", "2 intentos de cobro fallidos". El cliente estaba leyendo
notas de cobro sobre sí mismo en su propio panel.

Se han cerrado las dos puertas. La del servidor: la ruta que se la daba al cliente ya no
existe, y queda solo la del entrenador, que pide permisos de administrador. Y la de la
pantalla: la tarjeta se ha quitado. Comprobado que la ruta del cliente devuelve 404 y que sus
check-ins siguen funcionando con normalidad.

### Punto 7 - Hay dos pesos distintos en la misma app · DIAGNOSTICADO (se cierra en el 20)

Son dos fuentes distintas, y ninguna está mal en sí:

- **Reportes** enseña el peso del último reporte que mandó el cliente, con su fecha
  (`ReportsPage.jsx:354`, el "Último: 118 kg · 21 feb").
- **Ajustar macros** enseña el peso guardado en su ficha, que es con el que se calcularon los
  macros que tiene hoy (`MacroCalculatorClientPage.jsx:107`, vía `GET /macros`).

Si el cliente reporta 118 kg pero nadie ha recalculado sus macros desde que pesaba 94, las dos
cifras son correctas y contradictorias a la vez. **RESUELTO por el punto 25**: el ajuste usa ya el peso del reporte, así que las dos
pantallas dicen lo mismo. El documento remitía al punto 30 de este
mismo documento, así que aquí solo queda el diagnóstico.

### Punto 8 - Hay datos de prueba en producción · PREPARADO, PENDIENTE DE DAR LA ORDEN

En producción hay **18 cuentas de prueba** sobre 203 usuarios. `francisco@test.com` se queda
(decisión de Francisco) y también `clientedemo@test.com`, que es con la que se prueba la app.

Queda el script `backend/_limpiar_datos_prueba.py`, que **simula por defecto** y solo borra si
se le pasa `--ejecutar`. Ya se ha pasado en producción en modo simulación y la lista es esta:
16 cuentas vacías (los `test01@jg12.com` a `test10@jg12.com`, `test@test.com` y varios
`francisco*@test.com`) y **dos que sí tienen cosas dentro**:

- `jose@test.com`: 7 dietas, 1 reporte, 3 check-ins, 1 foto y 12 cambios de macros.
- `prueba@mail.com`: 1 reporte y 3 check-ins.

Esas dos no se tocan sin que Francisco las mire: por el volumen de datos, alguien las usó de
verdad. El backup del día está hecho (`/opt/jg12/backups/`, cron de las 4:30).

### Punto 9 - Hay alimentos sin macros en el catálogo · MATIZADO

El diagnóstico no se sostiene tal cual, y aplicarlo habría hecho daño. En el catálogo hay 15
alimentos con los tres macros a cero, pero **no son un error**: son la lechuga, el pepino, el
apio, las setas, el konjac y los refrescos zero. De verdad no aportan nada, y el método los usa
a propósito como alimentos libres. Sacarlos del buscador sería quitar medio plato de verdura.

Lo que sí rompe los números de un menú sin que nadie se entere es lo contrario: alimentos con
macros **mal puestos**. Ahí hay casos de verdad, y son los que encaja la frase "si uno entra en
un menú, los números salen mal y nadie se entera":

- Una tortita de maíz de 7 g con 125 g de grasa: mete 1149 kcal en la comida.
- Un turrón de coco con 79 g de proteína por 100 g.
- Varios panes y galletas con los macros por 100 g pero la ración puesta a 1 g.

Queda `backend/_auditar_catalogo.py`, que los lista ordenados por gravedad y con el enlace a la
ficha del producto para corregirlos. Salen 17, de los cuales unos 7 son claramente erróneos y
el resto son etiquetas mal redondeadas. **Corregir los valores es cosa de Jesús**: hay que
mirar la etiqueta real de cada uno, y no se pueden inventar.

### Punto 10 - Una ruta que echa al cliente al login · CERRADO

Es el aviso **"Tus macros son provisionales"**, que la app le manda a casi todos los clientes
nuevos a las dos horas de darse de alta. El aviso lleva un enlace a `/dashboard/ajustar-macros`
(`backend/core/avisos_cliente.py:79`) y **esa ruta no existe**: la pantalla de ajustar macros
está en `/dashboard/macro-calculator` (`frontend/src/App.js:214`).

Como la ruta no existe, cae en el comodín del router, que es
`<Route path="*" element={<Navigate to="/auth" replace />} />` (`App.js:247`) y manda al login
**sin comprobar si hay sesión**. O sea: el cliente nuevo pulsa la primera notificación que
recibe de la app y acaba en la pantalla de login. Es, literalmente, la peor primera impresión
posible, y le pasa a casi todos.

Se han arreglado las dos cosas, porque la segunda es la que convierte cualquier enlace roto
del futuro en una expulsión:

1. El aviso apunta ya a `/dashboard/macro-calculator`, que es donde está de verdad la pantalla.
2. El comodín del router ya no manda al login sin mirar. Ahora, si hay sesión, deja al cliente
   en su panel (y al entrenador en el suyo); al login solo va quien no ha entrado. Y mientras
   se está comprobando la sesión no redirige a ninguna parte, porque hacerlo antes de saber
   quién es era la otra forma de acabar en el login sin motivo.

Además queda un test que **lee las rutas de verdad del router** y las cruza con los enlaces de
todos los avisos. Si mañana alguien renombra una pantalla y se olvida de un aviso, salta ahí y
no en el móvil de un cliente. Los 33 destinos del router y los 12 enlaces de avisos están
cuadrados ahora mismo.

Comprobado en la app: entrando a `/dashboard/ajustar-macros` con la sesión abierta ya no
aparece el login, y el aviso que genera la app para un cliente recién dado de alta sale con el
enlace bueno.

---

## Bloque C - El alta y el quiz

### Puntos 11 y 15 - Los modificadores y el cuestionario único · CERRADOS JUNTOS

Resultaron ser la misma cosa. **El motor ya aplicaba los tres modificadores** y cumple las
ocho reglas del documento; lo comprobé con 39 tests que las fijan una a una. Lo que pasaba es
que **el cálculo se hacía antes de tenerlos**: el alta iba en dos cuestionarios, el primero
calculaba con cuatro preguntas y entregaba unos macros *provisionales*, y los tres
modificadores estaban en el segundo, detrás de un botón que había que volver a pulsar. De ahí
la frase "el quiz calcula con menos información": no faltaban las preguntas, faltaba que el
cálculo esperase a tenerlas.

Ahora el alta es **un solo recorrido**: los cuatro datos de la tabla y, seguido y sin cortes,
lo que afina los hidratos y lo que sirve para conocer al cliente. Se calcula una sola vez, al
final, y lo que se le entrega son sus macros de verdad. Los cuatro datos de partida se guardan
por el camino (crean su ficha), pero no se le enseña ningún número hasta el final.

Con eso desaparecen de la app los "macros provisionales": ya no hay dos cuestionarios, ni el
mensaje que decía que aquello no era lo definitivo, ni el botón de "Ajustar mis macros" al
final del alta. Quien vuelva más adelante por el botón de ajustar sigue entrando directo al
tramo de afinado, porque sus cuatro datos ya están en la ficha y no hay que volver a
preguntárselos.

**Las dos dudas del punto 11 quedaron resueltas el 07-08**: Francisco confirmó que el texto
del documento suplanta a cualquier decisión anterior, así que se aplicó literal. El +20 % de
"cómo engorda" lo cobra SOLO "casi no lo noto" (el 29-07 se lo daba también a "normal"), y el
umbral de grasa es 20 % para todos (el 30 % de mujeres del 06-08 se retira; consecuencia
asumida: la tabla de ellas empieza en el 20, así que en la práctica solo lo cobra quien esté
en el arranque). Cambio en `macro_engine.py` (`RESPUESTAS_QUE_SUBEN`, `BF_MAX_NO_ENGORDA`)
con sus tests reescritos: 162 en verde.

Comprobado el efecto de esa regla nueva sobre el cálculo: un hombre de 80 kg en definición que
contesta "normal" se queda en 140 · 130 de hidratos, los mismos que si no hubiera contestado
(antes se llevaba un +20 %); con "casi no lo noto" y grasa ≤ 20 % sube a 170 · 155, y con 25 %
de grasa no sube. En mujeres solo sube justo en el 20 %, como estaba previsto.

**De paso apareció un texto que engañaba en el desglose del cálculo.** El resumen que ve el
cliente al terminar decía "Otro deporte: +10 % hidratos en descanso" **siempre**, también a los
de volumen, que son los que se llevan un +20 %. O sea, se le enseñaba una subida distinta de la
que le habían dado. Ahora el porcentaje sale del propio cálculo en vez de estar escrito a mano,
así que dice +10 % en definición y +20 % en volumen.

Y dos detalles que salieron al escribir los tests y conviene tener por escrito. El día de
entreno **puede acabar por encima de su techo del +30 %**, pero solo para igualar al descanso:
es lo que sale de juntar la regla del techo con la de la comprobación final, y en volumen pasa
de verdad (234 de entreno contra 238 de descanso, y el entreno sube a 238). Y el deporte extra
parece tocar el día de entreno cuando lo que hace es empujar el descanso por encima y que la
comprobación final tire del entreno detrás.

### Punto 12 - Se pueden calcular macros sin contestar nada · CERRADO

Confirmado tal cual: mandando el cuestionario vacío, la app calculaba, guardaba los macros y
marcaba el ajuste como completado. Los cuatro datos de la tabla salían de la ficha y los tres
modificadores viajaban vacíos, así que no movían nada: el cliente se quedaba con unos macros
calculados a medias creyendo que eran los suyos.

Ahora hace falta haber contestado las tres que mueven el número, y se bloquea **en los dos
sitios**: la pantalla no deja pulsar y dice cuáles faltan, y el servidor lo rechaza aunque se
le llame por fuera. El resto de preguntas del recorrido, las que sirven para conocer al
cliente, se pueden dejar en blanco, que para eso están.

Comprobado por API: con el cuestionario vacío responde "falta que nos digas tu actividad
diaria, si practicas otro deporte, con qué facilidad engordas"; contestando dos de las tres,
nombra solo la que falta; y con las tres, calcula.

### Punto 13 - El resultado del cálculo sale fuera de pantalla · HECHO, FALTA VERLO

La pantalla de resultado va apretada: títulos más pequeños, menos aire entre bloques, las
tarjetas de macros más compactas y **un solo botón** donde antes había dos (el segundo llevaba
al cuestionario que ya no existe). Además el contenedor del cuestionario ya permite desplazarse
en vertical: tenía `overflow-hidden`, así que en una pantalla baja lo que sobraba quedaba fuera
y sin manera de llegar a ello.

**Queda verlo con los ojos.** Para comprobarlo de verdad hay que completar un alta entera, y
eso significa o alterar los datos de una cuenta real o crear una nueva; no he hecho ninguna de
las dos. Es una revisión de un minuto en cuanto haya un alta de prueba a mano.

### Punto 16 - Al terminar, el primer día viene montado · CERRADO

**Lo que había.** El cliente terminaba el alta, veía unos números y se quedaba ahí. Su primer
día estaba vacío y tenía que montarlo desde cero sin conocer la app, que es justo donde se cae
la gente.

**Lo que hay ahora.** En cuanto salen sus macros, la app le monta y le guarda el día de hoy:
cada comida con un menú del recetario cuadrado a los macros de esa comida. En la pantalla del
resultado, debajo de los números, ve qué le ha tocado ("Comida 1 · Uno clásico de toda la
vida"), y al entrar en Nutrición se lo encuentra puesto.

Detalles que importan: **ningún menú se repite en el mismo día** (dos comidas iguales el primer
día son la peor carta de presentación, y el generador tendía a elegir el mismo para dos comidas
seguidas), respeta lo que el cliente ha dicho que no quiere comer, y las cantidades salen
redondas porque pasan por el redondeo del punto 4. El intra y el post se dejan vacíos a
propósito: son bebidas y geles muy de cada uno, y llenárselos a ciegas el primer día es más
ruido que ayuda.

Se monta en segundo plano y sin bloquear: si fallara, el cliente termina el alta igual, solo
que con el día por montar.

**El segundo motivo también funciona, y está comprobado.** Cada dieta guardada alimenta la
frecuencia de alimentos, que es de donde salen luego las sugerencias. Al montar y guardar un
día de prueba, "Huevos enteros L" pasó de 6 a 8 usos y "Pechuga de pollo" apareció con 3. O
sea: aceptando o cambiando estas comidas el cliente nos va diciendo lo que le gusta sin que
haya que preguntárselo, que es lo que alimenta el bloque F.

**Medido**: montar un día de cuatro comidas tarda unos 2,5 segundos, y las cuatro salen
cuadradas (por ejemplo, objetivo 47,5 P · 51 H · 12 G y el menú lleva 48 · 51 · 11).

Vive en `POST /api/calculator/montar-dia`, que sirve para montar cualquier día, no solo el
primero.

### Punto 17 - «¿Sigues una dieta ahora?» solo tiene dos respuestas · BLOQUEADO (falta el documento de textos)

**Lo que se comprobó, y no cuadra con el enunciado.** Esa pregunta **ya tiene tres respuestas**,
no dos, y las tiene en los dos entornos (aquí y en producción):

1. "Sí, y sé exactamente lo que como."
2. "Como siempre parecido, pero no lo tengo medido."
3. "No, como lo que surge."

La tercera se añadió el **6 de agosto**, un día antes del documento, en el commit `daf052a`
("La dieta tiene tres respuestas, y la mejor pregunta se le hace a todos"). Así que o el
revisor miró una versión anterior a ese día, o lo que falta son opciones **además** de estas
tres. El punto dice "faltan opciones" en plural y remite al documento de textos, así que lo
segundo es lo más probable.

Se revisaron también las demás preguntas del cuestionario por si el enunciado se refería a
otra: de las 24 con opciones, solo tres tienen dos, y ninguna es sobre dieta (el sexo, el
objetivo volumen/definición y el "¿practicas otro deporte?", que son sí/no de por sí).

**Qué hace falta para cerrarlo.** El documento «LOS TEXTOS DE LA APP», que es donde el propio
punto dice que están las opciones. Sin él no se pueden inventar: el texto exacto de cada
respuesta es lo que decide qué se guarda y qué se hace luego con ese dato (la respuesta
"parecido", por ejemplo, hace que se le pida su dieta para partir de ella). En cuanto llegue,
esto es de un rato.

### Punto 18 - El check-in diario · MEDIO CERRADO (y con un fallo grave encontrado)

Este punto pedía dos cosas y solo una dependía del documento de textos.

**Sustituir las preguntas por las de Jesús: bloqueado.** Hoy el check-in diario pregunta dos
cosas, energía y "ansiedad y hambre", que vienen del documento del 31-07. Cambiarlas requiere
saber cuáles son las suyas, y están en el documento de textos que aún no tenemos.

**Que el cliente apunte lo que ha comido: hecho.** Es un campo de texto libre en el check-in
diario, opcional, con la pregunta "¿Qué has comido hoy?" y un aviso de que no hace falta pesar
nada y de que incluya lo que picó entre horas. No es su dieta -- esa ya está en la app y el
servidor la da por registrada él solo --: es lo que se ha comido de verdad. Se guarda con el
check-in, el cliente lo ve en su historial y **el entrenador lo ve en la ficha del cliente**,
debajo de la línea de ese día, que es donde tiene sentido: ahí aparece el picoteo que no está
en ninguna dieta, que es justo lo que explica por qué alguien coge peso sin saber por qué.

**Y mirando esto apareció un fallo que se llevaba por delante los check-ins enteros.** El
decorador de la ruta `POST /checkins` estaba pegado a una función auxiliar de más arriba en vez
de a la que crea el check-in. Con eso, FastAPI registraba como ruta la función auxiliar, cuyos
parámetros (`profile` y `fecha`) tomaba por parámetros de la URL: **cualquier cliente que
enviaba un check-in recibía un error pidiéndole una "fecha" que nadie le había preguntado**.
Ni el diario, ni el semanal, ni el mensual. No funcionaba para nadie.

Estaba así en el repositorio de antes de tocar nada, **y también en producción**, comprobado
en el servidor. Arreglado: el decorador vuelve a la función que crea el check-in, y probado de
punta a punta (se envía, se guarda con lo que ha comido, y se lee tanto en el historial del
cliente como en la ficha del entrenador).

### Punto 19 - Las fotos se suben desde el sitio equivocado · CERRADO

**Casi todo estaba hecho, pero sin llegar a producción.** El 6 de agosto ya se había movido la
subida de fotos a un único sitio, el reporte, con sus tres poses (frente, espaldas y perfil),
las indicaciones escritas y la foto del mes pasado al lado de cada hueco para que se coloque
igual. La pantalla de check-ins, donde antes se subían, se quedó solo para verlas. Y el vídeo
de Jesús explicando cómo se toman los perímetros también estaba, y es exactamente el del
enlace del punto.

Lo que pasa es que **nada de eso estaba en producción**: venía de un despliegue anterior a ese
día. De hecho, el fichero donde vive el enlace del vídeo es justo el que faltaba en el servidor
y el que hizo fallar el primer intento de despliegue de esta noche. Con el despliegue ya hecho,
todo eso está vivo.

**Lo que sí faltaba, y es lo que dice el punto.** El alta seguía pidiendo las tres fotos justo
después de dar los macros, con el argumento de que era "el momento de más ganas". Ese es el
punto del flujo donde el cliente aún no entiende para qué son: acaba de darse de alta, no sabe
qué es un reporte, y se le pide que se haga tres fotos del cuerpo sin haberle explicado nada.
Se han quitado de ahí.

Las **medidas sí se siguen pidiendo** en ese paso, con el vídeo de Jesús al lado, porque el
punto no las menciona y ahí no hay pudor que valga.

**Lo que se pierde, y conviene tenerlo claro:** la foto "inicial" pasa a ser la del primer
reporte del cliente y no la del día uno. Es la consecuencia de moverlas, y se asume porque una
foto que el cliente no entiende para qué es, muchas veces no se hace.

---

## El documento de textos, ya en nuestras manos (07-08 de noche)

Llegó `18 · LOS TEXTOS DE LA APP.docx` (6 de agosto, "versión definitiva", confirmado por
Jesús). Trae las 12 pantallas del test de entrada con su texto exacto y la aclaración de Jesús
debajo de cada pregunta, los cuatro mensajes del informe, y dos notas. Desbloquea el punto 17 y
destapa bastante más de lo que se pedía.

### Punto 17 - Las respuestas de la dieta · CERRADO

Son **cuatro**, no tres, y ahora se sabe cuáles:

1. Estricta, mido todo lo que como.
2. Pesar no, pero me cuido bastante.
3. Sin control, pero no como mal.
4. Como mal y desorganizado.

Las dos primeras traen una dieta de la que partir; las dos últimas no. Y eso importa, porque
"sin control pero no como mal" y "como mal y desorganizado" no son lo mismo y hasta ahora caían
las dos en el mismo saco.

Los valores guardados se conservan para no romper lo que ya contestaron los clientes de antes.
De esa respuesta colgaban **seis condiciones sueltas** repartidas por el cuestionario, y añadir
una cuarta opción obligaba a acertar en las seis: ahora hay una sola función que decide si
alguien trae dieta, y las seis la usan. En el servidor se hizo lo mismo, porque allí la
comprobación era `if sigue_dieta`, y en Python cualquier texto cuenta como verdadero: la
respuesta nueva habría colado como si trajera una dieta medida.

### Una regresión mía que el documento destapó

Al unificar el alta (punto 15) quité el mensaje de "estos no son tus macros definitivos". Era
pasarse: lo que dejó de tener sentido es llamar provisionales a unos macros que ya llevan
dentro los modificadores, pero **al cliente de plan con entrenador hay que seguir diciéndoselo**,
porque le queda el cuestionario largo y su coach se lo revisa. El documento trae ese texto
literal y está repuesto tal cual.

### El test de entrada, como lo pide el documento · HECHO

Aplicado tal cual, porque lo que dice el documento es lo que vale. Textos literales suyos, con
la aclaración de Jesús debajo de cada pregunta, y en su orden.

- **Actividad diaria: cuatro opciones** donde había tres (muy sedentario, ligeramente activo,
  moderadamente activo, muy activo). Ojo con esto porque toca macros: el +10 % de hidratos lo
  cobra **solo "muy activo"**, que es lo que dice el documento del 07-08; los otros tres no
  suben nada, ni siquiera el nuevo "moderadamente activo". Comprobado con los cuatro valores.
- **Las dos preguntas de seguimiento del deporte**: cuál practica, cuántos días y a qué
  intensidad, y si podría hacerlo en días que no va al gimnasio (sí / no / ya lo hago así).
  Solo salen a quien ha dicho que sí. No mueven macros.
- **La pantalla del apetito** ("¿Eres de buen comer?"), que no existía. No mueve macros.
- **La experiencia entrenando se muda al test de entrada**, con las cuatro opciones suyas
  (parto de cero / menos de 1 año / más de 1 año / años en serio). Estaba en el cuestionario
  largo, que solo ven los planes con entrenador, y con cinco tramos por años. Se ha quitado de
  allí para no preguntar lo mismo dos veces con opciones distintas.
- **Los textos exactos** del objetivo, la confirmación, el peso, el sexo y el porcentaje de
  grasa, y la tercera opción de "¿te cuesta definir?", que ahora dice "Nada" y no "Poco".

Los valores que ya estaban guardados se conservan (`sedentario` pasa a significar "muy
sedentario" y `normal` "ligeramente activo"), así que a nadie se le mueven los macros por esto.

### Lo que el documento pide y todavía NO está

Solo queda una cosa suelta del test: el documento dice que en la pantalla de la dieta se le
pida **"Ponme un día tipo. El de ayer, por ejemplo."**. En la app hay un bloque de dieta que
recoge eso mismo, pero con otro texto y otro formato; hay que cuadrarlo.

Y dos notas del final del documento, que no son del test:

- **Los fondos de pantalla**: reaprovechar los del quiz actual de ELM para las pantallas del
  test de la app. "Ya están hechos y son los buenos". Hay que localizarlos.
- **El biotipo de mujer** no se pone: el test de mujer salta esa pantalla, porque los siete
  apodos están escritos para hombre. En la app ya funciona así.

Y una regla del motor que el documento deja escrita y hay que verificar: lo de "con lo que comes
ahora, ¿mantienes, ganas o pierdes?" **modula hasta un 20 % y se aplica al final, después de
todos los demás modificadores**.

---|---|
| 3 · Experiencia entrenando (4 opciones: parto de cero / menos de 1 año / más de 1 año / años en serio) | Existe con **5 opciones distintas**, y está en el cuestionario largo, no en el test de entrada |
| 5 · Actividad diaria (**4 opciones**: muy sedentario / ligeramente activo / moderadamente activo / muy activo) | **3 opciones** (sedentario / normal / muy activo). Tocarlo mueve macros: hay que decidir cuál de las cuatro cobra el +10 % |
| 6 · Otro deporte: **dos preguntas de seguimiento** ("¿cuál, cuántos días y a qué intensidad?" y "¿podrías hacerlo en días que no vayas al gimnasio?") | Solo el sí/no |
| 7 · El apetito: "¿Eres de buen comer?" (mucho / lo normal / poco) | **No existe** |
| 9 · ¿Te cuesta definir? (mucho / lo normal / **nada**) | Existe, pero la tercera opción dice "poco" |
| 12 · "Ponme un día tipo. El de ayer, por ejemplo." | Existe algo parecido dentro del bloque de dieta; hay que cuadrar el texto |

Y una regla del motor que el documento deja escrita y hay que verificar: lo de "con lo que comes
ahora, ¿mantienes, ganas o pierdes?" **modula hasta un 20 % y se aplica al final, después de
todos los demás modificadores**.

### Punto 22 (numeración nueva) - Nutrición abre en una fecha futura · CERRADO

**La causa.** La pantalla guardaba la última fecha que hubieras mirado y la restauraba al
entrar, sin comprobar cuál era. Así que quien echaba un vistazo al día de mañana y se salía, al
volver se encontraba la app abierta en mañana. Y era peor de lo que dice el punto: quien miraba
un día y entraba al siguiente aterrizaba en la fecha de ayer, y una fecha guardada hacía una
semana se restauraba igual.

**Lo que hay ahora.** Al abrir, hoy. Se conserva lo único útil de aquello: si recargas la
página en el mismo día en el que estabas trabajando, vuelves al día que tenías abierto en vez de
perderlo. Para eso se guarda también cuándo se guardó, y la fecha solo se restaura si es de hoy
y no es futura.

Comprobado en la app con una fecha futura metida a mano (20 de agosto): al entrar, la pantalla
abre en "Hoy". Y los seis casos posibles se comportan como deben: mirar mañana y refrescar
lleva a hoy, mirar una fecha vieja hace días lleva a hoy, entrar al día siguiente lleva a hoy, y
solo recargar el mismo día conserva el día que tenías abierto.

De paso, el cálculo de "qué día es hoy" estaba repetido en tres sitios de la pantalla y ahora
vive en uno. Se hace en hora local y no en UTC a propósito: con la hora universal, quien entra
de madrugada vería el día anterior.

---

### Punto 23 - La app dice «afinar» y Jesús dice «ajustar» · CERRADO

Cambiado en toda la app. Los que veía el cliente eran seis:

- "Aquí puedes recalcular o **afinar** tus macros cuando cambie tu peso o tu objetivo" (el
  recorrido guiado del panel).
- "Añade otra categoría para **afinar**" (el buscador de alimentos).
- "**Afina** tus macros", dos veces: el título del bloque en Ajustar macros y el del tramo del
  cuestionario.
- "Con tus datos de estas semanas podemos **afinarlos**" (el aviso de que lleva semanas con los
  mismos macros).
- Y dos en el quiz de venta: "lo que necesitas es **afinar**, no que te lleven de la mano" y la
  respuesta "estoy bien ahora, quiero **afinar** más".

Se han cambiado también los comentarios del código, que no los ve nadie pero es por donde la
palabra se vuelve a colar cuando alguien escribe el texto siguiente mirando el de al lado.

Lo único que conserva la palabra es el nombre interno de la función que cuadra las cantidades de
un menú (`afinar_cantidades`) y los dos comentarios que la describen. Eso no es un texto: es
código, no lo lee ningún cliente, y renombrarlo sería riesgo sin beneficio.

---

### Punto 24 - Aprovechar los fondos del quiz actual · BLOQUEADO (no aparecen)

**Dónde irían, que eso sí está claro.** La portada del test de venta ya espera una imagen: el
código apunta a `public/portada-test.jpg` y, mientras el fichero no exista, se ve solo el
degradado. Es decir, el hueco está hecho y basta con dejar la imagen ahí. Las pantallas del
cuestionario no tienen fondo hoy, solo los degradados de marca.

**Lo que ya hay en la app** y no hay que volver a buscar: las siete fotos de los biotipos
(`public/biotipos/`) y las del porcentaje de grasa (`public/bodyfat/`).

**Lo que falta: las imágenes.** No están en el disco (Francisco lo confirma) y no las he
encontrado en Drive, buscando por cinco vías: por título ("fondo", "quiz", "test",
"cuestionario", "portada"), por tipo de imagen, entre lo compartido con Francisco, entre lo
reciente, y dentro de la carpeta de material gráfico de la cuenta de Jesús
(`admin@jesusgallegopt.com`), que resultó tener los mockups de la app antigua, no esto.

Lo que devuelve el buscador de Drive está dominado por las miles de fotos de progreso de
clientes que entran por los formularios, y su buscador no admite las consultas combinadas que
harían falta para filtrarlas.

**Hace falta la referencia concreta**: el enlace de la carpeta, su nombre exacto, o desde qué
cuenta se compartieron. Con eso es cuestión de minutos: descargarlas, dejarlas en `public/` y
apuntarlas desde las pantallas del test.

---

## Bloque D - El flujo del entrenador

### Punto 25 - El peso que sale es el último, no el del reporte · CERRADO

**Lo que pasaba.** Al ajustar los macros de un cliente, el formulario se rellenaba con el peso
de su ficha, que es el último que conste por cualquier vía (un check-in semanal, una edición a
mano). Pero Jesús ajusta **leyendo un reporte concreto**, así que el número que tiene delante
tiene que ser el de ese reporte.

**Y esto explica el punto 9**, el de los dos pesos distintos en la misma app: Reportes enseñaba
el del último reporte y Ajustar macros el de la ficha. No era que uno estuviera mal, es que son
dos cosas distintas y ninguna decía cuál era.

**Lo que hay ahora.** El formulario se rellena con el peso del reporte que se está ajustando, y
**dice de qué reporte viene**: "Del reporte del 21/02/2026". Debajo sigue la comparación con el
peso del ajuste anterior, que es lo primero que mira el coach. Si el cliente todavía no ha
mandado ningún reporte, se usa el de la ficha como hasta ahora.

**Comprobado con datos reales**: en la base hay un cliente con 80 kg en la ficha y 75,5 kg en su
último reporte, del 23 de julio. Con esto, el ajuste parte de 75,5 y lo dice. Y probados los
cuatro casos: con varios reportes coge el más reciente, sin reportes cae a la ficha, y un
reporte sin peso no cuenta.

**Falta verlo en pantalla.** La ficha del cliente es una página pesada y la extensión del
navegador se cuelga al abrirla; es la misma revisión de un minuto que el punto 15.

---

### Punto 26 - «La fecha por defecto es el lunes y tiene que ser mañana» · NO REPRODUCIDO

Este punto llegó con el apartado «Qué hacer» vacío, así que lo primero era encontrar dónde sale
ese lunes. **No sale en ningún sitio.** Lo comprobado, con pruebas y no de memoria:

**1 · La fecha del ajuste de macros ya es mañana, y también en producción.** Es el único campo de
fecha del flujo del entrenador y ya trae mañana por defecto desde el 05-08 (punto 2.3 del
documento anterior). Abierta la ficha de un cliente real con Playwright, hoy viernes 7:

```
[Macros] macro-effective-date = 2026-08-08 (sabado)
```

Y en el paquete que sirve producción ahora mismo (`main.2d305a8a.js`) está la misma cuenta,
`L3(1)` (= hoy + 1 día) y el atajo «Poner mañana». Así que lo que Jesús tiene delante en la web
tampoco es un lunes.

**2 · Recorridas las diez pestañas de la ficha** (Resumen, Macros, Membresía, Cuestionario,
Entreno, Nutrición, Menús, Suplementos, Seguimiento, Más) volcando todos los campos de fecha y
todo el texto con pinta de fecha. Los únicos campos de fecha son el del ajuste (mañana), los dos
filtros del historial (vacíos) y el del siguiente protocolo de suplementos (vacío).

**3 · Buscado el lunes en todo el código.** En el frontend la palabra «lunes» sólo aparece como
nombre de día en la rutina; en el paquete de producción, igual. En el backend, el único sitio que
calcula un lunes es `core/calendario_arranque.py` - «todos los clientes arrancan en lunes, pague
el día que pague», con la regla de las 48 horas y el anclaje del cobro de Stripe a los 84 días.
**Ese módulo no lo llama nadie**: está escrito y sin conectar.

**Lo que queda.** Hay dos lecturas del punto y las dos necesitan una palabra de Jesús:

- Si se refiere a **la fecha del ajuste**, ya está hecho: es mañana, en dev y en producción.
- Si se refiere a **cuándo arranca un cliente nuevo** - o sea, tirar la regla del lunes y que
  empiece al día siguiente de darse de alta -, es un cambio de método, no un cambio de campo, y
  toca el anclaje de la facturación. No se toca sin que lo confirme, y como el módulo está
  desconectado ahora mismo no cambia nada en la app: un cliente que se dé de alta el domingo
  empieza el lunes porque empieza al día siguiente, no porque haya una regla que lo mande.

### Punto 27 - El peso se guardaba con la fecha del ajuste · CERRADO

**Lo que pasaba.** El coach ajusta hoy leyendo un reporte de hace una semana. El peso de ese
reporte se archivaba con la **fecha del ajuste**, así que un pesaje del 23 de mayo quedaba
apuntado el 8 de agosto. La curva de peso salía corrida, y esa curva es de donde salen el ritmo
de cambio del cliente y el banco de casos: el modelo aprendía de un histórico falso.

**Ojo, esto lo pidió Jesús al revés el 05-08** («88 kilos con fecha de mañana para tener el
registro de ese peso, aunque el pesaje sea de hace una semana», punto 2.2). Manda el documento
nuevo, y el motivo que da es mejor: el histórico es el producto.

**Lo que hay ahora.** La fecha del pesaje viaja aparte de la del ajuste. El editor coge el peso
del reporte **y su fecha**, y las manda las dos; el ajuste sigue teniendo su propia
`effective_date`. En el historial de macros queda un campo nuevo, `peso_fecha`, y los dos sitios
que dibujan la curva de peso (el contexto que se le pasa al agente y el banco de casos) colocan
el peso por esa fecha, no por la del ajuste. Los ajustes viejos no la traen y se quedan donde
estaban, así que nada se mueve hacia atrás.

Debajo del peso, la app dice dónde va a quedar: **«Queda registrado el 23/05/2026, el día del
pesaje»** - antes decía justo lo contrario, «queda registrado con la fecha del ajuste». Y si el
cliente aún no ha mandado ningún reporte, lo dice también: «Sin reporte: queda registrado con la
fecha del ajuste».

**De paso, se terminó el punto 25.** El aviso «Del reporte del 23/05/2026» ya estaba, pero **la
caja del peso seguía trayendo el de la ficha**: el rótulo decía una cosa y el número era otra.
Ahora el número es el del reporte.

**Comprobado**, con el cliente de pruebas y devolviendo la ficha a su sitio al terminar:

| Qué se manda | Qué queda guardado |
|---|---|
| peso 77,7 con pesaje 2026-05-23, ajuste 2026-08-09 | `effective_date` 2026-08-09, `peso_fecha` **2026-05-23** |
| peso 78,8 sin fecha de pesaje | `effective_date` 2026-08-09, `peso_fecha` 2026-08-09 (como antes) |
| pesaje «20 de mayo» | 400, «La fecha del peso tiene que ser AAAA-MM-DD» |

Y en pantalla, guardando de verdad desde el editor: peso 85,4 · ajuste 2026-08-08 · pesaje
2026-05-23.

---

### Punto 28 - No hay confirmación al guardar · CERRADO

**Lo que había.** La confirmación **antes** de guardar ya estaba desde el 05-08 (punto 2.4) y está
en producción: se comprobó en el paquete que sirve la web ahora mismo, que trae el diálogo
«¿Guardar estos macros?» con el resumen de los ocho números. Al guardar salía además un aviso
flotante, «Macros actualizados».

**Por qué seguía sin valer.** El aviso flotante se va solo a los tres segundos. Si el coach mira
la pantalla medio minuto después, no tiene forma de saber si guardó - que es literalmente lo que
dice el punto: «si no sabe si ha guardado, va a guardar dos veces o ninguna».

**Lo que hay ahora.** Al guardar queda escrito en el editor, y se queda mientras siga en la
ficha:

> ✓ **Guardado a las 23:38.** Vigente desde el sábado, 8 de agosto · peso 85,4 kg del 23/05/2026.
> El cliente ya lo tiene.

Dice la hora (para distinguir un guardado de hace un minuto de uno de hace media hora), desde
cuándo aplica, con qué peso y de qué día es ese peso. Y desaparece en cuanto vuelve a tocar algo,
porque entonces lo que hay en pantalla ya no es lo guardado.

### Punto 29 - La columna que contesta «¿quién me toca esta semana?» · CERRADO

**Lo que pasaba.** La respuesta estaba en la base, pero repartida en dos colecciones
(`macro_history` y `reports`) y sin ninguna referencia en el cliente. Con 232 clientes, sacar
esa columna significaba recorrer el histórico entero de todos cada vez que se pinta la tabla,
así que la columna no existía y Jesús lo llevaba en una hoja aparte.

**Lo que hay ahora.** Las dos fechas se guardan **también en el cliente**, duplicadas a
propósito, y se refrescan al guardar (`backend/core/seguimiento.py`):

- `ultimo_ajuste` - cuándo se le movieron los macros por última vez. Se marca en los **cinco**
  sitios donde se guarda un ajuste: los dos del coach (editor de la ficha y su calculadora) y
  los tres del cliente (alta, cuestionario de ajuste y su propia calculadora).
- `ultimo_reporte` - cuándo mandó el último reporte. Se marca al crearlo.

Nunca van hacia atrás: si se corrige una entrada vieja del historial, la fecha no retrocede.
Lo que vale es la última vez que pasó algo, no la última vez que alguien editó algo.

**Dónde se ve.**

1. **La home del coach**, bloque nuevo arriba del todo: **«Esta semana te tocan estos 6»**, con
   los días desde el último ajuste y en naranja a partir del mes. El que nunca ha tenido un
   ajuste pone «nunca» y va por delante de todos - es justo el que se pierde cuando esto se
   lleva en una hoja. Al lado, «Ver los 226 ordenados», que abre la lista ya ordenada.
2. **La lista de clientes**, dos columnas nuevas: **Sin tocar** (se pincha para ordenar, y la
   flecha marca que está ordenando por ahí) y **Últ. reporte**.

El listado solo cuenta a los que tienen plan con ajuste del coach: al de autogestión no le
«toca» nadie, y meterlo sería ruido todas las semanas.

**Los que ya estaban.** `backend/_rellenar_fechas_seguimiento.py` rellena las dos fechas de los
clientes que ya existen, mirando el historial de la app **y el de Calma**: un cliente migrado al
que Jesús ajustó en junio en Calma no lleva sin tocar desde el principio de los tiempos, y si
saliera así taparía a los que de verdad están abandonados. Simula por defecto; escribe con
`--escribir`. En dev: **177 de 232 clientes con fecha, 55 sin ningún ajuste ni reporte**.

**Comprobado**: el listado devuelve las dos fechas, `te_tocan` sale ordenado de más abandonado a
menos, la home pinta los seis, la lista se ordena al llegar con `?orden=sin_tocar`, y al guardar
un ajuste la fecha del cliente pasa a hoy. La ficha del cliente de pruebas, devuelta a su sitio.

**Ojo para producción**: hay que pasar el script de relleno **una vez**, después de desplegar.
Sin eso, los 232 saldrían como «nunca».

### Punto 30 - Peso y % graso como series con fecha · CERRADO

**Lo que pasaba.** El peso «actual» vivía en `client_profiles.weight`, un campo suelto y sin
fecha, y el histórico vivía por otro lado: en los reportes, en el historial de macros y en lo
que vino de Calma. Dos sitios, dos números, y ninguno decía de cuándo era. Eso es el punto 9.

**Cuánto de grave era, medido.** Al construir las series salió el número: **en 50 de 232
clientes el peso de la ficha NO era el último pesaje de verdad**. Tres casos mirados uno a uno:

| Cliente | La ficha decía | El último pesaje real |
|---|---|---|
| `812e64f8` | 90,3 kg (de un ajuste de octubre de 2025) | 95,0 kg, de su reporte de marzo de 2026 |
| `8fb54f9a` | 86,0 kg (el penúltimo ajuste) | 103,0 kg, del ajuste del 20/07 |
| `fe9745c6` | 86,8 kg (un ajuste del 26/06) | 85,8 kg, del pesaje del 23/07 |

En los tres el histórico tenía razón y la ficha estaba vieja. No era un empate entre dos
fuentes: era un campo que se quedaba atrás.

**Lo que hay ahora.** `backend/core/series_cliente.py`. El peso es una serie
`{fecha, valor, origen}` y **el peso actual es el último de la serie**. Lo mismo el % graso,
que ya funcionaba así desde el 05-08 pero solo lo alimentaba el coach desde las fotos.

Todo lo que antes escribía un peso pasa ahora por ahí, y **con la fecha del hecho**, no la del
día en que se apunta: el reporte con la fecha del reporte, el check-in con la del check-in, el
ajuste del coach con la del pesaje (punto 27), el alta y las dos calculadoras con la suya. Son
**ocho** sitios. Cada punto lleva de dónde salió, porque no todos valen igual.

Reglas: un valor por día (si se anota dos veces el mismo día manda el último, que es una
corrección, no dos pesajes) y fuera de rango no entra (un peso de 700 kg no es un dato, es un
error de tecleo, y en una serie arrastra el modelo entero).

**Una diferencia con la letra del punto, a propósito.** El punto dice que el peso actual no se
almacene aparte «nunca». `weight` y `body_fat` siguen existiendo como campos porque los leen
decenas de sitios (el motor de macros, el agente, el chatbot, los informes), y quitarlos el fin
de semana antes de abrir es cambiar medio backend por gusto. Pero **ya no son un dato
independiente**: son un espejo que escribe *solo* `series_cliente.py` a partir del último de la
serie, así que no pueden discrepar de ella. El efecto es el que pide el punto - un solo peso en
toda la app - sin la cirugía. Está avisado en el modelo, encima de los dos campos.

**En pantalla**, la ficha del cliente ya lo enseña como pide el punto:

> **PESO** 103 kg · hace 19 días  **% GRASO** 30% · hoy

Y a menos de un mes dice «hace N días», «ayer» o «hoy»; a partir del mes, la fecha.

**Lo que esto desbloquea.** El punto dice que de 162 clientes solo 62 tienen el % graso en dos
momentos. Con las series construidas son **69**, y ahora además crece solo: el % graso del
check-in mensual, que hasta hoy se quedaba dentro del check-in sin llegar a ninguna serie, ya
entra. Sin dos momentos no hay eje respondedor que medir, así que esto era el tapón.

**Los que ya estaban.** `backend/_rellenar_series_peso_grasa.py` construye las series de los
clientes existentes juntando Calma, el historial de macros, los check-ins y los reportes. El
campo suelto de hoy, que no tiene fecha, solo se usa cuando el cliente no tiene ningún otro
punto (3 casos) y se apunta con la fecha del relleno: es el único dato que no se puede colocar,
y va el último para no perderlo. Simula por defecto. En dev: **173 clientes con serie**.

**Ojo para producción**: pasar el relleno **una vez**, después de desplegar.

### Punto 31 - Marcar qué macro se cambió en cada ajuste · CERRADO

**La mitad ya estaba, y conviene decirlo.** El historial **ya pintaba en rojo lo que cambió**
desde el 05-08 (era la petición del vídeo, minuto 1:47). Pero lo calculaba **en pantalla**,
comparando cada fila con la de abajo, y no se guardaba en ningún sitio. Así que la otra mitad
del punto - la que de verdad falta - es la que dice Jesús: **el modelo no sabe qué palanca se
movió en cada ajuste**. En el histórico estaban los ocho números de antes y los ocho de
después, pero no la decisión.

**Lo que hay ahora.** `backend/core/cambios_macros.py`. Al guardar un ajuste se calcula un
booleano por macro comparando con lo que el cliente tenía, y queda en la entrada del historial:

```
{"entreno":     {"proteina": false, "hidratos": true,  "grasa": false},
 "perientreno": {"proteina": false, "hidratos": false},
 "descanso":    {"proteina": false, "hidratos": false, "grasa": true}}
```

Se rellena en los **cinco** sitios donde se guarda un ajuste, y también al corregir una entrada
antigua - si no, el rojo seguiría señalando lo de antes de la corrección. No toca ningún
cálculo, como pide el punto.

Dos decisiones de criterio:

- **Estrenar no es cambiar.** Si antes no había perientreno y ahora lo hay, no se marca:
  marcarlo en rojo en veinte filas seguidas es ruido, no información.
- **Sin anterior, no hay booleano** (se guarda `null`, no `false`). En el primer ajuste de un
  cliente no es que no haya cambiado nada: es que no había nada antes, y decir `false` sería
  mentir al modelo.

**En pantalla**, el historial usa ahora el dato guardado cuando lo hay, y sigue comparando con
la fila de arriba para las entradas viejas y para la fila sin guardar. Comprobado en el
navegador: el rojo pinta exactamente lo mismo que antes del cambio, fila por fila.

**Al modelo**, cada ajuste del histórico le llega ahora con una línea nueva: `movió:
entreno.hidratos, descanso.grasa`. Antes tenía que deducirlo comparando dos filas de números.

**Los que ya estaban.** `backend/_rellenar_cambios_macros.py` los calcula hacia atrás usando
`previous_training`/`previous_rest`, que ya se guardaban en cada entrada (más fiel que comparar
con la fila anterior), y cayendo a la entrada anterior para el perientreno y para las
importadas de Calma. **3.251 de 3.427 ajustes** rellenados; 176 no tienen nada anterior.

**Y de paso sale un dato que no teníamos**: qué palanca mueve Jesús, en todo el histórico.

| Palanca | Veces |
|---|---|
| entreno.hidratos | 2.638 |
| descanso.hidratos | 2.576 |
| perientreno.hidratos | 1.350 |
| descanso.grasa | 1.303 |
| entreno.grasa | 1.020 |
| descanso.proteina | 931 |
| entreno.proteina | 797 |
| perientreno.proteina | 582 |

Los hidratos son la palanca, y la proteína casi no se toca - que es exactamente el método. Sirve
de comprobación de que el cálculo está bien, y es material para la revisión de las reglas del
agente que Jesús dejó pendiente. **Ojo: esto es dev**, con el ruido del harness de simulación
dentro; el número bueno saldrá al pasarlo en producción.

### Punto 32 - El semáforo, por celda y con cinco niveles · CERRADO

**Lo que pasaba.** «EN RIESGO» era binario: activo, semana ≥ 3 y sin reporte en 14 días.
Saltaba para el 76% de los activos, o sea que no era una alerta: era el color de fondo de la
pantalla. Y no decía **en qué**.

**Lo que hay ahora.** `backend/core/semaforo.py`: cinco estados - `ok`, `regular`,
`regular_malo`, `malo`, `info` - aplicados **por celda**. El backend devuelve por cada celda
un objeto `{valor, estado, texto, detalle}` y la tabla solo pinta. Un objeto y no
`"valor|color"` en una cadena, como avisa el punto: en cuanto haya que ordenar por la columna
o filtrar por estado, la cadena hay que romperla otra vez, y quien la rompe se equivoca.

Cinco celdas por cliente: **reporte**, **ajuste**, **contacto**, **peso** y **pago**.

**Los plazos salen del plan, no son generales.** Cada celda se mide contra la cadencia de su
plan (7, 14 o 28 días), no contra un 14 fijo para todos. Es el criterio que ya estaba escrito
para la columna de contacto y vale igual para todo: «al de 1.500 con llamada semanal, quince
días es un escándalo; al de 897 con reporte quincenal, no tanto». Los escalones son 1x el
plazo (ok), 1,5x (regular), 2x (regular-malo) y más (malo). **Esos multiplicadores son una
propuesta mía**: hacían falta unos números para poder enseñarlo, están juntos y con nombre al
principio del módulo, y los tiene que repasar Jesús.

**`info` no es un estado peor ni mejor**: es «esta casilla no cuenta para este cliente». Al de
autogestión no se le acompaña por chat, así que pintarle el contacto en rojo todos los días
sería ruido. Va en gris apagado, no en un color de aviso.

**Dos cosas que me salieron mal por el camino y conviene que consten**, porque las dos daban
el resultado que el punto quiere evitar:

1. **«Nunca» no puede ser malo por sí solo.** La primera versión pintaba en rojo a todo el que
   no hubiera mandado nunca un reporte, y saltaba para el 97%. Al cliente que entró el lunes
   todavía no le toca mandar el primero. Ahora, cuando algo no ha pasado nunca, el reloj se
   cuenta **desde que empezó** y el estado sale de ahí igual que en los demás; lo único que
   cambia es el texto, que dice «nunca» en vez de los días.
2. **Un resumen por fila reproduce la alerta binaria.** Con cinco celdas, «tiene alguna en
   regular-malo o peor» vuelve a ser cierto para casi todos. Por eso el panel ya no da una
   cifra sola: da **el desglose por celda**, que es lo accionable.

**Y un fallo de verdad, encontrado por no fiarme del número**: el panel decía 222 con algo en
rojo, pero la suma por celda daba como mucho 203. No cuadraba. Era que la consulta del panel no
traía el campo `status`, y `has_active_access` lo lee, así que **daba «pago pendiente» a los 228
clientes**. Corregido.

**Cómo queda, con los datos de dev (228 activos):**

| Celda | ok | regular | regular-malo | malo | info |
|---|---:|---:|---:|---:|---:|
| reporte | 64 | 51 | 32 | 78 | 3 |
| ajuste | 84 | 116 | 8 | 20 | 0 |
| contacto | 53 | 135 | 2 | 33 | 5 |
| peso | 85 | 43 | 28 | 72 | 0 |
| pago | 228 | 0 | 0 | 0 | 0 |

**Con alguna celda en rojo: 93 de 228, el 41%** - contra el 76% de la etiqueta vieja. Y ahora
además se sabe de qué: el panel pone «reporte 78 · peso 72 · contacto 33 · ajuste 20».

**En pantalla**, comprobado en el navegador: en la lista de clientes cada celda va con su
color, y se lee de un vistazo la diferencia entre un cliente nuevo (13 días sin ajuste en
ámbar, sin reporte todavía en ámbar, peso de hoy en verde) y uno abandonado (78 días en rojo,
sin reporte en rojo, nunca contactado en rojo).

### Punto 33 - Los protocolos de suplementación, versionados por fecha · CERRADO

**Lo que pasaba.** Había UN protocolo por cliente que se pisaba a sí mismo en cada guardado. No
quedaba registro de qué tomaba en cada momento, y lo de «siguiente + siguiente_fecha» era un
apaño para poder dejar uno preparado.

**Lo que hay ahora.** Una lista de versiones `{fecha, items, nota}` que se resuelve por la más
reciente que no pase de hoy - exactamente igual que los macros. Eso da las tres cosas de golpe:
se puede editar, queda el histórico, y dejar uno preparado para el futuro es simplemente una
versión con fecha futura.

Los dos bloques de la pantalla siguen siendo los mismos, pero ahora **cada uno tiene su fecha**:
«Lo toma desde el día» y «A partir del día». Y **corregir una dosis no abre una versión nueva**:
se corrige la vigente. Abrir una versión es una decisión, y para eso está la fecha.

Sobre lo de «guarda el protocolo como una lista de verdad, no como `"3|7|12"` en un texto»: eso
ya estaba bien. Cada suplemento es un objeto con su título, dosis, momento y observaciones,
editables aunque venga del catálogo.

**Comprobado en la app**, entrando como Francisco y usando la pantalla:

| Qué se hizo | Qué pasó |
|---|---|
| Creatina desde el 08/08 y Omega 3 desde el 07/09 | Histórico con 2 versiones: una «LO TOMA AHORA» y otra «PREPARADO» |
| Qué ve el cliente hoy | Creatina (no el Omega 3, que aún no le toca) |
| Corregir la dosis a «5 g al despertar» | Se guarda y **siguen siendo 2 versiones** |
| Borrar la versión del 07/09 | «Versión borrada», el histórico pasa a 1 y la vigente se queda |

Y la resolución por fecha, comprobada día a día: el 01/08 no tomaba nada, del 08/08 al 06/09
creatina, y del 07/09 en adelante Omega 3.

**Una cosa que me pasó y que vale la pena anotar**: la primera vez di por hecho que la edición
de la dosis no se guardaba, porque había escrito en el campo desde la consola en vez de con el
teclado. Con el teclado sí se guarda. Es exactamente el motivo por el que Francisco pidió
comprobar contra la app real: simular el evento se ve igual en pantalla y miente.

**Los que ya estaban.** `backend/_migrar_protocolos_suplementos.py` traduce los documentos
viejos: `actual` pasa a una versión con la fecha de su último guardado (es lo más cercano a la
verdad que hay: no se sabe desde cuándo lo tomaba, pero sí desde cuándo consta) y `siguiente` a
una con `siguiente_fecha`, que es literalmente lo que significaba. **En dev no hay ningún
protocolo asignado**, así que el script no ha tenido nada que migrar; hay que pasarlo en
producción, donde sí puede haberlos.

### Punto 34 - El entrenamiento en su propia pestaña · A MEDIAS, Y LO QUE FALTA ES UNA DECISIÓN

**En el flujo del entrenador ya está separado.** La ficha del cliente tiene diez pestañas y
**Entreno** es una de ellas, aparte de **Nutrición**: ahí están la maquinaria, las lesiones, las
observaciones de entrenamiento y la generación de la rutina. Se separó el 05-08 con el punto
2.5, y el comentario del código lo dice con las palabras de Jesús: «el entrenamiento lo llevo
aparte de la nutrición». Y en el menú del coach hay una sección **Rutinas** propia.

**En la app del cliente no hay pestaña de entrenamiento, y no es un descuido.** Comprobado en el
navegador: el menú del cliente es Novedades · Inicio · Nutrición · Alimentos · Ajustar macros ·
Suplementos · Asistente IA · Reportes · Check-ins. **No hay Rutina porque está oculta a
propósito** desde el 19-07-2026, «hasta completar la funcionalidad» (`planAccess.js`, línea 19).
Oculta el menú, la tarjeta «Entreno de hoy», el paso del tour y la ruta directa.

Así que lo único de entrenamiento que le queda al cliente delante es el selector
**Entreno / Descanso** de la pantalla de Nutrición - que es exactamente lo que Jesús está
viendo cuando dice que está mezclado.

**Y ese selector tiene que quedarse donde está.** No es desorden: los macros del día dependen de
si entrena o no, y el reparto de las comidas también. Sacarlo de Nutrición rompería el método.

**Decidido por Francisco el 08-08**: «no la reactives aún, puedes dejarla del lado del
entrenador pero no del cliente». Así que se queda como está - y eso obliga a rematar algo que
faltaba.

**Lo que había suelto: al cliente se le seguía hablando de la rutina.** Tres sitios le mandaban
avisos sobre una pantalla que no puede abrir:

- «Mañana empiezas · **Tu rutina ya está cargada**», con enlace a `/dashboard/routine`
- «**Tu rutina acaba el 12 de agosto** · Renuévala y sigue sin parar»
- «**Tu coach te ha preparado una rutina nueva**», cada vez que el entrenador le asignaba una

Los tres llevaban a una ruta que le devuelve al panel. Un aviso que no lleva a ningún sitio le
enseña al cliente a ignorar los avisos - y son los mismos por los que se entera de sus macros.

**Lo que hay ahora.** Una constante en el backend, `RUTINA_VISIBLE_PARA_EL_CLIENTE` en
`core/plan_access.py`, gemela de `CAP.RUTINA` del front: se encienden las dos juntas el día que
se reactive. Con ella apagada, el aviso de la rutina nueva no se manda, el de «tu rutina acaba»
tampoco, y el de «Mañana empiezas» se queda pero **sin prometerle lo que no va a ver** y
apuntando a su panel.

**El entrenador no pierde nada.** Comprobado en el navegador: su sección **Rutinas** sigue
entera (232 clientes, buscador, filtro «solo sin rutina», columnas de rutina, días de entreno y
generada), la pestaña **Entreno** de la ficha sigue generando y guardando rutinas, y la columna
«Sin rutina» del panel semanal sigue contando. Lo único que se apaga es lo que el cliente ve y
lo que se le dice.

Y comprobado también que `/dashboard/routine` escrito a mano **devuelve al cliente a su panel**,
no al login - que es el fallo que se arregló en el punto 10 y que aquí no se repite.

---

### Punto 35 - Las medidas comparadas · CERRADO

**Lo que pasaba.** Las diez medidas solo se veían sueltas: el último dato debajo de su foto en
la comparativa, y al rellenar el reporte la diferencia con el mes pasado. Nunca se veían las
diez a lo largo del tiempo, que es lo único que dice si algo se mueve - y es justo la razón por
la que se piden todas siempre.

**Lo que hay ahora.** En Seguimiento, debajo de la evolución del peso, la tabla **Evolución de
las medidas**: una fila por medida, una columna por toma, la diferencia con la toma anterior al
lado de cada número, y una columna **Total** con el cambio desde la primera.

Tabla y no gráfico a propósito: son diez series a la vez y en un gráfico de diez líneas no se
lee ninguna.

Tres decisiones de criterio:

- **En azul lo que sube, en verde lo que baja, y sin juzgar.** Subir de brazo y subir de cintura
  no son lo mismo, y eso lo pone el coach, no el color. Es el mismo código que ya usaba el
  reporte del cliente.
- **La medida que no ha dado nunca no ocupa una fila.** Con diez medidas y clientes que vienen
  de dar cinco, media tabla en blanco no es información.
- **Se enseñan las 8 últimas tomas y se dice cuántas quedan fuera.** Cortar en silencio haría
  pensar que eso es todo lo que hay.

Respeta los nombres viejos de Calma para la cintura y la cadera, que es lo único que se puede
traducir sin inventar (ya estaba decidido así en `lib/medidas.js`).

**Comprobado en la app** con tres tomas de prueba en el cliente de pruebas, borradas después: la
tabla sale con las diez medidas, las diferencias parciales (+0,3) y el total (+0,6), y cintura y
cadera en verde con -1,6 mientras el resto sube.

---

## Bloque E - Los planes

Doce puntos. **Cuatro ya estaban hechos** de documentos anteriores, uno se ha hecho ahora, y
siete son trabajo por delante. Lo primero fue medir contra la base de datos en vez de suponer.

### Punto 36 - El precio vive en el cliente · YA ESTABA

`client_profiles.price` existe y **es distinto dentro del mismo plan**. En dev, los clientes con
plan `gold` tienen precios de 0, 149 y 450 €. La tabla de planes trae un `precio` de referencia y
un `precio_nota` con el rango («450-847€/trimestre según antigüedad»), y de ahí se copia al dar
de alta - que es exactamente la plantilla que describe el punto. No está modelado como
*plan → precio*, así que los 43 clientes que avisa el punto no se rompen.

### Punto 37 - Dos Gold y dos Silver · YA ESTABA

Son códigos distintos en el catálogo: `reto12en12_gold` (1.500 €/trim) y `gold` (legacy, 450 €),
`reto12en12_silver` y `silver`. En la base los clientes están repartidos entre los cuatro, así
que la etiqueta que viaja en los datos no es «Gold» sino el código, y sí se puede saber cuál es.

### Punto 42 - Cada coach gestiona los suyos · YA ESTABA

Hecho el 06-08, y literalmente como lo pide el punto: el admin lo ve todo, el coach ve y edita
**los suyos y los que no tienen coach**, hay pestaña «Sin coach» de donde cualquiera puede
coger, y para cubrir a un compañero **se reasigna**. El mensaje del 403 lo dice así: «Este
cliente lo lleva otro entrenador. Si tienes que cubrirle, que te lo reasignen».

### Punto 43 - Los legacy, cerrados a altas nuevas · YA ESTABA

`planes_contratables()` solo devuelve los planes en estado `activo`, así que un legacy no se
puede contratar ni desde el checkout ni ofrecer en una renovación. Lo que sí puede el admin es
asignárselo a un cliente que ya lo tiene, y **eso tiene que seguir siendo así**: con 43 clientes
legacy, si un plan se pone mal no habría forma de arreglarlo.

### Punto 39 - Un campo de excepción por cliente · HECHO AHORA

Es el único de los cuatro imprescindibles que no existía, y el que ya costó dinero.

**Texto libre a propósito.** Las 17 excepciones no se parecen entre sí - uno cuya membresía paga
su marido, uno que paga en efectivo, uno al que no se le genera rutina, uno que no paga nada y
aun así se le hace, uno con ciclo de 4 semanas, otro al que se le manda el reporte por WhatsApp.
Modelarlas con casillas sería inventarse las categorías antes de conocerlas, y la de la número 18
no entraría en ninguna.

**Dónde salta**, que es la mitad que evita el problema:

1. **Arriba en la ficha**, antes de las pestañas y sin poder plegarse. Si hay que abrir algo para
   verla, está tan escondida como en la hoja de la que viene.
2. **En Membresía, debajo del precio y del próximo cobro**: «⚠ Antes de cobrarle: …». Es
   exactamente el sitio del caso que costó dinero.
3. **En el diálogo de guardar macros y de guardar suplementación**, en la primera línea.
4. **En la lista de clientes**, un triángulo naranja junto al nombre con la excepción en el
   tooltip. Si solo estuviera dentro de la ficha, para saber quién tiene una habría que entrar en
   las 232 - o sea, lo mismo que tenerlas en una hoja.

Y la cadena vacía significa «quitar la excepción», que necesitó su propia línea en el backend: el
PUT descarta los campos nulos, y sin eso el coach borraba el texto, le decía guardado y la
excepción seguía ahí.

**Comprobado en la app**: escrita una excepción en un cliente, sale arriba en naranja, sale en
Membresía debajo del próximo cobro y sale como triángulo en el listado (y los demás clientes no
lo tienen). Borrada al terminar.

### Punto 38 - Los planes antiguos entran tal cual · HECHO A MEDIAS

No hay ninguna conversión automática: cada cliente conserva su plan. Pero al comprobarlo contra
la base salió un **plan huérfano**: hay perfiles con el plan escrito `"CalMa"` tal cual, con esas
mayúsculas, y **CALMA 12 no estaba en el catálogo**. Un plan que no casa con ninguna entrada deja
al cliente **sin ninguna habilitación**: ni reportes, ni suplementación, ni cadencia de revisión.
Es literalmente lo que avisa el punto - la app tiene que saber representarlos.

Arreglado: CALMA 12 entra en el catálogo con las habilitaciones de un plan con coach detrás, y se
añade una tabla de alias (`codigo_de_plan`) para que la forma en que está escrito en los datos
migrados resuelva al código bueno. Comprobado: antes `CalMa` no daba ninguna feature; ahora da
macros, chat, rutina, reportes, mensual, suplementación y cardio, con revisión a 28 días.

### Punto 40 - 13 planes sin llenar el código de «if» · CERRADO

El patrón que pide el punto **ya era el nuestro**: los planes tienen `habilitaciones` y la app
pregunta `plan_grants_feature(plan, 'rutina')`, no por nombre. Meter un plan nuevo es tocar
datos. Auditado el código entero buscando decisiones por nombre de plan:

**El backend está limpio.** Los únicos sitios con nombres de plan escritos son los scripts de
migración y de pruebas, que es donde tienen que estar. **Menos uno**: al convertir un lead en
cliente, el plan por defecto era `"gold"` - legacy desde el 31-07. Cada lead convertido sin decir
el plan entraba en un plan que ya no se vende, con el precio de referencia de otra época.
Ahora el plan es obligatorio y tiene que ser uno de los contratables; si no, el error dice
cuáles son y recuerda que el plan viejo se puede poner después desde la ficha.

**El frontend tenía tres.** Los tres arreglados:

| Dónde | Qué pasaba |
|---|---|
| Filtro de la lista de clientes | Cableados Gold, Silver, Bronze y ELM. Con 17 planes en el catálogo, **había 13 por los que no se podía filtrar** - entre ellos los tres niveles nuevos, con los que entra todo el mundo desde ahora |
| Convertir un lead | Cableados los mismos cuatro, todos legacy |
| «Mejorar mi plan» del perfil | Decide con `profile.plan !== 'gold'` y ofrece «Gold, 149€/ciclo» - un plan que ya no se contrata a un precio que no es el suyo |

Los dos primeros salen ya del catálogo. El tercero **está apagado** (`UPGRADE_PLAN_UI = false`)
desde julio y se queda apagado, pero con un aviso escrito encima: el día que haya checkout de
upgrade, no se puede encender tal cual.

### Punto 41 - Qué ve el que no renueva · CERRADO

**Lo que pasaba.** Al cliente que llevaba un año pagando y terminaba su ciclo se le enseñaba
**la misma pantalla que al que acaba de registrarse**: «Bienvenido a 12EN12 · Para comenzar tu
transformación, selecciona un plan». No es lo mismo no haber empezado que haber terminado.

**Lo que hay ahora.** El servidor dice *por qué* no tiene acceso y no solo *que* no lo tiene:
`sin_plan`, `sin_pagar` o `caducado`. Con eso, al caducado se le enseña lo que pide el punto,
copiado de la calculadora antigua: **«Tu suscripción ha caducado»**, con quién escribir y el
chat de WhatsApp abierto con el mensaje ya redactado - si hay que escribirlo, la mitad no
escribe. Y debajo, la alternativa de la que se habló: seguir con la Membresía.

Comprobados los siete casos: sin perfil y perfil sin plan dan `sin_plan`; checkout a medias da
`sin_pagar`; baja, ciclo terminado y suscripción cancelada dan `caducado`. **Y salió un fallo de
paso**: un perfil `activo` pero **sin plan** daba acceso, porque `has_active_access` mira el
estado y la suscripción pero no si hay plan. Corregido.

**Falta el número de WhatsApp de soporte**: no está en ninguna parte del código y no me lo puedo
inventar. Hasta que Francisco lo diga, el bloque sale sin el botón en vez de con un enlace que no
lleva a nadie. Es una constante, `WHATSAPP_SOPORTE`.

### Punto 45 - Meter un reporte en nombre del cliente · CERRADO

Los Premium mandan el reporte y las fotos por WhatsApp y alguien del equipo se lo pasa a la app.
Hasta ahora eso solo se podía hacer **entrando con la cuenta del cliente**, que es literalmente
lo que describe el punto («subiendo las fotos con el correo del cliente para que se enlacen a su
ficha»).

Dos rutas nuevas:

- `POST /admin/clients/{id}/reporte` - el reporte en su nombre. **No comprueba la ventana de
  envío ni que el plan incluya reportes**: si el equipo lo está metiendo es porque ya llegó por
  otro lado, y bloquearlo por el calendario no protege nada. El peso va a su serie con la fecha
  del reporte (punto 30) y queda marcado con **quién lo metió**.
- `POST /admin/clients/{id}/reports/photos` - las fotos en su nombre, a la misma colección y con
  las mismas validaciones que las del cliente (se sacaron a una función común para que no puedan
  divergir). Queda anotado quién las subió.

**Y la pantalla**, en Seguimiento: un enlace discreto - **«Meter un reporte por él (llegó por
WhatsApp)»** - que abre el formulario. Peso, el objetivo que marca, las diez medidas plegadas
(en WhatsApp no siempre llegan todas), las fotos con su pose y un hueco para pegar lo que ha
escrito. Va plegado porque no es lo normal: se abre cuando toca.

**Comprobado en la app**, metiendo un reporte de verdad y borrándolo después. Y lo importante es
que se encadena con todo lo demás:

| Qué pasó | |
|---|---|
| El reporte | guardado con `metido_por: Francisco` y `origen: lo metio el equipo` |
| El peso | entra en su serie con origen «reporte (lo metió el equipo)» (punto 30) |
| El peso de la ficha | pasa a 84,2 - el último de la serie |
| `ultimo_reporte` | actualizado, así que cuenta para el semáforo (32) y para «quién me toca» (29) |

O sea que un reporte que llega por WhatsApp ya no se queda fuera de nada.

### Punto 47 - Los ajustes cada 2 semanas, validados · CERRADO

Al mandar el reporte, el cliente veía «Reporte enviado correctamente», que no le dice nada: ni si
tiene que hacer algo, ni cuándo tendrá sus macros. Ahora ve **«Estamos revisando tus respuestas.
En menos de 48 horas recibirás tus nuevos macros»**, con **24 en el Nivel 2**, y las horas salen
del plan y no de un número escrito a mano - es una de las cosas que tienen que notarse entre
niveles (punto 46).

Que espere y que se lo ponga una persona es parte del producto, así que el texto no promete nada
automático.

**Y el % graso, cada 12 semanas y no cada 2.** La calculadora del cliente le exigía el % graso
en **cada** ajuste, y los ajustes son quincenales: **seis veces por ciclo**. Un dato que se
estima a ojo mirando fotos no cambia cada quince días, y preguntarlo tan seguido solo consigue
dos cosas - que lo repita igual sin mirarlo, o que se lo invente.

Ahora el servidor dice cuál es su % graso vigente y si ya toca pedirlo, y la pantalla lo enseña
en vez de pedirlo:

> **% GRASO**  8%  ·  *cambiar*
> De esta semana. Se vuelve a pedir a las 12.

Con el botón de cambiarlo si de verdad quiere, y a las 12 semanas se le vuelve a pedir. Sale de
la serie del punto 30, que es la que sabe de cuándo es cada dato.

### Punto 44 - El calendario y la duración, como propiedad del plan · CERRADO

**Lo que había.** La cadencia estaba escrita en el código: un mapa con el día de cada tipo y una
función con tres `if` («quincenal si la semana es par, mensual si semana % 4 == 3, semanal
siempre»). Los números eran los buenos - coinciden con lo que dice el punto, incluso las semanas
- pero meter un plan con otro ritmo era tocar código, y **el ciclo de Premium no se podía
expresar de ninguna manera**.

**La idea que lo resuelve todo**: cada plan declara un **patrón de semanas que se repite**. Es
como lo describe Jesús para Premium - «S1 check-in semanal, S2 check-in semanal, S3 reporte
mensual, S4 check-in semanal; en planes más largos se sigue repitiendo esa lógica» - y resulta
que con eso se modelan los demás también:

| Plan | Patrón |
|---|---|
| Gold | `["", "quincenal", "mensual", "quincenal"]` |
| Silver | `["", "", "mensual", ""]` |
| ELM y Reto 60 días | `[]` |
| Premium | `["semanal", "semanal", "mensual", "semanal"]` |

Los patrones **no hay que escribirlos**: se deducen de los reportes que ya declara cada plan, así
que los 17 siguen igual sin tocarlos, y el que quiera otro ritmo pone el suyo. El día de envío
también sale del plan y se puede cambiar sin tocar código.

**Comprobado que no cambia nada para nadie**: comparado el patrón nuevo con la regla vieja, plan
a plan y semana a semana durante 24 semanas → **cero diferencias**. Y los **188 tests** de
planes, cadencia y renovación siguen pasando.

Cómo queda, semana a semana:

```
GOLD     S1:-    S2:quin S3:mens S4:quin S5:-    S6:quin S7:mens S8:quin ...
SILVER   S1:-    S2:-    S3:mens S4:-    S5:-    S6:-    S7:mens S8:-    ...
ELM      S1:-    S2:-    S3:-    S4:-    S5:-
PREMIUM  S1:sema S2:sema S3:mens S4:sema S5:sema S6:sema S7:mens S8:sema ...
```

**La duración, del contrato.** Tres campos nuevos en el cliente, vacíos por defecto: su
`ciclo_semanas` (hay planes de 4 semanas y de 5, y clientes con un ciclo distinto al de su plan -
es una de las 17 excepciones del punto 39, y ahora tiene dónde vivir), su `semana_de_entrada` y
su `calendario_reportes` propio si no sigue el de su plan. Todos pisan al plan, que es lo que
manda el punto 36: la tabla de planes es la plantilla, el contrato es lo que vale.

**Y aquí me equivoqué, y conviene que conste.** «Los de 4 semanas entran cuando están en Semana 3
y los de 5 cuando están en Semana 4» admite dos lecturas: que el patrón empiece desplazado, o que
las primeras semanas no le toque nada. Implementé la segunda y al probarla **Gold se quedaba sin
ningún reporte hasta la semana 11** - veintidós clientes en silencio dos meses y medio. Eso no
puede ser lo que pide un documento cuyo propio ejemplo es «quincenal el miércoles de la semana
2». Así que va como **desplazamiento** y **vacío por defecto**: con el campo vacío el patrón
empieza en la semana 1, que es lo que la app hacía hasta hoy y nadie cambia de comportamiento.

**Que Jesús aclare qué significa «entrar en el ciclo»**; el campo ya está y es cambiar un número.

### Punto 46 - Que se note la diferencia entre niveles · CASI CERRADO

Al mirarlo punto por punto salió que la mitad estaba y la otra mitad tenía **dos fallos de
verdad**, no cosas por hacer.

**Lo que ya estaba:** las horas de espera (24 en Nivel 2, 48 en el resto, hecho con el punto
47), el Nivel 3 sin botón de compra directa, el formulario de nombre+teléfono con aviso al
equipo… y la vía de cobro con tarjeta después de la llamada, que el punto da por inexistente y
**existe desde el 03-08**: en el panel, la llamada pendiente tiene un botón que genera el enlace
de pago del Nivel 3 y lo copia para mandarlo por WhatsApp.

**Fallo 1: la página de venta prometía algo que el plan no daba.** El punto dice que el Nivel 3
lleva **reporte semanal**, y la tabla de `/planes` ponía «Seguimiento: Semanal»… pero en el
catálogo el Nivel 3 tenía `["quincenal", "mensual"]`, o sea **exactamente lo mismo que el Nivel
2**. Quien pagara 1.500 € habría recibido la cadencia del de 897 €.

Corregido a `["semanal", "mensual"]`. Y ahora que el calendario sale del plan (punto 44) esto
tiene efecto de verdad - los tres niveles por fin se distinguen en lo que reciben:

```
Nivel 1   S1:-    S2:-    S3:mens S4:-    S5:-    S6:-    S7:mens S8:-
Nivel 2   S1:-    S2:quin S3:mens S4:quin S5:-    S6:quin S7:mens S8:quin
Nivel 3   S1:sema S2:sema S3:mens S4:sema S5:sema S6:sema S7:mens S8:sema
```

Comprobado en `/planes`: la fila de Reportes dice **mensual · quincenal + mensual · semanal +
mensual**. La tabla y el plan por fin dicen lo mismo.

**Fallo 2: «Agendar una llamada» llevaba al chat.** El botón del Nivel 3 hacía
`navigate('/dashboard/messages')`: el que quería el plan de 1.500 € acababa en el chat, **no
dejaba su teléfono y al equipo no le llegaba ningún aviso**. El flujo bueno ya existía -- nombre,
teléfono y franja horaria, cayendo en «Piden llamada» del panel -- pero **solo desde el test de
nivel**, no desde la página de planes, que es justo donde va el que ya se ha decidido.

Ahora abre el mismo formulario: **«El Nivel 3 se contrata hablando»**, con nombre, teléfono y
«¿cuándo te viene bien?». Cae donde las del test, así que sale en el panel y lleva su botón de
generar el enlace de pago. Comprobado en la app.

**Lo que queda, y es montar producto nuevo:** que el Nivel 1 pueda **comprar la rutina del mes
suelta** (55 €) y **contratar una llamada**, y que el Nivel 3 pueda contratar **llamadas con Jesús
a un precio más alto**. `rutina_mes` está en el catálogo como complemento pero **no aparece en
ninguna ruta del backend ni en ninguna pantalla**: no hay forma de comprarlo. Y de las llamadas
sueltas no hay nada. Las tres cosas son producto y cobro nuevos en Stripe, no un arreglo.

---

### Lo que queda del bloque E, y por qué

- **Del punto 46 solo quedan los productos sueltos**: comprar la rutina del mes (55 €) y
  contratar llamadas. Es producto y cobro nuevos en Stripe, no un arreglo.

### Una discrepancia que no toco sin que Jesús diga

El catálogo del equipo (27-05) marca como **Activos** a ELM, Reto 12en12 Gold y Silver, Reto 60,
Calculadora JP y Mantenimiento. En nuestro código están como **legacy** desde el 31-07, cuando se
decidió que «los tres niveles son lo único que se puede contratar».

Puede que las dos cosas sean ciertas y que «Activo» en esa tabla signifique **vivo, con gente
pagando** y no **a la venta**. La tabla es un inventario: incluye «Rutina del Mes · Suelto · 0
clientes». Pero si lo cambio, esos seis planes **aparecen en el checkout** junto a los tres
niveles, y eso contradice de frente al documento del 31-07. **No es una decisión mía**: que Jesús
diga si ELM y Reto 12en12 se pueden volver a contratar hoy, o si solo hay que seguir
manteniéndolos.

---

---

---

## Bloque F - La comparativa de fotos del reporte

Siete puntos. **La mitad ya estaba** del documento del 05-08 (punto 3.2), y al comprobar la otra
mitad salieron **tres fallos** que no estaban en el documento.

### Puntos 48, 49 y 50 - Las etiquetas, la rotacion y no repetir · YA ESTABAN

Las cuatro etiquetas (`inicial`, `inicio_fase`, `mes_anterior`, `actual`), la regla de que la
inicial no se mueve de la izquierda y la de fusionar cuando dos etiquetas apuntan a la misma
foto: todo eso se hizo el 05-08 y vive en `lib/comparativaFotos.js`, compartido con el informe
del cliente (`core/informe_mensual.py`). El numero de fotos sale solo y cuadra con la tabla del
punto 49: mes 1 -> 1, mes 2 -> 2, mes 3 en adelante -> 3, y 4 solo tras un cambio de fase.

Comprobado en la app con un cliente de una sola sesion: la foto sale con **«DE DONDE VENGO ·
COMO ESTOY HOY»**, las dos etiquetas en la misma foto, una sola vez. Que es el mes 1 de la tabla.

### Punto 51 - Los dos botones · YA ESTABA

«Ampliar comparativa» agranda y saca el resto de poses (por defecto solo de frente) y «Mostrar
todas» despliega el historico entero. Los dos estan y hacen cosas distintas.

### Punto 53 - El % graso NO se pide todos los meses · CERRADO

El punto dice «hoy la app lo pide cada mes», y era verdad: el **check-in mensual** tenia un campo
«% Grasa» que le salia al cliente cada cuatro semanas.

Quitado. Es un dato que estima Jesus mirando las fotos, y solo en tres momentos - al principio,
al empezar una fase y al acabarla -, y para eso ya esta el campo que hay **debajo de cada foto de
la comparativa**, que es donde el coach lo esta mirando. Pedirselo al cliente cada mes lo
convierte en ruido: nadie nota su cambio en cuatro semanas, asi que repite el mismo numero o pone
uno al azar, y ese ruido entra luego en el eje respondedor del perfil.

El backend lo sigue aceptando por si llega de una version vieja: si alguien se molesto en
ponerlo, no se tira. Comprobado en la app: el check-in mensual pasa a ser **«Peso y medidas»** y
ya solo pide el peso y las diez medidas.

### Punto 54 - Las dos cosas que no pueden pasar · CERRADO

- **Comparar solo contra el mes pasado**: no pasa. La inicial esta siempre, por diseño.
- **Generar el informe sin fotos**: en el informe del cliente **ya estaba resuelto** y me
  equivoque al darlo por roto. El backend no genera el informe sin fotos - devuelve
  `generado: false` con motivo `sin_fotos` - y el cliente ve «Tu informe esta a una foto» con un
  boton para subirlas. Llegue a anadir un hueco para ese caso; era codigo muerto, no se alcanza
  nunca, y lo he quitado.

  Donde **si** pasaba es en la **ficha del coach**: la comparativa hacia `return null` y
  **desaparecia entera**, asi que el coach abria Seguimiento sin saber si es que no hay fotos o
  si la pantalla esta rota. Ahora lo dice: «Todavia no hay fotos suyas. Sin fotos no hay
  comparacion, y sin comparacion esta pantalla no dice gran cosa».

### Punto 52 - Lo que va debajo de cada foto · CERRADO, y con dos arreglos

Fecha, peso y % graso ya estaban. Las medidas **no**: salian **las tres primeras del objeto**, o
sea las que cayeran, y con su nombre interno (`brazo_d 38 cm`). Ahora salen **cintura y cadera**,
que son las que se miran al lado de una foto, con su nombre de verdad, y las demas en el tooltip:
debajo de una foto de un cuarto de ancho no caben diez filas, y la comparacion completa ya la da
la tabla de evolucion de medidas del punto 35, justo encima.

**Y un fallo de la propia pantalla, encontrado al mirarla**: la rejilla se repartia entre las
fotos que hubiera, asi que **con una sola foto la comparativa ocupaba la pantalla entera** y
habia que hacer scroll para pasar de ella - en la pantalla que, dice el bloque, «tiene que darlo
todo de un vistazo». Y una sola foto es el mes 1: **todo cliente que entre el lunes**. Ahora la
rejilla es siempre de cuatro columnas: cada foto ocupa lo mismo, van creciendo hacia la derecha
segun se tienen, y la inicial se queda a la izquierda, que es la regla de Jesus.

---

---

## Bloque G - Las tres preguntas que faltaban en el reporte

**Las tres estaban ya**, hechas el 05-08 (punto 5 de aquel documento), con los textos de Jesus y
sus opciones exactas. Lo que hacia falta era comprobar que **sirven para lo que dice cada punto**,
y ahi aparecio el que no.

### Punto 55 - «Proximo objetivo» · YA ESTABA, con un texto a medias

La pregunta esta, con Definicion / Volumen / Mantenimiento, y **dispara el cambio de fase**: al
guardar el reporte cambia `goal` en el perfil y fecha `fase_desde`, que es lo que luego usa la
comparativa de fotos para la etiqueta de inicio de fase. Sin ella un Nivel 1 no cambiaria de fase
nunca, que es exactamente lo que avisa el punto.

El texto de ayuda estaba recortado: «De cara a las proximas 4 semanas, que puede ser lo mismo o
puedes cambiar». Faltaban **«que hasta ahora»** y el **«(piénsalo bien)»**, que no es relleno: es
lo que hace que no se conteste en automatico, y esta es la pregunta que mueve la fase. Puesto
literal.

### Punto 56 - «¿Como de viable seria un nuevo ajuste?» · YA ESTABA, y llega a donde tiene que llegar

Las tres opciones son las suyas, y la respuesta **alimenta el margen que mira el asistente**
(`_margen_del_cliente`): si el cliente dice que necesita comer mas, el agente lo ve. Antes ese
margen solo salia del cuestionario inicial, que se responde una vez y envejece; ahora se
pregunta cada reporte.

### Punto 57 - «¿En que grado has cumplido con el entrenamiento?» · ESTABA A MEDIAS

La pregunta estaba y se guardaba, pero **la barra del informe seguia sin usarla**. Seguia
contando registros de entreno que **no existen**: la app guarda el plan de rutina, no las
sesiones hechas, y el check-in diario dejo de preguntarlo en julio.

El resultado era peor que no tener barra:

```
antes:  {'dias': 0, 'previstos': 16, 'pct': 0, 'color': 'rojo'}
```

A un cliente que hubiera entrenado los dieciseis dias se le ensenaba **0%, en rojo**.

Ahora la barra sale de lo que el contesta:

| Contesta | Barra |
|---|---|
| Todos los entrenos | 100% verde |
| Casi todos | 80% verde |
| La mitad | 50% ambar |
| Pocos | 25% rojo |
| Ninguno | 0% rojo |

**Y se dice de donde sale**: debajo pone «segun lo que nos contaste» en vez de «N de 16». «Lo
dices tu» no es lo mismo que «esta contado», y dar por medido lo que no lo esta es de las cosas
que hacen que un informe deje de creerse. Los 105 tests del informe siguen pasando.

---

## PENDIENTES

Todo lo que queda abierto, ordenado por quién tiene que mover ficha. **Actualizado el 8 de agosto**,
con los bloques A al G cerrados.

Del documento de Jesús están trabajados los puntos **1 al 57**. Quedan por leer los bloques H al
K: los arreglos de la base de alimentos (58-60), los fallos apuntados que siguen ahí (61-64), los
menús autoajustables (65-75) y el asistente de IA (76-80). **Todos son de este fin de semana**, y
dos de esos bloques (I y K) están marcados como imprescindibles para el domingo.

---

### 1 · Lo que hace falta que nos pasen para poder seguir

**Las preguntas del check-in diario** (punto 20). El documento de textos no las trae: solo cubre
el test de entrada, los cuatro mensajes del informe y dos notas. Hoy la app pregunta energía y
«ansiedad y hambre», que vienen del documento del 31-07 y que el punto dice que no son de Jesús.
**Hay que pedirle cuáles son las suyas.** La otra mitad del punto (que el cliente apunte lo que
ha comido) ya está hecha.

**El texto roto** (punto 16). El documento dice que está identificado en el de textos, y no lo
está: ese documento trae los textos buenos de las 12 pantallas, pero en ningún sitio señala cuál
está roto en la app. **Que Jesús diga cuál es.**

**Dónde está el lunes** (punto 26). El punto llegó sin el «Qué hacer» y el lunes no aparece por
ningún lado: la fecha del ajuste ya es mañana en dev y en producción, y en el código la única
regla del lunes (`calendario_arranque.py`) está desconectada. **Que Jesús diga en qué pantalla lo
vio**, o si lo que quiere es que un cliente nuevo arranque al día siguiente en vez de esperar al
lunes - que es un cambio de método y toca la facturación.

**Los fondos de pantalla del test** (punto 24). Jesús dice que ya los pasó por Drive. **No
aparecen**: no están en el disco y en Drive se buscó por cinco vías sin resultado. Hace falta el
enlace de la carpeta, su nombre exacto o desde qué cuenta se compartieron. El hueco en el código
ya existe (`public/portada-test.jpg`): en cuanto aparezcan es cuestión de minutos.

**El repositorio fuente de la calculadora antigua** (`jgl-calma-web-next`). Solo tenemos el
bundle compilado en `_calma_ref/`, que sirve para contrastar comportamiento pero no para leer el
código como lo describe el documento (rutas y números de línea). Hasta ahora no ha hecho falta. Y
ojo: el documento avisa de que el código que Jesús leyó es la versión 1.1.0 y producción va por
la 1.9.0, así que **antes de dar por bueno un «fallo del código antiguo» hay que comprobarlo
contra la calculadora de verdad**.

---

### 2 · Lo que espera una orden de Francisco

**Desplegar a producción.** Desde el punto 19 no se ha subido nada. En producción está todo hasta
el commit `8421e3b`; lo posterior está en GitHub y sin desplegar, esperando la orden: el punto
19, el test de entrada del documento de textos, las cuatro respuestas de la dieta, las dos reglas
nuevas del filtro, y los **puntos 23, 25 y 27 al 57** (los bloques D, E, F y G enteros).

**Y con ese despliegue, pasar cuatro scripts**, cada uno **una sola vez** y después de subir:

| Script | Punto | Si no se pasa |
|---|---|---|
| `_rellenar_fechas_seguimiento.py --escribir` | 29 | La columna «Sin tocar» sale «nunca» para todos |
| `_rellenar_series_peso_grasa.py --escribir` | 30 | La ficha sigue enseñando el peso sin fecha |
| `_rellenar_cambios_macros.py --escribir` | 31 | El modelo solo sabrá qué palanca se movió de aquí en adelante |
| `_migrar_protocolos_suplementos.py --escribir` | 33 | Los protocolos ya asignados no pasan al formato con fecha |

**Ojo con el de las series (30)**: en dev cambió el peso actual de **50 de 232 clientes**, porque
el de la ficha no era el último pesaje de verdad. En producción va a pasar lo mismo, y es lo que
se busca, pero **conviene avisar a Jesús antes de que lo vea**.

**El número de WhatsApp de soporte** (punto 41). Hace falta para el cliente cuya suscripción
caduca: la pantalla está montada y el mensaje redactado, pero el número no está en ninguna parte
del código y no me lo puedo inventar. Mientras tanto sale el aviso sin el botón. Es una
constante, `WHATSAPP_SOPORTE` en `ClientDashboard.jsx`.

**Borrar las 18 cuentas de prueba de producción** (punto 10). Todo preparado y probado en
simulación contra producción: `backend/_limpiar_datos_prueba.py`, que no borra nada salvo que se
le pase `--ejecutar`. `francisco@test.com` y la cuenta demo quedan fuera. **Dos de las 18 tienen
datos dentro** y por eso no se han tocado: `jose@test.com` (7 dietas, 1 reporte, 3 check-ins, 1
foto y 12 cambios de macros) y `prueba@mail.com` (1 reporte y 3 check-ins). Hay que decidir si se
borran esas dos también.

---

### 3 · Lo que tiene que decidir Jesús

**¿ELM y Reto 12en12 se pueden volver a contratar?** (bloque E). Su catálogo los da como
**Activos** junto a Reto 60, Calculadora JP y Mantenimiento; nuestro código los tiene como
**legacy** desde el 31-07, cuando se decidió que los tres niveles son lo único contratable. Puede
que las dos cosas sean ciertas y que «Activo» en su tabla signifique *vivo, con gente pagando* y
no *a la venta* - la tabla incluye «Rutina del Mes · Suelto · 0 clientes», o sea que es un
inventario. Pero si lo cambio, **esos seis planes aparecen en el checkout**. No es decisión mía.

**¿Qué es «entrar en el ciclo»?** (punto 44). «Los de 4 semanas entran cuando están en Semana 3 y
los de 5 cuando están en Semana 4»: ¿el patrón de reportes empieza desplazado, o las primeras
semanas no le toca nada? Va como desplazamiento y vacío por defecto, porque la otra lectura
dejaba a Gold **sin ningún reporte hasta la semana 11**. El campo ya está: es cambiar un número.

**Los 56 mínimos por categoría** (punto 7). El mapa existe y funciona, pero los valores vienen de
la calculadora antigua y él quiere revisarlos; lo cifra en media hora. La tabla lista para
repasar está en `_internos_proceso/minimos_por_categoria_para_jesus.md`.

**Los dos criterios del tercio conviven, y no coinciden.** La calculadora antigua tiene su propia
forma de decidir si la proteína de un cereal o de un fruto seco cuenta, y no es la del tercio:
sobre el catálogo entero discrepan en 69 alimentos. Hoy la app usa el criterio de Jesús para lo
que el cliente ve y guarda en su día, y el heredado en el buscador mientras monta la comida y en
las herramientas de menús. Funciona, pero el mismo alimento puede enseñar dos cifras de proteína
distintas según dónde se mire.

**Los alimentos con macros mal puestos** (punto 11). No hay que sacar del buscador los que tienen
los tres macros a cero - son la lechuga, el pepino, el konjac y los refrescos zero, y el método
los usa a propósito. Lo que sí descuadra un menú en silencio son los que tienen los macros
**mal**: una tortita de maíz de 7 g con 125 g de grasa (1149 kcal), un turrón de coco con 79 g de
proteína, varios panes con la ración puesta a 1 g. La lista la saca `backend/_auditar_catalogo.py`
ordenada por gravedad y con el enlace a la ficha del producto. **Los valores buenos hay que
mirarlos en la etiqueta: no se pueden inventar.**

**La proyección de composición corporal** que tiene la calculadora antigua y nosotros no: estima
semana a semana, por tramos de cuatro, cuánta masa grasa y cuánta magra cambia según el punto de
partida, y con eso valida si un objetivo de peso es alcanzable en un plazo. Nosotros solo
calculamos la composición de hoy. Nadie la ha pedido; encaja después del lunes.

---

### 4 · Lo nuestro, pendiente de terminar

**Los productos sueltos del punto 46**, lo único que queda del bloque E: que el Nivel 1 pueda
**comprar la rutina del mes** (55 €) y **contratar una llamada**, y el Nivel 3 **llamadas con
Jesús a un precio más alto**. `rutina_mes` está en el catálogo como complemento pero **no aparece
en ninguna ruta del backend ni en ninguna pantalla**: hoy no hay forma de comprarlo. Y de las
llamadas sueltas no hay nada. Las tres cosas son **producto y cobro nuevos en Stripe**, no un
arreglo, así que no entran en el fin de semana salvo que Jesús diga lo contrario.

**La ficha de un cliente con mucho histórico se queda colgada** (visto el 08-08). Abriendo la de
un cliente migrado de Calma con fotos, la página deja de responder y hay que abrir otra pestaña.
Con clientes normales va bien. No bloquea el fin de semana, pero **es de las que Jesús va a abrir
el lunes**: pinta a que se cargan todas las fotos del historial de golpe.

**Normalizar el plan `"CalMa"` en la base.** Hay perfiles con el plan escrito así, sin
normalizar. Ya no rompe nada - la tabla de alias lo resuelve al vuelo (punto 38) - pero el dato
sigue sucio y conviene pasarlo a `calma12` cuando toque tocar producción.

**Verificar con los ojos que el resultado del alta se ve entero** (punto 15). Está apretado y el
contenedor ya permite desplazarse, pero para comprobarlo de verdad hay que completar un alta
entera, y eso significa alterar una cuenta real o crear una nueva. Revisión de un minuto en
cuanto haya un alta de prueba a mano.

**Cuadrar el texto de «Ponme un día tipo. El de ayer, por ejemplo.»** El documento de textos lo
pide en la pantalla de la dieta; en la app hay un bloque que recoge lo mismo con otro texto y
otro formato.

**Verificar la regla del 20 % de la dieta reportada.** El documento de textos dice que lo de «con
lo que comes ahora, ¿mantienes, ganas o pierdes?» **modula hasta un 20 % y se aplica al final,
después de todos los demás modificadores**. Hay que comprobar que el motor lo hace así.

**Un test falla desde antes de tocar nada** (`test_search_foods_by_category`): al buscar por la
categoría de carnes aparece un «Caldo de cocido» que no es de esa categoría. Es un problema de
cómo está clasificado ese alimento, no del buscador.

**El día de descanso pierde hasta 0,2 g de hidratos** por el redondeo a 0,1 g de cada comida
(65 ÷ 4 = 16,25). No se ve, porque lo que se le enseña al cliente va redondeado a múltiplos de 5,
pero está ahí.

---

### 5 · Ya resueltos (se dejan por trazabilidad)

~~**Quién cobra el +20 % de «cómo engorda»** y **el umbral de grasa en mujeres**.~~ Resueltos el
07-08: Francisco confirmó que el texto del documento suplanta a todo lo anterior y se aplicó
literal (solo «casi no lo noto»; umbral 20 % sin distinción de sexo).

~~**Falta el documento «LOS TEXTOS DE LA APP»**.~~ Llegó el 07-08 por la noche. Con él se cerró
el punto 19 (las cuatro respuestas de la dieta) y se hizo el test de entrada entero.

~~**Los avisos de rutina llevan a una pantalla oculta.**~~ Resuelto el 08-08 con el punto 34:
Francisco decidió que la Rutina se queda del lado del entrenador y no se le enseña al cliente, y
con esa decisión se callaron los tres avisos que le hablaban de ella
(`RUTINA_VISIBLE_PARA_EL_CLIENTE`).

~~**¿Se le vuelve a enseñar la Rutina al cliente?**~~ Decidido el 08-08: no, todavía no.
