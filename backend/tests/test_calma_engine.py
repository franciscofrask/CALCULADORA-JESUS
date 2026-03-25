"""
Tests de verificacion del motor CALMA v2
Basados en la BIBLIA_ALIMENTOS_v2 (Marzo 2026)

35 casos de prueba que el motor DEBE pasar TODOS.
"""

import pytest
import sys
sys.path.insert(0, '/app/backend')

from calma_engine import (
    calcular_macros_efectivos,
    comida_cuadrada,
    tolerancia_postentreno,
    _calibracion_cereales_panes,
    _calibracion_frutos_secos
)


# =========================================================
# BLOQUE 1: REGLAS DE CONTEO POR CATEGORIA (28 tests)
# =========================================================

class TestBloque1ConteoCategoria:
    """Tests de reglas de conteo por categoria."""
    
    def test_1_1_huevo_entero(self):
        """Test 1.1 - Huevo entero (cat 1.2): P siempre, H si >=2, G si >=3."""
        # Por 100g: P=12.7, H=0, G=9.5
        r = calcular_macros_efectivos(12.7, 0, 9.5, "1.2", 126)  # 2 huevos
        
        assert r["proteina_cuenta"] == True, "P debe contar siempre en huevos"
        assert r["hidratos_cuenta"] == False, "H=0 no debe contar (< 2)"
        assert r["grasa_cuenta"] == True, "G=9.5 debe contar (>= 3)"
        
        # Macros efectivos para 126g (2 huevos)
        assert abs(r["proteina_efectiva"] - 16.0) < 0.5
        assert r["hidratos_efectivos"] == 0
        assert abs(r["grasa_efectiva"] - 12.0) < 0.5
    
    def test_1_2_clara_huevo(self):
        """Test 1.2 - Clara de huevo liquida (cat 1.1)."""
        # Por 100g: P=11, H=0.7, G=0
        r = calcular_macros_efectivos(11, 0.7, 0, "1.1", 100)
        
        assert r["proteina_cuenta"] == True
        assert r["hidratos_cuenta"] == False, "H=0.7 < 2"
        assert r["grasa_cuenta"] == False, "G=0 < 3"
    
    def test_1_3_pechuga_pollo(self):
        """Test 1.3 - Pechuga de pollo (cat 2.2)."""
        # Por 100g: P=23, H=0, G=1.2
        r = calcular_macros_efectivos(23, 0, 1.2, "2.2", 200)
        
        assert r["proteina_cuenta"] == True
        assert r["hidratos_cuenta"] == False, "H=0 < 2"
        assert r["grasa_cuenta"] == False, "G=1.2 < 3"
        
        assert abs(r["proteina_efectiva"] - 46.0) < 0.5
        assert r["hidratos_efectivos"] == 0
        assert r["grasa_efectiva"] == 0
    
    def test_1_4_chorizo(self):
        """Test 1.4 - Chorizo (cat 2.1): todos los umbrales pasados."""
        # Por 100g: P=22, H=2, G=30
        r = calcular_macros_efectivos(22, 2, 30, "2.1", 100)
        
        assert r["proteina_cuenta"] == True
        assert r["hidratos_cuenta"] == True, "H=2 >= 2"
        assert r["grasa_cuenta"] == True, "G=30 >= 3"
    
    def test_1_5_salmon(self):
        """Test 1.5 - Salmon (cat 3)."""
        # Por 100g: P=20, H=0, G=13
        r = calcular_macros_efectivos(20, 0, 13, "3", 100)
        
        assert r["proteina_cuenta"] == True
        assert r["hidratos_cuenta"] == False, "H=0 < 2"
        assert r["grasa_cuenta"] == True, "G=13 >= 3"
    
    def test_1_6_gambas_mariscos_umbral_estricto(self):
        """Test 1.6 - Gambas (cat 3.9): umbral H estrictamente > 3."""
        # Por 100g: P=24, H=3, G=0.5
        r = calcular_macros_efectivos(24, 3, 0.5, "3.9", 100)
        
        assert r["proteina_cuenta"] == True
        assert r["hidratos_cuenta"] == False, "H=3 NO es > 3 (exactamente 3)"
        assert r["grasa_cuenta"] == False, "G=0.5 < 3"
    
    def test_1_7_surimi_mariscos(self):
        """Test 1.7 - Surimi (cat 3.9): H que si pasa."""
        # Por 100g: P=7, H=12, G=1
        r = calcular_macros_efectivos(7, 12, 1, "3.9", 100)
        
        assert r["proteina_cuenta"] == True
        assert r["hidratos_cuenta"] == True, "H=12 > 3"
        assert r["grasa_cuenta"] == False, "G=1 < 3"
    
    def test_1_8_whey_isolate(self):
        """Test 1.8 - Whey Isolate (cat 4.1.1): umbral 6g."""
        # Por 100g: P=90, H=3, G=1
        r = calcular_macros_efectivos(90, 3, 1, "4.1.1", 100)
        
        assert r["proteina_cuenta"] == True
        assert r["hidratos_cuenta"] == False, "H=3 no > 6"
        assert r["grasa_cuenta"] == False, "G=1 no > 6"
    
    def test_1_9_yogur_griego(self):
        """Test 1.9 - Yogur griego (cat 5.2): alimento mixto."""
        # Por 100g: P=5, H=4, G=10
        r = calcular_macros_efectivos(5, 4, 10, "5.2", 150)
        
        assert r["proteina_cuenta"] == True, "P siempre en lacteos"
        assert r["hidratos_cuenta"] == True, "H siempre en lacteos"
        assert r["grasa_cuenta"] == True, "G=10 > 1"
        
        assert abs(r["proteina_efectiva"] - 7.5) < 0.5
        assert abs(r["hidratos_efectivos"] - 6.0) < 0.5
        assert abs(r["grasa_efectiva"] - 15.0) < 0.5
    
    def test_1_10_yogur_desnatado(self):
        """Test 1.10 - Yogur desnatado 0% (cat 5.2)."""
        # Por 100g: P=10, H=4, G=0
        r = calcular_macros_efectivos(10, 4, 0, "5.2", 100)
        
        assert r["proteina_cuenta"] == True
        assert r["hidratos_cuenta"] == True
        assert r["grasa_cuenta"] == False, "G=0 no > 1"
    
    def test_1_11_leche_soja(self):
        """Test 1.11 - Leche de soja (cat 6.1): igual que lacteos."""
        # Por 100g: P=3.3, H=0.5, G=1.8
        r = calcular_macros_efectivos(3.3, 0.5, 1.8, "6.1", 100)
        
        assert r["proteina_cuenta"] == True
        assert r["hidratos_cuenta"] == True
        assert r["grasa_cuenta"] == True, "G=1.8 > 1"
    
    def test_1_12_avena(self):
        """Test 1.12 - Avena (cat 7.1): P no pasa 1/3."""
        # Por 100g: P=13, H=60, G=7
        r = calcular_macros_efectivos(13, 60, 7, "7.1", 100)
        
        assert r["hidratos_cuenta"] == True, "H siempre en cereales"
        assert r["proteina_cuenta"] == False, "P=13 no > 60/3=20"
        assert r["grasa_cuenta"] == False, "G=7 no > 8 y no > 60/4=15"
    
    def test_1_13_granola_grasa(self):
        """Test 1.13 - Granola con frutos secos (cat 7.1): G pasa umbral absoluto."""
        # Por 100g: P=10, H=55, G=18
        r = calcular_macros_efectivos(10, 55, 18, "7.1", 100)
        
        assert r["hidratos_cuenta"] == True
        assert r["proteina_cuenta"] == False, "P=10 no > 55/3=18.3"
        assert r["grasa_cuenta"] == True, "G=18 > 8 (umbral absoluto)"
    
    def test_1_14_patata(self):
        """Test 1.14 - Patata (cat 9): solo H."""
        # Por 100g: P=2, H=17, G=0.1
        r = calcular_macros_efectivos(2, 17, 0.1, "9", 200)
        
        assert r["proteina_cuenta"] == False, "P NUNCA en tuberculos"
        assert r["hidratos_cuenta"] == True
        assert r["grasa_cuenta"] == False, "G NUNCA en tuberculos"
    
    def test_1_15_garbanzos(self):
        """Test 1.15 - Garbanzos cocidos (cat 10): alimento mixto."""
        # Por 100g: P=9, H=27, G=3
        r = calcular_macros_efectivos(9, 27, 3, "10", 100)
        
        assert r["proteina_cuenta"] == True
        assert r["hidratos_cuenta"] == True
        assert r["grasa_cuenta"] == False, "G=3 < 8"
    
    def test_1_16_lechuga(self):
        """Test 1.16 - Lechuga (cat 13.1): NADA cuenta."""
        # Por 100g: P=1.3, H=2, G=0.2
        r = calcular_macros_efectivos(1.3, 2, 0.2, "13.1", 150)
        
        assert r["proteina_cuenta"] == False, "P nunca en verduras"
        assert r["hidratos_cuenta"] == False, "H=2 no > 4"
        assert r["grasa_cuenta"] == False, "G=0.2 no > 4"
        
        assert r["proteina_efectiva"] == 0
        assert r["hidratos_efectivos"] == 0
        assert r["grasa_efectiva"] == 0
    
    def test_1_17_guisantes(self):
        """Test 1.17 - Guisantes (cat 13): verdura con macros."""
        # Por 100g: P=5, H=14, G=0.4
        r = calcular_macros_efectivos(5, 14, 0.4, "13", 100)
        
        assert r["proteina_cuenta"] == False, "P nunca en verduras"
        assert r["hidratos_cuenta"] == True, "H=14 > 4"
        assert r["grasa_cuenta"] == False, "G=0.4 no > 4"
    
    def test_1_18_ketchup(self):
        """Test 1.18 - Ketchup (cat 16.2): umbral 6g."""
        # Por 100g: P=1, H=24, G=0
        r = calcular_macros_efectivos(1, 24, 0, "16.2", 100)
        
        assert r["proteina_cuenta"] == False, "P=1 < 6"
        assert r["hidratos_cuenta"] == True, "H=24 >= 6"
        assert r["grasa_cuenta"] == False, "G=0 < 6"
    
    def test_1_19_aceite_oliva(self):
        """Test 1.19 - Aceite de oliva (cat 17.1.1): solo G."""
        # Por 100g: P=0, H=0, G=100
        r = calcular_macros_efectivos(0, 0, 100, "17.1.1", 100)
        
        assert r["proteina_cuenta"] == False
        assert r["hidratos_cuenta"] == False
        assert r["grasa_cuenta"] == True
    
    def test_1_20_arroz_blanco(self):
        """Test 1.20 - Arroz blanco (cat 21.1): P NUNCA."""
        # Por 100g: P=7, H=78, G=0.6
        r = calcular_macros_efectivos(7, 78, 0.6, "21.1", 100)
        
        assert r["proteina_cuenta"] == False, "P NUNCA en arroz (proteina incompleta)"
        assert r["hidratos_cuenta"] == True
        assert r["grasa_cuenta"] == False, "G=0.6 < 6"
    
    def test_1_21_espaguetis(self):
        """Test 1.21 - Espaguetis (cat 22.1.1)."""
        # Por 100g: P=13, H=71, G=2
        r = calcular_macros_efectivos(13, 71, 2, "22.1.1", 100)
        
        assert r["hidratos_cuenta"] == True
        assert r["proteina_cuenta"] == False, "P=13 no > 71/3=23.7"
        assert r["grasa_cuenta"] == False, "G=2 no > 9 y no > 23.7"
    
    def test_1_22_tortellini_carne(self):
        """Test 1.22 - Tortellini de carne (cat 22.1.2.2): TODOS cuentan."""
        # Por 100g: P=11, H=45, G=7
        r = calcular_macros_efectivos(11, 45, 7, "22.1.2.2", 100)
        
        assert r["proteina_cuenta"] == True
        assert r["hidratos_cuenta"] == True
        assert r["grasa_cuenta"] == True
    
    def test_1_23_noquis(self):
        """Test 1.23 - Noquis (cat 22.6): TODOS cuentan."""
        # Por 100g: P=4, H=35, G=2
        r = calcular_macros_efectivos(4, 35, 2, "22.6", 100)
        
        assert r["proteina_cuenta"] == True
        assert r["hidratos_cuenta"] == True
        assert r["grasa_cuenta"] == True
    
    def test_1_24_patatas_fritas(self):
        """Test 1.24 - Patatas fritas (cat 38.1): H+G siempre."""
        # Por 100g: P=4, H=45, G=15
        r = calcular_macros_efectivos(4, 45, 15, "38.1", 100)
        
        assert r["hidratos_cuenta"] == True
        assert r["grasa_cuenta"] == True
        assert r["proteina_cuenta"] == False, "P=4, 4*4=16 < 45 (regla 25%)"
    
    def test_1_25_aminoacidos_map(self):
        """Test 1.25 - Aminoacidos MAP (cat 41): solo P."""
        # Por 100g: P=99, H=0, G=0
        r = calcular_macros_efectivos(99, 0, 0, "41", 100)
        
        assert r["proteina_cuenta"] == True
        assert r["hidratos_cuenta"] == False
        assert r["grasa_cuenta"] == False
    
    def test_1_26_sopa_pollo(self):
        """Test 1.26 - Sopa de pollo (cat 48): umbral 2g."""
        # Por 100g: P=3, H=5, G=1
        r = calcular_macros_efectivos(3, 5, 1, "48", 100)
        
        assert r["proteina_cuenta"] == True, "P=3 >= 2"
        assert r["hidratos_cuenta"] == True, "H=5 >= 2"
        assert r["grasa_cuenta"] == False, "G=1 < 2"
    
    def test_1_27_big_mac(self):
        """Test 1.27 - Big Mac McDonald's (cat 49): TODOS cuentan."""
        # Por 100g: P=11.6, H=19.4, G=12
        r = calcular_macros_efectivos(11.6, 19.4, 12, "49", 100)
        
        assert r["proteina_cuenta"] == True
        assert r["hidratos_cuenta"] == True
        assert r["grasa_cuenta"] == True
    
    def test_1_28_chocolate_negro(self):
        """Test 1.28 - Chocolate negro 85% (cat 37)."""
        # Por 100g: P=12, H=19, G=46
        r = calcular_macros_efectivos(12, 19, 46, "37", 100)
        
        assert r["hidratos_cuenta"] == True, "H siempre en cat 37"
        assert r["grasa_cuenta"] == True, "G=46 > 10"
        # P: regla 25%, G=46 es predominante. 12*4=48 > 46 -> SI
        assert r["proteina_cuenta"] == True, "P=12, 12*4=48 > 46"


