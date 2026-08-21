"""Las cuentas de prueba (`es_prueba: true`) no cuentan como clientes en el panel.

Tarea 2.1 del 21-08-2026: las cuentas que el equipo creó para probar tienen rol client,
así que el filtro por rol de `_fuera_el_equipo` no las tocaba y salían en la lista de
clientes y en todos los contadores. El flag lo pone `_marcar_cuentas_prueba.py` y el
filtro vive DENTRO de `_fuera_el_equipo`, de modo que un solo punto arrastra a la lista,
al dashboard, a los cuatro paneles y a la vista de rutinas.

Se prueba con dos cuentas de usar y tirar, gemelas en todo menos en el flag: si la de
control no saliera, el test no estaría probando el filtro sino cualquier otra cosa
(visibilidad, status, plan), y un "no está" por el motivo equivocado daría el test verde
con el filtro roto.
"""
import os
import sys
import uuid
from datetime import datetime, timezone

import pytest
import requests

from conftest import API

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

SUFIJO = uuid.uuid4().hex[:8]
EMAIL_MARCADA = f"prueba.marcada.{SUFIJO}@test.com"
EMAIL_CONTROL = f"prueba.control.{SUFIJO}@test.com"


@pytest.fixture
def cuentas_desechables(api_disponible):
    """Dos clientes sembrados en la base: uno con `es_prueba: true` y su gemelo sin él.

    Directo en Mongo, como el entrenador desechable de test_avisos_equipo_panel: el flag
    lo escribe un script de datos, no un endpoint, así que no hay API por la que crearlo.
    """
    motor = pytest.importorskip("motor.motor_asyncio")
    import asyncio

    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(RAIZ, ".env"))
    except ImportError:
        pass
    url, base = os.environ.get("MONGO_URL"), os.environ.get("DB_NAME")
    if not url or not base:
        pytest.skip("Sin MONGO_URL/DB_NAME no se pueden sembrar las cuentas de prueba.")

    ahora = datetime.now(timezone.utc).isoformat()
    cuentas = []
    for email, marcada in ((EMAIL_MARCADA, True), (EMAIL_CONTROL, False)):
        uid, pid = str(uuid.uuid4()), str(uuid.uuid4())
        user = {"id": uid, "email": email, "name": "Cuenta desechable es_prueba",
                "role": "client", "password": "x", "created_at": ahora}
        perfil = {"id": pid, "user_id": uid, "plan": "elm", "status": "activo",
                  "created_at": ahora}
        if marcada:
            user["es_prueba"] = True
            perfil["es_prueba"] = True
        cuentas.append((user, perfil))

    async def _sembrar():
        c = motor.AsyncIOMotorClient(url)
        for user, perfil in cuentas:
            await c[base].users.insert_one(dict(user))
            await c[base].client_profiles.insert_one(dict(perfil))
        c.close()

    async def _borrar():
        c = motor.AsyncIOMotorClient(url)
        for user, perfil in cuentas:
            await c[base].users.delete_one({"id": user["id"]})
            await c[base].client_profiles.delete_one({"id": perfil["id"]})
        c.close()

    asyncio.run(_sembrar())
    try:
        yield
    finally:
        asyncio.run(_borrar())


def test_la_marcada_no_sale_y_su_gemela_si(cuentas_desechables, cabeceras_admin):
    r = requests.get(f"{API}/admin/clients", headers=cabeceras_admin, timeout=30)
    assert r.status_code == 200, r.text
    correos = {(c.get("user") or {}).get("email") for c in r.json()}
    assert EMAIL_CONTROL in correos, "la cuenta de control tendria que salir: sin ella el test no prueba nada"
    assert EMAIL_MARCADA not in correos, "es_prueba=true tiene que dejar la cuenta fuera del panel"


def test_tampoco_cuenta_en_la_vista_de_rutinas(cuentas_desechables, cabeceras_admin):
    """El overview de rutinas tenia su propia copia del filtro (routines.py): si alguien
    la vuelve a separar del helper, la cuenta de prueba reaparece como trabajo pendiente."""
    r = requests.get(f"{API}/admin/routines/overview", headers=cabeceras_admin, timeout=30)
    assert r.status_code == 200, r.text
    correos = {c.get("email") for c in r.json()}
    assert EMAIL_CONTROL in correos
    assert EMAIL_MARCADA not in correos
