"""
Los menús de la gente, en el panel del equipo (Francisco, 19-08).

`db.meal_library` son las 266.000 comidas cosechadas de las dietas reales de los clientes:
es lo que el cliente ve en «Elige tu menú» junto a las recetas del recetario. En el panel
solo se veían las recetas (`menu_templates`), así que la mitad de lo que se le propone al
cliente no lo podía mirar nadie -- ni corregir un menú con una cantidad absurda, ni quitar
uno que no debería proponerse.

Aquí se listan con buscador y paginación (son demasiados para traerlos de golpe), se
editan y se borran. Al editar se recalculan los macros desde los alimentos, con las dos
varas que usa la app: la del método (`macros`, que es la que decide si un menú cuadra) y
la de la etiqueta (`macros_reales`, la que se enseña en «Reales»).
"""
import re
import unicodedata
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends

from core.database import db
from core.security import get_admin_user

router = APIRouter(prefix="/admin/biblioteca-menus", tags=["biblioteca-menus"])

# Cuántos caben en una página. Con 266.000 documentos, traerlos todos tumba la pantalla.
POR_PAGINA = 40

# BUSCAR SIN PONER LAS TILDES. Nadie escribe «salmón» con tilde en un buscador, y el
# catálogo sí las lleva: buscando «salmon» salían cero resultados aunque hubiera cientos de
# menús con salmón. Mongo no aplica la intercalación del idioma a las expresiones
# regulares, así que la tolerancia se construye en el propio patrón.
_LETRAS = {"a": "[aáàäâ]", "e": "[eéèëê]", "i": "[iíìïî]", "o": "[oóòöô]",
           "u": "[uúùüû]", "n": "[nñ]", "c": "[cç]"}


def _como_lo_escriba(termino: str) -> str:
    """El término convertido en un patrón que encuentra la palabra con y sin tildes."""
    plano = "".join(c for c in unicodedata.normalize("NFD", termino.lower())
                    if unicodedata.category(c) != "Mn")
    return "".join(_LETRAS.get(c, re.escape(c)) for c in plano)


def _macros_de(alimentos: list, foods: dict) -> tuple:
    """Los macros de un menú por sus dos varas: la del método y la de la etiqueta.

    La del método (`get_effective_macros_per_100g`) es la que usa el motor para decidir si
    un menú cuadra con el objetivo; la de la etiqueta es la suma cruda del alimento. Las
    dos se guardan porque la pantalla del cliente deja cambiar de una a otra.
    """
    from meal_builder import get_effective_macros_per_100g

    metodo = {"P": 0.0, "H": 0.0, "G": 0.0}
    reales = {"P": 0.0, "H": 0.0, "G": 0.0}
    for a in alimentos:
        food = foods.get(int(a["alimento_id"]))
        if not food:
            continue
        factor = float(a.get("cantidad_g") or 0) / 100.0
        ef = get_effective_macros_per_100g(food)
        metodo["P"] += float(ef.get("P", 0) or 0) * factor
        metodo["H"] += float(ef.get("H", 0) or 0) * factor
        metodo["G"] += float(ef.get("G", 0) or 0) * factor
        reales["P"] += float(food.get("proteinas") or 0) * factor
        reales["H"] += float(food.get("hidratos") or 0) * factor
        reales["G"] += float(food.get("grasas") or 0) * factor
    return ({m: round(v, 1) for m, v in metodo.items()},
            {m: round(v, 1) for m, v in reales.items()})


async def _con_nombres(docs: list) -> list:
    """Pone el nombre de cada alimento en la ficha. Los documentos guardan el id y un
    nombre de cuando se cosecharon; el bueno es el del catálogo de hoy."""
    ids = {int(a["alimento_id"]) for d in docs for a in (d.get("alimentos") or [])
           if a.get("alimento_id") is not None}
    if not ids:
        return docs
    foods = {f["id"]: f async for f in db.foods.find(
        {"id": {"$in": list(ids)}}, {"_id": 0, "id": 1, "nombre": 1})}
    for d in docs:
        for a in (d.get("alimentos") or []):
            food = foods.get(int(a.get("alimento_id") or -1))
            if food:
                a["nombre"] = food.get("nombre") or a.get("nombre")
    return docs


