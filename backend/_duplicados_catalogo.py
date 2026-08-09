# -*- coding: utf-8 -*-
"""
Barrido de duplicados en el catalogo de alimentos. Punto 60 del doc del 07-08.

Lo que decia el punto: «Buscando "pistacho" salen tres entradas proximas -- generico,
tostados con sal y tostados sin sal -- que son productos distintos. No se ha barrido el
catalogo entero».

Esto lo barre entero, con tres redes de distinta finura, porque «duplicado» no es una sola
cosa:

  1. MISMO NOMBRE. Normalizando acentos, mayusculas y signos. Duplicado seguro.
  2. MISMO NOMBRE Y MISMOS MACROS, pero escrito distinto. Aqui entran los "Pechuga pollo"
     vs "Pechuga de pollo": se comparan las palabras, no la cadena.
  3. MISMOS MACROS EXACTOS con nombres parecidos. La red mas fina y la mas ruidosa: dos
     marcas pueden tener la misma tabla nutricional siendo productos distintos, asi que
     esto se REVISA, no se borra.

No borra nada. Solo mira: cual de dos entradas se queda es una decision de Jesus, porque
depende de cual esta usada en dietas y cual tiene la URL buena.

    python _duplicados_catalogo.py
"""
import asyncio
import re
import sys
import unicodedata
from collections import defaultdict

from core.database import db

# Cuanto se tienen que parecer dos nombres (palabras en comun / palabras totales) para que
# valga la pena mirarlos. 0,6 deja pasar "pechuga pollo" vs "pechuga de pollo" y corta
# antes de "yogur natural" vs "yogur griego".
PARECIDO_MINIMO = 0.6


