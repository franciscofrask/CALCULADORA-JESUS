"""
CALMA v2 — Motor de cálculo de macros efectivos
Método Jesús Gallego — 12en12

Cada alimento tiene macros brutos (P, H, G por 100g).
Según su categoría, solo ciertos macros "cuentan".
Este motor aplica las reglas por categoría y devuelve los macros efectivos.
"""


def calcular_macros_efectivos(
    proteina_100g: float,
    hidratos_100g: float,
    grasa_100g: float,
    categoria: str,
    cantidad_g: float,
    categoria_secundaria: str = None,
    es_vegano: bool = False
) -> dict:
    """
    Calcula los macros efectivos de un alimento según las reglas CALMA v2.
    
    Args:
        proteina_100g: gramos de proteína por 100g del alimento
        hidratos_100g: gramos de hidratos por 100g del alimento
        grasa_100g: gramos de grasa por 100g del alimento
        categoria: categoría principal del alimento (string, ej: "2", "13", "17.2.1")
        cantidad_g: cantidad servida en gramos
        categoria_secundaria: segunda categoría si existe (para regla doble categoría)
        es_vegano: si el usuario es vegano (activa reglas especiales)
    
    Returns:
        dict con:
            proteina_efectiva: gramos de P que cuentan para la ración servida
            hidratos_efectivos: gramos de H que cuentan para la ración servida
            grasa_efectiva: gramos de G que cuentan para la ración servida
            proteina_cuenta: bool - si P cuenta o no
            hidratos_cuenta: bool - si H cuenta o no
            grasa_cuenta: bool - si G cuenta o no
    """
    
    # Paso 1: calcular macros brutos de la ración servida
    factor = cantidad_g / 100.0
    p_bruta = proteina_100g * factor
    h_bruta = hidratos_100g * factor
    g_bruta = grasa_100g * factor
    
    # Paso 2: determinar qué cuenta según categoría principal
    p_cuenta, h_cuenta, g_cuenta = _aplicar_reglas_categoria(
        proteina_100g, hidratos_100g, grasa_100g, 
        categoria, cantidad_g, es_vegano
    )
    
    # Paso 3: si hay categoría secundaria, aplicar regla de doble categoría
    # (la más permisiva: si CUALQUIERA dice que cuenta → cuenta)
    if categoria_secundaria:
        p2, h2, g2 = _aplicar_reglas_categoria(
            proteina_100g, hidratos_100g, grasa_100g,
            categoria_secundaria, cantidad_g, es_vegano
        )
        p_cuenta = p_cuenta or p2
        h_cuenta = h_cuenta or h2
        g_cuenta = g_cuenta or g2
    
    # Paso 4: calcular efectivos
    return {
        "proteina_efectiva": round(p_bruta, 1) if p_cuenta else 0.0,
        "hidratos_efectivos": round(h_bruta, 1) if h_cuenta else 0.0,
        "grasa_efectiva": round(g_bruta, 1) if g_cuenta else 0.0,
        "proteina_cuenta": p_cuenta,
        "hidratos_cuenta": h_cuenta,
        "grasa_cuenta": g_cuenta
    }


