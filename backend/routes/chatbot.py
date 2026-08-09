"""
Rutas del chatbot de nutrición.
"""
import re

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from datetime import datetime
from typing import Optional

from core.database import db
from core.security import get_current_user
from models.diet import ChatConfigRequest, ChatMessageRequest

# Import chatbot functions
from chatbot import get_or_create_chatbot, clear_session, save_chatbot_session, session_exists
from routes.diets import upsert_diet_doc
from pdf_generator import generate_diet_pdf

router = APIRouter(prefix="/chatbot", tags=["chatbot"])

# Sello de versión del asistente: al arrancar (y en cada recarga) se imprime la fecha
# del fichero más reciente del agente. Un vistazo al log dice si el server sirve el
# código actual; se añadió tras una noche entera persiguiendo "regresiones" que eran
# un recargador muerto sirviendo código viejo.
def _sello_agente():
    import os as _o
    from datetime import datetime as _dt
    base = _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))
    ficheros = ["agent_loop.py", "agent_tools.py", "chatbot.py", "food_semantic.py"]
    reciente = max(_o.path.getmtime(_o.path.join(base, f)) for f in ficheros)
    print(f"[agente] código del {_dt.fromtimestamp(reciente):%Y-%m-%d %H:%M:%S}")

_sello_agente()


def _assert_session_owner(session_id: str, current_user: dict):
    """Verifica que la sesión de chat pertenezca a quien la usa.

    Los session_id se crean como `chat_<user_id>_<fecha-hora>` en /start. Como el user_id
    es un UUID (sin guiones bajos), comprobar el prefijo basta para atar la sesión al dueño
    y cerrar el IDOR (un cliente no puede tocar la sesión de otro aunque conozca su id)."""
    uid = current_user.get("id") or current_user.get("user_id")
    if not session_id or not uid or not session_id.startswith(f"chat_{uid}_"):
        raise HTTPException(status_code=403, detail="Esta sesión de chat no te pertenece.")

@router.post("/start")
async def chatbot_start(current_user: dict = Depends(get_current_user)):
    """Inicia una nueva sesión de chatbot."""
    user_id = current_user.get('id') or current_user.get('user_id')
    session_id = f"chat_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    profile = await db.client_profiles.find_one(
        {"user_id": user_id},
        {"_id": 0}
    )
    
    # Los macros salen de `macros_por_fecha`, la MISMA función que usa la pantalla de
    # Nutrición. Aquí se leían del perfil (`macros_training`) y ahí, del historial vigente
    # para el día: 70 g de hidratos de diferencia al día para el mismo cliente, porque el
    # perfil se queda viejo en cuanto hay una revisión de macros, y 210 de los 236 clientes
    # tienen revisiones.
    #
    # Al arrancar todavía no se sabe qué día se va a montar (lo dice el front en
    # /configure), así que se resuelve para HOY y se recalcula allí con la fecha buena.
    from macros_por_fecha import para_el_chat
    user_macros = await para_el_chat(db, profile, datetime.now().strftime("%Y-%m-%d"))


    chatbot = await get_or_create_chatbot(session_id, db, user_macros)

    # Cargar preferencias del usuario para filtrar las sugerencias de alimentos.
    # En NOMBRES (punto 4.18): el filtro busca en AVOIDABLE_PREFIXES, que esta indexado por
    # nombre, y los clientes migrados las tienen guardadas como codigos. Sin traducirlas, el
    # asistente ignoraba lo que le gusta y lo que evita a 100 clientes.
    if profile:
        from core.preferencias import a_nombres
        chatbot.set_preferences(
            food_preferences=a_nombres(profile.get("food_preferences", [])),
            avoided_categories=a_nombres(profile.get("avoided_categories", [])),
            avoided_keywords=profile.get("avoided_keywords", []),
        )
    await save_chatbot_session(chatbot)

    return {
        "session_id": session_id,
        "macros": user_macros,
        "message": "¡Hola! Soy tu asistente de nutrición. ¿Hoy es día de entrenamiento o descanso?"
    }

