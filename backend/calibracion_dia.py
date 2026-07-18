"""Calibración progresiva de la proteína vegetal por ACUMULADO DEL DÍA.

Spec del usuario (17-07-2026): la calculadora ya aplica todas las reglas por
categoría; esta es LA regla que faltaba en el conteo real de la app.

  - Bloque 1 · cereales + panes (cat 7 y 8, acumulado CONJUNTO):
      H cuenta siempre. P solo si P > H/3 (por 100 g); cuando aplica, cuenta al
      0 % / 50 % / 100 % según el acumulado del día (0-50 / 50-100 / >100 g).
      Excepción: 7.1.3 y 8.8 (proteicos) -> P siempre al 100 %.
      La grasa sigue su regla de categoría normal (no es calibración).
  - Bloque 2 · frutos secos naturales (17.2.1/17.2.3/17.2.4/17.2.6, acumulado PROPIO):
      G cuenta siempre. P y H solo si superan G/3 (por 100 g); cuando aplican,
      cuentan al 0 % / 50 % / 100 % según su acumulado (0-20 / 20-40 / >40 g).

Reglas críticas:
  - El acumulador suma GRAMOS de ese tipo de alimento (unidades -> n x ración).
  - La comida ENTERA se asigna al tramo del acumulado TRAS añadirla (no se
    fracciona dentro de una comida).
  - Recorrer las comidas en orden cronológico hace que editar una comida solo
    afecte a esa y a las POSTERIORES (las anteriores no dependen de ella).
  - El acumulado nace de las comidas de ESE día: se "reinicia" solo a las 00:00
    porque cada fecha es su propia dieta.
  - En comidas SUELTAS (biblioteca de menús) esta regla no aplica.

El resto de macros (y los alimentos que no son de estos dos bloques) se calculan
con el MISMO motor de siempre (calma_suggest), para no tocar ninguna otra regla.
"""
import copy
from typing import Dict, List, Optional, Tuple

from calma_engine import _calibracion_cereales_panes, _calibracion_frutos_secos
from calma_suggest import aplicar_regla_macros, macros_at, food_in_any, _per100

CATS_CEREAL_PAN = ["7", "8"]
CATS_EXCEPCION_PROTEICA = ["7.1.3", "8.8"]  # P siempre al 100 %, sin calibración
CATS_FRUTOS_SECOS = ["17.2.1", "17.2.3", "17.2.4", "17.2.6"]


def clasificar_bloque(food: dict) -> Optional[str]:
    """'cereal_pan' | 'fruto_seco' | None (no participa en la calibración)."""
    if food_in_any(food, CATS_FRUTOS_SECOS):
        return "fruto_seco"
    if food_in_any(food, CATS_CEREAL_PAN):
        return "cereal_pan"
    return None


def _base_regla(food: dict) -> dict:
    """Copia del alimento con las reglas de categoría aplicadas y SIN el ajuste
    por cantidad legado de Calma (la calibración progresiva lo sustituye para
    los dos bloques; para el resto de alimentos no se llama a esta función)."""
    fc = copy.deepcopy(food)
    aplicar_regla_macros(fc)
    fc.pop("_ajuste", None)
    return fc


def macros_item_calibrados(food: dict, cantidad_g: float,
                           pct_cp: float, pct_fs: float) -> Dict[str, float]:
    """Macros efectivos {P,H,G} de UN alimento aplicando la calibración del día.

    `pct_cp` / `pct_fs`: porcentaje (0 / 0.5 / 1.0) del tramo asignado a la
    COMIDA a la que pertenece el alimento. Alimentos fuera de los dos bloques
    van por el motor de siempre, intacto."""
    bloque = clasificar_bloque(food)
    es_unidad = bool(food.get("unidades"))
    racion = float(food.get("racion") or 100) or 100.0
    cant_motor = (cantidad_g / racion) if es_unidad else cantidad_g

    if bloque is None:
        fc = copy.deepcopy(food)
        aplicar_regla_macros(fc)  # con su _ajuste legado: cero cambios fuera de los bloques
        m = macros_at(fc, cant_motor)
        return {"P": round(m["proteinas"], 2), "H": round(m["hidratos"], 2),
                "G": round(m["grasas"], 2)}

    fc = _base_regla(food)
    m = macros_at(fc, cant_motor)  # H y G según las reglas de categoría de siempre
    p100 = _per100(food, "proteinas")
    h100 = _per100(food, "hidratos")
    g100 = _per100(food, "grasas")
    factor = cantidad_g / 100.0

    if bloque == "cereal_pan":
        if food_in_any(food, CATS_EXCEPCION_PROTEICA):
            p_ef = p100 * factor  # proteicos: siempre al 100 %
        elif h100 > 0 and p100 > h100 / 3.0:
            p_ef = p100 * factor * pct_cp
        else:
            p_ef = 0.0  # no pasa el ratio: su proteína no cuenta nunca
        return {"P": round(p_ef, 2), "H": round(m["hidratos"], 2),
                "G": round(m["grasas"], 2)}

    # fruto_seco: G siempre (regla de categoría); P y H con gate G/3 + tramo
    p_ef = p100 * factor * pct_fs if (g100 > 0 and p100 > g100 / 3.0) else 0.0
    h_ef = h100 * factor * pct_fs if (g100 > 0 and h100 > g100 / 3.0) else 0.0
    return {"P": round(p_ef, 2), "H": round(h_ef, 2), "G": round(m["grasas"], 2)}


def pcts_por_comida(meals: List[Tuple[str, List[Tuple[dict, float]]]]) -> Dict[str, dict]:
    """Recorre las comidas EN ORDEN CRONOLÓGICO y asigna a cada una su tramo.

    `meals`: [(meal_key, [(food, cantidad_g), ...]), ...]
    La comida entera recibe el tramo del acumulado TRAS sumar sus gramos."""
    out: Dict[str, dict] = {}
    acum_cp = 0.0
    acum_fs = 0.0
    for key, items in meals:
        g_cp = sum(c for f, c in items if clasificar_bloque(f) == "cereal_pan")
        g_fs = sum(c for f, c in items if clasificar_bloque(f) == "fruto_seco")
        acum_cp += g_cp
        acum_fs += g_fs
        out[key] = {
            "pct_cp": _calibracion_cereales_panes(acum_cp),
            "pct_fs": _calibracion_frutos_secos(acum_fs),
            "acum_cp": round(acum_cp, 1),
            "acum_fs": round(acum_fs, 1),
        }
    return out


def calibrar_dia(meals: List[Tuple[str, List[Tuple[dict, float]]]]):
    """Calibra un día completo. Devuelve (macros_por_comida, pcts_por_comida):
    macros_por_comida[key] = [{P,H,G} por item, en el mismo orden de entrada]."""
    pcts = pcts_por_comida(meals)
    macros: Dict[str, list] = {}
    for key, items in meals:
        p = pcts[key]
        macros[key] = [macros_item_calibrados(f, c, p["pct_cp"], p["pct_fs"])
                       for f, c in items]
    return macros, pcts