# =========================================================
# BLOQUE 2: CALIBRACION PROGRESIVA DE CEREALES Y PANES (4 tests)
# =========================================================

class TestBloque2CalibracionCereales:
    """Tests de calibracion progresiva para cat 7+8."""
    
    def test_2_1_cereales_proteicos_3_comidas(self):
        """Test 2.1 - Cereales proteicos en 3 comidas."""
        # Alimento: cat 7, por 100g: P=25, H=55
        # P > H/3 -> 25 > 18.3 -> SI, aplica calibracion
        
        # Comida 1: 40g. Acumulado=40g (0-50g). P al 0%.
        r1 = calcular_macros_efectivos(25, 55, 0, "7", 40, acumulado_cereales_panes=0)
        assert r1["calibracion_p"] == 0.0, "Acumulado 40g -> calibracion 0%"
        assert r1["proteina_efectiva"] == 0, "P efectiva debe ser 0"
        assert abs(r1["hidratos_efectivos"] - 22.0) < 0.5, "H=55*40/100=22"
        
        # Comida 2: 30g. Acumulado PREVIO=40g, nuevo=70g (50-100g). P al 50%.
        r2 = calcular_macros_efectivos(25, 55, 0, "7", 30, acumulado_cereales_panes=40)
        assert r2["calibracion_p"] == 0.5, "Acumulado 70g -> calibracion 50%"
        # P efectiva = 25 * 30/100 * 0.5 = 3.75
        assert abs(r2["proteina_efectiva"] - 3.75) < 0.5
        
        # Comida 3: 40g. Acumulado PREVIO=70g, nuevo=110g (>100g). P al 100%.
        r3 = calcular_macros_efectivos(25, 55, 0, "7", 40, acumulado_cereales_panes=70)
        assert r3["calibracion_p"] == 1.0, "Acumulado 110g -> calibracion 100%"
        # P efectiva = 25 * 40/100 * 1.0 = 10
        assert abs(r3["proteina_efectiva"] - 10.0) < 0.5
    
    def test_2_2_cereales_proteicos_sin_calibracion(self):
        """Test 2.2 - Cereales proteicos (cat 7.1.3) SIN calibracion."""
        # Cat 7.1.3 = cereales proteicos -> P SIEMPRE al 100%
        # Por 100g: P=25, H=55
        
        r = calcular_macros_efectivos(25, 55, 0, "7.1.3", 40, acumulado_cereales_panes=0)
        
        assert r["calibracion_p"] == 1.0, "Cat 7.1.3 NO tiene calibracion"
        assert abs(r["proteina_efectiva"] - 10.0) < 0.5, "P=25*40/100=10"
        assert abs(r["hidratos_efectivos"] - 22.0) < 0.5
    
    def test_2_3_pan_proteico_sin_calibracion(self):
        """Test 2.3 - Pan proteico (cat 8.8) SIN calibracion."""
        # Cat 8.8 = pan proteico -> P SIEMPRE al 100%
        # Por 100g: P=22, H=30
        
        r = calcular_macros_efectivos(22, 30, 0, "8.8", 50, acumulado_cereales_panes=0)
        
        assert r["calibracion_p"] == 1.0, "Cat 8.8 NO tiene calibracion"
        assert abs(r["proteina_efectiva"] - 11.0) < 0.5, "P=22*50/100=11"
        assert abs(r["hidratos_efectivos"] - 15.0) < 0.5
    
    def test_2_4_avena_pan_acumulado_conjunto(self):
        """Test 2.4 - Avena + pan en el mismo dia (acumulado conjunto)."""
        # Comida 1: 30g avena (cat 7, P=13, H=60). P: 13 no > 20 -> NO aplica calibracion
        r1 = calcular_macros_efectivos(13, 60, 0, "7", 30, acumulado_cereales_panes=0)
        assert r1["proteina_cuenta"] == False, "P de avena no pasa regla 1/3"
        assert r1["proteina_efectiva"] == 0
        
        # Comida 2: 40g pan proteico normal (cat 8, P=18, H=45). P: 18 > 15 -> SI
        # Acumulado: 30+40=70g (50-100g). P al 50%.
        r2 = calcular_macros_efectivos(18, 45, 0, "8", 40, acumulado_cereales_panes=30)
        assert r2["proteina_cuenta"] == True, "P de pan pasa regla 1/3"
        assert r2["calibracion_p"] == 0.5
        # P efectiva = 18 * 40/100 * 0.5 = 3.6
        assert abs(r2["proteina_efectiva"] - 3.6) < 0.5
        
        # Comida 3: 50g avena. P no pasa 1/3, asi que calibracion no aplica
        r3 = calcular_macros_efectivos(13, 60, 0, "7", 50, acumulado_cereales_panes=70)
        assert r3["proteina_cuenta"] == False
        assert r3["proteina_efectiva"] == 0
        assert abs(r3["hidratos_efectivos"] - 30.0) < 0.5


