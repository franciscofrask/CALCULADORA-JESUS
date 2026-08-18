# -*- coding: utf-8 -*-
"""Rellena los huecos de la ficha del cliente con lo que Calma sabe de el.

Francisco, 14-08-2026: «actualiza la base de datos de clientes en prod tambien».

QUE SE RELLENA, Y QUE NO
------------------------
Solo lo que esta VACIO en la app. Si el cliente o el entrenador ya pusieron un valor,
manda ese: esto no es una sincronizacion de ida y vuelta, es rellenar huecos.

Medido antes de escribir, sobre 189 perfiles:

    height           lo tenian  10       age              lo tenian  10
    goal             lo tenian  19       activity_level   lo tenian   6

Y OJO CON UNA COSA QUE CASI ME CUESTA UN DESTROZO: los campos `momento_entreno_pref`,
`opcion_peri` y `training_weekdays` de `client_profiles` estan MUERTOS. No los lee nadie,
ni el backend ni el frontend. Lo que la app usa de verdad es `diet_momento_entreno`,
`diet_opcion_peri` y `diet_num_comidas`, y esos ya los tienen 179 de 189. Parecia que
faltaba la configuracion de dieta de 151 clientes y no faltaba de ninguno: era el campo
equivocado. Aqui no se tocan.

LOS MAPEOS, Y POR QUE
---------------------
  objetivo    DEFINICION -> definicion, VOLUMEN -> volumen. `goal` en la app solo admite
              esos dos (`models/user.py:867`). Los 17 de TONIFICAR se quedan FUERA: no es
              ni una cosa ni la otra, y elegir por Jesus cambiaria los macros de esa gente.
  estiloVida  «muy sedentario» -> sedentario y «muy activo» -> activo, que son los valores
              con los que trabaja la app. Se pierde el matiz del «muy», y es a proposito:
              mejor el escalon de al lado que un valor que la calculadora no entiende.
  estatura    Fuera lo que no puede ser una persona. 51 fichas traen «1», que es un metro
              mal tecleado o un campo a medias; entre 120 y 220 cm es lo que se acepta.
  edad        Se calcula de la fecha de nacimiento a dia de hoy. La edad envejece; la
              fecha no, pero el campo de la app es la edad, asi que se guarda calculada.

    python _sync_ficha_cliente.py             ensayo
    python _sync_ficha_cliente.py --escribir  lo hace
"""
import asyncio
import os
import sys
import unicodedata
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROD = "mongodb://127.0.0.1:27018"
BASE = "jg12_prod"
ESCRIBIR = "--escribir" in sys.argv


def _sin_tildes(t):
    return "".join(c for c in unicodedata.normalize("NFD", str(t or "").lower())
                   if unicodedata.category(c) != "Mn").strip()


def objetivo(v):
    t = _sin_tildes(v)
    if "definicion" in t:
        return "definicion"
    if "volumen" in t:
        return "volumen"
    return None            # TONIFICAR y demas: no se inventa


def estilo_de_vida(v):
    t = _sin_tildes(v)
    if not t:
        return None
    if "sedentario" in t:
        return "sedentario"
    if "activo" in t:
        return "activo"
    return None


def estatura(v):
    try:
        n = float(str(v).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None
    if n < 3:              # «1,75» en metros
        n *= 100
    return round(n) if 120 <= n <= 220 else None


def edad(fecha_nac):
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            d = datetime.strptime(str(fecha_nac).strip()[:10], formato)
            break
        except (TypeError, ValueError):
            continue
    else:
        return None
    hoy = datetime.now(timezone.utc)
    años = hoy.year - d.year - ((hoy.month, hoy.day) < (d.month, d.day))
    return años if 14 <= años <= 100 else None


def sexo(v):
    t = _sin_tildes(v)
    return {"m": "hombre", "f": "mujer", "hombre": "hombre", "mujer": "mujer"}.get(t)


async def main():
    from motor.motor_asyncio import AsyncIOMotorClient

    db = AsyncIOMotorClient(PROD, serverSelectionTimeoutMS=20000)[BASE]

    users = {}
    async for u in db.users.find({"deleted_at": None}, {"_id": 0, "id": 1, "email": 1, "phone": 1}):
        if u.get("email"):
            users[u["email"].lower()] = u

    cambios_perfil, cambios_user, descartes = [], [], {}
    def descarta(k):
        descartes[k] = descartes.get(k, 0) + 1

    async for c in db.calma_raw.find({}, {"_id": 0}):
        email = (c.get("email") or "").lower()
        u = users.get(email)
        if not u or not c.get("client_id"):
            continue
        perfil = await db.client_profiles.find_one({"id": c["client_id"]}, {"_id": 0}) or {}
        fi = c.get("formulario_inicial") or {}
        pon = {}

        if not perfil.get("height"):
            h = estatura(fi.get("estatura"))
            if h:
                pon["height"] = h
            elif fi.get("estatura"):
                descarta("estatura imposible")
        if not perfil.get("age"):
            a = edad(fi.get("fechaNacimiento"))
            if a:
                pon["age"] = a
            elif fi.get("fechaNacimiento"):
                descarta("fecha de nacimiento ilegible")
        if not perfil.get("goal"):
            g = objetivo(fi.get("objetivo"))
            if g:
                pon["goal"] = g
            elif fi.get("objetivo"):
                descarta("objetivo sin equivalente (TONIFICAR)")
        if not perfil.get("activity_level"):
            e = estilo_de_vida(fi.get("estiloVida"))
            if e:
                pon["activity_level"] = e
        if not perfil.get("sex"):
            s = sexo(c.get("sexo"))
            if s:
                pon["sex"] = s

        if pon:
            pon["ficha_completada_desde_calma"] = datetime.now(timezone.utc).isoformat()
            cambios_perfil.append((email, c["client_id"], pon))
        if c.get("telefono") and not u.get("phone"):
            cambios_user.append((email, u["id"], str(c["telefono"]).strip()[:32]))

    print(f"{'SE VA A ESCRIBIR' if ESCRIBIR else 'ENSAYO, no se toca nada'}\n")
    print(f"perfiles a completar: {len(cambios_perfil)}")
    cuenta = {}
    for _, _, pon in cambios_perfil:
        for k in pon:
            if k != "ficha_completada_desde_calma":
                cuenta[k] = cuenta.get(k, 0) + 1
    for k, v in sorted(cuenta.items(), key=lambda x: -x[1]):
        print(f"   {k:18s} {v:4d}")
    print(f"\nteléfonos a poner: {len(cambios_user)}")
    if descartes:
        print("\nlo que NO se mete, y por qué:")
        for k, v in sorted(descartes.items(), key=lambda x: -x[1]):
            print(f"   {k:38s} {v:4d}")

    if not ESCRIBIR:
        print("\nPara hacerlo: --escribir")
        return

    n = 0
    for _, cid, pon in cambios_perfil:
        r = await db.client_profiles.update_one({"id": cid}, {"$set": pon})
        n += r.modified_count
    m = 0
    for _, uid, tel in cambios_user:
        r = await db.users.update_one({"id": uid}, {"$set": {"phone": tel}})
        m += r.modified_count
    print(f"\nperfiles actualizados: {n}")
    print(f"teléfonos puestos: {m}")

    for campo in ("height", "age", "goal", "activity_level", "sex"):
        print(f"   ahora tienen {campo:16s}: "
              f"{await db.client_profiles.count_documents({campo: {'$nin': [None, '']}})} de "
              f"{await db.client_profiles.count_documents({})}")

asyncio.run(main())
