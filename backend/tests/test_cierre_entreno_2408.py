# -*- coding: utf-8 -*-
"""El cierre del 24-08 en rutina, entreno y suplementos.

Todo lo de aqui se prueba SIN backend: son las piezas de `routes/routines.py`, y lo que
toca base va con una base de mentira (al final del fichero). Lo que necesita el servidor
vivo (que el panel deje de pintar en rojo al que tiene su PDF) va en el repaso de
integracion, no aqui.
"""
import asyncio
import copy
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import routes.routines as rutinas                               # noqa: E402
from models.common import RoutineResponse                       # noqa: E402
from routes.routines import (                                   # noqa: E402
    _dias_limpios, _peticion_de_rutina_viva, _peticion_viva, _rutina_pintable, _series,
)

from datetime import date, timedelta                            # noqa: E402

# El bucle es el de la bateria entera (tests/conftest.py): ver ahi por que.
from conftest import corre  # noqa: E402


def _rutina_con(dias):
    """Una rutina como la que sirve GET /routines/current."""
    return {"id": "r1", "client_id": "c1", "days": dias, "created_at": "2026-08-24T09:00:00",
            "status": "active"}


class TestLasSeriesEnBlancoNoDejanSinRutina:
    """El entrenador escribe una plantilla en la biblioteca, borra el «3» de Series para
    reescribirlo y se le olvida. Guarda, se la asigna a un cliente y el panel dice
    «Activa». El cliente abre Mi rutina y lee «Sin rutina asignada»: GET /routines/current
    reventaba con un 500 porque `Exercise.sets` es un entero obligatorio, y la pantalla se
    tragaba el error. Nadie se entera hasta que el cliente pregunta.
    """

    def test_el_modelo_seguia_sin_admitir_el_blanco(self):
        # La causa, tal cual: si esto deja de fallar es que alguien aflojo el modelo y
        # estos tests ya no vigilan nada.
        with pytest.raises(Exception):
            RoutineResponse(**_rutina_con([
                {"day": "Lunes", "is_rest": False,
                 "exercises": [{"name": "Press banca", "sets": "", "reps": "10", "rest": "90s"}]},
            ]))

    def test_la_biblioteca_ya_no_guarda_el_blanco(self):
        dias = _dias_limpios([
            {"day": "Lunes", "exercises": [{"name": "Press banca", "sets": "", "reps": "10",
                                            "rest": "90s"}]},
        ])
        lunes = next(d for d in dias if d["day"] == "Lunes")
        assert lunes["exercises"][0]["sets"] == 1
        # Y lo guardado se puede pintar, que es de lo que iba todo esto.
        RoutineResponse(**_rutina_con(dias))

    def test_el_rango_del_generador_se_queda_con_el_primero(self):
        # «3-4» lo devuelve el modelo cuando le da por ahi: son 3 series, no una rutina
        # perdida.
        assert _series("3-4") == 3
        assert _series(" 4 ") == 4
        assert _series(None) == 1
        assert _series("") == 1
        assert _series(0) == 1
        assert _series(500) == 99

    def test_lo_que_se_guarda_para_un_cliente_se_puede_pintar(self):
        dias = _rutina_pintable([
            {"day": "Lunes", "is_rest": False, "exercises": [
                {"name": "Press banca", "sets": "3-4", "reps": "10-12", "rest": "90s"},
                {"name": "Aperturas", "sets": None},
            ]},
            {"day": "Martes", "is_rest": True, "exercises": []},
        ])
        RoutineResponse(**_rutina_con(dias))
        assert [e["sets"] for e in dias[0]["exercises"]] == [3, 1]
        # Al que le faltaban reps y descanso se le ponen vacios, no se le inventan.
        assert dias[0]["exercises"][1]["reps"] == ""

    def test_un_ejercicio_sin_nombre_no_deja_al_cliente_sin_rutina(self):
        # `Exercise` pide CUATRO campos y el saneado solo garantizaba tres: el ejercicio
        # que la IA devuelve sin `name` reventaba GET /current igual que el de las series.
        dias = _rutina_pintable([
            {"day": "Lunes", "is_rest": False, "exercises": [
                {"sets": 4, "reps": "10", "rest": "90s"},
                {"name": "Press banca", "sets": 4, "reps": "10", "rest": "90s"},
            ]},
        ])
        RoutineResponse(**_rutina_con(dias))
        assert [e["name"] for e in dias[0]["exercises"]] == ["Press banca"]

    def test_un_dia_sin_nombre_se_cae_el_dia_y_no_la_rutina(self):
        # `RoutineDay.day` tambien es obligatorio. Un dia sin nombre no se puede ni pintar
        # ni colocar en la tira de la semana, asi que se cae el dia y el resto se salva.
        dias = _rutina_pintable([
            {"is_rest": False, "exercises": [{"name": "Remo", "sets": 3}]},
            {"day": "Martes", "is_rest": True, "exercises": []},
        ])
        RoutineResponse(**_rutina_con(dias))
        assert [d["day"] for d in dias] == ["Martes"]

    def test_la_rutina_ya_guardada_se_arregla_al_leerla(self, monkeypatch):
        # LO QUE YA ESTABA GUARDADO. Sanear solo al escribir dejaba fuera las filas viejas:
        # el cliente leia «No hemos podido cargar tu rutina» con un «Volver a intentarlo»
        # que no podia funcionar nunca, porque el dato malo seguia ahi.
        rota = {"id": "r1", "client_id": "c1", "status": "active",
                "created_at": "2026-06-01T09:00:00",
                "days": [{"day": "Lunes", "is_rest": False,
                          "exercises": [{"name": "Press banca", "sets": "", "reps": "10",
                                         "rest": "90s"}]}]}
        monkeypatch.setattr(rutinas, "db", _Base(routines=_Rutinas(actual=rota)))
        salida = corre(rutinas.get_current_routine(ctx={"profile": {"id": "c1"}}))
        assert salida.days[0].exercises[0].sets == 1

    def test_una_rutina_vieja_mala_no_tumba_el_historial(self, monkeypatch):
        # /history trae tambien las `inactive`, que no sanea nadie, y viaja en el mismo
        # Promise.all que /current: una sola fila irrecuperable dejaba la pantalla entera en
        # el error aunque la rutina de hoy estuviera perfecta.
        buena = {"id": "r2", "client_id": "c1", "status": "active",
                 "created_at": "2026-08-01T09:00:00",
                 "days": [{"day": "Lunes", "is_rest": False,
                           "exercises": [{"name": "Remo", "sets": 4, "reps": "8", "rest": "90s"}]}]}
        irrecuperable = {"client_id": "c1", "status": "inactive", "days": []}  # sin id
        monkeypatch.setattr(rutinas, "db",
                            _Base(routines=_Rutinas(historial=[buena, irrecuperable])))
        salida = corre(rutinas.get_routine_history(ctx={"profile": {"id": "c1"}}))
        assert [r.id for r in salida] == ["r2"]

    def test_no_se_pierde_el_cardio_ni_el_video_por_el_camino(self):
        # Saneando de mas se perdian dos cosas que la pantalla del cliente si pinta.
        dias = _rutina_pintable([
            {"day": "Lunes", "is_rest": False, "cardio": {"type": "Cinta", "duration": "20 min"},
             "exercises": [{"name": "Press", "sets": 4, "reps": "10", "rest": "90s",
                            "video_url": "https://youtu.be/x"}]},
        ])
        assert dias[0]["cardio"]["type"] == "Cinta"
        assert dias[0]["exercises"][0]["video_url"] == "https://youtu.be/x"