# =========================================================
# BLOQUE 3: CALIBRACION PROGRESIVA DE FRUTOS SECOS (2 tests)
# =========================================================

class TestBloque3CalibracionFrutosSecos:
    """Tests de calibracion progresiva para cat 17.2.1/3/4."""
    
    def test_3_1_almendras_3_comidas(self):
        """Test 3.1 - Almendras en 3 comidas."""
        # Alimento: cat 17.2.1, por 100g: P=21, H=4, G=54
        # G siempre. P: 21 > 54/3=18 -> SI, con calibracion. H: 4 no > 18 -> NO
        
        # Comida 1: 15g. Acumulado=15g (0-20g). P al 0%.
        r1 = calcular_macros_efectivos(21, 4, 54, "17.2.1", 15, acumulado_frutos_secos=0)
        assert r1["grasa_cuenta"] == True
        assert r1["proteina_cuenta"] == True, "P pasa regla G/3"
        assert r1["calibracion_p"] == 0.0, "Acumulado 15g -> 0%"
        assert r1["proteina_efectiva"] == 0
        assert abs(r1["grasa_efectiva"] - 8.1) < 0.5
        
        # Comida 2: 10g. Acumulado=25g (20-40g). P al 50%.
        r2 = calcular_macros_efectivos(21, 4, 54, "17.2.1", 10, acumulado_frutos_secos=15)
        assert r2["calibracion_p"] == 0.5
        # P efectiva = 21 * 10/100 * 0.5 = 1.05
        assert abs(r2["proteina_efectiva"] - 1.05) < 0.5
        
        # Comida 3: 20g. Acumulado=45g (>40g). P al 100%.
        r3 = calcular_macros_efectivos(21, 4, 54, "17.2.1", 20, acumulado_frutos_secos=25)
        assert r3["calibracion_p"] == 1.0
        # P efectiva = 21 * 20/100 * 1.0 = 4.2
        assert abs(r3["proteina_efectiva"] - 4.2) < 0.5
    
    def test_3_2_almendras_nueces_acumulado_conjunto(self):
        """Test 3.2 - Almendras + nueces (acumulado conjunto)."""
        # Almendras: P=21, G=54. P > 54/3=18 -> SI
        # Nueces: P=15, G=65. P > 65/3=21.7 -> NO. P nunca cuenta para nueces.
        
        # Comida 1: 15g almendras. Acumulado=15g. P al 0%.
        r1 = calcular_macros_efectivos(21, 4, 54, "17.2.1", 15, acumulado_frutos_secos=0)
        assert r1["proteina_efectiva"] == 0
        
        # Comida 2: 25g nueces. Acumulado=40g. Pero P nueces no pasa regla.
        r2 = calcular_macros_efectivos(15, 7, 65, "17.2.1", 25, acumulado_frutos_secos=15)
        assert r2["proteina_cuenta"] == False, "P=15 no > 65/3=21.7"
        assert r2["proteina_efectiva"] == 0
        assert abs(r2["grasa_efectiva"] - 16.25) < 0.5
        
        # Comida 3: 10g almendras. Acumulado=50g (>40g). P al 100%.
        r3 = calcular_macros_efectivos(21, 4, 54, "17.2.1", 10, acumulado_frutos_secos=40)
        assert r3["calibracion_p"] == 1.0
        # P efectiva = 21 * 10/100 * 1.0 = 2.1
        assert abs(r3["proteina_efectiva"] - 2.1) < 0.5


