# -*- coding: utf-8 -*-
"""El cierre del 24-08 por el lado de la renovacion y el fin de ciclo.

Cada bloque empieza por lo que le pasaba a una persona de verdad, que es lo que hay que
impedir que vuelva. Todos son PUROS: no hablan con el backend ni con Mongo (las dos
funciones que si escriben se prueban contra una base de mentira), asi que se pueden pasar
con la app apagada.

Ejecutar:
    cd backend && venv/Scripts/python.exe -m pytest tests/test_cierre_renovacion_2408.py -q
"""
import asyncio
import os
from datetime import datetime, timedelta, timezone

from core.renovacion import estado_del_ciclo, inicio_del_ciclo

# El bucle es el de la bateria entera (tests/conftest.py): ver ahi por que.
from conftest import corre  # noqa: E402


def dentro(dias):
    return datetime.now(timezone.utc) + timedelta(days=dias)


def atras(dias):
    return datetime.now(timezone.utc) - timedelta(days=dias)


# =====================================================================================
# 1 · «Llevo tres semanas caducado y la pantalla me dice que voy por la semana 4»
# =====================================================================================
# La cabecera de /renovacion miraba `fin_de_ciclo`, un campo que solo escribe la rama de
# suscripcion de routes/billing.py -- muerta desde que todo el catalogo es de pago unico.
# Sin fecha de fin no habia `ya_vencido`, asi que al caducado se le pintaba «Vas por la
# semana N» con una semana que ademas da la vuelta sola (se cuenta en modulo), y se le
# seguia ofreciendo el «si renuevas antes de que acabe, no pierdes ni una semana».

def test_el_ciclo_terminado_se_dice_terminado():
    perfil = {"plan": "nivel2", "created_at": atras(105).isoformat(),
              "cycle_start": atras(105).isoformat(),
              "current_period_end": atras(21).isoformat()}
    estado = estado_del_ciclo(perfil)
    assert estado["conocido"], "con fecha de fin guardada la pantalla tiene que saberla"
    assert estado["ya_vencido"], (
        "al caducado se le sigue diciendo «vas por la semana N» y se le ofrece renovar "
        "antes de que acabe un ciclo que acabo hace tres semanas")
    assert estado["dias_restantes"] < 0


def test_el_fin_de_ciclo_de_toda_la_vida_sigue_valiendo_de_respaldo():
    """El modo pruebas escribe las dos fechas: la vieja no puede dejar de leerse."""
    perfil = {"plan": "nivel2", "created_at": atras(90).isoformat(),
              "fin_de_ciclo": dentro(5).isoformat()}
    estado = estado_del_ciclo(perfil)
    assert estado["conocido"] and estado["dias_restantes"] == 5
    assert estado["toca_renovar"] and not estado["ya_vencido"]


def test_una_fecha_heredada_de_calma_no_es_un_fin_de_ciclo():
    """«Gold · 1/1/2026 a 1/2/2030»: el mismo candado que Mi perfil (P50 del doc 23-08).

    Sin el, al empezar a leer `current_period_end` la pantalla saludaria a los importados
    con «Te quedan 1.257 días».
    """
    perfil = {"plan": "nivel2", "created_at": atras(400).isoformat(),
              "current_period_end": dentro(1257).isoformat()}
    assert estado_del_ciclo(perfil)["conocido"] is False


def test_sin_ninguna_fecha_no_se_inventa_el_final():
    """Los de antes del calendario de arranque: se sabe la semana, no el dia."""
    perfil = {"plan": "nivel2", "created_at": atras(70).isoformat()}
    estado = estado_del_ciclo(perfil)
    assert estado["conocido"] is False and estado["dias_restantes"] is None


