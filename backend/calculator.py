"""
Calculator Module — Ajuste automático de cantidades y validación
================================================================
Cuando el usuario añade un alimento a una comida, este módulo calcula
automáticamente cuántos gramos poner para cuadrar los macros.
"""

from typing import Dict, List, Optional, Tuple
from calma_engine import calcular_macros_efectivos_alimento as calcular_macros_efectivos, que_macros_cuentan
import math


# =====================================================
# TABLA DE REDONDEO POR CATEGORÍA
# =====================================================
# Clave: patrón de categoría → (múltiplo, es_unidades)

REDONDEO = {
    "1.1": 50,       # Claras: múltiplos de 50g
    "1.2": None,     # Huevos: unidades (usar racion)
    "2.1": 25,       # Fiambres/embutidos: múltiplos de 25g
    "2": 25,         # Carnes: múltiplos de 25g
    "3": 25,         # Pescados: múltiplos de 25g
    "4": 5,          # Proteína en polvo: múltiplos de 5g
    "5.1": 50,       # Leche: múltiplos de 50ml
    "5.2": 50,       # Yogures: múltiplos de 50g
    "5.3": 50,       # Quesos batidos: múltiplos de 50g
    "7.4": None,     # Tortitas arroz: unidades
    "7.5": None,     # Tortitas maíz: unidades
    "7.6": None,     # Tortitas: unidades
    "7": 10,         # Cereales/avena: múltiplos de 10g
    "8": 10,         # Panes: múltiplos de 10g
    "9": 25,         # Tubérculos: múltiplos de 25g
    "10": 25,        # Legumbres: múltiplos de 25g
    "11.1": None,    # Fruta fresca: medias unidades
    "11": 10,        # Resto fruta/zumos: múltiplos de 10g
    "13": 50,        # Verduras: múltiplos de 50g
    "17.1": 5,       # Aceites: múltiplos de 5ml
    "17.2": 5,       # Frutos secos/semillas/cremas: múltiplos de 5g
    "21": 25,        # Arroces: múltiplos de 25g
    "22": 10,        # Pasta: múltiplos de 10g
    "24": 50,        # Bebidas vegetales: múltiplos de 50ml
    "45": 25,        # Otras carnes: múltiplos de 25g
}

DEFAULT_REDONDEO = 10  # Para categorías no listadas


def _get_cat_principal(categorias_str: str) -> str:
    """Extrae la categoría numérica principal de un alimento."""
    if not categorias_str:
        return ""
    parts = [c.strip() for c in categorias_str.split("|")]
    for p in parts:
        if p and p[0].isdigit():
            return p
    return ""


def _get_multiplo_redondeo(cat_principal: str, alimento: dict) -> int:
    """
    Determina el múltiplo de redondeo para un alimento.
    Si es de unidades, devuelve None (se redondea a múltiplos de ración).
    """
    es_unidades = alimento.get("unidades", False)
    if es_unidades:
        return None  # Se maneja aparte

    # Buscar en la tabla de redondeo, de más específico a más general
    # Ejemplo: "2.1" matchea antes que "2"
    for pattern in sorted(REDONDEO.keys(), key=len, reverse=True):
        if cat_principal == pattern or cat_principal.startswith(pattern + "."):
            return REDONDEO[pattern]

    return DEFAULT_REDONDEO