# =========================================================
# BLOQUE 4: REGLA DE DOBLE CATEGORIA (4 tests)
# =========================================================

class TestBloque4DobleCategoria:
    """Tests de regla de doble categoria (la mas permisiva gana)."""
    
    def test_4_1_tomate_frito(self):
        """Test 4.1 - Tomate frito (cat 13.8 + 16.2)."""
        # Por 100g: P=1.5, H=6.5, G=3.5
        # Cat 13: P nunca. H > 4 -> SI. G > 4 -> NO.
        # Cat 16: P >= 6 -> NO. H >= 6 -> SI. G >= 6 -> NO.
        # Mas permisiva: H cuenta. G NO. P NO.
        
        r = calcular_macros_efectivos(1.5, 6.5, 3.5, "13.8", 100, categoria_secundaria="16.2")
        
        assert r["proteina_cuenta"] == False
        assert r["hidratos_cuenta"] == True
        assert r["grasa_cuenta"] == False
        assert abs(r["hidratos_efectivos"] - 6.5) < 0.5
    
    def test_4_2_alimento_h5_doble_cat(self):
        """Test 4.2 - Alimento con H=5g en cat 13.8 + 16.2."""
        # Cat 13: H > 4 -> 5 SI
        # Cat 16: H >= 6 -> 5 NO
        # Mas permisiva: H CUENTA (cat 13 lo permite)
        
        r = calcular_macros_efectivos(1, 5, 2, "13.8", 100, categoria_secundaria="16.2")
        
        assert r["hidratos_cuenta"] == True, "Cat 13 permite H=5"
    
    def test_4_3_mantequilla(self):
        """Test 4.3 - Mantequilla (cat 5.8 + 17.4)."""
        # Por 100g: P=0.6, H=0.4, G=82
        # Cat 5 (lacteos): P siempre, H siempre, G > 1 -> SI
        # Cat 17.4: solo G
        # Mas permisiva: P SI (cat 5), H SI (cat 5), G SI (ambas)
        
        r = calcular_macros_efectivos(0.6, 0.4, 82, "5.8", 100, categoria_secundaria="17.4")
        
        assert r["proteina_cuenta"] == True, "Cat 5 permite P"
        assert r["hidratos_cuenta"] == True, "Cat 5 permite H"
        assert r["grasa_cuenta"] == True
    
    def test_4_4_aceitunas_negras(self):
        """Test 4.4 - Aceitunas negras (cat 17.1.2 + 38 + 42)."""
        # Por 100g: P=0.6, H=0, G=16
        # Cat 17.1: solo G
        # Cat 38: regla 25%. P: 0.6*4=2.4 < 16 -> NO
        # Cat 42: solo G
        # Mas permisiva: solo G cuenta
        
        r = calcular_macros_efectivos(0.6, 0, 16, "17.1.2", 100, categoria_secundaria="38")
        
        assert r["proteina_cuenta"] == False
        assert r["hidratos_cuenta"] == False
        assert r["grasa_cuenta"] == True