def test_los_dias_que_le_quedan_se_cuentan_en_hora_de_espana():
    """A las 01:00 de Madrid la cabecera contaba un dia de mas y no daba por vencido un
    ciclo que habia acabado ayer. La media pantalla que se quedo en UTC (24-08)."""
    # 23:00 UTC del 24 son las 01:00 del 25 en Madrid (en agosto, UTC+2).
    ahora = datetime(2026, 8, 24, 23, 0, tzinfo=timezone.utc)
    acaba_hoy = {"plan": "nivel2", "created_at": atras(70).isoformat(),
                 "current_period_end": datetime(2026, 8, 25, 10, 0, tzinfo=timezone.utc).isoformat()}
    assert estado_del_ciclo(acaba_hoy, ahora)["dias_restantes"] == 0, (
        "en UTC todavia es dia 24 y se le promete un dia que ya no tiene")
    acabo_ayer = {"plan": "nivel2", "created_at": atras(70).isoformat(),
                  "current_period_end": datetime(2026, 8, 24, 20, 0, tzinfo=timezone.utc).isoformat()}
    assert estado_del_ciclo(acabo_ayer, ahora)["ya_vencido"], (
        "su ciclo acabo ayer para el y la pantalla le sigue diciendo «vas por la semana N»")


def _renovar_de(plan):
    from core.renovacion import salidas
    from models.user import PLAN_CATALOG, opciones_de_renovacion
    ss = salidas(plan_actual=plan, opciones_catalogo=opciones_de_renovacion(plan, PLAN_CATALOG),
                 catalogo=PLAN_CATALOG, precio_alta=None)
    return next((s for s in ss if s["tipo"] == "renovar"), None)


def test_al_del_catalogo_no_se_le_dice_que_su_plan_ya_no_se_vende():
    """La pantalla elegia el texto con `por_checkout`, y desde el 24-08 ese se enciende
    tambien para los planes que se venden: al de nivel2 le salia «tu plan ya no se vende,
    pero puedes seguir en el»."""
    catalogo = _renovar_de("nivel2")
    assert catalogo and catalogo["por_checkout"] and not catalogo["renovacion_legacy"]
    antiguo = _renovar_de("reto12en12")
    assert antiguo and antiguo["renovacion_legacy"], \
        "al del plan retirado hay que decirle que la renovacion la confirma el"


# =====================================================================================
# 2 · «Llevo dos años con vosotros y me dice 45 de 730 dias con el dia cuadrado»
# =====================================================================================
# La tarjeta «Constancia» y el contador de ajustes se median desde su fecha de alta, no
# desde que empezo el ciclo: es el «AJUSTES 176» de Jesus entrando por la otra puerta.

def test_la_constancia_se_mide_desde_que_empezo_este_ciclo():
    hoy = datetime.now(timezone.utc).date()
    perfil = {"created_at": atras(730).isoformat(),
              "current_period_start": atras(20).isoformat()}
    assert inicio_del_ciclo(perfil, hoy) == atras(20).date(), (
        "el resumen del ciclo cuenta desde que el cliente se registro: a uno de dos años "
        "le sale «45 de 730 dias» y los ajustes de toda su vida como si fueran de ahora")


def test_el_que_renovo_antes_de_tiempo_no_mide_un_ciclo_que_no_ha_empezado():
    """Encadenar deja `current_period_start` en el futuro: el ciclo que vive es el de antes."""
    hoy = datetime.now(timezone.utc).date()
    perfil = {"created_at": atras(400).isoformat(),
              "current_period_start": dentro(6).isoformat(), "billing_cycle_days": 84}
    assert inicio_del_ciclo(perfil, hoy) == (dentro(6) - timedelta(days=84)).date(), (
        "al que renueva una semana antes se le resume un ciclo que aun no ha empezado: "
        "«0 de 1 dias con el dia cuadrado»")


def test_sin_fecha_de_ciclo_se_cae_a_lo_que_haya():
    hoy = datetime.now(timezone.utc).date()
    assert inicio_del_ciclo({"created_at": atras(30).isoformat()}, hoy) == atras(30).date()
    assert inicio_del_ciclo({"arranque_lunes": atras(14).isoformat(),
                             "created_at": atras(300).isoformat()}, hoy) == atras(14).date()
    assert inicio_del_ciclo({}, hoy) is None


