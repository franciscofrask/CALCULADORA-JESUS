"""
Sección J del repaso de Jesús, "PERFIL, PLAN Y PERMISOS" (casos 66 a 71).

La lista es suya, de la tanda de 85 casos de prueba que entregó el 12-08-2026:

    66. [CRITICO] Abrir Mi perfil. Espero: el precio es el real del plan y la fecha de
        renovacion es una fecha. Nunca "0 EUR" ni "no definida".
    67. [CRITICO] Entrar con un plan que no incluye chat. Espero: la pantalla de chat no
        aparece en el menu.
    68. Entrar con un plan que no incluye rutina. Espero: la pantalla de rutina no aparece.
    69. [CRITICO] Quitar una capacidad a un plan desde el panel. Espero: al cliente le
        desaparece esa pantalla sin tocar nada mas.
    70. Abrir la app en movil. Espero: la barra de abajo tiene cuatro destinos y el menu,
        nueve entradas con "Seguimiento".
    71. [CRITICO] Abrir la misma cuenta en el ordenador. Espero: las secciones se llaman
        igual que en el movil.

CÓMO SE PRUEBAN LOS PERMISOS (67, 68 y 69). El menú del cliente lo decide `can()` en el
front a partir de las habilitaciones del plan que le llegan por `GET /api/plans`. Así que
los tres casos son el mismo movimiento: se le quita la capacidad al plan desde el panel
(`PUT /api/admin/plans/{code}`), se mira lo que le llega al cliente y se comprueba que el
servidor tampoco le sirve ya esa pantalla.

CUIDADO: el catálogo de planes es configuración COMPARTIDA. Todo lo que se toca aquí se
deja como estaba en un `finally`, y el gestor `plan_sin` es el único sitio que lo cambia.
"""
import os
import re
import time
from contextlib import contextmanager
from datetime import date

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRONT = os.path.join(_RAIZ, "frontend", "src")


def _fuente(*partes) -> str:
    ruta = os.path.join(FRONT, *partes)
    with open(ruta, encoding="utf-8") as f:
        return f.read()


# ─────────────────────────────────────────────────────────────────────────────
# El menú del cliente, leído del fuente
#
# NAV_ITEMS y BOTTOM_ITEMS están escritos en ClientDashboard.jsx y no viajan por ninguna
# API, así que la única forma de comprobar los casos 70 y 71 sin abrir un navegador es
# leerlos de ahí. Se parsean con lo justo: ruta, etiqueta y capacidad exigida.
# ─────────────────────────────────────────────────────────────────────────────

_ENTRADA = re.compile(
    r"\{\s*path:\s*'(?P<path>[^']+)'[^{}]*?label:\s*'(?P<label>[^']+)'"
    r"(?:[^{}]*?cap:\s*'(?P<cap>[^']+)')?[^{}]*\}")


def _sin_comentarios(src: str) -> str:
    """El fuente sin comentarios. Hace falta porque en este repo los comentarios citan a
    propósito el texto viejo que se quitó ("aquí ponía «No definida»"), y buscarlo a pelo
    daría por roto justo lo que se arregló."""
    return re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", src, flags=re.S))


def _lista_del_fuente(nombre: str) -> list:
    src = _fuente("pages", "ClientDashboard.jsx")
    m = re.search(rf"const {nombre} = \[(.*?)\n\];", src, re.S)
    assert m, f"no encuentro {nombre} en ClientDashboard.jsx"
    # Sin comentarios: dentro de la lista hay explicaciones que citan etiquetas ("El plan
    # «solo app» no lleva entrenador...") y no son entradas del menú.
    entradas = [d.groupdict() for d in _ENTRADA.finditer(_sin_comentarios(m.group(1)))]
    assert entradas, f"{nombre} está pero no consigo leer ninguna entrada"
    return entradas


