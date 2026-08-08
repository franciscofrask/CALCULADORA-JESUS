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

---

---

## PENDIENTES

Todo lo que queda abierto, ordenado por quién tiene que mover ficha. Actualizado el 7 de agosto
por la noche.

---

### 1 · Lo que hace falta que nos pasen para poder seguir

**Faltan 56 puntos del documento por leer: los bloques D al K.** De la versión actualizada solo
hemos visto hasta el punto 20. Sin ver quedan el flujo del entrenador (25-35), los planes
(36-47), la comparativa de fotos del reporte (48-54), las tres preguntas del reporte (55-57),
los arreglos de la base de alimentos (58-60), los fallos apuntados que siguen ahí (61-64), los
menús autoajustables (65-75) y el asistente de IA (76-80). **Todos son de este fin de semana**,
y tres de esos bloques (I y K) están marcados como imprescindibles para el domingo.

**Las preguntas del check-in diario** (punto 20 del documento nuevo). El documento de textos no
las trae: solo cubre el test de entrada, los cuatro mensajes del informe y dos notas. Hoy la app
pregunta energía y "ansiedad y hambre", que vienen del documento del 31-07 y que el punto dice
que no son de Jesús. **Hay que pedirle a Jesús cuáles son las suyas.** La otra mitad del punto
(que el cliente apunte lo que ha comido) ya está hecha.

**El texto roto** (punto 16). El documento dice que está identificado en el de textos, y no lo
está: ese documento trae los textos buenos de las 12 pantallas, pero en ningún sitio señala cuál
está roto en la app. Con los textos delante se puede ir pantalla por pantalla a buscarlo, pero
ya no es "de un minuto" como decía el punto. **Que Jesús diga cuál es.**

**Dónde está el lunes** (punto 26). El punto llegó sin el «Qué hacer» y el lunes no aparece por
ningún lado: la fecha del ajuste ya es mañana en dev y en producción, y en el código la única
regla del lunes (`calendario_arranque.py`) está desconectada. **Que Jesús diga en qué pantalla lo
vio**, o si lo que quiere es que un cliente nuevo arranque al día siguiente en vez de esperar al
lunes - que es un cambio de método y toca la facturación.

**Los fondos de pantalla del test** (punto 24). Jesús dice que ya los pasó por Drive y que no
hay que buscar fotos nuevas. **No aparecen**: no están en el disco y en Drive se ha buscado por
cinco vías sin resultado (detalle en el punto 24). Hace falta el enlace de la carpeta, su nombre
exacto o desde qué cuenta se compartieron. El hueco en el código ya existe
(`public/portada-test.jpg`), así que en cuanto aparezcan es cuestión de minutos.

**El repositorio fuente de la calculadora antigua** (`jgl-calma-web-next`). Solo tenemos el
bundle compilado en `_calma_ref/`, que sirve para contrastar comportamiento pero no para leer el
código como lo describe el documento (rutas de fichero y números de línea). Hasta ahora no ha
hecho falta. Y ojo con esto: el documento avisa de que el código que Jesús leyó es la versión
1.1.0 y producción va por la 1.9.0, así que **antes de dar por bueno un "fallo del código
antiguo" hay que comprobarlo contra la calculadora de verdad**.

---

### 2 · Lo que espera una orden de Francisco

**Borrar las 18 cuentas de prueba de producción** (punto 10). Está todo preparado y probado en
simulación contra producción: `backend/_limpiar_datos_prueba.py`, que no borra nada salvo que se
le pase `--ejecutar`. `francisco@test.com` y la cuenta demo quedan fuera. **Dos de las 18 tienen
datos dentro** y por eso no se han tocado: `jose@test.com` (7 dietas, 1 reporte, 3 check-ins, 1
foto y 12 cambios de macros) y `prueba@mail.com` (1 reporte y 3 check-ins). Hay que decidir si
se borran esas dos también.

**Desplegar a producción.** Desde el punto 19 no se ha subido nada. En producción está todo
hasta el commit `8421e3b`; lo posterior (el punto 19, el test de entrada del documento de
textos, las cuatro respuestas de la dieta, las dos reglas nuevas del filtro) está en GitHub y
sin desplegar, esperando la orden.

---

### 3 · Lo que tiene que decidir Jesús

