# -*- coding: utf-8 -*-
"""Los circuitos que la revision del 24-08 encontro abiertos, y que ya no lo estan.

Los seis graves por el lado del codigo. Lo que sigue faltando no es un arreglo sino una
pieza que no existe: que el equipo pueda alargar un ciclo desde el panel, para el que
paga por transferencia y para el que no tiene precio congelado.

Cada bloque empieza con lo que le pasaba a una persona, que es lo que hay que impedir
que vuelva.

Ejecutar:
    cd backend && REACT_APP_BACKEND_URL=http://127.0.0.1:8000 \
        venv/Scripts/python.exe -m pytest tests/test_circuitos_2408.py -q
"""
from datetime import datetime, timedelta, timezone

from core.plan_access import estado_de_acceso, has_active_access

# El bucle es el de la bateria entera (tests/conftest.py): ver ahi por que.
from conftest import corre  # noqa: E402


def dentro(dias=30):
    return (datetime.now(timezone.utc) + timedelta(days=dias)).isoformat()


def atras(dias=30):
    return (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()


# =====================================================================================
# GRAVE 5 · «pago mi plan y la app me dice que mi suscripcion ha terminado»
# =====================================================================================
# Todo lo que se vende es pago unico desde el 20-08: el webhook deja access_until en el
# futuro y subscription_status a None, pero no borra el stripe_subscription_id de una
# suscripcion vieja ya cancelada. Con eso se miraba la suscripcion muerta. El 24-08 eran
# 84 de los 119 clientes que entran.

def test_el_pago_unico_manda_sobre_la_suscripcion_vieja():
    perfil = {
        "plan": "nivel2", "status": "activo",
        "stripe_subscription_id": "sub_de_hace_dos_anos",   # cancelada hace tiempo
        "subscription_status": None,                        # lo que deja el pago unico
        "access_until": dentro(80),                         # acaba de pagar 12 semanas
    }
    assert has_active_access(perfil), \
        "acaba de pagar y se le deja sin acceso por una suscripcion que ya no existe"
    assert estado_de_acceso(perfil) == {"activo": True, "motivo": None}, \
        "el panel y la app le pintarian «caducado» al que acaba de pagar"


def test_el_pago_unico_caducado_no_da_acceso():
    """El arreglo no puede convertirse en una puerta abierta: lo pagado se acaba."""
    perfil = {"plan": "nivel2", "status": "activo",
              "stripe_subscription_id": "sub_viejo", "subscription_status": None,
              "access_until": atras(1)}
    assert not has_active_access(perfil)
    assert estado_de_acceso(perfil)["motivo"] == "caducado"


def test_la_baja_sigue_bloqueando_aunque_quede_pagado_por_delante():
    """Una baja manda sobre la fecha: si no, un dado de baja seguiria entrando."""
    for estado in ("baja", "baja_automatica", "cancelado", "pausado"):
        perfil = {"plan": "nivel2", "status": estado, "access_until": dentro(30)}
        assert not has_active_access(perfil), f"«{estado}» tendria que bloquear"


def test_la_suscripcion_viva_sigue_mandando_cuando_no_hay_pago_unico():
    """El que si tiene suscripcion (sin access_until) se sigue juzgando por ella."""
    vivo = {"plan": "nivel2", "status": "activo",
            "stripe_subscription_id": "sub_1", "subscription_status": "active"}
    muerto = {"plan": "nivel2", "status": "activo",
              "stripe_subscription_id": "sub_1", "subscription_status": "canceled"}
    assert has_active_access(vivo)
    assert not has_active_access(muerto)


# =====================================================================================
# GRAVE 1 · «pulso renovar, me dice que no tengo que hacer nada, y me quedo caducado»
# =====================================================================================
# `por_checkout` solo se encendia para el plan antiguo reabierto, asi que a los planes
# que se venden hoy se les daba el atajo de «no tienes que hacer nada mas» sin cobrarles.
# Desde el 20-08 NINGUN plan renueva solo: lo unico que justifica el atajo es arrastrar
# una suscripcion viva de las de antes.

def renovar_de(plan, suscripcion_viva=False, precio_alta=None):
    from core.renovacion import salidas
    from models.user import PLAN_CATALOG, opciones_de_renovacion
    ss = salidas(plan_actual=plan, opciones_catalogo=opciones_de_renovacion(plan, PLAN_CATALOG),
                 catalogo=PLAN_CATALOG, precio_alta=precio_alta,
                 suscripcion_viva=suscripcion_viva)
    return next((s for s in ss if s["tipo"] == "renovar"), None)


def test_renovar_un_plan_del_catalogo_lleva_a_pagar():
    for plan in ("nivel1", "nivel2", "elm", "mantenimiento"):
        r = renovar_de(plan)
        assert r, f"a un {plan} no se le ofrece seguir igual"
        assert r["por_checkout"], (
            f"a un {plan} se le dice «no tienes que hacer nada» y no se le cobra: "
            "llegara el fin de ciclo y se quedara caducado creyendo que renovo")


def test_el_que_tiene_suscripcion_viva_no_paga_dos_veces():
    """El atajo sigue existiendo para quien de verdad renueva solo."""
    for plan in ("nivel1", "nivel2", "elm", "mantenimiento"):
        r = renovar_de(plan, suscripcion_viva=True)
        assert not r["por_checkout"], (
            f"a un {plan} con la suscripcion viva se le mandaria a pagar otra vez")


def test_el_plan_que_se_cierra_hablando_no_abre_una_pasarela_de_1500():
    """nivel3 se contrata por telefono; renovarlo tampoco puede ser un autoservicio."""
    r = renovar_de("nivel3")
    assert r["por_llamada"], \
        "renovar el Premium abriria un cobro de 1.500 EUR por su cuenta"


def test_el_plan_antiguo_reabierto_se_queda_como_estaba():
    """Los legacy no se tocan aqui: su renovacion espera una decision de precio."""
    for plan in ("reto12en12", "gold"):
        r = renovar_de(plan)
        if r:
            assert r["por_checkout"], f"{plan} deberia seguir yendo a la pasarela"


# =====================================================================================
# GRAVE 3 · «abro el pago, me lo pienso, cierro, y he perdido el ciclo que ya habia pagado»
# =====================================================================================
# Los tests que tocan la base van con `corre()`, el bucle unico de arriba.

def test_abrir_un_pago_no_le_quita_el_acceso_al_que_ya_pago():
    async def recorrido():
        from core.database import db
        from core.stripe_billing import ensure_checkout_profile

        u = await db.users.find_one({"email": "clientedemo@test.com"}, {"id": 1, "email": 1})
        if not u:
            return "sin cuenta de demo"
        original = await db.client_profiles.find_one({"user_id": u["id"]}, {"_id": 0})
        if not original:
            return "la cuenta de demo no tiene ficha"
        fin = dentro(42)
        await db.client_profiles.update_one({"id": original["id"]}, {"$set": {
            "plan": "nivel2", "status": "activo", "current_period_end": fin,
            "access_until": fin, "subscription_status": None}})
        try:
            # Abre el pago de OTRO plan y lo abandona (no llega ningun webhook).
            await ensure_checkout_profile(u, "mantenimiento")
            despues = await db.client_profiles.find_one({"id": original["id"]}, {"_id": 0})
            return {
                "acceso": has_active_access(despues),
                "plan": despues.get("plan"),
                "status": despues.get("status"),
                "fin": despues.get("current_period_end"),
                "esperado_fin": fin,
            }
        finally:
            await db.client_profiles.replace_one({"id": original["id"]}, original)

    r = corre(recorrido())
    if isinstance(r, str):
        import pytest
        pytest.skip(r)
    assert r["acceso"], "abandonar un checkout le ha dejado sin el acceso que ya tenia pagado"
    assert r["plan"] == "nivel2", "le ha cambiado el plan sin haber pagado"
    assert r["status"] == "activo", "le ha dejado en «pendiente_pago» teniendo su ciclo vivo"
    assert r["fin"] == r["esperado_fin"], "le ha borrado la fecha de fin de su ciclo"


# =====================================================================================
# GRAVE 4 · «abro la conversacion y me dice que no hay mensajes con este cliente»
# =====================================================================================

def test_el_equipo_lee_el_hilo_aunque_lo_llevara_otro_companero():
    """La bandeja del equipo es compartida desde el 11-08; el hilo tambien tiene que serlo."""
    import os
    import uuid

    import pytest
    import requests
    from pymongo import MongoClient

    from core.config import DB_NAME, MONGO_URL

    api = os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/") + "/api"
    base = MongoClient(MONGO_URL)[DB_NAME]
    yo = base.users.find_one({"email": "francisco@test.com"}, {"id": 1})
    otro = base.users.find_one({"role": {"$in": ["admin", "trainer"]},
                                "id": {"$ne": (yo or {}).get("id")}}, {"id": 1})
    cliente = base.users.find_one({"role": "client", "deleted_at": None}, {"id": 1})
    if not (yo and otro and cliente):
        pytest.skip("hacen falta dos cuentas de equipo y un cliente")

    marca = "PRUEBA HILO COMPARTIDO " + uuid.uuid4().hex[:8]
    base.messages.insert_one({
        "id": str(uuid.uuid4()), "sender_id": cliente["id"], "receiver_id": otro["id"],
        "content": marca, "read": False, "created_at": dentro(0)})
    try:
        r = requests.post(f"{api}/auth/login",
                          json={"email": "francisco@test.com", "password": "demo123"}, timeout=30)
        if r.status_code != 200:
            pytest.skip("no se puede entrar como francisco@test.com")
        cab = {"Authorization": "Bearer " + r.json()["access_token"]}
        hilo = requests.get(f"{api}/messages?with_user={cliente['id']}", headers=cab, timeout=60)
        assert hilo.status_code == 200, hilo.text[:200]
        textos = [m.get("content") for m in hilo.json()]
        assert marca in textos, (
            "el equipo abre la conversacion y no ve lo que el cliente escribio a otro "
            "companero: puede contestar sin haber podido leerlo")
    finally:
        base.messages.delete_many({"content": marca})


# =====================================================================================
# GRAVE 6 · «llevo tres años con vosotros y no me deja renovar»
# =====================================================================================
# El endpoint de renovacion ya sabia cobrar un plan antiguo con su precio congelado y en
# linea (esos planes no tienen Price en Stripe). Pero una linea antes llamaba a
# `ensure_checkout_profile`, que resolvia el Price SIEMPRE -- un dato que en ese camino
# solo se guarda en la ficha -- y reventaba con 503 antes de llegar. Eran 73 clientes de
# plan antiguo de los 119 que entran.

def test_preparar_el_checkout_no_revienta_sin_precio_de_stripe():
    """El Price aqui solo se apunta; no poder resolverlo no puede cortar el paso."""
    async def recorrido():
        from core.database import db
        from core.stripe_billing import ensure_checkout_profile

        u = await db.users.find_one({"email": "clientedemo@test.com"}, {"_id": 0})
        if not u:
            return "sin cuenta de demo"
        original = await db.client_profiles.find_one({"user_id": u["id"]}, {"_id": 0})
        if not original:
            return "la cuenta de demo no tiene ficha"
        # Sin acceso vivo, para que entre por el camino que escribe la ficha.
        await db.client_profiles.update_one({"id": original["id"]}, {"$set": {
            "status": "pendiente_pago", "access_until": None, "current_period_end": None,
            "subscription_status": None}})
        suyo = original.get("plan")
        try:
            p = await ensure_checkout_profile(u, "reto12en12")   # legacy, sin Price
            return {"plan": p.get("plan"), "suyo": suyo,
                    "checkout_plan": p.get("checkout_plan")}
        finally:
            await db.client_profiles.replace_one({"id": original["id"]}, original)

    r = corre(recorrido())
    if isinstance(r, str):
        import pytest
        pytest.skip(r)
    # Lo que este test vigila es que NO REVIENTE: si hubiera vuelto el 503 de antes,
    # `corre` habria propagado la excepcion y no habriamos llegado hasta aqui.
    #
    # Y de paso, el contrato nuevo del 25-08: al que YA tiene plan no se le escribe el
    # que va a comprar hasta que pague. Antes esto afirmaba lo contrario -- que la ficha
    # se quedaba con «reto12en12» -- y ese era justamente el fallo: mirar un plan y
    # cerrar la ventana dejaba al cliente sin el suyo.
    assert r["plan"] == r["suyo"], "abrir un pago le ha cambiado el plan sin haber pagado"
    assert r["checkout_plan"] == "reto12en12", "no ha quedado apuntado que iba a por ese"


def test_sin_precio_congelado_no_se_adivina_cobrando_el_ultimo_recibo():
    """SU precio, o ninguno.

    La cascada tenia un escalon que miraba el ultimo cobro del cliente, fuera de lo que
    fuera. Medido sobre los diez sin precio: a dos les habria cobrado 60 EUR por renovar
    un Reto 12en12, porque 60 fue su ultimo recibo (un mes de Mantenimiento). Ahora, sin
    precio congelado, sale la frase humana y lo resuelve el equipo.
    """
    fuente = open("routes/billing.py", encoding="utf-8").read()
    trozo = fuente[fuente.index("ES LA RENOVACIÓN DE SU PLAN ANTIGUO"):]
    trozo = trozo[:trozo.index("EL PREMIUM SE CONTRATA POR LLAMADA")]
    assert "pagos_historicos" not in trozo, (
        "vuelve a adivinar el precio de renovacion con el ultimo cobro del cliente")
    assert "No sabemos tu precio de renovación" in trozo, \
        "se ha perdido la salida humana para el que no tiene precio congelado"