def _aplicar_reglas_categoria(
    p100: float, h100: float, g100: float,
    cat: str, cantidad_g: float, es_vegano: bool
) -> tuple:
    """
    Aplica las reglas de conteo según la categoría.
    Retorna (p_cuenta, h_cuenta, g_cuenta) como booleans.
    
    TODOS los porcentajes y umbrales se calculan sobre valores por 100g
    del alimento, NO sobre la ración servida (excepto calibraciones).
    """
    
    cat = str(cat).strip()
    
    # Macro predominante (por 100g)
    predominante = max(p100, h100, g100)
    
    # =====================================================
    # CAT 1 — Huevos y derivados
    # P: siempre | H: si >= 2% | G: si >= 3%
    # =====================================================
    if cat == "1":
        return (
            True,           # P siempre
            h100 >= 2.0,    # H si >= 2g por 100g
            g100 >= 3.0     # G si >= 3g por 100g
        )
    
    # =====================================================
    # CAT 2 — Carnes (aves, ternera, cerdo, otras)
    # P: siempre | H: si >= 2% | G: si >= 3%
    # =====================================================
    if cat == "2":
        return (
            True,
            h100 >= 2.0,
            g100 >= 3.0
        )
    
    # =====================================================
    # CAT 3 — Pescados (excepto 3.9)
    # P: siempre | H: si >= 2% | G: si >= 3%
    # =====================================================
    if cat == "3":
        return (
            True,
            h100 >= 2.0,
            g100 >= 3.0
        )
    
    # =====================================================
    # CAT 3.9 — Mariscos
    # P: siempre | H: si > 3% (estricto >) | G: si >= 3%
    # =====================================================
    if cat == "3.9":
        return (
            True,
            h100 > 3.0,     # OJO: > 3 (no >=), es "menor o igual a 3 NO cuenta"
            g100 >= 3.0
        )
    
    # =====================================================
    # CAT 4 — Proteína en polvo y barritas proteicas
    # P: siempre | H: si > 6% | G: regla general 25%
    # =====================================================
    if cat == "4" or cat.startswith("4."):
        # Excluir 4.1 y 4.2 en modo vegano (whey, caseína)
        g_cuenta = (predominante > 0 and g100 > 0.25 * predominante)
        return (
            True,
            h100 > 6.0,
            g_cuenta
        )
    
    # =====================================================
    # CAT 5 — Lácteos y derivados
    # P: siempre | H: siempre | G: si >= 1%
    # =====================================================
    if cat == "5" or cat.startswith("5."):
        return (
            True,
            True,
            g100 >= 1.0
        )
    
    # =====================================================
    # CAT 7 — Cereales excepto arroz
    # P: si > 1/3 del H (calibración: >100g servidos → P siempre)
    # H: siempre
    # G: si > 8% O si > 1/4 del H
    # =====================================================
    if cat == "7" or cat.startswith("7."):
        # Proteína
        if cantidad_g > 100:
            # Calibración: por encima de 100g, P SIEMPRE cuenta
            p_cuenta = True
        else:
            # Regla normal: P cuenta si > 1/3 del H
            p_cuenta = (h100 > 0 and p100 > h100 / 3.0)
        
        # Grasa: cuenta si > 8% O si > 1/4 del H
        g_cuenta = (g100 > 8.0) or (h100 > 0 and g100 > h100 / 4.0)
        
        return (p_cuenta, True, g_cuenta)
    
    # =====================================================
    # CAT 8 — Panes y tortillas de trigo
    # P: si > 1/3 del H (misma calibración que Cat 7)
    # H: siempre
    # G: si > 9% O si > 1/4 del H
    # =====================================================
    if cat == "8" or cat.startswith("8."):
        if cantidad_g > 100:
            p_cuenta = True
        else:
            p_cuenta = (h100 > 0 and p100 > h100 / 3.0)
        
        # Grasa: umbral 9% (no 8% como cereales)
        g_cuenta = (g100 > 9.0) or (h100 > 0 and g100 > h100 / 4.0)
        
        return (p_cuenta, True, g_cuenta)
    
    # =====================================================
    # CAT 9 — Tubérculos y derivados
    # SOLO hidratos. Nada más.
    # =====================================================
    if cat == "9" or cat.startswith("9."):
        return (False, True, False)
    
    # =====================================================
    # CAT 10 — Legumbres
    # P: siempre | H: siempre | G: si >= 8%
    # =====================================================
    if cat == "10" or cat.startswith("10."):
        return (
            True,
            True,
            g100 >= 8.0
        )
    
    # =====================================================
    # CAT 11 — Frutas, zumos, mermeladas
    # SOLO hidratos. Nada más.
    # =====================================================
    if cat == "11" or cat.startswith("11."):
        return (False, True, False)
    
    # =====================================================
    # CAT 13 — Verduras y hortalizas (excepto 13.9)
    # P: nunca | H: si > 4% por 100g | G: si > 4% por 100g
    # EXCEPCIÓN: H y G cuentan si >4% AUNQUE no superen 25% del predominante
    # =====================================================
    if cat == "13.9":
        # Cat 13.9 — Ensaladas preparadas (regla diferente)
        return (
            (h100 > 0 and p100 > h100 / 4.0),  # P si > 1/4 del H
            True,                                 # H siempre (implícito)
            g100 > 3.0                            # G si > 3%
        )
    
    if cat == "13" or cat.startswith("13."):
        return (
            False,          # P nunca
            h100 > 4.0,     # H si > 4g por 100g
            g100 > 4.0      # G si > 4g por 100g
        )
    
    # =====================================================
    # CAT 16 — Salsas, siropes y konjac
    # Cualquier macro < 6% NO cuenta (independiente de predominancia)
    # =====================================================
    if cat == "16" or cat.startswith("16."):
        return (
            p100 >= 6.0,
            h100 >= 6.0,
            g100 >= 6.0
        )
    
    # =====================================================
    # CAT 17.1, 17.4, 17.6, 17.10 — Aceites, mantequilla, aguacate, mayo
    # SOLO grasa. Nada más.
    # =====================================================
    if cat in ("17.1", "17.4", "17.6", "17.10"):
        return (False, False, True)
    if cat.startswith("17.1.") or cat.startswith("17.4.") or \
       cat.startswith("17.6.") or cat.startswith("17.10."):
        return (False, False, True)
    
    # =====================================================
    # CAT 17.2.6, 17.9 — Frutos secos en polvo y croquetas
    # TODO cuenta sin reglas
    # (Poner ANTES de 17.2.x para que no lo pille la regla de frutos secos)
    # =====================================================
    if cat in ("17.2.6", "17.9"):
        return (True, True, True)
    if cat.startswith("17.2.6.") or cat.startswith("17.9."):
        return (True, True, True)
    
    # =====================================================
    # CAT 17.2.1, 17.2.3, 17.2.4 — Frutos secos naturales y semillas
    # G: siempre | P: si > 1/2 pred | H: si > 1/2 pred
    # Calibración: > 50g servidos → P y H SIEMPRE cuentan
    # =====================================================
    if cat in ("17.2.1", "17.2.3", "17.2.4"):
        if cantidad_g > 50:
            # Calibración: P y H siempre cuentan
            return (True, True, True)
        else:
            p_cuenta = (predominante > 0 and p100 > predominante / 2.0)
            h_cuenta = (predominante > 0 and h100 > predominante / 2.0)
            return (p_cuenta, h_cuenta, True)
    if cat.startswith("17.2.1.") or cat.startswith("17.2.3.") or \
       cat.startswith("17.2.4."):
        if cantidad_g > 50:
            return (True, True, True)
        else:
            p_cuenta = (predominante > 0 and p100 > predominante / 2.0)
            h_cuenta = (predominante > 0 and h100 > predominante / 2.0)
            return (p_cuenta, h_cuenta, True)
    
    # =====================================================
    # CAT 17.2.2, 17.2.5, 17.5 (excepto 17.5.3) 
    # H: siempre | G: siempre | P: si > 1/2 pred
    # =====================================================
    if cat == "17.5.3":
        # Cat 17.5.3 — regla propia: P siempre, G siempre, H si > 1/2 pred
        h_cuenta = (predominante > 0 and h100 > predominante / 2.0)
        return (True, h_cuenta, True)
    
    if cat in ("17.2.2", "17.2.5", "17.5") or \
       cat.startswith("17.2.2.") or cat.startswith("17.2.5.") or \
       cat.startswith("17.5."):
        p_cuenta = (predominante > 0 and p100 > predominante / 2.0)
        return (p_cuenta, True, True)
    
    # =====================================================
    # CAT 17 — Cualquier otra subcategoría de 17 no cubierta
    # Solo grasa (fallback seguro para grasas)
    # =====================================================
    if cat == "17" or cat.startswith("17."):
        return (False, False, True)
    
    # =====================================================
    # CAT 21 — Arroces y derivados
    # P: nunca | H: siempre | G: si >= 6%
    # =====================================================
    if cat == "21" or cat.startswith("21."):
        return (
            False,
            True,
            g100 >= 6.0
        )
    
    # =====================================================
    # CAT 22.1.2.2, 22.6, 22.7 — Excepciones de pasta: TODO cuenta
    # (Poner ANTES de 22 genérico)
    # =====================================================
    if cat in ("22.1.2.2", "22.6", "22.7"):
        return (True, True, True)
    if cat.startswith("22.1.2.2.") or cat.startswith("22.6.") or \
       cat.startswith("22.7."):
        return (True, True, True)
    
    # =====================================================
    # CAT 22 — Pasta y quinoa (general)
    # P: si > 1/3 del H | H: siempre | G: si > 9% O > 1/3 del H
    # =====================================================
    if cat == "22" or cat.startswith("22."):
        p_cuenta = (h100 > 0 and p100 > h100 / 3.0)
        g_cuenta = (g100 > 9.0) or (h100 > 0 and g100 > h100 / 3.0)
        return (p_cuenta, True, g_cuenta)
    
    # =====================================================
    # CAT 24 — Bebidas vegetales
    # P: nunca | H: siempre | G: regla general 25%
    # =====================================================
    if cat == "24" or cat.startswith("24."):
        g_cuenta = (predominante > 0 and g100 > 0.25 * predominante)
        return (False, True, g_cuenta)
    
    # =====================================================
    # CAT 28 — Proteína vegetal (modo vegano)
    # Regla general 25%, pero H siempre si >= 4g/100g
    # =====================================================
    if cat == "28" or cat.startswith("28."):
        p_cuenta = (predominante > 0 and p100 > 0.25 * predominante)
        h_cuenta = (h100 >= 4.0) or (predominante > 0 and h100 > 0.25 * predominante)
        g_cuenta = (predominante > 0 and g100 > 0.25 * predominante)
        return (p_cuenta, h_cuenta, g_cuenta)
    
    # =====================================================
    # CAT 37 — Cacao, azúcares, chucherías, miel
    # H: siempre | P: si > 1/2 pred | G: si > 10%
    # =====================================================
    if cat == "37" or cat.startswith("37."):
        p_cuenta = (predominante > 0 and p100 > predominante / 2.0)
        return (p_cuenta, True, g100 > 10.0)
    
    # =====================================================
    # CAT 38.1 — Patatas fritas y derivados
    # H: siempre | G: siempre | P: si > 1/2 pred
    # =====================================================
    if cat == "38.1" or cat.startswith("38.1."):
        p_cuenta = (predominante > 0 and p100 > predominante / 2.0)
        return (p_cuenta, True, True)
    
    # =====================================================
    # CAT 41 — Aminoácidos para entrenar
    # P: siempre | H: nunca | G: nunca
    # =====================================================
    if cat == "41" or cat.startswith("41."):
        return (True, False, False)
    
    # =====================================================
    # CAT 48 — Sopas y caldos
    # Todo cuenta si >= 2% (2g por 100g)
    # =====================================================
    if cat == "48" or cat.startswith("48."):
        return (
            p100 >= 2.0,
            h100 >= 2.0,
            g100 >= 2.0
        )
    
    # =====================================================
    # CAT 52 — Mundo vegano
    # Todo cuenta si >= 2% (igual que sopas)
    # =====================================================
    if cat == "52" or cat.startswith("52."):
        return (
            p100 >= 2.0,
            h100 >= 2.0,
            g100 >= 2.0
        )
    
    # =====================================================
    # CAT 49, 50, 51, 53 — Comida rápida, asiática, preparada, superalimentos
    # Regla general del 25%
    # =====================================================
    if cat in ("49", "50", "51", "53") or \
       cat.startswith("49.") or cat.startswith("50.") or \
       cat.startswith("51.") or cat.startswith("53."):
        if predominante == 0:
            return (False, False, False)
        return (
            p100 > 0.25 * predominante,
            h100 > 0.25 * predominante,
            g100 > 0.25 * predominante
        )
    
    # =====================================================
    # FALLBACK — Regla general del 25%
    # Para cualquier categoría no listada arriba
    # =====================================================
    if predominante == 0:
        return (False, False, False)
    return (
        p100 > 0.25 * predominante,
        h100 > 0.25 * predominante,
        g100 > 0.25 * predominante
    )