**Los 56 mínimos por categoría** (punto 7). El mapa existe y funciona, pero los valores vienen
de la calculadora antigua y él quiere revisarlos; lo cifra en media hora. La tabla lista para
repasar, con el nombre de cada categoría y una columna en blanco, está en
`_internos_proceso/minimos_por_categoria_para_jesus.md`.

**Los dos criterios del tercio conviven, y no coinciden.** La calculadora antigua tiene su
propia forma de decidir si la proteína de un cereal o de un fruto seco cuenta, y no es la del
tercio: sobre el catálogo entero discrepan en 69 alimentos. Hoy la app usa el criterio de Jesús
para lo que el cliente ve y guarda en su día, y el heredado en el buscador mientras monta la
comida y en las herramientas de menús. Funciona, pero el mismo alimento puede enseñar dos cifras
de proteína distintas según dónde se mire.

**Los alimentos con macros mal puestos** (punto 11). No hay que sacar del buscador los que tienen
los tres macros a cero, porque son la lechuga, el pepino, el konjac y los refrescos zero, y el
método los usa a propósito. Lo que sí descuadra un menú en silencio son los que tienen los macros
**mal**: una tortita de maíz de 7 g con 125 g de grasa (1149 kcal), un turrón de coco con 79 g de
proteína, varios panes con la ración puesta a 1 g. La lista la saca `backend/_auditar_catalogo.py`
ordenada por gravedad y con el enlace a la ficha del producto. **Los valores buenos hay que
mirarlos en la etiqueta: no se pueden inventar.**

**La proyección de composición corporal** que tiene la calculadora antigua y nosotros no: estima
semana a semana, por tramos de cuatro, cuánta masa grasa y cuánta masa magra cambia según el
punto de partida, y con eso valida si un objetivo de peso es alcanzable en un plazo. Nosotros
solo calculamos la composición de hoy. Nadie la ha pedido; encaja en los bloques de después del
lunes.

---

### 4 · Lo nuestro, pendiente de terminar

**Verificar con los ojos que el resultado del alta se ve entero** (punto 15). Está apretado y el
contenedor ya permite desplazarse, pero para comprobarlo de verdad hay que completar un alta
entera, y eso significa o alterar una cuenta real o crear una nueva. Es una revisión de un minuto
en cuanto haya un alta de prueba a mano.

**Cuadrar el texto de "Ponme un día tipo. El de ayer, por ejemplo."** El documento de textos lo
pide en la pantalla de la dieta; en la app hay un bloque que recoge lo mismo pero con otro texto
y otro formato.

**Verificar la regla del 20 % de la dieta reportada.** El documento de textos dice que lo de "con
lo que comes ahora, ¿mantienes, ganas o pierdes?" **modula hasta un 20 % y se aplica al final,
después de todos los demás modificadores**. Hay que comprobar que el motor lo hace así.

**Los avisos de rutina llevan a una pantalla que está oculta.** Dos de los avisos que la app
manda apuntan a Rutinas, que está desactivada para todos los planes a propósito, así que el
cliente pulsa y acaba de vuelta en su panel. No echa a nadie al login, pero es un aviso que no
lleva a donde promete. Mientras Rutinas siga oculta, esos dos no deberían generarse.

**Un test falla desde antes de tocar nada** (`test_search_foods_by_category`): al buscar por la
categoría de carnes aparece un "Caldo de cocido" que no es de esa categoría. Es un problema de
cómo está clasificado ese alimento, no del buscador.

**El día de descanso pierde hasta 0,2 g de hidratos** por el redondeo a 0,1 g de cada comida
(65 ÷ 4 = 16,25). No se ve, porque lo que se le enseña al cliente va redondeado a múltiplos de 5,
pero está ahí.

---

### 5 · Ya resueltos (se dejan por trazabilidad)

~~**Quién cobra el +20 % de "cómo engorda"** y **el umbral de grasa en mujeres**.~~ Resueltos el
07-08: Francisco confirmó que el texto del documento suplanta a todo lo anterior y se aplicó
literal (solo "casi no lo noto"; umbral 20 % sin distinción de sexo).

~~**Falta el documento «LOS TEXTOS DE LA APP»**.~~ Llegó el 07-08 por la noche. Con él se cerró
el punto 19 (las cuatro respuestas de la dieta) y se hizo el test de entrada entero.
