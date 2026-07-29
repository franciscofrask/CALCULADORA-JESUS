# -*- coding: utf-8 -*-
"""Valida el agente de ajuste replayeando meses reales de un cliente de calma_raw:
para el mes N, le da el contexto hasta N y compara su propuesta con lo que Jesus
hizo de verdad en N+1."""
import asyncio, sys, os
sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv; load_dotenv(".env")
from core.database import db as m
import macro_agent as A

EMAIL = sys.argv[1] if len(sys.argv) > 1 else "ignaciocantalapiedra@hotmail.com"

def mk_macros(h):
    return {"entreno": {"proteina": h.get("p_ent"), "hidratos": h.get("h_ent"), "grasa": h.get("g_ent")},
            "perientreno": {"proteina": h.get("p_peri"), "hidratos": h.get("h_peri")},
            "descanso": {"proteina": h.get("p_desc"), "hidratos": h.get("h_desc"), "grasa": h.get("g_desc")}}

def fase_de(rep):
    ot = ((rep.get("objetivo") or {}).get("texto") or "").lower()
    return "volumen" if "volumen" in ot else "definicion"

def reporte_natural(rep):
    f = lambda k: (rep.get(k) or {}).get("texto") if isinstance(rep.get(k), dict) else rep.get(k)
    return {k: v for k, v in {
        "cumplimiento_dieta": f("cumplimientoDieta"),
        "esfuerzo_dieta": f("esfuerzoParaCumplirDieta"),
        "cumplimiento_entreno": f("cumplimientoEntrenamiento"),
        "cardio": f("cumplimientoCardio"),
        "descanso": f("descanso"),
        "suplementacion": f("suplementacion"),
        "objetivo": f("objetivo"),
        "problemas_entreno": rep.get("problemasParaEntrenar"),
        "comentario": rep.get("comentarioCliente"),
        "peso": rep.get("peso"),
    }.items() if v not in (None, "")}

async def main():
    d = await m.calma_raw.find_one({"email": EMAIL}, {"_id": 0})
    H = sorted([h for h in (d.get("macros_historial") or []) if h.get("fecha")], key=lambda x: x["fecha"])
    pesos = sorted([(p["fecha"], p["valor"]) for p in (d.get("pesos") or [])], key=lambda x: x[0])
    reps = sorted([r for r in (d.get("formularios_mensuales") or []) if r.get("fecha")], key=lambda x: x["fecha"])
    sexo = "mujer" if d.get("sexo") == "F" else "hombre"
    print(f"=== {EMAIL} | sexo {sexo} | {len(H)} ajustes ===\n")

    # transiciones a probar: las ultimas 5 (donde hay reporte en el ciclo)
    objetivos = []
    resultados = []
    for i in range(1, len(H) - 1):
        a, b = H[i], H[i + 1]
        rep = next((r for r in reps if a["fecha"] < r["fecha"] <= b["fecha"]), None)
        if not rep:
            continue
        resultados.append((i, a, b, rep))
    for i, a, b, rep in resultados[-5:]:
        fase = fase_de(rep)
        # meses en fase (consecutivos con misma fase)
        peso_hist = [(p, w) for p, w in pesos if p <= a["fecha"]]
        # historial de esta persona hasta a (para aprender su patron)
        hist = []
        wmap = dict(pesos)
        for h in H[:i + 1]:
            r_ = next((r for r in reps if r["fecha"] <= h["fecha"]), None)
            hist.append({"fecha": h["fecha"], "macros": mk_macros(h),
                         "peso": wmap.get(h["fecha"]),
                         "cumplimiento": ((r_ or {}).get("cumplimientoDieta") or {}).get("texto")})
        ctx = A.construir_contexto(
            macros_actuales=mk_macros(a), sexo=sexo, fase=fase,
            evolucion_peso=[{"fecha": p, "peso": w} for p, w in peso_hist],
            reporte=reporte_natural(rep), historial_ajustes=hist)
        out = await A.sugerir_ajuste(ctx)
        real = mk_macros(b)
        prop = out.get("propuesta", {})
        def he(mm): return (mm.get("entreno") or {}).get("hidratos")
        print(f"--- ajuste {a['fecha']} -> {b['fecha']} | fase {fase} | reporte dieta: {reporte_natural(rep).get('cumplimiento_dieta')} | peso {rep.get('peso')} ---")
        print(f"  ACTUAL (Jesus):  {A.formatear_macros(real)}")
        print(f"  AGENTE gpt-5.1:  {A.formatear_macros(prop) if prop else out}")
        # comparacion de direccion en HC entreno
        ha, hr, hp = he(mk_macros(a)), he(real), he(prop)
        def dirn(base, x): return "sube" if x is not None and x - base >= 5 else "baja" if x is not None and x - base <= -5 else "igual"
        print(f"  HC entreno: actual={ha} -> Jesus {hr} ({dirn(ha,hr)}) | agente {hp} ({dirn(ha,hp)}) | MISMA DIR: {dirn(ha,hr)==dirn(ha,hp)}")
        print(f"  razonamiento: {out.get('razonamiento','')[:220]}")
        if out.get("avisos"): print(f"  avisos: {out.get('avisos')}")
        warns = A.validar(prop, mk_macros(a), out.get("avisos", [])) if prop else []
        if warns: print(f"  GUARDARRAIL: {warns}")
        print()

asyncio.run(main())
