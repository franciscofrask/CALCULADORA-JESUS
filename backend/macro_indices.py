"""
INDICES Y PERFILES (pasos 2 a 4 del doc "El modelo predictivo de macros")
========================================================================
El paso 2 (reconstruir el camino) lo cubre macro_casos.py. Aqui se sube un piso:

  - INDICES por cliente: los del "Sistema de metricas JG12", empezando por las cinco
    clave (indice hidrato-grasa en el techo, ratio de recomposicion, distribucion
    mensual, los dos umbrales y la mejora neta).
  - PERFILES derivados DE LOS DATOS, no predefinidos: los dos ejes del doc,
    MOTOR (cuanto hidrato tolera = el techo) x RESPONDEDOR (coge musculo y pierde
    grasa = el indice hidrato-grasa). Los cortes salen de los terciles de la propia
    cartera, no de numeros inventados. Los nombres los pone Jesus mirando los grupos.
  - REGLAS DE AJUSTE POR PERFIL: que se movio de verdad en cada situacion y que dio,
    agregando los casos reales.
  - INFORME DE CALIDAD DE DATOS: que se uso, que se ignoro y que falta. El doc es
    explicito: si un dato falta, se marca y se pregunta; no se rellena el hueco.

Recalcular:  python macro_indices.py
Tambien:     POST /admin/macro-indices/reconstruir
"""
import asyncio
import statistics
import sys
from typing import Dict, List, Optional

from core.database import db
import macro_casos

# Un cliente sin recorrido no dice nada: hacen falta unos cuantos ajustes para que
# el techo, el suelo y los umbrales signifiquen algo.
MIN_AJUSTES = 4
# Para el ritmo mensual y la distribucion, tramos de menos de 10 dias son ruido.
DIAS_MIN = 10


def _num(x) -> Optional[float]:
    return float(x) if isinstance(x, (int, float)) else None


def _hc_total(macros: Dict) -> Optional[float]:
    """HC total del dia de entreno = HC de entreno + HC de intra (el doc: se SUMAN)."""
    e = _num((macros.get("entreno") or {}).get("hidratos"))
    i = _num((macros.get("perientreno") or {}).get("hidratos")) or 0.0
    return None if e is None else e + i


def _mediana(xs: List[float]) -> Optional[float]:
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 2) if xs else None


# ---------------------------------------------------------------- camino y fases
def _puntos_del_camino(cliente: Dict) -> List[Dict]:
    """Un punto por ajuste, con lo que hace falta para medir: fecha, macros, HC total,
    peso mas cercano, % graso si consta y la fase que estaba vigente."""
    pts = []
    for a in cliente["ajustes"]:
        peso = macro_casos._peso_en(cliente["pesos"], a["fecha"]) or a.get("peso_registrado")
        reporte = macro_casos._reporte_cercano(cliente["reportes"], a["fecha"])
        pts.append({
            "fecha": a["fecha"],
            "macros": a["macros"],
            "hc_total": _hc_total(a["macros"]),
            "hc_entreno": _num((a["macros"].get("entreno") or {}).get("hidratos")),
            "peso": peso,
            # El % graso se mide con menos frecuencia que el peso: se acepta el mas
            # cercano dentro de mes y medio. Sin el no hay eje RESPONDEDOR.
            "body_fat": (a.get("body_fat") if a.get("body_fat") is not None
                         else macro_casos._peso_en(cliente.get("grasos") or [], a["fecha"], margen=45)),
            "fase": macro_casos._fase_de(reporte, cliente.get("goal")),
            "cumplimiento": (reporte or {}).get("cumplimiento_dieta"),
        })
    return [p for p in pts if p["hc_total"] is not None]


