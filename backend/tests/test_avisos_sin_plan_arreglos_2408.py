# -*- coding: utf-8 -*-
"""La otra mitad del fallo 18: el cliente SIN PLAN CONTRATADO (repaso del 24-08).

EL FALLO, reproducido antes de tocar nada:

  - En el navegador (dev, cuenta prueba.elm.2408@test.com a la que se le quito el plan):
    /dashboard/checkins acaba en /dashboard, sin formulario y sin decir nada. Es la misma
    pared, porque la app le apaga TODAS las capacidades al que no tiene plan: `myPlan` sale
    null en AuthContext y `can()` devuelve false para todo.
  - Y el aviso nacia igual. El candado que se puso para el fallo 18 solo preguntaba por las
    habilitaciones del plan, y al que no tiene plan el catalogo no le dice nada en contra:
    `cierre_del_dia_incluido({})` responde «lo lleva» (asi tiene que ser, ver models/user).
  - No es hipotetico: el 24-08 habia en produccion un «Cierra tu dia» vivo y sin leer de un
    perfil con `plan: None`, creado el 23-08.

EL ARREGLO esta en routes/notifications.py, dentro de `_datos_para_avisos`: el mismo dato
que ya miraba la casilla del plan (`plan_con_cierre_dia`) se pone en False cuando el
cliente no tiene plan que la app le reconozca. Los tres casos son los que mira la app, no
otros: sin codigo, con un codigo que el catalogo no conoce, o con un checkout de Stripe a
medias (`status: pendiente_pago` + `checkout_status: draft|created`).

Los perfiles antiguos de pago manual estan en pendiente_pago SIN checkout_status y NO
entran: la app tampoco los deja fuera.
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# El bucle es el de la bateria entera (tests/conftest.py): ver ahi por que.
from conftest import corre                                     # noqa: E402

AHORA = datetime.now(timezone.utc)


class _Coleccion:
    """Lo minimo de una coleccion de Mongo para que `_datos_para_avisos` corra en seco."""

    async def find_one(self, *a, **k):
        return None

    async def update_one(self, *a, **k):
        return None


class _Base:
    def __getattr__(self, nombre):
        col = _Coleccion()
        setattr(self, nombre, col)
        return col


def _llave(monkeypatch, perfil):
    """`plan_con_cierre_dia` que sale para ese perfil, con el catalogo de verdad."""
    import macros_por_fecha
    import routes.notifications as notif
    import routes.plans as plans

    async def _nada(*a, **k):
        return None

    async def _sin_overrides():
        return {}

    async def _ventanas(*a, **k):
        return None, []

    async def _lista(*a, **k):
        return []

    async def _cierres(*a, **k):
        return True, 0

    async def _dias(*a, **k):
        return 0

    monkeypatch.setattr(notif, "db", _Base())
    monkeypatch.setattr(plans, "_overrides_by_code", _sin_overrides)
    monkeypatch.setattr(macros_por_fecha, "ultima_vigente", _nada)
    monkeypatch.setattr(macros_por_fecha, "ultimo_cambio", _nada)
    monkeypatch.setattr(notif, "_ventanas_de_reporte", _ventanas)
    monkeypatch.setattr(notif, "_fotos_o_medidas_viejas", _lista)
    monkeypatch.setattr(notif, "_cierres_del_cliente", _cierres)
    monkeypatch.setattr(notif, "_dias_sin_entrar", _dias)
    datos = corre(notif._datos_para_avisos(dict(perfil), AHORA, marcar_entrada=False))
    return datos["plan_con_cierre_dia"]


BASE = {"id": "c1", "user_id": "u1", "status": "activo",
        "created_at": "2026-01-01T00:00:00+00:00"}


class TestElQueNoTienePlanNoRecibeElAviso:

    def test_sin_plan_no_nace(self, monkeypatch):
        """EL CASO DE PRODUCCION: `plan: None` y un «Cierra tu dia» vivo apuntando a una
        pantalla que la app le cierra."""
        assert _llave(monkeypatch, {**BASE, "plan": None}) is False

    def test_con_el_plan_en_blanco_tampoco(self, monkeypatch):
        assert _llave(monkeypatch, {**BASE, "plan": ""}) is False

    def test_un_plan_que_el_catalogo_no_conoce_tampoco(self, monkeypatch):
        """La app hace la misma busqueda (`planDelCatalogo`) y se queda sin capacidades."""
        assert _llave(monkeypatch, {**BASE, "plan": "plan_que_no_existe"}) is False

    def test_con_el_pago_a_medias_tampoco(self, monkeypatch):
        """Un checkout de Stripe empezado y nunca pagado no es un plan contratado: la app
        lo trata asi en todas partes (`planUnpaid` en AuthContext)."""
        assert _llave(monkeypatch, {**BASE, "plan": "nivel2",
                                    "status": "pendiente_pago",
                                    "checkout_status": "created"}) is False

    def test_el_pago_manual_de_toda_la_vida_si_lo_recibe(self, monkeypatch):
        """Los perfiles antiguos estan en pendiente_pago SIN checkout_status: la app no los
        deja fuera y aqui tampoco. Regresion del arreglo, no del fallo."""
        assert _llave(monkeypatch, {**BASE, "plan": "nivel2",
                                    "status": "pendiente_pago"}) is True

    def test_el_cliente_normal_lo_sigue_recibiendo(self, monkeypatch):
        """El candado no puede callar al 99%: los 21 planes llevan el cierre del dia."""
        for codigo in ("elm", "nivel1", "nivel2", "nivel3", "mantenimiento", "gold"):
            assert _llave(monkeypatch, {**BASE, "plan": codigo}) is True, codigo

    def test_el_caducado_lo_sigue_recibiendo(self, monkeypatch):
        """LA TENTACION ERA USAR `estado_de_acceso`, que esta en el mismo fichero y da «no
        activo» tambien al caducado. Al caducado la app SI le abre el cierre del dia
        (comprobado en el navegador con el perfil en `caducado`: la pantalla entra), asi
        que con ese criterio le habriamos quitado el aviso a gente que si puede cerrar."""
        assert _llave(monkeypatch, {**BASE, "plan": "elm", "status": "caducado"}) is True

    def test_el_plan_escrito_a_mano_se_resuelve_por_alias(self, monkeypatch):
        """`codigo_de_plan` resuelve mayusculas y alias igual que la app: un perfil migrado
        con el plan escrito «CalMa» tiene plan de verdad y su aviso tiene que salir."""
        assert _llave(monkeypatch, {**BASE, "plan": "CalMa"}) is True
