# -*- coding: utf-8 -*-
"""
Seccion G del repaso de Jesus (12-08-2026): SEGUIMIENTO, casos 47 a 54.

Son sus 85 casos de prueba escritos como los cuenta el: "abro tal pantalla y espero ver
tal cosa". Aqui se fija la parte que DECIDE EL BACKEND, que es la que se puede sostener
en el tiempo; lo que solo se ve (colores, tarjetas apagadas) queda marcado como visual
con el fichero del front donde vive, para que se sepa donde mirar.

Los ocho casos, tal como los escribio:

  47. Abrir Seguimiento con la ventana del reporte abierta -> tarjeta de arriba en
      naranja, con la fecha limite, y el resto en gris.
  48. [CRITICO] Ventana cerrada -> no ensena el formulario apagado: dice cuando se abre,
      con fecha.
  49. [CRITICO] Reporte ya mandado -> dice "ya lo mandaste" y no ofrece "empezar".
  50. Check-in diario -> dos campos y nada mas; se guarda y se ve en el historial del dia.
  51. [CRITICO] Reporte mensual completo -> exige las diez medidas y las tres fotos. No
      deja mandar medio.
  52. "Mi evolucion" con un solo pesaje -> no dibuja una grafica de un punto: dice que
      hace falta otro pesaje.
  53. [CRITICO] Historial con varios reportes -> un reporte por fecha. No salen cuatro
      tarjetas iguales del mismo dia.
  54. Informe del mes -> cruza dietas, check-ins y macros del periodo y sale sin errores.

QUE FALLA HOY (a proposito: el test se queda fallando, no se ajusta para que pase):
  - 51: el backend no exige NADA salvo el peso, y las tres fotos que sube el cliente
        quedan en `client_photos` sin engancharse al reporte.
  - 53: el historial del cliente demo trae cuatro reportes identicos del 23 de julio.

Los datos que crean estas pruebas van marcados con MARCA y se borran al terminar; ademas
hay una limpieza de red al final del modulo por si algo revienta a mitad.
"""
import asyncio
import base64
import os
import sys
import time
import uuid
from datetime import datetime, timezone

import pytest
import requests

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

# El .env se carga aqui arriba y no dentro de cada test: si se carga tarde, MONGO_URL no
# esta cuando se resuelven los fixtures y las pruebas se saltan en silencio, que parece
# que pasan.
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(_RAIZ, ".env"))

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"

# Marca de los datos de prueba: todo lo que se inserta la lleva y por ella se borra.
MARCA = "TEST_G_SEGUIMIENTO"

# Las diez medidas de Jesus. Hoy solo existen en el front (frontend/src/lib/medidas.js):
# el backend no sabe que son diez ni cuales son, que es justo lo que destapa el caso 51.
DIEZ_MEDIDAS = ["hombros", "mesoesternal", "brazo_d", "brazo_i", "muslo_d", "muslo_i",
                "cadera", "cintura", "gemelo_d", "gemelo_i"]

# Un PNG de 1x1: al endpoint de fotos solo le importa el content-type y el tamano.
PNG_MINIMO = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


# ==================== fontaneria ====================

def _con_mongo(hacer):
    """Ejecuta `hacer(db)` con su propio cliente de Mongo.

    El cliente se crea DENTRO del asyncio.run: motor se queda pegado al bucle en el que
    nace, y reutilizar uno de un asyncio.run anterior revienta con "Event loop is closed".
    """
    async def _run():
        from motor.motor_asyncio import AsyncIOMotorClient
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "jg12_restored")]
        return await hacer(db)

    return asyncio.run(_run())


def _hay_mongo() -> bool:
    return bool(os.environ.get("MONGO_URL"))


