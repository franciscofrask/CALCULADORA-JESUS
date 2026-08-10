# -*- coding: utf-8 -*-
"""
Punto 6.2: la pantalla «Mis macros» del cliente y lo que su endpoint NO puede contar.

El historial de macros lo servia solo el panel del entrenador, y esas entradas llevan cosas
escritas para el y no para el cliente: el `criterio` (la nota interna del ajuste), la
`evaluacion` de como salio la fase -- con la casilla de de quien fue la culpa -- y lo que
propuso la IA. Por eso la respuesta del cliente se construye campo a campo en vez de tapar lo
que sobra: si mañana se guarda un campo mas en `macro_history`, no se cuela solo.

Los dos filtros que se prueban aqui son los que se le vieron en pantalla al montarla:

  - «Importado de Calma» y «Cuestionario inicial» son notas que escribe la APP. Puestas bajo
    «lo que te dijo tu entrenador» se leen como un mensaje suyo, y no lo son. Van por texto y
    no solo por `origen` porque el origen se empezo a guardar el 05-08 y la inmensa mayoria de
    las entradas son anteriores.

  - Quien ve el historico lo decide el plan (TABLA 20): `personalizado` si, `sin_ajuste` no.
"""
import asyncio

import pytest

from routes.users import (
    NOTAS_QUE_ESCRIBE_LA_APP,
    _bloque_de_macros,
    _feedback_del_entrenador,
    get_mi_historial_de_macros,
)


def correr(coro):
    """No hay pytest-asyncio en el repo: se corre a mano, como en el resto de tests."""
    return asyncio.run(coro)


# ── Una base de datos de mentira, con lo justo que toca el endpoint ──────────────────────

class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *a, **kw):
        return self

    async def to_list(self, n):
        return self._docs[:n]


class _Coleccion:
    def __init__(self, docs=None, uno=None):
        self._docs = docs or []
        self._uno = uno

    def find(self, *a, **kw):
        return _Cursor(self._docs)

    async def find_one(self, *a, **kw):
        return self._uno


class FakeDB:
    def __init__(self, perfil, entradas=None, dieta_de_hoy=None):
        self.client_profiles = _Coleccion(uno=perfil)
        self.macro_history = _Coleccion(docs=entradas or [])
        self.diets = _Coleccion(uno=dieta_de_hoy)


def entrada(fecha, note=None, origen=None, **kw):
    return {
        "id": "e-" + fecha,
        "client_id": "c1",
        "effective_date": fecha,
        "training": {"protein": 180, "carbs": 60, "fat": 50},
        "peri": {"protein": 45, "carbs": 15},
        "rest": {"protein": 210, "carbs": 50, "fat": 60},
        "peso": 72.5,
        "note": note,
        "origen": origen,
        **kw,
    }


def pedir(monkeypatch, perfil, entradas=None, dieta_de_hoy=None):
    import routes.users as users

    monkeypatch.setattr(users, "db", FakeDB(perfil, entradas, dieta_de_hoy))
    return correr(get_mi_historial_de_macros(user={"id": "u1"}))


PERSONALIZADO = {"id": "c1", "user_id": "u1", "plan": "nivel2", "pesos": []}
SIN_AJUSTE = {**PERSONALIZADO, "plan": "mantenimiento"}


class TestLoQueNuncaSaleDeAqui:
    """Lo unico que de verdad no puede fallar: que no se le enseñe al cliente lo del coach."""

    def test_ni_el_criterio_ni_la_evaluacion_ni_la_ia(self, monkeypatch):
        e = entrada("2026-07-02", note="Bajamos hidratos",
                    criterio="viene de una fase larga y no responde",
                    evaluacion={"resultado": "mala", "causa": "el cliente no cumplio"},
                    sugerencia_propuesta={"entreno": {}}, correccion_coach={"hidratos": -20},
                    changed_by="Jesus Gallego")
        datos = pedir(monkeypatch, PERSONALIZADO, [e])

        campos = set(datos["entradas"][0])
        for prohibido in ("criterio", "evaluacion", "sugerencia_propuesta",
                          "correccion_coach", "origen", "changed_by"):
            assert prohibido not in campos, f"«{prohibido}» no es para el cliente"

    def test_y_solo_salen_los_campos_elegidos(self, monkeypatch):
        """Con lista blanca: si alguien añade un campo a `macro_history`, no viaja solo."""
        datos = pedir(monkeypatch, PERSONALIZADO, [entrada("2026-07-02", secreto="lo que sea")])
        assert set(datos["entradas"][0]) == {
            "id", "fecha", "peso", "entreno", "peri", "descanso", "cambios", "feedback"}


class TestElFeedbackEsLoQueTeDijoTuEntrenador:
    def test_la_nota_del_coach_si(self):
        assert _feedback_del_entrenador(
            entrada("2026-07-02", note="Sigue asi", origen="manual")) == "Sigue asi"

    @pytest.mark.parametrize("nota", sorted(NOTAS_QUE_ESCRIBE_LA_APP))
    def test_pero_las_que_escribe_la_app_no(self, nota):
        """«Importado de Calma» no es nada que Jesus le haya dicho a nadie."""
        assert _feedback_del_entrenador(entrada("2026-07-02", note=nota)) is None

    def test_ni_el_motivo_que_escribio_el_mismo(self):
        """Es SU «motivo del cambio»: devolverselo en boca de su entrenador seria mentir."""
        assert _feedback_del_entrenador(
            entrada("2026-07-02", note="lo subo yo", origen="cliente_calculadora")) is None

    def test_y_una_nota_vacia_no_es_un_mensaje(self):
        assert _feedback_del_entrenador(entrada("2026-07-02", note="   ")) is None


