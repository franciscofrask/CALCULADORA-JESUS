"""
Los avisos que la app manda al cliente (doc de Jesus del 16-08, T10: los 19 avisos).

Lo que se fija aqui son las reglas que hacen que un aviso ayude en vez de molestar:

  - maximo UNA condicionada por semana,
  - ninguna repetida por entrar varias veces en la app,
  - el texto ROTA: nunca la misma variante dos veces seguidas,
  - las horas son las de España, no las de UTC,
  - y ninguna escrita desde la exigencia.

La ultima parece de estilo y no lo es: "este cliente lleva años oyendo que no tiene
fuerza de voluntad; si la app se une a ese coro, la desinstala".

LO QUE SE CAYO CON EL DOC DEL 16-08 y por eso ya no se prueba aqui: las condicionadas de
"¿Quieres que revisemos tu caso?" (estancado), "¿Te pesamos esta semana?" (7 dias sin
peso) y "¿Todo bien?" (5 dias sin dieta). El doc deja cuatro condicionadas y esas tres no
estan; ademas, con el tope de una por semana, tener seis candidatas solo significaba que
las de abajo no salian nunca. La tercera vuelve con otro criterio: cinco dias sin CERRAR
EL DIA, que se mira en `checkins` y no en la dieta.
"""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from core.avisos_cliente import (
    DIAS_ENTRE_CONDICIONADAS,
    avisos_condicionados,
    avisos_de_calendario,
    avisos_de_calendario_doc,
    elegir_avisos,
    rotar_variante,
    textos_de,
)

AHORA = datetime(2026, 8, 2, 10, 0, tzinfo=timezone.utc)
MADRID = ZoneInfo("Europe/Madrid")


def _claves(avisos):
    return [a["clave"].split(":")[0] for a in avisos]


def _es(anio, mes, dia, hora=0, minuto=0):
    """Un momento en hora de España, que es como llegan todas las horas del doc."""
    return datetime(anio, mes, dia, hora, minuto, tzinfo=MADRID)


def _ventana(tipo, abre, semana=1, mandado=False, dias_hasta_cierre=1, hora_cierre=20):
    return {"tipo": tipo, "semana": semana, "abre": abre, "mandado": mandado,
            "cierra": (abre + timedelta(days=dias_hasta_cierre)).replace(hour=hora_cierre)}


def _titulos(avisos):
    return [t["titulo"] for a in avisos for t in textos_de(a)]


class TestUnaPorSemanaYNoMas:
    """"maximo una notificacion por semana que no sea de calendario"."""

    def test_aunque_se_cumplan_todas_sale_una(self):
        cond = avisos_condicionados(
            ahora=AHORA, semanas_sin_ajustar=6, reporte_sin_fotos=True,
            dias_sin_cerrar=20, dias_sin_entrar=30)
        assert len(cond) == 4, "se detectan las cuatro del doc"
        elegidos = elegir_avisos([], cond, set(), None, AHORA)
        assert len(elegidos) == 1, "pero solo se manda una"

    def test_maximo_uno_al_dia_y_la_entrega_primero(self):
        # Regla del doc 19-08: «máximo uno al día, y por orden: primero el de entrega,
        # después el de recordatorio». Con calendario y condicionada a la vez, sale UNA
        # y es la de calendario.
        cal = avisos_de_calendario(
            perfil={"ajuste_macros_completado": True, "week": 11, "id": "c1"},
            ahora=AHORA, semanas_ciclo=12,
            proximo_ajuste=AHORA + timedelta(days=6))
        cond = avisos_condicionados(ahora=AHORA, dias_sin_cerrar=10)
        elegidos = elegir_avisos(cal, cond, set(), None, AHORA)
        assert len(elegidos) == 1
        assert elegidos[0]["clave"] == cal[0]["clave"]

    def test_si_hoy_ya_le_nacio_uno_no_sale_nada_mas(self):
        # El mismo caso, pero con un aviso ya nacido hoy (p. ej. la entrega del
        # miércoles): todo lo demás espera a mañana.
        cal = avisos_de_calendario(
            perfil={"ajuste_macros_completado": True, "week": 11, "id": "c1"},
            ahora=AHORA, semanas_ciclo=12,
            proximo_ajuste=AHORA + timedelta(days=6))
        cond = avisos_condicionados(ahora=AHORA, dias_sin_cerrar=10)
        assert elegir_avisos(cal, cond, set(), None, AHORA, hubo_aviso_hoy=True) == []

    def test_si_ya_tuvo_una_esta_semana_no_le_llega_otra(self):
        cond = avisos_condicionados(ahora=AHORA, dias_sin_cerrar=10, dias_sin_entrar=20)
        hace_dos_dias = (AHORA - timedelta(days=2)).isoformat()
        assert elegir_avisos([], cond, set(), hace_dos_dias, AHORA) == []

    def test_pasada_la_semana_vuelve_a_poder(self):
        cond = avisos_condicionados(ahora=AHORA, dias_sin_cerrar=10)
        hace_ocho_dias = (AHORA - timedelta(days=DIAS_ENTRE_CONDICIONADAS + 1)).isoformat()
        assert len(elegir_avisos([], cond, set(), hace_ocho_dias, AHORA)) == 1

    def test_el_tope_no_frena_las_de_calendario(self):
        """Ni las viejas ni las ocho del doc: el cierre del dia es DIARIO, y si el tope
        semanal le afectara, el cliente lo recibiria una vez cada siete dias."""
        ayer = (AHORA - timedelta(days=1)).isoformat()
        doc = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 2, 21), cerro_hoy=False)
        assert len(elegir_avisos(doc, [], set(), ayer, AHORA)) == 1


