"""
Nada con fecha de mañana cuenta como pasado. Punto 22 del doc del 07-08.

En produccion hay 31 reportes y 37 entradas de macros fechados por delante de hoy: 2026-09,
2026-11, 2027, 2028, 2029. Medido el 09-08-2026, y casi todos son de la importacion de
Calma (`calma_migrated: true`, nota "Importado de Calma") sobre el perfil del propio Jesus,
que es cliente de si mismo. Un dia sin año en el origen se convirtio en un dia de este año
que todavia no ha llegado.

Ordenar por fecha a secas hacia que ganara uno de esos. Sintomas que ya se han visto:

  - Reportes decia «Ultimo: 118 kg · 21 feb» -- de un reporte de 2028 -- mientras Ajustar
    macros decia 94 kg. Ese es el punto 9: dos pesos distintos en la misma app.
  - El historial de reportes empieza por un reporte de noviembre. Ese es el punto 22.

La regla, la misma que ya vale para las series de peso (`core/series_cliente.actual()`): un
dato del futuro no es el dato de nadie. No se borra -- adivinar el año bueno seria
inventarselo -- pero no se enseña como historia ni se usa para calcular.

    reports = await db.reports.find(hasta_hoy({"client_id": cid})) ...
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def ahora() -> str:
    """El instante de corte, en ISO, comparable con lo que guarda la app."""
    return datetime.now(timezone.utc).isoformat()


def hasta_hoy(filtro: Optional[Dict[str, Any]] = None, campo: str = "created_at",
              campo_es_dia: bool = False) -> Dict[str, Any]:
    """`filtro` con la condicion de que `campo` no sea posterior a ahora.

    Si el filtro ya trae una condicion sobre ese campo, se respeta y solo se añade el tope:
    asi se puede pedir "entre el reporte anterior y hoy" sin pisar nada.

    `campo_es_dia`: para campos que son UN DIA a secas (`effective_date`, "2026-08-23") y
    no un instante. Compararlos contra el instante UTC los dejaba fuera entre las 00:00 y
    las 02:00 de España ("2026-08-23" > "2026-08-22T22:30:00+00:00"): el ajuste que entra
    en vigor hoy no salia en el historial. El corte de un dia es el DIA de España.
    """
    if campo_es_dia:
        from core.tiempo import hoy_madrid
        corte = hoy_madrid().isoformat()
    else:
        corte = ahora()
    fuera = dict(filtro or {})
    actual = fuera.get(campo)
    if isinstance(actual, dict):
        fuera[campo] = {**actual, "$lte": min(actual["$lte"], corte) if "$lte" in actual else corte}
    elif actual is None:
        fuera[campo] = {"$lte": corte}
    # Si el filtro pedia una fecha exacta (`campo: "2026-08-09"`), se deja: quien pide un dia
    # concreto sabe cual pide.
    return fuera
