"""LA SEMANA DEL CICLO DEL INFORME SE CALCULA, NO SE LEE (3-09-2026).

El informe del mes le decía «Semana 1 de 12» a todo el mundo. Ese 1 no era la semana de
nadie: es el literal que escribe el alta en `client_profiles.week` para que la validación no
reviente (`routes/auth.py`, `routes/leads.py`, `core/stripe_billing.py`, y los cuatro
scripts de migración, todos con `"week": 1`), y desde entonces no lo mueve NADA. No hay cron,
no hay `$inc`, no hay pantalla que lo escriba. Medido el 3-09: 184 de 188 fichas de
producción en `week: 1` y las otras 4 sin el campo. Nadie llegaba nunca a la semana 2.

La semana de verdad ya se calculaba en `core/cycle` a partir de `cycle_start` -- es la que
enseñan Mi perfil, el panel del equipo, la renovación y la cadencia de reportes --, pero el
informe era el único sitio que se creía el campo muerto.

Funciones puras: se prueba sin base ni servidor. Lo que no cabe aquí (que la ruta llame a
`enrich_cycle`) se comprobó en pantalla: `_guia/_ver_mi_informe.js`.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.cycle import compute_cycle, enrich_cycle       # noqa: E402
from core.informe_del_mes import donde_estas             # noqa: E402

AHORA = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)

#: Una ficha como las de verdad: dada de alta hace diez semanas y con el `week` sin tocar.
def _ficha(dias_desde_el_alta: int, **extra):
    alta = (AHORA - timedelta(days=dias_desde_el_alta)).isoformat()
    return {"id": "c1", "plan": "nivel2", "goal": "definicion",
            "week": 1, "created_at": alta, **extra}


def test_el_campo_guardado_dice_1_y_la_semana_de_verdad_es_otra():
    ficha = _ficha(70)
    assert ficha["week"] == 1, "así es como está en la base"
    assert compute_cycle(ficha, AHORA)["week"] == 11


def test_enriquecida_la_ficha_el_informe_dice_la_semana_buena():
    ficha = enrich_cycle(_ficha(70))
    assert donde_estas(ficha["goal"], ficha["week"], 12)["ciclo_label"] == "Semana 11 de 12"


def test_sin_enriquecer_saldria_el_1_de_siempre():
    # El fallo, tal cual era. Si esto vuelve a pasar en la ruta, la pantalla vuelve a mentir.
    ficha = _ficha(70)
    assert donde_estas(ficha["goal"], ficha["week"], 12)["ciclo_label"] == "Semana 1 de 12"


def test_manda_cycle_start_por_encima_del_alta():
    # El que renueva tiene `cycle_start` y su ciclo arranca ahí, no el día que se dio de alta.
    ficha = _ficha(200, cycle_start=(AHORA - timedelta(days=21)).isoformat())
    assert compute_cycle(ficha, AHORA)["week"] == 4


def test_el_primer_dia_es_la_semana_1_de_verdad():
    assert compute_cycle(_ficha(0), AHORA)["week"] == 1
    assert compute_cycle(_ficha(6), AHORA)["week"] == 1
    assert compute_cycle(_ficha(7), AHORA)["week"] == 2


def test_al_pasarse_del_ciclo_se_da_la_vuelta():
    # Doce semanas y una: vuelve a la 1, pero es el ciclo 2. El informe solo enseña la
    # semana, y por eso hace falta que sea la del ciclo en curso y no una cuenta infinita.
    ciclo2 = compute_cycle(_ficha(7 * 12), AHORA)
    assert (ciclo2["week"], ciclo2["cycle_number"]) == (1, 2)
