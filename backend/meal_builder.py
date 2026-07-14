"""
MEAL BUILDER - Algoritmo de construcción de comidas CALMA v2
============================================================
Distribuye macros inteligentemente entre los alimentos solicitados.

REGLAS FUNDAMENTALES:
1. MÍNIMOS: Nunca poner un alimento por debajo de su mínimo
2. MÁXIMOS: No poner cantidades absurdas
3. DISTRIBUCIÓN: Repartir macros entre todos los alimentos
4. CALMA: Usar macros EFECTIVOS según categoría

Autor: JG12 Team
Fecha: 31/03/2026
"""

from typing import Dict, List, Tuple, Optional
from calma_engine import calcular_macros_efectivos, parse_categories
from calculator import get_food_config

# =========================================================
# CONSTANTES
# =========================================================

MARGEN_CALMA = 4.0  # ±4g de margen permitido

MACRO_NOMBRE = {"P": "proteína", "H": "hidratos", "G": "grasa"}


def razon_minimo_no_cabe(minimo_g: float, aporte: float, macro: str, restante: float) -> str:
    """Mensaje en lenguaje humano para 'el mínimo de este alimento ya se pasa
    de lo que queda de ese macro en la comida'."""
    nombre = MACRO_NOMBRE.get(macro, macro)
    queda = f"solo quedan {max(0.0, restante):.0f} g" if restante > 0.5 else "ya no queda nada"
    return (f"No cabe: su mínimo ({int(round(minimo_g))} g) aporta {aporte:.0f} g de {nombre} "
            f"y en esta comida {queda} de {nombre}")

# Mínimos por tipo de alimento (en gramos)
MINIMOS = {
    "carnes_pescados": 50,
    "embutidos": 25,
    "huevos": 1,  # 1 unidad (nunca medio)
    "proteina_polvo": 5,
    "leche": 20,
    "quesos": 20,
    "cereales": 10,
    "panes": 25,
    "arroz": 25,
    "verduras_sin_macros": 100,
    "aceites_grasas": 5,
    "frutos_secos": 5,
    "fruta_fresca": 0.5,  # media unidad
    "tuberculos": 25,
    "quinoa_pasta": 25,
}

# Máximos razonables (en gramos)
MAXIMOS = {
    "claras": 200,
    "huevos": 3,  # 3 unidades
    "carnes_pescados": 250,
    "queso_batido": 300,
    "frutos_secos": 25,
    "aceite": 10,  # 1 cucharada sopera
}


