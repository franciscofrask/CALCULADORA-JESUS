# -*- coding: utf-8 -*-
"""
Casos 55-59 de la lista de 85 que entrego Jesus: seccion H, «MIS MACROS».

La pantalla del cliente al que los macros se los lleva su entrenador
(`frontend/src/pages/MisMacrosPage.jsx`, servida por `GET /api/macros/historial`). Lo que
Jesus pide comprobar:

    55 [CRITICO]  carga en menos de tres segundos y no pide el historial mas de una vez.
    56 [CRITICO]  un ajuste por fecha: ocho guardados del mismo dia se agrupan en uno.
    57 [CRITICO]  el comentario del ultimo ajuste es el que escribio el entrenador,
                  nunca un texto que empiece por TEST_.
    58            la tabla en un movil de 390 px no se corta por la derecha.
    59 [CRITICO]  el cliente con entrenador ve una pantalla de solo lectura.

COMO SE PRUEBA. Dos niveles a proposito:

  - LA REGLA, contra el modulo, con una base de mentira. Es deterministica y dice si la app
    sabe hacer lo que Jesus pide, sin depender de que la base de desarrollo tenga hoy el caso.

  - LO QUE PASA DE VERDAD, contra la API con el cliente de pruebas
    (`clientedemo@test.com`), que es exactamente el «cliente con entrenador» del caso 59.

El 58 no se automatiza: es de ojo y de regla, y fingirlo con un ancho en un test seria
mentirse. Va marcado como salteado con su motivo.

NADA DE ESTO ESCRIBE EN LA BASE. Ni siquiera el caso 59 intenta el PUT: lo que decide si la
pantalla es de solo lectura es `macros_ajustables.puede` del perfil, y probar el 403 dejaria
un ajuste escrito en un cliente compartido.
"""
import asyncio
import re
import time
from pathlib import Path

import pytest
import requests

from conftest import API, CLIENT_EMAIL, CLIENT_PASSWORD
from core.quien_pone_los_macros import puede_ajustarlos
from routes.users import _feedback_del_entrenador, get_mi_historial_de_macros

FRONT = Path(__file__).resolve().parents[2] / "frontend" / "src"

# El backend local recarga solo y se cae unos segundos cada vez que alguien toca un fichero.
INTENTOS = 15


def correr(coro):
    """No hay pytest-asyncio en el repo: se corre a mano, como en el resto de tests."""
    return asyncio.run(coro)


def pide(metodo, ruta, **kw):
    kw.setdefault("timeout", 90)
    ultimo = None
    for _ in range(INTENTOS):
        try:
            return requests.request(metodo, f"{API}{ruta}", **kw)
        except requests.RequestException as e:
            ultimo = e
            time.sleep(2)
    pytest.skip(f"el backend no responde en {ruta}: {ultimo}")


@pytest.fixture(scope="module")
def cabeceras_cliente():
    """El cliente de pruebas: plan `gold` (calculadora personalizada) y con entrenador."""
    r = pide("post", "/auth/login", json={"email": CLIENT_EMAIL, "password": CLIENT_PASSWORD})
    if r.status_code != 200:
        pytest.skip(f"no se pudo entrar como cliente ({r.status_code})")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def pantalla(cabeceras_cliente):
    r = pide("get", "/macros/historial", headers=cabeceras_cliente)
    assert r.status_code == 200, r.text
    return r.json()


# ── Una base de mentira, con lo justo que toca el endpoint ─────────────────────────────────

class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *a, **kw):
        return self     # las filas se le dan ya ordenadas

    async def to_list(self, n):
        return self._docs[:n]


class _Coleccion:
    def __init__(self, docs=None, uno=None):
        self._docs = docs or []
        self._uno = uno

    def find(self, *a, **kw):
        return _Cursor(self._docs)

    async def find_one(self, *a, **kw):
        return self._uno


class FakeDB:
    def __init__(self, perfil, entradas=None, dieta_de_hoy=None):
        self.client_profiles = _Coleccion(uno=perfil)
        self.macro_history = _Coleccion(docs=entradas or [])
        self.diets = _Coleccion(uno=dieta_de_hoy)


