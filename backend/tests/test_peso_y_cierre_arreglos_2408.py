# -*- coding: utf-8 -*-
"""Los arreglos 5 a 9 del repaso del 24-08. Cada prueba empieza por lo que se rompio.

  5. ENVIAR EL REPORTE DESTRUIA UN PESAJE REAL. Un Premium se pesa el jueves (80,0) y el
     viernes (82,0). El viernes abre la ventana del semanal, el reporte le propone la media
     de la pareja (81,0) y al enviarlo esos 81,0 se archivaban CON LA FECHA DEL REPORTE:
     el viernes pasaba de 82,0 a 81,0 y el 82,0 que se peso de verdad desaparecia. El peso
     de la semana caia a 80,5 y cada reenvio lo movia otra vez (80,2...).

  6. EL REPORTE DEJO DE DECIR CUANTO PESABA. Al que no se peso esta semana se le deja la
     casilla vacia a proposito, asi que la frase de debajo es el unico sitio donde puede
     ver su ultimo peso, y se quedo sin los kilos: «Tu ultimo peso, del 20 de agosto».

  7. TRES SITIOS Y TRES NUMEROS para hasta cuando se puede fechar un pesaje: 30 en la serie
     (en una funcion que no llamaba nadie), 14 en el camino vivo y 8 dias en el desplegable.

  8. LA PREGUNTA DEL EXCESO DE MACROS se cayo de la pantalla y el servidor la seguia
     calculando en todas las cargas (resolvia macros y consultaba db.foods). Decision: no
     vuelve; las once preguntas son las de Jesus y el exceso no es ninguna.

  9. REEDITAR EL CIERRE BORRABA `comido_hoy` Y `mood`: el guardado sustituye la fila entera
     y esos dos no viajan en el formulario de hoy.

Las puras no necesitan nada; las de API se saltan solas si no hay backend.
"""
import os
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
import requests

from core.datos_reporte import de_donde_sale_el_peso
from core.series_cliente import (
    DIAS_ATRAS_PARA_UN_PESAJE,
    DIAS_DEL_ULTIMO_PESO,
    peso_semanal,
    poner_en_serie,
)

RAIZ = Path(__file__).resolve().parents[2]
PANTALLA = "frontend/src/pages/CheckInsPage.jsx"
RUTA_CHECKINS = "backend/routes/checkins.py"
RUTA_REPORTES = "backend/routes/reports.py"
API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/") + "/api"

# La semana del repaso, cerrada y pasada: asi estas pruebas dicen lo mismo dentro de un año.
LUNES = date(2026, 8, 10)
JUEVES = LUNES + timedelta(days=3)
VIERNES = LUNES + timedelta(days=4)


def _fuente(ruta: str) -> str:
    return (RAIZ / ruta).read_text(encoding="utf-8")


def _pedir(metodo, ruta, reintentos=4, **kwargs):
    """requests con paciencia: el backend de dev se reinicia solo (watchfiles) cuando otro
    trabajo guarda un .py, y un ConnectionError en ese instante no es un fallo del test."""
    kwargs.setdefault("timeout", 25)
    ultimo = None
    for _ in range(reintentos):
        try:
            return requests.request(metodo, f"{API}{ruta}", **kwargs)
        except requests.RequestException as e:
            ultimo = e
            time.sleep(3)
    raise ultimo


def _semana_del_premium():
    return [{"fecha": JUEVES.isoformat(), "valor": 80.0, "origen": "check-in daily"},
            {"fecha": VIERNES.isoformat(), "valor": 82.0, "origen": "check-in daily"}]


def _dia(serie, cuando):
    return next((p["valor"] for p in serie if p["fecha"] == cuando.isoformat()), None)


# ============ 5. EL REPORTE NO PISA UN PESAJE ============

