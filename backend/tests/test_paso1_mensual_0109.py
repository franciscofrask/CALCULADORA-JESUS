# -*- coding: utf-8 -*-
"""EL PASO 1 DEL MENSUAL (documento «El reporte mensual», 1-09-2026).

Las tres piezas del paso 1 y los numeros exactos de la maqueta:

    LO QUE HAS HECHO EN LOS ULTIMOS 28 DIAS
    Dietas guardadas 22 de 28 · Dias que comiste de mas 6 · Entrenos 13 de 16
    Cardio 7 de 12 · Movimiento 16 igual · 5 mas · 7 menos · Suplementacion 21 de 28

    Y COMO TE HAS SENTIDO
    Descanso 2,9 · Energia 3,1 · Hambre / ansiedad 3,6

    Te dejaste 3 entrenos sin registrar.
    Y 4 dias de dieta.

Lo que mas se comprueba aqui no son los aciertos, sino las filas QUE NO TIENEN QUE SALIR.
El bloque es una lista de notas y una fila con denominador inventado es un suspenso por
algo que nunca se le pidio: eso ya paso con los entrenos (punto 41 del doc del 19-08).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import actividad_mensual as am  # noqa: E402


# ── Los datos de la maqueta, tal cual ────────────────────────────────────────
DIETA = {"dias_periodo": 28, "dias_registrados": 22}
ENTRENO = {"previstos": 16, "hechos": 13, "sin_registrar": ["a", "b", "c"],
           "cardio": {"previstas": 12, "hechas": 7}}
CIERRES = {"dias_comio_de_mas": 6,
           "movimiento": {"igual": 16, "mas": 5, "menos": 7},
           "suplementacion": {"cumplidos": 21, "de": 28},
           "sensaciones": {"descanso": [3, 3, 2.7], "energia": [3, 3.2, 3.1],
                           "hambre": [4, 3.5, 3.3]}}


def _valores(filas):
    return {f["clave"]: f["valor"] for f in filas}


# ═════════════════════════════════════════════════════════════════════════════
# LO QUE HAS HECHO
# ═════════════════════════════════════════════════════════════════════════════

def test_las_seis_filas_de_la_maqueta():
    filas = am.filas_de_actividad(DIETA, ENTRENO, CIERRES)
    assert [f["clave"] for f in filas] == [
        "dietas", "extras", "entrenos", "cardio", "movimiento", "suplementacion"]
    assert _valores(filas) == {
        "dietas": "22 de 28",
        "extras": "6",
        "entrenos": "13 de 16",
        "cardio": "7 de 12",
        "movimiento": "16 igual · 5 más · 7 menos",
        "suplementacion": "21 de 28",
    }
    assert [f["etiqueta"] for f in filas] == [
        "Dietas guardadas", "Días que comiste de más", "Entrenos", "Cardio",
        "Movimiento", "Suplementación"]


def test_los_dias_que_comio_de_mas_no_llevan_denominador():
    """Es un recuento, no un cumplimiento. «6 de 28» lo convertiria en una nota."""
    filas = _valores(am.filas_de_actividad(DIETA, ENTRENO, CIERRES))
    assert filas["extras"] == "6"
    assert "de" not in filas["extras"]


def test_sin_rutina_no_hay_fila_de_entrenos_ni_de_cardio():
    sin_rutina = {"previstos": None, "hechos": 0, "cardio": {"previstas": None, "hechas": 0}}
    claves = [f["clave"] for f in am.filas_de_actividad(DIETA, sin_rutina, CIERRES)]
    assert "entrenos" not in claves
    assert "cardio" not in claves
    # Y las que si se saben siguen saliendo.
    assert "dietas" in claves and "movimiento" in claves


def test_cardio_sin_sesiones_pautadas_no_sale_aunque_haya_entrenos():
    """El denominador del cardio son los dias que su rutina lo marca. Sin eso, nada."""
    entreno = dict(ENTRENO, cardio={"previstas": None, "hechas": 4})
    claves = [f["clave"] for f in am.filas_de_actividad(DIETA, entreno, CIERRES)]
    assert "entrenos" in claves
    assert "cardio" not in claves


def test_el_movimiento_se_calla_los_ceros():
    cierres = dict(CIERRES, movimiento={"igual": 16, "mas": 0, "menos": 7})
    assert _valores(am.filas_de_actividad(DIETA, ENTRENO, cierres))["movimiento"] \
        == "16 igual · 7 menos"


def test_sin_ningun_movimiento_marcado_no_hay_fila():
    cierres = dict(CIERRES, movimiento={"igual": 0, "mas": 0, "menos": 0})
    claves = [f["clave"] for f in am.filas_de_actividad(DIETA, ENTRENO, cierres)]
    assert "movimiento" not in claves


def test_sin_suplementacion_en_el_plan_no_hay_fila():
    """Al que no lleva suplementos, «0 de 28» no significa nada."""
    cierres = dict(CIERRES, suplementacion={})
    claves = [f["clave"] for f in am.filas_de_actividad(DIETA, ENTRENO, cierres)]
    assert "suplementacion" not in claves


def test_sin_datos_no_revienta_y_devuelve_lista_vacia():
    assert am.filas_de_actividad(None, None, None) == []


def test_los_dos_rotulos_del_bloque():
    assert am.titulo_de_actividad(28, False) == "LO QUE HAS HECHO EN LOS ÚLTIMOS 28 DÍAS"
    assert am.titulo_de_actividad(120, True) == "LO QUE HAS HECHO EN 120 DÍAS"


# ═════════════════════════════════════════════════════════════════════════════
# Y COMO TE HAS SENTIDO
# ═════════════════════════════════════════════════════════════════════════════

def test_las_tres_sensaciones_con_su_media():
    filas = am.sensaciones_del_periodo(CIERRES)
    assert [f["clave"] for f in filas] == ["descanso", "energia", "hambre"]
    assert [f["etiqueta"] for f in filas] == ["Descanso", "Energía", "Hambre / ansiedad"]
    assert [f["media_label"] for f in filas] == ["2,9", "3,1", "3,6"]


def test_la_media_es_de_los_dias_que_contesto_no_del_mes():
    """Dos noches marcadas y veintiseis en blanco no se dividen entre 28."""
    filas = am.sensaciones_del_periodo({"sensaciones": {"descanso": [4, 2]}})
    assert filas[0]["media"] == 3.0
    assert filas[0]["dias"] == 2


def test_una_sensacion_sin_datos_no_sale():
    filas = am.sensaciones_del_periodo({"sensaciones": {"descanso": [3], "energia": [],
                                                        "hambre": []}})
    assert [f["clave"] for f in filas] == ["descanso"]


def test_la_serie_viaja_para_pintar_la_linea():
    filas = am.sensaciones_del_periodo({"sensaciones": {"descanso": [1, 5, 3]}})
    assert filas[0]["serie"] == [1, 5, 3]


def test_el_pie_de_las_sensaciones_cambia_con_el_periodo():
    assert am.pie_de_las_sensaciones(False, 28) == "Solo de estos 28 días. Lo de antes ya está cerrado."
    assert "120" in am.pie_de_las_sensaciones(True, 120)


# ═════════════════════════════════════════════════════════════════════════════
# LOS HUECOS
# ═════════════════════════════════════════════════════════════════════════════

def test_los_dos_huecos_de_la_maqueta():
    huecos = am.huecos_del_paso1(3, 4)
    assert [h["tipo"] for h in huecos] == ["entreno", "dieta"]
    assert huecos[0]["pregunta"] == "Te dejaste 3 entrenos sin registrar."
    assert huecos[1]["pregunta"] == "Y 4 días de dieta."
    assert [o["label"] for o in huecos[0]["opciones"]] == \
        ["No entrené", "Sí entrené, pero no lo marqué"]
    assert [o["label"] for o in huecos[1]["opciones"]] == \
        ["No la cumplí", "Sí, pero no la guardé"]


def test_el_hueco_de_dieta_solo_no_empieza_por_y():
    """«Y 4 dias de dieta» sin nada delante no es una frase."""
    huecos = am.huecos_del_paso1(0, 4)
    assert len(huecos) == 1
    assert huecos[0]["pregunta"] == "Te dejaste 4 días de dieta sin guardar."
    assert not huecos[0]["pregunta"].startswith("Y ")


def test_singulares():
    huecos = am.huecos_del_paso1(1, 1)
    assert huecos[0]["pregunta"] == "Te dejaste 1 entreno sin registrar."
    assert huecos[1]["pregunta"] == "Y 1 día de dieta."


def test_al_que_lo_registro_todo_no_se_le_pregunta_nada():
    assert am.huecos_del_paso1(0, 0) == []


def test_los_valores_de_respuesta_son_los_de_siempre():
    """Los mismos que entiende el servidor en `core/confirmacion_huecos.py`."""
    from core import confirmacion_huecos as ch
    huecos = am.huecos_del_paso1(2, 2)
    for h in huecos:
        assert [o["value"] for o in h["opciones"]] == [ch.NO_LO_HICE, ch.SI_PERO_NO_APUNTE]


# ═════════════════════════════════════════════════════════════════════════════
# LOS CIERRES, CONTADOS
# ═════════════════════════════════════════════════════════════════════════════

def _cierre(**kw):
    return kw


def test_cuenta_extras_movimiento_suplementos_y_sensaciones():
    cierres = [
        _cierre(extras_respuesta="si", movimiento="igual", suplementos={"respuesta": "si"},
                descanso=3, energy=4, hunger_anxiety=2),
        _cierre(extras_respuesta="no", movimiento="mas", suplementos={"respuesta": "si"},
                descanso=1, energy=2, hunger_anxiety=4),
        _cierre(extras_respuesta="si", movimiento="menos", suplementos={"respuesta": "no"}),
    ]
    r = am.cierres_del_periodo(cierres, 28, tiene_suplementacion=True)
    assert r["dias_comio_de_mas"] == 2
    assert r["movimiento"] == {"igual": 1, "mas": 1, "menos": 1}
    assert r["suplementacion"] == {"cumplidos": 2, "de": 28}
    assert r["sensaciones"]["descanso"] == [3.0, 1.0]
    assert r["sensaciones"]["hambre"] == [2.0, 4.0]


def test_no_todos_no_cuenta_como_suplementacion_tomada():
    """Medio protocolo no es la pauta. Si Jesus lo quiere al reves, es una linea."""
    cierres = [_cierre(suplementos={"respuesta": "no_todos"}),
               _cierre(suplementos={"respuesta": "si"})]
    r = am.cierres_del_periodo(cierres, 28, tiene_suplementacion=True)
    assert r["suplementacion"]["cumplidos"] == 1


def test_el_denominador_de_suplementacion_son_los_dias_del_periodo():
    """Un dia que no cerro es un dia que no consta que la tomara."""
    r = am.cierres_del_periodo([_cierre(suplementos={"respuesta": "si"})], 28,
                               tiene_suplementacion=True)
    assert r["suplementacion"] == {"cumplidos": 1, "de": 28}


def test_sin_suplementacion_en_el_plan_el_bloque_va_vacio():
    r = am.cierres_del_periodo([_cierre(suplementos={"respuesta": "si"})], 28,
                               tiene_suplementacion=False)
    assert r["suplementacion"] == {}


def test_si_no_contesto_ni_una_noche_no_se_le_escribe_un_cero():
    """«Suplementacion 0 de 28» al que no lo dijo nunca es un cero pelado, no un dato.

    Visto en la cuenta de pruebas contra el servidor: nueve dietas guardadas, tres cierres
    y ni una respuesta de suplementos, y la fila salia «0 de 28».
    """
    r = am.cierres_del_periodo([_cierre(movimiento="igual"), _cierre(descanso=3)], 28,
                               tiene_suplementacion=True)
    assert r["suplementacion"] == {}
    assert "suplementacion" not in [f["clave"] for f in am.filas_de_actividad(DIETA, ENTRENO, r)]


def test_con_una_sola_respuesta_ya_hay_fila():
    r = am.cierres_del_periodo([_cierre(suplementos={"respuesta": "no"})], 28,
                               tiene_suplementacion=True)
    assert r["suplementacion"] == {"cumplidos": 0, "de": 28}


def test_un_cierre_a_medias_no_rompe_nada():
    r = am.cierres_del_periodo([_cierre(), _cierre(movimiento=None, suplementos=None)], 28,
                               tiene_suplementacion=True)
    assert r["dias_comio_de_mas"] == 0
    assert r["movimiento"] == {"igual": 0, "mas": 0, "menos": 0}
    assert r["sensaciones"]["descanso"] == []


def test_sin_cierres_no_hay_sensaciones_que_pintar():
    r = am.cierres_del_periodo([], 28, tiene_suplementacion=True)
    assert am.sensaciones_del_periodo(r) == []


# ─────────────────────────────────────────────────────────────────────────────
# LA PREGUNTA 5: LOS EJERCICIOS QUE LE MOLESTAN (doc 1-09, aplicada el 3-09)
# ─────────────────────────────────────────────────────────────────────────────
#
# Su documento colapsa el bloque de lesiones -- zona, «como esta este mes» y ejercicios
# vetados -- en UNA pregunta con etiquetas. Lo que se guarda es la lista, y se guarda en
# `injuries`, que es por donde agrupa el generador de rutinas.

def test_los_ejercicios_que_le_molestan_salen_de_injuries():
    """«Estos son los que me diste»: lo que lee el generador de rutinas."""
    from core.datos_reporte import ejercicios_que_le_molestan
    perfil = {"injuries": ["Press militar", "Sentadilla profunda"]}
    assert ejercicios_que_le_molestan(perfil) == ["Press militar", "Sentadilla profunda"]


def test_y_se_le_suma_lo_que_dejo_dentro_de_sus_lesiones():
    """LA PRIMERA VEZ NO PUEDE SALIRLE EN BLANCO. Quien ya contesto el bloque viejo tiene
    sus ejercicios dentro de `lesiones[].ejercicios_vetados`, que el generador no mira: se
    suman aqui para que la pregunta nueva salga con todo lo que ya conto."""
    from core.datos_reporte import ejercicios_que_le_molestan
    perfil = {
        "injuries": ["Press militar"],
        "lesiones": [{"zona": "Hombro", "estado_mes": "igual",
                      "ejercicios_vetados": ["Fondos", "Press militar"]}],
    }
    # Sin repetir el que ya estaba, y en el orden en que se leen.
    assert ejercicios_que_le_molestan(perfil) == ["Press militar", "Fondos"]


def test_una_lesion_superada_no_arrastra_sus_ejercicios():
    """Se pregunto una vez y se cerro: sus vetados no vuelven a la lista."""
    from core.datos_reporte import ejercicios_que_le_molestan
    perfil = {"lesiones": [{"zona": "Rodilla", "estado_mes": "superada",
                            "ejercicios_vetados": ["Sentadilla profunda"]}]}
    assert ejercicios_que_le_molestan(perfil) == []


def test_sin_nada_apuntado_la_lista_sale_vacia_y_no_revienta():
    from core.datos_reporte import ejercicios_que_le_molestan
    assert ejercicios_que_le_molestan({}) == []
    assert ejercicios_que_le_molestan({"injuries": None, "lesiones": None}) == []


def test_el_modelo_acepta_la_lista_de_la_pregunta_5():
    from models.common import ReportCreate
    r = ReportCreate(tipo="mensual", weight=80.0,
                     ejercicios_molestos=["Press militar", "Fondos"])
    assert r.ejercicios_molestos == ["Press militar", "Fondos"]
    # Y sigue aceptando el bloque viejo: los reportes ya mandados se leen con el.
    assert ReportCreate(tipo="mensual", weight=80.0).ejercicios_molestos is None