# `nivel2` es el plan con entrenador del catalogo vigente: calculadora «personalizado», que
# es el unico modo en el que se enseña el historico (TABLA 20).
CON_ENTRENADOR = {"id": "c1", "user_id": "u1", "plan": "nivel2", "pesos": []}


def guardado(fecha, hora, proteina, note=None, origen="manual", **kw):
    return {
        "id": f"{fecha}-{hora}",
        "client_id": "c1",
        "effective_date": fecha,
        "created_at": f"{fecha}T{hora}:00",
        "training": {"protein": proteina, "carbs": 300, "fat": 70},
        "rest": {"protein": proteina, "carbs": 240, "fat": 80},
        "peso": 82.0,
        "note": note,
        "origen": origen,
        **kw,
    }


def pintar(monkeypatch, perfil, entradas):
    """Lo que le llega a «Mis macros» con esas filas en la base."""
    import routes.users as users

    # Ordenadas como las devuelve Mongo en el endpoint: por vigencia y, a igualdad, por
    # cuando se guardo, de lo mas nuevo a lo mas viejo.
    filas = sorted(entradas, key=lambda e: (e["effective_date"], e["created_at"]), reverse=True)
    monkeypatch.setattr(users, "db", FakeDB(perfil, filas))
    return correr(get_mi_historial_de_macros(user={"id": "u1"}))


# ── Caso 55 ────────────────────────────────────────────────────────────────────────────────

class TestCaso55CargaRapidoYPideElHistorialUnaVez:
    """[CRITICO] Tres segundos es todo el presupuesto, y la llamada se lleva casi todo."""

    LIMITE = 3.0

    def test_el_historial_llega_en_menos_de_tres_segundos(self, cabeceras_cliente):
        """Se miden tres pasadas y manda la mediana: una sola medida en un portatil que
        ademas tiene la base en Atlas no dice nada."""
        tiempos = []
        for _ in range(3):
            t0 = time.time()
            r = pide("get", "/macros/historial", headers=cabeceras_cliente)
            tiempos.append(time.time() - t0)
            assert r.status_code == 200, r.text
        mediana = sorted(tiempos)[1]
        assert mediana < self.LIMITE, (
            f"la llamada tarda {mediana:.2f}s (medidas: "
            f"{', '.join(f'{t:.2f}' for t in tiempos)}) y ahi todavia no se ha pintado nada")

    def test_el_front_no_lo_pide_mas_de_una_vez(self):
        """El cliente HTTP se crea UNA vez y no en cada render.

        Media app pide sus datos con `useEffect(..., [api])`. Cuando `api` era un
        `axios.create` suelto en el cuerpo de `AuthContext`, nacia uno nuevo en cada repintado
        y esos efectos se volvian a disparar: «Mis macros» pedia su historial TRES veces al
        abrirse. Se arreglo el 10-08 metiendolo en un `useMemo`; esto es el cerrojo para que
        no vuelva, porque el sintoma solo se ve con el panel de red abierto.
        """
        ruta = FRONT / "context" / "AuthContext.jsx"
        if not ruta.exists():
            pytest.skip(f"no encuentro {ruta}")
        texto = ruta.read_text(encoding="utf-8")
        assert re.search(r"const\s+api\s*=\s*useMemo\(", texto), (
            "el cliente HTTP ha vuelto a crearse en cada render: «Mis macros» pedira su "
            "historial una vez por repintado")


# ── Caso 56 ────────────────────────────────────────────────────────────────────────────────

