# -*- coding: utf-8 -*-
"""El cierre del dia rehecho: las once preguntas y la pantalla del doc 24-08 (1 a 23, 32).

Cada prueba empieza por la persona a la que le pasaba:

  1. Al cliente se le preguntaba SIETE cosas y ninguna era «como te fue el dia», «¿entrenaste
     hoy?» ni «¿hiciste cardio?». Ahora son once, y las cuatro nuevas tienen donde guardarse.

  2. Cuatro clientes activos con protocolo de suplementacion de su etapa anterior, y un plan
     que NO incluye suplementacion, recibian todas las noches «¿Tomaste tus suplementos?» por
     unos suplementos que su pantalla no les deja ni ver. El candado del cierre es ahora el
     mismo que el de la pantalla.

  3. El que se dejo dos comidas sin registrar veia «Te queda la comida 4 sin registrar»: el
     servidor calculaba la lista entera y devolvia solo la cola. Ahora devuelve la lista.

  4. El que se pesa por la mañana y cierra su dia de madrugada -- o el que se peso ayer y lo
     apunta hoy -- metia el pesaje en el dia que no era, y la pareja de dias seguidos desde
     el miercoles, de la que sale la media semanal, no se formaba nunca.

  5. El Diario del cliente. Aqui se probo a meter TODOS sus dias (punto 23) y se deshizo el
     mismo dia: components/Diario.jsx solo sabe pintar fecha, texto y nota de entreno, asi
     que al que cierra a diario le salian veinte tarjetas con la fecha y nada debajo. Lo que
     si viaja ya es `dia_resumen`, para que ese traslado sea pintar y nada mas.

  6. Los 81 de ELM, Mantenimiento, Calculadora JP y Basica. Entraban al cierre (la puerta de
     la app va por `cierre_dia`), contestaban las once y el Guardar les devolvia un 403: el
     cerrojo del servidor seguia pidiendo «reportes», que su plan no vende.

Casi todas son puras: llaman a la pieza o leen la pantalla. La de HTTP se salta sola si no
hay backend vivo.
"""
import os
import time
from pathlib import Path

import pytest
import requests

from routes.checkins import _comidas_sin_registrar, _dia_del_pesaje, ETIQUETA_COMIDA
from routes.diary import _entrada_del_dia, _resumen_del_dia
from models.common import CheckInCreate, CheckInResponse

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


# ============ 1. LAS CUATRO PREGUNTAS NUEVAS ============

class TestLoQueSeGuardaDeLasOnce:
    def test_las_cuatro_nuevas_entran_y_vuelven(self):
        c = CheckInCreate(type="daily", sensaciones=4, entreno_respuesta="si",
                          entreno_estrellas=3, cardio="no_tocaba", extras_respuesta="si")
        assert c.sensaciones == 4
        assert c.entreno_estrellas == 3
        assert c.cardio == "no_tocaba"
        assert c.extras_respuesta == "si"
        r = CheckInResponse(id="x", client_id="y", type="daily", created_at="2026-08-24T21:00:00+00:00",
                            sensaciones=4, entreno_respuesta="si", entreno_estrellas=3,
                            cardio="no_tocaba", extras_respuesta="si")
        assert (r.sensaciones, r.entreno_estrellas, r.cardio, r.extras_respuesta) == (4, 3, "no_tocaba", "si")

    def test_las_sensaciones_NO_reaprovechan_el_animo_viejo(self):
        """`mood` es la carita del check-in de antes, con otra escala y con filas escritas
        en mayo. Mezclarlas dejaria dos preguntas distintas en la misma media."""
        c = CheckInCreate(type="daily", sensaciones=5)
        assert c.mood is None
        modelo = _fuente("backend/models/common.py")
        assert "sensaciones: Optional[int] = Field(None, ge=1, le=5)" in modelo

    def test_el_entreno_admite_los_tres_estados_y_los_dos_viejos(self):
        for valor in ("si", "no", "descanso", "si_no_lo_puse", "no_entrene"):
            assert CheckInCreate(type="daily", entreno_respuesta=valor).entreno_respuesta == valor

    @pytest.mark.parametrize("campo,valor", [
        ("sensaciones", 6), ("sensaciones", 0),
        ("entreno_estrellas", 9), ("cardio", "quiza"),
        ("entreno_respuesta", "puede"), ("extras_respuesta", "tal_vez"),
        ("mood", 9),
    ])
    def test_no_se_cuela_cualquier_cosa(self, campo, valor):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            CheckInCreate(type="daily", **{campo: valor})


