# -*- coding: utf-8 -*-
"""
Escenario de FLUJOS: cada persona recorre el sistema de punta a punta y se registran
los comportamientos inesperados como hallazgos. Cubre el ciclo del cliente, el del
entrenador/admin, y las interacciones entre ambos (chat, macros, asignación).

Ejecuta:  PYTHONUTF8=1 ./venv/Scripts/python.exe -m _simulacion._sim_flujos
"""
import os
import sys
import asyncio
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from _simulacion._core import (
    construir_personas, hallazgo, hallazgos, guardar_informe, es_ok,
)
from _simulacion._setup import registrar_y_preparar, activar_planes, limpiar

HOY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# Habilitaciones esperadas por plan (derivadas de PLAN_CATALOG con la lógica de
# deriveCapabilities: rutina cuenta si != 'ninguna'): (rutina, suplementacion, reportes)
GATING = {
    "reto12en12_gold":   (True, True, True),
    "reto12en12_silver": (True, True, True),
    "elm":               (True, False, False),   # rutina del_mes
    "reto60":            (True, False, False),   # rutina del_mes
    "mantenimiento":     (True, False, False),   # rutina 'opcional' => permitida
    "calculadora_jp":    (False, False, False),  # rutina 'ninguna' => bloqueada
}


def chk(cond, categoria, sev, titulo, detalle, endpoint="", repro=""):
    if not cond:
        hallazgo(categoria, sev, titulo, detalle, endpoint, repro)
    return cond