class TestNoSeRepiten:
    def test_entrar_diez_veces_no_genera_diez_avisos(self):
        cond = avisos_condicionados(ahora=AHORA, dias_sin_cerrar=10)
        ya = {cond[0]["clave"]}
        assert elegir_avisos([], cond, ya, None, AHORA) == []

    def test_la_clave_lleva_la_semana_para_poder_repetirse_mas_adelante(self):
        de_esta = avisos_condicionados(ahora=AHORA, dias_sin_cerrar=10)[0]["clave"]
        otra_semana = AHORA + timedelta(days=14)
        de_otra = avisos_condicionados(ahora=otra_semana, dias_sin_cerrar=10)[0]["clave"]
        assert de_esta != de_otra

    def test_el_cierre_del_dia_lleva_el_dia_en_la_clave(self):
        """Uno por dia y solo uno: entrar cinco veces esa noche no puede dar cinco avisos,
        y el de mañana tiene que poder salir igual."""
        hoy = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 2, 21), cerro_hoy=False)[0]
        manana = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 3, 21), cerro_hoy=False)[0]
        assert hoy["clave"] == "cierra_dia:2026-08-02"
        assert hoy["clave"] != manana["clave"]
        assert elegir_avisos([hoy], [], {hoy["clave"]}, None, AHORA) == []


class TestElTextoRota:
    """Regla 3 del doc: "nunca la misma variante dos veces seguidas"."""

    def test_sin_nada_anterior_sale_la_primera(self):
        v = rotar_variante([{"titulo": "A"}, {"titulo": "B"}], None)
        assert v["titulo"] == "A" and v["variante"] == 0

    def test_la_siguiente_es_otra(self):
        assert rotar_variante([{"titulo": "A"}, {"titulo": "B"}], 0)["titulo"] == "B"

    def test_al_llegar_al_final_vuelve_a_empezar(self):
        tres = [{"titulo": "A"}, {"titulo": "B"}, {"titulo": "C"}]
        assert rotar_variante(tres, 2)["titulo"] == "A"

    def test_todos_los_avisos_del_doc_traen_sus_variantes(self):
        """Si alguno se queda con un texto solo, la rotacion no existe para el."""
        con_varias = [a for a in TODOS_LOS_AVISOS if a.get("variantes")]
        assert len(con_varias) == len(TODOS_LOS_AVISOS), "todos los del doc rotan"
        for a in con_varias:
            assert len(a["variantes"]) >= 2, f"«{a['variantes'][0]['titulo']}» no rota"


