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

from emergentintegrations.llm.chat import LlmChat, UserMessage

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
        self.api_key = os.environ.get('EMERGENT_LLM_KEY')
        
        # Estado de la conversación
        self.state = {
            "step": "init",  # init, config, building_meal, complete
            "tipo_dia": None,  # "entrenamiento" o "descanso"
            "num_comidas": 4,
            "momento_entreno": 1,  # Después de C1
            "opcion_peri": "intra_post",
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
            "comida_actual": 1,
            "comidas_completadas": {},  # {1: {alimentos: [...], macros: {...}}, ...}
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
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
    
    def set_user_macros(self, macros: dict):
        """Establece los macros del usuario desde su perfil."""
        self.state["macros_usuario"].update(macros)
    
    def configure_day(self, tipo_dia: str, num_comidas: int, momento_entreno: int = 1, opcion_peri: str = "intra_post"):
        """
        Configura el día y calcula la distribución de macros.
        
        Args:
            tipo_dia: "entrenamiento" o "descanso"
            num_comidas: 3 o 4
            momento_entreno: 0-3 (solo para entrenamiento)
            opcion_peri: "intra_post", "solo_post", "solo_intra", "sin_peri"
        """
        self.state["tipo_dia"] = tipo_dia
        self.state["num_comidas"] = num_comidas
        self.state["momento_entreno"] = momento_entreno
        self.state["opcion_peri"] = opcion_peri
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
            num_comidas=num_comidas,
            momento_entreno=momento_entreno,
            opcion_peri=opcion_peri
        )
        
        return self.state["distribucion"]
    
    def get_current_meal_macros(self) -> dict:
        """Obtiene los macros objetivo de la comida actual."""
        if not self.state["distribucion"]:
            return {"P": 0, "H": 0, "G": 0}
        
        comida_key = f"C{self.state['comida_actual']}"
        return self.state["distribucion"]["comidas"].get(comida_key, {"P": 0, "H": 0, "G": 0})
    
    def get_remaining_macros(self) -> dict:
        """Calcula los macros restantes de la comida actual."""
        objetivo = self.get_current_meal_macros()
        completada = self.state["comidas_completadas"].get(self.state["comida_actual"], {})
        macros_usados = completada.get("macros", {"P": 0, "H": 0, "G": 0})
        
        return {
            "P": round(objetivo["P"] - macros_usados.get("P", 0), 1),
            "H": round(objetivo["H"] - macros_usados.get("H", 0), 1),
            "G": round(objetivo["G"] - macros_usados.get("G", 0), 1)
        }
    
    async def search_foods(self, query: str, limit: int = 5) -> list:
        """
        Busca alimentos en la base de datos.
        Prioriza coincidencias exactas y al inicio del nombre.
        
        Args:
            query: Texto de búsqueda
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
        # Incluye variantes con y sin acento
        query_mappings = {
            "huevos": "huevos enteros",
            "huevo": "huevos enteros",
            "claras": "claras de huevo pasteurizadas",
            "clara": "claras de huevo pasteurizadas",
            "pavo": "fiambre pechuga pavo",
            "pan": "pan de barra",
            "avena": "copos de avena",
            "arroz": "arroz blanco",
            "pollo": "pechuga pollo",
            "pechuga": "pechuga pollo",
            "yogur": "yogur griego",
            "yogurt": "yogur griego",
            "garbanzos": "garbanzos cocidos",
            "garbanzo": "garbanzos cocidos",
            "aguacate": "aguacate",
            "calabacin": "calabacin",
            "salmon": "salmon",
            "atun": "atun",
            "patata": "patata",
            "patatas": "patata",
            "brocoli": "brocoli",
            "espinacas": "espinacas",
            "tomate": "tomate",
            "lechuga": "lechuga",
            "platano": "platano",
            "banana": "platano",
            "manzana": "manzana",
            "naranja": "naranja",
            "leche": "leche",
            "queso": "queso",
        }
        
        # Usar mapeo si existe
        search_term = query_mappings.get(query_norm, query_norm)
        search_norm = normalize(search_term)
        
        # Buscar en MongoDB usando la función normalizada de calculator.py
        # que maneja correctamente acentos y diacríticos
        from calculator import buscar_alimentos as calc_buscar
        
        # La función de calculator.py normaliza bien y trae candidatos
        candidates = await calc_buscar(
            self.db, 
            query=search_term, 
            limit=100,
            calcular_efectivos=False
        )
        
        # Si no hay resultados con el mapeo, intentar búsqueda directa
        if not candidates and search_term != query_norm:
            candidates = await calc_buscar(
                self.db, 
                query=query_norm, 
                limit=100,
                calcular_efectivos=False
            )
        
        # Puntuar candidatos por relevancia
        scored = []
        for food in candidates:
            nombre = food.get("nombre", "")
            nombre_norm = normalize(nombre)
            score = 0
            
            # Coincidencia exacta del nombre simplificado
            nombre_simple = nombre_norm.split("(")[0].strip()  # Quitar marca
            
            # Máxima prioridad: nombre empieza exactamente con la búsqueda
            if nombre_simple.startswith(search_norm):
                score += 200
            elif nombre_norm.startswith(search_norm):
                score += 150
            # Alta prioridad: todas las palabras de búsqueda están en el nombre
            elif all(w in nombre_norm for w in search_norm.split()):
                score += 100
            # Media prioridad: palabra principal al inicio
            elif any(nombre_simple.startswith(w) for w in search_norm.split()):
                score += 80
            # Baja prioridad: coincidencia parcial
            elif search_norm in nombre_norm:
                score += 40
            else:
                continue  # No incluir si no hay buena coincidencia
            
            # Bonificar genéricos (sin marca)
            if "(" not in nombre:
                score += 30
            
            # Bonificar alimentos con etiqueta GEN (genérico)
            if "GEN" in str(food.get("categorias", "")):
                score += 25
            
            # Bonificar alimentos frecuentes (TOP)
            if "TOP" in str(food.get("categorias", "")):
                score += 20
            
            # Penalizar productos procesados/complejos para búsquedas simples
            cats = str(food.get("categorias", ""))
            if any(c in cats for c in ["43", "44", "49"]) and len(query_norm) < 10:
                score -= 50
            
            scored.append((score, food))
        
        # Ordenar por score descendente
        scored.sort(key=lambda x: x[0], reverse=True)
        
        return [food for score, food in scored[:limit]]
    
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
        comida_num = self.state["comida_actual"]
        
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
        """Formatea la cantidad para mostrar al usuario."""
        # FIX: usar 'por_unidad' no 'tipo'
        if config.get("por_unidad", False):
            peso_unidad = config.get("peso_unidad", 0)
            if peso_unidad > 0:
                unidades = cantidad_g / peso_unidad
                if abs(unidades - round(unidades)) < 0.01:
                    return f"{int(round(unidades))} ud"
                elif config.get("permite_media", False):
                    # Mostrar medias unidades si aplica
                    medias = round(unidades * 2) / 2
                    if medias == int(medias):
                        return f"{int(medias)} ud"
                    else:
                        return f"{medias:.1f} ud"
                else:
                    return f"{int(round(unidades))} ud"
            else:
                # Fallback a racion
                racion = float(alimento.get("racion", 100) or 100)
                unidades = cantidad_g / racion
                if abs(unidades - round(unidades)) < 0.01:
                    return f"{int(round(unidades))} ud"
                else:
                    return f"{unidades:.1f} ud"
        else:
            return f"{int(cantidad_g)}g"
    
    def complete_current_meal(self) -> dict:
        """Marca la comida actual como completa y avanza a la siguiente."""
        comida_num = self.state["comida_actual"]
        resultado = self.state["comidas_completadas"].get(comida_num, {})
        
        self.state["comida_actual"] += 1
        
        # Verificar si todas las comidas están completas
        if self.state["comida_actual"] > self.state["num_comidas"]:
            self.state["step"] = "complete"
        
        return resultado
    
    def get_day_summary(self) -> dict:
        """Obtiene el resumen del día completo."""
        totales = {"P": 0, "H": 0, "G": 0}
        comidas_resumen = []
        
        for i in range(1, self.state["num_comidas"] + 1):
            comida = self.state["comidas_completadas"].get(i, {"alimentos": [], "macros": {"P": 0, "H": 0, "G": 0}})
            objetivo = self.state["distribucion"]["comidas"].get(f"C{i}", {"P": 0, "H": 0, "G": 0})
            
            comidas_resumen.append({
                "numero": i,
                "alimentos": comida.get("alimentos", []),
                "macros": comida.get("macros", {"P": 0, "H": 0, "G": 0}),
                "objetivo": objetivo
            })
            
            totales["P"] += comida.get("macros", {}).get("P", 0)
            totales["H"] += comida.get("macros", {}).get("H", 0)
            totales["G"] += comida.get("macros", {}).get("G", 0)
        
        objetivo_total = self.state["distribucion"]["resumen"]
        
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
    
    async def process_message(self, user_input: str) -> dict:
        """
        Procesa un mensaje del usuario y devuelve la respuesta.
        
        Args:
            user_input: Mensaje del usuario
        
        Returns:
            dict con action, message, data (opcional)
        """
        # Construir contexto para Claude
        context = self._build_context()
        
        # Mensaje con contexto
        full_message = f"""CONTEXTO ACTUAL:
{context}

