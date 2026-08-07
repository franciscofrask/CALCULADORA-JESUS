"""Auditoría del catálogo de alimentos: busca macros que no pueden ser (punto 9, doc 07-08).

El punto 9 pedía "sacar del buscador los alimentos sin macros". Al mirarlo resultó que los
alimentos con los tres macros a cero **no son un error**: son la lechuga, el pepino, el apio,
las setas, el konjac y los refrescos zero, que de verdad no aportan nada y que el método usa a
propósito como alimentos libres. Sacarlos del buscador sería quitar medio plato de verdura.

Lo que sí rompe los números de un menú sin que nadie se entere es lo contrario: alimentos con
macros **mal puestos**. Una tortita de 7 g con 125 g de grasa mete 1149 kcal en la comida y
nadie lo mira. Eso es lo que busca este script.

    cd backend && python _auditar_catalogo.py
"""
import asyncio
import sys

sys.path.insert(0, ".")
from core.database import db


def _macros(f):
    return (float(f.get("proteinas") or 0), float(f.get("hidratos") or 0), float(f.get("grasas") or 0))


def _kcal(p, h, g):
    return p * 4 + h * 4 + g * 9


# Cuánto se le perdona a una etiqueta antes de considerarla mal. Los macros de un alimento
# seco pueden acercarse mucho a su peso, y las etiquetas redondean: un 10 % de holgura evita
# llenar la lista de galletas que se pasan por medio gramo.
HOLGURA = 1.10


def revisar(f):
    """(gravedad, motivo) si el alimento es sospechoso, o None si está bien.

    La gravedad es cuántas veces se pasa de lo posible: 1,1 es una etiqueta mal redondeada y
    18 es un dato sencillamente equivocado.
    """
    p, h, g = _macros(f)
    racion = float(f.get("racion") or 100) or 100.0
    suma = p + h + g

    if p < 0 or h < 0 or g < 0:
        return (99, "algún macro es negativo")

    if f.get("unidades"):
        # Macros por unidad: una unidad no puede pesar menos que sus propios macros.
        if suma > racion * HOLGURA:
            return (suma / racion, f"la unidad pesa {racion:g} g y sus macros suman {suma:.1f} g")
        return None

    # A granel los macros son por 100 g: no caben más de 100 g de nada.
    if suma > 100 * HOLGURA:
        return (suma / 100, f"por 100 g suman {suma:.1f} g")
    if _kcal(p, h, g) > 900:
        return (_kcal(p, h, g) / 900, f"{_kcal(p, h, g):.0f} kcal por 100 g")
    return None


async def main():
    foods = await db.foods.find({}, {"_id": 0}).to_list(10000)
    sospechosos = [(f, r) for f in foods if (r := revisar(f))]
    sospechosos.sort(key=lambda x: -x[1][0])

    print(f"Catálogo: {len(foods)} alimentos")
    print(f"Con macros que no pueden ser: {len(sospechosos)}")
    print("(ordenados por gravedad: cuántas veces se pasan de lo posible)\n")
    for f, (gravedad, motivo) in sospechosos:
        marca = "  <<< REVISAR" if gravedad >= 1.3 else ""
        p, h, g = _macros(f)
        print(f"  x{gravedad:.1f}  [{f.get('id')}] {str(f.get('nombre'))[:48]}{marca}")
        print(f"        P{p} H{h} G{g} | ración {f.get('racion')} g | {motivo}")
        if f.get("url"):
            print(f"        {f['url']}")

    libres = [f for f in foods if _macros(f) == (0.0, 0.0, 0.0)]
    print(f"\nCon los tres macros a cero: {len(libres)} (alimentos libres, NO son un error)")
    print("  " + ", ".join(str(f.get("nombre"))[:26] for f in libres[:10]) + " ...")


if __name__ == "__main__":
    asyncio.run(main())
