# -*- coding: utf-8 -*-
"""El cierre del dia, 24-08: el PDF cuenta como rutina, y reeditar no borra.

Cada prueba empieza por la persona a la que le pasaba:

  1. Montalvo tiene su rutina entregada en PDF. El panel del equipo ya lo sabe decir
     ("En PDF", arreglado en bc2cba8), pero al abrir su cierre del dia la app le seguia
     sacando la caja "Tu entreno de hoy · Si entrenaste por tu cuenta, apuntalo aqui",
     que es la del que NO tiene rutina con nosotros: `tiene_rutina` miraba solo
     `db.routines`. Ahora los dos preguntan por la misma puerta, `tiene_rutina_puesta`.

  2. Un cliente anota por la manana sus notas personales y su peso. Por la noche ya tiene
     todas sus comidas marcadas, asi que el cierre le sale CORTO -- sin notas ni peso --
     y reabre para corregir la energia: no ve lo que escribio, no lo puede corregir y se
     queda pensando que se ha perdido. Y como el guardado SUSTITUYE la fila entera, todo
     campo que la pantalla no pinte se va de verdad (es lo que le pasaba al "La hice" de
     la comida pendiente). La regla nueva: editando, lo que trae respuesta se enseña.

  3. La pregunta del movimiento y los literales de las escalas vuelven a ser los suyos.

  4. El historial mezclaba sus cierres del dia con los reportes mensuales importados de
     Calma. Se parte en dos bloques con su titulo.

Casi todas son puras: leen el codigo de la pantalla o llaman a la pieza con una base de
mentira. La unica que necesita el backend vivo se salta sola si no lo hay.
"""
import os
import time
from pathlib import Path

import pytest
import requests

from conftest import corre
import routes.workout_logs as entrenos

RAIZ = Path(__file__).resolve().parents[2]
PANTALLA = "frontend/src/pages/CheckInsPage.jsx"
API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/") + "/api"


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


# ============ 1. EL PDF TAMBIEN ES RUTINA ============

class _Coleccion:
    """Lo justo de una coleccion de Mongo: `find_one` con filtro de igualdades."""

    def __init__(self, docs=()):
        self.docs = [dict(d) for d in docs]

    async def find_one(self, filtro, proyeccion=None, **kwargs):
        for d in self.docs:
            if all(d.get(campo) == valor for campo, valor in (filtro or {}).items()):
                return dict(d)
        return None


class _Base:
    def __init__(self, routines=(), rutina_pdfs=()):
        self.routines = _Coleccion(routines)
        self.rutina_pdfs = _Coleccion(rutina_pdfs)


class TestTieneRutinaPuesta:
    """La pregunta de un solo cliente, la misma que el panel hace de todos."""

    def _puesta(self, monkeypatch, **colecciones):
        monkeypatch.setattr(entrenos, "db", _Base(**colecciones))
        return corre(entrenos.tiene_rutina_puesta("c1"))

    def test_sin_rutina_de_ninguna_clase_es_que_no(self, monkeypatch):
        assert self._puesta(monkeypatch) is False

    def test_la_estructurada_activa_cuenta(self, monkeypatch):
        assert self._puesta(monkeypatch,
                            routines=[{"client_id": "c1", "status": "active"}]) is True

    def test_una_estructurada_ARCHIVADA_no_cuenta(self, monkeypatch):
        """La de la temporada pasada no es la rutina que tiene puesta hoy."""
        assert self._puesta(monkeypatch,
                            routines=[{"client_id": "c1", "status": "inactive"}]) is False

    def test_el_PDF_SOLO_cuenta_igual(self, monkeypatch):
        """EL CASO DE MONTALVO: sin fila en db.routines y con su PDF subido."""
        assert self._puesta(monkeypatch,
                            rutina_pdfs=[{"client_id": "c1", "uploaded_at": "2026-08-21"}]) is True

    def test_el_PDF_DE_OTRO_no_le_da_rutina(self, monkeypatch):
        assert self._puesta(monkeypatch,
                            rutina_pdfs=[{"client_id": "c9"}]) is False


class TestElCierreLoPreguntaPorLaPuertaBuena:
    def test_checkins_hoy_no_vuelve_a_escribir_el_criterio(self):
        """Antes: `tiene_rutina = rutina is not None`, o sea otra copia del criterio corto.

        La copia es el fallo: el panel se arreglo en bc2cba8 y esta se quedo atras, y el
        mismo cliente salia con rutina para el equipo y sin rutina para el mismo.
        """
        codigo = _fuente("backend/routes/checkins.py")
        assert "tiene_rutina = await tiene_rutina_puesta(profile[\"id\"])" in codigo
        assert "tiene_rutina = rutina is not None" not in codigo

    def test_el_ayudante_vive_en_un_solo_sitio(self):
        entrenados = _fuente("backend/routes/workout_logs.py")
        assert entrenados.count("async def tiene_rutina_puesta(") == 1
        assert "db.rutina_pdfs.find_one" in entrenados


