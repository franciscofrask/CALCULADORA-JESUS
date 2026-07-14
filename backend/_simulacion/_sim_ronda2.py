# -*- coding: utf-8 -*-
"""
RONDA 2 - Agentes caóticos (fuzzing adversario).
================================================
10 agentes que NO se comportan como usuarios que saben usar la app: lanzan secuencias
impredecibles para intentar ROMPER el sistema. Buscamos:

  - HTTP 500 (excepción no controlada del backend)  -> el objetivo principal
  - respuestas que ACEPTAN basura (200/201 con datos sin sentido) -> validación floja
  - filtración de trazas internas / detalles del servidor
  - inconsistencias de estado

Técnicas: tipos equivocados, campos faltantes/extra, inyección NoSQL ({"$gt":""}), XSS,
path traversal, números absurdos (negativos, enormes, NaN/inf como texto), fechas basura,
strings gigantes, unicode raro, métodos HTTP incorrectos, y llamadas FUERA DE ORDEN.

Para acotar efectos: solo endpoints por-usuario/por-cliente (los usuarios sim se borran al
final); los catálogos globales solo se LEEN. No corrige nada: reporta.

Ejecuta:  PYTHONUTF8=1 ./venv/Scripts/python.exe -m _simulacion._sim_ronda2 [--iter 400] [--seed 7]
"""
import os
import sys
import argparse
import random
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from _simulacion._core import Api, Persona, hallazgo, hallazgos, guardar_informe, PASSWORD, DOMINIO
from _simulacion._setup import registrar_y_preparar, activar_planes, limpiar


# ---------------------------------------------------------------- generadores de basura
BASURA_ESCALAR = [
    None, True, False, 0, -1, -999999, 999999999999, 1e308, "", " ",
    "0", "-5", "1e309", "NaN", "Infinity", "null", "undefined",
    "'; DROP TABLE users;--", "<script>alert(1)</script>", "../../etc/passwd",
    "%00", "", "😀" * 50, "A" * 5000, "。".join(["x"] * 100),
    {"$gt": ""}, {"$ne": None}, {"$where": "1==1"}, [1, 2, 3], {"a": {"b": {"c": 1}}},
    "2026-13-45", "no-soy-fecha", "0000-00-00", "2026/07/13", "1969-12-31T23:59:59Z",
]

FECHAS_BASURA = ["2026-13-45", "no-fecha", "0000-00-00", "2026/07/13", "'; --",
                 "../../secret", "9999-99-99", "", "{$gt:0}", "2026-02-30"]

CAMPOS_QUIZ = ["sex", "goal", "weight", "height", "body_fat", "birthdate",
               "training_experience", "activity_level", "biotype", "name", "phone"]


def rnd_escalar():
    return random.choice(BASURA_ESCALAR)


def rnd_body(campos):
    """Cuerpo aleatorio: subconjunto de campos con valores basura, a veces campos extra."""
    b = {}
    for c in campos:
        if random.random() < 0.7:
            b[c] = rnd_escalar()
    if random.random() < 0.3:
        b["campo_" + str(random.randint(0, 9))] = rnd_escalar()
    if random.random() < 0.15:
        return rnd_escalar()  # a veces ni siquiera un objeto
    return b


_VISTOS = set()  # dedup: un hallazgo por (metodo, ruta-normalizada, status)


def _ruta_norm(ruta):
    # Colapsa los ids variables para agrupar (/admin/clients/<x> -> /admin/clients/{id})
    import re
    r = ruta.split("?")[0]
    r = re.sub(r"/[^/]*\d[^/]*", "/{id}", r)
    return r


def registrar_resultado(agente, metodo, ruta, st, body):
    """Clasifica la respuesta a una petición caótica (deduplicado por endpoint+status)."""
    clave = (metodo, _ruta_norm(ruta), st)
    if clave in _VISTOS:
        return
    txt = str(body)[:200]
    if st == 500:
        _VISTOS.add(clave)
        hallazgo("BUG", "alta", f"500 en {metodo} {ruta}",
                 f"agente={agente}; el backend lanzó una excepción no controlada. Respuesta: {txt}",
                 f"{metodo} {ruta}", f"{metodo} /api{ruta} con payload caótico (ver seed)")
    elif st == 0:
        _VISTOS.add(clave)
        hallazgo("BUG", "media", f"Sin respuesta / caída en {metodo} {ruta}",
                 f"agente={agente}; {txt}", f"{metodo} {ruta}")
    elif isinstance(body, str) and ("Traceback" in body or 'File "' in body):
        _VISTOS.add(clave)
        hallazgo("SEGURIDAD", "media", f"Posible filtración de traza en {metodo} {ruta}",
                 f"agente={agente}; la respuesta contiene detalles internos: {txt}", f"{metodo} {ruta}")


