"""
CAPA DE TARGETS — Motor de cálculo de macros objetivo del cliente
================================================================
Dado (peso, sexo, %graso, objetivo), devuelve los macros objetivo
para los tres tipos de día: entrenamiento, perientreno y descanso.

Basado en las tablas del Excel de Jesús Gallego (macros_tables.json).
Las tablas son discretas (no fórmulas continuas). Para valores intermedios
se redondea al escalón más cercano. Para valores fuera de rango se usa el extremo.

Fórmulas de derivación:
    masa_grasa  = peso * (porcentaje_graso / 100)
    masa_magra  = peso - masa_grasa
    masa_trabajo = masa_magra / (1 - porcentaje_trabajo / 100)

Con porcentaje_trabajo=15 (default): masa_trabajo = masa_magra / 0.85

Fuente: SPEC_Capa_Targets_CALMA.md + macros_tables.json
"""

import json
import os
from typing import Dict, Optional, Tuple

# =========================================================
# CARGAR TABLAS AL INICIAR EL MÓDULO
# =========================================================

_TABLES_PATH = os.path.join(os.path.dirname(__file__), "macros_tables.json")

_TABLE_HOMBRE = []
_TABLE_MUJER = []
_INDEX = {}  # (sexo, peso, bf, obj) -> registro

# Escalones válidos
PESOS_HOMBRE = [60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110, 115, 120]
PESOS_MUJER = [50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110, 115]
BFS_HOMBRE = [10, 15, 20, 25, 30, 35, 40, 45]
BFS_MUJER = [20, 25, 30, 35, 40, 45, 50]


