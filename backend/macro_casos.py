"""
BANCO DE CASOS DE AJUSTE (memoria del agente)
=============================================
El agente de macros solo veia el historial DEL PROPIO cliente. Esto le da memoria de
TODA la cartera: por cada ajuste real de cualquier cliente guardamos el ESTADO del que
partia, el MOVIMIENTO que se hizo y el RESULTADO que dio (cuanto se movio el peso, en
% del peso corporal, hasta el siguiente ajuste).

Con eso, al pedir una sugerencia se buscan los casos mas parecidos (el "cliente gemelo"
del doc "El modelo predictivo de macros") y se le pasan al LLM como ejemplos con su
desenlace. Aprende de lo que funciono y de lo que no, sin entrenar nada: cada ajuste y
cada evaluacion nuevos entran en el banco al recalcularlo.

Reconstruir el banco:  python -m macro_casos            (o `python macro_casos.py`)
"""
import asyncio
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

from core.database import db

# Un caso solo vale si podemos medir que paso despues: el siguiente ajuste tiene que
# estar en una ventana razonable (ni al dia siguiente ni un ano despues).
DIAS_MIN_TRAMO = 10
DIAS_MAX_TRAMO = 120
# El histórico trae basura (pesos mal apuntados, entradas a medias). Un caso con un
# ritmo de peso o un movimiento de macros imposibles enseñaria cosas falsas.
RITMO_MENSUAL_MAX_PCT = 8.0     # % de peso corporal al mes
MOVIMIENTO_MAX_G = 120          # un salto mayor no es un ajuste, es un dato roto


def _num(x) -> Optional[float]:
    return float(x) if isinstance(x, (int, float)) else None


def _sanea_peso(w) -> Optional[float]:
    """Mismo criterio que las rutas: arregla el error de coma (819 -> 81.9)."""
    try:
        w = float(w)
    except (TypeError, ValueError):
        return None
    while w > 1000:
        w /= 1000.0
    if 300 < w <= 1000:
        w /= 10.0
    return round(w, 1) if 25 < w < 300 else None


def _dias(f0: str, f1: str) -> Optional[int]:
    try:
        return (datetime.strptime(f1[:10], "%Y-%m-%d") - datetime.strptime(f0[:10], "%Y-%m-%d")).days
    except (ValueError, TypeError):
        return None


def _macros_de_calma(h: Dict) -> Dict:
    return {
        "entreno": {"proteina": _num(h.get("p_ent")), "hidratos": _num(h.get("h_ent")), "grasa": _num(h.get("g_ent"))},
        "perientreno": {"proteina": _num(h.get("p_peri")), "hidratos": _num(h.get("h_peri"))},
        "descanso": {"proteina": _num(h.get("p_desc")), "hidratos": _num(h.get("h_desc")), "grasa": _num(h.get("g_desc"))},
    }


def _macros_de_app(h: Dict) -> Dict:
    g = lambda m, *k: next((_num(m.get(i)) for i in k if m.get(i) is not None), None)
    t, r, p = h.get("training") or {}, h.get("rest") or {}, h.get("peri") or {}
    return {
        "entreno": {"proteina": g(t, "protein", "proteinas"), "hidratos": g(t, "carbs", "hidratos"), "grasa": g(t, "fat", "grasas")},
        "perientreno": {"proteina": g(p, "protein", "proteinas"), "hidratos": g(p, "carbs", "hidratos")},
        "descanso": {"proteina": g(r, "protein", "proteinas"), "hidratos": g(r, "carbs", "hidratos"), "grasa": g(r, "fat", "grasas")},
    }


def _completos(m: Dict) -> bool:
    return m["entreno"].get("hidratos") is not None and m["descanso"].get("hidratos") is not None


