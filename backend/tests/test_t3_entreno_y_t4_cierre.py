"""
T3 (el registro del entreno) y T4 (el cierre del día), del doc 16-08.

La mayoría son puros: el día de rutina que toca, la cabecera de la pantalla y qué comida
se quedó sin registrar se pueden probar sin base y sin servidor. Los de HTTP comprueban
el contrato de `models/workout_log.py`, que es de donde va a salir el "entrenaste X de Y"
de Inicio y de los reportes.
"""
import pytest
import requests

from routes.checkins import ETIQUETA_COMIDA, _comidas_sin_registrar, _orden_de_comidas
from routes.workout_logs import DIAS_SEMANA, dia_de_rutina, numero_de_rutina, titulo_del_dia


RUTINA = {
    "id": "r1",
    "days": [
        {"day": "Lunes", "is_rest": False, "grupo": "Pecho, tríceps",
         "exercises": [{"name": "Press banca"}]},
        {"day": "Martes", "is_rest": True, "exercises": []},
        # Con tilde, que es como lo escribe el generador de rutinas.
        {"day": "Miércoles", "is_rest": False, "grupo": "Espalda, bíceps", "exercises": []},
        {"day": "Jueves", "is_rest": True, "exercises": []},
        {"day": "Viernes", "is_rest": False, "grupo": "Pierna, abdomen", "exercises": []},
        {"day": "Sábado", "is_rest": True, "exercises": []},
        {"day": "Domingo", "is_rest": True, "exercises": []},
    ],
}


# ── El día de rutina que toca ─────────────────────────────────────────────────

class TestQueLeTocaHoy:
    def test_el_lunes_le_toca_pecho(self):
        # 2026-08-17 es lunes.
        dia = dia_de_rutina(RUTINA, "2026-08-17")
        assert dia and titulo_del_dia(dia) == "Pecho, tríceps"

    def test_el_miercoles_con_tilde_tambien_casa(self):
        """La rutina guarda "Miércoles" y el calendario dice "miercoles": comparar las dos
        cadenas tal cual da falso, y entonces un día de entreno pasa por día de descanso."""
        dia = dia_de_rutina(RUTINA, "2026-08-19")
        assert dia and titulo_del_dia(dia) == "Espalda, bíceps"

    def test_un_dia_de_descanso_no_es_un_dia_de_rutina(self):
        assert dia_de_rutina(RUTINA, "2026-08-18") is None      # martes

    def test_sin_rutina_no_hay_dia(self):
        assert dia_de_rutina(None, "2026-08-17") is None
        assert dia_de_rutina({"days": []}, "2026-08-17") is None

    def test_una_fecha_que_no_se_entiende_no_revienta(self):
        assert dia_de_rutina(RUTINA, "manana") is None

    def test_los_dias_estan_en_el_orden_de_weekday(self):
        # weekday() devuelve 0 para el lunes: si esta tupla se desordena, a todo el mundo
        # le toca el entreno de otro día y nadie lo ve fallar.
        assert DIAS_SEMANA[0] == "lunes" and DIAS_SEMANA[6] == "domingo"

    def test_la_cabecera_no_se_inventa_un_grupo_muscular(self):
        assert titulo_del_dia({"day": "Lunes", "exercises": []}) == "Entreno de hoy"
        assert titulo_del_dia(None) == "Entreno de hoy"

    def test_un_dia_de_solo_cardio_se_llama_cardio(self):
        assert titulo_del_dia({"day": "Lunes", "exercises": [], "cardio": {"minutos": 40}}) == "Cardio"

    def test_que_numero_de_rutina_hace_el_dia(self):
        # "Semana 6 · rutina 3": el viernes es el tercer día de entreno de la semana.
        assert numero_de_rutina(RUTINA, dia_de_rutina(RUTINA, "2026-08-21")) == 3
        assert numero_de_rutina(RUTINA, dia_de_rutina(RUTINA, "2026-08-17")) == 1
        assert numero_de_rutina(RUTINA, None) is None


# ── La comida que se quedó sin registrar ──────────────────────────────────────

