"""Calibración progresiva de la proteína vegetal por TOTAL DEL DÍA.

Spec del usuario (17-07-2026): la calculadora ya aplica todas las reglas por
categoría; esta es LA regla que faltaba en el conteo real de la app.

  - Bloque 1 · cereales + panes (cat 7 y 8, total CONJUNTO):
      H cuenta siempre. P solo si P > H/3 (por 100 g); cuando aplica, cuenta al
      0 % / 50 % / 100 % según el total del día (0-50 / 50-100 / >100 g).
      Excepción: 7.1.3 y 8.8 (proteicos) -> P siempre al 100 %.
      La grasa sigue su regla de categoría normal (no es calibración).
  - Bloque 2 · frutos secos naturales (17.2.1/17.2.3/17.2.4/17.2.6, total PROPIO):
      G cuenta siempre. P y H solo si superan G/3 (por 100 g); cuando aplican,
      cuentan al 0 % / 50 % / 100 % según su total (0-20 / 20-40 / >40 g).

Reglas críticas:
  - El contador suma GRAMOS de ese tipo de alimento (unidades -> n x ración).
  - El tramo lo decide el TOTAL DEL DÍA de esa familia, y es el mismo para todas
    las comidas: así el resultado depende de lo que se come y no del orden en que
    se monten las comidas (decisión de Jesús del 13-08-2026, ver `pcts_por_comida`).
  - Por eso una comida SÍ puede cambiar al editar otra, incluso anterior: el día
    es uno. Antes no pasaba, y ese era justo el problema.
  - El total nace de las comidas de ESE día: se "reinicia" solo a las 00:00
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

# Categorías donde la proteína cuenta siempre al 100 %, por estar formulada para eso.
# En doble categoría gana la más permisiva (doc del 07-08): un alimento que sea cereal o pan
# y ADEMÁS proteína en polvo o vegetal se salta la calibración entera, porque su proteína no
# es la incidental de un cereal, es la que le han puesto a propósito.
CATS_SIEMPRE_AL_100 = ["4", "28"]


def cuenta_siempre_al_100(food: dict) -> bool:
    """El alimento tiene proteína añadida a propósito, así que no se calibra."""
    return food_in_any(food, CATS_EXCEPCION_PROTEICA) or food_in_any(food, CATS_SIEMPRE_AL_100)


def clasificar_bloque(food: dict) -> Optional[str]:
    """'cereal_pan' | 'fruto_seco' | None (no participa en la calibración).

    Ojo: el que cuenta siempre al 100 % SÍ se clasifica en su bloque, porque tiene que seguir
    sumando al acumulado del día. Lo que se salta es la calibración de su proteína, y eso se
    resuelve luego, en `macros_item_calibrados`.
    """
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


def _por_100_de_etiqueta(food: dict) -> Tuple[float, float, float]:
    """Los macros por 100 g del alimento tal y como vienen en su etiqueta (P, H, G).

    La regla del tercio se mide SIEMPRE sobre estos, nunca sobre lo que quede después de
    aplicar las reglas de categoría ni sobre el porcentaje del tramo. Ese es el orden que
    fija el doc del 07-08: el filtro va antes de calibrar, y si se hace al revés los
    números salen distintos.

    Por eso, si el alimento ya pasó por `aplicar_regla_macros` (que pone a cero lo que no
    cuenta), se leen los originales que aquella guardó en `_per100_orig`. Sin esto, unas
    almendras que llegaran ya "reguladas" perderían sus 21 g de proteína: la regla de
    categoría se los había puesto a cero, y el tercio los habría dado por no existentes.
    """
    orig = food.get("_per100_orig")
    if orig:
        return (float(orig.get("proteinas") or 0), float(orig.get("hidratos") or 0),
                float(orig.get("grasas") or 0))
    return (_per100(food, "proteinas"), _per100(food, "hidratos"), _per100(food, "grasas"))


def la_proteina_llega_al_tercio(food: dict) -> bool:
    """¿La proteína de este alimento cuenta ALGUNA VEZ, comas lo que comas?

    Es la puerta de entrada de la calibración, y estaba escondida dentro del cálculo:
    antes del tramo hay un filtro que exige que la proteína llegue a un tercio del macro
    dominante de su bloque (los hidratos en cereales y panes, la grasa en frutos secos).
    Si no llega, esa proteína NO cuenta nunca, y el tramo da igual.

    Se saca aquí para que la pantalla pueda decirlo (punto 133 del artifact del 26-08): el
    cartel de «frutos secos hoy: 25 de 40 g · su proteína te cuenta a la mitad» le salía a
    TODOS los frutos secos por igual, y a las nueces (23 %) o al cóctel (30,5 %) les
    prometía una proteína que aporta 0. «Que salga sólo en los que llegan al tercio. A los
    demás, una sola frase y para siempre: su proteína no te cuenta.»

    Devuelve True también para los que cuentan siempre al 100 (proteínas en polvo y
    vegetales en doble categoría): a ésos no se les aplica ni filtro ni tramo.
    """
    bloque = clasificar_bloque(food)
    if bloque is None:
        return True                       # fuera de los bloques no hay puerta que pasar
    if cuenta_siempre_al_100(food):
        return True
    p100, h100, g100 = _por_100_de_etiqueta(food)
    if bloque == "cereal_pan":
        return h100 > 0 and p100 > h100 / 3.0
    return g100 > 0 and p100 > g100 / 3.0


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
    p100, h100, g100 = _por_100_de_etiqueta(food)
    factor = cantidad_g / 100.0

    # Proteína puesta a propósito: ni filtro del tercio ni tramo. Vale para los cereales y
    # panes proteicos de siempre y, desde el doc del 07-08, para cualquier alimento de un
    # bloque calibrado que sea ADEMÁS proteína en polvo o vegetal: en doble categoría gana la
    # más permisiva. Sigue sumando al acumulado del día, eso no cambia.
    if cuenta_siempre_al_100(food):
        return {"P": round(p100 * factor, 2), "H": round(m["hidratos"], 2),
                "G": round(m["grasas"], 2)}

    if bloque == "cereal_pan":
        if h100 > 0 and p100 > h100 / 3.0:
            p_ef = p100 * factor * pct_cp
        else:
            p_ef = 0.0  # no pasa el ratio: su proteína no cuenta nunca
        return {"P": round(p_ef, 2), "H": round(m["hidratos"], 2),
                "G": round(m["grasas"], 2)}

    # fruto_seco: G siempre (regla de categoría); P y H con gate G/3 + tramo
    p_ef = p100 * factor * pct_fs if (g100 > 0 and p100 > g100 / 3.0) else 0.0
    h_ef = h100 * factor * pct_fs if (g100 > 0 and h100 > g100 / 3.0) else 0.0
    return {"P": round(p_ef, 2), "H": round(h_ef, 2), "G": round(m["grasas"], 2)}


def totales_del_dia(meals: List[Tuple[str, List[Tuple[dict, float]]]]) -> Tuple[float, float]:
    """Gramos de cada familia calibrada en TODO el día: (cereales+panes, frutos secos)."""
    total_cp = sum(c for _, items in meals for f, c in items
                   if clasificar_bloque(f) == "cereal_pan")
    total_fs = sum(c for _, items in meals for f, c in items
                   if clasificar_bloque(f) == "fruto_seco")
    return total_cp, total_fs


def pcts_por_comida(meals: List[Tuple[str, List[Tuple[dict, float]]]]) -> Dict[str, dict]:
    """El tramo sale del TOTAL DEL DÍA, y es el mismo para todas las comidas.

    `meals`: [(meal_key, [(food, cantidad_g), ...]), ...]

    ANTES ERA UNA CUENTA CORRIENTE, Y DEPENDÍA DEL ORDEN (13-08-2026). Cada comida cobraba
    el tramo del acumulado que llevaba el día HASTA ELLA, así que el mismo día montado en
    distinto orden daba números distintos. Jesús, con su ejemplo: 45 g de almendras, 30 en
    la comida 3 y 15 en la comida 1.

        montando en orden          C1 lleva 15 g -> 0 %    C3 lleva 45 g -> 100 %
        empezando por el gimnasio  C3 lleva 30 g -> 50 %   C1 lleva 45 g -> 100 %

    Reproducido con el motor real y las almendras del catálogo (P23/100 g): en el primer
    caso la Comida 1 cuenta 0,00 g de proteína y en el segundo 3,45 g. Mismos gramos, misma
    comida, y el cliente no ha hecho nada raro. Y no es solo el reparto: con 25 g en C1 y 5
    en C3 el TOTAL del día pasa de 3,45 g a 2,88 g solo por cambiar el orden.

    Ahora el porcentaje depende de lo que come, y de nada más: se suman los gramos del día
    entero de cada familia y ese total decide el tramo, igual para todas las comidas. Se
    pierde a cambio la propiedad de que editar una comida no tocaba las anteriores -- ahora
    puede cambiarlas, porque el día es uno --, que era justo lo que producía el problema.

    Los tramos siguen siendo los de siempre (frutos secos 20/40 g, cereales y panes
    50/100 g) y ninguna otra regla se toca: el filtro del tercio se sigue midiendo antes,
    sobre los macros de etiqueta.
    """
    total_cp, total_fs = totales_del_dia(meals)
    pct_cp = _calibracion_cereales_panes(total_cp)
    pct_fs = _calibracion_frutos_secos(total_fs)
    # `acum_*` pasa a ser el total del día: es el número que se le enseña al cliente en la
    # línea del alimento («frutos secos hoy: 15 de 20 g») y el que decide el tramo.
    return {key: {"pct_cp": pct_cp, "pct_fs": pct_fs,
                  "acum_cp": round(total_cp, 1), "acum_fs": round(total_fs, 1)}
            for key, _ in meals}


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


def macros_item_por_acumulado(food: dict, cantidad_g: float,
                              acum_cp: float = 0.0, acum_fs: float = 0.0) -> Dict[str, float]:
    """Macros efectivos de UN alimento a partir de los gramos que ya lleva el día.

    Para quien va añadiendo alimento a alimento (el chat) y todavía no tiene el día
    completo montado. El tramo sale del total TRAS sumar esta cantidad, que es el mismo
    criterio de `pcts_por_comida`: lo que decide es el día entero.

    `acum_*` tiene que ser el total del DÍA de esa familia, no el de las comidas
    anteriores a esta. El chat lo lleva así (`state["acumulado_*"]`) y además vuelve a
    calibrar el día completo tras cada cambio (`_recalibrar_dia`), que es lo que deja
    todas las comidas con el mismo tramo cuando el día ya está montado.

    Sustituye a `calma_engine.calcular_macros_efectivos_alimento`: por debajo cuenta con
    el motor fiel a Calma (`calma_suggest`) en vez del legado.
    """
    bloque = clasificar_bloque(food)
    pct_cp = _calibracion_cereales_panes(acum_cp + (cantidad_g if bloque == "cereal_pan" else 0))
    pct_fs = _calibracion_frutos_secos(acum_fs + (cantidad_g if bloque == "fruto_seco" else 0))
    return macros_item_calibrados(food, cantidad_g, pct_cp, pct_fs)
