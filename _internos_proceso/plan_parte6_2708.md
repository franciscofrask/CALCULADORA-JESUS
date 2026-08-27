# Plan de trabajo · «Para el equipo · parte 6» (puntos 179 a 197)

> **ESTADO 27-08, final del día: LA PARTE 6 ENTERA, HECHA Y COMPROBADA EN EL NAVEGADOR, sin
> desplegar.** Los 19 puntos, los siete cambios que la maqueta enseña sin número, y las dos
> decisiones que Francisco cerró esa tarde: **manda el documento** en las dos.
> Guiones: `_guia/_parte6_bc_2708.js` (191-197), `_guia/_parte6_suplementos_2708.js` (179-190)
> y `_guia/_parte6_maqueta_2708.js` (lo de la maqueta y las dos decisiones).

Fuente: `C:\Users\Administrador\Desktop\Para el equipo · parte 6.html` (27-08-2026).
Sigue a la parte 5, que cerró en el 178. Son **19 puntos** en dos pantallas.

---

## Reparto en tres bloques

| Bloque | Puntos | Ficheros |
|---|---|---|
| **A · Suplementos** | 179-190 | `frontend/src/pages/SupplementsPage.jsx` · `backend/core/guia_suplementacion.py` · `backend/routes/supplements.py` · `frontend/src/components/inicio/TuDietaHoy.jsx` (el 190) |
| **B · La frase del modo** | 191-195 | `frontend/src/components/nutrition/MealCard.jsx` |
| **C · El color de las comidas** | 196-197 | `frontend/src/components/nutrition/MealCard.jsx` |

B y C tocan el mismo fichero, así que van juntos y en ese orden. A es independiente.

---

## BLOQUE A · Suplementos (179-190)

Es el bloque grande: **la pantalla pasa de dos caminos a tres**, y hoy los dos que hay no son
ninguno de los tres.

### Cómo está hoy

`SupplementsPage.jsx` decide así:

- **Sin protocolo** → título «Tu suplementación» + la guía entera.
- **Con protocolo** → título «Tu suplementación» + su pauta + **la guía debajo, siempre**
  (líneas 497-505: «la ven todos, también quien ya tiene su pauta»).

O sea: **el que tiene su pauta ve además la guía entera**, y el punto 179 dice que no. Y los
dos casos se llaman igual, que es lo que denuncia el 180: «en uno de los dos es mentira».

### Los tres estados, y cómo se distinguen

La buena noticia es que el dato ya llega, aunque hoy no se use como tal:

| Estado | Cómo se sabe | Qué se ve |
|---|---|---|
| Con plan y con protocolo | `/supplements/current` responde 200 y `actual` trae líneas | **Mis suplementos**, solo lo suyo. **La guía no sale.** |
| Con plan, sin protocolo | responde 200 y `actual` viene vacío | **Mis suplementos** + el aviso del 183 + la guía debajo |
| Sin plan personalizado | responde **403** (`require_access("suplementacion")`) | **Suplementación** + la guía |

Hoy el 403 se traga en un `catch` que solo hace `console.error` y deja `protocol` en `null`
(`líneas 345-351`), así que el tercer estado y el segundo acaban en la misma rama por
casualidad. Hay que **guardar si la llamada fue 403 o 200**, que es lo que separa «no te toca»
de «todavía no te la hemos puesto».

### Punto por punto

**179 · Tres estados.** Lo de arriba. Es el que más código mueve.

**180 · El nombre cambia con el estado.** «Mis suplementos» en los dos primeros, «Suplementación»
en el tercero. Hoy pone «Tu suplementación» en todos (`líneas 385, 395, 434`).

**181 y 182 · Los textos.** El de «Mis suplementos» ya está escrito casi igual
(`línea 444`: «Lo que tienes pautado, dosis y cuándo tomarlo»). El de la guía es nuevo y **se
caen dos párrafos**: el que vende el Catálogo Premium dentro de lo que ya ha pagado y el que
promete el plan personalizado. Los dos vienen del servidor (`texto_entrada`), así que se tocan
en `guia_suplementacion.py`, no en la pantalla.

**183 · El aviso del que espera.** «Te lo estamos preparando. Te avisamos en cuanto esté.» Y sin
el «empieza por los básicos»: si se lo vas a decir tú, no tiene sentido mandarle a empezar por
su cuenta.

**184 · Cada suplemento, en cuatro líneas.**

```
Creatina
COMIDA 3                 ← naranja, debajo del nombre
Dosis — 5 g
Cuándo — Todos los días, entrenes o no
Comprar con descuento ↗
```

