"""
Rutas del chatbot de nutrición.
"""
import re

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from datetime import datetime
from typing import Optional

from core.database import db
from core.security import get_admin_user, get_current_user
from models.diet import ChatConfigRequest, ChatMessageRequest

# Import chatbot functions
from chatbot import (get_or_create_chatbot, clear_session, save_chatbot_session,
                     session_exists, nombre_visible)
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

    # LA PRESENTACION DE MARCO, LITERAL Y UNA SOLA VEZ.
    #
    # Es texto de Jesus y va en codigo, no en el prompt: asi sale tal cual la primera vez y
    # no vuelve a salir nunca, sin depender de que el modelo se acuerde de no repetirla. El
    # chiste hace gracia una vez.
    #
    # Sin «¿empezamos por el desayuno?»: a las comidas se las llama por su numero (decision
    # del 09-08), y ademas quien ya tiene medio dia montado no empieza por la primera.
    return {
        "session_id": session_id,
        "macros": user_macros,
        "message": ("Hola, soy Marco. Y sí: Marco, por Macro. Ya está el chiste hecho, no "
                    "hace falta que lo hagas tú. Te ayudo a montar tu dieta del día, comida "
                    "por comida. ¿Hoy es día de entrenamiento o de descanso?")
    }


async def _dieta_para_precargar(dieta: dict) -> tuple:
    """Las comidas guardadas de un dia y el catalogo de sus alimentos, listos para el chat.

    Sin la ficha de cada alimento no hay con que contar: lo guardado casi nunca trae
    `macros_efectivos` (411 de 55.323 en produccion), asi que el asistente leia el dia entero
    a cero. Y de paso pasan por aqui las cantidades de las dietas migradas, que guardan el
    CONTEO de piezas en el campo de gramos ("1" por un huevo): leidas como gramos, un huevo
    cuenta 0,1 de proteina. Es la misma normalizacion que hace Nutricion al abrir el dia
    (`routes/diets.py`, punto 4.5 del 09-08).
    """
    comidas = (dieta or {}).get("comidas") or {}
    ids = {
        a.get("alimento_id") if a.get("alimento_id") is not None else a.get("id")
        for comida in comidas.values()
        for a in ((comida or {}).get("alimentos") or [])
    }
    ids.discard(None)
    if not ids:
        return comidas, {}

    catalogo = {f["id"]: f async for f in db.foods.find({"id": {"$in": list(ids)}}, {"_id": 0})}
    from routes.diets import _normalizar_con_catalogo
    _normalizar_con_catalogo({"comidas": comidas}, catalogo)
    return comidas, catalogo


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
        # CAMBIAR DE FECHA ESTRENA DÍA (QA 15-08, A3-01/A3-02). configure_day conserva y
        # traspasa lo montado a propósito -- reconfigurar EL MISMO día no debe perder
        # trabajo -- pero entre fechas esa conservación es un arrastre: la comida del 18
        # viajaba al 19 y el volcado la guardaba allí. Lo que tenga el día nuevo lo trae
        # `precargar_desde_dieta` unas líneas más abajo, así que aquí se limpia todo lo
        # que es DEL día viejo, borradores y acumulados incluidos.
        if chatbot.state.get("fecha_objetivo") and chatbot.state["fecha_objetivo"] != config.fecha:
            for clave in ("comidas_completadas", "borradores"):
                chatbot.state[clave] = {}
            for clave in ("saved_meals", "comidas_traidas", "last_options",
                          "comidas_retiradas"):
                chatbot.state[clave] = []
            for clave in ("acumulado_cereales_panes", "acumulado_frutos_secos"):
                chatbot.state[clave] = 0
            chatbot.state["guion_peri_dicho"] = []
            chatbot.state["opcion_seq"] = {}
            chatbot.state["sustitucion_pendiente"] = None
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

    # LO QUE YA TIENE MONTADO ESE DIA ENTRA EN LA CONVERSACION.
    #
    # Hasta ahora el asistente empezaba en blanco aunque la dieta estuviera hecha: con las
    # cuatro comidas puestas decia «llevas 0 g» y «0/4», y desde ahi te ofrecia montar lo que
    # ya tenias. Abrirlo a media tarde era arriesgarse a perder el trabajo de la manana.
    #
    # Va DESPUES de configure_day a proposito: esa llamada rehace el orden de comidas y
    # limpia el estado, asi que precargar antes seria tirarlo. Y va aqui y no en /start
    # porque hasta este momento no se sabe que dia se esta montando.
    fecha_dieta = chatbot.state.get("fecha_objetivo") or datetime.now().strftime("%Y-%m-%d")
    user_id = current_user.get("id") or current_user.get("user_id")
    dieta = await db.diets.find_one({"user_id": user_id, "fecha": fecha_dieta}, {"_id": 0, "comidas": 1})
    comidas_traidas = chatbot.precargar_desde_dieta(*(await _dieta_para_precargar(dieta)))

    key = chatbot.current_meal_key()
    label = chatbot.meal_label(key)
    objetivo = chatbot.get_current_meal_macros()

    total = chatbot.total_meals()
    base_n = chatbot.state["num_comidas"]
    n_peri = total - base_n
    extra = f" (más {n_peri} peri-entreno)" if n_peri > 0 else ""
    # «PERFECTO, DÍA DE ENTRENAMIENTO CON 4 COMIDAS» ES LA RESPUESTA A ALGO QUE NADIE
    # PREGUNTÓ (17-08-2026).
    #
    # El chat ya no se configura a mano: arranca solo con lo que el cliente tiene en
    # Nutrición, y el front lo cuenta en su saludo («Vamos con Hoy, con lo que tienes en
    # Nutrición: día de entreno, 4 comidas, entrenas en ayunas, intra + post»). Justo
    # detrás, esta ruta contestaba «Perfecto, día de entrenamiento con 4 comidas»: el mismo
    # dato dos veces y, peor, con la forma de un «perfecto» a una petición del cliente que
    # no existe. Francisco: «se autocontesta un mensaje fantasma, es confuso».
    #
    # Con `saludo=False` (lo que manda el front) la apertura empieza por lo único que el
    # cliente no sabe: por dónde va su día. Se deja el eco para quien llame a esta ruta sin
    # haber saludado antes.
    if not config.saludo:
        mensaje = ""
    elif chatbot.state.get("single_meal"):
        mensaje = f"Perfecto, día de {config.tipo_dia} en bloque único (1 comida){extra}."
    else:
        mensaje = f"Perfecto, día de {config.tipo_dia} con {base_n} comidas{extra}."

    # SI YA TIENE TRABAJO HECHO, LO PRIMERO ES DECIRSELO.
    # Arrancar con «vamos con la Comida 1» a quien ya tiene tres puestas es invitarle a
    # rehacerlas. Se dice por donde va y se sigue por la primera que le falta.
    if comidas_traidas:
        v = chatbot.get_day_overview()
        r = v["restante"]
        hechas = f"{comidas_traidas} de {total}" if total else str(comidas_traidas)
        mensaje += f"\n\nYa tienes {hechas} comidas montadas de ese día."
        # En palabras, no en iniciales: «Te faltan 13 P · 17 H · 1 G» es lo que Jesús
        # leyó en el vídeo 1 del 15-08, y no lo dice nadie.
        falta = [f"{_gr(abs(round(r[k])))} g de {_NOMBRE_MACRO[k]}"
                 for k in ("P", "H", "G") if round(r[k]) > 0]
        # LO QUE SOBRA TAMBIÉN SE DICE. Con 303 g de hidratos sobre un objetivo de 65, el
        # resumen era «te faltan 105 g de proteína y 7 g de grasa» y se callaba los 238 g
        # de hidratos de más, que es EL problema de ese día (QA del 15-08 en producción).
        # La proteína no entra: pasarse de proteína el método lo tolera.
        sobra = [f"{_gr(abs(round(r[k])))} g de {_NOMBRE_MACRO[k]}"
                 for k in ("H", "G") if round(r[k]) < 0]
        if falta:
            mensaje += f" Te faltan {_enumerar(falta)}."
        if sobra:
            mensaje += f" Y te pasas de {_enumerar(sobra)}."
        elif not falta:
            mensaje += " El día ya te cuadra."

    # UNA COMIDA LLENA NO SE PRESENTA COMO VACÍA. Se aterrizaba en la Comida 3 con 300 g
    # de arroz dentro y el mensaje era «Seguimos por Comida 3 ... ¿Qué quieres tomar?»,
    # como si no hubiera nada: el cliente añade encima de lo que ya tiene sin saberlo (QA
    # del 15-08 en producción). Si hay algo puesto, se dice qué hay y se ofrece tocarlo.
    ya_puesto = (chatbot.state["comidas_completadas"].get(key) or {}).get("alimentos", [])
    if ya_puesto:
        # Por `nombre_visible`, que quita los apuntes de ficha del catálogo: este mensaje de
        # apertura le recitaba al cliente «Arroz tres delicias ya cocinado - macros
        # orientativos». La limpieza estaba puesta en las tarjetas y en lo que lee el modelo,
        # y faltaba justo aquí, que es lo primero que se lee al abrir el chat (16-08-2026).
        nombres = _enumerar([nombre_visible(a.get("nombre", "")) for a in ya_puesto
                             if a.get("nombre")])
        mensaje += f"\n\nSeguimos por {label}, que ya tiene {nombres}."
        rc = chatbot.get_remaining_macros()
        pasa = [f"{_gr(abs(round(rc[k])))} g de {_NOMBRE_MACRO[k]}"
                for k in ("H", "G") if round(rc[k]) < 0]
        if pasa:
            mensaje += f" Ahí te pasas de {_enumerar(pasa)}."
    elif comidas_traidas:
        mensaje += f"\n\nSeguimos por {label}. Tu objetivo son {_frase_objetivo(objetivo)}."
    else:
        # «Empezamos», no «Vamos con»: el saludo del front ya abre con «Vamos con Hoy...» y
        # dos «vamos con» seguidos suenan a dos personas hablando.
        mensaje += (f"\n\nEmpezamos por {label}. Tu objetivo es:\n"
                    f"• Proteína: {_gr(objetivo['P'])} g\n"
                    f"• Hidratos: {_gr(objetivo['H'])} g\n"
                    f"• Grasa: {_gr(objetivo['G'])} g")
    # Si el cambio se ha llevado por delante alguna comida (el intra y el post al pasar a
    # descanso, la Comida 4 al bajar a 3), lo que había ahí se ha traspasado a otra: hay
    # que DECIRLO. Antes se borraba en silencio y el cliente perdía el trabajo sin enterarse.
    reubicado = chatbot.state.get("reubicado_al_reconfigurar") or []
    if reubicado:
        mensaje += "\n\n" + _texto_reubicado(reubicado)
    # A quien llega a una comida ya montada no se le pregunta qué quiere tomar: se le
    # pregunta si la deja o la cambia.
    mensaje += ("\n\n¿La dejamos así o le cambiamos algo?" if ya_puesto
                else "\n\n¿Qué quieres tomar?")
    mensaje = mensaje.lstrip("\n")   # sin el eco de la config, el texto empieza aquí

    await save_chatbot_session(chatbot)
    return {
        "session_id": session_id,
        "distribucion": distribucion,
        # La de verdad, no un 1 fijo: con la dieta ya empezada se arranca en la primera
        # comida que le falta, y el front tiene que saber en cuál está.
        "comida_actual": chatbot.state["comida_actual"],
        "meal_order": chatbot.state["meal_order"],
        "meal_nombre": label,
        "objetivo": objetivo,
        # LO QUE FALTA, QUE NO ES LO MISMO QUE EL OBJETIVO. La cabecera del chat pinta
        # «faltan ...» y se le estaba dando el objetivo entero: con la Comida 3 llena de
        # arroz -- 240 g de hidratos sobre 16,7 -- decía «faltan 17 g de hidratos» cuando
        # sobraban 223 (QA del 15-08 en producción). En una comida vacía los dos números
        # coinciden, que es por lo que había pasado desapercibido.
        "restante": chatbot.get_remaining_macros(),
        "cuadrada": chatbot.comida_cuadrada(chatbot.get_remaining_macros()),
        "day_overview": chatbot.get_day_overview(),
        "reubicado": reubicado,
        # Lo que ya hay montado en la comida a la que se llega: el front vaciaba su lista
        # al reconfigurar y, con el traspaso, el cliente vería el aviso pero no el
        # alimento en pantalla hasta recargar.
        "alimentos": (chatbot.state["comidas_completadas"].get(key) or {}).get("alimentos", []),
        "mensaje": mensaje
    }


