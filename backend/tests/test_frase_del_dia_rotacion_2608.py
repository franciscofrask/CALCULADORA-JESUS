"""
LA FRASE DEL DÍA NO PUEDE DESAPARECER (punto 103 del artifact del 25-08).

El panel promete, con estas palabras, «si un día no hay frase nueva, el cliente sigue
viendo la última». No se cumplía: Inicio exigía además que la frase guardada fuese LA DE
HOY, así que en cuanto la cola de programadas se vaciaba el bloque entero desaparecía.
Pasó dos días seguidos con 125 clientes entrando.

Desde el 26-08 hay repertorio que ROTA día a día (`frases_rotacion`) y el orden de mando
es: frase puesta para HOY > la rotación de hoy > la última que hubo.

Aquí se comprueban las dos piezas: la elección por fecha (determinista, sin estado) y la
cascada entera de `ajustes_app`, que es donde se decide lo que ve el cliente.
"""
from datetime import date

import pytest

from conftest import corre                                     # noqa: E402
from routes.settings import _frase_por_rotacion, _normalizar_rotacion, ajustes_app


# --- El repertorio, limpio ---------------------------------------------------------

def test_la_rotacion_acepta_textos_pelados_y_diccionarios():
    """Se guarda como [{texto: ...}], pero una carga a mano puede dejar textos sueltos.
    Los dos formatos valen: si no, la rotación se quedaría muda sin decir por qué."""
    assert _normalizar_rotacion(["una", {"texto": "otra"}]) == ["una", "otra"]


def test_la_rotacion_tira_lo_vacio():
    """Un hueco en la lista correría el turno de todos los días siguientes y, el día que
    le tocara, dejaría la pantalla sin frase: justo el fallo que se está arreglando."""
    assert _normalizar_rotacion(["una", "", {"texto": "  "}, None, {"texto": "otra"}]) == ["una", "otra"]


def test_sin_repertorio_no_hay_frase_de_rotacion():
    assert _frase_por_rotacion([], date(2026, 8, 26)) is None
    assert _frase_por_rotacion(None, date(2026, 8, 26)) is None


# --- La elección del día -----------------------------------------------------------

def test_el_mismo_dia_da_siempre_la_misma_frase():
    """La frase es la misma para todos los clientes, y dos peticiones del mismo día no
    pueden dar cosas distintas: se elige por la fecha, no por un contador guardado."""
    rot = ["a", "b", "c"]
    dia = date(2026, 8, 26)
    assert _frase_por_rotacion(rot, dia) == _frase_por_rotacion(rot, dia)


def test_cambia_de_un_dia_al_siguiente():
    rot = ["a", "b", "c"]
    hoy = _frase_por_rotacion(rot, date(2026, 8, 26))["texto"]
    manana = _frase_por_rotacion(rot, date(2026, 8, 27))["texto"]
    assert hoy != manana


def test_da_la_vuelta_al_llegar_al_final():
    """Doce frases son doce días; el trece vuelve a la primera. Que no se agote nunca es
    la razón de ser de la rotación."""
    rot = [f"f{i}" for i in range(12)]
    primero = date(2026, 8, 26)
    seguidas = [_frase_por_rotacion(rot, date.fromordinal(primero.toordinal() + i))["texto"]
                for i in range(24)]
    assert seguidas[:12] == seguidas[12:]
    assert len(set(seguidas)) == 12


def test_con_una_sola_frase_no_revienta():
    assert _frase_por_rotacion(["única"], date(2026, 8, 26))["texto"] == "única"


def test_la_frase_de_rotacion_sale_fechada_hoy():
    """Va marcada con el día y con `puesta_por: rotacion` para que el panel enseñe lo que
    de verdad está viendo el cliente, y no la última que se escribió a mano."""
    f = _frase_por_rotacion(["una"], date(2026, 8, 26))
    assert f["fecha"] == "2026-08-26"
    assert f["puesta_por"] == "rotacion"


# --- La cascada entera -------------------------------------------------------------