def _tramos(pts: List[Dict]) -> List[Dict]:
    """Tramos entre ajustes consecutivos, con dias y variacion de peso en % (nunca kg
    sueltos: el doc insiste en que el ritmo se lee en % del peso corporal)."""
    out = []
    for a, b in zip(pts, pts[1:]):
        dias = macro_casos._dias(a["fecha"], b["fecha"])
        if not dias or dias < DIAS_MIN or not a["peso"] or not b["peso"]:
            continue
        out.append({
            "desde": a, "hasta": b, "dias": dias,
            "delta_hc": round((b["hc_total"] or 0) - (a["hc_total"] or 0), 1),
            "delta_peso_pct": round((b["peso"] - a["peso"]) / a["peso"] * 100, 2),
        })
    return out


# ---------------------------------------------------------------- indices
def indices_de(cliente: Dict) -> Optional[Dict]:
    pts = _puntos_del_camino(cliente)
    if len(pts) < MIN_AJUSTES:
        return None
    tramos = _tramos(pts)
    con_peso = [p for p in pts if p["peso"]]
    if len(con_peso) < 2:
        return None

    # 5-7: HC por kilo en el arranque, en el TECHO (giro a definicion) y en el SUELO
    # (giro a volumen). La diferencia techo-suelo es el rango de tolerancia al hidrato.
    techo_p = max(con_peso, key=lambda p: p["hc_total"])
    suelo_p = min(con_peso, key=lambda p: p["hc_total"])
    arranque = con_peso[0]
    hc_kg = lambda p: round(p["hc_total"] / p["peso"], 2) if p["peso"] else None

    # 8: INDICE HIDRATO-GRASA = cuanto hidrato por kilo sostiene con que % graso.
    # Alto = come mucho y acumula poca grasa = buen respondedor. Es la metrica que
    # mejor clasifica segun el doc, y la que mas datos le faltan al historico.
    ihg = lambda p: (round(p["hc_total"] / p["peso"] / p["body_fat"] * 100, 2)
                     if p["peso"] and p["body_fat"] else None)

    # 19-22: macros de referencia. Los UMBRALES son donde deja de ser rentable la fase:
    # subir hidrato y que el peso no suba (volumen), bajarlo y que no baje (definicion).
    umbral_vol = [t["desde"]["hc_total"] for t in tramos
                  if t["delta_hc"] > 0 and t["delta_peso_pct"] <= 0]
    umbral_def = [t["desde"]["hc_total"] for t in tramos
                  if t["delta_hc"] < 0 and t["delta_peso_pct"] >= 0]

    # 11-18: indices de ciclo por fase (meses, % de peso y ritmo mensual).
    por_fase = {}
    for fase in ("definicion", "volumen"):
        tf = [t for t in tramos if t["desde"]["fase"] == fase]
        if not tf:
            continue
        dias = sum(t["dias"] for t in tf)
        pct = sum(t["delta_peso_pct"] for t in tf)
        por_fase[fase] = {
            "meses": round(dias / 30.0, 1),
            "delta_peso_pct": round(pct, 2),
            "ritmo_mensual_pct": round(pct / dias * 30, 2) if dias else None,
            "tramos": len(tf),
        }

    # 24: distribucion mensual. Que parte del cambio total se lleva cada mes: es lo que
    # dice si el volumen se ensucia al final o la definicion se frena.
    total_abs = sum(abs(t["delta_peso_pct"]) for t in tramos)
    distribucion = [round(abs(t["delta_peso_pct"]) / total_abs * 100, 1)
                    for t in tramos] if total_abs else []

    # 27: ratio de recomposicion (grasa perdida / peso perdido) en definicion. Necesita
    # % graso en dos momentos: hoy casi nadie lo tiene, y por eso va al informe.
    bf = [p for p in pts if p["body_fat"] and p["peso"]]
    recomposicion = None
    if len(bf) >= 2:
        p0, p1 = bf[0], bf[-1]
        grasa0 = p0["peso"] * p0["body_fat"] / 100
        grasa1 = p1["peso"] * p1["body_fat"] / 100
        dpeso = p1["peso"] - p0["peso"]
        if abs(dpeso) > 0.5:
            recomposicion = round((grasa1 - grasa0) / dpeso, 2)

    ultimo = con_peso[-1]
    m_ult = ultimo["macros"]
    g = lambda blq, c: _num((m_ult.get(blq) or {}).get(c))

    return {
        "client_id": cliente["client_id"],
        "sexo": cliente["sexo"],
        "n_ajustes": len(pts),
        "n_tramos": len(tramos),
        "periodo": [pts[0]["fecha"], pts[-1]["fecha"]],
        # 1-4 ratios macro/peso (con que densidad entra la comida)
        "proteina_entreno_kg": round(g("entreno", "proteina") / ultimo["peso"], 2) if g("entreno", "proteina") else None,
        "hc_entreno_kg": hc_kg(ultimo),
        "proteina_descanso_kg": round(g("descanso", "proteina") / ultimo["peso"], 2) if g("descanso", "proteina") else None,
        "hc_descanso_kg": round(g("descanso", "hidratos") / ultimo["peso"], 2) if g("descanso", "hidratos") else None,
        # 5-7 HC/kg en los giros
        "hc_kg_arranque": hc_kg(arranque),
        "hc_kg_techo": hc_kg(techo_p),
        "hc_kg_suelo": hc_kg(suelo_p),
        "rango_tolerancia_hc": round((techo_p["hc_total"] - suelo_p["hc_total"]), 1),
        # 8-10 indice hidrato-grasa (eficiencia del motor)
        "indice_hidrato_grasa_techo": ihg(techo_p),
        "indice_hidrato_grasa_actual": ihg(ultimo),
        # 11-18 ciclo
        "ciclo": por_fase,
        # 19-22 referencias
        "techo_hc": techo_p["hc_total"],
        "techo_fecha": techo_p["fecha"],
        "suelo_hc": suelo_p["hc_total"],
        "suelo_fecha": suelo_p["fecha"],
        "umbral_volumen": max(umbral_vol) if umbral_vol else None,
        "umbral_definicion": min(umbral_def) if umbral_def else None,
        # 24 y 27
        "distribucion_mensual": distribucion,
        "ratio_recomposicion": recomposicion,
        # peso y % graso de referencia
        "peso_actual": ultimo["peso"],
        "body_fat_actual": ultimo["body_fat"],
        "n_con_body_fat": len(bf),
    }


