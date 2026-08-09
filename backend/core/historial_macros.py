"""
UNA fila por (cliente, fecha de vigencia) en `macro_history`. Punto 62 del doc del 07-08.

El historial de macros lo escriben seis sitios distintos: el formulario de la ficha, la
calculadora del coach, la calculadora del cliente, el cuestionario de alta, el de ajuste y
la edicion del perfil. Los seis hacian `insert_one`, asi que cada guardado dejaba una fila
nueva. Guardar dos veces el mismo dia -- que es lo normal: se calcula, se mira, se toca un
numero y se vuelve a guardar -- dejaba dos filas con la misma fecha de vigencia.

Lo que ve el entrenador en produccion:

    30/06/2026  82 kg  230-330-70 | 15-20 | 240-260-80   x4 identicas
    30/06/2026  80 kg  140- 60-60 | 30-30 | 150- 40-70

Cinco filas para un dia en el que hubo UN ajuste. Medido el 09-08 sobre prod: 25 dias con
mas de una fila, 92 filas de mas, y las firmas `changed_by` son nombres de clientes -- o
sea, la calculadora del cliente guardando varias veces seguidas.

Y no es solo ruido visual. `macros_por_fecha.resolver()` elige la entrada vigente de un dia;
con cinco candidatas para la misma fecha, cual gana depende del orden en que las devuelva
Mongo. El mismo dia podia salir con macros distintos segun quien preguntase.

La regla, que es la que pidio Jesus:

  - Una fila por (cliente, fecha de vigencia). La ultima manda: es una correccion, no dos
    ajustes. Misma regla que las series de peso (`core/series_cliente.py`), donde ya
    decidimos que dos pesajes el mismo dia son una correccion.

  - El rastro NO se pierde: la fila que se sustituye se copia entera a
    `macro_history_auditoria`. Si algun dia hay que saber quien escribio que y cuando, esta
    ahi. Lo que no puede es vivir en el historico que mira el entrenador.

  - El "de donde venia" se conserva. Si a las 19:41 se pasa de 200 a 230 y a las 19:45 de
    230 a 240, la fila que queda tiene que decir "de 200 a 240", no "de 230 a 240": el
    estado de las 19:41 nunca existio para nadie mas que para el que estaba tecleando. Por
    eso se arrastran los `previous_*` de la fila sustituida y se recalcula `cambios`.

El indice unico parcial (`core/database.py`) es el cinturon: cierra tambien la carrera de
dos guardados simultaneos, que el upsert por si solo no cierra.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.cambios_macros import marcar_cambios
from core.database import db

# Donde van a parar las filas sustituidas. Aparte a proposito: es un registro de auditoria,
# no historial clinico, y nadie lo pinta en pantalla.
COLECCION_AUDITORIA = "macro_history_auditoria"


def fecha_de_vigencia(macro_log: Dict[str, Any]) -> Optional[str]:
    """La fecha desde la que aplica el ajuste, 'YYYY-MM-DD'.

    `effective_date` si esta; si no, el dia de `created_at`. Es la misma cadena que usa
    `macros_por_fecha.resolver()` para elegir la entrada vigente, y por eso es la clave.
    """
    for campo in ("effective_date", "created_at"):
        v = str(macro_log.get(campo) or "")[:10]
        if len(v) == 10 and v[4] == "-":
            return v
    return None


def _con_lo_de_antes(nuevo: Dict[str, Any], anterior: Dict[str, Any]) -> Dict[str, Any]:
    """`nuevo` arrastrando el "de donde venia" de la fila que sustituye."""
    for campo in ("previous_training", "previous_rest", "previous_peri", "previous_periworkout"):
        if campo in anterior:
            nuevo[campo] = anterior.get(campo)

    # `cambios` se recalcula: comparado con el estado real anterior, no con el intermedio.
    antes = {"entreno": nuevo.get("previous_training"),
             "perientreno": nuevo.get("previous_peri") or nuevo.get("previous_periworkout"),
             "descanso": nuevo.get("previous_rest")}
    if any(isinstance(v, dict) for v in antes.values()):
        nuevo["cambios"] = marcar_cambios(antes, {
            "entreno": nuevo.get("training") or nuevo.get("new_training"),
            "perientreno": nuevo.get("peri") or nuevo.get("macros_periworkout"),
            "descanso": nuevo.get("rest") or nuevo.get("new_rest"),
        })

    # Cuando el ajuste que se sustituye venia de una sugerencia de la IA y el nuevo no, la
    # trazabilidad de la sugerencia se quedaria huerfana. Se conserva.
    for campo in ("sugerencia_id", "sugerencia_propuesta"):
        if campo in anterior and campo not in nuevo:
            nuevo[campo] = anterior.get(campo)
    return nuevo


async def guardar(macro_log: Dict[str, Any]) -> Dict[str, Any]:
    """Deja `macro_log` como LA fila de ese cliente para esa fecha de vigencia.

    Si ya habia una, se archiva en `macro_history_auditoria` y esta la sustituye. Devuelve
    el documento tal y como queda guardado.
    """
    client_id = macro_log.get("client_id")
    fecha = fecha_de_vigencia(macro_log)

    # Sin clave no hay nada que deduplicar: se guarda y punto. No deberia pasar (los seis
    # caminos ponen client_id), pero perder un ajuste por una clave incompleta seria peor
    # que dejar un duplicado.
    if not client_id or not fecha:
        await db.macro_history.insert_one(macro_log)
        return macro_log

    macro_log["effective_date"] = fecha
    clave = {"client_id": client_id, "effective_date": fecha}

    anterior = await db.macro_history.find_one(clave)
    if anterior:
        archivo = dict(anterior)
        archivo.pop("_id", None)
        archivo["sustituida_at"] = datetime.now(timezone.utc).isoformat()
        archivo["sustituida_por"] = macro_log.get("id")
        await db[COLECCION_AUDITORIA].insert_one(archivo)
        macro_log = _con_lo_de_antes(macro_log, anterior)
        await db.macro_history.replace_one({"_id": anterior["_id"]}, macro_log)
    else:
        await db.macro_history.insert_one(macro_log)
    return macro_log
