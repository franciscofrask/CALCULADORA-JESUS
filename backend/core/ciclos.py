"""
EL CUADERNO DE CICLOS (doc de Jesús del 2-09, fase 1; Francisco, 4-09: «cuando renueva no
podemos perder el ciclo anterior»).

Hasta hoy el ciclo de un cliente era UN campo, `client_profiles.cycle_start`, que la
renovación pisa con la fecha nueva (core/stripe_billing.py) y el panel reinicia al dar plan
a quien no tenía (routes/admin.py). Del ciclo anterior no quedaba nada: ni cuándo empezó, ni
cuándo acabó, ni por qué. Y de ahí cuelga medio documento de Jesús: «fin del ciclo
anterior», las fotos y los puntos de control agrupados por ciclo, el objetivo del ciclo.

Esto es el cuaderno: la colección `ciclos`, una fila por ciclo y cliente. Se ESCRIBE en el
momento en que el ciclo arranca (la pizarra de `cycle_start` se sigue escribiendo igual;
esto va además, nunca en su lugar) y de lo anterior a este código solo se apunta el ciclo
que estaba abierto, con motivo `registro_inicial`: los de antes no se escribieron nunca y
no se inventan (decisión de Francisco, 4-09: «empezar a contar con las nuevas y dejar como
pendiente las que ya existen»).

Reglas que hay que respetar al enganchar esto:
  - El cuaderno es secundario: si falla, la ficha se actualiza igual. Quien llama envuelve
    la llamada en try/except y solo deja aviso, como hace `anotar_cobro_en_historicos`.
  - Es idempotente por (cliente, día de inicio): los avisos de Stripe se repiten (un
    `customer.subscription.updated` llega varias veces con el mismo periodo) y no pueden
    abrir dos veces el mismo ciclo.
  - Los días son DÍAS DE ESPAÑA, no instantes ni días del reloj del cliente: el ciclo es un
    plazo del negocio (core/cycle.py cuenta en hora de Madrid; y desde Argentina las 00:00
    del lunes caen en el domingo).
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union

from pymongo.errors import DuplicateKeyError

from core.cycle import compute_cycle
from core.database import db
from core.tiempo import a_madrid

logger = logging.getLogger(__name__)

COLECCION = "ciclos"

# Motivos por los que arranca un ciclo. Los dos primeros los pide el doc de Jesús («el alta y
# la vuelta»); `renovacion` es el de cada renovación pegada a la anterior.
MOTIVOS = ("alta", "renovacion", "vuelta", "registro_inicial")
# Si el ciclo nuevo arranca como mucho esta cantidad de días después de acabar el anterior,
# es una renovación; más lejos, el cliente paró y ha vuelto.
DIAS_DE_GRACIA_PARA_RENOVAR = 7
# Un bloque son cuatro semanas, un reporte (doc de Jesús del 2-09).
SEMANAS_POR_BLOQUE = 4


def dia_de_espana(valor: Union[datetime, date, str, None]) -> Optional[str]:
    """Un instante, un día o un ISO a 'YYYY-MM-DD' en el calendario de España.

    Un día suelto («2026-08-24») se devuelve tal cual: ya es un día del calendario y pasarlo
    por una zona horaria le restaría un día a medio mundo."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        madrid = a_madrid(valor)
        return (madrid or valor).date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    texto = str(valor).strip()
    if len(texto) == 10 and texto[4] == "-" and texto[7] == "-":
        return texto
    madrid = a_madrid(texto)
    return madrid.date().isoformat() if madrid else None


def _sumar_dias(dia: str, n: int) -> str:
    return (date.fromisoformat(dia) + timedelta(days=n)).isoformat()


def _dias_entre(desde: str, hasta: str) -> int:
    return (date.fromisoformat(hasta) - date.fromisoformat(desde)).days


def semanas_del_plan(profile: Dict[str, Any]) -> Optional[int]:
    """La duración del ciclo en semanas según su plan (la misma regla que la semana viva)."""
    return compute_cycle(profile).get("cycle_total_weeks")


def inicio_del_ciclo_vigente(profile: Dict[str, Any]) -> Optional[str]:
    """El día en que arrancó el ciclo que el cliente tiene abierto HOY, contado como lo
    cuenta la semana viva (compute_cycle).

    No es siempre `cycle_start` (4-09, al preparar el registro inicial). Cuando el ancla se
    quedó vieja y el plan ya dio la vuelta -- en dev, 48 de las 176 fichas con ancla la
    tienen en un ciclo que según su plan acabó hace tiempo --, compute_cycle sigue contando
    en módulo («semana 3 del ciclo 2») y el ciclo abierto hoy es el que empezó `total`
    semanas después del ancla, tantas vueltas como hayan pasado. Apuntar `cycle_start` a
    secas dejaría en el cuaderno un ciclo abierto con el fin previsto ya pasado, y
    `ciclo_de` diría «semana 15» donde la app dice «semana 3». Un ancla en el futuro
    (renovó antes de vencer y encadena) se devuelve tal cual: ese día sí es el que arranca."""
    inicio = dia_de_espana((profile or {}).get("cycle_start"))
    if not inicio:
        return None
    calculado = compute_cycle(profile)
    total = calculado.get("cycle_total_weeks")
    vuelta = calculado.get("cycle_number") or 1
    if total and vuelta > 1:
        return _sumar_dias(inicio, (vuelta - 1) * total * 7)
    return inicio


