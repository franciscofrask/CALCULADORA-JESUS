"""
Faithful Python port of Calma's manual meal-builder suggestion engine.

Reverse-engineered from the production bundle:
  - Dieta.8ec0f1e0.js   (ajustarCantidadIngrediente, ordenarIngredientesPorMacro)
  - utils_.ac9d7b60.js   (H/cantidadMinima, ge/step, O lookup, Z/X maps, y/$ category match)
  - group-home-utils.e5bc7415.js (Qe=me, g=round-to-step, fe/Ze=diferenciaDeMacros, config T)

KEY FACTS (do not "simplify"):
  * Suggested quantity uses RAW macros for ALL THREE macros (P, H, G).
    me(remaining, perUnit) = min over {P,H,G} of remaining[m] / perUnit[m].
    The regla-25% / "macros efectivos" tables are ONLY for the auto-diet generator,
    NOT for manual suggestions.
  * For `unidades` foods the proteinas/hidratos/grasas fields are PER-UNIT totals and
    `racion` is grams per unit. For granel foods they are per-100g.
  * Display list is sorted by diferenciaDeMacros = Σ|contributed - remaining| ascending,
    then by name. (ordenarIngredientesPorMacro)
"""
import math
import unicodedata
from typing import Dict, List, Optional

INF = float("inf")

# ── Config constants (group-home-utils T) ──────────────────────────────────
MARGEN_VALIDO = 4
PORC_SUFICIENTE = 0.8
CANTIDAD_MINIMA_GRANEL = 5
STEP_GRANEL = 1

# ── Granel minimum-quantity map Z (utils_) ─────────────────────────────────
Z_MIN = {
    "1.1": 25, "2": 50, "2.1": 25, "3": 50, "4": 5, "5.1": 20, "5.2": 50,
    "5.3": 20, "5.6": 100, "6.1": 20, "6.2": 50, "7": 10, "7.2": 25, "7.3": 25,
    "7.6": 10, "8": 25, "8.4": 15, "9": 25, "10.2": 25, "10.3": 25, "11": 50,
    "11.3": 10, "11.5": 100, "11.7": 25, "11.9": 10, "13": 50, "15": 5, "16": 5,
    "16.1": 10, "16.4": 50, "17": 5, "17.1.2": 25, "17.6": 25, "17.7": 25,
    "17.9": 50, "18": 100, "18.3": 5, "18.4": 5, "19": 100, "19.3.3": 5,
    "21": 25, "21.3": 10, "22": 25, "24": 100, "25": 5, "27": 10, "28": 50,
    "32": 50, "34": 20, "35": 20, "36": 50, "37": 5, "38": 25, "39": 50,
    "41": 5, "43": 20,
}

# ── Granel step map X (utils_) ─────────────────────────────────────────────
X_STEP = {"13": 50, "16.1": 5, "16.4": 50, "16.5": 5, "24": 50}


