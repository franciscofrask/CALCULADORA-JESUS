"""
EL PESO DE LA SEMANA Y LOS AVISOS DEL PREMIUM (puntos 34 y 35 del doc de Jesus del 24-08).

    «La primera pareja de dias seguidos desde el miercoles. Miercoles-jueves,
     jueves-viernes o viernes-sabado. En cuanto los tiene, hace la media.»

Esa regla, medida contra produccion antes de escribirla, se cumple en el 0,35 % de las
semanas-cliente: la gente NO se pesa dos dias seguidos. De ahi la decision del 24-08, que
es una cascada de tres ramas -- pareja, media de la semana, ultimo conocido de 14 dias --
y que sube la cobertura al 32,0 % (1.466 de 4.576 semanas-cliente; 44 de 260 en los diez
Premium). Los numeros de esta cabecera se reprodujeron con `peso_semanal` contra la base
de produccion, de solo lectura, con el script `_guia/_fase1_peso_semanal.py` al lado.

Y lo que aqui se fija por encima de todo: que la pantalla pueda decir SIEMPRE de donde
sale el numero. Un peso puesto por la maquina que el cliente no sabe de donde viene es un
peso que va a borrar.
"""
import os
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)

import pytest  # noqa: E402

from core.avisos_cliente import avisos_de_calendario_doc, elegir_avisos  # noqa: E402
from core.datos_reporte import de_donde_sale_el_peso  # noqa: E402
from core.series_cliente import (  # noqa: E402
    DIAS_ATRAS_PARA_UN_PESAJE,
    DIAS_DEL_ULTIMO_PESO,
    actual,
    fecha_de_pesaje_valida,
    peso_semanal,
    poner_en_serie,
)

MADRID = ZoneInfo("Europe/Madrid")

# Una semana cerrada y pasada, para que estos tests digan lo mismo dentro de un año: la
# curva de peso corta en hoy a proposito (en produccion hay pesajes fechados en 2028).
LUNES = date(2026, 8, 10)
MIERCOLES, JUEVES, VIERNES, SABADO, DOMINGO = (LUNES + timedelta(days=n) for n in (2, 3, 4, 5, 6))


def _serie(*pesajes):
    """[(fecha, kg), ...] -> la serie tal y como vive en `client_profiles.pesos`."""
    return [{"fecha": f.isoformat(), "valor": v, "origen": "check-in"} for f, v in pesajes]


# ── a) La pareja de dias seguidos desde el miercoles ─────────────────────────

class TestLaParejaDeJesus:
    def test_miercoles_y_jueves_hacen_la_media(self):
        r = peso_semanal(_serie((MIERCOLES, 80.0), (JUEVES, 81.0)), DOMINGO)
        assert r["valor"] == 80.5
        assert r["regla"] == "pareja"
        assert r["fechas"] == ["2026-08-12", "2026-08-13"]
        assert r["de_esta_semana"] is True

    def test_jueves_y_viernes_tambien(self):
        r = peso_semanal(_serie((JUEVES, 80.0), (VIERNES, 80.4)), LUNES)
        assert (r["valor"], r["regla"]) == (80.2, "pareja")

    def test_viernes_y_sabado_tambien(self):
        r = peso_semanal(_serie((VIERNES, 79.8), (SABADO, 80.2)), LUNES)
        assert (r["valor"], r["regla"]) == (80.0, "pareja")

    def test_manda_la_PRIMERA_pareja_que_exista_no_la_ultima(self):
        """«La PRIMERA pareja de dias seguidos desde el miercoles»: mie-jue gana a vie-sab
        aunque la segunda sea mas reciente. Es la regla de Jesus, literal."""
        r = peso_semanal(_serie((MIERCOLES, 80.0), (JUEVES, 82.0),
                                (VIERNES, 90.0), (SABADO, 90.0)), LUNES)
        assert (r["valor"], r["fechas"]) == (81.0, ["2026-08-12", "2026-08-13"])

    def test_lunes_y_martes_NO_son_pareja(self):
        """La pareja se busca DESDE EL MIERCOLES. Dos dias seguidos a principio de semana
        no la forman, y entonces manda la rama de la media."""
        r = peso_semanal(_serie((LUNES, 80.0), (LUNES + timedelta(days=1), 82.0)), DOMINGO)
        assert r["regla"] == "media"

    def test_dos_dias_sueltos_de_la_semana_tampoco(self):
        r = peso_semanal(_serie((MIERCOLES, 80.0), (VIERNES, 82.0)), DOMINGO)
        assert (r["regla"], r["valor"]) == ("media", 81.0)

    def test_la_media_se_redondea_a_un_decimal(self):
        r = peso_semanal(_serie((MIERCOLES, 80.1), (JUEVES, 80.2)), LUNES)
        assert r["valor"] == 80.2      # 80,15 redondeado, no 80,15000000001