def test_el_que_nunca_pago_por_stripe_tambien_mide_el_ciclo_de_ahora():
    """El respaldo era el ancla ORIGINAL, no el arranque del ciclo vivo.

    `current_period_start` solo lo escribe el pago por Stripe; al que viene de Calma o del
    alta manual le quedaba `cycle_start`/`created_at` crudo, o sea su primer dia. La misma
    pantalla decia «Vas por la semana 9» arriba y «X de 730 dias con el dia cuadrado»
    debajo, y los ajustes de toda su vida contados como de este ciclo.
    """
    from core.cycle import compute_cycle

    hoy = datetime.now(timezone.utc).date()
    perfil = {"plan": "nivel2", "cycle_start": atras(730).isoformat(),
              "created_at": atras(730).isoformat()}
    d0 = inicio_del_ciclo(perfil, hoy)
    assert 0 <= (hoy - d0).days < 84, (
        f"el resumen arranca hace {(hoy - d0).days} dias: es su fecha de alta, no la de "
        "este ciclo")
    # Y la cuenta es LA MISMA que la de la cabecera: si no, las dos frases de la pantalla
    # se contradicen otra vez, solo que con numeros distintos.
    ciclo = compute_cycle(perfil)
    assert (hoy - d0).days // 7 == ciclo["week"] - 1

    # Los importados de Calma traen de ancla el tramo entero de membresia («Gold ·
    # 1/1/2026 a 1/2/2030»): mismo fallo, otro numero.
    calma = {"plan": "nivel2", "cycle_start": atras(235).isoformat()}
    assert (hoy - inicio_del_ciclo(calma, hoy)).days < 84


def test_el_caducado_hace_meses_no_resume_los_meses_que_lleva_fuera():
    """El plan mensual y el que dejo de pagar: el ciclo dura lo que dura.

    Con `current_period_start` de hace nueve meses la ventana llegaba hasta hoy y salia
    «X de 270 dias». La ventana la cierra `routes/billing` en d0 + la duracion del plan,
    que es este dato.
    """
    from core.renovacion import dias_de_ciclo

    assert dias_de_ciclo({"plan": "nivel2"}) == 84
    # Mensual (Mantenimiento): el catalogo no dice semanas, manda lo que se apunto al cobrar.
    assert dias_de_ciclo({"plan": "mantenimiento", "billing_cycle_days": 30}) == 30
    assert dias_de_ciclo({}) == 84


# =====================================================================================
# 3 · «Renove mi plan de siempre y a la vez siguiente me dicen que no saben mi precio»
# =====================================================================================
# El precio «se congela mientras el cliente no se de de baja». El checkout lo escribia con
# el de catalogo, y en los planes antiguos el catalogo pone 0,00 EUR (su importe vive en la
# hoja de control de pagos). Resultado: la primera renovacion se cobraba bien -- va con el
# precio congelado y en linea -- y la ficha quedaba sin el, asi que la siguiente moria en
# «No sabemos tu precio de renovación» o, en los que si tienen tarifa, le cobraba de mas.

class _Coleccion:
    """Lo justo de una coleccion de Mongo: buscar por igualdad y aplicar un $set.

    Con esto los dos caminos que ESCRIBEN se prueban sin base de datos, que es lo que
    permite pasar este fichero con la app apagada y sin pisar a nadie.
    """

    def __init__(self, docs=None):
        self.docs = docs or []

    @staticmethod
    def _casa(doc, filtro):
        return all(doc.get(k) == v for k, v in filtro.items())

    async def find_one(self, filtro, proyeccion=None):
        for d in self.docs:
            if self._casa(d, filtro):
                return dict(d)
        return None

    async def update_one(self, filtro, cambios, upsert=False):
        for d in self.docs:
            if self._casa(d, filtro):
                d.update(cambios.get("$set") or {})
                return
        if upsert:
            self.docs.append({**filtro, **(cambios.get("$set") or {})})

    async def insert_one(self, doc):
        self.docs.append(doc)


