"""
Ciclo del cliente: la semana del ciclo se CALCULA a partir de la fecha de inicio
(`cycle_start`, o `created_at` como respaldo) y la duración del plan, en vez de ser
un contador estático. Así avanza sola con el tiempo sin necesidad de un cron.

- Planes con ciclo fijo (ej. 12 semanas): la semana va 1..N y, al terminar, arranca
  un nuevo ciclo (week vuelve a 1, cycle_number +1). Encaja con planes que renuevan.
- Planes mensuales indefinidos (semanas=None): la semana cuenta desde el inicio, sin tope.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from models.user import PLAN_CATALOG


def _parse_dt(value) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def compute_cycle(profile: Dict[str, Any], now: Optional[datetime] = None) -> Dict[str, Any]:
    """Devuelve {week, cycle_number, cycle_total_weeks, cycle_start} para un perfil."""
    now = now or datetime.now(timezone.utc)
    plan = PLAN_CATALOG.get((profile.get("plan") or "").lower().strip()) or {}
    ciclo = plan.get("ciclo") or {}
    total = ciclo.get("semanas")
    # LOS PLANES MENSUALES TAMBIEN TIENEN CICLO, Y ES DE CUATRO SEMANAS (Francisco, 25-08).
    #
    # Solo se miraba `ciclo.semanas`, que en los mensuales es None, asi que no habia modulo
    # y la semana SUBIA SIN PARAR: a un cliente de El Lunes Empiezo -- que se cobra cada 28
    # dias -- la app le decia «Estas en la semana 8», un numero que no significaba nada y
    # que iba a seguir creciendo para siempre.
    #
    # Se coge de `billing_cycle_weeks`, que es lo que de verdad se le cobra, y SOLO en los
    # mensuales: los cinco complementos de pago unico (rutina del mes, revision...) no son
    # un ciclo, y los «variable» -- Premium y entrenamiento personal -- llevan 4 en ese
    # campo por defecto pero en la practica van a 84 dias, asi que decirles «semana 3 de 4»
    # seria cambiar un numero sin sentido por otro.
    if not total and ciclo.get("tipo") == "mensual":
        total = plan.get("billing_cycle_weeks")

    anchor = _parse_dt(profile.get("cycle_start")) or _parse_dt(profile.get("created_at")) or now
    # UN CICLO PAGADO POR ADELANTADO NO EMPIEZA HASTA QUE EMPIEZA (25-08).
    #
    # Desde hoy la renovacion escribe `cycle_start` con el arranque del ciclo pagado, y el
    # que renueva ANTES de vencer encadena: su ciclo nuevo arranca donde acaba el viejo, o
    # sea en el futuro. Con esa ancla por delante, `days` se quedaba a 0 por el `max` de
    # abajo y al cliente le salia «semana 1» varios dias antes de tiempo, cuando en
    # realidad esta acabando el anterior. Mientras no llegue, se cuenta desde el ciclo de
    # antes, que es donde esta de verdad.
    if total and total > 0 and anchor > now:
        anchor = anchor - timedelta(weeks=total)
    # LOS DIAS SE CUENTAN EN HORA DE ESPAÑA, no en UTC.
    #
    # Restando los instantes en UTC, entre las 22:00 y las 00:00 de aqui -- que en Madrid ya
    # son del dia siguiente -- el cliente seguia en la semana anterior. Se ve en el cambio de
    # semana: a las 00:30 del lunes en Madrid la app decia que aun era la semana pasada, y de
    # esa semana salen el reporte que le toca, su ventana y sus avisos. Contando los DIAS de
    # calendario en España, la semana cambia cuando le cambia a el.
    from core.tiempo import a_madrid
    days = max(0, ((a_madrid(now) or now).date() - (a_madrid(anchor) or anchor).date()).days)
    weeks_elapsed = days // 7  # 0-based

    if total and total > 0:
        week = (weeks_elapsed % total) + 1
        cycle_number = (weeks_elapsed // total) + 1
    else:
        week = weeks_elapsed + 1
        cycle_number = 1

    return {
        "week": week,
        "cycle_number": cycle_number,
        "cycle_total_weeks": total,
        "cycle_start": anchor.isoformat(),
    }


def enrich_cycle(profile: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Rellena week/cycle_number/cycle_total_weeks calculados sobre el perfil (in place)."""
    if not profile:
        return profile
    c = compute_cycle(profile)
    profile["week"] = c["week"]
    profile["cycle_number"] = c["cycle_number"]
    profile["cycle_total_weeks"] = c["cycle_total_weeks"]
    if not profile.get("cycle_start"):
        profile["cycle_start"] = c["cycle_start"]
    return profile
