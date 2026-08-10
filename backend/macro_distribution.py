"""
Distribución de Macros por Comida - Método 12en12
=========================================================
Toma los macros totales del día y los reparte entre las comidas
según el escenario (cantidad de H, momento de entreno, tipo de día).

Hay 4 escenarios de hidratos × 4 momentos de entreno = 16 tablas para día de entreno.
Día de descanso siempre reparte 25/25/25/25.
Periworkout: Intra 20%P/30%H, Post 80%P/70%H (con variantes).
"""

from typing import Dict, List, Optional
import logging
import math


# Peri de arranque para el cliente que todavia NO tiene perientreno configurado en su perfil
# (campo vacio, no un 0 puesto a proposito). Viene de cuando ningun perfil traia el campo.
PERI_DEFAULT_P = 35.0
PERI_DEFAULT_H = 15.0


def leer_macro(macros: Optional[Dict], *claves: str, default: float = 0.0) -> float:
    """Lee un macro de un dict de perfil probando varias claves (`protein`/`proteinas`).

    Distingue "no asignado" de un 0 puesto a proposito: un perientreno a 0 es una decision
    del coach, no un hueco que haya que rellenar con el valor por defecto. Antes las rutas
    encadenaban `peri.get("protein") or peri.get("proteinas") or 35`, y como en Python el 0
    cuenta como vacio, un peri a 0 se sustituia por 35 P / 15 H. Ese peri fantasma se colaba
    en el dia de entreno (repartido entre las comidas si la opcion era `sin_peri`) y hacia
    que el total del dia no cuadrase con los macros introducidos.
    """
    for clave in claves:
        valor = (macros or {}).get(clave)
        if valor is not None and valor != "":
            return float(valor)
    return float(default)


def leer_peri(peri: Optional[Dict], opcion_peri: Optional[str]) -> tuple:
    """Presupuesto de perientreno (P, H) del cliente, segun lo que tenga en el perfil.

    El peri son DOS ajustes distintos: cuanto tiene asignado (este dict) y como se lo toma
    (`opcion_peri`). El 35/15 de arranque solo es para el primero, cuando el campo esta vacio.

    En modo `sin_peri` ese arranque es 0: si el cliente no tiene peri configurado y ademas ha
    dicho que no toma peri, no hay presupuesto ninguno que repartir, y inventarle 35/15 le
    meteria en las comidas gramos que nadie le ha asignado. Ojo: esto NO toca al cliente que
    si tiene peri asignado y elige `sin_peri`; ese presupuesto es real y se sigue repartiendo
    entre las comidas (confirmado en el doc de Jesus del 07-08).
    """
    if opcion_peri == "sin_peri":
        por_defecto_p = por_defecto_h = 0.0
    else:
        por_defecto_p, por_defecto_h = PERI_DEFAULT_P, PERI_DEFAULT_H
    return (leer_macro(peri, "protein", "proteinas", default=por_defecto_p),
            leer_macro(peri, "carbs", "hidratos", default=por_defecto_h))


# NOTE: Calma rounds each per-meal macro to the nearest 0.5 g (stepRedondeo) ONLY FOR
# DISPLAY. The unrounded value drives the suggestion engine (me/diferencia). Rounding here
# made the frontend send the rounded remaining (e.g. 47 instead of 46.8) -> a granel food's
# me became 47/0.06=783 instead of 46.8/0.06=780. So distribution stays UNROUNDED; the 0.5
# display rounding lives in the frontend meal-target display only.
def _round_comidas_half(comidas: Dict[str, Dict[str, float]]) -> None:
    return  # intentionally a no-op; rounding is display-only (frontend)


# =====================================================
# 16 TABLAS DE DISTRIBUCIÓN - DÍA DE ENTRENAMIENTO
# =====================================================
# Formato: { momento_entreno: { "C1": [P%, H%, G%], "C2": [...], "C3": [...], "C4": [...] } }
# Momento: 0=En ayunas, 1=Después C1, 2=Después C2, 3=Después C3

# ESCENARIO 1: H > 150g
DIST_E1 = {
    0: {"C1": [25, 30, 20], "C2": [25, 20, 25], "C3": [20, 20, 25], "C4": [30, 30, 30]},
    1: {"C1": [25, 30, 20], "C2": [25, 30, 20], "C3": [20, 20, 30], "C4": [30, 20, 30]},
    2: {"C1": [25, 20, 30], "C2": [20, 30, 20], "C3": [25, 30, 20], "C4": [30, 20, 30]},
    3: {"C1": [30, 20, 30], "C2": [25, 20, 30], "C3": [20, 30, 20], "C4": [25, 30, 20]},
}