@router.post("/configure")
async def chatbot_configure(
    config: ChatConfigRequest,
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Configura el día (tipo, comidas, momento entreno)."""
    _assert_session_owner(session_id, current_user)
    chatbot = await get_or_create_chatbot(session_id, db)

    if config.fecha:
        chatbot.state["fecha_objetivo"] = config.fecha

    # Los macros de un cliente cambian con el tiempo, así que se resuelven PARA EL DÍA que
    # se va a montar, no una vez al arrancar la sesión. Sin esto, cambiar de día dentro de
    # la conversación («móntame el de mañana») dejaba los objetivos del día anterior.
    if config.fecha:
        from macros_por_fecha import para_el_chat
        user_id = current_user.get("id") or current_user.get("user_id")
        profile = await db.client_profiles.find_one({"user_id": user_id}, {"_id": 0})
        if profile:
            chatbot.set_user_macros(await para_el_chat(db, profile, config.fecha))

    distribucion = chatbot.configure_day(
        tipo_dia=config.tipo_dia,
        num_comidas=config.num_comidas,
        momento_entreno=config.momento_entreno,
        opcion_peri=config.opcion_peri,
        single_meal=config.single_meal
    )

    key = chatbot.current_meal_key()
    label = chatbot.meal_label(key)
    objetivo = chatbot.get_current_meal_macros()

    total = chatbot.total_meals()
    base_n = chatbot.state["num_comidas"]
    n_peri = total - base_n
    extra = f" (más {n_peri} peri-entreno)" if n_peri > 0 else ""
    if chatbot.state.get("single_meal"):
        mensaje = f"Perfecto, día de {config.tipo_dia} en bloque único (1 comida){extra}."
    else:
        mensaje = f"Perfecto, día de {config.tipo_dia} con {base_n} comidas{extra}."
    mensaje += (f"\n\nVamos con {label}. Tu objetivo es:\n"
                f"• Proteína: {objetivo['P']} g\n"
                f"• Hidratos: {objetivo['H']} g\n"
                f"• Grasa: {objetivo['G']} g")
    # Si el cambio se ha llevado por delante alguna comida (el intra y el post al pasar a
    # descanso, la Comida 4 al bajar a 3), lo que había ahí se ha traspasado a otra: hay
    # que DECIRLO. Antes se borraba en silencio y el cliente perdía el trabajo sin enterarse.
    reubicado = chatbot.state.get("reubicado_al_reconfigurar") or []
    if reubicado:
        mensaje += "\n\n" + _texto_reubicado(reubicado)
    mensaje += "\n\n¿Qué quieres tomar?"

    await save_chatbot_session(chatbot)
    return {
        "session_id": session_id,
        "distribucion": distribucion,
        "comida_actual": 1,
        "meal_order": chatbot.state["meal_order"],
        "meal_nombre": label,
        "objetivo": objetivo,
        "day_overview": chatbot.get_day_overview(),
        "reubicado": reubicado,
        # Lo que ya hay montado en la comida a la que se llega: el front vaciaba su lista
        # al reconfigurar y, con el traspaso, el cliente vería el aviso pero no el
        # alimento en pantalla hasta recargar.
        "alimentos": (chatbot.state["comidas_completadas"].get(key) or {}).get("alimentos", []),
        "mensaje": mensaje
    }


def _texto_reubicado(reubicado: list) -> str:
    """Aviso de a dónde ha ido a parar lo de las comidas que ya no existen."""
    por_destino = {}
    for r in reubicado:
        por_destino.setdefault((r["desde_nombre"], r["hacia_nombre"]), []).append(
            f"{r['nombre']} ({int(round(r['cantidad_g']))} g)")
    partes = [f"lo que tenías en {desde} ({', '.join(items)}) ha pasado a {hacia}"
              for (desde, hacia), items in por_destino.items()]
    return ("⚠️ Con este cambio " + "; ".join(partes) +
            ". No se ha borrado nada, pero revisa esas comidas porque los macros habrán cambiado.")

# Los mensajes van por el bucle del agente (agent_loop) con sus herramientas. El router
# de intenciones anterior se borró en F3 (06-08) tras validar el agente con el banco de
# casos (48/60 del router frente a 59-60/60 del agente); volver atrás es git revert.
async def _procesar_mensaje(chatbot, texto: str, progreso=None):
    from agent_loop import AgentLoop
    loop = await AgentLoop.crear(chatbot, progreso=progreso)
    return await loop.procesar(texto)


def _estado_para_front(chatbot) -> dict:
    """El estado que el front necesita tras cada mensaje. Lleva la CONFIG del día para
    que el front la refleje cuando el agente reconfigura por chat ('mejor 3 comidas'):
    antes eso lo parseaba el propio front con regex (leerCambioDeConfig), que era el
    mismo hardcodeo en otro idioma."""
    st = chatbot.state
    # La fecha va por el mismo camino y por el mismo motivo: quién decide que el cliente
    # quiere montar otro día es el agente, no el regex del front, que con "hoy es día de
    # descanso" cambiaba de día y se dejaba lo de descanso. Se consume de una vez: si se
    # quedara puesta, el front reabriría ese día en cada mensaje siguiente.
    fecha_pedida = st.pop("fecha_pedida", None)
    return {
        "step": st["step"],
        "comida_actual": st["comida_actual"],
        "meal_nombre": chatbot.meal_label(chatbot.current_meal_key()),
        "restante": chatbot.get_remaining_macros(),
        "fecha_pedida": fecha_pedida,
        "config": {
            "tipo_dia": st.get("tipo_dia"),
            "num_comidas": st.get("num_comidas"),
            "momento_entreno": st.get("momento_entreno"),
            "opcion_peri": st.get("opcion_peri"),
            "single_meal": st.get("single_meal", False),
        },
    }


@router.post("/message")
async def chatbot_message(
    request: ChatMessageRequest,
    current_user: dict = Depends(get_current_user)
):
    """Envía un mensaje al chatbot."""
    session_id = request.session_id
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id requerido")
    _assert_session_owner(session_id, current_user)

    chatbot = await get_or_create_chatbot(session_id, db)
    response = await _procesar_mensaje(chatbot, request.message)

    await save_chatbot_session(chatbot)
    return {
        "session_id": session_id,
        "response": response,
        "state": _estado_para_front(chatbot),
        "day_overview": chatbot.get_day_overview(),
    }


@router.post("/message-stream")
async def chatbot_message_stream(
    request: ChatMessageRequest,
    current_user: dict = Depends(get_current_user)
):
    """Como /message pero en SSE: emite un evento por herramienta que usa el agente
    (el indicador de "qué estoy haciendo" aprobado en el plan) y al final la respuesta
    completa. Con el agente apagado emite solo el evento final, así el front puede
    llamar siempre aquí sin preguntar por la bandera."""
    import asyncio
    import json as _json

    session_id = request.session_id
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id requerido")
    _assert_session_owner(session_id, current_user)
    chatbot = await get_or_create_chatbot(session_id, db)

    ETIQUETAS = {
        "buscar_alimentos": "Buscando en el catálogo...",
        "componer_menu": "Montando el menú...",
        "revisar_borrador": "Revisando el menú...",
        "editar_borrador": "Ajustando el menú...",
        "aplicar_borrador": "Añadiendo la comida...",
        "editar_comida": "Actualizando la comida...",
        "ver_estado": "Consultando cómo vas...",
        "navegar": "Cambiando de comida...",
        "guardar_comida": "Guardando la comida...",
        "explicar": "Consultando el método...",
        "configurar_dia": "Reconfigurando el día...",
    }
    cola: asyncio.Queue = asyncio.Queue()

    async def trabajar():
        try:
            resp = await _procesar_mensaje(
                chatbot, request.message,
                progreso=lambda h: cola.put_nowait(
                    {"tipo": "progreso", "texto": ETIQUETAS.get(h, "Trabajando...")}))
            await save_chatbot_session(chatbot)
            await cola.put({"tipo": "respuesta", "response": resp,
                            "state": _estado_para_front(chatbot),
                            "day_overview": chatbot.get_day_overview()})
        except Exception as e:
            await cola.put({"tipo": "error", "detalle": f"{type(e).__name__}"})
        await cola.put(None)

    async def eventos():
        tarea = asyncio.create_task(trabajar())
        while True:
            item = await cola.get()
            if item is None:
                break
            yield f"data: {_json.dumps(item, ensure_ascii=False, default=str)}\n\n"
        await tarea

    return StreamingResponse(eventos(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


@router.post("/apply-draft")
async def chatbot_apply_draft(
    session_id: str,
    borrador_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Aplica un borrador de menú del agente a la comida actual (el botón "Elegir este
    menú" de la tarjeta). Pasa por la revisión del backend: si algo choca con una
    restricción, se devuelve el porqué en vez de aplicar."""
    _assert_session_owner(session_id, current_user)
    chatbot = await get_or_create_chatbot(session_id, db)
    from agent_tools import AgentTools
    tools = await AgentTools.crear(chatbot)
    resultado = await tools.aplicar_borrador(borrador_id)
    await save_chatbot_session(chatbot)
    if resultado.get("ok"):
        response = chatbot._meal_response([], [])
        response["message"] = "Menú aplicado a la comida ✓."
    else:
        detalles = [p.get("detalle") for p in resultado.get("bloqueado_por", []) if p.get("detalle")]
        response = {"action": "no_foods",
                    "message": ("No lo he aplicado: " + "; ".join(detalles) + ". "
                                "Dime si lo cambio o lo pongo igualmente.")
                    if detalles else "No he podido aplicar ese menú.",
                    "day_overview": chatbot.get_day_overview()}
    return {"session_id": session_id, "response": response}


@router.post("/suggest-foods")
async def chatbot_suggest_foods(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Sugiere alimentos sueltos que cuadran con lo que falta de la comida actual."""
    _assert_session_owner(session_id, current_user)
    chatbot = await get_or_create_chatbot(session_id, db)
    response = await chatbot.suggest_foods_for_current_meal()
    await save_chatbot_session(chatbot)
    return {"session_id": session_id, "response": response}


@router.post("/add-food")
async def chatbot_add_food(
    session_id: str,
    alimento_id: int,
    cantidad_g: Optional[float] = None,
    current_user: dict = Depends(get_current_user)
):
    """Añade un alimento concreto (cuando el usuario toca una sugerencia).
    `cantidad_g` llega cuando la opción tenía cantidad fijada por el usuario
    (desambiguación de "150g de pavo"): se respeta tal cual."""
    _assert_session_owner(session_id, current_user)
    chatbot = await get_or_create_chatbot(session_id, db)
    response = await chatbot.add_food_by_id(alimento_id, cantidad_g)
    await save_chatbot_session(chatbot)
    return {"session_id": session_id, "response": response}


@router.post("/go-to-meal")
async def chatbot_go_to_meal(
    session_id: str,
    idx: int,
    current_user: dict = Depends(get_current_user)
):
    """Salta a una comida concreta para editarla (p.ej. una ya guardada)."""
    _assert_session_owner(session_id, current_user)
    chatbot = await get_or_create_chatbot(session_id, db)
    chatbot.go_to_meal(idx)
    await save_chatbot_session(chatbot)
    return {"session_id": session_id, "response": chatbot._meal_response([], [])}


@router.post("/remove-food")
async def chatbot_remove_food(
    session_id: str,
    index: int,
    current_user: dict = Depends(get_current_user)
):
    """Quita un alimento de la comida actual por su posición."""
    _assert_session_owner(session_id, current_user)
    chatbot = await get_or_create_chatbot(session_id, db)
    chatbot.remove_food_at(index)
    await save_chatbot_session(chatbot)
    return {"session_id": session_id, "response": chatbot._meal_response([], [])}

@router.post("/complete-meal")
async def chatbot_complete_meal(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Marca la comida actual como completa."""
    _assert_session_owner(session_id, current_user)
    chatbot = await get_or_create_chatbot(session_id, db)

    # Aviso si se guarda una comida sin cuadrar (se permite, pero se dice)
    label_guardada = chatbot.meal_label(chatbot.current_meal_key())
    rem = chatbot.get_remaining_macros()
    nombres_m = {"P": "proteína", "H": "hidratos", "G": "grasa"}
    faltan = [f"{rem[k]} g de {nombres_m[k]}" for k in ("P", "H", "G") if rem.get(k, 0) > 4]
    pasan = [f"{abs(rem[k])} g de {nombres_m[k]}" for k in ("P", "H", "G") if rem.get(k, 0) < -4]
    aviso = ""
    if faltan:
        aviso += f"\n⚠️ Ojo: {label_guardada} quedó sin cuadrar (faltan {' y '.join(faltan)})."
    if pasan:
        aviso += f"\n⚠️ En {label_guardada} te pasas {' y '.join(pasan)}."

    resultado = chatbot.complete_current_meal()
    await save_chatbot_session(chatbot)

    if resultado.get("vacia"):
        return {
            "session_id": session_id,
            "error": resultado.get("error"),
            "comida_actual": resultado.get("comida"),
            "objetivo": chatbot.get_current_meal_macros(),
            "mensaje": resultado.get("error")
        }
    
    if chatbot.state["step"] == "complete":
        summary = chatbot.get_day_summary()
        return {
            "session_id": session_id,
            "comida_completada": resultado,
            "dia_completo": True,
            "resumen": summary,
            "mensaje": "¡Día completo! Aquí tienes el resumen de tu dieta." + aviso
        }
    else:
        siguiente = chatbot.state["comida_actual"]
        label = chatbot.meal_label(chatbot.current_meal_key())
        objetivo = chatbot.get_current_meal_macros()
        return {
            "session_id": session_id,
            "comida_completada": resultado,
            "dia_completo": False,
            "comida_actual": siguiente,
            "meal_nombre": label,
            "objetivo": objetivo,
            "day_overview": chatbot.get_day_overview(),
            "mensaje": (f"Comida guardada ✓.{aviso}\nVamos con {label}. Tu objetivo es:\n"
                        f"• Proteína: {objetivo['P']} g\n"
                        f"• Hidratos: {objetivo['H']} g\n"
                        f"• Grasa: {objetivo['G']} g\n\n¿Qué quieres tomar?")
        }

@router.get("/summary")
async def chatbot_summary(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Obtiene el resumen del día."""
    _assert_session_owner(session_id, current_user)
    chatbot = await get_or_create_chatbot(session_id, db)
    return chatbot.get_day_summary()

@router.get("/session-exists")
async def chatbot_session_exists(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Indica si la sesión de chat sigue viva (persistida en Mongo).
    El frontend lo usa al volver a la página para detectar sesiones perdidas
    (p. ej. borradas o muy antiguas) y reiniciar limpio."""
    _assert_session_owner(session_id, current_user)
    return {"exists": await session_exists(session_id, db)}

@router.post("/save-to-diet")
async def chatbot_save_to_diet(
    session_id: str,
    fecha: str,
    overwrite: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """Vuelca la dieta construida por el chatbot en la pestaña de nutrición (db.diets)
    del día `fecha`. Si ese día ya tiene una dieta con alimentos y overwrite=False,
    devuelve needs_confirmation en lugar de sobrescribir."""
    _assert_session_owner(session_id, current_user)
    user_id = current_user.get('id') or current_user.get('user_id')
    chatbot = await get_or_create_chatbot(session_id, db)

    if chatbot.state.get("distribucion") is None:
        raise HTTPException(
            status_code=400,
            detail="No hay dieta configurada. Configura el día y añade alimentos antes de volcar."
        )

    if not re.match(r"^\d{4}-\d{2}-\d{2}$", fecha or ""):
        raise HTTPException(status_code=400, detail="Fecha inválida. Usa el formato YYYY-MM-DD.")

    # Chequeo de sobrescritura: ¿el día ya tiene alimentos?
    existing = await db.diets.find_one({"user_id": user_id, "fecha": fecha})
    if existing and not overwrite:
        tiene_alimentos = any(
            len((m or {}).get("alimentos", [])) > 0
            for m in (existing.get("comidas") or {}).values()
        )
        if tiene_alimentos:
            return {
                "needs_confirmation": True,
                "fecha": fecha,
                "message": f"Ya tienes una dieta guardada el {fecha}. ¿Quieres sobrescribirla?"
            }

    comidas = chatbot.export_to_diet_comidas()
    targets = chatbot.export_distribution_targets()

    await upsert_diet_doc(user_id, {
        "fecha": fecha,
        "tipo_dia": chatbot.state.get("tipo_dia"),
        "num_comidas": chatbot.state.get("num_comidas"),
        "momento_entreno": chatbot.state.get("momento_entreno"),
        "opcion_peri": chatbot.state.get("opcion_peri"),
        "comidas": comidas,
        "macros_snapshot": chatbot.state.get("macros_usuario"),
        "distribution_targets": targets,
        "is_cuadrado": False,
        "comida_volcada": None,
    })

    return {
        "message": "Dieta volcada en tu pestaña de nutrición",
        "fecha": fecha,
        "comidas": list(comidas.keys())
    }

@router.delete("/sessions")
async def chatbot_end_my_sessions(current_user: dict = Depends(get_current_user)):
    """Borra TODAS las sesiones de chatbot del usuario. El frontend lo llama al
    cerrar sesión: la conversación caduca con el logout, no espera al TTL."""
    uid = current_user.get("id") or current_user.get("user_id")
    result = await db.chatbot_sessions.delete_many({"session_id": {"$regex": f"^chat_{re.escape(uid)}_"}})
    return {"deleted": result.deleted_count}


@router.post("/reset")
async def chatbot_reset(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Reinicia la sesión de chatbot."""
    _assert_session_owner(session_id, current_user)
    await clear_session(session_id, db)
    return {"message": "Sesión reiniciada", "session_id": session_id}

@router.get("/export-pdf")
async def export_diet_pdf_route(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Genera y descarga un PDF con el resumen de la dieta del día."""
    _assert_session_owner(session_id, current_user)
    chatbot = await get_or_create_chatbot(session_id, db)

    if chatbot.state.get("distribucion") is None:
        raise HTTPException(
            status_code=400, 
            detail="No hay dieta configurada para exportar. Primero configura tu día y añade alimentos."
        )
    
    summary = chatbot.get_day_summary()
    user_name = current_user.get("name", "Cliente")
    fecha = datetime.now().strftime("%d/%m/%Y")
    
    pdf_buffer = generate_diet_pdf(summary, user_name, fecha)
    filename = f"dieta_jg12_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
