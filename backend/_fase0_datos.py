# -*- coding: utf-8 -*-
"""Fase 0 del doc del 24-08: los tres arreglos de DATOS en produccion.

  10 · retirar los avisos vivos con los textos viejos
  11 · que manana haya frase del dia
  12 · sacar del recuento lo que no es un cliente

Por defecto MIRA Y NO TOCA. Para escribir hay que pasar --escribir, y antes hace copia de
todo lo que va a cambiar en un fichero con fecha, que es la regla de la casa.

    backend/venv/Scripts/python.exe _fase0_datos.py            # solo mirar
    backend/venv/Scripts/python.exe _fase0_datos.py --escribir
"""
import asyncio
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:27018")
os.environ.setdefault("DB_NAME", "jg12_prod")

ESCRIBIR = "--escribir" in sys.argv

# Las dos marcas de agua de los textos viejos. La primera es el numero sin topar (hoy el
# motor lo corta en 12 semanas); la segunda, el asistente hablando en primera persona,
# que se paso a plural el 23-08 pero solo para los avisos que naciesen despues.
VIEJO_SEMANAS = "semanas con los mismos macros"
VIEJO_YO = ("puedo mirarlo", "puedo verlo", "te lo miro", "te lo ajusto", "yo te")

# Las cinco segundas cuentas de los entrenadores (punto 37 del doc) mas la cuenta basura.
# Las de trabajo ya estan fuera por su rol; estas cuentan como clientes y no lo son.
NO_SON_CLIENTES = [
    "carlosgarcia43@hotmail.es",          # Carlos Garcia Bravo, entrenador
    "info.rubiowellnesscoach@gmail.com",  # Gonzalo Rubio, admin
    "jmatamoros.digital@gmail.com",       # Jordi Matamoros, entrenador
    "gallegoteam.montse@gmail.com",       # Montse, correo de la casa
    "user@user.com",                      # registro de pruebas de mayo, plan gold, sin marcar
]
# xiquitin83@hotmail.com (Jose luis Garcia Banuls) NO entra: comparte iniciales y ano con el
# entrenador jlgb83 pero no comparte correo, y el doc solo dice "Jose Luis". Que lo confirme
# Jenny antes de tocarlo.


