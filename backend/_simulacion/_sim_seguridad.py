# -*- coding: utf-8 -*-
"""
Escenario de SEGURIDAD: matriz de ataques de autorización sobre el sistema ya poblado.
Prueba en vivo lo que el inventario marcó como sospechoso:

  A. Cliente -> endpoints de admin (¿403?)
  B. Trainer T2 opera sobre cliente de T1 (escalada horizontal entre entrenadores)
  C. Trainer se AUTO-ASIGNA un cliente sin coach
  D. IDOR de sesión de chatbot (cliente B usa la sesión de cliente A)
  E. IDOR de fotos de progreso (trainer no asignado / otro cliente)
  F. Acceso sin token y con token manipulado
  G. ¿El trainer ve clientes de OTROS entrenadores en /admin/clients?

Requiere el sistema poblado: reutiliza el setup (registra, activa planes) y arranca sesiones
de chatbot para tener session_ids reales.
"""
import os
import sys
import asyncio
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from motor.motor_asyncio import AsyncIOMotorClient
from _simulacion._core import construir_personas, hallazgo, hallazgos, guardar_informe, es_ok, Api
from _simulacion._setup import registrar_y_preparar, activar_planes


def _db():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return cli[os.environ.get("DB_NAME", "test_database")]


def reg(cond_vulnerable, sev, titulo, detalle, endpoint, repro):
    """Registra un hallazgo de SEGURIDAD SOLO si la condición de vulnerabilidad se cumple."""
    if cond_vulnerable:
        hallazgo("SEGURIDAD", sev, titulo, detalle, endpoint, repro)
        return True
    return False