class TestElReporteNoBorraUnPesaje:
    def test_el_viernes_que_se_peso_de_verdad_sigue_ahi(self):
        """La reproduccion literal del fallo, con las funciones de verdad."""
        serie = _semana_del_premium()
        propuesto = peso_semanal(serie, VIERNES)
        assert (propuesto["valor"], propuesto["regla"]) == (81.0, "pareja")

        despues = poner_en_serie(serie, VIERNES.isoformat(), propuesto["valor"],
                                 "reporte", pisa_pesajes=False)
        assert _dia(despues, VIERNES) == 82.0, "el reporte se ha comido el pesaje del viernes"
        assert peso_semanal(despues, VIERNES)["valor"] == 81.0

    def test_reenviar_el_reporte_no_mueve_el_peso_de_la_semana(self):
        """Antes: 81,0 -> 80,5 -> 80,2, un poco mas bajo en cada reenvio."""
        serie = _semana_del_premium()
        for _ in range(3):
            propuesto = peso_semanal(serie, VIERNES)["valor"]
            serie = poner_en_serie(serie, VIERNES.isoformat(), propuesto, "reporte",
                                   pisa_pesajes=False)
        assert peso_semanal(serie, VIERNES)["valor"] == 81.0

    def test_si_ese_dia_no_hay_pesaje_el_reporte_si_escribe(self):
        """El candado no puede dejar la semana sin peso: Jesus quiere que el peso semanal
        quede registrado."""
        solo_jueves = [{"fecha": JUEVES.isoformat(), "valor": 80.0, "origen": "check-in daily"}]
        despues = poner_en_serie(solo_jueves, VIERNES.isoformat(), 81.0, "reporte",
                                 pisa_pesajes=False)
        assert _dia(despues, VIERNES) == 81.0

    def test_un_reporte_si_corrige_a_otro_reporte(self):
        """Reenviar el mismo documento no es perder un pesaje, es corregirlo."""
        serie = poner_en_serie([], VIERNES.isoformat(), 81.0, "reporte", pisa_pesajes=False)
        serie = poner_en_serie(serie, VIERNES.isoformat(), 79.0, "reporte", pisa_pesajes=False)
        assert _dia(serie, VIERNES) == 79.0

    def test_un_punto_sin_origen_tampoco_se_pisa(self):
        """Los importados de Calma no llevan `origen`. Ante la duda no se borra un dato."""
        serie = poner_en_serie([{"fecha": VIERNES.isoformat(), "valor": 90.0}],
                               VIERNES.isoformat(), 70.0, "reporte", pisa_pesajes=False)
        assert _dia(serie, VIERNES) == 90.0

    def test_un_pesaje_de_verdad_si_manda_sobre_el_del_reporte(self):
        """El candado es de una sola direccion: la bascula gana al documento."""
        serie = poner_en_serie([], VIERNES.isoformat(), 81.0, "reporte", pisa_pesajes=False)
        serie = poner_en_serie(serie, VIERNES.isoformat(), 83.3, "check-in daily")
        assert _dia(serie, VIERNES) == 83.3

    def test_lo_normal_sigue_pisando(self):
        """Sin el parametro, la serie se comporta como siempre: un valor por dia y manda
        el ultimo. Media app depende de eso."""
        serie = poner_en_serie([{"fecha": VIERNES.isoformat(), "valor": 90.0,
                                 "origen": "check-in daily"}],
                               VIERNES.isoformat(), 70.0, "check-in daily")
        assert _dia(serie, VIERNES) == 70.0

    def test_las_dos_puertas_del_reporte_llevan_el_candado(self):
        codigo = _fuente(RUTA_REPORTES)
        llamadas = [l for l in codigo.splitlines()
                    if "await anotar_peso(" in l and not l.strip().startswith("#")]
        assert len(llamadas) == 2, "la del cliente y la del equipo"
        con_candado = codigo.count("pisa_pesajes=False)")
        assert con_candado == 2, \
            f"hay {con_candado} llamadas con el candado y tienen que ser las 2"


# ============ 6. EL REPORTE VUELVE A DECIR LOS KILOS ============