# ── b) La media de todos los pesajes de la semana ────────────────────────────

class TestLaMediaDeLaSemana:
    def test_tres_pesajes_sueltos(self):
        r = peso_semanal(_serie((LUNES, 80.0), (MIERCOLES, 81.0), (DOMINGO, 82.0)), MIERCOLES)
        assert (r["valor"], r["regla"]) == (81.0, "media")
        assert r["fechas"] == ["2026-08-10", "2026-08-12", "2026-08-16"]

    def test_con_un_solo_pesaje_la_media_es_ese(self):
        r = peso_semanal(_serie((MIERCOLES, 79.4)), DOMINGO)
        assert (r["valor"], r["regla"], r["de_esta_semana"]) == (79.4, "media", True)

    def test_la_semana_va_de_lunes_a_domingo(self):
        """El domingo entra en su semana y el lunes siguiente ya no."""
        r = peso_semanal(_serie((DOMINGO, 80.0), (DOMINGO + timedelta(days=1), 90.0)), LUNES)
        assert (r["valor"], r["fechas"]) == (80.0, ["2026-08-16"])

    def test_cualquier_dia_de_la_semana_da_la_misma_respuesta(self):
        """`dia` es cualquier dia de la semana que se resume: se lleva a su lunes."""
        s = _serie((MIERCOLES, 80.0), (JUEVES, 81.0))
        assert len({peso_semanal(s, LUNES + timedelta(days=n))["valor"] for n in range(7)}) == 1

    def test_un_cero_no_es_un_pesaje(self):
        """En la serie de produccion hay 0,0 kg y un 0,433 (un % de grasa mal metido). El
        saneado es el de la curva unica: si lo unico de la semana es basura, no hay media."""
        assert peso_semanal(_serie((MIERCOLES, 0.0), (JUEVES, 0.433)), DOMINGO) is None


# ── c) El ultimo conocido, con su fecha ──────────────────────────────────────

class TestElUltimoConocido:
    def test_sin_pesajes_esta_semana_vale_el_de_la_pasada(self):
        r = peso_semanal(_serie((LUNES - timedelta(days=3), 84.2)), JUEVES)
        assert (r["valor"], r["regla"]) == (84.2, "ultimo")
        assert r["fecha"] == "2026-08-07"
        assert r["de_esta_semana"] is False, "hay que poder decir que no es de esta semana"

    def test_manda_el_mas_reciente_de_los_que_haya(self):
        r = peso_semanal(_serie((LUNES - timedelta(days=10), 90.0),
                                (LUNES - timedelta(days=2), 84.0)), LUNES)
        assert (r["valor"], r["fecha"]) == (84.0, "2026-08-08")

    def test_catorce_dias_entra_y_quince_no(self):
        """El tope se mide desde el SABADO de esa semana, que es donde acaba el periodo."""
        justo = SABADO - timedelta(days=DIAS_DEL_ULTIMO_PESO)
        assert peso_semanal(_serie((justo, 83.0)), LUNES)["valor"] == 83.0
        assert peso_semanal(_serie((justo - timedelta(days=1), 83.0)), LUNES) is None

    def test_sin_nada_que_enseñar_no_se_inventa_un_peso(self):
        assert peso_semanal([], LUNES) is None
        assert peso_semanal(None, LUNES) is None

    def test_la_semana_de_una_persona_no_cambia_segun_el_dia_en_que_se_mire(self):
        """El corte de la rama c es el sabado y no «hoy» a proposito: una semana cerrada
        tiene que resumirse siempre igual, se abra el reporte el viernes o el sabado."""
        s = _serie((LUNES - timedelta(days=1), 85.0))
        assert {peso_semanal(s, LUNES + timedelta(days=n))["valor"] for n in range(7)} == {85.0}

    def test_en_la_semana_en_curso_los_catorce_dias_se_cuentan_desde_hoy(self, monkeypatch):
        """El reporte SIEMPRE pide la semana de hoy, y con el corte en el sabado que aun no
        ha llegado el lunes solo se miraban nueve dias hacia atras: al que se peso hace diez
        se le decia que no habia peso, y el jueves de esa misma semana si lo habia."""
        hoy = date(2026, 8, 24)                      # lunes
        monkeypatch.setattr("core.tiempo.hoy_madrid", lambda: hoy)
        r = peso_semanal(_serie((hoy - timedelta(days=10), 88.0)), hoy)
        assert (r["valor"], r["regla"], r["de_esta_semana"]) == (88.0, "ultimo", False)

    def test_y_el_tope_sigue_siendo_catorce_dias(self, monkeypatch):
        hoy = date(2026, 8, 24)
        monkeypatch.setattr("core.tiempo.hoy_madrid", lambda: hoy)
        justo = hoy - timedelta(days=DIAS_DEL_ULTIMO_PESO)
        assert peso_semanal(_serie((justo, 88.0)), hoy)["valor"] == 88.0
        assert peso_semanal(_serie((justo - timedelta(days=1), 88.0)), hoy) is None