# ============ 2. REEDITAR NO PUEDE BORRAR ============

class TestReeditarNoBorra:
    """El caso: notas y peso escritos por la manana, cierre CORTO por la noche.

    El formulario decidia que enseñar con `corta`, y al guardar hace un POST que SUSTITUYE
    la fila entera: si el corto escondia un campo que ya tenia respuesta, el cliente ni lo
    veia ni lo podia tocar, y ademas se perdia al reenviar.

    EL ARREGLO DEL 24-08 POR LA MAÑANA ERA UN PARCHE (`verNotas` / `verPeso`) y se cae con
    el rediseño del doc del 24: las once preguntas salen a todos todos los dias, asi que
    ya no hay cierre corto ni nada escondido, y lo que no se puede esconder no se puede
    perder. Estas pruebas vigilan que no vuelva.
    """

    def test_ya_no_hay_cierre_corto_que_esconda_nada(self):
        pantalla = _fuente(PANTALLA)
        for parche in ("const verNotas =", "const verPeso =", "const corta ="):
            assert parche not in pantalla, f"volvio {parche}, y con el lo que se escondia"

    def test_las_notas_y_el_peso_se_pintan_siempre(self):
        """Sin condicion delante: son opcionales, pero salen a todo el mundo."""
        pantalla = _fuente(PANTALLA)
        assert "{verNotas && (" not in pantalla and "{verPeso && (" not in pantalla
        assert 'data-testid="cierre-notas"' in pantalla
        assert 'data-testid="cierre-peso"' in pantalla

    def test_lo_que_ya_no_se_pregunta_no_se_borra(self):
        """El "La hice" de la comida pendiente y la nota del exceso de macros se dejaron
        de preguntar con el doc 24-08, pero hay cierres que los tienen escritos. Mandar
        null a pelo aqui se los llevaria por delante: el POST sustituye la fila entera."""
        pantalla = _fuente(PANTALLA)
        assert "cena_hecha: inicial?.cena_hecha ?? null," in pantalla
        assert "comida_pendiente: inicial?.comida_pendiente ?? null," in pantalla
        assert "exceso_nota: inicial?.exceso_nota || null," in pantalla

    def test_al_reabrir_vuelven_las_respuestas_viejas_del_entreno(self):
        """«Si, pero no lo puse» y «No entrene» son los dos valores de antes del 24-08. Si
        no se traducen a la pregunta nueva, al reabrir un cierre sale en blanco."""
        pantalla = _fuente(PANTALLA)
        assert "const ENTRENO_DE_VUELTA = { si_no_lo_puse: 'si', no_entrene: 'no' };" in pantalla
        modelo = _fuente("backend/models/common.py")
        assert 'pattern="^(si|no|descanso|si_no_lo_puse|no_entrene)$"' in modelo

    def test_el_servidor_le_da_a_la_pantalla_con_que_repintarlo(self):
        """La pantalla solo puede repintar lo guardado si `/checkins/hoy` se lo devuelve
        entero: de ahi sale `inicial`."""
        codigo = _fuente("backend/routes/checkins.py")
        assert '"checkin": hecho,' in codigo


class TestElReplaceQueSeLoLLevaTodo:
    """La otra mitad del mismo caso, contra el backend vivo: por que la pantalla TIENE que
    repintar. El POST del cierre sustituye la fila, asi que lo que no se reenvia se va."""

    def test_lo_que_el_segundo_envio_no_trae_desaparece(self, api_disponible, cabeceras_cliente):
        hoy = _pedir("GET", "/checkins/hoy", headers=cabeceras_cliente).json()
        fecha = hoy["fecha"]
        # El peso de siempre del cliente de pruebas si lo tiene: la serie de peso es un
        # dato de verdad y un test no tiene por que moverla de sitio.
        peso = ((hoy.get("ultimo_peso") or {}).get("valor")) or 80.0

        r1 = _pedir("POST", "/checkins", headers=cabeceras_cliente, json={
            "type": "daily", "fecha": fecha, "energy": 3,
            "notas": {"texto": "Lo escribi por la mañana.", "compartida": False},
            "weight": peso,
        })
        assert r1.status_code == 200, r1.text

        # El cierre corto de la noche: solo las cinco cosas, sin notas y sin peso.
        r2 = _pedir("POST", "/checkins", headers=cabeceras_cliente, json={
            "type": "daily", "fecha": fecha, "energy": 5, "descanso": 4,
        })
        assert r2.status_code == 200, r2.text

        guardado = _pedir("GET", "/checkins/hoy", headers=cabeceras_cliente).json()["checkin"]
        assert guardado["energy"] == 5, "la correccion vale"
        # SIGUE VALIENDO DESPUES DEL ARREGLO DEL 24-08 POR LA TARDE, y hay que decir por que.
        # Ese arreglo hizo que al reeditar NO se pierda lo que la pantalla ni siquiera
        # pregunta (`comido_hoy` y `mood`, del check-in de mayo, se iban). Pero el P75 no se
        # toco: una RESPUESTA del formulario que no llega es una respuesta borrada, y por eso
        # se sigue yendo. La frontera son las dos listas de backend/routes/checkins.py:
        # `_LO_QUE_PREGUNTA_EL_CIERRE` (se borra) y todo lo demas (se hereda). `notas` y
        # `weight` estan en la primera, asi que este test comprueba justo el lado que no
        # cambio: si algun dia se cae, es que una pregunta se ha salido de esa lista y
        # entonces el cliente ya no puede borrar su propia respuesta reeditando.
        assert guardado.get("notas") is None and guardado.get("weight") is None, (
            "si esto empieza a conservarse, el arreglo de la pantalla se puede simplificar; "
            "mientras el POST sustituya las RESPUESTAS, repintar es la unica defensa")


