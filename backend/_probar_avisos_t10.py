"""Comprobacion a mano de los avisos T10 contra los datos de verdad de dev.

No toca nada: lee el perfil del cliente demo, calcula sus ventanas de reporte y pregunta
que aviso saldria en varios momentos concretos (en hora de España). Sirve para ver que un
aviso sale CUANDO TOCA y no sale cuando no toca sin esperar al miercoles.
"""
import asyncio
from datetime import timedelta

from dotenv import load_dotenv
load_dotenv()

from core.avisos_cliente import avisos_de_calendario_doc, avisos_condicionados  # noqa: E402
from core.database import db  # noqa: E402
from core.tiempo import a_madrid  # noqa: E402
from routes.notifications import _datos_para_avisos  # noqa: E402


async def main():
    user = await db.users.find_one({"email": "clientedemo@test.com"}, {"_id": 0, "id": 1})
    perfil = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    from datetime import datetime, timezone
    ahora = datetime.now(timezone.utc)
    datos = await _datos_para_avisos(perfil, ahora)

    print(f"semana={datos['semana']} ciclo={datos['semanas_ciclo']} "
          f"cerro_hoy={datos['cerro_hoy']} dias_sin_cerrar={datos['dias_sin_cerrar']} "
          f"dias_sin_entrar={datos['dias_sin_entrar']} quiere={datos['quiere_cierre_dia']}")
    for v in datos["ventanas"]:
        print(f"  ventana {v['tipo']} semana {v['semana']}: abre {v['abre']} "
              f"cierra {v['cierra']} mandado={v['mandado']}")

    def probar(etiqueta, **kw):
        avisos = avisos_de_calendario_doc(
            cliente_id=perfil.get("id"), arranque=datos["arranque"],
            cerro_hoy=datos["cerro_hoy"], quiere_cierre_dia=datos["quiere_cierre_dia"],
            ventanas=datos["ventanas"], semana=datos["semana"],
            semanas_ciclo=datos["semanas_ciclo"], **kw)
        salen = [a["variantes"][0]["titulo"] for a in avisos]
        print(f"  {etiqueta}: {salen or 'nada'}")

    hoy_es = a_madrid(ahora)
    print("\nQUE SALDRIA...")
    probar("ahora mismo", ahora_es=hoy_es)
    probar("hoy a las 19:59", ahora_es=hoy_es.replace(hour=19, minute=59))
    probar("hoy a las 20:00", ahora_es=hoy_es.replace(hour=20, minute=0))
    if datos["ventanas"]:
        v = datos["ventanas"][-1]
        probar(f"el dia que abre el {v['tipo']}", ahora_es=v["abre"])
        probar("una hora antes de que abra", ahora_es=v["abre"] - timedelta(hours=1))
        probar("el dia siguiente a las 09:00",
               ahora_es=(v["abre"] + timedelta(days=1)).replace(hour=9))
        probar("el dia siguiente al cierre",
               ahora_es=v["cierra"] + timedelta(days=1))

    print("\nCONDICIONADAS:", [a["variantes"][0]["titulo"] for a in avisos_condicionados(
        ahora=ahora, semanas_sin_ajustar=datos["semanas_sin_ajustar"],
        reporte_sin_fotos=datos["reporte_sin_fotos"],
        dias_sin_cerrar=datos["dias_sin_cerrar"],
        dias_sin_entrar=datos["dias_sin_entrar"])])


asyncio.run(main())
