"""Redondeo de las cantidades que se le enseñan al cliente (punto 4 del doc del 07-08).

Regla de Jesús: los números que se le dan a un cliente son redondos. Nadie pesa 223 g de
pechuga ni 42 g de proteína en polvo.

  - Alimentos por unidades .......... unidades enteras o medias
  - Verduras y bebidas vegetales .... múltiplos de 50 g
  - Salsas .......................... múltiplos de 5 g
  - Todo lo demás ................... múltiplos de 5 g
  - Macros del día .................. proteína y grasa enteras, hidratos de 5 en 5

Dos decisiones que conviene tener claras:

**Se redondea al SALIR, no durante el cálculo.** Los motores (`calma_suggest`,
`meal_templates`) siguen trabajando con la cantidad exacta; esto se aplica encima, justo
antes de entregar el número. Si se redondease dentro, cada paso intermedio arrastraría su
propio error y el resultado final se desviaría de los macros objetivo.

**Siempre a la baja.** Redondear hacia arriba haría que el alimento aportase más de lo que
queda de esa comida, que es justo lo que el motor evita. Quedarse corto se absorbe con el
resto del menú; pasarse descuadra el día. La calculadora antigua hacía lo mismo, pero con un
parámetro llamado `redondear` que redondeaba a la baja siempre, con nombre y todo: aquí va
explícito en el nombre de la función.
"""
import math
from typing import Dict, Optional

# Verduras y hortalizas (13) y bebidas vegetales (24): se manejan en cantidades grandes,
# así que 50 g. Konjac (16.4) va con ellas por lo mismo, no porque sea una salsa.
PASO_50 = ("13", "24", "16.4")
PASO_GENERAL = 5.0          # salsas y todo lo demás
UNIDADES_POR_PASO = 0.5     # unidades enteras o medias


def _categorias(food: dict) -> list:
    crudo = food.get("categorias", "") or ""
    if isinstance(crudo, list):
        return [str(c).strip() for c in crudo]
    return [c.strip() for c in str(crudo).split("|")]


def _en_alguna(food: dict, codigos) -> bool:
    """True si el alimento está en alguno de esos códigos o en una subcategoría suya."""
    for token in _categorias(food):
        for codigo in codigos:
            if token == codigo or token.startswith(codigo + "."):
                return True
    return False


# ── Lo mínimo que se puede pesar en una cocina ──────────────────────────────────────────
#
# Jesús, 15-08-2026 (fallo 29): «Cuadrar» dejó el aguacate en 5 g y el yogur en 30. «5 gramos
# de aguacate es media cucharadita; 30 g de yogur son dos cucharadas. Nadie pesa eso: el
# cliente pone "un poco" y el cálculo se va». Redondear de 5 en 5 no bastaba, porque 5 es un
# múltiplo de 5 perfectamente válido: lo que faltaba era un SUELO.
#
# Hay alimentos que sí se usan a cucharaditas y de los que 5 o 10 g es la cantidad normal: el
# aceite, las salsas, el azúcar y la miel, los polvos (proteína, cacao, crema de arroz) y los
# suplementos. Esos conservan su mínimo de siempre. Los que se comen a cucharadas o a
# rodajas -- aguacate, yogur, arroz, carne -- no bajan de 20 g.
#
# Los de unidades no entran aquí: su cantidad mínima ya es una unidad, que es lo más pesable
# que hay ("un huevo").
CATEGORIAS_DE_CUCHARADITA = ("4", "16", "17.1", "18", "27", "37", "41")
MINIMO_PESABLE = 20.0


def minimo_pesable(food: dict, minimo_config: float = 0.0) -> float:
    """El mínimo de `food`, subido a una cantidad que alguien pueda pesar de verdad."""
    minimo = float(minimo_config or 0)
    if food.get("unidades") or food.get("por_unidad"):
        return minimo
    if _en_alguna(food, CATEGORIAS_DE_CUCHARADITA):
        return minimo
    return max(minimo, MINIMO_PESABLE)


def paso_en_gramos(food: dict) -> float:
    """El múltiplo al que hay que redondear la cantidad de ESTE alimento, en gramos."""
    if food.get("unidades") or food.get("por_unidad"):
        racion = float(food.get("racion") or food.get("peso_unidad") or 0)
        if racion > 0:
            return racion * UNIDADES_POR_PASO
        return PASO_GENERAL
    if _en_alguna(food, PASO_50):
        return 50.0
    return PASO_GENERAL


def _bajar_al_multiplo(cantidad: float, paso: float) -> float:
    # Un pelín de tolerancia: 149.9999 salido de un float es un 150, no un 100.
    return round(math.floor(cantidad / paso + 1e-9) * paso, 2)


def redondear_a_la_baja(cantidad_g: float, paso: float, minimo_g: float = 0.0) -> float:
    """`cantidad_g` bajada al múltiplo de `paso` inmediatamente inferior.

    Con una salida para los pasos grandes: 30 g de una verdura (paso 50) no se pueden bajar
    a un múltiplo de 50 sin dejarlos en cero y hacer desaparecer el alimento del plato. En
    ese caso se cae al múltiplo de 5, que sigue siendo un número redondo. Y si ni eso llega
    al mínimo del alimento, se deja la cantidad como venía: falsearla sería peor que tener
    un número feo.
    """
    cantidad = float(cantidad_g or 0)
    if paso <= 0 or cantidad <= 0:
        return cantidad
    minimo = float(minimo_g or 0)
    bajado = _bajar_al_multiplo(cantidad, paso)
    if bajado >= minimo and bajado > 0:
        return bajado
    if paso > PASO_GENERAL:
        bajado = _bajar_al_multiplo(cantidad, PASO_GENERAL)
        if bajado >= minimo and bajado > 0:
            return bajado
    return cantidad


def redondear_cantidad(food: dict, cantidad_g: float, minimo_g: Optional[float] = None) -> float:
    """La cantidad de `food` tal y como se le enseña al cliente."""
    return redondear_a_la_baja(cantidad_g, paso_en_gramos(food), minimo_g or 0.0)


def redondear_macros_dia(macros: Dict[str, float]) -> Dict[str, float]:
    """Los macros de un día: proteína y grasa enteras, hidratos de 5 en 5.

    Acepta las dos formas en las que viajan los macros por la app (`P`/`H`/`G` y
    `protein`/`carbs`/`fat` o `proteinas`/`hidratos`/`grasas`) y conserva el resto de claves
    tal cual (kcal y demás se recalculan donde toque, no aquí).
    """
    if not macros:
        return macros
    out = dict(macros)
    enteros = (("P", "protein", "proteinas"), ("G", "fat", "grasas"))
    for claves in enteros:
        for clave in claves:
            if out.get(clave) is not None:
                out[clave] = float(round(float(out[clave])))
    for clave in ("H", "carbs", "hidratos"):
        if out.get(clave) is not None:
            out[clave] = float(round(float(out[clave]) / 5.0) * 5)
    return out
