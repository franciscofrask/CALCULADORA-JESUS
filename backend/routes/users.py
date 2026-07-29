"""
Rutas de usuarios: perfiles, preferencias y macros.
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import uuid

from core.database import db
from core.security import get_current_user
from models.user import (
    ClientProfile, ClientProfileCreate, ClientProfileUpdate,
    MacrosUpdate, PLAN_TYPES, PLAN_CATALOG, QuestionnaireSubmit, OnboardingUpdate,
    Nivel1Submit, AjustesMacros
)
from target_calculator import calcular_targets, targets_to_profile_macros
from macro_engine import calcular_macros_v2, ajustes_to_kwargs, multiplicadores_de
from core.plan_access import tiene_entrenador_detras
from core.quiz_store import guardar_quiz_respuestas, registrar_revision
from core.cycle import enrich_cycle

router = APIRouter(tags=["users"])

# ==================== CLIENT PROFILE ====================

@router.post("/clients/profile", response_model=ClientProfile)
async def create_client_profile(data: ClientProfileCreate, user = Depends(get_current_user)):
    """Alta de membresía. El self-service directo está deshabilitado: activarse un plan
    aquí creaba un perfil `activo` con un pago falso, saltándose Stripe por completo.

    El alta real es: iniciar el checkout de Stripe (POST /billing/checkout-session) y que
    el webhook active la suscripción al confirmarse el pago. El admin puede dar de alta
    manualmente (plan cortesía) desde el panel.
    """
    raise HTTPException(
        status_code=403,
        detail="El alta de plan se realiza mediante el checkout de pago. "
               "Inicia el proceso desde tu panel; el plan se activa al confirmarse el pago.",
    )

@router.get("/clients/profile", response_model=ClientProfile)
async def get_client_profile(user = Depends(get_current_user)):
    """Obtener perfil del cliente actual (con la semana del ciclo calculada)."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    return ClientProfile(**enrich_cycle(profile))

@router.patch("/clients/onboarding", response_model=ClientProfile)
async def update_onboarding(data: OnboardingUpdate, user = Depends(get_current_user)):
    """Guardar el progreso del onboarding guiado (paso actual y/o completado)."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    update = {}
    if data.step is not None:
        update["onboarding_step"] = data.step
    if data.completed is not None:
        update["onboarding_completed"] = data.completed
    if data.checklist_dismissed is not None:
        update["checklist_dismissed"] = data.checklist_dismissed
    if update:
        await db.client_profiles.update_one({"user_id": user["id"]}, {"$set": update})
    updated = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    return ClientProfile(**updated)

@router.put("/clients/profile", response_model=ClientProfile)
async def update_client_profile(data: ClientProfileUpdate, user = Depends(get_current_user)):
    """Actualizar perfil del cliente. Si peso/sexo/bf/objetivo cambian, recalcula macros."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}

    # El perfil del cliente NO es la via para fijar macros: para eso esta PUT /macros,
    # que ademas los versiona en macro_history. Aqui se ignoran (antes se guardaban tal
    # cual, con lo que un cliente podia saltarse a su coach).
    for campo in ("macros_training", "macros_rest", "macros_periworkout", "macros_source",
                  "plan", "price", "week", "status", "trainer_id"):
        update_data.pop(campo, None)

    # Auto-calculate macros if body data is provided and macros_source is not 'manual'
    body_fields = {"weight", "sex", "goal", "body_fat"}
    if body_fields & set(update_data.keys()):
        # Merge with existing profile data
        peso = update_data.get("weight") or profile.get("weight")
        sexo = update_data.get("sex") or profile.get("sex")
        bf = update_data.get("body_fat") or profile.get("body_fat")
        objetivo = update_data.get("goal") or profile.get("goal")

        if all([peso, sexo, bf, objetivo]):
            try:
                # Motor v2: si hay ajustes guardados (preguntas 5-8), recalcular con
                # ellos; la tabla pura pisaria los modificadores del quiz.
                ajustes_guardados = profile.get("ajustes_macros")
                if ajustes_guardados:
                    resultado = calcular_macros_v2(
                        float(peso), sexo, float(bf), objetivo,
                        farmacologia=bool(profile.get("farmacologia")),
                        **ajustes_to_kwargs(ajustes_guardados),
                    )
                    targets = {"macros": resultado["macros"],
                               "multiplicadores": multiplicadores_de(resultado)}
                else:
                    targets = calcular_targets(float(peso), sexo, float(bf), objetivo)
                profile_macros = targets_to_profile_macros(targets)
                # Only auto-set if macros haven't been manually overridden
                if profile.get("macros_source") != "manual":
                    update_data["macros_training"] = profile_macros["macros_training"]
                    update_data["macros_rest"] = profile_macros["macros_rest"]
                    update_data["macros_periworkout"] = profile_macros["macros_periworkout"]
                    update_data["macros_source"] = "auto"
                    update_data["macros_multiplicadores"] = targets["multiplicadores"]
            except (ValueError, KeyError):
                pass  # Si los datos no son válidos, no recalcular

    if update_data:
        await db.client_profiles.update_one({"user_id": user["id"]}, {"$set": update_data})
    
    updated = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    return ClientProfile(**updated)