# =========================================================
# FUNCIÓN AUXILIAR: Calcular cantidad automática
# =========================================================

def calcular_cantidad_automatica(
    proteina_100g: float,
    hidratos_100g: float,
    grasa_100g: float,
    categoria: str,
    macros_restantes: dict,
    categoria_secundaria: str = None,
    es_vegano: bool = False
) -> dict:
    """
    Calcula la cantidad óptima de un alimento para cubrir los macros restantes
    sin pasarse en ninguno.
    
    Args:
        macros_restantes: {"proteina": X, "hidratos": Y, "grasa": Z}
    
    Returns:
        dict con cantidad_g, macros_efectivos
    """
    
    p_rest = macros_restantes.get("proteina", 0)
    h_rest = macros_restantes.get("hidratos", 0)
    g_rest = macros_restantes.get("grasa", 0)
    
    # Calcular macros efectivos por 100g (con cantidad estimada de 100g)
    ef_100 = calcular_macros_efectivos(
        proteina_100g, hidratos_100g, grasa_100g,
        categoria, 100.0, categoria_secundaria, es_vegano
    )
    
    p_ef = ef_100["proteina_efectiva"]
    h_ef = ef_100["hidratos_efectivos"]
    g_ef = ef_100["grasa_efectiva"]
    
    # Calcular cantidad máxima por cada macro
    cantidades = []
    if p_ef > 0 and p_rest > 0:
        cantidades.append(p_rest / p_ef * 100)
    if h_ef > 0 and h_rest > 0:
        cantidades.append(h_rest / h_ef * 100)
    if g_ef > 0 and g_rest > 0:
        cantidades.append(g_rest / g_ef * 100)
    
    if not cantidades:
        # Ningún macro efectivo coincide con lo que necesitamos
        return {
            "cantidad_g": 0,
            "macros_efectivos": {"proteina": 0, "hidratos": 0, "grasa": 0}
        }
    
    # Elegir la cantidad MÍNIMA (macro más limitante)
    cantidad = min(cantidades)
    
    # Redondear según categoría
    cantidad = _redondear_cantidad(cantidad, categoria)
    
    # Asegurar mínimo de 5g
    if cantidad < 5:
        cantidad = 5
    
    # Recalcular macros efectivos con la cantidad redondeada
    # NOTA: Recalcular porque la calibración puede cambiar con la nueva cantidad
    resultado = calcular_macros_efectivos(
        proteina_100g, hidratos_100g, grasa_100g,
        categoria, cantidad, categoria_secundaria, es_vegano
    )
    
    return {
        "cantidad_g": cantidad,
        "macros_efectivos": {
            "proteina": resultado["proteina_efectiva"],
            "hidratos": resultado["hidratos_efectivos"],
            "grasa": resultado["grasa_efectiva"]
        }
    }


