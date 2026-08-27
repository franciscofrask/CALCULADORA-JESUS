# -*- coding: utf-8 -*-
"""EL NOMBRE DEL SUPLEMENTO QUE VE EL CLIENTE (video de Jesus del 27-08).

EL PROBLEMA, MEDIDO. De las 528 lineas de suplemento vigentes en produccion, 305 llevan la
chuleta interna de Jesus dentro del nombre, y las ven 97 de los 100 clientes con protocolo:

    Omega 3 hombre · Creatina hombre · Aceite de krill 4 perlas · Fat burner hardcore mes 3
    Hydropeptides o MAP 15g · Selenio 1 capsula · Pre-workout 3 dosis
    Sinefrina con termogenico mes 1 (1 capsula primeras 2 semanas y a partir de la semana 3...)

LO QUE EL DICE, tres veces y con estas palabras:

    «Al cliente le va a aparecer este nombre siempre.»                                 [1:00]
    «El solamente ve Aceite de krill. NO tiene que ver Aceite de krill, tres perlas.»   [2:35]
    «Ve el nombre del suplemento, pero NO ve lo de hombre o lo de mujer. Ve solamente
     el nombre.»                                                                       [4:37]

De donde viene: el catalogo tiene dos familias. Las fichas hechas a mano (`seed-*`) estan
limpias y usan el campo `sexo` para la variante -- «Monohidrato de creatina», sexo hombre,
10 g --, que es exactamente lo que el describe. Las importadas de la guia (`guia:*`) se
trajeron su nombre de referencia como si fuera el del cliente, y los protocolos apuntan a esas.

POR QUE SE LIMPIA AL SERVIR Y NO EN LA BASE. El nombre con la dosis es SU chuleta y le sirve:
en el panel tiene que seguir viendo «Aceite de krill 3 perlas» para saber cual de las dos
versiones le puso a quien. Son dos vistas del mismo dato, igual que en Calma. El panel lee el
protocolo por `/admin/clients/{id}` y el cliente por `/supplements/current`: se limpia solo en
el segundo y nadie pierde nada.

QUE SE QUITA Y QUE NO. Solo lo que va AL FINAL y es inconfundiblemente suyo. Lo de en medio no
se toca, aunque huela a dosis: equivocarse quitando de menos deja un nombre feo, y equivocarse
quitando de mas deja un nombre que no es el del producto. Por eso «Cafeina anhidra 200 mg» se
queda con sus 200 mg (es la capsula que compra, no la dosis que le pauta) y «Whey Isolate +
crema de arroz (post-entreno)» conserva su parentesis, que ahi si dice algo.

Lo que hoy NO limpia, y esta bien que no lo haga (son 6 lineas de 528):
  - «Bebida intra 15 g ciclo + 15 g de hydro» y sus tres variantes: la dosis va en medio y es
    lo que distingue una de otra.
  - «Niacina Flush Free (subir HDL, 2 meses)»: el parentesis es una nota, no una dosis.
"""
import re
from typing import Optional

#: Lo que se corta del FINAL del nombre. En orden: se aplican todas, una detras de otra, hasta
#: que ninguna muerda. Cada una lleva delante el caso real que la justifica.
_COLAS = (
    # «Omega 3 hombre» (97 lineas), «Creatina mujer» (13). Sus palabras: «no ve lo de hombre
    # o lo de mujer».
    r"\s+(?:hombre|mujer)$",
    # «Fat burner hardcore mes 3» (47), «Sinefrina con termogenico mes 1 (1 capsula...)» (~25),
    # «Cafeina anhidra mes 1 protocolo light». Desde el «mes N» se corta todo lo que siga.
    r"\s+mes\s*\d+\b.*$",
    # «MONACOLINA PROTOCOLO 2».
    r"\s+protocolo\s*\d+\b.*$",
    # «Aceite de krill 3 perlas» (4), «Vitamina D3 + K2 4 perlas» (3). Su ejemplo del video.
    r"\s+\d+(?:[.,]\d+)?\s*perlas?$",
    # «Selenio 1 capsula» (4), «Selenio 2 capsulas» (2), «SAME + Betaina 3 Cap» (6).
    r"\s+\d+(?:[.,]\d+)?\s*(?:c[aá]psulas?|caps?)$",
    # «Ursobilane 500 mg 2 tomas» (2), «Total electrolitos 2 tomas» (1).
    r"\s+\d+(?:[.,]\d+)?\s*tomas?$",
    # «Pre-workout 3 dosis» (19), «Pre-workout 2 dosis» (1).
    r"\s+\d+(?:[.,]\d+)?\s*dosis$",
    # «Hydropeptides o MAP 15g» (23) y «10g» (6). Gramos a secas, NO «mg»: los 200 mg de la
    # cafeina son la capsula que compra, no lo que le pauta, y esos se quedan.
    r"\s+\d+(?:[.,]\d+)?\s*g$",
    # «Cafeina anhidra 200 mg suelta» (3): «suelta» es como el distingue la que va sola.
    r"\s+suelta$",
    # «CBD 40% CON DOSIS MARCADA».
    r"\s+con\s+dosis\s+marcada$",
)

_COLAS_COMPILADAS = tuple(re.compile(p, re.IGNORECASE) for p in _COLAS)


def nombre_para_el_cliente(titulo: Optional[str]) -> str:
    """El nombre del suplemento tal y como tiene que verlo el cliente.

    Si al quitar la cola no quedara nada -- un suplemento que se llamara solo «3 perlas» --,
    se devuelve el original: mas vale un nombre feo que ninguno.
    """
    limpio = (titulo or "").strip()
    if not limpio:
        return limpio
    cambia = True
    while cambia:
        cambia = False
        for patron in _COLAS_COMPILADAS:
            recortado = patron.sub("", limpio).strip()
            if recortado and recortado != limpio:
                limpio, cambia = recortado, True
    return limpio or (titulo or "").strip()
