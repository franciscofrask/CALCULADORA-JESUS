"""
Los cuatro paneles del doc del 19-08 (bloque 12): Dirección, Entrenador, Operaciones
y Soporte.

La regla de oro del doc: «cada número lleva a su lista de nombres». Por eso ningún
bloque devuelve un conteo a secas: siempre va la lista de clientes detrás, para que
quien mira el panel pueda abrir el número y ver QUIÉNES son. Y «de cada lista se
puede asignar tarea»: eso lo hace el front contra POST /admin/tareas, aquí no se
duplica.

Lo que el doc pide y HOY no llega a la app (GHL, la publicidad, ActiveCampaign) no se
inventa: cada panel devuelve un bloque `sin_conectar` que dice qué falta y por qué,
para que el hueco se vea en pantalla en vez de desaparecer en silencio.

Dinero solo para el admin (misma regla que routes/pagos_historicos.py): el panel de
Dirección va con get_admin_only_user; el resto los ve también el entrenador.
"""
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from core.cycle import compute_cycle
from core.database import db
from core.datos_dudosos import datos_imposibles
from core.plan_access import dias_hasta_la_revision, estado_de_acceso, plan_grants_feature
from core.security import get_admin_only_user, get_admin_user
from core.sin_futuro import hasta_hoy
from core.tiempo import a_madrid, hoy_madrid
from models.user import codigo_de_plan, merged_catalog
from routes.admin import _fuera_el_equipo
from routes.pagos_historicos import SIN_COPIAS, SOLO_DINERO
from routes.plans import _overrides_by_code
from routes.report_cadence import compute_client_report_state

router = APIRouter(prefix="/admin/paneles", tags=["paneles"])

_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

# Semanas que tiene un mes de media (365.25 / 12 / 7). Es lo que convierte un precio
# por ciclo de N semanas en un "al mes" comparable entre planes.
SEMANAS_POR_MES = 4.345


# ==================== La semana de negocio y las fechas en cristiano ====================

def _semana_es(hoy: Optional[date] = None) -> (date, date):
    """(lunes, domingo) de la semana de negocio: de lunes a domingo EN HORA DE ESPAÑA.

    Se calcula sobre hoy_madrid() y no sobre el día del servidor: entre las 00:00 y las
    02:00 de Madrid el servidor todavía va por ayer, y esa diferencia ya mordió tres
    veces en otros contadores.
    """
    hoy = hoy or hoy_madrid()
    lunes = hoy - timedelta(days=hoy.weekday())
    return lunes, lunes + timedelta(days=6)


def _fecha_de(iso: Any) -> Optional[date]:
    """La fecha (solo día) de un ISO guardado en Mongo, o None si no se entiende."""
    s = str(iso or "")[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _label_dia(d: Optional[date]) -> Optional[str]:
    """"lunes 25 ago": el día como se lee en el panel, no un ISO."""
    if not d:
        return None
    return f"{_DIAS[d.weekday()]} {d.day} {_MESES[d.month - 1]}"


def _label_rango(desde: date, hasta: date) -> str:
    """"25 ago - 31 ago" para las cabeceras de la previsión por semanas."""
    return f"{desde.day} {_MESES[desde.month - 1]} - {hasta.day} {_MESES[hasta.month - 1]}"


def _dias_desde(iso: Any, now: datetime) -> Optional[int]:
    """Días transcurridos desde un ISO, o None si no hay fecha o no se entiende."""
    d = a_madrid(iso)
    if not d:
        return None
    return max(0, ((a_madrid(now) or now).date() - d.date()).days)


# ==================== Cargas compartidas (sin N+1) ====================

# Todo lo que algún panel necesita del perfil, en UNA proyección compartida: cada
# endpoint carga los perfiles una sola vez y el resto sale de mapas en memoria.
_PROY_PERFIL = {
    "_id": 0, "id": 1, "user_id": 1, "plan": 1, "status": 1, "trainer_id": 1,
    "cycle_start": 1, "created_at": 1, "current_period_end": 1,
    "stripe_subscription_id": 1, "subscription_status": 1,
    "renovacion_importe_prevision": 1, "reporte_aplazado_hasta": 1,
    "reporte_aplazado_nota": 1, "reporte_aplazado_tipo": 1, "aplazamientos_seguidos": 1,
    "ultimo_ajuste": 1, "ultimo_reporte": 1, "height": 1, "goal": 1,
    "ultimo_contacto_externo": 1,
    # Lo que mira `datos_imposibles` (tarea 1.4): sin estos campos en la proyeccion, la
    # edad 5 de Juan o el peso de 1 kg se leerian como "falta" y la lista saldria vacia
    # en silencio, que es justo el fallo que esta tarea viene a destapar.
    "weight": 1, "age": 1, "body_fat": 1, "sex": 1,
    # Los tres campos con los que el contrato puede pisar el calendario del plan
    # (compute_client_report_state los lee del perfil).
    "calendario_reportes": 1, "ciclo_semanas": 1, "semana_de_entrada": 1,
}


async def _activos_con_usuarios() -> (List[Dict[str, Any]], Dict[str, Dict[str, Any]]):
    """Los clientes activos (fuera del equipo) y sus usuarios, en dos consultas.

    El filtro del equipo es el mismo de /admin/stats: si aquí se contara distinto, el
    panel enseñaría dos totales que no cuadran en la misma pantalla.
    """
    profiles = await db.client_profiles.find(
        {**await _fuera_el_equipo(), "status": "activo"}, _PROY_PERFIL).to_list(3000)
    uids = [p["user_id"] for p in profiles if p.get("user_id")]
    users = await db.users.find(
        {"id": {"$in": uids}},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "phone": 1, "last_seen": 1},
    ).to_list(len(uids) or 1)
    return profiles, {u["id"]: u for u in users}


