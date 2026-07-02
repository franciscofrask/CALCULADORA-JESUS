# -*- coding: utf-8 -*-
"""
Export de REVISIÓN (no escribe nada): saca admin@jesusgallegopt.com + 10 usuarios
aleatorios de la app original (Firestore + Firebase Auth), los mapea a nuestro modelo
y escribe un JSON para revisar antes de decidir la migración real.
"""
import json, random, sys, datetime
sys.stdout.reconfigure(encoding="utf-8")

import firebase_admin
from firebase_admin import credentials, firestore, auth

OUT = r"C:\Users\Administrador\Desktop\migracion_revision.json"
ADMIN_EMAIL = "admin@jesusgallegopt.com"
N_ALEATORIOS = 10

cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# ---------- helpers ----------
def jdefault(o):
    if isinstance(o, (datetime.datetime, datetime.date)):
        return o.isoformat()
    try:
        return str(o)
    except Exception:
        return None

MACRO_KEYS = ["p_entreno", "h_entreno", "g_entreno", "p_peri", "h_peri",
              "p_descanso", "h_descanso", "g_descanso"]

def decode_macros(s):
    parts = str(s).split()
    if len(parts) >= 8:
        out = {}
        for i, k in enumerate(MACRO_KEYS):
            try: out[k] = float(parts[i])
            except: out[k] = parts[i]
        return out
    return {"raw": s}

def _pdate(k):
    try:
        y, m, d = map(int, str(k).split("-")); return (y, m, d)
    except Exception:
        return (0, 0, 0)

def latest_key(m):
    return max(m.keys(), key=_pdate) if isinstance(m, dict) and m else None

def get_doc(col, email):
    try:
        snap = db.collection(col).document(email).get()
        return snap.to_dict() if snap.exists else None
    except Exception as e:
        return {"_error": str(e)}

def get_dietas(email, sample=3):
    """Las dietas cuelgan en subcolecciones: dietasUsuarios/{email}/dietas/{fecha}
    y /dietasFavoritas. Devuelve conteos + muestra de las ultimas `sample` dietas."""
    base = db.collection("dietasUsuarios").document(email)
    try:
        dietas_ids = [d.id for d in base.collection("dietas").select([]).stream()]
    except Exception:
        dietas_ids = []
    try:
        fav_ids = [d.id for d in base.collection("dietasFavoritas").select([]).stream()]
    except Exception:
        fav_ids = []
    recientes = sorted(dietas_ids, key=_pdate)[-sample:]
    muestra = {}
    for fid in recientes:
        snap = base.collection("dietas").document(fid).get()
        muestra[fid] = snap.to_dict() if snap.exists else None
    return {"total_dietas": len(dietas_ids), "total_favoritas": len(fav_ids),
            "muestra_ultimas": muestra}

# ---------- 1) usuarios (solo IDs) ----------
print("Leyendo IDs de 'usuarios'...")
user_ids = [d.id for d in db.collection("usuarios").select([]).stream()]
print(f"  usuarios en Firestore: {len(user_ids)}")

# ---------- 2) Auth (email -> record con hash) ----------
print("Leyendo usuarios de Auth (para hashes de contraseña)...")
auth_by_email = {}
page = auth.list_users()
while page:
    for u in page.users:
        if u.email:
            auth_by_email[u.email.lower()] = u
    page = page.get_next_page()
print(f"  usuarios en Auth: {len(auth_by_email)}")

# ---------- 3) seleccionar admin + 10 aleatorios ----------
candidatos = [e for e in user_ids if e.lower() != ADMIN_EMAIL.lower()]
random.shuffle(candidatos)
seleccion = []
for e in candidatos:
    if len(seleccion) >= N_ALEATORIOS:
        break
    seleccion.append(e)
seleccion = [ADMIN_EMAIL] + seleccion
print("Seleccionados:", seleccion)

# ---------- 4) construir revisión ----------
def build(email):
    u = get_doc("usuarios", email) or {}
    a = auth_by_email.get(email.lower())
    prefs = u.get("preferencias", {}) or {}
    macros_map = u.get("macros", {}) or {}
    lk = latest_key(macros_map)
    dietas_info = get_dietas(email)
    membresia = u.get("membresia") or []
    plan = None
    if isinstance(membresia, list) and membresia:
        plan = (membresia[-1] or {}).get("nombre")

    auth_info = None
    if a:
        auth_info = {
            "uid": a.uid,
            "disabled": a.disabled,
            "email_verified": a.email_verified,
            "created_at": getattr(a.user_metadata, "creation_timestamp", None),
            "last_sign_in": getattr(a.user_metadata, "last_sign_in_timestamp", None),
            "providers": [p.provider_id for p in (a.provider_data or [])],
            "password_preservable": bool(getattr(a, "password_hash", None)),
            "password_hash": getattr(a, "password_hash", None),
            "password_salt": getattr(a, "password_salt", None),
        }

    return {
        "email": email,
        "en_auth": a is not None,
        "auth": auth_info,
        "mapeado": {
            "nombre": u.get("nombre"),
            "sexo_original": u.get("sexo"),
            "sexo": {"M": "hombre", "F": "mujer"}.get(u.get("sexo"), u.get("sexo")),
            "rol_inferido": "admin" if email.lower() == ADMIN_EMAIL.lower() else "client",
            "plan": plan,
            "macros_actuales": {"fecha": lk, **decode_macros(macros_map[lk])} if lk else None,
            "preferencias": {
                "food_preferences": prefs.get("preferencias"),
                "alergias": prefs.get("alergias"),
                "dias_entrenamiento": prefs.get("diasEntrenamiento"),
                "momento_entreno": prefs.get("momentoEntrenamientoPreferente"),
                "intraentrenamiento": prefs.get("intraentrenamiento"),
                "reparto_comidas": prefs.get("repartoDeComidas"),
            },
            "conteos": {
                "historial_macros": len(macros_map),
                "pesos": len(u.get("pesos", {}) or {}),
                "porcentajes_grasos": len(u.get("porcentajesGrasos", {}) or {}),
                "rutinas": len(u.get("rutinas", {}) or {}),
                "cardios": len(u.get("cardios", {}) or {}),
                "suplementacion": len(u.get("suplementacion", {}) or {}),
                "dietas_guardadas": dietas_info["total_dietas"],
                "dietas_favoritas": dietas_info["total_favoritas"],
            },
        },
        "raw_firestore": {
            "usuarios": u,
            "dietasUsuarios": dietas_info,
            "formulariosIniciales": get_doc("formulariosIniciales", email),
            "formularios": get_doc("formularios", email),
        },
    }

revision = {
    "generado": datetime.datetime.now().isoformat(),
    "proyecto": "jesusgallegopt",
    "nota": "Archivo de REVISION. No se ha escrito nada en Firebase ni en nuestra DB.",
    "total_usuarios_firestore": len(user_ids),
    "total_usuarios_auth": len(auth_by_email),
    "usuarios": [build(e) for e in seleccion],
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(revision, f, ensure_ascii=False, indent=2, default=jdefault)

print(f"\nOK -> {OUT}")
print(f"Usuarios exportados: {len(revision['usuarios'])}")
