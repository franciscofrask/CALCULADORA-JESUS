"""
Las dos fechas que contestan "¿a quien le toca esta semana?" (punto 29 del doc del 07-08).

Es la pregunta que Jesus se hace todos los lunes y que hoy resuelve mirando una hoja de
calculo aparte. La respuesta esta en la base, pero repartida en dos colecciones
(`macro_history` y `reports`) y con mas de doscientos clientes: recorrer el historico de
todos para pintar una tabla no se sostiene, y por eso no existia la columna.

Asi que estas dos fechas se guardan TAMBIEN en el cliente, a proposito duplicadas, y se
refrescan cada vez que se guarda. La lista de clientes ordena por ellas sin tocar el
historico, y de ahi sale el bloque de la home: "esta semana te tocan estos seis".

  ultimo_ajuste  - cuando se le movieron los macros por ultima vez (lo haga quien lo haga)
  ultimo_reporte - cuando mando su ultimo reporte

Las dos son AAAA-MM-DD. Nunca van hacia atras: si llega una fecha mas antigua que la
guardada -- porque se corrige una entrada vieja del historial -- se ignora. La que vale es
la ultima vez que paso algo, no la ultima vez que alguien edito algo.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from core.database import db


def _dia(valor: Optional[str] = None) -> str:
    """AAAA-MM-DD a partir de una fecha ISO (o de hoy si no viene ninguna).

    El «hoy» de repuesto es el de ESPAÑA (bloque F, 23-08): con UTC, un ajuste de
    madrugada quedaba fechado en ayer y descolocaba el «a quién le toca esta semana»."""
    if not valor:
        from core.tiempo import hoy_madrid
        return hoy_madrid().isoformat()
    return str(valor)[:10]


async def _adelantar(client_id: Optional[str], campo: str, fecha: Optional[str]) -> None:
    """Deja `campo` en `fecha` si es mas reciente que lo que hubiera (o no habia nada)."""
    if not client_id:
        return
    dia = _dia(fecha)
    await db.client_profiles.update_one(
        {"id": client_id, "$or": [{campo: {"$lt": dia}}, {campo: None}, {campo: {"$exists": False}}]},
        {"$set": {campo: dia}},
    )


async def marcar_ajuste(client_id: Optional[str], fecha: Optional[str] = None) -> None:
    """Se le acaban de mover los macros.

    `fecha` es la de VIGENCIA del ajuste (`effective_date`), no la de la fila. Los que
    llamaban pasaban `created_at`, y por eso a los 159 clientes migrados les quedo aqui la
    fecha de la importacion en vez de la de su ultimo ajuste: medido el 12-08, este campo no
    coincidia con el historial en 184 de 185 perfiles, y en la mayoria estaba vacio. Es el
    campo por el que el panel ordena «esta semana te tocan estos», o sea que la primera
    pantalla del lunes senalaba a otros (caso 80 de la lista de Jesus).
    """
    await _adelantar(client_id, "ultimo_ajuste", fecha)


def fecha_de_vigencia(macro_log: dict) -> str:
    """La fecha con la que se marca un ajuste: la de vigencia, y si no la de guardado."""
    return _dia((macro_log or {}).get("effective_date") or (macro_log or {}).get("created_at"))


async def marcar_reporte(client_id: Optional[str], fecha: Optional[str] = None) -> None:
    """Acaba de mandar un reporte."""
    await _adelantar(client_id, "ultimo_reporte", fecha)


#: Cuánto puede mirar atrás el feedback de un ajuste para encontrar su reporte. Más allá,
#: ese reporte ya no es al que se está contestando: es historia.
DIAS_PARA_ENGANCHAR_EL_FEEDBACK = 45


async def feedback_al_informe(client_id: Optional[str], texto: Optional[str],
                              firmante: Optional[str] = None) -> Optional[str]:
    """Lleva al informe el feedback que el coach escribe al ajustar los macros.

    EL AGUJERO QUE CIERRA (revisión del 2-09). El formulario de ajuste pide «Feedback para
    el cliente (obligatorio)» y ese texto llegaba al aviso de la campanita y a Mis macros,
    pero `reports.trainer_feedback` nacía en None y no lo escribía NADIE: el informe del mes
    se quedaba con el hueco en gris y su «en estos momentos estamos revisando tu reporte
    mensual», que es justo donde al cliente se le ha prometido leerlo.

    A QUÉ REPORTE VA: al último suyo que aún no tenga feedback, y solo si es reciente
    (`DIAS_PARA_ENGANCHAR_EL_FEEDBACK`). No se pisa un feedback ya escrito -- eso sería
    borrar lo que el coach redactó a mano en el informe -- y no se rellena un reporte viejo,
    porque un ajuste de hoy no contesta a un reporte de hace medio año.

    Devuelve el id del reporte que quedó completado, o None si no había ninguno al que
    contestar. Falla en silencio como el resto de este módulo: el ajuste tiene que guardarse
    aunque esto no encuentre reporte.
    """
    escrito = (texto or "").strip()
    if not client_id or not escrito:
        return None
    try:
        desde = (datetime.now(timezone.utc) - timedelta(days=DIAS_PARA_ENGANCHAR_EL_FEEDBACK)).isoformat()
        reporte = await db.reports.find_one(
            {"client_id": client_id,
             "created_at": {"$gte": desde},
             "$or": [{"trainer_feedback": None}, {"trainer_feedback": ""},
                     {"trainer_feedback": {"$exists": False}}]},
            {"_id": 0, "id": 1}, sort=[("created_at", -1)])
        if not reporte:
            return None
        ahora = datetime.now(timezone.utc).isoformat()
        await db.reports.update_one(
            {"id": reporte["id"]},
            {"$set": {"trainer_feedback": escrito,
                      # La fecha con la que el informe lo firma. El estado NO se toca: que
                      # el informe se dé por «entregado» sigue siendo una decisión suya, en
                      # su botón de publicar.
                      "informe_publicado_at": ahora,
                      "feedback_de": firmante or None,
                      "feedback_origen": "ajuste de macros"}})
        return reporte["id"]
    except Exception:
        return None


def dias_desde(fecha: Optional[str], ahora: Optional[datetime] = None) -> Optional[int]:
    """Dias enteros desde una de estas fechas. None si no hay fecha o no se entiende."""
    if not fecha:
        return None
    try:
        d = datetime.strptime(str(fecha)[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None
    return max(0, ((ahora or datetime.now(timezone.utc)) - d).days)
