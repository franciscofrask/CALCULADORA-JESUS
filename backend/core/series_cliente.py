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
    # El fallback es EL DÍA DE ESPAÑA, no el de UTC (bloque F, 23-08). Con UTC, un pesaje
    # apuntado entre las 00:00 y las 02:00 de aquí se archivaba en AYER y, si ese día ya
    # tenía punto, `poner_en_serie` lo sobrescribía: se borraba un dato real. La lectura
    # (`actual`, `curva_de_peso`) ya cortaba en España; faltaba la escritura.
    if not valor:
        from core.tiempo import hoy_madrid
        return hoy_madrid().isoformat()
    return str(valor)[:10]


def _numero(valor: Any, minimo: float, maximo: float) -> Optional[float]:
    """El valor redondeado a un decimal, o None si no es un numero o se sale de rango."""
    try:
        v = round(float(valor), 1)
    except (TypeError, ValueError):
        return None
    return v if minimo <= v <= maximo else None


def sanea_peso(w: Any) -> Optional[float]:
    """Un peso que se pueda enseñar, o None. Arregla el error de coma (819 -> 81,9).

    Lo de arriba vale para lo que ESCRIBE este modulo, pero el peso tambien se lee de sitios
    viejos que nunca pasaron por aqui: `macro_history` y lo importado de Calma. Ahi hay 0,0,
    hay un 0,433 (un porcentaje de grasa metido donde va el peso) y hay saltos de 900 kg.

    Esta funcion existia YA, dos veces copiada (`routes/admin.py` y `macro_casos.py`), y por
    eso el panel del entrenador enseñaba la curva limpia mientras «Mis macros» le enseñaba al
    cliente sus 0 kg. Vive aqui, que es donde estan el rango y la regla.
    """
    try:
        w = float(w)
    except (TypeError, ValueError):
        return None
    minimo, maximo = PESO[2], PESO[3]
    while w > 1000:
        w /= 1000.0
    if 300 < w <= 1000:
        w /= 10.0
    return round(w, 1) if minimo < w < maximo else None


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
    """El ultimo punto de la serie HASTA HOY: {'valor', 'fecha'}. None si no hay ninguno.

    Lo de «hasta hoy» no es un detalle. En produccion hay pesajes y reportes fechados en
    2027 y 2028 -- de pruebas --, y cogiendo el maximo por fecha a secas ganaba uno de esos:
    Reportes enseñaba «Ultimo: 118 kg · 21 feb» (un reporte de 2028) mientras Ajustar macros
    decia 94 kg. Es el punto 9 del documento del 07-08, «hay dos pesos distintos en la misma
    app».

    Un pesaje del futuro no es el peso de nadie. Si algun dia hace falta programar algo a
    futuro, sera con otro campo y a proposito.

    EL «HOY» ES EL DE ESPAÑA (19-08), no el del reloj del servidor. Toda la app fecha en hora
    de España -- `hoy_madrid()` --, asi que entre las 00:00 y las 02:00 de aqui el servidor
    todavia esta en el dia anterior y un dato apuntado en esa franja quedaba «en el futuro»:
    se guardaba en la serie y a la vez BORRABA el campo que lee el resto de la app, porque
    esta funcion no encontraba ningun punto valido y devolvia None. Visto con un cliente real:
    su porcentaje de grasa entraba en la serie con fecha de hoy y su ficha se quedaba sin
    porcentaje de grasa, que es justo lo que hace falta para calcularle los macros.
    """
    from core.tiempo import hoy_madrid

    hoy = hoy_madrid().isoformat()
    puntos = [x for x in (serie or [])
              if x.get("valor") is not None and x.get("fecha") and _dia(x.get("fecha")) <= hoy]
    if not puntos:
        return None
    ultimo = max(puntos, key=lambda x: _dia(x.get("fecha")))
    return {"valor": ultimo["valor"], "fecha": _dia(ultimo.get("fecha"))}


def curva_de_peso(serie: Optional[List[Dict[str, Any]]],
                  apuntes: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Todos los pesajes del cliente ordenados por dia: [{'fecha', 'peso'}, ...].

    UNA SOLA CURVA PARA TODA LA APP (19-08). «Mis macros» ya la montaba asi -- la serie mas
    los pesos que viajaron dentro de un ajuste y nunca llegaron a la serie, que son casi todos
    los de Calma --, pero la tarjeta de renovacion miraba solo la serie y los reportes. Con un
    cliente que se habia movido 41 kg entre marzo y agosto, «Mis macros» pintaba la curva
    entera y la renovacion resumia el ciclo sin peso y sin cambio. Dos pantallas de la misma
    app contando cosas distintas del mismo cliente.

    `apuntes` son las filas de macro_history (o cualquier lista con `fecha`/`peso`). El peso
    se sanea igual que en el panel del entrenador: en produccion hay ajustes viejos con 0,0 kg,
    con un porcentaje de grasa metido donde va el peso y con errores de coma.
    """
    from core.tiempo import hoy_madrid

    hoy = hoy_madrid().isoformat()
    por_dia: Dict[str, float] = {}
    for p in (serie or []):
        fecha, valor = _dia(p.get("fecha")), sanea_peso(p.get("valor"))
        if fecha and valor is not None and fecha <= hoy:
            por_dia[fecha] = valor
    for a in (apuntes or []):
        fecha = _dia(a.get("fecha") or a.get("effective_date") or a.get("created_at"))
        crudo = a.get("peso") if a.get("peso") is not None else a.get("client_weight")
        valor = sanea_peso(crudo)
        # La serie manda: si ese dia ya tiene pesaje propio, el del ajuste no lo pisa.
        if fecha and valor is not None and fecha <= hoy and fecha not in por_dia:
            por_dia[fecha] = valor
    return [{"fecha": f, "peso": p} for f, p in sorted(por_dia.items())]


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


# Cada cuanto se le vuelve a pedir el % graso al cliente (punto 47 del doc del 07-08): "El %
# de grasa se pide cada 12 semanas, no cada 2". Los ajustes son quincenales, y hasta ahora la
# calculadora le exigia el % graso en cada uno: seis veces por ciclo. Un dato que se estima a
# ojo mirando fotos no cambia cada quince dias, y preguntarlo tan seguido solo consigue dos
# cosas -- que lo repita igual sin mirarlo, o que se lo invente.
SEMANAS_ENTRE_ESTIMACIONES_DE_GRASA = 12


def grasa_vigente(profile: Dict[str, Any], ahora: Optional[datetime] = None) -> Dict[str, Any]:
    """El % graso que vale ahora mismo y si toca volver a pedirlo.

    {valor, fecha, semanas, hay_que_pedirlo}. `hay_que_pedirlo` es True si no hay ninguno o
    si el ultimo tiene ya 12 semanas.
    """
    ultimo = actual(profile.get(GRASA[0]))
    if not ultimo:
        # Sin serie, el campo suelto del perfil todavia sirve de algo, pero sin fecha no se
        # puede saber si esta viejo: se pide.
        valor = profile.get(GRASA[1])
        return {"valor": valor, "fecha": None, "semanas": None, "hay_que_pedirlo": True}
    ahora = ahora or datetime.now(timezone.utc)
    try:
        d = datetime.strptime(str(ultimo["fecha"])[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        semanas = max(0, (ahora - d).days) // 7
    except (ValueError, TypeError):
        semanas = None
    return {
        "valor": ultimo["valor"],
        "fecha": ultimo["fecha"],
        "semanas": semanas,
        "hay_que_pedirlo": semanas is None or semanas >= SEMANAS_ENTRE_ESTIMACIONES_DE_GRASA,
    }
