# -*- coding: utf-8 -*-
"""
Punto 4.10, segunda vuelta: probar los CUATRO caminos de rebote contra la API de verdad.

El guion:
  1. Se coge un cliente de prueba y se le pone plan `silver` (personalizado).
  2. El ADMIN le pone unos macros desde su calculadora (POST /admin/clients/{id}/calculator/apply),
     que es justo el camino que deja `macros_source: "auto"`.
  3. El CLIENTE intenta machacarlos por los cuatro caminos.
  4. Se comprueba que sus macros siguen siendo los que le puso el coach.

Se ejecuta con el backend local levantado.
"""
import io
import json
import sys

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

API = "http://localhost:8000/api"


def entrar(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    return r.json().get("access_token") if r.status_code == 200 else None


def macros_de(hc):
    r = requests.get(f"{API}/macros", headers=hc, timeout=30)
    if r.status_code != 200:
        return None
    d = r.json()
    t = d.get("training") or d.get("macros_training") or {}
    return (t.get("protein"), t.get("carbs"), t.get("fat"))


def linea(que, ok, extra=""):
    print(f"   {'BIEN' if ok else 'MAL '}  {que:52} {extra}")
    return ok


def main():
    admin = entrar("francisco@test.com", "demo123")
    cliente = entrar("clientedemo@test.com", "demo123")
    if not admin or not cliente:
        print("no pude entrar; ¿esta el backend local levantado?")
        return
    ha = {"Authorization": f"Bearer {admin}"}
    hc = {"Authorization": f"Bearer {cliente}"}

    perfil = requests.get(f"{API}/clients/profile", headers=hc, timeout=30).json()
    cid = perfil.get("id")
    print(f"cliente de prueba: {cid}  plan actual: {perfil.get('plan')}")

    # 1) plan personalizado
    r = requests.put(f"{API}/admin/clients/{cid}", json={"plan": "silver"}, headers=ha, timeout=30)
    print(f"   plan -> silver: {r.status_code}")

    # 2) el coach le pone macros DESDE SU CALCULADORA (el camino que deja macros_source 'auto')
    r = requests.post(f"{API}/admin/clients/{cid}/calculator/apply",
                      json={"peso": 80, "sexo": "hombre", "porcentaje_graso": 20,
                            "objetivo": "definicion", "criterio": "prueba 4.10"},
                      headers=ha, timeout=60)
    print(f"   el coach aplica macros desde su calculadora: {r.status_code}")
    del_coach = macros_de(hc)
    print(f"   macros que le deja el coach: {del_coach}")
    if not del_coach or del_coach[0] is None:
        print("   no pude dejar macros de partida; abandono")
        return

    print()
    print("=" * 78)
    print("LOS CUATRO CAMINOS DE REBOTE (y los dos de proposito, de paso)")
    print("=" * 78)
    todo_bien = True

    # A) PUT /clients/profile cambiando el peso
    r = requests.put(f"{API}/clients/profile", json={"weight": 95}, headers=hc, timeout=30)
    ahora = macros_de(hc)
    todo_bien &= linea("PUT /clients/profile (cambia su peso a 95)", ahora == del_coach,
                       f"{r.status_code} -> {ahora}")

    # B) POST /clients/mi-cuerpo
    r = requests.post(f"{API}/clients/mi-cuerpo",
                      json={"peso": 95, "altura": 178, "porcentaje_graso": 28},
                      headers=hc, timeout=30)
    ahora = macros_de(hc)
    todo_bien &= linea("POST /clients/mi-cuerpo", ahora == del_coach, f"{r.status_code} -> {ahora}")

    # C) POST /calculator/targets/apply  (el agujero grande: 403 con motivo)
    r = requests.post(f"{API}/calculator/targets/apply",
                      json={"peso": 95, "sexo": "hombre", "porcentaje_graso": 28,
                            "objetivo": "volumen"},
                      headers=hc, timeout=30)
    ahora = macros_de(hc)
    motivo = ""
    try:
        motivo = str(r.json().get("detail"))[:60]
    except Exception:
        pass
    todo_bien &= linea("POST /calculator/targets/apply", r.status_code == 403 and ahora == del_coach,
                       f"{r.status_code} -> {ahora}  {motivo}")

    # D) POST /clients/questionnaire (puede dar 409 si ya lo hizo: tambien vale)
    r = requests.post(f"{API}/clients/questionnaire",
                      json={"weight": 95, "body_fat": 28, "goal": "volumen", "sex": "hombre",
                            "height": 178, "birthdate": "1990-01-01",
                            "training_experience": "intermedio", "activity_level": "moderado",
                            "biotype": "mesomorfo"},
                      headers=hc, timeout=30)
    ahora = macros_de(hc)
    todo_bien &= linea("POST /clients/questionnaire", ahora == del_coach, f"{r.status_code} -> {ahora}")

    # E) y F) los dos de proposito, que ya estaban
    r = requests.put(f"{API}/macros",
                     json={"training": {"protein": 999, "carbs": 999, "fat": 99},
                           "rest": {"protein": 999, "carbs": 999, "fat": 99}},
                     headers=hc, timeout=30)
    ahora = macros_de(hc)
    todo_bien &= linea("PUT /macros (el guardado manual)", r.status_code == 403 and ahora == del_coach,
                       f"{r.status_code} -> {ahora}")

    r = requests.post(f"{API}/clients/ajustar-macros",
                      json={"actividad_diaria": "sedentario", "deporte_extra": "no",
                            "facilidad_engordar": "facil"},
                      headers=hc, timeout=30)
    ahora = macros_de(hc)
    todo_bien &= linea("POST /clients/ajustar-macros", r.status_code == 403 and ahora == del_coach,
                       f"{r.status_code} -> {ahora}")

    print()
    print("=" * 78)
    print("Y QUE AL QUE SI PUEDE NO SE LE HAYA CERRADO NADA")
    print("=" * 78)
    # Se le pasa a un plan de autogestion: ahi manda el cliente.
    #
    # OJO con donde se mira el resultado: `GET /macros` resuelve por `macro_history` (la
    # version vigente a cada fecha) y este endpoint solo escribe el PERFIL, sin versionar. Asi
    # que hay que mirar el perfil, no /macros, o parece que no ha hecho nada.
    requests.put(f"{API}/admin/clients/{cid}", json={"plan": "nivel1"}, headers=ha, timeout=30)
    r = requests.post(f"{API}/calculator/targets/apply",
                      json={"peso": 95, "sexo": "hombre", "porcentaje_graso": 28,
                            "objetivo": "volumen"},
                      headers=hc, timeout=30)
    pr = requests.get(f"{API}/clients/profile", headers=hc, timeout=30).json()
    t = pr.get("macros_training") or {}
    en_perfil = (t.get("protein"), t.get("carbs"), t.get("fat"))
    todo_bien &= linea("en plan de autogestion SI se los aplica",
                       r.status_code == 200 and en_perfil != del_coach,
                       f"{r.status_code} -> perfil {en_perfil}")

    print()
    print("TODO BIEN" if todo_bien else "*** HAY ALGUN CAMINO ABIERTO ***")


main()
