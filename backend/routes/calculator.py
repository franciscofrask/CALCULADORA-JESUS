"""
Rutas del calculador de macros y búsqueda de alimentos.
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Response, Query
from bson import Binary
from datetime import datetime, timezone, timedelta, date
import math
import copy
import re
from typing import List, Dict, Any, Optional
import uuid

from core.database import db
from core.security import get_current_user
from models.common import FoodSuggestion, FoodSuggestionResponse

# Import calculator functions
from calma_engine import (
    que_macros_cuentan,
    calcular_macros_brutos,
    run_tests as calma_run_tests,
    parse_categories,
)
from calculator import buscar_alimentos as buscar_alimentos_async, sugerir_alimentos, get_food_config, calcular_cantidad_automatica, get_categoria_principal, get_all_foods_cached, normalize_text, cat_in_list
from calma_suggest import (
    ajustar_cantidad as ajustar_cantidad_calma,
    macros_at as macros_at_calma,
    diferencia_de_macros as diferencia_de_macros_calma,
    aplicar_regla_macros as aplicar_regla_macros_calma,
    food_in_cat as food_in_cat_calma,
    cantidad_minima as cantidad_minima_calma,
    macros_efectivos as macros_efectivos_calma,
)
from target_calculator import calcular_targets, targets_to_profile_macros, run_tests as target_run_tests
from macro_engine import calcular_macros_v2, ajustes_to_kwargs, multiplicadores_de
from core.quiz_store import guardar_quiz_respuestas
from core.series_cliente import anotar_peso, anotar_grasa
from core.topes_cantidad import tope_de_alimento
from macro_distribution import distribuir_macros as dist_macros, leer_macro, leer_peri
from redondeo_salida import redondear_cantidad, minimo_pesable

router = APIRouter(prefix="/calculator", tags=["calculator"])

# Alimentos favoritos OCULTOS (petición 2026-07-06): el orden favoritos-primero alteraba cómo
# se muestran los alimentos y no se quiere. La lógica se conserva; True para reactivar.
FOOD_FAVORITES_FIRST = False

# ── Filtro de preferencias / alimentos evitados (fuente única) ───────────────
# Mapea los IDs de categoría evitada (espejo del frontend PREFERENCE_CATEGORIES)
# a prefijos de categoría CALMA.
AVOIDABLE_PREFIXES = {
    'grasas_buenas': ['42'], 'grasas_todo': ['17'], 'aperitivos': ['38'],
    'arroces': ['21'], 'aves': ['2.2'], 'barritas': ['47'],
    'bebidas': ['19'], 'isotonicas': ['18.1'], 'beb_vegetales': ['24'],
    'bolleria': ['31'], 'cacao': ['37'], 'casqueria': ['40'],
    'cerdo': ['2.4'], 'cereales': ['7'], 'chocolates': ['34'],
    'cocina_esp': ['39'], 'comida_rapida': ['49'], 'embutidos': ['2.1'],
    'fruta': ['11'], 'helados': ['44'], 'huevos': ['1'],
    'lacteos': ['5'], 'legumbres': ['10'], 'carnes_blancas': ['2.6'],
    'carnes_rojas': ['2.7'], 'panes': ['8'], 'pasta': ['22'],
    'pescados': ['3'], 'pizza': ['32'], 'proteina_polvo': ['4', '29', '30'],
    'proteina_vegetal': ['28'], 'salsas': ['16'], 'sopas': ['48'],
    'superalimentos': ['51'], 'tuberculos': ['9'], 'vacuno': ['2.3'],
    'verduras': ['13'],
}


def build_avoided_filter(profile):
    """Devuelve (avoided_prefixes:set, avoided_keywords:list) desde el perfil."""
    avoided_categories = profile.get("avoided_categories", []) if profile else []
    avoided_keywords = [kw.lower() for kw in (profile.get("avoided_keywords", []) if profile else [])]
    avoided_prefixes = set()
    for cat_id in avoided_categories:
        for prefix in AVOIDABLE_PREFIXES.get(cat_id, []):
            avoided_prefixes.add(prefix)
    return avoided_prefixes, avoided_keywords


def food_is_avoided(alimento, avoided_prefixes, avoided_keywords):
    """True si el alimento debe evitarse por keyword o por categoría."""
    nombre = (alimento.get("nombre", "") or "").lower()
    for kw in avoided_keywords:
        if kw in nombre:
            return True
    if not avoided_prefixes:
        return False
    for food_cat in parse_categories(alimento.get("categorias", [])):
        for prefix in avoided_prefixes:
            if food_cat == prefix or food_cat.startswith(prefix + "."):
                return True
    return False

# ── Preparation filter helpers (mirrors Calma group-home-utils.js) ──────────
#
# Calma's $ function: new RegExp(`^((${code})[.]\d|(${code})$)`).test(token)
# → matches token if it EQUALS code exactly OR starts with "code.digit"
# → effectively a prefix match: "4" matches "4", "4.1", "4.1.1", "4.2", etc.

def _has_any_exact_cat(alimento, cat_codes: set) -> bool:
    """Mirror Calma's o(e, list) + $ function: prefix-aware category matching.
    'code' matches a token if token == code OR token starts with code+'.'
    """
    cats = str(alimento.get("categorias", "") or "")
    for t in cats.split("|"):
        t = t.strip()
        for code in cat_codes:
            if t == code or t.startswith(code + "."):
                return True
    return False

def _has_token(alimento, tag: str) -> bool:
    tag_up = tag.upper()
    cats = str(alimento.get("categorias", "") or "")
    raw_tags = alimento.get("tags", "") or ""
    if isinstance(raw_tags, list):
        tag_tokens = {str(t).strip().upper() for t in raw_tags}
    else:
        tag_tokens = {t.strip().upper() for t in str(raw_tags).split("|")}
    cat_tokens = {t.strip().upper() for t in cats.split("|")}
    return tag_up in cat_tokens or tag_up in tag_tokens

_LAT_CATS = {"2.2.8", "2.3.8", "2.4.8", "3.8", "3.9.8", "10.1.8", "11.8", "13.8"}
_FRE_CATS = {"FRE", "1.2.1", "2.2.1", "2.3.1", "2.4.1", "3.1", "3.9.1", "11.1", "13.1"}
_CGE_CATS = {"CGE", "2.2.4", "2.3.4", "2.4.4", "3.4", "3.9.4", "10.1.4", "11.4", "13.4"}
_PRE_CATS = {"PRE", "2.2.2", "2.3.2", "2.4.2", "3.2", "3.9.2", "11.5", "17.9.2"}
_YCO_CATS = {"YCO", "2.1", "2.2.3", "2.3.3", "2.4.3", "3.3", "3.9.3", "13.2", "17.9.3", "39"}

def _prep_lat(a):
    n = (a.get("nombre") or "").lower()
    return " lata" in n or "conserva" in n or _has_any_exact_cat(a, _LAT_CATS)

def _prep_fre(a):
    return _has_any_exact_cat(a, _FRE_CATS)

def _prep_cge(a):
    n = (a.get("nombre") or "").lower()
    return _has_any_exact_cat(a, _CGE_CATS) or "congelad" in n or "helad" in n

def _prep_pre(a):
    return _has_any_exact_cat(a, _PRE_CATS)

def _prep_yco(a):
    return _has_any_exact_cat(a, _YCO_CATS)

def _prep_ahu(a):
    n = (a.get("nombre") or "").lower()
    return _has_any_exact_cat(a, {"AHU", "3.7"}) or "ahumad" in n

def _prep_ya(a):
    # Original: o(e, ["YA", "2.1", "4", "11.5"]) || j.test(e)
    # "4" prefix matches all protein powders (4, 4.1, 4.1.1, etc.) → YA
    return _has_any_exact_cat(a, {"YA", "2.1", "4", "11.5"}) or _prep_ahu(a)

_PREP_TESTS = {
    "LAT": _prep_lat,
    "FRE": _prep_fre,
    "CGE": _prep_cge,
    "PRE": _prep_pre,
    "YCO": _prep_yco,
    "AHU": _prep_ahu,
    "YA":  _prep_ya,
    "HAM": lambda a: _has_token(a, "HAM"),
    "SNA": lambda a: _has_token(a, "SNA"),
    "SGL": lambda a: _has_token(a, "SGL"),
    "GEN": lambda a: not a.get("url"),
    "PRO": lambda a: _has_token(a, "PRO"),
    # Original: P(nombre,["polvo","harina"]) || o(e,["POL","4","7.1.2.6","16.5","18.3","27"]) || P(nombre,["crema","arroz"],AND)
    "POL": lambda a: (
        _has_any_exact_cat(a, {"POL", "4", "7.1.2.6", "16.5", "18.3", "27"}) or
        any(w in (a.get("nombre") or "").lower() for w in ("polvo", "harina")) or
        (("crema" in (a.get("nombre") or "").lower()) and ("arroz" in (a.get("nombre") or "").lower()))
    ),
    "MIN": lambda a: _has_token(a, "MIN"),
    "UNI": lambda a: bool(a.get("unidades") or a.get("por_unidad")),
}

_PREPS_ORDER = ["GEN", "PRO", "FRE", "CGE", "AHU", "LAT", "POL", "PRE", "HAM", "SNA", "MIN", "YCO", "UNI", "YA", "SGL"]

# Calma T.marcasRecomendadas: foods whose nombre matches get the PROMOCIONADO badge + a -0.5
# prioridad float. Calma appends "| PRO" to them at load (except "Native Isolate"); our DB has no
# PRO tag, so we detect by name (and honor an explicit PRO token if present).
_MARCAS_RECOMENDADAS = ("fullgas", "fitness burger", "my fitness meals")

# EL ORDEN DEL INTRA, QUE ES METODO Y NO GUSTO (Francisco, 25-08).
#
# Dentro del bloque de hidratos rapidos (categoria 18.3) las cuatro opciones tienen
# practicamente los mismos macros -- ciclodextrina H95, dextrosa H100, amilopectina,
# palatinosa --, asi que el orden por encaje las deja en cualquier sitio y la ciclodextrina
# salia tercera. Jesus la nombra por escrito como la primera opcion y la dextrosa como la
# alternativa barata (core/guion_peri.py: INTRA y INTRA_OTRO_HIDRATO), asi que ese orden se
# dice aqui en vez de dejarlo al azar de los decimales.
#
# El ajuste es pequeño a proposito (menos de 0,5) para que NUNCA saque a un alimento de su
# bloque de categoria: solo lo coloca dentro del suyo.
_FAVORITOS_DEL_INTRA = ("ciclodextrina", "dextrosa")


def _favorito_del_metodo(food) -> float:
    """Cuanto adelanta a un alimento por ser el que recomienda el metodo. 0 si no lo es."""
    n = (food.get("nombre") or "").lower()
    for idx, palabra in enumerate(_FAVORITOS_DEL_INTRA):
        if palabra in n:
            return 0.3 - idx * 0.1
    return 0.0

def _es_promocionado(food) -> bool:
    cats = {t.strip().upper() for t in str(food.get("categorias", "") or "").split("|")}
    if "PRO" in cats:
        return True
    n = (food.get("nombre") or "").lower()
    return any(m in n for m in _MARCAS_RECOMENDADAS) and "native isolate" not in n

# ==================== FOODS ====================

@router.get("/foods")
async def get_foods(
    search: Optional[str] = None, 
    category: Optional[str] = None, 
    limit: int = 100, 
    user = Depends(get_current_user)
):
    """Obtiene la lista de alimentos desde MongoDB con filtros opcionales."""
    query = {}
    
    if search:
        query["nombre"] = {"$regex": search, "$options": "i"}
    
    if category:
        query["categorias"] = {"$regex": category}
    
    foods_cursor = db.foods.find(query, {"_id": 0}).limit(limit)
    foods = await foods_cursor.to_list(limit)
    return foods

@router.get("/foods/count")
async def get_foods_count(user = Depends(get_current_user)):
    """Retorna el conteo total de alimentos."""
    count = await db.foods.count_documents({})
    return {"total": count}

def _n1(x: float) -> str:
    """Calma C(): número con hasta 1 decimal, sin .0 sobrante.
    Redondeo half-up (como toLocaleString JS), no el banker's de round()."""
    r = math.floor(float(x or 0) * 10 + 0.5) / 10
    return str(int(r)) if r == int(r) else str(r)

def _fmt_macros(m: dict) -> str:
    """Calma ae()/Q(): 'Xg proteínas / Yg hidratos / Zg grasas' (solo > 0)."""
    parts = []
    for k, label in (("proteinas", "proteínas"), ("hidratos", "hidratos"), ("grasas", "grasas")):
        v = m.get(k, 0)
        if v:
            parts.append(f"{_n1(v)}g {label}")
    return " / ".join(parts)

#: Los dos bloques que se calibran, con sus tramos y el nombre con el que se los nombra al
#: cliente. Los gramos son los de `calma_engine` y los mismos que aplica `calibracion_dia`.
_TRAMOS_CALIBRACION = {
    "fruto_seco": {"familia": "frutos secos y semillas", "tramos": [20, 40]},
    "cereal_pan": {"familia": "cereales y panes, juntos", "tramos": [50, 100]},
}


def _como_cuenta_su_proteina(food: dict) -> tuple:
    """Las tres cosas que hay que saber de un alimento, preguntadas UNA vez.

    Se pregunta a la vez porque cada respuesta cuesta recorrer las categorías del alimento y
    el listado son 3.200 fichas: pedirlas por separado ponía cuatro pasadas por alimento y
    la pantalla de Alimentos pasó de 1,4 s a 2,0 s, lo justo para despertar al test de los
    tres segundos. Con una sola clasificación vuelve a lo de antes.

    Devuelve (bloque, cuenta_alguna_vez, crece_con_el_dia).
    """
    from calibracion_dia import (clasificar_bloque, la_proteina_llega_al_tercio,
                                 cuenta_siempre_al_100)
    bloque = clasificar_bloque(food)
    if bloque is None:
        return None, True, False
    llega = la_proteina_llega_al_tercio(food)
    crece = llega and not cuenta_siempre_al_100(food)
    return bloque, llega, crece


def _calibracion_del_alimento(bloque: Optional[str], crece: bool) -> Optional[dict]:
    """Si a este alimento le crece la proteína con lo que lleves comido en el día.

    Devuelve el bloque y sus tramos, o None si no depende de la cantidad. Quedan fuera los
    dos extremos: el fruto seco que no pasa la puerta del tercio -- las nueces, el 23 % --,
    porque su proteína no cuenta nunca y enseñarle tramos sería prometerle algo que no va a
    llegar (punto 133); y el pan proteico, porque ya le cuenta entera desde el primer gramo.
    Ver `la_proteina_crece_con_el_dia`.
    """
    if not bloque or not crece:
        return None
    cfg = _TRAMOS_CALIBRACION.get(bloque)
    if not cfg:
        return None
    return {"bloque": bloque, "familia": cfg["familia"], "tramos": cfg["tramos"]}


def _proteina_que_no_cuenta_nunca(bloque, llega_al_tercio: bool) -> bool:
    """Si su proteína está condenada de antemano por la puerta del tercio.

    EL LISTADO PROMETÍA PROTEÍNA QUE EL DÍA NO DA. Los macros de esta pantalla salían de
    `aplicar_regla_macros` (la regla de categoría de Calma) y esa regla no conoce la puerta
    del tercio, que vive en `calibracion_dia`. Resultado: **39 panes y cereales del catálogo**
    -- el pan de centeno 55 %, la media hogaza de avena, los fibra sticks -- salían aquí con
    su proteína en la etiqueta verde y con la frase «Te cuenta proteína y hidratos», y al
    ponerlos en una comida aportaban 0 de proteína, comiera uno lo que comiera.

    Es la misma mentira que arregla el punto 139, del revés: allí la lista NEGABA una
    proteína que sí llega comiendo más, aquí la PROMETE cuando no va a llegar nunca. En los
    frutos secos no pasaba (la regla de categoría ya se los zeraba); es cosa de los cereales
    y panes, donde la regla de Calma los deja pasar y la puerta del tercio los para después.
    """
    return bool(bloque) and not llega_al_tercio


def _lo_que_depende_del_tramo(bloque, crece: bool) -> tuple:
    """Los macros de este alimento que la lista NO puede dar por contados.

    DOS VARAS PARA MEDIR LA MISMA PROTEÍNA (punto 136 del 26-08). Jesús lo encontró en dos
    cacahuetes: el natural (26 P / 52 G) dice «ni su proteína ni sus hidratos te cuentan» y
    el de Hacendado (24,1 / 45,1) dice «te cuenta proteína y grasa», siendo casi el mismo
    alimento, de la misma categoría y pasando los dos la puerta del tercio.

    No son datos mal puestos: **son dos reglas distintas midiendo lo mismo**. La de Calma
    zera la proteína de un fruto seco cuando `P·2 <= G` (la mitad, `calma_suggest:181`) y la
    calibración del día la deja pasar con `P > G/3` (el tercio, la spec del 07-08). Los tres
    cacahuetes caen justo en medio de las dos: 26·2 = 52 ≤ 52 zera, 24,1·2 = 48,2 > 45,1 no
    zera, 24·2 = 48 ≤ 50,4 zera. De ahí que uno diga una cosa y el de al lado la contraria.

    La vara buena es la del tercio: la calibración progresiva SUSTITUYÓ al ajuste legado de
    Calma en estos dos bloques (ver `_base_regla`), y es la que decide lo que el cliente ve
    en sus macros. Pero entonces esa proteína **depende del tramo del día**, y la lista no
    sabe cuánto vas a comer: no puede ponerla en «Macros del método» como si contara siempre.

    Así que en los que llevan punto no sale, y lo cuentan el punto y los tramos. Es el mismo
    criterio del punto 139 llevado del texto al número: 32 alimentos enseñaban una proteína
    que con menos de 20 g vale 0, y 30 idénticos ya la callaban. Ahora los 62 dicen lo mismo.

    En frutos secos alcanza también a los hidratos (7 alimentos), que van por el mismo tramo.
    """
    if not crece:
        return ()
    return ("proteinas", "hidratos") if bloque == "fruto_seco" else ("proteinas",)


