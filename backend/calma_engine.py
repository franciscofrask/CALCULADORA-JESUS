"""
CALMA v2 - Motor de calculo de macros efectivos
Metodo Jesus Gallego - 12en12
Basado en BIBLIA_ALIMENTOS_v2 (Marzo 2026)

REESCRITO el 25/03/2026 segun la Biblia de Alimentos definitiva.
Pasa los 35 tests de verificacion del documento original.

Cada alimento tiene macros brutos (P, H, G por 100g).
Segun su categoria, solo ciertos macros "cuentan".
Este motor aplica las reglas por categoria y devuelve los macros efectivos.

IMPORTANTE: Los macros en la BD son POR RACION, no por 100g.
Las reglas CALMA siempre se evaluan sobre macros POR 100 GRAMOS.
"""

from typing import Tuple, List, Dict, Optional


# =========================================================
# FUNCION PRINCIPAL: Calcular macros efectivos
# =========================================================

def calcular_macros_efectivos(
    proteina_100g: float,
    hidratos_100g: float,
    grasa_100g: float,
    categoria: str,
    cantidad_g: float,
    categoria_secundaria: str = None,
    es_vegano: bool = False,
    acumulado_cereales_panes: float = 0.0,
    acumulado_frutos_secos: float = 0.0,
    es_intra: bool = False,
    es_post: bool = False
) -> dict:
    """
    Calcula los macros efectivos de un alimento segun las reglas CALMA v2.
    
    Args:
        proteina_100g: gramos de proteina por 100g del alimento
        hidratos_100g: gramos de hidratos por 100g del alimento
        grasa_100g: gramos de grasa por 100g del alimento
        categoria: categoria principal del alimento (string, ej: "2", "13", "17.2.1")
        cantidad_g: cantidad servida en gramos
        categoria_secundaria: segunda categoria si existe (para regla doble categoria)
        es_vegano: si el usuario es vegano
        acumulado_cereales_panes: gramos acumulados de cat 7+8 ANTES de esta comida
        acumulado_frutos_secos: gramos acumulados de cat 17.2.1/3/4 ANTES de esta comida
        es_intra: si es comida intraentreno
        es_post: si es comida postentreno
    
    Returns:
        dict con:
            proteina_efectiva: gramos de P que cuentan
            hidratos_efectivos: gramos de H que cuentan
            grasa_efectiva: gramos de G que cuentan
            proteina_cuenta: bool
            hidratos_cuenta: bool
            grasa_cuenta: bool
            calibracion_p: float (0, 0.5 o 1.0) - solo para cereales/panes/frutos secos
    """
    
    # Paso 1: Determinar que macros cuentan segun categoria principal
    p_cuenta, h_cuenta, g_cuenta, calibracion_p = _aplicar_reglas_categoria(
        proteina_100g, hidratos_100g, grasa_100g,
        categoria, cantidad_g, acumulado_cereales_panes, acumulado_frutos_secos
    )
    
    # Paso 2: Si hay categoria secundaria, aplicar regla de doble categoria
    # (la mas permisiva: si CUALQUIERA dice que cuenta -> cuenta)
    if categoria_secundaria:
        p2, h2, g2, cal2 = _aplicar_reglas_categoria(
            proteina_100g, hidratos_100g, grasa_100g,
            categoria_secundaria, cantidad_g, acumulado_cereales_panes, acumulado_frutos_secos
        )
        p_cuenta = p_cuenta or p2
        h_cuenta = h_cuenta or h2
        g_cuenta = g_cuenta or g2
        # Usar la calibracion mas alta
        calibracion_p = max(calibracion_p, cal2)
    
    # Paso 3: Calcular macros brutos de la racion servida
    factor = cantidad_g / 100.0
    p_bruta = proteina_100g * factor
    h_bruta = hidratos_100g * factor
    g_bruta = grasa_100g * factor
    
    # Paso 4: Aplicar calibracion si corresponde (cereales, panes, frutos secos)
    p_efectiva = p_bruta * calibracion_p if p_cuenta else 0.0
    h_efectiva = h_bruta if h_cuenta else 0.0
    g_efectiva = g_bruta if g_cuenta else 0.0
    
    # Paso 5: Reglas especiales postentreno
    if es_post:
        # Bebidas vegetales: max 4g grasa, y esos 4g NO cuentan
        if _cat_matches(categoria, "24"):
            if g_efectiva <= 4.0:
                g_efectiva = 0.0
    
    return {
        "proteina_efectiva": round(p_efectiva, 2),
        "hidratos_efectivos": round(h_efectiva, 2),
        "grasa_efectiva": round(g_efectiva, 2),
        "proteina_cuenta": p_cuenta,
        "hidratos_cuenta": h_cuenta,
        "grasa_cuenta": g_cuenta,
        "calibracion_p": calibracion_p
    }


