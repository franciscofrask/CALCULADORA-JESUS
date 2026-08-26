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


TU_DIETA_HOY = "frontend/src/components/inicio/TuDietaHoy.jsx"


def _bloque_del_rotulo() -> str:
    """El trozo de Inicio donde se decide que dia se esta enseñando."""
    src = _fuente(INICIO)
    fin = src.index("const diaConfigurado")
    return src[src.index("const dieta") if "const dieta" in src else 0:src.index("\n", fin)]


# ── A · el perientreno del numero: desde el 26-08 es un INTERRUPTOR ─────────────────────
#
# Hasta el 25-08 aqui habia una frase, «Tus macros de hoy llevan el perientreno dentro», y
# para decidir si salia se recalculaba la configuracion del dia EN INICIO, con su propia
# precedencia; si esa precedencia se separaba de la de TuDietaHoy, el rotulo describia otro
# numero. Los puntos 86 a 88 del artifact del 25-08 lo cambian por un interruptor que vive
# donde viven los numeros y lee el mismo reparto, asi que no puede desmentirlos. Lo que se
# comprueba ahora es justo eso.

def test_el_interruptor_del_peri_sale_del_mismo_reparto_que_el_numero():
    """Si el interruptor sacara los gramos del peri de otro sitio (del perfil, por
    ejemplo), volveria a poder decir «40 P» debajo de un total que lleva otros 35."""
    src = _fuente(TU_DIETA_HOY)
    bloque = src[src.index("const periTotal"):src.index("const valoresDeVista")]
    assert "reparto?.periworkout" in bloque, \
        "el interruptor vuelve a sacar el peri de un sitio distinto del total"
    assert "conPeri.P - periTotal.P" in bloque, \
        "el numero sin peri ya no se calcula restando: puede dejar de cuadrar con el total"


def test_la_grasa_no_entra_en_la_cuenta_del_peri():
    """En el metodo la grasa del peri no cuenta, y por eso `G_total` nunca la llevo.
    Restarla dejaria la grasa mas baja al desmarcar, y eso seria un numero inventado."""
    src = _fuente(TU_DIETA_HOY)
    bloque = src[src.index("const sinPeri"):src.index("const valoresDeVista")]
    assert "G: conPeri.G" in bloque, "la grasa vuelve a moverse al sacar el peri"


def test_el_interruptor_solo_vive_en_macros():
    """Punto 88: en Dieta, Llevas y Falta el peri ya va contado como una comida mas, con su
    fila y su casilla, asi que ahi el interruptor mentiria."""
    src = _fuente(TU_DIETA_HOY)
    assert "vista === 'macros' && hayPeriEnElDia" in src, \
        "el interruptor del peri se ha soltado de la pestaña Macros"


def test_sin_peri_en_el_dia_no_hay_interruptor():
    """Descanso, `sin_peri` o un peri a 0 puesto por el coach: no hay nada que separar."""
    src = _fuente(TU_DIETA_HOY)
    assert re.search(r"hayPeriEnElDia = periTotal\.P > 0 \|\| periTotal\.H > 0", src), \
        "el interruptor vuelve a salir con el dia sin perientreno"


def test_la_nota_vieja_del_peri_ya_no_esta_en_inicio():
    """La frase suelta necesitaba un truco de `order` para no caer dentro de los extras.
    Al quitarla se fue el truco: que no vuelva ninguna de las dos."""
    src = _fuente(INICIO)
    assert "nota-perientreno" not in src, \
        "vuelve la frase suelta del peri: o se pega a los numeros con un truco, o cae en los extras"


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
    # Se corta por el `) : (` del ternario, que es donde acaba la rama CON macros: cortar
    # por el primer `</div>` daba por hecho que TuDietaHoy iba envuelto en uno, y desde el
    # 26-08 va suelto (se quito el envoltorio que sostenia la nota del peri).
    rama_con_macros = src.split("<TuDietaHoy", 1)[1].split(") : (", 1)[0]
    assert "<ExtrasDelDia" not in rama_con_macros
