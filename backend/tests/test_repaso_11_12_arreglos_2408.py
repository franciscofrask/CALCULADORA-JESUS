# -*- coding: utf-8 -*-
"""REPASO de los fallos 11 y 12 del 24-08: la invariante, no el texto del fichero.

Los dos arreglos son de pantalla y ya hay tests que miran el codigo JSX
(test_pantallas_arreglos_2408.py). Esto es lo otro: coger los datos DE VERDAD que la
pantalla recibe y comprobar sobre ellos que el fallo ya no puede ocurrir, y de paso que
sigue habiendo datos que lo ejercen (si no, un test verde no significa nada).

  11  LA FICHA DE CORTESIA. Se reproduce aqui el criterio VIEJO del aviso
      («ultimo_cobro y |precio_ciclo - cobro| >= 1», sin preguntar por la cortesia) sobre
      las fichas reales: si con los datos de hoy ese criterio sigue saltando en alguna
      cortesia, el fallo era real y el arreglo hace falta. Y se comprueba que el servidor
      manda `precio_cortesia` en todas ellas, que es la pregunta con la que la pantalla lo
      corta ahora.

  12  LAS PESTAÑAS DE CLIENTES. Se reproduce el reparto de la pantalla en Python sobre la
      respuesta real de /admin/clients y se exige que Activos + Fuera = Todos en las dos
      carteras y con los dos roles. Ademas se guarda la regresion nueva que el arreglo
      podria haber traido: que nadie con acceso vigente y con plan se quede en «Fuera».

Como pasarlos:
  cd backend && REACT_APP_BACKEND_URL=http://127.0.0.1:8000 \
      venv/Scripts/python.exe -m pytest tests/test_repaso_11_12_arreglos_2408.py -q
"""
import os
import pathlib
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"
FRONT = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src"

# El entrenador de pruebas del QA del 22-08. Sirve para el otro rol: al entrenador el
# servidor no le manda los registros sin terminar, y ahi el reparto tambien tiene que sumar.
COACH = ("coach.prueba@test.com", "QaPrueba2026!")


def fuente(relativo: str) -> str:
    return (FRONT / relativo).read_text(encoding="utf-8")


def pide(url, **kw):
    """GET con reintento: el backend de dev se reinicia solo cuando alguien toca un fichero,
    y un corte de dos segundos no es un fallo del arreglo. Sin esto, la bateria se cae con un
    ConnectionError que no dice nada de lo que se esta probando."""
    ultimo = None
    for _ in range(4):
        try:
            return requests.get(url, timeout=120, **kw)
        except requests.exceptions.ConnectionError as e:   # el servidor esta levantandose
            ultimo = e
            time.sleep(4)
    pytest.skip(f"El backend de dev no responde: {ultimo}")


# ---------------------------------------------------------------------------
# El reparto de AdminClientsList, tal cual esta en la pantalla. Si alguien lo cambia alli
# y no aqui, estos tests dejan de proteger nada: van juntos a proposito.
# ---------------------------------------------------------------------------
def tiene_acceso(c):
    return (c.get("acceso") or {}).get("activo") if c.get("acceso") else c.get("status") == "activo"


def esta_fuera(c):
    return c.get("status") == "registro_incompleto" or not c.get("plan") or not tiene_acceso(c)


def es_del_acceso(c, cual):
    if cual == "todos":
        return True
    return (not esta_fuera(c)) if cual == "activos" else esta_fuera(c)


def le_falta_entrenador(c):
    return bool(c["sin_entrenador"]) if "sin_entrenador" in c else not c.get("trainer_id")


def de_la_cartera(c, cartera):
    if cartera == "sin_coach":
        return le_falta_entrenador(c)
    return True


def cuantos_acceso(filas, cartera, cual):
    return sum(1 for c in filas
               if not c.get("es_tu_ficha") and de_la_cartera(c, cartera) and es_del_acceso(c, cual))


@pytest.fixture(scope="module")
def filas_admin(cabeceras_admin):
    r = pide(f"{API}/admin/clients?include_incomplete=true", headers=cabeceras_admin)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def filas_coach(api_disponible):
    r = requests.post(f"{API}/auth/login", json={"email": COACH[0], "password": COACH[1]}, timeout=60)
    if r.status_code != 200:
        pytest.skip("No hay entrenador de pruebas en esta base.")
    cab = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = pide(f"{API}/admin/clients?include_incomplete=true", headers=cab)
    assert r.status_code == 200, r.text
    return r.json()


# ==================== 12 · las pestañas suman, con los datos de verdad ====================