class TestLasOncePreguntasEnLaPantalla:
    # TRES LITERALES CAMBIARON EL 31-08, CON EL DOC «El día». No se borran de aquí sin
    # decir por qué, que es la única forma de que dentro de un mes se sepa si se cayeron a
    # propósito o se perdieron:
    #
    #   - «Sensaciones generales del día» SE FUE de la pantalla. Ya no está en la lista de
    #     preguntas del documento. El campo se sigue guardando y el historial de quien lo
    #     tenga contestado lo sigue pintando, así que el modelo no se toca.
    #   - «¿Tomaste tus suplementos?» pasa a «¿Tomaste la suplementación que tenías
    #     pautada?», y la opción del medio de «No todos» a «No toda».
    #   - La ayuda de los extras pasa a pedir en vez de describir.
    @pytest.mark.parametrize("literal", [
        "¿Entrenaste hoy?",
        "¿Cómo fue?",
        "¿Hiciste cardio?",
        "¿Te moviste lo suficiente?",
        "¿Tomaste la suplementación que tenías pautada?",
        "¿Se te ha escapado algo más hoy?",
        "Si no lo pusiste en el apartado de extras, ponlo ahora",
        "¿Cómo descansaste la noche de ayer?",
        "Niveles de energía durante el día",
        "Hambre / ansiedad con la dieta",
        "Notas personales",
        "Esto es para tu diario. Lo puedes compartir con nosotros o quedártelo para ti",
        "Cosas que quieras acordarte del entreno y de la dieta",
        "Registrarlo es opcional, sólo para ti. Te lo pediremos sólo para los reportes",
    ])
    def test_los_literales_de_jesus_van_palabra_por_palabra(self, literal):
        assert literal in _fuente(PANTALLA)

    def test_las_estrellas_son_el_componente_que_ya_existia(self):
        """Ni un segundo dibujo de estrellas: el de los reportes acepta lo que hace falta."""
        pantalla = _fuente(PANTALLA)
        assert "import { Estrellas } from '../components/reports/piezas';" in pantalla

    def test_como_fue_cuelga_del_si_y_va_sangrada(self):
        pantalla = _fuente(PANTALLA)
        i = pantalla.find("f.entreno_respuesta === 'si' && (")
        assert i > 0, "«¿Cómo fue?» tiene que colgar del «Sí»"
        assert "pl-3 border-l-2" in pantalla[i:i + 400], "y salir sangrada"


# ============ 2. LA REGLA DEL COLOR Y EL GUARDAR ============

