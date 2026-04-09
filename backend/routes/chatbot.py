"""
Rutas del chatbot de nutrición.
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from datetime import datetime
from typing import Optional

from core.database import db
from core.security import get_current_user
from models.diet import ChatConfigRequest, ChatMessageRequest

# Import chatbot functions
from chatbot import get_or_create_chatbot, clear_session
from pdf_generator import generate_diet_pdf

router = APIRouter(prefix="/chatbot", tags=["chatbot"])

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
    
    await get_or_create_chatbot(session_id, db, user_macros)
    
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
    chatbot = await get_or_create_chatbot(session_id, db)
    
    distribucion = chatbot.configure_day(
        tipo_dia=config.tipo_dia,
        num_comidas=config.num_comidas,
        momento_entreno=config.momento_entreno,
        opcion_peri=config.opcion_peri
    )
    
    comida_1 = distribucion["comidas"]["C1"]
    mensaje = f"Perfecto, día de {config.tipo_dia} con {config.num_comidas} comidas."
    mensaje += f"\n\nVamos con la Comida 1. Tu objetivo es: P={comida_1['P']}g, H={comida_1['H']}g, G={comida_1['G']}g."
    mensaje += "\n\n¿Qué te apetece desayunar?"
    
    return {
        "session_id": session_id,
        "distribucion": distribucion,
        "comida_actual": 1,
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
    
    chatbot = await get_or_create_chatbot(session_id, db)
    response = await chatbot.process_message(request.message)
    
    return {
        "session_id": session_id,
        "response": response,
        "state": {
            "step": chatbot.state["step"],
            "comida_actual": chatbot.state["comida_actual"],
            "restante": chatbot.get_remaining_macros()
        }
    }

@router.post("/complete-meal")
async def chatbot_complete_meal(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Marca la comida actual como completa."""
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
        objetivo = chatbot.get_current_meal_macros()
        return {
            "session_id": session_id,
            "comida_completada": resultado,
            "dia_completo": False,
            "comida_actual": siguiente,
            "objetivo": objetivo,
            "mensaje": f"Comida {siguiente-1} guardada. Vamos con la Comida {siguiente}. Objetivo: P={objetivo['P']}g, H={objetivo['H']}g, G={objetivo['G']}g. ¿Qué quieres comer?"
        }

@router.get("/summary")
async def chatbot_summary(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Obtiene el resumen del día."""
    chatbot = await get_or_create_chatbot(session_id, db)
    return chatbot.get_day_summary()

@router.post("/reset")
async def chatbot_reset(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Reinicia la sesión de chatbot."""
    clear_session(session_id)
    return {"message": "Sesión reiniciada", "session_id": session_id}

@router.get("/export-pdf")
async def export_diet_pdf_route(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Genera y descarga un PDF con el resumen de la dieta del día."""
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
