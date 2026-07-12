"""
Ciclo del cliente: la semana del ciclo se CALCULA a partir de la fecha de inicio
(`cycle_start`, o `created_at` como respaldo) y la duración del plan, en vez de ser
un contador estático. Así avanza sola con el tiempo sin necesidad de un cron.

- Planes con ciclo fijo (ej. 12 semanas): la semana va 1..N y, al terminar, arranca
  un nuevo ciclo (week vuelve a 1, cycle_number +1). Encaja con planes que renuevan.
- Planes mensuales indefinidos (semanas=None): la semana cuenta desde el inicio, sin tope.
"""
from datetime import datetime, timezone
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
    total = (plan.get("ciclo") or {}).get("semanas")

    anchor = _parse_dt(profile.get("cycle_start")) or _parse_dt(profile.get("created_at")) or now
    days = max(0, (now - anchor).days)
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
