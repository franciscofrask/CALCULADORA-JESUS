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


def corre(corutina):
    """Ejecuta una corutina en el bucle comun de la bateria."""
    return BUCLE.run_until_complete(corutina)

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
