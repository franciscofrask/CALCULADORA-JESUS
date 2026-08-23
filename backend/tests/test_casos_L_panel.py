# -*- coding: utf-8 -*-
"""
Seccion L, "EL PANEL DEL EQUIPO", de la lista de 85 casos de prueba que entrego Jesus el
12-08-2026.

    77. [CRITICO] Los contadores del panel y la tabla de clientes dan el mismo numero, y
        ningun contador es mayor que el total.
    78. [CRITICO] Pulsar la fila de un cliente abre su ficha.
    79. [CRITICO] No hay clientes de prueba (TEST_, "Caso Cliente") mezclados con los reales.
    80. [CRITICO] "Esta semana te tocan estos": clientes reales, ordenados por los que
        llevan mas sin que les toquen los macros.
    81. Ninguna fecha imposible en el panel.
    82. [CRITICO] Guardar un ajuste desde la ficha crea UN ajuste y UNA notificacion.
    83. [CRITICO] El entrenador ve los clientes pero no entra en la pantalla de usuarios.
    84. Los menus del panel y los del cliente: la diferencia se puede explicar.
    85. [CRITICO] La bandeja trae las conversaciones de todo el equipo y marca las que
        esperan respuesta.

Todo va contra la API viva, que es donde se puede comparar un contador con la lista que
resume. El caso 82 ESCRIBE en el cliente de prueba y lo deja como estaba (ver el propio
test).
"""
import os
import re
import time
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"

# El backend de desarrollo corre con `--reload`: cada vez que alguien guarda un fichero se
# reinicia y rechaza la conexion un par de segundos. Sin reintento saldrian rojos que no son
# del producto sino del servidor levantandose.
REINTENTOS = 20

HOY = datetime.now(timezone.utc).date()


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


def entrar(email, clave, quien):
    r = pedir("post", "/auth/login", json={"email": email, "password": clave})
    if r.status_code != 200:
        pytest.skip(f"No se puede entrar como {quien} ({email}): {r.status_code}")
    d = r.json()
    return {"Authorization": "Bearer " + (d.get("access_token") or d.get("token"))}


# Las cabeceras se sacan aqui y no de las fixtures del conftest a proposito: aquellas
# comprueban el servidor UNA vez y, si justo pillan un reinicio, se saltan la seccion
# entera. Un caso critico saltado se lee como un caso que no ha fallado.
@pytest.fixture(scope="module")
def cab_admin():
    return entrar(os.environ.get("TEST_ADMIN_EMAIL", "francisco@test.com"),
                  os.environ.get("TEST_ADMIN_PASSWORD", "demo123"), "admin")


@pytest.fixture(scope="module")
def cab_entrenador():
    """Un usuario con rol `trainer`, que no es lo mismo que un admin (caso 83)."""
    return entrar(os.environ.get("TEST_TRAINER_EMAIL", "coach.prueba@test.com"),
                  os.environ.get("TEST_TRAINER_PASSWORD", "demo123"), "entrenador")


@pytest.fixture(scope="module")
def cab_cliente():
    return entrar(os.environ.get("TEST_CLIENT_EMAIL", "clientedemo@test.com"),
                  os.environ.get("TEST_CLIENT_PASSWORD", "demo123"), "cliente")


@pytest.fixture(scope="module")
def panel(cab_admin):
    """Los contadores y la tabla, leidos sin que la base se mueva por el medio.

    Hay mas gente probando contra esta misma base y se crean y borran clientes de prueba
    todo el rato: si el total cambia entre las dos llamadas, la comparacion del caso 77
    saldria roja por una carrera y no por el panel. Se leen los contadores, la tabla y otra
    vez los contadores; si no coinciden, se repite.
    """
    for _ in range(4):
        antes = json_ok(pedir("get", "/admin/dashboard-stats", headers=cab_admin), "/admin/dashboard-stats")
        lista = json_ok(pedir("get", "/admin/clients", headers=cab_admin), "/admin/clients")
        despues = json_ok(pedir("get", "/admin/dashboard-stats", headers=cab_admin), "/admin/dashboard-stats")
        if antes["total_clients"] == despues["total_clients"]:
            return antes, lista
    pytest.skip("la base se esta moviendo (otra tanda creando clientes): no se puede comparar")


