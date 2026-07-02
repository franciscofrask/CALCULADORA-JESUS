"""
JG12 Nutrition Chatbot - Backend
================================
Chatbot conversacional que ayuda al cliente a montar su dieta del día.
Usa Claude como interfaz y las funciones de calculator.py y calma_engine.py.
"""

import os
import json
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from llm_client import LlmChat, UserMessage

# Importar funciones del motor CALMA
from calma_engine import (
    calcular_macros_efectivos,
    calcular_macros_efectivos_alimento,
    parse_categories
)
from calculator import (
    calcular_cantidad_automatica,
    get_food_config,
    ajustar_por_unidades,
    get_categoria_principal,
    get_categorias
)
from macro_distribution import distribuir_macros


# =====================================================
# CONSTANTES
# =====================================================

SYSTEM_PROMPT = """Eres un asistente de nutrición del método 12en12 de Jesús Gallego. 
Tu trabajo es ayudar al cliente a montar su dieta del día, comida por comida.

REGLAS IMPORTANTES:
1. Sé conciso y directo. No des explicaciones largas a menos que te las pidan.
2. Cuando el cliente mencione alimentos, extrae los nombres y busca en la base de datos.
3. Siempre muestra las cantidades en gramos o unidades según corresponda.
4. Si un alimento no cuadra con los macros restantes, explica brevemente por qué y sugiere alternativas.
5. Usa un tono amigable pero profesional.
6. NO inventes alimentos ni macros. Solo usa los datos de la base de datos.

FORMATO DE RESPUESTA para comidas montadas:
- Lista cada alimento con su cantidad y macros efectivos
- Al final, muestra el total de la comida y cuánto queda del objetivo

Cuando el cliente diga qué quiere comer, SIEMPRE devuelve un JSON con los alimentos encontrados en el siguiente formato:
{
  "action": "build_meal",
  "foods_requested": ["huevos", "pavo", "pan"],
  "message": "Tu mensaje para el usuario"
}

Si necesitas preguntar algo, usa:
{
  "action": "question",
  "message": "Tu pregunta"
}

Si la comida está completa, usa:
{
  "action": "meal_complete",
  "message": "Resumen de la comida"
}

IMPORTANTE: Siempre responde en formato JSON válido."""


# =====================================================
# CLASE PRINCIPAL DEL CHATBOT
# =====================================================

