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
from chatbot import get_or_create_chatbot, clear_session
from routes.diets import upsert_diet_doc
from pdf_generator import generate_diet_pdf

router = APIRouter(prefix="/chatbot", tags=["chatbot"])


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
    
    user_macros = {}
    if profile:
        mt = profile.get("macros_training", {})
        mr = profile.get("macros_rest", {})
        mp = profile.get("macros_periworkout", {})
        
        user_macros = {
            "p_entreno": mt.get("proteinas", 160),
            "h_entreno": mt.get("hidratos", 50),
            "g_entreno": mt.get("grasas", 40),
            "p_peri": mp.get("proteinas", 35),
            "h_peri": mp.get("hidratos", 15),
            "p_descanso": mr.get("proteinas", 140),
            "h_descanso": mr.get("hidratos", 40),
            "g_descanso": mr.get("grasas", 40)
        }
    else:
        user_macros = {
            "p_entreno": 160,
            "h_entreno": 50,
            "g_entreno": 40,
            "p_peri": 35,
            "h_peri": 15,
            "p_descanso": 140,
            "h_descanso": 40,
            "g_descanso": 40
        }
    
    chatbot = await get_or_create_chatbot(session_id, db, user_macros)

    # Cargar preferencias del usuario para filtrar las sugerencias de alimentos
    if profile:
        chatbot.set_preferences(
            food_preferences=profile.get("food_preferences", []),
            avoided_categories=profile.get("avoided_categories", []),
            avoided_keywords=profile.get("avoided_keywords", []),
        )

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
    mensaje += "\n\n¿Qué quieres tomar?"

    return {
        "session_id": session_id,
        "distribucion": distribucion,
        "comida_actual": 1,
        "meal_order": chatbot.state["meal_order"],
        "meal_nombre": label,
        "objetivo": objetivo,
        "day_overview": chatbot.get_day_overview(),
        "mensaje": mensaje
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
    response = await chatbot.process_message(request.message)

    return {
        "session_id": session_id,
        "response": response,
        "state": {
            "step": chatbot.state["step"],
            "comida_actual": chatbot.state["comida_actual"],
            "meal_nombre": chatbot.meal_label(chatbot.current_meal_key()),
            "restante": chatbot.get_remaining_macros(),
        },
        "day_overview": chatbot.get_day_overview(),
    }


@router.post("/suggest-foods")
async def chatbot_suggest_foods(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Sugiere alimentos sueltos que cuadran con lo que falta de la comida actual."""
    _assert_session_owner(session_id, current_user)
    chatbot = await get_or_create_chatbot(session_id, db)
    return {"session_id": session_id, "response": await chatbot.suggest_foods_for_current_meal()}


@router.post("/add-food")
async def chatbot_add_food(
    session_id: str,
    alimento_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Añade un alimento concreto (cuando el usuario toca una sugerencia)."""
    _assert_session_owner(session_id, current_user)
    chatbot = await get_or_create_chatbot(session_id, db)
    return {"session_id": session_id, "response": await chatbot.add_food_by_id(alimento_id)}


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
    return {"session_id": session_id, "response": chatbot._meal_response([], [])}

@router.post("/complete-meal")
async def chatbot_complete_meal(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Marca la comida actual como completa."""
    _assert_session_owner(session_id, current_user)
    chatbot = await get_or_create_chatbot(session_id, db)
    resultado = chatbot.complete_current_meal()
    
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
            "mensaje": "¡Día completo! Aquí tienes el resumen de tu dieta."
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
            "mensaje": (f"Comida guardada ✓. Vamos con {label}. Tu objetivo es:\n"
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
    """Indica si la sesión de chat sigue viva en memoria del backend.
    El frontend lo usa al volver a la página para detectar sesiones perdidas
    (p. ej. tras un reinicio del backend) y reiniciar limpio."""
    _assert_session_owner(session_id, current_user)
    from chatbot import _chatbot_sessions
    return {"exists": session_id in _chatbot_sessions}

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

@router.post("/reset")
async def chatbot_reset(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Reinicia la sesión de chatbot."""
    _assert_session_owner(session_id, current_user)
    clear_session(session_id)
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
