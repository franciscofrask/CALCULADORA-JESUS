# Vídeo de Jesús del 27-08 · «cómo quiero la pestaña de suplementación»

Fuente: https://vimeo.com/1221647441/d1a5364751 · 9 min 15 s.
Transcripción entera en `_guia/_video_2708/transcripcion.txt`; las tres capturas que valen,
en esa misma carpeta. Comparte pantalla los cinco primeros minutos (Calma) y a partir del 5:00
enseña el móvil a cámara, que no se lee: de ahí en adelante manda la voz.

---

## 1 · DESBLOQUEA MEDIO PUNTO 174, y el dato ya lo tenemos

El vídeo va casi entero de esto. Lo que dice, con sus palabras:

> [1:00] «Al cliente le va a aparecer este nombre siempre.»
> [2:35] «Él solamente ve *Aceite de krill*. **No tiene que ver Aceite de krill, tres perlas**.»
> [4:37] «Ve el nombre del suplemento, pero **no ve lo de hombre o lo de mujer**, no. Ve solamente el nombre.»
> [4:45] «¿Qué quiero yo? Que, por ejemplo, monohidrato de creatina, pues **que salga en desayuno**. O sea, que salga *creatina*. **No la dosis, sino el nombre.**»

Y en el segundo 4:56 lo enseña sin lugar a dudas: **tiene seleccionada con el ratón la palabra
«desayuno»** dentro del `¿Cuándo?` de «Monohidrato de creatina»
(`_guia/_video_2708/03_desayuno_seleccionado.png`). O sea, de dónde sale la comida.

**Cómo funciona en Calma** (capturas 01 y 02):

| Lo que ve JESÚS en su lista | Lo que ve EL CLIENTE |
|---|---|
| `Aceite de krill 3 perlas` | **Aceite de krill** |
| | ¿Cuándo? Todos los días, en dos tomas (desayuno y cena) |
| | ¿Cuánto? 3 perlas por toma (3 g al día) |
| | Observaciones: guárdalo siempre en frío |

El nombre con la dosis es su chuleta para acordarse de qué versión puso; el cliente ve el
nombre limpio y el detalle en `¿Cuándo?` y `¿Cuánto?`.

**Y ese modelo ya lo tenemos**: `supplement_catalog` lleva `titulo`, `cuando`, `cuanto`,
`observaciones`, `sexo`. Las fichas hechas a mano (`seed-*`) están bien:

    seed-creatina-hombre  titulo «Monohidrato de creatina»  sexo hombre  cuanto «10 g»
    seed-creatina-mujer   titulo «Monohidrato de creatina»  sexo mujer   cuanto «5 g»

y su `cuando` es, literal, **«Todos los días, con el desayuno (entrenes o no)»**: la misma
frase que él subrayó en el vídeo. Así que la fuente de la comida está en nuestra base.

### HECHO el 27-08, con la opción C

Se decidió que mandaran las dos cosas, en este orden: **lo que elija el coach en la ficha, y si
no ha elegido, lo que diga el «¿Cuándo?»**. Así funciona desde el primer día sin que él toque
nada, y solo corrige lo que salga torcido.

- Regla y por qué, con los números: `backend/core/comida_del_suplemento.py`
- Se resuelve al servir el protocolo, **no se guarda**: si mañana cambia el texto o la ficha, el
  sitio cambia con él y no queda una copia vieja diciendo otra cosa.
- Desplegable **«¿Con qué comida sale en su Inicio?»** en la ficha del catálogo
  (`SupplementsCatalogPage`), con «Automático» de fábrica.
- Se pinta en `TuDietaHoy`: «+ Creatina» debajo de los macros, **solo el nombre**. El intra y el
  post no llevan nada, que es lo que dice el propio punto.
- Comprobado en el navegador: `_guia/_p174_suplementos_2708.js` y `_guia/_p174_ficha_2708.js`.
  26 casos de la regla en `backend/tests/test_comida_del_suplemento_2708.py`.

**Con los 528 suplementos vivos de producción, así queda el reparto:**

| | |
|---|---|
| Caen solas en una comida | 206 · 39 % |
| Van con el entreno, y por eso **no llevan nada debajo** | 235 · 45 % |
| El texto no dice comida, y se quedan sin salir hasta que él las coloque | 87 · 16 % |

**Y queda una cosa que decirle**: con esta regla la creatina sale en la **Comida 1**, porque su
«¿Cuándo?» dice «con el desayuno». En el punto 174 él la dibujó en la **3**. Si la quiere en la
3, ahora se cambia en dos clics desde el desplegable de la ficha; pero conviene avisarle o
pensará que está mal.

---

## 2 · UN FALLO VIVO QUE NO ESTABA EN NINGÚN DOCUMENTO

**97 de los 100 clientes con protocolo están viendo el nombre interno de Jesús.**

