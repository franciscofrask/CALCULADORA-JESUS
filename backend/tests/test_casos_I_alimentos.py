"""
Sección I del repaso de Jesús, "ALIMENTOS Y SUPLEMENTOS" (casos 60 a 65).

La lista es suya, de la tanda de 85 casos de prueba que entregó el 12-08-2026. Cada test
lleva arriba el caso tal cual lo escribió, para que se pueda comparar lo que él pidió con
lo que la app hace. Los que están marcados [CRITICO] son suyos también.

    60. [CRITICO] Abrir Alimentos en un movil y cronometrar. Espero: carga en menos de
        tres segundos y pinta un punado de fichas, no trescientas.
    61. [CRITICO] Leer la ficha de un alimento. Espero: dice que macros te cuentan en
        lenguaje normal. Nunca "necesita 9g proteinas para ser sugerido".
    62. Filtrar por "verduras libres". Espero: devuelve las que no suman macros.
    63. Sugerir un alimento desde el cliente. Espero: llega al panel del equipo pendiente
        de aprobar.
    64. Abrir Suplementos con un plan que no la incluye. Espero: ensena la suplementacion
        recomendada, no una pantalla vacia.
    65. Abrir Suplementos con protocolo puesto. Espero: sale su protocolo con dosis y
        momento de toma.

Van contra el backend vivo (mismas credenciales que el resto de la suite, ver conftest).
Lo que es de pintado -- cuántas fichas se montan en el DOM, qué se ve al abrir -- se
comprueba leyendo el fuente del front, porque el dato que decide eso está escrito ahí y no
viaja por la API.
"""
import base64
import os
import re
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"

#: Un PNG de un pixel, para los casos que mandan una solicitud de alimento: desde el punto 161
#: del 27-08 las dos fotos son obligatorias. El servidor comprueba el tipo y el tamaño, no lo
#: que se ve en ellas.
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRONT = os.path.join(_RAIZ, "frontend", "src")


def _fuente(*partes) -> str:
    """El fuente de un fichero del front. Se lee tal cual: aquí no se ejecuta React, se
    comprueba lo que está escrito."""
    ruta = os.path.join(FRONT, *partes)
    with open(ruta, encoding="utf-8") as f:
        return f.read()


# ─────────────────────────────────────────────────────────────────────────────
# 60. [CRITICO] Abrir Alimentos en un movil y cronometrar.
# ─────────────────────────────────────────────────────────────────────────────

# Tres segundos es el número que puso Jesús. Se mide contra localhost, que es el mejor caso
# posible: si aquí ya va justo, en un móvil con datos va peor.
TOPE_SEGUNDOS = 3.0


@pytest.fixture(scope="module")
def listado_de_alimentos(cabeceras_cliente):
    """La llamada que hace la pantalla de Alimentos al abrirse, con lo que tardó."""
    t0 = time.time()
    r = requests.get(f"{API}/calculator/foods-listado", headers=cabeceras_cliente, timeout=60)
    tardanza = time.time() - t0
    assert r.status_code == 200, f"el listado no responde: {r.status_code} {r.text[:200]}"
    return {"datos": r.json(), "segundos": tardanza, "bytes": len(r.content)}


def test_60_alimentos_carga_en_menos_de_tres_segundos(listado_de_alimentos):
    """Lo que tarda la única llamada que hace la pantalla al abrirse."""
    segundos = listado_de_alimentos["segundos"]
    assert segundos < TOPE_SEGUNDOS, (
        f"la pantalla de Alimentos tarda {segundos:.2f}s en localhost "
        f"({listado_de_alimentos['bytes'] / 1024:.0f} KB); el tope de Jesús son "
        f"{TOPE_SEGUNDOS}s y esto es el mejor caso posible")


