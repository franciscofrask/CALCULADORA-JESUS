"""La mermelada y el cacao se pueden ofrecer: lo que no se puede es ofrecerlos SOLOS.

Francisco, 08-08-2026, sobre la regla de «no sugerible»: *«esta regla está mal, porque no
podría ofrecer mermelada? o cacao? necesita ser más específica»*.

La regla vetaba CATEGORÍAS enteras -- mermeladas, cacao y azúcares, salsas, harinas, masas
-- para que el asistente no propusiera tonterías por iniciativa propia. Pero el dato le da
la razón a Francisco. En las 147.820 comidas reales de Jesús:

    mermeladas (11.9)        1.230 usos       0 veces solas
    cacao y azúcares (37)    3.136 usos       1 vez sola
    salsas (16)              2.342 usos       4 veces solas

No es que no se usen: es que **nunca son el plato**. La miel va con el pan (952 usos, 0
veces sola), la mermelada con las claras, el cacao con los copos de avena. El veto estaba
puesto en el sitio equivocado: no en el alimento, sino en la soledad.

Ahora se puede ofrecer lo que ACOMPAÑA a algo que ya está en la comida, y sigue sin
ofrecerse cuando no hay a qué acompañar. Quién acompaña a quién lo dicen las dietas
(company_profile), no una lista escrita a mano.
"""
import asyncio
import os
import sys

import pytest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(_RAIZ, ".env"))

pytestmark = pytest.mark.skipif(not os.environ.get("MONGO_URL"),
                                reason="sin MONGO_URL: test de integración")

MACROS = {"p_entreno": 160, "h_entreno": 120, "g_entreno": 40,
          "p_peri": 35, "h_peri": 15,
          "p_descanso": 140, "h_descanso": 40, "g_descanso": 40}

# Lo que Francisco nombró, más los otros dos grupos que el mismo veto se llevaba por
# delante. Todos con cientos o miles de usos reales y casi ninguno en solitario.
ACOMPANAMIENTOS = ["mermelada", "miel", "cacao desgrasado"]


def _buscar(texto, precarga=(), limite=6):
    async def _correr():
        from motor.motor_asyncio import AsyncIOMotorClient
        from chatbot import NutritionChatbot
        from agent_tools import AgentTools
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "jg12_restored")]
        bot = NutritionChatbot(f"acomp_{texto}_{len(precarga)}", db)
        bot.set_user_macros(MACROS)
        bot.configure_day("entrenamiento", 4, momento_entreno=1, opcion_peri="intra_post")
        for nombre, cant in precarga:
            await bot.add_foods([{"nombre": nombre, "cantidad": cant, "unidad": "g", "sumar": False}])
        tools = await AgentTools.crear(bot)
        r = await tools.buscar_alimentos(texto=texto, limite=limite)
        return [i["nombre"].lower() for i in r["items"]]
    return asyncio.run(_correr())


DESAYUNO = (("pan de barra", 80), ("claras de huevo pasteurizadas", 200))


@pytest.mark.parametrize("texto", ACOMPANAMIENTOS)
def test_con_el_plato_vacio_no_se_ofrece(texto):
    """Nadie desayuna un bote de mermelada. Con la comida vacía sigue sin proponerse."""
    nombres = _buscar(texto)
    clave = texto.split()[0]
    sueltos = [n for n in nombres if n.startswith(clave)]
    assert not sueltos, f"«{texto}» con el plato vacío ofrece {sueltos}"


AVENA = (("copos de avena", 60), ("aislado de suero - whey isolate", 30))


@pytest.mark.parametrize("texto,con", [
    ("mermelada", DESAYUNO),   # sobre el pan
    ("miel", DESAYUNO),
    ("cacao desgrasado", AVENA),   # en el batido, no sobre el pan
])
def test_con_algo_a_lo_que_acompanar_si(texto, con):
    """Cada uno con SU compañía, la que dicen las dietas: la mermelada y la miel sobre el
    pan, el cacao con la avena y el batido."""
    nombres = _buscar(texto, precarga=con)
    clave = texto.split()[0]
    assert any(n.startswith(clave) for n in nombres), f"«{texto}» -> {nombres[:4]}"


@pytest.mark.parametrize("texto", ["azucar moreno", "ketchup"])
def test_el_veto_sigue_donde_tiene_que_seguir(texto):
    """El arreglo no puede abrir la puerta a todo. Tener algo en el plato no basta: hace
    falta que ESE acompañamiento vaya con ESO.

    Con solo mirar la elevación entraba el 89 % de lo vetado en cuanto hubiera cualquier
    cosa en el plato, porque con pocos usos una coincidencia suelta ya da elevación alta.
    Pidiendo además cinco coincidencias reales baja al 14 %: el azúcar moreno y el kétchup
    dejan de aparecer en un desayuno de pan con claras."""
    nombres = _buscar(texto, precarga=DESAYUNO)
    clave = texto.split()[0]
    assert not [n for n in nombres if n.startswith(clave)], f"«{texto}» -> {nombres[:4]}"


def test_el_dato_manda_sobre_la_intuicion():
    """La masa de pizza con claras SÍ entra, y está bien: es la pizza proteica que hace
    todo el mundo en estas dietas (127 usos, y sus dos compañías más frecuentes son la
    mozzarella y las claras). El primer test que se escribió aquí daba por hecho que no
    pegaban; se equivocaba el test, no el dato."""
    nombres = _buscar("masa de pizza", precarga=DESAYUNO)
    assert [n for n in nombres if n.startswith("masa de pizza")], nombres[:4]


def test_lo_normal_no_se_toca():
    """Un alimento corriente no depende de con qué vaya: se ofrece siempre."""
    for texto in ("pechuga de pollo", "arroz", "avena"):
        assert _buscar(texto), f"«{texto}» ha dejado de ofrecerse"
