# -*- coding: utf-8 -*-
"""
Bloque 13 del doc de Jesus del 23-08 («La app - todo lo que esta mal»): el panel de admin.

    P61. Un entrenador NO puede borrar el catalogo GLOBAL (alimentos, menus, plantillas
         de rutina, suplementos): 403 con frase humana. El admin si puede. Crear y
         editar siguen abiertos al equipo, y lo de SUS clientes tambien.
    P62. El dinero no viaja a un entrenador: dashboard-stats sin mrr/total_revenue y
         upcoming-payments cerrado (403).
    P63. Los activos del dashboard se cuentan con el criterio del servidor (acceso
         vigente), el mismo de la lista de Clientes; los caducados van aparte y el
         total cuadra con sus partes.
    P64. «Sin entrenador» del panel de Operaciones cuenta solo a los clientes cuyo plan
         SI lleva entrenador (habilitaciones.acompanamiento distinto de solo_app).

Todo va contra la API viva, al estilo de la casa. Los tests de borrado CREAN su propio
recurso y lo borran: no se toca ningun dato real del catalogo.
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"

# El backend de desarrollo corre con --reload: al guardar un fichero se reinicia y
# rechaza conexiones unos segundos. Sin reintento saldrian rojos que no son del producto.
REINTENTOS = 20

FRASE_BORRADO = "Esto solo puede borrarlo el administrador"


def pedir(metodo, ruta, **kw):
    fallo = None
    for _ in range(REINTENTOS):
        try:
            return requests.request(metodo, f"{API}{ruta}", timeout=120, **kw)
        except requests.RequestException as e:
            fallo = e
            time.sleep(2)
    raise AssertionError(f"El backend no responde en {ruta}: {fallo}")


def json_ok(respuesta, ruta):
    assert respuesta.status_code == 200, f"{ruta} devolvio {respuesta.status_code}: {respuesta.text[:200]}"
    return respuesta.json()


def entrar(email, claves, quien):
    """Entra probando las claves dadas en orden (las cuentas de prueba han cambiado de
    clave entre tandas de QA). Si ninguna vale, se salta la seccion con el motivo."""
    for clave in claves:
        r = pedir("post", "/auth/login", json={"email": email, "password": clave})
        if r.status_code == 200:
            d = r.json()
            return {"Authorization": "Bearer " + (d.get("access_token") or d.get("token"))}
    pytest.skip(f"No se puede entrar como {quien} ({email})")


@pytest.fixture(scope="module")
def cab_admin():
    return entrar(os.environ.get("TEST_ADMIN_EMAIL", "francisco@test.com"),
                  [os.environ.get("TEST_ADMIN_PASSWORD", "demo123")], "admin")


@pytest.fixture(scope="module")
def cab_entrenador():
    """Un usuario con rol trainer de verdad: el candado distingue admin de trainer."""
    email = os.environ.get("TEST_TRAINER_EMAIL", "coach.prueba@test.com")
    claves = [os.environ.get("TEST_TRAINER_PASSWORD")] if os.environ.get("TEST_TRAINER_PASSWORD") \
        else ["QaPrueba2026!", "demo123"]
    return entrar(email, claves, "entrenador")


# ---------------------------------------------------------------------------
# P61 - el catalogo global no lo borra un entrenador
# ---------------------------------------------------------------------------

def borrado_negado(r):
    """El candado del catalogo: 403 y la frase humana, no un error tecnico."""
    assert r.status_code == 403, f"se esperaba 403 y llego {r.status_code}: {r.text[:200]}"
    assert FRASE_BORRADO in (r.json().get("detail") or ""), (
        f"el 403 no lleva la frase humana: {r.text[:200]}")


def test_alimento_global_no_lo_borra_el_trainer_y_el_admin_si(cab_admin, cab_entrenador):
    """Ciclo completo con un alimento DE PRUEBA propio: crear (admin), intentar borrar
    (trainer, 403) y borrar de verdad (admin, 200). No se toca ningun alimento real."""
    creado = json_ok(pedir("post", "/admin/foods", headers=cab_admin, json={
        "nombre": f"TEST candado P61 {uuid.uuid4().hex[:8]}",
        "categorias": "YA", "proteinas": 10.0, "hidratos": 1.0, "grasas": 1.0,
    }), "/admin/foods")
    food_id = creado["food_id"]
    try:
        borrado_negado(pedir("delete", f"/admin/foods/{food_id}", headers=cab_entrenador))
        # Sigue existiendo: el 403 no puede haber borrado nada por el camino.
        r = pedir("put", f"/admin/foods/{food_id}", headers=cab_admin, json={})
        assert r.status_code == 200, "el alimento de prueba desaparecio tras el 403 del trainer"
    finally:
        r = pedir("delete", f"/admin/foods/{food_id}", headers=cab_admin)
        assert r.status_code == 200, f"el admin no pudo borrar su alimento de prueba: {r.status_code}"


def test_el_trainer_sigue_creando_y_editando_alimentos(cab_admin, cab_entrenador):
    """El candado es SOLO del borrado: el alta y la edicion del catalogo siguen siendo
    trabajo del equipo entero (asi estaba y asi se queda)."""
    creado = json_ok(pedir("post", "/admin/foods", headers=cab_entrenador, json={
        "nombre": f"TEST candado P61 edita {uuid.uuid4().hex[:8]}",
        "categorias": "YA", "proteinas": 20.0, "hidratos": 0.0, "grasas": 2.0,
    }), "/admin/foods (trainer)")
    food_id = creado["food_id"]
    try:
        r = pedir("put", f"/admin/foods/{food_id}", headers=cab_entrenador,
                  json={"proteinas": 21.0})
        assert r.status_code == 200, f"el trainer ya no puede editar un alimento: {r.status_code}"
    finally:
        r = pedir("delete", f"/admin/foods/{food_id}", headers=cab_admin)
        assert r.status_code == 200, "el admin no pudo limpiar el alimento de prueba"


def test_menu_del_recetario_no_lo_borra_el_trainer_y_el_admin_si(cab_admin, cab_entrenador):
    menu = json_ok(pedir("post", "/admin/menu-templates", headers=cab_admin, json={
        "nombre": f"TEST candado P61 {uuid.uuid4().hex[:8]}",
        "momento": "comida",
        "items": [{"rol": "proteina", "buscar": "pollo", "proporcion": 1}],
    }), "/admin/menu-templates")
    menu_id = menu["id"]
    try:
        borrado_negado(pedir("delete", f"/admin/menu-templates/{menu_id}", headers=cab_entrenador))
    finally:
        r = pedir("delete", f"/admin/menu-templates/{menu_id}", headers=cab_admin)
        assert r.status_code == 200, f"el admin no pudo borrar su menu de prueba: {r.status_code}"


def test_menu_de_la_biblioteca_no_lo_borra_el_trainer(cab_admin, cab_entrenador):
    """La biblioteca (meal_library) no tiene alta por API, asi que no se crea nada: se
    comprueba que el candado salta ANTES de mirar la base (403 con un id inventado,
    donde el admin recibe 404). Asi el test no puede borrar un menu real ni queriendo."""
    borrado_negado(pedir("delete", "/admin/biblioteca-menus/no-existe-p61", headers=cab_entrenador))
    r = pedir("delete", "/admin/biblioteca-menus/no-existe-p61", headers=cab_admin)
    assert r.status_code == 404, f"al admin le tendria que decir 404 (no existe): {r.status_code}"


def test_plantilla_de_rutina_no_la_borra_el_trainer_y_el_admin_si(cab_admin, cab_entrenador):
    rutina = json_ok(pedir("post", "/admin/routines/biblioteca", headers=cab_admin, json={
        "nombre": f"TEST candado P61 {uuid.uuid4().hex[:8]}",
        "days": [{"day": "Lunes", "exercises": [{"name": "Sentadilla", "sets": 3, "reps": "10"}]}],
    }), "/admin/routines/biblioteca")
    rutina_id = rutina["id"]
    try:
        borrado_negado(pedir("delete", f"/admin/routines/biblioteca/{rutina_id}",
                             headers=cab_entrenador))
    finally:
        r = pedir("delete", f"/admin/routines/biblioteca/{rutina_id}", headers=cab_admin)
        assert r.status_code == 200, f"el admin no pudo borrar su rutina de prueba: {r.status_code}"


def test_suplemento_del_catalogo_no_lo_apaga_el_trainer_ni_por_el_put(cab_admin, cab_entrenador):
    """El DELETE de suplementos es un apagado (activo=false) igual de destructivo, y el
    PUT acepta `activo`: se cierran las DOS puertas. Editar sin apagar sigue abierto."""
    item = {
        "titulo": f"TEST candado P61 {uuid.uuid4().hex[:8]}",
        "cuando": "nunca, es de prueba", "cuanto": "0 g",
    }
    creado = json_ok(pedir("post", "/admin/supplements/catalog", headers=cab_admin, json=item),
                     "/admin/supplements/catalog")
    item_id = creado["id"]
    try:
        # La puerta principal: el DELETE.
        borrado_negado(pedir("delete", f"/admin/supplements/catalog/{item_id}",
                             headers=cab_entrenador))
        # La puerta de atras: el PUT con activo=false.
        r = pedir("put", f"/admin/supplements/catalog/{item_id}", headers=cab_entrenador,
                  json={**item, "id": item_id, "activo": False})
        borrado_negado(r)
        # Editar sin apagar sigue siendo del equipo.
        r = pedir("put", f"/admin/supplements/catalog/{item_id}", headers=cab_entrenador,
                  json={**item, "id": item_id, "cuanto": "0 g (editado)", "activo": True})
        assert r.status_code == 200, f"el trainer ya no puede editar el catalogo: {r.status_code}"
    finally:
        r = pedir("delete", f"/admin/supplements/catalog/{item_id}", headers=cab_admin)
        assert r.status_code == 200, "el admin no pudo apagar su suplemento de prueba"


def test_el_trainer_sigue_pautando_suplementos_a_un_cliente(cab_entrenador):
    """Lo de SUS clientes sigue abierto: proponer un protocolo (no escribe nada) tiene
    que contestarle al trainer, no darle un 403."""
    lista = json_ok(pedir("get", "/admin/clients", headers=cab_entrenador), "/admin/clients")
    fila = next((c for c in lista if c.get("id")), None)
    if not fila:
        pytest.skip("no hay clientes en la base de dev")
    r = pedir("post", f"/admin/supplements/suggest?client_id={fila['id']}", headers=cab_entrenador)
    assert r.status_code == 200, (
        f"el candado del catalogo se ha llevado por delante el trabajo con clientes: {r.status_code}")


# ---------------------------------------------------------------------------
# P62 - el dinero no viaja a un entrenador
# ---------------------------------------------------------------------------

def test_el_dashboard_del_trainer_no_trae_dinero(cab_entrenador):
    stats = json_ok(pedir("get", "/admin/dashboard-stats", headers=cab_entrenador),
                    "/admin/dashboard-stats (trainer)")
    con_dinero = [k for k in ("mrr", "total_revenue") if k in stats]
    assert not con_dinero, f"al trainer le siguen llegando campos de dinero: {con_dinero}"
    # Y el resto del panel le sigue funcionando: no era capar el panel, era capar el dinero.
    assert "active_clients" in stats and "semaforo" in stats


def test_el_dashboard_del_admin_si_trae_dinero(cab_admin):
    stats = json_ok(pedir("get", "/admin/dashboard-stats", headers=cab_admin),
                    "/admin/dashboard-stats (admin)")
    assert "mrr" in stats and "total_revenue" in stats, "el admin se ha quedado sin sus numeros"


def test_los_proximos_cobros_estan_cerrados_al_trainer(cab_entrenador):
    r = pedir("get", "/admin/upcoming-payments", headers=cab_entrenador)
    assert r.status_code == 403, (
        f"el trainer sigue viendo los proximos cobros con importes: {r.status_code}")


def test_el_dashboard_legacy_tampoco_le_da_dinero_al_trainer(cab_entrenador):
    stats = json_ok(pedir("get", "/admin/dashboard", headers=cab_entrenador),
                    "/admin/dashboard (trainer)")
    con_dinero = [k for k in ("mrr", "total_revenue") if k in stats]
    assert not con_dinero, f"el endpoint legacy le sigue dando dinero al trainer: {con_dinero}"


# ---------------------------------------------------------------------------
# P63 - los activos del dashboard, con el criterio del servidor
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def panel(cab_admin):
    """Contadores y tabla sin que la base se mueva por el medio (mismo truco que en
    test_casos_L_panel: si el total cambia entre lecturas, se reintenta)."""
    for _ in range(4):
        antes = json_ok(pedir("get", "/admin/dashboard-stats", headers=cab_admin), "/admin/dashboard-stats")
        lista = json_ok(pedir("get", "/admin/clients", headers=cab_admin), "/admin/clients")
        despues = json_ok(pedir("get", "/admin/dashboard-stats", headers=cab_admin), "/admin/dashboard-stats")
        if antes["total_clients"] == despues["total_clients"]:
            return antes, lista
    pytest.skip("la base se esta moviendo (otra tanda creando clientes): no se puede comparar")


def test_los_activos_del_dashboard_son_los_de_la_lista(panel):
    """El numero del KPI «Activos» tiene que ser el de la pestaña «Activos» de Clientes:
    acceso vigente segun el servidor, no la etiqueta status."""
    stats, lista = panel
    con_acceso = [c for c in lista
                  if (c.get("acceso") or {}).get("activo") and not c.get("es_tu_ficha")]
    assert stats["active_clients"] == len(con_acceso), (
        f"el dashboard dice {stats['active_clients']} activos y la lista tiene "
        f"{len(con_acceso)} con acceso")


def test_los_caducados_van_aparte_y_el_total_cuadra(panel):
    stats, lista = panel
    assert "caducados_clients" in stats, "el dashboard no separa a los caducados"
    etiqueta_activo_sin_acceso = [
        c for c in lista
        if c.get("status") == "activo" and not (c.get("acceso") or {}).get("activo")
        and not c.get("es_tu_ficha")]
    assert stats["caducados_clients"] == len(etiqueta_activo_sin_acceso), (
        f"el dashboard dice {stats['caducados_clients']} caducados y en la lista hay "
        f"{len(etiqueta_activo_sin_acceso)} marcados activo sin acceso")
    partes = (stats["active_clients"] + stats["caducados_clients"]
              + stats["inactive_clients"] + stats["otros_clients"])
    assert stats["total_clients"] == partes, (
        f"{stats['total_clients']} totales frente a activos + caducados + bajas + otros = {partes}")


def test_el_mrr_no_cuenta_a_los_caducados(panel):
    """El MRR sale de los activos CON ACCESO: la suma de la barra de planes (que se
    calcula sobre los mismos) tiene que dar el numero de activos, no el de etiquetas."""
    stats, _ = panel
    assert sum(stats["plans"].values()) == stats["active_clients"], (
        "la barra de planes (la base del MRR) no reparte exactamente a los activos con acceso")


# ---------------------------------------------------------------------------
# P64 - «sin entrenador» filtrado por lo que el plan incluye
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def catalogo(cab_admin):
    return json_ok(pedir("get", "/plans", headers=cab_admin), "/plans")


def lleva_entrenador(catalogo, code):
    hab = (catalogo.get(code) or {}).get("habilitaciones") or {}
    return (hab.get("acompanamiento") or "solo_app") != "solo_app"


def test_sin_entrenador_solo_cuenta_planes_con_entrenador(cab_admin, catalogo):
    ops = json_ok(pedir("get", "/admin/paneles/operaciones", headers=cab_admin),
                  "/admin/paneles/operaciones")
    bloque = ops.get("sin_entrenador") or {}
    colados = [f for f in (bloque.get("clientes") or [])
               if not lleva_entrenador(catalogo, f.get("plan"))]
    assert not colados, (
        f"{len(colados)} clientes cuyo plan NO lleva entrenador siguen contando como "
        f"«sin entrenador»: {[(f['name'], f['plan']) for f in colados[:8]]}")
    assert bloque.get("n") == len(bloque.get("clientes") or []), (
        "el contador del bloque no es el tamaño de su lista")


def test_un_cliente_de_plan_solo_app_sin_coach_no_sale_en_la_lista(panel, cab_admin, catalogo):
    """La otra mitad del filtro: existe gente activa sin coach en planes solo_app (ELM,
    Mantenimiento...) y NINGUNO de ellos aparece en «sin entrenador»."""
    _, lista = panel
    solo_app_sin_coach = [
        c for c in lista
        if c.get("status") == "activo" and not c.get("trainer_id") and not c.get("es_tu_ficha")
        and (c.get("plan") or "").lower() in catalogo
        and not lleva_entrenador(catalogo, (c.get("plan") or "").lower())]
    if not solo_app_sin_coach:
        pytest.skip("en esta base no hay activos sin coach con plan solo_app que comprobar")
    ops = json_ok(pedir("get", "/admin/paneles/operaciones", headers=cab_admin),
                  "/admin/paneles/operaciones")
    en_lista = {f["client_id"] for f in (ops.get("sin_entrenador") or {}).get("clientes") or []}
    colados = [c["id"] for c in solo_app_sin_coach if c["id"] in en_lista]
    assert not colados, f"{len(colados)} clientes de planes solo_app se cuelan en la lista"


def test_el_panel_del_entrenador_cuenta_sin_asignar_con_el_mismo_criterio(cab_admin, catalogo):
    """`sin_asignar` del panel del entrenador es el mismo numero que el bloque de
    Operaciones: los dos filtran por plan (P64) y no pueden contradecirse en pantalla."""
    ent = json_ok(pedir("get", "/admin/paneles/entrenador", headers=cab_admin),
                  "/admin/paneles/entrenador")
    ops = json_ok(pedir("get", "/admin/paneles/operaciones", headers=cab_admin),
                  "/admin/paneles/operaciones")
    assert ent.get("sin_asignar") == (ops.get("sin_entrenador") or {}).get("n"), (
        f"el panel del entrenador dice {ent.get('sin_asignar')} sin asignar y Operaciones "
        f"{(ops.get('sin_entrenador') or {}).get('n')}")
