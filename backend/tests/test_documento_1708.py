"""
Los puntos del documento «12EN12 · Qué hay que hacer» (17-08-2026) que se arreglaron en
código, cada uno con el caso que los destapó.

Sin modelo y sin base de datos: son candados deterministas y tienen que poder comprobarse
en dos segundos. Lo que no está aquí es porque es de datos (limpiar filas) o de decisión de
Jesús, no de código.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.quien_pone_los_macros import puede_ajustarlos          # noqa: E402
from core.lectura_dieta import _distancia_a_lo_pedido            # noqa: E402
from core.series_cliente import sanea_peso                       # noqa: E402


# ── Punto 1: un cliente sin macros se quedaba atrapado en el alta ──────────────────────

def test_sin_macros_puede_calcular_aunque_su_plan_no_ajuste():
    """El caso de Daniel Ricobaldi: plan sin ajuste, sin macros, y el alta no le dejaba salir.

    El cuestionario es obligatorio para entrar y su último paso es «Calcular mis macros».
    Ahí recibía un 403 que además le decía «escríbenos», con el chat detrás de esa misma
    pantalla. Sin macros no hay nada que proteger.
    """
    perfil = {"id": "x", "plan": "mantenimiento", "macros_training": {}}
    puede, por_que_no = asyncio.run(puede_ajustarlos(None, perfil))
    assert puede is True
    assert por_que_no is None


def test_con_macros_el_plan_sin_ajuste_sigue_cerrado():
    """Y el candado sigue puesto para quien SÍ tiene macros: no se ha abierto la puerta.

    Comprobado además contra dev de punta a punta: `POST /calculator/targets/apply` con la
    cuenta encerrada da 200 y le escribe sus macros; la segunda llamada, ya con macros, da
    403. La puerta se abre una vez, para entrar.
    """
    perfil = {"id": "x", "plan": "mantenimiento", "macros_training": {"protein": 180}}
    puede, por_que_no = asyncio.run(puede_ajustarlos(None, perfil))
    assert puede is False
    assert "no incluye ajustes" in por_que_no


def test_un_plan_que_no_esta_en_el_catalogo_no_encierra_a_nadie():
    """El caso que de verdad había en producción: `plan: None`.

    `modo_calculadora` manda a `sin_ajuste` todo lo que no reconoce -- None, la cadena vacía
    y grafías que no están en el catálogo, como «CalMa» --, así que el régimen más
    restrictivo era también el de los perfiles con el plan mal puesto. En producción el
    17-08 eran 5 perfiles (4 sin plan y 1 «CalMa»), y 3 de ellos sin macros: uno era una
    clienta real y activa, que no podía pasar del cuestionario.
    """
    for plan in (None, "", "CalMa", "loquesea"):
        puede, _ = asyncio.run(puede_ajustarlos(None, {"id": "x", "plan": plan,
                                                       "macros_training": {}}))
        assert puede is True, f"con plan={plan!r} se queda encerrado"


# ── Punto 17: el lector de dieta elegía variantes que el cliente no había dicho ────────

def test_el_lector_prefiere_lo_que_menos_supone():
    """«leche» no puede acabar en «Leche desnatada» habiendo «Leche».

    Se ordena por (no empieza por lo pedido, palabras que sobran, largo): la ficha que menos
    añade es la que menos supone.
    """
    candidatos = ["Leche desnatada", "Leche", "Leche entera", "Bebida de avena con leche"]
    assert min(candidatos, key=lambda n: _distancia_a_lo_pedido("leche", n)) == "Leche"


def test_el_lector_no_se_va_a_una_preparacion():
    """«verduras» debe preferir «Verduras» a «Crema de verduras», que es otro plato."""
    candidatos = ["Crema de verduras", "Verduras salteadas", "Verduras"]
    assert min(candidatos, key=lambda n: _distancia_a_lo_pedido("verduras", n)) == "Verduras"


def test_entre_dos_variantes_gana_la_mas_corta_y_es_estable():
    """Cuando solo hay variantes se elige igual, pero SIEMPRE la misma: el cliente la ve
    escrita en la pantalla de confirmar con lo que él escribió al lado, y puede corregirla."""
    candidatos = ["Arroz integral", "Arroz blanco"]
    elegido = min(candidatos, key=lambda n: _distancia_a_lo_pedido("arroz", n))
    assert elegido == "Arroz blanco"
    assert min(reversed(candidatos), key=lambda n: _distancia_a_lo_pedido("arroz", n)) == elegido


# ── Punto 4: el peso decía lo contrario en Mis macros y en Seguimiento ─────────────────

def test_el_peso_se_sanea_igual_en_las_dos_pantallas():
    """Seguimiento leía `weight` en crudo. Estos son los valores reales que hay en
    producción y que hacían que la misma gráfica dijera «50 kg» y «77,1 kg»."""
    assert sanea_peso(0) is None            # el 0,0 de los ajustes viejos
    assert sanea_peso(0.433) is None        # un % de grasa metido donde va el peso
    assert sanea_peso(819) == 81.9          # error de coma
    assert sanea_peso(77.1) == 77.1
