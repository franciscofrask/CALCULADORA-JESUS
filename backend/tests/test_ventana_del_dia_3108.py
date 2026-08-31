# -*- coding: utf-8 -*-
"""LA VENTANA DEL CIERRE DEL DIA (doc «El día», 31-08).

«Una sola ventana, no dos cosas»: el cierre de un dia esta abierto desde su hora hasta las
15:00 del dia siguiente. Aqui se prueban los bordes, que es donde estan los fallos de este
tipo de regla, y la escalada de la linea del Inicio.

Se prueba la funcion pura y no la pantalla a proposito: las horas son lo unico de este
documento que no se puede mirar con los ojos sin esperar al dia siguiente.
"""
from datetime import date, datetime

import pytest

from core.ventana_del_dia import (HORA_LIMITE_DE_AYER, HORA_MINIMA, dia_abierto,
                                  dias_sin_cerrar, hora_de_apertura, texto_de_la_linea)

HOY = date(2026, 8, 31)
AYER = date(2026, 8, 30)


def a_las(h, m=0):
    return datetime(2026, 8, 31, h, m)


class TestLaVentana:
    @pytest.mark.parametrize("hora,esperado", [
        (0, AYER), (7, AYER), (14, AYER),          # la mañana: ayer sigue abierto
        (15, None), (16, None),                    # las dos horas de hueco
        (17, HOY), (21, HOY), (23, HOY),           # la noche: el de hoy
    ])
    def test_que_dia_esta_abierto_a_cada_hora(self, hora, esperado):
        assert dia_abierto(a_las(hora), HOY) == esperado

    def test_los_dos_bordes_al_minuto(self):
        """Las 14:59 y las 15:00 no son lo mismo, y las 16:59 y las 17:00 tampoco."""
        assert dia_abierto(a_las(14, 59), HOY) == AYER
        assert dia_abierto(a_las(15, 0), HOY) is None
        assert dia_abierto(a_las(16, 59), HOY) is None
        assert dia_abierto(a_las(17, 0), HOY) == HOY

    def test_nunca_hay_dos_dias_abiertos(self):
        """Lo dice el documento y es lo que sostiene la ventana: a ninguna hora del dia
        estan abiertos el de hoy y el de ayer a la vez."""
        for h in range(24):
            abierto = dia_abierto(a_las(h), HOY)
            assert abierto in (None, HOY, AYER)
            # Y no hay forma de que devuelva los dos: devuelve uno o ninguno.


class TestLaHoraQueElige:
    def test_por_defecto_las_cinco(self):
        assert hora_de_apertura(None) == HORA_MINIMA == 17

    def test_no_se_puede_adelantar(self):
        """«Puedes activarla a cualquier hora A PARTIR DE las 17:00.» Antes no: no se puede
        cerrar un dia que no ha pasado."""
        for h in (0, 9, 13, 16):
            assert hora_de_apertura(h) == HORA_MINIMA

    def test_si_se_puede_retrasar(self):
        """Los turnos de noche, que estan en su lista de particularidades: al que sale a las
        dos de la mañana las 17:00 no le sirven."""
        assert hora_de_apertura(22) == 22
        assert dia_abierto(a_las(21), HOY, 22) is None
        assert dia_abierto(a_las(22), HOY, 22) == HOY

    def test_retrasarla_no_toca_la_ventana_de_la_mañana(self):
        """La mañana siguiente es siempre hasta las 15:00, la elija a la hora que la elija:
        el limite de abajo es de la ventana, no de su hora."""
        assert dia_abierto(a_las(11), HOY, 22) == AYER
        assert dia_abierto(a_las(15), HOY, 22) is None

    def test_una_hora_imposible_no_rompe_nada(self):
        for basura in ("", "nueve", 99, -3, None):
            assert hora_de_apertura(basura) == HORA_MINIMA


