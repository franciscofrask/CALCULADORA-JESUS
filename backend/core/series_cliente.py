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
from datetime import date, datetime, timedelta, timezone
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


# LOS ORIGENES QUE NO SON UN PESAJE (24-08). El peso de un reporte no sale de la bascula de
# ese dia: es un numero que el cliente escribe para resumir la semana -- y que casi siempre
# es la media que le propone la propia app -- y que se archiva con la fecha DEL DOCUMENTO.
# Todo lo demas (el cierre del dia, el alta, el coach) si fecha un pesaje.
ORIGENES_DE_REPORTE = ("reporte", "reporte (lo metió el equipo)")


def poner_en_serie(serie: Optional[List[Dict[str, Any]]], fecha: str, valor: float,
                   origen: Optional[str] = None, *,
                   pisa_pesajes: bool = True) -> List[Dict[str, Any]]:
    """La serie con `valor` en `fecha`, sustituyendo lo que hubiera ese dia. Ordenada.

    `pisa_pesajes=False` para lo que NO es un pesaje (ver `ORIGENES_DE_REPORTE`): si ese dia
    ya tiene punto y lo escribio otra puerta, la serie se devuelve tal cual.

    POR QUE EXISTE ESTE CANDADO (fallo 5 del repaso del 24-08). Enviar el reporte llamaba a
    `anotar_peso(..., dia_reporte, origen="reporte")` y esto sustituia el punto de ese dia:
    con jueves 80,0 y viernes 82,0 el reporte propone 81,0 (la media de la pareja), y al
    enviarlo la serie quedaba jueves 80,0 y viernes 81,0. El 82,0 que el cliente se peso de
    verdad desaparecia, el peso de la semana pasaba a 80,5 y cada reenvio lo movia otra vez
    (80,2...). Mordia justo al Premium, que es para quien se escribio la regla del peso: la
    ventana del semanal abre en VIERNES y dos de las tres parejas de Jesus llevan viernes.

    Un reporte SI corrige el punto que escribio otro reporte: eso no es perder un pesaje,
    es el mismo documento reenviado. Y un punto sin `origen` (los importados de Calma) se
    trata como pesaje: ante la duda, no se borra un dato que no sabemos de donde vino.
    """
    if not pisa_pesajes:
        previo = next((x for x in (serie or []) if _dia(x.get("fecha")) == fecha), None)
        if previo is not None and previo.get("origen") not in ORIGENES_DE_REPORTE:
            return list(serie or [])
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


# ─────────────────────────────────────────────────────────────────────────────
# EL PESO DE LA SEMANA (punto 34 del doc del 24-08)
# ─────────────────────────────────────────────────────────────────────────────
#
# «La primera pareja de días seguidos desde el miércoles. Miércoles-jueves,
#  jueves-viernes o viernes-sábado. En cuanto los tiene, hace la media.»
#
# Esa es la regla de Jesus y manda cuando existe, pero medida contra produccion se cumple
# en el 0,35 % de las semanas-cliente: la gente no se pesa dos dias seguidos. Por eso la
# decision del 24-08 es una CASCADA de tres ramas, para que la semana tenga peso casi un
# tercio de las veces (32,0 % de 4.576 semanas-cliente; 44 de 260 en los diez Premium):
#
#   a) la pareja de Jesus,
#   b) si no hay pareja, la media de TODOS los pesajes de esa semana (18,1 %),
#   c) si tampoco, el ultimo peso conocido de los ultimos 14 dias, y entonces hay que
#      poder enseñar SU FECHA, porque no es de esta semana.
#
# Siempre se devuelve de que rama sale: la pantalla lo tiene que decir, y un numero que el
# cliente no sabe de donde viene es un numero que no se cree.

# Los dias que forman pareja, con el indice de `weekday()` (0 = lunes). Se buscan EN ESTE
# ORDEN: la primera que exista gana, no la mejor ni la mas reciente.
PAREJAS_DESDE_EL_MIERCOLES = ((2, 3), (3, 4), (4, 5))

# La memoria de la rama c. Es el mismo tope que se midio contra produccion: con 21 dias la
# cobertura sube al 23 % y con 30 al 30 %, pero un peso de hace un mes ya no describe la
# semana de la que habla el reporte.
DIAS_DEL_ULTIMO_PESO = 14