class TestLosUmbralesDeLasCondicionadas:
    def test_cuatro_dias_sin_cerrar_todavia_no(self):
        assert avisos_condicionados(ahora=AHORA, dias_sin_cerrar=4) == []

    def test_cinco_si(self):
        a = avisos_condicionados(ahora=AHORA, dias_sin_cerrar=5)[0]
        assert a["variantes"][0]["titulo"] == "Llevas 5 días sin apuntar nada"

    def test_a_los_doce_dias_sigue_diciendo_cinco(self):
        """El titulo es el del doc, no un contador. Un numero que crece cada dia solo
        sirve para que el aviso pese mas cuanto peor va la cosa."""
        a = avisos_condicionados(ahora=AHORA, dias_sin_cerrar=12)[0]
        assert a["variantes"][0]["titulo"] == "Llevas 5 días sin apuntar nada"

    def test_una_semana_sin_ajustar_no_es_motivo(self):
        assert avisos_condicionados(ahora=AHORA, semanas_sin_ajustar=1) == []

    def test_dos_semanas_si_y_el_numero_va_dentro(self):
        a = avisos_condicionados(ahora=AHORA, semanas_sin_ajustar=2)[0]
        assert a["variantes"][0]["titulo"] == "Llevas 2 semanas con los mismos macros"

    def test_seis_dias_sin_entrar_no(self):
        # La tabla del doc 19-08 pone «¿Todo bien?» a los SIETE días (el 16-08 decía 14).
        assert avisos_condicionados(ahora=AHORA, dias_sin_entrar=6) == []

    def test_siete_si_y_es_el_todo_bien(self):
        avisos = avisos_condicionados(ahora=AHORA, dias_sin_entrar=7)
        assert len(avisos) == 1
        assert avisos[0]["variantes"][0]["titulo"] == "¿Todo bien?"

    def test_sin_datos_no_inventa_avisos(self):
        assert avisos_condicionados(ahora=AHORA) == []


class TestPrioridad:
    """"si se cumplen varios a la vez, sale solo el de mas arriba", y el de arriba es el
    del doc, no el que se detecte antes."""

    def test_el_orden_es_el_del_doc(self):
        cond = avisos_condicionados(ahora=AHORA, reporte_sin_fotos=True,
                                    semanas_sin_ajustar=4, dias_sin_cerrar=10,
                                    dias_sin_entrar=30)
        assert _claves(cond) == ["sin_fotos", "sin_ajustar", "sin_cerrar", "sin_entrar"]

    def test_las_fotos_van_antes_que_todo(self):
        cond = avisos_condicionados(ahora=AHORA, reporte_sin_fotos=True, dias_sin_cerrar=10)
        assert _claves(cond)[0] == "sin_fotos"

    def test_al_que_no_entra_se_le_avisa_el_ultimo(self):
        cond = avisos_condicionados(ahora=AHORA, dias_sin_entrar=30, dias_sin_cerrar=10)
        assert _claves(cond)[-1] == "sin_entrar"


# ── Los ocho del calendario, con las horas de España ─────────────────────────

class TestElCierreDelDia:
    """"cada dia 20:00, solo si no lo ha cerrado". Activado por defecto, y se puede apagar."""

    def test_a_las_20_sale(self):
        a = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 2, 20), cerro_hoy=False)
        assert _claves(a) == ["cierra_dia"]

    def test_a_las_19_todavia_no(self):
        assert avisos_de_calendario_doc(ahora_es=_es(2026, 8, 2, 19, 59), cerro_hoy=False) == []

    def test_mas_tarde_tambien_sale(self):
        """No hay push ni cron: la hora dice DESDE CUANDO se puede ver. El que entra a las
        23:00 tiene que encontrarse el aviso de las 20:00, no haberselo perdido."""
        a = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 2, 23, 30), cerro_hoy=False)
        assert _claves(a) == ["cierra_dia"]

    def test_si_ya_cerro_no_se_le_dice_nada(self):
        assert avisos_de_calendario_doc(ahora_es=_es(2026, 8, 2, 22), cerro_hoy=True) == []

    def test_si_lo_apago_no_le_llega(self):
        assert avisos_de_calendario_doc(ahora_es=_es(2026, 8, 2, 22), cerro_hoy=False,
                                        quiere_cierre_dia=False) == []

    def test_la_hora_es_la_de_España_no_la_de_UTC(self):
        """A las 19:30 de Madrid son las 17:30 UTC. Con la hora en UTC este aviso saldria
        a las 22:00 de España en verano, que es cuando ya no sirve de nada."""
        madrid_1930 = _es(2026, 8, 2, 19, 30)
        assert madrid_1930.astimezone(timezone.utc).hour == 17
        assert avisos_de_calendario_doc(ahora_es=madrid_1930, cerro_hoy=False) == []
        assert avisos_de_calendario_doc(ahora_es=_es(2026, 8, 2, 20, 30), cerro_hoy=False)


