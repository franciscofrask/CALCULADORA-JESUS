"""
MOTOR DE MACROS v2 - Quiz inicial + modificadores (spec 18-07-2026)
===================================================================
Envuelve calcular_targets() (la tabla) y aplica encima, EN ORDEN:
modificadores de hidratos -> dato real (dieta reportada) -> suelos -> redondeo.

Reglas de la spec:
- Los modificadores solo tocan los HIDRATOS de entreno y descanso, NUNCA el
  perientreno y NUNCA la proteina (excepcion: farmacologia, +10% proteina
  SOLO en descanso).
- Los porcentajes se SUMAN sobre la base de tabla (no compuestos).
- "Engordo enseguida" = VETO: anula todas las subidas de hidratos.
- hc_e de la tabla son los hidratos de COMIDAS del dia de entreno (el peri
  va aparte en hc_pe); por eso el suelo de comidas es 50 (con peri 15 => 65).

Modulo puro: sin Mongo y sin FastAPI. La persistencia y los avisos al coach
viven en las rutas.
"""

from typing import Dict, List, Optional

from target_calculator import calcular_targets

# =========================================================
# CONSTANTES (spec "QUIZ INICIAL + MOTOR DE MACROS v2")
# =========================================================

# Modificadores de hidratos (fracciones sobre la base de tabla)
MOD_MUY_ACTIVO_ENTRENO = 0.10
MOD_MUY_ACTIVO_DESCANSO = 0.10
MOD_DEPORTE_EXTRA_DESCANSO = 0.10        # solo descanso
MOD_CASI_NO_ENGORDA = 0.20               # entreno y descanso; requiere bf <= 20
BF_MAX_CASI_NO_ENGORDA = 20.0
TOPE_SUBIDA_ENTRENO = 0.30
TOPE_SUBIDA_DESCANSO = 0.40

# Excepcion que toca proteina: farmacologia (+10% SOLO descanso)
MOD_FARMACOLOGIA_PROTEINA_DESCANSO = 0.10

# NO PROGRAMADOS AUN (guardar el dato, no aplicar):
APLICAR_HISTORIAL_DIETA = False   # +-10% por historial de dieta: en pausa, sin validar
APLICAR_ENGORDA_EN_MUJERES = False  # +20% "casi no engordo" en mujeres: n=11, sin validar
# El VETO ("engordo enseguida") SI aplica a ambos sexos: es lo conservador.

# Suelos (la tabla ya cumple la proteina; se dejan como red de seguridad).
# Los "macros umbral" (40 g de hidratos / 40 de grasa, max un mes) y la grasa
# de descanso 70 puntual NO los aplica el motor: son decision manual del coach.
SUELO_PROTEINA_ENTRENO = {"hombre": 160, "mujer": 120}
SUELO_HC_COMIDAS_ENTRENO = 50     # comidas de entreno; con el peri de 15, 65 totales
SUELO_HC_DESCANSO = 50
SUELO_GRASA = 50                  # entreno y descanso

# Dieta reportada: banda de peri por HC totales del dia de entreno
BANDAS_PERI = [(200, 50), (300, 60), (400, 75), (float("inf"), 90)]

# Definicion "come mucho": primer recorte (~13%) por tramo de HC totales.
# Anclas de la spec: 150->-20, 200->-25, 250->-30, 300->-40, 350->-45, 400+->-55.
# Se aplica el ancla mas cercana (cortes en los puntos medios).
RECORTES_DEFINICION = [(175, 20), (225, 25), (275, 30), (325, 40), (375, 45), (float("inf"), 55)]

UMBRAL_HC_EN_LAS_ULTIMAS = 75     # < 75 g netos -> arranque minimo
PERI_EN_LAS_ULTIMAS = 15
DESCANSO_SOBRE_COMIDAS = 0.75     # descanso = comidas de entreno - 25%

# Humano en el bucle: si lo reportado se desvia mas de esto de lo recomendado,
# se avisa al entrenador para que revise.
UMBRAL_REVISION = 0.15

VERSION_MOTOR = 2


def redondear5(x: float) -> int:
    """Multiplo de 5 mas cercano; los .5 exactos van al par (142.5->140,
    247.5->250), que es lo que cuadra con los ejemplos de la spec."""
    return int(round(x / 5.0)) * 5


