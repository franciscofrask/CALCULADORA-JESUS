"""
La campanita del EQUIPO: que los avisos que escribe `avisar_al_equipo` se puedan leer, y
que cada uno vea SOLO los suyos.

Por qué existe este fichero: durante meses `avisar_al_equipo` escribió avisos en
`db.notifications` que no pintaba nadie, porque no había endpoint que los sirviera y el
panel no llamaba a ninguno. Dos de esos avisos son dinero (la rutina del mes de 57 € y el
«Cuéntame el Silver»), así que lo que se prueba aquí no es una lista: es que una petición
de compra no se quede sin leer.

El filtro por destinatario se prueba de verdad, con un entrenador de usar y tirar que se
crea y se borra: `get_admin_user` deja pasar a admin Y a entrenador por igual, así que si
alguien quita el `user_id` del filtro, un entrenador se lleva el buzón de la casa entera y
nada más lo notaría.
"""
import os
import uuid
from datetime import datetime, timezone

import pytest
import requests

from conftest import API, login


TIPOS_DE_DINERO = {"rutina_del_mes", "interes_plan", "revision_suelta_pagada", "lead_pagado"}
# En @test.com y no en un dominio reservado tipo @test.invalid: el validador de email de
# la API los rechaza con un 422 y el entrenador de prueba no llegaba ni a entrar.
EMAIL_DESECHABLE = f"trainer.avisos.{uuid.uuid4().hex[:8]}@test.com"


def test_el_admin_lee_sus_avisos_de_equipo(cabeceras_admin):
    r = requests.get(f"{API}/notifications/equipo", headers=cabeceras_admin, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert isinstance(d.get("notifications"), list)
    assert isinstance(d.get("unread"), int)
    assert isinstance(d.get("dinero_sin_leer"), int)


def test_cada_aviso_trae_con_que_pintarlo(cabeceras_admin):
    """Etiqueta, marca de dinero y enlace a la ficha: sin eso la lista no se lee de un
    vistazo, que es justo el problema que había."""
    d = requests.get(f"{API}/notifications/equipo", headers=cabeceras_admin, timeout=30).json()
    for a in d["notifications"]:
        assert a.get("etiqueta"), a
        assert isinstance(a.get("dinero"), bool), a
        assert a["dinero"] == (a.get("type") in TIPOS_DE_DINERO), a
        if a.get("client_id"):
            assert a.get("link") == f"/admin/clients/{a['client_id']}", a


def test_las_peticiones_de_compra_van_primero(cabeceras_admin):
    """Lo que es una venta sin atender se pinta arriba, por delante de treinta
    cuestionarios rellenos: por fecha se quedaba debajo y no lo veía nadie."""
    d = requests.get(f"{API}/notifications/equipo", headers=cabeceras_admin, timeout=30).json()
    avisos = d["notifications"]
    ventas = d["dinero_sin_leer"]
    for a in avisos[:ventas]:
        assert a["dinero"] and not a.get("read"), a
    for a in avisos[ventas:]:
        assert not (a["dinero"] and not a.get("read")), a


def test_los_viejos_tambien_salen(cabeceras_admin):
    """Los avisos escritos antes de que existiera la marca `equipo` no llevan el campo:
    entran por el `type`. Si se filtrara solo por la marca, lo ya escrito se perdería."""
    d = requests.get(f"{API}/notifications/equipo", headers=cabeceras_admin, timeout=30).json()
    tipos = {a.get("type") for a in d["notifications"]}
    assert not tipos or tipos & {
        "rutina_del_mes", "interes_plan", "macros_propuestos", "perfil_completo",
        "revision_suelta_pagada", "lead_pagado"}


@pytest.mark.parametrize("ruta", ["", "/unread-count"])
def test_un_cliente_no_entra(cabeceras_cliente, ruta):
    r = requests.get(f"{API}/notifications/equipo{ruta}", headers=cabeceras_cliente, timeout=30)
    assert r.status_code == 403, r.text


# ── El filtro por destinatario, con un entrenador de verdad ───────────────────

@pytest.fixture
def entrenador_desechable(api_disponible):
    """Un entrenador nuevo, sin un solo cliente, que se borra al acabar.

    `created_at` es obligatorio en `UserResponse`: sin él el login revienta con un 500 y el
    fallo parece de otra cosa.
    """
    motor = pytest.importorskip("motor.motor_asyncio")
    import asyncio
    import sys

    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, raiz)
    from core.security import hash_password

    # La base sale del .env del backend, no del entorno del que lanza pytest: sin esto la
    # prueba del filtro por destinatario se saltaba en silencio, que es peor que fallar.
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(raiz, ".env"))
    except ImportError:
        pass

    url, base = os.environ.get("MONGO_URL"), os.environ.get("DB_NAME")
    if not url or not base:
        pytest.skip("Sin MONGO_URL/DB_NAME no se puede crear el entrenador de prueba.")

    uid = str(uuid.uuid4())
    doc = {"id": uid, "email": EMAIL_DESECHABLE, "name": "Trainer de prueba", "role": "trainer",
           "password": hash_password("demo123"),
           "created_at": datetime.now(timezone.utc).isoformat()}

    async def _crear():
        c = motor.AsyncIOMotorClient(url)
        await c[base].users.insert_one(dict(doc))
        c.close()

    async def _borrar():
        c = motor.AsyncIOMotorClient(url)
        await c[base].notifications.delete_many({"user_id": uid})
        await c[base].users.delete_many({"email": EMAIL_DESECHABLE})
        c.close()

    async def _sembrar(tipo, titulo, mensaje):
        """Le deja un aviso de equipo al entrenador de prueba, por la puerta de siempre."""
        c = motor.AsyncIOMotorClient(url)
        from core.avisos_equipo import avisar_al_equipo
        await avisar_al_equipo(c[base], tipo=tipo, titulo=titulo, mensaje=mensaje,
                               client_id=None, trainer_id=uid)
        c.close()

    asyncio.run(_crear())
    try:
        token = login(EMAIL_DESECHABLE, "demo123")
        if not token:
            pytest.skip("No se pudo entrar con el entrenador de prueba.")
        yield {"id": uid, "cabeceras": {"Authorization": f"Bearer {token}"},
               "sembrar": lambda *a: asyncio.run(_sembrar(*a))}
    finally:
        asyncio.run(_borrar())