class TestComoSeComportaLaPantalla:
    def test_todas_a_la_vista(self):
        """SE ACABÓ EL ACORDEÓN (doc «El día», 31-08): «todas a la vista, sin plegar nada».

        Hasta el 31-08 iba una encendida cada vez -- la primera sin contestar, salvo que el
        cliente reabriera otra a mano -- y la encendida era la naranja. El documento pide lo
        contrario, así que se cae la cadena y con ella el `abierta`.

        Y con el acordeón se cae también el naranja de la tarjeta: marcaba «esta es la que
        toca», y con las ocho abiertas no distingue nada. En esta app el naranja quiere decir
        «te has pasado» (punto 76), así que ocho tarjetas naranjas se leen como ocho errores.
        """
        pantalla = _fuente(PANTALLA)
        # Se miran los TOKENS del estado, no la palabra: «abierta» sigue apareciendo en los
        # comentarios que cuentan por qué se fue, y eso es lo que se quiere conservar.
        assert "const [abierta," not in pantalla, "queda el estado del acordeón"
        assert "setAbierta" not in pantalla, "queda quien lo apagaba y encendía"
        assert "encendida" in pantalla, "el componente sigue recibiendo el flag, siempre a true"
        assert "border-brand bg-brand/5" not in pantalla, (
            "la tarjeta ya no se pinta de naranja por estar abierta")

    def test_al_contestar_hay_tick_y_respuesta_debajo(self):
        pantalla = _fuente(PANTALLA)
        assert 'data-testid={`${testId}-tick`}' in pantalla
        assert 'data-testid={`${testId}-resumen`}' in pantalla

    def test_contestar_no_pliega_la_tarjeta(self):
        """Lo que el punto 18 resolvía con el «vuelve a encenderse al tocarla» ya no hace
        falta: nunca se apaga. Contestar solo guarda el valor (doc «El día», 31-08).

        Se comprueba por el lado de que NO vuelva a colarse el plegado, que es lo que este
        caso vigilaba desde el otro lado.
        """
        pantalla = _fuente(PANTALLA)
        assert "onAbrir={() => setAbierta" not in pantalla
        assert "const responder = (campo, valor) => set(campo, valor);" in pantalla

    def test_el_guardar_esta_apagado_hasta_el_final_Y_DICE_QUE_FALTA(self):
        """Un Guardar apagado sin decir por que es peor que uno encendido."""
        pantalla = _fuente(PANTALLA)
        assert "disabled={enviando || faltan.length > 0}" in pantalla
        assert "const faltan = pendientes.map(p => p.titulo);" in pantalla
        assert "Te queda por contestar:" in pantalla

    def test_las_notas_y_el_peso_no_bloquean_el_guardar(self):
        """Son opcionales por diseño: si contaran, el que no quiere pesarse ni escribir se
        queda sin poder cerrar su dia. Por eso no estan en la lista de preguntas."""
        pantalla = _fuente(PANTALLA)
        i = pantalla.find("const preguntas = [")
        j = pantalla.find("].filter(p => p.visible);", i)
        assert 0 < i < j
        bloque = pantalla[i:j]
        assert "id: 'notas'" not in bloque and "id: 'peso'" not in bloque

    def test_fuera_la_galeria_de_fotos_y_el_boton_de_diario_puesto(self):
        """Punto 17: «Anotado. Mañana seguimos · Editar lo de hoy · Ver mi diario. Y nada
        mas»."""
        pantalla = _fuente(PANTALLA)
        assert "PhotosSection api={api}" not in pantalla
        assert "Ver mi diario" in pantalla
        assert "/dashboard/reports?abrir=diario" in pantalla


# ============ 3. LA DIETA DE HOY, ARRIBA DEL TODO ============

