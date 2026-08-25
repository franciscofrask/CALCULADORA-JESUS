"""
Rutas de rutinas: obtener, generar con IA, guardar.
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import uuid
import os
import json
import logging
import re

from core.database import db
from core.dias_de_entreno import dias_de_entreno
from core.security import (
    get_current_user, get_admin_user, solo_admin_borra_catalogo, assert_client_access,
)
from core.sin_futuro import hasta_hoy
from core.plan_access import require_access, rutina_visible_para_el_cliente
from routes.notifications import avisar_rutina_nueva, _hay_aviso_de_hoy
from models.common import RoutineResponse, RoutineCreate
from models.user import PLAN_TYPES
from llm_client import LlmChat, UserMessage

router = APIRouter(prefix="/routines", tags=["routines"])

@router.get("/current", response_model=Optional[RoutineResponse])
async def get_current_routine(ctx = Depends(require_access("rutina"))):
    """Obtener rutina actual del cliente (requiere plan con rutina y suscripción activa)."""
    profile = ctx["profile"]

    routine = await db.routines.find_one(
        {"client_id": profile["id"], "status": "active"},
        {"_id": 0}
    )

    if not routine:
        return None

    # TAMBIÉN AL LEER (24-08). Sanear solo al escribir deja fuera lo que YA está guardado:
    # una fila vieja con las series en blanco seguía tumbando esta llamada con un 500, y el
    # cliente se quedaba con «No hemos podido cargar tu rutina» y un «Volver a intentarlo»
    # que no podía funcionar nunca. Aquí no se escribe en la base: se arregla lo que se
    # manda a pintar, que es lo único que necesita el cliente para ver su rutina hoy.
    routine["days"] = _rutina_pintable(routine.get("days"))
    return RoutineResponse(**routine)

# ── LA PETICIÓN DE LA RUTINA DEL MES, APUNTADA (24-08) ───────────────────────────────
#
# Hasta hoy pulsar «Quiero mi rutina · 57 €» solo escribía un aviso en la campana del
# equipo: no quedaba ni rastro en el perfil. El cliente pagaba, leía el mensaje, recargaba
# la pantalla y volvía a ver el botón como si no hubiera pasado nada; y podía volver a
# pulsarlo (pasadas 24 h la clave de idempotencia de Stripe ya no frena el segundo cargo).
# Desde aquí la petición se guarda en su ficha y la pantalla la lee para decirle cuándo la
# pidió en vez de volver a venderle lo mismo.
#
# LA RUTINA ES DEL MES, así que la petición vale un mes: pasado el plazo, si sigue sin
# rutina, puede volver a pedirla. Sin plazo, quien no llegara a recibirla se quedaba sin
# forma de reclamarla desde la app.
#
# Y SON DOS PUERTAS, no una: la misma rutina se pide desde aquí y marcando «Sí» en el
# reporte mensual, que cobra igual y no deja rastro en la ficha. Por eso el candado
# pregunta también por su último reporte (`_pedida_en_su_reporte`). Queda el otro sentido,
# que no se arregla desde este fichero: el reporte le sigue preguntando a quien ya la pidió
# aquí (`routes/reports.py` y `components/reports/ReporteMensual.jsx`).
DIAS_QUE_VALE_LA_PETICION = 30


def _peticion_de_rutina_viva(profile: Dict[str, Any], hoy) -> Optional[Dict[str, Any]]:
    """La petición de la rutina del mes si todavía cuenta, o None."""
    pedida = (profile or {}).get("rutina_mes_pedida") or {}
    try:
        cuando = datetime.fromisoformat(str(pedida.get("fecha"))).date()
    except (TypeError, ValueError):
        return None
    return pedida if (hoy - cuando).days < DIAS_QUE_VALE_LA_PETICION else None


async def _pedida_en_su_reporte(client_id: Optional[str], hoy) -> Optional[Dict[str, Any]]:
    """La rutina del mes pedida por LA OTRA PUERTA: marcando «Sí, básica/avanzada» en el
    reporte mensual (`routes/reports.py`, que cobra los 57 € y no escribe nada en la ficha).

    Mirando solo `rutina_mes_pedida` el candado tapaba media puerta: quien la marcó en su
    reporte el día 1 abría Mi rutina el día 5, veía el botón y pagaba OTRA VEZ. Y Stripe no
    lo frena ni dentro de las 24 h, porque las claves de idempotencia de las dos puertas son
    distintas (`rutina_del_mes:{perfil}:{report_id}` contra `...:None`,
    `core/rutina_del_mes.py`). El segundo cargo de 57 € es el fallo caro de todo esto.

    Se pregunta por el reporte y no por el aviso del equipo porque el reporte es el dato del
    cliente: el aviso se puede archivar y el reporte no. Con `hasta_hoy` por el punto 22: hay
    reportes importados de Calma fechados en 2028 y uno de esos, sin tope, dejaría a su
    dueño sin poder pedir la rutina nunca más.
    """
    if not client_id:
        return None
    from datetime import timedelta
    from core.tiempo import a_madrid
    desde = (hoy - timedelta(days=DIAS_QUE_VALE_LA_PETICION)).isoformat()
    reporte = await db.reports.find_one(
        hasta_hoy({"client_id": client_id,
                   "entreno.rutina_del_mes": {"$in": ["basica", "avanzada"]},
                   "created_at": {"$gte": desde}}),
        {"_id": 0, "created_at": 1, "entreno": 1},
        sort=[("created_at", -1)],
    )
    if not reporte:
        return None
    cuando = a_madrid(reporte.get("created_at"))
    return {"fecha": (cuando.date() if cuando else hoy).isoformat(),
            "modalidad": (reporte.get("entreno") or {}).get("rutina_del_mes"),
            "origen": "reporte_mensual"}


async def _peticion_viva(profile: Dict[str, Any], hoy) -> Optional[Dict[str, Any]]:
    """La petición de la rutina del mes que todavía cuenta, venga por la puerta que venga:
    la de esta pantalla (apuntada en la ficha) o la del reporte mensual."""
    return (_peticion_de_rutina_viva(profile, hoy)
            or await _pedida_en_su_reporte((profile or {}).get("id"), hoy))


@router.get("/quiero-la-rutina")
async def estado_de_la_peticion(user = Depends(get_current_user)):
    """¿Ya pidió la rutina del mes, y cuándo? Lo que la pantalla necesita para no volver
    a enseñarle el botón de 57 € a quien ya la pagó."""
    from core.tiempo import hoy_madrid
    profile = await db.client_profiles.find_one(
        {"user_id": user["id"]}, {"_id": 0, "id": 1, "rutina_mes_pedida": 1})
    pedida = await _peticion_viva(profile, hoy_madrid())
    if not pedida:
        return {"pedida": False}
    return {"pedida": True, "fecha": pedida.get("fecha"),
            "modalidad": pedida.get("modalidad"),
            # Del cobro solo se habla cuando consta que NO entró. De la pedida en el reporte
            # aquí no sabemos si se cobró (eso vive en el aviso del equipo), y decirle «se
            # quedó pendiente» a quien ya pagó asusta para nada. La cuenta de laboratorio
            # tampoco tiene nada pendiente: no se le cobra a propósito.
            "cobro_pendiente": (pedida.get("cobrado") is False
                                and pedida.get("motivo") != "cuenta_de_pruebas"),
            # Si ya se le ha puesto la rutina del mes vigente, cuál es.
            "rutina_puesta": pedida.get("rutina_puesta")}


@router.post("/quiero-la-rutina")
async def quiero_la_rutina(data: dict, user = Depends(get_current_user)):
    """«Quiero mi rutina» (P72 del doc 23-08): cobro directo a la tarjeta que ya tiene.

    HOY NO LO LLAMA NADIE (24-08). Desde que la rutina del mes se compra por Stripe Checkout
    (`POST /billing/rutina-del-mes/checkout`), Mi rutina usa esa puerta y este endpoint se
    quedó sin ninguna pantalla detrás: aquí solo podía comprar el que tuviera tarjeta
    guardada, y al que no la tiene -- el que viene de Calma, el de Calculadora -- se le
    apuntaba la petición sin cobrar y se quedaba esperando a que alguien le escribiera.
    Y ojo con lo que NO es: el «Sí» del reporte mensual tampoco pasa por aquí, llama
    directamente a `core.rutina_del_mes.cobrar` (`routes/reports.py`). Se deja vivo porque
    cobrar en la tarjeta que ya está guardada sigue siendo válido el día que se quiera
    ofrecer sin sacar al cliente de la app; lo que no puede es cobrar dos veces, y de eso se
    encarga `_peticion_viva`, que consultan las dos puertas antes de cobrar.
    El GET de al lado sí se usa: es el que lee la pantalla.

    Reutiliza EXACTAMENTE el circuito del reporte mensual del Bronze (19-08):
    `core/rutina_del_mes.cobrar` (57 EUR en la tarjeta guardada, con el freno de las
    cuentas de pruebas) y el aviso al equipo con el estado del cobro. Si el cobro no
    entra, la petición queda avisada igual: lo que no se hace es perderla.
    """
    from core.tiempo import hoy_madrid

    modalidad = str((data or {}).get("modalidad") or "").strip()
    if modalidad not in ("basica", "avanzada"):
        raise HTTPException(status_code=400, detail="Dinos si la quieres básica o avanzada.")

    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    # El que YA tiene rutina activa no compra otra por error.
    activa = await db.routines.find_one({"client_id": profile["id"], "status": "active"}, {"_id": 1})
    if activa:
        raise HTTPException(status_code=400, detail="Ya tienes una rutina activa.")

    # Ni el que ya la pidió este mes, POR CUALQUIERA DE LAS DOS PUERTAS (aquí o marcándola
    # en su reporte mensual): el segundo cargo de 57 € es el fallo caro y se para antes de
    # llamar a `cobrar`, que es lo irreversible.
    if await _peticion_viva(profile, hoy_madrid()):
        raise HTTPException(
            status_code=400,
            detail="Ya nos pediste tu rutina y estamos con ella. Te llega en unos días.")

    # NO SE COBRA LO QUE NO SE PUEDE ENTREGAR (verificación 24-08, fallo 14). El mismo
    # candado que la puerta de Stripe (`billing.comprar_la_rutina_del_mes`), y por la misma
    # razón: sin plantilla marcada ni PDF del mes preparado, aquí se pasaban 57 EUR por la
    # tarjeta y lo único que pasaba después era un aviso pidiendo entregarla a mano.
    if not await hay_rutina_del_mes_que_entregar():
        logging.getLogger("uvicorn.error").warning(
            "Rutina del mes: %s quiso comprarla y no hay ninguna preparada", profile.get("id"))
        raise HTTPException(
            status_code=409,
            detail="La rutina de este mes todavía no está lista. En cuanto la tengamos "
                   "podrás comprarla desde aquí.")

    from core.avisos_equipo import avisar_al_equipo
    from core.rutina_del_mes import PRECIO_EUR, cobrar

    cobro = await cobrar(profile, modalidad, None)

    # LO PRIMERO DESPUÉS DEL COBRO, que es lo irreversible: dejar constancia en su ficha.
    # De paso se le quita el aplazamiento («pregúntame en una semana»), igual que hace el
    # reporte al contestar (routes/reports.py): el que aplazó y luego compró recibía igual
    # el recordatorio «¿Te preparamos la rutina del mes?».
    #
    # De todo lo que se guarda aquí, la pantalla solo lee `fecha`, `modalidad` y `cobrado`.
    # `cuando`, `motivo`, `payment_intent` e `importe_eur` son TRAZABILIDAD y no los lee
    # ningún endpoint: son con lo que se contesta «¿cuándo la pidió y por qué no se le
    # cobró?» mirando su ficha, y el `payment_intent` es lo que se busca en Stripe el día que
    # haya que devolverle el dinero. `origen` hoy vale siempre lo mismo porque la otra puerta
    # (el reporte mensual) no escribe aquí: se lee desde `_pedida_en_su_reporte`.
    await db.client_profiles.update_one(
        {"id": profile["id"]},
        {"$set": {"rutina_mes_pedida": {
            "fecha": hoy_madrid().isoformat(),
            "cuando": datetime.now(timezone.utc).isoformat(),
            "modalidad": modalidad,
            "cobrado": bool(cobro["cobrado"]),
            "motivo": cobro.get("motivo"),
            "payment_intent": cobro.get("payment_intent"),
            "importe_eur": PRECIO_EUR,
            "origen": "pantalla_rutina",
        }},
         "$unset": {"rutina_mes_aplazada_hasta": ""}},
    )

    nombre = user.get("name") or user.get("email") or "Un cliente"
    etiqueta = "básica" if modalidad == "basica" else "avanzada"
    if cobro["cobrado"]:
        estado = f"Cobrados {PRECIO_EUR:.0f} € en su tarjeta."
    else:
        porques = {
            "sin_tarjeta": "no tiene tarjeta guardada",
            "requiere_autenticacion": "su banco pide que lo confirme él",
            "rechazada": "la tarjeta la rechazó",
            "sin_stripe": "los pagos no están configurados en este entorno",
            "cuenta_de_pruebas": "es una cuenta de pruebas (no se cobra de verdad)",
        }
        estado = ("SIN COBRAR: " + porques.get(cobro.get("motivo"), str(cobro.get("motivo")))
                  + ". Hay que cobrárselo a mano.")

    await avisar_al_equipo(
        db, tipo="rutina_del_mes",
        titulo="Quiere la rutina del mes",
        mensaje=f"{nombre} ha pedido la rutina del mes {etiqueta} ({PRECIO_EUR:.0f} €) "
                f"desde la pantalla de Rutina. {estado}",
        client_id=profile["id"], trainer_id=profile.get("trainer_id"),
        extra={"modalidad": modalidad, "cobrado": cobro["cobrado"],
               "motivo": cobro.get("motivo"), "payment_intent": cobro.get("payment_intent"),
               "importe_eur": PRECIO_EUR, "origen": "pantalla_rutina"},
    )
    # Al cliente, la verdad de lo que ha pasado, sin tecnicismos.
    return {
        "ok": True,
        "cobrado": cobro["cobrado"],
        "pedida_el": hoy_madrid().isoformat(),
        "modalidad": modalidad,
        "mensaje": ("Hecho. Te hemos cobrado los 57 € y el equipo se pone con tu rutina: "
                    "la tendrás cargada aquí en cuanto esté."
                    if cobro["cobrado"] else
                    "Tu petición está apuntada y el equipo se pone con ella. El cobro no ha "
                    "podido hacerse ahora: te escribiremos para resolverlo."),
    }


@router.get("/history", response_model=List[RoutineResponse])
async def get_routine_history(ctx = Depends(require_access("rutina"))):
    """Obtener historial de rutinas (requiere plan con rutina y suscripción activa)."""
    profile = ctx["profile"]

    routines = await db.routines.find(
        {"client_id": profile["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(20)

    # UNA RUTINA VIEJA MALA NO PUEDE TUMBAR LA PANTALLA (24-08). Aquí vienen también las
    # `inactive`, que nadie sanea nunca, y la pantalla pide esto y /current a la vez: si una
    # sola de las veinte no se puede construir, el cliente se quedaba sin ver la rutina que
    # tiene puesta y perfecta. Se sanea lo que se puede y la que aun así no se pueda pintar
    # se cae ella sola, con su motivo en el log para quien tenga que arreglar el dato.
    fuera = []
    for r in routines:
        r["days"] = _rutina_pintable(r.get("days"))
        try:
            fuera.append(RoutineResponse(**r))
        except Exception as e:                     # noqa: BLE001
            logging.getLogger("uvicorn.error").warning(
                "historial de rutinas: la rutina %s de %s no se puede pintar: %s",
                r.get("id"), profile["id"], e)
    return fuera


# ==================== ADMIN ROUTES ====================

admin_router = APIRouter(prefix="/admin/routines", tags=["admin-routines"])


# ── EL PDF TAMBIÉN ES RUTINA (24-08) ─────────────────────────────────────────────────
#
# El PDF es la vía de entrega real -- «se siguen generando como hasta ahora», bloque 11 del
# doc 19-08 -- y para el panel de Rutinas no existía: el cliente que ya tenía la suya
# entregada salía en rojo como trabajo pendiente, entraba en los grupos del «Ponérsela a los
# N» y se le podía generar encima una rutina de IA que no necesitaba. Su ficha sí sabía
# decirlo («Rutina entregada en PDF el ...»).
#
# UNA SOLA FORMA DE PREGUNTARLO, y agrupando EN LA BASE: en `rutina_pdfs` cada fila lleva el
# PDF entero dentro (hasta `MAX_PDF_BYTES`, 15 MB), así que lo que no se pida no viaja y
# vuelve una fila por cliente en vez de una por PDF. Esta es justo la pantalla donde ya hubo
# que arreglar siete segundos (ver `_los_que_no_tienen_rutina`).
#
# EL ÍNDICE YA ESTÁ (repaso 24-08). Este comentario decía «lo que falta es el índice por
# client_id», y era verdad hasta el 24-08: en producción `index_information()` solo devolvía
# `_id_`. Se creó en `core/database.create_indexes`, compuesto `("client_id", 1),
# ("uploaded_at", -1)`, y con él los `find_one(..., sort=[("uploaded_at", -1)])` del PDF
# salen por IXSCAN y sin ordenar en memoria (comprobado con explain en dev: `totalDocsExamined
# 0`). Se crea al arrancar el backend, así que en producción aparece con el próximo deploy.
# Este `aggregate` recorre la colección entera a propósito: los quiere todos.
async def _ultimo_pdf_por_cliente() -> Dict[str, str]:
    """{client_id: fecha del último PDF de rutina que se le subió}."""
    fuera: Dict[str, str] = {}
    # El `$project` va DELANTE del `$group` a propósito: sin él la tubería arrastra el
    # documento entero de cada PDF (el binario, hasta 15 MB) para acabar quedándose con dos
    # campos. Con la entrega mensual ya subida -- 35 filas en producción hoy y 165 clientes
    # a los que les toca -- eso es medio giga moviéndose por dentro de Mongo cada vez que se
    # abre el panel de Rutinas.
    async for fila in db.rutina_pdfs.aggregate(
            [{"$project": {"client_id": 1, "uploaded_at": 1}},
             {"$group": {"_id": "$client_id", "ultimo": {"$max": "$uploaded_at"}}}]):
        if fila.get("_id"):
            fuera[fila["_id"]] = fila.get("ultimo") or ""
    return fuera


@admin_router.get("/overview")
async def routines_overview(user = Depends(get_admin_user)):
    """Vista general para el panel: cada cliente activo y si tiene rutina PUESTA o no,
    sea la estructurada (`db.routines`) o la entregada en PDF."""
    # El equipo fuera, como en el resto del panel desde el 09-08. Aquí seguían dentro y
    # salían "Admin" y los entrenadores entre los clientes sin rutina, contando como
    # trabajo pendiente: nadie le va a poner una rutina al perfil de pruebas del admin.
    # Con el helper compartido y no con una copia: así el filtro de cuentas de prueba
    # (`es_prueba`, 21-08) arrastra aquí igual que al resto de contadores.
    from routes.admin import _fuera_el_equipo
    solo_clientes = await _fuera_el_equipo()
    profiles = await db.client_profiles.find(
        {**solo_clientes, "status": {"$ne": "baja"}}, {"_id": 0, "id": 1, "user_id": 1, "plan": 1}
    ).to_list(2000)
    uids = [p["user_id"] for p in profiles]
    users = await db.users.find(
        {"id": {"$in": uids}, "deleted_at": None}, {"_id": 0, "id": 1, "name": 1, "email": 1}
    ).to_list(2000)
    umap = {u["id"]: u for u in users}
    routines = await db.routines.find(
        {"status": "active"}, {"_id": 0, "client_id": 1, "days": 1, "created_at": 1}
    ).to_list(2000)
    rmap = {r["client_id"]: r for r in routines}
    # El que tiene su rutina entregada en PDF no es trabajo pendiente: ver arriba.
    pdfs = await _ultimo_pdf_por_cliente()

    out = []
    for p in profiles:
        u = umap.get(p["user_id"])
        if not u:
            continue
        r = rmap.get(p["id"])
        pdf = pdfs.get(p["id"])
        out.append({
            "client_id": p["id"],
            "name": u.get("name"),
            "email": u.get("email"),
            "plan": p.get("plan"),
            "has_routine": bool(r) or bool(pdf),
            # Cuál de las dos tiene: la estructurada se puede abrir por dentro (días y
            # ejercicios) y el PDF no, así que la pantalla no puede tratarlos igual.
            "tiene_pdf": bool(pdf),
            "pdf_uploaded_at": pdf or None,
            "training_days": len([d for d in r.get("days", []) if not d.get("is_rest")]) if r else 0,
            "routine_created_at": r.get("created_at") if r else None,
        })
    # Primero los que NO tienen rutina (los que necesitan trabajo), luego alfabetico
    out.sort(key=lambda c: (c["has_routine"], (c["name"] or "").lower()))
    return out

@admin_router.post("/generate")
async def generate_routine_ai(data: RoutineCreate, user = Depends(get_admin_user)):
    """Generar rutina con IA."""
    profile = await db.client_profiles.find_one({"id": data.client_id}, {"_id": 0})
    assert_client_access(user, profile)

    client_user = await db.users.find_one({"id": profile["user_id"]}, {"_id": 0, "password": 0})
    
    # Hasta hoy (punto 22): los tres reportes que se le mandan a la IA son los tres ultimos
    # DE VERDAD, no los importados con fecha de 2028, que ganaban el orden.
    reports = await db.reports.find(hasta_hoy({"client_id": data.client_id}), {"_id": 0}).sort("created_at", -1).to_list(3)
    prev_routines = await db.routines.find({"client_id": data.client_id}, {"_id": 0}).sort("created_at", -1).to_list(2)
    
    plan_features = PLAN_TYPES.get(profile["plan"], {}).get("features", [])
    include_cardio = "cardio" in plan_features
    
    context = f"""