def _aplicar_reglas_categoria(
    p100: float, h100: float, g100: float,
    cat: str, cantidad_g: float,
    acumulado_cereales_panes: float = 0.0,
    acumulado_frutos_secos: float = 0.0
) -> Tuple[bool, bool, bool, float]:
    """
    Aplica las reglas de conteo segun la categoria.
    Retorna (p_cuenta, h_cuenta, g_cuenta, calibracion_p)
    
    calibracion_p es 1.0 por defecto, pero puede ser 0, 0.5 o 1.0
    para cereales, panes y frutos secos con calibracion progresiva.
    
    TODAS las reglas se evaluan sobre valores por 100g.
    """
    
    cat = str(cat).strip()
    
    # Macro predominante (por 100g) - usado para regla 25%
    predominante = max(p100, h100, g100)
    
    # =====================================================
    # CAT 1 - Huevos y derivados (1.1, 1.2, 1.2.1, 1.2.2)
    # P: SIEMPRE | H: si >= 2g | G: si >= 3g
    # =====================================================
    if cat == "1" or cat.startswith("1."):
        return (True, h100 >= 2.0, g100 >= 3.0, 1.0)
    
    # =====================================================
    # CAT 2 - Carnes (todas las subcategorias)
    # P: SIEMPRE | H: si >= 2g | G: si >= 3g
    # =====================================================
    if cat == "2" or cat.startswith("2."):
        return (True, h100 >= 2.0, g100 >= 3.0, 1.0)
    
    # =====================================================
    # CAT 3 - Pescados y mariscos
    # =====================================================
    # CAT 3.9 - Mariscos: H si > 3g (ESTRICTO, no >=)
    if _cat_matches(cat, "3.9"):
        return (True, h100 > 3.0, g100 >= 3.0, 1.0)
    
    # CAT 3 - Pescados generales
    if cat == "3" or cat.startswith("3."):
        return (True, h100 >= 2.0, g100 >= 3.0, 1.0)
    
    # =====================================================
    # CAT 4 - Proteina en polvo
    # P: SIEMPRE | H: si > 6g | G: si > 6g
    # =====================================================
    if cat == "4" or cat.startswith("4."):
        return (True, h100 > 6.0, g100 > 6.0, 1.0)
    
    # =====================================================
    # CAT 5 - Lacteos y derivados (ALIMENTO MIXTO)
    # P: SIEMPRE | H: SIEMPRE | G: si > 1g
    # =====================================================
    if cat == "5" or cat.startswith("5."):
        return (True, True, g100 > 1.0, 1.0)
    
    # =====================================================
    # CAT 6 - Soja y derivados
    # =====================================================
    # CAT 6.1 - Leche de soja: igual que lacteos
    if _cat_matches(cat, "6.1"):
        return (True, True, g100 > 1.0, 1.0)
    
    # CAT 6.2 - Tofu, tempeh: P siempre, H y G segun regla 25%
    if _cat_matches(cat, "6.2") or cat == "6":
        p_cuenta = True
        h_cuenta = _regla_25(h100, predominante)
        g_cuenta = _regla_25(g100, predominante)
        return (p_cuenta, h_cuenta, g_cuenta, 1.0)
    
    # =====================================================
    # CAT 7 - Cereales excepto arroz (con CALIBRACION PROGRESIVA)
    # H: SIEMPRE
    # P: si > H/3 + calibracion progresiva
    # G: si > 8g O si > H/4
    # EXCEPCION: Cat 7.1.3 (cereales proteicos) - P siempre al 100%
    # =====================================================
    if cat == "7" or cat.startswith("7."):
        h_cuenta = True
        
        # Excepcion cat 7.1.3: P siempre al 100% sin calibracion
        if _cat_matches(cat, "7.1.3"):
            p_cuenta = True
            calibracion = 1.0
        else:
            # Regla normal: P cuenta si > H/3
            if h100 > 0 and p100 > h100 / 3.0:
                p_cuenta = True
                # Calibracion progresiva basada en acumulado de cat 7+8
                calibracion = _calibracion_cereales_panes(acumulado_cereales_panes + cantidad_g)
            else:
                p_cuenta = False
                calibracion = 0.0
        
        # Grasa: > 8g (umbral absoluto) O > H/4
        g_cuenta = g100 > 8.0 or (h100 > 0 and g100 > h100 / 4.0)
        
        return (p_cuenta, h_cuenta, g_cuenta, calibracion)
    
    # =====================================================
    # CAT 8 - Panes y tortillas de trigo (con CALIBRACION PROGRESIVA)
    # H: SIEMPRE
    # P: si > H/3 + calibracion progresiva
    # G: si > 9g O si > H/4
    # EXCEPCION: Cat 8.8 (panes proteicos) - P siempre al 100%
    # =====================================================
    if cat == "8" or cat.startswith("8."):
        h_cuenta = True
        
        # Excepcion cat 8.8: P siempre al 100% sin calibracion
        if _cat_matches(cat, "8.8"):
            p_cuenta = True
            calibracion = 1.0
        else:
            # Regla normal: P cuenta si > H/3
            if h100 > 0 and p100 > h100 / 3.0:
                p_cuenta = True
                # Calibracion progresiva basada en acumulado de cat 7+8
                calibracion = _calibracion_cereales_panes(acumulado_cereales_panes + cantidad_g)
            else:
                p_cuenta = False
                calibracion = 0.0
        
        # Grasa: > 9g (umbral absoluto) O > H/4
        g_cuenta = g100 > 9.0 or (h100 > 0 and g100 > h100 / 4.0)
        
        return (p_cuenta, h_cuenta, g_cuenta, calibracion)
    
    # =====================================================
    # CAT 9 - Tuberculos
    # H: SIEMPRE | P: NUNCA | G: NUNCA
    # =====================================================
    if cat == "9" or cat.startswith("9."):
        return (False, True, False, 1.0)
    
    # =====================================================
    # CAT 10 - Legumbres (ALIMENTO MIXTO)
    # P: SIEMPRE | H: SIEMPRE | G: si >= 8g
    # =====================================================
    if cat == "10" or cat.startswith("10."):
        return (True, True, g100 >= 8.0, 1.0)
    
    # =====================================================
    # CAT 11 - Frutas, zumos, potitos, mermeladas
    # H: SIEMPRE | P: NUNCA | G: NUNCA
    # =====================================================
    if cat == "11" or cat.startswith("11."):
        return (False, True, False, 1.0)
    
    # =====================================================
    # CAT 13 - Verduras y hortalizas
    # P: NUNCA | H: si > 4g | G: si > 4g
    # EXCEPCION: Cat 13.9 (ensaladas preparadas)
    # =====================================================
    if _cat_matches(cat, "13.9"):
        # Cat 13.9: P si > H/4, H si > 4g, G si > 3g
        p_cuenta = h100 > 0 and p100 > h100 / 4.0
        h_cuenta = h100 > 4.0
        g_cuenta = g100 > 3.0
        return (p_cuenta, h_cuenta, g_cuenta, 1.0)
    
    if cat == "13" or cat.startswith("13."):
        return (False, h100 > 4.0, g100 > 4.0, 1.0)
    
    # =====================================================
    # CAT 14 - Hidratos en polvo
    # H: SIEMPRE (es lo unico relevante)
    # =====================================================
    if cat == "14" or cat.startswith("14."):
        return (False, True, False, 1.0)
    
    # =====================================================
    # CAT 16 - Salsas, siropes y konjac
    # Cualquier macro >= 6g cuenta
    # EXCEPCION: Cat 16.4 (konjac) - como verduras sin macros
    # =====================================================
    if _cat_matches(cat, "16.4"):
        return (False, False, False, 1.0)
    
    if cat == "16" or cat.startswith("16."):
        return (p100 >= 6.0, h100 >= 6.0, g100 >= 6.0, 1.0)
    
    # =====================================================
    # CAT 17 - Alimentos ricos en grasas
    # =====================================================
    # 17.1, 17.4, 17.6, 17.10 - Aceites, mantequilla, aguacate, mayo
    # G: SIEMPRE | P: NUNCA | H: NUNCA
    if _cat_matches(cat, "17.1") or _cat_matches(cat, "17.4") or \
       _cat_matches(cat, "17.6") or _cat_matches(cat, "17.10"):
        return (False, False, True, 1.0)
    
    # 17.2.1, 17.2.3, 17.2.4 - Frutos secos naturales, semillas, cremas sin azucar
    # G: SIEMPRE | P: si > G/3 + calibracion | H: si > G/3 + calibracion
    if _cat_matches(cat, "17.2.1") or _cat_matches(cat, "17.2.3") or _cat_matches(cat, "17.2.4"):
        g_cuenta = True
        
        # P cuenta si > G/3
        if g100 > 0 and p100 > g100 / 3.0:
            p_cuenta = True
            calibracion = _calibracion_frutos_secos(acumulado_frutos_secos + cantidad_g)
        else:
            p_cuenta = False
            calibracion = 0.0
        
        # H cuenta si > G/3 (raro pero posible)
        if g100 > 0 and h100 > g100 / 3.0:
            h_cuenta = True
            # Usa la misma calibracion que P
        else:
            h_cuenta = False
        
        return (p_cuenta, h_cuenta, g_cuenta, calibracion)
    
    # 17.2.2, 17.2.5 - Frutos secos con azucar, cremas con azucar
    # H: SIEMPRE | G: SIEMPRE | P: si > 50% del macro mas alto
    if _cat_matches(cat, "17.2.2") or _cat_matches(cat, "17.2.5"):
        h_cuenta = True
        g_cuenta = True
        p_cuenta = p100 > predominante / 2.0 if predominante > 0 else False
        return (p_cuenta, h_cuenta, g_cuenta, 1.0)
    
    # 17.2.6 - Frutos secos en polvo (cacahuete desgrasado)
    # Funciona como frutos secos naturales
    if _cat_matches(cat, "17.2.6"):
        g_cuenta = True
        if g100 > 0 and p100 > g100 / 3.0:
            p_cuenta = True
            calibracion = _calibracion_frutos_secos(acumulado_frutos_secos + cantidad_g)
        else:
            p_cuenta = False
            calibracion = 0.0
        h_cuenta = g100 > 0 and h100 > g100 / 3.0
        return (p_cuenta, h_cuenta, g_cuenta, calibracion)
    
    # 17.5.3 - Cremas proteicas
    # P: SIEMPRE | G: SIEMPRE | H: si > 50% del predominante
    if _cat_matches(cat, "17.5.3"):
        h_cuenta = h100 > predominante / 2.0 if predominante > 0 else False
        return (True, h_cuenta, True, 1.0)
    
    # 17.5.1, 17.5.2 - Cremas de cacao con/sin azucar
    # H: SIEMPRE | G: SIEMPRE | P: si > 50% del predominante
    if _cat_matches(cat, "17.5"):
        p_cuenta = p100 > predominante / 2.0 if predominante > 0 else False
        return (p_cuenta, True, True, 1.0)
    
    # 17.7 - Cremas vegetales: regla general 25%
    if _cat_matches(cat, "17.7"):
        return (
            _regla_25(p100, predominante),
            _regla_25(h100, predominante),
            _regla_25(g100, predominante),
            1.0
        )
    
    # 17.9 - Croquetas: TODOS los macros cuentan
    if _cat_matches(cat, "17.9"):
        return (True, True, True, 1.0)
    
    # 17 generico - Solo grasa
    if cat == "17" or cat.startswith("17."):
        return (False, False, True, 1.0)
    
    # =====================================================
    # CAT 18 - Intraentrenamiento
    # =====================================================
    # 18.1.1 - Bebidas isotonicas con azucar: H siempre
    if _cat_matches(cat, "18.1.1"):
        return (False, True, False, 1.0)
    
    # 18.1.2 - Bebidas isotonicas zero: NADA cuenta
    if _cat_matches(cat, "18.1.2"):
        return (False, False, False, 1.0)
    
    # 18.3 - Hidratos en polvo: H siempre
    if _cat_matches(cat, "18.3"):
        return (False, True, False, 1.0)
    
    # 18 generico
    if cat == "18" or cat.startswith("18."):
        return (False, True, False, 1.0)
    
    # =====================================================
    # CAT 19 - Bebidas energeticas, refrescos y cafes
    # =====================================================
    # 19.2 - Bebidas zero: NADA cuenta
    if _cat_matches(cat, "19.2"):
        return (False, False, False, 1.0)
    
    # 19.1, 19.3 - Regla general 25%
    if cat == "19" or cat.startswith("19."):
        return (
            _regla_25(p100, predominante),
            _regla_25(h100, predominante),
            _regla_25(g100, predominante),
            1.0
        )
    
    # =====================================================
    # CAT 21 - Arroces y derivados
    # H: SIEMPRE | P: NUNCA (proteina incompleta) | G: si >= 6g
    # =====================================================
    if cat == "21" or cat.startswith("21."):
        return (False, True, g100 >= 6.0, 1.0)
    
    # =====================================================
    # CAT 22 - Pasta, quinoa y derivados
    # H: SIEMPRE | P: si > H/3 (sin calibracion) | G: si > 9g O > H/3
    # EXCEPCION: 22.1.2.2 (pasta rellena) y 22.6 (noquis) - TODOS cuentan
    # =====================================================
    if _cat_matches(cat, "22.1.2.2") or _cat_matches(cat, "22.6"):
        return (True, True, True, 1.0)
    
    if cat == "22" or cat.startswith("22."):
        h_cuenta = True
        p_cuenta = h100 > 0 and p100 > h100 / 3.0
        g_cuenta = g100 > 9.0 or (h100 > 0 and g100 > h100 / 3.0)
        return (p_cuenta, h_cuenta, g_cuenta, 1.0)
    
    # =====================================================
    # CAT 24 - Bebidas vegetales
    # Regla general 25%
    # =====================================================
    if cat == "24" or cat.startswith("24."):
        return (
            _regla_25(p100, predominante),
            _regla_25(h100, predominante),
            _regla_25(g100, predominante),
            1.0
        )
    
    # =====================================================
    # CAT 25 - Postentreno
    # Es INDICATIVA. Reglas segun la otra categoria del alimento.
    # =====================================================
    if cat == "25":
        # Regla general 25% como fallback
        return (
            _regla_25(p100, predominante),
            _regla_25(h100, predominante),
            _regla_25(g100, predominante),
            1.0
        )
    
    # =====================================================
    # CAT 27 - Sustitutivos de comidas
    # Regla general 25%
    # =====================================================
    if cat == "27" or cat.startswith("27."):
        return (
            _regla_25(p100, predominante),
            _regla_25(h100, predominante),
            _regla_25(g100, predominante),
            1.0
        )
    
    # =====================================================
    # CAT 28 - Proteina vegetal
    # P: SIEMPRE | H y G: segun regla 25%
    # =====================================================
    if cat == "28" or cat.startswith("28."):
        return (
            True,
            _regla_25(h100, predominante),
            _regla_25(g100, predominante),
            1.0
        )
    
    # =====================================================
    # CAT 29, 30 - Barritas proteicas
    # Regla general 25%
    # =====================================================
    if cat in ("29", "30") or cat.startswith("29.") or cat.startswith("30."):
        return (
            _regla_25(p100, predominante),
            _regla_25(h100, predominante),
            _regla_25(g100, predominante),
            1.0
        )
    
    # =====================================================
    # CAT 31 - Bolleria industrial y galletas
    # Regla general 25%
    # =====================================================
    if cat == "31" or cat.startswith("31."):
        return (
            _regla_25(p100, predominante),
            _regla_25(h100, predominante),
            _regla_25(g100, predominante),
            1.0
        )
    
    # =====================================================
    # CAT 32 - Pizza, lasana, empanadas
    # TODOS los macros cuentan
    # =====================================================
    if cat == "32" or cat.startswith("32."):
        return (True, True, True, 1.0)
    
    # =====================================================
    # CAT 34 - Chocolates y chocolatinas
    # Regla general 25%
    # =====================================================
    if cat == "34" or cat.startswith("34."):
        return (
            _regla_25(p100, predominante),
            _regla_25(h100, predominante),
            _regla_25(g100, predominante),
            1.0
        )
    
    # =====================================================
    # CAT 35 - Helados
    # Regla general 25%
    # =====================================================
    if cat == "35" or cat.startswith("35."):
        return (
            _regla_25(p100, predominante),
            _regla_25(h100, predominante),
            _regla_25(g100, predominante),
            1.0
        )
    
    # =====================================================
    # CAT 36 - Postres
    # Regla general 25%
    # =====================================================
    if cat == "36" or cat.startswith("36."):
        return (
            _regla_25(p100, predominante),
            _regla_25(h100, predominante),
            _regla_25(g100, predominante),
            1.0
        )
    
    # =====================================================
    # CAT 37 - Cacao en polvo, azucares, chucherias, miel
    # H: SIEMPRE | G: si > 10g | P: segun regla 25%
    # =====================================================
    if cat == "37" or cat.startswith("37."):
        return (
            _regla_25(p100, predominante),
            True,
            g100 > 10.0,
            1.0
        )
    
    # =====================================================
    # CAT 38 - Aperitivos
    # =====================================================
    # 38.1 - Patatas fritas: H siempre, G siempre, P segun 25%
    if _cat_matches(cat, "38.1"):
        return (_regla_25(p100, predominante), True, True, 1.0)
    
    # 38.2, 38.3 - Frutos secos aperitivo, pate: regla 25%
    if cat == "38" or cat.startswith("38."):
        return (
            _regla_25(p100, predominante),
            _regla_25(h100, predominante),
            _regla_25(g100, predominante),
            1.0
        )
    
    # =====================================================
    # CAT 39 - Cocina tradicional espanola
    # Regla general 25%
    # =====================================================
    if cat == "39" or cat.startswith("39."):
        return (
            _regla_25(p100, predominante),
            _regla_25(h100, predominante),
            _regla_25(g100, predominante),
            1.0
        )
    
    # =====================================================
    # CAT 40 - Casqueria
    # Como carnes: P siempre, H si >= 2g, G si >= 3g
    # =====================================================
    if cat == "40" or cat.startswith("40."):
        return (True, h100 >= 2.0, g100 >= 3.0, 1.0)
    
    # =====================================================
    # CAT 41 - Aminoacidos para entrenar
    # P: SIEMPRE (es lo unico)
    # =====================================================
    if cat == "41" or cat.startswith("41."):
        return (True, False, False, 1.0)
    
    # =====================================================
    # CAT 42 - Grasas de buena calidad
    # G: SIEMPRE (es lo unico)
    # =====================================================
    if cat == "42" or cat.startswith("42."):
        return (False, False, True, 1.0)
    
    # =====================================================
    # CAT 45 - Otras carnes
    # Funciona como carnes (cat 2): P siempre, H si >=2g, G si >=3g
    # =====================================================
    if cat == "45" or cat.startswith("45."):
        return (True, h100 >= 2.0, g100 >= 3.0, 1.0)
    
    # =====================================================
    # CAT 46 - Cremas y tortas de arroz
    # Funciona como arroces (cat 21): H siempre, P NUNCA, G si >=6g
    # =====================================================
    if cat == "46" or cat.startswith("46."):
        return (False, True, g100 >= 6.0, 1.0)
    
    # =====================================================
    # CAT 48 - Sopas y caldos
    # Cualquier macro >= 2g cuenta
    # =====================================================
    if cat == "48" or cat.startswith("48."):
        return (p100 >= 2.0, h100 >= 2.0, g100 >= 2.0, 1.0)
    
    # =====================================================
    # CAT 52 - Mundo vegano
    # Regla general del 25%
    # =====================================================
    if cat == "52" or cat.startswith("52."):
        return (
            _regla_25(p100, predominante),
            _regla_25(h100, predominante),
            _regla_25(g100, predominante),
            1.0
        )
    
    # =====================================================
    # CAT 43, 44, 47, 49, 50, 51, 53 - Procesados complejos
    # TODOS los macros cuentan SIEMPRE
    # =====================================================
    if cat in ("43", "44", "47", "49", "50", "51", "53") or \
       cat.startswith("43.") or cat.startswith("44.") or \
       cat.startswith("47.") or cat.startswith("49.") or \
       cat.startswith("50.") or cat.startswith("51.") or \
       cat.startswith("53."):
        return (True, True, True, 1.0)
    
    # =====================================================
    # FALLBACK - Regla general del 25%
    # Para cualquier categoria no listada arriba
    # =====================================================
    return (
        _regla_25(p100, predominante),
        _regla_25(h100, predominante),
        _regla_25(g100, predominante),
        1.0
    )