# ── La linea que lo explica en la pantalla ───────────────────────────────────

class TestDeDondeSale:
    def test_la_pareja_dice_los_dos_dias(self):
        r = peso_semanal(_serie((MIERCOLES, 80.0), (JUEVES, 81.0)), LUNES)
        assert de_donde_sale_el_peso(r) == "La media de tus pesajes del 12 y el 13 de agosto"

    def test_si_la_pareja_cruza_de_mes_se_nombran_los_dos_meses(self):
        """La pareja viernes-sabado puede caer a caballo de dos meses, y ahi «del 31 y el
        1» no se entiende."""
        r = peso_semanal(_serie((date(2026, 7, 31), 80.0), (date(2026, 8, 1), 81.0)),
                         date(2026, 7, 27))
        assert de_donde_sale_el_peso(r) == "La media de tus pesajes del 31 de julio y el 1 de agosto"

    def test_la_media_dice_cuantos_pesajes_entraron(self):
        r = peso_semanal(_serie((LUNES, 80.0), (MIERCOLES, 81.0), (DOMINGO, 82.0)), LUNES)
        assert de_donde_sale_el_peso(r) == "La media de tus 3 pesajes de esta semana"

    def test_con_uno_solo_no_se_llama_media_a_un_numero_suelto(self):
        r = peso_semanal(_serie((MIERCOLES, 79.4)), LUNES)
        assert de_donde_sale_el_peso(r) == "Tu peso del 12 de agosto"

    def test_el_ultimo_conocido_enseña_SU_fecha_Y_SUS_KILOS(self):
        """La rama c es la única que dice los kilos, y a propósito (arreglo del 24-08 por
        la tarde). Las otras dos hablan de pesajes DE ESTA SEMANA, que el cliente acaba de
        hacer y ya tiene delante en la casilla. Esta no: es un peso de hace hasta catorce
        días, y con «Tu último peso, del 3 de agosto» a secas no había forma de saber si el
        número que se está mandando al reporte es el de ese día o uno nuevo. El test decía
        la frase de antes."""
        r = peso_semanal(_serie((date(2026, 8, 3), 84.2)), LUNES)
        assert de_donde_sale_el_peso(r) == "Tu último peso: 84,2 kg, del 3 de agosto"

    def test_sin_peso_no_hay_linea(self):
        assert de_donde_sale_el_peso(None) is None


# ── La puerta de entrada: un pesaje con SU fecha ─────────────────────────────