async def ciclo_abierto(client_id: str) -> Optional[Dict[str, Any]]:
    """El ciclo sin cerrar del cliente, si lo hay (el más reciente por si hubiera dos)."""
    return await db[COLECCION].find_one(
        {"client_id": client_id, "fin": None}, {"_id": 0}, sort=[("inicio", -1)])


async def ciclos_de(client_id: str) -> list[Dict[str, Any]]:
    """Todos los ciclos del cliente, del más antiguo al de hoy."""
    return await db[COLECCION].find({"client_id": client_id}, {"_id": 0}).sort("inicio", 1).to_list(1000)


def _motivo_por_defecto(anterior: Optional[Dict[str, Any]], inicio: str) -> str:
    if not anterior:
        return "alta"
    fin_anterior = anterior.get("fin") or anterior.get("fin_previsto")
    if fin_anterior and _dias_entre(fin_anterior, inicio) <= DIAS_DE_GRACIA_PARA_RENOVAR + 1:
        return "renovacion"
    return "vuelta"


async def abrir_ciclo(profile: Dict[str, Any], *, inicio, origen: str, motivo: Optional[str] = None,
                      plan: Optional[str] = None, semanas: Optional[int] = None,
                      numero: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Apunta en el cuaderno que arranca un ciclo y cierra el que estuviera abierto.

    `inicio` puede ser un instante o un día; se guarda como día de España. Si ya hay un
    ciclo de ese cliente con ese mismo inicio, se devuelve ese y no se escribe nada (así los
    avisos repetidos de Stripe no duplican). Devuelve el ciclo (nuevo o ya existente) o
    None si no había con qué (perfil sin id o inicio ilegible)."""
    client_id = (profile or {}).get("id")
    dia_inicio = dia_de_espana(inicio)
    if not client_id or not dia_inicio:
        return None

    ya = await db[COLECCION].find_one({"client_id": client_id, "inicio": dia_inicio}, {"_id": 0})
    if ya:
        return ya

    if semanas is None:
        semanas = semanas_del_plan({**profile, **({"plan": plan} if plan else {})})
    plan = plan or profile.get("plan")
    fin_previsto = _sumar_dias(dia_inicio, semanas * 7 - 1) if semanas else None

    anteriores = await ciclos_de(client_id)
    abierto = next((c for c in reversed(anteriores) if not c.get("fin")), None)
    ultimo = anteriores[-1] if anteriores else None
    if motivo not in MOTIVOS:
        motivo = _motivo_por_defecto(ultimo, dia_inicio)
    # El número sigue al del último apuntado, no a cuántas filas hay: el registro inicial
    # puede entrar con el número que la app ya le enseña al cliente («ciclo 3»), y el
    # siguiente tiene que ser el 4, no el 2.
    if not numero:
        numero = (ultimo.get("numero") or len(anteriores)) + 1 if ultimo else 1

    ahora = datetime.now(timezone.utc).isoformat()
    # El que estaba abierto se cierra: en su fin previsto si ya había pasado (el cliente
    # paró y ha vuelto), y si no, el día antes de que arranque el nuevo (renovó encadenando,
    # o antes de tiempo). Nunca se deja un ciclo abierto encima de otro.
    if abierto:
        fin_previsto_ant = abierto.get("fin_previsto")
        vispera = _sumar_dias(dia_inicio, -1)
        fin = fin_previsto_ant if fin_previsto_ant and fin_previsto_ant < vispera else vispera
        if fin < abierto["inicio"]:
            fin = abierto["inicio"]
        await db[COLECCION].update_one({"id": abierto["id"]}, {"$set": {"fin": fin, "cerrado_at": ahora}})

    ciclo = {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "user_id": profile.get("user_id"),
        "numero": numero,
        "inicio": dia_inicio,
        "fin": None,
        "fin_previsto": fin_previsto,
        "semanas": semanas,
        "plan": plan,
        "motivo": motivo,
        "origen": origen,
        # Fase 2 del doc: el objetivo del ciclo lo pone el entrenador al abrirlo. Nace con
        # el objetivo ACTUAL de la ficha (`client_profiles.objetivo_actual`), que es el que
        # el entrenador ya tenía puesto; si después lo cambia, va por
        # PUT /admin/clients/{id}/objetivo con `objetivo_ciclo` (Francisco, 4-09).
        "objetivo": (profile or {}).get("objetivo_actual"),
        # Fase 3: el pico de forma, uno por ciclo, marcado desde el panel al contestar un
        # reporte. Se guarda aquí el id del reporte que lo lleva.
        "pico_de_forma": None,
        "created_at": ahora,
        "cerrado_at": None,
    }
    try:
        await db[COLECCION].insert_one(dict(ciclo))
    except DuplicateKeyError:
        # Dos avisos a la vez del mismo periodo: el índice único (cliente, inicio) cierra la
        # carrera y el que perdió devuelve el que ya está.
        return await db[COLECCION].find_one({"client_id": client_id, "inicio": dia_inicio}, {"_id": 0})
    return ciclo


async def registrar_ciclo_vigente(profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Lo único que se salva de antes de este código: el ciclo que el cliente tiene ABIERTO
    hoy, que sí sabemos cuándo empezó (`cycle_start`, o la vuelta que toque de él si el
    ancla es vieja: `inicio_del_ciclo_vigente`). Si el cliente ya tiene algo en el
    cuaderno, no se toca. Motivo `registro_inicial`, para que se distinga de los que nacen
    de una renovación de verdad."""
    client_id = (profile or {}).get("id")
    inicio = inicio_del_ciclo_vigente(profile)
    if not client_id or not inicio:
        return None
    if await db[COLECCION].find_one({"client_id": client_id}, {"_id": 1}):
        return None
    # Con el número que la app ya le enseña (compute_cycle): para el que renueva por Stripe
    # el ancla se reescribe en cada renovación y sale 1 aunque lleve años; no es mentira
    # nueva, es la misma que ya ve, y se corregirá cuando se reconstruya lo anterior.
    return await abrir_ciclo(profile, inicio=inicio, origen="script", motivo="registro_inicial",
                             numero=compute_cycle(profile).get("cycle_number") or 1)


def _bloque(semana: Optional[int]) -> Optional[int]:
    return (semana - 1) // SEMANAS_POR_BLOQUE + 1 if semana else None


def _instante_de(dia: str) -> datetime:
    """El mediodía de ese día en UTC, para preguntarle a compute_cycle por un día concreto
    sin caer en el cambio de fecha."""
    return datetime.fromisoformat(dia).replace(hour=12, tzinfo=timezone.utc)


async def ciclo_de(profile: Dict[str, Any], dia: Union[datetime, date, str, None] = None) -> Dict[str, Any]:
    """A qué ciclo, semana y bloque pertenece un día del cliente. Para CONGELARLO en lo
    que se escribe ese día (una foto, un reporte), porque después el ancla se habrá pisado.

    Primero mira el cuaderno; si el día no cae en ningún ciclo apuntado (clientes sin
    cuaderno todavía, o un día anterior a lo registrado), lo calcula como lo hace la
    semana viva (compute_cycle) y lo dice con `ciclo_id: None`.

    Devuelve siempre las cinco claves, con None donde no se sabe:
      ciclo_id, ciclo_numero, ciclo_inicio, semana_del_ciclo, bloque."""
    vacio = {"ciclo_id": None, "ciclo_numero": None, "ciclo_inicio": None,
             "semana_del_ciclo": None, "bloque": None}
    client_id = (profile or {}).get("id")
    dia_es = dia_de_espana(dia) or dia_de_espana(datetime.now(timezone.utc))
    if not client_id or not dia_es:
        return vacio

    apuntado = await db[COLECCION].find_one(
        {"client_id": client_id, "inicio": {"$lte": dia_es},
         "$or": [{"fin": None}, {"fin": {"$gte": dia_es}}]},
        {"_id": 0}, sort=[("inicio", -1)])
    if apuntado:
        semana = _dias_entre(apuntado["inicio"], dia_es) // 7 + 1
        return {"ciclo_id": apuntado["id"], "ciclo_numero": apuntado.get("numero"),
                "ciclo_inicio": apuntado["inicio"], "semana_del_ciclo": semana, "bloque": _bloque(semana)}

    if not (profile.get("cycle_start") or profile.get("created_at")):
        return vacio
    calculado = compute_cycle(profile, now=_instante_de(dia_es))
    inicio = dia_de_espana(calculado.get("cycle_start"))
    semana = calculado.get("week")
    return {"ciclo_id": None, "ciclo_numero": calculado.get("cycle_number"),
            "ciclo_inicio": inicio, "semana_del_ciclo": semana, "bloque": _bloque(semana)}