class TestLaComidaQueFalta:
    def test_el_orden_mete_el_peri_en_el_momento_del_entreno(self):
        dieta = {"num_comidas": 4, "opcion_peri": "intra_post", "momento_entreno": 2}
        assert _orden_de_comidas(dieta) == ["C1", "C2", "Intra", "Post", "C3", "C4"]

    def test_sin_peri_son_las_comidas_y_ya(self):
        assert _orden_de_comidas({"num_comidas": 3, "opcion_peri": "sin_peri"}) == ["C1", "C2", "C3"]

    def test_salen_TODAS_las_que_faltan_y_en_orden(self):
        """El aviso de arriba del cierre las lista («Comida 3 · Comida 4», punto 16 del
        doc 24-08). Devolvía solo la última porque antes se preguntaba por una sola."""
        dieta = {"num_comidas": 3, "comidas": {
            "C1": {"alimentos": [{"nombre": "Avena"}]},
            "C2": {"alimentos": []},
            "C3": {"alimentos": []},
        }}
        assert _comidas_sin_registrar(dieta) == ["C2", "C3"]

    def test_si_esta_todo_registrado_no_se_avisa_de_nada(self):
        dieta = {"num_comidas": 2, "comidas": {
            "C1": {"alimentos": [{"nombre": "Avena"}]},
            "C2": {"alimentos": [{"nombre": "Pollo"}]},
        }}
        assert _comidas_sin_registrar(dieta) == []

    def test_sin_dieta_no_se_avisa(self):
        """Un día sin dieta montada no tiene nada a medias: no hay nada que reclamarle."""
        assert _comidas_sin_registrar(None) == []

    def test_a_la_comida_se_la_llama_por_su_numero(self):
        # Decisión del 09-08: al cliente no se le dice "cena" ni "desayuno". El literal
        # del doc ("Te queda la {comida} sin registrar") se rellena con esto.
        assert ETIQUETA_COMIDA["C3"] == "comida 3"
        assert ETIQUETA_COMIDA["Post"] == "post-entreno"


# ── El contrato por HTTP ──────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def entreno_encendido(api_disponible, cabeceras_admin):
    """T3 vive detrás del interruptor `t3_entreno`: sin encenderlo no hay nada que probar."""
    r = requests.put(f"{api_disponible}/admin/settings", headers=cabeceras_admin,
                     json={"pantallas": {"t3_entreno": True}}, timeout=15)
    assert r.status_code == 200
    return r.json()["pantallas"]


class TestElRegistroDeEntreno:
    def test_hoy_trae_lo_que_la_pantalla_necesita(self, api_disponible, cabeceras_cliente, entreno_encendido):
        r = requests.get(f"{api_disponible}/workout-logs/hoy", headers=cabeceras_cliente, timeout=15)
        assert r.status_code == 200
        d = r.json()
        # El contrato de models/workout_log.py: `log` está siempre, aunque sea a null.
        assert "log" in d
        for clave in ("fecha", "tiene_rutina", "dia_rutina", "semana", "pesos_referencia"):
            assert clave in d, f"falta {clave}: la pantalla no puede pintarse sin eso"

    def test_guardar_dos_veces_el_mismo_dia_corrige_y_no_duplica(
            self, api_disponible, cabeceras_cliente, entreno_encendido):
        """Es LA regla de la colección: si cada guardado creara una fila, "entrenaste 14 de
        16" contaría los arrepentimientos como entrenos."""
        antes = requests.get(f"{api_disponible}/workout-logs", headers=cabeceras_cliente,
                             timeout=15).json()["logs"]

        r = requests.post(f"{api_disponible}/workout-logs", headers=cabeceras_cliente, timeout=15,
                          json={"hecho": True, "estrellas": 3,
                                "pesos": [{"ejercicio": "Press banca", "reps": 8, "peso_kg": 80}]})
        assert r.status_code == 200
        r = requests.post(f"{api_disponible}/workout-logs", headers=cabeceras_cliente, timeout=15,
                          json={"hecho": True, "estrellas": 5})
        assert r.status_code == 200
        assert r.json()["log"]["estrellas"] == 5, "el segundo guardado corrige al primero"

        despues = requests.get(f"{api_disponible}/workout-logs", headers=cabeceras_cliente,
                               timeout=15).json()["logs"]
        de_hoy = [l for l in despues if l["fecha"] == r.json()["log"]["fecha"]]
        assert len(de_hoy) == 1, "una fila por día, pase lo que pase"
        assert len(despues) <= len(antes) + 1

    def test_las_estrellas_van_de_1_a_5(self, api_disponible, cabeceras_cliente, entreno_encendido):
        r = requests.post(f"{api_disponible}/workout-logs", headers=cabeceras_cliente, timeout=15,
                          json={"hecho": True, "estrellas": 9})
        assert r.status_code == 422

    def test_apagado_el_interruptor_no_se_puede_registrar(
            self, api_disponible, cabeceras_admin, cabeceras_cliente):
        """Y el mensaje no es técnico: el cliente lee una frase, no un flag."""
        requests.put(f"{api_disponible}/admin/settings", headers=cabeceras_admin,
                     json={"pantallas": {"t3_entreno": False}}, timeout=15)
        try:
            r = requests.get(f"{api_disponible}/workout-logs/hoy", headers=cabeceras_cliente, timeout=15)
            assert r.status_code == 403
            assert "disponible" in r.json()["detail"]
        finally:
            requests.put(f"{api_disponible}/admin/settings", headers=cabeceras_admin,
                         json={"pantallas": {"t3_entreno": True}}, timeout=15)


