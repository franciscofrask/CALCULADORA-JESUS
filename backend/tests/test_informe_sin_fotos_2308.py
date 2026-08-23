"""El informe del mes sale SIEMPRE, con lo que haya (punto 41 del doc del 23-08).

Hasta ese doc, `montar_informe` devolvía `generado: False` sin fotos, y como el equipo
mete los reportes de los Premium (que mandan por WhatsApp), los Premium no tenían
informe nunca. La regla nueva: el informe se monta con peso, ciclo, cumplimiento y
macros, y la foto lo COMPLETA (el apartado de fotos dice que faltan).

Función pura: se prueba sin base ni servidor.
"""
from core.informe_mensual import montar_informe

PERFIL = {"id": "c1", "week": 6, "plan": "nivel2", "goal": "definicion",
          "body_fat": 18.0, "weight": 82.0, "training_days": 4,
          "macros_training": {"protein": 180, "carbs": 200, "fat": 55}}

REPORTE = {"id": "r1", "client_id": "c1", "weight": 81.2, "photos": [],
           "created_at": "2026-08-20T10:00:00+00:00"}

ANTERIOR = {"id": "r0", "client_id": "c1", "weight": 82.5, "photos": [],
            "created_at": "2026-07-20T10:00:00+00:00"}


def _montar(reporte):
    return montar_informe(
        perfil=PERFIL, reporte=reporte, reporte_anterior=ANTERIOR,
        fotos_dia_cero=[], semanas_ciclo=12,
        dias_dieta=20, dias_entreno=14, dias_periodo=28,
        macros_comidos={"P": 175, "H": 190, "G": 60},
        macros_nuevos=None, explicacion_equipo=None, la_escribe_el_equipo=False)


def test_41_sin_fotos_el_informe_sale_igual():
    informe = _montar(REPORTE)
    assert informe["generado"] is True, "sin fotos el informe volvía a esconderse"
    assert informe["fotos"]["faltan"] is True
    assert informe["fotos"]["ahora"] == []
    # Los apartados de verdad están, que es lo que pide el doc: peso, ciclo, cumplimiento.
    assert informe["peso"] and informe["ciclo"]["semana"] == 6
    assert informe["cumplimiento"]["dieta"]["dias"] == 20


def test_41_con_fotos_no_cambia_nada():
    informe = _montar({**REPORTE, "photos": ["data:image/webp;base64,AAA"]})
    assert informe["generado"] is True
    assert informe["fotos"]["faltan"] is False
    assert informe["fotos"]["ahora"] == ["data:image/webp;base64,AAA"]
