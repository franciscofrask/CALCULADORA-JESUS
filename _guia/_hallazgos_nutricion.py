# -*- coding: utf-8 -*-
"""LOS 14 HALLAZGOS DE LA REVISION DE NUTRICION (1-09), con su estado.

Vienen del recorrido funcional de la pestaña de Nutricion que se hizo en otra sesion
(artifact 7ae47ff3). Aqui estan para poder pintarlos DENTRO del repaso grande: Francisco
pidio que los tres documentos de Jesus y esto vivan en el mismo sitio.

Cada uno lleva:
  · lo que se vio, con la medida que lo prueba (suyo, no mio),
  · el veredicto de ahora: arreglado, esperando una decision, o pendiente,
  · y, si esta arreglado, que se hizo, en que commit y con que se comprueba.

LOS COMMITS SON REALES Y ESTAN EN PRODUCCION desde el 2-09. Si algun dia esto se copia a
otro sitio, que se copie con ellos: un «arreglado» sin commit no vale nada.
"""

HECHO = "hecho"
ESPERA = "espera"
PENDIENTE = "pendiente"

ETIQUETA_ESTADO = {
    HECHO: "Arreglado",
    ESPERA: "Espera una decisión",
    PENDIENTE: "Pendiente",
}

#: (numero, titulo, gravedad, estado, lo que se vio, la medida, lo que se hizo)
HALLAZGOS = [
    ("01", "Abrir un día para mirarlo lo reescribe, y le quita el «cuadrado»", "Grave", HECHO,
     "No hacía falta tocar nada: bastaba con abrir un día pasado y salir. El documento se "
     "volvía a guardar con la fecha de hoy y con el «cuadrado» recalculado con los macros de "
     "AHORA, así que un día que se cuadró en su momento dejaba de estarlo por consultarlo. De "
     "ese campo salen el verde del calendario y la cuenta de «cuadraste N días».",
     "antes  2026-08-19 · updated_at = 2026-08-24T23:18:32\n"
     "después 2026-08-19 · updated_at = 2026-09-01T22:27:21\n\n"
     "24-08 · is_cuadrado: true → false  (sin tocar un solo alimento)",
     "Ahora se guarda una HUELLA de cómo estaba el día al cargarlo, y sin cambios no se manda "
     "nada. La huella lleva solo lo que decide el cliente; «macros_snapshot», «is_cuadrado» y "
     "«distribution_targets» se quedan fuera a propósito, porque salen de los macros de hoy y "
     "con ellos dentro cualquier día viejo saldría «cambiado» siempre. Y se cerró un cuarto "
     "camino que la revisión no vio: el detector de tipo de día le ponía el de la rutina a "
     "TODOS los días, incluidos los ya configurados."),

    ("02", "Al abrir la pantalla, el objetivo del día es el del tipo de día equivocado", "Grave", HECHO,
     "En un día de descanso la cabecera arrancaba pidiendo los macros de un día de entreno, y "
     "no se corregía sola: seguía mal hasta tocar el selector Entreno/Descanso.",
     "al abrir            faltan 400 / 280 / 50\n"
     "tras tocar el selector  faltan 300 / 200 / 80",
     "El efecto que vuelve a pedir el reparto leía «loading» pero no lo tenía en sus "
     "dependencias, así que si el tipo cambiaba durante la carga, ese reparto no se pedía "
     "nunca. La carrera la cierra el primer commit (el detector corre después de cargar) y el "
     "segundo pone la red: la pantalla se corrige sola si lo que se ve deja de coincidir con "
     "el último reparto pedido."),

    ("03", "«Cuadrar» no cuadra la comida, y a veces la deja peor que antes", "Grave", ESPERA,
     "El botón principal de cada comida se queda corto de hidratos y puede estropear una "
     "comida que ya estaba bien. Con el arroz en 35 g la comida estaba en «válido» (28 de 30 H) "
     "y pulsar «Cuadrar» la bajaba a 25 g dejándola en «faltan 10».",
     "arroz 35 g  antes 50P 28H 10G (desvío 2,0)  →  25 g · 50P 20H 10G (10,0)  PEOR\n"
     "arroz 45 g  antes 50P 36H 10G (desvío 6,0)  →  25 g · 50P 20H 10G (10,0)  PEOR",
     "Reproducido con la cuenta de la revisión, cuya C1 es 50P/30H/10G. Y LA CAUSA NO ES LA "
     "QUE DECÍA EL DOCUMENTO: no es el redondeo. El pollo ya clava la proteína en el objetivo "
     "y «ajustar_cantidad» limita cada alimento por el macro más restrictivo, así que el arroz "
     "no puede crecer y cae a su mínimo de 25 g. El que cuadraría son 37,5 g → 35, pero esos "
     "35 g meten 2,45 g de proteína de más y la regla es «sin pasarse». O sea que la elección "
     "real es 50P/20H (faltan 10 H) contra 52,5P/28H (sobran 2,5 P), y hoy se elige la primera "
     "sin decirlo. Es una decisión del método: falta saber HASTA CUÁNTO se puede pasar de la "
     "proteína. Con ese número, el arreglo es corto."),

    ("04", "«Cuadrar el día» avisa de que el día quedó cuadrado cuando no lo está", "Grave", HECHO,
     "El aviso salía en cuanto la petición no fallaba, sin mirar el resultado, así que se "
     "quedaba el verde encima y los números de al lado diciendo lo contrario. Un mensaje que "
     "dice lo contrario de lo que se ve enseña a no leer los mensajes.",
     "decía    «Día cuadrado a tus macros.»\n"
     "se veía  PROTEÍNA 279 faltan 21 · HIDRATOS 181 faltan 19 · GRASA 92 sobran 12\n\n"
     "ahora    «El día no cuadra del todo: faltan 20,8 g de proteína, faltan 19,1 g\n"
     "          de hidratos y sobran 11,6 g de grasa. No se ha quitado nada más.»",
     "Se suma el desfase de todas las comidas y se dice lo que hay. El listón de los 4 g y las "
     "palabras salen ahora de un solo sitio, compartido con el «Cuadrar» de una comida: los "
     "dos botones hacen lo mismo y tienen que contarlo igual."),

    ("05", "El PDF y el guardado de despedida trabajan en la cuenta equivocada", "Grave", HECHO,
     "Con el entrenador dentro de la calculadora de un cliente, toda la pantalla manda "
     "«X-Actuar-Como» menos dos llamadas que se montan su propio «fetch». El PDF se descargaba "
     "el día del ENTRENADOR con el nombre del día del cliente. Y el guardado de despedida, que "
     "además ESCRIBE, le creaba al entrenador la dieta del cliente en su propia cuenta: salta "
     "al pasar la pestaña a segundo plano, o sea cambiando de pestaña.",
     "GET /api/diets/2026-09-01/pdf\n"
     "X-Actuar-Como: (NO LA MANDA)\n\n"
     "ahora  PDF       X-Actuar-Como: f99879aa-…\n"
     "       guardado  X-Actuar-Como: f99879aa-…",
     "Las dos pasan ya por «lib/cabeceras», que es donde vive la regla desde el 17-08. Era el "
     "mismo fallo de entonces con dos sitios que se quedaron fuera."),

    ("06", "Se puede dejar fuera el catálogo entero y la app dice que sí puede cuadrarte", "Grave", HECHO,
     "La franja que frena una configuración imposible solo miraba los alimentos PREFERIDOS, "
     "así que se podían marcar los 37 grupos para evitar, seguía diciendo «podemos cuadrarte» "
     "y guardaba sin protestar. Detrás, el sugeridor pasaba de 223 opciones a «No hay menús "
     "para esta comida».",
     "con todo marcado como PREFERIDO:   proteina true · hidratos true\n"
     "y todo marcado además para EVITAR: proteina false · hidratos false\n"
     "evitando solo un grupo:            proteina true · hidratos true",
     "Los evitados viajan ya con la pregunta y se descuentan con la MISMA regla que los "
     "descuenta en el resto de la app, no con una copia. Y el efecto ya no depende solo de los "
     "marcados: antes, marcar algo para evitar ni siquiera volvía a preguntar. La tercera "
     "línea de la prueba está a propósito: evitar un grupo suelto no puede tumbar la franja."),

    ("07", "La «X» del calendario está encima de la flecha de mes siguiente", "Medio", HECHO,
     "Al ir a avanzar de mes por la esquina del botón se cerraba el calendario: quien recibía "
     "el clic ahí era el botón de cerrar. Y en móvil ese botón medía 18 × 18 px, menos de la "
     "mitad del mínimo cómodo para el dedo.",
     "antes  la esquina de la flecha la recibe «Close» · cerrar 18×18\n"
     "ahora  la esquina de la flecha la recibe la flecha · cerrar 36×36",
     "NO ERA DEL CALENDARIO: el botón vive en «ui/dialog.jsx», o sea en todos los diálogos de "
     "la app. Pasa de 18×18 a 36×36 sin mover ni un píxel la equis que se ve, así que ningún "
     "diálogo cambia de aspecto, y el calendario deja hueco para que la flecha se aparte. De "
     "paso se anuncia «Cerrar» y no «Close», que era el texto de shadcn sin traducir."),

    ("08", "El PDF dice «descargado» y deja un fichero a medias", "Medio", HECHO,
     "El contenido llegaba entero pero la descarga no se cerraba nunca: quedaba un "
     "«.crdownload» y el cliente no tenía ningún PDF que abrir.",
     "aviso en pantalla: «PDF descargado»\n"
     "en Descargas:      dieta_jg12_2026-08-19.pdf.crdownload  6.768 bytes\n"
     "del servidor:      6.768 bytes  (el fichero completo)",
     "«revokeObjectURL» iba en la misma vuelta que el clic: se le quitaban los datos al "
     "navegador mientras los leía. Ahora el enlace se mete en el documento antes de pulsarlo y "
     "la URL se suelta después. CON UNA SALVEDAD: el guion de comprobación no distingue, pasa "
     "igual antes y después, porque Playwright se queda la descarga por su cuenta. El "
     "«.crdownload» se midió en un Chrome de verdad."),

    ("09", "El calendario no marca el día que estás mirando", "Medio", HECHO,
     "Solo se resaltaba «hoy». Quien estaba en el 15 de agosto y abría el calendario para "
     "saltar a otro día no tenía nada que le dijera de dónde venía, y el calendario se abre "
     "justo para eso.",
     "",
     "El día abierto va relleno y con «aria-current=date»; hoy conserva su aro, que son dos "
     "cosas distintas y tienen que distinguirse cuando coinciden. Y el calendario se abre en "
     "el mes del día que se está mirando, no en el de hoy."),

    ("10", "El calendario da por «completo» cualquier día con cuatro comidas", "Medio", HECHO,
     "El número de comidas estaba escrito a mano en el servidor teniendo el propio día el "
     "suyo: un día de TRES comidas no llegaba nunca a «completo» y uno de seis lo alcanzaba a "
     "medias.",
     "día de 3 comidas con las 3 puestas   antes «partial»   ahora «complete»",
     "Sale del «num_comidas» del propio día. Y el peri no cuenta ni arriba ni abajo: son las "
     "comidas normales, y el intra y el post no los llevan todos los días."),
]

