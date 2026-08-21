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

from core.database import db
from core.dias_de_entreno import dias_de_entreno
from core.security import get_current_user, get_admin_user, assert_client_access
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

    return RoutineResponse(**routine)

@router.get("/history", response_model=List[RoutineResponse])
async def get_routine_history(ctx = Depends(require_access("rutina"))):
    """Obtener historial de rutinas (requiere plan con rutina y suscripción activa)."""
    profile = ctx["profile"]

    routines = await db.routines.find(
        {"client_id": profile["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(20)
    
    return [RoutineResponse(**r) for r in routines]


# ==================== ADMIN ROUTES ====================

admin_router = APIRouter(prefix="/admin/routines", tags=["admin-routines"])


@admin_router.get("/overview")
async def routines_overview(user = Depends(get_admin_user)):
    """Vista general para el panel: cada cliente activo y si tiene rutina activa o no."""
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

    out = []
    for p in profiles:
        u = umap.get(p["user_id"])
        if not u:
            continue
        r = rmap.get(p["id"])
        out.append({
            "client_id": p["id"],
            "name": u.get("name"),
            "email": u.get("email"),
            "plan": p.get("plan"),
            "has_routine": bool(r),
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
        "days": routine.get("days", []),
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
    """Los clientes cuyo plan incluye rutina y no tienen ninguna activa."""
    from core.plan_access import plan_grants_feature
    from routes.admin import _fuera_el_equipo

    con_rutina = set(await db.routines.distinct("client_id", {"status": "active"}))
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
                    "days": rutina.get("days", []),
                    "trainer_notes": rutina.get("trainer_notes"),
                    "status": "active",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    # De dónde salió, para poder deshacerlo y para saber cuál se puso a mano.
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
    porNombre = {}
    for d in (dias or []):
        if not isinstance(d, dict):
            continue
        nombre = str(d.get("day") or "").strip().capitalize()
        if nombre not in SEMANA:
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
                "sets": e.get("sets"),
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
        fuera.append(r)
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
async def borrar_de_biblioteca(rutina_id: str, user = Depends(get_admin_user)):
    """Quita una rutina de la biblioteca.

    No toca a quien ya la tenga puesta: al asignarla se copió, así que sus clientes siguen
    con la suya. Borrar la plantilla no le deja a nadie sin rutina.
    """
    r = await db.routine_templates.delete_one({"id": rutina_id})
    if not r.deleted_count:
        raise HTTPException(status_code=404, detail="Esa rutina ya no está")
    return {"borrada": True}


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

    await db.routines.update_many({"client_id": client_id, "status": "active"},
                                  {"$set": {"status": "inactive"}})
    rutina = {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "days": plantilla.get("days", []),
        "trainer_notes": plantilla.get("trainer_notes"),
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
        # De dónde salió: para saber cuál se puso a mano, cuál la IA y cuál la biblioteca.
        "origen": "biblioteca",
        "plantilla_id": rutina_id,
        "plantilla_nombre": plantilla.get("nombre"),
        "puesta_por": user.get("id"),
    }
    await db.routines.insert_one(dict(rutina))
    if await rutina_visible_para_el_cliente():
        await avisar_rutina_nueva(profile["user_id"])
    return {"asignada": True, "nombre": plantilla.get("nombre")}


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
from fastapi import File, UploadFile          # noqa: E402
from fastapi.responses import Response        # noqa: E402
from bson.binary import Binary                # noqa: E402

MAX_PDF_BYTES = 15 * 1024 * 1024


async def _guardar_pdf_de_rutina(client_id: str, file: UploadFile, subido_por: str) -> dict:
    if (file.content_type or "").lower() != "application/pdf" \
            and not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="La rutina tiene que ser un PDF.")
    contenido = await file.read()
    if not contenido:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")
    if len(contenido) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413,
                            detail=f"El PDF pesa demasiado; el máximo es {MAX_PDF_BYTES // (1024 * 1024)} MB.")
    doc = {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "filename": file.filename or "rutina.pdf",
        "size": len(contenido),
        "subido_por": subido_por,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "data": Binary(contenido),
    }
    await db.rutina_pdfs.insert_one(doc)
    return doc


@admin_router.post("/pdf/{client_id}")
async def subir_pdf_de_rutina(client_id: str, file: UploadFile = File(...),
                              user=Depends(get_admin_user)):
    """Sube (o sustituye) la rutina en PDF de un cliente. Se guarda el histórico: el
    cliente ve siempre la última, pero la del mes pasado no se pierde."""
    perfil = await db.client_profiles.find_one({"id": client_id}, {"_id": 0, "id": 1, "user_id": 1})
    if not perfil:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    doc = await _guardar_pdf_de_rutina(client_id, file, subido_por=user.get("id"))
    # El aviso de entrega, el mismo que mandan las tres vías estructuradas y que aquí
    # faltaba: el PDF se quedaba guardado sin que el cliente supiera que lo tenía. Mismo
    # candado que ellas (t3_entreno) y máximo uno al día, que es la regla de los avisos
    # de entrega: resubirlo para corregir una errata no puede sonarle dos veces.
    if perfil.get("user_id") and await rutina_visible_para_el_cliente() \
            and not await _hay_aviso_de_hoy(perfil["user_id"], "rutina_nueva"):
        await avisar_rutina_nueva(perfil["user_id"])
    return {"ok": True, "id": doc["id"], "filename": doc["filename"],
            "size": doc["size"], "uploaded_at": doc["uploaded_at"]}


@admin_router.get("/pdf/{client_id}/info")
async def info_pdf_de_rutina_admin(client_id: str, user=Depends(get_admin_user)):
    doc = await db.rutina_pdfs.find_one({"client_id": client_id}, {"_id": 0, "data": 0},
                                        sort=[("uploaded_at", -1)])
    return {"hay": bool(doc), **({k: doc[k] for k in ("id", "filename", "size", "uploaded_at")} if doc else {})}


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
    return {"hay": bool(doc), **({k: doc[k] for k in ("filename", "uploaded_at")} if doc else {})}


@router.get("/pdf")
async def ver_pdf_de_rutina(user=Depends(get_current_user)):
    perfil = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
    if not perfil:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    doc = await db.rutina_pdfs.find_one({"client_id": perfil["id"]}, {"_id": 0},
                                        sort=[("uploaded_at", -1)])
    return await _servir_pdf(doc)
