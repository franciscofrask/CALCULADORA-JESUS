"""Los días de entreno, que ya no se preguntan. Bloque 5 del doc del cuestionario (18-08).

LA AVERÍA. En el panel de Rutinas ponía «A 158 no se les puede generar todavía: falta saber
lo básico de su entrenamiento». Lo que faltaba eran los días de entreno a la semana, y el
problema no era que el cliente no lo hubiera contestado: era que NINGUNA pantalla de la app
lo preguntaba. El campo nacía a None en el alta y ahí se quedaba, así que de 164 clientes
que pagan rutina ninguno real la tenía puesta y no había forma de desbloquearlos.

El documento lo cierra por el otro lado: son siempre cuatro, así que se deja de preguntar y
el campo se rellena solo con 4. Aquí se comprueban las tres cosas que eso implica:

  1. Una ficha nueva nace con cuatro días, por las tres puertas de entrada (registro,
     lead convertido y checkout de Stripe).
  2. Quien lee los días nunca se queda sin nada, aunque la ficha venga de antes y no traiga
     el campo.
  3. El panel de Rutinas ya no frena a nadie por los días. El objetivo sí sigue frenando:
     ese sí se pregunta, y sin él la rutina no vale.

Se corre con el backend vivo (REACT_APP_BACKEND_URL) y borra las cuentas que crea.
"""
import os
import sys
import uuid

import pytest
import requests

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)

from conftest import API  # noqa: E402
from core.dias_de_entreno import (  # noqa: E402
    DIAS_DE_ENTRENO_POR_DEFECTO, dias_de_entreno, dias_guardados,
)

CLAVE = "Bloque5Prueba1234"


@pytest.fixture(scope="module")
def mongo(api_disponible):
    from pymongo import MongoClient

    from core.config import DB_NAME, MONGO_URL

    cliente = MongoClient(MONGO_URL)
    try:
        yield cliente[DB_NAME]
    finally:
        cliente.close()


@pytest.fixture(scope="module")
def limpieza(mongo):
    """Recoge los correos creados y los borra al terminar, pase lo que pase."""
    correos = []
    yield correos
    for correo in correos:
        u = mongo.users.find_one({"email": correo}, {"_id": 0, "id": 1})
        if u:
            mongo.client_profiles.delete_many({"user_id": u["id"]})
            mongo.users.delete_many({"id": u["id"]})
        mongo.leads.delete_many({"email": correo})


# ─────────────────────────────────────────────────────────────────────────────
# 2 · Quien lee los días nunca se queda sin nada
# ─────────────────────────────────────────────────────────────────────────────

class TestLeerLosDias:

    def test_una_ficha_sin_el_campo_son_cuatro(self):
        """Las 256 fichas que ya existen no traen el campo, y no se van a rellenar a mano."""
        assert dias_de_entreno({}) == 4, "una ficha vieja tiene que valer cuatro, no None"
        assert dias_de_entreno({"training_days": None}) == 4
        assert dias_de_entreno({"training_days": []}) == 4, \
            "la lista vacía es «nadie lo ha dicho», no «cero días»"

    def test_lo_que_dijo_el_cliente_manda_sobre_el_cuatro(self):
        """Rellenar no es machacar: al que consta que entrena tres, tres."""
        assert dias_de_entreno({"training_days": 3}) == 3
        assert dias_de_entreno({"training_days": "6"}) == 6
        assert dias_de_entreno({"training_weekdays": ["lunes", "jueves"]}) == 2

    def test_los_disparates_no_pasan(self):
        """Un 0 o un 12 no son días de la semana; y una letra no revienta la lectura."""
        assert dias_de_entreno({"training_days": 0}) == 4, "cero días no es entrenar"
        assert dias_de_entreno({"training_days": 12}) == 7
        assert dias_de_entreno({"training_days": "no sé"}) == 4

    def test_se_puede_seguir_sabiendo_si_el_dato_existe(self):
        """El recuento de «a cuántos hay que preguntárselo» necesita distinguir el supuesto.

        Si la única lectura rellenara siempre, nadie podría volver a contar cuántas fichas
        traen el dato de verdad, y ese recuento es el que dice si hace falta migrarlas.
        """
        assert dias_guardados({}) is None
        assert dias_guardados({"training_days": 4}) == 4


# ─────────────────────────────────────────────────────────────────────────────
# 1 · Una ficha nueva nace con cuatro días
# ─────────────────────────────────────────────────────────────────────────────

