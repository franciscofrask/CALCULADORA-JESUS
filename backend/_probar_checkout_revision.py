"""
Crea de verdad la sesion de pago de la revision suelta contra Stripe (modo test) y comprueba
que sale con el importe, la moneda y los metadatos correctos.

Deja el enlace de pago por pantalla para poder terminarlo a mano con una tarjeta de prueba.
"""
import asyncio
import sys
import uuid

import httpx

from core.database import db

BASE = "http://localhost:8000/api"
EMAIL = f"checkout_rev_{uuid.uuid4().hex[:6]}@test.com"


async def main():
    borrar = "--borrar" in sys.argv
    if borrar:
        async for p in db.client_profiles.find({"email": {"$regex": "^checkout_rev_"}}, {"_id": 0, "id": 1, "user_id": 1}):
            for col in ("client_profiles", "macro_sugerencias", "notifications", "macro_history", "quiz_respuestas"):
                await db[col].delete_many({"$or": [{"client_id": p["id"]}, {"user_id": p["user_id"]}]})
            await db.users.delete_one({"id": p["user_id"]})
        print("limpiado")
        return

    async with httpx.AsyncClient(timeout=90) as c:
        r = await c.post(f"{BASE}/auth/register", json={
            "email": EMAIL, "password": "Prueba1234", "name": "Checkout Revision", "phone": "600000001"})
        tok, uid = r.json()["access_token"], r.json()["user"]["id"]
        h = {"Authorization": f"Bearer {tok}"}

        # Plan que se autogestiona y macros ya afinados: es a quien se le ofrece la revision.
        cid = str(uuid.uuid4())
        await db.client_profiles.insert_one({
            "id": cid, "user_id": uid, "name": "Checkout Revision", "email": EMAIL,
            "plan": "calculadora_jp", "price": 60, "status": "activo",
            "created_at": "2026-07-30T00:00:00+00:00",
            "weight": 85, "body_fat": 18, "sex": "hombre", "goal": "definicion",
            "questionnaire_completed": True, "ajuste_macros_completado": True,
            "macros_training": {"protein": 200, "carbs": 180, "fat": 60},
        })

        r = await c.post(f"{BASE}/billing/revision-suelta/checkout", headers=h, json={})
        print("crear sesion de pago ->", r.status_code)
        if r.status_code >= 300:
            print("  ", r.text[:300])
            return
        d = r.json()
        print("  importe:", d.get("importe_eur"), "EUR")
        print("  sesion :", d.get("session_id"))
        print("  enlace :", d.get("checkout_url"))

        # Lo que Stripe tiene guardado de esa sesion: es la prueba de que se creo bien.
        from core.stripe_billing import get_stripe_module, stripe_api_call
        s = await stripe_api_call(get_stripe_module().checkout.Session.retrieve, d["session_id"],
                                  expand=["line_items"])
        li = (s.get("line_items") or {}).get("data") or [{}]
        print("\nlo que ve Stripe:")
        print("  modo         :", s.get("mode"), "(payment = pago unico, correcto)")
        print("  total        :", (s.get("amount_total") or 0) / 100, s.get("currency"))
        print("  concepto     :", (li[0].get("description") or "?"))
        print("  metadatos    :", s.get("metadata"))
        print("  estado       :", s.get("status"), "/", s.get("payment_status"))

        # Y que un cliente con coach NO puede comprarla (su plan ya la incluye).
        await db.client_profiles.update_one({"id": cid}, {"$set": {"plan": "elm"}})
        r2 = await c.post(f"{BASE}/billing/revision-suelta/checkout", headers=h, json={})
        print("\ncon plan que YA lleva coach ->", r2.status_code, r2.json().get("detail", "")[:60])
        await db.client_profiles.update_one({"id": cid}, {"$set": {"plan": "calculadora_jp"}})

    print(f"\nPara terminarlo a mano: abre el enlace y paga con la tarjeta de prueba de Stripe.")
    print(f"Al acabar, limpia con:  ./venv/Scripts/python.exe _probar_checkout_revision.py --borrar")

asyncio.run(main())