def _redondear_cantidad(cantidad: float, categoria: str) -> float:
    """Redondea la cantidad según el tipo de alimento."""
    cat = str(categoria).strip()
    
    # Pan: múltiplos de 10g
    if cat == "8" or cat.startswith("8."):
        return round(cantidad / 10) * 10
    
    # Arroz, pasta, patata, carne, pescado, verduras: múltiplos de 25g
    if cat in ("2", "3", "9", "13", "21", "22") or \
       cat.startswith("2.") or cat.startswith("3.") or \
       cat.startswith("9.") or cat.startswith("13.") or \
       cat.startswith("21.") or cat.startswith("22."):
        return round(cantidad / 25) * 25
    
    # Huevos: múltiplos de 55g (aprox 1 huevo)
    if cat == "1" or cat.startswith("1."):
        return round(cantidad / 55) * 55
    
    # Frutos secos, proteína polvo, cereales: múltiplos de 5g
    if cat.startswith("17.2") or cat.startswith("4") or \
       cat == "7" or cat.startswith("7."):
        return round(cantidad / 5) * 5
    
    # Aceite: múltiplos de 5ml
    if cat in ("17.1", "17.4", "17.6", "17.10") or \
       cat.startswith("17.1.") or cat.startswith("17.4.") or \
       cat.startswith("17.6.") or cat.startswith("17.10."):
        return round(cantidad / 5) * 5
    
    # Fruta: múltiplos de 25g (aprox media pieza)
    if cat == "11" or cat.startswith("11."):
        return round(cantidad / 25) * 25
    
    # Lácteos: múltiplos de 25g
    if cat == "5" or cat.startswith("5."):
        return round(cantidad / 25) * 25
    
    # Default: múltiplos de 10g
    return round(cantidad / 10) * 10


# =========================================================
# TESTS INTEGRADOS
# =========================================================

