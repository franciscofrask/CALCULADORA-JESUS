"""
Cadencia de reportes del coach (entregable del catálogo de planes).

El catálogo ("JG - Catálogo de Planes y Membresías") define reportes coach→cliente
con cadencia fija sobre la semana del ciclo de cada cliente:
  - quincenal: se envía el MIÉRCOLES de las semanas pares (2, 4, 6...)
  - mensual:   se envía el VIERNES de las semanas 3, 7, 11...
  - semanal:   cada semana (Premium/6M, por WhatsApp), sin día fijo → límite domingo

El envío real ocurre fuera de la app (ActiveCampaign / WhatsApp); aquí solo se
controla que ocurra: qué toca esta semana, marcarlo como enviado (db.coach_reports)
y alertar (report_overdue) si la fecha pasa sin registrar el envío.

La semana del ciclo se calcula al vuelo con core/cycle.py - no hay cron: las
alertas de vencido se generan al consultar la vista (create_alert ya deduplica).
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from core.calendario_reportes import (
    calendario_del_cliente, dia_de_envio, reporte_de_la_semana, toca_en_la_semana)
from core.cycle import compute_cycle, _parse_dt
from core.database import db
from core.security import get_admin_user, get_current_user
from core.stripe_billing import create_alert
from models.user import merged_catalog
from routes.audit import audit
from routes.notifications import notify
from routes.plans import _overrides_by_code

router = APIRouter(prefix="/admin/report-cadence", tags=["admin-report-cadence"])
client_router = APIRouter(prefix="/reports", tags=["reports"])

# EL CALENDARIO YA NO VIVE AQUI (punto 44 del doc del 07-08). Antes esto era un mapa fijo
# con el dia de cada tipo y una funcion con tres `if` ("quincenal si la semana es par,
# mensual si semana % 4 == 3, semanal siempre"). Los numeros eran los buenos, pero meter un
# plan con otro ritmo era tocar codigo, y el ciclo de Premium no se podia expresar.
#
# Ahora cada plan declara un patron de semanas que se repite, y el contrato de cada cliente
# lo puede pisar: core/calendario_reportes.py. Lo que queda aqui es el nombre visible de
# cada tipo, que si es de la interfaz.
LABEL = {"quincenal": "Reporte quincenal", "mensual": "Reporte mensual",
         "semanal": "Reporte semanal"}
DIA_LABEL = {0: "lunes", 1: "martes", 2: "miércoles", 3: "jueves", 4: "viernes",
             5: "sábado", 6: "domingo"}

# Se mantiene el nombre `REPORT_RULES` con los valores por defecto porque hay codigo y
# tests que lo consultan para saber que tipos existen; el CUANDO ya no sale de aqui.
REPORT_RULES = {
    "quincenal": {"due_weekday": 2, "label": "Reporte quincenal", "due_label": "miércoles"},
    "mensual": {"due_weekday": 4, "label": "Reporte mensual", "due_label": "viernes"},
    "semanal": {"due_weekday": 6, "label": "Reporte semanal", "due_label": "domingo"},
}


def _cal(profile: Dict[str, Any], catalog: Dict[str, Any]) -> Dict[str, Any]:
    """El calendario de este cliente: el de su plan, pisado por lo que diga su contrato."""
    from models.user import codigo_de_plan
    plan = (catalog or {}).get(codigo_de_plan(profile.get("plan"))) or {}
    return calendario_del_cliente(profile, plan)


def _week_window_start(profile: Dict[str, Any], now: datetime) -> datetime:
    """Inicio (00:00 relativo al ancla) de la semana de ciclo en curso del cliente."""
    anchor = _parse_dt(profile.get("cycle_start")) or _parse_dt(profile.get("created_at")) or now
    weeks_elapsed = max(0, (now - anchor).days) // 7
    return anchor + timedelta(days=weeks_elapsed * 7)


def _due_date_in_window(window_start: datetime, due_weekday: int) -> datetime:
    """Fecha del weekday pedido dentro de la ventana de 7 días de la semana de ciclo."""
    offset = (due_weekday - window_start.weekday()) % 7
    return window_start + timedelta(days=offset)


@router.get("")
async def get_report_cadence(user=Depends(get_admin_user)):
    """Reportes de coach que tocan esta semana (por cliente activo y tipo), con su
    estado: pendiente / enviado / vencido. Genera alertas report_overdue al detectar
    vencidos (deduplicadas a 7 días)."""
    now = datetime.now(timezone.utc)
    catalog = merged_catalog(await _overrides_by_code())

    profiles = await db.client_profiles.find(
        {"status": "activo"},
        {"_id": 0, "id": 1, "user_id": 1, "plan": 1, "cycle_start": 1, "created_at": 1},
    ).to_list(2000)

    # Nombres/emails en una sola consulta.
    user_ids = [p["user_id"] for p in profiles if p.get("user_id")]
    users = await db.users.find(
        {"id": {"$in": user_ids}}, {"_id": 0, "id": 1, "name": 1, "email": 1}
    ).to_list(len(user_ids) or 1)
    users_by_id = {u["id"]: u for u in users}

    items: List[Dict[str, Any]] = []
    keys = []  # (client_id, tipo, due_date_iso) para buscar los envíos en bloque
    for p in profiles:
        plan = catalog.get((p.get("plan") or "").lower().strip())
        if not plan:
            continue
        reportes = (plan.get("habilitaciones") or {}).get("reportes") or []
        if not reportes:
            continue
        cycle = compute_cycle(p, now)
        window_start = _week_window_start(p, now)
        u = users_by_id.get(p.get("user_id"), {})
        # Que le toca a ESTE cliente esta semana, segun el calendario de su plan y de su
        # contrato (punto 44). Antes se recorrian los tipos del plan aplicando una regla
        # fija; ahora el patron ya dice cual toca, si es que toca alguno.
        cal = _cal(p, catalog)
        tipo = reporte_de_la_semana(cal, cycle["week"])
        for tipo in ([tipo] if tipo else []):
            due = _due_date_in_window(window_start, dia_de_envio(cal, tipo))
            due_iso = due.date().isoformat()
            rule = {"label": LABEL.get(tipo, tipo),
                    "due_label": DIA_LABEL.get(dia_de_envio(cal, tipo), "domingo")}
            keys.append((p["id"], tipo, due_iso))
            items.append({
                "client_id": p["id"],
                "client_name": u.get("name"),
                "client_email": u.get("email"),
                "plan": plan.get("code"),
                "plan_name": plan.get("name"),
                "tipo": tipo,
                "tipo_label": rule["label"],
                "due_label": rule["due_label"],
                "week": cycle["week"],
                "cycle_number": cycle["cycle_number"],
                "due_date": due_iso,
            })

    # Estado de envío en una sola consulta.
    sent_docs = await db.coach_reports.find(
        {"$or": [{"client_id": c, "tipo": t, "due_date": d} for c, t, d in keys]},
        {"_id": 0},
    ).to_list(len(keys) or 1) if keys else []
    sent_by_key = {(d["client_id"], d["tipo"], d["due_date"]): d for d in sent_docs}

    today_iso = now.date().isoformat()
    for item in items:
        sent = sent_by_key.get((item["client_id"], item["tipo"], item["due_date"]))
        if sent:
            item["status"] = "enviado"
            item["sent_at"] = sent.get("sent_at")
            item["sent_by"] = sent.get("sent_by_name")
        elif item["due_date"] < today_iso:
            item["status"] = "vencido"
            await create_alert(
                item["client_id"], "report_overdue",
                f"{item['tipo_label']} vencido",
                f"El {item['tipo_label'].lower()} de {item['client_name'] or 'cliente'} "
                f"tocaba el {item['due_label']} {item['due_date']} y no está marcado como enviado.",
                severity="warning",
            )
        else:
            item["status"] = "pendiente"

    # Vencidos primero, luego pendientes por fecha, enviados al final.
    order = {"vencido": 0, "pendiente": 1, "enviado": 2}
    items.sort(key=lambda i: (order[i["status"]], i["due_date"], i["client_name"] or ""))
    return {"week_of": today_iso, "items": items}


# ==================== CLIENTE: recordatorio de reporte pendiente ====================

_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _fecha_es(dt: datetime) -> str:
    return f"{_DIAS[dt.weekday()]} {dt.day} {_MESES[dt.month - 1]}"


def _client_deadline(tipo: str, due: datetime, window_start: datetime):
    """Plazo de respuesta del cliente según el catálogo: quincenal → jueves 20:00
    (día siguiente al envío del miércoles); mensual → lunes siguiente al viernes
    de envío ("lunes de la semana 4"); semanal → fin de la semana de ciclo."""
    if tipo == "quincenal":
        deadline = (due + timedelta(days=1)).replace(hour=20, minute=0, second=0, microsecond=0)
        return deadline, f"{_fecha_es(deadline)} a las 20:00"
    if tipo == "mensual":
        deadline = (due + timedelta(days=3)).replace(hour=23, minute=59, second=0, microsecond=0)
        return deadline, _fecha_es(deadline)
    deadline = (window_start + timedelta(days=6)).replace(hour=23, minute=59, second=0, microsecond=0)
    return deadline, _fecha_es(deadline)


# ==================== Ventana de envío del cliente (viernes -> lunes 6:00) ====================
#
# TODOS los reportes del cliente se recogen en el fin de semana de la semana de ciclo
# en la que tocan: la ventana abre el VIERNES 00:00 y cierra el LUNES 06:00. Fuera de
# ella el envío se bloquea ("espera a la semana que viene"). Horas en UTC (como el
# resto del módulo); se podrían pasar a Europe/Madrid más adelante.


def _submission_window(window_start: datetime):
    """(apertura, cierre) de la ventana de envío: viernes 00:00 -> lunes 06:00."""
    friday = _due_date_in_window(window_start, 4).replace(hour=0, minute=0, second=0, microsecond=0)
    close = (friday + timedelta(days=3)).replace(hour=6, minute=0, second=0, microsecond=0)
    return friday, close


def _principal_label(tipos: List[str]) -> str:
    """Etiqueta del reporte más relevante que toca (mensual > quincenal > semanal)."""
    for t in ("mensual", "quincenal", "semanal"):
        if t in tipos:
            return LABEL[t]
    return "reporte"


def compute_client_report_state(profile: Dict[str, Any], catalog: Dict[str, Any], now: datetime) -> Dict[str, Any]:
    """Estado del reporte del cliente esta semana de ciclo: qué tipos tocan y la
    ventana de envío (abierta/cerrada). Compartido por /reports/due y POST /reports."""
    cycle = compute_cycle(profile, now)
    window_start = _week_window_start(profile, now)
    # El calendario de su plan y de su contrato (punto 44), no una regla fija.
    cal = _cal(profile, catalog)
    tipo = reporte_de_la_semana(cal, cycle["week"])
    tipos = [tipo] if tipo else []
    win_open, win_close = _submission_window(window_start)
    return {
        "cycle": cycle,
        "window_start": window_start,
        "tipos": tipos,
        # Cuanto dura su ciclo y desde que semana entra: del contrato, no un supuesto.
        "ciclo_semanas": cal.get("duracion_semanas"),
        "semana_de_entrada": cal.get("semana_de_entrada"),
        "due": bool(tipos),
        "window_open": win_open,
        "window_close": win_close,
        "is_open": bool(tipos) and win_open <= now <= win_close,
    }


@client_router.get("/due")
async def get_my_due_report(user=Depends(get_current_user)):
    """Estado del reporte del cliente esta semana (para el banner del dashboard y el
    formulario): qué tipos tocan y la ventana de envío (viernes 00:00 -> lunes 06:00).
    Cuando la ventana ABRE crea la notificación de la campanita (una por semana de
    ciclo). Devuelve {items: [], window: {...}}."""
    profile = await db.client_profiles.find_one(
        {"user_id": user["id"]},
        {"_id": 0, "id": 1, "plan": 1, "status": 1, "cycle_start": 1, "created_at": 1},
    )
    if not profile or profile.get("status") != "activo":
        return {"items": [], "window": None}

    catalog = merged_catalog(await _overrides_by_code())
    now = datetime.now(timezone.utc)
    state = compute_client_report_state(profile, catalog, now)

    if not state["due"]:
        return {"items": [], "window": {"due": False, "is_open": False}}

    win_open, win_close = state["window_open"], state["window_close"]
    # ¿Ya subió un reporte dentro de esta semana de ciclo?
    submitted = await db.reports.find_one(
        {"client_id": profile["id"], "created_at": {"$gte": state["window_start"].isoformat()}},
        {"_id": 0, "id": 1},
    )
    label = _principal_label(state["tipos"])
    closes_label = f"{_fecha_es(win_close)} a las 6:00"
    opens_label = _fecha_es(win_open)
    window = {
        "due": True,
        "is_open": state["is_open"],
        "submitted": bool(submitted),
        "opens_at": win_open.isoformat(),
        "closes_at": win_close.isoformat(),
        "opens_label": opens_label,
        "closes_label": closes_label,
        "tipo_label": label,
        # Los tipos en crudo: el formulario los necesita porque no pide lo mismo en el
        # quincenal que en el mensual (las medidas solo van en el mensual, parte 7.3).
        "tipos": state["tipos"],
    }

    items = []
    if not submitted:
        for tipo in state["tipos"]:
            rule = REPORT_RULES[tipo]
            items.append({
                "tipo": tipo,
                "tipo_label": rule["label"],
                "deadline": win_close.isoformat(),
                "deadline_label": closes_label,
                "overdue": now > win_close,
                "is_open": state["is_open"],
                "opens_label": opens_label,
            })

        # Campanita cuando la ventana está ABIERTA (aviso del viernes, tarea 11+13).
        # Una sola por semana de ciclo.
        if state["is_open"]:
            title = f"Ya puedes rellenar tu {label.lower()}: tienes hasta el {closes_label}"
            already = await db.notifications.find_one({
                "user_id": user["id"], "type": "reporte",
                "created_at": {"$gte": state["window_start"].isoformat()},
                "title": {"$regex": "^Ya puedes rellenar tu"},
            }, {"_id": 0, "id": 1})
            if not already:
                await notify(user["id"], "reporte", title, "/dashboard/reports")

    return {"items": items, "window": window}


@router.post("/mark")
async def mark_report_sent(data: Dict[str, Any] = Body(...), user=Depends(get_admin_user)):
    """Marca (o desmarca con enviado=false) un reporte de coach como enviado."""
    client_id = (data.get("client_id") or "").strip()
    tipo = (data.get("tipo") or "").strip()
    due_date = (data.get("due_date") or "").strip()
    enviado = data.get("enviado", True)
    if not client_id or tipo not in REPORT_RULES or not due_date:
        raise HTTPException(status_code=400, detail="client_id, tipo y due_date son requeridos")

    profile = await db.client_profiles.find_one({"id": client_id}, {"_id": 0, "id": 1})
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    key = {"client_id": client_id, "tipo": tipo, "due_date": due_date}
    if enviado:
        await db.coach_reports.update_one(
            key,
            {"$set": {**key, "sent_at": datetime.now(timezone.utc).isoformat(),
                      "sent_by": user["id"], "sent_by_name": user.get("name")}},
            upsert=True,
        )
        # Resuelve la alerta de vencido si existía.
        await db.alerts.update_many(
            {"client_id": client_id, "type": "report_overdue", "resolved": False},
            {"$set": {"resolved": True, "resolved_at": datetime.now(timezone.utc).isoformat()}},
        )
        await audit(user, "reporte", f"Marcó enviado el reporte {tipo} ({due_date}) del cliente {client_id}")
    else:
        await db.coach_reports.delete_one(key)
        await audit(user, "reporte", f"Desmarcó el reporte {tipo} ({due_date}) del cliente {client_id}")
    return {"ok": True, "enviado": bool(enviado)}