class TestElCierreDelDia:
    def test_dice_lo_que_le_falta_hoy(self, api_disponible, cabeceras_cliente):
        r = requests.get(f"{api_disponible}/checkins/hoy", headers=cabeceras_cliente, timeout=20)
        assert r.status_code == 200
        d = r.json()
        for clave in ("fecha", "hecho", "entreno", "suplementos", "comidas_pendientes",
                      "ultimo_peso",
                      # NUEVA (24-08): cuantos dias atras acepta el servidor que se feche un
                      # pesaje. Viaja para que el desplegable de la pantalla ofrezca
                      # exactamente lo que se acepta; si deja de venir, el desplegable se
                      # inventa su propio tope y vuelve a haber dos reglas.
                      "peso_dias_atras"):
            assert clave in d, f"falta {clave}"
        # `exceso` YA NO VIENE, y no es un olvido: la pregunta del exceso de macros dejó de
        # existir con las once de Jesús (fallo 8 del repaso del 24-08) y con ella se fue el
        # cálculo del servidor. Se comprueba que NO está para que no vuelva a colarse un
        # dato que ya no se le enseña a nadie y que costaba una consulta de la dieta entera
        # cada vez que se abría el cierre.
        assert "exceso" not in d
        # La fecha es la del cliente (España), en formato de día.
        assert len(d["fecha"]) == 10

    def test_el_modelo_acepta_lo_nuevo_sin_soltar_lo_viejo(self):
        from models.common import CheckInCreate

        c = CheckInCreate(type="daily", descanso=4, movimiento="mas",
                          suplementos={"respuesta": "no_todos", "detalle": "La creatina."},
                          cena_hecha=True, comida_pendiente="C4",
                          notas={"texto": "Sin ganas pero entrené.", "compartida": False})
        assert c.descanso == 4 and c.suplementos.respuesta == "no_todos"
        assert c.notas.compartida is False, "lo que no comparte no se comparte"
        # Y lo de antes se sigue aceptando: los check-ins viejos no se tiran.
        viejo = CheckInCreate(type="daily", energy=3, hunger_anxiety=2, comido_hoy="Un café")
        assert viejo.energy == 3 and viejo.descanso is None

    def test_las_escalas_no_admiten_cualquier_cosa(self):
        from pydantic import ValidationError
        from models.common import CheckInCreate

        with pytest.raises(ValidationError):
            CheckInCreate(type="daily", descanso=7)
        with pytest.raises(ValidationError):
            CheckInCreate(type="daily", movimiento="regular")