def _capacidades(habilitaciones: dict) -> dict:
    """Espejo en Python de `deriveCapabilities` (frontend/src/lib/planAccess.js).

    Se copia a propósito en vez de leerla: aquí no hay forma de ejecutar el JS. Para que
    la copia no se quede atrás en silencio, `test_las_reglas_del_front_siguen_siendo_estas`
    comprueba que las reglas del fichero original no han cambiado.
    """
    from routes.settings import PANTALLAS

    h = habilitaciones or {}
    reportes = h.get("reportes") or []
    # Espejo de `suplementacionIncluida`: los tres valores del doc 19-08 («ninguna» es un
    # texto y un texto es truthy), tolerando el booleano viejo de los overrides.
    supl = h.get("suplementacion")
    if isinstance(supl, str):
        supl_incluida = supl.strip().lower() in ("guia", "guía", "protocolo")
    else:
        supl_incluida = bool(supl)
    return {
        # La Rutina depende del interruptor `t3_entreno` del panel además de del plan (T3
        # del doc 16-08). Aquí se mira su valor POR DEFECTO, que es lo que se puede saber
        # leyendo el código; encenderlo en el panel la abre a quien tenga rutina en su plan.
        "rutina": (PANTALLAS["t3_entreno"] and bool(h.get("rutina"))
                   and h.get("rutina") != "ninguna"),
        "suplementacion": supl_incluida,
        "macros_personalizados": h.get("calculadora") == "personalizado",
        "reportes": len(reportes) > 0,
        "harbiz": bool(h.get("harbiz")),
        # EL CHAT SALE DEL ACOMPAÑAMIENTO DEL PLAN (decisión de Francisco del 23-08, P73).
        # Antes lo veían los siete planes: al de «solo app», que por definición no lleva
        # entrenador, se le enseñaba el Chat y dentro encontraba un vacío. Ahora lo abre
        # quien tiene entrenador detrás, sea `con_entrenador` o `con_entrenador_y_llamadas`
        # (el Premium es lo segundo, y con la igualdad exacta se quedaba fuera).
        "chat": str(h.get("acompanamiento") or "").startswith("con_entrenador"),
    }


def _menu_del_cliente(habilitaciones: dict) -> list:
    """Las entradas del menú tal y como las arma ClientLayout: filtra por capacidad, quita
    Check-ins (vive dentro de Seguimiento) y renombra Reportes a Seguimiento."""
    caps = _capacidades(habilitaciones)
    fuera = []
    for i in _lista_del_fuente("NAV_ITEMS"):
        if i["path"] == "/dashboard/checkins":
            continue
        if i["cap"] and not caps.get(i["cap"]):
            continue
        etiqueta = "Seguimiento" if i["path"] == "/dashboard/reports" else i["label"]
        fuera.append(etiqueta)
    return fuera


def test_las_reglas_del_front_siguen_siendo_estas():
    """Cerrojo del espejo de arriba: si cambian las reglas de planAccess.js, esto avisa."""
    src = _fuente("lib", "planAccess.js")
    for regla in ("[CAP.RUTINA]: !!rutinaVisible && !!h.rutina && h.rutina !== 'ninguna'",
                  "[CAP.SUPLEMENTACION]: suplementacionIncluida(h)",
                  "[CAP.REPORTES]: reportes.length > 0",
                  "[CAP.CHAT]: String(h.acompanamiento || '').startsWith('con_entrenador')"):
        assert regla in src, (
            f"cambió una regla de deriveCapabilities ({regla}): actualiza `_capacidades` "
            "en este fichero o los casos 67-69 dejan de probar lo que creen")


# ─────────────────────────────────────────────────────────────────────────────
# Quitar una capacidad a un plan desde el panel, y devolverla
# ─────────────────────────────────────────────────────────────────────────────

