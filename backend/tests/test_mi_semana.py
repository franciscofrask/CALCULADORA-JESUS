"""
GET /diets/semana: la semana de Mi semana (tarea 5.1 del rediseño, 21-08).

Se monta una semana lejana (enero de 2030) en la cuenta de prueba del cliente para no
pisar datos reales, y se comprueba:

  - los siete días llegan de lunes a domingo, pidiendo la semana por CUALQUIER día,
  - los estados: montada / empezada / sin_montar, con el conteo «X de N comidas»,
  - el peri (Post) NO cuenta como comida: un día con C1..C4 llenas y Post llena
    sigue siendo «montada» con 4 de 4,
  - un día guardado como descanso sale como descanso,
  - los macros de un día montado suman de verdad (alimento real del catálogo),
  - el resumen cuadra con los días,
  - y el contador de entrenos (punto 59 del doc 24-08): «X de N» solo cuando ese
    cliente registra sus sesiones, y un total que no promete entrenos invisibles.
"""
import os
from datetime import date, timedelta

import pytest
import requests

from conftest import API

# Lunes de una semana que no existe en los datos reales.
LUNES = date(2030, 1, 7)
assert LUNES.weekday() == 0, "el ancla del test tiene que ser un lunes"
FECHAS = [(LUNES + timedelta(days=i)).isoformat() for i in range(7)]

# Otro lunes todavía más lejos, para la semana de la que no se sabe NADA: ni dietas
# guardadas ni rutina que la cubra.
LUNES_VACIO = LUNES + timedelta(weeks=52)
assert LUNES_VACIO.weekday() == 0


def _alimento_real(cabeceras):
    """Un alimento del catálogo con proteína, para que el día montado sume macros."""
    r = requests.get(f"{API}/calculator/foods", params={"search": "pollo", "limit": 5},
                     headers=cabeceras, timeout=15)
    if r.status_code == 200 and isinstance(r.json(), list) and r.json():
        f = r.json()[0]
        return {"alimento_id": f.get("id"), "nombre": f.get("nombre", "Pollo"),
                "cantidad_g": 150}
    # Sin catálogo (base vacía) el test de estados sigue valiendo; el de macros se salta.
    return {"alimento_id": "no-existe", "nombre": "Alimento de prueba", "cantidad_g": 150}


def _guardar_dia(cabeceras, fecha, tipo_dia, comidas):
    r = requests.post(f"{API}/diets", headers=cabeceras, timeout=20, json={
        "fecha": fecha,
        "tipo_dia": tipo_dia,
        "num_comidas": 4,
        "comidas": comidas,
        "comidas_completas": True,
    })
    assert r.status_code == 200, f"no se pudo guardar {fecha}: {r.text}"


@pytest.fixture(scope="module")
def semana_montada(api_disponible, cabeceras_cliente):
    """Deja la semana de prueba montada y la limpia al terminar."""
    # Por si un run anterior no llegó a limpiar.
    for f in FECHAS:
        requests.delete(f"{API}/diets/{f}", headers=cabeceras_cliente, timeout=15)

    alimento = _alimento_real(cabeceras_cliente)
    con = {"alimentos": [dict(alimento)]}
    vacia = {"alimentos": []}

    # Lunes: montada (C1..C4 llenas) y ADEMÁS el Post lleno, que no debe contar.
    _guardar_dia(cabeceras_cliente, FECHAS[0], "entrenamiento",
                 {"C1": con, "C2": con, "C3": con, "C4": con, "Post": con})
    # Martes: empezada (2 de 4).
    _guardar_dia(cabeceras_cliente, FECHAS[1], "entrenamiento",
                 {"C1": con, "C2": con, "C3": vacia, "C4": vacia})
    # Miércoles: día de DESCANSO, empezado (1 de 4).
    _guardar_dia(cabeceras_cliente, FECHAS[2], "descanso",
                 {"C1": con, "C2": vacia, "C3": vacia, "C4": vacia})
    # Jueves: guardado pero sin nada -> sin montar. Viernes a domingo: sin documento.
    _guardar_dia(cabeceras_cliente, FECHAS[3], "entrenamiento",
                 {"C1": vacia, "C2": vacia, "C3": vacia, "C4": vacia})

    yield alimento

    for f in FECHAS:
        requests.delete(f"{API}/diets/{f}", headers=cabeceras_cliente, timeout=15)