class TestUnPesajeConSuFecha:
    """Punto 34: hoy el peso se archiva con la fecha del documento y no con la del pesaje,
    y por eso la pareja de dias seguidos no puede existir por ninguna via. La casilla del
    cierre del dia la hace otro; esto es el candado que tiene que llamar."""

    HOY = date(2026, 8, 24)

    def test_sin_fecha_es_hoy(self):
        assert fecha_de_pesaje_valida(None, hoy=self.HOY) == "2026-08-24"
        assert fecha_de_pesaje_valida("", hoy=self.HOY) == "2026-08-24"

    def test_un_dia_de_atras_entra(self):
        assert fecha_de_pesaje_valida("2026-08-20", hoy=self.HOY) == "2026-08-20"

    def test_del_futuro_no_entra_ni_uno(self):
        """Un pesaje de mañana no es el peso de nadie, y ademas se quedaria escondido en la
        serie hasta que llegara su dia: `actual` solo mira hasta hoy."""
        assert fecha_de_pesaje_valida("2026-08-25", hoy=self.HOY) is None

    def test_de_hace_un_año_tampoco(self):
        assert fecha_de_pesaje_valida("2025-08-24", hoy=self.HOY) is None

    def test_el_tope_de_atras_es_el_declarado(self):
        justo = self.HOY - timedelta(days=DIAS_ATRAS_PARA_UN_PESAJE)
        assert fecha_de_pesaje_valida(justo.isoformat(), hoy=self.HOY) == justo.isoformat()
        assert fecha_de_pesaje_valida((justo - timedelta(days=1)).isoformat(),
                                      hoy=self.HOY) is None

    def test_lo_que_no_es_una_fecha_no_pasa(self):
        assert fecha_de_pesaje_valida("ayer", hoy=self.HOY) is None
        assert fecha_de_pesaje_valida("2026-13-40", hoy=self.HOY) is None

    def test_apuntar_un_pesaje_viejo_no_cambia_el_peso_actual(self):
        """La serie ya admite fechas que no son hoy sin romperse, y hace falta que siga
        siendo verdad: la casilla nueva va a meter pesajes de hace dos dias."""
        serie = poner_en_serie(_serie((JUEVES, 80.0)), MIERCOLES.isoformat(), 84.0, "check-in")
        assert [p["fecha"] for p in serie] == ["2026-08-12", "2026-08-13"]
        assert actual(serie) == {"valor": 80.0, "fecha": "2026-08-13"}

    def test_y_el_pesaje_viejo_entra_en_la_media_de_su_semana(self):
        serie = poner_en_serie(_serie((JUEVES, 80.0)), MIERCOLES.isoformat(), 81.0, "check-in")
        assert peso_semanal(serie, LUNES)["regla"] == "pareja"


# ── Los tres avisos del Premium ──────────────────────────────────────────────
#
# Los textos son LITERALES del doc y se comprueban letra a letra: es la voz de Jesus.
#
# OJO: ESTOS TRES CAMBIARON EL 1-09 (commit 758c024) y esta clase defendia los de antes.
# Eran el del MIERCOLES («Hoy toca pesarte y manana tambien») y el del JUEVES; se fueron
# porque su calendario del doc «validado» pone el aviso el MARTES y deja los dos dias de
# pesada con FILA en Inicio, no con aviso -- su regla de la cola, «nunca dos avisos» --, y
# porque ademas mandaban a /dashboard/checkins, donde el campo del peso ya no esta.
#
# Los de ahora son otros tres: martes, miercoles de la semana 1 del primer ciclo, y el
# rescate del viernes. Se reescriben aqui en vez de borrarse: lo que hay que fijar es la
# regla vigente, y de paso queda escrito cual se derogo y por que.

MARTES_ES = datetime(2026, 8, 11, 9, 0, tzinfo=MADRID)
MIERCOLES_ES = datetime(2026, 8, 12, 9, 0, tzinfo=MADRID)
JUEVES_ES = datetime(2026, 8, 13, 9, 0, tzinfo=MADRID)
VIERNES_ES = datetime(2026, 8, 14, 9, 0, tzinfo=MADRID)


def _peso(avisos):
    return [a for a in avisos if a["clave"].startswith("peso_")]