def _delta(antes: Dict, despues: Dict) -> Dict:
    """Que se movio de un ajuste al siguiente, macro a macro (solo lo que cambio)."""
    out = {}
    for bloque in ("entreno", "perientreno", "descanso"):
        for campo in ("proteina", "hidratos", "grasa"):
            a, d = antes.get(bloque, {}).get(campo), despues.get(bloque, {}).get(campo)
            if a is None or d is None:
                continue
            if round(d - a, 1) != 0:
                out.setdefault(bloque, {})[campo] = round(d - a, 1)
    return out


def _peso_en(pesos: List[Dict], fecha: str, margen: int = 21) -> Optional[float]:
    """Peso mas cercano a esa fecha (dentro de `margen` dias)."""
    mejor, mejor_d = None, None
    for p in pesos:
        d = _dias(p["fecha"], fecha)
        if d is None:
            continue
        d = abs(d)
        if d <= margen and (mejor_d is None or d < mejor_d):
            mejor, mejor_d = p["peso"], d
    return mejor


def _fase_de(reporte: Optional[Dict], goal: Optional[str]) -> str:
    txt = ((reporte or {}).get("objetivo") or goal or "definicion").lower()
    return "volumen" if "vol" in txt else "definicion"


async def _cartera() -> List[Dict]:
    """Un dict por cliente con todo lo necesario para reconstruir su camino."""
    clientes = []
    async for p in db.client_profiles.find({}, {"_id": 0, "id": 1, "user_id": 1, "sex": 1, "goal": 1,
                                                "body_fat": 1, "height": 1}):
        raw = await db.calma_raw.find_one(
            {"$or": [{"client_id": p["id"]}, {"user_id": p.get("user_id")}]},
            {"_id": 0, "macros_historial": 1, "pesos": 1, "formularios_mensuales": 1, "sexo": 1}) or {}

        pesos = {}
        for x in (raw.get("pesos") or []):
            w = _sanea_peso(x.get("valor"))
            if w and x.get("fecha"):
                pesos[x["fecha"][:10]] = w
        async for r in db.reports.find({"client_id": p["id"]}, {"_id": 0, "created_at": 1, "weight": 1}):
            w = _sanea_peso(r.get("weight"))
            if w and r.get("created_at"):
                pesos[r["created_at"][:10]] = w

        # ajustes: los de Calma + los de la app, en una sola linea de tiempo
        ajustes = []
        for h in (raw.get("macros_historial") or []):
            if h.get("fecha"):
                ajustes.append({"fecha": h["fecha"][:10], "macros": _macros_de_calma(h), "fuente": "calma"})
        async for h in db.macro_history.find({"client_id": p["id"]}, {"_id": 0}):
            fecha = h.get("effective_date") or (h.get("created_at") or "")[:10]
            if not fecha:
                continue
            ajustes.append({"fecha": fecha[:10], "macros": _macros_de_app(h), "fuente": "app",
                            "criterio": h.get("criterio"), "evaluacion": h.get("evaluacion"),
                            "body_fat": _num(h.get("body_fat")),
                            "peso_registrado": _sanea_peso(h.get("client_weight"))})
            if h.get("body_fat") is None and h.get("client_weight") is not None:
                w = _sanea_peso(h.get("client_weight"))
                if w:
                    pesos.setdefault(fecha[:10], w)
        ajustes = [a for a in ajustes if _completos(a["macros"])]
        ajustes.sort(key=lambda a: a["fecha"])

        reportes = sorted([r for r in (raw.get("formularios_mensuales") or []) if r.get("fecha")],
                          key=lambda r: r["fecha"])
        clientes.append({
            "client_id": p["id"], "sexo": (p.get("sex") or raw.get("sexo") or "hombre").lower(),
            "goal": p.get("goal"), "body_fat": _num(p.get("body_fat")),
            "pesos": [{"fecha": f, "peso": w} for f, w in sorted(pesos.items())],
            "ajustes": ajustes, "reportes": reportes,
        })
    return clientes