@pytest.fixture(scope="module")
def semana(cab_admin):
    return json_ok(pedir("get", "/admin/todo-semana", headers=cab_admin), "/admin/todo-semana")


def nombre_de(fila):
    return (fila.get("user") or {}).get("name") or fila.get("name") or ""


# ---------------------------------------------------------------------------
# CASO 77 [CRITICO] - los contadores contra la tabla
# ---------------------------------------------------------------------------

def test_el_total_del_panel_es_el_de_la_tabla_de_clientes(panel):
    stats, lista = panel
    # Los "registro_incompleto" son usuarios sin perfil y solo salen si se piden aparte,
    # asi que no deberian aparecer, pero se descuentan por si acaso.
    #
    # Y `es_tu_ficha`: desde el 13-08 cada uno del equipo ve SU propia ficha en la tabla
    # (Francisco: «usan la app de las dos formas»), pero el equipo no es negocio y los
    # contadores siguen sin contarla. Es UNA fila y viene marcada justo para esto.
    filas = [c for c in lista
             if c.get("status") != "registro_incompleto" and not c.get("es_tu_ficha")]
    assert stats["total_clients"] == len(filas), (
        f"el panel dice {stats['total_clients']} clientes y la tabla trae {len(filas)}")


def test_los_activos_se_cuentan_igual_en_las_dos_pantallas(panel):
    """Desde P63 (doc 23-08) el criterio unico es el del servidor: activo = con acceso
    vigente (`acceso.activo`, lo que mira la pestaña «Activos» de Clientes), no la
    etiqueta `status`, que contaba a los caducados como activos e inflaba el MRR."""
    stats, lista = panel
    activos = [c for c in lista
               if (c.get("acceso") or {}).get("activo") and not c.get("es_tu_ficha")]
    assert stats["active_clients"] == len(activos), (
        f"el panel dice {stats['active_clients']} activos y en la tabla hay {len(activos)}")


def test_el_total_cuadra_con_sus_partes(panel):
    """«"0 bajas" con 188 totales y 184 activos: faltan cuatro por algun sitio».

    Desde P63 hay un cajon mas y siguen siendo excluyentes: activos (con acceso) +
    caducados (etiqueta «activo» sin acceso) + bajas + otros = total."""
    stats, _ = panel
    partes = (stats["active_clients"] + stats.get("caducados_clients", 0)
              + stats["inactive_clients"] + stats["otros_clients"])
    assert stats["total_clients"] == partes, (
        f"{stats['total_clients']} totales frente a {stats['active_clients']} activos + "
        f"{stats.get('caducados_clients', 0)} caducados + "
        f"{stats['inactive_clients']} bajas + {stats['otros_clients']} otros = {partes}")


def test_ningun_contador_del_panel_es_mayor_que_el_total(panel, semana):
    """«Sin contacto: 234» sobre 228 clientes (Jesus, 11-08)."""
    stats, _ = panel
    total = stats["total_clients"]
    assert stats["at_risk_clients"] <= stats["active_clients"], (
        f"hay que mirarlos: {stats['at_risk_clients']} sobre {stats['active_clients']} activos")
    for nombre, valor in semana.items():
        if isinstance(valor, list):
            assert len(valor) <= total, f"«{nombre}» trae {len(valor)} clientes de {total}"


def test_el_semaforo_reparte_exactamente_a_los_activos(panel):
    """Cada celda cuenta a TODOS los activos una vez: si no, el reparto no es un reparto."""
    stats, _ = panel
    for celda, reparto in (stats.get("semaforo") or {}).items():
        assert sum(reparto.values()) == stats["active_clients"], (
            f"la celda «{celda}» reparte {sum(reparto.values())} clientes y hay "
            f"{stats['active_clients']} activos")


# ---------------------------------------------------------------------------
# CASO 78 [CRITICO] - pulsar la fila abre la ficha
# ---------------------------------------------------------------------------