# ==================== CUESTIONARIO INICIAL (ELM) ====================

def _age_from_birthdate(birthdate: Optional[str]) -> Optional[int]:
    """Edad en años a partir de 'YYYY-MM-DD'. None si no parsea."""
    if not birthdate:
        return None
    try:
        b = datetime.strptime(birthdate[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    today = datetime.now(timezone.utc).date()
    return today.year - b.year - ((today.month, today.day) < (b.month, b.day))

@router.post("/clients/questionnaire")
async def submit_questionnaire(data: QuestionnaireSubmit, user = Depends(get_current_user)):
    """Cuestionario inicial (Nivel 0). Guarda las respuestas en el perfil, marca
    questionnaire_completed y calcula los macros con el MOTOR v2 (tabla + ajustes
    de las preguntas 5-8). Devuelve {profile, resultado} para que el front muestre
    los 8 numeros y el desglose en la pantalla final."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado. Selecciona un plan primero.")
    if profile.get("questionnaire_completed"):
        raise HTTPException(status_code=409, detail="El cuestionario ya fue completado.")

    sexo = (data.sex or "hombre").strip().lower()
    if sexo not in ("hombre", "mujer"):
        sexo = "hombre"
    ajustes = data.ajustes.model_dump() if data.ajustes else None
    update = {
        "questionnaire_completed": True,
        "goal": data.goal,
        "weight": data.weight,
        "height": data.height,
        "body_fat": data.body_fat,
        "sex": sexo,
        "birthdate": data.birthdate,
        "age": _age_from_birthdate(data.birthdate),
        "training_experience": data.training_experience,
        "activity_level": data.activity_level,
        "biotype": data.biotype,
    }
    if ajustes:
        update["ajustes_macros"] = ajustes

    # Calcular y aplicar macros con el motor v2 (no pisar si el coach ya los fijó manualmente).
    resultado = None
    try:
        resultado = calcular_macros_v2(
            float(data.weight), sexo, float(data.body_fat), data.goal,
            farmacologia=bool(profile.get("farmacologia")),
            **ajustes_to_kwargs(ajustes),
        )
        targets = {"macros": resultado["macros"],
                   "multiplicadores": multiplicadores_de(resultado)}
        profile_macros = targets_to_profile_macros(targets)
        if profile.get("macros_source") != "manual":
            update["macros_training"] = profile_macros["macros_training"]
            update["macros_rest"] = profile_macros["macros_rest"]
            update["macros_periworkout"] = profile_macros["macros_periworkout"]
            update["macros_source"] = "auto"
            update["macros_multiplicadores"] = targets["multiplicadores"]
    except (ValueError, KeyError):
        pass  # datos fuera de tabla → guardar respuestas igual, sin macros

    # Actualizar nombre/teléfono del usuario si los aportó.
    user_update = {}
    if data.name:
        user_update["name"] = data.name
    if data.phone:
        user_update["phone"] = data.phone
    if user_update:
        await db.users.update_one({"id": user["id"]}, {"$set": user_update})

    await db.client_profiles.update_one({"user_id": user["id"]}, {"$set": update})

    # Versionar en macro_history (Calma todosLosMacros) los macros calculados por el quiz, igual
    # que hacen PUT /macros y el admin. Sin esto, el resolver por fecha (dietas, ajustar macros)
    # usaría entradas antiguas o el fallback e ignoraría los macros recién calculados → desajuste.
    client_id = profile.get("id") or str(uuid.uuid4())
    if not profile.get("id"):
        await db.client_profiles.update_one({"user_id": user["id"]}, {"$set": {"id": client_id}})
    if "macros_training" in update:
        training = update["macros_training"]
        rest = update["macros_rest"]
        peri = update.get("macros_periworkout")
        effective_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        await db.macro_history.insert_one({
            "id": str(uuid.uuid4()),
            "client_id": client_id,
            "user_id": user["id"],
            "previous_training": profile.get("macros_training"),
            "previous_rest": profile.get("macros_rest"),
            "new_training": training,
            "new_rest": rest,
            "training": training,
            "rest": rest,
            "peri": peri,
            "effective_date": effective_date,
            "note": "Cuestionario inicial",
            "changed_by": user.get("name", user.get("email", "cliente")),
            "client_weight": data.weight,
            "peso": data.weight,
            "porcentaje_graso": data.body_fat,
            "sexo": sexo,
            "objetivo": data.goal,
            # Motor v2: desglose explicable y ajustes que originaron estos macros.
            "motor": {"version": resultado["version_motor"], "desglose": resultado["desglose"],
                      "ajustes": ajustes} if resultado else None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    # GUARDAR SIEMPRE las respuestas desde el dia uno (calibracion futura), y
    # avisar al coach si la dieta reportada no cuadra con lo recomendado.
    await guardar_quiz_respuestas(
        user_id=user["id"],
        client_id=client_id,
        origen="quiz_inicial",
        respuestas=data.model_dump(),
        resultado=resultado,
        contexto={"peso": data.weight, "porcentaje_graso": data.body_fat,
                  "sexo": sexo, "objetivo": data.goal},
    )
    await registrar_revision({**profile, "id": client_id}, user, resultado)

    updated = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    return {"profile": ClientProfile(**updated).model_dump(), "resultado": resultado}


@router.get("/clients/mis-dias")
async def mis_dias_montados(user = Depends(get_current_user)):
    """Los últimos días que el cliente tiene montados en la calculadora (para elegir uno en P10)."""
    from core.lectura_dieta import dias_disponibles
    return {"dias": await dias_disponibles(user["id"])}


@router.post("/clients/leer-dieta")
async def leer_dieta(data: dict, user = Depends(get_current_user)):
    """
    P10 del doc: traduce a macros la dieta que trae el cliente, por cualquiera de las tres
    puertas (texto, un menú suyo o una foto). NO aplica nada: solo devuelve lo entendido para
    que él lo confirme. Sin su confirmación este dato no entra en el cálculo.
    """
    from core.lectura_dieta import leer_de_texto, leer_de_menu_guardado, leer_de_foto

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Cuerpo inválido")

    texto = (data.get("texto") or "").strip()
    fecha_menu = (data.get("fecha_menu") or "").strip()
    imagen = data.get("imagen")

    if fecha_menu:
        resultado = await leer_de_menu_guardado(fecha_menu, user["id"])
    elif imagen:
        resultado = await leer_de_foto(imagen, user["id"])
    elif texto:
        if len(texto) > 4000:
            raise HTTPException(status_code=400, detail="El texto es demasiado largo")
        resultado = await leer_de_texto(texto, user["id"])
    else:
        raise HTTPException(status_code=400, detail="Cuéntanos tu dieta, elige un día o sube una foto")

    if resultado.get("error"):
        raise HTTPException(status_code=422, detail=resultado["error"])
    if not resultado.get("alimentos"):
        raise HTTPException(status_code=422,
                            detail="No hemos reconocido ningún alimento. Prueba a escribirlo con cantidades.")
    return resultado


@router.put("/clients/ajuste-progreso")
async def guardar_progreso_ajuste(data: dict, user = Depends(get_current_user)):
    """
    Guarda el cuestionario de ajuste a medias, respuesta a respuesta.

    Sin esto, salirse a mitad significaba empezar de cero, y son nueve preguntas. Se guarda lo
    contestado y en que pantalla iba; al volver, sigue donde lo dejo.
    """
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Cuerpo inválido")
    respuestas = data.get("respuestas")
    if not isinstance(respuestas, dict):
        raise HTTPException(status_code=400, detail="Faltan las respuestas")
    paso = data.get("paso")
    progreso = {
        "respuestas": respuestas,
        "paso": int(paso) if isinstance(paso, (int, float)) else 0,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    r = await db.client_profiles.update_one(
        {"user_id": user["id"]}, {"$set": {"ajuste_macros_progreso": progreso}})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    return {"guardado": True, "paso": progreso["paso"]}


@router.post("/clients/ajustar-macros")
async def ajustar_macros(data: AjustesMacros, user = Depends(get_current_user)):
    """
    Cuestionario de AJUSTE (paso 2 del doc del 29-07): afina los macros provisionales del alta
    y devuelve los DEFINITIVOS.

    Va aparte del alta a proposito: el alta se rellena una vez y se cierra, mientras que esto se
    puede repetir (si cambia de trabajo, si empieza a jugar al padel, si cambia de dieta). Los
    cuatro datos de la tabla (peso, sexo, grasa, objetivo) se leen del perfil, que ya los tiene.
    """
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado. Selecciona un plan primero.")

    peso, sexo = profile.get("weight"), (profile.get("sex") or "hombre")
    bf, objetivo = profile.get("body_fat"), profile.get("goal")
    if not all([peso, bf is not None, objetivo]):
        raise HTTPException(status_code=400,
                            detail="Faltan tus datos de partida (peso, grasa y objetivo). Completa el alta primero.")

    ajustes = data.model_dump()
    # Terminado: el progreso a medias ya no hace falta.
    update = {"ajustes_macros": ajustes, "ajuste_macros_completado": True,
              "ajuste_macros_progreso": None}

    try:
        resultado = calcular_macros_v2(
            float(peso), sexo, float(bf), objetivo,
            farmacologia=bool(profile.get("farmacologia")),
            **ajustes_to_kwargs(ajustes),
        )
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"No se pueden calcular tus macros: {e}")

    targets = {"macros": resultado["macros"], "multiplicadores": multiplicadores_de(resultado)}
    profile_macros = targets_to_profile_macros(targets)

    # Seccion 6 del doc: el cuestionario es el mismo para todos, lo que cambia es que hace la app
    # con las respuestas. Con entrenador detras, los macros se CALCULAN pero no se aplican solos:
    # se le presentan como propuesta y esperan a que el coach los valide. Se calculan igual (y no
    # se le deja con los provisionales del alta) porque si no, el que mas paga seria el que peor lo
    # pasa: esperaria con peores numeros que el del plan basico.
    con_entrenador = tiene_entrenador_detras(profile.get("plan"))
    aplicado = False
    if not con_entrenador and profile.get("macros_source") != "manual":
        update["macros_training"] = profile_macros["macros_training"]
        update["macros_rest"] = profile_macros["macros_rest"]
        update["macros_periworkout"] = profile_macros["macros_periworkout"]
        update["macros_source"] = "auto"
        update["macros_multiplicadores"] = targets["multiplicadores"]
        aplicado = True

    client_id = profile.get("id") or str(uuid.uuid4())
    if not profile.get("id"):
        update["id"] = client_id
    await db.client_profiles.update_one({"user_id": user["id"]}, {"$set": update})

    # Igual que el alta: se versiona en macro_history para que el resolver por fecha coja estos
    # macros y no los del alta.
    if "macros_training" in update:
        await db.macro_history.insert_one({
            "id": str(uuid.uuid4()),
            "client_id": client_id,
            "user_id": user["id"],
            "previous_training": profile.get("macros_training"),
            "previous_rest": profile.get("macros_rest"),
            "new_training": update["macros_training"],
            "new_rest": update["macros_rest"],
            "training": update["macros_training"],
            "rest": update["macros_rest"],
            "peri": update.get("macros_periworkout"),
            "effective_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "note": "Cuestionario de ajuste de macros",
            "changed_by": user.get("name", user.get("email", "cliente")),
            "client_weight": peso,
            "peso": peso,
            "porcentaje_graso": bf,
            "sexo": sexo,
            "objetivo": objetivo,
            "motor": {"version": resultado["version_motor"], "desglose": resultado["desglose"],
                      "ajustes": ajustes},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    await guardar_quiz_respuestas(
        user_id=user["id"], client_id=client_id, origen="ajuste_macros",
        respuestas=ajustes, resultado=resultado,
        contexto={"peso": peso, "porcentaje_graso": bf, "sexo": sexo, "objetivo": objetivo},
    )
    await registrar_revision({**profile, "id": client_id}, user, resultado)

    # Con entrenador: la propuesta queda pendiente para el coach, con todo lo que necesita para
    # decidir (los macros propuestos, las respuestas del cliente y el desglose del porque).
    entrega = {"aplicado": aplicado, "con_entrenador": con_entrenador, "coach": None}
    if con_entrenador:
        propuesta_id = str(uuid.uuid4())
        await db.macro_sugerencias.insert_one({
            "id": propuesta_id,
            "client_id": client_id,
            "user_id": user["id"],
            "origen": "cuestionario_cliente",
            "estado": "pendiente",
            "propuesta": profile_macros,
            "multiplicadores": targets["multiplicadores"],
            "respuestas": ajustes,
            "desglose": resultado["desglose"],
            "actuales": {
                "macros_training": profile.get("macros_training"),
                "macros_rest": profile.get("macros_rest"),
                "macros_periworkout": profile.get("macros_periworkout"),
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        entrega["propuesta_id"] = propuesta_id

        coach = None
        if profile.get("trainer_id"):
            coach = await db.users.find_one({"id": profile["trainer_id"]}, {"_id": 0, "name": 1})
        entrega["coach"] = (coach or {}).get("name")
        # Aviso al coach por la campanita, con lo justo para que sepa que hacer.
        if profile.get("trainer_id"):
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": profile["trainer_id"],
                "type": "macros_propuestos",
                "title": "Macros propuestos por el cuestionario",
                "message": f"{profile.get('name') or 'Un cliente'} ha rellenado el formulario. "
                           f"Revisa la propuesta antes de aplicarla.",
                "client_id": client_id,
                "read": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

    updated = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    return {"profile": ClientProfile(**updated).model_dump(), "resultado": resultado,
            "entrega": entrega}


@router.post("/clients/questionnaire/nivel1", response_model=ClientProfile)
async def submit_questionnaire_nivel1(data: Nivel1Submit, user = Depends(get_current_user)):
    """Cuestionario Nivel 1 (solo planes con coach). Alimenta el perfil largo
    (biotipo, pesos historicos, salud, entreno, alimentos...) y el caso gemelo.
    NO toca los macros: eso es exclusivo del Nivel 0 y del motor."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    nivel1 = {k: v for k, v in data.model_dump().items() if v is not None}
    update = {
        "nivel1": nivel1,
        "questionnaire_nivel1_completed": True,
    }
    # Espejo de los campos que ya existian en el perfil plano (los usan la ficha
    # del coach, el caso gemelo y el chatbot).
    if data.height is not None:
        update["height"] = data.height
    if data.biotype:
        update["biotype"] = data.biotype
    if data.birthdate:
        update["birthdate"] = data.birthdate
        update["age"] = _age_from_birthdate(data.birthdate)
    if data.training_experience:
        update["training_experience"] = data.training_experience
    if data.num_comidas is not None:
        update["diet_num_comidas"] = data.num_comidas

    client_id = profile.get("id") or str(uuid.uuid4())
    if not profile.get("id"):
        update["id"] = client_id

    await db.client_profiles.update_one({"user_id": user["id"]}, {"$set": update})

    await guardar_quiz_respuestas(
        user_id=user["id"],
        client_id=client_id,
        origen="nivel1",
        respuestas=nivel1,
    )

    updated = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    return ClientProfile(**updated)

# ==================== USER PREFERENCES ====================

@router.get("/user/preferences")
async def get_user_preferences(user = Depends(get_current_user)):
    """Obtener preferencias de alimentos del usuario."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        return {"food_preferences": [], "avoided_categories": [], "avoided_keywords": [], "has_preferences": False}

    preferences = profile.get("food_preferences", [])
    return {
        "food_preferences": preferences,
        "avoided_categories": profile.get("avoided_categories", []),
        "avoided_keywords": profile.get("avoided_keywords", []),
        "has_preferences": len(preferences) > 0
    }

@router.post("/user/preferences")
async def save_user_preferences(data: dict, user = Depends(get_current_user)):
    """Guardar preferencias y alimentos a evitar del usuario."""
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Cuerpo inválido")
    preferences = data.get("food_preferences", [])
    avoided_categories = data.get("avoided_categories", [])
    avoided_keywords = data.get("avoided_keywords", [])

    if not all(isinstance(x, list) for x in (preferences, avoided_categories, avoided_keywords)):
        raise HTTPException(status_code=400, detail="Las preferencias deben ser listas.")
    if len(preferences) < 3:
        raise HTTPException(status_code=400, detail="Debes seleccionar al menos 3 categorías")

    await db.client_profiles.update_one(
        {"user_id": user["id"]},
        {"$set": {
            "food_preferences": preferences,
            "avoided_categories": avoided_categories,
            "avoided_keywords": avoided_keywords,
        }, "$setOnInsert": {"id": str(uuid.uuid4())}},
        upsert=True
    )

    return {"success": True, "food_preferences": preferences, "avoided_categories": avoided_categories, "avoided_keywords": avoided_keywords}

# ==================== DIET CONFIG ====================

@router.get("/user/diet-config")
async def get_diet_config(user = Depends(get_current_user)):
    """Obtener configuración de dieta persistida (momento entreno, num comidas, opcion peri)."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    defaults = {"momento_entreno": 1, "num_comidas": 4, "opcion_peri": "intra_post"}
    if not profile:
        return defaults
    # num_comidas: la elección del cliente manda; si no eligió, deriva del ajuste del
    # coach (single_meal_mode -> 1 comida), si no, 4.
    num_comidas = profile.get("diet_num_comidas")
    if num_comidas is None:
        num_comidas = 1 if profile.get("single_meal_mode") else 4
    return {
        "momento_entreno": profile.get("diet_momento_entreno", 1),
        "num_comidas": num_comidas,
        "opcion_peri": profile.get("diet_opcion_peri", "intra_post"),
    }

@router.patch("/user/diet-config")
async def save_diet_config(data: dict, user = Depends(get_current_user)):
    """Guardar configuración de dieta para el usuario (persiste entre dispositivos)."""
    allowed = {"momento_entreno", "num_comidas", "opcion_peri"}
    update = {}
    if "momento_entreno" in data and isinstance(data["momento_entreno"], int):
        update["diet_momento_entreno"] = data["momento_entreno"]
    if "num_comidas" in data and isinstance(data["num_comidas"], int):
        update["diet_num_comidas"] = data["num_comidas"]
    if "opcion_peri" in data and isinstance(data["opcion_peri"], str):
        update["diet_opcion_peri"] = data["opcion_peri"]
    if update:
        await db.client_profiles.update_one(
            {"user_id": user["id"]},
            {"$set": update},
            upsert=False
        )
    return {"ok": True}

# ==================== MACROS ====================

@router.get("/macros")
async def get_macros(fecha: Optional[str] = None, user = Depends(get_current_user)):
    """Obtener macros del usuario. Si se pasa `fecha` (YYYY-MM-DD), devuelve la versión de
    macros VIGENTE a esa fecha (date-versioned, Calma todosLosMacros): la última entrada de
    macro_history con effective_date <= fecha; antes del primer cambio, la más antigua; sin
    historial, los macros actuales del perfil. Así el editor precarga los del día elegido."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        return {
            "training": {"protein": 160, "carbs": 50, "fat": 40},
            "rest": {"protein": 140, "carbs": 40, "fat": 40},
            "periworkout": {"protein": 35, "carbs": 15},
            "source": "default"
        }
    if fecha:
        # Reusa el mismo resolver que las dietas, para no divergir.
        from routes.calculator import _resolve_macros_for_date, _choose_macro_entry_for_date
        training, rest, peri = await _resolve_macros_for_date(profile, fecha)
        entry = await _choose_macro_entry_for_date(profile, fecha)
        # Inputs de la entrada vigente; si la entrada es legacy (sin inputs) cae al perfil.
        inputs = {
            "peso": (entry or {}).get("peso") if entry else None,
            "porcentaje_graso": (entry or {}).get("porcentaje_graso") if entry else None,
            "sexo": (entry or {}).get("sexo") if entry else None,
            "objetivo": (entry or {}).get("objetivo") if entry else None,
        }
        if inputs["peso"] is None: inputs["peso"] = profile.get("weight")
        if inputs["porcentaje_graso"] is None: inputs["porcentaje_graso"] = profile.get("body_fat")
        if inputs["sexo"] is None: inputs["sexo"] = profile.get("sex")
        if inputs["objetivo"] is None: inputs["objetivo"] = profile.get("goal")
        return {
            "training": training or {"protein": 160, "carbs": 50, "fat": 40},
            "rest": rest or {"protein": 140, "carbs": 40, "fat": 40},
            "periworkout": peri or {"protein": 35, "carbs": 15},
            "source": profile.get("macros_source", "default"),
            "fecha": fecha,
            **inputs,
        }
    return {
        "training": profile.get("macros_training") or {"protein": 160, "carbs": 50, "fat": 40},
        "rest": profile.get("macros_rest") or {"protein": 140, "carbs": 40, "fat": 40},
        "periworkout": profile.get("macros_periworkout") or {"protein": 35, "carbs": 15},
        "source": profile.get("macros_source", "default"),
        "peso": profile.get("weight"),
        "porcentaje_graso": profile.get("body_fat"),
        "sexo": profile.get("sex"),
        "objetivo": profile.get("goal"),
    }

@router.put("/macros", response_model=Dict[str, Any])
async def update_macros(data: MacrosUpdate, user = Depends(get_current_user)):
    """Actualizar macros del usuario (override manual, versionado por fecha).

    El cliente ajusta sus propios macros igual que el admin: además de guardarlos en el
    perfil, se registra una entrada en `macro_history` con `effective_date` para que las
    dietas resuelvan la versión vigente a cada fecha (Calma todosLosMacros). Antes esto
    escribía en `macro_logs` sin fecha ni peri, así que los cambios del cliente no se
    versionaban ni los veía el resolver de dietas.
    """
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    training = data.training.model_dump()
    rest = data.rest.model_dump()
    training["calories"] = training["protein"] * 4 + training["carbs"] * 4 + training["fat"] * 9
    rest["calories"] = rest["protein"] * 4 + rest["carbs"] * 4 + rest["fat"] * 9
    # Formato alternativo (proteinas/hidratos/grasas) para el chatbot y el motor de dietas.
    training["proteinas"] = training["protein"]
    training["hidratos"] = training["carbs"]
    training["grasas"] = training["fat"]
    rest["proteinas"] = rest["protein"]
    rest["hidratos"] = rest["carbs"]
    rest["grasas"] = rest["fat"]

    update = {
        "macros_training": training,
        "macros_rest": rest,
        "macros_source": "manual",
    }

    peri = None
    if data.peri is not None:
        peri = data.peri.model_dump()
        peri["calories"] = peri["protein"] * 4 + peri["carbs"] * 4
        peri["proteinas"] = peri["protein"]
        peri["hidratos"] = peri["carbs"]
        update["macros_periworkout"] = peri

    # Calc inputs → también al perfil (peso/%graso/sexo/objetivo) para que la calculadora
    # precargue los últimos valores y haya trazabilidad del estado actual.
    if data.peso is not None:
        update["weight"] = data.peso
    if data.porcentaje_graso is not None:
        update["body_fat"] = data.porcentaje_graso
    if data.sexo:
        update["sex"] = data.sexo
    if data.objetivo:
        update["goal"] = data.objetivo

    # Motor v2: ultima version de las preguntas 5-8 al perfil (precarga de la
    # pantalla y recalculos futuros). La revision se recalcula en SERVIDOR (no
    # nos fiamos del desglose que mande el front).
    ajustes = data.ajustes.model_dump() if data.ajustes is not None else None
    resultado_v2 = None
    if ajustes is not None:
        update["ajustes_macros"] = ajustes
        peso_v2 = data.peso if data.peso is not None else profile.get("weight")
        bf_v2 = data.porcentaje_graso if data.porcentaje_graso is not None else profile.get("body_fat")
        sexo_v2 = data.sexo or profile.get("sex")
        obj_v2 = data.objetivo or profile.get("goal")
        if all([peso_v2, sexo_v2, bf_v2, obj_v2]):
            try:
                resultado_v2 = calcular_macros_v2(
                    float(peso_v2), sexo_v2, float(bf_v2), obj_v2,
                    farmacologia=bool(profile.get("farmacologia")),
                    **ajustes_to_kwargs(ajustes),
                )
            except (ValueError, KeyError):
                pass

    # El versionado por fecha (macro_history) se indexa por profile.id. Algunos perfiles antiguos
    # no tienen el campo `id`; lo generamos y persistimos para que el resolver de dietas funcione.
    client_id = profile.get("id") or str(uuid.uuid4())
    if not profile.get("id"):
        update["id"] = client_id

    await db.client_profiles.update_one({"user_id": user["id"]}, {"$set": update})

    # Macros versionados por fecha (Calma todosLosMacros): la entrada registra la fecha DESDE la
    # que aplican. Por defecto = hoy. El resolver (_resolve_macros_for_date) elige la última
    # entrada con effective_date <= fecha de la dieta, así las dietas pasadas mantienen su versión.
    effective_date = data.effective_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    macro_log = {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "user_id": user["id"],
        "previous_training": profile.get("macros_training"),
        "previous_rest": profile.get("macros_rest"),
        "new_training": training,
        "new_rest": rest,
        "training": training,
        "rest": rest,
        "peri": peri,
        "effective_date": effective_date,
        "note": data.note,
        "changed_by": user.get("name", user.get("email", "cliente")),
        "client_weight": data.peso if data.peso is not None else profile.get("weight"),
        # Calc inputs guardados POR cambio → trazabilidad de cómo se derivaron los macros.
        "peso": data.peso,
        "porcentaje_graso": data.porcentaje_graso,
        "sexo": data.sexo,
        "objetivo": data.objetivo,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if ajustes is not None:
        macro_log["motor"] = {
            "version": 2,
            "ajustes": ajustes,
            # El desglose del front es informativo; el recalculado manda.
            "desglose": (resultado_v2 or {}).get("desglose") or data.desglose,
        }
    await db.macro_history.insert_one(macro_log)

    revision_registrada = False
    if ajustes is not None:
        await guardar_quiz_respuestas(
            user_id=user["id"],
            client_id=client_id,
            origen="ajustar_macros_guardar",
            respuestas=ajustes,
            resultado=resultado_v2,
            contexto={"peso": data.peso, "porcentaje_graso": data.porcentaje_graso,
                      "sexo": data.sexo, "objetivo": data.objetivo},
        )
        revision_registrada = await registrar_revision({**profile, "id": client_id}, user, resultado_v2)

    return {
        "success": True,
        "training": training,
        "rest": rest,
        "peri": peri,
        "effective_date": effective_date,
        "revision_avisada": revision_registrada,
    }


# ==================== FAVORITE FOODS ====================

@router.get("/favorites")
async def get_favorites(user = Depends(get_current_user)):
    """Get user's favorite food IDs."""
    doc = await db.food_favorites.find_one({"user_id": user["id"]}, {"_id": 0})
    return {"favorites": doc.get("food_ids", []) if doc else []}


@router.post("/favorites/{food_id}")
async def add_favorite(food_id: int, user = Depends(get_current_user)):
    """Add a food to favorites."""
    await db.food_favorites.update_one(
        {"user_id": user["id"]},
        {"$addToSet": {"food_ids": food_id}},
        upsert=True
    )
    doc = await db.food_favorites.find_one({"user_id": user["id"]}, {"_id": 0})
    return {"favorites": doc.get("food_ids", [])}


@router.delete("/favorites/{food_id}")
async def remove_favorite(food_id: int, user = Depends(get_current_user)):
    """Remove a food from favorites."""
    await db.food_favorites.update_one(
        {"user_id": user["id"]},
        {"$pull": {"food_ids": food_id}}
    )
    doc = await db.food_favorites.find_one({"user_id": user["id"]}, {"_id": 0})
    return {"favorites": doc.get("food_ids", []) if doc else []}