# =========================================================
# BLOQUE 5: CANTIDADES MINIMAS Y SUGERENCIAS
# (Tests de logica, no de motor - se verifican reglas)
# =========================================================

class TestBloque5CantidadesMinimas:
    """Tests de cantidades minimas (verificacion de reglas)."""
    
    def test_5_1_salmon_no_cabe(self):
        """Test 5.1 - Salmon: verificar que P+G cuentan."""
        # Para el test de sugerencia: Salmon P+G cuentan
        r = calcular_macros_efectivos(20, 0, 13, "3", 23)  # 23g (hipotetico max)
        
        assert r["proteina_cuenta"] == True
        assert r["grasa_cuenta"] == True
        # Max por G=3: 23g da G=3.0
        assert abs(r["grasa_efectiva"] - 2.99) < 0.5
    
    def test_5_2_aceite_oliva_cabe(self):
        """Test 5.2 - Aceite de oliva: solo G cuenta."""
        r = calcular_macros_efectivos(0, 0, 100, "17.1", 8)
        
        assert r["grasa_cuenta"] == True
        assert abs(r["grasa_efectiva"] - 8.0) < 0.5
    
    def test_5_3_lechuga_sin_macros(self):
        """Test 5.3 - Lechuga: 0 macros efectivos."""
        r = calcular_macros_efectivos(1.3, 2, 0.2, "13", 100)
        
        assert r["proteina_efectiva"] == 0
        assert r["hidratos_efectivos"] == 0
        assert r["grasa_efectiva"] == 0
    
    def test_5_4_fruta_fresca(self):
        """Test 5.4 - Manzana: solo H cuenta."""
        # Por 100g: P=0.3, H=14, G=0.2
        r = calcular_macros_efectivos(0.3, 14, 0.2, "11.1", 90)  # 0.5 unidad
        
        assert r["hidratos_cuenta"] == True
        assert r["proteina_cuenta"] == False
        assert r["grasa_cuenta"] == False
        assert abs(r["hidratos_efectivos"] - 12.6) < 0.5


