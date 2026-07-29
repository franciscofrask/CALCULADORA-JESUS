"""Lectura de la dieta del cliente (P10): que entiende de un texto escrito a mano."""
import asyncio
from core.lectura_dieta import leer_de_texto

CASOS = [
    "Desayuno 80 g de avena con 30 g de proteina en polvo. Comida 200 g de pollo con 100 g de arroz. "
    "Cena 200 g de merluza con ensalada y una cucharada de aceite de oliva.",
    "4 huevos, 100 gramos de pan, 150 g de ternera, 200 de patata y un platano",
]


async def main():
    for i, texto in enumerate(CASOS, 1):
        print(f"\n--- CASO {i}: {texto[:60]}...")
        r = await leer_de_texto(texto, "prueba")
        m = r["macros"]
        print(f"    ENTENDIDO: {m['hidratos']} g hidratos, {m['proteina']} g proteina, {m['grasa']} g grasa")
        for a in r["alimentos"]:
            print(f"      {a['cantidad_g']:7.1f} g  {str(a['nombre'])[:42]:42s} (pedido: {a['pedido']})")
        if r["no_reconocidos"]:
            print("      no reconocidos:", r["no_reconocidos"])

asyncio.run(main())
