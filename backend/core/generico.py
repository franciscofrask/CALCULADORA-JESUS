# -*- coding: utf-8 -*-
"""Si un alimento es GENERICO o es DE MARCA. Una sola definicion, la misma que el front.

El catalogo no guarda el dato: `db.foods` tiene {nombre, categorias, racion, macros, unidades,
minimo, url, imagen, codigoBarras} y ninguno de `marca`, `es_generico` o `sin_web`
(comprobado en produccion el 29-08-2026). Se deduce, y se deducia solo de la URL.

Francisco, 29-08-2026: «el filtro de generico no esta funcionando bien, se le escapan
alimentos con marca, no pasa en todas las categorias». En produccion hay SEIS alimentos de
marca sin enlace, y con «sin enlace = generico» se colaban todos:

    Chicharron iberico (7 Hermanos)          Batido proteico Smart Protein... (Nutrisport)
    Levadura nutricional (Sol Natural)       Cafe con leche sin azucares... (Hacendado)
    Barrita proteica apple pie (Nutrisport)  Copos de avena integral sin gluten (Esgir)

Se miran las dos cosas: el enlace y el parentesis del nombre (el criterio que confirmo
Francisco el 08-07: 2.736 de 3.211 lo llevan). El parentesis solo no basta porque a veces es
una ACLARACION. Se listaron los 18 que hay entre los 475 sin enlace y salen 12 aclaraciones
-- tres patrones -- y 6 marcas; de ahi la lista de abajo.

Lo que NO cubre: una marca sin parentesis y sin enlace (Aquarius, Gatorade, Monster son asi,
aunque hoy los tres tienen enlace). Para eso hace falta un campo en el catalogo.

El gemelo en el front es `frontend/src/lib/generico.js`: si se toca uno, se toca el otro.
"""
import re

# Parentesis que aclaran el alimento en vez de nombrar una marca. Salen del catalogo real.
ACLARACIONES = re.compile(
    r"corte magro|corte graso|m[áa]s del|menos del|\d\s*%|c[áa]scara|al natural|en conserva|"
    r"congelad|cocinad|cocid|crud|desgrasad|sin az[úu]car|sin sal|light|enter[oa]|peque[nñ]|"
    r"grande|mediano|por gramos|macros orientativos|aprox",
    re.I,
)

_PARENTESIS = re.compile(r"\(([^)]+)\)")


def marca_del_nombre(nombre):
    """El texto del parentesis si parece una MARCA; None si es aclaracion o no hay."""
    m = _PARENTESIS.search(nombre or "")
    if not m:
        return None
    dentro = m.group(1).strip()
    return None if ACLARACIONES.search(dentro) else dentro


def es_de_marca(food):
    """De marca: tiene enlace a la web del super, o lleva la marca en el nombre."""
    food = food or {}
    return bool(food.get("url")) or bool(marca_del_nombre(food.get("nombre")))


def es_generico(food):
    """Generico: ni enlace ni marca en el nombre."""
    return not es_de_marca(food)
