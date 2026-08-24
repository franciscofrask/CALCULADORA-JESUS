# -*- coding: utf-8 -*-
"""Trae a PRODUCCION las dietas y favoritas de Calma que todavia no estan.

Francisco, 13-08-2026: «necesitamos actualizar la base de datos de produccion con los datos
actualizados a dia de hoy, de los clientes, no puede quedar nada fuera».

Calma (Firestore) sigue vivo y los clientes siguen guardando dietas alli, asi que la
migracion del 04-08 se quedo vieja al dia siguiente. Ademas hubo 8 clientes que aquella
migracion salto A PROPOSITO por tener cuenta nativa en 12EN12 (jlgb83, mtejero81,
agusortega7, est3banbike, info@rubiowellnesscoach, jmatamoros.elite, marcel-raul,
vcortessoler): se salto el cliente ENTERO para no pisarle la cuenta, y con el se quedaron
fuera sus dietas. Solo esos dos primeros son 2.069 dietas.

    Fuente:   Firestore del proyecto jesusgallegopt (dietasUsuarios/{email}/...)
    Destino:  Mongo de produccion, por el tunel del 27018

    python _sync_dietas.py                      cuenta lo que insertaria y NO escribe
    python _sync_dietas.py --escribir           lo escribe
    python _sync_dietas.py --email uno@dos.com  un solo cliente (para probar)

QUE NO HACE, y por que:

  - No pisa NUNCA una dieta que ya exista. La clave natural es (user_id, fecha) y solo se
    insertan las fechas que faltan. Si un cliente monto su comida del martes en 12EN12, ese
    martes se queda como esta aunque en Calma haya otra cosa ese mismo dia. En la resincro
    del 04-08 se perdieron 5 dietas de gallegoteam.montse justo por esto: aquel script hacia
    upsert y machacaba el dia. Aqui no hay upsert.

  - No toca a nadie que no tenga cuenta en la app. En Calma hay 1.323 fichas y en la app 194
    usuarios: el cruce por email da 177, y esos son todos los que se miran.

  - Es idempotente. Ejecutarlo dos veces no duplica nada: `diets` tiene indice unico sobre
    (user_id, fecha), y en favoritas se compara por (user_id, nombre) antes de insertar.
"""
import argparse
import datetime
import json
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AQUI = os.path.dirname(os.path.abspath(__file__))
os.chdir(AQUI)

import firebase_admin
from firebase_admin import credentials, firestore
from pymongo import MongoClient
from pymongo.errors import BulkWriteError

# Produccion, por el tunel SSH. Ojo: el 27018, no el 27017 (el 27017 es el Mongo local).
from _destino_sync import destino, no_entra, rotulo, solo_correos   # --dev escribe en desarrollo
PROD, BASE_PROD = destino()
SOLO = solo_correos()   # --solo fichero.txt limita la pasada
CLAVE = os.path.join(AQUI, "serviceAccountKey.json")

# Lo insertado se deja anotado en disco. Los documentos salen con el MISMO formato que los
# que ya estan (se comprobo contra 616 dietas y 56 favoritas ya migradas), asi que no llevan
# ninguna marca extra que los distinga: si hubiera que deshacer esto, la lista de claves
# esta aqui y no hay que deducirla.
#
# El ensayo escribe en OTRO fichero a proposito. Al principio compartian nombre y el primer
# ensayo que se lanzo despues de escribir dejo el registro a cero: como ya no faltaba nada,
# guardo listas vacias encima del acta de las 2.432 filas insertadas.
REGISTRO = os.path.join(AQUI, "_sync_dietas_insertadas.json")
PREVISION = os.path.join(AQUI, "_sync_dietas_previsto.json")


def ahora():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def norm_date(k):
    """'2025-11-1' -> '2025-11-01'. Los ids de documento de Calma no llevan ceros delante."""
    try:
        y, m, d = map(int, str(k).split("-"))
        return f"{y:04d}-{m:02d}-{d:02d}"
    except Exception:
        return str(k)


