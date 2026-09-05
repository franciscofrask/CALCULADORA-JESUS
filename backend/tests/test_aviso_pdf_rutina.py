"""
El aviso al subir la rutina en PDF (tarea 1.2 del plan del lunes).

Por qué existe este fichero: las tres vías estructuradas de poner rutina (guardarla,
generarla, asignarla de la biblioteca) avisan al cliente con `avisar_rutina_nueva`, y la
cuarta -- subirle el PDF -- guardaba en `db.rutina_pdfs` y se callaba. El entrenador leía
«Rutina en PDF subida» y el cliente no se enteraba de que la tenía.

Se prueba con un cliente de usar y tirar (mismo patrón que el entrenador desechable de
test_avisos_equipo_panel.py): así el primer aviso del día es de verdad el primero, y no
depende de lo que le haya pasado hoy a clientedemo.

OJO al lanzarlo: por RUTA explícita (el conftest se salta en silencio ficheros sin
commitear si se lanza por directorio).
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

import pytest
import requests

from conftest import API

PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< >>\n%%EOF\n"


def _subir(cabeceras_admin, client_id, nombre="rutina.pdf"):
    return requests.post(f"{API}/admin/routines/pdf/{client_id}", headers=cabeceras_admin,
                         files={"file": (nombre, PDF, "application/pdf")}, timeout=30)


@pytest.fixture(scope="module")
def entreno_encendido(api_disponible, cabeceras_admin):
    """El aviso lleva el mismo candado que la pantalla (t3_entreno): sin encenderlo no
    habría nada que probar."""
    r = requests.put(f"{api_disponible}/admin/settings", headers=cabeceras_admin,
                     json={"pantallas": {"t3_entreno": True}}, timeout=15)
    assert r.status_code == 200
    return r.json()["pantallas"]


@pytest.fixture
def cliente_desechable(api_disponible):
    """Un cliente nuevo en la base, sin ningún aviso encima, que se borra al acabar."""
    motor = pytest.importorskip("motor.motor_asyncio")

    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, raiz)
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(raiz, ".env"))
    except ImportError:
        pass

    url, base = os.environ.get("MONGO_URL"), os.environ.get("DB_NAME")
    if not url or not base:
        pytest.skip("Sin MONGO_URL/DB_NAME no se puede crear el cliente de prueba.")

    uid, cid = str(uuid.uuid4()), str(uuid.uuid4())
    ahora = datetime.now(timezone.utc).isoformat()

    async def _crear():
        c = motor.AsyncIOMotorClient(url)
        await c[base].users.insert_one({
            "id": uid, "email": f"pdf.rutina.{uid[:8]}@test.com", "name": "Cliente PDF",
            "role": "client", "password": "sin-login", "created_at": ahora})
        await c[base].client_profiles.insert_one({
            "id": cid, "user_id": uid, "name": "Cliente PDF", "status": "activo",
            "plan": "nivel2", "created_at": ahora})
        c.close()

    async def _borrar():
        c = motor.AsyncIOMotorClient(url)
        await c[base].notifications.delete_many({"user_id": uid})
        await c[base].rutina_pdfs.delete_many({"client_id": cid})
        await c[base].client_profiles.delete_many({"id": cid})
        await c[base].users.delete_many({"id": uid})
        c.close()

    async def _avisos():
        c = motor.AsyncIOMotorClient(url)
        docs = await c[base].notifications.find(
            {"user_id": uid, "familia": "rutina_nueva"}, {"_id": 0}).to_list(50)
        c.close()
        return docs

    asyncio.run(_crear())
    try:
        yield {"user_id": uid, "client_id": cid,
               "avisos": lambda: asyncio.run(_avisos())}
    finally:
        asyncio.run(_borrar())


def test_subir_el_pdf_avisa_y_resubirlo_no_avisa_dos_veces(
        cabeceras_admin, cliente_desechable, entreno_encendido):
    """Lo importante de todo el fichero: el PDF que se guarda le SUENA al cliente, y el
    que se resube el mismo día para corregir una errata no le suena otra vez (la regla de
    «máximo uno al día» de los avisos de entrega de notifications.py)."""
    cid = cliente_desechable["client_id"]

    r = _subir(cabeceras_admin, cid)
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True

    avisos = cliente_desechable["avisos"]()
    assert len(avisos) == 1, "subir el PDF tiene que crear el aviso de rutina nueva"
    assert avisos[0]["title"] == "Ya tienes tu rutina"
    assert avisos[0]["link"] == "/dashboard/routine"
    assert avisos[0]["read"] is False

    r = _subir(cabeceras_admin, cid, nombre="rutina_corregida.pdf")
    assert r.status_code == 200, r.text

    avisos = cliente_desechable["avisos"]()
    assert len(avisos) == 1, "la resubida del mismo día no puede sonar dos veces"


def test_con_el_interruptor_apagado_el_pdf_se_guarda_pero_no_suena(
        api_disponible, cabeceras_admin, cliente_desechable):
    """El mismo candado que las tres vías estructuradas: con `t3_entreno` apagado el
    cliente no puede abrir la pantalla, así que avisarle sería enseñarle a ignorar los
    avisos. El PDF sí se guarda: el candado es del aviso, no de la subida."""
    requests.put(f"{api_disponible}/admin/settings", headers=cabeceras_admin,
                 json={"pantallas": {"t3_entreno": False}}, timeout=15)
    try:
        r = _subir(cabeceras_admin, cliente_desechable["client_id"])
        assert r.status_code == 200, r.text
        assert cliente_desechable["avisos"]() == []
    finally:
        requests.put(f"{api_disponible}/admin/settings", headers=cabeceras_admin,
                     json={"pantallas": {"t3_entreno": True}}, timeout=15)


def test_un_cliente_que_no_existe_no_deja_aviso_huerfano(cabeceras_admin, entreno_encendido):
    r = _subir(cabeceras_admin, f"no-existe-{uuid.uuid4().hex[:8]}")
    assert r.status_code == 404


def test_el_panel_deja_de_pedir_rutina_a_quien_ya_tiene_su_pdf(
        cabeceras_admin, cliente_desechable, entreno_encendido):
    """PUNTOS 67 Y 69 DEL DOC DEL 24-08: «Montalvo tiene su PDF subido, su reparto por
    días y sus 8 semanas, y el sistema lo cuenta como sin rutina».

    La pantalla de Rutinas ya cuenta el PDF desde el 24-08 (`has_routine` = la
    estructurada O el PDF), pero el «Por hacer esta semana» del Dashboard se quedó
    contando solo la estructurada. Medido en producción el 28-08: de los 177 clientes
    activos cuyo plan incluye rutina, 0 tenían una estructurada y 33 su PDF, así que un
    panel decía 177 «sin rutina» y el otro 33 «con rutina puesta».

    Y no es solo el número: esa columna se esconde sola cuando le falta a más de nueve de
    cada diez, porque entonces deja de ser trabajo pendiente y pasa a ser el estado de la
    casa. Con la cuenta mala se escondía siempre.
    """
    cid = cliente_desechable["client_id"]

    def sin_rutina():
        r = requests.get(f"{API}/admin/todo-semana", headers=cabeceras_admin, timeout=120)
        assert r.status_code == 200, r.text
        return {c["client_id"] for c in (r.json().get("sin_rutina") or [])}

    assert cid in sin_rutina(), (
        "el cliente de prueba (plan nivel2, que incluye rutina) tendría que salir como "
        "pendiente antes de subirle nada")

    assert _subir(cabeceras_admin, cid).status_code == 200
    assert cid not in sin_rutina(), (
        "con su PDF subido, el panel sigue pidiéndole rutina: es el punto 69 otra vez")


# ── UNA SOLA RESPUESTA A «¿TIENE RUTINA?» (4-09) ──────────────────────────────────────
#
# Puntos 80 y 103 del artefacto «La app, pantalla por pantalla», confirmados por Gonzalo en
# producción ese día: «Montalvo tiene rutina-152.pdf entregada y el cliente la ve y la abre.
# La ficha, en Resumen, dice Sin rutina» y «se corrigió el conteo en Rutinas y el Inicio
# sigue con el suyo». Desde hoy las tres pantallas leen `core.rutina_puesta`.

def test_la_ficha_dice_en_pdf_con_la_misma_funcion_que_el_panel(
        cabeceras_admin, cliente_desechable, entreno_encendido):
    """Punto 80: el Resumen de la ficha pinta `rutina_puesta`, que viene del backend con la
    misma función que el panel. Antes miraba solo `routines` (las estructuradas)."""
    cid = cliente_desechable["client_id"]

    def ficha():
        r = requests.get(f"{API}/admin/clients/{cid}", headers=cabeceras_admin, timeout=120)
        assert r.status_code == 200, r.text
        return r.json().get("rutina_puesta") or {}

    antes = ficha()
    assert antes.get("estado") == "ninguna" and antes.get("tiene") is False, antes

    assert _subir(cabeceras_admin, cid).status_code == 200
    despues = ficha()
    assert despues.get("estado") == "pdf", despues
    assert despues.get("tiene") is True and despues.get("en_pdf") is True
    assert despues.get("pdf_uploaded_at"), "la fecha del PDF es lo que pinta Entreno"


def test_el_inicio_y_rutinas_cuentan_a_los_mismos_sin_rutina(cabeceras_admin):
    """Punto 103: dos números de la misma sesión que no pueden discrepar. El Inicio decía
    93 y Rutinas 70 (23 + 47) porque el Inicio contaba como prometida la rutina «opcional»
    de Bronze y Mantenimiento. Ahora los dos salen de `clientes_y_su_rutina`."""
    todo = requests.get(f"{API}/admin/todo-semana", headers=cabeceras_admin, timeout=120)
    assert todo.status_code == 200, todo.text
    inicio = {c["client_id"] for c in todo.json().get("sin_rutina") or []}

    ov = requests.get(f"{API}/admin/routines/overview", headers=cabeceras_admin, timeout=120)
    assert ov.status_code == 200, ov.text
    filas = ov.json()
    rutinas = {c["client_id"] for c in filas if c["la_lleva_en_su_plan"] and not c["has_routine"]}
    assert inicio == rutinas, (
        f"solo en el Inicio: {len(inicio - rutinas)} · solo en Rutinas: {len(rutinas - inicio)}")
    assert todo.json()["con_rutina_en_plan"] == sum(1 for c in filas if c["la_lleva_en_su_plan"])
    # Y la pantalla de Rutinas no se rompió: las claves de siempre siguen ahí.
    if filas:
        assert {"client_id", "name", "email", "plan", "has_routine", "tiene_pdf",
                "pdf_uploaded_at", "training_days", "routine_created_at"} <= set(filas[0])
        assert "perfil" not in filas[0], "el perfil no viaja a la pantalla"


class TestElCriterioEnCore:
    """Las preguntas puras de `core.rutina_puesta`, sin base."""

    @staticmethod
    def _core():
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import core.rutina_puesta as rp
        return rp

    def test_la_estructurada_manda_y_el_pdf_tambien_es_tener_rutina(self):
        rp = self._core()
        assert rp.estado_de(None) == "ninguna"
        assert rp.estado_de({"activa": None, "pdf": None}) == "ninguna"
        assert rp.estado_de({"activa": None, "pdf": "2026-08-26"}) == "pdf"
        # Un PDF sin fecha sigue siendo un PDF.
        assert rp.estado_de({"activa": None, "pdf": ""}) == "pdf"
        assert rp.estado_de({"activa": {"days": []}, "pdf": "2026-08-26"}) == "activa"
        assert rp.tiene_rutina({"activa": None, "pdf": ""}) is True
        assert rp.tiene_rutina(None) is False

    def test_opcional_no_es_incluida(self):
        rp = self._core()
        catalogo = {
            "nivel2": {"habilitaciones": {"rutina": "personalizada"}},
            "nivel1": {"habilitaciones": {"rutina": "del_mes"}},
            "bronze": {"habilitaciones": {"rutina": "opcional"}},
            "basica": {"habilitaciones": {"rutina": "ninguna"}},
            "raro": {},
        }
        assert rp.la_lleva_en_su_plan("nivel2", catalogo) is True
        assert rp.la_lleva_en_su_plan("nivel1", catalogo) is True
        assert rp.la_lleva_en_su_plan("NIVEL2 ", catalogo) is True   # mayúsculas y espacios
        assert rp.la_lleva_en_su_plan("bronze", catalogo) is False
        assert rp.la_lleva_en_su_plan("basica", catalogo) is False
        assert rp.la_lleva_en_su_plan("raro", catalogo) is False
        assert rp.la_lleva_en_su_plan(None, catalogo) is False
        assert rp.a_quien_le_falta([
            {"la_lleva_en_su_plan": True, "has_routine": False, "n": 1},
            {"la_lleva_en_su_plan": True, "has_routine": True, "n": 2},
            {"la_lleva_en_su_plan": False, "has_routine": False, "n": 3},
        ]) == [{"la_lleva_en_su_plan": True, "has_routine": False, "n": 1}]
