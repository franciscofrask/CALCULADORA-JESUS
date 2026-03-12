"""
Calculator CALMA v2 — Búsqueda, ajuste automático, sugerencias
Método Jesús Gallego — 12en12

Funciones principales:
- buscar_alimentos: búsqueda con filtros de categoría
- calcular_cantidad_automatica: calcula gramos óptimos
- ordenar_por_aporte: ordena alimentos por cuánto cuadran la comida
- validar_comida: verifica si la comida está cuadrada
- sugerir_alimentos: sugiere alimentos para completar la comida
"""

from typing import Dict, List, Optional
from calma_engine import (
    calcular_macros_efectivos,
    calcular_macros_efectivos_alimento,
    calcular_macros_brutos,
    que_macros_cuentan,
    _redondear_cantidad
)
import re
import unicodedata


# =========================================================
# FUNCIÓN: Normalizar texto (eliminar acentos)
# =========================================================

def normalize_text(text: str) -> str:
    """
    Normaliza texto eliminando acentos y diacríticos.
    'pollo' coincide con 'Pollo', 'atún' coincide con 'atun', etc.
    """
    if not text:
        return ""
    # Descomponer caracteres (á -> a + acento)
    normalized = unicodedata.normalize('NFD', text)
    # Eliminar los caracteres de combinación (acentos)
    without_accents = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    return without_accents.lower()

# =========================================================
# CONSTANTES — CATEGORÍAS PERMITIDAS
# =========================================================

# Categorías permitidas en INTRA-ENTRENO (solo estas)
CATS_INTRA = ['41', '18.1.1', '18.1.3', '18.1.2']

# Categorías permitidas en POST-ENTRENO (solo estas)
CATS_POST = [
    '4.1.1', '4.1.2', '4.1', '4.2', '5.4', '5.2.3', '5.2.2', '5.1',
    '4.3', '27', '21.3', '7.1.1', '7.1.2.1',
    '18.3', '11.5', '11.2.1', '11.2.2', '11.1', '11.4', '11.2.1',
    '11.2.2', '11.6', '11.7', '21.2', '7.3.1',
    '8', '24', '19.1', '18.1', '18.2', '37', '16.5', '16.1'
]

# Categorías para CUADRAR GRASAS AL FINAL
CATS_CUADRAR_GRASAS = ['17.1.1', '17.1', '42']

# Categorías de PROTEÍNA (para el flujo guiado paso 1)
CATS_PROTEINA = [
    '1', '1.1', '1.2',           # Huevos
    '2', '2.1', '2.2', '2.3', '2.4', '2.6', '2.7',  # Carnes
    '3', '3.1', '3.2', '3.3', '3.4', '3.7', '3.8', '3.9',  # Pescados
    '4', '4.1', '4.2', '4.3',    # Proteína polvo
    '5', '5.1', '5.2', '5.3', '5.4',  # Lácteos
    '10', '10.1', '10.2',        # Legumbres
    '28',                          # Proteína vegetal
    '6', '6.1', '6.2',           # Soja
]

# Categorías de HIDRATOS (para el flujo guiado paso 2)
CATS_HIDRATOS = [
    '21', '21.1', '21.2', '21.3', '21.4',  # Arroces
    '8',                                       # Panes
    '7', '7.1', '7.2', '7.3', '7.4', '7.5', '7.6',  # Cereales
    '22', '22.1', '22.2', '22.3', '22.4', '22.5', '22.6',  # Pasta
    '9',                                       # Tubérculos
    '11', '11.1', '11.4', '11.5',            # Frutas
    '24',                                      # Bebidas vegetales
]

# Categorías de VERDURAS (para el flujo guiado paso 3)
CATS_VERDURAS = ['13', '13.1', '13.2', '13.4', '13.8']

# Categorías de GRASAS (para el flujo guiado paso 4)
CATS_GRASAS = [
    '17.1', '17.1.1', '17.1.2', '17.1.3',   # Aceites
    '17.6',                                     # Aguacate
    '17.2.1', '17.2.3', '17.2.4',            # Frutos secos naturales
    '17.4',                                     # Mantequilla
    '42',                                       # Grasas buena calidad
]

