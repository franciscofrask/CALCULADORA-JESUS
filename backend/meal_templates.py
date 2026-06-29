"""
Meal Templates — Plantillas de menú para "Elige tu menú"
Método Jesús Gallego — 12en12

60 plantillas: 15 desayuno, 15 comida, 15 merienda, 15 cena
Cada plantilla define: tipo proteína, fuente HC, verduras, grasa de ajuste
Las cantidades se calculan dinámicamente según los macros del usuario.
"""

from typing import Dict, List, Optional
from calma_engine import calcular_macros_efectivos, _redondear_cantidad, parse_categories

# =========================================================
# PLANTILLAS BASE
# =========================================================
# Estructura: cada plantilla es un dict con:
# - id: identificador único
# - nombre: nombre descriptivo del menú
# - momento: "desayuno", "comida", "merienda", "cena"
# - items: lista de alimentos con su rol y búsqueda en BD
#   - rol: "proteina", "hidrato", "verdura", "grasa", "complemento"
#   - buscar: nombre genérico para buscar en BD (campo nombre)
#   - categoria: categoría CALMA preferida
#   - proporcion: qué proporción del macro objetivo cubre este item
#     (para proteínas: 1.0 = todo el P objetivo)
#     (para hidratos: 1.0 = todo el H objetivo)
#     (para grasas: "ajuste" = lo que falte al final)
# - tags: para filtrar (alto_calorico, bajo_calorico, rapido, etc.)
# - min_kcal: kcal mínimas de la comida para que esta plantilla tenga sentido
# - max_kcal: kcal máximas

