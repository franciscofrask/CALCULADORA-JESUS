"""
UN DIA GUARDADO, LISTO PARA ENSEÑARLO.

Lo que hay en `db.diets` no se puede pintar tal cual: es un registro incompleto a proposito.
De 4.166 alimentos guardados, 3.731 no traen `macros_efectivos`, y en las dietas que vinieron
de Calma los alimentos por unidades guardan el CONTEO de piezas en `cantidad_g` (un huevo es
un "1"). Quien lea la dieta sin resolver eso enseña P0 H0 G0 y "1 g de huevo".

Eso es exactamente lo que pasaba en el panel de admin (Jesus, 16-08: «al abrir cualquier
dieta de la lista, todas las lineas ponen P0 H0 G0» y «un huevo sale como 1 g»): la ruta del
cliente y el PDF ya lo resolvian cada uno por su lado, y la del entrenador devolvia el
documento crudo de Mongo.

Aqui esta esa resolucion, UNA vez, para las tres puertas:

  - las cantidades a gramos (`normalizar_con_catalogo`),
  - los macros que cuentan, calculados si no se guardaron (`macros_de`),
  - la cantidad escrita como la lee una persona: "2 ud (126 g)" (`cantidad_de`),
  - la ficha del producto y los macros de etiqueta (`adjuntar_urls`).

Nada de esto se GUARDA: es la lectura. Lo guardado sigue siendo lo que escribio la app.
"""
from typing import Any, Dict, Optional

from core.database import db

# Lo que necesita `_adjuntar_urls`: `categorias` va en la proyeccion porque la necesita
# `get_food_config` para saber si un alimento va por unidades y cuanto pesa una.
CAMPOS_MINIMOS = {
    "_id": 0, "id": 1, "url": 1, "proteinas": 1, "hidratos": 1, "grasas": 1,
    "racion": 1, "unidades": 1, "categorias": 1, "nombre": 1,
}


def clave_de(alimento: dict):
    """El id de catalogo de una linea de dieta. Segun por donde entro se llama de dos
    maneras (`alimento_id` en lo que guarda la app, `id` en lo que vino de fuera)."""
    return alimento.get("alimento_id") if alimento.get("alimento_id") is not None else alimento.get("id")


def alimentos_de(diet: dict):
    """Todas las lineas del dia, sin importar en que comida esten."""
    for comida in (diet.get("comidas") or {}).values():
        for a in ((comida or {}).get("alimentos") or []):
            yield a


def ids_de(diet: dict) -> set:
    """Los ids de alimento que aparecen en un dia."""
    ids = {clave_de(a) for a in alimentos_de(diet)}
    ids.discard(None)
    return ids


def normalizar_con_catalogo(diet: dict, catalogo: dict) -> int:
    """Pasa a gramos las cantidades del dia. Punto 4.5 de la revision del 09-08.

    En las dietas que vinieron de Calma los alimentos POR UNIDADES guardan el CONTEO de piezas
    en `cantidad_g`: un huevo entero aparece como "1". Leido como un gramo de huevo da 0,1 de
    proteina y al pintarlo en unidades sale "0 ud", que es lo que reporto Jesus.

    Se convierte AL LEER y no en la pantalla porque por aqui pasan todas -- Nutricion, el
    asistente, el PDF, la ficha del entrenador --, y arreglarlo en una sola dejaria a las
    otras enseñando el numero malo. Y ademas era el escritor: al abrir un dia migrado, la
    pantalla recalculaba los macros con la cantidad como gramos y al guardar los dejaba
    escritos, convirtiendo un registro incompleto en uno falso.
    """
    from calculator import get_food_config
    from core.cantidad_de_dieta import normalizar_dieta

    cfgs = {}

    def config_de(alimento_id, item):
        if alimento_id not in cfgs:
            ficha = catalogo.get(alimento_id)
            cfgs[alimento_id] = get_food_config(ficha) if ficha else None
        return cfgs[alimento_id]

    return normalizar_dieta(diet, config_de)


async def catalogo_de(diet: dict, campos: Optional[dict] = None) -> Dict[Any, dict]:
    """Las fichas de catalogo de los alimentos del dia, en una sola consulta."""
    ids = ids_de(diet)
    if not ids:
        return {}
    return {
        f["id"]: f
        async for f in db.foods.find({"id": {"$in": list(ids)}}, campos or CAMPOS_MINIMOS)
    }


async def normalizar_cantidades(diet: dict) -> int:
    """Lo mismo, trayendose el catalogo que haga falta. Para las rutas que no lo tienen ya."""
    if not ids_de(diet):
        return 0
    return normalizar_con_catalogo(diet, await catalogo_de(diet))