# ESCENARIO 2: 100-150g H
DIST_E2 = {
    0: {"C1": [25, 36, 20], "C2": [25, 18, 25], "C3": [20, 10, 25], "C4": [30, 36, 30]},
    1: {"C1": [25, 36, 20], "C2": [25, 36, 20], "C3": [20, 18, 30], "C4": [30, 10, 30]},
    2: {"C1": [25, 18, 30], "C2": [20, 36, 20], "C3": [25, 36, 20], "C4": [30, 10, 30]},
    3: {"C1": [30, 10, 30], "C2": [25, 18, 30], "C3": [20, 36, 20], "C4": [25, 36, 20]},
}

# ESCENARIO 3 y 4 usan lógica especial (no porcentajes fijos para H)


def _get_escenario(h_total: float) -> int:
    """Determina el escenario según los hidratos totales del día."""
    if h_total > 150:
        return 1
    elif h_total >= 100:
        return 2
    elif h_total >= 50:
        return 3
    else:
        return 4


def _distribuir_escenario_1_2(
    p_total: float, h_total: float, g_total: float,
    momento: int, escenario: int
) -> Dict[str, Dict[str, float]]:
    """Distribuye macros para escenarios 1 (>150H) y 2 (100-150H)."""
    tabla = DIST_E1 if escenario == 1 else DIST_E2
    dist = tabla[momento]

    resultado = {}
    for comida, pcts in dist.items():
        resultado[comida] = {
            "P": round(p_total * pcts[0] / 100, 1),
            "H": round(h_total * pcts[1] / 100, 1),
            "G": round(g_total * pcts[2] / 100, 1),
        }
    return resultado


def _distribuir_escenario_3(
    p_total: float, h_total: float, g_total: float,
    momento: int
) -> Dict[str, Dict[str, float]]:
    """
    Escenario 3: 50-100g H.
    Regla: Restar 20g del total de H. 
    Esos 20g → 10g + 10g a las 2 comidas MÁS LEJOS del entreno.
    El resto (h_total - 20) → 50/50 entre las 2 comidas MÁS CERCA del entreno.
    P y G se reparten con los mismos % que escenario 1.
    """
    h_resto = h_total - 20  # Lo que se reparte 50/50
    h_mitad = round(h_resto / 2, 1)

    # P y G: usar porcentajes del escenario 1
    p_dist = DIST_E1[momento]

    # Determinar qué comidas están cerca y lejos del entreno
    # Momento 0 (en ayunas): entreno antes de C1
    #   Cerca: C1 y C4 (post-entreno=C1, pre=C4 del día anterior → C1 y C4)
    #   Lejos: C2 y C3
    # Momento 1 (después C1): entreno entre C1 y C2
    #   Cerca: C1 (pre) y C2 (post)
    #   Lejos: C3 y C4
    # Momento 2 (después C2): entreno entre C2 y C3
    #   Cerca: C2 (pre) y C3 (post)
    #   Lejos: C1 y C4
    # Momento 3 (después C3): entreno entre C3 y C4
    #   Cerca: C3 (pre) y C4 (post)
    #   Lejos: C1 y C2

    h_map = {
        0: {"C1": h_mitad, "C2": 10, "C3": 10, "C4": h_mitad},
        1: {"C1": h_mitad, "C2": h_mitad, "C3": 10, "C4": 10},
        2: {"C1": 10, "C2": h_mitad, "C3": h_mitad, "C4": 10},
        3: {"C1": 10, "C2": 10, "C3": h_mitad, "C4": h_mitad},
    }

    resultado = {}
    for comida in ["C1", "C2", "C3", "C4"]:
        pcts = p_dist[comida]
        resultado[comida] = {
            "P": round(p_total * pcts[0] / 100, 1),
            "H": round(h_map[momento][comida], 1),
            "G": round(g_total * pcts[2] / 100, 1),
        }
    return resultado


