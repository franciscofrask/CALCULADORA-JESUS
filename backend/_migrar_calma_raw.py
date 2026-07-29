# -*- coding: utf-8 -*-
"""
Import de STAGING de Calma -> coleccion `calma_raw` (NO toca los formularios actuales).

Motivacion: los formularios/cuestionarios de la app van a cambiar, asi que NO reescribimos
client_profiles / checkins / reports. En su lugar volcamos TODO el dato de Calma (Firestore)
en una coleccion nueva `calma_raw`, por cliente, con:
  - los campos decodificados y legibles (macros, mediciones, respuestas mensuales, membresias...)
  - el Firestore verbatim (raw_firestore) por si el decode se deja algo.
Cuando el nuevo formulario este listo, se mapea desde `calma_raw` sin haber perdido nada.

Fuentes Firestore (proyecto jesusgallegopt):
  usuarios/{email}, formulariosIniciales/{email}, formularios/{email}
  (las dietas NO se copian: ya estan en db.diets; solo se cuenta cuantas hay)

Idempotente: upsert por email. Solo escribe en `calma_raw`. No modifica nada mas.

Uso (desde backend/):
  venv/Scripts/python.exe _migrar_calma_raw.py <email>     # 1 cliente (validar)
  venv/Scripts/python.exe _migrar_calma_raw.py all         # todos
  venv/Scripts/python.exe _migrar_calma_raw.py all --limit 20
"""
import asyncio, sys, uuid, math, datetime
sys.stdout.reconfigure(encoding="utf-8")
import firebase_admin
from firebase_admin import credentials, firestore
from core.database import db as mdb

firebase_admin.initialize_app(credentials.Certificate("serviceAccountKey.json"))
fs = firestore.client()

# ---------------- helpers ----------------
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

