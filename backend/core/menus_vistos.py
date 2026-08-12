"""Qué menús del recetario se le han propuesto ya a cada cliente.

El sugeridor da tres opciones con PROTEÍNAS DIFERENTES, o sea un hueco por familia. En
comida hay 22 menús de pollo peleando por ese hueco, y lo gana siempre el mismo: el orden
es por error de macros y no cambia. Medido en producción, 10 de esos 22 no salían nunca.

Con esto, dentro de un empate se prefiere el que el cliente NO ha visto. **Solo dentro del
empate** (decisión de Francisco, 12-08-2026): un menú que cuadra peor no adelanta a uno que
cuadra mejor, así que la variedad no cuesta ni un gramo de precisión.

Se guarda en el propio perfil (`client_profiles.menus_vistos`), por momento:

    {"comida": ["ME5A021C1", ...], "desayuno": [...]}

Cuando ya se le han enseñado todos los de un momento, esa lista se vacía y vuelve a empezar:
así nunca se queda sin opciones, y la rueda da la vuelta en vez de pararse.
"""
from typing import Dict, List, Optional, Set

# Un tope por si algún día hay miles de plantillas: la lista vive en el perfil y no debe
# crecer sin freno. Con 159 plantillas no se llega ni de lejos.
TOPE_POR_MOMENTO = 400


def _mapa(perfil: Optional[dict]) -> Dict[str, List[str]]:
    m = (perfil or {}).get("menus_vistos")
    return m if isinstance(m, dict) else {}


def vistos_de(perfil: Optional[dict], momento: Optional[str]) -> Set[str]:
    """Los ids que ya se le han propuesto en ese momento del día."""
    return set(_mapa(perfil).get(momento or "", []) or [])


async def anotar(db, client_id: Optional[str], momento: Optional[str],
                 ids: List[str], total_del_momento: Optional[int] = None) -> None:
    """Apunta los ids propuestos. Si ya los ha visto todos, se vacía y vuelve a empezar.

    `total_del_momento` es cuántas plantillas hay en ese momento; sirve para saber cuándo
    dio la vuelta. Sin ese dato no se vacía nunca, que es el lado seguro: como mucho, deja
    de haber variedad nueva.
    """
    ids = [i for i in (ids or []) if i]
    if not client_id or not momento or not ids:
        return
    perfil = await db.client_profiles.find_one(
        {"id": client_id}, {"_id": 0, "menus_vistos": 1})
    if perfil is None:
        return
    mapa = _mapa(perfil)
    lista = list(mapa.get(momento) or [])
    for i in ids:
        if i not in lista:
            lista.append(i)
    # La vuelta completa: se queda con lo de ESTA tanda para no repetirlos de inmediato.
    if total_del_momento and len(lista) >= total_del_momento:
        lista = list(ids)
    mapa[momento] = lista[-TOPE_POR_MOMENTO:]
    await db.client_profiles.update_one({"id": client_id}, {"$set": {"menus_vistos": mapa}})