# Alimentos que van en MEDIAS UNIDADES
# Cat 11.1 siempre va de media en media
# Más las excepciones por nombre
def es_media_unidad(alimento: dict) -> bool:
    """Determina si un alimento se mide en medias unidades."""
    cats = str(alimento.get("categoria", ""))
    nombre = str(alimento.get("nombre", "")).lower()
    
    # Cat 11.1 (Fruta fresca) siempre va de media en media
    if cats == "11.1" or cats.startswith("11.1."):
        return True
    
    # Excepciones por nombre
    if 'hamburguesa' in nombre or 'bagel' in nombre:
        return True
    if 'brazo' in nombre and 'my fitness meals' in nombre:
        return True
    if 'bizcocho' in nombre and 'my fitness meals' in nombre:
        return True
    if 'arroz' in nombre and 'minuto' in nombre:
        return True
    
    return False


def detectar_preparacion(alimento: dict) -> Optional[str]:
    """Detecta forma de preparación automática por el nombre."""
    nombre = str(alimento.get("nombre", "")).lower()
    
    if 'harina' in nombre:
        return 'polvo'
    if 'crema' in nombre and 'arroz' in nombre:
        return 'polvo'
    
    keywords = {
        'congelad': 'congelado',
        'helad': 'helado',
        'ahumad': 'ahumado',
        ' lata': 'lata',
        'conserva': 'conserva',
        'polvo': 'polvo',
    }
    
    for keyword, prep in keywords.items():
        if keyword in nombre:
            return prep
    
    return None


def es_marca_recomendada(alimento: dict) -> bool:
    """Verifica si el alimento es de marca recomendada."""
    tags = alimento.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]
    return 'PRO' in tags


# =========================================================
# FUNCIONES DE CATEGORÍA
# =========================================================

def cat_matches(cat_alimento: str, cat_filtro: str) -> bool:
    """Verifica si la categoría del alimento coincide con el filtro.
    
    Ejemplo: cat_alimento="2.2.1" coincide con cat_filtro="2" (es subcategoría)
    """
    cat_a = str(cat_alimento).strip()
    cat_f = str(cat_filtro).strip()
    
    if cat_a == cat_f:
        return True
    if cat_a.startswith(cat_f + "."):
        return True
    return False


def cat_in_list(cat_alimento: str, lista_cats: list) -> bool:
    """Verifica si la categoría del alimento está en alguna de la lista."""
    for cat_f in lista_cats:
        if cat_matches(cat_alimento, cat_f):
            return True
    return False


def get_categoria_principal(alimento: dict) -> str:
    """Obtiene la categoría principal de un alimento."""
    cat = alimento.get("categoria", alimento.get("categorias", ""))
    if isinstance(cat, list):
        return str(cat[0]) if cat else ""
    if isinstance(cat, str):
        # Manejar formato "2.2.2 | HAM"
        if "|" in cat:
            parts = cat.split("|")
            return parts[0].strip()
        if "," in cat:
            parts = cat.split(",")
            return parts[0].strip()
    return str(cat).strip()


def get_categorias(alimento: dict) -> list:
    """Obtiene todas las categorías de un alimento."""
    cat = alimento.get("categoria", alimento.get("categorias", ""))
    if isinstance(cat, list):
        return [str(c).strip() for c in cat]
    if isinstance(cat, str):
        # Manejar formato "2.2.2 | HAM" o "2.2.2, 28"
        parts = cat.replace("|", ",").split(",")
        return [c.strip() for c in parts if c.strip()]
    return [str(cat).strip()] if cat else []


# =========================================================
# FUNCIÓN PRINCIPAL: Calcular cantidad automática
# =========================================================