def peri_option(peri):
    if not isinstance(peri, dict):
        return "sin_peri"
    intra, post = bool(peri.get("intraentreno")), bool(peri.get("postentreno"))
    if intra and post:
        return "intra_post"
    if post:
        return "solo_post"
    if intra:
        return "solo_intra"
    return "sin_peri"


class Decodificador:
    """Pasa una dieta de Calma al documento que espera `db.diets`.

    Es el mismo decodificador de `_migrar_todos.py` con una diferencia deliberada: NO calcula
    macros ni convierte las unidades a gramos. Se contrasto contra las dietas que ya hay en
    produccion (616 de tres clientes ya migrados) y salen identicas campo a campo, de modo que
    lo que hay guardado en prod es exactamente esto:

        {"alimento_id", "nombre", "cantidad_g", "categorias", "racion", "unidades"}

    `cantidad_g` guarda el numero tal cual viene de Calma, que en los alimentos por unidades
    es el CONTEO DE PIEZAS y no gramos (un huevo entero aparece como "1"). Eso se corrige al
    LEER, en `core/cantidad_de_dieta.py`, que es la decision del 09-08: convertirlo aqui en
    masa haria que estas 2.400 dietas nuevas no se pareciesen a las 39.700 que ya estan, y
    encima las normalizaria dos veces.
    """

    def __init__(self, foods):
        self.foods = foods
        self.sin_catalogo = Counter()  # ids de alimento de Calma que ya no estan en db.foods

    def comida(self, meal_str):
        alimentos = []
        for tok in str(meal_str).split("-"):
            if "|" not in tok:
                continue
            sid, sqty = tok.split("|", 1)
            try:
                fid, qty = int(sid), float(sqty)
            except ValueError:
                continue
            food = self.foods.get(fid)
            if not food:
                # El alimento se borro del catalogo. Se cuenta y se sigue: dejar la dieta
                # fuera entera por un alimento seria perder las otras cinco lineas del dia.
                self.sin_catalogo[fid] += 1
                continue
            alimentos.append({
                "alimento_id": fid,
                "nombre": food.get("nombre"),
                "cantidad_g": qty,
                "categorias": food.get("categorias"),
                "racion": food.get("racion"),
                "unidades": bool(food.get("unidades")),
            })
        return {"alimentos": alimentos}

    def comidas_de(self, doc):
        """Las 4 comidas mas intra y post. `comidas` viene como lista, y un null es dia vacio."""
        comidas_src = doc.get("comidas") or []
        peri_src = doc.get("perientrenamiento") or {}
        comidas = {}
        for i, meal_str in enumerate(comidas_src):
            if meal_str:
                comidas[f"C{i+1}"] = self.comida(meal_str)
        if peri_src.get("intraentreno"):
            comidas["Intra"] = self.comida(peri_src["intraentreno"])
        if peri_src.get("postentreno"):
            comidas["Post"] = self.comida(peri_src["postentreno"])
        return comidas, comidas_src, peri_src

    @staticmethod
    def tipo_dia_de(doc):
        """Calma no guardaba el tipo de dia, pero lo delata la estructura: un dia (o una
        favorita) de DESCANSO no lleva ni momento de entreno ni perientrenamiento. Antes
        esto era un literal "entrenamiento" y las favoritas de descanso migradas salian
        como entreno (doc 57, F4: 225 corregidas en prod el 21-08 por nombre+sin peri)."""
        tiene_entreno = bool(doc.get("momentoEntrenamiento")) or bool(doc.get("perientrenamiento"))
        return "entrenamiento" if tiene_entreno else "descanso"

    def dieta(self, doc_id, doc, user_id):
        comidas, comidas_src, peri_src = self.comidas_de(doc)
        if not comidas:
            return None  # dia sin nada guardado; la migracion original tambien los salta
        return {
            "user_id": user_id,
            "fecha": norm_date(doc_id),
            "tipo_dia": self.tipo_dia_de(doc),
            "num_comidas": len([m for m in comidas_src if m]) or 4,
            # `momentoEntrenamiento` 0 es «en ayunas» y con el `or` cae en 1, igual que en la
            # migracion original. Se respeta para no crear dos criterios distintos.
            "momento_entreno": int(doc.get("momentoEntrenamiento") or 1),
            "opcion_peri": peri_option(peri_src),
            "comidas": comidas,
            "updated_at": ahora(),
            "is_cuadrado": False,
            "comida_volcada": None,
            "calma_migrated": True,
        }

    def favorita(self, doc_id, doc, user_id):
        import uuid
        comidas, comidas_src, peri_src = self.comidas_de(doc)
        return {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            # El id del documento ES el nombre que le puso el cliente. Algunos si traen
            # ademas el campo `nombre`, y ese manda.
            "name": doc.get("nombre") or doc_id,
            "tipo_dia": self.tipo_dia_de(doc),
            "num_comidas": len([m for m in comidas_src if m]) or 4,
            "momento_entreno": int(doc.get("momentoEntrenamiento") or 1),
            "opcion_peri": peri_option(peri_src),
            "comidas": comidas,
            "macros_snapshot": None,
            "distribution_targets": None,
            "created_at": ahora(),
            "calma_migrated": True,
        }