# =========================================================
# BLOQUE 6: MARGENES Y TOLERANCIAS (5 tests)
# =========================================================

class TestBloque6MargenesTolerancias:
    """Tests de margenes y tolerancias."""
    
    def test_6_1_comida_cuadrada(self):
        """Test 6.1 - Comida cuadrada."""
        objetivo = {"P": 40, "H": 60, "G": 15}
        consumido = {"P": 38, "H": 62, "G": 13}
        
        r = comida_cuadrada(objetivo, consumido)
        
        assert r["cuadrada"] == True
        assert r["diferencias"]["P"] == -2
        assert r["diferencias"]["H"] == 2
        assert r["diferencias"]["G"] == -2
    
    def test_6_2_comida_no_cuadrada(self):
        """Test 6.2 - Comida NO cuadrada."""
        objetivo = {"P": 40, "H": 60, "G": 15}
        consumido = {"P": 38, "H": 65, "G": 13}  # H se pasa en 5g
        
        r = comida_cuadrada(objetivo, consumido)
        
        assert r["cuadrada"] == False
        assert r["diferencias"]["H"] == 5
    
    def test_6_3_intra_cuadrado(self):
        """Test 6.3 - Intraentreno con margen +/-2g: CUADRADO."""
        objetivo = {"P": 10, "H": 20, "G": 0}
        consumido = {"P": 8, "H": 19, "G": 0}
        
        r = comida_cuadrada(objetivo, consumido, es_intra=True)
        
        assert r["cuadrada"] == True
    
    def test_6_4_intra_no_cuadrado(self):
        """Test 6.4 - Intraentreno NO cuadrado (P falta 3g)."""
        objetivo = {"P": 10, "H": 20, "G": 0}
        consumido = {"P": 7, "H": 19, "G": 0}  # P falta 3g, supera margen 2g
        
        r = comida_cuadrada(objetivo, consumido, es_intra=True)
        
        assert r["cuadrada"] == False
    
    def test_6_5_tolerancia_post_proteinas(self):
        """Test 6.5 - Tolerancia postentreno proteinas (<= 2g)."""
        # Faltan 1.5g de P -> VALIDO
        assert tolerancia_postentreno(30, 28.5) == True
        
        # Faltan 3g de P -> NO valido
        assert tolerancia_postentreno(30, 27) == False