@router.get("")
async def listar(q: str = "", tipo_comida: str = "", origen: str = "",
                 pagina: int = 1, user=Depends(get_admin_user)):
    """Una página de menús de la gente, con su buscador.

    El orden es por cuánta GENTE lo monta, que es lo que hace que un menú se proponga a
    otros: los que más arriba son los que más se están viendo, y son los que compensa
    revisar. `q` busca por el nombre del alimento (no por el del menú: estos no tienen
    nombre, son la lista de lo que lleva).
    """
    filtro = {}
    if tipo_comida.strip():
        filtro["tipo_comida"] = tipo_comida.strip()
    if origen.strip():
        filtro["origen"] = origen.strip()

    termino = q.strip()
    if termino:
        # Se busca el alimento en el catálogo y luego los menús que lo llevan: la
        # colección tiene índice por `alimento_ids`, así que esto va por índice y no
        # recorre los 266.000 documentos.
        patron = _como_lo_escriba(termino)
        ids = [f["id"] async for f in db.foods.find(
            {"nombre": {"$regex": patron, "$options": "i"}}, {"_id": 0, "id": 1}).limit(60)]
        # Y por el título que le haya puesto el equipo, si lo tiene.
        por_titulo = {"nombre": {"$regex": patron, "$options": "i"}}
        filtro["$or"] = [{"alimento_ids": {"$in": ids}}, por_titulo] if ids else [por_titulo]

    total = await db.meal_library.count_documents(filtro)
    pagina = max(1, int(pagina or 1))
    docs = await db.meal_library.find(filtro, {"_id": 0}).sort(
        [("clientes", -1), ("usos", -1), ("id", 1)]
    ).skip((pagina - 1) * POR_PAGINA).limit(POR_PAGINA).to_list(POR_PAGINA)

    return {
        "menus": await _con_nombres(docs),
        "total": total,
        "pagina": pagina,
        "paginas": (total + POR_PAGINA - 1) // POR_PAGINA,
        "por_pagina": POR_PAGINA,
    }


@router.get("/momentos")
async def momentos(user=Depends(get_admin_user)):
    """Los momentos que existen de verdad en la biblioteca («Comida 1», «Peri»...), con
    cuántos hay de cada uno. Se leen de los datos y no de una lista escrita a mano: si
    mañana aparece un momento nuevo, sale solo."""
    filas = await db.meal_library.aggregate([
        {"$group": {"_id": "$tipo_comida", "n": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]).to_list(50)
    return {"momentos": [{"tipo_comida": f["_id"], "n": f["n"]} for f in filas if f["_id"]]}


@router.put("/{menu_id}")
async def editar(menu_id: str, data: dict, user=Depends(get_admin_user)):
    """Cambia los alimentos de un menú (o su momento) y recalcula sus macros.

    Se recalculan aquí y no se aceptan los que mande la pantalla: los macros son lo que
    decide a quién se le propone este menú, y tienen que salir siempre de los alimentos.
    """
    doc = await db.meal_library.find_one({"id": menu_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Ese menú no existe")

    alimentos = data.get("alimentos")
    if alimentos is not None:
        if not isinstance(alimentos, list) or not alimentos:
            raise HTTPException(400, "El menú tiene que llevar al menos un alimento")
        limpios = []
        for i, a in enumerate(alimentos):
            try:
                aid = int(a.get("alimento_id"))
                gramos = float(a.get("cantidad_g") or 0)
            except (TypeError, ValueError):
                raise HTTPException(400, f"El alimento {i + 1} no está bien puesto")
            if gramos <= 0:
                raise HTTPException(400, f"El alimento {i + 1} necesita una cantidad")
            limpios.append({**a, "alimento_id": aid, "cantidad_g": round(gramos, 1)})

        foods = {f["id"]: f async for f in db.foods.find(
            {"id": {"$in": [a["alimento_id"] for a in limpios]}}, {"_id": 0})}
        faltan = [a["alimento_id"] for a in limpios if a["alimento_id"] not in foods]
        if faltan:
            raise HTTPException(400, "Hay un alimento que ya no está en el catálogo")

        for a in limpios:
            a["nombre"] = foods[a["alimento_id"]].get("nombre") or a.get("nombre")
        metodo, reales = _macros_de(limpios, foods)
        doc.update({
            "alimentos": limpios,
            "alimento_ids": [a["alimento_id"] for a in limpios],
            "n_alimentos": len(limpios),
            "macros": metodo,
            "macros_reales": reales,
        })

    # EL TÍTULO (Francisco, 19-08). Estos menús nacen sin nombre: son la lista de lo que
    # llevan. Si el equipo le pone uno, es el que ve el cliente en su tarjeta. Vaciarlo lo
    # devuelve a como estaba.
    if "nombre" in data:
        nombre = (data.get("nombre") or "").strip()
        if nombre:
            doc["nombre"] = nombre
        else:
            doc.pop("nombre", None)
            await db.meal_library.update_one({"id": menu_id}, {"$unset": {"nombre": ""}})

    tipo_comida = (data.get("tipo_comida") or "").strip()
    if tipo_comida:
        doc["tipo_comida"] = tipo_comida
        # `tipo` es lo que separa una comida de un peri, y la busca el motor por índice.
        doc["tipo"] = "peri" if tipo_comida.lower().startswith("peri") else "comida"

    doc["editado_por"] = user.get("email") or user.get("name")
    doc["editado_at"] = datetime.now(timezone.utc).isoformat()
    await db.meal_library.update_one({"id": menu_id}, {"$set": doc})
    return doc


@router.delete("/{menu_id}")
async def borrar(menu_id: str, user=Depends(get_admin_user)):
    """Quita un menú de la biblioteca: deja de proponerse a nadie."""
    r = await db.meal_library.delete_one({"id": menu_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "Ese menú no existe")
    return {"borrado": menu_id}
