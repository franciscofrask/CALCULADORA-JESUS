# -*- coding: utf-8 -*-
"""Le pone a cada cliente ACTIVO el plan que de verdad tiene contratado en Calma.

Francisco, 17-08-2026: «hay varios que no tienen los mismos planes que nos sale a
nosotros», «que conserven la misma membresia, nada de cambios», «los accesos de los planes
que si tenemos, como el de ELM, se quedan como los tenemos nosotros».

DE DONDE VIENE EL DESCUADRE
---------------------------
De la migracion de julio. `_migrar_todos.py::map_plan` solo sabia mirar tres palabras:

    if "gold" in t: return "gold"
    if "silver" in t: return "silver"
    if "bronze" in t: return "bronze"
    return "elm"          # <- aqui cayo TODO lo demas

Asi que Mantenimiento, Calculadora JP, Reto 12en12, Premium, CALMA 12 y Plan 6M acabaron
todos como «ELM (El Lunes Empiezo)». El texto original quedo guardado en `calma_plan_raw`,
que es de donde se puede reconstruir, pero el plan que ve el equipo -- y del que dependen
las habilitaciones -- era el equivocado para 58 clientes activos.

QUE HACE ESTE SCRIPT, Y QUE NO
------------------------------
HACE: leer la membresia VIGENTE de cada cliente en Calma (Firestore, `usuarios.membresia`,
el tramo que cubre hoy) y escribir el codigo de plan que le corresponde en
`client_profiles.plan` y `users.plan`, dejando el nombre original en `calma_plan_raw`.

NO HACE: tocar las habilitaciones de ningun plan. Lo que ELM da o deja de dar es decision
nuestra y se queda como esta, aunque en Calma ese mismo plan de otra cosa. Aqui solo se
corrige A QUE PLAN pertenece cada cliente.

NO TOCA a quien no esta activo en Calma, ni a los tres «Entrenador» (que son equipo, no
clientes), ni a nadie cuyo plan no se pueda determinar sin inventar.

EL MAPA, Y POR QUE CADA UNO
---------------------------
Los `items` de la membresia de Calma dicen a que da acceso cada plan (28 permisos
numerados; la tabla vive en su bundle, `_calma_ref/group-admin-miembros`). Medido sobre los
140 activos, los nombres se agrupan en cuatro accesos distintos, y el mapa sale de ahi y no
del parecido de los nombres:

    Gold / Reto 12en12 / Plan 6M .... 1,3,4..9,10,11,12,14,16,17,18,19  (quincenal + rutina
                                      personalizada + aerobico)
    Silver / Personalizado ......... igual pero sin quincenal, sin aerobico y con rutina
                                      «adaptada a tu nivel» (item 13)
    Bronze ......................... como Silver pero sin ninguna rutina
    ELM / Calculadora JP /
    Mantenimiento / CALMA 12 ....... dietas por macros, EDICION de macros por el cliente,
                                      buscador, historico de macros, favoritas y extras

    python _sync_planes_calma.py             enseña lo que cambiaria y NO escribe
    python _sync_planes_calma.py --escribir  lo escribe
"""
import asyncio
import os
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import firebase_admin
from firebase_admin import credentials, firestore
from motor.motor_asyncio import AsyncIOMotorClient

PROD = "mongodb://127.0.0.1:27018"
BASE = "jg12_restored"
ESCRIBIR = "--escribir" in sys.argv
HOY = datetime.now(timezone.utc)

if not firebase_admin._apps:
    firebase_admin.initialize_app(credentials.Certificate(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "serviceAccountKey.json")))
fs = firestore.client()


def _limpio(t: str) -> str:
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(t.split())


# Los que NO se tocan porque no son un plan de cliente.
NO_ES_PLAN = ("entrenador",)

# Los que hacen falta y todavia no existen en el catalogo del codigo. Se dejan fuera a
# proposito: escribir un plan que el catalogo no conoce deja al cliente sin habilitaciones
# (plan_features devuelve [] y se queda sin nada), que es peor que el plan equivocado.
FALTAN_EN_EL_CATALOGO = {
    "reto12en12": "Reto 12en12 (accesos identicos a Gold)",
    "basica": "Basica (solo dietas por macros y buscador)",
    "personalizado": "Plan Personalizado 500/550 (accesos de Silver)",
}


def codigo_de_calma(nombre: str):
    """El codigo de nuestro catalogo para el nombre de plan que usa Calma."""
    t = _limpio(nombre)
    if not t:
        return None
    if any(x in t for x in NO_ES_PLAN):
        return None
    if "reto" in t and ("12en12" in t or "12 en 12" in t):
        return "reto12en12"
    if "reto 60" in t or "reto60" in t:
        return "reto60"
    if "gold" in t:
        return "gold"
    if "silver" in t:
        return "silver"
    if "bronze" in t or "bronce" in t:
        return "bronze"
    if "lunes empiezo" in t or t == "elm":
        return "elm"
    if "calculadora" in t:
        return "calculadora_jp"
    if "mantenimiento" in t:
        return "mantenimiento"
    if "calma" in t:
        return "calma12"
    if "premium" in t:
        return "premium"
    if "6m" in t or "6 m" in t:
        return "plan_6m"
    if "personalizado" in t:
        return "personalizado"
    if "basica" in t:
        return "basica"
    return None


