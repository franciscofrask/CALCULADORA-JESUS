"""
Las tareas automaticas que ya no aplican se cierran solas (2.6 del plan del lunes).

«Asignar entrenador a X» se creaba cuando faltaba el dato, pero nada la cerraba cuando
el dato aparecia: la tarea seguia abierta con el entrenador ya asignado, y lo mismo con
el resto de claves de estado (sin_datos, sin_precio, sin_plan...). Lo que se fija aqui,
con un cliente de usar y tirar en la base de verdad:

  - un perfil con plan de coach y sin entrenador genera la tarea `sin_entrenador`,
  - se le asigna entrenador y la siguiente pasada la marca hecha por el sistema
    (hecha=True, hecha_por_nombre="sistema", con hecha_at),
  - `sin_datos` sigue el mismo camino cuando el dato que faltaba se rellena,
  - y una tarea que SI sigue aplicando no se cierra.

Se usa la base del .env del backend (el patron del entrenador desechable de
test_avisos_equipo_panel): la pasada es la de verdad, con el catalogo de verdad.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

import pytest

motor = pytest.importorskip("motor.motor_asyncio")

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(RAIZ, ".env"))
except ImportError:
    pass

MONGO_URL, DB_NAME = os.environ.get("MONGO_URL"), os.environ.get("DB_NAME")

pytestmark = pytest.mark.skipif(
    not MONGO_URL or not DB_NAME,
    reason="Sin MONGO_URL/DB_NAME no se puede montar el cliente de prueba.")


@pytest.fixture(autouse=True)
def _sin_overrides_de_planes(monkeypatch):
    """`generar_tareas_automaticas` lee los overrides del catalogo por el cliente motor
    GLOBAL de core.database, que se queda atado al event loop del primer test que lo usa
    y revienta en el segundo («Event loop is closed»). Para estas pruebas basta el
    catalogo del codigo: los overrides se devuelven vacios y cada test vive en su loop."""
    import routes.plans as plans

    async def _vacio():
        return {}

    monkeypatch.setattr(plans, "_overrides_by_code", _vacio)


def test_asignar_entrenador_cierra_la_tarea_sola():
    from core.tareas_automaticas import generar_tareas_automaticas

    uid, cid = str(uuid.uuid4()), str(uuid.uuid4())
    ahora = datetime.now(timezone.utc).isoformat()

    async def _todo():
        c = motor.AsyncIOMotorClient(MONGO_URL)
        db = c[DB_NAME]
        try:
            # Un cliente activo con plan de coach (nivel2), SIN entrenador y sin % de
            # grasa. El resto de campos, rellenos: que solo salten sus dos tareas.
            await db.users.insert_one({
                "id": uid, "email": f"cierre.tareas.{uid[:8]}@test.com",
                "name": "Cliente Cierre De Tareas", "role": "client", "created_at": ahora})
            await db.client_profiles.insert_one({
                "id": cid, "user_id": uid, "status": "activo", "plan": "nivel2",
                "price": 847, "week": 1, "cycle_start": ahora[:10], "created_at": ahora,
                "height": 175, "goal": "perder grasa", "body_fat": None,
                "ultima_entrada": ahora[:10], "ultimo_reporte": ahora[:10]})

            # Primera pasada: las dos tareas de estado saltan y quedan abiertas.
            await generar_tareas_automaticas(db, forzar=True)
            sin_entrenador = await db.tareas.find_one({"clave": f"sin_entrenador:{cid}"}, {"_id": 0})
            sin_datos = await db.tareas.find_one({"clave": {"$regex": f"^sin_datos:{cid}:"}}, {"_id": 0})
            assert sin_entrenador and sin_entrenador["hecha"] is False, sin_entrenador
            assert sin_datos and sin_datos["hecha"] is False, sin_datos

            # Alguien asigna el entrenador y apunta el % de grasa...
            await db.client_profiles.update_one(
                {"id": cid}, {"$set": {"trainer_id": "coach-de-prueba", "body_fat": 18}})

            # ...y la siguiente pasada las cierra ella sola, como sistema.
            await generar_tareas_automaticas(db, forzar=True)
            for clave in (f"sin_entrenador:{cid}",):
                t = await db.tareas.find_one({"clave": clave}, {"_id": 0})
                assert t["hecha"] is True, t
                assert t["hecha_por_nombre"] == "sistema", t
                assert t["hecha_at"], t
            t = await db.tareas.find_one({"clave": {"$regex": f"^sin_datos:{cid}:"}}, {"_id": 0})
            assert t["hecha"] is True and t["hecha_por_nombre"] == "sistema", t

            # Y no reaparece: la clave sigue deduplicando aunque este hecha.
            assert await db.tareas.count_documents({"clave": f"sin_entrenador:{cid}"}) == 1
        finally:
            await db.tareas.delete_many({"sobre_quien": cid})
            await db.notifications.delete_many({"client_id": cid})
            await db.client_profiles.delete_many({"id": cid})
            await db.users.delete_many({"id": uid})
            c.close()

    asyncio.run(_todo())


def test_la_que_sigue_aplicando_no_se_cierra():
    """El cierre es por condicion cumplida, no una escoba: mientras el dato siga
    faltando, la tarea sigue abierta pasada tras pasada."""
    from core.tareas_automaticas import generar_tareas_automaticas

    uid, cid = str(uuid.uuid4()), str(uuid.uuid4())
    ahora = datetime.now(timezone.utc).isoformat()

    async def _todo():
        c = motor.AsyncIOMotorClient(MONGO_URL)
        db = c[DB_NAME]
        try:
            await db.users.insert_one({
                "id": uid, "email": f"cierre.tareas.{uid[:8]}@test.com",
                "name": "Cliente Sigue Sin Entrenador", "role": "client", "created_at": ahora})
            await db.client_profiles.insert_one({
                "id": cid, "user_id": uid, "status": "activo", "plan": "nivel2",
                "price": 847, "week": 1, "cycle_start": ahora[:10], "created_at": ahora,
                "height": 175, "goal": "perder grasa", "body_fat": 18,
                "ultima_entrada": ahora[:10], "ultimo_reporte": ahora[:10]})

            await generar_tareas_automaticas(db, forzar=True)
            await generar_tareas_automaticas(db, forzar=True)   # dos pasadas, sin tocar nada

            t = await db.tareas.find_one({"clave": f"sin_entrenador:{cid}"}, {"_id": 0})
            assert t and t["hecha"] is False, t
        finally:
            await db.tareas.delete_many({"sobre_quien": cid})
            await db.notifications.delete_many({"client_id": cid})
            await db.client_profiles.delete_many({"id": cid})
            await db.users.delete_many({"id": uid})
            c.close()

    asyncio.run(_todo())
