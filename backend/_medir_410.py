# -*- coding: utf-8 -*-
"""
Punto 4.10, segunda vuelta: ¿a cuantos clientes les vale todavia el atajo?

El cerrojo del 4.10 se puso en los dos caminos que el cliente usa a proposito para tocar sus
macros (PUT /macros y POST /clients/ajustar-macros). Pero hay CUATRO mas que tambien los
reescriben de rebote, y esos solo miran `macros_source != "manual"`:

    PUT  /clients/profile          si cambia peso, sexo, grasa u objetivo -> recalcula
    POST /clients/questionnaire    si repite el cuestionario del alta     -> recalcula
    POST /clients/mi-cuerpo        si vuelve a pasar por "Mi cuerpo"      -> recalcula
    POST /calculator/targets/apply calcula y aplica, sin mas

Y `macros_source` no vale como cerrojo, porque la calculadora del PANEL DEL COACH
(POST /admin/clients/{id}/calculator/apply) deja `macros_source: "auto"`. O sea: justo los
clientes a los que el coach les puso los macros desde su calculadora son los que quedan
abiertos.

Esto cuenta a cuantos les pasa hoy en produccion.
"""
import asyncio
import io
import sys

from motor.motor_asyncio import AsyncIOMotorClient

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

CALCULADOS_POR_LA_APP = ("", "quiz_alta", "quiz_ajuste")


def de_una_persona(ap):
    if not ap:
        return False
    origen = ap.get("origen") or ""
    return origen not in CALCULADOS_POR_LA_APP or bool(ap.get("changed_by"))


async def main():
    cli = AsyncIOMotorClient("mongodb://127.0.0.1:27018", serverSelectionTimeoutMS=15000)
    db = cli["jg12_prod"]

    perfiles = await db.client_profiles.find(
        {"status": "activo"},
        {"_id": 0, "id": 1, "plan": 1, "macros_source": 1, "user_id": 1},
    ).to_list(None)
    print(f"perfiles activos: {len(perfiles)}")

    # Que planes son 'personalizado' segun el catalogo del codigo.
    sys.path.insert(0, r"C:\Users\Administrador\Desktop\CALCULADORA-JESUS\backend")
    from models.user import PLAN_CATALOG

    def modo(plan):
        p = PLAN_CATALOG.get((plan or "").lower().strip()) or {}
        return (p.get("habilitaciones") or {}).get("calculadora") or "sin_ajuste"

    expuestos, protegidos, libres, sin_nadie = [], [], [], []
    por_plan = {}
    for p in perfiles:
        m = modo(p.get("plan"))
        por_plan[(p.get("plan"), m)] = por_plan.get((p.get("plan"), m), 0) + 1
        if m != "personalizado":
            libres.append(p)
            continue
        ultimo = await db.macro_history.find_one(
            {"client_id": p.get("id")}, {"_id": 0, "origen": 1, "changed_by": 1},
            sort=[("created_at", -1)])
        if not de_una_persona(ultimo):
            sin_nadie.append(p)
        elif (p.get("macros_source") or "") == "manual":
            protegidos.append(p)
        else:
            expuestos.append((p, (ultimo or {}).get("origen"), (ultimo or {}).get("changed_by")))

    print()
    print("planes de los activos (plan -> modo calculadora):")
    for (plan, m), n in sorted(por_plan.items(), key=lambda x: -x[1]):
        print(f"   {n:4}  {str(plan):28} {m}")

    print()
    print("de los de plan PERSONALIZADO:")
    print(f"   con macros puestos por una persona y macros_source='manual' .... {len(protegidos):4}  (a salvo por los dos lados)")
    print(f"   con macros puestos por una persona y macros_source != 'manual' . {len(expuestos):4}  <-- SE LOS PUEDEN MACHACAR")
    print(f"   sin nadie detras todavia (macros de su alta) .................... {len(sin_nadie):4}  (pueden y deben poder)")
    print(f"otros planes (autogestion / sin_ajuste) ............................ {len(libres):4}")

    if expuestos:
        print()
        print("de donde salieron los macros de los expuestos:")
        cuenta = {}
        for _, origen, quien in expuestos:
            cuenta[origen or "(sin origen)"] = cuenta.get(origen or "(sin origen)", 0) + 1
        for origen, n in sorted(cuenta.items(), key=lambda x: -x[1]):
            print(f"   {n:4}  {origen}")

    cli.close()


asyncio.run(main())
