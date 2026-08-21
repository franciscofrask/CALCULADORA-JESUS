# -*- coding: utf-8 -*-
"""Sanea `supplement_catalog`: apaga la basura y los duplicados de la guía (tarea 2.2, 21-08).

QUÉ PASÓ. `_completar_catalogo_admin_suplementos.py` volcó las 106 fichas de
`db.supplements` al catálogo del admin con `categoria='guia'`, casando SOLO por id
('guia:<id>'), nunca por título. Resultado, medido en producción el 21-08: todo suplemento
que ya existía entre las semillas sale DOS veces en el selector (su categoría + «Guía»), y
fichas marcadas «NO USAR» u «obsoleto» en el propio título quedaron con activo=True, es
decir, elegibles para pautárselas a un cliente.

QUÉ HACE ESTE SCRIPT (borrado lógico, aquí no se borra nada):
  a) activo=False a toda ficha cuyo TÍTULO contenga «obsoleto» o «NO USAR»,
     sin distinguir mayúsculas ni tildes.
  b) Desduplica por título normalizado (minúsculas, sin tildes, espacios colapsados):
     si una ficha de categoría "guia" repite el título de una semilla de otra categoría,
     la de "guia" pasa a activo=False. La semilla no se toca.

Antes de escribir deja un backup JSON de los documentos que va a tocar, tal y como
estaban, en _backup_catalogo_suplementos_<fecha>.json.

Uso:
    venv/Scripts/python.exe _sanear_catalogo_suplementos.py              # dev (.env), solo mira
    venv/Scripts/python.exe _sanear_catalogo_suplementos.py --escribir   # dev, lo deja hecho

Contra producción, por el túnel (LO LANZA FRANCISCO, no un agente):
    MONGO_URL="mongodb://localhost:27018" DB_NAME=jg12_prod PYTHONIOENCODING=utf-8 \
      venv/Scripts/python.exe _sanear_catalogo_suplementos.py --escribir
"""
import asyncio
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone

BASURA = ("obsoleto", "no usar")


def titulo_normalizado(titulo) -> str:
    """Minúsculas, sin tildes y con los espacios colapsados: «  Omega-3  » y «OMEGA-3»
    son el mismo suplemento. Es la llave del desduplicado y de la idempotencia del
    importador; función pura para poder probarla sola."""
    plano = unicodedata.normalize("NFD", str(titulo or ""))
    sin_tildes = "".join(c for c in plano if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sin_tildes).strip().lower()


def es_basura(titulo) -> bool:
    """«Suplemento obsoleto», «NIACINA FLUSH FREE 3 tomas - NO USAR»... fichas que el
    propio título dice que no se pauten."""
    t = titulo_normalizado(titulo)
    return any(marca in t for marca in BASURA)


def _cfg():
    if os.environ.get("MONGO_URL"):
        return os.environ["MONGO_URL"], os.environ.get("DB_NAME", "jg12_prod")
    from dotenv import dotenv_values
    cfg = dotenv_values(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    return cfg["MONGO_URL"], cfg["DB_NAME"]


async def main():
    from motor.motor_asyncio import AsyncIOMotorClient

    escribir = "--escribir" in sys.argv
    url, nombre = _cfg()
    # La cadena de conexion, no solo el nombre de la base: dev y prod se llaman parecido.
    print(f"CONEXION: {url[:32]}...  base: {nombre}")
    print("MODO:", "ESCRIBE" if escribir else "ENSAYO, no se toca nada")
    db = AsyncIOMotorClient(url)[nombre]

    fichas = await db.supplement_catalog.find({}, {"_id": 0}).to_list(1000)
    activas = [f for f in fichas if f.get("activo") is not False]

    # (a) La basura, por su propio título.
    apagar_basura = [f for f in activas if es_basura(f.get("titulo"))]

    # (b) Los duplicados: la de "guia" se apaga si repite título de una semilla.
    titulos_semilla = {titulo_normalizado(f.get("titulo"))
                       for f in fichas if f.get("categoria") != "guia"}
    apagar_duplicadas = [
        f for f in activas
        if f.get("categoria") == "guia"
        and titulo_normalizado(f.get("titulo")) in titulos_semilla
        and not es_basura(f.get("titulo"))  # esas ya caen por (a), que no salgan dos veces
    ]

    print(f"\nfichas en el catálogo: {len(fichas)} ({len(activas)} activas)")
    print(f"  a apagar por «obsoleto»/«NO USAR»: {len(apagar_basura)}")
    for f in apagar_basura:
        print(f"    [{f.get('categoria')}] {str(f.get('titulo'))[:70]}")
    print(f"  duplicados de \"guia\" a apagar:     {len(apagar_duplicadas)}")
    for f in apagar_duplicadas:
        print(f"    {str(f.get('titulo'))[:70]}")

    a_tocar = apagar_basura + apagar_duplicadas
    if not a_tocar:
        print("\nNada que sanear.")
        return
    if not escribir:
        print("\nNo se ha escrito nada. Para hacerlo: --escribir")
        return

    # El backup de lo que se toca, tal y como estaba, antes de tocar nada.
    sello = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        f"_backup_catalogo_suplementos_{sello}.json")
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(a_tocar, fh, ensure_ascii=False, indent=2)
    print(f"\nbackup: {ruta}")

    ahora = datetime.now(timezone.utc).isoformat()
    n = 0
    for f, motivo in ([(x, "titulo obsoleto/NO USAR") for x in apagar_basura]
                      + [(x, "duplicado de una semilla") for x in apagar_duplicadas]):
        r = await db.supplement_catalog.update_one(
            {"id": f["id"]},
            # Deja rastro de por qué se apagó, que dentro de un mes nadie se acuerda.
            {"$set": {"activo": False, "desactivado_motivo": motivo, "desactivado_at": ahora}})
        n += r.modified_count
    print(f"fichas apagadas: {n}")


if __name__ == "__main__":
    asyncio.run(main())