def _distribuir_escenario_4(
    p_total: float, h_total: float, g_total: float,
    momento: int
) -> Dict[str, Dict[str, float]]:
    """
    Escenario 4: <50g H. Mirrors Calma `pe`:
      - H < 30:  ALL carbs go to the post meal (s==a+1), 0 everywhere else.
                 (e.g. h=25, momento1 -> [0,25,0,0], NOT [10,15,0,0].)
      - 30 <= H < 50: post meal gets H-10, the secondary meal (s%4==a) gets 10, rest 0.
    P y G usan porcentajes del escenario 1.
    """
    if h_total < 30:
        h_principal = h_total       # post meal absorbs everything
        h_secundaria = 0
    else:
        h_principal = max(0, h_total - 10)
        h_secundaria = 10

    # principal = post meal (s == a+1); secundaria = s%4 == a
    # Momento 0: post=C1, secundaria=C4 | 1: post=C2, sec=C1 | 2: post=C3, sec=C2 | 3: post=C4, sec=C3
    h_map = {
        0: {"C1": h_principal, "C2": 0, "C3": 0, "C4": h_secundaria},
        1: {"C1": h_secundaria, "C2": h_principal, "C3": 0, "C4": 0},
        2: {"C1": 0, "C2": h_secundaria, "C3": h_principal, "C4": 0},
        3: {"C1": 0, "C2": 0, "C3": h_secundaria, "C4": h_principal},
    }

    p_dist = DIST_E1[momento]

    resultado = {}
    for comida in ["C1", "C2", "C3", "C4"]:
        pcts = p_dist[comida]
        resultado[comida] = {
            "P": round(p_total * pcts[0] / 100, 1),
            "H": round(h_map[momento][comida], 1),
            "G": round(g_total * pcts[2] / 100, 1),
        }
    return resultado


def _distribuir_descanso(
    p_total: float, h_total: float, g_total: float,
    num_comidas: int
) -> Dict[str, Dict[str, float]]:
    """Día de descanso: reparto equitativo entre todas las comidas."""
    pct = 100.0 / num_comidas
    resultado = {}
    for i in range(1, num_comidas + 1):
        resultado[f"C{i}"] = {
            "P": round(p_total * pct / 100, 1),
            "H": round(h_total * pct / 100, 1),
            "G": round(g_total * pct / 100, 1),
        }
    return resultado


def _distribuir_3_comidas(
    p_total: float, h_total: float, g_total: float
) -> Dict[str, Dict[str, float]]:
    """3 comidas: reparto equitativo 33.3% cada una. Sin escenarios de H."""
    tercio_p = round(p_total / 3, 1)
    tercio_h = round(h_total / 3, 1)
    tercio_g = round(g_total / 3, 1)
    return {
        "C1": {"P": tercio_p, "H": tercio_h, "G": tercio_g},
        "C2": {"P": tercio_p, "H": tercio_h, "G": tercio_g},
        "C3": {"P": tercio_p, "H": tercio_h, "G": tercio_g},
    }


def _calcular_periworkout(
    p_peri: float, h_peri: float,
    opcion_peri: str
) -> Dict[str, Dict[str, float]]:
    """
    Calcula los macros de Intra y Post según la opción de periworkout.

    4 modos OFICIALES (decisión de proyecto 2026-06-22):
        "intra_post" → Intra 20%P/30%H, Post 80%P/70%H         (modo 1, base Calma)
        "solo_post"  → Post 100%P/100%H, sin Intra             (modo 2, base Calma)
        "solo_intra" → Intra 25%P/35%H; el resto (75%/65%) se reparte entre las comidas (modo 3)
        "sin_peri"   → sin Intra/Post; todo el presupuesto peri se reparte entre las comidas (modo 4)
    Los modos 3 y 4 NO existen en Calma pero son oficiales en nuestra app.
    Cualquier otro valor cae a intra_post.
    """
    resultado = {}

    if opcion_peri == "sin_peri":
        # Sin peri: no hay Intra/Post; el presupuesto peri se reparte equitativo entre las comidas.
        resultado["extra_comidas"] = {"P": p_peri, "H": h_peri}
        return resultado

    if opcion_peri == "solo_intra":
        # Solo intra (spec del video): el intra se lleva su parte normal + 5 puntos =
        #   proteínas 20% -> 25% del peri ; hidratos 30% -> 35% del peri.
        # El RESTO del peri (75% P, 65% H) se reparte EQUITATIVO entre las comidas
        # (mecanismo extra_comidas). El intra NO lleva grasa (peri = solo P/H).
        resultado["Intra"] = {
            "P": round(p_peri * 0.25, 1),
            "H": round(h_peri * 0.35, 1),
            "G": 0.0
        }
        resultado["extra_comidas"] = {"P": p_peri * 0.75, "H": h_peri * 0.65}
        return resultado

    if opcion_peri == "solo_post":
        resultado["Post"] = {
            "P": round(p_peri, 1),
            "H": round(h_peri, 1),
            "G": 0.0
        }
    else:
        # intra_post (default)
        resultado["Intra"] = {
            "P": round(p_peri * 0.20, 1),
            "H": round(h_peri * 0.30, 1),
            "G": 0.0
        }
        resultado["Post"] = {
            "P": round(p_peri * 0.80, 1),
            "H": round(h_peri * 0.70, 1),
            "G": 0.0
        }

    resultado["extra_comidas"] = {"P": 0.0, "H": 0.0}
    return resultado