class _Base:
    def __init__(self, perfiles, usuarios=None):
        self.client_profiles = _Coleccion(perfiles)
        self.users = _Coleccion(usuarios if usuarios is not None else [{"id": "u1"}])


def _sesion_pagada(plan, perfil_id="p1", precio_congelado=None):
    metadata = {"plan": plan, "user_id": "u1", "profile_id": perfil_id}
    if precio_congelado is not None:
        # Lo que pone routes/billing.py cuando cobra un plan antiguo: el importe en linea
        # que se le ha cobrado de verdad, que no es el del catalogo.
        metadata["precio_congelado"] = f"{precio_congelado:.2f}"
    return {"payment_status": "paid", "client_reference_id": perfil_id, "customer": "cus_1",
            "created": int(datetime.now(timezone.utc).timestamp()), "metadata": metadata}


def test_renovar_su_plan_antiguo_no_le_borra_el_precio_de_siempre(monkeypatch):
    from core import stripe_billing

    perfil = {"id": "p1", "user_id": "u1", "plan": "reto12en12", "price": 87.0,
              "status": "activo", "billing_cycle_days": 84,
              "current_period_end": dentro(20).isoformat()}
    monkeypatch.setattr(stripe_billing, "db", _Base([perfil]))
    corre(stripe_billing.sync_profile_from_one_time_session(
        _sesion_pagada("reto12en12", precio_congelado=87.0)))
    assert perfil["price"] == 87.0, (
        "renovar le ha dejado la ficha con el precio de catalogo (0 EUR en los planes "
        "antiguos): la proxima renovacion le dira que no sabemos su precio")


def test_el_plan_del_catalogo_guarda_lo_que_cobra_la_tarifa(monkeypatch):
    """Al reves tambien: si se le cobra el Price de catalogo, eso es lo que se guarda.

    Guardarle un precio distinto del que le cobra Stripe seria la otra mitad del mismo
    fallo: la pantalla enseñaria un importe y la pasarela cobraria otro.
    """
    from core import stripe_billing
    from models.user import PLAN_TYPES

    perfil = {"id": "p1", "user_id": "u1", "plan": "nivel2", "price": 800.0,
              "status": "activo", "billing_cycle_days": 84}
    monkeypatch.setattr(stripe_billing, "db", _Base([perfil]))
    corre(stripe_billing.sync_profile_from_one_time_session(_sesion_pagada("nivel2")))
    assert perfil["price"] == PLAN_TYPES["nivel2"]["price"]


def test_renovar_antes_de_que_acabe_encadena_el_ciclo(monkeypatch):
    """«Que puedan renovar una semana antes y no pierdan una semana de trabajo»."""
    from core import stripe_billing

    fin = dentro(20).isoformat()
    perfil = {"id": "p1", "user_id": "u1", "plan": "nivel2", "price": 847.0,
              "status": "activo", "billing_cycle_days": 84, "current_period_end": fin,
              "access_until": fin}
    monkeypatch.setattr(stripe_billing, "db", _Base([perfil]))
    corre(stripe_billing.sync_profile_from_one_time_session(_sesion_pagada("nivel2")))
    assert perfil["current_period_start"] == fin, (
        "el ciclo nuevo no arranca donde acaba el viejo: se le comen los dias que ya "
        "tenia pagados, justo lo contrario de lo que le promete el aviso")