def _media(valores: List[float]) -> float:
    return round(sum(valores) / len(valores), 1)


def peso_semanal(serie: Optional[List[Dict[str, Any]]], dia: date,
                 apuntes: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    """El peso de la semana de `dia` y DE DONDE SALE, con la cascada de arriba.

    `dia` es cualquier dia de la semana que se quiere resumir: se lleva a su lunes. La
    semana va de lunes a domingo, como la ISO y como el resto de la app.

    Devuelve `None` si no hay nada que enseñar, o:

        {"valor": 81.4,                     el kilo que sale
         "regla": "pareja" | "media" | "ultimo",
         "fechas": ["2026-08-19", "2026-08-20"],   los pesajes que entran en la cuenta
         "fecha": "2026-08-20",             el ultimo de ellos
         "de_esta_semana": True}            False solo en la rama c

    Los pesajes salen de `curva_de_peso`, que es LA UNICA CURVA de la app: asi el peso
    semanal cuenta con los mismos puntos que «Mis macros» y la tarjeta de renovacion, y de
    paso hereda el saneado (en produccion hay 0,0 kg y errores de coma) y el corte en hoy
    (hay pesajes fechados en 2027 y 2028, de pruebas).
    """
    lunes = dia - timedelta(days=dia.weekday())
    puntos: Dict[date, float] = {}
    for p in curva_de_peso(serie, apuntes):
        try:
            puntos[date.fromisoformat(p["fecha"])] = p["peso"]
        except (ValueError, TypeError):      # una fecha rota no tumba la semana entera
            continue

    de_la_semana = {k: puntos[lunes + timedelta(days=k)]
                    for k in range(7) if (lunes + timedelta(days=k)) in puntos}

    def _sale(valor: float, regla: str, dias: List[date], de_esta_semana: bool = True):
        return {"valor": valor, "regla": regla,
                "fechas": [d.isoformat() for d in dias],
                "fecha": max(dias).isoformat(),
                "de_esta_semana": de_esta_semana}

    # a) La pareja de dias seguidos desde el miercoles.
    for a, b in PAREJAS_DESDE_EL_MIERCOLES:
        if a in de_la_semana and b in de_la_semana:
            return _sale(_media([de_la_semana[a], de_la_semana[b]]), "pareja",
                         [lunes + timedelta(days=a), lunes + timedelta(days=b)])

    # b) La media de todos los pesajes de la semana. Con uno solo, la media es ese.
    if de_la_semana:
        return _sale(_media(list(de_la_semana.values())), "media",
                     [lunes + timedelta(days=k) for k in sorted(de_la_semana)])

    # c) El ultimo conocido, mirando hacia atras DESDE EL SABADO. El sabado y no hoy porque
    # asi el peso de una semana YA PASADA no cambia segun el dia en que se mire: la semana
    # es un periodo cerrado y su resumen tiene que ser siempre el mismo.
    #
    # PERO EN LA SEMANA EN CURSO EL CORTE ES HOY, y esto no es un detalle: el reporte se
    # pide siempre de la semana de hoy (`datos_del_reporte` llama con el ultimo dia del
    # periodo, que es hoy), asi que con el sabado a secas el lunes solo se miraban NUEVE
    # dias hacia atras -- los catorce menos los cinco que faltan para el sabado -- y a quien
    # se peso hace diez dias se le decia que no hay peso. Los catorce dias son catorce
    # contados desde el dia en que se abre el reporte. Mirar hasta el sabado que aun no ha
    # llegado no aporta nada: `curva_de_peso` ya corta en hoy y ahi no hay ningun punto.
    from core.tiempo import hoy_madrid

    hasta = min(lunes + timedelta(days=5), hoy_madrid())
    for i in range(DIAS_DEL_ULTIMO_PESO + 1):
        d = hasta - timedelta(days=i)
        if d in puntos:
            return _sale(puntos[d], "ultimo", [d], de_esta_semana=False)
    return None


# Cuanto hacia atras se acepta un pesaje que el cliente apunta a mano con su fecha.
#
# LA REGLA VIVE AQUI Y SOLO AQUI (fallo 7 del repaso del 24-08). Estaba escrita en tres
# sitios con tres numeros: 30 aqui, 14 en `routes/checkins.py` (el camino vivo) y 8 dias en
# el desplegable de la pantalla, que es lo unico que el cliente podia elegir. Ahora el
# servidor la aplica desde este modulo y ademas se la dice a la pantalla
# (`peso_dias_atras` en GET /checkins/hoy), asi que el desplegable ofrece exactamente lo
# que el servidor acepta.
#
# El numero son los mismos 14 dias con los que la regla del peso semanal busca «el ultimo
# conocido»: fechar mas atras no le sirve a nadie -- ese pesaje ya no entra en ninguna
# semana -- y si abre la puerta a rehacer la curva de hace un mes.
DIAS_ATRAS_PARA_UN_PESAJE = DIAS_DEL_ULTIMO_PESO


def fecha_de_pesaje_valida(fecha: Optional[str], hoy: Optional[date] = None) -> Optional[str]:
    """La fecha de un pesaje apuntado a mano, en ISO, o None si no se puede aceptar.

    ES LA PUERTA DE ENTRADA de la casilla de peso CON FECHA del cierre del dia (punto 34
    del doc del 24-08): hasta hoy el peso se archivaba con la fecha del documento y no con
    la del pesaje, y sin esto no puede existir nunca la pareja de dias seguidos.

    La serie ya admite un pesaje de otro dia sin romperse -- `poner_en_serie` sustituye el
    punto de ESE dia y `actual` sigue devolviendo el ultimo hasta hoy --, asi que lo unico
    que falta es que no se cuele lo que no es un pesaje:

      - del FUTURO no entra nada. Un pesaje de mañana no es el peso de nadie, y ademas se
        quedaria escondido en la serie hasta que llegara su dia (ver `actual`).
      - de hace mas de `DIAS_ATRAS_PARA_UN_PESAJE` tampoco.

    Sin fecha devuelve la de hoy, que es el caso normal: quien no toca la casilla se esta
    pesando ahora. Quien llama decide que decirle al cliente cuando sale None; aqui no se
    escriben mensajes.
    """
    from core.tiempo import hoy_madrid

    hoy = hoy or hoy_madrid()
    if not fecha:
        return hoy.isoformat()
    try:
        d = date.fromisoformat(str(fecha)[:10])
    except (ValueError, TypeError):
        return None
    if d > hoy or (hoy - d).days > DIAS_ATRAS_PARA_UN_PESAJE:
        return None
    return d.isoformat()


async def _anotar(cual, client_id: Optional[str], valor: Any,
                  fecha: Optional[str] = None, origen: Optional[str] = None, *,
                  pisa_pesajes: bool = True) -> Optional[float]:
    """Mete un valor en la serie y deja el campo 'actual' en el ultimo de la serie.

    Devuelve el valor actual resultante (que puede NO ser el que se acaba de anotar: si se
    anota un pesaje de hace un mes, el actual sigue siendo el de la semana pasada; y con
    `pisa_pesajes=False`, si ese dia ya tenia pesaje, no se anota nada en absoluto).
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
    serie = poner_en_serie(perfil.get(campo_serie), _dia(fecha), v, origen,
                           pisa_pesajes=pisa_pesajes)
    ahora = actual(serie)
    await db.client_profiles.update_one(
        {"id": client_id},
        {"$set": {campo_serie: serie, campo_actual: ahora["valor"] if ahora else None}},
    )
    return ahora["valor"] if ahora else None


async def anotar_peso(client_id: Optional[str], valor: Any, fecha: Optional[str] = None,
                      origen: Optional[str] = None, *,
                      pisa_pesajes: bool = True) -> Optional[float]:
    """Un pesaje. `fecha` es la del PESAJE, no la del dia en que se apunta.

    `pisa_pesajes=False` para el peso que llega dentro de un reporte, que no es un pesaje de
    ese dia: ver `poner_en_serie`.
    """
    return await _anotar(PESO, client_id, valor, fecha, origen, pisa_pesajes=pisa_pesajes)


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
