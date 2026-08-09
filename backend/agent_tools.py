"""Las herramientas del agente de nutrición (F1 del plan del 06-08).

Ocho trabajos completos, deterministas, sobre el motor de siempre (calma_suggest /
meal_builder / calculator) y la sesión del chatbot. El modelo que las llame decide QUÉ
hacer; los gramos, los macros y los filtros los pone este código. Ninguna herramienta
lee el texto libre del chat: lo que no venga en sus parámetros no existe.

    tools = await AgentTools.crear(bot)
    await tools.buscar_alimentos("batido", para_macro="P", generico=True)
    await tools.componer_menu(incluir_ids=[...], estilo="ligera")
    await tools.revisar_borrador("b1") -> problemas accionables
    await tools.aplicar_borrador("b1") -> la comida, montada

Los borradores de menú viven en el estado de la sesión (bot.state["borradores"]) y NO
entran en la comida hasta `aplicar_borrador`, que revisa antes de volcar (guardarraíl 2
del plan: ningún menú se enseña ni se aplica sin pasar por el validador).

Devuelven diccionarios cortos y en lenguaje de personas (nombre, qué cuenta, por qué no
cabe), pensados para gastar pocos tokens y enseñar cuando fallan: "no hay genéricos que
cubran 39 g de proteína; el más cercano cubre 22" en vez de una lista vacía.
"""
import re
from typing import Dict, List, Optional

from calculator import (
    cat_in_list,
    es_sugerible,
    filtrar_por_tipo_comida,
    get_food_config,
)
from calma_engine import parse_categories
from food_semantic import BusquedaSemantica, CorrectorErratas
from meal_moment import momento_de_comida, describe_comida, PERI
from moment_profile import PerfilMomento, cat2_de

# Umbral de poda por momento: mismo criterio que el sugeridor (F0.5) y el banco de casos.
COHERENCIA_MINIMA = 0.25
# Un borrador con más desvío total que esto no puede aplicarse sin arreglo.
MARGEN_BORRADOR = 12.0

_ROL_A_MACRO = {"proteina": "P", "hidrato": "H", "grasa": "G"}
_MACRO_LBL = {"P": "proteína", "H": "hidratos", "G": "grasa"}