@router.get("/foods-listado")
async def get_foods_listado(
    limit: Optional[int] = Query(None, ge=0),
    offset: int = Query(0, ge=0),
    user = Depends(get_current_user),
):
    """Lista completa de alimentos enriquecida para el Buscador (réplica de Calma
    `getTodosLosAlimentos`): macros efectivos tras la regla, info de etiqueta con los
    originales, cantidad mínima y si 'siempre puede ser sugerido'."""
    foods = await get_all_foods_cached(db)
    # Tanda opcional (P39, doc 23-08). Sin parámetros se devuelve el catálogo entero,
    # como siempre, para no romper a quien ya llamaba así; con limit/offset solo el
    # tramo pedido, que es lo que evita mandar los tres mil de golpe. Se recorta antes
    # de enriquecer para no calcular macros de fichas que no van a viajar.
    if offset:
        foods = foods[offset:]
    if limit is not None:
        foods = foods[:limit]
    out = []
    for f in foods:
        orig = {"proteinas": float(f.get("proteinas") or 0),
                "hidratos": float(f.get("hidratos") or 0),
                "grasas": float(f.get("grasas") or 0)}
        # Las tres preguntas de la calibración, en una sola pasada por sus categorías: son
        # 3.200 fichas y repetirlas se nota en la pantalla (ver `_como_cuenta_su_proteina`).
        bloque, llega_al_tercio, crece_con_el_dia = _como_cuenta_su_proteina(f)
        aplicar_regla_macros_calma(f)  # zera macros que no cuentan (in place) + fija _ajuste
        eff = {"proteinas": float(f.get("proteinas") or 0),
               "hidratos": float(f.get("hidratos") or 0),
               "grasas": float(f.get("grasas") or 0)}
        # La regla de categoría no conoce la puerta del tercio: ver `_proteina_que_no_cuenta_nunca`.
        # Se toca la copia que viaja, no `f`, para no mover `cantidad_minima` ni la sugerencia,
        # que son del sugeridor y tienen su propio filtro.
        if _proteina_que_no_cuenta_nunca(bloque, llega_al_tercio):
            eff["proteinas"] = 0.0
        # Y lo que sólo llega si comes bastante tampoco se cuenta aquí como fijo, que es lo
        # que hacía decir cosas distintas a dos cacahuetes iguales: ver `_lo_que_depende_del_tramo`.
        for macro in _lo_que_depende_del_tramo(bloque, crece_con_el_dia):
            eff[macro] = 0.0
        calibracion = _calibracion_del_alimento(bloque, crece_con_el_dia)
        cm = cantidad_minima_calma(f)
        out.append({
            "id": f.get("id"),
            "nombre": f.get("nombre"),
            "categorias": f.get("categorias"),
            "url": f.get("url"),
            "racion": f.get("racion"),
            "unidades": bool(f.get("unidades")),
            "proteinas": eff["proteinas"],
            "hidratos": eff["hidratos"],
            "grasas": eff["grasas"],
            "tiene_macros": any(v > 0 for v in eff.values()),
            # «MACROS REALES», NO «EN LA ETIQUETA PONE» (punto 142). Un generico no tiene
            # etiqueta: «Almendras» no es el bote de nadie, y esos 23 / 4,8 / 53,1 salen de
            # tabla de composicion. El nombre nuevo vale para los dos casos -- en una marca
            # son los de su envase, en un generico los de tabla -- y ademas dice QUE es, que
            # es lo que faltaba: el otro numero pasa a llamarse «macros del metodo».
            "macros_reales": {"P": orig["proteinas"], "H": orig["hidratos"], "G": orig["grasas"]}
                             if eff != orig else None,
            "cantidad_minima": cm,
            # AQUI VIAJABA `sugerencia`, una frase por alimento: «Necesita 9g proteínas / 5.5g
            # hidratos / 5.5g grasas para ser sugerido». La pantalla dejo de pintarla el 26-08
            # (la sustituyo `que_te_cuenta`) y desde el 27-08 lo que dice lo dicen `desde` y
            # `necesitas`, asi que era texto muerto: 224 KB de los 1.644 que pesa el catalogo.
            # Con 3.219 fichas y el tope de tres segundos de Jesus, eso no es limpieza, es
            # margen. Si alguna vez hace falta la frase, se arma con los dos campos de abajo.
            # LA CUARTA LINEA DEL ALIMENTO: «Desde 5 g · necesitas 2,7 G» (puntos 148 a 150).
            # Van juntas porque separadas no dicen nada: 5 g solo es un numero y 2,7 G solo es
            # otro. El minimo se escribe como se dice (`_desde_cuanto`) y lo que aporta con la
            # letra de cada macro, igual que en el resto de la pantalla.
            # Cuando no cuenta nada, `necesitas` viaja vacio y la pantalla escribe «siempre
            # cabe»: el minimo existe -- no se meten 10 g de lechuga -- pero no hay nada que
            # comprobar (en Calma, «Siempre puede ser sugerido»).
            "desde": _desde_cuanto(f, cm),
            # Los macros que aporta esa cantidad minima, en crudo: la pantalla los escribe con
            # su letra y su coma decimal (lib/numeros), igual que hace con `macros_reales`.
            # Vacio -- no cero -- cuando no aporta ninguno, que es lo que distingue «necesitas
            # 2,7 G» de «siempre cabe».
            "necesitas": _necesitas(f, eff, cm),
            # Para escribir «por 100 ml» en vez de «por 100 g» y «Bebe» en vez de «Come».
            "es_liquido": _es_liquido(f),
            # QUE LE CUENTA DE ESTE ALIMENTO, EN CRISTIANO.
            #
            # Debajo de cada alimento salia «Necesita 9g proteinas / 5.5g hidratos / 5.5g
            # grasas para ser sugerido»: es el filtro del tercio dicho al reves y en lenguaje
            # de programador. Y esta es justo la pantalla donde alguien viene a entender por
            # que la app le cuenta unas cosas y otras no, asi que ahi se perdia la ocasion de
            # explicar el metodo (Jesus, 11-08).
            #
            # El dato ya estaba: `orig` son los macros de la etiqueta y `eff` los que cuentan
            # despues de aplicar la regla. Lo que sobraba era traducirlo.
            # SI SU PROTEINA CRECE CON LA CANTIDAD DEL DIA (puntos 138 a 140). De aqui sale
            # el punto que lo distingue en la lista -- «hoy los tres se ven exactamente
            # igual» -- y los tramos que se enseñan al abrirlo. No basta con ser de la
            # familia: hay que pasar ademas la puerta del tercio, o la proteina no cuenta
            # nunca y no hay tramo ninguno que enseñar.
            "calibracion": calibracion,
            "que_te_cuenta": _que_te_cuenta(orig, eff, se_calibra=bool(calibracion)),
        })
    return out


#: Cada macro con su articulo, tal y como se lo decimos al cliente. En singular los tres:
#: «el hidrato», no «los hidratos» (punto 147 del 27-08, y es como esta escrito en su
#: documento). Una frase mal concordada en la pantalla que explica el metodo se lee como un
#: descuido.
_NOMBRE_MACRO = {"proteinas": "la proteína", "hidratos": "el hidrato", "grasas": "la grasa"}

_LOS_TRES = ("proteinas", "hidratos", "grasas")


def _que_te_cuenta(orig: dict, eff: dict, se_calibra: bool = False) -> str:
    """Una frase que dice que macros de este alimento cuentan para sus objetivos.

    LAS CUATRO FORMAS (punto 147 del 27-08). Se comparan los macros que CUENTAN con los que
    el alimento TIENE, no con los tres siempre:

      - «Te cuenta todo»            le cuentan todos los que lleva. El huevo entra aqui:
                                    tiene proteina y grasa, no tiene hidratos, y las dos
                                    cuentan. Antes esto decia «Te cuentan los tres», que del
                                    huevo es sencillamente falso.
      - «Te cuenta solo la grasa»   lleva mas de uno y solo le cuenta ese.
      - «Te cuenta la proteína y la grasa»   lleva los tres y le cuentan dos.
      - «No te cuenta nada»         las verduras libres y los zero.

    `se_calibra`: si a este alimento le crece la proteina con la cantidad del dia (punto 139
    del 26-08). En esos CAE EL «SOLO»: «Te cuenta la grasa», sin mas. En las almendras la
    proteina si cuenta a partir de 20 g, asi que decir «solo» seria mentira medio dia. En las
    nueces, que no cuentan nunca, si va. Lo que depende de la cantidad lo dice el punto y, al
    abrir el alimento, los tramos.

    Y con esto desaparece la coletilla «Su proteína no te cuenta»: el «solo» ya lo dice, y es
    una linea menos por alimento.
    """
    tiene = [k for k in _LOS_TRES if (orig.get(k) or 0) > 0]
    cuentan = [k for k in tiene if (eff.get(k) or 0) > 0]

    if not cuentan:
        return "No te cuenta nada"
    if len(cuentan) == len(tiene):
        return "Te cuenta todo"
    if len(cuentan) == 1:
        solo = "" if se_calibra else "solo "
        return f"Te cuenta {solo}{_NOMBRE_MACRO[cuentan[0]]}"
    return "Te cuenta " + _lista([_NOMBRE_MACRO[k] for k in cuentan])


#: LO QUE SE BEBE, PARA QUE EL MINIMO VAYA EN MILILITROS Y LA FRASE DIGA «BEBE».
#: La maqueta del 27-08 escribe la Coca-Cola Zero como «por 100 ml ... Desde 100 ml · siempre
#: cabe» y «Bebe lo que quieras», y la lechuga como «por 100 g» y «Come lo que quieras». En la
#: base no hay ningun campo que diga si algo es liquido, asi que sale de la categoria.
#: Quedan FUERA a proposito los polvos que viven en ramas de bebidas: los hidratos para
#: entrenar (18.3) y el cafe en polvo (19.3.3) se pesan, no se miden.
_CATEGORIAS_LIQUIDAS = ("5.1", "6.1", "11.5", "18.1", "19.1", "19.2", "19.3.1", "19.3.2", "24")


def _es_liquido(food: dict) -> bool:
    return any(food_in_cat_calma(food, c) for c in _CATEGORIAS_LIQUIDAS)


#: EL NOMBRE DE LA UNIDAD, PARA LOS QUE EMPIEZAN EN MEDIA (punto 149 del 27-08).
#:
#: «Desde media hamburguesa · desde media tarrina · desde 1 unidad»: en los tres ejemplos que
#: da Jesus el nombre aparece SOLO donde dice «media». El huevo, que va por unidad entera, es
#: «desde 1 unidad» y no «desde 1 huevo». Asi que la unidad entera no necesita nombre y la
#: media si, porque «media unidad» no se entiende.
#:
#: Son 142 fichas de 3.219 las que empiezan en media unidad, y esta tabla las cubre casi
#: todas. El orden IMPORTA: «Pan de hamburguesa 2 rebanadas» lleva la palabra «hamburguesa»
#: dentro y no es una hamburguesa, asi que el pan va primero.
#:
#: Se resuelve por regla y no por un campo en la ficha porque el catalogo crece todas las
#: semanas (el viernes a las 10, punto 168) y sobre todo con hamburguesas: una regla coge las
#: nuevas sola, y un campo habria que rellenarlo a mano cada vez.
_NOMBRE_DE_LA_UNIDAD = (
    ("pan de hamburguesa", "medio pan"),
    ("hamburguesa", "media hamburguesa"),
    ("tarrina", "media tarrina"),
    ("bagel", "medio bagel"),
    ("bizcocho", "medio bizcocho"),
    ("brazo de gitano", "medio brazo"),
    ("donut", "medio donut"),
    ("ensalada", "media ensalada"),
    ("bolsita", "media bolsita"),
    ("lata", "media lata"),
    ("yogur", "medio yogur"),
    ("manzana", "media manzana"),
    ("naranja", "media naranja"),
    ("mandarina", "media mandarina"),
    ("ciruela", "media ciruela"),
    ("nectarina", "media nectarina"),
    ("pera", "media pera"),
    ("platano", "medio plátano"),
    ("melocoton", "medio melocotón"),
    ("kiwi", "medio kiwi"),
    ("caqui", "medio caqui"),
    ("kaki", "medio kaki"),
)


def _media_unidad_de(nombre: str) -> str:
    """«media hamburguesa», «media tarrina»... y «media unidad» si no se reconoce."""
    n = normalize_text(nombre or "")
    for palabra, texto in _NOMBRE_DE_LA_UNIDAD:
        if palabra in n:
            return texto
    return "media unidad"


def _necesitas(food: dict, eff: dict, minimo: float) -> Optional[dict]:
    """Lo que TE CUENTA la cantidad minima, o None si no te cuenta nada.

    De los macros EFECTIVOS, no de los de la etiqueta. En las almendras la maqueta escribe
    «Desde 5 g · necesitas 2,7 G» y nada mas: la proteina y los hidratos que lleva no salen,
    porque a esa cantidad no cuentan. Con los crudos saldria «2,3 P · 0,5 H · 2,7 G», que es
    justo lo que el punto 147 quita de la linea de arriba y volveria a colarse aqui.

    `eff` ya trae aplicadas las tres reglas (la de categoria, la puerta del tercio y el tramo
    de la calibracion), asi que solo hay que escalarlo: `minimo` viene en unidades si el
    alimento va por unidades y en gramos si va a granel, y los macros estan en la misma
    referencia (por unidad o por 100 g).

    Sale en numeros, como `macros_reales`, para que la pantalla los escriba con su letra y su
    coma decimal: el punto y la coma son cosa de como se escribe en español y eso lo resuelve
    `lib/numeros` en el front.
    """
    escala = float(minimo) if food.get("unidades") else float(minimo) / 100.0
    fuera = {k: float(eff.get(n) or 0) * escala
             for k, n in (("P", "proteinas"), ("H", "hidratos"), ("G", "grasas"))}
    return fuera if any(v > 0 for v in fuera.values()) else None


def _con_coma(x: float) -> str:
    """El numero como se escribe en español: «5» y «12,5», nunca «12.5»."""
    return _n1(x).replace(".", ",")


def _desde_cuanto(food: dict, minimo: float) -> str:
    """A partir de cuanto se puede ofrecer este alimento, dicho como se le dice al cliente.

    LA CANTIDAD MINIMA ESTA EN CALMA Y FALTABA EN LA APP (punto 148 del 27-08). Es del metodo
    igual que los macros: la app solo sugiere un alimento si su minimo cabe en lo que queda
    por cubrir, sin pasarse de ninguno. Si te quedan 5 g de proteina y 3 de grasa, el salmon
    no se sugiere -- su minimo son 50 g y eso son 10 de proteina -- y el aceite si.

    `minimo` viene del motor en SUS unidades: piezas si el alimento va por unidades, gramos
    si va a granel (`calma_suggest.cantidad_minima`).
    """
    if food.get("unidades"):
        if minimo <= 0.75:
            return _media_unidad_de(food.get("nombre"))
        return "1 unidad" if minimo == 1 else f"{_con_coma(minimo)} unidades"
    return f"{_con_coma(minimo)} {'ml' if _es_liquido(food) else 'g'}"


def _lista(partes: list) -> str:
    if len(partes) <= 1:
        return partes[0] if partes else ""
    return ", ".join(partes[:-1]) + " y " + partes[-1]

# ==================== CATEGORIES ====================

@router.get("/categories")
async def get_food_categories(user = Depends(get_current_user)):
    """Obtiene todas las categorías de alimentos."""
    categories_cursor = db.food_categories.find({}, {"_id": 0})
    categories = await categories_cursor.to_list(500)
    return categories

@router.get("/categories/count")
async def get_categories_count(user = Depends(get_current_user)):
    """Retorna el conteo total de categorías."""
    count = await db.food_categories.count_documents({})
    return {"total": count}

# ==================== MEAL CALCULATIONS ====================

@router.post("/meal")
async def calculate_meal(foods: List[Dict[str, Any]], user = Depends(get_current_user)):
    """Calcula macros totales de una comida."""
    total = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}
    
    for item in foods:
        quantity = item.get("quantity", 100) / 100
        total["calories"] += item.get("calories", 0) * quantity
        total["protein"] += item.get("protein", 0) * quantity
        total["carbs"] += item.get("carbs", 0) * quantity
        total["fat"] += item.get("fat", 0) * quantity
    
    return {k: round(v, 1) for k, v in total.items()}

# ==================== CALMA ENGINE ====================

def _minimo_en_gramos(alimento: dict) -> float:
    """La cantidad mínima del alimento, en gramos.

    El motor la da en las unidades con las que trabaja (unidades si el alimento va por
    unidades, gramos si va a granel), y de cara al cliente todo son gramos.
    """
    minimo = cantidad_minima_calma(alimento)
    if alimento.get("unidades"):
        minimo = minimo * (float(alimento.get("racion") or 100) or 100.0)
    return round(float(minimo), 1)


def _redondear_para_el_cliente(alimento: dict, cantidad_g: float) -> float:
    """La cantidad en gramos, redondeada a la baja al múltiplo que le toca (redondeo_salida)."""
    return redondear_cantidad(alimento, cantidad_g, minimo_g=_minimo_en_gramos(alimento))


def _efectivos_calma(alimento: dict, cantidad_g: float,
                     dia_cp: Optional[float] = None, dia_fs: Optional[float] = None):
    """Macros efectivos/brutos at `cantidad_g` using the SAME engine as the suggestion/
    add path (calma_suggest), so editing a food's quantity stays consistent with how it
    was first added. The legacy calcular_macros_efectivos divided granel macros by `racion`
    instead of 100 (broke any food with racion != 100, e.g. prepared dishes), and used a
    different regla - switching quantity replaced correct macros with garbage. Here:
      - apply aplicar_regla_macros (regla 25% + _ajuste) on a copy,
      - granel: scale by cantidad_g/100; unidades: macros are per-unit, scale by units
        (cantidad_g / racion), which macros_at expects.
    Returns ({P,H,G} efectivos, {P,H,G} brutos, {P,H,G} bool que_cuenta)."""
    es_unidad = bool(alimento.get("unidades"))
    racion = float(alimento.get("racion") or 100) or 100.0
    # CON EL DÍA, SI SE LO DAN (punto 135). `macros_efectivos_calma` es el motor de antes de
    # que existiera la calibración, y por eso la ventana de montar comidas decía «P 0» de
    # unas almendras que al guardar contaban 2,9. Ahora, cuando quien llama sabe lo que lleva
    # el día, se calcula como lo calculará la comida. Fuera de las dos familias calibradas
    # devuelve exactamente lo mismo. Ver `macros_al_anadirlo`.
    #
    # Sin contexto del día se deja el motor de siempre A PROPÓSITO, y no vale poner ceros:
    # «día a cero» es un contexto real (tramo 0) y no es lo mismo que «esto no es un día».
    # Por aquí pasan también las COMIDAS SUELTAS -- la biblioteca de menús, `/macros-comida`
    # --, donde la calibración no aplica porque no hay día que acumular.
    if dia_cp is None and dia_fs is None:
        m = macros_efectivos_calma(alimento, cantidad_g)
    else:
        from calibracion_dia import macros_al_anadirlo
        m = macros_al_anadirlo(alimento, cantidad_g, dia_cp or 0.0, dia_fs or 0.0)
    efectivos = {"P": round(m["P"], 1), "H": round(m["H"], 1), "G": round(m["G"], 1)}
    scale = (cantidad_g / racion) if es_unidad else (cantidad_g / 100.0)
    brutos = {
        "P": round(float(alimento.get("proteinas") or 0) * scale, 1),
        "H": round(float(alimento.get("hidratos") or 0) * scale, 1),
        "G": round(float(alimento.get("grasas") or 0) * scale, 1),
    }
    cuenta = {"P": efectivos["P"] > 0, "H": efectivos["H"] > 0, "G": efectivos["G"] > 0}
    return efectivos, brutos, cuenta


@router.post("/macros-efectivos")
async def get_macros_efectivos(data: dict, user = Depends(get_current_user)):
    """Calcula los macros efectivos de un alimento."""
    alimento_id = data.get("alimento_id")
    cantidad_g = data.get("cantidad_g", 100)

    alimento = await db.foods.find_one({"id": alimento_id}, {"_id": 0})
    if not alimento:
        raise HTTPException(status_code=404, detail="Alimento no encontrado")

    # Sólo si quien llama dice lo que lleva el día; si no, motor de siempre (comida suelta).
    tiene_dia = data.get("dia_cp") is not None or data.get("dia_fs") is not None
    efectivos, brutos, cuenta = _efectivos_calma(
        alimento, cantidad_g,
        dia_cp=float(data.get("dia_cp") or 0) if tiene_dia else None,
        dia_fs=float(data.get("dia_fs") or 0) if tiene_dia else None)

    return {
        "alimento": {
            "id": alimento.get("id"),
            "nombre": alimento.get("nombre"),
            "categorias": alimento.get("categorias"),
            "racion": alimento.get("racion")
        },
        "cantidad_g": cantidad_g,
        "efectivos": efectivos,
        "brutos": brutos,
        "que_cuenta": cuenta,
        # La familia calibrada a la que pertenece (o null), para que quien lo añade sepa que
        # tiene que contarlo en el acumulado del día de la siguiente búsqueda.
        "bloque": __import__("calibracion_dia").clasificar_bloque(alimento),
    }

@router.post("/adjust")
async def adjust_food_quantity(data: dict, user = Depends(get_current_user)):
    """Cuánto poner de un alimento para lo que queda de comida.

    REPUESTO el 2026-08-02. Esta ruta no existía y el frontend la llamaba: al pulsar un
    alimento en el buscador de Nutrición, `handleAddFood` hacía POST aquí, recibía un 404
    y caía en su catch con un "Error añadiendo alimento". O sea, añadir un alimento desde
    el buscador estaba roto. El motor (`calcular_cantidad_automatica`) siempre ha estado
    ahí; lo que faltaba era la puerta.

    Lo encontró un test que yo venía descartando como caduco. No lo era.
    """
    alimento_id = data.get("alimento_id")
    restantes = data.get("macros_restantes") or {}
    es_vegano = bool(data.get("es_vegano"))

    alimento = await db.foods.find_one({"id": alimento_id}, {"_id": 0})
    if not alimento:
        raise HTTPException(status_code=404, detail="Alimento no encontrado")

    # Se monta sobre calma_suggest, que es el motor con el que cuenta TODO desde el 31-07.
    # El antiguo `calculator.calcular_cantidad_automatica` es de antes de unificar y ya ni
    # se ejecuta: revienta con KeyError 'proteina_cuenta' porque busca una clave que la
    # forma actual de los macros efectivos ya no tiene. Usarlo aquí habría repuesto la
    # puerta para dar un 500 en vez de un 404.
    from calma_suggest import ajustar_cantidad

    remaining = {
        "proteinas": float(restantes.get("P") or restantes.get("proteina") or 0),
        "hidratos": float(restantes.get("H") or restantes.get("hidratos") or 0),
        "grasas": float(restantes.get("G") or restantes.get("grasa") or 0),
    }
    # OJO: ajustar_cantidad devuelve UNIDADES si el alimento va por unidades, y gramos si
    # va a granel. El frontend espera gramos, así que se convierte. Sin esto salían "1 g"
    # de aceite (era 1 cucharada) y "2 g" de pollo (eran 2 latas de 52 g).
    cantidad = ajustar_cantidad(alimento, remaining)
    # 0 no es una cantidad: es la forma que tiene el motor de decir que el alimento no cabe
    # ni a su cantidad mínima (media lata, 5 g de aceite, 50 g de verdura). Si se devolviera
    # como cantidad, el alimento entraría en la comida ocupando una línea a 0 ud, que es lo
    # que pasaba con el "Queso Havarti · 0 ud". Por debajo del mínimo se descarta, no se deja
    # a cero (regla del doc del 07-08, punto 5).
    if cantidad <= 0:
        return {
            "alimento_id": alimento.get("id"),
            "nombre": alimento.get("nombre"),
            "cantidad_g": 0.0,
            "macros_efectivos": {"P": 0.0, "H": 0.0, "G": 0.0},
            "macros_brutos": {"P": 0.0, "H": 0.0, "G": 0.0},
            "que_cuenta": {"P": False, "H": False, "G": False},
            "cabe": False,
            "motivo": "no_llega_al_minimo",
            "cantidad_minima_g": _minimo_en_gramos(alimento),
        }
    if alimento.get("unidades"):
        cantidad_g = cantidad * (float(alimento.get("racion") or 100) or 100.0)
    else:
        cantidad_g = cantidad
    # El número que se le enseña al cliente va redondeado (nadie pesa 223 g de pechuga), y
    # los macros se calculan sobre esa cantidad ya redondeada para que lo que ve cuadre con
    # lo que suma.
    cantidad_g = _redondear_para_el_cliente(alimento, cantidad_g)
    efectivos, brutos, cuenta = _efectivos_calma(alimento, cantidad_g)

    return {
        "alimento_id": alimento.get("id"),
        "nombre": alimento.get("nombre"),
        "cantidad_g": cantidad_g,
        "macros_efectivos": efectivos,
        "macros_brutos": brutos,
        "que_cuenta": cuenta,
        # Cabe si aporta algo y no se pasa de lo que queda en ningún macro.
        "cabe": all(
            efectivos.get(k, 0) <= remaining[v] + 0.5 or remaining[v] <= 0
            for k, v in (("P", "proteinas"), ("H", "hidratos"), ("G", "grasas"))
        ),
    }


