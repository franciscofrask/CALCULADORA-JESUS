# -*- coding: utf-8 -*-
"""Repaso de los arreglos 5 a 9 del 24-08: lo que faltaba por probar POR FUERA.

Los arreglos ya tienen sus pruebas de dentro (`test_peso_y_cierre_arreglos_2408.py`), que
miran las funciones y el codigo fuente. Estas son las de fuera: la peticion de verdad
contra el servidor y el dato que queda en la base despues, que es donde se vio el fallo la
primera vez.

  5. El reporte no puede borrar un pesaje. Se prueba por LA PUERTA DEL EQUIPO
     (`POST /admin/clients/{id}/reporte`), que es la unica de las dos que se puede llamar
     cualquier dia: la del cliente solo abre en su ventana. Las dos llaman a la misma
     linea, con el mismo `pisa_pesajes=False`.

  6. La frase del peso del reporte no puede dejar al cliente sin saber cuanto pesaba: o el
     kilo esta en la casilla, o esta en la frase. Se prueba como invariante, para que valga
     tambien para la rama que se invente el que venga detras.

  7. El pesaje se archiva EL DIA QUE DICE EL CLIENTE. Se comprueba en la serie del perfil,
     que es lo que de verdad importa: `_dia_del_pesaje` puede devolver la fecha buena y que
     luego nadie la use.

  9. Reeditar no puede duplicar la fila del dia. El arreglo toca el camino del
     `replace_one`, y dos filas del mismo dia cuentan doble en todo lo que lea la coleccion.

Todo lo que tocan estas pruebas se devuelve como estaba: la serie de pesos del cliente, su
cierre de hoy y los reportes que se crean por el camino.
"""
import os
import time
import uuid
from datetime import date, timedelta

import pytest
import requests

from core.datos_reporte import de_donde_sale_el_peso
from core.series_cliente import DIAS_ATRAS_PARA_UN_PESAJE, peso_semanal
from core.tiempo import hoy_madrid
# `from conftest import`, NO `from tests.conftest import`, y no es cosmetico: son DOS
# modulos distintos para Python (`conftest` y `tests.conftest`), cada uno con SU
# `BUCLE = asyncio.new_event_loop()`. Los otros 43 ficheros de la bateria entran por el
# primero, este entraba por el segundo, y con dos bucles el cliente de Motor -- que se queda
# con el de su primera consulta -- acababa atado a uno mientras aqui se corria en el otro:
# tres tests en rojo y tres en error con «Event loop is closed», verdes en solitario. Se
# reproduce con `pytest tests/test_circuitos_2408.py tests/test_repaso_peso_cierre_arreglos_2408.py`.
from conftest import CLIENT_EMAIL, corre

API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/") + "/api"


def _pedir(metodo, ruta, reintentos=4, **kwargs):
    """requests con paciencia: el backend de dev se reinicia solo cuando alguien guarda un
    .py, y un ConnectionError en ese instante no es un fallo del arreglo."""
    kwargs.setdefault("timeout", 30)
    ultimo = None
    for _ in range(reintentos):
        try:
            return requests.request(metodo, f"{API}{ruta}", **kwargs)
        except requests.RequestException as e:      # noqa: PERF203
            ultimo = e
            time.sleep(3)
    raise ultimo


# ─────────────────────────────────────────────────────────────────────────────
# Utiles de base. El cliente es el mismo de conftest, y se le deja como estaba.
# ─────────────────────────────────────────────────────────────────────────────

async def _perfil():
    from core.database import db
    u = await db.users.find_one({"email": CLIENT_EMAIL}, {"_id": 0, "id": 1})
    return await db.client_profiles.find_one({"user_id": u["id"]},
                                             {"_id": 0, "id": 1, "pesos": 1, "weight": 1})


async def _poner_serie(client_id, serie):
    from core.database import db
    from core.series_cliente import actual
    a = actual(serie)
    await db.client_profiles.update_one(
        {"id": client_id},
        {"$set": {"pesos": serie, "weight": a["valor"] if a else None}})