def test_60_pinta_un_punado_de_fichas_no_trescientas():
    """«Pinta un puñado de fichas, no trescientas»: cuántas se montan al entrar.

    El número está en el fuente (POR_TANDA) porque es una decisión del front, no un dato de
    la API.

    UNA SOLA TANDA, LA MISMA EN LOS DOS SITIOS (Francisco, 31-08-2026). Habia dos numeros,
    `CAP_TELEFONO` a 20 y `CAP_ORDENADOR` a 40, y su frase fue «en telefono decia 20 y en
    escritorio 40, ese era el fallo»: lo que estaba mal no era el numero sino que la pantalla
    se portara distinto segun el aparato. Ahora es una constante, y este caso lo comprueba:
    si vuelve a aparecer un numero por aparato, salta.

    Lo que el caso defiende sigue siendo lo de siempre -- que no se pinten las trescientas de
    golpe, los 69.711 px que se midieron --, asi que el tope se queda holgado en 60.
    """
    src = _fuente("pages", "FoodSearchPage.jsx")

    por_tanda = re.search(r"const POR_TANDA\s*=\s*(\d+)", src)
    assert por_tanda, "la pantalla ya no dice cuántas fichas pinta de golpe"
    assert int(por_tanda.group(1)) <= 60, (
        f"pinta {por_tanda.group(1)} fichas de golpe")
    assert "CAP_TELEFONO" not in src and "CAP_ORDENADOR" not in src, (
        "vuelve a haber una tanda por aparato: era justo lo que dejó que el teléfono se "
        "quedara en 20 mientras el ordenador iba a 40")
    # Y que de verdad corte la lista al pintar, no que el número esté ahí de adorno.
    assert "filtered.slice(0, aLaVista)" in src, (
        "el tope está declarado pero la lista se pinta entera")


def test_60_el_catalogo_no_viaja_entero_a_la_pantalla(cabeceras_cliente, listado_de_alimentos):
    """El caso 60 es de paginación: la pantalla NO puede traerse los 3.211 de golpe.

    Pintar veinte no arregla descargar tres mil: el teléfono se come igual el megabyte y
    medio y lo tiene todo en memoria. `/calculator/foods-listado` no admite ni limit ni
    offset -- se le pasan y los ignora --, así que hoy no hay forma de pedir una tanda.
    """
    con_tope = requests.get(f"{API}/calculator/foods-listado?limit=20&offset=0",
                            headers=cabeceras_cliente, timeout=60)
    assert con_tope.status_code == 200
    devueltos = len(con_tope.json())
    total = len(listado_de_alimentos["datos"])
    assert devueltos < total, (
        f"el listado ignora limit/offset: pidiéndole 20 devuelve los {devueltos} del "
        f"catálogo entero ({listado_de_alimentos['bytes'] / 1024:.0f} KB en una sola "
        f"respuesta). No hay paginación que probar.")


# ─────────────────────────────────────────────────────────────────────────────
# 61. [CRITICO] Leer la ficha de un alimento.
# ─────────────────────────────────────────────────────────────────────────────

# Lo que Jesús no quiere leer nunca en la ficha. Es el filtro del tercio dicho al revés y
# en lenguaje de programador.
JERGA = ("para ser sugerido", "necesita 9g", "cantidad mínima", "cantidad minima")


def test_61_cada_alimento_dice_que_macros_te_cuentan(listado_de_alimentos):
    """La frase de qué te cuenta tiene que llegar a TODAS las fichas, no a las cómodas."""
    datos = listado_de_alimentos["datos"]
    sin_frase = [f["nombre"] for f in datos if not (f.get("que_te_cuenta") or "").strip()]
    assert not sin_frase, (
        f"{len(sin_frase)} alimentos no dicen qué te cuentan, p.ej.: {sin_frase[:5]}")


def test_61_la_frase_esta_en_lenguaje_normal(listado_de_alimentos):
    """Y que la frase sea castellano, no el filtro dicho al revés."""
    datos = listado_de_alimentos["datos"]
    con_jerga = [f["nombre"] for f in datos
                 if any(j in (f.get("que_te_cuenta") or "").lower() for j in JERGA)]
    assert not con_jerga, f"la frase sigue siendo técnica en: {con_jerga[:5]}"

    # Un par de casos concretos para que no se convierta en una frase vacía que pasa el
    # test: si el alimento no suma nada, tiene que decirlo; si suma, tiene que decir qué.
    libres = [f for f in datos if not f.get("tiene_macros")]
    assert libres, "no hay ningún alimento que no cuente macros: mira el motor"
    assert all("cuenta" in (f.get("que_te_cuenta") or "").lower() for f in libres[:20]), (
        "los alimentos que no cuentan macros no lo dicen")


