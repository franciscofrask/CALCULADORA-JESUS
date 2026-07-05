# -*- coding: utf-8 -*-
"""
Migración COMPLETA de los 166 miembros activos de Calma (lista admin-miembros) a nuestra MongoDB.
Todos como clientes, todo el histórico (dietas, pesos, macros, check-ins, favoritas), con su plan.
- Contraseña: NO se pone temporal; solo se guarda el hash de Firebase (login por scrypt) y un
  bcrypt aleatorio inservible para que exista el campo.
- Fotos de reportes: bloqueadas por permisos (otro bucket). Se guardan las URLs gs:// en el
  check-in (photo_urls_calma) para descargarlas cuando haya acceso.
- Idempotente (marca calma_migrated). NO toca usuarios nativos (no-calma) ya existentes: los salta.
Ejecutar desde backend/: venv/Scripts/python.exe _migrar_todos.py
"""
import asyncio, sys, uuid, datetime
sys.stdout.reconfigure(encoding="utf-8")
import bcrypt
import firebase_admin
from firebase_admin import credentials, firestore, auth
from core.database import db as mdb
from routes.calculator import _efectivos_calma

firebase_admin.initialize_app(credentials.Certificate("serviceAccountKey.json"))
fs = firestore.client()

MIEMBROS = r"C:\Users\Administrador\Desktop\calma_miembros.txt"

def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def norm_date(k):
    try:
        y, m, d = map(int, str(k).split("-")); return f"{y:04d}-{m:02d}-{d:02d}"
    except Exception:
        return str(k)

def pdate(k):
    try:
        y, m, d = map(int, str(k).split("-")); return (y, m, d)
    except Exception:
        return (0, 0, 0)

def latest(mp):
    return max(mp.keys(), key=pdate) if isinstance(mp, dict) and mp else None

MK = ["p_ent", "h_ent", "g_ent", "p_peri", "h_peri", "p_desc", "h_desc", "g_desc"]

def decode_macros(s):
    parts = str(s).split()
    if len(parts) < 8:
        return None
    v = {}
    for i, k in enumerate(MK):
        try: v[k] = float(parts[i])
        except: v[k] = 0.0
    return v

def _mb(P, H, G=None):
    b = {"protein": P, "carbs": H, "proteinas": P, "hidratos": H}
    if G is not None:
        b["fat"] = G; b["grasas"] = G
    b["calories"] = round(P * 4 + H * 4 + (G or 0) * 9, 1)
    return b

def macro_blocks(dec):
    return (_mb(dec["p_ent"], dec["h_ent"], dec["g_ent"]),
            _mb(dec["p_peri"], dec["h_peri"]),
            _mb(dec["p_desc"], dec["h_desc"], dec["g_desc"]))

def peri_option(peri):
    if not isinstance(peri, dict):
        return "sin_peri"
    intra, post = bool(peri.get("intraentreno")), bool(peri.get("postentreno"))
    if intra and post: return "intra_post"
    if post: return "solo_post"
    if intra: return "solo_intra"
    return "sin_peri"

def map_plan(txt):
    t = (txt or "").lower()
    if "gold" in t: return "gold"
    if "silver" in t: return "silver"
    if "bronze" in t or "bronce" in t: return "bronze"
    return "elm"  # Premium/Reto/Calculadora JP/etc.: default; el texto crudo queda en calma_plan_raw