def _pide(metodo: str, ruta: str, **kw):
    """Una llamada a la API, reintentando si la conexion se cae.

    El backend de desarrollo se reinicia solo con watchfiles cada vez que se guarda un
    .py (start_server.py, RELOAD=1), y el reinicio tarda unos segundos. Sin esto, guardar
    un fichero mientras corre la suite deja media seccion en rojo por algo que no tiene
    nada que ver con lo que se esta probando. Solo se reintenta cuando NO hubo respuesta:
    un 4xx o un 5xx llega tal cual al test.
    """
    kw.setdefault("timeout", 60)
    ultimo = None
    for _ in range(8):          # hasta ~40 s: lo que tarda en volver un reinicio
        try:
            return requests.request(metodo, f"{API}{ruta}", **kw)
        except requests.ConnectionError as e:
            ultimo = e
            time.sleep(5)
    raise ultimo


@pytest.fixture(scope="module")
def cliente(cabeceras_cliente):
    """El cliente demo, con su token y su client_id (sale de sus propios reportes)."""
    r = _pide("GET", "/reports", headers=cabeceras_cliente)
    assert r.status_code == 200, f"GET /reports no responde: {r.status_code} {r.text[:200]}"
    reportes = r.json()
    if not reportes:
        pytest.skip("El cliente de prueba no tiene ningun reporte: no hay de donde sacar su client_id.")
    return {"headers": cabeceras_cliente, "client_id": reportes[0]["client_id"],
            "reportes": reportes}


@pytest.fixture(scope="module")
def ventana(cliente):
    """El estado de la ventana HOY, tal como lo da el backend."""
    r = _pide("GET", "/reports/due", headers=cliente["headers"])
    assert r.status_code == 200, f"GET /reports/due responde {r.status_code}"
    return r.json()


def _mete_reporte(client_id, *, fotos=None):
    """Mete un reporte de hoy directamente en la base y devuelve su id.

    Se escribe en Mongo y no por POST /reports a proposito: la ventana de envio esta
    cerrada casi todos los dias de la semana, asi que por la ruta del cliente estas
    pruebas solo se podrian correr de viernes a lunes. Y por la ruta del equipo
    (POST /admin/clients/{id}/reporte) se moverian el peso de la serie, la fase del
    perfil y `ultimo_reporte`, que es ensuciar al cliente para probar una lectura.
    """
    rid = f"{MARCA}_{uuid.uuid4().hex[:8]}"
    doc = {
        "id": rid, "client_id": client_id, "weight": 75.0,
        "measurements": {"cintura": 82.0}, "photos": fotos,
        "notes": MARCA, "created_at": datetime.now(timezone.utc).isoformat(),
    }

    async def _ins(db):
        await db.reports.insert_one(dict(doc))

    _con_mongo(_ins)
    return rid


def _borra_reporte(rid):
    async def _del(db):
        return (await db.reports.delete_many({"id": rid})).deleted_count

    return _con_mongo(_del)


@pytest.fixture(scope="module", autouse=True)
def limpieza_final():
    """Red de seguridad: si un test revienta a mitad, lo que dejo puesto se va igual."""
    yield
    if not _hay_mongo():
        return

    async def _limpia(db):
        return (
            (await db.reports.delete_many({"notes": MARCA})).deleted_count,
            (await db.checkins.delete_many({"notes": MARCA})).deleted_count,
            (await db.client_photos.delete_many({"filename": f"{MARCA}.png"})).deleted_count,
        )

    print(f"Limpieza final (reportes, check-ins, fotos): {_con_mongo(_limpia)}")


# ==================== 47 y 48: la ventana, sin depender del dia que se ejecute ====================
#
# El estado lo decide `compute_client_report_state`, que es una funcion pura: se le da el
# perfil, el catalogo y un instante, y dice si toca reporte y si la ventana esta abierta.
# Probarla con fechas fijas es lo unico que hace que el caso 47 se pueda comprobar un
# martes, que es cuando falta.

ANCLA = "2026-06-01T09:00:00+00:00"        # un lunes
CATALOGO = {"plan_de_prueba": {"habilitaciones": {"reportes": ["mensual"]}}}
PERFIL = {"id": "perfil_de_prueba", "plan": "plan_de_prueba",
          "cycle_start": ANCLA, "status": "activo"}