**La comida sale del trabajo de ayer**: `en_comidas` ya viaja en cada línea del protocolo
(`core/comida_del_suplemento.py`, punto 174). Aquí solo hay que pintarlo, y con el mismo naranja
que en Inicio, que es lo que pide el punto: «es el mismo dato y el mismo color que verá en
Inicio».
Y las etiquetas pierden la interrogación: `¿Cuánto?` → **Dosis**, `¿Cuándo?` → **Cuándo**
(hoy en `líneas 38, 44, 122, 127`).

> **Ojo con el orden.** «Dosis» va antes que «Cuándo», al revés de como está hoy. Es lo que dice
> el punto: «en ese orden, igual que la frase de arriba» («dosis y cuándo tomarlo»).

**185 · «Dónde encontrarlo» → «Comprar con descuento».** Tres sitios (`líneas 55, 94, 136`).

**186 · Alimentos antes que Básicos.** En `guia_suplementacion.py` hoy `basicos` es orden 1 y
`alimentos` orden 2: se intercambian. Y las frases de las categorías **no se tocan** (punto 189),
aunque en la maqueta salgan cortadas: ahí están recortadas para que quepan, y el 189 dice
«las siete categorías con sus frases» se quedan.

**187 · «El resto de la guía» se cae.** Es `_resto` en `SupplementsPage.jsx:232`, el cajón de
sastre de los que no caen en ninguna sección. Si se borra sin más, esos suplementos desaparecen
de la guía en vez de recolocarse, así que **lo primero era contarlos**. Ya está contado, y es
poco: de las 28 fichas de la guía, **solo 2 caen en el cajón**.

    Citrulina malato        -> Rendimiento. Obvio: es un preentreno.
    Crema RELIEF EFFECT     -> Descanso. Es una crema para la zona dolorida después de
                               entrenar, y esa categoría dice, literal, «mejoran la calidad
                               de tu sueño y TU RECUPERACIÓN».

El reparto queda: Alimentos 4 · Básicos 4 · Rendimiento **9** · Salud 11 · Volumen 2 ·
Definición 4 · Descanso **3**. La crema es la única discutible; se le dice al entregar.

**188 · El código.** «Ya está así en la app y no se toca.» Solo hay que asegurarse de que sale
al final de **las tres** pantallas.

**189 · Lo que no se toca.** Las siete categorías con sus frases, el Cuándo y el Dosis de cada
suplemento, y las fotos de los botes.

**190 · Cómo se llega desde Inicio.** «Con el + Creatina debajo de la comida 3 ya hay por dónde:
tocando ahí.»
Eso es lo que se montó ayer, pero **hoy no se puede tocar**: el `+ Creatina` va dentro del botón
de la fila de la comida, que lleva a Nutrición. Hay que sacarlo de ahí — un botón dentro de otro
botón no es HTML válido — y darle su propio destino.

---

## BLOQUE B · La frase del modo (191-195)

El más pequeño y el más claro: **dos frases**, y tres puntos que dicen que no toque nada más.

**191 · La frase de Automático.** `MealCard.jsx:633`.
Hoy: «Yo te ajusto las cantidades» → Queda: **«Ajusta las cantidades de los alimentos a tus
macros»**. Sale del singular (una de las seis frases del plural) y dice a qué ajusta.

**193 · La frase de Cuadrar.** `MealCard.jsx:838`.
Hoy: «Te ajusto las cantidades sin pasarme de tus macros.» → Queda: **«Ajusta las cantidades sin
pasarse de tus macros»**, sin punto final.

**192, 194 y 195 · Nada que hacer, solo verificar.**
- 192: la de Manual ya es la buena («Las pones tú y lo compensas en el día»).
- 194: las dos frases quedan parecidas **a propósito**, y lo deja escrito para que nadie lo lea
  como un copiado.
- 195: el punto 124 ya está entero. Verificar que pone «AJUSTE DE CANTIDADES» y que la frase se
  ve en el móvil.

---

## BLOQUE C · El color de las comidas (196-197)

**Corrige dos puntos suyos anteriores.** El 116 y el 117 daban naranja a la comida sin crear, y
se escribieron antes de cerrar la regla del color del 76: **el naranja es solo para lo que se
pasa**. Una comida sin crear no es un error, es que aún no la has hecho.

Hoy, en `MealCard.jsx`:
- `línea 44`: `if (!cuantosAlimentos) return { texto: 'sin crear', color: 'pasado' }` — naranja.
- `línea 422`: `sinCrear` pinta **la tarjeta entera en naranja, borde y fondo**.

**196 · «Sin crear» en gris y sin punto.** La palabra se queda -- en Nutrición estás justo para
montar el día --, pero sin color y sin el punto de estado. La lista queda:
`● cuadrada` verde · `● válido +2` verde · `● sobran 6 de grasa` en #FF5A2E · `sin crear` en
gris, sin punto.

