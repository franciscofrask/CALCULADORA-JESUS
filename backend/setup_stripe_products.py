#!/usr/bin/env python3
"""
Crea Products + Prices en Stripe para los planes JG12 (idempotente por lookup_key).
Ciclo de cobro: 84 días (12 semanas) recurrente, EUR.

Re-ejecutar es seguro: busca precios existentes por lookup_key antes de crear.
Tras correr, escribe los Price IDs en backend/.env (STRIPE_PRICE_GOLD, etc).

Uso:
    1. Pon STRIPE_SECRET_KEY=sk_test_... en backend/.env
    2. python setup_stripe_products.py
    3. Reinicia el backend
"""
import os
import sys
from pathlib import Path

import stripe
from dotenv import load_dotenv, set_key

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

# Planes (precio en EUR, amount en céntimos)
PLANS = [
    {"key": "gold",   "env": "STRIPE_PRICE_GOLD",   "name": "JG12 Gold",   "amount": 14900, "description": "Plan Gold - El más completo. Rutina, macros, chat directo, reportes quincenales, cardio, audio, suplementación."},
    {"key": "silver", "env": "STRIPE_PRICE_SILVER", "name": "JG12 Silver", "amount": 9900,  "description": "Plan Silver - Balance servicio/precio. Rutina personalizada, macros, chat, reporte mensual."},
    {"key": "bronze", "env": "STRIPE_PRICE_BRONZE", "name": "JG12 Bronze", "amount": 6900,  "description": "Plan Bronze - Para empezar. Rutina básica, macros, chat, reporte mensual."},
    {"key": "elm",    "env": "STRIPE_PRICE_ELM",    "name": "JG12 ELM",    "amount": 3900,  "description": "Plan ELM - Solo macros, para quienes ya tienen rutina."},
]

CURRENCY = "eur"
INTERVAL_DAYS = 84  # 12 semanas


def find_or_create_price(plan: dict) -> str:
    lookup_key = f"jg12_{plan['key']}_84d_eur"
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

    price = stripe.Price.create(
        product=product.id, unit_amount=plan["amount"], currency=CURRENCY,
        recurring={"interval": "day", "interval_count": INTERVAL_DAYS},
        lookup_key=lookup_key, nickname=f"{plan['name']} - 84 días",
        metadata={"jg12_plan": plan["key"], "cycle_days": str(INTERVAL_DAYS)})
    print(f"  [PRICE]   {plan['name']}: {price.id}  (EUR {plan['amount']/100:.2f} / {INTERVAL_DAYS} días)")
    return price.id


def main() -> None:
    print(f"\nCreando 4 products + prices (EUR, cada {INTERVAL_DAYS} días)...\n")
    created = {}
    for plan in PLANS:
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
