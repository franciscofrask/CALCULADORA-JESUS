"""
Variantes de género y número en la búsqueda de alimentos (petición 2026-08-02).

Nadie pide la comida como está escrita en el catálogo: alguien pide "tostadas" y en la
base pone "Pan tostado". Antes no se encontraban, y la lista de opciones se llenaba de
marcas raras sin que el genérico de toda la vida apareciera nunca.

Aquí se fija la raíz (que es de donde sale todo lo demás) y el freno: una raíz corta
emparejaría media base, así que no se usa.
"""
import pytest

from chatbot import NutritionChatbot as C


class TestLaRaiz:
    @pytest.mark.parametrize("palabra", ["tostadas", "tostada", "tostado", "tostados"])
    def test_las_cuatro_formas_caen_en_la_misma_raiz(self, palabra):
        assert C._raiz(palabra) == "tostad"

    def test_el_plural_en_es_tambien(self):
        assert C._raiz("panes") == "pan" or C._raiz("panes") == ""

    @pytest.mark.parametrize("palabra", ["pan", "col", "ajo", "te"])
    def test_las_palabras_muy_cortas_no_dan_raiz(self, palabra):
        assert C._raiz(palabra) == ""

    def test_nunca_recorta_por_debajo_de_cuatro_letras(self):
        """Lo peligroso sería "pavo" -> "pav": emparejaría media base. Se queda entero."""
        assert C._raiz("pavo") == "pavo"
        for p in ("pavo", "pollo", "huevo", "arroz", "queso", "leche", "atun"):
            assert len(C._raiz(p)) == 0 or len(C._raiz(p)) >= 4, p

    def test_una_palabra_larga_conserva_sentido(self):
        """Se le quita el plural y nada más. Hasta el 08-08-2026 quedaba en "almendr" y
        de ahí alcanzaba también al almendro, que es el árbol."""
        assert C._raiz("almendras") == "almendra"

    @pytest.mark.parametrize("femenino,masculino", [
        ("pimienta", "pimiento"),   # Francisco, 08-08: pedía pimienta y le salían
        ("hueva", "huevo"),         # pimientos rojos
        ("grana", "grano"),
    ])
    def test_el_genero_de_un_sustantivo_no_es_la_misma_palabra(self, femenino, masculino):
        """La -o y la -a de un sustantivo distinguen alimentos distintos; quitarlas los
        fundía en la misma raíz. En los participios sí es flexión y se sigue quitando."""
        assert C._raiz(femenino) != C._raiz(masculino), (
            f"«{femenino}» y «{masculino}» caen en la misma raíz")

    @pytest.mark.parametrize("a,b", [
        ("tostada", "tostado"), ("cocidas", "cocido"), ("asada", "asados"),
    ])
    def test_el_genero_de_un_participio_si(self, a, b):
        assert C._raiz(a) == C._raiz(b), f"«{a}» y «{b}» son la misma palabra"

    def test_no_revienta_con_basura(self):
        for v in ("", "   ", None):
            assert C._raiz(v) == ""


class TestElPatron:
    def test_casa_las_variantes_de_tostada(self):
        import re
        pat = C._regex_raiz("tostadas")
        assert pat
        for nombre in ("pan tostado", "tostadas de avena", "avellana tostada",
                       "pistachos tostados"):
            assert re.search(pat, nombre), nombre

    def test_no_casa_otra_cosa(self):
        import re
        pat = C._regex_raiz("tostadas")
        for nombre in ("pan de barra", "pechuga de pollo", "arroz blanco"):
            assert not re.search(pat, nombre), nombre

    def test_sin_patron_cuando_la_palabra_es_muy_corta(self):
        assert C._regex_raiz("col") == ""

    def test_pavo_no_arrastra_medio_catalogo(self):
        """Con raíz "pav" habría traído pavía, pavo real y demás. Solo pavo/pavos."""
        import re
        pat = C._regex_raiz("pavo")
        assert re.search(pat, "pechuga de pavo") and re.search(pat, "pavos enteros")
        for nombre in ("pavia en almibar", "pan de barra", "pechuga de pollo"):
            assert not re.search(pat, nombre), nombre

    def test_respeta_los_acentos_al_normalizar(self):
        """"plátanos" y "platano" tienen que dar la misma raíz."""
        assert C._raiz(C._norm_text("plátanos")) == C._raiz(C._norm_text("platano"))
