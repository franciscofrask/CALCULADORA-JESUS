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

# Importar funciones del motor CALMA. El conteo de macros va por calma_suggest (fiel al
# bundle de Calma) via calibracion_dia; de calma_engine solo queda el parseo de categorias.
from calma_engine import parse_categories
from calibracion_dia import macros_item_por_acumulado
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

SYSTEM_PROMPT = """Eres un asistente de nutrición del método 12en12.
Tu trabajo es ayudar al cliente a preparar su dieta del día, comida por comida.

REGLAS IMPORTANTES:
1. Sé conciso y directo. No des explicaciones largas a menos que te las pidan.
2. Cuando el cliente mencione alimentos, extrae los nombres y busca en la base de datos.
3. Siempre muestra las cantidades en gramos o unidades según corresponda.
4. Si un alimento no cuadra con los macros restantes, explica brevemente por qué y sugiere alternativas.
5. Usa un tono amigable pero profesional.
6. NO inventes alimentos ni macros. Solo usa los datos de la base de datos.
7. Escribe SIEMPRE en español neutro con tuteo ("añade", "elige", "tienes", "prepara"). Prohibido el voseo ("armá", "tenés", "elegí") y los regionalismos ("armar la comida"). Para alimentos usa los nombres habituales en España: aguacate (no palta), fresa (no frutilla), melocotón (no durazno), boniato (no batata), plátano (no banana), judías verdes (no chauchas).

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
            "acumulado_frutos_secos": 0,
            "last_options": [],  # Últimas opciones ofrecidas (sugerencias/desambiguación) para elegir por texto
            "saved_meals": [],  # Claves de comidas guardadas con "guardar y siguiente"
            "seen_sugg": {},  # Sugerencias ya ofrecidas por comida (para no repetirlas)
            "last_termino": None,  # De qué tipo de alimento iba la última lista ("tostadas")
            "termino_vistos": [],  # Ids ya enseñados de ese término, para no repetirlos
        }
        
        # Historial de mensajes para persistencia
        self.messages_history = []
        
        # Inicializar chat con Claude
        self.chat = LlmChat(
            api_key=self.api_key,
            session_id=session_id,
            system_message=SYSTEM_PROMPT
        ).with_model("openai", os.environ.get('OPENAI_MODEL', 'gpt-4.1-mini')).with_json_mode()
    
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

        # Reconfigurar a mitad de camino cambia los objetivos, pero lo que ya haya montado
        # se RESPETA: quien lleva media Comida 1 hecha no merece perderla por decir "quita
        # el intra". Solo se cae lo que ya no existe en el día nuevo (el propio intra, o la
        # Comida 4 al bajar a 3), que si no se colaría en la dieta guardada sin estar en el
        # recorrido. Los objetivos nuevos se ven al momento en cada comida.
        vivas = set(self.state["meal_order"])
        self.state["comidas_completadas"] = {
            k: v for k, v in (self.state.get("comidas_completadas") or {}).items() if k in vivas
        }
        self.state["saved_meals"] = [k for k in (self.state.get("saved_meals") or []) if k in vivas]
        if not self.state["comidas_completadas"]:
            self.state["acumulado_cereales_panes"] = 0
            self.state["acumulado_frutos_secos"] = 0

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
        if order:
            # Fuera de rango (p.ej. tras completar el día): la última comida real,
            # nunca una "Comida 7" fantasma con objetivo 0/0/0.
            return order[-1]
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
    
    async def buscar_con_interpretacion(self, nombre: str, interpretacion: Optional[str] = None,
                                        limit: int = 5) -> list:
        """Busca lo que ha pedido y, si hace falta, lo que eso significa en la tabla.

        La gente no habla como está escrito el catálogo: pide "tostadas" y ahí pone "pan
        tostado". El router ya traduce (`busqueda`), y aquí se usa esa traducción SOLO
        como segunda vía:

          1. se busca lo que dijo el usuario, tal cual;
          2. si no sale nada, o lo que sale es un parecido flojo, se busca la traducción.

        En ese orden a propósito. Lo que el usuario escribe manda: si pide "arroz" y ya
        hay "Arroz blanco", no queremos que una traducción del LLM se cuele por delante.
        La traducción solo entra donde antes no había nada.
        """
        directo = await self.search_foods(nombre, limit=limit)
        if directo and not directo[0].get("_match_parcial"):
            return directo
        if not interpretacion:
            return directo

        traducido = await self.search_foods(interpretacion, limit=limit)
        traducido = [f for f in traducido if not f.get("_match_parcial")]
        if not traducido:
            return directo

        # Se marca de dónde sale, para poder decírselo al usuario en vez de colar un
        # alimento con otro nombre en silencio.
        salida = [dict(f) for f in traducido]
        for f in salida:
            f["_interpretado"] = nombre
        return salida

    # Palabras que existen de verdad en el catálogo, para corregir erratas por parecido.
    # Se construye una vez por proceso (3.200 alimentos) y se comparte entre sesiones.
    _VOCAB_CATALOGO = None

    async def _vocabulario_catalogo(self) -> set:
        if NutritionChatbot._VOCAB_CATALOGO is None:
            vocab = set()
            async for f in self.db.foods.find({}, {"_id": 0, "nombre": 1}):
                limpio = re.sub(r"[(),/%.\-]", " ", self._norm_text(f.get("nombre", "")))
                for w in limpio.split():
                    if len(w) >= 4 and w.isalpha():
                        vocab.add(w)
            NutritionChatbot._VOCAB_CATALOGO = vocab
        return NutritionChatbot._VOCAB_CATALOGO

    async def _corregir_erratas(self, palabras: list) -> str:
        """Devuelve la consulta con las palabras mal escritas cambiadas por la del catálogo
        más parecida, o "" si no hay nada que corregir.

        El listón (0.8) es alto a propósito: "arrox"->"arroz" sí, pero "pavo"->"pato" no.
        Y solo se tocan palabras que NO existen en el catálogo, para no "corregir" lo que
        ya está bien escrito."""
        import difflib
        vocab = await self._vocabulario_catalogo()
        salida, tocado = [], False
        for w in palabras:
            if len(w) >= 4 and w.isalpha() and w not in vocab:
                cerca = difflib.get_close_matches(w, vocab, n=1, cutoff=0.8)
                if cerca:
                    salida.append(cerca[0])
                    tocado = True
                    continue
            salida.append(w)
        return " ".join(salida) if tocado else ""

    async def search_foods(self, query: str, limit: int = 5, _remap: bool = True) -> list:
        """
        Busca alimentos en la base de datos.
        Usa MongoDB text search para búsquedas de múltiples palabras.
        Prioriza coincidencias exactas y genéricos.

        Args:
            query: Texto de búsqueda (ej: "queso batido", "nueces")
            limit: Máximo de resultados
            _remap: uso interno; False evita reintentar el remap por palabra (anti-recursión).

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
            "huevo frito": "huevos enteros L",
            "huevos fritos": "huevos enteros L",
            "huevo cocido": "huevos enteros L",
            "huevos cocidos": "huevos enteros L",
            "huevos revueltos": "huevos enteros L",
            "claras": "claras de huevo pasteurizadas",
            "clara": "claras de huevo pasteurizadas",
            # OJO: "pavo" NO se mapea a propósito (petición 2026-07-17): en la base hay
            # tipos muy distintos (fiambre 2.1, pechuga fresca 2.2, jamón de pavo...) y
            # el asistente debe OFRECER opciones, no plantar siempre el fiambre.
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

            # Typos frecuentes y regionalismos (el usuario escribe como habla)
            "wevos": "huevos enteros L",
            "webos": "huevos enteros L",
            "uevos": "huevos enteros L",
            "guevos": "huevos enteros L",
            "wevo": "huevos enteros L",
            "poyo": "pollo",
            "poio": "pollo",
            "keso": "queso",
            "keso batido": "queso fresco batido 0%",
            "abena": "copos de avena",
            "palta": "aguacate",
            "frutilla": "fresas",
            "frutillas": "fresas",
            "durazno": "melocoton",
        }
        # Cachear en la clase los términos con elección canónica: la desambiguación NO debe
        # preguntar por ellos (para "arroz" ya sabemos que es arroz blanco, etc.).
        NutritionChatbot._CANONICAL_TERMS = frozenset(query_mappings)

        # Palabras significativas de la consulta (sin preposiciones/artículos):
        # se usan para decidir mapeos y para exigir cobertura en los resultados.
        _STOP = {"de", "del", "la", "el", "los", "las", "con", "sin", "al", "a",
                 "en", "un", "una", "unos", "unas", "y", "o", "u", "por", "para"}
        sig_words = [w for w in query_norm.split() if w not in _STOP and len(w) > 1]

        # Usar mapeo si existe. El mapeo POR PALABRA solo aplica a consultas de una
        # única palabra significativa: si no, "leche de avena" acabaría en leche de
        # vaca porque la palabra "leche" secuestra la búsqueda.
        search_term = query_mappings.get(query_norm, None)
        mapeado = search_term is not None
        if not search_term and len(sig_words) == 1 and sig_words[0] in query_mappings:
            search_term = query_mappings[sig_words[0]]
            mapeado = True
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
        
        # Paso 2b: variantes de género y número. "tostadas" tiene que llegar a "Pan
        # tostado": es el mismo alimento y el usuario no tiene por qué adivinar cómo está
        # escrito en el catálogo. Solo para consultas de UNA palabra significativa; con
        # varias, los pasos de arriba ya acotan bastante y ensanchar aquí traería ruido.
        raiz_pat = self._regex_raiz(sig_words[0]) if len(sig_words) == 1 else ""
        if raiz_pat:
            try:
                variantes = await self.db.foods.find(
                    {"nombre": {"$regex": raiz_pat, "$options": "i"}}, {"_id": 0}
                ).limit(50).to_list(50)
                existing_nombres = {c.get("nombre") for c in candidates}
                candidates.extend(r for r in variantes if r.get("nombre") not in existing_nombres)
            except Exception:
                pass

        # Erratas de tecleo: "arrox" -> "arroz", "poyo" -> "pollo". Va por PARECIDO con el
        # vocabulario real del catálogo, no por una lista de typos escrita a mano: la lista
        # solo cubre lo que alguien previó ("wevos", "abena") y el teclado no se agota.
        # Solo entra cuando no hay ningún candidato, así que nunca puede tapar un acierto.
        if not candidates and _remap and sig_words:
            corregida = await self._corregir_erratas(sig_words)
            if corregida and corregida != " ".join(sig_words):
                res = await self.search_foods(corregida, limit=limit, _remap=False)
                for r in res:
                    r["_corregido_de"] = query.strip()
                    r["_corregido_a"] = corregida
                if res:
                    return res

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
            # Misma palabra en otro género o número ("tostadas" -> "Pan tostado"). Va la
            # última y suma poco: es una coincidencia real, pero nunca debe adelantar a
            # quien empieza por lo que se ha pedido.
            elif raiz_pat and re.search(raiz_pat, nombre_norm):
                score += 35
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

        # COBERTURA: si la consulta tiene varias palabras significativas y NO vino
        # de un mapeo, exigir que el resultado las contenga (todas si son 2; todas
        # menos una si son 3+). Evita falsos positivos silenciosos tipo
        # "filete de unicornio" -> "Filete de pechuga empanado".
        resultados = [food for _, food in unique_scored[:limit]]
        if _remap and not mapeado and len(sig_words) >= 2:
            necesarias = len(sig_words) if len(sig_words) == 2 else len(sig_words) - 1
            con_cobertura = [
                food for _, food in unique_scored
                if sum(1 for w in sig_words if w in normalize(food.get("nombre", ""))) >= necesarias
            ]
            if con_cobertura:
                resultados = con_cobertura[:limit]
            else:
                # Sin cobertura: reintentar con el mapeo de alguna palabra suelta
                # ("batido de proteina" -> whey). _remap=False evita recursión.
                for w in sig_words:
                    if w in query_mappings:
                        remap = await self.search_foods(query_mappings[w], limit=limit, _remap=False)
                        if remap:
                            resultados = remap
                            break
                # Ninguna palabra cubre el término: marcar PARCIAL para que el
                # asistente avise ("no tengo X tal cual, he usado Y") en vez de
                # colar un alimento silenciosamente ("filete de unicornio" -> empanado).
                resultados = [dict(f) for f in resultados]
                for f in resultados:
                    f["_match_parcial"] = query.strip()
        return resultados
    
    def calculate_food_amount(self, alimento: dict, macros_restantes: dict) -> dict:
        """
        Calcula la cantidad óptima de un alimento sin pasarse de los macros restantes.
        
        IMPORTANTE: Aplica límites máximos RAZONABLES por categoría para que
        las cantidades tengan sentido humano (no sugerir 266g de claras).
        
        Returns:
            dict con cantidad_g, macros_efectivos, cabe, config
        """
        from calma_engine import parse_categories

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
        
        # Calcular qué macros cuentan para 100g (motor fiel a Calma + calibración del día)
        ef_100 = macros_item_por_acumulado(
            alimento, 100.0,
            acum_cp=self.state["acumulado_cereales_panes"],
            acum_fs=self.state["acumulado_frutos_secos"]
        )

        p_ef_100 = ef_100["P"]
        h_ef_100 = ef_100["H"]
        g_ef_100 = ef_100["G"]
        
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
        ef_final = macros_item_por_acumulado(
            alimento, cantidad,
            acum_cp=self.state["acumulado_cereales_panes"],
            acum_fs=self.state["acumulado_frutos_secos"]
        )

        # Verificar si se pasa en algún macro
        if ef_final["P"] > p_rest + 4:  # margen CALMA
            cabe = False
        if ef_final["H"] > h_rest + 4:
            cabe = False
        if ef_final["G"] > g_rest + 4:
            cabe = False

        return {
            "cantidad_g": round(cantidad, 1),
            "macros_efectivos": {
                "P": round(ef_final["P"], 1),
                "H": round(ef_final["H"], 1),
                "G": round(ef_final["G"], 1)
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
        
        # Límites por categoría (en gramos), calibrados con las cantidades que
        # aparecen en las dietas reales de los clientes.
        limites = {
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

        # Calcular macros efectivos. Mismo motor que el buscador y que anadir a mano
        # (calma_suggest, fiel a Calma) + la calibracion progresiva del dia.
        efectivos = macros_item_por_acumulado(
            alimento, cantidad_g,
            acum_cp=self.state["acumulado_cereales_panes"],
            acum_fs=self.state["acumulado_frutos_secos"]
        )
        
        # Actualizar acumulados si aplica
        cats = get_categorias(alimento)
        cat_principal = cats[0] if cats else ""
        
        if cat_principal.startswith("7") or cat_principal.startswith("8"):
            self.state["acumulado_cereales_panes"] += cantidad_g
        
        if cat_principal.startswith(("17.2.1", "17.2.3", "17.2.4", "17.2.6")):
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
        # Si el redondeo a unidades se aleja de los gramos contados (15 g de aceite
        # NO son "2 cucharadas" de 10 g), mostrar los gramos: lo que el usuario se
        # sirve debe coincidir con lo que se le contabiliza.
        if abs(uds * peso_unidad - cantidad_g) > 0.25 * peso_unidad:
            return f"{int(round(cantidad_g))}g"
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

        saved = self.state.setdefault("saved_meals", [])
        if comida_num not in saved:
            saved.append(comida_num)

        # Avanzar a la siguiente comida SIN guardar (no simplemente la siguiente en orden:
        # si el usuario volvió atrás a editar, no debe re-pasar por comidas ya guardadas).
        order = self.state["meal_order"]
        pendientes = [i + 1 for i, k in enumerate(order) if k not in saved]
        if not pendientes:
            self.state["step"] = "complete"
            self.state["comida_actual"] = max(1, len(order))
        else:
            actual = self.state["comida_actual"]
            siguientes = [i for i in pendientes if i > actual]
            self.state["comida_actual"] = siguientes[0] if siguientes else pendientes[0]

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
            "Extrae los alimentos que el usuario QUIERE COMER en su mensaje. "
            'Devuelve SOLO un JSON: {"foods": [{"nombre": "...", "cantidad": <número o null>, '
            '"unidad": "g"|"ud"|null}]}. '
            "Incluye cada alimento que el usuario quiera, tenga o no cantidad. "
            "MUY IMPORTANTE: NO incluyas alimentos que el usuario está NEGANDO o EXCLUYENDO "
            "(\"sin pan\" -> el pan NO va; \"no quiero pescado\" -> el pescado NO va; "
            "\"nada de arroz\" -> el arroz NO va; \"sin el pan\" -> el pan NO va). "
            "Tampoco incluyas alimentos mencionados solo como referencia o comparación. "
            "'nombre': el alimento en singular, sin cantidades. "
            "'cantidad': el número que el usuario indique para ese alimento, o null si no indica ninguno. "
            "'unidad': \"g\" para gramos o kilos, \"ud\" para unidades/piezas/lonchas, o null si no se indica. "
            "Interpreta números pegados o mal escritos (\"yogurt100 g\" -> yogur 100 g, "
            "\"100 de avena\" -> avena 100 g, \"4 huevos\" -> huevos 4 ud). "
            "Convierte medidas caseras a gramos: \"un cazo/scoop de proteína\" -> 30 g, "
            "\"una cucharada de aceite/crema\" -> 10 g, \"un puñado de frutos secos\" -> 30 g, "
            "\"un chorrito de aceite\" -> 5 g, \"un vaso de leche\" -> 250 g. "
            "\"medio/media X\" -> cantidad 0.5 con unidad \"ud\" (\"media palta\" -> aguacate 0.5 ud). "
            'Ejemplo: "pollo y arroz" -> {"foods": [{"nombre": "pollo", "cantidad": null, "unidad": null}, '
            '{"nombre": "arroz", "cantidad": null, "unidad": null}]}. '
            'Ejemplo: "lo mismo que ayer pero sin el pan" -> {"foods": []} (el pan está excluido '
            "y \"lo mismo que ayer\" no nombra alimentos concretos). "
            'Devuelve {"foods": []} SOLO si el mensaje no menciona ningún alimento que el usuario quiera. No añadas nada más.'
        )
        # El modelo es estocástico y a veces devuelve {"foods": []} para un alimento claro, o falla
        # de forma transitoria (timeout, 429). Reintentamos si sale VACÍO o hay excepción, para que
        # un tropiezo puntual NO haga que un alimento válido caiga en "no reconocí". Cada intento usa
        # un chat nuevo para no arrastrar el historial de un envío fallido.
        raw = []
        last_err = None
        for intento in range(2):
            chat = LlmChat(api_key=self.api_key, system_message=prompt).with_model(
                "openai", os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
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
            "completas": len(self.state.get("saved_meals", [])),
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
                "guardada": key in self.state.get("saved_meals", []),
                "es_actual": idx == self.state["comida_actual"],
                # Lo que lleva cada comida, para que el resumen del dia se pueda pintar
                # en condiciones en vez de como una lista de texto.
                "alimentos": [
                    {"nombre": a.get("nombre"),
                     "cantidad_display": a.get("cantidad_display") or f"{a.get('cantidad_g', 0)}g",
                     "macros": a.get("macros", {}),
                     "categorias": (a.get("alimento") or {}).get("categorias") or a.get("categorias")}
                    for a in comida.get("alimentos", [])
                ],
            })
        return out

    def go_to_meal(self, idx: int) -> bool:
        """Salta a una comida concreta (para editar una ya guardada o volver atrás)."""
        if 1 <= int(idx) <= self.total_meals():
            self.state["comida_actual"] = int(idx)
            self.state["step"] = "building_meal"
            return True
        return False

    def resolve_meal_ref(self, ref) -> Optional[int]:
        """Convierte una referencia de comida del usuario ('2', 'comida 2', 'post',
        'post-entreno', 'intra', 'última'...) en el índice 1-based dentro de meal_order.
        Los NÚMEROS refieren a las comidas principales (C1..Cn), NO a la posición en
        meal_order (que intercala Intra/Post): "comida 2" es siempre C2 aunque el
        post-entreno vaya antes. Devuelve None si no se reconoce."""
        order = self.state.get("meal_order") or []
        if not order:
            return None

        def idx_of(key):
            return order.index(key) + 1 if key in order else None

        if isinstance(ref, bool):
            return None
        if isinstance(ref, (int, float)):
            return idx_of(f"C{int(ref)}")
        if not isinstance(ref, str):
            return None
        t = self._norm_text(ref)
        if "post" in t:
            return idx_of("Post")
        if "intra" in t:
            return idx_of("Intra")
        if "ultim" in t:
            return len(order)
        if "actual" in t or t in ("esta", "esta comida"):
            return self.state["comida_actual"]
        m = re.search(r"\d+", t)
        if m:
            return idx_of(f"C{int(m.group())}")
        if "unic" in t or "bloque" in t:
            return idx_of("C1")
        return None

    def list_meals_text(self, idx: int = None) -> str:
        """Texto con el contenido de una comida (idx 1-based en meal_order) o de todas,
        para responder por texto a 'lístame la comida 2' / 'qué comidas tengo'."""
        meals = self.get_meals_status()
        if idx is not None:
            meals = [m for m in meals if m["idx"] == idx]
            if not meals:
                return "No encontré esa comida."
        lines = []
        for m in meals:
            comida = self.state["comidas_completadas"].get(m["key"], {})
            alimentos = comida.get("alimentos", [])
            marca = " (comida actual)" if m["es_actual"] else ""
            if m["cuadrado"] and alimentos:
                estado = "✅ cuadrada"
            elif not alimentos:
                estado = "vacía"
            elif m.get("guardada"):
                estado = "guardada, sin cuadrar"
            else:
                estado = "incompleta"
            lines.append(f"**{m['nombre']}**{marca} · {estado}")
            for a in alimentos:
                mm = a.get("macros", {})
                lines.append(
                    f"• {a.get('nombre')}: {a.get('cantidad_display', '')} "
                    f"(proteína {mm.get('P', 0)} g · hidratos {mm.get('H', 0)} g · grasa {mm.get('G', 0)} g)"
                )
            r = m.get("restante", {})
            nombres_m = {"P": "proteína", "H": "hidratos", "G": "grasa"}
            faltan = [f"{nombres_m[k]} {r.get(k, 0)} g" for k in ("P", "H", "G") if r.get(k, 0) > 0]
            pasan = [f"{nombres_m[k]} {abs(r.get(k, 0))} g" for k in ("P", "H", "G") if r.get(k, 0) < 0]
            partes = []
            if faltan:
                partes.append("Falta: " + " · ".join(faltan))
            if pasan:
                partes.append("Te pasas: " + " · ".join(pasan))
            lines.append(" | ".join(partes) if partes else "Cuadrada al gramo.")
            lines.append("")
        lines.append('Puedes decirme "edita la comida 2", "borra la comida 3" o "vacía el post-entreno".')
        return "\n".join(lines).strip()

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
        self.state.setdefault("seen_sugg", {}).pop(key, None)
        if key in self.state.get("saved_meals", []):
            self.state["saved_meals"].remove(key)
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

    @staticmethod
    def _raiz(palabra: str) -> str:
        """La raiz de una palabra en español, sin genero ni numero.

        Nadie pide la comida en la forma exacta en que esta escrita en la base. Alguien
        pide "tostadas" y en el catalogo pone "Pan tostado": misma cosa, y la busqueda
        no los unia porque comparaba letra a letra. Aqui "tostadas", "tostada", "tostado"
        y "tostados" caen todos en "tostad".

        Se queda corta a proposito: quitar plural y la vocal final cubre la mayoria del
        castellano sin inventar parentescos. Devuelve "" si la raiz queda tan corta que
        emparejaria cualquier cosa ("pavo" -> "pav" no vale).
        """
        p = (palabra or "").strip()
        if p.endswith("es") and len(p) > 4:
            p = p[:-2]
        elif p.endswith("s") and len(p) > 3:
            p = p[:-1]
        if p and p[-1] in "ao" and len(p) > 4:
            p = p[:-1]
        return p if len(p) >= 4 else ""

    @classmethod
    def _regex_raiz(cls, palabra: str) -> str:
        """Patron que casa la palabra en cualquier genero y numero. "" si no aplica."""
        raiz = cls._raiz(cls._norm_text(palabra))
        # La "s" suelta hace falta cuando la raíz conserva su vocal ("pavo" -> "pavos");
        # sin ella el plural de las palabras cortas se quedaba fuera.
        return rf"\b{raiz}(s|a|o|as|os|es)?\b" if raiz else ""

    @staticmethod
    def _clave_fonetica(s: str) -> str:
        """Como suena, para comparar nombres de alimentos escritos deprisa.

        La mitad de España sesea y en el movil se escribe rapido: "sumo" por "zumo",
        "cosido" por "cocido", "berengena" por "berenjena". Comparando por escrito, un
        cliente que pedia "la mitad de sumo" recibia "sumo: no encontrado" aunque tenia
        el zumo delante en la lista.

        Se pliegan los sonidos que se confunden de verdad en español:
          z, ce/ci -> s      (seseo)
          ll -> y            (yeismo)
          v -> b, h -> nada, qu/k -> k, gue/gui -> ge/gi
        Y las dobles, que solo se notan al escribir.
        """
        import unicodedata
        t = (s or "").lower()
        t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
        t = t.replace("qu", "k").replace("gue", "ge").replace("gui", "gi")
        t = re.sub(r"c(?=[ei])", "s", t)
        t = t.replace("z", "s").replace("ll", "y").replace("v", "b").replace("h", "")
        t = t.replace("y", "i").replace("c", "k")   # "aceyte" == "aceite"
        return re.sub(r"(.)\1+", r"\1", t)   # dobles: "arrós" == "aros"

    def _match_meal_food_index(self, name: str, strict: bool = False) -> int:
        """Índice del alimento de la comida actual que mejor coincide con `name`, o -1.

        `strict=True` exige que TODAS las palabras pedidas estén en el nombre Y que la
        primera palabra significativa del nombre esté entre las pedidas. Evita el desastre
        de que "claras de huevo" actualice los "Huevos enteros L" (comparten "huevo") o que
        "añade 2 huevos" cambie la cantidad de las claras ya presentes."""
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
            if strict:
                if not all(t in fn for t in q_tokens):
                    continue
                fn_sig = [w for w in re.findall(r"\w+", fn)
                          if w not in self._MATCH_STOPWORDS and len(w) > 1]
                head = fn_sig[0] if fn_sig else ""
                if not any(t in head or head in t for t in q_tokens):
                    continue
            score = sum(1 for t in q_tokens if t in fn)
            # Segunda pasada, por como SUENA: "sumo" encuentra el zumo, "cosido" el cocido.
            # Puntua menos que la coincidencia literal para que esta siempre gane.
            if not score:
                fn_fon = self._clave_fonetica(f.get("nombre", ""))
                score = sum(0.5 for t in q_tokens if self._clave_fonetica(t) in fn_fon)
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

    async def set_food_quantity(self, name: str, cantidad: float = None, unidad: str = None,
                                incrementar: bool = False) -> dict:
        """Fija manualmente la cantidad de un alimento, con paridad con la calculadora: NO topa
        por los macros restantes (permite SOBREPASAR el objetivo). Si el alimento ya está en la
        comida, actualiza su cantidad; si no, lo añade a la cantidad indicada.

        `unidad`: "g" (gramos), "ud" (unidades) o None (se resuelve según el alimento:
        unidades si es un alimento contable, gramos en caso contrario).
        `incrementar`: si True, SUMA la cantidad a lo que ya hay de ese alimento en la comida
        ("agrega un huevo": 2 -> 3), en vez de fijar el total."""
        key = self.current_meal_key()
        # 1) Match ESTRICTO contra la comida (evita actualizar un alimento parecido pero
        #    distinto). 2) Si no, resolver contra la base y ver si ESE alimento ya está.
        idx = self._match_meal_food_index(name, strict=True)
        if idx >= 0:
            alimento = self.state["comidas_completadas"][key]["alimentos"][idx].get("alimento")
            if not alimento:
                matches = await self.search_foods(name, limit=1)
                alimento = matches[0] if matches else None
        else:
            matches = await self.search_foods(name, limit=1)
            alimento = matches[0] if matches else None
            if alimento:
                # ¿El alimento resuelto ya está en la comida? ("cambia el pollo a 200g"
                # resuelve a "Pechuga de pollo", que sí está) -> actualizar, no duplicar.
                objetivo_norm = self._norm_text(alimento.get("nombre", ""))
                for i, f in enumerate(self.state["comidas_completadas"].get(key, {}).get("alimentos", [])):
                    if self._norm_text(f.get("nombre", "")) == objetivo_norm:
                        idx = i
                        break
        if not alimento:
            return {"ok": False, "nombre": name}
        # Coincidencia solo parcial ("filete de unicornio" -> pollo empanado): NO añadir
        # en silencio; devolver la sugerencia para que el usuario confirme.
        if alimento.get("_match_parcial"):
            return {"ok": False, "nombre": name, "sugerencia": alimento.get("nombre")}
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
        # Incremento ("agrega un huevo"): sumar lo pedido a lo que ya hay de ese alimento
        # en la comida, en vez de fijar el total. Si aún no está, equivale a añadir esa cantidad.
        if incrementar and idx >= 0:
            actual = self.state["comidas_completadas"][key]["alimentos"][idx]
            cantidad_g = float(actual.get("cantidad_g") or actual.get("cantidad") or 0) + cantidad_g
        # Tope de cordura: nadie come 999999 kg de lentejas; rechazar en vez de aceptar
        # cantidades imposibles con un simple aviso.
        if cantidad_g > 5000:
            return {"ok": False, "nombre": alimento.get("nombre", name), "excesivo": True}
        macros = self._macros_at(alimento, cantidad_g)
        if idx >= 0:
            display = self._update_food_at(key, idx, alimento, cantidad_g, macros)
        else:
            self._ensure_meal(key)
            display = self._append_food(key, alimento, cantidad_g, macros)
        return {"ok": True, "nombre": alimento.get("nombre"),
                "cantidad_display": display, "macros": macros,
                "cantidad_g": cantidad_g,
                "parcial": alimento.get("_match_parcial"),
                # Errata corregida por parecido: quien llama lo cuenta al usuario.
                "corregido_a": alimento.get("_corregido_a"),
                "max_razonable": self._max_auto_g(alimento)}

    def _max_auto_g(self, alimento: dict) -> float:
        """Tope de gramos con sentido humano para el dimensionado AUTOMÁTICO de un
        alimento (no aplica a cantidades que el usuario fija explícitamente)."""
        config = get_food_config(alimento)
        cats = parse_categories(alimento.get("categorias", []))
        cat = cats[0] if cats else "0"
        racion = float(alimento.get("racion", 100) or 100)
        return self._get_max_cantidad_razonable(cat, config, racion)

    def _size_food(self, alimento: dict, restante: dict):
        """Dimensiona un alimento contra los macros restantes con el MISMO motor que la
        calculadora (calma_suggest), TOPADO a una cantidad con sentido humano (nadie se
        toma 500 g de salsa de soja para llegar a la proteína).
        Devuelve (cantidad_g, macros{P,H,G}) o None si no cabe."""
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
            # No cabe en lo que queda. Se pone su racion minima igualmente: el chat es el
            # modo manual, lo que pide el usuario entra y en el resumen ya se ve lo que
            # sobra. Antes se rechazaba y el alimento no aparecia por ningun lado.
            cant = cantidad_minima(a)
            if cant <= 0:
                return None
        es_unidad = bool(a.get("unidades"))
        racion = float(a.get("racion") or 100) or 100.0
        cantidad_g = (cant * racion) if es_unidad else cant

        # Tope de sensatez: si el cálculo pide más de lo que una persona se pondría
        # en el plato, recortar (la comida quedará "faltan X" y se completa con otro alimento).
        max_g = self._max_auto_g(alimento)
        minimo_g = cantidad_minima(a) * (racion if es_unidad else 1)
        if cantidad_g > max_g >= minimo_g:
            if es_unidad:
                cant = max(1.0, math.floor(max_g / racion))
                cantidad_g = cant * racion
            else:
                from calma_suggest import step_granel, _round_step
                cant = _round_step(max_g, step_granel(a), floor=True) or max_g
                cantidad_g = cant

        m = macros_at(a, cant)
        macros = {"P": round(m["proteinas"], 1), "H": round(m["hidratos"], 1), "G": round(m["grasas"], 1)}
        return cantidad_g, macros

    def _razon_no_cabe(self, alimento: dict, restante: dict) -> str:
        """Explica en lenguaje humano por qué un alimento no entra en lo que queda
        de la comida (en vez del críptico 'Mínimo excede G restante')."""
        import copy
        from calma_suggest import aplicar_regla_macros, macros_at, cantidad_minima
        a = copy.deepcopy(alimento)
        aplicar_regla_macros(a)
        cant_min = cantidad_minima(a)
        m = macros_at(a, cant_min)
        aportes = {"P": m["proteinas"], "H": m["hidratos"], "G": m["grasas"]}
        nombres = {"P": "proteína", "H": "hidratos", "G": "grasa"}
        es_unidad = bool(a.get("unidades"))
        racion = float(a.get("racion") or 100) or 100.0
        min_g = int(round(cant_min * racion)) if es_unidad else int(round(cant_min))
        for k in ("G", "H", "P"):  # primero el bloqueo más habitual (grasa en peri)
            resta = float(restante.get(k, 0))
            if aportes[k] > 0.5 and resta < aportes[k]:
                queda = f"solo quedan {max(0.0, resta):.0f} g" if resta > 0.5 else "ya no queda nada"
                return (f"Lo encontré, pero no cabe: su mínimo ({min_g} g) aporta "
                        f"{aportes[k]:.0f} g de {nombres[k]} y en esta comida {queda} de {nombres[k]}")
        return "Lo encontré, pero no cabe en lo que queda de esta comida"

    # Preposiciones/artículos que no cuentan como "palabra significativa" del alimento.
    _STOP_TERMINO = {"de", "del", "la", "el", "los", "las", "con", "sin", "al", "a",
                     "en", "un", "una", "y", "o", "para"}

    # Lo que la gente pide por CONCEPTO y no por nombre. Buscarlo como texto sacaba
    # "mostaza dulce" o "maiz dulce": llevan la palabra y no son un postre.
    _CONCEPTOS = {
        "dulce": ["31", "34", "35", "36", "37", "43", "44"],
        "dulces": ["31", "34", "35", "36", "37", "43", "44"],
        "postre": ["34", "35", "36", "44"],
        "postres": ["34", "35", "36", "44"],
        "chuche": ["37"], "chuches": ["37"],
        "salado": ["38", "49"], "aperitivo": ["38"], "aperitivos": ["38"],
        "picar": ["38", "17.2"], "snack": ["38", "29", "47"], "snacks": ["38", "29", "47"],
    }

    async def _alimentos_de_categorias(self, cats: list) -> list:
        """Todos los alimentos de unas categorias del metodo (con sus subcategorias)."""
        from calculator import cat_in_list, get_categoria_principal, get_all_foods_cached
        todos = await get_all_foods_cached(self.db)
        return [a for a in todos if cat_in_list(get_categoria_principal(a), cats)]

    async def _opciones_ambiguas(self, nombre: str, restante: dict, max_op: int = 6,
                                 cantidad: float = None, unidad: str = None):
        """Si `nombre` es un término GENÉRICO (p.ej. 'lomo', 'pavo') que en la base
        corresponde a alimentos de tipos dispares (fiambre vs pechuga fresca, embutido vs
        salmón), devuelve una lista de OPCIONES para que el usuario elija, en vez de
        adivinar una. Devuelve None si el término es específico o homogéneo.

        Con `cantidad` (el usuario dijo p.ej. "150g de pavo"): las opciones se muestran a
        ESA cantidad fija (llevan cantidad_fija/cantidad_g) y al elegir una se respeta."""
        sig = [w for w in self._norm_text(nombre).split()
               if w not in self._STOP_TERMINO and len(w) > 1]
        # Solo desambiguamos términos de UNA palabra significativa ("lomo", "filete").
        # Si el usuario ya concretó ("lomo embuchado", "lomo de salmón"), se respeta.
        if len(sig) != 1:
            return None
        termino = sig[0]

        # "Algo dulce", "algo salado": son CONCEPTOS, no nombres. Buscarlos por texto sacaba
        # mostaza dulce y maíz dulce, que llevan la palabra y no son lo que nadie quiere de
        # postre. Se resuelven por categoría del método.
        cats_concepto = self._CONCEPTOS.get(termino)
        concepto = bool(cats_concepto)
        if concepto:
            cands = await self._alimentos_de_categorias(cats_concepto)
            if len(cands) < 2:
                return None
        else:
            cands = await self.search_foods(nombre, limit=30)  # también rellena _CANONICAL_TERMS
        # Términos con elección por defecto (arroz, atún, tomate, pollo…): no se pregunta.
        if not concepto and termino in getattr(NutritionChatbot, "_CANONICAL_TERMS", frozenset()):
            return None
        # Solo candidatos que REALMENTE contienen el término (evita que "arroz" arrastre
        # "azúcar blanco"/"pescado blanco" por compartir la palabra "blanco"). Cuenta
        # también en otro género o número: quien pide "tostadas" quiere ver "Pan tostado".
        raiz_pat = self._regex_raiz(termino)
        if not concepto:
            cands = [c for c in cands
                     if termino in self._norm_text(c.get("nombre", ""))
                     or (raiz_pat and re.search(raiz_pat, self._norm_text(c.get("nombre", ""))))]
            if len(cands) < 2:
                return None
        # ¿Coincidencia parcial? (search no tenía el término tal cual). No forzamos opciones.
        if not concepto and any(c.get("_match_parcial") for c in cands):
            return None

        # Si hay un alimento que se llama EXACTAMENTE como lo pedido, no hay nada que
        # desambiguar: es ese. Pedir "bacon" sacaba seis alimentos "sabor bacon" y escondía
        # el propio "Bacon", porque la lista de opciones descarta lo que no cabe en lo que
        # queda de la comida y el bacon (42 g de grasa por 100) se caía por el mínimo de su
        # categoría. Preguntar "¿cuál de estos?" cuando el usuario ha dicho el nombre exacto
        # de un alimento no tiene sentido; esto solo afecta a términos con alimento propio
        # (bacon, merluza, salmón...), no a los ambiguos de verdad (pavo, lomo, pollo).
        pedido = self._norm_text(nombre).strip()
        if not concepto and any(self._norm_text(c.get("nombre", "")).strip() == pedido for c in cands):
            return None

        # Subfamilias (nivel 2) distintas entre los candidatos: si hay 2+, es ambiguo de
        # verdad. Cubre tanto familias enteras (carne 2 vs pescado 3, "lomo") como tipos
        # dispares dentro de una familia (fiambre 2.1 vs carne fresca 2.2, "pavo").
        # Si todos son de la misma subfamilia (p.ej. toda fruta fresca 11.1), se auto-elige.
        cats2 = set()
        for c in cands:
            cc = parse_categories(c.get("categorias"))
            if cc:
                cats2.add(".".join(cc[0].split(".")[:2]))
        if not concepto and len(cats2) < 2:
            return None

        # Construir opciones IGUAL que el buscador de la calculadora (petición 2026-07-17):
        # mismo motor (calma_suggest) para la cantidad sugerida y misma ordenación por
        # diferenciaDeMacros ascendente (el que mejor cuadra con lo que falta, primero).
        # Lo que no cabe en lo que queda se excluye, como hace la calculadora.
        from calma_suggest import diferencia_de_macros
        remaining = {
            "proteinas": float(restante.get("P", 0)),
            "hidratos": float(restante.get("H", 0)),
            "grasas": float(restante.get("G", 0)),
        }
        # Cantidad fija pedida por el usuario (mismas conversiones que set_food_quantity)
        cant_fija, u_fija = cantidad, unidad
        if cant_fija is not None and u_fija == "kg":
            cant_fija, u_fija = cant_fija * 1000, "g"

        rankeados = []
        for c in cands:
            if cant_fija is not None:
                # A la cantidad pedida, tal cual (sin topes: la ha fijado el usuario)
                u = u_fija if u_fija in ("g", "ud") else ("ud" if c.get("unidades") else "g")
                if u == "ud":
                    racion = float(c.get("racion") or 100) or 100.0
                    cantidad_g = cant_fija * racion
                else:
                    cantidad_g = cant_fija
                macros = self._macros_at(c, cantidad_g)
            else:
                sized = self._size_food(c, restante)
                if not sized:
                    # No cabe en lo que queda de la comida: no ofrecerla como opción
                    # (antes salía "Lomo de wagyu (0 g · 0 g · 0 g)" sin cantidad, confuso).
                    continue
                cantidad_g, macros = sized
            contrib = {"proteinas": macros["P"], "hidratos": macros["H"], "grasas": macros["G"]}
            dif = diferencia_de_macros(contrib, remaining)
            # Orden: primero lo que de verdad ES lo pedido, luego el genérico, luego macros.
            #
            # Quien pide "tostadas" quiere tostadas. Ampliar la búsqueda a otros géneros
            # trajo "Edamame tostado" y "Copos de maíz tostado", que llevan la palabra de
            # adjetivo; sin este primer criterio se colaban ANTES que las tostadas. Por eso
            # la forma exacta manda: un edamame no adelanta a una tostada.
            nombre_c = self._norm_text(c.get("nombre") or "")
            # Misma palabra en singular o plural, pero NO en otro género: "tostadas" case
            # con "Tostada sin gluten", y "tostado" (adjetivo) se queda en el segundo bloque.
            base_term = termino[:-1] if termino.endswith("s") and len(termino) > 3 else termino
            exacto = 0 if (concepto or re.search(rf"{re.escape(base_term)}s?", nombre_c)) else 1
            # Genérico primero, marca después (petición 2026-08-02). En la base, genérico =
            # NO tiene URL. Es lo neutro: el que pide "tostadas" quiere la tostada de toda
            # la vida antes que la de una marca concreta.
            es_marca = 1 if c.get("url") else 0
            rankeados.append((exacto, es_marca, dif, c.get("nombre") or "", c, cantidad_g, macros))
        rankeados.sort(key=lambda t: (t[0], t[1], t[2], t[3]))

        # Para no repetir 6 marcas de lo mismo, una opción por TIPO real: agrupamos por las
        # 2 primeras palabras SIGNIFICATIVAS del nombre sin marca ("fiambre pechuga" vs
        # "pechuga pavo" vs "jamon pavo") y de cada grupo queda el MEJOR clasificado.
        def clave_tipo(nombre_al):
            base = self._norm_text((nombre_al or "").split("(")[0])
            sig_w = [w for w in base.split() if w not in self._STOP_TERMINO and len(w) > 1]
            return " ".join(sig_w[:2])

        vistos, opciones = set(), []
        for _exacto, _es_marca, dif, _nombre, c, cantidad_g, macros in rankeados:
            clave = clave_tipo(c.get("nombre"))
            if not clave or clave in vistos:
                continue
            vistos.add(clave)
            disp = self._format_cantidad(cantidad_g, c, get_food_config(c))
            op = {
                "alimento_id": c.get("id"), "nombre": (c.get("nombre") or "").strip(),
                "cantidad_display": disp, "macros": macros,
            }
            if cant_fija is not None:
                op["cantidad_fija"] = True
                op["cantidad_g"] = cantidad_g
            opciones.append(op)
            if len(opciones) >= max_op:
                break

        # Que siempre asome un genérico si lo hay. Los genéricos van delante, pero solo
        # dentro de su bloque de relevancia: si el término exacto son todo marcas (con
        # "tostad" hay 48 de marca y 3 genéricos), la lista se llenaba de marcas y el
        # "Pan tostado" de toda la vida no se veía nunca. Este hueco lo garantiza.
        ids = {o["alimento_id"] for o in opciones}
        if opciones and not any(not (r[4].get("url")) for r in rankeados if r[4].get("id") in ids):
            gen = next((r for r in rankeados if not r[4].get("url") and r[4].get("id") not in ids), None)
            if gen:
                _e, _g, _d, _n, c, cantidad_g, macros = gen
                op = {
                    "alimento_id": c.get("id"), "nombre": (c.get("nombre") or "").strip(),
                    "cantidad_display": self._format_cantidad(cantidad_g, c, get_food_config(c)),
                    "macros": macros,
                }
                if cant_fija is not None:
                    op["cantidad_fija"], op["cantidad_g"] = True, cantidad_g
                if len(opciones) >= max_op:
                    opciones[-1] = op
                else:
                    opciones.append(op)
        return opciones if len(opciones) >= 2 else None

    async def _mas_opciones_termino(self, termino: str):
        """Más opciones DEL MISMO tipo de alimento, sin repetir las ya enseñadas.

        Antes, pedir "¿hay otras opciones de tostadas?" caía en las sugerencias generales
        y contestaba con callos y batidos de proteína. Si ha pedido tostadas, se le enseñan
        tostadas; y cuando de verdad no quedan, se dice y se le pregunta, en vez de
        cambiarle de tema sin avisar.

        Devuelve None si el término no da ninguna lista (que lo trate el flujo normal).
        """
        vistos = set(self.state.get("termino_vistos") or [])
        restante = self.get_remaining_macros()
        opciones = await self._opciones_ambiguas(termino, restante, max_op=6 + len(vistos))
        if opciones is None:
            # No hay lista para este término: que siga el camino de siempre.
            return None

        nuevas = [o for o in opciones if o.get("alimento_id") not in vistos][:6]
        if not nuevas:
            # Honestidad: no quedan más. Y en vez de dejarle en un callejón, se le
            # ofrece la salida (esto es lo que el chat debe hacer cuando no sabe seguir).
            self.state["last_options"] = []
            return {
                "action": "no_foods",
                "message": (f"No me quedan más opciones de {termino} que cuadren con lo que "
                            f"te falta. ¿Quieres que te sugiera otra cosa parecida, o prefieres "
                            f"decirme tú qué te apetece?"),
                "day_overview": self.get_day_overview(),
            }

        self.state["last_options"] = nuevas
        self.state["last_termino"] = termino
        self.state["termino_vistos"] = list(vistos) + [o.get("alimento_id") for o in nuevas]
        return {
            "action": "no_foods",
            "message": ((f"Más opciones de {termino}." if vistos else f"Opciones de {termino}.") + f" Dime cuál quieres (p.ej. \"el 1\"):\n"
                        f"{self._format_options_lines(nuevas)}"),
            "day_overview": self.get_day_overview(),
        }

    # Relleno que no distingue una elección ("quiero el primero", "venga, la 2", "mejor ese")
    _PICK_FILLER = {"el", "la", "lo", "los", "las", "un", "una", "unas", "unos", "opcion",
                    "numero", "quiero", "dame", "pon", "ponme", "anade", "anademe", "mete",
                    "meteme", "pilla", "coge", "elige", "elijo", "prefiero", "ese", "esa",
                    "esas", "esos", "este", "esta", "mejor", "de", "del", "por", "favor",
                    "porfa", "porfi", "si", "vale", "venga", "pues", "ok", "okay", "dale",
                    "va", "anda", "oye", "entonces", "tio", "jaja", "jajaja", "y", "e",
                    "a", "al", "que", "q", "pa", "para", "con", "me", "gusta"}
    _ORDINALES = {"primero": 1, "primera": 1, "segundo": 2, "segunda": 2,
                  "tercero": 3, "tercera": 3, "cuarto": 4, "cuarta": 4,
                  "quinto": 5, "quinta": 5, "sexto": 6, "sexta": 6}

    def _format_options_lines(self, opciones: list) -> str:
        """Lista numerada de opciones para que el usuario elija por texto."""
        lineas = []
        for i, s in enumerate(opciones, 1):
            m = s.get("macros", {})
            cant = f" · {s['cantidad_display']}" if s.get("cantidad_display") else ""
            lineas.append(f"{i}. {(s.get('nombre') or '').strip()}{cant} "
                          f"(proteína {m.get('P', 0)} g · hidratos {m.get('H', 0)} g · grasa {m.get('G', 0)} g)")
        return "\n".join(lineas)

    def _match_option_pick(self, text: str):
        """Si hay opciones pendientes (sugerencias/desambiguación) y el mensaje es una
        elección ("la 1", "venga, el segundo", "ponme la 4, las claras esas", "salmón"),
        devuelve ("ok", alimento_id). Si es un intento de elección fuera de rango ("la 9"
        con 6 opciones), devuelve ("range", n_opciones). Si no parece una elección, None."""
        opts = self.state.get("last_options") or []
        if not opts:
            return None
        norm = self._norm_text(text)
        toks = [t for t in re.findall(r"\w+", norm) if t not in self._PICK_FILLER]
        # Si el mensaje habla de comidas o de otra acción ("edita la comida 2", "vacía la 1",
        # "guarda y siguiente"), NO es una elección de la lista: que lo resuelva el router.
        _NO_PICK = {"comida", "comidas", "edita", "editar", "ve", "vete", "abre", "lista",
                    "listame", "vacia", "vaciame", "borra", "borrame", "elimina", "quita",
                    "quitame", "guarda", "guardar", "siguiente", "resumen", "cambia",
                    "cambiame", "post", "intra", "entreno", "dia", "falta", "sugiere",
                    "sugiereme", "recomienda", "recomiendame", "otras", "otros", "gramos"}
        if any(t in _NO_PICK for t in toks):
            return None

        def resolver_idx(idx):
            if 1 <= idx <= len(opts):
                return ("ok", opts[idx - 1])  # la opción completa (puede llevar cantidad fija)
            return ("range", len(opts))

        # Número u ordinal entre los tokens ("venga la 1", "ponme la 4, las claras esas"):
        # el resto de tokens, si los hay, deben ser descripción compatible o irrelevante.
        numeros = [t for t in toks if t.isdigit() and len(t) <= 2]
        ordinales = [self._ORDINALES[t] for t in toks if t in self._ORDINALES]
        if len(numeros) == 1 and not ordinales:
            idx = int(numeros[0])
            resto = [t for t in toks if not t.isdigit()]
            # Si además nombra algo, que no contradiga: o describe la opción elegida,
            # o no coincide con ninguna otra opción.
            if 1 <= idx <= len(opts):
                nombre_idx = self._norm_text(opts[idx - 1].get("nombre", ""))
                # Las palabras extra deben DESCRIBIR la opción elegida ("ponme la 4, las
                # claras esas"). Si nombran otra cosa ("añade 2 huevos": el 2 es una
                # CANTIDAD de otro alimento), NO es una elección: sigue el flujo normal.
                contradice = resto and not all(t in nombre_idx for t in resto)
                if not contradice:
                    return resolver_idx(idx)
            elif len(toks) <= 3:
                return resolver_idx(idx)  # "la 9" -> avisar del rango
        if len(ordinales) == 1 and not numeros and len(toks) <= 3:
            return resolver_idx(ordinales[0])
        if not toks:
            return None
        if len(toks) == 1 and toks[0] in ("ultimo", "ultima"):
            return resolver_idx(len(opts))
        # Por nombre: TODOS los tokens del usuario deben estar en el nombre de UNA sola opción
        # ("salmón" -> "Lomo de salmón"). Si nombra algo que no es una opción, sigue el flujo normal.
        if len(toks) <= 4:
            matches = [o for o in opts
                       if all(t in self._norm_text(o.get("nombre", "")) for t in toks)]
            if len(matches) == 1:
                return ("ok", matches[0])
        return None

    def _ensure_meal(self, key: str):
        if key not in self.state["comidas_completadas"]:
            self.state["comidas_completadas"][key] = {"alimentos": [], "macros": {"P": 0, "H": 0, "G": 0}}

    def _append_food(self, key: str, alimento: dict, cantidad_g: float, macros: dict):
        self._ensure_meal(key)
        nombre = (alimento.get("nombre", "") or "").strip()
        # Si el MISMO alimento ya está en la comida, fusionar (sumar gramos y recalcular)
        # en vez de crear una línea duplicada ("ponme más claras").
        for i, f in enumerate(self.state["comidas_completadas"][key]["alimentos"]):
            if self._norm_text(f.get("nombre", "")) == self._norm_text(nombre):
                total_g = f.get("cantidad_g", f.get("cantidad", 0)) + cantidad_g
                macros_total = self._macros_at(alimento, total_g)
                return self._update_food_at(key, i, alimento, total_g, macros_total)
        config = get_food_config(alimento)
        display = self._format_cantidad(cantidad_g, alimento, config)
        self.state["comidas_completadas"][key]["alimentos"].append({
            "nombre": nombre,
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

    def _recalibrar_dia(self):
        """Calibración progresiva de la proteína vegetal (spec 17-07-2026) sobre TODO
        el día del chat: recorre meal_order en orden cronológico con los acumulados
        de cereales+panes y frutos secos, y reescribe los macros por alimento y los
        totales de cada comida. El tramo de una comida solo depende de las anteriores,
        así que editar una comida recalcula esa y las posteriores, nunca las previas."""
        from calibracion_dia import calibrar_dia
        order = self.state.get("meal_order") or []
        if not order:
            return
        NEUTRO = {"categorias": "", "proteinas": 0, "hidratos": 0, "grasas": 0, "racion": 100}
        meals = []
        for k in order:
            comida = self.state["comidas_completadas"].get(k) or {}
            fila = [((f.get("alimento") or NEUTRO),
                     float(f.get("cantidad_g") or f.get("cantidad") or 0))
                    for f in comida.get("alimentos", [])]
            meals.append((k, fila))
        macros_dia, _ = calibrar_dia(meals)
        for k in order:
            comida = self.state["comidas_completadas"].get(k)
            if not comida:
                continue
            tot = {"P": 0.0, "H": 0.0, "G": 0.0}
            for i, f in enumerate(comida.get("alimentos", [])):
                if f.get("alimento"):  # sin doc del catálogo no se recalibra ese item
                    ef = macros_dia[k][i]
                    f["macros"] = {"P": round(ef["P"], 1), "H": round(ef["H"], 1), "G": round(ef["G"], 1)}
                m = f.get("macros") or {}
                for mk in ("P", "H", "G"):
                    tot[mk] += float(m.get(mk, 0) or 0)
            comida["macros"] = {mk: round(v, 1) for mk, v in tot.items()}

    # Cuando no hay NADA parecido, un "no encontrado" seco deja al usuario sin salida y
    # sin saber si el fallo es suyo o del catálogo. Se le devuelve la pregunta.
    _NO_LO_TENGO = ("No lo tengo con ese nombre. ¿Cómo lo llamas normalmente, "
                    "o quieres que te sugiera algo parecido?")

    def _meal_response(self, foods_added: list, foods_not_found: list, choices: list = None) -> dict:
        # Toda mutación sale por aquí: aplicar la calibración del día antes de responder,
        # y alinear los macros de "foods_added" con lo que ha quedado guardado (calibrado).
        try:
            self._recalibrar_dia()
        except Exception:
            pass  # la respuesta nunca debe romperse por la calibración
        key = self.current_meal_key()
        comida = self.state["comidas_completadas"].get(key, {})
        for fa in (foods_added or []):
            for f in comida.get("alimentos", []):
                if f.get("nombre") == fa.get("nombre"):
                    fa["macros"] = f.get("macros", fa.get("macros"))
                    break
        restante = self.get_remaining_macros()
        cuadrado = all(abs(restante[m]) <= 4 for m in ("P", "H", "G"))
        return {
            "action": "meal_updated",
            "foods_added": foods_added,
            "foods_not_found": foods_not_found,
            "choices": choices or [],
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

    # Detección determinista de "sumar a lo que ya hay" vs "fijar el total". Se hace en
    # código (no en el LLM) porque el router clasificaba "pon un huevo" de forma inestable.
    # "quiero añadir un alimento", "voy a sugerir algo", "puedo meter un producto": pide
    # meter algo pero SIN decir qué. El que elige es él, no el asistente: se le pregunta cuál.
    _RE_ADD_SIN_DECIR_QUE = re.compile(
        r"\b(?:quiero|queria|quisiera|voy a|me gustaria|puedo|podria|deseo)\b"
        r"(?:\W+\w+){0,2}\W+"
        r"(?:anadir|poner|meter|agregar|sumar|echar|sugerir|proponer|introducir|cargar)\b"
        r"[^.?!]*?\b(?:alimento|alimentos|algo|comida|producto|cosa)\b")

    _RE_SET_TOTAL = re.compile(r"\b(a|en)\s+\d|\b(deja|dejalo|baja|bajala|sube|subela|subelo|cambia|solo|unicamente)\b")
    _RE_INCREMENTO = re.compile(r"\b(agrega|anade|suma|echa|mete|otro|otra|un|una)\b|\bmas\b")
    # Marca aditiva "fuerte" (verbo o 'otro'/'más', SIN 'un/una'): la exigimos para
    # incrementar cuando la cantidad viene en GRAMOS ('añade 20 g más de arroz'), para no
    # confundir un objetivo en gramos ('80 g de arroz') con un incremento.
    _RE_INCREMENTO_FUERTE = re.compile(r"\b(agrega|anade|suma|echa|mete|otro|otra)\b|\bmas\b")
    # Nombres de medida vaga: 'un poco/puñado/vaso de X' no es '1 unidad de X'.
    _MEDIDAS_VAGAS = {"poco", "poca", "poquito", "punado", "punadito", "vaso", "vasos",
                      "loncha", "lonchas", "rebanada", "rebanadas", "cucharada", "cucharadita",
                      "cucharadas", "lata", "latas", "pizca", "chorro", "chorrito", "trozo",
                      "trozos", "cacho", "taza", "tazas", "bol", "cazo", "plato", "platos",
                      "racion", "raciones", "porcion", "porciones", "kilo", "kilos", "litro",
                      "litros", "gramo", "gramos"}

    def _tiene_medida_vaga(self, text: str) -> bool:
        return bool(self._MEDIDAS_VAGAS.intersection(self._norm_text(text or "").split()))

    def _a_num(self, w: str):
        """Un número suelto ('2', 'dos', '1.5') -> float, o None."""
        w = self._norm_text(w or "").strip()
        if re.match(r"^\d+(?:[.,]\d+)?$", w):
            return float(w.replace(",", "."))
        return self._NUM_PALABRAS.get(w)

    # Lo que queda cuando alguien dice la cantidad pero no el alimento ("quitale 14
    # gramos"): es una medida, no un nombre. Se resuelve como "el ultimo que pusiste".
    _SOLO_MEDIDA = {"g", "gr", "gramo", "gramos", "kg", "kilo", "kilos",
                    "ud", "uds", "unidad", "unidades"}
    _RE_DEC = re.compile(r"\b(?:quita\w*|kita\w*|qita\w*|saca\w*|elimina\w*|retira\w*|resta\w*)\s+(?:solo\s+)?"
                         r"(un|una|uno|dos|tres|cuatro|cinco|\d+(?:[.,]\d+)?)\b\s*(?:de\s+)?(.*)")
    _RE_DEC_MENOS = re.compile(r"\b(un|una|uno|dos|tres|cuatro|cinco|\d+(?:[.,]\d+)?)\s+(.+?)\s+menos\b")

    def _intento_decremento(self, text: str):
        """Detecta 'quita N X' / 'N X menos' / 'quita uno' -> (nombre|'__ultimo__', n) o None.
        NO se activa con 'deja/solo N' (eso es fijar el total) ni si el mensaje también añade."""
        t = self._norm_text(text or "")
        if re.search(r"\b(deja|dejame|solo|unicamente)\b", t) or "en total" in t:
            return None
        if re.search(r"\b(agrega\w*|anade\w*|ponme|pon|dame|quiero|echa\w*|mete\w*)\b", t) \
                and re.search(r"\b(quita\w*|kita\w*|qita\w*|saca\w*)\b", t):
            return None  # mensaje mixto add+quitar: lo gestiona _intento_mixto / flujo normal
        en_gramos = bool(re.search(r"\d\s*(?:g|gr|gramos?|kg|kilos?)\b", t))
        for rgx, gf, gn in ((self._RE_DEC, 2, 1), (self._RE_DEC_MENOS, 2, 1)):
            m = rgx.search(t)
            if m:
                n = self._a_num(m.group(gn))
                food = m.group(gf).strip()
                # Todos los prefijos de golpe: "quita 100 gramos de la avena" -> "avena".
                # Antes se quitaban en dos pasadas y "gramos de arroz" se quedaba en
                # "de arroz"; colaba de milagro porque luego "de" se filtra como palabra
                # vacia al buscar, pero el nombre llegaba sucio a todo lo demas.
                food = re.sub(r"^(?:(?:g|gr|gramos?|kg|kilos?|ud|uds|unidades?|"
                              r"de|del|la|el|los|las)\s+)+", "", food).strip()
                food = re.sub(r"\s+de\s+(?:la|el|los|las)\s+comida.*$", "", food).strip()
                # "quitale 14 gramos": no ha dicho de QUE, y no hace falta, va del que
                # acaba de poner. Sin esto, el nombre del alimento acababa siendo
                # "gramos" y respondia "no veo ese alimento en la comida".
                if n and (not food or food in self._SOLO_MEDIDA):
                    # "quita uno/dos" sigue siendo en porciones, como siempre. Pero un
                    # numero suelto sin unidad ("quitale 14") no se adivina aqui: se pasa
                    # None y lo decide el alimento, porque en un granel son 14 gramos y
                    # tomarlo como 14 raciones lo borraria entero.
                    if en_gramos:
                        return ("__ultimo__", n, True)
                    if food in ("ud", "uds", "unidad", "unidades"):
                        return ("__ultimo__", n, False)   # lo ha dicho: son unidades
                    palabra = m.group(gn) in self._NUM_PALABRAS
                    return ("__ultimo__", n, False if palabra else None)
                if n and food:
                    return (food, n, en_gramos)
        if re.search(r"\b(?:quita\w*|kita\w*|qita\w*|saca\w*)\s+(?:un|una|uno|otro|otra)\b", t) and " de " not in f" {t} ":
            return ("__ultimo__", 1.0, False)
        return None

    async def decrementar_alimento(self, name: str, n: float, en_gramos: bool = False) -> dict:
        """Reduce un alimento de la comida; si baja a ~0 lo quita. `n` se interpreta como
        gramos si `en_gramos`; si no, como unidades/porciones (para granel contado por
        unidad, p.ej. 'quita 2 claras', se resta n * ración).

        `en_gramos=None` = no dijo la unidad ("quitale 14"): manda el alimento, gramos si
        va a granel y unidades si va por unidades."""
        key = self.current_meal_key()
        alimentos = self.state["comidas_completadas"].get(key, {}).get("alimentos", [])
        if not alimentos:
            return {"ok": False, "vacio": True}
        idx = (len(alimentos) - 1) if name == "__ultimo__" else self._match_meal_food_index(name, strict=False)
        if idx < 0 or idx >= len(alimentos):
            return {"ok": False, "nombre": (None if name == "__ultimo__" else name)}
        item = alimentos[idx]
        alimento = item.get("alimento") or {}
        es_ud = bool(alimento.get("unidades"))
        racion = float(alimento.get("racion") or 100) or 100.0
        cur_g = float(item.get("cantidad_g") or 0)
        nombre = item.get("nombre")
        # Gramos a restar según el tipo de alimento y cómo se pidió.
        if en_gramos is None:
            en_gramos = not es_ud
        if en_gramos:
            resta_g = n
        elif es_ud:
            resta_g = n * racion
        else:
            resta_g = n * racion  # granel contado por porción ("quita 2 claras")
        nuevo_g = cur_g - resta_g
        if nuevo_g <= (0.4 * racion if es_ud else 4):
            self.remove_food_at(idx)
            return {"ok": True, "removido": True, "nombre": nombre}
        nuevo = (nuevo_g / racion) if es_ud else nuevo_g
        res = await self.set_food_quantity(nombre, cantidad=nuevo, unidad=("ud" if es_ud else "g"))
        res["nombre"] = res.get("nombre") or nombre
        return res

    def _intento_quitar_todo(self, text: str):
        """'quita todo el arroz' -> 'arroz' (quitar ESE alimento entero, no vaciar la comida)."""
        m = re.search(r"\b(?:quita\w*|kita\w*|qita\w*|saca\w*|elimina\w*|borra\w*)\s+tod[oa]s?\s+"
                      r"(?:el\s+|la\s+|los\s+|las\s+)?(\w{3,}.*)", self._norm_text(text or ""))
        if not m:
            return None
        food = re.sub(r"\s+de\s+(?:la|esta)\s+comida.*$", "", m.group(1).strip()).strip()
        return food or None

    _RE_REEMPLAZO = re.compile(r"\b(?:cambia\w*|canbia\w*|kambia\w*|canvia\w*|reemplaza\w*|reenplaza\w*|sustituy\w*)\s+(?:el |la |los |las )?(.+?)\s+por\s+(.+)")
    _RE_REEMPLAZO_ENVEZ = re.compile(r"\ben (?:vez|lugar) de\s+(?:el |la |los |las )?(.+?)\s+"
                                     r"(?:pon\w*|ponme|dame|quiero|echa\w*|mete\w*|usa|anade\w*|agrega\w*)\s+(.+)")

    def _intento_reemplazo(self, text: str):
        """'cambia el pollo por pavo' / 'en vez de pollo ponme atún' -> (viejo, spec_nuevo) o None."""
        t = self._norm_text(text or "")
        m = self._RE_REEMPLAZO.search(t) or self._RE_REEMPLAZO_ENVEZ.search(t)
        if not m:
            return None
        old = m.group(1).strip()
        new = re.sub(r"\bpor favor\b.*$", "", m.group(2)).strip()
        if not old or not new or new in ("favor", "fa"):
            return None
        return (old, new)

    def _parse_cantidad_spec(self, spec: str):
        """'100g de pavo' -> (100,'g','pavo'); '2 huevos' -> (2,'ud','huevos'); 'pavo' -> (None,None,'pavo')."""
        t = self._norm_text(spec or "")
        cant, uni, nombre = None, None, spec
        mg = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|kilos?|gr|gramos?|g)\b", t)
        if mg:
            cant = float(mg.group(1).replace(",", ".")); uni = "g"
            if mg.group(2).startswith("k"):
                cant *= 1000
            nombre = re.sub(r"\d+(?:[.,]\d+)?\s*(kg|kilos?|gr|gramos?|g)\b", "", spec, flags=re.I)
        else:
            mn = re.match(r"\s*(un|una|uno|dos|tres|cuatro|cinco|\d+(?:[.,]\d+)?)\s+(.+)", t)
            if mn:
                cant = self._a_num(mn.group(1)); uni = "ud"; nombre = mn.group(2)
        nombre = re.sub(r"^\s*(?:de\s+)?(?:el|la|los|las)\s+", "", nombre.strip(), flags=re.I).strip()
        nombre = re.sub(r"^\s*de\s+", "", nombre, flags=re.I).strip()
        return cant, uni, (nombre or spec).strip()

    # Coletillas que van DETRAS del nombre y no forman parte de el. Sin esto, "la cantidad
    # de zumo que sea la mitad" buscaba un alimento llamado "zumo que sea la mitad".
    _RE_COLETILLA = re.compile(
        r"\s+(?:que\s+sea\w*|que\s+quede\w*|porfa\w*|por\s+favor|please|"
        r"en\s+total|nada\s+mas|solamente|solo)\b.*$")

    def _intento_multiplicador(self, text: str):
        """'el doble'/'la mitad'/'el triple' (de X) -> (factor, nombre|'__ultimo__') o None."""
        t = self._norm_text(text or "")
        factor = (2.0 if re.search(r"\b(doble|duplica\w*)\b", t)
                  else 3.0 if re.search(r"\b(triple|triplica\w*)\b", t)
                  else 0.5 if re.search(r"\b(mitad|halfa?|50\s*%)\b", t)
                  else None)
        if factor is None:
            return None

        # Fuera la expresion del multiplicador: lo que quede es la frase con el alimento.
        # Si no se quita, "la mitad de zumo" y "de zumo la mitad" se comportan distinto.
        sin_mult = re.sub(
            r"\b(?:la\s+|el\s+)?(?:mitad|doble|triple|duplica\w*|triplica\w*|halfa?|50\s*%)\b",
            " ", t)

        # "...de zumo", que es la forma habitual.
        m = re.search(r"\b(?:de|del)\s+(?:la\s+|el\s+|los\s+|las\s+)?(.+)", sin_mult)
        if not m:
            # "que el zumo sea la mitad": aqui el nombre va ANTES del multiplicador.
            m = re.search(r"\bque\s+(?:el|la|los|las)\s+(.+?)\s+sea\w*\b", t)
        if not m:
            return (factor, "__ultimo__")   # "la mitad" a secas: el ultimo que añadio

        nombre = self._RE_COLETILLA.sub("", m.group(1)).strip()
        nombre = re.sub(r"\s+(?:de\s+)?(?:la\s+|el\s+)?comida.*$", "", nombre).strip()
        return (factor, nombre or "__ultimo__")

    async def aplicar_multiplicador(self, factor: float, food: str) -> dict:
        key = self.current_meal_key()
        alimentos = self.state["comidas_completadas"].get(key, {}).get("alimentos", [])
        if not alimentos:
            return {"ok": False, "vacio": True}
        idx = (len(alimentos) - 1) if food == "__ultimo__" else self._match_meal_food_index(food, strict=False)
        if idx < 0 or idx >= len(alimentos):
            return {"ok": False, "nombre": food}
        item = alimentos[idx]
        alimento = item.get("alimento") or {}
        es_ud = bool(alimento.get("unidades"))
        racion = float(alimento.get("racion") or 100) or 100.0
        new_g = float(item.get("cantidad_g") or 0) * factor
        cur = (new_g / racion) if es_ud else new_g
        return await self.set_food_quantity(item.get("nombre"), cantidad=cur, unidad=("ud" if es_ud else "g"))

    def _intento_ajuste_ultimo(self, text: str):
        """Ajuste referido al ÚLTIMO alimento sin nombrarlo: 'ponlo en 2', 'que sean 150 g',
        'añade 20 g más'. Devuelve (cantidad, unidad|None, incrementar) o None."""
        t = self._norm_text(text or "")
        # "ponme otro" / "otro" / "uno más": +1 unidad del último alimento (sin nombrarlo).
        # Se excluye "otro X" (con alimento nombrado): eso lo maneja el incremento normal.
        if (re.fullmatch(r"(?:y\s+)?(?:otro|otra|uno mas|una mas)", t)
                or re.search(r"\b(?:ponme|pon|dame|echa\w*|agrega\w*|anade\w*|suma\w*|mete\w*)\s+"
                             r"(?:otro|otra|uno mas|una mas)\b", t)) \
                and not re.search(r"\b(?:otro|otra)\s+[a-z]{3,}", t):
            return (1.0, "ud", True)
        mi = re.search(r"\b(?:anade\w*|suma\w*|agrega\w*|echa\w*)\s+(\d+(?:[.,]\d+)?)\s*(?:g|gr|gramos?)\b.*\bmas\b", t)
        if mi:
            return (float(mi.group(1).replace(",", ".")), "g", True)
        m2 = re.search(r"\b(?:ponlo|ponla|ponlos|ponlas|dejalo|dejala|dejalos|dejalas)\s+"
                       r"(?:en|a)\s+(\d+(?:[.,]\d+)?)\s*(g|gr|gramos?|ud|unidades?)?\b", t)
        m3 = m2 or re.search(r"\bque\s+sea[n]?\s+(?:de\s+)?(\d+(?:[.,]\d+)?)\s*(g|gr|gramos?|ud|unidades?)?\b", t)
        if m3:
            u = m3.group(2)
            uni = "g" if (u and u.startswith("g")) else ("ud" if u else None)
            return (float(m3.group(1).replace(",", ".")), uni, False)
        return None

    def _intento_mixto(self, text: str):
        """'agrega un huevo y quita uno' (mismo alimento) -> (nombre, neto) o None."""
        t = self._norm_text(text or "")
        ma = re.search(r"\b(?:agrega\w*|anade\w*|ponme|pon|suma\w*|echa\w*|mete\w*)\s+"
                       r"(un|una|uno|dos|tres|\d+)\s+(?:el\s+|la\s+|los\s+|las\s+)?([a-z]{3,})", t)
        md = re.search(r"\b(?:quita\w*|kita\w*|qita\w*|saca\w*)\s+(un|una|uno|dos|tres|\d+)?\s*(?:el\s+|la\s+|los\s+|las\s+)?([a-z]{3,})?", t)
        if not (ma and md):
            return None
        # Solo si el 'quita' se refiere al MISMO alimento. Si NO nombra alimento (p.ej.
        # "quita uno", donde 'uno' es el conteo), es el mismo -> neto. Si nombra OTRO
        # alimento distinto ("... y quita el arroz"), no es un neto: que lo haga el flujo normal.
        food = ma.group(2)
        dec_food = (md.group(2) or "").strip()
        if dec_food and dec_food not in ("uno", "una", "otro", "otra") \
                and food not in dec_food and dec_food not in food:
            return None
        nadd = self._a_num(ma.group(1)) or 1
        ndec = self._a_num(md.group(1)) if md.group(1) else 1
        return (food, nadd - ndec)

    def _es_incremento(self, text: str) -> bool:
        """¿El usuario quiere SUMAR a lo que ya hay (incremento) en vez de FIJAR el total?
        Marca aditiva ('agrega/añade/suma/otro/más/un/una') SALVO que haya marca de fijar
        total ('a N', 'en N', 'deja/baja/sube/cambia/solo'). Ej.: 'pon un huevo' -> suma;
        'deja los huevos en 2' / 'pon el arroz a 80' / '2 huevos' -> fija el total."""
        t = self._norm_text(text or "")
        if self._RE_SET_TOTAL.search(t):
            return False
        return bool(self._RE_INCREMENTO.search(t))

    _NUM_PALABRAS = {"un": 1, "una": 1, "uno": 1, "otro": 1, "otra": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5}

    def _num_pedido(self, text: str):
        """Número de unidades pedido en el texto ('dos claras' -> 2, 'un huevo más' -> 1), o None."""
        t = self._norm_text(text or "")
        m = re.search(r"\b(\d+)\b", t)
        if m:
            return float(m.group(1))
        return next((v for w, v in self._NUM_PALABRAS.items() if re.search(rf"\b{w}\b", t)), None)

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
        added, not_found, avisos = [], [], []

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
        # Cómo se llamaría cada cosa en la tabla, según el router ("tostadas" -> "pan
        # tostado"). Se lleva aparte porque el nombre que dijo el usuario no se toca.
        interpretacion = {it["nombre"]: it.get("busqueda") for it in real_items if it.get("busqueda")}

        # ── 0) Desambiguación: términos GENÉRICOS (p.ej. "lomo", "pavo") que en la base
        #     corresponden a alimentos muy distintos NO se adivinan; se ofrecen OPCIONES
        #     igual que el buscador de la calculadora. Aplica también con cantidad
        #     explícita ("150g de pavo": opciones a esa cantidad), SALVO que el alimento
        #     ya esté en la comida (entonces es una actualización y no se pregunta). ──
        choices = []
        restante_amb = self.get_remaining_macros()
        auto_clear = []
        for nombre in auto_names:
            opciones = await self._opciones_ambiguas(nombre, restante_amb)
            if opciones:
                choices.append({"termino": nombre, "opciones": opciones})
            else:
                auto_clear.append(nombre)
        auto_names = auto_clear

        explicit_clear = []
        for it in explicit:
            if self._match_meal_food_index(it["nombre"]) >= 0:
                explicit_clear.append(it)  # ya está en la comida: actualizar, no preguntar
                continue
            opciones = await self._opciones_ambiguas(
                it["nombre"], restante_amb, cantidad=it["cantidad"], unidad=it.get("unidad"))
            if opciones:
                choices.append({"termino": it["nombre"], "opciones": opciones})
            else:
                explicit_clear.append(it)
        explicit = explicit_clear

        # ── 1) Cantidades explícitas: una a una, manual (sin tope, se respeta lo pedido) ──
        for it in explicit:
            # Barbaridades: se PREGUNTA antes de meterlas. Antes entraban con un aviso de
            # pasada y el día se quedaba con 480 g de grasa arrastrando el descuadre a
            # todas las comidas siguientes. Si lo confirma, entra tal cual.
            desmedido = await self._es_desmedido(it)
            if desmedido and not self._confirmado(it):
                self.state["pendiente_confirmar"] = it
                return {"action": "confirmar",
                        "message": (f"{desmedido['texto']} ¿Seguro que quieres tanto? "
                                    f"Dime \"sí\" y lo pongo, o dime otra cantidad."),
                        "day_overview": self.get_day_overview()}
            res = await self.set_food_quantity(it["nombre"], cantidad=it["cantidad"],
                                               unidad=it.get("unidad"), incrementar=it.get("sumar", False))
            if res.get("ok"):
                added.append({"nombre": res["nombre"], "cantidad_display": res["cantidad_display"],
                              "macros": res["macros"]})
                if res.get("parcial"):
                    avisos.append(f"No tengo \"{res['parcial']}\" tal cual; he usado {res['nombre']}.")
                if res.get("corregido_a"):
                    avisos.append(f"Te he entendido \"{res['corregido_a']}\" donde ponía \"{it['nombre']}\".")
                choca = self._choca_con_restriccion(await self._alimento_de(res.get("nombre", "")))
                if choca:
                    avisos.append(f"Ojo: me dijiste que sin {choca}, y {res['nombre'].strip()} "
                                  f"lo es. Te lo pongo porque me lo pides; dime \"quitalo\" si no.")
                matiz = self._matiz_no_pedido(it["nombre"], res.get("nombre", ""))
                if matiz:
                    avisos.append(f"No tengo \"{it['nombre']}\" a secas: te he puesto "
                                  f"{res['nombre'].strip()}.")
                maxr = res.get("max_razonable") or 0
                if maxr and res.get("cantidad_g", 0) > 3 * maxr:
                    avisos.append(
                        f"Ojo: {res['cantidad_display']} de {res['nombre']} es una cantidad enorme "
                        f"(lo habitual es no pasar de {int(maxr)} g). Lo dejo porque lo has pedido tú."
                    )
            elif res.get("excesivo"):
                not_found.append({"buscado": it["nombre"],
                                  "razon": "Esa cantidad no es realista (más de 5 kg). Dime una cantidad normal y lo añado."})
            elif res.get("sugerencia"):
                not_found.append({"buscado": it["nombre"], "razon": "No lo tengo en la base de datos",
                                  "sugerencia": f"Lo más parecido que tengo es \"{res['sugerencia'].strip()}\". Escríbelo si lo quieres."})
            else:
                not_found.append({"buscado": it["nombre"], "razon": self._NO_LO_TENGO})

        # ── 2) Sin cantidad: resolver nombres primero; los matches PARCIALES no se añaden
        #     en silencio (se sugiere el parecido y el usuario decide). ──
        nombres_ok = []
        for nombre_pedido in auto_names:
            m = await self.buscar_con_interpretacion(
                nombre_pedido, interpretacion.get(nombre_pedido), limit=1)
            if not m:
                not_found.append({"buscado": nombre_pedido, "razon": self._NO_LO_TENGO})
            elif m[0].get("_match_parcial"):
                not_found.append({"buscado": nombre_pedido, "razon": "No lo tengo en la base de datos",
                                  "sugerencia": f"Lo más parecido que tengo es \"{(m[0].get('nombre') or '').strip()}\". Escríbelo si lo quieres."})
            elif m[0].get("_interpretado"):
                # Se ha entendido lo que quería, pero en la tabla se llama de otra forma.
                # Se añade con su nombre real y se le dice, para que no parezca un cambiazo.
                nombres_ok.append(m[0].get("nombre"))
                avisos.append(f"\"{nombre_pedido}\" lo tengo como \"{(m[0].get('nombre') or '').strip()}\".")
            elif m[0].get("_corregido_a"):
                # Errata de tecleo corregida por parecido: se dice, porque cambiar en
                # silencio lo que alguien escribe es la forma más rápida de perder su
                # confianza en lo que ve en pantalla.
                nombres_ok.append(m[0].get("nombre"))
                avisos.append(f"Te he entendido \"{m[0]['_corregido_a']}\" donde ponía \"{nombre_pedido}\".")
            elif self._matiz_no_pedido(nombre_pedido, m[0].get("nombre", "")):
                # El catálogo solo lo tiene con un matiz (0%, sin azúcar, desnatada):
                # se pone, pero se dice, que no es lo mismo comerse una cosa que otra.
                nombres_ok.append(m[0].get("nombre"))
                avisos.append(f"No tengo \"{nombre_pedido}\" a secas: te he puesto "
                              f"{(m[0].get('nombre') or '').strip()}.")
            else:
                choca = self._choca_con_restriccion(m[0])
                if choca:
                    avisos.append(f"Ojo: me dijiste que sin {choca}, y "
                                  f"{(m[0].get('nombre') or '').strip()} lo es. Te lo pongo porque "
                                  f"me lo pides; dime \"quitalo\" si no.")
                nombres_ok.append(nombre_pedido)

        if len(nombres_ok) == 1:
            restante = self.get_remaining_macros()
            matches = await self.search_foods(nombres_ok[0], limit=1)
            alimento = matches[0]
            sized = self._size_food(alimento, restante)
            if not sized:
                not_found.append({"buscado": nombres_ok[0], "encontrado": alimento.get("nombre"),
                                  "razon": self._razon_no_cabe(alimento, restante)})
            else:
                cantidad_g, macros = sized
                display = self._append_food(key, alimento, cantidad_g, macros)
                added.append({"nombre": (alimento.get("nombre") or "").strip(),
                              "cantidad_display": display, "macros": macros})
                # Si topamos en la cantidad razonable y aun así no se cubre lo pedido, explicarlo
                # (antes: tope silencioso de 300g de merluza con 20g de proteína sin cubrir).
                if cantidad_g >= self._max_auto_g(alimento) - 1:
                    rest_despues = self.get_remaining_macros()
                    faltan = [f"{rest_despues[k]} g de " + {"P": "proteína", "H": "hidratos", "G": "grasa"}[k]
                              for k in ("P", "H", "G") if rest_despues.get(k, 0) > 4 and macros.get(k, 0) > 0]
                    if faltan:
                        avisos.append(
                            f"Te he puesto el tope razonable de {alimento.get('nombre').strip()} "
                            f"({display}); aún quedan {' y '.join(faltan)}. Añade otro alimento o pídeme sugerencias."
                        )
        elif len(nombres_ok) >= 2:
            from meal_builder import build_meal
            restante = self.get_remaining_macros()
            # forzar=True: el chat es el modo manual, lo que pide el usuario entra aunque
            # la comida se pase de macros (el resumen ya avisa de lo que sobra).
            result = await build_meal(self.db, nombres_ok, restante, self.search_foods,
                                      forzar=True)
            not_found.extend(result.get("foods_not_found", []))
            for f in result["foods_added"]:
                cantidad_g = f.get("cantidad", f.get("cantidad_g", 0))
                matches = await self.search_foods(f["nombre"], limit=1)
                alimento = matches[0] if matches else {"nombre": f["nombre"], "racion": 100}
                macros = self._macros_at(alimento, cantidad_g) if matches else f.get("macros", {"P": 0, "H": 0, "G": 0})
                display = self._append_food(key, alimento, cantidad_g, macros)
                added.append({"nombre": (f["nombre"] or "").strip(), "cantidad_display": display, "macros": macros})

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

        # Preparaciones con aceite ("huevo frito"): el catálogo cuenta el alimento
        # BASE (no existe "huevo frito") y el cambio de nombre despistaba. Avisar
        # y recordar que el aceite se apunta aparte. No toca el matching.
        _FRITURA = ("frito", "frita", "fritos", "fritas", "rebozado", "rebozada",
                    "rebozados", "rebozadas", "empanado", "empanada", "empanados", "empanadas")
        pidio_frito = any(
            any(w in self._norm_text(it.get("nombre", "")).split() for w in _FRITURA)
            for it in items
        )
        if pidio_frito and any(
            not any(w in self._norm_text(a.get("nombre", "")) for w in _FRITURA)
            for a in added
        ):
            avisos.append(
                "Apunto el alimento en su versión base (el catálogo no distingue la preparación). "
                "Si lo haces frito o rebozado, cuenta el aceite aparte: dime, por ejemplo, \"aceite de oliva 5 g\"."
            )

        resp = self._meal_response(added, not_found, choices)
        msgs = list(avisos)
        if choices:
            flat = [op for c in choices for op in (c.get("opciones") or [])]
            self.state["last_options"] = flat
            # De qué iba la lista, para poder darle MÁS de lo mismo si pide otras.
            self.state["last_termino"] = choices[-1]["termino"]
            self.state["termino_vistos"] = [op.get("alimento_id") for op in flat]
            terms = ", ".join(f'"{c["termino"]}"' for c in choices)
            msgs.append(f"Tengo varios tipos de {terms}. Dime cuál quieres (p.ej. \"el 1\"):\n"
                        f"{self._format_options_lines(flat)}")
        if msgs:
            resp["message"] = "\n".join(msgs)
        return resp

    # Categorías que NUNCA deben resolver una petición genérica de macro
    # ("algo de proteína" no puede acabar en salsa de soja, refrescos, dulces
    # o fast food, aunque técnicamente aporten ese macro).
    CATS_NO_PLATO = ("16", "18", "19", "35", "36", "38", "39", "43", "44",
                     "45", "46", "47", "48", "49")

    async def _pick_food_for_macro(self, macro: str):
        """Elige un alimento real de un macro genérico ('una grasa', 'algo de proteína') que
        quepa en lo que falta de la comida, respetando lo evitado. Entre lo que más aporta
        de ese macro, prefiere el que lo hace con MENOS gramos (comida de verdad, no medio
        litro de batido comercial). Devuelve (alimento, cantidad_g, macros) o None."""
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
        # En peri el filtro de tipo de comida ya define qué es legítimo (Aquarius en
        # el intra lo es); ahí solo vetamos salsas. En comidas de plato, veto completo.
        veto = ("16",) if es_peri else self.CATS_NO_PLATO
        pool = [a for a in pool
                if not cat_hit(a.get("categorias"), veto)
                and not any(kw in (a.get("nombre", "") or "").lower() for kw in avoid_keywords)
                and not (avoid_prefixes and cat_hit(a.get("categorias"), avoid_prefixes))]

        candidatos = []
        for a in pool:
            sized = self._size_food(a, restante)
            if not sized:
                continue
            cantidad_g, macros = sized
            if macros.get(macro, 0) <= 0:
                continue
            candidatos.append((macros[macro], cantidad_g, a, macros))
        if not candidatos:
            return None
        # Mejor aporte primero; a igual aporte (±2g), el que necesita menos gramos.
        mejor_aporte = max(c[0] for c in candidatos)
        finalistas = [c for c in candidatos if c[0] >= mejor_aporte - 2]
        finalistas.sort(key=lambda c: c[1])
        _, cantidad_g, a, macros = finalistas[0]
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
        # Guardar el estado actual: si el reparto recalculado sale PEOR que lo que ya
        # tiene el usuario (pasaba con ajustes manuales finos), se restaura y se dice.
        import copy as _copy
        snapshot = _copy.deepcopy(comida)
        desvio_antes = sum(abs(target[k] - comida.get("macros", {}).get(k, 0)) for k in ("P", "H", "G"))
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

        macros_desp = self.state["comidas_completadas"][key].get("macros", {})
        desvio_despues = sum(abs(target[k] - macros_desp.get(k, 0)) for k in ("P", "H", "G"))
        if desvio_despues > desvio_antes + 0.5:
            # El reparto automático empeora lo que había: restaurar y ser honesto.
            self.state["comidas_completadas"][key] = snapshot
            resp = self._meal_response([], [])
            resp["message"] = ("Tus cantidades actuales ya están más cerca del objetivo que "
                               "cualquier reparto que consigo con estos mismos alimentos, así que "
                               "lo dejo como está. Para acercarte más, añade o cambia algún alimento.")
            return resp

        resp = self._meal_response(added, not_found)
        rest = self.get_remaining_macros()
        nombres_m = {"P": "proteína", "H": "hidratos", "G": "grasa"}
        faltan = [f"{rest[k]} g de {nombres_m[k]}" for k in ("P", "H", "G") if rest.get(k, 0) > 4]
        if faltan:
            resp["message"] = (f"He recalculado las cantidades, pero con estos alimentos siguen "
                               f"faltando {' y '.join(faltan)}. Añade algo más o pídeme sugerencias.")
        else:
            resp["message"] = "He recalculado las cantidades y la comida queda cuadrada."
        return resp

    async def add_food_by_id(self, alimento_id, cantidad_g: float = None) -> dict:
        """Añade un alimento concreto por id (cuando el usuario elige una opción).

        `cantidad_g`: si viene (opción de desambiguación con cantidad fijada por el
        usuario, p.ej. "150g de pavo"), se respeta tal cual, sin autodimensionar."""
        self.state["last_options"] = []  # elegir resuelve cualquier lista pendiente
        key = self.current_meal_key()
        alimento = await self.db.foods.find_one({"id": alimento_id}, {"_id": 0})
        if not alimento:
            return self._meal_response([], [{"buscado": str(alimento_id), "razon": "No encontrado"}])
        if cantidad_g and cantidad_g > 0:
            macros = self._macros_at(alimento, cantidad_g)
        else:
            sized = self._size_food(alimento, self.get_remaining_macros())
            if not sized:
                return self._meal_response([], [{"buscado": alimento.get("nombre"),
                                                 "razon": self._razon_no_cabe(alimento, self.get_remaining_macros())}])
            cantidad_g, macros = sized
        display = self._append_food(key, alimento, cantidad_g, macros)
        return self._meal_response([{"nombre": alimento.get("nombre"), "cantidad_display": display, "macros": macros}], [])

    async def suggest_foods_for_current_meal(self, limit: int = 6, macro: str = None,
                                             marca: str = None) -> dict:
        """Sugiere alimentos sueltos POR FASES, igual que la calculadora:
        primero PROTEÍNA (pollo, carnes, huevos, pescados…), luego HIDRATOS (arroz,
        pasta, cereales…), luego GRASA (aceites, frutos secos…). Si `macro` viene
        ("sugiéreme grasas" -> "G"), se respeta ESE macro en vez de la fase automática.
        En las comidas peri (Intra/Post) usa solo las categorías permitidas de peri.
        Respeta preferencias y alimentos evitados, no repite lo ya ofrecido en esta
        comida y añade variedad para que no salga siempre lo mismo."""
        import random
        from routes.calculator import AVOIDABLE_PREFIXES
        from calculator import (
            CATS_PROTEINA_PURAS, CATS_HIDRATOS, CATS_GRASAS, CATS_CUADRAR_GRASAS,
            filtrar_por_tipo_comida, cat_in_list, get_categoria_principal,
        )

        MACRO_LBL = {"P": "proteína", "H": "hidratos", "G": "grasa"}
        restante = self.get_remaining_macros()
        if all(abs(restante[m]) <= 4 for m in ("P", "H", "G")):
            return {"action": "suggestions", "suggestions": [],
                    "message": "Esta comida ya está cuadrada. Pulsa \"Guardar y siguiente\".",
                    "day_overview": self.get_day_overview()}

        if macro in ("P", "H", "G") and not marca:
            # El usuario pidió un macro concreto: respetarlo, y si ya va servido, decirlo.
            # Con una marca de por medio no se corta: ha pedido ver productos de esa marca.
            if restante[macro] <= 0:
                exceso = abs(restante[macro])
                detalle = f" (te pasas {exceso} g)" if exceso > 0.5 else ""
                return {"action": "suggestions", "suggestions": [],
                        "message": (f"De {MACRO_LBL[macro]} ya vas servido en esta comida{detalle}. "
                                    "¿Quieres sugerencias de lo que sí falta?"),
                        "day_overview": self.get_day_overview()}
            fase = {"P": "proteina", "H": "hidratos", "G": "grasa"}[macro]
            driver = macro
        # Fase según el macro que más falta (orden CALMA: proteína → hidratos → grasa)
        elif restante["P"] > 4:
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

        # Marca pedida ("algo de FullGas"): se busca en TODO el catálogo, no solo en las
        # categorías de la fase, porque una marca vende de todo y lo que el usuario quiere
        # es ver SUS productos. Si no queda ninguno se avisa en vez de colar otra cosa.
        if marca:
            marca_norm = self._norm_text(marca)
            de_la_marca = [a for a in all_foods
                           if marca_norm in self._norm_text(a.get("nombre", ""))]
            if not de_la_marca:
                return {"action": "suggestions", "suggestions": [],
                        "message": f"No tengo alimentos de \"{marca}\" en la base de datos.",
                        "day_overview": self.get_day_overview()}
            pool = [a for a in de_la_marca
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
            # Con una marca pedida vale cualquier producto suyo que quepa: se ordenan por
            # lo que aporten a lo que falta, pero no se descarta el que no aporte ese macro
            # (el usuario quiere ver los productos de esa marca, no cuadrar a toda costa).
            if macros[driver] <= 0 and not marca:
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
                "categorias": a.get("categorias"),  # para el emoji de la opcion en la app
            }))

        # Dentro de cada tipo: mejores primero, baraja los top para variedad, y pon al final
        # lo YA ofrecido antes en esta comida ("no me gusta ninguna, dame otras").
        seen = set(self.state.setdefault("seen_sugg", {}).get(key, []))
        for b in buckets:
            buckets[b].sort(key=lambda x: -x[0])
            head = buckets[b][:8]
            random.shuffle(head)
            buckets[b] = ([x for x in head if x[2]["alimento_id"] not in seen]
                          + [x for x in head if x[2]["alimento_id"] in seen])

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
        self.state["last_options"] = chosen
        self.state["seen_sugg"].setdefault(key, [])
        self.state["seen_sugg"][key].extend(
            s["alimento_id"] for s in chosen if s["alimento_id"] not in self.state["seen_sugg"][key])
        if chosen:
            # La lista de opciones la pinta la app con <ChatSuggestions> a partir de
            # `suggestions` (tarjetas que se pulsan). Aquí solo va la frase de contexto y,
            # si toca, el aviso de que ninguna cubre sola lo que falta: repetir las opciones
            # en el texto dejaba el mensaje duplicado.
            # El encabezado ("lo que más te falta es proteína" / "esto es lo que tengo de
            # FullGas") lo pone la tarjeta de opciones, que ya lleva ese contexto. Aquí el
            # texto se queda VACÍO para no decir lo mismo dos veces, una en la burbuja y
            # otra en la tarjeta; solo se rellena con el aviso de más abajo si hace falta.
            message = ""
            motivo = "marca" if marca else ("pedido" if macro else "falta")
            # Honestidad: si ninguna opción cubre por sí sola lo que falta, decirlo.
            mejor = max((s["macros"].get(driver, 0) for s in chosen), default=0)
            if mejor < restante[driver] - 4:
                message = (f"Ninguna cubre sola los {restante[driver]} g de {MACRO_LBL[driver]} "
                           "que faltan: combina un par, o añade otro alimento después.")
        else:
            motivo = "vacio"
            # Un "no encuentro nada" a secas deja al usuario parado sin saber qué hacer.
            # Se dice qué falta y se le pregunta, que es la forma de seguir avanzando.
            falta = [f"{restante[m]} g de {MACRO_LBL[m]}" for m in ("P", "H", "G") if restante[m] > 4]
            # Y si el motivo real es que ya se ha pasado de algo, se dice ESO: casi nunca
            # hay nada que cuadre cuando la comida arrastra 400 g de grasa de más, y
            # callarlo deja al cliente creyendo que el catálogo se ha quedado corto.
            pasados = [(m, abs(restante[m])) for m in ("P", "H", "G") if restante[m] < -4]
            if pasados:
                peor = max(pasados, key=lambda x: x[1])
                culpable = self._mayor_aporte_de(peor[0])
                message = (
                    f"Así no hay nada que cuadre: en esta comida te pasas {peor[1]} g de "
                    f"{MACRO_LBL[peor[0]]}"
                    + (f", casi todo de {culpable}" if culpable else "")
                    + ". Quita o baja eso y te busco con lo que quede"
                    + (f" (faltan {' y '.join(falta)})" if falta else "") + "."
                )
            else:
                message = (
                    f"No encuentro nada que cuadre con lo que falta"
                    + (f" ({' y '.join(falta)})" if falta else "")
                    + ". ¿Te digo alimentos aunque se pasen un poco, o prefieres decirme tú qué te apetece?"
                )
        return {
            "action": "suggestions",
            "fase": fase,
            "motivo": motivo,      # de qué va la lista: falta / pedido / marca
            "marca": marca,
            "message": message,
            "suggestions": chosen,
            "day_overview": self.get_day_overview(),
        }

    def _mayor_aporte_de(self, macro: str) -> Optional[str]:
        """Qué alimento de la comida actual aporta más de ese macro. Para poder señalar al
        culpable cuando la comida se ha pasado, en vez de dejarlo en un "algo sobra"."""
        alimentos = self.state["comidas_completadas"].get(self.current_meal_key(), {}).get("alimentos", [])
        if not alimentos:
            return None
        peor = max(alimentos, key=lambda a: float((a.get("macros") or {}).get(macro, 0) or 0))
        if float((peor.get("macros") or {}).get(macro, 0) or 0) <= 0:
            return None
        return (peor.get("nombre") or "").strip() or None

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

    def _falta_para_llm(self, rem: dict) -> str:
        """Lo que falta y lo que sobra, en palabras, para el contexto del modelo.

        Se le pasaba en crudo ("falta P=-12") y el modelo leía los negativos como una
        avería: llegó a contestarle al cliente "tienes un fallo raro en los macros
        (negativos), ¿confirmas esas cantidades?". No hay fallo: es que se ha pasado.
        """
        nombres = {"P": "proteína", "H": "hidratos", "G": "grasa"}
        falta = [f"{rem.get(m, 0)} g de {nombres[m]}" for m in ("P", "H", "G") if rem.get(m, 0) > 0.5]
        pasa = [f"{abs(rem.get(m, 0))} g de {nombres[m]}" for m in ("P", "H", "G") if rem.get(m, 0) < -0.5]
        partes = []
        if falta:
            partes.append("falta " + " y ".join(falta))
        if pasa:
            partes.append("SE HA PASADO de " + " y ".join(pasa) + " (no es un error, es exceso)")
        return "; ".join(partes) if partes else "cuadrado"

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
            kcal = lambda m: round(m.get("P", 0) * 4 + m.get("H", 0) * 4 + m.get("G", 0) * 9)
            lines.append(
                f"Día de {self.state.get('tipo_dia', '')}. "
                f"Objetivo total del día: P={obj.get('P', 0)}g H={obj.get('H', 0)}g G={obj.get('G', 0)}g (≈{kcal(obj)} kcal). "
                f"Consumido: P={con.get('P', 0)}g H={con.get('H', 0)}g G={con.get('G', 0)}g (≈{kcal(con)} kcal). "
                f"Falta en el día: {self._falta_para_llm(rem)}."
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
                    f"{self._falta_para_llm(r)}; {estado}. Contiene: {foods}."
                )
        ctx = "\n".join(lines)
        system = (
            "Eres el asistente del método 12en12 (CALMA) de nutrición. Respondes las dudas del "
            "cliente de forma breve y clara, en español de España con tuteo (prohibido el voseo tipo "
            "'armá'/'tenés', los regionalismos, y di siempre 'añadir', nunca 'agregar'), en 2-4 frases. "
            "NO tienes acceso a otros días ni historial: si mencionan 'ayer', 'lo de siempre' o días "
            "anteriores, di claramente que no guardas ese historial y pide que te digan los alimentos. "
            "Si preguntan por calorías, usa las kcal aproximadas que van en los DATOS. "
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
            "openai", os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
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
                    items.append({"nombre": nombre, "cantidad": None, "unidad": None, "sumar": False})
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
            # Cómo se llamaría en la tabla ("tostadas" -> "pan tostado"). Se guarda aparte:
            # el nombre que dijo el usuario NO se toca, porque es lo que se le enseña y lo
            # que se busca primero. Esto es una segunda vía, no un reemplazo.
            busq = (f.get("busqueda") or "").strip() if isinstance(f.get("busqueda"), str) else ""
            if busq.lower() == nombre.lower():
                busq = ""
            items.append({"nombre": nombre, "cantidad": cant, "unidad": unidad,
                          "sumar": bool(f.get("sumar")),
                          "busqueda": busq or None})
        return items

    async def understand(self, text: str) -> dict:
        """Router con LLM: clasifica la INTENCIÓN del mensaje y extrae lo necesario. El LLM solo
        interpreta el lenguaje; el código hace toda la matemática. Devuelve
        {intent, foods, remove, goto}."""
        prompt = (
            "Eres el router de un asistente de nutrición. El usuario está montando una comida. "
            "Clasifica su mensaje en UNA intención y extrae lo necesario. Devuelve SOLO JSON: "
            '{"intent": "add|suggest|complete|remove|clear|status|summary|rebalance|goto|list|question|none", '
            '"foods": [{"nombre": "...", "cantidad": <numero o null>, "unidad": "g"|"ud"|null, '
            '"busqueda": "<como se llamaria eso en una tabla de alimentos, o null>"}], '
            '"remove": "<alimento a quitar o null>", "goto": <numero de comida, "post", "intra", "ultima", "actual" o null>, '
            '"macro": "P"|"H"|"G"|null, "marca": "<marca pedida o null>", '
            '"termino": "<tipo de alimento del que pide MAS opciones, o null>"}. '
            # La gente no habla como está escrito el catálogo. Pide "tostadas" y en la tabla
            # pone "pan tostado"; pide "cereales" y pone "copos de maíz". Aquí se traduce.
            "CÓMO SE LLAMA EN LA TABLA ('busqueda'): la gente no pide la comida como está "
            "escrita en una tabla de alimentos. Por cada alimento, di también cómo se "
            "llamaría ahí. Ejemplos: 'tostadas' -> 'pan tostado'; 'cereales' -> 'copos de "
            "maíz'; 'fiambre' -> 'jamón de york'; 'pasta' -> 'macarrones'; 'refresco' -> "
            "'bebida de cola'; 'embutido' -> 'chorizo'. "
            "DOS REGLAS que no se saltan: "
            "(a) si lo que ha dicho YA es como se llamaría en la tabla ('pechuga de pollo', "
            "'arroz blanco', 'huevos'), 'busqueda' va a null: no hay nada que traducir. "
            "(b) NO concretes lo que es ambiguo a propósito. Si dice 'pavo', 'lomo', "
            "'filete', 'queso' o 'yogur', déjalo tal cual con 'busqueda' a null: son "
            "términos que el sistema pregunta al usuario, y concretarlos le quitaría la "
            "elección. Traduce solo cuando la palabra que ha usado NO aparecería en la tabla. "
            "Intenciones: "
            "'add' = dice qué alimentos quiere comer/añadir o CAMBIAR DE CANTIDAD "
            "(ej: 'quiero tortilla de claras y pan', 'pon 80 g de arroz', 'cambia el arroz a 100g'). "
            "MUY IMPORTANTE - cambios de cantidad son 'add' con la cantidad FINAL, NUNCA 'remove' ni 'clear': "
            "'baja las almendras a 26 g' -> add almendras 26 g; 'sube el pollo a 200' -> add pollo 200 g; "
            "'deja los huevos en 2' / 'quita un huevo, déjame solo 2' / 'quita 2 huevos y deja 2' -> add huevo 2 ud; "
            "'ponme más claras' -> add claras (cantidad null). "
            "También es 'add' cuando NOMBRA un alimento concreto aunque hable de cuadrar/cubrir macros: "
            "'ponme merluza para cubrir la proteína que falta' -> add merluza (cantidad null); "
            "'patata cocida para llegar a los hidratos' -> add patata cocida; "
            "'ponme unas nueces para la grasa' -> add nueces. "
            "'suggest' = pide que TÚ sugieras/recomiendes qué poner SIN nombrar ningún alimento concreto "
            "(ej: 'qué me sugieres', 'dame opciones', 'qué pongo', 'no sé qué añadir'). Si pide sugerencias "
            "de un macro concreto ('sugiéreme grasas', 'opciones de proteína'), pon ese macro en 'macro'. "
            "MARCAS: si pide algo de una MARCA ('recomiéndame algo de FullGas', 'algún alimento Hacendado', "
            "'un yogur de Mercadona'), es 'suggest' con la marca en 'marca' y 'macro' a null. Una marca NUNCA "
            "es un macro: 'fullgas' NO es grasa. Si no nombra ninguna marca, 'marca' va a null. "
            "MAS OPCIONES DE LO MISMO: si acabas de ofrecerle una lista de un tipo de alimento y pide "
            "otras ('hay otras opciones de tostadas?', 'dame mas tostadas', 'otras', 'alguna mas'), es "
            "'suggest' con ese tipo en 'termino' ('tostadas'). Si dice solo 'otras' sin decir de qué, "
            "'termino' va a null y el código ya sabe de qué hablaba. 'termino' NO es una marca ni un macro. "
            "OJO CON QUIÉN SUGIERE: 'suggest' es SOLO cuando pide que TÚ elijas. Si el que va a decir el "
            "alimento es ÉL ('quiero añadir un alimento', 'quiero sugerir un alimento', 'voy a poner algo', "
            "'quiero meter un alimento'), NO es 'suggest': es 'add' con 'foods' vacío, para preguntarle cuál. "
            "'complete' = quiere GUARDAR/cerrar esta comida y pasar a la siguiente "
            "(ej: 'siguiente', 'guardar y siguiente', 'ya está, la dejo así', 'pasa a la siguiente'). "
            "'remove' = quitar del todo UN alimento ya añadido, SIN cantidad final "
            "(ej: 'borra las aceitunas', 'quita el arroz de la comida 2'); pon el nombre en 'remove'. "
            "'clear' = vaciar TODA una comida (ej: 'vacía la comida 1', 'borra la comida 2', 'borra el post-entreno', "
            "'quita todo de esta comida', 'empieza de cero'). NUNCA uses 'clear' si el mensaje nombra un alimento. "
            "'status' = pide los NÚMEROS de cómo va (ej: 'qué me falta', 'cuántos macros quedan', 'cómo voy'). "
            "'summary' = resumen del día completo. "
            "'rebalance' = recalcular/cuadrar las cantidades de lo que YA hay (ej: 'cuadra las cantidades', 'reparte mejor'). "
            "'goto' = ir a una comida concreta para verla o editarla (ej: 'vamos a la comida 2', "
            "'edita la comida 3', 'abre el post-entreno', 'edita la última'). "
            "'list' = quiere VER/LISTAR el contenido de sus comidas o alimentos cargados "
            "(ej: 'qué comidas tengo', 'lístame la comida 1', 'qué llevo en la comida 2', 'qué llevo hasta ahora'). "
            "'question' = dudas de nutrición Y toda pregunta que espera una RESPUESTA en texto: "
            "'¿por qué el arroz cuenta como hidrato?', '¿por qué solo 300 g?', '¿cuántas calorías llevo?', "
            "'¿pasa algo si la guardo así?', '¿puedo cambiar el aceite por aguacate?', "
            "referencias a otros días ('lo mismo que ayer' -> no hay historial, es question), o algo fuera de tema. "
            "'none' = saludo o ininteligible. "
            "REFERENCIA DE COMIDA ('goto'): siempre que el mensaje nombre una comida concreta, rellena 'goto' "
            "con su número (de 'la comida 2' pon 2), \"post\" o \"intra\" para el peri-entreno, \"ultima\" para "
            "la última, \"actual\" para 'esta comida'; si no nombra ninguna, null. Aplica a goto/list/clear y "
            "también a add/remove cuando dicen DÓNDE ('añade pollo a la comida 3', 'quita el arroz de la comida 2'). "
            "IMPORTANTE: 'terminar/completar/ajustar la comida' cuando PIDEN ayuda o sugerencias es 'suggest', NO 'complete'. "
            "'complete' es solo cuando quieren guardar y avanzar. "
            "Listar o VER el contenido de las comidas es 'list', NO 'status' (status es SOLO cuánto falta). "
            "Interpreta números pegados o mal escritos. Rellena 'foods' SOLO si intent='add'. "
            "En 'foods' NUNCA incluyas alimentos negados o excluidos (\"sin pan\", \"no quiero pescado\"). "
            "Si el mensaje MEZCLA quitar y añadir (\"quítame el arroz y pon más pollo\"), usa intent='add', "
            "pon el alimento a quitar en 'remove' Y los alimentos a añadir en 'foods'. "
            "Si añade y quita el MISMO alimento en el mismo mensaje ('ponme un plátano... y quita el plátano'), "
            "interpreta la intención FINAL: no lo pongas en 'foods'. "
            "Si corrige un alimento equivocado ('te pedí un plátano GRANDE, no pequeño'), usa 'add' con el "
            "correcto en 'foods' Y el equivocado en 'remove'."
        )
        raw = {}
        last_err = None
        for _ in range(2):
            chat = LlmChat(api_key=self.api_key, system_message=prompt).with_model(
                "openai", os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
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
            # Fallo del LLM (transitorio): NO seguir como un "add" vacío, que
            # producía un "comida actualizada" sin alimentos y el chat quedaba
            # en blanco/confuso. Se devuelve un intent propio para avisar.
            return {"intent": "llm_fallo", "foods": [], "remove": None, "goto": None, "macro": None}

        intents = ("add", "suggest", "complete", "remove", "clear", "status",
                   "summary", "rebalance", "goto", "list", "question", "none")
        intent = raw.get("intent")
        if intent not in intents:
            intent = "add"
        remove = raw.get("remove")
        if not isinstance(remove, str) or not remove.strip():
            remove = None
        # goto puede ser un número ("comida 2" -> 2) o texto ("post", "intra");
        # resolve_meal_ref lo convierte después al índice real de meal_order.
        goto = raw.get("goto")
        if isinstance(goto, str):
            goto = goto.strip() or None
        elif goto is not None:
            try:
                goto = int(goto)
            except (TypeError, ValueError):
                goto = None
        macro = raw.get("macro")
        if macro not in ("P", "H", "G"):
            macro = None
        # Marca pedida ("algo de FullGas", "un yogur de Hacendado"). Se filtran las
        # sugerencias por ella. Antes no existía y el router colaba las marcas en `macro`:
        # "recomienda algún alimento fullgas" salía como sugerencias de GRASA.
        marca = raw.get("marca")
        if not isinstance(marca, str) or not marca.strip():
            marca = None
        else:
            marca = marca.strip()
        # Tipo de alimento del que pide más opciones ("otras tostadas").
        termino = raw.get("termino")
        if not isinstance(termino, str) or not termino.strip():
            termino = None
        else:
            termino = termino.strip()
        return {
            "intent": intent,
            "foods": self._normalize_food_items(raw.get("foods") or []),
            "remove": remove,
            "goto": goto,
            "macro": macro,
            "marca": marca,
            "termino": termino,
        }

    # "que sigue", "que comida toca ahora", "cual es la siguiente", "donde voy".
    _RE_DONDE_ESTOY = re.compile(
        r"^(?:(?:y|ahora|entonces|pues|bueno|vale)\s+){0,3}"
        r"(?:(?:que|cual|cuales|donde|en que)\b.*"
        r"\b(?:sigue|siguiente|toca|vamos|voy|queda|estamos|falta|resta)\b"
        r"|(?:que|cual)\s+comida\b|siguiente\s+comida\b)"
    )

    def _pregunta_donde_estoy(self, text: str) -> bool:
        """¿Está preguntando en qué comida va, en vez de mandando avanzar?"""
        t = self._norm_text(text or "").strip(" ¿?¡!.")
        if not t or len(t.split()) > 6:
            return False
        return bool(self._RE_DONDE_ESTOY.search(t))

    # "¿esto cuadra?", "¿está bien así?", "¿voy bien?", "¿ya está cuadrada?"
    _RE_CUADRA = re.compile(
        r"\b(cuadra|cuadrada|cuadrado|esta bien|va bien|voy bien|vale asi|asi esta bien|"
        r"lo tengo bien|es correcto|correcta)\b")

    # Matices que cambian lo que te vas a comer y que, si no los has pedido tú, hay que
    # decirlos: pides "cerveza" y te ponen la 0%, o "leche" y te ponen la desnatada.
    _MATICES = ("0% alcohol", "sin alcohol", "0%", "sin azucar", "sin azucares", "light",
                "desnatada", "desnatado", "semidesnatada", "integral", "sin lactosa",
                "descafeinado", "sin gluten", "sin sal", "bajo en grasa", "proteico")

    def _matiz_no_pedido(self, pedido: str, nombre_real: str) -> Optional[str]:
        """El matiz que trae el alimento del catálogo y que el usuario NO escribió."""
        p, n = self._norm_text(pedido or ""), self._norm_text(nombre_real or "")
        for matiz in self._MATICES:
            m = self._norm_text(matiz)
            if m in n and m not in p:
                return matiz
        return None

    # "lo mismo que en la comida 2", "repite la comida 1", "igual que el post"
    _RE_COPIAR = re.compile(
        r"\b(?:lo mismo|igual|lo mesmo|repite|repiteme|repetir|copia|copiame|clona)\b"
        r"[^0-9a-z]*(?:que\s+)?(?:en\s+|de\s+|la\s+|el\s+)*"
        r"(comida\s*[1-6]|c[1-6]\b|intra\w*|post\w*|peri\w*)")

    def _intento_copiar_comida(self, text: str) -> Optional[int]:
        """¿Pide repetir otra comida del MISMO día? Devuelve su índice.

        Lo contestaba el modelo con un "no guardo el historial ni los alimentos de comidas
        anteriores"... en la misma respuesta en la que describía lo que había en esa comida.
        Las tiene delante: copiarlas es cosa de dos líneas y Nutrición ya lo hace.
        """
        t = self._norm_text(text or "")
        m = self._RE_COPIAR.search(t)
        return self.resolve_meal_ref(m.group(1)) if m else None

    def copiar_comida(self, idx_origen: int) -> dict:
        """Vuelca los alimentos de otra comida en la actual (se suman a lo que haya)."""
        order = self.state.get("meal_order") or []
        if not (1 <= idx_origen <= len(order)):
            return {"ok": False}
        origen_key = order[idx_origen - 1]
        destino_key = self.current_meal_key()
        if origen_key == destino_key:
            return {"ok": False, "misma": True}
        alimentos = self.state["comidas_completadas"].get(origen_key, {}).get("alimentos", [])
        if not alimentos:
            return {"ok": False, "vacia": True, "origen": self.meal_label(origen_key)}
        copiados = []
        for a in alimentos:
            alimento = a.get("alimento")
            if not alimento:
                continue
            # Se recalculan los macros al volcarlos: el objetivo de la comida destino es
            # otro, pero las cantidades son las mismas (repetir es repetir).
            cantidad_g = float(a.get("cantidad_g") or 0)
            macros = self._macros_at(alimento, cantidad_g)
            self._ensure_meal(destino_key)
            display = self._append_food(destino_key, alimento, cantidad_g, macros)
            copiados.append({"nombre": alimento.get("nombre"), "cantidad_display": display,
                             "macros": macros})
        return {"ok": bool(copiados), "copiados": copiados,
                "origen": self.meal_label(origen_key), "destino": self.meal_label(destino_key)}

    # Las maneras reales de decir "esto no me lo puedo comer".
    _RE_RESTRICCION = re.compile(
        r"\b(?:sin|no quiero|nada de|no puedo (?:comer|tomar)|no tomo|no como|"
        r"no tolero|soy alergic[oa] al?|soy intolerante a la?|me sienta mal el?a?|"
        r"tengo alergia al?)\s+(?:el\s|la\s|los\s|las\s)?(\w{3,})")
    _NO_SON_RESTRICCION = {"nada", "mas", "menos", "duda", "cantidad", "problema", "peri",
                           "azucar", "embargo", "momento", "eso", "esto", "gracias"}
    # Palabras que no son un alimento sino una FAMILIA entera: por nombre no filtran nada
    # ("lacteos" no aparece en "Yogur griego"), así que se traducen a categorías CALMA.
    _FAMILIAS = {
        "lacteo": ["5"], "lacteos": ["5"], "lactosa": ["5"], "leche": ["5"],
        "gluten": ["7", "8"], "trigo": ["7", "8"], "cereal": ["7"], "cereales": ["7"],
        "marisco": ["3"], "mariscos": ["3"], "pescado": ["3"], "pescados": ["3"],
        "carne": ["2"], "carnes": ["2"], "cerdo": ["2"], "huevo": ["1"], "huevos": ["1"],
        "legumbre": ["10"], "legumbres": ["10"], "fruto": ["17.2"], "frutos": ["17.2"],
        "frutos secos": ["17.2"], "soja": ["6"], "alcohol": ["19"],
    }

    def _registrar_restricciones(self, text: str) -> list:
        """Apunta lo que el cliente ha dicho que no come. Devuelve lo nuevo apuntado."""
        nuevas = []
        t = self._norm_text(text or "")
        for m in self._RE_RESTRICCION.finditer(t):
            kw = m.group(1)
            if kw in self._NO_SON_RESTRICCION:
                continue
            cats = self._FAMILIAS.get(kw)
            if cats:
                actuales = self.state.setdefault("avoided_categories", [])
                for c in cats:
                    if c not in actuales:
                        actuales.append(c)
                        nuevas.append(kw)
            if kw not in self.state.setdefault("avoided_keywords", []):
                self.state["avoided_keywords"].append(kw)
                if not cats:
                    nuevas.append(kw)
        return nuevas

    def _choca_con_restriccion(self, alimento: dict) -> Optional[str]:
        """¿Este alimento es justo lo que dijo que no podía comer? Devuelve la palabra."""
        if not alimento:
            return None
        nombre = self._norm_text(alimento.get("nombre", ""))
        for kw in self.state.get("avoided_keywords", []):
            if kw in nombre:
                return kw
        cats_evitadas = [str(c) for c in self.state.get("avoided_categories", [])]
        if cats_evitadas:
            from calculator import cat_in_list, get_categoria_principal
            if cat_in_list(get_categoria_principal(alimento), cats_evitadas):
                # Se devuelve la palabra que lo provocó, no el número de categoría.
                for kw, cats in self._FAMILIAS.items():
                    if any(c in cats_evitadas for c in cats) and kw in self.state.get("avoided_keywords", []):
                        return kw
                return "eso"
        return None

    async def _alimento_de(self, nombre: str) -> Optional[dict]:
        """El documento del alimento a partir de su nombre ya resuelto (para mirarle la
        categoría sin volver a interpretar lo que dijo el usuario)."""
        if not nombre:
            return None
        r = await self.search_foods(nombre, limit=1)
        return r[0] if r else None

    def _sin_contenido(self, text: str) -> Optional[str]:
        """Mensajes que no dicen nada: vacío, solo emojis o signos, o teclado aporreado.

        Devuelve la respuesta corta que toca, o None si el mensaje sí tiene contenido.
        Antes los tres caían en el texto largo de "no reconocí ningún alimento…" con las
        cinco líneas de ayuda, que para un 😀 es desproporcionado.
        """
        bruto = (text or "").strip()
        if not bruto:
            return "No me ha llegado nada. Escribe qué quieres comer y lo montamos."
        t = self._norm_text(bruto)
        if re.fullmatch(r"[\d.,]+", t):
            return None   # un número suelto es una elección o una cantidad, no un ruido
        letras = re.sub(r"[^a-z]", "", t)
        if not letras:
            return "😊 Dime qué te apetece comer, o pregúntame qué te falta."
        # Una sola "palabra" larga, sin vocales o con secuencias imposibles en español:
        # gente que apoya la mano en el teclado, no gente pidiendo comida.
        if " " not in t.strip() and len(letras) >= 5:
            vocales = sum(1 for c in letras if c in "aeiou")
            if vocales == 0 or re.search(r"[bcdfghjklmnpqrstvwxyz]{5,}", letras):
                return ("No he entendido eso. Dime un alimento (\"pollo\", \"arroz\") "
                        "o pregúntame \"¿qué me falta?\".")
        return None

    def _texto_falta_sobra(self, rem: dict) -> str:
        """"faltan 20 g de proteína y te pasas de 30 g de grasa". Un solo sitio para
        decirlo: un "-488 de grasa" en mitad de una frase no lo entiende nadie."""
        nombres = {"P": "proteína", "H": "hidratos", "G": "grasa"}
        faltan = [f"{rem[m]} g de {nombres[m]}" for m in ("P", "H", "G") if rem.get(m, 0) > 4]
        sobran = [f"{abs(rem[m])} g de {nombres[m]}" for m in ("P", "H", "G") if rem.get(m, 0) < -4]
        partes = []
        if faltan:
            partes.append("faltan " + " y ".join(faltan))
        if sobran:
            partes.append("te pasas de " + " y ".join(sobran))
        return " y ".join(partes) if partes else "todo cuadra"

    def _pregunta_si_cuadra(self, text: str) -> bool:
        """¿Pregunta si la comida está cuadrada? Se contesta con el dato, no con el LLM."""
        t = self._norm_text(text or "").strip(" ¿?¡!.")
        if not t or len(t.split()) > 7:
            return False
        if re.search(r"\b(cuadrame|cuadramelo|cuadra la|cuadra esto|cuadralo)\b", t):
            return False   # eso es una ORDEN de cuadrar, no una pregunta
        return bool(self._RE_CUADRA.search(t))

    def _respuesta_si_cuadra(self) -> dict:
        """Sí o no, con los gramos exactos.

        Lo contestaba el modelo por su cuenta y llegó a decir "sí, cuadra bien" con 33 g de
        hidratos sin cubrir. Es la peor respuesta posible: da por bueno un día que no lo
        está. El dato ya lo tiene el sistema, así que aquí no opina nadie.
        """
        key = self.current_meal_key()
        rem = self.get_remaining_macros()
        alimentos = self.state["comidas_completadas"].get(key, {}).get("alimentos", [])
        nombres = {"P": "proteína", "H": "hidratos", "G": "grasa"}
        if not alimentos:
            return {"action": "status", "message": f"{self.meal_label(key)} está vacía todavía.",
                    "meals_status": self.get_meals_status(), "day_overview": self.get_day_overview()}
        texto = self._texto_falta_sobra(rem)
        if texto == "todo cuadra":
            msg = f"Sí, {self.meal_label(key)} cuadra (todo dentro de ±4 g). Puedes guardarla."
        else:
            msg = f"Todavía no: en {self.meal_label(key)} {texto}."
        return {"action": "status", "message": msg,
                "meals_status": self.get_meals_status(), "day_overview": self.get_day_overview()}

    # Saludar o dar las gracias no es pedir comida: contestaba con el muro de instrucciones,
    # que empieza por "No reconocí ningún alimento ahí" y suena a error por ser educado.
    _RE_CORTESIA = re.compile(
        r"^(hola|buenas|buenos dias|buenas tardes|buenas noches|hey|ey|que tal|"
        r"gracias|muchas gracias|mil gracias|grasias|ok|oka|okey|vale|genial|perfecto|"
        r"guay|estupendo|de acuerdo|entendido|adios|hasta luego|chao|nos vemos)\b")

    # Lo que puede acompañar a un saludo sin dejar de ser solo un saludo.
    _RELLENO_CORTESIA = {"tio", "tia", "amigo", "bro", "crack", "maquina", "campeon",
                         "gracias", "muchas", "mil", "por", "todo", "ya", "pues", "muy",
                         "bien", "de", "nada", "hombre", "chaval", "compi"}

    def _es_cortesia(self, text: str) -> bool:
        """Solo si el mensaje es SOLO cortesía: "ok ponme pollo" es una orden con un ok
        delante, y tratarlo como saludo se comería la comida que está pidiendo."""
        t = self._norm_text(text or "").strip(" ¿?¡!.,")
        m = self._RE_CORTESIA.match(t) if t else None
        if not m:
            return False
        resto = t[m.end():].replace(",", " ").split()
        return all(w in self._RELLENO_CORTESIA for w in resto)

    def _respuesta_cortesia(self, text: str) -> dict:
        t = self._norm_text(text)
        key = self.current_meal_key()
        rem = self.get_remaining_macros()
        if re.match(r"^(gracias|muchas gracias|mil gracias|grasias)", t):
            msg = "A ti. "
        elif re.match(r"^(adios|hasta luego|chao|nos vemos)", t):
            return {"action": "status", "message": "¡Hasta luego! Lo que lleves montado se queda guardado.",
                    "meals_status": self.get_meals_status(), "day_overview": self.get_day_overview()}
        elif re.match(r"^(ok|oka|okey|vale|genial|perfecto|guay|estupendo|de acuerdo|entendido)", t):
            msg = "Bien. "
        else:
            msg = "¡Hola! "
        msg += f"Vamos con {self.meal_label(key)}: {self._texto_falta_sobra(rem)}. ¿Qué te apetece?"
        # Con meals_status: sin él, la pantalla pinta debajo "Aún no has configurado el día".
        return {"action": "status", "message": msg,
                "meals_status": self.get_meals_status(), "day_overview": self.get_day_overview()}

    # Cuántas veces el tope razonable hay que pedir para que la app pregunte en vez de
    # obedecer. Tres veces es "mucho" (avisa y lo pone); cinco es "esto no puede ser".
    _VECES_PARA_PREGUNTAR = 5

    async def _es_desmedido(self, it: dict) -> Optional[dict]:
        """¿La cantidad pedida es tan grande que hay que confirmarla? Devuelve el texto del
        aviso, en las MISMAS unidades en que se ha pedido (pedir 500 g y que te conteste
        '50 ud de cucharada sopera' no ayuda a nadie)."""
        matches = await self.search_foods(it.get("nombre", ""), limit=1)
        if not matches:
            return None
        alimento = matches[0]
        maxr = self._max_auto_g(alimento) or 0
        if not maxr:
            return None
        cantidad = float(it.get("cantidad") or 0)
        unidad = it.get("unidad")
        racion = float(alimento.get("racion") or 100) or 100.0
        if unidad == "kg":
            gramos = cantidad * 1000
        elif unidad == "ud":
            gramos = cantidad * racion
        else:
            gramos = cantidad
        if gramos <= self._VECES_PARA_PREGUNTAR * maxr:
            return None
        pedido = (f"{cantidad:g} kg" if unidad == "kg"
                  else f"{cantidad:g} ud" if unidad == "ud" else f"{gramos:g} g")
        return {"texto": (f"{pedido} de {alimento.get('nombre', '').strip()} son "
                          f"{gramos:g} g, y lo habitual es no pasar de {int(maxr)} g.")}

    def _confirmado(self, it: dict) -> bool:
        """¿Es justo lo que acabamos de preguntarle y ya ha dicho que sí?"""
        pendiente = self.state.get("pendiente_confirmar")
        if not pendiente:
            return False
        mismo = (self._norm_text(pendiente.get("nombre", "")) == self._norm_text(it.get("nombre", ""))
                 and float(pendiente.get("cantidad") or 0) == float(it.get("cantidad") or 0))
        if mismo:
            self.state["pendiente_confirmar"] = None
        return mismo

    _RE_SI = re.compile(r"^(si|sii+|claro|venga|dale|adelante|confirmo|ponlo|hazlo|"
                        r"si quiero|eso es|correcto|ok|vale)\b")

    def _respuesta_donde_estoy(self) -> dict:
        """Dónde estamos: la comida de ahora, su objetivo, lo que ya lleva y lo que falta."""
        key = self.current_meal_key()
        obj = self.get_current_meal_macros()
        ov = self.get_day_overview()
        hechas = ov.get("completas", 0)
        total = ov.get("total_comidas", self.total_meals())
        alimentos = self.state["comidas_completadas"].get(key, {}).get("alimentos", [])
        msg = (f"Vas por {self.meal_label(key)} ({hechas} de {total} comidas hechas). "
               f"Su objetivo es {obj['P']} g de proteína, {obj['H']} de hidratos y {obj['G']} de grasa.")
        if alimentos:
            msg += " Ahora mismo lleva: " + ", ".join(a.get("nombre", "") for a in alimentos) + "."
        else:
            msg += " Está vacía: dime qué te apetece y la montamos."
        return {"action": "status", "message": msg,
                "meals_status": self.get_meals_status(), "day_overview": ov}

    async def process_message(self, user_input: str) -> dict:
        """Interpreta el mensaje con el LLM (router de intención) y ejecuta con código
        determinista. El LLM solo entiende QUÉ quiere el usuario; la matemática es del código."""
        # ¿Está eligiendo una de las opciones ofrecidas ("la 1", "el segundo", "salmón")?
        # Se resuelve ANTES del router LLM: es determinista y evita malinterpretaciones.
        pick = self._match_option_pick(user_input)
        if pick is not None:
            tipo, valor = pick
            if tipo == "range":
                # "la 9" con 6 opciones: avisar y MANTENER la lista para que pueda reelegir.
                return {"action": "no_foods",
                        "message": f"Solo hay {valor} opciones en la lista. Dime un número del 1 al {valor}, o el nombre.",
                        "day_overview": self.get_day_overview()}
            self.state["last_options"] = []
            # Si la opción llevaba cantidad fijada por el usuario ("150g de pavo"), se respeta.
            return await self.add_food_by_id(
                valor.get("alimento_id"),
                valor.get("cantidad_g") if valor.get("cantidad_fija") else None,
            )

        # "¿qué sigue?", "¿qué comida toca?", "¿dónde voy?" son PREGUNTAS, no la orden de
        # guardar y avanzar. El router las clasificaba como "complete" por la palabra
        # "sigue" y contestaba "esta comida está vacía: dime qué quieres comer antes de
        # guardarla", que no responde a lo que se ha preguntado. Se resuelve antes del LLM.
        # ¿Está confirmando la barbaridad que le acabamos de preguntar? Va lo primero:
        # "vale" y "ok" también son cortesía, y aquí significan "sí, ponlo".
        pendiente = self.state.get("pendiente_confirmar")
        if pendiente:
            if self._RE_SI.match(self._norm_text(user_input).strip(" ¡!.,")):
                res = await self.set_food_quantity(
                    pendiente["nombre"], cantidad=pendiente["cantidad"],
                    unidad=pendiente.get("unidad"), incrementar=pendiente.get("sumar", False))
                self.state["pendiente_confirmar"] = None
                if res.get("ok"):
                    resp = self._meal_response(
                        [{"nombre": res["nombre"], "cantidad_display": res["cantidad_display"],
                          "macros": res["macros"]}], [])
                    resp["message"] = f"Hecho: {res['cantidad_display']} de {res['nombre']}. Tú mandas."
                    return resp
                return {"action": "no_foods", "message": "No he podido ponerlo.",
                        "day_overview": self.get_day_overview()}
            # Cualquier otra cosa cancela la pregunta y sigue su curso normal.
            self.state["pendiente_confirmar"] = None

        # Un emoji suelto, un mensaje vacío o un manotazo al teclado no necesitan el manual
        # de instrucciones de cinco líneas: se contesta corto y se sigue.
        sin_sentido = self._sin_contenido(user_input)
        if sin_sentido:
            return {"action": "no_foods", "message": sin_sentido,
                    "day_overview": self.get_day_overview()}

        # "lo mismo que en la comida 2": se copia, que las comidas del día están aquí.
        idx_copiar = self._intento_copiar_comida(user_input)
        if idx_copiar:
            r = self.copiar_comida(idx_copiar)
            if r.get("ok"):
                resp = self._meal_response(r["copiados"], [])
                resp["message"] = (f"Copiado de {r['origen']} a {r['destino']}: "
                                   + ", ".join(c["nombre"] for c in r["copiados"]) + ".")
                return resp
            if r.get("vacia"):
                return {"action": "no_foods",
                        "message": f"{r['origen']} está vacía, no hay nada que copiar.",
                        "day_overview": self.get_day_overview()}
            if r.get("misma"):
                return {"action": "no_foods", "message": "Esa es la comida en la que estás.",
                        "day_overview": self.get_day_overview()}

        if self._pregunta_donde_estoy(user_input):
            return self._respuesta_donde_estoy()

        # "¿esto cuadra?" y "hola/gracias": las dos las contestaba el LLM a su manera, una
        # diciendo que sí cuando no, y la otra con el muro de "no reconocí ningún alimento".
        if self._pregunta_si_cuadra(user_input):
            return self._respuesta_si_cuadra()
        if self._es_cortesia(user_input):
            return self._respuesta_cortesia(user_input)

        # Restricciones dichas de pasada: recordarlas el resto de la sesión para no
        # sugerir esos alimentos después. Además de "sin X" y "no quiero X", ahora entra
        # la forma en que la gente cuenta de verdad una intolerancia o una alergia: "no
        # puedo comer lácteos", "soy alérgico al marisco", "no tolero la lactosa".
        self._registrar_restricciones(user_input)

        data = await self.understand(user_input)
        intent = data.get("intent")
        if intent == "llm_fallo":
            # El interprete no está disponible ahora mismo: pedir reintento en
            # vez de fingir una actualización vacía.
            return {"action": "no_foods",
                    "message": "Ahora mismo no he podido interpretar tu mensaje (fallo puntual del asistente). "
                               "Escríbelo otra vez en unos segundos, o usa los botones de abajo.",
                    "day_overview": self.get_day_overview()}
        # Cualquier acción que no sea informativa invalida las opciones pendientes
        # (si dice "pollo y arroz", un "2" posterior ya no debe referirse a la lista vieja).
        if intent not in ("question", "status", "summary", "list", "none"):
            self.state["last_options"] = []
        # Referencia de comida ("comida 2", "post", "intra") resuelta al índice real
        goto_idx = self.resolve_meal_ref(data.get("goto")) if data.get("goto") is not None else None

        # Día ya completo: no tocar comidas "fantasma". Se puede consultar, y se puede
        # reabrir una comida concreta ("edita la comida 2"); el resto se explica.
        if self.state.get("step") == "complete" and intent not in ("question", "status", "summary", "list", "none", "goto"):
            if goto_idx:
                self.go_to_meal(goto_idx)  # reabre esa comida y sigue con la acción pedida
            else:
                return {"action": "no_foods",
                        "message": ("El día ya está completo ✅. Si quieres cambiar algo, dime p.ej. "
                                    "\"edita la comida 2\" y la reabro; también puedo darte el "
                                    "\"resumen del día\"."),
                        "day_overview": self.get_day_overview()}

        # ── Operaciones deterministas que el router interpreta mal (decremento, reemplazo,
        #    multiplicador, add+quitar mixto). Se detectan del texto crudo y tienen PRIORIDAD
        #    sobre el intent del LLM (que p.ej. malclasifica "agrega X y quita Y" como pregunta). ──
        _puede_mutar = self.state.get("step") != "complete" or bool(goto_idx)
        # "quita todo el arroz" el router lo suele marcar como 'clear' (vaciar); lo
        # interceptamos aparte para quitar SOLO ese alimento.
        if _puede_mutar and self.state["comidas_completadas"].get(self.current_meal_key(), {}).get("alimentos"):
            qt = self._intento_quitar_todo(user_input)
            if qt:
                if goto_idx:
                    self.go_to_meal(goto_idx)
                quitado = self.remove_food_by_name(qt)
                resp = self._meal_response([], [])
                resp["message"] = (f"Quité {quitado.get('nombre')} de esta comida." if quitado
                                   else f"No veo {qt} en esta comida.")
                return resp

        if _puede_mutar and intent not in ("suggest", "complete", "clear", "rebalance", "status", "summary", "list"):
            mix = self._intento_mixto(user_input)
            if mix:
                if goto_idx:
                    self.go_to_meal(goto_idx)
                nombre, neto = mix
                if abs(neto) < 0.001:
                    resp = self._meal_response([], [])
                    resp["message"] = "Lo dejo igual (lo que añades y quitas se compensa)."
                    return resp
                if neto > 0:
                    r = await self.set_food_quantity(nombre, cantidad=neto, unidad="ud", incrementar=True)
                    resp = self._meal_response([{"nombre": r.get("nombre"), "cantidad_display": r.get("cantidad_display"), "macros": r.get("macros")}] if r.get("ok") else [], [])
                else:
                    r = await self.decrementar_alimento(nombre, -neto)
                    resp = self._meal_response([], [])
                resp["message"] = f"Ajustado: {r.get('nombre') or nombre}." if r.get("ok") else f"No pude ajustar {nombre}."
                return resp

            dec = self._intento_decremento(user_input)
            if dec:
                if goto_idx:
                    self.go_to_meal(goto_idx)
                res = await self.decrementar_alimento(dec[0], dec[1], dec[2])
                resp = self._meal_response([], [])
                if not res.get("ok"):
                    resp["message"] = ("Esta comida está vacía." if res.get("vacio")
                                       else "No veo ese alimento en la comida para quitarlo.")
                elif res.get("removido"):
                    resp["message"] = f"Quité {res['nombre']} de esta comida."
                else:
                    resp["message"] = f"Bajé {res['nombre']} a {res.get('cantidad_display')}."
                return resp

            rep = self._intento_reemplazo(user_input)
            if rep:
                if goto_idx:
                    self.go_to_meal(goto_idx)
                old, newspec = rep
                quitado = self.remove_food_by_name(old)
                cant, uni, nombre = self._parse_cantidad_spec(newspec)
                resp = await self.add_foods([{"nombre": nombre, "cantidad": cant, "unidad": uni, "sumar": False}])
                viejo = quitado.get("nombre") if quitado else old
                nota = f"Cambié {viejo} por {nombre}." if quitado else f"No tenías {old}; añadí {nombre}."
                resp["message"] = nota + ("\n" + resp["message"] if resp.get("message") else "")
                return resp

            mult = self._intento_multiplicador(user_input)
            # El limite de palabras esta para no disparar el multiplicador cuando "mitad"
            # aparece de pasada en una frase larga. Pero solo hace falta cuando NO se sabe
            # a que alimento se refiere: si nombra uno ("la cantidad de zumo que sea la
            # mitad", 8 palabras), la intencion es inequivoca y la longitud da igual.
            _mult_claro = bool(mult and mult[1] != "__ultimo__" and len(mult[1]) > 2)
            if mult and (_mult_claro or len(user_input.split()) <= 6) \
                    and self.state["comidas_completadas"].get(self.current_meal_key(), {}).get("alimentos"):
                if goto_idx:
                    self.go_to_meal(goto_idx)
                res = await self.aplicar_multiplicador(mult[0], mult[1])
                if res.get("ok"):
                    resp = self._meal_response([{"nombre": res["nombre"], "cantidad_display": res.get("cantidad_display"), "macros": res.get("macros")}], [])
                    resp["message"] = f"Ajusté {res['nombre']} a {res.get('cantidad_display')}."
                    return resp

            # "ponlo en 2" / "que sean 150 g" / "añade 20 g más": ajuste del ÚLTIMO alimento.
            adj = self._intento_ajuste_ultimo(user_input)
            if adj:
                alimentos = self.state["comidas_completadas"].get(self.current_meal_key(), {}).get("alimentos", [])
                if alimentos:
                    if goto_idx:
                        self.go_to_meal(goto_idx)
                    cant, uni, inc = adj
                    res = await self.set_food_quantity(alimentos[-1].get("nombre"), cantidad=cant, unidad=uni, incrementar=inc)
                    if res.get("ok"):
                        resp = self._meal_response([{"nombre": res["nombre"], "cantidad_display": res.get("cantidad_display"), "macros": res.get("macros")}], [])
                        resp["message"] = f"Ajusté {res['nombre']} a {res.get('cantidad_display')}."
                        return resp

        if intent == "goto":
            if goto_idx and self.go_to_meal(goto_idx):
                resp = self._meal_response([], [])
                resp["message"] = (f"Estás editando {self.meal_label(self.current_meal_key())}. "
                                   "Añade o quita alimentos, o dime \"lista esta comida\" para verla.")
                return resp
            return {"action": "no_foods",
                    "message": ("No encontré esa comida. Dime, p.ej., \"edita la comida 2\" "
                                "o \"ve al post-entreno\"."),
                    "day_overview": self.get_day_overview()}

        if intent == "list":
            # `vista: dia` = la app pinta el resumen con <ChatDayOverview> (una fila por
            # comida, con sus alimentos y barras) en vez de soltar el texto de list_meals_text,
            # que se queda como respaldo.
            return {"action": "message", "message": self.list_meals_text(goto_idx),
                    "vista": "dia",
                    "day_overview": self.get_day_overview()}

        if intent == "status":
            ov = self.get_day_overview()
            rem = ov.get("restante", {})
            rem_c = ov.get("comida_restante", {})
            return {"action": "status", "meals_status": self.get_meals_status(),
                    # En palabras: un "hidratos -32 g" en mitad de la frase no lo lee nadie.
                    "message": (f"En el día te queda: {self._texto_falta_sobra(rem)}. "
                                f"En {ov.get('comida_nombre', 'esta comida')}: "
                                f"{self._texto_falta_sobra(rem_c)}."),
                    "day_overview": ov}

        if intent == "complete":
            comida = self.state["comidas_completadas"].get(self.current_meal_key(), {})
            if not comida.get("alimentos"):
                return {"action": "no_foods",
                        "message": "Esta comida está vacía: dime qué quieres comer antes de guardarla.",
                        "day_overview": self.get_day_overview()}
            return {"action": "complete_request"}

        if intent == "suggest":
            # "¿hay otras opciones de tostadas?" pedía MÁS DE LO MISMO, y se contestaba con
            # una lista de proteína: callos, batidos y fiambre cuando había pedido tostadas.
            # Si se puede saber de qué habla, se le dan más de eso.
            # El término solo se hereda si la lista sigue en pantalla sin elegir: un
            # "dame opciones" tres comidas después no puede seguir sacando tostadas.
            heredado = self.state.get("last_termino") if self.state.get("last_options") else None
            termino = data.get("termino") or heredado
            if termino and not data.get("marca"):
                mas = await self._mas_opciones_termino(termino)
                if mas is not None:
                    return mas
            return await self.suggest_foods_for_current_meal(macro=data.get("macro"),
                                                             marca=data.get("marca"))

        if intent == "summary":
            return {"action": "summary", "day_overview": self.get_day_overview()}

        if intent == "rebalance":
            return await self.rebalance_current_meal()

        if intent == "clear":
            if data.get("goto") is not None and goto_idx is None:
                return {"action": "no_foods",
                        "message": "No pude identificar qué comida vaciar. Dime, p.ej., \"vacía la comida 2\" o \"vacía el post-entreno\".",
                        "day_overview": self.get_day_overview()}
            nombre = self.clear_meal(goto_idx)
            if nombre:
                resp = self._meal_response([], [])
                resp["message"] = f"He vaciado {nombre}. Puedes empezarla de nuevo."
                return resp
            return {"action": "no_foods",
                    "message": "No pude identificar qué comida vaciar. Dime, p.ej., \"vacía la comida 2\".",
                    "day_overview": self.get_day_overview()}

        if intent == "remove":
            # "quita el arroz de la comida 2": navegar primero a esa comida
            if goto_idx:
                self.go_to_meal(goto_idx)
            removed = self.remove_food_by_name(data.get("remove") or user_input)
            if removed:
                resp = self._meal_response([], [])
                resp["message"] = f"He quitado {removed.get('nombre')} de esta comida."
                return resp
            return {
                "action": "no_foods",
                "message": ("No encontré ese alimento en la comida actual para quitarlo. "
                            "Míralo en la lista de arriba y toca la × del que quieras eliminar."),
                "day_overview": self.get_day_overview(),
            }

        if intent == "question":
            return await self.answer_question(user_input)

        # intent == "add" (o fallback): añadir los alimentos que dijo.
        # Si el mensaje también pedía quitar algo ("quítame el arroz y pon más pollo"),
        # primero se quita y luego se añade.
        foods = data.get("foods") or []
        # "añade pollo a la comida 3": navegar a esa comida antes de tocarla
        if goto_idx and (foods or data.get("remove")):
            self.go_to_meal(goto_idx)
        quitado = None
        if data.get("remove"):
            quitado = self.remove_food_by_name(data["remove"])
        if foods:
            # ¿Suma a lo que ya hay ("pon/agrega un huevo") o fija el total ("deja en 2")?
            # Determinista en código. Solo aplica a unidades/porciones: los gramos explícitos
            # ("80 g de arroz") son un objetivo, no un incremento.
            t_norm = self._norm_text(user_input)
            set_marker = bool(self._RE_SET_TOTAL.search(t_norm))
            weak = not set_marker and bool(self._RE_INCREMENTO.search(t_norm))          # incluye un/una (unidades)
            strong = not set_marker and bool(self._RE_INCREMENTO_FUERTE.search(t_norm))  # verbos/más (gramos)
            cnt_hint = self._num_pedido(user_input)
            vaga = self._tiene_medida_vaga(user_input)
            for f in foods:
                # En gramos solo se incrementa con marca fuerte ('añade 20 g más'); en
                # unidades basta 'un/una/otro/más' ('un huevo más').
                is_incr = strong if f.get("unidad") == "g" else weak
                f["sumar"] = is_incr
                # "un huevo más" / "otro huevo": el router a veces no captura el número. Si es un
                # incremento con conteo explícito Y no es una medida vaga ("un poco de arroz"),
                # fijar +N unidades en vez de auto-dimensionar (que lo rechazaría con "no cabe").
                if is_incr and f.get("cantidad") is None and cnt_hint and not vaga:
                    f["cantidad"] = cnt_hint
                    f["unidad"] = f.get("unidad") or "ud"
            resp = await self.add_foods(foods)
            if quitado:
                # Si lo quitado se volvió a añadir (era un cambio de cantidad), decirlo como
                # cambio, no como "quité X" (que hace creer al usuario que perdió el alimento).
                mismo = next((a for a in resp.get("foods_added", [])
                              if self._norm_text(a.get("nombre", "")) == self._norm_text(quitado.get("nombre", ""))), None)
                if mismo:
                    nota = f"He cambiado {mismo['nombre']} a {mismo.get('cantidad_display', '')}."
                else:
                    nota = f"He quitado {quitado.get('nombre')} de esta comida."
                resp["message"] = (nota + "\n" + resp["message"]) if resp.get("message") else nota
            return resp
        if quitado:
            resp = self._meal_response([], [])
            resp["message"] = f"He quitado {quitado.get('nombre')} de esta comida."
            return resp

        # Mensaje corto sin alimentos según el router ("arroz" a secas, "otro huevo",
        # "un huevo más"): tratarlo como un alimento directo antes de rendirse. Se quitan
        # las palabras de relleno/cantidad para buscar SOLO el alimento (el router falla a
        # veces con estas frases sin verbo). Solo con match de cobertura real (nada de colar
        # "noodles" cuando el usuario dijo "no").
        _SMALLTALK = {"hola", "buenas", "gracias", "vale", "venga", "adios", "hasta", "luego"}
        _FILLER = {"otro", "otra", "mas", "uno", "una", "dos", "tres", "cuatro", "cinco",
                   "pon", "ponme", "dame", "quiero", "agrega", "anade", "suma", "echa", "mete",
                   "por", "favor", "gramos", "gramo", "unidad", "unidades", "unos", "unas"}
        toks_cortos = [t for t in re.findall(r"[a-zñ]+", self._norm_text(user_input)) if len(t) >= 3]
        content = [t for t in toks_cortos if t not in _FILLER]
        if intent in ("add", "none") and len(user_input.split()) <= 4 and content \
                and not any(t in _SMALLTALK for t in toks_cortos):
            query = " ".join(content)
            matches = await self.search_foods(query, limit=1)
            if matches and not matches[0].get("_match_parcial") \
                    and all(t in self._norm_text(matches[0].get("nombre", "")) for t in content):
                # Conteo pedido ("dos claras", "un huevo más" -> 2/1) y si suma o fija.
                # Las medidas vagas ("un poco de arroz") no fuerzan conteo: se auto-dimensionan.
                cnt = None if self._tiene_medida_vaga(user_input) else self._num_pedido(user_input)
                incr = self._es_incremento(user_input)
                return await self.add_foods([{"nombre": query, "cantidad": cnt, "unidad": None,
                                              "sumar": bool(incr and cnt)}])

        # "quiero añadir un alimento" / "voy a poner algo" / "quiero sugerir un alimento":
        # dice que quiere meter algo pero no dice QUÉ. No es una duda de nutrición (que es
        # a donde iba por tener 4+ palabras) ni una petición de que sugiera el asistente:
        # el que va a decir el alimento es él, así que se le pregunta cuál.
        if intent in ("add", "none") and self._RE_ADD_SIN_DECIR_QUE.search(self._norm_text(user_input)):
            return {"action": "no_foods",
                    "message": ("Dime cuál quieres añadir: el alimento y, si la tienes, la "
                                "cantidad (por ejemplo \"pechuga de pollo\" o \"200 g de arroz\"). "
                                "Si prefieres que elija yo, dime \"sugiéreme algo\"."),
                    "day_overview": self.get_day_overview()}

        # Sin alimentos claros: si parece una frase, tratar como duda; si no, pedir alimentos.
        if len(user_input.split()) >= 4:
            return await self.answer_question(user_input)
        msg = ("No reconocí ningún alimento ahí. Dime qué quieres comer (p.ej. \"huevos, pan, "
               "claras\"), o pregúntame \"¿qué me falta?\". También puedes manejar las comidas "
               "por texto: \"edita la comida 2\", \"lista la comida 1\", \"vacía el post-entreno\". "
               "O pulsa \"Sugerir alimentos\" o \"Guardar y siguiente\".")
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


# Sesiones persistidas en Mongo (db.chatbot_sessions). Todo el estado del bot vive
# en self.state (JSON puro): en cada petición se crea la instancia y se rehidrata
# desde Mongo, y la ruta guarda al terminar. Así la sesión sobrevive a reinicios
# del backend y funciona con varios workers (antes vivía en un dict en RAM y
# obligaba a --workers 1).


async def get_or_create_chatbot(session_id: str, db, user_macros: dict = None) -> NutritionChatbot:
    """Obtiene o crea un chatbot para la sesión, rehidratando el estado desde Mongo."""
    chatbot = await create_chatbot(session_id, db, user_macros)
    doc = await db.chatbot_sessions.find_one({"session_id": session_id}, {"_id": 0, "state": 1})
    if doc and doc.get("state"):
        chatbot.state = doc["state"]
        if user_macros:
            chatbot.state.setdefault("macros_usuario", {}).update(user_macros)
    return chatbot


async def save_chatbot_session(chatbot: NutritionChatbot):
    """Persiste la sesión tras cada interacción (última escritura gana)."""
    from datetime import timezone
    await chatbot.db.chatbot_sessions.update_one(
        {"session_id": chatbot.session_id},
        {"$set": {"state": chatbot.state, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )


async def session_exists(session_id: str, db) -> bool:
    """True si la sesión está persistida en Mongo."""
    return await db.chatbot_sessions.count_documents({"session_id": session_id}, limit=1) > 0


async def clear_session(session_id: str, db=None):
    """Limpia una sesión de chatbot."""
    if db is not None:
        await db.chatbot_sessions.delete_one({"session_id": session_id})
