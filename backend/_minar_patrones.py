# -*- coding: utf-8 -*-
"""Mina los historicos de calma_raw para extraer los patrones REALES de ajuste de
macros de Jesus (para fundar el motor en datos, no en un solo cliente).

Por cada par de ajustes consecutivos (mes N -> N+1) saca:
 - deltas de cada macro (E/Pe/D  P/H/G)
 - tendencia de peso en ese ciclo (usando pesos por fecha)
 - cumplimiento de dieta del reporte de ese ciclo (nota A/B/C/I)
Y agrega: estabilidad de proteina, tamanos de escalon, direccion segun
peso x cumplimiento, suelos/techos por sexo, valores de peri.
"""
import asyncio, sys, collections, statistics
sys.stdout.reconfigure(encoding="utf-8")
from core.database import db as m

def num(v):
    return float(v) if isinstance(v, (int, float)) else None

def norm_cumpl(nota, texto):
    t = (texto or "").lower()
    if nota == "A": return "bien"
    if nota == "B": return "regular"
    if nota == "C": return "mal"
    if nota == "I" or "mant" in t or "nada" in t: return "mantener"
    return None

async def main():
    docs = [d async for d in m.calma_raw.find(
        {"user_id": {"$ne": None}, "macros_historial.1": {"$exists": True}},
        {"_id": 0, "email": 1, "sexo": 1, "macros_historial": 1, "pesos": 1, "formularios_mensuales": 1})]
    print(f"clientes con >=2 ajustes: {len(docs)}")

    dprot = []        # deltas de proteina entreno (para ver estabilidad)
    dprot_desc = []
    step_h_ent, step_h_desc, step_g_ent, step_g_desc = [], [], [], []
    peri_h_vals = collections.Counter()
    # direccion HC entreno segun (fase, peso, cumplimiento)
    cross = collections.defaultdict(lambda: collections.Counter())  # (fase,trend,cumpl) -> {sube,baja,igual}
    step_by_fase = collections.defaultdict(list)  # fase -> deltas HC entreno
    # suelos/techos por sexo (min/max de HC entreno por cliente)
    floors = collections.defaultdict(list); ceils = collections.defaultdict(list)
    n_ajustes = 0; n_prot_cambia = 0

    for d in docs:
        sexo = d.get("sexo")
        H = [h for h in (d.get("macros_historial") or []) if h.get("fecha")]
        H.sort(key=lambda h: h["fecha"])
        pesos = {p["fecha"]: p["valor"] for p in (d.get("pesos") or [])}
        reps = sorted([r for r in (d.get("formularios_mensuales") or []) if r.get("fecha")], key=lambda r: r["fecha"])
        # techo/suelo de HC entreno de este cliente
        he_vals = [num(h.get("h_ent")) for h in H if num(h.get("h_ent")) is not None]
        if he_vals:
            floors[sexo].append(min(he_vals)); ceils[sexo].append(max(he_vals))

        for i in range(len(H) - 1):
            a, b = H[i], H[i + 1]
            n_ajustes += 1
            # proteina
            pe0, pe1 = num(a.get("p_ent")), num(b.get("p_ent"))
            if pe0 is not None and pe1 is not None:
                dprot.append(pe1 - pe0)
                if pe1 != pe0: n_prot_cambia += 1
            pd0, pd1 = num(a.get("p_desc")), num(b.get("p_desc"))
            if pd0 is not None and pd1 is not None: dprot_desc.append(pd1 - pd0)
            # escalones (solo no nulos)
            for k, arr in (("h_ent", step_h_ent), ("h_desc", step_h_desc), ("g_ent", step_g_ent), ("g_desc", step_g_desc)):
                v0, v1 = num(a.get(k)), num(b.get(k))
                if v0 is not None and v1 is not None and v1 != v0:
                    arr.append(round(v1 - v0))
            if num(b.get("h_peri")) is not None: peri_h_vals[int(num(b.get("h_peri")))] += 1

            # tendencia de peso en el ciclo (a.fecha -> b.fecha)
            wa, wb = pesos.get(a["fecha"]), pesos.get(b["fecha"])
            trend = None
            if isinstance(wa, (int, float)) and isinstance(wb, (int, float)) and 40 < wa < 250 and 40 < wb < 250:
                dw = wb - wa
                trend = "sube" if dw >= 0.5 else "baja" if dw <= -0.5 else "igual"
            # cumplimiento y OBJETIVO(fase) del reporte de ese ciclo (fecha entre a y b)
            cumpl = None; fase = None
            for r in reps:
                if a["fecha"] < r["fecha"] <= b["fecha"]:
                    cd = r.get("cumplimientoDieta") or {}
                    cumpl = norm_cumpl(cd.get("nota"), cd.get("texto"))
                    ot = ((r.get("objetivo") or {}).get("texto") or "").lower()
                    fase = "volumen" if "volumen" in ot else "definicion" if "defin" in ot else None
            # direccion HC entreno
            he0, he1 = num(a.get("h_ent")), num(b.get("h_ent"))
            if he0 is not None and he1 is not None:
                dirn = "sube" if he1 - he0 >= 5 else "baja" if he1 - he0 <= -5 else "igual"
                if fase:
                    step_by_fase[fase].append(round(he1 - he0))
                if fase and trend and cumpl:
                    cross[(fase, trend, cumpl)][dirn] += 1

    def dist(arr):
        if not arr: return "sin datos"
        c = collections.Counter(arr)
        top = ", ".join(f"{k:+d}:{v}" for k, v in sorted(c.items()))
        return f"n={len(arr)} media={statistics.mean(arr):+.1f} | {top}"

    print(f"\n=== PROTEINA (estabilidad) ===")
    print(f"ajustes totales: {n_ajustes} | proteina entreno CAMBIA en {n_prot_cambia} ({100*n_prot_cambia/max(n_ajustes,1):.0f}%)")
    print("delta proteina entreno:", dist([int(x) for x in dprot]))
    print("delta proteina descanso:", dist([int(x) for x in dprot_desc]))

    print(f"\n=== ESCALONES (solo cambios, g) ===")
    print("HC entreno:", dist(step_h_ent))
    print("HC descanso:", dist(step_h_desc))
    print("Grasa entreno:", dist(step_g_ent))
    print("Grasa descanso:", dist(step_g_desc))
    print("Peri HC (valores usados):", dict(peri_h_vals.most_common()))

    print(f"\n=== ESCALON HC entreno POR FASE (solo cambios) ===")
    for f in ("definicion", "volumen"):
        arr = [x for x in step_by_fase.get(f, []) if x != 0 and abs(x) < 300]
        print(f"  {f}: {dist(arr)}")

    print(f"\n=== DIRECCION HC entreno segun FASE x PESO x CUMPLIMIENTO (clave: pautado-vs-real) ===")
    for f in ("definicion", "volumen"):
        print(f"  --- {f.upper()} ---   {'(peso, cumpl)':26} | sube  baja  igual  (n)")
        for key in sorted(k for k in cross if k[0] == f):
            c = cross[key]; tot = sum(c.values())
            print(f"{'':26}{str((key[1], key[2])):28} | {c['sube']:4}  {c['baja']:4}  {c['igual']:4}   ({tot})")

    print(f"\n=== SUELO/TECHO de HC entreno por sexo (mediana entre clientes) ===")
    for s in ("M", "F"):
        if floors.get(s):
            print(f"  {s}: suelo(min) mediana {statistics.median(floors[s]):.0f} | techo(max) mediana {statistics.median(ceils[s]):.0f} | n={len(floors[s])}")

asyncio.run(main())