def test_61_la_ficha_no_pinta_el_texto_tecnico():
    """Y que la pantalla no lo pinte, aunque la API siga mandándolo.

    `sugerencia` («Necesita 9g proteínas / 5.5g hidratos / 5.5g grasas para ser sugerido»)
    y `cantidad_minima` siguen viajando en la respuesta. Lo que no puede es llegar a la
    ficha.
    """
    src = _fuente("pages", "FoodSearchPage.jsx")
    # Solo el JSX pintado: los comentarios del fichero citan la frase vieja a propósito,
    # para explicar por qué se quitó.

    sin_comentarios = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    for campo in ("food.sugerencia", "food.cantidad_minima"):
        assert campo not in sin_comentarios, f"la ficha vuelve a pintar {campo}"
    assert "food.que_te_cuenta" in sin_comentarios, (
        "la ficha ya no pinta la frase de qué te cuenta")


# ─────────────────────────────────────────────────────────────────────────────
# 62. Filtrar por "verduras libres".
# ─────────────────────────────────────────────────────────────────────────────

def test_62_verduras_libres_es_un_filtro_de_la_pantalla():
    """El filtro existe y se llama así delante del cliente."""
    src = _fuente("pages", "FoodSearchPage.jsx")
    assert "Verduras libres" in src, "el filtro «Verduras libres» ya no está en la pantalla"
    # Detrás es `sinMacros`: se queda con lo que el motor cuenta a cero.
    assert "opcion === 'sinMacros'" in src and "!f.tiene_macros" in src, (
        "el filtro ya no se queda con los que no suman macros")


def test_62_verduras_libres_devuelve_las_que_no_suman_macros(listado_de_alimentos):
    """Lo que devuelve el filtro: solo alimentos que el motor cuenta a cero."""
    datos = listado_de_alimentos["datos"]
    libres = [f for f in datos if not f.get("tiene_macros")]

    assert libres, "el filtro «Verduras libres» no devuelve nada"
    cuelan = [f["nombre"] for f in libres
              if any(float(f.get(k) or 0) > 0 for k in ("proteinas", "hidratos", "grasas"))]
    assert not cuelan, f"se cuelan alimentos que sí suman macros: {cuelan[:5]}"

    # Y las verduras de toda la vida tienen que estar: si el filtro se queda vacío de
    # verduras, es que la regla de cero dejó de aplicarse.
    nombres = {(f.get("nombre") or "").lower() for f in libres}
    esperadas = [v for v in ("brócoli", "calabacín", "espinacas", "lechuga", "pepino")
                 if any(v in n for n in nombres)]
    assert esperadas, f"ninguna verdura clásica entre las {len(libres)} libres: {sorted(nombres)[:10]}"


# ─────────────────────────────────────────────────────────────────────────────
# 63. Sugerir un alimento desde el cliente.
# ─────────────────────────────────────────────────────────────────────────────

