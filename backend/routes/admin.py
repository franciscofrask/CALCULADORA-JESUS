"""
Rutas de administración: clientes, dashboard, entrenadores.
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
import uuid

from core.database import db
from core.security import get_admin_user, hash_password, generate_temp_password
from routes.notifications import notify
from routes.audit import audit
from models.user import ClientProfile, ClientProfileUpdate, MacrosUpdate, TrainerAssign, PLAN_CATALOG
from core.cycle import enrich_cycle, compute_cycle
from models.common import FoodSuggestionUpdate, AdminFoodCreate
from calculator import invalidate_foods_cache

router = APIRouter(prefix="/admin", tags=["admin"])

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

    # Registros incompletos: solo sin filtros (no tienen plan/estado/coach que filtrar)
    if include_incomplete and not (plan or status or trainer_id):
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
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    enrich_cycle(profile)

    user_data = await db.users.find_one({"id": profile["user_id"]}, {"_id": 0, "password": 0})
    routines = await db.routines.find({"client_id": client_id}, {"_id": 0}).sort("created_at", -1).to_list(10)
    reports = await db.reports.find({"client_id": client_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
    payments = await db.payments.find({"client_id": client_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
    messages = await db.messages.find(
        {"$or": [{"sender_id": profile["user_id"]}, {"receiver_id": profile["user_id"]}]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    macro_history = await db.macro_history.find({"client_id": client_id}, {"_id": 0}).sort("effective_date", -1).to_list(500)
    supplement_protocol = await db.supplement_protocols.find_one({"client_id": client_id}, {"_id": 0})

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
    }

@router.get("/clients/{client_id}/diet")
async def get_client_diet(client_id: str, fecha: str, user = Depends(get_admin_user)):
    """Dieta de un cliente en una fecha concreta (visor de dietas del admin)."""
    profile = await db.client_profiles.find_one({"id": client_id}, {"_id": 0, "user_id": 1})
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
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
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
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
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
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
        "changed_by": user.get("name", user.get("email", "admin")),
        "client_weight": profile.get("weight"),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.macro_history.insert_one(macro_log)

    await notify(profile["user_id"], "macros", "Tu coach ha actualizado tus macros", "/dashboard/nutrition")
    client_user = await db.users.find_one({"id": profile["user_id"]}, {"_id": 0, "name": 1, "email": 1})
    await audit(user, "macros", f"Actualizó macros de {(client_user or {}).get('name') or client_id} (manual)")

    return {"training": training, "rest": rest}


@router.put("/clients/{client_id}/macro-history/{entry_id}")
async def update_macro_history_entry(client_id: str, entry_id: str, data: MacrosUpdate, user = Depends(get_admin_user)):
    """Editar una entrada concreta del historial de macros (corrige ese registro; no cambia los macros ACTUALES del cliente)."""
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
    if data.effective_date:
        set_data["effective_date"] = data.effective_date
    if data.peri is not None:
        peri = data.peri.model_dump()
        peri["calories"] = peri["protein"] * 4 + peri["carbs"] * 4
        peri["proteinas"] = peri["protein"]; peri["hidratos"] = peri["carbs"]
        set_data["peri"] = peri

    await db.macro_history.update_one({"id": entry_id}, {"$set": set_data})
    return {**entry, **set_data}


@router.delete("/clients/{client_id}/macro-history/{entry_id}")
async def delete_macro_history_entry(client_id: str, entry_id: str, user = Depends(get_admin_user)):
    """Eliminar una entrada del historial de macros."""
    result = await db.macro_history.delete_one({"id": entry_id, "client_id": client_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entrada de historial no encontrada")
    return {"deleted": entry_id}

@router.post("/clients/{client_id}/calculator/apply")
async def admin_calculator_apply(client_id: str, data: dict, user = Depends(get_admin_user)):
    """Calcular targets con tablas JG y aplicarlos al perfil del cliente."""
    from target_calculator import calcular_targets, targets_to_profile_macros

    profile = await db.client_profiles.find_one({"id": client_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    peso = data.get("peso")
    sexo = data.get("sexo")
    bf = data.get("porcentaje_graso")
    objetivo = data.get("objetivo")
    note = data.get("note", "Cálculo automático JG")

    if not all([peso, sexo, bf is not None, objetivo]):
        raise HTTPException(status_code=400, detail="Faltan campos: peso, sexo, porcentaje_graso, objetivo")

    try:
        targets = calcular_targets(float(peso), sexo, float(bf), objetivo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    profile_macros = targets_to_profile_macros(targets)
    training = profile_macros["macros_training"]
    rest = profile_macros["macros_rest"]
    peri = profile_macros["macros_periworkout"]

    # Aliases for chatbot compatibility
    for m in (training, rest):
        m["proteinas"] = m["protein"]
        m["hidratos"] = m["carbs"]
        m["grasas"] = m["fat"]

    await db.client_profiles.update_one(
        {"id": client_id},
        {"$set": {
            "weight": float(peso),
            "sex": sexo,
            "body_fat": float(bf),
            "goal": objetivo,
            "macros_training": training,
            "macros_rest": rest,
            "macros_periworkout": peri,
            "macros_source": "auto",
            "macros_multiplicadores": targets["multiplicadores"],
        }}
    )

    macro_log = {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "previous_training": profile.get("macros_training"),
        "previous_rest": profile.get("macros_rest"),
        "new_training": training,
        "new_rest": rest,
        "training": training,
        "rest": rest,
        "note": note,
        "changed_by": user.get("name", user.get("email", "admin")),
        "client_weight": float(peso),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.macro_history.insert_one(macro_log)

    await notify(profile["user_id"], "macros", "Tu coach ha actualizado tus macros", "/dashboard/nutrition")
    client_user = await db.users.find_one({"id": profile["user_id"]}, {"_id": 0, "name": 1, "email": 1})
    await audit(user, "macros", f"Aplicó macros por calculadora a {(client_user or {}).get('name') or client_id}")

    return {"applied": True, "targets": targets, "training": training, "rest": rest, "peri": peri}

# ==================== DASHBOARD ====================

VALID_ROLES = {"client", "trainer", "admin"}


STAFF_ROLES = ["admin", "trainer"]


@router.get("/users")
async def admin_list_users(role: Optional[str] = None, staff: bool = False, include_deleted: bool = False,
                           q: Optional[str] = None, user=Depends(get_admin_user)):
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
async def admin_update_user(user_id: str, data: dict, user=Depends(get_admin_user)):
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
async def admin_reset_password(user_id: str, user=Depends(get_admin_user)):
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
async def admin_soft_delete_user(user_id: str, user=Depends(get_admin_user)):
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
async def admin_restore_user(user_id: str, user=Depends(get_admin_user)):
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
