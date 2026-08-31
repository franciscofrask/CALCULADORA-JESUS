# Plan de trabajo · «El día» (parte 1)

Fuente: `C:\Users\Administrador\Desktop\El día.html` (31-08-2026).
Tres apartados: **el cierre del día**, **qué pasa cuando deja de cerrarlo** y **qué puede
apagar**. El documento no numera los puntos, así que los numero yo por bloques (A1, B2...)
para poder cerrarlos uno a uno y que no se pierda ninguno.

**28 puntos en total**: 22 son trabajo y 4 son dudas ya contestadas en el propio documento.

> **OJO CON LOS CÓDIGOS: A1, B2, C3... LOS PUSE YO.** El documento **no numera nada** salvo
> las cuatro «Duda». Tiene tres apartados con subtítulos, y ya está. Los códigos sirven para
> ir cerrando cosas una a una sin perder ninguna, pero **no se pueden buscar en el
> documento**. Para eso está la tabla de abajo.

## Dónde vive cada punto en el documento

| Código | Apartado | Búscalo por este subtítulo |
|---|---|---|
| A1 | El check-in del día | *Las nueve, todas a la vista* (ya no está en la lista) |
| A2 | El check-in del día | *Las nueve, todas a la vista* · 5.ª línea |
| A3 | El check-in del día | *Las nueve, todas a la vista* · 6.ª línea |
| A4 | El check-in del día | *Antes de guardar* |
| A5 | El check-in del día | *Si no le falta nada* |
| A6 | El check-in del día | la línea bajo el título, y *Las nueve, todas a la vista* |
| B1 | El check-in del día | *Ese mismo día, desde las 17:00* |
| B2 | El check-in del día | *Tras 2 días perdidos* |
| B3 | El check-in del día | *Tras 4 días perdidos* |
| B4-B5 | El check-in del día | *Tras una semana* |
| C1, C3 | El día que no lo cierra | *El día, con sus horas* |
| C2 | El día que no lo cierra | *A la mañana siguiente, si ayer no lo cerró* |
| C4 | El día que no lo cierra | *Por qué la mañana siguiente y no el reporte* |
| D1-D2 | La configuración de los avisos | *Todo encendido* |
| D3 | La configuración de los avisos | *Los dos del cierre del día son distintos* |
| D4 | La configuración de los avisos | *Al apagar el cierre del día* |
| D5 | La configuración de los avisos | *La regla: lo que interrumpe sí, lo que informa no* |
| D6 | La configuración de los avisos | *Y cuatro que no se apagan* |
| D7 | La configuración de los avisos | *Las notificaciones del móvil* |
| E1 | El check-in del día | *Los avisos no salen de la app* · última línea |
| E2 | La configuración de los avisos | *Duda 7*, y *Como te llega hoy* |
| F | La configuración de los avisos | *El aviso que falta: cuando tú le contestas* |

## Las dos decisiones, cerradas: MANDA EL DOCUMENTO

Francisco, 31-08: **«déjalo como diga el documento»**. Las dos preguntas que quedaban se
cierran en favor de la maqueta, igual que se hizo con la parte 6 el 27-08.

1. **La suplementación entra para todos** (A2). El documento la lista como una de las nueve,
   sin condición, así que se le pregunta a todo el mundo.
   **Y hay que decir qué se lleva por delante**: el candado de las dos condiciones se puso el
   24-08 por un caso real — cuatro clientes activos con protocolo de su etapa anterior y un
   plan que ya no incluye suplementación, a los que el cierre preguntaba cada noche por unos
   suplementos que su propia pantalla no les deja ver. Con la pregunta para todos, ese caso
   vuelve, y además se le pregunta al que nunca ha tomado nada. Queda dicho una vez y se hace
   como manda el documento.
2. **La pantalla se abre entera** (A6). *«Todas a la vista, sin plegar nada.»* Se cae el
   acordeón: las nueve preguntas abiertas, con sus estrellas y sus botones. Con él se cae la
   cadena que llevaba de una pregunta a la siguiente, así que **lo que dice qué falta pasa a
   ser el pie** («Te queda por contestar», A4), que es justo lo que la maqueta enseña.

---

## Lo que ya está y no hay que inventar

Antes de proponer nada, lo que hay hoy en el código, que es más de lo que la maqueta enseña:

- **La pregunta de la suplementación YA EXISTE** (`CheckInsPage.jsx:667`), con sus tres
  opciones y con una cola («¿Cuál y por qué?») cuando contesta «No todos». Lo que pasa es
  que es **condicional**: solo le sale a quien su plan le da suplementación y además tiene
  protocolo puesto, y lo decide el servidor. Por eso no aparece en la maqueta de «como está
  hoy»: ese cliente no la tiene. **No es una pregunta que falte, es una que no se ve.**