def calcular_cantidad_automatica(
    alimento: dict,
    macros_restantes: Dict[str, float],
    es_vegano: bool = False
) -> Dict:
    """
    Calcula la cantidad óptima de un alimento para cubrir los macros restantes
    sin pasarse en ningún macro.
    
    REGLA CLAVE: Se ajusta siempre al macro MÁS LIMITANTE.
    Si un alimento alcanza antes el tope de grasas que el de proteínas,
    para en las grasas aunque la proteína no esté al 100%.
    
    Args:
        alimento: dict de MongoDB con campos: proteinas, hidratos, grasas, racion, categoria
        macros_restantes: {"P": X, "H": Y, "G": Z} o {"proteina": X, "hidratos": Y, "grasa": Z}
    
    Returns:
        dict con cantidad_g, macros_efectivos, macros_brutos, que_cuenta, cabe
    """
    
    # Normalizar keys de macros_restantes
    p_rest = float(macros_restantes.get("P", macros_restantes.get("proteina", 0)) or 0)
    h_rest = float(macros_restantes.get("H", macros_restantes.get("hidratos", 0)) or 0)
    g_rest = float(macros_restantes.get("G", macros_restantes.get("grasa", 0)) or 0)
    
    # Datos del alimento
    racion = float(alimento.get("racion", 100) or 100)
    P_base = float(alimento.get("proteinas", 0) or 0)
    H_base = float(alimento.get("hidratos", 0) or 0)
    G_base = float(alimento.get("grasas", 0) or 0)
    
    # Macros por 100g
    P_100 = P_base * 100.0 / racion if racion > 0 else 0
    H_100 = H_base * 100.0 / racion if racion > 0 else 0
    G_100 = G_base * 100.0 / racion if racion > 0 else 0
    
    # Categoría
    cat = get_categoria_principal(alimento)
    cat_sec = None
    cats = get_categorias(alimento)
    if len(cats) > 1:
        cat_sec = cats[1]
    
    # Calcular qué macros cuentan (usando una ración de referencia de 100g)
    efectivos_100 = calcular_macros_efectivos(
        P_100, H_100, G_100, cat, 100.0, cat_sec, es_vegano
    )
    
    p_ef_100 = efectivos_100["proteina_efectiva"]
    h_ef_100 = efectivos_100["hidratos_efectivos"]
    g_ef_100 = efectivos_100["grasa_efectiva"]
    
    # Calcular cantidad máxima por cada macro EFECTIVO
    cantidades = []
    
    if p_ef_100 > 0 and p_rest > 0:
        cantidades.append(p_rest / p_ef_100 * 100)
    elif p_ef_100 > 0 and p_rest <= 0:
        # Si P cuenta pero ya no necesitamos P, este alimento se pasaría
        cantidades.append(0)
    
    if h_ef_100 > 0 and h_rest > 0:
        cantidades.append(h_rest / h_ef_100 * 100)
    elif h_ef_100 > 0 and h_rest <= 0:
        cantidades.append(0)
    
    if g_ef_100 > 0 and g_rest > 0:
        cantidades.append(g_rest / g_ef_100 * 100)
    elif g_ef_100 > 0 and g_rest <= 0:
        cantidades.append(0)
    
    if not cantidades:
        return {
            "cantidad_g": 0,
            "macros_efectivos": {"P": 0, "H": 0, "G": 0, "kcal": 0},
            "macros_brutos": {"P": 0, "H": 0, "G": 0, "kcal": 0},
            "que_cuenta": {"P": False, "H": False, "G": False},
            "cabe": False
        }
    
    # Elegir la cantidad MÍNIMA (macro más limitante)
    cantidad = max(0, min(cantidades))
    
    # Manejar medias unidades
    if es_media_unidad(alimento):
        peso_unidad = float(alimento.get("peso_unidad", racion) or racion)
        media = peso_unidad / 2.0
        if media > 0:
            cantidad = round(cantidad / media) * media
            if cantidad < media:
                cantidad = media
    else:
        # Redondear según categoría
        cantidad = _redondear_cantidad(cantidad, cat)
    
    # Mínimo 5g (salvo que sea 0)
    if 0 < cantidad < 5:
        cantidad = 5
    
    # Recalcular macros efectivos con la cantidad final
    # (la calibración puede cambiar con la nueva cantidad)
    efectivos_final = calcular_macros_efectivos(
        P_100, H_100, G_100, cat, cantidad, cat_sec, es_vegano
    )
    
    # Macros brutos
    factor = cantidad / 100.0
    p_bruta = round(P_100 * factor, 1)
    h_bruta = round(H_100 * factor, 1)
    g_bruta = round(G_100 * factor, 1)
    
    # Verificar si cabe (no se pasa en ningún macro efectivo)
    p_ef = efectivos_final["proteina_efectiva"]
    h_ef = efectivos_final["hidratos_efectivos"]
    g_ef = efectivos_final["grasa_efectiva"]
    
    cabe = True
    if p_ef > p_rest + 4:  # margen CALMA de 4g
        cabe = False
    if h_ef > h_rest + 4:
        cabe = False
    if g_ef > g_rest + 4:
        cabe = False
    
    kcal_ef = round(p_ef * 4 + h_ef * 4 + g_ef * 9, 1)
    kcal_bruta = round(p_bruta * 4 + h_bruta * 4 + g_bruta * 9, 1)
    
    return {
        "cantidad_g": cantidad,
        "macros_efectivos": {"P": p_ef, "H": h_ef, "G": g_ef, "kcal": kcal_ef},
        "macros_brutos": {"P": p_bruta, "H": h_bruta, "G": g_bruta, "kcal": kcal_bruta},
        "que_cuenta": {
            "P": efectivos_final["proteina_cuenta"],
            "H": efectivos_final["hidratos_cuenta"],
            "G": efectivos_final["grasa_cuenta"]
        },
        "cabe": cabe
    }