class TestCaso56UnAjustePorFecha:
    """[CRITICO] Ocho guardados del mismo dia son UN ajuste corregido ocho veces.

    Al ESCRIBIR ya esta resuelto desde el punto 62 (`core/historial_macros.guardar` sustituye
    la fila del dia en vez de añadir otra, ver `test_historial_una_por_dia`). Lo que estos
    tests miran es lo que se LEE, que es lo que Jesus abre: las filas que ya estaban
    duplicadas antes de aquello siguen en la base y la pantalla las pinta todas.
    """

    def test_ocho_guardados_del_mismo_dia_salen_como_uno(self, monkeypatch):
        filas = [guardado("2026-06-30", f"19:{40 + i}", 200 + i * 10) for i in range(8)]
        datos = pintar(monkeypatch, CON_ENTRENADOR, filas)
        del_dia = [e for e in datos["entradas"] if e["fecha"] == "2026-06-30"]
        assert len(del_dia) == 1, (
            f"la tabla enseña {len(del_dia)} filas para el 30/06: son ocho guardados de un "
            "mismo ajuste, no ocho ajustes")

    def test_y_la_que_queda_es_la_ultima(self, monkeypatch):
        """Manda la correccion, no el primer intento: los estados de en medio no existieron."""
        filas = [guardado("2026-06-30", f"19:{40 + i}", 200 + i * 10) for i in range(8)]
        datos = pintar(monkeypatch, CON_ENTRENADOR, filas)
        del_dia = [e for e in datos["entradas"] if e["fecha"] == "2026-06-30"]
        assert del_dia[0]["entreno"]["proteina"] == 270

    def test_dias_distintos_siguen_siendo_filas_distintas(self, monkeypatch):
        """El agrupado no puede comerse la escalera, que es lo que la tabla cuenta."""
        filas = [guardado(f, "19:40", p) for f, p in
                 [("2026-06-30", 200), ("2026-07-15", 210), ("2026-07-30", 220)]]
        datos = pintar(monkeypatch, CON_ENTRENADOR, filas)
        assert len(datos["entradas"]) == 3

    def test_en_la_base_de_verdad_tampoco_se_repite_ninguna_fecha(self, pantalla):
        """Lo mismo, contra la API. Aqui es donde se ve el arrastre de lo ya guardado."""
        vistas, repetidas = set(), []
        for e in pantalla["entradas"]:
            (repetidas.append(e["fecha"]) if e["fecha"] in vistas else vistas.add(e["fecha"]))
        assert not repetidas, f"fechas que salen mas de una vez en la tabla: {sorted(set(repetidas))}"


# ── Caso 57 ────────────────────────────────────────────────────────────────────────────────

class TestCaso57ElComentarioEsElDeSuEntrenador:
    """[CRITICO] Lo de «lo que te dijimos en este ajuste» tiene que ser algo que se le dijo."""

    def test_la_nota_del_entrenador_si_sale(self):
        nota = "Subimos hidratos el fin de semana, que llegas justo al entreno."
        assert _feedback_del_entrenador({"note": nota, "origen": "manual"}) == nota

    @pytest.mark.parametrize("nota", [
        "TEST_Ajuste semanal por progreso",
        "TEST_Segundo ajuste",
        "TEST_Restauracion valores originales",
    ])
    def test_pero_un_texto_de_pruebas_nunca(self, nota):
        """Los deja cualquiera probando la app: se guardan con `origen: manual` y firmados
        con un nombre del equipo, asi que por dentro son indistinguibles de un consejo. En la
        base de desarrollo hay 76 filas asi, todas del cliente de pruebas."""
        assert _feedback_del_entrenador({"note": nota, "origen": "manual",
                                         "changed_by": "Francisco"}) is None, (
            f"«{nota}» se le enseña al cliente entrecomillado como si se lo hubiera escrito "
            "su entrenador")

    def test_el_ultimo_ajuste_de_verdad_no_trae_un_texto_de_pruebas(self, pantalla):
        vigente = pantalla.get("vigente") or {}
        feedback = vigente.get("feedback") or ""
        assert not feedback.startswith("TEST_"), (
            f"el comentario de su ultimo ajuste ({vigente.get('fecha')}) es «{feedback}»")

    def test_ni_ninguno_de_los_que_viajan_a_su_pantalla(self, pantalla):
        """La tabla del historico hoy no pinta el comentario, pero el navegador del cliente
        se los descarga igual: son suyos en cuanto salen del servidor."""
        malos = [(e["fecha"], e["feedback"]) for e in pantalla["entradas"]
                 if (e.get("feedback") or "").startswith("TEST_")]
        assert not malos, f"{len(malos)} comentarios de pruebas en su historial: {malos[:3]}"


# ── Caso 58 ────────────────────────────────────────────────────────────────────────────────

@pytest.mark.skip(reason="visual: la tabla del historico a 390 px se mira en el navegador. "
                         "Lo que hay que ver es si la fila entera cabe o si el contenedor "
                         "`overflow-x-auto` de MisMacrosPage.jsx se desplaza solo, y eso no "
                         "se decide leyendo el `min-w-[520px]` de la clase.")