Cliente: {client_user.get('name', 'Cliente')}
Plan: {profile['plan'].upper()}
Objetivo: {profile.get('goal', 'No especificado')}
Peso: {profile.get('weight', 'No especificado')} kg
Altura: {profile.get('height', 'No especificado')} cm
Edad: {profile.get('age', 'No especificado')} años
Sexo: {profile.get('sex', 'No especificado')}
Días de entrenamiento: {dias_de_entreno(profile)}
Equipamiento disponible: {', '.join(profile.get('equipment') or ['Gimnasio completo'])}
Lesiones/Limitaciones: {', '.join(profile.get('injuries') or ['Ninguna'])}

Macros actuales (entreno): P:{(profile.get('macros_training') or {}).get('protein', 'N/A')}g, H:{(profile.get('macros_training') or {}).get('carbs', 'N/A')}g, G:{(profile.get('macros_training') or {}).get('fat', 'N/A')}g

Incluir cardio: {'Sí' if include_cardio else 'No'}
Instrucciones del entrenador: {data.instructions or 'Generar rutina estándar según objetivo'}
"""

    prompt = f"""Genera una rutina de entrenamiento personalizada en formato JSON para el siguiente cliente:

{context}

La rutina debe tener este formato exacto:
{{
  "days": [
    {{"day": "Lunes", "is_rest": false, "exercises": [{{"name": "Nombre", "sets": 4, "reps": "10-12", "rest": "90s"}}]}},
    {{"day": "Martes", "is_rest": true, "exercises": []}}
  ],
  "trainer_notes": "Notas generales"
}}

