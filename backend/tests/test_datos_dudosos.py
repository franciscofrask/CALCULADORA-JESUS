# -*- coding: utf-8 -*-
"""
Tarea 1.4 del 21-08: macros PROVISIONALES cuando el perfil trae datos imposibles o
incompletos.

En produccion hay 98 perfiles asi: el de Juan (importado de Calma) tiene edad 5, y hay
estaturas de 1 cm y pesos de 1 kg. La puerta de la API valida los rangos al ESCRIBIR
(RANGOS_PERFIL), pero la importacion escribio directo en Mongo y al calcular macros no se
re-valida nada: el dato imposible corrompe en silencio, sin reventar.

Lo que se prueba:
  1. La funcion pura `datos_dudosos`: rangos (limites incluidos), faltantes, perfil sano,
     valores que ni siquiera son numeros, y perfil inexistente.
  2. Que los rangos son EXACTAMENTE los de la puerta Pydantic (una sola fuente).
  3. El campo expuesto: GET /macros devuelve `datos_dudosos` en sus dos ramas.
"""
import asyncio

from core.datos_dudosos import datos_dudosos, datos_imposibles
from models.user import RANGOS_PERFIL


def correr(coro):
    """No hay pytest-asyncio en el repo: se corre a mano, como en el resto de tests."""
    return asyncio.run(coro)


# Un perfil con todo lo que mira la funcion, dentro de rango.
PERFIL_SANO = {
    "weight": 80.5, "height": 178, "age": 34, "body_fat": 18,
    "sex": "hombre", "goal": "volumen",
}


def dudosos_por_campo(perfil):
    return {d["campo"]: d for d in datos_dudosos(perfil)}


# ---------------------------------------------------------------- la funcion pura

def test_perfil_sano_no_tiene_nada_que_decir():
    assert datos_dudosos(PERFIL_SANO) == []
    assert datos_imposibles(PERFIL_SANO) == []


def test_la_edad_5_de_juan_es_imposible_y_trae_el_valor():
    d = dudosos_por_campo({**PERFIL_SANO, "age": 5})
    assert list(d) == ["age"]
    assert d["age"]["motivo"] == "imposible"
    assert d["age"]["valor"] == 5
    assert d["age"]["nombre"] == "edad"


def test_la_estatura_de_1_cm_y_el_peso_de_1_kg_de_produccion():
    d = dudosos_por_campo({**PERFIL_SANO, "height": 1, "weight": 1})
    assert set(d) == {"height", "weight"}
    assert all(v["motivo"] == "imposible" for v in d.values())


def test_los_limites_del_rango_son_validos_y_lo_de_fuera_no():
    # Los extremos INCLUIDOS valen: son los mismos ge/le de la puerta Pydantic.
    for campo, (minimo, maximo) in RANGOS_PERFIL.items():
        assert dudosos_por_campo({**PERFIL_SANO, campo: minimo}) == {}
        assert dudosos_por_campo({**PERFIL_SANO, campo: maximo}) == {}
        assert dudosos_por_campo({**PERFIL_SANO, campo: minimo - 1})[campo]["motivo"] == "imposible"
        assert dudosos_por_campo({**PERFIL_SANO, campo: maximo + 1})[campo]["motivo"] == "imposible"


def test_lo_que_falta_se_dice_como_falta_no_como_imposible():
    perfil = dict(PERFIL_SANO)
    del perfil["height"]
    perfil["age"] = None
    perfil["sex"] = ""
    d = dudosos_por_campo(perfil)
    assert set(d) == {"height", "age", "sex"}
    assert all(v["motivo"] == "falta" for v in d.values())
    # Lo que falta no lleva valor: no hay nada que enseñar.
    assert all("valor" not in v for v in d.values())


def test_un_texto_donde_toca_un_numero_es_imposible():
    d = dudosos_por_campo({**PERFIL_SANO, "weight": "ochenta"})
    assert d["weight"]["motivo"] == "imposible"
    assert d["weight"]["valor"] == "ochenta"


def test_sin_perfil_falta_todo():
    faltas = datos_dudosos(None)
    assert {d["campo"] for d in faltas} == set(RANGOS_PERFIL) | {"sex", "goal"}
    assert all(d["motivo"] == "falta" for d in faltas)
    # Y nada de eso cuenta como "imposible": no hay valores que corregir, solo huecos.
    assert datos_imposibles(None) == []


def test_datos_imposibles_filtra_las_faltas():
    perfil = {**PERFIL_SANO, "age": 5}
    del perfil["height"]
    imposibles = datos_imposibles(perfil)
    assert [d["campo"] for d in imposibles] == ["age"]


def test_los_rangos_son_los_de_la_puerta_pydantic():
    """Una sola fuente: si alguien vuelve a escribir los limites a mano en los Field y
    divergen, esto lo canta."""
    from models.user import ClientProfileUpdate
    for campo, (minimo, maximo) in RANGOS_PERFIL.items():
        meta = ClientProfileUpdate.model_fields[campo].metadata
        ge = next(m.ge for m in meta if hasattr(m, "ge"))
        le = next(m.le for m in meta if hasattr(m, "le"))
        assert (ge, le) == (minimo, maximo), campo


# ---------------------------------------------------------------- el campo expuesto

class _Col:
    def __init__(self, doc):
        self._doc = doc

    async def find_one(self, *a, **kw):
        return self._doc


class FakeDB:
    def __init__(self, perfil):
        self.client_profiles = _Col(perfil)


def test_get_macros_sin_perfil_expone_datos_dudosos(monkeypatch):
    """La rama de los macros por defecto: sin perfil, falta todo, y se dice."""
    import routes.users as ru
    monkeypatch.setattr(ru, "db", FakeDB(None))
    res = correr(ru.get_macros(fecha=None, user={"id": "u-sin-perfil"}))
    assert res["source"] == "default"
    assert {d["campo"] for d in res["datos_dudosos"]} == set(RANGOS_PERFIL) | {"sex", "goal"}


def test_get_macros_con_el_perfil_de_juan_rotula_la_edad(monkeypatch):
    """La rama con fecha (que es la de siempre: sin fecha significa hoy). Los macros NO se
    tocan -- salen del resolver igual que antes --, solo viaja la lista al lado."""
    import routes.users as ru
    import routes.calculator as rc

    perfil = {**PERFIL_SANO, "id": "c-juan", "user_id": "u-juan", "age": 5,
              "macros_source": "manual"}
    entreno = {"protein": 150, "carbs": 200, "fat": 50}
    descanso = {"protein": 140, "carbs": 100, "fat": 50}

    async def resolve(profile, fecha):
        return entreno, descanso, None

    async def choose(profile, fecha):
        return None

    monkeypatch.setattr(ru, "db", FakeDB(perfil))
    monkeypatch.setattr(rc, "_resolve_macros_for_date", resolve)
    monkeypatch.setattr(rc, "_choose_macro_entry_for_date", choose)

    res = correr(ru.get_macros(fecha=None, user={"id": "u-juan"}))
    assert res["training"] == entreno          # los macros, intactos
    dudosos = {d["campo"]: d for d in res["datos_dudosos"]}
    assert list(dudosos) == ["age"]
    assert dudosos["age"]["motivo"] == "imposible"
    assert dudosos["age"]["valor"] == 5
