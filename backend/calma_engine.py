"""
CALMA v2 Engine — Motor de conteo de macros del Método Jesús Gallego
====================================================================
Este motor determina qué macronutrientes CUENTAN para cada alimento
según su categoría. No todos los macros de un alimento cuentan para
el balance de la dieta — depende de reglas específicas por categoría.

Ejemplo: La pechuga de pollo tiene 21P, 0H, 1.5G por 100g.
- P siempre cuenta (es proteína, cat 2.2)
- H no cuenta (es 0, y además <2% para cat 2)
- G no cuenta (1.5% < 3% para cat 2)
Resultado: solo cuenta P=21. Los otros macros se IGNORAN en el balance.

Ejemplo 2: Tomate frito tiene 0.8P, 6.5H, 4.2G (cat 13.8 + 16.2)
- Cat 13: P nunca cuenta. H cuenta si >4% (6.5>4 → SÍ). G cuenta si >4% (4.2>4 → SÍ)
- Cat 16: Cualquier macro ≥6% cuenta. P=0.8<6 → NO. H=6.5≥6 → SÍ. G=4.2<6 → NO
- Doble categoría: regla MÁS PERMISIVA → P=NO, H=SÍ (ambas dicen sí), G=SÍ (cat 13 dice sí)
Resultado: cuentan H=6.5 y G=4.2
"""

from typing import Dict, List, Optional, Tuple


def parse_categories(categorias_str: str) -> List[str]:
    """
    Parsea el string de categorías de un alimento.
    Input: "2.2.1 | FRE | TOP"
    Output: ["2.2.1", "FRE", "TOP"]
    
    La PRIMERA categoría es la principal (numérica).
    El resto pueden ser numéricas (doble categoría) o etiquetas (FRE, PRO, TOP, etc.)
    """
    if not categorias_str:
        return []
    parts = [c.strip() for c in categorias_str.split("|")]
    return [p for p in parts if p]


def get_numeric_categories(categorias: List[str]) -> List[str]:
    """
    Filtra solo las categorías numéricas (las que tienen reglas de conteo).
    Input: ["2.2.1", "FRE", "TOP"]
    Output: ["2.2.1"]
    
    Input: ["13.8", "16.2", "YA"]
    Output: ["13.8", "16.2"]
    """
    numeric = []
    for cat in categorias:
        # Es numérica si empieza con dígito
        if cat and cat[0].isdigit():
            numeric.append(cat)
    return numeric


def cat_matches(cat: str, pattern: str) -> bool:
    """
    Verifica si una categoría coincide con un patrón.
    cat_matches("2.2.1", "2") → True (2.2.1 está dentro de 2)
    cat_matches("2.2.1", "2.2") → True
    cat_matches("2.2.1", "2.2.1") → True
    cat_matches("2.2.1", "2.3") → False
    cat_matches("2.2.1", "3") → False
    cat_matches("17.2.1", "17.2") → True
    cat_matches("17.2.1", "17") → True
    cat_matches("17.2.1", "17.1") → False
    """
    if cat == pattern:
        return True
    # cat empieza con pattern seguido de "."
    return cat.startswith(pattern + ".")


def cat_in_any(cat: str, patterns: List[str]) -> bool:
    """Verifica si una categoría coincide con ALGUNO de los patrones."""
    return any(cat_matches(cat, p) for p in patterns)


def get_macro_predominante(proteinas: float, hidratos: float, grasas: float) -> float:
    """Retorna el valor del macro predominante (el más alto)."""
    return max(proteinas, hidratos, grasas)