class TestLasComidasSinRegistrar:
    def test_se_devuelven_todas_y_en_orden(self):
        dieta = {"num_comidas": 4, "comidas": {
            "C1": {"alimentos": [{"nombre": "Avena"}]},
            "C2": {"alimentos": [{"nombre": "Pollo"}]},
            "C3": {"alimentos": []},
            "C4": {"alimentos": []},
        }}
        assert _comidas_sin_registrar(dieta) == ["C3", "C4"]

    def test_el_peri_entra_en_el_orden_en_que_se_come(self):
        dieta = {"num_comidas": 3, "opcion_peri": "intra_post", "momento_entreno": 1,
                 "comidas": {"C1": {"alimentos": [{"nombre": "Avena"}]}}}
        assert _comidas_sin_registrar(dieta) == ["Intra", "Post", "C2", "C3"]

    def test_un_dia_con_solo_extras_no_es_un_dia_montado(self):
        """Apuntar un extra hace `upsert` en db.diets, asi que un dia al que solo le
        pusieron «dos cañas» tiene documento y ni una comida. Sin este corte, el cierre le
        avisaria de cuatro comidas sin registrar de un dia que nunca planifico."""
        assert _comidas_sin_registrar({"extras": [{"texto": "Dos cañas"}]}) == []
        assert _comidas_sin_registrar({"comidas": {}}) == []

    def test_la_etiqueta_va_con_mayuscula_para_la_lista(self):
        """«Comida 3 · Comida 4», que es como se lee en la pantalla. La de minusculas iba
        dentro de una frase («Te queda la comida 4 sin registrar») y se queda para eso."""
        assert ETIQUETA_COMIDA["C3"].capitalize() == "Comida 3"
        assert ETIQUETA_COMIDA["Post"].capitalize() == "Post-entreno"

    def test_la_pantalla_lo_avisa_antes_de_la_primera_pregunta(self):
        pantalla = _fuente(PANTALLA)
        assert "const sinRegistrar = hoy?.comidas_pendientes || [];" in pantalla
        assert "Te quedan ${sinRegistrar.length} comidas sin registrar" in pantalla
        assert "Puedes cerrarlas antes de seguir" in pantalla
        # EL OTRO ESTADO CAMBIÓ EL 31-08 (doc «El día»). Decía «Dieta registrada» y sólo
        # salía si había dieta montada -- por `hayDietaMontada`, que existía porque un día
        # al que sólo le apuntaron «dos cañas» tiene documento y ninguna comida, y decirle
        # «dieta registrada» habría sido mentira.
        #
        # Ahora el hueco dice «El día, todo bien · No te queda nada por registrar», y esa
        # frase sí es verdad no haya comidas pendientes, haya montado dieta o no. Por eso
        # se cae el candado: lo que cambió no es la condición, es lo que se afirma.
        assert "El día, todo bien" in pantalla
        assert "No te queda nada por registrar" in pantalla
        assert "hayDietaMontada = " not in pantalla
        # Ojo: «Dieta registrada» SIGUE en el fichero y tiene que seguir. Es otra cosa: la
        # línea del historial de un día pasado («· Dieta registrada»). Lo que se comprueba
        # es que no esté como AVISO de arriba.
        assert "<p className=\"text-sm text-foreground\">Dieta registrada</p>" not in pantalla
        # Y se va la casilla «La hice» de abajo: las dos no (decision de Jesus, 24-08).
        assert 'data-testid="cierre-comida-hecha"' not in pantalla


# ============ 4. EL PESO, CON SU FECHA ============

class TestElDiaDelPesaje:
    def test_sin_fecha_elegida_manda_el_dia_del_cierre(self):
        assert _dia_del_pesaje(None, "2026-08-24") == "2026-08-24"
        assert _dia_del_pesaje("", "2026-08-24") == "2026-08-24"

    def test_el_de_ayer_se_archiva_en_ayer(self):
        """Sin esto la pareja miercoles-jueves no se forma nunca y la semana se queda sin
        peso, que es de lo que sale la media semanal del doc 24-08."""
        assert _dia_del_pesaje("2026-08-23", "2026-08-24") == "2026-08-23"

    def test_no_se_puede_fechar_en_el_futuro(self):
        assert _dia_del_pesaje("2026-08-25", "2026-08-24") == "2026-08-24"

    def test_ni_mas_atras_de_dos_semanas(self):
        """Mas atras no le sirve a la regla del peso y si abre la puerta a rehacer la
        curva de hace un mes."""
        assert _dia_del_pesaje("2026-08-09", "2026-08-24") == "2026-08-24"   # 15 dias, fuera
        assert _dia_del_pesaje("2026-08-10", "2026-08-24") == "2026-08-10"   # 14 justos, entra

    def test_una_fecha_rara_no_tumba_el_cierre_de_nadie(self):
        assert _dia_del_pesaje("ayer", "2026-08-24") == "2026-08-24"
        assert _dia_del_pesaje("2026-13-40", "2026-08-24") == "2026-08-24"

    def test_la_pantalla_pregunta_de_que_dia_es(self):
        pantalla = _fuente(PANTALLA)
        assert "¿De qué día es este peso?" in pantalla
        assert "peso_fecha: f.weight ? pesoFecha : null," in pantalla


