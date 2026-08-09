# -*- coding: utf-8 -*-
"""
Punto 5.4: lo que el informe dejo como «no verificado por falta de acceso».

Probado contra la API el 09-08. De los cinco casos, cuatro ya estaban bien y uno no:

    inyeccion en campos de texto ......... BIEN. Los operadores de Mongo se guardan como
                                           texto y `login` con {'$ne': None} devuelve 422.
    tamaño maximo de foto ............... BIEN. 5 MB -> 413, vacia -> 400, .exe -> 400.
    dos entrenadores a la vez ........... BIEN. Dos guardados simultaneos dejan UNA fila:
                                           el indice unico del punto 62 aguanta la carrera.
    texto en campo numerico ............. BIEN. 'mucho' en el peso -> 422.
    NEGATIVOS Y FUERA DE RANGO .......... MAL. peso -80, peso 0, peso 5.000 y % graso 200
                                           se guardaban con un 200.

Lo ultimo es el origen de los «pesos de 38 y 42 kg» que aparecen en el historico, y un peso
malo no se queda quieto en su fila: entra en la serie, en la grafica, en el calculo de macros
y en lo que lee el agente para proponer el ajuste.
"""
import pytest
from pydantic import ValidationError

from models.common import ReportCreate
from models.user import ClientProfileUpdate


class TestElPerfilNoAceptaImposibles:
    @pytest.mark.parametrize("campo,valor", [
        ("weight", -80), ("weight", 0), ("weight", 5000), ("weight", 24),
        ("body_fat", -10), ("body_fat", 0), ("body_fat", 200), ("body_fat", 61),
        ("height", 30), ("height", 300),
        ("age", 3), ("age", 130),
    ])
    def test_fuera_de_rango(self, campo, valor):
        with pytest.raises(ValidationError):
            ClientProfileUpdate(**{campo: valor})

    @pytest.mark.parametrize("campo,valor", [
        ("weight", 80), ("weight", 25), ("weight", 300),
        ("body_fat", 25), ("body_fat", 3), ("body_fat", 60),
        ("height", 175), ("age", 38),
    ])
    def test_lo_normal_pasa(self, campo, valor):
        assert getattr(ClientProfileUpdate(**{campo: valor}), campo) == valor

    def test_no_mandar_nada_sigue_valiendo(self):
        """El perfil se actualiza campo a campo: no poner el peso no es poner un peso malo."""
        p = ClientProfileUpdate(goal="definicion")
        assert p.weight is None and p.body_fat is None


class TestElReporteTampoco:
    @pytest.mark.parametrize("peso", [-80, 0, 5000, 10])
    def test_un_peso_imposible_no_entra(self, peso):
        with pytest.raises(ValidationError):
            ReportCreate(weight=peso)

    def test_un_peso_de_verdad_si(self):
        assert ReportCreate(weight=82.5).weight == 82.5

    def test_los_limites_son_los_mismos_que_los_de_la_serie(self):
        """Si un valor no vale para la serie de peso, tampoco puede valer para el campo."""
        from core.series_cliente import GRASA, PESO

        _, _, peso_min, peso_max = PESO
        _, _, grasa_min, grasa_max = GRASA
        assert ReportCreate(weight=peso_min).weight == peso_min
        assert ClientProfileUpdate(weight=peso_max).weight == peso_max
        assert ClientProfileUpdate(body_fat=grasa_min).body_fat == grasa_min
        assert ClientProfileUpdate(body_fat=grasa_max).body_fat == grasa_max


class TestLaMembresiaVencida:
    """«El cliente sigue activo y sin proximo cobro» -> calcular el estado desde la fecha."""

    def _perfil(self, **kw):
        return {"plan": "gold", "status": "activo", **kw}

    def test_sin_fecha_de_fin_sigue_valiendo_el_estado(self):
        """168 de los 169 perfiles sin Stripe no tienen fecha de fin: no se les puede aplicar."""
        from core.plan_access import has_active_access
        assert has_active_access(self._perfil()) is True

    def test_con_el_ciclo_terminado_se_acaba_el_acceso(self):
        from core.plan_access import has_active_access
        assert has_active_access(self._perfil(current_period_end="2020-01-01")) is False

    def test_con_el_ciclo_en_marcha_no(self):
        from core.plan_access import has_active_access
        assert has_active_access(self._perfil(current_period_end="2099-01-01")) is True

    def test_un_cobro_retrasado_NO_le_quita_la_app(self):
        """Que un cobro no haya entrado no quiere decir que la membresia haya terminado.
        Cortarle la app a alguien que paga por eso seria peor que el fallo."""
        from core.plan_access import has_active_access
        assert has_active_access(self._perfil(next_payment="2020-01-01")) is True

    def test_con_stripe_manda_stripe(self):
        from core.plan_access import has_active_access
        con_stripe = self._perfil(stripe_subscription_id="sub_1",
                                  subscription_status="active",
                                  current_period_end="2020-01-01")
        assert has_active_access(con_stripe) is True