def test_un_entrenador_sin_clientes_no_ve_nada(entrenador_desechable):
    """Lo importante de todo el fichero: el buzón de otro no es suyo."""
    r = requests.get(f"{API}/notifications/equipo",
                     headers=entrenador_desechable["cabeceras"], timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()["notifications"] == []
    r = requests.get(f"{API}/notifications/equipo/unread-count",
                     headers=entrenador_desechable["cabeceras"], timeout=30)
    assert r.json()["count"] == 0


def test_la_campanita_del_cliente_no_se_lleva_las_peticiones_de_compra(entrenador_desechable):
    """El agujero por el que se perdían de verdad.

    Los avisos del cliente y los del equipo viven en la MISMA colección y bajo el mismo
    `user_id`. El `PUT /notifications/read-all` del cliente marcaba leído todo lo que
    encontrara, así que a quien abriera la campanita del cliente se le quedaban leídas las
    peticiones de compra sin haberlas visto nadie. Comprobado en dev antes de arreglarlo.
    """
    cab = entrenador_desechable["cabeceras"]
    entrenador_desechable["sembrar"]("rutina_del_mes", "Quiere la rutina del mes",
                                     "Prueba: la campanita del cliente no debe tocarlo.")
    assert requests.get(f"{API}/notifications/equipo/unread-count",
                        headers=cab, timeout=30).json()["count"] == 1

    r = requests.put(f"{API}/notifications/read-all", headers=cab, timeout=30)
    assert r.status_code == 200, r.text

    assert requests.get(f"{API}/notifications/equipo/unread-count",
                        headers=cab, timeout=30).json()["count"] == 1


def test_el_cliente_no_ve_los_avisos_del_equipo_en_su_campanita(entrenador_desechable):
    """Y al revés: en la lista del cliente no se cuelan. Cada buzón, el suyo."""
    cab = entrenador_desechable["cabeceras"]
    entrenador_desechable["sembrar"]("interes_plan", "Quiere que le cuentes el plan de arriba",
                                     "Prueba: esto no es un aviso de cliente.")
    d = requests.get(f"{API}/notifications", headers=cab, timeout=30).json()
    assert not [n for n in d["notifications"] if n.get("type") == "interes_plan"], d


def test_un_entrenador_no_marca_leido_lo_de_otro(cabeceras_admin, entrenador_desechable):
    """Ni con el id delante: si pudiera, le apagaría a otro un aviso que ese no ha visto."""
    d = requests.get(f"{API}/notifications/equipo", headers=cabeceras_admin, timeout=30).json()
    ajenos = [a["id"] for a in d["notifications"] if not a.get("read")]
    if not ajenos:
        pytest.skip("El admin no tiene ningún aviso sin leer con el que probarlo.")
    antes = d["unread"]

    r = requests.put(f"{API}/notifications/equipo/{ajenos[0]}/read",
                     headers=entrenador_desechable["cabeceras"], timeout=30)
    assert r.status_code == 200 and r.json()["ok"] is False

    r = requests.put(f"{API}/notifications/equipo/read-all",
                     headers=entrenador_desechable["cabeceras"], timeout=30)
    assert r.status_code == 200

    despues = requests.get(f"{API}/notifications/equipo",
                           headers=cabeceras_admin, timeout=30).json()["unread"]
    assert despues == antes
