"""
La llave propia del cierre del día y los precios congelados (decisiones de Jesús, 24-08).

DOS COSAS, LAS DOS DE `models/user.py`:

1) EL CIERRE DEL DÍA TIENE LLAVE PROPIA. Vivía detrás de la habilitación «reportes» y 81
   perfiles de producción no la tienen -- El Lunes Empiezo (51), Mantenimiento (19),
   Calculadora JP (7), Básica (1) y 3 sin plan --, así que no podían contar su día.
   Darles «reportes» les encendería un calendario de reportes que su plan no vende, así
   que la llave es `cierre_dia` y la llevan TODOS los planes.

2) EL PRECIO DE LOS QUE YA ESTÁN NO SE TOCA. «Los clientes que vienen del sistema anterior
   conservan su plan y su precio; las tarifas nuevas solo aplican a clientes nuevos.» En
   producción hay 69 clientes de pago sin precio en la ficha, que tiran de la tarifa del
   catálogo: subirla se lo subía a todos de golpe.
"""
import pytest

from models.user import (
    PLAN_CATALOG,
    PLAN_TYPES,
    cierre_del_dia_incluido,
    derive_features,
    merged_catalog,
    precio_de_ciclo,
    tarifa_del_plan,
)


class TestLaLlaveDelCierreDelDia:
    def test_la_llevan_todos_los_planes(self):
        """Los 21, no solo los que venden reportes."""
        sin_llave = [c for c, p in PLAN_TYPES.items() if "cierre_dia" not in p["features"]]
        assert sin_llave == []

    @pytest.mark.parametrize("code", ["elm", "mantenimiento", "calculadora_jp", "basica"])
    def test_los_cuatro_que_no_tienen_reportes_si_cierran_el_dia(self, code):
        """Son los cuatro planes de los 81 clientes del recuento del 24-08."""
        features = PLAN_TYPES[code]["features"]
        assert "reportes" not in features
        assert "cierre_dia" in features

    def test_sin_campo_escrito_es_que_si(self):
        """Ninguna ficha lo declara y los overrides guardados en db.plan_overrides
        tampoco: con el valor por defecto apagado, encender la llave habría dejado fuera
        justo a los planes que alguien tocó desde el panel."""
        assert cierre_del_dia_incluido({}) is True
        assert cierre_del_dia_incluido(None) is True
        assert "cierre_dia" in derive_features({"reportes": []})

    def test_se_puede_apagar_plan_a_plan(self):
        assert cierre_del_dia_incluido({"cierre_dia": False}) is False
        assert "cierre_dia" not in derive_features({"cierre_dia": False})

    def test_un_override_viejo_del_panel_no_apaga_la_llave(self):
        """Los overrides guardados antes de hoy traen el dict de habilitaciones entero y
        sin `cierre_dia`. Se mezclan clave a clave, así que el plan sigue con la llave."""
        catalogo = merged_catalog({"elm": {"habilitaciones": {"reportes": [],
                                                              "suplementacion": "guia"}}})
        assert "cierre_dia" in catalogo["elm"]["features"]

    def test_apagarla_desde_el_panel_llega_al_servidor(self):
        catalogo = merged_catalog({"elm": {"habilitaciones": {"cierre_dia": False}}})
        assert "cierre_dia" not in catalogo["elm"]["features"]


class TestElPrecioCongelado:
    def test_el_precio_de_la_ficha_manda_sobre_la_tarifa(self):
        """Lo de siempre, y es la primera defensa: el que pasó por la pasarela tiene su
        importe escrito en el perfil (`core/stripe_billing`), y ese no lo mueve nadie."""
        catalogo = merged_catalog()
        perfil = {"plan": "nivel1", "price": 197.0, "created_at": "2026-01-01T00:00:00+00:00"}
        assert precio_de_ciclo(perfil, catalogo) == 197.0

    def test_subir_la_tarifa_no_le_sube_el_precio_al_que_ya_estaba(self):
        """El caso que hay que evitar: 69 clientes de producción sin precio en la ficha
        que tiran de la tarifa del catálogo."""
        catalogo = merged_catalog()
        catalogo["nivel1"] = {**catalogo["nivel1"], "precio": 297.0,
                              "precios_anteriores": [{"hasta": "2026-09-01", "importe": 247.0}]}
        viejo = {"plan": "nivel1", "created_at": "2026-05-17T03:15:15+00:00"}
        nuevo = {"plan": "nivel1", "created_at": "2026-09-15T10:00:00+00:00"}
        assert precio_de_ciclo(viejo, catalogo) == 247.0
        assert precio_de_ciclo(nuevo, catalogo) == 297.0

    def test_sin_fecha_de_alta_se_le_da_la_tarifa_mas_vieja(self):
        """14 perfiles de producción no tienen `created_at`. No saber cuándo entró alguien
        no puede ser el motivo de cobrarle más."""
        plan = {"precio": 297.0, "precios_anteriores": [{"hasta": "2026-09-01", "importe": 247.0},
                                                        {"hasta": "2025-01-01", "importe": 197.0}]}
        assert tarifa_del_plan(plan, None) == 197.0
        assert tarifa_del_plan(plan, "2024-06-01") == 197.0
        assert tarifa_del_plan(plan, "2026-02-01") == 247.0
        assert tarifa_del_plan(plan, "2026-12-01") == 297.0

    def test_hoy_ninguna_ficha_congela_nada_y_los_numeros_no_se_mueven(self):
        """El candado es para el siguiente cambio de tarifa: mientras nadie escriba
        `precios_anteriores`, cada plan vale su `precio` de siempre."""
        for code, plan in PLAN_CATALOG.items():
            assert "precios_anteriores" not in plan, code
            assert tarifa_del_plan(plan, "2020-01-01") == float(plan["precio"])

    def test_la_cortesia_sigue_a_cero(self):
        catalogo = merged_catalog()
        assert precio_de_ciclo({"plan": "nivel2", "comp_plan": True}, catalogo) == 0.0

    def test_una_tarifa_ilegible_no_deja_al_cliente_sin_precio(self):
        plan = {"precio": 100.0, "precios_anteriores": [{"hasta": "2026-09-01", "importe": "ochenta"}]}
        assert tarifa_del_plan(plan, "2026-01-01") == 100.0