# ---------------------------------------------------------------- perfiles
def _tercil(valor: Optional[float], cortes) -> Optional[str]:
    if valor is None or not cortes:
        return None
    bajo, alto = cortes
    return "bajo" if valor <= bajo else ("alto" if valor >= alto else "medio")


def clasificar(indices: List[Dict]) -> List[Dict]:
    """Los dos ejes del doc. Los cortes son los terciles de la PROPIA cartera, por sexo
    (el doc: en mujeres los rangos son mas bajos y estrechos, no valen los mismos cortes).
    El respondedor manda sobre el motor cuando hay dato de los dos."""
    cortes = {}
    for sexo in {i["sexo"] for i in indices}:
        for eje, campo in (("motor", "hc_kg_techo"), ("respondedor", "indice_hidrato_grasa_techo")):
            vals = sorted(i[campo] for i in indices if i["sexo"] == sexo and i.get(campo))
            if len(vals) >= 6:
                cortes[(sexo, eje)] = (vals[len(vals) // 3], vals[2 * len(vals) // 3])

    for i in indices:
        motor = _tercil(i.get("hc_kg_techo"), cortes.get((i["sexo"], "motor")))
        resp = _tercil(i.get("indice_hidrato_grasa_techo"), cortes.get((i["sexo"], "respondedor")))
        i["perfil_motor"] = motor
        i["perfil_respondedor"] = resp or "sin_dato"
        # Etiqueta descriptiva, no un nombre inventado: los nombres los pone Jesus
        # cuando vea los grupos (paso 3 del doc).
        i["perfil"] = f"motor_{motor or 'sin_dato'}__respondedor_{resp or 'sin_dato'}"
    return indices


# ---------------------------------------------------------------- reglas por perfil
async def _reglas_por_perfil(perfil_por_cliente: Dict[str, str]) -> List[Dict]:
    """Que se hizo de verdad en cada situacion y que dio. Agrega los casos reales por
    perfil, fase y cumplimiento: el movimiento tipico de HC de entreno y el % de peso
    que vino despues. Es el paso 3 del doc, cuantificado."""
    grupos = {}
    async for c in db.macro_casos.find({}, {"_id": 0}):
        perfil = perfil_por_cliente.get(c.get("client_id"))
        if not perfil:
            continue
        cumple = (c.get("cumplimiento") or "").lower()
        if not cumple:
            nivel = "sin_reporte"
        elif "perfect" in cumple or "100" in cumple:
            nivel = "cumple"
        elif "no" in cumple or "mal" in cumple:
            nivel = "no_cumple"
        else:
            nivel = "parcial"
        mov = (c.get("movimiento") or {}).get("entreno", {}).get("hidratos", 0)
        k = (perfil, c.get("fase"), nivel)
        g = grupos.setdefault(k, {"movs": [], "resultados": [], "n": 0, "sin_tocar": 0})
        g["n"] += 1
        if mov:
            g["movs"].append(mov)
        else:
            g["sin_tocar"] += 1
        g["resultados"].append(c.get("delta_peso_pct"))

    reglas = []
    for (perfil, fase, nivel), g in grupos.items():
        if g["n"] < 5:      # con menos casos no es una regla, es una anecdota
            continue
        reglas.append({
            "perfil": perfil, "fase": fase, "cumplimiento": nivel, "n_casos": g["n"],
            "mov_hc_entreno_mediana": _mediana(g["movs"]),
            "pct_sin_tocar": round(g["sin_tocar"] / g["n"] * 100),
            "delta_peso_pct_mediana": _mediana(g["resultados"]),
        })
    reglas.sort(key=lambda r: (-r["n_casos"], r["perfil"]))
    return reglas


# ---------------------------------------------------------------- calidad de datos
def _informe_calidad(indices: List[Dict], descartados: Dict) -> Dict:
    """Lo que pide el doc: que se uso, que se ignoro y por que, y que falta. Sin esto,
    los perfiles parecen mas solidos de lo que son."""
    con_bf = [i for i in indices if i.get("indice_hidrato_grasa_techo") is not None]
    return {
        "clientes_con_indices": len(indices),
        "descartados": descartados,
        "con_body_fat_para_indice_hidrato_grasa": len(con_bf),
        "sin_body_fat": len(indices) - len(con_bf),
        "con_ratio_recomposicion": sum(1 for i in indices if i.get("ratio_recomposicion") is not None),
        "con_umbral_volumen": sum(1 for i in indices if i.get("umbral_volumen") is not None),
        "con_umbral_definicion": sum(1 for i in indices if i.get("umbral_definicion") is not None),
        "clasificados_por_respondedor": sum(1 for i in indices if i.get("perfil_respondedor") != "sin_dato"),
        "aviso": ("El indice hidrato-grasa necesita % graso por ajuste y el historico casi no lo "
                  "tiene: hasta que se acumule, el eje RESPONDEDOR queda sin dato en la mayoria y "
                  "la clasificacion se apoya sobre todo en el MOTOR."),
    }


# ---------------------------------------------------------------- reconstruccion
async def reconstruir() -> Dict:
    clientes = await macro_casos._cartera()
    indices, descartados = [], {"pocos_ajustes": 0, "sin_peso": 0}
    for c in clientes:
        ix = indices_de(c)
        if ix:
            indices.append(ix)
        elif len(c["ajustes"]) < MIN_AJUSTES:
            descartados["pocos_ajustes"] += 1
        else:
            descartados["sin_peso"] += 1

    clasificar(indices)
    perfil_por_cliente = {i["client_id"]: i["perfil"] for i in indices}
    reglas = await _reglas_por_perfil(perfil_por_cliente)

    if indices:
        await db.macro_indices_tmp.drop()
        await db.macro_indices_tmp.insert_many(indices)
        await db.macro_indices_tmp.create_index("client_id")
        try:
            await db.macro_indices_tmp.rename("macro_indices", dropTarget=True)
        except Exception:
            await db.macro_indices.delete_many({})
            await db.macro_indices.insert_many(indices)
            await db.macro_indices_tmp.drop()
    await db.macro_reglas.delete_many({})
    if reglas:
        await db.macro_reglas.insert_many(reglas)

    reparto = {}
    for i in indices:
        reparto[i["perfil"]] = reparto.get(i["perfil"], 0) + 1
    return {
        "clientes": len(clientes),
        "con_indices": len(indices),
        "reglas": len(reglas),
        "reparto_perfiles": dict(sorted(reparto.items(), key=lambda kv: -kv[1])),
        "calidad": _informe_calidad(indices, descartados),
    }


# Igual que el banco de casos: se rehace solo cuando cambia algo, en segundo plano y
# sin solaparse. Los indices dependen del mismo camino, asi que van juntos.
_reconstruyendo = asyncio.Lock()
_pendiente = False


async def refrescar_en_segundo_plano() -> None:
    global _pendiente
    if _reconstruyendo.locked():
        _pendiente = True
        return
    async with _reconstruyendo:
        while True:
            _pendiente = False
            try:
                await reconstruir()
            except Exception as e:
                print(f"[macro_indices] fallo al reconstruir indices/perfiles: {e}")
            if not _pendiente:
                return


# ---------------------------------------------------------------- consumo
async def perfil_de(client_id: str) -> Optional[Dict]:
    return await db.macro_indices.find_one({"client_id": client_id}, {"_id": 0})


async def reglas_de(perfil: str, fase: str) -> List[Dict]:
    cur = db.macro_reglas.find({"perfil": perfil, "fase": fase}, {"_id": 0}).sort("n_casos", -1)
    return [r async for r in cur]


def formatear_para_prompt(ix: Optional[Dict], reglas: List[Dict]) -> str:
    """El perfil y sus reglas, en el idioma del agente."""
    if not ix:
        return ""
    L = ["PERFIL DE ESTE CLIENTE (derivado de su propio camino, no del cuestionario):"]
    L.append(f"  motor={ix.get('perfil_motor') or 'sin dato'} (HC total de entreno por kg en su techo: "
             f"{ix.get('hc_kg_techo')}), respondedor={ix.get('perfil_respondedor')}"
             + (f" (indice hidrato-grasa en el techo: {ix['indice_hidrato_grasa_techo']})"
                if ix.get("indice_hidrato_grasa_techo") else " (sin % graso suficiente para medirlo)"))
    L.append(f"  su techo historico son {ix.get('techo_hc')} g de HC total ({ix.get('techo_fecha')}) y su "
             f"suelo {ix.get('suelo_hc')} g ({ix.get('suelo_fecha')}); rango de tolerancia {ix.get('rango_tolerancia_hc')} g.")
    if ix.get("umbral_volumen") or ix.get("umbral_definicion"):
        L.append(f"  umbrales observados: subir por encima de {ix.get('umbral_volumen')} g dejo de subirle el peso; "
                 f"bajar de {ix.get('umbral_definicion')} g dejo de bajarselo.")
    for fase, c in (ix.get("ciclo") or {}).items():
        L.append(f"  en {fase}: {c['meses']} meses acumulados, {c['delta_peso_pct']:+}% de peso "
                 f"({c['ritmo_mensual_pct']:+}% al mes).")
    if reglas:
        L.append("QUE SE HIZO CON CLIENTES DE SU MISMO PERFIL (mediana de casos reales):")
        for r in reglas[:4]:
            mov = r["mov_hc_entreno_mediana"]
            L.append(f"  - {r['fase']}, cumplimiento {r['cumplimiento']} ({r['n_casos']} casos): "
                     + (f"HC de entreno {mov:+g} g de mediana" if mov else "sin tocar el HC de entreno")
                     + f", en el {r['pct_sin_tocar']}% no se toco nada; el peso hizo "
                     f"{r['delta_peso_pct_mediana']:+}% despues.")
    return "\n".join(L)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    import json
    print(json.dumps(asyncio.run(reconstruir()), indent=2, ensure_ascii=False))
