"""
JG12 Nutrition Chatbot - Backend
================================
Chatbot conversacional que ayuda al cliente a montar su dieta del día.
Usa Claude como interfaz y las funciones de calculator.py y calma_engine.py.
"""

import math
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

# Palabras que son una unidad y no un alimento. Ver `NutritionChatbot._sacar_cantidad`.
_SOLO_UNIDAD = {"g", "gr", "grs", "gramo", "gramos", "kg", "kgs", "kilo", "kilos",
                "ml", "mls", "mililitro", "mililitros", "l", "litro", "litros",
                "ud", "uds", "unidad", "unidades"}


# =====================================================
# NOTA (F3, 06-08-2026): el router de intenciones, sus 30 regex, los 17 interceptores
# _intento_* y la tabla de 83 sinónimos se BORRARON tras validar el agente con el banco
# de casos (router 48/60; agente 59-60/60). La conversación la lleva agent_loop.py con
# las herramientas de agent_tools.py. Aquí queda el MOTOR de la sesión: estado, búsqueda,
# dimensionado, mutaciones de comida y exportación. Volver atrás es git revert.
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
            # Las que YA venian montadas de Nutricion al abrir el chat. No se tocan sin
            # decirselo al cliente: es trabajo suyo de antes de esta conversacion.
            "comidas_traidas": [],
            "seen_sugg": {},  # Sugerencias ya ofrecidas por comida (para no repetirlas)
            "last_termino": None,  # De qué tipo de alimento iba la última lista ("tostadas")
            "termino_vistos": [],  # Ids ya enseñados de ese término, para no repetirlos
            # Lo que el cliente cuenta de sí mismo y hace falta luego: lo que tiene en
            # casa, gustos, horarios. Al agente solo se le pasan los ÚLTIMOS 6 mensajes,
            # así que sin esto lo usaba y cinco mensajes después contestaba «no puedo ver
            # lo que tienes en casa, no guardo esa info» -- en la misma conversación.
            "notas_cliente": [],
        }
        
        # Historial de mensajes para persistencia (lo rellena el agente: solo lo humano)
        self.messages_history = []
    
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
        orden_antiguo = list(self.state.get("meal_order") or [])
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
        # el intra". Los objetivos nuevos se ven al momento en cada comida.
        #
        # Las comidas que ya no existen en el día nuevo (el intra y el post al pasar a
        # descanso, la Comida 4 al bajar a 3) no pueden quedarse donde estaban: se colarían
        # en la dieta guardada sin estar en el recorrido. Hasta el 08-08-2026 se BORRABAN,
        # y en silencio: Francisco montó el post, pasó a descanso y desapareció sin que
        # nadie se lo dijera -- y el asistente, que tampoco se había enterado, le contestó
        # que "lo del post lo tienes metido en la Comida 2". Ahora se traspasan de verdad a
        # la comida principal más cercana (la de antes en el orden viejo, y si no la de
        # después) y el traspaso se cuenta, para que ni se pierda el trabajo ni haya que
        # adivinarlo. Descuadra la comida destino, claro: por eso se avisa y se puede
        # cuadrar a mano, que es mejor que perderlo.
        vivas = set(self.state["meal_order"])
        completadas = self.state.get("comidas_completadas") or {}
        caidas = [k for k in orden_antiguo if k not in vivas]
        caidas += [k for k in completadas if k not in vivas and k not in caidas]

        self.state["comidas_completadas"] = {k: v for k, v in completadas.items() if k in vivas}
        self.state["saved_meals"] = [k for k in (self.state.get("saved_meals") or []) if k in vivas]
        self.state["comidas_traidas"] = [k for k in (self.state.get("comidas_traidas") or [])
                                         if k in vivas]

        reubicado = []
        for k in caidas:
            alimentos = (completadas.get(k) or {}).get("alimentos") or []
            if not alimentos:
                continue
            destino = self._comida_mas_cercana_viva(k, orden_antiguo, self.state["meal_order"])
            if not destino:
                continue
            for f in alimentos:
                alimento = f.get("alimento")
                cantidad_g = f.get("cantidad_g", f.get("cantidad", 0)) or 0
                if not alimento or cantidad_g <= 0:
                    continue
                self._append_food(destino, alimento, cantidad_g, self._macros_at(alimento, cantidad_g))
                reubicado.append({
                    "desde": k, "desde_nombre": self.meal_label(k),
                    "hacia": destino, "hacia_nombre": self.meal_label(destino),
                    "nombre": f.get("nombre", ""), "cantidad_g": cantidad_g,
                })
        self.state["reubicado_al_reconfigurar"] = reubicado

        if not self.state["comidas_completadas"]:
            self.state["acumulado_cereales_panes"] = 0
            self.state["acumulado_frutos_secos"] = 0

        return self.state["distribucion"]

    @staticmethod
    def _comida_mas_cercana_viva(key: str, orden_antiguo: list, orden_nuevo: list) -> str:
        """A qué comida se traspasa lo que había en una que ya no existe: la anterior del
        orden viejo que siga viva (el intra cae en la comida de antes de entrenar), y si
        no hay ninguna detrás, la primera que venga después."""
        vivas = set(orden_nuevo)
        if key in orden_antiguo:
            i = orden_antiguo.index(key)
            for k in reversed(orden_antiguo[:i]):
                if k in vivas:
                    return k
            for k in orden_antiguo[i + 1:]:
                if k in vivas:
                    return k
        return orden_nuevo[0] if orden_nuevo else ""

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

    @staticmethod
    def margen_de(objetivo: float) -> float:
        """Cuánto se puede desviar un macro para que la comida siga estando «cuadrada».

        El margen de Calma son 4 g y en una comida normal está bien: sobre 47 g de proteína
        es un 8 %. Pero el intra pide 9 g de proteína, y ahí esos mismos 4 g son el 44 %:
        Francisco vio en producción «Comida cuadrada. Pulsa Guardar y siguiente» debajo de
        un «5 / 9» de proteína, y con el propio asistente diciendo en el mensaje de al lado
        que faltaban 4 g. Dos cosas contradictorias en la misma pantalla, y la que manda es
        la que le invita a guardar y pasar a otra cosa.

        Así que el margen se estrecha cuando el objetivo es pequeño -- una cuarta parte de
        lo que se pide -- y nunca baja de 1,5 g, que es lo que se puede afinar con cucharas
        y básculas de casa. En una comida normal no cambia nada: el 25 % de 47 es 11, así
        que sigue mandando el 4 de siempre.
        """
        return min(4.0, max(1.5, 0.25 * abs(float(objetivo or 0)))) if objetivo else 4.0

    def comida_cuadrada(self, restante: dict, objetivo: dict = None) -> bool:
        """¿Está cuadrada? Con el margen que le toca a cada macro (ver `margen_de`)."""
        objetivo = objetivo or self.get_current_meal_macros()
        return all(abs(restante.get(m, 0)) <= self.margen_de(objetivo.get(m, 0))
                   for m in ("P", "H", "G"))

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

    # Perfil de momento (db.moment_profiles): en qué momento del día se come cada
    # alimento, aprendido de las dietas reales. Cargado una vez por proceso; si la
    # colección no existe (aún sin generar en este entorno), False = sin perfil y
    # las sugerencias se comportan como siempre.
    _PERFIL_MOMENTO = None

    # Perfil de forma (db.meal_shapes): de cuántas piezas se compone una comida de ese
    # momento y qué parte del macro pone cada una. Mismo trato que el de arriba.
    _PERFIL_FORMA = None

    async def _perfil_momento(self):
        if NutritionChatbot._PERFIL_MOMENTO is None:
            try:
                from moment_profile import PerfilMomento
                perfil = await PerfilMomento.cargar(self.db)
                NutritionChatbot._PERFIL_MOMENTO = perfil if perfil.base else False
            except Exception:
                NutritionChatbot._PERFIL_MOMENTO = False
        return NutritionChatbot._PERFIL_MOMENTO or None

    async def _perfil_forma(self):
        """De cuántas piezas se compone una comida real de cada momento (db.meal_shapes).

        Sin la colección minada (`_perfil_forma.py`) devuelve None y todo sigue como antes:
        cada sugerencia se mide contra el hueco entero de la comida."""
        if NutritionChatbot._PERFIL_FORMA is None:
            try:
                from meal_shape import PerfilForma
                forma = await PerfilForma.cargar(self.db)
                NutritionChatbot._PERFIL_FORMA = forma if forma.hay_datos else False
            except Exception:
                NutritionChatbot._PERFIL_FORMA = False
        return NutritionChatbot._PERFIL_FORMA or None

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
        
        # La tabla de 83 sinónimos (query_mappings) se borró en F3 (06-08-2026):
        # la traducción coloquial->catálogo la hace la búsqueda semántica del agente
        # (food_semantic) ANTES de llegar aquí. Esta función busca lo que le pidan,
        # tal cual: text-search + regex + raíces + corrección de erratas.
        _STOP = {"de", "del", "la", "el", "los", "las", "con", "sin", "al", "a",
                 "en", "un", "una", "unos", "unas", "y", "o", "u", "por", "para"}
        sig_words = [w for w in query_norm.split() if w not in _STOP and len(w) > 1]
        search_term = query_norm
        mapeado = False

        search_norm = normalize(search_term)
        
        # ESTRATEGIA DE BÚSQUEDA MEJORADA:
        # 1. Si es un término específico (>2 palabras), usar regex PRIMERO
        # 2. Si no, usar text search
        # 3. Fallback a búsqueda por palabras
        
        candidates = []
        
        # Paso 1: Para términos específicos (queso fresco batido, crema de cacahuete), regex primero
        words = search_norm.split()
        # Cada palabra tiene que EMPEZAR una palabra del nombre, no aparecer en mitad de
        # otra: "queso.*fresco.*batido" encontraba también lo que llevara esas letras
        # dentro. Ver _regex_termino.
        patron_de = lambda ws: ".*".join(self._regex_termino(w) for w in ws if w)
        if len(words) >= 2:
            regex_pattern = patron_de(words)

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
            regex_pattern = patron_de(words)

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
                            {"nombre": {"$regex": self._regex_termino(word), "$options": "i"}},
                            {"_id": 0}
                        ).limit(30).to_list(30)
                        candidates.extend(word_results)
                    except Exception:
                        pass
        
        # Puntuar candidatos por relevancia
        perfil_uso = await self._perfil_momento()   # frecuencia de uso real, para el boost
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
            elif all(self._es_palabra_del_nombre(w, nombre_norm) for w in query_words):
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
            # Baja prioridad: coincidencia parcial. Tiene que empezar una palabra del
            # nombre: "en mitad de otra palabra" no es una coincidencia, es una casualidad
            # de letras, y era la línea por la que se colaban el chocolate al pedir col o
            # el aceite al pedir té.
            elif any(self._es_palabra_del_nombre(w, nombre_norm) for w in query_words):
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

            # Frecuencia de USO REAL (perfil aprendido de las dietas): lo que la gente
            # come de verdad sube. Sustituye la elección canónica de la tabla borrada en
            # F3 ("huevos" -> huevos enteros L) con datos en vez de con un diccionario.
            if perfil_uso:
                p_uso = perfil_uso.alimentos.get(str(int(food.get("id", 0) or 0)))
                total_uso = p_uso["total"] if p_uso else 0
                if total_uso >= 1000:
                    score += 30
                elif total_uso >= 100:
                    score += 20
                elif total_uso >= 20:
                    score += 10
            
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
                # (aquí había un reintento con la tabla de sinónimos; F3 la borró)
                # Ninguna palabra cubre el término: marcar PARCIAL para que el
                # asistente avise ("no tengo X tal cual, he usado Y") en vez de
                # colar un alimento silenciosamente ("filete de unicornio" -> empanado).
                resultados = [dict(f) for f in resultados]
                for f in resultados:
                    f["_match_parcial"] = query.strip()
        elif _remap and not mapeado and len(sig_words) == 1 and resultados:
            # Con UNA sola palabra no había red: la cobertura de arriba pide dos o más, y
            # por ese hueco se colaba lo de la SAL. Como la sal no está en el catálogo de
            # Jesús, quien la pedía se llevaba «Frutos secos cocktail tostado sin sal»
            # metido en la comida, sin preguntar y sin avisar; con «té» pasaba lo mismo.
            #
            # Lo que decide no es que la palabra aparezca -- en «sin sal» aparece -- sino
            # DÓNDE: si solo sale detrás de un «sin», «con», «bajo en» o «sabor a», es un
            # matiz del alimento, no el alimento. Ver _nucleo_nombre.
            termino = sig_words[0]
            con_nucleo = [food for _, food in unique_scored
                          if self._en_nucleo(termino, food.get("nombre", ""))]
            if con_nucleo:
                resultados = con_nucleo[:limit]
            else:
                resultados = [dict(f) for f in resultados]
                for f in resultados:
                    f["_match_parcial"] = query.strip()
        return resultados

    # Cuántas palabras del principio del nombre dicen DE QUÉ es el alimento. Lo que va
    # más atrás son matices: cómo está hecho, qué lleva, qué no lleva.
    #
    #   Pollo asado                             -> pollo, la 1.ª
    #   Pechuga de pollo                        -> pollo, la 3.ª
    #   Frutos secos cocktail tostado sin sal   -> sal, la 6.ª  => no va de sal
    #   Cacahuete tostado 0 % sal añadida       -> sal, la 5.ª  => no va de sal
    #   Lomo embuchado 25 % menos de sal        -> sal, la 7.ª  => no va de sal
    #
    # Lo que va detrás de estos nexos es lo que el alimento LLEVA, no lo que es: «Pipas
    # con sal» son pipas. Se corta ahí antes de mirar nada más.
    _NEXOS_DE_MATIZ = (" con ", " sin ", " sabor ", " bajo en ")
    # Y el alimento se nombra en la primera palabra, o detrás de un «de»: «Pechuga DE
    # pollo» va de pollo, «Harina DE avena» va de avena. Sin ese «de» lo que sigue es un
    # acompañamiento del nombre, no el alimento: «Chorizo pimienta» es chorizo, «Salchichón
    # pimienta» es salchichón. Es gramática, no una lista de alimentos: vale igual para la
    # sal, el azúcar, el limón o lo que se pida mañana.
    _NEXOS_DE_NUCLEO = ("de", "del")
    # Y ese «de» tiene que ir al principio del nombre, que es donde compone: en «Lomo
    # embuchado 25 % menos DE sal» o «Patatas fritas al punto DE sal» ya no compone nada.
    _PALABRAS_DEL_NUCLEO = 4

    @classmethod
    def _en_nucleo(cls, termino: str, nombre: str) -> bool:
        """¿Lo pedido es de lo que va el alimento, o solo algo que lleva?

        Aquí la palabra tiene que coincidir ENTERA (o en otro género o número), no valer
        de prefijo como en la búsqueda. Buscar admite el prefijo a propósito -- «tostad»
        tiene que llegar a «tostadas» --, pero para decidir si un alimento ES lo que han
        pedido eso es demasiado laxo: barriendo las 3.211 fichas salió que «sal» se colaba
        por «Lomo de SALmón» y «SALchichas», y así nunca habría avisado de que la sal no
        está.
        """
        pedido = cls._norm_text(termino or "")
        n = cls._norm_text((nombre or "").split("(")[0])
        for nexo in cls._NEXOS_DE_MATIZ:
            i = n.find(nexo)
            if i != -1:
                n = n[:i]
        palabras = n.replace(",", " ").replace("-", " ").split()[:cls._PALABRAS_DEL_NUCLEO]
        raiz = cls._regex_raiz(termino)
        for i, palabra in enumerate(palabras):
            if i and palabras[i - 1] not in cls._NEXOS_DE_NUCLEO:
                continue
            if palabra == pedido:
                return True
            if raiz and re.search(raiz, palabra):
                return True
        return False
    
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

    def precargar_desde_dieta(self, comidas: dict, catalogo: dict = None) -> int:
        """Trae a la sesion lo que el cliente YA tiene montado ese dia en Nutricion.

        El asistente vivia en su burbuja: montaba el dia desde cero sin mirar la dieta
        guardada. Con las cuatro comidas hechas y 127 g de proteina encima, su resumen decia
        «llevas 0 g» y «0/4 comidas», y a partir de ahi te ofrecia montar lo que ya tenias.
        Quien lo abriera a media tarde se arriesgaba a que le pisara el trabajo. Lo encontro
        Jesus en el repaso del 11-08 y es lo unico de su lista que hace PERDER trabajo.

        Las claves de comida son las mismas en los dos sitios (C1, Intra, Post, C2...), asi
        que la traida es directa. Solo entran las comidas que existen en la configuracion de
        ahora: si el dia se monto con cuatro comidas y ahora se piden tres, lo que sobra no
        se cuela por la puerta de atras.

        LOS MACROS SE RECALCULAN CON EL MOTOR (12-08). Traerlos y creerse el
        `macros_efectivos` guardado dejaba el dia a CERO: medido contra produccion, de 55.323
        alimentos guardados solo 411 (el 0,7 %) lo traen con algo dentro. El resto son dias
        montados en Nutricion o venidos de la migracion, que nunca escribieron ese campo. Es
        el mismo agujero que dejaba el PDF a cero (`routes/diets.py::_macros_de`, 11-08), solo
        que aqui salia como «llevas 0 g» con el dia entero puesto. En una dieta real de
        produccion: leia 0/0/0 donde el motor dice 192 P / 149 H / 21 G.

        Por eso hace falta el `catalogo` ({id: ficha}): sin la ficha no hay con que contar. Si
        no se pasa, se usa lo guardado y el que llame se queda como estaba.

        Devuelve cuantas comidas se han traido.
        """
        catalogo = catalogo or {}
        vivas = self.state.get("meal_order") or []
        traidas = 0
        # EN ORDEN DE COMIDA, no en el del diccionario: la calibracion progresiva depende de
        # los gramos acumulados ANTES de cada alimento, asi que contar la cena antes del
        # desayuno da otro numero.
        for key in vivas:
            datos = (comidas or {}).get(key)
            alimentos = (datos or {}).get("alimentos") or []
            if not alimentos:
                continue
            entradas = []
            totales = {"P": 0.0, "H": 0.0, "G": 0.0}
            for a in alimentos:
                ficha = catalogo.get(a.get("alimento_id") if a.get("alimento_id") is not None
                                     else a.get("id"))
                cantidad = float(a.get("cantidad_g") or 0)
                m = self._macros_del_guardado(a, ficha, cantidad)
                entradas.append({
                    "nombre": a.get("nombre", ""),
                    "cantidad_g": cantidad,
                    "cantidad_display": a.get("cantidad_display") or f"{int(round(cantidad))} g",
                    "macros": {k: float(m.get(k) or 0) for k in ("P", "H", "G")},
                    # LA FICHA VIAJA CON EL ALIMENTO (caso 46, 13-08-2026).
                    #
                    # Sin esto, lo que el cliente traía montado de Nutrición volvía a
                    # Nutrición SIN `alimento_id`: `export_to_diet_comidas` lo saca de
                    # `food["alimento"]["id"]` y aquí no se guardaba la ficha, así que
                    # volcaba None. Con el id se van también las categorías, la ración y
                    # las unidades, o sea la foto, el «2 ud» y los macros de la etiqueta:
                    # el alimento volvía a la pantalla convertido en un nombre suelto.
                    #
                    # Es la misma forma con la que lo guardan los otros dos caminos que
                    # meten comida en el estado (`add_food_to_meal` y `_process_build_meal`),
                    # que por eso no tenían el problema.
                    "alimento": ficha or {"id": a.get("alimento_id"),
                                          "nombre": a.get("nombre", ""),
                                          "categorias": a.get("categorias"),
                                          "racion": a.get("racion"),
                                          "unidades": a.get("unidades")},
                })
                for k in ("P", "H", "G"):
                    totales[k] += float(m.get(k) or 0)
                # Los acumulados del dia mandan sobre lo que cuenta cada alimento nuevo
                # (calibracion progresiva). Si se traen 300 g de arroz sin sumarlos, el
                # siguiente alimento se calcula como si el dia estuviera vacio.
                cats = str((ficha or {}).get("categorias") or a.get("categorias") or "")
                principal = cats.split("|")[0].strip()
                if principal.startswith(("7", "8")):
                    self.state["acumulado_cereales_panes"] += cantidad
                if principal.startswith(("17.2.1", "17.2.3", "17.2.4", "17.2.6")):
                    self.state["acumulado_frutos_secos"] += cantidad
            self.state["comidas_completadas"][key] = {
                "alimentos": entradas,
                "macros": {k: round(v, 1) for k, v in totales.items()},
            }
            # Una comida que viene de la dieta guardada ESTA guardada. Sin esto, el resumen
            # decia «0 de 4 comidas hechas» con las cuatro puestas (ChatbotPage lo pinta desde
            # `completas`, que cuenta `saved_meals`), y «guardar y siguiente» volvia a pasar
            # por comidas que el cliente ya tenia montadas.
            saved = self.state.setdefault("saved_meals", [])
            if key not in saved:
                saved.append(key)
            # Y APARTE, que viene de fuera de esta conversacion. Es lo que no se puede
            # tocar sin decirselo al cliente: lo que monto el en Nutricion esta manana.
            # Medido: sin esta marca, «montame el dia» le rehacia una comida ya puesta
            # 1 de cada 4 veces. Ver `AgentTools._protegida`.
            traidas_de_fuera = self.state.setdefault("comidas_traidas", [])
            if key not in traidas_de_fuera:
                traidas_de_fuera.append(key)
            traidas += 1

        if traidas:
            self._situarse_en_la_primera_sin_montar()
        return traidas

    def _macros_del_guardado(self, a: dict, ficha: dict, cantidad_g: float) -> dict:
        """Lo que le cuenta a un alimento ya guardado en la dieta.

        Lo guardado solo vale de atajo: la mayoria de los dias no lo tienen (ver
        `precargar_desde_dieta`). Cuando no vale, cuenta el mismo motor que usa el chat al
        anadir a mano (`macros_item_por_acumulado`), con los gramos que ya lleva el dia: asi
        el pan que entra el cuarto cuenta lo que le toca por tramo, y no lo que contaria si
        fuera el primero. De paso, el filtro del tercio y las excepciones por categoria las
        resuelve el motor, no quien lea esto.

        Un cero legitimo -- la lechuga, o el macro que el filtro del tercio descarta -- sigue
        saliendo cero, porque lo dice el motor y no la ausencia del campo.
        """
        guardado = a.get("macros_efectivos") or a.get("macros") or {}
        if guardado and any((guardado.get(k) or 0) > 0 for k in ("P", "H", "G")):
            return guardado
        if not ficha:
            return guardado or {}
        try:
            return macros_item_por_acumulado(
                ficha, cantidad_g,
                acum_cp=self.state["acumulado_cereales_panes"],
                acum_fs=self.state["acumulado_frutos_secos"],
            )
        except Exception:
            # Un alimento raro del catalogo no puede impedir que se recupere el dia.
            return guardado or {}

    def _situarse_en_la_primera_sin_montar(self) -> None:
        """Deja `comida_actual` en la primera comida que aun no tiene nada.

        Si estan todas hechas se queda en la ultima, que es donde tiene sentido seguir
        hablando: por ahi se cambia o se ajusta lo que ya hay.
        """
        orden = self.state.get("meal_order") or []
        hechas = self.state.get("comidas_completadas") or {}
        for i, key in enumerate(orden, start=1):
            if not (hechas.get(key) or {}).get("alimentos"):
                self.state["comida_actual"] = i
                return
        if orden:
            self.state["comida_actual"] = len(orden)

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
                "cuadrado": self.comida_cuadrada(rem, obj),
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

        El GENERO solo se quita en los participios (-ado/-ada, -ido/-ida). Ahi la -o y la
        -a son la misma palabra en masculino y femenino: tostado y tostada son el mismo
        pan. En un sustantivo NO lo son, y quitarlas fundia alimentos distintos:

            pimienta -> pimient <- pimiento     (Francisco, 08-08: pedia pimienta y le
            hueva    -> huev    <- huevo         salian pimientos rojos)
            grana    -> gran    <- grano

        Quitar el plural sigue valiendo para todo, que ahi no hay ambiguedad ninguna.
        """
        p = (palabra or "").strip()
        if p.endswith("es") and len(p) > 4:
            p = p[:-2]
        elif p.endswith("s") and len(p) > 3:
            p = p[:-1]
        if len(p) > 4 and p[-3:] in ("ado", "ada", "ido", "ida"):
            p = p[:-1]
        return p if len(p) >= 4 else ""

    # Cada letra que en el catálogo puede aparecer acentuada, con sus variantes. El regex
    # de Mongo NO normaliza acentos: `\bcafe\b` no encuentra "Café", y por eso el `\b` que
    # ya había en _regex_raiz nunca llegaba a filtrar nada.
    _ACENTOS = {"a": "aá", "e": "eé", "i": "ií", "o": "oó", "u": "uúü", "n": "nñ", "c": "cç"}
    # Frontera por la IZQUIERDA. No vale `\b`: en "chocolate" la "col" empieza en mitad de
    # palabra y `\b` no lo ve. Lo que se exige es que delante no haya letra ni número.
    _INICIO_PALABRA = r"(?<![0-9a-zA-ZáéíóúüñçÁÉÍÓÚÜÑÇ])"

    @classmethod
    def _regex_termino(cls, palabra: str) -> str:
        """Patrón que casa la palabra al PRINCIPIO de una palabra del nombre, con o sin
        acentos.

        Hasta el 08-08-2026 se buscaba la subcadena en cualquier posición, y eso traía:
        «col» -> Barrita proteica doble CHOCOLATE, «te» -> ACEITE de oliva, «ajo» -> atún
        BAJO en sal, «pan» -> pollo emPANado, «ron» -> macaRRONes. Medido sobre las 3.211
        fichas: de los 1.048 candidatos de «te», 962 eran ruido; de los 353 de «col», 278.
        Y como cada consulta a Mongo se corta en 50 en orden natural, el ruido no solo
        ensuciaba la lista: podía dejar fuera lo que se buscaba.

        No se exige final de palabra a propósito: «tostad» tiene que llegar a «tostadas» y
        «pan» a «panes». Quien empieza exactamente por lo pedido ya puntúa más arriba."""
        p = cls._norm_text(palabra or "").strip()
        if not p:
            return ""
        cuerpo = "".join(f"[{cls._ACENTOS[c]}]" if c in cls._ACENTOS else re.escape(c) for c in p)
        return cls._INICIO_PALABRA + cuerpo

    @classmethod
    def _es_palabra_del_nombre(cls, termino: str, nombre_norm: str) -> bool:
        """¿`termino` empieza alguna palabra de `nombre_norm`? La versión en Python del
        mismo criterio, para puntuar sin volver a la base."""
        pat = cls._regex_termino(termino)
        return bool(pat) and bool(re.search(pat, nombre_norm))

    @classmethod
    def _regex_raiz(cls, palabra: str) -> str:
        """Patron que casa la palabra en cualquier genero y numero. "" si no aplica."""
        raiz = cls._raiz(cls._norm_text(palabra))
        if not raiz:
            return ""
        # La "s" suelta hace falta cuando la raíz conserva su vocal ("pavo" -> "pavos");
        # sin ella el plural de las palabras cortas se quedaba fuera.
        return cls._regex_termino(raiz) + r"(s|a|o|as|os|es)?\b"

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
            # El peso de UNA unidad es `peso_unidad`, no `racion`.
            #
            # `racion` es la cantidad de referencia con la que están escritos los macros de
            # la ficha, y para casi todo son 100 g. Usarla como peso de una unidad hacía
            # que «3 claras» entraran como 3 x 100 = 300 g -- tres claras son unos 100 --,
            # y con eso una comida de 47 g de proteína se iba al triple. Con los huevos no
            # se notaba porque ahí `racion` (63) sí es el peso de uno.
            config = get_food_config(alimento)
            peso_unidad = float(config.get("peso_unidad") or 0)
            if not config.get("por_unidad") or peso_unidad <= 0:
                # Este alimento NO se mide por unidades (las claras van por gramos,
                # `unidades=False` en la ficha). Antes se inventaba que una unidad eran
                # 100 g; ahora se dice, y quien convierta que lo pida en gramos.
                return {"ok": False, "nombre": alimento.get("nombre", name),
                        "no_va_por_unidades": True,
                        "racion": float(alimento.get("racion") or 100)}
            cantidad_g = cantidad * peso_unidad
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

        # NÚMEROS REDONDOS (puntos 4 y 6 del doc del 07-08). `calma_suggest` dimensiona de
        # gramo en gramo (STEP_GRANEL = 1), que es lo que hacía Calma, y de ahí salían los
        # 223 g de pechuga y los 42 g de whey que reportó Jesús. `redondeo_salida` está
        # escrito justo para esto desde el 07-08 pero solo estaba enchufado en el recetario:
        # el asistente, que es por donde el cliente monta una comida desde cero, seguía
        # entregando el número crudo.
        #
        # Se aplica AQUÍ y no más arriba porque este es el punto de salida: lo que devuelve
        # `_size_food` es a la vez lo que se le enseña y lo que se le mete en la dieta. Si se
        # redondease dentro del cálculo, cada paso arrastraría su error.
        #
        # Y los macros se recalculan sobre la cantidad ya redondeada: enseñar «200 g · 46 P»
        # cuando los 46 P eran de los 223 g sería peor que el número feo.
        from redondeo_salida import redondear_cantidad
        redondeada = redondear_cantidad(a, cantidad_g, minimo_g=minimo_g)
        if redondeada > 0 and redondeada != cantidad_g:
            cantidad_g = redondeada
            cant = (cantidad_g / racion) if es_unidad else cantidad_g

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

        # Elección canónica APRENDIDA del uso real (sustituye a la tabla borrada en F3).
        # Dos señales, las dos con datos y ninguna con listas:
        #   1. la CABEZA del nombre: quien dice "huevos" quiere huevos ("Huevos
        #      enteros..."), no todo lo que contenga la palabra ("Claras de huevo");
        #   2. el USO: la cabeza tiene que llevarse la mayoría del uso real del término,
        #      y dentro de ella una subfamilia casi todo.
        # "Huevos" pasa (la cabeza son los huevos de verdad y se llevan todo el uso);
        # "pavo" NO pasa (lo que empieza por "Pavo..." apenas se usa: el uso está en
        # pechugas y fiambres) y sigue ofreciendo opciones, que es la decisión de Jesús
        # del 2026-07-17. Sin perfil de uso (colección sin generar), no se auto-elige.
        if not concepto and raiz_pat:
            perfil_uso = await self._perfil_momento()
            if perfil_uso:
                def _uso(c):
                    p = perfil_uso.alimentos.get(str(int(c.get("id", 0) or 0)))
                    return (p or {}).get("total", 0)
                uso_total = sum(_uso(c) for c in cands)
                cabeza = [c for c in cands
                          if re.match(raiz_pat, self._norm_text(c.get("nombre", "")))]
                uso_cabeza = sum(_uso(c) for c in cabeza)
                if cabeza and uso_total >= 50 and uso_cabeza >= 0.5 * uso_total:
                    por_sub = {}
                    for c in cabeza:
                        cc = parse_categories(c.get("categorias"))
                        if cc:
                            sub = ".".join(cc[0].split(".")[:2])
                            por_sub[sub] = por_sub.get(sub, 0) + _uso(c)
                    if por_sub and max(por_sub.values()) >= 0.8 * max(uso_cabeza, 1):
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
        cuadrado = self.comida_cuadrada(restante)
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

        # La cantidad, fuera del nombre, ANTES de buscar nada (ver `_sacar_cantidad`). Va
        # aqui y no en `_normalize_food_items` porque la herramienta del agente llama
        # derecha a `add_foods`: puesto alli, esta ruta -- la que usan los clientes -- se
        # quedaba sin el arreglo y «500 ml de leche entera» seguia metiendo leche de
        # almendras.
        items = [dict(it, **dict(zip(("nombre", "cantidad", "unidad"),
                                     self._sacar_cantidad(it.get("nombre"), it.get("cantidad"),
                                                          it.get("unidad")))))
                 for it in (items or [])]

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
            elif res.get("no_va_por_unidades"):
                not_found.append({
                    "buscado": it["nombre"],
                    "razon": (f"{res['nombre']} no se mide por unidades en el método, va por "
                              f"GRAMOS. Convierte tú lo que ha pedido a gramos (una clara "
                              f"de huevo son unos 33 g, una cucharada unos 10) y vuelve a "
                              f"pedirlo con unidad='g'. No te lo inventes en unidades."),
                    "va_por_gramos": True})
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
            filtrar_por_tipo_comida, cat_in_list, get_categoria_principal, es_sugerible,
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
                and es_sugerible(a)
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
            es_sugerible, prioridad_post,
        )

        MACRO_LBL = {"P": "proteína", "H": "hidratos", "G": "grasa"}
        restante = self.get_remaining_macros()
        if self.comida_cuadrada(restante):
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

        # Quitar los evitados y lo que no se propone por iniciativa propia (ingredientes
        # crudos y condimentos: masa de pizza, harina de repostería, mermelada, azúcar
        # suelto, salsas, refrescos). Las categorías de la fase ya acotan; los preferidos
        # solo priorizan, no excluyen - si el usuario no marcó "arroces" igual debe ver arroz.
        pool = [a for a in pool
                if es_sugerible(a)
                and not any(kw in (a.get("nombre", "") or "").lower() for kw in avoid_keywords)
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

        # Coherencia con el MOMENTO del día (perfil aprendido de las dietas reales,
        # db.moment_profiles): a las 8 de la mañana no se ofrecen callos ni entrecot.
        # Solo se poda lo claramente atípico (coherencia < 0.25), la comida peri queda
        # neutra por diseño, con marca pedida no se toca (quiere ver SUS productos), y
        # si la poda dejara poco donde elegir, se relaja sola antes que quedarse corta.
        if not marca:
            perfil = await self._perfil_momento()
            if perfil:
                from meal_moment import momento_de_comida
                momento = momento_de_comida(key, self.state.get("num_comidas") or 4,
                                            self.state.get("single_meal", False))
                tipicos = [a for a in pool if perfil.coherencia(a, momento) >= 0.25]
                if len(tipicos) >= limit * 2:
                    pool = tipicos

        # LO QUE LE TOCA A UNA PIEZA, NO LA COMIDA ENTERA (13-08-2026).
        #
        # Aquí se dimensionaba contra lo que falta de toda la comida, así que la lista salía
        # llena de alimentos que la cubren ELLOS SOLOS: con 47 g de proteína pendientes,
        # «Yogur +Proteínas 470 g», «Batido proteico 130 g», «Jamón serrano 130 g». Francisco,
        # 12-08: «me ofreció todo yogur o batidos pero nada de proteína real como huevos, u
        # otros acompañamientos, tostadas, palta, frutas».
        #
        # Una comida real de ese momento reparte su proteína entre varias piezas (`meal_shapes`,
        # medido sobre las dietas de Jesús), así que cada alimento se mide contra ESA parte.
        # El yogur pasa a salir en su ración normal y los huevos, el pan o la fruta dejan de
        # quedar fuera por «no llegar». En el peri no se toca: ahí una pieza sí es la comida.
        hueco_pieza = dict(restante)
        # Con un solo macro pendiente no hay comida que montar, hay que rematarla: ahí la
        # sugerencia tiene que CERRAR lo que falta (caso 39 de Jesús). El reparto por
        # piezas es para cuando queda comida por delante.
        pendientes = sum(1 for m in ("P", "H", "G") if restante[m] > 4)
        if not es_peri and pendientes >= 2:
            forma = await self._perfil_forma()
            if forma:
                from meal_moment import momento_de_comida
                momento = momento_de_comida(key, self.state.get("num_comidas") or 4,
                                            self.state.get("single_meal", False))
                cuota = forma.cuota(momento, driver, max(restante[driver], 0))
                if cuota > 0:
                    hueco_pieza[driver] = min(restante[driver], cuota)

        # Para ordenar por lo que se pone de verdad a esta hora (más abajo): el perfil de
        # uso, el momento y el catálogo por id. En el peri no aplica -- ahí el polvo es lo
        # que toca -- y sin perfil minado se queda en None y todo sigue como antes.
        from meal_moment import momento_de_comida
        perfil_uso = None if es_peri else await self._perfil_momento()
        momento_actual = momento_de_comida(key, self.state.get("num_comidas") or 4,
                                           self.state.get("single_meal", False))
        por_id = {int(a["id"]): a for a in all_foods if a.get("id") is not None}

        # Dimensionar; agrupar por TIPO de alimento (categoría a 2 niveles) para diversificar
        from collections import defaultdict
        buckets = defaultdict(list)  # coarse_cat -> [(aporte, es_pref, item)]
        mejor_bucket = {}            # coarse_cat -> mejor aporte real (antes de barajar)
        prio_bucket = {}             # coarse_cat -> puesto en el orden del post
        for a in pool:
            sized = self._size_food(a, hueco_pieza)
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
            mejor_bucket[coarse] = max(mejor_bucket.get(coarse, 0), macros[driver])
            prio_bucket[coarse] = min(prio_bucket.get(coarse, 999), prioridad_post(a))
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
        objetivo_pieza = max(float(hueco_pieza.get(driver, 0) or 0), 0)
        for b in buckets:
            # El que MEJOR se acerca a lo que le toca poner a una pieza, no el que más
            # pone: con «más es mejor» la lista la encabezaban siempre los concentrados,
            # que es de lo que venía la queja. Sin reparto por piezas (peri, o base sin
            # minar) `objetivo_pieza` es el hueco entero y esto se comporta como antes.
            buckets[b].sort(key=lambda x: abs(x[0] - objetivo_pieza) if objetivo_pieza else -x[0])
            # Barajar para dar variedad, pero solo entre los que resuelven parecido: si en
            # el mismo tipo hay un aislado que pone 45 g de proteína y otro que pone 3, el
            # azar no puede sacar el de 3 ("5 g de caseína" no es una sugerencia).
            mejor = buckets[b][0][0]
            # PRIMERO SE FILTRA POR ENCAJE, Y LUEGO MANDA EL USO. Sin cortar por cercanía
            # antes de tiempo: la «Pechuga de pollo» genérica se queda a 0,5 g de la cuota
            # y hay docenas de variantes que la clavan, así que cualquier corte previo la
            # dejaba fuera y el almuerzo lo acababa representando una «pechuga ya cocinada»
            # que casi nadie pone. Son 6.637 comidas de Jesús con la genérica frente a un
            # puñado con las otras: el desempate no puede decidirlo medio gramo.
            if objetivo_pieza:
                margen = abs(mejor - objetivo_pieza) + objetivo_pieza * 0.4
                head = [x for x in buckets[b] if abs(x[0] - objetivo_pieza) <= margen]
            else:
                head = [x for x in buckets[b] if x[0] >= mejor * 0.6]
            head = head or buckets[b][:1]
            random.shuffle(head)
            # Y ENTRE LOS QUE ENCAJAN, LO QUE JESUS PONE A ESA HORA (13-08-2026).
            #
            # Encajar en la cuota no basta: en produccion, para una merienda salian mero,
            # langostino y huevas de caballa, y para un desayuno estofado de pavo y lomo
            # marinado. Todos ponen sus 19 g de proteina; ninguno se merienda. Francisco:
            # «no tiene criterio de que se puede comer en cada comida».
            #
            # El dato ya estaba guardado y no se usaba aqui: cuantas VECES se ha puesto ese
            # alimento en ese momento (`moment_profiles`). No es la coherencia -- que es un
            # ratio y empata a todo lo que «pega» --, es el uso en bruto, que es el que
            # distingue las claras (miles de desayunos) de un lomo marinado. Se ordena por
            # tramos logaritmicos para que el barajado siga dando variedad entre los que se
            # usan parecido. Es el mismo criterio que ya ordena el chat.
            if perfil_uso and momento_actual:
                def _tramo_uso(x):
                    f = por_id.get(x[2]["alimento_id"])
                    if not f:
                        return 0
                    usos = perfil_uso.usos(f, momento_actual)
                    return min(int(math.log2(usos)) + 1, 15) if usos > 0 else 0
                # Los más usados delante y, entre los que se usan parecido, el que mejor
                # encaja. El barajado de arriba sigue decidiendo entre iguales.
                head.sort(key=lambda x: (-_tramo_uso(x), abs(x[0] - objetivo_pieza)))
            head = head[:12]
            buckets[b] = ([x for x in head if x[2]["alimento_id"] not in seen]
                          + [x for x in head if x[2]["alimento_id"] in seen])

        # Orden de tipos: los que tienen alimentos preferidos primero, luego por mejor aporte
        # El ORDEN DE LOS TIPOS también mira lo que se come a esa hora, no solo lo que
        # encaja: ordenar por uso dentro de cada familia no sirve de nada si la primera
        # familia que sale es la del jamón ibérico. Cada tipo se representa por su
        # candidato más usado, que es el primero desde el sort de arriba.
        def _uso_del_tipo(b):
            if not (perfil_uso and momento_actual):
                return 0
            f = por_id.get(buckets[b][0][2]["alimento_id"])
            if not f:
                return 0
            usos = perfil_uso.usos(f, momento_actual)
            return min(int(math.log2(usos)) + 1, 15) if usos > 0 else 0

        cat_order = sorted(
            buckets.keys(),
            key=lambda b: (0 if any(p for _, p, _ in buckets[b]) else 1,
                           -_uso_del_tipo(b),
                           abs(buckets[b][0][0] - objetivo_pieza) if objetivo_pieza
                           else -buckets[b][0][0])
        )
        # En el POST el orden lo marca el método, no el que más macro lleve: primero la
        # proteína rápida y el hidrato de asimilación rápida (crema de arroz, cereales,
        # dextrosa, fruta) y el pan al final (CATS_POST_PRIORIDAD, del propio Calma).
        # La prioridad solo decide entre los tipos que de verdad cubren lo que falta: un
        # aislado con 3 g de hidrato no puede ir primero cuando lo que faltan son hidratos.
        if key == "Post":
            tope = min(max(mejor_bucket.values(), default=0), max(restante[driver], 0))
            cat_order.sort(key=lambda b: (
                0 if any(p for _, p, _ in buckets[b]) else 1,
                0 if mejor_bucket.get(b, 0) >= tope * 0.5 else 1,
                prio_bucket.get(b, 999),
                -mejor_bucket.get(b, 0),
            ))

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
            #
            # Con las cantidades repartidas por piezas eso pasa casi siempre, y a propósito:
            # son piezas de una comida, no sustitutivos. Así que el aviso cambia de tono en
            # vez de sonar a que el catálogo se queda corto.
            mejor = max((s["macros"].get(driver, 0) for s in chosen), default=0)
            if mejor < restante[driver] - 4:
                reparte = objetivo_pieza and objetivo_pieza < restante[driver] - 4
                message = (
                    f"Van pensadas para combinarse: cada una pone una parte de los "
                    f"{restante[driver]} g de {MACRO_LBL[driver]} que faltan, así que coge "
                    f"un par y completamos."
                    if reparte else
                    f"Ninguna cubre sola los {restante[driver]} g de {MACRO_LBL[driver]} "
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
            # LA CANTIDAD, FUERA DEL NOMBRE. Al modelo se le pide que la mande aparte, y a
            # veces no lo hace: manda nombre="500 ml de leche entera". Ese texto entero se
            # va a la busqueda semantica, y los numeros y las unidades arrastran el vector:
            # medido, «leche entera» encuentra Leche entera la primera, y «500 ml de leche
            # entera» devuelve **leche de almendras** la primera. El cliente pedia leche y
            # se le apuntaba otra cosa (caso J10 del banco).
            #
            # Se quita en codigo y no pidiendoselo mejor al prompt: es gramatica, no
            # vocabulario, asi que no choca con la regla de no meter comida en el prompt.
            nombre, cant, unidad = NutritionChatbot._sacar_cantidad(nombre, cant, unidad)
            items.append({"nombre": nombre, "cantidad": cant, "unidad": unidad,
                          "sumar": bool(f.get("sumar")),
                          "busqueda": busq or None})
        return items

    # «300 g de arroz», «2 huevos», «500 ml de leche»: numero, unidad opcional y «de».
    _CANTIDAD_DELANTE = re.compile(
        r"^\s*(\d+(?:[.,]\d+)?)\s*"
        r"(kg|kgs|kilos?|gramos?|grs?|g|mililitros?|mls?|ml|litros?|l|unidades?|uds?|ud)?"
        r"\s*(?:de\s+)?(?=\S)", re.IGNORECASE)

    @staticmethod
    def _sacar_cantidad(nombre: str, cant, unidad):
        """Separa la cantidad que venga pegada al nombre. Devuelve (nombre, cantidad, unidad).

        Solo actua si el nombre EMPIEZA por un numero y queda texto detras: «2 huevos» si,
        «leche entera 3,8% MG» no. Y no pisa la cantidad que ya venga puesta aparte.

        Los mililitros cuentan como gramos. Para la leche eso son 515 g de verdad frente a
        500 (un 3%, 0,45 g de proteina en medio litro), y para todo lo demas que se bebe la
        densidad es practicamente 1. Pendiente de que Jesus diga si le vale.
        """
        m = NutritionChatbot._CANTIDAD_DELANTE.match(nombre or "")
        if not m:
            return nombre, cant, unidad
        resto = nombre[m.end():].strip()
        # Lo que queda tiene que ser un alimento. Con «500 g» a secas, la unidad se queda
        # sin consumir y el alimento pasaria a llamarse «g».
        if not resto or resto.lower() in _SOLO_UNIDAD:
            return nombre, cant, unidad
        if cant is not None:
            return resto, cant, unidad          # la cantidad buena ya venia aparte
        try:
            n = float(m.group(1).replace(",", "."))
        except ValueError:
            return nombre, cant, unidad
        u = (m.group(2) or "").lower()
        if u.startswith(("kg", "kilo")):
            return resto, n * 1000, "g"
        if u.startswith(("litro", "l")):
            return resto, n * 1000, "g"
        if u.startswith(("g", "gr", "gramo", "ml", "mililitro")):
            return resto, n, "g"
        if u.startswith(("ud", "unidad")):
            return resto, n, "ud"
        # Sin unidad («2 huevos») es un conteo de piezas: que lo resuelva el motor.
        return resto, n, "ud"

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