def distribuir_macros(
    p_entreno: float,
    h_entreno: float,
    g_entreno: float,
    p_peri: float,
    h_peri: float,
    p_descanso: float,
    h_descanso: float,
    g_descanso: float,
    tipo_dia: str,
    num_comidas: int,
    momento_entreno: int,
    opcion_peri: str,
    single_meal: bool = False
) -> Dict:
    """
    FUNCIÓN PRINCIPAL - Distribuye los macros totales del día entre las comidas.

    Args:
        p_entreno, h_entreno, g_entreno: macros de día de entrenamiento
        p_peri, h_peri: macros de periworkout
        p_descanso, h_descanso, g_descanso: macros de día de descanso
        tipo_dia: "entrenamiento" o "descanso"
        num_comidas: 3 o 4
        momento_entreno: 0 (ayunas), 1 (después C1), 2 (después C2), 3 (después C3)
        opcion_peri: "intra_post", "solo_post", "solo_intra", "sin_peri"

    Returns:
        {
            "comidas": {
                "C1": {"P": 45.0, "H": 75.0, "G": 13.0},
                "C2": {"P": 45.0, "H": 50.0, "G": 16.3},
                ...
            },
            "periworkout": {
                "Intra": {"P": 8.0, "H": 9.0, "G": 0.0},    # si aplica
                "Post": {"P": 32.0, "H": 21.0, "G": 0.0},     # si aplica
            },
            "resumen": {
                "P_total": 220.0,
                "H_total": 280.0,
                "G_total": 65.0,
                "kcal_total": 2585.0
            },
            "escenario": 1,
            "config": {
                "tipo_dia": "entrenamiento",
                "num_comidas": 4,
                "momento_entreno": 1,
                "opcion_peri": "intra_post"
            }
        }
    """

    # El momento de entreno indexa las tablas, asi que cualquier valor fuera de 0-3 reventaba
    # con un KeyError. Eso llega como un 500 a /distribute, y la pantalla de Nutricion se queda
    # con TODOS los objetivos por comida a cero (se ve como "todo sobra"). Ante un valor que no
    # existe se usa el de siempre, "despues de la Comida 1", que es el que ya asumen las rutas.
    corregido = []   # lo que llego mal y hubo que arreglar, para poder decirlo

    try:
        _m = int(momento_entreno)
    except (TypeError, ValueError):
        _m = None
    if _m not in (0, 1, 2, 3):
        corregido.append(f"momento_entreno={momento_entreno!r} no es 0-3: se usa 1")
        _m = 1
    momento_entreno = _m

    # NUM_COMIDAS: 3 o 4, y nada mas (punto 5.4). Cualquier otro valor caia en el `else` y se
    # trataba como 4 sin decir nada: un cliente configurado a 5 comidas recibia el reparto de
    # cuatro y la quinta se quedaba a cero, que en pantalla se ve como "todo sobra".
    try:
        _n = int(num_comidas)
    except (TypeError, ValueError):
        _n = None
    if _n not in (3, 4):
        corregido.append(f"num_comidas={num_comidas!r} no es 3 ni 4: se usa 4")
        _n = 4
    num_comidas = _n

    # Y NADA NEGATIVO. Con -50 de hidratos el reparto devolvia -50 en una comida tan tranquilo,
    # y de ahi salen objetivos negativos en la pantalla. Un macro negativo no es un macro
    # pequeño: es un dato roto, y repartirlo es propagarlo.
    def _no_negativo(valor, nombre):
        try:
            v = float(valor or 0)
        except (TypeError, ValueError):
            v = 0.0
        if v < 0:
            corregido.append(f"{nombre}={valor!r} es negativo: se usa 0")
            return 0.0
        return v

    # OPCION_PERI: los cuatro modos, y nada mas (punto 5.4, TABLA 19). Un valor desconocido
    # cae en el `else` de `_calcular_periworkout` y se trata como intra_post -- que es lo
    # razonable --, pero era el unico de los tres controles de rango que lo hacia SIN decirlo.
    # Un cliente configurado en "solo post" cuyo modo llegue mal escrito recibe intra y post
    # y no hay nada en ninguna parte que permita enterarse.
    if opcion_peri not in ("intra_post", "solo_intra", "solo_post", "sin_peri"):
        corregido.append(f"opcion_peri={opcion_peri!r} no es un modo conocido: se usa intra_post")
        opcion_peri = "intra_post"

    p_entreno = _no_negativo(p_entreno, "p_entreno")
    h_entreno = _no_negativo(h_entreno, "h_entreno")
    g_entreno = _no_negativo(g_entreno, "g_entreno")
    p_peri = _no_negativo(p_peri, "p_peri")
    h_peri = _no_negativo(h_peri, "h_peri")
    p_descanso = _no_negativo(p_descanso, "p_descanso")
    h_descanso = _no_negativo(h_descanso, "h_descanso")
    g_descanso = _no_negativo(g_descanso, "g_descanso")

    # Se corrige y se sigue -- dejar al cliente sin reparto es peor --, pero queda escrito.
    # Un valor malo que se arregla en silencio se queda para siempre: nadie va a buscar lo que
    # nadie ha dicho que este pasando.
    if corregido:
        logging.getLogger("uvicorn.error").warning(
            "distribuir_macros recibio valores fuera de rango: %s", "; ".join(corregido))

    # === DÍA DE DESCANSO ===
    if tipo_dia == "descanso":
        # Modo comida única (Calma esModoSinRepartoDeMacrosPorComidas): 1 comida con TODO el
        # presupuesto del día, sin reparto. Descanso no tiene peri.
        if single_meal:
            comidas = {"C1": {"P": round(p_descanso, 1), "H": round(h_descanso, 1), "G": round(g_descanso, 1)}}
        else:
            comidas = _distribuir_descanso(p_descanso, h_descanso, g_descanso, num_comidas)
        _round_comidas_half(comidas)

        p_total = p_descanso
        h_total = h_descanso
        g_total = g_descanso

        return {
            "comidas": comidas,
            "periworkout": {},
            "resumen": {
                "P_total": round(p_total, 1),
                "H_total": round(h_total, 1),
                "G_total": round(g_total, 1),
                "kcal_total": round(p_total * 4 + h_total * 4 + g_total * 9, 1)
            },
            "escenario": 0,
            "config": {
                "tipo_dia": "descanso",
                "num_comidas": num_comidas,
                "momento_entreno": None,
                "opcion_peri": None
            }
        }

    # === DÍA DE ENTRENAMIENTO ===

    # 1. Calcular periworkout
    peri = _calcular_periworkout(p_peri, h_peri, opcion_peri)
    extra_P = peri.get("extra_comidas", {}).get("P", 0.0)
    extra_H = peri.get("extra_comidas", {}).get("H", 0.0)

    # 2. El presupuesto de peri que el cliente no se toma en bebida (modos `sin_peri` y el
    # resto del `solo_intra`) se lo come en las comidas, asi que entra en el total del dia
    # ANTES de repartir: el tramo de hidratos y los porcentajes de las tablas se aplican
    # sobre lo que de verdad va a las comidas.
    #
    # Antes se sumaba DESPUES, a partes iguales entre las 4 comidas, y eso deshacia la forma
    # del reparto: 50 H de entreno + 15 de peri en modo `sin_peri` daba 18,8 / 18,8 / 13,8 /
    # 13,8 en vez de los 22,5 / 22,5 / 10 / 10 del tramo de 50-100 g (doc de Jesus del 07-08).
    # El total del dia no cambia; cambia como se reparte.
    p_comidas = p_entreno + extra_P
    h_comidas = h_entreno + extra_H
    g_comidas = g_entreno

    # 3. Distribuir comidas principales
    if single_meal:
        # Modo comida única: la única comida recibe TODO el presupuesto de entreno (no-peri);
        # el peri (intra/post) queda aparte. Sin escenarios de H ni reparto.
        comidas = {"C1": {"P": round(p_comidas, 1), "H": round(h_comidas, 1), "G": round(g_comidas, 1)}}
        escenario = 0
    elif num_comidas == 3:
        # 3 comidas: reparto equitativo, sin escenarios de H
        comidas = _distribuir_3_comidas(p_comidas, h_comidas, g_comidas)
        escenario = 0
    else:
        # 4 comidas: usar escenarios según H
        escenario = _get_escenario(h_comidas)

        if escenario == 1:
            comidas = _distribuir_escenario_1_2(p_comidas, h_comidas, g_comidas, momento_entreno, 1)
        elif escenario == 2:
            comidas = _distribuir_escenario_1_2(p_comidas, h_comidas, g_comidas, momento_entreno, 2)
        elif escenario == 3:
            comidas = _distribuir_escenario_3(p_comidas, h_comidas, g_comidas, momento_entreno)
        else:
            comidas = _distribuir_escenario_4(p_comidas, h_comidas, g_comidas, momento_entreno)

    # 4. Construir periworkout (sin el campo extra_comidas)
    periworkout_result = {}
    if "Intra" in peri:
        periworkout_result["Intra"] = peri["Intra"]
    if "Post" in peri:
        periworkout_result["Post"] = peri["Post"]

    # Calma redondea cada macro de cada comida/peri a 0.5 g (stepRedondeo).
    _round_comidas_half(comidas)
    _round_comidas_half(periworkout_result)

    # 5. Calcular totales
    p_total = sum(c["P"] for c in comidas.values())
    h_total = sum(c["H"] for c in comidas.values())
    g_total = sum(c["G"] for c in comidas.values())

    if "Intra" in periworkout_result:
        p_total += periworkout_result["Intra"]["P"]
        h_total += periworkout_result["Intra"]["H"]
    if "Post" in periworkout_result:
        p_total += periworkout_result["Post"]["P"]
        h_total += periworkout_result["Post"]["H"]

    return {
        "comidas": comidas,
        "periworkout": periworkout_result,
        "resumen": {
            "P_total": round(p_total, 1),
            "H_total": round(h_total, 1),
            "G_total": round(g_total, 1),
            "kcal_total": round(p_total * 4 + h_total * 4 + g_total * 9, 1),
            "P_entreno": round(p_entreno, 1),
            "H_entreno": round(h_entreno, 1),
            "G_entreno": round(g_entreno, 1),
        },
        "escenario": escenario,
        "config": {
            "tipo_dia": "entrenamiento",
            "num_comidas": 1 if single_meal else num_comidas,
            "momento_entreno": momento_entreno,
            "opcion_peri": opcion_peri,
            "single_meal": single_meal
        }
    }


