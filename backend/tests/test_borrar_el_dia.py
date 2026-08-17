"""Vaciar el día se le CUENTA al cliente, y no se le recomienda nada en ese mismo turno.

Los tres fallos que Francisco vio el 17-08-2026 al pedir «elimina el día completo»:

  1. se borró y el asistente cerró el turno hablando de otra cosa: se quedó sin saber si su
     día seguía ahí;
  2. encima le soltó el guion del intra con sus tarjetas, que él no había pedido (vaciar deja
     en la primera comida y con entreno en ayunas esa es el intra);
  3. y la nota de «vaciado pendiente» se quedaba armada tras vaciar con `forzar`, así que el
     siguiente «sí» del cliente -- que contestaba a «¿te monto la Comida 1?» -- volvía a
     vaciar el día y se comía su respuesta.

Aquí se prueban las ramas de código, sin modelo y sin Mongo: son candados deterministas y es
justamente lo que los hace fiables.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_loop import _YA_DICE_QUE_LO_VACIO  # noqa: E402
from agent_tools import AgentTools  # noqa: E402


class _BotEnElIntra:
    """Lo justo que lee `guion_del_peri`: dónde está y qué le falta."""

    def __init__(self, state=None, mensaje=""):
        self.state = state if state is not None else {}
        self.mensaje_en_curso = mensaje

    def current_meal_key(self):
        return "Intra"

    def get_remaining_macros(self):
        return {"P": 9.0, "H": 15.0, "G": 0.0}

    @staticmethod
    def _norm_text(t):
        import unicodedata
        return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower())
                       if unicodedata.category(c) != "Mn")


def _tools(state=None, mensaje=""):
    t = AgentTools.__new__(AgentTools)      # sin `crear`: no hace falta el catálogo
    t.bot = _BotEnElIntra(state, mensaje)
    return t


def test_el_guion_del_intra_sigue_saliendo_cuando_toca():
    r = _tools().guion_del_peri()
    assert r.get("ok") and r.get("texto"), "el guion del método no puede dejar de decirse"


def test_tras_vaciar_el_dia_no_se_recomienda_nada_en_ese_turno():
    r = _tools({"vacio_el_dia_en_el_turno": True}).guion_del_peri()
    assert r.get("ok") is False
    assert not r.get("texto"), "quien acaba de tirar su día no ha pedido recomendaciones"
    assert "vaciar" in (r.get("error") or ""), r


def test_pedir_borrar_con_palabras_abre_los_dos_candados():
    """El candado de la comida traída de Nutrición frenaba «vacía el día» (17-08): el
    cliente no nombraba la Comida 4, así que el asistente le pedía permiso otra vez."""
    pide = ["vacia el dia", "vacía el día", "elimina el dia completo", "borra todo",
            "limpia la comida 2", "quitame todo", "deja la comida 1 vacia"]
    no_pide = ["ponme 200 g de arroz", "que hay en el dia?", "olvida los menus",
               "esas opciones no me valen", "si", "vamos a la comida 2"]
    for m in pide:
        assert _tools(mensaje=m)._cliente_pidio_borrar(), m
    for m in no_pide:
        assert not _tools(mensaje=m)._cliente_pidio_borrar(), m


def test_el_aviso_del_vaciado_se_antepone_solo_si_falta():
    ya_lo_dice = [
        "Listo, hemos vaciado todo el día.",
        "Día vacío y ahora estás en Intra-entreno.",     # con la í acentuada
        "He borrado todas las comidas.",
        "Todo eliminado.",
        "El día queda a cero.",
        "Te lo he dejado en blanco.",
    ]
    no_lo_dice = [
        "Ya no hay nada puesto; estás en Intra-entreno.",
        "Te propongo montar el Intra-entreno, ¿te parece?",
        "",
    ]
    for texto in ya_lo_dice:
        assert _YA_DICE_QUE_LO_VACIO.search(texto), texto
    for texto in no_lo_dice:
        assert not _YA_DICE_QUE_LO_VACIO.search(texto), texto