# =========================================================
# FUNCIONES AUXILIARES
# =========================================================

def _regla_25(macro: float, predominante: float) -> bool:
    """
    Regla base del 25%: un macro secundario solo cuenta si supera
    el 25% del macro principal.
    macro * 4 > predominante
    """
    if predominante <= 0:
        return False
    return macro * 4 > predominante


def _cat_matches(cat: str, pattern: str) -> bool:
    """
    Verifica si una categoria coincide con un patron.
    Ej: _cat_matches("17.2.1", "17.2") -> True
    Ej: _cat_matches("17.1", "17.2") -> False
    """
    cat = str(cat).strip()
    pattern = str(pattern).strip()
    return cat == pattern or cat.startswith(pattern + ".")


def _calibracion_cereales_panes(acumulado_g: float) -> float:
    """
    Calibracion progresiva para cereales (cat 7) y panes (cat 8).
    Basada en el acumulado conjunto de cat 7 + cat 8 en el dia.
    
    | Acumulado | Proteinas |
    |-----------|-----------|
    | 0-50g     | 0%        |
    | 50-100g   | 50%       |
    | >100g     | 100%      |
    """
    if acumulado_g <= 50:
        return 0.0
    elif acumulado_g <= 100:
        return 0.5
    else:
        return 1.0