def _semana(cabeceras, inicio):
    r = requests.get(f"{API}/diets/semana", params={"inicio": inicio},
                     headers=cabeceras, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def _mongo():
    """La base de dev. El registro de sesiones se pone y se quita a mano: el endpoint que
    lo guarda exige rutina activa y aquí lo único que importa es que la fila EXISTA."""
    import pymongo
    from dotenv import dotenv_values
    cfg = dotenv_values(os.path.join(os.path.dirname(__file__), "..", ".env"))
    return pymongo.MongoClient(cfg["MONGO_URL"])[cfg["DB_NAME"]]


def _client_id(cabeceras, db):
    """El id de la FICHA del cliente: workout_logs va por client_profiles.id, no por
    users.id (los dos ids de siempre)."""
    me = requests.get(f"{API}/auth/me", headers=cabeceras, timeout=15).json()
    perfil = db.client_profiles.find_one({"user_id": me["id"]}, {"_id": 0, "id": 1}) or {}
    return perfil.get("id")


class TestMiSemana:

    def test_siete_dias_de_lunes_a_domingo_desde_cualquier_dia(self, semana_montada, cabeceras_cliente):
        # Se pide por el MIÉRCOLES y tiene que volver la semana entera desde el lunes.
        data = _semana(cabeceras_cliente, FECHAS[2])
        assert data["inicio"] == FECHAS[0]
        assert data["fin"] == FECHAS[6]
        assert [d["fecha"] for d in data["dias"]] == FECHAS
        assert len(data["dias"]) == 7

    def test_estados_montada_empezada_y_sin_montar(self, semana_montada, cabeceras_cliente):
        dias = _semana(cabeceras_cliente, FECHAS[0])["dias"]
        estados = {d["fecha"]: d["estado"] for d in dias}
        assert estados[FECHAS[0]] == "montada"
        assert estados[FECHAS[1]] == "empezada"
        assert estados[FECHAS[2]] == "empezada"     # descanso con una comida puesta
        assert estados[FECHAS[3]] == "sin_montar"   # guardado vacío
        assert estados[FECHAS[4]] == "sin_montar"   # sin documento
        assert estados[FECHAS[5]] == "sin_montar"
        assert estados[FECHAS[6]] == "sin_montar"

        martes = next(d for d in dias if d["fecha"] == FECHAS[1])
        assert martes["n_comidas_con_alimentos"] == 2
        assert martes["n_comidas_total"] == 4

    def test_el_peri_no_cuenta_como_comida(self, semana_montada, cabeceras_cliente):
        lunes = next(d for d in _semana(cabeceras_cliente, FECHAS[0])["dias"]
                     if d["fecha"] == FECHAS[0])
        # El Post está lleno y aún así el día son 4 de 4, no 5 de nada.
        assert lunes["n_comidas_total"] == 4
        assert lunes["n_comidas_con_alimentos"] == 4
        assert lunes["estado"] == "montada"

    def test_un_dia_de_descanso_sale_como_descanso(self, semana_montada, cabeceras_cliente):
        dias = _semana(cabeceras_cliente, FECHAS[0])["dias"]
        miercoles = next(d for d in dias if d["fecha"] == FECHAS[2])
        assert miercoles["tipo_dia"] == "descanso"
        # Un día de descanso no lleva nombre de entreno ni entreno hecho.
        assert miercoles["entreno"]["nombre"] is None
        lunes = next(d for d in dias if d["fecha"] == FECHAS[0])
        assert lunes["tipo_dia"] == "entrenamiento"

    def test_los_macros_del_dia_montado_suman(self, semana_montada, cabeceras_cliente):
        lunes = next(d for d in _semana(cabeceras_cliente, FECHAS[0])["dias"]
                     if d["fecha"] == FECHAS[0])
        m = lunes["macros"]
        assert set(m) == {"P", "H", "G"}
        if semana_montada["alimento_id"] != "no-existe":
            # Cuatro comidas de pollo tienen que sumar proteína; el peri va aparte y
            # los macros son los del motor de conteo (calibrar_dia), no una clave leída
            # a mano, así que basta con que el total sea de verdad mayor que cero.
            assert m["P"] > 0

    def test_el_resumen_cuadra_con_los_dias(self, semana_montada, cabeceras_cliente):
        data = _semana(cabeceras_cliente, FECHAS[0])
        r = data["resumen"]
        assert r["montadas"] == 1
        assert r["empezadas"] == 2
        assert r["sin_montar"] == 4
        # Los entrenos: N son los días de entreno resueltos de ESTA semana, y los
        # hechos o son un número o son null (cuando el registro de sesiones está
        # apagado no se inventa un «0 de N»).
        de_entreno = sum(1 for d in data["dias"] if d["tipo_dia"] == "entrenamiento")
        assert r["entrenos_total"] == de_entreno
        assert r["entrenos_hechos"] is None or isinstance(r["entrenos_hechos"], int)
        assert "hoy" in data

    def test_fecha_invalida_da_400(self, api_disponible, cabeceras_cliente):
        r = requests.get(f"{API}/diets/semana", params={"inicio": "esto-no-es-fecha"},
                         headers=cabeceras_cliente, timeout=15)
        assert r.status_code == 400

    def test_sin_token_no_hay_semana(self, api_disponible):
        r = requests.get(f"{API}/diets/semana", timeout=15)
        assert r.status_code in (401, 403)


class TestElContadorDeEntrenos:
    """«0 de 5 entrenos» le mentía a todo el mundo (punto 59 del doc 24-08).

    En producción la pantalla de registro de entrenos estaba encendida y la colección de
    sesiones VACÍA, así que el titular decía «0 de N» a los 120 clientes: un cero que no
    había contado nadie. Y el caso peor era el de quien no tiene la semana montada: «0 de
    5 entrenos» con los siete días diciendo «Por decidir», porque ese 5 salía de la ficha.
    """

    def test_sin_ni_una_sesion_registrada_el_contador_se_calla(self, semana_montada, cabeceras_cliente):
        """El caso de producción: ningún registro suyo, ningún contador. La semana dice
        «N entrenos» (los previstos, que sí es verdad) y no «0 de N»."""
        db = _mongo()
        cid = _client_id(cabeceras_cliente, db)
        assert cid, "el cliente de prueba no tiene ficha"
        # Sus sesiones se apartan y se devuelven enteras (con su _id) al terminar.
        suyos = list(db.workout_logs.find({"client_id": cid}))
        if suyos:
            db.workout_logs.delete_many({"client_id": cid})
        try:
            r = _semana(cabeceras_cliente, FECHAS[0])["resumen"]
            assert r["entrenos_hechos"] is None, "sin sesiones registradas no se cuenta nada"
            assert r["entrenos_total"] >= 1, "los entrenos previstos sí se dicen"
        finally:
            if suyos:
                db.workout_logs.insert_many(suyos)

    def test_con_una_sesion_registrada_aparece_su_contador(self, semana_montada, cabeceras_cliente):
        """El límite: la condición es POR CLIENTE. Al que marca su primera sesión sí le
        sale «1 de N», y ese día se pinta como hecho."""
        db = _mongo()
        ajustes = db.app_settings.find_one({}, {"_id": 0, "pantallas": 1}) or {}
        if not (ajustes.get("pantallas") or {}).get("t3_entreno"):
            pytest.skip("t3_entreno apagado en esta base: no hay registro de sesiones")
        cid = _client_id(cabeceras_cliente, db)
        assert cid, "el cliente de prueba no tiene ficha"
        # Por si un run anterior se cortó antes de limpiar: (client_id, fecha) es índice
        # ÚNICO, así que la fila superviviente haría reventar el insert de todos los runs
        # siguientes con un error que no habla de este test.
        db.workout_logs.delete_one({"client_id": cid, "fecha": FECHAS[0]})
        db.workout_logs.insert_one({
            "id": "test-mi-semana-contador", "client_id": cid, "fecha": FECHAS[0],
            "hecho": True, "dia_rutina": None, "pesos": [],
        })
        try:
            data = _semana(cabeceras_cliente, FECHAS[0])
            assert data["resumen"]["entrenos_hechos"] == 1
            lunes = next(d for d in data["dias"] if d["fecha"] == FECHAS[0])
            assert lunes["entreno"]["hecho"] is True
        finally:
            db.workout_logs.delete_one({"id": "test-mi-semana-contador"})

    def test_una_semana_de_la_que_no_se_sabe_nada_no_promete_entrenos(self, api_disponible, cabeceras_cliente):
        """Sin dietas y sin rutina, los siete días dicen «Por decidir»: el titular no
        puede prometer entrenos que no están pintados en ninguna parte (el respaldo que
        se caía a los días de entreno de la ficha decía «4 entrenos» aquí)."""
        data = _semana(cabeceras_cliente, LUNES_VACIO.isoformat())
        # El respaldo solo entraba sin rutina y sin dietas. Si esta cuenta tiene rutina
        # activa, la semana sí se pinta y aquí no hay nada que comprobar: se dice y se
        # salta, que un test que pasa por no llegar a mirar es peor que no tenerlo.
        if any(d["tipo_dia"] is not None for d in data["dias"]):
            pytest.skip("la cuenta de prueba tiene rutina o dietas en esa semana: el respaldo no entraba ahí")
        assert data["resumen"]["entrenos_total"] == 0, "no se prometen entrenos que la semana no pinta"
        # Y sin ningún día de entreno tampoco se cuenta lo hecho: «0 de 0» no es un dato.
        assert data["resumen"]["entrenos_hechos"] is None
