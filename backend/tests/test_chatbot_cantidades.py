"""
Cambiar la cantidad de un alimento hablando con el asistente.

Caso real reportado el 02-08-2026: un cliente con un zumo en la comida escribio
"la cantidad de sumo que sea la mitad" y recibio "sumo: no encontrado en la base de
datos", teniendo el zumo delante en la lista. Fallaban tres cosas a la vez:

  1. el patron se llevaba la frase entera como nombre ("sumo que sea la mitad"),
  2. "sumo" no encontraba el "zumo" (media España sesea, y en el movil se escribe
     deprisa),
  3. y aunque las dos anteriores hubieran ido bien, habia un limite de 6 palabras
     que dejaba fuera la peticion por larga.
"""
import pytest

from chatbot import NutritionChatbot as C

# Estas funciones solo miran el texto: no hace falta levantar una sesion entera para
# probarlas, pero si un objeto de verdad porque se llaman entre ellas.
BOT = object.__new__(C)


class TestElNombreDelAlimento:
    """Lo que se extrae tiene que ser el alimento, no la frase entera."""

    @pytest.mark.parametrize("frase,esperado", [
        ("la cantidad de sumo que sea la mitad", "sumo"),
        ("la mitad de zumo", "zumo"),
        ("el doble de pollo", "pollo"),
        ("pon la mitad de arroz por favor", "arroz"),
        ("la mitad de arroz porfa", "arroz"),
        ("que el zumo sea la mitad", "zumo"),
        ("el triple de avena", "avena"),
    ])
    def test_se_queda_solo_con_el_alimento(self, frase, esperado):
        assert BOT._intento_multiplicador(frase)[1] == esperado

    def test_sin_nombre_se_refiere_al_ultimo(self):
        assert BOT._intento_multiplicador("la mitad")[1] == "__ultimo__"

    @pytest.mark.parametrize("frase,factor", [
        ("la mitad de zumo", 0.5),
        ("el doble de pollo", 2.0),
        ("el triple de avena", 3.0),
        ("duplica el arroz", 2.0),
    ])
    def test_el_factor(self, frase, factor):
        assert BOT._intento_multiplicador(frase)[0] == factor

    def test_una_frase_sin_multiplicador_no_lo_activa(self):
        assert BOT._intento_multiplicador("pon 200 gramos de arroz") is None


class TestComoSuena:
    """Comparar por como suena, no por como se escribe."""

    @pytest.mark.parametrize("escrito,real", [
        ("sumo", "zumo"),            # seseo, el caso reportado
        ("cosido", "cocido"),
        ("arros", "arroz"),
        ("poyo", "pollo"),           # yeismo
        ("abena", "avena"),
        ("aceyte", "aceite"),
        ("kalabacin", "calabacin"),
        ("arrozz", "arroz"),         # dobles al escribir deprisa
    ])
    def test_se_reconocen_igual(self, escrito, real):
        assert C._clave_fonetica(escrito) == C._clave_fonetica(real)

    @pytest.mark.parametrize("a,b", [
        ("pollo", "pavo"), ("arroz", "avena"), ("zumo", "humus"),
        ("pan", "atun"), ("leche", "lentejas"),
    ])
    def test_pero_no_se_confunden_alimentos_distintos(self, a, b):
        """Plegar sonidos no puede hacer que un alimento encuentre a otro."""
        assert C._clave_fonetica(a) != C._clave_fonetica(b)

    def test_no_se_come_las_diferencias_de_verdad(self):
        assert C._clave_fonetica("pollo") != C._clave_fonetica("polvo")


class TestQuitarCantidades:
    """Lo que ya funcionaba, para que siga funcionando."""

    @pytest.mark.parametrize("frase,nombre,n,en_gramos", [
        ("quita 100 gramos de arroz", "arroz", 100.0, True),
        ("quita 50 g de arroz", "arroz", 50.0, True),
        ("quita 2 claras", "claras", 2.0, False),
        ("2 huevos menos", "huevos", 2.0, False),
    ])
    def test_lo_que_entiende(self, frase, nombre, n, en_gramos):
        r = BOT._intento_decremento(frase)
        assert r == (nombre, n, en_gramos)

    def test_dejar_en_una_cantidad_no_es_restar(self):
        """"deja el arroz en 80" fija el total; no resta 80."""
        assert BOT._intento_decremento("deja el arroz en 80 gramos") is None

    def test_quitar_a_secas_se_refiere_al_ultimo(self):
        assert BOT._intento_decremento("quita uno")[0] == "__ultimo__"

    def test_un_mensaje_que_quita_y_añade_no_es_solo_resta(self):
        assert BOT._intento_decremento("quitame el arroz y ponme mas pollo") is None