def sanitize(o):
    """Deja el objeto JSON/Mongo-safe: datetimes -> iso, NaN -> None, recursivo."""
    if isinstance(o, dict):
        return {k: sanitize(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [sanitize(v) for v in o]
    if isinstance(o, (datetime.datetime, datetime.date)):
        return o.isoformat()
    if isinstance(o, float) and math.isnan(o):
        return None
    if isinstance(o, (str, int, float, bool)) or o is None:
        return o
    return str(o)  # Timestamp, GeoPoint, etc.

def to_iso(v):
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.isoformat()
    return v

MK = ["p_ent", "h_ent", "g_ent", "p_peri", "h_peri", "p_desc", "h_desc", "g_desc"]

def decode_macros(s):
    parts = str(s).split()
    if len(parts) < 8:
        return {"raw": s}
    out = {"raw": s}
    for i, k in enumerate(MK):
        try: out[k] = float(parts[i])
        except: out[k] = None
    return out

def decode_mediciones(s):
    """'116|99|33|...' -> {'raw': str, 'valores': [floats]}. Orden segun el form de Calma."""
    if not s:
        return None
    vals = []
    for tok in str(s).split("|"):
        tok = tok.strip()
        try: vals.append(float(tok))
        except: vals.append(None)
    return {"raw": str(s), "valores": vals}

def decode_respuesta(s):
    """Respuesta mensual 'texto|NOTA|score' o 'texto|NOTA' -> {texto, nota, score, raw}."""
    if s is None:
        return None
    parts = str(s).split("|")
    r = {"raw": str(s), "texto": parts[0].strip() if parts else None, "nota": None, "score": None}
    if len(parts) > 1:
        r["nota"] = parts[1].strip() or None
    if len(parts) > 2:
        try: r["score"] = float(parts[2])
        except: r["score"] = parts[2].strip() or None
    return r

def split_codes(s):
    if not s:
        return []
    return [t.strip() for t in str(s).split("|") if t.strip()]

FOTO_KEYS = ("fotoFrente", "fotoPerfil", "fotoEspalda")

def foto_paths(d):
    out = []
    for k in FOTO_KEYS:
        v = d.get(k)
        if isinstance(v, str) and v:
            out.append({"tipo": k, "path": v})
    return out

def decode_membresia(lst):
    out = []
    if isinstance(lst, list):
        for m in lst:
            if not isinstance(m, dict):
                continue
            out.append({
                "nombre": (m.get("nombre") or "").strip(),
                "inicio": to_iso(m.get("inicio")),
                "fin": to_iso(m.get("fin")),
                "items": split_codes(m.get("items")),
                "items_raw": m.get("items"),
            })
    # ordenar por inicio ascendente cuando se pueda
    out.sort(key=lambda x: str(x.get("inicio") or ""))
    return out

def decode_suplementacion(d):
    if not isinstance(d, dict):
        return None
    protocolos, observaciones = [], None
    for k, v in d.items():
        if k == "observaciones":
            observaciones = v
        else:
            protocolos.append({"fecha": norm_date(k), "codigos": split_codes(v), "raw": v})
    protocolos.sort(key=lambda x: x["fecha"])
    return {"protocolos": protocolos, "observaciones": observaciones}

def map_por_fecha(m, cast=float):
    out = []
    if isinstance(m, dict):
        for k, v in m.items():
            try: val = cast(v)
            except Exception: val = v
            out.append({"fecha": norm_date(k), "valor": val})
        out.sort(key=lambda x: x["fecha"])
    return out

# ---- campos del cuestionario inicial (para copiar tal cual, legibles) ----
FI_CAMPOS = [
    "nombre", "email", "fechaNacimiento", "telefono", "instagram", "direccion",
    "codigoPostal", "profesion", "fuenteCliente", "estatura", "peso", "pesoMaximo",
    "objetivo", "estiloVida", "preparadores", "estadoFormaAnterior",
    "comentariosFotoFormaAnterior", "medicacion", "farmacosActuales", "ejemploDieta",
    "interesEnSuplementacion", "entrenamientoActual", "rutinaInicial", "maquinaria",
    "lesiones", "descanso", "informacionSobreServicios", "interesCBD",
    "comentarioCliente", "formulario", "fechaEnvio",
]

def build_formulario_inicial(fi_doc):
    """formulariosIniciales tiene {fechaUltimoFormulario, '<fecha>': {...}}."""
    if not isinstance(fi_doc, dict):
        return None
    fechas = [k for k, v in fi_doc.items() if isinstance(v, dict)]
    if not fechas:
        return None
    fk = sorted(fechas)[-1]  # el mas reciente
    d = fi_doc[fk]
    out = {"fecha": norm_date(fk)}
    for c in FI_CAMPOS:
        if c in d:
            out[c] = to_iso(d.get(c))
    out["mediciones"] = decode_mediciones(d.get("mediciones"))
    out["fotos"] = foto_paths(d)
    return out

# ---- campos de respuesta del reporte mensual ----
RESP_CAMPOS = ["compromiso", "objetivo", "cumplimientoDieta", "esfuerzoParaCumplirDieta",
               "suplementacion", "cumplimientoEntrenamiento", "cumplimientoCardio", "descanso"]
TEXTO_CAMPOS = ["problemasParaEntrenar", "comentarioCliente", "informacionSobreServicios",
                "nombre", "formulario"]

def build_formularios_mensuales(f_doc):
    out = []
    if not isinstance(f_doc, dict):
        return out
    for fk, val in f_doc.items():
        if not isinstance(val, dict):
            continue
        m = {"fecha": norm_date(fk), "fechaEnvio": to_iso(val.get("fechaEnvio"))}
        peso = val.get("peso")
        m["peso"] = float(peso) if isinstance(peso, (int, float)) else peso
        for c in RESP_CAMPOS:
            if c in val:
                m[c] = decode_respuesta(val.get(c))
        for c in TEXTO_CAMPOS:
            if c in val:
                m[c] = val.get(c)
        m["mediciones"] = decode_mediciones(val.get("mediciones"))
        m["fotos"] = foto_paths(val)
        out.append(m)
    out.sort(key=lambda x: x["fecha"])
    return out

def all_foto_paths(fi, mensuales):
    paths = []
    if fi:
        paths += [f["path"] for f in fi.get("fotos", [])]
    for m in mensuales:
        paths += [f["path"] for f in m.get("fotos", [])]
    return paths

# ---------------- core ----------------
def get_doc(col, email):
    try:
        snap = fs.collection(col).document(email).get()
        return snap.to_dict() if snap.exists else None
    except Exception as e:
        return {"_error": str(e)}

def count_dietas(email):
    try:
        base = fs.collection("dietasUsuarios").document(email)
        return len([d.id for d in base.collection("dietas").select([]).stream()])
    except Exception:
        return None

async def build_and_store(email):
    u = get_doc("usuarios", email) or {}
    fi_doc = get_doc("formulariosIniciales", email)
    f_doc = get_doc("formularios", email)

    fi = build_formulario_inicial(fi_doc)
    mensuales = build_formularios_mensuales(f_doc)

    # link con nuestra DB (si el usuario fue migrado / existe)
    our_user = await mdb.users.find_one({"email": email}, {"_id": 0, "id": 1})
    user_id = our_user["id"] if our_user else None
    client_id = None
    if user_id:
        prof = await mdb.client_profiles.find_one({"user_id": user_id}, {"_id": 0, "id": 1})
        client_id = prof["id"] if prof else None

    doc = {
        "email": email,
        "user_id": user_id,
        "client_id": client_id,
        "nombre": u.get("nombre"),
        "telefono": u.get("telefono"),
        "sexo": u.get("sexo"),
        "ruta_ficha_drive": u.get("rutaFichaDrive"),
        "fin_membresia": to_iso(u.get("finDeMembresia")),
        # perfil decodificado
        "membresia": decode_membresia(u.get("membresia")),
        "suplementacion": decode_suplementacion(u.get("suplementacion")),
        "preferencias": {
            "raw": sanitize(u.get("preferencias")),
            "alergias": split_codes((u.get("preferencias") or {}).get("alergias")),
            "preferencias_codigos": split_codes((u.get("preferencias") or {}).get("preferencias")),
            "dias_entrenamiento": split_codes((u.get("preferencias") or {}).get("diasEntrenamiento")),
            "momento_entreno": (u.get("preferencias") or {}).get("momentoEntrenamientoPreferente"),
            "intraentrenamiento": (u.get("preferencias") or {}).get("intraentrenamiento"),
            "reparto_comidas": (u.get("preferencias") or {}).get("repartoDeComidas"),
        },
        "macros_historial": [
            {"fecha": norm_date(k), **decode_macros(v)}
            for k, v in sorted((u.get("macros") or {}).items(), key=lambda kv: pdate(kv[0]))
        ],
        "pesos": map_por_fecha(u.get("pesos")),
        "porcentajes_grasos": map_por_fecha(u.get("porcentajesGrasos")),
        # cuestionario inicial + reportes mensuales completos
        "formulario_inicial": fi,
        "formularios_mensuales": mensuales,
        # fotos (paths de Storage, para descargar en un paso aparte)
        "foto_paths": all_foto_paths(fi, mensuales),
        "dietas_count": count_dietas(email),
        # verbatim, por si el decode se deja algo
        "raw_firestore": {
            "usuarios": sanitize(u),
            "formulariosIniciales": sanitize(fi_doc),
            "formularios": sanitize(f_doc),
        },
        "source": "calma",
        "imported_at": now_iso(),
    }

    doc = sanitize(doc)  # datetimes -> iso, NaN -> None en todo el documento
    existing = await mdb.calma_raw.find_one({"email": email}, {"_id": 0, "id": 1})
    doc["id"] = existing["id"] if existing else str(uuid.uuid4())
    await mdb.calma_raw.update_one({"email": email}, {"$set": doc}, upsert=True)
    return {
        "email": email, "user_id": bool(user_id),
        "inicial": bool(fi), "mensuales": len(mensuales),
        "membresias": len(doc["membresia"]), "fotos": len(doc["foto_paths"]),
        "macros": len(doc["macros_historial"]),
    }

async def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__); return

    await mdb.calma_raw.create_index("email", unique=True)
    await mdb.calma_raw.create_index("user_id")

    target = args[0]
    limit = None
    if "--limit" in args:
        try: limit = int(args[args.index("--limit") + 1])
        except Exception: limit = None

    if "@" in target:  # un solo cliente
        r = await build_and_store(target.strip().lower())
        print("OK:", r); return

    if target != "all":
        print("Uso: _migrar_calma_raw.py <email> | all [--limit N]"); return

    print("recogiendo lista de emails (union de las 3 colecciones)...")
    emails = set()
    for col in ("usuarios", "formulariosIniciales", "formularios"):
        try:
            emails |= set(d.id for d in fs.collection(col).select([]).stream())
        except Exception as e:
            print(f"  aviso {col}: {e}")
    emails = sorted(e for e in emails if e and "@" in e)
    if limit:
        emails = emails[:limit]
    print(f"emails a procesar: {len(emails)}")

    stats = {"ok": 0, "con_inicial": 0, "con_mensuales": 0, "con_user": 0, "fotos": 0, "errores": 0}
    for i, email in enumerate(emails, 1):
        try:
            r = await build_and_store(email)
            stats["ok"] += 1
            stats["con_inicial"] += 1 if r["inicial"] else 0
            stats["con_mensuales"] += 1 if r["mensuales"] else 0
            stats["con_user"] += 1 if r["user_id"] else 0
            stats["fotos"] += r["fotos"]
            if i % 25 == 0 or i == len(emails):
                print(f"[{i}/{len(emails)}] {email} | ini={r['inicial']} mens={r['mensuales']} fotos={r['fotos']} | acum ok={stats['ok']}")
        except Exception as e:
            stats["errores"] += 1
            print(f"  ERROR {email}: {type(e).__name__}: {e}")

    print("\n===== RESUMEN calma_raw =====")
    for k, v in stats.items():
        print(f"  {k}: {v}")

asyncio.run(main())
