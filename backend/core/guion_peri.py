"""Lo que Marco dice en el intra y en el post. Palabras de Jesus, literales.

Estos textos son METODO, no conversacion: dicen qué se toma en el peri-entreno, por qué y
cómo. Los escribió Jesús y van tal cual.

POR QUE ESTAN AQUI Y NO EN EL PROMPT
------------------------------------
Por dos motivos, y los dos importan:

1. **Un modelo parafrasea.** Si el texto va en el prompt, cada cliente recibe una version
   distinta de la recomendación de Jesús. Aquí sale la suya, igual para todos, siempre.

2. **La regla del 8 bis: en el prompt no entran nombres de comida.** No es manía: el sistema
   viejo llevaba 83 sinónimos de alimentos dentro del prompt y por ahí se rompía todo, y hay
   un test (`tests/test_prompt_sin_alimentos.py`) que falla si aparece uno. Estos textos
   llevan 23 palabras del catálogo -- ciclodextrina, dextrosa, whey, crema, arroz, arándanos,
   plátano, queso, almendra... --, así que en el prompt no caben. Como respuesta fija, sí:
   aquí no compiten con la búsqueda ni sesgan lo que el agente propone.

El agente los pide con la herramienta `guion_del_peri` cuando el cliente llega al intra o al
post, y los suelta tal cual. Lo que rodea al texto (saludar, encadenar, cerrar la comida)
sigue siendo suyo.
"""
from typing import Optional

INTRA = (
    "Para el intra te recomiendo combinar MAP -aminoácidos esenciales- con hidratos de "
    "carbono de asimilación rápida. Mi favorito es la ciclodextrina, mezclado con agua o "
    "con bebida isotónica sin azúcar. Eso te lo ajusto yo de forma automática. Te lo vas "
    "bebiendo a pequeños sorbos durante el entrenamiento, al menos 700 ml.\n\n"
    "Si te cuadra, te digo exactamente la cantidad que necesitas de cada cosa. Y si no, te "
    "propongo otras alternativas."
)

INTRA_ALTERNATIVA = (
    "Como alternativa te propongo MAP o aminoácidos esenciales en polvo mezclados con una "
    "bebida isotónica normal -con azúcar, no light, tipo Aquarius-. De esa forma sacamos "
    "los hidratos de la propia bebida. Siempre en la cantidad que necesitas."
)

# Si no quiere ciclodextrina: el resto de hidratos de intra que tenga la calculadora,
# empezando por la dextrosa, que es mas economica.
INTRA_OTRO_HIDRATO = (
    "Sin problema. Tenemos otros hidratos rápidos para el intra; el más económico es la "
    "dextrosa. Te lo ajusto yo en la cantidad que necesitas."
)

MARCA = ("Yo uso FullGas, y por ser cliente tienes un descuento con el código GALLEGO10.")

POST = (
    "Para el post te recomiendo una proteína de calidad y que se asimile rápido. Mi "
    "favorita es el aislado, el whey isolate, con crema de arroz, o con crema de arroz y "
    "fruta.\n\n"
    "Mi combinación favorita: proteína en polvo, crema de arroz y fruta congelada -a mí me "
    "encantan los arándanos-, todo con 300 ml de bebida de almendra sin azúcar y hielo "
    "picado, a la batidora. Aunque en esta comida no metemos grasas, tienes hasta 4 g de "
    "margen justo para esto.\n\n"
    "Si te cuadra, te digo exactamente la cantidad que necesitas de cada cosa. Y si no, te "
    "propongo otras alternativas."
)

POST_SIN_BATIDO = (
    "También tienes otras combinaciones, pero aquí tampoco vale cualquier cosa. Por "
    "ejemplo, queso batido con fruta: un plátano."
)

_GUIONES = {
    ("intra", "principal"): INTRA,
    ("intra", "alternativa"): INTRA_ALTERNATIVA,
    ("intra", "otro_hidrato"): INTRA_OTRO_HIDRATO,
    ("post", "principal"): POST,
    ("post", "alternativa"): POST_SIN_BATIDO,
    ("post", "sin_batido"): POST_SIN_BATIDO,
}

# LO QUE NOMBRA CADA GUION, para que las tarjetas digan lo mismo que el texto.
#
# Francisco, 13-08-2026: «me hace una recomendación, luego una sugerencia, y no veo el MAP
# que él mismo me ofrece en un principio». Tenía razón: el texto recomendaba MAP con
# ciclodextrina y debajo salían Powerade, Aquarius y amilopectina. Todo eso vale para un
# intra -- son del universo del peri --, pero no es lo que se acaba de recomendar, y el
# cliente se queda buscando en la lista lo que le han dicho.
#
# Van AQUÍ y no en el prompt por lo mismo que los textos: la regla del 8 bis prohíbe nombres
# de comida en el prompt, y además así el día que Jesús cambie su recomendación, el texto y
# los alimentos se cambian en el mismo sitio y no se pueden desparejar.
#
# Son términos de BÚSQUEDA, no ids: resolverlos contra el catálogo de cada base ya es
# trabajo del buscador de siempre.
#
# UNA LISTA POR PIEZA, y dentro los nombres de ESA pieza por orden de preferencia. Importa:
# «MAP -aminoácidos esenciales-» es una aposición, un mismo polvo con dos nombres, y en
# plano se convertía en dos piezas -- dos proteínas en un intra que solo pide una --. Así
# son dos piezas, la proteína y el hidrato, que es lo que dice el texto; y el segundo nombre
# queda de respaldo para cuando el primero no está en el catálogo de ese cliente.
ALIMENTOS_DEL_GUION = {
    ("intra", "principal"): [["MAP", "aminoácidos esenciales"], ["ciclodextrina"]],
    ("intra", "alternativa"): [["MAP", "aminoácidos esenciales"], ["bebida isotónica"]],
    ("intra", "otro_hidrato"): [["dextrosa"], ["MAP", "aminoácidos esenciales"]],
    ("post", "principal"): [["aislado de suero", "whey isolate"], ["crema de arroz"],
                            ["arándanos"]],
    ("post", "alternativa"): [["queso batido"], ["plátano"]],
    ("post", "sin_batido"): [["queso batido"], ["plátano"]],
}


def piezas_del_guion(momento: str, variante: str = "principal") -> list:
    """Las piezas que nombra ese guion, en el orden en que las dice.

    Cada pieza es una lista de nombres de la MISMA cosa, el preferido primero.
    """
    clave = ((momento or "").strip().lower(), (variante or "principal").strip().lower())
    return [list(p) for p in (ALIMENTOS_DEL_GUION.get(clave) or [])]


def alimentos_del_guion(momento: str, variante: str = "principal") -> list:
    """El nombre principal de cada pieza: lo que hay que montar, una cosa por pieza."""
    return [p[0] for p in piezas_del_guion(momento, variante) if p]


def guion(momento: str, variante: str = "principal") -> Optional[str]:
    """El texto de Jesus para ese momento, o None si no hay guion escrito.

    `momento`: "intra" o "post". `variante`: "principal", "alternativa" o, en el intra,
    "otro_hidrato".
    """
    texto = _GUIONES.get(((momento or "").strip().lower(), (variante or "principal").strip().lower()))
    if texto and momento and momento.strip().lower() == "intra" and variante != "principal":
        return f"{texto}\n\n{MARCA}"
    return texto