def _estado(cuando: str):
    from routes.report_cadence import compute_client_report_state
    return compute_client_report_state(PERFIL, CATALOGO, datetime.fromisoformat(cuando))


class TestCaso47VentanaAbierta:
    """47. Seguimiento con la ventana del reporte abierta."""

    def test_47_con_la_ventana_abierta_toca_reporte_y_hay_fecha_limite(self):
        # Sabado de la semana 3 del ciclo: el mensual toca y la ventana (viernes 10:00 ->
        # lunes 18:00, el reloj del doc del 19-08) esta abierta.
        #
        # ESTE TEST CODIFICABA LA VENTANA VIEJA (viernes 00:00 -> lunes 06:00, en UTC) y
        # llevaba en rojo desde que el 19-08 la movio; se actualizo el 21-08 al repasar
        # las ventanas del semanal. Lunes 18:00 de Madrid en junio son las 16:00 UTC.
        e = _estado("2026-06-20T12:00:00+00:00")
        assert e["due"] is True, "en la semana del mensual tiene que tocar reporte"
        assert e["tipos"] == ["mensual"]
        assert e["is_open"] is True, "el sabado de esa semana la ventana esta abierta"
        # La fecha limite es lo que Jesus quiere leer en la tarjeta de arriba.
        assert e["window_close"] == datetime.fromisoformat("2026-06-22T16:00:00+00:00"), \
            "la ventana cierra el lunes a las 18:00 de España"

    def test_47_la_semana_que_no_toca_no_hay_tarjeta(self):
        """Y el resto en gris: en la semana 2 de este plan no toca nada."""
        e = _estado("2026-06-10T10:00:00+00:00")
        assert e["due"] is False and e["tipos"] == []

    def test_47_el_endpoint_da_la_fecha_limite_cuando_esta_abierta(self, ventana):
        w = ventana.get("window") or {}
        if not w.get("due") or not w.get("is_open"):
            pytest.skip("Hoy la ventana del cliente de prueba no esta abierta; "
                        "la parte deterministica va en los dos tests de arriba.")
        assert w.get("closes_at") and w.get("closes_label"), \
            "con la ventana abierta hay que decir hasta cuando, y con fecha"
        pendientes = ventana.get("items") or []
        assert pendientes, "abierta y sin mandar: tiene que haber algo que rellenar"
        assert pendientes[0].get("deadline_label"), "la tarjeta necesita su fecha limite"

    @pytest.mark.skip(reason="visual: el naranja de la tarjeta de arriba y el gris del resto "
                             "los pone frontend/src/pages/ReportsPage.jsx (tocaRevision / "
                             "aunNoAbre); el backend solo da due, is_open y las fechas")
    def test_47_la_tarjeta_de_arriba_va_en_naranja(self):
        pass


