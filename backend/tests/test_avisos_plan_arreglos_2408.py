# -*- coding: utf-8 -*-
"""El aviso del cierre del dia mira TAMBIEN la llave del plan (fallo 18 del repaso 24-08).

EL FALLO, tal cual se reprodujo antes de tocar nada: se apaga el cierre del dia para el
plan ELM desde el panel (db.plan_overrides -> habilitaciones.cierre_dia = False) y

  - la pantalla /dashboard/checkins deja de abrirse: `CapabilityRoute` devuelve al cliente
    al Inicio sin decirle nada (comprobado en el navegador con una cuenta de dev de ese
    plan: acaba en /dashboard y no hay formulario),
  - pero el aviso de las 20:00 «Cierra tu dia» seguia naciendo, porque la regla solo
    miraba el interruptor DEL CLIENTE (`profile.avisos.cierre_dia`) y nadie le pasaba la
    llave del plan. O sea: un aviso que lleva a una puerta cerrada, que es justo lo que la
    decision D-D del 24-08 vino a matar (habia 16 avisos asi vivos en produccion, cuatro
    de ellos al mismo cliente).

Lo mismo valia para los otros tres avisos que llevan a esa pantalla: los dos del peso del
Premium y la condicionada de «llevas 5 dias sin apuntar nada». Van todos por el mismo
candado: `plan_con_cierre_dia`, que se calcula en routes/notifications.py -- que es quien
puede leer la base -- y se le pasa a las reglas, como ya se hacia con `rutina_visible`,
`con_ajuste` o `es_premium`.

Hoy los 21 planes llevan `cierre_dia`, asi que nada de esto le quita un aviso a nadie: es
para el dia que alguien lo apague desde el panel.
"""
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.avisos_cliente import (                              # noqa: E402
    avisos_condicionados, avisos_de_calendario_doc)

# El bucle es el de la bateria entera (tests/conftest.py): ver ahi por que.
from conftest import corre                                     # noqa: E402

MADRID = ZoneInfo("Europe/Madrid")
AHORA = datetime.now(timezone.utc)


def _es(a, m, d, h=0, mi=0):
    return datetime(a, m, d, h, mi, tzinfo=MADRID)


def _familias(avisos):
    return [a.get("familia") for a in avisos]


NOCHE = _es(2026, 8, 6, 21)          # jueves a las 21:00, sin cerrar el dia
MIERCOLES = _es(2026, 8, 5, 9)       # los dos del peso del Premium
JUEVES = _es(2026, 8, 6, 9)


# ── La regla: el aviso de las 20:00 ──────────────────────────────────────────

class TestCierraTuDiaMiraElPlan:

    def test_con_el_plan_apagado_no_nace(self):
        """EL CASO DEL FALLO. Antes salia igual: la regla no sabia nada del plan."""
        assert avisos_de_calendario_doc(ahora_es=NOCHE, cerro_hoy=False,
                                        plan_con_cierre_dia=False) == []

    def test_con_el_plan_encendido_nace_como_siempre(self):
        """El candado no puede callar al 99% de la gente: los 21 planes lo llevan."""
        avisos = avisos_de_calendario_doc(ahora_es=NOCHE, cerro_hoy=False,
                                          plan_con_cierre_dia=True)
        assert _familias(avisos) == ["cierra_dia"]

    def test_el_defecto_es_que_el_plan_lo_lleva(self):
        """Como `cierre_del_dia_incluido`: sin campo escrito, es que si. Al reves habria
        apagado el aviso de todo el mundo, que es peor que el fallo que se arregla."""
        assert _familias(avisos_de_calendario_doc(ahora_es=NOCHE, cerro_hoy=False)) == ["cierra_dia"]

    def test_el_interruptor_del_cliente_sigue_mandando(self):
        """Son dos candados distintos y los dos siguen valiendo: lo que el cliente QUIERE
        y lo que su plan LE ABRE. Regresion del arreglo, no del fallo."""
        assert avisos_de_calendario_doc(ahora_es=NOCHE, cerro_hoy=False,
                                        quiere_cierre_dia=False,
                                        plan_con_cierre_dia=True) == []

    def test_con_el_dia_cerrado_tampoco_cambia_nada(self):
        assert avisos_de_calendario_doc(ahora_es=NOCHE, cerro_hoy=True,
                                        plan_con_cierre_dia=True) == []


# ── Ningun aviso puede llevar a una pantalla que el plan no abre ─────────────

