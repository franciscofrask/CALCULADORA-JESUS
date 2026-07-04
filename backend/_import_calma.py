# -*- coding: utf-8 -*-
"""
Import de PRUEBA: trae 3 usuarios de Calma (desde calma_3users_raw.json ya exportado)
a NUESTRA MongoDB. Rol = cliente, todo el histórico, sin plan real (placeholder).
Idempotente: borra lo previo marcado calma_migrated de estos emails antes de reimportar.
Contraseña: temporal (bcrypt) para poder entrar; se guarda el hash de Firebase para
conservar la real más adelante (login scrypt pendiente).
"""
import asyncio, sys, json, uuid, datetime
sys.stdout.reconfigure(encoding="utf-8")
import bcrypt
from core.database import db
from routes.calculator import _efectivos_calma

RAW = r"C:\Users\Administrador\Desktop\calma_3users_raw.json"
TEMP_PW = "Calma2026"          # contraseña temporal para los 3 de prueba
PLAN_PLACEHOLDER = "elm"       # sin plan real por ahora

def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def norm_date(k):
    """'2026-3-8' -> '2026-03-08'."""
    try:
        y, m, d = map(int, str(k).split("-"))
        return f"{y:04d}-{m:02d}-{d:02d}"
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
    training = _mb(dec["p_ent"], dec["h_ent"], dec["g_ent"])
    peri = _mb(dec["p_peri"], dec["h_peri"])
    rest = _mb(dec["p_desc"], dec["h_desc"], dec["g_desc"])
    return training, peri, rest

def peri_option(peri):
    if not isinstance(peri, dict):
        return "sin_peri"
    intra = bool(peri.get("intraentreno"))
    post = bool(peri.get("postentreno"))
    if intra and post: return "intra_post"
    if post: return "solo_post"
    if intra: return "solo_intra"
    return "sin_peri"

