# -*- coding: utf-8 -*-
"""CON QUE COMIDA SALE CADA SUPLEMENTO (punto 174 del artifact del 27-08).

El punto pide que en el Inicio, debajo de los macros de una comida, salga el suplemento que
toca con ella: «+ Creatina debajo de los macros de la comida 3». Hasta hoy no se podia hacer
porque el dato no existia: lo unico guardado es el `¿Cuando?`, un texto que escribe Jesus.

QUIEN MANDA, EN ESTE ORDEN (la opcion C, decidida el 27-08 con los numeros delante):

  1. Lo que haya elegido el coach en la ficha (`comida`). Si esta puesto, se acabo.
  2. Si no, se deduce del `¿Cuando?`.
  3. Si el texto no dice nada claro, el suplemento NO sale en ninguna comida y se queda solo
     en su pestana, como hasta ahora. Nunca se inventa un sitio.

POR QUE LAS DOS COSAS Y NO UNA. Medido contra produccion el 27-08, sobre las 528 lineas de
suplemento vivas (son 23 textos distintos en total, asi que se puede contar exacto):

    206  39 %  caen solas en una comida  («con el desayuno», «desayuno y cena»)
    235  45 %  van con el entreno         (el intra, el post, «30 minutos antes de empezar»),
                                          y esos NO llevan nada debajo: es el propio punto 174
     87  16 %  el texto no dice comida    («al despertar», «haciendolas coincidir con el
                                          termogenico», «en cualquier momento del dia»)

O sea: de lo que de verdad va con una comida, el texto coloca casi todo, y lo que queda a
oscuras son 87 lineas. Con solo el texto esas 87 no saldrian nunca; con solo la mano habria que
repasar 106 fichas antes de ver nada en pantalla. Asi se ve desde el primer dia y el coach solo
toca lo que salga torcido.

LA PRIMERA Y LA ULTIMA, NO «COMIDA 1» Y «COMIDA 4». Un cliente puede tener de una a cuatro
comidas, asi que «la cena» es la C3 en unos y la C4 en otros. Se devuelve el hueco en simbolico
y lo resuelve la pantalla, que es la que sabe cuantas comidas tiene el dia delante.

EL INTRA Y EL POST NO LLEVAN NADA DEBAJO, y por eso «durante el entreno» y «despues de
entrenar» acaban en «ninguna»: son sus palabras en el mismo punto 174, «ellos son el
suplemento, y ponerles otro debajo confunde».
"""
import re
import unicodedata
from typing import List, Optional

#: Lo que puede haber elegido el coach. `""`/None significa «deducelo tu».
PRIMERA = "primera"
ULTIMA = "ultima"
NINGUNA = "ninguna"
COMIDAS_FIJAS = ("C1", "C2", "C3", "C4")
ELECCIONES = ("", PRIMERA, ULTIMA, NINGUNA) + COMIDAS_FIJAS


def _plano(texto: str) -> str:
    """En minusculas y sin tildes: el coach escribe «Desayuno», «desayuno» y «Cena» sin
    criterio fijo, y una tilde no puede decidir donde sale un suplemento."""
    s = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


#: Lo que descarta ANTES de mirar si hay comida. Va primero porque estos textos tambien
#: nombran comidas de refilon («con el desayuno, entrenes o no» no entra aqui; «30 minutos
#: antes de empezar a entrenar» si), y porque el intra y el post no llevan nada debajo.
_FUERA_DE_LAS_COMIDAS = (
    "durante el entren",        # el intra: 111 lineas en produccion
    "despues de entrenar",      # el post: 98 lineas
    "despues del ejercicio",    # una crema, ni siquiera se come
    "antes de entrenar",
    "antes de empezar",
)

#: Y estas si son comidas. «Al despertar» y «antes de acostarte» quedan fuera a proposito: son
#: momentos del dia, no comidas del reparto, y colocarlos en la primera o en la ultima seria
#: ponerle a Jesus una palabra que el no ha escrito.
_ES_DESAYUNO = re.compile(r"\bdesayuno\b")
_ES_CENA = re.compile(r"\bcena\b")


def deducir_del_cuando(cuando: str) -> List[str]:
    """Los huecos que dice el texto del `¿Cuando?`, o lista vacia si no dice ninguno."""
    t = _plano(cuando)
    if not t:
        return []
    if any(p in t for p in _FUERA_DE_LAS_COMIDAS):
        return []
    huecos = []
    if _ES_DESAYUNO.search(t):
        huecos.append(PRIMERA)
    if _ES_CENA.search(t):
        huecos.append(ULTIMA)
    return huecos


def comidas_del_suplemento(item: dict, ficha: Optional[dict] = None) -> List[str]:
    """Donde sale este suplemento: lista de huecos («primera», «ultima», «C1»...).

    `item` es la linea del protocolo del cliente y `ficha` la del catalogo de la que salio
    (por `catalog_id`), que es donde el coach lo elige UNA vez para todos. La linea del
    cliente puede pisarlo, para el caso de que a uno concreto le toque en otra comida.
    """
    for fuente in (item or {}, ficha or {}):
        elegido = (fuente.get("comida") or "").strip()
        if elegido == NINGUNA:
            return []
        if elegido in COMIDAS_FIJAS or elegido in (PRIMERA, ULTIMA):
            return [elegido]
    # Sin elegir en ningun sitio: manda el texto. El del cliente primero, porque el coach
    # puede haberle cambiado el «¿Cuando?» a el en particular.
    return (deducir_del_cuando((item or {}).get("cuando"))
            or deducir_del_cuando((ficha or {}).get("cuando")))