def test_cambiar_de_plan_si_estrena_precio_y_ciclo(monkeypatch):
    """El arreglo del precio congelado no puede congelar tambien al que se cambia."""
    from core import stripe_billing
    from models.user import PLAN_TYPES

    perfil = {"id": "p1", "user_id": "u1", "plan": "nivel1", "price": 247.0,
              "status": "activo", "billing_cycle_days": 84,
              "current_period_end": dentro(20).isoformat()}
    monkeypatch.setattr(stripe_billing, "db", _Base([perfil]))
    corre(stripe_billing.sync_profile_from_one_time_session(_sesion_pagada("nivel2")))
    assert perfil["plan"] == "nivel2"
    assert perfil["price"] == PLAN_TYPES["nivel2"]["price"], \
        "se ha quedado pagando el precio del plan que ya no tiene"


def test_abrir_el_pago_de_su_plan_antiguo_tampoco_le_pisa_el_precio(monkeypatch):
    """El otro sitio que lo escribia: la preparacion del checkout, antes de pagar."""
    from core import stripe_billing

    perfil = {"id": "p1", "user_id": "u1", "plan": "reto12en12", "price": 87.0,
              "status": "pendiente_pago"}   # ya caducado: entra por el camino que escribe
    monkeypatch.setattr(stripe_billing, "db", _Base([perfil]))
    corre(stripe_billing.ensure_checkout_profile(
        {"id": "u1", "email": "cliente@ejemplo.com"}, "reto12en12", price_override=87.0))
    assert perfil["price"] == 87.0, \
        "abrir el checkout le ha borrado su precio congelado antes incluso de pagar"

    # Y que el endpoint se lo pasa de verdad: sin esto lo de arriba prueba un parametro
    # que no usa nadie. Es la misma comprobacion por fuente que test_circuitos_2408.
    aqui = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(aqui, "..", "routes", "billing.py"), encoding="utf-8") as f:
        fuente = f.read()
    assert "price_override=precio_congelado" in fuente, \
        "el checkout prepara la ficha sin el precio congelado y se lo borra"
    assert 'checkout_metadata["precio_congelado"]' in fuente, \
        "el precio cobrado no viaja con la sesion: al volver el pago se escribe el de tarifa"


# =====================================================================================
# 4 · «Pago la renovacion y sigo viendo que mi suscripcion ha terminado»
# =====================================================================================
# La pantalla mandaba a /dashboard?renovado=ok y ese parametro no lo lee nadie: sin
# webhook (o con el webhook lento) el cliente se quedaba con el dinero cobrado y la
# pantalla de caducado delante. Las otras tres vueltas de Stripe si sincronizan.

def _fuente_de_la_pantalla():
    aqui = os.path.dirname(os.path.abspath(__file__))
    ruta = os.path.join(aqui, "..", "..", "frontend", "src", "pages", "RenovacionPage.jsx")
    with open(ruta, encoding="utf-8") as f:
        return f.read()


def test_la_vuelta_del_pago_confirma_el_cobro():
    fuente = _fuente_de_la_pantalla()
    assert "/renovacion?renovado=ok" in fuente, \
        "la vuelta de Stripe va a una pantalla que no confirma el pago"
    assert "/billing/checkout-session/sync" in fuente, \
        "nadie sincroniza la sesion al volver: se depende solo del webhook"


def test_al_que_se_baja_a_mantenimiento_no_se_le_dice_que_estrena_ciclo():
    """Las tres salidas volvian con el mismo texto: «¡Pago confirmado! Tu ciclo nuevo ya
    esta en marcha» al que acaba de dejarlo es lo contrario de lo que ha hecho."""
    fuente = _fuente_de_la_pantalla()
    assert "salida=${salida.tipo}" in fuente, \
        "la vuelta no lleva que eligio, asi que solo puede confirmarse de una manera"
    assert "Ya estás en Mantenimiento" in fuente, \
        "al que se baja a Mantenimiento se le confirma un ciclo nuevo que no ha comprado"