**197 · Se apaga lo hecho en vez de pintar lo que falta.** Mismo efecto que pedía el 117,
sin gastar un color: la tarjeta de una comida cuadrada baja de opacidad. Eso ya existe
(`yaEsta`, `línea 423`); lo que se quita es el naranja del `sinCrear`.

Resultado: **en un día a medias no hay ni un color en pantalla**, porque no hay nada que
corregir, solo cosas que hacer.

---

## Lo que enseña la maqueta y NO lleva número

El artifact dibuja cinco pantallas de Nutrición completas, y en ellas hay cambios que **no están
en ningún punto numerado**. El documento dice que solo entra lo validado, así que están
validados, pero conviene decidirlos aparte porque no son «arreglar una frase»:

1. **Los objetivos con letra**: `Objetivo · 33P · 20H · 10G` en vez de `33 · 20 · 10`. El pie de
   la maqueta lo dice: «los objetivos con letra». **Revierte el punto 115**, igual que el 173 de
   la parte 5 revirtió el 98 para el Inicio, así que es coherente. `MealCard.jsx:415-417`.
2. **El día con su nombre**: «Jueves, 27 de agosto» en vez de «Hoy».
3. **«Nutrición» en vez de «Plan nutricional»** en el rótulo de arriba.
4. **Un rótulo «Comidas del día»** antes de la lista.
5. **Los Extras plegados**, con la frase en una línea y un «+» para abrir.
6. **El intra y el post con su estado** («cuadrada»), que hoy salen sin él.
7. **El `+ Creatina` bajo la comida 3 y el `+ Omega 3 · NAC` bajo la 4** — que es lo del punto
   190 y ya está hecho en Inicio; en Nutrición no.

---

## Y UNA CONTRADICCIÓN CON EL VÍDEO DE HOY MISMO

La maqueta del aviso de pasarse dice:

> «Este día se pasa de tus macros **de ahora** · Si tus macros han cambiado, **te reajustamos**
> las cantidades sin quitarte nada» · botón **«Cuadrar el día»**

Y en el vídeo de esta mañana, leyéndolo en voz alta, dijo lo contrario:

> «Sería, se pasa de tus macros **actuales**» · «podemos reajustar las cantidades sin quitarte
> nada» · «Y entonces pondríamos recuadrar el día. **No. Pondríamos reajustar.**»

**Se hizo lo del vídeo hace unas horas** y está en la app: «macros actuales» y botón
«Reajustar». No lo toco: el vídeo es él corrigiéndose en directo sobre esa misma frase, y en la
parte 6 el aviso sale dentro de una maqueta, no en un punto numerado. **Pero hay que
preguntárselo**, porque es la misma frase con dos redacciones suyas del mismo día.

---

## Orden

1. **B y C** primero: los dos son `MealCard.jsx`, son cinco cambios pequeños y tres de ellos
   solo hay que verificarlos.
2. **A** después, que es el que rehace una pantalla entera y toca servidor.
3. Y antes de A, **contar cuántos suplementos hay en «El resto de la guía»** (punto 187): si son
   muchos, es una decisión suya y no una limpieza.

Comprobación en el navegador con las cinco pantallas de la maqueta, y **nada a producción sin
que lo pida**.

---

# Lo que salió al hacerlo (27-08)

## El 196 pedía una cosa más de la que parecía

Dice, de pasada: «no es lo mismo que *faltan 11 de proteína*, que es un número y **va en
blanco** con su número (punto 82)». O sea que no solo cambia «sin crear»: **«faltan X» estaba
en naranja y tenía que estar en blanco**.

Y encaja con la regla de color de la app entera, la del punto 76: *verde si ese macro ya está
resuelto, naranja si te has **pasado**, y sin color mientras vas por debajo*. Ir corto no es un
error, es que no has terminado. Con el naranja puesto, la mitad de las comidas de cualquier día
a medio montar salían en color de aviso.

Así que el estado de una comida pasa de dos tonos a tres, que es la lista literal del 196:

    ● cuadrada              verde
    ● válido +2             verde
    ● sobran 6 de grasa     #FF5A2E
      faltan 11 de proteína en blanco, sin punto
      sin crear             en gris, sin punto

Y el puntito que va al lado del nombre de la comida bajó al gris en los mismos dos casos.
**Resultado**: un día a medias no tiene ni un color en la lista de comidas, que es exactamente
lo que dice el pie de la maqueta.

## El 187 era pequeño, pero no gratis

Quitar el cajón «El resto de la guía» habría hecho **desaparecer de la guía** lo que hubiera
dentro. Contado antes: eran **2 fichas de 28**, y se recolocaron con
`backend/_colocar_huerfanos_guia_2708.py` (idempotente, con copia de seguridad):

    Citrulina malato     -> Rendimiento   (es un preentreno)
    Crema RELIEF EFFECT  -> Descanso      (esa categoría dice «tu sueño y TU RECUPERACIÓN»,
                                           y la crema es para la zona dolorida)

