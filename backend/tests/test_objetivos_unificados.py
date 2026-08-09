"""Punto 80: el asistente y la pantalla de Nutrición tienen que dar el MISMO objetivo.

*«Sus objetivos no coinciden con los de la pantalla de Nutrición.»* No coincidían, y la
diferencia no era pequeña. Mismo cliente, mismo día, misma configuración:

    Nutrición   C1 = 47,5 P / 51 H / 12 G     220 H al día    (H entreno 170)
    Asistente   C1 = 47,5 P / 72 H / 12 G     290 H al día    (H entreno 240)

**70 g de hidratos al día, 280 kcal.** La proteína y la grasa coincidían; los hidratos no.

Los macros de un cliente cambian con el tiempo -- es el ajuste mensual del método -- y cada
cambio queda en la colección `macro_history` con su `effective_date`. Nutrición leía de ahí
(replicando `todosLosMacros` de Calma); el asistente leía `client_profiles.macros_training`,
que es la foto suelta del perfil y se queda vieja en cuanto hay una revisión. Y hay: **210
de los 236 clientes** tienen historial, 3.439 entradas en total.

Ahora los dos llaman a `macros_por_fecha`, que es una sola función. Y el asistente los
recalcula en `/configure` con la fecha que se va a montar, no una vez al arrancar la
sesión: si no, cambiar de día dentro de la conversación dejaba los objetivos del anterior.
"""
import asyncio
import os
import sys

import pytest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(_RAIZ, ".env"))

API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000")
pytestmark = pytest.mark.skipif(not os.environ.get("MONGO_URL"),
                                reason="sin MONGO_URL: test de integración")

CFG = {"tipo_dia": "entrenamiento", "num_comidas": 4, "momento_entreno": 1,
       "opcion_peri": "intra_post", "single_meal": False}


def _sesion():
    import requests
    r = requests.post(f"{API}/api/auth/login",
                      json={"email": "clientedemo@test.com", "password": "demo123"}, timeout=60)
    if r.status_code != 200:
        pytest.skip("sin backend en pie o sin usuario de prueba")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _objetivos(fecha):
    """Lo que dice cada pantalla para el mismo día.

    Con `--reload` puesto, editar un fichero tira el backend a mitad de la petición y salta
    un ConnectionError que no dice nada del código. Eso se salta, no se da por roto."""
    import requests
    try:
        h = _sesion()
        nutri = requests.post(f"{API}/api/calculator/distribute",
                              json={**CFG, "fecha": fecha}, headers=h, timeout=120).json()
        sid = requests.post(f"{API}/api/chatbot/start", headers=h, timeout=90).json()["session_id"]
        chat = requests.post(f"{API}/api/chatbot/configure?session_id={sid}",
                             json={**CFG, "fecha": fecha}, headers=h, timeout=120).json()
    except requests.exceptions.RequestException as e:
        pytest.skip(f"backend no disponible ({type(e).__name__}); ¿se está recargando?")
    return (nutri.get("comidas") or {},
            (chat.get("distribucion") or {}).get("comidas") or {},
            nutri.get("resumen") or {},
            (chat.get("distribucion") or {}).get("resumen") or {})


@pytest.mark.parametrize("fecha", ["2026-08-20", "2026-07-15", "2026-06-01"])
def test_las_dos_pantallas_dicen_lo_mismo(fecha):
    nutri, chat, rn, rc = _objetivos(fecha)
    assert nutri and chat, "alguna de las dos no devuelve objetivos"
    for comida in ("C1", "C2", "C3"):
        if comida in nutri or comida in chat:
            assert nutri.get(comida) == chat.get(comida), (
                f"{fecha} {comida}: Nutrición dice {nutri.get(comida)} y el asistente "
                f"{chat.get(comida)}")
    for macro in ("P_total", "H_total", "G_total"):
        assert rn.get(macro) == rc.get(macro), (
            f"{fecha} {macro}: Nutrición {rn.get(macro)} vs asistente {rc.get(macro)}")


def test_los_macros_cambian_de_verdad_con_la_fecha():
    """Si dieran lo mismo siempre, el test de arriba pasaría sin probar nada."""
    _, chat_agosto, _, _ = _objetivos("2026-08-20")
    _, chat_julio, _, _ = _objetivos("2026-07-15")
    assert chat_agosto.get("C1") != chat_julio.get("C1"), (
        "el cliente de prueba tiene historial de macros: dos fechas separadas por una "
        "revisión no pueden dar el mismo objetivo")


def test_la_funcion_es_una_sola():
    """La lógica vivía solo en la calculadora y el asistente tenía su propia copia, que es
    justo lo que los separó. Que las dos rutas apunten al mismo sitio."""
    import inspect
    from routes import calculator
    fuente = inspect.getsource(calculator._resolve_macros_for_date)
    assert "macros_por_fecha" in fuente, "la calculadora ya no usa el módulo común"
    from macros_por_fecha import para_el_chat, resolver  # noqa: F401