def test_al_caducado_del_catalogo_se_le_sigue_diciendo_algo():
    """La mitad que faltaba del arreglo del texto (24-08).

    El aviso «tu plan no se renueva solo» pedia `!ciclo.ya_vencido`, y en cuanto
    `ya_vencido` empezo a funcionar el caducado del catalogo se quedo con «Tu ciclo ha
    terminado» y tres botones, sin una linea que le dijera que la renovacion la confirma
    el ahi mismo.
    """
    fuente = _fuente_de_la_pantalla()
    assert "!ciclo.ya_vencido" not in fuente, \
        "con el ciclo vencido no se entra en ningun bloque: se queda sin texto"
    assert "para volver a tenerlo, la renovación la confirmas tú aquí abajo." in fuente
    # Y al que aun no ha vencido se le sigue prometiendo el encadenado, que para el si vale.
    assert "no pierdes ni una semana" in fuente


# =====================================================================================
# 5 · «Miro el precio, cierro la ventana y la pantalla se olvida de que he caducado»
# =====================================================================================
# `ensure_checkout_profile` ponia las dos fechas del ciclo a None a todo el que no tuviera
# acceso vivo. El caducado que pulsa «Cambiar a...», ve el precio y cierra volvia a
# /renovacion sin `current_period_end` -- otra vez «Vas por la semana N» y otra vez el «si
# renuevas antes de que acabe» -- y sin `current_period_start`, con lo que «Constancia»
# volvia a contar desde su fecha de alta. O sea, abandonar un checkout deshacia los
# arreglos de arriba.

def test_abrir_el_pago_y_cerrarlo_no_le_borra_las_fechas_de_su_ciclo(monkeypatch):
    from core import stripe_billing

    inicio, fin = atras(105).isoformat(), atras(21).isoformat()
    perfil = {"id": "p1", "user_id": "u1", "plan": "nivel2", "price": 847.0,
              "status": "activo",           # activo pero con el ciclo terminado: caducado
              "current_period_start": inicio, "current_period_end": fin}
    monkeypatch.setattr(stripe_billing, "db", _Base([perfil]))
    corre(stripe_billing.ensure_checkout_profile(
        {"id": "u1", "email": "cliente@ejemplo.com"}, "nivel2"))

    assert perfil["current_period_end"] == fin, (
        "mirar el precio y cerrar la ventana le ha borrado el fin de ciclo: la pantalla "
        "vuelve a decirle «vas por la semana N» y a ofrecerle renovar antes de que acabe")
    assert perfil["current_period_start"] == inicio, \
        "y la tarjeta «Constancia» vuelve a contar desde su fecha de alta"
    # Que las fechas sigan ahi no le regala acceso: ese es el motivo de poder dejarlas.
    from core.plan_access import has_active_access
    assert not has_active_access(perfil)
    assert estado_del_ciclo(perfil)["ya_vencido"]


def test_al_que_le_ha_fallado_el_cobro_no_se_le_dice_que_todo_sigue_igual(monkeypatch):
    """La frase humana valia para `active` y mentia para `past_due`.

    A ese cliente el cobro automatico le ha FALLADO: decirle «tu plan sigue con el cobro
    automático de antes» es justo lo contrario, y le llega -- la pantalla le pinta el boton
    de la pasarela porque `renueva_solo` solo cuenta active/trialing.
    """
    import pytest
    from fastapi import HTTPException

    from core import stripe_billing

    perfil = {"id": "p1", "user_id": "u1", "plan": "nivel2", "status": "pago_pendiente",
              "subscription_status": "past_due"}
    monkeypatch.setattr(stripe_billing, "db", _Base([perfil]))
    with pytest.raises(HTTPException) as fallo:
        corre(stripe_billing.ensure_checkout_profile(
            {"id": "u1", "email": "cliente@ejemplo.com"}, "mantenimiento"))
    detalle = fallo.value.detail
    assert "cobro automático de antes" not in detalle, \
        "se le dice que todo sigue igual justo cuando su cobro no ha entrado"
    assert "tarjeta" in detalle, "no se le dice lo unico que puede resolverlo"
    assert "cliente" not in detalle.lower(), "lenguaje de sistema: lo lee el cliente"