#: Los menores, que son de una línea.
MENORES = [
    ("Los avisos se apilan y tapan la esquina", PENDIENTE,
     "Llegó a haber tres a la vez cubriendo el botón «···» de la comida y el panel de extras; "
     "hubo que quitarlos para poder seguir pulsando."),
    ("«Este día se pasa de tus macros de ahora» cuando el día se queda corto", PENDIENTE,
     "En el 19 de agosto faltaban 199 g de proteína y 200 de hidratos, y solo sobraban 7 de "
     "grasa. El titular dice lo contrario de lo que pasa."),
    ("«Con lo que has marcado podemos cuadrarte 20 g de proteína»", PENDIENTE,
     "Se lee como un techo cuando es un mínimo de viabilidad. Con el catálogo entero "
     "disponible, suena a mala noticia."),
    ("El botón de cerrar se anunciaba en inglés («Close»)", HECHO,
     "Arreglado con el punto 07, y en TODOS los diálogos de la app: no era del calendario."),
]

SIN_CERRAR = (
    "La pestaña se congeló tres veces durante la revisión: más de un minuto sin responder y "
    "sin recuperarse, quemando 8,75 s de CPU en 6 s de reloj con 757 MB de memoria y sin un "
    "solo error en la consola. No se pudo acotar, y en navegador limpio y automatizado no se "
    "reproduce (doce vueltas alternando tipo de día dejan la memoria estable entre 38 y 64 MB, "
    "sin fugas). Las tres veces ocurrió con la extensión de automatización inyectando en la "
    "página, así que queda apuntado con lo medido y sin venderlo como fallo de la pantalla."
)

COMMITS = "50e0e49 · 818ac98 · 3bd9c19 · b4577d9"