async def _serie(client_id):
    from core.database import db
    p = await db.client_profiles.find_one({"id": client_id}, {"_id": 0, "pesos": 1, "weight": 1})
    return {q["fecha"]: q for q in (p.get("pesos") or [])}, p.get("weight")


@pytest.fixture
def cliente_con_serie_limpia(api_disponible):
    """Presta la serie de pesos del cliente de pruebas y la devuelve intacta al acabar."""
    perfil = corre(_perfil())
    guardada = perfil.get("pesos")
    peso_guardado = perfil.get("weight")
    yield perfil["id"]
    corre(_poner_serie(perfil["id"], guardada or []))
    if not guardada:
        from core.database import db
        corre(db.client_profiles.update_one({"id": perfil["id"]},
                                            {"$set": {"weight": peso_guardado}}))


@pytest.fixture
def cierre_de_hoy_prestado(api_disponible):
    """Igual con el cierre del dia: se devuelve el que hubiera."""
    from core.database import db
    perfil = corre(_perfil())
    dia = hoy_madrid().isoformat()
    previo = corre(db.checkins.find_one({"client_id": perfil["id"], "type": "daily"},
                                        {"_id": 0}, sort=[("created_at", -1)]))
    yield perfil["id"]
    corre(db.checkins.delete_many({"client_id": perfil["id"], "type": "daily", "dia": dia}))
    if previo and previo.get("dia") == dia:
        corre(db.checkins.insert_one(dict(previo)))


# ============ 5. EL REPORTE NO BORRA UN PESAJE (por la puerta del equipo) ============

class TestElReporteQueMeteElEquipoNoBorraElPesaje:
    """Lo que se vio: serie con 80,0 y 82,0, el reporte propone 81,0 y al enviarlo el 82,0
    que el cliente se peso de verdad desaparecia. Aqui se manda el reporte de verdad."""

    def _mandar_reporte(self, cabeceras_admin, client_id, kilos):
        from core.database import db
        r = _pedir("POST", f"/admin/clients/{client_id}/reporte", headers=cabeceras_admin,
                   json={"tipo": "mensual", "weight": kilos,
                         "notes": f"prueba del repaso 24-08 {uuid.uuid4().hex[:6]}"})
        assert r.status_code == 200, r.text
        rid = r.json()["id"]
        # El reporte de prueba no se queda en la base del cliente.
        corre(db.reports.delete_one({"id": rid}))
        return rid

    def test_el_pesaje_de_hoy_sigue_siendo_el_del_cliente(
            self, api_disponible, cabeceras_admin, cliente_con_serie_limpia):
        cid = cliente_con_serie_limpia
        hoy = hoy_madrid()
        ayer = (hoy - timedelta(days=1)).isoformat()
        serie = [{"fecha": ayer, "valor": 80.0, "origen": "check-in daily"},
                 {"fecha": hoy.isoformat(), "valor": 82.0, "origen": "check-in daily"}]
        corre(_poner_serie(cid, serie))
        antes = peso_semanal(serie, hoy)["valor"]

        self._mandar_reporte(cabeceras_admin, cid, 81.0)

        puntos, peso = corre(_serie(cid))
        assert puntos[hoy.isoformat()]["valor"] == 82.0, \
            "el reporte se ha llevado por delante el pesaje de la bascula"
        assert puntos[hoy.isoformat()]["origen"] == "check-in daily"
        assert peso == 82.0, "y el peso del perfil tiene que ser el pesaje, no el del reporte"
        # Y el peso de la semana es el mismo que antes de mandarlo: enviar un reporte no
        # puede cambiar el numero que ese mismo reporte estaba resumiendo.
        assert peso_semanal(list(puntos.values()), hoy)["valor"] == antes

    def test_si_hoy_no_hay_pesaje_el_reporte_si_lo_escribe(
            self, api_disponible, cabeceras_admin, cliente_con_serie_limpia):
        """El candado no puede cargarse el caso normal: sin pesaje ese dia, el peso del
        reporte es lo unico que hay y tiene que entrar en la curva."""
        cid = cliente_con_serie_limpia
        hoy = hoy_madrid()
        corre(_poner_serie(cid, [{"fecha": (hoy - timedelta(days=1)).isoformat(),
                                  "valor": 80.0, "origen": "check-in daily"}]))

        self._mandar_reporte(cabeceras_admin, cid, 81.0)

        puntos, peso = corre(_serie(cid))
        assert puntos[hoy.isoformat()]["valor"] == 81.0
        assert puntos[hoy.isoformat()]["origen"] == "reporte (lo metió el equipo)"
        assert peso == 81.0

    def test_dos_reportes_seguidos_no_mueven_el_peso(
            self, api_disponible, cabeceras_admin, cliente_con_serie_limpia):
        """El reenvio era lo que hacia bajar el numero cada vez (81,0 -> 80,5 -> 80,2)."""
        cid = cliente_con_serie_limpia
        hoy = hoy_madrid()
        corre(_poner_serie(cid, [{"fecha": hoy.isoformat(), "valor": 82.0,
                                  "origen": "check-in daily"}]))
        for _ in range(3):
            self._mandar_reporte(cabeceras_admin, cid, 81.0)
        puntos, _ = corre(_serie(cid))
        assert puntos[hoy.isoformat()]["valor"] == 82.0
        assert len(puntos) == 1, "y no se ha colado ningun punto de mas"