# =========================================================
# BLOQUE 7: CASOS ESPECIALES (5 tests)
# =========================================================

class TestBloque7CasosEspeciales:
    """Tests de casos especiales."""
    
    def test_7_1_flan_clara_huevo(self):
        """Test 7.1 - Flan de clara de huevo (cat 36, NO cat 1)."""
        # Es un postre, no un huevo. Regla cat 36 (25%), no cat 1.
        # Por 100g: P=8.1, H=8.1, G=0
        r = calcular_macros_efectivos(8.1, 8.1, 0, "36", 100)
        
        # P y H empatan. Ambos superan 25% del otro: 8.1*4=32.4 > 8.1
        assert r["proteina_cuenta"] == True
        assert r["hidratos_cuenta"] == True
        assert r["grasa_cuenta"] == False
    
    def test_7_2_bebida_isotonica_zero(self):
        """Test 7.2 - Bebida isotonica zero (cat 18.1.2): NADA cuenta."""
        r = calcular_macros_efectivos(0, 0, 0, "18.1.2", 500)
        
        assert r["proteina_cuenta"] == False
        assert r["hidratos_cuenta"] == False
        assert r["grasa_cuenta"] == False
        assert r["proteina_efectiva"] == 0
        assert r["hidratos_efectivos"] == 0
        assert r["grasa_efectiva"] == 0
    
    def test_7_3_bebida_vegetal_post(self):
        """Test 7.3 - Bebida vegetal en postentreno: G <= 4g no cuenta."""
        # Por 100g: P=0.5, H=3, G=3
        r = calcular_macros_efectivos(0.5, 3, 3, "24", 100, es_post=True)
        
        # G=3 <= 4g, en postentreno no cuenta
        assert r["grasa_efectiva"] == 0
    
    def test_7_4_campo_minimo_bd(self):
        """Test 7.4 - Campo minimo en BD tiene prioridad (verificacion conceptual)."""
        # Este test verifica que el motor recibe correctamente los parametros
        # La logica de minimo la maneja calculator.py, no calma_engine.py
        # Aqui solo verificamos que las reglas de categoria funcionan
        r = calcular_macros_efectivos(20, 0, 1, "2.1", 15)  # 15g de embutido
        
        assert r["proteina_cuenta"] == True
        assert abs(r["proteina_efectiva"] - 3.0) < 0.5  # 20 * 15/100 = 3
    
    def test_7_5_congelados(self):
        """Test 7.5 - Alimento congelado (verificacion conceptual)."""
        # La regla de congelados (min 50g) la maneja calculator.py
        # Aqui verificamos que el motor calcula correctamente para 50g
        r = calcular_macros_efectivos(13, 60, 7, "7", 50)  # 50g cereales congelados
        
        assert r["hidratos_cuenta"] == True
        assert abs(r["hidratos_efectivos"] - 30.0) < 0.5  # 60 * 50/100 = 30