# =========================================================
# FUNCIÓN: Calcular aporte total de un alimento
# (para ordenación: mayor aporte primero)
# =========================================================

def calcular_aporte_total(
    alimento: dict,
    macros_restantes: Dict[str, float],
    es_vegano: bool = False
) -> Dict:
    """
    Calcula cuánto aporta un alimento al máximo sin pasarse.
    Devuelve el total de macros efectivos que aportaría.
    Se usa para ORDENAR: el que más aporta va primero.
    
    REGLA: calcula la cantidad máxima que cabe, luego suma todos los macros
    efectivos de esa cantidad. El que tiene mayor suma total cuadra la comida más rápido.
    """
    resultado = calcular_cantidad_automatica(alimento, macros_restantes, es_vegano)
    
    ef = resultado["macros_efectivos"]
    total_macros = ef.get("P", 0) + ef.get("H", 0) + ef.get("G", 0)
    
    return {
        "alimento": alimento,
        "cantidad_g": resultado["cantidad_g"],
        "macros_efectivos": ef,
        "total_macros_aportados": total_macros,
        "cabe": resultado["cabe"],
        "es_marca_recomendada": es_marca_recomendada(alimento)
    }


# =========================================================
# FUNCIÓN: Ordenar alimentos por aporte
# =========================================================

def ordenar_por_aporte(
    alimentos: list,
    macros_restantes: Dict[str, float],
    es_vegano: bool = False
) -> list:
    """
    Ordena alimentos por cuánto cuadran la comida:
    1. Primero los que CABEN (no se pasan)
    2. Dentro de los que caben: por total de macros aportados (mayor primero)
    3. Dentro de misma prioridad: marcas recomendadas primero
    
    REGLA: "calcula la cantidad máxima de cada alimento que cabe sin pasarse,
    después calcula el total de macros para esa cantidad y los ordena
    de mayor a menor macros aportados"
    """
    resultados = []
    
    for alimento in alimentos:
        try:
            aporte = calcular_aporte_total(alimento, macros_restantes, es_vegano)
            resultados.append(aporte)
        except Exception:
            continue
    
    # Ordenar:
    # 1. cabe=True primero
    # 2. mayor total_macros_aportados
    # 3. marca recomendada primero (dentro de mismo nivel)
    resultados.sort(
        key=lambda x: (
            x["cabe"],                          # True > False
            x["total_macros_aportados"],        # Mayor primero
            x["es_marca_recomendada"],          # True > False
        ),
        reverse=True
    )
    
    return resultados


# =========================================================
# FUNCIÓN: Filtrar alimentos por tipo de comida
# =========================================================

def filtrar_por_tipo_comida(alimentos: list, tipo_comida: str) -> list:
    """
    Filtra alimentos según el tipo de comida:
    - "normal": todos los alimentos (sin restricción)
    - "intra": solo categorías CATS_INTRA
    - "post": solo categorías CATS_POST
    - "cuadrar_grasas": solo categorías CATS_CUADRAR_GRASAS
    """
    if tipo_comida == "normal":
        return alimentos
    
    if tipo_comida == "intra":
        cats_permitidas = CATS_INTRA
    elif tipo_comida == "post":
        cats_permitidas = CATS_POST
    elif tipo_comida == "cuadrar_grasas":
        cats_permitidas = CATS_CUADRAR_GRASAS
    else:
        return alimentos
    
    resultado = []
    for alimento in alimentos:
        cat = get_categoria_principal(alimento)
        if cat_in_list(cat, cats_permitidas):
            resultado.append(alimento)
    
    return resultado


# =========================================================
# FUNCIÓN: Sugerir alimentos para completar comida
# =========================================================