# ============ 6. LA FRASE DEL PESO NUNCA DEJA AL CLIENTE SIN SU NUMERO ============

class TestElClienteSiempreVeSuPeso:
    """El fallo fue quitarle los kilos a la frase de la rama «ultimo», que es justo la rama
    en la que la casilla se deja vacia. La regla, dicha de una vez y para todas las ramas:
    o el kilo va en la casilla, o va en la frase."""

    LUNES = date(2026, 8, 10)

    @pytest.mark.parametrize("serie,dia", [
        ([("2026-08-13", 80.0), ("2026-08-14", 82.0)], LUNES),          # pareja
        ([("2026-08-12", 79.4)], LUNES),                                # media de uno
        ([("2026-08-11", 80.0), ("2026-08-13", 81.0)], LUNES),          # media de dos
        ([("2026-08-05", 84.0)], LUNES),                                # ultimo conocido
    ])
    def test_o_el_kilo_esta_en_la_casilla_o_esta_en_la_frase(self, serie, dia):
        ps = peso_semanal([{"fecha": f, "valor": v} for f, v in serie], dia)
        frase = de_donde_sale_el_peso(ps)
        # La pantalla escribe el numero en la casilla solo si el peso es de esta semana
        # (ReporteQuincenal.jsx, `mediaPuesta`).
        en_la_casilla = bool(ps["de_esta_semana"])
        assert en_la_casilla or "kg" in frase, \
            f"la casilla sale vacia y la frase no dice el peso: «{frase}»"

    def test_mas_de_catorce_dias_sin_pesarse_no_inventa_una_frase(self):
        """Y entonces la pantalla vuelve a «Ultimo registro: X kg, el ...», que es la linea
        de siempre y sigue en el codigo. Sin este corte, la frase hablaria de un peso de
        hace meses como si fuera el de la semana."""
        viejo = [{"fecha": (self.LUNES - timedelta(days=40)).isoformat(), "valor": 84.0}]
        assert peso_semanal(viejo, self.LUNES) is None


# ============ 7. EL PESAJE SE ARCHIVA EL DIA QUE DICE EL CLIENTE ============

