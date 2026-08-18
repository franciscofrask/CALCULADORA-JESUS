"""Pone el campo `macros_training` del perfil al día con la fila VIGENTE del histórico.

Por qué (17-08-2026). `client_profiles.macros_training` es un espejo: lo escriben el ajuste
del coach, la calculadora del cliente y la sincronización de Calma. Lo que de verdad usa el
reparto del día -- y por tanto lo que el cliente tiene delante en Nutrición, en Inicio y en
el asistente -- es la fila vigente de `macro_history` por `effective_date`.

Cuando alguien escribe uno sin el otro, la ficha del entrenador enseña una cosa y el cliente
come otra. Medido en producción: 6 de 175 activos, cuatro con la última fila puesta «por
migracion» y dos de ese mismo día. Cliente Demo: la ficha decía 220 g de proteína y el
cliente comía 170.

Manda el HISTÓRICO, no el campo: el histórico está fechado y es lo que se aplicó de verdad.

Uso:
    python _cuadrar_macros_perfil.py            # en seco: dice qué tocaría y no toca nada
    python _cuadrar_macros_perfil.py --hazlo    # lo escribe

Contra producción hace falta el túnel (ver _internos_proceso/tocar_datos_de_produccion.md):
    MONGO_URL="mongodb://localhost:27018" DB_NAME=jg12_prod python _cuadrar_macros_perfil.py
"""
import asyncio
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import db                       # noqa: E402
from macros_por_fecha import ultima_vigente        # noqa: E402


def _p(m):
    return (m or {}).get("protein") if (m or {}).get("protein") is not None else (m or {}).get("proteinas")


def _completo(m):
    """El bloque con las dos formas de nombrar los macros, como lo guarda el resto de la app."""
    if not m:
        return None
    fuera = dict(m)
    for es, en in (("proteinas", "protein"), ("hidratos", "carbs"), ("grasas", "fat")):
        if fuera.get(en) is not None:
            fuera[es] = fuera[en]
        elif fuera.get(es) is not None:
            fuera[en] = fuera[es]
    return fuera


async def main():
    hazlo = "--hazlo" in sys.argv
    hoy = date.today().isoformat()

    equipo = set(await db.users.distinct("id", {"role": {"$in": ["admin", "trainer"]}}))
    tocar = []

    async for perfil in db.client_profiles.find({"status": "activo"}, {"_id": 0}):
        if perfil.get("user_id") in equipo:
            continue
        campo = perfil.get("macros_training") or {}
        if _p(campo) is None:
            continue
        vig = await ultima_vigente(db, perfil["id"], hoy)
        if not vig:
            continue
        # SIN FECHA EFECTIVA NO MANDA. De una fila sin `effective_date` no se sabe cuándo se
        # aplicó, y aquí se decide con qué come alguien: antes de pisarle el campo del perfil
        # con un dato sin fecha, se deja como está y se mira a mano.
        if not str(vig.get("effective_date") or "").strip():
            continue
        entreno = vig.get("training") or vig.get("new_training")
        if _p(entreno) is None:
            continue
        if abs(float(_p(campo)) - float(_p(entreno))) < 1:
            continue

        u = await db.users.find_one({"id": perfil["user_id"]}, {"_id": 0, "name": 1}) or {}
        tocar.append({
            "id": perfil["id"], "nombre": u.get("name"),
            "de": _p(campo), "a": _p(entreno), "desde": vig.get("effective_date"),
            "quien": vig.get("changed_by"),
            "set": {
                "macros_training": _completo(entreno),
                "macros_rest": _completo(vig.get("rest") or vig.get("new_rest")) or perfil.get("macros_rest"),
                "macros_periworkout": _completo(vig.get("peri")) or perfil.get("macros_periworkout"),
            },
        })

    print(f"perfiles cuyo campo no cuadra con lo que comen hoy: {len(tocar)}\n")
    for t in tocar:
        print(f"   {str(t['nombre'])[:26]:26s} {t['de']} -> {t['a']} g de proteína "
              f"(vigente desde {t['desde']}, lo puso {t['quien']})")

    if not tocar:
        return
    if not hazlo:
        print("\n(en seco: no se ha tocado nada. Repite con --hazlo para escribirlo)")
        return

    for t in tocar:
        await db.client_profiles.update_one({"id": t["id"]},
                                            {"$set": {k: v for k, v in t["set"].items() if v}})
    print(f"\nactualizados: {len(tocar)}")


asyncio.run(main())
