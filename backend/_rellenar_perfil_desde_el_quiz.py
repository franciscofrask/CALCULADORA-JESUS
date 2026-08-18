"""Rellena en la ficha lo que el cliente YA contestó y se quedó por el camino.

Punto 0 del doc del 18-08. El cuestionario guardaba las respuestas en dos sitios que no
lee casi nadie -- `ajustes_macros` dentro de la ficha y la colección `quiz_respuestas` --
y los campos del perfil que sí lee la app se quedaban vacíos: el generador de rutinas mira
`training_experience`, el agente de ajustes mira `biotype`, y ahí no había nada.

El arreglo del código ya está hecho, pero solo vale para quien conteste a partir de ahora.
Esto es para los que ya están dentro: se les rellena con SU respuesta, sin preguntarles
nada otra vez.

QUÉ SE RELLENA
    training_experience   experiencia entrenando
    activity_level        actividad diaria, traducida a la escala de la ficha
    biotype               biotipo
    height                altura
    birthdate + age       fecha de nacimiento

DE DÓNDE SE SACA, por orden de preferencia (lo más reciente primero)
    1. `ajustes_macros` de la propia ficha (lo último que contestó en el ajuste)
    2. `nivel1` de la ficha (el cuestionario largo)
    3. `quiz_respuestas`, el histórico entero: el envío más reciente que traiga el dato
    4. `calma_raw.formulario_inicial`, el cuestionario que rellenó en Calma. Son 266
       formularios importados, de los que 72 son de clientes que hoy están en la app.
       De ahí salen la altura, la fecha de nacimiento y el objetivo.

LA FECHA DE NACIMIENTO DE CALMA VIENE CORRIDA UN DÍA
    Firestore guardó la medianoche de Madrid en UTC, así que 242 de las 266 fechas
    llegan como "22:00" o "23:00" del día ANTERIOR. Cortar el texto por los diez
    primeros caracteres le quita un día al cumpleaños de casi todo el mundo: hay que
    pasarlo a hora de España antes de quedarse con el día.

REGLAS
    - Nunca se pisa un valor que ya esté puesto. Solo se rellenan huecos.
    - Sin `--escribir` no toca nada: enseña lo que haría.

USO
    # dev
    ./venv/Scripts/python.exe _rellenar_perfil_desde_el_quiz.py
    # produccion, por el tunel del 27018
    MONGO_URL="mongodb://localhost:27018" DB_NAME=jg12_prod \
        ./venv/Scripts/python.exe _rellenar_perfil_desde_el_quiz.py --escribir
"""
import asyncio
import os
import sys
from collections import Counter
from datetime import date, datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

ESCRIBIR = "--escribir" in sys.argv
MADRID = ZoneInfo("Europe/Madrid")

# La misma traducción que hace el backend al guardar (routes/users.py ACTIVIDAD_A_PERFIL).
ACTIVIDAD_A_PERFIL = {"sedentario": "sedentario", "normal": "ligero",
                      "moderado": "moderado", "muy_activo": "activo"}

# El objetivo, como lo escribía Calma. «TONIFICAR» (17 fichas) se queda fuera a
# propósito: no es ninguno de los dos nuestros y decidirlo por él sería inventarse su
# objetivo. Sale en el resumen para que se decida a mano.
OBJETIVO_CALMA = {"DEFINICION": "definicion", "DEFINICIÓN": "definicion",
                  "VOLUMEN": "volumen"}

CAMPOS = ("training_experience", "activity_level", "biotype", "height", "birthdate", "goal")


def _fecha_de_calma(v):
    """La fecha de nacimiento tal y como la vivió el cliente, en su día de España."""
    if not v:
        return None
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if d.tzinfo is None:
        return d.date().isoformat()
    return d.astimezone(MADRID).date().isoformat()


def _vacio(v):
    return v is None or v == "" or v == []


