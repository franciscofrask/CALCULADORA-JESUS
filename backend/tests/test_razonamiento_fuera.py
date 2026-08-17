"""El asistente no le enseña al cliente lo que se dice a sí mismo.

17-08-2026, en la pantalla de Francisco, encabezando la respuesta del asistente:

    «Need to add 30g whey in Post, user generic; present options of whey isolate and say
    que elija cuál para poner 30g, sin editar hasta elija. También informar de Comida 2
    cómo va. One question max.»

El filtro que ya existía pedía cuatro palabras de una lista inglesa en el mismo párrafo y
ese texto solo llevaba una, así que pasó entero. Lo que lo delata no es cuánto inglés
tiene: es que se habla de «user» en tercera persona, se manda tareas y se pone límites de
estilo. Ver `_sin_razonamiento` en `agent_loop.py`.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_loop import _sin_razonamiento  # noqa: E402

EL_DE_FRANCISCO = (
    "Need to add 30g whey in Post, user generic; present options of whey isolate and say "
    "que elija cuál para poner 30g, sin editar hasta elija. También informar de Comida 2 "
    "cómo va. One question max.\n\n"
    "He dejado ya en la Comida 2: 200 g de claras de huevo pasteurizadas y 50 g de copos "
    "de avena; con eso ahí te siguen faltando unos 25,5 g de proteína."
)


def test_el_plan_que_se_escribe_a_si_mismo_no_sale():
    limpio = _sin_razonamiento(EL_DE_FRANCISCO)
    assert limpio.startswith("He dejado ya en la Comida 2")
    assert "user generic" not in limpio
    assert "One question max" not in limpio


def test_tambien_cuando_se_lo_dice_en_castellano():
    texto = ("Hay que informar de que la Comida 2 se pasa y también informar del intra. "
             "Una sola pregunta.\n\nLa Comida 2 se pasa 8 g de hidratos.")
    assert _sin_razonamiento(texto) == "La Comida 2 se pasa 8 g de hidratos."


def test_una_respuesta_normal_no_se_toca():
    """Los falsos positivos serían peores: aquí hay una marca inglesa y un «máximo»."""
    intactos = [
        "Te he puesto 40 g de Aislado de suero - Whey Isolate (FullGas) en el Post-entreno.\n\n"
        "Así te queda clavado al máximo de proteína que toca.",
        "Listo, he vaciado la Comida 2 y el Post-entreno.",
        "Para el intra te recomiendo MAP con hidratos de asimilación rápida.",
        "En la Comida 1 tienes Choco Gotas de chocolate negro (Hacendado) y Whey Isolate.",
    ]
    for texto in intactos:
        assert _sin_razonamiento(texto) == texto, texto