# =====================================================
# TESTS DE VERIFICACIÓN
# =====================================================

def run_tests():
    print("=" * 60)
    print("TESTS DISTRIBUCIÓN DE MACROS")
    print("=" * 60)

    passed = 0
    failed = 0

    def test(name, result, expected, tolerance=0.2):
        nonlocal passed, failed
        if isinstance(expected, float):
            if abs(result - expected) <= tolerance:
                print(f"  ✅ {name}: {result}")
                passed += 1
            else:
                print(f"  ❌ {name}: esperado {expected}, obtenido {result}")
                failed += 1
        else:
            if result == expected:
                print(f"  ✅ {name}: {result}")
                passed += 1
            else:
                print(f"  ❌ {name}: esperado {expected}, obtenido {result}")
                failed += 1

    # --- TEST 1: Escenario 1 (>150H), momento 1, 4 comidas, intra+post ---
    print("\n--- Escenario 1: 250H, después C1, 4 comidas, intra+post ---")
    r = distribuir_macros(
        p_entreno=180, h_entreno=250, g_entreno=65,
        p_peri=40, h_peri=30,
        p_descanso=180, h_descanso=200, g_descanso=65,
        tipo_dia="entrenamiento", num_comidas=4,
        momento_entreno=1, opcion_peri="intra_post"
    )
    test("Escenario", r["escenario"], 1)
    test("C1 P", r["comidas"]["C1"]["P"], 45.0)
    test("C1 H", r["comidas"]["C1"]["H"], 75.0)
    test("C1 G", r["comidas"]["C1"]["G"], 13.0)
    test("C2 P", r["comidas"]["C2"]["P"], 45.0)
    test("C2 H", r["comidas"]["C2"]["H"], 75.0)
    test("C2 G", r["comidas"]["C2"]["G"], 13.0)
    test("C3 P", r["comidas"]["C3"]["P"], 36.0)
    test("C3 H", r["comidas"]["C3"]["H"], 50.0)
    test("C3 G", r["comidas"]["C3"]["G"], 19.5)
    test("C4 P", r["comidas"]["C4"]["P"], 54.0)
    test("C4 H", r["comidas"]["C4"]["H"], 50.0)
    test("C4 G", r["comidas"]["C4"]["G"], 19.5)
    test("Intra P", r["periworkout"]["Intra"]["P"], 8.0)
    test("Intra H", r["periworkout"]["Intra"]["H"], 9.0)
    test("Post P", r["periworkout"]["Post"]["P"], 32.0)
    test("Post H", r["periworkout"]["Post"]["H"], 21.0)

    # --- TEST 2: Día de descanso, 4 comidas ---
    print("\n--- Día de descanso, 4 comidas ---")
    r = distribuir_macros(
        p_entreno=180, h_entreno=250, g_entreno=65,
        p_peri=40, h_peri=30,
        p_descanso=180, h_descanso=200, g_descanso=65,
        tipo_dia="descanso", num_comidas=4,
        momento_entreno=0, opcion_peri="intra_post"
    )
    test("C1 P", r["comidas"]["C1"]["P"], 45.0)
    test("C1 H", r["comidas"]["C1"]["H"], 50.0)
    test("C1 G", r["comidas"]["C1"]["G"], 16.2, 0.3)
    test("C2 = C3 = C4 (equitativo)", r["comidas"]["C2"]["P"], r["comidas"]["C3"]["P"])
    test("Sin periworkout", r["periworkout"], {})

    # --- TEST 3: 3 comidas, entrenamiento ---
    print("\n--- 3 comidas, entrenamiento, intra+post ---")
    r = distribuir_macros(
        p_entreno=180, h_entreno=250, g_entreno=65,
        p_peri=40, h_peri=30,
        p_descanso=180, h_descanso=200, g_descanso=65,
        tipo_dia="entrenamiento", num_comidas=3,
        momento_entreno=1, opcion_peri="intra_post"
    )
    test("Solo 3 comidas", len(r["comidas"]), 3)
    test("C1 P = 60 (180/3)", r["comidas"]["C1"]["P"], 60.0)
    test("C1 H = 83.3 (250/3)", r["comidas"]["C1"]["H"], 83.3)
    test("Tiene Intra", "Intra" in r["periworkout"], True)
    test("Tiene Post", "Post" in r["periworkout"], True)

    # --- TEST 4: Solo post ---
    print("\n--- 4 comidas, solo post ---")
    r = distribuir_macros(
        p_entreno=180, h_entreno=250, g_entreno=65,
        p_peri=40, h_peri=30,
        p_descanso=180, h_descanso=200, g_descanso=65,
        tipo_dia="entrenamiento", num_comidas=4,
        momento_entreno=1, opcion_peri="solo_post"
    )
    test("No tiene Intra", "Intra" not in r["periworkout"], True)
    test("Post P = 40 (100%)", r["periworkout"]["Post"]["P"], 40.0)
    test("Post H = 30 (100%)", r["periworkout"]["Post"]["H"], 30.0)

    # (solo_intra / sin_peri eliminados - no existen en Calma)

    # --- TEST 7: Escenario 3 (50-100H) ---
    print("\n--- Escenario 3: 80H, momento 1 ---")
    r = distribuir_macros(
        p_entreno=180, h_entreno=80, g_entreno=65,
        p_peri=40, h_peri=30,
        p_descanso=180, h_descanso=60, g_descanso=65,
        tipo_dia="entrenamiento", num_comidas=4,
        momento_entreno=1, opcion_peri="intra_post"
    )
    test("Escenario", r["escenario"], 3)
    # H: (80-20)/2 = 30 per comida cercana, 10 per lejana
    # Momento 1: cerca=C1,C2, lejos=C3,C4
    test("C1 H = 30 (cercana)", r["comidas"]["C1"]["H"], 30.0)
    test("C2 H = 30 (cercana)", r["comidas"]["C2"]["H"], 30.0)
    test("C3 H = 10 (lejana)", r["comidas"]["C3"]["H"], 10.0)
    test("C4 H = 10 (lejana)", r["comidas"]["C4"]["H"], 10.0)

    # --- TEST 8: Escenario 4 (<50H) ---
    print("\n--- Escenario 4: 40H, momento 2 ---")
    r = distribuir_macros(
        p_entreno=180, h_entreno=40, g_entreno=65,
        p_peri=40, h_peri=30,
        p_descanso=180, h_descanso=30, g_descanso=65,
        tipo_dia="entrenamiento", num_comidas=4,
        momento_entreno=2, opcion_peri="intra_post"
    )
    test("Escenario", r["escenario"], 4)
    # Momento 2: principal=C3 (post), secundaria=C2 (pre)
    test("C1 H = 0", r["comidas"]["C1"]["H"], 0.0)
    test("C2 H = 10", r["comidas"]["C2"]["H"], 10.0)
    test("C3 H = 30 (40-10)", r["comidas"]["C3"]["H"], 30.0)
    test("C4 H = 0", r["comidas"]["C4"]["H"], 0.0)

    # --- TEST 8b: Escenario 4 con H<30 (todo al post) ---
    print("\n--- Escenario 4: 25H (<30), momento 1 -> todo al post ---")
    r = distribuir_macros(
        p_entreno=180, h_entreno=25, g_entreno=65,
        p_peri=40, h_peri=30,
        p_descanso=180, h_descanso=20, g_descanso=65,
        tipo_dia="entrenamiento", num_comidas=4,
        momento_entreno=1, opcion_peri="intra_post"
    )
    test("Escenario", r["escenario"], 4)
    # Calma: H<30 -> todo a C2 (post, s==a+1), 0 al resto. NO [10,15,0,0].
    test("C1 H = 0", r["comidas"]["C1"]["H"], 0.0)
    test("C2 H = 25 (todo)", r["comidas"]["C2"]["H"], 25.0)
    test("C3 H = 0", r["comidas"]["C3"]["H"], 0.0)
    test("C4 H = 0", r["comidas"]["C4"]["H"], 0.0)

    # --- TEST 9: Escenario 2 (100-150H), en ayunas ---
    print("\n--- Escenario 2: 120H, en ayunas ---")
    r = distribuir_macros(
        p_entreno=180, h_entreno=120, g_entreno=65,
        p_peri=40, h_peri=30,
        p_descanso=180, h_descanso=100, g_descanso=65,
        tipo_dia="entrenamiento", num_comidas=4,
        momento_entreno=0, opcion_peri="intra_post"
    )
    test("Escenario", r["escenario"], 2)
    test("C1 H = 43.2 (36%)", r["comidas"]["C1"]["H"], 43.2)
    test("C2 H = 21.6 (18%)", r["comidas"]["C2"]["H"], 21.6)
    test("C3 H = 12.0 (10%)", r["comidas"]["C3"]["H"], 12.0)
    test("C4 H = 43.2 (36%)", r["comidas"]["C4"]["H"], 43.2)

    # --- TEST 10: Los totales cuadran ---
    print("\n--- Verificación de totales ---")
    r = distribuir_macros(
        p_entreno=180, h_entreno=250, g_entreno=65,
        p_peri=40, h_peri=30,
        p_descanso=180, h_descanso=200, g_descanso=65,
        tipo_dia="entrenamiento", num_comidas=4,
        momento_entreno=1, opcion_peri="intra_post"
    )
    p_sum = sum(c["P"] for c in r["comidas"].values())
    if "Intra" in r["periworkout"]:
        p_sum += r["periworkout"]["Intra"]["P"]
    if "Post" in r["periworkout"]:
        p_sum += r["periworkout"]["Post"]["P"]
    test("P total = entreno+peri", abs(p_sum - (180 + 40)) < 1, True)

    g_sum = sum(c["G"] for c in r["comidas"].values())
    test("G total = entreno", abs(g_sum - 65) < 1, True)

    # --- RESUMEN ---
    print("\n" + "=" * 60)
    print(f"RESULTADO: {passed} pasados, {failed} fallidos de {passed + failed}")
    print("=" * 60)

    if failed > 0:
        print("\n⚠️  HAY TESTS FALLIDOS - REVISAR")
    else:
        print("\n✅ TODOS LOS TESTS PASAN - Distribución OK")

    return failed == 0


if __name__ == "__main__":
    run_tests()