# ---------------------------------------------------------------- acciones caóticas
def acciones_para(agente: Api, personas_cli: list, personas_all: list):
    """Devuelve una lista de closures; cada una hace UNA petición caótica y clasifica."""
    hoy = "2026-07-13"
    cli_ids = [p.profile_id for p in personas_cli if p.profile_id]
    user_ids = [p.user_id for p in personas_all if p.user_id]

    def do(metodo, ruta, **kw):
        st, body = agente.req(metodo, ruta, **kw)
        registrar_resultado(agente.etiqueta, metodo, ruta, st, body)
        return st, body

    acc = [
        # --- auth / cuenta ---
        lambda: do("POST", "/auth/register", auth=False, json_body=rnd_body(["email", "password", "name", "phone"])),
        lambda: do("POST", "/auth/login", auth=False, json_body={"email": rnd_escalar(), "password": rnd_escalar()}),
        lambda: do("POST", "/auth/change-password", json_body={"current_password": rnd_escalar(), "new_password": rnd_escalar()}),
        lambda: do("PUT", "/auth/me", json_body=rnd_body(["name", "phone"])),
        # --- perfil / cuestionario / macros (fuera de orden y con basura) ---
        lambda: do("POST", "/clients/questionnaire", json_body=rnd_body(CAMPOS_QUIZ)),
        lambda: do("PUT", "/clients/profile", json_body=rnd_body(["weight", "sex", "goal", "body_fat", "height", "age"])),
        lambda: do("PUT", "/macros", json_body=rnd_body(["training", "rest", "peri", "peso", "porcentaje_graso"])),
        lambda: do("GET", "/macros", params={"fecha": random.choice(FECHAS_BASURA)}),
        lambda: do("POST", "/user/preferences", json_body=rnd_body(["food_preferences", "avoided_categories", "avoided_keywords"])),
        lambda: do("PATCH", "/user/diet-config", json_body=rnd_body(["num_comidas", "opcion_peri", "momento_entreno"])),
        # --- dietas (fechas basura, cuerpos rotos) ---
        lambda: do("POST", "/diets", json_body={"fecha": random.choice(FECHAS_BASURA), "comidas": rnd_escalar()}),
        lambda: do("GET", f"/diets/{random.choice(FECHAS_BASURA)}"),
        lambda: do("DELETE", f"/diets/{random.choice(FECHAS_BASURA)}"),
        lambda: do("GET", f"/diets/calendar/{rnd_escalar()}/{rnd_escalar()}"),
        lambda: do("POST", "/diets/copy-day", json_body={"fecha_origen": random.choice(FECHAS_BASURA), "fecha_destino": rnd_escalar()}),
        lambda: do("POST", "/diets/copy", json_body=rnd_body(["source_date", "source_meal", "target_date", "target_meal"])),
        lambda: do("POST", "/diets/favorites", json_body=rnd_body(["name", "tipo_dia", "comidas"])),
        lambda: do("DELETE", f"/diets/favorites/{rnd_escalar()}"),
        lambda: do("PATCH", f"/diets/{random.choice(FECHAS_BASURA)}/targets", json_body={"distribution_targets": rnd_escalar()}),
        # --- favoritos (food_id inexistente / no numérico) ---
        lambda: do("POST", f"/favorites/{random.choice([999999999, -1, 0])}"),
        lambda: do("DELETE", f"/favorites/{random.randint(1, 5000)}"),
        # --- chatbot FUERA DE ORDEN (sin start/configure) y con basura ---
        lambda: do("POST", "/chatbot/configure", params={"session_id": rnd_escalar()}, json_body=rnd_body(["tipo_dia", "num_comidas", "opcion_peri", "momento_entreno", "single_meal"])),
        lambda: do("POST", "/chatbot/message", json_body={"session_id": rnd_escalar(), "message": rnd_escalar()}),
        lambda: do("POST", "/chatbot/save-to-diet", params={"session_id": rnd_escalar(), "fecha": random.choice(FECHAS_BASURA)}),
        lambda: do("POST", "/chatbot/complete-meal", params={"session_id": rnd_escalar()}),
        lambda: do("GET", "/chatbot/summary", params={"session_id": rnd_escalar()}),
        # --- reportes / checkins con basura ---
        lambda: do("POST", "/reports", json_body=rnd_body(["weight", "training_compliance", "sleep_quality", "energy_level", "stress_level", "notes", "measurements"])),
        lambda: do("POST", "/checkins", json_body=rnd_body(["type", "weight", "training_compliance", "energy_level"])),
        # --- mensajes (inyección en receiver_id / with_user) ---
        lambda: do("POST", "/messages", json_body={"receiver_id": rnd_escalar(), "content": rnd_escalar()}),
        lambda: do("GET", "/messages", params={"with_user": rnd_escalar()}),
        lambda: do("PUT", "/messages/read-all", params={"with_user": rnd_escalar()}),
        lambda: do("PUT", f"/messages/{rnd_escalar()}/read"),
        # --- billing (portal sin customer, checkout con plan basura) ---
        lambda: do("POST", "/billing/checkout-session", json_body={"plan": rnd_escalar()}),
        lambda: do("POST", "/billing/checkout-session/sync", json_body={"session_id": rnd_escalar()}),
        lambda: do("POST", "/billing/portal"),
        # --- notificaciones ---
        lambda: do("GET", "/notifications"),
        lambda: do("PUT", "/notifications/read-all"),
        # --- admin de solo lectura con ids basura (IDOR/500) ---
        lambda: do("GET", f"/admin/clients/{rnd_escalar()}"),
        lambda: do("GET", f"/admin/clients/{random.choice(cli_ids) if cli_ids else 'x'}/diet", params={"fecha": random.choice(FECHAS_BASURA)}),
        lambda: do("PUT", f"/admin/clients/{rnd_escalar()}/macros", json_body=rnd_body(["training", "rest"])),
        lambda: do("GET", f"/admin/clients/{rnd_escalar()}/health-score"),
        lambda: do("PUT", f"/admin/users/{rnd_escalar()}", json_body=rnd_body(["role", "plan", "email", "name"])),
        lambda: do("GET", "/admin/clients", params={"plan": rnd_escalar(), "trainer_id": rnd_escalar()}),
        # --- métodos incorrectos ---
        lambda: do(random.choice(["DELETE", "PATCH", "PUT"]), "/auth/me"),
        lambda: do(random.choice(["POST", "DELETE"]), "/macros"),
    ]
    return acc