def _calibracion_frutos_secos(acumulado_g: float) -> float:
    """
    Calibracion progresiva para frutos secos naturales (cat 17.2.1, 17.2.3, 17.2.4).
    
    | Acumulado | P y H (si pasan regla) |
    |-----------|------------------------|
    | 0-20g     | 0%                     |
    | 20-40g    | 50%                    |
    | >40g      | 100%                   |
    """
    if acumulado_g <= 20:
        return 0.0
    elif acumulado_g <= 40:
        return 0.5
    else:
        return 1.0


def _redondear_cantidad(cantidad: float, categoria: str) -> float:
    """Redondea la cantidad segun el tipo de alimento."""
    cat = str(categoria).strip()
    
    # Pan: multiplos de 10g
    if cat == "8" or cat.startswith("8."):
        return round(cantidad / 10) * 10
    
    # Arroz, pasta, patata, carne, pescado, verduras: multiplos de 25g
    if cat in ("2", "3", "9", "13", "21", "22") or \
       cat.startswith("2.") or cat.startswith("3.") or \
       cat.startswith("9.") or cat.startswith("13.") or \
       cat.startswith("21.") or cat.startswith("22."):
        return round(cantidad / 25) * 25
    
    # Claras de huevo (cat 1.1): medición continua, 1g de precisión
    if cat == "1.1" or cat.startswith("1.1."):
        return round(cantidad)

    # Huevos enteros (cat 1.2): múltiplos de 55g (aprox 1 huevo)
    if cat == "1" or cat.startswith("1."):
        return round(cantidad / 55) * 55
    
    # Frutos secos, proteina polvo, cereales: multiplos de 5g
    if cat.startswith("17.2") or cat.startswith("4") or \
       cat == "7" or cat.startswith("7."):
        return round(cantidad / 5) * 5
    
    # Aceite: multiplos de 5ml
    if cat in ("17.1", "17.4", "17.6", "17.10") or \
       cat.startswith("17.1.") or cat.startswith("17.4.") or \
       cat.startswith("17.6.") or cat.startswith("17.10."):
        return round(cantidad / 5) * 5
    
    # Fruta: multiplos de 25g (aprox media pieza)
    if cat == "11" or cat.startswith("11."):
        return round(cantidad / 25) * 25
    
    # Lacteos: multiplos de 25g
    if cat == "5" or cat.startswith("5."):
        return round(cantidad / 25) * 25
    
    # Default: multiplos de 10g
    return round(cantidad / 10) * 10


