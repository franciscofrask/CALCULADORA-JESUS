"""
La renovacion de la semana 12 (especificacion 31-07-2026, partes 1 y 3).

    "Su foto del dia 1 al lado de la de hoy, su evolucion y su resumen del ciclo.
     Tres salidas: renovar, subir de nivel, o salir a la membresia."

Lo que se fija aqui:
  - el precio congelado se respeta al renovar en el mismo plan,
  - al que viene de un plan que ya no se vende no se le ofrece seguir en el,
  - la salida a la membresia esta SIEMPRE, y la ultima,
  - y no se enseña una comparacion de fotos a medias.
"""
from datetime import datetime, timedelta, timezone

import pytest

from core.renovacion import (
    estado_del_ciclo,
    montar_renovacion,
    resumen_del_ciclo,
    salidas,
)
from models.user import PLAN_CATALOG, opciones_de_renovacion

AHORA = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)


def perfil(**extra):
    base = {
        "plan": "nivel2", "week": 11, "body_fat": 19.0,
        "arranque_lunes": (AHORA - timedelta(weeks=11)).isoformat(),
        "fin_de_ciclo": (AHORA + timedelta(days=7)).isoformat(),
        "precio_alta": 897.0,
    }
    base.update(extra)
    return base


class TestElEstadoDelCiclo:
    def test_sabe_cuantos_dias_quedan(self):
        e = estado_del_ciclo(perfil(), AHORA)
        assert e["conocido"] is True and e["dias_restantes"] == 7

    def test_a_una_semana_toca_renovar(self):
        assert estado_del_ciclo(perfil(), AHORA)["toca_renovar"] is True

    def test_en_mitad_del_ciclo_todavia_no(self):
        p = perfil(fin_de_ciclo=(AHORA + timedelta(weeks=6)).isoformat())
        assert estado_del_ciclo(p, AHORA)["toca_renovar"] is False

    def test_un_ciclo_vencido_se_marca(self):
        p = perfil(fin_de_ciclo=(AHORA - timedelta(days=3)).isoformat())
        e = estado_del_ciclo(p, AHORA)
        assert e["ya_vencido"] is True and e["dias_restantes"] == -3

    def test_los_clientes_antiguos_sin_fin_de_ciclo_no_revientan(self):
        """Los de antes del calendario de arranque no lo tienen guardado."""
        e = estado_del_ciclo({"week": 11}, AHORA)
        assert e["conocido"] is False and e["toca_renovar"] is True

    def test_y_en_la_semana_5_a_esos_tampoco_se_les_molesta(self):
        assert estado_del_ciclo({"week": 5}, AHORA)["toca_renovar"] is False


class TestElResumen:
    def _resumen(self, **extra):
        args = dict(
            reporte_primero={"weight": 88.0, "body_fat": 26.0, "photos": ["a", "b", "c"]},
            reporte_ultimo={"weight": 81.0, "photos": ["x", "y", "z"]},
            perfil=perfil(), dias_dieta=70, dias_totales=84, ajustes_de_macros=3)
        args.update(extra)
        return resumen_del_ciclo(**args)

    def test_el_peso_va_en_porcentaje(self):
        r = self._resumen()
        assert r["peso"]["cambio_pct"] == -8.0
        assert r["peso"]["cambio_kg"] == -7.0

    def test_pone_las_fotos_del_dia_1_al_lado_de_las_de_hoy(self):
        r = self._resumen()
        assert r["fotos"]["comparables"] is True
        assert len(r["fotos"]["antes"]) == 3 and len(r["fotos"]["ahora"]) == 3

    def test_sin_fotos_del_principio_no_se_finge_la_comparacion(self):
        r = self._resumen(reporte_primero={"weight": 88.0, "photos": []})
        assert r["fotos"]["comparables"] is False

    def test_sin_fotos_de_ahora_tampoco(self):
        r = self._resumen(reporte_ultimo={"weight": 81.0, "photos": []})
        assert r["fotos"]["comparables"] is False

    def test_cuenta_su_constancia(self):
        r = self._resumen()
        assert r["constancia"]["pct"] == 83

    def test_sin_pesos_no_inventa_el_cambio(self):
        r = self._resumen(reporte_primero=None, reporte_ultimo=None)
        assert r["peso"]["cambio_pct"] is None


class TestLasTresSalidas:
    def _salidas(self, plan="nivel2", precio_alta=847.0):
        return salidas(plan_actual=plan, opciones_catalogo=opciones_de_renovacion(plan),
                       catalogo=PLAN_CATALOG, precio_alta=precio_alta)

    def test_estan_las_tres(self):
        tipos = [s["tipo"] for s in self._salidas()]
        assert "renovar" in tipos and "cambiar" in tipos and "salida" in tipos

    def test_la_de_salir_va_la_ultima(self):
        """Se ofrece, pero no es lo primero que se le pone delante."""
        assert self._salidas()[-1]["tipo"] == "salida"

    def test_seguir_igual_respeta_su_precio_congelado(self):
        s = [x for x in self._salidas(precio_alta=697.0) if x["tipo"] == "renovar"][0]
        assert s["precio"] == 697.0, "paga lo que pagaba, no lo que cuesta hoy"
        assert s["precio_congelado"] is True

    def test_si_su_precio_es_el_de_hoy_no_se_marca_como_congelado(self):
        s = [x for x in self._salidas(precio_alta=847.0) if x["tipo"] == "renovar"][0]
        assert s["precio_congelado"] is False

    def test_cambiar_de_plan_cuesta_el_precio_nuevo(self):
        for s in self._salidas():
            if s["tipo"] == "cambiar":
                assert s["precio"] == PLAN_CATALOG[s["plan"]]["precio"]
                assert s["precio_congelado"] is False

    def test_al_que_viene_de_un_plan_viejo_se_le_ofrece_seguir_en_el_suyo(self):
        """Desde el 20-08 (Francisco): todos los legacy son renovables por los suyos.
        Sigue eligiendo tambien entre los nuevos, pero «seguir igual» esta."""
        s = self._salidas(plan="reto12en12_gold", precio_alta=1500.0)
        renovar = [x for x in s if x["tipo"] == "renovar"]
        assert len(renovar) == 1 and renovar[0]["por_checkout"] is True
        assert {x["plan"] for x in s if x["tipo"] == "cambiar"} == {"nivel1", "nivel2", "nivel3", "elm"}

    def test_subir_se_ofrece_antes_que_bajar(self):
        cambios = [s for s in self._salidas(plan="nivel1") if s["tipo"] == "cambiar"]
        precios = [c["precio"] for c in cambios]
        assert precios == sorted(precios, reverse=True)

    def test_al_del_nivel_3_no_se_le_ofrece_subir_a_ninguna_parte(self):
        cambios = [s for s in self._salidas(plan="nivel3") if s["tipo"] == "cambiar"]
        assert all(c["precio"] < 1497 for c in cambios)