def redondear_cantidad(cantidad: float, alimento: dict) -> float:
    """
    Redondea la cantidad al múltiplo lógico según el tipo de alimento.
    Si es de unidades, redondea a múltiplos de ración.
    Para fruta fresca (11.1), redondea a medias unidades.
    """
    racion = alimento.get("racion", 100) or 100
    es_unidades = alimento.get("unidades", False)
    cat = _get_cat_principal(alimento.get("categorias", ""))

    if es_unidades:
        # Redondear a múltiplos de ración (unidades enteras)
        if racion <= 0:
            return max(cantidad, 1)
        unidades = cantidad / racion
        # Para fruta fresca y algunos especiales: permitir medias unidades
        if cat.startswith("11.1"):
            unidades_redondeadas = round(unidades * 2) / 2  # 0.5, 1, 1.5, 2...
            unidades_redondeadas = max(unidades_redondeadas, 0.5)
        else:
            # Verificar si permite medias unidades
            nombre = (alimento.get("nombre", "") or "").lower()
            permite_media = any(x in nombre for x in ["hamburguesa", "bagel"])
            if cat.startswith("11.1") or permite_media:
                unidades_redondeadas = round(unidades * 2) / 2
                unidades_redondeadas = max(unidades_redondeadas, 0.5)
            else:
                unidades_redondeadas = max(round(unidades), 1)

        return unidades_redondeadas * racion

    # Para alimentos en gramos
    multiplo = _get_multiplo_redondeo(cat, alimento)
    if multiplo is None:
        multiplo = racion  # Usar ración como múltiplo

    if multiplo <= 0:
        multiplo = DEFAULT_REDONDEO

    # Redondear al múltiplo más cercano
    redondeado = round(cantidad / multiplo) * multiplo

    # Aplicar mínimo
    minimo = alimento.get("minimo")
    if minimo and redondeado < minimo:
        redondeado = minimo

    # Nunca devolver 0 o negativo
    if redondeado <= 0:
        redondeado = multiplo

    return redondeado


def calcular_cantidad_automatica(
    alimento: dict,
    macros_restantes: Dict[str, float],
    es_vegano: bool = False
) -> Dict:
    """
    FUNCIÓN PRINCIPAL — Calcula cuántos gramos de un alimento poner
    para cuadrar los macros restantes de una comida.

    Args:
        alimento: dict del alimento de la BD
        macros_restantes: {"P": 12.0, "H": 6.0, "G": 3.0} — lo que FALTA en la comida
        es_vegano: modo vegano

    Returns:
        {
            "cantidad_g": 150.0,
            "macros_efectivos": {"P": 31.5, "H": 0, "G": 0, "kcal": 126},
            "macros_brutos": {"P": 31.5, "H": 0, "G": 2.25, "kcal": 146.3},
            "que_cuenta": {"P": true, "H": false, "G": false},
            "cabe": true,
            "advertencia": null
        }
    """
    racion = alimento.get("racion", 100) or 100
    es_unidades = alimento.get("unidades", False)
    minimo = alimento.get("minimo")

    # Macros por ración
    P_base = float(alimento.get("proteinas", 0) or 0)
    H_base = float(alimento.get("hidratos", 0) or 0)
    G_base = float(alimento.get("grasas", 0) or 0)

    # Macros por 100g (para reglas CALMA y cálculos)
    if racion > 0:
        P_100 = P_base * 100.0 / racion
        H_100 = H_base * 100.0 / racion
        G_100 = G_base * 100.0 / racion
    else:
        P_100 = P_base
        H_100 = H_base
        G_100 = G_base

    # Qué macros cuentan
    cuenta = que_macros_cuentan(alimento, racion, es_vegano)

    P_rest = macros_restantes.get("P", 0)
    H_rest = macros_restantes.get("H", 0)
    G_rest = macros_restantes.get("G", 0)

    MARGEN = 4.0  # margen aceptable

    # PASO 1: Identificar el macro dominante del alimento (el que cuenta y es mayor)
    macros_que_cuentan = {}
    if cuenta["P"] and P_100 > 0:
        macros_que_cuentan["P"] = P_100
    if cuenta["H"] and H_100 > 0:
        macros_que_cuentan["H"] = H_100
    if cuenta["G"] and G_100 > 0:
        macros_que_cuentan["G"] = G_100

    if not macros_que_cuentan:
        # Alimento sin macros que cuentan → poner mínimo
        cantidad = float(minimo) if minimo else float(racion)
        cantidad = redondear_cantidad(cantidad, alimento)
        return _build_result(alimento, cantidad, es_vegano, cabe=True, advertencia="Sin macros que cuenten")

    # PASO 2: Determinar por qué macro ajustar
    # Buscar el macro que más falta Y que el alimento aporta
    mejor_macro = None
    mejor_necesidad = -999

    restantes = {"P": P_rest, "H": H_rest, "G": G_rest}

    for macro, valor_100 in macros_que_cuentan.items():
        necesidad = restantes[macro]
        if necesidad > mejor_necesidad:
            mejor_necesidad = necesidad
            mejor_macro = macro

    # Si todos los macros que aporta ya están cubiertos (restante <= 0),
    # ajustar por el que menos se pase
    if mejor_necesidad <= 0:
        # El alimento no cabe bien, poner mínimo
        cantidad = float(minimo) if minimo else float(racion)
        cantidad = redondear_cantidad(cantidad, alimento)
        return _build_result(alimento, cantidad, es_vegano, cabe=False,
                           advertencia="Macros ya cubiertos para este alimento")

    # PASO 3: Calcular cantidad ideal para cubrir el macro dominante
    valor_100_dominante = macros_que_cuentan[mejor_macro]
    cantidad_ideal = (restantes[mejor_macro] / valor_100_dominante) * 100

    # PASO 4: Verificar que no sobrepasa otros macros
    for macro, valor_100 in macros_que_cuentan.items():
        if macro == mejor_macro:
            continue
        rest_macro = restantes[macro]
        if valor_100 > 0:
            # Máximo permitido: lo que falta + margen
            max_por_macro = ((rest_macro + MARGEN) / valor_100) * 100
            if max_por_macro < cantidad_ideal and max_por_macro > 0:
                cantidad_ideal = max_por_macro

    # PASO 5: Aplicar mínimo
    if cantidad_ideal < 0:
        cantidad_ideal = 0

    if minimo and cantidad_ideal < float(minimo):
        cantidad_ideal = float(minimo)

    # Para unidades: como mínimo 1 unidad (o media si fruta)
    if es_unidades and cantidad_ideal < racion * 0.5:
        cantidad_ideal = racion * 0.5

    # PASO 6: Redondear
    cantidad_final = redondear_cantidad(cantidad_ideal, alimento)

    # PASO 7: Verificar si cabe (después de redondear)
    macros_ef = calcular_macros_efectivos(alimento, cantidad_final, es_vegano)
    cabe = True
    advertencia = None

    for macro in ["P", "H", "G"]:
        macro_aportado = macros_ef[macro]
        macro_restante = restantes[macro]
        if macro_aportado > macro_restante + MARGEN:
            if cuenta[macro]:
                cabe = False
                advertencia = f"Se pasa en {macro}: aporta {macro_aportado}g, faltaban {macro_restante}g"
                break

    return _build_result(alimento, cantidad_final, es_vegano, cabe, advertencia)


