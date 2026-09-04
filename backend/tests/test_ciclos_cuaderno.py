"""El cuaderno de ciclos (core/ciclos.py): lo que se apunta al arrancar un ciclo y lo que se
lee de el. Doc de Jesus del 2-09, fase 1; Francisco, 4-09: «cuando renueva no podemos
perder el ciclo anterior; empezar a contar con las nuevas y dejar como pendiente las que
ya existen».

Contra la base de dev. El modulo se prueba con perfiles de mentira (solo hacen falta `id`,
`user_id` y `plan`, y no hay que darlos de alta en ningun sitio); los dos enganches de
Stripe, llamando a `sync_profile_from_*` con el mismo diccionario que mandaria el webhook
sobre un perfil temporal; y el del panel, por la API con una cuenta recien registrada.
Todo lo que se crea se borra al acabar.
"""
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest                                                           # noqa: E402
import requests                                                         # noqa: E402

from conftest import API, corre                                         # noqa: E402
from core.database import db                                            # noqa: E402
from core.cycle import compute_cycle                                    # noqa: E402
from core.ciclos import (abrir_ciclo, ciclo_de, ciclos_de, dia_de_espana,   # noqa: E402
                         inicio_del_ciclo_vigente, registrar_ciclo_vigente)
from core import stripe_billing                                         # noqa: E402


def _perfil(plan="nivel1", **extra):
    sufijo = uuid.uuid4().hex[:12]
    return {"id": f"ciclo-test-{sufijo}", "user_id": f"ciclo-test-user-{sufijo}", "plan": plan, **extra}


def _cuaderno(perfil):
    return corre(ciclos_de(perfil["id"]))


def _hoy():
    return date.fromisoformat(dia_de_espana(datetime.now(timezone.utc)))


@pytest.fixture
def perfil():
    """Un perfil de mentira (nivel1: 12 semanas) que no existe en client_profiles."""
    p = _perfil()
    yield p
    corre(db.ciclos.delete_many({"client_id": p["id"]}))


@pytest.fixture
def perfil_en_base():
    """Un perfil de verdad en client_profiles, sin plan, como el que deja el checkout
    pendiente. Es lo que necesitan los `sync_profile_from_*` de Stripe."""
    p = {**_perfil(plan=None), "status": "pendiente_pago",
         "created_at": datetime.now(timezone.utc).isoformat()}
    corre(db.client_profiles.insert_one(dict(p)))
    yield p
    corre(db.ciclos.delete_many({"client_id": p["id"]}))
    corre(db.client_profiles.delete_many({"id": p["id"]}))


# ---------------------------------------------------------------- el modulo

def test_abrir_dos_veces_el_mismo_inicio_no_duplica(perfil):
    uno = corre(abrir_ciclo(perfil, inicio="2026-01-05", origen="test"))
    # El mismo dia escrito como instante (un aviso repetido de Stripe): el mismo ciclo.
    dos = corre(abrir_ciclo(perfil, inicio="2026-01-05T10:00:00+00:00", origen="test"))
    assert uno and dos and uno["id"] == dos["id"]
    assert len(_cuaderno(perfil)) == 1


def test_el_segundo_ciclo_cierra_el_primero_la_vispera_y_es_renovacion(perfil):
    primero = corre(abrir_ciclo(perfil, inicio="2026-01-05", origen="test"))
    assert primero["motivo"] == "alta" and primero["numero"] == 1
    assert primero["semanas"] == 12 and primero["fin_previsto"] == "2026-03-29"
    assert primero["fin"] is None and primero["plan"] == "nivel1"
    segundo = corre(abrir_ciclo(perfil, inicio="2026-03-30", origen="test"))
    assert segundo["motivo"] == "renovacion" and segundo["numero"] == 2
    cuaderno = _cuaderno(perfil)
    assert [c["inicio"] for c in cuaderno] == ["2026-01-05", "2026-03-30"]
    assert cuaderno[0]["fin"] == "2026-03-29" and cuaderno[0]["cerrado_at"]
    assert cuaderno[1]["fin"] is None


def test_renovar_antes_de_tiempo_cierra_el_anterior_el_dia_antes(perfil):
    corre(abrir_ciclo(perfil, inicio="2026-01-05", origen="test"))
    segundo = corre(abrir_ciclo(perfil, inicio="2026-03-20", origen="test"))
    assert segundo["motivo"] == "renovacion"
    assert _cuaderno(perfil)[0]["fin"] == "2026-03-19"


