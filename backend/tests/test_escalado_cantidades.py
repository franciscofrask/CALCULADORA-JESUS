"""
Los macros del metodo son LINEALES con la cantidad.

De esto depende `scaleFood` (frontend/src/pages/NutritionPage.jsx): al pulsar -/+ no
llama al servidor, escala los `macros_efectivos` que ya tiene el alimento por el cambio
de cantidad. Eso solo vale si escalar == recalcular.

Antes escalaba los campos crudos del catalogo (los de la etiqueta) y al pan se le
colaban 6,8 g de proteina y 1,4 g de grasa que el metodo no cuenta.

Si algun dia una regla deja de ser lineal (por ejemplo un tope por racion), estos tests
se ponen en rojo y hay que volver a recalcular en el servidor en vez de escalar.
"""
import pytest

from calma_suggest import macros_efectivos

PAN = {"nombre": "Pan crujiente", "proteinas": 13, "hidratos": 75, "grasas": 2.7,
       "racion": 100, "categorias": "8.1"}
ARROZ = {"nombre": "Arroz blanco", "proteinas": 7, "hidratos": 80, "grasas": 1,
         "racion": 100, "categorias": "21.1"}
ALMENDRAS = {"nombre": "Almendras", "proteinas": 23, "hidratos": 4.8, "grasas": 53.1,
             "racion": 100, "categorias": "17.2.1"}
POLLO = {"nombre": "Pechuga de pollo", "proteinas": 20, "hidratos": 0, "grasas": 0,
         "racion": 100, "categorias": "2.2.1"}
HUEVO = {"nombre": "Huevos enteros L", "proteinas": 8, "hidratos": 0, "grasas": 6,
         "racion": 63, "unidades": True, "categorias": "3.1"}

TODOS = [PAN, ARROZ, ALMENDRAS, POLLO, HUEVO]


class TestLinealidad:
    @pytest.mark.parametrize("food", TODOS, ids=lambda f: f["nombre"])
    @pytest.mark.parametrize("desde,hasta", [(90, 91), (100, 250), (200, 50), (63, 126), (100, 103)])
    def test_escalar_es_igual_que_recalcular(self, food, desde, hasta):
        """Lo que hace scaleFood tiene que dar lo mismo que preguntarle al motor."""
        base = macros_efectivos(food, desde)
        factor = hasta / desde
        escalado = {k: round(base[k] * factor, 1) for k in "PHG"}
        recalculado = {k: round(macros_efectivos(food, hasta)[k], 1) for k in "PHG"}
        for k in "PHG":
            assert escalado[k] == pytest.approx(recalculado[k], abs=0.15), (
                f"{food['nombre']} {k}: escalando {escalado[k]} vs recalculando {recalculado[k]}")

    def test_muchos_pasos_no_derivan(self):
        """12 clics del boton + no pueden separarse del valor real por redondeos."""
        cantidad = 90.0
        macros = macros_efectivos(ARROZ, cantidad)
        for _ in range(12):
            nueva = cantidad + 1
            factor = nueva / cantidad
            macros = {k: round(macros[k] * factor, 1) for k in "PHG"}
            cantidad = nueva
        real = macros_efectivos(ARROZ, cantidad)
        for k in "PHG":
            assert macros[k] == pytest.approx(real[k], abs=0.2)


class TestLoQueNoDebeAparecer:
    def test_al_pan_no_le_sale_proteina_al_escalar(self):
        """El caso concreto que se colaba: 60 g de pan -> 62 g."""
        base = macros_efectivos(PAN, 60)
        assert base["P"] == 0 and base["G"] == 0  # el metodo no los cuenta
        factor = 62 / 60
        escalado = {k: round(base[k] * factor, 1) for k in "PHG"}
        assert escalado["P"] == 0, "la proteina del pan no cuenta a ninguna cantidad"
        assert escalado["G"] == 0

    def test_a_las_almendras_no_les_sale_proteina(self):
        base = macros_efectivos(ALMENDRAS, 30)
        assert base["P"] == 0
        assert round(base["P"] * (45 / 30), 1) == 0

    def test_escalar_la_etiqueta_habria_dado_otra_cosa(self):
        """Deja constancia de cuanto se colaba: 62 g de pan = 8,1 g de proteina."""
        etiqueta = round(PAN["proteinas"] * 62 / 100, 1)
        metodo = round(macros_efectivos(PAN, 62)["P"], 1)
        assert etiqueta == 8.1
        assert metodo == 0.0