class TestCaso48VentanaCerrada:
    """48 [CRITICO]. Con la ventana cerrada se dice CUANDO se abre, con fecha."""

    def test_48_antes_de_abrir_dice_cuando_abre(self):
        # Miercoles de la semana del mensual: toca, pero todavia no se puede mandar.
        # (Codificaba la apertura vieja del viernes 00:00; el reloj del 19-08 la puso a
        # las 10:00 de España -- 08:00 UTC en junio -- y se actualizo el 21-08.)
        e = _estado("2026-06-17T10:00:00+00:00")
        assert e["due"] is True
        assert e["is_open"] is False, "el miercoles la ventana no esta abierta"
        assert e["window_open"] == datetime.fromisoformat("2026-06-19T08:00:00+00:00"), \
            "hay que poder decir 'abre el viernes 19 a las 10:00', y esa fecha sale de aqui"

    def test_48_ya_cerrada_sigue_sabiendo_las_dos_fechas(self):
        # Lunes a las 19:00 de España, una hora despues del cierre del 19-08 (18:00).
        #
        # CON ANCLA EN MIERCOLES, a proposito: para el perfil anclado en lunes, el lunes
        # ya es la semana siguiente del ciclo y el mensual deja de tocar (due False), asi
        # que «cerrada pero de esta semana» no existe. Con el ciclo empezando en miercoles
        # el lunes sigue siendo la semana 3 y se ve lo que el test quiere ver: cerrada, y
        # con las dos fechas todavia dichas.
        from routes.report_cadence import compute_client_report_state
        perfil = {**PERFIL, "cycle_start": "2026-06-03T00:00:00+00:00"}   # un miercoles
        e = compute_client_report_state(perfil, CATALOGO,
                                        datetime.fromisoformat("2026-06-22T17:00:00+00:00"))
        assert e["due"] is True and e["is_open"] is False
        assert e["window_open"] < e["window_close"] <= datetime.fromisoformat("2026-06-22T16:00:00+00:00")

    def test_48_el_endpoint_cerrado_trae_la_fecha_de_apertura(self, ventana):
        """Lo que la pantalla necesita para no ensenar el formulario apagado."""
        w = ventana.get("window") or {}
        if not w.get("due"):
            pytest.skip("Esta semana no le toca reporte al cliente de prueba.")
        if w.get("is_open"):
            pytest.skip("Hoy la ventana esta abierta; este caso es el de la cerrada.")
        assert w.get("opens_at"), "cerrada sin decir cuando abre es la pantalla apagada de Jesus"
        assert w.get("opens_label"), "y la fecha tiene que venir escrita, no solo en ISO"
        # 'viernes 7 ago': dia de la semana y fecha, que es lo que se lee.
        assert any(ch.isdigit() for ch in str(w["opens_label"])), \
            f"opens_label sin fecha: {w['opens_label']!r}"

    def test_48_con_la_ventana_cerrada_no_deja_mandar_y_lo_dice_con_palabras(self, cliente, ventana):
        w = ventana.get("window") or {}
        if w.get("is_open"):
            pytest.skip("La ventana esta abierta: mandar aqui crearia un reporte de verdad.")
        r = _pide("POST", "/reports", headers=cliente["headers"],
                  json={"weight": 75.0})
        assert r.status_code == 403, f"con la ventana cerrada no se manda: {r.status_code}"
        detalle = (r.json() or {}).get("detail", "")
        assert detalle and "Traceback" not in detalle, \
            "al cliente se le habla, no se le ensena una traza"


class TestCaso49YaMandado:
    """49 [CRITICO]. Con el reporte ya mandado no se ofrece 'empezar'."""

    def test_49_con_el_reporte_mandado_no_queda_nada_pendiente(self, cliente, ventana):
        if not (ventana.get("window") or {}).get("due"):
            pytest.skip("Esta semana no le toca reporte al cliente de prueba.")
        if not _hay_mongo():
            pytest.skip("Sin MONGO_URL no se puede simular el reporte ya mandado.")

        rid = _mete_reporte(cliente["client_id"])
        try:
            r = _pide("GET", "/reports/due", headers=cliente["headers"])
            assert r.status_code == 200
            d = r.json()
            assert (d.get("window") or {}).get("submitted") is True, \
                "el reporte de esta semana ya esta puesto y el backend tiene que verlo"
            assert d.get("items") == [], \
                "si ya lo mando, no se le puede seguir ofreciendo que lo empiece"
        finally:
            assert _borra_reporte(rid) == 1

    def test_49_borrado_el_reporte_vuelve_a_estar_pendiente(self, cliente, ventana):
        """La otra mitad: el estado se calcula, no se queda pegado."""
        w = ventana.get("window") or {}
        if not w.get("due"):
            pytest.skip("Esta semana no le toca reporte al cliente de prueba.")
        r = _pide("GET", "/reports/due", headers=cliente["headers"])
        assert (r.json().get("window") or {}).get("submitted") == w.get("submitted"), \
            "despues de limpiar, el estado tiene que ser el mismo que al empezar"