class TestElPesoDelHistorialDelCliente:
    """Partir el historial le da titulo propio a «Reportes anteriores», y ahi es donde
    salen los pesos importados de Calma: 159 filas de 18 clientes los tienen en GRAMOS.

    El saneo ya se hacia en la ficha del entrenador y en los reportes, pero no en la lista
    que ve el cliente, que es la unica que el mira. Y de esa lista sale ademas el ultimo
    peso conocido con el que el cierre compara lo que escribe: a 8 clientes el mas reciente
    les viene en gramos, o sea «tu ultimo peso fue 68350 kg» cada vez que se pesan.
    """

    def test_los_gramos_no_llegan_a_la_pantalla_del_cliente(self):
        from core.series_cliente import sanea_peso
        # Los dos de verdad que hay en produccion. El decimal cae al par (68,35 -> 68,3):
        # es el redondeo de Python y da igual, lo que importa es que sean kilos.
        assert sanea_peso(68350.0) == 68.3
        assert sanea_peso(61250.0) == 61.2
        assert sanea_peso(80.4) == 80.4, "un peso normal se queda como esta"

    def test_la_lista_del_cliente_lo_sanea_igual_que_la_del_entrenador(self):
        codigo = _fuente("backend/routes/checkins.py")
        i = codigo.find("async def get_my_checkins(")
        j = codigo.find("async def admin_get_client_checkins(")
        assert 0 < i < j
        assert "sanea_peso" in codigo[i:j], (
            "la lista del cliente volvio a enseñar el peso crudo")


# ============ 3. LOS LITERALES DE JESUS ============

class TestLoQuePreguntaElCierre:
    def test_el_movimiento_vuelve_a_su_pregunta(self):
        pantalla = _fuente(PANTALLA)
        assert "¿Te moviste lo suficiente?" in pantalla
        assert "¿Tuviste más desgaste de lo normal?" not in pantalla, (
            "esa la pusimos nosotros el 23-08 y no es la suya")

    def test_los_tres_botones_caben_en_el_movil(self):
        """Tres frases en fila se partian en tres renglones dentro del boton."""
        pantalla = _fuente(PANTALLA)
        for corto, largo in (("'Menos'", "'Menos de lo habitual'"),
                             ("'Como siempre'", "'Como me vengo moviendo'"),
                             ("'Más'", "'Más de lo habitual'")):
            assert f"l: {corto}" in pantalla
            assert largo not in pantalla

    def test_el_historial_habla_el_mismo_idioma_que_los_botones(self):
        """Acortar los botones y dejar el historial diciendo «Desgaste: menos de lo
        habitual» son dos vocabularios para el mismo dato. Desde el punto 21 del doc 24-08
        el detalle lleva el nombre y el valor por separado («Movimiento · Como siempre»),
        asi que el valor tiene que ser LITERALMENTE la etiqueta del boton."""
        pantalla = _fuente(PANTALLA)
        assert "DESGASTE_HIST" not in pantalla
        assert ("const MOVIMIENTO_VALOR = { menos: 'Menos', igual: 'Como siempre', mas: 'Más' };"
                in pantalla)

    def test_los_valores_guardados_no_se_tocan(self):
        """Lo que cambia es como se le pregunta, no lo que se guarda: `menos|igual|mas`
        esta en el modelo y en los cierres que ya hay escritos."""
        pantalla = _fuente(PANTALLA)
        for valor in ("'menos'", "'igual'", "'mas'"):
            assert f"v: {valor}" in pantalla
        modelo = _fuente("backend/models/common.py")
        assert 'pattern="^(menos|igual|mas)$"' in modelo

    @pytest.mark.parametrize("literal", [
        "¿Cómo descansaste la noche de ayer?",
        "Fundamental tener una buena rutina de sueño si no la tienes ya",
        "Niveles de energía durante el día",
        "Fuera de tu entrenamiento, en tu día normal",
        "Hambre / ansiedad con la dieta",
        "Registrarlo es opcional, sólo para ti. Te lo pediremos sólo para los reportes",
    ])
    def test_los_literales_del_doc_estan_tal_cual(self, literal):
        assert literal in _fuente(PANTALLA)

    def test_los_extremos_de_las_escalas_siguen_donde_estaban(self):
        pantalla = _fuente(PANTALLA)
        for extremo in ('minLabel="fatal"', 'maxLabel="genial"', 'minLabel="bajita"',
                        'maxLabel="pletórico"', 'minLabel="nada"', 'maxLabel="mucha"'):
            assert extremo in pantalla

    def test_el_ultimo_peso_va_en_su_renglon_y_con_punto_medio(self):
        pantalla = _fuente(PANTALLA)
        assert "Último registro: {kilos(hoy.ultimo_peso.valor)} · {cuando(hoy.ultimo_peso.fecha)}" in pantalla
        assert "Opcional{hoy?.ultimo_peso" not in pantalla, "seguia siendo una sola linea"