def _gr(x) -> str:
    """Un gramaje como lo diría una persona: «40,5», «15» (nunca «15.0» ni «40.5»).

    Los mensajes de esta ruta salían con el número de máquina -- «Tu objetivo son
    40.5 P · 10 H · 15.0 G», «Te faltan 13 P · 17 H · 1 G» -- y es una de las quejas
    transversales de los vídeos del 15-08: el cliente no habla en iniciales ni con
    punto decimal."""
    v = float(x or 0)
    if abs(v - round(v)) < 0.05:
        return str(int(round(v)))
    return f"{v:.1f}".replace(".", ",")


_NOMBRE_MACRO = {"P": "proteína", "H": "hidratos", "G": "grasa"}


def _enumerar(partes: list) -> str:
    """«A», «A y B», «A, B y C». Como lo diría una persona, no una lista separada por comas."""
    if not partes:
        return ""
    if len(partes) == 1:
        return partes[0]
    return ", ".join(partes[:-1]) + " y " + partes[-1]


def _frase_objetivo(objetivo: dict) -> str:
    return (f"{_gr(objetivo['P'])} g de proteína, {_gr(objetivo['H'])} de hidratos "
            f"y {_gr(objetivo['G'])} de grasa")


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
SIN_MACROS = (
    "Todavía no tienes macros asignados, así que no puedo montarte el día: cualquier "
    "cantidad que te diera me la estaría inventando. Habla con tu entrenador para que te "
    "los asigne y vuelve por aquí, que lo montamos en un momento."
)
"""Lo mismo que le dice Nutrición («aún no tienes macros asignados»), en la voz de Marco.

El asistente era la única pantalla que NO lo comprobaba: con el cliente sin macros tiraba
del relleno de `macros_por_fecha` (160 P de entreno), le montaba un día de 195 P y se lo
guardaba en su dieta. En producción son 4 clientes activos, y ninguno debería comer eso.
"""