def _build_result(alimento: dict, cantidad_g: float, es_vegano: bool,
                  cabe: bool, advertencia: Optional[str]) -> Dict:
    """Construye el resultado del cálculo."""
    from calma_engine import calcular_macros_efectivos_alimento as calcular_macros_efectivos, calcular_macros_brutos, que_macros_cuentan

    efectivos = calcular_macros_efectivos(alimento, cantidad_g, es_vegano)
    brutos = calcular_macros_brutos(alimento, cantidad_g)
    cuenta = que_macros_cuentan(alimento, cantidad_g, es_vegano)

    return {
        "cantidad_g": cantidad_g,
        "macros_efectivos": efectivos,
        "macros_brutos": brutos,
        "que_cuenta": cuenta,
        "cabe": cabe,
        "advertencia": advertencia
    }


def validar_comida(
    alimentos: List[Dict],
    macros_objetivo: Dict[str, float],
    es_vegano: bool = False
) -> Dict:
    """
    Valida si una comida está cuadrada.

    Args:
        alimentos: lista de {"alimento": dict, "cantidad_g": float}
        macros_objetivo: {"P": 45, "H": 50, "G": 15}
        es_vegano: modo vegano

    Returns:
        {
            "estado": "cuadrada" | "faltan" | "sobran" | "vacia",
            "macros_servidos": {"P": 44, "H": 49, "G": 14, "kcal": 502},
            "macros_objetivo": {"P": 45, "H": 50, "G": 15},
            "macros_restantes": {"P": 1, "H": 1, "G": 1},
            "detalle_estado": {"P": "ok", "H": "ok", "G": "ok"},
            "detalle_alimentos": [...]
        }
    """
    MARGEN = 4.0

    if not alimentos:
        return {
            "estado": "vacia",
            "macros_servidos": {"P": 0, "H": 0, "G": 0, "kcal": 0},
            "macros_objetivo": macros_objetivo,
            "macros_restantes": {
                "P": macros_objetivo.get("P", 0),
                "H": macros_objetivo.get("H", 0),
                "G": macros_objetivo.get("G", 0)
            },
            "detalle_estado": {"P": "falta", "H": "falta", "G": "falta"},
            "detalle_alimentos": []
        }

    total_P = 0.0
    total_H = 0.0
    total_G = 0.0
    detalle = []

    for item in alimentos:
        al = item["alimento"]
        cant = item["cantidad_g"]
        ef = calcular_macros_efectivos(al, cant, es_vegano)
        total_P += ef["P"]
        total_H += ef["H"]
        total_G += ef["G"]
        detalle.append({
            "nombre": al.get("nombre", ""),
            "cantidad_g": cant,
            "efectivos": ef
        })

    obj_P = macros_objetivo.get("P", 0)
    obj_H = macros_objetivo.get("H", 0)
    obj_G = macros_objetivo.get("G", 0)

    rest_P = round(obj_P - total_P, 1)
    rest_H = round(obj_H - total_H, 1)
    rest_G = round(obj_G - total_G, 1)

    # Estado por macro
    def estado_macro(restante):
        if abs(restante) <= MARGEN:
            return "ok"
        elif restante > 0:
            return "falta"
        else:
            return "sobra"

    est_P = estado_macro(rest_P)
    est_H = estado_macro(rest_H)
    est_G = estado_macro(rest_G)

    # Estado global
    if est_P == "ok" and est_H == "ok" and est_G == "ok":
        estado = "cuadrada"
    elif "sobra" in [est_P, est_H, est_G]:
        estado = "sobran"
    else:
        estado = "faltan"

    return {
        "estado": estado,
        "macros_servidos": {
            "P": round(total_P, 1),
            "H": round(total_H, 1),
            "G": round(total_G, 1),
            "kcal": round(total_P * 4 + total_H * 4 + total_G * 9, 1)
        },
        "macros_objetivo": macros_objetivo,
        "macros_restantes": {"P": rest_P, "H": rest_H, "G": rest_G},
        "detalle_estado": {"P": est_P, "H": est_H, "G": est_G},
        "detalle_alimentos": detalle
    }