Medido contra producción, sobre la versión vigente hoy:

- 528 líneas de suplemento que la gente ve.
- **305 llevan dentro su chuleta**: `Creatina hombre` (738 usos históricos), `Omega 3 hombre`
  (780), `Aceite de krill 4 perlas`, `Fat burner hardcore mes 3`, `Hydropeptides o MAP 15g`,
  `Sinefrina con termogénico mes 2 (sube 2 y 1 las dos primeras semanas y sube a 2 y 2 a partir
  de la semana 3)`…
- 48 de los 83 títulos distintos en uso.

Se ve en dos sitios: `SupplementsPage.jsx:34` y `:86` pintan `item.titulo` tal cual, y el Inicio
lo repite en una línea (`ClientDashboard.jsx:554`, `nombresSuplementos`).

**De dónde viene.** `supplement_catalog` tiene dos familias. Las `seed-*`, hechas a mano, están
limpias («Monohidrato de creatina», `sexo: hombre`). Las `guia:*`, importadas de la guía, se
trajeron la chuleta como si fuera el nombre del cliente:

    guia:creatina-hombre           titulo «Creatina hombre»            sexo ambos
    guia:aceite-de-krill-3-perlas  titulo «Aceite de krill 3 perlas»   sexo ambos

y los protocolos de la gente apuntan a esas.

**Esto no es una interpretación mía**: lo dice tres veces y con esas palabras. Es lo primero que
hay que arreglar de suplementación, y encaja con lo que él mismo remata en el 7:53: «no quiero
que sea cuello de botella los suplementos».

### HECHO el 27-08 · se limpia AL SERVIR, y solo para el cliente

**Sin tocar un solo dato.** El nombre con la dosis es SU chuleta y le sirve: en el panel tiene
que seguir viendo «Aceite de krill 3 perlas» para saber cuál de las dos versiones le puso a
quién. Son dos vistas del mismo dato, igual que en Calma, y da la casualidad de que ya salen
por endpoints distintos: el panel lee por `/admin/clients/{id}` y el cliente por
`/supplements/current`. Se corta solo en el segundo.

- La regla, con los 53 nombres reales delante: `backend/core/nombre_del_suplemento.py`
- **Cambian 34 nombres, 328 de las 528 líneas vivas.**
- Solo se corta lo que va **al final** y es inconfundiblemente suyo: ` hombre`/` mujer`,
  ` N perlas`, ` N cápsulas`, ` N tomas`, ` N dosis`, ` mes N (…)`, ` protocolo N`, ` NNg`,
  ` suelta`, ` CON DOSIS MARCADA`.
- **Lo de en medio no se toca**, aunque huela a dosis: «Cafeína anhidra **200 mg**» se queda con
  sus 200 mg (es la cápsula que compra, no lo que le pauta), «Whey Isolate + crema de arroz
  **(post-entreno)**» conserva su paréntesis, y las cuatro «Bebida intra 15 g ciclo + 15 g de
  hydro» se quedan enteras porque esos gramos son lo único que las distingue.
- 44 casos en `backend/tests/test_nombre_del_suplemento_2708.py`, la mitad de ellos probando lo
  que **NO** se toca, que es donde se puede hacer daño.
- Comprobado en el navegador (`_guia/_nombres_suplementos_2708.js`): el cliente ve «Creatina» y
  el panel sigue viendo «Creatina hombre».

Quedan **6 líneas de 528** que siguen enseñando su chuleta y están bien así: las cuatro bebidas
intra y «Niacina Flush Free (subir HDL, 2 meses)». Si las quiere limpias, se cambia el nombre en
la ficha y ya.

---

## 3 · LA RUTINA: la palabra PDF fuera, y NO ABRE

> [5:53] «Y la rutina en PDF, no.»
> [6:06] «Tarda en abrirse, estoy tocando y no abre. No sé por qué. Toco y no abre. **No abre la rutina**.»
> [8:46] «Directamente que le abra. Esto de *tu rutina en PDF, tu entrenador te la ha preparado*.
> Esto no. Que directamente, si tienes rutina, que le abra. **Olvida el PDF. Olvida la palabra
> PDF. Eso no tiene sentido.**»

Los dos textos que cita están localizados, palabra por palabra:

- `ClientDashboard.jsx:892` — «Tu rutina, en PDF» · «Abrirla»
- `RoutinePage.jsx:249-251` — «Tu rutina, en PDF» + «Tu entrenador te la ha preparado el {fecha}.»

**Y el «no abre» tiene causa.** `abrirPdfRutina` (`ClientDashboard.jsx:610`) hace:

    const r = await api.get('/routines/pdf', { responseType: 'blob' });
    window.open(URL.createObjectURL(...), '_blank');