async def _procesar_mensaje(chatbot, texto: str, progreso=None):
    if chatbot.sin_macros_asignados():
        return {"action": "message", "message": SIN_MACROS, "sin_macros": True}
    from agent_loop import AgentLoop

    # EL TURNO, CRONOMETRADO Y GUARDADO (17-08-2026). La traza se escribía solo en el log
    # del pod, así que se iba con cada despliegue: el del 17 se llevó las de la sesión que
    # había que analizar y no quedó forma de saber qué había llamado el agente. Se guarda
    # aquí porque esta es la única puerta por la que pasan TODOS los turnos, también la
    # docena de atajos que contestan antes de llegar al modelo (`core/trazas_chat`).
    import time as _time

    from core.trazas_chat import guardar as _guardar_traza

    _t0 = _time.perf_counter()
    respuesta = None
    try:
        loop = await AgentLoop.crear(chatbot, progreso=progreso)
        respuesta = await loop.procesar(texto)
    except Exception as e:
        await _guardar_traza(chatbot=chatbot, mensaje=texto, respuesta=None,
                             ms=round((_time.perf_counter() - _t0) * 1000), error=repr(e)[:300])
        raise
    await _guardar_traza(chatbot=chatbot, mensaje=texto, respuesta=respuesta,
                         ms=round((_time.perf_counter() - _t0) * 1000))
    # LA CONVERSACIÓN SE APUNTA AQUÍ, PASE LO QUE PASE DENTRO. El agente ya la apunta en su
    # camino largo, pero tiene una docena de atajos que contestan antes de llegar al modelo
    # (el «sí» a una oferta, la calibración, deshacer, navegar...) y esos turnos se perdían:
    # ni el asistente los recordaba en el turno siguiente ni quedaban en el registro. Esta
    # es la única puerta por la que pasan todos.
    ultimo = (chatbot.messages_history or [])[-2:]
    ya_apuntado = any((m or {}).get("role") == "user" and (m or {}).get("content") == texto
                      for m in ultimo)
    if not ya_apuntado:
        chatbot.messages_history = (chatbot.messages_history or []) + [
            {"role": "user", "content": texto},
            {"role": "assistant", "content": (respuesta or {}).get("message") or ""}]
        chatbot.messages_history = chatbot.messages_history[-20:]
        chatbot.state["mensajes"] = chatbot.messages_history
    return respuesta


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
        # SI ESTÁ CUADRADA LO DICE EL MOTOR, NO EL REDONDEO DEL FRONT. La tarjeta ponía
        # «Comida cuadrada. Pulsa Guardar y siguiente» y la cabecera, justo encima,
        # «faltan 1 g de hidratos»: eran 0,5 g redondeados hacia arriba por el front
        # mientras el margen del método los daba por buenos (visto en producción el
        # 15-08). Dos criterios para la misma pregunta siempre acaban contradiciéndose.
        "cuadrada": chatbot.comida_cuadrada(chatbot.get_remaining_macros()),
        "fecha_pedida": fecha_pedida,
        # Consumida de una vez, como la fecha: dice que ESTE turno reconfiguró el día
        # por chat. El front solo arrastra la config al día nuevo cuando viene esto a
        # true («mañana descanso»: día y tipo en la misma frase). Sin la bandera, el
        # descanso dicho AYER para el día viejo se contagiaba a cada día nuevo.
        "config_tocada": bool(st.pop("config_tocada", False)),
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

    # EL ESTADO PARA EL FRONT SE ARMA ANTES DE GUARDAR, PORQUE CONSUME BANDERAS (16-08-2026).
    #
    # `_estado_para_front` hace `pop` de las de un solo uso -- `fecha_pedida`,
    # `config_tocada` --, y guardando primero se persistían PUESTAS. `config_tocada` decide
    # si la configuración viaja al día nuevo: una vez encendida se quedaba encendida para
    # siempre, así que a partir de ahí CUALQUIER cambio de día plantaba la configuración del
    # día viejo encima del nuevo. Medido en producción: tras pedir «3 comidas» para el lunes,
    # el martes y el domingo pasaban a anunciarse como «3 comidas, solo post» teniendo cuatro
    # y sin peri en el plan. Es el contagio que Jesús reportó en la ronda 1, colándose por
    # otra puerta.
    estado = _estado_para_front(chatbot)
    await save_chatbot_session(chatbot)
    return {
        "session_id": session_id,
        "response": response,
        "state": estado,
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
            # Igual que en `/message`: primero se consume el estado del turno (hace `pop`
            # de las banderas de un solo uso) y DESPUÉS se guarda, o se quedan pegadas.
            estado = _estado_para_front(chatbot)
            await save_chatbot_session(chatbot)
            await cola.put({"tipo": "respuesta", "response": resp,
                            "state": estado,
                            "day_overview": chatbot.get_day_overview()})
        except Exception as e:
            await cola.put({"tipo": "error", "detalle": f"{type(e).__name__}"})
        await cola.put(None)

    # UN TURNO LARGO NO ES UNA CONEXIÓN CAÍDA (17-08-2026).
    #
    # «No quiero que quites la avena, solo bájala a 30 g. Y las nueces fuera. ¿Qué tengo
    # ahora?» -- tres cosas en un mensaje, que el prompt promete atender -- estuvo minuto y
    # medio trabajando y acabó en «se me ha cortado la conexión y he dejado la petición a
    # medias». No se cortó nada: la pantalla corta a los 45 segundos de SILENCIO, y entre dos
    # herramientas el modelo puede pensar más que eso sin que aquí salga ningún evento.
    #
    # Así que mientras haya trabajo se manda un latido. Cambia dos cosas: la pantalla no se
    # rinde, y el cliente ve que seguimos con lo suyo en vez de un indicador congelado.
    LATIDO = 12

    async def eventos():
        tarea = asyncio.create_task(trabajar())
        esperas = 0
        # OJO AL ESPERAR CON LATIDO: la espera NO puede cancelar el `get` de la cola.
        # Con `asyncio.wait_for(cola.get(), timeout)` el primer latido que caía justo cuando
        # llegaba la respuesta se la LLEVABA por delante -- el get cancelado se traga el
        # elemento -- y la pantalla se quedaba en «Un momento más...» con el turno terminado y
        # el log del servidor diciendo 200 OK. Así que la espera se hace sobre una tarea que
        # sobrevive al timeout, y el elemento no se pierde nunca.
        pendiente = None
        while True:
            if pendiente is None:
                pendiente = asyncio.ensure_future(cola.get())
            listas, _ = await asyncio.wait({pendiente}, timeout=LATIDO)
            if not listas:
                esperas += 1
                yield ('data: ' + _json.dumps(
                    {"tipo": "progreso",
                     "texto": "Sigo con lo tuyo..." if esperas < 3 else "Un momento más..."},
                    ensure_ascii=False) + "\n\n")
                continue
            item = pendiente.result()
            pendiente = None
            esperas = 0
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
        # El motivo más común de fallo sin detalles: la tarjeta es de una ronda vieja (el
        # historial las deja pulsables al hacer scroll) y ese borrador ya no existe.
        existe = borrador_id in (chatbot.state.get("borradores") or {})
        if detalles:
            mensaje = ("No lo he aplicado: " + "; ".join(detalles) +
                       ". Dime si lo cambio o lo pongo igualmente.")
        elif not existe:
            mensaje = ("Ese menú era de una ronda anterior y ya no está activo. "
                       "Si lo quieres, pídeme opciones otra vez y te lo vuelvo a montar.")
        else:
            mensaje = ("No he podido aplicar ese menú. " +
                       (resultado.get("error") or "Dime si te monto opciones nuevas."))
        response = {"action": "no_foods", "message": mensaje,
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
    faltan = [f"{_gr(rem[k])} g de {nombres_m[k]}" for k in ("P", "H", "G") if rem.get(k, 0) > 4]
    pasan = [f"{_gr(abs(rem[k]))} g de {nombres_m[k]}" for k in ("P", "H", "G") if rem.get(k, 0) < -4]
    aviso = ""
    if faltan:
        aviso += f"\n⚠️ Ojo: {label_guardada} quedó sin cuadrar (faltan {' y '.join(faltan)})."
    if pasan:
        aviso += f"\n⚠️ En {label_guardada} te pasas {' y '.join(pasan)}."

    resultado = chatbot.complete_current_meal()
    # Guardar avanza de comida: los menús propuestos para la que se cierra mueren con
    # ella, igual que en la herramienta del agente (QA 15-08, A4-F04: en el Post seguía
    # citando «las opciones 3-6» de la Comida 1 porque el botón no las tiraba).
    st = chatbot.state
    mk_ahora = chatbot.current_meal_key()
    bs = st.get("borradores") or {}
    for bid in [k for k, b in bs.items() if b.get("meal_key") != mk_ahora]:
        bs.pop(bid, None)
    st["last_options"] = []
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
        key_sig = chatbot.current_meal_key()
        label = chatbot.meal_label(key_sig)
        objetivo = chatbot.get_current_meal_macros()
        # Si el botón «Guardar y siguiente» aterriza en el intra o el post, el guion del
        # método sale AQUÍ, igual que cuando se llega por chat. Por el botón se recibía
        # un «¿Qué quieres tomar?» pelado, y el guion de Jesús solo existía para quien
        # guardaba hablando (ronda 1 del 15-08). Se marca como dicho para que el agente
        # no lo repita: a la siguiente frase del cliente toca montar, no volver a recitar.
        guion_txt = None
        momento_sig = {"Intra": "intra", "Post": "post"}.get(key_sig)
        if momento_sig:
            try:
                from core.guion_peri import guion
                guion_txt = guion(momento_sig, "principal")
            except Exception:
                guion_txt = None
            if guion_txt:
                dichos = chatbot.state.setdefault("guion_peri_dicho", [])
                marca = f"{key_sig}:principal"
                if marca not in dichos:
                    dichos.append(marca)
                await save_chatbot_session(chatbot)
        mensaje = (f"Comida guardada ✓.{aviso}\nVamos con {label}. Tu objetivo es:\n"
                   f"• Proteína: {_gr(objetivo['P'])} g\n"
                   f"• Hidratos: {_gr(objetivo['H'])} g\n"
                   f"• Grasa: {_gr(objetivo['G'])} g\n\n")
        mensaje += guion_txt if guion_txt else "¿Qué quieres tomar?"
        return {
            "session_id": session_id,
            "comida_completada": resultado,
            "dia_completo": False,
            "comida_actual": siguiente,
            "meal_nombre": label,
            "objetivo": objetivo,
            "day_overview": chatbot.get_day_overview(),
            "mensaje": mensaje
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

@router.get("/day-overview")
async def chatbot_day_overview(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """El estado del día tal y como está AHORA en la sesión. El botón «Resumen del día»
    pintaba el estado que React tenía en memoria, que tras un guardado iba una comida por
    detrás (QA 15-08, A1-M3: «5/6» con las seis guardadas)."""
    _assert_session_owner(session_id, current_user)
    chatbot = await get_or_create_chatbot(session_id, db)
    return {"day_overview": chatbot.get_day_overview()}


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

    # EL VOLCADO SOLO VALE PARA EL DÍA EN EL QUE ESTÁ LA SESIÓN (QA 15-08, A3-01). Al
    # cambiar de día hay una ventana en la que el front ya apunta a la fecha nueva pero
    # la sesión todavía lleva las comidas de la vieja: un volcado en esa ventana escribía
    # la comida del 18 dentro del 19 (235 g de proteína sobre un objetivo de 56). Si la
    # fecha pedida no es la de la sesión, no se escribe nada y se dice por qué.
    fecha_sesion = chatbot.state.get("fecha_objetivo")
    if fecha_sesion and fecha_sesion != fecha:
        return {"skipped": "cambio_de_dia", "fecha": fecha, "fecha_sesion": fecha_sesion}

    # DOS PESTAÑAS NO SE PISAN EL DÍA (QA 15-08 en prod, el más caro de todos). Cada
    # pestaña abre su sesión, y la que llevaba el estado viejo volcaba con overwrite=true
    # y BORRABA el intra, la Comida 2 y la Comida 3 que la otra acababa de montar, además
    # de devolver la configuración a la de antes. Nadie se enteraba.
    #
    # La última sesión que toca un día se apunta en la propia dieta: si el volcado viene
    # de otra sesión distinta, no se escribe y se dice, que es lo que pidió Jesús («al
    # menos debe avisar»). Volcar a mano con overwrite explícito sigue pudiendo.
    existing = await db.diets.find_one({"user_id": user_id, "fecha": fecha})
    dueno = (existing or {}).get("sesion_chat")
    if existing and dueno and dueno != session_id and not overwrite:
        return {
            "skipped": "otra_sesion",
            "fecha": fecha,
            "message": ("Este día lo estás montando en otra pestaña o en otro dispositivo. "
                        "Para no pisar lo que hay allí, no lo he guardado desde aquí: sigue "
                        "en la otra o recarga esta para trabajar con lo último."),
        }

    # LO QUE EL CLIENTE BORRA EN NUTRICIÓN NO SE LE DEVUELVE (15-08, encontrado por
    # Francisco en producción).
    #
    # El asistente se trae al empezar lo que el día ya tenía montado (`comidas_traidas`) y
    # lo guarda en su sesión. Si después el cliente vacía ese día en Nutrición -- en otra
    # pestaña, en el móvil, o simplemente porque no lo quería --, la sesión sigue con su
    # copia, y el siguiente «Guardar y siguiente» la escribe otra vez con `upsert`: la
    # comida que acababa de borrar reaparece. Él lo vio con un desayuno que había quitado a
    # mano.
    #
    # Ni se resucita ni se tira su trabajo: se frena y se dice. Solo mira las comidas que
    # VINIERON del plan; lo montado aquí en el chat no se toca. Con `overwrite` explícito
    # (el cliente ha dicho que sí a sobrescribir) se guarda igual.
    traidas = list(chatbot.state.get("comidas_traidas") or [])
    if traidas and not overwrite:
        en_el_plan = (existing or {}).get("comidas") or {}
        fuera = [k for k in traidas if not (en_el_plan.get(k) or {}).get("alimentos")]
        if fuera:
            nombres = _enumerar([chatbot.meal_label(k) for k in fuera])
            return {
                "skipped": "borrado_fuera",
                "fecha": fecha,
                "comidas": fuera,
                "message": (f"Has vaciado {nombres} en tu plan mientras lo teníamos abierto "
                            f"aquí. No lo guardo para no devolverte algo que acabas de "
                            f"quitar. Recarga el asistente y seguimos con lo que hay ahora."),
            }

    # Chequeo de sobrescritura: ¿el día ya tiene alimentos?
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
        # Quién ha escrito este día por última vez, para que la otra pestaña no lo pise.
        "sesion_chat": session_id,
        "macros_snapshot": chatbot.state.get("macros_usuario"),
        "distribution_targets": targets,
        "is_cuadrado": False,
        "comida_volcada": None,
    })

    # LO QUE ACABA DE IRSE A NUTRICIÓN ESTÁ GUARDADO, Y HAY QUE APUNTARLO (16-08, en prod).
    #
    # El contador salía «Comidas guardadas: 1/6» con cinco comidas montadas y las cinco
    # escritas en el plan: `completas` cuenta `saved_meals`, y a esa lista solo entraban las
    # que pasaban por el botón «Guardar y siguiente» o las que venían del plan. Con el
    # volcado automático encendido siempre (16-08), casi ninguna pasa ya por ese botón.
    # Resultado: el resumen del día mentía, y «guardar y siguiente» volvía a parar en
    # comidas que ya estaban puestas.
    tocadas = [k for k, v in comidas.items() if (v or {}).get("alimentos")]
    saved = chatbot.state.setdefault("saved_meals", [])
    nuevas = [k for k in tocadas if k not in saved]
    if nuevas:
        saved.extend(nuevas)
        await save_chatbot_session(chatbot)

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


# ── LA TRAZA, PARA QUIEN TIENE QUE DIAGNOSTICAR ─────────────────────────────────────────
#
# Hasta ahora, ante un «mira lo que me ha hecho el asistente» había que pedirle al cliente
# que pegara la conversación y cruzar los dedos para que el pod no se hubiera reiniciado.
# Esto lee lo que `core/trazas_chat` va guardando: el mensaje, lo que llamó el agente en
# orden, lo que le contestó cada herramienta y lo que acabó respondiendo.
#
# Es del equipo (admin y entrenadores), como la ficha del cliente: aquí se lee lo que ha
# escrito una persona en su chat.
trazas_router = APIRouter(prefix="/chat-traces", tags=["chatbot"])


@trazas_router.get("")
async def listar_trazas(email: Optional[str] = None, user_id: Optional[str] = None,
                        session_id: Optional[str] = None, desde: Optional[str] = None,
                        limite: int = 50, staff=Depends(get_admin_user)):
    """Los últimos turnos, del cliente que se pida (por correo o por id) o de todos.

    `desde` filtra por fecha ("2026-08-17"). El tiempo del modelo no se guarda aparte: es
    el total menos lo que se fue en herramientas, y se calcula aquí para no repetir la
    resta en cada sitio que lo lea.
    """
    filtro = {}
    if email:
        u = await db.users.find_one({"email": email.strip().lower()}, {"_id": 0, "id": 1})
        if not u:
            raise HTTPException(status_code=404, detail="No hay ningún usuario con ese correo")
        filtro["user_id"] = u["id"]
    elif user_id:
        filtro["user_id"] = user_id
    if session_id:
        filtro["session_id"] = session_id
    if desde:
        try:
            filtro["created_at"] = {"$gte": datetime.fromisoformat(desde)}
        except ValueError:
            raise HTTPException(status_code=400, detail="La fecha va como 2026-08-17")

    limite = max(1, min(int(limite or 50), 200))
    filas = await db.chat_traces.find(filtro, {"_id": 0}).sort("created_at", -1).to_list(limite)

    # El nombre de quien habla, para no tener que ir a buscarlo a mano cliente por cliente.
    ids = {f.get("user_id") for f in filas if f.get("user_id")}
    quien = {}
    if ids:
        async for u in db.users.find({"id": {"$in": list(ids)}}, {"_id": 0, "id": 1, "name": 1, "email": 1}):
            quien[u["id"]] = {"nombre": u.get("name"), "email": u.get("email")}

    for f in filas:
        f["cliente"] = quien.get(f.get("user_id"), {})
        f["ms_modelo"] = max(0, int(f.get("ms_total") or 0) - int(f.get("ms_herramientas") or 0))
        if isinstance(f.get("created_at"), datetime):
            f["created_at"] = f["created_at"].isoformat()
    return {"total": len(filas), "trazas": filas}