class TestElArranque:
    """"domingo 19:00, una sola vez, antes del dia 1"."""

    def test_el_domingo_a_las_19(self):
        a = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 2, 19),
                                     arranque=date(2026, 8, 3))
        assert a[0]["variantes"][0]["titulo"] == "Mañana empiezas"
        assert a[0]["variantes"][1]["titulo"] == "Mañana arrancamos"

    def test_esa_misma_tarde_a_las_18_no(self):
        assert avisos_de_calendario_doc(ahora_es=_es(2026, 8, 2, 18),
                                        arranque=date(2026, 8, 3)) == []

    def test_dos_dias_antes_tampoco(self):
        assert avisos_de_calendario_doc(ahora_es=_es(2026, 8, 1, 20),
                                        arranque=date(2026, 8, 3)) == []

    def test_una_sola_vez(self):
        a = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 2, 20), arranque=date(2026, 8, 3))
        assert elegir_avisos(a, [], {a[0]["clave"]}, None, AHORA) == []

    def test_con_la_rutina_apagada_no_le_manda_a_una_pantalla_que_no_puede_abrir(self):
        base = {"ahora_es": _es(2026, 8, 2, 20), "arranque": date(2026, 8, 3)}
        assert avisos_de_calendario_doc(**base, rutina_visible=True)[0]["link"] == "/dashboard/routine"
        assert avisos_de_calendario_doc(**base)[0]["link"] == "/dashboard"

    def test_el_viejo_se_calla_cuando_manda_el_del_doc(self):
        """Los dos existen (el interruptor `t10_avisos_nuevos` decide cual), pero nunca a
        la vez: seria el mismo recado con dos redacciones distintas."""
        base = {"perfil": {"ajuste_macros_completado": True}, "ahora": AHORA,
                "arranque": AHORA + timedelta(days=1)}
        assert _claves(avisos_de_calendario(**base)) == ["arranque"]
        assert avisos_de_calendario(**base, nuevos=True) == []


class TestElQuincenal:
    """"solo Gold, miercoles 09:00, semanas 2, 4, 6, 8, 10 y 12". Quien lo tiene no se
    pregunta por el nombre del plan: si su calendario no trae quincenal, no le llega
    ninguna ventana de ese tipo y aqui no sale nada."""

    MIERCOLES = _es(2026, 8, 5, 9)      # 2026-08-05 es miercoles

    def test_el_miercoles_a_las_9_se_abre(self):
        a = avisos_de_calendario_doc(ahora_es=self.MIERCOLES,
                                     ventanas=[_ventana("quincenal", self.MIERCOLES)])
        assert _claves(a) == ["quincenal_abierto"]
        assert a[0]["variantes"][0]["titulo"] == "Tu reporte quincenal está abierto"
        assert len(a[0]["variantes"]) == 3

    def test_a_las_8_todavia_no(self):
        a = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 5, 8),
                                     ventanas=[_ventana("quincenal", self.MIERCOLES)])
        assert a == []

    def test_sin_quincenal_en_su_plan_no_hay_aviso(self):
        assert avisos_de_calendario_doc(ahora_es=self.MIERCOLES, ventanas=[]) == []

    def test_el_jueves_a_las_9_el_ultimo_dia(self):
        a = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 6, 9),
                                     ventanas=[_ventana("quincenal", self.MIERCOLES)])
        assert _claves(a) == ["quincenal_ultimo"]
        assert a[0]["variantes"][0]["cuerpo"] == "Se cierra hoy a las 20:00."

    def test_si_ya_lo_mando_no_se_le_recuerda(self):
        a = avisos_de_calendario_doc(
            ahora_es=_es(2026, 8, 6, 9),
            ventanas=[_ventana("quincenal", self.MIERCOLES, mandado=True)])
        assert a == []