class TestLosTresAvisosDelPeso:
    def test_el_del_martes_avisa_de_que_toca_reporte(self):
        a = _peso(avisos_de_calendario_doc(ahora_es=MARTES_ES, es_premium=True,
                                           toca_quincenal_esta_semana=True))[0]
        assert a["titulo"] == "Esta semana toca reporte quincenal"
        assert a["cuerpo"] == ("Recuerda pesarte y registrar el dato. Manana y el jueves, "
                               "en ayunas y despues de ir al bano.").replace(
                                   "Manana", "Mañana").replace("despues", "después").replace(
                                   "bano", "baño")
        # AL SITIO DONDE SE APUNTA. Los de antes mandaban a /dashboard/checkins y el campo
        # del peso se mudo a Evolucion: era mandarle donde no puede hacer lo que se le pide.
        assert a["link"] == "/dashboard/reports?abrir=peso"

    def test_el_del_martes_no_sale_la_semana_sin_reporte(self):
        """Sin quincenal esa semana no hay media que preparar, asi que no se le pide."""
        assert _peso(avisos_de_calendario_doc(ahora_es=MARTES_ES, es_premium=True)) == []

    def test_el_de_la_semana_1_solo_el_primer_ciclo(self):
        """Es el que le ENSENA el metodo; repetirselo cada ciclo es ruido."""
        a = _peso(avisos_de_calendario_doc(ahora_es=MIERCOLES_ES, es_premium=True,
                                           semana=1, primer_ciclo=True))[0]
        assert a["titulo"] == "Esta semana no toca reporte"
        assert "te pesas dos días seguidos entre el miércoles y el viernes" in a["cuerpo"]
        assert _peso(avisos_de_calendario_doc(ahora_es=MIERCOLES_ES, es_premium=True,
                                              semana=1, primer_ciclo=False)) == []

    def test_el_del_viernes_es_el_rescate_y_solo_si_le_falta_una(self):
        a = _peso(avisos_de_calendario_doc(ahora_es=VIERNES_ES, es_premium=True,
                                           le_falta_una_pesada=True))[0]
        assert a["titulo"] == "Te falta una pesada"
        assert "antes de las 10" in a["cuerpo"]
        # Al que tiene las dos no le falta nada, y al que no mando el reporte no se le
        # persigue: las dos cosas las decide `le_falta_una_pesada`.
        assert _peso(avisos_de_calendario_doc(ahora_es=VIERNES_ES, es_premium=True)) == []

    def test_el_miercoles_y_el_jueves_ya_no_llevan_aviso(self):
        """LOS DOS DIAS DE PESADA LLEVAN FILA EN INICIO, no aviso (1-09). Este test es el
        que impide que vuelvan sin querer: si alguien los resucita, salta aqui."""
        for cuando in (MIERCOLES_ES, JUEVES_ES):
            assert _peso(avisos_de_calendario_doc(ahora_es=cuando, es_premium=True)) == []
            assert _peso(avisos_de_calendario_doc(ahora_es=cuando, es_premium=True,
                                                  se_peso_miercoles=True)) == []

    def test_ningun_otro_dia_de_la_semana(self):
        """Lunes, jueves, sabado y domingo, ninguno. El martes, el miercoles y el viernes
        tienen los suyos pero con condicion, y sin ella tampoco nacen."""
        for n in (0, 3, 5, 6):
            cuando = datetime(2026, 8, 10 + n, 9, 0, tzinfo=MADRID)
            assert _peso(avisos_de_calendario_doc(ahora_es=cuando, es_premium=True)) == []


class TestNoNacenDeMadrugada:
    """Todos los avisos de esta funcion llevan su hora, y estos dos no la llevaban: nacian
    a las 00:00. Un aviso nacido de madrugada CIERRA EL DIA -- solo nace uno -- y se lleva
    por delante al que tenia su hora mas tarde y era candidato ese dia y solo ese. Es el
    mismo mordisco que la pasada de fondo de las 00:15 (ver `sincronizar_avisos`)."""

    #: Los dias que llevan aviso desde el 1-09, con lo que hace falta para que nazca: el
    #: martes (11) y el viernes (14). El miercoles y el jueves ya no llevan ninguno.
    CON_AVISO = [(11, {"toca_quincenal_esta_semana": True}),
                 (14, {"le_falta_una_pesada": True})]

    @pytest.mark.parametrize("dia,cond", CON_AVISO)
    def test_a_las_cero_treinta_no_nace(self, dia, cond):
        madrugada = datetime(2026, 8, dia, 0, 30, tzinfo=MADRID)
        assert _peso(avisos_de_calendario_doc(ahora_es=madrugada, es_premium=True, **cond)) == []

    @pytest.mark.parametrize("dia,cond", CON_AVISO)
    def test_a_las_ocho_ya_esta(self, dia, cond):
        ocho = datetime(2026, 8, dia, 8, 0, tzinfo=MADRID)
        assert len(_peso(avisos_de_calendario_doc(ahora_es=ocho, es_premium=True, **cond))) == 1