@contextmanager
def plan_sin(codigo: str, cabeceras_admin: dict, **cambios):
    """Deja el plan `codigo` con esas habilitaciones cambiadas mientras dure el bloque, y
    lo devuelve a como estaba al salir, pase lo que pase.

    Si el plan NO tenía override, se restaura borrándolo (`DELETE`), que lo devuelve al
    valor del código. Si lo tenía, se vuelve a escribir la matriz que había, para no
    llevarse por delante lo que el equipo hubiera editado.
    """
    antes = requests.get(f"{API}/admin/plans", headers=cabeceras_admin, timeout=30)
    assert antes.status_code == 200, f"no puedo leer el catálogo: {antes.status_code}"
    plan = antes.json()[codigo]
    original = dict(plan["habilitaciones"])
    tenia_override = bool(plan.get("has_override"))

    nueva = {**original, **cambios}
    puesta = requests.put(f"{API}/admin/plans/{codigo}", headers=cabeceras_admin,
                          json={"habilitaciones": nueva}, timeout=30)
    assert puesta.status_code == 200, f"el panel no deja editar el plan: {puesta.text[:200]}"
    try:
        yield nueva
    finally:
        # Se reintenta: el backend local se reinicia solo cuando alguien toca un fichero, y
        # dejar el catálogo a medias por una desconexión de dos segundos sería peor que el
        # test que lo provocó.
        if tenia_override:
            _insiste(lambda: requests.put(f"{API}/admin/plans/{codigo}", headers=cabeceras_admin,
                                          json={"habilitaciones": original}, timeout=30))
        else:
            _insiste(lambda: requests.delete(f"{API}/admin/plans/{codigo}",
                                             headers=cabeceras_admin, timeout=30))
        vuelta = _insiste(lambda: requests.get(f"{API}/plans", timeout=30)).json()[codigo]
        assert {k: vuelta["habilitaciones"].get(k) for k in original} == original, (
            f"OJO: el plan {codigo} NO quedó como estaba. Era {original} y está "
            f"{vuelta['habilitaciones']}")


def _insiste(llamada, intentos=25, espera=3):
    """Repite una llamada hasta que el servidor conteste. Solo para restaurar."""
    ultimo = None
    for _ in range(intentos):
        try:
            r = llamada()
            if r.status_code < 500:
                return r
            ultimo = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            ultimo = str(e)[:120]
        time.sleep(espera)
    raise AssertionError(f"no consigo dejar el catálogo como estaba: {ultimo}")


@pytest.fixture(scope="module")
def plan_del_cliente(cabeceras_cliente):
    """El código de plan de la cuenta de pruebas. Es el que se toca en 67, 68 y 69."""
    r = requests.get(f"{API}/clients/profile", headers=cabeceras_cliente, timeout=30)
    assert r.status_code == 200, f"la cuenta de pruebas no tiene perfil: {r.status_code}"
    plan = r.json().get("plan")
    if not plan:
        pytest.skip("la cuenta de pruebas no tiene plan contratado")
    return plan


def _catalogo_del_cliente(cabeceras_cliente, codigo):
    """El plan tal y como le llega al cliente (es lo que alimenta `can()` en el front)."""
    r = requests.get(f"{API}/plans", headers=cabeceras_cliente, timeout=30)
    assert r.status_code == 200
    return r.json()[codigo]


# ─────────────────────────────────────────────────────────────────────────────
# 66. [CRITICO] Abrir Mi perfil.
# ─────────────────────────────────────────────────────────────────────────────

def test_66_el_precio_es_el_real_del_plan_nunca_cero(cabeceras_cliente):
    """«El precio es el real del plan. Nunca 0 EUR».

    El servidor resuelve `precio_ciclo`: `price` venía a cero en los 168 perfiles
    migrados de Calma y la pantalla enseñaba «0 €/ciclo» a gente que paga.
    """
    perfil = requests.get(f"{API}/clients/profile", headers=cabeceras_cliente, timeout=30).json()
    if perfil.get("precio_cortesia"):
        pytest.skip("la cuenta de pruebas es de cortesía: ahí no hay precio que enseñar")
    precio = perfil.get("precio_ciclo")
    assert precio is not None, "Mi perfil no trae precio del ciclo: la pantalla pinta «-»"
    assert float(precio) > 0, f"Mi perfil enseña {precio}€/ciclo"


def test_66_la_fecha_de_renovacion_es_una_fecha(cabeceras_cliente):
    """«La fecha de renovacion es una fecha».

    `renovacion.fecha` sale de `current_period_end` (Stripe) o de `fin_de_ciclo` (el
    calendario de arranque). Un cliente con ciclo en marcha -- `cycle_start` y
    `cycle_total_weeks` puestos -- tiene un final de ciclo perfectamente calculable, así
    que si aquí no hay fecha es que no se está mirando donde está el dato.
    """
    perfil = requests.get(f"{API}/clients/profile", headers=cabeceras_cliente, timeout=30).json()
    renovacion = perfil.get("renovacion") or {}
    fecha = renovacion.get("fecha") or renovacion.get("proximo_cobro") or perfil.get("next_payment")
    assert fecha, (
        "Mi perfil no tiene ninguna fecha de renovación que enseñar "
        f"(renovacion={renovacion}, next_payment={perfil.get('next_payment')}, "
        f"y sin embargo el ciclo empezó el {str(perfil.get('cycle_start'))[:10]} y dura "
        f"{perfil.get('cycle_total_weeks')} semanas)")
    date.fromisoformat(str(fecha)[:10])  # revienta si no es una fecha de verdad


