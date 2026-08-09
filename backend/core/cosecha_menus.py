"""La cosecha semanal: el banco de menús crece solo con lo que monta la gente.

Punto 71 del documento del 07-08-2026. No se le pide nada al cliente -- en la
plataforma ya hay un botón de «envíanos tu receta» y la gente no sugiere. En su
lugar, una vez por semana se recogen las comidas que ha montado la gente, se pasa
el filtro de calidad y las buenas entran solas.

LA REGLA QUE HACE QUE ESTO FUNCIONE
-----------------------------------
Se cuenta por PERSONAS DISTINTAS, no por usos. Un menú que han montado 30 personas
diferentes es bueno; uno que una sola persona ha repetido 30 veces solo dice que a
esa persona le gusta. Es la diferencia entre una señal y un sesgo.

Y por eso la cosecha NO es incremental. Si cada semana sumásemos las personas de
esa semana a las de la anterior, quien repite un menú cada lunes contaría como una
persona nueva cada vez, que es exactamente el sesgo del que se huye. Cada pasada
recuenta sobre toda la historia de dietas: son 38.000, se recorren en segundos, y
el número que queda es de verdad «cuánta gente distinta lo ha montado alguna vez».

DE DÓNDE VIENE CADA NÚMERO
--------------------------
La biblioteca actual se importó de un CSV de la calculadora antigua, que traía
`veces` (usos) pero no la persona, así que `clientes` quedó a 0 en los 23.681. Y 0
no es lo mismo que «no lo sé»: el sugeridor ordena por personas distintas, y un 0
heredado compite de tú a tú con un 0 real. Por eso se separan:

  - `usos_calma`   : lo que se sabe de la calculadora antigua. No hay persona.
  - `usos`         : veces montado en ESTA app.
  - `clientes`     : personas distintas que lo han montado en ESTA app.

Un menú heredado sin cosechar queda en usos=0, clientes=0 y usos_calma=803: no se
le inventa una popularidad que no se puede comprobar, pero tampoco se pierde lo que
ya se sabía de él.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Set, Tuple

# ── Filtro de calidad (punto 67) ────────────────────────────────────────────
# Los menús de los clientes son la fuente 3 y son de relleno: 266.170 combinaciones
# guardadas, pero medido sobre las nuestras solo el 8 % lleva verdura y el 42 %
# lleva proteína en polvo. Sin filtro, sugerir «lo que monta la gente» es sugerir
# batidos. Estos son los tres cortes que pide el documento.

# Una comida de 1 alimento no es una comida, y de 10 es un día entero volcado.
MIN_ALIMENTOS = 2
MAX_ALIMENTOS = 9

# Cuántos de los alimentos pueden ser suplementos antes de que aquello deje de ser
# comida. La mitad justa se admite (un batido con fruta es una merienda de verdad);
# pasar de ahí ya es una lista de botes.
MAX_PROPORCION_SUPLEMENTOS = 0.5

# La verdura es la familia 13 (13.1 frescas, 13.2 cremas y gazpacho, 13.4
# congeladas, 13.8 en conserva, 13.9 ensaladas preparadas). Cuidado con darlo por
# sabido: la 14 NO es verdura, son «Hidratos en polvo», y un filtro con la 14 aquí
# exigiría justo lo contrario de lo que se busca.
CATS_VERDURA = ("13",)

# La 11 es fruta, zumos, potitos y mermeladas. En un desayuno o una merienda, la
# fruta hace el papel de la verdura: un desayuno de tostada, huevo y kiwi está bien,
# y pedirle brócoli no. En la comida y la cena no cuela.
CATS_FRUTA = ("11",)

# Proteína en polvo, hidratos en polvo, intra, aminoácidos, sustitutivos y barritas.
# No es que estén mal -- el post-entreno vive de ellos -- es que un menú hecho solo
# de eso no se le enseña a nadie como idea de comida.
#
# Fuera de esta lista a propósito: la 46 (cremas y tortas de arroz) es comida, y la
# 25 (Postentreno) es una etiqueta transversal que llevan alimentos normales, no una
# familia de botes.
CATS_SUPLEMENTO = ("4", "14", "18", "27", "28", "29", "30", "41")

# El peri (intra y post) se juzga con otra vara: ahí un batido SÍ es la comida, y
# pedirle verdura no tiene sentido.
TIPOS_SIN_FILTRO_DE_VERDURA = ("peri",)

# En el desayuno vale la fruta en lugar de la verdura. Sin esta excepción el filtro
# se lleva por delante el 98 % de los desayunos -- medido: de 5.626 pasaban 113 --,
# y no porque sean malos, sino porque casi nadie desayuna brócoli.
TIPOS_DONDE_LA_FRUTA_CUENTA = ("desayuno",)


def _prefijo(cat: str, familia: str) -> bool:
    """¿La categoría `cat` cuelga de `familia`? '14.1' cuelga de '14'; '141' no."""
    cat = (cat or "").strip()
    return cat == familia or cat.startswith(familia + ".")


def _familias(food: dict) -> List[str]:
    return [c.strip() for c in str(food.get("categorias") or "").split("|") if c.strip()]


def es_verdura(food: dict) -> bool:
    return any(_prefijo(c, f) for c in _familias(food) for f in CATS_VERDURA)


def es_fruta(food: dict) -> bool:
    return any(_prefijo(c, f) for c in _familias(food) for f in CATS_FRUTA)


def es_suplemento(food: dict) -> bool:
    return any(_prefijo(c, f) for c in _familias(food) for f in CATS_SUPLEMENTO)


def pasa_el_filtro(foods: List[dict], tipo: str = "comida") -> Tuple[bool, str]:
    """¿Este menú es lo bastante bueno para ofrecérselo a alguien?

    Devuelve (vale, motivo). El motivo se guarda para poder contar por qué se cae
    cada cosa: un filtro que descarta el 95 % sin decir por qué no se puede afinar.
    """
    n = len(foods)
    if n < MIN_ALIMENTOS:
        return False, "muy_pocos_alimentos"
    if n > MAX_ALIMENTOS:
        return False, "dia_entero_volcado"

    suplementos = sum(1 for f in foods if es_suplemento(f))
    if suplementos / n > MAX_PROPORCION_SUPLEMENTOS:
        return False, "cargado_de_suplementos"

    if tipo not in TIPOS_SIN_FILTRO_DE_VERDURA:
        vale = any(es_verdura(f) for f in foods)
        if not vale and tipo in TIPOS_DONDE_LA_FRUTA_CUENTA:
            vale = any(es_fruta(f) for f in foods)
        if not vale:
            return False, "sin_verdura"

    return True, "ok"


# ── La cosecha ──────────────────────────────────────────────────────────────

PERI_KEYS = ("Intra", "Post", "intra", "post")

# La primera comida del día es el desayuno. Va por posición y sin excepciones, que es
# la misma decisión que se tomó el 06-08 para el resto de la app (ver meal_moment.py):
# quien entrena en ayunas sigue teniendo un desayuno en su Comida 1.
PRIMERA_COMIDA = ("C1", "c1")


def firma(alimento_ids: Iterable[int]) -> Tuple[int, ...]:
    """Dos comidas son la misma si llevan los mismos alimentos, den igual las
    cantidades: el sugeridor las va a reescalar de todas formas."""
    return tuple(sorted(set(int(a) for a in alimento_ids)))


async def recontar(db, desde: Optional[datetime] = None) -> Dict[tuple, dict]:
    """Recorre las dietas y devuelve, por firma, cuántas veces se montó y CUÁNTAS
    PERSONAS DISTINTAS la montaron.

    `desde` acota por fecha para poder mirar una semana suelta, pero la cosecha de
    verdad va sin acotar: ver la explicación de arriba sobre por qué no es
    incremental.

    LAS CANTIDADES SE PASAN A GRAMOS ANTES DE CONTARLAS (punto 4.5 del 09-08). En las
    dietas que vinieron de Calma los alimentos por unidades guardan el CONTEO de piezas en
    `cantidad_g`: un plátano entero aparece como "1". Cosechado tal cual, la biblioteca
    acababa ofreciendo menús con «1 g de plátano» y «1 g de yogur», y con los macros
    calculados sobre eso. Medido tras la primera cosecha del 09-08: 10.732 de los 42.364
    menús que pasan el filtro -- uno de cada cuatro -- llevaban algún alimento así.
    """
    from calculator import get_food_config
    from core.cantidad_de_dieta import gramos as a_gramos

    # La configuración de cada alimento, una sola vez: aquí se recorren cientos de miles
    # de items y resolverla por item multiplicaría el trabajo por nada.
    cfgs: Dict[int, dict] = {}
    async for f in db.foods.find({}, {"_id": 0, "id": 1, "categorias": 1,
                                      "racion": 1, "unidades": 1}):
        try:
            cfgs[int(f["id"])] = get_food_config(f)
        except (TypeError, ValueError, KeyError):
            pass

    q = {}
    if desde:
        q["fecha"] = {"$gte": desde.strftime("%Y-%m-%d")}

    acc: Dict[tuple, dict] = defaultdict(
        lambda: {"usos": 0, "personas": set(), "peri": 0, "c1": 0,
                 "cantidades": defaultdict(list)})

    cursor = db.diets.find(q, {"_id": 0, "user_id": 1, "comidas": 1})
    async for dieta in cursor:
        uid = dieta.get("user_id")
        comidas = dieta.get("comidas")
        if not isinstance(comidas, dict):
            continue  # dietas corruptas (un Int64 en 'comidas'): se ignoran
        for meal_key, meal in comidas.items():
            if not isinstance(meal, dict):
                continue
            alimentos = meal.get("alimentos") or []
            ids, cants = [], {}
            for a in alimentos:
                try:
                    aid = int(a.get("alimento_id"))
                    cant = float(a.get("cantidad_g") or 0)
                except (TypeError, ValueError):
                    ids = []
                    break
                # Hay dietas con cantidades NaN. Ojo con el orden: `NaN <= 0` es
                # False, así que un `if cant <= 0` las deja pasar y revientan más
                # tarde, al sacar la mediana.
                if cant != cant or cant in (float("inf"), float("-inf")) or cant <= 0:
                    continue
                # Y a gramos, si lo que hay guardado era un conteo de piezas (punto 4.5).
                cfg = cfgs.get(aid)
                if cfg:
                    convertida = a_gramos(cant, cfg)
                    if convertida:
                        cant = convertida
                ids.append(aid)
                cants[aid] = cant
            if len(set(ids)) < MIN_ALIMENTOS:
                continue
            sig = firma(ids)
            c = acc[sig]
            c["usos"] += 1
            if uid:
                c["personas"].add(uid)
            if meal_key in PERI_KEYS:
                c["peri"] += 1
            if meal_key in PRIMERA_COMIDA:
                c["c1"] += 1
            for aid, cant in cants.items():
                c["cantidades"][aid].append(cant)

    return acc


def personas_distintas(acumulado: dict) -> int:
    return len(acumulado["personas"])


def es_peri(acumulado: dict) -> bool:
    """Peri si la mayoría de las veces se montó en el intra o el post. Un menú que
    unos ponen de merienda y otros de post no es peri: manda dónde suele ir."""
    return acumulado["peri"] >= acumulado["usos"] * 0.7


def es_desayuno(acumulado: dict) -> bool:
    """Desayuno si la mayoría de las veces se montó en la primera comida. Sirve para
    no exigirle verdura: ahí la fruta hace ese papel."""
    return acumulado["c1"] >= acumulado["usos"] * 0.7


def semana_pasada(hoy: Optional[datetime] = None) -> datetime:
    hoy = hoy or datetime.now(timezone.utc)
    return hoy - timedelta(days=7)