@router.post("/macros-comida")
async def get_macros_comida(data: dict, user = Depends(get_current_user)):
    """Calcula los macros totales de una comida completa."""
    alimentos_input = data.get("alimentos", [])
    es_vegano = data.get("es_vegano", False)
    
    total_P = total_H = total_G = 0.0
    total_P_bruto = total_H_bruto = total_G_bruto = 0.0
    detalle = []
    
    for item in alimentos_input:
        alimento = await db.foods.find_one({"id": item["alimento_id"]}, {"_id": 0})
        if not alimento:
            continue
        
        cantidad = item.get("cantidad_g", alimento.get("racion", 100))

        # Mismo motor que el buscador y que anadir a mano (calma_suggest), para que una
        # comida no sume distinto segun el endpoint por el que se pregunte.
        efectivos, brutos, cuenta = _efectivos_calma(alimento, cantidad)

        total_P += efectivos["P"]
        total_H += efectivos["H"]
        total_G += efectivos["G"]
        total_P_bruto += brutos["P"]
        total_H_bruto += brutos["H"]
        total_G_bruto += brutos["G"]
        
        detalle.append({
            "alimento_id": item["alimento_id"],
            "nombre": alimento.get("nombre", ""),
            "cantidad_g": cantidad,
            "efectivos": efectivos,
            "brutos": brutos,
            "que_cuenta": cuenta
        })
    
    return {
        "total_efectivos": {
            "P": round(total_P, 1),
            "H": round(total_H, 1),
            "G": round(total_G, 1),
            "kcal": round(total_P * 4 + total_H * 4 + total_G * 9, 1)
        },
        "total_brutos": {
            "P": round(total_P_bruto, 1),
            "H": round(total_H_bruto, 1),
            "G": round(total_G_bruto, 1),
            "kcal": round(total_P_bruto * 4 + total_H_bruto * 4 + total_G_bruto * 9, 1)
        },
        "detalle": detalle
    }

@router.get("/test-calma")
async def test_calma(user = Depends(get_current_user)):
    """Ejecuta los tests del motor CALMA v2."""
    results = calma_run_tests()
    return results


# ==================== DISTRIBUTE MACROS ====================

# La lógica vive en `macros_por_fecha`, compartida con el asistente. Estaba solo aquí, y
# el asistente leía el perfil por su cuenta: 70 g de hidratos de diferencia al día para el
# mismo cliente (punto 80 del documento del 07-08). Se dejan estos dos nombres porque el
# resto del fichero los usa.
async def _choose_macro_entry_for_date(profile: dict, fecha: Optional[str]):
    from macros_por_fecha import elegir_entrada
    return await elegir_entrada(db, profile, fecha)


async def _resolve_macros_for_date(profile: dict, fecha: Optional[str]):
    from macros_por_fecha import resolver
    return await resolver(db, profile, fecha)


@router.post("/distribute")
async def distribute_macros(data: dict, user = Depends(get_current_user)):
    """
    Distribuye los macros del usuario entre sus comidas del día.
    Los macros se resuelven POR FECHA (date-versioned, Calma todosLosMacros): un día usa la
    versión de macros vigente a esa fecha, no siempre la última.
    """
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil de cliente no encontrado")

    training, rest, peri = await _resolve_macros_for_date(profile, data.get("fecha"))

    if not training:
        raise HTTPException(status_code=400, detail="No tienes macros asignados")

    opcion_peri = data.get("opcion_peri", "intra_post")
    # El 35/15 de arranque solo entra si el cliente NO tiene peri configurado, y nunca en modo
    # `sin_peri`. Un peri a 0 es decision del coach y se respeta (ver leer_peri/leer_macro).
    p_peri, h_peri = leer_peri(peri, opcion_peri)

    resultado = dist_macros(
        p_entreno=leer_macro(training, "protein", "proteinas"),
        h_entreno=leer_macro(training, "carbs", "hidratos"),
        g_entreno=leer_macro(training, "fat", "grasas"),
        p_peri=p_peri,
        h_peri=h_peri,
        p_descanso=leer_macro(rest, "protein", "proteinas"),
        h_descanso=leer_macro(rest, "carbs", "hidratos"),
        g_descanso=leer_macro(rest, "fat", "grasas"),
        tipo_dia=data.get("tipo_dia", "entrenamiento"),
        num_comidas=data.get("num_comidas", 4),
        momento_entreno=data.get("momento_entreno", 1),
        opcion_peri=opcion_peri,
        # single-meal: el cliente puede elegirlo desde Nutrición (select nº comidas = 1),
        # lo que sobrescribe el ajuste del coach. Si el request no lo manda, se usa el perfil.
        single_meal=(bool(data["single_meal"]) if data.get("single_meal") is not None
                     else bool(profile.get("single_meal_mode", False))),
    )

    # Si los datos del perfil son de fiar (tarea 1.4 del 21-08). La cabecera de Nutricion
    # pinta estos objetivos: cuando la lista no viene vacia, rotula «Provisionales» y empuja
    # a completar el perfil. Va aqui y no en el perfil del AuthContext porque esta llamada
    # viaja con las cabeceras de «actuar como»: el perfil que se evalua es el del cliente
    # sobre el que se trabaja, no el del que ha iniciado sesion.
    from core.datos_dudosos import datos_dudosos
    resultado["datos_dudosos"] = datos_dudosos(profile)
    return resultado


# ==================== SEARCH & SUGGEST ====================

@router.get("/search")
async def search_foods_endpoint(
    q: str = "",
    category: Optional[str] = None,
    tipo_comida: str = "normal",
    tag: Optional[str] = None,
    limit: int = 50,
    vegano: bool = False,
    p_rest: Optional[float] = None,
    h_rest: Optional[float] = None,
    g_rest: Optional[float] = None,
    frequent: bool = False,
    cuadrar: bool = False,
    peri: Optional[str] = None,
    solo_cantidad: bool = False,
    # Lo que el día lleva ya de cada familia calibrada. Sin esto los macros que enseña el
    # buscador son los de antes de que existiera la calibración: ver `macros_al_anadirlo`.
    # Sin mandarlos NO se calibra: quien busca para un menú suelto de la biblioteca no tiene
    # día que acumular, y ahí la regla no aplica.
    dia_cp: Optional[float] = None,
    dia_fs: Optional[float] = None,
    user = Depends(get_current_user)
):
    """Búsqueda de alimentos con macros efectivos (CALMA).
    Si se pasan p_rest/h_rest/g_rest, ordena por aporte y calcula cantidad sugerida.
    `solo_cantidad=true` -> el hueco de macros decide la CANTIDAD de cada alimento, pero
    NO el orden ni quién sale: es lo que necesita el buscador por nombre, donde manda lo
    que ha escrito el cliente (Jesús, 15-08) pero la cantidad tiene que cuadrar el macro
    igual que en Calma (Jesús, 17-08).
    Filtra alimentos que el usuario marcó como 'a evitar'.
    `frequent=true` -> el set de alimentos = top-20 frecuentes del usuario (como el
    filtro TOP de Calma); luego pasa por el mismo motor (cantidad + regla + diferencia).
    """
    if frequent:
        # Calma's "Alimentos frecuentes": top-20 by raw appearance count across all the
        # user's saved diets. They go through the SAME suggestion engine below.
        freq = await _get_food_frequency(user["id"])
        top_ids_str = sorted(freq, key=lambda k: freq[k], reverse=True)[:20]
        top_int = [int(f) for f in top_ids_str if str(f).lstrip("-").isdigit()]
        alimentos = await db.foods.find({"id": {"$in": top_int}}, {"_id": 0}).to_list(20) if top_int else []
        base_order = {fid: i for i, fid in enumerate(top_int)}
        alimentos.sort(key=lambda a: base_order.get(a.get("id"), 9999))
    else:
        # Fetch ALL matches for both category browse AND text search - Calma ranks the full
        # filtered set by diferencia and shows it. Capping to `limit` BEFORE the engine sort
        # truncated in DB order, dropping the best-fitting foods (e.g. searching "arroz" lost
        # Pollo tikka / Crema de lentejas because they sat past the first 50 DB matches).
        fetch_limit = limit if (not category and not q) else 4000
        alimentos = await buscar_alimentos_async(
            db=db,
            query=q,
            categoria=category or "",
            tipo_comida=tipo_comida,
            es_vegano=vegano,
            limit=fetch_limit,
            calcular_efectivos=True,
            tag_filter=""  # tag filtering done below, after computing available_preps
        )

    # NOTE: Calma's "TOP/alimentos frecuentes" special filter (manejarAlimentos) is OFF by
    # default (filtrosActivacionPorDefecto = false). Frequent foods only appear when the user
    # explicitly opens the dedicated "Alimentos frecuentes" view, NOT injected into every
    # category browse. Injecting them here showed unrelated foods (Lomo, Arroz con pollo,
    # Crema de cacahuete) inside the Huevos category. Removed to match Calma.

    # Load user avoided preferences for filtering
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    avoided_prefixes, avoided_keywords = build_avoided_filter(profile)
    alimentos = [a for a in alimentos if not food_is_avoided(a, avoided_prefixes, avoided_keywords)]

    # POSTENTRENO universe restriction (Calma Dieta.js `todosLosAlimentos`):
    #   nombre == "postentreno" ? G(getTodosLosAlimentos, ["25"]) : getTodosLosAlimentos
    # i.e. for postentreno the WHOLE food universe is restricted to category "25" = "Postentreno"
    # (utils_ I map: ["25","Postentreno"]) - fast-digesting recovery foods. Intersected with the
    # picked category this is why e.g. the Salsas/Siropes/Konjac category in postentreno shows
    # ONLY the siropes (the only cat-16 foods also tagged 25). Intraentreno is NOT restricted.
    if peri == "post":
        alimentos = [a for a in alimentos if food_in_cat_calma(a, "25")]

    # Collect available preparations using Calma-equivalent test functions (before filtering).
    available_preps = [p for p in _PREPS_ORDER if any(_PREP_TESTS[p](a) for a in alimentos)]

    # Apply preparation filter - supports comma-separated multiple tags (OR logic).
    if tag:
        tag_list = [t.strip().upper() for t in tag.split(',') if t.strip()]
        def matches_tag(alimento, tag_upper):
            test_fn = _PREP_TESTS.get(tag_upper)
            if test_fn:
                return test_fn(alimento)
            return _has_token(alimento, tag_upper)
        alimentos = [a for a in alimentos if any(matches_tag(a, t) for t in tag_list)]

    # No early truncation: the diferencia sort (below) must see the FULL filtered set, then
    # we cap AFTER sorting so the top results are the best-fitting, like Calma.

    # Inject per-unit config so frontend can display "2 ud" vs "120g" correctly
    for a in alimentos:
        cfg = get_food_config(a)
        a["por_unidad"] = cfg.get("por_unidad", False)
        a["peso_unidad"] = cfg.get("peso_unidad", 0)
        a["is_promocionado"] = _es_promocionado(a)  # PROMOCIONADO badge (Calma esPromocionado)

    # ── Relevancia del texto escrito ─────────────────────────────────────────────
    # El filtro de nombre es "cada palabra de la query esta en el nombre", en cualquier
    # posicion. Con eso solo, buscar "huevo" mezclaba los huevos con un "Doble McExtreme
    # BBQ Bourbon Huevo", y ni siquiera salian "Huevos enteros M/XL": el orden lo decidian
    # la diferencia de macros o la frecuencia, que no saben lo que se ha escrito.
    #
    # Aqui se antepone lo evidente: primero lo que EMPIEZA por lo escrito, luego donde lo
    # escrito arranca una palabra, y al final donde solo aparece suelto. Dentro de cada
    # grupo manda el orden de siempre (diferencia de macros / frecuencia), asi que el
    # motor de Calma sigue decidiendo entre alimentos igual de relevantes.
    q_norm = normalize_text(q).strip() if q else ""
    _re_palabra = re.compile(r"\b" + re.escape(q_norm)) if q_norm else None

    def _relevancia(alimento) -> int:
        if not q_norm:
            return 0
        nombre = normalize_text(alimento.get("nombre", ""))
        if nombre.startswith(q_norm):
            return 0
        if _re_palabra and _re_palabra.search(nombre):
            return 1
        return 2

    has_macros_context = p_rest is not None or h_rest is not None or g_rest is not None
    # Si quien busca ha dicho lo que lleva el día, sus macros se calculan como los calculará
    # la comida al guardarse (punto 135). Ver el uso más abajo.
    hay_dia = dia_cp is not None or dia_fs is not None
    # Calma's remaining uses raw-gram macros keyed proteinas/hidratos/grasas.
    # Unspecified macro -> inf (unconstrained); negatives clamped inside the engine.
    remaining = {
        "proteinas": float(p_rest) if p_rest is not None else float('inf'),
        "hidratos": float(h_rest) if h_rest is not None else float('inf'),
        "grasas": float(g_rest) if g_rest is not None else float('inf'),
    }

    if has_macros_context:
        # ── Calma manual-builder engine (calma_suggest) ──────────────────────
        # Suggested quantity = ajustarCantidadIngrediente (raw me, all 3 macros).
        # Ordering = diferenciaDeMacros ascending. NO "macros efectivos" here.
        procesados = []
        for a in alimentos:
            # Calma applies the macro-counting rule (ye) at food load: non-counting
            # macros are zeroed so they neither fill their target nor display. This
            # drives the ordering of mixed-macro prepared foods.
            aplicar_regla_macros_calma(a)
            cant = ajustar_cantidad_calma(a, remaining)  # units (unidades) or grams
            if cant <= 0 or math.isinf(cant):
                # 0 -> minimum portion already overshoots; exclude (matches Calma a>cant).
                # inf only for zero-macro foods, already resolved inside the engine.
                if cant <= 0:
                    if not solo_cantidad:
                        continue
                    # Buscando por nombre nadie se cae de la lista: si ni la ración mínima
                    # cabe en el hueco, la cantidad es esa mínima y la pantalla avisa de que
                    # la comida se pasa.
                    cant = cantidad_minima_calma(a) or 1.0
            contrib = macros_at_calma(a, cant)  # {proteinas,hidratos,grasas}
            es_unidad = bool(a.get("unidades"))
            racion = float(a.get("racion") or 100)
            # Frontend expects grams in _cantidad_sugerida + peso_unidad = g/unit.
            a["por_unidad"] = es_unidad
            a["peso_unidad"] = racion
            # El ORDEN de las sugerencias lo sigue decidiendo la cantidad exacta del motor
            # (misma diferencia de macros que Calma); lo que se redondea es el número que se
            # enseña, y sus macros con él. Redondear antes de ordenar cambiaría qué alimento
            # sale el primero, que no es lo que se pide.
            cant_mostrada = (cant * racion) if es_unidad else cant
            cant_mostrada = _redondear_para_el_cliente(a, cant_mostrada)
            a["_cantidad_sugerida"] = cant_mostrada
            # LOS MACROS QUE SE ENSEÑAN, CON LA CALIBRACIÓN DEL DÍA PUESTA (punto 135).
            # El orden y la cantidad los sigue decidiendo el motor de Calma más arriba
            # (`contrib` y `_diferencia`): aquí sólo se calcula el número que se lee, que es
            # el que tiene que coincidir con el que quedará en la comida al guardar.
            from calibracion_dia import macros_al_anadirlo, clasificar_bloque
            if hay_dia:
                ef = macros_al_anadirlo(a, cant_mostrada, dia_cp or 0.0, dia_fs or 0.0)
                ef = {"proteinas": ef["P"], "hidratos": ef["H"], "grasas": ef["G"]}
            else:
                ef = macros_at_calma(a, (cant_mostrada / racion) if es_unidad else cant_mostrada)
            a["_macros_sugeridos"] = {"P": round(ef["proteinas"], 1),
                                      "H": round(ef["hidratos"], 1),
                                      "G": round(ef["grasas"], 1)}
            # De qué familia calibrada es, para que la ventana pueda ir sumando lo que lleva
            # puesto sin tener que repetir aquí la clasificación por categorías.
            a["bloque"] = clasificar_bloque(a)
            a["_diferencia"] = diferencia_de_macros_calma(contrib, remaining)
            a["_aporte_total"] = contrib["proteinas"] + contrib["hidratos"] + contrib["grasas"]
            procesados.append(a)
        alimentos = procesados

        # Get favorites (feature OCULTA 2026-07-06: la estrella alteraba el orden y no se quiere;
        # FOOD_FAVORITES_FIRST=True para reactivar el orden favoritos-primero).
        fav_doc = await db.food_favorites.find_one({"user_id": user["id"]}, {"_id": 0})
        fav_ids = set(str(fid) for fid in (fav_doc.get("food_ids", []) if fav_doc else []))
        for a in alimentos:
            a["is_favorite"] = str(a.get("id", "")) in fav_ids

        # Calma ordenarIngredientesPorMacro: sort by diferenciaDeMacros asc (tie-break nombre),
        # THEN a stable sort by prioridad[fase]. prioridad (de()) = min matched index in the fase's
        # prioritarias list, and PRO/PROMOCIONADO brands get idx-0.5 so they float to the TOP of
        # their bucket (verified 2026-06-15 in the intra phase: FullGas amino/peptides surface
        # above non-promo of cat 41). See _is_pro below for the marcasRecomendadas detection.
        _is_pro = _es_promocionado  # PRO/PROMOCIONADO float (-0.5), Calma de() + marcasRecomendadas
        def _diff(f):
            d = f.get("_diferencia")
            return d if d is not None else float('inf')
        # Calma cuadrarMacros phase (paso 3): after the diferencia order, a stable sort by
        # prioridad[fase] floats certain categories to the top after the diferencia order
        # (Calma's second sort in ordenarIngredientesPorMacro). de() = min matched index in
        # the fase's prioritarias list, PRO brands -0.5. Phases:
        #   cuadrarMacros (paso 3 normal meal): good fats 17.1.1 -> 17.1 -> 42
        #   intraentreno / postentreno (peri meals): their own prioritarias lists.
        _PRIOR_LISTS = {
            "cuadrar": ("17.1.1", "17.1", "42"),
            # INTRA: nos separamos de Calma A PROPOSITO (Francisco, 25-08).
            #
            # Calma tiene ["41", "18.1.1", "18.1.3", "18.1.2"] y nosotros la copiamos tal
            # cual, pero esa lista esta mal en el origen y por eso el intra no sugeria lo
            # que dice el metodo:
            #   - 18.3 (ciclodextrina, dextrosa, palatinosa) NO estaba. Es el hidrato
            #     rapido que Jesus recomienda en el intra por escrito (core/guion_peri.py:
            #     «Mi favorito es la ciclodextrina»), y en Calma solo aparece en la lista
            #     del POST. Sin el, el sugeridor no lo subia nunca.
            #   - 18.1.3 esta VACIA en nuestro catalogo: 0 alimentos. Ocupaba sitio y nada mas.
            #
            # El orden que queda es el del metodo: MAP primero (dentro de 41, el de FullGas
            # sale delante solo, por el -0.5 de marca recomendada), luego la ciclodextrina y
            # los otros hidratos rapidos, y solo despues las isotonicas: primero las que
            # llevan azucar (18.1.1), que es la alternativa del guion, y al final las light
            # (18.1.2), que no aportan hidratos.
            "intra": ("41", "18.3", "18.1.1", "18.1.2"),
            "post": ("4.1.1", "4.1.2", "4.1", "4.2", "5.4", "5.2.3", "5.2.2", "5.1", "4.3",
                     "27", "21.3", "7.1.1", "7.1.2.1", "18.3", "11.5", "11.2.1", "11.2.2",
                     "11.1", "11.4", "11.6", "11.7", "21.2", "7.3.1", "8", "24", "19.1",
                     "18.1", "18.2", "37", "16.5", "16.1"),
        }
        # Calma fase selection (Dieta.js ordenarIngredientesPorMacro): `cuadrarMacros` once P&H
        # are >80% of target, REGARDLESS of meal type, takes precedence over the peri list.
        # `peri` (post/intra) is the MEAL TYPE (drives the cat-25 universe + grasas margin) and is
        # sent independently of `cuadrar`, so cuadrar must win here when both are present.
        if cuadrar:
            _prior_list = _PRIOR_LISTS["cuadrar"]
        elif peri in ("intra", "post"):
            _prior_list = _PRIOR_LISTS[peri]
        else:
            _prior_list = None
        def _prioridad(f):
            if not _prior_list:
                return 0
            for idx, code in enumerate(_prior_list):
                if food_in_cat_calma(f, code):
                    p = (idx - 0.5) if _is_pro(f) else float(idx)
                    return p - _favorito_del_metodo(f) if peri == "intra" else p
            return float('inf')
        # BUSCANDO, EL ORDEN ES EL DE CALMA Y NADA MÁS (Francisco, 17-08).
        #
        # El buscador de la Dieta de Calma NO puntúa el parecido con lo escrito: eso es el
        # scoring `Ie` del catálogo de Alimentos, otra pantalla. Aquí `ordenarIngredientes-
        # PorMacro` ordena por diferencia de macros y desempata por nombre, y punto. Poner
        # el parecido por delante partía la lista en bloques ("Pollo asado" antes que
        # "Pechuga de pollo") donde Calma los mezcla por encaje.
        #
        # Y el parecido no hacía de escudo contra el fallo 3: el filtro por nombre ya es el
        # de Calma -- cada palabra escrita tiene que estar en el nombre (`buscar_alimentos`)
        # --, así que buscando «pechuga» salen 58 pechugas y ninguna Pepsi, medido.
        alimentos.sort(key=lambda f: (
            0 if solo_cantidad else _relevancia(f),
            (0 if f.get("is_favorite") else 1) if FOOD_FAVORITES_FIRST else 0,
            _prioridad(f),
            _diff(f),
            f.get("nombre", "")
        ))
    else:
        # Default sort: (favorites si FOOD_FAVORITES_FIRST) > frequency > alphabetical
        fav_doc = await db.food_favorites.find_one({"user_id": user["id"]}, {"_id": 0})
        fav_ids = set(str(fid) for fid in (fav_doc.get("food_ids", []) if fav_doc else []))
        food_freq = await _get_food_frequency(user["id"])

        for a in alimentos:
            a["is_favorite"] = str(a.get("id", "")) in fav_ids

        alimentos.sort(key=lambda f: (
            _relevancia(f),
            (0 if f.get("is_favorite") else 1) if FOOD_FAVORITES_FIRST else 0,
            -food_freq.get(str(f.get("id", "")), 0),
            f.get("nombre", "")
        ))

    # Text search: cap AFTER the diferencia sort so the top (best-fitting) results survive,
    # like Calma's full-list ranking. 200 comfortably covers any real query (e.g. "arroz" ~120).
    if q:
        alimentos = alimentos[:max(limit, 200)]

    # CUANTO CABE DE ESTE ALIMENTO EN UNA COMIDA DE VERDAD.
    #
    # El asistente ya lo sabia (nunca propone 500 g de salsa de soja); la calculadora no, y
    # por eso se guardo 1 litro de leche de almendras en una comida (Jesus, 16-08). El tope
    # viaja con la ficha para que la pantalla pueda avisar sin preguntar otra vez. Es un
    # tope RAZONABLE: avisa, no bloquea.
    for a in alimentos:
        a["max_razonable"] = tope_de_alimento(a)

    return {"alimentos": alimentos, "total": len(alimentos), "available_preps": available_preps}