def test_66_nunca_se_le_dice_no_definida(cabeceras_cliente):
    """«Nunca "no definida"». Si no hay fecha, no se enseña la etiqueta: callar dice menos
    que decir que no se sabe (decisión de Jesús del 11-08)."""
    src = _fuente("pages", "ProfilePage.jsx")
    assert not re.search(r"[Nn]o definida", _sin_comentarios(src)), (
        "Mi perfil vuelve a decirle al cliente «No definida»")
    # Y que la etiqueta solo se pinte cuando hay fecha.
    assert "{fechaDeRenovacion && (" in src, (
        "la etiqueta de renovación ya no depende de que haya fecha")


# ─────────────────────────────────────────────────────────────────────────────
# 67. [CRITICO] El Chat, con cualquier plan de pago.
#
# EL CASO SE DIO LA VUELTA EL 21-08 (incongruencia 1b del doc de Jesús): el caso 67
# original («un plan sin chat no enseña la pantalla») escondía el Chat entero al plan
# «solo app», y con él la única vía para preguntar por cobros, renovación o baja -- que
# su propio catálogo promete («Solo incidencias técnicas»). Decisión del doc: «la de
# Mi suscripción la necesitan todos los planes, porque todos pagan». El Chat abre ahora
# con dos entradas (Mi suscripción · Algo no funciona) y es visible para todos.
# ─────────────────────────────────────────────────────────────────────────────

def test_67_el_chat_es_del_que_tiene_entrenador_detras(
        cabeceras_admin, cabeceras_cliente, plan_del_cliente):
    """DOS DECISIONES SEGUIDAS, y manda la ultima.

    El doc del 21-08 (incongruencia 1b) abrio el Chat a los siete planes porque por el
    entran «Mi suscripcion» y «Algo no funciona», y esas son de todos. El 23-08 Francisco
    decidio lo contrario (P73): el Chat vuelve a ser del acompanamiento, porque al plan
    «solo app» -- que por definicion no lleva entrenador -- se le enseñaba el Chat y
    dentro encontraba «Soporte JG12» y un vacio.

    Este test fija la regla vigente. QUEDA ABIERTO, y esta en el informe del 24-08: el
    cliente de «solo app» paga y hoy no tiene por donde preguntar por su dinero.
    """
    with plan_sin(plan_del_cliente, cabeceras_admin, acompanamiento="solo_app"):
        plan = _catalogo_del_cliente(cabeceras_cliente, plan_del_cliente)
        assert _capacidades(plan["habilitaciones"])["chat"] is False, \
            "el plan «solo app» no lleva entrenador: el Chat no es suyo (P73 del 23-08)"

    with plan_sin(plan_del_cliente, cabeceras_admin, acompanamiento="con_entrenador_y_llamadas"):
        plan = _catalogo_del_cliente(cabeceras_cliente, plan_del_cliente)
        caps = _capacidades(plan["habilitaciones"])
        assert caps["chat"] is True, (
            "al plan con entrenador Y llamadas -- el Premium, el mas caro -- se le "
            "esconde el Chat: la regla compara con igualdad y su valor es otro")
        assert "Chat" in _menu_del_cliente(plan["habilitaciones"])


def test_67_el_chat_tambien_esta_abierto_por_detras(
        cabeceras_admin, cabeceras_cliente, plan_del_cliente):
    """Y el servidor tampoco se lo cierra: `GET /messages` (la que abre la pantalla del
    cliente) contesta a un plan «solo app», porque ese cliente también paga."""
    with plan_sin(plan_del_cliente, cabeceras_admin, acompanamiento="solo_app"):
        r = requests.get(f"{API}/messages", headers=cabeceras_cliente, timeout=30)
        assert r.status_code == 200, (
            f"el chat responde {r.status_code} a un plan «solo app»: la entrada de "
            "«Mi suscripción» es de todos los planes de pago (doc 21-08)")