def _edad(nacimiento):
    try:
        b = datetime.strptime(str(nacimiento)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    hoy = date.today()
    return hoy.year - b.year - ((hoy.month, hoy.day) < (b.month, b.day))


def _de(fuente, campo):
    """El valor de un campo dentro de un bloque de respuestas, ya traducido.

    Vale para los tres formatos: las respuestas de nuestro quiz, el bloque `nivel1` y el
    formulario de Calma, que llama a las cosas por su nombre en castellano.
    """
    if not isinstance(fuente, dict):
        return None
    if campo == "activity_level":
        return ACTIVIDAD_A_PERFIL.get(fuente.get("actividad_diaria"))
    if campo == "birthdate" and fuente.get("fechaNacimiento"):
        return _fecha_de_calma(fuente["fechaNacimiento"])
    if campo == "goal" and fuente.get("objetivo"):
        return OBJETIVO_CALMA.get(str(fuente["objetivo"]).strip().upper())
    v = fuente.get(campo)
    if campo == "height" and v is None:
        v = fuente.get("estatura")
    if campo == "height":
        try:
            v = float(v) if v not in (None, "") else None
        except (TypeError, ValueError):
            v = None
        # Una altura de 1,78 o de 17 cm no es una altura: no se rellena con eso.
        if v is not None and not (120 <= v <= 230):
            return None
    return None if _vacio(v) else v


async def main():
    url = os.environ["MONGO_URL"]
    base = os.environ.get("DB_NAME", "jg12_restored")
    # Se imprime la CADENA, no solo el nombre: es lo unico que dice de verdad donde estas.
    print(f"conexion: {url[:34]}...  |  base: {base}")
    print(f"modo: {'ESCRIBIR' if ESCRIBIR else 'solo mirar'}\n")
    db = AsyncIOMotorClient(url, serverSelectionTimeoutMS=25000)[base]

    # El historico del quiz, del mas nuevo al mas viejo, agrupado por cliente.
    historico = {}
    async for q in db.quiz_respuestas.find({}, {"_id": 0}).sort("created_at", -1):
        for clave in (q.get("client_id"), q.get("user_id")):
            if clave:
                historico.setdefault(clave, []).append(q.get("respuestas") or {})

    # El cuestionario de Calma, por client_id y por correo: la migracion enlazo unos por
    # una via y otros por la otra.
    calma = {}
    async for c in db.calma_raw.find({"formulario_inicial": {"$nin": [None, {}, []]}},
                                     {"_id": 0, "formulario_inicial": 1, "client_id": 1,
                                      "email": 1}):
        f = c.get("formulario_inicial") or {}
        if c.get("client_id"):
            calma[c["client_id"]] = f
        if c.get("email"):
            calma[c["email"].strip().lower()] = f
    correos = {}
    async for u in db.users.find({}, {"_id": 0, "id": 1, "email": 1}):
        if u.get("email"):
            correos[u["id"]] = u["email"].strip().lower()
    tonificar = 0

    puestos = Counter()
    tenian = Counter()
    clientes_tocados = 0
    sin_fuente = Counter()

    async for p in db.client_profiles.find({}, {"_id": 0}):
        fuentes = [p.get("ajustes_macros"), p.get("nivel1")]
        fuentes += historico.get(p.get("id"), []) + historico.get(p.get("user_id"), [])
        # Calma va la ultima: es la mas antigua de todas.
        suyo_en_calma = calma.get(p.get("id")) or calma.get(correos.get(p.get("user_id"), ""))
        if suyo_en_calma:
            fuentes.append(suyo_en_calma)
            if (_vacio(p.get("goal"))
                    and str(suyo_en_calma.get("objetivo") or "").strip().upper() == "TONIFICAR"):
                tonificar += 1

        cambios = {}
        for campo in CAMPOS:
            if not _vacio(p.get(campo)):
                tenian[campo] += 1
                continue
            for f in fuentes:
                v = _de(f, campo)
                if v is not None:
                    cambios[campo] = v
                    break
            else:
                sin_fuente[campo] += 1

        if cambios.get("birthdate") and _vacio(p.get("age")):
            edad = _edad(cambios["birthdate"])
            if edad:
                cambios["age"] = edad

        if not cambios:
            continue
        clientes_tocados += 1
        for c in cambios:
            puestos[c] += 1
        if ESCRIBIR:
            await db.client_profiles.update_one({"id": p["id"]}, {"$set": cambios})

    print(f"{'campo':22} {'ya lo tenian':>13} {'se rellenan':>12} {'sin respuesta':>14}")
    for campo in CAMPOS + ("age",):
        print(f"{campo:22} {tenian[campo]:>13} {puestos[campo]:>12} {sin_fuente[campo]:>14}")
    print(f"\nfichas tocadas: {clientes_tocados}")
    if tonificar:
        print(f"\n{tonificar} fichas sin objetivo pusieron «TONIFICAR» en Calma. No es ni "
              "definición ni volumen, así que se quedan sin tocar: eso lo decide Jesús.")
    if not ESCRIBIR:
        print("\nNo se ha escrito nada. Con --escribir se aplica.")


asyncio.run(main())