def _regla_categoria(
    cat: str,
    proteinas_100g: float,
    hidratos_100g: float,
    grasas_100g: float,
    cantidad_g: float = 100.0,
    es_vegano: bool = False
) -> Dict[str, bool]:
    """
    Aplica las reglas de conteo para UNA categoría específica.
    
    Retorna: {"P": True/False, "H": True/False, "G": True/False}
    donde True = ese macro CUENTA para el balance.
    
    cantidad_g se usa para las reglas de calibración (cat 7, 8, 17.2)
    """
    P = proteinas_100g
    H = hidratos_100g
    G = grasas_100g
    predominante = get_macro_predominante(P, H, G)
    
    cuenta_P = False
    cuenta_H = False
    cuenta_G = False
    
    # =====================================================
    # CATEGORÍAS 1, 2, 3 (excepto 3.9) — Huevos, Carnes, Pescados
    # P siempre cuenta. G no cuenta si <3%. H no cuenta si <2%.
    # =====================================================
    if cat_in_any(cat, ["1", "2", "3"]) and not cat_matches(cat, "3.9"):
        cuenta_P = True  # P siempre cuenta
        cuenta_G = G >= 3.0
        cuenta_H = H >= 2.0
        return {"P": cuenta_P, "H": cuenta_H, "G": cuenta_G}
    
    # =====================================================
    # CATEGORÍA 3.9 — Mariscos
    # P siempre cuenta. G no cuenta si <3%. H no cuenta si ≤3%.
    # =====================================================
    if cat_matches(cat, "3.9"):
        cuenta_P = True
        cuenta_G = G >= 3.0
        cuenta_H = H > 3.0  # ≤3% NO cuenta → solo cuenta si >3%
        return {"P": cuenta_P, "H": cuenta_H, "G": cuenta_G}
    
    # =====================================================
    # CATEGORÍA 4 — Proteínas en polvo
    # P siempre cuenta. H no cuenta si ≤6%. G regla general.
    # =====================================================
    if cat_matches(cat, "4"):
        cuenta_P = True
        cuenta_H = H > 6.0
        # G: regla general (>25% del predominante)
        cuenta_G = G > 0.25 * predominante if predominante > 0 else False
        return {"P": cuenta_P, "H": cuenta_H, "G": cuenta_G}
    
    # =====================================================
    # CATEGORÍA 5 — Lácteos
    # P y H cuentan (alimento mixto). G no cuenta si <1%.
    # =====================================================
    if cat_matches(cat, "5"):
        cuenta_P = True
        cuenta_H = True
        cuenta_G = G >= 1.0
        return {"P": cuenta_P, "H": cuenta_H, "G": cuenta_G}
    
    # =====================================================
    # CATEGORÍA 6 — Soja
    # Regla general del 25%
    # =====================================================
    if cat_matches(cat, "6"):
        if predominante > 0:
            cuenta_P = P > 0.25 * predominante
            cuenta_H = H > 0.25 * predominante
            cuenta_G = G > 0.25 * predominante
        return {"P": cuenta_P, "H": cuenta_H, "G": cuenta_G}
    
    # =====================================================
    # CATEGORÍA 7 — Cereales excepto arroz
    # H siempre cuenta.
    # P: solo si P > 1/3 de H. CALIBRACIÓN: si <100g servidos, P no cuenta si P < 1/3 predominante
    # G: solo si G>8% O G > 1/4 de H
    # =====================================================
    if cat_matches(cat, "7"):
        cuenta_H = True
        # Proteínas
        if H > 0 and P > H / 3.0:
            cuenta_P = True
        # Calibración: por debajo de 100g, P no cuenta si < 1/3 del predominante
        if cantidad_g < 100 and predominante > 0 and P < predominante / 3.0:
            cuenta_P = False
        # Grasas
        cuenta_G = G > 8.0 or (H > 0 and G > H / 4.0)
        return {"P": cuenta_P, "H": cuenta_H, "G": cuenta_G}
    
    # =====================================================
    # CATEGORÍA 8 — Panes y tortillas de trigo
    # H siempre cuenta.
    # P: solo si P > 1/3 de H. CALIBRACIÓN: si <100g servidos, P no cuenta si P < 1/3 predominante
    # G: solo si G>9% O G > 1/4 de H
    # =====================================================
    if cat_matches(cat, "8"):
        cuenta_H = True
        # Proteínas
        if H > 0 and P > H / 3.0:
            cuenta_P = True
        # Calibración
        if cantidad_g < 100 and predominante > 0 and P < predominante / 3.0:
            cuenta_P = False
        # Grasas (umbral 9% en vez de 8% para panes)
        cuenta_G = G > 9.0 or (H > 0 and G > H / 4.0)
        return {"P": cuenta_P, "H": cuenta_H, "G": cuenta_G}
    
    # =====================================================
    # CATEGORÍA 9 — Tubérculos
    # SOLO cuentan H. P y G nunca cuentan.
    # =====================================================
    if cat_matches(cat, "9"):
        return {"P": False, "H": True, "G": False}
    
    # =====================================================
    # CATEGORÍA 10 — Legumbres
    # P y H siempre cuentan (alimento mixto). G solo si ≥8%.
    # =====================================================
    if cat_matches(cat, "10"):
        cuenta_P = True
        cuenta_H = True
        cuenta_G = G >= 8.0
        return {"P": cuenta_P, "H": cuenta_H, "G": cuenta_G}
    
    # =====================================================
    # CATEGORÍA 11 — Fruta, zumo, potitos, mermeladas
    # SOLO cuentan H.
    # CORRECCIÓN: Los zumos (11.5) SÍ cuentan H (ya está cubierto porque H siempre cuenta en cat 11)
    # =====================================================
    if cat_matches(cat, "11"):
        return {"P": False, "H": True, "G": False}
    
    # =====================================================
    # CATEGORÍA 13 (excepto 13.9) — Verduras y hortalizas
    # P: NUNCA cuenta.
    # H: SOLO cuenta si >4% (excepción a regla general del 25%)
    # G: SOLO cuenta si >4% (excepción a regla general del 25%)
    # =====================================================
    if cat_matches(cat, "13") and not cat_matches(cat, "13.9"):
        cuenta_H = H > 4.0
        cuenta_G = G > 4.0
        return {"P": False, "H": cuenta_H, "G": cuenta_G}
    
    # =====================================================
    # CATEGORÍA 13.9 — Ensaladas preparadas
    # P: solo si P > 1/4 de H
    # G: solo si G > 3%
    # H: regla general
    # =====================================================
    if cat_matches(cat, "13.9"):
        cuenta_P = (H > 0 and P > H / 4.0)
        cuenta_G = G > 3.0
        cuenta_H = True  # ensaladas preparadas: H cuenta
        return {"P": cuenta_P, "H": cuenta_H, "G": cuenta_G}
    
    # =====================================================
    # CATEGORÍA 14 — Hidratos en polvo
    # Solo cuentan H
    # =====================================================
    if cat_matches(cat, "14"):
        return {"P": False, "H": True, "G": False}
    
    # =====================================================
    # CATEGORÍA 16 — Salsas, siropes y konjac
    # Cualquier macro ≥6% cuenta. Cualquier macro <6% NO cuenta.
    # (sin importar la relación de predominancia)
    # =====================================================
    if cat_matches(cat, "16"):
        return {
            "P": P >= 6.0,
            "H": H >= 6.0,
            "G": G >= 6.0
        }
    
    # =====================================================
    # CATEGORÍAS 17.1, 17.4, 17.6, 17.10 — Aceites, mantequilla, aguacate, mayonesa
    # SOLO cuentan G
    # =====================================================
    if cat_in_any(cat, ["17.1", "17.4", "17.6", "17.10"]):
        return {"P": False, "H": False, "G": True}
    
    # =====================================================
    # CATEGORÍAS 17.2.1, 17.2.3, 17.2.4 — Frutos secos naturales, semillas, cremas naturales
    # G siempre cuenta.
    # P: solo si P > 1/2 del predominante
    # H: solo si H > 1/2 del predominante
    # CALIBRACIÓN: >50g servidos → P y H cuentan si > 1/4 del predominante (más permisivo)
    # =====================================================
    if cat_in_any(cat, ["17.2.1", "17.2.3", "17.2.4"]):
        cuenta_G = True
        if predominante > 0:
            if cantidad_g <= 50:
                cuenta_P = P > predominante / 2.0
                cuenta_H = H > predominante / 2.0
            else:
                # Calibración: se relaja, cuentan si > 1/4 del predominante
                cuenta_P = P > predominante / 4.0
                cuenta_H = H > predominante / 4.0
        return {"P": cuenta_P, "H": cuenta_H, "G": cuenta_G}
    
    # =====================================================
    # CATEGORÍAS 17.2.2, 17.2.5, 17.5 (excepto 17.5.3)
    # Frutos secos con azúcar, cremas con azúcar, cremas de cacao
    # H: siempre cuenta
    # G: siempre cuenta
    # P: solo si P > 1/2 del predominante
    # =====================================================
    if cat_in_any(cat, ["17.2.2", "17.2.5"]) or (cat_matches(cat, "17.5") and not cat_matches(cat, "17.5.3")):
        cuenta_H = True
        cuenta_G = True
        cuenta_P = P > predominante / 2.0 if predominante > 0 else False
        return {"P": cuenta_P, "H": cuenta_H, "G": cuenta_G}
    
    # =====================================================
    # CATEGORÍA 17.5.3 — Cremas proteicas
    # P: siempre cuenta
    # G: siempre cuenta
    # H: solo si H > 1/2 del predominante
    # =====================================================
    if cat_matches(cat, "17.5.3"):
        cuenta_P = True
        cuenta_G = True
        cuenta_H = H > predominante / 2.0 if predominante > 0 else False
        return {"P": cuenta_P, "H": cuenta_H, "G": cuenta_G}
    
    # =====================================================
    # CATEGORÍAS 17.2.6, 17.9 — Frutos secos en polvo, Croquetas
    # TODOS los macros cuentan sin ninguna regla
    # =====================================================
    if cat_in_any(cat, ["17.2.6", "17.9"]):
        return {"P": True, "H": True, "G": True}
    
    # =====================================================
    # CATEGORÍA 17.7 — Cremas vegetales
    # Si no ha caído en ninguna sub de 17, regla general
    # =====================================================
    if cat_matches(cat, "17.7"):
        if predominante > 0:
            cuenta_P = P > 0.25 * predominante
            cuenta_H = H > 0.25 * predominante
            cuenta_G = G > 0.25 * predominante
        return {"P": cuenta_P, "H": cuenta_H, "G": cuenta_G}
    
    # =====================================================
    # CATEGORÍA 17 (resto que no haya matcheado arriba)
    # Regla general
    # =====================================================
    if cat_matches(cat, "17"):
        if predominante > 0:
            cuenta_P = P > 0.25 * predominante
            cuenta_H = H > 0.25 * predominante
            cuenta_G = G > 0.25 * predominante
        return {"P": cuenta_P, "H": cuenta_H, "G": cuenta_G}
    
    # =====================================================
    # CATEGORÍA 21 — Arroces y derivados
    # H siempre cuenta. P NO cuenta. G solo si ≥6%.
    # =====================================================
    if cat_matches(cat, "21"):
        return {"P": False, "H": True, "G": G >= 6.0}
    
    # =====================================================
    # CATEGORÍA 22 (excepto 22.1.2.2, 22.6, 22.7) — Pasta, quinoa
    # H siempre cuenta.
    # P: solo si P > 1/3 de H
    # G: solo si G>9% O G > 1/3 de H
    # =====================================================
    if cat_matches(cat, "22"):
        # Las excepciones 22.1.2.2, 22.6, 22.7 usan regla general
        if cat_in_any(cat, ["22.1.2.2", "22.6", "22.7"]):
            if predominante > 0:
                cuenta_P = P > 0.25 * predominante
                cuenta_H = H > 0.25 * predominante
                cuenta_G = G > 0.25 * predominante
            return {"P": cuenta_P, "H": cuenta_H, "G": cuenta_G}
        
        cuenta_H = True
        cuenta_P = P > H / 3.0 if H > 0 else False
        cuenta_G = G > 9.0 or (H > 0 and G > H / 3.0)
        return {"P": cuenta_P, "H": cuenta_H, "G": cuenta_G}
    
    # =====================================================
    # CATEGORÍA 24 — Bebidas vegetales
    # P NO cuenta. H y G regla general.
    # =====================================================
    if cat_matches(cat, "24"):
        cuenta_P = False
        if predominante > 0:
            cuenta_H = H > 0.25 * predominante
            cuenta_G = G > 0.25 * predominante
        return {"P": cuenta_P, "H": cuenta_H, "G": cuenta_G}
    
    # =====================================================
    # CATEGORÍA 28 — Proteína vegetal
    # Regla general del 25%.
    # EN MODO VEGANO: H siempre cuentan si ≥4g/100g
    # =====================================================
    if cat_matches(cat, "28"):
        if predominante > 0:
            cuenta_P = P > 0.25 * predominante
            cuenta_H = H > 0.25 * predominante
            cuenta_G = G > 0.25 * predominante
        if es_vegano and H >= 4.0:
            cuenta_H = True
        return {"P": cuenta_P, "H": cuenta_H, "G": cuenta_G}
    
    # =====================================================
    # CATEGORÍA 37 — Cacao, azúcares, chucherías, miel
    # H: siempre cuenta
    # P: solo si P > 1/2 del predominante
    # G: solo si G > 10%
    # =====================================================
    if cat_matches(cat, "37"):
        cuenta_H = True
        cuenta_P = P > predominante / 2.0 if predominante > 0 else False
        cuenta_G = G > 10.0
        return {"P": cuenta_P, "H": cuenta_H, "G": cuenta_G}
    
    # =====================================================
    # CATEGORÍA 38.1 — Patatas fritas y derivados
    # H: siempre cuenta
    # G: siempre cuenta
    # P: solo si P > 1/2 del predominante
    # =====================================================
    if cat_matches(cat, "38.1"):
        cuenta_H = True
        cuenta_G = True
        cuenta_P = P > predominante / 2.0 if predominante > 0 else False
        return {"P": cuenta_P, "H": cuenta_H, "G": cuenta_G}
    
    # =====================================================
    # CATEGORÍA 41 — Aminoácidos para entrenar
    # Solo cuentan P. H y G no cuentan.
    # =====================================================
    if cat_matches(cat, "41"):
        return {"P": True, "H": False, "G": False}
    
    # =====================================================
    # CATEGORÍA 48 — Sopas y caldos
    # Todos los macros cuentan si su valor ≥ 2%
    # =====================================================
    if cat_matches(cat, "48"):
        return {
            "P": P >= 2.0,
            "H": H >= 2.0,
            "G": G >= 2.0
        }
    
    # =====================================================
    # CATEGORÍA 52 — Mundo vegano
    # EN MODO VEGANO: todos los macros ≥2% cuentan (como cat 48)
    # EN MODO NORMAL: regla general del 25%
    # =====================================================
    if cat_matches(cat, "52"):
        if es_vegano:
            return {
                "P": P >= 2.0,
                "H": H >= 2.0,
                "G": G >= 2.0
            }
        else:
            if predominante > 0:
                cuenta_P = P > 0.25 * predominante
                cuenta_H = H > 0.25 * predominante
                cuenta_G = G > 0.25 * predominante
            return {"P": cuenta_P, "H": cuenta_H, "G": cuenta_G}
    
    # =====================================================
    # REGLA GENERAL — Para todas las categorías no listadas arriba
    # (cat 6, 18, 19, 25, 27, 29, 30, 31, 32, 34, 35, 36, 38.2, 38.3,
    #  39, 40, 42, 43, 44, 45, 46, 47, 49, 50, 51, 53, etc.)
    # Macro cuenta si > 25% del macro predominante
    # =====================================================
    if predominante > 0:
        cuenta_P = P > 0.25 * predominante
        cuenta_H = H > 0.25 * predominante
        cuenta_G = G > 0.25 * predominante
    
    return {"P": cuenta_P, "H": cuenta_H, "G": cuenta_G}