class TestQuienVeElHistorico:
    """TABLA 20 del documento."""

    def test_el_plan_personalizado_lo_ve(self, monkeypatch):
        datos = pedir(monkeypatch, PERSONALIZADO,
                      [entrada("2026-07-02"), entrada("2026-06-04")])
        assert datos["con_historico"] is True
        assert len(datos["entradas"]) == 2

    def test_el_plan_sin_ajuste_no(self, monkeypatch):
        datos = pedir(monkeypatch, SIN_AJUSTE, [entrada("2026-07-02"), entrada("2026-06-04")])
        assert datos["con_historico"] is False
        assert datos["entradas"] == []

    def test_pero_sus_macros_de_hoy_los_ve_igual(self, monkeypatch):
        """No tener historico de cambios no es no tener macros."""
        datos = pedir(monkeypatch, SIN_AJUSTE, [entrada("2026-07-02")])
        assert datos["vigente"]["entreno"] == {"proteina": 180, "hidratos": 60, "grasa": 50}


class TestLaTarjetaDeHoy:
    def test_el_vigente_es_el_primero(self, monkeypatch):
        """La lista llega ordenada de mas nuevo a mas viejo y ya filtrada hasta hoy."""
        datos = pedir(monkeypatch, PERSONALIZADO,
                      [entrada("2026-07-02"), entrada("2026-06-04")])
        assert datos["vigente"]["fecha"] == "2026-07-02"

    def test_dice_si_hoy_entrena_cuando_el_dia_esta_montado(self, monkeypatch):
        datos = pedir(monkeypatch, PERSONALIZADO, [entrada("2026-07-02")],
                      dieta_de_hoy={"tipo_dia": "descanso"})
        assert datos["tipo_dia_hoy"] == "descanso"

    def test_y_no_se_lo_inventa_cuando_no(self, monkeypatch):
        datos = pedir(monkeypatch, PERSONALIZADO, [entrada("2026-07-02")])
        assert datos["tipo_dia_hoy"] is None

    def test_sin_ningun_ajuste_no_hay_vigente(self, monkeypatch):
        datos = pedir(monkeypatch, PERSONALIZADO, [])
        assert datos["vigente"] is None and datos["entradas"] == []


class TestLaCurvaDePeso:
    def test_sale_de_la_serie_del_perfil(self, monkeypatch):
        perfil = {**PERSONALIZADO, "pesos": [
            {"fecha": "2026-05-07", "valor": 74.0}, {"fecha": "2026-06-04", "valor": 73.1}]}
        datos = pedir(monkeypatch, perfil, [])
        assert datos["evolucion_peso"] == [
            {"fecha": "2026-05-07", "peso": 74.0}, {"fecha": "2026-06-04", "peso": 73.1}]

    def test_y_recoge_los_pesajes_que_viajaron_con_un_ajuste(self, monkeypatch):
        """Los importados de Calma son de 2022 en adelante y no estan en la serie: sin esto
        la curva empieza el dia que estrenamos la serie y se pierde todo el recorrido."""
        perfil = {**PERSONALIZADO, "pesos": [{"fecha": "2026-06-04", "valor": 73.1}]}
        datos = pedir(monkeypatch, perfil, [entrada("2022-03-01", peso=88.0)])
        assert datos["evolucion_peso"][0] == {"fecha": "2022-03-01", "peso": 88.0}

    def test_pero_manda_la_serie_si_los_dos_hablan_del_mismo_dia(self, monkeypatch):
        perfil = {**PERSONALIZADO, "pesos": [{"fecha": "2026-07-02", "valor": 71.0}]}
        datos = pedir(monkeypatch, perfil, [entrada("2026-07-02", peso=99.0)])
        assert datos["evolucion_peso"] == [{"fecha": "2026-07-02", "peso": 71.0}]

    def test_y_un_pesaje_del_futuro_no_es_el_peso_de_nadie(self, monkeypatch):
        perfil = {**PERSONALIZADO, "pesos": [
            {"fecha": "2026-06-04", "valor": 73.1}, {"fecha": "2099-01-01", "valor": 118.0}]}
        datos = pedir(monkeypatch, perfil, [])
        assert [p["fecha"] for p in datos["evolucion_peso"]] == ["2026-06-04"]


class TestLosDosVocabulariosDeMacros:
    """En la base conviven `protein`/`carbs`/`fat` y `proteinas`/`hidratos`/`grasas` segun
    quien escribiera la entrada. La pantalla sale por uno solo."""

    def test_entiende_los_nombres_en_ingles(self):
        assert _bloque_de_macros({"protein": 180, "carbs": 60, "fat": 50}) == {
            "proteina": 180, "hidratos": 60, "grasa": 50}

    def test_y_los_de_las_entradas_viejas(self):
        assert _bloque_de_macros({"proteinas": 180, "hidratos": 60, "grasas": 50}) == {
            "proteina": 180, "hidratos": 60, "grasa": 50}

    def test_el_perientreno_no_lleva_grasa(self):
        assert _bloque_de_macros({"protein": 45, "carbs": 15}, con_grasa=False) == {
            "proteina": 45, "hidratos": 15}

    def test_un_bloque_que_no_esta_es_None_y_no_una_fila_de_guiones(self):
        assert _bloque_de_macros(None) is None
        assert _bloque_de_macros({}) is None