class AgentTools:
    """Las herramientas, atadas a una sesión (bot) y a las cachés compartidas."""

    # Cachés de proceso: mismas para todas las sesiones, como _VOCAB_CATALOGO.
    _SEMANTICA = None
    _CORRECTOR = None
    _FOODS = None          # id -> doc del catálogo

    _COMPANYIA = None      # qué va con qué, aprendido de las dietas

    def __init__(self, bot, semantica, corrector, perfil, foods: Dict[int, dict],
                 companyia=None):
        self.bot = bot
        self.db = bot.db
        self.semantica = semantica
        self.corrector = corrector
        self.perfil = perfil
        self.foods = foods
        self.companyia = companyia

    @classmethod
    async def crear(cls, bot) -> "AgentTools":
        if cls._FOODS is None:
            cls._FOODS = {int(f["id"]): f async for f in bot.db.foods.find({}, {"_id": 0})}
        if cls._SEMANTICA is None:
            try:
                cls._SEMANTICA = await BusquedaSemantica.cargar(bot.db)
            except RuntimeError:
                cls._SEMANTICA = False   # sin embeddings generados: búsqueda solo léxica
        if cls._CORRECTOR is None:
            cls._CORRECTOR = await CorrectorErratas.cargar(bot.db)
        if cls._COMPANYIA is None:
            from company_profile import PerfilCompanyia
            perfil_c = await PerfilCompanyia.cargar(bot.db)
            # Sin la colección generada (entorno nuevo) se sigue como siempre: el perfil
            # de compañía afina, no es imprescindible para montar una comida.
            cls._COMPANYIA = perfil_c if perfil_c.comidas else False
        perfil = await bot._perfil_momento()
        return cls(bot, cls._SEMANTICA or None, cls._CORRECTOR, perfil, cls._FOODS,
                   cls._COMPANYIA or None)

    # ------------------------------------------------------------ contexto común
    def _momento_actual(self) -> str:
        return momento_de_comida(
            self.bot.current_meal_key(),
            self.bot.state.get("num_comidas") or 4,
            self.bot.state.get("single_meal", False),
        )

    def _universo(self) -> List[dict]:
        """El catálogo que aplica a la comida actual (el peri tiene el suyo)."""
        key = self.bot.current_meal_key()
        todos = list(self.foods.values())
        if key in ("Intra", "Post"):
            return filtrar_por_tipo_comida(todos, "intra" if key == "Intra" else "post")
        return todos

    def _es_evitado(self, food: dict) -> Optional[str]:
        """Evitados del perfil (categorías y palabras) + restricciones de la sesión."""
        from routes.calculator import AVOIDABLE_PREFIXES
        nombre = (food.get("nombre") or "").lower()
        for kw in self.bot.state.get("avoided_keywords", []):
            if kw in nombre:
                return f"evitado del perfil ({kw})"
        prefijos = set()
        for cid in self.bot.state.get("avoided_categories", []):
            prefijos.update(AVOIDABLE_PREFIXES.get(cid, []))
        if prefijos:
            for c in parse_categories(food.get("categorias")):
                for p in prefijos:
                    if c == p or c.startswith(p + "."):
                        return "categoría evitada del perfil"
        motivo = self.bot._choca_con_restriccion(food)
        if motivo:
            return motivo
        return None

    def _etiquetas_de(self, food: dict) -> set:
        return {t for t in parse_categories(food.get("categorias")) if t and not t[0].isdigit()}

    def _item_de(self, food: dict, cantidad_g: float, macros: dict) -> dict:
        config = get_food_config(food)
        return {
            "id": int(food["id"]),
            "nombre": food.get("nombre"),
            "es_marca": bool(food.get("url")),
            "cantidad_g": round(cantidad_g, 1),
            "cantidad_display": self.bot._format_cantidad(cantidad_g, food, config),
            "macros": {m: round(float(macros.get(m, 0) or 0), 1) for m in ("P", "H", "G")},
            "categorias": food.get("categorias"),   # para el emoji de la tarjeta
            # Cómo se mide ESTE alimento. Sin decirlo, el asistente lo suponía: a «ponme 3
            # claras» les puso 300 g dando por hecho que una clara son 100 (son unos 33), y
            # con eso una comida de 47 g de proteína se iba al triple.
            "medida": (f"unidades de {int(config['peso_unidad'])} g"
                       if config.get("por_unidad") and config.get("peso_unidad")
                       else "gramos (NO tiene unidades)"),
        }

    # ============================================================ 1. buscar_alimentos
    async def buscar_alimentos(self, texto: str = "", para_macro: str = None,
                               generico: bool = None, marca: str = None,
                               etiquetas: List[str] = None,
                               coherente_con_momento: bool = True,
                               limite: int = 8,
                               heredar_estilo: bool = True,
                               acompanando_a: List[dict] = None) -> dict:
        """Busca en el catálogo con el texto TAL CUAL lo dijo el cliente (la traducción
        coloquial→catálogo es semántica, no una tabla). Sin texto, ordena por lo que más
        aporta al macro pedido (o al que más falta). Devuelve cada alimento ya
        dimensionado a lo que cabe en la comida actual."""
        limite = max(1, min(int(limite or 8), 15))
        restante = self.bot.get_remaining_macros()
        momento = self._momento_actual()
        universo = {int(f["id"]): f for f in self._universo()}

        # --- candidatos en orden de relevancia
        orden: List[int] = []
        texto = (texto or "").strip()
        # Herencia de la petición: con un menú del cliente abierto ("batido con
        # fruta"), una búsqueda SIN texto hereda ese estilo. Sin esto, "sugiéreme otra
        # proteína" a secas iba por aporte puro y ofrecía panceta para un batido.
        # `heredar_estilo=False` la apaga: la usa el compositor cuando el estilo ya no
        # dio candidatos y necesita el respaldo por aporte puro (sin esa salida, su
        # segundo intento heredaba el MISMO estilo que acababa de fallar y el menú se
        # quedaba corto de un macro sin remedio).
        if not texto and heredar_estilo:
            abiertos = list((self.bot.state.get("borradores") or {}).values())
            if abiertos:
                texto = (abiertos[-1].get("filtros", {}).get("estilo") or "").strip()
        # Los que casan con el nombre de lo pedido. Se guardan aparte porque tienen otro
        # trato: no es lo mismo que el cliente diga «lechuga» -- y exista una Lechuga --
        # que pedir «algo verde» y que el sistema proponga lo que le parezca.
        pedidos_por_nombre: set = set()
        texto_buscado = texto
        if texto:
            corregido = self.corrector.corregir(texto)
            # Lo que de verdad se ha buscado, ya sin erratas ("wevos" -> "huevos"): es con
            # esto con lo que hay que comparar los resultados más abajo, no con lo tecleado.
            texto_buscado = corregido
            # Léxico primero: si pidió un alimento por su nombre ("pechuga de pollo"),
            # eso gana a cualquier vecindad semántica.
            lex = await self.bot.search_foods(corregido, limit=10, _remap=False)
            pedidos_por_nombre = {int(a["id"]) for a in lex if int(a["id"]) in universo}
            orden.extend(int(a["id"]) for a in lex if int(a["id"]) in universo)
            if self.semantica:
                sem = await self.semantica.buscar(corregido, limite=80,
                                                  solo_ids=set(universo))
                orden.extend(h["id"] for h in sem if h["id"] not in set(orden))
        else:
            driver = para_macro if para_macro in ("P", "H", "G") else \
                max(("P", "H", "G"), key=lambda m: restante[m])
            from meal_builder import get_effective_macros_per_100g
            orden = sorted(universo,
                           key=lambda i: -get_effective_macros_per_100g(universo[i]).get(driver, 0))
            # Sin texto no hay una petición concreta que respetar: barajar la cabeza da
            # variedad entre sesiones (mismo criterio que el sugeridor de siempre).
            import random
            cabeza, resto = orden[:10], orden[10:]
            random.shuffle(cabeza)
            orden = cabeza + resto

        # --- filtros duros (datos del catálogo, nunca juicios)
        marca_norm = self.bot._norm_text(marca) if marca else None
        etiquetas = {e.upper() for e in (etiquetas or [])}
        vetados_momento = vetados_solos = 0
        items, no_caben = [], []
        # Lo que ya hay en el plato: decide si un acompañamiento tiene a quién acompañar.
        # `acompanando_a` lo pasa quien está MONTANDO un menú, donde el plato todavía está
        # vacío pero las piezas ya están elegidas; sin eso, un menú compuesto de cero nunca
        # podría llevar mermelada ni miel.
        ya_en_la_comida = list(acompanando_a or []) + [
            self.foods[int(f["alimento"]["id"])]
            for f in (self.bot.state["comidas_completadas"]
                      .get(self.bot.current_meal_key()) or {}).get("alimentos", [])
            if (f.get("alimento") or {}).get("id") is not None
            and int(f["alimento"]["id"]) in self.foods]
        for aid in orden:
            food = universo.get(aid)
            if not food:
                continue
            if not es_sugerible(food) and not self._acompana_a_algo(food, ya_en_la_comida):
                vetados_solos += 1
                continue
            if generico is True and food.get("url"):
                continue
            if generico is False and not food.get("url"):
                continue
            if marca_norm and marca_norm not in self.bot._norm_text(food.get("nombre", "")):
                continue
            if etiquetas and not etiquetas <= self._etiquetas_de(food):
                continue
            if self._es_evitado(food):
                continue
            # La coherencia con el momento no descarta lo que se ha pedido POR SU NOMBRE.
            #
            # Está para no proponer callos de desayuno por iniciativa propia, no para
            # llevarle la contraria al cliente. Pedir «lechuga» en la Comida 1 devolvía
            # ensaladilla, cebolla frita, puerro y calabaza -- la Lechuga existe (id 363)
            # y el veto la tiraba -- y encima en silencio, porque el aviso de «vetados
            # por atípicos» solo sale cuando no queda NINGÚN resultado, y vecinos había.
            # El cliente acababa con calabaza sin que nadie le explicara nada.
            if coherente_con_momento and self.perfil and momento != PERI \
                    and aid not in pedidos_por_nombre \
                    and self.perfil.coherencia(food, momento) < COHERENCIA_MINIMA:
                vetados_momento += 1
                continue
            sized = self.bot._size_food(food, restante)
            if not sized:
                if len(no_caben) < 3:
                    no_caben.append({"id": aid, "nombre": food.get("nombre"),
                                     "por_que_no": self.bot._razon_no_cabe(food, restante)})
                continue
            cantidad_g, macros = sized
            # `para_macro` ORDENA, pero solo descarta cuando no hay texto.
            #
            # Con texto hay una petición concreta del cliente, y esa manda. Si pide
            # lechuga y el agente busca `texto="lechuga", para_macro="H"`, la lechuga
            # no aporta hidratos y esta línea la tiraba: la búsqueda devolvía sus
            # vecinos semánticos -- calabaza, puerro -- y el cliente acababa con
            # calabaza sin que nadie le dijera nada. Pasa con todo lo que aporta poco o
            # nada: lechuga, pepino, apio, café, especias, agua.
            #
            # Sin texto sí filtra: ahí la petición ES el macro («dame una proteína para
            # completar»), y ofrecer algo que no aporta nada no tendría sentido.
            if texto:
                pass
            elif para_macro in ("P", "H", "G") and macros.get(para_macro, 0) <= 0:
                continue
            items.append(self._item_de(food, cantidad_g, macros))
            if len(items) >= limite:
                break

        out = {"items": items,
               "comida": describe_comida(self.bot.current_meal_key(),
                                         self.bot.state.get("num_comidas") or 4,
                                         self.bot.state.get("single_meal", False),
                                         self.bot.meal_label(self.bot.current_meal_key())),
               "falta": {m: restante[m] for m in ("P", "H", "G")}}
        # Si NINGÚN resultado va de lo que ha pedido el cliente, no se devuelven items.
        #
        # Ni la sal, ni la pimienta, ni el té solo están en el catálogo de Jesús. Devolver
        # «lo más parecido» hacía que a quien pedía sal le salieran pistachos y a quien
        # pedía pimienta, fiambre de pavo -- y no en una lista para elegir, sino METIDO en
        # la comida. Se probó primero a avisar por texto ("no lo añadas, que lo decida
        # él"); el asistente lo metía igual y lo contaba después, que es exactamente lo que
        # no puede pasar: el aviso se lee y se olvida, el alimento se queda en la dieta.
        #
        # Así que no es un aviso, es que no hay nada que añadir. Los nombres viajan en el
        # texto para que pueda enseñárselos y ofrecerle elegir; ninguno trae id.
        #
        # Solo cuando lo pedido es UNA palabra, que es donde estaba el hueco: con varias ya
        # actúa la cobertura de search_foods, y aquí daría falsos positivos ("pechuga de
        # pollo" no es una palabra de ningún nombre).
        #
        # Y solo cuando NO se ha vetado nada por soledad: si lo pedido son mermeladas y se
        # han apartado 18 por no tener a qué acompañar, la lista se queda con los vecinos
        # semánticos (melón, zumos) y concluir de ahí que «no hay ninguna mermelada» es
        # mentira. Los dos arreglos son de la misma tarde y este choque salió en la app:
        # el asistente respondió «ahora mismo en el catálogo no tengo ninguna mermelada».
        sig = [w for w in self.bot._norm_text(texto_buscado or "").split() if len(w) > 1]
        if len(sig) == 1 and items and not vetados_solos:
            if not any(self.bot._en_nucleo(sig[0], i.get("nombre", "")) for i in items):
                out["items"] = []
                out["sin_resultados_porque"] = [
                    f"NO hay ningún alimento que sea '{texto}' en el catálogo. Lo más "
                    f"parecido que aparece, y solo lleva ese nombre dentro, es: "
                    + "; ".join(i.get("nombre", "") for i in items[:4])
                    + f". Dile que no tienes '{texto}', enséñale esos y que elija él si "
                      f"quiere alguno."]
                return out
        # Lo apartado por soledad se cuenta SIEMPRE, haya items o no: es la diferencia
        # entre «no lo tengo» y «no te lo pongo suelto».
        if vetados_solos and any(self.bot._en_nucleo(w, f.get("nombre", ""))
                                 for w in sig
                                 for f in self.foods.values()
                                 if not es_sugerible(f)):
            out["ojo"] = (
                f"'{texto}' SÍ está en el catálogo ({vetados_solos} fichas), pero es un "
                f"acompañamiento y no se ofrece suelto: nadie desayuna un bote de "
                f"mermelada. NO digas que no lo tienes. Monta antes la base de la comida "
                f"y vuelve a pedirlo, o dile sobre qué se lo puedes poner.")
        if not items:
            # El error enseña: qué se probó y por qué no salió nada.
            notas = []
            if no_caben:
                notas.append("hay candidatos pero no caben: "
                             + "; ".join(f"{c['nombre']} ({c['por_que_no']})" for c in no_caben))
            if vetados_momento:
                notas.append(f"{vetados_momento} descartados por atípicos para {momento} "
                             "(repite con coherente_con_momento=false si lo quiere igualmente)")
            # SÍ están en el catálogo: no se ofrecen solos. Sin esta nota el asistente lo
            # contaba como que no existen -- «ahora mismo en el catálogo no tengo ninguna
            # mermelada» con 18 mermeladas dentro --, que es peor que el veto original.
            if vetados_solos:
                notas.append(
                    f"OJO: {vetados_solos} sí existen en el catálogo, pero son "
                    f"acompañamientos y no se proponen sueltos (nadie desayuna un bote de "
                    f"mermelada). NO digas que no los tienes: dile que se los pones sobre "
                    f"algo, y monta primero la base de la comida.")
            if not notas:
                notas.append("nada en el catálogo pasa esos filtros; prueba con otro texto "
                             "o quita algún filtro")
            out["sin_resultados_porque"] = notas
        return out

    # Con quién tiene que casar un acompañamiento para poder ofrecerlo: elevación por
    # encima de 1.0 (en las dietas reales SÍ se ponen juntos) Y un mínimo de veces que haya
    # pasado de verdad.
    #
    # Las dos condiciones hacen falta. Con la elevación sola entraba el 89 % de lo vetado
    # en cuanto hubiera cualquier cosa en el plato -- el azúcar moreno colándose en las
    # tres comidas que se probaron --, porque con pocos usos una coincidencia suelta ya da
    # una elevación alta. Exigiendo además cinco coincidencias reales, baja al 14 %.
    COMPANYIA_PARA_ACOMPANAR = 1.0
    VECES_PARA_ACOMPANAR = 5

    def _acompana_a_algo(self, food: dict, presentes: List[dict]) -> bool:
        """¿Este alimento, que no se propone suelto, acompaña a algo que ya hay en el plato?

        La regla de «no sugerible» vetaba CATEGORÍAS enteras: mermeladas, cacao y azúcares,
        salsas, harinas. Francisco, 08-08: *«esta regla está mal, porque no podría ofrecer
        mermelada? o cacao? necesita ser más específica»*. Y el dato le da la razón, en las
        147.820 comidas reales de Jesús:

            mermeladas       1.230 usos       0 veces solas
            cacao y azúcares 3.136 usos       1 vez sola
            salsas           2.342 usos       4 veces solas

        No es que no se usen: es que **nunca son el plato**. La miel va con el pan, la
        mermelada con las claras, el cacao con los copos de avena. Así que el veto deja de
        ser por categoría y pasa a ser por soledad: se puede ofrecer lo que acompaña a algo
        que ya está, y no se ofrece cuando no hay a qué acompañar.
        """
        if not self.companyia or not presentes:
            return False
        for otro in presentes:
            e = self.companyia.elevacion(food, otro)
            if e is not None and e >= self.COMPANYIA_PARA_ACOMPANAR \
                    and self.companyia.coincidencias(food, otro) >= self.VECES_PARA_ACOMPANAR:
                return True
        return False

    def _semilla_variedad(self) -> int:
        """Con qué se baraja: estable por CLIENTE, DÍA y COMIDA.

        Ni fija ni al azar puro. Fija daba lo que Francisco vio el 08-08 -- todos los
        clientes con los mismos macros recibiendo exactamente las mismas tres recetas --;
        al azar puro cambiaría las opciones cada vez que se recarga la página, y el
        cliente no entendería nada. Así el mismo cliente ve lo mismo mientras esté en esa
        comida, y mañana o el de al lado ven otra cosa."""
        st = self.bot.state
        partes = (str(self.bot.session_id or ""), str(st.get("fecha_objetivo") or ""),
                  self.bot.current_meal_key())
        return abs(hash("|".join(partes))) % (2 ** 31)

    def _companyia_mala(self, items: List[dict], ids_exentos: set = None):
        """¿Hay en esta comida un par que en las dietas reales no se pone junto? Devuelve
        el motivo, o None si la comida es normal (o si no hay datos para juzgarla).

        Los alimentos que el cliente ha pedido por su nombre quedan fuera del juicio: si
        quiere yogur con atún, es su comida y no hay nada que discutir. Lo que se corrige
        es lo que el asistente propone POR SU CUENTA."""
        if not self.companyia:
            return None
        ids_exentos = ids_exentos or set()
        foods = [self.foods[i["id"]] for i in items
                 if i.get("id") in self.foods and i["id"] not in ids_exentos]
        if len(foods) < 2:
            return None
        malo = self.companyia.discordante(foods)
        if not malo:
            return None
        elev, a, b = malo
        return (f"un intento juntaba {a.get('nombre')} con {b.get('nombre')}, y en las "
                f"dietas reales casi no coinciden (elevación {elev:.2f})", elev)

    # ============================================================ 2. componer_menu
    async def componer_menu(self, incluir_ids: List[int] = None, estilo: str = "",
                            generico: bool = None, marca: str = None,
                            n: int = 3) -> dict:
        """Monta hasta `n` menús completos para la comida actual con el catálogo entero.
        `incluir_ids` son obligatorios (van en todas las opciones); `estilo` es el texto
        libre del cliente y guía la elección por semántica. El recetario (153 recetas de
        Jesús) entra como candidato cuando encaja; nunca limita.
        Deja cada opción como BORRADOR: enseñar sí, aplicar solo tras revisar."""
        from meal_builder import build_meal, get_effective_macros_per_100g, classify_food_role

        n = max(1, min(int(n or 3), 4))
        incluir_ids = [int(x) for x in (incluir_ids or []) if int(x) in self.foods]
        restante = self.bot.get_remaining_macros()
        momento = self._momento_actual()
        opciones: List[dict] = []

        # --- 1) Recetario: solo sin estilo/filtros que él no sabe respetar y fuera del peri
        if momento != PERI and not estilo and not incluir_ids and generico is None and not marca:
            try:
                from meal_templates import generar_opciones_menu
                from routes.calculator import AVOIDABLE_PREFIXES
                avoid = set()
                for cid in self.bot.state.get("avoided_categories", []):
                    avoid.update(AVOIDABLE_PREFIXES.get(cid, []))
                recetas = await generar_opciones_menu(
                    self.db, momento, restante,
                    avoided_prefixes=avoid,
                    avoided_keywords=self.bot.state.get("avoided_keywords", []),
                    max_opciones=n,
                    semilla=self._semilla_variedad())
            except Exception:
                recetas = []
            for r in recetas:
                items = []
                for it in r.get("alimentos", r.get("items", [])):
                    aid = it.get("alimento_id") or it.get("id")
                    food = self.foods.get(int(aid)) if aid else None
                    if not food:
                        items = []
                        break
                    items.append(self._item_de(food, float(it.get("cantidad", it.get("cantidad_g", 0)) or 0),
                                               it.get("macros", it.get("macros_efectivos", {}))))
                if items:
                    opciones.append({"items": items, "origen": "recetario",
                                     "nombre": r.get("nombre") or r.get("titulo"),
                                     "receta_url": r.get("fuente")})

        # --- 2) Composición propia hasta n, con proteínas distintas entre opciones
        roles_necesarios = [rol for rol, m in _ROL_A_MACRO.items() if restante[m] > 4]
        if not roles_necesarios:
            roles_necesarios = ["proteina"]
        fijos = []
        for aid in incluir_ids:
            food = self.foods[aid]
            rol = {"P": "proteina", "PH": "proteina", "PG": "proteina",
                   "H": "hidrato", "G": "grasa", "V": "verdura"}.get(
                classify_food_role(food, get_effective_macros_per_100g(food)), "proteina")
            fijos.append((rol, food))
        def _cat2_de_id(aid):
            cc = parse_categories(self.foods[aid].get("categorias"))
            return ".".join(cc[0].split(".")[:2]) if cc else "?"

        candidatos_por_rol: Dict[str, List[dict]] = {}
        import random
        for rol in roles_necesarios:
            if any(r == rol for r, _ in fijos):
                continue
            res = await self.buscar_alimentos(
                texto=estilo, para_macro=_ROL_A_MACRO[rol],
                generico=generico, marca=marca, limite=max(n + 6, 10))
            cands = res["items"]
            # Cabeza DIVERSA por subfamilia y barajada. El top semántico de un estilo
            # suele ser tres variantes del mismo alimento (tres quesos batidos para
            # "batido"): barajarlas daba "variedad" de pega y salía siempre el mismo de
            # base. Máximo uno por subfamilia en la cabeza; el resto, detrás.
            cabeza, cola, sub_vistas = [], [], set()
            for c in cands:
                sub = _cat2_de_id(c["id"]) if c["id"] in self.foods else "?"
                if sub not in sub_vistas and len(cabeza) < 4:
                    sub_vistas.add(sub)
                    cabeza.append(c)
                else:
                    cola.append(c)
            random.shuffle(cabeza)
            candidatos_por_rol[rol] = cabeza + cola

        # Subfamilias ya usadas EN CUALQUIER opción anterior (también las del recetario):
        # mientras haya alternativas, ninguna se repite entre opciones. Antes solo rotaba
        # la proteína y salían tres menús idénticos con la grasa cambiada (visto 07-08).
        usadas_entre_opciones = {_cat2_de_id(i["id"]) for o in opciones
                                 for i in o.get("items", []) if i.get("id") in self.foods}
        intento = 0
        descartes_bucle = None
        apartadas = []      # descartadas por compañía, por si no queda ninguna otra
        while len(opciones) < n and intento < n + 5:
            nombres, ids_opcion, repetida = [], [], False
            for rol, food in fijos:
                nombres.append(food.get("nombre"))
                ids_opcion.append(int(food["id"]))
            # Tipos ya presentes en la opción (subfamilia a 2 niveles): un menú no lleva
            # el mismo alimento dos veces ni dos del mismo tipo en roles distintos. Sin
            # esto, el queso batido (que tiene P e H) salía elegido para LOS DOS roles:
            # "queso batido 300 g + queso batido 300 g" no es una comida de nadie.
            tipos_opcion = {_cat2_de_id(i) for i in ids_opcion}

            for rol in roles_necesarios:
                if any(r == rol for r, _ in fijos):
                    continue
                cands = candidatos_por_rol.get(rol) or []
                # Todos los roles rotan con el intento: da variedad entre opciones y
                # además sirve de REINTENTO cuando un intento se descartó por pasarse
                # (el coco rallado dispara la grasa: el siguiente suele cuadrar).
                idx = intento
                if not cands:
                    continue
                elegido = None
                for salto in range(len(cands)):
                    c = cands[min(idx + salto, len(cands) - 1)]
                    if c["id"] in ids_opcion or _cat2_de_id(c["id"]) in tipos_opcion:
                        continue
                    # Subfamilia ya enseñada en otra opción: se salta, salvo que sea el
                    # último recurso (mejor repetir que dejar el rol sin cubrir).
                    if _cat2_de_id(c["id"]) in usadas_entre_opciones \
                            and salto < len(cands) - 1:
                        continue
                    elegido = c
                    break
                if elegido is None:
                    continue
                usadas_entre_opciones.add(_cat2_de_id(elegido["id"]))
                tipos_opcion.add(_cat2_de_id(elegido["id"]))
                nombres.append(elegido["nombre"])
                ids_opcion.append(elegido["id"])
            intento += 1
            if not nombres:
                break
            resultado = await build_meal(self.db, nombres, restante,
                                         self.bot.search_foods, forzar=bool(incluir_ids))
            if not resultado.get("foods_added"):
                continue

            # Si tras el cuadre queda un macro claramente descubierto (la fruta sola no
            # llega a los hidratos de un desayuno de entreno), se añade UNA fuente
            # complementaria de ese macro y se recuadra. Primero respetando el estilo;
            # si el estilo no da candidatos, sin él: mejor un menú completo que uno
            # puramente fiel al estilo pero corto.
            # Y con un techo de piezas: el 84,5 % de las 147.820 comidas reales tienen 5
            # alimentos o menos, y aquí salían menús de 6 y de 7 (yogur, frambuesas,
            # almendras, pan, tomate, fiambre de pavo y atún, todo en el mismo desayuno).
            # El número lo dicen las dietas, no una constante escrita a mano.
            tope_piezas = self.companyia.tamano_habitual() if self.companyia else 5
            for _ in range(2):   # hasta DOS complementos: lácteo+fruta topan sus máximos
                if len(nombres) >= tope_piezas:
                    break
                rem = resultado.get("remaining") or {}
                peor = max(("P", "H", "G"), key=lambda m: float(rem.get(m, 0) or 0))
                if float(rem.get(peor, 0) or 0) <= 8:
                    break
                extra = None
                textos = [estilo] if estilo else []
                textos.append("")
                for txt in textos:
                    rx = await self.buscar_alimentos(
                        texto=txt, para_macro=peor, generico=generico, marca=marca,
                        limite=6, heredar_estilo=False,
                        # El complemento SÍ puede ser un acompañamiento (la mermelada de
                        # las tostadas), porque a estas alturas ya hay piezas a las que
                        # acompañar aunque el plato del cliente siga vacío.
                        acompanando_a=[self.foods[i] for i in ids_opcion if i in self.foods])
                    extra = next((i for i in rx["items"]
                                  if i["id"] not in ids_opcion
                                  and _cat2_de_id(i["id"]) not in tipos_opcion), None)
                    if extra:
                        break
                if not extra:
                    break
                resultado2 = await build_meal(self.db, nombres + [extra["nombre"]],
                                              restante, self.bot.search_foods,
                                              forzar=bool(incluir_ids))
                rem2 = resultado2.get("remaining") or {}
                if not resultado2.get("foods_added") or \
                        sum(max(float(v or 0), 0) for v in rem2.values()) >= \
                        sum(max(float(v or 0), 0) for v in rem.values()):
                    break
                resultado = resultado2
                nombres.append(extra["nombre"])
                ids_opcion.append(extra["id"])
                tipos_opcion.add(_cat2_de_id(extra["id"]))
                usadas_entre_opciones.add(_cat2_de_id(extra["id"]))
            items, ids_vistos = [], set()
            for f in resultado["foods_added"]:
                food = next((x for x in self.foods.values()
                             if x.get("nombre") == f.get("nombre")), None)
                if not food:
                    continue
                # build_meal resuelve por NOMBRE: dos peticiones distintas pueden acabar
                # en el MISMO alimento popular (se vio en real: el mismo plato tres
                # veces). Un menú no repite alimento: la repetición se tira.
                if int(food["id"]) in ids_vistos:
                    continue
                ids_vistos.add(int(food["id"]))
                items.append(self._item_de(food, float(f.get("cantidad", 0) or 0),
                                           f.get("macros", {})))
            if not items:
                continue
            # Lo que el cliente ha pedido POR SU NOMBRE tiene que estar en el plato.
            #
            # `incluir_ids` se llamaba «obligatorios» y no lo eran: se convertían a
            # nombres y era `build_meal` quien decidía qué entraba según lo que cabía,
            # sin devolver nunca qué se había quedado fuera. Pidiendo pollo, lechuga,
            # huevos y zumo salían tres opciones de «huevos + manzana», y el cliente no
            # tenía forma de saber por qué. Si falta algo pedido, el intento no vale y
            # se reintenta; lo que no se puede es enseñarlo como si estuviera.
            faltan_pedidos = [self.foods[i].get("nombre") for i in incluir_ids
                              if i not in ids_vistos]
            if faltan_pedidos:
                descartes_bucle = ("un intento se quedó sin lo que pediste: "
                                   + ", ".join(faltan_pedidos))
                continue
            firma = tuple(sorted(i["id"] for i in items))
            if any(tuple(sorted(x["id"] for x in o["items"])) == firma for o in opciones):
                continue
            # Exceso gordo DENTRO del bucle: descartar aquí deja vivo el reintento (la
            # siguiente vuelta rota proteína y grasa). Los obligatorios del cliente solo
            # eximen SU PROPIO exceso: que el cliente exigiera la fruta no da permiso a
            # que el relleno dispare la grasa (el coco de 32 g se coló por esta rendija).
            tot_i = {m: sum(i["macros"][m] for i in items) for m in ("P", "H", "G")}
            exceso_i = sum(max(tot_i[m] - restante[m], 0) for m in ("P", "H", "G"))
            ids_fijos = {int(f["id"]) for _, f in fijos}
            tot_fijos = {m: sum(i["macros"][m] for i in items if i["id"] in ids_fijos)
                         for m in ("P", "H", "G")}
            exceso_fijos = sum(max(tot_fijos[m] - restante[m], 0) for m in ("P", "H", "G"))
            if exceso_i > 2 * MARGEN_BORRADOR and exceso_fijos <= MARGEN_BORRADOR:
                peor_m = max(("P", "H", "G"), key=lambda m: tot_i[m] - restante[m])
                descartes_bucle = f"un intento se pasaba {tot_i[peor_m] - restante[peor_m]:.0f} g de {_MACRO_LBL[peor_m]}"
                continue
            # Combinaciones que nadie come. Cuadrar los macros era lo único que se miraba,
            # y salían cosas como yogur con atún, pollo con fiambre de pavo en el desayuno
            # o caseína con chocolate negro -- Francisco, 08-08: «esa combinación de
            # alimentos no tiene sentido». Qué va con qué no lo decide una lista escrita a
            # mano sino las 147.820 comidas reales de la base (ver company_profile).
            #
            # Lo que el cliente ha pedido por su nombre no se juzga: si quiere yogur con
            # atún, es su comida.
            discordante = self._companyia_mala(items, ids_fijos)
            if discordante:
                descartes_bucle = discordante[0]
                # Guardada, no tirada: si al final no queda NINGUNA opción, es mejor
                # ofrecer la menos mala con su aviso que dejar al cliente sin nada. Pasa
                # de verdad: pidiendo "tostadas" todo lo que cuadra son tres tostadas
                # distintas juntas, y las tres se descartaban.
                apartadas.append((discordante[1], {
                    "items": items, "origen": "compuesto", "nombre": None,
                    "receta_url": None, "aviso_companyia": discordante[0]}))
                continue
            opciones.append({"items": items, "origen": "compuesto", "nombre": None,
                             "receta_url": None})

        # Si el filtro de compañía se lo ha llevado TODO, se rescata lo menos malo con su
        # aviso: quedarse sin nada que ofrecer es peor que ofrecer una combinación rara y
        # decir que lo es.
        if not opciones and apartadas:
            apartadas.sort(key=lambda x: -x[0])
            opciones = [op for _, op in apartadas[:n]]

        # --- 3) A borrador, con totales, desvío y PUERTA DE CALIDAD del motor: un menú
        # que se va a lo loco del objetivo (49 g de grasa sobre 12 se vio en real) no
        # sale de aquí, diga lo que diga quien llama. Es la regla dura en código.
        borradores = self.bot.state.setdefault("borradores", {})
        # Número de opción DE CARA AL CLIENTE: sigue la cuenta de la comida actual y
        # nunca se reinicia dentro de ella. La tarjeta lo pinta y el asistente lo usa;
        # sin esto, "dame otra variante" enseñaba "Opción 1" mientras el texto decía
        # "la opción 3" (cada uno numeraba por su lado).
        mk = self.bot.current_meal_key()
        numero = max((b.get("numero") or 0 for b in borradores.values()
                      if b.get("meal_key") == mk), default=0)
        salida, descartes = [], []
        for op in opciones[:n]:
            tot = {m: round(sum(i["macros"][m] for i in op["items"]), 1) for m in ("P", "H", "G")}
            desvio = {m: round(tot[m] - restante[m], 1) for m in ("P", "H", "G")}
            # Solo bloquea el EXCESO gordo (49 g de grasa sobre 12 no es una comida, es
            # basura). El déficit pasa: es trabajo pendiente que el agente arregla con
            # editar_borrador o que el revisor señalará. Los obligatorios del cliente
            # eximen SU exceso, no el del relleno (misma regla que dentro del bucle).
            exceso = sum(max(v, 0) for v in desvio.values())
            ids_fijos = {int(f["id"]) for _, f in fijos}
            tot_fij = {m: sum(i["macros"][m] for i in op["items"] if i["id"] in ids_fijos)
                       for m in ("P", "H", "G")}
            exceso_fij = sum(max(tot_fij[m] - restante[m], 0) for m in ("P", "H", "G"))
            if exceso > 2 * MARGEN_BORRADOR and exceso_fij <= MARGEN_BORRADOR:
                peor_m = max(desvio, key=lambda m: desvio[m])
                descartes.append(f"una opción se pasaba {desvio[peor_m]:.0f} g de "
                                 f"{_MACRO_LBL[peor_m]} y se descartó")
                continue
            bid = f"b{len(borradores) + 1}"
            numero += 1
            borrador = {"id": bid, "numero": numero,
                        "items": op["items"], "origen": op["origen"],
                        "nombre": op["nombre"], "receta_url": op.get("receta_url"),
                        "macros_totales": tot, "objetivo": dict(restante), "desvio": desvio,
                        "filtros": {"generico": generico, "marca": marca, "estilo": estilo or None},
                        "momento": momento, "meal_key": self.bot.current_meal_key()}
            # Rescatada del filtro de compañía: se enseña, pero diciendo lo que es.
            if op.get("aviso_companyia"):
                borrador["avisos"] = [op["aviso_companyia"].replace("un intento", "esta opción")]
            borradores[bid] = borrador
            salida.append(borrador)
        if not salida:
            notas = descartes or []
            if descartes_bucle:
                notas.append(descartes_bucle)
            notas.append("no salió ningún menú que cuadre con esos filtros y lo que "
                         "falta; fija los imprescindibles con incluir_ids o móntalo "
                         "alimento a alimento")
            return {"borradores": [], "sin_resultados_porque": notas}
        return {"borradores": salida}

    # ============================================================ 3. revisar_borrador
    async def revisar_borrador(self, borrador_id: str) -> dict:
        """Auditoría determinista de un borrador: solo lo comprobable con datos.
        La fidelidad al estilo pedido es responsabilidad de quien llama."""
        b = (self.bot.state.get("borradores") or {}).get(borrador_id)
        if not b:
            return {"ok": False, "problemas": [{"tipo": "no_existe",
                                                "detalle": f"no hay borrador {borrador_id}"}]}
        problemas = []
        momento = b.get("momento") or self._momento_actual()
        for it in b["items"]:
            food = self.foods.get(it["id"])
            if not food:
                problemas.append({"item_id": it["id"], "tipo": "no_existe",
                                  "detalle": f"{it['nombre']} ya no está en el catálogo"})
                continue
            motivo = self._es_evitado(food)
            if motivo:
                problemas.append({"item_id": it["id"], "tipo": "restriccion",
                                  "detalle": f"{it['nombre']}: {motivo}"})
            if b.get("filtros", {}).get("generico") is True and food.get("url"):
                problemas.append({"item_id": it["id"], "tipo": "marca_no_pedida",
                                  "detalle": f"pidió genéricos y {it['nombre']} es de marca"})
            if self.perfil and momento != PERI \
                    and self.perfil.coherencia(food, momento) < COHERENCIA_MINIMA:
                problemas.append({"item_id": it["id"], "tipo": "momento_incoherente",
                                  "detalle": f"{it['nombre']} es atípico para {momento}"})
        firma = tuple(sorted(i["id"] for i in b["items"]))
        if list(firma) in (self.bot.state.get("menus_vistos") or []):
            problemas.append({"item_id": None, "tipo": "ya_ofrecido",
                              "detalle": "este menú ya se le ofreció antes"})
        exceso = sum(abs(v) for v in b["desvio"].values())
        if exceso > MARGEN_BORRADOR:
            peor = max(b["desvio"], key=lambda m: abs(b["desvio"][m]))
            problemas.append({"item_id": None, "tipo": "fuera_de_margen",
                              "detalle": f"se desvía {abs(b['desvio'][peor])} g de "
                                         f"{_MACRO_LBL[peor]} del objetivo"})

        sugerencias = []
        for p in problemas:
            if p.get("item_id") is None:
                continue
            it = next((x for x in b["items"] if x["id"] == p["item_id"]), None)
            if not it:
                continue
            food = self.foods.get(it["id"])
            rol = next((r for r, m in _ROL_A_MACRO.items()
                        if it["macros"].get(m, 0) == max(it["macros"].values())), "proteina")
            # Las alternativas respetan el PAPEL de la pieza (su macro) y la PETICIÓN
            # original del cliente (el estilo con que se compuso el menú), que es el
            # criterio de sustitución: nunca el parecido superficial.
            alt = await self.buscar_alimentos(
                texto=b.get("filtros", {}).get("estilo") or "",
                para_macro=_ROL_A_MACRO[rol],
                generico=b.get("filtros", {}).get("generico"), limite=3)
            alternativas = [a for a in alt["items"] if a["id"] != it["id"]][:2]
            if alternativas:
                sugerencias.append({"item_id": it["id"],
                                    "alternativas": [{"id": a["id"], "nombre": a["nombre"]}
                                                     for a in alternativas]})
        return {"ok": not problemas, "problemas": problemas,
                "sugerencias_de_cambio": sugerencias}

    # ============================================================ 3b. ofrecer_sustitutos
    async def ofrecer_sustitutos(self, borrador_id: str, item_id: int,
                                 texto: str = "", limite: int = 4) -> dict:
        """Ofrece reemplazos para UNA pieza de un menú y deja la sustitución ARMADA:
        cuando el cliente elija (por número o por nombre), el bucle hace el cambio en el
        borrador de forma determinista, sin que el modelo tenga que acordarse.

        Nació de un fallo real: el asistente ofrecía sustitutos con buscar_alimentos,
        el cliente elegía por nombre y la elección acababa como alimento suelto en la
        comida, con el menú tirado a la basura y un "te cambio solo el yogur" mentira.
        """
        b = (self.bot.state.get("borradores") or {}).get(borrador_id)
        if not b:
            return {"ok": False, "error": f"no hay borrador {borrador_id}"}
        it = next((x for x in b["items"] if int(x["id"]) == int(item_id)), None)
        if not it:
            return {"ok": False, "error": f"el borrador no tiene el alimento {item_id}; "
                                          f"sus items son " + ", ".join(
                                              f"{x['nombre']} (id {x['id']})" for x in b["items"])}
        rol_macro = max(("P", "H", "G"), key=lambda m: it["macros"].get(m, 0))
        en_menu = {int(x["id"]) for x in b["items"]}
        # Se pide MUY hondo a propósito: el top del ranking suele ser una sola
        # subfamilia (siete quesos batidos seguidos) y la diversificación de abajo
        # necesita donde elegir.
        res = await self.buscar_alimentos(
            texto=texto or (b.get("filtros", {}).get("estilo") or ""),
            para_macro=rol_macro,
            generico=b.get("filtros", {}).get("generico"),
            limite=max(limite * 3, 12))
        candidatas = [i for i in res["items"] if i["id"] not in en_menu]
        # "Cámbialo por otra cosa" no puede contestar con cuatro variantes de lo mismo:
        # fuera la subfamilia del saliente (al final, de relleno), y la lista se
        # diversifica: máximo una opción por subfamilia mientras haya donde elegir.
        cat_saliente = cat2_de(self.foods.get(int(item_id), {}))
        distintas = [i for i in candidatas
                     if cat2_de(self.foods.get(i["id"], {})) != cat_saliente]
        hermanas = [i for i in candidatas if i not in distintas]
        opciones, vistas = [], set()
        for i in distintas:
            c = cat2_de(self.foods.get(i["id"], {}))
            if c not in vistas:
                vistas.add(c)
                opciones.append(i)
        opciones += [i for i in distintas if i not in opciones] + hermanas
        opciones = opciones[:limite]
        if not opciones:
            return {"ok": False, "error": "no encontré sustitutos que encajen; prueba "
                                          "con otro texto o sin filtros"}
        self.bot.state["sustitucion_pendiente"] = {
            "borrador_id": borrador_id, "item_id": int(item_id),
            "item_nombre": it["nombre"],
            "opciones": [{"id": o["id"], "nombre": o["nombre"]} for o in opciones],
        }
        self.bot.state["last_options"] = []   # las listas viejas ya no aplican
        return {"ok": True, "sustituyendo": it["nombre"], "opciones": opciones,
                "nota": "el cliente elegirá por número o nombre y el cambio se hará solo; "
                        "no vuelvas a buscar ni añadas nada tú"}

    # ============================================================ 4. editar_borrador
    async def editar_borrador(self, borrador_id: str, operaciones: List[dict]) -> dict:
        """Cambia items de un borrador y RECUADRA el menú entero con el motor.
        Ops: {op:'sustituir', item_id, por_id} | {op:'quitar', item_id} |
             {op:'añadir', alimento_id}."""
        from meal_builder import build_meal

        borradores = self.bot.state.get("borradores") or {}
        b = borradores.get(borrador_id)
        if not b:
            return {"ok": False, "error": f"no hay borrador {borrador_id}"}
        ids = [i["id"] for i in b["items"]]
        for op in operaciones or []:
            tipo = (op.get("op") or "").strip().lower().replace("anadir", "añadir")
            if tipo == "quitar" and int(op.get("item_id", 0)) in ids:
                ids.remove(int(op["item_id"]))
            elif tipo == "sustituir":
                viejo, nuevo = int(op.get("item_id", 0)), int(op.get("por_id", 0))
                if viejo in ids and nuevo in self.foods:
                    ids[ids.index(viejo)] = nuevo
            elif tipo == "añadir":
                nuevo = int(op.get("alimento_id", 0))
                if nuevo in self.foods and nuevo not in ids:
                    ids.append(nuevo)
        if not ids:
            return {"ok": False, "error": "el borrador se quedaría vacío"}
        nombres = [self.foods[i]["nombre"] for i in ids]
        objetivo = b.get("objetivo") or self.bot.get_remaining_macros()
        resultado = await build_meal(self.db, nombres, objetivo, self.bot.search_foods, forzar=True)
        items = []
        for f in resultado.get("foods_added", []):
            food = next((x for x in self.foods.values() if x.get("nombre") == f.get("nombre")), None)
            if food:
                items.append(self._item_de(food, float(f.get("cantidad", 0) or 0), f.get("macros", {})))
        if not items:
            return {"ok": False, "error": "con ese cambio no sale ninguna combinación que cuadre"}
        tot = {m: round(sum(i["macros"][m] for i in items), 1) for m in ("P", "H", "G")}
        b.update({"items": items, "origen": "editado", "nombre": None, "receta_url": None,
                  "macros_totales": tot,
                  "desvio": {m: round(tot[m] - objetivo[m], 1) for m in ("P", "H", "G")}})
        return {"ok": True, "borrador": b}

    # ============================================================ 5. aplicar_borrador
    async def aplicar_borrador(self, borrador_id: str, forzar: bool = False) -> dict:
        """Vuelca un borrador a la comida actual. REVISA antes: con problemas no aplica
        (salvo forzar=True explícito tras contárselo al cliente)."""
        b = (self.bot.state.get("borradores") or {}).get(borrador_id)
        if not b:
            return {"ok": False, "error": f"no hay borrador {borrador_id}"}
        revision = await self.revisar_borrador(borrador_id)
        if not revision["ok"] and not forzar:
            return {"ok": False, "bloqueado_por": revision["problemas"],
                    "sugerencias_de_cambio": revision.get("sugerencias_de_cambio", [])}
        for it in b["items"]:
            await self.bot.add_food_by_id(it["id"], it["cantidad_g"])
        vistos = self.bot.state.setdefault("menus_vistos", [])
        firma = sorted(i["id"] for i in b["items"])
        if firma not in vistos:
            vistos.append(firma)
        return {"ok": True, "comida": self.ver_estado("comida")}

    # ============================================================ 6. editar_comida
    async def editar_comida(self, operaciones: List[dict]) -> dict:
        """Todas las mutaciones de la comida actual en una llamada, en orden.
        Ops: {op:'añadir', texto|alimento_id, cantidad?, unidad?}
             {op:'quitar', nombre|alimento_id}
             {op:'ajustar', nombre, a?|mas?|por?, unidad?}  (fijar / sumar / multiplicar)"""
        hechos, fallos = [], []
        for op in operaciones or []:
            tipo = (op.get("op") or "").strip().lower().replace("anadir", "añadir")
            try:
                if tipo == "añadir":
                    if op.get("alimento_id"):
                        r = await self.bot.add_food_by_id(int(op["alimento_id"]),
                                                          op.get("cantidad"))
                        ok = bool(r.get("foods_added"))
                    else:
                        r = await self.bot.add_foods([{"nombre": op.get("texto") or "",
                                                       "cantidad": op.get("cantidad"),
                                                       "unidad": op.get("unidad"),
                                                       "sumar": bool(op.get("sumar"))}])
                        ok = bool(r.get("foods_added"))
                        # El respaldo es para cuando NO SE ENCUENTRA el alimento; no para
                        # cuando se ha encontrado y el problema es la cantidad. Si no, el
                        # aviso se pierde y el motor dimensiona a su gusto: a «3 claras»
                        # les ponía 300 g y a «2 huevos», 1 ud. Justo lo que se quería
                        # evitar, y encima por la puerta de atrás.
                        problema_de_cantidad = any(
                            f.get("va_por_gramos") for f in (r.get("foods_not_found") or []))
                        if not ok and self.semantica and not problema_de_cantidad:
                            # El nombre pedido no existe tal cual en el catálogo
                            # ("<preparación> de <alimento>" con otro nombre comercial):
                            # la vecindad semántica encuentra lo que el léxico no.
                            cerca = await self.buscar_alimentos(op.get("texto") or "", limite=1)
                            if cerca["items"]:
                                # add_food_by_id trabaja en gramos: la cantidad solo
                                # se respeta si venía en g; en unidades, que dimensione.
                                en_g = op.get("cantidad") if op.get("unidad") == "g" else None
                                r = await self.bot.add_food_by_id(cerca["items"][0]["id"], en_g)
                                ok = bool(r.get("foods_added"))
                    (hechos if ok else fallos).append(
                        {"op": op, "detalle": (r.get("foods_added") or r.get("foods_not_found") or [{}])[0]})
                elif tipo == "quitar":
                    nombre = op.get("nombre") or str(op.get("alimento_id") or "")
                    q = self.bot.remove_food_by_name(nombre)
                    (hechos if q else fallos).append(
                        {"op": op, "detalle": q or f"no veo '{nombre}' en la comida"})
                elif tipo == "ajustar":
                    if op.get("por") is not None:
                        r = await self.bot.aplicar_multiplicador(float(op["por"]), op.get("nombre") or "")
                    else:
                        cantidad = op.get("a", op.get("mas"))
                        r = await self.bot.set_food_quantity(
                            op.get("nombre") or "", cantidad=float(cantidad),
                            unidad=op.get("unidad"), incrementar=op.get("mas") is not None)
                    (hechos if r.get("ok") else fallos).append({"op": op, "detalle": r})
                else:
                    fallos.append({"op": op, "detalle": f"operación desconocida '{tipo}'"})
            except Exception as e:
                fallos.append({"op": op, "detalle": f"{type(e).__name__}: {e}"})
        return {"ok": not fallos, "hechos": hechos, "fallos": fallos,
                "comida": self.ver_estado("comida")}

    # ============================================================ 7. estado / navegar / explicar / guardar
    def ver_estado(self, ambito: str = "comida") -> dict:
        """El estado en pocas líneas: lo que hay, lo que falta, dónde estamos."""
        bot = self.bot
        n = bot.state.get("num_comidas") or 4
        single = bot.state.get("single_meal", False)
        key = bot.current_meal_key()
        comida = bot.state["comidas_completadas"].get(key, {})
        actual = {
            "comida": describe_comida(key, n, single, bot.meal_label(key)),
            "objetivo": bot.get_current_meal_macros(),
            "falta": bot.get_remaining_macros(),
            "alimentos": [{"id": a.get("alimento_id"), "nombre": a.get("nombre"),
                           "cantidad": a.get("cantidad_display"),
                           "macros": a.get("macros")} for a in comida.get("alimentos", [])],
        }
        if ambito != "dia":
            return actual
        ov = bot.get_day_overview()
        return {"actual": actual, "tipo_dia": bot.state.get("tipo_dia"),
                "objetivo_dia": ov.get("objetivo"), "consumido": ov.get("consumido"),
                "falta_dia": ov.get("restante"),
                "comidas": [{"nombre": m.get("nombre"),
                             "momento": momento_de_comida(m.get("key", ""), n, single),
                             "estado": ("cuadrada" if m.get("cuadrado")
                                        else "vacía" if not m.get("tiene_alimentos")
                                        else "incompleta"),
                             "es_actual": m.get("es_actual", False)}
                            for m in ov.get("meals", [])]}

    def navegar(self, a) -> dict:
        """Ir a una comida ('2', 'post', 'intra', 'ultima', 'siguiente')."""
        ref = str(a).strip().lower()
        if ref == "siguiente":
            idx = min(self.bot.state["comida_actual"] + 1, len(self.bot.state["meal_order"]))
        else:
            ref = ref.replace("comida", "").strip()
            idx = self.bot.resolve_meal_ref(int(ref) if ref.isdigit() else ref)
        if idx and self.bot.go_to_meal(idx):
            return {"ok": True, "comida": self.ver_estado("comida")}
        return {"ok": False, "error": f"no encuentro la comida '{a}'; el día tiene "
                                      f"{len(self.bot.state['meal_order'])} comidas"}

    def guardar_comida(self) -> dict:
        """Guarda la comida actual y avanza a la siguiente pendiente. Guardar sin
        cuadrar se permite, pero se avisa (mismo criterio que /complete-meal); el
        volcado del día a la dieta sigue siendo la acción aparte de siempre."""
        rem = self.bot.get_remaining_macros()
        faltan = [f"{rem[m]} g de {_MACRO_LBL[m]}" for m in ("P", "H", "G") if rem.get(m, 0) > 4]
        pasan = [f"{abs(rem[m])} g de {_MACRO_LBL[m]}" for m in ("P", "H", "G") if rem.get(m, 0) < -4]
        r = self.bot.complete_current_meal()
        if r.get("vacia"):
            return {"ok": False, "error": r.get("error")}
        out = {"ok": True, "dia_completo": self.bot.state.get("step") == "complete",
               "comida": self.ver_estado("comida")}
        if faltan:
            out["aviso"] = "la comida quedó sin cuadrar: faltan " + " y ".join(faltan)
        if pasan:
            out["aviso"] = (out.get("aviso", "") + ("; " if out.get("aviso") else "")
                            + "se pasa " + " y ".join(pasan))
        return out

    async def explicar(self, alimento: str) -> dict:
        """Qué cuenta un alimento en CALMA y por qué (determinista, del motor)."""
        matches = await self.bot.search_foods(self.corrector.corregir(alimento),
                                              limit=1, _remap=False)
        if not matches:
            return {"ok": False, "error": f"no encuentro '{alimento}' en el catálogo"}
        food = matches[0]
        cuenta, brutos, cat, base = self.bot._que_cuenta(food)
        return {"ok": True, "nombre": food.get("nombre"), "categoria": cat,
                "macros_etiqueta": brutos, "base": base,
                "cuenta_en_calma": {_MACRO_LBL[m]: cuenta[m] for m in ("P", "H", "G")}}

    # ============================================================ 8. configurar_dia
    def configurar_dia(self, tipo_dia: str = None, num_comidas: int = None,
                       momento_entreno: int = None, opcion_peri: str = None,
                       single_meal: bool = None) -> dict:
        """Cambia la configuración del día a mitad de conversación ('mejor 3 comidas',
        'hoy descanso', 'en ayunas', 'sin peri'). Lo ya montado se respeta."""
        st = self.bot.state
        self.bot.configure_day(
            tipo_dia=tipo_dia or st.get("tipo_dia") or "entrenamiento",
            num_comidas=int(num_comidas or st.get("num_comidas") or 4),
            momento_entreno=int(momento_entreno if momento_entreno is not None
                                else st.get("momento_entreno", 1)),
            opcion_peri=opcion_peri or st.get("opcion_peri") or "intra_post",
            single_meal=bool(single_meal if single_meal is not None
                             else st.get("single_meal", False)),
        )
        out = {"ok": True, "dia": self.ver_estado("dia")}
        # Las comidas que el cambio se lleva por delante (intra y post al pasar a descanso)
        # no se borran: su contenido se traspasa. El agente TIENE que saberlo o se lo
        # inventa -- que es justo lo que pasó el 08-08: "lo del post lo tienes metido en
        # la Comida 2" cuando en realidad se había esfumado.
        reubicado = st.get("reubicado_al_reconfigurar") or []
        if reubicado:
            out["reubicado"] = reubicado
            out["avisa_al_usuario"] = (
                "Dile de dónde a dónde ha ido lo que tenía montado en las comidas que ya "
                "no existen, y que revise esas comidas porque los macros han cambiado.")
        return out

    # ========================================================= 9. cambiar_de_dia
    def cambiar_de_dia(self, fecha: str = None) -> dict:
        """Montar OTRA fecha. Quién decide que el cliente quiere cambiar de día es el
        agente, no un regex: hasta el 08-08 lo miraba el front con
        `/^(hoy|manana|pasado manana)\\b/` y "hoy es día de descanso" se leía como "vete al
        día de hoy", cambiaba de fecha y tiraba lo de descanso. El agente entiende que ahí
        hay dos peticiones y atiende las dos.

        Aquí solo se APUNTA la fecha; recargar la configuración de ese día desde Nutrición
        y volver a arrancar es cosa del front, que es quien la tiene."""
        import re
        from datetime import date
        if not fecha or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", (fecha or "").strip()):
            return {"ok": False, "error": "la fecha tiene que venir como YYYY-MM-DD"}
        try:
            date.fromisoformat(fecha)
        except ValueError:
            return {"ok": False, "error": f"'{fecha}' no es una fecha real"}
        self.bot.state["fecha_pedida"] = fecha
        return {"ok": True, "fecha": fecha,
                "nota": ("La app va a abrir ese día con SU configuración guardada. Confírmaselo "
                         "al cliente en una línea. Lo montado hasta ahora se quedó en su fecha.")}