- **El aviso de arriba ya tiene dos estados** (`líneas 833-855`): el de las comidas sin
  registrar y uno verde con un tic. Lo que pasa es que el verde dice **«Dieta registrada»**
  y solo sale si hay dieta montada.
- **El «Te queda por contestar» ya existe** (`línea 929`) y ya corta en tres con el «y N
  más». El mecanismo está bien; lo que cambia es cuánto enseña.
- **La línea de Inicio ya existe** (`ClientDashboard.jsx:669`) con su llave propia
  (`cierre_dia`), su texto en cursiva y el «último registro: 23 de agosto, 11:41» debajo.
  Lo que **no** tiene es hora ni escalada.
- **El día que se puede cerrar ya se valida con un margen de un día**
  (`core/tiempo.py:53`, `dia_del_cliente`), así que **la ventana de la mañana no choca con
  el servidor**: ayer ya es una fecha aceptable. Lo que falta es la regla de las horas.
- **El interruptor de avisos ya existe** (`ProfilePage.jsx:650`), pero es **uno solo**:
  «Recordarme cerrar el día · Cada día a las 20:00».

---

## BLOQUE A · El cierre del día (la pantalla)

Ficheros: `frontend/src/pages/CheckInsPage.jsx` · `backend/routes/checkins.py` ·
`backend/models/common.py` · `backend/tests/test_cierre_once_preguntas_2408.py`

### A1 · Fuera «Sensaciones generales del día»

Hoy es la **primera** pregunta (`línea 592`) y son cinco estrellas. El documento la quita:
en la columna de la derecha no está.

Lo que hay que mirar antes de borrarla, porque no es solo una tarjeta:

- El campo `sensaciones` **se guarda** (`línea 785`) y **se pinta en el historial**
  (`línea 119`, «Sensaciones» con sus estrellitas).
- Sale también en el reporte y en el panel del entrenador.

→ **Se quita de la pantalla, no de la base.** Lo ya guardado se sigue enseñando en el
historial de quien lo tenga; lo que deja de haber es el campo nuevo. Borrarlo del modelo
dejaría meses de historial sin poder pintarse.

### A2 · La suplementación entra en la cadena

El documento la pone como pregunta fija — *«entra: es la que faltaba de tus once»* — y con
otro texto y otras opciones:

| | hoy | queda |
|---|---|---|
| título | ¿Tomaste tus suplementos? | **¿Tomaste la suplementación que tenías pautada?** |
| opciones | Sí · No todos · No | Sí · **No toda** · No |

**CERRADO: entra para todos** (31-08, «déjalo como diga el documento»).

Hoy es condicional: el servidor mira dos cosas — que su plan incluya suplementación y que
tenga protocolo vigente ese día — y solo entonces la pinta. Ese candado se cae.

Queda dicho una vez, porque se lleva por delante un arreglo del 24-08: se puso justamente
porque había **cuatro clientes activos** con protocolo de su etapa anterior y un plan que ya
no incluye suplementación, y el cierre les preguntaba cada noche por unos suplementos que su
propia pantalla no les deja ni ver. Con la pregunta para todos, ese caso vuelve, y además se
le pregunta al que nunca ha tomado nada. Se hace como manda el documento.

### A3 · El subtítulo de los extras

Hoy: *«Algo que comieras de más y no pusieras en el apartado "extras"»*.
Queda: **«Si no lo pusiste en el apartado de extras, ponlo ahora»**.

Dice lo mismo pero en imperativo y sin el paréntesis. El campo ya lleva al mismo sitio que
los Extras del Inicio, así que eso no se toca.

### A4 · El «Te queda por contestar», entero

Hoy corta en tres y añade «y 5 más». El documento las quiere **las ocho enteras**, y sin
«sensaciones», que ya no existe.

Es cambiar un `slice(0, 3)` por la lista completa. **Ojo al móvil**: ocho títulos en una
línea de 11 px son tres o cuatro renglones en 390 px. Hay que verlo antes de darlo por
bueno.

### A5 · El aviso de arriba, en verde, cuando no falta nada

Hoy el verde dice **«Dieta registrada»** y solo sale si hay dieta montada; si no hay nada,
el hueco se queda vacío.

Queda:

```
✓  El día, todo bien
   No te queda nada por registrar
```