# ── String / category helpers ──────────────────────────────────────────────
def _norm(s: str) -> str:
    """Calma h(): NFD strip accents, uppercase."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s or "")
        if unicodedata.category(c) != "Mn"
    ).upper()


def _name_match(nombre: str, needles: List[str], require_all: bool = False) -> bool:
    """Calma g()=P(): accent/case-insensitive substring match (any/all)."""
    n = _norm(nombre)
    tests = [_norm(x) in n for x in needles]
    return all(tests) if require_all else any(tests)


def _cats(food: dict) -> List[str]:
    return [t.strip() for t in str(food.get("categorias", "") or "").split("|")]


def _token_matches_code(token: str, code: str) -> bool:
    """Calma $(): token equals code OR token starts with code + '.<digit>'."""
    if token == code:
        return True
    return token.startswith(code + ".") and len(token) > len(code) + 1 and token[len(code) + 1].isdigit()


def food_in_cat(food: dict, code: str) -> bool:
    """Calma y(): any pipe-token of categorias matches code."""
    return any(_token_matches_code(t, code) for t in _cats(food))


def food_in_any(food: dict, codes: List[str]) -> bool:
    """Calma o()/ce(): food matches any of codes."""
    return any(food_in_cat(food, c) for c in codes)


# ── Regla de macros efectivos (Calma `ye`) ─────────────────────────────────
# A macro "counts" only if it is a meaningful share of the food. If it doesn't
# count, Calma zeroes it (e[t]=0) so it neither fills its target nor displays.
# This is THE missing piece that orders mixed-macro prepared foods: e.g. for a
# lean prepared chicken (cat 2, fat/100g < 3 and < 25% of the dominant macro)
# the grasas get zeroed, so the food no longer "fills" the fat target and ranks
# below a balanced dish (tikka) whose fat does count.
# Rule applies only to foods in these top-level categories (`ue`):
_UE = ["1", "2", "3", "4", "5", "7", "8", "9", "10", "11", "13", "16", "17",
       "19", "21", "22", "24", "36", "37", "38.1", "41", "48"]


def _per100(food: dict, key: str) -> float:
    v = float(food.get(key) or 0)
    if food.get("unidades"):
        rac = float(food.get("racion") or 100)
        return v * 100.0 / rac if rac else 0.0
    return v


def aplicar_regla_macros(food: dict) -> None:
    """Calma ye(): zero non-counting macros in place (regla 25% + category rules).
    Also sets food['_ajuste'] for cereals/breads/nuts (quantity-dependent counting).
    `r` (per-100g) is snapshotted from the ORIGINAL macros; conditions use it."""
    if not food_in_any(food, _UE):
        return
    r = {"proteinas": _per100(food, "proteinas"),
         "hidratos": _per100(food, "hidratos"),
         "grasas": _per100(food, "grasas")}
    n = max(r["proteinas"], r["hidratos"], r["grasas"])
    o = lambda lst: food_in_any(food, lst)
    d = lambda c: food_in_cat(food, c)
    rH = r["hidratos"]

    # HIDRATOS
    rt = r["hidratos"]
    if (rt * 4 < n or o(["13", "16", "17", "36"])) and (
            o(["17.1", "17.4", "17.6", "17.10", "41"]) or
            (o(["1", "2", "3", "36", "48"]) and rt <= 2) or
            (d("3.9") and rt <= 3) or
            (o(["4", "16"]) and rt < 6) or
            (d("8") and rt <= 8) or
            (d("13") and rt < 4) or
            (o(["17.2.1", "17.2.3", "17.2.4", "17.5.3"]) and rt * 2 <= n) or
            (d("19.2") and rt <= 0.5)):
        food["hidratos"] = 0

    # GRASAS
    rt = r["grasas"]
    if (rt * 4 < n or o(["13", "16"])) and (
            o(["9", "11", "41"]) or
            (o(["1", "2", "3", "13.9", "19"]) and rt < 3) or
            (o(["4", "16", "21"]) and rt < 6) or
            (d("5") and rt < 1) or
            (d("7") and not (rt > 8 or rt * 4 > rH)) or
            (o(["8"]) and rt * 4 <= rH) or
            (o(["8", "22"]) and rt <= 9 and not o(["22.1.2.2", "22.6", "22.7"])) or
            (d("10") and rt <= 8) or
            (d("13") and rt <= 1) or
            (d("22") and rt * 3 <= rH and not o(["22.1.2.2", "22.6", "22.7"])) or
            (o(["22.6"]) and rt < 2) or
            (d("37") and rt <= 10) or
            (d("48") and rt < 2)):
        food["grasas"] = 0

    # PROTEINAS
    rt = r["proteinas"]
    if (rt * 4 < n or o(["13", "16", "17", "19", "24", "36"])) and (
            o(["9", "11", "17.1", "17.4", "17.6", "17.10", "21"]) or
            (o(["7", "8", "22"]) and rt * 3 <= rH and not o(["22.1.2.2", "22.6", "22.7"])) or
            (d("13") and not d("13.9")) or
            (o(["13.9"]) and rt * 4 <= rH) or
            (d("16") and rt < 6) or
            (o(["17.2", "17.5", "17.7", "37", "38.1"]) and rt * 2 <= n and not o(["17.2.6", "17.5.3"])) or
            (o(["19", "36"]) and rt <= 2) or
            (d("22.6") and rt < 5) or
            (d("24") and rt < 1) or
            (d("48") and rt < 2)):
        food["proteinas"] = 0

    # ajustePorCantidad (quantity-dependent zeroing) for cereals/breads/nuts
    if o(["7", "8"]):
        food["_ajuste"] = {"umbral": 100, "preds": [("proteinas", r["proteinas"] * 3 < n)]}
    elif o(["17.2.1", "17.2.3", "17.2.4"]):
        food["_ajuste"] = {"umbral": 50, "preds": [
            ("proteinas", (r["proteinas"] * 4) / 3 < n),
            ("hidratos", (r["hidratos"] * 4) / 3 < n)]}


def _o_lookup(token: str, table: Dict[str, float]) -> Optional[float]:
    """Calma O(): exact then recursive parent (strip last .segment)."""
    if token in table:
        return table[token]
    if "." in token:
        return _o_lookup(token.rsplit(".", 1)[0], table)
    return None


# ── Per-unit / per-gram raw macros ─────────────────────────────────────────
def _raw(food: dict) -> Dict[str, float]:
    return {
        "proteinas": float(food.get("proteinas") or 0),
        "hidratos": float(food.get("hidratos") or 0),
        "grasas": float(food.get("grasas") or 0),
    }


def macros_at(food: dict, cantidad: float) -> Dict[str, float]:
    """Calma K(): macros contributed at `cantidad` (units if unidades else grams).
    Honors `_ajuste` (ajustePorCantidad) - quantity-dependent macro zeroing for
    cereals/breads/nuts: below the gram threshold the flagged macros don't count."""
    s = cantidad if food.get("unidades") else cantidad / 100.0
    r = _raw(food)
    aj = food.get("_ajuste")
    if aj:
        grams = cantidad * float(food.get("racion") or 100) if food.get("unidades") else cantidad
        if grams <= aj["umbral"]:
            for macro, pred in aj["preds"]:
                if pred:
                    r[macro] = 0.0
    return {k: v * s for k, v in r.items()}