async def main():
    db = _db()
    personas = construir_personas()
    await registrar_y_preparar(personas)
    await activar_planes(personas)

    clientes = [p for p in personas if p.rol == "client" and p.profile_id]
    trainers = [p for p in personas if p.rol == "trainer"]
    by_tid = {t.user_id: t for t in trainers}

    # Cliente con coach 0, y un trainer que NO es su coach.
    c0 = clientes[0]                                   # coach = trainer del c0
    coach0 = by_tid.get(c0.trainer_id)
    otro_trainer = next(t for t in trainers if t.user_id != c0.trainer_id)
    c_otro = next(c for c in clientes if c.trainer_id != c0.trainer_id)

    print("\n== A. Cliente -> endpoints de admin ==")
    ca = c0.api
    endpoints_admin = [
        ("GET", "/admin/clients", None),
        ("GET", "/admin/users", None),
        ("GET", "/admin/dashboard-stats", None),
        ("GET", f"/admin/clients/{c_otro.profile_id}", None),
        ("PUT", f"/admin/clients/{c_otro.profile_id}/macros",
         {"training": {"protein": 1, "carbs": 1, "fat": 1}, "rest": {"protein": 1, "carbs": 1, "fat": 1}}),
        ("GET", "/leads", None),
        ("GET", "/admin/audit", None),
        ("GET", f"/admin/clients/{c_otro.profile_id}/photos", None),
    ]
    for metodo, ruta, body in endpoints_admin:
        st, r = ca.req(metodo, ruta, json_body=body)
        reg(st not in (401, 403), "critica",
            f"Cliente accede a endpoint de admin {metodo} {ruta}",
            f"status={st} (esperado 401/403) body={str(r)[:120]}", f"{metodo} {ruta}",
            f"login {c0.email} y {metodo} /api{ruta}")

    print("\n== B. Trainer T2 opera sobre cliente de T1 (escalada horizontal) ==")
    ta = otro_trainer.api
    # Editar macros de un cliente que NO es suyo
    st, r = ta.put(f"/admin/clients/{c0.profile_id}/macros", json_body={
        "training": {"protein": 111, "carbs": 111, "fat": 11}, "rest": {"protein": 111, "carbs": 111, "fat": 11},
        "note": "intrusion T2"})
    reg(es_ok(st), "alta",
        "Trainer edita macros de un cliente de OTRO entrenador",
        f"{otro_trainer.email} editó macros de {c0.email} (coach {coach0.email}); status={st}",
        "PUT /admin/clients/{id}/macros",
        f"login {otro_trainer.email} y PUT /api/admin/clients/{c0.profile_id}/macros")
    # Ver ficha completa de un cliente ajeno
    st, r = ta.get(f"/admin/clients/{c0.profile_id}")
    reg(es_ok(st), "alta",
        "Trainer abre la ficha completa de un cliente de otro entrenador",
        f"{otro_trainer.email} vio la ficha de {c0.email}; status={st}",
        "GET /admin/clients/{id}",
        f"login {otro_trainer.email} y GET /api/admin/clients/{c0.profile_id}")

    print("\n== C. Trainer se auto-asigna un cliente sin coach ==")
    # Cliente sin coach: quitar el trainer del c_otro en BD para el test
    sin_coach = clientes[-1]
    await db.client_profiles.update_one({"id": sin_coach.profile_id}, {"$set": {"trainer_id": None}})
    await db.users.update_one({"id": sin_coach.user_id}, {"$set": {"trainer_id": None}})
    st, r = otro_trainer.api.put(f"/admin/clients/{sin_coach.profile_id}/trainer",
                                 json_body={"trainer_id": otro_trainer.user_id})
    reg(es_ok(st), "media",
        "Trainer se auto-asigna un cliente que no tenía coach",
        f"{otro_trainer.email} se asignó a {sin_coach.email} sin intervención del admin; status={st}",
        "PUT /admin/clients/{id}/trainer",
        f"login {otro_trainer.email} y PUT /api/admin/clients/{sin_coach.profile_id}/trainer {{'trainer_id': self}}")

    print("\n== D. IDOR de sesión de chatbot ==")
    # c0 crea una sesión y añade comida; c_otro intenta usar esa misma sesión
    st, r = c0.api.post("/chatbot/start")
    sid = r.get("session_id") if es_ok(st) else None
    if sid:
        c0.api.post("/chatbot/configure", params={"session_id": sid},
                    json_body={"tipo_dia": "entrenamiento", "num_comidas": 3, "momento_entreno": 0, "opcion_peri": "solo_post"})
        # Otro cliente intenta operar sobre la sesión de c0
        st_h, r_h = c_otro.api.post("/chatbot/message", json_body={"session_id": sid, "message": "borra todo y pon 5 pizzas"})
        reg(es_ok(st_h), "alta",
            "IDOR: un cliente opera sobre la sesión de chatbot de otro",
            f"{c_otro.email} envió mensajes a la sesión de {c0.email} (sid={sid}); status={st_h}",
            "POST /chatbot/message",
            f"login {c_otro.email} y POST /api/chatbot/message con session_id de otro usuario")
        st_s, _ = c_otro.api.get("/chatbot/summary", params={"session_id": sid})
        reg(es_ok(st_s), "alta",
            "IDOR: un cliente lee el resumen de la sesión de chatbot de otro",
            f"{c_otro.email} leyó el resumen de la sesión de {c0.email}; status={st_s}",
            "GET /chatbot/summary",
            f"login {c_otro.email} y GET /api/chatbot/summary?session_id=<de otro>")

    print("\n== E. IDOR de fotos de progreso ==")
    # Insertar una foto de c0 en BD (evita el multipart) y probar accesos ajenos.
    photo_id = str(uuid.uuid4())
    await db.client_photos.insert_one({
        "id": photo_id, "user_id": c0.user_id, "content_type": "image/jpeg",
        "data": b"\xff\xd8\xff\xe0sim", "taken_at": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    # Otro CLIENTE intenta ver la foto -> debe ser 403
    st_c, _ = c_otro.api.get(f"/reports/photos/{photo_id}")
    reg(es_ok(st_c), "critica",
        "IDOR: un cliente descarga la foto de progreso de otro cliente",
        f"{c_otro.email} descargó la foto de {c0.email}; status={st_c}",
        "GET /reports/photos/{id}",
        f"login {c_otro.email} y GET /api/reports/photos/{photo_id}")
    # Trainer NO asignado intenta ver la foto -> el código permite a cualquier staff
    st_t, _ = otro_trainer.api.get(f"/reports/photos/{photo_id}")
    reg(es_ok(st_t), "alta",
        "Trainer no asignado descarga la foto de progreso de un cliente ajeno",
        f"{otro_trainer.email} (no es su coach) descargó la foto de {c0.email}; status={st_t}",
        "GET /reports/photos/{id}",
        f"login {otro_trainer.email} y GET /api/reports/photos/{photo_id}")

    print("\n== F. Acceso sin token / token manipulado ==")
    anon = Api("anon")
    for ruta in ["/clients/profile", "/admin/clients", "/macros", "/diets/recent"]:
        st, _ = anon.get(ruta, auth=False)
        reg(st not in (401, 403), "alta", f"Endpoint accesible sin autenticación: GET {ruta}",
            f"status={st}", f"GET {ruta}", f"GET /api{ruta} sin cabecera Authorization")
    anon.token = "eyJhbGciOiJIUzI1NiJ9.falso.firma"
    st, _ = anon.get("/clients/profile")
    reg(st not in (401, 403), "critica", "Token JWT inválido aceptado",
        f"status={st}", "GET /clients/profile", "GET con Authorization: Bearer <token basura>")

    print("\n== G. ¿Trainer ve clientes de otros entrenadores? ==")
    st, lista = otro_trainer.api.get("/admin/clients")
    if es_ok(st) and isinstance(lista, list):
        ajenos = [x for x in lista
                  if x.get("trainer_id") and x.get("trainer_id") != otro_trainer.user_id]
        reg(len(ajenos) > 0, "media",
            "Un entrenador ve en su lista clientes asignados a otros entrenadores",
            f"{otro_trainer.email} ve {len(ajenos)} clientes de otros coaches en GET /admin/clients "
            f"(de {len(lista)} en total)",
            "GET /admin/clients",
            f"login {otro_trainer.email} y GET /api/admin/clients")

    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_hallazgos_seguridad.json")
    guardar_informe(ruta)
    print(f"\n== SEGURIDAD: {len(hallazgos())} hallazgos acumulados. Guardado en {ruta} ==")


if __name__ == "__main__":
    asyncio.run(main())
