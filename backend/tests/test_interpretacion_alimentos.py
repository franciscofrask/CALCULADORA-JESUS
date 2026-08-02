"""
Interpretar lo que pide el cliente al vocabulario del catalogo (peticion 2026-08-02).

"Si el usuario pide tostadas quiero que la IA tambien sepa interpretar porque quiza
quiere pan tostado. Debe poder discernir estas cosas por su cuenta."

El router (que ya se llama en cada mensaje) traduce: "tostadas" -> "pan tostado",
"chuches" -> "gominolas". Lo que se fija aqui es el orden y los frenos, que es donde esto
se puede volver en contra:

  - lo que escribe el usuario manda; la traduccion es la SEGUNDA via, no un reemplazo,
  - y no se le cambia un alimento por otro en silencio: se le dice.
"""
import pytest

from chatbot import NutritionChatbot as C


class BotFalso(C):
    """Un bot que solo sabe buscar, con un catalogo de mentira."""

    def __init__(self, catalogo):
        self.catalogo = catalogo

    async def search_foods(self, query, limit=5, _remap=True):
        q = (query or "").lower()
        return [dict(f) for f in self.catalogo if q in f["nombre"].lower()][:limit]


CATALOGO = [
    {"nombre": "Pan tostado"},
    {"nombre": "Gominolas clásicas"},
    {"nombre": "Arroz blanco"},
    {"nombre": "Tostadas de avena (Diet Radisson)"},
]


def buscar(nombre, interpretacion):
    """Ejecuta la búsqueda. Sin pytest-asyncio: no hace falta una dependencia para esto."""
    import asyncio
    return asyncio.run(BotFalso(CATALOGO).buscar_con_interpretacion(nombre, interpretacion))


class TestElOrden:
    def test_lo_que_escribe_el_usuario_manda(self):
        """Si lo suyo ya encuentra algo bueno, la traducción no se usa."""
        r = buscar("arroz", "arroz blanco de grano largo")
        assert r[0]["nombre"] == "Arroz blanco"
        assert "_interpretado" not in r[0]

    def test_la_traduccion_entra_donde_no_habia_nada(self):
        r = buscar("chuches", "gominolas")
        assert r[0]["nombre"] == "Gominolas clásicas"
        assert r[0]["_interpretado"] == "chuches"

    def test_sin_traduccion_se_comporta_como_siempre(self):
        assert buscar("nomeconsta", None) == []

    def test_si_la_traduccion_tampoco_encuentra_no_se_inventa_nada(self):
        assert buscar("gaseosa", "bebida de cola") == []

    def test_se_marca_de_donde_sale_para_poder_decirselo(self):
        """Cambiarle un alimento por otro sin avisar es un cambiazo."""
        assert buscar("chuches", "gominolas")[0]["_interpretado"] == "chuches"


class TestLoQueLlegaDelRouter:
    def test_guarda_la_traduccion_aparte_del_nombre(self):
        items = C._normalize_food_items([{"nombre": "tostadas", "busqueda": "pan tostado"}])
        assert items[0]["nombre"] == "tostadas"
        assert items[0]["busqueda"] == "pan tostado"

    def test_si_traduce_a_lo_mismo_no_se_guarda(self):
        items = C._normalize_food_items([{"nombre": "Arroz blanco", "busqueda": "arroz blanco"}])
        assert items[0]["busqueda"] is None

    def test_sin_traduccion_queda_a_nulo(self):
        assert C._normalize_food_items([{"nombre": "pavo"}])[0]["busqueda"] is None

    @pytest.mark.parametrize("v", [None, "", "   ", 5, [], {}])
    def test_la_basura_no_pasa(self, v):
        assert C._normalize_food_items([{"nombre": "pavo", "busqueda": v}])[0]["busqueda"] is None