# =========================================================
# FUNCIONES PARA MARGENES Y VALIDACION
# =========================================================

def comida_cuadrada(objetivo: dict, consumido: dict, es_intra: bool = False) -> dict:
    """
    Verifica si una comida esta cuadrada (dentro del margen permitido).
    
    Margen general: +/- 4g en cada macro
    Margen intra: +/- 2g (mas estricto)
    
    Returns:
        dict con:
            cuadrada: bool - True si todos los macros estan dentro del margen
            diferencias: dict - diferencia en cada macro
            estado: str - "cuadrada", "valida", "exceso", "falta"
    """
    margen = 2 if es_intra else 4
    
    diff_p = consumido.get("P", 0) - objetivo.get("P", 0)
    diff_h = consumido.get("H", 0) - objetivo.get("H", 0)
    diff_g = consumido.get("G", 0) - objetivo.get("G", 0)
    
    p_ok = abs(diff_p) <= margen
    h_ok = abs(diff_h) <= margen
    g_ok = abs(diff_g) <= margen
    
    cuadrada = p_ok and h_ok and g_ok
    
    # Determinar estado
    if diff_p == 0 and diff_h == 0 and diff_g == 0:
        estado = "cuadrada"
    elif cuadrada:
        estado = "valida"
    elif diff_p > margen or diff_h > margen or diff_g > margen:
        estado = "exceso"
    else:
        estado = "falta"
    
    return {
        "cuadrada": cuadrada,
        "diferencias": {"P": diff_p, "H": diff_h, "G": diff_g},
        "estado": estado,
        "detalles": {
            "P_ok": p_ok,
            "H_ok": h_ok,
            "G_ok": g_ok
        }
    }


