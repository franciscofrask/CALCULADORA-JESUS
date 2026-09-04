"""LA FOTO DEL SUPLEMENTO, RESUELTA AL SERVIR (3-09-2026).

«Falta la foto. Falta la foto, Francisco. La foto no esta.» (Jesus, minuto 28:22 del video
con Gonzalo.) Medido: 5.435 de los 5.445 suplementos pautados salian sin foto, porque al
pautar se congela una copia de la ficha y los 100 protocolos se guardaron antes de que se
importaran las imagenes.

Y los `catalog_id` de los protocolos casi no existen ya en el catalogo -- 6 de 85 --, asi
que buscar solo por id no arregla nada: hay que cruzar tambien por nombre normalizado, que
si casa. Con eso se recuperan 3.669 de 5.445.

Funciones puras: se prueban sin base ni servidor. Lo de la pantalla se comprobo en el
navegador con la cuenta de una clienta con protocolo (`_guia/_suplementos_con_foto.png`).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.foto_del_suplemento import clave, foto_de      # noqa: E402

FOTOS = {
    "ciclodextrina": "https://fullgas.org/ciclo.jpg",
    "whey isolate crema de arroz": "https://fullgas.org/whey.jpg",
}


def test_el_id_con_guiones_y_el_nombre_con_espacios_son_la_misma_llave():
    assert clave("whey-isolate-crema-de-arroz") == "whey isolate crema de arroz"
    assert clave("Whey Isolate + crema de arroz") == "whey isolate crema de arroz"
    assert clave("Aceite de krill") == clave("ACEITE  DE   KRILL")


def test_la_encuentra_por_el_id_aunque_la_linea_no_la_traiga():
    item = {"catalog_id": "ciclodextrina", "titulo": "Ciclodextrina", "imagen": None}
    assert foto_de(item, FOTOS) == "https://fullgas.org/ciclo.jpg"


def test_y_por_el_nombre_cuando_el_id_ya_no_existe():
    # El caso de verdad: `whey-isolate-crema-de-arroz` no esta en el catalogo, pero
    # «Whey Isolate + crema de arroz» si.
    item = {"catalog_id": "whey-isolate-crema-de-arroz",
            "titulo": "Whey Isolate + crema de arroz", "imagen": None}
    assert foto_de(item, FOTOS) == "https://fullgas.org/whey.jpg"


def test_la_congelada_manda_si_es_una_direccion_de_verdad():
    item = {"catalog_id": "ciclodextrina", "titulo": "Ciclodextrina",
            "imagen": "https://fullgas.org/la-que-le-pusieron.jpg"}
    assert foto_de(item, FOTOS) == "https://fullgas.org/la-que-le-pusieron.jpg"


def test_una_ruta_relativa_no_es_una_foto():
    # En el catalogo del coach hay 14 fichas con cosas como `tarro.webp`: apuntan a un sitio
    # que no es el nuestro, o sea una imagen rota en la pantalla del cliente. Se ignora y se
    # busca otra; el icono de pastilla es mejor que una foto que no carga.
    item = {"catalog_id": "ciclodextrina", "titulo": "Ciclodextrina", "imagen": "tarro.webp"}
    assert foto_de(item, FOTOS) == "https://fullgas.org/ciclo.jpg"


def test_lo_que_no_tiene_nadie_se_queda_sin_foto_y_no_se_inventa():
    # Son nueve: Omega 3 (hombre y mujer), Hydropeptides o MAP (tres dosis), Ursobilane
    # (tres) y PRO-H. Esos hay que subirlos.
    item = {"catalog_id": "omega-3-hombre", "titulo": "Omega 3 hombre", "imagen": None}
    assert foto_de(item, FOTOS) is None
