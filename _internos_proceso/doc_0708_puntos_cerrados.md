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
cifras son correctas y contradictorias a la vez. El arreglo de fondo es del punto 20 de este
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

---

## Pendientes que no dependen de nosotros

*(Se irán anotando aquí según aparezcan: decisiones de Jesús, datos que faltan o terceros.)*

**No tenemos el repositorio fuente de la calculadora antigua** (`jgl-calma-web-next`). En
`_calma_ref/` solo está el bundle compilado, que sirve para contrastar comportamiento pero no
para leer el código como lo describe el documento (nombres de fichero, números de línea y las
funciones a medio desminificar). Si Jesús quiere que revisemos algo concreto de ese código, hace
falta acceso al repositorio. Hasta ahora no ha hecho falta: el reparto se pudo portar y validar
contra el bundle.

~~**Quién cobra el +20 % de "cómo engorda"** y **el umbral de grasa en mujeres** (punto 11).~~
**RESUELTAS el 07-08**: Francisco confirmó que el texto del documento suplanta a todo lo
anterior y se aplicó literal (solo "casi no lo noto"; umbral 20 % sin distinción de sexo).
Detalle y consecuencias en el propio punto 11.

**Falta el documento «LOS TEXTOS DE LA APP»** (punto 14 y los textos del bloque C). Sin él no
se puede localizar el texto roto, que el documento da por identificado allí.

**Los 56 mínimos por categoría están sin repasar** (punto 5). El mapa existe y funciona, pero
los valores vienen de la calculadora antigua y Jesús quiere revisarlos; él mismo lo cifra en
media hora. La tabla lista para repasar está en
`_internos_proceso/minimos_por_categoria_para_jesus.md`. **Decide Jesús.**

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