class TestLaFichaNaceConCuatro:

    def test_el_que_se_registra(self, api_disponible, mongo, limpieza):
        correo = f"bloque5-alta-{uuid.uuid4().hex[:8]}@test.com"
        limpieza.append(correo)
        r = requests.post(f"{API}/auth/register",
                          json={"email": correo, "password": CLAVE, "name": "Bloque5 Alta"},
                          timeout=30)
        assert r.status_code == 200, f"no se ha podido registrar: {r.status_code} {r.text[:200]}"

        uid = r.json()["user"]["id"]
        perfil = mongo.client_profiles.find_one({"user_id": uid}, {"_id": 0, "training_days": 1})
        assert perfil, "el registro no ha dejado ficha de cliente"
        assert perfil.get("training_days") == DIAS_DE_ENTRENO_POR_DEFECTO, \
            (f"la ficha nace con training_days={perfil.get('training_days')!r}: con None el "
             f"panel de Rutinas la deja fuera y no hay pantalla donde arreglarlo")

    def test_el_lead_que_se_convierte_en_cliente(self, cabeceras_admin, mongo, limpieza):
        correo = f"bloque5-lead-{uuid.uuid4().hex[:8]}@test.com"
        limpieza.append(correo)
        r = requests.post(f"{API}/leads", headers=cabeceras_admin, timeout=30,
                          json={"name": "Bloque5 Lead", "email": correo, "source": "web"})
        assert r.status_code in (200, 201), f"no se ha podido crear el lead: {r.status_code} {r.text[:200]}"
        lead_id = r.json().get("id") or r.json().get("lead", {}).get("id")
        assert lead_id, f"la respuesta del lead no trae id: {r.text[:200]}"

        r = requests.post(f"{API}/leads/{lead_id}/convert", headers=cabeceras_admin, timeout=30,
                          json={"plan": "nivel1", "password": CLAVE})
        assert r.status_code == 200, f"no se ha podido convertir: {r.status_code} {r.text[:300]}"

        uid = r.json()["user_id"]
        perfil = mongo.client_profiles.find_one({"user_id": uid}, {"_id": 0, "training_days": 1})
        assert perfil.get("training_days") == DIAS_DE_ENTRENO_POR_DEFECTO, \
            (f"el lead convertido nace con training_days={perfil.get('training_days')!r}; "
             f"por esta puerta entran los que cierra el equipo por teléfono")
        mongo.leads.delete_one({"id": lead_id})

    def test_el_que_paga_por_stripe(self):
        """El checkout monta la ficha a mano y hasta hoy ni escribía el campo.

        No se prueba llamando a Stripe: se comprueba que la ficha que arma el módulo lleva
        el dato, que es lo que se dejó fuera.
        """
        fuente = open(os.path.join(_RAIZ, "core", "stripe_billing.py"),
                      encoding="utf-8").read()
        assert '"training_days": DIAS_DE_ENTRENO_POR_DEFECTO' in fuente, \
            "la ficha del checkout de Stripe vuelve a nacer sin días de entreno"


# ─────────────────────────────────────────────────────────────────────────────
# 3 · El panel de Rutinas ya no frena por los días
# ─────────────────────────────────────────────────────────────────────────────

class TestElPanelDeRutinas:

    def test_los_dias_ya_no_son_un_dato_que_falte(self):
        from routes.routines import _que_le_falta

        assert _que_le_falta({"goal": "definicion"}) == [], \
            "sin días de entreno ya no se frena a nadie: son cuatro para todos"

    def test_el_objetivo_sigue_frenando(self):
        """Ese sí se pregunta, y es la primera pantalla del cuestionario."""
        from routes.routines import _que_le_falta

        assert _que_le_falta({"training_days": 4}) == ["objetivo"]

    def test_el_panel_no_dice_que_falten_dias(self, cabeceras_admin):
        r = requests.get(f"{API}/admin/routines/pendientes-por-grupo",
                         headers=cabeceras_admin, timeout=120)
        assert r.status_code == 200, f"el panel no contesta: {r.status_code} {r.text[:200]}"
        datos = r.json()
        faltas = [q.get("dato") for q in (datos.get("que_les_falta") or [])]
        assert "días de entreno" not in faltas, \
            f"el panel sigue bloqueando por los días de entreno: {datos.get('que_les_falta')}"

    def test_el_grupo_de_uno_sin_dias_se_llama_de_cuatro(self):
        """Antes salía «volumen · 0 días»: un grupo con un cero delante no lo abre nadie."""
        from routes.routines import _clave_de_grupo, _como_se_llama_el_grupo

        nombre = _como_se_llama_el_grupo(_clave_de_grupo({"goal": "volumen"}))
        assert "4 días" in nombre, nombre