class TestElReporteDiceCuantoPesabas:
    def _rama_ultimo(self):
        vieja = [{"fecha": (LUNES - timedelta(days=5)).isoformat(), "valor": 84.0}]
        return peso_semanal(vieja, LUNES + timedelta(days=1))

    def test_la_rama_del_ultimo_conocido_lleva_los_kilos(self):
        r = self._rama_ultimo()
        assert r["regla"] == "ultimo" and r["de_esta_semana"] is False
        assert de_donde_sale_el_peso(r) == "Tu último peso: 84 kg, del 5 de agosto"

    def test_el_decimal_va_con_coma_y_el_cero_no_se_enseña(self):
        con_decimal = {"valor": 80.5, "regla": "ultimo", "fechas": ["2026-08-03"],
                       "fecha": "2026-08-03", "de_esta_semana": False}
        assert "80,5 kg" in de_donde_sale_el_peso(con_decimal)
        redondo = {**con_decimal, "valor": 80.0}
        assert "80 kg" in de_donde_sale_el_peso(redondo)

    def test_donde_el_numero_ya_esta_en_la_casilla_no_se_repite(self):
        """En pareja y media el kilo va escrito en el campo: decirlo otra vez sobra."""
        pareja = peso_semanal(_semana_del_premium(), VIERNES)
        assert de_donde_sale_el_peso(pareja) == \
            "La media de tus pesajes del 13 y el 14 de agosto"
        assert "kg" not in de_donde_sale_el_peso(pareja)

    def test_al_que_no_se_peso_esta_semana_se_le_recuerda_su_kilo(self):
        """Si vuelve a caerse el kilo de la frase, la pantalla se queda sin decirlo.

        ESTO SE COMPROBABA EN LA PANTALLA Y AHORA SE COMPRUEBA EN EL DATO, que es donde de
        verdad se decide. El 1-09 el peso del quincenal se fue a su paso 1 («Todo lo validado
        antes del 1 de septiembre»), donde la tarjeta enseña los tres dias de la semana; el
        campo de antes, con su linea «Ultimo registro», ya no existe. Lo que no puede
        desaparecer es la INFORMACION: al que no se peso esta semana la casilla se le deja
        vacia a proposito, y si ademas no se le dice cuanto pesaba, se le esta pidiendo el
        peso sin recordarle el suyo. Eso es el fallo 6, y le pasa al 13,94 % de las semanas.
        """
        from core.datos_reporte import peso_semanal_por_dias

        # Un cliente que se peso hace nueve dias y esta semana no: rama «ultimo».
        perfil = {"pesos": [{"fecha": (LUNES - timedelta(days=5)).isoformat(), "valor": 84.0}]}
        ficha = peso_semanal_por_dias(perfil, LUNES + timedelta(days=1))
        assert ficha["valor"] is None, "un peso viejo no se fecha de esta semana"
        assert "84 kg" in (ficha["nota"] or ""), \
            "sin el kilo, la pantalla le pide el peso sin recordarle el suyo (fallo 6)"

        codigo = _fuente("backend/core/datos_reporte.py")
        assert "fallo 6" in codigo, "el porque tiene que quedar escrito al lado"


# ============ 7. UNA SOLA REGLA PARA FECHAR UN PESAJE ============

class TestUnaSolaReglaParaFecharUnPesaje:
    def test_la_regla_vive_en_la_serie_y_es_la_del_peso_semanal(self):
        assert DIAS_ATRAS_PARA_UN_PESAJE == DIAS_DEL_ULTIMO_PESO == 14

    def test_las_rutas_no_declaran_la_suya(self):
        declaraciones = [l for l in _fuente(RUTA_CHECKINS).splitlines()
                         if l.startswith("DIAS_ATRAS_PARA_UN_PESAJE")]
        assert declaraciones == [], \
            f"la segunda copia de la regla es la que se queda vieja: {declaraciones}"
        assert "from core.series_cliente import fecha_de_pesaje_valida" in _fuente(RUTA_CHECKINS)

    def test_el_camino_vivo_acepta_justo_lo_que_dice_la_regla(self):
        import routes.checkins as ck

        cierre = date(2026, 8, 24)
        justo = (cierre - timedelta(days=DIAS_ATRAS_PARA_UN_PESAJE)).isoformat()
        pasado = (cierre - timedelta(days=DIAS_ATRAS_PARA_UN_PESAJE + 1)).isoformat()
        assert ck._dia_del_pesaje(justo, cierre.isoformat()) == justo
        assert ck._dia_del_pesaje(pasado, cierre.isoformat()) == cierre.isoformat()
        assert ck._dia_del_pesaje((cierre + timedelta(days=1)).isoformat(),
                                  cierre.isoformat()) == cierre.isoformat()
        assert ck._dia_del_pesaje("ayer", cierre.isoformat()) == cierre.isoformat()

    def test_la_pantalla_no_lleva_el_numero_a_mano(self):
        """El desplegable ofrece lo que el servidor acepta, y el numero lo dice el servidor.

        LA PANTALLA ES OTRA DESDE EL 1-09: el campo del peso se mudo del cierre del dia a
        Evolucion (bloque 4 de «Todo lo validado antes del 1 de septiembre»), y con el se
        mudo el desplegable de «¿de que dia es este peso?». La regla no cambio -- sigue
        viviendo solo en `core/series_cliente` -- pero ahora viaja en `/reports/evolution`
        en vez de en `/checkins/hoy`. Lo que se comprueba es lo de siempre: que ningun 8 ni
        ningun 14 este escrito a mano en la pantalla.
        """
        campo = _fuente("frontend/src/components/CampoDePeso.jsx")
        assert "i < 8" not in campo, "los 8 dias del desplegable eran la tercera copia"
        assert "diasAtras" in campo and "peso_dias_atras" in _fuente(
            "frontend/src/pages/ReportsPage.jsx")
        assert "hoy?.peso_dias_atras" not in _fuente(PANTALLA), \
            "el cierre del dia ya no pide el peso: si vuelve a leerlo, hay dos campos"

    def test_el_servidor_se_la_dice_a_la_pantalla(self, api_disponible, cabeceras_cliente):
        r = _pedir("GET", "/checkins/hoy", headers=cabeceras_cliente)
        assert r.status_code == 200
        assert r.json().get("peso_dias_atras") == DIAS_ATRAS_PARA_UN_PESAJE


