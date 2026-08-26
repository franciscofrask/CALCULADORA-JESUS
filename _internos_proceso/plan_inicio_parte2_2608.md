# Inicio, parte 2 (puntos 75 al 104) - plan por fases

Fuente: artifact «Para el equipo · parte 2», cerrado el 25 de agosto.
https://claude.ai/code/artifact/bdba180b-3784-482b-9cee-afd56911fb9a

Son 30 puntos (75 a 104) sobre una sola pantalla: **el Inicio del cliente**.
Todo cae en dos ficheros de front y uno de backend:

- `frontend/src/components/inicio/TuDietaHoy.jsx` (los cuatro numeros y la lista de comidas)
- `frontend/src/pages/ClientDashboard.jsx` -> `InicioNuevo` (403-1031): cabecera, frase, nota del peri
- `backend/routes/diets.py` (marcar comida) y `backend/routes/settings.py` (frase del dia)

## Antes de empezar: comprobar el interruptor

El Inicio que dibuja Jesus es el **Inicio nuevo**, y vive detras de `t1_inicio_nuevo`
(`backend/routes/settings.py:35`, nace apagado; `ClientDashboard.jsx:1047` y `:1190-1198`).
Si en produccion estuviera apagado, estariamos tocando una pantalla que no ve nadie.
**Primer paso de la fase 1: confirmar en prod que esta encendido.**

---

## La regla de color, en una tabla

Vale igual en las cuatro pestañas. Margen: **±4 g**.

| Situacion | Color | Macros | Dieta | Llevas | Falta |
|---|---|---|---|---|---|
| Sin estado (Macros) | sin color | `tu objetivo` | - | - | - |
| Por debajo, fuera de margen | sin color | - | `faltan 76` | `de 250` | `para llegar` |
| Dentro de margen (1 a 4) | verde `#22C55E` | - | `valido -4` / `valido +3` | `ya lo tienes` | `cuadrado` |
| Clavado | verde `#22C55E` | - | `cuadrado` | `ya lo tienes` | `cuadrado` |
| Pasado, fuera de margen | naranja `#FF5A2E` | - | `sobran 12` | `te pasas 14` | `te pasas 14` |

Pies de la tarjeta:

- **Macros**: «Los macros totales a los que tienes que llegar hoy» + el interruptor del peri.
- **Dieta**: «Lo que tienes creado en **tu** calculadora».
- **Llevas**: el contador («2 comidas marcadas», «3 comidas marcadas y el intra»,
  «2 comidas marcadas, intra y post») o, sin nada marcado,
  «Todavia no has marcado nada. Marca abajo lo que vayas comiendo».
- **Falta**: «Lo que te queda para cuadrar el dia»; con los tres a cero,
  «Dia cuadrado. Mañana seguimos».

La barra: del color del estado. Corta si falta, llena a tope si sobra,
las tres llenas de verde de lado a lado en un dia cuadrado.

---

# FASE 1 · La frase del dia (103) + la cabecera (102)

**Por que primero:** no es diseño, es un fallo vivo. El panel promete que si un dia
no hay frase nueva el cliente sigue viendo la ultima, y lleva dos dias sin salir.

**Causa:** `ClientDashboard.jsx:765-768` exige que la frase guardada sea **de hoy**:

```
appSettings?.frase_del_dia?.fecha === hoyDelCliente ? ...texto : null
```

Sin frase nueva, el hueco se queda vacio. La cola de programadas ya se resuelve sola
en `backend/routes/settings.py:98-111`, asi que la fecha solo tiene que decidir
**cuando entra** una frase nueva, no si se enseña la que hay.

**Que se hace**
1. Confirmar en prod `t1_inicio_nuevo` y `frase_del_dia` encendidos (`settings.py:34-35`).
2. Enseñar la ultima frase que haya, sea de hoy o no.
3. Punto 102: la cabecera (fecha, entreno/descanso, saludo, frase) **no se toca**. Solo verificar.

**Ficheros:** `ClientDashboard.jsx`, `backend/routes/settings.py` (si acaso).
**Riesgo:** bajo.

---

# FASE 2 · La lista de comidas: intra y post marcables (96, 97, 98, 100, 101)

**Por que va segunda:** es el otro fallo de verdad. Hoy **Llevas no puede llegar al total
nunca**: marcas las cuatro comidas, te tomas el batido, y te siguen faltando los 40 de
proteina, porque el perientreno no se puede marcar.

**Causa: tres candados**
1. `TuDietaHoy.jsx:402-420` - intra y post se funden en **una** tarjeta «Perientreno»
   que solo navega, sin casilla. El rayo ocupa el sitio del circulo.
2. `TuDietaHoy.jsx:184` - `claves = ['C1','C2','C3','C4']`, asi que ni entran en la
   lista marcable ni suman en `llevas` (`:191-201`).
3. `backend/routes/diets.py:708-721` - `marcar_comida()` valida `C[1-9]` y rechaza el
   resto con un 400. El comentario de `:715` lo dice: «El peri no se marca (regla 3 del
   diseño)». **Esa regla es de antes y ahora Jesus la cambia** (ver preguntas).