PLANTILLAS = [
    # ==============================================
    # DESAYUNOS (15)
    # ==============================================
    {
        "id": "D01",
        "nombre": "Tostadas con pavo y aceite",
        "momento": "desayuno",
        "items": [
            {"rol": "proteina", "buscar": "Pechuga de pavo", "categoria": "2.2", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Pan de barra integral", "categoria": "8.2", "proporcion": 1.0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["clasico", "rapido"],
        "min_kcal": 200,
        "max_kcal": 600
    },
    {
        "id": "D02",
        "nombre": "Avena con whey y fruta",
        "momento": "desayuno",
        "items": [
            {"rol": "proteina", "buscar": "Aislado de suero", "categoria": "4.1.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Avena", "categoria": "7.1", "proporcion": 0.7},
            {"rol": "hidrato", "buscar": "Plátano", "categoria": "11.1", "proporcion": 0.3},
            {"rol": "grasa", "buscar": "Almendras", "categoria": "17.2.1", "proporcion": "ajuste"},
        ],
        "tags": ["clasico", "fitness"],
        "min_kcal": 250,
        "max_kcal": 700
    },
    {
        "id": "D03",
        "nombre": "Tortitas de avena con claras",
        "momento": "desayuno",
        "items": [
            {"rol": "proteina", "buscar": "Clara de huevo", "categoria": "1.1", "proporcion": 0.7},
            {"rol": "proteina", "buscar": "Huevo entero", "categoria": "1.2", "proporcion": 0.3},
            {"rol": "hidrato", "buscar": "Harina de avena", "categoria": "7.2.2", "proporcion": 1.0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["clasico", "fitness"],
        "min_kcal": 250,
        "max_kcal": 650
    },
    {
        "id": "D04",
        "nombre": "Yogur griego con cereales y frutos secos",
        "momento": "desayuno",
        "items": [
            {"rol": "proteina", "buscar": "Yogur griego", "categoria": "5.2", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Cereales integrales", "categoria": "7.1.2", "proporcion": 1.0},
            {"rol": "grasa", "buscar": "Nueces", "categoria": "17.2.1", "proporcion": "ajuste"},
        ],
        "tags": ["rapido", "sin_cocinar"],
        "min_kcal": 200,
        "max_kcal": 500
    },
    {
        "id": "D05",
        "nombre": "Tostadas con huevos revueltos",
        "momento": "desayuno",
        "items": [
            {"rol": "proteina", "buscar": "Huevo entero", "categoria": "1.2", "proporcion": 0.4},
            {"rol": "proteina", "buscar": "Clara de huevo", "categoria": "1.1", "proporcion": 0.6},
            {"rol": "hidrato", "buscar": "Pan de molde integral", "categoria": "8.7", "proporcion": 1.0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["clasico"],
        "min_kcal": 250,
        "max_kcal": 600
    },
    {
        "id": "D06",
        "nombre": "Batido de proteínas con avena y plátano",
        "momento": "desayuno",
        "items": [
            {"rol": "proteina", "buscar": "Aislado de suero", "categoria": "4.1.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Avena", "categoria": "7.1", "proporcion": 0.5},
            {"rol": "hidrato", "buscar": "Plátano", "categoria": "11.1", "proporcion": 0.5},
            {"rol": "grasa", "buscar": "Crema de cacahuete", "categoria": "17.2.4", "proporcion": "ajuste"},
        ],
        "tags": ["rapido", "batido"],
        "min_kcal": 300,
        "max_kcal": 700
    },
    {
        "id": "D07",
        "nombre": "Queso batido con fruta y avena",
        "momento": "desayuno",
        "items": [
            {"rol": "proteina", "buscar": "Queso batido 0%", "categoria": "5.2.3", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Avena", "categoria": "7.1", "proporcion": 0.6},
            {"rol": "hidrato", "buscar": "Fresas", "categoria": "11.1", "proporcion": 0.4},
            {"rol": "grasa", "buscar": "Almendras", "categoria": "17.2.1", "proporcion": "ajuste"},
        ],
        "tags": ["rapido", "sin_cocinar"],
        "min_kcal": 200,
        "max_kcal": 550
    },
    {
        "id": "D08",
        "nombre": "Sandwich de atún con aguacate",
        "momento": "desayuno",
        "items": [
            {"rol": "proteina", "buscar": "Atún en conserva", "categoria": "3.8", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Pan de molde integral", "categoria": "8.7", "proporcion": 1.0},
            {"rol": "grasa", "buscar": "Aguacate", "categoria": "17.6", "proporcion": "ajuste"},
        ],
        "tags": ["rapido", "sin_cocinar"],
        "min_kcal": 200,
        "max_kcal": 550
    },
    {
        "id": "D09",
        "nombre": "Porridge de avena con whey",
        "momento": "desayuno",
        "items": [
            {"rol": "proteina", "buscar": "Concentrado de suero", "categoria": "4.1.3", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Avena", "categoria": "7.1", "proporcion": 1.0},
            {"rol": "grasa", "buscar": "Nueces", "categoria": "17.2.1", "proporcion": "ajuste"},
        ],
        "tags": ["clasico", "fitness", "invierno"],
        "min_kcal": 300,
        "max_kcal": 700
    },
    {
        "id": "D10",
        "nombre": "Tostada con jamón serrano y tomate",
        "momento": "desayuno",
        "items": [
            {"rol": "proteina", "buscar": "Jamón serrano", "categoria": "2.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Pan de barra", "categoria": "8.1", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Tomate", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["clasico", "español"],
        "min_kcal": 200,
        "max_kcal": 500
    },
    {
        "id": "D11",
        "nombre": "Bowl de yogur proteico con granola",
        "momento": "desayuno",
        "items": [
            {"rol": "proteina", "buscar": "Yogur proteico", "categoria": "5.2.3", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Cereales", "categoria": "7.1.1", "proporcion": 1.0},
            {"rol": "grasa", "buscar": "Almendras", "categoria": "17.2.1", "proporcion": "ajuste"},
        ],
        "tags": ["rapido", "sin_cocinar"],
        "min_kcal": 200,
        "max_kcal": 500
    },
    {
        "id": "D12",
        "nombre": "Crepes de avena con queso batido",
        "momento": "desayuno",
        "items": [
            {"rol": "proteina", "buscar": "Queso batido 0%", "categoria": "5.2.3", "proporcion": 0.5},
            {"rol": "proteina", "buscar": "Clara de huevo", "categoria": "1.1", "proporcion": 0.5},
            {"rol": "hidrato", "buscar": "Harina de avena", "categoria": "7.2.2", "proporcion": 1.0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["fitness"],
        "min_kcal": 250,
        "max_kcal": 600
    },
    {
        "id": "D13",
        "nombre": "Leche con cereales y whey",
        "momento": "desayuno",
        "items": [
            {"rol": "proteina", "buscar": "Aislado de suero", "categoria": "4.1.1", "proporcion": 0.7},
            {"rol": "hidrato", "buscar": "Cereales integrales", "categoria": "7.1.2", "proporcion": 1.0},
            {"rol": "complemento", "buscar": "Leche desnatada", "categoria": "5.1", "proporcion": 0.3},
        ],
        "tags": ["rapido", "clasico"],
        "min_kcal": 200,
        "max_kcal": 500
    },
    {
        "id": "D14",
        "nombre": "Tostada de pavo con queso fresco",
        "momento": "desayuno",
        "items": [
            {"rol": "proteina", "buscar": "Pechuga de pavo", "categoria": "2.2", "proporcion": 0.7},
            {"rol": "proteina", "buscar": "Queso fresco", "categoria": "5.3", "proporcion": 0.3},
            {"rol": "hidrato", "buscar": "Pan de barra integral", "categoria": "8.2", "proporcion": 1.0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["clasico"],
        "min_kcal": 200,
        "max_kcal": 550
    },
    {
        "id": "D15",
        "nombre": "Gachas de avena con huevo y fruta",
        "momento": "desayuno",
        "items": [
            {"rol": "proteina", "buscar": "Huevo entero", "categoria": "1.2", "proporcion": 0.5},
            {"rol": "proteina", "buscar": "Clara de huevo", "categoria": "1.1", "proporcion": 0.5},
            {"rol": "hidrato", "buscar": "Avena", "categoria": "7.1", "proporcion": 0.7},
            {"rol": "hidrato", "buscar": "Manzana", "categoria": "11.1", "proporcion": 0.3},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["clasico", "invierno"],
        "min_kcal": 300,
        "max_kcal": 700
    },

    # ==============================================
    # COMIDAS / ALMUERZO (15)
    # ==============================================
    {
        "id": "C01",
        "nombre": "Pollo con arroz y ensalada",
        "momento": "comida",
        "items": [
            {"rol": "proteina", "buscar": "Pechuga de pollo", "categoria": "2.2.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Arroz blanco", "categoria": "21.1", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Lechuga", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["clasico", "gym"],
        "min_kcal": 300,
        "max_kcal": 800
    },
    {
        "id": "C02",
        "nombre": "Merluza con patata y brócoli",
        "momento": "comida",
        "items": [
            {"rol": "proteina", "buscar": "Merluza", "categoria": "3.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Patata cocida", "categoria": "9", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Brócoli", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["clasico", "pescado"],
        "min_kcal": 300,
        "max_kcal": 750
    },
    {
        "id": "C03",
        "nombre": "Ternera con pasta y verduras",
        "momento": "comida",
        "items": [
            {"rol": "proteina", "buscar": "Ternera", "categoria": "2.3.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Pasta", "categoria": "22.1.1", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Pimiento", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["clasico"],
        "min_kcal": 350,
        "max_kcal": 900
    },
    {
        "id": "C04",
        "nombre": "Salmón con boniato y espárragos",
        "momento": "comida",
        "items": [
            {"rol": "proteina", "buscar": "Salmón", "categoria": "3.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Boniato", "categoria": "9", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Espárragos", "categoria": "13.1", "proporcion": 0},
        ],
        "tags": ["alto_calorico", "pescado_graso"],
        "min_kcal": 350,
        "max_kcal": 900
    },
    {
        "id": "C05",
        "nombre": "Pollo con quinoa y aguacate",
        "momento": "comida",
        "items": [
            {"rol": "proteina", "buscar": "Pechuga de pollo", "categoria": "2.2.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Quinoa", "categoria": "22.5", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Tomate", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aguacate", "categoria": "17.6", "proporcion": "ajuste"},
        ],
        "tags": ["fitness", "variado"],
        "min_kcal": 300,
        "max_kcal": 800
    },
    {
        "id": "C06",
        "nombre": "Lentejas con arroz y verduras",
        "momento": "comida",
        "items": [
            {"rol": "proteina", "buscar": "Lentejas cocidas", "categoria": "10.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Arroz blanco", "categoria": "21.1", "proporcion": 0.5},
            {"rol": "verdura", "buscar": "Zanahoria", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["clasico", "español", "legumbres"],
        "min_kcal": 350,
        "max_kcal": 900
    },
    {
        "id": "C07",
        "nombre": "Pavo con arroz integral y ensalada",
        "momento": "comida",
        "items": [
            {"rol": "proteina", "buscar": "Pechuga de pavo", "categoria": "2.2.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Arroz integral", "categoria": "21.1", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Lechuga", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["clasico", "gym"],
        "min_kcal": 300,
        "max_kcal": 800
    },
    {
        "id": "C08",
        "nombre": "Gambas con pasta y tomate",
        "momento": "comida",
        "items": [
            {"rol": "proteina", "buscar": "Gambas", "categoria": "3.9.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Pasta", "categoria": "22.1.1", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Tomate triturado", "categoria": "13.8", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["pescado", "italiano"],
        "min_kcal": 300,
        "max_kcal": 800
    },
    {
        "id": "C09",
        "nombre": "Pollo con patata y judías verdes",
        "momento": "comida",
        "items": [
            {"rol": "proteina", "buscar": "Pechuga de pollo", "categoria": "2.2.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Patata cocida", "categoria": "9", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Judías verdes", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["clasico", "español"],
        "min_kcal": 300,
        "max_kcal": 800
    },
    {
        "id": "C10",
        "nombre": "Atún con arroz y ensalada",
        "momento": "comida",
        "items": [
            {"rol": "proteina", "buscar": "Atún en conserva", "categoria": "3.8", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Arroz blanco", "categoria": "21.1", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Lechuga", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["rapido", "conserva"],
        "min_kcal": 300,
        "max_kcal": 750
    },
    {
        "id": "C11",
        "nombre": "Huevos con arroz y aguacate",
        "momento": "comida",
        "items": [
            {"rol": "proteina", "buscar": "Huevo entero", "categoria": "1.2", "proporcion": 0.4},
            {"rol": "proteina", "buscar": "Clara de huevo", "categoria": "1.1", "proporcion": 0.6},
            {"rol": "hidrato", "buscar": "Arroz blanco", "categoria": "21.1", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Tomate", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aguacate", "categoria": "17.6", "proporcion": "ajuste"},
        ],
        "tags": ["clasico", "economico"],
        "min_kcal": 300,
        "max_kcal": 800
    },
    {
        "id": "C12",
        "nombre": "Cerdo con boniato y brócoli",
        "momento": "comida",
        "items": [
            {"rol": "proteina", "buscar": "Lomo de cerdo", "categoria": "2.4.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Boniato", "categoria": "9", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Brócoli", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["variado"],
        "min_kcal": 350,
        "max_kcal": 850
    },
    {
        "id": "C13",
        "nombre": "Garbanzos con pollo y espinacas",
        "momento": "comida",
        "items": [
            {"rol": "proteina", "buscar": "Pechuga de pollo", "categoria": "2.2.1", "proporcion": 0.6},
            {"rol": "proteina", "buscar": "Garbanzos cocidos", "categoria": "10.1", "proporcion": 0.4},
            {"rol": "verdura", "buscar": "Espinacas", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["legumbres", "español"],
        "min_kcal": 350,
        "max_kcal": 850
    },
    {
        "id": "C14",
        "nombre": "Lubina con patata y ensalada",
        "momento": "comida",
        "items": [
            {"rol": "proteina", "buscar": "Lubina", "categoria": "3.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Patata cocida", "categoria": "9", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Lechuga", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["pescado", "clasico"],
        "min_kcal": 300,
        "max_kcal": 750
    },
    {
        "id": "C15",
        "nombre": "Pollo con cous cous y verduras",
        "momento": "comida",
        "items": [
            {"rol": "proteina", "buscar": "Pechuga de pollo", "categoria": "2.2.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Cous cous", "categoria": "22.4", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Calabacín", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["variado"],
        "min_kcal": 300,
        "max_kcal": 800
    },

    # ==============================================
    # MERIENDAS (15)
    # ==============================================
    {
        "id": "M01",
        "nombre": "Batido de proteínas con fruta",
        "momento": "merienda",
        "items": [
            {"rol": "proteina", "buscar": "Aislado de suero", "categoria": "4.1.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Plátano", "categoria": "11.1", "proporcion": 1.0},
            {"rol": "grasa", "buscar": "Almendras", "categoria": "17.2.1", "proporcion": "ajuste"},
        ],
        "tags": ["rapido", "batido"],
        "min_kcal": 200,
        "max_kcal": 500
    },
    {
        "id": "M02",
        "nombre": "Yogur con frutos secos y fruta",
        "momento": "merienda",
        "items": [
            {"rol": "proteina", "buscar": "Yogur griego", "categoria": "5.2", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Manzana", "categoria": "11.1", "proporcion": 1.0},
            {"rol": "grasa", "buscar": "Nueces", "categoria": "17.2.1", "proporcion": "ajuste"},
        ],
        "tags": ["rapido", "sin_cocinar"],
        "min_kcal": 200,
        "max_kcal": 500
    },
    {
        "id": "M03",
        "nombre": "Tostada con pavo y queso fresco",
        "momento": "merienda",
        "items": [
            {"rol": "proteina", "buscar": "Pechuga de pavo", "categoria": "2.2", "proporcion": 0.7},
            {"rol": "proteina", "buscar": "Queso fresco", "categoria": "5.3", "proporcion": 0.3},
            {"rol": "hidrato", "buscar": "Pan de molde integral", "categoria": "8.7", "proporcion": 1.0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["rapido"],
        "min_kcal": 200,
        "max_kcal": 500
    },
    {
        "id": "M04",
        "nombre": "Queso batido con avena y fruta",
        "momento": "merienda",
        "items": [
            {"rol": "proteina", "buscar": "Queso batido 0%", "categoria": "5.2.3", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Avena", "categoria": "7.1", "proporcion": 0.6},
            {"rol": "hidrato", "buscar": "Fresas", "categoria": "11.1", "proporcion": 0.4},
            {"rol": "grasa", "buscar": "Crema de cacahuete", "categoria": "17.2.4", "proporcion": "ajuste"},
        ],
        "tags": ["fitness", "sin_cocinar"],
        "min_kcal": 200,
        "max_kcal": 550
    },
    {
        "id": "M05",
        "nombre": "Sandwich de atún",
        "momento": "merienda",
        "items": [
            {"rol": "proteina", "buscar": "Atún en conserva", "categoria": "3.8", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Pan de molde integral", "categoria": "8.7", "proporcion": 1.0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["rapido", "sin_cocinar"],
        "min_kcal": 200,
        "max_kcal": 500
    },
    {
        "id": "M06",
        "nombre": "Tortitas de arroz con pavo y aguacate",
        "momento": "merienda",
        "items": [
            {"rol": "proteina", "buscar": "Pechuga de pavo", "categoria": "2.2", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Tortas de arroz", "categoria": "21.2", "proporcion": 1.0},
            {"rol": "grasa", "buscar": "Aguacate", "categoria": "17.6", "proporcion": "ajuste"},
        ],
        "tags": ["rapido", "sin_cocinar"],
        "min_kcal": 150,
        "max_kcal": 450
    },
    {
        "id": "M07",
        "nombre": "Batido de caseína con avena",
        "momento": "merienda",
        "items": [
            {"rol": "proteina", "buscar": "Caseína", "categoria": "4.2", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Avena", "categoria": "7.1", "proporcion": 1.0},
            {"rol": "grasa", "buscar": "Almendras", "categoria": "17.2.1", "proporcion": "ajuste"},
        ],
        "tags": ["fitness", "batido"],
        "min_kcal": 250,
        "max_kcal": 600
    },
    {
        "id": "M08",
        "nombre": "Huevos cocidos con pan y tomate",
        "momento": "merienda",
        "items": [
            {"rol": "proteina", "buscar": "Huevo entero", "categoria": "1.2", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Pan de barra", "categoria": "8.1", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Tomate", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["clasico", "español"],
        "min_kcal": 200,
        "max_kcal": 500
    },
    {
        "id": "M09",
        "nombre": "Yogur proteico con cereales",
        "momento": "merienda",
        "items": [
            {"rol": "proteina", "buscar": "Yogur proteico", "categoria": "5.2.3", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Cereales integrales", "categoria": "7.1.2", "proporcion": 1.0},
            {"rol": "grasa", "buscar": "Nueces", "categoria": "17.2.1", "proporcion": "ajuste"},
        ],
        "tags": ["rapido", "sin_cocinar"],
        "min_kcal": 200,
        "max_kcal": 500
    },
    {
        "id": "M10",
        "nombre": "Batido de proteínas con crema de cacahuete",
        "momento": "merienda",
        "items": [
            {"rol": "proteina", "buscar": "Aislado de suero", "categoria": "4.1.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Plátano", "categoria": "11.1", "proporcion": 1.0},
            {"rol": "grasa", "buscar": "Crema de cacahuete", "categoria": "17.2.4", "proporcion": "ajuste"},
        ],
        "tags": ["rapido", "batido", "alto_calorico"],
        "min_kcal": 300,
        "max_kcal": 700
    },
    {
        "id": "M11",
        "nombre": "Tostada con salmón ahumado y queso",
        "momento": "merienda",
        "items": [
            {"rol": "proteina", "buscar": "Salmón ahumado", "categoria": "3.7", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Pan de molde integral", "categoria": "8.7", "proporcion": 1.0},
            {"rol": "proteina", "buscar": "Queso fresco", "categoria": "5.3", "proporcion": 0.2},
        ],
        "tags": ["gourmet"],
        "min_kcal": 200,
        "max_kcal": 500
    },
    {
        "id": "M12",
        "nombre": "Queso batido con frutos secos",
        "momento": "merienda",
        "items": [
            {"rol": "proteina", "buscar": "Queso batido 0%", "categoria": "5.2.3", "proporcion": 1.0},
            {"rol": "grasa", "buscar": "Almendras", "categoria": "17.2.1", "proporcion": "ajuste"},
        ],
        "tags": ["rapido", "sin_cocinar", "bajo_calorico"],
        "min_kcal": 100,
        "max_kcal": 350
    },
    {
        "id": "M13",
        "nombre": "Wrap de pollo con lechuga",
        "momento": "merienda",
        "items": [
            {"rol": "proteina", "buscar": "Pechuga de pollo", "categoria": "2.2", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Tortilla de trigo", "categoria": "8.5", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Lechuga", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["rapido"],
        "min_kcal": 200,
        "max_kcal": 550
    },
    {
        "id": "M14",
        "nombre": "Leche con cacao y avena",
        "momento": "merienda",
        "items": [
            {"rol": "proteina", "buscar": "Leche desnatada", "categoria": "5.1", "proporcion": 0.5},
            {"rol": "proteina", "buscar": "Concentrado de suero", "categoria": "4.1.3", "proporcion": 0.5},
            {"rol": "hidrato", "buscar": "Avena", "categoria": "7.1", "proporcion": 1.0},
            {"rol": "complemento", "buscar": "Cacao en polvo", "categoria": "37", "proporcion": 0},
        ],
        "tags": ["clasico", "invierno"],
        "min_kcal": 250,
        "max_kcal": 600
    },
    {
        "id": "M15",
        "nombre": "Fruta con yogur y semillas",
        "momento": "merienda",
        "items": [
            {"rol": "proteina", "buscar": "Yogur griego", "categoria": "5.2", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Plátano", "categoria": "11.1", "proporcion": 0.5},
            {"rol": "hidrato", "buscar": "Fresas", "categoria": "11.1", "proporcion": 0.5},
            {"rol": "grasa", "buscar": "Semillas de chía", "categoria": "17.2.3", "proporcion": "ajuste"},
        ],
        "tags": ["rapido", "sin_cocinar"],
        "min_kcal": 200,
        "max_kcal": 500
    },

    # ==============================================
    # CENAS (15)
    # ==============================================
    {
        "id": "N01",
        "nombre": "Pollo a la plancha con ensalada y arroz",
        "momento": "cena",
        "items": [
            {"rol": "proteina", "buscar": "Pechuga de pollo", "categoria": "2.2.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Arroz blanco", "categoria": "21.1", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Lechuga", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["clasico", "gym"],
        "min_kcal": 300,
        "max_kcal": 750
    },
    {
        "id": "N02",
        "nombre": "Merluza al horno con patata",
        "momento": "cena",
        "items": [
            {"rol": "proteina", "buscar": "Merluza", "categoria": "3.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Patata cocida", "categoria": "9", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Espárragos", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["clasico", "pescado"],
        "min_kcal": 300,
        "max_kcal": 700
    },
    {
        "id": "N03",
        "nombre": "Tortilla francesa con pan",
        "momento": "cena",
        "items": [
            {"rol": "proteina", "buscar": "Huevo entero", "categoria": "1.2", "proporcion": 0.4},
            {"rol": "proteina", "buscar": "Clara de huevo", "categoria": "1.1", "proporcion": 0.6},
            {"rol": "hidrato", "buscar": "Pan de barra", "categoria": "8.1", "proporcion": 1.0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["clasico", "rapido", "español"],
        "min_kcal": 250,
        "max_kcal": 650
    },
    {
        "id": "N04",
        "nombre": "Pavo con boniato y verduras al vapor",
        "momento": "cena",
        "items": [
            {"rol": "proteina", "buscar": "Pechuga de pavo", "categoria": "2.2.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Boniato", "categoria": "9", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Brócoli", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["clasico", "saludable"],
        "min_kcal": 300,
        "max_kcal": 750
    },
    {
        "id": "N05",
        "nombre": "Salmón con arroz y ensalada",
        "momento": "cena",
        "items": [
            {"rol": "proteina", "buscar": "Salmón", "categoria": "3.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Arroz blanco", "categoria": "21.1", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Lechuga", "categoria": "13.1", "proporcion": 0},
        ],
        "tags": ["pescado_graso", "alto_calorico"],
        "min_kcal": 350,
        "max_kcal": 800
    },
    {
        "id": "N06",
        "nombre": "Revuelto de gambas con verduras y arroz",
        "momento": "cena",
        "items": [
            {"rol": "proteina", "buscar": "Gambas", "categoria": "3.9.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Arroz blanco", "categoria": "21.1", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Pimiento", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["variado", "marisco"],
        "min_kcal": 300,
        "max_kcal": 700
    },
    {
        "id": "N07",
        "nombre": "Pollo con pasta integral y verduras",
        "momento": "cena",
        "items": [
            {"rol": "proteina", "buscar": "Pechuga de pollo", "categoria": "2.2.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Pasta integral", "categoria": "22.1.1", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Calabacín", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["clasico"],
        "min_kcal": 350,
        "max_kcal": 800
    },
    {
        "id": "N08",
        "nombre": "Atún con patata y ensalada",
        "momento": "cena",
        "items": [
            {"rol": "proteina", "buscar": "Atún en conserva", "categoria": "3.8", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Patata cocida", "categoria": "9", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Lechuga", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["rapido", "conserva"],
        "min_kcal": 250,
        "max_kcal": 700
    },
    {
        "id": "N09",
        "nombre": "Ternera con arroz y brócoli",
        "momento": "cena",
        "items": [
            {"rol": "proteina", "buscar": "Ternera", "categoria": "2.3.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Arroz blanco", "categoria": "21.1", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Brócoli", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["clasico", "gym"],
        "min_kcal": 350,
        "max_kcal": 850
    },
    {
        "id": "N10",
        "nombre": "Lentejas con verduras",
        "momento": "cena",
        "items": [
            {"rol": "proteina", "buscar": "Lentejas cocidas", "categoria": "10.1", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Zanahoria", "categoria": "13.1", "proporcion": 0},
            {"rol": "verdura", "buscar": "Espinacas", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["legumbres", "español"],
        "min_kcal": 300,
        "max_kcal": 700
    },
    {
        "id": "N11",
        "nombre": "Dorada con patata y judías verdes",
        "momento": "cena",
        "items": [
            {"rol": "proteina", "buscar": "Dorada", "categoria": "3.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Patata cocida", "categoria": "9", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Judías verdes", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["pescado", "clasico"],
        "min_kcal": 300,
        "max_kcal": 700
    },
    {
        "id": "N12",
        "nombre": "Huevos revueltos con pan y tomate",
        "momento": "cena",
        "items": [
            {"rol": "proteina", "buscar": "Huevo entero", "categoria": "1.2", "proporcion": 0.4},
            {"rol": "proteina", "buscar": "Clara de huevo", "categoria": "1.1", "proporcion": 0.6},
            {"rol": "hidrato", "buscar": "Pan de barra integral", "categoria": "8.2", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Tomate", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["clasico", "rapido"],
        "min_kcal": 250,
        "max_kcal": 650
    },
    {
        "id": "N13",
        "nombre": "Pollo con cous cous y ensalada",
        "momento": "cena",
        "items": [
            {"rol": "proteina", "buscar": "Pechuga de pollo", "categoria": "2.2.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Cous cous", "categoria": "22.4", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Tomate", "categoria": "13.1", "proporcion": 0},
            {"rol": "verdura", "buscar": "Pepino", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["variado"],
        "min_kcal": 300,
        "max_kcal": 750
    },
    {
        "id": "N14",
        "nombre": "Cerdo con arroz y espárragos",
        "momento": "cena",
        "items": [
            {"rol": "proteina", "buscar": "Lomo de cerdo", "categoria": "2.4.1", "proporcion": 1.0},
            {"rol": "hidrato", "buscar": "Arroz blanco", "categoria": "21.1", "proporcion": 1.0},
            {"rol": "verdura", "buscar": "Espárragos", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["variado"],
        "min_kcal": 350,
        "max_kcal": 800
    },
    {
        "id": "N15",
        "nombre": "Garbanzos con bacalao y espinacas",
        "momento": "cena",
        "items": [
            {"rol": "proteina", "buscar": "Bacalao", "categoria": "3.1", "proporcion": 0.6},
            {"rol": "proteina", "buscar": "Garbanzos cocidos", "categoria": "10.1", "proporcion": 0.4},
            {"rol": "verdura", "buscar": "Espinacas", "categoria": "13.1", "proporcion": 0},
            {"rol": "grasa", "buscar": "Aceite de oliva virgen", "categoria": "17.1.1", "proporcion": "ajuste"},
        ],
        "tags": ["legumbres", "pescado"],
        "min_kcal": 350,
        "max_kcal": 800
    },
]


# =========================================================
# FUNCIÓN: Generar 3 opciones A/B/C para una comida
# =========================================================

def _item_avoided_precheck(item: dict, avoided_prefixes: set, avoided_keywords: list) -> bool:
    """Pre-chequeo barato sobre el item del template (sin tocar BD)."""
    buscar = (item.get("buscar", "") or "").lower()
    for kw in (avoided_keywords or []):
        if kw in buscar:
            return True
    cat = str(item.get("categoria", ""))
    for p in (avoided_prefixes or set()):
        if cat == p or cat.startswith(p + "."):
            return True
    return False


async def generar_opciones_menu(
    db,
    momento: str,
    macros_objetivo: Dict[str, float],
    es_vegano: bool = False,
    excluir_proteinas: list = None,
    avoided_prefixes: set = None,
    avoided_keywords: list = None,
) -> List[Dict]:
    """
    Genera hasta 3 opciones de menú (A, B, C) autoajustadas para un momento.

    REGLAS:
    1. Las 3 opciones usan PROTEÍNAS DIFERENTES
    2. Las cantidades se autoajustan (mínimo + escalar) a los macros exactos
    3. Solo se devuelven menús CUADRADOS donde TODOS los alimentos entran
    4. Se descartan menús con alimentos evitados por el usuario
    """
    avoided_prefixes = avoided_prefixes or set()
    avoided_keywords = avoided_keywords or []

    p_obj = float(macros_objetivo.get("P", macros_objetivo.get("proteina", 0)) or 0)
    h_obj = float(macros_objetivo.get("H", macros_objetivo.get("hidratos", 0)) or 0)
    g_obj = float(macros_objetivo.get("G", macros_objetivo.get("grasa", 0)) or 0)
    kcal_obj = p_obj * 4 + h_obj * 4 + g_obj * 9

    excluir = set(excluir_proteinas or [])

    # Filtrar plantillas por momento y rango de kcal
    candidatas = [
        p for p in PLANTILLAS
        if p["momento"] == momento
        and p["min_kcal"] <= kcal_obj <= p["max_kcal"]
    ]

    if not candidatas:
        # Si no hay en rango, usar todas del momento
        candidatas = [p for p in PLANTILLAS if p["momento"] == momento]

    # Descartar plantillas con algún item evitado (pre-chequeo barato)
    if avoided_prefixes or avoided_keywords:
        candidatas = [
            p for p in candidatas
            if not any(_item_avoided_precheck(it, avoided_prefixes, avoided_keywords) for it in p["items"])
        ]

    # Priorizar: si alto calórico, preferir plantillas con tag alto_calorico
    if kcal_obj > 600:
        candidatas.sort(key=lambda p: ("alto_calorico" in p.get("tags", [])), reverse=True)

    # Seleccionar hasta 3 con proteínas diferentes; solo menús cuadrados
    opciones = []
    proteinas_usadas = set()

    for plantilla in candidatas:
        if len(opciones) >= 3:
            break

        # Proteína principal de esta plantilla (2 niveles: 2.2 aves / 2.3 vacuno /
        # 3.1 pescado / 10.1 legumbre... → más variedad que solo "2")
        prot_principal = None
        for item in plantilla["items"]:
            if item["rol"] == "proteina":
                prot_principal = ".".join(item["categoria"].split(".")[:2])
                break

        if prot_principal in proteinas_usadas:
            continue
        if prot_principal in excluir:
            continue

        opcion = await _ajustar_plantilla(
            db, plantilla, macros_objetivo, es_vegano,
            avoided_prefixes, avoided_keywords,
        )

        if opcion:  # _ajustar_plantilla solo devuelve menús cuadrados con todo dentro
            opciones.append(opcion)
            proteinas_usadas.add(prot_principal)

    # Etiquetar A, B, C
    letras = ["A", "B", "C"]
    for i, opcion in enumerate(opciones):
        opcion["letra"] = letras[i] if i < 3 else f"D{i-2}"

    return opciones[:3]


def _food_avoided(alimento: dict, avoided_prefixes: set, avoided_keywords: list) -> bool:
    """True si el alimento debe evitarse por keyword (en el nombre) o por categoría."""
    nombre = (alimento.get("nombre", "") or "").lower()
    for kw in (avoided_keywords or []):
        if kw in nombre:
            return True
    if not avoided_prefixes:
        return False
    for c in parse_categories(alimento.get("categorias", [])):
        for p in avoided_prefixes:
            if c == p or c.startswith(p + "."):
                return True
    return False


MARGEN_MENU = 4.0  # ±4 g por macro para considerar el menú "cuadrado"


def _driver_macro(rol: str) -> Optional[str]:
    """Macro que ESE alimento escala según su rol en el menú."""
    return {"proteina": "P", "hidrato": "H", "grasa": "G"}.get(rol)


def _menu_max(rol: str, cat: str, maximo_base: float) -> float:
    """Tope superior generoso para el autoajuste de menús (el alimento de ajuste
    debe poder crecer; los topes del chatbot son demasiado estrictos aquí)."""
    if cat.startswith("17.1") or cat.startswith("42"):   # aceites / grasas buenas
        return 30.0
    if cat.startswith("17"):                             # frutos secos, aguacate, cremas
        return 60.0
    return max(maximo_base, 60.0)


async def _ajustar_plantilla(
    db,
    plantilla: dict,
    macros_objetivo: Dict[str, float],
    es_vegano: bool = False,
    avoided_prefixes: set = None,
    avoided_keywords: list = None,
) -> Optional[Dict]:
    """
    Autoajuste de una plantilla a los macros de la comida.

    Criterio: TODOS los alimentos del menú tienen que entrar. Se parte de la
    cantidad MÍNIMA de cada alimento y se escalan las cantidades hasta cuadrar
    P/H/G (±MARGEN). Si algún alimento no se puede sourcear, está evitado, o el
    menú no cuadra (a mínimos ya se pasa, o no se llega) -> se descarta (None).
    """
    from meal_builder import get_effective_macros_per_100g, get_food_limits
    from calculator import get_food_config

    avoided_prefixes = avoided_prefixes or set()
    avoided_keywords = avoided_keywords or []

    obj = {
        "P": float(macros_objetivo.get("P", macros_objetivo.get("proteina", 0)) or 0),
        "H": float(macros_objetivo.get("H", macros_objetivo.get("hidratos", 0)) or 0),
        "G": float(macros_objetivo.get("G", macros_objetivo.get("grasa", 0)) or 0),
    }

    # Paso 1: resolver TODOS los alimentos por categoría (gate: todos deben existir)
    foods = []
    for item in plantilla["items"]:
        alimento = await _buscar_alimento_generico(db, item["buscar"], item["categoria"])
        if not alimento:
            return None
        if _food_avoided(alimento, avoided_prefixes, avoided_keywords):
            return None
        cfg = get_food_config(alimento)
        ef = get_effective_macros_per_100g(alimento)  # {P,H,G,cat,...} efectivos por 100g
        minimo = float(cfg.get("minimo", 5) or 5)
        _, maximo_base = get_food_limits(alimento, cfg)
        maximo = _menu_max(item["rol"], ef.get("cat", ""), maximo_base)
        foods.append({
            "item": item, "alimento": alimento, "ef": ef, "cat": ef.get("cat", ""),
            "minimo": minimo, "maximo": max(minimo, maximo),
            "driver": _driver_macro(item["rol"]), "cantidad": minimo,
        })

    def totales():
        T = {"P": 0.0, "H": 0.0, "G": 0.0}
        for f in foods:
            fac = f["cantidad"] / 100.0
            T["P"] += f["ef"]["P"] * fac
            T["H"] += f["ef"]["H"] * fac
            T["G"] += f["ef"]["G"] * fac
        return T

    # Paso 2: gate de overshoot a mínimos (solo se puede escalar hacia arriba)
    T = totales()
    for m in ("P", "H", "G"):
        if T[m] > obj[m] + MARGEN_MENU:
            return None

    # Paso 3: escalar cada macro con sus alimentos motor (grasa al final: absorbe
    # la grasa incidental de proteínas)
    for m in ("H", "P", "G"):
        drivers = [f for f in foods if f["driver"] == m and f["ef"][m] > 1e-6]
        if not drivers:
            continue
        T = totales()
        needed = obj[m] - T[m]
        if needed <= 0:
            continue
        per = needed / len(drivers)
        for f in drivers:
            extra_g = per / (f["ef"][m] / 100.0)
            nueva = min(f["maximo"], f["cantidad"] + extra_g)
            nueva = _redondear_cantidad(nueva, f["cat"])
            if nueva < f["minimo"]:
                nueva = f["minimo"]
            f["cantidad"] = nueva

    # Paso 4: validar cuadrado
    T = totales()
    if any(abs(T[m] - obj[m]) > MARGEN_MENU for m in ("P", "H", "G")):
        return None

    # Paso 5: construir items en la forma que consume el front
    items_resultado = []
    for f in foods:
        fac = f["cantidad"] / 100.0
        items_resultado.append({
            "alimento_id": f["alimento"].get("id"),
            "nombre": f["alimento"].get("nombre", f["item"]["buscar"]),
            "cantidad_g": f["cantidad"],
            "macros_efectivos": {
                "P": round(f["ef"]["P"] * fac, 1),
                "H": round(f["ef"]["H"] * fac, 1),
                "G": round(f["ef"]["G"] * fac, 1),
            },
            "rol": f["item"]["rol"],
        })

    return {
        "plantilla_id": plantilla["id"],
        "nombre": plantilla["nombre"],
        "items": items_resultado,
        "macros_totales": {
            "P": round(T["P"], 1),
            "H": round(T["H"], 1),
            "G": round(T["G"], 1),
            "kcal": round(T["P"] * 4 + T["H"] * 4 + T["G"] * 9, 1),
        },
        "macros_objetivo": obj,
        "cuadrada": True,
        "tags": plantilla.get("tags", []),
    }


async def _buscar_alimento_generico(db, nombre: str, categoria: str) -> Optional[dict]:
    """
    Busca un alimento genérico en MongoDB por nombre y categoría.
    Prioriza: 1) coincidencia exacta de categoría + nombre
              2) categoría padre + nombre
              3) solo nombre
    Prefiere alimentos con tag GEN (genérico).
    """
    import re
    
    # Intentar búsqueda por categoría exacta + nombre
    filtro = {
        "nombre": {"$regex": re.escape(nombre), "$options": "i"},
        "$or": [
            {"categorias": {"$regex": f"(^|\\|)\\s*{re.escape(categoria)}", "$options": "i"}},
            {"categorias": categoria}
        ]
    }
    
    resultados = await db.foods.find(filtro, {"_id": 0}).limit(20).to_list(20)
    
    if not resultados:
        # Solo por nombre
        filtro = {"nombre": {"$regex": re.escape(nombre), "$options": "i"}}
        resultados = await db.foods.find(filtro, {"_id": 0}).limit(20).to_list(20)
    
    if not resultados:
        return None
    
    # Priorizar genéricos (tag GEN)
    for r in resultados:
        tags = r.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        if "GEN" in tags:
            return r
    
    # Si no hay genérico, devolver el primero
    return resultados[0]


# =========================================================
# TESTS
# =========================================================

def run_tests():
    tests = []
    
    def test(nombre, condicion, detalle=""):
        tests.append({"nombre": nombre, "passed": condicion, "detalle": detalle})
    
    # Test plantillas
    test("60 plantillas definidas", len(PLANTILLAS) == 60, f"tiene {len(PLANTILLAS)}")
    
    desayunos = [p for p in PLANTILLAS if p["momento"] == "desayuno"]
    comidas = [p for p in PLANTILLAS if p["momento"] == "comida"]
    meriendas = [p for p in PLANTILLAS if p["momento"] == "merienda"]
    cenas = [p for p in PLANTILLAS if p["momento"] == "cena"]
    
    test("15 desayunos", len(desayunos) == 15, f"tiene {len(desayunos)}")
    test("15 comidas", len(comidas) == 15, f"tiene {len(comidas)}")
    test("15 meriendas", len(meriendas) == 15, f"tiene {len(meriendas)}")
    test("15 cenas", len(cenas) == 15, f"tiene {len(cenas)}")
    
    # Verificar que cada plantilla tiene al menos 1 proteína
    for p in PLANTILLAS:
        tiene_prot = any(i["rol"] == "proteina" for i in p["items"])
        test(f"{p['id']} tiene proteína", tiene_prot, p["nombre"])
    
    # Verificar IDs únicos
    ids = [p["id"] for p in PLANTILLAS]
    test("IDs únicos", len(ids) == len(set(ids)), f"duplicados: {len(ids) - len(set(ids))}")
    
    # Verificar variedad de proteínas por momento
    for momento in ["desayuno", "comida", "merienda", "cena"]:
        cats_prot = set()
        for p in PLANTILLAS:
            if p["momento"] == momento:
                for item in p["items"]:
                    if item["rol"] == "proteina":
                        cats_prot.add(item["categoria"].split(".")[0])
        test(
            f"{momento}: variedad proteínas >= 3 tipos",
            len(cats_prot) >= 3,
            f"tipos: {cats_prot}"
        )
    
    total = len(tests)
    passed = sum(1 for t in tests if t["passed"])
    
    return {
        "total": total,
        "passed": passed,
        "failed_count": total - passed,
        "all_passed": passed == total,
        "tests": tests,
        "failed_tests": [t for t in tests if not t["passed"]]
    }
