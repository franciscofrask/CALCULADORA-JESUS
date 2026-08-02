"""
El buscador de alimentos ordena por lo que se ha escrito.

El filtro de nombre es "cada palabra de la query aparece en el nombre", en cualquier
posicion. Con eso solo, buscar "huevo" devolvia los huevos mezclados con un "Doble
McExtreme BBQ Bourbon Huevo", y "Huevos enteros M/XL" ni siquiera salian: el orden lo
decidian la diferencia de macros o la frecuencia de uso, que no saben lo que se ha
escrito. Escribir "huevos" (en plural) sI los sacaba, y esa diferencia no tenia
ninguna logica para quien busca.

Estos tests fijan el desempate por relevancia. La relevancia SOLO ordena: no filtra
nada ni cambia el orden cuando no hay texto (categorias, sugeridor, cuadrar).
"""
import re

from calculator import normalize_text


def relevancia(nombre: str, query: str) -> int:
    """Copia de la funcion del endpoint (routes/calculator.py, search_foods_endpoint).

    0 = el nombre empieza por lo escrito, 1 = lo escrito arranca una palabra del
    nombre, 2 = solo aparece suelto.
    """
    q = normalize_text(query).strip()
    if not q:
        return 0
    n = normalize_text(nombre)
    if n.startswith(q):
        return 0
    if re.search(r"\b" + re.escape(q), n):
        return 1
    return 2


class TestOrdenPorRelevancia:
    def test_los_que_empiezan_por_lo_escrito_van_primero(self):
        assert relevancia("Huevos enteros L", "huevo") == 0
        assert relevancia("Huevos cocidos (Hacendado)", "huevo") == 0

    def test_despues_los_que_lo_llevan_como_palabra(self):
        assert relevancia("Claras de huevo pasteurizadas", "huevo") == 1
        assert relevancia("Doble McExtreme BBQ Bourbon Huevo (McDonald's)", "huevo") == 1

    def test_el_hamburguesa_no_gana_al_huevo(self):
        """El caso que reporto el usuario."""
        huevo = relevancia("Huevos enteros L", "huevo")
        burger = relevancia("Doble McExtreme BBQ Bourbon Huevo (McDonald's)", "huevo")
        assert huevo < burger

    def test_singular_y_plural_ordenan_igual(self):
        """"huevo" y "huevos" tienen que sacar los mismos primeros."""
        nombres = ["Huevos enteros L", "Claras de huevo pasteurizadas",
                   "Huevos enteros XL", "Filetes de merluza al huevo (Hacendado)"]
        por_singular = sorted(nombres, key=lambda n: (relevancia(n, "huevo"), n))
        por_plural = sorted(nombres, key=lambda n: (relevancia(n, "huevos"), n))
        assert por_singular[:2] == por_plural[:2] == ["Huevos enteros L", "Huevos enteros XL"]

    def test_no_distingue_acentos_ni_mayusculas(self):
        assert relevancia("Atún al natural lata", "atun") == 0
        assert relevancia("ATÚN", "atún") == 0

    def test_varias_palabras(self):
        assert relevancia("Arroz integral (SOS)", "arroz integral") == 0
        assert relevancia("Arroz Integral con quinoa (Brillante)", "arroz integral") == 0
        # "arroz blanco integral" contiene las dos palabras pero no seguidas: el filtro
        # lo deja pasar (busca palabra a palabra) y la relevancia lo manda al final.
        assert relevancia("Arroz blanco integral", "arroz integral") == 2

    def test_sin_texto_todos_empatan(self):
        """Sin query la relevancia no puede alterar el orden del motor de macros."""
        assert relevancia("Lo que sea", "") == 0
        assert relevancia("Otra cosa", "   ") == 0


class TestNoRompeElResto:
    def test_solo_desempata_no_filtra(self):
        """Lo que no es relevante sigue estando, al final: nadie desaparece."""
        nombres = ["Huevos enteros L", "Tortilla con huevos camperos", "Flan de huevo"]
        ordenados = sorted(nombres, key=lambda n: (relevancia(n, "huevo"), n))
        assert len(ordenados) == len(nombres)
        assert set(ordenados) == set(nombres)

    def test_dentro_del_mismo_grupo_manda_el_orden_de_siempre(self):
        """Dos alimentos igual de relevantes conservan el orden que traian."""
        a, b = "Huevos enteros L", "Huevos enteros XL"
        assert relevancia(a, "huevo") == relevancia(b, "huevo")
