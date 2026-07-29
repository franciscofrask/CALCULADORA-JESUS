"""
Recorre el camino nuevo por la API: registro -> alta (4 preguntas) -> ajuste.
Comprueba que el alta da macros provisionales y que el ajuste los cambia.
Necesita el backend levantado en :8000. Crea un usuario de prueba y lo borra al final.
"""
import asyncio
import uuid

import httpx

BASE = "http://localhost:8000/api"
EMAIL = f"prueba_alta_{uuid.uuid4().hex[:8]}@test.com"
PASS = "Prueba1234"


def macros(r):
    m = (r or {}).get("macros") or {}
    e, p, d = m.get("entreno", {}), m.get("perientreno", {}), m.get("descanso", {})
    return f"entreno {e.get('hidratos')}+{p.get('hidratos')} | descanso {d.get('hidratos')} | grasa {e.get('grasa')}/{d.get('grasa')}"


async def main():
    async with httpx.AsyncClient(timeout=60) as c:
        # 1) Registro con telefono (el doc lo quiere aqui, no en el quiz)
        r = await c.post(f"{BASE}/auth/register", json={
            "email": EMAIL, "password": PASS, "name": "Cliente Prueba", "phone": "600111222"})
        print("1) registro          ->", r.status_code)
        if r.status_code >= 300:
            print("   ", r.text[:200]); return
        tok = r.json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        me = await c.get(f"{BASE}/auth/me", headers=h)
        print("   telefono guardado ->", me.json().get("phone"))

        # 2) Perfil con plan. El alta real pasa por Stripe, asi que para la prueba se crea
        #    directamente en la base (esto es dev y el usuario se borra al final).
        from core.database import db as _db
        me_id = me.json()["id"]
        await _db.client_profiles.insert_one({
            "id": str(uuid.uuid4()), "user_id": me_id, "name": "Cliente Prueba",
            "email": EMAIL, "plan": "elm", "price": 0, "status": "activo", "week": 1,
            "start_date": "2026-07-29", "created_at": "2026-07-29T00:00:00+00:00",
        })
        print("2) perfil/plan       -> creado en la base (dev)")

        # 3) EL ALTA: solo los cuatro datos de la tabla
        r = await c.post(f"{BASE}/clients/questionnaire", headers=h, json={
            "goal": "definicion", "sex": "hombre", "weight": 85, "body_fat": 18})
        print("3) alta (4 preguntas)->", r.status_code)
        if r.status_code >= 300:
            print("   ", r.text[:300]); return
        prov = r.json().get("resultado")
        print("   PROVISIONALES:", macros(prov))
        perfil = r.json().get("profile") or {}
        print("   ajuste pendiente ->", not perfil.get("ajuste_macros_completado"))

        # 4) EL AJUSTE: las respuestas que afinan
        r = await c.post(f"{BASE}/clients/ajustar-macros", headers=h, json={
            "actividad_diaria": "muy_activo", "deporte_extra": True,
            "facilidad_engordar": "normal", "cuesta_definir": "normal",
            "sigue_dieta": True, "tiempo_dieta": "3_6m", "como_va": "bien",
            "hambre_saturacion": "normal", "dieta_hc_entreno": 300,
            "dieta_grasa_entreno": 70, "dieta_confirmada": True})
        print("4) ajuste            ->", r.status_code)
        if r.status_code >= 300:
            print("   ", r.text[:300]); return
        defin = r.json().get("resultado")
        print("   DEFINITIVOS:  ", macros(defin))
        perfil2 = r.json().get("profile") or {}
        print("   ajuste hecho     ->", bool(perfil2.get("ajuste_macros_completado")))

        distintos = macros(prov) != macros(defin)
        print(f"\n   el ajuste cambia los macros: {'SI' if distintos else 'NO'}")

        # 5) Se puede repetir (a diferencia del alta, que se cierra)
        r = await c.post(f"{BASE}/clients/ajustar-macros", headers=h, json={
            "actividad_diaria": "sedentario", "deporte_extra": False,
            "facilidad_engordar": "enseguida", "sigue_dieta": False})
        print("5) repetir el ajuste ->", r.status_code, "|", macros(r.json().get("resultado")))
        r2 = await c.post(f"{BASE}/clients/questionnaire", headers=h, json={
            "goal": "definicion", "sex": "hombre", "weight": 85, "body_fat": 18})
        print("   repetir el alta   ->", r2.status_code, "(409 = cerrada, correcto)")

    # Limpieza
    from core.database import db
    u = await db.users.find_one({"email": EMAIL}, {"_id": 0, "id": 1})
    if u:
        await db.client_profiles.delete_many({"user_id": u["id"]})
        await db.macro_history.delete_many({"user_id": u["id"]})
        await db.quiz_respuestas.delete_many({"user_id": u["id"]})
        await db.users.delete_one({"id": u["id"]})
        print("\n   usuario de prueba borrado")

asyncio.run(main())
