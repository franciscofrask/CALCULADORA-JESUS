"""
La traza de cada turno del asistente, guardada en la base.

Hasta el 17-08 la traza se escribía solo con `logger.info` en el pod: el despliegue de esa
madrugada se llevó por delante las del día anterior, justo las de la sesión que había que
analizar, y no quedó forma de saber qué herramientas había llamado el agente. Lo que se
fija aquí:

  - que el turno se guarda entero (mensaje, herramientas en orden, respuesta y tiempos),
  - que un turno de los que contestan SIN pasar por el modelo también deja documento,
  - que los tiempos permiten separar el modelo de nuestra cocina,
  - y que si la escritura falla, el chat sigue: un registro perdido no puede tumbar la
    comida que el cliente está montando.
"""
import asyncio

from core import trazas_chat


class ColeccionDeMentira:
    def __init__(self, revienta=False):
        self.docs = []
        self.revienta = revienta

    async def insert_one(self, doc):
        if self.revienta:
            raise RuntimeError("mongo caído")
        self.docs.append(doc)
        return type("R", (), {"inserted_id": "x"})()


class BaseDeMentira:
    def __init__(self, revienta=False):
        self.chat_traces = ColeccionDeMentira(revienta)


class BotDeMentira:
    """Lo justo que lee la traza del chatbot de verdad."""

    def __init__(self, restante=None, revienta_restante=False):
        self.session_id = "chat_u1_20260817"
        self.usuario_id = "u1"
        self.state = {"fecha": "2026-08-17", "comida_actual": 2, "step": "building_meal"}
        self._restante = restante or {"P": 12.0, "H": -3.0, "G": 0.0}
        self._revienta = revienta_restante

    def get_remaining_macros(self):
        if self._revienta:
            raise RuntimeError("sin estado")
        return self._restante


def _guardar(bot, base, **kwargs):
    trazas_chat.db = base          # ninguna prueba escribe en la base de verdad
    asyncio.run(trazas_chat.guardar(chatbot=bot, **kwargs))
    return base.chat_traces.docs


def test_guarda_el_turno_entero():
    bot, base = BotDeMentira(), BaseDeMentira()
    respuesta = {
        "message": "Te he puesto 100 g de pollo.",
        "traza": [
            {"herramienta": "buscar_alimentos", "args": {"texto": "pollo"},
             "resultado_resumen": "{'items': [...]}", "ms": 120},
            {"herramienta": "editar_comida", "args": {"operaciones": [{"op": "añadir"}]},
             "resultado_resumen": "{'ok': True}", "ms": 80},
        ],
    }
    docs = _guardar(bot, base, mensaje="ponme pollo", respuesta=respuesta, ms=4300)

    assert len(docs) == 1
    d = docs[0]
    assert d["user_id"] == "u1" and d["session_id"] == "chat_u1_20260817"
    assert d["mensaje"] == "ponme pollo"
    assert d["respuesta"].startswith("Te he puesto")
    assert [h["herramienta"] for h in d["herramientas"]] == ["buscar_alimentos", "editar_comida"]
    assert d["comida"] == 2 and d["paso"] == "building_meal"
    assert d["fecha_dieta"] == "2026-08-17"
    assert d["restante"] == {"P": 12.0, "H": -3.0, "G": 0.0}
    assert d["sin_herramientas"] is False


def test_los_tiempos_separan_el_modelo_de_las_herramientas():
    """El total menos las herramientas es lo que se fue en el modelo: sin esto, «el chat
    tarda quince segundos» no se puede ni medir."""
    bot, base = BotDeMentira(), BaseDeMentira()
    respuesta = {"message": "ya está", "traza": [
        {"herramienta": "componer_menu", "args": {}, "resultado_resumen": "ok", "ms": 2200},
        {"herramienta": "revisar_borrador", "args": {}, "resultado_resumen": "ok", "ms": 300},
    ]}
    d = _guardar(bot, base, mensaje="componme la comida", respuesta=respuesta, ms=15000)[0]

    assert d["ms_total"] == 15000
    assert d["ms_herramientas"] == 2500          # 2200 + 300
    assert d["ms_total"] - d["ms_herramientas"] == 12500


def test_un_atajo_sin_herramientas_tambien_deja_traza():
    """Los caminos que contestan antes de llegar al modelo (el «sí» a una oferta, deshacer,
    navegar) son los que más despistan cuando algo sale raro: que no llamen a nada ES la
    respuesta, y para verlo tiene que existir el documento."""
    bot, base = BotDeMentira(), BaseDeMentira()
    d = _guardar(bot, base, mensaje="sí", respuesta={"message": "Hecho."}, ms=90)[0]

    assert d["herramientas"] == []
    assert d["sin_herramientas"] is True
    assert d["ms_herramientas"] == 0


def test_lo_muy_largo_se_corta():
    """Un turno con quince búsquedas y sus resultados enteros son cientos de kilobytes por
    documento. Para diagnosticar basta con el principio de cada cosa."""
    bot, base = BotDeMentira(), BaseDeMentira()
    respuesta = {
        "message": "x" * 9000,
        "traza": [{"herramienta": "buscar_alimentos", "args": {"texto": "y" * 3000},
                   "resultado_resumen": "z" * 3000, "ms": 10}],
    }
    d = _guardar(bot, base, mensaje="a" * 5000, respuesta=respuesta, ms=100)[0]

    assert len(d["mensaje"]) <= trazas_chat.TOPE_MENSAJE + 1
    assert len(d["respuesta"]) <= trazas_chat.TOPE_RESPUESTA + 1
    assert len(d["herramientas"][0]["args"]) <= trazas_chat.TOPE_ARGS + 1
    assert len(d["herramientas"][0]["resultado"]) <= trazas_chat.TOPE_RESUMEN + 1


def test_si_la_base_falla_el_chat_no_se_entera():
    """Quedarse sin registro es un problema nuestro, no del cliente que está comiendo."""
    bot, base = BotDeMentira(), BaseDeMentira(revienta=True)
    _guardar(bot, base, mensaje="hola", respuesta={"message": "hola"}, ms=10)   # no levanta
    assert base.chat_traces.docs == []


def test_si_no_se_puede_leer_lo_que_falta_se_guarda_igual():
    bot, base = BotDeMentira(revienta_restante=True), BaseDeMentira()
    d = _guardar(bot, base, mensaje="hola", respuesta={"message": "hola"}, ms=10)[0]
    assert d["restante"] is None
    assert d["mensaje"] == "hola"


def test_un_turno_que_revienta_deja_el_error_escrito():
    """Si el turno se cae, el documento es lo único que queda para saber por dónde iba."""
    bot, base = BotDeMentira(), BaseDeMentira()
    d = _guardar(bot, base, mensaje="componme el día", respuesta=None, ms=8000,
                 error="TimeoutError()")[0]
    assert d["error"] == "TimeoutError()"
    assert d["respuesta"] == ""
    assert d["ms_total"] == 8000