async def main():
    # 1) lista de miembros + plan
    lines = [l.strip() for l in open(MIEMBROS, encoding="utf-8") if l.strip()]
    miembros = []
    for l in lines:
        email, _, plan = l.partition("|")
        miembros.append((email.strip().lower(), plan.strip()))
    emails = set(e for e, _ in miembros)
    print(f"miembros a migrar: {len(miembros)}")

    # 2) hashes de Auth (una pasada, recogemos solo los 166)
    print("recogiendo hashes de Auth...")
    authmap = {}
    page = auth.list_users()
    while page:
        for u in page.users:
            if u.email and u.email.lower() in emails:
                authmap[u.email.lower()] = {
                    "uid": u.uid,
                    "password_hash": getattr(u, "password_hash", None),
                    "password_salt": getattr(u, "password_salt", None),
                }
        page = page.get_next_page()
    print(f"hashes recogidos: {len(authmap)}/{len(emails)}")

    # 3) foods para calcular macros de dietas
    foods = {f["id"]: f for f in await mdb.foods.find({}, {"_id": 0}).to_list(6000)}
    print(f"foods: {len(foods)}")

    def build_meal(meal_str):
        alimentos = []
        for tok in str(meal_str).split("-"):
            if "|" not in tok: continue
            sid, sqty = tok.split("|", 1)
            try: fid = int(sid); qty = float(sqty)
            except: continue
            food = foods.get(fid)
            if not food: continue
            es_unidad = bool(food.get("unidades"))
            racion = float(food.get("racion") or 100) or 100.0
            cantidad_g = qty * racion if es_unidad else qty
            try: ef, _, _ = _efectivos_calma(food, cantidad_g)
            except Exception: ef = {"P": 0, "H": 0, "G": 0}
            alimentos.append({"alimento_id": fid, "nombre": food.get("nombre"),
                              "cantidad_g": cantidad_g, "macros_efectivos": ef,
                              "categorias": food.get("categorias"), "racion": food.get("racion"),
                              "unidades": es_unidad})
        return {"alimentos": alimentos}

    stats = {"migrados": 0, "saltados_nativos": 0, "sin_auth": 0,
             "diets": 0, "reports": 0, "macro_history": 0, "checkins": 0, "favoritas": 0, "fotos_urls": 0}
    saltados, errores = [], []

    for idx, (email, plan_raw) in enumerate(miembros, 1):
        try:
            # saltar usuarios NATIVOS ya existentes (no calma) para no pisarlos
            existing = await mdb.users.find_one({"email": email}, {"_id": 0, "id": 1, "calma_migrated": 1})
            if existing and not existing.get("calma_migrated"):
                stats["saltados_nativos"] += 1; saltados.append(email); continue

            u = fs.collection("usuarios").document(email).get().to_dict() or {}
            am = authmap.get(email)
            if not am:
                stats["sin_auth"] += 1  # sin cuenta Auth: no podra loguear, pero migramos datos

            prev_uid = existing["id"] if existing else None
            prof_prev = await mdb.client_profiles.find_one({"user_id": prev_uid} if prev_uid else {"_id": None}, {"_id": 0, "id": 1})
            prev_cid = prof_prev["id"] if prof_prev else None
            if prev_uid:
                await mdb.diets.delete_many({"user_id": prev_uid})
            if prev_cid:
                await mdb.macro_history.delete_many({"client_id": prev_cid, "calma_migrated": True})
                await mdb.reports.delete_many({"client_id": prev_cid, "calma_migrated": True})
                await mdb.checkins.delete_many({"client_id": prev_cid, "calma_migrated": True})
                await mdb.diet_favorites.delete_many({"user_id": prev_uid, "calma_migrated": True})

            user_id = prev_uid or str(uuid.uuid4())
            client_id = prev_cid or str(uuid.uuid4())
            pw = bcrypt.hashpw(uuid.uuid4().hex.encode(), bcrypt.gensalt()).decode()  # inservible

            await mdb.users.update_one({"email": email}, {"$set": {
                "id": user_id, "email": email, "password": pw,
                "name": u.get("nombre") or email.split("@")[0], "phone": None,
                "role": "client", "plan": map_plan(plan_raw), "trainer_id": None, "created_at": now_iso(),
                "calma_migrated": True, "calma_email": email,
                "firebase_password_hash": am.get("password_hash") if am else None,
                "firebase_password_salt": am.get("password_salt") if am else None,
            }}, upsert=True)

            macros_map = u.get("macros") or {}
            lk = latest(macros_map)
            dec = decode_macros(macros_map[lk]) if lk else None
            training, peri, rest = macro_blocks(dec) if dec else ({}, {}, {})
            pesos = u.get("pesos") or {}
            grasos = u.get("porcentajesGrasos") or {}
            prefs = u.get("preferencias") or {}
            sexo = {"M": "hombre", "F": "mujer"}.get(u.get("sexo"), "hombre")

            await mdb.client_profiles.update_one({"user_id": user_id}, {"$set": {
                "id": client_id, "user_id": user_id,
                "plan": map_plan(plan_raw), "calma_plan_raw": plan_raw, "price": 0.0, "week": 1,
                "status": "activo", "trainer_id": None,
                "macros_training": training, "macros_rest": rest, "macros_periworkout": peri,
                "macros_source": "manual", "sex": sexo,
                "weight": float(pesos[latest(pesos)]) if pesos else None,
                "body_fat": float(grasos[latest(grasos)]) if grasos else None,
                "food_preferences": [x for x in str(prefs.get("preferencias", "")).split("|") if x],
                "avoided_categories": [],
                "avoided_keywords": [x.strip() for x in str(prefs.get("alergias", "")).split(",") if x.strip()],
                "diet_momento_entreno": int(prefs.get("momentoEntrenamientoPreferente", 1) or 1),
                "diet_num_comidas": 4,
                "diet_opcion_peri": "intra_post" if prefs.get("intraentrenamiento") else "solo_post",
                "questionnaire_completed": True, "created_at": now_iso(), "calma_migrated": True,
            }}, upsert=True)

            # macro_history
            mh = []
            for fk, val in macros_map.items():
                d = decode_macros(val)
                if not d: continue
                tr, pe, re_ = macro_blocks(d)
                mh.append({"id": str(uuid.uuid4()), "client_id": client_id, "user_id": user_id,
                           "new_training": tr, "new_rest": re_, "training": tr, "rest": re_, "peri": pe,
                           "effective_date": norm_date(fk), "note": "Importado de Calma", "changed_by": "migracion",
                           "client_weight": float(pesos[fk]) if fk in pesos else None,
                           "peso": float(pesos[fk]) if fk in pesos else None,
                           "porcentaje_graso": float(grasos[fk]) if fk in grasos else None,
                           "sexo": sexo, "created_at": now_iso(), "calma_migrated": True})
            if mh: await mdb.macro_history.insert_many(mh); stats["macro_history"] += len(mh)

            # pesos -> reports
            reps = []
            for fk, w in pesos.items():
                try: wf = float(w)
                except: continue
                reps.append({"id": str(uuid.uuid4()), "client_id": client_id, "weight": wf,
                             "measurements": None, "photos": None, "notes": "Importado de Calma",
                             "trainer_feedback": None, "created_at": norm_date(fk) + "T12:00:00+00:00",
                             "calma_migrated": True})
            if reps: await mdb.reports.insert_many(reps); stats["reports"] += len(reps)

            # dietas
            base = fs.collection("dietasUsuarios").document(email)
            n_diet = 0
            for d in base.collection("dietas").stream():
                dd = d.to_dict() or {}
                comidas_src = dd.get("comidas") or []
                peri_src = dd.get("perientrenamiento") or {}
                comidas = {}
                for i, meal_str in enumerate(comidas_src):
                    if meal_str: comidas[f"C{i+1}"] = build_meal(meal_str)
                if peri_src.get("intraentreno"): comidas["Intra"] = build_meal(peri_src["intraentreno"])
                if peri_src.get("postentreno"): comidas["Post"] = build_meal(peri_src["postentreno"])
                if not comidas: continue
                fecha = norm_date(d.id)
                await mdb.diets.update_one({"user_id": user_id, "fecha": fecha}, {"$set": {
                    "user_id": user_id, "fecha": fecha, "tipo_dia": "entrenamiento",
                    "num_comidas": len([m for m in comidas_src if m]) or 4,
                    "momento_entreno": int(dd.get("momentoEntrenamiento") or 1),
                    "opcion_peri": peri_option(peri_src), "comidas": comidas, "updated_at": now_iso(),
                    "is_cuadrado": False, "comida_volcada": None, "calma_migrated": True,
                }}, upsert=True)
                n_diet += 1
            stats["diets"] += n_diet

            # dietas favoritas -> diet_favorites
            favs = []
            for d in base.collection("dietasFavoritas").stream():
                fav = d.to_dict() or {}
                comidas_src = fav.get("comidas") or []
                peri_src = fav.get("perientrenamiento") or {}
                comidas = {}
                for i, meal_str in enumerate(comidas_src):
                    if meal_str: comidas[f"C{i+1}"] = build_meal(meal_str)
                if peri_src.get("intraentreno"): comidas["Intra"] = build_meal(peri_src["intraentreno"])
                if peri_src.get("postentreno"): comidas["Post"] = build_meal(peri_src["postentreno"])
                favs.append({"id": str(uuid.uuid4()), "user_id": user_id,
                             "name": fav.get("nombre") or d.id,
                             "tipo_dia": "entrenamiento",
                             "num_comidas": len([m for m in comidas_src if m]) or 4,
                             "momento_entreno": int(fav.get("momentoEntrenamiento") or 1),
                             "opcion_peri": peri_option(peri_src), "comidas": comidas,
                             "macros_snapshot": None, "distribution_targets": None,
                             "created_at": now_iso(), "calma_migrated": True})
            if favs: await mdb.diet_favorites.insert_many(favs); stats["favoritas"] += len(favs)

            # formularios -> checkins (con URLs de foto guardadas para bajarlas luego)
            forms = fs.collection("formularios").document(email).get().to_dict() or {}
            cks = []
            for fk, val in forms.items():
                if not isinstance(val, dict): continue
                foto_urls = [v for v in val.values() if isinstance(v, str) and v.startswith("gs://")]
                stats["fotos_urls"] += len(foto_urls)
                peso = val.get("peso")
                cks.append({"id": str(uuid.uuid4()), "client_id": client_id, "user_id": user_id,
                            "type": "monthly",
                            "weight": float(peso) if isinstance(peso, (int, float)) else None,
                            "notes": f"Importado de Calma. suplementacion={val.get('suplementacion')} cumplimiento={val.get('cumplimientoDieta')}",
                            "trainer_feedback": None,
                            "photo_urls_calma": foto_urls,  # pendientes de descargar (Storage bloqueado)
                            "created_at": (val.get("fechaEnvio") or (norm_date(fk) + "T12:00:00+00:00")),
                            "calma_migrated": True})
            if cks: await mdb.checkins.insert_many(cks); stats["checkins"] += len(cks)

            stats["migrados"] += 1
            if idx % 10 == 0 or idx == len(miembros):
                print(f"[{idx}/{len(miembros)}] {email} | diets={n_diet} favs={len(favs)} ck={len(cks)} | acum: {stats['migrados']} migrados, {stats['diets']} dietas")
        except Exception as e:
            errores.append((email, f"{type(e).__name__}: {e}"))
            print(f"  ERROR en {email}: {type(e).__name__}: {e}")

    print("\n===== RESUMEN =====")
    for k, v in stats.items(): print(f"  {k}: {v}")
    print(f"  saltados (nativos existentes): {saltados}")
    print(f"  errores: {len(errores)}")
    for e, msg in errores[:20]: print(f"    {e}: {msg}")

asyncio.run(main())