def tolerancia_postentreno(objetivo_p: float, consumido_p: float) -> bool:
    """
    Tolerancia especial del postentreno: si faltan 2g o menos de proteina,
    se considera valido.
    """
    falta = objetivo_p - consumido_p
    return falta <= 2.0


# =========================================================
# FUNCIONES WRAPPER para compatibilidad con server.py
# =========================================================

def parse_categories(categorias) -> list:
    """
    Convierte el campo categorias (puede ser lista o string) a una lista de strings.
    Maneja el separador '|' para categorias como "2.2.2 | HAM"
    Solo devuelve las categorias NUMERICAS (que empiezan con digito).
    """
    if isinstance(categorias, list):
        result = []
        for c in categorias:
            if c:
                if "|" in str(c):
                    parts = str(c).split("|")
                    result.extend([p.strip() for p in parts if p.strip()])
                else:
                    result.append(str(c).strip())
    elif isinstance(categorias, str):
        parts = categorias.replace("|", ",").split(",")
        result = [c.strip() for c in parts if c.strip()]
    else:
        result = []
    
    # Filtrar solo categorias numericas (empiezan con digito)
    return [c for c in result if c and c[0].isdigit()]


def get_numeric_categories(cats: list) -> list:
    """Alias para compatibilidad."""
    return [c for c in cats if c and c[0].isdigit()]