def test_volver_mucho_despues_es_vuelta_y_el_anterior_se_cierra_en_su_fin_previsto(perfil):
    corre(abrir_ciclo(perfil, inicio="2026-01-05", origen="test"))
    segundo = corre(abrir_ciclo(perfil, inicio="2026-06-01", origen="test"))
    assert segundo["motivo"] == "vuelta" and segundo["numero"] == 2
    cuaderno = _cuaderno(perfil)
    assert cuaderno[0]["fin"] == "2026-03-29"
    assert cuaderno[1]["fin"] is None


def test_dia_de_espana():
    # Las 22:00 UTC de agosto ya son el dia siguiente en Madrid (UTC+2).
    assert dia_de_espana("2026-08-23T22:00:00+00:00") == "2026-08-24"
    assert dia_de_espana(datetime(2026, 8, 23, 22, 0, tzinfo=timezone.utc)) == "2026-08-24"
    # En invierno, UTC+1.
    assert dia_de_espana("2026-01-05T23:30:00+00:00") == "2026-01-06"
    assert dia_de_espana("2026-01-05T22:30:00+00:00") == "2026-01-05"
    # Un dia suelto es un dia del calendario y se devuelve tal cual.
    assert dia_de_espana("2026-08-24") == "2026-08-24"
    assert dia_de_espana(date(2026, 8, 24)) == "2026-08-24"
    assert dia_de_espana(None) is None and dia_de_espana("") is None


def test_ciclo_de_da_semana_y_bloque_del_ciclo_apuntado(perfil):
    c = corre(abrir_ciclo(perfil, inicio="2026-01-05", origen="test"))
    donde = corre(ciclo_de(perfil, "2026-02-04"))     # dia 30 desde el inicio
    assert donde == {"ciclo_id": c["id"], "ciclo_numero": 1, "ciclo_inicio": "2026-01-05",
                     "semana_del_ciclo": 5, "bloque": 2}
    assert corre(ciclo_de(perfil, "2026-01-05"))["semana_del_ciclo"] == 1
    assert corre(ciclo_de(perfil, "2026-01-11"))["semana_del_ciclo"] == 1
    assert corre(ciclo_de(perfil, "2026-01-12"))["semana_del_ciclo"] == 2
    # Un dia anterior a lo apuntado no cae en ningun ciclo del cuaderno: se calcula como
    # la semana viva y se dice con ciclo_id None.
    antes = corre(ciclo_de({**perfil, "cycle_start": "2026-01-05"}, "2026-01-01"))
    assert antes["ciclo_id"] is None and antes["semana_del_ciclo"] is not None


def test_registrar_ciclo_vigente_no_escribe_si_ya_hay_cuaderno(perfil):
    perfil["cycle_start"] = (_hoy() - timedelta(days=10)).isoformat()
    primero = corre(registrar_ciclo_vigente(perfil))
    assert primero and primero["motivo"] == "registro_inicial" and primero["origen"] == "script"
    assert primero["inicio"] == perfil["cycle_start"]
    assert corre(registrar_ciclo_vigente(perfil)) is None
    assert len(_cuaderno(perfil)) == 1


def test_registrar_ciclo_vigente_no_pisa_un_cuaderno_que_ya_tiene_ciclos(perfil):
    corre(abrir_ciclo(perfil, inicio="2026-01-05", origen="test"))
    perfil["cycle_start"] = (_hoy() - timedelta(days=10)).isoformat()
    assert corre(registrar_ciclo_vigente(perfil)) is None
    assert [c["inicio"] for c in _cuaderno(perfil)] == ["2026-01-05"]


def test_registrar_ciclo_vigente_sin_cycle_start_no_hace_nada(perfil):
    assert corre(registrar_ciclo_vigente(perfil)) is None
    assert _cuaderno(perfil) == []


def test_el_registro_inicial_apunta_la_vuelta_en_curso_si_el_ancla_es_vieja():
    """La misma cuenta que la semana viva: con un ancla de hace 100 dias en un plan de 12
    semanas la app dice «semana 3 del ciclo 2», y el ciclo abierto hoy empezo 84 dias
    despues del ancla, no en el ancla."""
    hoy = _hoy()
    vieja = _perfil(cycle_start=(hoy - timedelta(days=100)).isoformat())
    assert inicio_del_ciclo_vigente(vieja) == (hoy - timedelta(days=16)).isoformat()
    reciente = _perfil(cycle_start=(hoy - timedelta(days=10)).isoformat())
    assert inicio_del_ciclo_vigente(reciente) == (hoy - timedelta(days=10)).isoformat()
    futura = _perfil(cycle_start=(hoy + timedelta(days=3)).isoformat())
    assert inicio_del_ciclo_vigente(futura) == (hoy + timedelta(days=3)).isoformat()
    assert inicio_del_ciclo_vigente(_perfil()) is None
    try:
        registrado = corre(registrar_ciclo_vigente(vieja))
        assert registrado["inicio"] == (hoy - timedelta(days=16)).isoformat()
        assert registrado["fin_previsto"] >= hoy.isoformat()
        assert corre(ciclo_de(vieja))["semana_del_ciclo"] == compute_cycle(vieja)["week"] == 3
    finally:
        corre(db.ciclos.delete_many({"client_id": vieja["id"]}))


