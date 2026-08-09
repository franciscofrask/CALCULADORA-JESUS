# -*- coding: utf-8 -*-
"""
Punto 4.2: los cuatro problemas de «Sugerir ajuste (IA)».

El caso es el que probo Jesus: cliente en definicion, 80 kg, 25 % de grasa, con
195/150/60 · 50/50 · 195/120/60, y la IA propuso 195/130/50 · 50/50 · 195/100/60.

Se prueba lo determinista -- el guardarrail y como se le dan los datos al modelo --, no lo
que escribe el modelo, que no se puede fijar en un test.
"""
import pytest

from macro_agent import (
    MOVIMIENTO_DE_CAMBIO_DE_FASE,
    SYSTEM_PROMPT,
    formatear_macros,
    validar,
)

ACTUALES = {
    "entreno": {"proteina": 195, "hidratos": 150, "grasa": 60},
    "perientreno": {"proteina": 50, "hidratos": 50},
    "descanso": {"proteina": 195, "hidratos": 120, "grasa": 60},
}
PROPUESTA_DE_JESUS = {
    "entreno": {"proteina": 195, "hidratos": 130, "grasa": 50},
    "perientreno": {"proteina": 50, "hidratos": 50},
    "descanso": {"proteina": 195, "hidratos": 100, "grasa": 60},
}


def _avisa_de(warns, *palabras):
    return [w for w in warns if all(p.lower() in w.lower() for p in palabras)]


class TestProblema4ElTamanoDelMovimiento:
    """Tres escalones legales por separado que suman un cambio de fase."""

    def test_el_caso_de_jesus_avisa(self):
        warns = validar(PROPUESTA_DE_JESUS, ACTUALES, [])
        gordos = _avisa_de(warns, "50 g en total")
        assert gordos, f"50 g movidos y ningun aviso. Avisos: {warns}"
        assert "cambio de fase" in gordos[0]

    def test_cada_escalon_por_separado_es_legal(self):
        """Por eso hacia falta el aviso: ninguno de los tres rompe nada."""
        warns = validar(PROPUESTA_DE_JESUS, ACTUALES, [])
        assert not _avisa_de(warns, "no es un escalon"), \
            "los tres saltos son escalones validos del metodo"

    def test_un_ajuste_prudente_no_avisa(self):
        prudente = {
            "entreno": {"proteina": 195, "hidratos": 130, "grasa": 60},
            "perientreno": {"proteina": 50, "hidratos": 50},
            "descanso": {"proteina": 195, "hidratos": 120, "grasa": 60},
        }
        assert not _avisa_de(validar(prudente, ACTUALES, []), "en total")

    def test_en_un_cambio_de_fase_no_estorba(self):
        """Si el ajuste ES un cambio de fase, mover mucho es lo que toca."""
        warns = validar(PROPUESTA_DE_JESUS, ACTUALES, ["Cambio de fase a volumen"])
        assert not _avisa_de(warns, "en total")

    def test_sin_datos_y_moviendo_mucho_se_dice_las_dos_cosas(self):
        warns = validar(PROPUESTA_DE_JESUS, ACTUALES,
                        ["No hay datos de peso ni de cumplimiento"])
        assert _avisa_de(warns, "en total")
        assert _avisa_de(warns, "a ciegas"), \
            "mover 50 g sin datos merece decirlo, no solo avisar del tamano"

    def test_el_umbral_es_el_del_metodo(self):
        assert MOVIMIENTO_DE_CAMBIO_DE_FASE == 40


class TestProblema3ElIntraNoSeConfunde:
    """«Venia sin intra» y dos frases despues «manteniendo el intra en 50»."""

    def test_no_tener_intra_y_no_constar_se_dicen_distinto(self):
        sin_dato = formatear_macros({"entreno": {"proteina": 195, "hidratos": 150, "grasa": 60},
                                     "descanso": {"proteina": 195, "hidratos": 120, "grasa": 60}})
        a_cero = formatear_macros({"entreno": {"proteina": 195, "hidratos": 150, "grasa": 60},
                                   "perientreno": {"proteina": 0, "hidratos": 0},
                                   "descanso": {"proteina": 195, "hidratos": 120, "grasa": 60}})
        assert "NO CONSTA" in sin_dato
        assert "NO TIENE" in a_cero
        assert sin_dato != a_cero, "el mismo guion valia para las dos cosas y por eso se confundia"

    def test_con_intra_se_ve_el_numero(self):
        texto = formatear_macros(ACTUALES)
        assert "Intra P50/H50" in texto
        assert "NO TIENE" not in texto and "NO CONSTA" not in texto


class TestProblema2ElRegistro:
    """Sin tildes, con «coach» y con «prote»."""

    def test_el_prompt_prohibe_coach_y_prote(self):
        bajo = SYSTEM_PROMPT.lower()
        assert "coach" in bajo and "prote\"" in bajo, \
            "el prompt tiene que prohibir explicitamente 'coach' y 'prote'"
        assert "tildes" in bajo, "el prompt tiene que pedir castellano con tildes"

    def test_el_prompt_dice_que_el_razonamiento_es_para_el_entrenador(self):
        assert "ENTRENADOR" in SYSTEM_PROMPT
        assert "para el ENTRENADOR" in SYSTEM_PROMPT

    def test_el_prompt_avisa_de_no_decir_que_se_mantiene_lo_que_cambia(self):
        """Problema 3: «venia sin intra» y «manteniendo el intra en 50» en el mismo texto."""
        assert "SE MANTIENE" in SYSTEM_PROMPT
        assert "NO CONSTA" in SYSTEM_PROMPT or "no consta" in SYSTEM_PROMPT