def get_food_limits(alimento: dict, config: dict) -> Tuple[float, float]:
    """
    Obtiene los límites mínimo y máximo para un alimento.
    
    Returns:
        (minimo_g, maximo_g)
    """
    nombre = alimento.get("nombre", "").lower()
    cats_str = str(alimento.get("categorias", ""))
    racion = float(alimento.get("racion", 100) or 100)
    es_unidad = alimento.get("unidades", False) or config.get("por_unidad", False)
    
    # Parsear categorías como lista
    cats = [c.strip() for c in cats_str.split('|')]
    
    def has_cat(prefix):
        """Verifica si tiene una categoría que empieza con prefix."""
        return any(c.startswith(prefix) for c in cats)
    
    # Determinar mínimo según categoría/tipo
    minimo = config.get("minimo", 5)
    maximo = 500  # Default alto
    
    # ============ FRUTOS SECOS Y ACEITES (PRIORIDAD ALTA) ============
    # Cat 17.2 - Frutos secos (ANTES de otras reglas que puedan matchear mal)
    if has_cat("17.2"):
        minimo = MINIMOS["frutos_secos"]  # 5g
        maximo = MAXIMOS["frutos_secos"]  # 25g
        return (minimo, maximo)
    
    # Cat 17.1 - Aceites
    if has_cat("17.1"):
        minimo = MINIMOS["aceites_grasas"]  # 5g
        maximo = MAXIMOS["aceite"]  # 10g
        return (minimo, maximo)
    
    # ============ PROTEÍNAS ============
    # Cat 1.1 - Claras
    if has_cat("1.1") and "clara" in nombre:
        minimo = 30
        maximo = MAXIMOS["claras"]
    
    # Cat 1.2 - Huevos enteros
    elif has_cat("1.2") and "huevo" in nombre:
        peso_unidad = int(racion) if racion > 0 else 55
        minimo = peso_unidad  # 1 huevo mínimo
        maximo = peso_unidad * MAXIMOS["huevos"]  # 3 huevos máximo
    
    # Cat 2 - Carnes
    elif has_cat("2."):
        minimo = MINIMOS["carnes_pescados"]
        maximo = MAXIMOS["carnes_pescados"]
        # Embutidos tienen mínimo menor
        if any(x in nombre for x in ["jamón", "pavo", "lomo", "fiambre", "embutido"]):
            minimo = MINIMOS["embutidos"]
    
    # Cat 3 - Pescados
    elif has_cat("3."):
        minimo = MINIMOS["carnes_pescados"]
        maximo = MAXIMOS["carnes_pescados"]
    
    # Cat 4 - Proteína en polvo
    elif has_cat("4."):
        minimo = MINIMOS["proteina_polvo"]
        maximo = 60
    
    # ============ LÁCTEOS ============
    # Cat 5 - Lácteos
    elif has_cat("5."):
        if "batido" in nombre or "queso fresco batido" in nombre:
            minimo = MINIMOS["quesos"]
            maximo = MAXIMOS["queso_batido"]
        elif "leche" in nombre:
            minimo = MINIMOS["leche"]
            maximo = 300
        else:
            minimo = MINIMOS["quesos"]
            maximo = 150
    
    # ============ HIDRATOS ============
    # Cat 7 - Cereales
    elif has_cat("7."):
        minimo = MINIMOS["cereales"]
        maximo = 100
    
    # Cat 8 - Panes
    elif has_cat("8."):
        if racion < 100 and es_unidad:
            peso_unidad = int(racion) if racion > 0 else 60
            minimo = peso_unidad
            maximo = peso_unidad * 3
        else:
            minimo = MINIMOS["panes"]
            maximo = 100
    
    # Cat 9 - Tubérculos
    elif has_cat("9."):
        minimo = MINIMOS["tuberculos"]
        maximo = 300
    
    # Cat 11 - Frutas
    elif has_cat("11."):
        if es_unidad:
            peso_unidad = int(racion) if racion > 0 else 100
            minimo = peso_unidad // 2  # Media unidad
            maximo = peso_unidad * 2  # 2 unidades
        else:
            minimo = 50
            maximo = 200
    
    # Cat 13 - Verduras
    elif has_cat("13."):
        minimo = 50  # Reducido de 100 para verduras pequeñas
        maximo = 300
    
    # Cat 21 - Arroz
    elif has_cat("21."):
        minimo = MINIMOS["arroz"]
        maximo = 150
    
    # Cat 22 - Pasta y quinoa
    elif has_cat("22."):
        minimo = MINIMOS["quinoa_pasta"]
        maximo = 150
    
    # Si es por unidad, ajustar al peso de la unidad
    if es_unidad and racion > 0 and racion < 200:
        peso_unidad = int(racion)
        if minimo < peso_unidad:
            minimo = peso_unidad
    
    return (minimo, maximo)


def get_effective_macros_per_100g(alimento: dict) -> Dict[str, float]:
    """
    Calcula los macros EFECTIVOS por 100g de un alimento según CALMA.
    """
    cats = parse_categories(alimento.get("categorias", []))
    cat = cats[0] if cats else "0"
    
    racion = float(alimento.get("racion", 100) or 100)
    P_100 = float(alimento.get("proteinas", 0) or 0) * 100.0 / racion
    H_100 = float(alimento.get("hidratos", 0) or 0) * 100.0 / racion
    G_100 = float(alimento.get("grasas", 0) or 0) * 100.0 / racion
    
    ef = calcular_macros_efectivos(P_100, H_100, G_100, cat, 100.0)
    
    return {
        "P": ef["proteina_efectiva"],
        "H": ef["hidratos_efectivos"],
        "G": ef["grasa_efectiva"],
        "cat": cat,
        "p_cuenta": ef["proteina_cuenta"],
        "h_cuenta": ef["hidratos_cuenta"],
        "g_cuenta": ef["grasa_cuenta"],
    }


