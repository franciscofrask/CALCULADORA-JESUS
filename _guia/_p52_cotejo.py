# -*- coding: utf-8 -*-
"""Punto 52: que avisos guardados llevan un texto que el codigo YA NO escribe. SOLO MIRA."""
import asyncio, os, re, sys
from collections import Counter
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", ".env"))

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")

def texto_del_codigo():
    """Todo el codigo del backend en una cadena: si un titulo guardado no aparece por
    ninguna parte, es que hoy nadie lo escribe."""
    trozos = []
    for base, _, ficheros in os.walk(RAIZ):
        if "venv" in base or "__pycache__" in base or "/tests" in base.replace("\\", "/"):
            continue
        for f in ficheros:
            if f.endswith(".py"):
                try:
                    trozos.append(open(os.path.join(base, f), encoding="utf-8").read())
                except Exception:
                    pass
    return "\n".join(trozos)

# Los titulos que llevan un dato dentro: se comparan por su parte fija.
CON_DATO = [
    (re.compile(r"^Llevas \d+ semanas con los mismos macros$"), "Llevas {n} semanas con los mismos macros"),
    (re.compile(r"^Tarea nueva: "), "Tarea nueva: {...}"),
    (re.compile(r" te ha escrito$"), "{quien} te ha escrito"),
    (re.compile(r"^Tu coach ahora es "), "Tu coach ahora es {quien}"),
    (re.compile(r"^Ya puedes rellenar tu reporte "), "Ya puedes rellenar tu reporte {...}"),
    (re.compile(r"^Esta semana toca tu reporte "), "Esta semana toca tu reporte {...}"),
]

async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    codigo = texto_del_codigo()
    print(f"base: {os.environ['DB_NAME']}\n")

    huerfanos = Counter()
    sin_leer = Counter()
    ejemplos = {}
    async for n in db.notifications.find({"caducada": {"$ne": True}}, {"_id": 0}):
        t = (n.get("title") or "").strip()
        if not t:
            continue
        plantilla = next((p for r, p in CON_DATO if r.search(t)), None)
        if plantilla:
            # Los de plantilla se miran aparte, mas abajo.
            continue
        if t not in codigo:
            huerfanos[t] += 1
            if not n.get("read"):
                sin_leer[t] += 1
            ejemplos.setdefault(t, n.get("id"))

    print("== TITULOS QUE EL CODIGO YA NO ESCRIBE ==")
    if not huerfanos:
        print("   ninguno")
    for t, c in huerfanos.most_common():
        print(f"   {c:>3} ({sin_leer.get(t,0)} sin leer)  «{t}»")

    print("\n== LOS DE «Llevas N semanas», con el tope de 12 ==")
    pasados = []
    async for n in db.notifications.find(
            {"title": {"$regex": "^Llevas [0-9]+ semanas"}, "caducada": {"$ne": True}},
            {"_id": 0, "id": 1, "title": 1, "read": 1, "created_at": 1, "user_id": 1}):
        m = re.search(r"Llevas (\d+) semanas", n["title"])
        if m and int(m.group(1)) > 12:
            pasados.append(n)
    print(f"   por encima del tope: {len(pasados)}")
    for n in pasados:
        print(f"      {n['title']}   {'leido' if n.get('read') else 'SIN LEER'}   {str(n.get('created_at'))[:10]}   {n['id']}")

asyncio.run(main())