class NutritionChatbot:
    """Chatbot de nutrición que usa Claude + funciones CALMA."""
    
    def __init__(self, session_id: str, db):
        """
        Inicializa el chatbot.
        
        Args:
            session_id: ID único de la sesión de chat
            db: Conexión a MongoDB
        """
        self.session_id = session_id
        self.db = db
        self.api_key = os.environ.get('OPENAI_API_KEY')
        
        # Estado de la conversación
        self.state = {
            "step": "init",  # init, config, building_meal, complete
            "tipo_dia": None,  # "entrenamiento" o "descanso"
            "num_comidas": 4,
            "momento_entreno": 1,  # Después de C1
            "opcion_peri": "intra_post",
            "single_meal": False,  # Bloque único: 1 comida con todo el día
            "macros_usuario": {
                "p_entreno": 160,
                "h_entreno": 50,
                "g_entreno": 40,
                "p_peri": 35,
                "h_peri": 15,
                "p_descanso": 140,
                "h_descanso": 40,
                "g_descanso": 40
            },
            "distribucion": None,  # Resultado de distribuir_macros
            "meal_order": [],  # Orden de comidas a montar: ["C1","Intra","Post","C2",...]
            "comida_actual": 1,  # Índice 1-based dentro de meal_order
            "comidas_completadas": {},  # {"C1": {alimentos: [...], macros: {...}}, "Intra": {...}, ...}
            "acumulado_cereales_panes": 0,
            "acumulado_frutos_secos": 0
        }
        
        # Historial de mensajes para persistencia
        self.messages_history = []
        
        # Inicializar chat con Claude
        self.chat = LlmChat(
            api_key=self.api_key,
            session_id=session_id,
            system_message=SYSTEM_PROMPT
        ).with_model("openai", os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')).with_json_mode()
    
    def set_user_macros(self, macros: dict):
        """Establece los macros del usuario desde su perfil."""
        self.state["macros_usuario"].update(macros)
    
    def configure_day(self, tipo_dia: str, num_comidas: int, momento_entreno: int = 1, opcion_peri: str = "intra_post", single_meal: bool = False):
        """
        Configura el día y calcula la distribución de macros.

        Args:
            tipo_dia: "entrenamiento" o "descanso"
            num_comidas: 3 o 4 (1 si single_meal)
            momento_entreno: 0-3 (solo para entrenamiento)
            opcion_peri: "intra_post", "solo_post", "solo_intra", "sin_peri"
            single_meal: bloque único (toda la dieta del día en 1 comida)
        """
        self.state["tipo_dia"] = tipo_dia
        self.state["num_comidas"] = 1 if single_meal else num_comidas
        self.state["momento_entreno"] = momento_entreno
        self.state["opcion_peri"] = opcion_peri
        self.state["single_meal"] = single_meal
        self.state["step"] = "building_meal"
        self.state["comida_actual"] = 1

        macros = self.state["macros_usuario"]

        # Calcular distribución
        self.state["distribucion"] = distribuir_macros(
            p_entreno=macros["p_entreno"],
            h_entreno=macros["h_entreno"],
            g_entreno=macros["g_entreno"],
            p_peri=macros["p_peri"],
            h_peri=macros["h_peri"],
            p_descanso=macros["p_descanso"],
            h_descanso=macros["h_descanso"],
            g_descanso=macros["g_descanso"],
            tipo_dia=tipo_dia,
            num_comidas=self.state["num_comidas"],
            momento_entreno=momento_entreno,
            opcion_peri=opcion_peri,
            single_meal=single_meal
        )

        # Construir el orden de comidas a montar (incluye Intra/Post en su posición)
        self.state["meal_order"] = self._build_meal_order()

        return self.state["distribucion"]

    def _build_meal_order(self) -> list:
        """Orden de comidas a montar, replicando getMealOrder del front:
        comidas principales C1..Cn con las peri (Intra/Post) intercaladas en
        la posición del momento de entreno."""
        single = self.state.get("single_meal", False)
        n = self.state["num_comidas"]
        base = ["C1"] if single else [f"C{i}" for i in range(1, n + 1)]

        if self.state["tipo_dia"] == "descanso":
            return base

        op = self.state["opcion_peri"]
        if op == "intra_post":
            peri = ["Intra", "Post"]
        elif op == "solo_post":
            peri = ["Post"]
        elif op == "solo_intra":
            peri = ["Intra"]
        else:  # sin_peri
            peri = []

        if not peri:
            return base

        order = list(base)
        # En bloque único las peri van después de la comida única; si no, en el momento de entreno.
        idx = len(base) if single else min(self.state["momento_entreno"], len(base))
        order[idx:idx] = peri
        return order

    def total_meals(self) -> int:
        """Número total de comidas a montar (principales + peri)."""
        return len(self.state["meal_order"]) or self.state["num_comidas"]

    def current_meal_key(self) -> str:
        """Clave de la comida actual (C1/Intra/Post/...) según meal_order."""
        order = self.state["meal_order"]
        idx = self.state["comida_actual"] - 1
        if 0 <= idx < len(order):
            return order[idx]
        return f"C{self.state['comida_actual']}"

    def meal_label(self, key: str) -> str:
        """Etiqueta legible de una comida para mostrar al usuario."""
        if key == "Intra":
            return "Intra-entreno"
        if key == "Post":
            return "Post-entreno"
        if key == "C1" and self.state.get("single_meal"):
            return "Comida única"
        if key.startswith("C"):
            return f"Comida {key[1:]}"
        return key

    def _target_for_key(self, key: str) -> dict:
        """Macros objetivo de una comida por su clave (principal o peri)."""
        dist = self.state["distribucion"] or {}
        if key in dist.get("comidas", {}):
            return dist["comidas"][key]
        return dist.get("periworkout", {}).get(key, {"P": 0, "H": 0, "G": 0})

    def get_current_meal_macros(self) -> dict:
        """Obtiene los macros objetivo de la comida actual."""
        if not self.state["distribucion"]:
            return {"P": 0, "H": 0, "G": 0}
        return self._target_for_key(self.current_meal_key())

    def get_remaining_macros(self) -> dict:
        """Calcula los macros restantes de la comida actual."""
        objetivo = self.get_current_meal_macros()
        completada = self.state["comidas_completadas"].get(self.current_meal_key(), {})
        macros_usados = completada.get("macros", {"P": 0, "H": 0, "G": 0})

        return {
            "P": round(objetivo["P"] - macros_usados.get("P", 0), 1),
            "H": round(objetivo["H"] - macros_usados.get("H", 0), 1),
            "G": round(objetivo["G"] - macros_usados.get("G", 0), 1)
        }
    
    async def search_foods(self, query: str, limit: int = 5) -> list:
        """
        Busca alimentos en la base de datos.
        Usa MongoDB text search para búsquedas de múltiples palabras.
        Prioriza coincidencias exactas y genéricos.
        
        Args:
            query: Texto de búsqueda (ej: "queso batido", "nueces")
            limit: Máximo de resultados
        
        Returns:
            Lista de alimentos encontrados, ordenados por relevancia
        """
        import unicodedata
        def normalize(text):
            return ''.join(
                c for c in unicodedata.normalize('NFD', text.lower())
                if unicodedata.category(c) != 'Mn'
            )
        
        query_norm = normalize(query.strip())
        
        # Mapeo de términos comunes a búsquedas específicas
        query_mappings = {
            # Proteínas
            "huevos": "huevos enteros L",
            "huevo": "huevos enteros L",
            "claras": "claras de huevo pasteurizadas",
            "clara": "claras de huevo pasteurizadas",
            "pavo": "fiambre pechuga pavo",
            "pollo": "pechuga de pollo",
            "pechuga": "pechuga de pollo",
            "pechuga de pollo": "pechuga de pollo",
            "salmon": "salmon",
            "atun": "atun",
            "dorada": "dorada",
            "merluza": "merluza",
            "sepia": "sepia",
            "gambas": "gambas",
            "whey": "whey concentrate",
            "proteina": "whey concentrate",
            
            # Hidratos
            "avena": "copos de avena",
            "copos de avena": "copos de avena",
            "arroz": "arroz blanco",
            "pan": "pan de barra",
            "pan tostado": "pan tostado",
            "patata": "patata cocida",
            "patatas": "patata cocida",
            "boniato": "boniato",
            "batata": "boniato",
            
            # Frutas
            "platano": "platano",
            "banana": "platano",
            "manzana": "manzana",
            "naranja": "naranja",
            "frambuesas": "frambuesas",
            "frambuesa": "frambuesas",
            "fresas": "fresas",
            "fresa": "fresas",
            "arandanos": "arandanos",
            
            # Verduras
            "calabacin": "calabacin",
            "lechuga": "lechuga",
            "pepino": "pepino",
            "tomate": "tomate",
            "brocoli": "brocoli",
            "espinacas": "espinacas",
            
            # Grasas
            "aceite": "aceite de oliva virgen extra",
            "aceite de oliva": "aceite de oliva virgen extra",
            "almendras": "almendras",
            "almendra": "almendras",
            "nueces": "nueces peladas",
            "nuez": "nueces peladas",
            "cacahuete": "crema de cacahuete",
            "crema de cacahuete": "crema de cacahuete natural",
            "mantequilla de cacahuete": "crema de cacahuete natural",
            "aguacate": "aguacate",
            
            # Lácteos
            "yogur": "yogur griego",
            "yogurt": "yogur griego",
            "leche": "leche",
            "queso": "queso",
            "queso batido": "queso fresco batido 0%",
            "queso fresco batido": "queso fresco batido 0%",
            
            # Legumbres
            "garbanzos": "garbanzos cocidos",
            "garbanzo": "garbanzos cocidos",
            "lentejas": "lentejas cocidas",
            "alubias": "alubias cocidas",
            
            # Tortitas de arroz
            "tortas": "tortita de arroz",
            "torta": "tortita de arroz",
            "tortitas": "tortita de arroz",
            "tortita": "tortita de arroz",
            "tortitas de arroz": "tortita de arroz",
        }
        
        # Usar mapeo si existe (buscar primero el query completo, luego palabras individuales)
        search_term = query_mappings.get(query_norm, None)
        if not search_term:
            # Intentar con palabras individuales
            words = query_norm.split()
            for w in words:
                if w in query_mappings:
                    search_term = query_mappings[w]
                    break
        if not search_term:
            search_term = query_norm
        
        search_norm = normalize(search_term)
        
        # ESTRATEGIA DE BÚSQUEDA MEJORADA:
        # 1. Si es un término específico (>2 palabras), usar regex PRIMERO
        # 2. Si no, usar text search
        # 3. Fallback a búsqueda por palabras
        
        candidates = []
        
        # Paso 1: Para términos específicos (queso fresco batido, crema de cacahuete), regex primero
        words = search_norm.split()
        if len(words) >= 2:
            regex_pattern = ".*".join(words)  # "queso.*fresco.*batido" para "queso fresco batido"
            
            try:
                regex_results = await self.db.foods.find(
                    {"nombre": {"$regex": regex_pattern, "$options": "i"}},
                    {"_id": 0}
                ).limit(50).to_list(50)
                candidates.extend(regex_results)
            except Exception:
                pass
        
        # Paso 2: MongoDB text search
        if len(candidates) < 10:
            try:
                text_results = await self.db.foods.find(
                    {"$text": {"$search": search_term}},
                    {"_id": 0, "score": {"$meta": "textScore"}}
                ).sort([("score", {"$meta": "textScore"})]).limit(50).to_list(50)
                
                # Añadir solo los que no están ya
                existing_nombres = {c.get("nombre") for c in candidates}
                for r in text_results:
                    if r.get("nombre") not in existing_nombres:
                        candidates.append(r)
            except Exception:
                pass
        
        # Paso 3: Si aún no hay suficientes, regex más simple
        if len(candidates) < 10:
            regex_pattern = ".*".join(words)
            
            try:
                regex_results = await self.db.foods.find(
                    {"nombre": {"$regex": regex_pattern, "$options": "i"}},
                    {"_id": 0}
                ).limit(50).to_list(50)
                
                existing_nombres = {c.get("nombre") for c in candidates}
                for r in regex_results:
                    if r.get("nombre") not in existing_nombres:
                        candidates.append(r)
            except Exception:
                pass
        
        # Paso 3: Si aún no hay resultados, buscar palabra por palabra
        if not candidates:
            for word in search_norm.split():
                if len(word) >= 3:
                    try:
                        word_results = await self.db.foods.find(
                            {"nombre": {"$regex": word, "$options": "i"}},
                            {"_id": 0}
                        ).limit(30).to_list(30)
                        candidates.extend(word_results)
                    except Exception:
                        pass
        
        # Puntuar candidatos por relevancia
        scored = []
        query_words = set(search_norm.split())
        
        for food in candidates:
            nombre = food.get("nombre", "")
            nombre_norm = normalize(nombre)
            nombre_words = set(nombre_norm.split())
            score = 0
            
            # Coincidencia exacta del nombre simplificado
            nombre_simple = nombre_norm.split("(")[0].strip()  # Quitar marca
            
            # Normalizar espacios en porcentajes (0 % -> 0%)
            nombre_simple_clean = nombre_simple.replace(" %", "%").replace("  ", " ")
            search_clean = search_norm.replace(" %", "%").replace("  ", " ")
            
            # Máxima prioridad: nombre empieza exactamente con la búsqueda
            if nombre_simple_clean.startswith(search_clean):
                score += 200
            elif nombre_norm.startswith(search_norm):
                score += 150
            # Alta prioridad: TODAS las palabras de búsqueda están en el nombre
            elif all(w in nombre_norm for w in query_words):
                score += 120
            # Bonificar si tiene "batido" cuando buscamos "batido"
            elif "batido" in search_norm and "batido" in nombre_norm:
                score += 110
            # Media-alta: la mayoría de palabras coinciden
            elif len(query_words & nombre_words) >= len(query_words) - 1:
                score += 100
            # Media prioridad: palabra principal al inicio
            elif any(nombre_simple.startswith(w) for w in query_words):
                score += 80
            # Baja prioridad: coincidencia parcial
            elif any(w in nombre_norm for w in query_words):
                score += 40
            else:
                continue  # No incluir si no hay coincidencia
            
            # Bonificar genéricos (sin marca)
            if "(" not in nombre:
                score += 30
            
            # Bonificar alimentos con etiqueta GEN (genérico)
            cats_str = str(food.get("categorias", ""))
            if "GEN" in cats_str:
                score += 25
            
            # Bonificar alimentos frecuentes (TOP)
            if "TOP" in cats_str:
                score += 20
            
            # Bonificar si es de una categoría "buena" (no procesados)
            if "5.2.3" in cats_str:  # Queso batido
                score += 15
            if "17.2" in cats_str:  # Frutos secos
                score += 15
            
            # Penalizar productos procesados/complejos para búsquedas simples
            if any(c in cats_str for c in ["43", "44", "49"]) and len(query_norm) < 15:
                score -= 50
            
            scored.append((score, food))
        
        # Eliminar duplicados (por id)
        seen_ids = set()
        unique_scored = []
        for score, food in scored:
            fid = food.get("id")
            if fid not in seen_ids:
                seen_ids.add(fid)
                unique_scored.append((score, food))
        
        # Ordenar por score descendente
        unique_scored.sort(key=lambda x: x[0], reverse=True)
        
        return [food for score, food in unique_scored[:limit]]
    
    def calculate_food_amount(self, alimento: dict, macros_restantes: dict) -> dict:
        """
        Calcula la cantidad óptima de un alimento sin pasarse de los macros restantes.
        
        IMPORTANTE: Aplica límites máximos RAZONABLES por categoría para que
        las cantidades tengan sentido humano (no sugerir 266g de claras).
        
        Returns:
            dict con cantidad_g, macros_efectivos, cabe, config
        """
        from calma_engine import calcular_macros_efectivos, parse_categories
        
        config = get_food_config(alimento)
        
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
        cats = parse_categories(alimento.get("categorias", []))
        cat = cats[0] if cats else "0"
        cat_sec = cats[1] if len(cats) > 1 else None
        
        # Macros restantes
        p_rest = float(macros_restantes.get("P", 0))
        h_rest = float(macros_restantes.get("H", 0))
        g_rest = float(macros_restantes.get("G", 0))
        
        # Calcular qué macros cuentan para 100g
        ef_100 = calcular_macros_efectivos(
            P_100, H_100, G_100, cat, 100.0, cat_sec,
            acumulado_cereales_panes=self.state["acumulado_cereales_panes"],
            acumulado_frutos_secos=self.state["acumulado_frutos_secos"]
        )
        
        p_ef_100 = ef_100["proteina_efectiva"]
        h_ef_100 = ef_100["hidratos_efectivos"]
        g_ef_100 = ef_100["grasa_efectiva"]
        
        # Calcular cantidad máxima por cada macro EFECTIVO
        cantidades = []
        
        if p_ef_100 > 0:
            if p_rest > 0:
                cantidades.append(p_rest / p_ef_100 * 100)
            else:
                cantidades.append(0)  # No cabe nada si P ya está cubierta
        
        if h_ef_100 > 0:
            if h_rest > 0:
                cantidades.append(h_rest / h_ef_100 * 100)
            else:
                cantidades.append(0)
        
        if g_ef_100 > 0:
            if g_rest > 0:
                cantidades.append(g_rest / g_ef_100 * 100)
            else:
                cantidades.append(0)
        
        if not cantidades:
            # Alimento sin macros efectivos (ej: lechuga)
            cantidad = config.get("minimo", 100)
            cabe = True
        else:
            cantidad = max(0, min(cantidades))
            cabe = cantidad > 0
        
        # =====================================================
        # LÍMITES MÁXIMOS RAZONABLES POR CATEGORÍA
        # Para que el chatbot sugiera cantidades humanas
        # =====================================================
        max_cantidad = self._get_max_cantidad_razonable(cat, config, racion)
        if cantidad > max_cantidad:
            cantidad = max_cantidad
        
        # Aplicar mínimo del config
        minimo = config.get("minimo", 5)
        if cantidad < minimo:
            # Si no cabe ni el mínimo, no se puede usar
            cabe = False
            cantidad = minimo  # Para mostrar la cantidad mínima
        
        # =====================================================
        # AJUSTE POR UNIDADES (fix: usar 'por_unidad' no 'tipo')
        # =====================================================
        if config.get("por_unidad", False) and cabe:
            cantidad = ajustar_por_unidades(cantidad, config)
        
        # Recalcular macros efectivos con la cantidad final
        ef_final = calcular_macros_efectivos(
            P_100, H_100, G_100, cat, cantidad, cat_sec,
            acumulado_cereales_panes=self.state["acumulado_cereales_panes"],
            acumulado_frutos_secos=self.state["acumulado_frutos_secos"]
        )
        
        # Verificar si se pasa en algún macro
        if ef_final["proteina_efectiva"] > p_rest + 4:  # margen CALMA
            cabe = False
        if ef_final["hidratos_efectivos"] > h_rest + 4:
            cabe = False
        if ef_final["grasa_efectiva"] > g_rest + 4:
            cabe = False
        
        return {
            "cantidad_g": round(cantidad, 1),
            "macros_efectivos": {
                "P": round(ef_final["proteina_efectiva"], 1),
                "H": round(ef_final["hidratos_efectivos"], 1),
                "G": round(ef_final["grasa_efectiva"], 1)
            },
            "cabe": cabe,
            "config": config,
            "nombre": alimento.get("nombre", ""),
            "unidades": alimento.get("unidades", False),
            "racion": racion
        }
    
    def _get_max_cantidad_razonable(self, cat: str, config: dict, racion: float) -> float:
        """
        Devuelve la cantidad máxima razonable para un alimento según su categoría.
        Esto evita que el bot sugiera cantidades absurdas como 266g de claras.
        
        REGLA: El chatbot debe sugerir cantidades que un humano usaría en una comida real.
        """
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
        
        # Límites por categoría (en gramos)
        limites = {
            "1.1": 150,   # Claras: máximo 150g (es más razonable)
            "1.2": 165,   # Huevos enteros: máximo 3 (55g * 3)
            "2.1": 100,   # Embutidos/Fiambres: máximo 100g
            "2.2": 200,   # Aves: máximo 200g
            "2.3": 200,   # Vacuno: máximo 200g
            "2.4": 200,   # Cerdo: máximo 200g
            "2.6": 200,   # Otras carnes: máximo 200g
            "3": 200,     # Pescado: máximo 200g
            "4": 50,      # Proteína en polvo: máximo 50g
            "5.1": 300,   # Leche: máximo 300ml
            "5.2": 250,   # Yogures: máximo 250g
            "5.3": 100,   # Quesos: máximo 100g
            "7": 100,     # Cereales: máximo 100g
            "8": 120,     # Panes: máximo 120g
            "9": 300,     # Tubérculos: máximo 300g
            "10": 200,    # Legumbres: máximo 200g
            "11": 300,    # Frutas: máximo 300g
            "13": 400,    # Verduras: máximo 400g
            "17.1": 30,   # Aceites: máximo 30g
            "17.2": 50,   # Frutos secos: máximo 50g
            "17.6": 100,  # Aguacate: máximo 100g
            "21": 150,    # Arroces: máximo 150g (en seco)
            "22": 150,    # Pasta: máximo 150g (en seco)
        }
        
        # Buscar límite para la categoría (soporta subcategorías)
        for cat_prefix, max_g in limites.items():
            if cat.startswith(cat_prefix):
                return max_g
        
        # Default: máximo 300g
        return 300
    
    def add_food_to_meal(self, alimento: dict, cantidad_g: float) -> dict:
        """
        Añade un alimento a la comida actual.
        
        Returns:
            dict con los macros añadidos
        """
        comida_num = self.current_meal_key()

        if comida_num not in self.state["comidas_completadas"]:
            self.state["comidas_completadas"][comida_num] = {
                "alimentos": [],
                "macros": {"P": 0, "H": 0, "G": 0}
            }

        # Calcular macros efectivos
        efectivos = calcular_macros_efectivos_alimento(
            alimento, cantidad_g,
            acumulado_cereales_panes=self.state["acumulado_cereales_panes"],
            acumulado_frutos_secos=self.state["acumulado_frutos_secos"]
        )
        
        # Actualizar acumulados si aplica
        cats = get_categorias(alimento)
        cat_principal = cats[0] if cats else ""
        
        if cat_principal.startswith("7") or cat_principal.startswith("8"):
            self.state["acumulado_cereales_panes"] += cantidad_g
        
        if cat_principal.startswith("17.2.1") or cat_principal.startswith("17.2.3") or cat_principal.startswith("17.2.4"):
            self.state["acumulado_frutos_secos"] += cantidad_g
        
        # Añadir a la comida
        config = get_food_config(alimento)
        food_entry = {
            "nombre": alimento.get("nombre", ""),
            "cantidad_g": cantidad_g,
            "cantidad_display": self._format_cantidad(cantidad_g, alimento, config),
            "macros": {
                "P": efectivos["P"],
                "H": efectivos["H"],
                "G": efectivos["G"]
            }
        }
        
        self.state["comidas_completadas"][comida_num]["alimentos"].append(food_entry)
        
        # Actualizar totales de la comida
        self.state["comidas_completadas"][comida_num]["macros"]["P"] += efectivos["P"]
        self.state["comidas_completadas"][comida_num]["macros"]["H"] += efectivos["H"]
        self.state["comidas_completadas"][comida_num]["macros"]["G"] += efectivos["G"]
        
        return efectivos
    
    def _format_cantidad(self, cantidad_g: float, alimento: dict, config: dict) -> str:
        """Formatea la cantidad para mostrar al usuario (nunca '0 ud')."""
        if not config.get("por_unidad", False):
            return f"{int(round(cantidad_g))}g"

        peso_unidad = config.get("peso_unidad", 0) or float(alimento.get("racion", 100) or 100)
        if peso_unidad <= 0:
            return f"{int(round(cantidad_g))}g"

        unidades = cantidad_g / peso_unidad
        permite_media = config.get("permite_media", False)
        # Redondear a unidad o media unidad (sin bajar de 0.5 ud)
        if permite_media:
            uds = round(unidades * 2) / 2
            uds = max(0.5, uds)
        else:
            uds = max(1, int(round(unidades)))
        if uds == int(uds):
            return f"{int(uds)} ud"
        return f"{uds:.1f} ud"
    
    def complete_current_meal(self) -> dict:
        """
        Marca la comida actual como completa y avanza a la siguiente.
        
        IMPORTANTE: No permite guardar comidas vacías.
        """
        comida_num = self.current_meal_key()
        resultado = self.state["comidas_completadas"].get(comida_num, {})

        # No guardar comidas vacías
        alimentos = resultado.get("alimentos", [])
        if not alimentos:
            return {
                "error": "No puedes guardar una comida vacía. Dime qué quieres comer primero.",
                "comida": comida_num,
                "vacia": True
            }

        self.state["comida_actual"] += 1

        # Verificar si todas las comidas (principales + peri) están completas
        if self.state["comida_actual"] > self.total_meals():
            self.state["step"] = "complete"

        return resultado
    
    def get_day_summary(self) -> dict:
        """Obtiene el resumen del día completo."""
        totales = {"P": 0, "H": 0, "G": 0}
        comidas_resumen = []

        for idx, key in enumerate(self.state["meal_order"], start=1):
            comida = self.state["comidas_completadas"].get(key, {"alimentos": [], "macros": {"P": 0, "H": 0, "G": 0}})
            objetivo = self._target_for_key(key)

            comidas_resumen.append({
                "numero": idx,
                "key": key,
                "nombre": self.meal_label(key),
                "alimentos": comida.get("alimentos", []),
                "macros": comida.get("macros", {"P": 0, "H": 0, "G": 0}),
                "objetivo": objetivo
            })

            totales["P"] += comida.get("macros", {}).get("P", 0)
            totales["H"] += comida.get("macros", {}).get("H", 0)
            totales["G"] += comida.get("macros", {}).get("G", 0)
        
        objetivo_total = self.state["distribucion"]["resumen"]
        totales = {k: round(v, 1) for k, v in totales.items()}

        return {
            "comidas": comidas_resumen,
            "totales": totales,
            "objetivo_total": {
                "P": objetivo_total["P_total"],
                "H": objetivo_total["H_total"],
                "G": objetivo_total["G_total"]
            },
            "diferencia": {
                "P": round(totales["P"] - objetivo_total["P_total"], 1),
                "H": round(totales["H"] - objetivo_total["H_total"], 1),
                "G": round(totales["G"] - objetivo_total["G_total"], 1)
            }
        }
    
    def export_to_diet_comidas(self) -> dict:
        """
        Transforma las comidas construidas (comidas_completadas, ya con clave de comida
        C1..Cn / Intra / Post) al objeto `comidas` que consume la pestaña de nutrición
        (db.diets), con los alimentos en el formato del front. Incluye las peri.
        """
        comidas = {}

        for key in self.state["meal_order"]:
            comida = self.state["comidas_completadas"].get(key)
            if not comida:
                continue

            alimentos_src = comida.get("alimentos", [])
            if not alimentos_src:
                continue

            alimentos = []
            for food in alimentos_src:
                # Normalizar las dos formas posibles del alimento en el estado:
                #  - _process_build_meal: {nombre, cantidad, macros, alimento:{doc}}
                #  - add_food_to_meal:    {nombre, cantidad_g, macros}
                cantidad_g = food.get("cantidad_g", food.get("cantidad", 0))
                m = food.get("macros", {})
                ali = food.get("alimento") or {}

                alimentos.append({
                    "alimento_id": ali.get("id"),
                    "nombre": food.get("nombre", ""),
                    "cantidad_g": cantidad_g,
                    "macros_efectivos": {
                        "P": m.get("P", 0),
                        "H": m.get("H", 0),
                        "G": m.get("G", 0),
                    },
                    "categorias": ali.get("categorias"),
                    "racion": ali.get("racion"),
                    "unidades": ali.get("unidades", ali.get("por_unidad", False)),
                })

            comidas[key] = {"alimentos": alimentos}

        return comidas

    def export_distribution_targets(self) -> dict:
        """
        Devuelve el overlay de objetivos por comida {mealKey: {P,H,G}} que la pestaña
        de nutrición consume como distribution_targets. Incluye las comidas principales
        (C1..Cn) y las peri (Intra/Post) si aplican.
        """
        dist = self.state.get("distribucion") or {}
        targets = dict(dist.get("comidas", {}))
        targets.update(dist.get("periworkout", {}))
        return targets

    # =====================================================
    # FLUJO DETERMINISTA (el LLM SOLO extrae alimentos)
    # =====================================================

    def set_preferences(self, food_preferences=None, avoided_categories=None, avoided_keywords=None):
        """Carga las preferencias del usuario para filtrar las sugerencias."""
        self.state["food_preferences"] = food_preferences or []
        self.state["avoided_categories"] = avoided_categories or []
        self.state["avoided_keywords"] = [k.lower() for k in (avoided_keywords or [])]

    async def extract_foods(self, text: str) -> list:
        """Usa el LLM SOLO para extraer los alimentos que menciona el usuario, con su
        cantidad si la indica. Devuelve una lista de dicts:
        [{"nombre": str, "cantidad": float|None, "unidad": "g"|"ud"|None}]."""
        prompt = (
            "Extrae TODOS los alimentos que el usuario menciona en su mensaje. "
            'Devuelve SOLO un JSON: {"foods": [{"nombre": "...", "cantidad": <número o null>, '
            '"unidad": "g"|"ud"|null}]}. '
            "Incluye SIEMPRE cada alimento mencionado, tenga o no cantidad. "
            "'nombre': el alimento en singular, sin cantidades. "
            "'cantidad': el número que el usuario indique para ese alimento, o null si no indica ninguno. "
            "'unidad': \"g\" para gramos o kilos, \"ud\" para unidades/piezas/lonchas, o null si no se indica. "
            "Interpreta números pegados o mal escritos (\"yogurt100 g\" -> yogur 100 g, "
            "\"100 de avena\" -> avena 100 g, \"4 huevos\" -> huevos 4 ud). "
            'Ejemplo: "pollo y arroz" -> {"foods": [{"nombre": "pollo", "cantidad": null, "unidad": null}, '
            '{"nombre": "arroz", "cantidad": null, "unidad": null}]}. '
            'Devuelve {"foods": []} SOLO si el mensaje no menciona ningún alimento. No añadas nada más.'
        )
        # El modelo es estocástico y a veces devuelve {"foods": []} para un alimento claro, o falla
        # de forma transitoria (timeout, 429). Reintentamos si sale VACÍO o hay excepción, para que
        # un tropiezo puntual NO haga que un alimento válido caiga en "no reconocí". Cada intento usa
        # un chat nuevo para no arrastrar el historial de un envío fallido.
        raw = []
        last_err = None
        for intento in range(2):
            chat = LlmChat(api_key=self.api_key, system_message=prompt).with_model(
                "openai", os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
            ).with_json_mode()
            try:
                resp = await chat.send_message(UserMessage(text=text))
                data = self._parse_claude_response(resp)
                raw = data.get("foods", []) if isinstance(data, dict) else []
                last_err = None
                if raw:
                    break
            except Exception as e:
                last_err = e
                import asyncio as _asyncio
                await _asyncio.sleep(0.4)
        if last_err is not None:
            print(f"[extract_foods] fallo tras reintentos: {type(last_err).__name__}: {last_err}")
            return []

        items = []
        for f in raw:
            if isinstance(f, str):
                nombre = f.strip()
                if nombre:
                    items.append({"nombre": nombre, "cantidad": None, "unidad": None})
                continue
            if not isinstance(f, dict):
                continue
            nombre = (f.get("nombre") or "").strip()
            if not nombre:
                continue
            cant = f.get("cantidad")
            try:
                cant = float(cant) if cant is not None else None
            except (TypeError, ValueError):
                cant = None
            unidad = f.get("unidad")
            if unidad == "kg" and cant is not None:
                cant *= 1000
                unidad = "g"
            if unidad not in ("g", "ud"):
                unidad = None
            items.append({"nombre": nombre, "cantidad": cant, "unidad": unidad})
        return items

    def get_day_overview(self) -> dict:
        """Objetivo total del día + consumido + restante, y la comida actual."""
        dist = self.state.get("distribucion") or {}
        resumen = dist.get("resumen", {})
        consumido = {"P": 0.0, "H": 0.0, "G": 0.0}
        for comida in self.state["comidas_completadas"].values():
            m = comida.get("macros", {})
            consumido["P"] += m.get("P", 0)
            consumido["H"] += m.get("H", 0)
            consumido["G"] += m.get("G", 0)
        objetivo = {
            "P": resumen.get("P_total", 0),
            "H": resumen.get("H_total", 0),
            "G": resumen.get("G_total", 0),
        }
        key = self.current_meal_key()
        return {
            "objetivo": objetivo,
            "consumido": {k: round(v, 1) for k, v in consumido.items()},
            "restante": {k: round(objetivo[k] - consumido[k], 1) for k in ("P", "H", "G")},
            "comida_key": key,
            "comida_nombre": self.meal_label(key),
            "comida_objetivo": self.get_current_meal_macros(),
            "comida_restante": self.get_remaining_macros(),
            "completas": self.state["comida_actual"] - 1,
            "total_comidas": self.total_meals(),
            "meals": self.get_meals_status(),
        }

    def get_meals_status(self) -> list:
        """Estado de TODAS las comidas del día (para responder 'qué me falta y dónde'
        y para el navegador de comidas)."""
        out = []
        for idx, key in enumerate(self.state.get("meal_order", []), start=1):
            obj = self._target_for_key(key)
            comida = self.state["comidas_completadas"].get(key, {})
            act = comida.get("macros", {"P": 0, "H": 0, "G": 0})
            rem = {m: round(obj.get(m, 0) - act.get(m, 0), 1) for m in ("P", "H", "G")}
            out.append({
                "idx": idx,
                "key": key,
                "nombre": self.meal_label(key),
                "objetivo": obj,
                "actual": {m: round(act.get(m, 0), 1) for m in ("P", "H", "G")},
                "restante": rem,
                "cuadrado": all(abs(rem[m]) <= 4 for m in ("P", "H", "G")),
                "tiene_alimentos": len(comida.get("alimentos", [])) > 0,
                "es_actual": idx == self.state["comida_actual"],
            })
        return out

    def go_to_meal(self, idx: int) -> bool:
        """Salta a una comida concreta (para editar una ya guardada o volver atrás)."""
        if 1 <= int(idx) <= self.total_meals():
            self.state["comida_actual"] = int(idx)
            self.state["step"] = "building_meal"
            return True
        return False

    def clear_meal(self, idx=None):
        """Vacía TODA una comida (sus alimentos). Si `idx` viene, navega a esa comida y la vacía;
        si no, vacía la actual. Devuelve el nombre de la comida vaciada, o None si el idx no es válido."""
        if idx is not None:
            try:
                if not self.go_to_meal(int(idx)):
                    return None
            except (TypeError, ValueError):
                return None
        key = self.current_meal_key()
        self.state["comidas_completadas"][key] = {"alimentos": [], "macros": {"P": 0, "H": 0, "G": 0}}
        return self.meal_label(key)

    def remove_food_at(self, food_index: int) -> bool:
        """Quita un alimento de la comida actual por su posición y recalcula los macros."""
        key = self.current_meal_key()
        comida = self.state["comidas_completadas"].get(key)
        if not comida or food_index < 0 or food_index >= len(comida.get("alimentos", [])):
            return False
        f = comida["alimentos"].pop(food_index)
        m = f.get("macros", {})
        for k in ("P", "H", "G"):
            comida["macros"][k] = round(comida["macros"][k] - m.get(k, 0), 1)
        return True

    # Palabras a ignorar al emparejar el nombre de un alimento dentro de una orden
    # ("borra las aceitunas", "pon 80 g de aguacate"): verbos, unidades y relleno.
    _MATCH_STOPWORDS = {
        "borra", "borrar", "borrame", "quita", "quitar", "quitame", "quitale", "elimina",
        "eliminar", "saca", "sacar", "sacame", "retira", "retirar", "remueve", "remover",
        "pon", "poner", "ponme", "pongo", "cambia", "cambiar", "cambiame", "ajusta", "ajustar",
        "sube", "subir", "baja", "bajar", "deja", "dejar", "mejor", "vez", "lugar", "en",
        "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "y", "e", "con",
        "sin", "g", "gr", "grs", "gramos", "kg", "kilo", "kilos", "ud", "uds", "unidad",
        "unidades", "por", "favor", "esta", "este", "esa", "ese", "comida", "a", "al",
    }

    # Términos de macro genérico: cuando el usuario pide "una grasa"/"algo de proteína" en vez
    # de un alimento concreto, el asistente elige uno real de ese macro.
    GENERIC_MACRO = {
        "grasa": "G", "grasas": "G",
        "proteina": "P", "proteinas": "P",
        "hidrato": "H", "hidratos": "H", "carbohidrato": "H", "carbohidratos": "H",
        "carbo": "H", "carbos": "H", "carbohidrato de carbono": "H",
    }

    @staticmethod
    def _norm_text(s: str) -> str:
        import unicodedata
        s = (s or "").lower()
        return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

    def _match_meal_food_index(self, name: str) -> int:
        """Índice del alimento de la comida actual que mejor coincide con `name`, o -1."""
        key = self.current_meal_key()
        comida = self.state["comidas_completadas"].get(key)
        if not comida or not comida.get("alimentos"):
            return -1
        q_tokens = [t for t in re.findall(r"\w+", self._norm_text(name))
                    if t not in self._MATCH_STOPWORDS and len(t) > 1 and not t.isdigit()]
        if not q_tokens:
            return -1
        best_idx, best_score = -1, 0
        for i, f in enumerate(comida["alimentos"]):
            fn = self._norm_text(f.get("nombre", ""))
            score = sum(1 for t in q_tokens if t in fn)
            if score > best_score:
                best_score, best_idx = score, i
        return best_idx if best_score > 0 else -1

    def remove_food_by_name(self, name: str):
        """Quita de la comida actual el alimento que mejor coincide con `name`
        (p.ej. "borra las aceitunas negras"). Devuelve el alimento quitado o None."""
        idx = self._match_meal_food_index(name)
        if idx < 0:
            return None
        comida = self.state["comidas_completadas"][self.current_meal_key()]
        removed = comida["alimentos"][idx]
        self.remove_food_at(idx)
        return removed

    def _update_food_at(self, key: str, idx: int, alimento: dict, cantidad_g: float, macros: dict):
        """Cambia la cantidad/macros de un alimento ya presente en la comida y ajusta los totales."""
        comida = self.state["comidas_completadas"][key]
        entry = comida["alimentos"][idx]
        old = entry.get("macros", {})
        for k in ("P", "H", "G"):
            comida["macros"][k] = round(comida["macros"][k] - old.get(k, 0) + macros.get(k, 0), 1)
        config = get_food_config(alimento)
        entry["cantidad"] = cantidad_g
        entry["cantidad_g"] = cantidad_g
        entry["cantidad_display"] = self._format_cantidad(cantidad_g, alimento, config)
        entry["macros"] = macros
        entry["alimento"] = alimento
        return entry["cantidad_display"]

    async def set_food_quantity(self, name: str, cantidad: float = None, unidad: str = None) -> dict:
        """Fija manualmente la cantidad de un alimento, con paridad con la calculadora: NO topa
        por los macros restantes (permite SOBREPASAR el objetivo). Si el alimento ya está en la
        comida, actualiza su cantidad; si no, lo añade a la cantidad indicada.

        `unidad`: "g" (gramos), "ud" (unidades) o None (se resuelve según el alimento:
        unidades si es un alimento contable, gramos en caso contrario)."""
        key = self.current_meal_key()
        idx = self._match_meal_food_index(name)
        if idx >= 0:
            alimento = self.state["comidas_completadas"][key]["alimentos"][idx].get("alimento")
            if not alimento:
                matches = await self.search_foods(name, limit=1)
                alimento = matches[0] if matches else None
        else:
            matches = await self.search_foods(name, limit=1)
            alimento = matches[0] if matches else None
        if not alimento:
            return {"ok": False, "nombre": name}
        if cantidad is None or cantidad <= 0:
            return {"ok": False, "nombre": alimento.get("nombre", name)}
        u = unidad
        if u == "kg":
            cantidad *= 1000
            u = "g"
        if u not in ("g", "ud"):
            u = "ud" if alimento.get("unidades") else "g"
        if u == "ud":
            racion = float(alimento.get("racion") or 100) or 100.0
            cantidad_g = cantidad * racion
        else:
            cantidad_g = cantidad
        macros = self._macros_at(alimento, cantidad_g)
        if idx >= 0:
            display = self._update_food_at(key, idx, alimento, cantidad_g, macros)
        else:
            self._ensure_meal(key)
            display = self._append_food(key, alimento, cantidad_g, macros)
        return {"ok": True, "nombre": alimento.get("nombre"),
                "cantidad_display": display, "macros": macros}

    def _size_food(self, alimento: dict, restante: dict):
        """Dimensiona un alimento contra los macros restantes con el MISMO motor que la
        calculadora (calma_suggest). Devuelve (cantidad_g, macros{P,H,G}) o None si no cabe."""
        import copy, math
        from calma_suggest import ajustar_cantidad, macros_at, aplicar_regla_macros, cantidad_minima

        a = copy.deepcopy(alimento)
        aplicar_regla_macros(a)
        remaining = {
            "proteinas": float(restante.get("P", 0)),
            "hidratos": float(restante.get("H", 0)),
            "grasas": float(restante.get("G", 0)),
        }
        cant = ajustar_cantidad(a, remaining)
        if cant is None:
            return None
        if math.isinf(cant):
            cant = cantidad_minima(a)  # alimento libre (sin macros que cuenten)
        if cant <= 0:
            return None
        es_unidad = bool(a.get("unidades"))
        racion = float(a.get("racion") or 100) or 100.0
        cantidad_g = (cant * racion) if es_unidad else cant
        m = macros_at(a, cant)
        macros = {"P": round(m["proteinas"], 1), "H": round(m["hidratos"], 1), "G": round(m["grasas"], 1)}
        return cantidad_g, macros

    def _ensure_meal(self, key: str):
        if key not in self.state["comidas_completadas"]:
            self.state["comidas_completadas"][key] = {"alimentos": [], "macros": {"P": 0, "H": 0, "G": 0}}

    def _append_food(self, key: str, alimento: dict, cantidad_g: float, macros: dict):
        self._ensure_meal(key)
        config = get_food_config(alimento)
        display = self._format_cantidad(cantidad_g, alimento, config)
        self.state["comidas_completadas"][key]["alimentos"].append({
            "nombre": alimento.get("nombre", ""),
            "cantidad": cantidad_g,
            "cantidad_g": cantidad_g,
            "cantidad_display": display,
            "macros": macros,
            "alimento": alimento,
        })
        mm = self.state["comidas_completadas"][key]["macros"]
        mm["P"] = round(mm["P"] + macros["P"], 1)
        mm["H"] = round(mm["H"] + macros["H"], 1)
        mm["G"] = round(mm["G"] + macros["G"], 1)
        return display

    def _meal_response(self, foods_added: list, foods_not_found: list) -> dict:
        key = self.current_meal_key()
        comida = self.state["comidas_completadas"].get(key, {})
        restante = self.get_remaining_macros()
        cuadrado = all(abs(restante[m]) <= 4 for m in ("P", "H", "G"))
        return {
            "action": "meal_updated",
            "foods_added": foods_added,
            "foods_not_found": foods_not_found,
            "meal_status": {
                "comida": self.state["comida_actual"],
                "comida_key": key,
                "comida_nombre": self.meal_label(key),
                "objetivo": self.get_current_meal_macros(),
                "actual": comida.get("macros", {"P": 0, "H": 0, "G": 0}),
                "restante": restante,
                "alimentos": comida.get("alimentos", []),
                "cuadrado": cuadrado,
            },
            "day_overview": self.get_day_overview(),
        }

    def _macros_at(self, alimento: dict, cantidad_g: float) -> dict:
        """Macros efectivos de un alimento a una cantidad, con el MISMO motor que la
        calculadora (calma_suggest), para paridad de los números mostrados."""
        import copy
        from calma_suggest import macros_at, aplicar_regla_macros
        a = copy.deepcopy(alimento)
        aplicar_regla_macros(a)
        racion = float(a.get("racion") or 100) or 100.0
        cant = (cantidad_g / racion) if bool(a.get("unidades")) else cantidad_g
        m = macros_at(a, cant)
        return {"P": round(m["proteinas"], 1), "H": round(m["hidratos"], 1), "G": round(m["grasas"], 1)}

    async def add_foods(self, items: list) -> dict:
        """Añade a la comida actual los alimentos extraídos del mensaje.

        `items`: [{"nombre", "cantidad", "unidad"}].
        - Los que traen cantidad EXPLÍCITA se fijan manualmente (se respeta el número aunque
          sobrepase el objetivo, como en la calculadora).
        - Los que NO traen cantidad se dimensionan/reparten automáticamente contra lo que
          queda: 1 alimento con `_size_food`; varios, equilibrado con `meal_builder`.
        Los macros mostrados se recalculan con el motor de la calculadora (paridad).
        """
        key = self.current_meal_key()
        added, not_found = [], []

        def tiene_cantidad(it):
            return it.get("cantidad") is not None and it.get("cantidad") > 0

        # Separar peticiones de macro genérico ("una grasa", "algo de proteína"): no son un
        # alimento concreto; el asistente elige uno real de ese macro que quepa (paso 3).
        generic_macros = []
        real_items = []
        for it in items:
            gm = self.GENERIC_MACRO.get(self._norm_text(it.get("nombre", "")))
            if gm and not tiene_cantidad(it):
                generic_macros.append(gm)
            else:
                real_items.append(it)

        explicit = [it for it in real_items if tiene_cantidad(it)]
        auto_names = [it["nombre"] for it in real_items if not tiene_cantidad(it)]

        # ── 1) Cantidades explícitas: una a una, manual (sin tope) ──
        for it in explicit:
            res = await self.set_food_quantity(it["nombre"], cantidad=it["cantidad"], unidad=it.get("unidad"))
            if res.get("ok"):
                added.append({"nombre": res["nombre"], "cantidad_display": res["cantidad_display"],
                              "macros": res["macros"]})
            else:
                not_found.append({"buscado": it["nombre"], "razon": "No encontrado en la base de datos"})

        # ── 2) Sin cantidad: auto-dimensionado contra lo que queda tras los explícitos ──
        if len(auto_names) == 1:
            restante = self.get_remaining_macros()
            matches = await self.search_foods(auto_names[0], limit=1)
            if not matches:
                not_found.append({"buscado": auto_names[0], "razon": "No encontrado en la base de datos"})
            else:
                alimento = matches[0]
                sized = self._size_food(alimento, restante)
                if not sized:
                    not_found.append({"buscado": auto_names[0], "encontrado": alimento.get("nombre"),
                                      "razon": "No cabe en lo que queda de esta comida"})
                else:
                    cantidad_g, macros = sized
                    display = self._append_food(key, alimento, cantidad_g, macros)
                    added.append({"nombre": alimento.get("nombre"), "cantidad_display": display, "macros": macros})
        elif len(auto_names) >= 2:
            from meal_builder import build_meal
            restante = self.get_remaining_macros()
            result = await build_meal(self.db, auto_names, restante, self.search_foods)
            not_found.extend(result.get("foods_not_found", []))
            for f in result["foods_added"]:
                cantidad_g = f.get("cantidad", f.get("cantidad_g", 0))
                matches = await self.search_foods(f["nombre"], limit=1)
                alimento = matches[0] if matches else {"nombre": f["nombre"], "racion": 100}
                macros = self._macros_at(alimento, cantidad_g) if matches else f.get("macros", {"P": 0, "H": 0, "G": 0})
                display = self._append_food(key, alimento, cantidad_g, macros)
                added.append({"nombre": f["nombre"], "cantidad_display": display, "macros": macros})

        # ── 3) Macros genéricos: elegir un alimento real de ese macro que quepa ──
        for gm in generic_macros:
            picked = await self._pick_food_for_macro(gm)
            macro_lbl = {"P": "proteína", "H": "hidratos", "G": "grasa"}[gm]
            if picked:
                a, cantidad_g, macros = picked
                display = self._append_food(key, a, cantidad_g, macros)
                added.append({"nombre": a.get("nombre"), "cantidad_display": display, "macros": macros})
            else:
                not_found.append({"buscado": f"algo de {macro_lbl}",
                                  "razon": f"No encontré un alimento de {macro_lbl} que quepa en lo que queda"})

        return self._meal_response(added, not_found)

    async def _pick_food_for_macro(self, macro: str):
        """Elige un alimento real de un macro genérico ('una grasa', 'algo de proteína') que
        quepa en lo que falta de la comida, respetando lo evitado. Prioriza el que más aporta
        de ese macro. Devuelve (alimento, cantidad_g, macros) o None."""
        from routes.calculator import AVOIDABLE_PREFIXES
        from calculator import (
            CATS_PROTEINA_PURAS, CATS_HIDRATOS, CATS_GRASAS, CATS_CUADRAR_GRASAS,
            filtrar_por_tipo_comida, cat_in_list, get_categoria_principal,
        )
        restante = self.get_remaining_macros()
        key = self.current_meal_key()
        es_peri = key in ("Intra", "Post")
        cats_map = {
            "P": CATS_PROTEINA_PURAS,
            "H": CATS_HIDRATOS,
            "G": CATS_GRASAS + CATS_CUADRAR_GRASAS,
        }
        cats = cats_map.get(macro, [])

        avoid_prefixes = set()
        for cid in self.state.get("avoided_categories", []):
            avoid_prefixes.update(AVOIDABLE_PREFIXES.get(cid, []))
        avoid_keywords = self.state.get("avoided_keywords", [])

        def cat_hit(cats_field, prefixes):
            for c in parse_categories(cats_field):
                for p in prefixes:
                    if c == p or c.startswith(p + "."):
                        return True
            return False

        all_foods = await self.db.foods.find({}, {"_id": 0}).to_list(3500)
        if es_peri:
            pool = filtrar_por_tipo_comida(all_foods, "intra" if key == "Intra" else "post")
        else:
            pool = [a for a in all_foods if cat_in_list(get_categoria_principal(a), cats)]
        pool = [a for a in pool
                if not any(kw in (a.get("nombre", "") or "").lower() for kw in avoid_keywords)
                and not (avoid_prefixes and cat_hit(a.get("categorias"), avoid_prefixes))]

        best = None
        for a in pool:
            sized = self._size_food(a, restante)
            if not sized:
                continue
            cantidad_g, macros = sized
            if macros.get(macro, 0) <= 0:
                continue
            if best is None or macros[macro] > best[0]:
                best = (macros[macro], a, cantidad_g, macros)
        if best is None:
            return None
        _, a, cantidad_g, macros = best
        return a, cantidad_g, macros

    async def rebalance_current_meal(self) -> dict:
        """Recalcula las cantidades de los alimentos que YA están en la comida para acercarse
        lo máximo posible a su objetivo (reparto equilibrado, respetando mínimos). Es lo que
        hace 'cuadra las cantidades': no cambia los alimentos, solo sus gramos."""
        key = self.current_meal_key()
        comida = self.state["comidas_completadas"].get(key, {})
        names = [a.get("nombre") for a in comida.get("alimentos", []) if a.get("nombre")]
        if not names:
            return {"action": "no_foods",
                    "message": "No hay alimentos en esta comida para cuadrar. Añade alguno primero.",
                    "day_overview": self.get_day_overview()}

        objetivo = self.get_current_meal_macros()
        target = {"P": objetivo.get("P", 0), "H": objetivo.get("H", 0), "G": objetivo.get("G", 0)}
        # Vaciar la comida y reconstruir con los mismos alimentos, cuadrando al objetivo.
        self.state["comidas_completadas"][key] = {"alimentos": [], "macros": {"P": 0, "H": 0, "G": 0}}
        added, not_found = [], []
        if len(names) == 1:
            matches = await self.search_foods(names[0], limit=1)
            if matches:
                sized = self._size_food(matches[0], target)
                if sized:
                    cantidad_g, macros = sized
                    display = self._append_food(key, matches[0], cantidad_g, macros)
                    added.append({"nombre": matches[0].get("nombre"), "cantidad_display": display, "macros": macros})
                else:
                    not_found.append({"buscado": names[0], "razon": "No cabe en el objetivo"})
        else:
            from meal_builder import build_meal
            result = await build_meal(self.db, names, target, self.search_foods)
            not_found.extend(result.get("foods_not_found", []))
            for f in result["foods_added"]:
                cantidad_g = f.get("cantidad", f.get("cantidad_g", 0))
                matches = await self.search_foods(f["nombre"], limit=1)
                alimento = matches[0] if matches else {"nombre": f["nombre"], "racion": 100}
                macros = self._macros_at(alimento, cantidad_g) if matches else f.get("macros", {"P": 0, "H": 0, "G": 0})
                display = self._append_food(key, alimento, cantidad_g, macros)
                added.append({"nombre": f["nombre"], "cantidad_display": display, "macros": macros})

        resp = self._meal_response(added, not_found)
        resp["message"] = "Cuadré las cantidades lo mejor posible con estos alimentos."
        return resp

    async def add_food_by_id(self, alimento_id) -> dict:
        """Añade un alimento concreto por id (cuando el usuario toca una sugerencia)."""
        key = self.current_meal_key()
        alimento = await self.db.foods.find_one({"id": alimento_id}, {"_id": 0})
        if not alimento:
            return self._meal_response([], [{"buscado": str(alimento_id), "razon": "No encontrado"}])
        sized = self._size_food(alimento, self.get_remaining_macros())
        if not sized:
            return self._meal_response([], [{"buscado": alimento.get("nombre"), "razon": "No cabe"}])
        cantidad_g, macros = sized
        display = self._append_food(key, alimento, cantidad_g, macros)
        return self._meal_response([{"nombre": alimento.get("nombre"), "cantidad_display": display, "macros": macros}], [])

    async def suggest_foods_for_current_meal(self, limit: int = 6) -> dict:
        """Sugiere alimentos sueltos POR FASES, igual que la calculadora:
        primero PROTEÍNA (pollo, carnes, huevos, pescados…), luego HIDRATOS (arroz,
        pasta, cereales…), luego GRASA (aceites, frutos secos…). En las comidas peri
        (Intra/Post) usa solo las categorías permitidas de peri. Respeta preferencias
        y alimentos evitados, y añade variedad para que no salga siempre lo mismo."""
        import random
        from routes.calculator import AVOIDABLE_PREFIXES
        from calculator import (
            CATS_PROTEINA_PURAS, CATS_HIDRATOS, CATS_GRASAS, CATS_CUADRAR_GRASAS,
            filtrar_por_tipo_comida, cat_in_list, get_categoria_principal,
        )

        restante = self.get_remaining_macros()
        if all(abs(restante[m]) <= 4 for m in ("P", "H", "G")):
            return {"action": "suggestions", "suggestions": [],
                    "message": "Esta comida ya está cuadrada. Pulsa \"Guardar y siguiente\".",
                    "day_overview": self.get_day_overview()}

        # Fase según el macro que más falta (orden CALMA: proteína → hidratos → grasa)
        if restante["P"] > 4:
            fase, driver = "proteina", "P"
        elif restante["H"] > 4:
            fase, driver = "hidratos", "H"
        else:
            fase, driver = "grasa", "G"

        key = self.current_meal_key()
        es_peri = key in ("Intra", "Post")

        # Filtros de preferencias / evitados
        avoid_prefixes, pref_prefixes = set(), set()
        for cid in self.state.get("avoided_categories", []):
            avoid_prefixes.update(AVOIDABLE_PREFIXES.get(cid, []))
        for cid in self.state.get("food_preferences", []):
            pref_prefixes.update(AVOIDABLE_PREFIXES.get(cid, []))
        avoid_keywords = self.state.get("avoided_keywords", [])

        def cat_hit(cats_field, prefixes):
            for c in parse_categories(cats_field):
                for p in prefixes:
                    if c == p or c.startswith(p + "."):
                        return True
            return False

        all_foods = await self.db.foods.find({}, {"_id": 0}).to_list(3500)

        # Universo según el tipo de comida / la fase
        if es_peri:
            pool = filtrar_por_tipo_comida(all_foods, "intra" if key == "Intra" else "post")
        else:
            cats = {
                "proteina": CATS_PROTEINA_PURAS,
                "hidratos": CATS_HIDRATOS,
                "grasa": CATS_GRASAS + CATS_CUADRAR_GRASAS,
            }[fase]
            pool = [a for a in all_foods if cat_in_list(get_categoria_principal(a), cats)]

        # Quitar SOLO los evitados (las categorías de la fase ya acotan; los preferidos
        # solo priorizan, no excluyen - si el usuario no marcó "arroces" igual debe ver arroz)
        pool = [a for a in pool
                if not any(kw in (a.get("nombre", "") or "").lower() for kw in avoid_keywords)
                and not (avoid_prefixes and cat_hit(a.get("categorias"), avoid_prefixes))]

        # Dimensionar; agrupar por TIPO de alimento (categoría a 2 niveles) para diversificar
        from collections import defaultdict
        buckets = defaultdict(list)  # coarse_cat -> [(aporte, es_pref, item)]
        for a in pool:
            sized = self._size_food(a, restante)
            if not sized:
                continue
            cantidad_g, macros = sized
            if macros[driver] <= 0:
                continue
            cats = parse_categories(a.get("categorias"))
            coarse = ".".join(cats[0].split(".")[:2]) if cats else "?"
            es_pref = bool(pref_prefixes and cat_hit(a.get("categorias"), pref_prefixes))
            config = get_food_config(a)
            buckets[coarse].append((macros[driver], es_pref, {
                "alimento_id": a.get("id"),
                "nombre": a.get("nombre"),
                "cantidad_display": self._format_cantidad(cantidad_g, a, config),
                "macros": macros,
            }))

        # Dentro de cada tipo: mejores primero, baraja los top para variedad
        for b in buckets:
            buckets[b].sort(key=lambda x: -x[0])
            head = buckets[b][:5]
            random.shuffle(head)
            buckets[b] = head

        # Orden de tipos: los que tienen alimentos preferidos primero, luego por mejor aporte
        cat_order = sorted(
            buckets.keys(),
            key=lambda b: (0 if any(p for _, p, _ in buckets[b]) else 1, -buckets[b][0][0])
        )

        # Round-robin entre tipos → variedad (pollo, carne, huevo, pescado…)
        chosen = []
        while len(chosen) < limit and any(buckets[b] for b in cat_order):
            for b in cat_order:
                if buckets[b]:
                    chosen.append(buckets[b].pop(0)[2])
                    if len(chosen) >= limit:
                        break

        fase_lbl = {"proteina": "proteína", "hidratos": "hidratos", "grasa": "grasa"}[fase]
        return {
            "action": "suggestions",
            "fase": fase,
            "message": f"Toca un alimento de {fase_lbl} para añadirlo (es lo que más te falta):",
            "suggestions": chosen,
            "day_overview": self.get_day_overview(),
        }

    def _que_cuenta(self, alimento: dict):
        """Determinista: qué macros CUENTAN en CALMA para el alimento (según su categoría),
        sus macros brutos y su categoría principal. Mismo motor que la calculadora.
        Devuelve (cuenta{P,H,G bool}, brutos{P,H,G}, categoria, base_lbl)."""
        import copy
        from calma_suggest import aplicar_regla_macros, macros_at
        try:
            from calculator import get_categoria_principal
            cat = get_categoria_principal(alimento)
        except Exception:
            cats = alimento.get("categorias") or []
            cat = cats[0] if cats else ""
        a = copy.deepcopy(alimento)
        aplicar_regla_macros(a)
        es_unidad = bool(alimento.get("unidades"))
        cant = 1.0 if es_unidad else 100.0
        m = macros_at(a, cant)
        cuenta = {"P": m["proteinas"] > 0.01, "H": m["hidratos"] > 0.01, "G": m["grasas"] > 0.01}
        brutos = {
            "P": round(float(alimento.get("proteinas") or 0), 1),
            "H": round(float(alimento.get("hidratos") or 0), 1),
            "G": round(float(alimento.get("grasas") or 0), 1),
        }
        return cuenta, brutos, cat, ("por unidad" if es_unidad else "por 100 g")

    async def answer_question(self, text: str) -> dict:
        """Responde una pregunta de nutrición/CALMA del cliente. Los HECHOS (qué macros
        cuentan para un alimento, contexto del día) los calcula el código; el LLM solo redacta."""
        food_facts = ""
        try:
            items = await self.extract_foods(text)
        except Exception:
            items = []
        if items:
            matches = await self.search_foods(items[0]["nombre"], limit=1)
            if matches:
                a = matches[0]
                cuenta, brutos, cat, base = self._que_cuenta(a)
                si = lambda b: "sí" if b else "no"
                food_facts = (
                    f"Alimento: {a.get('nombre')} (categoría CALMA {cat}). "
                    f"Macros {base}: P={brutos['P']}, H={brutos['H']}, G={brutos['G']}. "
                    f"En CALMA cuenta -> Proteína: {si(cuenta['P'])}, "
                    f"Hidratos: {si(cuenta['H'])}, Grasa: {si(cuenta['G'])}."
                )
        ov = self.get_day_overview()
        lines = []
        if ov:
            obj = ov.get("objetivo", {}); con = ov.get("consumido", {}); rem = ov.get("restante", {})
            lines.append(
                f"Día de {self.state.get('tipo_dia', '')}. "
                f"Objetivo total del día: P={obj.get('P', 0)}g H={obj.get('H', 0)}g G={obj.get('G', 0)}g. "
                f"Consumido: P={con.get('P', 0)}g H={con.get('H', 0)}g G={con.get('G', 0)}g. "
                f"Falta en el día: P={rem.get('P', 0)}g H={rem.get('H', 0)}g G={rem.get('G', 0)}g."
            )
            lines.append("Desglose por comidas:")
            for m in ov.get("meals", []):
                o = m.get("objetivo", {}); r = m.get("restante", {})
                if m.get("cuadrado"):
                    estado = "cuadrada"
                elif not m.get("tiene_alimentos"):
                    estado = "vacía"
                else:
                    estado = "incompleta"
                marca = " [comida actual]" if m.get("es_actual") else ""
                comida = self.state["comidas_completadas"].get(m["key"], {})
                foods = ", ".join(
                    f"{a.get('nombre')} {a.get('cantidad_display', '')}".strip()
                    for a in comida.get("alimentos", [])
                ) or "sin alimentos"
                lines.append(
                    f"- {m['nombre']}{marca}: objetivo P={o.get('P', 0)} H={o.get('H', 0)} G={o.get('G', 0)}; "
                    f"falta P={r.get('P', 0)} H={r.get('H', 0)} G={r.get('G', 0)}; {estado}. Contiene: {foods}."
                )
        ctx = "\n".join(lines)
        system = (
            "Eres el asistente del método 12en12 (CALMA) de nutrición. Respondes las dudas del "
            "cliente de forma breve y clara, en español neutro (sin voseo), en 2-4 frases. "
            "ÁMBITO: solo respondes sobre nutrición, dieta, macros, alimentos, entrenamiento y el "
            "uso de esta app. Si la pregunta NO trata de eso (p.ej. política, geografía, noticias, "
            "cultura general), NO la respondas ni la mezcles con nutrición: di brevemente que solo "
            "puedes ayudar con su dieta y su método, y ofrécete a seguir con la comida. "
            "NO inventes números: usa solo los DATOS que te doy (objetivo del día, consumido, y el "
            "desglose por comidas con lo que falta en cada una). "
            "Si preguntan en qué comida meter un macro o un alimento, mira el desglose y recomienda "
            "la(s) comida(s) que aún necesitan ese macro (las de mayor 'falta' de ese macro), citando "
            "su nombre. "
            "Reglas CALMA para explicar: cada alimento se clasifica por su categoría principal y "
            "solo cuentan los macros coherentes con ella. Fuentes de hidratos (arroz, pasta, pan, "
            "patata, avena): cuentan SIEMPRE sus hidratos; su proteína solo cuenta si es sustancial "
            "(más de un tercio de sus hidratos), por eso la poca proteína del arroz no cuenta. "
            "Fuentes de proteína (pollo, huevo, pescado, carne): cuenta su proteína (y su grasa si es "
            "alta). Fuentes de grasa (aceite, aguacate, frutos secos, aceitunas): cuenta su grasa. "
            "La idea es cubrir cada macro con el alimento idóneo, no sumar 'relleno' de baja calidad."
        )
        user_msg = f"Pregunta del cliente: {text}\n\nDATOS:\n{food_facts}\n{ctx}".strip()
        chat = LlmChat(api_key=self.api_key, system_message=system).with_model(
            "openai", os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        )
        try:
            answer = await chat.send_message(UserMessage(text=user_msg))
        except Exception:
            answer = ("En CALMA cada alimento cuenta según su categoría principal: las fuentes de "
                      "hidratos aportan hidratos, las de proteína aportan proteína y las de grasa "
                      "aportan grasa, para cubrir cada macro con el alimento idóneo. ¿Sobre qué "
                      "alimento o comida quieres saber?")
        answer = (answer or "").strip()
        if not answer:
            answer = ("Solo puedo ayudarte con tu dieta y el método 12en12. ¿Seguimos con tu comida?")
        return {"action": "message", "message": answer, "day_overview": ov}

    @staticmethod
    def _normalize_food_items(raw) -> list:
        """Normaliza una lista de alimentos del LLM a [{nombre, cantidad, unidad}]."""
        items = []
        for f in raw or []:
            if isinstance(f, str):
                nombre = f.strip()
                if nombre:
                    items.append({"nombre": nombre, "cantidad": None, "unidad": None})
                continue
            if not isinstance(f, dict):
                continue
            nombre = (f.get("nombre") or "").strip()
            if not nombre:
                continue
            cant = f.get("cantidad")
            try:
                cant = float(cant) if cant is not None else None
            except (TypeError, ValueError):
                cant = None
            unidad = f.get("unidad")
            if unidad == "kg" and cant is not None:
                cant *= 1000
                unidad = "g"
            if unidad not in ("g", "ud"):
                unidad = None
            items.append({"nombre": nombre, "cantidad": cant, "unidad": unidad})
        return items

    async def understand(self, text: str) -> dict:
        """Router con LLM: clasifica la INTENCIÓN del mensaje y extrae lo necesario. El LLM solo
        interpreta el lenguaje; el código hace toda la matemática. Devuelve
        {intent, foods, remove, goto}."""
        prompt = (
            "Eres el router de un asistente de nutrición. El usuario está montando una comida. "
            "Clasifica su mensaje en UNA intención y extrae lo necesario. Devuelve SOLO JSON: "
            '{"intent": "add|suggest|complete|remove|clear|status|summary|rebalance|goto|question|none", '
            '"foods": [{"nombre": "...", "cantidad": <numero o null>, "unidad": "g"|"ud"|null}], '
            '"remove": "<alimento a quitar o null>", "goto": <numero de comida o null>}. '
            "Intenciones: "
            "'add' = dice qué alimentos quiere comer/añadir, con o sin cantidad "
            "(ej: 'quiero tortilla de claras y pan', 'pon 80 g de arroz', 'cambia el arroz a 100g'). "
            "'suggest' = pide que TÚ sugieras/recomiendes qué poner para ajustar o COMPLETAR la comida "
            "(ej: 'qué me sugieres', 'dame opciones', 'qué pongo', 'ayúdame a terminar de ajustar la comida', 'no sé qué añadir'). "
            "'complete' = quiere GUARDAR/cerrar esta comida y pasar a la siguiente "
            "(ej: 'siguiente', 'guardar y siguiente', 'ya está, la dejo así', 'pasa a la siguiente'). "
            "'remove' = quitar UN alimento ya añadido (ej: 'borra las aceitunas', 'quita el arroz'); pon el nombre en 'remove'. "
            "'clear' = vaciar TODA una comida (ej: 'vacía la comida 1', 'borra la comida 2', 'quita todo de esta comida', 'empieza de cero'); pon el número de comida en 'goto' (o null si es la actual). "
            "'status' = pregunta cuánto le FALTA por cubrir o cómo va de macros (ej: 'qué me falta', "
            "'cuántos macros quedan', 'cómo voy'). "
            "'summary' = resumen del día completo. "
            "'rebalance' = recalcular/cuadrar las cantidades de lo que YA hay (ej: 'cuadra las cantidades', 'reparte mejor'). "
            "'goto' = ir a una comida concreta (ej: 'vamos a la comida 2'); pon el número en 'goto'. "
            "'question' = cualquier otra consulta informativa: qué alimentos o comidas tiene CARGADAS, "
            "listar sus comidas/alimentos ('qué comidas tengo', 'lístame la comida 1', 'qué llevo'), "
            "dudas de nutrición ('por qué el arroz cuenta como hidrato'), o algo fuera de tema. "
            "'none' = saludo o ininteligible. "
            "IMPORTANTE: 'terminar/completar/ajustar la comida' cuando PIDEN ayuda o sugerencias es 'suggest', NO 'complete'. "
            "'complete' es solo cuando quieren guardar y avanzar. "
            "Listar o VER el contenido de las comidas/alimentos ('qué comidas tengo cargadas', "
            "'lístame los alimentos') es 'question', NO 'status' (status es SOLO cuánto falta). "
            "'borra/vacía la comida N' = 'clear' (vaciar toda la comida), mientras que "
            "'borra <alimento>' = 'remove' (quitar un alimento suelto). "
            "Interpreta números pegados o mal escritos. Rellena 'foods' SOLO si intent='add'."
        )
        raw = {}
        last_err = None
        for _ in range(2):
            chat = LlmChat(api_key=self.api_key, system_message=prompt).with_model(
                "openai", os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
            ).with_json_mode()
            try:
                resp = await chat.send_message(UserMessage(text=text))
                raw = self._parse_claude_response(resp)
                last_err = None
                break
            except Exception as e:
                last_err = e
                import asyncio as _asyncio
                await _asyncio.sleep(0.3)
        if last_err is not None or not isinstance(raw, dict):
            print(f"[understand] fallo: {last_err}")
            return {"intent": "add", "foods": [], "remove": None, "goto": None}

        intents = ("add", "suggest", "complete", "remove", "clear", "status",
                   "summary", "rebalance", "goto", "question", "none")
        intent = raw.get("intent")
        if intent not in intents:
            intent = "add"
        remove = raw.get("remove")
        if not isinstance(remove, str) or not remove.strip():
            remove = None
        goto = raw.get("goto")
        try:
            goto = int(goto) if goto is not None else None
        except (TypeError, ValueError):
            goto = None
        return {
            "intent": intent,
            "foods": self._normalize_food_items(raw.get("foods") or []),
            "remove": remove,
            "goto": goto,
        }

    async def process_message(self, user_input: str) -> dict:
        """Interpreta el mensaje con el LLM (router de intención) y ejecuta con código
        determinista. El LLM solo entiende QUÉ quiere el usuario; la matemática es del código."""
        data = await self.understand(user_input)
        intent = data.get("intent")

        if intent == "goto" and data.get("goto"):
            if self.go_to_meal(int(data["goto"])):
                return self._meal_response([], [])

        if intent == "status":
            return {"action": "status", "meals_status": self.get_meals_status(),
                    "day_overview": self.get_day_overview()}

        if intent == "complete":
            return {"action": "complete_request"}

        if intent == "suggest":
            return await self.suggest_foods_for_current_meal()

        if intent == "summary":
            return {"action": "summary", "day_overview": self.get_day_overview()}

        if intent == "rebalance":
            return await self.rebalance_current_meal()

        if intent == "clear":
            nombre = self.clear_meal(data.get("goto"))
            if nombre:
                resp = self._meal_response([], [])
                resp["message"] = f"Vacié {nombre}. Puedes empezarla de nuevo."
                return resp
            return {"action": "no_foods",
                    "message": "No pude identificar qué comida vaciar. Dime, p.ej., \"vacía la comida 2\".",
                    "day_overview": self.get_day_overview()}

        if intent == "remove":
            removed = self.remove_food_by_name(data.get("remove") or user_input)
            if removed:
                resp = self._meal_response([], [])
                resp["message"] = f"Quité {removed.get('nombre')} de esta comida."
                return resp
            return {
                "action": "no_foods",
                "message": ("No encontré ese alimento en la comida actual para quitarlo. "
                            "Míralo en la lista de arriba y toca la × del que quieras eliminar."),
                "day_overview": self.get_day_overview(),
            }

        if intent == "question":
            return await self.answer_question(user_input)

        # intent == "add" (o fallback): añadir los alimentos que dijo
        foods = data.get("foods") or []
        if foods:
            return await self.add_foods(foods)

        # Sin alimentos claros: si parece una frase, tratar como duda; si no, pedir alimentos.
        if len(user_input.split()) >= 4:
            return await self.answer_question(user_input)
        msg = ("No reconocí ningún alimento ahí. Dime qué quieres comer (p.ej. \"huevos, pan, "
               "claras\"), o pregúntame \"¿qué me falta?\". También puedes pulsar \"Sugerir "
               "alimentos\" o \"Guardar y siguiente\".")
        return {"action": "no_foods", "message": msg, "day_overview": self.get_day_overview()}
    
    def _parse_claude_response(self, response: str) -> dict:
        """Parsea la respuesta del LLM como JSON, tolerando fences de Markdown
        (```json ... ```) que algunos modelos (Groq) añaden a veces."""
        text = (response or "").strip()

        # Quitar fences de Markdown si los hay
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
            text = re.sub(r"\n?```$", "", text).strip()

        try:
            return json.loads(text)
        except:
            # Buscar el primer objeto JSON dentro del texto
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass

            # Si no se puede parsear, devolver como mensaje
            return {
                "action": "message",
                "message": response
            }
    
# =====================================================
# FUNCIONES DE AYUDA PARA EL API
# =====================================================

async def create_chatbot(session_id: str, db, user_macros: dict = None) -> NutritionChatbot:
    """
    Crea una instancia del chatbot.
    
    Args:
        session_id: ID único de sesión
        db: Conexión MongoDB
        user_macros: Macros del usuario (opcional)
    
    Returns:
        Instancia de NutritionChatbot
    """
    chatbot = NutritionChatbot(session_id, db)
    
    if user_macros:
        chatbot.set_user_macros(user_macros)
    
    return chatbot


# Almacén en memoria de sesiones (en producción usar Redis)
_chatbot_sessions: Dict[str, NutritionChatbot] = {}


async def get_or_create_chatbot(session_id: str, db, user_macros: dict = None) -> NutritionChatbot:
    """Obtiene o crea un chatbot para la sesión."""
    if session_id not in _chatbot_sessions:
        _chatbot_sessions[session_id] = await create_chatbot(session_id, db, user_macros)
    return _chatbot_sessions[session_id]


def clear_session(session_id: str):
    """Limpia una sesión de chatbot."""
    if session_id in _chatbot_sessions:
        del _chatbot_sessions[session_id]