class TestElSemanal:
    """La rama semanal (Premium/6M), calcada del quincenal: antes el que tenia cadencia
    semanal no recibia NINGUN aviso de reporte.

    LA VENTANA ES LA DEL DOC DEL 21-08 (apartado 15): abre el VIERNES a las 10:00 y
    cierra el SABADO a las 10:00. (Hasta ese doc iba de domingo 00:00 a domingo 23:00,
    que era un relleno: ningun documento la cubria; estos tests codificaban esa ventana
    vieja y se actualizaron con la regla nueva.) El recordatorio de ultimo dia cae el
    sabado desde las 8:00 -- no las 9:00 del quincenal, porque aqui se cierra a las
    10:00 de la MAÑANA y avisar a las 9:00 dejaba una hora --, solo si sigue sin
    mandarlo ni aplazarlo."""

    VIERNES = _es(2026, 8, 7, 10)       # 2026-08-07 es viernes; abre a las 10:00

    def _v(self, **kw):
        # Cierra el sabado 8 a las 10:00, veinticuatro horas despues.
        return _ventana("semanal", self.VIERNES, dias_hasta_cierre=1, hora_cierre=10, **kw)

    def test_el_viernes_a_las_10_se_abre(self):
        a = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 7, 10, 30), ventanas=[self._v()])
        assert _claves(a) == ["semanal_abierto"]
        assert a[0]["variantes"][0]["titulo"] == "Tu reporte semanal está abierto"
        assert "hasta mañana a las 10:00" in a[0]["variantes"][0]["cuerpo"]
        assert len(a[0]["variantes"]) == 3

    def test_el_viernes_antes_de_las_10_nada(self):
        assert avisos_de_calendario_doc(ahora_es=_es(2026, 8, 7, 9, 59),
                                        ventanas=[self._v()]) == []

    def test_el_sabado_desde_las_8_se_le_recuerda_si_no_lo_mando(self):
        a = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 8, 8), ventanas=[self._v()])
        assert _claves(a) == ["semanal_ultimo"]
        assert a[0]["variantes"][0]["cuerpo"] == "Se cierra hoy a las 10:00."

    def test_si_ya_lo_mando_no_se_le_recuerda(self):
        a = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 8, 8),
                                     ventanas=[self._v(mandado=True)])
        assert a == []

    def test_aplazado_apaga_el_recordatorio(self):
        a = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 8, 8),
                                     ventanas=[{**self._v(), "aplazado": True}])
        assert a == []

    def test_el_domingo_ya_no_se_insiste(self):
        """El semanal no lleva el aviso del martes ('no me llego'): a la semana
        siguiente ya le toca el suyo, como al quincenal."""
        assert avisos_de_calendario_doc(ahora_es=_es(2026, 8, 9, 9),
                                        ventanas=[self._v()]) == []


class TestElMensual:
    VIERNES = _es(2026, 8, 7, 0)        # 2026-08-07 es viernes

    def _v(self, **kw):
        # El mensual cierra el lunes a las 18:00: tres dias despues del viernes.
        return _ventana("mensual", self.VIERNES, dias_hasta_cierre=3, hora_cierre=18, **kw)

    def test_el_viernes_se_abre(self):
        a = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 7, 10), ventanas=[self._v()])
        assert _claves(a) == ["mensual_abierto"]
        assert len(a[0]["variantes"]) == 3

    def test_el_sabado_no_se_repite_el_de_apertura(self):
        assert avisos_de_calendario_doc(ahora_es=_es(2026, 8, 8, 10), ventanas=[self._v()]) == []

    def test_el_domingo_a_las_10_el_ultimo_dia(self):
        a = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 9, 10), ventanas=[self._v()])
        assert _claves(a) == ["mensual_ultimo"]

    def test_el_domingo_a_las_9_todavia_no(self):
        assert avisos_de_calendario_doc(ahora_es=_es(2026, 8, 9, 9), ventanas=[self._v()]) == []

    def test_si_ya_lo_mando_el_domingo_no_le_llega(self):
        assert avisos_de_calendario_doc(ahora_es=_es(2026, 8, 9, 11),
                                        ventanas=[self._v(mandado=True)]) == []

    def test_el_martes_no_me_llego_tu_reporte(self):
        """Cierra el lunes a las 18:00; el martes es el dia siguiente. Es el correo mas
        abierto de ActiveCampaign (18,9 %) y hoy en la app no existe."""
        a = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 11, 9), ventanas=[self._v()])
        assert _claves(a) == ["reporte_no_llego"]
        # Plural desde el 23-08 (punto 57: la voz de la app es «nosotros»).
        assert a[0]["variantes"][0]["titulo"] == "No nos llegó tu reporte"

    def test_el_martes_si_lo_mando_no(self):
        assert avisos_de_calendario_doc(ahora_es=_es(2026, 8, 11, 9),
                                        ventanas=[self._v(mandado=True)]) == []

    def test_el_lunes_a_las_17_todavia_esta_a_tiempo(self):
        """Antes de que cierre no se le puede decir que no llegó: aun puede mandarlo."""
        assert avisos_de_calendario_doc(ahora_es=_es(2026, 8, 10, 17),
                                        ventanas=[self._v()]) == []

    def test_el_miercoles_ya_no_se_insiste(self):
        assert avisos_de_calendario_doc(ahora_es=_es(2026, 8, 12, 9), ventanas=[self._v()]) == []