# ==================== 50: el check-in diario ====================

class TestCaso50CheckInDiario:
    """50. Dos campos y nada mas; se guarda y se ve en el historial del dia."""

    def test_50_se_manda_con_los_dos_campos_y_se_ve_en_el_historial(self, cliente):
        hoy = datetime.now(timezone.utc).date().isoformat()
        r = _pide("POST", "/checkins", headers=cliente["headers"],
                  json={"type": "daily", "energy": 4, "hunger_anxiety": 2,
                        "notes": MARCA})
        assert r.status_code == 200, f"el diario no se guarda: {r.status_code} {r.text[:200]}"
        creado = r.json()
        cid = creado["id"]
        try:
            assert creado["energy"] == 4 and creado["hunger_anxiety"] == 2
            assert creado["created_at"][:10] == hoy

            lista = _pide("GET", "/checkins", headers=cliente["headers"],
                          params={"type": "daily", "limit": 30})
            assert lista.status_code == 200
            assert any(c["id"] == cid for c in lista.json()), \
                "lo que se guarda tiene que salir en el historial del dia"
        finally:
            if _hay_mongo():
                async def _del(db):
                    return (await db.checkins.delete_many({"id": cid})).deleted_count
                assert _con_mongo(_del) == 1

    def test_50_no_se_le_pregunta_por_la_dieta_la_rellena_el_servidor(self, monkeypatch):
        """Lo que ya consta no se pregunta (parte 7.2 del documento).

        Va contra una base falsa: lo que se comprueba es la regla, no que el cliente demo
        tenga dieta puesta hoy.
        """
        from routes import checkins as modulo

        class _Base:
            def __init__(self, dieta):
                self._dieta = dieta
                self.diets = self

            async def find_one(self, *a, **k):
                return self._dieta

        con_comida = {"comidas": {"comida1": {"alimentos": [{"nombre": "pollo"}]}}}
        monkeypatch.setattr(modulo, "db", _Base(con_comida))
        salida = asyncio.run(modulo._dieta_y_entreno_del_dia({"user_id": "u"}, "2026-08-12"))
        assert salida.get("nutrition_followed") is True, \
            "con la dieta registrada, el servidor la da por seguida sin preguntar"

        monkeypatch.setattr(modulo, "db", _Base({"comidas": {"comida1": {"alimentos": []}}}))
        vacia = asyncio.run(modulo._dieta_y_entreno_del_dia({"user_id": "u"}, "2026-08-12"))
        assert vacia.get("nutrition_followed") is False

    def test_50_el_entreno_no_se_inventa(self, monkeypatch):
        """No hay registro de sesiones hechas, asi que el entreno no se autorrellena.

        Darlo por hecho el dia que tocaba contaria entrenos que nadie ha hecho.
        """
        from routes import checkins as modulo

        class _Base:
            diets = None

            async def find_one(self, *a, **k):
                return {"comidas": {"c1": {"alimentos": [{"n": 1}]}}}

        base = _Base()
        base.diets = base
        monkeypatch.setattr(modulo, "db", base)
        salida = asyncio.run(modulo._dieta_y_entreno_del_dia({"user_id": "u"}, "2026-08-12"))
        assert "trained" not in salida


# ==================== 51: el reporte mensual completo ====================