async def main():
    from core.database import db

    print("base: %s   modo: %s\n" % (db.name, "ESCRIBIR" if ESCRIBIR else "solo mirar"))
    copia = {"cuando": datetime.now(timezone.utc).isoformat(), "base": db.name}

    # ------------------------------------------------------------------ 10 · avisos viejos
    print("=" * 78)
    print("10 · LOS AVISOS VIVOS CON LOS TEXTOS VIEJOS")
    print("=" * 78)
    from routes.notifications import SOLO_DEL_CLIENTE

    vivos = await db.notifications.find(
        {"caducada": {"$ne": True}, **SOLO_DEL_CLIENTE}, {"_id": 0}).to_list(None)
    print("avisos vivos de cliente: %d" % len(vivos))

    def texto_de(a):
        return " ".join(str(a.get(k) or "") for k in ("title", "body", "titulo", "cuerpo"))

    # NO SE RETIRA TODA LA FAMILIA, SOLO LO QUE ESTA MAL. De los que hablan de semanas, la
    # mayoria dicen un numero razonable y en plural: esos son correctos y el cliente puede
    # querer actuar sobre ellos. Se retiran dos cosas y nada mas:
    #   - el numero sin topar: el motor lo corta hoy en 12 semanas (avisos_cliente.py:374),
    #     asi que un «133 semanas» es de antes del tope y es lo que Jesus fotografio;
    #   - la primera persona: el asistente decia «puedo mirarlo» y se paso a plural el 23-08,
    #     pero eso solo afecta a los avisos que nacieran despues.
    import re

    de_la_familia, a_caducar, correctos = [], [], []
    for a in vivos:
        t = texto_de(a)
        if VIEJO_SEMANAS not in t and not any(m in t.lower() for m in VIEJO_YO):
            continue
        de_la_familia.append(a)
        m = re.search(r"Llevas\s+(\d+)\s+semanas", t)
        semanas = int(m.group(1)) if m else None
        motivos = []
        if semanas is not None and semanas > 12:
            motivos.append("numero sin topar (%d)" % semanas)
        if any(x in t.lower() for x in VIEJO_YO):
            motivos.append("primera persona")
        (a_caducar if motivos else correctos).append((a, motivos, semanas))

    print("\n  de la familia «semanas con los mismos macros»: %d" % len(de_la_familia))
    print("\n  SE RETIRAN (%d):" % len(a_caducar))
    for a, motivos, _ in a_caducar:
        print("     %-10s %-9s %-28s %s" % (
            str(a.get("created_at"))[:10], "leido" if a.get("read") else "SIN LEER",
            ", ".join(motivos), texto_de(a).strip()[:70]))
    print("\n  SE QUEDAN, estan bien (%d):" % len(correctos))
    for a, _, semanas in correctos:
        print("     %-10s %-9s %s" % (str(a.get("created_at"))[:10],
                                      "leido" if a.get("read") else "SIN LEER",
                                      texto_de(a).strip()[:78]))

    a_caducar = [a for a, _, _ in a_caducar]
    copia["notifications"] = a_caducar

    # ------------------------------------------------------------------ 11 · la frase
    print("\n" + "=" * 78)
    print("11 · LA FRASE DEL DIA")
    print("=" * 78)
    ajustes = await db.app_settings.find_one({"id": "app"}, {"_id": 0})
    frase = (ajustes or {}).get("frase_del_dia") or {}
    cola = (ajustes or {}).get("frases_programadas") or []
    print("  la de hoy   : %s  (%s)" % (frase.get("texto"), frase.get("fecha")))
    print("  en la cola  : %d" % len(cola))
    copia["app_settings"] = ajustes

    # ------------------------------------------------------------------ 12 · no son clientes
    print("\n" + "=" * 78)
    print("12 · LO QUE CUENTA COMO CLIENTE Y NO LO ES")
    print("=" * 78)
    fuera_u, fuera_p = [], []
    for correo in NO_SON_CLIENTES:
        u = await db.users.find_one({"email": correo}, {"_id": 0})
        if not u:
            print("  %-38s NO EXISTE" % correo)
            continue
        p = await db.client_profiles.find_one({"user_id": u["id"]}, {"_id": 0})
        print("  %-38s rol=%-8s es_prueba=%-5s plan=%-14s nombre=%s" % (
            correo, u.get("role"), u.get("es_prueba"), (p or {}).get("plan"), str(u.get("name"))[:24]))
        if not u.get("es_prueba"):
            fuera_u.append(u)
        if p and not p.get("es_prueba"):
            fuera_p.append(p)
    copia["users"] = fuera_u
    copia["client_profiles"] = fuera_p

    print("\n  se marcarian es_prueba: %d usuarios y %d perfiles" % (len(fuera_u), len(fuera_p)))

    # ------------------------------------------------------------------ resumen y escritura
    print("\n" + "=" * 78)
    print("RESUMEN: %d avisos a caducar, %d usuarios y %d perfiles a marcar" % (
        len(a_caducar), len(fuera_u), len(fuera_p)))
    print("=" * 78)

    if not ESCRIBIR:
        print("\nNo se ha tocado nada. Con --escribir se hace, y antes la copia.")
        return

    sello = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    ruta = "_backup_fase0_%s.json" % sello
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(copia, f, ensure_ascii=False, indent=1, default=str)
    print("\ncopia previa en backend/%s" % ruta)

    if a_caducar:
        r = await db.notifications.update_many(
            {"id": {"$in": [a["id"] for a in a_caducar if a.get("id")]}},
            {"$set": {"caducada": True,
                      "caducada_por": "textos viejos, fase 0 del doc 24-08"}})
        print("  avisos caducados: %d" % r.modified_count)

    if fuera_u:
        r = await db.users.update_many(
            {"id": {"$in": [u["id"] for u in fuera_u]}}, {"$set": {"es_prueba": True}})
        print("  usuarios marcados: %d" % r.modified_count)
    if fuera_p:
        r = await db.client_profiles.update_many(
            {"id": {"$in": [p["id"] for p in fuera_p]}}, {"$set": {"es_prueba": True}})
        print("  perfiles marcados: %d" % r.modified_count)


if __name__ == "__main__":
    asyncio.run(main())