# ---------------------------------------------------------------- los enganches de Stripe

def test_el_pago_unico_apunta_el_ciclo_y_el_encadenado_lo_renueva(perfil_en_base):
    p = perfil_en_base
    pago = datetime(2026, 1, 7, 10, 0, tzinfo=timezone.utc)          # un miercoles
    sesion = {"id": f"cs_test_{uuid.uuid4().hex}", "payment_status": "paid",
              "created": int(pago.timestamp()), "customer": None,
              "metadata": {"plan": "reto60", "profile_id": p["id"]}}
    corre(stripe_billing.sync_profile_from_one_time_session(sesion))
    cuaderno = _cuaderno(p)
    assert len(cuaderno) == 1
    c = cuaderno[0]
    assert c["origen"] == "stripe_pago_unico" and c["motivo"] == "alta"
    assert c["plan"] == "reto60" and c["semanas"] == 8 and c["user_id"] == p["user_id"]
    # Arranca el lunes que le toca (calendario de arranque) y dura 8 semanas.
    assert c["inicio"] == "2026-01-12" and c["fin_previsto"] == "2026-03-08"
    ficha = corre(db.client_profiles.find_one({"id": p["id"]}, {"_id": 0}))
    assert dia_de_espana(ficha["cycle_start"]) == c["inicio"]

    # OJO (4-09): aqui NO se repite la misma sesion a proposito. `sync_profile_from_one_time_session`
    # no recuerda que sesiones ya proceso, y la misma sesion pagada le llega dos veces (la
    # vuelta a la app, `sync` en routes/billing.py, y el webhook): la segunda vez ve «mismo
    # plan y ciclo sin vencer» y ENCADENA otro ciclo en la ficha, o sea que cycle_start y
    # access_until se van 8 semanas mas alla con un solo pago. Eso es de la ficha, no del
    # cuaderno, que solo la sigue; esta apuntado en el informe del 4-09 para arreglarlo
    # aparte. La idempotencia del cuaderno por dia la cubre
    # test_abrir_dos_veces_el_mismo_inicio_no_duplica.

    # Renueva el mismo plan una semana antes de vencer: el nuevo ENCADENA (arranca en el
    # futuro, donde acaba el viejo) y el viejo se cierra la vispera, que es su fin previsto.
    pago2 = datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc)
    sesion2 = {**sesion, "id": f"cs_test_{uuid.uuid4().hex}", "created": int(pago2.timestamp())}
    corre(stripe_billing.sync_profile_from_one_time_session(sesion2))
    cuaderno = _cuaderno(p)
    assert [c["inicio"] for c in cuaderno] == ["2026-01-12", "2026-03-09"]
    assert cuaderno[0]["fin"] == "2026-03-08"
    assert cuaderno[1]["motivo"] == "renovacion" and cuaderno[1]["numero"] == 2
    assert cuaderno[1]["fin_previsto"] == "2026-05-03"


def test_la_suscripcion_apunta_el_ciclo_una_vez_por_periodo(perfil_en_base):
    p = perfil_en_base
    sufijo = uuid.uuid4().hex
    inicio1 = datetime(2026, 2, 2, 9, 0, tzinfo=timezone.utc)
    fin1 = inicio1 + timedelta(weeks=4)
    sub = {"id": f"sub_test_{sufijo}", "customer": f"cus_test_{sufijo}", "status": "active",
           "items": {"data": [{"price": {"id": "price_de_prueba"}}]},
           "metadata": {"plan": "elm", "profile_id": p["id"]},
           "current_period_start": int(inicio1.timestamp()),
           "current_period_end": int(fin1.timestamp()), "cancel_at_period_end": False}
    corre(stripe_billing.sync_profile_from_subscription(sub))
    # `customer.subscription.updated` llega varias veces con el mismo periodo.
    corre(stripe_billing.sync_profile_from_subscription(sub))
    corre(stripe_billing.sync_profile_from_subscription({**sub, "status": "past_due"}))
    cuaderno = _cuaderno(p)
    assert len(cuaderno) == 1
    c = cuaderno[0]
    assert c["origen"] == "stripe_suscripcion" and c["motivo"] == "alta"
    assert c["plan"] == "elm" and c["semanas"] == 4
    assert c["inicio"] == "2026-02-02" and c["fin_previsto"] == "2026-03-01"

    # El periodo siguiente: el ciclo nuevo arranca donde acaba el anterior.
    sub2 = {**sub, "current_period_start": int(fin1.timestamp()),
            "current_period_end": int((fin1 + timedelta(weeks=4)).timestamp())}
    corre(stripe_billing.sync_profile_from_subscription(sub2))
    cuaderno = _cuaderno(p)
    assert [c["inicio"] for c in cuaderno] == ["2026-02-02", "2026-03-02"]
    assert cuaderno[0]["fin"] == "2026-03-01"
    assert cuaderno[1]["motivo"] == "renovacion" and cuaderno[1]["numero"] == 2