class TestLasPestanasSumanSobreLosDatosReales:
    @pytest.mark.parametrize("cartera", ["todos", "sin_coach"])
    def test_activos_mas_fuera_dan_todos(self, filas_admin, cartera):
        a = cuantos_acceso(filas_admin, cartera, "activos")
        f = cuantos_acceso(filas_admin, cartera, "fuera")
        t = cuantos_acceso(filas_admin, cartera, "todos")
        assert a + f == t, f"cartera {cartera}: Activos {a} + Fuera {f} no dan Todos {t}"
        assert t > 0, "sin filas este test no comprueba nada"

    def test_tambien_le_suman_al_entrenador(self, filas_coach):
        """Al entrenador el servidor no le manda los registros sin terminar, asi que su
        reparto es otro. Tenia que sumar igual y no se habia mirado."""
        for cartera in ("todos", "sin_coach"):
            a = cuantos_acceso(filas_coach, cartera, "activos")
            f = cuantos_acceso(filas_coach, cartera, "fuera")
            t = cuantos_acceso(filas_coach, cartera, "todos")
            assert a + f == t, f"entrenador, cartera {cartera}: {a} + {f} != {t}"
        assert not any(c.get("status") == "registro_incompleto" for c in filas_coach)

    def test_la_pestaña_cuenta_las_filas_que_enseña_menos_la_propia(self, filas_admin):
        """La regla del arreglo. La unica diferencia permitida entre el numero y las filas
        es la ficha del propio miembro del equipo (#56): se ve, pero no cuenta."""
        for cartera in ("todos", "sin_coach"):
            for cual in ("activos", "fuera", "todos"):
                filas = [c for c in filas_admin
                         if de_la_cartera(c, cartera) and es_del_acceso(c, cual)]
                propias = sum(1 for c in filas if c.get("es_tu_ficha"))
                assert cuantos_acceso(filas_admin, cartera, cual) == len(filas) - propias

    def test_el_criterio_viejo_seguiria_sin_cuadrar(self, filas_admin):
        """LA REPRODUCCION DEL FALLO 12. El de antes contaba «Todos» con `cuentaComoCliente`
        (sin los registros a medias) y «Fuera» con `!es_tu_ficha` (con ellos). Con los datos
        de hoy tiene que seguir descuadrando: si no, este fichero estaria dando por buena
        una base que ya no ejerce el fallo."""
        def viejo(cual):
            if cual == "todos":
                return sum(1 for c in filas_admin
                           if c.get("status") != "registro_incompleto" and not c.get("es_tu_ficha"))
            return sum(1 for c in filas_admin
                       if not c.get("es_tu_ficha") and es_del_acceso(c, cual))
        a, f, t = viejo("activos"), viejo("fuera"), viejo("todos")
        assert a + f != t, ("la base ya no tiene registros sin terminar: el fallo 12 no se "
                            "puede reproducir y este test no protege nada")
        # Y el arreglo, sobre esos mismos datos, si cuadra.
        assert (cuantos_acceso(filas_admin, "todos", "activos")
                + cuantos_acceso(filas_admin, "todos", "fuera")
                == cuantos_acceso(filas_admin, "todos", "todos"))

    def test_nadie_con_acceso_y_con_plan_se_queda_fuera(self, filas_admin):
        """LA REGRESION QUE PODIA TRAER EL ARREGLO. «Fuera» se amplio con `!c.plan` (Jesus,
        24-08). Si alguna fila con acceso vigente viniera sin plan por un hueco de datos, ese
        cliente desapareceria de «Activos», que es la pestaña que se abre: al que paga no se
        le pierde de vista."""
        colados = [c for c in filas_admin
                   if tiene_acceso(c) and c.get("status") != "registro_incompleto"
                   and not c.get("plan")]
        assert not colados, ("con acceso y sin plan: "
                             + ", ".join((c.get("user") or {}).get("email", "?") for c in colados[:5]))

    def test_la_nota_de_cuadre_sale_cuando_hay_algo_que_explicar(self, filas_admin):
        """La nota cuelga de `sinTerminarEnVista`, o sea del mismo dato que hace que las
        pestañas sumen mas que el total de clientes. Si hay registros a medias tiene que
        haber nota, y la resta que promete tiene que salir."""
        sin_terminar = sum(1 for c in filas_admin
                           if not c.get("es_tu_ficha") and c.get("status") == "registro_incompleto")
        if not sin_terminar:
            pytest.skip("No hay registros sin terminar en esta base.")
        clientes = sum(1 for c in filas_admin
                       if c.get("status") != "registro_incompleto" and not c.get("es_tu_ficha"))
        assert cuantos_acceso(filas_admin, "todos", "todos") == clientes + sin_terminar
        assert "cuadre-pestanas" in fuente("pages/AdminDashboard.jsx")