def test_63_lo_sugerido_llega_al_panel_pendiente_de_aprobar(cabeceras_cliente, cabeceras_admin):
    """El cliente sugiere y el equipo lo ve pendiente. Se borra al terminar.

    Hay un tope de 2 sugerencias por semana y cliente: la sugerencia se borra al final
    para no gastarle el cupo a la cuenta de pruebas ni dejar basura en el panel.
    """
    nombre = f"Alimento de prueba {uuid.uuid4().hex[:8]}"
    # Las dos fotos y el enlace (o «No tiene web») son obligatorios desde el punto 161 del
    # 27-08: sin ellos el servidor devuelve un 400 y no hay solicitud que revisar. Este caso
    # va del camino cliente -> panel, así que se manda completa.
    alta = requests.post(
        f"{API}/calculator/suggest-food",
        headers=cabeceras_cliente,
        data={"nombre": nombre, "por_unidad": "false", "racion": "100",
              "es_conserva": "false", "peso_tipo": "neto",
              "proteinas": "20", "hidratos": "5", "grasas": "3", "sin_web": "true"},
        files={"foto_frontal": ("frontal.png", _PNG, "image/png"),
               "foto_reverso": ("reverso.png", _PNG, "image/png")},
        timeout=30,
    )
    if alta.status_code == 429:
        pytest.skip("la cuenta de pruebas ya gastó su cupo semanal de sugerencias")
    assert alta.status_code == 200, f"no deja sugerir: {alta.status_code} {alta.text[:200]}"
    sugerencia = alta.json()
    sid = sugerencia["id"]

    try:
        assert sugerencia.get("status") == "pending", (
            f"la sugerencia nace en estado {sugerencia.get('status')}, no pendiente")

        panel = requests.get(f"{API}/admin/food-suggestions?status=pending",
                             headers=cabeceras_admin, timeout=30)
        assert panel.status_code == 200, f"el panel no lista: {panel.status_code}"
        mia = next((s for s in panel.json() if s.get("id") == sid), None)
        assert mia is not None, "lo sugerido por el cliente no aparece en el panel del equipo"
        assert (mia.get("food") or {}).get("nombre") == nombre
        # Y con quién lo pidió: una sugerencia sin dueño no se puede contestar.
        assert mia.get("client"), "la sugerencia llega al panel sin decir de qué cliente es"
    finally:
        requests.delete(f"{API}/admin/food-suggestions/{sid}",
                        headers=cabeceras_admin, timeout=30)


# ─────────────────────────────────────────────────────────────────────────────
# 64. Abrir Suplementos con un plan que no la incluye.
# ─────────────────────────────────────────────────────────────────────────────

def test_64_sin_protocolo_se_ensena_la_suplementacion_recomendada(cabeceras_cliente):
    """«Ensena la suplementacion recomendada, no una pantalla vacia».

    LA REGLA CAMBIÓ Y ESTE CASO SE HABÍA QUEDADO CON LA VIEJA. El 18-08 Jesús dijo «la
    suplementación tiene que salir siempre la genérica hasta que le pongamos la suya», y
    se compuso una general de cinco líneas dentro de `/supplements/current`, marcada con
    `es_generica`. Un día después, en el doc del 19-08 (bloque 08), la vio y contestó:
    «No es eso. Es mi guía entera».

    Así que la general se quitó de ahí y quien no tiene la suya ve LA GUÍA, que es otra
    pantalla y otro endpoint (`/supplements/guia`). El caso 64 sigue siendo el mismo -- no
    puede quedarse con la pantalla vacía -- pero se comprueba donde la respuesta vive
    ahora; buscando `es_generica` este test daba rojo por medir una regla derogada, y un
    rojo que nadie puede arreglar acaba tapando a uno de verdad.
    """
    r = requests.get(f"{API}/supplements/current", headers=cabeceras_cliente, timeout=30)
    if r.status_code == 403:
        pytest.skip("El plan del cliente de pruebas no tiene la suplementación habilitada.")
    assert r.status_code == 200, r.text
    datos = r.json() or {}

    if datos.get("actual"):
        pytest.skip("la cuenta de pruebas tiene protocolo puesto: este caso es el del que no lo tiene")

    # Sin protocolo propio: `current` viene vacío A PROPÓSITO, y lo que no puede venir
    # vacío es la guía, que es lo que la pantalla enseña en su lugar.
    guia = requests.get(f"{API}/supplements/guia", headers=cabeceras_cliente, timeout=30)
    assert guia.status_code == 200, (
        f"sin protocolo propio no hay ni guía que enseñar: {guia.status_code} {guia.text[:200]}")
    g = guia.json() or {}
    lineas = [f for s in (g.get("secciones") or []) for f in (s.get("fichas") or [])]
    assert lineas, (
        "sin protocolo propio la pantalla se queda vacía: la guía no trae ni una ficha. "
        f"Respuesta: {str(g)[:300]}")
    for ficha in lineas:
        assert ficha.get("nombre"), "cada línea de la guía necesita su producto"
    assert any(f.get("cuanto") or f.get("cuando") for f in lineas), (
        "la guía se lee como una pauta: alguna ficha tiene que decir cuánto o cuándo")