class TestLaPantallaEntera:
    def _montar(self, p=None):
        p = p or perfil()
        return montar_renovacion(
            perfil=p, catalogo=PLAN_CATALOG,
            opciones_catalogo=opciones_de_renovacion(p.get("plan")),
            resumen=resumen_del_ciclo(
                reporte_primero={"weight": 88.0, "photos": ["a"]},
                reporte_ultimo={"weight": 81.0, "photos": ["b"]},
                perfil=p, dias_dieta=70, dias_totales=84, ajustes_de_macros=3),
            ahora=AHORA)

    def test_trae_el_ciclo_el_resumen_y_las_salidas(self):
        r = self._montar()
        assert r["ciclo"]["toca_renovar"] is True
        assert r["resumen"]["peso"]["cambio_pct"] == -8.0
        assert len(r["salidas"]) >= 3

    def test_avisa_de_que_si_no_hace_nada_se_renueva(self):
        """No es un paywall: Stripe cobra solo el dia que acaba el ciclo."""
        assert self._montar()["renueva_solo"] is True

    def test_al_que_viene_de_un_plan_viejo_ya_no_hay_motivo_que_explicar(self):
        # Con «seguir igual» disponible (20-08), el texto de «tu plan ya no se ofrece»
        # sobra: seguir en el suyo es justo lo que ahora puede hacer.
        r = self._montar(perfil(plan="gold", precio_alta=450.0))
        assert r["motivo_cambio"] is None


# ---------------------------------------------------------------------------
# «AJUSTES 176»
#
# Jesus, 12-08-2026: la tarjeta de la renovacion le decia que le habian ajustado los macros
# 176 veces, en una tarjeta que resume DOCE SEMANAS.
#
# La fecha buena de un ajuste es `effective_date`, no `created_at`: en las 3.446 filas que
# vinieron de Calma, `created_at` es el dia en que se importaron -- todas el 05-08-2026 --
# y `effective_date` es el dia en que el ajuste entro en vigor. Sus 176 filas son 176 fechas
# de verdad repartidas entre 2022 y 2029; por `created_at`, una sola. Los dos numeros que
# salen de ahi, 176 y 1, son igual de falsos.
#
# Contado como toca -- dentro del ciclo y hasta hoy -- son 11.
# ---------------------------------------------------------------------------
from datetime import date  # noqa: E402

from routes.billing import dias_distintos  # noqa: E402


def test_las_reescrituras_del_mismo_dia_son_un_ajuste():
    assert dias_distintos(["2026-07-04T10:00:00Z"] * 176) == 1


def test_dias_distintos_cuentan_por_separado():
    marcas = ["2026-07-04T10:00:00Z", "2026-07-04T18:30:00Z", "2026-08-01T09:00:00Z"]
    assert dias_distintos(marcas) == 2


def test_solo_cuenta_lo_del_ciclo():
    """Lo de antes de arrancar el ciclo no es de este ciclo."""
    marcas = ["2026-05-01T10:00:00Z", "2026-07-10T10:00:00Z", "2026-08-01T10:00:00Z"]
    assert dias_distintos(marcas, desde=date(2026, 7, 4)) == 2


def test_un_ajuste_que_aun_no_ha_empezado_no_se_ha_hecho():
    """Hay ajustes programados con fecha por delante; los de una cuenta llegan a 2029."""
    marcas = ["2026-07-10", "2026-08-01", "2029-01-08"]
    assert dias_distintos(marcas, desde=date(2026, 7, 4), hasta=date(2026, 8, 12)) == 2


def test_el_caso_de_jesus():
    """176 filas, una sola fecha de importacion, 176 fechas de vigencia entre 2022 y 2029.
    Dentro de su ciclo (04-07) y hasta hoy (12-08) quedan las de julio y agosto."""
    reales = ([f"2022-{m:02d}-06" for m in range(1, 13)]      # historia vieja
              + ["2026-07-10", "2026-07-24", "2026-08-07"]     # las de su ciclo
              + ["2029-01-08"])                                # una programada
    assert dias_distintos(reales) == 16
    assert dias_distintos(reales, desde=date(2026, 7, 4), hasta=date(2026, 8, 12)) == 3


def test_una_marca_ilegible_no_cuenta_ni_rompe():
    assert dias_distintos([None, "", "vete a saber", "2026-07-10T10:00:00Z"]) == 1


def test_sin_historial_son_cero():
    assert dias_distintos([]) == 0