# ─────────────────────────────────────────────────────────────────────────────
# 68. Entrar con un plan que no incluye rutina.
# ─────────────────────────────────────────────────────────────────────────────

def test_68_un_plan_sin_rutina_no_ensena_la_pantalla_de_rutina(
        cabeceras_admin, cabeceras_cliente, plan_del_cliente):
    with plan_sin(plan_del_cliente, cabeceras_admin, rutina="ninguna"):
        plan = _catalogo_del_cliente(cabeceras_cliente, plan_del_cliente)
        menu = _menu_del_cliente(plan["habilitaciones"])
        assert "Rutina" not in menu, f"la Rutina sigue en el menú: {menu}"


def test_68_la_rutina_se_enciende_por_el_mismo_sitio_en_los_dos_lados():
    """Matiz que hay que decir: la Rutina la abre el panel, no el código.

    Se escondió el 19-07-2026 con una constante en cada lado y desde T3 (doc 16-08) manda
    el interruptor `t3_entreno` de db.app_settings. Los dos lados tienen que leer ESE, y no
    cada uno el suyo: si uno se enciende solo, al cliente le llegan avisos de una pantalla
    que no puede abrir, o al revés, ve la pantalla y no se entera de que tiene rutina nueva.
    """
    front = _fuente("lib", "planAccess.js")
    assert "rutinaVisible" in front, "el front ya no lee el interruptor de la Rutina"

    ruta = os.path.join(_RAIZ, "backend", "core", "plan_access.py")
    with open(ruta, encoding="utf-8") as f:
        backend = f.read()
    assert "pantalla_activa(\"t3_entreno\")" in backend, (
        "el backend ya no resuelve la Rutina por el interruptor t3_entreno")

    # Y que quien lo enciende sea uno solo: el mismo nombre en los dos sitios.
    contexto = _fuente("context", "AuthContext.jsx")
    assert "pantalla('t3_entreno')" in contexto, (
        "el front no está pasando el interruptor a deriveCapabilities")


# ─────────────────────────────────────────────────────────────────────────────
# 69. [CRITICO] Quitar una capacidad a un plan desde el panel.
# ─────────────────────────────────────────────────────────────────────────────

def test_69_quitada_del_panel_le_desaparece_del_menu(
        cabeceras_admin, cabeceras_cliente, plan_del_cliente):
    """El panel quita la suplementación y al cliente le desaparece del menú, sin tocar
    nada más de su cuenta."""
    antes = _menu_del_cliente(_catalogo_del_cliente(cabeceras_cliente, plan_del_cliente)["habilitaciones"])
    if "Suplementos" not in antes:
        pytest.skip(f"el plan de la cuenta de pruebas ya no lleva Suplementos: {antes}")

    with plan_sin(plan_del_cliente, cabeceras_admin, suplementacion=False):
        plan = _catalogo_del_cliente(cabeceras_cliente, plan_del_cliente)
        assert plan["habilitaciones"]["suplementacion"] is False, (
            "lo editado en el panel no llega al catálogo que lee el cliente")
        assert "suplementacion" not in (plan.get("features") or []), (
            "las `features` del plan no se recalculan con lo editado en el panel")
        despues = _menu_del_cliente(plan["habilitaciones"])
        assert "Suplementos" not in despues, f"la pantalla sigue en el menú: {despues}"
        # «Sin tocar nada mas»: lo demás del menú se queda igual.
        assert [x for x in antes if x != "Suplementos"] == despues, (
            f"se movió algo más del menú: antes {antes}, después {despues}")


def test_69_quitada_del_panel_el_servidor_tampoco_la_sirve(
        cabeceras_admin, cabeceras_cliente, plan_del_cliente):
    """Y que la capacidad se quite de verdad, no solo de la vista.

    `require_access` decide con `PLAN_TYPES`, que se calcula UNA vez al importar
    `models/user.py` a partir de `PLAN_CATALOG`: los overrides del panel
    (`db.plan_overrides`) no entran ahí. O sea que lo que se edita en el panel cambia el
    menú del cliente pero no cierra el endpoint.
    """
    with plan_sin(plan_del_cliente, cabeceras_admin, suplementacion=False):
        r = requests.get(f"{API}/supplements/current", headers=cabeceras_cliente, timeout=30)
        assert r.status_code in (402, 403), (
            f"con la suplementación quitada desde el panel, /supplements/current sigue "
            f"respondiendo {r.status_code}: la pantalla desaparece del menú pero los datos "
            "siguen sirviéndose a quien pida la URL")


