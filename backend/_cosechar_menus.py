"""La cosecha semanal de menús (punto 71 del documento del 07-08-2026).

Recorre las dietas que ha montado la gente, cuenta por PERSONAS DISTINTAS, pasa el
filtro de calidad del punto 67 y deja el resultado en db.meal_library.

Qué hace exactamente, en orden:

  1. Recuenta sobre TODA la historia de dietas (no incremental: ver la explicación
     en core/cosecha_menus.py). Salen usos y personas distintas de verdad.
  2. Separa lo heredado: el `usos` que hay hoy en la biblioteca vino del CSV de la
     calculadora antigua y no tiene persona detrás. Pasa a llamarse `usos_calma`
     para que no se confunda con lo que sabemos de esta app.
  3. Recalcula los macros con el motor de ahora, que aplica la regla por categoría.
     Los que traía el CSV no la aplican y en 1.928 casos se desvían hasta 25 g de
     proteína -- y ese campo es el que usa la preselección del sugeridor.
  4. Marca cada menú con si pasa el filtro y por qué se cae, para poder afinarlo.
  5. Da de alta los menús nuevos que la gente haya montado y no estuvieran.

Uso:
    venv/Scripts/python.exe _cosechar_menus.py            # dry run, no toca nada
    venv/Scripts/python.exe _cosechar_menus.py --apply    # escribe

Pensado para correr una vez por semana. Es idempotente: pasarlo dos veces seguidas
deja lo mismo.
"""
import asyncio
import hashlib
import os
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.cosecha_menus import (  # noqa: E402
    es_peri, firma, pasa_el_filtro, personas_distintas, recontar,
)
from meal_builder import get_effective_macros_per_100g  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Cuantas personas distintas hacen falta para que un menu NUEVO entre en el banco.
# Con 1 no hay senal: es el gusto de una persona. Con 2 ya es algo que le ha
# apetecido a gente que no se conoce.
MIN_PERSONAS_PARA_ENTRAR = 2


def clasificar_driver(ef: dict) -> str:
    """Un alimento es 'driver limpio' de un macro si aporta ese macro y casi nada de
    los otros dos. Es lo que permite ajustar un menú sin descuadrar el resto."""
    p, h, g = (float(ef.get(k, 0) or 0) for k in ("P", "H", "G"))
    total = p + h + g
    if total <= 0:
        return "mixto"
    if p / total >= 0.8:
        return "proteina_limpia"
    if h / total >= 0.8:
        return "hidrato_limpio"
    if g / total >= 0.8:
        return "grasa_limpia"
    return "mixto"


def id_de_firma(sig) -> str:
    return "L" + hashlib.sha1(",".join(map(str, sig)).encode()).hexdigest()[:10].upper()