El `window.open` va **después de un `await`**, así que el navegador ya no lo cuenta como gesto
del usuario: **Safari de iPhone lo bloquea en silencio**. Él toca, no pasa nada, y no sale ni
aviso porque el `catch` solo salta si falla la petición. Es exactamente lo que describe.

### HECHO el 27-08

- **La ventana se abre dentro del toque** y se le pone el fichero cuando llega:
  `frontend/src/lib/abrirRutina.js`. Vive en un solo sitio porque el fallo estaba **copiado en
  tres pantallas** (Inicio, Entreno y Rutina) y arreglar dos de tres no arregla nada.
- **Medido, y reproducido antes y después.** Con el fallo puesto, del toque a la ventana pasan
  **492 ms**: el gesto ya está perdido. Con el arreglo, **4 ms**. Y no vale probar «si abre en
  Chrome»: Chrome de escritorio no bloquea nada y abriría igual con el fallo dentro. Lo que se
  mide es el salto del toque a la ventana (`_guia/_rutina_abre_2708.js`).
- **Fuera la palabra PDF** de todo lo que ve el cliente: la línea del Inicio, el botón de
  Entreno, el título y el subtítulo de la ficha de Rutina, el enlace de la semana y hasta el
  `aria-label` del visor. «Tu rutina, en PDF» → «Tu rutina»; «Tu entrenador te la ha preparado
  el 12 de agosto» → «Preparada el 12 de agosto»; «Abrir el PDF» → «Abrirla entera».
  Comprobado barriendo la pantalla entera: no queda ni una.

---

## 4 · TRES TEXTOS MÁS

**El aviso de «te pasas de tus macros»** [6:52-7:38], con sus correcciones:

- «Este día se pasa de tus macros» → «Este día se pasa de tus macros **actuales**»
- «Si tus macros han cambiado, podemos reajustar las cantidades **sin quitarte nada**»
- El botón: no «recuadrar el día» → **«Reajustar»**
- Y avisa: «te digo ese mensaje, pero **hay muchos más**. Tengo que revisar esto despacio.»

**HECHO el 27-08** (`NutritionPage.jsx`). El «sin quitarte nada» ya estaba; lo que faltaba era
«actuales» y el botón. Y de paso el aviso de después, que seguía diciendo «Día recuadrado a tus
macros»: el botón dice una palabra y lo que sale luego tiene que decir la misma.
Comprobado montando un día que se pasa de verdad (`_guia/_aviso_macros_2708.js`).

**Sigue abierto lo que él mismo dice**: «hay muchos más» mensajes por repasar. Ese repaso es un
frente aparte y no está hecho.

**El buscador de alimentos** [8:04]: «Veo muy cargada la búsqueda de alimentos. Lo veo muy
cargado. Esta pantalla.» Lo dice mirando **producción**, o sea la de antes de lo de hoy: los
puntos 145 a 160 de la parte 5 son justo eso (cuatro líneas, una categoría, sin colores, la
leyenda recortada y el botón de pedir al final). Ya está hecho y sin desplegar.

**Extras del día** [5:09-5:52]: «lo que hay dentro del texto, la caja, sale muy grande. Tiene
que tener el mismo tamaño de letra que… o cursiva más pequeña. Como tiene, por ejemplo, *para
rellenar al final del día, último registro*. Esa letra tiene que ser más pequeña la que está en
la caja. **No puede ser más grande que lo que está afuera**.» → Es el **punto 176, y está hecho
hoy**: la ayuda quedó en 13,5 px contra los 15,75 px de la instrucción. Confirmado.

---

## Resumen: qué cierra y qué abre

**Todo lo del vídeo está hecho y comprobado en el navegador. Sin desplegar.**

| | |
|---|---|
| **El 176** | Ya estaba bien: lo describe igual que se hizo. |
| **El 174** | Hecho con la opción C: manda la ficha, y en automático manda el «¿Cuándo?». |
| **El nombre interno** | Hecho. 328 de 528 líneas cambian para el cliente; el panel conserva la chuleta. Sin tocar un dato. |
| **La rutina** | Hecha. Del toque a la ventana: 492 ms antes, 4 ms ahora. Y ni una «PDF» delante del cliente. |
| **Los textos** | Hechos: «macros actuales» y botón «Reajustar», y el aviso de después con la misma palabra. |

**Lo que queda, y son dos cosas que dependen de él:**

1. **Decirle lo de la creatina.** Con la regla sale en la **Comida 1** (su «¿Cuándo?» dice «con
   el desayuno») y en el punto 174 él la dibujó en la **3**. Se cambia en dos clics desde el
   desplegable de la ficha, pero si no se lo avisamos pensará que está mal.
2. **«Hay muchos más» mensajes por repasar**, dicho por él en el minuto 7:38. Ese repaso es un
   frente aparte y no está empezado.