# =========================================================
# TESTS AUXILIARES DE FUNCIONES INTERNAS
# =========================================================

class TestFuncionesAuxiliares:
    """Tests de funciones auxiliares."""
    
    def test_calibracion_cereales_rangos(self):
        """Test de rangos de calibracion cereales/panes."""
        assert _calibracion_cereales_panes(0) == 0.0
        assert _calibracion_cereales_panes(25) == 0.0
        assert _calibracion_cereales_panes(50) == 0.0
        assert _calibracion_cereales_panes(51) == 0.5
        assert _calibracion_cereales_panes(75) == 0.5
        assert _calibracion_cereales_panes(100) == 0.5
        assert _calibracion_cereales_panes(101) == 1.0
        assert _calibracion_cereales_panes(200) == 1.0
    
    def test_calibracion_frutos_secos_rangos(self):
        """Test de rangos de calibracion frutos secos."""
        assert _calibracion_frutos_secos(0) == 0.0
        assert _calibracion_frutos_secos(10) == 0.0
        assert _calibracion_frutos_secos(20) == 0.0
        assert _calibracion_frutos_secos(21) == 0.5
        assert _calibracion_frutos_secos(30) == 0.5
        assert _calibracion_frutos_secos(40) == 0.5
        assert _calibracion_frutos_secos(41) == 1.0
        assert _calibracion_frutos_secos(60) == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