def sugerir_alimentos(
    alimentos_disponibles: list,
    macros_restantes: Dict[str, float],
    tipo_comida: str = "normal",
    es_vegano: bool = False,
    max_resultados: int = 20,
    excluir_ids: list = None
) -> list:
    """
    Sugiere los mejores alimentos para completar una comida.
    
    REGLA PRINCIPAL: "la calculadora siempre sugiere el alimento que antes
    cuadre con los 3 macros, con independencia de si estoy cuadrando
    proteínas o hidratos. Calcula la cantidad máxima que cabe y los ordena
    de mayor a menor macros aportados."
    
    EXCEPCIONES:
    1. Intra/Post: solo categorías permitidas
    2. Cuadrar grasas al final: solo aceites y grasas buenas
    """
    excluir = set(excluir_ids or [])
    
    # Paso 1: Filtrar por tipo de comida
    filtrados = filtrar_por_tipo_comida(alimentos_disponibles, tipo_comida)
    
    # Paso 2: Excluir alimentos ya en la comida
    filtrados = [a for a in filtrados if a.get("id") not in excluir]
    
    # Paso 3: Filtrar vegano si aplica
    if es_vegano:
        cats_excluir_vegano = ['1', '2', '3', '4.1', '4.2', '5']
        filtrados = [
            a for a in filtrados
            if not cat_in_list(get_categoria_principal(a), cats_excluir_vegano)
        ]
    
    # Paso 4: Detectar si estamos "cuadrando al final"
    p_rest = float(macros_restantes.get("P", macros_restantes.get("proteina", 0)) or 0)
    h_rest = float(macros_restantes.get("H", macros_restantes.get("hidratos", 0)) or 0)
    g_rest = float(macros_restantes.get("G", macros_restantes.get("grasa", 0)) or 0)
    
    # Si solo faltan grasas (P y H dentro de margen), priorizar categorías de cuadrar grasas
    if abs(p_rest) <= 4 and abs(h_rest) <= 4 and g_rest > 4:
        # Primero intentar con grasas buenas
        grasas_buenas = filtrar_por_tipo_comida(filtrados, "cuadrar_grasas")
        if grasas_buenas:
            ordenados = ordenar_por_aporte(grasas_buenas, macros_restantes, es_vegano)
            # Añadir el resto por si el usuario quiere más opciones
            otros = [a for a in filtrados if a.get("id") not in {g["alimento"].get("id") for g in ordenados}]
            ordenados_otros = ordenar_por_aporte(otros, macros_restantes, es_vegano)
            return (ordenados + ordenados_otros)[:max_resultados]
    
    # Paso 5: Ordenar por aporte (mayor primero)
    ordenados = ordenar_por_aporte(filtrados, macros_restantes, es_vegano)
    
    return ordenados[:max_resultados]


# =========================================================
# FUNCIÓN: Validar comida (¿está cuadrada?)
# =========================================================

def validar_comida(
    alimentos_comida: list,
    macros_objetivo: Dict[str, float],
    es_vegano: bool = False
) -> Dict:
    """
    Valida si una comida está cuadrada (±4g en cada macro).
    
    Args:
        alimentos_comida: lista de dicts con {alimento_id, nombre, cantidad_g, macros_efectivos}
        macros_objetivo: {"P": X, "H": Y, "G": Z}
    
    Returns:
        dict con estado, macros_servidos, macros_objetivo, diferencia
    """
    p_obj = float(macros_objetivo.get("P", macros_objetivo.get("proteina", 0)) or 0)
    h_obj = float(macros_objetivo.get("H", macros_objetivo.get("hidratos", 0)) or 0)
    g_obj = float(macros_objetivo.get("G", macros_objetivo.get("grasa", 0)) or 0)
    
    p_servido = 0
    h_servido = 0
    g_servido = 0
    
    for alimento in alimentos_comida:
        ef = alimento.get("macros_efectivos", {})
        p_servido += float(ef.get("P", ef.get("proteina", 0)) or 0)
        h_servido += float(ef.get("H", ef.get("hidratos", 0)) or 0)
        g_servido += float(ef.get("G", ef.get("grasa", 0)) or 0)
    
    diff_p = round(p_servido - p_obj, 1)
    diff_h = round(h_servido - h_obj, 1)
    diff_g = round(g_servido - g_obj, 1)
    
    p_ok = abs(diff_p) <= 4
    h_ok = abs(diff_h) <= 4
    g_ok = abs(diff_g) <= 4
    
    cuadrada = p_ok and h_ok and g_ok
    
    if cuadrada:
        estado = "cuadrada"
    elif p_servido < p_obj - 4 or h_servido < h_obj - 4 or g_servido < g_obj - 4:
        estado = "falta"
    else:
        estado = "sobra"
    
    return {
        "estado": estado,
        "cuadrada": cuadrada,
        "macros_servidos": {
            "P": round(p_servido, 1),
            "H": round(h_servido, 1),
            "G": round(g_servido, 1),
            "kcal": round(p_servido * 4 + h_servido * 4 + g_servido * 9, 1)
        },
        "macros_objetivo": {
            "P": p_obj, "H": h_obj, "G": g_obj,
            "kcal": round(p_obj * 4 + h_obj * 4 + g_obj * 9, 1)
        },
        "diferencia": {"P": diff_p, "H": diff_h, "G": diff_g},
        "detalle": {
            "P": "ok" if p_ok else ("sobra" if diff_p > 0 else "falta"),
            "H": "ok" if h_ok else ("sobra" if diff_h > 0 else "falta"),
            "G": "ok" if g_ok else ("sobra" if diff_g > 0 else "falta"),
        }
    }


