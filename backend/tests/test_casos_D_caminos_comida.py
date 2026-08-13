# -*- coding: utf-8 -*-
"""
Seccion D de la lista de 85 casos de prueba que entrego Jesus: LOS CUATRO CAMINOS DE LA
COMIDA (casos 21 a 30). Cada test lleva arriba el enunciado suyo, tal cual, y debajo lo
que se comprueba de verdad contra la app viva.

Los cuatro caminos son las cuatro maneras de llenar una comida vacia: "sugiereme un menu"
(recetario y biblioteca), "lo hago yo" (el constructor por fases), "repetir" (traerse una
comida de otro dia) y el asistente.

Lo que NO se finge: lo que solo se ve en pantalla (que salgan los cuatro botones, que
aparezca el de guardar, que salte un aviso antes de copiar) va marcado como `skip` con el
motivo. Lo que si se puede medir por HTTP se mide por HTTP, y si sale rojo se deja rojo:
un test que se ajusta para pasar no vale para nada.

Como se ejecuta (backend vivo en el 8000):
    cd backend
    REACT_APP_BACKEND_URL=http://localhost:8000 venv/Scripts/python.exe -m pytest \
        tests/test_casos_D_caminos_comida.py -q
"""
import os
import time
from datetime import date

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"

# Dias de trabajo de esta seccion. Van al 2099 a proposito: asi no pisan ningun dia real
# del cliente demo y se distinguen de los que crean otras tandas de tests. Se borran al
# terminar el modulo (fixture `limpiar_dias`).
DIA_ORIGEN = "2099-03-21"
DIA_DESTINO = "2099-03-22"

# El margen del metodo: +-4 g por macro es lo que hace que una comida este "cuadrada"
# (backend/meal_templates.py, MARGEN_MENU).
MARGEN = 4.0

# Las 31 categorias del constructor "Lo hago yo", copiadas de
# frontend/src/components/nutrition/BuildMealModal.jsx: 11 chips de fuente proteica
# (paso 1) + 20 de acompanamiento (paso 2). Son las que Jesus cuenta en el caso 23.
CATS_PROTEINA = ['1', '2.1', '2.2', '2.3', '2.4', '45', '3', '5', '30', '28', '10']
CATS_ACOMPANAMIENTO = ['21', '8', '7', '22', '9', '11', '13', '10', '5', '24', '19', '27',
                       '32', '43', '44', '37', '38', '39', '16', '17']

CONFIG_DIA = {"tipo_dia": "entrenamiento", "num_comidas": 4, "momento_entreno": 1,
              "opcion_peri": "intra_post"}


def pedir(metodo, ruta, intentos=20, **kw):
    """Una llamada a la API que aguanta que el servidor se reinicie por debajo.

    El backend de desarrollo corre con recarga automatica y hay varias sesiones tocando
    ficheros a la vez, asi que se cae y vuelve cada pocos minutos. Sin esto, la mitad de
    los fallos que salen son "conexion rechazada" y tapan los de verdad. Solo se reintenta
    cuando NO hubo respuesta: cualquier codigo de estado se devuelve tal cual, incluido un
    500, que es justo lo que queremos ver.
    """
    kw.setdefault("timeout", 90)
    ultimo = None
    for _ in range(intentos):
        try:
            return requests.request(metodo, f"{API}{ruta}", **kw)
        except requests.RequestException as err:
            ultimo = err
            time.sleep(3)
    raise ultimo


def tiene_categoria(alimento, codigos):
    """Si el alimento pertenece a alguna de esas categorias del catalogo.

    Se compara igual que el buscador del backend: el codigo entero o como raiz seguida de
    punto, de modo que "2.2" coge a "2.2.3" (pechuga) y "1" NO coge a "13" (verduras).
    """
    cats = [c.strip() for c in (alimento.get("categorias") or "").split("|")]
    return any(c == cod or c.startswith(cod + ".") for c in cats for cod in codigos)