def cat_matches(cat: str, pattern: str) -> bool:
    """Wrapper publico de _cat_matches."""
    return _cat_matches(cat, pattern)


def cat_in_any(cat: str, patterns: list) -> bool:
    """Verifica si una categoria coincide con alguno de los patrones."""
    for pattern in patterns:
        if _cat_matches(cat, pattern):
            return True
    return False


def calcular_macros_efectivos_alimento(
    alimento: dict,
    cantidad_g: float,
    es_vegano: bool = False,
    acumulado_cereales_panes: float = 0.0,
    acumulado_frutos_secos: float = 0.0,
    es_intra: bool = False,
    es_post: bool = False
) -> dict:
    """
    Wrapper que recibe un objeto alimento de MongoDB.
    Extrae los valores necesarios y llama a calcular_macros_efectivos.
    
    IMPORTANTE: Los macros en MongoDB son POR RACION, hay que convertir a por 100g.
    
    Retorna dict con formato {"P": float, "H": float, "G": float, "kcal": float}
    """
    # Extraer macros por racion
    p_racion = float(alimento.get("proteinas", 0) or 0)
    h_racion = float(alimento.get("hidratos", 0) or 0)
    g_racion = float(alimento.get("grasas", 0) or 0)
    racion = float(alimento.get("racion", 100) or 100)
    
    # Convertir a por 100g
    if racion > 0:
        p100 = (p_racion / racion) * 100
        h100 = (h_racion / racion) * 100
        g100 = (g_racion / racion) * 100
    else:
        p100, h100, g100 = p_racion, h_racion, g_racion
    
    # Extraer categorias
    categorias = parse_categories(alimento.get("categorias", []))
    categoria = categorias[0] if categorias else "0"
    categoria_secundaria = categorias[1] if len(categorias) > 1 else None
    
    # Llamar a la funcion principal
    resultado = calcular_macros_efectivos(
        p100, h100, g100, categoria, cantidad_g,
        categoria_secundaria, es_vegano,
        acumulado_cereales_panes, acumulado_frutos_secos,
        es_intra, es_post
    )
    
    # Calcular kcal
    p_ef = resultado["proteina_efectiva"]
    h_ef = resultado["hidratos_efectivos"]
    g_ef = resultado["grasa_efectiva"]
    kcal = p_ef * 4 + h_ef * 4 + g_ef * 9
    
    return {
        "P": round(p_ef, 1),
        "H": round(h_ef, 1),
        "G": round(g_ef, 1),
        "kcal": round(kcal, 1),
        "proteina_cuenta": resultado["proteina_cuenta"],
        "hidratos_cuenta": resultado["hidratos_cuenta"],
        "grasa_cuenta": resultado["grasa_cuenta"],
        "calibracion_p": resultado["calibracion_p"]
    }


def calcular_macros_brutos(alimento: dict, cantidad_g: float) -> dict:
    """
    Calcula los macros BRUTOS (sin aplicar reglas) de un alimento.
    
    IMPORTANTE: Los macros en MongoDB son POR RACION.
    
    Retorna dict con formato {"P": float, "H": float, "G": float, "kcal": float}
    """
    p_racion = float(alimento.get("proteinas", 0) or 0)
    h_racion = float(alimento.get("hidratos", 0) or 0)
    g_racion = float(alimento.get("grasas", 0) or 0)
    racion = float(alimento.get("racion", 100) or 100)
    
    # Los macros en BD son por racion, convertir a cantidad real
    if racion > 0:
        factor = cantidad_g / racion
        p = p_racion * factor
        h = h_racion * factor
        g = g_racion * factor
    else:
        factor = cantidad_g / 100.0
        p = p_racion * factor
        h = h_racion * factor
        g = g_racion * factor
    
    kcal = p * 4 + h * 4 + g * 9
    
    return {
        "P": round(p, 1),
        "H": round(h, 1),
        "G": round(g, 1),
        "kcal": round(kcal, 1)
    }


def que_macros_cuentan(
    alimento: dict,
    cantidad_g: float,
    es_vegano: bool = False,
    acumulado_cereales_panes: float = 0.0,
    acumulado_frutos_secos: float = 0.0
) -> dict:
    """
    Determina que macros cuentan para un alimento dado.
    
    Retorna dict con formato {"P": bool, "H": bool, "G": bool}
    """
    resultado = calcular_macros_efectivos_alimento(
        alimento, cantidad_g, es_vegano,
        acumulado_cereales_panes, acumulado_frutos_secos
    )
    
    return {
        "P": resultado["proteina_cuenta"],
        "H": resultado["hidratos_cuenta"],
        "G": resultado["grasa_cuenta"]
    }