# ============ 8. LA PREGUNTA DEL EXCESO SE FUE ENTERA ============

class TestElExcesoDeMacrosYaNoSeCalcula:
    def test_no_queda_ni_la_funcion_ni_sus_ayudantes(self):
        import routes.checkins as ck

        for muerto in ("_se_ha_pasado", "_consumido_del_dia", "NOMBRE_MACRO"):
            assert not hasattr(ck, muerto), \
                f"{muerto} no lo mira nadie: o vuelve la pregunta o se va del servidor"

    def test_la_decision_esta_escrita(self):
        codigo = _fuente(RUTA_CHECKINS)
        assert "SE FUE LA PREGUNTA DEL EXCESO DE MACROS" in codigo, \
            "se cayo una vez sin dejar nota y por eso el servidor siguio calculandola"

    def test_la_pantalla_no_la_pinta(self):
        pantalla = _fuente(PANTALLA)
        for testid in ("cierre-exceso", "cierre-exceso-nota"):
            assert testid not in pantalla
        assert "hoy?.exceso" not in pantalla

    def test_la_nota_vieja_del_exceso_se_sigue_guardando(self):
        """La pregunta se va; lo que el cliente escribio en su dia, no."""
        from models.common import CheckInCreate, CheckInResponse

        assert "exceso_nota" in CheckInCreate.model_fields
        assert "exceso_nota" in CheckInResponse.model_fields

    def test_el_endpoint_ya_no_lo_devuelve(self, api_disponible, cabeceras_cliente):
        r = _pedir("GET", "/checkins/hoy", headers=cabeceras_cliente)
        assert r.status_code == 200
        assert "exceso" not in r.json()


# ============ 9. REEDITAR NO BORRA LO QUE NO SE PREGUNTA ============