def run_tests():
    """Ejecuta todos los tests de verificación. Retorna dict con resultados."""
    
    tests = []
    
    def test(nombre, resultado, esperado_p, esperado_h, esperado_g, tolerancia=0.5):
        p_ok = abs(resultado["proteina_efectiva"] - esperado_p) <= tolerancia
        h_ok = abs(resultado["hidratos_efectivos"] - esperado_h) <= tolerancia
        g_ok = abs(resultado["grasa_efectiva"] - esperado_g) <= tolerancia
        passed = p_ok and h_ok and g_ok
        tests.append({
            "nombre": nombre,
            "passed": passed,
            "resultado": {
                "P": resultado["proteina_efectiva"],
                "H": resultado["hidratos_efectivos"],
                "G": resultado["grasa_efectiva"]
            },
            "esperado": {"P": esperado_p, "H": esperado_h, "G": esperado_g},
            "detalle": f"P:{'✅' if p_ok else '❌'} H:{'✅' if h_ok else '❌'} G:{'✅' if g_ok else '❌'}"
        })
        return passed
    
    # ===== CAT 1: HUEVOS =====
    # Huevo entero (13P, 0.7H, 10G /100g) - 120g (2 huevos)
    r = calcular_macros_efectivos(13, 0.7, 10, "1", 120)
    test("Cat1: Huevo entero 120g", r, 15.6, 0, 12.0)  # H=0 (0.7<2), G=12 (10>=3)
    
    # Claras (11P, 0.7H, 0.2G /100g) - 180g
    r = calcular_macros_efectivos(11, 0.7, 0.2, "1", 180)
    test("Cat1: Claras 180g", r, 19.8, 0, 0)  # H=0 (0.7<2), G=0 (0.2<3)
    
    # ===== CAT 2: CARNES =====
    # Pechuga pollo (21P, 0H, 1.5G /100g) - 200g
    r = calcular_macros_efectivos(21, 0, 1.5, "2", 200)
    test("Cat2: Pechuga pollo 200g", r, 42.0, 0, 0)  # G=0 (1.5<3)
    
    # Contramuslo sin piel (24P, 0H, 4.5G /100g) - 175g
    r = calcular_macros_efectivos(24, 0, 4.5, "2", 175)
    test("Cat2: Contramuslo 175g", r, 42.0, 0, 7.9)  # G=7.9 (4.5>=3)
    
    # Pechuga pavo (24P, 0H, 1G /100g) - 200g
    r = calcular_macros_efectivos(24, 0, 1, "2", 200)
    test("Cat2: Pechuga pavo 200g", r, 48.0, 0, 0)  # G=0 (1<3)
    
    # ===== CAT 3: PESCADOS =====
    # Merluza (17P, 0H, 0.8G /100g) - 200g
    r = calcular_macros_efectivos(17, 0, 0.8, "3", 200)
    test("Cat3: Merluza 200g", r, 34.0, 0, 0)  # G=0 (0.8<3)
    
    # Salmón (22P, 0H, 13G /100g) - 200g
    r = calcular_macros_efectivos(22, 0, 13, "3", 200)
    test("Cat3: Salmón 200g", r, 44.0, 0, 26.0)  # G=26 (13>=3)
    
    # ===== CAT 3.9: MARISCOS =====
    # Gambas (20P, 1.5H, 1G /100g) - 150g
    r = calcular_macros_efectivos(20, 1.5, 1, "3.9", 150)
    test("Cat3.9: Gambas 150g", r, 30.0, 0, 0)  # H=0 (1.5<=3), G=0 (1<3)
    
    # Mejillones (12P, 3.5H, 2G /100g) - 200g
    r = calcular_macros_efectivos(12, 3.5, 2, "3.9", 200)
    test("Cat3.9: Mejillones 200g", r, 24.0, 7.0, 0)  # H=7 (3.5>3), G=0 (2<3)
    
    # ===== CAT 4: PROTEÍNA EN POLVO =====
    # Whey Isolate (85P, 3H, 1G /100g) - 30g
    r = calcular_macros_efectivos(85, 3, 1, "4", 30)
    test("Cat4: Whey Isolate 30g", r, 25.5, 0, 0)  # H=0 (3<=6), G=0 (1/85=1.2%<25%)
    
    # Whey normal (75P, 8H, 6G /100g) - 35g
    r = calcular_macros_efectivos(75, 8, 6, "4", 35)
    test("Cat4: Whey normal 35g", r, 26.3, 2.8, 0)  # H=2.8 (8>6), G=0 (6/75=8%<25%)
    
    # Barrita proteica (35P, 30H, 10G /100g) - 60g
    r = calcular_macros_efectivos(35, 30, 10, "4", 60)
    test("Cat4: Barrita 60g", r, 21.0, 18.0, 6.0)  # H=18 (30>6), G=6 (10/35=29%>25%)
    
    # ===== CAT 5: LÁCTEOS =====
    # Yogur griego (10P, 3.5H, 10G /100g) - 200g
    r = calcular_macros_efectivos(10, 3.5, 10, "5", 200)
    test("Cat5: Yogur griego 200g", r, 20.0, 7.0, 20.0)  # P+H siempre, G=20 (10>=1)
    
    # Queso batido 0% (8P, 3.5H, 0.1G /100g) - 250g
    r = calcular_macros_efectivos(8, 3.5, 0.1, "5", 250)
    test("Cat5: Queso batido 0% 250g", r, 20.0, 8.8, 0)  # G=0 (0.1<1)
    
    # Leche desnatada (3.4P, 4.8H, 0.3G /100g) - 250ml
    r = calcular_macros_efectivos(3.4, 4.8, 0.3, "5", 250)
    test("Cat5: Leche desnatada 250ml", r, 8.5, 12.0, 0)  # G=0 (0.3<1)
    
    # ===== CAT 7: CEREALES =====
    # Avena (12P, 60H, 7G /100g) - 60g (<=100g)
    r = calcular_macros_efectivos(12, 60, 7, "7", 60)
    test("Cat7: Avena 60g", r, 0, 36.0, 0)  # P=0 (12/60=0.2<0.33), G=0 (7<8, 7/60=0.12<0.25)
    
    # Avena (12P, 60H, 7G /100g) - 120g (>100g, calibración)
    r = calcular_macros_efectivos(12, 60, 7, "7", 120)
    test("Cat7: Avena 120g CALIBRACIÓN", r, 14.4, 72.0, 0)  # P=14.4 (>100g → P siempre)
    
    # Granola grasa (8P, 55H, 15G /100g) - 60g
    r = calcular_macros_efectivos(8, 55, 15, "7", 60)
    test("Cat7: Granola grasa 60g", r, 0, 33.0, 9.0)  # P=0 (8/55=0.15<0.33), G=9 (15>8)
    
    # ===== CAT 8: PANES =====
    # Pan de barra (9P, 50H, 1G /100g) - 60g
    r = calcular_macros_efectivos(9, 50, 1, "8", 60)
    test("Cat8: Pan barra 60g", r, 0, 30.0, 0)  # P=0 (9/50=0.18<0.33), G=0 (1<9, 1/50<0.25)
    
    # Pan integral (10P, 44H, 2G /100g) - 120g (>100g)
    r = calcular_macros_efectivos(10, 44, 2, "8", 120)
    test("Cat8: Pan integral 120g CALIBRACIÓN", r, 12.0, 52.8, 0)  # P=12 (>100g → P siempre)
    
    # ===== CAT 9: TUBÉRCULOS =====
    # Patata (2P, 17H, 0.1G /100g) - 200g
    r = calcular_macros_efectivos(2, 17, 0.1, "9", 200)
    test("Cat9: Patata 200g", r, 0, 34.0, 0)  # SOLO H
    
    # Boniato (1.5P, 21H, 0.1G /100g) - 150g
    r = calcular_macros_efectivos(1.5, 21, 0.1, "9", 150)
    test("Cat9: Boniato 150g", r, 0, 31.5, 0)
    
    # ===== CAT 10: LEGUMBRES =====
    # Lentejas cocidas (9P, 20H, 0.4G /100g) - 250g
    r = calcular_macros_efectivos(9, 20, 0.4, "10", 250)
    test("Cat10: Lentejas 250g", r, 22.5, 50.0, 0)  # P+H siempre, G=0 (0.4<8)
    
    # Garbanzos cocidos (9P, 27H, 2.6G /100g) - 200g
    r = calcular_macros_efectivos(9, 27, 2.6, "10", 200)
    test("Cat10: Garbanzos 200g", r, 18.0, 54.0, 0)  # G=0 (2.6<8)
    
    # ===== CAT 11: FRUTAS =====
    # Plátano (1P, 23H, 0.3G /100g) - 120g
    r = calcular_macros_efectivos(1, 23, 0.3, "11", 120)
    test("Cat11: Plátano 120g", r, 0, 27.6, 0)  # SOLO H
    
    # Manzana (0.3P, 14H, 0.2G /100g) - 180g
    r = calcular_macros_efectivos(0.3, 14, 0.2, "11", 180)
    test("Cat11: Manzana 180g", r, 0, 25.2, 0)
    
    # ===== CAT 13: VERDURAS =====
    # Lechuga (1.4P, 1.8H, 0.2G /100g) - 150g
    r = calcular_macros_efectivos(1.4, 1.8, 0.2, "13", 150)
    test("Cat13: Lechuga 150g", r, 0, 0, 0)  # H=0 (1.8<=4), G=0 (0.2<=4)
    
    # Brócoli (2.8P, 2.4H, 0.4G /100g) - 200g
    r = calcular_macros_efectivos(2.8, 2.4, 0.4, "13", 200)
    test("Cat13: Brócoli 200g", r, 0, 0, 0)  # H=0 (2.4<=4)
    
    # Zanahoria (0.9P, 7H, 0.2G /100g) - 200g
    r = calcular_macros_efectivos(0.9, 7, 0.2, "13", 200)
    test("Cat13: Zanahoria 200g", r, 0, 14.0, 0)  # H=14 (7>4), G=0 (0.2<=4)
    
    # Guisantes (5P, 14H, 0.4G /100g) - 150g
    r = calcular_macros_efectivos(5, 14, 0.4, "13", 150)
    test("Cat13: Guisantes 150g", r, 0, 21.0, 0)  # H sí (14>4), P nunca
    
    # ===== CAT 16: SALSAS =====
    # Ketchup (1P, 25H, 0.1G /100g) - 30g
    r = calcular_macros_efectivos(1, 25, 0.1, "16", 30)
    test("Cat16: Ketchup 30g", r, 0, 7.5, 0)  # P=0 (1<6), H=7.5 (25>=6), G=0 (0.1<6)
    
    # Salsa de soja (8P, 5H, 0G /100g) - 15g
    r = calcular_macros_efectivos(8, 5, 0, "16", 15)
    test("Cat16: Salsa soja 15g", r, 1.2, 0, 0)  # P=1.2 (8>=6), H=0 (5<6)
    
    # ===== CAT 17.1: ACEITES =====
    # Aceite oliva (0P, 0H, 100G /100g) - 10ml
    r = calcular_macros_efectivos(0, 0, 100, "17.1", 10)
    test("Cat17.1: Aceite oliva 10ml", r, 0, 0, 10.0)  # SOLO G
    
    # ===== CAT 17.6: AGUACATE =====
    # Aguacate (2P, 2H, 15G /100g) - 50g
    r = calcular_macros_efectivos(2, 2, 15, "17.6", 50)
    test("Cat17.6: Aguacate 50g", r, 0, 0, 7.5)  # SOLO G
    
    # ===== CAT 17.2.1: FRUTOS SECOS =====
    # Almendras (21P, 4H, 54G /100g) - 30g (<=50g)
    r = calcular_macros_efectivos(21, 4, 54, "17.2.1", 30)
    test("Cat17.2.1: Almendras 30g", r, 0, 0, 16.2)  # P=0 (21/54=0.39<0.5), H=0

    # Almendras - 60g (>50g, calibración)
    r = calcular_macros_efectivos(21, 4, 54, "17.2.1", 60)
    test("Cat17.2.1: Almendras 60g CALIBRACIÓN", r, 12.6, 2.4, 32.4)  # TODO cuenta
    
    # Cacahuetes (26P, 16H, 49G /100g) - 30g (<=50g)
    r = calcular_macros_efectivos(26, 16, 49, "17.2.1", 30)
    test("Cat17.2.1: Cacahuetes 30g", r, 7.8, 0, 14.7)  # P=7.8 (26/49=0.53>0.5), H=0 (16/49=0.33<0.5)
    
    # Cacahuetes - 60g (>50g)
    r = calcular_macros_efectivos(26, 16, 49, "17.2.1", 60)
    test("Cat17.2.1: Cacahuetes 60g CALIBRACIÓN", r, 15.6, 9.6, 29.4)
    
    # Nueces (15P, 7H, 65G /100g) - 25g (<=50g)
    r = calcular_macros_efectivos(15, 7, 65, "17.2.1", 25)
    test("Cat17.2.1: Nueces 25g", r, 0, 0, 16.3)  # P=0 (15/65=0.23<0.5)
    
    # ===== CAT 17.2.6: FRUTOS SECOS POLVO =====
    # Todo cuenta
    r = calcular_macros_efectivos(20, 30, 40, "17.2.6", 50)
    test("Cat17.2.6: F.secos polvo 50g", r, 10.0, 15.0, 20.0)
    
    # ===== CAT 21: ARROCES =====
    # Arroz blanco (7P, 78H, 0.6G /100g) - 100g
    r = calcular_macros_efectivos(7, 78, 0.6, "21", 100)
    test("Cat21: Arroz blanco 100g", r, 0, 78.0, 0)  # P nunca, G=0 (0.6<6)
    
    # ===== CAT 22: PASTA =====
    # Pasta normal (13P, 71H, 1.5G /100g) - 80g
    r = calcular_macros_efectivos(13, 71, 1.5, "22", 80)
    test("Cat22: Pasta normal 80g", r, 0, 56.8, 0)  # P=0 (13/71=0.18<0.33), G=0
    
    # ===== CAT 9: TUBÉRCULOS (solo H) =====
    r = calcular_macros_efectivos(2, 17, 0.1, "9", 300)
    test("Cat9: Patata 300g", r, 0, 51.0, 0)
    
    # ===== CAT 37: CACAO/AZÚCAR =====
    # Chocolate 70% (8P, 33H, 42G /100g) - 25g
    r = calcular_macros_efectivos(8, 33, 42, "37", 25)
    test("Cat37: Chocolate 70% 25g", r, 0, 8.3, 10.5)  # P=0 (8/42=0.19<0.5), G=10.5 (42>10)
    
    # Miel (0.3P, 82H, 0G /100g) - 20g
    r = calcular_macros_efectivos(0.3, 82, 0, "37", 20)
    test("Cat37: Miel 20g", r, 0, 16.4, 0)  # P=0 (0.3/82<0.5), G=0 (0<=10)
    
    # ===== CAT 38.1: PATATAS FRITAS =====
    # Patatas fritas (6P, 45H, 30G /100g) - 50g
    r = calcular_macros_efectivos(6, 45, 30, "38.1", 50)
    test("Cat38.1: Patatas fritas 50g", r, 0, 22.5, 15.0)  # P=0 (6/45=0.13<0.5), H+G siempre
    
    # ===== CAT 41: AMINOÁCIDOS =====
    # EAA (80P, 5H, 0G /100g) - 15g
    r = calcular_macros_efectivos(80, 5, 0, "41", 15)
    test("Cat41: EAA 15g", r, 12.0, 0, 0)  # Solo P
    
    # ===== CAT 48: SOPAS =====
    # Sopa verduras (1.5P, 4H, 1G /100g) - 300g
    r = calcular_macros_efectivos(1.5, 4, 1, "48", 300)
    test("Cat48: Sopa verduras 300g", r, 0, 12.0, 0)  # P=0 (1.5<2), H=12 (4>=2), G=0 (1<2)
    
    # ===== CAT 24: BEBIDAS VEGETALES =====
    # Leche almendras (0.5P, 3H, 1.1G /100g) - 200ml
    r = calcular_macros_efectivos(0.5, 3, 1.1, "24", 200)
    test("Cat24: Leche almendras 200ml", r, 0, 6.0, 2.2)  # G SÍ cuenta (1.1>25% de 3)
    
    # ===== DOBLE CATEGORÍA =====
    # Alimento con Cat 9 (solo H) + Cat 2 (P siempre, G si >=3%)
    # Más permisiva: P cuenta (por Cat 2), H cuenta (por Cat 9)
    r = calcular_macros_efectivos(5, 17, 0.5, "9", 200, categoria_secundaria="2")
    test("DOBLE CAT: 9+2 200g", r, 10.0, 34.0, 0)  # P=10 (por Cat 2), H=34 (por Cat 9), G=0 (<3 en ambas)
    
    # ===== RESUMEN =====
    total = len(tests)
    passed = sum(1 for t in tests if t["passed"])
    failed = [t for t in tests if not t["passed"]]
    
    return {
        "total": total,
        "passed": passed,
        "failed_count": total - passed,
        "all_passed": passed == total,
        "tests": tests,
        "failed_tests": failed
    }