# ---------------------------------------------------------------- main
async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iter", type=int, default=400, help="peticiones caóticas totales")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    random.seed(args.seed)

    # 10 agentes: 2 trainers + 6 clientes (autenticados) + 2 anónimos.
    personas = []
    for i in range(2):
        personas.append(Persona(idx=i, rol="trainer", nombre=f"Caos Trainer {i}",
                                 email=f"sim.r2trainer{i}@{DOMINIO}", telefono=f"6{i}0000000"))
    for i in range(6):
        personas.append(Persona(idx=i, rol="client", nombre=f"Caos Cliente {i}",
                                 email=f"sim.r2cliente{i}@{DOMINIO}", telefono=f"7{i}0000000",
                                 sexo="hombre" if i % 2 else "mujer", edad=25 + i, altura=170 + i,
                                 peso=70 + i, objetivo="definicion", actividad="moderado"))

    await registrar_y_preparar(personas)
    await activar_planes(personas)

    clientes = [p for p in personas if p.rol == "client"]
    agentes = [p.api for p in personas if p.api and p.api.token]
    # 2 anónimos (sin token)
    agentes += [Api("anon-A"), Api("anon-B")]

    print(f"\n== RONDA 2 (caos): {len(agentes)} agentes, {args.iter} peticiones, seed={args.seed} ==")
    for n in range(args.iter):
        agente = random.choice(agentes)
        accion = random.choice(acciones_para(agente, clientes, personas))
        try:
            accion()
        except Exception as e:
            hallazgo("BUG", "media", "El harness/servidor cortó la conexión de forma abrupta",
                     f"agente={agente.etiqueta}; excepción cliente: {type(e).__name__}: {e}", "")
        if (n + 1) % 100 == 0:
            print(f"  ... {n + 1}/{args.iter} peticiones")

    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_hallazgos_ronda2.json")
    guardar_informe(ruta)
    hs = hallazgos()
    # Resumen agrupado por endpoint para el informe
    print(f"\n== RONDA 2: {len(hs)} hallazgos. Guardado en {ruta} ==")


if __name__ == "__main__":
    asyncio.run(main())