# =========================================================
# FUNCIÓN: Buscar alimentos en MongoDB
# =========================================================

async def buscar_alimentos(
    db,
    query: str = "",
    categoria: str = "",
    tipo_comida: str = "normal",
    es_vegano: bool = False,
    limit: int = 50,
    excluir_categorias: list = None,
    calcular_efectivos: bool = False
) -> list:
    """
    Busca alimentos en MongoDB con filtros.
    
    Args:
        db: conexión MongoDB
        query: texto de búsqueda (nombre del alimento)
        categoria: filtrar por categoría específica
        tipo_comida: "normal", "intra", "post" (filtra categorías permitidas)
        es_vegano: filtra alimentos de origen animal
        limit: máximo de resultados
        excluir_categorias: lista de categorías a excluir
        calcular_efectivos: si True, calcula macros efectivos para cada alimento
    """
    filtro = {}
    
    # Filtro por categoría específica
    if categoria:
        filtro["$or"] = [
            {"categorias": categoria},
            {"categorias": {"$regex": f"^{re.escape(categoria)}\\."}}
        ]
    
    # Determinar límite de búsqueda en MongoDB
    # Si hay query de texto, necesitamos traer más porque filtramos en Python
    if query and len(query) >= 2:
        # Traer todos los alimentos (o los filtrados por categoría) para buscar por texto
        search_limit = 4000  # Suficiente para cubrir toda la BD
    else:
        search_limit = limit * 3
    
    cursor = db.foods.find(filtro, {"_id": 0}).limit(search_limit)
    alimentos = await cursor.to_list(length=search_limit)
    
    # Filtrar por texto con normalización de acentos
    if query and len(query) >= 2:
        query_normalized = normalize_text(query)
        alimentos = [
            a for a in alimentos
            if query_normalized in normalize_text(a.get("nombre", ""))
        ]
    
    # Filtrar por tipo de comida (intra/post)
    if tipo_comida in ("intra", "post"):
        alimentos = filtrar_por_tipo_comida(alimentos, tipo_comida)
    
    # Filtrar vegano
    if es_vegano:
        cats_excluir_vegano = ['1', '2', '3', '4.1', '4.2', '5']
        alimentos = [
            a for a in alimentos
            if not cat_in_list(get_categoria_principal(a), cats_excluir_vegano)
        ]
    
    # Excluir categorías específicas
    if excluir_categorias:
        alimentos = [
            a for a in alimentos
            if not cat_in_list(get_categoria_principal(a), excluir_categorias)
        ]
    
    # Limitar resultados
    alimentos = alimentos[:limit]
    
    # Calcular macros efectivos si se solicita
    if calcular_efectivos:
        for alimento in alimentos:
            racion = float(alimento.get("racion", 100) or 100)
            macros_ef = calcular_macros_efectivos_alimento(alimento, racion, es_vegano)
            cuenta = que_macros_cuentan(alimento, racion, es_vegano)
            alimento["macros_efectivos"] = macros_ef
            alimento["que_cuenta"] = cuenta
    
    return alimentos


# =========================================================
# TESTS
# =========================================================