# ============ 4. EL HISTORIAL, EN DOS BLOQUES ============

class TestElHistorialPartidoEnDos:
    def test_los_dos_bloques_tienen_su_titulo(self):
        pantalla = _fuente(PANTALLA)
        assert "Tus días" in pantalla
        assert "Reportes anteriores" in pantalla
        assert 'data-testid="historial-tus-dias"' in pantalla
        assert 'data-testid="historial-reportes"' in pantalla

    def test_no_se_filtra_a_los_cierres(self):
        """98 de los 103 clientes con historial en produccion SOLO tienen mensuales: si se
        filtra a daily se quedan con la pantalla vacia. Su etapa anterior tambien es suya.
        """
        pantalla = _fuente(PANTALLA)
        assert "const reportes = visibles.filter(c => c.type !== 'daily');" in pantalla
        assert "const cierres = visibles.filter(c => c.type === 'daily');" in pantalla

    def test_cargar_mas_sigue_contando_entradas_y_no_bloques(self):
        pantalla = _fuente(PANTALLA)
        assert "const visibles = checkins.slice(0, histShown);" in pantalla
        i, j = pantalla.find("const visibles ="), pantalla.find("const cierres =")
        assert 0 < i < j, "hay que recortar ANTES de partir"

    def test_ninguna_entrada_del_historial_lleva_hora(self):
        """"La hora confunde: un check-in de las 07:29 es el del dia anterior" (punto 22).

        Y la fila sin `dia` NO es el caso raro que se puede dejar como estaba: medido en
        produccion son 1.595 de las 1.600 entradas (1.593 mensuales de Calma, 2 semanales
        y 2 cierres de antes del bloque F), o sea el historial entero de los 103 clientes
        que tienen alguno. Ahi el dia sale de `created_at`, que va con su "+00:00" y el
        navegador lo pasa a la hora del cliente.
        """
        pantalla = _fuente(PANTALLA)
        i = pantalla.find("const fechaDeEntrada = (c) => (c.dia")
        assert i > 0
        cuerpo = pantalla[i:i + 400]
        corta = "toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' })"
        assert cuerpo.count(corta) == 2, "las dos ramas se fechan igual, con dia y sin dia"
        for con_hora in ("toLocaleString", "hour:", "minute:"):
            assert con_hora not in cuerpo, "la fecha del historial volvio a llevar la hora"

    def test_la_pildora_de_tipo_solo_donde_el_titulo_no_llega(self):
        """Dentro de un bloque con titulo la pildora sobra, salvo en «Reportes anteriores»
        cuando ahi conviven semanales y mensuales (pasa con 2 clientes en produccion)."""
        pantalla = _fuente(PANTALLA)
        assert "const mezclaDeReportes = new Set(reportes.map(c => c.type)).size > 1;" in pantalla
        assert "conTipo={mezclaDeReportes}" in pantalla
        # «Tus dias» ya no pinta entradas sueltas: es una linea por dia (punto 19), y ahi
        # la pildora no aparece por ninguna parte.
        assert "<HistorialDeDias cierres={cierres}" in pantalla

    def test_el_aviso_del_peso_raro_sigue_mirando_la_lista_entera(self):
        """LO QUE MUERDE AL PARTIR LA LISTA: en produccion casi todos los pesos conocidos
        vienen de los mensuales importados. Si `ultimoPeso` saliera de los cierres, el
        aviso del 50 detras del 94 no tendria con que comparar y no saltaria nunca."""
        pantalla = _fuente(PANTALLA)
        assert "const ultimoPeso = checkins.find(c => c.weight != null)?.weight ?? null;" in pantalla