class TestElFinDeCiclo:
    """"semana 11, con el mensual"."""

    VIERNES = _es(2026, 8, 7, 0)

    def _v(self, semana=11):
        return _ventana("mensual", self.VIERNES, semana=semana,
                        dias_hasta_cierre=3, hora_cierre=18)

    def test_en_la_11_de_un_ciclo_de_12_y_con_el_mensual_abierto(self):
        a = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 7, 10), cliente_id="c1",
                                     semana=11, semanas_ciclo=12, ventanas=[self._v()])
        assert "fin_ciclo" in _claves(a)
        fin = [x for x in a if x["clave"].startswith("fin_ciclo")][0]
        assert fin["variantes"][0]["titulo"] == "Tu ciclo acaba en una semana"
        assert fin["variantes"][1]["titulo"] == "Queda una semana"

    def test_antes_de_que_abra_el_mensual_no(self):
        """El doc lo pone AL LADO del reporte, no suelto a mitad de semana."""
        a = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 5, 10), cliente_id="c1",
                                     semana=11, semanas_ciclo=12, ventanas=[self._v()])
        assert _claves(a) == []

    def test_en_la_semana_5_no(self):
        """Sale el del mensual, que ahi si toca, pero el del fin de ciclo no."""
        a = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 7, 10), cliente_id="c1",
                                     semana=5, semanas_ciclo=12, ventanas=[self._v(5)])
        assert _claves(a) == ["mensual_abierto"]

    def test_el_viejo_se_calla_cuando_manda_el_del_doc(self):
        perfil = {"ajuste_macros_completado": True, "week": 11, "id": "c1"}
        assert _claves(avisos_de_calendario(perfil=perfil, ahora=AHORA, semanas_ciclo=12)) == ["fin_ciclo"]
        assert avisos_de_calendario(perfil=perfil, ahora=AHORA, semanas_ciclo=12, nuevos=True) == []


class TestLoQueSeQuedaDelSistemaViejo:
    """Los tres de calendario que el doc no reescribe siguen igual."""

    def test_los_macros_provisionales_avisan_a_las_dos_horas(self):
        perfil = {"created_at": (AHORA - timedelta(hours=2, minutes=1)).isoformat()}
        assert _claves(avisos_de_calendario(perfil=perfil, ahora=AHORA,
                                            va_a_recibir_definitivos=True)) == ["macros_provisionales"]

    def test_si_se_los_puso_su_coach_no_son_provisionales(self):
        """El fallo del punto 4.1, que en produccion afectaba a los 174 clientes activos."""
        perfil = {"created_at": (AHORA - timedelta(days=40)).isoformat()}
        assert _claves(avisos_de_calendario(perfil=perfil, ahora=AHORA,
                                            va_a_recibir_definitivos=True)) == ["macros_provisionales"]
        assert avisos_de_calendario(perfil=perfil, ahora=AHORA,
                                    va_a_recibir_definitivos=True,
                                    macros_puestos_por_alguien=True) == []

    def test_solo_le_sale_a_quien_va_a_recibir_unos_definitivos(self):
        """Punto 04 del doc del 19-08: «ese mensaje promete unos definitivos, y eso solo se
        cumple en tres casos... Si le sale a alguien más, le estamos prometiendo algo que no
        va a recibir». Al de Calculadora y al de Mantenimiento no le manda nadie nada el
        miércoles: sus macros son los que salieron de su cuestionario."""
        perfil = {"created_at": (AHORA - timedelta(days=1)).isoformat()}
        assert avisos_de_calendario(perfil=perfil, ahora=AHORA,
                                    va_a_recibir_definitivos=False) == []

    def test_el_texto_es_el_de_jesus(self):
        """Literal del punto 04. «"Finos" no lo digo yo. El texto es este.»"""
        perfil = {"created_at": (AHORA - timedelta(days=1)).isoformat()}
        a = avisos_de_calendario(perfil=perfil, ahora=AHORA, va_a_recibir_definitivos=True)[0]
        assert a["titulo"] == "Estos son tus macros provisionales."
        assert a["cuerpo"] == "Unas preguntas más y recibirás los definitivos."

    def test_la_rutina_avisa_tres_dias_antes_y_solo_si_esta_encendida(self):
        base = {"perfil": {"ajuste_macros_completado": True}, "ahora": AHORA}
        assert avisos_de_calendario(**base, rutina_caduca=AHORA + timedelta(days=3),
                                    rutina_visible=True)
        assert avisos_de_calendario(**base, rutina_caduca=AHORA + timedelta(days=3),
                                    rutina_visible=False) == []
        assert avisos_de_calendario(**base, rutina_caduca=AHORA, rutina_visible=True) == []


