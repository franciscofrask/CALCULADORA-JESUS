# -*- coding: utf-8 -*-
"""Muestra DIVERSA de clientes con historial de macros largo, para diseñar el motor
de re-ajuste sin sobreajustar a un solo cliente. Resume por perfil (sexo/objetivo)
la progresion de macros y peso."""
import asyncio, sys
sys.stdout.reconfigure(encoding="utf-8")
from core.database import db as m

def g(h, k):
    v = h.get(k); return int(v) if isinstance(v, (int, float)) else v

async def r():
    # clientes con >=5 ajustes y user enlazado, variados
    cur = m.calma_raw.find({"user_id": {"$ne": None}, "macros_historial.4": {"$exists": True}},
                           {"_id": 0, "email": 1, "sexo": 1, "formulario_inicial": 1,
                            "macros_historial": 1, "pesos": 1})
    docs = [d async for d in cur]
    docs.sort(key=lambda d: len(d.get("macros_historial") or []), reverse=True)
    print(f"clientes con >=5 ajustes: {len(docs)}")
    # reparto por sexo/objetivo
    import collections
    rep = collections.Counter()
    for d in docs:
        obj = ((d.get("formulario_inicial") or {}).get("objetivo") or "?").upper()[:3]
        rep[(d.get("sexo"), obj)] += 1
    print("reparto (sexo,objetivo):", dict(rep))

    # mostrar 6 variados: intenta 2 mujeres, 2 volumen, 2 definicion hombre
    def obj_of(d): return ((d.get("formulario_inicial") or {}).get("objetivo") or "").upper()
    sel = []
    def take(pred, n):
        c = 0
        for d in docs:
            if d in sel: continue
            if pred(d): sel.append(d); c += 1
            if c >= n: break
    take(lambda d: d.get("sexo") == "F", 2)
    take(lambda d: "VOLUMEN" in obj_of(d), 2)
    take(lambda d: d.get("sexo") == "M" and "DEFINI" in obj_of(d), 2)

    for d in sel:
        fi = d.get("formulario_inicial") or {}
        pesos = {p["fecha"]: p["valor"] for p in (d.get("pesos") or [])}
        print(f"\n===== {d['email']} | sexo {d.get('sexo')} | obj {fi.get('objetivo')} | estatura {fi.get('estatura')} =====")
        for h in (d.get("macros_historial") or []):
            f = h["fecha"]
            print(f"  {f} | E {g(h,'p_ent')}/{g(h,'h_ent')}/{g(h,'g_ent')}"
                  f" | Pe {g(h,'p_peri')}/{g(h,'h_peri')}"
                  f" | D {g(h,'p_desc')}/{g(h,'h_desc')}/{g(h,'g_desc')} | peso {pesos.get(f,'-')}")

asyncio.run(r())
