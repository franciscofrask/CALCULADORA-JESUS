"""
Configuracion comun de los tests.

Aqui se arregla la razon por la que la suite llevaba tiempo dando 138 "errores" que no
eran errores: los tests de integracion hablan con la API por HTTP y sacaban la URL de
`REACT_APP_BACKEND_URL`. Si no estaba puesta, la URL quedaba en "/api/auth/login" sin
dominio y requests reventaba ANTES de ejecutar el test, asi que salia como error de setup
y escondia lo que de verdad pasara por debajo.

Ahora:
  - la URL tiene un valor por defecto sensato (el backend local),
  - las credenciales estan en UN sitio y salen del entorno, no repetidas en ocho ficheros
    (que es como se quedaron apuntando a un admin que ya no existe),
  - y si no hay servidor, los tests de integracion se SALTAN con un motivo claro en vez
    de fallar en masa. Un test que no se puede ejecutar no es un test roto, y mezclarlos
    hace que nadie mire la lista.
"""
import asyncio
import os

import pytest
import requests

# UN SOLO BUCLE DE ASYNCIO PARA TODA LA BATERIA.
#
# El cliente de Motor (`core.database.db`) se ata al bucle en el que nace, asi que dos
# ficheros que creen cada uno el suyo se pisan: el segundo recibe «Event loop is closed» o,
# peor, resultados fantasma (paso de verdad en test_pedir_alimento_concreto, donde un test
# veia peras al buscar pepino). Y no se nota corriendo el fichero solo -- ahi hay un unico
# bucle y todo pasa --, solo cuando se lanza la bateria entera: el 24-08 tres tests de
# correos empezaron a fallar SOLO en tanda por esto.
#
# Los tests que tocan la base llaman a `corre(...)` en vez de a `asyncio.run` y todos
# comparten este.
BUCLE = asyncio.new_event_loop()


def _bucle_de_motor():
    """El bucle al que se ato el cliente de Motor, o None si todavia no se ha atado.

    Motor 3.3 guarda el bucle de la PRIMERA operacion en `client._io_loop` y lo reutiliza
    para siempre (`AgnosticClient.io_loop`), asi que es un dato privado suyo y aqui se lee
    con cuidado: si un dia cambia de nombre, esto devuelve None y todo sigue como estaba.
    """
    try:
        from core.database import client
        return client, getattr(client, "_io_loop", None)
    except Exception:                                    # noqa: BLE001
        return None, None


def corre(corutina):
    """Ejecuta una corutina en el bucle comun de la bateria.

    Y CURA EL BUCLE MUERTO, que es lo que hacia fallar estos tests SOLO en tanda. El
    cliente de Motor se queda con el bucle de su primera operacion; si esa primera vez cayo
    dentro de un `asyncio.run(...)` de otro fichero -- quedan 51 asi --, ese bucle se cierra
    al acabar y a partir de ahi cualquier consulta por `corre()` muere con «Event loop is
    closed» aunque BUCLE siga abierto. Paso en la bateria del 24-08 con los dos de
    test_circuitos_2408 y los tres de test_correos_avisos_2308: verdes en solitario, rojos
    en tanda, y ni el codigo ni el test tenian nada que ver.

    Se le presta BUCLE solo mientras dura esta corutina y se le devuelve lo que tenia. Y
    solo cuando su bucle esta CERRADO, es decir cuando la llamada iba a reventar de todas
    formas: si el atado es bueno, aqui no pasa nada de nada y esto es la linea de siempre.
    """
    client, atado = _bucle_de_motor()
    if client is None or atado is None or not atado.is_closed():
        return BUCLE.run_until_complete(corutina)
    client._io_loop = BUCLE
    try:
        return BUCLE.run_until_complete(corutina)
    finally:
        # Se le devuelve el suyo aunque este muerto: los ficheros que van por `asyncio.run`
        # no pasan por aqui, y dejarles BUCLE (abierto pero sin correr) les colgaria la
        # consulta para siempre en vez de darles un error.
        client._io_loop = atado

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"

# Credenciales de las cuentas de prueba locales. Se pueden cambiar por entorno sin tocar
# ni un test.
ADMIN_EMAIL = os.environ.get("TEST_ADMIN_EMAIL", "francisco@test.com")
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "demo123")
CLIENT_EMAIL = os.environ.get("TEST_CLIENT_EMAIL", "clientedemo@test.com")
CLIENT_PASSWORD = os.environ.get("TEST_CLIENT_PASSWORD", "demo123")


def _hay_servidor() -> bool:
    try:
        return requests.get(f"{API}/health", timeout=5).status_code == 200
    except requests.RequestException:
        return False


def login(email: str, password: str):
    """Devuelve el token, o None si no se puede entrar."""
    try:
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
        if r.status_code != 200:
            return None
        return r.json().get("access_token") or r.json().get("token")
    except requests.RequestException:
        return None


@pytest.fixture(scope="session")
def api_disponible():
    """Salta la prueba si no hay backend escuchando, con un motivo que se entiende."""
    if not _hay_servidor():
        pytest.skip(f"No hay backend en {BASE_URL}. Levántalo o ajusta REACT_APP_BACKEND_URL.")
    return API


@pytest.fixture(scope="session")
def token_admin(api_disponible):
    t = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not t:
        pytest.skip(f"No se pudo entrar como admin ({ADMIN_EMAIL}). Ajusta TEST_ADMIN_EMAIL/PASSWORD.")
    return t


@pytest.fixture(scope="session")
def token_cliente(api_disponible):
    t = login(CLIENT_EMAIL, CLIENT_PASSWORD)
    if not t:
        pytest.skip(f"No se pudo entrar como cliente ({CLIENT_EMAIL}). Ajusta TEST_CLIENT_EMAIL/PASSWORD.")
    return t


@pytest.fixture(scope="session")
def cabeceras_admin(token_admin):
    return {"Authorization": f"Bearer {token_admin}"}


@pytest.fixture(scope="session")
def cabeceras_cliente(token_cliente):
    return {"Authorization": f"Bearer {token_cliente}"}
