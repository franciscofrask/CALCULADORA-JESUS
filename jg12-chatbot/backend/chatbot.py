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
        # Normalizar query (quitar acentos)
        import unicodedata
        def normalize(text):
            return ''.join(
                c for c in unicodedata.normalize('NFD', text.lower())
                if unicodedata.category(c) != 'Mn'
            )
        
        query_norm = normalize(query.strip())
        query_words = query_norm.split()
        
        # Buscar en MongoDB con regex
        regex_pattern = f".*{query_norm}.*"
        cursor = self.db.foods.find(
            {"nombre": {"$regex": regex_pattern, "$options": "i"}},
            {"_id": 0}
        ).limit(50)
        
        candidates = await cursor.to_list(length=50)
        
        # Puntuar candidatos por relevancia
        scored = []
        for food in candidates:
            nombre = food.get("nombre", "")
            nombre_norm = normalize(nombre)
            score = 0
            
            # Coincidencia exacta al inicio = máxima prioridad
            if nombre_norm.startswith(query_norm):
                score += 100
            # Palabra completa al inicio
            elif any(nombre_norm.startswith(w) for w in query_words):
                score += 80
            # Coincidencia como palabra completa
            elif query_norm in nombre_norm.split():
                score += 60
            # Coincidencia parcial
            elif query_norm in nombre_norm:
                score += 40
            
            # Penalizar productos de marca que no son lo buscado
            # Ej: buscar "pan" no debería devolver "Donut (Panrico)"
            if "(" in nombre and query_norm not in normalize(nombre.split("(")[0]):
                score -= 30
            
            # Bonificar genéricos
            if "GEN" in str(food.get("categorias", "")):
                score += 10
            
            # Bonificar si tiene la etiqueta TOP (alimentos frecuentes)
            if "TOP" in str(food.get("categorias", "")):
                score += 15
            
            scored.append((score, food))
        
        # Ordenar por score descendente
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # Devolver los mejores
        return [food for score, food in scored[:limit]]
    
    def calculate_food_amount(self, alimento: dict, macros_restantes: dict) -> dict:
        """
        Calcula la cantidad óptima de un alimento sin pasarse de los macros restantes.
        
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
        
        # Aplicar mínimo del config
        minimo = config.get("minimo", 5)
        if cantidad < minimo:
            # Si no cabe ni el mínimo, no se puede usar
            cabe = False
            cantidad = minimo  # Para mostrar la cantidad mínima
        
        # Ajustar por unidades si aplica
        if config.get("tipo") == "unidad" and cabe:
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
        if config.get("tipo") == "unidad":
            racion = float(alimento.get("racion", 100) or 100)
            unidades = cantidad_g / racion
            if unidades == int(unidades):
                return f"{int(unidades)} ud"
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
        Procesa la construcción de una comida.
        
        Args:
            foods_requested: Lista de nombres de alimentos solicitados
            claude_message: Mensaje original de Claude
        
        Returns:
            dict con los alimentos encontrados y cantidades calculadas
        """
        restantes = self.get_remaining_macros()
        found_foods = []
        not_found = []
        
        for food_name in foods_requested:
            # Buscar en BD
            matches = await self.search_foods(food_name, limit=3)
            
            if matches:
                # Tomar el primer resultado
                alimento = matches[0]
                
                # Calcular cantidad
                calc_result = self.calculate_food_amount(alimento, restantes)
                
                if calc_result.get("cabe", True) and calc_result.get("cantidad_g", 0) > 0:
                    # Añadir a la comida
                    self.add_food_to_meal(alimento, calc_result["cantidad_g"])
                    
                    found_foods.append({
                        "nombre": alimento.get("nombre"),
                        "cantidad": calc_result["cantidad_g"],
                        "cantidad_display": self._format_cantidad(
                            calc_result["cantidad_g"], 
                            alimento, 
                            calc_result.get("config", {})
                        ),
                        "macros": calc_result.get("macros_efectivos", {}),
                        "alternativas": [m.get("nombre") for m in matches[1:3]]
                    })
                    
                    # Actualizar restantes para el siguiente alimento
                    restantes = self.get_remaining_macros()
                else:
                    not_found.append({
                        "buscado": food_name,
                        "encontrado": alimento.get("nombre"),
                        "razon": "No cabe en los macros restantes"
                    })
            else:
                not_found.append({
                    "buscado": food_name,
                    "encontrado": None,
                    "razon": "No encontrado en la base de datos"
                })
        
        # Construir respuesta
        objetivo = self.get_current_meal_macros()
        comida_actual = self.state["comidas_completadas"].get(self.state["comida_actual"], {})
        macros_actuales = comida_actual.get("macros", {"P": 0, "H": 0, "G": 0})
        restantes_final = self.get_remaining_macros()
        
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
