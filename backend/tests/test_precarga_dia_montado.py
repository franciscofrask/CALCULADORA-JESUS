"""El asistente lee el día que YA está montado, y lo lee bien.

Jesús, 12-08-2026: «Lo abrí en producción con las cuatro comidas hechas y 127 g de proteína
encima, y su resumen decía "llevas 0 g" y "0/4 comidas guardadas"».

La precarga ya existía (11-08) pero se creía el `macros_efectivos` guardado en la dieta, y
ese campo casi nunca está: medido contra producción, 411 de 55.323 alimentos guardados lo
traen con algo dentro. Es el mismo agujero que dejaba el PDF a cero. En una dieta real de
producción el asistente leía 0/0/0 donde el motor dice 192 P / 149 H / 21 G.

Y «0/4» era otra cosa: `completas` cuenta `saved_meals`, y la precarga no metía ahí nada.

Todo esto corre sin Mongo y sin OpenAI: se le da al bot el catálogo a mano.
"""
import os
import sys

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)

from chatbot import NutritionChatbot  # noqa: E402

MACROS = {"p_entreno": 160, "h_entreno": 120, "g_entreno": 40,
          "p_peri": 35, "h_peri": 15,
          "p_descanso": 140, "h_descanso": 40, "g_descanso": 40}

# Fichas del catálogo real (los campos que mira el motor).
POLLO = {"id": 101, "nombre": "Pechuga de pollo", "categorias": "1.1",
         "proteinas": 23.0, "hidratos": 0.0, "grasas": 1.5, "racion": 100, "unidades": False}
ARROZ = {"id": 102, "nombre": "Arroz blanco", "categorias": "7.2",
         "proteinas": 7.0, "hidratos": 78.0, "grasas": 0.6, "racion": 100, "unidades": False}
ACEITE = {"id": 103, "nombre": "Aceite de oliva virgen extra", "categorias": "17.1",
          "proteinas": 0.0, "hidratos": 0.0, "grasas": 100.0, "racion": 100, "unidades": False}
CATALOGO = {f["id"]: f for f in (POLLO, ARROZ, ACEITE)}


def _bot():
    bot = NutritionChatbot("test_precarga", MACROS)
    bot.configure_day(tipo_dia="entrenamiento", num_comidas=4, momento_entreno=1,
                      opcion_peri="sin_peri")
    return bot


def _dia_guardado():
    """Un día como los que hay en la base: SIN `macros_efectivos`, que es el caso normal."""
    return {
        "C1": {"alimentos": [
            {"alimento_id": 101, "nombre": "Pechuga de pollo", "cantidad_g": 150},
            {"alimento_id": 102, "nombre": "Arroz blanco", "cantidad_g": 100},
        ]},
        "C2": {"alimentos": [
            {"alimento_id": 101, "nombre": "Pechuga de pollo", "cantidad_g": 200},
            {"alimento_id": 103, "nombre": "Aceite de oliva virgen extra", "cantidad_g": 10},
        ]},
    }


def test_lo_montado_cuenta_aunque_no_haya_macros_guardados():
    """El fallo que reportó Jesús: día puesto, «llevas 0 g»."""
    bot = _bot()
    traidas = bot.precargar_desde_dieta(_dia_guardado(), CATALOGO)

    assert traidas == 2
    consumido = bot.get_day_overview()["consumido"]
    assert consumido["P"] > 50, f"la proteína del día se perdió: {consumido}"
    assert consumido["H"] > 0, f"los hidratos del día se perdieron: {consumido}"
    assert consumido["G"] > 0, f"la grasa del día se perdió: {consumido}"


def test_sin_catalogo_no_se_inventa_nada():
    """Sin fichas no hay con qué contar: se trae lo que haya y no se rellena."""
    bot = _bot()
    assert bot.precargar_desde_dieta(_dia_guardado()) == 2
    assert bot.get_day_overview()["consumido"]["P"] == 0


def test_lo_guardado_manda_si_esta():
    """Si la dieta trae macros escritos, no se recalculan."""
    bot = _bot()
    bot.precargar_desde_dieta({"C1": {"alimentos": [
        {"alimento_id": 101, "nombre": "Pechuga de pollo", "cantidad_g": 150,
         "macros_efectivos": {"P": 99, "H": 0, "G": 0}},
    ]}}, CATALOGO)
    assert bot.get_day_overview()["consumido"]["P"] == 99


def test_las_comidas_traidas_cuentan_como_guardadas():
    """El «0/4 comidas guardadas» con las cuatro puestas."""
    bot = _bot()
    bot.precargar_desde_dieta(_dia_guardado(), CATALOGO)
    v = bot.get_day_overview()
    assert v["total_comidas"] == 4
    assert v["completas"] == 2, f"dice {v['completas']} de {v['total_comidas']}"
    assert [m["guardada"] for m in v["meals"]] == [True, True, False, False]


def test_se_sigue_por_la_primera_que_falta():
    """Con C1 y C2 puestas, se sigue por la C3: no se reabre lo que ya está hecho."""
    bot = _bot()
    bot.precargar_desde_dieta(_dia_guardado(), CATALOGO)
    assert bot.state["comida_actual"] == 3


def test_no_se_pisa_lo_que_ya_hay():
    """Lo traído sigue en la comida después de precargar: es lo que hacía perder trabajo."""
    bot = _bot()
    bot.precargar_desde_dieta(_dia_guardado(), CATALOGO)
    c1 = bot.state["comidas_completadas"]["C1"]["alimentos"]
    assert [a["nombre"] for a in c1] == ["Pechuga de pollo", "Arroz blanco"]
    assert [a["cantidad_g"] for a in c1] == [150, 100]


def test_los_acumulados_del_dia_se_traen():
    """El arroz que ya se comió cuenta para la calibración del siguiente cereal."""
    bot = _bot()
    bot.precargar_desde_dieta(_dia_guardado(), CATALOGO)
    assert bot.state["acumulado_cereales_panes"] == 100


def test_solo_entran_las_comidas_que_existen_ahora():
    """Un día de 4 comidas abierto con 3: la C4 no se cuela."""
    bot = NutritionChatbot("test_precarga_3", MACROS)
    bot.configure_day(tipo_dia="entrenamiento", num_comidas=3, momento_entreno=1,
                      opcion_peri="sin_peri")
    guardado = _dia_guardado()
    guardado["C4"] = {"alimentos": [
        {"alimento_id": 101, "nombre": "Pechuga de pollo", "cantidad_g": 500}]}
    bot.precargar_desde_dieta(guardado, CATALOGO)
    assert "C4" not in bot.state["comidas_completadas"]
