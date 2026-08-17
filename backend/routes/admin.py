"""
Rutas de administración: clientes, dashboard, entrenadores.
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse, Response
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
import asyncio
import re
import uuid
import os

from core.database import db
from core.security import (
    get_admin_user, get_admin_only_user, assert_client_access, hash_password, generate_temp_password,
    decode_token,
)

# Carpeta local con las fotos de progreso importadas de Calma (solo dev).
_FOTOS_CALMA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_fotos_calma")
from routes.notifications import avisar_macros, notify
from routes.audit import audit
from models.user import (
    ClientProfile, ClientProfileUpdate, MacrosUpdate, MacroEvaluacion, TrainerAssign, PLAN_CATALOG,
    precio_de_ciclo,
)
from core.cycle import enrich_cycle, compute_cycle
from core.seguimiento import marcar_ajuste, dias_desde, fecha_de_vigencia
from core.series_cliente import anotar_peso, anotar_grasa, actual as actual_de_serie
from core.cambios_macros import marcar_cambios, palancas
from core.historial_macros import guardar as guardar_en_historial
from core.sin_futuro import hasta_hoy
from core import semaforo
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

    # LAS FILAS SIN NOMBRE ERAN REVISIONES HUÉRFANAS.
    #
    # «Las ocho filas dicen "Cliente" sin nombre» (Jesús, 11-08). Seis de esas ocho son de
    # usuarios que se borraron después: la revisión se quedó, el usuario no. Poníamos
    # "Cliente" de relleno y la fila llevaba a una ficha que ya no existe, así que la lista
    # con la que se decide a quién ajustar contaba trabajo que nadie puede hacer.
    # Si no hay a quién revisar, no es una revisión pendiente.
    vivas = [i for i in items if i.get("user_id") in umap]
    for i in vivas:
        u = umap[i["user_id"]]
        i["client_name"] = u.get("name") or u.get("email") or "Cliente"
    return {"items": vivas}


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

def _semaforo_del_cliente(profile: Dict[str, Any], hablado: Dict[str, str],
                          ahora: datetime) -> Dict[str, Any]:
    """El semaforo de un cliente, celda a celda (punto 32 del 07-08).

    Cinco estados y POR CELDA, no por fila: asi se distingue quien va regular de quien va
    mal, y en que. Cada plazo se mide contra la cadencia de SU plan, no contra un numero
    general. La tabla recibe {valor, estado, texto, detalle} y solo pinta.
    """
    from core.plan_access import has_active_access, plan_grants_feature, dias_hasta_la_revision

    plan = profile.get("plan")
    plazo = dias_hasta_la_revision(plan)          # 7, 14 o 28 segun su plan

    # Cuando algo NO HA PASADO NUNCA, el reloj corre desde que empezo: al que entro el lunes
    # todavia no le toca mandar su primer reporte, y pintarlo en rojo es el fallo que
    # denuncia el punto. Es el mismo criterio que ya usaba la columna de contacto.
    desde_que_empezo = dias_desde(
        (profile.get("cycle_start") or profile.get("created_at") or "")[:10], ahora)

    def _celda(fecha, texto_nunca="nunca"):
        if fecha:
            return semaforo.por_plazo(dias_desde(str(fecha)[:10], ahora), plazo)
        return semaforo.por_plazo(desde_que_empezo, plazo, nunca=True, texto_nunca=texto_nunca)

    # Reporte y ajuste: las dos fechas del punto 29, ya guardadas en el cliente.
    reporte = _celda(profile.get("ultimo_reporte"), "ninguno")
    ajuste = _celda(profile.get("ultimo_ajuste"))

    # Contacto: solo los planes con chat. Al de autogestion no se le acompana por ahi, asi
    # que pintarselo en rojo todos los dias seria ruido y no una alerta.
    contacto = (_celda(hablado.get(profile.get("user_id")))
                if plan_grants_feature(plan, "chat")
                else semaforo.no_aplica("su plan no lleva chat"))

    # Peso: cuanto lleva sin pesarse. Sale de la serie (punto 30), asi que trae su fecha.
    ultimo_peso = actual_de_serie(profile.get("pesos"))
    if ultimo_peso:
        peso = semaforo.por_plazo(dias_desde(ultimo_peso["fecha"], ahora), plazo)
        peso["valor"] = ultimo_peso["valor"]
        peso["texto"] = f"{ultimo_peso['valor']} kg"
        peso["detalle"] = f"del {ultimo_peso['fecha']}"
    else:
        peso = semaforo.por_plazo(desde_que_empezo, plazo, nunca=True, texto_nunca="sin peso")

    # Pago: binario de verdad, este si. O esta al corriente o no lo esta.
    al_corriente = has_active_access(profile)
    pago = semaforo.celda(al_corriente, semaforo.OK if al_corriente else semaforo.MALO,
                          "al día" if al_corriente else "pendiente")

    celdas = {"reporte": reporte, "ajuste": ajuste, "contacto": contacto,
              "peso": peso, "pago": pago}
    # `peor` va SOLO para poder ordenar la tabla por quien esta peor. No se usa como
    # etiqueta ni se cuenta: con cuatro celdas, "alguna en rojo" vuelve a ser cierto para
    # casi todos, que es exactamente la alerta binaria que el punto manda quitar.
    return {**celdas, "peor": semaforo.peor(*[c["estado"] for c in celdas.values()])}


# `precio_de_ciclo` se mudó a models/user.py y se importa arriba: lo necesitan también el
# perfil del cliente y su ficha, y viviendo aquí solo lo tenía el panel (punto 2.4c).


# De cuántos meses es cada ciclo, para poder sumar peras con peras.
_MESES_DE_CICLO = {"mensual": 1, "bimestral": 2, "trimestral": 3, "semestral": 6}


def precio_mensual(perfil: Dict[str, Any], catalogo: Dict[str, Any]) -> float:
    """Lo que aporta este cliente AL MES. Es lo que hay que sumar para un MRR.

    El MRR sumaba los `price` tal cual, y son precios de CICLO: un gold son 450 € cada
    trimestre, no cada mes. Mezclado con los mensuales, la cifra no significaba nada.
    """
    plan = (catalogo or {}).get(perfil.get("plan") or "") or {}
    meses = _MESES_DE_CICLO.get(((plan.get("ciclo") or {}).get("tipo") or "mensual"), 1)
    return precio_de_ciclo(perfil, catalogo) / max(meses, 1)


async def _fuera_el_equipo(salvo: Optional[str] = None) -> Dict[str, Any]:
    """Filtro de `client_profiles` que deja fuera los perfiles del equipo.

    Jesús, 09-08-2026: *«los 13 usuarios figuran con plan Gold (legacy), incluidos Admin y
    Jesús»*, y salían tanto en la lista de clientes como en todos los contadores del panel
    -- clientes totales, activos, MRR, el semáforo de "hay que mirarlos" --. Once de los
    trece tienen perfil de cliente con plan, así que no era una fila suelta.

    Los perfiles no se tocan: hacen falta para que el equipo pueda usar la app en modo
    cliente y probar las pantallas. Lo que se quita es que cuenten como negocio.

    `salvo` deja fuera del filtro a un usuario: se usa para que cada uno pueda encontrar SU
    propia ficha (ver `get_all_clients`). En los contadores del panel no se pasa nunca,
    porque ahí la pregunta es cuánto negocio hay y el equipo sigue sin ser negocio.
    """
    del_equipo = await db.users.distinct("id", {"role": {"$in": ["admin", "trainer"]}})
    if salvo:
        del_equipo = [uid for uid in del_equipo if uid != salvo]
    return {"user_id": {"$nin": del_equipo}} if del_equipo else {}


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
    from core.plan_access import estado_de_acceso

    query = {}
    if plan:
        query["plan"] = plan.lower()
    if status:
        query["status"] = status
    if trainer_id:
        query["trainer_id"] = trainer_id
    es_trainer = user.get("role") == "trainer"

    # El admin ve a todos. El entrenador ve LOS SUYOS y los que no tienen coach, que
    # son de donde puede coger (documento del 06-08-2026, que revierte la decisión del
    # 21-07). Los de otro coach no salen ni en la lista: no es solo que no pueda
    # entrar, es que no tiene por qué verlos.
    # EL ENTRENADOR VE A TODOS LOS CLIENTES (Jesús, 13-08-2026, caso 83).
    #
    # Es su decisión del 21-07, que él mismo reafirma hoy con el motivo: *«con 177 clientes
    # y el equipo que tienes, separas: el día que uno se va de vacaciones, los suyos se
    # quedan sin nadie que los mire»*. Entre el 06-08 y hoy el código hizo lo contrario --
    # cada coach veía los suyos y los libres --, y el caso 83 llevaba en rojo esperando
    # precisamente a que él desempatara. Ya está: ven y gestionan a todos.
    #
    # Esto contradice A PROPÓSITO un hallazgo de la auditoría de seguridad («un trainer
    # accede a clientes ajenos»): no es un fallo, es cómo quiere que trabaje su equipo. Lo
    # que sigue cerrado es la pestaña Usuarios, que es de admin (casos 83 y siguientes), y
    # un cliente sigue sin ver a otro cliente.
    #
    # Las reglas de VISIBILIDAD van aparte de los filtros que pide quien busca (plan,
    # estado, coach): así se puede hacer una excepción con las primeras -- tu propia ficha
    # -- sin saltarse las segundas.
    visibilidad: Dict[str, Any] = {}

    # El equipo fuera de la lista de clientes. Jesús, 09-08: los 13 usuarios del equipo
    # figuraban como clientes con plan Gold, él y el admin incluidos, y salían mezclados
    # con los de verdad y contando en todos los números del panel.
    visibilidad.update(await _fuera_el_equipo())

    # PERO CADA UNO SE VE A SÍ MISMO (13-08-2026). Francisco: *«necesito que los
    # entrenadores y administradores puedan buscar su propia ficha como clientes porque
    # ellos usan la app de las dos formas, y hoy ya no pueden modificar sus propios
    # macros»*. Sacar al equipo de la lista era para que no contara como negocio -- lo dice
    # la propia `_fuera_el_equipo`: «los perfiles hacen falta para que el equipo pueda usar
    # la app en modo cliente» --, pero de paso se quedaron sin poder abrir su ficha, que es
    # por donde se tocan los macros. Medido: 12 de los 16 del equipo tienen ficha de
    # cliente, y ninguno se encontraba.
    #
    # Es una excepción de UNA fila: cada cual se ve a sí mismo, nadie ve al resto del
    # equipo, y los contadores del panel siguen contando solo clientes de verdad. Los
    # filtros que pida quien busca (plan, estado) se aplican también a su ficha: si filtras
    # por «gold» y tú eres nivel 2, no sales, que es lo que se espera de un filtro.
    if visibilidad:
        query["$or"] = [visibilidad, {"user_id": user["id"]}]

    # Proyección mínima para el listado (los detalles van por /clients/{id}) y usuarios en
    # UNA consulta batch en vez de una por perfil (N+1 que hacía lenta la lista).
    # `ultimo_ajuste` y `ultimo_reporte` viajan aqui (punto 29): son las dos fechas que
    # contestan "¿quien me toca esta semana?" y estan guardadas EN el cliente justo para
    # poder ordenar la lista sin recorrer el historico de doscientos y pico clientes.
    # `current_period_end` y `checkout_status` viajan porque sin ellos el panel NO PUEDE
    # saber si el cliente tiene acceso: son justo los dos campos que mira la puerta de la
    # app (`core/plan_access`). Sin el primero, un perfil con el ciclo terminado el 20 de
    # julio salía como «Activo» en la lista mientras a él, al entrar, se le decía que su
    # suscripción había caducado (Francisco, 17-08, con un cliente de ELM). Son 60 de los
    # 184 marcados activos en producción: el panel no se equivocaba en uno, se equivocaba
    # en todos los que se les acabó el ciclo.
    LIST_FIELDS = {"_id": 0, "id": 1, "user_id": 1, "plan": 1, "price": 1, "week": 1,
                   "cycle_start": 1, "status": 1, "trainer_id": 1, "created_at": 1,
                   "ultimo_ajuste": 1, "ultimo_reporte": 1, "pesos": 1,
                   "stripe_subscription_id": 1, "subscription_status": 1, "access_until": 1,
                   "current_period_end": 1, "checkout_status": 1,
                   # La excepcion viaja en el listado (punto 39): si solo estuviera dentro
                   # de la ficha, para verla habria que entrar en las 232, que es lo mismo
                   # que tenerla en una hoja aparte.
                   "excepcion": 1}
    profiles = await db.client_profiles.find(query, LIST_FIELDS).to_list(1000)

    uids = [p["user_id"] for p in profiles]
    users = await db.users.find(
        {"id": {"$in": uids}},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "phone": 1, "role": 1}
    ).to_list(len(uids) or 1)
    umap = {u["id"]: u for u in users}

    # El semaforo (punto 32) necesita saber cuando se le hablo por ultima vez. Una consulta
    # para todos, no una por cliente.
    ahora = datetime.now(timezone.utc)
    staff = set(await db.users.distinct("id", {"role": {"$in": ["admin", "trainer"]}}))
    hablado: Dict[str, str] = {}
    async for m in db.messages.find({"sender_id": {"$in": list(staff)}},
                                    {"_id": 0, "receiver_id": 1, "created_at": 1}):
        uid, ca = m.get("receiver_id"), m.get("created_at")
        if uid and ca and (uid not in hablado or ca > hablado[uid]):
            hablado[uid] = ca

    # El precio que se ENSEÑA sale del catálogo cuando el perfil no trae uno propio. Los
    # clientes que vinieron de Calma llegaron con `price` a cero y la lista les ponía 0 €
    # aunque estuvieran pagando; ver `precio_de_ciclo`.
    from routes.plans import _overrides_by_code
    from models.user import merged_catalog
    catalogo = merged_catalog(await _overrides_by_code())

    result = []
    for profile in profiles:
        user_data = umap.get(profile["user_id"])
        if user_data:
            # EL MISMO ESTADO QUE VE ÉL AL ENTRAR. `status` es una etiqueta que alguien puso
            # una vez y no se entera de que pasa el tiempo; quien decide si puede usar la app
            # es `estado_de_acceso`, que además mira el fin del ciclo. Se manda calculado y
            # no se deja que lo deduzca el panel: dos criterios para la misma pregunta
            # siempre acaban contradiciéndose, y esta vez le dijeron cosas distintas al
            # equipo y al cliente el mismo día.
            fila = {**enrich_cycle(profile), "user": user_data,
                    "price": precio_de_ciclo(profile, catalogo),
                    "precio_mensual": round(precio_mensual(profile, catalogo), 2),
                    "acceso": estado_de_acceso(profile),
                    "semaforo": _semaforo_del_cliente(profile, hablado, ahora)}
            # TU PROPIA FICHA VA MARCADA. Es la única que entra por la excepción de arriba,
            # y no es negocio: los contadores del panel (clientes totales, activos, MRR)
            # siguen sin contarla, así que quien compare la tabla con un contador tiene que
            # poder descontarla. Sin la marca, el caso 77 de Jesús -- «los contadores y la
            # tabla dan el mismo número» -- salía en rojo por una fila que es tuya.
            if profile["user_id"] == user["id"]:
                fila["es_tu_ficha"] = True
            result.append(fila)

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
    # Hasta hoy (punto 22): la ficha abria por un reporte de noviembre. Los 31 reportes
    # fechados por delante vinieron de la importacion de Calma, no de la app.
    # SIN EL INFORME DENTRO. Desde T9 cada reporte guarda su informe montado, y la ficha se
    # trae cincuenta: eso son cincuenta informes enteros en una respuesta que solo necesita
    # la lista. El informe se pide aparte, cuando se abre uno (`GET /reports/{id}/informe`).
    reports = await db.reports.find(
        hasta_hoy({"client_id": client_id}), {"_id": 0, "informe": 0}
    ).sort("created_at", -1).to_list(50)
    # LOS COBROS DE LA FICHA SON LOS DE COBROS (punto 5 del documento del 17-08).
    #
    # Esto leía `db.payments`, que es lo que escribe el checkout de la app. Cobros lee otra
    # colección, `db.pagos_historicos`, que es donde `_sync_membresias_cobros.py` unifica
    # Stripe, Holded y ThriveCart. Dos sitios para «lo que ha pagado», y el de la ficha casi
    # siempre vacío: en producción, Jose Alberto Marquez Valenzuela tenía un cobro de
    # Mantenimiento del 16-08 y un Plan Gold de 847 EUR del 25-05 en Cobros, y su ficha decía
    # «Sin pagos registrados». Se cruzan por CORREO, que es la clave con la que llegan de las
    # tres pasarelas; el `client_id` no viaja en todas.
    correo = (user_data or {}).get("email") or ""
    payments = []
    if correo:
        payments = await db.pagos_historicos.find(
            {"email": correo.lower().strip(), "duplicado_de": {"$exists": False}},
            {"_id": 0},
        ).sort("fecha", -1).to_list(50)
    # Lo que escribió el checkout de la app, por si hay algo que no haya llegado a la
    # sincronización todavía. Las referencias se comparan para no enseñar el mismo cobro dos
    # veces con dos nombres.
    vistos = {p.get("referencia") for p in payments}
    async for p in db.payments.find({"client_id": client_id}, {"_id": 0}).sort("created_at", -1):
        if p.get("referencia") not in vistos:
            payments.append(p)
    messages = await db.messages.find(
        {"$or": [{"sender_id": profile["user_id"]}, {"receiver_id": profile["user_id"]}]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    # Por fecha de efecto y, a igualdad, por cuándo se hizo el cambio. Ordenar solo por
    # effective_date dejaba al azar el orden de varios ajustes del MISMO día: el panel del
    # coach podía enseñar primero el cambio más viejo de hoy.
    # Hasta hoy tambien aqui (punto 22): hay 37 entradas con fecha de vigencia por delante
    # -- 2026-09, 2027, 2029 --, y el historial del coach abria por una de ellas, o sea por
    # unos macros que todavia no aplican a nadie.
    macro_history = await db.macro_history.find(
        hasta_hoy({"client_id": client_id}, campo="effective_date"), {"_id": 0}
    ).sort([("effective_date", -1), ("created_at", -1)]).to_list(500)
    # El protocolo va RESUELTO POR FECHA (punto 33): `actual` es el que le toca hoy y
    # `siguiente` el que ya esta preparado, y viaja el historico entero.
    from routes.supplements import _respuesta as _protocolo_resuelto
    _sp = await db.supplement_protocols.find_one({"client_id": client_id}, {"_id": 0})
    supplement_protocol = _protocolo_resuelto(_sp) if _sp else None

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

    # El precio que se enseña en la pestaña Membresía de la ficha, resuelto igual que en la
    # lista (punto 2.4c): sin esto, el entrenador veía «0 €/ciclo» en la ficha del mismo
    # cliente al que la lista le pone su precio.
    from routes.plans import _overrides_by_code
    from models.user import merged_catalog
    profile["precio_ciclo"] = precio_de_ciclo(profile, merged_catalog(await _overrides_by_code()))
    profile["precio_cortesia"] = bool(profile.get("comp_plan"))

    # TODOS LOS PESOS DE LA FICHA, EN KILOS.
    #
    # «Agosto de 2026 · 62800 kg · ▼ 700 kg» (Jesus, 16-08). Son 62,8 kg y 700 g. La
    # «Evolucion del cliente» junta tres fuentes -- los reportes de la app, el historial de
    # macros y lo que vino de Calma -- y las de Calma guardan el peso EN GRAMOS. Mezcladas
    # sin sanear, el mes en gramos sale a 62800 y la diferencia contra el mes anterior en
    # kilos da el peso entero. Se sanea aqui, en el origen, y no en la pantalla: de esta
    # misma respuesta comen el mural de fotos y la comparativa de fases, que comparten
    # `_pesoCercano`, y arreglarlo en una sola dejaria a las otras dos con los gramos.
    _sanear_pesos(reports, "weight")
    _sanear_pesos(macro_history, "peso", "client_weight")
    if calma_raw:
        _sanear_pesos(calma_raw.get("pesos"), "valor")
        _sanear_pesos(calma_raw.get("formularios_mensuales"), "peso")

    # LOS MACROS QUE COME HOY, QUE NO SIEMPRE SON LOS DEL CAMPO (17-08-2026).
    #
    # `macros_training` es un espejo: lo escriben el ajuste del coach, la calculadora y la
    # sincronización de Calma. La fila vigente de `macro_history` es lo que de verdad usa el
    # reparto del día, o sea lo que el cliente tiene delante en Nutrición, en Inicio y en el
    # asistente. Cuando alguien escribe uno sin el otro, la ficha enseña una cosa y el
    # cliente come otra: medido en producción el 17-08, 6 de 175 activos, cuatro de ellos con
    # la última fila puesta «por migracion» y dos de ese mismo día. Cliente Demo: la ficha
    # decía 220 g de proteína y el cliente comía 170.
    #
    # No se toca el campo -- lo leen decenas de sitios --, se manda al lado lo que rige hoy y
    # que la pantalla enseñe eso. Es lo mismo que se hizo con el peso en `series_cliente`.
    from macros_por_fecha import ultima_vigente

    vigente = await ultima_vigente(db, client_id)
    if vigente:
        profile["macros_vigentes"] = {
            "entreno": vigente.get("training") or vigente.get("new_training"),
            "descanso": vigente.get("rest") or vigente.get("new_rest"),
            "perientreno": vigente.get("peri"),
            "desde": vigente.get("effective_date"),
            "quien": vigente.get("changed_by"),
        }
        de_hoy = (vigente.get("training") or vigente.get("new_training") or {})
        del_campo = profile.get("macros_training") or {}
        p_hoy = de_hoy.get("protein") or de_hoy.get("proteinas")
        p_campo = del_campo.get("protein") or del_campo.get("proteinas")
        try:
            profile["macros_descuadrados"] = (p_hoy is not None and p_campo is not None
                                              and abs(float(p_hoy) - float(p_campo)) >= 1)
        except (TypeError, ValueError):
            profile["macros_descuadrados"] = False

    from core.plan_access import estado_de_acceso

    return {
        "profile": profile,
        # Si puede entrar en la app y, si no, por qué. Va calculado desde aquí por lo mismo
        # que en la lista: el `status` del perfil no sabe que se le acabó el ciclo.
        "acceso": estado_de_acceso(profile),
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
    """Corrige errores de coma en el peso (819 -> 81.9, 51400 -> 51.4).

    La regla vive en `core.series_cliente`, con el rango del peso. Estaba copiada aqui y en
    `macro_casos.py`, y la pantalla del cliente no tenia ninguna de las dos: por eso el coach
    veia la curva saneada y el cliente veia sus 0 kg (Jesus, 12-08)."""
    from core.series_cliente import sanea_peso
    return sanea_peso(w)


def _sanear_pesos(filas, *campos) -> None:
    """Deja en kilos los campos de peso de una lista de documentos, en el sitio.

    Solo toca lo que es un numero: un peso que no lo sea (o que se salga del rango del
    cuerpo humano) se queda en None, que es lo que la pantalla entiende como «no hay dato».
    Un texto se deja tal cual, porque no es un peso y no le toca a esta funcion decidirlo.
    """
    for fila in (filas or []):
        if not isinstance(fila, dict):
            continue
        for campo in campos:
            if isinstance(fila.get(campo), (int, float)):
                fila[campo] = _sanea_peso(fila[campo])


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


# Lo que contesta el cliente en el reporte ("¿como de viable seria un nuevo ajuste?",
# punto 5 del 05-08) traducido al lenguaje del prompt del agente. Es el MARGEN de la
# persona: cuanto se le puede apretar. Manda sobre el dato del cuestionario inicial,
# que se responde una vez y luego envejece.
_VIABILIDAD_A_MARGEN = {
    "me_adapto": "normal",
    "necesito_mas": "mucho",         # pasa hambre: ajustes suaves
    "necesito_menos": "no_puedo_mas",  # no puede comer mas: subidas suaves
}


def _margen_del_cliente(profile: dict, reporte_app: Optional[dict]) -> Optional[str]:
    v = (reporte_app or {}).get("viabilidad_ajuste")
    if v in _VIABILIDAD_A_MARGEN:
        return _VIABILIDAD_A_MARGEN[v]
    return (profile.get("ajustes_macros") or {}).get("hambre_saturacion")


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
    # El peso de un ajuste va en la curva por la FECHA DEL PESAJE, no por la del ajuste
    # (punto 27 del 07-08): el coach ajusta hoy leyendo un reporte de hace una semana. Los
    # ajustes antiguos no traen `peso_fecha` y se quedan donde estaban.
    async for h in db.macro_history.find({"client_id": client_id},
                                         {"_id": 0, "effective_date": 1, "peso_fecha": 1, "peso": 1, "client_weight": 1}):
        w = _sanea_peso(h.get("peso") if h.get("peso") is not None else h.get("client_weight"))
        fecha_peso = h.get("peso_fecha") or h.get("effective_date")
        if w and fecha_peso:
            pesos[fecha_peso] = w
    async for r in db.reports.find(hasta_hoy({"client_id": client_id}), {"_id": 0, "created_at": 1, "weight": 1}):
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

    # El ultimo reporte hecho EN LA APP (los de arriba son los importados de Calma). De aqui
    # salen el margen del cliente y su proximo objetivo, que es el que dispara la fase.
    # Hasta hoy (punto 22): sin el corte, un reporte importado con fecha de 2028 gana el
    # sort y es el que decide la FASE que se le manda al agente. No es solo que no se
    # enseñe: es que no se calcula con el.
    reporte_app = await db.reports.find_one(
        hasta_hoy({"client_id": client_id}), {"_id": 0}, sort=[("created_at", -1)])
    if (reporte_app or {}).get("proximo_objetivo") in ("definicion", "volumen"):
        fase = reporte_app["proximo_objetivo"]

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
        # El peso del ajuste es el que se guardo CON EL AJUSTE, y su fecha va aparte (punto
        # 27): el ajuste es de hoy y el pesaje puede ser de la semana pasada. Antes se
        # buscaba en la curva por la fecha del ajuste, que es justo lo que desplazaba el dato.
        peso_del_ajuste = _sanea_peso(h.get("peso") if h.get("peso") is not None else h.get("client_weight"))
        historial.append({
            "fecha": fecha,
            "peso": peso_del_ajuste or pesos.get(fecha),
            "peso_fecha": h.get("peso_fecha") or fecha,
            "porcentaje_graso": h.get("body_fat"),
            "criterio": h.get("criterio"),
            "evaluacion": h.get("evaluacion"),
            # Senal de correccion: si ese ajuste salio de una sugerencia de la IA, si el coach
            # la guardo tal cual o cuanto la corrigio (macro a macro). Se venia guardando desde
            # el 26-07 pero no se le devolvia al agente, asi que tropezaba dos veces con la
            # misma piedra en el mismo cliente.
            "origen": h.get("origen"),
            "correccion_coach": h.get("correccion_coach"),
            # QUE PALANCA MOVIO en ese ajuste (punto 31): "descanso.hidratos", no "los ocho
            # numeros cambiaron de A a B". Es la decision del coach, y hasta ahora el agente
            # tenia que deducirla comparando dos filas.
            "palancas": palancas(h.get("cambios")),
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
        # El margen del cliente. Manda lo que haya contestado en el REPORTE de este mes
        # (pregunta "¿como de viable seria un nuevo ajuste?", punto 5 del 05-08): el dato del
        # cuestionario inicial se responde una vez y envejece.
        hambre_saturacion=_margen_del_cliente(profile, reporte_app))
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
    """Dieta de un cliente en una fecha concreta (visor de dietas del admin).

    RESUELTA, no cruda. Esta ruta devolvia el documento tal cual esta en Mongo, y lo que
    hay ahi es un registro incompleto: 3.731 de 4.166 alimentos guardados no traen
    `macros_efectivos`, y en las dietas de Calma los alimentos por unidades guardan piezas
    en `cantidad_g`. De ahi salian los dos primeros fallos del 16-08 -- «todas las lineas
    ponen P0 H0 G0» y «un huevo sale como 1 g» --, en la pantalla desde la que se decide el
    ajuste de 179 personas. Se resuelve por el mismo helper que la ruta del cliente y el PDF.
    """
    profile = await db.client_profiles.find_one({"id": client_id}, {"_id": 0, "user_id": 1, "trainer_id": 1})
    assert_client_access(user, profile)
    diet = await db.diets.find_one(
        {"user_id": profile["user_id"], "fecha": fecha}, {"_id": 0}
    )
    if not diet:
        raise HTTPException(status_code=404, detail="Sin dieta en esa fecha")
    from core.dieta_para_ver import enriquecer_para_ver
    return await enriquecer_para_ver(diet)


@router.put("/clients/{client_id}", response_model=ClientProfile)
async def update_client_admin(client_id: str, data: ClientProfileUpdate, user = Depends(get_admin_user)):
    """Actualizar perfil de cliente (admin)."""
    profile = await db.client_profiles.find_one({"id": client_id})
    assert_client_access(user, profile)

    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    # El coach se cambia solo por PUT /clients/{id}/trainer (ahí viven las reglas de permisos)
    update_data.pop("trainer_id", None)
    # La excepcion (punto 39) es el unico campo donde la cadena VACIA significa algo:
    # "quitala". Con el filtro de arriba, mandar "" la deja tal cual estaba y el coach se
    # queda creyendo que la ha borrado -- justo el tipo de malentendido que este campo
    # existe para evitar.
    if data.excepcion is not None:
        update_data["excepcion"] = data.excepcion.strip()
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
                     # Al cliente no se le nombra el puesto, se le dice quién le lleva (Jesús, 11-08).
                     f"Ahora te lleva {trainer_name}" if trainer_name else "Hay un cambio en quien te lleva",
                     "/dashboard/messages")
        client_user = await db.users.find_one({"id": profile["user_id"]}, {"_id": 0, "name": 1, "email": 1})
        client_name = (client_user or {}).get("name") or (client_user or {}).get("email") or client_id
        await audit(user, "coach", f"Coach de {client_name}: {trainer_name or 'sin asignar'}")
    return {"ok": True, "trainer_id": new_trainer, "trainer_name": trainer_name}

@router.put("/clients/{client_id}/body-fat")
async def anotar_body_fat(client_id: str, data: dict, user = Depends(get_admin_user)):
    """Anota el % graso de una FECHA concreta, la de una sesion de fotos.

    Jesus lo estima mirando las fotos y solo cuando decide ponerlo (documento 05-08,
    punto 3.3): "solo lo estimo en los momentos en que hay foto". Por eso se anota desde
    la foto y no en un campo suelto, y por eso va a una SERIE por fecha y no a un unico
    valor: el % graso en dos momentos es lo que permite medir el eje respondedor del
    perfil, que hoy solo se podia calcular con el historico traido de Calma.

    Guarda en `porcentajes_grasos` del perfil, con el mismo formato que la serie de Calma
    (`{fecha, valor}`), para que las dos se puedan leer juntas.
    """
    profile = await db.client_profiles.find_one({"id": client_id})
    assert_client_access(user, profile)

    fecha = str(data.get("fecha") or "")[:10]
    if not fecha:
        raise HTTPException(status_code=400, detail="Falta la fecha")
    valor = data.get("valor")

    # Borrar el valor de un dia (el coach se arrepiente de una estimacion) no pasa por el
    # modulo de series: lo suyo es anotar, no quitar.
    if valor in (None, ""):
        serie = [x for x in (profile.get("porcentajes_grasos") or []) if str(x.get("fecha"))[:10] != fecha]
        ahora = actual_de_serie(serie)
        await db.client_profiles.update_one({"id": client_id}, {"$set": {
            "porcentajes_grasos": serie, "body_fat": ahora["valor"] if ahora else None}})
        _refrescar_casos()
        return {"porcentajes_grasos": serie, "body_fat": ahora["valor"] if ahora else None}

    try:
        v = round(float(valor), 1)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="El % graso tiene que ser un número")
    if not (3 <= v <= 60):
        raise HTTPException(status_code=400, detail="Un % graso fuera de 3-60 no es un dato, es un error")

    # Por la misma via que el resto (punto 30): la serie manda y `body_fat` es su ultimo.
    await anotar_grasa(client_id, v, fecha, origen=f"foto · {user.get('name', user.get('email', 'coach'))}")
    perfil = await db.client_profiles.find_one(
        {"id": client_id}, {"_id": 0, "porcentajes_grasos": 1, "body_fat": 1})
    _refrescar_casos()   # el eje respondedor depende de esta serie
    return {"porcentajes_grasos": perfil.get("porcentajes_grasos") or [], "body_fat": perfil.get("body_fat")}


def _no_le_ha_tocado_nada(cambios, peri_antes, peri_ahora) -> bool:
    """¿Ha guardado los MISMOS macros que ya tenía? De ahí sale «Este mes no te toco nada».

    Se apoya en `marcar_cambios`, que ya compara macro a macro al guardar, más el
    perientreno: ese bloque puede estrenarse o quitarse entero, y `marcar_cambios` no lo
    marca a propósito (aparecer de la nada no es "cambiar el intra"), pero para el cliente
    sí es un cambio y no se le puede decir que este mes no se le toca nada.

    Con `cambios` a None -- el primer ajuste de su vida -- no hay con qué comparar: eso no
    es que no haya cambiado nada, así que se le manda el aviso normal.
    """
    if cambios is None:
        return False
    return not palancas(cambios) and bool(peri_antes) == bool(peri_ahora)


@router.put("/clients/{client_id}/macros")
async def update_client_macros(client_id: str, data: MacrosUpdate, user = Depends(get_admin_user)):
    """Actualizar macros de un cliente (admin). Marca como override manual.

    DE AQUI SALEN «Tienes macros nuevos» Y «Este mes no te toco nada»: los dos avisos
    cuelgan del ajuste que se escribe en esta ruta (`marcar_cambios` + `marcar_ajuste`).
    Guardar la dieta de un dia NO los dispara, y no puede hacerlo: mientras se monta una
    dieta se guarda muchas veces y al cliente le llegaria un aviso por cada guardado. El
    aviso es de la pestaña Macros, que es donde se decide el ajuste. La otra puerta buena
    es `admin_calculator_apply`; no hay ninguna mas.
    """
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

    # El PESO con el que se hace el ajuste. Es el del reporte que el coach esta leyendo, que
    # puede no ser el que tiene el perfil (punto 25 del 07-08). Si lo informa, manda y
    # actualiza el perfil.
    peso_ajuste = data.peso if data.peso is not None else profile.get("weight")

    # Y se archiva CON LA FECHA DEL PESAJE, no con la del ajuste (punto 27 del 07-08). El
    # 05-08 se pidio lo contrario ("88 kilos con fecha de manana"), pero manda el documento
    # nuevo: el coach ajusta hoy leyendo un reporte de la semana pasada, y si ese peso se
    # guarda con la fecha del ajuste el historico queda desplazado. Y el historico es lo que
    # alimenta el modelo. Sin fecha de pesaje se queda la del ajuste, como hasta ahora.
    peso_fecha = (data.peso_fecha or "").strip() or None
    if peso_fecha and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", peso_fecha):
        raise HTTPException(status_code=400, detail="La fecha del peso tiene que ser AAAA-MM-DD")

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
        # La fecha del pesaje (punto 27). Es la que manda para colocar el peso en la curva.
        "peso_fecha": peso_fecha or effective_date,
        # QUE MACRO SE MOVIO (punto 31): un booleano por macro, comparando con lo que tenia.
        # No toca ningun calculo; es lo que pinta el rojo del historial y lo que le dice al
        # modelo que palanca uso el coach, que hasta ahora no se guardaba en ningun sitio.
        "cambios": marcar_cambios(
            {"entreno": profile.get("macros_training"),
             "perientreno": profile.get("macros_periworkout"),
             "descanso": profile.get("macros_rest")},
            {"entreno": training, "perientreno": set_data.get("macros_periworkout"),
             "descanso": rest},
        ),
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

    # ANTES DE GUARDAR EN EL HISTORIAL, que reescribe `cambios`. Solo hay una fila por día
    # (`core/historial_macros.py`): al segundo guardado del día, `cambios` pasa a comparar
    # con el estado de la mañana, no con el que tenía el cliente hace un minuto. Eso es lo
    # que quiere el historial, y lo contrario de lo que quiere el aviso: tocar los macros a
    # las 10:00 y volver a guardar los mismos a las 12:00 le mandaba "tienes macros nuevos"
    # las dos veces.
    #
    # El perientreno solo se escribe si viene en la petición: omitirlo NO se lo quita al
    # cliente, así que lo que tiene después es lo nuevo o, si no vino, lo de antes.
    peri_despues = (set_data.get("macros_periworkout") if data.peri is not None
                    else profile.get("macros_periworkout"))
    sin_cambios = _no_le_ha_tocado_nada(macro_log["cambios"],
                                        profile.get("macros_periworkout"), peri_despues)

    await guardar_en_historial(macro_log)
    # "¿Quien me toca esta semana?" (punto 29): la fecha se queda tambien en el cliente.
    await marcar_ajuste(client_id, fecha_de_vigencia(macro_log))
    # Peso y % graso van a sus SERIES, con la fecha del pesaje (puntos 27 y 30). Ni uno ni
    # otro se escriben sueltos en el perfil: el "actual" sale siempre del ultimo de la serie.
    if data.peso is not None:
        await anotar_peso(client_id, data.peso, peso_fecha or effective_date, origen="ajuste del coach")
    if data.porcentaje_graso is not None:
        await anotar_grasa(client_id, data.porcentaje_graso, peso_fecha or effective_date,
                           origen="ajuste del coach")

    # El banco de casos (clientes gemelos) se refresca solo con cada ajuste nuevo.
    _refrescar_casos()

    await avisar_macros(profile["user_id"], nota=data.note, sin_cambios=sin_cambios)
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

    # Si se corrige una entrada, hay que recalcular que macro cambio (punto 31): si no, el
    # rojo del historial seguiria senalando los de antes de la correccion.
    set_data["cambios"] = marcar_cambios(
        {"entreno": entry.get("previous_training"),
         "perientreno": entry.get("previous_peri"),
         "descanso": entry.get("previous_rest")},
        {"entreno": training, "perientreno": set_data.get("peri", entry.get("peri")),
         "descanso": rest},
    )

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
    `ajustes` opcional en el body; si no llega, se usan los guardados del cliente.

    La otra puerta de la que salen «Tienes macros nuevos» y «Este mes no te toco nada»,
    junto a `update_client_macros`. Guardar la dieta de un dia no los dispara: se guarda
    muchas veces mientras se monta y el cliente recibiria un aviso por cada guardado.
    """
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

    # Ni `weight` ni `body_fat` van aqui: los pone `anotar_peso`/`anotar_grasa` a partir de
    # sus series, mas abajo (punto 30). Escribirlos sueltos es lo que hacia que la app
    # pudiera ensenar dos pesos distintos.
    set_data = {
        "sex": sexo,
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
        # Que macro se movio (punto 31).
        "cambios": marcar_cambios(
            {"entreno": profile.get("macros_training"),
             "perientreno": profile.get("macros_periworkout"),
             "descanso": profile.get("macros_rest")},
            {"entreno": training, "perientreno": peri, "descanso": rest},
        ),
        "criterio": data.get("criterio"),
        # Explicito, no por el fallback a created_at: asi el coach puede decir desde cuando
        # aplica, igual que en el guardado manual.
        "effective_date": data.get("effective_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "motor": {"version": resultado["version_motor"], "desglose": resultado["desglose"],
                  "ajustes": ajustes},
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    # Antes de guardarlo: el historial reescribe `cambios` al segundo guardado del día
    # (una fila por día, ver el comentario del guardado manual).
    sin_cambios = _no_le_ha_tocado_nada(macro_log["cambios"],
                                        profile.get("macros_periworkout"), peri)

    await guardar_en_historial(macro_log)
    await marcar_ajuste(client_id, fecha_de_vigencia(macro_log))   # punto 29
    # Peso y % graso, a sus series con la fecha del ajuste (punto 30).
    await anotar_peso(client_id, peso, macro_log["effective_date"], origen="calculadora del coach")
    await anotar_grasa(client_id, bf, macro_log["effective_date"], origen="calculadora del coach")

    # GUARDAR SIEMPRE las respuestas/calculo (calibracion futura)
    await guardar_quiz_respuestas(
        user_id=profile["user_id"], client_id=client_id, origen="coach",
        respuestas=ajustes or {}, resultado=resultado,
        contexto={"peso": float(peso), "porcentaje_graso": float(bf),
                  "sexo": sexo, "objetivo": objetivo},
    )

    await avisar_macros(profile["user_id"], nota=note, sin_cambios=sin_cambios)
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
        if not plan_code:
            # QUITARLE EL PLAN. Los dos sitios del panel que lo editan -- la lista de
            # usuarios y la ficha del cliente -- traen «Sin plan» como primera opcion y
            # mandan `null`, pero aqui todo pasaba por el catalogo y `PLAN_CATALOG.get("")`
            # no da entrada: se respondia «Plan no valido». Asignar un plan se podia,
            # quitarlo no, asi que uno puesto por error solo se arreglaba tocando la base.
            #
            # Sin plan no hay acceso y no hace falta nada mas: `estado_de_acceso` devuelve
            # `sin_plan` aunque el perfil siga "activo", y las funciones de pago exigen una
            # feature, que un perfil sin plan no tiene (`plan_features(None)` es la lista
            # vacia). No se toca el `status` -- para dejar a alguien fuera esta la baja
            # logica -- ni el `cycle_start`, que ya se reinicia solo el dia que se le
            # vuelva a asignar plan.
            set_user["plan"] = None
            set_prof["plan"] = None
            # La cortesia lo era de un plan que ya no tiene. Dejarla puesta marcaria como
            # «precio cortesia» en la ficha a alguien que no tiene membresia ninguna.
            set_user["comp_plan"] = False
            set_prof["comp_plan"] = False
        else:
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

    # Sin el equipo: son 11 perfiles con plan que no son negocio (ver _fuera_el_equipo).
    solo_clientes = await _fuera_el_equipo()
    total = await db.client_profiles.count_documents(solo_clientes)
    active = await db.client_profiles.count_documents({**solo_clientes, "status": "activo"})
    inactive = await db.client_profiles.count_documents(
        {**solo_clientes, "status": {"$in": ["inactivo", "baja", "cancelado"]}})
    # EL HUECO DE LOS CUATRO (punto 2.4g): «"0 bajas" con 188 totales y 184 activos: faltan
    # cuatro por algún sitio». Son los `pendiente_pago` y demás estados intermedios, que no
    # caían ni en activos ni en bajas y desaparecían de la suma. Un total que no cuadra con
    # sus partes hace que no te creas ninguna de las tres cifras.
    otros = max(0, total - active - inactive)

    # HAY QUE MIRARLOS (punto 32 del 07-08). Antes esto era "en riesgo": activo, semana >= 3
    # y sin reporte en 14 dias. Saltaba para el 76% de los activos, o sea que no era una
    # alerta: era el color de fondo de la pantalla. Y no distinguia a quien va regular de
    # quien va mal ni en que.
    #
    # Ahora se cuenta con el mismo semaforo de la lista, que mide cada celda contra el plazo
    # DE SU PLAN y no contra un 14 fijo, y solo cuenta el que tiene alguna celda en
    # regular-malo o peor. Los `info` (lo que su plan no incluye) no cuentan.
    active_profiles = await db.client_profiles.find(
        {**solo_clientes, "status": "activo"},
        # OJO con `status`: `has_active_access` lo lee, y sin el en la proyeccion daba
        # "pago pendiente" a todo el mundo y el semaforo salia rojo entero.
        {"_id": 0, "id": 1, "user_id": 1, "plan": 1, "created_at": 1, "cycle_start": 1,
         "status": 1, "ultimo_ajuste": 1, "ultimo_reporte": 1, "pesos": 1,
         "stripe_subscription_id": 1, "subscription_status": 1, "access_until": 1},
    ).to_list(2000)
    staff_ids = set(await db.users.distinct("id", {"role": {"$in": ["admin", "trainer"]}}))
    hablado_a: Dict[str, str] = {}
    async for m in db.messages.find({"sender_id": {"$in": list(staff_ids)}},
                                    {"_id": 0, "receiver_id": 1, "created_at": 1}):
        uid, ca = m.get("receiver_id"), m.get("created_at")
        if uid and ca and (uid not in hablado_a or ca > hablado_a[uid]):
            hablado_a[uid] = ca

    # POR CELDA, no por fila. Con cuatro celdas, "tiene alguna en rojo" es cierto para casi
    # todo el mundo y volveriamos a la alerta que nadie mira. Lo que sirve es saber CUANTOS
    # y EN QUE: "78 sin mandar reporte a tiempo, 72 sin pesarse, 33 sin que nadie les hable".
    CELDAS = ("reporte", "ajuste", "contacto", "peso", "pago")
    reparto = {c: {semaforo.OK: 0, semaforo.REGULAR: 0, semaforo.REGULAR_MALO: 0,
                   semaforo.MALO: 0, semaforo.INFO: 0} for c in CELDAS}
    at_risk = 0
    for p in active_profiles:
        s = _semaforo_del_cliente(p, hablado_a, now)
        for c in CELDAS:
            reparto[c][s[c]["estado"]] += 1
        if s["peor"] == semaforo.MALO:
            at_risk += 1

    # Bajas DEL MES (punto 2.4g): `first_of_month` se calculaba arriba y no se usaba, así
    # que «bajas del mes» eran todas las bajas de la historia. Se cuenta por cuándo se dio
    # de baja, y si esa fecha no está, por la última vez que se tocó el perfil.
    bajas_mes = await db.client_profiles.count_documents({
        **solo_clientes,
        "status": {"$in": ["baja", "cancelado", "inactivo"]},
        "$or": [
            {"baja_fecha": {"$gte": first_of_month.isoformat()}},
            {"baja_fecha": {"$exists": False}, "updated_at": {"$gte": first_of_month.isoformat()}},
        ],
    })

    # Plan distribution + MRR en una sola agregación. Cubre TODOS los planes del
    # catálogo (activos, legacy, especiales), no solo los cuatro históricos.
    plans = {}
    mrr = 0
    # El MRR se calcula en Python y no con una agregación porque hace falta el catálogo:
    # el precio del cliente casi nunca está en su perfil (168 de 174 lo tienen vacío) y hay
    # que normalizar el ciclo a meses. Sumando `price` a secas salían 2.115 € con 184
    # activos -- 11,50 € por cliente y mes, con planes que van de 60 a 1.500 €.
    from routes.plans import _overrides_by_code
    from models.user import merged_catalog
    catalogo = merged_catalog(await _overrides_by_code())
    for p in await db.client_profiles.find(
            {**solo_clientes, "status": "activo"},
            {"_id": 0, "plan": 1, "price": 1}).to_list(3000):
        plan = p.get("plan") or "sin_plan"
        plans[plan] = plans.get(plan, 0) + 1
        mrr += precio_mensual(p, catalogo)
    mrr = round(mrr, 2)

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
        # El reparto POR CELDA: cuantos van bien, regular y mal en cada cosa. Es lo que
        # deja decir "78 sin reporte a tiempo" en vez de una cifra que no distingue nada.
        "semaforo": reparto,
        "bajas_mes": bajas_mes,
        "inactive_clients": inactive,
        # Los que no son ni activos ni bajas (punto 2.4g): total = activos + bajas + otros.
        "otros_clients": otros,
        # Y EN QUÉ ESTADO ESTÁN, que la suma ya cuadraba pero la pantalla no los nombraba
        # (punto 63, QA del 15-08). «+ 5 ni activos ni de baja» no le dice a nadie qué
        # hacer; «4 pendientes de pago y 1 registrado» sí. En producción son eso.
        "otros_por_estado": [
            {"estado": d["_id"] or "sin estado", "n": d["n"]}
            for d in await db.client_profiles.aggregate([
                {"$match": {**solo_clientes,
                            "status": {"$nin": ["activo", "inactivo", "baja", "cancelado"]}}},
                {"$group": {"_id": "$status", "n": {"$sum": 1}}},
                {"$sort": {"n": -1}},
            ]).to_list(10)
        ],
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

    # Del catálogo, como el resto (punto 2.4b): aquí salía «jose · GOLD · 0 EUR» y «GOLD ·
    # 149 EUR», que no son precios de ningún plan. Los dos venían del `price` en crudo.
    from routes.plans import _overrides_by_code
    from models.user import merged_catalog
    catalogo = merged_catalog(await _overrides_by_code())
    results = []
    for p in profiles:
        user_data = umap.get(p["user_id"])
        results.append({
            "client_id": p["id"],
            "name": user_data.get("name", "?") if user_data else "?",
            "email": user_data.get("email", "") if user_data else "",
            "plan": p.get("plan"),
            "price": precio_de_ciclo(p, catalogo),
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

    # UN CONTADOR NO PUEDE SER MAYOR QUE EL TOTAL.
    #
    # «Sin contacto: 234» sobre 228 clientes (Jesús, 11-08). El motivo es que esta consulta
    # contaba con el equipo dentro y los totales del panel (/admin/stats) los dejan fuera
    # desde el 09-08: dos bases distintas para números que se leen juntos en la misma
    # pantalla. Los perfiles del equipo existen para poder probar la app en modo cliente,
    # así que no son trabajo pendiente de nadie.
    profiles = await db.client_profiles.find(
        {**await _fuera_el_equipo(), "status": {"$in": ["activo", "pago_pendiente"]}},
        {"_id": 0, "id": 1, "user_id": 1, "plan": 1, "status": 1, "macros_training": 1,
         "stripe_subscription_id": 1, "subscription_status": 1, "access_until": 1,
         "cycle_start": 1, "created_at": 1, "ultimo_ajuste": 1, "ultimo_reporte": 1},
    ).to_list(3000)

    uids = [p["user_id"] for p in profiles if p.get("user_id")]
    users = await db.users.find(
        {"id": {"$in": uids}}, {"_id": 0, "id": 1, "name": 1, "email": 1}
    ).to_list(len(uids) or 1)
    umap = {u["id"]: u for u in users}

    # Rutinas activas y reportes recientes: una consulta cada uno (no N+1).
    active_routine_clients = set(await db.routines.distinct("client_id", {"status": "active"}))
    cutoff = (now - timedelta(days=10)).isoformat()
    # Con tope hoy (punto 22): un reporte fechado en 2027 cumple el «>= cutoff» y contaba
    # como reporte reciente, o sea que tapaba a su cliente en «Reporte pendiente».
    recent = await db.reports.find(
        hasta_hoy({"created_at": {"$gte": cutoff}}), {"_id": 0, "client_id": 1, "created_at": 1}
    ).to_list(5000)
    last_report: Dict[str, str] = {}
    for r in recent:
        cid, ca = r.get("client_id"), r.get("created_at")
        if cid and (cid not in last_report or ca > last_report[cid]):
            last_report[cid] = ca

    # Cuándo se le habló por última vez. Solo cuentan los mensajes que SALEN del equipo:
    # que el cliente escriba no es contacto, es justo lo contrario -- si escribió y nadie
    # le contestó, ese cliente tiene que salir en rojo, no desaparecer de la lista.
    staff_ids = set(await db.users.distinct("id", {"role": {"$in": ["admin", "trainer"]}}))
    ultimo_contacto: Dict[str, str] = {}
    async for m in db.messages.find(
        {"sender_id": {"$in": list(staff_ids)}},
        {"_id": 0, "receiver_id": 1, "created_at": 1},
    ):
        uid, ca = m.get("receiver_id"), m.get("created_at")
        if uid and ca and (uid not in ultimo_contacto or ca > ultimo_contacto[uid]):
            ultimo_contacto[uid] = ca

    sin_macros, sin_rutina, reporte_pendiente, sin_contacto = [], [], [], []
    te_tocan = []
    con_rutina_en_plan = 0
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
        if plan_grants_feature(p.get("plan"), "rutina"):
            # Contamos también a cuántos les tocaría tener rutina, no solo a los que no la
            # tienen. El panel lo necesita para saber si «sin rutina» señala un pendiente o
            # está describiendo el estado normal de la casa (227 de 228), en cuyo caso deja
            # de ocupar una columna. Sin el total no se puede distinguir una cosa de la otra.
            con_rutina_en_plan += 1
            if p["id"] not in active_routine_clients:
                sin_rutina.append(base)

        # Sin contacto: cuántos días lleva sin que nadie del equipo le hable. Solo para
        # los planes que incluyen chat -- al de autogestión no se le acompaña por ahí, así
        # que sacarlo en esta lista sería ruido todos los días.
        #
        # Y no hay umbral: se enseñan todos con sus días. Poner el corte en el panel (en
        # rojo a partir de X) es decisión de quien mira, no del servidor, y cada plan tiene
        # su ritmo: al de 1.500 con llamada semanal, quince días es un escándalo; al de 897
        # con reporte quincenal, no tanto.
        # El chat NO está en `habilitaciones` (ahí viven calculadora, rutina, reportes,
        # suplementación, harbiz y acompañamiento): está en las features del plan.
        if plan_grants_feature(p.get("plan"), "chat"):
            visto = ultimo_contacto.get(p.get("user_id"))
            desde = visto or p.get("cycle_start") or p.get("created_at")
            dias = None
            if desde:
                try:
                    d = datetime.fromisoformat(str(desde).replace("Z", "+00:00"))
                    if d.tzinfo is None:
                        d = d.replace(tzinfo=timezone.utc)
                    dias = (now - d).days
                except (ValueError, TypeError):
                    dias = None
            sin_contacto.append({**base, "dias": dias, "nunca": visto is None})

        # "¿A quien le toca esta semana?" (punto 29). Solo los planes que llevan ajuste del
        # coach: al de autogestion no le "toca" nadie. Se ordena por lo que lleva sin que le
        # muevan los macros, y el que nunca los ha tenido movidos va arriba del todo -- que
        # es justo el que se pierde cuando esto se lleva en una hoja aparte.
        if hab.get("calculadora") == "personalizado":
            desde_ajuste = dias_desde(p.get("ultimo_ajuste"), now)
            te_tocan.append({
                **base,
                "ultimo_ajuste": p.get("ultimo_ajuste"),
                "ultimo_reporte": p.get("ultimo_reporte"),
                "dias_sin_ajuste": desde_ajuste,
                "dias_sin_reporte": dias_desde(p.get("ultimo_reporte"), now),
                "nunca_ajustado": not p.get("ultimo_ajuste"),
            })

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
        "con_rutina_en_plan": con_rutina_en_plan,
        "reporte_pendiente": reporte_pendiente,
        # De más abandonado a menos: el que lleva más tiempo sin que nadie le hable va
        # arriba, que es donde hay que mirar primero.
        "sin_contacto": sorted(sin_contacto, key=lambda x: -(x["dias"] or 0)),
        # De más abandonado a menos, y el que nunca se ha tocado por delante de todos.
        "te_tocan": sorted(te_tocan, key=lambda x: (0 if x["nunca_ajustado"] else 1,
                                                    -(x["dias_sin_ajuste"] or 0))),
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

async def _siguiente_id_de_alimento() -> int:
    """El siguiente id LIBRE del catalogo, como numero.

    Los 3.211 alimentos tienen id entero, y medio backend cuenta con ello: `agent_tools`
    hace `int(f["id"])` al cargar el catalogo en tres sitios. Un alimento con id de texto
    revienta ahi con ValueError y **deja al asistente sin funcionar para todos los
    clientes**, no solo para quien lo use.

    El alta desde el panel escribia `str(uuid.uuid4())`. En produccion todavia no ha pasado
    (0 alimentos con id no numerico), pero el primero que diera de alta el equipo tumbaba el
    chat entero. Lo encontro la tanda de casos del 12-08 cuando un test creo uno.
    """
    ultimo = await db.foods.find_one({"id": {"$type": ["int", "long", "double"]}},
                                     {"_id": 0, "id": 1}, sort=[("id", -1)])
    return int((ultimo or {}).get("id") or 0) + 1


def _food_doc_from_fields(f: dict, categorias: Optional[str], nuevo_id=None) -> dict:
    """Construye un documento de db.foods a partir de los campos de una sugerencia/alta."""
    por_unidad = bool(f.get("por_unidad"))
    racion = float(f.get("racion") or 100) or 100.0
    proteinas = float(f.get("proteinas") or 0)
    hidratos = float(f.get("hidratos") or 0)
    grasas = float(f.get("grasas") or 0)
    url = (f.get("url") or "").strip() or None
    return {
        # Numerico, nunca un UUID: ver `_siguiente_id_de_alimento`.
        "id": nuevo_id if nuevo_id is not None else str(uuid.uuid4()),
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

    # SIN CATEGORIA NO SE APRUEBA.
    #
    # La categoria no es una etiqueta de adorno: es la que decide que excepcion del filtro del
    # tercio se le aplica -- cereales y panes, tuberculos y frutas, aceites y frutos secos --,
    # o sea QUE MACROS LE CUENTAN al cliente. Un alimento aprobado sin ella entra al catalogo
    # sin que nadie sepa como debe contar, y eso no se ve: se ve meses despues, en las cuentas
    # de alguien que no cuadra.
    #
    # Aqui se aprobaba sin mirarlo, y la ficha pendiente lo decia a la cara: «Categorias: sin
    # asignar». Lo encontro Jesus el 11-08 y es el hallazgo mas fino de su repaso.
    if not str(doc.get("categorias") or "").strip():
        raise HTTPException(
            status_code=400,
            detail="Ponle una categoría antes de aprobarlo: de ella depende qué macros le "
                   "cuentan al cliente. Edítalo y vuelve a intentarlo.",
        )

    food_doc = _food_doc_from_fields(doc.get("food") or {}, doc.get("categorias"),
                                     await _siguiente_id_de_alimento())
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
    # La categoria decide QUE MACROS le cuentan al cliente. Sin ella el alimento no entra en
    # ninguna excepcion del filtro y cuenta sus tres macros crudos para siempre. Aprobar una
    # sugerencia sin categoria ya estaba cerrado (11-08); esta puerta, la del alta a mano, se
    # quedo abierta, y es la que mas se usa (caso 37 de la lista del 12-08).
    if not (data.categorias or "").strip():
        raise HTTPException(
            status_code=400,
            detail="Ponle una categoría: de ella depende qué macros le cuentan al cliente.",
        )
    racion = 100.0 if not data.por_unidad else max(float(data.racion or 0), 1.0)
    food_doc = _food_doc_from_fields(
        {**data.model_dump(), "racion": racion}, data.categorias,
        await _siguiente_id_de_alimento()
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