def _macros_per_step(food: dict) -> Dict[str, float]:
    """q(e) at cantidad=1: per-unit (unidades) or per-gram (granel)."""
    return macros_at(food, 1)


# ── me(): maximum quantity before exceeding any remaining macro ─────────────
def _me_max(remaining: Dict[str, float], per: Dict[str, float]) -> float:
    """Calma Qe(): min over macros of remaining/per. 0/0 -> ignored; x/0 -> inf."""
    ratios = []
    for k, pv in per.items():
        rv = remaining.get(k, INF)
        if pv == 0:
            if rv == 0:
                continue  # 0/0 -> NaN, ignored
            ratios.append(INF)
        else:
            ratios.append(rv / pv)
    return min(ratios) if ratios else INF


# ── cantidad minima / step (utils_ H) ──────────────────────────────────────
def _H(food: dict, table: Dict[str, float], default: float) -> float:
    if food.get("unidades"):
        nombre = food.get("nombre", "")
        if (_name_match(nombre, ["hamburguesa", "bagel"]) or
                _name_match(nombre, ["brazo", "My Fitness Meals"], True) or
                _name_match(nombre, ["bizcocho", "My Fitness Meals"], True) or
                food_in_cat(food, "11.1") or
                _name_match(nombre, ["arroz", "minuto"], True)):
            return 0.5
        return 1
    for token in _cats(food):
        t = _o_lookup(token, table)
        if t:
            return t
    return default


def cantidad_minima(food: dict) -> float:
    """utils_ me(): food.minimo or H(food, Z, 5)."""
    if food.get("minimo"):
        return float(food["minimo"])
    return _H(food, Z_MIN, CANTIDAD_MINIMA_GRANEL)


def step_granel(food: dict) -> float:
    """utils_ ge(): H(food, X, 1)."""
    return _H(food, X_STEP, STEP_GRANEL)


def _round_step(x: float, step: float, floor: bool = True) -> float:
    """Calma g(): t=x%step; x + (-t if t<step/2 or floor else step-t)."""
    if step == 0:
        return x
    t = math.fmod(x, step)
    if t < step / 2 or floor:
        return x - t
    return x + (step - t)


# ── ajustarCantidadIngrediente: the suggested quantity ─────────────────────
def ajustar_cantidad(food: dict, remaining: Dict[str, float]) -> float:
    """
    Returns suggested quantity (units if unidades else grams), or 0 to exclude.
    Mirrors Dieta.js ajustarCantidadIngrediente exactly.
    """
    rem = {k: (0 if (v is not None and v < 0) else v) for k, v in remaining.items()}
    per = _macros_per_step(food)
    s = _me_max(rem, per)
    if s == INF:
        # No constraining macro (zero-macro food). Calma fallback.
        if food_in_any(food, ["13", "16.4"]):
            return 100.0
        return cantidad_minima(food) or 100.0
    a = cantidad_minima(food)
    d = step_granel(food)
    if food.get("unidades") and a < s < d:
        cant = a
    else:
        cant = _round_step(s, d, floor=True)
    if a > cant:
        return 0.0
    return cant


# ── diferenciaDeMacros: ordering key ───────────────────────────────────────
def diferencia_de_macros(contributed: Dict[str, float], remaining: Dict[str, float]) -> float:
    """Calma Ze(): Σ|contributed - remaining| over P,H,G. Lower = better fit."""
    total = 0.0
    for k in ("proteinas", "hidratos", "grasas"):
        rv = remaining.get(k, 0)
        cv = contributed.get(k, 0)
        if rv == INF:
            # Unconstrained macro contributes nothing to the distance.
            continue
        total += abs(cv - rv)
    return total


# ── Phase selection (filtroParaAplicar) ────────────────────────────────────
def hay_suficiente(actual: float, objetivo: float) -> bool:
    if not objetivo:
        return True
    return actual / objetivo > PORC_SUFICIENTE