Dos renglones en vez de uno, y el mismo hueco. El documento lo dice explícito: *«si "El día,
todo bien" era un texto, este es su sitio»*.

**Ojo**: hoy el verde depende de `hayDietaMontada`, y esa condición existe por algo — desde
que los extras hacen un guardado por su cuenta, un día al que solo le apuntaron «dos cañas»
tiene documento y ninguna comida, y decirle «dieta registrada» sería mentira. Con el texto
nuevo la condición hay que rehacerla: **«no te queda nada por registrar»** es verdad cuando
no hay comidas pendientes, tenga o no tenga dieta montada.

### A6 · «Todas a la vista, sin plegar nada»

El documento dice, de la maqueta: *«Todas a la vista, sin plegar nada: nueve preguntas y las
notas»*.

Hoy la pantalla es **una tarjeta encendida cada vez** (acordeón): se contesta una y se abre
la siguiente. Eso viene del doc del 24-08 y está escrito así en el código
(`línea 374`: «ONCE PREGUNTAS, una por tarjeta, y una sola encendida cada vez»).

**CERRADO: se abre entera** (31-08, «déjalo como diga el documento»). Las nueve preguntas a
la vista, con sus estrellas y sus botones. Se cae la cadena del naranja que llevaba de una a
la siguiente, y lo que dice qué falta pasa a ser el pie, que es lo que la maqueta enseña.

---

## BLOQUE B · La línea de Inicio, con su escalada

Ficheros: `frontend/src/pages/ClientDashboard.jsx` · `backend/core/avisos_cliente.py`

Hoy la línea dice **lo mismo el primer día que el décimo**, y sale a cualquier hora.

### B1 · No sale antes de las 17:00

*«Por la mañana no sale. Se enciende a las 17:00, hora de España: antes no tiene nada que
cerrar, y verla apagada todo el día la convierte en parte del decorado.»*

**La hora es de España**, no del reloj del cliente: el documento lo dice y es coherente con
la regla de la casa (el reloj del cliente decide qué día vive; España decide plazos y
ventanas).

**Y ojo, que aquí hay un cruce con D2**: si el cliente puede elegir a qué hora le sale
(«A qué hora me sale · 17:00»), entonces las 17:00 son el **valor por defecto**, no la regla.
La regla es «a partir de la hora que él haya puesto, y nunca antes de las 17:00».

### B2 · A los dos días

```
¿Cómo fuiste hoy?
Llevas 2 días seguidos sin cerrar, no lo dejes hoy también
```

### B3 · A los cuatro días

```
Llevas 4 días sin cerrar
Retómalo hoy mismo: es de donde salen tus ajustes
```

Cambia el título, no solo el subtítulo. Y dice lo que se pierde, que es verdad: esos días
van en blanco en su reporte.

### B4 · A la semana

```
Llevas una semana sin cerrar el día
Dejo de recordártelo. Si te está costando, dímelo y lo vemos
```

### B5 · La línea NO desaparece nunca

*«Tu frase, sin el "hasta que vuelvas": la línea no desaparece. Si se quitara, se queda sin
el único sitio donde se le dice y no vuelve.»*

O sea: a partir de la semana el texto se queda **fijo** en el de B4. Deja de escalar, pero
sigue ahí.

**Hace falta un dato que hoy no se calcula**: los días seguidos sin cerrar. Hoy solo se sabe
el último cierre (`ultimoCierre`). Contar la racha es del servidor, no de la pantalla.

---

## BLOQUE C · La ventana de la mañana (lo nuevo)

Ficheros: `backend/routes/checkins.py` · `backend/core/tiempo.py` ·
`frontend/src/pages/ClientDashboard.jsx` · `frontend/src/pages/CheckInsPage.jsx`

Es **lo único del documento que no existe de ninguna forma**, y es lo que de verdad arregla
los huecos.

### C1 · Ayer sigue abierto hasta las 15:00

El check-in de un día está abierto **desde su hora hasta las 15:00 del día siguiente**. El
documento insiste en que no son dos mecanismos sino **una sola ventana**, y tiene razón:

```
17:00  se abre el cierre de hoy
       (al día siguiente, hasta las 15:00, todavía se puede rellenar el de ayer)
15:00  ayer se cierra · ya no vuelve
17:00  se abre el de hoy
```

Entre las 15:00 y las 17:00 **no hay ningún día abierto**, y eso es lo que impide que se
solapen dos. El tope de arriba se resuelve solo.

### C2 · El aviso de la mañana

```
Ayer no cerraste el día
Puedes hacerlo hasta las 3 de la tarde
último registro: 23 de agosto, 11:41
```

