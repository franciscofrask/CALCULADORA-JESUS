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
    def _salidas(self, plan="nivel2", precio_alta=897.0):
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
        s = [x for x in self._salidas(precio_alta=897.0) if x["tipo"] == "renovar"][0]
        assert s["precio_congelado"] is False

    def test_cambiar_de_plan_cuesta_el_precio_nuevo(self):
        for s in self._salidas():
            if s["tipo"] == "cambiar":
                assert s["precio"] == PLAN_CATALOG[s["plan"]]["precio"]
                assert s["precio_congelado"] is False

    def test_al_que_viene_de_un_plan_viejo_no_se_le_ofrece_seguir(self):
        """Su plan ya no se vende: al renovar elige entre los nuevos."""
        s = self._salidas(plan="reto12en12_gold", precio_alta=1500.0)
        assert "renovar" not in [x["tipo"] for x in s]
        assert {x["plan"] for x in s if x["tipo"] == "cambiar"} == {"nivel1", "nivel2", "nivel3"}

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

    def test_al_que_viene_de_un_plan_viejo_se_le_explica_por_que(self):
        r = self._montar(perfil(plan="gold", precio_alta=450.0))
        assert r["motivo_cambio"]