def run_tests():
    """Tests de verificación."""
    tests = []
    
    def test(nombre, condicion, detalle=""):
        tests.append({"nombre": nombre, "passed": condicion, "detalle": detalle})
    
    # Test 1: Categorías intra
    test("CATS_INTRA tiene 4 categorías", len(CATS_INTRA) == 4, f"tiene {len(CATS_INTRA)}")
    
    # Test 2: Categorías post
    test("CATS_POST tiene categorías", len(CATS_POST) > 20, f"tiene {len(CATS_POST)}")
    
    # Test 3: cat_matches
    test("cat_matches 2.2.1 con 2", cat_matches("2.2.1", "2") == True)
    test("cat_matches 2.2.1 con 3", cat_matches("2.2.1", "3") == False)
    test("cat_matches 17.1.1 con 17.1", cat_matches("17.1.1", "17.1") == True)
    test("cat_matches 17.1.1 con 17", cat_matches("17.1.1", "17") == True)
    test("cat_matches 41 con 41", cat_matches("41", "41") == True)
    
    # Test 4: cat_in_list para intra
    test("Cat 41 válida para intra", cat_in_list("41", CATS_INTRA) == True)
    test("Cat 18.1.1 válida para intra", cat_in_list("18.1.1", CATS_INTRA) == True)
    test("Cat 2 NO válida para intra", cat_in_list("2", CATS_INTRA) == False)
    test("Cat 21 NO válida para intra", cat_in_list("21", CATS_INTRA) == False)
    
    # Test 5: cat_in_list para post
    test("Cat 4.1.1 válida para post", cat_in_list("4.1.1", CATS_POST) == True)
    test("Cat 4.1 válida para post", cat_in_list("4.1", CATS_POST) == True)
    test("Cat 11.1 válida para post", cat_in_list("11.1", CATS_POST) == True)
    test("Cat 2 NO válida para post", cat_in_list("2", CATS_POST) == False)
    
    # Test 6: Cuadrar grasas
    test("Cat 17.1.1 para cuadrar grasas", cat_in_list("17.1.1", CATS_CUADRAR_GRASAS) == True)
    test("Cat 42 para cuadrar grasas", cat_in_list("42", CATS_CUADRAR_GRASAS) == True)
    test("Cat 2 NO para cuadrar grasas", cat_in_list("2", CATS_CUADRAR_GRASAS) == False)
    
    # Test 7: calcular_cantidad_automatica — Pechuga pollo
    alimento_pollo = {
        "id": 1, "nombre": "Pechuga de pollo",
        "proteinas": 21.0, "hidratos": 0.0, "grasas": 1.5,
        "racion": 100, "categorias": "2.2.1"
    }
    resultado = calcular_cantidad_automatica(
        alimento_pollo, {"P": 45, "H": 75, "G": 13}
    )
    test(
        "Pollo: solo cuenta P, G<3% no cuenta",
        resultado["macros_efectivos"]["G"] == 0,
        f"G={resultado['macros_efectivos']['G']}, cantidad={resultado['cantidad_g']}g"
    )
    test(
        "Pollo: cantidad ~200-225g",
        175 <= resultado["cantidad_g"] <= 250,
        f"cantidad={resultado['cantidad_g']}g"
    )
    
    # Test 8: calcular_cantidad_automatica — Salmón
    alimento_salmon = {
        "id": 2, "nombre": "Salmón a la plancha",
        "proteinas": 22.0, "hidratos": 0.0, "grasas": 13.0,
        "racion": 100, "categorias": "3.1"
    }
    resultado = calcular_cantidad_automatica(
        alimento_salmon, {"P": 45, "H": 75, "G": 13}
    )
    test(
        "Salmón: G sí cuenta (13>=3)",
        resultado["macros_efectivos"]["G"] > 0,
        f"G={resultado['macros_efectivos']['G']}"
    )
    test(
        "Salmón: limitado por G (100g max para 13G)",
        resultado["cantidad_g"] <= 125,
        f"cantidad={resultado['cantidad_g']}g"
    )
    
    # Test 9: calcular_cantidad_automatica — Arroz
    alimento_arroz = {
        "id": 3, "nombre": "Arroz blanco",
        "proteinas": 7.0, "hidratos": 78.0, "grasas": 0.6,
        "racion": 100, "categorias": "21.1"
    }
    resultado = calcular_cantidad_automatica(
        alimento_arroz, {"P": 0, "H": 75, "G": 10}
    )
    test(
        "Arroz: solo cuenta H, P nunca",
        resultado["macros_efectivos"]["P"] == 0,
        f"P={resultado['macros_efectivos']['P']}"
    )
    test(
        "Arroz: cantidad ~96g para 75H",
        75 <= resultado["cantidad_g"] <= 125,
        f"cantidad={resultado['cantidad_g']}g, H={resultado['macros_efectivos']['H']}"
    )
    
    # Test 10: calcular_cantidad_automatica — Patata (solo H)
    alimento_patata = {
        "id": 4, "nombre": "Patata cocida",
        "proteinas": 2.0, "hidratos": 17.0, "grasas": 0.1,
        "racion": 100, "categorias": "9"
    }
    resultado = calcular_cantidad_automatica(
        alimento_patata, {"P": 0, "H": 34, "G": 0}
    )
    test(
        "Patata: P=0 G=0 (cat 9 solo H)",
        resultado["macros_efectivos"]["P"] == 0 and resultado["macros_efectivos"]["G"] == 0,
        f"P={resultado['macros_efectivos']['P']}, G={resultado['macros_efectivos']['G']}"
    )
    
    # Test 11: Validar comida cuadrada
    comida = [
        {"macros_efectivos": {"P": 43, "H": 73, "G": 12}},
        {"macros_efectivos": {"P": 0, "H": 0, "G": 0}},
    ]
    val = validar_comida(comida, {"P": 45, "H": 75, "G": 13})
    test("Comida cuadrada (±4g)", val["cuadrada"] == True, f"estado={val['estado']}")
    
    # Test 12: Validar comida NO cuadrada
    comida2 = [
        {"macros_efectivos": {"P": 30, "H": 73, "G": 12}},
    ]
    val2 = validar_comida(comida2, {"P": 45, "H": 75, "G": 13})
    test("Comida falta P", val2["cuadrada"] == False and val2["estado"] == "falta", f"estado={val2['estado']}")
    
    # Test 13: es_media_unidad
    test("Fruta fresca es media unidad", es_media_unidad({"categoria": "11.1"}) == True)
    test("Hamburguesa es media unidad", es_media_unidad({"categoria": "2", "nombre": "Hamburguesa ternera"}) == True)
    test("Pollo NO es media unidad", es_media_unidad({"categoria": "2.2.1", "nombre": "Pechuga pollo"}) == False)
    test("Bagel es media unidad", es_media_unidad({"categoria": "8", "nombre": "Bagel integral"}) == True)
    
    # Test 14: detectar_preparacion
    test("Congelado detectado", detectar_preparacion({"nombre": "Pollo congelado"}) == "congelado")
    test("Harina es polvo", detectar_preparacion({"nombre": "Harina de avena"}) == "polvo")
    test("Crema de arroz es polvo", detectar_preparacion({"nombre": "Crema de arroz"}) == "polvo")
    test("Pollo plancha sin prep", detectar_preparacion({"nombre": "Pollo a la plancha"}) is None)
    
    # Test 15: es_marca_recomendada
    test("Con tag PRO es recomendada", es_marca_recomendada({"tags": ["PRO", "TOP"]}) == True)
    test("Sin tag PRO no es recomendada", es_marca_recomendada({"tags": ["GEN"]}) == False)
    test("Sin tags no es recomendada", es_marca_recomendada({}) == False)
    
    # Test 16: Ordenación — el que más aporta va primero
    alimentos = [alimento_arroz, alimento_pollo, alimento_salmon]
    ordenados = ordenar_por_aporte(alimentos, {"P": 45, "H": 75, "G": 13})
    # El pollo debería aportar más macros totales (45P) que el arroz (~75H limitado)
    # que el salmón (limitado por G=13 → ~100g → ~22P)
    test(
        "Ordenación: mayor aporte primero",
        len(ordenados) == 3,
        f"1º={ordenados[0]['alimento']['nombre'] if ordenados else 'VACÍO'}"
    )
    
    # Test 17: get_categoria_principal con formato "2.2.2 | HAM"
    alimento_formato_pipe = {"categorias": "2.2.2 | HAM"}
    test(
        "get_categoria_principal con pipe",
        get_categoria_principal(alimento_formato_pipe) == "2.2.2",
        f"got: {get_categoria_principal(alimento_formato_pipe)}"
    )
    
    # Test 18: get_categorias con formato "2.2.2 | HAM"
    cats = get_categorias(alimento_formato_pipe)
    test(
        "get_categorias con pipe",
        len(cats) == 2 and cats[0] == "2.2.2" and cats[1] == "HAM",
        f"got: {cats}"
    )
    
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
    print(f"\nCalculator Tests: {results['passed']}/{results['total']}")
    if not results["all_passed"]:
        for t in results["failed_tests"]:
            print(f"  ❌ {t['nombre']}: {t['detalle']}")
