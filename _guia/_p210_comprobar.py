# -*- coding: utf-8 -*-
"""Punto 210: comprueba contra la API que /diets/recent ya no ofrece dias futuros.

Entra con clientedemo@test.com (que tiene 8 dias con fecha por delante de hoy) y pide la
lista tal y como la pide la pantalla del dia vacio: limit=14 y para=<dia abierto>.
"""
import os, sys, requests, json

API = os.environ.get("API", "http://127.0.0.1:8000/api")
EMAIL = "clientedemo@test.com"
CLAVE = "demo123"
HOY = "2026-08-28"


def entrar():
    r = requests.post(f"{API}/auth/login", json={"email": EMAIL, "password": CLAVE}, timeout=20)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def main():
    cab = entrar()
    for para in (HOY, "2026-08-24"):
        r = requests.get(f"{API}/diets/recent", params={"limit": 14, "para": para},
                         headers=cab, timeout=60)
        r.raise_for_status()
        dias = r.json().get("diets") or []
        futuros = [d["fecha"] for d in dias if d["fecha"] > para]
        print(f"\npara={para}  ->  {len(dias)} dias")
        print("  fechas:", ", ".join(d["fecha"] for d in dias))
        print("  POR DELANTE DEL DIA ABIERTO:", futuros or "ninguno  OK")
        for d in dias[:5]:
            nc = sum(1 for v in (d.get("comidas") or {}).values() if (v or {}).get("alimentos"))
            print(f"    {d['fecha']}  {d.get('tipo_dia'):<14} {nc} comidas  "
                  f"macros={d.get('macros')}  encaja={d.get('encaja')}")


main()


# Segunda pasada: con hoy_cliente, que es el techo de verdad (punto 210).
print("\n\n=== con hoy_cliente (el techo real) ===")
cab = entrar()
for para in (HOY, "2026-08-24", "2026-08-30"):
    r = requests.get(f"{API}/diets/recent",
                     params={"limit": 14, "para": para, "hoy_cliente": HOY},
                     headers=cab, timeout=60)
    r.raise_for_status()
    dias = r.json().get("diets") or []
    futuros = [d["fecha"] for d in dias if d["fecha"] > HOY]
    print(f"\npara={para}  hoy_cliente={HOY}  ->  {len(dias)} dias")
    print("  fechas:", ", ".join(d["fecha"] for d in dias))
    print("  POR DELANTE DE HOY:", futuros or "ninguno  OK")