# Cache breve por usuario de la frecuencia de alimentos (rendimiento 2026-07-06):
# antes cada búsqueda recargaba TODAS las dietas del usuario con sus comidas (>1 s
# en clientes con años de histórico). La frecuencia solo cambia al guardar dieta,
# así que 60 s de cache no altera el comportamiento percibido.
_FREQ_CACHE: dict = {}
_FREQ_CACHE_TTL = 60  # segundos


async def _get_food_frequency(user_id: str) -> dict:
    """Raw appearance count of each food across ALL the user's saved diets, mirroring
    Calma's `alimentosFrecuentes` = Ge(Pe(dietas).ingredientes): repeticiones++ per
    occurrence, no time decay. Returns {food_id_str: count}.
    Calculado EN MongoDB con agregación (antes venían las dietas completas a Python).

    OJO: lo que se devuelve es el dict CACHEADO, no una copia (copiarlo en cada búsqueda
    costaría más que el ahorro del cache). Es de SOLO LECTURA: quien lo mute se lo estará
    mutando a las demás peticiones del mismo usuario durante el TTL.
    """
    import time as _time
    now = _time.monotonic()
    cached = _FREQ_CACHE.get(user_id)
    if cached and (now - cached[0]) < _FREQ_CACHE_TTL:
        return cached[1]

    rows = await db.diets.aggregate([
        {"$match": {"user_id": user_id}},
        {"$project": {"meals": {"$objectToArray": {"$ifNull": ["$comidas", {}]}}}},
        {"$unwind": "$meals"},
        {"$unwind": "$meals.v.alimentos"},
        {"$group": {
            "_id": {"$toString": {"$ifNull": [
                "$meals.v.alimentos.id",
                {"$ifNull": ["$meals.v.alimentos.alimento_id", ""]},
            ]}},
            "count": {"$sum": 1},
        }},
    ]).to_list(10000)

    counts = {r["_id"]: r["count"] for r in rows if r["_id"]}
    _FREQ_CACHE[user_id] = (now, counts)
    return counts

@router.get("/frequent-foods")
async def get_frequent_foods(
    limit: int = 20,
    user = Depends(get_current_user)
):
    """Top alimentos más usados por el usuario en su historial de dietas."""
    freq = await _get_food_frequency(user["id"])
    if not freq:
        return {"alimentos": []}

    # Top IDs sorted by frequency
    top_ids_str = sorted(freq, key=lambda k: freq[k], reverse=True)[:limit]

    # Convert to int where possible (food IDs are numeric in this DB)
    top_ids = []
    for fid in top_ids_str:
        try:
            top_ids.append(int(fid))
        except (ValueError, TypeError):
            top_ids.append(fid)

    foods_cursor = db.foods.find({"id": {"$in": top_ids}}, {"_id": 0})
    foods_map = {}
    async for f in foods_cursor:
        foods_map[str(f["id"])] = f

    # Load user avoided preferences
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    avoided_prefixes, avoided_keywords = build_avoided_filter(profile)

    enriched = []
    for fid_str in top_ids_str:
        food = foods_map.get(fid_str)
        if not food or food_is_avoided(food, avoided_prefixes, avoided_keywords):
            continue
        cfg = get_food_config(food)
        enriched.append({
            **food,
            "por_unidad": cfg.get("por_unidad", False),
            "peso_unidad": cfg.get("peso_unidad", 0),
            "usos": freq[fid_str],
        })

    return {"alimentos": enriched}


@router.post("/refit-diet")
async def refit_diet(data: dict, user = Depends(get_current_user)):
    """Re-ajusta las cantidades de una dieta (p.ej. una favorita al aplicarla) a los macros del
    día indicado, SIN pasarse y respetando el mínimo de cada alimento. Reutiliza el reparto por
    comida de /distribute (macros de hoy) y la misma función de dimensionado del constructor
    (ajustar_cantidad). Los alimentos que no caben ni a su cantidad mínima se quitan y se
    devuelven en 'excluidos'. NO inventa lógica: solo aplica la existente a alimentos fijos.

    Flag opcional `descartar_sin_objetivo` (adaptar una favorita al tipo de día actual,
    entreno<->descanso): las comidas que no existen en el día destino (Intra/Post en
    descanso, o Intra con opcion_peri solo_post) se vacían y sus alimentos van a
    'excluidos' con motivo 'sin_objetivo_en_dia' en vez de copiarse tal cual."""
    dist = await distribute_macros({
        "fecha": data.get("fecha"),
        "tipo_dia": data.get("tipo_dia", "entrenamiento"),
        "num_comidas": data.get("num_comidas", 4),
        "momento_entreno": data.get("momento_entreno", 1),
        "opcion_peri": data.get("opcion_peri", "intra_post"),
        "single_meal": (data.get("num_comidas", 4) == 1),
    }, user)
    targets = dist.get("comidas", {}) if isinstance(dist, dict) else {}
    # El peri no tiene target en `comidas` (va aparte, en `periworkout`): sirve para
    # distinguir "peri legítimo del día" de "comida que este día no tiene" (p.ej.
    # Intra/Post al adaptar una favorita de entreno a un día de descanso).
    peri_targets = dist.get("periworkout", {}) if isinstance(dist, dict) else {}
    # descartar_sin_objetivo (adaptar entreno<->descanso): las comidas sin hueco en el
    # día NO se copian tal cual, se vacían y sus alimentos se devuelven en excluidos.
    descartar = bool(data.get("descartar_sin_objetivo", False))

    def _target(mk):
        # El intra y el post tienen su objetivo en `periworkout`, no en `comidas`.
        # Hasta el 08-08-2026 esto solo miraba `comidas`, así que el botón «Cuadrar»
        # del peri no hacía absolutamente nada: le entraban 500 g de avena y devolvía
        # 500 g. El botón estaba, se pulsaba, y no pasaba nada.
        t = targets.get(mk) or peri_targets.get(mk) or {}
        es_peri = mk not in targets and mk in peri_targets
        return {
            "proteinas": float(t.get("P", t.get("proteinas", 0)) or 0),
            "hidratos": float(t.get("H", t.get("hidratos", 0)) or 0),
            # En el peri la grasa va libre. En Calma el objetivo del peri directamente
            # no tiene clave de grasas -- no es que sea 0, es que no se cuadra -- y
            # nuestro reparto la escribe como 0. Tomárselo al pie de la letra haría que
            # cualquier cosa con una pizca de grasa saliera como «te sobra grasa».
            "grasas": float("inf") if es_peri else float(t.get("G", t.get("grasas", 0)) or 0),
        }

    comidas_in = data.get("comidas") or {}
    out_comidas = {}
    excluidos = []
    desfases = {}
    for meal_key, meal in comidas_in.items():
        meal = meal if isinstance(meal, dict) else {}
        # El peri sí se cuadra: tiene objetivo, solo que en `periworkout`.
        if meal_key not in targets and meal_key not in peri_targets:
            if descartar:
                # Adaptar al tipo de día: esta comida no existe en el día destino
                # (p.ej. Intra/Post en descanso). Se vacía (si quedaran alimentos
                # ocultos, el autosave los persistiría y reaparecerían sin ajustar
                # al volver a entreno) y se avisa al front vía excluidos.
                for it in (meal.get("alimentos") or []):
                    excluidos.append({"meal": meal_key, "nombre": it.get("nombre"),
                                      "motivo": "sin_objetivo_en_dia"})
                out_comidas[meal_key] = {**meal, "alimentos": []}
                continue
            # Sin objetivo para esa comida: la dejamos como estaba (no vaciar por seguridad).
            out_comidas[meal_key] = meal
            continue
        remaining = _target(meal_key)
        refit_foods = []
        food_docs = []
        # ¿Se ha movido alguna cantidad al dejarla en algo pesable? Si se ha movido, los
        # macros ya no son los que salieron del cálculo y hay que decirlo (fallo 29).
        redondeado = False

        # Se REPARTE, no se sirve en cola (Francisco, 08-08-2026).
        #
        # Antes esto recorría los alimentos en el orden de la lista y cada uno se
        # llevaba todo lo que podía del presupuesto que quedaba. Los últimos se
        # encontraban el presupuesto a cero, recibían cantidad 0 y SE BORRABAN. No se
        # iban por descuadrar ni por ser peores: se iban por llegar tarde. Se
        # comprobó poniendo el mismo alimento el primero y el cuarto: el primero
        # sobrevivía y el cuarto no, fuera cual fuera.
        #
        # Ahora se le reserva a cada uno su cantidad mínima antes de repartir nada, y
        # solo se reparte lo que sobra. Así los seis siguen ahí. Si con los mínimos ya
        # se pasa del objetivo, el reparto no da más de sí y se queda en los mínimos:
        # el desfase se cuenta y se dice, pero **no se quita nada**. Lo que el cliente
        # ha puesto lo quita el cliente.
        entradas = []
        for it in (meal.get("alimentos") or []):
            aid = it.get("alimento_id")
            # Los dos únicos casos en los que un alimento desaparece al cuadrar, y
            # ninguno es una decisión sobre macros: o la línea no dice a qué alimento
            # se refiere, o ese alimento ya no está en el catálogo. En los dos se
            # avisa -- nada se va en silencio.
            if aid in (None, ""):
                excluidos.append({"meal": meal_key, "nombre": it.get("nombre"),
                                  "motivo": "sin_alimento_id"})
                continue
            try:
                food = await db.foods.find_one({"id": int(aid)}, {"_id": 0})
            except (TypeError, ValueError):
                food = None
            if not food:
                excluidos.append({"meal": meal_key, "nombre": it.get("nombre"),
                                  "motivo": "no_esta_en_el_catalogo"})
                continue
            aplicar_regla_macros_calma(food)
            entradas.append((it, food, cantidad_minima_calma(food)))

        # Lo que consumen los mínimos sale del presupuesto antes de repartir.
        for _, food, minimo in entradas:
            aporte = macros_at_calma(food, minimo)
            for k in ("proteinas", "hidratos", "grasas"):
                if not math.isinf(remaining[k]):
                    remaining[k] = max(0.0, remaining[k] - aporte[k])

        for it, food, minimo in entradas:
            aid = it.get("alimento_id")
            # Lo que quepa por encima del mínimo, con el mismo dimensionado de siempre.
            extra = ajustar_cantidad_calma(food, remaining)
            if extra <= 0 or math.isinf(extra):
                extra = 0.0
            # `ajustar_cantidad` devuelve la cantidad total que cabría, no un extra:
            # como el mínimo ya está reservado, se descuenta para no contarlo dos veces.
            cant = max(minimo, extra)
            contrib = macros_at_calma(food, cant)
            aporte_minimo = macros_at_calma(food, minimo)
            for k in ("proteinas", "hidratos", "grasas"):
                if not math.isinf(remaining[k]):
                    remaining[k] = max(0.0, remaining[k] - max(0.0, contrib[k] - aporte_minimo[k]))
            es_unidad = bool(food.get("unidades"))
            racion = float(food.get("racion") or 100)
            refit_foods.append({
                **it,
                "alimento_id": int(aid),
                "nombre": food.get("nombre") or it.get("nombre"),
                "cantidad_g": round((cant * racion) if es_unidad else cant, 1),
                "macros_efectivos": {
                    "P": round(contrib["proteinas"], 1),
                    "H": round(contrib["hidratos"], 1),
                    "G": round(contrib["grasas"], 1),
                },
                "racion": food.get("racion"),
                "unidades": es_unidad,
            })
            food_docs.append(food)

        # Pasada final de afinado (mismo optimizador que los menús): el dimensionado
        # secuencial "sin pasarse" deja macros cortos que solo se arreglan aceptando
        # pasarse un poco o intercambiando cantidades entre alimentos (p.ej. el único
        # alimento con grasa va por unidades: 1 huevo = 6G y faltan 4G -> 2 huevos).
        if refit_foods:
            from meal_templates import afinar_cantidades, _menu_max
            from meal_builder import get_effective_macros_per_100g, get_food_limits
            from calculator import get_food_config
            tgt = _target(meal_key)
            obj_fino = {"P": tgt["proteinas"], "H": tgt["hidratos"], "G": tgt["grasas"]}
            opt_foods = []
            for rf, food in zip(refit_foods, food_docs):
                cfg = get_food_config(food)
                ef = get_effective_macros_per_100g(food)
                # CANTIDADES QUE SE PUEDAN PESAR (Jesús, 15-08, fallo 29). El mínimo del
                # catálogo deja bajar el aguacate a 5 g y el yogur a 30, y eso no es comida:
                # es «un poco». `minimo_pesable` sube ese suelo a 20 g salvo en lo que de
                # verdad se usa a cucharaditas (aceites, salsas, polvos, azúcar). Se aplica
                # también a la cantidad de partida, porque el afinado solo acepta movimientos
                # DENTRO del rango: si entra por debajo del suelo, se queda ahí.
                minimo = minimo_pesable(food, float(cfg.get("minimo", 5) or 5))
                _, maximo_base = get_food_limits(food, cfg)
                peso_unidad = float(food.get("peso_unidad") or food.get("racion") or 0)
                es_unidad = bool(food.get("unidades") or food.get("por_unidad") or cfg.get("por_unidad"))
                opt_foods.append({
                    "cantidad": max(float(rf["cantidad_g"]), minimo),
                    "minimo": minimo,
                    "maximo": max(minimo, _menu_max("", ef.get("cat", ""), maximo_base)),
                    "ef": ef, "cat": ef.get("cat", ""),
                    "paso_unidad": peso_unidad if (es_unidad and peso_unidad > 0) else None,
                })
            # El afinado puede empeorar, y desde que no se quita nada se nota: con tres
            # alimentos grasos subía el cacao de 32 a 100 g para tapar la proteína que
            # faltaba, y de paso metía 10 g de grasa de más. Optimiza la distancia total
            # y no distingue entre quedarse corto y pasarse. Así que se mide antes y
            # después y **se queda el mejor de los dos**.
            def _distancia(cantidades):
                t = {"P": 0.0, "H": 0.0, "G": 0.0}
                for cant, of in zip(cantidades, opt_foods):
                    fac = cant / 100.0
                    for m in t:
                        t[m] += (of["ef"].get(m, 0) or 0) * fac
                # pasarse pesa el doble que quedarse corto: sobrar grasa descuadra el
                # día entero y faltar se arregla en la comida siguiente
                return sum((2 if t[m] > obj_fino[m] else 1) * abs(t[m] - obj_fino[m])
                           for m in ("P", "H", "G"))

            antes = [of["cantidad"] for of in opt_foods]
            d_antes = _distancia(antes)
            afinar_cantidades(opt_foods, obj_fino)
            if _distancia([of["cantidad"] for of in opt_foods]) > d_antes:
                for of, cant in zip(opt_foods, antes):
                    of["cantidad"] = cant

            for rf, of, food in zip(refit_foods, opt_foods, food_docs):
                # El afinado trabaja fino y deja cantidades como 182,5 o 120,1: al salir se
                # bajan al múltiplo redondo, y los macros se recalculan con la cantidad final.
                antes_de_redondear = float(rf["cantidad_g"])
                of["cantidad"] = max(of["minimo"],
                                     redondear_cantidad(food, of["cantidad"], minimo_g=of["minimo"]))
                # Redondear a la baja puede dejar la cantidad por debajo del suelo pesable
                # (`redondear_a_la_baja` devuelve el número tal cual cuando no le cabe otra):
                # ahí manda el suelo, que es lo que se puede pesar.
                fac = of["cantidad"] / 100.0
                if abs(of["cantidad"] - antes_de_redondear) > 0.5:
                    redondeado = True
                rf["cantidad_g"] = round(of["cantidad"], 1)
                rf["macros_efectivos"] = {
                    "P": round((of["ef"].get("P", 0) or 0) * fac, 1),
                    "H": round((of["ef"].get("H", 0) or 0) * fac, 1),
                    "G": round((of["ef"].get("G", 0) or 0) * fac, 1),
                }
        # Lo que ha quedado sin cuadrar, para poder decirlo en vez de callarlo. Como ya
        # no se quita nada, hay comidas que no van a cuadrar al gramo -- por ejemplo si
        # los mínimos de lo que ha puesto el cliente ya se pasan de grasa --, y eso hay
        # que contárselo: es su decisión quitar algo o quedarse como está.
        tgt = _target(meal_key)
        servido = {"P": 0.0, "H": 0.0, "G": 0.0}
        for rf in refit_foods:
            me = rf.get("macros_efectivos") or {}
            for m in servido:
                servido[m] += float(me.get(m, 0) or 0)
        # La grasa del peri va libre (target infinito): ahí no hay desfase que contar,
        # y decir «sobra grasa» en un post-entreno sería mentir.
        desfase = {
            m: (0.0 if math.isinf(tgt[k]) else round(servido[m] - tgt[k], 1))
            for m, k in (("P", "proteinas"), ("H", "hidratos"), ("G", "grasas"))
        }
        # Y si no ha cuadrado, se dice QUÉ habría que tocar. No basta con «sobran 6 g
        # de grasa»: el cliente quiere saber por cuál empezar. Si sobra un macro, el
        # culpable es el que más lo aporta -- ese es el que habría que quitar o bajar,
        # y lo decide él. Si falta, no hay nada que quitar: hay que añadir.
        # Manda lo que SE PASA, aunque otro macro se quede más corto: pasarse es lo que
        # solo se arregla quitando, y faltar se arregla añadiendo -- y eso el cliente ya
        # lo está viendo en las barras. Con cuatro aceites salía «te falta añadir
        # hidratos» cuando lo que pasaba es que sobraban 21,9 g de grasa.
        sugerencia = None
        sobra = {m: v for m, v in desfase.items() if v > 4}
        falta = {m: v for m, v in desfase.items() if v < -4}
        if sobra:
            peor = max(sobra, key=lambda m: sobra[m])
            culpable = max(
                refit_foods,
                key=lambda rf: float((rf.get("macros_efectivos") or {}).get(peor, 0) or 0),
                default=None)
            if culpable:
                sugerencia = {
                    "que_hacer": "quitar_o_bajar", "macro": peor,
                    "sobra": desfase[peor],
                    "alimento": culpable.get("nombre"),
                    "alimento_id": culpable.get("alimento_id"),
                    "aporta": float((culpable.get("macros_efectivos") or {}).get(peor, 0) or 0),
                }
        elif falta:
            peor = min(falta, key=lambda m: falta[m])
            sugerencia = {"que_hacer": "anadir", "macro": peor, "falta": -desfase[peor]}
        desfases[meal_key] = {**desfase, "sugerencia": sugerencia, "redondeado": redondeado}
        out_comidas[meal_key] = {**meal, "alimentos": refit_foods}
    return {"comidas": out_comidas, "distribution": dist, "excluidos": excluidos,
            "desfases": desfases}


