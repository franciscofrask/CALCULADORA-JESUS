# -*- coding: utf-8 -*-
"""
Quita los macros calculados sobre un conteo de piezas leido como gramos. Punto 4.5.

Esto NO reescribe los 120.000 items que vinieron de Calma: eso se decidio no hacerlo (adivinar
en masa lo que significo un numero hace tres años no es arreglar). Esos se convierten solos al
abrir su dia, uno a uno, con alguien delante.

Lo que si arregla es el rastro que dejo el fallo: los items a los que ALGUIEN ya les calculo
los macros leyendo el conteo como gramos, que se quedaron guardados como si fueran buenos.
Medido el 09-08 en produccion: 8 items, y sus `updated_at` son del dia de la revision -- se
corrompieron al abrir esas dietas para mirarlas.

Un huevo con 0,1 g de proteina no es un dato incompleto: es un dato falso, y ademas cuadra el
dia con menos macros de los que el cliente se ha comido. Se le quitan los macros para que se
recalculen sobre la cantidad ya convertida.

    python _arreglar_cantidades_de_piezas.py            # solo dice lo que haria
    python _arreglar_cantidades_de_piezas.py --hazlo    # lo hace
"""
import asyncio
import math
import sys

from calculator import get_food_config
from core.cantidad_de_dieta import parece_un_conteo
from core.database import db

HAZLO = "--hazlo" in sys.argv


def _n(v):
    try:
        x = float(v or 0)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if math.isnan(x) or math.isinf(x) else x


async def main():
    print(f"{'HACIENDOLO' if HAZLO else 'ENSAYO (nada se toca)'}\n")

    cfgs = {}
    async for f in db.foods.find({}, {"_id": 0, "id": 1, "nombre": 1, "categorias": 1,
                                      "racion": 1, "unidades": 1}):
        cfgs[f.get("id")] = (get_food_config(f), f.get("nombre"))

    tocadas = items = 0
    async for d in db.diets.find({}, {"_id": 1, "comidas": 1, "fecha": 1, "user_id": 1}):
        comidas = d.get("comidas")
        if not isinstance(comidas, dict):
            continue
        cambio = False
        for clave, comida in comidas.items():
            if not isinstance(comida, dict):
                continue
            for it in (comida.get("alimentos") or []):
                if not isinstance(it, dict):
                    continue
                aid = it.get("alimento_id") if it.get("alimento_id") is not None else it.get("id")
                cfg, nombre = cfgs.get(aid, (None, it.get("nombre")))
                if not cfg:
                    continue
                if not parece_un_conteo(it.get("cantidad_g"), cfg.get("por_unidad"),
                                        cfg.get("peso_unidad")):
                    continue
                # Solo los que YA tienen macros calculados sobre el numero malo.
                if _n((it.get("macros_efectivos") or {}).get("P")) <= 0:
                    continue
                items += 1
                cambio = True
                print(f"   {d.get('fecha')}  {clave}  {str(nombre)[:34]:34} "
                      f"guarda {it.get('cantidad_g')} (una pieza pesa {cfg['peso_unidad']} g) "
                      f"-> P={it['macros_efectivos'].get('P')} se quita")
                for campo in ("macros_efectivos", "macros_brutos", "macros_reales"):
                    it.pop(campo, None)
        if cambio:
            tocadas += 1
            if HAZLO:
                await db.diets.update_one({"_id": d["_id"]}, {"$set": {"comidas": comidas}})

    print(f"\n{items} items en {tocadas} dietas")
    if not HAZLO:
        print("(ensayo: no se ha tocado nada)")


if __name__ == "__main__":
    asyncio.run(main())
