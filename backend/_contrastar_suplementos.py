"""Compara los suplementos de la web con los que tenemos (punto 75 del 07-08-2026).

QUÉ SE ENCONTRÓ AL MIRARLO
--------------------------
El punto dice «no hay que escribir ni un protocolo: hay que traerlos». Ya se
trajeron: `db.supplements` tiene 106 entradas importadas el 19-05-2026, y son MÁS
detalladas que la web. Lo que allí es prosa («Semanas 2 y 3: 1 y 1, Semanas 4 y 5:
2 y 1...»), aquí ya está troceado en pasos aplicables: «Cafeína 100 mg mes 1»,
«mes 2», «finalización (10 días)».

El problema no es traerlos, es que **llevan sin mirarse desde mayo**. Ejemplo real:
la web tiene hoy «Silimarina, 150 mg por toma» y nosotros «Cardo mariano, 1
cápsula». Es el mismo suplemento -- la silimarina es el extracto del cardo
mariano -- con otro nombre y la dosis dicha de otra forma. Nada está roto, pero lo
que lee el cliente y lo que Jesús publica ya no dicen lo mismo.

Esto no lo arregla solo: hace falta que alguien decida qué versión vale. Lo que
hace este script es enseñar las diferencias para poder decidirlas.

DE DÓNDE SALE EL FICHERO DE LA WEB
----------------------------------
`_suplementos_elm.json` se saca de /membresia-elm/suplementacion-recomendada/ con
la sesión abierta (la página devuelve 302 sin ella, y la REST de WordPress da la
lista pero no el «¿Cuándo?» ni el «¿Cuánto?»). El listado enseña 10 y hay 28: se
recorren las 12 categorías del filtro para verlos todos.

Uso:
    venv/Scripts/python.exe _contrastar_suplementos.py
"""
import asyncio
import io
import json
import os
import re
import sys
import unicodedata

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

WEB = os.path.join(os.path.dirname(__file__), "_suplementos_elm.json")

# La web y el catálogo no siempre llaman igual a lo mismo. Esto no es un apaño: es
# la lista de equivalencias que hay que conocer para comparar sin ruido.
MISMO_SUPLEMENTO = {
    "silimarina": "cardo mariano",          # la silimarina es el extracto del cardo
    "map o eaa s": "hydropeptides o map",   # tras normalizar, el apóstrofo es un espacio
    "fat burner hardcore termogenico 75 mg cafeina por capsula": "fat burner hardcore",
}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()


def parecido(a: str, b: str) -> float:
    ta, tb = set(norm(a).split()), set(norm(b).split())
    if not ta:
        return 0.0
    return len(ta & tb) / len(ta)


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "jg12_restored")]
    web = json.load(io.open(WEB, encoding="utf-8"))
    nuestros = await db.supplements.find({}, {"_id": 0}).to_list(None)
    print(f"suplementos en la web: {len(web)}  |  en la app: {len(nuestros)}")

    ausentes, distintos = [], []
    for w in web:
        buscado = MISMO_SUPLEMENTO.get(norm(w["nombre"]), w["nombre"])
        variantes = [n for n in nuestros
                     if parecido(buscado, n.get("categoria") or "") >= 0.6
                     or parecido(buscado, n.get("nombre") or "") >= 0.6]
        if not variantes:
            ausentes.append(w["nombre"])
            continue
        # ¿alguna de nuestras variantes dice lo mismo que la web?
        cuanto_web = norm(w["cuanto"])
        coincide = any(norm(v.get("descripcion") or "").find(cuanto_web[:40]) >= 0
                       for v in variantes if cuanto_web)
        if not coincide:
            distintos.append((w, variantes))

    print(f"\nEN LA WEB Y NO EN LA APP: {len(ausentes)}")
    for n in ausentes:
        print(f"   - {n}")

    print(f"\nESTÁN, PERO NO DICEN LO MISMO: {len(distintos)}")
    for w, variantes in distintos:
        print(f"\n   {w['nombre']}")
        print(f"      web : {w['cuanto'][:110]}")
        for v in variantes[:3]:
            d = (v.get("descripcion") or "").replace("\n", " ")
            corte = d.split("¿Cuánto?")[-1].strip()
            print(f"      app : [{v['nombre'][:34]}] {corte[:96]}")

    print("\nEl protocolo de la web va en prosa y el nuestro en pasos, así que muchas")
    print("diferencias son de forma y no de fondo. Hay que leerlas una a una.")


if __name__ == "__main__":
    asyncio.run(main())