# Ejecutar si se llama directamente
if __name__ == "__main__":
    results = run_tests()
    print(f"\n{'='*60}")
    print(f"CALMA v2 — Tests: {results['passed']}/{results['total']}")
    print(f"{'='*60}")
    if results["all_passed"]:
        print("✅ TODOS LOS TESTS PASAN")
    else:
        print("❌ TESTS FALLIDOS:")
        for t in results["failed_tests"]:
            print(f"  - {t['nombre']}: {t['detalle']}")
            print(f"    Resultado: {t['resultado']}")
            print(f"    Esperado:  {t['esperado']}")



# =========================================================
# FUNCIONES WRAPPER para compatibilidad con server.py
# Estas funciones reciben un objeto "alimento" de MongoDB
# y llaman a las funciones principales con los parámetros correctos
# =========================================================

def calcular_macros_efectivos_alimento(alimento: dict, cantidad_g: float, es_vegano: bool = False) -> dict:
    """
    Wrapper que recibe un objeto alimento de MongoDB.
    Extrae los valores necesarios y llama a calcular_macros_efectivos.
    
    Retorna dict con formato {"P": float, "H": float, "G": float, "kcal": float}
    """
    # Extraer macros por 100g del alimento
    p100 = float(alimento.get("proteinas", 0) or 0)
    h100 = float(alimento.get("hidratos", 0) or 0)
    g100 = float(alimento.get("grasas", 0) or 0)
    
    # Extraer categorías usando parse_categories
    categorias = parse_categories(alimento.get("categorias", []))
    categoria = categorias[0] if categorias else "0"
    
    # Categoría secundaria si existe
    categoria_secundaria = categorias[1] if len(categorias) > 1 else None
    
    # Llamar a la función principal
    resultado = calcular_macros_efectivos(
        p100, h100, g100, categoria, cantidad_g, categoria_secundaria, es_vegano
    )
    
    # Convertir al formato esperado por server.py
    p_ef = resultado["proteina_efectiva"]
    h_ef = resultado["hidratos_efectivos"]
    g_ef = resultado["grasa_efectiva"]
    kcal = p_ef * 4 + h_ef * 4 + g_ef * 9
    
    return {
        "P": round(p_ef, 1),
        "H": round(h_ef, 1),
        "G": round(g_ef, 1),
        "kcal": round(kcal, 1)
    }