MENSAJE DEL USUARIO:
{user_input}

Responde en formato JSON según las instrucciones del sistema."""
        
        try:
            # Enviar a Claude
            user_message = UserMessage(text=full_message)
            response = await self.chat.send_message(user_message)
            
            # Parsear respuesta JSON
            response_data = self._parse_claude_response(response)
            
            # Procesar según la acción
            if response_data.get("action") == "build_meal":
                foods_requested = response_data.get("foods_requested", [])
                return await self._process_build_meal(foods_requested, response_data.get("message", ""))
            
            return response_data
            
        except Exception as e:
            return {
                "action": "error",
                "message": f"Error procesando mensaje: {str(e)}"
            }
    
    def _build_context(self) -> str:
        """Construye el contexto actual para Claude."""
        ctx = []
        
        ctx.append(f"Paso: {self.state['step']}")
        ctx.append(f"Tipo de día: {self.state['tipo_dia'] or 'No configurado'}")
        ctx.append(f"Número de comidas: {self.state['num_comidas']}")
        
        if self.state["distribucion"]:
            ctx.append(f"\nComida actual: {self.state['comida_actual']}")
            
            objetivo = self.get_current_meal_macros()
            ctx.append(f"Objetivo comida {self.state['comida_actual']}: P={objetivo['P']}g, H={objetivo['H']}g, G={objetivo['G']}g")
            
            restantes = self.get_remaining_macros()
            ctx.append(f"Macros restantes: P={restantes['P']}g, H={restantes['H']}g, G={restantes['G']}g")
            
            # Alimentos ya añadidos
            comida_actual = self.state["comidas_completadas"].get(self.state["comida_actual"], {})
            alimentos = comida_actual.get("alimentos", [])
            if alimentos:
                ctx.append(f"\nAlimentos ya añadidos a esta comida:")
                for a in alimentos:
                    ctx.append(f"  - {a['nombre']}: {a['cantidad_display']} (P={a['macros']['P']}, H={a['macros']['H']}, G={a['macros']['G']})")
        
        return "\n".join(ctx)
    
    def _parse_claude_response(self, response: str) -> dict:
        """Parsea la respuesta de Claude como JSON."""
        try:
            # Intentar parsear directamente
            return json.loads(response)
        except:
            # Buscar JSON en la respuesta
            json_match = re.search(r'\{[\s\S]*\}', response)
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
    
    async def _process_build_meal(self, foods_requested: list, claude_message: str) -> dict:
        """
        Procesa la construcción de una comida con DISTRIBUCIÓN INTELIGENTE de macros.
        
        ESTRATEGIA SIMPLIFICADA:
        1. Buscar todos los alimentos
        2. Separar por macro PRINCIPAL (P, H, G, otros)
        3. Las fuentes de cada macro se reparten el objetivo de ese macro equitativamente
        4. Aplicar límites min/max
        
        Args:
            foods_requested: Lista de nombres de alimentos solicitados
            claude_message: Mensaje original de Claude
        
        Returns:
            dict con los alimentos encontrados y cantidades calculadas
        """
        from calma_engine import parse_categories, calcular_macros_efectivos
        
        objetivo = self.get_current_meal_macros()
        p_objetivo = float(objetivo.get("P", 0))
        h_objetivo = float(objetivo.get("H", 0))
        g_objetivo = float(objetivo.get("G", 0))
        
        # Paso 1: Buscar todos los alimentos
        alimentos_info = []
        not_found = []
        
        for food_name in foods_requested:
            matches = await self.search_foods(food_name, limit=3)
            
            if matches:
                alimento = matches[0]
                config = get_food_config(alimento)
                
                cats = parse_categories(alimento.get("categorias", []))
                cat = cats[0] if cats else "0"
                
                racion = float(alimento.get("racion", 100) or 100)
                P_100 = float(alimento.get("proteinas", 0) or 0) * 100.0 / racion
                H_100 = float(alimento.get("hidratos", 0) or 0) * 100.0 / racion
                G_100 = float(alimento.get("grasas", 0) or 0) * 100.0 / racion
                
                ef_100 = calcular_macros_efectivos(P_100, H_100, G_100, cat, 100.0)
                p_ef = ef_100["proteina_efectiva"]
                h_ef = ef_100["hidratos_efectivos"]
                g_ef = ef_100["grasa_efectiva"]
                
                # Determinar macro principal (el que más aporta)
                max_ef = max(p_ef, h_ef, g_ef)
                if max_ef == 0:
                    macro_principal = "otros"
                elif p_ef == max_ef:
                    macro_principal = "P"
                elif h_ef == max_ef:
                    macro_principal = "H"
                else:
                    macro_principal = "G"
                
                alimentos_info.append({
                    "alimento": alimento,
                    "config": config,
                    "cat": cat,
                    "macro_principal": macro_principal,
                    "p_ef_100": p_ef,
                    "h_ef_100": h_ef,
                    "g_ef_100": g_ef,
                    "alternativas": [m.get("nombre") for m in matches[1:3]]
                })
            else:
                not_found.append({
                    "buscado": food_name,
                    "encontrado": None,
                    "razon": "No encontrado en la base de datos"
                })
        
        # Paso 2: Agrupar por macro principal
        fuentes_P = [a for a in alimentos_info if a["macro_principal"] == "P"]
        fuentes_H = [a for a in alimentos_info if a["macro_principal"] == "H"]
        fuentes_G = [a for a in alimentos_info if a["macro_principal"] == "G"]
        fuentes_otros = [a for a in alimentos_info if a["macro_principal"] == "otros"]
        
        found_foods = []
        restantes = {"P": p_objetivo, "H": h_objetivo, "G": g_objetivo}
        
        # IMPORTANTE: Estimar cuánta P aportarán las fuentes de H
        # (legumbres como garbanzos aportan P significativa aunque su macro principal sea H)
        p_de_fuentes_H = 0
        for fuente in fuentes_H:
            if fuente["p_ef_100"] > 5:  # Si aporta >5g P por 100g, es significativo
                # Estimar cuántos gramos vamos a usar basados en el H
                if fuente["h_ef_100"] > 0:
                    cant_estimada = (h_objetivo / len(fuentes_H) / fuente["h_ef_100"]) * 100
                    # Límite máximo
                    max_cant = self._get_max_cantidad_razonable(fuente["cat"], fuente["config"], float(fuente["alimento"].get("racion", 100)))
                    cant_estimada = min(cant_estimada, max_cant)
                    p_de_fuentes_H += (cant_estimada / 100) * fuente["p_ef_100"]
        
        # Ajustar el objetivo de P para las fuentes puras de P
        p_objetivo_ajustado = max(0, p_objetivo - p_de_fuentes_H)
        
        # Paso 3: Distribuir P entre fuentes de P
        # ESTRATEGIA MEJORADA: 
        # 1. Primero calculamos cuánto puede dar cada fuente con su máximo
        # 2. Si una fuente no puede dar su parte, las demás compensan
        if fuentes_P:
            # Calcular cuánto puede dar cada fuente como máximo
            capacidades = []
            for fuente in fuentes_P:
                if fuente["p_ef_100"] <= 0:
                    capacidades.append({"fuente": fuente, "max_p": 0})
                    continue
                
                config = fuente["config"]
                alimento = fuente["alimento"]
                max_cant = self._get_max_cantidad_razonable(fuente["cat"], config, float(alimento.get("racion", 100)))
                
                # Si es por unidad, ajustar al máximo de unidades
                if config.get("por_unidad", False):
                    max_cant = ajustar_por_unidades(max_cant, config)
                
                max_p = (max_cant / 100) * fuente["p_ef_100"]
                capacidades.append({"fuente": fuente, "max_p": max_p, "max_cant": max_cant})
            
            # Distribuir P_AJUSTADO equitativamente, compensando si alguien no puede
            p_restante = p_objetivo_ajustado  # Usar el objetivo ajustado
            fuentes_restantes = [c for c in capacidades if c["max_p"] > 0]
            
            # Procesar fuentes ordenando por menor capacidad primero
            # (así las que tienen límites bajos se procesan primero y las demás compensan)
            fuentes_restantes.sort(key=lambda x: x["max_p"])
            
            for i, cap in enumerate(fuentes_restantes):
                fuente = cap["fuente"]
                n_restantes = len(fuentes_restantes) - i
                
                # Cuánto le toca a esta fuente
                p_por_fuente = p_restante / n_restantes if n_restantes > 0 else 0
                
                # Cuánto puede dar realmente
                p_dar = min(p_por_fuente, cap["max_p"])
                
                # Calcular gramos
                cantidad_g = (p_dar / fuente["p_ef_100"]) * 100 if fuente["p_ef_100"] > 0 else 0
                
                # Aplicar límites
                max_cant = cap.get("max_cant", 200)
                cantidad_g = min(cantidad_g, max_cant)
                
                config = fuente["config"]
                alimento = fuente["alimento"]
                
                minimo = config.get("minimo", 5)
                if cantidad_g < minimo:
                    cantidad_g = minimo
                
                if config.get("por_unidad", False):
                    cantidad_g = ajustar_por_unidades(cantidad_g, config)
                
                efectivos = self.add_food_to_meal(alimento, cantidad_g)
                
                found_foods.append({
                    "nombre": alimento.get("nombre"),
                    "cantidad": cantidad_g,
                    "cantidad_display": self._format_cantidad(cantidad_g, alimento, config),
                    "macros": efectivos,
                    "alternativas": fuente["alternativas"]
                })
                
                restantes["P"] -= efectivos.get("P", 0)
                restantes["H"] -= efectivos.get("H", 0)
                restantes["G"] -= efectivos.get("G", 0)
                
                # Actualizar P restante para las siguientes fuentes
                p_restante -= efectivos.get("P", 0)
        
        # Paso 4: Distribuir H entre fuentes de H (usando lo que queda)
        if fuentes_H and restantes["H"] > 0:
            h_por_fuente = restantes["H"] / len(fuentes_H)
            
            for fuente in fuentes_H:
                if fuente["h_ef_100"] <= 0:
                    continue
                
                alimento = fuente["alimento"]
                config = fuente["config"]
                
                cantidad_g = (h_por_fuente / fuente["h_ef_100"]) * 100
                
                max_cant = self._get_max_cantidad_razonable(fuente["cat"], config, float(alimento.get("racion", 100)))
                cantidad_g = min(cantidad_g, max_cant)
                
                minimo = config.get("minimo", 5)
                if cantidad_g < minimo:
                    cantidad_g = minimo
                
                if config.get("por_unidad", False):
                    cantidad_g = ajustar_por_unidades(cantidad_g, config)
                
                efectivos = self.add_food_to_meal(alimento, cantidad_g)
                
                found_foods.append({
                    "nombre": alimento.get("nombre"),
                    "cantidad": cantidad_g,
                    "cantidad_display": self._format_cantidad(cantidad_g, alimento, config),
                    "macros": efectivos,
                    "alternativas": fuente["alternativas"]
                })
                
                restantes["P"] -= efectivos.get("P", 0)
                restantes["H"] -= efectivos.get("H", 0)
                restantes["G"] -= efectivos.get("G", 0)
        
        # Paso 5: Distribuir G entre fuentes de G
        if fuentes_G and restantes["G"] > 0:
            g_por_fuente = restantes["G"] / len(fuentes_G)
            
            for fuente in fuentes_G:
                if fuente["g_ef_100"] <= 0:
                    continue
                
                alimento = fuente["alimento"]
                config = fuente["config"]
                
                cantidad_g = (g_por_fuente / fuente["g_ef_100"]) * 100
                
                max_cant = self._get_max_cantidad_razonable(fuente["cat"], config, float(alimento.get("racion", 100)))
                cantidad_g = min(cantidad_g, max_cant)
                
                minimo = config.get("minimo", 5)
                if cantidad_g < minimo:
                    cantidad_g = minimo
                
                if config.get("por_unidad", False):
                    cantidad_g = ajustar_por_unidades(cantidad_g, config)
                
                efectivos = self.add_food_to_meal(alimento, cantidad_g)
                
                found_foods.append({
                    "nombre": alimento.get("nombre"),
                    "cantidad": cantidad_g,
                    "cantidad_display": self._format_cantidad(cantidad_g, alimento, config),
                    "macros": efectivos,
                    "alternativas": fuente["alternativas"]
                })
                
                restantes["P"] -= efectivos.get("P", 0)
                restantes["H"] -= efectivos.get("H", 0)
                restantes["G"] -= efectivos.get("G", 0)
        
        # Paso 6: Añadir otros (verduras) con cantidad fija
        for fuente in fuentes_otros:
            alimento = fuente["alimento"]
            config = fuente["config"]
            
            cantidad_g = config.get("defecto", 100)
            
            if config.get("por_unidad", False):
                cantidad_g = ajustar_por_unidades(cantidad_g, config)
            
            efectivos = self.add_food_to_meal(alimento, cantidad_g)
            
            found_foods.append({
                "nombre": alimento.get("nombre"),
                "cantidad": cantidad_g,
                "cantidad_display": self._format_cantidad(cantidad_g, alimento, config),
                "macros": efectivos,
                "alternativas": fuente["alternativas"]
            })
            
            restantes["P"] -= efectivos.get("P", 0)
            restantes["H"] -= efectivos.get("H", 0)
            restantes["G"] -= efectivos.get("G", 0)
        
        # Construir respuesta
        comida_actual = self.state["comidas_completadas"].get(self.state["comida_actual"], {})
        macros_actuales = comida_actual.get("macros", {"P": 0, "H": 0, "G": 0})
        restantes_final = self.get_remaining_macros()
        
        # Sugerencia si faltan grasas
        sugerencia = None
        if restantes_final["G"] > 2 and restantes_final["P"] <= 2 and restantes_final["H"] <= 2:
            sugerencia = f"Faltan {restantes_final['G']:.0f}g de grasa. Añade aceite de oliva ({restantes_final['G']:.0f}ml) para cuadrar."
        
        return {
            "action": "meal_updated",
            "foods_added": found_foods,
            "foods_not_found": not_found,
            "meal_status": {
                "comida": self.state["comida_actual"],
                "objetivo": objetivo,
                "actual": macros_actuales,
                "restante": restantes_final,
                "alimentos": comida_actual.get("alimentos", [])
            },
            "sugerencia": sugerencia,
            "message": claude_message
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
