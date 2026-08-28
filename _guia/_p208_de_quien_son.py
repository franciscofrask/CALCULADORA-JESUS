# -*- coding: utf-8 -*-
"""Punto 208: ¿a algun CLIENTE se le ofrecen dietas con el nombre de OTRA persona?

Las favoritas van por `user_id`, asi que nadie ve las de nadie. Lo que hay que mirar es
otra cosa: si dentro de la cuenta de un cliente hay favoritas bautizadas con el nombre de
alguien que no es el.
"""
import asyncio, os, sys, re, unicodedata
from collections import Counter
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", ".env"))


def plano(t):
    t = unicodedata.normalize("NFKD", str(t or ""))
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def trozos(t):
    return {p for p in re.split(r"[^a-z]+", plano(t)) if len(p) >= 4}


async def main():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]

    usuarios = {}
    async for u in db.users.find({}, {"id": 1, "email": 1, "name": 1, "role": 1}):
        usuarios[u["id"]] = u
    perfiles = {}
    async for c in db.client_profiles.find({}, {"user_id": 1, "nombre": 1, "apellidos": 1}):
        perfiles[c.get("user_id")] = c

    # El diccionario de nombres de persona: solo nombres de pila de la casa.
    nombres_casa = set()
    for u in usuarios.values():
        nombres_casa |= trozos(u.get("name"))
    for c in perfiles.values():
        nombres_casa |= trozos(f"{c.get('nombre')} {c.get('apellidos')}")
    # Palabras que NO son nombres aunque lo parezcan
    NO_SON = {"dieta", "descanso", "entreno", "entrene", "prueba", "reto", "semanas",
              "comida", "unica", "favorita", "nueva", "formacion", "espana", "dinamarca",
              "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
              "septiembre", "octubre", "noviembre", "diciembre", "lunes", "martes",
              "miercoles", "jueves", "viernes", "sabado", "domingo", "sin", "reparto",
              "todo", "dias", "plan"}
    nombres_casa -= NO_SON

    por_usuario = {}
    async for f in db.diet_favorites.find({}, {"_id": 0, "user_id": 1, "name": 1, "calma_migrated": 1}):
        por_usuario.setdefault(f.get("user_id"), []).append(f)

    print(f"cuentas con favoritas: {len(por_usuario)}   favoritas: {sum(len(v) for v in por_usuario.values())}")
    reparto = Counter()
    for v in por_usuario.values():
        n = len(v)
        reparto["1" if n == 1 else "2-5" if n <= 5 else "6-20" if n <= 20 else "21-50" if n <= 50 else "51+"] += 1
    print(f"cuantas tiene cada uno: {dict(reparto)}")

    print("\n=== cuentas donde alguna favorita lleva el nombre de OTRA persona ===")
    culpables = []
    for uid, favs in por_usuario.items():
        u = usuarios.get(uid) or {}
        p = perfiles.get(uid) or {}
        suyo = trozos(u.get("name")) | trozos(f"{p.get('nombre')} {p.get('apellidos')}")
        suyo |= trozos((u.get("email") or "").split("@")[0])
        ajenas = []
        for f in favs:
            otros = (trozos(f.get("name")) & nombres_casa) - suyo
            if otros:
                ajenas.append((f.get("name"), sorted(otros)))
        if ajenas:
            culpables.append((len(ajenas), len(favs), u, ajenas))

    culpables.sort(reverse=True, key=lambda x: x[0])
    for n, tot, u, ajenas in culpables:
        rol = u.get("role") or "?"
        print(f"\n  {n} de {tot}   {u.get('email')}   ({u.get('name')})   rol={rol}")
        for nombre, otros in ajenas[:6]:
            print(f"       «{nombre}»  -> {', '.join(otros)}")
        if len(ajenas) > 6:
            print(f"       ... y {len(ajenas) - 6} mas")
    if not culpables:
        print("  ninguna")

    print(f"\ncuentas afectadas: {len(culpables)} de {len(por_usuario)}")
    cli.close()

asyncio.run(main())
