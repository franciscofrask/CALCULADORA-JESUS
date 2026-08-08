"""Que cada ruta esté colgada de la función que le toca.

Sale del punto 18 del doc del 07-08. Al ir a añadir un campo al check-in diario se descubrió
que `POST /checkins` estaba registrada sobre una función auxiliar de más arriba, porque el
decorador se había quedado pegado a ella. FastAPI tomaba los parámetros de esa auxiliar
(`profile` y `fecha`) por parámetros de la URL, así que cualquier cliente que enviaba un
check-in recibía un 422 pidiéndole una fecha que nadie le había preguntado. Ni diario, ni
semanal, ni mensual: no funcionaba para nadie, y llevaba así hasta en producción.

Nadie se enteró porque no había un solo test tocando esa ruta. Estos son baratos y cubren la
clase entera de fallo, no solo el caso concreto:

  - una ruta que recibe datos no puede pedir nada por la URL que no esté en la propia URL,
  - y ninguna ruta puede apuntar a una función privada (las que empiezan por guion bajo).
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.routing import APIRoute

from server import app


def _rutas():
    return [r for r in app.routes if isinstance(r, APIRoute)]


def test_hay_rutas_que_revisar():
    assert len(_rutas()) > 50, "no se han podido leer las rutas de la app"


@pytest.mark.parametrize("ruta", _rutas(), ids=lambda r: f"{list(r.methods)[0]} {r.path}")
def test_ninguna_ruta_apunta_a_una_funcion_privada(ruta):
    """Una función que empieza por guion bajo es de andar por casa, no una ruta. Si una lo es,
    casi siempre significa que el decorador se ha quedado pegado a la función equivocada."""
    nombre = getattr(ruta.endpoint, "__name__", "")
    assert not nombre.startswith("_"), (
        f"{list(ruta.methods)[0]} {ruta.path} está colgada de `{nombre}`, que es una función "
        f"auxiliar: seguramente el decorador se quedó pegado a la de arriba")


@pytest.mark.parametrize("ruta", _rutas(), ids=lambda r: f"{list(r.methods)[0]} {r.path}")
def test_nada_que_no_quepa_en_una_url_se_pide_por_la_url(ruta):
    """Por la dirección solo caben cosas sueltas: un texto, un número, una fecha. Si una ruta
    espera por ahí algo que no cabe -- un diccionario, una lista, un objeto --, es que está
    colgada de la función equivocada.

    Un parámetro suelto y requerido en un POST sí es legítimo y lo usa el asistente
    (`?session_id=...`), así que eso no se toca; lo que no puede ser es pedir un diccionario.
    """
    from fastapi.dependencies.utils import get_dependant
    dependant = get_dependant(path=ruta.path_format, call=ruta.endpoint)
    for parametro in dependant.query_params:
        tipo = getattr(parametro.field_info, "annotation", None)
        assert tipo not in (dict, list, set, tuple), (
            f"{list(ruta.methods)[0]} {ruta.path} espera un `{getattr(tipo, '__name__', tipo)}` "
            f"llamado `{parametro.name}` en la dirección, y eso ahí no cabe")


def test_el_alta_de_checkin_acepta_un_checkin():
    """El caso concreto que lo destapó: la ruta tiene que recibir el check-in en el cuerpo."""
    from models.common import CheckInCreate
    ruta = next((r for r in _rutas() if r.path.endswith("/checkins") and "POST" in r.methods), None)
    assert ruta is not None, "no existe POST /checkins"
    assert ruta.endpoint.__name__ == "create_checkin"
    anotaciones = getattr(ruta.endpoint, "__annotations__", {})
    assert CheckInCreate in anotaciones.values(), "no recibe el check-in en el cuerpo"


def test_el_checkin_diario_admite_lo_que_ha_comido():
    """Punto 18: el campo nuevo, que es texto libre y opcional."""
    from models.common import CheckInCreate, CheckInResponse
    assert "comido_hoy" in CheckInCreate.model_fields
    assert "comido_hoy" in CheckInResponse.model_fields, "si no viaja de vuelta, el coach no lo ve"
    c = CheckInCreate(type="daily", energy=4, hunger_anxiety=2,
                      comido_hoy="Un cafe, el tupper y dos galletas de la maquina")
    assert c.comido_hoy.startswith("Un cafe")
    assert CheckInCreate(type="daily", energy=4).comido_hoy is None, "es opcional"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