def normalizar(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", s).strip()


def palabras(s) -> set:
    return {p for p in normalizar(s).split() if p}


def parecido(a: str, b: str) -> float:
    pa, pb = palabras(a), palabras(b)
    if not pa or not pb:
        return 0.0
    return len(pa & pb) / len(pa | pb)


def firma_macros(f) -> tuple:
    def n(k):
        try:
            return round(float(f.get(k) or 0), 1)
        except (TypeError, ValueError):
            return 0.0
    return (n("proteinas"), n("hidratos"), n("grasas"))


async def main():
    foods = await db.foods.find({}, {"_id": 0}).to_list(None)
    print(f"alimentos en el catalogo: {len(foods)}\n")

    # Cuantas veces se usa cada alimento: es el dato que decide cual se queda.
    usos = defaultdict(int)
    async for d in db.diets.find({}, {"_id": 0, "comidas": 1}):
        comidas = d.get("comidas")
        # `comidas` es {'C1': {'alimentos': [...]}, ...}, pero en documentos viejos ha sido
        # una lista y hasta un numero. Se recorre lo que sea recorrible y lo demas se ignora.
        if isinstance(comidas, dict):
            comidas = list(comidas.values())
        elif not isinstance(comidas, list):
            continue
        for comida in comidas:
            if not isinstance(comida, dict):
                continue
            for it in (comida.get("alimentos") or comida.get("items") or []):
                if not isinstance(it, dict):
                    continue
                aid = it.get("alimento_id") if it.get("alimento_id") is not None else it.get("id")
                if aid is not None:
                    usos[str(aid)] += 1

    def ficha(f):
        return (f"      id={str(f.get('id'))[:10]:10} {str(f.get('nombre'))[:44]:44} "
                f"P{firma_macros(f)[0]:6} H{firma_macros(f)[1]:6} G{firma_macros(f)[2]:6} "
                f"usos={usos.get(str(f.get('id')), 0):4} {'con URL' if f.get('url') else 'sin URL'}")

    # ---------- 1. MISMO NOMBRE ----------
    por_nombre = defaultdict(list)
    for f in foods:
        por_nombre[normalizar(f.get("nombre"))].append(f)
    iguales = {k: v for k, v in por_nombre.items() if k and len(v) > 1}
    print(f"1) MISMO NOMBRE: {len(iguales)} nombres repetidos, {sum(len(v) - 1 for v in iguales.values())} filas de mas")
    for k, v in sorted(iguales.items(), key=lambda kv: -len(kv[1]))[:20]:
        print(f"   \"{k}\"")
        for f in v:
            print(ficha(f))

    # ---------- 2 y 3. NOMBRES PARECIDOS ----------
    # Solo se comparan alimentos que comparten al menos una palabra: comparar 3.211 con
    # 3.211 son cinco millones de pares, y la inmensa mayoria no se parecen en nada.
    por_palabra = defaultdict(list)
    for i, f in enumerate(foods):
        for p in palabras(f.get("nombre")):
            if len(p) > 2:
                por_palabra[p].append(i)

    vistos, mismos_macros, solo_nombre = set(), [], []
    for indices in por_palabra.values():
        if len(indices) > 400:      # palabras como "de" o "sin": no discriminan
            continue
        for x in range(len(indices)):
            for y in range(x + 1, len(indices)):
                par = (indices[x], indices[y])
                if par in vistos:
                    continue
                vistos.add(par)
                a, b = foods[indices[x]], foods[indices[y]]
                if normalizar(a.get("nombre")) == normalizar(b.get("nombre")):
                    continue                       # ya salio en la red 1
                s = parecido(a.get("nombre"), b.get("nombre"))
                if s < PARECIDO_MINIMO:
                    continue
                if firma_macros(a) == firma_macros(b) and firma_macros(a) != (0.0, 0.0, 0.0):
                    mismos_macros.append((s, a, b))
                else:
                    solo_nombre.append((s, a, b))

    mismos_macros.sort(key=lambda t: -t[0])
    solo_nombre.sort(key=lambda t: -t[0])

    # PAREJA MARCA/GENERICO, QUE ES A PROPOSITO. En este catalogo un alimento con URL es de
    # marca y uno sin URL es generico, y para muchos productos existen los dos a proposito:
    # "Alitas de pollo frescas (Aldelis)" y "Alitas de pollo frescas". Tienen la misma tabla
    # porque el generico se saco de la marca. NO son duplicados y borrar uno romperia las
    # dietas que lo usan. Se separan para no contarlos como basura.
    def es_pareja_marca_generico(a, b):
        con_url = [x for x in (a, b) if x.get("url")]
        sin_url = [x for x in (a, b) if not x.get("url")]
        if len(con_url) != 1 or len(sin_url) != 1:
            return False
        # El generico es el nombre de la marca sin el parentesis: sus palabras estan
        # contenidas en las del otro.
        return palabras(sin_url[0].get("nombre")) <= palabras(con_url[0].get("nombre"))

    parejas = [t for t in mismos_macros if es_pareja_marca_generico(t[1], t[2])]
    de_verdad = [t for t in mismos_macros if not es_pareja_marca_generico(t[1], t[2])]

    print(f"\n2) NOMBRE PARECIDO Y MISMOS MACROS: {len(mismos_macros)} pares")
    print(f"   de esos, {len(parejas)} son la pareja marca/generico DE PROPOSITO "
          f"(uno con URL y otro sin ella, mismo nombre sin el parentesis): no se tocan.")
    print(f"   quedan {len(de_verdad)} que si parecen duplicados:")
    for s, a, b in de_verdad[:25]:
        print(f"   parecido {s:.2f}")
        print(ficha(a))
        print(ficha(b))

    print(f"\n3) NOMBRE PARECIDO PERO MACROS DISTINTOS (revisar, no borrar): {len(solo_nombre)} pares")
    print("   Son los que menciona el punto: 'pistacho generico' / 'tostados con sal' /")
    print("   'tostados sin sal' son productos distintos y tienen que seguir estando.")
    for s, a, b in solo_nombre[:15]:
        print(f"   parecido {s:.2f}")
        print(ficha(a))
        print(ficha(b))

    # ---------- 4. TABLAS IMPOSIBLES ----------
    # Salio de mirar los duplicados: "Tortita de maiz (Hacendado)" tiene 125 g de grasa por
    # cada 100 g de producto. En 100 g de comida no caben mas de 100 g de macros, y una
    # tortita de maiz no tiene grasa. Un numero asi no descuadra un plato: descuadra el dia
    # entero, porque el motor dimensiona contra el.
    print("\n4) TABLAS IMPOSIBLES (mas de 100 g de macros en 100 g de producto)")
    # Solo los que se cuentan POR 100 G. Los menus de Burger King llevan la tabla del menu
    # entero -- 175 g de hidratos es un menu, no 100 g de producto -- y estan asi a
    # proposito: van por unidades. Meterlos aqui llenaba la lista de falsos positivos y
    # tapaba el unico caso de verdad.
    # Dos reglas distintas, porque los macros se leen distinto segun el alimento (lo dice
    # `_size_food`: `macros_at(a, cant)` con `cant` en unidades si el alimento va por
    # unidades, y en gramos si va a granel):
    #
    #   - A GRANEL: los macros son por 100 g. La suma no puede pasar de 100.
    #   - POR UNIDADES: los macros son por unidad. Ninguno puede pesar mas que la unidad
    #     entera. Los menus de Burger King pasan porque su racion ES el menu (400 g).
    #
    # Se pide racion >= 3 g en el segundo caso: hay alimentos con `racion: 1` que no es un
    # peso sino un marcador, y colarlos aqui llenaba la lista de falsos positivos.
    imposibles = []
    for f in foods:
        try:
            racion = float(f.get("racion") or 100)
        except (TypeError, ValueError):
            racion = 100.0
        p, h, g = firma_macros(f)
        por_unidades = bool(f.get("unidades") or f.get("por_unidad"))
        if por_unidades:
            if racion >= 3 and max(p, h, g) > racion:
                imposibles.append((max(p, h, g) - racion, f, racion))
        elif (p + h + g) > 101:      # 1 g de margen: las tablas redondean
            imposibles.append((p + h + g - 100, f, 100.0))
    imposibles.sort(key=lambda t: -t[0])
    print(f"   {len(imposibles)} alimentos")
    for _, f, racion in imposibles[:20]:
        p, h, g = firma_macros(f)
        print(f"      racion {racion:6.0f} g, macros {p + h + g:6.1f} g" + ficha(f)[9:])

    print(f"\nRESUMEN")
    print(f"   {sum(len(v) - 1 for v in iguales.values())} duplicados seguros (mismo nombre exacto)")
    print(f"   {len(de_verdad)} pares con nombre parecido y la misma tabla, que hay que mirar")
    print(f"   {len(parejas)} parejas marca/generico: A PROPOSITO, no se tocan")
    print(f"   {len(solo_nombre)} pares con nombre parecido pero tabla distinta: productos distintos")


if __name__ == "__main__":
    asyncio.run(main())
