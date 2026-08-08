"""
El peso y el % graso del cliente, como SERIES con fecha (punto 30 del doc del 07-08).

El problema que resuelve es el de los dos pesos (punto 9): el peso "actual" se guardaba
en `client_profiles.weight`, suelto, y el historico vivia por otro lado -- en los reportes,
en el historial de macros y en lo que vino de Calma. Dos sitios, dos numeros, y ninguno
decia de cuando era.

Aqui el peso es una SERIE `{fecha, valor, origen}` y **el peso actual es el ultimo de la
serie, calculado**. `weight` se sigue escribiendo porque lo leen decenas de sitios, pero ya
no es un dato independiente: es un espejo que solo escribe este modulo a partir de la
serie, asi que no puede discrepar de ella. Lo mismo con `body_fat` y `porcentajes_grasos`,
que ya funcionaba asi desde el 05-08 (el endpoint del % graso por foto).

Reglas:

  - Un valor por dia. Si se anota dos veces el mismo dia, manda el ultimo: es una
    correccion, no dos pesajes.
  - Fuera de rango no entra. Un peso de 700 kg o un 90% de grasa no es un dato, es un
    error de tecleo, y en una serie un error asi arrastra el modelo entero.
  - Cada punto lleva de donde salio (`origen`: reporte, check-in, ajuste del coach, alta),
    porque no todos valen igual: el peso de un reporte lo ha mirado el coach.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.database import db

# La serie y el campo "actual" que refleja su ultimo valor.
PESO = ("pesos", "weight", 25.0, 300.0)
GRASA = ("porcentajes_grasos", "body_fat", 3.0, 60.0)


def _dia(valor: Optional[str] = None) -> str:
    if not valor:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return str(valor)[:10]


def _numero(valor: Any, minimo: float, maximo: float) -> Optional[float]:
    """El valor redondeado a un decimal, o None si no es un numero o se sale de rango."""
    try:
        v = round(float(valor), 1)
    except (TypeError, ValueError):
        return None
    return v if minimo <= v <= maximo else None


def poner_en_serie(serie: Optional[List[Dict[str, Any]]], fecha: str, valor: float,
                   origen: Optional[str] = None) -> List[Dict[str, Any]]:
    """La serie con `valor` en `fecha`, sustituyendo lo que hubiera ese dia. Ordenada."""
    fuera = [x for x in (serie or []) if _dia(x.get("fecha")) != fecha]
    punto: Dict[str, Any] = {"fecha": fecha, "valor": valor}
    if origen:
        punto["origen"] = origen
    fuera.append(punto)
    fuera.sort(key=lambda x: _dia(x.get("fecha")))
    return fuera


def actual(serie: Optional[List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    """El ultimo punto de la serie: {'valor', 'fecha'}. None si no hay ninguno."""
    puntos = [x for x in (serie or []) if x.get("valor") is not None and x.get("fecha")]
    if not puntos:
        return None
    ultimo = max(puntos, key=lambda x: _dia(x.get("fecha")))
    return {"valor": ultimo["valor"], "fecha": _dia(ultimo.get("fecha"))}


async def _anotar(cual, client_id: Optional[str], valor: Any,
                  fecha: Optional[str] = None, origen: Optional[str] = None) -> Optional[float]:
    """Mete un valor en la serie y deja el campo 'actual' en el ultimo de la serie.

    Devuelve el valor actual resultante (que puede NO ser el que se acaba de anotar: si se
    anota un pesaje de hace un mes, el actual sigue siendo el de la semana pasada).
    """
    campo_serie, campo_actual, minimo, maximo = cual
    if not client_id:
        return None
    v = _numero(valor, minimo, maximo)
    if v is None:
        return None

    perfil = await db.client_profiles.find_one({"id": client_id}, {"_id": 0, campo_serie: 1})
    if perfil is None:
        return None
    serie = poner_en_serie(perfil.get(campo_serie), _dia(fecha), v, origen)
    ahora = actual(serie)
    await db.client_profiles.update_one(
        {"id": client_id},
        {"$set": {campo_serie: serie, campo_actual: ahora["valor"] if ahora else None}},
    )
    return ahora["valor"] if ahora else None


async def anotar_peso(client_id: Optional[str], valor: Any, fecha: Optional[str] = None,
                      origen: Optional[str] = None) -> Optional[float]:
    """Un pesaje. `fecha` es la del PESAJE, no la del dia en que se apunta."""
    return await _anotar(PESO, client_id, valor, fecha, origen)


async def anotar_grasa(client_id: Optional[str], valor: Any, fecha: Optional[str] = None,
                       origen: Optional[str] = None) -> Optional[float]:
    """Un % graso estimado. Jesus solo lo pone cuando hay foto, asi que van pocos y sueltos."""
    return await _anotar(GRASA, client_id, valor, fecha, origen)