# ---------------------------------------------------------------- el panel

@pytest.fixture
def cuenta_fresca(api_disponible, cabeceras_admin):
    """Una cuenta recien registrada, sin plan. Se borra entera al acabar."""
    email = f"cuaderno.{uuid.uuid4().hex[:10]}@test.com"
    r = requests.post(f"{API}/auth/register", json={
        "email": email, "password": "demo123", "name": "Cuaderno De Prueba", "sex": "hombre"})
    if r.status_code == 429:
        pytest.skip("El limitador de registro está activo; pon AUTH_SIN_LIMITE=1 en dev.")
    assert r.status_code in (200, 201), r.text
    tok = requests.post(f"{API}/auth/login", json={"email": email, "password": "demo123"}).json()["access_token"]
    uid = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()["id"]
    yield uid
    perfil = corre(db.client_profiles.find_one({"user_id": uid}, {"_id": 0, "id": 1}))
    if perfil:
        corre(db.ciclos.delete_many({"client_id": perfil["id"]}))
    corre(db.client_profiles.delete_many({"user_id": uid}))
    corre(db.users.delete_many({"id": uid}))


def test_el_panel_apunta_el_alta_y_no_los_cambios_de_plan(cuenta_fresca, cabeceras_admin):
    uid = cuenta_fresca

    def poner(plan):
        r = requests.put(f"{API}/admin/users/{uid}", headers=cabeceras_admin, json={"plan": plan})
        assert r.status_code == 200, r.text

    poner("nivel2")
    perfil = corre(db.client_profiles.find_one({"user_id": uid}, {"_id": 0}))
    cuaderno = corre(ciclos_de(perfil["id"]))
    assert len(cuaderno) == 1
    c = cuaderno[0]
    assert c["origen"] == "panel" and c["motivo"] == "alta"
    assert c["plan"] == "nivel2" and c["semanas"] == 12 and c["user_id"] == uid
    assert c["inicio"] == dia_de_espana(perfil["cycle_start"])
    # Cambiar de plan a quien ya lo tiene conserva el ciclo (punto 70 del doc del 23-08) y
    # no abre otro; quitarlo tampoco.
    for plan in ("gold", "elm", None):
        poner(plan)
        assert len(corre(ciclos_de(perfil["id"]))) == 1, f"el cambio a {plan} abrió un ciclo"


def test_la_misma_sesion_de_pago_unico_repetida_no_encadena_otro_ciclo(perfil_en_base):
    # La sesion pagada llega dos veces (la vuelta a la app y el webhook) y hasta el 4-09 la
    # segunda encadenaba otro ciclo en la ficha: cycle_start, current_period_end y
    # access_until se iban ocho semanas mas alla con un solo pago, y el cuaderno lo seguia.
    p = perfil_en_base
    pago = datetime(2026, 1, 7, 10, 0, tzinfo=timezone.utc)
    sesion = {"id": f"cs_test_{uuid.uuid4().hex}", "payment_status": "paid",
              "created": int(pago.timestamp()), "customer": None,
              "metadata": {"plan": "reto60", "profile_id": p["id"]}}
    corre(stripe_billing.sync_profile_from_one_time_session(sesion))
    antes = corre(db.client_profiles.find_one({"id": p["id"]}, {"_id": 0}))
    assert antes["stripe_ultima_sesion"] == sesion["id"]

    corre(stripe_billing.sync_profile_from_one_time_session(sesion))   # la misma, otra vez
    despues = corre(db.client_profiles.find_one({"id": p["id"]}, {"_id": 0}))
    for campo in ("cycle_start", "current_period_start", "current_period_end", "access_until", "fecha_pago"):
        assert despues[campo] == antes[campo], campo
    assert len(_cuaderno(p)) == 1