def classify_food_role(alimento: dict, macros_ef: dict) -> str:
    """
    Clasifica el rol del alimento en la comida.
    
    Returns:
        "P" - Fuente principal de proteína
        "H" - Fuente principal de hidratos
        "G" - Fuente principal de grasa
        "PH" - Mixto proteína+hidratos (lácteos, legumbres)
        "PG" - Mixto proteína+grasa (huevos)
        "V" - Verdura sin macros efectivos
    """
    p = macros_ef["P"]
    h = macros_ef["H"]
    g = macros_ef["G"]
    cat = macros_ef["cat"]
    
    # Verduras sin macros
    if p == 0 and h == 0 and g == 0:
        return "V"
    
    # Lácteos y legumbres son mixtos P+H
    if cat.startswith("5") or cat.startswith("10"):
        if macros_ef["p_cuenta"] and macros_ef["h_cuenta"]:
            return "PH"
    
    # Huevos son mixtos P+G
    if cat.startswith("1.2"):
        return "PG"
    
    # Determinar macro principal
    max_macro = max(p, h, g)
    if max_macro == 0:
        return "V"
    
    if p == max_macro:
        return "P"
    elif h == max_macro:
        return "H"
    else:
        return "G"


def calculate_food_amount(
    alimento: dict,
    config: dict,
    macros_ef: dict,
    target_macro: str,
    target_amount: float,
    minimo: float,
    maximo: float
) -> Tuple[float, Dict[str, float]]:
    """
    Calcula la cantidad de un alimento para alcanzar un objetivo de macro.
    
    Args:
        alimento: Datos del alimento
        config: Configuración (minimo, por_unidad, etc)
        macros_ef: Macros efectivos por 100g
        target_macro: "P", "H" o "G"
        target_amount: Gramos de macro objetivo
        minimo: Cantidad mínima permitida
        maximo: Cantidad máxima permitida
    
    Returns:
        (cantidad_g, macros_resultantes)
    """
    # Obtener macro efectivo por 100g
    macro_per_100 = macros_ef.get(target_macro, 0)
    
    if macro_per_100 <= 0:
        # Este alimento no aporta el macro objetivo
        return (0, {"P": 0, "H": 0, "G": 0})
    
    # Calcular cantidad para el objetivo
    cantidad_ideal = (target_amount / macro_per_100) * 100
    
    # Aplicar límites
    cantidad_g = max(minimo, min(maximo, cantidad_ideal))
    
    # Si es por unidad, redondear a unidades completas
    if config.get("por_unidad", False):
        peso_unidad = config.get("peso_unidad", 0) or float(alimento.get("racion", 100))
        if peso_unidad > 0:
            unidades = round(cantidad_g / peso_unidad)
            unidades = max(1, unidades)  # Al menos 1 unidad
            cantidad_g = unidades * peso_unidad
    
    # Calcular macros resultantes
    factor = cantidad_g / 100.0
    macros_result = {
        "P": round(macros_ef["P"] * factor, 1),
        "H": round(macros_ef["H"] * factor, 1),
        "G": round(macros_ef["G"] * factor, 1),
    }
    
    return (cantidad_g, macros_result)


def format_cantidad_display(cantidad_g: float, alimento: dict, config: dict) -> str:
    """Formatea la cantidad para mostrar al usuario."""
    if config.get("por_unidad", False):
        peso_unidad = config.get("peso_unidad", 0) or float(alimento.get("racion", 100))
        if peso_unidad > 0:
            unidades = round(cantidad_g / peso_unidad)
            if unidades == 1:
                return "1 ud"
            else:
                return f"{unidades} ud"
    
    return f"{int(cantidad_g)}g"


