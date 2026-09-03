# -*- coding: utf-8 -*-
"""UN INFORME DEL MES COMPLETO, PARA PODER MIRARLO EN LA APP.

El informe del mes cuelga de un reporte, y las dos cuentas de pruebas tenian CERO. Sin uno
no hay nada que abrir: Seguimiento -> Reportes sale vacio.

Y UN REPORTE PELADO ENSEÑA UN INFORME PELADO. Los bloques del informe no se pintan si no
hay datos, a proposito: la regla 1 del documento es «el informe no le pide nada», asi que
un bloque sin nada que decir desaparece en vez de salir vacio o pidiendole que suba algo.
La primera version de este guion solo dejaba el peso, y por eso faltaban las medidas y las
fotos. Ahora deja el escenario entero:

    TRES reportes         hace 8 semanas, hace 4 y hoy. Hacen falta tres y no uno porque
                          las medidas se enseñan a dos columnas, «Mes ant.» y «1ª toma»:
                          con un solo reporte anterior las dos columnas serian la misma.
    Las diez medidas      en los tres, creciendo como corresponde a «ganar musculo».
    SEIS fotos            frente, espaldas y perfil en las dos fechas, subidas por la API
                          de verdad (`POST /api/reports/photos`), no metidas a mano en la
                          base: asi pasan por el mismo sitio que las de un cliente.

Las fotos son placeholders dibujados aqui mismo, con su pose y su fecha escritas encima.
No es la foto de nadie.

    Se ve en:  Seguimiento -> Reportes -> «Ver mi informe del mes»

SOLO EN DEV Y SOLO A LA CUENTA DE PRUEBAS. Y se quita entero:

    backend/venv/Scripts/python.exe _guia/_dejar_un_informe.py              lo deja
    backend/venv/Scripts/python.exe _guia/_dejar_un_informe.py --con-feedback  contestado
    backend/venv/Scripts/python.exe _guia/_dejar_un_informe.py --quitar     lo borra todo
    CUENTA=clientedemo@test.com ... _dejar_un_informe.py                    a otra cuenta
"""
import asyncio
import io
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

import requests
from PIL import Image, ImageDraw

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "backend"))

from core.database import db          # noqa: E402

API = os.environ.get("API", "http://127.0.0.1:8000")
CORREO = os.environ.get("CUENTA", "francisco@test.com")
CLAVE = os.environ.get("CLAVE", "demo123")
#: De donde salio, para poder borrarlo sin llevarse por delante ninguno de verdad.
MARCA = "dejado-para-mirar-0309"

FEEDBACK = ("Has subido 8,2 kg cumpliendo 18 de 28 días. El descanso te ha caído y ahí está "
            "el hambre que me cuentas. Te subo los hidratos del perientreno y te bajo el "
            "cardio a dos sesiones.")

# LAS DIEZ MEDIDAS, EN TRES MOMENTOS. Las claves son las de `ETIQUETAS_MEDIDAS`
# (core/informe_del_mes.py); si se inventa una, esa fila no sale y no avisa nadie.
# Crecen, que el objetivo de la cuenta es ganar musculo: asi las dos columnas salen en
# verde, que es la regla de color del bloque («menos cintura es buena noticia bajando grasa
# y mala ganando musculo»).
MEDIDAS = {
    "primera": {"hombros": 118.0, "mesoesternal": 98.0, "brazo_d": 35.0, "brazo_i": 35.0,
                "muslo_d": 56.0, "muslo_i": 56.0, "cadera": 104.0, "cintura": 96.0,
                "gemelo_d": 34.0, "gemelo_i": 34.0},
    "anterior": {"hombros": 120.0, "mesoesternal": 99.0, "brazo_d": 36.0, "brazo_i": 35.5,
                 "muslo_d": 57.0, "muslo_i": 57.0, "cadera": 104.0, "cintura": 95.0,
                 "gemelo_d": 34.5, "gemelo_i": 34.0},
    "ahora": {"hombros": 122.0, "mesoesternal": 101.0, "brazo_d": 37.5, "brazo_i": 37.0,
              "muslo_d": 58.5, "muslo_i": 58.0, "cadera": 105.0, "cintura": 95.0,
              "gemelo_d": 35.0, "gemelo_i": 35.0},
}

# EN SINGULAR: `routes/checkins.py` solo acepta «frente», «espalda» y «perfil», y lo que no
# esté en esa lista lo guarda SIN pose, sin quejarse. Mandando «espaldas» las fotos entraban
# y no aparecían: fue así como salió el fallo del botón del informe.
POSES = (("frente", "FRENTE"), ("espalda", "ESPALDAS"), ("perfil", "PERFIL"))