@router.post("/suggest")
async def suggest_foods_endpoint(
    data: dict,
    user = Depends(get_current_user)
):
    """Sugerir alimentos para completar macros.

    Acepta los dos nombres de cada campo (`restante`/`macros_restantes`,
    `limit`/`max_resultados`) porque hay clientes usando ambos, y pasa `excluir_ids` al
    motor: lo soportaba desde siempre y la ruta se lo estaba comiendo, así que pedir
    "otras sugerencias, esas no" devolvía las mismas.
    """
    objetivo = data.get("objetivo", {"P": 40, "H": 15, "G": 8})
    restante = data.get("restante") or data.get("macros_restantes") or objetivo
    paso = data.get("paso")
    limit = data.get("limit") or data.get("max_resultados") or 5
    excluir = data.get("excluir_ids") or []
    tipo_comida = data.get("tipo_comida", "normal")

    foods_list = await get_all_foods_cached(db)

    sugerencias = sugerir_alimentos(
        alimentos_disponibles=foods_list,
        macros_restantes=restante,
        tipo_comida=tipo_comida,
        max_resultados=limit,
        excluir_ids=excluir,
        paso=paso
    )
    
    return {"suggestions": sugerencias, "count": len(sugerencias)}


@router.post("/preferencias/cuadra")
async def preferencias_cuadran(data: dict, user = Depends(get_current_user)):
    """¿Con lo marcado se pueden cuadrar 20 g de proteína y 20 g de hidratos? (doc 19-08).

    La comprobación es directa contra el motor de sugerencias, no contra una tabla aparte:
    «la calculadora ya sabe cuánto macro hace falta para poder sugerir cada alimento», así
    que se le pregunta a ella con el catálogo recortado a las categorías marcadas. La grasa
    no se comprueba porque las de buena calidad se ofrecen siempre, y por eso sus categorías
    entran en el recorte aunque no vengan marcadas.

    Se comprueba EN VIVO (el front llama a cada cambio, antes de guardar) y no se le dice
    qué marcar: eso sería decirle qué comer.
    """
    from core.preferencias import a_nombres
    from calma_suggest import food_in_any, hay_suficiente

    marcadas = data.get("marcadas") if isinstance(data, dict) else None
    if not isinstance(marcadas, list):
        raise HTTPException(status_code=400, detail="Falta la lista de categorías marcadas.")

    nombres = set(a_nombres(marcadas))
    nombres.add("grasas_buenas")   # se ofrecen siempre: el motor las tiene aunque no se marquen
    prefijos = [p for n in nombres for p in AVOIDABLE_PREFIXES.get(n, [])]

    foods_list = await get_all_foods_cached(db)
    elegibles = [f for f in foods_list if food_in_any(f, prefijos)]

    def se_cuadra(macro: str) -> bool:
        # El mismo bucle que hace el cliente: sugerir, añadir, volver a sugerir. Si en
        # seis pasos no llega al 80% de los 20 g (el `hay_suficiente` del motor), con lo
        # marcado no se cuadra. `cabe` filtra las sugerencias que el motor devuelve solo
        # como relleno, con cantidad cero.
        objetivo = 20.0
        restante = {"P": 0.0, "H": 0.0, "G": 0.0}
        restante[macro] = objetivo
        usados: list = []
        for _ in range(6):
            if hay_suficiente(objetivo - restante[macro], objetivo):
                return True
            sugerencias = sugerir_alimentos(
                alimentos_disponibles=elegibles,
                macros_restantes=restante,
                tipo_comida="normal",
                max_resultados=3,
                excluir_ids=usados,
            )
            con_algo = next((s for s in sugerencias
                             if s.get("cabe") and (s.get("macros_efectivos") or {}).get(macro, 0) > 0), None)
            if not con_algo:
                break
            aporta = con_algo["macros_efectivos"]
            for k in restante:
                restante[k] = max(0.0, restante[k] - (aporta.get(k) or 0))
            usados.append((con_algo.get("alimento") or {}).get("id"))
        return hay_suficiente(objetivo - restante[macro], objetivo)

    return {"proteina": se_cuadra("P"), "hidratos": se_cuadra("H")}

# ==================== FOOD SUGGESTIONS (user submitted) ====================
#
# Proceso "Sugerencia e inclusión de alimentos": el cliente propone un alimento
# con sus macros, el enlace de la fuente y dos fotos (frontal + reverso). El admin
# lo revisa en su panel y, si lo aprueba, se carga en el catálogo (db.foods).

MAX_SUGGEST_PHOTO_BYTES = 6 * 1024 * 1024  # 6 MB por foto
ALLOWED_SUGGEST_PHOTO_TYPES = {
    "image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic", "image/heif",
}
WEEKLY_SUGGESTION_LIMIT = 2  # máximo de alimentos que un cliente puede sugerir por semana


def _week_start_iso() -> str:
    """ISO del lunes 00:00 UTC de la semana actual (para el límite semanal)."""
    now = datetime.now(timezone.utc)
    monday = now - timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


async def _store_suggestion_photo(suggestion_id: str, kind: str, file: UploadFile):
    """Valida y guarda una foto de la sugerencia como binario en food_suggestion_photos."""
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_SUGGEST_PHOTO_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Formato de imagen no admitido ({content_type or 'desconocido'}). Usa JPEG, PNG, WebP o HEIC.",
        )
    contents = await file.read()
    if len(contents) > MAX_SUGGEST_PHOTO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"La foto pesa {len(contents) // 1024} KB; el máximo permitido es {MAX_SUGGEST_PHOTO_BYTES // (1024 * 1024)} MB.",
        )
    await db.food_suggestion_photos.insert_one({
        "id": str(uuid.uuid4()),
        "suggestion_id": suggestion_id,
        "kind": kind,  # "frontal" | "reverso"
        "filename": file.filename or f"{kind}.jpg",
        "content_type": content_type,
        "size": len(contents),
        "data": Binary(contents),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    })


async def _peticiones_que_le_quedan(client_id: str) -> int:
    """Cuántas solicitudes le quedan a este cliente esta semana."""
    gastadas = await db.food_suggestions.count_documents({
        "client_id": client_id,
        "created_at": {"$gte": _week_start_iso()},
    })
    return max(0, WEEKLY_SUGGESTION_LIMIT - gastadas)


@router.get("/food-suggestions/restantes")
async def food_suggestions_restantes(user = Depends(get_current_user)):
    """«Te quedan 2 peticiones esta semana» (punto 167 del 27-08).

    El límite existía desde siempre en el servidor, pero no se le decía a nadie: el cliente
    rellenaba el formulario entero -- dos fotos incluidas -- y se llevaba un 429 al pulsar.
    Ahora el número viaja antes, y la pantalla lo enseña debajo del botón.
    """
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    return {"restantes": await _peticiones_que_le_quedan(profile["id"]),
            "limite": WEEKLY_SUGGESTION_LIMIT}


