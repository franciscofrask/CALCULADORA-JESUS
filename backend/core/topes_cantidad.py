"""
CUANTO DE UN ALIMENTO CABE EN UNA COMIDA DE VERDAD.

Esta tabla vivia dentro del asistente (`chatbot._get_max_cantidad_razonable`), que la usa
para no proponer 266 g de claras ni 500 g de salsa de soja. La calculadora no la tenia: alli
el unico freno era un tope plano de 2000 g, asi que se podia guardar un litro de leche de
almendras en una comida y nadie decia nada (Jesus, 16-08).

Vive aqui para que el asistente y la calculadora usen EL MISMO numero. Si el tope de la
leche cambia, cambia en los dos sitios a la vez o vuelve a haber dos criterios.

Lo que este modulo dice es un tope RAZONABLE, no un maximo legal: por encima se avisa y se
deja seguir si el cliente insiste. Quien bloquea de verdad es el tope duro de la calculadora.
"""
from typing import Any, Dict, Optional

# Limites por categoria (en gramos), calibrados con las cantidades que aparecen en las
# dietas reales de los clientes.
LIMITES: Dict[str, int] = {
    "1.1": 300,   # Claras: en dietas reales se usan 200-300g
    "1.2": 190,   # Huevos enteros: máximo 3 (63g L * 3)
    "2.1": 150,   # Embutidos/Fiambres
    "2.2": 300,   # Aves
    "2.3": 300,   # Vacuno
    "2.4": 300,   # Cerdo
    "2.6": 300,   # Otras carnes
    "3": 300,     # Pescado
    "4": 60,      # Proteína en polvo
    "5.1": 400,   # Leche (un vaso grande / bol)
    "5.2.3": 500, # Queso fresco batido (tarrina)
    "5.2": 250,   # Yogures
    "5.3": 100,   # Quesos
    "7": 120,     # Cereales
    "8": 150,     # Panes
    "9": 350,     # Tubérculos
    "10": 250,    # Legumbres
    "11": 300,    # Frutas
    "13": 400,    # Verduras
    "16": 30,     # Salsas y condimentos: nunca son "el plato"
    "17.1": 30,   # Aceites
    "17.2": 60,   # Frutos secos
    "17.6": 150,  # Aguacate
    "18": 500,    # Bebidas deportivas / refrescos (una botella)
    "19": 400,    # Otras bebidas (cerveza 0%, vegetales...)
    "21": 150,    # Arroces (en seco)
    "22": 150,    # Pasta (en seco)
}

# Lo que se admite de un alimento que no encaja en ninguna categoria conocida.
POR_DEFECTO = 300


def max_cantidad_razonable(cat: str, config: dict, racion: float) -> float:
    """
    Devuelve la cantidad máxima razonable para un alimento según su categoría.
    Esto evita que el bot sugiera cantidades absurdas como 266g de claras.

    REGLA: El chatbot debe sugerir cantidades que un humano usaría en una comida real.
    """
    cat = str(cat or "")

    # Si es por unidad, máximo 3-4 unidades
    if config.get("por_unidad", False):
        peso_unidad = config.get("peso_unidad", racion)
        # Máximo 3 unidades para la mayoría, 4 para panes pequeños
        if cat.startswith("8"):  # Panes
            return peso_unidad * 4
        elif cat.startswith("1.2"):  # Huevos enteros
            return peso_unidad * 3  # Máximo 3 huevos
        elif cat.startswith("5.2"):  # Yogures
            return peso_unidad * 2  # Máximo 2 yogures
        else:
            return peso_unidad * 3

    # Buscar límite para la categoría (soporta subcategorías)
    for cat_prefix, max_g in LIMITES.items():
        if cat.startswith(cat_prefix):
            return max_g

    return POR_DEFECTO


def tope_de_alimento(alimento: Optional[Dict[str, Any]]) -> Optional[float]:
    """El tope razonable de una FICHA del catalogo, resolviendo sola su categoria y unidad.

    Es la puerta por la que entra la calculadora: alli no hay ni `cat` ni `config` a mano,
    solo el alimento tal cual sale del buscador.
    """
    if not alimento:
        return None
    try:
        from calculator import get_food_config
        from calma_engine import parse_categories

        config = get_food_config(alimento)
        cats = parse_categories(alimento.get("categorias", []))
        cat = cats[0] if cats else "0"
        racion = float(alimento.get("racion", 100) or 100)
        return round(max_cantidad_razonable(cat, config, racion), 1)
    except Exception:
        # Un alimento raro no puede tumbar una busqueda: sin tope se cae al tope plano.
        return None
