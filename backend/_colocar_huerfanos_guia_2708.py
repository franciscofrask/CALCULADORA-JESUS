# -*- coding: utf-8 -*-
"""LOS DOS SUPLEMENTOS QUE SE QUEDABAN EN «EL RESTO DE LA GUIA» (punto 187 del 27-08).

    «Es una categoria que no dice que tiene dentro, y no deberia existir: todos los
     suplementos tienen que estar en alguna de las otras siete. Si hay alguno que no encaja
     en ninguna, el problema es que falta una categoria -- no que haga falta un cajon de
     sastre.»

El cajon se quita de la pantalla, asi que lo que hubiera dentro DESAPARECERIA de la guia si
no se recoloca antes. Contado contra produccion: de las 28 fichas, solo 2 estaban sin seccion.

    Citrulina malato     -> rendimiento
        Es un preentreno. La categoria dice «para mejorar la calidad de los entrenamientos».

    Crema RELIEF EFFECT  -> descanso
        Es una crema para la zona dolorida despues de entrenar («¿Cuando? Despues del
        ejercicio, en la zona que hayas entrenado o que sientas dolorida»). Esa categoria
        dice, literal, «los que mejoran la calidad de tu sueno y TU RECUPERACION».
        Es la unica discutible de las dos: si Jesus la quiere en Salud, se cambia aqui.

IDEMPOTENTE: solo toca las fichas que sigan sin seccion. Correrlo dos veces no hace nada.

    python _colocar_huerfanos_guia_2708.py            (mira y no toca)
    python _colocar_huerfanos_guia_2708.py --escribir (lo hace, con copia antes)
"""
import asyncio
import io
import json
import os
import sys
from datetime import datetime, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

#: A donde va cada uno, por nombre. Se busca por nombre exacto y sin distinguir mayusculas.
DESTINOS = {
    "citrulina malato": "rendimiento",
    "crema relief effect": "descanso",
}


async def main(escribir: bool):
    cliente = AsyncIOMotorClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=20000)
    db = cliente[os.environ["DB_NAME"]]
    from core.guia_suplementacion import SECCIONES

    claves = {s["clave"] for s in SECCIONES}
    fichas = await db.guia_suplementos.find({}, {"_id": 0}).to_list(500)
    huerfanas = [f for f in fichas
                 if not [c for c in (f.get("secciones") or []) if c in claves]]

    print(f"fichas de la guia: {len(fichas)}")
    print(f"sin seccion:       {len(huerfanas)}")
    if not huerfanas:
        print("\nNo queda ninguna huerfana: el cajon se puede quitar sin perder nada.")
        return

    plan = []
    for f in huerfanas:
        destino = DESTINOS.get((f.get("nombre") or "").strip().lower())
        plan.append((f, destino))
        print(f"   - {f.get('nombre')!r}  ->  {destino or 'SIN DESTINO DECIDIDO'}")

    sin_destino = [f for f, d in plan if not d]
    if sin_destino:
        print("\nHay fichas sin destino: NO se escribe nada hasta decidirlas.")
        print("Se anaden a DESTINOS en este mismo fichero y se vuelve a correr.")
        return

    if not escribir:
        print("\n(en seco: nada tocado. Con --escribir se hace)")
        return

    copia = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         f"_backup_guia_huerfanas_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.json")
    with io.open(copia, "w", encoding="utf-8") as fh:
        json.dump([f for f, _ in plan], fh, ensure_ascii=False, indent=1, default=str)
    print(f"\ncopia de seguridad -> {copia}")

    for f, destino in plan:
        secciones = list(f.get("secciones") or []) + [destino]
        await db.guia_suplementos.update_one({"id": f.get("id")},
                                             {"$set": {"secciones": secciones}})
        print(f"   {f.get('nombre')} -> {secciones}")

    quedan = [f for f in await db.guia_suplementos.find({}, {"_id": 0}).to_list(500)
              if not [c for c in (f.get("secciones") or []) if c in claves]]
    print(f"\nhuerfanas que quedan: {len(quedan)}")


asyncio.run(main("--escribir" in sys.argv))