# ─────────────────────────────────────────────────────────────────────────────
# 65. Abrir Suplementos con protocolo puesto.
# ─────────────────────────────────────────────────────────────────────────────

def test_65_con_protocolo_puesto_sale_con_dosis_y_momento(cabeceras_cliente, cabeceras_admin):
    """Se le pone un protocolo al cliente de pruebas, se lee como lo lee él, y se quita.

    Interesa que lleguen las dos cosas que Jesús nombra: cuánto (dosis) y cuándo (momento
    de toma). Un protocolo sin eso es una lista de botes.
    """
    perfil = requests.get(f"{API}/clients/profile", headers=cabeceras_cliente, timeout=30).json()
    client_id = perfil["id"]

    catalogo = requests.get(f"{API}/admin/supplements/catalog", headers=cabeceras_admin,
                            timeout=30).json()
    item = next((c for c in catalogo if c.get("cuando") and c.get("cuanto")), None)
    if not item:
        pytest.skip("el catálogo de suplementos no tiene ningún ítem con cuándo y cuánto")

    from datetime import datetime, timezone
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    previo = requests.get(f"{API}/supplements/current", headers=cabeceras_cliente,
                          timeout=30).json()

    guardar = requests.post(
        f"{API}/admin/supplements/save?client_id={client_id}",
        headers=cabeceras_admin,
        json={"actual": [{"catalog_id": item["id"], "titulo": item["titulo"],
                          "imagen": item.get("imagen"), "enlaces": item.get("enlaces") or [],
                          "cuando": item["cuando"], "cuanto": item["cuanto"],
                          "observaciones": item.get("observaciones")}],
              "siguiente": [], "actual_fecha": hoy, "nota": "Protocolo de prueba (caso 65)"},
        timeout=30,
    )
    assert guardar.status_code == 200, f"no deja guardar el protocolo: {guardar.text[:200]}"

    try:
        visto = requests.get(f"{API}/supplements/current", headers=cabeceras_cliente, timeout=30)
        assert visto.status_code == 200, (
            f"el cliente no puede leer su protocolo: {visto.status_code}")
        protocolo = visto.json()
        assert protocolo and protocolo.get("actual"), "el protocolo guardado no le llega"
        primero = protocolo["actual"][0]
        assert primero.get("titulo"), "el suplemento llega sin nombre"
        assert primero.get("cuanto"), "el suplemento llega sin dosis"
        assert primero.get("cuando"), "el suplemento llega sin momento de toma"
    finally:
        # LIMPIAR NO PUEDE LLEVARSE LO QUE HABÍA. Este caso guarda una versión con la fecha
        # de HOY, y si el cliente ya tenía la suya con esa misma fecha, la pisa; borrar
        # después «la versión de hoy» se llevaba las dos. Pasó de verdad el 27-08: dejó al
        # cliente de pruebas sin protocolo y el propio assert de abajo fue quien lo cantó.
        # Por eso ahora se REPONE lo que había en vez de borrar a ciegas.
        if previo and previo.get("actual"):
            requests.post(
                f"{API}/admin/supplements/save?client_id={client_id}",
                headers=cabeceras_admin,
                json={"actual": previo.get("actual") or [],
                      "siguiente": previo.get("siguiente") or [],
                      "actual_fecha": previo.get("actual_fecha") or hoy,
                      "siguiente_fecha": previo.get("siguiente_fecha"),
                      "nota": previo.get("nota")},
                timeout=30,
            )
            vuelta = requests.get(f"{API}/supplements/current", headers=cabeceras_cliente,
                                  timeout=30).json()
            assert vuelta and vuelta.get("actual"), "al limpiar se llevó por delante lo que había"
        else:
            requests.delete(f"{API}/admin/supplements/version/{hoy}?client_id={client_id}",
                            headers=cabeceras_admin, timeout=30)
