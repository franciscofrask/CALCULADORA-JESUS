"""
El 500 al abrir un adjunto del chat mandado desde un Mac (28-08-2026).

Francisco: «este error solo aparece cuando se envía desde una mac», y desde el iPhone sí
se cargaban.

No era el Mac: era el NOMBRE. macOS bautiza sus capturas de pantalla con un ESPACIO FINO
DE NO SEPARACIÓN (U+202F) delante del AM/PM -- «Screenshot 2026-08-28 at 6.17.43 PM.jpg»
-- y las cabeceras HTTP se escriben en latin-1, donde ese carácter no existe. Al montar el
`Content-Disposition` saltaba un UnicodeEncodeError y la respuesta era un 500, con la
imagen perfectamente guardada. Diez de los catorce adjuntos de producción estaban así.

Desde el iPhone iba porque sus fotos se llaman «IMG_4821.jpg», todo ASCII; y una foto
normal arrastrada desde un Mac también iba. Viaja el nombre, no el aparato.

Aquí se prueba la función que arma la cabecera (`core.fotos.cabecera_nombre`), que es la
que usan las CUATRO puertas que sirven un fichero con nombre puesto por una persona: el
adjunto del chat, la foto del check-in, la del cuestionario y el PDF de la rutina.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.fotos import cabecera_nombre  # noqa: E402

# El nombre EXACTO que llegó de producción, con su U+202F.
MAC = "Screenshot 2026-08-28 at 6.17.43 PM.jpg"


def _se_puede_mandar(cabecera):
    """Una cabecera HTTP se escribe en latin-1: si no cabe, el servidor devuelve 500."""
    cabecera.encode("latin-1")
    return True


def test_el_nombre_de_la_captura_de_mac_ya_no_tumba_la_respuesta():
    assert _se_puede_mandar(cabecera_nombre(MAC, "imagen"))


def test_y_el_nombre_de_verdad_sigue_viajando_entero():
    """El de respaldo va en ASCII, pero el bueno viaja en `filename*` y el navegador lo
    usa: la descarga conserva «Screenshot ... PM.jpg» y no un nombre mutilado."""
    c = cabecera_nombre(MAC, "imagen")
    assert "filename*=UTF-8''" in c
    assert "%E2%80%AF" in c, "el espacio fino tiene que ir codificado, no perdido"
    assert "Screenshot" in c


def test_el_de_siempre_no_cambia():
    """Lo que ya cabía en latin-1 se sirve igual que antes, sin `filename*` de más."""
    c = cabecera_nombre("IMG_4821.jpg", "imagen")
    assert c == 'inline; filename="IMG_4821.jpg"'


def test_sin_nombre_se_usa_el_generico():
    assert cabecera_nombre(None, "imagen") == 'inline; filename="imagen"'
    assert cabecera_nombre("   ", "foto") == 'inline; filename="foto"'


def test_un_nombre_entero_en_otro_alfabeto_no_se_queda_en_guiones():
    """Si al pasarlo a ASCII no queda nada legible, el de respaldo es el genérico: un
    «___.jpg» no le dice nada a nadie. El bueno sigue yendo en `filename*`."""
    c = cabecera_nombre("写真.jpg", "imagen")
    assert _se_puede_mandar(c)
    # Con el genérico y SU EXTENSIÓN: «.jpg» a secas es un fichero sin nombre, y el
    # ordenador que se lo baje tiene que saber que es una imagen.
    assert 'filename="imagen.jpg"' in c
    assert "filename*=UTF-8''" in c


@pytest.mark.parametrize("nombre", [
    "Screenshot 2026-08-26 at 9.44.13 PM.png",   # los de producción
    "Captura de pantalla 2026-08-28 a las 19.32.45.png",
    'foto"con"comillas.jpg',                          # comillas: romperían la cabecera
    "salto\nde\nlinea.jpg",                           # y un salto la partiría en dos
    "café con leche.jpg",                             # acentos, que sí caben en latin-1
    "café descompuesto.jpg",                    # el mismo en NFD, como lo escribe macOS
])
def test_ninguno_de_estos_nombres_puede_tumbar_la_respuesta(nombre):
    c = cabecera_nombre(nombre, "imagen")
    assert _se_puede_mandar(c)
    assert "\n" not in c and "\r" not in c
    # Las comillas del nombre no pueden cerrar la del `filename=`.
    assert c.count('"') == 2
