"""
La evolucion de referencia: el octavo apartado del informe (documento, parte 8).

"Cómo va respecto a gente de su perfil." Lo delicado aqui no es el percentil, son los dos
frenos: con poca gente detras no se enseña nada (seria ruido, y ademas dejaria deducir el
progreso de una persona concreta), y la comparacion nunca sustituye al objetivo propio,
que sale de SU perfil.
"""
import pytest

from core.informe_mensual import COHORTE_MINIMA, evolucion_de_referencia


def cohorte(n, valor=-0.5):
    return [valor] * n


class TestCuandoNoSeEnseña:
    def test_con_poca_gente_no_se_compara(self):
        r = evolucion_de_referencia(-0.7, cohorte(COHORTE_MINIMA - 1))
        assert r["disponible"] is False and "suficientes personas" in r["motivo"]

    def test_sin_cohorte_tampoco(self):
        assert evolucion_de_referencia(-0.7, None)["disponible"] is False
        assert evolucion_de_referencia(-0.7, [])["disponible"] is False

    def test_sin_su_propio_ritmo_no_hay_nada_que_situar(self):
        assert evolucion_de_referencia(None, cohorte(20))["disponible"] is False

    def test_en_mantenimiento_no_se_compara(self):
        """Ahí "ir mejor" no significa nada."""
        r = evolucion_de_referencia(-0.1, cohorte(20), sentido="mantener")
        assert r["disponible"] is False

    def test_la_basura_de_la_cohorte_no_cuenta(self):
        r = evolucion_de_referencia(-0.7, [None, "x", -0.5] + cohorte(3))
        assert r["disponible"] is False and r["cohorte"] == 4


class TestDondeQueda:
    def test_perdiendo_mas_que_todos_va_por_delante(self):
        r = evolucion_de_referencia(-1.0, cohorte(10, -0.3), sentido="bajar")
        assert r["percentil"] == 100 and "por delante" in r["texto"]

    def test_perdiendo_menos_que_todos_va_por_detras(self):
        r = evolucion_de_referencia(-0.1, cohorte(10, -0.8), sentido="bajar")
        assert r["percentil"] == 0 and "por detrás" in r["texto"]

    def test_en_volumen_se_invierte(self):
        """Subiendo, ganar más es ir por delante."""
        r = evolucion_de_referencia(0.9, cohorte(10, 0.2), sentido="subir")
        assert r["percentil"] == 100

    def test_justo_en_medio(self):
        ritmos = [-0.9, -0.8, -0.7, -0.6, -0.4, -0.3, -0.2, -0.1]
        r = evolucion_de_referencia(-0.5, ritmos, sentido="bajar")
        assert r["percentil"] == 50 and "en la media" in r["texto"]


class TestLoQueNoSeFiltra:
    def test_no_salen_datos_de_nadie(self):
        """Solo agregados: percentil, tamaño y media. Nunca un ritmo individual."""
        r = evolucion_de_referencia(-0.7, [-0.1, -0.2, -0.3, -0.4, -0.5, -0.6, -0.8, -0.9])
        assert set(r) == {"disponible", "percentil", "cohorte", "tu_ritmo_semanal_pct",
                          "media_cohorte_pct", "texto", "nota"}

    def test_recuerda_que_el_objetivo_es_el_suyo(self):
        r = evolucion_de_referencia(-0.7, cohorte(10))
        assert "el tuyo" in r["nota"]

    def test_ir_por_detras_no_se_cuenta_como_suspenso(self):
        r = evolucion_de_referencia(-0.1, cohorte(10, -0.8))
        assert "no es un suspenso" in r["texto"].lower()