def _plan_de(catalogo: Dict[str, Any], p: Dict[str, Any]) -> Dict[str, Any]:
    """La entrada del catálogo del plan de este perfil, resolviendo alias ("CalMa")."""
    return catalogo.get(codigo_de_plan(p.get("plan"))) or {}


def _plan_lleva_entrenador(plan: Dict[str, Any]) -> bool:
    """True si el plan incluye entrenador detrás (habilitaciones.acompanamiento).

    Es el criterio de la casa para saber si un plan lleva acompañamiento: `merged_catalog`
    completa `acompanamiento` en todas las entradas (solo_app | con_entrenador |
    con_entrenador_y_llamadas). ELM y Mantenimiento son solo_app: sus clientes no tienen
    entrenador QUE ASIGNAR, así que contarlos como «sin entrenador» era inflar la lista
    con gente que está exactamente como su plan manda (P64, doc 23-08: 82 donde había ~5).
    Un plan que no está en el catálogo sale como solo_app y no cuenta: si no se sabe qué
    incluye, no se le apunta trabajo a nadie."""
    hab = plan.get("habilitaciones") or {}
    return (hab.get("acompanamiento") or "solo_app") != "solo_app"


def _fila(p: Dict[str, Any], u: Optional[Dict[str, Any]], plan: Dict[str, Any]) -> Dict[str, Any]:
    """La fila básica que llevan todas las listas: quién es y de qué plan."""
    return {
        "client_id": p["id"],
        "name": (u or {}).get("name") or "?",
        "plan": codigo_de_plan(p.get("plan")),
        "plan_nombre": plan.get("name") or p.get("plan") or "",
    }


async def _ultimo_pago_por_email(emails: List[str]) -> Dict[str, Dict[str, Any]]:
    """El último cobro REAL de cada email, en una sola agregación.

    Mismos filtros obligatorios que routes/pagos_historicos.py: sin las copias
    (duplicado_de) y solo lo que fue dinero (es_dinero != false). Sin ellos, un evento
    de "intento de cobro" o una factura duplicada inflaría la previsión.
    """
    if not emails:
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    cursor = db.pagos_historicos.aggregate([
        {"$match": {**SIN_COPIAS, **SOLO_DINERO,
                    "email": {"$in": emails}, "importe": {"$gt": 0}}},
        {"$sort": {"fecha": 1}},
        {"$group": {"_id": "$email",
                    "importe": {"$last": "$importe"}, "fecha": {"$last": "$fecha"}}},
    ])
    async for doc in cursor:
        out[doc["_id"]] = doc
    return out


def _importe_renovacion(p: Dict[str, Any], plan: Dict[str, Any],
                        pago: Optional[Dict[str, Any]]) -> (float, bool):
    """Cuánto se espera que pague este cliente al renovar. Devuelve (importe, es_a_mano).

    La cascada, en orden de confianza:
      (a) `renovacion_importe_prevision` en el perfil: lo puso una persona a mano, y ahí
          van también los que pagan por transferencia. Manda sobre todo lo demás.
      (b) Su último cobro real (> 0) en pagos_historicos: lo que pagó la última vez es la
          mejor pista de lo que va a pagar, sobre todo en los legacy con precio por
          antigüedad (un gold puede pagar 450 o 847). Se usa tal cual, sin adivinar si
          era "razonable": si no lo es, para eso está el ajuste a mano de (a).
      (c) El `precio` del catálogo de su plan: el que nunca ha pagado por la app (alta
          manual, importado) al menos sale con el precio de tarifa, no con un 0.
    """
    a_mano = p.get("renovacion_importe_prevision")
    if isinstance(a_mano, (int, float)) and not isinstance(a_mano, bool):
        return round(float(a_mano), 2), True
    if pago and float(pago.get("importe") or 0) > 0:
        return round(float(pago["importe"]), 2), False
    return round(float(plan.get("precio") or 0), 2), False


def _estado_renovacion(p: Dict[str, Any], plan: Dict[str, Any], es_a_mano: bool) -> str:
    """"confirmado" si renueva solo (Stripe activo o el plan renueva automático),
    "a_mano" si el importe lo fijó una persona, "por_confirmar" el resto."""
    if es_a_mano:
        return "a_mano"
    stripe_activo = bool(p.get("stripe_subscription_id")) and \
        (p.get("subscription_status") or "").lower() == "active"
    if stripe_activo or (plan.get("renovacion") or {}).get("automatica"):
        return "confirmado"
    return "por_confirmar"