def calcular_macros_efectivos(
    alimento: dict,
    cantidad_g: float = None,
    es_vegano: bool = False
) -> Dict[str, float]:
    """
    FUNCIÓN PRINCIPAL — Calcula los macros que CUENTAN de un alimento.
    
    Args:
        alimento: dict con campos: proteinas, hidratos, grasas, racion, categorias, unidades
        cantidad_g: gramos servidos (para calibración). Si None, usa racion.
        es_vegano: si el usuario está en modo vegano
    
    Returns:
        {"P": gramos_proteina, "H": gramos_hidratos, "G": gramos_grasa, "kcal": calorias}
        Solo incluye los macros que CUENTAN según las reglas. Los que no cuentan = 0.
    
    Ejemplo:
        alimento = {"proteinas": 21, "hidratos": 0, "grasas": 1.5, "racion": 100, "categorias": "2.2 | FRE", "unidades": False}
        calcular_macros_efectivos(alimento, 150)
        → {"P": 31.5, "H": 0, "G": 0, "kcal": 126}
        (G no cuenta porque 1.5 < 3% para cat 2)
    """
    racion = alimento.get("racion", 100) or 100
    es_unidades = alimento.get("unidades", False)
    
    # Macros por 100g (o por unidad si es de unidades)
    P_base = float(alimento.get("proteinas", 0) or 0)
    H_base = float(alimento.get("hidratos", 0) or 0)
    G_base = float(alimento.get("grasas", 0) or 0)
    
    # Macros por 100g para las reglas de categoría
    if es_unidades:
        # Los macros en BD son POR UNIDAD (por ración)
        # Convertir a por 100g para aplicar reglas
        if racion > 0:
            P_100g = P_base * 100.0 / racion
            H_100g = H_base * 100.0 / racion
            G_100g = G_base * 100.0 / racion
        else:
            P_100g = P_base
            H_100g = H_base
            G_100g = G_base
    else:
        # Los macros en BD son POR RACIÓN
        # Convertir a por 100g
        if racion > 0:
            P_100g = P_base * 100.0 / racion
            H_100g = H_base * 100.0 / racion
            G_100g = G_base * 100.0 / racion
        else:
            P_100g = P_base
            H_100g = H_base
            G_100g = G_base
    
    # Cantidad servida
    if cantidad_g is None:
        cantidad_g = racion
    
    # Calcular macros reales servidos
    if es_unidades:
        # cantidad_g es en gramos, racion es gramos por unidad
        factor = cantidad_g / racion if racion > 0 else 1
        P_servido = P_base * factor
        H_servido = H_base * factor
        G_servido = G_base * factor
    else:
        # Macros base son por ración, calcular por cantidad servida
        factor = cantidad_g / racion if racion > 0 else 1
        P_servido = P_base * factor
        H_servido = H_base * factor
        G_servido = G_base * factor
    
    # Parsear categorías
    categorias_raw = parse_categories(alimento.get("categorias", ""))
    categorias_num = get_numeric_categories(categorias_raw)
    
    if not categorias_num:
        # Sin categoría numérica → regla general: todo cuenta si >25% predominante
        predominante = get_macro_predominante(P_100g, H_100g, G_100g)
        if predominante > 0:
            cuenta_P = P_100g > 0.25 * predominante
            cuenta_H = H_100g > 0.25 * predominante
            cuenta_G = G_100g > 0.25 * predominante
        else:
            cuenta_P = cuenta_H = cuenta_G = False
    elif len(categorias_num) == 1:
        # Una sola categoría → aplicar sus reglas
        resultado = _regla_categoria(categorias_num[0], P_100g, H_100g, G_100g, cantidad_g, es_vegano)
        cuenta_P = resultado["P"]
        cuenta_H = resultado["H"]
        cuenta_G = resultado["G"]
    else:
        # DOBLE CATEGORÍA → regla MÁS PERMISIVA
        # Si ALGUNA categoría dice que el macro cuenta → CUENTA
        cuenta_P = False
        cuenta_H = False
        cuenta_G = False
        for cat in categorias_num:
            resultado = _regla_categoria(cat, P_100g, H_100g, G_100g, cantidad_g, es_vegano)
            if resultado["P"]:
                cuenta_P = True
            if resultado["H"]:
                cuenta_H = True
            if resultado["G"]:
                cuenta_G = True
    
    # Aplicar: los macros que NO cuentan se ponen a 0
    P_final = round(P_servido, 1) if cuenta_P else 0.0
    H_final = round(H_servido, 1) if cuenta_H else 0.0
    G_final = round(G_servido, 1) if cuenta_G else 0.0
    
    # Calorías solo de los macros que CUENTAN
    kcal = round(P_final * 4 + H_final * 4 + G_final * 9, 1)
    
    return {
        "P": P_final,
        "H": H_final,
        "G": G_final,
        "kcal": kcal
    }