async def main():
    apply = "--apply" in sys.argv
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "jg12_restored")]

    foods = {}
    async for f in db.foods.find({}, {"_id": 0}):
        foods[int(f["id"])] = f
    print(f"catálogo: {len(foods)} alimentos | modo: {'APPLY' if apply else 'DRY RUN'}")

    # 1. Recuento real sobre las dietas de esta app
    acc = await recontar(db)
    print(f"combinaciones distintas montadas por la gente: {len(acc)}")
    con_gente = sum(1 for c in acc.values() if personas_distintas(c) >= 2)
    print(f"   montadas por 2 personas o más: {con_gente}")

    # 2. Lo que ya hay en la biblioteca, indexado POR FIRMA y no por id.
    #
    # Los menús heredados del CSV llevan ids de la calculadora antigua
    # ("b270e88c4ad0446c") y los que salen de aquí se numeran con otro esquema
    # ("L" + hash). Casar por id daría cero coincidencias y daríamos de alta 70.000
    # menús que ya estaban, duplicando la biblioteca entera. Lo que identifica a un
    # menú es lo que lleva dentro.
    todos = await db.meal_library.find({}, {"_id": 0}).to_list(None)
    agrupados = {}
    for d in todos:
        sig = firma(a["alimento_id"] for a in d.get("alimentos") or [])
        agrupados.setdefault((sig, d.get("tipo") or "comida"), []).append(d)

    # De cada grupo se queda el más usado y los demás se marcan como repetidos.
    #
    # No son menús distintos: llevan los mismos alimentos y solo cambian las
    # cantidades, y el sugeridor reescala las cantidades de todas formas. Al cliente
    # le salían tres veces la misma comida con otros gramos. No se borra ninguno --
    # hay dietas guardadas que apuntan a ellos --, se marcan y el picker los salta.
    # El representante tiene que salir SIEMPRE el mismo, y por eso no se elige por
    # `usos`: este script reescribe ese campo, así que en la pasada siguiente el
    # grupo se ordenaba distinto y el representante cambiaba. Manda, por este orden:
    # el que ya lo era, el más usado en la calculadora antigua (ese número ya no se
    # toca nunca) y el id, para deshacer empates de forma fija.
    def _orden(d):
        return (1 if d.get("repetido_de") else 0,
                -(d.get("usos_calma") if d.get("usos_calma") is not None else d.get("usos") or 0),
                d["id"])

    por_firma, repetidos = {}, []
    for clave, grupo in agrupados.items():
        grupo.sort(key=_orden)
        por_firma[clave] = grupo[0]
        repetidos += [(d["id"], grupo[0]["id"]) for d in grupo[1:]]
    actuales = {d["id"]: d for d in por_firma.values()}
    print(f"biblioteca actual: {len(todos)} documentos, {len(por_firma)} menús distintos")
    print(f"   repetidos (mismos alimentos, otras cantidades): {len(repetidos)}")

    ops = []
    motivos = Counter()
    descartados_alta = 0
    nuevos = 0
    cosechados = 0
    macros_corregidos = 0

    # 3. Todo lo que la gente ha montado: se actualiza o se da de alta
    for sig, c in acc.items():
        if not all(a in foods for a in sig):
            continue  # lleva algo que ya no está en el catálogo
        fs = [foods[a] for a in sig]
        tipo = "peri" if es_peri(c) else "comida"
        vale, motivo = pasa_el_filtro(fs, tipo)
        motivos[motivo] += 1

        viejo = por_firma.get((sig, tipo))
        mid = viejo["id"] if viejo else id_de_firma(sig)

        # Un menú NUEVO solo entra si es bueno Y lo han montado varias personas. Es
        # la regla del punto 71 aplicada donde se decide: de las 70.115
        # combinaciones que ha montado la gente, 68.390 las montó UNA sola persona.
        # Guardarlas todas no es tener un banco de menús, es tener el historial de
        # todo el mundo -- y no cabe: Atlas es de 512 MB.
        if viejo is None and not (vale and personas_distintas(c) >= MIN_PERSONAS_PARA_ENTRAR):
            descartados_alta += 1
            continue

        alimentos_doc, tot = [], {"P": 0.0, "H": 0.0, "G": 0.0}
        for aid in sig:
            food = foods[aid]
            ef = get_effective_macros_per_100g(food)
            cant = round(statistics.median(c["cantidades"][aid]))
            fac = cant / 100.0
            for m in tot:
                tot[m] += (float(ef.get(m, 0) or 0)) * fac
            alimentos_doc.append({
                "alimento_id": aid,
                "nombre": food.get("nombre", ""),
                "cantidad_g": cant,
                "driver": clasificar_driver(ef),
            })
        macros = {m: round(v, 1) for m, v in tot.items()}
        macros["kcal"] = round(tot["P"] * 4 + tot["H"] * 4 + tot["G"] * 9)

        campos = {
            "alimento_ids": list(sig),
            "alimentos": alimentos_doc,
            "macros": macros,
            "usos": c["usos"],
            "clientes": personas_distintas(c),
            "tipo": tipo,
            "calidad": {"pasa": vale, "motivo": motivo},
            "cosechado_at": datetime.now(timezone.utc).isoformat(),
        }
        if viejo is None:
            nuevos += 1
            campos.update({"id": mid, "fuente": "clientes", "usos_calma": 0})
        else:
            cosechados += 1
            # el `usos` heredado del CSV pasa a su sitio la primera vez
            if "usos_calma" not in viejo:
                campos["usos_calma"] = viejo.get("usos", 0)
        ops.append((mid, campos, viejo is None))

    # 4. Lo heredado que nadie ha montado aquí: se corrigen macros y se marca calidad,
    #    pero usos/clientes quedan a 0 -- no se le inventa popularidad que no consta.
    tocados = {mid for mid, _, _ in ops}
    solo_heredados = 0
    for mid, d in actuales.items():
        if mid in tocados:
            continue
        sig = tuple(sorted(int(a["alimento_id"]) for a in d.get("alimentos") or []))
        if not sig or not all(a in foods for a in sig):
            continue
        fs = [foods[a] for a in sig]
        tipo = d.get("tipo") or "comida"
        vale, motivo = pasa_el_filtro(fs, tipo)
        tot = {"P": 0.0, "H": 0.0, "G": 0.0}
        for a in d["alimentos"]:
            ef = get_effective_macros_per_100g(foods[int(a["alimento_id"])])
            fac = float(a["cantidad_g"]) / 100.0
            for m in tot:
                tot[m] += (float(ef.get(m, 0) or 0)) * fac
        macros = {m: round(v, 1) for m, v in tot.items()}
        macros["kcal"] = round(tot["P"] * 4 + tot["H"] * 4 + tot["G"] * 9)
        antes = d.get("macros") or {}
        if any(abs(float(antes.get(m, 0) or 0) - macros[m]) > 1 for m in ("P", "H", "G")):
            macros_corregidos += 1
        campos = {
            "macros": macros,
            "usos": 0,
            "clientes": 0,
            "calidad": {"pasa": vale, "motivo": motivo},
        }
        if "usos_calma" not in d:
            campos["usos_calma"] = d.get("usos", 0)
        ops.append((mid, campos, False))
        solo_heredados += 1
        motivos[motivo] += 1

    print(f"\ncosechados de las dietas de aquí: {cosechados} actualizados, {nuevos} nuevos")
    print(f"heredados de Calma sin montar aquí: {solo_heredados}")
    print(f"macros corregidos por la regla: {macros_corregidos}")
    print("\nfiltro de calidad:")
    for m, n in motivos.most_common():
        print(f"   {m:24} {n:6}")

    if not apply:
        print("\nDRY RUN: no se ha escrito nada. Pasa --apply para aplicar.")
        return

    from pymongo import UpdateOne
    lote = [UpdateOne({"id": mid}, {"$set": campos}, upsert=es_nuevo)
            for mid, campos, es_nuevo in ops]
    lote += [UpdateOne({"id": rid}, {"$set": {"repetido_de": bueno}})
             for rid, bueno in repetidos]
    for i in range(0, len(lote), 1000):
        await db.meal_library.bulk_write(lote[i:i + 1000], ordered=False)
    print(f"\naplicado: {len(lote)} menús escritos")

    pasan = await db.meal_library.count_documents({"calidad.pasa": True})
    con_gente = await db.meal_library.count_documents({"clientes": {"$gte": 2}})
    print(f"   pasan el filtro: {pasan}")
    print(f"   montados por 2 personas o más: {con_gente}")


if __name__ == "__main__":
    asyncio.run(main())