# Todos los avisos del doc 16-08, forzando a la vez cada condicion que los dispara.
TODOS_LOS_AVISOS = (
    avisos_condicionados(ahora=AHORA, semanas_sin_ajustar=8, reporte_sin_fotos=True,
                         dias_sin_cerrar=30, dias_sin_entrar=30)
    + avisos_de_calendario_doc(
        ahora_es=_es(2026, 8, 2, 20), cliente_id="c1", arranque=date(2026, 8, 3),
        cerro_hoy=False, semana=11, semanas_ciclo=12,
        ventanas=[_ventana("quincenal", _es(2026, 8, 2, 9)),
                  _ventana("mensual", _es(2026, 8, 2, 0), semana=11,
                           dias_hasta_cierre=3, hora_cierre=18)])
    + avisos_de_calendario_doc(
        ahora_es=_es(2026, 8, 3, 9),
        ventanas=[_ventana("quincenal", _es(2026, 8, 2, 9))])
    + avisos_de_calendario_doc(
        ahora_es=_es(2026, 8, 4, 10),
        ventanas=[_ventana("mensual", _es(2026, 8, 2, 0), dias_hasta_cierre=3, hora_cierre=18)])
    + avisos_de_calendario_doc(
        ahora_es=_es(2026, 8, 6, 10),
        ventanas=[_ventana("mensual", _es(2026, 8, 2, 0), dias_hasta_cierre=3, hora_cierre=18)])
)


def test_estan_los_diecinueve_menos_los_que_dependen_de_otra_tarea():
    """Los 19 del doc: 8 de calendario + 6 de accion de Jesus + 4 condicionadas + 1 de
    confirmacion. Aqui se comprueban los que son REGLA (calendario y condicionadas); los
    otros siete se disparan al guardar y viven en `routes/notifications.py`."""
    familias = {a["familia"] for a in TODOS_LOS_AVISOS}
    assert familias == {
        "arranque", "cierra_dia", "quincenal_abierto", "quincenal_ultimo",
        "mensual_abierto", "mensual_ultimo", "reporte_no_llego", "fin_ciclo",
        "sin_fotos", "sin_ajustar", "sin_cerrar", "sin_entrar",
    }


class TestElTono:
    """"todas escritas desde el alivio, no desde la exigencia". Se miran TODAS las
    variantes: da igual cual toque hoy, ninguna puede sonar a reproche."""

    @pytest.mark.parametrize("prohibida", [
        "fuerza de voluntad", "excusa", "vago", "deberías", "deberias",
        "no has", "otra vez", "te lo dijimos", "incumpl", "fallado", "abandonar",
    ])
    def test_ninguno_regaña(self, prohibida):
        for a in TODOS_LOS_AVISOS:
            for t in textos_de(a):
                texto = f"{t['titulo']} {t.get('cuerpo') or ''}".lower()
                assert prohibida not in texto, f"«{t['titulo']}» suena a reproche"

    def test_ninguno_lleva_guiones_largos(self):
        """Regla de la casa: guion normal, ni em-dash ni en-dash."""
        for a in TODOS_LOS_AVISOS:
            for t in textos_de(a):
                texto = f"{t['titulo']} {t.get('cuerpo') or ''}"
                assert "—" not in texto and "–" not in texto, f"«{t['titulo']}»"

    def test_la_de_los_macros_es_factual_y_va_directa(self):
        """La unica que el documento quiere directa: es un dato, no un juicio."""
        a = avisos_condicionados(ahora=AHORA, semanas_sin_ajustar=5)[0]
        assert a["variantes"][0]["titulo"] == "Llevas 5 semanas con los mismos macros"

    def test_al_que_lleva_una_semana_fuera_se_le_deja_la_puerta_abierta(self):
        # «¿Todo bien?» (doc 19-08), y el tono sigue siendo el de siempre: sin reproche.
        a = avisos_condicionados(ahora=AHORA, dias_sin_entrar=20)[0]
        assert a["variantes"][0]["titulo"] == "¿Todo bien?"
        assert "Retomamos cuando quieras." in a["variantes"][0]["cuerpo"]
        assert "Sin prisa." in a["variantes"][1]["cuerpo"]

    def test_todos_llevan_a_algun_sitio(self):
        """Un aviso sin sitio al que ir es solo ruido."""
        for a in TODOS_LOS_AVISOS:
            assert a.get("link"), f"«{textos_de(a)[0]['titulo']}» no lleva a ninguna parte"