class TestLaRutinaDelMesQueYaPidio:
    """El cliente de Mantenimiento pulsa «Quiero mi rutina · 57 €», paga, lee el mensaje y
    recarga la pantalla. Volvia a ver el boton como si no hubiera pasado nada, y a las 24
    horas la clave de idempotencia de Stripe ya no frenaba el segundo cargo. Ahora la
    peticion queda apuntada en su ficha y esto es lo que decide si sigue contando.
    """

    def test_la_de_hoy_cuenta(self):
        perfil = {"rutina_mes_pedida": {"fecha": "2026-08-24", "modalidad": "basica",
                                        "cobrado": True}}
        assert _peticion_de_rutina_viva(perfil, date(2026, 8, 24))

    def test_la_de_hace_un_mes_ya_no(self):
        # La rutina es DEL MES: pasado el plazo puede volver a pedirla, que si no el que no
        # llego a recibirla se quedaba sin forma de reclamarla desde la app.
        perfil = {"rutina_mes_pedida": {"fecha": "2026-07-01"}}
        assert _peticion_de_rutina_viva(perfil, date(2026, 8, 24)) is None

    def test_el_dia_29_todavia_cuenta_y_el_30_no(self):
        perfil = {"rutina_mes_pedida": {"fecha": "2026-08-01"}}
        assert _peticion_de_rutina_viva(perfil, date(2026, 8, 30))
        assert _peticion_de_rutina_viva(perfil, date(2026, 8, 31)) is None

    def test_quien_no_ha_pedido_nada_puede_pedirla(self):
        assert _peticion_de_rutina_viva({}, date(2026, 8, 24)) is None
        assert _peticion_de_rutina_viva(None, date(2026, 8, 24)) is None

    def test_una_fecha_rota_no_bloquea_la_compra(self):
        # Un dato viejo o a medias no puede dejar a nadie sin poder pedir su rutina.
        for basura in ("", "ayer", None, {}, "2026-13-45"):
            assert _peticion_de_rutina_viva({"rutina_mes_pedida": {"fecha": basura}},
                                            date(2026, 8, 24)) is None


