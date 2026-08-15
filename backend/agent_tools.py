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
import logging
import math
import re
import zlib
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

logger = logging.getLogger(__name__)

_ROL_A_MACRO = {"proteina": "P", "hidrato": "H", "grasa": "G"}
_MACRO_LBL = {"P": "proteína", "H": "hidratos", "G": "grasa"}
# Con artículo, para la frase de qué cuenta: «te cuenta la grasa; la proteína no».
_MACRO_ART = {"P": "la proteína", "H": "los hidratos", "G": "la grasa"}


def _y(palabras: list) -> str:
    """«la proteína y la grasa», no «proteína, grasa»."""
    if len(palabras) <= 1:
        return "".join(palabras)
    return ", ".join(palabras[:-1]) + " y " + palabras[-1]


def _sin_tildes(t: str) -> str:
    """Minúsculas y sin acentos, para comparar con lo que escribió el cliente.

    Nadie teclea las tildes en el chat, y aquí se cotejan citas contra sus mensajes.
    """
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower())
                   if unicodedata.category(c) != "Mn")

# El bote, detrás del plato a igualdad de distancia (punto 78 del documento del 07-08).
# NO son categorías prohibidas: el cliente las busca y las mete cuando quiere, y en el intra
# y el post son justo lo que toca. Es solo el desempate de las SUGERENCIAS en una comida
# normal, donde «primero un aislado de 90 g de proteína» es lo que hizo saltar el punto.
CATS_SUPLEMENTO = [
    '4',      # proteínas en polvo (suero, aislado, caseína, vegetal)
    '14',     # hidratos en polvo
    '18.3',   # hidratos de carbono en polvo para entrenar
    '27',     # sustitutivos de comidas
    '29',     # barritas proteicas
    '30',     # proteína en polvo y barritas proteicas
]