**Que se hace**
- **96 + 97**: partir la tarjeta en **dos filas**, «Intra» y «Post», con el circulo a la
  izquierda como las comidas y el rayo junto al nombre. Van seguidas en la lista. Si el
  cliente solo tiene una, una sola linea (Post o Intra). La palabra «Perientreno» desaparece.
- Backend: aceptar INTRA/POST en `marcar_comida()` y guardarlas en `comidas.*.marcada`.
- Front: que entren en `claves`, en `hechas` y en la suma de `llevas`.
- **98**: `lineaMacros` (`TuDietaHoy.jsx:63-65`) sin letras y redondo:
  «61P · 30,2H · 19,6G» pasa a «61 · 30 · 20».
- **100**: intra y post no llevan suplementos debajo. Solo las comidas.
- **101**: al marcar, tick verde y linea apagada, igual que una comida. Sin etiquetas.

**Ficheros:** `TuDietaHoy.jsx`, `backend/routes/diets.py`, tests de `diets`.
**Riesgo:** medio. Toca el calculo de Llevas y el backend.
**Ojo:** el contador de Llevas («y el intra», «intra y post») es la fase 6, pero
depende de esta.

---

# FASE 3 · El color y la letra (75, 76, 77, 81)

**Estado hoy:** los tres numeros grandes van en **naranja de marca `#FF671F`**
(`TuDietaHoy.jsx:296`, `text-brand`), el mismo del boton de Guardar y de la pestaña
activa. Cuando se pasa, `text-amber-600 / dark:text-amber-400` (`#D97706` / `#FBBF24`).

**Que se hace**
- **75**: los numeros, en blanco (`text-foreground`, `#F5F5F5`).
- **76**: naranja propio de «te has pasado»: **`#FF5A2E`**, distinto del naranja de marca.
  Fuera los `amber` del Inicio nuevo.
- **77**: verde de «resuelto»: **`#22C55E`**. Lo usan el punto, la palabra y la barra.
- **81**: numeros mas altos y menos gordos. Hoy son `font-data font-bold text-[34px]
  sm:text-[40px]`, o sea **ya van en peso 700**, no en 850 (ver notas). Lo que queda de
  este punto es el estirado a lo alto y el estrechado.

**Ficheros:** `frontend/src/index.css`, `frontend/tailwind.config.js`, `TuDietaHoy.jsx`.
**Riesgo:** bajo, pero los tokens son globales: los dos colores nuevos se añaden como
tokens propios (`--macro-ok`, `--macro-pasado`) y solo se usan en Inicio, para no
repintar el resto de la app sin querer.

---

# FASE 4 · El motor del estado (78, 79, 80, 82, 83)

Es la pieza de la que cuelgan las fases 5 y 6. Una funcion unica, y las cuatro pestañas
la usan.

**Estado hoy:** no hay punto de color junto al nombre del macro, y la barra existe
**solo en la pestaña Falta** (`TuDietaHoy.jsx:304-307`). No hay margen: cualquier
desvio de 1 g ya pinta.

**Que se hace**
- **78**: margen de 4 g. De 1 a 4, falte o sobre, es valido y sale en verde.
- **79**: las palabras de cada estado, segun la tabla de arriba.
- **82**: punto junto al nombre del macro. Verde si resuelto, naranja si pasado,
  **nada** mientras va por debajo (asi no hay leyenda que aprenderse).
- **83**: barra en las cuatro pestañas, del color del estado, y con la longitud
  distinguiendo faltar (corta) de sobrar (llena a tope). Dia cuadrado: las tres
  llenas de verde de lado a lado.
- **80**: todos los numeros redondos en Inicio, arriba y en las comidas. El decimal
  exacto solo en la linea de aviso: «Te has pasado 13,7 g de hidratos».
  Hoy esa linea ya sale entera («13 g») porque `falta` lleva `Math.round`
  (`TuDietaHoy.jsx:203-207`): hay que guardar el valor sin redondear para el aviso.

**Ficheros:** `TuDietaHoy.jsx`, `frontend/src/lib/estadoMacro.js` (nuevo),
`frontend/src/lib/numeros.js`.
**Riesgo:** medio. Es el corazon; conviene bateria de casos por estado y pestaña.

---

# FASE 5 · Macros y el perientreno (84, 85, 86, 87, 88)

**Estado hoy:** no hay interruptor. Hay un rotulo que no se puede tocar:
«Tus macros de hoy llevan el perientreno dentro» (`ClientDashboard.jsx:841-845`).
La opcion de peri se elige lejos de aqui, en Nutricion (`ConfigSection.jsx:10-17`).

**Que se hace**
- **84**: Macros nunca lleva color. Los tres en blanco.
- **85**: debajo de cada numero, «tu objetivo»; el pie se queda como esta.
- **86**: interruptor del perientreno **a la izquierda**, delante del texto, para que se
  lea como una casilla y no compita por el ancho en el movil.
