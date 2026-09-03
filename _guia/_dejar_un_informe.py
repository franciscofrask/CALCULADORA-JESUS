# -*- coding: utf-8 -*-
"""UN REPORTE MENSUAL MANDADO, PARA PODER VER EL INFORME EN LA APP.

El informe del mes cuelga de un reporte, y las dos cuentas de pruebas tienen CERO. Sin uno
no hay nada que abrir: Seguimiento -> Reportes sale vacio.

Esto le deja uno mandado, con su informe montado por el mismo camino que lo monta la app
(`_bloques_del_informe`), asi que lo que se ve es lo de verdad y no un ejemplo pintado.

    Se ve en:  Seguimiento -> Reportes -> «Ver mi informe del mes»

SOLO EN DEV Y SOLO A LA CUENTA DE PRUEBAS. Y se puede quitar:

    backend/venv/Scripts/python.exe _guia/_dejar_un_informe.py              lo deja
    backend/venv/Scripts/python.exe _guia/_dejar_un_informe.py --con-feedback  contestado
    backend/venv/Scripts/python.exe _guia/_dejar_un_informe.py --quitar     lo borra
"""
import asyncio
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "backend"))

from core.database import db          # noqa: E402

CORREO = os.environ.get("CUENTA", "francisco@test.com")
#: De donde salio, para poder borrarlo sin llevarse por delante ninguno de verdad.
MARCA = "dejado-para-mirar-0309"

FEEDBACK = ("Has bajado 2,8 kg cumpliendo 22 de 28 días. El descanso te ha caído y ahí está "
            "el hambre que me cuentas. Te subo los hidratos del perientreno y te bajo el "
            "cardio a dos sesiones.")


async def main() -> None:
    quitar = "--quitar" in sys.argv
    con_feedback = "--con-feedback" in sys.argv

    user = await db.users.find_one({"email": CORREO}, {"_id": 0, "id": 1})
    if not user:
        print(f"no existe {CORREO}")
        return
    perfil = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not perfil:
        print("esa cuenta no tiene ficha de cliente")
        return

    fuera = await db.reports.delete_many({"client_id": perfil["id"], "origen": MARCA})
    if fuera.deleted_count:
        print(f"quitados {fuera.deleted_count} reportes de los dejados para mirar")
    if quitar:
        return

    hoy = date.today()
    reporte = {
        "id": str(uuid.uuid4()),
        "client_id": perfil["id"],
        "user_id": user["id"],
        "tipo": "mensual",
        "origen": MARCA,
        "fecha": hoy.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "weight": perfil.get("weight") or 78.4,
        "periodo_desde": (hoy - timedelta(days=28)).isoformat(),
        "periodo_hasta": hoy.isoformat(),
        # El informe se entrega AL ENVIAR (doc «El informe del mes», 1-09): el hueco del
        # feedback sale en gris hasta que el entrenador contesta.
        "informe_estado": "entregado",
    }
    if con_feedback:
        reporte["trainer_feedback"] = FEEDBACK
        reporte["trainer_feedback_by"] = "Jesús Gallego"
        reporte["trainer_feedback_at"] = datetime.now(timezone.utc).isoformat()

    await db.reports.insert_one(dict(reporte))
    print(f"dejado un reporte mensual a {CORREO} ({hoy})")
    print("   Seguimiento -> Reportes -> «Ver mi informe del mes»")
    print("   feedback:", "contestado por Jesús" if con_feedback else "en gris, sin contestar")


if __name__ == "__main__":
    asyncio.run(main())