def _reporte_cercano(reportes: List[Dict], fecha: str, margen: int = 25) -> Optional[Dict]:
    """El reporte mensual mas proximo (y anterior) al ajuste: es lo que el coach leyo."""
    mejor, mejor_d = None, None
    for r in reportes:
        d = _dias(r["fecha"], fecha)
        if d is None or d < 0 or d > margen:
            continue
        if mejor_d is None or d < mejor_d:
            mejor, mejor_d = r, d
    if not mejor:
        return None
    gt = lambda k: (mejor.get(k) or {}).get("texto") if isinstance(mejor.get(k), dict) else mejor.get(k)
    return {"cumplimiento_dieta": gt("cumplimientoDieta"), "objetivo": gt("objetivo"),
            "esfuerzo": gt("esfuerzoParaCumplirDieta")}


def construir_casos(clientes: List[Dict]) -> List[Dict]:
    """Un caso por tramo entre dos ajustes consecutivos: estado + movimiento + resultado."""
    casos = []
    for c in clientes:
        ajustes = c["ajustes"]
        for i, a in enumerate(ajustes[:-1]):
            sig = ajustes[i + 1]
            dias = _dias(a["fecha"], sig["fecha"])
            if dias is None or not (DIAS_MIN_TRAMO <= dias <= DIAS_MAX_TRAMO):
                continue
            peso_ini = _peso_en(c["pesos"], a["fecha"]) or a.get("peso_registrado")
            peso_fin = _peso_en(c["pesos"], sig["fecha"]) or sig.get("peso_registrado")
            if not peso_ini or not peso_fin:
                continue

            delta_pct = round((peso_fin - peso_ini) / peso_ini * 100, 2)
            if abs(delta_pct) / dias * 30 > RITMO_MENSUAL_MAX_PCT:
                continue    # peso mal apuntado: no es un caso del que aprender

            movimiento = _delta(a["macros"], sig["macros"])
            if any(abs(v) > MOVIMIENTO_MAX_G for campos in movimiento.values() for v in campos.values()):
                continue    # salto imposible: entrada rota o cambio de fase mal registrado

            reporte = _reporte_cercano(c["reportes"], a["fecha"])
            he = a["macros"]["entreno"].get("hidratos")
            hi = a["macros"]["perientreno"].get("hidratos") or 0
            casos.append({
                "client_id": c["client_id"],
                "fecha": a["fecha"],
                "sexo": c["sexo"],
                "fase": _fase_de(reporte, c["goal"]),
                # estado del que se parte
                "peso": peso_ini,
                "body_fat": a.get("body_fat") if a.get("body_fat") is not None else c.get("body_fat"),
                "hc_entreno": he,
                "hc_total_entreno": round(he + hi, 1) if he is not None else None,
                "hc_entreno_kg": round(he / peso_ini, 2) if he and peso_ini else None,
                "hc_descanso": a["macros"]["descanso"].get("hidratos"),
                "grasa_entreno": a["macros"]["entreno"].get("grasa"),
                "proteina_entreno": a["macros"]["entreno"].get("proteina"),
                "intra": hi,
                "cumplimiento": (reporte or {}).get("cumplimiento_dieta"),
                "criterio": a.get("criterio"),
                # que se hizo y que paso despues
                "movimiento": movimiento,
                "dias_tramo": dias,
                "delta_peso_pct": delta_pct,
                "delta_peso_kg": round(peso_fin - peso_ini, 1),
                "evaluacion": a.get("evaluacion"),
                "fuente": a["fuente"],
            })
    return casos


async def reconstruir() -> Dict:
    """Rehace el banco entero (idempotente: se puede lanzar cuantas veces haga falta)."""
    clientes = await _cartera()
    casos = construir_casos(clientes)
    await db.macro_casos.delete_many({})
    if casos:
        await db.macro_casos.insert_many(casos)
        await db.macro_casos.create_index([("sexo", 1), ("fase", 1)])
    con_movimiento = sum(1 for c in casos if c["movimiento"])
    return {
        "clientes": len(clientes),
        "clientes_con_casos": len({c["client_id"] for c in casos}),
        "casos": len(casos),
        "con_movimiento": con_movimiento,
        "sin_movimiento": len(casos) - con_movimiento,
        "con_cumplimiento": sum(1 for c in casos if c.get("cumplimiento")),
        "con_evaluacion": sum(1 for c in casos if c.get("evaluacion")),
    }