# ============ 5. EL DIARIO TRAE TODOS LOS DIAS ============

class TestElDiarioYaNoPideTexto:
    def test_el_diario_no_se_llena_de_tarjetas_vacias(self):
        """Se probo a meter TODOS los dias en el Diario (punto 23) y se deshizo el mismo
        dia: quien pinta esto es components/Diario.jsx, que de una entrada solo sabe
        enseñar fecha, texto y nota de entreno. Al que cierra a diario le salian veinte
        tarjetas con la fecha y nada debajo. El filtro se abre CUANDO este pintada la
        vista de dia, no antes."""
        codigo = _fuente("backend/routes/diary.py")
        i = codigo.find("async def _componer(")
        j = codigo.find("@router.get(\"/diary\")")
        assert 0 < i < j
        cuerpo = codigo[i:j]
        assert 'filtro_checkins = {"client_id": client_id, "type": "daily"}' not in cuerpo
        assert '{"notas.texto": con_texto}' in cuerpo
        assert '{"entreno_nota": con_texto}' in cuerpo

    def test_al_equipo_le_sigue_llegando_solo_lo_escrito_y_compartido(self):
        """La promesa que se le hace al cliente al escribir no cambia con esto."""
        codigo = _fuente("backend/routes/diary.py")
        i = codigo.find("if solo_compartidas:")
        j = codigo.find("else:", i)
        assert 0 < i < j
        assert '{"notas.texto": con_texto, "notas.compartida": True}' in codigo[i:j]

    def test_la_entrada_del_dia_lleva_lo_contestado(self):
        """Para poder pintar «Lun 24 · estrellas · Entreno si · Dieta si · 96 kg» sin
        volver a pedir los check-ins."""
        e = _entrada_del_dia({
            "dia": "2026-08-24", "created_at": "2026-08-24T21:00:00+00:00",
            "sensaciones": 4, "entreno_respuesta": "si", "entreno_estrellas": 3,
            "cardio": "no_tocaba", "weight": 96.0, "nutrition_followed": True,
        })
        assert e["dia_resumen"]["sensaciones"] == 4
        assert e["dia_resumen"]["entreno_respuesta"] == "si"
        assert e["dia_resumen"]["weight"] == 96.0

    def test_el_resumen_no_inventa_lo_que_no_contesto(self):
        """Los cierres de antes del 24-08 no tienen cardio ni sensaciones: el hueco no se
        rellena con un cero."""
        r = _resumen_del_dia({"dia": "2026-05-17", "energy": 3, "mood": 4})
        assert r == {"energy": 3, "mood": 4}


# ============ 6. LA LISTA DEL HISTORIAL ============

class TestElHistorialUnaLineaPorDia:
    def test_el_entreno_tiene_sus_tres_estados(self):
        """«entreno -> ✓ · le tocaba y no fue -> ✗ · tocaba descanso -> Descanso, sin
        simbolo, porque no es ni bueno ni malo.»"""
        pantalla = _fuente(PANTALLA)
        i = pantalla.find("const ENTRENO_LINEA = {")
        assert i > 0
        bloque = pantalla[i:i + 220]
        assert "si: 'Entreno ✓'" in bloque
        assert "no: 'Entreno ✗'" in bloque
        assert "descanso: 'Descanso'" in bloque

    def test_el_peso_solo_el_dia_que_lo_registro(self):
        pantalla = _fuente(PANTALLA)
        i = pantalla.find("const lineaDelDia = (c) => {")
        j = pantalla.find("};", i)
        assert 0 < i < j
        assert "if (c.weight != null) trozos.push(kilos(c.weight));" in pantalla[i:j]

    def test_el_detalle_dice_3_de_5_y_no_3_barra_5(self):
        pantalla = _fuente(PANTALLA)
        i = pantalla.find("const detalleDelDia = (c) => {")
        j = pantalla.find("\n};", i)
        assert 0 < i < j
        cuerpo = pantalla[i:j]
        assert "de 5`" in cuerpo
        assert "/5`" not in cuerpo, "«3 de 5», no «3/5»: se lee, no se descifra"

    def test_los_dias_seguidos_sin_cierre_van_en_una_sola_linea(self):
        pantalla = _fuente(PANTALLA)
        assert "Sin rellenar" in pantalla
        assert "if (ultima && ultima.tipo === 'hueco') ultima.dias.push(dia);" in pantalla

    def test_los_huecos_se_cuentan_desde_su_primer_cierre_y_no_desde_el_alta(self):
        """Hay clientes de 2023: contar desde el alta llena la pantalla de dos años de
        huecos. Y con tope, que la lista tiene que caber."""
        pantalla = _fuente(PANTALLA)
        assert "const DIAS_DE_HUECO_COMO_MUCHO = 30;" in pantalla
        assert "const desde = primero > tope ? primero : tope;" in pantalla

    def test_ninguna_linea_del_historial_lleva_hora(self):
        pantalla = _fuente(PANTALLA)
        for con_hora in ("toLocaleTimeString", "hour: '2-digit'", "minute: '2-digit'"):
            assert con_hora not in pantalla, "la hora del historial volvio"


