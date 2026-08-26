"""
LOS EXTRAS Y LA NOTA DEL PERIENTRENO: los cuatro arreglos del repaso del 24-08.

Guardan cuatro cosas que ya se rompieron una vez y que se rompen sin que nadie se entere,
porque son texto y colocacion de pantalla y no las cubre ningun test de API:

  1. El paso 5 del recorrido de la primera vez prometia que los extras «cuentan igual»
     (era verdad el 21-08; el punto 28 del doc del 24-08 lo cambio y el texto se quedo).
  2. El cliente SIN macros se quedaba sin campo de extras en Inicio, porque el bloque vive
     dentro de TuDietaHoy y ese componente solo se monta cuando hay objetivo.
  3. Nutricion montaba ExtrasDelDia sin `origen`, asi que la mitad de los extras se
     guardaban sin procedencia.
 16. La nota «Tus macros de hoy llevan el perientreno dentro» caia debajo del campo de
     extras (TuDietaHoy devuelve TRES secciones, no una tarjeta).

Los tres primeros se miran en la fuente de las pantallas -- es el mismo patron que
test_cierre_once_preguntas_2408.py -- y el del `origen` se comprueba ademas de punta a
punta contra la API, que es donde se ve el dato guardado.

Como se ejecuta:
  cd backend && REACT_APP_BACKEND_URL=http://127.0.0.1:8000 venv/Scripts/python.exe -m pytest tests/test_extras_arreglos_2408.py -q
"""
import os
import re
from datetime import date
from pathlib import Path

import pytest
import requests

RAIZ = Path(__file__).resolve().parents[2]
RECORRIDO = "frontend/src/components/RecorridoPrimeraVez.jsx"
INICIO = "frontend/src/pages/ClientDashboard.jsx"
NUTRICION = "frontend/src/pages/NutritionPage.jsx"
API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/") + "/api"


def _fuente(ruta: str) -> str:
    return (RAIZ / ruta).read_text(encoding="utf-8")


# ── FALLO 1 · el recorrido de la primera vez ────────────────────────────────────────────

def _texto_del_paso_extras() -> str:
    """El `texto:` del paso 5, sin comentarios: lo que de verdad se pinta."""
    paso = _fuente(RECORRIDO).split("id: 'extras'", 1)[1].split("},", 1)[0]
    return re.search(r"texto:\s*'([^']*)'", paso).group(1)


def test_recorrido_no_promete_que_los_extras_cuenten():
    """Es lo PRIMERO que lee del metodo quien entra por primera vez."""
    src = _fuente(RECORRIDO)
    assert "cuenta igual" not in _texto_del_paso_extras().lower(), \
        "el paso 5 vuelve a prometer que los extras suman"
    # El dibujo de al lado decia lo mismo: «Cuenta igual que lo demás».
    dibujo = src.split("const EsquemaExtras", 1)[1].split(");", 1)[0]
    assert "Cuenta igual" not in dibujo


def test_recorrido_dice_que_no_tocan_los_macros_con_la_frase_de_jesus():
    texto = _texto_del_paso_extras()
    assert "No cuenta contra tus macros" in texto
    # La frase de Jesus del punto 28, literal.
    assert "se te fue algo, lo apuntas, y te sigues comiendo tus comidas" in texto.lower()


# ── FALLO 2 · el campo de extras en Inicio, tambien sin macros ──────────────────────────

def test_inicio_sin_macros_tiene_campo_de_extras():
    """Puntos 26 y 29: «el campo esta en Inicio», sin condiciones."""
    src = _fuente(INICIO)
    assert "import ExtrasDelDia" in src
    # La rama sin objetivo es la de «Configura tus macros»: el bloque tiene que estar ahi,
    # entre esa linea y el cierre del ternario.
    rama = src.split('testId="inicio-sin-macros"', 1)[1].split("\n            )}", 1)[0]
    assert "<ExtrasDelDia" in rama, "el cliente sin macros vuelve a quedarse sin donde apuntar"
    assert 'origen="inicio"' in rama


# ── FALLO 3 · de donde viene el extra ───────────────────────────────────────────────────

def test_nutricion_monta_los_extras_con_su_origen():
    """ExtrasDelDia no trae `origen` por defecto a proposito: lo pone el padre."""
    bloque = _fuente(NUTRICION).split("<ExtrasDelDia", 1)[1].split("/>", 1)[0]
    assert 'origen="nutricion"' in bloque


def test_nutricion_ya_no_dice_que_los_extras_cuenten_en_llevas():
    assert "Cuentan en Llevas" not in _fuente(NUTRICION)


@pytest.mark.parametrize("origen", ["inicio", "nutricion", "checkin"])
def test_el_origen_llega_hasta_el_dato_guardado(cabeceras_cliente, origen):
    """De punta a punta: lo que manda la pantalla es lo que queda escrito en el dia."""
    hoy = date.today().isoformat()
    texto = f"prueba de origen {origen} {os.getpid()}"
    r = requests.post(f"{API}/diets/{hoy}/extras", headers=cabeceras_cliente,
                      json={"texto": texto, "origen": origen}, timeout=20)
    assert r.status_code == 200, r.text
    extra = r.json()["extra"]
    try:
        assert extra["origen"] == origen
        dia = requests.get(f"{API}/diets/{hoy}", headers=cabeceras_cliente, timeout=20).json()
        guardado = next(e for e in dia["extras"] if e["id"] == extra["id"])
        assert guardado["origen"] == origen
    finally:
        requests.delete(f"{API}/diets/{hoy}/extras/{extra['id']}", headers=cabeceras_cliente, timeout=20)


# ── FALLO 16 · donde se pinta la nota del perientreno ───────────────────────────────────

def test_no_hay_frases_sueltas_de_macros_alrededor_de_los_extras():
    """TuDietaHoy devuelve TRES secciones (numeros, marcar comidas y extras), asi que una
    frase escrita detras del componente aterriza debajo del campo de texto de los extras:
    «EXTRAS DEL DIA», que son dos lineas de Jesus, acababa con una frase de macros que no es
    suya. Se sostenia con un truco de `order`.

    Desde el 26-08 (puntos 86 a 88) esa frase es un interruptor y vive DENTRO de la tarjeta
    de Macros, asi que ni hace falta el truco ni se puede caer. Lo que se comprueba es que
    no vuelva ninguna de las dos cosas."""
    src = _fuente(INICIO)
    assert "nota-perientreno" not in src, \
        "vuelve la frase suelta del peri en Inicio: acaba dentro de los extras"
    assert not re.search(r"\[&>\[data-testid=tu-dieta-hoy\]\]:order-\[-1\]", src), \
        "vuelve el truco de `order`: solo hacia falta para sostener la frase suelta"