async def adjuntar_urls(diet: dict) -> None:
    """
    Pone en cada alimento del dia lo que hay que resolver contra el catalogo:

      - `url`: la ficha del producto (los de marca la tienen; los genericos no).
      - `macros_reales`: lo que dice la etiqueta, para el switch de la pestaña de
        Nutricion. Es SOLO para enseñarlo: no se guarda, no cuenta y no cambia el
        reparto; lo que cuenta sigue siendo `macros_efectivos`.

    Se resuelve aqui y no al guardar por dos motivos: los dias ya guardados no lo tienen
    (de 3365 alimentos guardados, solo 95 traian los macros de etiqueta), y los alimentos
    entran por muchas puertas (buscador, chatbot, menu sugerido, copiar dia, favoritas),
    asi que guardarlo en cada una seria facil de olvidar. Ademas, si se corrige un
    alimento, los dias antiguos lo cogen solos. Es una unica consulta por dia.
    """
    from calma_suggest import macros_reales

    if not ids_de(diet):
        return
    catalogo = await catalogo_de(diet)

    # Las cantidades, a gramos ANTES de calcular nada (punto 4.5): si no, `macros_reales`
    # saldria del numero equivocado.
    normalizar_con_catalogo(diet, catalogo)

    from core.topes_cantidad import tope_de_alimento

    for a in alimentos_de(diet):
        ficha = catalogo.get(clave_de(a))
        if not ficha:
            continue
        if ficha.get("url"):
            a["url"] = ficha["url"]
        # Cuanto cabe de esto en una comida de verdad: la calculadora lo necesita para
        # avisar al subir la cantidad de un alimento que YA estaba en el dia, no solo de
        # los que acaban de salir del buscador.
        a["max_razonable"] = tope_de_alimento(ficha)
        try:
            a["macros_reales"] = macros_reales(ficha, float(a.get("cantidad_g") or 0))
        except (TypeError, ValueError):
            pass  # un alimento raro no puede tumbar la carga del dia


def macros_de(a: dict, catalogo: Dict[Any, dict]) -> dict:
    """Los macros que le cuentan a este alimento. Guardados si estan, calculados si no.

    EL PDF SALIA CON TODOS LOS ALIMENTOS A CERO (Francisco, 11-08-2026: «puedo ver sus
    dietas pero no los macros de esos alimentos»), y la ficha del cliente en el panel de
    admin, tambien (Jesus, 16-08).

    Leia `macros_efectivos` de lo guardado y punto. Medido: de 4.166 alimentos guardados,
    3.731 NO tienen ese campo -- huevos, claras, pan, yogur, whey --, asi que el PDF los
    escribia a 0 y de paso daba un total del dia que no era el suyo. No es que el dato
    este mal: es que nunca se llego a escribir en la mayoria de las dietas.

    Asi que se calcula con el motor de conteo unico (`calma_suggest.macros_efectivos`,
    el mismo que usa la app desde el 31-07), y lo guardado solo se usa como atajo. Un
    cero legitimo -- la lechuga, o un macro que el filtro del tercio descarta -- sigue
    saliendo cero, porque lo dice el motor y no la ausencia del campo.
    """
    me = a.get("macros_efectivos")
    if me and any((me.get(r) or 0) > 0 for r in ("P", "H", "G")):
        return me
    food = catalogo.get(clave_de(a))
    if not food:
        return me or {}
    try:
        from calma_suggest import macros_efectivos as _efectivos
        return _efectivos(food, float(a.get("cantidad_g") or 0))
    except Exception:
        # Si el motor falla por lo que sea, mejor lo guardado que romper la descarga.
        return me or {}


def cantidad_de(a: dict, catalogo: Dict[Any, dict]) -> str:
    """Texto de la cantidad. En los alimentos por unidades, Jesus quiere ver las
    unidades y el peso entre parentesis: "2 ud (126 g)", no "126 g" a secas."""
    gramos = a.get("cantidad_g", 0) or 0
    food = catalogo.get(clave_de(a)) or {}
    por_unidad = bool(food.get("unidades")) or a.get("unidad") == "ud"
    racion = float(food.get("racion") or a.get("racion") or 0)
    if por_unidad and racion > 0:
        uds = round(gramos / racion * 2) / 2          # medias unidades, como en la app
        uds_txt = f"{uds:.0f}" if uds == int(uds) else f"{uds:.1f}"
        return f"{uds_txt} ud ({gramos:.0f} g)"
    return f"{gramos:.0f} g"


async def enriquecer_para_ver(diet: dict) -> dict:
    """El dia con todo resuelto, listo para pintarlo sin que la pantalla calcule nada.

    Escribe en cada alimento `macros_efectivos` (los de verdad, calculados si no estaban) y
    `cantidad_texto` ("2 ud (126 g)"), y suma el total de cada comida y del dia. Es lo que
    consume el visor de dietas del panel: antes recibia el documento crudo, y de ahi salian
    los dos primeros fallos del 16-08.
    """
    if not ids_de(diet):
        return diet

    # La ficha ENTERA: `macros_efectivos` necesita todos los campos de macros del alimento,
    # no solo los de la proyeccion corta.
    catalogo = await catalogo_de(diet, {"_id": 0})
    normalizar_con_catalogo(diet, catalogo)

    total_dia = {"P": 0.0, "H": 0.0, "G": 0.0}
    for comida in (diet.get("comidas") or {}).values():
        if not isinstance(comida, dict):
            continue
        total = {"P": 0.0, "H": 0.0, "G": 0.0}
        for a in (comida.get("alimentos") or []):
            ficha = catalogo.get(clave_de(a))
            if ficha and ficha.get("url"):
                a["url"] = ficha["url"]
            m = macros_de(a, catalogo) or {}
            a["macros_efectivos"] = {r: round(float(m.get(r) or 0), 1) for r in ("P", "H", "G")}
            a["cantidad_texto"] = cantidad_de(a, catalogo)
            for r in ("P", "H", "G"):
                total[r] += a["macros_efectivos"][r]
        comida["macros_totales"] = {r: round(total[r], 1) for r in ("P", "H", "G")}
        for r in ("P", "H", "G"):
            total_dia[r] += total[r]

    diet["macros_totales"] = {r: round(total_dia[r], 1) for r in ("P", "H", "G")}
    return diet
