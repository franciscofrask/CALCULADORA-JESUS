"""
Rutas de administración: clientes, dashboard, entrenadores.
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse, Response
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
import asyncio
import uuid
import os

from core.database import db
from core.security import (
    get_admin_user, get_admin_only_user, assert_client_access, hash_password, generate_temp_password,
    decode_token,
)

# Carpeta local con las fotos de progreso importadas de Calma (solo dev).
_FOTOS_CALMA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_fotos_calma")
from routes.notifications import notify
from routes.audit import audit
from models.user import (
    ClientProfile, ClientProfileUpdate, MacrosUpdate, MacroEvaluacion, TrainerAssign, PLAN_CATALOG,
)
from core.cycle import enrich_cycle, compute_cycle
from models.common import FoodSuggestionUpdate, AdminFoodCreate
from calculator import invalidate_foods_cache

router = APIRouter(prefix="/admin", tags=["admin"])

# ==================== REVISIONES DE MACROS (motor v2) ====================
# Dieta reportada que no cuadra con lo recomendado: el motor la deja en
# db.macro_revisiones con status 'pendiente' y aquí la ve/resuelve el staff.

@router.get("/macro-revisiones")
async def list_macro_revisiones(status: str = "pendiente", user = Depends(get_admin_user)):
    """Revisiones de macros pendientes. Admin y trainer las ven todas (coherente con
    que el entrenador ve a todos los clientes)."""
    query: Dict[str, Any] = {"status": status}
    items = await db.macro_revisiones.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)

    # Nombre del cliente en una consulta batch.
    uids = list({i.get("user_id") for i in items if i.get("user_id")})
    users = await db.users.find({"id": {"$in": uids}}, {"_id": 0, "id": 1, "name": 1, "email": 1}).to_list(len(uids) or 1)
    umap = {u["id"]: u for u in users}
    for i in items:
        u = umap.get(i.get("user_id")) or {}
        i["client_name"] = u.get("name") or u.get("email") or "Cliente"
    return {"items": items}


@router.post("/macro-revisiones/{revision_id}/resolver")
async def resolve_macro_revision(revision_id: str, user = Depends(get_admin_user)):
    """Marca una revisión de macros como revisada."""
    r = await db.macro_revisiones.update_one(
        {"id": revision_id},
        {"$set": {"status": "revisada", "resolved_by": user.get("name", user.get("email")),
                  "resolved_at": datetime.now(timezone.utc).isoformat()}}
    )
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Revisión no encontrada")
    return {"success": True}

# ==================== CLIENTS ====================

@router.get("/clients", response_model=List[Dict[str, Any]])
async def get_all_clients(
    plan: Optional[str] = None,
    status: Optional[str] = None,
    trainer_id: Optional[str] = None,
    include_incomplete: bool = False,
    user = Depends(get_admin_user)
):
    """Obtener todos los clientes con filtros opcionales. Con include_incomplete=true añade
    también los usuarios rol client SIN perfil (se registraron pero no completaron el alta)."""
    query = {}
    if plan:
        query["plan"] = plan.lower()
    if status:
        query["status"] = status
    if trainer_id:
        query["trainer_id"] = trainer_id
    # Admin y entrenador ven a TODOS los clientes, incluidos los ya asignados a otro
    # coach (decisión del usuario 21-07). El filtro por coach solo aplica si se pide
    # explícitamente con el parámetro trainer_id.
    es_trainer = user.get("role") == "trainer"

    # Proyección mínima para el listado (los detalles van por /clients/{id}) y usuarios en
    # UNA consulta batch en vez de una por perfil (N+1 que hacía lenta la lista).
    LIST_FIELDS = {"_id": 0, "id": 1, "user_id": 1, "plan": 1, "price": 1, "week": 1,
                   "cycle_start": 1, "status": 1, "trainer_id": 1, "created_at": 1}
    profiles = await db.client_profiles.find(query, LIST_FIELDS).to_list(1000)

    uids = [p["user_id"] for p in profiles]
    users = await db.users.find(
        {"id": {"$in": uids}},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "phone": 1, "role": 1}
    ).to_list(len(uids) or 1)
    umap = {u["id"]: u for u in users}

    result = []
    for profile in profiles:
        user_data = umap.get(profile["user_id"])
        if user_data:
            result.append({**enrich_cycle(profile), "user": user_data})

    # Registros incompletos: solo el admin sin filtros (no tienen plan/estado/coach que filtrar)
    if include_incomplete and not es_trainer and not (plan or status or trainer_id):
        with_profile = {p["user_id"] for p in await db.client_profiles.find({}, {"_id": 0, "user_id": 1}).to_list(5000)}
        orphans = await db.users.find(
            {"role": "client", "deleted_at": None, "id": {"$nin": list(with_profile)}},
            {"_id": 0, "password": 0, "firebase_password_hash": 0, "firebase_password_salt": 0}
        ).to_list(1000)
        for u in orphans:
            result.append({
                "id": None,
                "user_id": u["id"],
                "plan": None,
                "price": None,
                "week": None,
                "status": "registro_incompleto",
                "trainer_id": None,
                "created_at": u.get("created_at"),
                "user": u,
            })

    return result

@router.get("/clients/{client_id}")
async def get_client_detail(client_id: str, user = Depends(get_admin_user)):
    """Obtener detalle completo de un cliente (8 pestañas)."""
    profile = await db.client_profiles.find_one({"id": client_id}, {"_id": 0})
    assert_client_access(user, profile)
    enrich_cycle(profile)

    user_data = await db.users.find_one({"id": profile["user_id"]}, {"_id": 0, "password": 0})
    routines = await db.routines.find({"client_id": client_id}, {"_id": 0}).sort("created_at", -1).to_list(10)
    reports = await db.reports.find({"client_id": client_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
    payments = await db.payments.find({"client_id": client_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
    messages = await db.messages.find(
        {"$or": [{"sender_id": profile["user_id"]}, {"receiver_id": profile["user_id"]}]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    # Por fecha de efecto y, a igualdad, por cuándo se hizo el cambio. Ordenar solo por
    # effective_date dejaba al azar el orden de varios ajustes del MISMO día: el panel del
    # coach podía enseñar primero el cambio más viejo de hoy.
    macro_history = await db.macro_history.find({"client_id": client_id}, {"_id": 0}).sort(
        [("effective_date", -1), ("created_at", -1)]
    ).to_list(500)
    supplement_protocol = await db.supplement_protocols.find_one({"client_id": client_id}, {"_id": 0})

    # Datos rescatados de Calma (staging, solo lectura). Se busca por client_id o user_id.
    # Se excluye raw_firestore (verbatim, muy pesado): la ficha usa los campos decodificados.
    calma_raw = await db.calma_raw.find_one(
        {"$or": [{"client_id": client_id}, {"user_id": profile["user_id"]}]},
        {"_id": 0, "raw_firestore": 0},
    )

    # Nutrition stats: fechas con proyección ligera (sin las comidas, que es lo que pesa)
    # y el top de alimentos calculado EN MongoDB con agregación (antes venían hasta 3000
    # dietas completas a Python solo para contar).
    diets = await db.diets.find(
        {"user_id": profile["user_id"]},
        {"_id": 0, "fecha": 1, "tipo_dia": 1}
    ).sort("fecha", -1).to_list(3000)

    top_rows = await db.diets.aggregate([
        {"$match": {"user_id": profile["user_id"]}},
        {"$project": {"meals": {"$objectToArray": {"$ifNull": ["$comidas", {}]}}}},
        {"$unwind": "$meals"},
        {"$unwind": "$meals.v.alimentos"},
        {"$group": {"_id": "$meals.v.alimentos.nombre", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5},
    ]).to_list(5)
    top_foods = [(r["_id"] or "?", r["count"]) for r in top_rows]

    nutrition_stats = {
        "total_diets": len(diets),
        "recent_diets": [{"fecha": d["fecha"], "tipo_dia": d.get("tipo_dia", "?")} for d in diets[:7]],
        "diet_dates": [{"fecha": d["fecha"], "tipo_dia": d.get("tipo_dia", "?")} for d in diets],
        "top_foods": [{"nombre": n, "count": c} for n, c in top_foods],
    }

    return {
        "profile": profile,
        "user": user_data,
        "routines": routines,
        "reports": reports,
        "payments": payments,
        "messages": messages,
        "macro_history": macro_history,
        "nutrition_stats": nutrition_stats,
        "supplement_protocol": supplement_protocol,
        "calma_raw": calma_raw,
    }


def _sanea_peso(w):
    """Corrige errores de coma en el peso (819 -> 81.9, 51400 -> 51.4)."""
    try:
        w = float(w)
    except (TypeError, ValueError):
        return None
    while w > 1000:
        w /= 1000.0
    if 300 < w <= 1000:
        w /= 10.0
    return round(w, 1) if 25 < w < 300 else None


def _refrescar_casos():
    """Rehace el banco de casos (gemelos) y los indices/perfiles, sin bloquear la
    respuesta: los dos salen del mismo camino, asi que se refrescan juntos."""
    import macro_casos, macro_indices
    asyncio.create_task(macro_casos.refrescar_en_segundo_plano())
    asyncio.create_task(macro_indices.refrescar_en_segundo_plano())


def _delta_vs_propuesta(propuesta, training, rest, peri):
    """Cuanto corrigio el coach la propuesta de la IA, macro a macro. Devuelve solo
    lo que cambio: {} = la acepto tal cual."""
    guardado = {
        "entreno": {"proteina": training.get("protein"), "hidratos": training.get("carbs"), "grasa": training.get("fat")},
        "descanso": {"proteina": rest.get("protein"), "hidratos": rest.get("carbs"), "grasa": rest.get("fat")},
        "perientreno": {"proteina": (peri or {}).get("protein"), "hidratos": (peri or {}).get("carbs")},
    }
    delta = {}
    for bloque, campos in guardado.items():
        prop = (propuesta or {}).get(bloque) or {}
        for campo, valor in campos.items():
            p = prop.get(campo)
            if p is None or valor is None:
                continue
            if round(float(valor) - float(p), 1) != 0:
                delta.setdefault(bloque, {})[campo] = round(float(valor) - float(p), 1)
    return delta


def _contexto_decision(evolucion, reporte):
    """B9: consolida lo que mira el coach (lo que Jesus revisa a mano): ultimo peso
    y fecha, dias desde el pesaje anterior, kg desde el ultimo y desde el inicio, y
    el cumplimiento/comentario del reporte. Para mostrarlo junto a la sugerencia."""
    cd = {}
    pts = [e for e in (evolucion or []) if isinstance(e.get("peso"), (int, float))]
    if pts:
        last = pts[-1]
        cd["peso_actual"] = last["peso"]
        cd["fecha_actual"] = last["fecha"]
        cd["peso_inicial"] = pts[0]["peso"]
        cd["fecha_inicial"] = pts[0]["fecha"]
        cd["delta_inicio"] = round(last["peso"] - pts[0]["peso"], 1)
        if len(pts) >= 2:
            prev = pts[-2]
            cd["peso_anterior"] = prev["peso"]
            cd["fecha_anterior"] = prev["fecha"]
            cd["delta_ultimo"] = round(last["peso"] - prev["peso"], 1)
            try:
                d1 = datetime.strptime(last["fecha"][:10], "%Y-%m-%d")
                d0 = datetime.strptime(prev["fecha"][:10], "%Y-%m-%d")
                cd["dias_desde_anterior"] = (d1 - d0).days
            except (ValueError, TypeError):
                pass
    if reporte:
        cd["cumplimiento_dieta"] = reporte.get("cumplimiento_dieta")
        cd["comentario"] = reporte.get("comentario")
    return cd


@router.post("/macro-casos/reconstruir")
async def reconstruir_macro_casos(user = Depends(get_admin_only_user)):
    """Rehace el banco de casos que usa el agente para buscar clientes gemelos.

    Hay que lanzarlo de vez en cuando (los ajustes y las evaluaciones nuevas no entran
    solos). Es idempotente: borra y reconstruye.
    """
    import macro_casos, macro_indices
    casos = await macro_casos.reconstruir()
    indices = await macro_indices.reconstruir()
    return {"casos": casos, "indices_y_perfiles": indices}


@router.post("/clients/{client_id}/sugerir-ajuste")
async def sugerir_ajuste_macros(client_id: str, user = Depends(get_admin_user)):
    """Agente de re-ajuste de macros (Tarea 1): arma el contexto del cliente y
    propone el siguiente ajuste para que el COACH lo revise/edite/confirme."""
    import macro_agent

    profile = await db.client_profiles.find_one({"id": client_id}, {"_id": 0})
    assert_client_access(user, profile)

    macros_actuales = {
        "entreno": profile.get("macros_training") or {},
        "perientreno": profile.get("macros_periworkout") or {},
        "descanso": profile.get("macros_rest") or {},
    }
    sexo = profile.get("sex") or "hombre"

    raw = await db.calma_raw.find_one(
        {"$or": [{"client_id": client_id}, {"user_id": profile["user_id"]}]},
        {"_id": 0, "macros_historial": 1, "pesos": 1, "formularios_mensuales": 1}) or {}

    # evolucion de peso (calma + macro_history + reports), saneada
    pesos = {}
    for p in (raw.get("pesos") or []):
        w = _sanea_peso(p.get("valor"))
        if w and p.get("fecha"):
            pesos[p["fecha"]] = w
    async for h in db.macro_history.find({"client_id": client_id}, {"_id": 0, "effective_date": 1, "peso": 1, "client_weight": 1}):
        w = _sanea_peso(h.get("peso") if h.get("peso") is not None else h.get("client_weight"))
        if w and h.get("effective_date"):
            pesos[h["effective_date"]] = w
    async for r in db.reports.find({"client_id": client_id}, {"_id": 0, "created_at": 1, "weight": 1}):
        w = _sanea_peso(r.get("weight")); f = (r.get("created_at") or "")[:10]
        if w and f:
            pesos[f] = w
    evolucion = [{"fecha": f, "peso": w} for f, w in sorted(pesos.items())]

    # ultimo reporte (calma formularios_mensuales) + fase
    fm = sorted([x for x in (raw.get("formularios_mensuales") or []) if x.get("fecha")], key=lambda x: x["fecha"])
    reporte = None
    fase = profile.get("goal") or "definicion"
    if fm:
        r = fm[-1]
        gt = lambda k: (r.get(k) or {}).get("texto") if isinstance(r.get(k), dict) else r.get(k)
        reporte = {k: v for k, v in {
            "cumplimiento_dieta": gt("cumplimientoDieta"), "esfuerzo_dieta": gt("esfuerzoParaCumplirDieta"),
            "cumplimiento_entreno": gt("cumplimientoEntrenamiento"), "cardio": gt("cumplimientoCardio"),
            "descanso": gt("descanso"), "objetivo": gt("objetivo"),
            "problemas_entreno": r.get("problemasParaEntrenar"), "comentario": r.get("comentarioCliente"),
            "peso": _sanea_peso(r.get("peso")),
        }.items() if v not in (None, "")}
        ot = (gt("objetivo") or "").lower()
        if "volumen" in ot:
            fase = "volumen"
        elif "defin" in ot:
            fase = "definicion"
    fase = "volumen" if str(fase).lower().startswith("vol") else "definicion"

    # historial de ajustes de ESTA persona (para que el agente aprenda su patron):
    # los importados de Calma + los hechos en la app (estos si traen criterio,
    # evaluacion de la fase y % graso: el paso 1 del modelo predictivo).
    historial = []
    for h in sorted([x for x in (raw.get("macros_historial") or []) if x.get("fecha")], key=lambda x: x["fecha"]):
        historial.append({"fecha": h["fecha"], "peso": pesos.get(h["fecha"]), "macros": {
            "entreno": {"proteina": h.get("p_ent"), "hidratos": h.get("h_ent"), "grasa": h.get("g_ent")},
            "perientreno": {"proteina": h.get("p_peri"), "hidratos": h.get("h_peri")},
            "descanso": {"proteina": h.get("p_desc"), "hidratos": h.get("h_desc"), "grasa": h.get("g_desc")}}})
    async for h in db.macro_history.find({"client_id": client_id}, {"_id": 0}):
        fecha = h.get("effective_date") or (h.get("created_at") or "")[:10]
        if not fecha:
            continue
        historial.append({
            "fecha": fecha,
            "peso": pesos.get(fecha) or _sanea_peso(h.get("client_weight")),
            "porcentaje_graso": h.get("body_fat"),
            "criterio": h.get("criterio"),
            "evaluacion": h.get("evaluacion"),
            # Senal de correccion: si ese ajuste salio de una sugerencia de la IA, si el coach
            # la guardo tal cual o cuanto la corrigio (macro a macro). Se venia guardando desde
            # el 26-07 pero no se le devolvia al agente, asi que tropezaba dos veces con la
            # misma piedra en el mismo cliente.
            "origen": h.get("origen"),
            "correccion_coach": h.get("correccion_coach"),
            "macros": {"entreno": h.get("training") or {}, "perientreno": h.get("peri") or {},
                       "descanso": h.get("rest") or {}},
        })
    historial.sort(key=lambda x: x["fecha"])

    # Memoria de la cartera: el PERFIL de este cliente (motor x respondedor, derivado de
    # su camino), las REGLAS de ajuste de ese perfil y los casos parecidos de otros
    # clientes. Ver backend/macro_indices.py y backend/macro_casos.py.
    import macro_casos, macro_indices
    peso_actual = evolucion[-1]["peso"] if evolucion else _sanea_peso(profile.get("weight"))
    hc_ent = (macros_actuales["entreno"] or {}).get("carbs") or (macros_actuales["entreno"] or {}).get("hidratos")
    ref = {
        "sexo": (sexo or "hombre").lower(), "fase": fase, "peso": peso_actual,
        "body_fat": profile.get("body_fat"), "hc_entreno": hc_ent,
        "hc_entreno_kg": round(hc_ent / peso_actual, 2) if hc_ent and peso_actual else None,
        "cumplimiento": (reporte or {}).get("cumplimiento_dieta"),
    }
    perfil_ix, reglas_perfil, mismo_perfil = None, [], None
    try:
        perfil_ix = await macro_indices.perfil_de(client_id)
        if perfil_ix:
            reglas_perfil = await macro_indices.reglas_de(perfil_ix["perfil"], fase)
            mismo_perfil = {d["client_id"] async for d in db.macro_indices.find(
                {"perfil": perfil_ix["perfil"]}, {"_id": 0, "client_id": 1})}
            mismo_perfil.discard(client_id)
    except Exception:
        pass   # los indices pueden no estar construidos todavia
    try:
        gemelos = await macro_casos.buscar_gemelos(ref, k=8, excluir_client_id=client_id,
                                                   mismo_perfil=mismo_perfil)
    except Exception:
        gemelos = []   # el banco puede no estar construido todavia

    ctx = macro_agent.construir_contexto(
        macros_actuales=macros_actuales, sexo=sexo, fase=fase, evolucion_peso=evolucion,
        reporte=reporte, historial_ajustes=historial,
        biotipo=(profile.get("nivel1") or {}).get("biotype"), porcentaje_graso=profile.get("body_fat"),
        casos_gemelos=macro_casos.formatear_gemelos(gemelos),
        perfil=macro_indices.formatear_para_prompt(perfil_ix, reglas_perfil),
        # P9 del cuestionario: con cuanta mano se le puede ajustar (hambre o saturacion).
        hambre_saturacion=(profile.get("ajustes_macros") or {}).get("hambre_saturacion"))
    out = await macro_agent.sugerir_ajuste(ctx)
    if isinstance(out, dict) and out.get("propuesta"):
        out["guardarrail"] = macro_agent.validar(out["propuesta"], macros_actuales, out.get("avisos", []))
    out["contexto_usado"] = {"fase": fase, "sexo": sexo, "n_pesos": len(evolucion),
                             "n_historial": len(historial), "tiene_reporte": bool(reporte),
                             "n_gemelos": len(gemelos), "n_reglas_perfil": len(reglas_perfil)}
    if perfil_ix:
        out["perfil"] = {
            "etiqueta": perfil_ix.get("perfil"),
            "motor": perfil_ix.get("perfil_motor"),
            "respondedor": perfil_ix.get("perfil_respondedor"),
            "techo_hc": perfil_ix.get("techo_hc"),
            "suelo_hc": perfil_ix.get("suelo_hc"),
            "hc_kg_techo": perfil_ix.get("hc_kg_techo"),
            "indice_hidrato_grasa_techo": perfil_ix.get("indice_hidrato_grasa_techo"),
            "umbral_volumen": perfil_ix.get("umbral_volumen"),
            "umbral_definicion": perfil_ix.get("umbral_definicion"),
            "ratio_recomposicion": perfil_ix.get("ratio_recomposicion"),
        }
    out["contexto_decision"] = _contexto_decision(evolucion, reporte)

    # Toda sugerencia queda registrada. Cuando el coach guarde los macros diremos si
    # la uso tal cual, la corrigio (con el delta) o la ignoro: esa es la senal con la
    # que el agente puede ir aprendiendo.
    if out.get("propuesta"):
        out["sugerencia_id"] = str(uuid.uuid4())
        await db.macro_sugerencias.insert_one({
            "id": out["sugerencia_id"],
            "client_id": client_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "pedida_por": user.get("name", user.get("email", "admin")),
            "macros_actuales": macros_actuales,
            "propuesta": out["propuesta"],
            "cambios": out.get("cambios"),
            "razonamiento": out.get("razonamiento"),
            "avisos": out.get("avisos"),
            "guardarrail": out.get("guardarrail"),
            "confianza": out.get("confianza"),
            "modelo": out.get("_modelo"),
            "contexto_usado": out["contexto_usado"],
            "resultado": "pendiente",     # pendiente | aceptada | corregida
        })
    return out


@router.get("/clients/{client_id}/calma-foto")
async def get_calma_foto(client_id: str, file: str, w: int = 0, user = Depends(get_admin_user)):
    """Sirve una foto de progreso importada de Calma (disco local del backend).

    Auth por cabecera (get_admin_user) + acceso al cliente. El frontend la carga por
    fetch autenticado (blob), no con el token en la URL. Valida que el fichero pertenece
    a este cliente (esta en su fotos_descargadas) y evita path traversal.
    `w` opcional: devuelve un thumbnail JPEG de ese ancho maximo (respeta la orientacion EXIF).
    """
    profile = await db.client_profiles.find_one({"id": client_id}, {"_id": 0, "user_id": 1, "trainer_id": 1})
    assert_client_access(user, profile)
    raw = await db.calma_raw.find_one(
        {"$or": [{"client_id": client_id}, {"user_id": profile["user_id"]}]},
        {"_id": 0, "fotos_descargadas": 1},
    )
    allowed = {f.get("file") for f in (raw or {}).get("fotos_descargadas", [])}
    if file not in allowed:
        raise HTTPException(status_code=404, detail="Foto no encontrada")

    full = os.path.normpath(os.path.join(_FOTOS_CALMA_DIR, file))
    if not full.startswith(_FOTOS_CALMA_DIR) or not os.path.exists(full):
        raise HTTPException(status_code=404, detail="Foto no encontrada")

    if w and w > 0:
        try:
            from PIL import Image, ImageOps
            import io
            img = Image.open(full)
            img = ImageOps.exif_transpose(img)  # respeta la orientación EXIF (fotos de móvil)
            img.thumbnail((w, w * 3))
            buf = io.BytesIO()
            img.convert("RGB").save(buf, "JPEG", quality=80)
            return Response(content=buf.getvalue(), media_type="image/jpeg")
        except Exception:
            pass
    return FileResponse(full)

@router.get("/clients/{client_id}/diet")
async def get_client_diet(client_id: str, fecha: str, user = Depends(get_admin_user)):
    """Dieta de un cliente en una fecha concreta (visor de dietas del admin)."""
    profile = await db.client_profiles.find_one({"id": client_id}, {"_id": 0, "user_id": 1, "trainer_id": 1})
    assert_client_access(user, profile)
    diet = await db.diets.find_one(
        {"user_id": profile["user_id"], "fecha": fecha}, {"_id": 0}
    )
    if not diet:
        raise HTTPException(status_code=404, detail="Sin dieta en esa fecha")
    return diet


@router.put("/clients/{client_id}", response_model=ClientProfile)
async def update_client_admin(client_id: str, data: ClientProfileUpdate, user = Depends(get_admin_user)):
    """Actualizar perfil de cliente (admin)."""
    profile = await db.client_profiles.find_one({"id": client_id})
    assert_client_access(user, profile)

    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    # El coach se cambia solo por PUT /clients/{id}/trainer (ahí viven las reglas de permisos)
    update_data.pop("trainer_id", None)
    if update_data:
        await db.client_profiles.update_one({"id": client_id}, {"$set": update_data})

    updated = await db.client_profiles.find_one({"id": client_id}, {"_id": 0})
    return ClientProfile(**updated)


@router.put("/clients/{client_id}/trainer")
async def assign_client_trainer(client_id: str, data: TrainerAssign, user = Depends(get_admin_user)):
    """Asignar, traspasar o quitar el coach de un cliente.
    Reglas: admin asigna libremente; un coach solo puede asignarse
    a si mismo clientes sin coach; si el cliente ya tiene coach, solo ese coach
    puede traspasarlo a otro o liberarlo."""
    profile = await db.client_profiles.find_one({"id": client_id}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    current_trainer = profile.get("trainer_id") or None
    new_trainer = data.trainer_id or None

    if user.get("role") == "trainer":
        if current_trainer and current_trainer != user["id"]:
            raise HTTPException(status_code=403, detail="Este cliente ya tiene coach; solo su coach actual puede cambiarlo")
        if not current_trainer and new_trainer != user["id"]:
            raise HTTPException(status_code=403, detail="Solo puedes asignarte a ti mismo clientes sin coach")

    trainer_doc = None
    if new_trainer:
        trainer_doc = await db.users.find_one(
            {"id": new_trainer, "deleted_at": None}, {"_id": 0, "id": 1, "name": 1, "role": 1}
        )
        if not trainer_doc or trainer_doc.get("role") not in ["trainer", "admin"]:
            raise HTTPException(status_code=400, detail="Entrenador no válido")

    # trainer_id vive en client_profiles y users: se actualizan juntos
    await db.client_profiles.update_one({"id": client_id}, {"$set": {"trainer_id": new_trainer}})
    await db.users.update_one({"id": profile["user_id"]}, {"$set": {"trainer_id": new_trainer}})

    trainer_name = trainer_doc.get("name") if trainer_doc else None
    if new_trainer != current_trainer:
        await notify(profile["user_id"], "coach",
                     f"Tu coach ahora es {trainer_name}" if trainer_name else "Tu asignación de coach ha cambiado",
                     "/dashboard/messages")
        client_user = await db.users.find_one({"id": profile["user_id"]}, {"_id": 0, "name": 1, "email": 1})
        client_name = (client_user or {}).get("name") or (client_user or {}).get("email") or client_id
        await audit(user, "coach", f"Coach de {client_name}: {trainer_name or 'sin asignar'}")
    return {"ok": True, "trainer_id": new_trainer, "trainer_name": trainer_name}

@router.put("/clients/{client_id}/macros")
async def update_client_macros(client_id: str, data: MacrosUpdate, user = Depends(get_admin_user)):
    """Actualizar macros de un cliente (admin). Marca como override manual."""
    profile = await db.client_profiles.find_one({"id": client_id})
    assert_client_access(user, profile)

    training = data.training.model_dump()
    rest = data.rest.model_dump()
    training["calories"] = training["protein"] * 4 + training["carbs"] * 4 + training["fat"] * 9
    rest["calories"] = rest["protein"] * 4 + rest["carbs"] * 4 + rest["fat"] * 9

    # Also store in alternative format for chatbot compatibility
    training["proteinas"] = training["protein"]
    training["hidratos"] = training["carbs"]
    training["grasas"] = training["fat"]
    rest["proteinas"] = rest["protein"]
    rest["hidratos"] = rest["carbs"]
    rest["grasas"] = rest["fat"]

    set_data = {
        "macros_training": training,
        "macros_rest": rest,
        "macros_source": "manual",
    }

    # Modelo predictivo (paso 1): el % graso del momento del ajuste. Si el coach lo
    # informa, ademas actualiza el perfil (es el dato mas reciente que hay).
    body_fat = data.porcentaje_graso if data.porcentaje_graso is not None else profile.get("body_fat")
    if data.porcentaje_graso is not None:
        set_data["body_fat"] = data.porcentaje_graso

    # El PESO con el que se hace el ajuste (peticion de Jesus 05-08, punto 2.2). Es el del
    # reporte de esta semana, que puede no ser el que tiene el perfil, y va con la fecha del
    # ajuste: "88 kilos con fecha de manana para tener el registro de ese peso, aunque el
    # pesaje sea de hace una semana". Si lo informa, manda y actualiza el perfil.
    peso_ajuste = data.peso if data.peso is not None else profile.get("weight")
    if data.peso is not None:
        set_data["weight"] = data.peso

    if data.peri is not None:
        peri = data.peri.model_dump()
        peri["calories"] = peri["protein"] * 4 + peri["carbs"] * 4
        peri["proteinas"] = peri["protein"]
        peri["hidratos"] = peri["carbs"]
        set_data["macros_periworkout"] = peri

    await db.client_profiles.update_one(
        {"id": client_id},
        {"$set": set_data}
    )
    
    # Date-versioned macros (Calma todosLosMacros): the entry records the date FROM which these
    # macros apply. Default = today. The resolver picks the latest entry with effective_date <=
    # the diet date, so past diets keep the prior version.
    effective_date = data.effective_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    macro_log = {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "previous_training": profile.get("macros_training"),
        "previous_rest": profile.get("macros_rest"),
        "new_training": training,
        "new_rest": rest,
        "training": training,
        "rest": rest,
        "peri": set_data.get("macros_periworkout"),
        "effective_date": effective_date,
        "note": data.note,
        # Modelo predictivo (paso 1): criterio interno del coach y % graso del momento.
        # La `evaluacion` de la fase que abre este ajuste se rellena despues, con
        # PUT .../macro-history/{id}/evaluacion.
        "criterio": data.criterio,
        "body_fat": body_fat,
        "changed_by": user.get("name", user.get("email", "admin")),
        "client_weight": peso_ajuste,
        "peso": peso_ajuste,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    # Si el ajuste viene de una sugerencia de la IA, guardamos cuanto la corrigio el
    # coach: es la senal de aprendizaje (y no le cuesta un clic extra a nadie).
    macro_log["origen"] = "manual"
    if data.sugerencia_id:
        sug = await db.macro_sugerencias.find_one({"id": data.sugerencia_id, "client_id": client_id}, {"_id": 0})
        if sug:
            delta = _delta_vs_propuesta(sug.get("propuesta"), training, rest, set_data.get("macros_periworkout"))
            macro_log["origen"] = "ia" if not delta else "ia_corregida"
            macro_log["sugerencia_id"] = data.sugerencia_id
            macro_log["sugerencia_propuesta"] = sug.get("propuesta")
            macro_log["correccion_coach"] = delta or None
            await db.macro_sugerencias.update_one({"id": data.sugerencia_id}, {"$set": {
                "resultado": "aceptada" if not delta else "corregida",
                "correccion_coach": delta or None,
                "macro_history_id": macro_log["id"],
                "guardado_at": macro_log["created_at"],
                "criterio_coach": data.criterio,
            }})

    await db.macro_history.insert_one(macro_log)

    # El banco de casos (clientes gemelos) se refresca solo con cada ajuste nuevo.
    _refrescar_casos()

    await notify(profile["user_id"], "macros", "Tu coach ha actualizado tus macros", "/dashboard/nutrition", body=data.note)
    client_user = await db.users.find_one({"id": profile["user_id"]}, {"_id": 0, "name": 1, "email": 1})
    await audit(user, "macros", f"Actualizó macros de {(client_user or {}).get('name') or client_id} (manual)")

    return {"training": training, "rest": rest}


@router.put("/clients/{client_id}/macro-history/{entry_id}")
async def update_macro_history_entry(client_id: str, entry_id: str, data: MacrosUpdate, user = Depends(get_admin_user)):
    """Editar una entrada concreta del historial de macros (corrige ese registro; no cambia los macros ACTUALES del cliente)."""
    prof = await db.client_profiles.find_one({"id": client_id}, {"_id": 0, "trainer_id": 1, "user_id": 1})
    assert_client_access(user, prof)
    entry = await db.macro_history.find_one({"id": entry_id, "client_id": client_id}, {"_id": 0})
    if not entry:
        raise HTTPException(status_code=404, detail="Entrada de historial no encontrada")

    training = data.training.model_dump()
    rest = data.rest.model_dump()
    for m in (training, rest):
        m["calories"] = m["protein"] * 4 + m["carbs"] * 4 + m["fat"] * 9
        m["proteinas"] = m["protein"]; m["hidratos"] = m["carbs"]; m["grasas"] = m["fat"]

    set_data = {
        "training": training, "new_training": training,
        "rest": rest, "new_rest": rest,
        "note": data.note,
    }
    if data.criterio is not None:
        set_data["criterio"] = data.criterio
    if data.porcentaje_graso is not None:
        set_data["body_fat"] = data.porcentaje_graso
    if data.effective_date:
        set_data["effective_date"] = data.effective_date
    if data.peri is not None:
        peri = data.peri.model_dump()
        peri["calories"] = peri["protein"] * 4 + peri["carbs"] * 4
        peri["proteinas"] = peri["protein"]; peri["hidratos"] = peri["carbs"]
        set_data["peri"] = peri

    await db.macro_history.update_one({"id": entry_id}, {"$set": set_data})
    return {**entry, **set_data}


@router.put("/clients/{client_id}/macro-history/{entry_id}/evaluacion")
async def evaluar_macro_history_entry(client_id: str, entry_id: str, data: MacroEvaluacion,
                                      user = Depends(get_admin_user)):
    """Modelo predictivo (paso 1): evaluar como salio la fase que abrio este ajuste.

    Se rellena a toro pasado (cuando llega el reporte siguiente): si fue mala, de quien
    fue la culpa (del ajuste = del coach, o del cliente que no cumplio). Es lo que le
    permite al modelo aprender que ajustes funcionaron y cuales no.
    """
    prof = await db.client_profiles.find_one({"id": client_id}, {"_id": 0, "trainer_id": 1, "user_id": 1})
    assert_client_access(user, prof)
    entry = await db.macro_history.find_one({"id": entry_id, "client_id": client_id}, {"_id": 0, "id": 1})
    if not entry:
        raise HTTPException(status_code=404, detail="Entrada de historial no encontrada")

    evaluacion = {
        "resultado": data.resultado,
        # La culpa solo tiene sentido si la fase salio mal.
        "causa": data.causa if data.resultado == "mala" else None,
        "nota": data.nota,
        "evaluado_por": user.get("name", user.get("email", "admin")),
        "evaluado_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.macro_history.update_one({"id": entry_id}, {"$set": {"evaluacion": evaluacion}})
    # Los casos con evaluacion pesan mas al buscar gemelos: refrescamos el banco.
    _refrescar_casos()
    return {"id": entry_id, "evaluacion": evaluacion}


@router.delete("/clients/{client_id}/macro-history/{entry_id}")
async def delete_macro_history_entry(client_id: str, entry_id: str, user = Depends(get_admin_user)):
    """Eliminar una entrada del historial de macros."""
    prof = await db.client_profiles.find_one({"id": client_id}, {"_id": 0, "trainer_id": 1, "user_id": 1})
    assert_client_access(user, prof)
    result = await db.macro_history.delete_one({"id": entry_id, "client_id": client_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entrada de historial no encontrada")
    return {"deleted": entry_id}

@router.post("/clients/{client_id}/calculator/apply")
async def admin_calculator_apply(client_id: str, data: dict, user = Depends(get_admin_user)):
    """Calcular con el MOTOR v2 (mismas reglas que la vista del cliente: tabla +
    modificadores de las preguntas 5-8 + suelos + redondeo) y aplicar al perfil.
    `ajustes` opcional en el body; si no llega, se usan los guardados del cliente."""
    from target_calculator import targets_to_profile_macros
    from macro_engine import calcular_macros_v2, ajustes_to_kwargs, multiplicadores_de
    from core.quiz_store import guardar_quiz_respuestas

    profile = await db.client_profiles.find_one({"id": client_id})
    assert_client_access(user, profile)

    peso = data.get("peso")
    sexo = data.get("sexo")
    bf = data.get("porcentaje_graso")
    objetivo = data.get("objetivo")
    note = data.get("note", "Cálculo automático JG")

    if not all([peso, sexo, bf is not None, objetivo]):
        raise HTTPException(status_code=400, detail="Faltan campos: peso, sexo, porcentaje_graso, objetivo")

    # Mismas reglas que el cliente: ajustes del body (el coach puede tocarlos) o,
    # si no llegan, los últimos guardados en el perfil del cliente.
    ajustes = data.get("ajustes") if isinstance(data.get("ajustes"), dict) else profile.get("ajustes_macros")
    try:
        resultado = calcular_macros_v2(
            float(peso), sexo, float(bf), objetivo,
            farmacologia=bool(profile.get("farmacologia")),
            **ajustes_to_kwargs(ajustes),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    targets = {**resultado["base"], "macros": resultado["macros"],
               "multiplicadores": multiplicadores_de(resultado)}

    profile_macros = targets_to_profile_macros(targets)
    training = profile_macros["macros_training"]
    rest = profile_macros["macros_rest"]
    peri = profile_macros["macros_periworkout"]

    # Aliases for chatbot compatibility
    for m in (training, rest):
        m["proteinas"] = m["protein"]
        m["hidratos"] = m["carbs"]
        m["grasas"] = m["fat"]

    set_data = {
        "weight": float(peso),
        "sex": sexo,
        "body_fat": float(bf),
        "goal": objetivo,
        "macros_training": training,
        "macros_rest": rest,
        "macros_periworkout": peri,
        "macros_source": "auto",
        "macros_multiplicadores": targets["multiplicadores"],
    }
    if ajustes:
        set_data["ajustes_macros"] = ajustes
    await db.client_profiles.update_one({"id": client_id}, {"$set": set_data})

    macro_log = {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "previous_training": profile.get("macros_training"),
        "previous_rest": profile.get("macros_rest"),
        "new_training": training,
        "new_rest": rest,
        "training": training,
        "rest": rest,
        "peri": peri,
        "note": note,
        "changed_by": user.get("name", user.get("email", "admin")),
        "client_weight": float(peso),
        "peso": float(peso),
        "porcentaje_graso": float(bf),
        "sexo": sexo,
        "objetivo": objetivo,
        # Rastro del ajuste (peticion de Jesus 05-08): de que camino salio y por que. Sin
        # `origen`, en el historial no se distingue una decision del coach de un calculo
        # automatico, y el agente los aprendia todos como si fueran criterio suyo.
        "origen": "coach_calculadora",
        "criterio": data.get("criterio"),
        # Explicito, no por el fallback a created_at: asi el coach puede decir desde cuando
        # aplica, igual que en el guardado manual.
        "effective_date": data.get("effective_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "motor": {"version": resultado["version_motor"], "desglose": resultado["desglose"],
                  "ajustes": ajustes},
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.macro_history.insert_one(macro_log)

    # GUARDAR SIEMPRE las respuestas/calculo (calibracion futura)
    await guardar_quiz_respuestas(
        user_id=profile["user_id"], client_id=client_id, origen="coach",
        respuestas=ajustes or {}, resultado=resultado,
        contexto={"peso": float(peso), "porcentaje_graso": float(bf),
                  "sexo": sexo, "objetivo": objetivo},
    )

    await notify(profile["user_id"], "macros", "Tu coach ha actualizado tus macros", "/dashboard/nutrition", body=note)
    client_user = await db.users.find_one({"id": profile["user_id"]}, {"_id": 0, "name": 1, "email": 1})
    await audit(user, "macros", f"Aplicó macros por calculadora a {(client_user or {}).get('name') or client_id}")

    return {"applied": True, "targets": targets, "training": training, "rest": rest, "peri": peri,
            "resultado": {"macros": resultado["macros"], "desglose": resultado["desglose"],
                          "revision": resultado["revision"], "no_aplicados": resultado["no_aplicados"]}}

# ==================== DASHBOARD ====================

VALID_ROLES = {"client", "trainer", "admin"}


STAFF_ROLES = ["admin", "trainer"]


@router.get("/users")
async def admin_list_users(role: Optional[str] = None, staff: bool = False, include_deleted: bool = False,
                           q: Optional[str] = None, user=Depends(get_admin_only_user)):
    """Lista de usuarios para gestión (roles, plan, baja lógica). Con staff=true muestra solo
    el equipo (admin/coach). Excluye los dados de baja salvo include_deleted."""
    query = {}
    if role:
        query["role"] = role
    elif staff:
        query["role"] = {"$in": STAFF_ROLES}
    if not include_deleted:
        query["deleted_at"] = None  # en Mongo, {campo: None} incluye también los que no lo tienen
    if q and q.strip():
        rx = {"$regex": q.strip(), "$options": "i"}
        query["$or"] = [{"email": rx}, {"name": rx}]
    users = await db.users.find(
        query, {"_id": 0, "password": 0, "firebase_password_hash": 0, "firebase_password_salt": 0}
    ).sort("created_at", -1).to_list(5000)
    uids = [u["id"] for u in users]
    profs = await db.client_profiles.find(
        {"user_id": {"$in": uids}}, {"_id": 0, "id": 1, "user_id": 1, "status": 1, "comp_plan": 1}
    ).to_list(5000)
    pmap = {p["user_id"]: p for p in profs}
    out = []
    for u in users:
        p = pmap.get(u["id"]) or {}
        out.append({**u, "profile_id": p.get("id"), "profile_status": p.get("status"),
                    "comp_plan": bool(u.get("comp_plan") or p.get("comp_plan")),
                    "deleted": bool(u.get("deleted_at"))})
    return out


@router.put("/users/{user_id}")
async def admin_update_user(user_id: str, data: dict, user=Depends(get_admin_only_user)):
    """Editar un usuario: nombre, email, teléfono, rol y plan (con opción de cortesía/sin pago)."""
    target = await db.users.find_one({"id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    set_user, set_prof = {}, {}
    if "name" in data and data["name"] is not None:
        set_user["name"] = str(data["name"]).strip()
    if "phone" in data:
        set_user["phone"] = data["phone"]
    if data.get("email") and data["email"].strip().lower() != (target.get("email") or "").lower():
        new_email = data["email"].strip().lower()
        if await db.users.find_one({"email": new_email, "id": {"$ne": user_id}}):
            raise HTTPException(status_code=400, detail="Ese email ya está en uso")
        set_user["email"] = new_email
    if data.get("role"):
        if data["role"] not in VALID_ROLES:
            raise HTTPException(status_code=400, detail=f"Rol inválido. Usa: {', '.join(sorted(VALID_ROLES))}")
        set_user["role"] = data["role"]
    if "plan" in data:
        plan_code = (data["plan"] or "").lower().strip()
        plan_entry = PLAN_CATALOG.get(plan_code)
        if not plan_entry:
            raise HTTPException(status_code=400, detail="Plan no válido")
        if not plan_entry.get("asignable"):
            raise HTTPException(status_code=400, detail=f"El plan '{plan_entry['name']}' no es asignable como membresía")
        set_user["plan"] = plan_code
        set_prof["plan"] = plan_code
        # Cambiar de plan reinicia el ciclo (nueva duración, semana 1).
        if plan_code != (target.get("plan") or ""):
            set_prof["cycle_start"] = datetime.now(timezone.utc).isoformat()
        if data.get("comp_plan"):
            set_user["comp_plan"] = True
            set_prof.update({"comp_plan": True, "price": 0.0, "status": "activo"})
        elif "comp_plan" in data:
            set_user["comp_plan"] = False
            set_prof["comp_plan"] = False
    if set_user:
        await db.users.update_one({"id": user_id}, {"$set": set_user})
    if set_prof:
        await db.client_profiles.update_one({"user_id": user_id}, {"$set": set_prof})
    if set_user or set_prof:
        cambios = ", ".join(sorted(set(list(set_user.keys()) + list(set_prof.keys()))))
        await audit(user, "usuario", f"Editó a {target.get('name') or target.get('email')} ({cambios})")
    return await db.users.find_one(
        {"id": user_id}, {"_id": 0, "password": 0, "firebase_password_hash": 0, "firebase_password_salt": 0})


@router.post("/users/{user_id}/reset-password")
async def admin_reset_password(user_id: str, user=Depends(get_admin_only_user)):
    """Genera una contraseña temporal nueva para un usuario (para cuando la olvida).
    Se devuelve UNA vez; el staff se la pasa al cliente por WhatsApp."""
    target = await db.users.find_one({"id": user_id}, {"_id": 0, "id": 1, "name": 1})
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    temp = generate_temp_password()
    await db.users.update_one({"id": user_id}, {
        "$set": {"password": hash_password(temp)},
        "$unset": {"firebase_password_hash": "", "firebase_password_salt": ""},
    })
    await audit(user, "password", f"Restableció la contraseña de {target.get('name') or user_id}")
    return {"ok": True, "temp_password": temp, "name": target.get("name")}


@router.delete("/users/{user_id}")
async def admin_soft_delete_user(user_id: str, user=Depends(get_admin_only_user)):
    """Baja LÓGICA: no borra datos; el usuario no puede entrar y se oculta de los listados."""
    if user_id == user.get("id"):
        raise HTTPException(status_code=400, detail="No puedes darte de baja a ti mismo")
    target = await db.users.find_one({"id": user_id}, {"_id": 0, "id": 1})
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    await db.users.update_one({"id": user_id}, {"$set": {
        "deleted_at": datetime.now(timezone.utc).isoformat(),
        "deleted_by": user.get("email") or user.get("id"),
    }})
    await db.client_profiles.update_one({"user_id": user_id}, {"$set": {"status": "baja"}})
    await audit(user, "baja", f"Dio de baja al usuario {user_id}")
    return {"ok": True, "soft_deleted": user_id}


@router.post("/users/{user_id}/restore")
async def admin_restore_user(user_id: str, user=Depends(get_admin_only_user)):
    """Reactivar un usuario dado de baja lógica."""
    res = await db.users.update_one({"id": user_id}, {"$set": {"deleted_at": None}, "$unset": {"deleted_by": ""}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    await db.client_profiles.update_one({"user_id": user_id}, {"$set": {"status": "activo"}})
    await audit(user, "alta", f"Reactivó al usuario {user_id}")
    return {"ok": True, "restored": user_id}


@router.get("/dashboard-stats")
async def get_dashboard_stats_v2(user = Depends(get_admin_user)):
    """Métricas reales del negocio con agregación MongoDB."""
    now = datetime.now(timezone.utc)
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total = await db.client_profiles.count_documents({})
    active = await db.client_profiles.count_documents({"status": "activo"})
    inactive = await db.client_profiles.count_documents({"status": {"$in": ["inactivo", "baja", "cancelado"]}})

    # At-risk: active but week >= 3 (calculada) and no report in last 14 days.
    # UNA consulta distinct sobre reports en vez de una por cliente (N+1).
    fourteen_ago = (now - timedelta(days=14)).isoformat()
    active_profiles = await db.client_profiles.find(
        {"status": "activo"},
        {"_id": 0, "id": 1, "plan": 1, "created_at": 1, "cycle_start": 1},
    ).to_list(2000)
    ids = [p["id"] for p in active_profiles if compute_cycle(p)["week"] >= 3]
    with_recent = set(await db.reports.distinct(
        "client_id", {"client_id": {"$in": ids}, "created_at": {"$gte": fourteen_ago}}
    )) if ids else set()
    at_risk = len([i for i in ids if i not in with_recent])

    # Bajas del mes
    bajas_mes = await db.client_profiles.count_documents({
        "status": {"$in": ["baja", "cancelado", "inactivo"]},
    })

    # Plan distribution + MRR en una sola agregación. Cubre TODOS los planes del
    # catálogo (activos, legacy, especiales), no solo los cuatro históricos.
    plans = {}
    mrr = 0
    async for row in db.client_profiles.aggregate([
        {"$match": {"status": "activo"}},
        {"$group": {"_id": "$plan", "count": {"$sum": 1}, "mrr": {"$sum": {"$ifNull": ["$price", 0]}}}},
    ]):
        plans[row["_id"] or "sin_plan"] = row["count"]
        mrr += row["mrr"]

    # Revenue: suma en la base de datos, no en Python
    rev = await db.payments.aggregate([
        {"$match": {"status": "success"}},
        {"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$amount", 0]}}}},
    ]).to_list(1)
    total_revenue = rev[0]["total"] if rev else 0

    return {
        "total_clients": total,
        "active_clients": active,
        "at_risk_clients": at_risk,
        "bajas_mes": bajas_mes,
        "inactive_clients": inactive,
        "plans": plans,
        "mrr": mrr,
        "total_revenue": total_revenue,
    }


@router.get("/upcoming-payments")
async def get_upcoming_payments(user = Depends(get_admin_user)):
    """Clientes con cobro en los próximos 7 días."""
    now = datetime.now(timezone.utc)
    seven_days = now + timedelta(days=7)
    now_iso = now.isoformat()
    seven_iso = seven_days.isoformat()

    profiles = await db.client_profiles.find(
        {
            "status": "activo",
            "next_payment": {"$gte": now_iso, "$lte": seven_iso}
        },
        {"_id": 0}
    ).sort("next_payment", 1).to_list(100)

    # Usuarios en una consulta batch (antes: una por perfil)
    uids = [p["user_id"] for p in profiles]
    users = await db.users.find(
        {"id": {"$in": uids}}, {"_id": 0, "id": 1, "name": 1, "email": 1}
    ).to_list(len(uids) or 1)
    umap = {u["id"]: u for u in users}

    results = []
    for p in profiles:
        user_data = umap.get(p["user_id"])
        results.append({
            "client_id": p["id"],
            "name": user_data.get("name", "?") if user_data else "?",
            "email": user_data.get("email", "") if user_data else "",
            "plan": p.get("plan"),
            "price": p.get("price", 0),
            "next_payment": p.get("next_payment"),
        })

    return {"upcoming": results, "total": len(results)}


@router.get("/todo-semana")
async def get_todo_semana(user = Depends(get_admin_user)):
    """Panel 'por hacer esta semana' del coach (tarea 19): clientes sin macros
    asignados (planes con calculadora personalizada), sin rutina activa (planes con
    rutina), y con el reporte de esta semana pendiente. Cada cliente lleva si está
    'al corriente de pago' para poder priorizar/filtrar."""
    from core.plan_access import has_active_access, plan_grants_feature
    from routes.report_cadence import compute_client_report_state
    from routes.plans import _overrides_by_code
    from models.user import merged_catalog

    now = datetime.now(timezone.utc)
    catalog = merged_catalog(await _overrides_by_code())

    profiles = await db.client_profiles.find(
        {"status": {"$in": ["activo", "pago_pendiente"]}},
        {"_id": 0, "id": 1, "user_id": 1, "plan": 1, "status": 1, "macros_training": 1,
         "stripe_subscription_id": 1, "subscription_status": 1, "access_until": 1,
         "cycle_start": 1, "created_at": 1},
    ).to_list(3000)

    uids = [p["user_id"] for p in profiles if p.get("user_id")]
    users = await db.users.find(
        {"id": {"$in": uids}}, {"_id": 0, "id": 1, "name": 1, "email": 1}
    ).to_list(len(uids) or 1)
    umap = {u["id"]: u for u in users}

    # Rutinas activas y reportes recientes: una consulta cada uno (no N+1).
    active_routine_clients = set(await db.routines.distinct("client_id", {"status": "active"}))
    cutoff = (now - timedelta(days=10)).isoformat()
    recent = await db.reports.find(
        {"created_at": {"$gte": cutoff}}, {"_id": 0, "client_id": 1, "created_at": 1}
    ).to_list(5000)
    last_report: Dict[str, str] = {}
    for r in recent:
        cid, ca = r.get("client_id"), r.get("created_at")
        if cid and (cid not in last_report or ca > last_report[cid]):
            last_report[cid] = ca

    sin_macros, sin_rutina, reporte_pendiente = [], [], []
    for p in profiles:
        u = umap.get(p.get("user_id"), {})
        base = {
            "client_id": p["id"], "name": u.get("name") or "?", "email": u.get("email") or "",
            "plan": p.get("plan"), "al_corriente": has_active_access(p),
        }
        plan_cat = catalog.get((p.get("plan") or "").lower().strip()) or {}
        hab = plan_cat.get("habilitaciones") or {}

        # Sin macros: el plan espera macros del coach (calculadora personalizada) y no los tiene.
        if hab.get("calculadora") == "personalizado" and not p.get("macros_training"):
            sin_macros.append(base)

        # Sin rutina: el plan incluye rutina y el cliente no tiene una activa.
        if plan_grants_feature(p.get("plan"), "rutina") and p["id"] not in active_routine_clients:
            sin_rutina.append(base)

        # Reporte de esta semana pendiente (no enviado dentro de la semana de ciclo).
        state = compute_client_report_state(p, catalog, now)
        if state["due"]:
            reported = last_report.get(p["id"])
            if not (reported and reported >= state["window_start"].isoformat()):
                reporte_pendiente.append({
                    **base, "tipo": state["tipos"][0],
                    "is_open": state["is_open"], "overdue": now > state["window_close"],
                })

    return {
        "sin_macros": sin_macros,
        "sin_rutina": sin_rutina,
        "reporte_pendiente": reporte_pendiente,
        "generated_at": now.isoformat(),
    }


@router.get("/dashboard")
async def get_dashboard_stats(user = Depends(get_admin_user)):
    """Legacy dashboard endpoint (backwards compatible)."""
    stats = await get_dashboard_stats_v2(user)
    return {
        "total_clients": stats["total_clients"],
        "active_clients": stats["active_clients"],
        "plans": stats["plans"],
        "mrr": stats["mrr"],
        "total_revenue": stats["total_revenue"],
        "clients_by_plan": stats["plans"],
    }

# ==================== TRAINERS ====================

@router.get("/trainers")
async def get_trainers(user = Depends(get_admin_user)):
    """Obtener lista de entrenadores."""
    trainers = await db.users.find(
        {"role": {"$in": ["trainer", "admin"]}, "deleted_at": None},
        {"_id": 0, "password": 0}
    ).to_list(100)
    return trainers


# ==================== SUGERENCIAS DE ALIMENTOS ====================
#
# Revisión y aprobación de los alimentos sugeridos por clientes. Al aprobar, el
# alimento se carga en el catálogo (db.foods) con las categorías asignadas.

def _food_doc_from_fields(f: dict, categorias: Optional[str]) -> dict:
    """Construye un documento de db.foods a partir de los campos de una sugerencia/alta."""
    por_unidad = bool(f.get("por_unidad"))
    racion = float(f.get("racion") or 100) or 100.0
    proteinas = float(f.get("proteinas") or 0)
    hidratos = float(f.get("hidratos") or 0)
    grasas = float(f.get("grasas") or 0)
    url = (f.get("url") or "").strip() or None
    return {
        "id": str(uuid.uuid4()),
        "nombre": (f.get("nombre") or "").strip(),
        "categorias": (categorias or "").strip() or None,
        "proteinas": proteinas,
        "hidratos": hidratos,
        "grasas": grasas,
        "racion": racion,
        "unidades": por_unidad,
        "url": url,
        "tiene_macros": any(v > 0 for v in (proteinas, hidratos, grasas)),
        "tags": "",
    }


async def _suggestions_with_client(query: dict) -> List[Dict[str, Any]]:
    """Sugerencias que cumplen `query`, enriquecidas con nombre y correo del cliente."""
    docs = await db.food_suggestions.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    cids = list({d["client_id"] for d in docs})
    profiles = await db.client_profiles.find(
        {"id": {"$in": cids}}, {"_id": 0, "id": 1, "user_id": 1}
    ).to_list(len(cids) or 1)
    uid_by_cid = {p["id"]: p["user_id"] for p in profiles}
    users = await db.users.find(
        {"id": {"$in": list(uid_by_cid.values())}}, {"_id": 0, "id": 1, "name": 1, "email": 1}
    ).to_list(len(uid_by_cid) or 1)
    umap = {u["id"]: u for u in users}
    for d in docs:
        u = umap.get(uid_by_cid.get(d["client_id"]))
        d["client"] = {"name": u.get("name"), "email": u.get("email")} if u else None
        d["photos"] = d.get("photos") or []
    return docs


@router.get("/food-suggestions")
async def list_food_suggestions(status: Optional[str] = None, user = Depends(get_admin_user)):
    """Lista sugerencias de alimentos. `status`: pending | approved | rejected (o vacío = todas)."""
    query = {}
    if status:
        query["status"] = status
    return await _suggestions_with_client(query)


@router.get("/food-suggestions/{suggestion_id}")
async def get_food_suggestion(suggestion_id: str, user = Depends(get_admin_user)):
    """Detalle de una sugerencia concreta."""
    result = await _suggestions_with_client({"id": suggestion_id})
    if not result:
        raise HTTPException(status_code=404, detail="Sugerencia no encontrada")
    return result[0]


@router.put("/food-suggestions/{suggestion_id}")
async def update_food_suggestion(suggestion_id: str, data: FoodSuggestionUpdate, user = Depends(get_admin_user)):
    """Edita los datos de una sugerencia (corrección del admin) y/o asigna categorías.
    No modifica las fotos. Si el alimento ya estaba aprobado, sincroniza el alimento del catálogo."""
    doc = await db.food_suggestions.find_one({"id": suggestion_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Sugerencia no encontrada")

    payload = data.model_dump(exclude_unset=True)
    food = dict(doc.get("food") or {})
    for k in ("nombre", "por_unidad", "racion", "proteinas", "hidratos", "grasas", "url"):
        if k in payload and payload[k] is not None:
            food[k] = payload[k]

    set_fields = {"food": food}
    if "categorias" in payload:
        set_fields["categorias"] = payload["categorias"]
    if "admin_notes" in payload:
        set_fields["admin_notes"] = payload["admin_notes"]

    await db.food_suggestions.update_one({"id": suggestion_id}, {"$set": set_fields})

    # Si ya estaba aprobado, reflejar los cambios en el alimento del catálogo
    if doc.get("status") == "approved" and doc.get("food_id"):
        new_doc = _food_doc_from_fields(food, set_fields.get("categorias", doc.get("categorias")))
        await db.foods.update_one(
            {"id": doc["food_id"]},
            {"$set": {k: v for k, v in new_doc.items() if k != "id"}},
        )
        invalidate_foods_cache()

    await audit(user, "editar", f"Editó la sugerencia de alimento {suggestion_id}")
    return {"ok": True}


@router.post("/food-suggestions/{suggestion_id}/approve")
async def approve_food_suggestion(suggestion_id: str, user = Depends(get_admin_user)):
    """Aprueba la sugerencia: crea el alimento en el catálogo y marca la sugerencia como aprobada."""
    doc = await db.food_suggestions.find_one({"id": suggestion_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Sugerencia no encontrada")
    if doc.get("status") == "approved":
        raise HTTPException(status_code=409, detail="Esta sugerencia ya está aprobada")

    food_doc = _food_doc_from_fields(doc.get("food") or {}, doc.get("categorias"))
    await db.foods.insert_one(food_doc)
    invalidate_foods_cache()

    await db.food_suggestions.update_one(
        {"id": suggestion_id},
        {"$set": {
            "status": "approved",
            "food_id": food_doc["id"],
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "reviewed_by": user["id"],
        }},
    )

    # Avisar al cliente que sugirió el alimento (campanita in-app)
    profile = await db.client_profiles.find_one({"id": doc["client_id"]}, {"_id": 0, "user_id": 1})
    if profile:
        await notify(
            profile["user_id"],
            "alimento",
            f"Tu alimento sugerido '{food_doc['nombre']}' ha sido aprobado y ya está en la calculadora",
            "/dashboard/foods",
        )

    await audit(user, "alta", f"Aprobó el alimento sugerido '{food_doc['nombre']}' ({food_doc['id']})")
    return {"ok": True, "food_id": food_doc["id"]}


@router.post("/food-suggestions/{suggestion_id}/reject")
async def reject_food_suggestion(suggestion_id: str, data: Optional[dict] = None, user = Depends(get_admin_user)):
    """Rechaza la sugerencia. Opcional: {motivo} guardado en las notas del admin."""
    doc = await db.food_suggestions.find_one({"id": suggestion_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Sugerencia no encontrada")

    set_fields = {
        "status": "rejected",
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "reviewed_by": user["id"],
    }
    motivo = (data or {}).get("motivo")
    if motivo:
        set_fields["admin_notes"] = motivo
    await db.food_suggestions.update_one({"id": suggestion_id}, {"$set": set_fields})

    # Avisar al cliente que sugirió el alimento (campanita in-app)
    nombre = (doc.get("food") or {}).get("nombre") or "el alimento"
    profile = await db.client_profiles.find_one({"id": doc["client_id"]}, {"_id": 0, "user_id": 1})
    if profile:
        titulo = f"Tu alimento sugerido '{nombre}' no se ha aprobado"
        if motivo:
            titulo += f". Motivo: {motivo}"
        await notify(profile["user_id"], "alimento", titulo, "/dashboard/foods")

    await audit(user, "editar", f"Rechazó la sugerencia de alimento {suggestion_id}")
    return {"ok": True}


@router.delete("/food-suggestions/{suggestion_id}")
async def delete_food_suggestion(suggestion_id: str, user = Depends(get_admin_user)):
    """Elimina una sugerencia y sus fotos. No borra el alimento del catálogo si ya fue aprobado."""
    doc = await db.food_suggestions.find_one({"id": suggestion_id}, {"_id": 0, "id": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="Sugerencia no encontrada")
    await db.food_suggestion_photos.delete_many({"suggestion_id": suggestion_id})
    await db.food_suggestions.delete_one({"id": suggestion_id})
    await audit(user, "editar", f"Eliminó la sugerencia de alimento {suggestion_id}")
    return {"ok": True}


# ==================== ALTA / EDICIÓN DIRECTA DE ALIMENTOS ====================

@router.post("/foods")
async def admin_create_food(data: AdminFoodCreate, user = Depends(get_admin_user)):
    """Alta directa de un alimento en el catálogo desde el panel admin."""
    if not data.nombre.strip():
        raise HTTPException(status_code=400, detail="El nombre es obligatorio")
    racion = 100.0 if not data.por_unidad else max(float(data.racion or 0), 1.0)
    food_doc = _food_doc_from_fields(
        {**data.model_dump(), "racion": racion}, data.categorias
    )
    await db.foods.insert_one(food_doc)
    invalidate_foods_cache()
    await audit(user, "alta", f"Creó el alimento '{food_doc['nombre']}' ({food_doc['id']})")
    return {"ok": True, "food_id": food_doc["id"]}


@router.put("/foods/{food_id}")
async def admin_update_food(food_id: str, data: FoodSuggestionUpdate, user = Depends(get_admin_user)):
    """Edita un alimento del catálogo (incluye categorías)."""
    existing = await db.foods.find_one({"id": food_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Alimento no encontrado")

    payload = data.model_dump(exclude_unset=True)
    updates: Dict[str, Any] = {}
    for k in ("nombre", "proteinas", "hidratos", "grasas", "url", "categorias"):
        if k in payload and payload[k] is not None:
            updates[k] = payload[k]
    if "por_unidad" in payload and payload["por_unidad"] is not None:
        updates["unidades"] = payload["por_unidad"]
    if "racion" in payload and payload["racion"] is not None:
        updates["racion"] = payload["racion"]
    if any(k in updates for k in ("proteinas", "hidratos", "grasas")):
        p = updates.get("proteinas", existing.get("proteinas") or 0)
        h = updates.get("hidratos", existing.get("hidratos") or 0)
        g = updates.get("grasas", existing.get("grasas") or 0)
        updates["tiene_macros"] = any(float(v or 0) > 0 for v in (p, h, g))

    if not updates:
        return {"ok": True}
    await db.foods.update_one({"id": food_id}, {"$set": updates})
    invalidate_foods_cache()
    await audit(user, "editar", f"Editó el alimento {food_id}")
    return {"ok": True}


@router.delete("/foods/{food_id}")
async def admin_delete_food(food_id: str, user = Depends(get_admin_user)):
    """Elimina un alimento del catálogo (uso excepcional, no recuperable)."""
    res = await db.foods.delete_one({"id": food_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Alimento no encontrado")
    invalidate_foods_cache()
    await audit(user, "baja", f"Eliminó el alimento {food_id}")
    return {"ok": True}