class TestCaso51ReporteCompleto:
    """51 [CRITICO]. "Exige las diez medidas y las tres fotos. No deja mandar medio."

    ESTOS TESTS FALLAN HOY, y se dejan fallando. Lo que hay:
      - el unico campo obligatorio del backend es el peso (models/common.py::ReportCreate),
      - las diez medidas solo se exigen en el navegador (ReportsPage.handleSubmit) y solo
        en la semana del mensual,
      - y las tres fotos no se exigen en ningun sitio: se suben por su cuenta a
        `client_photos` y el reporte se guarda con `photos` a nulo.
    """

    def _crear(self, **campos):
        from models.common import ReportCreate
        return ReportCreate(**{"weight": 78.0, **campos})

    def test_51_no_deja_mandar_sin_las_diez_medidas(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            self._crear()          # peso y nada mas: medio reporte
        with pytest.raises(ValidationError):
            self._crear(measurements={"cintura": 82.0})   # una de diez

    def test_51_no_deja_mandar_sin_las_tres_fotos(self):
        from pydantic import ValidationError
        completo_de_medidas = {m: 50.0 for m in DIEZ_MEDIDAS}
        with pytest.raises(ValidationError):
            self._crear(measurements=completo_de_medidas)          # sin fotos
        with pytest.raises(ValidationError):
            self._crear(measurements=completo_de_medidas, photos=["frente"])   # una de tres

    def test_51_las_tres_fotos_que_sube_quedan_pegadas_al_reporte(self, cliente):
        """Las sube, y el informe dice que no hay fotos.

        Es el mismo agujero visto desde el otro lado: TresFotos.jsx las manda a
        POST /reports/photos (coleccion `client_photos`) y nadie las engancha al reporte,
        que es de donde las lee el informe.
        """
        if not _hay_mongo():
            pytest.skip("Sin MONGO_URL no se puede limpiar lo que sube esta prueba.")

        subidas = []
        for pose in ("frente", "espalda", "perfil"):
            r = _pide("POST", "/reports/photos", headers=cliente["headers"],
                      params={"pose": pose},
                      files={"file": (f"{MARCA}.png", PNG_MINIMO, "image/png")})
            assert r.status_code == 200, f"no se pudo subir la foto de {pose}: {r.text[:200]}"
            subidas.append(r.json()["id"])

        rid = _mete_reporte(cliente["client_id"])   # el reporte que se manda hoy, sin fotos
        try:
            informe = _pide("GET", f"/reports/{rid}/informe",
                            headers=cliente["headers"]).json()
            assert informe.get("generado") is True, (
                "el cliente subio sus tres fotos y aun asi el informe dice "
                f"{informe.get('motivo')!r}: las fotos no llegan al reporte")
        finally:
            _borra_reporte(rid)

            async def _del(db):
                return (await db.client_photos.delete_many(
                    {"id": {"$in": subidas}})).deleted_count
            assert _con_mongo(_del) == len(subidas)


# ==================== 52: mi evolucion ====================

class TestCaso52Evolucion:
    """52. Con un solo pesaje no se dibuja una curva."""

    def test_52_la_evolucion_trae_la_fecha_de_cada_pesaje(self, cliente):
        """El backend da los puntos con su fecha; quien cuenta los dias es la grafica.

        Sin la fecha de verdad no se puede saber si hay uno o dos pesajes -- dos del mismo
        dia son una correccion, no una evolucion --, asi que esto es la condicion de que
        el aviso del caso 52 se pueda dar.
        """
        r = _pide("GET", "/reports/evolution", headers=cliente["headers"])
        assert r.status_code == 200
        serie = r.json().get("weight") or []
        for punto in serie:
            assert punto.get("date"), "un pesaje sin fecha no se puede situar en el tiempo"
            assert isinstance(punto.get("value"), (int, float))
            datetime.fromisoformat(str(punto["date"]).replace("Z", "+00:00"))

    @pytest.mark.skip(reason="visual: el aviso 'Con dos pesajes te dibujamos tu evolucion. Te "
                             "falta uno.' lo decide frontend/src/components/GraficaDePeso.jsx "
                             "(datos.length === 1), agrupando antes por dia; el backend "
                             "devuelve la serie en crudo")
    def test_52_con_un_pesaje_dice_que_falta_otro(self):
        pass


# ==================== 53: el historial ====================

class TestCaso53Historial:
    """53 [CRITICO]. Un reporte por fecha.

    ESTE TEST FALLA HOY, y se deja fallando: el cliente demo tiene cuatro reportes
    identicos del 23 de julio (18:28, 18:36, 18:44 y 18:49), que es literalmente lo que
    Jesus describe. Ni la ruta ni la pantalla agrupan: GET /reports devuelve un documento
    por envio y ReportsPage pinta una tarjeta por documento. La regla ya existe para el
    historial de macros (punto 62, una fila por cliente y fecha) y aqui no.
    """

    def test_53_no_hay_dos_reportes_del_mismo_dia(self, cliente):
        por_dia = {}
        for rep in cliente["reportes"]:
            por_dia.setdefault(str(rep["created_at"])[:10], []).append(rep)
        repetidos = {dia: len(v) for dia, v in por_dia.items() if len(v) > 1}
        assert not repetidos, f"varias tarjetas del mismo dia en el historial: {repetidos}"

    def test_53_cada_reporte_del_historial_es_uno_distinto(self, cliente):
        ids = [r["id"] for r in cliente["reportes"]]
        assert len(ids) == len(set(ids)), "el historial repite el mismo reporte"


# ==================== 54: el informe del mes ====================

class TestCaso54InformeDelMes:
    """54. Cruza dietas, check-ins y macros del periodo y sale sin errores."""

    def test_54_el_informe_cruza_dietas_checkins_y_macros(self, cliente):
        if not _hay_mongo():
            pytest.skip("Sin MONGO_URL no se puede montar el reporte de la prueba.")
        # Con fotos: sin ellas el informe no se genera a proposito (parte 6 de la
        # especificacion del 31-07), y entonces no se cruzaria nada.
        rid = _mete_reporte(cliente["client_id"], fotos=[f"{MARCA}-frente"])
        try:
            r = _pide("GET", f"/reports/{rid}/informe",
                      headers=cliente["headers"])
            assert r.status_code == 200, f"el informe revienta: {r.status_code} {r.text[:300]}"
            d = r.json()
            assert d.get("generado") is True, f"no se genero: {d.get('motivo')}"

            # Las dietas del periodo.
            cumpl = d["cumplimiento"]
            assert cumpl["dias_periodo"] >= 1
            assert isinstance(cumpl["dieta"]["dias"], int)
            assert cumpl["dieta"]["color"] in ("verde", "ambar", "amarillo", "rojo")
            # Los check-ins del periodo (de ahi salen los entrenos contados).
            assert isinstance(cumpl["entreno"]["dias"], int)
            # Los macros: objetivo contra comido, una fila por macro.
            assert len(d["macros"]["filas"]) == 3
            assert {f["macro"] for f in d["macros"]["filas"]} == {"Proteína", "Hidratos", "Grasa"}
            # Y el resto de apartados montados.
            for apartado in ("ciclo", "peso", "grasa", "fotos", "explicacion", "referencia"):
                assert apartado in d, f"falta el apartado {apartado}"
        finally:
            assert _borra_reporte(rid) == 1

    def test_54_los_informes_de_los_reportes_de_verdad_no_revientan(self, cliente):
        """Los suyos, tal y como estan guardados: ninguno puede dar un 500."""
        for rep in cliente["reportes"][:10]:
            r = _pide("GET", f"/reports/{rep['id']}/informe",
                      headers=cliente["headers"])
            assert r.status_code == 200, \
                f"el informe del reporte {rep['id']} responde {r.status_code}"
            d = r.json()
            if not d.get("generado"):
                # Sin fotos no hay informe, pero se dice con palabras y no con un error.
                assert d.get("motivo") == "sin_fotos" and d.get("mensaje")

    def test_54_un_informe_que_no_existe_no_revienta(self, cliente):
        """De paso, la puerta: pedir un informe que no existe no puede dar un 500."""
        r = _pide("GET", f"/reports/{uuid.uuid4()}/informe",
                  headers=cliente["headers"])
        assert r.status_code == 404
