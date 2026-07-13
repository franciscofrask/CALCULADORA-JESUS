#!/usr/bin/env python3
"""
Crea Products + Prices en Stripe para los planes JG12 (idempotente por lookup_key).

Fuente única: PLAN_CATALOG (models/user.py). Crea un precio recurrente por cada plan que
tenga `stripe_price_env` configurado, usando su `precio` (EUR) y su ciclo de cobro
(`billing_cycle_weeks` × 7 días). Así importes e intervalos coinciden con el catálogo.

Re-ejecutar es seguro: busca precios existentes por lookup_key antes de crear. El
lookup_key incluye el intervalo, así que cambiar el ciclo crea un precio nuevo; cambiar
solo el importe NO actualiza el precio existente (Stripe no permite editar importes; habría
que archivar el viejo y crear otro).

Uso:
    1. Pon STRIPE_SECRET_KEY=sk_test_... en backend/.env
    2. python setup_stripe_products.py
    3. Reinicia el backend

Los planes de "pago único" del catálogo (p.ej. reto60) se crean como Price one-time
(sin recurring); el checkout los cobra con mode="payment" y el acceso dura su ciclo.
"""
import os
import sys
from pathlib import Path

import stripe
from dotenv import load_dotenv, set_key

# Catálogo como fuente única de importes/ciclos.
sys.path.insert(0, str(Path(__file__).parent))
from models.user import PLAN_CATALOG, PLAN_TYPES

ROOT_DIR = Path(__file__).parent
ENV_PATH = ROOT_DIR / ".env"
load_dotenv(ENV_PATH)

secret_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
if not secret_key:
    print("[X] Falta STRIPE_SECRET_KEY en .env")
    sys.exit(1)

stripe.api_key = secret_key
stripe.api_version = "2026-02-25.clover"

mode = "TEST" if secret_key.startswith("sk_test_") else "LIVE"
print(f"Usando Stripe en modo {mode}")
if mode == "LIVE":
    print("[!] Estás en LIVE. Cancela (Ctrl+C) si no era la intención.")

CURRENCY = "eur"


def build_plans() -> list:
    """Deriva del catálogo la lista de planes con Price en Stripe (los que tienen
    stripe_price_env). Cada uno: key, env, name, amount(céntimos), interval_days, desc."""
    plans = []
    for code, p in PLAN_CATALOG.items():
        env = (p.get("stripe_price_env") or "").strip()
        if not env:
            continue  # premium/6m/complementos: sin cobro por Stripe
        precio = float(p.get("precio") or 0)
        if precio <= 0:
            print(f"  [SKIP] {code}: precio 0/indefinido, no se crea Price")
            continue
        weeks = p.get("billing_cycle_weeks") or 4
        plans.append({
            "key": code,
            "env": env,
            "name": f"JG12 {p['name']}",
            "amount": round(precio * 100),
            "interval_days": weeks * 7,
            "one_time": PLAN_TYPES[code]["one_time"],
            "description": (p.get("precio_nota") or p.get("name") or code)[:250],
        })
    return plans


def find_or_create_price(plan: dict) -> str:
    lookup_key = (f"jg12_{plan['key']}_onetime_eur" if plan["one_time"]
                  else f"jg12_{plan['key']}_{plan['interval_days']}d_eur")
    try:
        existing = stripe.Price.list(lookup_keys=[lookup_key], limit=1, active=True)
        if existing.data:
            print(f"  [EXISTE] {plan['name']}: {existing.data[0].id} (lookup={lookup_key})")
            return existing.data[0].id
    except Exception as e:
        print(f"  [!] lookup falló para {plan['name']}: {e}")

    product = stripe.Product.create(
        name=plan["name"], description=plan["description"], metadata={"jg12_plan": plan["key"]})
    print(f"  [PRODUCT] {plan['name']}: {product.id}")

    price_kwargs = dict(
        product=product.id, unit_amount=plan["amount"], currency=CURRENCY,
        lookup_key=lookup_key,
        metadata={"jg12_plan": plan["key"], "cycle_days": str(plan["interval_days"])})
    if plan["one_time"]:
        price_kwargs["nickname"] = f"{plan['name']} - pago único"
    else:
        price_kwargs["recurring"] = {"interval": "day", "interval_count": plan["interval_days"]}
        price_kwargs["nickname"] = f"{plan['name']} - {plan['interval_days']} días"
    price = stripe.Price.create(**price_kwargs)
    tipo = "pago único" if plan["one_time"] else f"cada {plan['interval_days']} días"
    print(f"  [PRICE]   {plan['name']}: {price.id}  (EUR {plan['amount']/100:.2f} {tipo})")
    return price.id


def main() -> None:
    plans = build_plans()
    print(f"\nCreando {len(plans)} products + prices (EUR)...\n")
    created = {}
    for plan in plans:
        try:
            created[plan["env"]] = find_or_create_price(plan)
        except Exception as e:
            print(f"  [X] Falló {plan['name']}: {e}")
            sys.exit(1)

    print("\nEscribiendo Price IDs en .env...")
    for env_name, price_id in created.items():
        set_key(str(ENV_PATH), env_name, price_id, quote_mode="never")
        print(f"  {env_name}={price_id}")

    print("\nListo. Reinicia el backend para recoger los cambios.")


if __name__ == "__main__":
    main()