def _load_tables():
    """Carga las tablas desde el JSON y construye el índice."""
    global _TABLE_HOMBRE, _TABLE_MUJER, _INDEX

    if not os.path.exists(_TABLES_PATH):
        raise FileNotFoundError(f"No se encontró {_TABLES_PATH}")

    with open(_TABLES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    _TABLE_HOMBRE = data.get("hombre", [])
    _TABLE_MUJER = data.get("mujer", [])

    for r in _TABLE_HOMBRE:
        obj_norm = _normalize_obj(r["obj"])
        key = ("hombre", float(r["peso"]), float(r["bf"]), obj_norm)
        _INDEX[key] = r

    for r in _TABLE_MUJER:
        obj_norm = _normalize_obj(r["obj"])
        key = ("mujer", float(r["peso"]), float(r["bf"]), obj_norm)
        _INDEX[key] = r


def _normalize_obj(obj: str) -> str:
    """Normaliza el objetivo: quita tildes, lowercase."""
    obj = obj.strip().lower()
    obj = obj.replace("ó", "o").replace("í", "i")
    if obj in ("volumen", "vol"):
        return "volumen"
    if obj in ("definicion", "definición", "def", "defi"):
        return "definicion"
    return obj


def _snap_to_nearest(value: float, steps: list) -> float:
    """Redondea al escalón más cercano. Si fuera de rango, clamp al extremo."""
    if value <= steps[0]:
        return float(steps[0])
    if value >= steps[-1]:
        return float(steps[-1])
    closest = min(steps, key=lambda s: abs(s - value))
    return float(closest)


# =========================================================
# FUNCIONES PÚBLICAS
# =========================================================

def calcular_masa_trabajo(
    peso: float,
    porcentaje_graso: float,
    porcentaje_trabajo: float = 15.0
) -> Dict[str, float]:
    """
    Calcula masa_grasa, masa_magra y masa_trabajo.

    Returns:
        {"masa_grasa": X, "masa_magra": Y, "masa_trabajo": Z}
    """
    masa_grasa = peso * (porcentaje_graso / 100.0)
    masa_magra = peso - masa_grasa
    divisor = 1.0 - (porcentaje_trabajo / 100.0)
    masa_trabajo = masa_magra / divisor if divisor > 0 else masa_magra

    return {
        "masa_grasa": round(masa_grasa, 2),
        "masa_magra": round(masa_magra, 2),
        "masa_trabajo": round(masa_trabajo, 2),
    }


def calcular_targets(
    peso: float,
    sexo: str,
    porcentaje_graso: float,
    objetivo: str,
    porcentaje_trabajo: float = 15.0
) -> Dict:
    """
    Función principal: dado un cliente, devuelve sus macros objetivo.

    Args:
        peso: kg
        sexo: "hombre" o "mujer"
        porcentaje_graso: % grasa corporal
        objetivo: "volumen" o "definicion"/"definición"
        porcentaje_trabajo: corrección (default 15)

    Returns:
        {
            "input": {peso, sexo, porcentaje_graso, objetivo},
            "derivacion": {masa_grasa, masa_magra, masa_trabajo},
            "lookup": {peso_snap, bf_snap},
            "macros": {
                "entreno": {"proteina": X, "hidratos": Y, "grasa": Z},
                "perientreno": {"proteina": X, "hidratos": Y},
                "descanso": {"proteina": X, "hidratos": Y, "grasa": Z}
            },
            "multiplicadores": {...}  // Para override del coach
        }
    """
    if not _INDEX:
        _load_tables()

    sexo_norm = sexo.strip().lower()
    if sexo_norm not in ("hombre", "mujer"):
        raise ValueError(f"Sexo no válido: {sexo}. Usa 'hombre' o 'mujer'.")

    obj_norm = _normalize_obj(objetivo)
    if obj_norm not in ("volumen", "definicion"):
        raise ValueError(f"Objetivo no válido: {objetivo}. Usa 'volumen' o 'definicion'.")

    # Snap peso y bf al escalón más cercano
    if sexo_norm == "hombre":
        peso_snap = _snap_to_nearest(peso, PESOS_HOMBRE)
        bf_snap = _snap_to_nearest(porcentaje_graso, BFS_HOMBRE)
    else:
        peso_snap = _snap_to_nearest(peso, PESOS_MUJER)
        bf_snap = _snap_to_nearest(porcentaje_graso, BFS_MUJER)

    # Lookup
    key = (sexo_norm, peso_snap, bf_snap, obj_norm)
    registro = _INDEX.get(key)

    if not registro:
        raise ValueError(
            f"No se encontró registro para ({sexo_norm}, peso={peso_snap}, bf={bf_snap}, obj={obj_norm})"
        )

    # Calcular derivación
    derivacion = calcular_masa_trabajo(peso, porcentaje_graso, porcentaje_trabajo)

    # Extraer macros
    macros = {
        "entreno": {
            "proteina": float(registro["pr_e"]),
            "hidratos": float(registro["hc_e"]),
            "grasa": float(registro["gr_e"]),
        },
        "perientreno": {
            "proteina": float(registro["pr_pe"]),
            "hidratos": float(registro["hc_pe"]),
        },
        "descanso": {
            "proteina": float(registro["pr_d"]),
            "hidratos": float(registro["hc_d"]),
            "grasa": float(registro["gr_d"]),
        },
    }

    # Calcular multiplicadores (para override del coach)
    mt = derivacion["masa_trabajo"]
    multiplicadores = {}
    if mt > 0:
        multiplicadores = {
            "pr_entreno": round(macros["entreno"]["proteina"] / mt, 4),
            "hc_entreno": round(macros["entreno"]["hidratos"] / mt, 4),
            "gr_entreno": round(macros["entreno"]["grasa"] / mt, 4),
            "pr_perientreno": round(macros["perientreno"]["proteina"] / mt, 4),
            "hc_perientreno": round(macros["perientreno"]["hidratos"] / mt, 4),
            "pr_descanso": round(macros["descanso"]["proteina"] / mt, 4),
            "hc_descanso": round(macros["descanso"]["hidratos"] / mt, 4),
            "gr_descanso": round(macros["descanso"]["grasa"] / mt, 4),
        }

    # Kcal por tipo de día
    kcal_entreno = macros["entreno"]["proteina"] * 4 + macros["entreno"]["hidratos"] * 4 + macros["entreno"]["grasa"] * 9
    kcal_descanso = macros["descanso"]["proteina"] * 4 + macros["descanso"]["hidratos"] * 4 + macros["descanso"]["grasa"] * 9

    return {
        "input": {
            "peso": peso,
            "sexo": sexo_norm,
            "porcentaje_graso": porcentaje_graso,
            "objetivo": obj_norm,
            "porcentaje_trabajo": porcentaje_trabajo,
        },
        "derivacion": derivacion,
        "lookup": {
            "peso_snap": peso_snap,
            "bf_snap": bf_snap,
        },
        "macros": macros,
        "kcal": {
            "entreno": round(kcal_entreno),
            "descanso": round(kcal_descanso),
        },
        "multiplicadores": multiplicadores,
    }


def targets_to_profile_macros(targets: Dict) -> Dict:
    """
    Convierte el resultado de calcular_targets al formato que usa el perfil del cliente.
    Compatible con el formato existente de macros_training / macros_rest / macros_periworkout.

    Returns:
        {
            "macros_training": {"protein": X, "carbs": Y, "fat": Z, "calories": C},
            "macros_rest": {"protein": X, "carbs": Y, "fat": Z, "calories": C},
            "macros_periworkout": {"protein": X, "carbs": Y}
        }
    """
    m = targets["macros"]

    training = {
        "protein": m["entreno"]["proteina"],
        "carbs": m["entreno"]["hidratos"],
        "fat": m["entreno"]["grasa"],
    }
    training["calories"] = training["protein"] * 4 + training["carbs"] * 4 + training["fat"] * 9

    rest = {
        "protein": m["descanso"]["proteina"],
        "carbs": m["descanso"]["hidratos"],
        "fat": m["descanso"]["grasa"],
    }
    rest["calories"] = rest["protein"] * 4 + rest["carbs"] * 4 + rest["fat"] * 9

    peri = {
        "protein": m["perientreno"]["proteina"],
        "carbs": m["perientreno"]["hidratos"],
    }

    # Formato alternativo que usa el chatbot (proteinas/hidratos/grasas)
    training_alt = {
        "proteinas": m["entreno"]["proteina"],
        "hidratos": m["entreno"]["hidratos"],
        "grasas": m["entreno"]["grasa"],
    }
    rest_alt = {
        "proteinas": m["descanso"]["proteina"],
        "hidratos": m["descanso"]["hidratos"],
        "grasas": m["descanso"]["grasa"],
    }
    peri_alt = {
        "proteinas": m["perientreno"]["proteina"],
        "hidratos": m["perientreno"]["hidratos"],
    }

    return {
        "macros_training": {**training, **training_alt},
        "macros_rest": {**rest, **rest_alt},
        "macros_periworkout": {**peri, **peri_alt},
    }


# =========================================================
# TESTS
# =========================================================

def run_tests() -> Dict:
    """Ejecuta tests de verificación del motor de targets."""
    if not _INDEX:
        _load_tables()

    results = []

    def check(name, condition, detail=""):
        results.append({
            "nombre": name,
            "passed": condition,
            "detalle": detail if not condition else "OK",
        })

    # Test 1: Caso canónico hombre 80kg 20%BF volumen
    t = calcular_targets(80, "hombre", 20, "volumen")
    check("Canónico H80 BF20 vol: P entreno", t["macros"]["entreno"]["proteina"] == 190,
          f"Esperado 190, got {t['macros']['entreno']['proteina']}")
    check("Canónico H80 BF20 vol: H entreno", t["macros"]["entreno"]["hidratos"] == 170,
          f"Esperado 170, got {t['macros']['entreno']['hidratos']}")
    check("Canónico H80 BF20 vol: G entreno", t["macros"]["entreno"]["grasa"] == 60,
          f"Esperado 60, got {t['macros']['entreno']['grasa']}")
    check("Canónico H80 BF20 vol: P peri", t["macros"]["perientreno"]["proteina"] == 45,
          f"Esperado 45, got {t['macros']['perientreno']['proteina']}")
    check("Canónico H80 BF20 vol: H peri", t["macros"]["perientreno"]["hidratos"] == 50,
          f"Esperado 50, got {t['macros']['perientreno']['hidratos']}")
    check("Canónico H80 BF20 vol: P descanso", t["macros"]["descanso"]["proteina"] == 225,
          f"Esperado 225, got {t['macros']['descanso']['proteina']}")

    # Test 2: Masa de trabajo correcta
    d = t["derivacion"]
    check("Masa grasa = 16", d["masa_grasa"] == 16.0,
          f"Esperado 16.0, got {d['masa_grasa']}")
    check("Masa magra = 64", d["masa_magra"] == 64.0,
          f"Esperado 64.0, got {d['masa_magra']}")
    check("Masa trabajo ~ 75.29", abs(d["masa_trabajo"] - 75.29) < 0.1,
          f"Esperado ~75.29, got {d['masa_trabajo']}")

    # Test 3: Peso fuera de rango (hombre 55kg → snap a 60)
    t2 = calcular_targets(55, "hombre", 20, "volumen")
    check("Peso bajo snap: 55→60", t2["lookup"]["peso_snap"] == 60,
          f"Esperado 60, got {t2['lookup']['peso_snap']}")

    # Test 4: Peso fuera de rango alto (hombre 130kg → snap a 120)
    t3 = calcular_targets(130, "hombre", 20, "volumen")
    check("Peso alto snap: 130→120", t3["lookup"]["peso_snap"] == 120,
          f"Esperado 120, got {t3['lookup']['peso_snap']}")

    # Test 5: BF intermedio (22% → snap a 20)
    t4 = calcular_targets(80, "hombre", 22, "volumen")
    check("BF intermedio: 22→20", t4["lookup"]["bf_snap"] == 20,
          f"Esperado 20, got {t4['lookup']['bf_snap']}")

    # Test 6: Peso intermedio (82kg → snap a 80)
    t5 = calcular_targets(82, "hombre", 20, "volumen")
    check("Peso intermedio: 82→80", t5["lookup"]["peso_snap"] == 80,
          f"Esperado 80, got {t5['lookup']['peso_snap']}")

    # Test 7: Mujer caso básico
    t6 = calcular_targets(60, "mujer", 25, "volumen")
    check("Mujer 60kg 25%BF vol lookup", t6["macros"]["entreno"]["proteina"] > 0,
          f"P debe ser > 0, got {t6['macros']['entreno']['proteina']}")

    # Test 8: Invariante del objetivo (P y G iguales para vol y def)
    tv = calcular_targets(80, "hombre", 20, "volumen")
    td = calcular_targets(80, "hombre", 20, "definicion")
    check("Invariante: P entreno vol==def",
          tv["macros"]["entreno"]["proteina"] == td["macros"]["entreno"]["proteina"],
          f"Vol={tv['macros']['entreno']['proteina']}, Def={td['macros']['entreno']['proteina']}")
    check("Invariante: G entreno vol==def",
          tv["macros"]["entreno"]["grasa"] == td["macros"]["entreno"]["grasa"],
          f"Vol={tv['macros']['entreno']['grasa']}, Def={td['macros']['entreno']['grasa']}")
    check("Invariante: H entreno vol!=def",
          tv["macros"]["entreno"]["hidratos"] != td["macros"]["entreno"]["hidratos"],
          f"Vol={tv['macros']['entreno']['hidratos']}, Def={td['macros']['entreno']['hidratos']}")

    # Test 9: Cobertura completa (208 hombre + 196 mujer)
    check("Cobertura hombre", len(_TABLE_HOMBRE) == 208,
          f"Esperado 208, got {len(_TABLE_HOMBRE)}")
    check("Cobertura mujer", len(_TABLE_MUJER) == 196,
          f"Esperado 196, got {len(_TABLE_MUJER)}")

    # Test 10: targets_to_profile_macros
    pm = targets_to_profile_macros(tv)
    check("Profile macros training P", pm["macros_training"]["protein"] == 190,
          f"Esperado 190, got {pm['macros_training']['protein']}")
    check("Profile macros periworkout P", pm["macros_periworkout"]["protein"] == 45,
          f"Esperado 45, got {pm['macros_periworkout']['protein']}")

    # Test 11: Definición con acento
    t_accent = calcular_targets(80, "hombre", 20, "definición")
    check("Acepto 'definición' con tilde",
          t_accent["macros"]["entreno"]["proteina"] == td["macros"]["entreno"]["proteina"])

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = [r for r in results if not r["passed"]]

    return {
        "total": total,
        "passed": passed,
        "failed_count": total - passed,
        "all_passed": passed == total,
        "tests": results,
        "failed_tests": failed,
    }


# Pre-cargar tablas al importar
try:
    _load_tables()
except Exception:
    pass  # Se cargará al primer uso


if __name__ == "__main__":
    r = run_tests()
    print(f"\nTarget Calculator - Tests: {r['passed']}/{r['total']}")
    if r["all_passed"]:
        print("OK - Todos los tests pasan")
    else:
        print("ERRORES:")
        for t in r["failed_tests"]:
            print(f"  - {t['nombre']}: {t['detalle']}")