# ==================== 11 · la cortesia manda sobre el aviso de dinero ====================


def _fichas_de_cortesia(cabeceras):
    r = pide(f"{API}/admin/clients?include_incomplete=false", headers=cabeceras)
    r.raise_for_status()
    ids = [c["id"] for c in r.json() if c.get("id") and c.get("precio_fuente") == "cortesia"]
    fichas = []
    for cid in ids[:30]:
        d = pide(f"{API}/admin/clients/{cid}", headers=cabeceras)
        if d.status_code == 200:
            fichas.append((cid, d.json().get("profile") or {}))
    return fichas


@pytest.fixture(scope="module")
def cortesias(cabeceras_admin):
    fichas = _fichas_de_cortesia(cabeceras_admin)
    if not fichas:
        pytest.skip("No hay fichas de cortesia en esta base.")
    return fichas


def _aviso_viejo(perfil):
    """El criterio con el que el aviso `cobro-no-cuadra` saltaba antes del arreglo."""
    cobro = perfil.get("ultimo_cobro")
    return bool(cobro) and perfil.get("precio_ciclo") is not None \
        and abs(float(perfil["precio_ciclo"]) - float(cobro["importe"])) >= 1


class TestLaFichaDeCortesia:
    def test_el_aviso_viejo_seguia_saltando_en_alguna_cortesia(self, cortesias):
        """LA REPRODUCCION DEL FALLO 11, con los datos de hoy: hay fichas de cortesia en las
        que el criterio viejo dispara. Sobre esas mismas, la pantalla de ahora entra por la
        rama de la cortesia y el aviso no se pinta."""
        saltaban = [(cid, p) for cid, p in cortesias if _aviso_viejo(p)]
        assert saltaban, ("ninguna cortesia arrastra ya un cobro antiguo: el fallo 11 no se "
                          "puede reproducir y este test no protege nada")
        for cid, p in saltaban:
            assert p.get("precio_cortesia") is True, \
                f"{cid} dispara el aviso viejo y la pantalla no tiene con que callarlo"

    def test_para_el_negocio_toda_cortesia_cuenta_cero(self, cortesias):
        """Es la premisa del arreglo: el 0 de la ficha es una decision tomada en
        `importe_de_ciclo`, no un dato que falte, asi que la pantalla no puede llamarlo
        descuadre."""
        for cid, p in cortesias:
            assert p.get("precio_cortesia") is True, cid
            assert p.get("euros_al_mes") == 0, f"{cid} es de cortesia y cuenta {p.get('euros_al_mes')}"

    def test_el_cero_va_explicado_y_la_renovacion_tambien(self):
        """Las dos frases que ve quien esta a punto de llamar a alguien a pedirle dinero."""
        src = fuente("pages/ClientDetailPage.jsx")
        assert "cortesia-explicada" in src and "renovacion-cortesia" in src
        assert "no hay nada que cobrarle" in src

    def test_la_etiqueta_y_el_aviso_preguntan_por_el_mismo_campo(self):
        """El fallo era que dos trozos de la MISMA tarjeta decidian con datos distintos: la
        etiqueta «Cortesia» con `precio_cortesia` y el aviso con la resta. Mientras los dos
        pregunten por `precio_cortesia` no pueden volver a contradecirse."""
        src = fuente("pages/ClientDetailPage.jsx")
        assert "profile?.precio_cortesia ? 'Cortesía'" in src
        assert "{profile?.precio_cortesia ? (" in src

    def test_la_cortesia_con_stripe_vivo_es_el_unico_aviso_que_queda(self, cortesias):
        """Ahi el 0 del panel si seria mentira. Hoy no le pasa a nadie ni en dev ni en
        produccion, y por eso el aviso tiene que estar escrito para el dia que pase."""
        assert "cortesia-con-stripe" in fuente("pages/ClientDetailPage.jsx")
        for cid, p in cortesias:
            via = (p.get("renueva_solo") or {}).get("via")
            if via == "stripe":
                # No es un fallo del codigo, es un dato que hay que mirar: se avisa en claro.
                print(f"OJO: la cortesia {cid} tiene una suscripcion viva en Stripe")


# ==================== la casa ====================


def test_ninguno_de_los_dos_ficheros_lleva_guion_largo():
    for f in ("pages/AdminDashboard.jsx", "pages/ClientDetailPage.jsx"):
        src = fuente(f)
        assert "—" not in src and "–" not in src, f"{f} lleva guion largo"
