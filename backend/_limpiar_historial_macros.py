# -*- coding: utf-8 -*-
"""
Deja UNA fila por (cliente, fecha de vigencia) en `macro_history`. Punto 62 del doc del 07-08.

El upsert de `core/historial_macros.py` cierra la puerta de aqui en adelante; esto limpia lo
que ya se coló. Medido en produccion el 09-08-2026: 3.596 filas, 25 dias con mas de una,
92 filas de mas, y 48 de ellas apuntando a clientes que ya no existen.

Que hace, en este orden:

  1. HUERFANAS. Filas cuyo `client_id` no es ningun cliente. Salieron de los usuarios de
     prueba que se borraron el 09-08: se borro el perfil y el historial se quedo colgando.
     No se pueden enseñar en ninguna ficha porque no hay ficha. Se archivan y se borran.

  2. DUPLICADAS. De cada grupo (cliente, fecha) se queda la ULTIMA por `created_at` -- es
     la correccion, la que el coach dio por buena -- arrastrando el "de donde venia" de la
     primera, que es el estado real anterior. Las demas se copian a
     `macro_history_auditoria` con el motivo y se borran.

Nada se pierde: todo lo que se quita queda en `macro_history_auditoria`.

    python _limpiar_historial_macros.py            # solo dice lo que haria
    python _limpiar_historial_macros.py --hazlo    # lo hace
"""
import asyncio
import sys
from collections import defaultdict
from datetime import datetime, timezone

from core.cambios_macros import marcar_cambios
from core.database import db
from core.historial_macros import COLECCION_AUDITORIA, fecha_de_vigencia

HAZLO = "--hazlo" in sys.argv


def _orden(fila):
    """Para elegir la que se queda: la ultima escrita."""
    return (str(fila.get("created_at") or ""), str(fila.get("id") or ""))


async def _quien(client_id) -> str:
    """El nombre del cliente, para poder leer el informe. El nombre vive en `users`."""
    perfil = await db.client_profiles.find_one({"id": client_id}, {"_id": 0, "user_id": 1, "name": 1})
    if not perfil:
        return "(ya no existe)"
    if perfil.get("name"):
        return str(perfil["name"])
    u = await db.users.find_one({"id": perfil.get("user_id")}, {"_id": 0, "name": 1, "email": 1})
    return str((u or {}).get("name") or (u or {}).get("email") or client_id)


async def _archivar(filas, motivo):
    if not filas:
        return
    ahora = datetime.now(timezone.utc).isoformat()
    copias = []
    for f in filas:
        c = dict(f)
        c.pop("_id", None)
        c["sustituida_at"] = ahora
        c["motivo"] = motivo
        copias.append(c)
    await db[COLECCION_AUDITORIA].insert_many(copias)
    await db.macro_history.delete_many({"_id": {"$in": [f["_id"] for f in filas]}})


async def main():
    print(f"{'HACIENDOLO' if HAZLO else 'ENSAYO (nada se toca)'}\n")
    total = await db.macro_history.count_documents({})
    print(f"filas al empezar: {total}")

    filas = await db.macro_history.find({}).to_list(None)
    clientes = set(await db.client_profiles.distinct("id"))

    # ---------- 1. HUERFANAS ----------
    huerfanas = [f for f in filas if f.get("client_id") not in clientes]
    print(f"\n1) HUERFANAS (client_id que no es ningun cliente): {len(huerfanas)}")
    for cid, n in sorted(
            {c: sum(1 for f in huerfanas if f.get("client_id") == c) for c in
             {f.get("client_id") for f in huerfanas}}.items(), key=lambda kv: -kv[1])[:5]:
        print(f"     {str(cid)[:38]:38} {n} filas")
    if HAZLO:
        await _archivar(huerfanas, "cliente inexistente")

    # ---------- 2. DUPLICADAS ----------
    vivas = [f for f in filas if f.get("client_id") in clientes]
    grupos = defaultdict(list)
    for f in vivas:
        fecha = fecha_de_vigencia(f)
        if fecha:
            grupos[(f["client_id"], fecha)].append(f)

    dups = {k: v for k, v in grupos.items() if len(v) > 1}
    sobran = sum(len(v) - 1 for v in dups.values())
    print(f"\n2) DUPLICADAS: {len(dups)} dias con mas de una fila -> {sobran} filas de mas")

    a_borrar, a_corregir = [], []
    for (cid, fecha), v in sorted(dups.items()):
        v.sort(key=_orden)
        primera, ultima = v[0], v[-1]
        a_borrar.extend(v[:-1])

        # El "de donde venia" real es el de la PRIMERA del dia: los estados intermedios no
        # existieron para nadie mas que para quien estaba tecleando.
        arreglo = {}
        for campo in ("previous_training", "previous_rest", "previous_peri", "previous_periworkout"):
            if campo in primera and primera.get(campo) != ultima.get(campo):
                arreglo[campo] = primera.get(campo)
        if arreglo:
            antes = {"entreno": arreglo.get("previous_training", ultima.get("previous_training")),
                     "perientreno": arreglo.get("previous_peri", ultima.get("previous_peri")),
                     "descanso": arreglo.get("previous_rest", ultima.get("previous_rest"))}
            if any(isinstance(x, dict) for x in antes.values()):
                arreglo["cambios"] = marcar_cambios(antes, {
                    "entreno": ultima.get("training") or ultima.get("new_training"),
                    "perientreno": ultima.get("peri"),
                    "descanso": ultima.get("rest") or ultima.get("new_rest")})
            a_corregir.append((ultima["_id"], arreglo))

        if len(a_borrar) <= 12:
            print(f"     {(await _quien(cid))[:26]:26} {fecha}  {len(v)} filas -> se queda "
                  f"la de {str(ultima.get('created_at'))[11:19]} ({ultima.get('origen') or 'sin origen'})")

    print(f"\n   se borran {len(a_borrar)} filas y se corrige el 'venia de' en {len(a_corregir)}")

    if HAZLO:
        await _archivar(a_borrar, "duplicada del mismo dia")
        for _id, arreglo in a_corregir:
            await db.macro_history.update_one({"_id": _id}, {"$set": arreglo})

        # ---------- 3. EL INDICE ----------
        # Se crea aqui y no solo en el arranque para que el fallo, si lo hay, se vea.
        try:
            await db.macro_history.create_index(
                [("client_id", 1), ("effective_date", 1)], unique=True,
                name="una_por_cliente_y_fecha",
                partialFilterExpression={"client_id": {"$type": "string"},
                                         "effective_date": {"$type": "string"}})
            print("\n3) indice unico (cliente, fecha de vigencia): creado")
        except Exception as e:
            print(f"\n3) indice unico: NO se pudo crear -> {e}")

        quedan = await db.macro_history.count_documents({})
        archivadas = await db[COLECCION_AUDITORIA].count_documents({})
        print(f"\nfilas al terminar: {quedan}  (archivadas en {COLECCION_AUDITORIA}: {archivadas})")

        # Comprobacion: ya no queda ningun (cliente, fecha) repetido.
        repes = await db.macro_history.aggregate([
            {"$match": {"client_id": {"$type": "string"}, "effective_date": {"$type": "string"}}},
            {"$group": {"_id": {"c": "$client_id", "f": "$effective_date"}, "n": {"$sum": 1}}},
            {"$match": {"n": {"$gt": 1}}},
        ]).to_list(None)
        print(f"claves repetidas que quedan: {len(repes)}")


if __name__ == "__main__":
    asyncio.run(main())
