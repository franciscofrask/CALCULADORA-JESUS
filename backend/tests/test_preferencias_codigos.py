# -*- coding: utf-8 -*-
"""
Punto 4.18: «7 categorias seleccionadas» y solo una marcada.

No era el contador. Los clientes que vinieron de Calma tienen guardados los CODIGOS de
categoria ('8', '2.3') y toda la app trabaja con NOMBRES ('panes', 'vacuno'), asi que ni se
marcaban las casillas ni filtraba nada: `AVOIDABLE_PREFIXES.get('8')` no existe. Sus
preferencias eran datos muertos desde la migracion.
"""
from core.preferencias import a_nombres
from routes.calculator import AVOIDABLE_PREFIXES


class TestLoQueHayGuardadoEnProduccion:
    def test_los_codigos_se_traducen(self):
        """Los ocho mas frecuentes de la base, tal cual estan guardados."""
        assert a_nombres(["8"]) == ["panes"]
        assert a_nombres(["21"]) == ["arroces"]
        assert a_nombres(["2.3"]) == ["vacuno"]
        assert a_nombres(["11"]) == ["fruta"]
        assert a_nombres(["3"]) == ["pescados"]

    def test_el_caso_de_jesus(self):
        """Siete guardadas, siete marcadas."""
        guardadas = ["8", "21", "22", "2.3", "2.2", "11", "3"]
        nombres = a_nombres(guardadas)
        assert len(nombres) == 7, f"salen {len(nombres)}: {nombres}"
        assert all(n in AVOIDABLE_PREFIXES for n in nombres), \
            "si un nombre no esta en el mapa, la casilla no existe y no se marca"

    def test_varios_codigos_de_la_misma_no_la_duplican(self):
        """La proteina en polvo son tres codigos (4, 29, 30) y una sola casilla."""
        assert a_nombres(["4", "29", "30"]) == ["proteina_polvo"]


class TestQueNoSeRompeNadaDeLoQueYaFuncionaba:
    def test_los_nombres_se_quedan_como_estan(self):
        """Quien paso por la pantalla nueva ya las tiene bien; no se le tocan."""
        assert a_nombres(["panes", "fruta"]) == ["panes", "fruta"]

    def test_mezclados_tambien(self):
        assert a_nombres(["panes", "21"]) == ["panes", "arroces"]

    def test_no_se_repiten(self):
        assert a_nombres(["panes", "8", "panes"]) == ["panes"]


class TestLosBordes:
    def test_un_codigo_que_ya_no_existe_se_cae(self):
        """Arrastrarlo solo sirve para que el contador diga un numero que no cuadra."""
        assert a_nombres(["999", "8"]) == ["panes"]

    def test_un_codigo_general_se_abre_en_los_suyos(self):
        """Quien dijo que le gusta la carne no dijo que solo la de aves."""
        r = a_nombres(["2"])
        assert "aves" in r and "cerdo" in r and "vacuno" in r
        assert all(n in AVOIDABLE_PREFIXES for n in r)

    def test_vacio_y_basura(self):
        for x in (None, [], ["", "  "], [None]):
            assert a_nombres(x) == []