def main():
    ap = argparse.ArgumentParser(description="Sincroniza las dietas de Calma que faltan en produccion.")
    ap.add_argument("--escribir", action="store_true", help="escribe de verdad (por defecto solo cuenta)")
    ap.add_argument("--email", help="limitar a un cliente")
    # Las lee `_destino_sync` de sys.argv; aqui solo se declaran para que argparse no las
    # rechace (este es el unico sincronizador con argparse).
    ap.add_argument("--dev", action="store_true", help="escribir en desarrollo, no en produccion")
    ap.add_argument("--solo", help="fichero con los correos a los que limitar la pasada")
    args = ap.parse_args()
    escribir = args.escribir

    db = MongoClient(PROD, serverSelectionTimeoutMS=10000)[BASE_PROD]
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(CLAVE))
    fs = firestore.client()

    print("=" * 78)
    print("SINCRONIZAR DIETAS DE CALMA  ->  " + ("ESCRIBIENDO EN " + rotulo() if escribir
                                                 else "ENSAYO (no se toca nada)"))
    print("=" * 78)

    # El indice unico de (user_id, fecha) es la ultima red: aunque el codigo se equivocase,
    # Mongo no dejaria meter dos veces el mismo dia del mismo cliente.
    idx = db.diets.index_information()
    unico = any(i.get("unique") and [k[0] for k in i["key"]] == ["user_id", "fecha"]
                for i in idx.values())
    print(f"indice unico (user_id, fecha) en db.diets: {'SI' if unico else 'NO'}")
    if not unico:
        print("   AVISO: sin ese indice la idempotencia depende solo del codigo.")

    # --- a quien se mira: los que tienen cuenta en la app Y ficha en Calma, por email ---
    # OJO con los identificadores: `calma_raw.client_id` es el id del PERFIL de cliente, no
    # el del usuario. `db.diets.user_id` y `db.diet_favorites.user_id` van con `users.id`.
    users = {}
    for u in db.users.find({"deleted_at": None}, {"_id": 0, "id": 1, "email": 1}):
        if no_entra(u.get("email"), SOLO):
            continue
        if u.get("email"):
            users[u["email"].lower().strip()] = u["id"]
    emails_calma = set()
    for c in db.calma_raw.find({}, {"_id": 0, "email": 1}):
        if c.get("email"):
            emails_calma.add(c["email"].lower().strip())
    gente = sorted(emails_calma & set(users))
    if args.email:
        gente = [e for e in gente if e == args.email.lower().strip()]
        if not gente:
            print(f"\n{args.email} no cruza: o no tiene cuenta en la app, o no esta en Calma.")
            return
    print(f"clientes en Calma: {len(emails_calma)}   usuarios en la app: {len(users)}   "
          f"cruce por email: {len(gente)}")

    antes_dietas = db.diets.count_documents({})
    antes_favs = db.diet_favorites.count_documents({})
    print(f"antes: {antes_dietas} dietas y {antes_favs} favoritas en produccion\n")

    foods = {f["id"]: f for f in db.foods.find({}, {"_id": 0})}
    dec = Decodificador(foods)
    print(f"catalogo de alimentos: {len(foods)}")

    tot = Counter()
    por_cliente = []
    registro = {"cuando": ahora(), "escrito": escribir, "dietas": {}, "favoritas": {}}

    for i, email in enumerate(gente, 1):
        uid = users[email]
        base = fs.collection("dietasUsuarios").document(email)

        # ---------------- dietas ----------------
        ya = {d["fecha"] for d in db.diets.find({"user_id": uid}, {"_id": 0, "fecha": 1})}
        nuevas, vistas = {}, 0
        for snap in base.collection("dietas").stream():
            vistas += 1
            doc = dec.dieta(snap.id, snap.to_dict() or {}, uid)
            if doc is None:
                tot["dietas_vacias"] += 1
                continue
            if doc["fecha"] in ya:
                tot["dietas_ya_estaban"] += 1
                continue
            if doc["fecha"] in nuevas:
                # Dos ids distintos de Calma que normalizan a la misma fecha ('2025-1-1' y
                # '2025-01-01'). Se queda el ultimo, que es como lo veria el cliente en Calma.
                tot["dietas_fecha_repetida_en_calma"] += 1
            nuevas[doc["fecha"]] = doc

        # ---------------- favoritas ----------------
        # Aqui no hay indice unico, asi que la comprobacion por nombre es la unica defensa.
        ya_fav = {f.get("name") for f in db.diet_favorites.find({"user_id": uid}, {"_id": 0, "name": 1})}
        nuevas_fav, vistas_fav = {}, 0
        for snap in base.collection("dietasFavoritas").stream():
            vistas_fav += 1
            doc = dec.favorita(snap.id, snap.to_dict() or {}, uid)
            if doc["name"] in ya_fav:
                tot["favoritas_ya_estaban"] += 1
                continue
            if doc["name"] in nuevas_fav:
                tot["favoritas_nombre_repetido_en_calma"] += 1
            nuevas_fav[doc["name"]] = doc

        tot["dietas_en_calma"] += vistas
        tot["favoritas_en_calma"] += vistas_fav
        tot["dietas_a_insertar"] += len(nuevas)
        tot["favoritas_a_insertar"] += len(nuevas_fav)
        if nuevas or nuevas_fav:
            tot["clientes_con_algo"] += 1
            por_cliente.append((email, len(ya), len(nuevas), len(ya_fav), len(nuevas_fav)))
            registro["dietas"][email] = sorted(nuevas)
            registro["favoritas"][email] = sorted(nuevas_fav)

        if escribir:
            if nuevas:
                tot["dietas_insertadas"] += _meter(db.diets, list(nuevas.values()), tot, "dietas")
            if nuevas_fav:
                tot["favoritas_insertadas"] += _meter(db.diet_favorites, list(nuevas_fav.values()),
                                                      tot, "favoritas")

        if i % 15 == 0 or i == len(gente):
            print(f"   [{i}/{len(gente)}] {tot['dietas_a_insertar']} dietas y "
                  f"{tot['favoritas_a_insertar']} favoritas por meter, "
                  f"de {tot['clientes_con_algo']} clientes")

    # ---------------- informe ----------------
    print("\n" + "=" * 78)
    print("RESULTADO" if escribir else "LO QUE SE INSERTARIA (nada se ha escrito)")
    print("=" * 78)
    for k in ("dietas_en_calma", "dietas_ya_estaban", "dietas_vacias", "dietas_a_insertar",
              "dietas_insertadas", "favoritas_en_calma", "favoritas_ya_estaban",
              "favoritas_a_insertar", "favoritas_insertadas", "clientes_con_algo",
              "dietas_fecha_repetida_en_calma", "favoritas_nombre_repetido_en_calma",
              "choques_dietas", "choques_favoritas"):
        if tot[k] or k.endswith(("_a_insertar", "_ya_estaban", "clientes_con_algo")):
            print(f"   {k:38s} {tot[k]:>8d}")

    if dec.sin_catalogo:
        perdidos = sum(dec.sin_catalogo.values())
        print(f"\n   lineas descartadas por alimento que ya no esta en db.foods: {perdidos} "
              f"({len(dec.sin_catalogo)} ids distintos)")
        print(f"   ids: {sorted(dec.sin_catalogo)[:15]}")

    if por_cliente:
        por_cliente.sort(key=lambda x: -x[2])
        print(f"\n   {'cliente':40s}{'ya tenia':>10s}{'nuevas':>9s}{'fav ya':>8s}{'fav nuevas':>12s}")
        for email, ya, n, yaf, nf in por_cliente[:25]:
            print(f"   {email[:38]:40s}{ya:>10d}{n:>9d}{yaf:>8d}{nf:>12d}")
        if len(por_cliente) > 25:
            print(f"   ... y {len(por_cliente) - 25} clientes mas")

    salida = REGISTRO if escribir else PREVISION
    with open(salida, "w", encoding="utf-8") as fh:
        json.dump(registro, fh, ensure_ascii=False, indent=1)
    print(f"\n   claves de lo {'insertado' if escribir else 'que se insertaria'} en {salida}")

    # ---------------- comprobacion despues ----------------
    despues_dietas = db.diets.count_documents({})
    despues_favs = db.diet_favorites.count_documents({})
    print(f"\n   dietas    antes {antes_dietas} -> despues {despues_dietas} "
          f"({despues_dietas - antes_dietas:+d})")
    print(f"   favoritas antes {antes_favs} -> despues {despues_favs} "
          f"({despues_favs - antes_favs:+d})")

    if escribir:
        dup = list(db.diets.aggregate([
            {"$group": {"_id": {"u": "$user_id", "f": "$fecha"}, "n": {"$sum": 1}}},
            {"$match": {"n": {"$gt": 1}}},
            {"$count": "pares"},
        ]))
        dupf = list(db.diet_favorites.aggregate([
            {"$group": {"_id": {"u": "$user_id", "n": "$name"}, "n": {"$sum": 1}}},
            {"$match": {"n": {"$gt": 1}}},
            {"$count": "pares"},
        ]))
        print(f"   duplicados por (user_id, fecha):  {dup[0]['pares'] if dup else 0}")
        print(f"   duplicados por (user_id, nombre): {dupf[0]['pares'] if dupf else 0}")
    else:
        print("\n   ENSAYO: no se ha escrito nada. Repite con --escribir cuando cuadre.")


def _meter(coleccion, docs, tot, etiqueta):
    """Inserta en bloque. Un duplicado no aborta el resto ni se cuenta como insertado.

    `ordered=False` es a proposito: si otro cliente guarda ese mismo dia desde la app justo
    ahora, el indice unico rechaza ESA fila y las demas entran igual. Ese choque significa
    que el dato del cliente gano, que es lo que tiene que pasar.
    """
    try:
        res = coleccion.insert_many(docs, ordered=False)
        return len(res.inserted_ids)
    except BulkWriteError as e:
        choques = len(e.details.get("writeErrors", []))
        tot[f"choques_{etiqueta}"] += choques
        return e.details.get("nInserted", len(docs) - choques)


if __name__ == "__main__":
    main()
