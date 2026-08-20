# -*- coding: utf-8 -*-
"""Asignar a cada ficha de la guía su sección (doc 19-08, bloque 08).

El mapa sale del scrape de noteconformesconmenos.com/membresia-elm/suplementacion-recomendada
hecho el 20-08 con la sesión de Francisco: las 12 opciones del filtro de la web, una a una.
Una ficha puede vivir en varias secciones (la creatina está en Básicos y en Rendimiento).

Escribe en db.supplements: `secciones` (lista de claves) y `subfiltros` (los de Salud).
Y deja el texto de entrada LITERAL de la web en db.app_state (clave guia_suplementacion).

Idempotente: pisa esos tres campos con el mapa, no toca nada más. Lo que no case lo lista.

Uso:  ./venv/Scripts/python.exe _asignar_secciones_guia.py            # dev
      MONGO_URL=... DB_NAME=jg12_prod ... _asignar_secciones_guia.py  # prod
"""
import asyncio
import os
import re
import unicodedata

from motor.motor_asyncio import AsyncIOMotorClient

# categoría de la web -> (clave de sección, subfiltro de Salud o None)
CATEGORIAS = {
    "Alimentos": ("alimentos", None),
    "Básicos": ("basicos", None),
    "Definición": ("definicion", None),
    "Descanso": ("descanso", None),
    "Rendimiento": ("rendimiento", None),
    "Salud - Colesterol (corazón)": ("salud", "Colesterol"),
    "Salud - Digestivo": ("salud", "Digestivo"),
    "Salud - Glucosa": ("salud", "Glucosa"),
    "Salud - Hepático": ("salud", "Hepático"),
    "Salud - Salud ósea": ("salud", "Salud ósea"),
    "Salud - Sistema inmune": ("salud", "Sistema inmune"),
    "Volumen": ("volumen", None),
}

# Lo que enseña la web, tal cual (scrape 20-08).
MAPA_WEB = {
    "Alimentos": ["Amilopectina", "Ciclodextrina", "Whey Isolate + crema de arroz",
                  "Whey Isolate o Iso Micellar casein + harina de avena"],
    "Básicos": ["MAP o EAA´S", "Monohidrato de creatina", "Omega 3", "Whey Isolate + crema de arroz"],
    "Definición": ["Cafeína anhidra 100 mg", "Cafeína anhidra 200 mg",
                   "Fat burner hardcore (termogénico / 75 mg cafeína por cápsula)", "Sinefrina (30 mg)"],
    "Descanso": ["Aceite de CBD al 40 %", "Melatonina"],
    "Rendimiento": ["Cafeína anhidra 100 mg", "Cafeína anhidra 200 mg",
                    "Fat burner hardcore (termogénico / 75 mg cafeína por cápsula)", "Glicerol",
                    "Monohidrato de creatina", "Pre-workout", "Sinefrina (30 mg)", "Total electrolitos"],
    "Salud - Colesterol (corazón)": ["Aceite de krill", "Monacolina K", "Niacina Flush Free", "Omega 3"],
    "Salud - Digestivo": ["Probiótico Megaflora 9 EVOLUTION (FullGas)"],
    "Salud - Glucosa": ["Berberina 500"],
    "Salud - Hepático": ["NAC", "SAME + Betaína", "Silimarina"],
    "Salud - Salud ósea": ["Vitamina D3 + Magnesio"],
    "Salud - Sistema inmune": ["Sport Vitamin Premium (complejo vitamínico)", "Vitamina D3 + Magnesio"],
    "Volumen": ["Amilopectina", "Ciclodextrina"],
}

# El texto de entrada de la página, sin cambiarlo («El texto de entrada: sin cambiarlo»).
TEXTO_ENTRADA = (
    "Estos son los suplementos que más utilizo y recomiendo, con pautas exactas sobre su uso.\n"
    "Están organizados por categorías según su función.\n"
    "En condiciones normales, te recomiendo empezar con los básicos.\n"
    "Si estás en fase de definición, dentro del Catálogo Premium tienes también la Guía "
    "básica de suplementación para perder grasa, con los protocolos más efectivos basados "
    "en mi experiencia de años. Son directos, prácticos y los puedes aplicar tal cual.\n"
    "*IMPORTANTE: tienes un descuento especial en FullGas con el código GALLEGOVIP "
    "(lo tendrás activo todo el tiempo que dure tu suscripción). Te aplicarán un 20% en toda la web"
)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]+", " ", s).strip()


def _cfg():
    if os.environ.get("MONGO_URL"):
        return os.environ["MONGO_URL"], os.environ.get("DB_NAME", "jg12_prod")
    from dotenv import dotenv_values
    cfg = dotenv_values(os.path.join(os.path.dirname(__file__), ".env"))
    return cfg["MONGO_URL"], cfg["DB_NAME"]


async def main():
    url, nombre_db = _cfg()
    db = AsyncIOMotorClient(url)[nombre_db]
    fichas = await db.supplements.find({}, {"_id": 0, "id": 1, "nombre": 1}).to_list(500)
    por_norma = {_norm(f["nombre"]): f for f in fichas}

    def casar(titulo_web: str):
        n = _norm(titulo_web)
        if n in por_norma:
            return por_norma[n]
        # tolerante: el nombre de la web contenido en el de la ficha o al reves, con el
        # candidato mas corto (el mas especifico gana sobre "pack de...")
        candidatos = [f for k, f in por_norma.items() if n in k or k in n]
        if candidatos:
            return sorted(candidatos, key=lambda f: len(f["nombre"]))[0]
        # ultima pasada: por la primera palabra gorda (creatina, melatonina...)
        gordas = [w for w in n.split() if len(w) > 5]
        if gordas:
            candidatos = [f for k, f in por_norma.items() if gordas[0] in k]
            if len(candidatos) == 1:
                return candidatos[0]
        return None

    asignaciones = {}      # id de ficha -> {"secciones": set, "subfiltros": set}
    sin_casar = []
    for cat, titulos in MAPA_WEB.items():
        clave, sub = CATEGORIAS[cat]
        for t in titulos:
            f = casar(t)
            if not f:
                sin_casar.append((cat, t))
                continue
            a = asignaciones.setdefault(f["id"], {"secciones": set(), "subfiltros": set(), "nombre": f["nombre"]})
            a["secciones"].add(clave)
            if sub:
                a["subfiltros"].add(sub)

    for fid, a in asignaciones.items():
        await db.supplements.update_one({"id": fid}, {"$set": {
            "secciones": sorted(a["secciones"]),
            "subfiltros": sorted(a["subfiltros"]),
        }})
        print(f"  {a['nombre']}: {sorted(a['secciones'])}" + (f" {sorted(a['subfiltros'])}" if a["subfiltros"] else ""))

    await db.app_state.update_one(
        {"clave": "guia_suplementacion"},
        {"$set": {"texto_entrada": TEXTO_ENTRADA}},
        upsert=True)

    print(f"\n{nombre_db}: {len(asignaciones)} fichas con seccion; texto de entrada guardado.")
    if sin_casar:
        print("SIN CASAR (revisar a mano):")
        for cat, t in sin_casar:
            print(f"  {cat} · {t}")


asyncio.run(main())
