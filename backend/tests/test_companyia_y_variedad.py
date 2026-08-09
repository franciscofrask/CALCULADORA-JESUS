"""Que las sugerencias tengan sentido, y que no sean siempre las mismas.

Francisco, 08-08-2026: *«me di cuenta que siempre que piden sugerencias sugiere lo mismo a
todos, esto porque tienen los mismos macros pero igual debería variar; además esas
sugerencias no tienen sentido alguno, comer harina con avena? esa combinación de alimentos
no tiene sentido»*.

Dos cosas distintas, medidas por separado.

**El sentido.** Qué va con qué no lo decide una lista escrita a mano -- eso es justo lo que
está prohibido en este repo -- sino las 147.820 comidas reales de db.diets. La medida es la
elevación: cuántas veces coinciden dos alimentos frente a las que coincidirían por azar.
Separa limpiamente:

    pollo + fiambre de pavo  0.14      arroz + aceite de oliva  2.59
    caseína + frutos rojos   0.25      whey + plátano           2.19
    harina de avena + copos  0.30      claras + pan de barra    1.63

**La variedad.** El recetario ordenaba por error y cogía los tres primeros, así que con los
mismos macros salían siempre las mismas tres recetas. Ahora el error se agrupa en escalones
de 5 g -- desviarse 2 g o 5 no hace mejor a un menú -- y dentro del escalón se baraja con
una semilla estable por cliente, día y comida: el mismo cliente ve lo mismo si recarga, y
otro cliente ve otra cosa.
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


def _db():
    from motor.motor_asyncio import AsyncIOMotorClient
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "jg12_restored")]


def _menus(sesion, fecha="2026-08-10", estilo="", n=3):
    """Los nombres de lo que sugiere, para comparar entre llamadas."""
    async def _correr():
        from chatbot import NutritionChatbot
        from agent_tools import AgentTools
        bot = NutritionChatbot(sesion, _db())
        bot.set_user_macros(MACROS)
        bot.state["fecha_objetivo"] = fecha
        bot.configure_day("entrenamiento", 4, momento_entreno=1, opcion_peri="intra_post")
        tools = await AgentTools.crear(bot)
        r = await tools.componer_menu(estilo=estilo, n=n)
        return [b.get("nombre") or "+".join(str(i["id"]) for i in b["items"])
                for b in (r.get("borradores") or [])]
    return asyncio.run(_correr())


# ------------------------------------------------------------------ el sentido
class TestElPerfilDeCompanyia:
    """La pieza de datos: qué alimentos van juntos, sacado de db.diets."""

    @pytest.fixture(scope="class")
    def perfil(self):
        async def _correr():
            from company_profile import PerfilCompanyia
            return await PerfilCompanyia.cargar(_db())
        p = asyncio.run(_correr())
        if not p.comidas:
            pytest.skip("sin db.company_profiles: correr _perfil_companyia.py")
        return p

    def test_hay_datos_de_sobra(self, perfil):
        assert perfil.comidas > 100000, f"solo {perfil.comidas} comidas"
        assert len(perfil.alimentos) > 500

    @pytest.mark.parametrize("a,b", [
        ("Pechuga de pollo", "Fiambre de pechuga de pavo de buena calidad (más del 85 %)"),
        ("Yogur desnatado natural", "Atún al natural lata"),
        ("Harina de avena", "Copos de avena"),
    ])
    def test_lo_que_no_pega_sale_bajo(self, perfil, a, b):
        async def _correr():
            db = _db()
            fa = await db.foods.find_one({"nombre": a}, {"_id": 0})
            fb = await db.foods.find_one({"nombre": b}, {"_id": 0})
            return fa, fb
        fa, fb = asyncio.run(_correr())
        assert fa and fb, f"no están en el catálogo: {a} / {b}"
        e = perfil.elevacion(fa, fb)
        assert e is not None, "sin datos para juzgar este par"
        from company_profile import ELEVACION_MINIMA
        assert e < ELEVACION_MINIMA, f"«{a}» + «{b}» sale {e:.2f}, y no pegan"

    @pytest.mark.parametrize("a,b", [
        ("Pechuga de pollo", "Arroz blanco"),
        ("Huevos enteros L", "Pan de molde"),
        ("Claras de huevo pasteurizadas", "Huevos enteros L"),
    ])
    def test_lo_que_si_pega_sale_alto(self, perfil, a, b):
        async def _correr():
            db = _db()
            return (await db.foods.find_one({"nombre": a}, {"_id": 0}),
                    await db.foods.find_one({"nombre": b}, {"_id": 0}))
        fa, fb = asyncio.run(_correr())
        assert fa and fb
        e = perfil.elevacion(fa, fb)
        from company_profile import ELEVACION_MINIMA
        assert e is not None and e >= ELEVACION_MINIMA, f"«{a}» + «{b}» sale {e}"

    def test_lo_que_no_se_sabe_no_se_juzga(self, perfil):
        """Un alimento sin usos no puede penalizar a nadie: mismo criterio que el perfil
        de momento."""
        async def _correr():
            db = _db()
            f = await db.foods.find_one({"id": 498}, {"_id": 0})
            return f
        pollo = asyncio.run(_correr())
        inventado = {"id": 999999, "nombre": "Chuchurrumia", "categorias": "99.9"}
        assert perfil.elevacion(pollo, inventado) is None

    def test_el_tamano_sale_de_las_dietas(self, perfil):
        """El sugeridor daba menús de 6 y 7 alimentos; las comidas reales no son así."""
        t = perfil.tamano_habitual()
        assert 3 <= t <= 6, f"tamaño habitual raro: {t}"


class TestLoQueCompone:
    """Lo que monta la app por su cuenta sí se filtra. Las recetas del recetario de Jesús
    NO: son suyas, y contradecirlas con una estadística no nos toca (ver el documento)."""

    def test_lo_que_compone_no_junta_lo_que_no_pega(self):
        async def _correr():
            from chatbot import NutritionChatbot
            from agent_tools import AgentTools
            from company_profile import PerfilCompanyia, ELEVACION_MINIMA
            db = _db()
            perfil = await PerfilCompanyia.cargar(db)
            if not perfil.comidas:
                return None
            malas = []
            for estilo in ("algo con avena", "pollo", "algo rapido", "tostadas"):
                bot = NutritionChatbot(f"comp_{estilo}", db)
                bot.set_user_macros(MACROS)
                bot.configure_day("entrenamiento", 4, momento_entreno=1, opcion_peri="intra_post")
                tools = await AgentTools.crear(bot)
                r = await tools.componer_menu(estilo=estilo, n=3)
                for b in (r.get("borradores") or []):
                    if b.get("origen") != "compuesto" or b.get("avisos"):
                        continue    # el recetario no se juzga; lo rescatado ya lleva aviso
                    foods = [tools.foods[i["id"]] for i in b["items"] if i["id"] in tools.foods]
                    peor = perfil.peor_pareja(foods)
                    if peor and peor[0] < ELEVACION_MINIMA:
                        malas.append((estilo, peor[0], peor[1]["nombre"], peor[2]["nombre"]))
            return malas
        malas = asyncio.run(_correr())
        if malas is None:
            pytest.skip("sin db.company_profiles")
        assert not malas, f"compone combinaciones que nadie come: {malas[:3]}"

    def test_si_todo_discorda_no_deja_al_cliente_sin_nada(self):
        """Pidiendo «tostadas» todo lo que cuadra son tres tostadas distintas juntas y las
        tres se descartaban. Se rescata la menos mala, con su aviso."""
        async def _correr():
            from chatbot import NutritionChatbot
            from agent_tools import AgentTools
            bot = NutritionChatbot("rescate", _db())
            bot.set_user_macros(MACROS)
            bot.configure_day("entrenamiento", 4, momento_entreno=1, opcion_peri="intra_post")
            tools = await AgentTools.crear(bot)
            return await tools.componer_menu(estilo="tostadas", n=3)
        r = asyncio.run(_correr())
        bs = r.get("borradores") or []
        assert bs, f"se queda sin nada que ofrecer: {r.get('sin_resultados_porque')}"
        assert any(b.get("avisos") for b in bs), "rescata y no dice que la opción es rara"


# ----------------------------------------------------------------- la variedad
class TestLaVariedad:
    def test_el_mismo_cliente_ve_lo_mismo(self):
        """Estable dentro de la comida: recargar la página no puede cambiar las opciones."""
        a = _menus("cli-estable")
        b = _menus("cli-estable")
        assert a and a == b, f"{a} != {b}"

    def test_dos_clientes_con_los_mismos_macros_ven_cosas_distintas(self):
        """El fallo que señaló Francisco: mismos macros, mismas tres recetas para todos."""
        vistas = {tuple(_menus(f"cli-{s}")) for s in ("A", "B", "C", "D", "E")}
        assert len(vistas) >= 3, f"5 clientes y solo {len(vistas)} listas distintas"

    def test_dias_distintos_ven_cosas_distintas(self):
        vistas = {tuple(_menus("cli-dias", fecha=f))
                  for f in ("2026-08-10", "2026-08-11", "2026-08-12", "2026-08-13")}
        assert len(vistas) >= 3, f"4 días y solo {len(vistas)} listas distintas"

    def test_variar_no_es_empeorar(self):
        """Barajar solo dentro del escalón de error: las opciones siguen cuadrando."""
        async def _correr():
            from chatbot import NutritionChatbot
            from agent_tools import AgentTools
            peores = []
            for s in ("A", "B", "C", "D"):
                bot = NutritionChatbot(f"cal-{s}", _db())
                bot.set_user_macros(MACROS)
                bot.configure_day("entrenamiento", 4, momento_entreno=1, opcion_peri="intra_post")
                tools = await AgentTools.crear(bot)
                r = await tools.componer_menu(n=3)
                for b in (r.get("borradores") or []):
                    peores.append(sum(abs(v) for v in b["desvio"].values()))
            return peores
        desvios = asyncio.run(_correr())
        assert desvios, "no sugiere nada"
        assert max(desvios) <= 60, f"barajando salen menús muy desviados: {max(desvios):.0f} g"