# ============ 7. LOS SUPLEMENTOS, CON EL CANDADO DE SU PANTALLA ============

class TestElCandadoDeLosSuplementos:
    def test_el_cierre_pregunta_por_la_misma_puerta_que_la_pantalla(self):
        """Se decidia solo por tener protocolo escrito, sin mirar el plan: cuatro clientes
        activos con protocolo de su etapa anterior y plan sin suplementacion recibian la
        pregunta todas las noches."""
        codigo = _fuente("backend/routes/checkins.py")
        i = codigo.find("async def cierre_del_dia_hoy(")
        j = codigo.find("async def create_checkin(")
        assert 0 < i < j
        cuerpo = codigo[i:j]
        assert 'plan_grants_feature(profile.get("plan"), "suplementacion")' in cuerpo
        assert "suplementos = False" in cuerpo


# ============ 7b. UN DIA, UNA FILA (salio probando lo de arriba) ============

class TestNoSeDuplicaElCierre:
    """El caso: el cliente que vive en America. En España ya es dia 25 y el todavia esta
    en el 24, cosa que el bloque F permite a proposito. `_cierre_de_hoy` miraba SU cierre
    mas reciente y comparaba el dia, asi que en cuanto se colaba una fila del 25 -- otra
    pestaña, el reloj del servidor -- el cierre del 24 dejaba de encontrar al suyo y se
    insertaba otra vez. Dos filas del mismo dia cuentan doble en todo lo que lea la
    coleccion. Paso en dev justo al probar el rediseño.
    """

    def test_se_busca_por_el_dia_y_no_por_el_ultimo_que_haya(self):
        codigo = _fuente("backend/routes/checkins.py")
        i = codigo.find("async def _cierre_de_hoy(")
        j = codigo.find("@router.get(\"/checkins/hoy\")")
        assert 0 < i < j
        cuerpo = codigo[i:j]
        assert '{"client_id": client_id, "type": "daily", "dia": fecha}' in cuerpo
        # Y los de antes del bloque F, que no traen `dia`, siguen saliendo por created_at.
        assert '"dia": {"$in": [None, ""]}' in cuerpo
        assert "a_madrid" in cuerpo


# ============ 8. LOS EXTRAS DE LA NOCHE, A LA MISMA LISTA ============

class TestElSiDeLosExtras:
    def test_escribe_en_la_lista_del_dia_y_con_la_fecha_del_dia(self):
        """Punto 32: «se abre el mismo campo y va a la misma lista». Y la fecha es la del
        dia de la dieta que se estaba comiendo, no la de mañana."""
        pantalla = _fuente(PANTALLA)
        assert "const fechaDelDia = hoy?.fecha || todayKey();" in pantalla
        assert "api.post(`/diets/${fechaDelDia}/extras`," in pantalla
        assert "{ texto, origen: 'checkin' }" in pantalla

    def test_el_placeholder_es_el_del_campo_del_inicio(self):
        assert ("Con la cantidad aproximada a ojo si no lo pesas, pero ponlo todo."
                in _fuente(PANTALLA))

    def test_si_falla_apuntarlo_se_lo_decimos_en_cristiano(self):
        pantalla = _fuente(PANTALLA)
        assert "No hemos podido apuntarlo. Inténtalo en un momento." in pantalla
        assert "console.error('No se pudo apuntar el extra desde el cierre del día:'" in pantalla