@router.post("/suggest-food", response_model=FoodSuggestionResponse)
async def suggest_new_food(
    nombre: str = Form(...),
    por_unidad: bool = Form(False),
    racion: float = Form(100.0),
    es_conserva: bool = Form(False),
    peso_tipo: str = Form("neto"),
    proteinas: float = Form(0.0),
    hidratos: float = Form(0.0),
    grasas: float = Form(0.0),
    url: Optional[str] = Form(None),
    sin_web: bool = Form(False),
    foto_frontal: Optional[UploadFile] = File(None),
    foto_reverso: Optional[UploadFile] = File(None),
    user = Depends(get_current_user),
):
    """El cliente solicita un alimento nuevo. Se registra como 'pendiente' hasta que el admin
    lo revise. Cada cliente puede pedir un máximo de 2 por semana.

    TODO ES OBLIGATORIO (punto 161 del 27-08). Hasta hoy se podía mandar con el nombre y nada
    más: las fotos salían como «opcionales, pero ayudan a la revisión» y los macros tampoco se
    exigían. Y una solicitud así NO SE PUEDE DAR DE ALTA -- hay que escribirle, preguntarle y
    esperar --, o sea que era el cuello de botella entero del proceso.

    Y se comprueba AQUÍ además de en la pantalla: el botón apagado evita el descuido, no la
    petición hecha a mano ni la pantalla vieja que se haya quedado en la caché de alguien.
    """
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    # Límite semanal (lunes-domingo)
    if await _peticiones_que_le_quedan(profile["id"]) <= 0:
        raise HTTPException(
            status_code=429,
            detail=f"Solo puedes pedir {WEEKLY_SUGGESTION_LIMIT} alimentos por semana. Vuelve a intentarlo la próxima semana.",
        )

    # Lo que falta, dicho todo junto: un viaje por campo es un formulario que se contesta a
    # ciegas, y aquí el cliente acaba de hacer dos fotos.
    hay_frontal = foto_frontal is not None and bool(foto_frontal.filename)
    hay_reverso = foto_reverso is not None and bool(foto_reverso.filename)
    enlace = (url or "").strip()
    faltan = []
    if not nombre.strip():
        faltan.append("el nombre del alimento")
    if not hay_frontal:
        faltan.append("la foto frontal")
    if not hay_reverso:
        faltan.append("la foto del reverso o el lateral")
    if por_unidad and not (float(racion or 0) > 0):
        faltan.append("el peso de la unidad")
    # Los tres macros a cero es una etiqueta sin copiar, no un alimento sin macros: los que de
    # verdad no aportan nada (la lechuga, los zero) ya están en el catálogo.
    if not any(float(v or 0) > 0 for v in (proteinas, hidratos, grasas)):
        faltan.append("los macros del envase")
    if not enlace and not sin_web:
        faltan.append("el enlace de la fuente (o marcar «No tiene web»)")
    if faltan:
        raise HTTPException(
            status_code=400,
            detail="Para pedir un alimento falta " + (
                faltan[0] if len(faltan) == 1 else ", ".join(faltan[:-1]) + " y " + faltan[-1]) + ".",
        )

    # racion: por 100 g -> 100; por unidad -> peso indicado (mínimo 1 g)
    racion_g = 100.0 if not por_unidad else max(float(racion or 0), 1.0)
    food = FoodSuggestion(
        nombre=nombre.strip(),
        por_unidad=por_unidad,
        racion=racion_g,
        es_conserva=es_conserva,
        # Fuera de las conservas no se pregunta, así que no se guarda una respuesta que nadie
        # ha dado: sin lata, el peso es el neto y punto.
        peso_tipo=("escurrido" if (es_conserva and peso_tipo == "escurrido") else "neto"),
        proteinas=float(proteinas or 0),
        hidratos=float(hidratos or 0),
        grasas=float(grasas or 0),
        url=(enlace or None),
        sin_web=bool(sin_web),
    )

    suggestion_id = str(uuid.uuid4())

    photos = []
    await _store_suggestion_photo(suggestion_id, "frontal", foto_frontal)
    photos.append("frontal")
    await _store_suggestion_photo(suggestion_id, "reverso", foto_reverso)
    photos.append("reverso")

    suggestion = {
        "id": suggestion_id,
        "client_id": profile["id"],
        "food": food.model_dump(),
        "status": "pending",
        "categorias": None,
        "admin_notes": None,
        "photos": photos,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.food_suggestions.insert_one(suggestion)
    return FoodSuggestionResponse(**suggestion)


@router.get("/my-food-suggestions", response_model=List[FoodSuggestionResponse])
async def my_food_suggestions(user = Depends(get_current_user)):
    """Sugerencias propias del cliente (para que vea el estado de cada una)."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        return []
    docs = await db.food_suggestions.find(
        {"client_id": profile["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return [FoodSuggestionResponse(**d) for d in docs]


@router.get("/food-suggestions/{suggestion_id}/photo/{kind}")
async def get_suggestion_photo(suggestion_id: str, kind: str, user = Depends(get_current_user)):
    """Sirve la foto (frontal/reverso) de una sugerencia. El dueño o el staff pueden verla."""
    suggestion = await db.food_suggestions.find_one(
        {"id": suggestion_id}, {"_id": 0, "client_id": 1}
    )
    if not suggestion:
        raise HTTPException(status_code=404, detail="Sugerencia no encontrada")

    is_staff = user.get("role") in ("admin", "trainer")
    if not is_staff:
        profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
        if not profile or profile["id"] != suggestion["client_id"]:
            raise HTTPException(status_code=403, detail="Sin permiso para ver esta foto")

    photo = await db.food_suggestion_photos.find_one(
        {"suggestion_id": suggestion_id, "kind": kind}, {"_id": 0}
    )
    if not photo or not photo.get("data"):
        raise HTTPException(status_code=404, detail="Foto no encontrada")

    return Response(
        content=bytes(photo["data"]),
        media_type=photo.get("content_type") or "application/octet-stream",
        headers={
            "Cache-Control": "private, max-age=3600",
            "Content-Disposition": f'inline; filename="{photo.get("filename") or kind}"',
        },
    )

# ==================== CALIBRACIÓN PROGRESIVA (día completo) ====================

@router.post("/calibrar-dia")
async def calibrar_dia_endpoint(data: dict, user = Depends(get_current_user)):
    """Recalcula los macros efectivos de TODO el día aplicando la calibración
    progresiva de la proteína vegetal (spec 17-07-2026): acumulado conjunto de
    cereales+panes y acumulado propio de frutos secos, por tramos, recorriendo
    las comidas en orden cronológico. La comida entera se asigna al tramo del
    acumulado tras añadirla; editar una comida solo cambia esa y las posteriores.

    Body: {meal_order: ["C1","Intra",...], comidas: {key: [{alimento_id, cantidad_g}]}}
    Devuelve por item macros_efectivos/brutos/que_cuenta (null si el alimento ya
    no existe: el front conserva lo que tenía) y los acumulados por comida.
    """
    from calibracion_dia import (calibrar_dia as _calibrar, clasificar_bloque,
                                 la_proteina_llega_al_tercio, la_proteina_crece_con_el_dia)

    meal_order = [str(k) for k in (data.get("meal_order") or [])]
    comidas_in = data.get("comidas") or {}
    keys = [k for k in meal_order if k in comidas_in]
    keys += [k for k in comidas_in if k not in keys]

    ids = set()
    for items in comidas_in.values():
        for it in (items or []):
            if it.get("alimento_id") is not None:
                try:
                    ids.add(int(it["alimento_id"]))
                except (TypeError, ValueError):
                    pass
    foods = {}
    if ids:
        async for f in db.foods.find({"id": {"$in": list(ids)}}, {"_id": 0}):
            foods[int(f["id"])] = f

    # Estructura para el módulo puro; los no encontrados van como comodín neutro
    # (no participa en bloques ni aporta) y se marcan para que el front los ignore.
    NEUTRO = {"categorias": "", "proteinas": 0, "hidratos": 0, "grasas": 0, "racion": 100}
    meals, encontrados = [], {}
    for k in keys:
        fila = []
        flags = []
        for it in (comidas_in.get(k) or []):
            aid = it.get("alimento_id")
            try:
                food = foods.get(int(aid)) if aid is not None else None
            except (TypeError, ValueError):
                food = None
            cant = float(it.get("cantidad_g") or 0)
            fila.append(((food or NEUTRO), max(0.0, cant)))
            flags.append(food is not None)
        meals.append((k, fila))
        encontrados[k] = flags

    macros_dia, pcts = _calibrar(meals)

    out = {}
    for k, fila in meals:
        items_out = []
        for i, (food, cant) in enumerate(fila):
            if not encontrados[k][i]:
                items_out.append({"alimento_id": (comidas_in.get(k) or [])[i].get("alimento_id"),
                                  "cantidad_g": cant, "macros_efectivos": None,
                                  "macros_brutos": None, "que_cuenta": None})
                continue
            ef = macros_dia[k][i]
            racion = float(food.get("racion") or 100) or 100.0
            scale = (cant / racion) if food.get("unidades") else (cant / 100.0)
            brutos = {"P": round(float(food.get("proteinas") or 0) * scale, 1),
                      "H": round(float(food.get("hidratos") or 0) * scale, 1),
                      "G": round(float(food.get("grasas") or 0) * scale, 1)}
            items_out.append({
                "alimento_id": int(food["id"]),
                "cantidad_g": cant,
                "macros_efectivos": {"P": round(ef["P"], 1), "H": round(ef["H"], 1), "G": round(ef["G"], 1)},
                "macros_brutos": brutos,
                "que_cuenta": {"P": ef["P"] > 0, "H": ef["H"] > 0, "G": ef["G"] > 0},
                "bloque": clasificar_bloque(food),
                # LA PUERTA DEL TERCIO, PARA QUE LA PANTALLA PUEDA DECIRLA (punto 133 del
                # 26-08). Sin esto el cartel de la calibracion le salia a todos los frutos
                # secos por igual y les prometia una proteina que aporta 0.
                "proteina_cuenta": la_proteina_llega_al_tercio(food),
                # Y el otro extremo: los 44 cereales y panes proteicos, a los que ya les
                # cuenta entera desde el primer gramo. El contador les enseñaba un tramo que
                # no les aplica. Ver `la_proteina_crece_con_el_dia`.
                "proteina_crece": la_proteina_crece_con_el_dia(food),
            })
        out[k] = items_out

    return {"comidas": out, "pcts": pcts}


# ==================== MENU TEMPLATES ====================

@router.post("/menu-options")
async def get_menu_options(data: dict, user = Depends(get_current_user)):
    """Genera hasta 3 opciones de menú autoajustadas a los macros de la comida.

    Body: {momento, macros_objetivo:{P,H,G}, es_vegano?, excluir_proteinas?}.
    Respeta las preferencias/alimentos evitados del usuario.
    """
    from meal_templates import generar_opciones_menu
    from meal_library import BIBLIOTECA_DE_CLIENTES

    # Biblioteca real en las sugerencias del CLIENTE: DESACTIVADA (petición 2026-07-12).
    # El coach la seguía usando desde su buscador (envía `fuentes` explícitamente),
    # hasta que el 06-08-2026 se apagó para todos con BIBLIOTECA_DE_CLIENTES.
    BIBLIOTECA_EN_SUGERENCIAS_CLIENTE = False

    momento = data.get("momento", "comida")
    macros_objetivo = data.get("macros_objetivo") or {"P": 40, "H": 15, "G": 8}
    es_vegano = bool(data.get("es_vegano", False))
    excluir_proteinas = data.get("excluir_proteinas") or []
    if data.get("fuentes"):
        fuentes = set(data["fuentes"])
    else:
        fuentes = {"recetario", "clientes"} if BIBLIOTECA_EN_SUGERENCIAS_CLIENTE else {"recetario"}
    # Con la biblioteca apagada manda el interruptor, aunque el que llama pida
    # "clientes" a las claras (el buscador del coach lo hacía).
    if not BIBLIOTECA_DE_CLIENTES:
        fuentes = {"recetario"}
    tipo = "peri" if (data.get("tipo") or "").strip().lower() == "peri" else "comida"

    # El coach puede buscar PARA un cliente: se usan las preferencias de ese cliente
    profile = None
    client_id = (data.get("client_id") or "").strip()
    if client_id and user.get("role") in ("admin", "trainer"):
        profile = await db.client_profiles.find_one({"id": client_id}, {"_id": 0})
    if not profile:
        profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    avoided_prefixes, avoided_keywords = build_avoided_filter(profile)

    from core.menus_vistos import anotar as _anotar_menus, vistos_de

    async def _anotar_vistos(perfil, momento_, plantillas_):
        """Lo propuesto queda apuntado para que la próxima vez salgan otros (dentro del
        mismo escalón de error: la variedad no cuesta precisión)."""
        total = await db.menu_templates.count_documents({"momento": momento_})
        await _anotar_menus(db, (perfil or {}).get("id"), momento_,
                            [p.get("plantilla_id") for p in plantillas_], total)

    from meal_library import buscar_en_biblioteca

    alimento_ids = data.get("alimento_ids") or []
    relajado = False
    opciones = []

    if alimento_ids:
        # Filtro "con estos alimentos" (AND estricto en ambas fuentes)
        if "clientes" in fuentes:
            opciones += await buscar_en_biblioteca(
                db, macros_objetivo, alimento_ids=alimento_ids, tipo=tipo, limit=6,
            )
        if "recetario" in fuentes:
            plantillas = await generar_opciones_menu(
                db, momento, macros_objetivo, es_vegano, excluir_proteinas,
                avoided_prefixes, avoided_keywords, required_food_ids=alimento_ids,
                vistos=vistos_de(profile, momento),
            )
            for p in plantillas:
                p["fuente"] = "recetario"
            opciones += plantillas
            await _anotar_vistos(profile, momento, plantillas)
        if not opciones and len(alimento_ids) > 1 and "clientes" in fuentes:
            vistos = set()
            for i in range(len(alimento_ids)):
                subset = alimento_ids[:i] + alimento_ids[i + 1:]
                for r in await buscar_en_biblioteca(db, macros_objetivo, alimento_ids=subset, tipo=tipo, limit=6):
                    if r["biblioteca_id"] not in vistos:
                        vistos.add(r["biblioteca_id"])
                        opciones.append(r)
            relajado = bool(opciones)
    else:
        # Sin filtro de alimentos: TODAS las plantillas del recetario que encajen
        # (y biblioteca real solo si la fuente está activa: hoy, solo el coach).
        if "recetario" in fuentes:
            plantillas = await generar_opciones_menu(
                db, momento, macros_objetivo, es_vegano, excluir_proteinas,
                avoided_prefixes, avoided_keywords,
                max_opciones=40, variar_proteinas=False,
            )
            for p in plantillas:
                p["fuente"] = "recetario"
            opciones += plantillas
        if "clientes" in fuentes:
            opciones += await buscar_en_biblioteca(db, macros_objetivo, tipo=tipo, limit=6)

    # Orden global: cuadradas primero, luego cercanía al objetivo
    obj = {m: float(macros_objetivo.get(m, 0) or 0) for m in ("P", "H", "G")}
    def _err(o):
        mt = o.get("macros_totales", {})
        return sum(abs(obj[m] - float(mt.get(m, 0) or 0)) for m in ("P", "H", "G"))
    opciones.sort(key=lambda o: (not o.get("cuadrada", False), _err(o)))
    opciones = opciones[:40]
    abc = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for i, o in enumerate(opciones):
        o["letra"] = abc[i] if i < len(abc) else str(i + 1)
    return {"opciones": opciones, "relajado": relajado}


async def _objetivo_de_comida(data: dict, user: dict, meal_key: str) -> dict:
    """Macros objetivo de una comida para los sugeridores de menús.

    Los manda la calculadora (reparto del día). Si llegan vacíos o a cero (bug de
    capturas 0P/0H/0G), se reparte aquí el día con la config que envía el front y
    se toma el target de esa comida, en vez de tratar el 0 como objetivo real.
    """
    objetivo_in = data.get("macros_objetivo") or {}
    obj = {m: float(objetivo_in.get(m, 0) or 0) for m in ("P", "H", "G")}
    if obj["P"] > 0 or obj["H"] > 0 or obj["G"] > 0:
        return obj
    if not meal_key:
        raise HTTPException(status_code=422, detail="No hay macros objetivo para esta comida")

    dist = await distribute_macros({
        "fecha": data.get("fecha"),
        "tipo_dia": data.get("tipo_dia", "entrenamiento"),
        "num_comidas": data.get("num_comidas", 4),
        "momento_entreno": data.get("momento_entreno", 1),
        "opcion_peri": data.get("opcion_peri", "intra_post"),
        "single_meal": (data.get("num_comidas", 4) == 1),
    }, user)
    fuente = dist.get("periworkout", {}) if meal_key in ("Intra", "Post") else dist.get("comidas", {})
    t = fuente.get(meal_key) or {}
    obj = {m: float(t.get(m, 0) or 0) for m in ("P", "H", "G")}
    if obj["P"] <= 0 and obj["H"] <= 0 and obj["G"] <= 0:
        raise HTTPException(status_code=422, detail="No hay macros objetivo para esta comida")
    return obj


@router.get("/menu-catalog")
async def menu_catalog(user = Depends(get_current_user)):
    """Listado ligero de TODOS los menús del recetario (pestaña "Recetario" del
    modal de menús). Sin cálculos: solo nombre, momentos y alimentos. Las
    cantidades se cuadran al elegirlo (POST /calculator/menu-apply).

    Deduplicado por nombre: los platos principales están guardados dos veces
    (comida y cena) y aquí salen una sola vez, con los dos momentos."""
    docs = await db.menu_templates.find(
        {}, {"_id": 0, "id": 1, "nombre": 1, "momento": 1, "items": 1, "fuente": 1,
             "foto": 1}
    ).to_list(2000)
    vistos = {}
    for d in docs:
        key = (d.get("nombre") or "").strip().lower()
        if not key:
            continue
        momento = d.get("momento")
        if key in vistos:
            if momento and momento not in vistos[key]["momentos"]:
                vistos[key]["momentos"].append(momento)
            continue
        vistos[key] = {
            "id": d["id"],
            "nombre": d["nombre"],
            "momento": momento,
            "momentos": [momento] if momento else [],
            "fuente": d.get("fuente"),
            # La foto de la receta, servida por la web de Jesús. Puede no estar: los
            # menús que salgan de los PDFs y de la cosecha no traen foto, y entonces
            # la tarjeta va sin ella. No se pone una genérica.
            "foto": d.get("foto"),
            "alimentos": [it.get("buscar", "") for it in d.get("items", []) if it.get("buscar")],
            # Si no lleva proteína no cubre una comida entera, y el sugeridor automático no
            # la propone (ver `meal_templates.generar_opciones_menu`). En el recetario sigue
            # estando: se marca para que el cliente sepa por qué se le va a quedar corta en
            # vez de llevarse el aviso sin explicación.
            "completa": any(it.get("rol") == "proteina" for it in d.get("items", [])),
        }
    menus = sorted(vistos.values(), key=lambda x: x["nombre"].lower())
    momentos = sorted({m for x in menus for m in x["momentos"]})
    return {"menus": menus, "total": len(menus), "momentos": momentos}


async def _items_con_macros(opcion: dict):
    """Los items de una comida ya cuadrada, con sus macros y lo que necesitan los steppers.

    Los macros de `_ajustar_plantilla` salen de escalar los efectivos por 100 g; aqui se
    recalculan a la cantidad final con `_efectivos_calma`, que es el MISMO motor que usa
    añadir o editar un alimento. Asi la tarjeta enseña justo lo que va a sumar la comida al
    volcarla, y no una aproximacion.

    Estaba escrito dentro de `menu-apply`. Se saca aqui porque `cuadrar-comida` (punto 4.9)
    necesita exactamente lo mismo, y tener dos copias de esto es tener dos formas de contar.
    """
    ids = [int(it["alimento_id"]) for it in opcion["items"] if it.get("alimento_id") is not None]
    foods = {}
    if ids:
        async for f in db.foods.find({"id": {"$in": ids}}, {"_id": 0}):
            foods[int(f["id"])] = f

    items = []
    tot = {"P": 0.0, "H": 0.0, "G": 0.0}
    for it in opcion["items"]:
        cantidad_g = float(it.get("cantidad_g") or 0)
        food = foods.get(int(it["alimento_id"])) if it.get("alimento_id") is not None else None
        if food:
            efectivos, brutos, cuenta = _efectivos_calma(food, cantidad_g)
        else:
            efectivos = {m: float(it.get("macros_efectivos", {}).get(m, 0) or 0) for m in ("P", "H", "G")}
            brutos, cuenta = dict(efectivos), {"P": True, "H": True, "G": True}
        for m in ("P", "H", "G"):
            tot[m] += efectivos[m]
        por_unidades = bool(food and food.get("unidades"))
        racion = float((food or {}).get("racion") or 100) or 100.0
        unidades_n = round(cantidad_g / racion, 2) if por_unidades else None
        items.append({
            "alimento_id": it.get("alimento_id"),
            "nombre": it.get("nombre") or (food or {}).get("nombre"),
            "cantidad_g": cantidad_g,
            "unidades_n": unidades_n,
            # «1 ud» no dice cuánto pesa una unidad, y sin eso el mismo alimento vale una cosa
            # pulsándolo y otra escribiéndolo (Jesús, 15-08, fallo 46). La equivalencia va
            # pegada a la unidad, como en la calculadora de ahora.
            "cantidad_display": f"{unidades_n:g} ud ({racion:g} g)" if unidades_n else f"{cantidad_g:g} g",
            "macros_efectivos": efectivos,
            "macros_brutos": brutos,
            "que_cuenta": cuenta,
            "rol": it.get("rol"),
            "categorias": (food or {}).get("categorias", ""),
            "racion": (food or {}).get("racion"),
            "unidades": por_unidades,
            "url": (food or {}).get("url"),
        })
    return items, {m: round(tot[m], 1) for m in ("P", "H", "G")}


@router.post("/cuadrar-comida")
async def cuadrar_comida(data: dict, user = Depends(get_current_user)):
    """Cuadra una lista de alimentos a los macros de una comida. Punto 4.9 del 09-08.

    Lo usa «Repetir de otro día». Hasta ahora esa pantalla escalaba las cantidades por el
    RATIO DE PROTEINA y ya: la proteina caia cerca del objetivo y los hidratos y la grasa
    donde salieran. En la prueba de Jesus, con un objetivo de 30 P / 20 H / 10 G:

        Proteina  34,2 / 30     sobran 4,2
        Hidratos  30,0 / 20     sobran 10
        Grasas     3,2 / 10     faltan 6,8

    O sea que no era «copiar tal cual» -- cambiaba las cantidades -- ni cuadrar. Lo peor de
    las dos cosas: ni es fiel al dia que copias ni te deja la comida en verde.

    Y por el recetario si cuadra, con `_ajustar_plantilla`. Dos caminos haciendo cosas
    distintas sin decirlo. Aqui se usa ESE MISMO motor, asi que los dos hacen lo mismo:
    parten de la cantidad minima de cada alimento y escalan hasta cuadrar P/H/G.

    `best_effort=True`: una comida copiada no se rechaza nunca. Si no cuadra del todo se
    devuelve lo mas cerca que se pueda y se dice con `cuadrada: false`.

    Body: {items: [{alimento_id, cantidad_g?}], macros_objetivo?, mealKey? + config del dia}
    """
    from meal_templates import MARGEN_MENU, _ajustar_plantilla

    crudos = data.get("items") or data.get("alimentos") or []
    items_in = [{"alimento_id": it.get("alimento_id"), "cantidad_g": it.get("cantidad_g"),
                 "nombre": it.get("nombre")}
                for it in crudos if isinstance(it, dict) and it.get("alimento_id") is not None]
    if not items_in:
        raise HTTPException(status_code=422, detail="No hay alimentos que cuadrar.")

    meal_key = (data.get("mealKey") or data.get("meal_key") or "").strip()
    obj = await _objetivo_de_comida(data, user, meal_key)

    # COMPLETAR LO QUE NO TIENE FUENTE (caso 28 de los 85; punto 14 del doc del 23-08).
    # Escalar no inventa macros: una comida copiada que es solo pollo no llega a los
    # hidratos de hoy ni con un kilo. Si al objetivo le falta un eje que ninguno de los
    # alimentos aporta, se pide al MISMO motor de sugerencias de la pantalla (uso 2) el
    # mejor candidato de ese eje y se añade marcado como `anadido_para_cuadrar`, para
    # que el front pueda decirlo. Después cuadra el conjunto entero como siempre.
    ids_puestos = {int(it["alimento_id"]) for it in items_in
                   if str(it.get("alimento_id")).lstrip("-").isdigit()}
    puestos = []
    if ids_puestos:
        async for f in db.foods.find({"id": {"$in": list(ids_puestos)}}, {"_id": 0}):
            puestos.append(f)
    from calma_suggest import _per100
    anadidos = []
    disponibles = await get_all_foods_cached(db)

    # OJO: las claves de la base son las castellanas (proteinas/hidratos/grasas); leer
    # P/H/G aqui da ceros SIN error y el filtro se lo traga todo (la trampa conocida).
    _CAMPO = {"P": "proteinas", "H": "hidratos", "G": "grasas"}

    def _densidad(f: dict, m: str) -> float:
        try:
            return float(_per100(f, _CAMPO[m]) or 0)
        except Exception:
            return 0.0

    async def _anadir_fuente(m: str, hueco_m: float) -> bool:
        """Añade el mejor candidato del motor que sea fuente de verdad del eje `m`."""
        # La petición ENFATIZA el eje que falta pero no pone los otros a cero: con
        # ceros el motor elige lo que menos estorba (vinagre, tomate), no lo que
        # alimenta; con los otros a un margen pequeño gana el que más aporta del eje.
        restante = {k: (max(hueco_m, 10.0) if k == m else min(float(obj.get(k) or 0), 5.0))
                    for k in ("P", "H", "G")}
        candidatos = sugerir_alimentos(
            alimentos_disponibles=disponibles, macros_restantes=restante,
            tipo_comida="normal", max_resultados=25,
            excluir_ids=list(ids_puestos) + [int(a["alimento_id"]) for a in anadidos])
        for s in candidatos:
            comida_s = s.get("alimento") or s
            id_s = comida_s.get("id") or s.get("alimento_id")
            if id_s is None or _densidad(comida_s, m) < 10:
                continue
            anadidos.append({"alimento_id": int(id_s), "cantidad_g": None,
                             "nombre": comida_s.get("nombre")})
            f = await db.foods.find_one({"id": int(id_s)}, {"_id": 0})
            if f:
                puestos.append(f)
            return True
        return False

    # Un eje esta cubierto si algun alimento de la comida es FUENTE de verdad de ese
    # macro (>= 8 g por 100): el pollo trae 2 de grasa, pero pedirle los 12 g del dia
    # es pedirle 600 g de pollo.
    for m in ("P", "H", "G"):
        if float(obj.get(m) or 0) <= 8:
            continue
        if any(_densidad(f, m) >= 8 for f in puestos):
            continue
        await _anadir_fuente(m, float(obj.get(m) or 0))

    # Cuadrar, y si un eje se queda corto porque su fuente tocó techo (el máximo por
    # alimento del motor de menús), una segunda fuente de ese eje y otra pasada. Dos
    # rondas bastan: más es señal de que el objetivo no es alcanzable y se devuelve
    # lo más cerca posible (best effort), dicho con `cuadrada: false`.
    opcion = None
    items: list = []
    totales: dict = {}
    for _ronda in range(3):
        opcion = await _ajustar_plantilla(db, {"items": items_in + anadidos}, obj, best_effort=True)
        if not opcion:
            raise HTTPException(status_code=422,
                                detail="No se pudo cuadrar: algún alimento ya no está en el catálogo.")
        items, totales = await _items_con_macros(opcion)
        cortos = [m for m in ("P", "H", "G")
                  if float(obj.get(m) or 0) > 8 and (obj[m] - totales[m]) > MARGEN_MENU]
        if not cortos or _ronda == 2:
            break
        alguno = False
        for m in cortos:
            alguno = await _anadir_fuente(m, obj[m] - totales[m]) or alguno
        if not alguno:
            break
    # Se marca lo que puso el motor y no el cliente, para que la pantalla lo diga.
    ids_anadidos = {int(a["alimento_id"]) for a in anadidos if a.get("alimento_id") is not None}
    for it in items:
        if int(it.get("alimento_id") or it.get("id") or 0) in ids_anadidos:
            it["anadido_para_cuadrar"] = True
    err = sum(abs(obj[m] - totales[m]) for m in ("P", "H", "G"))
    return {
        "items": items,
        "macros_totales": {**totales,
                           "kcal": round(totales["P"] * 4 + totales["H"] * 4 + totales["G"] * 9, 1)},
        "macros_objetivo": obj,
        "cuadrada": all(abs(obj[m] - totales[m]) <= MARGEN_MENU for m in ("P", "H", "G")),
        "err": round(err, 1),
        "origen": "repetido",
    }


@router.post("/menu-apply")
async def menu_apply(data: dict, user = Depends(get_current_user)):
    """Cuadra UN menú del recetario a los macros objetivo (al elegirlo en la
    pestaña "Recetario" del modal de menús).

    Body: {plantilla_id, macros_objetivo?: {P,H,G}, mealKey? + config del día}.
    Devuelve los items con las cantidades ya ajustadas (best effort: nunca rechaza
    el menú elegido) y sus macros calculados con el MISMO motor que añadir o editar
    un alimento, para que la tarjeta sea justo lo que sumará la comida al volcarla.
    """
    from meal_templates import MARGEN_MENU, _ajustar_plantilla

    plantilla_id = (data.get("plantilla_id") or "").strip()
    meal_key = (data.get("mealKey") or data.get("meal_key") or "").strip()
    plantilla = await db.menu_templates.find_one({"id": plantilla_id}, {"_id": 0})
    if not plantilla:
        raise HTTPException(status_code=404, detail="Menú no encontrado")

    obj = await _objetivo_de_comida(data, user, meal_key)
    opcion = await _ajustar_plantilla(db, plantilla, obj, best_effort=True)
    if not opcion:
        raise HTTPException(status_code=422, detail="No se pudo montar el menú (algún alimento ya no existe)")

    # Los macros de _ajustar_plantilla salen de escalar los efectivos por 100 g:
    # aquí se recalculan a la cantidad final con _efectivos_calma (igual que
    # /library-menus) y se añaden los campos que necesitan los steppers del front.
    ids = [int(it["alimento_id"]) for it in opcion["items"] if it.get("alimento_id") is not None]
    foods = {}
    if ids:
        async for f in db.foods.find({"id": {"$in": ids}}, {"_id": 0}):
            foods[int(f["id"])] = f

    items = []
    tot = {"P": 0.0, "H": 0.0, "G": 0.0}
    for it in opcion["items"]:
        cantidad_g = float(it.get("cantidad_g") or 0)
        food = foods.get(int(it["alimento_id"])) if it.get("alimento_id") is not None else None
        if food:
            efectivos, brutos, cuenta = _efectivos_calma(food, cantidad_g)
        else:
            efectivos = {m: float(it.get("macros_efectivos", {}).get(m, 0) or 0) for m in ("P", "H", "G")}
            brutos, cuenta = dict(efectivos), {"P": True, "H": True, "G": True}
        for m in ("P", "H", "G"):
            tot[m] += efectivos[m]
        por_unidades = bool(food and food.get("unidades"))
        racion = float((food or {}).get("racion") or 100) or 100.0
        unidades_n = round(cantidad_g / racion, 2) if por_unidades else None
        items.append({
            "alimento_id": it.get("alimento_id"),
            "nombre": it.get("nombre"),
            "cantidad_g": cantidad_g,
            "unidades_n": unidades_n,
            "cantidad_display": f"{unidades_n:g} ud" if unidades_n else f"{cantidad_g:g} g",
            "macros_efectivos": efectivos,
            "macros_brutos": brutos,
            "que_cuenta": cuenta,
            "rol": it.get("rol"),
            # para los steppers de cantidad del front al editar la comida
            "categorias": (food or {}).get("categorias", ""),
            "racion": (food or {}).get("racion"),
            "unidades": por_unidades,
            # los de marca llevan enlace a la ficha del producto: el front lo subraya
            "url": (food or {}).get("url"),
        })

    totales = {m: round(tot[m], 1) for m in ("P", "H", "G")}
    err = sum(abs(obj[m] - totales[m]) for m in ("P", "H", "G"))
    return {
        "plantilla_id": plantilla["id"],
        "nombre": plantilla["nombre"],
        "momento": plantilla.get("momento"),
        "fuente": plantilla.get("fuente"),
        "items": items,
        "macros_totales": {**totales,
                           "kcal": round(totales["P"] * 4 + totales["H"] * 4 + totales["G"] * 9, 1)},
        "macros_objetivo": obj,
        "cuadrada": all(abs(obj[m] - totales[m]) <= MARGEN_MENU for m in ("P", "H", "G")),
        "clavado": err <= 0.5,
        "err": round(err, 1),
        "tags": plantilla.get("tags", []),
        "origen": "recetario",
    }


async def _items_a_alimentos(items: List[dict]) -> List[dict]:
    """Los items de un menú, en la forma con la que viaja un alimento dentro de una dieta.

    El generador de menús devuelve lo justo (id, nombre, cantidad y unos macros escalados por
    100 g). Aquí se completan con lo que el alimento es de verdad -- si va por unidades, su
    ración, su categoría, su enlace -- y los macros se recalculan a la cantidad final con el
    mismo motor que usa añadir un alimento a mano, para que la comida sume lo mismo venga de
    donde venga.
    """
    ids = [int(it["alimento_id"]) for it in items if it.get("alimento_id") is not None]
    catalogo = {}
    if ids:
        async for f in db.foods.find({"id": {"$in": ids}}, {"_id": 0}):
            catalogo[int(f["id"])] = f

    salida = []
    for it in items:
        cantidad_g = float(it.get("cantidad_g") or 0)
        food = catalogo.get(int(it["alimento_id"])) if it.get("alimento_id") is not None else None
        if food:
            efectivos, brutos, cuenta = _efectivos_calma(food, cantidad_g)
        else:
            efectivos = {m: float((it.get("macros_efectivos") or {}).get(m, 0) or 0)
                         for m in ("P", "H", "G")}
            brutos, cuenta = dict(efectivos), {"P": True, "H": True, "G": True}
        salida.append({
            "alimento_id": it.get("alimento_id"),
            "nombre": it.get("nombre"),
            "cantidad_g": cantidad_g,
            "macros_efectivos": efectivos,
            "macros_brutos": brutos,
            "que_cuenta": cuenta,
            "rol": it.get("rol"),
            "categorias": (food or {}).get("categorias", ""),
            "racion": (food or {}).get("racion"),
            "unidades": bool(food and food.get("unidades")),
            "url": (food or {}).get("url"),
        })
    return salida


@router.post("/montar-dia")
async def montar_dia(data: dict, user = Depends(get_current_user)):
    """Llena un día entero de comidas, cuadradas a los macros de cada una.

    Es lo que ve el cliente nada más terminar el alta: antes se quedaba mirando unos números
    y una pantalla en blanco, y montar la primera dieta desde cero, sin conocer la app, es
    justo donde se cae la gente. Ahora se le da el día hecho para que lo acepte o lo cambie.

    Y lo que cambie vale doble: cada dieta guardada alimenta la frecuencia de alimentos, que
    es de donde salen luego las sugerencias. O sea que aceptando o tocando estas comidas nos
    está diciendo lo que le gusta sin que haya que preguntárselo.

    Body: la config del día (tipo_dia, num_comidas, momento_entreno, opcion_peri) + `fecha`
    y `guardar` opcional. Con `guardar: true` deja la dieta puesta en esa fecha.
    """
    from meal_templates import generar_opciones_menu

    # Sin fecha, el dia de ESPAÑA, no el de UTC (bloque F, 23-08): un alta a las 00:30 de
    # aqui escribia su primera dieta en AYER y el cliente estrenaba la app con hoy vacio.
    # Lo suyo es que el front mande la fecha del cliente; esto es la red de seguridad.
    from core.tiempo import hoy_madrid
    fecha = (data.get("fecha") or hoy_madrid().isoformat()).strip()
    dist = await distribute_macros({
        "fecha": fecha,
        "tipo_dia": data.get("tipo_dia", "entrenamiento"),
        "num_comidas": data.get("num_comidas", 4),
        "momento_entreno": data.get("momento_entreno", 1),
        "opcion_peri": data.get("opcion_peri", "intra_post"),
        "single_meal": data.get("single_meal"),
    }, user)

    objetivos = dict(dist.get("comidas") or {})
    peri = dist.get("periworkout") or {}

    comidas: Dict[str, Any] = {}
    usados: set = set()   # un menú no se repite en el mismo día: comer dos veces lo mismo
                          # el primer día es la peor carta de presentación posible
    montadas, vacias = [], []

    from core.menus_vistos import anotar as _anotar_menus, vistos_de
    _perfil_dia = await db.client_profiles.find_one(
        {"user_id": user["id"]},
        {"_id": 0, "id": 1, "menus_vistos": 1, "avoided_categories": 1, "avoided_keywords": 1})
    _vistos_comida = vistos_de(_perfil_dia, "comida")
    _propuestos = []

    # LO QUE NO PUEDE COMER MANDA SOBRE EL MENÚ (bloque 3 del doc del 18-08). El día que
    # se monta solo salía de las recetas que cuadran y de nada más: a una intolerante total
    # a la lactosa se le plantaba queso en su primera comida, el mismo día que acaba de
    # decirnos que no lo tolera. Y es el primer día, que es el que decide si vuelve.
    #
    # El filtro es el mismo que usa el resto de la calculadora, así que lo que aquí se
    # descarta es exactamente lo que no le sale al buscar a mano.
    _evitar_prefijos, _evitar_palabras = build_avoided_filter(_perfil_dia)

    for meal_key, obj in objetivos.items():
        objetivo = {"P": float(obj.get("P") or 0), "H": float(obj.get("H") or 0),
                    "G": float(obj.get("G") or 0)}
        if sum(objetivo.values()) <= 0:
            continue
        try:
            # Los que ya se le propusieron otras veces van detrás, dentro de su mismo
            # escalón de error: el día que se monta solo no le sale siempre lo mismo.
            opciones = await generar_opciones_menu(
                db, "comida", objetivo, vistos=_vistos_comida)
        except Exception:
            opciones = []
        # Primero las que cuadran, y de esas la que no se haya usado ya hoy y no lleve
        # nada de lo que no puede comer. Se resuelve cada candidata antes de elegirla:
        # el menú trae ids, y para saber si lleva un lácteo hay que mirar el alimento.
        candidatas = [o for o in opciones if o.get("cuadrada")] + [o for o in opciones if not o.get("cuadrada")]
        elegida, alimentos_elegidos = None, []
        for candidata in candidatas:
            if (candidata.get("nombre") or "") in usados:
                continue
            alimentos = await _items_a_alimentos(candidata.get("items") or [])
            if any(food_is_avoided(a, _evitar_prefijos, _evitar_palabras) for a in alimentos):
                continue
            elegida, alimentos_elegidos = candidata, alimentos
            break
        if not elegida:
            vacias.append(meal_key)
            comidas[meal_key] = {"alimentos": []}
            continue
        usados.add(elegida.get("nombre") or "")
        _propuestos.append(elegida.get("plantilla_id"))
        _vistos_comida = _vistos_comida | {elegida.get("plantilla_id")}
        comidas[meal_key] = {
            "alimentos": alimentos_elegidos,
            "menu_nombre": elegida.get("nombre"),
        }
        montadas.append({"comida": meal_key, "menu": elegida.get("nombre"),
                         "cuadrada": bool(elegida.get("cuadrada"))})

    if _propuestos:
        await _anotar_menus(db, (_perfil_dia or {}).get("id"), "comida", _propuestos,
                            await db.menu_templates.count_documents({"momento": "comida"}))

    # El peri no se monta: son bebidas y geles muy de cada uno, y llenárselo a ciegas el
    # primer día es más ruido que ayuda. Se deja con su objetivo, listo para que lo complete.
    for meal_key in peri:
        comidas.setdefault(meal_key, {"alimentos": []})

    if data.get("guardar"):
        await db.diets.update_one(
            {"user_id": user["id"], "fecha": fecha},
            {"$set": {
                "user_id": user["id"], "fecha": fecha, "comidas": comidas,
                "tipo_dia": data.get("tipo_dia", "entrenamiento"),
                "num_comidas": data.get("num_comidas", 4),
                "momento_entreno": data.get("momento_entreno", 1),
                "opcion_peri": data.get("opcion_peri", "intra_post"),
                "montada_automaticamente": True,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True)

    return {
        "fecha": fecha,
        "comidas": comidas,
        "objetivos": objetivos,
        "montadas": montadas,
        "sin_menu": vacias,
        "guardada": bool(data.get("guardar")),
    }


@router.post("/library-search")
async def library_search(data: dict, user = Depends(get_current_user)):
    """Busca menús REALES (biblioteca minada de clientes, db.meal_library) que
    contengan los alimentos indicados y cuadren/ajusten a los macros objetivo.

    Body: {macros_objetivo: {P,H,G}, alimento_ids?: [int], tipo?: 'comida'|'peri', limit?: int}
    """
    from meal_library import buscar_en_biblioteca, BIBLIOTECA_DE_CLIENTES

    if not BIBLIOTECA_DE_CLIENTES:
        return {"opciones": [], "total": 0, "biblioteca_apagada": True}

    macros_objetivo = data.get("macros_objetivo") or {}
    alimento_ids = data.get("alimento_ids") or []
    tipo = (data.get("tipo") or "comida").strip().lower()
    if tipo not in ("comida", "peri"):
        tipo = "comida"
    limit = min(int(data.get("limit") or 5), 15)

    resultados = await buscar_en_biblioteca(
        db, macros_objetivo, alimento_ids=alimento_ids, tipo=tipo, limit=limit,
    )
    relajado = False
    if not resultados and len(alimento_ids) > 1:
        # AND estricto sin resultados: relajar a n-1 alimentos (se avisa al front)
        for i in range(len(alimento_ids)):
            subset = alimento_ids[:i] + alimento_ids[i + 1:]
            parciales = await buscar_en_biblioteca(
                db, macros_objetivo, alimento_ids=subset, tipo=tipo, limit=limit,
            )
            resultados.extend(r for r in parciales if r["biblioteca_id"] not in {x["biblioteca_id"] for x in resultados})
        resultados.sort(key=lambda r: (not r["cuadrada"], -r["popularidad"]["clientes"]))
        resultados = resultados[:limit]
        relajado = bool(resultados)
    return {"resultados": resultados, "relajado": relajado}


# ── Biblioteca de menús reales: sugeridor por CERCANÍA (sin reescalar) ────────

# mealKey de la app -> tipo de comida de la biblioteca. Días de 5-6 comidas se
# mapean a "Comida 4" (la casilla más parecida); Intra/Post comparten "Peri".
_LIBRARY_TIPOS = {"C1": "Comida 1", "C2": "Comida 2", "C3": "Comida 3", "C4": "Comida 4",
                  "C5": "Comida 4", "C6": "Comida 4", "Intra": "Peri", "Post": "Peri"}
_LIBRARY_MARGEN_DEFAULT = 5.0
_LIBRARY_MARGEN_MAX = 15.0
_LIBRARY_CANDIDATOS_MAX = 4000
_LIBRARY_TRABAJO_MAX = 300  # solo los mejores N se materializan con macros por item

# Lo que convierte un menú en UNA COMIDA y no en un desayuno o una merienda: una fuente
# proteica sólida o un plato preparado. Deja fuera a propósito la proteína en polvo (4) y
# los lácteos (5): un batido o un yogur con cereales cuadran los macros igual de bien, pero
# nadie llama a eso "la comida". La biblioteca guarda en qué NÚMERO de comida se comió cada
# menú, no a qué hora ni cuándo entrenaba esa persona, así que sin esto la Comida 2 de quien
# desayuna tarde acaba ofreciéndose como la Comida 2 de quien acaba de entrenar.
_CATS_DE_PLATO = ['1', '2', '3', '6', '10', '28', '32', '39', '40', '45', '49', '50', '53']


@router.post("/library-menus")
async def library_menus(data: dict, user = Depends(get_current_user)):
    """Sugeridor "elige tu menú" sobre la BIBLIOTECA REAL (db.meal_library, 266k
    comidas de clientes ya cuadradas con el método).

    Cercanía + PALANCAS (doc "FLUJO COMPLETO" 17-07, sustituye al "tal cual" del
    16-07): se buscan los menús más cercanos al objetivo y se AJUSTAN con los
    drivers limpios del menú (la palanca de proteína ±20 g, la de hidratos ±30,
    la de grasa ±8, sin descuadrar el resto). El menú se devuelve con las
    cantidades ya ajustadas; si un menú no tiene palanca útil, se ofrece tal
    cual siempre que entre en ±margen. Los alimentos por unidades (huevo,
    yogur...) nunca actúan de palanca (no se parten unidades).
    El objetivo lo define la calculadora (reparto del día); si llega vacío o a cero
    (bug de capturas 0P/0H/0G), se reparte aquí el día con /distribute y se toma
    el target de la comida en vez de tratar 0 como objetivo real.

    Body: {mealKey, macros_objetivo?: {P,H,G}, margen?: 1-15 (def 5),
           orden?: 'cuadrado'|'usado', limit?: <=60,
           fecha?, tipo_dia?, num_comidas?, momento_entreno?, opcion_peri? (fallback)}
    """
    from meal_library import BIBLIOTECA_DE_CLIENTES

    meal_key = (data.get("mealKey") or data.get("meal_key") or "").strip()
    tipo_comida = data.get("tipo_comida") or _LIBRARY_TIPOS.get(meal_key)
    if tipo_comida not in ("Comida 1", "Comida 2", "Comida 3", "Comida 4", "Peri"):
        raise HTTPException(status_code=422, detail="mealKey o tipo_comida inválido")

    # Biblioteca apagada (06-08-2026): no hay menús de clientes que ofrecer. Se
    # responde con la lista vacía y la bandera, para que quien llame enseñe el
    # recetario en su lugar en vez de un hueco sin explicación.
    if not BIBLIOTECA_DE_CLIENTES:
        return {"menus": [], "total": 0, "biblioteca_apagada": True,
                "objetivo": await _objetivo_de_comida(data, user, meal_key)}

    # El objetivo lo manda la calculadora; el 0/0/0 se resuelve repartiendo el día.
    obj = await _objetivo_de_comida(data, user, meal_key)

    try:
        margen = float(data.get("margen") or _LIBRARY_MARGEN_DEFAULT)
    except (TypeError, ValueError):
        margen = _LIBRARY_MARGEN_DEFAULT
    margen = max(1.0, min(_LIBRARY_MARGEN_MAX, margen))
    orden = "usado" if (data.get("orden") or "").strip().lower() == "usado" else "cuadrado"
    # El tope estaba en 60 y el front pedía 40, así que de ±4 en adelante siempre se
    # veían los mismos 40 por muy alto que se pusiera el margen: el slider no hacía
    # nada visible. Con 150 la lista no se recorta en la práctica (el caso medido
    # llega a 96 con ±15) y ampliar el margen se nota.
    limit = max(1, min(int(data.get("limit") or 30), 150))

    # Preselección ampliada por el rango de las palancas: un menú a más de ±margen
    # puede acabar dentro tras ajustar su driver (P ±20, H ±30, G ±8).
    from meal_library import AJUSTE_MAX, _ajustar_menu
    from meal_builder import get_effective_macros_per_100g
    q = {"tipo_comida": tipo_comida}
    # Los menús de clientes son de relleno y van SIEMPRE con filtro (punto 67 del
    # 07-08): solo los que llevan verdura, no son una lista de botes y tienen un
    # número razonable de ingredientes. Lo marca la cosecha (_cosechar_menus.py).
    q["calidad.pasa"] = True
    # Y sin repetir: 10.304 de los 23.681 llevan los mismos alimentos que otro y solo
    # cambian las cantidades... que aquí se reajustan con las palancas de todas
    # formas. Al cliente le salía tres veces la misma comida con otros gramos.
    q["repetido_de"] = {"$exists": False}
    # La preselección NO depende del margen elegido: se busca siempre con el margen
    # máximo y el margen solo filtra al final.
    #
    # El margen es un TECHO, no un objetivo: pedir ±10 quiere decir «acepto hasta 10
    # de desfase», así que todo lo que cuadra a ±5 también vale a ±10. Si la búsqueda
    # se estrechara con el margen, ampliarlo cambiaría el conjunto entero en vez de
    # agrandarlo, y pasaba justo eso: al subir de ±4 a ±5 aparecía un menú y
    # DESAPARECÍA otro que ya estaba. Con la preselección fija, ampliar el margen solo
    # puede añadir.
    for m in ("P", "H", "G"):
        q[f"macros.{m}"] = {"$gte": obj[m] - _LIBRARY_MARGEN_MAX - AJUSTE_MAX[m],
                            "$lte": obj[m] + _LIBRARY_MARGEN_MAX + AJUSTE_MAX[m]}
    # Se pide en DOS vueltas a propósito. La primera trae solo lo que hace falta para
    # ORDENAR (macros y popularidad); los ingredientes se piden abajo, y solo de los 300
    # que se van a trabajar de verdad. La lista de `alimentos` es casi todo el peso del
    # documento y de 4.000 candidatos se materializan 300: traerla para los 4.000 costaba
    # 86 s contra el Atlas de dev (4,5 s contra el Mongo de prod, que está en la misma
    # máquina que la app). Medido el 09-08-2026 con el mismo plan de ejecución en las dos
    # -- no es la consulta, es lo que viaja por el cable. Y el modal girando minuto y
    # medio se cuenta como "la biblioteca no devuelve nada", que es justo lo que se estaba
    # investigando. Los índices ya están: tipo_comida + macros.P/H/G para esta, id para la
    # segunda.
    campos_orden = {"_id": 0, "id": 1, "macros": 1, "veces": 1, "usos": 1,
                    "clientes": 1, "usos_calma": 1, "fuente": 1}
    campos = {"_id": 0, "id": 1, "macros": 1, "macros_reales": 1, "veces": 1,
              "usos": 1, "clientes": 1, "usos_calma": 1, "fuente": 1, "menu": 1,
              # `nombre` es el título que le pone el equipo desde el panel. Sin pedirlo
              # aquí, la respuesta lo lleva siempre a nulo aunque esté guardado.
              "origen": 1, "alimentos": 1, "alimento_ids": 1, "nombre": 1}
    candidatos = await db.meal_library.find(q, campos_orden).to_list(_LIBRARY_CANDIDATOS_MAX)

    # Las comidas de los menús de Jesús se piden APARTE, y no es un capricho: la
    # consulta de arriba corta a 4.000 y Mongo los devuelve en orden natural, así que
    # las 73 de ELM -- que se insertaron las últimas de 23.900 -- no entraban nunca en
    # el corte. Se veía como si no existieran: ni con el objetivo clavado salía una.
    q_jesus = dict(q)
    q_jesus["fuente"] = "elm_menus"
    de_jesus = await db.meal_library.find(q_jesus, campos_orden).to_list(500)
    ya = {c["id"] for c in candidatos}
    candidatos += [c for c in de_jesus if c["id"] not in ya]

    # Cuando la preselección viene vacía hay dos motivos que desde fuera se ven IGUAL
    # (200 OK y la lista a cero): que no haya menús para ese objetivo, o que a esta base
    # no se le haya pasado nunca la cosecha. Y el segundo es el que ha pasado de verdad:
    # `calidad.pasa` no viene con el menú, lo calcula backend/_cosechar_menus.py, y en
    # producción no se había corrido nunca. Medido el 09-08-2026: 0 de 266.170 menús lo
    # tenían, así que el `q["calidad.pasa"] = True` de arriba dejaba la consulta en cero
    # con cualquier objetivo -- el de Jesús (Comida 1, 30 P / 20 H / 10 G) daba 48.085
    # candidatos sin ese filtro y 0 con él. Corrida la cosecha son 42.364 los que pasan.
    #
    # Que un dato DERIVADO sin calcular se vea igual que "no hay nada" costó dos vueltas
    # del documento (puntos 4.8 y 10.3), así que ahora se distingue: se avisa en el log y
    # se dice en la respuesta. La consulta no se relaja sola a propósito: sin el filtro
    # vuelven los batidos y las listas de botes que hicieron apagar la biblioteca el
    # 06-08. Lo que hay que hacer es correr la cosecha, y así se sabe.
    sin_cosechar = False
    if not candidatos and await db.meal_library.find_one({}, {"_id": 1}):
        sin_cosechar = await db.meal_library.find_one({"calidad.pasa": True}, {"_id": 1}) is None
        if sin_cosechar:
            import logging
            logging.getLogger("uvicorn.error").warning(
                "meal_library sin cosechar en esta base: ningún menú tiene calidad.pasa, "
                "así que /library-menus devolverá vacío siempre. Corre backend/_cosechar_menus.py --apply."
            )

    def _err(c):
        mm = c.get("macros", {})
        return sum(abs(obj[m] - float(mm.get(m, 0) or 0)) for m in ("P", "H", "G"))

    def _desfase(c):
        """El PEOR macro, que es lo que mide el margen. Ordenar por esto y no por la
        suma es lo que hace que ampliar el margen no descoloque nada: un menú que
        entra a ±5 tiene su peor macro en 5 o menos, y todo lo que aparezca al subir a
        ±10 lo tiene por encima de 5, así que va detrás. Con la suma no se cumple --
        un menú de (4,4,4) suma 12 y entra a ±5, y otro de (6,0,0) suma 6 y solo entra
        a ±6, pero se colaría por delante y echaría a alguien de la lista."""
        mm = c.get("macros", {})
        return max(abs(obj[m] - float(mm.get(m, 0) or 0)) for m in ("P", "H", "G"))

    def _de_jesus(c):
        """Las comidas de los menús de ELM van por delante de las de los clientes.
        Son material suyo, cocinado y publicado; las otras son de relleno."""
        return c.get("fuente") == "elm_menus"

    def _gente(c):
        """Cuánta GENTE DISTINTA lo ha montado aquí. Es el criterio del punto 71 y no
        es lo mismo que las veces: un menú que han montado 30 personas es bueno; uno
        que una persona ha repetido 30 veces solo dice que a esa persona le gusta."""
        return int(c.get("clientes") or 0)

    def _veces(c):
        """Las veces que se ha montado en esta app. `veces` es el contador viejo que
        vino del CSV de la calculadora antigua, donde no consta quién montó qué, y
        por eso va el último: desempata entre menús que aquí no ha tocado nadie."""
        return int(c.get("usos") or 0), int(c.get("veces") or c.get("usos_calma") or 0)

    if orden == "usado":
        candidatos.sort(key=lambda c: (not _de_jesus(c), -_gente(c), -_veces(c)[0], _desfase(c)))
    else:
        # Dentro de lo que ya cuadra, el desfase no lo nota nadie -- y ordenar por él
        # al detalle deja el criterio de la gente sin estrenar, porque casi todos
        # cuadran al decimal. Se agrupa por gramo entero y manda la gente.
        candidatos.sort(key=lambda c: (round(_desfase(c)), not _de_jesus(c), -_gente(c),
                                       -_veces(c)[0], _err(c)))
    # Segunda vuelta: ya ordenados, se piden los ingredientes SOLO de los que se van a
    # trabajar. Se respeta el orden que acaba de salir, que Mongo no garantiza ninguno.
    orden_ids = [c["id"] for c in candidatos[:_LIBRARY_TRABAJO_MAX]]
    completos = {}
    if orden_ids:
        async for d in db.meal_library.find({"id": {"$in": orden_ids}}, campos):
            completos[d["id"]] = d
    trabajo = [completos[i] for i in orden_ids if i in completos]

    # Preferencias del usuario (alimentos evitados) + catálogo de los candidatos
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    avoided_prefixes, avoided_keywords = build_avoided_filter(profile)
    ids = {aid for c in trabajo for aid in c.get("alimento_ids", [])}
    foods = {}
    if ids:
        async for f in db.foods.find({"id": {"$in": list(ids)}}, {"_id": 0}):
            foods[int(f["id"])] = f

    menus = []
    for c in trabajo:
        # Paso 1: resolver alimentos y filtrar evitados; preparar items para las palancas.
        alimentos_c = c.get("alimentos", [])
        food_list = []
        valido = True
        for a in alimentos_c:
            food = foods.get(int(a["alimento_id"]))
            if not food or food_is_avoided(food, avoided_prefixes, avoided_keywords):
                valido = False
                break
            food_list.append(food)
        if not valido or not alimentos_c:
            continue

        # Paso 2: MOTOR DE PALANCAS. Los alimentos por unidades nunca son driver
        # (no se parten unidades): se degradan a "mixto" y no se tocan.
        adj_items = []
        for a, food in zip(alimentos_c, food_list):
            driver = a.get("driver", "mixto")
            if a.get("unidades_n") or food.get("unidades"):
                driver = "mixto"
            adj_items.append({
                "cantidad_g": float(a["cantidad_g"]),
                "driver": driver,
                "_ef": get_effective_macros_per_100g(food),
            })
        ajuste = _ajustar_menu(adj_items, obj, c.get("macros", {}))
        if ajuste:
            # Las palancas escalan fino y dejan cantidades como 182,5: al cliente se le dan
            # números redondos, así que se bajan a su múltiplo y los macros del menú se
            # recalculan con las cantidades finales. Se hace ANTES de mirar el margen (abajo)
            # para no aceptar un menú por unos macros que luego no son los que se enseñan.
            finales = [_redondear_para_el_cliente(food, it["cantidad_g"])
                       for food, it in zip(food_list, ajuste["items"])]
            metodo_final = {m: 0.0 for m in ("P", "H", "G")}
            for it, cant in zip(adj_items, finales):
                for m in ("P", "H", "G"):
                    metodo_final[m] += (it["_ef"].get(m, 0) or 0) * cant / 100.0
            metodo_final = {m: round(v, 1) for m, v in metodo_final.items()}
        else:
            finales = [float(a["cantidad_g"]) for a in alimentos_c]
            metodo_final = {m: float(c.get("macros", {}).get(m, 0) or 0) for m in ("P", "H", "G")}
        ajustado = bool(ajuste) and any(
            abs(f - float(a["cantidad_g"])) >= 1 for f, a in zip(finales, alimentos_c))

        # Paso 3: el criterio del margen se aplica a lo que el cliente SE LLEVA
        # (tras palancas). Sin ajuste posible, el menú original debe entrar solo.
        if any(abs(obj[m] - metodo_final[m]) > margen for m in ("P", "H", "G")):
            continue

        # Paso 4: items con el MISMO motor que añadir/editar alimentos: lo que se
        # muestra aquí es exactamente lo que contará la comida al volcarlo.
        items = []
        tot = {"P": 0.0, "H": 0.0, "G": 0.0}
        for a, food, cantidad_g in zip(alimentos_c, food_list, finales):
            efectivos, brutos, cuenta = _efectivos_calma(food, cantidad_g)
            for m in ("P", "H", "G"):
                tot[m] += efectivos[m]
            sin_cambio = abs(cantidad_g - float(a["cantidad_g"])) < 0.5
            # Con la equivalencia al lado de la unidad (fallo 46): «2 ud (10 g)».
            _racion = float(food.get("racion") or 0)
            display = (f"{a['unidades_n']} ud" + (f" ({_racion:g} g)" if _racion > 0 else "")
                       if (a.get("unidades_n") and sin_cambio)
                       else f"{cantidad_g:g} g")
            items.append({
                "alimento_id": int(a["alimento_id"]),
                "nombre": food.get("nombre", a.get("nombre", "")),
                "cantidad_g": cantidad_g,
                "unidades_n": a.get("unidades_n") if sin_cambio else None,
                "cantidad_display": display,
                "macros_efectivos": efectivos,
                "macros_brutos": brutos,
                "que_cuenta": cuenta,
                # para los steppers de cantidad del front al editar la comida
                "categorias": food.get("categorias", ""),
                "racion": food.get("racion"),
                "unidades": bool(food.get("unidades")),
                # los de marca llevan enlace a la ficha del producto: el front lo subraya
                "url": food.get("url"),
            })

        err = sum(abs(obj[m] - metodo_final[m]) for m in ("P", "H", "G"))
        # El peor macro: es lo que mide el margen y con lo que se ordena, para que
        # ampliar el margen solo pueda añadir menús al final y nunca mover los de
        # arriba. Ver _desfase() más arriba.
        desfase = max(abs(obj[m] - metodo_final[m]) for m in ("P", "H", "G"))
        menus.append({
            "biblioteca_id": c["id"],
            "desfase": round(desfase, 1),
            "items": items,
            # ¿Es una comida de verdad o un desayuno/merienda que cuadra por macros?
            "es_plato": any(cat_in_list(get_categoria_principal(f), _CATS_DE_PLATO) for f in food_list),
            # macros del método que el cliente SE LLEVA (tras palancas)
            "macros_metodo": metodo_final,
            # macros del menú base tal cual se guardó (sin ajustar)
            "macros_base": c.get("macros", {}),
            # macros de etiqueta (reales) del menú base
            "macros_reales": c.get("macros_reales", {}),
            # lo que sumará la comida al volcar los items (motor actual)
            "macros_totales": {"P": round(tot["P"], 1), "H": round(tot["H"], 1), "G": round(tot["G"], 1),
                               "kcal": round(tot["P"] * 4 + tot["H"] * 4 + tot["G"] * 9)},
            "veces": int(c.get("veces", 0) or 0),
            # Cuánta gente distinta lo ha montado en esta app. Es lo que se le enseña
            # al cliente, porque es lo que de verdad dice si un menú vale: `veces`
            # cuenta repeticiones, y una persona repitiendo 30 veces no es una señal.
            "personas": int(c.get("clientes") or 0),
            "origen": c.get("origen", "cliente"),
            # De dónde sale: "elm_menus" son las comidas de los menús de Jesús y
            # "clientes" lo que monta la gente. Al cliente se le dice cuál es cuál.
            "de_jesus": c.get("fuente") == "elm_menus",
            "menu_elm": c.get("menu"),
            # El título que le haya puesto el equipo desde el panel. Estos menús nacen sin
            # nombre -- son la lista de lo que llevan --, así que casi ninguno lo tiene.
            "nombre": c.get("nombre"),
            "ajustado": ajustado,
            "cuadrada": bool(ajuste and ajuste.get("cuadrada")),
            "clavado": err <= 0.5,
            "err": round(err, 1),
            "fuente": "biblioteca",
        })

    # ── Dos filtros de sentido común, ambos con red: solo se aplican si después de
    # aplicarlos SIGUE habiendo menús de sobra. Antes que quedarse corto, se relajan.

    # 1) Coherencia con el momento del día. Solo la primera comida admite formato
    # desayuno, y solo si NO entrena en ayunas: si entrena antes de desayunar, su C1 es
    # la comida de después del entreno y toca plato, no yogur con cereales. El peri se
    # queda fuera de esta regla (son bebidas y batidos por definición).
    momento = int(data.get("momento_entreno", 1) or 0)
    admite_desayuno = (meal_key == "C1" and momento != 0)
    solo_platos = False
    if tipo_comida != "Peri" and not admite_desayuno:
        platos = [m for m in menus if m["es_plato"]]
        if len(platos) >= limit:
            menus, solo_platos = platos, True

    # 2) Las variantes (mismo menú real con las cantidades escaladas, veces=0) son el
    # relleno para objetivos que no encuentran nada: si hay comida de cliente de sobra,
    # no se ofrecen.
    de_cliente = [m for m in menus if m.get("origen") != "variante"]
    solo_cliente = len(de_cliente) >= limit
    if solo_cliente:
        menus = de_cliente

    # Orden final sobre el resultado REAL (tras palancas), no sobre el menú base.
    # Manda la gente distinta, igual que en la preselección: si aquí se volviera a
    # ordenar solo por `veces` y por error, se perdería por el camino todo lo que se
    # ha hecho arriba.
    if orden == "usado":
        # Aquí manda la gente porque es lo que se ha pedido, así que ampliar el margen
        # sí puede reordenar: si entra un menú que ha montado más gente, se pone
        # delante. Es lo esperable en este modo, no en el de por defecto.
        menus.sort(key=lambda m: (not m["de_jesus"], -m["personas"], -m["veces"], m["desfase"]))
    else:
        # Por desfase (el peor macro) y no por la suma: así, ampliar el margen solo
        # añade menús al final y no mueve ni uno de los de arriba. Comprobado de ±1 a
        # ±15 en Comida 1 y Comida 2: ningún menú desaparece al ampliar.
        #
        # Y dentro de lo que cuadra igual de bien, primero lo de Jesús: son comidas
        # suyas, publicadas en sus menús, y las de los clientes son de relleno.
        menus.sort(key=lambda m: (round(m["desfase"]), not m["de_jesus"], -m["personas"],
                                  -m["veces"], m["err"]))
    total = len(menus)   # menús ofrecibles: cuadran a ±margen y pasan los dos filtros
    menus = menus[:limit]

    return {
        "menus": menus,
        "total": total,
        "objetivo": obj,
        "margen": margen,
        "orden": orden,
        "tipo_comida": tipo_comida,
        # Para saber por qué salió lo que salió sin tener que adivinarlo. `sin_cosechar`
        # es la diferencia entre "no hay menús para este objetivo" y "a esta base nunca
        # se le pasó la cosecha", que hasta el 09-08-2026 se veían igual.
        "filtros": {"solo_platos": solo_platos, "solo_cliente": solo_cliente,
                    "sin_cosechar": sin_cosechar},
    }


@router.get("/test-templates")
async def test_templates(user = Depends(get_current_user)):
    """Test endpoint para verificar templates de menú."""
    from meal_templates import generar_opciones_menu

    target = {"P": 40, "H": 45, "G": 12}
    return {
        "desayuno": await generar_opciones_menu(db, "desayuno", target),
        "comida": await generar_opciones_menu(db, "comida", target),
    }

# ==================== CONFIG ====================

@router.get("/food-config/{food_id}")
async def get_food_config_endpoint(food_id: int, user = Depends(get_current_user)):
    """Obtiene la configuración (min/max) de un alimento."""
    food = await db.foods.find_one({"id": food_id}, {"_id": 0})
    if not food:
        raise HTTPException(status_code=404, detail="Alimento no encontrado")
    
    config = get_food_config(food)
    return {
        "food_id": food_id,
        "nombre": food.get("nombre"),
        "config": config
    }


# ==================== TARGET CALCULATOR ====================

@router.post("/targets")
async def calculate_client_targets(data: dict, user = Depends(get_current_user)):
    """
    Calcula los macros objetivo del cliente basado en peso, sexo, %graso y objetivo.
    Usa las tablas del método (macros_tables.json).

    Body: {"peso": 80, "sexo": "hombre", "porcentaje_graso": 20, "objetivo": "volumen"}

    Motor v2 (spec 18-07): si el body trae `ajustes` (preguntas 5-8 del quiz:
    actividad_diaria, deporte_extra, facilidad_engordar, dieta reportada...),
    se aplica calcular_macros_v2 y la respuesta incluye ademas `desglose`,
    `revision`, `no_aplicados` y `base`. Sin `ajustes` el comportamiento es
    identico al de siempre (tabla pura). La farmacologia se lee SIEMPRE del
    perfil (la fija el coach), nunca del body.
    """
    peso = data.get("peso")
    sexo = data.get("sexo")
    bf = data.get("porcentaje_graso")
    objetivo = data.get("objetivo")

    if not all([peso, sexo, bf is not None, objetivo]):
        raise HTTPException(status_code=400, detail="Faltan campos: peso, sexo, porcentaje_graso, objetivo")

    ajustes = data.get("ajustes")
    if not isinstance(ajustes, dict):
        try:
            targets = calcular_targets(
                peso=float(peso),
                sexo=sexo,
                porcentaje_graso=float(bf),
                objetivo=objetivo
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return targets

    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
    try:
        resultado = calcular_macros_v2(
            peso=float(peso),
            sexo=sexo,
            porcentaje_graso=float(bf),
            objetivo=objetivo,
            farmacologia=bool(profile.get("farmacologia")),
            **ajustes_to_kwargs(ajustes),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # GUARDAR SIEMPRE, desde el dia uno: cada calculo con sus respuestas, se
    # apliquen los modificadores o no y se guarden los macros o no.
    await guardar_quiz_respuestas(
        user_id=user["id"],
        client_id=profile.get("id"),
        origen="ajustar_macros",
        respuestas=ajustes,
        resultado=resultado,
        contexto={"peso": float(peso), "porcentaje_graso": float(bf),
                  "sexo": sexo, "objetivo": objetivo},
    )
    return resultado


@router.post("/targets/apply")
async def calculate_and_apply_targets(data: dict, user = Depends(get_current_user)):
    """
    Calcula targets Y los aplica al perfil del cliente automáticamente.
    Guarda macros_training, macros_rest y macros_periworkout en el perfil.
    
    Body: {"peso": 80, "sexo": "hombre", "porcentaje_graso": 20, "objetivo": "volumen"}

    Motor v2: si el perfil tiene `ajustes_macros` guardados (preguntas 5-8),
    se aplican tambien aqui para no pisar los macros v2 con la tabla pura.
    """
    peso = data.get("peso")
    sexo = data.get("sexo")
    bf = data.get("porcentaje_graso")
    objetivo = data.get("objetivo")

    if not all([peso, sexo, bf is not None, objetivo]):
        raise HTTPException(status_code=400, detail="Faltan campos: peso, sexo, porcentaje_graso, objetivo")

    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0}) or {}

    # ESTE ERA EL AGUJERO GRANDE DEL 4.10. Los demás caminos por lo menos miraban
    # `macros_source != "manual"`; éste no miraba nada. Con un peso y un objetivo, cualquier
    # cliente autenticado se machacaba los macros que le había puesto su entrenador -- los 180
    # de plan personalizado que hay hoy en producción, no sólo los cuatro con "auto".
    #
    # Aquí sí es un 403 con su motivo: el cliente viene expresamente a aplicarse unos macros,
    # no de rebote, así que hay que decírselo en vez de callar y no hacer nada.
    if profile:
        from core.quien_pone_los_macros import exigir_que_pueda
        await exigir_que_pueda(db, profile)

    ajustes_guardados = profile.get("ajustes_macros")
    try:
        if ajustes_guardados:
            resultado = calcular_macros_v2(
                peso=float(peso),
                sexo=sexo,
                porcentaje_graso=float(bf),
                objetivo=objetivo,
                farmacologia=bool(profile.get("farmacologia")),
                **ajustes_to_kwargs(ajustes_guardados),
            )
            targets = {**resultado["base"], "macros": resultado["macros"],
                       "multiplicadores": multiplicadores_de(resultado)}
        else:
            targets = calcular_targets(
                peso=float(peso),
                sexo=sexo,
                porcentaje_graso=float(bf),
                objetivo=objetivo
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    profile_macros = targets_to_profile_macros(targets)

    # Actualizar perfil del cliente. El peso y el % graso no van aqui: van a sus series
    # justo despues (punto 30), y el "actual" del perfil sale del ultimo de la serie.
    update_data = {
        "sex": sexo,
        "goal": objetivo,
        "macros_training": profile_macros["macros_training"],
        "macros_rest": profile_macros["macros_rest"],
        "macros_periworkout": profile_macros["macros_periworkout"],
        "macros_source": "auto",
        "macros_multiplicadores": targets["multiplicadores"],
    }

    # upsert: si el perfil aún no existe (cuenta nueva que usa la calculadora antes de crear el
    # perfil formal), asignar un `id` al INSERTAR. Sin esto el doc se creaba sin `id` y rompía el
    # versionado de macros (macro_history se indexa por profile.id).
    result = await db.client_profiles.update_one(
        {"user_id": user["id"]},
        {"$set": update_data, "$setOnInsert": {"id": str(uuid.uuid4())}},
        upsert=True
    )

    perfil = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
    client_id = (perfil or {}).get("id")
    await anotar_peso(client_id, peso, origen="calculadora")
    await anotar_grasa(client_id, bf, origen="calculadora")

    # Y SE VERSIONA, COMO TODOS LOS DEMAS CAMINOS (punto 10.5 del doc del 09-08). Esto
    # escribia el perfil y nada mas, mientras que las dietas y el chatbot resuelven los macros
    # por `macro_history` (la version vigente a cada fecha, Calma todosLosMacros). Resultado:
    # un cliente de plan de autogestion se aplicaba unos macros, la pantalla los enseñaba y el
    # asistente le seguia cuadrando las comidas con los anteriores.
    #
    # Salio al probar el cerrojo del 4.10: con una entrada de historial delante, el chatbot
    # leia 140 g de hidratos cuando el perfil ya decia 170.
    from core.cambios_macros import marcar_cambios
    from core.historial_macros import guardar as guardar_en_historial

    training = profile_macros["macros_training"]
    rest = profile_macros["macros_rest"]
    peri = profile_macros.get("macros_periworkout")
    await guardar_en_historial({
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "user_id": user["id"],
        "previous_training": profile.get("macros_training"),
        "previous_rest": profile.get("macros_rest"),
        "new_training": training,
        "new_rest": rest,
        "training": training,
        "rest": rest,
        "peri": peri,
        "effective_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        # Sale de la tabla con SUS datos, no lo decide una persona: `quiz_ajuste` es lo que
        # `core/macros_de_quien` cuenta como calculado por la app. Ponerle un `changed_by`
        # aqui haria que el propio cliente contara como «alguien detras» y se cerrara a si
        # mismo la calculadora en la siguiente vuelta.
        "origen": "quiz_ajuste",
        "cambios": marcar_cambios(
            {"entreno": profile.get("macros_training"),
             "perientreno": profile.get("macros_periworkout"),
             "descanso": profile.get("macros_rest")},
            {"entreno": training, "perientreno": peri, "descanso": rest},
        ),
        "peso": peso,
        "client_weight": peso,
        "porcentaje_graso": bf,
        "sexo": sexo,
        "objetivo": objetivo,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "applied": True,
        "targets": targets,
        "profile_macros": profile_macros,
    }


@router.get("/test-targets")
async def test_targets(user = Depends(get_current_user)):
    """Ejecuta los tests del motor de targets."""
    return target_run_tests()