def _fila_renovacion(p: Dict[str, Any], u: Optional[Dict[str, Any]], plan: Dict[str, Any],
                     pago: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Fila básica + lo que hace falta para hablar de su renovación: importe, estado
    y la fecha en la que se le acaba lo pagado."""
    importe, es_a_mano = _importe_renovacion(p, plan, pago)
    fecha = _fecha_de(p.get("current_period_end"))
    return {
        **_fila(p, u, plan),
        "importe": importe,
        "estado": _estado_renovacion(p, plan, es_a_mano),
        "fecha": fecha.isoformat() if fecha else None,
        "fecha_label": _label_dia(fecha),
    }


def _eur_mes(importe: float, plan: Dict[str, Any]) -> float:
    """El importe de ciclo de este cliente, normalizado a euros AL MES.

    Sumar importes de ciclo tal cual mezcla trimestres con meses y la cifra no
    significa nada (ya pasó con el MRR del panel viejo). La normalización:
    importe * (4.345 / semanas del ciclo de cobro). Si el plan no declara
    billing_cycle_weeks, se mira el periodo del primer precio del catálogo; y si
    tampoco, se trata como mensual, que es el caso por defecto de la casa.
    """
    semanas = plan.get("billing_cycle_weeks")
    if semanas:
        return importe * SEMANAS_POR_MES / float(semanas)
    periodo = str(((plan.get("precios") or [{}])[0] or {}).get("periodo") or "").lower()
    if "trimestre" in periodo or "12 semanas" in periodo:
        return importe / 3.0
    if "año" in periodo or "ano" in periodo or "anual" in periodo:
        return importe / 12.0
    return importe


async def _origenes_de_leads(now: datetime) -> Dict[str, Any]:
    """Los leads de las últimas 4 semanas, agrupados por origen (newsletter,
    publicidad, referido...). El dato entra por el webhook de GHL: si GHL no manda,
    aquí sale cero y el panel lo dice en vez de esconderlo."""
    desde = (now - timedelta(days=28)).isoformat()
    grupos: Dict[str, int] = {}
    ultimo = None
    async for l in db.leads.find({"created_at": {"$gte": desde}},
                                 {"_id": 0, "source": 1, "origen_detalle": 1, "created_at": 1}):
        # La atribución fina si el webhook la trajo (anuncio, IG orgánico...); si no,
        # la fuente gorda de siempre.
        clave = l.get("origen_detalle") or l.get("source") or "sin origen"
        grupos[clave] = grupos.get(clave, 0) + 1
        if not ultimo or (l.get("created_at") or "") > ultimo:
            ultimo = l.get("created_at")
    if not ultimo:
        doc = await db.leads.find_one({}, {"_id": 0, "created_at": 1},
                                      sort=[("created_at", -1)])
        ultimo = (doc or {}).get("created_at")
    return {
        "por_origen": sorted([{"origen": k, "n": v} for k, v in grupos.items()],
                             key=lambda x: -x["n"]),
        "total": sum(grupos.values()),
        "ultimo_lead": ultimo,
    }


# ==================== 1) Dirección ====================

@router.get("/direccion")
async def panel_direccion(user=Depends(get_admin_only_user)):
    """El panel de Dirección: lo que entra esta semana, la cartera, altas y bajas,
    la factura del mes y la previsión a cuatro semanas. Solo admin: es dinero."""
    now = datetime.now(timezone.utc)
    catalogo = merged_catalog(await _overrides_by_code())
    lunes, domingo = _semana_es()
    profiles, umap = await _activos_con_usuarios()

    emails = [umap[p["user_id"]]["email"] for p in profiles
              if p.get("user_id") in umap and umap[p["user_id"]].get("email")]
    pagos = await _ultimo_pago_por_email(emails)

    def pago_de(p):
        u = umap.get(p.get("user_id")) or {}
        return pagos.get(u.get("email"))

    # Renovaciones de las próximas 4 semanas, repartidas por semana natural (la 0 es la
    # actual). Renovar = se le acaba lo pagado (current_period_end) ese día.
    semanas: List[List[Dict[str, Any]]] = [[], [], [], []]
    for p in profiles:
        fecha = _fecha_de(p.get("current_period_end"))
        if not fecha or fecha < lunes:
            continue
        indice = (fecha - lunes).days // 7
        if indice < 4:
            semanas[indice].append(
                _fila_renovacion(p, umap.get(p.get("user_id")), _plan_de(catalogo, p), pago_de(p)))
    for lista in semanas:
        lista.sort(key=lambda f: (f["fecha"] or "9999", f["name"]))

    # Lo que entra ESTA semana. Lo puesto a mano cuenta como confirmado: lo escribió una
    # persona que sabe cómo paga ese cliente (transferencia incluida), que es más de lo
    # que sabe Stripe de él.
    confirmado = round(sum(f["importe"] for f in semanas[0]
                           if f["estado"] in ("confirmado", "a_mano")), 2)
    por_confirmar = round(sum(f["importe"] for f in semanas[0]
                              if f["estado"] == "por_confirmar"), 2)

    # La CARTERA se calcula más abajo, cuando ya se sabe quién paga: el criterio de
    # Francisco (20-08) es que «los que no pagan no cuentan». El delta y la foto semanal
    # van con ese mismo número.

    # ALTAS Y BAJAS de la semana. Las altas son perfiles creados esta semana. Las bajas
    # son una APROXIMACIÓN honesta: la app no registra bajas explícitas todavía, así que
    # se toma "se le acabó lo pagado esta semana y su acceso dice caducado" (no renovó).
    # El día que exista un registro de bajas de verdad, esto se lee de ahí.
    lunes_iso, fin_iso = lunes.isoformat(), (lunes + timedelta(days=7)).isoformat()
    movimientos = await db.client_profiles.find(
        {**await _fuera_el_equipo(),
         "$or": [{"created_at": {"$gte": lunes_iso, "$lt": fin_iso}},
                 {"current_period_end": {"$gte": lunes_iso, "$lt": fin_iso}}]},
        {**_PROY_PERFIL, "access_until": 1, "checkout_status": 1},
    ).to_list(1000)
    uids_extra = [p["user_id"] for p in movimientos
                  if p.get("user_id") and p["user_id"] not in umap]
    if uids_extra:
        for u in await db.users.find({"id": {"$in": uids_extra}},
                                     {"_id": 0, "id": 1, "name": 1}).to_list(len(uids_extra)):
            umap[u["id"]] = u
    altas, bajas = [], []
    for p in movimientos:
        fila = _fila(p, umap.get(p.get("user_id")), _plan_de(catalogo, p))
        if lunes_iso <= str(p.get("created_at") or "")[:10] < fin_iso:
            altas.append(fila)
        fin = _fecha_de(p.get("current_period_end"))
        if fin and lunes <= fin <= domingo and estado_de_acceso(p)["motivo"] == "caducado":
            bajas.append(fila)

    # FACTURA AL MES y reparto por plan, con el importe de renovación de cada uno
    # normalizado a mes. `a_cero` es el aviso del doc: «28 clientes están a 0 EUR;
    # cualquier suma sale corta». Que el número esté a la vista, no escondido.
    factura_mes, a_cero = 0.0, 0
    pagando = 0
    por_plan: Dict[str, Dict[str, Any]] = {}
    for p in profiles:
        plan = _plan_de(catalogo, p)
        importe, _ = _importe_renovacion(p, plan, pago_de(p))
        eur = _eur_mes(importe, plan)
        factura_mes += eur
        if eur <= 0:
            a_cero += 1
        else:
            pagando += 1
        code = codigo_de_plan(p.get("plan")) or "sin_plan"
        grupo = por_plan.setdefault(
            code, {"plan": code, "nombre": plan.get("name") or code, "n": 0, "eur_mes": 0.0})
        grupo["n"] += 1
        grupo["eur_mes"] += eur

    # CARTERA ACTIVA = LOS QUE PAGAN (criterio de Francisco, 20-08: «los que no pagan no
    # cuentan»). Los que tienen acceso pero suman 0 EUR no engordan la cartera; van en
    # `a_cero`, a la vista. El delta compara contra la foto de la semana pasada, que se
    # guarda al servir: una por semana ISO, la primera visita de la semana fija el número
    # (machacarla en cada carga haría el delta comparar la foto de hace 5 minutos).
    iso_year, iso_week, _ = lunes.isocalendar()
    semana_iso = f"{iso_year}-W{iso_week:02d}"
    if not await db.panel_snapshots.find_one({"semana": semana_iso}, {"_id": 1}):
        await db.panel_snapshots.insert_one(
            {"semana": semana_iso, "activos": pagando, "fecha": now.isoformat(),
             "criterio": "pagando"})
    prev_year, prev_week, _ = (lunes - timedelta(days=7)).isocalendar()
    anterior = await db.panel_snapshots.find_one(
        {"semana": f"{prev_year}-W{prev_week:02d}"}, {"_id": 0, "activos": 1})
    delta = (pagando - anterior["activos"]) if anterior else None

    prevision = []
    for i in range(4):
        desde, hasta = lunes + timedelta(days=7 * i), lunes + timedelta(days=7 * i + 6)
        prevision.append({
            "desde": desde.isoformat(), "hasta": hasta.isoformat(),
            "etiqueta": _label_rango(desde, hasta),
            "total": round(sum(f["importe"] for f in semanas[i]), 2),
            "clientes": semanas[i],
        })

    return {
        "entra_esta_semana": {"confirmado": confirmado, "por_confirmar": por_confirmar,
                              "clientes": semanas[0]},
        # `activos` son los que pagan; `con_acceso` es el total con acceso vigente, para
        # que la diferencia (los a cero) no desaparezca de la vista.
        "cartera": {"activos": pagando, "con_acceso": len(profiles), "delta_semana": delta},
        "altas_bajas": {"altas": len(altas), "bajas": len(bajas),
                        "altas_clientes": altas, "bajas_clientes": bajas},
        "factura_mes": round(factura_mes, 2),
        "a_cero": a_cero,
        "prevision": prevision,
        "reparto_por_plan": sorted(
            [{**g, "eur_mes": round(g["eur_mes"], 2)} for g in por_plan.values()],
            key=lambda g: -g["eur_mes"]),
        # DE DÓNDE VIENEN LOS QUE ENTRAN: el origen de los leads de las últimas 4
        # semanas. La tubería es el webhook de GHL (/leads/webhook/ghl); si GHL deja de
        # mandar, esto se queda a cero y se nota, que es lo que tiene que pasar.
        "origenes": await _origenes_de_leads(now),
        # Los bloques del doc cuyos datos hoy NO llegan a la app. Se devuelven con
        # su motivo para que el panel enseñe el hueco en vez de fingir que no existe.
        "sin_conectar": [
            {"bloque": "La publicidad",
             "motivo": "El gasto y los resultados de las campañas no llegan a la app: no hay conexión con las plataformas de anuncios."},
            {"bloque": "La newsletter",
             "motivo": "Los envíos y las aperturas están en ActiveCampaign y la app no tiene acceso a esa cuenta."},
        ],
        "generated_at": now.isoformat(),
    }


@router.put("/direccion/prevision/{client_id}")
async def poner_prevision(client_id: str, data: Dict[str, Any] = Body(...),
                          user=Depends(get_admin_only_user)):
    """Fija (o borra con null) el importe de renovación a mano de un cliente. Es la vía
    para los que pagan por transferencia o pactaron otro precio: manda sobre el último
    cobro y sobre el catálogo."""
    importe = data.get("importe", None)
    if importe is not None:
        if isinstance(importe, bool) or not isinstance(importe, (int, float)):
            raise HTTPException(status_code=400, detail="El importe tiene que ser un número o null")
        if not 0 <= float(importe) <= 10000:
            raise HTTPException(status_code=400, detail="El importe tiene que estar entre 0 y 10000")
    perfil = await db.client_profiles.find_one({"id": client_id}, {"_id": 0, "id": 1})
    if not perfil:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    if importe is None:
        await db.client_profiles.update_one(
            {"id": client_id}, {"$unset": {"renovacion_importe_prevision": ""}})
    else:
        await db.client_profiles.update_one(
            {"id": client_id}, {"$set": {"renovacion_importe_prevision": round(float(importe), 2)}})
    return {"ok": True, "importe": None if importe is None else round(float(importe), 2)}


# ==================== 2) Entrenador ====================

@router.get("/entrenador")
async def panel_entrenador(trainer_id: Optional[str] = None, user=Depends(get_admin_user)):
    """El panel de cada entrenador: sus reportes de la semana, macros por entregar,
    fotos nuevas y quién se le está cayendo. El admin puede mirar el de cualquiera
    con ?trainer_id=; el trainer sin parámetro ve el suyo."""
    now = datetime.now(timezone.utc)
    catalogo = merged_catalog(await _overrides_by_code())

    # A quién se mira: el trainer se mira a sí mismo salvo que pida otro (puede: desde
    # el 13-08 el equipo ve a todos los clientes). El admin sin parámetro también se ve
    # a sí mismo, porque en esta casa los admin llevan clientes (Jesús es admin).
    tid = trainer_id or user["id"]
    equipo = await db.users.find(
        {"role": {"$in": ["trainer", "admin"]}}, {"_id": 0, "id": 1, "name": 1}
    ).to_list(100)
    trainer = next((u for u in equipo if u["id"] == tid), None)
    if not trainer:
        raise HTTPException(status_code=404, detail="Ese entrenador no existe")

    profiles, umap = await _activos_con_usuarios()
    # Sin asignar = su plan lleva entrenador y no tiene a nadie (P64): los solo_app
    # (ELM, Mantenimiento) no cuentan, no hay nada que asignarles.
    sin_asignar = sum(1 for p in profiles
                      if not p.get("trainer_id") and _plan_lleva_entrenador(_plan_de(catalogo, p)))
    mios = [p for p in profiles if p.get("trainer_id") == tid]
    ids = [p["id"] for p in mios]

    # El último ajuste VIGENTE de mis clientes, de una sola consulta al histórico: el
    # campo del perfil se queda viejo con los migrados de Calma (core/ultimo_ajuste).
    from core.tiempo import hoy_madrid as _hoy_madrid
    from core.ultimo_ajuste import ajuste_de, ultimos_ajustes_vigentes
    hoy_es_ajustes = _hoy_madrid().isoformat()
    ajustes_del_historico = await ultimos_ajustes_vigentes(db, ids, hoy_es_ajustes)

    # Rutinas, últimos reportes y fotos recientes de MIS clientes, una consulta cada
    # cosa. La rutina hace falta porque desde el doc 19-08 la semana que decide el
    # reporte es la de la rutina cuando existe.
    rutina_de = {r["client_id"]: r for r in await db.routines.find(
        {"client_id": {"$in": ids}, "status": "active"},
        {"_id": 0, "client_id": 1, "created_at": 1}).to_list(len(ids) or 1)}
    corte_reportes = (now - timedelta(days=60)).isoformat()
    ultimo_reporte: Dict[str, str] = {}
    async for r in db.reports.find(
            hasta_hoy({"client_id": {"$in": ids}, "created_at": {"$gte": corte_reportes}}),
            {"_id": 0, "client_id": 1, "created_at": 1}):
        cid, ca = r.get("client_id"), r.get("created_at")
        if cid and ca and (cid not in ultimo_reporte or ca > ultimo_reporte[cid]):
            ultimo_reporte[cid] = ca
    corte_fotos = (now - timedelta(days=7)).isoformat()
    fotos: Dict[str, Dict[str, Any]] = {}
    async for f in db.client_photos.aggregate([
            {"$match": {"client_id": {"$in": ids}, "uploaded_at": {"$gte": corte_fotos}}},
            {"$group": {"_id": "$client_id", "n": {"$sum": 1}, "ultima": {"$max": "$uploaded_at"}}}]):
        if f.get("_id"):
            fotos[f["_id"]] = f

    mandados, les_toca, aplazados = [], [], []
    macros_por_entregar, fotos_nuevas, cayendo = [], [], []
    for p in mios:
        u = umap.get(p.get("user_id"))
        plan = _plan_de(catalogo, p)
        fila = _fila(p, u, plan)
        state = compute_client_report_state(p, catalogo, now, rutina=rutina_de.get(p["id"]))
        reporte = ultimo_reporte.get(p["id"])
        reporte_en_ventana = bool(reporte and reporte >= state["window_start"].isoformat())
        aplazado_hasta = p.get("reporte_aplazado_hasta")
        aplazado_vigente = bool(aplazado_hasta and str(aplazado_hasta) >= now.isoformat())

        if state["due"]:
            if reporte_en_ventana:
                mandados.append(fila)
            elif aplazado_vigente:
                aplazados.append({**fila, "nota": p.get("reporte_aplazado_nota") or None,
                                  "aplazado_hasta": aplazado_hasta,
                                  "seguidos": int(p.get("aplazamientos_seguidos") or 0)})
            else:
                les_toca.append(fila)

        # Macros por entregar: mandó su reporte (dentro de su ventana de esta semana) y
        # el último ajuste de macros es anterior al reporte, o no hay ajuste ninguno.
        # O sea: el cliente ya hizo su parte y espera la del coach.
        if reporte_en_ventana:
            # Del histórico si va por delante del campo (core/ultimo_ajuste): con los
            # migrados de Calma el campo se queda viejo y aquí saldría gente a la que ya
            # se le ajustó.
            ajuste = ajuste_de(p, ajustes_del_historico, hoy_es_ajustes)
            if not ajuste or str(ajuste) < reporte:
                macros_por_entregar.append({**fila, "reporte_el": reporte})

        if p["id"] in fotos:
            fotos_nuevas.append({**fila, "n_fotos": int(fotos[p["id"]]["n"]),
                                 "ultima": fotos[p["id"]].get("ultima")})

        # CAYENDO. (a) Dos reportes seguidos sin mandar: la app no guarda "ventanas
        # falladas", así que se aproxima con lo que sí hay: dos aplazamientos seguidos,
        # o el último reporte hace más del DOBLE de su cadencia (si le toca cada 14 días
        # y lleva 30 sin mandar, se ha saltado dos). Es una aproximación y se asume.
        dias_reporte = _dias_desde(reporte or p.get("ultimo_reporte"), now)
        cadencia = dias_hasta_la_revision(codigo_de_plan(p.get("plan")))
        if int(p.get("aplazamientos_seguidos") or 0) >= 2 or \
                (dias_reporte is not None and dias_reporte > 2 * cadencia):
            cayendo.append({**fila, "motivo": "dos reportes sin mandar"})
        # (b) Sin entrar en la app 14 días o más. `last_seen` nació hace poco: al que no
        # lo tiene no se le acusa de nada, porque "sin dato" no es "sin entrar".
        dias_visto = _dias_desde((u or {}).get("last_seen"), now)
        if dias_visto is not None and dias_visto >= 14:
            cayendo.append({**fila, "motivo": f"{dias_visto} días sin entrar"})

    return {
        "trainer": {"id": trainer["id"], "name": trainer.get("name")},
        "equipo": sorted(equipo, key=lambda u: (u.get("name") or "").lower()),
        "reporte": {"mandados": mandados, "les_toca": les_toca, "aplazados": aplazados},
        "macros_por_entregar": macros_por_entregar,
        "fotos_nuevas": sorted(fotos_nuevas, key=lambda f: f["ultima"] or "", reverse=True),
        "cayendo": cayendo,
        # Para que el panel pueda decir POR QUÉ sale vacío: hoy solo 8 de 247 clientes
        # tienen entrenador asignado, y un panel vacío sin este número parece roto.
        "sin_asignar": sin_asignar,
        "generated_at": now.isoformat(),
    }


# ==================== 3) Operaciones ====================

@router.get("/operaciones")
async def panel_operaciones(user=Depends(get_admin_user)):
    """El panel de Operaciones: lo parado esperando a Jesús, lo que cierra hoy, los
    huecos de datos y las tareas vencidas de cada uno."""
    now = datetime.now(timezone.utc)
    hoy = hoy_madrid()
    catalogo = merged_catalog(await _overrides_by_code())
    profiles, umap = await _activos_con_usuarios()

    # LO QUE ESPERA A JESÚS. El criterio es el del doc («lo que está parado
    # esperándole»): sus tareas sin hacer. Se le busca por nombre que empieza por "Jes"
    # y rol admin porque no hay un campo "es el jefe" en la base; si algún día hay dos
    # admin que se llamen Jesús, esto se cambia por un id fijo en app_settings.
    jesus = await db.users.find_one(
        {"role": "admin", "name": {"$regex": "^Jes"}}, {"_id": 0, "id": 1, "name": 1})
    esperando = []
    if jesus:
        docs = await db.tareas.find(
            {"a_quien": jesus["id"], "hecha": False},
            {"_id": 0, "id": 1, "que": 1, "para_cuando": 1,
             "sobre_quien": 1, "sobre_quien_nombre": 1, "created_at": 1},
        ).to_list(500)
        esperando = sorted(docs, key=lambda t: t.get("para_cuando") or "9999")

    # CIERRA HOY: ventanas de reporte abiertas que se cierran hoy EN HORA DE ESPAÑA y
    # cuyo cliente no ha mandado nada (los aplazados no cuentan: ya avisaron).
    ids = [p["id"] for p in profiles]
    rutina_de = {r["client_id"]: r for r in await db.routines.find(
        {"client_id": {"$in": ids}, "status": "active"},
        {"_id": 0, "client_id": 1, "created_at": 1}).to_list(len(ids) or 1)}
    corte = (now - timedelta(days=21)).isoformat()
    ultimo_reporte: Dict[str, str] = {}
    async for r in db.reports.find(
            hasta_hoy({"client_id": {"$in": ids}, "created_at": {"$gte": corte}}),
            {"_id": 0, "client_id": 1, "created_at": 1}):
        cid, ca = r.get("client_id"), r.get("created_at")
        if cid and ca and (cid not in ultimo_reporte or ca > ultimo_reporte[cid]):
            ultimo_reporte[cid] = ca

    cierra_hoy, sin_entrenador, sin_datos, con_imposibles = [], [], [], []
    for p in profiles:
        u = umap.get(p.get("user_id"))
        plan = _plan_de(catalogo, p)
        fila = _fila(p, u, plan)

        # Solo si su plan LLEVA entrenador (P64): al de ELM o Mantenimiento no le falta
        # nadie, su plan es sin acompañamiento.
        if not p.get("trainer_id") and _plan_lleva_entrenador(plan):
            sin_entrenador.append(fila)

        faltas = [nombre for campo, nombre in (("height", "altura"), ("goal", "objetivo"))
                  if not p.get(campo)]
        if faltas:
            sin_datos.append({**fila, "falta": " y ".join(faltas)})

        # DATOS IMPOSIBLES (tarea 1.4 del 21-08): valores que la API no dejaria escribir
        # (edad 5, estatura 1 cm, peso 1 kg) y que entraron por la importacion de Calma
        # directa a Mongo. Es una lista APARTE de «sin datos» a proposito: aquello es lo
        # que falta; esto es lo que esta MAL, y hay que corregirlo con el cliente delante.
        imposibles = datos_imposibles(p)
        if imposibles:
            con_imposibles.append({**fila, "imposible": " · ".join(
                f"{d['nombre']}: {d['valor']}" for d in imposibles)})

        state = compute_client_report_state(p, catalogo, now, rutina=rutina_de.get(p["id"]))
        if not state["due"] or not state["is_open"]:
            continue
        cierre = a_madrid(state["window_close"])
        if not cierre or cierre.date() != hoy:
            continue
        aplazado = p.get("reporte_aplazado_hasta")
        if aplazado and str(aplazado) >= now.isoformat():
            continue
        reporte = ultimo_reporte.get(p["id"])
        if reporte and reporte >= state["window_start"].isoformat():
            continue
        cierra_hoy.append({**fila, "tipo": (state["tipos"] or [None])[0],
                           "cierra": state["window_close"].isoformat()})

    # TAREAS VENCIDAS, agrupadas por persona. La tarea no guarda el nombre del asignado
    # (core/tareas.py solo escribe `a_quien`), así que el nombre se resuelve aquí contra
    # db.users en una consulta.
    vencidas = await db.tareas.find(
        {"hecha": False, "para_cuando": {"$lt": hoy.isoformat(), "$ne": None}},
        {"_id": 0, "id": 1, "a_quien": 1, "que": 1, "para_cuando": 1, "sobre_quien_nombre": 1},
    ).to_list(1000)
    nombres = {u["id"]: u.get("name") for u in await db.users.find(
        {"id": {"$in": list({t.get("a_quien") for t in vencidas if t.get("a_quien")})}},
        {"_id": 0, "id": 1, "name": 1}).to_list(200)} if vencidas else {}
    por_persona: Dict[str, Dict[str, Any]] = {}
    for t in sorted(vencidas, key=lambda t: t.get("para_cuando") or ""):
        quien = t.get("a_quien") or "?"
        grupo = por_persona.setdefault(quien, {
            "a_quien": quien, "a_quien_nombre": nombres.get(quien) or "?", "n": 0, "tareas": []})
        grupo["n"] += 1
        grupo["tareas"].append({"id": t.get("id"), "que": t.get("que"),
                                "para_cuando": t.get("para_cuando"),
                                "sobre_quien_nombre": t.get("sobre_quien_nombre")})

    # La lista del doc de Francisco: dos números que se apuntan a mano (PUT de abajo).
    ajustes = await db.app_settings.find_one({"id": "app"}, {"_id": 0, "lista_doc_1908": 1}) or {}
    lista = ajustes.get("lista_doc_1908") or {}

    return {
        "esperando_a_jesus": esperando,
        "cierra_hoy": sorted(cierra_hoy, key=lambda f: f["name"]),
        "sin_entrenador": {"n": len(sin_entrenador),
                           "clientes": sorted(sin_entrenador, key=lambda f: f["name"])},
        "sin_datos": {"n": len(sin_datos), "clientes": sorted(sin_datos, key=lambda f: f["name"])},
        "datos_imposibles": {"n": len(con_imposibles),
                             "clientes": sorted(con_imposibles, key=lambda f: f["name"])},
        "tareas_vencidas": sorted(por_persona.values(), key=lambda g: -g["n"]),
        "lista_francisco": {"hechas": lista.get("hechas"), "total": lista.get("total")},
        "generated_at": now.isoformat(),
    }


@router.put("/operaciones/lista")
async def poner_lista(data: Dict[str, Any] = Body(...), user=Depends(get_admin_user)):
    """Apunta el avance de la lista del doc (hechas / total). Va al mismo documento
    único de db.app_settings (id "app") que usa routes/settings.py."""
    hechas, total = data.get("hechas"), data.get("total")
    for v in (hechas, total):
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            raise HTTPException(status_code=400,
                                detail="hechas y total tienen que ser enteros de 0 en adelante")
    if hechas > total:
        raise HTTPException(status_code=400, detail="hechas no puede ser mayor que total")
    await db.app_settings.update_one(
        {"id": "app"},
        {"$set": {"lista_doc_1908": {"hechas": hechas, "total": total,
                                     "actualizado": datetime.now(timezone.utc).isoformat()}}},
        upsert=True,
    )
    return {"ok": True, "hechas": hechas, "total": total}


# ==================== 4) Soporte ====================

@router.get("/soporte")
async def panel_soporte(user=Depends(get_admin_user)):
    """El panel de Soporte: a quién se le acaba pronto (con su teléfono, para llamarle),
    quién tiene el pago atascado y quién lleva demasiado sin que nadie le escriba."""
    now = datetime.now(timezone.utc)
    hoy = hoy_madrid()
    catalogo = merged_catalog(await _overrides_by_code())
    profiles, umap = await _activos_con_usuarios()

    emails = [umap[p["user_id"]]["email"] for p in profiles
              if p.get("user_id") in umap and umap[p["user_id"]].get("email")]
    pagos = await _ultimo_pago_por_email(emails)

    renovacion, problemas = [], []
    for p in profiles:
        u = umap.get(p.get("user_id"))
        plan = _plan_de(catalogo, p)
        fecha = _fecha_de(p.get("current_period_end"))
        pago = pagos.get((u or {}).get("email"))

        if fecha and hoy <= fecha <= hoy + timedelta(days=14):
            ciclo = compute_cycle(p, now)
            renovacion.append({
                **_fila_renovacion(p, u, plan, pago),
                "telefono": (u or {}).get("phone") or None,
                "semana": ciclo["week"],
                # Cuántas semanas tiene su ciclo, para leer "semana 11 de 12" de un
                # vistazo. Los mensuales no declaran semanas en `ciclo`: se cae al
                # ciclo de cobro, que es el que está renovando.
                "semanas_ciclo": (plan.get("ciclo") or {}).get("semanas")
                                 or plan.get("billing_cycle_weeks"),
            })

        st = (p.get("subscription_status") or "").lower()
        if st in ("past_due", "unpaid", "incomplete"):
            problemas.append({**_fila(p, u, plan), "motivo": f"cobro atascado en Stripe ({st})"})
        elif not (plan.get("renovacion") or {}).get("automatica") and \
                fecha and hoy <= fecha <= hoy + timedelta(days=7):
            # No renueva solo y le queda una semana o menos: alguien tiene que cobrarle.
            problemas.append({**_fila(p, u, plan), "motivo": "paga a mano y le toca"})

    # SIN CONTACTAR: mismos criterios que /admin/todo-semana para que los dos sitios
    # cuenten igual. Solo planes con chat (al de autogestión no se le acompaña por ahí)
    # y solo cuentan los mensajes que SALEN del equipo: que el cliente escriba y nadie
    # le conteste tiene que sumar días, no borrarle de la lista.
    staff_ids = await db.users.distinct("id", {"role": {"$in": ["admin", "trainer"]}})
    ultimo_contacto: Dict[str, str] = {}
    async for m in db.messages.find({"sender_id": {"$in": staff_ids}},
                                    {"_id": 0, "receiver_id": 1, "created_at": 1}):
        uid, ca = m.get("receiver_id"), m.get("created_at")
        if uid and ca and (uid not in ultimo_contacto or ca > ultimo_contacto[uid]):
            ultimo_contacto[uid] = ca
    sin_contactar = []
    for p in profiles:
        if not plan_grants_feature(codigo_de_plan(p.get("plan")), "chat"):
            continue
        # El contacto por WhatsApp (via GHL) también cuenta desde el 20-08: llega por el
        # webhook ghl-contacto y se apunta en la ficha. Manda el más reciente de los dos.
        externo = (p.get("ultimo_contacto_externo") or {}).get("fecha")
        interno = ultimo_contacto.get(p.get("user_id"))
        visto = max((f for f in (interno, externo) if f), default=None)
        # Al que nunca se le ha escrito se le cuentan los días desde que empezó: es más
        # honesto que un guion, porque lleva TODO ese tiempo sin oír a nadie.
        dias = _dias_desde(visto or p.get("cycle_start") or p.get("created_at"), now)
        sin_contactar.append({**_fila(p, umap.get(p.get("user_id")), _plan_de(catalogo, p)),
                              "dias": dias, "nunca": visto is None})
    sin_contactar.sort(key=lambda f: -(f["dias"] or 0))

    return {
        "renovacion": sorted(renovacion, key=lambda f: (f["fecha"] or "9999", f["name"])),
        "problemas_pago": problemas,
        # Top 30: la lista entera son cientos y el panel es para actuar hoy, no para
        # hacer scroll. La lista completa con todos ya vive en /admin/todo-semana.
        "sin_contactar": sin_contactar[:30],
        "sin_conectar": [
            {"bloque": "Newsletter y ZeroChats",
             "motivo": "Las conversaciones de la newsletter y de ZeroChats viven fuera (ActiveCampaign y ZeroChats) y la app no tiene conexión con ninguna de las dos."},
        ],
        "generated_at": now.isoformat(),
    }