class TestSoloPremium:
    def test_los_dos_codigos_del_premium_cuentan(self):
        """El Premium son DOS fichas del catalogo: la que se vende (`nivel3`) y la vieja de
        especiales (`premium`), legacy pero asignable, que es la que llevaban los nueve de
        siempre. Con `nivel3` a secas, a un Premium de los de antes no le llegaba ninguno de
        los tres y nada lo habria dicho."""
        from models.user import PLAN_CATALOG
        from routes.notifications import CODIGOS_PREMIUM

        por_nombre = {c for c, p in PLAN_CATALOG.items()
                      if str(p.get("name") or "").lower().startswith("premium")}
        assert por_nombre and por_nombre <= set(CODIGOS_PREMIUM)
        assert "plan_6m" not in CODIGOS_PREMIUM

    def test_al_que_no_es_premium_no_le_llega(self):
        """Y se gatea por el CODIGO DEL PLAN, no por «tiene reporte semanal»: por ahi
        entraba tambien plan_6m, que lo lleva y tiene dos clientes en produccion."""
        assert _peso(avisos_de_calendario_doc(ahora_es=MIERCOLES_ES)) == []
        assert _peso(avisos_de_calendario_doc(ahora_es=JUEVES_ES, es_premium=False)) == []

    def test_al_que_ya_se_peso_no_se_le_dice_que_se_pese(self):
        assert _peso(avisos_de_calendario_doc(ahora_es=MIERCOLES_ES, es_premium=True,
                                              se_peso_miercoles=True)) == []
        assert _peso(avisos_de_calendario_doc(ahora_es=JUEVES_ES, es_premium=True,
                                              se_peso_miercoles=True,
                                              se_peso_jueves=True)) == []