# ── Los enlaces existen de verdad (punto 10 del doc del 07-08) ───────────────
#
# El aviso de los macros provisionales llevaba a /dashboard/ajustar-macros, que no existe
# porque la pantalla está en /dashboard/macro-calculator. Una dirección que no existe cae en
# el comodín del router, y el comodín mandaba al login: el cliente nuevo pulsaba la primera
# notificación de su vida en la app y acababa en la pantalla de identificarse.
#
# Esto lee las rutas de verdad del router y las cruza con los enlaces de los avisos, así que
# renombrar una pantalla y olvidarse de un aviso vuelve a saltar aquí y no en el móvil de un
# cliente.

import os
import re

APP_JS = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src", "App.js")


def _rutas_declaradas():
    """Las direcciones que el router sabe pintar, montadas desde App.js."""
    with open(APP_JS, encoding="utf-8") as fh:
        fuente = fh.read()
    sueltas, hijas, padre = set(), set(), None
    for linea in fuente.splitlines():
        m = re.search(r'path="([^"]+)"', linea)
        if not m:
            continue
        ruta = m.group(1)
        if ruta.startswith("/"):
            padre = ruta.rstrip("/")
            sueltas.add(padre or "/")
        elif ruta != "*" and padre:
            hijas.add(f"{padre}/{ruta}")
    return sueltas | hijas


# Los enlaces de los avisos que se disparan al guardar (los seis de Jesús y el de
# confirmación) no salen de las reglas puras, así que se listan aquí para que pasen por la
# misma comprobación: son los que llevan al cliente a Nutrición, a Suplementos, a su
# entreno y a Seguimiento.
ENLACES_DE_LOS_AVISOS_DE_ACCION = [
    "/dashboard/nutrition", "/dashboard/supplements", "/dashboard/routine",
    "/dashboard/reports",
]


class TestLosEnlacesLlevanADondeDicen:

    @pytest.fixture(scope="class")
    def rutas(self):
        r = _rutas_declaradas()
        assert "/dashboard/macro-calculator" in r, "no se han podido leer las rutas de App.js"
        return r

    @pytest.mark.parametrize("aviso", TODOS_LOS_AVISOS)
    def test_el_enlace_existe_en_el_router(self, aviso, rutas):
        link = (aviso.get("link") or "").split("?")[0].rstrip("/") or "/"
        assert link in rutas, (
            f"«{textos_de(aviso)[0]['titulo']}» lleva a {link}, que no es ninguna pantalla "
            f"de la app: el cliente acabaría fuera de donde quería ir")

    @pytest.mark.parametrize("link", ENLACES_DE_LOS_AVISOS_DE_ACCION)
    def test_los_de_accion_tambien(self, link, rutas):
        assert link in rutas

    def test_el_de_los_macros_provisionales_va_a_la_pantalla_de_macros(self):
        """El caso concreto que echaba al cliente al login: lo recibe todo el que espera
        unos definitivos a las dos horas de darse de alta, así que suele ser lo primero
        que toca de la app."""
        perfil = {"created_at": (AHORA - timedelta(days=1)).isoformat()}
        provisionales = [a for a in avisos_de_calendario(perfil=perfil, ahora=AHORA,
                                                         va_a_recibir_definitivos=True)
                         if a["clave"].startswith("macros_provisionales")]
        assert provisionales, "ya no existe ese aviso: si se quitó, quitar también este test"
        assert provisionales[0]["link"] == "/dashboard/macro-calculator"