async def main():
    raw = json.load(open(RAW, encoding="utf-8"))
    foods = {f["id"]: f for f in await db.foods.find({}, {"_id": 0}).to_list(6000)}
    print(f"foods cargados: {len(foods)}")
    pw_hash = bcrypt.hashpw(TEMP_PW.encode(), bcrypt.gensalt()).decode()

    for email, data in raw.items():
        u = data.get("usuarios") or {}
        auth = data.get("auth") or {}
        print(f"\n===== {email} ({u.get('nombre')}) =====")

        # --- limpiar import previo de este email (idempotente) ---
        prev = await db.users.find_one({"email": email, "calma_migrated": True}, {"_id": 0, "id": 1})
        prev_uid = prev["id"] if prev else None
        prof_prev = await db.client_profiles.find_one({"user_id": prev_uid} if prev_uid else {"_id": None}, {"_id": 0, "id": 1})
        prev_cid = prof_prev["id"] if prof_prev else None
        if prev_uid:
            await db.diets.delete_many({"user_id": prev_uid})
        if prev_cid:
            await db.macro_history.delete_many({"client_id": prev_cid, "calma_migrated": True})
            await db.reports.delete_many({"client_id": prev_cid, "calma_migrated": True})
            await db.checkins.delete_many({"client_id": prev_cid, "calma_migrated": True})

        user_id = prev_uid or str(uuid.uuid4())
        client_id = prev_cid or str(uuid.uuid4())

        # --- users ---
        await db.users.update_one({"email": email}, {"$set": {
            "id": user_id, "email": email, "password": pw_hash,
            "name": u.get("nombre") or email.split("@")[0], "phone": None,
            "role": "client", "plan": None, "trainer_id": None, "created_at": now_iso(),
            "calma_migrated": True, "calma_email": email,
            "firebase_password_hash": auth.get("password_hash"),
            "firebase_password_salt": auth.get("password_salt"),
        }}, upsert=True)

        # --- macros vigentes (última entrada) ---
        macros_map = u.get("macros") or {}
        lk = latest(macros_map)
        dec = decode_macros(macros_map[lk]) if lk else None
        training, peri, rest = macro_blocks(dec) if dec else ({}, {}, {})
        pesos = u.get("pesos") or {}
        grasos = u.get("porcentajesGrasos") or {}
        prefs = u.get("preferencias") or {}
        sexo = {"M": "hombre", "F": "mujer"}.get(u.get("sexo"), "hombre")

        # --- client_profiles ---
        await db.client_profiles.update_one({"user_id": user_id}, {"$set": {
            "id": client_id, "user_id": user_id,
            "plan": PLAN_PLACEHOLDER, "price": 0.0, "week": 1, "status": "activo", "trainer_id": None,
            "macros_training": training, "macros_rest": rest, "macros_periworkout": peri,
            "macros_source": "manual",
            "sex": sexo,
            "weight": float(pesos[latest(pesos)]) if pesos else None,
            "body_fat": float(grasos[latest(grasos)]) if grasos else None,
            "food_preferences": [x for x in str(prefs.get("preferencias", "")).split("|") if x],
            "avoided_categories": [],
            "avoided_keywords": [x.strip() for x in str(prefs.get("alergias", "")).split(",") if x.strip()],
            "diet_momento_entreno": int(prefs.get("momentoEntrenamientoPreferente", 1) or 1),
            "diet_num_comidas": 4,
            "diet_opcion_peri": "intra_post" if prefs.get("intraentrenamiento") else "solo_post",
            "questionnaire_completed": True,
            "created_at": now_iso(), "calma_migrated": True,
        }}, upsert=True)

        # --- macro_history (todo el histórico) ---
        mh = []
        for fk, val in macros_map.items():
            d = decode_macros(val)
            if not d: continue
            tr, pe, re_ = macro_blocks(d)
            fdate = norm_date(fk)
            mh.append({
                "id": str(uuid.uuid4()), "client_id": client_id, "user_id": user_id,
                "new_training": tr, "new_rest": re_, "training": tr, "rest": re_, "peri": pe,
                "effective_date": fdate, "note": "Importado de Calma", "changed_by": "migracion",
                "client_weight": float(pesos[fk]) if fk in pesos else None,
                "peso": float(pesos[fk]) if fk in pesos else None,
                "porcentaje_graso": float(grasos[fk]) if fk in grasos else None,
                "sexo": sexo, "created_at": now_iso(), "calma_migrated": True,
            })
        if mh:
            await db.macro_history.insert_many(mh)

        # --- pesos -> reports ---
        reps = []
        for fk, w in pesos.items():
            try: wf = float(w)
            except: continue
            reps.append({
                "id": str(uuid.uuid4()), "client_id": client_id, "weight": wf,
                "measurements": None, "photos": None,
                "notes": "Importado de Calma", "trainer_feedback": None,
                "created_at": norm_date(fk) + "T12:00:00+00:00", "calma_migrated": True,
            })
        if reps:
            await db.reports.insert_many(reps)

        # --- dietas -> db.diets (todo el histórico) ---
        dietas = data.get("dietas") or {}
        n_diet = 0
        for fk, dd in dietas.items():
            comidas_src = dd.get("comidas") or []
            peri_src = dd.get("perientrenamiento") or {}
            comidas = {}
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
                    try:
                        ef, _, _ = _efectivos_calma(food, cantidad_g)
                    except Exception:
                        ef = {"P": 0, "H": 0, "G": 0}
                    alimentos.append({
                        "alimento_id": fid, "nombre": food.get("nombre"),
                        "cantidad_g": cantidad_g, "macros_efectivos": ef,
                        "categorias": food.get("categorias"), "racion": food.get("racion"),
                        "unidades": es_unidad,
                    })
                return {"alimentos": alimentos}
            for i, meal_str in enumerate(comidas_src):
                if meal_str:
                    comidas[f"C{i+1}"] = build_meal(meal_str)
            if peri_src.get("intraentreno"):
                comidas["Intra"] = build_meal(peri_src["intraentreno"])
            if peri_src.get("postentreno"):
                comidas["Post"] = build_meal(peri_src["postentreno"])
            if not comidas:
                continue
            fecha = norm_date(fk)
            await db.diets.update_one({"user_id": user_id, "fecha": fecha}, {"$set": {
                "user_id": user_id, "fecha": fecha, "tipo_dia": "entrenamiento",
                "num_comidas": len([m for m in comidas_src if m]) or 4,
                "momento_entreno": int(dd.get("momentoEntrenamiento") or 1),
                "opcion_peri": peri_option(peri_src),
                "comidas": comidas, "updated_at": now_iso(),
                "is_cuadrado": False, "comida_volcada": None, "calma_migrated": True,
            }}, upsert=True)
            n_diet += 1

        # --- checkins (formularios) - basico (peso, fecha, nota); fotos/mediciones = TODO ---
        forms = data.get("formularios") or {}
        cks = []
        for fk, val in forms.items():
            if not isinstance(val, dict): continue
            peso = val.get("peso")
            cks.append({
                "id": str(uuid.uuid4()), "client_id": client_id, "type": "monthly",
                "weight": float(peso) if isinstance(peso, (int, float)) else None,
                "notes": f"Importado de Calma. suplementacion={val.get('suplementacion')} cumplimiento={val.get('cumplimientoDieta')}",
                "trainer_feedback": None,
                "created_at": (val.get("fechaEnvio") or (norm_date(fk) + "T12:00:00+00:00")),
                "calma_migrated": True,
            })
        if cks:
            await db.checkins.insert_many(cks)

        print(f"  users:1 profile:1 macro_history:{len(mh)} reports:{len(reps)} diets:{n_diet} checkins:{len(cks)}")

    print(f"\nContraseña temporal de los 3: {TEMP_PW}")
    print("Import de prueba completado.")

asyncio.run(main())
