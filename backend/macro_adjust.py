"""
MOTOR DE RE-AJUSTE MENSUAL DE MACROS (Tarea 1 - metodologia de Jesus)
====================================================================
NO calcula macros iniciales (eso es macro_engine.py). Toma los macros ACTUALES
de un cliente + su evolucion de peso + el reporte del mes, y PROPONE el siguiente
ajuste, siguiendo el metodo de Jesus. Es una SUGERENCIA: el coach revisa/edita.

Fundado en datos (mineria de 162 clientes / 3367 ajustes reales, ver
_minar_patrones.py), NO en un solo cliente:
 - Proteina estable por defecto (cambia solo el 22%: cambios de fase/largo plazo).
 - Hidratos en pasos de 10/20/30 g (moda 20). Grasas en pasos de 10 g.
 - DEFINICION: por defecto recorta; no recorta si el reporte dice que no cumple.
 - VOLUMEN: por defecto sube poco a poco.
 - Suelo/techo de HC entreno por sexo (hombre 70-170, mujer 60-100 aprox).
 - Suelo duro 40 g para carbos Y grasas, "no mas de un mes" (aviso).

Modulo puro: sin Mongo ni FastAPI. La persistencia/avisos viven en las rutas.
"""
from typing import Dict, List, Optional

# ---- parametros sacados de los datos (medianas por sexo) ----
HC_ENT_SUELO = {"hombre": 50, "mujer": 50}      # suelo duro de comidas (con peri aparte)
HC_ENT_MUY_BAJO = {"hombre": 70, "mujer": 60}   # por debajo: "muy bajo, valora refeed"
HC_ENT_TECHO = {"hombre": 200, "mujer": 120}    # techo suave; cerca -> pasos mas pequenos
GRASA_SUELO = 40                                 # suelo duro grasas (max 1 mes)
PERI_MIN = 15
STEP_HC = 20      # escalon tipico de hidratos (moda de los datos)
STEP_HC_MIN = 10  # escalon pequeno (cerca de suelo/techo o "va bien")
STEP_G = 10       # escalon tipico de grasas

VERSION_AJUSTE = 1


def redondear5(x: float) -> int:
    return int(round(x / 5.0)) * 5


def _val(m: Dict, *keys):
    for k in keys:
        v = m.get(k)
        if v is not None:
            return float(v)
    return None


def _tendencia_peso(evolucion_peso: List[Dict]) -> Dict:
    """Ultima vs anterior con dato valido. Devuelve {trend, delta, ...}."""
    pts = [(p.get("fecha"), p.get("peso")) for p in (evolucion_peso or [])
           if isinstance(p.get("peso"), (int, float)) and 30 < p["peso"] < 300]
    pts.sort(key=lambda x: x[0] or "")
    if len(pts) < 2:
        return {"trend": None, "delta": None, "peso_actual": pts[-1][1] if pts else None,
                "peso_desde_inicio": None}
    delta = pts[-1][1] - pts[-2][1]
    trend = "sube" if delta >= 0.5 else "baja" if delta <= -0.5 else "igual"
    return {"trend": trend, "delta": round(delta, 1), "peso_actual": pts[-1][1],
            "peso_anterior": pts[-2][1], "peso_desde_inicio": round(pts[-1][1] - pts[0][1], 1)}


def _norm_cumpl(c: Optional[str]) -> Optional[str]:
    """Normaliza el cumplimiento de dieta a bien|regular|mal|mantener."""
    if not c:
        return None
    c = str(c).lower()
    if c in ("bien", "regular", "mal", "mantener"):
        return c
    if c in ("a",) or "perfect" in c or "casi" in c:
        return "bien"
    if c in ("b",) or "70" in c:
        return "regular"
    if c in ("c",) or "regular" in c or "cuesta" in c or "mal" in c:
        return "mal"
    if c in ("i",) or "mant" in c or "nada" in c:
        return "mantener"
    return None


