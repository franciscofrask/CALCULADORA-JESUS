"""
Cuando el numero guardado en `cantidad_g` no son gramos. Punto 4.5 de la revision del 09-08.

Lo que reporto Jesus: al abrir una dieta migrada, «Atun al natural lata, 0 ud, 0,6 g
proteina». Lo leyo como que falta aplicar la regla de descarte por minimo. No es eso.

En las dietas que vinieron de Calma, los alimentos que van POR UNIDADES guardan el CONTEO de
piezas en el campo `cantidad_g`, y los que van a granel guardan gramos de verdad. En la misma
comida y en el mismo campo:

    Pan de barra ............. 20     <- gramos
    Tomate rallado ........... 30     <- gramos
    Jamon serrano ............ 40     <- gramos
    Huevos enteros M .......... 1     <- UN HUEVO, no un gramo de huevo
    Queso Havarti loncha ...... 1     <- UNA LONCHA

Leido como gramos, un huevo de 53 g pasa a valer 1 g: 0,1 de proteina, y al convertirlo a
unidades para enseñarlo sale «0 ud». De ahi la linea que vio.

Medido en produccion el 09-08: 119.974 items de 624.214 estan asi. **Casi todos (119.966) no
guardan macros**, asi que son registros incompletos de la migracion, no datos erroneos. Los
8 que si los guardan son los que ya paso alguien por la pantalla de Nutricion: al abrirla, el
front recalcula los macros de los items que no los traen usando la cantidad como gramos, y al
guardar escribe ese 0,6. Es decir, ABRIR una dieta migrada la convertia en una dieta mal
guardada. Los `updated_at` de esos 8 son del dia de la revision.

Aqui se arregla el escritor: la cantidad se normaliza AL LEER, asi que lo que llega a la
pantalla, al asistente y a lo que se vuelva a guardar ya son gramos.

Decision de Francisco (09-08): NO se reescriben en bloque los 120.000 de la migracion.
Adivinar en masa lo que significo un numero hace tres años no es arreglar, es inventar. Se
convierten de uno en uno y solo cuando se abren, que es cuando hay alguien delante mirandolo.

La regla es deliberadamente estrecha. Solo se convierte cuando leerlo como gramos es
IMPOSIBLE, no cuando es raro:

  - el alimento va por unidades y se sabe lo que pesa una,
  - el numero es un entero de 1 a 12 (un conteo de piezas, no una pesada),
  - y no llega ni a un tercio de una sola pieza.

Con eso, 3 en una lata de 60 g son tres latas. Pero 40 en una loncha de 25 g se quedan como
40 gramos, porque ahi si puede ser una pesada.
"""
import math
from typing import Any, Dict, Optional

# Un conteo de piezas es un numero pequeño. Por encima de esto ya no es "cuantas me pongo",
# es una cantidad, y no se toca.
MAXIMO_PIEZAS = 12

# Cuanto tiene que quedarse por debajo de una pieza para que leerlo como gramos sea absurdo.
# Un tercio: 3 g de un huevo de 53 no es una racion de nada.
FRACCION_ABSURDA = 3.0


def _numero(v: Any) -> Optional[float]:
    """El valor como numero, o None si no lo es.

    Los NaN existen en esta base: hay dietas guardadas con `cantidad_g: NaN`. Un NaN pasa el
    `float()` sin quejarse y revienta despues en el `int()`, y como esto corre al LEER una
    dieta, un solo NaN tumbaria la pantalla de Nutricion entera con un 500.
    """
    try:
        x = float(v or 0)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) or math.isinf(x) else x


def parece_un_conteo(cantidad: Any, por_unidad: bool, peso_unidad: Any) -> bool:
    """True si `cantidad` es un numero de piezas metido donde van los gramos."""
    if not por_unidad:
        return False
    peso, n = _numero(peso_unidad), _numero(cantidad)
    if peso is None or n is None or peso <= 0 or n <= 0 or n != int(n):
        return False
    return 1 <= n <= MAXIMO_PIEZAS and n < peso / FRACCION_ABSURDA


def gramos(cantidad: Any, config: Dict[str, Any]) -> Optional[float]:
    """La cantidad en gramos. Convierte solo si el numero guardado era un conteo de piezas."""
    n = _numero(cantidad)
    if n is None:
        return None
    if parece_un_conteo(n, config.get("por_unidad"), config.get("peso_unidad")):
        return n * float(config["peso_unidad"])
    return n


def normalizar_dieta(diet: Dict[str, Any], config_de) -> int:
    """Pasa a gramos las cantidades de una dieta ya leida. Devuelve cuantas cambio.

    `config_de(alimento_id, item)` devuelve la configuracion del alimento (la de
    `calculator.get_food_config`). Se pasa como parametro para no atar este modulo a la base
    de datos: asi se puede probar sin Mongo.

    Se anota en el propio item (`cantidad_convertida`) de donde sale el numero. Si algun dia
    hay que revisar una de estas conversiones, esta dicho en el dato y no hay que deducirlo.
    """
    comidas = diet.get("comidas")
    if isinstance(comidas, dict):
        comidas = list(comidas.values())
    elif not isinstance(comidas, list):
        return 0

    convertidas = 0
    for comida in comidas:
        if not isinstance(comida, dict):
            continue
        for item in (comida.get("alimentos") or []):
            if not isinstance(item, dict):
                continue
            aid = item.get("alimento_id", item.get("id"))
            cfg = config_de(aid, item)
            if not cfg:
                continue
            original = item.get("cantidad_g")
            if not parece_un_conteo(original, cfg.get("por_unidad"), cfg.get("peso_unidad")):
                continue
            item["cantidad_g"] = float(original) * float(cfg["peso_unidad"])
            item["cantidad_convertida"] = {
                "de": original, "unidades": original, "peso_unidad": cfg["peso_unidad"],
                "por_que": "venia de Calma con el numero de piezas en el campo de gramos",
            }
            # Los macros que hubiera estan calculados sobre el numero equivocado: se quitan
            # para que se recalculen sobre los gramos buenos. Dejarlos seria peor que no
            # tenerlos, porque parecen un dato bueno.
            for campo in ("macros_efectivos", "macros_brutos", "macros_reales"):
                item.pop(campo, None)
            convertidas += 1
    return convertidas