class _Coleccion:
    def __init__(self, doc):
        self._doc = doc
        self.escrituras = []

    async def find_one(self, *_a, **_k):
        return dict(self._doc)

    async def update_one(self, filtro, cambios, **_k):
        self.escrituras.append(cambios)
        self._doc.update(cambios.get("$set", {}))


class _Base:
    def __init__(self, doc):
        self.app_settings = _Coleccion(doc)


@pytest.fixture
def base(monkeypatch):
    """Una base de mentira para `ajustes_app`, y el día de España clavado: la frase se
    elige por fecha, así que un test que dependa del reloj de quien lo corre no vale."""
    def _montar(doc):
        b = _Base(doc)
        monkeypatch.setattr("routes.settings.db", b)
        monkeypatch.setattr("routes.settings.ahora_madrid",
                            lambda: __import__("datetime").datetime(2026, 8, 26, 10, 0))
        return b
    return _montar


def test_la_frase_puesta_para_hoy_manda_sobre_la_rotacion(base):
    """El panel sigue pudiendo poner LA frase de un día concreto. Si la rotación pisara
    eso, escribir una frase a mano no serviría de nada."""
    base({"id": "app",
          "frase_del_dia": {"texto": "la de hoy a mano", "fecha": "2026-08-26"},
          "frases_rotacion": [{"texto": "la que rota"}]})
    ajustes = corre(ajustes_app(con_overrides=False))
    assert ajustes["frase_del_dia"]["texto"] == "la de hoy a mano"


def test_sin_frase_de_hoy_entra_la_rotacion(base):
    """El caso del 25-08: la última frase es de hace días y la cola está vacía. Antes esto
    dejaba el hueco en blanco."""
    base({"id": "app",
          "frase_del_dia": {"texto": "la vieja", "fecha": "2026-08-21"},
          "frases_rotacion": [{"texto": "la que rota"}]})
    ajustes = corre(ajustes_app(con_overrides=False))
    assert ajustes["frase_del_dia"]["texto"] == "la que rota"
    assert ajustes["frases_en_rotacion"] == 1


def test_sin_rotacion_se_queda_la_ultima_que_hubo(base):
    """La promesa literal del panel. Es la red de abajo del todo: aunque no haya
    repertorio, el bloque NO se queda vacío."""
    base({"id": "app", "frase_del_dia": {"texto": "la vieja", "fecha": "2026-08-21"}})
    ajustes = corre(ajustes_app(con_overrides=False))
    assert ajustes["frase_del_dia"]["texto"] == "la vieja"
    assert ajustes["frases_en_rotacion"] == 0


def test_una_programada_que_vence_gana_a_la_rotacion(base):
    """La cola sigue mandando el día que le toca: si no, programar una frase para una
    fecha concreta (un lanzamiento, un festivo) no valdría para nada."""
    b = base({"id": "app",
              "frase_del_dia": {"texto": "la vieja", "fecha": "2026-08-21"},
              "frases_programadas": [{"texto": "la programada", "fecha": "2026-08-26"}],
              "frases_rotacion": [{"texto": "la que rota"}]})
    ajustes = corre(ajustes_app(con_overrides=False))
    assert ajustes["frase_del_dia"]["texto"] == "la programada"
    # Y se asciende en la base, que es lo que la deja como «la última que hubo».
    assert b.app_settings.escrituras


def test_la_rotacion_no_escribe_en_la_base(base):
    """Se calcula al leer. Si escribiera, cada visita de cada cliente sería una escritura
    en el documento que leen todos."""
    b = base({"id": "app",
              "frase_del_dia": {"texto": "la vieja", "fecha": "2026-08-21"},
              "frases_rotacion": [{"texto": "la que rota"}]})
    corre(ajustes_app(con_overrides=False))
    assert b.app_settings.escrituras == []


def test_sin_nada_de_nada_no_hay_frase_pero_tampoco_error(base):
    base({"id": "app"})
    ajustes = corre(ajustes_app(con_overrides=False))
    assert ajustes["frase_del_dia"] is None
