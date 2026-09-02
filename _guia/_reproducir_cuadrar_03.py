# -*- coding: utf-8 -*-
"""El caso 03 con la cuenta de la revision: C1 = 50P / 30H / 10G."""
import json, urllib.request
BASE = "http://127.0.0.1:8000/api"

def pedir(ruta, token=None, metodo="GET", cuerpo=None):
    req = urllib.request.Request(BASE + ruta, method=metodo)
    req.add_header("Content-Type", "application/json")
    if token: req.add_header("Authorization", "Bearer " + token)
    d = json.dumps(cuerpo).encode() if cuerpo is not None else None
    with urllib.request.urlopen(req, d, timeout=60) as r:
        return json.loads(r.read().decode())

t = pedir("/auth/login", metodo="POST",
          cuerpo={"email": "francisco@test.com", "password": "demo123"})["access_token"]
POLLO, ARROZ = 119, 1657

def efectivos(aid, g):
    e = pedir("/calculator/macros-efectivos", t, "POST",
              {"alimento_id": aid, "cantidad_g": g, "es_vegano": False})["efectivos"]
    return {"P": e["P"], "H": e["H"], "G": e["G"]}

base = {"fecha": "2026-09-02", "tipo_dia": "entrenamiento", "num_comidas": 4,
        "momento_entreno": 1, "opcion_peri": "intra_post"}
o = {"P": 50.0, "H": 30.0, "G": 10.0}
print(f"objetivo C1: {o}\n")
for arroz_g in (25, 35, 45, 60, 100):
    a1, a2 = efectivos(POLLO, 250), efectivos(ARROZ, arroz_g)
    antes = {k: round(a1[k] + a2[k], 1) for k in "PHG"}
    r = pedir("/calculator/refit-diet", t, "POST", {**base, "comidas": {"C1": {"alimentos": [
        {"alimento_id": POLLO, "nombre": "Pollo", "cantidad_g": 250},
        {"alimento_id": ARROZ, "nombre": "Arroz", "cantidad_g": arroz_g}]}}})
    sal = (r.get("comidas") or {}).get("C1", {}).get("alimentos") or []
    desp = {k: round(sum(a["macros_efectivos"][k] for a in sal), 1) for k in "PHG"}
    gramos = ", ".join(f"{a['nombre'][:12]} {a['cantidad_g']:g}" for a in sal)
    da = sum(abs(antes[k] - o[k]) for k in "PHG")
    dd = sum(abs(desp[k] - o[k]) for k in "PHG")
    marca = "  <-- PEOR" if dd > da + 0.5 else ""
    print(f"arroz {arroz_g:3} g")
    print(f"   antes    {antes}  desvio {da:5.1f}")
    print(f"   despues  {desp}  desvio {dd:5.1f}   [{gramos}]{marca}")
    print(f"   desfase  {r.get('desfases', {}).get('C1')}")