class TestReeditarElCierreNoBorra:
    def _payload_de_la_pantalla(self, fecha, sensaciones):
        """Exactamente lo que arma CheckInsPage al guardar (jsx:771-801)."""
        return {"type": "daily", "fecha": fecha, "sensaciones": sensaciones,
                "entreno_respuesta": None, "entreno_estrellas": None, "cardio": None,
                "movimiento": "igual", "descanso": 4, "energy": 3, "hunger_anxiety": 2,
                "suplementos": None, "extras_respuesta": "no", "cena_hecha": None,
                "comida_pendiente": None, "exceso_nota": None, "entreno_nota": None,
                "notas": None, "weight": None, "peso_fecha": None}

    def test_comido_hoy_y_mood_sobreviven_a_una_reedicion(
            self, api_disponible, cabeceras_cliente):
        hoy = _pedir("GET", "/checkins/hoy", headers=cabeceras_cliente).json()
        fecha = hoy["fecha"]
        marca = f"lo escribio el cliente {uuid.uuid4().hex[:6]}"

        primero = _pedir("POST", "/checkins", headers=cabeceras_cliente,
                         json={"type": "daily", "fecha": fecha, "sensaciones": 4,
                               "energy": 3, "comido_hoy": marca, "mood": 4})
        assert primero.status_code == 200
        assert primero.json()["comido_hoy"] == marca

        segundo = _pedir("POST", "/checkins", headers=cabeceras_cliente,
                         json=self._payload_de_la_pantalla(fecha, 5))
        assert segundo.status_code == 200
        d = segundo.json()
        assert d["comido_hoy"] == marca, "reeditar se llevo por delante un campo que no pregunta"
        assert d["mood"] == 4
        assert d["sensaciones"] == 5, "y lo que si pregunta se actualiza"

    def test_lo_que_se_manda_en_blanco_se_queda_en_blanco(
            self, api_disponible, cabeceras_cliente):
        """El otro lado del arreglo: conservar no puede significar resucitar. Si el cliente
        borra una respuesta al reeditar, se borra."""
        hoy = _pedir("GET", "/checkins/hoy", headers=cabeceras_cliente).json()
        fecha = hoy["fecha"]
        _pedir("POST", "/checkins", headers=cabeceras_cliente,
               json={"type": "daily", "fecha": fecha, "sensaciones": 4, "energy": 3,
                     "exceso_nota": "una nota que luego se borra"})
        d = _pedir("POST", "/checkins", headers=cabeceras_cliente,
                   json=self._payload_de_la_pantalla(fecha, 3)).json()
        assert d.get("exceso_nota") is None
        assert d["sensaciones"] == 3

    def test_una_pregunta_del_cierre_si_se_puede_dejar_en_blanco(
            self, api_disponible, cabeceras_cliente):
        """P75 sigue en pie: conservar los huerfanos no puede impedir borrar una respuesta.
        Aqui el segundo envio ni siquiera nombra `descanso` y tiene que irse."""
        hoy = _pedir("GET", "/checkins/hoy", headers=cabeceras_cliente).json()
        fecha = hoy["fecha"]
        _pedir("POST", "/checkins", headers=cabeceras_cliente,
               json={"type": "daily", "fecha": fecha, "energy": 3, "descanso": 4})
        d = _pedir("POST", "/checkins", headers=cabeceras_cliente,
                   json={"type": "daily", "fecha": fecha, "energy": 5}).json()
        assert d.get("descanso") is None, "lo que el cierre pregunta y no llega, se va"
        assert d["energy"] == 5

    def test_el_arreglo_no_va_campo_a_campo(self):
        """Lo de listar los huerfanos en el front es lo que se olvido dos veces. Lo que se
        declara ahora es lo contrario: LO QUE SE PREGUNTA, y todo lo demas queda protegido
        sin tener que apuntarlo."""
        codigo = _fuente(RUTA_CHECKINS)
        assert "_LO_QUE_PREGUNTA_EL_CIERRE" in codigo
        assert "_LO_QUE_PONE_EL_SERVIDOR" in codigo
        assert "data.model_fields_set" in codigo, \
            "sin esto no se distingue «no lo mando» de «lo mando en blanco»"

    def test_los_huerfanos_no_estan_en_la_lista_de_preguntas(self):
        """Lo que el cierre NO pregunta no puede estar en la lista: si esta, reeditar lo borra.

        `weight` y `peso_fecha` SE FUERON DE LA LISTA EL 1-09, y no es un descuido. El campo
        del peso se mudo del cierre del dia a Evolucion («Todo lo validado antes del 1 de
        septiembre», bloque 4: «es el unico sitio donde el peso se escribe»), asi que esta
        pantalla ya no lo manda. Si siguieran aqui, cada reedicion de un cierre viejo se
        leeria como «lo ha borrado» y le vaciaria el peso que aquel dia si apunto.
        """
        from routes.checkins import _LO_QUE_PREGUNTA_EL_CIERRE

        for huerfano in ("comido_hoy", "mood", "cena_hecha", "comida_pendiente",
                         "exceso_nota", "entreno_nota", "weight", "peso_fecha"):
            assert huerfano not in _LO_QUE_PREGUNTA_EL_CIERRE, \
                f"{huerfano} no se pregunta en ningun sitio: si entra aqui, se pierde"
        for pregunta in ("sensaciones", "descanso", "energy", "hunger_anxiety", "notas"):
            assert pregunta in _LO_QUE_PREGUNTA_EL_CIERRE

    def test_lo_que_calcula_el_servidor_no_se_hereda(self):
        """`nutrition_followed` sale de la dieta de HOY: heredarlo diria que registro la
        dieta un dia que no lo hizo."""
        from routes.checkins import _LO_QUE_PONE_EL_SERVIDOR

        for campo in ("id", "client_id", "dia", "created_at", "trainer_feedback",
                      "autorrelleno", "nutrition_followed"):
            assert campo in _LO_QUE_PONE_EL_SERVIDOR