# ---------------------------------------------------------------- flujo cliente
async def flujo_cliente(c):
    a = c.api
    et = c.email.split("@")[0]

    # --- Estado inicial: /auth/me y /clients/profile
    st, me = a.get("/auth/me")
    chk(es_ok(st) and me.get("role") == "client", "BUG", "alta",
        f"/auth/me de {et} inesperado", f"status={st} body={me}", "GET /auth/me")

    st, prof = a.get("/clients/profile")
    if c.plan is None:
        chk(st == 404, "BUG", "media", f"Cliente sin plan {et}: /clients/profile no da 404",
            f"status={st}", "GET /clients/profile")
        return  # sin plan no hay más recorrido de cliente
    chk(es_ok(st), "BUG", "alta", f"{et} con plan no puede leer su perfil",
        f"status={st} body={prof}", "GET /clients/profile")

    # --- Cuestionario inicial (calcula macros)
    quiz = {
        "sex": c.sexo, "goal": c.objetivo, "weight": c.peso, "height": c.altura,
        "body_fat": 18 if c.sexo == "hombre" else 26,
        "birthdate": f"{datetime.now().year - c.edad}-05-15",
        "training_experience": "intermedio", "activity_level": c.actividad,
        "biotype": "mesomorfo", "name": c.nombre, "phone": c.telefono,
    }
    st, r = a.post("/clients/questionnaire", json_body=quiz)
    chk(es_ok(st), "BUG", "alta", f"Cuestionario de {et} falló",
        f"status={st} body={r}", "POST /clients/questionnaire")
    # repetir el cuestionario debe dar 409
    st2, _ = a.post("/clients/questionnaire", json_body=quiz)
    chk(st2 == 409, "BUG", "baja", f"Cuestionario repetible en {et}",
        f"segundo envío status={st2}", "POST /clients/questionnaire")

    # --- Macros calculados
    st, mac = a.get("/macros")
    tiene_macros = es_ok(st) and (mac.get("training", {}).get("protein", 0) > 0)
    chk(tiene_macros, "BUG", "alta", f"{et} sin macros tras cuestionario",
        f"status={st} body={mac}", "GET /macros")

    # --- Preferencias (mínimo 3)
    st, _ = a.post("/user/preferences", json_body={
        "food_preferences": ["2", "3", "7", "11"], "avoided_categories": [],
        "avoided_keywords": ["cerdo"],
    })
    chk(es_ok(st), "BUG", "media", f"Guardar preferencias falló en {et}",
        f"status={st}", "POST /user/preferences")
    # menos de 3 debe fallar
    st_bad, _ = a.post("/user/preferences", json_body={"food_preferences": ["2"]})
    chk(st_bad == 400, "BUG", "baja", f"Preferencias acepta <3 en {et}",
        f"status={st_bad}", "POST /user/preferences")

    # --- Ajustar macros manualmente
    st, _ = a.put("/macros", json_body={
        "training": {"protein": 180, "carbs": 200, "fat": 60},
        "rest": {"protein": 170, "carbs": 120, "fat": 60},
        "peri": {"protein": 40, "carbs": 40},
        "peso": c.peso, "porcentaje_graso": 18, "sexo": c.sexo, "objetivo": c.objetivo,
        "note": "ajuste simulación",
    })
    chk(es_ok(st), "BUG", "media", f"PUT /macros falló en {et}", f"status={st}", "PUT /macros")

    # --- Montar y guardar una dieta del día
    st, _ = a.patch("/user/diet-config", json_body={"num_comidas": 4, "opcion_peri": "intra_post", "momento_entreno": 1})
    dieta = {
        "fecha": HOY, "tipo_dia": "entrenamiento",
        "comidas": {
            "C1": {"alimentos": [{"nombre": "Pechuga de pollo", "cantidad_g": 200,
                                  "macros_efectivos": {"P": 40, "H": 0, "G": 2}}]},
        },
    }
    st, r = a.post("/diets", json_body=dieta)
    chk(es_ok(st), "BUG", "alta", f"Guardar dieta falló en {et}",
        f"status={st} body={r}", "POST /diets")
    st, r = a.get(f"/diets/{HOY}")
    chk(es_ok(st), "BUG", "media", f"Leer dieta del día falló en {et}",
        f"status={st}", "GET /diets/{fecha}")
    st, r = a.get(f"/diets/calendar/{HOY[:4]}/{int(HOY[5:7])}")
    chk(es_ok(st), "BUG", "baja", f"Calendario de dietas falló en {et}", f"status={st}",
        "GET /diets/calendar")

    # --- Chatbot completo
    await flujo_chatbot(c)

    # --- Reportes y check-ins (según gating)
    rutina_ok, sup_ok, rep_ok = GATING.get(c.plan, (False, False, False))

    st_rep, _ = a.post("/reports", json_body={
        "weight": c.peso, "training_compliance": 90, "nutrition_compliance": 85,
        "sleep_quality": 7, "energy_level": 8, "stress_level": 3, "notes": "sim",
    })
    if rep_ok:
        chk(es_ok(st_rep), "BUG", "media", f"Crear reporte falló en {et}", f"status={st_rep}", "POST /reports")
    else:
        # El plan NO incluye reportes: si la API igual lo acepta, el gating es solo de UI.
        chk(not es_ok(st_rep), "SEGURIDAD", "media",
            f"{et} ({c.plan}) sin reportes puede crear reporte por API (gating solo en UI)",
            f"status={st_rep}", "POST /reports",
            repro=f"login {c.email} y POST /api/reports")

    st_chk, _ = a.post("/checkins", json_body={
        "type": "weekly", "weight": c.peso, "training_compliance": 90,
        "energy_level": 8, "sleep_quality": 7, "stress_level": 3,
    })
    if rep_ok:
        chk(es_ok(st_chk), "BUG", "media", f"Crear check-in falló en {et}", f"status={st_chk}", "POST /checkins")
    else:
        chk(not es_ok(st_chk), "SEGURIDAD", "media",
            f"{et} ({c.plan}) sin reportes puede crear check-in por API (gating solo en UI)",
            f"status={st_chk}", "POST /checkins",
            repro=f"login {c.email} y POST /api/checkins")

    # --- Gating de rutina y suplementos
    st_r, _ = a.get("/routines/current")
    if rutina_ok:
        chk(st_r != 403, "BUG", "media", f"{et} ({c.plan}) DEBERÍA tener rutina y da 403",
            f"status={st_r}", "GET /routines/current")
    else:
        chk(st_r == 403, "SEGURIDAD", "media", f"{et} ({c.plan}) NO debería ver rutina pero da {st_r}",
            f"status={st_r}", "GET /routines/current",
            repro=f"login {c.email} y GET /api/routines/current")

    st_s, _ = a.get("/supplements/current")
    if sup_ok:
        chk(st_s != 403, "BUG", "media", f"{et} ({c.plan}) DEBERÍA tener suplementos y da 403",
            f"status={st_s}", "GET /supplements/current")
    else:
        chk(st_s == 403, "SEGURIDAD", "media", f"{et} ({c.plan}) NO debería ver suplementos pero da {st_s}",
            f"status={st_s}", "GET /supplements/current",
            repro=f"login {c.email} y GET /api/supplements/current")

    # --- Mensaje al entrenador (el front manda receiver_id="support", que el backend
    #     resuelve al coach del cliente). Nota: el modelo MessageCreate exige receiver_id
    #     aunque el resolver está escrito para aceptar None -> inconsistencia (registrada aparte).
    st, r = a.post("/messages", json_body={"receiver_id": "support",
                                           "content": f"Hola, soy {c.nombre}, ¿revisas mi dieta?"})
    chk(es_ok(st), "BUG", "media", f"Enviar mensaje al coach falló en {et}",
        f"status={st} body={r}", "POST /messages")