Va en la misma fila de Inicio, en el mismo sitio.

### C3 · Nunca dos días abiertos a la vez

De 15:00 a 17:00 no sale nada. Es una regla, no un efecto: hay que escribirla y probarla.

**Trampa que ya mordió** (está en las notas del 28-08): `dia_del_cliente` recorta a un día
del de España, y **sirve para validar el reloj, no para decidir qué día se está montando**.
Para la ventana hay que validar la fecha aparte, o se acepta cerrar ayer a las 18:00.

### C4 · El reporte no pide reconstruir nada

*«Lo que se quedó sin cerrar, se quedó sin cerrar.»* Ya es así, así que aquí no hay trabajo:
solo dejarlo escrito para que a nadie se le ocurra añadirlo.

---

## BLOQUE D · La configuración de los avisos

Ficheros: `frontend/src/pages/ProfilePage.jsx` · `backend/routes/notifications.py` ·
`backend/models/user.py`

Hoy hay **un interruptor**. El documento pide **siete y un selector de hora**, en cuatro
grupos.

### D1 · Los siete, agrupados

```
EL CIERRE DEL DÍA
  Rellenar el cierre del día          [ON]
  A qué hora me sale                  [17:00 ▾]
  Recordármelo si me lo salto         [ON]

LOS REPORTES
  Recordatorio del reporte quincenal  [ON]
  Recordatorio del reporte mensual    [ON]
  «El quincenal y el mensual no se pueden desactivar: son los que hacen tu ajuste.
   Aquí solo apagas los recordatorios.»

EL PESO
  Recordatorio de los días de pesada  [ON]

CÓMO TE AVISO
  Avisos en la app                    [ON]
  Por correo                          [ON]
  «Lo que tengas pendiente seguirá saliendo en Inicio. Aquí solo apagas los avisos.»
```

**Ojo con «Por correo»**: hay una decisión del 30-08 escrita y con nombre —
`correos_avisos` **no se enciende nunca**. Poner el interruptor al cliente no lo enciende,
pero hay que asegurarse de que apagarlo tampoco promete nada al revés.

### D2 · El selector de hora

*«Puedes activarla a cualquier hora a partir de las 17:00. Permanecerá activa hasta las
15:00 del día siguiente.»*

Tiene un motivo real y suyo: **los turnos de noche**. Al que sale a las dos de la mañana las
17:00 no le sirven.

Esto es un campo nuevo en la ficha del cliente y manda sobre B1.

### D3 · Los dos del cierre son distintos, y hoy son uno

- **Rellenar el cierre del día**, apagado → la fila **no sale nunca**, y ese cliente cae en
  la versión del reporte que no pide datos diarios.
- **Recordármelo si me lo salto**, apagado → la fila **sale igual**, pero la escalada de los
  2, 4 y 7 días **no salta**.

*«Es para el que sí quiere rellenarlo pero no quiere que se lo recuerden cuando falla. Hoy
no puede elegir eso: o todo o nada.»*

### D4 · El diálogo al apagar el cierre del día

```
Si lo apagas, no podrás registrar tus datos del día, pero deberás rellenar las
preguntas del reporte quincenal y del reporte mensual para poder recibir tus ajustes.

Puedes volver a activarlo cuando quieras.

[ Dejarlo como está ]   [ Apagarlo ]
```

La segunda línea no es adorno: *«sin ella el interruptor parece una puerta de un solo
sentido, y hay gente que no lo toca por miedo a no poder deshacerlo»*.

### D5 · La regla que sostiene todo

*«Lo que interrumpe sí, lo que informa no.»* La fila de pendientes de Inicio **no es un
aviso, es el estado de su cuenta**. Por eso la línea de abajo del último grupo es
obligatoria: con ella puede apagarlo todo sin quedarse a ciegas.

### D6 · Los cuatro que no se apagan

1. La fila de pendientes de Inicio.
2. El aviso de que le has contestado (macros, rutina, informe, chat).
3. El fuera de plazo del jueves de 20:00 a 24:00.
4. El aviso de renovación — *«va de su contrato, no de su entrenamiento»*.

Trabajo real: **comprobar que ninguno de los cuatro cuelga de un interruptor** que el
cliente pueda apagar hoy sin querer.

### D7 · Nada de notificaciones del móvil

*«No hay interruptor porque no hay notificaciones.»* No se añade. Queda escrito para que no
se vuelva a proponer.

---

## BLOQUE E · El panel

Ficheros: `backend/routes/admin.py` · `frontend/src/pages/AdminDashboard.jsx`

### E1 · Una columna de días sin cerrar en Clientes