def foto_de_mentira(pose: str, cuando: date, tono: int) -> bytes:
    """Una foto de progreso PLACEHOLDER, con la pose y la fecha escritas encima.

    Se dibuja aqui y no se coge de ningun sitio: en una cuenta de pruebas no tiene por que
    aparecer el cuerpo de nadie, y escribiendole encima lo que es no hay forma de
    confundirla con una foto de verdad.
    """
    ancho, alto = 480, 640
    img = Image.new("RGB", (ancho, alto), (tono, tono, tono + 6))
    d = ImageDraw.Draw(img)
    # Una silueta a brochazos, para que se distinga una pose de otra de un vistazo.
    d.ellipse((205, 70, 275, 140), fill=(tono + 30, tono + 30, tono + 38))
    d.rounded_rectangle((180, 150, 300, 380), radius=28, fill=(tono + 30, tono + 30, tono + 38))
    d.rounded_rectangle((150, 160, 180, 340), radius=14, fill=(tono + 22, tono + 22, tono + 30))
    d.rounded_rectangle((300, 160, 330, 340), radius=14, fill=(tono + 22, tono + 22, tono + 30))
    d.rounded_rectangle((195, 380, 235, 570), radius=18, fill=(tono + 26, tono + 26, tono + 34))
    d.rounded_rectangle((245, 380, 285, 570), radius=18, fill=(tono + 26, tono + 26, tono + 34))
    d.text((24, 24), f"{pose}", fill=(240, 120, 40))
    d.text((24, 44), cuando.strftime("%d/%m/%Y"), fill=(220, 220, 220))
    d.text((24, alto - 40), "FOTO DE PRUEBA - no es de nadie", fill=(150, 150, 150))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def entrar() -> str:
    r = requests.post(f"{API}/api/auth/login", json={"email": CORREO, "password": CLAVE},
                      timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def subir_fotos(token: str, fechas) -> int:
    """Las seis fotos, por la API de verdad. Devuelve cuantas entraron."""
    puestas = 0
    for i, cuando in enumerate(fechas):
        for pose, etiqueta in POSES:
            datos = foto_de_mentira(etiqueta, cuando, 34 + i * 10)
            r = requests.post(
                f"{API}/api/reports/photos",
                params={"pose": pose, "taken_at": f"{cuando.isoformat()}T09:00:00+00:00"},
                files={"file": (f"prueba_{pose}_{cuando.isoformat()}.png", datos, "image/png")},
                headers={"Authorization": f"Bearer {token}"}, timeout=60)
            if r.ok:
                puestas += 1
            else:
                print(f"   la foto {pose} de {cuando} no entro: {r.status_code} {r.text[:120]}")
    return puestas


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

    # SIEMPRE SE LIMPIA ANTES, tambien al dejarlo: asi se puede repetir sin ir apilando
    # reportes ni fotos, y lo que borra es solo lo que puso este guion.
    fuera = await db.reports.delete_many({"client_id": perfil["id"], "origen": MARCA})
    fotos_fuera = await db.client_photos.delete_many({"client_id": perfil["id"], "origen": MARCA})
    if fuera.deleted_count or fotos_fuera.deleted_count:
        print(f"quitados {fuera.deleted_count} reportes y {fotos_fuera.deleted_count} fotos")
    if quitar:
        return

    hoy = date.today()
    # Tres fechas: la primera toma, el mes pasado y hoy. Cuatro semanas entre cada una, que
    # es lo que dura el periodo de un reporte mensual.
    fechas = [hoy - timedelta(days=56), hoy - timedelta(days=28), hoy]
    pesos = [70.0, 74.1, 78.2]
    cuales = ["primera", "anterior", "ahora"]

    for cuando, peso, cual in zip(fechas, pesos, cuales):
        reporte = {
            "id": str(uuid.uuid4()),
            "client_id": perfil["id"],
            "user_id": user["id"],
            "tipo": "mensual",
            "origen": MARCA,
            "fecha": cuando.isoformat(),
            "created_at": f"{cuando.isoformat()}T10:00:00+00:00",
            "weight": peso,
            "measurements": MEDIDAS[cual],
            "periodo_desde": (cuando - timedelta(days=27)).isoformat(),
            "periodo_hasta": cuando.isoformat(),
            # El informe se entrega AL ENVIAR (doc «El informe del mes», 1-09): el hueco del
            # feedback sale en gris hasta que el entrenador contesta.
            "informe_estado": "entregado",
        }
        # El feedback solo en el ultimo, que es el que se mira. Los de atras estan
        # contestados desde hace tiempo, cada uno con su fecha.
        if cual != "ahora":
            reporte["trainer_feedback"] = "Buen mes. Seguimos igual."
            reporte["trainer_feedback_at"] = f"{(cuando + timedelta(days=2)).isoformat()}T12:00:00+00:00"
        elif con_feedback:
            reporte["trainer_feedback"] = FEEDBACK
            reporte["trainer_feedback_by"] = "Jesús Gallego"
            reporte["trainer_feedback_at"] = datetime.now(timezone.utc).isoformat()
        await db.reports.insert_one(dict(reporte))

    print(f"dejados 3 reportes mensuales a {CORREO} ({', '.join(f.isoformat() for f in fechas)})")

    # LAS FOTOS, POR LA API. Se suben en las dos ultimas fechas: la primera columna del
    # comparador es la foto mas vieja de esa pose y la segunda la mas nueva.
    try:
        token = entrar()
    except Exception as e:                                        # noqa: BLE001
        print(f"   sin fotos: no se pudo entrar en la API ({e})")
    else:
        puestas = subir_fotos(token, fechas[1:])
        # Marcarlas DESPUES de subirlas: la API no conoce este campo, y sin el `--quitar`
        # no sabria cuales son suyas.
        await db.client_photos.update_many(
            {"client_id": perfil["id"], "origen": {"$exists": False}},
            {"$set": {"origen": MARCA}})
        print(f"subidas {puestas} fotos de prueba (frente, espaldas y perfil en dos fechas)")

    print()
    print("   Seguimiento -> Reportes -> «Ver mi informe del mes»")
    print("   feedback:", "contestado por Jesús" if con_feedback else "en gris, sin contestar")


if __name__ == "__main__":
    asyncio.run(main())
