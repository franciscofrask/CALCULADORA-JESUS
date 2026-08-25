"""
REPASO de los arreglos de los extras y de la nota del perientreno (24-08).

Este fichero NO repite lo que ya guarda test_extras_arreglos_2408.py (el texto del
recorrido, el campo de extras en Inicio, el `origen` de Nutricion y el sitio de la nota).
Guarda lo que el repaso encontro suelto DESPUES de aquellos arreglos:

  A. EL ROTULO DEL PERIENTRENO MENTIA A QUIEN NO LO LLEVA. «Tus macros de hoy llevan el
     perientreno dentro» se pintaba SIEMPRE que el dia no estuviera guardado, porque
     `GET /diets/{fecha}` no manda configuracion ninguna cuando el dia no existe.
     Reproducido el 24-08 en el navegador con una cuenta sin perientreno asignado y el dia
     sin montar: los numeros de arriba eran 190/240/60 pelados y la nota salia igual.

     La condicion buena es SI EL DIA TIENE BLOQUE DE PERI, porque el numero de Inicio es el
     total del reparto y el de Mis macros es ese total MENOS el bloque Intra/Post
     (`objetivo_de_las_comidas`): los dos numeros se separan justo ahi y no antes. Medido
     contra /calculator/distribute y contra la pantalla, ocho estados:
       peri 45/50 + intra_post -> 235/290 arriba y 190/240 en Mis macros: SALE
       peri 45/50 + sin_peri   -> 235/290 en los dos (se reparte entre las comidas): NO sale
       dia de descanso         -> 225/240 en los dos: NO sale
       peri a 0 + intra_post   -> 190/240 en los dos: NO sale
       sin peri asignado       -> el servidor arranca en 35/15: 225/255 arriba: SALE
     Y para saber la configuracion cuando el dia no esta montado hay que pedir
     `GET /user/diet-config`, que es lo que ya hace TuDietaHoy para pedir ese reparto.

  B. UN DIA QUE EXISTE SOLO PORQUE HAY UN EXTRA NO ES UN DIA MONTADO. Desde el 24-08
     apuntar un extra hace upsert del documento del dia, asi que `exists` dejo de
     significar «configurado». El marcador bueno es `num_comidas`. Si esto se rompe, el
     rotulo del peri vuelve a leer una configuracion que no existe (y TuDietaHoy le pinta
     4 comidas vacias a quien tiene 3).

  C. UN EXTRA NO MUEVE NINGUN NUMERO (punto 28). Es la regla que ya mordio una vez: cuando
     sumaban en «Llevas», la app le decia al que se habia comido una tarta que se saltara
     la comida 4.

Como se ejecuta:
  cd backend && REACT_APP_BACKEND_URL=http://127.0.0.1:8000 venv/Scripts/python.exe -m pytest tests/test_repaso_extras_arreglos_2408.py -q
"""
import os
import re
from datetime import date
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parents[2]
INICIO = "frontend/src/pages/ClientDashboard.jsx"
API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/") + "/api"

# Una fecha del pasado que no usa nadie: los extras se cuelgan del documento del dia y no
# hay que ensuciar el dia de hoy del cliente de pruebas para comprobar el upsert.
FECHA_LIBRE = "2019-03-04"


def _fuente(ruta: str) -> str:
    return (RAIZ / ruta).read_text(encoding="utf-8")


def _bloque_del_rotulo() -> str:
    """El trozo de Inicio donde se decide si sale la nota del perientreno."""
    src = _fuente(INICIO)
    fin = src.index("const conPerientreno")
    return src[src.index("const diaConfigurado"):src.index("\n", fin)]


# ── A · el rotulo del perientreno describe el numero que se enseña ──────────────────────

def test_el_rotulo_del_peri_mira_la_configuracion_del_cliente():
    """Sin `/user/diet-config` la pantalla no sabe si el cliente lleva peri, y al que lo
    tiene apagado se le dice que sus macros lo llevan dentro."""
    src = _fuente(INICIO)
    assert "/user/diet-config" in src, \
        "Inicio ha dejado de preguntar la configuracion del cliente: el rotulo del peri vuelve a inventarsela"
    bloque = _bloque_del_rotulo()
    assert "configDieta?.opcion_peri" in bloque, \
        "el dia sin montar vuelve a dar por hecho que todo el mundo lleva perientreno"


def test_el_rotulo_del_peri_se_calla_en_los_tres_casos_sin_bloque_de_peri():
    """Descanso, `sin_peri` y peri a 0: en los tres el numero de Inicio y el de Mis macros
    son el mismo, asi que no hay nada que aclarar."""
    bloque = _bloque_del_rotulo()
    assert "!== 'descanso'" in bloque and "!== 'sin_peri'" in bloque, \
        "el rotulo vuelve a salir en descanso o en sin_peri"
    assert re.search(r"periP > 0 \|\| periH > 0", bloque), \
        "un perientreno a 0 es decision del coach: con el a 0 los dos numeros coinciden"