def sugerir_alimentos(
    alimentos_db: List[dict],
    macros_restantes: Dict[str, float],
    tipo_comida: str = "principal",
    es_vegano: bool = False,
    max_resultados: int = 10
) -> List[Dict]:
    """
    Sugiere alimentos que caben en los macros restantes.

    Args:
        alimentos_db: lista de todos los alimentos de la BD
        macros_restantes: {"P": 12, "H": 6, "G": 3}
        tipo_comida: "principal", "intra", "post", "cuadrar_grasa"
        es_vegano: modo vegano
        max_resultados: máximo de sugerencias

    Returns:
        Lista de {"alimento": dict, "cantidad_sugerida": float, "macros": dict, "score": float}
    """
    from calma_engine import parse_categories, get_numeric_categories, cat_matches, cat_in_any

    MARGEN = 4.0
    sugerencias = []

    # Filtrar por tipo de comida
    CATS_INTRA = ["41", "18.1.1", "18.1.3", "18.1.2"]
    CATS_POST_PRIORIDAD = [
        "4.1.1", "4.1.2", "4.1", "4.2", "5.4", "5.2.3", "5.2.2", "5.1",
        "4.3", "27", "21.3", "7.1.1", "7.1.2.1", "18.3", "11.5",
        "11.2.1", "11.2.2", "11.1", "11.4", "11.6", "11.7", "21.2",
        "7.3.1", "8", "24", "19.1", "18.1", "18.2", "37", "16.5", "16.1"
    ]
    CATS_CUADRAR_GRASA = ["17.1.1", "17.1", "42"]

    # Categorías veganas a ocultar
    CATS_OCULTAR_VEGANO = ["1", "2", "3", "4.1", "4.2", "5"]

    for al in alimentos_db:
        cats_raw = parse_categories(al.get("categorias", ""))
        cats_num = get_numeric_categories(cats_raw)
        cat_principal = cats_num[0] if cats_num else ""

        # Filtrar por modo vegano
        if es_vegano:
            es_vegano_cat = any(cat_in_any(c, ["28", "52"]) for c in cats_num)
            es_oculto = any(cat_in_any(c, CATS_OCULTAR_VEGANO) for c in cats_num)
            if es_oculto and not es_vegano_cat:
                continue

        # Filtrar por tipo de comida
        if tipo_comida == "intra":
            if not any(cat_in_any(c, CATS_INTRA) for c in cats_num):
                continue
        elif tipo_comida == "cuadrar_grasa":
            if not any(cat_in_any(c, CATS_CUADRAR_GRASA) for c in cats_num):
                continue

        # Calcular si cabe
        resultado = calcular_cantidad_automatica(al, macros_restantes, es_vegano)

        if resultado["cantidad_g"] <= 0:
            continue

        # Calcular score
        ef = resultado["macros_efectivos"]
        score = ef["P"] * 1.2 + ef["H"] * 1.0 + ef["G"] * 0.8

        # Bonus para marcas recomendadas
        if "PRO" in cats_raw:
            score *= 1.1

        # Bonus para prioridades de post
        if tipo_comida == "post":
            for idx, cat_prio in enumerate(CATS_POST_PRIORIDAD):
                if cat_in_any(cat_principal, [cat_prio]):
                    score += (len(CATS_POST_PRIORIDAD) - idx) * 10
                    break

        sugerencias.append({
            "alimento_id": al.get("id"),
            "nombre": al.get("nombre", ""),
            "categorias": al.get("categorias", ""),
            "cantidad_sugerida": resultado["cantidad_g"],
            "macros_efectivos": ef,
            "cabe": resultado["cabe"],
            "score": round(score, 1)
        })

    # Ordenar por score descendente
    sugerencias.sort(key=lambda x: x["score"], reverse=True)

    return sugerencias[:max_resultados]