Genera una rutina completa de 7 días. Responde SOLO con el JSON."""

    try:
        llm_key = os.environ.get('OPENAI_API_KEY')
        chat = LlmChat(
            api_key=llm_key,
            session_id=f"routine-{data.client_id}-{uuid.uuid4()}",
            system_message=("Eres un entrenador personal experto. Genera rutinas en formato JSON. "
                            "Escribe los nombres de ejercicios y notas en español neutro con tuteo "
                            "(prohibido el voseo y los regionalismos).")
        ).with_model("openai", os.environ.get('OPENAI_MODEL', 'gpt-4.1-mini'))
        
        response = await chat.send_message(UserMessage(text=prompt))
        
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        
        routine_data = json.loads(response_text)
        
        return {"generated": True, "routine": routine_data, "client_context": context}
        
    except Exception as e:
        default_routine = _get_default_routine()
        return {
            "generated": True,
            "routine": default_routine,
            "client_context": context,
            "note": "Rutina por defecto debido a error en generación IA"
        }

# ─────────────────────────────────────────────────────────────────────────────────────
# LO QUE SE GUARDA TIENE QUE PODERSE PINTAR (24-08)
#
# `Exercise` (models/common.py) pide las series como ENTERO. El campo Series del editor de
# la biblioteca admite el blanco y el generador puede devolver un rango («3-4»), y nada
# validaba entre lo que se escribe y lo que se guarda: con un solo ejercicio así,
# GET /routines/current revienta con un 500 y el cliente lee «Sin rutina asignada»
# mientras el panel le dice «Activa». Nadie se entera hasta que el cliente pregunta.
#
# Por eso se sanea al ESCRIBIR, en los sitios que escriben rutina de un cliente (la de la
# IA, la de la biblioteca y la de la asignación en bloque), y TAMBIÉN AL LEER en /current y
# /history: lo que ya está guardado no lo arregla ningún candado nuevo, y esa fila vieja es
# justo la que deja al cliente mirando un error con un botón de reintentar que no sirve.
# ─────────────────────────────────────────────────────────────────────────────────────

def _series(valor: Any) -> int:
    """Las series de un ejercicio, siempre un entero entre 1 y 99.

    Se queda con el primer número que traiga, que es lo que salva el rango del generador
    («3-4» son 3 series y una nota de reps, no un error que deba costar la rutina entera).
    Sin ningún número, una: un número raro se ve en la pantalla y el entrenador lo corrige;
    una rutina que no se puede pintar deja al cliente sin nada y sin decirle por qué.
    """
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        n = int(valor)
    else:
        encontrado = re.search(r"\d+", str(valor or ""))
        n = int(encontrado.group()) if encontrado else 1
    return min(max(n, 1), 99)


def _rutina_pintable(dias: Any) -> Any:
    """Los días, con TODO lo que el modelo exige: `day` en el día (RoutineDay) y `name`,
    `sets`, `reps` y `rest` en el ejercicio (Exercise, models/common.py).

    Estaban solo los tres del ejercicio y faltaban los dos nombres: un ejercicio de la IA
    sin `name`, o un día sin `day`, reventaba `GET /current` con el mismo 500 y el mismo
    «Sin rutina» que esto venía a cerrar. Sin nombre no hay nada que pintar, así que se cae
    ese ejercicio (o ese día) y no la rutina entera, que es la regla de la biblioteca
    (`_dias_limpios`) desde el 17-08.

    No toca nada más a propósito: por aquí pasan rutinas de la IA y de la biblioteca con
    campos que la limpieza de la biblioteca no conoce (el cardio del día, el vídeo del
    ejercicio) y que no se pueden perder por el camino.
    """
    limpios = []
    for d in dias or []:
        if not isinstance(d, dict):
            continue
        dia = str(d.get("day") or "").strip()
        if not dia:
            continue
        d["day"] = dia
        ejercicios = []
        for e in d.get("exercises") or []:
            if not isinstance(e, dict):
                continue
            nombre = str(e.get("name") or "").strip()
            if not nombre:
                continue
            e["name"] = nombre
            e["sets"] = _series(e.get("sets"))
            e["reps"] = str(e.get("reps") or "")
            e["rest"] = str(e.get("rest") or "")
            ejercicios.append(e)
        d["exercises"] = ejercicios
        limpios.append(d)
    return limpios


@admin_router.post("/save", response_model=RoutineResponse)
async def save_routine(client_id: str, routine: Dict[str, Any], user = Depends(get_admin_user)):
    """Guardar rutina para un cliente."""
    profile = await db.client_profiles.find_one({"id": client_id})
    assert_client_access(user, profile)

    await db.routines.update_many(
        {"client_id": client_id, "status": "active"},
        {"$set": {"status": "inactive"}}
    )
    
    routine_id = str(uuid.uuid4())
    routine_doc = {
        "id": routine_id,
        "client_id": client_id,
        "days": _rutina_pintable(routine.get("days", [])),
        "trainer_notes": routine.get("trainer_notes"),
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.routines.insert_one(routine_doc)

    # La rutina se guarda igual -- el entrenador la sigue creando y asignando -- pero al
    # cliente no se le avisa mientras no pueda verla (interruptor t3_entreno). Avisarle de
    # algo que no puede abrir le ensena a ignorar los avisos, y son los mismos por los que
    # se entera de sus macros.
    if await rutina_visible_para_el_cliente():
        await avisar_rutina_nueva(profile["user_id"])

    return RoutineResponse(**routine_doc)


# ─────────────────────────────────────────────────────────────────────────────────────
# ASIGNAR RUTINA A VARIOS A LA VEZ (punto 6 del documento del 17-08)
#
# «164 clientes tienen la rutina incluida en su plan y ninguno la tiene puesta. La vía
# existe -- ficha → Entreno → Generar rutina con IA -- pero uno a uno, 164 veces, no es
# viable. Lo que hace falta: poder generar y asignar en bloque, o al menos por grupos
# (mismo objetivo, misma maquinaria, mismo nivel)».
#
# Se hace POR GRUPOS, que es lo que pide el documento y además es lo único sensato: una
# llamada al modelo por cliente son 164 llamadas para rutinas que, con el mismo objetivo,
# los mismos días, el mismo material y el mismo nivel, iban a salir casi iguales. Se genera
# UNA por grupo y se asigna a todos los del grupo.
#
# Lo que NO hace: tocar a quien ya tiene rutina activa. Este endpoint es para el que no
# tiene ninguna; cambiarle la rutina a alguien que ya entrena con la suya es otra cosa y
# se hace desde su ficha, de una en una y mirándola.
# ─────────────────────────────────────────────────────────────────────────────────────

# Lo que la gente escribe cuando quiere decir que no tiene ninguna.
_NINGUNA = {"no", "ninguna", "ninguno", "nada", "n/a", "-"}


def _lista(valor: Any) -> set:
    """El campo, en minúsculas y sin vacíos. Un texto suelto es UN elemento, no sus letras."""
    if isinstance(valor, str):
        valor = [valor]
    return {str(v).strip().lower() for v in (valor or []) if str(v).strip()}


def _clave_de_grupo(perfil: Dict[str, Any]) -> Dict[str, Any]:
    """Lo que hace que dos clientes puedan compartir rutina.

    Los cuatro del documento: mismo objetivo, mismo material, mismos días y mismo nivel.
    El peso y los macros no entran -- la rutina no cambia porque uno pese cinco kilos más --
    y las lesiones sí, porque una rutina que ignora una lesión no vale para esa persona:
    quien tenga alguna se queda en su propio grupo y se le genera aparte.
    """
    equipo = sorted(_lista(perfil.get("equipment")))
    # «no» NO es una lesión. Hay fichas donde `injuries` viene como texto y no como lista, y
    # al recorrerlas letra a letra salía un grupo entero que se llamaba «con n y o».
    lesiones = sorted(l for l in _lista(perfil.get("injuries")) if l not in _NINGUNA)
    return {
        "objetivo": (perfil.get("goal") or "sin objetivo").strip().lower(),
        "dias": _dias_de_entreno(perfil),
        # EL CAMPO SE LLAMA `training_experience` (17-08). Buscando `experience` salían cero
        # de 163, y no era que nadie lo tuviera: era que ese nombre no existe en la base.
        "nivel": (perfil.get("training_experience") or "sin nivel").strip().lower(),
        "material": equipo or ["gimnasio completo"],
        "lesiones": lesiones,
    }


def _dias_de_entreno(perfil: Dict[str, Any]) -> int:
    """Cuántos días entrena a la semana. Nunca «no lo sé»: si no consta, cuatro.

    Hasta el 18-08 esto devolvía None cuando la ficha no traía el dato, y `_que_le_falta` lo
    marcaba como pendiente. El freno se puso para no darle a nadie una rutina de cuatro días
    sin saber si entrena dos, pero medido en producción el 17-08 dejaba fuera a 159 de los
    163 clientes con rutina en el plan por un dato que NO PEDÍA NINGUNA PANTALLA: no había
    forma de desbloquearlos. El documento del cuestionario (18-08) lo cierra por el otro
    lado: son siempre cuatro, así que deja de preguntarse y el campo se rellena solo.
    """
    return dias_de_entreno(perfil)


def _que_le_falta(perfil: Dict[str, Any]) -> List[str]:
    """Los datos sin los cuales no se le puede generar una rutina que valga.

    Queda uno solo: el objetivo, que lo tienen 72 de los 163 medidos en producción el 17-08.
    Los días de entreno ya no cuentan como falta -- son cuatro para todo el mundo, ver
    `core.dias_de_entreno` --, y eran justo los que bloqueaban a 159 de esos 163.

    El material y el nivel sí se dan por supuestos (gimnasio completo, nivel intermedio):
    ahí equivocarse cambia los ejercicios, no el plan.
    """
    falta = []
    if not (perfil.get("goal") or "").strip():
        falta.append("objetivo")
    return falta


def _id_de_grupo(clave: Dict[str, Any]) -> str:
    return "|".join([clave["objetivo"], str(clave["dias"]), clave["nivel"],
                     ",".join(clave["material"]), ",".join(clave["lesiones"])])


def _como_se_llama_el_grupo(clave: Dict[str, Any]) -> str:
    """El nombre que ve quien mira la pantalla. En sus palabras, no en claves.

    El material viene del cuestionario con los nombres del formulario -- `barra_olimpica`,
    `pull_up_bar`, `bandas_elasticas` --, y una fila con los nueve puestos ocupa dos líneas
    y no se lee. Se enseñan tres y se cuenta el resto.
    """
    partes = [clave["objetivo"], f"{clave['dias']} días", clave["nivel"]]
    material = [m.replace("_", " ") for m in clave["material"]]
    if material != ["gimnasio completo"]:
        if len(material) > 3:
            partes.append(", ".join(material[:3]) + f" y {len(material) - 3} cosas más")
        else:
            partes.append(" y ".join(material))
    if clave["lesiones"]:
        partes.append("con " + " y ".join(l.replace("_", " ") for l in clave["lesiones"]))
    return " · ".join(p for p in partes if p and p not in ("sin objetivo", "sin nivel"))


async def _los_que_no_tienen_rutina(user) -> List[Dict[str, Any]]:
    """Los clientes cuyo plan incluye rutina y no tienen ninguna PUESTA: ni estructurada
    activa ni entregada en PDF (24-08, ver `_ultimo_pdf_por_cliente`)."""
    from core.plan_access import plan_grants_feature
    from routes.admin import _fuera_el_equipo

    con_rutina = set(await db.routines.distinct("client_id", {"status": "active"}))
    # Con el PDF subido YA TIENE SU RUTINA: es la vía de entrega real y quien la tiene no es
    # trabajo pendiente. Sin esto entraba en los grupos del «Ponérsela a los N» y la
    # asignación en bloque le machacaba con una rutina de IA la que ya le habían hecho.
    con_rutina |= set(await _ultimo_pdf_por_cliente())
    filtro: Dict[str, Any] = {**await _fuera_el_equipo(),
                              "status": {"$in": ["activo", "pago_pendiente"]}}
    # Un entrenador solo ve y toca a los suyos, la misma regla que la ficha.
    if user.get("role") == "trainer":
        filtro["trainer_id"] = user.get("id")

    # Solo los campos que se miran. Sin la proyección venían los perfiles enteros -- con la
    # serie de pesos y lo importado de Calma dentro -- y agrupar a 219 tardaba siete segundos.
    CAMPOS = {"_id": 0, "id": 1, "user_id": 1, "plan": 1, "goal": 1, "training_days": 1,
              "training_weekdays": 1, "training_experience": 1, "equipment": 1, "injuries": 1}
    fuera = []
    async for p in db.client_profiles.find(filtro, CAMPOS):
        if not plan_grants_feature(p.get("plan"), "rutina"):
            continue
        if p["id"] in con_rutina:
            continue
        fuera.append(p)
    return fuera


@admin_router.get("/pendientes-por-grupo")
async def rutinas_pendientes_por_grupo(user = Depends(get_admin_user)):
    """Quién está sin rutina, agrupado por lo que permite compartirla.

    No genera nada: es la foto previa, para poder decidir por dónde empezar y ver de un
    vistazo cuántas rutinas hacen falta de verdad (que son bastantes menos que clientes).
    """
    grupos: Dict[str, Dict[str, Any]] = {}
    incompletos: List[Dict[str, Any]] = []
    por_falta: Dict[str, int] = {}

    pendientes = await _los_que_no_tienen_rutina(user)
    # Los nombres en UNA consulta, no una por cliente: con 219 pendientes eran 219 viajes a
    # la base y la pantalla se quedaba en «Agrupando…».
    uids = [p.get("user_id") for p in pendientes if p.get("user_id")]
    umap = {u["id"]: u for u in await db.users.find(
        {"id": {"$in": uids}}, {"_id": 0, "id": 1, "name": 1, "email": 1}
    ).to_list(len(uids) or 1)}

    for p in pendientes:
        u = umap.get(p.get("user_id")) or {}
        ficha = {"client_id": p["id"], "nombre": u.get("name") or "?",
                 "email": u.get("email") or "", "plan": p.get("plan")}

        falta = _que_le_falta(p)
        if falta:
            ficha["le_falta"] = falta
            incompletos.append(ficha)
            for f in falta:
                por_falta[f] = por_falta.get(f, 0) + 1
            continue

        clave = _clave_de_grupo(p)
        gid = _id_de_grupo(clave)
        g = grupos.setdefault(gid, {"id": gid, "clave": clave,
                                    "nombre": _como_se_llama_el_grupo(clave), "clientes": []})
        g["clientes"].append(ficha)

    salida = sorted(grupos.values(), key=lambda g: -len(g["clientes"]))
    for g in salida:
        g["cuantos"] = len(g["clientes"])
    listos = sum(g["cuantos"] for g in salida)
    return {
        "grupos": salida,
        "sin_rutina": listos + len(incompletos),
        "se_les_puede_poner_ya": listos,
        "rutinas_que_harian_falta": len(salida),
        # A QUIÉN NO SE LE PUEDE, Y POR QUÉ. Es la mitad importante de la respuesta: en
        # producción son casi todos, y sin decirlo el panel enseñaría «0 grupos» sin
        # explicar que el problema no es la herramienta sino que faltan los datos.
        "les_faltan_datos": len(incompletos),
        "que_les_falta": [{"dato": k, "a_cuantos": v}
                          for k, v in sorted(por_falta.items(), key=lambda x: -x[1])],
        "incompletos": incompletos[:200],
    }


@admin_router.post("/asignar-en-bloque")
async def asignar_rutinas_en_bloque(data: Dict[str, Any], user = Depends(get_admin_user)):
    """Genera UNA rutina por grupo y se la asigna a todos los de ese grupo.

    Recibe `{"grupos": ["id1", "id2"]}` con los ids que devuelve `/pendientes-por-grupo`, o
    `{"grupos": "todos"}`. Con `"probar": true` genera y devuelve lo que haría SIN guardar
    nada, que es lo que hay que mirar antes de asignarle una rutina a treinta personas.

    Devuelve, por grupo, a cuántos se la ha puesto y a cuántos no, con el motivo.
    """
    pedidos = data.get("grupos")
    solo_probar = bool(data.get("probar"))
    instrucciones = (data.get("instrucciones") or "").strip()

    pendientes = await _los_que_no_tienen_rutina(user)
    por_grupo: Dict[str, List[Dict[str, Any]]] = {}
    claves: Dict[str, Dict[str, Any]] = {}
    saltados = 0
    for p in pendientes:
        # Sin objetivo no se le pone nada: ver `_que_le_falta`.
        if _que_le_falta(p):
            saltados += 1
            continue
        clave = _clave_de_grupo(p)
        gid = _id_de_grupo(clave)
        claves[gid] = clave
        por_grupo.setdefault(gid, []).append(p)

    if pedidos != "todos":
        if not isinstance(pedidos, list) or not pedidos:
            raise HTTPException(status_code=400, detail="Dime a qué grupos, o «todos»")
        por_grupo = {g: v for g, v in por_grupo.items() if g in pedidos}
    if not por_grupo:
        return {"grupos": [], "asignadas": 0, "sin_datos": saltados,
                "nota": (f"A {saltados} les falta el objetivo y no se les puede generar una "
                         "rutina que valga."
                         if saltados else "No hay nadie sin rutina en lo que has pedido.")}

    resultado, asignadas = [], 0
    for gid, perfiles in por_grupo.items():
        clave = claves[gid]
        # Una rutina para el grupo, con el primero como referencia: comparten objetivo,
        # días, nivel y material, que es todo lo que mira el generador.
        muestra = perfiles[0]
        try:
            rutina = await _generar_para_grupo(clave, len(perfiles), instrucciones, muestra)
        except Exception as e:                     # noqa: BLE001
            resultado.append({"grupo": gid, "nombre": _como_se_llama_el_grupo(clave),
                              "cuantos": len(perfiles), "asignadas": 0,
                              "error": "no se ha podido generar la rutina de este grupo"})
            logging.getLogger("uvicorn.error").warning("rutina en bloque, grupo %s: %s", gid, e)
            continue

        puestas, fallos = [], []
        for p in perfiles:
            if solo_probar:
                continue
            try:
                await db.routines.update_many({"client_id": p["id"], "status": "active"},
                                              {"$set": {"status": "inactive"}})
                await db.routines.insert_one({
                    "id": str(uuid.uuid4()),
                    "client_id": p["id"],
                    "days": _rutina_pintable(rutina.get("days", [])),
                    "trainer_notes": rutina.get("trainer_notes"),
                    "status": "active",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    # De dónde salió y quién la puso: para poder contestar «¿por qué tiene
                    # esta rutina?» mirando la fila. Decía «para poder deshacerlo» y ese
                    # deshacer NO existe -- no hay endpoint ni botón que lea estos campos --,
                    # así que la etiqueta engañaba al que viniera a buscarlo.
                    "origen": "bloque",
                    "grupo": gid,
                    "puesta_por": user.get("id"),
                })
                puestas.append(p["id"])
                if await rutina_visible_para_el_cliente():
                    await avisar_rutina_nueva(p["user_id"])
            except Exception as e:                 # noqa: BLE001
                fallos.append(p["id"])
                logging.getLogger("uvicorn.error").warning("rutina en bloque, cliente %s: %s",
                                                           p["id"], e)
        asignadas += len(puestas)
        resultado.append({
            "grupo": gid, "nombre": _como_se_llama_el_grupo(clave),
            "cuantos": len(perfiles), "asignadas": len(puestas), "fallos": len(fallos),
            "rutina": rutina if solo_probar else None,
        })

    return {"grupos": resultado, "asignadas": asignadas, "sin_datos": saltados,
            "probado_sin_guardar": solo_probar}


async def _generar_para_grupo(clave: Dict[str, Any], cuantos: int, instrucciones: str,
                              muestra: Dict[str, Any]) -> Dict[str, Any]:
    """Una rutina para un grupo. Misma forma que la de uno, sin datos de nadie.

    A propósito NO se le manda nombre, peso ni macros de ningún cliente: esta rutina la van
    a usar `cuantos` personas y no puede estar escrita para una.
    """
    contexto = f"""