def calcular_macros_brutos(alimento: dict, cantidad_g: float) -> dict:
    """
    Calcula los macros BRUTOS (sin aplicar reglas) de un alimento.
    Simplemente multiplica los valores por 100g por la cantidad.
    
    Retorna dict con formato {"P": float, "H": float, "G": float, "kcal": float}
    """
    factor = cantidad_g / 100.0
    p = float(alimento.get("proteinas", 0) or 0) * factor
    h = float(alimento.get("hidratos", 0) or 0) * factor
    g = float(alimento.get("grasas", 0) or 0) * factor
    kcal = p * 4 + h * 4 + g * 9
    
    return {
        "P": round(p, 1),
        "H": round(h, 1),
        "G": round(g, 1),
        "kcal": round(kcal, 1)
    }


def que_macros_cuentan(alimento: dict, cantidad_g: float, es_vegano: bool = False) -> dict:
    """
    Determina qué macros cuentan para un alimento dado.
    
    Retorna dict con formato {"P": bool, "H": bool, "G": bool}
    """
    # Extraer macros por 100g del alimento
    p100 = float(alimento.get("proteinas", 0) or 0)
    h100 = float(alimento.get("hidratos", 0) or 0)
    g100 = float(alimento.get("grasas", 0) or 0)
    
    # Extraer categorías usando parse_categories
    categorias = parse_categories(alimento.get("categorias", []))
    categoria = categorias[0] if categorias else "0"
    
    # Categoría secundaria si existe
    categoria_secundaria = categorias[1] if len(categorias) > 1 else None
    
    # Llamar a la función principal
    resultado = calcular_macros_efectivos(
        p100, h100, g100, categoria, cantidad_g, categoria_secundaria, es_vegano
    )
    
    return {
        "P": resultado["proteina_cuenta"],
        "H": resultado["hidratos_cuenta"],
        "G": resultado["grasa_cuenta"]
    }