*«Dejar de cerrar suele ser el primer síntoma, y llega antes que el impago.»*

Es el mismo dato de la racha que hace falta para B2-B4, así que se calcula una vez y lo usan
los dos sitios.

### E2 · Distinguir el silencio (Duda 7)

Hoy los dos llegan igual:

```
Cliente A · Gold · semana 2   Sin reporte
Cliente B · Gold · semana 2   Sin reporte
```

Queda: el que lo ignoró, **«Sin reporte» en rojo**; el que apagó los avisos, **«Avisos
apagados» en gris**. *«Su silencio no significa lo mismo.»*

Y lo mismo con el cierre del día: *«un 0 de 14 de alguien que lo apagó y uno de alguien que
te está abandonando te llegan exactamente iguales, y no son lo mismo: uno eligió y el otro
se está yendo»*.

---

## BLOQUE F · El aviso que falta

*«Cuando revisas su reporte y le pones los macros nuevos, le subes la rutina del mes o le
dejas el informe, algo tiene que decírselo. Y ese aviso no está diseñado en ninguna parte.»*

*«Es el único aviso de toda la app que le da algo en vez de pedirle algo, así que es el que
más quiere recibir.»* Y no lleva interruptor.

**No está diseñado**, y el documento lo dice él mismo. Aquí no hay punto que ejecutar: hay
que decidir **qué lo dispara** (macros nuevos, rutina subida, informe dejado, mensaje del
chat), **qué dice** y **dónde cae**. Lo dejo levantado y no lo invento.

---

## Las cuatro dudas, ya contestadas en el documento

| | Duda | Respuesta |
|---|---|---|
| **Duda 4** | ¿El aviso del reporte, solo el primer ciclo o cada cuatro semanas? | **Solo la primera vez.** «Repetido cada mes deja de leerse.» |
| **Duda 5** | ¿Se puede apagar este aviso? | **Sí, con los recordatorios del peso.** No merece interruptor propio. |
| **Duda 7** | ¿Se marca en el panel al que apagó los avisos? | **Sí.** Es E2. |
| **Duda 11** | «La media la hace la app sola de forma automática» | **«La media la hace la app de forma automática.»** «Sola» y «de forma automática» dicen lo mismo. |

La 11 es un texto suelto: hay que encontrar dónde vive esa frase antes de cambiarla.

---

## Lo único que queda abierto

**B1 y D2 se pisan.** Si el cliente elige la hora, las 17:00 dejan de ser una regla y pasan
a ser el mínimo y el valor por defecto. Se hace así, que es lo que dice el propio documento
en *La hora: una ventana, no dos cosas*.

Y **F** (el aviso de que le has contestado) sigue sin diseñar, y lo dice el documento mismo:
no hay nada que ejecutar hasta que se decida qué lo dispara y qué dice.

---

## Orden de trabajo

1. **A** primero (la pantalla): son cambios de texto y de condición, ninguno depende de
   nadie, y los dos bloqueados (A2, A6) se pueden dejar para el final sin parar el resto.
2. **C** después, que es lo nuevo y lo que más valor tiene: la ventana de la mañana. Toca
   servidor y hay que escribir la regla de las horas con cuidado.
3. **B** con C, porque la escalada necesita el dato de la racha y la ventana necesita la
   misma fila de Inicio.
4. **D** luego: es la pantalla con más piezas nuevas (siete interruptores, un selector, un
   diálogo) y toca el modelo del cliente.
5. **E** al final, que reutiliza el dato de la racha que ya habrá calculado B.
6. **F** no se toca hasta que se decida.

## Cómo se comprueba

Navegador contra la app real, teléfono y escritorio, con las cuentas de prueba. La regla de
siempre: encoger la ventana no prueba móvil, y ningún rojo se da por «de otro».

Lo que hay que probar sí o sí, porque es donde está el riesgo:

- **Las horas de C**: a las 14:59, a las 15:01, a las 16:59 y a las 17:01. Con el reloj de
  España y con un cliente fuera de España.
- **La racha de B**: 1, 2, 3, 4, 6, 7 y 10 días sin cerrar.
- **D3**: los dos interruptores del cierre por separado, en sus cuatro combinaciones.
- **A1**: que el historial de quien tenga sensaciones guardadas las siga enseñando.
- Tests: `test_cierre_once_preguntas_2408.py` y `test_cierre_avisos_2408.py` cubren esto y
  **van a ponerse rojos con A1** — la pregunta desaparece —, así que hay que actualizarlos
  con la razón escrita dentro, no borrarlos.
