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
import os
import re
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"

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

    El número está en el fuente (CAP_TELEFONO / CAP_ORDENADOR) porque es una decisión del
    front, no un dato de la API.
    """
    src = _fuente("pages", "FoodSearchPage.jsx")

    tel = re.search(r"const CAP_TELEFONO\s*=\s*(\d+)", src)
    orden = re.search(r"const CAP_ORDENADOR\s*=\s*(\d+)", src)
    assert tel and orden, "la pantalla ya no dice cuántas fichas pinta de golpe"
    assert int(tel.group(1)) <= 30, f"en el móvil pinta {tel.group(1)} fichas de golpe"
    assert int(orden.group(1)) <= 60, f"en el ordenador pinta {orden.group(1)} fichas de golpe"
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
    alta = requests.post(
        f"{API}/calculator/suggest-food",
        headers=cabeceras_cliente,
        data={"nombre": nombre, "por_unidad": "false", "racion": "100",
              "peso_tipo": "neto", "proteinas": "20", "hidratos": "5", "grasas": "3"},
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

    CERRADO EL 18-08 con la orden de Jesús: «la suplementación tiene que salir siempre la
    genérica hasta que le pongamos la suya». Antes este caso estaba en rojo a propósito:
    `/supplements/current` devolvía `null`, la pantalla ponía «de momento no te hemos
    puesto nada» y la única propuesta por perfil vivía en `/admin/supplements/suggest`,
    que el cliente no puede pedir.

    Ahora la general viaja en la misma respuesta, marcada con `es_generica` para que
    nadie la confunda con una pauta suya.
    """
    r = requests.get(f"{API}/supplements/current", headers=cabeceras_cliente, timeout=30)
    if r.status_code == 403:
        pytest.skip("El plan del cliente de pruebas no tiene la suplementación habilitada.")
    assert r.status_code == 200, r.text
    datos = r.json() or {}

    if not datos.get("es_generica"):
        assert datos.get("actual"), (
            "sin protocolo propio la respuesta llega vacía: la pantalla vuelve a ser la de "
            f"«Todavía no tienes suplementación». Respuesta: {datos!r}")
        pytest.skip("la cuenta de pruebas tiene protocolo puesto: este caso es el del que no lo tiene")

    assert datos.get("actual"), "se marca como genérica pero no trae ni una línea"
    for item in datos["actual"]:
        assert item.get("titulo"), "cada línea necesita su producto"
        assert (item.get("cuanto") or item.get("cuando")), (
            f"la general se enseña igual que la suya, con dosis y momento: {item!r}")


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
        requests.delete(f"{API}/admin/supplements/version/{hoy}?client_id={client_id}",
                        headers=cabeceras_admin, timeout=30)
        # Si el cliente ya tenía algo puesto de antes, se comprueba que sigue ahí.
        if previo and previo.get("actual"):
            vuelta = requests.get(f"{API}/supplements/current", headers=cabeceras_cliente,
                                  timeout=30).json()
            assert vuelta and vuelta.get("actual"), "al limpiar se llevó por delante lo que había"
