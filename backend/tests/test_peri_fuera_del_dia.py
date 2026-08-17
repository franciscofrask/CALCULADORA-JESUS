"""El asistente cuenta el día como lo cuenta Nutrición: con el perientreno APARTE.

Punto 3 del documento del 17-08: *«Está arreglado cuando Inicio, Nutrición y el asistente
dicen el mismo número»*. Y el punto 10, que es la causa: *«el resumen del asistente enseña
otro objetivo. Son los 15 g del peri, contados dentro en un sitio y fuera en otro»*.

Lo que pasaba: `get_day_overview` metía el peri en los DOS lados -- el objetivo era el total
del día (peri incluido) y el consumido sumaba también el Intra y el Post --, mientras la
cabecera de Nutrición lo descuenta de los dos. La diferencia entre ambas cuentas es
exactamente lo que le falta al peri, así que las dos pantallas nunca coincidían.

Medido en producción el 17-08 en el día 5 de julio de una cuenta real: Nutrición decía
«faltan 10,1 g de grasa» y el asistente, del mismo día, «te faltan 5 g de grasa».

Sin Mongo y sin OpenAI: el catálogo se le da a mano.
"""
import os
import sys

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)

from chatbot import NutritionChatbot  # noqa: E402

# Entreno 180 P / 180 H / 60 G, con un peri de 45 P / 60 H y SIN grasa, como el del caso.
MACROS = {"p_entreno": 180, "h_entreno": 180, "g_entreno": 60,
          "p_peri": 45, "h_peri": 60,
          "p_descanso": 140, "h_descanso": 40, "g_descanso": 40}

POLLO = {"id": 101, "nombre": "Pechuga de pollo", "categorias": "1.1",
         "proteinas": 23.0, "hidratos": 0.0, "grasas": 1.5, "racion": 100, "unidades": False}
ACEITE = {"id": 103, "nombre": "Aceite de oliva virgen extra", "categorias": "17.1",
          "proteinas": 0.0, "hidratos": 0.0, "grasas": 100.0, "racion": 100, "unidades": False}


def _bot(opcion_peri="intra_post"):
    bot = NutritionChatbot("test_peri", None)
    bot.set_user_macros(MACROS)          # los macros van por aquí, no por el constructor
    bot.configure_day(tipo_dia="entrenamiento", num_comidas=3, momento_entreno=1,
                      opcion_peri=opcion_peri)
    return bot


def _poner(bot, key, macros):
    """Deja una comida montada con esos macros, sin pasar por el catálogo."""
    bot.state["comidas_completadas"][key] = {"alimentos": [], "macros": dict(macros)}


def test_el_peri_no_se_descuenta_del_presupuesto_de_las_comidas():
    """La grasa del POST no puede comerse la grasa de las comidas.

    Es el caso literal del 5 de julio: el peri de ese día no tenía objetivo de grasa, el
    post traía 5 g, y esos 5 g se restaban del presupuesto del día. Nutrición decía
    «faltan 10,1 g» y el asistente «faltan 5».
    """
    bot = _bot()
    ov0 = bot.get_day_overview()
    assert ov0["peri"]["objetivo"]["G"] == 0, "este día no reparte grasa al peri"
    objetivo_g = ov0["objetivo_comidas"]["G"]

    _poner(bot, "C1", {"P": 0, "H": 0, "G": objetivo_g - 10.1})   # falta 10,1 en las comidas
    _poner(bot, "Post", {"P": 20, "H": 15, "G": 5})               # y el post trae 5 de propina

    ov = bot.get_day_overview()
    # Lo que se le dice al cliente: el par de Nutrición, sin tocar por el peri.
    assert round(ov["restante_comidas"]["G"], 1) == 10.1
    # La cuenta vieja se comía esos 5 g y decía 5,1.
    assert round(ov["restante"]["G"], 1) == 5.1


def test_el_objetivo_de_las_comidas_es_el_dia_menos_el_peri():
    bot = _bot()
    ov = bot.get_day_overview()
    o, oc, p = ov["objetivo"], ov["objetivo_comidas"], ov["peri"]["objetivo"]
    for k in ("P", "H", "G"):
        assert round(oc[k], 1) == round((o.get(k) or 0) - p[k], 1)
    # El peri de este día lleva proteína e hidratos, pero no grasa.
    assert p["G"] == 0


def test_el_peri_lleva_su_propia_cuenta():
    bot = _bot()
    _poner(bot, "Post", {"P": 20, "H": 25, "G": 0})
    peri = bot.get_day_overview()["peri"]
    assert peri["hay"] is True
    assert peri["consumido"]["P"] == 20
    assert round(peri["restante"]["P"], 1) == round(peri["objetivo"]["P"] - 20, 1)


def test_sin_peri_las_dos_cuentas_coinciden():
    """Un día sin perientreno no puede tener dos presupuestos distintos."""
    bot = _bot(opcion_peri="sin_peri")
    _poner(bot, "C1", {"P": 50, "H": 40, "G": 10})
    ov = bot.get_day_overview()
    for k in ("P", "H", "G"):
        assert round(ov["restante"][k], 1) == round(ov["restante_comidas"][k], 1)
    assert ov["peri"]["hay"] is False


def test_el_total_del_dia_sigue_siendo_el_total():
    """La tarjeta «Total del día» del chat pinta `objetivo`/`consumido`, y ahí el peri SÍ
    cuenta: es un total. Lo que cambió es lo que se le dice al cliente, no esto."""
    bot = _bot()
    _poner(bot, "C1", {"P": 100, "H": 80, "G": 20})
    _poner(bot, "Post", {"P": 45, "H": 60, "G": 0})
    ov = bot.get_day_overview()
    assert ov["consumido"]["P"] == 145      # las comidas Y el peri
    assert ov["consumido_comidas"]["P"] == 100