def calcular_macros_brutos(
    alimento: dict,
    cantidad_g: float = None
) -> Dict[str, float]:
    """
    Calcula los macros REALES (sin aplicar reglas CALMA).
    Útil para mostrar información nutricional completa.
    """
    racion = alimento.get("racion", 100) or 100
    P_base = float(alimento.get("proteinas", 0) or 0)
    H_base = float(alimento.get("hidratos", 0) or 0)
    G_base = float(alimento.get("grasas", 0) or 0)
    
    if cantidad_g is None:
        cantidad_g = racion
    
    factor = cantidad_g / racion if racion > 0 else 1
    
    P = round(P_base * factor, 1)
    H = round(H_base * factor, 1)
    G = round(G_base * factor, 1)
    kcal = round(P * 4 + H * 4 + G * 9, 1)
    
    return {"P": P, "H": H, "G": G, "kcal": kcal}


def que_macros_cuentan(
    alimento: dict,
    cantidad_g: float = None,
    es_vegano: bool = False
) -> Dict[str, bool]:
    """
    Función auxiliar: solo dice SÍ/NO para cada macro, sin calcular cantidades.
    Útil para el frontend (mostrar qué macros están activos).
    """
    racion = alimento.get("racion", 100) or 100
    es_unidades = alimento.get("unidades", False)
    
    P_base = float(alimento.get("proteinas", 0) or 0)
    H_base = float(alimento.get("hidratos", 0) or 0)
    G_base = float(alimento.get("grasas", 0) or 0)
    
    if es_unidades and racion > 0:
        P_100g = P_base * 100.0 / racion
        H_100g = H_base * 100.0 / racion
        G_100g = G_base * 100.0 / racion
    elif racion > 0:
        P_100g = P_base * 100.0 / racion
        H_100g = H_base * 100.0 / racion
        G_100g = G_base * 100.0 / racion
    else:
        P_100g = P_base
        H_100g = H_base
        G_100g = G_base
    
    if cantidad_g is None:
        cantidad_g = racion
    
    categorias_raw = parse_categories(alimento.get("categorias", ""))
    categorias_num = get_numeric_categories(categorias_raw)
    
    if not categorias_num:
        predominante = get_macro_predominante(P_100g, H_100g, G_100g)
        if predominante > 0:
            return {
                "P": P_100g > 0.25 * predominante,
                "H": H_100g > 0.25 * predominante,
                "G": G_100g > 0.25 * predominante
            }
        return {"P": False, "H": False, "G": False}
    
    if len(categorias_num) == 1:
        return _regla_categoria(categorias_num[0], P_100g, H_100g, G_100g, cantidad_g, es_vegano)
    
    # Doble categoría: más permisiva
    cuenta_P = False
    cuenta_H = False
    cuenta_G = False
    for cat in categorias_num:
        r = _regla_categoria(cat, P_100g, H_100g, G_100g, cantidad_g, es_vegano)
        cuenta_P = cuenta_P or r["P"]
        cuenta_H = cuenta_H or r["H"]
        cuenta_G = cuenta_G or r["G"]
    
    return {"P": cuenta_P, "H": cuenta_H, "G": cuenta_G}