def test_la_ficha_abre_para_cualquier_fila_de_la_tabla(panel, cab_admin):
    """Se prueban las primeras y unas cuantas repartidas, no las 235: cada ficha trae
    reportes, dietas, historial y suplementos, y abrirlas todas tarda minutos."""
    _, lista = panel
    filas = [c for c in lista if c.get("id")]
    muestra = filas[:5] + filas[len(filas) // 2:len(filas) // 2 + 5] + filas[-5:]
    rotas = []
    for fila in muestra:
        r = pedir("get", f"/admin/clients/{fila['id']}", headers=cab_admin)
        if r.status_code != 200:
            rotas.append((nombre_de(fila), fila["id"], r.status_code))
            continue
        ficha = r.json()
        if (ficha.get("profile") or {}).get("id") != fila["id"]:
            rotas.append((nombre_de(fila), fila["id"], "abre la ficha de otro"))
    assert not rotas, f"fichas que no abren: {rotas}"


def test_la_ficha_trae_las_pestanas_que_pinta_el_panel(panel, cab_admin):
    _, lista = panel
    fila = next(c for c in lista if c.get("id"))
    ficha = json_ok(pedir("get", f"/admin/clients/{fila['id']}", headers=cab_admin), "ficha")
    assert set(ficha) >= {"profile", "user", "reports", "payments", "messages",
                          "macro_history", "nutrition_stats"}


@pytest.mark.skip(reason="visual: que la fila entera sea pulsable y navegue a la ficha se "
                         "comprueba en el navegador. Aqui se fija que la ficha existe y "
                         "responde para cualquier fila de la tabla.")
def test_la_fila_entera_es_pulsable():
    pass


# ---------------------------------------------------------------------------
# CASO 79 [CRITICO] - ningun cliente de prueba mezclado con los reales
# ---------------------------------------------------------------------------

# Los nombres que deja la maquinaria de pruebas. Los dos primeros los nombro Jesus; los
# otros son los del simulador (`backend/_simulacion`) y los de las cuentas de test.
PINTA_DE_PRUEBA = re.compile(
    r"(TEST_|Caso Cliente|Caos Cliente|Caos Trainer|@jg12-sim\.com|jg12-sim)", re.IGNORECASE)


def test_en_la_lista_de_clientes_no_hay_clientes_de_prueba(panel):
    _, lista = panel
    colados = []
    for fila in lista:
        u = fila.get("user") or {}
        if PINTA_DE_PRUEBA.search(f"{u.get('name') or ''} {u.get('email') or ''}"):
            colados.append(u.get("name") or u.get("email"))
    assert not colados, (
        f"{len(colados)} clientes de prueba mezclados con los reales, por ejemplo "
        f"{colados[:8]}. Los dejan las tandas de tests (leads convertidos a cliente) y el "
        "simulador, y cuentan en los totales, en el MRR y en el semaforo del panel")


# ---------------------------------------------------------------------------
# CASO 80 [CRITICO] - "esta semana te tocan estos"
# ---------------------------------------------------------------------------

def test_en_los_que_te_tocan_no_hay_clientes_de_prueba(semana):
    colados = [x["name"] for x in semana["te_tocan"] if PINTA_DE_PRUEBA.search(x.get("name") or "")]
    assert not colados, (
        f"{len(colados)} clientes de prueba en «esta semana te tocan», y ademas arriba del "
        f"todo porque nunca se les ajusto nada: {colados[:8]}")


def test_los_que_te_tocan_van_por_lo_que_llevan_sin_que_les_ajusten(semana):
    """Primero el que nunca ha tenido un ajuste, y despues de mas abandonado a menos."""
    orden = [(0 if x["nunca_ajustado"] else 1, -(x["dias_sin_ajuste"] or 0))
             for x in semana["te_tocan"]]
    assert orden == sorted(orden), "la lista no esta ordenada por lo que llevan sin ajuste"


def test_el_que_nunca_ha_tenido_ajuste_no_trae_fecha(semana):
    for x in semana["te_tocan"]:
        if x["nunca_ajustado"]:
            assert not x.get("ultimo_ajuste"), (
                f"{x['name']} sale como nunca ajustado y trae fecha {x['ultimo_ajuste']}")


def test_el_ultimo_ajuste_del_panel_es_el_del_historico_del_cliente(semana, cab_admin):
    """La fecha que ordena la lista tiene que ser la del ULTIMO AJUSTE DE VERDAD.

    El panel ordena por `client_profiles.ultimo_ajuste`, que es una copia guardada en el
    cliente para no recorrer el historico de doscientos y pico (core/seguimiento.py). La
    fecha buena de un ajuste es su `effective_date`, que es por la que abre la ficha
    (`macros_por_fecha.ultima_vigente`). Si la copia no es esa fecha, "quien lleva mas sin
    que le toquen los macros" senala a otro.
    """
    con_ajuste = [x for x in semana["te_tocan"] if not x["nunca_ajustado"]][:12]
    if not con_ajuste:
        pytest.skip("no hay clientes con ajustes previos en la lista")
    descuadres = []
    for x in con_ajuste:
        ficha = json_ok(pedir("get", f"/admin/clients/{x['client_id']}", headers=cab_admin), "ficha")
        historico = ficha.get("macro_history") or []
        real = None
        if historico:
            real = historico[0].get("effective_date") or str(historico[0].get("created_at") or "")[:10]
        if str(x["ultimo_ajuste"])[:10] != str(real)[:10]:
            descuadres.append((x["name"], "panel:" + str(x["ultimo_ajuste"]),
                               "historico:" + str(real), f"{len(historico)} ajustes"))
    assert not descuadres, (
        f"{len(descuadres)} de {len(con_ajuste)} clientes mirados tienen en el panel una "
        f"fecha de ultimo ajuste que no esta en su historico: {descuadres[:8]}")


# ---------------------------------------------------------------------------
# CASO 81 - ninguna fecha imposible
# ---------------------------------------------------------------------------

# Un dia planificado por delante es legitimo (el cliente puede montarse la semana), asi
# que "imposible" es lo que no puede ser de nadie: antes de que existiera el metodo o mas
# de un año por delante. Es lo que caza los 2099 y los 1970.
MAS_ANTIGUA = date(2015, 1, 1)
MAS_LEJANA = HOY + timedelta(days=365)


def dia(valor):
    try:
        return date.fromisoformat(str(valor or "")[:10])
    except ValueError:
        return None


def imposible(valor):
    d = dia(valor)
    return d is not None and (d < MAS_ANTIGUA or d > MAS_LEJANA)


def test_ninguna_fecha_imposible_en_la_tabla_de_clientes(panel):
    _, lista = panel
    raras = []
    for fila in lista:
        for campo in ("created_at", "cycle_start", "ultimo_ajuste", "ultimo_reporte"):
            if imposible(fila.get(campo)):
                raras.append((nombre_de(fila), campo, fila.get(campo)))
    assert not raras, f"fechas imposibles en la tabla: {raras[:10]}"


def test_ninguna_fecha_imposible_en_lo_de_esta_semana(semana):
    raras = []
    for nombre, valor in semana.items():
        if not isinstance(valor, list):
            continue
        for fila in valor:
            for campo in ("ultimo_ajuste", "ultimo_reporte"):
                if imposible(fila.get(campo)):
                    raras.append((nombre, fila.get("name"), campo, fila.get(campo)))
    assert not raras, f"fechas imposibles en «por hacer esta semana»: {raras[:10]}"


def test_los_cobros_de_los_proximos_siete_dias_son_de_los_proximos_siete_dias(cab_admin):
    proximos = json_ok(pedir("get", "/admin/upcoming-payments", headers=cab_admin),
                       "/admin/upcoming-payments")
    fuera = []
    for p in proximos["upcoming"]:
        d = dia(p.get("next_payment"))
        if d is None or d < HOY or d > HOY + timedelta(days=8):
            fuera.append((p.get("name"), p.get("next_payment")))
    assert not fuera, f"cobros que no caen en los proximos 7 dias: {fuera[:10]}"


def test_ninguna_fecha_imposible_dentro_de_una_ficha(panel, cab_admin):
    _, lista = panel
    filas = [c for c in lista if c.get("id")]
    raras = []
    for fila in filas[:6]:
        ficha = json_ok(pedir("get", f"/admin/clients/{fila['id']}", headers=cab_admin), "ficha")
        for r in (ficha.get("reports") or []):
            if imposible(r.get("created_at")):
                raras.append((nombre_de(fila), "reporte", r.get("created_at")))
        for m in (ficha.get("macro_history") or []):
            if imposible(m.get("effective_date")):
                raras.append((nombre_de(fila), "ajuste", m.get("effective_date")))
        for d in ((ficha.get("nutrition_stats") or {}).get("diet_dates") or []):
            if imposible(d.get("fecha")):
                raras.append((nombre_de(fila), "dia montado", d.get("fecha")))
    assert not raras, f"fechas imposibles dentro de las fichas: {raras[:10]}"


# ---------------------------------------------------------------------------
# CASO 82 [CRITICO] - guardar un ajuste crea UN ajuste y UNA notificacion
# ---------------------------------------------------------------------------

def test_guardar_un_ajuste_crea_uno_solo_y_avisa_una_vez(cab_admin, cab_cliente):
    """ESTE TEST ESCRIBE. Se hace sobre el cliente demo y se deshace al terminar.

    Se guarda con los MISMOS macros que ya tiene (no le cambia los numeros a nadie) y con
    una fecha de vigencia que ese cliente no tenga usada, para poder reconocer la fila. Al
    final se borra la fila por el mismo camino que la borraria el coach. La notificacion no
    se puede borrar por API: se queda una, marcada con el texto de la nota.
    """
    perfil = json_ok(pedir("get", "/clients/profile", headers=cab_cliente), "/clients/profile")
    cid = perfil["id"]
    ficha = json_ok(pedir("get", f"/admin/clients/{cid}", headers=cab_admin), "ficha")
    historico = ficha.get("macro_history") or []
    usadas = {h.get("effective_date") for h in historico}

    # Una fecha libre y lo mas reciente posible: cuanto menos atras, menos dias de dieta
    # quedan bajo un ajuste que no existia (y que ademas lleva los macros de hoy).
    fecha = None
    for atras in range(1, 60):
        candidata = (HOY - timedelta(days=atras)).isoformat()
        if candidata not in usadas:
            fecha = candidata
            break
    assert fecha, "el cliente de prueba tiene ajustes en los ultimos 60 dias sin un hueco"

    actual = ficha["profile"]
    marca = f"Ajuste de prueba automatica (caso 82) {uuid.uuid4().hex[:8]}"

    def bloque(m, con_grasa=True):
        m = m or {}
        salida = {"protein": float(m.get("protein") or m.get("proteinas") or 0),
                  "carbs": float(m.get("carbs") or m.get("hidratos") or 0)}
        if con_grasa:
            salida["fat"] = float(m.get("fat") or m.get("grasas") or 0)
        return salida

    cuerpo = {"training": bloque(actual.get("macros_training")),
              "rest": bloque(actual.get("macros_rest")),
              "effective_date": fecha, "note": marca}
    if actual.get("macros_periworkout"):
        cuerpo["peri"] = bloque(actual["macros_periworkout"], con_grasa=False)

    creado = None
    try:
        r = pedir("put", f"/admin/clients/{cid}/macros", headers=cab_admin, json=cuerpo)
        assert r.status_code == 200, f"no se pudo guardar el ajuste: {r.status_code} {r.text[:200]}"

        despues = json_ok(pedir("get", f"/admin/clients/{cid}", headers=cab_admin), "ficha")
        nuevas = [h for h in (despues.get("macro_history") or []) if h.get("effective_date") == fecha]
        assert len(nuevas) == 1, (
            f"un guardado y {len(nuevas)} filas en el historial para el {fecha}")
        creado = nuevas[0].get("id")
        assert len(despues.get("macro_history") or []) == len(historico) + 1, (
            "el historial no crecio en exactamente una fila")

        avisos = json_ok(pedir("get", "/notifications", headers=cab_cliente), "/notifications")
        mios = [n for n in avisos["notifications"] if (n.get("body") or "") == marca]
        assert len(mios) == 1, (
            f"un ajuste guardado y {len(mios)} notificaciones con la misma nota")
        assert mios[0].get("type") == "macros"
        assert mios[0].get("link"), "el aviso no lleva a ninguna parte"
    finally:
        if creado:
            borrado = pedir("delete", f"/admin/clients/{cid}/macro-history/{creado}",
                            headers=cab_admin)
            assert borrado.status_code == 200, (
                f"OJO: no se pudo borrar el ajuste de prueba {creado} del cliente {cid}")


# ---------------------------------------------------------------------------
# CASO 83 [CRITICO] - el entrenador ve clientes, no usuarios
# ---------------------------------------------------------------------------

def test_el_entrenador_no_entra_en_la_pantalla_de_usuarios(cab_entrenador):
    """La pestaña Usuarios es solo del admin: desde ahi se cambian roles y contraseñas."""
    r = pedir("get", "/admin/users", headers=cab_entrenador)
    assert r.status_code == 403, f"el entrenador entra en /admin/users: {r.status_code}"


def test_el_entrenador_tampoco_puede_tocar_a_un_usuario(cab_entrenador):
    """Con un id inventado a proposito: el cerrojo tiene que saltar ANTES de buscar a
    nadie, y asi el test no puede renombrar a un usuario de verdad si el cerrojo falla."""
    r = pedir("put", f"/admin/users/{uuid.uuid4()}", headers=cab_entrenador,
              json={"name": "no deberia poder"})
    assert r.status_code == 403, f"el entrenador edita usuarios: {r.status_code}"


def test_el_entrenador_si_ve_el_panel(cab_entrenador):
    r = pedir("get", "/admin/dashboard-stats", headers=cab_entrenador)
    assert r.status_code == 200, f"el entrenador no ve el panel: {r.status_code}"


def test_el_entrenador_ve_todos_los_clientes(cab_entrenador, cab_admin):
    """Caso 83 tal y como lo escribio Jesus: "ve todos los clientes".

    YA NO ES UNA CONTRADICCION, ES UNA DECISION TOMADA. Hubo dos: la del 21-07 («ven y
    gestionan a todos») y la del 06-08, que la revertia (cada coach los suyos y los libres).
    Este test se dejo en rojo a proposito, con la contradiccion a la vista, para que la
    desempatara Jesus. Lo hizo el 13-08-2026: *«los entrenadores ven a todos los clientes.
    Es lo que decidi el 21 de julio»*, y el motivo, que es lo que hay que recordar antes de
    "arreglarlo" de vuelta: *«con 177 clientes y el equipo que tienes, separas: el dia que
    uno se va de vacaciones, los suyos se quedan sin nadie que los mire»*.

    Contradice a proposito el hallazgo de la auditoria de seguridad sobre el acceso del
    trainer a clientes ajenos: no es un fallo, es como quiere que trabaje su equipo. Lo que
    sigue cerrado -- y lo fijan los tres tests de aqui arriba -- es la pantalla de Usuarios,
    que es de admin.
    """
    del_admin = json_ok(pedir("get", "/admin/clients", headers=cab_admin), "/admin/clients")
    del_coach = json_ok(pedir("get", "/admin/clients", headers=cab_entrenador), "/admin/clients")
    # Sin las fichas propias: cada uno del equipo ve la SUYA y no la de los demas (13-08),
    # asi que la del admin sale en su lista y no en la del coach sin que eso sea un cliente
    # escondido. Es la unica diferencia legitima entre las dos listas.
    ids_admin = {c["id"] for c in del_admin if c.get("id") and not c.get("es_tu_ficha")}
    ocultos = ids_admin - {c["id"] for c in del_coach if c.get("id")}
    assert not ocultos, (
        f"el entrenador ve {len(del_coach)} clientes y el admin {len(del_admin)}: "
        f"{len(ocultos)} son de otro coach y no le salen ni en la lista")


# ---------------------------------------------------------------------------
# CASO 84 - los menus del panel y los del cliente
# ---------------------------------------------------------------------------

def test_el_panel_dice_cuantas_plantillas_tiene_y_las_trae(cab_admin):
    menus = json_ok(pedir("get", "/admin/menu-templates", headers=cab_admin), "/admin/menu-templates")
    assert menus["total"] == len(menus["templates"]), (
        f"el panel dice {menus['total']} menus y devuelve {len(menus['templates'])}")


def test_al_cliente_se_le_dice_cuantos_cuadran_y_cuantos_se_le_ensenan(cab_cliente):
    """La diferencia entre las dos pantallas es explicable porque la del cliente lo dice.

    El panel enseña el RECETARIO (`menu_templates`, los menus escritos). Al cliente se le
    ofrecen los de la BIBLIOTECA que cuadran con el objetivo de esa comida, y la pantalla
    trae `total` (cuantos cuadran) aparte de la lista que se pinta (`limit`). Sin ese
    `total`, "veo 10 y en el panel hay 159" no se puede explicar.
    """
    r = pedir("post", "/calculator/library-menus", headers=cab_cliente,
              json={"mealKey": "comida1", "tipo_comida": "Comida 1", "margen": 8,
                    "limit": 10, "macros_objetivo": {"P": 40, "H": 60, "G": 15}})
    datos = json_ok(r, "/calculator/library-menus")
    assert "total" in datos, "la pantalla del cliente no dice cuantos menus cuadran"
    assert len(datos["menus"]) <= datos["total"], (
        f"enseña {len(datos['menus'])} menus y dice que cuadran {datos['total']}")
    assert len(datos["menus"]) <= 10, "no respeta el limite que se le pide"


# ---------------------------------------------------------------------------
# CASO 85 [CRITICO] - la bandeja del equipo
# ---------------------------------------------------------------------------

def test_la_bandeja_es_la_del_equipo_y_no_la_de_cada_uno(cab_admin, cab_entrenador):
    """«la bandeja tiene una sola conversacion con mas de 228 clientes» (Jesus, 11-08).

    La prueba de que es del equipo y no de cada cual: el entrenador, que no ha escrito a
    nadie, tiene que ver las mismas conversaciones que el admin.
    """
    del_admin = json_ok(pedir("get", "/messages/conversations", headers=cab_admin), "bandeja admin")
    del_coach = json_ok(pedir("get", "/messages/conversations", headers=cab_entrenador), "bandeja coach")
    if not del_admin:
        pytest.skip("no hay ni una conversacion en esta base")
    faltan = {c["user_id"] for c in del_admin} - {c["user_id"] for c in del_coach}
    # La propia conversacion de quien mira no cuenta: a uno mismo no se le escribe.
    assert not faltan, (
        f"el admin ve {len(del_admin)} conversaciones y el entrenador {len(del_coach)}: "
        f"{len(faltan)} no le llegan")


def test_la_bandeja_marca_las_que_esperan_respuesta(cab_admin):
    bandeja = json_ok(pedir("get", "/messages/conversations", headers=cab_admin), "bandeja")
    if not bandeja:
        pytest.skip("no hay ni una conversacion en esta base")
    for c in bandeja:
        assert "sin_respuesta" in c, f"la conversacion con {c['user_id']} no dice si espera respuesta"
        assert c["ultimo_de"] in ("cliente", "equipo")
        # El que se pierde es el que nadie ve: si el ultimo en hablar fue el cliente, esa
        # conversacion esta esperando a alguien.
        assert c["sin_respuesta"] == (c["ultimo_de"] == "cliente"), (
            f"la conversacion con {(c.get('user') or {}).get('name')} dice ultimo_de="
            f"{c['ultimo_de']} y sin_respuesta={c['sin_respuesta']}")


def test_las_que_esperan_respuesta_van_arriba(cab_admin):
    bandeja = json_ok(pedir("get", "/messages/conversations", headers=cab_admin), "bandeja")
    esperando = [not c["sin_respuesta"] for c in bandeja]
    assert esperando == sorted(esperando), "las que esperan respuesta no van las primeras"


def test_cada_conversacion_trae_con_quien_es_y_el_ultimo_mensaje(cab_admin):
    bandeja = json_ok(pedir("get", "/messages/conversations", headers=cab_admin), "bandeja")
    if not bandeja:
        pytest.skip("no hay ni una conversacion en esta base")
    for c in bandeja:
        assert (c.get("user") or {}).get("name"), (
            f"conversacion con {c['user_id']} sin nombre: en pantalla sale «Usuario eliminado»")
        assert (c.get("last_message") or {}).get("created_at")
        assert c["unread"] >= 0


# ------------------------------------------------------- el equipo, tambien como cliente
# Peticion de Francisco del 13-08-2026: *«necesito que los entrenadores y administradores
# puedan buscar su propia ficha como clientes porque ellos usan la app de las dos formas, y
# hoy ya no pueden modificar sus propios macros»*.
#
# Sacar al equipo de la lista (`_fuera_el_equipo`, 09-08) era para que no contara como
# negocio -- 13 usuarios con plan Gold inflando los contadores y el MRR --, pero de paso se
# quedaron sin poder abrir su ficha, que es por donde se tocan los macros. Medido el 13-08:
# 12 de los 16 del equipo tienen ficha de cliente y ninguno se encontraba.
def test_el_del_equipo_se_encuentra_a_si_mismo(cab_admin):
    yo = json_ok(pedir("get", "/auth/me", headers=cab_admin), "/auth/me")
    clientes = json_ok(pedir("get", "/admin/clients", headers=cab_admin), "/admin/clients")
    mio = [c for c in clientes if (c.get("user") or {}).get("id") == yo.get("id")]
    if not mio:
        # Sin ficha de cliente no hay nada que enseñar, y eso es correcto: aparece quien
        # TIENE ficha, no cualquiera del equipo por el hecho de existir.
        perfil = pedir("get", "/clients/profile", headers=cab_admin)
        if perfil.status_code != 200:
            pytest.skip("este admin no tiene ficha de cliente")
        assert False, "tiene ficha de cliente y no se encuentra en la lista"
    assert len(mio) == 1, "sale mas de una vez"


def test_pero_no_ve_al_resto_del_equipo(cab_admin):
    """La excepcion es de UNA fila: cada cual se ve a si mismo, no al equipo entero."""
    yo = json_ok(pedir("get", "/auth/me", headers=cab_admin), "/auth/me")
    clientes = json_ok(pedir("get", "/admin/clients", headers=cab_admin), "/admin/clients")
    otros = [(c.get("user") or {}).get("email") for c in clientes
             if (c.get("user") or {}).get("role") in ("admin", "trainer")
             and (c.get("user") or {}).get("id") != yo.get("id")]
    assert not otros, f"tambien salen otros del equipo: {otros[:3]}"


def test_el_del_equipo_puede_tocar_sus_propios_macros(cab_admin):
    """La otra mitad de la queja: encontrarse no sirve de nada si no puedes editarte."""
    yo = json_ok(pedir("get", "/auth/me", headers=cab_admin), "/auth/me")
    clientes = json_ok(pedir("get", "/admin/clients", headers=cab_admin), "/admin/clients")
    mio = [c for c in clientes if (c.get("user") or {}).get("id") == yo.get("id")]
    if not mio:
        pytest.skip("este admin no tiene ficha de cliente")
    cid = mio[0]["id"]
    ficha = json_ok(pedir("get", f"/admin/clients/{cid}", headers=cab_admin), "ficha propia")
    perfil = ficha.get("profile") or ficha
    antes = (perfil.get("macros_training") or {}).get("protein")
    if antes is None:
        pytest.skip("la ficha no tiene macros todavia")
    entreno = dict(perfil.get("macros_training") or {})
    descanso = dict(perfil.get("macros_rest") or {})

    def guardar(p):
        return pedir("put", f"/admin/clients/{cid}/macros", headers=cab_admin, json={
            "training": {"protein": p, "carbs": entreno.get("carbs", 0), "fat": entreno.get("fat", 0)},
            "rest": {"protein": descanso.get("protein", p), "carbs": descanso.get("carbs", 0),
                     "fat": descanso.get("fat", 0)}})

    r = guardar(float(antes) + 1)
    assert r.status_code == 200, f"no deja guardar sus propios macros: {r.status_code} {r.text[:150]}"
    ficha2 = json_ok(pedir("get", f"/admin/clients/{cid}", headers=cab_admin), "ficha propia")
    p2 = ficha2.get("profile") or ficha2
    try:
        assert (p2.get("macros_training") or {}).get("protein") == float(antes) + 1
    finally:
        guardar(antes)   # se deja como estaba, igual que el caso 82