class TestElPesajeSeGuardaEnSuDia:
    """La regla vive en la serie, el servidor la publica (`peso_dias_atras`) y la pantalla
    ofrece eso. Falta lo importante: que el dato acabe en ese dia de la serie."""

    def _guardar(self, cabeceras_cliente, dia, peso_fecha):
        return _pedir("POST", "/checkins", headers=cabeceras_cliente,
                      json={"type": "daily", "fecha": dia, "sensaciones": 3,
                            "weight": 77.7, "peso_fecha": peso_fecha})

    def test_el_servidor_ofrece_y_acepta_los_mismos_dias(
            self, api_disponible, cabeceras_cliente, cliente_con_serie_limpia,
            cierre_de_hoy_prestado):
        cid = cliente_con_serie_limpia
        hoy = _pedir("GET", "/checkins/hoy", headers=cabeceras_cliente).json()
        dia = hoy["fecha"]
        atras = hoy["peso_dias_atras"]
        assert atras == DIAS_ATRAS_PARA_UN_PESAJE

        el_limite = (date.fromisoformat(dia) - timedelta(days=atras)).isoformat()
        corre(_poner_serie(cid, []))
        assert self._guardar(cabeceras_cliente, dia, el_limite).status_code == 200
        puntos, _ = corre(_serie(cid))
        assert el_limite in puntos, \
            "el ultimo dia del desplegable tiene que llegar a la serie con SU fecha"
        assert puntos[el_limite]["valor"] == 77.7

    def test_lo_que_no_cabe_en_la_regla_se_archiva_en_el_dia_del_cierre(
            self, api_disponible, cabeceras_cliente, cliente_con_serie_limpia,
            cierre_de_hoy_prestado):
        """Una fecha imposible no puede tumbar el cierre del dia de nadie: se ignora en
        silencio y manda el dia del cierre."""
        cid = cliente_con_serie_limpia
        dia = _pedir("GET", "/checkins/hoy", headers=cabeceras_cliente).json()["fecha"]
        demasiado = (date.fromisoformat(dia)
                     - timedelta(days=DIAS_ATRAS_PARA_UN_PESAJE + 1)).isoformat()
        for fecha_mala in (demasiado,
                           (date.fromisoformat(dia) + timedelta(days=1)).isoformat(),
                           "ayer"):
            corre(_poner_serie(cid, []))
            assert self._guardar(cabeceras_cliente, dia, fecha_mala).status_code == 200
            puntos, _ = corre(_serie(cid))
            assert list(puntos) == [dia], f"con «{fecha_mala}» quedo {list(puntos)}"


# ============ 9. REEDITAR NO DUPLICA LA FILA DEL DIA ============

class TestReeditarNoDuplicaElDia:
    def test_tres_envios_del_mismo_dia_son_una_sola_fila(
            self, api_disponible, cabeceras_cliente, cierre_de_hoy_prestado):
        """El arreglo de los huerfanos toca el camino del `replace_one`. Dos filas del mismo
        dia cuentan doble en el historial, en la ficha del entrenador y en los avisos."""
        from core.database import db

        cid = cierre_de_hoy_prestado
        dia = _pedir("GET", "/checkins/hoy", headers=cabeceras_cliente).json()["fecha"]
        marca = f"lo escribio el cliente {uuid.uuid4().hex[:6]}"
        _pedir("POST", "/checkins", headers=cabeceras_cliente,
               json={"type": "daily", "fecha": dia, "sensaciones": 4, "comido_hoy": marca})
        for estrellas in (3, 5):
            r = _pedir("POST", "/checkins", headers=cabeceras_cliente,
                       json={"type": "daily", "fecha": dia, "sensaciones": estrellas})
            assert r.status_code == 200

        filas = corre(db.checkins.count_documents(
            {"client_id": cid, "type": "daily", "dia": dia}))
        assert filas == 1, f"{filas} filas para el mismo dia"
        fila = corre(db.checkins.find_one({"client_id": cid, "type": "daily", "dia": dia},
                                          {"_id": 0}))
        assert fila["sensaciones"] == 5
        assert fila["comido_hoy"] == marca