def test_caso_58_la_tabla_en_un_movil_de_390_px():
    raise AssertionError("sin comprobar")


# ── Caso 59 ────────────────────────────────────────────────────────────────────────────────

HOY = "2026-08-12"


def perfil_con_entrenador(**kw):
    return {"id": "c1", "plan": "nivel2", "status": "activo", "trainer_id": "t1", **kw}


class _HistorialFalso:
    """Lo justo para `puede_ajustarlos`, que resuelve el ajuste vigente por `effective_date`."""

    def __init__(self, apuntes):
        self.macro_history = self._Col(apuntes)

    class _Col:
        def __init__(self, docs):
            self._docs = docs

        def find(self, *a, **kw):
            return self._Cursor(self._docs)

        async def find_one(self, *a, **kw):
            return self._docs[0] if self._docs else None

        class _Cursor:
            def __init__(self, docs):
                self._docs = docs

            async def to_list(self, _n=None):
                return list(self._docs)


class TestCaso59LaPantallaEsDeSoloLectura:
    """[CRITICO] En su plan los macros los lleva alguien: no hay nada que el pueda tocar.

    Quien decide si la pantalla es un formulario o «Mis macros» es el servidor, con
    `macros_ajustables.puede` del perfil: `MacroCalculatorClientPage.jsx` hace
    `if (!puedeAjustar) return <MisMacrosPage />`. Asi que basta con mirar ese campo.
    """

    def test_si_se_los_lleva_su_entrenador_no_puede_tocarlos(self):
        apuntes = [{"origen": "manual", "changed_by": "Jesus Gallego",
                    "effective_date": "2026-07-15"}]
        puede, motivo = correr(puede_ajustarlos(_HistorialFalso(apuntes), perfil_con_entrenador()))
        assert puede is False and motivo

    def test_y_no_deja_de_llevarselos_porque_el_guarde_una_vez(self):
        """El agujero: la regla mira SOLO el apunte vigente. A un cliente al que su entrenador
        lleva ajustando desde marzo le basta con pasar una vez por el cuestionario para que su
        ultimo apunte sea `quiz_ajuste` -- lo escribe la app, no una persona -- y la pantalla
        vuelve a ser el formulario editable, con su boton de Guardar, hasta que el entrenador
        escriba otra vez. Es justo el caso del cliente de pruebas hoy."""
        apuntes = [
            {"origen": "manual", "changed_by": "Jesus Gallego", "effective_date": "2026-03-02"},
            {"origen": "manual", "changed_by": "Jesus Gallego", "effective_date": "2026-07-15"},
            {"origen": "quiz_ajuste", "changed_by": None, "effective_date": HOY},
        ]
        puede, _ = correr(puede_ajustarlos(_HistorialFalso(apuntes), perfil_con_entrenador()))
        assert puede is False, (
            "un cliente con entrenador recupera la calculadora editable por haber pasado una "
            "vez por el cuestionario: su historial entero lo escribio su entrenador")

    def test_el_cliente_de_pruebas_ve_la_pantalla_cerrada(self, cabeceras_cliente):
        r = pide("get", "/clients/profile", headers=cabeceras_cliente)
        assert r.status_code == 200, r.text
        p = r.json()
        if not p.get("trainer_id"):
            pytest.skip("el cliente de pruebas ya no tiene entrenador asignado")
        ajustables = p.get("macros_ajustables") or {}
        assert ajustables.get("puede") is False, (
            f"a un cliente con entrenador (plan {p.get('plan')!r}) se le enseña la "
            f"calculadora editable: {ajustables}")

    def test_y_con_un_motivo_escrito_para_el(self, cabeceras_cliente):
        """Sin explicacion, una pantalla sin botones parece una pantalla rota."""
        r = pide("get", "/clients/profile", headers=cabeceras_cliente)
        ajustables = (r.json() or {}).get("macros_ajustables") or {}
        if ajustables.get("puede") is not False:
            pytest.skip("no esta cerrada: lo cuenta el test de arriba")
        assert (ajustables.get("por_que_no") or "").strip()
