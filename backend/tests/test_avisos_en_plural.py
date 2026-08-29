"""
Los avisos que escribe la máquina sola hablan en PLURAL (punto 57 del 23-08, recordado por
el 52 del 24-08).

Jesús: «"Con tus datos puedo mirarlo" en primera persona. Se topó el número y se pasó todo
a plural, pero lo que ya estaba escrito no se tocó».

La razón no es de estilo. Los avisos de `core/avisos_cliente.py` los genera una pasada
automática: cuando uno dice «puedo mirarlo», NADIE ha mirado nada, es el servidor
prometiendo en nombre de una persona que ni se ha enterado.

Y LA REGLA NO ES «NUNCA PRIMERA PERSONA». Los de `routes/notifications.py` («Te he cambiado
la suplementación», «Con mi feedback y tus macros nuevos») salen cuando una persona ACABA
DE HACER esa cosa, y ahí la primera persona es la verdad. Este candado vigila solo los
automáticos, que es donde estaba el fallo; poner el candado en los otros sería quitarle la
voz al entrenador en los recados que sí son suyos.

Es una prueba de TEXTO, sin base ni servidor: lee el fichero y mira lo que hay escrito.
"""
import os
import re

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUTOMATICOS = os.path.join(RAIZ, "core", "avisos_cliente.py")

# Las formas de primera persona del singular que se le colarían a un texto de aviso. No es
# un detector de español: es la lista corta de lo que aparece en frases de este tipo.
PRIMERA_PERSONA = re.compile(
    r"\b(puedo|miro|te he |te lo miro|he hecho|hice|mi feedback|conmigo|te cuento|"
    r"te ajusto|te pongo|te subo|te mando|te dejo|te aviso yo)\b", re.IGNORECASE)

# Lo que va entre comillas detrás de "titulo": o "cuerpo": -- o sea, lo que LEE el cliente.
TEXTO_DE_AVISO = re.compile(r'"(?:titulo|cuerpo)":\s*(?:f)?"([^"]{3,200})"')


def _textos_de(fichero):
    with open(fichero, encoding="utf-8") as f:
        return TEXTO_DE_AVISO.findall(f.read())


def test_hay_textos_que_mirar():
    """Si el fichero cambia de forma y el buscador deja de encontrar nada, esta prueba
    pasaría por no llegar a mirar. Eso es peor que no tenerla."""
    assert len(_textos_de(AUTOMATICOS)) >= 10


@pytest.mark.parametrize("texto", _textos_de(AUTOMATICOS))
def test_ningun_aviso_automatico_habla_en_primera_persona(texto):
    encontrado = PRIMERA_PERSONA.search(texto)
    assert not encontrado, (
        f"«{texto}» habla en primera persona ({encontrado.group(0)!r}), y este aviso lo "
        f"escribe la máquina sola: no hay nadie detrás que lo haya hecho. "
        f"Ver la regla 4 de la cabecera de core/avisos_cliente.py.")