# ─────────────────────────────────────────────────────────────────────────────
# 70. Abrir la app en movil.
# ─────────────────────────────────────────────────────────────────────────────

def test_70_la_barra_de_abajo_tiene_cuatro_destinos(cabeceras_cliente, plan_del_cliente):
    """Inicio, Nutrición, Seguimiento y Perfil. Sin botón «Más»: el cajón escondía media
    app detrás de una palabra que no dice qué hay dentro."""
    plan = _catalogo_del_cliente(cabeceras_cliente, plan_del_cliente)
    caps = _capacidades(plan["habilitaciones"])
    barra = [i["label"] for i in _lista_del_fuente("BOTTOM_ITEMS")
             if not i["cap"] or caps.get(i["cap"])]
    assert len(barra) == 4, f"la barra de abajo tiene {len(barra)} destinos: {barra}"
    assert barra == ["Inicio", "Nutrición", "Seguimiento", "Perfil"], barra


def test_70_el_menu_tiene_nueve_entradas_y_una_es_seguimiento(cabeceras_cliente, plan_del_cliente):
    """«El menu, nueve entradas con Seguimiento»."""
    plan = _catalogo_del_cliente(cabeceras_cliente, plan_del_cliente)
    menu = _menu_del_cliente(plan["habilitaciones"])
    assert "Seguimiento" in menu, f"no hay ninguna entrada «Seguimiento»: {menu}"
    assert "Reportes" not in menu and "Check-ins" not in menu, (
        f"vuelven a estar Reportes y Check-ins por separado: {menu}")
    assert len(menu) == 9, f"el menú tiene {len(menu)} entradas y no nueve: {menu}"


# ─────────────────────────────────────────────────────────────────────────────
# 71. [CRITICO] Abrir la misma cuenta en el ordenador.
# ─────────────────────────────────────────────────────────────────────────────

def test_71_las_secciones_se_llaman_igual_en_movil_y_ordenador():
    """La misma persona abre la app en el móvil por la mañana y en el ordenador por la
    tarde: si la sección se llama distinto en cada sitio, la busca dos veces.

    La comprobación es que las dos vistas pinten LA MISMA lista (`navItems`): el cajón del
    móvil y la barra lateral del escritorio.
    """
    src = _fuente("pages", "ClientDashboard.jsx")
    lateral = re.search(r'data-testid="desktop-sidebar".*?</aside>', src, re.S)
    cajon = re.search(r'data-testid="mobile-drawer".*?\{drawerOpen', src, re.S) or \
        re.search(r'data-testid="mobile-drawer"(.*)', src, re.S)
    assert lateral and cajon, "no encuentro la barra lateral o el cajón del móvil"
    assert "navItems.map" in lateral.group(0), "el escritorio ya no pinta `navItems`"
    assert "navItems.map" in cajon.group(0), "el cajón del móvil ya no pinta `navItems`"

    # Y que no haya una segunda lista de etiquetas por ahí para el escritorio.
    listas = re.findall(r"const (NAV_ITEMS\w*|BOTTOM_ITEMS\w*) = \[", src)
    assert sorted(listas) == ["BOTTOM_ITEMS", "NAV_ITEMS"], (
        f"hay más de una lista de menú y pueden divergir: {listas}")


def test_71_las_cuatro_de_abajo_tienen_su_sitio_en_el_menu(cabeceras_cliente, plan_del_cliente):
    """Los cuatro destinos del móvil llevan a secciones que en el ordenador existen y se
    llaman igual (Perfil / Mi perfil es la única abreviatura, y es por el ancho)."""
    plan = _catalogo_del_cliente(cabeceras_cliente, plan_del_cliente)
    caps = _capacidades(plan["habilitaciones"])
    menu = {i["path"] for i in _lista_del_fuente("NAV_ITEMS")
            if not i["cap"] or caps.get(i["cap"])}
    for destino in _lista_del_fuente("BOTTOM_ITEMS"):
        assert destino["path"] in menu, (
            f"«{destino['label']}» está en la barra del móvil y no en el menú del ordenador")
