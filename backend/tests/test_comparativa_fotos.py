# -*- coding: utf-8 -*-
"""La comparativa de fotos del informe (documento de Jesus del 05-08, punto 3.2).

Su tabla, que es lo que se comprueba aqui:

    Momento                                  Cuantas   Cuales, de izquierda a derecha
    Mes 1                                    1         la inicial, que es tambien la actual
    Mes 2                                    2         la del mes anterior (que es la inicial) · la actual
    Mes 3 y siguientes, sin cambio de fase   3         la inicial · la del mes anterior · la actual
    Despues de un cambio de fase             4         la inicial · la de inicio de fase · la del mes anterior · la actual

Y las dos reglas: la inicial nunca se mueve de la izquierda, y si dos etiquetas
apuntan a la misma foto se ensena una sola vez.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.informe_mensual import comparativa_de_fotos


def rep(rid, fecha, peso=80.0, fotos=("f1",)):
    return {"id": rid, "created_at": f"{fecha}T10:00:00+00:00", "weight": peso, "photos": list(fotos)}


class TestLaTablaDeJesus:
    def test_mes_1_una_sola_foto(self):
        """La inicial es tambien la actual: una foto, no la misma dos veces."""
        r1 = rep("r1", "2026-01-10")
        c = comparativa_de_fotos(reporte=r1, reporte_anterior=None, reporte_inicial=r1,
                                 reporte_inicio_fase=None)
        assert len(c) == 1
        assert set(c[0]["etiquetas"]) == {"inicial", "actual"}

    def test_mes_2_dos_fotos(self):
        """La del mes anterior es la inicial: se funden en una, y la actual aparte."""
        r1, r2 = rep("r1", "2026-01-10"), rep("r2", "2026-02-10")
        c = comparativa_de_fotos(reporte=r2, reporte_anterior=r1, reporte_inicial=r1,
                                 reporte_inicio_fase=None)
        assert len(c) == 2
        assert set(c[0]["etiquetas"]) == {"inicial", "mes_anterior"}
        assert c[1]["etiquetas"] == ["actual"]

    def test_mes_3_sin_cambio_de_fase_tres_fotos(self):
        r1, r2, r3 = rep("r1", "2026-01-10"), rep("r2", "2026-02-10"), rep("r3", "2026-03-10")
        c = comparativa_de_fotos(reporte=r3, reporte_anterior=r2, reporte_inicial=r1,
                                 reporte_inicio_fase=None)
        assert [x["etiquetas"] for x in c] == [["inicial"], ["mes_anterior"], ["actual"]]

    def test_despues_de_un_cambio_de_fase_cuatro_fotos(self):
        r1 = rep("r1", "2026-01-10")
        rf = rep("rf", "2026-03-10")     # el reporte con el que arranco la fase
        r4 = rep("r4", "2026-04-10")     # mes anterior
        r5 = rep("r5", "2026-05-10")     # actual
        c = comparativa_de_fotos(reporte=r5, reporte_anterior=r4, reporte_inicial=r1,
                                 reporte_inicio_fase=rf)
        assert len(c) == 4
        assert [x["etiquetas"][0] for x in c] == ["inicial", "inicio_fase", "mes_anterior", "actual"]

    def test_primer_mes_de_una_fase_nueva_no_repite_foto(self):
        """El inicio de fase ES el reporte actual: se ensena una vez con las dos etiquetas."""
        r1, r4, r5 = rep("r1", "2026-01-10"), rep("r4", "2026-04-10"), rep("r5", "2026-05-10")
        c = comparativa_de_fotos(reporte=r5, reporte_anterior=r4, reporte_inicial=r1,
                                 reporte_inicio_fase=r5)
        assert len(c) == 3
        assert set(c[-1]["etiquetas"]) == {"inicio_fase", "actual"}


class TestReglasDuras:
    def test_la_inicial_siempre_la_primera(self):
        r1, r4, r5, rf = rep("r1", "2026-01-10"), rep("r4", "2026-04-10"), rep("r5", "2026-05-10"), rep("rf", "2026-03-10")
        c = comparativa_de_fotos(reporte=r5, reporte_anterior=r4, reporte_inicial=r1, reporte_inicio_fase=rf)
        assert "inicial" in c[0]["etiquetas"]

    def test_nunca_mas_de_cuatro(self):
        r = [rep(f"r{i}", f"2026-0{i}-10") for i in range(1, 6)]
        c = comparativa_de_fotos(reporte=r[4], reporte_anterior=r[3], reporte_inicial=r[0], reporte_inicio_fase=r[2])
        assert len(c) <= 4

    def test_nunca_la_misma_dos_veces(self):
        r1, r2 = rep("r1", "2026-01-10"), rep("r2", "2026-02-10")
        c = comparativa_de_fotos(reporte=r2, reporte_anterior=r1, reporte_inicial=r1, reporte_inicio_fase=r1)
        ids = [x["fecha"] for x in c]
        assert len(ids) == len(set(ids))

    def test_un_reporte_sin_fotos_no_entra(self):
        r1 = rep("r1", "2026-01-10")
        sin = {"id": "r2", "created_at": "2026-02-10T10:00:00+00:00", "weight": 80, "photos": []}
        c = comparativa_de_fotos(reporte=rep("r3", "2026-03-10"), reporte_anterior=sin,
                                 reporte_inicial=r1, reporte_inicio_fase=None)
        assert [x["etiquetas"][0] for x in c] == ["inicial", "actual"]

    def test_cada_foto_lleva_su_fecha_peso_y_medidas(self):
        r1 = rep("r1", "2026-01-10", peso=95.5)
        r1["measurements"] = {"waist": 92}
        c = comparativa_de_fotos(reporte=r1, reporte_anterior=None, reporte_inicial=r1, reporte_inicio_fase=None)
        assert c[0]["fecha"] == "2026-01-10"
        assert c[0]["peso"] == 95.5
        assert c[0]["medidas"] == {"waist": 92}
