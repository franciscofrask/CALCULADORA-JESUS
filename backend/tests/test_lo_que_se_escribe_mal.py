"""UN DATO IMPOSIBLE SE DICE EN SU PANTALLA, NO AL FINAL (18-08).

Francisco, probando el cuestionario: escribió 80 en la altura, contestó veinte pantallas más
y al pulsar «Calcular mis macros» se encontró con «Revisa el campo height: no hemos podido
guardarlo así». Dos cosas mal a la vez:

  - El aviso llegaba AL FINAL, y no decía a cuál de las veinte pantallas volver.
  - Y llamaba al dato por su nombre en la base («height»), que no es como se llama en la
    pantalla donde lo escribió («tu altura»).

Lo que se comprueba aquí es el lado del servidor -- que los rangos existen y que rechaza lo
imposible -- y que los nombres que traduce la pantalla son los mismos campos que valida el
modelo. Que el aviso salga en su pantalla es cosa del navegador y se comprobó ahí.
"""
import json
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]


def test_el_perfil_no_acepta_una_altura_imposible():
    from pydantic import ValidationError

    from models.user import ClientProfileUpdate

    for imposible in (80, 15, 400):
        with pytest.raises(ValidationError):
            ClientProfileUpdate(height=imposible)
    assert ClientProfileUpdate(height=178).height == 178


def test_el_alta_tampoco():
    from pydantic import ValidationError

    from models.user import QuestionnaireSubmit

    base = {"goal": "definicion", "weight": 84.0, "body_fat": 20.0}
    with pytest.raises(ValidationError):
        QuestionnaireSubmit(**base, height=80)
    assert QuestionnaireSubmit(**base, height=178).height == 178


def test_la_pantalla_avisa_de_los_mismos_campos_que_valida_el_servidor():
    """Si alguien añade un rango en el modelo y no aquí, el cliente vuelve a estrellarse al
    final. Esta prueba es la que ata las dos listas."""
    pagina = (RAIZ / "frontend/src/pages/QuestionnairePage.jsx").read_text(encoding="utf-8")
    i = pagina.find("const RANGOS = {")
    assert i > 0, "el cuestionario ya no avisa de los rangos en la propia pantalla"
    bloque = pagina[i:pagina.find("};", i)]
    for campo in ("height", "weight", "peso_maximo", "peso_minimo", "peso_mejor_momento"):
        assert f"{campo}:" in bloque, f"«{campo}» no avisa en su pantalla"

    # Y el texto del error, con el nombre que el cliente reconoce.
    mensajes = (RAIZ / "frontend/src/lib/mensajeDeError.js").read_text(encoding="utf-8")
    assert "'tu altura'" in mensajes and "'tu peso'" in mensajes, (
        "el error sigue llamando a los datos por su nombre en la base")
    assert "«${campo}»: no hemos podido" not in mensajes.split("COMO_SE_LLAMA")[0], (
        "el mensaje genérico con el nombre crudo ya no puede ser el primero")