async def flujo_chatbot(c):
    a = c.api
    et = c.email.split("@")[0]
    st, r = a.post("/chatbot/start")
    if not es_ok(st):
        hallazgo("BUG", "alta", f"chatbot/start falló en {et}", f"status={st} body={r}", "POST /chatbot/start")
        return
    sid = r.get("session_id")
    c.chat_session = sid
    st, r = a.post("/chatbot/configure", params={"session_id": sid}, json_body={
        "tipo_dia": "entrenamiento", "num_comidas": 3, "momento_entreno": 0, "opcion_peri": "solo_post",
    })
    chk(es_ok(st), "BUG", "media", f"chatbot/configure falló en {et}", f"status={st}", "POST /chatbot/configure")
    for msg in ["pollo con arroz y aceite", "un yogur con nueces", "qué me falta"]:
        st, r = a.post("/chatbot/message", json_body={"session_id": sid, "message": msg})
        chk(es_ok(st), "BUG", "media", f"chatbot/message falló en {et}", f"status={st} msg={msg}",
            "POST /chatbot/message")
    st, r = a.post("/chatbot/suggest-foods", params={"session_id": sid})
    chk(es_ok(st), "BUG", "baja", f"suggest-foods falló en {et}", f"status={st}", "POST /chatbot/suggest-foods")


# ---------------------------------------------------------------- flujo trainer/admin
async def flujo_trainer(t, admin_api):
    a = t.api
    et = t.email.split("@")[0]

    # Lista de clientes que ve el trainer
    st, clientes = a.get("/admin/clients")
    chk(es_ok(st), "BUG", "alta", f"{et} no puede listar clientes", f"status={st}", "GET /admin/clients")

    # Dashboard stats (admin+trainer)
    st, stats = a.get("/admin/dashboard-stats")
    chk(es_ok(st), "BUG", "baja", f"{et} dashboard-stats falló", f"status={st}", "GET /admin/dashboard-stats")

    # Bandeja de conversaciones
    st, _ = a.get("/messages/conversations")
    chk(es_ok(st), "BUG", "baja", f"{et} conversaciones falló", f"status={st}", "GET /messages/conversations")

    # Listar entrenadores
    st, _ = a.get("/admin/trainers")
    chk(es_ok(st), "BUG", "baja", f"{et} listar trainers falló", f"status={st}", "GET /admin/trainers")


async def flujo_interaccion(cliente, trainer):
    """El trainer edita macros de SU cliente y le responde por chat."""
    a = trainer.api
    et = trainer.email.split("@")[0]
    if not cliente.profile_id:
        return
    # Editar macros del cliente asignado
    st, r = a.put(f"/admin/clients/{cliente.profile_id}/macros", json_body={
        "training": {"protein": 190, "carbs": 210, "fat": 55},
        "rest": {"protein": 175, "carbs": 130, "fat": 55},
        "note": "ajuste del coach (sim)",
    })
    chk(es_ok(st), "BUG", "media", f"{et} no pudo editar macros de su cliente",
        f"status={st} body={r}", "PUT /admin/clients/{id}/macros")

    # Ver la ficha del cliente
    st, ficha = a.get(f"/admin/clients/{cliente.profile_id}")
    chk(es_ok(st), "BUG", "media", f"{et} no pudo abrir ficha de su cliente",
        f"status={st}", "GET /admin/clients/{id}")

    # Responder por chat al cliente
    st, r = a.post("/messages", json_body={
        "receiver_id": cliente.user_id, "content": f"Hola {cliente.nombre}, te he ajustado los macros."})
    chk(es_ok(st), "BUG", "media", f"{et} no pudo escribir a su cliente",
        f"status={st} body={r}", "POST /messages")


# ---------------------------------------------------------------- main
async def main():
    personas = construir_personas()
    await registrar_y_preparar(personas)
    await activar_planes(personas)

    clientes = [p for p in personas if p.rol == "client"]
    trainers = [p for p in personas if p.rol == "trainer"]

    # Inconsistencia detectada: POST /messages sin receiver_id da 422 aunque _resolve_receiver
    # está escrito para aceptar None. El front lo salva mandando "support".
    hallazgo("BUG", "baja", "MessageCreate.receiver_id obligatorio pese a resolver que acepta None",
             "POST /api/messages sin receiver_id -> 422 (Field required); el resolver _resolve_receiver "
             "tiene una rama para None/'support' que queda muerta. Hacer receiver_id Optional en el modelo.",
             "POST /messages")

    print("\n== FLUJO CLIENTE ==")
    for c in clientes:
        await flujo_cliente(c)

    print("\n== FLUJO ENTRENADOR/ADMIN ==")
    for t in trainers:
        await flujo_trainer(t, None)

    print("\n== INTERACCIONES CLIENTE<->ENTRENADOR ==")
    # cada cliente con plan y su trainer asignado
    by_id = {t.user_id: t for t in trainers}
    for c in clientes:
        t = by_id.get(c.trainer_id)
        if t and c.profile_id:
            await flujo_interaccion(c, t)

    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_hallazgos_flujos.json")
    guardar_informe(ruta)
    hs = hallazgos()
    print(f"\n== FLUJOS: {len(hs)} hallazgos. Guardado en {ruta} ==")


if __name__ == "__main__":
    asyncio.run(main())