class TestNoSeComenAOtroAviso:
    """La regla de UNO AL DIA (doc 19-08): `elegir_avisos` manda el primero de calendario
    sin mandar, y lo que pierde su dia lo pierde para siempre. Se simulan las 26 semanas de
    un Premium con sus ventanas de verdad."""

    def _ventanas_de_premium(self, semanas=26):
        """Las ventanas reales de un Premium (nivel3), con el calendario del catalogo."""
        from core.calendario_reportes import (calendario_del_plan, reporte_de_la_semana,
                                              ventana_del_reporte)
        from models.user import PLAN_CATALOG

        cal = calendario_del_plan(PLAN_CATALOG["nivel3"])
        fuera = []
        for n in range(1, semanas + 1):
            inicio = LUNES + timedelta(days=7 * (n - 1))
            tipo = reporte_de_la_semana(cal, n)
            if not tipo:
                continue
            v = ventana_del_reporte(cal, tipo, inicio)
            fuera.append({"tipo": tipo, "semana": n, "mandado": False, **v})
        return fuera

    def test_el_premium_no_tiene_ventana_abierta_ni_miercoles_ni_jueves(self):
        for v in self._ventanas_de_premium():
            assert v["abre"].weekday() == 4, "todas las ventanas del Premium abren viernes"

    # Martes (1) con quincenal esa semana, y viernes (4) con una pesada de menos. Antes
    # eran el miercoles y el jueves, que desde el 1-09 no llevan aviso.
    #
    # Y CADA UNO A SU HORA. El del viernes solo vive de 8:00 a 13:00 («si te pesas esta
    # manana antes de las 10, aun entra»), asi que a las 21:00 no existe y probarlo ahi no
    # dice nada: se mira a las 9. El del martes si nace por la tarde.
    @pytest.mark.parametrize("dia_semana,hora,cond",
                             [(1, 21, {"toca_quincenal_esta_semana": True}),
                              (4, 9, {"le_falta_una_pesada": True})])
    def test_el_aviso_del_peso_nace_las_26_semanas(self, dia_semana, hora, cond):
        ventanas = self._ventanas_de_premium()
        for n in range(26):
            dia = LUNES + timedelta(days=7 * n + dia_semana)
            ahora = datetime(dia.year, dia.month, dia.day, hora, 0, tzinfo=MADRID)
            calendario = avisos_de_calendario_doc(
                ahora_es=ahora, cliente_id="c1", cerro_hoy=False,
                ventanas=[v for v in ventanas
                          if abs((v["abre"].date() - dia).days) <= 7],
                semana=n + 1, semanas_ciclo=12, es_premium=True, **cond)
            assert _peso(calendario), f"semana {n + 1}: no nacio el aviso del peso"

    def test_y_a_las_26_semanas_le_gana_a_cierra_tu_dia(self):
        """NACER NO ES GANAR, y esta clase va de lo segundo. El del martes gana siempre
        menos cuando hay algo mas gordo delante: «no nos llego tu reporte», que es un
        plazo que se le paso. Eso NO es que se lo coma un aviso cualquiera -- es la regla
        de uno al dia funcionando --, asi que lo que se fija es que gane a «Cierra tu
        dia», que es el que se los comia antes del arreglo del 24-08.
        """
        ventanas = self._ventanas_de_premium()
        perdidas = []
        for n in range(26):
            dia = LUNES + timedelta(days=7 * n + 1)
            ahora = datetime(dia.year, dia.month, dia.day, 21, 0, tzinfo=MADRID)
            calendario = avisos_de_calendario_doc(
                ahora_es=ahora, cliente_id="c1", cerro_hoy=False,
                ventanas=[v for v in ventanas
                          if abs((v["abre"].date() - dia).days) <= 7],
                semana=n + 1, semanas_ciclo=12, es_premium=True,
                toca_quincenal_esta_semana=True)
            elegido = elegir_avisos(calendario, [], set(), None, ahora)
            assert elegido, f"semana {n + 1}: no nacio ningun aviso"
            gana = elegido[0]["clave"]
            assert not gana.startswith("cierra_dia"), (
                f"semana {n + 1}: «Cierra tu dia» se comio al del peso")
            if not gana.startswith("peso_"):
                perdidas.append(gana.split(":")[0])
        # Lo unico que le gana es el reporte que no llego. Si algun dia le gana otra cosa,
        # que salte aqui y se mire: puede estar bien, pero hay que decidirlo.
        assert set(perdidas) <= {"reporte_no_llego"}, sorted(set(perdidas))

    def test_pero_no_le_quita_el_sitio_a_una_entrega(self):
        """Va el ultimo de los de calendario a proposito: gana a «Cierra tu dia», que
        vuelve a nacer mañana, y pierde contra el fin de ciclo, que trae el dinero."""
        ahora = datetime(2026, 8, 11, 21, 0, tzinfo=MADRID)
        calendario = avisos_de_calendario_doc(
            ahora_es=ahora, cliente_id="c1", cerro_hoy=False, es_premium=True,
            toca_quincenal_esta_semana=True, fin_de_ciclo=date(2026, 8, 16))
        elegido = elegir_avisos(calendario, [], set(), None, ahora)
        assert elegido[0]["familia"] == "fin_ciclo"

    def test_y_gana_a_cierra_tu_dia(self):
        """El del MARTES desde el 1-09. La familia sigue llamandose «peso_miercoles»
        porque es el mismo interruptor de siempre: el nombre es de la llave, no del dia."""
        ahora = datetime(2026, 8, 11, 21, 0, tzinfo=MADRID)
        calendario = avisos_de_calendario_doc(ahora_es=ahora, cliente_id="c1",
                                              cerro_hoy=False, es_premium=True,
                                              toca_quincenal_esta_semana=True)
        assert [a["familia"] for a in calendario] == ["peso_miercoles", "cierra_dia"]


class TestElTonoDeLosTres:
    """La misma vara que el resto de avisos: ninguno puede sonar a reproche ni llevar un
    guion largo."""

    TODOS = (_peso(avisos_de_calendario_doc(ahora_es=MIERCOLES_ES, es_premium=True))
             + _peso(avisos_de_calendario_doc(ahora_es=JUEVES_ES, es_premium=True))
             + _peso(avisos_de_calendario_doc(ahora_es=JUEVES_ES, es_premium=True,
                                              se_peso_miercoles=True)))

    @pytest.mark.parametrize("prohibida", [
        "fuerza de voluntad", "excusa", "vago", "deberías", "deberias",
        "no has", "otra vez", "te lo dijimos", "incumpl", "fallado", "abandonar",
    ])
    def test_ninguno_regaña(self, prohibida):
        for a in self.TODOS:
            assert prohibida not in f"{a['titulo']} {a.get('cuerpo') or ''}".lower()

    def test_ninguno_lleva_guiones_largos(self):
        for a in self.TODOS:
            texto = f"{a['titulo']} {a.get('cuerpo') or ''}"
            assert "—" not in texto and "–" not in texto

    def test_todos_llevan_a_donde_se_apunta_el_peso(self):
        for a in self.TODOS:
            assert a["link"] == "/dashboard/checkins"