class TestNingunAvisoContraLaPared:
    """La regla entera, no solo el de las 20:00: `/dashboard/checkins` es la pantalla que
    cierra `CapabilityRoute`, asi que ningun aviso puede apuntar ahi si el plan la tiene
    apagada. Se barre la semana entera para que el dia que alguien añada un aviso nuevo con
    ese enlace, esta prueba se entere."""

    def _todos(self, **kw):
        fuera = []
        for dia in range(3, 10):                     # una semana completa de agosto de 2026
            for hora in (8, 9, 10, 12, 20, 21, 23):
                fuera += avisos_de_calendario_doc(
                    ahora_es=_es(2026, 8, dia, hora), cliente_id="c1", cerro_hoy=False,
                    es_premium=True, con_correo_de_novedades=True, **kw)
        fuera += avisos_condicionados(ahora=AHORA, dias_sin_cerrar=9, **kw)
        return fuera

    def test_con_el_plan_apagado_ninguno_apunta_al_cierre(self):
        enlaces = [a["link"] for a in self._todos(plan_con_cierre_dia=False)]
        assert "/dashboard/checkins" not in enlaces

    def test_y_con_el_plan_encendido_si_los_hay(self):
        """Si no, la prueba de arriba pasaria sola con la lista vacia."""
        enlaces = [a["link"] for a in self._todos(plan_con_cierre_dia=True)]
        assert enlaces.count("/dashboard/checkins") >= 3   # cierra_dia + los dos del peso

    def test_lo_demas_sigue_saliendo_igual(self):
        """El candado es solo para los del cierre: el correo del viernes, el arranque y los
        reportes no tienen nada que ver con esa pantalla y no se pueden llevar por delante."""
        sin = [a["familia"] for a in self._todos(plan_con_cierre_dia=False)]
        assert "correo_viernes" in sin


# ── La condicionada de los cinco dias ────────────────────────────────────────

class TestLosCincoDiasSinApuntar:
    """«Llevas 5 dias sin apuntar nada» tambien manda a /dashboard/checkins. Si el plan no
    abre esa pantalla, el cliente no puede cerrar el dia -- por eso lleva cinco sin
    hacerlo -- y regañarle por ello es el mismo fallo por la otra puerta."""

    def test_con_el_plan_apagado_no_se_le_reclama(self):
        assert avisos_condicionados(ahora=AHORA, dias_sin_cerrar=9,
                                    plan_con_cierre_dia=False) == []

    def test_con_el_plan_encendido_se_le_reclama(self):
        avisos = avisos_condicionados(ahora=AHORA, dias_sin_cerrar=9,
                                      plan_con_cierre_dia=True)
        assert _familias(avisos) == ["sin_cerrar"]

    def test_el_defecto_tambien_es_que_si(self):
        assert _familias(avisos_condicionados(ahora=AHORA, dias_sin_cerrar=9)) == ["sin_cerrar"]


# ── El dato sale de la base y llega a la regla ───────────────────────────────

class _Coleccion:
    """Lo minimo de una coleccion de Mongo: devuelve siempre el mismo documento."""

    def __init__(self, doc=None):
        self.doc = doc

    async def find_one(self, *a, **k):
        return self.doc

    async def update_one(self, *a, **k):
        return None


class _Base:
    def __getattr__(self, nombre):
        col = _Coleccion()
        setattr(self, nombre, col)
        return col


class TestElDatoSaleDelCatalogo:
    """`_datos_para_avisos` es quien puede leer la base, asi que la llave se calcula ahi.
    Y del catalogo MEZCLADO con `db.plan_overrides`, que es donde escribe el panel: leyendo
    el del codigo, apagar el cierre desde el panel cambiaria la puerta y no el aviso, y
    volveriamos a tener avisos contra una pared."""

    PERFIL = {"id": "c1", "user_id": "u1", "plan": "elm", "status": "activo",
              "created_at": "2026-01-01T00:00:00+00:00"}

    def _llave(self, monkeypatch, habilitaciones):
        import macros_por_fecha
        import routes.notifications as notif
        import routes.plans as plans

        async def _nada(*a, **k):
            return None

        async def _overrides():
            return {"elm": {"habilitaciones": habilitaciones}} if habilitaciones is not None else {}

        async def _ventanas(*a, **k):
            return None, []

        async def _lista(*a, **k):
            return []

        async def _cierres(*a, **k):
            return True, 0

        async def _dias(*a, **k):
            return 0

        monkeypatch.setattr(notif, "db", _Base())
        monkeypatch.setattr(plans, "_overrides_by_code", _overrides)
        monkeypatch.setattr(macros_por_fecha, "ultima_vigente", _nada)
        monkeypatch.setattr(macros_por_fecha, "ultimo_cambio", _nada)
        monkeypatch.setattr(notif, "_ventanas_de_reporte", _ventanas)
        monkeypatch.setattr(notif, "_fotos_o_medidas_viejas", _lista)
        monkeypatch.setattr(notif, "_cierres_del_cliente", _cierres)
        monkeypatch.setattr(notif, "_dias_sin_entrar", _dias)
        datos = corre(notif._datos_para_avisos(dict(self.PERFIL), AHORA,
                                               marcar_entrada=False))
        return datos["plan_con_cierre_dia"]

    def test_el_panel_lo_apaga_y_el_aviso_se_entera(self, monkeypatch):
        assert self._llave(monkeypatch, {"cierre_dia": False}) is False

    def test_sin_tocar_nada_el_plan_lo_lleva(self, monkeypatch):
        assert self._llave(monkeypatch, None) is True

    def test_un_override_de_otra_cosa_no_lo_apaga(self, monkeypatch):
        """Las habilitaciones se mezclan clave a clave: quien edito el nombre del plan no
        queria dejar a sus clientes sin cierre del dia."""
        assert self._llave(monkeypatch, {"rutina": "ninguna"}) is True