def membresia_vigente(doc: dict):
    """La membresia que vale hoy: la que cubre HOY, y si no, una que aun no ha vencido.

    Lo segundo no es un apaño: es el criterio de Calma. Su panel decia 141 miembros y yo
    detectaba 140, y el que faltaba era Marcos Roman, que renovo con un Reto 12en12 que
    EMPIEZA mañana mientras su Mantenimiento acabo el 11. Entre las dos hay un hueco de
    seis dias en los que no le cubre ninguna, y aun asi es miembro: ya ha pagado lo
    siguiente. Contar solo la que abraza el dia de hoy deja fuera a quien renueva por
    adelantado, que es justo el que mejor se porta.
    """
    tramos = [m for m in (doc.get("membresia") or [])
              if isinstance(m, dict) and m.get("inicio") and m.get("fin")]
    cubren_hoy = [m for m in tramos if m["inicio"] <= HOY <= m["fin"]]
    if cubren_hoy:
        return max(cubren_hoy, key=lambda x: x["fin"])
    sin_vencer = [m for m in tramos if m["fin"] >= HOY]
    return max(sin_vencer, key=lambda x: x["fin"]) if sin_vencer else None


async def main():
    db = AsyncIOMotorClient(PROD, serverSelectionTimeoutMS=20000)[BASE]
    print(f"{'ENSAYO (no escribe)' if not ESCRIBIR else 'ESCRIBIENDO EN PRODUCCION'}\n")

    usuarios = {}
    async for u in db.users.find({}, {"_id": 0, "id": 1, "email": 1, "name": 1, "plan": 1}):
        if u.get("email"):
            usuarios[u["email"].lower()] = u

    cambios, sin_codigo, sin_catalogo, ya_estaban = [], Counter(), Counter(), 0
    mirados = 0

    for d in fs.collection("usuarios").stream():
        correo = d.id.lower()
        u = usuarios.get(correo)
        if not u:
            continue
        m = membresia_vigente(d.to_dict() or {})
        if not m:
            continue
        mirados += 1
        nombre = (m.get("nombre") or "").strip()
        codigo = codigo_de_calma(nombre)
        if not codigo:
            sin_codigo[nombre or "(sin nombre)"] += 1
            continue
        if codigo in FALTAN_EN_EL_CATALOGO:
            sin_catalogo[f"{nombre}  ->  {codigo}"] += 1
            continue
        perfil = await db.client_profiles.find_one({"user_id": u["id"]},
                                                   {"_id": 0, "id": 1, "plan": 1})
        if not perfil:
            continue
        if (perfil.get("plan") or "").lower() == codigo:
            ya_estaban += 1
            continue
        cambios.append((u.get("name") or "?", correo, perfil.get("plan"), codigo, nombre,
                        perfil["id"], u["id"]))

    print(f"activos de Calma con cuenta en la app: {mirados}")
    print(f"   ya tenian el plan correcto: {ya_estaban}")
    print(f"   se corrigen ahora:          {len(cambios)}")
    print(f"   esperan a que exista el plan: {sum(sin_catalogo.values())}")
    print(f"   sin plan que se pueda deducir: {sum(sin_codigo.values())}\n")

    print(f"   {'nombre':26}{'correo':34}{'antes':16}{'ahora':16}en Calma")
    for nombre, correo, antes, ahora, calma, _pid, _uid in sorted(cambios, key=lambda x: x[3]):
        print(f"   {nombre[:24]:26}{correo[:32]:34}{str(antes):16}{ahora:16}{calma[:26]}")

    if sin_catalogo:
        print("\n   ESPERAN A QUE SE CREE EL PLAN:")
        for k, v in sin_catalogo.most_common():
            print(f"      {v:3}  {k}")
    if sin_codigo:
        print("\n   NO SE TOCAN (no es un plan de cliente o no se puede deducir):")
        for k, v in sin_codigo.most_common():
            print(f"      {v:3}  {k}")

    if not ESCRIBIR:
        print("\n(ensayo: no se ha escrito nada. Con --escribir se aplica)")
        return

    for _n, _c, _antes, ahora, calma, pid, uid in cambios:
        await db.client_profiles.update_one(
            {"id": pid},
            {"$set": {"plan": ahora, "calma_plan_raw": calma,
                      "plan_origen": "calma", "plan_puesto_en": HOY.isoformat()}})
        await db.users.update_one({"id": uid}, {"$set": {"plan": ahora}})
    print(f"\nescritos {len(cambios)} clientes")


# Solo al ejecutarlo: `_alta_desde_calma` importa de aqui el mapa de planes y el
# criterio de membresia vigente, y sin esto le corria la sincronizacion entera por
# el mero hecho de importarlo.
if __name__ == "__main__":
    asyncio.run(main())