def ajustar_macros(
    macros_actuales: Dict,
    sexo: str,
    fase: str,                      # 'definicion' | 'volumen'
    evolucion_peso: List[Dict],     # [{fecha, peso}, ...]
    reporte: Optional[Dict] = None, # {cumplimiento_dieta, cumplimiento_entreno, ...}
    meses_en_fase: Optional[int] = None,
    fase_anterior: Optional[str] = None,
) -> Dict:
    """Propone el siguiente ajuste de macros. Devuelve propuesta + motivo + avisos."""
    sexo = "mujer" if str(sexo).lower().startswith(("m u", "f", "muj")) or sexo == "F" else "hombre"
    fase = "volumen" if str(fase).lower().startswith("vol") else "definicion"
    cumpl = _norm_cumpl((reporte or {}).get("cumplimiento_dieta"))
    tp = _tendencia_peso(evolucion_peso)
    trend = tp["trend"]

    # copia editable de los macros (formato del motor)
    E = dict(macros_actuales.get("entreno", {}))
    Pe = dict(macros_actuales.get("perientreno", {}))
    D = dict(macros_actuales.get("descanso", {}))
    he = _val(E, "hidratos", "carbs") or 0.0
    hd = _val(D, "hidratos", "carbs") or 0.0
    ge = _val(E, "grasa", "fat") or 0.0
    gd = _val(D, "grasa", "fat") or 0.0

    avisos: List[str] = []
    cambios: List[str] = []
    suelo = HC_ENT_SUELO[sexo]; muy_bajo = HC_ENT_MUY_BAJO[sexo]; techo = HC_ENT_TECHO[sexo]

    # ---------- cambio de fase: evento distinto (recorte/subida mayor) ----------
    if fase_anterior and fase_anterior != fase:
        avisos.append(f"CAMBIO DE FASE ({fase_anterior} -> {fase}): revisa el % graso y valora recalcular; el ajuste suele ser mayor.")

    # ---------- decidir accion sobre HIDRATOS (proteina NO se toca) ----------
    accion = "mantener"; paso = 0; motivo = ""

    if cumpl in ("mal", "mantener"):
        # pautado-vs-real: si no cumple, no se ajusta a la baja; el "ajuste" es cumplir
        accion = "mantener"
        motivo = ("El reporte indica que no ha cumplido bien: no bajo macros sobre lo pautado. "
                  "El ajuste es que haga lo que ya tiene marcado (regla pautado-vs-real).")
        if fase == "volumen":
            motivo += " (Volumen: mantener hasta que cumpla.)"

    elif fase == "definicion":
        cerca_suelo = he <= muy_bajo
        if trend == "baja":
            if cerca_suelo:
                accion = "mantener_o_min"; paso = 0
                motivo = "Baja de peso y cumple, pero ya en macros bajos: no toco casi (si acaso, refeed)."
                avisos.append("En/near el suelo: valora un refeed o el zigzag antes de seguir bajando.")
            else:
                accion = "cortar"; paso = STEP_HC_MIN
                motivo = "Baja bien y cumple: recorte pequeno para seguir progresando."
        else:  # igual o sube, cumpliendo -> recortar mas
            accion = "cortar"; paso = STEP_HC
            motivo = ("Cumple pero el peso no baja: recorto un escalon de hidratos."
                      if trend == "igual" else
                      "Cumple pero sube de peso: recorto hidratos.")

    else:  # volumen, cumpliendo
        cerca_techo = he >= techo
        if trend == "sube":
            accion = "subir"; paso = STEP_HC_MIN if cerca_techo else STEP_HC
            motivo = "Gana peso y cumple: subo poco a poco (mas suave cerca del techo)."
        else:  # igual o baja en volumen -> subir mas
            accion = "subir"; paso = STEP_HC
            motivo = "No termina de ganar y cumple: subo hidratos para empujar."

    # ---------- aplicar la accion a hidratos entreno + descanso ----------
    if accion == "cortar":
        he = max(suelo, he - paso)
        hd = max(suelo, hd - paso)
        cambios.append(f"HC entreno -{paso}, HC descanso -{paso}")
        if he <= muy_bajo:
            avisos.append("Quedas en macros bajos: no lo mantengas muchas semanas.")
    elif accion == "subir":
        he = min(techo + 40, he + paso)
        hd = hd + max(STEP_HC_MIN, paso - STEP_HC_MIN)  # descanso sube algo menos
        cambios.append(f"HC entreno +{paso}, HC descanso +{max(STEP_HC_MIN, paso - STEP_HC_MIN)}")
    elif accion == "mantener_o_min":
        # ajuste minimo estilo 'si funciona toca poco': +10 grasa descanso
        gd = gd + STEP_G
        cambios.append(f"Grasa descanso +{STEP_G} (ajuste minimo)")

    # ---------- suelo duro de grasas (40, max 1 mes) ----------
    if ge <= GRASA_SUELO or gd <= GRASA_SUELO:
        avisos.append(f"Grasas en el suelo ({GRASA_SUELO} g): no lo mantengas mas de un mes; toca subirlas.")

    # ---------- montar propuesta (proteina intacta, redondeo a 5) ----------
    prop = {
        "entreno": {"proteina": redondear5(_val(E, "proteina", "protein") or 0),
                    "hidratos": redondear5(he), "grasa": redondear5(ge)},
        "perientreno": {"proteina": redondear5(_val(Pe, "proteina", "protein") or 0),
                        "hidratos": redondear5(max(PERI_MIN, _val(Pe, "hidratos", "carbs") or PERI_MIN))},
        "descanso": {"proteina": redondear5(_val(D, "proteina", "protein") or 0),
                     "hidratos": redondear5(hd), "grasa": redondear5(gd)},
    }
    if not cambios:
        cambios.append("Sin cambios de hidratos/grasas (mantener)")

    return {
        "propuesta": prop,
        "accion": accion,
        "motivo": motivo,
        "cambios": cambios,
        "avisos": avisos,
        "contexto": {
            "fase": fase, "sexo": sexo, "cumplimiento_dieta": cumpl,
            "tendencia_peso": trend, "delta_peso": tp["delta"],
            "peso_actual": tp["peso_actual"], "peso_desde_inicio": tp["peso_desde_inicio"],
            "meses_en_fase": meses_en_fase,
            "suelo_hc_entreno": suelo, "techo_hc_entreno": techo,
        },
        "version": VERSION_AJUSTE,
    }
