"""
Los tres arreglos de la base de alimentos del bloque H (doc del 07-08, puntos 58, 59 y 60).

Se hace como script y no a mano porque **el catalogo de dev y el de produccion no tienen por
que ser el mismo**: los tres puntos hablan de datos, no de codigo, y lo que aqui esta bien
alli puede no estarlo. Esto revisa los tres, dice lo que encuentra y arregla los dos que se
pueden arreglar sin inventarse ningun valor.

  58 · CEREALES PROTEICOS SIN LA CATEGORIA 7.1.3
       La 7.1.3 hace que la proteina cuente al 100 % sin pasar por la calibracion
       progresiva (calibracion_dia.CATS_EXCEPCION_PROTEICA). Un cereal con 30 g de
       proteina que no la tenga se calibra como si fuera un muesli normal, y el mismo
       producto acaba contando distinto segun quien lo metiera en el catalogo.
       SE ARREGLA: se le anade 7.1.3 al cereal (familia 7.) con proteina >= UMBRAL.

  59 · FRUTOS SECOS CON LA PROTEINA A CERO
       Un fruto seco a 0 de proteina no pasa el filtro y no cuenta nunca nada. NO se
       corrige solo: el valor bueno esta en la etiqueta y no se puede inventar. Se listan
       para que alguien los mire, y se dice el valor del mismo producto con marca cuando
       existe, que es la mejor pista.

  60 · DUPLICADOS GENERICO + MARCA
       Solo se LISTAN. Que un alimento este dos veces, uno generico y otro con marca, es
       el diseno del catalogo (el generico existe para quien no compra esa marca), asi que
       borrar uno no es un arreglo evidente: hay dietas guardadas que apuntan a uno de los
       dos. Se sacan los que tienen ADEMAS los mismos macros, que son los que de verdad no
       aportan nada, para que Jesus decida cual se queda.

  python _revisar_alimentos_bloque_h.py             mira y cuenta, no toca nada
  python _revisar_alimentos_bloque_h.py --escribir  aplica lo del 58
"""
import asyncio
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from core.database import db   # noqa: E402

# Desde cuanta proteina un cereal es "proteico". Los muesli y granolas normales andan por
# 9-15 g; los que se venden como proteicos, por encima de 20. 18 deja fuera a los normales
# con frutos secos sin colarse en los de verdad.
UMBRAL_PROTEICO = 18.0
CAT_PROTEICOS = "7.1.3"

# Familias de fruto seco (17.2.x): ahi un cero de proteina es siempre un error.
FAMILIA_FRUTOS_SECOS = "17.2"


def _cats(f):
    return [c.strip() for c in str(f.get("categorias") or "").split("|") if c.strip()]


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _sin_marca(nombre):
    """El nombre sin el '(Marca)' del final, para emparejar generico y marca."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", str(nombre or "")).strip().lower()


async def main(escribir: bool):
    alimentos = await db.foods.find({}, {"_id": 0, "id": 1, "nombre": 1, "categorias": 1,
                                         "proteinas": 1, "hidratos": 1, "grasas": 1,
                                         "url": 1}).to_list(20000)
    print(f"{len(alimentos)} alimentos en el catalogo\n")

    # ── 58 ────────────────────────────────────────────────────────────────────
    faltan = []
    for f in alimentos:
        c = _cats(f)
        if not any(x.startswith("7.") for x in c) or CAT_PROTEICOS in c:
            continue
        p = _num(f.get("proteinas"))
        if p is not None and p >= UMBRAL_PROTEICO:
            faltan.append(f)

    print(f"58 · CEREALES PROTEICOS SIN {CAT_PROTEICOS}: {len(faltan)}")
    for f in faltan:
        print(f"     P={f.get('proteinas'):<6} {str(f.get('categorias'))[:22]:24s} {f['nombre'][:56]}")
    if escribir and faltan:
        for f in faltan:
            nuevas = " | ".join(_cats(f) + [CAT_PROTEICOS])
            await db.foods.update_one({"id": f["id"]}, {"$set": {"categorias": nuevas}})
        print(f"     -> {CAT_PROTEICOS} anadida a {len(faltan)}")

    # ── 59 ────────────────────────────────────────────────────────────────────
    ceros = [f for f in alimentos
             if any(x.startswith(FAMILIA_FRUTOS_SECOS) for x in _cats(f))
             and (_num(f.get("proteinas")) or 0) == 0]
    print(f"\n59 · FRUTOS SECOS CON LA PROTEINA A CERO: {len(ceros)}")
    por_nombre = defaultdict(list)
    for f in alimentos:
        por_nombre[_sin_marca(f["nombre"])].append(f)
    for f in ceros:
        pistas = [g for g in por_nombre[_sin_marca(f["nombre"])]
                  if g["id"] != f["id"] and (_num(g.get("proteinas")) or 0) > 0]
        pista = f"  (el mismo con marca tiene {pistas[0].get('proteinas')} g)" if pistas else ""
        print(f"     {f['nombre'][:56]}{pista}")
    if ceros:
        print("     NO se tocan: el valor bueno esta en la etiqueta y no se inventa.")

    # ── 60 ────────────────────────────────────────────────────────────────────
    print("\n60 · DUPLICADOS generico + marca CON LOS MISMOS MACROS:")
    n = 0
    for base, grupo in sorted(por_nombre.items()):
        if len(grupo) < 2:
            continue
        genericos = [g for g in grupo if not g.get("url")]
        marcas = [g for g in grupo if g.get("url")]
        if not genericos or not marcas:
            continue
        for g in genericos:
            iguales = [m for m in marcas
                       if _num(m.get("proteinas")) == _num(g.get("proteinas"))
                       and _num(m.get("hidratos")) == _num(g.get("hidratos"))
                       and _num(m.get("grasas")) == _num(g.get("grasas"))]
            for m in iguales:
                n += 1
                print(f"     P={g.get('proteinas')} · «{g['nombre'][:40]}» = «{m['nombre'][:44]}»")
    print(f"     {n} parejas. Se LISTAN, no se borran: hay dietas guardadas apuntando a uno")
    print("     de los dos, y cual se queda lo decide Jesus.")

    print("\nESCRITO (solo el 58)" if escribir else "\nSOLO MIRADO: nada tocado (pasa --escribir)")


if __name__ == "__main__":
    asyncio.run(main("--escribir" in sys.argv))