class TestLaRacha:
    def test_sin_ninguno_cerrado_cuenta_hacia_atras(self):
        # A las 20:00 ayer ya se perdio, asi que se empieza a contar en ayer.
        assert dias_sin_cerrar([], a_las(20), HOY) == 60      # el tope

    def test_hoy_nunca_cuenta(self):
        """No ha terminado: contarlo seria reñirle por algo que aun puede hacer."""
        # Cerro anteayer y ayer; hoy no, pero son las 20:00 y todavia puede.
        hechos = ["2026-08-29", "2026-08-30"]
        assert dias_sin_cerrar(hechos, a_las(20), HOY) == 0

    def test_por_la_mañana_ayer_todavia_no_cuenta(self):
        """Son las once y el de ayer sigue abierto: no es un dia perdido."""
        hechos = ["2026-08-29"]           # ayer NO
        assert dias_sin_cerrar(hechos, a_las(11), HOY) == 0

    def test_a_partir_de_las_tres_ayer_ya_cuenta(self):
        hechos = ["2026-08-29"]
        assert dias_sin_cerrar(hechos, a_las(15), HOY) == 1

    @pytest.mark.parametrize("faltan,esperado", [(1, 1), (2, 2), (4, 4), (7, 7)])
    def test_cuenta_los_seguidos(self, faltan, esperado):
        from datetime import timedelta
        # Cerro todos menos los `faltan` ultimos (sin contar hoy).
        hechos = [(HOY - timedelta(days=d)).isoformat() for d in range(faltan + 1, 30)]
        assert dias_sin_cerrar(hechos, a_las(20), HOY) == esperado

    def test_un_hueco_viejo_no_suma(self):
        """La racha son dias SEGUIDOS: lo de hace tres semanas no se acumula."""
        from datetime import timedelta
        hechos = [(HOY - timedelta(days=d)).isoformat() for d in range(1, 30) if d != 20]
        assert dias_sin_cerrar(hechos, a_las(20), HOY) == 0


class TestLaLineaDelInicio:
    def test_el_dia_normal(self):
        assert texto_de_la_linea(0, False) == {
            "titulo": "¿Cómo fuiste hoy?", "detalle": "Para rellenar al final del día"}

    def test_a_los_dos_dias_le_pide_el_de_hoy(self):
        """«No lo dejes hoy tambien» es lo que hace el trabajo: le pide el de hoy, no le
        riñe por los de atras."""
        linea = texto_de_la_linea(2, False)
        assert linea["titulo"] == "¿Cómo fuiste hoy?"
        assert linea["detalle"] == "Llevas 2 días seguidos sin cerrar, no lo dejes hoy también"

    def test_a_los_cuatro_cambia_el_titulo(self):
        assert texto_de_la_linea(4, False) == {
            "titulo": "Llevas 4 días sin cerrar",
            "detalle": "Retómalo hoy mismo: es de donde salen tus ajustes"}

    def test_a_la_semana_deja_de_insistir_pero_no_desaparece(self):
        """«La linea NO desaparece. Si se quitara, se queda sin el unico sitio donde se le
        dice y no vuelve.»"""
        linea = texto_de_la_linea(7, False)
        assert linea["titulo"] == "Llevas una semana sin cerrar el día"
        assert "Dejo de recordártelo" in linea["detalle"]
        # Y a los veinte dias sigue diciendo lo mismo, no algo peor.
        assert texto_de_la_linea(20, False) == linea

    def test_la_mañana_manda_sobre_la_racha(self):
        """Si ayer sigue abierto, lo que toca es decirselo, no contarle los dias."""
        linea = texto_de_la_linea(9, True)
        assert linea == {"titulo": "Ayer no cerraste el día",
                         "detalle": "Puedes hacerlo hasta las 3 de la tarde"}

    def test_los_cuatro_estados_son_distintos(self):
        textos = {tuple(texto_de_la_linea(r, False).values()) for r in (0, 2, 4, 7)}
        assert len(textos) == 4
