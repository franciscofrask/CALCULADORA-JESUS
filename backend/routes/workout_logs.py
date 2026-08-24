"""
El registro de los entrenos hechos (T3 del doc 16-08).

El contrato esta escrito en `models/workout_log.py` y esto lo cumple: una fila por
cliente y dia, con `fecha` = el dia del cliente en hora de España, y `client_id` = el id
del PERFIL (client_profiles.id), el mismo criterio que `checkins`.

Es la fuente de "entrenaste X de Y": la leen la linea de entreno de Inicio (T1), el
Diario (T5) y los conteos de los reportes (T7/T8). Por eso guarda lo que el cliente
marca y nada mas: no da por entrenado el dia que le tocaba.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from core.database import db
from core.plan_access import require_access
from core.tiempo import hoy_madrid
from models.workout_log import WorkoutLogCreate
from routes.settings import pantalla_activa

router = APIRouter(tags=["workout_logs"])

# Los dias de la semana como los escribe el panel en `routines.days[].day`. `weekday()`
# devuelve 0 para el lunes, asi que el orden de esta tupla es el que hay que respetar.
DIAS_SEMANA = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")

# Las tildes de "miércoles" y "sábado": la rutina puede traerlos escritos de las dos
# maneras segun quien la cargara, y comparar "miércoles" con "miercoles" da falso.
_SIN_TILDES = str.maketrans("áéíóúÁÉÍÓÚ", "aeiouAEIOU")


def _plano(texto: Optional[str]) -> str:
    return str(texto or "").strip().lower().translate(_SIN_TILDES)


async def _exige_pantalla_encendida() -> None:
    """T3 entero vive detras del interruptor `t3_entreno` (regla transversal del doc:
    cada pantalla nueva se tiene que poder apagar desde el panel sin desplegar)."""
    if not await pantalla_activa("t3_entreno"):
        raise HTTPException(
            status_code=403,
            detail="El registro de entrenos todavía no está disponible.",
        )


def dia_de_rutina(routine: Optional[Dict[str, Any]], fecha_iso: str) -> Optional[Dict[str, Any]]:
    """El dia de la rutina que le toca en esa fecha, o None si descansa o no hay rutina.

    La rutina se guarda por dia de la semana ("Lunes", "Martes"...), no por fecha: aqui se
    traduce el dia del cliente al dia de la rutina.
    """
    if not routine:
        return None
    try:
        nombre = DIAS_SEMANA[datetime.fromisoformat(fecha_iso).weekday()]
    except (ValueError, TypeError, IndexError):
        return None
    for d in routine.get("days") or []:
        if _plano(d.get("day")) == nombre:
            return None if d.get("is_rest") else d
    return None


def titulo_del_dia(dia: Optional[Dict[str, Any]]) -> str:
    """Lo que va en la cabecera de la pantalla: el grupo muscular del dia.

    La rutina no tiene hoy un campo obligatorio para esto (el panel guarda dias y
    ejercicios), asi que se acepta el que traiga -- `grupo`, `focus` o `nombre`, segun de
    donde venga cargada -- y si no trae ninguno se pone un titulo honrado en vez de
    inventarse un grupo muscular que nadie ha dicho.
    """
    if not dia:
        return "Entreno de hoy"
    for clave in ("grupo", "focus", "nombre", "titulo"):
        valor = str(dia.get(clave) or "").strip()
        if valor:
            return valor
    if not (dia.get("exercises") or []) and dia.get("cardio"):
        return "Cardio"
    return "Entreno de hoy"


def numero_de_rutina(routine: Optional[Dict[str, Any]], dia: Optional[Dict[str, Any]]) -> Optional[int]:
    """"rutina 3": que numero hace este dia entre los de entreno de la semana."""
    if not routine or not dia:
        return None
    n = 0
    for d in routine.get("days") or []:
        if d.get("is_rest"):
            continue
        n += 1
        if _plano(d.get("day")) == _plano(dia.get("day")):
            return n
    return None


async def _perfil_y_rutina(ctx: dict) -> tuple:
    profile = ctx["profile"]
    routine = await db.routines.find_one(
        {"client_id": profile["id"], "status": "active"}, {"_id": 0})
    return profile, routine


async def log_del_dia(client_id: str, fecha: str) -> Optional[Dict[str, Any]]:
    """El registro de ese dia, si lo hay. Lo usan tambien el cierre del dia (T4, para
    saber si le falta marcar el entreno) e Inicio (T1)."""
    return await db.workout_logs.find_one({"client_id": client_id, "fecha": fecha}, {"_id": 0})


async def tiene_rutina_puesta(client_id: str) -> bool:
    """¿Tiene rutina puesta? La estructurada (`db.routines`) o la entregada en PDF.

    UNA SOLA FORMA DE PREGUNTARLO (24-08). Cada pantalla lo preguntaba por su cuenta
    mirando solo `db.routines` con `status: active`, y el PDF es la via de entrega real
    ("se siguen generando como hasta ahora", bloque 11 del doc 19-08). Resultado con un
    cliente de verdad: tenia su rutina entregada en PDF, el panel de Rutinas ya lo decia
    ("En PDF", arreglado en bc2cba8) y el cierre del dia le seguia sacando la caja "Tu
    entreno de hoy · Si entrenaste por tu cuenta, apuntalo aqui", que es la del que NO
    tiene rutina con nosotros.

    Esta es la version de UN cliente de lo que el panel pregunta de todos
    (`routines._ultimo_pdf_por_cliente`): la misma fuente, sin otra copia del criterio.
    Quien necesite saberlo, que llame aqui y no vuelva a escribir el find.

    EL INDICE NO ES "PARA CUANDO CREZCA", ES PARA ESTA SEMANA. `db.rutina_pdfs` solo
    tiene el de `_id`, asi que esto recorre la coleccion entera, y cada fila lleva el PDF
    dentro (hasta 15 MB): medido en produccion son 2 filas y 4,7 MB, o sea 2,3 MB de media.
    Al que NO tiene PDF -- hoy 196 de 198 -- se le leen todas antes de contestar que no, y
    esto se llama en cada carga del cierre del dia. El doc 24-08 (punto 67) dice que a 165
    clientes hay que subirles la suya ya: con eso serian ~390 MB recorridos por cada
    apertura de la pantalla. El arreglo es una linea en `core/database.create_indexes`
    (fichero de otro bloque), y el mismo indice arregla de paso los `find_one(...,
    sort=[("uploaded_at", -1)])` de `routines.py`, que recorren lo mismo desde el 21-08.
    """
    if await db.routines.find_one({"client_id": client_id, "status": "active"}, {"_id": 1}):
        return True
    return await db.rutina_pdfs.find_one({"client_id": client_id}, {"_id": 1}) is not None


async def pesos_de_la_ultima_vez(client_id: str, dia_rutina: Optional[str],
                                 excluye_fecha: Optional[str] = None) -> List[Dict[str, Any]]:
    """Los pesos de la ultima vez que le toco ESA misma rutina.

    Es lo que pide el doc ("para que sepas de donde partir"): la tabla no empieza vacia,
    empieza donde la dejo. Si nunca ha registrado ese dia, se devuelve vacia en vez de
    ensenarle los pesos de otro grupo muscular, que le haria empezar por el sitio
    equivocado.
    """
    query: Dict[str, Any] = {"client_id": client_id, "pesos": {"$ne": []}}
    if dia_rutina:
        query["dia_rutina"] = dia_rutina
    if excluye_fecha:
        query["fecha"] = {"$ne": excluye_fecha}
    ultimo = await db.workout_logs.find_one(query, {"_id": 0, "pesos": 1}, sort=[("fecha", -1)])
    return (ultimo or {}).get("pesos") or []


@router.get("/workout-logs/hoy")
async def get_log_de_hoy(fecha: Optional[str] = Query(None), ctx=Depends(require_access("rutina"))):
    """Lo que Inicio y la pantalla de registro necesitan de hoy.

    Devuelve `{"log": ... | null}` (el contrato) y, ademas, lo que la pantalla tiene que
    pintar antes de que el cliente toque nada: la cabecera del dia y los pesos de la
    ultima vez con esa misma rutina.

    `fecha` es el dia del RELOJ DEL CLIENTE (bloque F, 23-08), validado; sin el, España.
    """
    await _exige_pantalla_encendida()
    profile, routine = await _perfil_y_rutina(ctx)
    from core.tiempo import dia_del_cliente
    fecha = dia_del_cliente(fecha)
    dia = dia_de_rutina(routine, fecha)
    log = await log_del_dia(profile["id"], fecha)
    titulo = titulo_del_dia(dia)

    return {
        "log": log,
        "fecha": fecha,
        # AQUI `tiene_rutina` NO ES "¿tiene rutina puesta?", ES "¿se que te toca HOY?", y
        # por eso NO llama a `tiene_rutina_puesta()` aunque se le parezca. Quien lo lee es
        # Inicio (frontend/src/pages/ClientDashboard.jsx:452): con esto en true da por
        # bueno el resto de la respuesta y decide el dia con `descanso`
        # (`esDiaDeEntreno = !!entrenoDelDia && !entrenoDelDia.descanso`).
        #
        # Ponerlo en true para el que tiene su rutina en PDF -- que es la respuesta honrada
        # a la otra pregunta -- rompe Inicio: del PDF no sale que dias entrena (el reparto
        # y `training_weekdays` estan vacios en el unico cliente real que lo tiene hoy),
        # asi que `descanso` seria false SIEMPRE y le diriamos "Entreno · Ver la rutina"
        # los siete dias, tapando ademas la linea buena que ya tiene, "Tu rutina, en PDF"
        # (esa sale de /routines/pdf/info y funciona).
        #
        # Para cambiarlo hay que tocar Inicio primero: que distinga "no se que te toca"
        # (descanso null) de "hoy descansas" (descanso false/true). Mientras tanto, quien
        # necesite saber si tiene rutina PUESTA que llame a `tiene_rutina_puesta()`, que
        # para eso esta y ya lo usa el cierre del dia.
        "tiene_rutina": bool(routine),
        "dia_rutina": titulo if dia else None,
        "semana": profile.get("week"),
        "numero_rutina": numero_de_rutina(routine, dia),
        "descanso": bool(routine) and dia is None,
        # Un dia de solo cardio ("Hoy solo cardio · 40 minutos") se registra como cardio:
        # cuenta como dia hecho en Inicio, pero en el mensual va a su propio bloque.
        "tipo": "cardio" if (dia and not (dia.get("exercises") or []) and dia.get("cardio")) else "entreno",
        # Los minutos van con el tipo: Inicio escribe «Hoy solo cardio · 40 minutos» y sin
        # esto tendría que volver a buscar el día en la rutina por su cuenta, que es como
        # acababa mirando el día del NAVEGADOR en vez del de España.
        "cardio_minutos": ((dia or {}).get("cardio") or {}).get("duration"),
        "ejercicios": [e.get("name") for e in (dia or {}).get("exercises") or []],
        # Los de hoy si ya guardo, y si no los de la ultima vez que le toco esta rutina.
        "pesos_referencia": (log or {}).get("pesos") or await pesos_de_la_ultima_vez(
            profile["id"], titulo if dia else None, excluye_fecha=fecha),
    }


@router.get("/workout-logs")
async def listar_logs(
    desde: Optional[str] = Query(None, description="YYYY-MM-DD"),
    hasta: Optional[str] = Query(None, description="YYYY-MM-DD"),
    ctx=Depends(require_access("rutina")),
):
    """Los registros del cliente en un tramo de fechas (Diario y conteos de reportes)."""
    await _exige_pantalla_encendida()
    profile = ctx["profile"]
    query: Dict[str, Any] = {"client_id": profile["id"]}
    tramo: Dict[str, Any] = {}
    if desde:
        tramo["$gte"] = desde
    if hasta:
        tramo["$lte"] = hasta
    if tramo:
        query["fecha"] = tramo
    logs = await db.workout_logs.find(query, {"_id": 0}).sort("fecha", -1).to_list(400)
    return {"logs": logs}


@router.post("/workout-logs")
async def guardar_log(data: WorkoutLogCreate, ctx=Depends(require_access("rutina"))):
    """Guarda el entreno de HOY. Upsert por (client_id, fecha): volver a guardar el mismo
    dia corrige lo puesto, no crea una fila nueva ni cuenta dos entrenos."""
    await _exige_pantalla_encendida()
    profile, routine = await _perfil_y_rutina(ctx)
    # El dia del RELOJ DEL CLIENTE si la pantalla lo manda (bloque F, 23-08): un entreno
    # registrado a las 00:30 de un cliente al este de España se apuntaba en su mañana.
    from core.tiempo import dia_del_cliente
    fecha = dia_del_cliente(getattr(data, "fecha", None))

    # El dia de la rutina lo manda la pantalla (es lo que enseño), y si no viene se
    # resuelve aqui: sin el, el Diario y la precarga de pesos se quedan sin saber de que
    # entreno hablan.
    dia_rutina = (data.dia_rutina or "").strip() or None
    if not dia_rutina:
        dia = dia_de_rutina(routine, fecha)
        dia_rutina = titulo_del_dia(dia) if dia else None

    ahora = datetime.now(timezone.utc).isoformat()
    doc = {
        "client_id": profile["id"],
        "fecha": fecha,
        "routine_id": (routine or {}).get("id"),
        "dia_rutina": dia_rutina,
        "hecho": bool(data.hecho),
        "tipo": data.tipo,
        "estrellas": data.estrellas,
        "nota": (data.nota or "").strip() or None,
        "pesos": [p.model_dump() for p in data.pesos],
        "compartida": bool(data.compartida),
        "updated_at": ahora,
    }
    await db.workout_logs.update_one(
        {"client_id": profile["id"], "fecha": fecha},
        {"$set": doc, "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": ahora}},
        upsert=True,
    )
    return {"log": await log_del_dia(profile["id"], fecha)}