La crema es la única discutible. Si la quiere en Salud, se cambia en el guión y se vuelve a
correr.

## El 184 pedía «el mismo color que en Inicio», y no lo era

Puse la comida en `text-brand-orange`, que es **#FFA500**: el amarillo que él mismo señaló en el
punto 158 -- «ese amarillo no es de la casa». En Inicio el `+ Creatina` va en `text-brand`,
**#FF671F**. Ahora los dos son el mismo, y la comprobación lo mide.

## Y la comida sale con su número, no con una palabra

La maqueta dice **COMIDA 3** y **COMIDA 4**. El servidor da el hueco en simbólico -- «primera»,
«última» -- porque quien sabe cuántas comidas hay es la pantalla que tiene el día delante, y
Suplementos no lo tiene. Se resuelve pidiendo el número de comidas del cliente
(`GET /user/diet-config`), que es de donde sale también el reparto del Inicio. Sin ese dato se
dice «Primera comida» / «Última comida», que es verdad siempre.

## El 190 obligaba a tocar la fila del Inicio

El `+ Creatina` estaba **dentro** del botón de la comida, que lleva a Nutrición. Un botón dentro
de otro botón ni es HTML válido ni deja elegir destino, así que la tarjeta de la comida pasa a
tener dos partes: la fila de siempre y, debajo, la línea del suplemento con su propio destino.

---

## Las dos decisiones, cerradas: MANDA EL DOCUMENTO

**1 · El aviso de pasarse (27-08, Francisco: «respeta el documento»).** Por la mañana se hizo
lo del vídeo -- «macros **actuales**», botón «**Reajustar**» -- y por la tarde se revirtió a lo
que dibuja la parte 6:

    Este día se pasa de tus macros de ahora
    Si tus macros han cambiado, te reajustamos las cantidades sin quitarte nada.
    [ Cuadrar el día ]

Y el aviso de después también, que decía «Día reajustado»: si el botón dice una palabra, lo que
sale luego tiene que decir la misma.

**2 · El naranja de la cabecera (27-08, «manda el documento»).** El pie de la maqueta dice «ni
un color en toda la pantalla», así que **por debajo del objetivo ya no se pinta nada**, ni en
Nutrición ni en Inicio.

Esto revierte la decisión del 26-08 que había en `lib/estadoDelMacro` («a partir de 5 pinta
naranja, falte o sobre») y **vuelve a la regla del punto 76**, que es la que ese mismo fichero
tenía escrita arriba: *verde si ese macro ya está resuelto, naranja si te has pasado, sin color
mientras vas por debajo*. Lo que distingue faltar de sobrar sigue siendo la longitud de la
barra; ahora, además, el color.

Como el color pasa de dos casos a cuatro y lo leen **tres pantallas** (Inicio, la cabecera de
Nutrición y cada comida), la decisión se saca a `claseDelMacro`, `fondoDelMacro` y `llevaPunto`
en `lib/estadoDelMacro`: antes cada una lo resolvía con su propio ternario y bastaba con
olvidarse de una para que dijeran cosas distintas.

    'ok'       verde     ese macro ya está resuelto
    'pasado'   naranja   te has pasado
    null       blanco    vas por debajo
    'apagado'  gris      no es un estado («tu objetivo», «sin crear», «bloqueada»)

## Y los siete de la maqueta, hechos

1. **Los objetivos con letra**: `Objetivo · 33P · 20H · 10G`. Revierte el punto 115, igual que el
   173 revirtió el 98 para el Inicio.
2. **El día con su nombre**: «Jueves, 27 de agosto», también hoy. Y se cayó el `capitalize` del
   botón, que con la fecha larga ponía «27 **De Agosto**».
3. **«Nutrición»** en vez de «Plan nutricional»: era el único sitio de la app con otro nombre.
4. **«Comidas del día» también en el móvil**: estaba escondido en `lg`, y encima de la lista hay
   tres números grandes, un pie y a veces un aviso; sin el rótulo la lista empezaba sin que nada
   dijera que empezaba.
5. **Los Extras plegados, con su «+»** — sólo en Nutrición. En Inicio siguen abiertos: allí se
   apunta sobre la marcha y un toque de más es donde se pierde la gente. Y con algo apuntado se
   abre solo, que la lista no se esconde detrás de un botón.
6. **El intra y el post, con su estado**: estaban excluidos y en una lista de seis tomas dos no
   decían en qué punto estaban.
7. **«+ Creatina» también en Nutrición**. La regla sale de `TuDietaHoy` a
   `lib/suplementosDelDia`, porque ahora la pintan dos pantallas y con la cuenta escrita dos
   veces una se quedaría vieja sin que nadie lo viera.