def test_un_peri_a_cero_no_se_rellena_con_el_arranque_del_servidor():
    """Misma regla que `leer_peri` en backend/macro_distribution.py: el 35/15 es solo para
    el peri SIN ASIGNAR. Rellenar un 0 puesto a proposito ya mordio una vez en el servidor."""
    bloque = _bloque_del_rotulo()
    assert "v !== undefined && v !== null && v !== ''" in bloque, \
        "el 0 vuelve a contar como vacio y se rellena con el 35/15"


def test_la_nota_solo_se_pinta_con_conperientreno():
    """La nota no puede volver a pintarse siempre: cuelga de la condicion."""
    src = _fuente(INICIO)
    trozo = src[src.index("{conPerientreno && ("):]
    assert 'data-testid="nota-perientreno"' in trozo[:600]


# ── B · el dia que existe solo por un extra no es un dia montado ────────────────────────

def test_inicio_no_confunde_dia_existente_con_dia_montado():
    bloque = _bloque_del_rotulo()
    assert "dieta.num_comidas" in bloque, \
        "el rotulo vuelve a fiarse de `exists`, que desde el 24-08 lo pone tambien un extra"


def test_un_extra_crea_el_dia_pero_no_lo_da_por_montado(cabeceras_cliente):
    """El invariante del que se fia la pantalla, comprobado contra la API de verdad."""
    r = requests.post(f"{API}/diets/{FECHA_LIBRE}/extras", headers=cabeceras_cliente,
                      json={"texto": "cafe de las diez", "origen": "inicio"}, timeout=20)
    assert r.status_code == 200, r.text
    extra = r.json()["extra"]
    try:
        dia = requests.get(f"{API}/diets/{FECHA_LIBRE}", headers=cabeceras_cliente, timeout=20).json()
        assert dia["exists"] is True, "el extra tiene que crear el documento del dia"
        assert not dia.get("num_comidas"), \
            "un dia creado por un extra no puede pasar por dia configurado"
        assert not dia.get("comidas"), "un extra no monta comidas"
    finally:
        # El dia entero, no solo el extra: lo creo esta prueba y no lo dejamos puesto.
        requests.delete(f"{API}/diets/{FECHA_LIBRE}", headers=cabeceras_cliente, timeout=20)


# ── C · un extra no mueve ningun numero ─────────────────────────────────────────────────

def test_un_extra_no_toca_ni_el_objetivo_ni_lo_servido(cabeceras_cliente):
    """Punto 28: van en su lista, aparte. Si esto se cae, «Falta» vuelve a encogerse y la
    app le enseña a compensar."""
    hoy = date.today().isoformat()
    antes = requests.get(f"{API}/diets/{hoy}", headers=cabeceras_cliente, timeout=20).json()
    r = requests.post(f"{API}/diets/{hoy}/extras", headers=cabeceras_cliente,
                      json={"texto": "dos cañas y un pincho de tortilla", "origen": "inicio"},
                      timeout=20)
    assert r.status_code == 200, r.text
    extra = r.json()["extra"]
    try:
        assert extra["macros"] is None, "un extra escrito a mano no puede traer macros"
        despues = requests.get(f"{API}/diets/{hoy}", headers=cabeceras_cliente, timeout=20).json()
        assert despues.get("objetivo_comidas") == antes.get("objetivo_comidas")
        assert despues.get("servido_comidas") == antes.get("servido_comidas")
    finally:
        requests.delete(f"{API}/diets/{hoy}/extras/{extra['id']}",
                        headers=cabeceras_cliente, timeout=20)


def test_un_origen_que_no_conocemos_se_guarda_vacio(cabeceras_cliente):
    """Mejor sin procedencia que con una inventada: `_ORIGENES_EXTRA` es la lista buena."""
    r = requests.post(f"{API}/diets/{FECHA_LIBRE}/extras", headers=cabeceras_cliente,
                      json={"texto": "vino de algun sitio", "origen": "widget"}, timeout=20)
    assert r.status_code == 200, r.text
    extra = r.json()["extra"]
    try:
        assert extra["origen"] is None
    finally:
        requests.delete(f"{API}/diets/{FECHA_LIBRE}", headers=cabeceras_cliente, timeout=20)


# ── D · un solo bloque de extras por pantalla ───────────────────────────────────────────

def test_inicio_monta_los_extras_en_una_sola_rama():
    """Con macros los pinta TuDietaHoy y sin macros los pinta Inicio: si algun dia se
    montan los dos en la misma rama, el cliente ve dos listas del mismo dia."""
    src = _fuente(INICIO)
    assert src.count("<ExtrasDelDia") == 1, "Inicio monta el bloque de extras mas de una vez"
    # Y va en la rama SIN objetivo, la de «Configura tus macros», no al lado de TuDietaHoy.
    rama_con_macros = src.split("<TuDietaHoy", 1)[1].split("</div>", 1)[0]
    assert "<ExtrasDelDia" not in rama_con_macros