# ============ 9. DE PUNTA A PUNTA, CONTRA EL BACKEND VIVO ============

def test_hoy_devuelve_la_lista_de_comidas_pendientes(api_disponible, cabeceras_cliente):
    r = _pedir("GET", "/checkins/hoy", headers=cabeceras_cliente)
    assert r.status_code == 200, r.text
    d = r.json()
    assert isinstance(d.get("comidas_pendientes"), list), "el aviso de arriba necesita la lista"
    for c in d["comidas_pendientes"]:
        assert c["etiqueta"][0].isupper(), "en la lista van con mayuscula"


def test_las_once_respuestas_entran_y_vuelven(api_disponible, cabeceras_cliente):
    fecha = _pedir("GET", "/checkins/hoy", headers=cabeceras_cliente).json()["fecha"]
    cuerpo = {
        "type": "daily", "fecha": fecha,
        "sensaciones": 4,
        "entreno_respuesta": "si", "entreno_estrellas": 3,
        "entreno_nota": "Empuje, y la ultima serie justita.",
        "cardio": "no_tocaba",
        "movimiento": "igual",
        "extras_respuesta": "no",
        "descanso": 3, "energy": 4, "hunger_anxiety": 2,
        "notas": {"texto": "Buen dia.", "compartida": False},
    }
    r = _pedir("POST", "/checkins", headers=cabeceras_cliente, json=cuerpo)
    assert r.status_code == 200, r.text

    guardado = _pedir("GET", "/checkins/hoy", headers=cabeceras_cliente).json()["checkin"]
    assert guardado["sensaciones"] == 4
    assert guardado["entreno_respuesta"] == "si" and guardado["entreno_estrellas"] == 3
    assert guardado["cardio"] == "no_tocaba"
    assert guardado["extras_respuesta"] == "no"

    # Y por el listado, que es de donde se pinta el historial.
    lista = _pedir("GET", "/checkins?type=daily&limit=5", headers=cabeceras_cliente).json()
    fila = next(c for c in lista if c.get("dia") == fecha)
    for campo in ("sensaciones", "entreno_respuesta", "entreno_estrellas", "cardio"):
        assert fila.get(campo) is not None, f"el historial se queda sin {campo}"


def test_el_dia_escrito_llega_al_diario_con_lo_contestado(api_disponible, cabeceras_cliente,
                                                          cabeceras_admin):
    """El Diario sigue siendo lo que ESCRIBE, y cada entrada viaja ya con `dia_resumen`:
    lo contestado ese dia, para que pintar la linea del punto 19 alli sea pintar y no
    volver a pedir los check-ins."""
    encendido = _pedir("PUT", "/admin/settings", headers=cabeceras_admin,
                       json={"pantallas": {"t5_diario": True}})
    assert encendido.status_code == 200, encendido.text

    fecha = _pedir("GET", "/checkins/hoy", headers=cabeceras_cliente).json()["fecha"]
    r = _pedir("POST", "/checkins", headers=cabeceras_cliente,
               json={"type": "daily", "fecha": fecha, "sensaciones": 5, "energy": 4,
                     "notas": {"texto": "Dia raro pero cerrado.", "compartida": False}})
    assert r.status_code == 200, r.text

    entradas = _pedir("GET", "/diary", headers=cabeceras_cliente).json()["entradas"]
    dia = next((e for e in entradas if e["tipo"] == "dia" and e["fecha"] == fecha), None)
    assert dia is not None, "lo que escribio tiene que estar en su diario"
    assert dia["dia_resumen"]["sensaciones"] == 5