- **87**: marcado, solo la palabra «Perientreno incluido». Desmarcado,
  «Perientreno aparte · 40 P · 50 H», y los numeros bajan a los de las comidas:
  210 + 40 = 250 de proteina, 160 + 50 = 210 de hidratos.
  El backend ya da los dos numeros: `resumen.P_total` (con peri) y
  `objetivo_de_las_comidas()` (sin peri), `backend/macro_distribution.py:520-566`.
- **88**: el interruptor solo vive en Macros. En Dieta, Llevas y Falta no aparece.
- Fuera el rotulo `nota-perientreno`: lo sustituye el interruptor.

**Ficheros:** `TuDietaHoy.jsx`, `ClientDashboard.jsx`.
**Riesgo:** bajo-medio.

---

# FASE 6 · Dieta, Llevas y Falta (89, 90, 91, 92, 93, 94, 95)

Depende de la 4 (motor) y, para el contador, de la 2 (intra y post marcables).

**Dieta**
- **89**: debajo del numero, lo que sobra o lo que falta («faltan 76» / «sobran 12»),
  en vez del «de 250» de hoy (`TuDietaHoy.jsx:310-312`).
- **90**: fuera la linea de aviso de arriba (`TuDietaHoy.jsx:318-326`,
  `data-testid="falta-pasado"`): si cada macro lo dice debajo, la frase lo repite.
- **91**: el pie, con «tu»: «Lo que tienes creado en **tu** calculadora».

**Llevas**
- **92**: «ya lo tienes» cuando un macro esta resuelto.
- **93**: el contador cuenta el peri aparte: «2 comidas marcadas», «3 comidas marcadas
  y el intra», «2 comidas marcadas, intra y post». El peri no es una comida.
- **94**: sin marcar, los ceros y «Todavia no has marcado nada. Marca abajo lo que
  vayas comiendo».

**Falta**
- **95**: debajo del numero, «para llegar» (no «faltan»: seria decirlo dos veces).
  Al llegar, el numero es 0 y debajo «cuadrado». Los tres ceros en verde, y el pie
  pasa a «Dia cuadrado. Mañana seguimos».

**Ficheros:** `TuDietaHoy.jsx`.
**Riesgo:** bajo.

---

# FASE 7 · Los suplementos, dentro de su comida (99)

Va aparte porque **no hay dato**. Hoy no existe en ninguna pantalla el vinculo
suplemento -> comida: los suplementos son una lista suelta
(`GET /supplements/current`, `SupplementsPage.jsx`, navegada por categorias).

Lo que pide el punto es «+ Creatina» debajo de los macros de la comida 3 y
«+ Omega 3 · NAC» en la 4. Para eso hace falta decidir quien dice que suplemento va en
que comida (ver preguntas). Con eso decidido, es media tarde de trabajo.

**Ficheros:** modelo de suplementos en backend, `SupplementsPage.jsx`, `TuDietaHoy.jsx`.
**Riesgo:** medio, y bloqueada por decision.

---

# FASE 8 · El saludo por hora (104)

Jesus lo deja como pregunta, no como cierre: si alguien entra entre las 4:30 y las 6:00,
«Buen madrugon, Juan»; a las doce de la noche, «Hola, trasnochador».

Se puede hacer, y sale barato: el saludo esta en `ClientDashboard.jsx:786-788` y la hora
del cliente ya la tenemos con la regla del navegador (`hoyLocal` / `lib/horaEspana.js`).
Falta que Jesus diga las franjas y los textos exactos.

**Riesgo:** bajo. Bloqueada por decision.

---

# Lo que hay que preguntarle a Jesus

1. **Por debajo y fuera de margen: ¿sin color o naranja?**
   La frase de cabecera dice «de 1 a 4 es valido y sale en verde; a partir de 5, naranja».
   Pero en su propia maqueta del borde del margen, «faltan 5» sale **sin color** y la
   barra gris. Me quedo con la maqueta (por debajo nunca pinta; el naranja es solo para
   lo que se pasa), pero conviene que lo confirme.

2. **El peri pasa a ser marcable, y antes cerramos lo contrario.**
   En el codigo hay una regla escrita a proposito: «El peri no se marca (regla 3 del
   diseño)». El punto 96 la cambia. Confirmado esto, se levanta el candado.

3. **Suplementos por comida (99): ¿quien decide el reparto?**
   Hoy no existe. ¿Lo dice el entrenador al montar la dieta, cliente a cliente, o vale
   una tabla fija por suplemento (creatina en la comida 3, omega 3 y NAC en la 4)?

4. **El saludo por hora (104): ¿si o no, y con que franjas?**

# Notas

- **El peso 850 no existe hoy.** El punto 81 dice «de peso 850 a 700», pero los numeros
  ya van en `font-bold` = 700 (`TuDietaHoy.jsx:296`). El 850 es de su maqueta. De ese
  punto solo queda estirarlos a lo alto y estrecharlos.
- **Los extras del dia no suman** en ninguna de las cuatro cuentas
  (`TuDietaHoy.jsx:197-201`). El artifact no lo menciona; queda como esta.
- **La parte 1 (puntos 1 al 74)** no esta en el repo. Si hace falta cotejar que quedo
  cerrado alli, hay que pedirle el artifact de la parte 1.