# =====================================================
# TESTS DE VERIFICACIÓN
# Ejecutar: python calma_engine.py
# Todos deben pasar SIN errores
# =====================================================

def run_tests():
    """Tests de verificación del motor CALMA v2."""
    
    print("=" * 60)
    print("TESTS CALMA v2 ENGINE")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    def test(name, result, expected):
        nonlocal passed, failed
        if result == expected:
            print(f"  ✅ {name}")
            passed += 1
        else:
            print(f"  ❌ {name}")
            print(f"     Esperado: {expected}")
            print(f"     Obtenido: {result}")
            failed += 1
    
    # --- TEST 1: Pechuga de pollo (cat 2.2) ---
    print("\n--- Pechuga de pollo (cat 2.2) ---")
    pollo = {"proteinas": 21, "hidratos": 0, "grasas": 1.5, "racion": 100, "categorias": "2.2 | FRE", "unidades": False}
    r = que_macros_cuentan(pollo, 150)
    test("P cuenta", r["P"], True)
    test("H no cuenta (0 < 2%)", r["H"], False)
    test("G no cuenta (1.5 < 3%)", r["G"], False)
    
    m = calcular_macros_efectivos(pollo, 150)
    test("P servido = 31.5", m["P"], 31.5)
    test("H servido = 0", m["H"], 0.0)
    test("G servido = 0", m["G"], 0.0)
    
    # --- TEST 2: Salmón (cat 3.1) con grasa alta ---
    print("\n--- Salmón (cat 3.1) con grasa ---")
    salmon = {"proteinas": 20, "hidratos": 0, "grasas": 13, "racion": 100, "categorias": "3.1 | FRE", "unidades": False}
    r = que_macros_cuentan(salmon, 200)
    test("P cuenta", r["P"], True)
    test("H no cuenta", r["H"], False)
    test("G cuenta (13 >= 3%)", r["G"], True)
    
    # --- TEST 3: Arroz basmati (cat 21) ---
    print("\n--- Arroz basmati (cat 21) ---")
    arroz = {"proteinas": 7, "hidratos": 78, "grasas": 0.6, "racion": 100, "categorias": "21.1 | GEN", "unidades": False}
    r = que_macros_cuentan(arroz, 80)
    test("P no cuenta (cat 21)", r["P"], False)
    test("H cuenta", r["H"], True)
    test("G no cuenta (0.6 < 6%)", r["G"], False)
    
    # --- TEST 4: Aceite oliva (cat 17.1.1) ---
    print("\n--- Aceite oliva (cat 17.1.1) ---")
    aove = {"proteinas": 0, "hidratos": 0, "grasas": 99, "racion": 10, "categorias": "17.1.1 | GEN", "unidades": False}
    r = que_macros_cuentan(aove, 15)
    test("P no cuenta", r["P"], False)
    test("H no cuenta", r["H"], False)
    test("G cuenta", r["G"], True)
    
    m = calcular_macros_efectivos(aove, 15)
    test("G servido = 148.5", m["G"], 148.5)  # 99 * 15/10 = 148.5
    
    # --- TEST 5: Verdura con H>4% (cat 13) ---
    print("\n--- Zanahoria con H>4% (cat 13) ---")
    zanahoria = {"proteinas": 0.9, "hidratos": 7, "grasas": 0.2, "racion": 100, "categorias": "13.1 | FRE", "unidades": False}
    r = que_macros_cuentan(zanahoria, 100)
    test("P no cuenta (cat 13 nunca)", r["P"], False)
    test("H cuenta (7 > 4%)", r["H"], True)
    test("G no cuenta (0.2 < 4%)", r["G"], False)
    
    # --- TEST 6: Verdura con H<4% (cat 13) ---
    print("\n--- Lechuga H<4% (cat 13) ---")
    lechuga = {"proteinas": 1.4, "hidratos": 2.9, "grasas": 0.2, "racion": 100, "categorias": "13.1 | FRE", "unidades": False}
    r = que_macros_cuentan(lechuga, 100)
    test("P no cuenta", r["P"], False)
    test("H no cuenta (2.9 < 4%)", r["H"], False)
    test("G no cuenta", r["G"], False)
    
    # --- TEST 7: Salsa con macros mixtos (cat 16) ---
    print("\n--- Salsa tomate frito (cat 16) ---")
    salsa = {"proteinas": 1.2, "hidratos": 8, "grasas": 4.5, "racion": 100, "categorias": "16.2 | YA", "unidades": False}
    r = que_macros_cuentan(salsa, 50)
    test("P no cuenta (1.2 < 6%)", r["P"], False)
    test("H cuenta (8 >= 6%)", r["H"], True)
    test("G no cuenta (4.5 < 6%)", r["G"], False)
    
    # --- TEST 8: DOBLE CATEGORÍA — Tomate frito (cat 13.8 + 16.2) ---
    print("\n--- Tomate frito DOBLE CAT (13.8 + 16.2) ---")
    tomate = {"proteinas": 0.8, "hidratos": 6.5, "grasas": 4.2, "racion": 100, "categorias": "13.8 | 16.2 | YA", "unidades": False}
    r = que_macros_cuentan(tomate, 50)
    test("P no cuenta (ambas dicen no)", r["P"], False)
    test("H cuenta (cat13: 6.5>4 SÍ, cat16: 6.5>=6 SÍ)", r["H"], True)
    test("G cuenta (cat13: 4.2>4 SÍ, cat16: 4.2<6 NO → SÍ por cat13)", r["G"], True)
    
    # --- TEST 9: Doble categoría permisiva con H entre 4 y 6 ---
    print("\n--- Alimento doble cat con 5H (13 + 16) ---")
    mixto = {"proteinas": 1, "hidratos": 5, "grasas": 3, "racion": 100, "categorias": "13.1 | 16.1", "unidades": False}
    r = que_macros_cuentan(mixto, 100)
    test("H cuenta (cat13: 5>4 SÍ, cat16: 5<6 NO → SÍ por cat13)", r["H"], True)
    
    # --- TEST 10: Proteína en polvo (cat 4) con H<=6 ---
    print("\n--- Whey isolate (cat 4.1) con H bajo ---")
    whey = {"proteinas": 90, "hidratos": 3, "grasas": 0.5, "racion": 100, "categorias": "4.1.1 | PRO", "unidades": False}
    r = que_macros_cuentan(whey, 30)
    test("P cuenta", r["P"], True)
    test("H no cuenta (3 <= 6%)", r["H"], False)
    test("G no cuenta (0.5 < 25% de 90)", r["G"], False)
    
    # --- TEST 11: Legumbres (cat 10) ---
    print("\n--- Garbanzos (cat 10) ---")
    garbanzos = {"proteinas": 19, "hidratos": 44, "grasas": 5, "racion": 100, "categorias": "10.2 | GEN", "unidades": False}
    r = que_macros_cuentan(garbanzos, 80)
    test("P cuenta (siempre en cat 10)", r["P"], True)
    test("H cuenta (siempre en cat 10)", r["H"], True)
    test("G no cuenta (5 < 8%)", r["G"], False)
    
    # --- TEST 12: Tubérculos (cat 9) ---
    print("\n--- Patata (cat 9) ---")
    patata = {"proteinas": 2, "hidratos": 17, "grasas": 0.1, "racion": 100, "categorias": "9 | FRE", "unidades": False}
    r = que_macros_cuentan(patata, 200)
    test("P no cuenta (cat 9 solo H)", r["P"], False)
    test("H cuenta", r["H"], True)
    test("G no cuenta (cat 9 solo H)", r["G"], False)
    
    # --- TEST 13: Aminoácidos (cat 41) ---
    print("\n--- BCAAs (cat 41) ---")
    bcaa = {"proteinas": 80, "hidratos": 5, "grasas": 0, "racion": 100, "categorias": "41 | PRO", "unidades": False}
    r = que_macros_cuentan(bcaa, 10)
    test("P cuenta", r["P"], True)
    test("H no cuenta (cat 41)", r["H"], False)
    test("G no cuenta (cat 41)", r["G"], False)
    
    # --- TEST 14: Sopas (cat 48) ---
    print("\n--- Sopa (cat 48) ---")
    sopa = {"proteinas": 2.5, "hidratos": 4, "grasas": 1.5, "racion": 100, "categorias": "48 | YA", "unidades": False}
    r = que_macros_cuentan(sopa, 300)
    test("P cuenta (2.5 >= 2%)", r["P"], True)
    test("H cuenta (4 >= 2%)", r["H"], True)
    test("G no cuenta (1.5 < 2%)", r["G"], False)
    
    # --- TEST 15: Frutos secos naturales (cat 17.2.1) <=50g ---
    print("\n--- Almendras 30g (cat 17.2.1) ---")
    almendras = {"proteinas": 21, "hidratos": 4, "grasas": 54, "racion": 100, "categorias": "17.2.1 | GEN", "unidades": False}
    r = que_macros_cuentan(almendras, 30)
    test("G cuenta (siempre)", r["G"], True)
    test("P no cuenta (21 < 54/2=27)", r["P"], False)
    test("H no cuenta (4 < 54/2=27)", r["H"], False)
    
    # --- TEST 16: Frutos secos naturales (cat 17.2.1) >50g ---
    print("\n--- Almendras 60g (cat 17.2.1) calibración ---")
    r = que_macros_cuentan(almendras, 60)
    test("G cuenta (siempre)", r["G"], True)
    test("P cuenta (21 > 54/4=13.5, calibración >50g)", r["P"], True)
    test("H no cuenta (4 < 54/4=13.5)", r["H"], False)
    
    # --- TEST 17: Modo vegano — proteína vegetal (cat 28) ---
    print("\n--- Tofu modo vegano (cat 28) ---")
    tofu = {"proteinas": 15, "hidratos": 2, "grasas": 9, "racion": 100, "categorias": "28 | 6.2", "unidades": False}
    r_normal = que_macros_cuentan(tofu, 100, es_vegano=False)
    r_vegano = que_macros_cuentan(tofu, 100, es_vegano=True)
    test("Normal: H no cuenta (2 < 25% de 15)", r_normal["H"], False)
    test("Vegano: H no cuenta (2 < 4g)", r_vegano["H"], False)
    
    tempeh = {"proteinas": 20, "hidratos": 8, "grasas": 11, "racion": 100, "categorias": "28 | 6.2", "unidades": False}
    r_vegano2 = que_macros_cuentan(tempeh, 100, es_vegano=True)
    test("Vegano tempeh: H cuenta (8 >= 4g)", r_vegano2["H"], True)
    
    # --- TEST 18: Lácteos (cat 5) ---
    print("\n--- Queso batido 0% (cat 5) ---")
    queso = {"proteinas": 8, "hidratos": 4, "grasas": 0.2, "racion": 100, "categorias": "5.2.2 | GEN", "unidades": False}
    r = que_macros_cuentan(queso, 200)
    test("P cuenta (siempre en cat 5)", r["P"], True)
    test("H cuenta (siempre en cat 5)", r["H"], True)
    test("G no cuenta (0.2 < 1%)", r["G"], False)
    
    # --- TEST 19: Zumo (cat 11.5) ---
    print("\n--- Zumo naranja (cat 11.5) ---")
    zumo = {"proteinas": 0.7, "hidratos": 10, "grasas": 0.2, "racion": 100, "categorias": "11.5 | GEN", "unidades": False}
    r = que_macros_cuentan(zumo, 200)
    test("H cuenta (cat 11, H siempre)", r["H"], True)
    test("P no cuenta (cat 11 solo H)", r["P"], False)
    
    # --- TEST 20: Croquetas (cat 17.9) ---
    print("\n--- Croquetas (cat 17.9) ---")
    croquetas = {"proteinas": 7, "hidratos": 20, "grasas": 12, "racion": 100, "categorias": "17.9 | YA", "unidades": False}
    r = que_macros_cuentan(croquetas, 100)
    test("P cuenta (cat 17.9 todo cuenta)", r["P"], True)
    test("H cuenta (cat 17.9 todo cuenta)", r["H"], True)
    test("G cuenta (cat 17.9 todo cuenta)", r["G"], True)
    
    # --- TEST 21: Bebida vegetal (cat 24) ---
    print("\n--- Bebida avena (cat 24) ---")
    beb_avena = {"proteinas": 0.3, "hidratos": 6, "grasas": 1.5, "racion": 100, "categorias": "24 | GEN", "unidades": False}
    r = que_macros_cuentan(beb_avena, 200)
    test("P no cuenta (cat 24 nunca)", r["P"], False)
    test("H cuenta (6 > 25% de 6 = 1.5)", r["H"], True)
    test("G cuenta (1.5 > 25% de 6 = 1.5? NO, 1.5 no es > 1.5)", r["G"], False)
    
    # --- RESUMEN ---
    print("\n" + "=" * 60)
    print(f"RESULTADO: {passed} pasados, {failed} fallidos de {passed + failed} tests")
    print("=" * 60)
    
    if failed > 0:
        print("\n⚠️  HAY TESTS FALLIDOS — REVISAR ANTES DE CONTINUAR")
    else:
        print("\n✅ TODOS LOS TESTS PASAN — Motor CALMA v2 OK")
    
    return failed == 0


if __name__ == "__main__":
    run_tests()