Objetivo: {clave['objetivo']}
Días de entrenamiento: {clave['dias']}
Nivel: {clave['nivel']}
Equipamiento disponible: {', '.join(clave['material'])}
Lesiones/Limitaciones: {', '.join(clave['lesiones']) or 'Ninguna'}
Incluir cardio: {'Sí' if 'cardio' in (PLAN_TYPES.get(muestra.get('plan'), {}).get('features') or []) else 'No'}
Instrucciones del entrenador: {instrucciones or 'Generar rutina estándar según objetivo'}
"""
    prompt = f"""Genera una rutina de entrenamiento en formato JSON para este perfil:

{contexto}
Esta rutina la van a seguir {cuantos} personas con ese mismo perfil, así que no la
personalices con nombres ni con pesos concretos: usa rangos de repeticiones y de descanso.

La rutina debe tener este formato exacto:
{{
  "days": [
    {{"day": "Lunes", "is_rest": false, "exercises": [{{"name": "Nombre", "sets": 4, "reps": "10-12", "rest": "90s"}}]}},
    {{"day": "Martes", "is_rest": true, "exercises": []}}
  ],
  "trainer_notes": "Notas generales"
}}

Genera una rutina completa de 7 días. Responde SOLO con el JSON."""

    chat = LlmChat(
        api_key=os.environ.get('OPENAI_API_KEY'),
        session_id=f"rutina-grupo-{uuid.uuid4()}",
        system_message=("Eres un entrenador personal experto. Genera rutinas en formato JSON. "
                        "Escribe los nombres de ejercicios y notas en español neutro con tuteo "
                        "(prohibido el voseo y los regionalismos)."),
    ).with_model("openai", os.environ.get('OPENAI_MODEL', 'gpt-4.1-mini'))

    # LOS DÍAS QUE ENTRENA SE COMPRUEBAN, NO SE PIDEN (17-08). En la primera prueba, un
    # grupo de «volumen · 2 días» salió con CUATRO días de entreno: el modelo lee «2 días»
    # y monta la rutina que le parece. A quien entrena dos días una rutina de cuatro no le
    # sirve, y encima no se nota hasta que el cliente la abre. Se cuenta y, si no cuadra, se
    # le dice y se repite una vez. Si a la segunda tampoco, ese grupo se queda sin rutina y
    # se informa: mejor eso que asignarle a nadie una que no puede seguir.
    aviso = ""
    for intento in (1, 2):
        texto = (await chat.send_message(UserMessage(text=prompt + aviso))).strip()
        if texto.startswith("```"):
            texto = texto.split("```")[1]
            if texto.startswith("json"):
                texto = texto[4:]
        rutina = json.loads(texto)
        dias = rutina.get("days") or []
        if not dias:
            raise ValueError("la rutina vino sin días")
        entreno = len([d for d in dias if not d.get("is_rest")])
        if entreno == clave["dias"]:
            return rutina
        aviso = (f"\n\nATENCIÓN: la rutina anterior tenía {entreno} días de entrenamiento y "
                 f"tienen que ser EXACTAMENTE {clave['dias']}. El resto de los 7 días van con "
                 f'"is_rest": true y sin ejercicios.')
        logging.getLogger("uvicorn.error").info(
            "rutina en bloque: pedidos %s días de entreno y vinieron %s (intento %s)",
            clave["dias"], entreno, intento)
    raise ValueError(f"la rutina no respeta los {clave['dias']} días de entreno")


# ─────────────────────────────────────────────────────────────────────────────────────
# LA BIBLIOTECA DE RUTINAS DEL EQUIPO (17-08-2026)
#
# Hasta hoy una rutina solo podía nacer de dos sitios: la IA, o escribirla a mano en la
# ficha de UN cliente. Las que Jesús escribe cada mes -- «Rutina del mes Hombre», «Rutina
# Agosto ELM Mujer», la carpeta «Rutinas GOLD» -- viven en Drive y se mandan por fuera, así
# que la app no las conoce y cada asignación empieza de cero.
#
# Esto es el sitio donde guardarlas: se crea una vez, se le pone nombre, y desde la ficha de
# cualquier cliente se elige y se le asigna. Al asignarla se COPIA, no se enlaza: si luego se
# le cambia un ejercicio a ese cliente, no se le toca la rutina a los otros veinte que la
# tienen puesta.
#
# El formato es el que la app ya sabe pintar (días con ejercicios de serie/reps/descanso) más
# un campo de notas por ejercicio, que es donde cabe la ejecución. Lo que Jesús escribe de
# verdad -- semanas con descarga, RIR serie a serie, aproximaciones con porcentajes -- NO
# cabe todavía y es lo primero de la lista de lo que queda.
# ─────────────────────────────────────────────────────────────────────────────────────

def _dias_limpios(dias: Any) -> List[Dict[str, Any]]:
    """Los siete días de una rutina, con lo que valga y sin lo que no.

    Se limpia aquí y no en la pantalla porque a esta colección se escribe desde el panel y,
    el día de mañana, desde la importación de las rutinas de Drive.
    """
    SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    # SIN TILDES TAMBIÉN VALE (24-08). Se comparaba con el nombre tal cual, así que un
    # «Miercoles» sin tilde -- lo que escribe cualquiera que llame a la API a mano, y lo que
    # va a traer la importación de las rutinas de Drive -- no casaba con ninguno de los
    # siete y ese día se perdía ENTERO, sin un solo error: la plantilla se guardaba con un
    # día menos y nadie se enteraba hasta que el cliente abría su rutina.
    _llanos = str.maketrans("áéíóúüÁÉÍÓÚÜ", "aeiouuAEIOUU")
    canonico = {n.translate(_llanos).lower(): n for n in SEMANA}
    porNombre = {}
    for d in (dias or []):
        if not isinstance(d, dict):
            continue
        nombre = canonico.get(str(d.get("day") or "").strip().translate(_llanos).lower())
        if not nombre:
            continue
        ejercicios = []
        for e in (d.get("exercises") or []):
            if not isinstance(e, dict):
                continue
            nom = str(e.get("name") or "").strip()
            if not nom:
                continue
            ejercicios.append({
                "name": nom[:120],
                # Entero siempre: ver `_series`. Guardar aquí el '' del campo en blanco
                # dejaba sin rutina a todo el que recibiera esta plantilla.
                "sets": _series(e.get("sets")),
                "reps": str(e.get("reps") or "")[:40],
                "rest": str(e.get("rest") or "")[:40],
                # Donde cabe la ejecución y las notas del entrenador.
                "notes": str(e.get("notes") or "")[:2000] or None,
            })
        porNombre[nombre] = {
            "day": nombre,
            # Un día es de descanso si lo dicen O si no tiene ejercicios: así no hace falta
            # acordarse de marcar la casilla.
            "is_rest": bool(d.get("is_rest")) or not ejercicios,
            "exercises": ejercicios,
        }
    return [porNombre.get(n, {"day": n, "is_rest": True, "exercises": []}) for n in SEMANA]


@admin_router.get("/biblioteca")
async def listar_biblioteca(user = Depends(get_admin_user)):
    """Las rutinas guardadas del equipo, para elegir una."""
    fuera = []
    async for r in db.routine_templates.find({}, {"_id": 0}).sort("updated_at", -1):
        dias = r.get("days") or []
        r["dias_de_entreno"] = len([d for d in dias if not d.get("is_rest")])
        r["ejercicios"] = sum(len(d.get("exercises") or []) for d in dias)
        # Siempre presente aunque la plantilla sea de antes de que existiera la marca: la
        # pantalla pinta un interruptor con esto y `undefined` le dejaría el botón mudo.
        r["del_mes"] = bool(r.get("del_mes"))
        fuera.append(r)
    # La del mes, la primera: es la que se entrega sola y la que hay que poder cambiar.
    fuera.sort(key=lambda r: not r["del_mes"])
    return {"rutinas": fuera}


@admin_router.post("/biblioteca")
async def crear_en_biblioteca(data: Dict[str, Any], user = Depends(get_admin_user)):
    """Guarda una rutina nueva en la biblioteca (o reescribe una, si viene con `id`)."""
    nombre = str(data.get("nombre") or "").strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="Ponle un nombre a la rutina")

    dias = _dias_limpios(data.get("days"))
    if not any(not d["is_rest"] for d in dias):
        raise HTTPException(
            status_code=400,
            detail="Esta rutina no tiene ningún día con ejercicios. Añade al menos uno.")

    ahora = datetime.now(timezone.utc).isoformat()
    doc = {
        "nombre": nombre[:120],
        "descripcion": str(data.get("descripcion") or "").strip()[:500] or None,
        "objetivo": str(data.get("objetivo") or "").strip().lower() or None,
        "nivel": str(data.get("nivel") or "").strip().lower() or None,
        "days": dias,
        "trainer_notes": str(data.get("trainer_notes") or "").strip()[:2000] or None,
        "updated_at": ahora,
        "updated_by": user.get("name") or user.get("email"),
    }

    if data.get("id"):
        r = await db.routine_templates.update_one({"id": data["id"]}, {"$set": doc})
        if not r.matched_count:
            raise HTTPException(status_code=404, detail="Esa rutina ya no está")
        return {"id": data["id"], **doc}

    doc["id"] = str(uuid.uuid4())
    doc["created_at"] = ahora
    doc["created_by"] = doc["updated_by"]
    await db.routine_templates.insert_one(dict(doc))
    return doc


@admin_router.delete("/biblioteca/{rutina_id}")
async def borrar_de_biblioteca(rutina_id: str, user = Depends(solo_admin_borra_catalogo)):
    """Quita una rutina de la biblioteca.

    No toca a quien ya la tenga puesta: al asignarla se copió, así que sus clientes siguen
    con la suya. Borrar la plantilla no le deja a nadie sin rutina.

    Solo admin (P61, doc 23-08): la biblioteca de rutinas es del equipo entero. Guardar,
    reescribir y asignar plantillas siguen abiertos al entrenador.
    """
    r = await db.routine_templates.delete_one({"id": rutina_id})
    if not r.deleted_count:
        raise HTTPException(status_code=404, detail="Esa rutina ya no está")
    return {"borrada": True}


async def _ponerle_la_plantilla(plantilla: Dict[str, Any], profile: Dict[str, Any],
                                origen: str, puesta_por: Optional[str] = None) -> None:
    """Copia una plantilla de la biblioteca en la rutina activa de un cliente.

    Se COPIA, no se enlaza: si luego se le cambia un ejercicio a ese cliente, no se le
    toca la rutina a los otros veinte que la tienen puesta.
    """
    client_id = profile["id"]
    await db.routines.update_many({"client_id": client_id, "status": "active"},
                                  {"$set": {"status": "inactive"}})
    await db.routines.insert_one({
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        # También aquí: en la biblioteca pueden quedar plantillas guardadas antes de que
        # las series se saneasen al escribir, y esa copia es la que va a abrir el cliente.
        "days": _rutina_pintable(plantilla.get("days", [])),
        "trainer_notes": plantilla.get("trainer_notes"),
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
        # De dónde salió: para saber cuál se puso a mano, cuál la IA y cuál la biblioteca.
        "origen": origen,
        "plantilla_id": plantilla.get("id"),
        "plantilla_nombre": plantilla.get("nombre"),
        "puesta_por": puesta_por,
    })
    # Con `.get`: hay fichas de la migración de Calma sin `user_id` (nadie ha entrado nunca
    # con esa cuenta). Con el corchete, la entrega de la rutina ya comprada reventaba DESPUÉS
    # de escribirla, y arriba se le decía al equipo que había que ponérsela a mano.
    if profile.get("user_id") and await rutina_visible_para_el_cliente():
        await avisar_rutina_nueva(profile["user_id"])


@admin_router.post("/biblioteca/{rutina_id}/asignar")
async def asignar_de_biblioteca(rutina_id: str, data: Dict[str, Any],
                                user = Depends(get_admin_user)):
    """Le pone a un cliente una rutina de la biblioteca. Se copia, no se enlaza."""
    client_id = str(data.get("client_id") or "").strip()
    if not client_id:
        raise HTTPException(status_code=400, detail="Falta el cliente")
    plantilla = await db.routine_templates.find_one({"id": rutina_id}, {"_id": 0})
    if not plantilla:
        raise HTTPException(status_code=404, detail="Esa rutina ya no está")

    profile = await db.client_profiles.find_one({"id": client_id})
    assert_client_access(user, profile)

    await _ponerle_la_plantilla(plantilla, profile, "biblioteca", puesta_por=user.get("id"))
    return {"asignada": True, "nombre": plantilla.get("nombre")}


# ── CUÁL ES «LA RUTINA DEL MES» (24-08) ──────────────────────────────────────────────
#
# Faltaba el concepto. La app vende «la rutina del mes» por 57 € en tres sitios -- el
# reporte mensual, la pantalla de Rutina y el catálogo de Inicio -- y en la base no había
# forma de preguntar CUÁL es la de este mes: la biblioteca es una lista plana de
# plantillas sin fecha ni marca, y las de Jesús ni siquiera están ahí (viven en Drive y se
# entregan en PDF). Resultado: el cliente pagaba y lo único que pasaba era un aviso al
# equipo para que se la mandara a mano.
#
# La marca es UNA en toda la biblioteca (`del_mes: true`): el equipo dice cuál es la de
# este mes y, a partir de ahí, quien la compra la tiene puesta al volver de pagar. Sin
# ninguna marcada esto devuelve None y el circuito de compra sigue funcionando como hasta
# hoy -- cobra y avisa al equipo --, que es lo que no se puede romper.
async def rutina_del_mes_vigente() -> Optional[Dict[str, Any]]:
    """La plantilla marcada como rutina del mes, o None si el equipo no ha marcado ninguna."""
    return await db.routine_templates.find_one({"del_mes": True}, {"_id": 0},
                                               sort=[("updated_at", -1)])


# ── LO QUE SE VENDE TIENE QUE PODER ENTREGARSE (verificación 24-08, fallo 14) ────────
#
# La marca de arriba (`routine_templates.del_mes`) se quedó a medias: en producción hay CERO
# plantillas en la biblioteca y ninguna marcada, mientras que la entrega real del negocio es
# un PDF -- los 32 de agosto se subieron así, a `db.rutina_pdfs` --. O sea que la única vía
# que sabía entregar la compra era la que nunca se usa, y alguien podía pagar 57 € y no
# recibir nada automáticamente.
#
# Se entrega LO QUE DE VERDAD HAY, y en este orden:
#   1. la plantilla ESTRUCTURADA marcada «la del mes», si el equipo ha marcado alguna
#      (es mejor producto: el cliente puede marcar series y pesos), y
#   2. si no, EL PDF DEL MES VIGENTE, que es como se entrega hoy de hecho.
#
# `_entregar_el_pdf_del_mes` está definido más abajo, en el bloque del PDF (necesita
# `_guardar_pdf_de_rutina`): en Python el nombre se resuelve al llamar, no al definir.
async def entregar_la_rutina_del_mes(client_id: str, origen: str = "compra") -> Optional[str]:
    """Le entrega la rutina del mes vigente a quien acaba de comprarla.

    Devuelve el nombre de lo que se le ha puesto (la plantilla o el PDF), o None si no hay
    NADA preparado y entonces se la entrega el equipo a mano.
    """
    profile = await db.client_profiles.find_one({"id": client_id}, {"_id": 0, "id": 1, "user_id": 1})
    if not profile:
        return None
    plantilla = await rutina_del_mes_vigente()
    if plantilla:
        await _ponerle_la_plantilla(plantilla, profile, origen)
        return plantilla.get("nombre")
    return await _entregar_el_pdf_del_mes(profile, origen)


@admin_router.post("/biblioteca/{rutina_id}/del-mes")
async def marcar_la_rutina_del_mes(rutina_id: str, data: Optional[Dict[str, Any]] = None,
                                   user = Depends(get_admin_user)):
    """Marca (o desmarca) qué plantilla es LA RUTINA DEL MES: la que se le entrega sola a
    quien la compre desde la app."""
    plantilla = await db.routine_templates.find_one({"id": rutina_id}, {"_id": 0, "id": 1, "nombre": 1})
    if not plantilla:
        raise HTTPException(status_code=404, detail="Esa rutina ya no está")
    quitarla = (data or {}).get("del_mes") is False
    if quitarla:
        await db.routine_templates.update_one({"id": rutina_id}, {"$set": {"del_mes": False}})
        return {"del_mes": False, "nombre": plantilla.get("nombre")}
    # Solo una a la vez: si hubiera dos marcadas, «la del mes» dejaría de significar algo.
    await db.routine_templates.update_many({"id": {"$ne": rutina_id}}, {"$set": {"del_mes": False}})
    await db.routine_templates.update_one({"id": rutina_id}, {"$set": {"del_mes": True}})
    return {"del_mes": True, "nombre": plantilla.get("nombre")}


def _get_default_routine():
    """Rutina por defecto."""
    return {
        "days": [
            {"day": "Lunes", "is_rest": False, "exercises": [
                {"name": "Press banca", "sets": 4, "reps": "8-10", "rest": "90s"},
                {"name": "Press inclinado", "sets": 3, "reps": "10-12", "rest": "75s"},
                {"name": "Aperturas", "sets": 3, "reps": "12-15", "rest": "60s"}
            ]},
            {"day": "Martes", "is_rest": True, "exercises": []},
            {"day": "Miércoles", "is_rest": False, "exercises": [
                {"name": "Sentadilla", "sets": 4, "reps": "8-10", "rest": "120s"},
                {"name": "Prensa", "sets": 4, "reps": "10-12", "rest": "90s"},
                {"name": "Curl femoral", "sets": 3, "reps": "10-12", "rest": "75s"}
            ]},
            {"day": "Jueves", "is_rest": True, "exercises": []},
            {"day": "Viernes", "is_rest": False, "exercises": [
                {"name": "Dominadas", "sets": 4, "reps": "6-10", "rest": "90s"},
                {"name": "Remo", "sets": 4, "reps": "8-10", "rest": "90s"},
                {"name": "Curl bíceps", "sets": 3, "reps": "10-12", "rest": "60s"}
            ]},
            {"day": "Sábado", "is_rest": True, "exercises": []},
            {"day": "Domingo", "is_rest": True, "exercises": []}
        ],
        "trainer_notes": "Rutina generada automáticamente."
    }


# ─────────────────────────────────────────────────────────────────────────────
# EL PDF DE LA RUTINA (bloque 11, doc 19-08): «que se pueda subir y ver desde la
# app; se siguen generando como hasta ahora». El equipo lo genera fuera, lo sube
# desde la ficha del cliente, y el cliente lo abre desde Entreno. Se guarda en la
# base como las fotos de progreso: el mismo camino que ya funciona.
# ─────────────────────────────────────────────────────────────────────────────
from fastapi import File, Form, UploadFile    # noqa: E402
from fastapi.responses import Response        # noqa: E402
from bson.binary import Binary                # noqa: E402

MAX_PDF_BYTES = 15 * 1024 * 1024


# ── Los dos datos que acompañan al PDF (tarea 7.1 del 21-08, apartados 12 y 19) ──
#
# El REPARTO DE GRUPOS POR DÍA («Empuje, Tirón, Pierna, Empuje») y las SEMANAS que dura
# la rutina los pone el entrenador al subir el PDF. Viven EN EL PROPIO DOCUMENTO de
# `rutina_pdfs`, no en el perfil: describen ESA rutina -- la siguiente tendrá su propio
# reparto y su propia duración -- y así el histórico queda coherente sin inventar otra
# colección. Los días de la semana en que entrena el cliente NO van aquí: esos son suyos
# (dependen de su vida, no de la rutina) y viven en `client_profiles.training_weekdays`.

def _reparto_limpio(valor: Any) -> Optional[List[str]]:
    """El reparto como lista de grupos («Empuje», «Tirón»...). Acepta la lista o el texto
    separado por comas que escribe el panel. Vacío es None: no hay reparto, no una lista
    de nada."""
    if isinstance(valor, str):
        valor = valor.split(",")
    if not isinstance(valor, (list, tuple)):
        return None
    grupos = [str(g).strip()[:40] for g in valor if str(g).strip()]
    # Más de 7 grupos no caben en una semana: se recorta en vez de rechazar, que en el
    # panel un error por la coma de más solo consigue que el dato no se rellene nunca.
    return grupos[:7] or None


def _semanas_limpias(valor: Any) -> Optional[int]:
    """Cuántas semanas dura la rutina. Un número entre 1 y 52, o None si no viene."""
    try:
        n = int(str(valor).strip())
    except (TypeError, ValueError):
        return None
    return n if 1 <= n <= 52 else None


async def _leer_el_pdf(file: UploadFile) -> bytes:
    """El archivo en memoria, ya comprobado.

    Separado de guardarlo porque la subida EN BLOQUE lo lee una vez y lo escribe para N
    clientes: `file.read()` solo devuelve el contenido la primera vez, y llamarlo dentro
    del bucle le habría guardado un PDF vacío a todos menos al primero.
    """
    if (file.content_type or "").lower() != "application/pdf" \
            and not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="La rutina tiene que ser un PDF.")
    contenido = await file.read()
    if not contenido:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")
    if len(contenido) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413,
                            detail=f"El PDF pesa demasiado; el máximo es {MAX_PDF_BYTES // (1024 * 1024)} MB.")
    return contenido


async def _guardar_pdf_de_rutina(client_id: str, contenido: bytes, filename: str,
                                 subido_por: str,
                                 reparto: Optional[List[str]] = None,
                                 semanas: Optional[int] = None,
                                 origen: Optional[str] = None) -> dict:
    doc = {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "filename": filename or "rutina.pdf",
        "size": len(contenido),
        "subido_por": subido_por,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        # El reparto de grupos por día de entreno y las semanas que dura (7.1 del 21-08).
        "reparto": reparto,
        "semanas": semanas,
        # Quién lo puso ahí: "compra" cuando lo entrega sola la compra de la rutina del mes,
        # None cuando lo sube el entrenador desde la ficha (que es lo de siempre). Sirve para
        # saber en la ficha si esa entrega la hizo una persona o el circuito de pago.
        "origen": origen,
        "data": Binary(contenido),
    }
    await db.rutina_pdfs.insert_one(doc)
    return doc


async def _avisar_de_la_rutina_en_pdf(user_id: Optional[str]) -> None:
    """El aviso de entrega, el mismo que mandan las tres vías estructuradas y que aquí
    faltaba: el PDF se quedaba guardado sin que el cliente supiera que lo tenía. Mismo
    candado que ellas (t3_entreno) y máximo uno al día, que es la regla de los avisos de
    entrega: resubirlo para corregir una errata no puede sonarle dos veces."""
    if not user_id:
        return
    if await rutina_visible_para_el_cliente() and not await _hay_aviso_de_hoy(user_id, "rutina_nueva"):
        await avisar_rutina_nueva(user_id)


@admin_router.post("/pdf/{client_id}")
async def subir_pdf_de_rutina(client_id: str, file: UploadFile = File(...),
                              reparto: Optional[str] = Form(None),
                              semanas: Optional[str] = Form(None),
                              user=Depends(get_admin_user)):
    """Sube (o sustituye) la rutina en PDF de un cliente. Se guarda el histórico: el
    cliente ve siempre la última, pero la del mes pasado no se pierde.

    `reparto` (texto separado por comas: «Empuje, Tirón, Pierna, Empuje») y `semanas`
    (número) son opcionales: sin ellos el PDF se ve igual, pero la semana del cliente no
    puede decir qué grupo toca cada día."""
    perfil = await db.client_profiles.find_one({"id": client_id}, {"_id": 0, "id": 1, "user_id": 1})
    if not perfil:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    contenido = await _leer_el_pdf(file)
    doc = await _guardar_pdf_de_rutina(client_id, contenido, file.filename or "rutina.pdf",
                                       subido_por=user.get("id"),
                                       reparto=_reparto_limpio(reparto),
                                       semanas=_semanas_limpias(semanas))
    await _avisar_de_la_rutina_en_pdf(perfil.get("user_id"))
    return {"ok": True, "id": doc["id"], "filename": doc["filename"],
            "size": doc["size"], "uploaded_at": doc["uploaded_at"],
            "reparto": doc.get("reparto"), "semanas": doc.get("semanas")}


# ── LA MISMA RUTINA A VARIOS DE GOLPE (24-08) ────────────────────────────────────────
#
# «La del mes solo a los que se le incluyen, la personalizada se le da una personalizada,
# debemos agregar eso» (Jesús, 24-08). En producción hay 58 clientes con plan de rutina
# PERSONALIZADA y 58 sin rutina: ponérsela de una en una desde la ficha son 58 vueltas de
# ficha, subir, volver. La entrega mensual de agosto hubo que hacerla por un script suelto
# (`backend/_subir_rutina_del_mes.py`) justamente porque esto no existía.
#
# Se sube UN archivo y se escribe una fila por cliente, igual que la subida de la ficha: el
# PDF entero dentro de cada documento. No es lo más fino -- treinta copias del mismo
# binario -- pero es EXACTAMENTE lo que ya hace la app, y una entrega mensual no es sitio
# para estrenar almacenamiento compartido: el día que se cambie, se cambia para las dos.
MAX_CLIENTES_EN_BLOQUE = 300


@admin_router.post("/pdf-en-bloque")
async def subir_pdf_de_rutina_a_varios(file: UploadFile = File(...),
                                       clientes: str = Form(...),
                                       reparto: Optional[str] = Form(None),
                                       semanas: Optional[str] = Form(None),
                                       del_mes: Optional[str] = Form(None),
                                       user=Depends(get_admin_user)):
    """Sube el mismo PDF de rutina a varios clientes a la vez.

    `clientes` son los id separados por comas. El reparto y las semanas, si vienen, se le
    ponen a todos: es la misma rutina, así que dura lo mismo y reparte igual.

    `del_mes=true` deja además este mismo PDF preparado como LA RUTINA DEL MES, que es lo
    que recibe el que la compra por 57 €. Es el gesto natural del día de la entrega: el
    archivo ya está subido, y sin esto la compra no tiene nada que entregar (fallo 14).

    NO PISA NADA: como la subida de uno en uno, guarda una entrega más en el histórico y
    el cliente ve la última. Y a cada uno le suena su aviso de rutina nueva.
    """
    ids = [c.strip() for c in (clientes or "").split(",") if c.strip()]
    # Sin duplicados y respetando el orden en que llegan (una selección de la tabla puede
    # traer el mismo id dos veces y serían dos entregas iguales al mismo cliente).
    ids = list(dict.fromkeys(ids))
    if not ids:
        raise HTTPException(status_code=400, detail="No has elegido a nadie.")
    if len(ids) > MAX_CLIENTES_EN_BLOQUE:
        raise HTTPException(
            status_code=400,
            detail=f"Son demasiados de una vez; el máximo es {MAX_CLIENTES_EN_BLOQUE}.")

    contenido = await _leer_el_pdf(file)
    lista = _reparto_limpio(reparto)
    cuantas = _semanas_limpias(semanas)
    guardar_del_mes = str(del_mes or "").strip().lower() in ("1", "true", "si", "sí", "on")
    if guardar_del_mes:
        await _guardar_el_pdf_del_mes(contenido, file.filename or "rutina.pdf",
                                      subido_por=user.get("id"), mes=_mes_limpio(None),
                                      reparto=lista, semanas=cuantas)

    perfiles = await db.client_profiles.find(
        {"id": {"$in": ids}}, {"_id": 0, "id": 1, "user_id": 1}).to_list(len(ids))
    porId = {p["id"]: p for p in perfiles}

    subidas, sin_perfil = [], []
    for client_id in ids:
        perfil = porId.get(client_id)
        if not perfil:
            # Uno que ya no está no puede tumbar la entrega de los otros cincuenta.
            sin_perfil.append(client_id)
            continue
        # De uno en uno y no con `insert_many`: cada fila lleva el PDF dentro y treinta de
        # 4,6 MB en un solo lote se pasan del tamaño máximo de una operación de Mongo.
        await _guardar_pdf_de_rutina(client_id, contenido, file.filename or "rutina.pdf",
                                     subido_por=user.get("id"),
                                     reparto=lista, semanas=cuantas)
        await _avisar_de_la_rutina_en_pdf(perfil.get("user_id"))
        subidas.append(client_id)

    return {"ok": True, "subidas": len(subidas), "clientes": subidas,
            "sin_perfil": sin_perfil, "filename": file.filename,
            "reparto": lista, "semanas": cuantas,
            "del_mes": guardar_del_mes}


# ─────────────────────────────────────────────────────────────────────────────
# EL PDF DE LA RUTINA DEL MES (verificación 24-08, fallo 14)
#
# QUÉ PASABA. La compra de los 57 € solo sabía entregar una plantilla ESTRUCTURADA de la
# biblioteca marcada `del_mes`. En producción hay CERO plantillas y ninguna marcada,
# mientras que la entrega de verdad del negocio es un PDF (los 32 de agosto se subieron
# así). Resultado: se cobraba y no se entregaba nada; quedaba un aviso al equipo diciendo
# «hay que entregársela a mano».
#
# LA FORMA MÁS SIMPLE QUE FUNCIONA. Una colección con UNA fila vigente, `db.rutina_mes_pdf`,
# que guarda el PDF del mes tal cual (el mismo formato que `rutina_pdfs`: el binario dentro
# del documento, que es lo que ya hace toda la app). Cuando alguien la compra, ese PDF se
# COPIA a su `rutina_pdfs` -- exactamente lo mismo que hace la entrega en bloque -- y a
# partir de ahí lo ve por el camino que ya funciona: `GET /routines/pdf/info`, la pantalla
# de Rutina y `tiene_rutina_puesta()`. No hace falta nada nuevo en el cliente.
#
# Se copia y no se enlaza por la misma razón que se copian las plantillas: el mes que viene
# se sube otro PDF y al que compró en agosto no se le puede cambiar la rutina debajo.
#
# CÓMO SE PONE. Dos vías, las dos aquí:
#   - `POST /admin/routines/pdf-del-mes` sube el PDF del mes, y
#   - `POST /admin/routines/pdf-en-bloque` con `del_mes=true` guarda de paso como PDF del
#     mes el mismo que se le acaba de repartir a los clientes, que es el gesto natural del
#     equipo el día de la entrega mensual.
# EL PANEL TODAVÍA NO TIENE BOTÓN para esto (el frontend de admin es de otro bloque): hasta
# que lo tenga se pone por API o desde `backend/_subir_rutina_del_mes.py`.
# ─────────────────────────────────────────────────────────────────────────────

def _mes_limpio(valor: Any) -> str:
    """El mes al que corresponde la rutina, «YYYY-MM». Sin él, el mes de hoy en España."""
    texto = str(valor or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}", texto):
        return texto
    from core.tiempo import hoy_madrid
    return hoy_madrid().strftime("%Y-%m")


MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre")


def _nombre_del_mes(mes: str) -> str:
    """«2026-08» -> «La rutina de agosto». Es lo que lee el cliente en su aviso."""
    try:
        anio, numero = mes.split("-")
        return f"La rutina de {MESES[int(numero) - 1]} de {anio}"
    except (ValueError, IndexError):
        return "La rutina del mes"


async def pdf_del_mes_vigente(con_datos: bool = False) -> Optional[Dict[str, Any]]:
    """El PDF marcado como la rutina de este mes, o None si el equipo no ha subido ninguno.

    `con_datos=False` por defecto y NO por comodidad: el binario son hasta 15 MB y esto lo
    pregunta la pantalla de compra. Solo lo pide quien va a entregarlo.
    """
    fuera = None if con_datos else {"data": 0}
    return await db.rutina_mes_pdf.find_one({"vigente": True}, {"_id": 0, **(fuera or {})},
                                            sort=[("uploaded_at", -1)])


async def hay_rutina_del_mes_que_entregar() -> bool:
    """¿Hay algo preparado para el que compre la rutina del mes? Plantilla marcada o PDF.

    Es el candado del dinero: sin esto el botón cobraba 57 € a ciegas (fallo 14).
    """
    if await rutina_del_mes_vigente():
        return True
    return await pdf_del_mes_vigente() is not None


async def _guardar_el_pdf_del_mes(contenido: bytes, filename: str, subido_por: str,
                                  mes: str, reparto: Optional[List[str]] = None,
                                  semanas: Optional[int] = None) -> Dict[str, Any]:
    """Deja este PDF como la rutina del mes vigente. Solo una vigente a la vez."""
    doc = {
        "id": str(uuid.uuid4()),
        "mes": mes,
        "nombre": _nombre_del_mes(mes),
        "filename": filename or "rutina.pdf",
        "size": len(contenido),
        "reparto": reparto,
        "semanas": semanas,
        "subido_por": subido_por,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "vigente": True,
        "data": Binary(contenido),
    }
    # Las anteriores se archivan en vez de borrarse: quien compró en agosto tiene su copia,
    # pero saber qué se repartió cada mes vale más que los megas que ocupa.
    await db.rutina_mes_pdf.update_many({"vigente": True}, {"$set": {"vigente": False}})
    await db.rutina_mes_pdf.insert_one(doc)
    return doc


async def _entregar_el_pdf_del_mes(profile: Dict[str, Any], origen: str) -> Optional[str]:
    """Le copia el PDF del mes vigente a un cliente. Devuelve cómo se llama, o None.

    Lo llama `entregar_la_rutina_del_mes` cuando no hay plantilla estructurada marcada, que
    hoy es SIEMPRE (cero plantillas en producción).
    """
    doc = await pdf_del_mes_vigente(con_datos=True)
    if not doc:
        return None
    await _guardar_pdf_de_rutina(profile["id"], bytes(doc["data"]), doc.get("filename"),
                                 subido_por=doc.get("subido_por"),
                                 reparto=doc.get("reparto"), semanas=doc.get("semanas"),
                                 origen=origen)
    # El mismo aviso que le suena cuando se la sube su entrenador: acaba de pagarla, tiene
    # que enterarse de que ya la tiene.
    await _avisar_de_la_rutina_en_pdf(profile.get("user_id"))
    return doc.get("nombre") or doc.get("filename") or "La rutina del mes"


@admin_router.post("/pdf-del-mes")
async def subir_el_pdf_del_mes(file: UploadFile = File(...),
                               mes: Optional[str] = Form(None),
                               reparto: Optional[str] = Form(None),
                               semanas: Optional[str] = Form(None),
                               user=Depends(get_admin_user)):
    """Sube LA RUTINA DEL MES en PDF: la que recibe solo el que la compra por 57 €.

    No se la manda a nadie: queda preparada. Para repartirla a los que ya la llevan
    incluida está `pdf-en-bloque`, que además puede dejarla marcada aquí de una pasada.
    """
    contenido = await _leer_el_pdf(file)
    doc = await _guardar_el_pdf_del_mes(contenido, file.filename or "rutina.pdf",
                                        subido_por=user.get("id"), mes=_mes_limpio(mes),
                                        reparto=_reparto_limpio(reparto),
                                        semanas=_semanas_limpias(semanas))
    return {"ok": True, **{k: doc[k] for k in ("id", "mes", "nombre", "filename", "size",
                                               "uploaded_at", "reparto", "semanas")}}


@admin_router.get("/pdf-del-mes/info")
async def info_del_pdf_del_mes(user=Depends(get_admin_user)):
    """¿Hay rutina del mes preparada, y cuál? Lo que el panel necesita para saber si la
    compra puede entregar algo."""
    plantilla = await rutina_del_mes_vigente()
    doc = await pdf_del_mes_vigente()
    return {"hay": bool(plantilla or doc),
            "plantilla": (plantilla or {}).get("nombre"),
            "pdf": {k: doc.get(k) for k in ("id", "mes", "nombre", "filename", "size",
                                            "uploaded_at", "reparto", "semanas")} if doc else None}


@admin_router.get("/pdf-del-mes")
async def ver_el_pdf_del_mes(user=Depends(get_admin_user)):
    """El PDF del mes, para comprobar que es el bueno antes de venderlo."""
    return await _servir_pdf(await pdf_del_mes_vigente(con_datos=True))


@admin_router.delete("/pdf-del-mes")
async def retirar_el_pdf_del_mes(user=Depends(get_admin_user)):
    """Retira la rutina del mes: deja de haber nada que entregar y la compra se cierra
    sola. Se usa cuando el PDF subido estaba mal, para que no se venda de mientras."""
    r = await db.rutina_mes_pdf.update_many({"vigente": True}, {"$set": {"vigente": False}})
    return {"ok": True, "retiradas": getattr(r, "modified_count", 0)}


@router.get("/rutina-del-mes/disponible")
async def la_rutina_del_mes_esta_lista(user=Depends(get_current_user)):
    """¿Se puede comprar hoy la rutina del mes? Lo pregunta la pantalla de Rutina para no
    enseñar un botón de 57 € que el servidor va a rechazar (fallo 14 de la verificación)."""
    return {"disponible": await hay_rutina_del_mes_que_entregar()}


@admin_router.patch("/pdf/{client_id}/detalles")
async def detalles_pdf_de_rutina(client_id: str, data: Dict[str, Any],
                                 user=Depends(get_admin_user)):
    """Corrige el reparto o las semanas del ÚLTIMO PDF sin volver a subirlo: los PDF que
    ya están subidos no traen estos dos datos, y resubir el archivo para ponérselos es
    trabajo doble. Solo escribe lo que venga en la petición."""
    doc = await db.rutina_pdfs.find_one({"client_id": client_id}, {"_id": 0, "id": 1},
                                        sort=[("uploaded_at", -1)])
    if not doc:
        raise HTTPException(status_code=404, detail="Este cliente no tiene ningún PDF subido.")
    update: Dict[str, Any] = {}
    if "reparto" in (data or {}):
        update["reparto"] = _reparto_limpio(data.get("reparto"))
    if "semanas" in (data or {}):
        update["semanas"] = _semanas_limpias(data.get("semanas"))
    if update:
        await db.rutina_pdfs.update_one({"id": doc["id"]}, {"$set": update})
    return {"ok": True, **update}


@admin_router.get("/pdf/{client_id}/info")
async def info_pdf_de_rutina_admin(client_id: str, user=Depends(get_admin_user)):
    doc = await db.rutina_pdfs.find_one({"client_id": client_id}, {"_id": 0, "data": 0},
                                        sort=[("uploaded_at", -1)])
    if not doc:
        return {"hay": False}
    return {"hay": True, **{k: doc[k] for k in ("id", "filename", "size", "uploaded_at")},
            "reparto": doc.get("reparto"), "semanas": doc.get("semanas")}


async def _servir_pdf(doc: Optional[dict]) -> Response:
    if not doc:
        raise HTTPException(status_code=404, detail="No hay ninguna rutina en PDF subida.")
    return Response(content=bytes(doc["data"]), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{doc.get("filename") or "rutina.pdf"}"'})


@admin_router.get("/pdf/{client_id}")
async def ver_pdf_de_rutina_admin(client_id: str, user=Depends(get_admin_user)):
    doc = await db.rutina_pdfs.find_one({"client_id": client_id}, {"_id": 0},
                                        sort=[("uploaded_at", -1)])
    return await _servir_pdf(doc)


@router.get("/pdf/info")
async def info_pdf_de_rutina(user=Depends(get_current_user)):
    """¿Tiene PDF? Para que la app enseñe el botón solo si existe. Sin gate de plan a
    propósito: si su entrenador se lo subió, es suyo y lo puede abrir."""
    perfil = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
    if not perfil:
        return {"hay": False}
    doc = await db.rutina_pdfs.find_one({"client_id": perfil["id"]}, {"_id": 0, "data": 0},
                                        sort=[("uploaded_at", -1)])
    if not doc:
        return {"hay": False}
    return {"hay": True, **{k: doc[k] for k in ("filename", "uploaded_at")},
            "reparto": doc.get("reparto"), "semanas": doc.get("semanas")}


@router.get("/pdf")
async def ver_pdf_de_rutina(user=Depends(get_current_user)):
    perfil = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
    if not perfil:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    doc = await db.rutina_pdfs.find_one({"client_id": perfil["id"]}, {"_id": 0},
                                        sort=[("uploaded_at", -1)])
    return await _servir_pdf(doc)


# ─────────────────────────────────────────────────────────────────────────────
# LA SEMANA DE LA RUTINA (tarea 7.1 del 21-08, apartados 12 y 19 del doc de Jesús)
#
# Con el reparto del PDF (lo pone el entrenador) y los días que entrena el cliente
# (los pone él: `client_profiles.training_weekdays`), la pantalla de Rutina puede decir
# «Rutina #2 · Semana 3 de 8», pintar la tira de la semana con el grupo de cada día y
# preguntar por el entreno que se dejó. El registro de lo HECHO sigue siendo
# `workout_logs` (T3): aquí no se inventa otra fuente, se escribe en la misma.
#
# Los días del cliente se guardan como NOMBRES («lunes», «miercoles»...). En la base
# quedan unos pocos perfiles de la época de Calma con enteros, y su significado no se
# puede verificar (el código que los escribió no está en el repo): esos se cuentan para
# el total de días (core/dias_de_entreno) pero NO se usan para colocar grupos en días
# concretos, que pintarle «Empuje» el día equivocado es peor que no pintar nada.
# ─────────────────────────────────────────────────────────────────────────────
from datetime import date, timedelta                              # noqa: E402
from core.tiempo import a_madrid, hoy_madrid                      # noqa: E402
from routes.workout_logs import DIAS_SEMANA, _plano               # noqa: E402

# Como se enseñan («Hoy · jueves · Empuje»), con sus tildes.
DIAS_BONITOS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def indices_de_entreno(perfil: Dict[str, Any]) -> Optional[List[int]]:
    """Qué días de la semana entrena, como índices 0-6 (0 = lunes), ordenados.

    Solo de los nombres de día: ver el aviso de arriba sobre los enteros heredados."""
    v = (perfil or {}).get("training_weekdays")
    if not isinstance(v, (list, tuple)):
        return None
    dias = {DIAS_SEMANA.index(_plano(d)) for d in v
            if isinstance(d, str) and _plano(d) in DIAS_SEMANA}
    return sorted(dias) or None


def _grupo_estructurado(routine: Optional[Dict[str, Any]], indice: int) -> Optional[str]:
    """El grupo que la rutina estructurada le pone a ese día de la semana, si lo trae."""
    for d in (routine or {}).get("days") or []:
        if _plano(d.get("day")) == DIAS_SEMANA[indice] and not d.get("is_rest"):
            for clave in ("grupo", "focus", "nombre", "titulo"):
                valor = str(d.get(clave) or "").strip()
                if valor:
                    return valor
    return None


def _grupos_por_dia(indices: Optional[List[int]], reparto: Optional[List[str]],
                    routine: Optional[Dict[str, Any]]) -> Dict[int, str]:
    """{índice de la semana: grupo} para los días de entreno.

    El reparto va POR ORDEN sobre los días del cliente: el primer grupo al primer día de
    entreno de su semana, y así. Si el reparto se queda corto, los días de más son
    «Entreno» a secas: un nombre honrado, no un grupo inventado."""
    if not indices:
        return {}
    grupos: Dict[int, str] = {}
    for n, i in enumerate(indices):
        g = None
        if reparto:
            g = reparto[n] if n < len(reparto) else None
        grupos[i] = g or _grupo_estructurado(routine, i) or "Entreno"
    return grupos


async def grupos_del_reparto(perfil: Dict[str, Any]) -> Optional[Dict[int, str]]:
    """Para Mi semana (GET /diets/semana): {índice 0-6: grupo} según el reparto del PDF
    vigente y los días del cliente, o None si falta cualquiera de los dos datos."""
    if not (perfil or {}).get("id"):
        return None
    indices = indices_de_entreno(perfil)
    if not indices:
        return None
    pdf = await db.rutina_pdfs.find_one({"client_id": perfil["id"]},
                                        {"_id": 0, "reparto": 1},
                                        sort=[("uploaded_at", -1)])
    reparto = (pdf or {}).get("reparto") or None
    if not reparto:
        return None
    return _grupos_por_dia(indices, reparto, None)


# ── QUÉ LE TOCA HOY AL QUE TIENE LA RUTINA EN PDF (punto 69, 24-08) ──────────────────
#
# El cabo que quedó del 69. `tiene_rutina_puesta()` (workout_logs) ya cuenta el PDF, pero
# GET /workout-logs/hoy devuelve otro `tiene_rutina` que significa otra cosa -- «¿sé qué te
# toca HOY?» -- y ahí sigue mirando solo la rutina estructurada, con este motivo escrito al
# lado: «del PDF no sale qué días entrena, así que `descanso` sería false SIEMPRE y le
# diríamos "Entreno · Ver la rutina" los siete días».
#
# Del PDF SÍ sale, cuando tiene reparto y el cliente tiene sus días puestos: es lo mismo
# que ya pinta la tira de Mi rutina. Esto lo deja en una función para que quien la llame no
# tenga que copiar el criterio, y devuelve TRES estados, que es lo que hacía falta:
#
#     None                                -> no se sabe (sin reparto o sin días suyos)
#     {"entrena": False, "grupo": None}   -> hoy descansa
#     {"entrena": True, "grupo": "Empuje"} -> hoy le toca eso
#
# Lo que falta para cerrarlo del todo NO está en este fichero: `routes/workout_logs.py`
# tiene que llamar aquí (import dentro de la función, que routines ya importa workout_logs
# y al revés sería circular) y `ClientDashboard.jsx` tiene que distinguir el None -- «no sé
# qué te toca» -- del «hoy descansas», que hoy son el mismo `descanso: false`.
async def dia_de_entreno_del_pdf(perfil: Dict[str, Any],
                                 fecha: str) -> Optional[Dict[str, Any]]:
    """Qué le toca a este cliente el día `fecha` (YYYY-MM-DD) según el reparto de su PDF."""
    if not (perfil or {}).get("id"):
        return None
    grupos = await grupos_del_reparto(perfil)
    if not grupos:
        return None
    try:
        indice = date.fromisoformat(str(fecha)).weekday()
    except (TypeError, ValueError):
        return None
    grupo = grupos.get(indice)
    return {"entrena": bool(grupo), "grupo": grupo}


async def _plan_de_la_semana(perfil: Dict[str, Any]) -> Dict[str, Any]:
    """Todo lo que hace falta para componer la semana de un cliente, en una pieza."""
    pdf = await db.rutina_pdfs.find_one({"client_id": perfil["id"]}, {"_id": 0, "data": 0},
                                        sort=[("uploaded_at", -1)])
    routine = await db.routines.find_one({"client_id": perfil["id"], "status": "active"},
                                         {"_id": 0, "days": 1, "created_at": 1})
    indices = indices_de_entreno(perfil)
    if indices is None and routine:
        # Sin días propios pero con rutina estructurada: los días los dice la rutina.
        indices = sorted({DIAS_SEMANA.index(_plano(d.get("day")))
                          for d in routine.get("days") or []
                          if not d.get("is_rest") and _plano(d.get("day")) in DIAS_SEMANA}) or None
    grupos = _grupos_por_dia(indices, (pdf or {}).get("reparto"), routine)
    return {"pdf": pdf, "routine": routine, "indices": indices, "grupos": grupos}


def _semana_actual(pdf: Optional[Dict[str, Any]], routine: Optional[Dict[str, Any]],
                   hoy: date) -> Optional[int]:
    """En qué semana de la rutina está. Se cuenta desde el LUNES de la semana en que se
    subió el PDF (semana 1 = esa semana): el PDF no trae fecha de inicio, solo la de
    subida, y contar por semanas naturales es lo que casa con la tira de lunes a domingo.
    Sin PDF, desde la creación de la rutina estructurada."""
    inicio = a_madrid((pdf or {}).get("uploaded_at") or (routine or {}).get("created_at"))
    if not inicio:
        return None
    lunes_inicio = inicio.date() - timedelta(days=inicio.date().weekday())
    lunes_hoy = hoy - timedelta(days=hoy.weekday())
    return max(1, (lunes_hoy - lunes_inicio).days // 7 + 1)


@router.get("/semana")
async def semana_de_rutina(hoy_cliente: Optional[str] = None, user=Depends(get_current_user)):
    """La semana de la rutina del cliente: qué grupo toca cada día, qué está hecho, qué
    se dejó y qué toca hoy. Es lo que pinta la cabecera y la tira de Mi rutina.

    Sin gate de plan, como /routines/pdf/info: si su entrenador le subió la rutina, es
    suya. Lo de MARCAR sí depende del interruptor `t3_entreno`, y va en `puede_marcar`."""
    perfil = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not perfil or not perfil.get("id"):
        return {"hay": False}

    plan = await _plan_de_la_semana(perfil)
    pdf, routine, indices, grupos = plan["pdf"], plan["routine"], plan["indices"], plan["grupos"]
    if not grupos or not (pdf or routine):
        # Sin días del cliente (o sin rutina ninguna) no hay semana que pintar. Se dice
        # qué falta para que la pantalla pueda seguir enseñando el PDF a secas.
        return {"hay": False, "tiene_pdf": bool(pdf), "tiene_rutina": bool(routine),
                "faltan_dias": not indices}

    # El «hoy» del RELOJ DEL CLIENTE si la pantalla lo mando (bloque F, 23-08); sin el,
    # España. Decide la marca «hoy» de la tira y la semana que se pinta.
    from core.tiempo import dia_del_cliente
    hoy = date.fromisoformat(dia_del_cliente(hoy_cliente))
    lunes = hoy - timedelta(days=hoy.weekday())
    fechas = [(lunes + timedelta(days=i)).isoformat() for i in range(7)]

    puede_marcar = await pantalla_activa_rutina()
    logs: Dict[str, Dict[str, Any]] = {}
    if puede_marcar:
        async for l in db.workout_logs.find(
                {"client_id": perfil["id"], "fecha": {"$gte": fechas[0], "$lte": fechas[6]}},
                {"_id": 0, "fecha": 1, "hecho": 1}):
            logs[l["fecha"]] = l

    # Las recuperaciones de ESTA semana: un entreno perdido que se va a hacer otro día.
    recuperaciones = {}
    por_original = {}
    async for r in db.workout_recuperaciones.find(
            {"client_id": perfil["id"], "fecha": {"$gte": fechas[0], "$lte": fechas[6]}},
            {"_id": 0}):
        recuperaciones[r["fecha"]] = r
        por_original[r.get("fecha_original")] = r

    dias = []
    for i, fecha in enumerate(fechas):
        rec = recuperaciones.get(fecha)
        entrena = i in grupos or bool(rec)
        grupo = (rec or {}).get("grupo") if rec else grupos.get(i)
        log = logs.get(fecha)
        dias.append({
            "fecha": fecha,
            "dia": DIAS_BONITOS[i],
            "entrena": entrena,
            "grupo": grupo if entrena else None,
            "recuperacion": bool(rec),
            # A qué día se movió, si este se perdió y se va a recuperar.
            "recuperado_en": (por_original.get(fecha) or {}).get("fecha"),
            # true/false solo con el registro encendido; null = no hay forma de saberlo.
            "hecho": bool(log and log.get("hecho")) if (puede_marcar and entrena) else None,
            "registrado": bool(log),
            "hoy": fecha == hoy.isoformat(),
        })

    # EL QUE SE DEJÓ: el día de entreno más reciente de esta semana, anterior a hoy, sin
    # ningún registro (decir «no lo hice» TAMBIÉN es un registro y no se le vuelve a
    # preguntar) y sin una recuperación ya apuntada. Solo uno: la pregunta es una, no una
    # lista de reproches.
    pendiente = None
    if puede_marcar:
        for d in reversed(dias):
            if d["fecha"] >= hoy.isoformat() or not d["entrena"]:
                continue
            if d["registrado"] or d["recuperado_en"]:
                continue
            pendiente = {"fecha": d["fecha"], "dia": d["dia"], "grupo": d["grupo"]}
            break

    # «Rutina #2»: qué número hace este PDF entre los suyos.
    numero = await db.rutina_pdfs.count_documents({"client_id": perfil["id"]}) if pdf else None

    return {
        "hay": True,
        "tiene_pdf": bool(pdf),
        "numero": numero,
        "semanas": (pdf or {}).get("semanas"),
        "semana_actual": _semana_actual(pdf, routine, hoy),
        "dias_de_entreno": len(indices or []),
        "dias": dias,
        "hoy": next(d for d in dias if d["hoy"]),
        "pendiente": pendiente,
        "puede_marcar": puede_marcar,
    }


async def pantalla_activa_rutina() -> bool:
    """El interruptor `t3_entreno`, el mismo que gobierna todo el registro de entrenos."""
    from routes.settings import pantalla_activa
    return await pantalla_activa("t3_entreno")


def _fecha_de_esta_semana(valor: Any, hoy: date) -> date:
    """Valida una fecha del cliente: tiene que ser un día de SU semana actual."""
    try:
        f = date.fromisoformat(str(valor or ""))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Esa fecha no vale.")
    lunes = hoy - timedelta(days=hoy.weekday())
    if not (lunes <= f <= lunes + timedelta(days=6)):
        raise HTTPException(status_code=400,
                            detail="Solo se puede tocar un día de esta semana.")
    return f


@router.post("/semana/hecho")
async def marcar_dia_de_la_semana(data: Dict[str, Any], ctx=Depends(require_access("rutina"))):
    """«Sí lo hice»: marca como hecho un día de ESTA semana que ya pasó.

    POST /workout-logs solo escribe el día de hoy (y está bien que así sea); esto cubre
    el único caso nuevo del apartado 12: el entreno del martes que se marca el jueves.
    Escribe en la MISMA colección y con la misma forma, así que Inicio, el Diario y los
    reportes lo cuentan igual. No pisa un registro que ya exista más que para ponerlo en
    hecho."""
    if not await pantalla_activa_rutina():
        raise HTTPException(status_code=403,
                            detail="El registro de entrenos todavía no está disponible.")
    profile = ctx["profile"]
    # El «hoy» del cliente si viaja en el body (bloque F, 23-08): a un cliente al este de
    # España su propio hoy le salia como «todavía no ha llegado».
    from core.tiempo import dia_del_cliente
    hoy = date.fromisoformat(dia_del_cliente((data or {}).get("hoy")))
    f = _fecha_de_esta_semana((data or {}).get("fecha"), hoy)
    if f > hoy:
        raise HTTPException(status_code=400, detail="Ese día todavía no ha llegado.")
    grupo = str((data or {}).get("grupo") or "").strip()[:200] or None
    ahora = datetime.now(timezone.utc).isoformat()
    await db.workout_logs.update_one(
        {"client_id": profile["id"], "fecha": f.isoformat()},
        {"$set": {"hecho": True, "updated_at": ahora},
         "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": ahora,
                          "tipo": "entreno", "dia_rutina": grupo, "estrellas": None,
                          "nota": None, "pesos": [], "compartida": False,
                          "routine_id": None}},
        upsert=True,
    )
    # Si ese día tenía una recuperación apuntada, ya no hace falta: lo hizo.
    await db.workout_recuperaciones.delete_many(
        {"client_id": profile["id"], "fecha_original": f.isoformat()})
    return {"ok": True, "fecha": f.isoformat()}


@router.post("/semana/recuperar")
async def recuperar_entreno(data: Dict[str, Any], ctx=Depends(require_access("rutina"))):
    """«Recuperarlo otro día»: el entreno perdido no se mueve, se RECUPERA en un día de
    descanso de esta semana (decisión del apartado 12: «No se puede mover. Si se ha
    perdido, se recupera otro día»). Se apunta la recuperación y ese día pasa a enseñar
    el grupo pendiente; marcarlo hecho es lo mismo de siempre (workout_logs)."""
    if not await pantalla_activa_rutina():
        raise HTTPException(status_code=403,
                            detail="El registro de entrenos todavía no está disponible.")
    profile = ctx["profile"]
    perfil = await db.client_profiles.find_one({"id": profile["id"]}, {"_id": 0}) or profile
    plan = await _plan_de_la_semana(perfil)
    grupos = plan["grupos"]
    if not grupos:
        raise HTTPException(status_code=400, detail="Todavía no sabemos tu semana de entreno.")

    from core.tiempo import dia_del_cliente
    hoy = date.fromisoformat(dia_del_cliente((data or {}).get("hoy")))
    original = _fecha_de_esta_semana((data or {}).get("fecha_original"), hoy)
    nueva = _fecha_de_esta_semana((data or {}).get("fecha"), hoy)
    if original >= hoy:
        raise HTTPException(status_code=400, detail="Ese entreno no se ha perdido todavía.")
    if original.weekday() not in grupos:
        raise HTTPException(status_code=400, detail="Ese día no tocaba entreno.")
    if nueva < hoy:
        raise HTTPException(status_code=400, detail="El día para recuperarlo tiene que estar por llegar.")
    if nueva.weekday() in grupos:
        raise HTTPException(status_code=400,
                            detail="Ese día ya tiene su entreno: elige un día de descanso.")
    if await db.workout_logs.find_one({"client_id": profile["id"], "fecha": original.isoformat()}):
        raise HTTPException(status_code=400, detail="Ese día ya está registrado.")

    ahora = datetime.now(timezone.utc).isoformat()
    await db.workout_recuperaciones.update_one(
        {"client_id": profile["id"], "fecha_original": original.isoformat()},
        {"$set": {"fecha": nueva.isoformat(), "grupo": grupos.get(original.weekday()),
                  "updated_at": ahora},
         "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": ahora}},
        upsert=True,
    )
    return {"ok": True, "fecha": nueva.isoformat(), "grupo": grupos.get(original.weekday())}