# ============ 10. LO QUE SALIO AL REPASAR LO DE ARRIBA (24-08) ============

class TestLaLlaveDelCierreDelDia:
    """El caso: los 81 clientes de ELM, Mantenimiento, Calculadora JP y Basica. Su plan no
    vende reportes, pero el cierre del dia lo llevan los 21 planes (decision de Jesus, con
    llave propia `cierre_dia`). La puerta de la app ya iba por ahi (App.js), asi que
    entraban a la pantalla, contestaban las once y el Guardar les devolvia un 403: el
    cerrojo del servidor seguia pidiendo «reportes».
    """

    def test_el_cierre_diario_va_por_cierre_dia_y_el_reporte_por_reportes(self):
        codigo = _fuente("backend/routes/checkins.py")
        i = codigo.find("async def create_checkin(")
        j = codigo.find("cuerpo = data.model_dump(", i)
        assert 0 < i < j
        cuerpo = codigo[i:j]
        assert 'llave = "cierre_dia" if data.type == "daily" else "reportes"' in cuerpo
        assert 'plan_grants_feature(profile.get("plan"), "reportes")' not in cuerpo

    def test_los_planes_sin_reportes_si_pueden_cerrar_su_dia(self):
        from core.plan_access import plan_grants_feature
        from models.user import PLAN_TYPES

        sin_reportes = [c for c, p in PLAN_TYPES.items() if "reportes" not in p["features"]]
        assert sin_reportes, "si esto se queda vacio, el caso ya no existe y sobra el test"
        for code in sin_reportes:
            assert plan_grants_feature(code, "cierre_dia"), code


class TestUnaSolaCajaDeNotas:
    def test_no_hay_segunda_caja_colgando_del_si(self):
        """Punto 11: «UNA SOLA CAJA, con la pista de que poner», y la pista que da es
        «Cosas que quieras acordarte del entreno y de la dieta». Con dos, el que lleva
        rutina apunta lo mismo en dos sitios, y el rotulo de la segunda no era de Jesus."""
        pantalla = _fuente(PANTALLA)
        assert 'data-testid="cierre-entreno-nota"' not in pantalla
        assert 'placeholder="Qué entrenaste hoy (opcional)"' not in pantalla
        assert pantalla.count('placeholder="Cosas que quieras acordarte del entreno y de la dieta"') == 1

    def test_lo_que_ya_escribio_no_se_borra_al_reeditar(self):
        """El guardado sustituye la fila entera: sin esto, reabrir un cierre de antes se
        llevaba por delante su nota de entreno."""
        assert "entreno_nota: inicial?.entreno_nota || null," in _fuente(PANTALLA)


class TestElHistorialNoPierdeDiasCerrados:
    def test_el_cierre_de_hace_dos_meses_sigue_en_la_lista(self):
        """El tope de 30 dias es para los HUECOS, no para la lista. Recorriendo solo esos
        30 dias, al que cerro un dia hace dos meses y ninguno desde entonces le
        desaparecia su unico dia y se quedaba con un mes de «Sin rellenar» y nada mas."""
        pantalla = _fuente(PANTALLA)
        assert "for (const dia of [...porDia.keys()].filter(d => d < desde).sort().reverse())" in pantalla

    def test_un_tramo_largo_se_dice_por_sus_extremos(self):
        """30 nombres de dia seguidos son cuatro renglones que dicen lo mismo que uno."""
        pantalla = _fuente(PANTALLA)
        assert "const TRAMO_QUE_TODAVIA_SE_LEE = 5;" in pantalla
        assert "Sin rellenar" in pantalla


def test_ni_un_guion_largo_en_lo_que_se_toco():
    """Regla de la casa. Se coló uno en un comentario del historial."""
    for ruta in ("backend/models/common.py", "backend/routes/checkins.py",
                 "backend/routes/diary.py", PANTALLA):
        texto = _fuente(ruta)
        # Escritos con su codigo a proposito: la regla vale tambien para este fichero.
        assert chr(0x2014) not in texto and chr(0x2013) not in texto, ruta