async def build_meal(
    db,
    foods_requested: List[str],
    objetivo: Dict[str, float],
    search_func
) -> Dict:
    """
    Construye una comida distribuyendo macros entre los alimentos.
    
    Args:
        db: Conexión a MongoDB
        foods_requested: Lista de nombres de alimentos
        objetivo: {"P": 32.5, "H": 32.5, "G": 15}
        search_func: Función async para buscar alimentos
    
    Returns:
        {
            "foods_added": [...],
            "foods_not_found": [...],
            "totals": {"P": x, "H": y, "G": z},
            "remaining": {"P": x, "H": y, "G": z},
            "cuadrado": bool,
            "sugerencia": str or None
        }
    """
    p_obj = float(objetivo.get("P", 0))
    h_obj = float(objetivo.get("H", 0))
    g_obj = float(objetivo.get("G", 0))
    
    # Paso 1: Buscar y clasificar todos los alimentos
    alimentos_info = []
    not_found = []
    
    for food_name in foods_requested:
        matches = await search_func(food_name, limit=5)
        
        if matches:
            alimento = matches[0]
            config = get_food_config(alimento)
            macros_ef = get_effective_macros_per_100g(alimento)
            role = classify_food_role(alimento, macros_ef)
            minimo, maximo = get_food_limits(alimento, config)
            
            alimentos_info.append({
                "alimento": alimento,
                "config": config,
                "macros_ef": macros_ef,
                "role": role,
                "minimo": minimo,
                "maximo": maximo,
                "buscado": food_name,
                "alternativas": [m.get("nombre") for m in matches[1:4]],
            })
        else:
            not_found.append({
                "buscado": food_name,
                "encontrado": None,
                "razon": "No encontrado en la base de datos"
            })
    
    # Paso 2: Separar por rol
    verduras = [a for a in alimentos_info if a["role"] == "V"]
    fuentes_P = [a for a in alimentos_info if a["role"] in ("P", "PG")]
    fuentes_H = [a for a in alimentos_info if a["role"] in ("H", "PH")]
    fuentes_G = [a for a in alimentos_info if a["role"] == "G"]
    fuentes_PH = [a for a in alimentos_info if a["role"] == "PH"]
    fuentes_PG = [a for a in alimentos_info if a["role"] == "PG"]
    
    # También incluir PH en fuentes de P (cuentan para ambos)
    for f in fuentes_PH:
        if f not in fuentes_P:
            fuentes_P.append(f)
    
    found_foods = []
    totals = {"P": 0, "H": 0, "G": 0}
    
    # Paso 3: Añadir verduras primero (cantidad fija)
    for info in verduras:
        alimento = info["alimento"]
        config = info["config"]
        cantidad_g = info["minimo"]  # Verduras usan mínimo (100g típico)
        
        # Formato display
        display = format_cantidad_display(cantidad_g, alimento, config)
        
        found_foods.append({
            "nombre": alimento.get("nombre"),
            "cantidad": cantidad_g,
            "cantidad_display": display,
            "macros": {"P": 0, "H": 0, "G": 0},
            "alternativas": info["alternativas"]
        })
    
    # Paso 4: Estrategia inteligente de distribución
    # 
    # ORDEN DE PROCESAMIENTO:
    # 1. Alimentos PG (huevos) - Calcular cuántos poner sin pasarse de G
    # 2. Alimentos de H - Cubrir los hidratos
    # 3. Alimentos de P pura - Cubrir la P restante (después de PG y PH)
    # 4. Alimentos de G pura - SOLO si queda G por cubrir
    
    g_remaining = g_obj  # Grasa disponible
    p_remaining = p_obj  # Proteína a cubrir
    h_remaining = h_obj  # Hidratos a cubrir
    
    # ========== PASO 4a: Procesar PG (huevos) ==========
    # Los huevos aportan P y G. Poner solo los necesarios sin pasarse de G.
    for info in fuentes_PG:
        alimento = info["alimento"]
        config = info["config"]
        macros_ef = info["macros_ef"]
        minimo = info["minimo"]
        maximo = info["maximo"]
        
        peso_unidad = config.get("peso_unidad", 0) or float(alimento.get("racion", 55))
        p_per_unit = macros_ef["P"] * peso_unidad / 100
        g_per_unit = macros_ef["G"] * peso_unidad / 100
        
        if p_per_unit <= 0 or g_per_unit <= 0:
            continue
        
        # Verificar que al menos el mínimo cabe en G
        min_g = macros_ef["G"] * minimo / 100
        if min_g > g_remaining + MARGEN_CALMA:
            not_found.append({
                "buscado": info["buscado"],
                "encontrado": alimento.get("nombre"),
                "razon": razon_minimo_no_cabe(minimo, min_g, "G", g_remaining),
                "alternativas": info["alternativas"]
            })
            continue
        
        # Calcular cuántas unidades poner:
        # - Máximo por G disponible
        # - Máximo por P objetivo (si no hay otras fuentes de P)
        # - Máximo permitido
        
        max_by_g = int(g_remaining / g_per_unit) if g_per_unit > 0 else 3
        max_by_p = int(p_remaining / p_per_unit) if p_per_unit > 0 else 3
        max_by_limit = int(maximo / peso_unidad)
        
        # Si hay claras u otras fuentes de P pura, no necesitamos tantos huevos
        # Solo poner 1-2 huevos y dejar que las claras cubran el resto de P
        fuentes_P_puras = [f for f in fuentes_P if f["role"] == "P"]
        if fuentes_P_puras:
            # Hay claras u otra fuente de P pura, limitar huevos a 1-2
            unidades = min(2, max_by_g, max_by_limit)
        else:
            # No hay otras fuentes de P, usar huevos para toda la P
            unidades = min(max_by_p, max_by_g, max_by_limit)
        
        unidades = max(1, unidades)  # Al menos 1
        cantidad_g = unidades * peso_unidad
        
        factor = cantidad_g / 100.0
        macros = {
            "P": round(macros_ef["P"] * factor, 1),
            "H": round(macros_ef["H"] * factor, 1),
            "G": round(macros_ef["G"] * factor, 1),
        }
        
        display = format_cantidad_display(cantidad_g, alimento, config)
        
        found_foods.append({
            "nombre": alimento.get("nombre"),
            "cantidad": cantidad_g,
            "cantidad_display": display,
            "macros": macros,
            "alternativas": info["alternativas"]
        })
        
        totals["P"] += macros["P"]
        totals["H"] += macros["H"]
        totals["G"] += macros["G"]
        p_remaining -= macros["P"]
        g_remaining -= macros["G"]
    
    # Paso 5: Procesar fuentes de H
    # ESTRATEGIA: Primero los alimentos con cantidad fija (por unidad), luego ajustar el resto
    h_remaining = h_obj - totals["H"]
    
    fuentes_H_puras = [f for f in fuentes_H if f["role"] == "H"]
    fuentes_H_mixtas = [f for f in fuentes_H if f["role"] == "PH"]
    
    # Separar alimentos por unidad vs por peso
    # Incluir frutas (cat 11) como "cantidad fija" porque tienen mínimo específico
    def is_fixed_quantity(info):
        config = info["config"]
        alimento = info["alimento"]
        cats = str(alimento.get("categorias", ""))
        # Por unidad O fruta (cat 11)
        return (
            config.get("por_unidad", False) or 
            alimento.get("unidades", False) or
            any(c.startswith("11") for c in cats.split("|"))
        )
    
    fuentes_H_fija = [f for f in fuentes_H_puras if is_fixed_quantity(f)]
    fuentes_H_peso = [f for f in fuentes_H_puras if f not in fuentes_H_fija]
    
    # ========== 5a: Procesar H mixtas (lácteos PH) ==========
    if fuentes_H_mixtas and h_remaining > 0:
        h_per_source = h_remaining / len(fuentes_H_mixtas)
        
        for info in fuentes_H_mixtas:
            alimento = info["alimento"]
            config = info["config"]
            macros_ef = info["macros_ef"]
            minimo = info["minimo"]
            maximo = info["maximo"]
            
            if macros_ef["H"] <= 0:
                continue
            
            min_h = macros_ef["H"] * minimo / 100
            if min_h > h_remaining + MARGEN_CALMA:
                not_found.append({
                    "buscado": info["buscado"],
                    "encontrado": alimento.get("nombre"),
                    "razon": razon_minimo_no_cabe(minimo, min_h, "H", h_remaining),
                    "alternativas": info["alternativas"]
                })
                continue
            
            cantidad_g, macros = calculate_food_amount(
                alimento, config, macros_ef, "H", h_per_source, minimo, maximo
            )
            
            if cantidad_g > 0:
                display = format_cantidad_display(cantidad_g, alimento, config)
                
                found_foods.append({
                    "nombre": alimento.get("nombre"),
                    "cantidad": cantidad_g,
                    "cantidad_display": display,
                    "macros": macros,
                    "alternativas": info["alternativas"]
                })
                
                totals["P"] += macros["P"]
                totals["H"] += macros["H"]
                totals["G"] += macros["G"]
                h_remaining -= macros["H"]
                p_remaining -= macros["P"]
    
    # ========== 5b: Procesar H con cantidad fija PRIMERO (por unidad o frutas) ==========
    for info in fuentes_H_fija:
        alimento = info["alimento"]
        config = info["config"]
        macros_ef = info["macros_ef"]
        minimo = info["minimo"]
        maximo = info["maximo"]
        
        if macros_ef["H"] <= 0:
            continue
        
        # Para alimentos por unidad, usar el mínimo (1 unidad típicamente)
        cantidad_g = minimo
        
        # Si es fruta, puede ser media unidad
        if config.get("permite_media", False):
            cantidad_g = minimo
        
        min_h = macros_ef["H"] * cantidad_g / 100
        if min_h > h_remaining + MARGEN_CALMA:
            not_found.append({
                "buscado": info["buscado"],
                "encontrado": alimento.get("nombre"),
                "razon": razon_minimo_no_cabe(cantidad_g, min_h, "H", h_remaining),
                "alternativas": info["alternativas"]
            })
            continue
        
        factor = cantidad_g / 100.0
        macros = {
            "P": round(macros_ef["P"] * factor, 1),
            "H": round(macros_ef["H"] * factor, 1),
            "G": round(macros_ef["G"] * factor, 1),
        }
        
        display = format_cantidad_display(cantidad_g, alimento, config)
        
        found_foods.append({
            "nombre": alimento.get("nombre"),
            "cantidad": cantidad_g,
            "cantidad_display": display,
            "macros": macros,
            "alternativas": info["alternativas"]
        })
        
        totals["P"] += macros["P"]
        totals["H"] += macros["H"]
        totals["G"] += macros["G"]
        h_remaining -= macros["H"]
    
    # ========== 5c: Procesar H por peso (ajustar para cubrir el resto) ==========
    if fuentes_H_peso and h_remaining > 0:
        # Repartir el H restante entre las fuentes de peso
        h_per_source = h_remaining / len(fuentes_H_peso)
        
        for info in fuentes_H_peso:
            alimento = info["alimento"]
            config = info["config"]
            macros_ef = info["macros_ef"]
            minimo = info["minimo"]
            maximo = info["maximo"]
            
            if macros_ef["H"] <= 0:
                continue
            
            # Verificar que el mínimo cabe
            min_h = macros_ef["H"] * minimo / 100
            if min_h > h_remaining + MARGEN_CALMA:
                not_found.append({
                    "buscado": info["buscado"],
                    "encontrado": alimento.get("nombre"),
                    "razon": razon_minimo_no_cabe(minimo, min_h, "H", h_remaining),
                    "alternativas": info["alternativas"]
                })
                continue
            
            cantidad_g, macros = calculate_food_amount(
                alimento, config, macros_ef, "H", h_per_source, minimo, maximo
            )
            
            if cantidad_g > 0:
                display = format_cantidad_display(cantidad_g, alimento, config)
                
                found_foods.append({
                    "nombre": alimento.get("nombre"),
                    "cantidad": cantidad_g,
                    "cantidad_display": display,
                    "macros": macros,
                    "alternativas": info["alternativas"]
                })
                
                totals["P"] += macros["P"]
                totals["H"] += macros["H"]
                totals["G"] += macros["G"]
                h_remaining -= macros["H"]
    
    # Paso 6: Procesar fuentes de P (descontando P ya aportada por PG y PH)
    p_remaining = p_obj - totals["P"]
    
    # Solo fuentes P puras (no PG que ya procesamos)
    fuentes_P_puras = [f for f in fuentes_P if f["role"] == "P"]
    
    if fuentes_P_puras and p_remaining > 0:
        p_per_source = p_remaining / len(fuentes_P_puras)
        
        for info in fuentes_P_puras:
            alimento = info["alimento"]
            config = info["config"]
            macros_ef = info["macros_ef"]
            minimo = info["minimo"]
            maximo = info["maximo"]
            
            if macros_ef["P"] <= 0:
                continue
            
            # Verificar que el mínimo cabe
            min_p = macros_ef["P"] * minimo / 100
            if min_p > p_remaining + MARGEN_CALMA:
                not_found.append({
                    "buscado": info["buscado"],
                    "encontrado": alimento.get("nombre"),
                    "razon": razon_minimo_no_cabe(minimo, min_p, "P", p_remaining),
                    "alternativas": info["alternativas"]
                })
                continue
            
            cantidad_g, macros = calculate_food_amount(
                alimento, config, macros_ef, "P", p_per_source, minimo, maximo
            )
            
            if cantidad_g > 0:
                display = format_cantidad_display(cantidad_g, alimento, config)
                
                found_foods.append({
                    "nombre": alimento.get("nombre"),
                    "cantidad": cantidad_g,
                    "cantidad_display": display,
                    "macros": macros,
                    "alternativas": info["alternativas"]
                })
                
                totals["P"] += macros["P"]
                totals["H"] += macros["H"]
                totals["G"] += macros["G"]
                p_remaining -= macros["P"]
    
    # Paso 7: Procesar fuentes de G SOLO SI QUEDA G POR CUBRIR
    g_remaining = g_obj - totals["G"]
    
    # Solo añadir grasas si realmente faltan (más de 2g)
    if fuentes_G and g_remaining > 2:
        g_per_source = g_remaining / len(fuentes_G)
        
        for info in fuentes_G:
            alimento = info["alimento"]
            config = info["config"]
            macros_ef = info["macros_ef"]
            minimo = info["minimo"]
            maximo = info["maximo"]
            
            if macros_ef["G"] <= 0:
                continue
            
            # Para alimentos por unidad, calcular el mínimo real (1 unidad)
            if config.get("por_unidad", False) or alimento.get("unidades", False):
                peso_unidad = config.get("peso_unidad", 0) or float(alimento.get("racion", 10))
                min_g_efectivo = macros_ef["G"] * peso_unidad / 100
            else:
                min_g_efectivo = macros_ef["G"] * minimo / 100
            
            # Si el mínimo de 1 unidad excede lo que queda + margen, rechazar
            if min_g_efectivo > g_remaining + MARGEN_CALMA:
                not_found.append({
                    "buscado": info["buscado"],
                    "encontrado": alimento.get("nombre"),
                    "razon": razon_minimo_no_cabe(
                        peso_unidad if (config.get("por_unidad", False) or alimento.get("unidades", False)) else minimo,
                        min_g_efectivo, "G", g_remaining),
                    "alternativas": info["alternativas"]
                })
                continue
            
            cantidad_g, macros = calculate_food_amount(
                alimento, config, macros_ef, "G", g_per_source, minimo, maximo
            )
            
            if cantidad_g > 0:
                display = format_cantidad_display(cantidad_g, alimento, config)
                
                found_foods.append({
                    "nombre": alimento.get("nombre"),
                    "cantidad": cantidad_g,
                    "cantidad_display": display,
                    "macros": macros,
                    "alternativas": info["alternativas"]
                })
                
                totals["P"] += macros["P"]
                totals["H"] += macros["H"]
                totals["G"] += macros["G"]
                g_remaining -= macros["G"]
    
    # Paso 8: Calcular restantes y verificar si cuadra
    remaining = {
        "P": round(p_obj - totals["P"], 1),
        "H": round(h_obj - totals["H"], 1),
        "G": round(g_obj - totals["G"], 1),
    }
    
    desviacion = {
        "P": round(totals["P"] - p_obj, 1),
        "H": round(totals["H"] - h_obj, 1),
        "G": round(totals["G"] - g_obj, 1),
    }
    
    cuadrado = (
        abs(desviacion["P"]) <= MARGEN_CALMA and
        abs(desviacion["H"]) <= MARGEN_CALMA and
        abs(desviacion["G"]) <= MARGEN_CALMA
    )
    
    # Paso 9: Generar sugerencia si faltan macros
    sugerencia = None
    faltantes = []
    ejemplos = []
    
    if remaining["P"] > MARGEN_CALMA:
        faltantes.append(f"{remaining['P']:.0f}g de proteína")
        ejemplos.append(f"claras ({remaining['P']*3:.0f}g) o pechuga ({remaining['P']*5:.0f}g)")
    
    if remaining["H"] > MARGEN_CALMA:
        faltantes.append(f"{remaining['H']:.0f}g de hidratos")
        ejemplos.append(f"avena ({remaining['H']*1.7:.0f}g) o boniato ({remaining['H']*5:.0f}g)")
    
    if remaining["G"] > MARGEN_CALMA:
        faltantes.append(f"{remaining['G']:.0f}g de grasa")
        ejemplos.append(f"aceite de oliva ({remaining['G']:.0f}ml)")
    
    if faltantes:
        sugerencia = f"Te faltan {' y '.join(faltantes)}. Puedes añadir: {' o '.join(ejemplos)}."
    
    return {
        "foods_added": found_foods,
        "foods_not_found": not_found,
        "totals": totals,
        "objetivo": {"P": p_obj, "H": h_obj, "G": g_obj},
        "remaining": remaining,
        "desviacion": desviacion,
        "cuadrado": cuadrado,
        "sugerencia": sugerencia
    }