class AgentTools:
    """Las herramientas, atadas a una sesión (bot) y a las cachés compartidas."""

    # Cachés de proceso: mismas para todas las sesiones, como _VOCAB_CATALOGO.
    _SEMANTICA = None
    _CORRECTOR = None
    _FOODS = None          # id -> doc del catálogo

    _COMPANYIA = None      # qué va con qué, aprendido de las dietas
    _FORMA = None          # de cuántas piezas se compone una comida, y de qué papeles
    _ROLES = {}            # id -> papel del alimento (P/H/G/V), calculado una vez
    _EF100 = {}            # id -> macros efectivos por 100 g, calculados una vez

    def __init__(self, bot, semantica, corrector, perfil, foods: Dict[int, dict],
                 companyia=None, forma=None):
        self.bot = bot
        self.db = bot.db
        self.semantica = semantica
        self.corrector = corrector
        self.perfil = perfil
        self.foods = foods
        self.companyia = companyia
        self.forma = forma

    @classmethod
    async def _cargar_catalogo(cls, db) -> Dict[int, dict]:
        """El catálogo entero, o nada. Nunca a medias.

        Esta caché es de PROCESO: se llena una vez y la usan todas las sesiones hasta que se
        reinicie el backend. Si la conexión se corta a mitad de la lectura -- y se corta: los
        tests del asistente fallan justo así, con `AutoReconnect` de Atlas al traer los 3.200
        alimentos --, lo que se guardaba era un catálogo incompleto, y a partir de ahí el
        asistente le decía a todo el mundo que no existe un alimento que sí existe. Un fallo
        de red de dos segundos se convertía en un fallo permanente hasta el siguiente
        despliegue, y sin nada en el log que lo dijera.

        Así que se cuenta primero y se compara: si lo que llega no son todos, se reintenta, y
        si tampoco, se levanta la excepción. Fallar la petición es malo; servir un catálogo
        mutilado durante horas es peor.
        """
        from pymongo.errors import AutoReconnect, NetworkTimeout

        ultimo_error = None
        for intento in (1, 2):
            try:
                esperados = await db.foods.count_documents({})
                catalogo = {int(f["id"]): f async for f in db.foods.find({}, {"_id": 0})}
                if esperados and len(catalogo) < esperados:
                    raise AutoReconnect(
                        f"catalogo incompleto: {len(catalogo)} de {esperados}")
                return catalogo
            except (AutoReconnect, NetworkTimeout) as e:
                ultimo_error = e
                logging.getLogger("uvicorn.error").warning(
                    "[agente] el catalogo no se pudo cargar entero (intento %d): %s", intento, e)
        raise ultimo_error

    @classmethod
    async def crear(cls, bot) -> "AgentTools":
        if cls._FOODS is None:
            cls._FOODS = await cls._cargar_catalogo(bot.db)
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
        if cls._FORMA is None:
            from meal_shape import PerfilForma
            forma = await PerfilForma.cargar(bot.db)
            # Sin `meal_shapes` minado (hay que correr `_perfil_forma.py` en cada base) el
            # asistente se comporta como antes: las sugerencias vuelven a ordenarse contra
            # el hueco entero y los menús se componen por macros. Se degrada, no se rompe.
            cls._FORMA = forma if forma.hay_datos else False
        perfil = await bot._perfil_momento()
        return cls(bot, cls._SEMANTICA or None, cls._CORRECTOR, perfil, cls._FOODS,
                   cls._COMPANYIA or None, cls._FORMA or None)

    # ------------------------------------------------------------ contexto común
    def _momento_actual(self) -> str:
        return momento_de_comida(
            self.bot.current_meal_key(),
            self.bot.state.get("num_comidas") or 4,
            self.bot.state.get("single_meal", False),
        )

    def _nombre_comida_actual(self) -> str:
        """Cómo se llama esta comida en la pantalla del cliente: «Comida 1», «Post-entreno».

        Para los avisos que ACABAN VIÉNDOSE en la tarjeta. El momento (desayuno, almuerzo...)
        sigue decidiendo qué es típico de cada comida, pero esa palabra ya no se le enseña:
        decisión de Francisco del 09-08-2026, punto 10.5. Ver `meal_moment.describe_comida`.
        """
        key = self.bot.current_meal_key()
        return self.bot.meal_label(key) or key

    def _universo(self) -> List[dict]:
        """El catálogo que aplica a la comida actual (el peri tiene el suyo)."""
        key = self.bot.current_meal_key()
        todos = list(self.foods.values())
        if key in ("Intra", "Post"):
            return filtrar_por_tipo_comida(todos, "intra" if key == "Intra" else "post")
        return todos

    def _es_preferido(self, food: dict) -> bool:
        """Los gustos de la pestaña de Nutrición: PRIORIZAN, nunca excluyen.

        Es la misma regla que ya aplica el flujo guiado: si el cliente no marcó
        «arroces», el arroz se le sigue enseñando; si marcó «frutos secos», los frutos
        secos salen antes a igualdad de encaje. Aquí faltaba: las tarjetas del chat y la
        biblioteca ignoraban los gustos que él mismo configuró.
        """
        prefs = self.bot.state.get("food_preferences") or []
        if not food or not prefs:
            return False
        from routes.calculator import AVOIDABLE_PREFIXES
        cats = parse_categories(food.get("categorias"))
        for cid in prefs:
            for p in AVOIDABLE_PREFIXES.get(cid, []):
                for c in cats:
                    if c == p or c.startswith(p + "."):
                        return True
        return False

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

    # ---------------------------------------------------- de qué se compone una comida
    def _rol_de(self, food: dict) -> str:
        """Qué papel hace este alimento en el plato: P, H, G o V.

        El mismo `classify_food_role` con el que se montan las comidas, con los mixtos
        llevados a su macro dominante (un lácteo proteico y unos huevos son la proteína
        del desayuno). Se calcula una vez por alimento y por proceso: entra en el bucle
        que recorre los 3.211 del catálogo en cada búsqueda sin texto.
        """
        aid = int(food.get("id") or 0)
        rol = AgentTools._ROLES.get(aid)
        if rol is None:
            from meal_builder import classify_food_role
            try:
                bruto = classify_food_role(food, self._ef100(food))
            except Exception:
                bruto = "H"
            rol = {"P": "P", "PH": "P", "PG": "P", "H": "H", "G": "G", "V": "V"}.get(bruto, "H")
            AgentTools._ROLES[aid] = rol
        return rol

    def _ef100(self, food: dict) -> dict:
        """Los macros que CUENTAN de este alimento por 100 g, calculados una vez.

        Se consultan para cada alimento del catálogo en cada búsqueda sin texto (para el
        papel y para saber si aporta el macro que se busca), y calcularlos cuesta: la
        primera búsqueda del proceso tardaba 5,8 s y las siguientes 0,66."""
        aid = int(food.get("id") or 0)
        ef = AgentTools._EF100.get(aid)
        if ef is None:
            from meal_builder import get_effective_macros_per_100g
            try:
                ef = get_effective_macros_per_100g(food)
            except Exception:
                ef = {"P": 0.0, "H": 0.0, "G": 0.0, "cat": ""}
            AgentTools._EF100[aid] = ef
        return ef

    def _piezas_por_cubrir(self, restante: dict) -> int:
        """Cuántos alimentos le faltan a esta comida para parecerse a una comida real.

        De aquí sale la diferencia entre MONTAR y REMATAR, que es el fondo de lo que
        Francisco vio el 12-08 (doce batidos seguidos para un desayuno vacío):

          - montando (faltan 2 piezas o más), ninguna pieza tiene que cubrir el hueco
            entero, así que juzgar cada alimento contra ese hueco entero premia justo a
            los que sí lo cubren solos, que son los sustitutivos de comida;
          - rematando (falta 1), el hueco sí es de una pieza y vuelve a mandar «lo que
            menos desajusta», que es lo que pidió Jesús en el punto 76 del 07-08.

        Sin `meal_shapes` minado se responde 1 y todo sigue como estaba.
        """
        if not self.forma:
            return 1
        # UN SOLO MACRO PENDIENTE NO ES UNA COMIDA, ES UN REMATE. Si a la comida solo le
        # falta proteína -- ya tiene su pan y su aceite --, lo que se pide es algo que
        # cierre esa proteína, no tres trozos que la repartan. Es el caso 39 de Jesús:
        # «faltan 40,5 g de proteína: todas las opciones los cierran».
        if sum(1 for m in ("P", "H", "G") if float(restante.get(m, 0) or 0) > 4) < 2:
            return 1
        momento = self._momento_actual()
        kcal = sum(max(float(restante.get(m, 0) or 0), 0) * (9 if m == "G" else 4)
                   for m in ("P", "H", "G"))
        tipicas = self.forma.piezas_tipicas(momento, kcal)
        puestas = len(((self.bot.state.get("comidas_completadas") or {})
                       .get(self.bot.current_meal_key()) or {}).get("alimentos", []))
        return max(1, tipicas - puestas)

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
            "que_cuenta": self._frase_que_cuenta(food),
        }

    def _anotar_ofrecidos(self, items: List[dict]) -> None:
        """Apunta que estos alimentos ya se le han enseñado en esta comida.

        Misma memoria que el botón de sugerir (`seen_sugg`), para que las dos vías cuenten
        lo mismo. Se limpia sola al vaciar la comida, que es donde ya se limpiaba.
        """
        key = self.bot.current_meal_key()
        vistos = self.bot.state.setdefault("seen_sugg", {}).setdefault(key, [])
        for it in items:
            if it.get("id") not in vistos:
                vistos.append(it["id"])

    def _frase_que_cuenta(self, food: dict) -> str:
        """El filtro del tercio y las excepciones por categoría, ya resueltos y en palabras.

        Jesús, 12-08-2026: «Si le mandas "almendras: te cuenta la grasa, la proteína no", no
        tiene que razonar la regla y no la puede fallar. Si le mandas la regla y los macros
        crudos, la fallará algunas veces. Y basta una para que el cliente deje de fiarse».

        La regla ya era determinista (`_que_cuenta`, el mismo motor que la calculadora), pero
        solo se alcanzaba llamando a la herramienta `explicar`, o sea cuando al modelo se le
        ocurría preguntarla. Aquí pasa a venir puesta en CADA alimento que el asistente ve --
        búsquedas, borradores de menú y lo que ya hay en la comida --, porque `_item_de` es
        la única puerta por la que entran todos.
        """
        try:
            cuenta, _brutos, _cat, _base = self.bot._que_cuenta(food)
        except Exception:
            return ""   # un alimento raro no puede tumbar una búsqueda
        si = [_MACRO_ART[m] for m in ("P", "H", "G") if cuenta[m]]
        no = [_MACRO_ART[m] for m in ("P", "H", "G") if not cuenta[m]]
        if not si:
            return "no cuenta ningún macro (es libre)"
        if not no:
            return "cuenta los tres macros"
        return f"te cuenta {_y(si)}; {_y(no)} no"

    # ============================================================ 1. buscar_alimentos
    async def buscar_alimentos(self, texto: str = "", para_macro: str = None,
                               generico: bool = None, marca: str = None,
                               etiquetas: List[str] = None,
                               coherente_con_momento: bool = True,
                               limite: int = 8,
                               heredar_estilo: bool = True,
                               acompanando_a: List[dict] = None,
                               hueco: dict = None,
                               familia: str = None,
                               anotar: bool = True,
                               como_pieza: bool = False) -> dict:
        """Busca en el catálogo con el texto TAL CUAL lo dijo el cliente (la traducción
        coloquial→catálogo es semántica, no una tabla). Sin texto, ordena por lo que más
        aporta al macro pedido (o al que más falta). Devuelve cada alimento ya
        dimensionado a lo que cabe en la comida actual."""
        # El tope de 15 es para lo que ve el cliente (una tarjeta por resultado, y tokens).
        # Las búsquedas internas del compositor (`anotar=False`) no se enseñan y necesitan
        # de dónde elegir: con 15 resultados repartidos entre familias, a cada hueco del
        # menú le llegaban uno o dos candidatos y las tres opciones salían casi iguales.
        limite = max(1, min(int(limite or 8), 15 if anotar else 30))
        # El hueco contra el que se dimensiona y se ordena. Normalmente es lo que le falta
        # a la comida, pero quien está MONTANDO un menú tiene que pasar lo que le falta al
        # menú ya empezado: si no, al buscar el complemento se mide contra la comida entera
        # y entran alimentos que la cubren de golpe -- un muffin de 40 P / 40 H / 6 G
        # encima de una base que ya llevaba 43 g de hidratos de avena, y el menú se pasaba
        # 40 g. Se veía como «pidiendo algo con avena no sale ninguna opción».
        restante = dict(hueco) if hueco else self.bot.get_remaining_macros()
        momento = self._momento_actual()
        # El repertorio del cliente, una vez por herramienta: ordena sus tarjetas igual
        # que ya ordena las sugerencias del bot (lo suyo delante, en tramos).
        self._mios = await self.bot.usos_propios()
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
            # Sin texto la petición ES el macro («dame algo de proteína»), y ahí lo que
            # manda es CUÁNTO DESAJUSTA cada alimento, no cuánto aporta del macro que falta.
            #
            # Esto ordenaba por `macros_por_100g[macro que falta]`, que es literalmente
            # «mirar el macro que falta sin mirar lo que desajusta al meterlo» (punto 76
            # del documento de Jesús). Con 9,3 g de proteína y 6,2 de grasa pendientes
            # salían en el puesto 6 un aislado de 89,9 g de proteína y una tortita de maíz
            # de 125 g de grasa. Ordenando por distancia esos se van al final solos y suben
            # las brochetas de pollo, que dan 9,2 P y 6,2 G: distancia 0,1.
            #
            # Se mira el catálogo ENTERO y se ordena después, con cada alimento ya
            # dimensionado. Acotar antes por «lo que más aporta por 100 g» -- que es lo que
            # se hacía -- deja fuera justo lo que se busca: los primeros son siempre los
            # concentrados, así que las brochetas de pollo (9,2 P y 6,2 G, distancia 0,1)
            # ni llegaban a competir con un aislado (9 P y 0 G, distancia 6,5). Medido:
            # dimensionar los 3.211 alimentos cuesta 0,53 s, nada al lado de lo que tarda
            # el modelo en contestar.
            orden = list(universo)

        # MONTAR NO ES REMATAR (13-08-2026).
        #
        # Sin texto, la petición es «algo para esta comida», y con la comida vacía el hueco
        # es el de la comida ENTERA. Ordenar por lo que menos la desajusta premia entonces
        # al que la cubre él solo, que es la definición de sustitutivo de comida. Medido en
        # la Comida 1 con 50P/30H/10G: de 15 sugerencias, 6 batidos, 4 yogures proteicos, 3
        # levaduras y 2 pancakes. Cuatro familias, ningún huevo, ningún pan, ninguna fruta.
        # Francisco, 12-08: «me ofreció todo yogur o batidos pero nada de proteína real como
        # huevos, u otros acompañamientos, tostadas, palta, frutas». En las dietas reales un
        # desayuno de solo batidos y polvos es el 0,3 % (5 de 1.441).
        #
        # Montando, cada alimento se mide y se dimensiona contra LA PARTE que le toca a una
        # pieza de su papel: en un desayuno real la proteína la ponen 3 piezas, los hidratos
        # 1 y la grasa 1 (medianas de `meal_shapes`). Rematando (falta una pieza), no cambia
        # nada: sigue mandando «lo que menos desajusta», que es el punto 76 de Jesús.
        # Con texto manda la petición del cliente y el hueco es el de la comida: quien pide
        # «pechuga de pollo» quiere la que le cierre lo que falta. `como_pieza` lo fuerza
        # igualmente, y lo usa el compositor: ahí el texto es el estilo del menú, no una
        # pieza suelta, y sin esto el batido de un «menú con batido» se dimensionaba contra
        # los 50 g de proteína de la comida entera y salían 176 g que se pasaban 13.
        piezas_por_cubrir = self._piezas_por_cubrir(restante) if (como_pieza or not texto) else 1
        montando = piezas_por_cubrir > 1 and bool(self.forma)
        cuotas = {}
        if montando:
            cuotas = {m: self.forma.cuota(momento, m, max(float(restante.get(m, 0) or 0), 0))
                      for m in ("P", "H", "G")}

        # --- filtros duros (datos del catálogo, nunca juicios)
        marca_norm = self.bot._norm_text(marca) if marca else None
        etiquetas = {e.upper() for e in (etiquetas or [])}
        vetados_momento = vetados_solos = 0
        items, no_caben, repetidos = [], [], []
        ya_ofrecidos = set(self.bot.state.setdefault("seen_sugg", {})
                           .get(self.bot.current_meal_key()) or [])
        # Lo que ya hay en el plato: decide si un acompañamiento tiene a quién acompañar.
        # `acompanando_a` lo pasa quien está MONTANDO un menú, donde el plato todavía está
        # vacío pero las piezas ya están elegidas; sin eso, un menú compuesto de cero nunca
        # podría llevar mermelada ni miel.
        #
        # Con `.get`, no con corchetes: el estado de la sesión se guarda en
        # `chatbot_sessions` y vive entre despliegues, así que una sesión abierta antes de
        # que existiera esta clave revienta aquí con un KeyError -- y lo hace dentro de la
        # sugerencia, o sea que al cliente se le cae el asistente entero. Una comida sin
        # nada puesto y una clave que todavía no existe son lo mismo para este cálculo:
        # ninguna de las dos tiene alimentos con los que acompañar.
        ya_en_la_comida = list(acompanando_a or []) + [
            self.foods[int(f["alimento"]["id"])]
            for f in ((self.bot.state.get("comidas_completadas") or {})
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
            # Familia (cat2) exacta: la usa el compositor para pedir «el pan de este menú»
            # o «la grasa de este menú» siguiendo un esqueleto real, en vez de pedir «algo
            # que dé hidratos» y que le toque lo que sea.
            if familia and cat2_de(food) != familia:
                continue
            if etiquetas and not etiquetas <= self._etiquetas_de(food):
                continue
            if self._es_evitado(food):
                continue
            # Quien no lleva ese macro no puede aportarlo: se descarta ANTES de calcular su
            # cantidad, que es lo caro. Es el mismo filtro que ya había debajo sobre el
            # alimento ya dimensionado, adelantado con los macros por 100 g; sin él, cada
            # búsqueda por macro dimensionaba los 3.211 alimentos del catálogo para tirar
            # 2.400. Solo cuando no hay texto: con texto manda lo que ha pedido el cliente.
            if not texto and para_macro in ("P", "H", "G") \
                    and float(self._ef100(food).get(para_macro, 0) or 0) <= 0:
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
            sized = self.bot._size_food(
                food, self._hueco_de_pieza(restante, food, cuotas) if montando else restante)
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
            # LO QUE YA SE LE ENSEÑÓ, AL FINAL DE LA COLA.
            #
            # Caso 7 de los diez de Jesús: «alguien que dice "esto no me gusta" tres veces
            # seguidas». Sin esto, el ranking es el mismo cada vez y a la tercera le salen
            # los mismos tres alimentos; medido, fallaba las tres pasadas del banco. La
            # memoria es la de siempre (`seen_sugg`, por comida), la misma que ya usaba el
            # botón de sugerir: así el chat y el botón no se pisan.
            #
            # Se aparta, no se descarta: si al filtrar no queda nada nuevo, mejor repetir
            # que decirle que no hay. Y lo que ha pedido POR SU NOMBRE nunca se aparta:
            # quien escribe «lechuga» quiere lechuga, se la hayan ofrecido antes o no.
            (repetidos if (aid in ya_ofrecidos and aid not in pedidos_por_nombre)
             else items).append(self._item_de(food, cantidad_g, macros))
            # Con texto se corta ya: el orden lo manda lo que pidió el cliente y los
            # primeros son los suyos. Sin texto NO se corta, porque el orden bueno es por
            # distancia y esa solo se sabe con el alimento dimensionado: quedarse con los
            # primeros que pasan los filtros es de donde salían los disparates.
            if texto and len(items) >= limite:
                break

        if not texto:
            if items:
                items = self._ordenar_sugerencias(items, restante, momento, cuotas)
            if repetidos:
                repetidos = self._ordenar_sugerencias(repetidos, restante, momento, cuotas)
        # SIN NADA NUEVO, LA RUEDA DA OTRA VUELTA (ver `_semilla_variedad`). Si se le han
        # enseñado ya todos los candidatos, volver al orden de siempre es lo que hacia que
        # la sexta sugerencia fuera identica a la primera. Se vacia la memoria de esta
        # comida y se sube la vuelta, que cambia el barajado: asi insistir trae algo
        # distinto en vez de lo mismo.
        if not items and repetidos:
            key_c = self.bot.current_meal_key()
            self.bot.state.setdefault("seen_sugg", {})[key_c] = []
            vueltas = self.bot.state.setdefault("vueltas_sugerencia", {})
            vueltas[key_c] = int(vueltas.get(key_c, 0)) + 1
            items, repetidos = self._ordenar_sugerencias(repetidos, restante, momento, cuotas), []
        if len(items) < limite:
            items = items + repetidos[:limite - len(items)]
        if not texto:
            items = self._topar_por_familia(items)
        items = items[:limite]
        # `anotar=False` lo pasa el compositor: mira decenas de alimentos por cada menú que
        # monta y el cliente no ve ninguno. Apuntarlos como enseñados dejaba la memoria de
        # sugerencias llena de cosas que nadie vio, y luego el chat las apartaba por
        # repetidas.
        if anotar:
            self._anotar_ofrecidos(items)

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
                notas.append(f"{vetados_momento} descartados por atípicos para la "
                             f"{self._nombre_comida_actual()} "
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

    # Dos alimentos que se desvían 1,5 g y 3 g del hueco son igual de buenos: compiten en
    # el mismo tramo y dentro se baraja. Sin esto ganaría siempre el mismo y volveríamos a
    # tener el sugeridor que da lo mismo a todo el mundo.
    ESCALON_DISTANCIA = 3.0

    # Cuántas veces puede repetirse una misma familia (cat2) en una lista de sugerencias.
    # Seis batidos distintos no son seis opciones, son una: el cliente no elige entre
    # Barebells y Valio, elige entre desayunar un batido o desayunar huevos con pan.
    MAX_POR_FAMILIA = 2

    # Hasta qué escalón de desvío se considera que un alimento «entra» en su cuota. Con
    # ESCALON_DISTANCIA = 3 g, son 9 g: lo que se puede recolocar moviendo cantidades en el
    # resto del plato. Por encima, el alimento no está haciendo el papel que se le pide.
    ESCALONES_QUE_ENTRAN = 3

    def _hueco_de_pieza(self, restante: dict, food: dict, cuotas: dict) -> dict:
        """El hueco contra el que se mide UNA pieza: su macro topado a lo que le toca, y
        los demás como están (nadie puede pasarse de lo que le falta a la comida)."""
        h = {m: max(float(restante.get(m, 0) or 0), 0) for m in ("P", "H", "G")}
        rol = self._rol_de(food)
        if rol in h and cuotas.get(rol):
            h[rol] = min(h[rol], cuotas[rol])
        return h

    def _topar_por_familia(self, items: List[dict]) -> List[dict]:
        """Deja como mucho `MAX_POR_FAMILIA` de la misma familia por delante; el resto va
        detrás sin perderse. Es lo que evita la lista de doce variantes de lo mismo."""
        cabeza, cola, vistas = [], [], {}
        for it in items:
            fam = cat2_de(self.foods.get(it["id"]) or {})
            vistas[fam] = vistas.get(fam, 0) + 1
            (cabeza if vistas[fam] <= self.MAX_POR_FAMILIA else cola).append(it)
        return cabeza + cola

    def _ordenar_sugerencias(self, items: List[dict], restante: dict, momento: str,
                             cuotas: dict = None) -> List[dict]:
        """Rematando, lo que menos desajusta (punto 76). Montando, una lista con la forma
        de una comida (ver `_mezclar_por_papel`)."""
        if not cuotas:
            return self._ordenar_por_distancia(items, restante)
        return self._mezclar_por_papel(items, momento, cuotas)

    def _mezclar_por_papel(self, items: List[dict], momento: str, cuotas: dict) -> List[dict]:
        """Una lista que se parece a una comida: proteínas, hidratos y grasas mezclados.

        Repartir el hueco entre las piezas NO bastaba, y está medido: con la comida vacía
        y el hueco dividido entre cinco seguían saliendo doce lácteos proteicos seguidos.
        La razón es que la distancia se mide sobre los TRES macros a la vez, así que
        siempre gana el alimento que los cubre todos en la proporción justa, y las piezas
        de una comida de verdad son especializadas: los huevos ponen proteína y no traen
        hidratos, el pan pone hidratos y no trae proteína.

        Así que cada alimento compite SOLO con los de su papel y SOLO por su macro, y la
        lista se compone después mezclándolos en la proporción de una comida real de ese
        momento (3 proteínas por 1 hidrato y 1 grasa en un desayuno). Los papeles cuyo
        macro ya está cubierto van al final: siguen estando, pero no ocupan la cabeza.
        """
        import random
        from meal_shape import MACRO_DE_ROL

        rng = random.Random(self._semilla_variedad())
        colas: Dict[str, List[dict]] = {}
        for it in items:
            colas.setdefault(self._rol_de(self.foods.get(it["id"]) or {}), []).append(it)

        en_peri = self.bot.current_meal_key() in ("Intra", "Post")
        for rol, lista in colas.items():
            rng.shuffle(lista)
            macro = MACRO_DE_ROL.get(rol)
            cuota = cuotas.get(macro) if macro else None
            if not cuota:
                continue
            # Dentro del papel: primero lo que más se acerca a su cuota (por escalones,
            # para que dos alimentos parecidos no queden siempre en el mismo orden), y a
            # igualdad de encaje lo que de verdad se come a esa hora.
            #
            # El desempate por momento no sobraba: sin él, la cuota de grasa de un desayuno
            # la ganaban la morcilla oreada, el paté de hígado y la galta de cerdo, que
            # encajan en 10 g de grasa tan bien como el aceite de oliva. El filtro de
            # coherencia no los quita porque no tienen datos propios y lo que no se sabe no
            # se penaliza (1.0 neutro); lo que hace falta aquí no es vetarlos, es que el
            # aceite, el aguacate y los frutos secos -- que están en el 26 % de los
            # desayunos reales -- salgan antes. Y a igualdad, la comida real por delante
            # del bote (punto 78).
            # Primero lo que ENTRA en su cuota, y entre lo que entra, lo que Jesús pone de
            # verdad a esa hora. El encaje se satura en `ESCALONES_QUE_ENTRAN` para que sea
            # una puerta y no una regla de tres: dentro de esa tolerancia manda el uso real,
            # y lo que se aleja más se va al final por mucho que se use. Así los huevos, que
            # se quedan a 8 g de su cuota porque su grasa topa antes, siguen saliendo (son
            # la mitad de los desayunos), y un alimento que no pinta nada no se cuela por
            # ser popular. A igualdad, la comida real antes que el bote (punto 78).
            # Dentro de la puerta del encaje: primero SUS gustos (los de la pestaña de
            # Nutrición), luego SU repertorio (lo que él come de verdad), luego lo típico
            # del momento. Igual que en el flujo guiado: el gusto prioriza, no excluye.
            def _gusto(it):
                return 0 if self._es_preferido(self.foods.get(it["id"])) else 1
            mios = getattr(self, "_mios", None) or {}
            def _mio(it):
                usos = mios.get(it["id"], 0)
                return min(int(math.log2(usos)) + 1, 15) if usos > 0 else 0
            lista.sort(key=lambda it: (
                min(int(abs(float(it["macros"].get(macro, 0) or 0) - cuota)
                        // self.ESCALON_DISTANCIA), self.ESCALONES_QUE_ENTRAN),
                _gusto(it),
                -_mio(it),
                -self._tipico_en(it, momento),
                0 if en_peri else self._es_bote(it)))

        # Cuántas de cada papel: las que lleva una comida real de ese momento. Un papel
        # cuyo macro ya está cubierto no entra en el reparto y se queda para el final.
        pesos = {}
        for rol, lista in colas.items():
            macro = MACRO_DE_ROL.get(rol)
            if lista and macro and cuotas.get(macro):
                pesos[rol] = max(1, self.forma.piezas_de_rol(momento, rol))
        if not pesos:
            return items

        # Reparto proporcional: cada papel acumula su peso y sale el que más crédito tiene,
        # así la cabeza lleva uno de cada y el conjunto respeta la proporción de la comida.
        total = sum(pesos.values())
        credito = {rol: 0.0 for rol in pesos}
        salida = []
        while any(colas[rol] for rol in pesos):
            for rol in pesos:
                credito[rol] += pesos[rol]
            rol = max((r for r in pesos if colas[r]), key=lambda r: credito[r])
            credito[rol] -= total
            salida.append(colas[rol].pop(0))
        for rol, lista in colas.items():
            salida.extend(lista)
        return salida

    def _tipico_en(self, item: dict, momento: str) -> int:
        """Cuánto se pone ESTO a esa hora, en tramos: 3 = a diario, 0 = casi nunca.

        Es el uso REAL del alimento en ese momento, no su coherencia. La coherencia es un
        ratio y sirve para vetar lo que no pega (callos a las 8:00), pero para ELEGIR entre
        lo que sí pega empata a todo el mundo: una crema de yogur de marca rara hereda de
        «yogures» y compite de tú a tú con las claras pasteurizadas. Probado en la Comida 1:
        ordenando por coherencia salían Yeo Valley, Wow cereals y Naturli, y no salía ni un
        huevo, ni pan, ni las claras, que son la mitad de los desayunos de Jesús.

        En tramos logarítmicos y no en bruto para que el desempate no se coma el barajado:
        entre dos alimentos que se usan a diario decide el encaje de macros, y el orden de
        los que empatan cambia cada día.
        """
        if not self.perfil or momento == PERI:
            return 0
        food = self.foods.get(item.get("id"))
        if not food:
            return 0
        try:
            usos = self.perfil.usos(food, momento)
        except Exception:
            return 0
        if usos <= 0:
            return 0
        # En log2 y no en log10: con tres tramos empataban ciento y pico alimentos y el
        # desempate acababa siendo el barajado, así que las claras (9.998 usos en desayuno)
        # competían de igual a igual con un jamón serrano de 120. Doblar los usos sube un
        # escalón, que separa lo suficiente sin dejar de agrupar a los parecidos.
        return min(int(math.log2(usos)) + 1, 15)

    def _es_bote(self, item: dict) -> int:
        """1 si el alimento es de las categorías de suplemento (punto 78)."""
        for c in parse_categories(item.get("categorias")):
            for p in CATS_SUPLEMENTO:
                if c == p or c.startswith(p + "."):
                    return 1
        return 0

    def _ordenar_por_distancia(self, items: List[dict], restante: dict) -> List[dict]:
        """Los que menos desajustan la comida, primero (`diferenciaDeMacros` de Calma).

        Punto 76 del documento del 07-08: «ordenar por |ΔP| + |ΔH| + |ΔG| respecto al
        hueco, de menor a mayor». La función ya existía en el motor y la calculadora ya
        ordenaba así; el asistente no. Ordenaba por lo que más aportaba del macro que
        faltaba, y por eso con 9,3 g de proteína pendientes ofrecía un aislado de 89,9.

        Arregla de paso el punto 78 (polvos por delante de la comida real) sin penalizar
        nada a mano: un aislado da 9 g de proteína y 0 de grasa -- distancia 6,5 --,
        mientras que unas brochetas de pollo dan 9,2 P y 6,2 G a la vez, distancia 0,1. La
        comida real gana sola porque cubre los dos macros de un golpe.

        PERO NO SIEMPRE: cuando el polvo y la comida real caen en el MISMO escalón de 3 g,
        el orden dentro del escalón lo decidía el barajado, así que el aislado podía volver
        a salir el primero. El punto pedía «penalizar las categorías de suplemento cuando
        hay alternativas de comida real que cubren igual», y eso es exactamente un
        desempate: a igualdad de distancia, primero lo que se come.

        En el intra y en el post NO se aplica: ahí el polvo es lo que toca, y el universo
        de esas dos ya viene filtrado por `_universo`.
        """
        from calma_suggest import diferencia_de_macros
        hueco = {"proteinas": float(restante.get("P", 0) or 0),
                 "hidratos": float(restante.get("H", 0) or 0),
                 "grasas": float(restante.get("G", 0) or 0)}

        def distancia(it):
            m = it.get("macros") or {}
            return diferencia_de_macros(
                {"proteinas": m.get("P", 0), "hidratos": m.get("H", 0), "grasas": m.get("G", 0)},
                hueco)

        # A igualdad de escalón, la comida real por delante del bote (punto 78).
        en_peri = self.bot.current_meal_key() in ("Intra", "Post")

        def es_polvo(it):
            return 0 if en_peri else self._es_bote(it)

        # Y dentro del escalón, SUS gustos y SU repertorio por delante (14-08-2026): los
        # de la pestaña de Nutrición priorizan aquí igual que en el flujo guiado, y lo que
        # este cliente come de verdad gana a lo estadísticamente típico. El barajado sigue
        # decidiendo entre iguales de verdad.
        def _gusto(it):
            return 0 if self._es_preferido(self.foods.get(it["id"])) else 1
        mios = getattr(self, "_mios", None) or {}
        def _mio(it):
            usos = mios.get(it["id"], 0)
            return min(int(math.log2(usos)) + 1, 15) if usos > 0 else 0
        import random
        rng = random.Random(self._semilla_variedad())
        rng.shuffle(items)
        return sorted(items, key=lambda it: (int(distancia(it) // self.ESCALON_DISTANCIA),
                                             _gusto(it), -_mio(it), es_polvo(it)))

    def _semilla_variedad(self) -> int:
        """Con qué se baraja: estable por CLIENTE, DÍA y COMIDA.

        Ni fija ni al azar puro. Fija daba lo que Francisco vio el 08-08 -- todos los
        clientes con los mismos macros recibiendo exactamente las mismas tres recetas --;
        al azar puro cambiaría las opciones cada vez que se recarga la página, y el
        cliente no entendería nada. Así el mismo cliente ve lo mismo mientras esté en esa
        comida, y mañana o el de al lado ven otra cosa."""
        st = self.bot.state
        # `getattr` y no punto seco: no toda la casa entra por una sesión de chat. El
        # compositor de menús usa estas mismas herramientas con un bot sin sesión, y ahí
        # `session_id` no existe: con el acceso directo se cae la ordenación entera, que es
        # de lo último que uno quiere que dependa de un atributo opcional. Sin sesión, la
        # semilla es la del día y la comida, que sigue siendo estable.
        #
        # Y LA VUELTA. Estable esta bien para recargar la pagina, pero hacia que INSISTIR
        # devolviera lo mismo: cuando ya se le habian enseñado todos los candidatos, la
        # memoria de `seen_sugg` se quedaba sin nada nuevo y el orden volvia a ser el de
        # siempre. Medido el 12-08: pidiendo sugerencias seis veces seguidas, las vueltas
        # 1, 5 y 6 salian IDENTICAS -- «los copos de avena estan siempre», dijo Francisco.
        # La vuelta sube cada vez que se agota la lista, asi que la rueda da otro giro en
        # vez de pararse, y recargar sin pedir nada nuevo sigue enseñando lo mismo.
        partes = (str(getattr(self.bot, "session_id", None) or ""),
                  str(st.get("fecha_objetivo") or ""),
                  self.bot.current_meal_key(),
                  str((st.get("vueltas_sugerencia") or {}).get(self.bot.current_meal_key(), 0)))
        # `crc32` y no `hash()`: el hash de las cadenas en Python lleva una sal ALEATORIA
        # POR PROCESO, así que la semilla «estable por cliente, día y comida» cambiaba en
        # cada arranque del backend. El cliente veía otras sugerencias tras cada despliegue
        # sin haber tocado nada, y en los tests salía como fallo intermitente (el del punto
        # 78 pasaba o fallaba según la corrida, sin tocar el código).
        return zlib.crc32("|".join(partes).encode("utf-8"))

    def _acompanamiento_suelto(self, items: List[dict], ids_exentos: set = None):
        """¿Lleva este menú algo que nunca es el plato, sin nada a lo que acompañar?

        Mismo criterio que en las sugerencias (`es_sugerible` + `_acompana_a_algo`), pero
        mirando el menú YA MONTADO en vez de la comida: al componer, la comida está vacía y
        cualquier acompañamiento quedaba huérfano por definición. Devuelve el motivo o None.

        Lo que el cliente fijó por su nombre no se juzga: si quiere la crema de cacao, es
        suya. Esto solo corrige lo que el asistente monta por su cuenta.
        """
        from calculator import es_sugerible
        ids_exentos = ids_exentos or set()
        foods = [self.foods[i["id"]] for i in items if i.get("id") in self.foods]
        for f in foods:
            if int(f.get("id", 0)) in ids_exentos or es_sugerible(f):
                continue
            otros = [o for o in foods if o.get("id") != f.get("id")]
            if not self._acompana_a_algo(f, otros):
                return (f"un intento ponía {f.get('nombre')} sin nada a lo que acompañar, "
                        f"y eso no se come solo")
        return None

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

    # ------------------------------------------------- menús con forma de comida real
    def _rol_de_familia(self, familia: str) -> str:
        """Qué papel hace una familia entera (cat2) en el plato: el de la mayoría de sus
        alimentos. '8.1' (panes) es H, '1.2' (huevos) es P, '17.1' (aceites) es G."""
        rol = AgentTools._ROLES.get(f"fam:{familia}")
        if rol is None:
            votos: Dict[str, int] = {}
            for f in self.foods.values():
                if cat2_de(f) == familia:
                    r = self._rol_de(f)
                    votos[r] = votos.get(r, 0) + 1
            rol = max(votos, key=votos.get) if votos else "H"
            AgentTools._ROLES[f"fam:{familia}"] = rol
        return rol

    def _esqueletos_para(self, momento: str, restante: dict, fijos: list,
                         fams_pedidas: set = None) -> List[List[str]]:
        """Las formas de comida reales que sirven para lo que falta, de más a menos usada.

        Un esqueleto es la lista de familias de una comida que Jesús montó de verdad
        ('1.1', '1.2', '2.1', '8.1', '17.1' son claras, huevos, fiambre de pavo, pan y
        aceite). Se descartan los que no traen el papel de un macro que falta -- un
        esqueleto sin hidratos no puede cubrir 30 g de hidratos -- y las familias de los
        alimentos que el cliente ha exigido se quitan del esqueleto, porque su sitio ya
        está ocupado por lo suyo.
        """
        if not self.forma:
            return []
        faltan = {m for m in ("P", "H", "G") if float(restante.get(m, 0) or 0) > 4}
        roles_fijos = {self._rol_de(food) for _, food in fijos}
        fams_fijas = {cat2_de(food) for _, food in fijos}
        # Una comida entera no se cubre con dos cosas. Los esqueletos de dos familias
        # existen (el 7,5 % de las comidas reales llevan uno o dos alimentos) pero son la
        # excepción, y es justo lo que Francisco señaló: «no tiene sentido que solo tenga
        # esas dos cosas». Cuando lo que falta es poco -- una comida ya empezada -- el
        # mínimo baja solo, porque ahí dos piezas sí son una comida.
        minimo_familias = min(3, self._piezas_por_cubrir(restante))
        # Y un techo, por el otro lado: hay comidas reales de ocho y nueve alimentos, pero
        # son la cola. Una merienda de Jesús tiene 3 piezas de mediana y salían menús de 9,
        # que no son cómodos de preparar aunque cuadren. Se deja un margen de una pieza
        # sobre lo típico, que es donde está el 85 % de las comidas.
        maximo_familias = self._piezas_por_cubrir(restante) + 1
        salida = []
        for familias, _n in self.forma.formas(momento):
            # LO QUE PIDE EL CLIENTE MANDA SOBRE LA FORMA. Si ha dicho «avena», solo valen
            # las comidas reales que llevan avena; el resto no son una alternativa suya,
            # son otra cosa. Sin esto el esqueleto se comía la petición: pidiendo «avena»
            # salía un desayuno de huevos, pan y pavo, y pidiendo «pollo» tampoco había
            # pollo. Cuando ninguna forma real lleva lo pedido se devuelve vacío a
            # propósito, y compone el camino de siempre, que sí parte del texto.
            if fams_pedidas and not (fams_pedidas & set(familias)):
                continue
            fams = [f for f in familias
                    if f not in fams_fijas and self._rol_de_familia(f) not in roles_fijos]
            roles = {self._rol_de_familia(f) for f in fams} | roles_fijos
            if not faltan <= roles:
                continue
            if minimo_familias <= len(fams) + len(fijos) <= maximo_familias:
                salida.append(fams)
        if not salida and fams_pedidas:
            salida = self._esqueleto_alrededor_de(fams_pedidas, faltan, roles_fijos,
                                                  fams_fijas, minimo_familias)
        return salida

    def _esqueleto_alrededor_de(self, fams_pedidas: set, faltan: set, roles_fijos: set,
                                fams_fijas: set, minimo: int) -> List[List[str]]:
        """Cuando lo pedido no sale en ninguna comida entera, se le monta una alrededor.

        Pasa con lo que Jesús casi nunca pone como plato: pidiendo «batido» no había ni un
        esqueleto real con esa familia, así que se caía al camino por macros -- el que
        montaba «batido + proteína de soja + cacahuete frito con miel» -- y encima con
        ocho intentos y quince cuadres, que son 21 de los 29 s que tardaba.

        Con qué se acompaña no lo decide nadie a mano: son las familias que más veces
        coinciden con la pedida en las 147.820 comidas reales (`company_profiles`), y solo
        las que hacen el papel de un macro que todavía falta.
        """
        if not self.companyia:
            return []
        salida = []
        for pedida in sorted(fams_pedidas):
            perfil = self.companyia.categorias.get(pedida)
            if not perfil:
                continue
            fams = [pedida]
            roles = {self._rol_de_familia(pedida)} | roles_fijos
            for otra, _veces in sorted((perfil.get("con") or {}).items(),
                                       key=lambda kv: -kv[1]):
                if faltan <= roles and len(fams) >= minimo:
                    break
                rol = self._rol_de_familia(otra)
                if otra in fams or otra in fams_fijas or rol in roles:
                    continue
                if rol not in faltan and len(fams) >= minimo:
                    continue
                fams.append(otra)
                roles.add(rol)
            if faltan <= roles and len(fams) + len(fams_fijas) >= minimo:
                salida.append(fams)
        return salida

    async def _familias_de(self, texto: str, cache: dict = None) -> set:
        """Las familias a las que apunta lo que ha pedido el cliente ('avena' -> 7.1).

        Se resuelve con la misma búsqueda que usa el chat, así que vale cualquier forma de
        decirlo; solo se miran los primeros resultados, que son los que de verdad son eso.

        De paso deja en el caché lo encontrado, repartido por familia: es la MISMA lista
        que necesita después cada hueco del esqueleto, y buscarla una vez por familia
        costaba una búsqueda semántica por cada una (medido: 15,6 s en montar tres menús
        con estilo, contra 2,4 s sin estilo).
        """
        if not texto:
            return set()
        res = await self.buscar_alimentos(texto=texto, limite=30, anotar=False,
                                          como_pieza=True)
        items = res.get("items") or []
        if cache is not None:
            por_familia: Dict[str, List[dict]] = {}
            for it in items:
                por_familia.setdefault(cat2_de(self.foods.get(it["id"]) or {}), []).append(it)
            for fam, lista in por_familia.items():
                cache[(fam, texto)] = lista
        return {cat2_de(self.foods.get(i["id"]) or {}) for i in items[:4]}

    async def _candidatos_de_macro(self, macro: str, estilo: str, generico: bool,
                                   marca: str, cache: dict) -> List[dict]:
        """Los mejores para ese macro, sin atarse a una familia. Es el respaldo cuando la
        familia que pedía el esqueleto no da nada aquí."""
        # La clave NO lleva el estilo: la búsqueda es sin texto (el estilo ya se ha puesto
        # en su pieza), así que meterlo en la clave solo servía para repetir la misma
        # búsqueda una vez por estilo. Eran 7 de los 21 s que tardaba «menús con batido».
        clave = (f"macro:{macro}", "")
        if clave not in cache:
            res = await self.buscar_alimentos(
                texto="", para_macro=macro, generico=generico, marca=marca,
                limite=8, heredar_estilo=False, anotar=False, como_pieza=True)
            cache[clave] = res.get("items") or []
        return cache[clave]

    # Cuánto se pueden parecer dos opciones. Por encima de esto son la misma idea con otro
    # nombre y no son una alternativa.
    PARECIDO_MAXIMO = 0.6

    def _siguiente_esqueleto(self, esqueletos: List[List[str]], usados: List[List[str]],
                             desde: int) -> List[str]:
        """La siguiente forma de comida que NO sea la de al lado otra vez.

        Los esqueletos vienen ordenados por lo que más se repite, y los primeros de un
        momento suelen ser variaciones del mismo plato: en producción, las tres opciones de
        un desayuno salieron «copos + proteína + nueces», «queso batido + muesli + proteína
        + almendras» y «muesli + proteína + pistachos». Cada una es un desayuno de Jesús,
        pero las tres juntas son una sola propuesta repetida, y Francisco lo leyó como lo
        que es: no darle a elegir. Se salta el que comparte más del `PARECIDO_MAXIMO` de sus
        familias con alguno ya propuesto; si no queda ninguno distinto, se sigue por orden,
        que es mejor que quedarse sin opción.
        """
        n = len(esqueletos)
        for salto in range(n):
            esq = esqueletos[(desde + salto) % n]
            fams = set(esq)
            if all(len(fams & set(u)) / max(len(fams | set(u)), 1) <= self.PARECIDO_MAXIMO
                   for u in usados):
                return esq
        return esqueletos[desde % n]

    async def _candidatos_de_familia(self, fam: str, estilo: str, generico: bool,
                                     marca: str, cache: dict) -> List[dict]:
        """Los mejores de esa familia para esta comida, buscados una sola vez.

        El caché no es un adorno: cada opción mira 4 o 6 familias, los esqueletos comparten
        casi todas, y sin él la misma búsqueda sobre los 3.211 alimentos se repetía hasta
        cuarenta veces por petición (medido: 14 s en montar tres menús).
        """
        clave = (fam, estilo or "")
        if clave in cache:
            return cache[clave]
        # Con estilo NO se vuelve a buscar: lo que hay es lo que dejó `_familias_de` de su
        # única búsqueda, repartido por familias. Cada búsqueda con texto pasa por la
        # semántica y cuesta 2 s; repetirla por familia era la mitad de los 12 s que
        # tardaba montar tres menús con estilo. Si de esa familia no salió nada, la pieza
        # se elige sin estilo: «avena» no dice nada sobre el aceite del desayuno.
        items = []
        if not estilo:
            res = await self.buscar_alimentos(
                texto="", generico=generico, marca=marca, familia=fam,
                limite=8, heredar_estilo=False, anotar=False, como_pieza=True)
            items = res.get("items") or []
        else:
            items = await self._candidatos_de_familia(fam, "", generico, marca, cache)
        cache[clave] = items
        return items

    async def _elegir_por_esqueleto(self, esqueleto: List[str], estilo: str,
                                    generico: bool, marca: str, salto: int,
                                    ids_puestos: List[int], tipos_puestos: set,
                                    cache: dict, fams_pedidas: set = None,
                                    faltan: set = None, objetivo: dict = None,
                                    ya_en_otras: set = None) -> List[dict]:
        """Un alimento por familia del esqueleto, el que Jesús pondría ahí.

        La elección de cada hueco es la misma búsqueda de siempre (ya ordena por lo que
        entra en su cuota y por lo que se usa de verdad a esa hora), acotada a esa familia.
        `salto` rota el elegido dentro de cada familia para que dos opciones del mismo
        esqueleto no salgan idénticas.

        EL ESTILO SOLO PINTA EN SU PIEZA. Pedir «avena» dice qué hidrato quiere el cliente,
        no cómo tiene que ser el resto del plato; arrastrarlo a todas las familias es lo que
        montaba «leche de avena + Colacao avenacao + 250 g de fiambre de pavo», donde lo
        único que unía las tres piezas era la palabra. En las demás manda lo de siempre: lo
        que se pone de verdad a esa hora.
        """
        fams_pedidas = fams_pedidas or set()
        ya_en_otras = ya_en_otras or set()
        def _antes_los_nuevos(lista):
            """El mismo alimento no puede salir en las tres opciones.

            Las familias SÍ se repiten entre opciones -- dos meriendas distintas pueden
            llevar las dos su lácteo --, pero el alimento concreto no: en la app salieron
            las opciones 11, 12 y 13 las tres con «Queso fresco batido 0 %», que es la
            misma queja de siempre con otra cara. Se ORDENA, no se descarta: si de esa
            familia no queda nada más, mejor repetir que dejar el hueco sin cubrir.
            """
            if not ya_en_otras:
                return lista
            return ([c for c in lista if c["id"] not in ya_en_otras]
                    + [c for c in lista if c["id"] in ya_en_otras])

        def _casan(lista):
            """Los que además pegan con lo que ya está puesto en este menú.

            El esqueleto acierta con las FAMILIAS, pero dentro de una familia caben cosas
            que no se ponen juntas: montado el menú entero salían «patatas fritas con
            pechuga de pollo» o «queso batido con kaki», y entonces el filtro de compañía
            tumbaba la opción ENTERA y había que enseñarla con un aviso al pie. Mirar la
            compañía aquí, pieza a pieza, sale mucho más barato: se elige otro alimento de
            la misma familia y el menú nace bien.

            Si ninguno casa se devuelve la lista tal cual: mejor un menú con un par flojo
            (que el aviso explicará) que un hueco sin cubrir.
            """
            if not self.companyia or not ids_puestos:
                return lista
            puestos = [self.foods[i] for i in ids_puestos if i in self.foods]
            buenos = []
            for c in lista:
                food = self.foods.get(c["id"])
                if not food:
                    continue
                if self.companyia.discordante(puestos + [food]):
                    continue
                buenos.append(c)
            return buenos or lista

        def _valen(lista):
            # UN BOTE POR MENÚ COMO MUCHO. En las comidas reales de Jesús el 36 % lleva
            # algún suplemento, casi siempre uno y rodeado de comida: yogur, copos, aislado
            # y crema de cacahuete. Sin este tope salían dos y tres por menú -- «batido +
            # proteína de soja + cacahuete», que es la queja del 12-08 -- y el 69 % de los
            # menús acababa con bote, el doble de lo que él hace.
            ya_hay_bote = any(self._es_bote({"categorias": (self.foods.get(i) or {}).get("categorias")})
                              for i in ids_puestos)
            return [c for c in lista
                    if c["id"] not in ids_puestos
                    and cat2_de(self.foods.get(c["id"]) or {}) not in tipos_puestos
                    and not (ya_hay_bote and self._es_bote(c))]

        elegidos = []
        for fam in esqueleto:
            texto_fam = estilo if fam in fams_pedidas else ""
            cands = _antes_los_nuevos(_casan(_valen(await self._candidatos_de_familia(
                fam, texto_fam, generico, marca, cache))))
            if not cands:
                # Esa familia no da nada aquí (o su sitio ya está ocupado): se busca otra
                # pieza del MISMO papel, que es lo que el plato necesita. Sin esto el menú
                # se quedaba sin grasa y luego lo descartaba la puerta de calidad por
                # quedarse corto, con lo que la forma real se perdía por el camino.
                macro = {"P": "P", "H": "H", "G": "G"}.get(self._rol_de_familia(fam))
                if macro:
                    cands = _antes_los_nuevos(_casan(_valen(await self._candidatos_de_macro(
                        macro, texto_fam, generico, marca, cache))))
            if not cands:
                continue
            elegido = cands[salto % len(cands)]
            elegidos.append(elegido)
            ids_puestos.append(elegido["id"])
            tipos_puestos.add(cat2_de(self.foods.get(elegido["id"]) or {}))

        # NINGÚN MACRO SE QUEDA SIN QUIEN LO PONGA. El esqueleto se elige mirando el papel
        # de cada FAMILIA, pero el alimento concreto que sale de ella puede no hacerlo: de
        # los panes proteicos (papel de proteína en su familia) salió una tostada, y con
        # «tostadas» se montó un desayuno de dos tostadas y cacahuetes al que le faltaban
        # los 50 g de proteína enteros. Se comprueba sobre lo elegido, que es lo único que
        # no engaña, y si falta el que lo pone, se añade.
        for macro in sorted(faltan or ()):
            puesto = sum(float(c["macros"].get(macro, 0) or 0) for c in elegidos)
            if puesto >= 0.25 * float((objetivo or {}).get(macro, 0) or 0):
                continue
            cands = _antes_los_nuevos(_casan(_valen(await self._candidatos_de_macro(
                "" if macro == "V" else macro, "", generico, marca, cache))))
            if not cands:
                continue
            elegido = cands[salto % len(cands)]
            elegidos.append(elegido)
            ids_puestos.append(elegido["id"])
            tipos_puestos.add(cat2_de(self.foods.get(elegido["id"]) or {}))
        return elegidos

    # ------------------------------------------------------------ comidas reales
    # LAS OPCIONES SALEN DE COMIDAS QUE ALGUIEN COMIÓ, NO DE INVENTAR (14-08-2026).
    #
    # Francisco: «la IA no sabe montar menús... tengo una base de datos de todas las
    # dietas de los usuarios, ¿por qué no la entrenas con eso?». Tenía razón en el fondo:
    # el compositor INVENTA combinaciones pieza a pieza y luego filtra con estadísticas, y
    # inventar-y-filtrar deja pasar tonterías (la crema de cacao con la paella salió por
    # ahí). Una comida que una persona real comió es coherente por construcción: el
    # trabajo bueno no es inventar, es encontrarla y reajustar las cantidades.
    #
    # Dos fuentes, por este orden, y el compositor queda de último recurso:
    #   1. El HISTORIAL del propio cliente en esa misma comida (desde el 13-08 está
    #      completo en producción). Nada le encaja mejor que lo suyo.
    #   2. La BIBLIOTECA de comidas reales (266k, con su filtro de calidad de la cosecha).
    #
    # Y la puerta de coherencia, que es la otra mitad de lo que pidió: «un usuario puede
    # armar un día sin sentido porque hizo una prueba, y esos menús no pueden pasar».
    # Lo repetido pasa solo (2+ clientes distintos, o 2+ fechas en el historial propio:
    # nadie repite un experimento); lo que una persona montó UNA vez lo juzga el modelo
    # del chat una única vez en la vida, con el veredicto guardado (`core/juez_menus`).
    # Si el juez no contesta, ese menú no se ofrece: mejor una opción menos.

    async def _veredicto_menu(self, momento: str, items: List[dict],
                              clientes: int = 0, fechas: int = 0,
                              juicios: dict = None) -> str:
        """'pasa', 'fuera' o 'sin_veredicto' (cupo agotado o el juez caído, sin cachear).

        La diferencia entre 'fuera' y 'sin_veredicto' importa: lo juzgado malo se tira
        siempre; lo no juzgado se tira salvo que no quede NADA que enseñar, y entonces
        sale con su aviso (quedarse sin nada es peor, decisión del 07-08).
        """
        from core.juez_menus import (JUICIOS_POR_PETICION, firma_de, juzgar,
                                     pasa_sin_juicio, veredicto_cacheado)
        if pasa_sin_juicio(clientes, fechas):
            return "pasa"
        firma = firma_de(momento, [i["id"] for i in items])
        visto = await veredicto_cacheado(self.db, firma)
        if visto is not None:
            return "pasa" if visto else "fuera"
        if juicios is not None:
            if juicios.get("n", 0) >= JUICIOS_POR_PETICION:
                return "sin_veredicto"   # el resto de candidatos, a la próxima petición
            juicios["n"] = juicios.get("n", 0) + 1
        etiqueta = [f"{i['nombre']} ({float(i.get('cantidad_g') or 0):.0f} g)" for i in items]
        vale = await juzgar(self.db, momento, etiqueta, firma)
        if not vale and await veredicto_cacheado(self.db, firma) is None:
            return "sin_veredicto"       # el juez no contestó; no es lo mismo que un no
        return "pasa" if vale else "fuera"

    async def _pasa_coherencia(self, momento: str, items: List[dict],
                               clientes: int = 0, fechas: int = 0,
                               juicios: dict = None) -> bool:
        """Para las fuentes recuperadas (historial, biblioteca): solo el 'pasa' vale."""
        return await self._veredicto_menu(momento, items, clientes=clientes,
                                          fechas=fechas, juicios=juicios) == "pasa"

    async def _recuadrar_a_hoy(self, foods: List[dict], restante: dict):
        """Recuadra un menu REAL al hueco de hoy. Devuelve los items, o None si no da.

        Tres pasos, y el porque de cada uno (14-08-2026, del repaso de Francisco):

        1. `build_meal` con el resolvedor EXACTO: los mismos alimentos, cantidades de hoy.
        2. Si UN macro queda corto mas alla del margen, se remata con UNA pieza, igual
           que hace el compositor: su desayuno de siempre mas un poco de pan es un
           servicio; «elige y ya lo retocamos» es trabajo a medias.
        3. Y si ni rematado entra SIN avisos, no se ofrece. Un menu recuperado sale
           limpio o no sale: los rescates con aviso son del compositor, que es el ultimo
           recurso y ahi se justifican.
        """
        from meal_builder import build_meal

        por_nombre = {f["nombre"]: f for f in foods}

        async def _exacto(q, *a, **k):
            f = por_nombre.get(q)
            return [f] if f else []

        def _items_de(rb):
            out = [self._item_de(por_nombre[x["nombre"]],
                                 float(x.get("cantidad", 0) or 0), x.get("macros", {}))
                   for x in (rb.get("foods_added") or []) if x.get("nombre") in por_nombre]
            return out if len(out) == len(por_nombre) else None

        try:
            items = _items_de(await build_meal(self.db, list(por_nombre.keys()), restante,
                                               _exacto, forzar=True))
        except Exception:
            return None
        if items is None:
            return None

        def _tot(its):
            return {m: sum(i["macros"][m] for i in its) for m in ("P", "H", "G")}

        tot = _tot(items)
        cortos = [m for m in ("P", "H", "G") if restante[m] - tot[m] > MARGEN_BORRADOR]
        if len(cortos) == 1 and len(por_nombre) <= 5:
            try:
                res = await self.buscar_alimentos(texto="", para_macro=cortos[0], limite=3,
                                                  heredar_estilo=False, anotar=False,
                                                  como_pieza=True)
                for extra in (res.get("items") or []):
                    f2 = self.foods.get(extra["id"])
                    if not f2 or f2["nombre"] in por_nombre or self._es_evitado(f2):
                        continue
                    por_nombre[f2["nombre"]] = f2
                    nuevo = _items_de(await build_meal(self.db, list(por_nombre.keys()),
                                                       restante, _exacto, forzar=True))
                    if nuevo:
                        items, tot = nuevo, _tot(nuevo)
                    else:
                        por_nombre.pop(f2["nombre"], None)
                    break
            except Exception:
                pass

        if sum(max(tot[m] - restante[m], 0) for m in ("P", "H", "G")) > 2 * MARGEN_BORRADOR:
            return None
        if any(restante[m] - tot[m] > MARGEN_BORRADOR for m in ("P", "H", "G")):
            return None
        return items

    async def _menus_del_historial(self, restante: dict, momento: str, n: int = 2,
                                   offset: int = 0, incluir_ids: List[int] = None,
                                   juicios: dict = None) -> List[dict]:
        """Las comidas que ESTE cliente ya se monta en ESTA comida, recuadradas a hoy.

        Mismo hueco del día (C1 con C1): su desayuno no se le ofrece de cena. Solo entran
        las firmas comidas en dos fechas o más -- un día de prueba no se repite -- o las
        que apruebe el juez. Las cantidades se recalculan siempre contra lo que falta HOY,
        así que da igual cómo cuadrara aquel día.
        """
        from meal_builder import build_meal

        key = self.bot.current_meal_key()
        firmas: Dict[tuple, set] = {}
        async for d in self.db.diets.find({"user_id": self.bot.usuario_id},
                                          {"_id": 0, "comidas": 1, "fecha": 1}
                                          ).sort("fecha", -1).limit(400):
            comida = (d.get("comidas") or {}).get(key) or {}
            ids = sorted({int(a["alimento_id"]) for a in (comida.get("alimentos") or [])
                          if a.get("alimento_id") is not None})
            if 2 <= len(ids) <= 7:
                firmas.setdefault(tuple(ids), set()).add(str(d.get("fecha")))

        pedidos = set(int(x) for x in (incluir_ids or []))
        candidatas = sorted(firmas.items(), key=lambda kv: -len(kv[1]))
        salida, saltadas = [], 0
        for firma, fechas in candidatas:
            if len(salida) >= n:
                break
            if pedidos and not pedidos <= set(firma):
                continue
            foods = [self.foods.get(i) for i in firma]
            if any(f is None or self._es_evitado(f) for f in foods):
                continue
            if list(firma) in (self.bot.state.get("menus_vistos") or []):
                continue
            if saltadas < offset:                      # «dame otras»: rota el escaparate
                saltadas += 1
                continue
            items = await self._recuadrar_a_hoy(foods, restante)
            if items is None:
                continue
            if not await self._pasa_coherencia(momento, items,
                                               fechas=len(fechas), juicios=juicios):
                continue
            salida.append({"items": items, "origen": "historial", "nombre": None,
                           "receta_url": None})
        return salida

    async def _menus_de_la_biblioteca(self, restante: dict, momento: str, n: int = 2,
                                      offset: int = 0, incluir_ids: List[int] = None,
                                      ya: List[tuple] = None,
                                      familias_ya: List[set] = None,
                                      juicios: dict = None) -> List[dict]:
        """Comidas reales de la biblioteca (266k), ya cuadradas por su ajustador.

        El filtro de calidad de la cosecha viene puesto de fábrica; aquí se añaden las
        restricciones de ESTE cliente, la coherencia con el momento (una comida de
        mediodía no se ofrece de desayuno) y la puerta del juez para lo que solo montó
        una persona.
        """
        from meal_builder import build_meal
        from meal_library import buscar_en_biblioteca

        # SOLO EN COMIDA Y CENA (14-08-2026, medido): la biblioteca es de tipo "comida",
        # y en el desayuno el filtro de coherencia de momento tumbaba TODOS los
        # candidatos... despues de traerse 500 menus enteros por la red. 19,5 segundos
        # para devolver cero. El desayuno ya lo cubren el historial, el recetario y el
        # compositor; aqui ni se entra.
        from meal_moment import CENA, COMIDA
        if momento not in (COMIDA, CENA):
            return []
        tipo = "peri" if momento == PERI else "comida"
        try:
            reales = await buscar_en_biblioteca(
                self.db, restante,
                alimento_ids=[int(x) for x in incluir_ids] if incluir_ids else None,
                tipo=tipo, limit=n + offset + 12, max_candidatos=120)
        except Exception:
            return []
        ya = set(ya or [])
        familias_ya = [set(f) for f in (familias_ya or [])]
        # Los gustos de la pestaña de Nutrición también ordenan aquí: entre dos menús
        # reales que cuadran, primero el que lleva algo de lo que marcó que le gusta.
        # Orden estable: dentro de cada grupo sigue mandando el criterio de la biblioteca
        # (cuadradas primero, la que más gente distinta montó).
        def _con_gusto(r):
            return 0 if any(self._es_preferido(self.foods.get(int(i["alimento_id"])))
                            for i in (r.get("items") or [])) else 1
        reales.sort(key=_con_gusto)
        salida, saltadas = [], 0
        for r in reales:
            if len(salida) >= n:
                break
            ids = [int(i["alimento_id"]) for i in (r.get("items") or [])]
            # El techo de piezas que ya usa el compositor: el 84,5 % de las comidas
            # reales llevan 5 alimentos o menos. Un menu de seis o mas es picoteo de
            # alguien (salio uno con un aperitivo frito y salado en pleno desayuno), no
            # una comida que ofrecer.
            if len(ids) > 5:
                continue
            firma = tuple(sorted(ids))
            if firma in ya or list(firma) in (self.bot.state.get("menus_vistos") or []):
                continue
            foods = [self.foods.get(i) for i in ids]
            if any(f is None or self._es_evitado(f) for f in foods):
                continue
            if self.perfil and any(self.perfil.coherencia(f, momento) < COHERENCIA_MINIMA
                                   for f in foods):
                continue
            # DOS OPCIONES CASI IGUALES NO SON DOS OPCIONES (14-08-2026). Francisco:
            # «muy repetitivo», con cuatro variantes del mismo desayuno (huevos + pan +
            # flan proteico + fiambre) cambiando solo la marca del flan. La firma las
            # distinguia porque el id cambia; las FAMILIAS no: si comparte mas del 60 %
            # de familias con una opcion ya puesta, es la misma comida con otra etiqueta.
            fams = {cat2_de(f) for f in foods}
            if any(len(fams & fy) / max(1, min(len(fams), len(fy))) > 0.6
                   for fy in familias_ya):
                continue
            if saltadas < offset:
                saltadas += 1
                continue
            # RECUADRE AL DIA DE HOY (14-08-2026). La biblioteca trae cada menu con SU
            # cuadre de origen, y el ajustador propio solo toca drivers limpios: los
            # desayunos reales de ~30 g de hidratos salian tal cual contra un objetivo
            # de 51, todos cortos y todos con aviso. Se recuadran con build_meal y el
            # resolvedor exacto, como el historial; si ni recuadrado entra en margen,
            # ese menu no es para este dia y se salta.
            # El juez ANTES del recuadre (14-08): con la biblioteca ya barrida el juicio
            # es una lectura de cache, y el recuadre es un build_meal entero. Recuadrar
            # candidatos que el juez iba a tumbar era donde se iban los segundos.
            clientes = int(((r.get("popularidad") or {}).get("clientes")) or 0)
            items_previos = [{"id": int(i["alimento_id"]), "nombre": i.get("nombre", ""),
                              "cantidad_g": float(i.get("cantidad_g") or 0)}
                             for i in (r.get("items") or [])]
            if not await self._pasa_coherencia(tipo, items_previos,
                                               clientes=clientes, juicios=juicios):
                continue
            items = await self._recuadrar_a_hoy(foods, restante)
            if items is None:
                continue
            # El juicio de un menu de biblioteca va POR SU TIPO (comida/peri), no por el
            # momento en que asoma: si no, el mismo menu se juzgaria una vez para la
            # comida, otra para la cena... y el "entrenamiento" en bloque no serviria de
            # cache. Si pega o no con el momento ya lo decide el filtro mecanico de
            # arriba (coherencia del perfil); el juez decide si ES una comida.
            ya.add(firma)
            familias_ya.append(fams)
            salida.append({"items": items, "origen": "biblioteca",
                           "nombre": r.get("nombre"), "receta_url": None})
        return salida

    # ---------------------------------------------------------- filtros que dice el cliente
    # UN FILTRO QUE HABLA DEL CLIENTE TIENE QUE PODER DEMOSTRARLO (13-08-2026).
    #
    # Francisco: «siempre me dice que pedí genéricos, y solo le pedí opciones, nunca
    # mencioné ni genéricos ni marcas». En la sesión de producción estaba escrito negro
    # sobre blanco: `filtros = {'generico': True, 'marca': None, 'estilo': 'Comida 1'}`
    # después de un «para la comida dos dame opciones». El modelo rellenaba un booleano que
    # en el esquema no tenía ni descripción, y el revisor lo repetía como un hecho: «pidió
    # genéricos y Nocilla noir es de marca».
    #
    # Y no era solo un cartel molesto: con `generico=True` el compositor deja fuera TODAS
    # las marcas del catálogo en cada opción, o sea que estaba estrechando el catálogo por
    # su cuenta en todas las composiciones. Justo lo contrario de la variedad que se pide.
    #
    # No se arregla pidiéndole al modelo que no lo haga: se le pide la CITA. Si el filtro
    # viene de lo que dijo el cliente, sus palabras están en la conversación; si no están,
    # el filtro no se aplica y se le dice por qué. Comprobarlo es mirar el historial, no
    # adivinar intenciones, y el cliente solo tiene que copiar.
    def _lo_dijo_el_cliente(self, cita: str) -> bool:
        cita = _sin_tildes((cita or "").strip().strip('"«»“”'))
        if len(cita) < 3:
            return False
        dicho = [_sin_tildes(str(h.get("content") or ""))
                 for h in (self.bot.messages_history or [])
                 if h.get("role") == "user"]
        # Lo que él mismo mandó apuntar cuenta igual: lo escribió el cliente, solo que en
        # otro turno («no me compro marcas» dicho el lunes vale el martes).
        dicho += [_sin_tildes(str(n)) for n in (self.bot.state.get("notas_cliente") or [])]
        return any(cita in d for d in dicho)

    def _filtro_de_marca(self, generico, marca, porque):
        """(generico, marca, nota). Sin cita del cliente que lo respalde, no hay filtro."""
        if generico is None and not marca:
            return generico, marca, None
        if self._lo_dijo_el_cliente(porque):
            return generico, marca, None
        pedido = "genéricos" if generico is True else ("de marca" if generico is False
                                                       else f"solo {marca}")
        return None, None, (
            f"NO he filtrado por {pedido}: no consta que el cliente lo pidiera. Si lo dijo, "
            "vuelve a llamarme con `filtro_porque` = sus palabras exactas. Si no lo dijo, "
            "no se lo atribuyas: el menú va con todo el catálogo.")

    def _estilo_limpio(self, estilo: str) -> str:
        """El estilo es cómo quiere la comida, no cuál es.

        Llegaba `estilo="Comida 1"` desde el modelo, y eso se va a la búsqueda semántica a
        buscar alimentos que se parezcan a la frase «Comida 1»: ni es lo que el cliente
        pidió ni significa nada de comida. Los nombres de las comidas del día salen del
        propio estado, así que esto no es una lista de palabras que haya que mantener.
        """
        e = (estilo or "").strip()
        if not e:
            return ""
        nombres = {_sin_tildes(str(k)) for k in (self.bot.state.get("meal_order") or [])}
        nombres |= {f"comida {i}" for i in range(1, 9)}
        nombres |= {"intra", "post", "peri", "pre", "pre entreno", "postentreno"}
        return "" if _sin_tildes(e) in nombres else e

    # ============================================================ 2. componer_menu
    async def componer_menu(self, incluir_ids: List[int] = None, estilo: str = "",
                            generico: bool = None, marca: str = None,
                            n: int = 3, solo_recetario: bool = False,
                            filtro_porque: str = None) -> dict:
        """Monta hasta `n` menús completos para la comida actual con el catálogo entero.
        `incluir_ids` son obligatorios (van en todas las opciones); `estilo` es el texto
        libre del cliente y guía la elección por semántica. El recetario (153 recetas de
        Jesús) entra como candidato cuando encaja; nunca limita.
        Deja cada opción como BORRADOR: enseñar sí, aplicar solo tras revisar."""
        from meal_builder import build_meal, get_effective_macros_per_100g, classify_food_role

        n = max(1, min(int(n or 3), 4))
        incluir_ids = [int(x) for x in (incluir_ids or []) if int(x) in self.foods]
        # Los filtros que hablan del cliente, solo con sus palabras detrás (ver arriba).
        generico, marca, nota_filtro = self._filtro_de_marca(generico, marca, filtro_porque)
        estilo = self._estilo_limpio(estilo)
        restante = self.bot.get_remaining_macros()
        momento = self._momento_actual()
        opciones: List[dict] = []

        # CADA VEZ QUE PIDE OTRA, OTRO BARAJADO (ver `_semilla_variedad`).
        #
        # Francisco, 12-08-2026: «repite siempre copos de avena, los copos están siempre que
        # le pido la sugerencia». Medido pidiendo seis veces seguidas: las vueltas 1, 5 y 6
        # salían IDÉNTICAS. La semilla es estable por cliente-día-comida a propósito -- para
        # que recargar la página no cambie lo que está viendo --, pero eso hacía que INSISTIR
        # tampoco lo cambiara. Aquí sube la vuelta en cada peticion NUEVA de menús, que es lo
        # que el cliente entiende por «dame otras»; recargar no pasa por aquí.
        key_comida = self.bot.current_meal_key()
        pedidas = self.bot.state.setdefault("veces_compuesto", {})
        if pedidas.get(key_comida):
            vueltas = self.bot.state.setdefault("vueltas_sugerencia", {})
            vueltas[key_comida] = int(vueltas.get(key_comida, 0)) + 1
        pedidas[key_comida] = int(pedidas.get(key_comida, 0)) + 1

        # --- 0) COMIDAS REALES ANTES DE INVENTAR NADA (14-08-2026, ver el bloque de
        # arriba). Primero lo que este cliente ya se monta en esta comida (tope 2 de n:
        # lo suyo abre, pero las otras plazas traen cosas nuevas), luego la biblioteca.
        # Con estilo o filtros de marca no se entra: una comida recuperada no sabe
        # respetarlos, y ofrecer «lo de siempre» a quien pidió «algo ligero» es no
        # escuchar. El peri tampoco: ahí manda el guion del método.
        # El cupo de juicios de ESTA petición lo comparten las fuentes recuperadas y el
        # compositor (4 llamadas al juez como mucho; el resto lo pone el cache). Se crea
        # AQUÍ y no dentro del if: con estilo o filtros no hay recuperación, pero el
        # compositor sigue necesitando su juez.
        juicios = {"n": 0}
        if momento != PERI and not solo_recetario and not estilo \
                and generico is None and not marca:
            vuelta = int(self.bot.state.get("vueltas_sugerencia", {}).get(key_comida, 0))
            try:
                opciones += await self._menus_del_historial(
                    restante, momento, n=min(2, n), offset=vuelta,
                    incluir_ids=incluir_ids, juicios=juicios)
            except Exception:
                logger.warning("historial de comidas no disponible", exc_info=True)
            # La biblioteca rellena, pero deja UNA plaza libre: la última la pelean el
            # recetario y el compositor, para que siempre asome algo distinto.
            #
            # SALVO con n=1: ahí no hay variedad que proteger, y reservar la única plaza
            # dejaba a la biblioteca con cupo CERO. Se vio en dev el 14-08: «dame
            # opciones», el modelo pidió una sola, y salió el compositor con la
            # biblioteca sin consultar siquiera.
            cupo_biblio = max(0, (n if n == 1 else n - 1) - len(opciones))
            if cupo_biblio:
                try:
                    opciones += await self._menus_de_la_biblioteca(
                        restante, momento, n=cupo_biblio,
                        offset=vuelta, incluir_ids=incluir_ids,
                        ya=[tuple(sorted(i["id"] for i in o["items"])) for o in opciones],
                        familias_ya=[{cat2_de(self.foods[i["id"]]) for i in o["items"]
                                      if i["id"] in self.foods} for o in opciones],
                        juicios=juicios)
                except Exception:
                    logger.warning("biblioteca de comidas no disponible", exc_info=True)

        # --- 1) Recetario: sin estilo ni filtros que él no sabe respetar, y fuera del peri.
        # `solo_recetario` lo salta a propósito: cuando el cliente PIDE las recetas de
        # Jesús («¿tienes recetas suyas?»), traerlas es lo que hay que hacer, y antes ni
        # con esas salían -- el asistente llegó a contestar que no tenía recetario.
        if momento != PERI and (solo_recetario or
                                (not estilo and not incluir_ids and generico is None and not marca)):
            try:
                from meal_templates import generar_opciones_menu
                from routes.calculator import AVOIDABLE_PREFIXES
                avoid = set()
                for cid in self.bot.state.get("avoided_categories", []):
                    avoid.update(AVOIDABLE_PREFIXES.get(cid, []))
                # Las recetas ya enseñadas en esta conversación van detrás, dentro de su
                # mismo escalón de error: pedir otra opción tiene que traer otra cosa.
                # `menus_vistos` de la sesión ya guarda la firma de lo aplicado; aquí manda
                # la lista de plantillas propuestas, que es lo que se compara.
                ya = set(self.bot.state.get("recetas_ofrecidas") or [])
                recetas = await generar_opciones_menu(
                    self.db, momento, restante,
                    avoided_prefixes=avoid,
                    avoided_keywords=self.bot.state.get("avoided_keywords", []),
                    max_opciones=n,
                    semilla=self._semilla_variedad(),
                    vistos=ya)
                # REPETIR ANTES QUE QUEDARSE CORTO (14-08-2026). Una sesión larga agota
                # el recetario: cada receta ofrecida se apunta para no repetirse, y tras
                # una tarde de pruebas ya no quedaba NINGUNA para el desayuno, así que
                # todo caía al compositor y salía una opción única. Si el filtro de
                # vistas lo dejó a cero, se vuelve a empezar la rueda: una receta buena
                # repetida gana a un compuesto flojo.
                if not recetas and ya:
                    recetas = await generar_opciones_menu(
                        self.db, momento, restante,
                        avoided_prefixes=avoid,
                        avoided_keywords=self.bot.state.get("avoided_keywords", []),
                        max_opciones=n,
                        semilla=self._semilla_variedad(),
                        vistos=set())
                ofrecidas = self.bot.state.setdefault("recetas_ofrecidas", [])
                for r in recetas:
                    if r.get("plantilla_id") and r["plantilla_id"] not in ofrecidas:
                        ofrecidas.append(r["plantilla_id"])
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
                                     "receta_url": r.get("fuente"),
                                     "receta_foto": r.get("foto")})

        # --- 2) Composición propia hasta n, con proteínas distintas entre opciones.
        # Con `solo_recetario` no se compone nada: han pedido las recetas de Jesús, y
        # rellenar con invento propio sería colar lo nuestro como suyo. Si no encaja
        # ninguna, se dice, que también es información.
        if solo_recetario and not opciones:
            return {"borradores": [], "sin_resultados_porque": [
                "ninguna receta del recetario cuadra con lo que falta en esta comida; "
                "dilo así y ofrécele montar algo equivalente tú"]}
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

        async def _candidatos_del_rol(rol: str) -> List[dict]:
            """Los candidatos de un papel, buscados la primera vez que hacen falta.

            Antes se buscaban los tres papeles siempre, al entrar: tres búsquedas de vez y
            media cada una que, cuando el menú se monta sobre un esqueleto, no se usan
            nunca. Medido en «menús con batido»: 6,4 s de los 23 que tardaba."""
            if rol in candidatos_por_rol:
                return candidatos_por_rol[rol]
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
            return candidatos_por_rol[rol]

        # Subfamilias ya usadas EN CUALQUIER opción anterior (también las del recetario):
        # mientras haya alternativas, ninguna se repite entre opciones. Antes solo rotaba
        # la proteína y salían tres menús idénticos con la grasa cambiada (visto 07-08).
        usadas_entre_opciones = {_cat2_de_id(i["id"]) for o in opciones
                                 for i in o.get("items", []) if i.get("id") in self.foods}
        # LA FORMA DE LA COMIDA, ANTES QUE LOS MACROS (13-08-2026).
        #
        # Debajo, la composición de siempre elige UN alimento por macro que falta, y de ahí
        # salían menús que cuadran y que nadie se come: «copos de avena 50 g + 218 g de
        # fiambre de magro de jamón» para desayunar, o «batido + proteína de soja +
        # cacahuete frito con miel». Francisco, 12-08: «no tiene sentido que solo tenga esas
        # dos cosas, los menús deben de tener sentido».
        #
        # Un menú no es un macro por pieza: es una FORMA. En las dietas reales el 87,6 % de
        # los desayunos llevan de 3 a 6 alimentos, y sus combinaciones se repiten (claras +
        # huevos + pan + fiambre de pavo + aceite, o avena + proteína + frutos secos). Esas
        # combinaciones están minadas en `meal_shapes`, y aquí cada opción se monta sobre
        # una de ellas: el esqueleto dice QUÉ lleva el plato y `build_meal` sigue diciendo
        # CUÁNTO. Si no hay esqueletos (base sin minar, o ninguno sirve para lo que falta),
        # se sigue por el camino de siempre.
        esqueletos = []
        fams_pedidas: set = set()
        cache_familias: Dict[tuple, List[dict]] = {}
        if momento != PERI:
            fams_pedidas = await self._familias_de(estilo, cache_familias)
            esqueletos = self._esqueletos_para(momento, restante, fijos, fams_pedidas)
        vuelta = int((self.bot.state.get("vueltas_sugerencia") or {}).get(key_comida, 0))
        esqueletos_usados: List[List[str]] = []
        intento = 0
        descartes_bucle = None
        apartadas = []      # descartadas por compañía, por si no queda ninguna otra
        sin_juicio = []     # compuestas que el juez no llegó a ver (cupo o caída)
        rechazadas_juez = []   # compuestas que el juez tumbó, por si no queda NADA
        # Los intentos cuestan: cada uno monta un menú entero (una búsqueda por pieza más
        # el cuadre) y con estilo se llegaba a 29 s. Con esqueletos hacen falta menos, y de
        # sobra: cada uno sale ya con forma de comida en vez de a la primera que cuadre.
        # Los intentos cuestan: cada uno monta un menú entero (una búsqueda por pieza más el
        # cuadre). Con esqueletos hacen falta menos y salen mejor, así que se recortan; el
        # número está medido sobre siete peticiones distintas, no elegido a ojo:
        #
        #   tope    opciones   menús con bote   desvío medio   segundos (total / peor)
        #    n         15            7              4,0            22,1 / 4,8
        #    n+1       18            8              5,4            33,4 / 7,7
        #    n+2       20            9              5,5            44,2 / 11,5
        #
        # n+1 es donde se recuperan las opciones que se pierden por descartar más (una por
        # petición) sin volver a los tiempos de antes, que eran de 16 a 21 s en el peor caso.
        tope_intentos = (n + 1) if esqueletos else (n + 5)
        while not solo_recetario and len(opciones) < n and intento < tope_intentos:
            nombres, ids_opcion, repetida = [], [], False
            for rol, food in fijos:
                nombres.append(food.get("nombre"))
                ids_opcion.append(int(food["id"]))
            # Tipos ya presentes en la opción (subfamilia a 2 niveles): un menú no lleva
            # el mismo alimento dos veces ni dos del mismo tipo en roles distintos. Sin
            # esto, el queso batido (que tiene P e H) salía elegido para LOS DOS roles:
            # "queso batido 300 g + queso batido 300 g" no es una comida de nadie.
            tipos_opcion = {_cat2_de_id(i) for i in ids_opcion}

            # Una forma real por opción, rotando con el intento y con las veces que ya ha
            # pedido otras: «dame otras» tiene que traer otra comida, no la misma con la
            # grasa cambiada.
            # Cuando ya se han probado todas las formas que servían, los intentos que
            # quedan van por el camino de siempre: mejor una opción más, montada por
            # macros, que quedarse en una sola.
            por_esqueleto = []
            if esqueletos and intento < max(len(esqueletos), n):
                esqueleto = self._siguiente_esqueleto(esqueletos, esqueletos_usados,
                                                      intento + vuelta)
                esqueletos_usados.append(esqueleto)
                por_esqueleto = await self._elegir_por_esqueleto(
                    esqueleto, estilo, generico, marca, vuelta + intento,
                    ids_opcion, tipos_opcion, cache_familias, fams_pedidas,
                    faltan={m for m in ("P", "H", "G") if restante[m] > 4},
                    objetivo=restante,
                    ya_en_otras={i["id"] for o in opciones for i in o.get("items", [])})
                for c in por_esqueleto:
                    nombres.append(c["nombre"])
                    usadas_entre_opciones.add(_cat2_de_id(c["id"]))

            # Sin esqueleto, o cuando el que tocaba no dio ni para un plato, el camino de
            # siempre: un alimento por cada macro que falta.
            for rol in ([] if len(por_esqueleto) >= 2 else roles_necesarios):
                if any(r == rol for r, _ in fijos):
                    continue
                cands = await _candidatos_del_rol(rol)
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
                    # QUIEN HACE DE PROTEÍNA TIENE QUE DAR PROTEÍNA. Con texto del cliente
                    # el filtro por macro se levanta a propósito (quien pide lechuga quiere
                    # lechuga), pero aquí no se está resolviendo una petición: se está
                    # rellenando el hueco de proteína de un menú. Sin esto, pidiendo
                    # «tostadas» salía un desayuno de dos tostadas y cacahuetes al que le
                    # faltaban los 50 g de proteína enteros, y con «avena» la proteína la
                    # ponía la avena.
                    if float(c["macros"].get(_ROL_A_MACRO[rol], 0) or 0) <= 0:
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
            # Hasta DOS complementos (lácteo+fruta topan sus máximos), pero uno solo cuando
            # el menú viene de un esqueleto: ese ya trae sus piezas y su papel para cada
            # macro, así que el segundo remate no arreglaba nada y costaba otra búsqueda
            # más otro cuadre por intento.
            for _ in range(1 if por_esqueleto else 2):
                if len(nombres) >= tope_piezas:
                    break
                rem = resultado.get("remaining") or {}
                peor = max(("P", "H", "G"), key=lambda m: float(rem.get(m, 0) or 0))
                if float(rem.get(peor, 0) or 0) <= 8:
                    break
                extra = None
                # Con el menú montado sobre un esqueleto, el estilo ya está puesto en la
                # pieza a la que le tocaba, así que el remate se busca sin él: repetir aquí
                # la búsqueda con texto costaba una semántica (2 s) por intento y por
                # complemento, que es de donde salían los 27 s de montar tres menús.
                textos = [estilo] if (estilo and not por_esqueleto) else []
                textos.append("")
                for txt in textos:
                    if por_esqueleto:
                        # Del caché: la lista de quién puede poner ese macro es la misma en
                        # todos los intentos, y de lo que devuelve solo se usa el NOMBRE
                        # (la cantidad la vuelve a calcular `build_meal` sobre el menú
                        # entero). Repetir la búsqueda en cada intento eran 1,5 s por
                        # intento y de ahí salían los 23 s de montar tres menús con estilo.
                        items_extra = await self._candidatos_de_macro(
                            peor, txt, generico, marca, cache_familias)
                    else:
                        rx = await self.buscar_alimentos(
                            texto=txt, para_macro=peor, generico=generico, marca=marca,
                            limite=6, heredar_estilo=False,
                            # Lo que le falta AL MENÚ, no a la comida entera: el complemento
                            # se pone encima de lo que ya se ha elegido.
                            hueco={m: max(float(rem.get(m, 0) or 0), 0) for m in ("P", "H", "G")},
                            # El complemento SÍ puede ser un acompañamiento (la mermelada de
                            # las tostadas), porque a estas alturas ya hay piezas a las que
                            # acompañar aunque el plato del cliente siga vacío.
                            acompanando_a=[self.foods[i] for i in ids_opcion if i in self.foods])
                        items_extra = rx["items"]
                    extra = next((i for i in items_extra
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
            # UN ACOMPAÑAMIENTO NECESITA A QUIÉN ACOMPAÑAR, TAMBIÉN DENTRO DEL MENÚ.
            #
            # `es_sugerible` y su rescate ya vetan esto en las SUGERENCIAS, pero ahí el
            # rescate mira lo que hay en la comida, y cuando se compone un menú la comida
            # está vacía: la crema de cacao no acompañaba a nada porque todavía no había
            # nada. Se comprueba otra vez con el menú entero montado, que es cuando ya se
            # sabe con qué iba a ir.
            #
            # Sin esto, «paella + pechuga de pavo + Nocilla noir»: cuadra los macros -- una
            # crema de untar cubre hidratos y grasa de una vez -- y no es una comida.
            suelto = self._acompanamiento_suelto(items, ids_fijos)
            if suelto:
                descartes_bucle = suelto
                continue
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
            # LA MISMA TANDA NO REPITE COMIDA (14-08-2026). El candado de familias que ya
            # tienen la biblioteca y el historial vale igual aquí: en una tanda salieron
            # tres opciones con «pollo tikka + arroz congelado» dentro de las tres,
            # cambiando solo el acompañante. Si comparte más del 60 % de familias con una
            # opción ya puesta, es la misma comida con otro adorno.
            fams_op = {_cat2_de_id(i["id"]) for i in items}
            repetida = False
            for o in opciones:
                fo = {_cat2_de_id(x["id"]) for x in o["items"] if x["id"] in self.foods}
                if fo and len(fams_op & fo) / max(1, min(len(fams_op), len(fo))) > 0.6:
                    repetida = True
                    break
            if repetida:
                descartes_bucle = "un intento repetía casi la misma comida y se descartó"
                continue
            # EL COMPOSITOR TAMBIÉN PASA POR EL JUEZ (14-08-2026). Era la única fuente
            # sin juzgar, y por ahí llegó «cereal de maíz con polvo de suero y cacahuete
            # frito» servido como comida. Francisco: «yo no le veo mucho sentido». Lo
            # juzgado malo se tira y el bucle reintenta otra combinación; lo que el juez
            # no llegó a ver (cupo agotado, API caída) solo sale si no queda NADA más, y
            # con su aviso. El peri queda fuera: ahí las piezas las nombra el método.
            if momento != PERI:
                v = await self._veredicto_menu(momento, items, juicios=juicios)
                if v == "fuera":
                    descartes_bucle = "un intento no parecía una comida de verdad y se descartó"
                    if len(rechazadas_juez) < 3:
                        rechazadas_juez.append({"items": items, "origen": "compuesto",
                                                "nombre": None, "receta_url": None})
                    continue
                if v == "sin_veredicto":
                    sin_juicio.append({"items": items, "origen": "compuesto",
                                       "nombre": None, "receta_url": None})
                    continue
            opciones.append({"items": items, "origen": "compuesto", "nombre": None,
                             "receta_url": None})

        # Si el filtro de compañía se lo ha llevado TODO, se rescata lo menos malo con su
        # aviso: quedarse sin nada que ofrecer es peor que ofrecer una combinación rara y
        # decir que lo es.
        if not opciones and apartadas:
            apartadas.sort(key=lambda x: -x[0])
            opciones = [op for _, op in apartadas[:n]]
        # Y si lo único que quedó fue lo que el juez no llegó a ver, sale UNA con su
        # aviso: quedarse sin nada que enseñar es peor (decisión del 07-08), pero decir
        # que no está comprobada es obligatorio.
        if not opciones and sin_juicio:
            op = sin_juicio[0]
            op["aviso_companyia"] = ("no he podido comprobar esta combinación contra el "
                                     "método: revísala antes de darla por buena")
            opciones = [op]
        # Último peldaño: todo lo compuesto fue tumbado por el juez. Antes que una
        # pantalla vacía (regla del 07-08: nadie se queda sin opciones), sale la menos
        # mala DICIENDO que el método no la daría por buena. El cliente decide informado,
        # que es la misma lógica del rescate de compañía.
        if not opciones and rechazadas_juez:
            op = rechazadas_juez[0]
            op["aviso_companyia"] = ("esta combinación no la daría por buena el método: "
                                     "revísala o pídeme otra cosa")
            opciones = [op]

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
        salida, descartes, cortos = [], [], []
        for op in opciones[:n]:
            tot = {m: round(sum(i["macros"][m] for i in op["items"]), 1) for m in ("P", "H", "G")}
            desvio = {m: round(tot[m] - restante[m], 1) for m in ("P", "H", "G")}
            # Bloquea el EXCESO gordo (49 g de grasa sobre 12 no es una comida, es basura)
            # Y TAMBIÉN el déficit gordo.
            #
            # El déficit pasaba entero: se daba por hecho que era «trabajo pendiente» que
            # el agente remataría o que el revisor señalaría. Medido sobre 38 borradores de
            # diez estilos distintos, **el 37 % salía con más de 30 g sin cubrir**, y el
            # peor con 73 (le faltaban 40 g de proteína y 33 de hidratos). Eso no es un
            # menú al que le falta un remate: es medio menú, y el cliente lo acepta creyendo
            # que cuadra. Un menú corto se puede completar y uno pasado no, cierto -- por
            # eso, si al final no queda ninguna opción, la mejor se rescata con su aviso en
            # vez de dejar al cliente sin nada.
            #
            # Los obligatorios del cliente eximen SU exceso, no el del relleno (misma regla
            # que dentro del bucle).
            exceso = sum(max(v, 0) for v in desvio.values())
            deficit = sum(-v for v in desvio.values() if v < 0)
            ids_fijos = {int(f["id"]) for _, f in fijos}
            tot_fij = {m: sum(i["macros"][m] for i in op["items"] if i["id"] in ids_fijos)
                       for m in ("P", "H", "G")}
            exceso_fij = sum(max(tot_fij[m] - restante[m], 0) for m in ("P", "H", "G"))
            if exceso > 2 * MARGEN_BORRADOR and exceso_fij <= MARGEN_BORRADOR:
                peor_m = max(desvio, key=lambda m: desvio[m])
                descartes.append(f"una opción se pasaba {desvio[peor_m]:.0f} g de "
                                 f"{_MACRO_LBL[peor_m]} y se descartó")
                continue
            if deficit > 2 * MARGEN_BORRADOR:
                peor_m = min(desvio, key=lambda m: desvio[m])
                cortos.append((deficit, op, f"le faltaban {-desvio[peor_m]:.0f} g de "
                                            f"{_MACRO_LBL[peor_m]}"))
                descartes.append(f"una opción se quedaba {deficit:.0f} g corta y se descartó")
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
        # Si TODAS se quedaban cortas, se rescata la que menos, con su aviso. Un menú corto
        # se puede rematar; quedarse sin nada que enseñar, no.
        #
        # PERO PRIMERO LA MENOS MALA DE VERDAD. Pidiendo «tostadas» se rescataba un
        # desayuno de dos tostadas y cacahuetes al que le faltaban los 50 g de proteína
        # ENTEROS, habiendo otras opciones cortas mucho más completas. Así que si alguna
        # cubre al menos la mitad de cada macro, el rescate sale de entre esas.
        #
        # Y si NINGUNA llega, se rescata igual: quedarse sin nada que enseñar es peor, que
        # es la decisión de Francisco del 07-08 y lo que protegen `test_menus_cortos` y
        # `test_companyia_y_variedad`. Para eso va el aviso, que dice cuánto falta.
        decentes = [c for c in cortos
                    if all(c[1] and sum(i["macros"][m] for i in c[1]["items"]) >= 0.5 * restante[m]
                           for m in ("P", "H", "G") if restante[m] > 4)]
        cortos = decentes or cortos
        if not salida and cortos:
            cortos.sort(key=lambda x: x[0])
            _, op, motivo = cortos[0]
            tot = {m: round(sum(i["macros"][m] for i in op["items"]), 1) for m in ("P", "H", "G")}
            bid = f"b{len(borradores) + 1}"
            numero += 1
            borrador = {"id": bid, "numero": numero,
                        "items": op["items"], "origen": op["origen"],
                        "nombre": op["nombre"], "receta_url": op.get("receta_url"),
                        "macros_totales": tot, "objetivo": dict(restante),
                        "desvio": {m: round(tot[m] - restante[m], 1) for m in ("P", "H", "G")},
                        "filtros": {"generico": generico, "marca": marca, "estilo": estilo or None},
                        "momento": momento, "meal_key": self.bot.current_meal_key(),
                        "avisos": [f"esta opción se queda corta: {motivo}. Complétala antes "
                                   f"de dársela por buena."]}
            borradores[bid] = borrador
            salida.append(borrador)
        if not salida:
            notas = descartes or []
            if descartes_bucle:
                notas.append(descartes_bucle)
            notas.append("no salió ningún menú que cuadre con esos filtros y lo que "
                         "falta; fija los imprescindibles con incluir_ids o móntalo "
                         "alimento a alimento")
            if nota_filtro:
                notas.append(nota_filtro)
            return {"borradores": [], "sin_resultados_porque": notas}
        out = {"borradores": salida}
        if nota_filtro:
            out["nota"] = nota_filtro
        return out

    # ============================================================ 3. revisar_borrador
    # QUÉ IMPIDE APLICAR UN MENÚ Y QUÉ SOLO SE AVISA (13-08-2026).
    #
    # Antes bloqueaba cualquier problema, y con eso el cliente se quedó encerrado en
    # producción: eligió un menú, se le contestó «no lo he aplicado: pidió genéricos y Copos
    # de avena instant (VitoBest) es de marca», volvió a decir «Elijo: ese menú» y recibió
    # la misma frase. Otra vez.
    #
    # La marca no puede bloquear, porque el menú SE LE ENSEÑÓ con el nombre del producto
    # delante y él lo eligió: elegirlo ES la respuesta a la pregunta. Bloquearlo es discutir
    # con el cliente sobre una preferencia suya. Lo mismo con lo atípico y con lo repetido:
    # son cosas que se dicen, no que se impiden.
    #
    # Lo que sí para la mano es lo que el cliente NO puede haber querido: que el menú se vaya
    # de sus macros, que lleve algo que él tiene en «evitar» (eso no es un gusto, es una
    # alergia o un rechazo firmado en su ficha) o que el alimento ya no exista.
    PROBLEMAS_QUE_BLOQUEAN = {"fuera_de_margen", "restriccion", "no_existe"}

    async def revisar_borrador(self, borrador_id: str) -> dict:
        """Auditoría determinista de un borrador: solo lo comprobable con datos.
        La fidelidad al estilo pedido es responsabilidad de quien llama.

        Cada problema dice si BLOQUEA o solo avisa (`PROBLEMAS_QUE_BLOQUEAN`)."""
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
                # Este `detalle` SE VE en la tarjeta del menú («⚠ Arroz basmati es atípico
                # para desayuno»), así que la comida se nombra como en la pantalla.
                problemas.append({"item_id": it["id"], "tipo": "momento_incoherente",
                                  "detalle": f"{it['nombre']} es atípico para la "
                                             f"{self._nombre_comida_actual()}"})
        firma = tuple(sorted(i["id"] for i in b["items"]))
        if list(firma) in (self.bot.state.get("menus_vistos") or []):
            problemas.append({"item_id": None, "tipo": "ya_ofrecido",
                              "detalle": "este menú ya se le ofreció antes"})
        # EL DESVIO, CONTRA EL OBJETIVO DE AHORA (12-08-2026).
        #
        # Se guardaba al componer, contra lo que faltaba en la comida en ESE momento. Si
        # entre medias cambia la configuracion del dia, el objetivo de la comida cambia y el
        # aviso se queda hablando del viejo: Francisco vio «se desvia 60,1 g de hidratos»
        # justo encima de un «65,9 / 66» que decia lo contrario. Dos numeros que no pueden
        # ser verdad a la vez, y el cliente no sabe a cual creer.
        tot = b.get("macros_totales") or {}
        ahora = self.bot.get_remaining_macros()
        desvio = {m: round(float(tot.get(m, 0) or 0) - float(ahora.get(m, 0) or 0), 1)
                  for m in ("P", "H", "G")}
        b["desvio"] = desvio
        b["objetivo"] = dict(ahora)
        exceso = sum(abs(v) for v in desvio.values())
        if exceso > MARGEN_BORRADOR:
            peor = max(desvio, key=lambda m: abs(desvio[m]))
            problemas.append({"item_id": None, "tipo": "fuera_de_margen",
                              "detalle": f"se desvía {abs(desvio[peor])} g de "
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
        for p in problemas:
            p["bloquea"] = p.get("tipo") in self.PROBLEMAS_QUE_BLOQUEAN
        bloqueantes = [p for p in problemas if p["bloquea"]]
        return {"ok": not problemas, "problemas": problemas,
                # `ok` sigue diciendo si el menú está limpio del todo (lo usa el agente para
                # contarlo), pero aplicar solo se para con estos.
                "impide_aplicar": bloqueantes,
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
        # LOS AVISOS SON DE LA VERSIÓN ANTERIOR (13-08-2026). Al cambiar el menú, la
        # revisión que los generó deja de valer, y se quedaban pegados a la tarjeta: en
        # producción salió «pidió genéricos y Masa para pancake de arroz y avena (Prozis)
        # es de marca» en un menú de copos de avena, whey, nueces y leche de almendras.
        # El aviso era CIERTO cuando se escribió -- el compositor habia metido esa marca --
        # y el propio asistente la sustituyó justo después por el generico; lo que quedó
        # fue la etiqueta, hablando de un alimento que ya no estaba. Quien quiera saber si
        # el menú nuevo tiene problemas, que vuelva a revisarlo.
        b.pop("avisos", None)
        return {"ok": True, "borrador": b}

    # ============================================================ 5. aplicar_borrador
    def _protegida(self, forzar: bool = False) -> Optional[dict]:
        """El error a devolver si la comida actual la trajo montada el cliente. None si no.

        Jesús, 12-08-2026: «Si alguien lo abre a media tarde, le monta el día otra vez y le
        pisa lo que ya tenía». Medido contra la app con dos comidas puestas y «móntame el
        día»: el agente rehacía una de ellas 1 de cada 4 veces (`navegar` a la Comida 1 y
        `editar_comida` encima). Que la comida estuviera montada y guardada no lo paraba,
        porque nada se lo impedía: solo el criterio del modelo, que unas veces acierta y
        otras no.

        Esto no prohíbe cambiar una comida hecha -- el cliente pide eso a menudo --, obliga a
        que sea a petición suya: con `forzar=True`, que el agente solo pone cuando el cliente
        ha nombrado esa comida. Es la misma puerta que ya tenía `aplicar_borrador`.
        """
        if forzar:
            return None
        key = self.bot.current_meal_key()
        if key not in (self.bot.state.get("comidas_traidas") or []):
            return None
        return {
            "ok": False,
            "error": f"{self._nombre_comida_actual()} ya la tenía montada el cliente antes de "
                     f"abrir el chat. No la toques por tu cuenta: enséñale lo que hay y "
                     f"pregúntale si quiere cambiarla. SI YA TE HA DICHO QUE SÍ EN ESTE CHAT, "
                     f"repite AHORA esta misma llamada con forzar=true y hazlo: no se lo "
                     f"vuelvas a preguntar, que es lo que le deja dando vueltas. "
                     f"Para montar lo que le falta, ve a una comida vacía.",
            "comida_ya_montada": self.ver_estado("comida"),
        }

    async def aplicar_borrador(self, borrador_id: str, forzar: bool = False) -> dict:
        """Vuelca un borrador a la comida actual. REVISA antes: solo lo que de verdad
        impide aplicarlo lo para (ver `PROBLEMAS_QUE_BLOQUEAN`); el resto se aplica y se
        cuenta. Con `forzar=True` entra igualmente."""
        b = (self.bot.state.get("borradores") or {}).get(borrador_id)
        if not b:
            return {"ok": False, "error": f"no hay borrador {borrador_id}"}
        protegida = self._protegida(forzar)
        if protegida:
            return protegida
        revision = await self.revisar_borrador(borrador_id)
        impiden = revision.get("impide_aplicar") or []
        if impiden and not forzar:
            return {"ok": False, "bloqueado_por": impiden,
                    "instruccion": "Cuéntale qué pasa y ofrécele arreglarlo. SI YA TE HA "
                                   "DICHO QUE LO QUIERE IGUAL -- «ese», «ponlo», «me da "
                                   "igual» --, repite AHORA esta llamada con forzar=true en "
                                   "vez de volver a preguntar.",
                    "sugerencias_de_cambio": revision.get("sugerencias_de_cambio", [])}
        for it in b["items"]:
            await self.bot.add_food_by_id(it["id"], it["cantidad_g"])
        vistos = self.bot.state.setdefault("menus_vistos", [])
        firma = sorted(i["id"] for i in b["items"])
        if firma not in vistos:
            vistos.append(firma)
        # APLICAR NO ES CERRAR (14-08-2026). El cliente eligió «1», se le aplicó la
        # opción... y el asistente guardó la comida y le plantó el guion del intra sin
        # que nadie se lo pidiera: «me mandó al intra sin que se lo pida, ni había
        # cerrado la comida 1». Elegir un menú monta la comida; cerrarla y avanzar es
        # decisión suya, y el modelo necesita que se lo diga el resultado, no el prompt.
        out = {"ok": True, "comida": self.ver_estado("comida"),
               "instruccion": ("La comida queda MONTADA, no cerrada: NO llames a "
                               "guardar_comida por tu cuenta. Enséñale cómo quedó y, si "
                               "acaso, ofrécele guardar; se guarda cuando ÉL lo diga.")}
        # Lo que no impedía aplicarlo pero él tiene que saber: la marca cuando había pedido
        # genéricos, un alimento atípico a esa hora. Se aplica y SE DICE, en vez de no
        # aplicar y preguntar -- que es lo que le dejaba dando vueltas.
        avisos = [p["detalle"] for p in (revision.get("problemas") or [])
                  if not p.get("bloquea") and p.get("detalle")]
        if avisos:
            out["avisos"] = avisos
            out["instruccion"] = ("Ya está puesto. Dile de pasada lo que hay que decirle "
                                  "(está en `avisos`) y ofrécele cambiarlo si quiere, sin "
                                  "preguntar si lo aplicas: ya lo has aplicado. Y NO lo "
                                  "guardes ni avances de comida: eso lo decide él.")
        return out

    # ============================================================ 6. editar_comida
    async def editar_comida(self, operaciones: List[dict], forzar: bool = False) -> dict:
        """Todas las mutaciones de la comida actual en una llamada, en orden.
        Ops: {op:'añadir', texto|alimento_id, cantidad?, unidad?}
             {op:'quitar', nombre|alimento_id}
             {op:'ajustar', nombre, a?|mas?|por?, unidad?}  (fijar / sumar / multiplicar)
             {op:'vaciar'}   deja la comida a cero, con todo lo que tenga dentro
             {op:'vaciar_dia'}  vacia TODAS las comidas del dia y vuelve a la primera
        `forzar` solo para cambiar una comida que el cliente ya traía montada, y solo si te
        lo ha pedido él.

        VACIAR ES UNA OPERACIÓN, NO UNA LISTA DE «QUITAR» (13-08-2026). Francisco pidió
        «vacía la comida 1» y confirmó tres veces -- «vaciala», «si», «vacia la comida 1
        entera» -- y el asistente siguió pidiendo permiso en bucle sin vaciar nada. La
        protección de las comidas que el cliente ya traía montadas es correcta y se queda;
        lo que faltaba era la forma de obedecer cuando dice que sí: había que adivinar que
        se hacía mandando un `quitar` por cada alimento, y encima con `forzar`."""
        protegida = self._protegida(forzar)
        if protegida:
            return protegida
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
                elif tipo == "vaciar":
                    cuantos = len(((self.bot.state.get("comidas_completadas") or {})
                                   .get(self.bot.current_meal_key()) or {}).get("alimentos", []))
                    nombre = self.bot.clear_meal()
                    (hechos if nombre else fallos).append(
                        {"op": op, "detalle": (f"{nombre} vaciada ({cuantos} alimentos fuera)"
                                               if nombre else "no se pudo vaciar")})
                elif tipo == "vaciar_dia":
                    # «Vacía todas las comidas» en UNA operación (14-08-2026). Antes eran
                    # navegar + vaciar por cada comida: doce llamadas para un día de seis,
                    # el bucle chocaba con su tope de 8 y el cliente recibía la red de
                    # seguridad («no he conseguido cerrarlo») con el trabajo a medias
                    # hecho. Un encargo de una frase merece una herramienta de una frase.
                    vaciadas = []
                    for i in range(1, len(self.bot.state.get("meal_order") or []) + 1):
                        nombre = self.bot.clear_meal(i)
                        if nombre:
                            vaciadas.append(nombre)
                    self.bot.go_to_meal(1)
                    self._tirar_borradores_de_otras_comidas()
                    hechos.append({"op": op, "detalle": "vaciadas " + ", ".join(vaciadas)
                                   + "; estás en la primera comida"})
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

    def _tirar_borradores_de_otras_comidas(self) -> None:
        """Los menús propuestos para una comida no valen para la siguiente.

        En producción, con la Comida 1 ya aplicada y guardada, el asistente seguía
        preguntando «¿opción 1 o opción 2?» estando en el Intra: las opciones viejas
        seguían vivas en la sesión y cualquier «dale» del cliente las reactivaba. Al
        cambiar de comida se van, que es lo que pasa en la cabeza de cualquiera.
        """
        actual = self.bot.current_meal_key()
        borradores = self.bot.state.get("borradores") or {}
        for bid in [k for k, b in borradores.items() if b.get("meal_key") != actual]:
            borradores.pop(bid, None)

    def navegar(self, a) -> dict:
        """Ir a una comida ('2', 'post', 'intra', 'ultima', 'siguiente')."""
        ref = str(a).strip().lower()
        if ref == "siguiente":
            idx = min(self.bot.state["comida_actual"] + 1, len(self.bot.state["meal_order"]))
        else:
            ref = ref.replace("comida", "").strip()
            idx = self.bot.resolve_meal_ref(int(ref) if ref.isdigit() else ref)
        if idx and self.bot.go_to_meal(idx):
            self._tirar_borradores_de_otras_comidas()
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
        # Guardar avanza a la comida siguiente: los menús que se propusieron para la que se
        # acaba de cerrar ya no pintan nada (ver `_tirar_borradores_de_otras_comidas`).
        self._tirar_borradores_de_otras_comidas()
        out = {"ok": True, "dia_completo": self.bot.state.get("step") == "complete",
               "comida": self.ver_estado("comida")}
        if faltan:
            out["aviso"] = "la comida quedó sin cuadrar: faltan " + " y ".join(faltan)
        if pasan:
            out["aviso"] = (out.get("aviso", "") + ("; " if out.get("aviso") else "")
                            + "se pasa " + " y ".join(pasan))
        return out

    def guion_del_peri(self, variante: str = "principal") -> dict:
        """Lo que Jesus dice en el intra y en el post, literal. Se suelta TAL CUAL.

        No esta en el prompt a proposito: un modelo parafrasea, y esto es metodo, no
        conversacion. Ademas lleva 23 nombres de alimento del catalogo y en el prompt no
        caben (regla del 8 bis). Ver `core/guion_peri.py`.
        """
        from core.guion_peri import guion, alimentos_del_guion
        key = self.bot.current_meal_key()
        momento = {"Intra": "intra", "Post": "post"}.get(key)
        if not momento:
            return {"ok": False, "error": "esto solo aplica al intra y al post; "
                                          f"ahora estas en {self._nombre_comida_actual()}"}
        texto = guion(momento, variante)
        if not texto:
            return {"ok": False, "error": f"no hay guion de '{variante}' para el {momento}"}

        # EL GUION SE DICE UNA VEZ, Y DESPUES SE MONTA (13-08-2026).
        #
        # En produccion el intra se quedo en bucle: el cliente decia «me cuadra», «dale»,
        # «dale con eso», y el asistente volvia a soltar el mismo parrafo sin poner nada.
        # La herramienta decia «LLAMALA SIEMPRE al llegar al intra», y eso es lo que hacia:
        # llamarla siempre. Faltaba la otra mitad, que ademas el propio texto promete --
        # «eso te lo ajusto yo de forma automatica», «te digo exactamente la cantidad» --.
        #
        # Se lleva la cuenta en el estado, no en el prompt: a la segunda, la herramienta
        # deja de dar texto para repetir y dice lo unico que queda por hacer. Un bucle no
        # se arregla pidiendole al modelo que no lo haga.
        dichos = self.bot.state.setdefault("guion_peri_dicho", [])
        marca = f"{key}:{variante}"
        ya_dicho = marca in dichos
        if not ya_dicho:
            dichos.append(marca)
        falta = self.bot.get_remaining_macros()
        pendiente = [f"{falta[m]:.0f} g de {_MACRO_LBL[m]}"
                     for m in ("P", "H", "G") if falta[m] > 1]
        # CON QUE SE MONTA: lo que nombra ESTE guion, no lo que primero encaje.
        #
        # Decia «busca lo que nombra el metodo», y el modelo buscaba a ojo: en el intra
        # acabo montando amilopectina con aminoacidos despues de haber recomendado MAP con
        # ciclodextrina. Los dos entran en un intra, pero el cliente habia dicho «cuadra» a
        # OTRA cosa. Los terminos van aqui, junto al texto que los dice (`core/guion_peri`),
        # para que no se puedan desparejar.
        busca = alimentos_del_guion(momento, variante)
        siguiente = (
            "Si el cliente dice que si -- «vale», «dale», «me cuadra» --, NO vuelvas a "
            "escribir este texto: MONTA la comida ya con lo que acabas de recomendar. "
            + (f"Busca EXACTAMENTE estos terminos, uno por uno, con `buscar_alimentos`: "
               f"{', '.join(busca)}. " if busca else
               "Busca lo que nombra el metodo con `buscar_alimentos`. ")
            + "Metelos con `editar_comida`; las cantidades las pone el motor, que es lo "
              "que le has prometido. Si alguno no esta en su catalogo, dilo y ofrece la "
              "alternativa -- no lo cambies por otro en silencio."
            + (f" Ahora mismo faltan {_y(pendiente)}." if pendiente else ""))
        if ya_dicho:
            return {"ok": True, "momento": momento, "variante": variante,
                    "texto": None, "ya_se_lo_dijiste": True, "monta_con": busca,
                    "instruccion": "Ya le soltaste este guion en esta comida y te dijo que "
                                   "si. NO lo repitas: " + siguiente}
        return {"ok": True, "momento": momento, "variante": variante, "texto": texto,
                "monta_con": busca,
                "instruccion": "Escribe este texto TAL CUAL, sin resumirlo ni reescribirlo.",
                "y_despues": siguiente}

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

    # ============================================================= 9. recordar
    # Tope: son notas de trabajo, no un expediente. Con las últimas basta.
    MAX_NOTAS = 8

    def recordar(self, nota: str = None) -> dict:
        """Apunta algo que el cliente ha contado de sí mismo y va a hacer falta después.

        Al agente solo se le pasan los ÚLTIMOS 6 MENSAJES de la conversación. Con eso
        parecía que recordaba -- y lo usaba -- hasta que el dato salía de la ventana y
        contestaba lo contrario. Medido el 08-08: el cliente dice «en casa solo tengo
        huevos, avena y plátano», el asistente monta el desayuno «con tus huevos, avena y
        plátano», y seis mensajes más tarde responde *«no puedo ver lo que tienes en casa,
        no guardo esa info ni tu despensa»*. Las dos cosas en la misma conversación.

        Lo apuntado aquí viaja SIEMPRE en el contexto, no dependa de la ventana. Es memoria
        de la sesión, no del cliente: no se guarda en su perfil.
        """
        nota = (nota or "").strip()
        if not nota:
            return {"ok": False, "error": "no hay nada que apuntar"}
        notas = self.bot.state.setdefault("notas_cliente", [])
        if nota not in notas:
            notas.append(nota)
            del notas[:-self.MAX_NOTAS]
        return {"ok": True, "apuntado": nota, "notas": list(notas)}

    # ========================================================= 10. cambiar_de_dia
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