def _banda_peri(hc_totales: float) -> int:
    for limite, peri in BANDAS_PERI:
        if hc_totales <= limite:
            return peri
    return BANDAS_PERI[-1][1]


def _recorte_definicion(hc_totales: float) -> int:
    for limite, recorte in RECORTES_DEFINICION:
        if hc_totales <= limite:
            return recorte
    return RECORTES_DEFINICION[-1][1]


def calcular_macros_v2(
    peso: float,
    sexo: str,
    porcentaje_graso: float,
    objetivo: str,
    actividad_diaria: Optional[str] = None,   # 'sedentario' | 'normal' | 'muy_activo'
    deporte_extra: Optional[bool] = None,
    facilidad_engordar: Optional[str] = None,  # 'enseguida' | 'normal' | 'casi_no'
    dieta_reportada: Optional[Dict] = None,    # {'hc_entreno': g, 'grasa_entreno': g|None, 'texto': str}
    farmacologia: bool = False,
    historial_dietas: Optional[str] = None,    # solo se registra, no se aplica
) -> Dict:
    """Los 8 numeros del metodo con la spec v2 encima de la tabla.

    Devuelve {base, macros, desglose, revision, no_aplicados, version_motor}.
    """
    base = calcular_targets(peso, sexo, porcentaje_graso, objetivo)
    sexo_norm = base["input"]["sexo"]
    obj_norm = base["input"]["objetivo"]
    bm = base["macros"]

    pr_e = bm["entreno"]["proteina"]
    hc_e = bm["entreno"]["hidratos"]
    gr_e = bm["entreno"]["grasa"]
    pr_pe = bm["perientreno"]["proteina"]
    hc_pe = bm["perientreno"]["hidratos"]
    pr_d = bm["descanso"]["proteina"]
    hc_d = bm["descanso"]["hidratos"]
    gr_d = bm["descanso"]["grasa"]

    desglose: List[Dict] = [{
        "paso": "tabla",
        "detalle": f"{sexo_norm} {base['lookup']['peso_snap']:.0f} kg / {base['lookup']['bf_snap']:.0f}% {obj_norm}",
        "valores": {"pr_e": pr_e, "hc_e": hc_e, "gr_e": gr_e, "pr_pe": pr_pe,
                    "hc_pe": hc_pe, "pr_d": pr_d, "hc_d": hc_d, "gr_d": gr_d},
    }]
    no_aplicados: Dict = {}

    # -----------------------------------------------------
    # 1) Modificadores de hidratos (sumados, luego topes y veto)
    # -----------------------------------------------------
    pct_e = 0.0
    pct_d = 0.0

    if actividad_diaria == "muy_activo":
        pct_e += MOD_MUY_ACTIVO_ENTRENO
        pct_d += MOD_MUY_ACTIVO_DESCANSO
        desglose.append({"paso": "muy_activo", "estado": "aplicado",
                         "detalle": "+10% HC entreno y descanso"})

    if deporte_extra:
        pct_d += MOD_DEPORTE_EXTRA_DESCANSO
        desglose.append({"paso": "deporte_extra", "estado": "aplicado",
                         "detalle": "+10% HC solo descanso"})

    if facilidad_engordar == "casi_no":
        if sexo_norm == "mujer" and not APLICAR_ENGORDA_EN_MUJERES:
            no_aplicados["engorda_mujer"] = "casi_no"
            desglose.append({"paso": "casi_no_engorda", "estado": "no_aplica_mujer",
                             "detalle": "Modificador sin validar en mujeres: se guarda, no se aplica"})
        elif porcentaje_graso <= BF_MAX_CASI_NO_ENGORDA:
            pct_e += MOD_CASI_NO_ENGORDA
            pct_d += MOD_CASI_NO_ENGORDA
            desglose.append({"paso": "casi_no_engorda", "estado": "aplicado",
                             "detalle": "+20% HC entreno y descanso"})
        else:
            desglose.append({"paso": "casi_no_engorda", "estado": "no_aplica_bf",
                             "detalle": f"Requiere grasa <= {BF_MAX_CASI_NO_ENGORDA:.0f}%"})

    if facilidad_engordar == "enseguida" and (pct_e > 0 or pct_d > 0):
        desglose.append({"paso": "veto_engorda_enseguida", "estado": "vetado",
                         "detalle": f"Anuladas subidas de HC (+{pct_e:.0%} entreno, +{pct_d:.0%} descanso)"})
        pct_e = 0.0
        pct_d = 0.0

    if historial_dietas and not APLICAR_HISTORIAL_DIETA:
        no_aplicados["historial_dietas"] = historial_dietas
        desglose.append({"paso": "historial_dietas", "estado": "no_aplicado",
                         "detalle": "El +-10% por historial esta en pausa: se guarda, no se aplica"})

    if pct_e > TOPE_SUBIDA_ENTRENO or pct_d > TOPE_SUBIDA_DESCANSO:
        desglose.append({"paso": "tope", "estado": "recortado",
                         "detalle": f"Tope +{TOPE_SUBIDA_ENTRENO:.0%} entreno / +{TOPE_SUBIDA_DESCANSO:.0%} descanso"})
    pct_e = min(pct_e, TOPE_SUBIDA_ENTRENO)
    pct_d = min(pct_d, TOPE_SUBIDA_DESCANSO)

    hc_e = hc_e * (1 + pct_e)
    hc_d = hc_d * (1 + pct_d)

    # -----------------------------------------------------
    # 2) Excepcion proteina: farmacologia (+10% SOLO descanso)
    # -----------------------------------------------------
    if farmacologia:
        pr_d = pr_d * (1 + MOD_FARMACOLOGIA_PROTEINA_DESCANSO)
        desglose.append({"paso": "farmacologia", "estado": "aplicado",
                         "detalle": "+10% proteina solo en descanso"})

    # HC de entreno recomendados (comidas + peri) tras modificadores: es la
    # referencia contra la que se compara la dieta reportada.
    hc_recomendados = hc_e + hc_pe

    # -----------------------------------------------------
    # 3) Dieta reportada (pisa los hidratos; proteina siempre la de tabla)
    # -----------------------------------------------------
    revision = None
    hc_rep = None
    if dieta_reportada and dieta_reportada.get("hc_entreno") is not None:
        hc_rep = float(dieta_reportada["hc_entreno"])
        grasa_rep = dieta_reportada.get("grasa_entreno")
        grasa_rep = float(grasa_rep) if grasa_rep is not None else None

        if obj_norm == "definicion" and hc_rep < UMBRAL_HC_EN_LAS_ULTIMAS:
            # Llega "en las ultimas": arranque minimo, se sube en el siguiente ajuste
            hc_e, gr_e = 60.0, 50.0
            hc_pe = float(PERI_EN_LAS_ULTIMAS)
            hc_d, gr_d = 50.0, 60.0
            desglose.append({"paso": "dieta_reportada", "rama": "def_ultimas",
                             "detalle": f"Reporta {hc_rep:.0f} g de HC (<{UMBRAL_HC_EN_LAS_ULTIMAS}): arranque 60/50, peri 15, descanso 50/60"})
        else:
            total = hc_rep
            recorte = 0
            if obj_norm == "definicion":
                recorte = _recorte_definicion(hc_rep)
                total = hc_rep - recorte
            peri = _banda_peri(total)
            comidas = total - peri
            hc_e = comidas
            hc_pe = float(peri)
            hc_d = comidas * DESCANSO_SOBRE_COMIDAS

            if obj_norm == "volumen":
                gr_e = 60.0
                if grasa_rep is not None and grasa_rep > 70:
                    gr_e = 80.0 if hc_rep > 450 else 70.0
                gr_d = 80.0 if (grasa_rep is not None and grasa_rep > 70) else 70.0
                desglose.append({"paso": "dieta_reportada", "rama": "volumen",
                                 "detalle": f"Mismos {hc_rep:.0f} g repartidos: peri {peri} por banda, {comidas:.0f} a comidas, descanso -25%"})
            else:
                desglose.append({"paso": "dieta_reportada", "rama": "def_come_mucho",
                                 "detalle": f"Recorte -{recorte} g (~13%) sobre {hc_rep:.0f}: peri {peri}, {comidas:.0f} a comidas, descanso -25%"})

        diferencia = hc_rep - hc_recomendados
        diferencia_pct = abs(diferencia) / hc_recomendados if hc_recomendados else 0.0
        revision = {
            "requiere_revision": diferencia_pct > UMBRAL_REVISION,
            "hc_reportados": hc_rep,
            "hc_recomendados": redondear5(hc_recomendados),
            "diferencia": redondear5(diferencia),
            "diferencia_pct": round(diferencia_pct, 3),
            "umbral": UMBRAL_REVISION,
        }

    # -----------------------------------------------------
    # 4) Suelos
    # -----------------------------------------------------
    suelos_activados = []
    suelo_pr = SUELO_PROTEINA_ENTRENO[sexo_norm]
    if pr_e < suelo_pr:
        pr_e = float(suelo_pr)
        suelos_activados.append(f"proteina entreno {suelo_pr}")
    if hc_e < SUELO_HC_COMIDAS_ENTRENO:
        hc_e = float(SUELO_HC_COMIDAS_ENTRENO)
        suelos_activados.append(f"HC comidas entreno {SUELO_HC_COMIDAS_ENTRENO}")
    if hc_d < SUELO_HC_DESCANSO:
        hc_d = float(SUELO_HC_DESCANSO)
        suelos_activados.append(f"HC descanso {SUELO_HC_DESCANSO}")
    if gr_e < SUELO_GRASA:
        gr_e = float(SUELO_GRASA)
        suelos_activados.append(f"grasa entreno {SUELO_GRASA}")
    if gr_d < SUELO_GRASA:
        gr_d = float(SUELO_GRASA)
        suelos_activados.append(f"grasa descanso {SUELO_GRASA}")
    if suelos_activados:
        desglose.append({"paso": "suelos", "estado": "aplicado", "activados": suelos_activados})

    # -----------------------------------------------------
    # 5) Redondeo a multiplo de 5 (siempre el ultimo paso)
    # -----------------------------------------------------
    macros = {
        "entreno": {"proteina": redondear5(pr_e), "hidratos": redondear5(hc_e), "grasa": redondear5(gr_e)},
        "perientreno": {"proteina": redondear5(pr_pe), "hidratos": redondear5(hc_pe)},
        "descanso": {"proteina": redondear5(pr_d), "hidratos": redondear5(hc_d), "grasa": redondear5(gr_d)},
    }

    return {
        "base": base,
        "macros": macros,
        "kcal": {
            "entreno": macros["entreno"]["proteina"] * 4 + macros["entreno"]["hidratos"] * 4 + macros["entreno"]["grasa"] * 9,
            "descanso": macros["descanso"]["proteina"] * 4 + macros["descanso"]["hidratos"] * 4 + macros["descanso"]["grasa"] * 9,
        },
        "desglose": desglose,
        "revision": revision,
        "no_aplicados": no_aplicados,
        "version_motor": VERSION_MOTOR,
    }