# ---------------------------------------------------------------- recuperacion
def _similitud(caso: Dict, ref: Dict) -> Optional[float]:
    """Distancia entre un caso del banco y la situacion actual. Menor = mas parecido.
    Sexo y fase son filtros duros; el resto pondera."""
    if caso.get("sexo") != ref.get("sexo") or caso.get("fase") != ref.get("fase"):
        return None
    d = 0.0
    # lo que mas define el estado: cuanto hidrato lleva por kilo
    if caso.get("hc_entreno_kg") and ref.get("hc_entreno_kg"):
        d += abs(caso["hc_entreno_kg"] - ref["hc_entreno_kg"]) * 3.0
    elif caso.get("hc_entreno") and ref.get("hc_entreno"):
        d += abs(caso["hc_entreno"] - ref["hc_entreno"]) / 50.0
    else:
        d += 1.5
    if caso.get("body_fat") and ref.get("body_fat"):
        d += abs(caso["body_fat"] - ref["body_fat"]) / 10.0
    if caso.get("peso") and ref.get("peso"):
        d += abs(caso["peso"] - ref["peso"]) / 25.0
    # mismo tipo de cumplimiento pesa: no es lo mismo aconsejar a quien cumple
    if ref.get("cumplimiento") and caso.get("cumplimiento"):
        d += 0.0 if str(caso["cumplimiento"])[:12].lower() == str(ref["cumplimiento"])[:12].lower() else 0.6
    elif ref.get("cumplimiento") or caso.get("cumplimiento"):
        d += 0.3
    # los casos con evaluacion del coach valen mas (sabemos si salio bien)
    if (caso.get("evaluacion") or {}).get("resultado"):
        d -= 0.4
    if caso.get("criterio"):
        d -= 0.2
    return d


async def buscar_gemelos(ref: Dict, k: int = 8, excluir_client_id: Optional[str] = None) -> List[Dict]:
    """Los k casos mas parecidos a la situacion actual del cliente."""
    q = {"sexo": ref.get("sexo"), "fase": ref.get("fase")}
    candidatos = []
    async for c in db.macro_casos.find(q, {"_id": 0}):
        if excluir_client_id and c.get("client_id") == excluir_client_id:
            continue
        s = _similitud(c, ref)
        if s is not None:
            candidatos.append((s, c))
    candidatos.sort(key=lambda x: x[0])
    return [c for _, c in candidatos[:k]]


def formatear_gemelos(casos: List[Dict]) -> str:
    """Los casos, listos para meter en el prompt."""
    if not casos:
        return ""
    L = ["CASOS PARECIDOS DE OTROS CLIENTES (misma fase y sexo, estado similar). Formato: "
         "estado de partida -> que se hizo -> que paso con el peso:"]
    for c in casos:
        mov = c.get("movimiento") or {}
        if mov:
            partes = [f"{b} {k} {v:+g}" for b, campos in mov.items() for k, v in campos.items()]
            que = ", ".join(partes)
        else:
            que = "no se toco nada"
        estado = (f"{c.get('peso')} kg"
                  + (f", {c.get('body_fat')}% graso" if c.get("body_fat") else "")
                  + f", HC entreno {c.get('hc_entreno')} (+{c.get('intra')} intra)"
                  + (f", cumplimiento {c.get('cumplimiento')}" if c.get("cumplimiento") else ""))
        linea = f"  - {estado} -> {que} -> {c.get('delta_peso_pct'):+.2f}% de peso en {c.get('dias_tramo')} dias"
        ev = (c.get("evaluacion") or {}).get("resultado")
        if ev:
            linea += f" (el coach la marco como fase {ev})"
        L.append(linea)
        if c.get("criterio"):
            L.append(f"      criterio del coach entonces: {c['criterio']}")
    return "\n".join(L)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(asyncio.run(reconstruir()))