class TestLaOtraPuertaDelCobro:
    """La rutina del mes se pide desde DOS sitios: esta pantalla y el «Si, basica» del
    reporte mensual (routes/reports.py), que cobra los 57 EUR y no escribe nada en la ficha.
    Mirando solo la ficha, el que la marco en su reporte el dia 1 abria Mi rutina el dia 5,
    veia el boton y pagaba otra vez: las claves de idempotencia de Stripe son distintas
    (`rutina_del_mes:pid:{report_id}` contra `...:None`) y no frenan ese segundo cargo.
    """

    HOY = date(2026, 8, 24)
    PERFIL = {"id": "c1"}

    def _pedida(self, monkeypatch, *reportes, perfil=None):
        monkeypatch.setattr(rutinas, "db", _Base(reports=_Reportes(*reportes)))
        return corre(_peticion_viva(perfil or self.PERFIL, self.HOY))

    def _reporte(self, dias, respuesta="basica", cliente="c1"):
        cuando = (self.HOY - timedelta(days=dias)).isoformat()
        return {"client_id": cliente, "created_at": f"{cuando}T10:00:00+00:00",
                "entreno": {"rutina_del_mes": respuesta}}

    def test_el_que_la_pidio_en_su_reporte_no_la_paga_dos_veces(self, monkeypatch):
        pedida = self._pedida(monkeypatch, self._reporte(4))
        assert pedida and pedida["modalidad"] == "basica"
        assert pedida["fecha"] == "2026-08-20"

    def test_el_reporte_del_mes_pasado_ya_no_frena(self, monkeypatch):
        # Mismo plazo que la peticion de la pantalla: la rutina es DEL MES y quien no llego
        # a recibirla tiene que poder volver a pedirla.
        assert self._pedida(monkeypatch, self._reporte(45)) is None

    def test_el_que_dijo_ahora_no_puede_comprarla(self, monkeypatch):
        assert self._pedida(monkeypatch, self._reporte(3, "ahora_no")) is None
        assert self._pedida(monkeypatch, self._reporte(3, "aplazar_una_semana")) is None

    def test_el_reporte_de_otro_cliente_no_le_bloquea(self, monkeypatch):
        assert self._pedida(monkeypatch, self._reporte(3, cliente="c9")) is None

    def test_un_reporte_del_futuro_no_le_deja_sin_rutina_para_siempre(self, monkeypatch):
        # Punto 22: hay reportes importados de Calma fechados en 2028. Sin el tope de
        # `hasta_hoy` uno de esos cumple el «de los ultimos 30 dias» todos los dias.
        de_calma = {"client_id": "c1", "created_at": "2028-03-01T10:00:00+00:00",
                    "entreno": {"rutina_del_mes": "basica"}}
        assert self._pedida(monkeypatch, de_calma) is None

    def test_lo_apuntado_en_su_ficha_manda_y_ni_se_pregunta_por_reportes(self, monkeypatch):
        perfil = {"id": "c1", "rutina_mes_pedida": {"fecha": "2026-08-24",
                                                    "modalidad": "avanzada",
                                                    "cobrado": False}}
        pedida = self._pedida(monkeypatch, perfil=perfil)
        assert pedida["modalidad"] == "avanzada" and pedida["cobrado"] is False


# ── Lo que toca base, con una base de mentira ────────────────────────────────

class _Cursor:
    def __init__(self, docs):
        self.docs = list(docs)

    def sort(self, *a, **k):
        return self

    async def to_list(self, cuantos):
        return self.docs[:cuantos]


class _Rutinas:
    """Lo justo de db.routines. Devuelve copias, como Mongo: el saneado al leer toca el
    documento que le dan y no puede quedarse escrito en el de al lado."""

    def __init__(self, actual=None, historial=()):
        self.actual, self.historial = actual, list(historial)

    async def find_one(self, *a, **k):
        return copy.deepcopy(self.actual)

    def find(self, *a, **k):
        return _Cursor(copy.deepcopy(self.historial))


class _Reportes:
    """Lo justo de db.reports para este candado: el cliente, la respuesta del bloque de
    entreno y la ventana de fechas. Se filtra de verdad para que el test vigile el filtro
    y no solo la respuesta."""

    def __init__(self, *docs):
        self.docs = list(docs)

    async def find_one(self, filtro, proyeccion=None, sort=None):
        valen = [d for d in self.docs if self._cuadra(d, filtro)]
        valen.sort(key=lambda d: d.get("created_at") or "", reverse=True)
        return valen[0] if valen else None

    @staticmethod
    def _cuadra(doc, filtro):
        if doc.get("client_id") != filtro.get("client_id"):
            return False
        cuales = (filtro.get("entreno.rutina_del_mes") or {}).get("$in")
        if cuales and (doc.get("entreno") or {}).get("rutina_del_mes") not in cuales:
            return False
        cuando = doc.get("created_at") or ""
        ventana = filtro.get("created_at") or {}
        if "$gte" in ventana and cuando < ventana["$gte"]:
            return False
        if "$lte" in ventana and cuando > ventana["$lte"]:
            return False
        return True


class _Base:
    def __init__(self, **colecciones):
        for nombre, col in colecciones.items():
            setattr(self, nombre, col)

    def __getattr__(self, nombre):        # cualquier otra coleccion, vacia
        col = _Reportes()
        setattr(self, nombre, col)
        return col
