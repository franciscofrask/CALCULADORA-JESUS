# -*- coding: utf-8 -*-
"""EL INFORME DEL MES (documento del 1-09-2026), los diez bloques.

Los numeros son los de la maqueta, para que se pueda cotejar linea a linea:

    Empezaste el mes en 81,2 · Lo acabas en 78,4 · Cuando empezaste pesabas 84,0
    Semana 1 10 % · Semana 2 32 % · Semana 3 36 % · Semana 4 22 %
    Dietas completas 22 · Cuadradas 17 · Comiste de mas 6 · Entrenos 13 / perdidos 3
    Post: 30 g de whey y 40 g de crema de arroz, los 13 dias de entreno
    Cena: cambia casi cada dia, 17 combinaciones distintas
    Proteina: pollo 18 dias, claras 21, whey 13
    Extras: seis dias, y cinco cayeron en fin de semana

Lo que mas se prueba, otra vez, es lo que NO tiene que salir: el informe es lo unico que
el cliente lee del mes, y un dato inventado ahi vale por diez aciertos.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import informe_del_mes as idm  # noqa: E402


# ═════════════════════════════════════════════════════════════════════════════
# 1 · DONDE ESTAS
# ═════════════════════════════════════════════════════════════════════════════

def test_el_objetivo_se_dice_con_sus_palabras():
    r = idm.donde_estas("definicion", 8, 12)
    assert r["objetivo_label"] == "Bajar grasa"
    assert r["ciclo_label"] == "Semana 8 de 12"


def test_sin_ciclo_cerrado_solo_la_semana():
    assert idm.donde_estas("volumen", 8, None)["ciclo_label"] == "Semana 8"
    assert idm.donde_estas("volumen", 8, None)["objetivo_label"] == "Ganar músculo"


def test_un_objetivo_que_no_conocemos_no_se_inventa():
    assert idm.donde_estas("recomposicion", 3, 12)["objetivo_label"] is None


# ═════════════════════════════════════════════════════════════════════════════
# 2 · TU FEEDBACK
# ═════════════════════════════════════════════════════════════════════════════

def test_sin_feedback_el_hueco_lleva_el_dia_y_la_hora():
    r = idm.feedback_del_informe(None)
    assert r["pendiente"] is True
    assert "Antes del viernes a las 15:00" in r["aviso"]


def test_el_dia_prometido_no_esta_escrito_a_mano():
    r = idm.feedback_del_informe("", dia_prometido="sábado", hora_prometida="10:00")
    assert "Antes del sábado a las 10:00" in r["aviso"]


def test_con_feedback_va_firmado():
    r = idm.feedback_del_informe("  Has bajado 2,8 kg.  ", "Jesús Gallego", "5 de septiembre")
    assert r["pendiente"] is False
    assert r["texto"] == "Has bajado 2,8 kg."
    assert r["iniciales"] == "JG"
    assert r["fecha_label"] == "5 de septiembre"


# ═════════════════════════════════════════════════════════════════════════════
# 3 · TU PESO
# ═════════════════════════════════════════════════════════════════════════════

PESOS = [
    {"fecha": "2026-08-04", "valor": 81.2},
    {"fecha": "2026-08-11", "valor": 80.9},
    {"fecha": "2026-08-18", "valor": 80.0},
    {"fecha": "2026-08-25", "valor": 79.0},
    {"fecha": "2026-09-01", "valor": 78.4},
]


def test_el_peso_del_mes_con_los_numeros_de_la_maqueta():
    r = idm.peso_del_mes(PESOS, peso_al_empezar=84.0)
    assert r["empezaste_label"] == "81,2 kg"
    assert r["acabas_label"] == "78,4 kg"
    assert r["cambio_label"] == "−2,8 kg"
    assert r["al_empezar_label"] == "84 kg"
    assert r["desde_el_principio_label"] == "−5,6 kg"
    assert r["titulo_cambio"] == "−2,8 kg este mes"


def test_el_reparto_por_semana_suma_cien():
    filas = idm.peso_del_mes(PESOS)["por_semana"]
    assert [f["semana"] for f in filas] == [1, 2, 3, 4]
    assert sum(f["pct"] for f in filas) == 100


def test_una_semana_que_va_al_reves_sale_en_negativo():
    """Maquillarla con valores absolutos daria cuatro numeros que no suman lo que paso."""
    pesos = [{"fecha": "2026-08-04", "valor": 81.0},
             {"fecha": "2026-08-11", "valor": 81.5},   # esta subio
             {"fecha": "2026-08-18", "valor": 80.5},
             {"fecha": "2026-08-25", "valor": 80.0},
             {"fecha": "2026-09-01", "valor": 79.0}]
    filas = idm.peso_del_mes(pesos)["por_semana"]
    assert filas[0]["pct"] < 0
    assert sum(f["pct"] for f in filas) == 100


def test_sin_cambio_no_hay_reparto_que_hacer():
    pesos = [{"fecha": "2026-08-04", "valor": 80.0}, {"fecha": "2026-09-01", "valor": 80.0}]
    r = idm.peso_del_mes(pesos)
    assert r["por_semana"] == []
    assert r["titulo_cambio"] == "Igual que el mes pasado"


def test_sin_pesajes_no_hay_bloque():
    assert idm.peso_del_mes([])["hay"] is False


def test_sin_peso_de_partida_no_se_inventa_la_linea():
    r = idm.peso_del_mes(PESOS)
    assert r["al_empezar_label"] is None
    assert r["desde_el_principio_label"] is None


# ═════════════════════════════════════════════════════════════════════════════
# 4 · TUS MEDIDAS
# ═════════════════════════════════════════════════════════════════════════════

ETIQUETAS = [("cuello", "Cuello"), ("mesoesternal", "Mesoesternal"), ("cintura", "Cintura")]


def test_las_medidas_van_contra_el_mes_pasado_y_contra_la_primera():
    r = idm.medidas_del_informe({"cuello": 39, "mesoesternal": 111, "cintura": 88},
                                {"cuello": 40, "mesoesternal": 112, "cintura": 90},
                                {"cuello": 40, "mesoesternal": 108, "cintura": 96},
                                ETIQUETAS, objetivo="definicion")
    filas = {f["clave"]: f for f in r["filas"]}
    assert filas["cuello"]["mes"]["label"] == "−1"
    assert filas["cuello"]["primera"]["label"] == "−1"
    assert filas["mesoesternal"]["mes"]["label"] == "−1"
    assert filas["mesoesternal"]["primera"]["label"] == "+3"


def test_el_color_depende_del_objetivo():
    """Bajar cintura es bueno definiendo y malo en volumen. No se pinta igual."""
    def color(objetivo):
        r = idm.medidas_del_informe({"cintura": 88}, {"cintura": 90}, None,
                                    ETIQUETAS, objetivo=objetivo)
        return r["filas"][0]["mes"]["color"]
    assert color("definicion") == "verde"
    assert color("volumen") == "rojo"


def test_el_cero_no_es_ni_bueno_ni_malo():
    r = idm.medidas_del_informe({"cintura": 90}, {"cintura": 90}, None, ETIQUETAS)
    assert r["filas"][0]["mes"]["color"] == "gris"
    assert r["filas"][0]["mes"]["label"] == "0"


def test_sin_toma_anterior_la_columna_va_vacia_y_no_a_cero():
    r = idm.medidas_del_informe({"cintura": 90}, None, None, ETIQUETAS)
    assert r["filas"][0]["mes"] is None
    assert r["hay_mes"] is False


def test_sin_medidas_no_hay_bloque():
    assert idm.medidas_del_informe({}, {"cintura": 90}, None, ETIQUETAS)["hay"] is False


# ═════════════════════════════════════════════════════════════════════════════
# 5 · GRASA
# ═════════════════════════════════════════════════════════════════════════════

#: EL TEXTO CAMBIÓ EL 2-09 y estos dos tests fijaban el viejo. Decía «se mide al final de cada
#: ciclo, cada 12 semanas», que sonaba a obligación, y el punto 10.2 de «Todo lo que está
#: validado» lo deja escrito de otra forma: es OPCIONAL y lo que se recomienda es hacerlo uno
#: de cada 3 reportes. Se comprueban las dos cosas que no pueden faltar de esa frase.
def _dice_que_es_opcional(texto):
    return "opcional" in texto.lower() and "12 semanas" in texto


def test_la_grasa_dice_cuando_se_midio_y_cuando_toca():
    r = idm.grasa_del_informe(18.0, "4 de junio", semanas_desde=8)
    assert r["ultima"] == "La última medición: 18 %, el 4 de junio."
    assert r["cuando"] == "En 4 semanas"
    assert _dice_que_es_opcional(r["explicacion"]), r["explicacion"]


def test_si_ya_toca_lo_dice():
    assert idm.grasa_del_informe(18.0, "4 de junio", semanas_desde=13)["cuando"] == "Toca ahora"


def test_sin_medicion_se_explica_igual_para_que_no_parezca_un_hueco():
    r = idm.grasa_del_informe(None, None, None)
    assert r["hay"] is False
    assert _dice_que_es_opcional(r["explicacion"]), r["explicacion"]


# ═════════════════════════════════════════════════════════════════════════════
# 7 · LO QUE HAS HECHO
# ═════════════════════════════════════════════════════════════════════════════

DIETA = {"dias_periodo": 28, "dias_registrados": 22, "dias_cuadrados": 17}
ENTRENO = {"previstos": 16, "hechos": 13, "cardio": {"previstas": 12, "hechas": 7}}
CIERRES = {"dias_comio_de_mas": 6, "suplementacion": {"cumplidos": 21, "de": 28}}


def test_las_cuatro_filas_con_su_contrario_al_lado():
    filas = {f["clave"]: f for f in idm.lo_que_has_hecho(DIETA, ENTRENO, CIERRES)["filas"]}
    assert (filas["dietas"]["valor"], filas["dietas"]["valor2"]) == (22, 28)
    assert (filas["cuadradas"]["valor"], filas["cuadradas"]["valor2"]) == (17, 6)
    assert (filas["entrenos"]["valor"], filas["entrenos"]["valor2"]) == (13, 3)
    assert (filas["cardios"]["valor"], filas["cardios"]["valor2"]) == (7, 5)
    assert (filas["suplementacion"]["valor"], filas["suplementacion"]["valor2"]) == (21, 7)


def test_sin_rutina_no_hay_entrenos_perdidos_que_contar():
    sin = {"previstos": None, "hechos": 0, "cardio": {}}
    claves = [f["clave"] for f in idm.lo_que_has_hecho(DIETA, sin, CIERRES)["filas"]]
    assert "entrenos" not in claves and "cardios" not in claves
    assert "dietas" in claves


def test_sin_suplementacion_pautada_esa_fila_no_existe():
    claves = [f["clave"] for f in idm.lo_que_has_hecho(DIETA, ENTRENO, {})["filas"]]
    assert "suplementacion" not in claves


# ═════════════════════════════════════════════════════════════════════════════
# 8 · TU DIA TIPO
# ═════════════════════════════════════════════════════════════════════════════

def _comida(clave, fecha, items, momento=None, peri=False, nombre=None):
    return {"clave": clave, "fecha": fecha, "items": items, "momento": momento,
            "es_peri": peri, "nombre": nombre or clave}


def test_el_post_que_no_cambia_sale_con_sus_cantidades():
    dias = [_comida("Post", f"2026-08-{d:02d}",
                    [{"nombre": "Whey", "cantidad": 30, "unidad": "g"},
                     {"nombre": "Crema de arroz", "cantidad": 40, "unidad": "g"}],
                    peri=True)
            for d in range(1, 14)]
    fila = idm.dia_tipo(dias)["filas"][0]
    assert fila["varia"] is False
    assert fila["texto"] == "30 g de Whey y 40 g de Crema de arroz"
    assert fila["cuantos"] == "los 13 días de entreno"
    assert fila["momento"] == "Al terminar"


def test_la_cena_que_cambia_se_cuenta_por_combinaciones():
    dias = [_comida("C4", f"2026-08-{d:02d}",
                    [{"nombre": f"Cena {d}", "cantidad": 100, "unidad": "g"}], momento="cena")
            for d in range(1, 18)]
    fila = idm.dia_tipo(dias)["filas"][0]
    assert fila["varia"] is True
    assert fila["texto"] == "Cambia casi cada día"
    assert fila["cuantos"] == "17 combinaciones distintas"
    assert fila["momento"] == "Noche"


def test_la_combinacion_se_reconoce_aunque_cambien_los_gramos():
    """La calculadora reajusta cada dia: exigir que coincidan al gramo daria 28 combinaciones."""
    dias = [_comida("C3", f"2026-08-{d:02d}",
                    [{"nombre": "Yogur griego", "cantidad": 1, "unidad": "ud"},
                     {"nombre": "Nueces", "cantidad": 28 + d, "unidad": "g"}], momento="merienda")
            for d in range(1, 13)]
    fila = idm.dia_tipo(dias)["filas"][0]
    assert fila["varia"] is False
    assert fila["combinaciones_distintas"] == 1
    assert fila["texto"].startswith("1 Yogur griego y ")
    assert fila["cuantos"] == "12 de 12 días"
    assert fila["momento"] == "Tarde"


def test_las_comidas_salen_en_el_orden_del_dia():
    dias = ([_comida("C4", "2026-08-01", [{"nombre": "Cena", "cantidad": 1, "unidad": "ud"}], momento="cena")] * 3
            + [_comida("C1", "2026-08-01", [{"nombre": "Avena", "cantidad": 80, "unidad": "g"}], momento="desayuno")] * 3
            + [_comida("Post", "2026-08-01", [{"nombre": "Whey", "cantidad": 30, "unidad": "g"}], peri=True)] * 3)
    assert [f["clave"] for f in idm.dia_tipo(dias)["filas"]] == ["C1", "Post", "C4"]


def test_una_comida_vacia_no_cuenta_como_dia():
    dias = [_comida("C1", "2026-08-01", []), _comida("C1", "2026-08-02", []),
            _comida("C1", "2026-08-03", [{"nombre": "Avena", "cantidad": 80, "unidad": "g"}],
                    momento="desayuno")]
    filas = idm.dia_tipo(dias)["filas"]
    assert filas[0]["dias"] == 1


def test_sin_dietas_no_hay_dia_tipo():
    assert idm.dia_tipo([])["hay"] is False


# ═════════════════════════════════════════════════════════════════════════════
# 9 · PREFERENCIAS
# ═════════════════════════════════════════════════════════════════════════════

def _uso(nombre, fecha, P=0, H=0, G=0):
    return {"nombre": nombre, "fecha": fecha, "macros": {"P": P, "H": H, "G": G}}


def test_los_tres_de_cada_grupo_con_sus_dias():
    usos = ([_uso("Pollo", f"2026-08-{d:02d}", P=30) for d in range(1, 19)]
            + [_uso("Claras", f"2026-08-{d:02d}", P=11) for d in range(1, 22)]
            + [_uso("Whey", f"2026-08-{d:02d}", P=24) for d in range(1, 14)]
            + [_uso("Avena", f"2026-08-{d:02d}", H=60, P=13) for d in range(1, 22)]
            + [_uso("Aceite de oliva", f"2026-08-{d:02d}", G=100) for d in range(1, 17)])
    r = idm.preferencias_de_alimentos(usos)
    assert [x["nombre"] for x in r["proteina"]] == ["Claras", "Pollo", "Whey"]
    assert [x["dias"] for x in r["proteina"]] == [21, 18, 13]
    assert r["proteina"][0]["label"] == "21 días"
    assert [x["nombre"] for x in r["hidratos"]] == ["Avena"]
    assert [x["nombre"] for x in r["grasas"]] == ["Aceite de oliva"]


def test_el_grupo_se_decide_por_calorias_no_por_gramos():
    """Con 10 g de grasa (90 kcal) y 12 de hidratos (48), el alimento es una grasa."""
    r = idm.preferencias_de_alimentos([_uso("Nueces", "2026-08-01", H=12, G=10)])
    assert [x["nombre"] for x in r["grasas"]] == ["Nueces"]
    assert r["hidratos"] == []


def test_dos_veces_el_mismo_dia_es_un_dia():
    usos = [_uso("Pollo", "2026-08-01", P=30), _uso("Pollo", "2026-08-01", P=30),
            _uso("Pollo", "2026-08-02", P=30)]
    assert idm.preferencias_de_alimentos(usos)["proteina"][0]["dias"] == 2


def test_un_alimento_sin_macros_no_se_clasifica():
    r = idm.preferencias_de_alimentos([_uso("Agua", "2026-08-01")])
    assert r["hay"] is False


# ═════════════════════════════════════════════════════════════════════════════
# 10 · EXTRAS
# ═════════════════════════════════════════════════════════════════════════════

EXTRAS = [
    {"fecha": "2026-08-09", "texto": "Dos cañas y unas bravas"},   # domingo
    {"fecha": "2026-08-17", "texto": "Comida familiar"},           # lunes
    {"fecha": "2026-08-22", "texto": "Un cruasán"},                # sábado
    {"fecha": "2026-08-23", "texto": "Pizza"},                     # domingo
    {"fecha": "2026-08-30", "texto": "Helado"},                    # domingo
    {"fecha": "2026-08-31", "texto": "Vino y queso"},              # lunes
]


def test_los_extras_dicen_cuantos_cayeron_en_finde():
    r = idm.extras_registrados(EXTRAS)
    assert r["dias"] == 6
    assert r["en_finde"] == 4
    assert r["titulo"] == "Seis días, y cuatro cayeron en fin de semana. Lo que apuntaste:"
    assert r["lista"][0]["dia_label"] == "Dom 9"
    assert r["lista"][-1]["texto"] == "Vino y queso"


def test_si_todos_cayeron_en_finde_no_se_repite_el_numero():
    r = idm.extras_registrados([{"fecha": "2026-08-22", "texto": "Pizza"},
                                {"fecha": "2026-08-23", "texto": "Helado"}])
    assert r["titulo"] == "Dos días, y cayeron en fin de semana. Lo que apuntaste:"


def test_sin_extras_no_hay_bloque():
    assert idm.extras_registrados([])["hay"] is False
    assert idm.extras_registrados([{"fecha": "2026-08-01", "texto": "   "}])["hay"] is False