def leer_del_front(*partes):
    """El fuente de una pantalla, para los casos cuya mitad comprobable esta en el front."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    with open(os.path.join(raiz, "frontend", "src", *partes), encoding="utf-8") as f:
        return f.read()


# ── Fixtures ────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def catalogo(cabeceras_cliente):
    """El recetario entero (pestaña "Recetario" del modal de menus)."""
    r = pedir("get", "/calculator/menu-catalog", headers=cabeceras_cliente)
    assert r.status_code == 200, f"El recetario no responde: {r.status_code} {r.text[:200]}"
    return r.json()


@pytest.fixture(scope="module")
def receta_de_comida(catalogo):
    """Una receta de comida COMPLETA (con fuente proteica), que es lo que se elige para
    llenar una comida del dia. Se busca por nombre para no depender del id."""
    completas = [m for m in catalogo["menus"] if m.get("completa")]
    assert completas, "El recetario no tiene ni una receta completa."
    preferida = [m for m in completas if m["nombre"].lower().startswith("arroz salteado con pavo")]
    return (preferida or completas)[0]


@pytest.fixture(scope="module")
def pollo(cabeceras_cliente):
    """Un alimento de proteina de verdad del catalogo, para montar comidas de prueba."""
    r = pedir("get", "/calculator/search", headers=cabeceras_cliente,
              params={"q": "pechuga de pollo", "limit": 5})
    assert r.status_code == 200
    alimentos = r.json()["alimentos"]
    assert alimentos, "No hay pechuga de pollo en el catalogo."
    return alimentos[0]


@pytest.fixture(scope="module")
def objetivo_c2(cabeceras_cliente):
    """Los macros que el metodo le pone HOY a la Comida 2 del cliente demo."""
    r = pedir("post", "/calculator/distribute", headers=cabeceras_cliente,
              json={"fecha": date.today().isoformat(), **CONFIG_DIA})
    assert r.status_code == 200, f"No hay reparto del dia: {r.status_code} {r.text[:200]}"
    return r.json()["comidas"]["C2"]


@pytest.fixture(scope="module", autouse=True)
def limpiar_dias(cabeceras_cliente):
    """Los dias que crea esta seccion se borran al terminar: son del cliente demo."""
    yield
    for fecha in (DIA_ORIGEN, DIA_DESTINO):
        pedir("delete", f"/diets/{fecha}", headers=cabeceras_cliente)


@pytest.fixture
def dia_con_comida_descuadrada(cabeceras_cliente, pollo):
    """Un dia guardado cuya Comida 2 no cuadra ni de lejos con los macros de hoy:
    20 g de pechuga de pollo, unos 4,6 g de proteina contra los ~47 que toca."""
    comidas = {"C2": {"alimentos": [{
        "alimento_id": pollo["id"], "id": pollo["id"], "nombre": pollo["nombre"],
        "cantidad_g": 20, "macros_efectivos": {"P": 4.6, "H": 0.0, "G": 0.4},
    }]}}
    r = pedir("post", "/diets", headers=cabeceras_cliente,
              json={"fecha": DIA_ORIGEN, "comidas": comidas, **CONFIG_DIA})
    assert r.status_code == 200, f"No se pudo preparar el dia origen: {r.text[:200]}"
    return DIA_ORIGEN


# ── Caso 21 ─────────────────────────────────────────────────────────────────────────

@pytest.mark.skip(reason=(
    "visual: hay que ver la tarjeta de la comida vacia. Al mirar el fuente "
    "(MealCard.jsx) solo hay TRES botones -- Sugiereme un menu, Lo hago yo y Repetir -- y "
    "ninguno lleva al asistente, asi que el cuarto camino no esta en la tarjeta. Queda "
    "para comprobar en el navegador antes de darlo por roto."))
def test_21_la_comida_vacia_ofrece_los_cuatro_caminos():
    """21. Abrir una comida vacia. Espero: salen las cuatro vias: sugiereme un menu, lo
    hago yo, repetir y el asistente."""


# ── Caso 22 (CRITICO) ───────────────────────────────────────────────────────────────

def test_22_el_buscador_con_la_proteina_sin_cubrir_solo_ofrece_proteina(cabeceras_cliente, objetivo_c2):
    """22. Camino "lo hago yo": abrir el buscador con la proteina sin cubrir. Espero: solo
    ofrece fuentes de proteina, y cada resultado trae la cantidad ya calculada para cerrar
    lo que falta.

    Este es el camino que usa la app de verdad: el constructor por fases pide
    GET /calculator/search con las categorias del paso 1 y lo que queda de la comida.
    """
    r = pedir("get", "/calculator/search", headers=cabeceras_cliente, params={
        "category": ",".join(CATS_PROTEINA),
        "p_rest": objetivo_c2["P"], "h_rest": objetivo_c2["H"], "g_rest": objetivo_c2["G"],
        "limit": 50,
    })
    assert r.status_code == 200, f"El buscador no responde: {r.status_code} {r.text[:200]}"
    alimentos = r.json()["alimentos"]
    assert alimentos, "Con la proteina sin cubrir el buscador no ofrece nada."

    intrusos = [a["nombre"] for a in alimentos[:60] if not tiene_categoria(a, CATS_PROTEINA)]
    assert not intrusos, f"En la fase de proteina se cuelan alimentos que no lo son: {intrusos[:5]}"

    # "La cantidad ya calculada": el buscador no puede devolver una lista de alimentos a
    # secas, tiene que decir cuanto poner de cada uno para cerrar lo que falta.
    sin_cantidad = [a["nombre"] for a in alimentos[:20] if not (a.get("_cantidad_sugerida") or 0) > 0]
    assert not sin_cantidad, f"Estos salen sin cantidad calculada: {sin_cantidad[:5]}"


def test_22_el_sugeridor_por_pasos_devuelve_cantidades(cabeceras_cliente, objetivo_c2):
    """22 (la otra puerta). POST /calculator/suggest con paso="proteina" es el sugeridor
    documentado del constructor (`sugerir_alimentos` + CATS_PROTEINA_PURAS). Se le pide lo
    mismo: fuentes de proteina con la cantidad calculada.
    """
    r = pedir("post", "/calculator/suggest", headers=cabeceras_cliente, json={
        "restante": objetivo_c2, "paso": "proteina", "limit": 10,
    })
    assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
    sugerencias = r.json()["suggestions"]
    assert sugerencias, "El sugeridor de la fase de proteina no devuelve nada."

    sin_cantidad = [s["alimento"]["nombre"] for s in sugerencias if not (s.get("cantidad_g") or 0) > 0]
    assert not sin_cantidad, (
        "Ninguna sugerencia trae cantidad. El motor `calcular_cantidad_automatica` revienta "
        "con KeyError 'proteina_cuenta' en su return bueno y `ordenar_por_aporte` se traga la "
        f"excepcion, asi que solo sobreviven los alimentos que NO caben: {sin_cantidad[:5]}")


# ── Caso 23 (CRITICO) ───────────────────────────────────────────────────────────────

def test_23_cubierta_la_proteina_se_abren_las_31_categorias(cabeceras_cliente, objetivo_c2):
    """23. Cubrir la proteina. Espero: la fase cambia sola, se abren las 31 categorias y
    aparece el boton de guardar, que antes no estaba.

    De las tres cosas, aqui se comprueba la de datos: que las 31 categorias del
    constructor (11 de proteina + 20 de acompanamiento) tienen alimentos que ofrecer, y
    que con la proteina ya cubierta el buscador deja de estar limitado a fuentes de
    proteina y sirve acompanamientos con su cantidad.
    """
    chips = CATS_PROTEINA + CATS_ACOMPANAMIENTO
    assert len(chips) == 31, f"El constructor deberia abrir 31 categorias y son {len(chips)}."

    vacias = []
    for codigo in chips:
        r = pedir("get", "/calculator/search", headers=cabeceras_cliente,
                  params={"category": codigo, "limit": 3})
        assert r.status_code == 200, f"La categoria {codigo} no responde: {r.status_code}"
        if r.json()["total"] == 0:
            vacias.append(codigo)
    assert not vacias, f"Estas categorias se abren vacias: {vacias}"

    # Fase 2: la proteina ya esta puesta (queda medio gramo) y faltan hidratos y grasa.
    r = pedir("get", "/calculator/search", headers=cabeceras_cliente, params={
        "category": ",".join(CATS_ACOMPANAMIENTO),
        "p_rest": 0.5, "h_rest": objetivo_c2["H"], "g_rest": objetivo_c2["G"], "limit": 30,
    })
    assert r.status_code == 200
    acompanamientos = r.json()["alimentos"]
    assert acompanamientos, "Con la proteina cubierta no se ofrece ningun acompanamiento."
    assert any(not tiene_categoria(a, CATS_PROTEINA) for a in acompanamientos[:30]), (
        "En la fase de acompanamiento solo salen fuentes de proteina: la fase no ha abierto nada.")
    sin_cantidad = [a["nombre"] for a in acompanamientos[:20] if not (a.get("_cantidad_sugerida") or 0) > 0]
    assert not sin_cantidad, f"Acompanamientos sin cantidad calculada: {sin_cantidad[:5]}"


@pytest.mark.skip(reason=(
    "visual: que la fase cambie sola y que aparezca el boton de guardar son dos cosas de "
    "pantalla (BuildMealModal.jsx cambia de paso cuando P y H pasan del 80% del objetivo). "
    "Se comprueba en el navegador."))
def test_23_al_cubrir_la_proteina_aparece_el_boton_de_guardar():
    """23 (la mitad de pantalla). La fase cambia sola y sale el boton de guardar."""


# ── Caso 24 (CRITICO) ───────────────────────────────────────────────────────────────

def test_24_el_recetario_responde_en_menos_de_tres_segundos(cabeceras_cliente):
    """24. Camino "sugiereme un menu": abrir la ventana. Espero: abre en el Recetario y
    devuelve resultados en menos de tres segundos.

    Se mide de verdad, tres veces, y se juzga por la mediana para que un hipo del servidor
    no tumbe el test ni lo salve.
    """
    tiempos = []
    for _ in range(3):
        t0 = time.time()
        r = pedir("get", "/calculator/menu-catalog", headers=cabeceras_cliente)
        tiempos.append(time.time() - t0)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        assert r.json()["total"] > 0, "El recetario abre vacio."
    mediana = sorted(tiempos)[1]
    print(f"\n[caso 24] recetario: {[round(t, 2) for t in tiempos]} s (mediana {mediana:.2f})")
    assert mediana < 3.0, f"El recetario tarda {mediana:.2f} s en abrir (tiempos: {tiempos})."


def test_24_la_ventana_de_menus_abre_en_el_recetario():
    """24 (la otra mitad). "Abre en el Recetario": la pestaña por defecto del modal."""
    fuente = leer_del_front("components", "nutrition", "LibraryMenusModal.jsx")
    assert "useState('recetario')" in fuente, (
        "El modal de menus ya no abre en el recetario. Jesus dejo la biblioteca mas de 30 "
        "segundos cargando y esta es la puerta de entrada de la pantalla.")


def test_24_la_biblioteca_no_se_queda_cargando(cabeceras_cliente, objetivo_c2):
    """24 (la biblioteca). No se le pide que sea rapida como el recetario, se le pide que
    conteste: o trae menus, o dice que esta apagada, pero no se queda colgada."""
    t0 = time.time()
    r = pedir("post", "/calculator/library-menus", headers=cabeceras_cliente, json={
        "mealKey": "C2", "macros_objetivo": objetivo_c2, "limit": 20, **CONFIG_DIA,
    })
    tardo = time.time() - t0
    print(f"\n[caso 24] biblioteca: {tardo:.2f} s")
    assert r.status_code == 200, f"La biblioteca falla: {r.status_code} {r.text[:200]}"
    cuerpo = r.json()
    assert "menus" in cuerpo, f"La biblioteca contesta algo raro: {str(cuerpo)[:200]}"
    assert tardo < 15.0, f"La biblioteca tarda {tardo:.1f} s: para el cliente eso es quedarse cargando."


# ── Caso 25 (CRITICO) ───────────────────────────────────────────────────────────────

def test_25_la_receta_se_recalcula_a_30_10_15(cabeceras_cliente, receta_de_comida):
    """25. Elegir una receta para una comida de 30 P / 10 H / 15 G. Espero: las cantidades
    se recalculan a ese objetivo y los tres macros quedan cuadrados o validos."""
    objetivo = {"P": 30, "H": 10, "G": 15}
    r = pedir("post", "/calculator/menu-apply", headers=cabeceras_cliente, json={
        "plantilla_id": receta_de_comida["id"], "macros_objetivo": objetivo, "mealKey": "C2",
    })
    assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
    menu = r.json()

    assert menu["items"], "La receta vuelve sin alimentos."
    a_cero = [i["nombre"] for i in menu["items"] if not (i.get("cantidad_g") or 0) > 0]
    assert not a_cero, f"La receta vuelve con alimentos a 0 g: {a_cero}"

    totales = menu["macros_totales"]
    desviados = {m: (totales[m], objetivo[m]) for m in ("P", "H", "G")
                 if abs(totales[m] - objetivo[m]) > MARGEN}
    assert not desviados, (
        f"«{menu['nombre']}» no cuadra a 30/10/15: {desviados} "
        f"(servido {totales}, objetivo {objetivo})")
    assert menu["cuadrada"] is True, "Sale dentro de margen pero no se marca como cuadrada."


def test_25_la_marca_de_cuadrada_no_miente(cabeceras_cliente, catalogo):
    """25 (lo que ve el cliente). No todas las recetas cuadran a cualquier objetivo, y eso
    es normal. Lo que no puede pasar es que una comida que se pasa de margen llegue a la
    tarjeta marcada como cuadrada, porque entonces el cliente se la come creyendo que va
    bien. Se comprueba en las 12 primeras recetas completas."""
    objetivo = {"P": 30, "H": 10, "G": 15}
    completas = [m for m in catalogo["menus"] if m.get("completa")][:12]
    assert completas, "No hay recetas completas que probar."

    mentiras, cuadran = [], 0
    for receta in completas:
        r = pedir("post", "/calculator/menu-apply", headers=cabeceras_cliente, json={
            "plantilla_id": receta["id"], "macros_objetivo": objetivo, "mealKey": "C2"})
        assert r.status_code == 200, f"{receta['nombre']}: {r.status_code} {r.text[:150]}"
        menu = r.json()
        dentro = all(abs(menu["macros_totales"][m] - objetivo[m]) <= MARGEN for m in ("P", "H", "G"))
        cuadran += bool(dentro)
        if menu["cuadrada"] != dentro:
            mentiras.append((receta["nombre"], menu["macros_totales"], menu["cuadrada"]))
    print(f"\n[caso 25] cuadran a 30/10/15: {cuadran} de {len(completas)} recetas")
    assert not mentiras, f"Estas recetas dicen una cosa y sirven otra: {mentiras}"


# ── Caso 26 (CRITICO) ───────────────────────────────────────────────────────────────

def test_26_la_misma_receta_con_otros_macros_da_otras_cantidades(cabeceras_cliente, cabeceras_admin,
                                                                 receta_de_comida):
    """26. Elegir la misma receta para otro cliente con otros macros. Espero: salen
    cantidades distintas. Los menus no guardan gramos fijos.

    Se pide LA MISMA receta con dos sesiones distintas y con el objetivo de cada uno. Si el
    recetario guardara gramos fijos, los dos se llevarian el mismo plato y uno de los dos
    estaria comiendo los macros del otro.
    """
    flaco = {"P": 25, "H": 20, "G": 8}
    grande = {"P": 55, "H": 65, "G": 18}

    def aplicar(cabeceras, objetivo):
        r = pedir("post", "/calculator/menu-apply", headers=cabeceras, json={
            "plantilla_id": receta_de_comida["id"], "macros_objetivo": objetivo, "mealKey": "C2"})
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        return r.json()

    uno = aplicar(cabeceras_cliente, flaco)
    otro = aplicar(cabeceras_admin, grande)

    cantidades_uno = {i["nombre"]: i["cantidad_g"] for i in uno["items"]}
    cantidades_otro = {i["nombre"]: i["cantidad_g"] for i in otro["items"]}
    assert set(cantidades_uno) == set(cantidades_otro), "La receta no trae los mismos alimentos."
    assert cantidades_uno != cantidades_otro, (
        f"«{receta_de_comida['nombre']}» sale con los MISMOS gramos para dos objetivos "
        f"distintos ({flaco} y {grande}): {cantidades_uno}. El menu esta guardando gramos fijos.")

    # Y no valen cantidades distintas cualquiera: el que necesita mas tiene que recibir mas.
    assert sum(cantidades_otro.values()) > sum(cantidades_uno.values()), (
        f"Al objetivo grande {grande} le toca menos comida que al pequeno {flaco}: "
        f"{sum(cantidades_otro.values())} g contra {sum(cantidades_uno.values())} g.")

    # Cada uno tiene que ir a lo suyo: mas proteina pedida, mas proteina servida.
    assert otro["macros_totales"]["P"] > uno["macros_totales"]["P"], (
        f"La proteina servida no sigue al objetivo: {uno['macros_totales']} contra {otro['macros_totales']}.")


# ── Caso 27 ─────────────────────────────────────────────────────────────────────────

def test_27_repetir_solo_ofrece_dias_con_esa_comida_cuadrada(cabeceras_cliente,
                                                             dia_con_comida_descuadrada):
    """27. Camino "repetir": abrir la lista de dias. Espero: solo salen dias con esa comida
    cuadrada y con los macros vigentes de ahora.

    Se deja guardado un dia cuya Comida 2 son 20 g de pollo (unos 4,6 g de proteina contra
    los ~47 de hoy) y se abre la lista que pinta el modal de repetir (GET /diets/recent).
    Ese dia no deberia ofrecerse para repetir la Comida 2.
    """
    r = pedir("get", "/diets/recent", headers=cabeceras_cliente, params={"limit": 14})
    assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
    dias = r.json()["diets"]

    ofrecen_c2 = [d for d in dias if (d.get("comidas_resumen") or {}).get("C2")]
    fechas = [d["fecha"] for d in ofrecen_c2]
    assert dia_con_comida_descuadrada not in fechas, (
        f"Se ofrece repetir la Comida 2 del {dia_con_comida_descuadrada}, que son 20 g de "
        "pollo y no cuadra con los macros de hoy. La lista sale de /diets/recent, que "
        "devuelve todos los dias guardados sin mirar si esa comida cuadra.")

    # La otra mitad del caso: "con los macros vigentes de ahora". Para poder decir que un
    # dia esta cuadrado hay que compararlo con los macros de HOY, y la lista tiene que
    # traer con que hacerlo.
    sin_con_que_juzgar = [d["fecha"] for d in ofrecen_c2
                          if not d.get("distribution_targets") and "cuadrada" not in d]
    assert not sin_con_que_juzgar, (
        "La lista de dias no dice si cada comida cuadra ni con que macros se guardo "
        f"(distribution_targets viene a null): {sin_con_que_juzgar[:5]}")


# ── Caso 28 ─────────────────────────────────────────────────────────────────────────

def test_28_copiar_una_comida_que_no_cuadra_la_cuadra(cabeceras_cliente, pollo, objetivo_c2):
    """28. Copiar una comida de otro dia que no cuadra con los macros de hoy. Espero: avisa
    antes de copiar y ofrece cuadrarla.

    La app no pregunta: cuadra sola, llamando a POST /calculator/cuadrar-comida con los
    alimentos del dia de origen (el punto 4.9 del 09-08, para no repetir el escalado por
    proteina que dejaba la comida en rojo). Lo que se comprueba aqui es eso: que la comida
    copiada llega cuadrada a los macros de hoy.
    """
    r = pedir("post", "/calculator/cuadrar-comida", headers=cabeceras_cliente, json={
        # Lo que manda el front al repetir: id, gramos y nombre de cada alimento.
        "items": [{"alimento_id": pollo["id"], "cantidad_g": 20, "nombre": pollo["nombre"]}],
        "mealKey": "C2", "fecha": date.today().isoformat(), **CONFIG_DIA,
    })
    assert r.status_code == 200, (
        f"Cuadrar la comida copiada devuelve {r.status_code}: {r.text[:200]}. "
        "El front se lo come en su catch y vuelve al escalado por proteina, que es "
        "justo lo que Jesus reporto descuadrado.")

    comida = r.json()
    objetivo = comida["macros_objetivo"]
    totales = comida["macros_totales"]
    assert comida["items"], "La comida copiada vuelve sin alimentos."
    desviados = {m: (totales[m], objetivo[m]) for m in ("P", "H", "G")
                 if abs(totales[m] - objetivo[m]) > MARGEN}
    assert comida["cuadrada"] is True and not desviados, (
        f"La comida copiada no queda cuadrada a los macros de hoy: {desviados} "
        f"(servido {totales}, objetivo {objetivo}).")


@pytest.mark.skip(reason=(
    "visual, y ademas la app hace otra cosa: no avisa ni ofrece nada, cuadra sola al "
    "copiar (NutritionPage.copyMealFromDay). Si Jesus quiere el aviso hay que anadirlo; "
    "el test de arriba comprueba que al menos lo que copia queda cuadrado."))
def test_28_avisa_antes_de_copiar_una_comida_que_no_cuadra():
    """28 (la mitad de pantalla). Avisa antes de copiar y ofrece cuadrarla."""


# ── Caso 29 ─────────────────────────────────────────────────────────────────────────

def test_29_no_se_guarda_una_dieta_favorita_sin_comidas(cabeceras_cliente):
    """29. Guardar una dieta favorita sin ninguna comida montada. Espero: no deja: el boton
    esta apagado hasta que haya al menos una comida.

    El boton apagado es la mitad de pantalla (el test de abajo). Esta es la otra: que
    guardar un dia vacio no se pueda, punto. Si el unico cerrojo esta en el boton, la
    favorita de cero comidas que vio Jesus puede volver por cualquier otra puerta.
    """
    r = pedir("post", "/diets/favorites", headers=cabeceras_cliente,
              json={"name": "PRUEBA CASO 29 (borrar)", "comidas": {}})
    if r.status_code == 200:
        # Se guardo: se limpia antes de suspender, que el cliente demo no se queda con basura.
        pedir("delete", f"/diets/favorites/{r.json()['favorite']['id']}", headers=cabeceras_cliente)
    assert r.status_code in (400, 422), (
        f"Se guarda una favorita sin ninguna comida (la API responde {r.status_code}). "
        "El unico cerrojo esta en el boton del modal.")


def test_29_el_boton_de_guardar_favorita_se_apaga_con_el_dia_vacio():
    """29 (la mitad de pantalla, en el fuente). El boton de guardar la favorita tiene que
    estar apagado mientras el dia no tenga ninguna comida montada."""
    modal = leer_del_front("components", "nutrition", "FavoritesModal.jsx")
    assert "diaVacio" in modal and "disabled={!name.trim() || saving || diaVacio}" in modal, (
        "El boton de guardar la favorita ya no mira si el dia esta vacio.")

    pantalla = leer_del_front("pages", "NutritionPage.jsx")
    assert "diaVacio=" in pantalla, (
        "La pantalla de Nutricion no le dice al modal si el dia esta vacio, asi que el "
        "boton nunca se apaga.")


# ── Caso 30 ─────────────────────────────────────────────────────────────────────────

def test_30_copiar_la_dieta_a_una_fecha_ocupada_avisa_antes_de_sustituir(
        cabeceras_cliente, pollo, dia_con_comida_descuadrada):
    """30. Copiar la dieta de hoy a otra fecha que ya tiene comidas. Espero: avisa antes de
    sustituir.

    El aviso es de pantalla, pero lo que se puede medir es si hay algo que sustituir sin
    remedio: se deja el dia destino con una Comida 4 montada y se copia encima. O la API
    avisa (un 409, o pidiendo confirmacion), o al menos no se lleva por delante lo que
    habia. Hoy hace las dos cosas mal: reemplaza el dia entero y no lo dice.
    """
    comidas_destino = {"C4": {"alimentos": [{
        "alimento_id": pollo["id"], "id": pollo["id"], "nombre": pollo["nombre"],
        "cantidad_g": 100, "macros_efectivos": {"P": 23.0, "H": 0.0, "G": 2.0},
    }]}}
    r = pedir("post", "/diets", headers=cabeceras_cliente,
              json={"fecha": DIA_DESTINO, "comidas": comidas_destino, **CONFIG_DIA})
    assert r.status_code == 200, f"No se pudo preparar el dia destino: {r.text[:200]}"

    copia = pedir("post", "/diets/copy-day", headers=cabeceras_cliente,
                  json={"fecha_origen": dia_con_comida_descuadrada, "fecha_destino": DIA_DESTINO})

    if copia.status_code in (409, 422):
        return  # avisa antes de sustituir: es lo que pide el caso

    assert copia.status_code == 200, f"Copiar el dia falla: {copia.status_code} {copia.text[:200]}"
    despues = pedir("get", f"/diets/{DIA_DESTINO}", headers=cabeceras_cliente).json()
    comidas = despues.get("comidas") or {}
    assert "C4" in comidas and (comidas["C4"].get("alimentos") or []), (
        f"Copiar sobre el {DIA_DESTINO} se ha llevado por delante la Comida 4 que ya habia "
        f"sin avisar de nada (quedan: {sorted(comidas)}). Ni /diets/copy-day ni la pantalla "
        "(NutritionPage.copyDiet) miran si la fecha destino tiene algo.")
