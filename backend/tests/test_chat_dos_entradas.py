"""EL CHAT CON DOS ENTRADAS (doc del 21-08, apartados 13 y 20).

El cliente entra al Chat por una de dos puertas -- «Mi suscripción» o «Algo no
funciona» -- y cada mensaje viaja etiquetado con su canal («suscripcion» | «tecnico»).
El campo es OPCIONAL por compatibilidad: los mensajes de antes de las dos entradas, y
los que escribe el staff desde su bandeja, no llevan canal y se comportan como siempre.

Lo que se prueba aquí, por ruta explícita:
  - POST /api/messages con canal: el canal vuelve en la respuesta y queda en la base.
  - GET /api/messages: el canal se devuelve al listar.
  - GET /api/messages/conversations (staff): el último mensaje trae su canal, que es
    de donde la bandeja pinta el chip.
  - Sin canal, o con un canal desconocido: el mensaje se guarda como los de siempre.

NO SE PRUEBA (porque no existe todavía, a propósito): el respondedor automático de
«Algo no funciona». El doc lo quiere automático con el equipo detrás; es un agente
aparte y no era del lunes.
"""
import pytest
import requests

from conftest import API

# Todos los mensajes de esta batería empiezan igual, para poder borrarlos al salir y no
# dejar ruido en la conversación de la cuenta demo.
MARCA = "[test canal]"


@pytest.fixture(scope="module")
def mongo(api_disponible):
    from pymongo import MongoClient

    from core.config import DB_NAME, MONGO_URL

    cliente = MongoClient(MONGO_URL)
    try:
        yield cliente[DB_NAME]
    finally:
        cliente.close()


@pytest.fixture(autouse=True)
def limpia(mongo):
    """Cada test recoge lo suyo: la conversación de la demo no es una papelera."""
    yield
    mongo.messages.delete_many({"content": {"$regex": r"^\[test canal\]"}})


def _envia(cabeceras, texto, **extra):
    r = requests.post(f"{API}/messages", headers=cabeceras,
                      json={"content": f"{MARCA} {texto}", **extra}, timeout=30)
    assert r.status_code == 200, f"no se pudo enviar el mensaje: {r.status_code} {r.text[:200]}"
    return r.json()


@pytest.mark.parametrize("canal", ["suscripcion", "tecnico"])
def test_el_canal_viaja_y_persiste(cabeceras_cliente, mongo, canal):
    """POST con canal: vuelve en la respuesta, queda escrito en la base y se devuelve
    al listar. Es el circuito entero de la etiqueta, por ruta explícita."""
    enviado = _envia(cabeceras_cliente, f"por la entrada {canal}", canal=canal)
    assert enviado.get("canal") == canal, (
        f"POST /api/messages no devuelve el canal: {enviado}")

    # Persistió: el documento de la base lleva el canal, no solo la respuesta.
    doc = mongo.messages.find_one({"id": enviado["id"]}, {"_id": 0})
    assert doc, "el mensaje no está en db.messages"
    assert doc.get("canal") == canal, f"en la base el canal es {doc.get('canal')!r}"

    # Y GET /api/messages lo devuelve, que es lo que leen las dos pantallas.
    r = requests.get(f"{API}/messages", headers=cabeceras_cliente, timeout=30)
    assert r.status_code == 200
    de_vuelta = next((m for m in r.json() if m["id"] == enviado["id"]), None)
    assert de_vuelta, "el mensaje enviado no sale al listar"
    assert de_vuelta.get("canal") == canal, (
        f"GET /api/messages pierde el canal: {de_vuelta}")


def test_sin_canal_todo_sigue_como_hoy(cabeceras_cliente, mongo):
    """Compatibilidad: un POST sin canal (los mensajes de siempre, y los del staff) se
    guarda sin el campo y al listar vuelve con canal a null."""
    enviado = _envia(cabeceras_cliente, "sin canal, como siempre")
    assert enviado.get("canal") is None

    doc = mongo.messages.find_one({"id": enviado["id"]}, {"_id": 0})
    assert doc and "canal" not in doc, (
        f"un mensaje sin canal no debe escribir el campo: {doc}")


def test_un_canal_desconocido_no_se_guarda(cabeceras_cliente, mongo):
    """Solo hay dos entradas. Cualquier otra cosa que llegue en `canal` se ignora y el
    mensaje entra igual: perder un mensaje por una etiqueta mala sería peor."""
    enviado = _envia(cabeceras_cliente, "canal inventado", canal="whatsapp")
    assert enviado.get("canal") is None, (
        "un canal que no es «suscripcion» ni «tecnico» no puede viajar como si lo fuera")
    doc = mongo.messages.find_one({"id": enviado["id"]}, {"_id": 0})
    assert doc and "canal" not in doc


def test_la_bandeja_del_staff_trae_el_canal(cabeceras_cliente, cabeceras_admin):
    """GET /messages/conversations: el último mensaje de la conversación trae su canal.
    Es de donde la bandeja del equipo pinta el chip de la lista."""
    enviado = _envia(cabeceras_cliente, "para el chip de la bandeja", canal="suscripcion")

    r = requests.get(f"{API}/messages/conversations", headers=cabeceras_admin, timeout=30)
    assert r.status_code == 200, f"la bandeja del staff no contesta: {r.status_code}"
    conv = next((c for c in r.json() if c["user_id"] == enviado["sender_id"]), None)
    assert conv, "la conversación del cliente demo no sale en la bandeja del staff"
    assert conv["last_message"]["id"] == enviado["id"], (
        "el último mensaje de la conversación no es el recién enviado; el test no puede "
        "comprobar el canal sobre otro mensaje")
    assert conv["last_message"].get("canal") == "suscripcion", (
        f"la bandeja no trae el canal del último mensaje: {conv['last_message']}")
