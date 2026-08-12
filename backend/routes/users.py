"""
Rutas de usuarios: perfiles, preferencias y macros.
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import logging
import uuid

logger = logging.getLogger(__name__)

from core.database import db
from core.security import get_current_user
from models.user import (
    ClientProfile, ClientProfileCreate, ClientProfileUpdate,
    MacrosUpdate, PLAN_TYPES, PLAN_CATALOG, QuestionnaireSubmit, OnboardingUpdate,
    Nivel1Submit, AjustesMacros
)
from target_calculator import calcular_targets, targets_to_profile_macros
from macro_engine import calcular_macros_v2, ajustes_to_kwargs, multiplicadores_de
from core.plan_access import tiene_entrenador_detras, dias_hasta_la_revision
from core.quiz_store import guardar_quiz_respuestas, registrar_revision
from core.avisos_equipo import avisar_al_equipo
from core.cycle import enrich_cycle
from core.seguimiento import marcar_ajuste, fecha_de_vigencia
from core.series_cliente import anotar_peso, anotar_grasa
from core.cambios_macros import marcar_cambios
from core.historial_macros import guardar as guardar_en_historial

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
    # Si tiene acceso y, si no, por que (punto 41): el front necesita distinguir al que
    # nunca contrato del que se le acabo, porque no se les puede decir lo mismo.
    from core.plan_access import estado_de_acceso
    from core.series_cliente import grasa_vigente
    datos = enrich_cycle(profile)
    datos["acceso"] = estado_de_acceso(profile)
    # Su % graso vigente y si toca volver a pedirlo (punto 47). Lo decide el servidor para
    # que las pantallas no tengan cada una su version de "cuanto hace de esto".
    datos["grasa"] = grasa_vigente(profile)
    # ¿Hay alguien detras de sus macros? (punto 4.1). De esto depende que Inicio le diga o no
    # que le falta terminar de ajustarlos, y en produccion se lo estaba diciendo a 169 de los
    # 174 activos -- gente que lleva meses con Jesus y a la que el mismo les pone los numeros.
    from core.macros_de_quien import de_una_persona
    # Por `effective_date`, no por `created_at`: ver `macros_por_fecha.ultima_vigente`.
    from macros_por_fecha import ultima_vigente
    ultimo = await ultima_vigente(db, profile.get("id"))
    datos["macros_puestos_por_alguien"] = de_una_persona(ultimo)
    # Y si PUEDE ajustarselos el (punto 4.10). Lo decide el servidor y viaja al front para que
    # la pantalla no le enseñe un formulario y un boton de Guardar que van a devolver un 403:
    # dejarle contestar quince preguntas para negarselo al final es peor que decirselo antes.
    from core.quien_pone_los_macros import puede_ajustarlos
    puede, por_que_no = await puede_ajustarlos(db, profile)
    datos["macros_ajustables"] = {"puede": puede, "por_que_no": por_que_no}
    # QUIÉN es su entrenador, con nombre (punto 4.16). El chat decía «Tu Entrenador» en
    # abstracto porque el cliente no tenía forma de saber su nombre: el listado del equipo es
    # solo para admins. Sin esto, la conversación con la persona que te lleva se parece a un
    # formulario de soporte.
    if profile.get("trainer_id"):
        t = await db.users.find_one({"id": profile["trainer_id"]}, {"_id": 0, "id": 1, "name": 1})
        if t:
            datos["entrenador"] = {"id": t.get("id"), "nombre": t.get("name")}
    # LO QUE PAGA, de verdad (punto 2.4c). `price` viene a cero en los 168 perfiles migrados
    # de Calma, y Mi perfil enseñaba «0 €/ciclo» a un cliente de pago. El precio del plan
    # tapa ese hueco; el cero solo se respeta si hay cortesía marcada.
    from models.user import merged_catalog, precio_de_ciclo
    from routes.plans import _overrides_by_code
    datos["precio_ciclo"] = precio_de_ciclo(profile, merged_catalog(await _overrides_by_code()))
    datos["precio_cortesia"] = bool(profile.get("comp_plan"))
    # CUÁNDO SE LE ACABA (punto 2.4d). «Próxima renovación: no definida» a alguien cuya
    # membresía venció hace una semana no es que falte el dato: es que se miraba solo
    # `next_payment`, que es el próximo COBRO, y los migrados no tienen ninguno. Lo que se
    # sabe de cuándo termina lo pagado está en `current_period_end` (Stripe) o en
    # `fin_de_ciclo` (calendario de arranque), y si esa fecha ya pasó hay que decirlo.
    _fin = str(profile.get("current_period_end") or profile.get("fin_de_ciclo") or "")[:10] or None
    datos["renovacion"] = {
        "fecha": _fin,
        "proximo_cobro": profile.get("next_payment"),
        "vencida": bool(_fin and _fin < datetime.now(timezone.utc).date().isoformat()),
    }
    return ClientProfile(**datos)

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
    # `farmacologia` mueve la proteina de descanso: la fija el coach desde la ficha del
    # cliente, nunca el propio cliente desde su perfil.
    for campo in ("macros_training", "macros_rest", "macros_periworkout", "macros_source",
                  "plan", "price", "week", "status", "trainer_id", "farmacologia"):
        update_data.pop(campo, None)

    # Auto-calculate macros if body data is provided and macros_source is not 'manual'
    #
    # PERO NO SI SUS MACROS LOS LLEVA SU ENTRENADOR (punto 4.10, segunda vuelta). Este es un
    # camino de rebote: el cliente viene a apuntar su peso nuevo y de paso se le recalculaban
    # los macros por encima de los que le habia puesto una persona. `macros_source != "manual"`
    # no bastaba de cerrojo, porque la calculadora del panel del coach deja "auto".
    #
    # No se devuelve 403: guardar su peso es legitimo y es a lo que venia. Lo unico que no
    # pasa es el recalculo.
    from core.quien_pone_los_macros import puede_ajustarlos
    puede_recalcular, _ = await puede_ajustarlos(db, profile)

    body_fields = {"weight", "sex", "goal", "body_fat"}
    if puede_recalcular and (body_fields & set(update_data.keys())):
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

    # Peso y % graso NO se escriben sueltos: van a sus series con la fecha de hoy y el
    # "actual" sale de la serie (punto 30). Si no, el cliente editando su perfil dejaba un
    # peso sin fecha que discrepaba del de su ultimo reporte.
    peso_nuevo = update_data.pop("weight", None)
    grasa_nueva = update_data.pop("body_fat", None)

    if update_data:
        await db.client_profiles.update_one({"user_id": user["id"]}, {"$set": update_data})
    if peso_nuevo is not None:
        await anotar_peso(profile["id"], peso_nuevo, origen="lo puso el cliente")
    if grasa_nueva is not None:
        await anotar_grasa(profile["id"], grasa_nueva, origen="lo puso el cliente")

    # ESTE CAMINO NO DEJABA RASTRO (punto 62 del doc del 07-08). El cliente cambia su peso
    # o su objetivo desde su perfil, los macros se recalculan solos aqui arriba... y no se
    # escribia NADA en el historial. Consecuencias:
    #
    #   - el perfil decia unos macros y el historial otros, y el resolver por fecha
    #     (_resolve_macros_for_date) segia dando los viejos a las dietas nuevas;
    #   - y sobre todo: ese historial con el criterio es lo que va a entrenar al modelo.
    #     Un ajuste sin rastro es un dato perdido para siempre.
    #
    # Se marca `origen` para que el agente no lo confunda con una decision del coach: esto
    # lo movio el propio cliente editando su ficha.
    if "macros_training" in update_data:
        ahora = datetime.now(timezone.utc)
        macro_log = {
            "id": str(uuid.uuid4()),
            "client_id": profile["id"],
            "user_id": user["id"],
            "previous_training": profile.get("macros_training"),
            "previous_rest": profile.get("macros_rest"),
            "new_training": update_data["macros_training"],
            "new_rest": update_data.get("macros_rest"),
            "training": update_data["macros_training"],
            "rest": update_data.get("macros_rest"),
            "peri": update_data.get("macros_periworkout"),
            "effective_date": ahora.strftime("%Y-%m-%d"),
            "note": "Recalculados al editar su perfil",
            "origen": "cliente_perfil",
            "changed_by": user.get("name", user.get("email", "cliente")),
            "peso": peso_nuevo if peso_nuevo is not None else profile.get("weight"),
            "client_weight": peso_nuevo if peso_nuevo is not None else profile.get("weight"),
            "body_fat": grasa_nueva if grasa_nueva is not None else profile.get("body_fat"),
            "cambios": marcar_cambios(
                {"entreno": profile.get("macros_training"),
                 "perientreno": profile.get("macros_periworkout"),
                 "descanso": profile.get("macros_rest")},
                {"entreno": update_data.get("macros_training"),
                 "perientreno": update_data.get("macros_periworkout"),
                 "descanso": update_data.get("macros_rest")},
            ),
            "created_at": ahora.isoformat(),
        }
        await guardar_en_historial(macro_log)
        await marcar_ajuste(profile["id"], fecha_de_vigencia(macro_log))

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
    # Sin `weight` ni `body_fat`: los pone `anotar_peso`/`anotar_grasa` al final, a partir
    # de sus series (punto 30). El cálculo de macros de aquí abajo usa `data.weight`
    # directamente, así que no depende de esto.
    update = {
        "questionnaire_completed": True,
        "goal": data.goal,
        "height": data.height,
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
    #
    # Camino de rebote del punto 4.10: los 160 que vinieron de Calma nunca pasaron por este
    # cuestionario y ya tienen macros puestos por Jesús, así que el día que lo rellenen no se
    # les puede recalcular por encima. Se guardan sus respuestas -- que valen para el perfil y
    # para el agente -- y los macros se quedan como estaban.
    from core.quien_pone_los_macros import puede_ajustarlos
    puede_recalcular, _ = await puede_ajustarlos(db, profile)

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
        if puede_recalcular and profile.get("macros_source") != "manual":
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
        await guardar_en_historial({
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
            # De que camino salio (peticion de Jesus 05-08): esto NO es una decision del
            # coach, lo calculo el cuestionario. Sin marcarlo, en el historial parecia un
            # ajuste suyo y el agente lo aprendia como tal.
            "origen": "quiz_alta",
            # Que macro se movio (punto 31). En el alta suele salir None: no hay anterior.
            "cambios": marcar_cambios(
                {"entreno": profile.get("macros_training"),
                 "perientreno": profile.get("macros_periworkout"),
                 "descanso": profile.get("macros_rest")},
                {"entreno": training, "perientreno": peri, "descanso": rest},
            ),
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
        # "¿Quien me toca esta semana?" (punto 29): la fecha se queda en el cliente.
        await marcar_ajuste(client_id)

    # El primer punto de las dos series: el peso y el % graso del alta (punto 30). Se anotan
    # despues del $set para que el "actual" salga de la serie y no del campo suelto.
    await anotar_peso(client_id, data.weight, origen="cuestionario del alta")
    await anotar_grasa(client_id, data.body_fat, origen="cuestionario del alta")

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


@router.post("/clients/mi-cuerpo")
async def calcular_mi_cuerpo(data: dict, user = Depends(get_current_user)):
    """De qué está hecho hoy, a cambio de tres datos. GRATIS: no exige plan ni pago.

    Es el regalo del acceso gratis: se registra, da peso, altura y su % de grasa, y
    recibe algo suyo -- cuánto músculo lleva para su altura, cuántos kilos son de músculo
    y cuántos de grasa, y cuánto pesaría definido.

    El sexo y el objetivo NO se le vuelven a preguntar: vienen del test de nivel, y si no
    hizo el test se cogen de su ficha. Preguntar dos veces lo mismo es la forma más rápida
    de que alguien cierre la pestaña.

    Los tres datos se guardan en su ficha, que es lo que hace que esto no sea una
    calculadora suelta: al día siguiente siguen ahí.
    """
    from core.ficha_partida import composicion_de, peso_si_se_define, referencia_de_parecidos

    def _num(v, minimo, maximo):
        try:
            n = float(v)
        except (TypeError, ValueError):
            return None
        return n if minimo <= n <= maximo else None

    peso = _num(data.get("peso"), 30, 300)
    altura = _num(data.get("altura"), 120, 230)
    bf = _num(data.get("porcentaje_graso"), 3, 60)

    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    # EL % GRASO NO SE PIDE EN CADA AJUSTE (punto 47 del doc del 07-08): "se pide cada 12
    # semanas, no cada 2". Si tiene uno de hace menos, se reutiliza. Los ajustes son
    # quincenales, asi que antes se lo pediamos seis veces por ciclo -- y un dato que se
    # estima a ojo mirando fotos no cambia cada quince dias: preguntarlo tan seguido solo
    # consigue que lo repita sin mirarlo o que se lo invente.
    from core.series_cliente import grasa_vigente
    if bf is None:
        vigente = grasa_vigente(profile)
        if not vigente["hay_que_pedirlo"] and vigente["valor"] is not None:
            bf = float(vigente["valor"])
    if peso is None:
        raise HTTPException(status_code=400, detail="Necesitamos tu peso")
    if bf is None:
        raise HTTPException(
            status_code=400,
            detail="Necesitamos tu % de grasa: hace más de 12 semanas de la última vez.")

    sexo = (data.get("sexo") or profile.get("sex") or "hombre").lower()
    sexo = "mujer" if sexo.startswith("muj") or sexo in ("f", "femenino") else "hombre"
    objetivo = (data.get("objetivo") or profile.get("goal") or "definicion").lower()
    fase = "volumen" if "vol" in objetivo else "definicion"

    # Peso y % graso van a sus series al final (punto 30), no aqui sueltos.
    cambios = {"sex": sexo, "goal": fase}
    if altura:
        cambios["height"] = altura

    # Y con esos datos ya salen sus macros de tabla: los ocho números, sin modificar. No
    # es un extra -- sin macros no hay a qué cuadrar los menús, y el momento mágico
    # ("estas son comidas que puedes comer hoy") se quedaría vacío, que es justo la parte
    # que convence. La app queda usable desde aquí.
    #
    # Salvo que sus macros los lleve su entrenador (punto 4.10): esto es el regalo del acceso
    # gratis, pensado para quien llega sin nada. A un cliente de plan personalizado que ya
    # tiene macros puestos se le enseña su composición igual -- que es a lo que venía -- pero
    # no se le tocan los números.
    from core.quien_pone_los_macros import puede_ajustarlos
    puede_recalcular, _ = await puede_ajustarlos(db, profile)

    if puede_recalcular and profile.get("macros_source") != "manual":
        try:
            targets = calcular_targets(peso, sexo, bf, fase)
            m = targets_to_profile_macros(targets)
            cambios.update({
                "macros_training": m["macros_training"],
                "macros_rest": m["macros_rest"],
                "macros_periworkout": m["macros_periworkout"],
                "macros_source": "auto",
                "macros_multiplicadores": targets["multiplicadores"],
            })
        except (ValueError, KeyError):
            pass   # sin macros el regalo principal se enseña igual

    await db.client_profiles.update_one({"id": profile["id"]}, {"$set": cambios})

    composicion = composicion_de(peso, bf, altura or profile.get("height"), sexo)
    return {
        "composicion": composicion,
        "definido": peso_si_se_define(composicion["masa_magra"], sexo),
        "referencia": await referencia_de_parecidos(
            sexo, fase, peso, bf, excluir_client_id=profile.get("id")),
        "sexo": sexo,
        "fase": fase,
    }


@router.get("/clients/mi-ficha")
async def mi_ficha_de_partida(user = Depends(get_current_user)):
    """
    La ficha que se le entrega en el punto de partida (paso 3 del doc): de qué está hecho hoy,
    cuánto músculo lleva para su altura, y qué le pasó a la gente que empezó pareciéndose a él.
    """
    from core.ficha_partida import composicion_de, referencia_de_parecidos

    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    peso, bf = profile.get("weight"), profile.get("body_fat")
    if not peso or bf is None:
        raise HTTPException(status_code=400, detail="Faltan tu peso o tu % de grasa")

    sexo = (profile.get("sex") or "hombre").lower()
    sexo = "mujer" if sexo.startswith("muj") or sexo in ("f", "femenino") else "hombre"
    objetivo = (profile.get("goal") or "definicion").lower()
    fase = "volumen" if "vol" in objetivo else "definicion"
    altura = profile.get("height") or (profile.get("nivel1") or {}).get("height")

    composicion = composicion_de(float(peso), float(bf), altura, sexo)
    referencia = await referencia_de_parecidos(
        sexo, fase, float(peso), float(bf), excluir_client_id=profile.get("id"))

    fotos = await db.client_photos.count_documents({"client_id": profile.get("id")})
    return {
        "composicion": composicion,
        "referencia": referencia,
        "fase": fase,
        "fotos_subidas": fotos,
        "punto_de_partida_hecho": bool(profile.get("punto_de_partida_hecho")),
    }


@router.post("/clients/punto-de-partida")
async def guardar_punto_de_partida(data: dict, user = Depends(get_current_user)):
    """
    Guarda las medidas del día 1 y marca el punto de partida como hecho. Las fotos van por su
    propio endpoint (POST /reports/photos), que ya sabe tratarlas.
    """
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Cuerpo inválido")
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    medidas = data.get("medidas") if isinstance(data.get("medidas"), dict) else {}
    limpias = {}
    for k, v in medidas.items():
        try:
            n = float(v)
        except (TypeError, ValueError):
            continue
        if 0 < n < 300:            # cm de contorno: fuera de ahí es un error de tecleo
            limpias[str(k)[:30]] = round(n, 1)

    update = {"punto_de_partida_hecho": True}
    if limpias:
        update["medidas_inicio"] = {**limpias, "fecha": datetime.now(timezone.utc).strftime("%Y-%m-%d")}
    # La altura se pregunta aquí si aún no la tenemos: sin ella no hay índice de muscularidad.
    altura = data.get("altura")
    try:
        if altura and 120 <= float(altura) <= 230:
            update["height"] = float(altura)
    except (TypeError, ValueError):
        pass

    await db.client_profiles.update_one({"user_id": user["id"]}, {"$set": update})
    return {"guardado": True, "medidas": limpias}


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
    Cuestionario de AJUSTE (paso 2 del doc del 29-07): ajusta los macros provisionales del alta
    y devuelve los DEFINITIVOS.

    Va aparte del alta a proposito: el alta se rellena una vez y se cierra, mientras que esto se
    puede repetir (si cambia de trabajo, si empieza a jugar al padel, si cambia de dieta). Los
    cuatro datos de la tabla (peso, sexo, grasa, objetivo) se leen del perfil, que ya los tiene.
    """
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado. Selecciona un plan primero.")

    # Igual que el guardado manual (punto 4.10): en un plan personalizado esto vale para
    # sacar los macros de arranque, pero no para volver a calcularlos por encima de los que
    # ya le puso su entrenador.
    from core.quien_pone_los_macros import puede_ajustarlos
    puede, por_que_no = await puede_ajustarlos(db, profile)
    if not puede:
        raise HTTPException(status_code=403, detail=por_que_no)

    peso, sexo = profile.get("weight"), (profile.get("sex") or "hombre")
    bf, objetivo = profile.get("body_fat"), profile.get("goal")
    if not all([peso, bf is not None, objetivo]):
        raise HTTPException(status_code=400,
                            detail="Faltan tus datos de partida (peso, grasa y objetivo). Completa el alta primero.")

    ajustes = data.model_dump()

    # Sin las tres respuestas que mueven los hidratos no hay macros que dar (punto 12 del doc
    # del 07-08). Antes se podia llamar aqui con el cuestionario vacio: los cuatro datos de la
    # tabla salian del perfil, los modificadores viajaban a None y no movian nada, y el
    # resultado se guardaba igual marcado como completado. O sea, el cliente se quedaba con
    # unos macros calculados a medias creyendo que eran los suyos.
    ETIQUETAS = {"actividad_diaria": "tu actividad diaria",
                 "deporte_extra": "si practicas otro deporte",
                 "facilidad_engordar": "con que facilidad engordas"}
    faltan = [texto for clave, texto in ETIQUETAS.items() if ajustes.get(clave) is None]
    if faltan:
        raise HTTPException(
            status_code=400,
            detail=f"Antes de calcular tus macros falta que nos digas {', '.join(faltan)}.")

    # Terminado: el progreso a medias ya no hace falta.
    update = {"ajustes_macros": ajustes, "ajuste_macros_completado": True,
              "ajuste_macros_progreso": None}

    # El biotipo y la altura viajan con el ajuste desde el 06-08-2026 y viven en el perfil,
    # no dentro de `ajustes_macros`: los lee la ficha, el índice de muscularidad y la
    # búsqueda de casos parecidos, y ninguno de esos sabe de cuestionarios. No tocan macros.
    if data.biotype:
        update["biotype"] = data.biotype
    if data.height:
        update["height"] = float(data.height)

    try:
        resultado = calcular_macros_v2(
            float(peso), sexo, float(bf), objetivo,
            farmacologia=bool(profile.get("farmacologia")),
            **ajustes_to_kwargs(ajustes),
        )
    except (ValueError, KeyError) as e:
        # El detalle va al log, no al cliente: un KeyError se formatea como `'porcentaje_graso'`
        # -- el nombre de un campo nuestro entre comillas -- y eso acababa impreso en su
        # pantalla. Se le dice qué le falta a él, que es lo único que puede arreglar.
        logger.warning("No se pudieron calcular los macros de %s: %r", user.get("id"), e)
        raise HTTPException(
            status_code=400,
            detail="No hemos podido calcular tus macros. Revisa tu peso, tu sexo y tu porcentaje graso.",
        )

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
    # Peso y % graso, a sus series (punto 30). Van despues del $set porque hasta aqui el
    # perfil podia no tener `id`, que es por donde entra el modulo de series.
    await anotar_peso(client_id, peso, origen="cuestionario de ajuste")
    await anotar_grasa(client_id, bf, origen="cuestionario de ajuste")

    # Igual que el alta: se versiona en macro_history para que el resolver por fecha coja estos
    # macros y no los del alta.
    if "macros_training" in update:
        await guardar_en_historial({
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
            "origen": "quiz_ajuste",     # lo recalculo el cuestionario, no el coach
            # Que macro se movio (punto 31).
            "cambios": marcar_cambios(
                {"entreno": profile.get("macros_training"),
                 "perientreno": profile.get("macros_periworkout"),
                 "descanso": profile.get("macros_rest")},
                {"entreno": update["macros_training"],
                 "perientreno": update.get("macros_periworkout"),
                 "descanso": update["macros_rest"]},
            ),
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
        await marcar_ajuste(client_id)   # punto 29

    await guardar_quiz_respuestas(
        user_id=user["id"], client_id=client_id, origen="ajuste_macros",
        respuestas=ajustes, resultado=resultado,
        contexto={"peso": peso, "porcentaje_graso": bf, "sexo": sexo, "objetivo": objetivo},
    )
    await registrar_revision({**profile, "id": client_id}, user, resultado)

    # Con entrenador: la propuesta queda pendiente para el coach, con todo lo que necesita para
    # decidir (los macros propuestos, las respuestas del cliente y el desglose del porque).
    # La fecha de la proxima revision: en el plan que se autogestiona es la revision automatica;
    # en el plan con coach, cuando le toca repasarlos con el.
    proxima = datetime.now(timezone.utc) + timedelta(days=dias_hasta_la_revision(profile.get("plan")))
    MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    entrega = {
        "aplicado": aplicado,
        "con_entrenador": con_entrenador,
        "coach": None,
        "proxima_revision": f"{proxima.day} de {MESES[proxima.month - 1]}",
    }
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
        # Aviso por la campanita, con lo justo para que sepa que hacer. Si el cliente no
        # tiene entrenador asignado (que es lo normal: nada lo asigna al pagar), se avisa
        # a todo el staff. Antes el aviso colgaba de tener entrenador y no salia nunca.
        await avisar_al_equipo(
            db,
            tipo="macros_propuestos",
            titulo="Macros propuestos por el cuestionario",
            mensaje=f"{profile.get('name') or user.get('name') or 'Un cliente'} ha rellenado el "
                    f"formulario. Revisa la propuesta antes de aplicarla.",
            client_id=client_id,
            trainer_id=profile.get("trainer_id"),
        )

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

    # Este es el formulario que se le vende como "tu coach usará todo esto para tu
    # estrategia": si no avisa a nadie, esa frase es mentira. No avisaba a nadie, ni
    # siquiera con entrenador asignado.
    await avisar_al_equipo(
        db,
        tipo="perfil_completo",
        titulo="Perfil completo del cliente",
        mensaje=f"{profile.get('name') or user.get('name') or 'Un cliente'} ha rellenado el "
                f"cuestionario largo: historial, salud, entreno y alimentos. Ya puedes montarle "
                f"la estrategia.",
        client_id=client_id,
        trainer_id=profile.get("trainer_id"),
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

    # En NOMBRES, no en codigos (punto 4.18). Los clientes que vinieron de Calma tienen
    # guardados los codigos de categoria ('8', '2.3') y toda la app trabaja con nombres
    # ('panes', 'vacuno'), asi que sus preferencias no se marcaban en la pantalla ni filtraban
    # nada. Se traducen al leer: no hace falta reescribir la base para que empiecen a servir.
    from core.preferencias import a_nombres

    preferences = a_nombres(profile.get("food_preferences", []))
    return {
        "food_preferences": preferences,
        "avoided_categories": a_nombres(profile.get("avoided_categories", [])),
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

    # Este upsert puede CREAR el perfil: es lo primero que ofrece Nutrición y se puede
    # hacer antes de contratar plan. Al nacer aquí, el perfil se marca pendiente_pago
    # (no da acceso a nada) y lleva su created_at; antes salía sin fecha y el perfil
    # quedaba ilegible para el resto de la app.
    await db.client_profiles.update_one(
        {"user_id": user["id"]},
        {"$set": {
            "food_preferences": preferences,
            "avoided_categories": avoided_categories,
            "avoided_keywords": avoided_keywords,
        }, "$setOnInsert": {
            "id": str(uuid.uuid4()),
            "status": "pendiente_pago",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }},
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
    # SIN FECHA SIGNIFICA HOY, no "lo ultimo que se escribio" (punto 4.6).
    #
    # Aqui estaba la tercera version de los macros de un cliente. Sin `fecha` se devolvian
    # los campos sueltos del perfil (`macros_training`...), que son un espejo de la ultima
    # escritura y no saben de fechas de vigencia. Nutricion y Ajustar macros SI pasan fecha y
    # pasan por el resolver, asi que Inicio -- que llama sin ella -- podia enseñar unos macros
    # y las otras dos pantallas otros:
    #
    #     Inicio            170 P / 70 H / 50 G  |  peri 40/25
    #     Ajustar macros    120 P / 60 H / 50 G  |  peri 30/30
    #     Nutricion         120 P / 60 H / 50 G  |  peri 30/30
    #
    # Pasaba con un ajuste programado a futuro o con dos filas del mismo dia: el espejo se
    # queda con la ultima escrita y el resolver con la vigente, que es la buena.
    #
    # No se cambia la firma ni se toca ninguna pantalla: se le da a "sin fecha" el unico
    # significado que puede tener, que es hoy. Sin historial el resolver cae al perfil, asi
    # que para un cliente nuevo devuelve exactamente lo mismo que antes.
    fecha = fecha or datetime.now(timezone.utc).strftime("%Y-%m-%d")
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


# ==================== MIS MACROS (punto 6.2 de la revision del 09-08) ====================
#
# El historial de macros existe desde hace meses y solo lo veia el entrenador. Lo que pide el
# 6.2 es enseñarselo al cliente al que le pasan las cosas: sus numeros de hoy, lo que le dijo
# su entrenador en el ultimo ajuste, la escalera de los anteriores con lo que cambio marcado, y
# su peso. Todo eso ya esta guardado; lo unico que faltaba era una puerta para el.
#
# La puerta es nueva y no reutiliza la del admin a proposito: la entrada del historial lleva
# cosas que el cliente NO puede ver, y la unica forma de garantizarlo es construir la respuesta
# campo a campo en vez de tapar lo que sobra.

# Lo que nunca sale de aqui, y por que:
#
#   criterio        es la nota INTERNA del entrenador ("bajo hidratos, viene de una fase
#                   larga y no responde"). Se escribe sabiendo que no la lee el cliente.
#   evaluacion      como salio la fase, con la casilla de "de quien fue la culpa".
#   sugerencia_*    lo que propuso la IA y cuanto lo corrigio el coach.
#   correccion_coach, motor, origen, changed_by
#
# Por eso abajo se construye un diccionario nuevo con los campos elegidos: si algun dia se
# guarda un campo mas en `macro_history`, no se cuela solo en esta respuesta.

# Los origenes que escribe el PROPIO cliente. La nota de esas entradas es suya -- el «motivo
# del cambio» de su calculadora --, asi que no puede pintarse bajo «lo que te dijo tu
# entrenador»: seria devolverle sus propias palabras en boca de otro.
LOS_ESCRIBE_EL_CLIENTE = {"cliente_calculadora", "cliente_perfil", "quiz_alta",
                          "quiz_ajuste", "cuestionario_cliente"}

# Las notas que escribe la APP, no una persona: la etiqueta de la migracion y el nombre del
# camino por el que se calcularon esos macros. En el historial del entrenador se leen como lo
# que son, pero debajo de «lo que te dijo tu entrenador» se leerian como un mensaje suyo, y
# «Importado de Calma» no es nada que Jesus le haya dicho a nadie.
#
# Van por texto y no solo por `origen` porque el origen se empezo a guardar el 05-08: de las
# 3.400 entradas de desarrollo, 3.200 no lo tienen y si tienen una de estas notas. Filtrando
# solo por origen, a todo cliente migrado le saldria «Importado de Calma» entrecomillado como
# el consejo de su entrenador.
NOTAS_QUE_ESCRIBE_LA_APP = {
    "Importado de Calma",
    "Cuestionario inicial",
    "Cuestionario de ajuste de macros",
    "Recalculados al editar su perfil",
}


def _bloque_de_macros(m: Optional[Dict[str, Any]], con_grasa: bool = True) -> Optional[Dict[str, Any]]:
    """Un bloque de macros con los nombres de siempre. None si no hay nada que enseñar.

    En la base conviven los dos vocabularios (`protein`/`carbs`/`fat` y
    `proteinas`/`hidratos`/`grasas`) segun quien lo escribiera; aqui se sale por uno solo.
    """
    if not isinstance(m, dict):
        return None
    def _n(*nombres):
        for k in nombres:
            v = m.get(k)
            if v is not None:
                try:
                    return round(float(v))
                except (TypeError, ValueError):
                    return None
        return None
    fuera = {"proteina": _n("protein", "proteinas"), "hidratos": _n("carbs", "hidratos")}
    if con_grasa:
        fuera["grasa"] = _n("fat", "grasas")
    return fuera if any(v is not None for v in fuera.values()) else None


def _feedback_del_entrenador(h: Dict[str, Any]) -> Optional[str]:
    """La `note` del ajuste, solo si de verdad se la escribio su entrenador."""
    nota = (h.get("note") or "").strip()
    if not nota or nota in NOTAS_QUE_ESCRIBE_LA_APP:
        return None
    if (h.get("origen") or "") in LOS_ESCRIBE_EL_CLIENTE:
        return None
    return nota


@router.get("/macros/historial")
async def get_mi_historial_de_macros(user = Depends(get_current_user)):
    """Lo que se pinta en «Mis macros»: sus ajustes, su feedback y su peso (punto 6.2).

    QUIEN VE EL HISTORICO lo decide su plan, como manda la TABLA 20 del documento:

        calculadora: personalizado   sus macros los lleva una persona -> CON historico
        calculadora: sin_ajuste      no se le tocan                   -> SIN historico

    La diferencia no es cosmetica. En el plan personalizado el historico ES el producto: es la
    prueba de que alguien mira sus numeros cada quince dias y por que los movio. En el plan sin
    ajuste no hay ajustes que enseñar, y una tabla con una sola fila repetida solo consigue que
    parezca que le hemos dejado de hacer caso.
    """
    from core.plan_access import modo_calculadora
    from core.sin_futuro import hasta_hoy

    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    modo = modo_calculadora(profile.get("plan"))
    con_historico = modo == "personalizado"
    client_id = profile.get("id")

    # HASTA HOY, igual que el panel del entrenador (punto 22): hay ajustes programados con
    # fecha por delante, y al cliente le tiene que salir arriba el que le aplica HOY, no uno
    # que todavia no ha empezado. Su fecha de vigencia es lo que ordena, y el momento en que se
    # guardo desempata: dos ajustes del mismo dia van del mas nuevo al mas viejo.
    # UN AJUSTE POR FECHA, Y SIN CORTAR EN 60.
    #
    # Cortaba en 60 filas, y hay cuentas con 262: a esos clientes la pantalla les enseñaba
    # solo el ultimo trozo de su historia. Y como la tarjeta de renovacion cuenta los dias
    # con ajuste del ciclo entero, los dos numeros no cuadraban -- que es justo lo que pide
    # el caso 76 de Jesus: «el contador de ajustes coincide con el historico de Mis macros».
    # Medido: 13 en la tarjeta contra 6 en la pantalla.
    #
    # Se agrupa por fecha porque un ajuste ES un dia: guardar dos veces el mismo dia es una
    # correccion, no dos ajustes (misma regla que `core/historial_macros`, que ya deduplica
    # al escribir). Al cliente demo le salian 36 filas del 07-08. Manda la mas reciente de
    # ese dia, que es la que quedo vigente.
    entradas_crudas = []
    if client_id:
        todas = await db.macro_history.find(
            hasta_hoy({"client_id": client_id}, campo="effective_date"), {"_id": 0}
        ).sort([("effective_date", -1), ("created_at", -1)]).to_list(1000)
        vistas = set()
        for h in todas:
            dia = h.get("effective_date") or str(h.get("created_at") or "")[:10]
            if dia in vistas:
                continue
            vistas.add(dia)
            entradas_crudas.append(h)

    entradas = []
    for h in entradas_crudas:
        peri = h.get("peri") or h.get("macros_periworkout")
        entradas.append({
            "id": h.get("id"),
            "fecha": h.get("effective_date") or (h.get("created_at") or "")[:10],
            "peso": h.get("peso") if h.get("peso") is not None else h.get("client_weight"),
            "entreno": _bloque_de_macros(h.get("training") or h.get("new_training")),
            "peri": _bloque_de_macros(peri, con_grasa=False),
            "descanso": _bloque_de_macros(h.get("rest") or h.get("new_rest")),
            # Que macro se movio, calculado al guardar (punto 31). Es el mismo dato con el que
            # el entrenador lee la escalera en su panel, asi que los dos ven lo mismo marcado.
            "cambios": h.get("cambios"),
            "feedback": _feedback_del_entrenador(h),
        })

    # SU PESO, de la serie (punto 30), que es donde caen los pesajes vengan de donde vengan. Se
    # le suman los que viajaron con un ajuste y no llegaron a la serie -- los importados de
    # Calma son de 2022 en adelante --, porque si no la curva empieza el dia que estrenamos la
    # serie y se pierde justo el recorrido que le da sentido.
    # SANEADO, como el panel del entrenador (`_sanea_peso`). El de aqui era el unico camino
    # que pintaba el peso crudo, y en produccion los ajustes viejos traen 0,0 kg, un 0,433 (un
    # porcentaje de grasa metido donde va el peso) y errores de coma de tres cifras. El coach
    # veia la curva limpia y el cliente, en «Mis macros», veia la sucia. Jesus, 12-08.
    from core.series_cliente import sanea_peso
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pesos: Dict[str, float] = {}
    for p in (profile.get("pesos") or []):
        fecha, valor = str(p.get("fecha") or "")[:10], sanea_peso(p.get("valor"))
        if fecha and fecha <= hoy and valor is not None:
            pesos[fecha] = valor
    for e in entradas:
        limpio = sanea_peso(e["peso"])
        # Tambien en la FILA, no solo en la curva: la tabla enseña el peso de cada ajuste.
        e["peso"] = limpio
        if limpio is not None and e["fecha"] and e["fecha"] not in pesos:
            pesos[e["fecha"]] = limpio

    # «HOY · ENTRENO»: si tiene el dia montado en su calculadora, ya dijo si entrena o descansa,
    # y entonces la tarjeta puede decirle cual de los tres bloques le toca. Si no lo ha montado
    # no se supone nada: se le enseñan los tres sin destacar ninguno.
    dia_de_hoy = await db.diets.find_one({"user_id": user["id"], "fecha": hoy},
                                         {"_id": 0, "tipo_dia": 1})

    vigente = entradas[0] if entradas else None
    return {
        "con_historico": con_historico,
        "tipo_dia_hoy": (dia_de_hoy or {}).get("tipo_dia"),
        # La tabla solo va en los planes que la TABLA 20 dice. `vigente` y la curva de peso
        # salen siempre: son sus numeros de hoy y su peso, no el registro de ajustes.
        "entradas": entradas if con_historico else [],
        "vigente": vigente,
        "evolucion_peso": [{"fecha": f, "peso": p} for f, p in sorted(pesos.items())],
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

    # NO EN LOS PLANES CON ENTRENADOR (punto 4.10). El catalogo dice desde hace tiempo quien
    # ajusta los macros de cada plan y nadie lo miraba aqui: un cliente de plan personalizado
    # podia machacar lo que le hubiera puesto su entrenador sin que este se enterase.
    from core.quien_pone_los_macros import puede_ajustarlos
    puede, por_que_no = await puede_ajustarlos(db, profile)
    if not puede:
        raise HTTPException(status_code=403, detail=por_que_no)

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

    # Calc inputs → también al perfil (sexo/objetivo) para que la calculadora precargue los
    # últimos valores. El peso y el % graso van a sus series al final (punto 30): así el
    # "actual" es siempre el último de la serie y no un campo suelto que puede discrepar.
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
        "origen": "cliente_calculadora",   # lo movio el propio cliente desde su calculadora
        # Que macro se movio (punto 31).
        "cambios": marcar_cambios(
            {"entreno": profile.get("macros_training"),
             "perientreno": profile.get("macros_periworkout"),
             "descanso": profile.get("macros_rest")},
            {"entreno": training, "perientreno": peri, "descanso": rest},
        ),
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
    await guardar_en_historial(macro_log)
    await marcar_ajuste(client_id, fecha_de_vigencia(macro_log))   # punto 29
    # Peso y % graso, a sus series con la fecha de vigencia del ajuste (punto 30).
    if data.peso is not None:
        await anotar_peso(client_id, data.peso, macro_log.get("effective_date"),
                          origen="calculadora del cliente")
    if data.porcentaje_graso is not None:
        await anotar_grasa(client_id, data.porcentaje_graso, macro_log.get("effective_date"),
                           origen="calculadora del cliente")

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
