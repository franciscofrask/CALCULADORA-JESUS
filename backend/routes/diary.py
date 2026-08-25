"""
El Diario (T5 del doc 16-08).

"Solo lectura. Cae todo lo que escribe: las notas del día y lo del entreno."

No es una coleccion nueva: es una VISTA. Se compone de lo que el cliente ya escribio en
dos sitios, y por eso aqui no hay POST ni PUT ninguno:

  - `workout_logs` con `nota`: las entradas de entreno, con sus estrellas y su peso
    destacado (T3).
  - `checkins` con `notas.texto` o con `entreno_nota`: las entradas del dia, del cierre
    del dia (T4). Cada una viaja ademas con `dia_resumen`, lo que contesto ese dia, para
    que el traslado del historial al Diario (punto 23 del doc 24-08) sea pintar y no
    volver a pedir los check-ins.

Dos reglas que no son de estilo:

  - EL EQUIPO SOLO VE LAS COMPARTIDAS. La marca la pone el cliente al escribir y manda
    ella. El filtro va aqui, en el servidor, y no en la pantalla: una nota privada que
    viaja al navegador del coach ya se ha escapado, la pinte o no.
  - `client_id` es el id del PERFIL (client_profiles.id), el mismo criterio que
    `checkins` y `workout_logs`: en esta base conviven dos ids de cliente y mezclarlos da
    cifras falsas sin dar ningun error.

La fecha que manda es el dia del cliente en hora de España (`dia` en los checkins,
`fecha` en los workout_logs), no el `created_at` en UTC: un cierre de las 23:30 de Madrid
es de hoy, no de mañana.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core.database import db
from core.security import get_current_user, get_admin_user, assert_client_access
from routes.settings import pantalla_activa

router = APIRouter(tags=["diary"])

# Tope de seguridad de la paginacion: el Diario de un cliente de un año son unos 400
# apuntes, y aun asi se pide por bloques.
LIMITE_MAXIMO = 100


async def _exige_pantalla_encendida() -> None:
    """El Diario entero vive detras del interruptor `t5_diario` (regla transversal del
    doc: cada pantalla nueva se tiene que poder apagar desde el panel sin desplegar)."""
    if not await pantalla_activa("t5_diario"):
        raise HTTPException(status_code=403, detail="Tu diario todavía no está disponible.")


def _numero(valor: Any) -> str:
    """80.0 -> "80", 82.5 -> "82,5". Los decimales con coma, que es como se escriben aqui."""
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return ""
    entero = int(n)
    return str(entero) if n == entero else f"{n}".replace(".", ",")


def _peso_destacado(pesos: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    """"Press banca 80 kg": el ejercicio mas pesado de la sesion.

    Es lo que el doc enseña al lado de las estrellas. Con varias filas se coge la de mas
    peso porque es la que el cliente reconoce como "lo de hoy"; sin peso apuntado no se
    inventa nada.
    """
    candidatos = [p for p in (pesos or []) if p and p.get("peso_kg") is not None and p.get("ejercicio")]
    if not candidatos:
        return None
    mejor = max(candidatos, key=lambda p: p.get("peso_kg") or 0)
    return f"{str(mejor['ejercicio']).strip()} {_numero(mejor['peso_kg'])} kg"


def _entrada_de_entreno(log: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "tipo": "entreno",
        "fecha": log.get("fecha"),
        "texto": log.get("nota"),
        "estrellas": log.get("estrellas"),
        "compartida": bool(log.get("compartida")),
        "peso_destacado": _peso_destacado(log.get("pesos")),
        "dia_rutina": log.get("dia_rutina"),
        "created_at": log.get("created_at") or log.get("updated_at") or "",
    }


# Las once respuestas de un cierre, tal cual se guardaron. La pantalla las nombra y las
# pinta; aqui solo se recogen, para que el Diario pueda enseñar el dia entero y no solo lo
# que se escribio a mano.
CAMPOS_DEL_DIA = (
    "sensaciones", "entreno_respuesta", "entreno_estrellas", "cardio", "movimiento",
    "suplementos", "extras_respuesta", "descanso", "energy", "hunger_anxiety",
    "nutrition_followed", "weight", "peso_fecha", "cena_hecha", "comida_pendiente",
    "exceso_nota", "mood", "trained",
)


def _resumen_del_dia(checkin: Dict[str, Any]) -> Dict[str, Any]:
    """Lo contestado ese dia, sin los campos vacios: la linea del historial y su detalle."""
    return {campo: checkin[campo] for campo in CAMPOS_DEL_DIA
            if checkin.get(campo) is not None}


def _entrada_del_dia(checkin: Dict[str, Any], solo_compartidas: bool = False) -> Dict[str, Any]:
    notas = checkin.get("notas") or {}
    texto = notas.get("texto")
    compartida = bool(notas.get("compartida"))
    # La regla de siempre, tambien cuando la fila entro a la lista por su nota de entreno:
    # al equipo una nota personal no compartida no le llega ni vacia de contenido. Lo que
    # queda entonces (la nota de entreno) si es para el equipo, y la entrada servida se
    # marca como tal: la marca habla de lo que va dentro, no de lo que se quito.
    if solo_compartidas and not compartida:
        texto = None
        compartida = True
    return {
        "tipo": "dia",
        # Los cierres nuevos traen `dia` (el dia del cliente); los viejos, solo el
        # created_at en UTC, y de ahi se saca la fecha para que no se queden sin ordenar.
        "fecha": checkin.get("dia") or str(checkin.get("created_at") or "")[:10],
        "texto": texto,
        "estrellas": None,
        "compartida": compartida,
        "peso_destacado": None,
        "dia_rutina": None,
        # La nota de entreno del cierre (P80, doc 23-08): quien no tiene rutina apunta ahi
        # su entreno, y "cae todo lo que escribe" incluye eso. No lleva marca de privacidad
        # porque es la respuesta a una pregunta nuestra: el equipo ya la ve en el check-in.
        "entreno_nota": checkin.get("entreno_nota"),
        # LO QUE CONTESTO ESE DIA, para poder pintar la linea del historial sin volver a
        # pedir los check-ins (punto 19 del doc 24-08: "Lun 24 · estrellas · Entreno si ·
        # Dieta si · 96 kg"). Va aparte y no suelto en la entrada para que lo que ya lee
        # el Diario de hoy siga leyendose igual.
        "dia_resumen": _resumen_del_dia(checkin),
        "created_at": checkin.get("created_at") or "",
    }


async def _componer(client_id: str, solo_compartidas: bool, skip: int, limit: int) -> Dict[str, Any]:
    """Las dos fuentes en una sola lista, de lo mas nuevo a lo mas viejo.

    Se piden de cada coleccion los que harian falta para llenar hasta esta pagina y uno
    mas: con eso se sabe si hay siguiente sin contar las dos colecciones enteras.
    """
    hasta = skip + limit + 1

    filtro_logs: Dict[str, Any] = {"client_id": client_id, "nota": {"$nin": [None, ""]}}
    con_texto = {"$nin": [None, ""]}
    if solo_compartidas:
        filtro_logs["compartida"] = True
        # AL EQUIPO, SOLO LO ESCRITO Y SOLO LO SUYO. Las notas personales si van
        # compartidas; la nota de entreno siempre, que es la respuesta a nuestra pregunta y
        # ya la ve en el check-in. Sus dias enteros el equipo los tiene en la ficha del
        # cliente: meterlos aqui llenaria el Diario del coach de lineas sin una palabra
        # escrita, que es justo lo contrario de para lo que lo abre.
        filtro_checkins: Dict[str, Any] = {
            "client_id": client_id,
            "$or": [
                {"notas.texto": con_texto, "notas.compartida": True},
                {"entreno_nota": con_texto},
            ],
        }
    else:
        # AL CLIENTE, DE MOMENTO, SOLO LOS DIAS CON ALGO ESCRITO. Un cierre entra al Diario
        # por su nota personal O por su nota de entreno (P80): el que no tiene rutina apunta
        # ahi su entreno y eso tambien es "lo que escribe".
        #
        # AQUI SE PROBO A TRAER TODOS LOS DIAS (punto 23, «el Diario y el historial en un
        # solo sitio») y se deshizo el mismo dia: quien pinta esto es
        # `components/Diario.jsx`, que de una entrada solo sabe enseñar la fecha, el texto y
        # la nota de entreno. Con todos los dias dentro, al que cierra a diario le salian
        # veinte tarjetas con la fecha y NADA debajo. La lista entera es de verdad lo que
        # pide el punto 23, pero el traslado va junto: la vista de dia (`dia_resumen`, que
        # ya viaja aqui abajo) tiene que estar pintada ANTES de abrir el filtro. Cuando lo
        # este, esto es esta linea y nada mas.
        filtro_checkins = {
            "client_id": client_id,
            "$or": [{"notas.texto": con_texto}, {"entreno_nota": con_texto}],
        }

    logs = await db.workout_logs.find(filtro_logs, {"_id": 0}).sort("fecha", -1).to_list(hasta)
    checkins = await db.checkins.find(filtro_checkins, {"_id": 0}).sort("created_at", -1).to_list(hasta)

    entradas = [_entrada_de_entreno(l) for l in logs] + [_entrada_del_dia(c, solo_compartidas) for c in checkins]
    # Por dia y, dentro del mismo dia, por la hora a la que se escribio: el entreno de la
    # mañana y el cierre de la noche del mismo dia tienen que salir en ese orden.
    entradas.sort(key=lambda e: (str(e.get("fecha") or ""), str(e.get("created_at") or "")), reverse=True)

    pagina = entradas[skip:skip + limit]
    return {"entradas": pagina, "hay_mas": len(entradas) > skip + limit}


@router.get("/diary")
async def mi_diario(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=LIMITE_MAXIMO),
    user=Depends(get_current_user),
):
    """El diario del propio cliente: lo suyo entero, privado y compartido."""
    await _exige_pantalla_encendida()
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    return await _componer(profile["id"], solo_compartidas=False, skip=skip, limit=limit)


@router.get("/admin/clients/{client_id}/diary")
async def diario_del_cliente(
    client_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=LIMITE_MAXIMO),
    user=Depends(get_admin_user),
):
    """El diario de un cliente para el equipo: SOLO las entradas compartidas.

    La regla del doc ("tu solo ves las compartidas") se cumple aqui y no en la pantalla:
    lo privado no sale de la base. El acceso al cliente sigue la regla de siempre (admin =
    todos; trainer = los suyos).
    """
    await _exige_pantalla_encendida()
    profile = await db.client_profiles.find_one({"id": client_id}, {"_id": 0, "id": 1, "trainer_id": 1})
    assert_client_access(user, profile)
    return await _componer(client_id, solo_compartidas=True, skip=skip, limit=limit)