def multiplicadores_de(resultado: Dict) -> Dict:
    """Multiplicadores por masa de trabajo sobre los macros FINALES del motor
    (mismas claves que target_calculator, para macros_multiplicadores)."""
    mt = resultado["base"]["derivacion"]["masa_trabajo"]
    if not mt:
        return {}
    m = resultado["macros"]
    return {
        "pr_entreno": round(m["entreno"]["proteina"] / mt, 4),
        "hc_entreno": round(m["entreno"]["hidratos"] / mt, 4),
        "gr_entreno": round(m["entreno"]["grasa"] / mt, 4),
        "pr_perientreno": round(m["perientreno"]["proteina"] / mt, 4),
        "hc_perientreno": round(m["perientreno"]["hidratos"] / mt, 4),
        "pr_descanso": round(m["descanso"]["proteina"] / mt, 4),
        "hc_descanso": round(m["descanso"]["hidratos"] / mt, 4),
        "gr_descanso": round(m["descanso"]["grasa"] / mt, 4),
    }


def ajustes_to_kwargs(ajustes: Optional[Dict]) -> Dict:
    """Convierte el dict AjustesMacros (preguntas 5-8 del quiz) en los kwargs
    del motor. Tolera None y claves ausentes (perfil sin ajustes guardados)."""
    a = ajustes or {}
    dieta = None
    if a.get("sigue_dieta") and a.get("dieta_hc_entreno") is not None:
        dieta = {
            "hc_entreno": a.get("dieta_hc_entreno"),
            "grasa_entreno": a.get("dieta_grasa_entreno"),
            "texto": a.get("dieta_texto"),
        }
    return {
        "actividad_diaria": a.get("actividad_diaria"),
        "deporte_extra": a.get("deporte_extra"),
        "facilidad_engordar": a.get("facilidad_engordar"),
        "dieta_reportada": dieta,
        "historial_dietas": a.get("historial_dietas"),
    }