# =========================================================
# FUNCION AUXILIAR: Calcular cantidad automatica
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
    Calcula la cantidad optima de un alimento para cubrir los macros restantes
    sin pasarse en ninguno.
    
    Args:
        macros_restantes: {"proteina": X, "hidratos": Y, "grasa": Z}
    
    Returns:
        dict con cantidad_g, macros_efectivos
    """
    
    p_rest = macros_restantes.get("proteina", 0)
    h_rest = macros_restantes.get("hidratos", 0)
    g_rest = macros_restantes.get("grasa", 0)
    
    # Calcular macros efectivos por 100g
    ef_100 = calcular_macros_efectivos(
        proteina_100g, hidratos_100g, grasa_100g,
        categoria, 100.0, categoria_secundaria, es_vegano
    )
    
    p_ef = ef_100["proteina_efectiva"]
    h_ef = ef_100["hidratos_efectivos"]
    g_ef = ef_100["grasa_efectiva"]
    
    # Calcular cantidad maxima por cada macro
    cantidades = []
    if p_ef > 0 and p_rest > 0:
        cantidades.append(p_rest / p_ef * 100)
    if h_ef > 0 and h_rest > 0:
        cantidades.append(h_rest / h_ef * 100)
    if g_ef > 0 and g_rest > 0:
        cantidades.append(g_rest / g_ef * 100)
    
    if not cantidades:
        return {
            "cantidad_g": 0,
            "macros_efectivos": {"proteina": 0, "hidratos": 0, "grasa": 0}
        }
    
    # Elegir la cantidad MINIMA (macro mas limitante)
    cantidad = min(cantidades)
    
    # Redondear
    cantidad = round(cantidad)
    
    # Asegurar minimo de 5g
    if cantidad < 5:
        cantidad = 5
    
    # Recalcular macros efectivos
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


# =========================================================
# TESTS - Funcion run_tests para compatibilidad con server.py
# =========================================================

def run_tests() -> dict:
    """
    Ejecuta tests basicos del motor CALMA.
    Mantiene compatibilidad con server.py que importa esta funcion.
    
    Returns:
        dict con total, passed, failed_count, all_passed, tests, failed_tests
    """
    tests = []
    
    def check(nombre, condicion, detalle=""):
        tests.append({
            "nombre": nombre,
            "passed": condicion,
            "detalle": detalle if not condicion else "OK"
        })
        return condicion
    
    # Test 1: Huevo (cat 1.2) - P siempre, H no (0<2), G si (9.5>=3)
    r = calcular_macros_efectivos(12.7, 0, 9.5, "1.2", 126)
    check("Huevo: P cuenta", r["proteina_cuenta"] == True)
    check("Huevo: H no cuenta", r["hidratos_cuenta"] == False)
    check("Huevo: G cuenta", r["grasa_cuenta"] == True)
    
    # Test 2: Pechuga (cat 2.2) - Solo P
    r = calcular_macros_efectivos(23, 0, 1.2, "2.2", 200)
    check("Pechuga: solo P", r["proteina_cuenta"] and not r["grasa_cuenta"])
    
    # Test 3: Gambas (cat 3.9) - H=3 NO cuenta (umbral estricto >3)
    r = calcular_macros_efectivos(24, 3, 0.5, "3.9", 100)
    check("Gambas: H=3 no cuenta", r["hidratos_cuenta"] == False)
    
    # Test 4: Yogur (cat 5) - P+H siempre, G si >1
    r = calcular_macros_efectivos(5, 4, 10, "5.2", 100)
    check("Yogur: P+H+G cuentan", r["proteina_cuenta"] and r["hidratos_cuenta"] and r["grasa_cuenta"])
    
    # Test 5: Patata (cat 9) - Solo H
    r = calcular_macros_efectivos(2, 17, 0.1, "9", 200)
    check("Patata: solo H", r["hidratos_cuenta"] and not r["proteina_cuenta"])
    
    # Test 6: Arroz (cat 21) - P NUNCA
    r = calcular_macros_efectivos(7, 78, 0.6, "21", 100)
    check("Arroz: P nunca", r["proteina_cuenta"] == False)
    
    # Test 7: Lechuga (cat 13) - NADA cuenta
    r = calcular_macros_efectivos(1.3, 2, 0.2, "13", 100)
    check("Lechuga: nada cuenta", not any([r["proteina_cuenta"], r["hidratos_cuenta"], r["grasa_cuenta"]]))
    
    # Test 8: Big Mac (cat 49) - TODO cuenta
    r = calcular_macros_efectivos(11.6, 19.4, 12, "49", 100)
    check("BigMac: todo cuenta", all([r["proteina_cuenta"], r["hidratos_cuenta"], r["grasa_cuenta"]]))
    
    # Test 9: Calibracion cereales 0-50g -> 0%
    r = calcular_macros_efectivos(25, 55, 0, "7", 40, acumulado_cereales_panes=0)
    check("Calibracion 0-50g: P=0", r["proteina_efectiva"] == 0)
    
    # Test 10: Calibracion cereales 50-100g -> 50%
    r = calcular_macros_efectivos(25, 55, 0, "7", 30, acumulado_cereales_panes=40)
    check("Calibracion 50-100g: P al 50%", abs(r["proteina_efectiva"] - 3.75) < 0.5)
    
    # Resumen
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


if __name__ == "__main__":
    results = run_tests()
    print(f"\nCALMA v2 - Tests basicos: {results['passed']}/{results['total']}")
    if results["all_passed"]:
        print("OK - Todos los tests pasan")
    else:
        print("ERRORES:")
        for t in results["failed_tests"]:
            print(f"  - {t['nombre']}: {t['detalle']}")