# =========================================================
# FUNCIONES AUXILIARES para manejo de categorías
# Usadas por calculator.py para filtrado de alimentos
# =========================================================

def parse_categories(categorias) -> list:
    """
    Convierte el campo categorias (puede ser lista o string) a una lista de strings.
    Maneja el separador '|' para categorías como "2.2.2 | HAM"
    """
    if isinstance(categorias, list):
        result = []
        for c in categorias:
            if c:
                # Manejar separador |
                if "|" in str(c):
                    parts = str(c).split("|")
                    result.extend([p.strip() for p in parts if p.strip()])
                else:
                    result.append(str(c).strip())
        return result
    if isinstance(categorias, str):
        # Primero separar por | y luego por ,
        parts = categorias.replace("|", ",").split(",")
        return [c.strip() for c in parts if c.strip()]
    return []


def get_numeric_categories(cats: list) -> list:
    """
    Devuelve la lista de categorías como strings (ya viene así normalmente).
    """
    return cats


def cat_matches(cat: str, pattern: str) -> bool:
    """
    Verifica si una categoría coincide con un patrón.
    Ej: cat_matches("17.2.1", "17.2") → True
    Ej: cat_matches("17.1", "17.2") → False
    """
    cat = str(cat).strip()
    pattern = str(pattern).strip()
    return cat == pattern or cat.startswith(pattern + ".")


def cat_in_any(cat: str, patterns: list) -> bool:
    """
    Verifica si una categoría coincide con alguno de los patrones.
    """
    for pattern in patterns:
        if cat_matches(cat, pattern):
            return True
    return False

    resultado = calcular_macros_efectivos(
        p100, h100, g100, categoria, cantidad_g, categoria_secundaria, es_vegano
    )
    
    return {
        "P": resultado["proteina_cuenta"],
        "H": resultado["hidratos_cuenta"],
        "G": resultado["grasa_cuenta"]
    }