# =====================================================
# TESTS
# =====================================================

def run_tests():
    print("=" * 60)
    print("TESTS CALCULADORA")
    print("=" * 60)

    passed = 0
    failed = 0

    def test(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            print(f"  ✅ {name}")
            passed += 1
        else:
            print(f"  ❌ {name} — {detail}")
            failed += 1

    # --- TEST 1: Ajuste automático pollo ---
    print("\n--- Ajuste automático: Pechuga de pollo ---")
    pollo = {"proteinas": 21, "hidratos": 0, "grasas": 1.5, "racion": 100,
             "categorias": "2.2 | FRE", "unidades": False, "minimo": None}
    r = calcular_cantidad_automatica(pollo, {"P": 45, "H": 50, "G": 15})
    test("Cantidad > 0", r["cantidad_g"] > 0, f"cantidad={r['cantidad_g']}")
    test("Cantidad redondeada a 25g", r["cantidad_g"] % 25 == 0, f"cantidad={r['cantidad_g']}")
    # 45g P / 21g per 100g = 214g → redondear a 225 o 200
    test("Cantidad razonable (175-225g)", 175 <= r["cantidad_g"] <= 225, f"cantidad={r['cantidad_g']}")
    test("Cabe en la comida", r["cabe"] is True)

    # --- TEST 2: Ajuste automático arroz ---
    print("\n--- Ajuste automático: Arroz basmati ---")
    arroz = {"proteinas": 7, "hidratos": 78, "grasas": 0.6, "racion": 100,
             "categorias": "21.1 | GEN", "unidades": False, "minimo": None}
    r = calcular_cantidad_automatica(arroz, {"P": 0, "H": 50, "G": 15})
    test("Cantidad > 0", r["cantidad_g"] > 0, f"cantidad={r['cantidad_g']}")
    test("Cantidad redondeada a 25g", r["cantidad_g"] % 25 == 0, f"cantidad={r['cantidad_g']}")
    # 50g H / 78g per 100g = 64g → redondear a 75
    test("Cantidad razonable (50-100g)", 50 <= r["cantidad_g"] <= 100, f"cantidad={r['cantidad_g']}")

    # --- TEST 3: Ajuste automático aceite ---
    print("\n--- Ajuste automático: AOVE ---")
    # AOVE: 10g de grasa por ración de 10g → 100g grasa por 100g
    aove = {"proteinas": 0, "hidratos": 0, "grasas": 10, "racion": 10,
            "categorias": "17.1.1 | GEN", "unidades": False, "minimo": None}
    r = calcular_cantidad_automatica(aove, {"P": 0, "H": 0, "G": 15})
    test("Cantidad > 0", r["cantidad_g"] > 0, f"cantidad={r['cantidad_g']}")
    test("Cantidad redondeada a 5ml", r["cantidad_g"] % 5 == 0, f"cantidad={r['cantidad_g']}")
    # 15g G / 100g per 100g * 100 = 15ml → redondeado a 15ml
    test("Cantidad razonable (10-20ml)", 10 <= r["cantidad_g"] <= 20, f"cantidad={r['cantidad_g']}")

    # --- TEST 4: Huevos (unidades) ---
    print("\n--- Ajuste automático: Huevos ---")
    huevo = {"proteinas": 7.5, "hidratos": 0, "grasas": 5.5, "racion": 60,
             "categorias": "1.2.1 | FRE", "unidades": True, "minimo": None}
    r = calcular_cantidad_automatica(huevo, {"P": 20, "H": 50, "G": 15})
    test("Cantidad es múltiplo de 60", r["cantidad_g"] % 60 == 0, f"cantidad={r['cantidad_g']}")
    # 20g P / 7.5g per 60g → 2.67 huevos → 3 huevos = 180g
    test("Cantidad razonable (120-180g = 2-3 huevos)", 120 <= r["cantidad_g"] <= 180, f"cantidad={r['cantidad_g']}")

    # --- TEST 5: Validar comida cuadrada ---
    print("\n--- Validar comida cuadrada ---")
    alimentos_comida = [
        {"alimento": pollo, "cantidad_g": 200},
        {"alimento": arroz, "cantidad_g": 75},
        {"alimento": {"proteinas": 0, "hidratos": 0, "grasas": 10, "racion": 10,
                       "categorias": "17.1.1 | GEN", "unidades": False, "minimo": None}, "cantidad_g": 15},
    ]
    resultado = validar_comida(alimentos_comida, {"P": 45, "H": 60, "G": 15})
    test("Estado es string", resultado["estado"] in ["cuadrada", "faltan", "sobran"])
    test("Macros servidos tiene P", "P" in resultado["macros_servidos"])
    test("Macros restantes calculados", "P" in resultado["macros_restantes"])

    # --- TEST 6: Comida vacía ---
    print("\n--- Validar comida vacía ---")
    resultado = validar_comida([], {"P": 45, "H": 50, "G": 15})
    test("Estado = vacia", resultado["estado"] == "vacia")
    test("P restante = 45", resultado["macros_restantes"]["P"] == 45)

    # --- TEST 7: Redondeo ---
    print("\n--- Redondeo de cantidades ---")
    test("Pollo 137g → 125 o 150", redondear_cantidad(137, pollo) in [125, 150], f"resultado={redondear_cantidad(137, pollo)}")
    test("Arroz 64g → 50 o 75", redondear_cantidad(64, arroz) in [50, 75], f"resultado={redondear_cantidad(64, arroz)}")

    avena = {"proteinas": 12, "hidratos": 60, "grasas": 7, "racion": 100,
             "categorias": "7.1 | GEN", "unidades": False, "minimo": None}
    test("Avena 43g → 40 o 50", redondear_cantidad(43, avena) in [40, 50], f"resultado={redondear_cantidad(43, avena)}")

    # --- TEST 8: Alimento que no cabe ---
    print("\n--- Alimento que no cabe (macros ya cubiertos) ---")
    r = calcular_cantidad_automatica(pollo, {"P": 0, "H": 0, "G": 0})
    test("Advertencia presente", r["advertencia"] is not None)

    # --- RESUMEN ---
    print("\n" + "=" * 60)
    print(f"RESULTADO: {passed} pasados, {failed} fallidos de {passed + failed}")
    print("=" * 60)

    if failed > 0:
        print("\n⚠️  HAY TESTS FALLIDOS — REVISAR")
    else:
        print("\n✅ TODOS LOS TESTS PASAN — Calculadora OK")

    return failed == 0


if __name__ == "__main__":
    run_tests()
