"""Ponerles rutina a varios a la vez. Punto 6 del documento del 17-08.

«164 clientes tienen la rutina incluida en su plan y ninguno la tiene puesta (...). Está
arreglado cuando el contador de "sin rutina" empieza a bajar y existe una forma de asignar
a más de uno a la vez.»

Lo que se comprueba aquí es el agrupamiento y, sobre todo, EL FRENO: a quien no tiene datos
no se le genera nada. Medido en producción el 17-08 sobre los 163 clientes con rutina en el
plan y sin rutina puesta: 91 sin objetivo, 159 sin días de entreno, 0 con los datos
completos. Una herramienta que les pusiera a los 163 la misma rutina «de 4 días sin
objetivo» dejaría el contador a cero y el problema intacto.

Sin Mongo y sin OpenAI.
"""
import os
import sys

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)

from routes.routines import (  # noqa: E402
    _clave_de_grupo, _como_se_llama_el_grupo, _dias_de_entreno, _id_de_grupo, _que_le_falta,
)


def test_los_dias_se_leen_de_los_dos_campos():
    """Está guardado como número y como lista de días de la semana."""
    assert _dias_de_entreno({"training_days": 4}) == 4
    assert _dias_de_entreno({"training_days": "3"}) == 3
    assert _dias_de_entreno({"training_weekdays": ["lunes", "miércoles", "viernes"]}) == 3
    assert _dias_de_entreno({"training_days": []}) is None


def test_sin_dias_no_se_inventa_un_cuatro():
    """A quien entrena dos días, una rutina de cuatro no le sirve: mejor no dársela."""
    assert _dias_de_entreno({}) is None
    assert "días de entreno" in _que_le_falta({"goal": "definicion"})


def test_sin_objetivo_tampoco():
    assert "objetivo" in _que_le_falta({"training_days": 4})
    assert _que_le_falta({"goal": "  ", "training_days": 4}) == ["objetivo"]


def test_con_objetivo_y_dias_ya_se_le_puede():
    assert _que_le_falta({"goal": "definicion", "training_days": 4}) == []


def test_el_nivel_se_llama_training_experience():
    """El nombre del campo, que es donde estaba el fallo.

    Buscando `experience` salían 0 de 163 en producción, y no era que nadie lo tuviera.
    """
    clave = _clave_de_grupo({"goal": "volumen", "training_days": 4,
                             "training_experience": "Intermedio"})
    assert clave["nivel"] == "intermedio"


def test_dos_clientes_iguales_comparten_grupo_y_dos_distintos_no():
    a = {"goal": "definicion", "training_days": 4, "training_experience": "novato",
         "equipment": ["gym"]}
    b = dict(a)
    c = dict(a, training_days=3)
    assert _id_de_grupo(_clave_de_grupo(a)) == _id_de_grupo(_clave_de_grupo(b))
    assert _id_de_grupo(_clave_de_grupo(a)) != _id_de_grupo(_clave_de_grupo(c))


def test_una_lesion_te_saca_del_grupo():
    """Una rutina que ignora una lesión no vale para esa persona."""
    sano = {"goal": "volumen", "training_days": 4}
    tocado = dict(sano, injuries=["hombro"])
    assert _id_de_grupo(_clave_de_grupo(sano)) != _id_de_grupo(_clave_de_grupo(tocado))


def test_el_nombre_del_grupo_se_lee():
    """Con nueve materiales puestos, la fila ocupaba dos líneas de claves del formulario."""
    nombre = _como_se_llama_el_grupo(_clave_de_grupo({
        "goal": "volumen", "training_days": 5, "training_experience": "avanzado",
        "equipment": ["barra_olimpica", "bandas_elasticas", "pull_up_bar", "kettlebell",
                      "mancuernas", "maquinas"],
    }))
    assert "_" not in nombre, nombre
    assert "cosas más" in nombre
    assert nombre.startswith("volumen · 5 días · avanzado")
