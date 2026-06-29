"""
Semilla del catálogo de suplementos (db.supplement_catalog).
Porta un set base/común del método (textos de timing/dosis reales de Calma).
Idempotente: reemplaza los ítems marcados con seed=True, conserva los creados a mano.

Uso:  venv/Scripts/python seed_supplements.py
"""
import asyncio
from dotenv import load_dotenv
load_dotenv()
from core.database import db

# Textos de "cuándo" (timing) reutilizados
MN = "Todos los días, con el desayuno (entrenes o no)"
DOS = "Todos los días, en dos tomas (desayuno y cena)"
INTRA = "Durante el entreno"
PRE = "Unos 30 minutos antes de empezar a entrenar"
DESAY = "Todos los días, en el desayuno"
NOCHE = "Todos los días, aproximadamente 1 hora antes de acostarte"
SOLO_ENTRENO = "Solamente los días que entrenes fuerza, unos 30 minutos antes de empezar"
SEGUN_MACROS = "La cantidad que se ajuste a los macros que tengas asignados"

# (slug, titulo, sexo, categoria, objetivo, cuando, cuanto, observaciones)
SEED = [
    ("creatina-hombre", "Monohidrato de creatina", "hombre", "base", "ambos", MN, "10 g", None),
    ("creatina-mujer", "Monohidrato de creatina", "mujer", "base", "ambos", MN, "5 g", None),
    ("omega3-hombre", "Omega 3", "hombre", "base", "ambos", DOS, "2 perlas por toma", None),
    ("omega3-mujer", "Omega 3", "mujer", "base", "ambos", DOS, "2 perlas por toma", None),
    ("vitamina-d3-k2", "Vitamina D3 + K2", "ambos", "base", "ambos", MN, "2 perlas", None),
    ("multivitaminico", "Sport Vitamin Premium (multivitamínico)", "ambos", "salud", "ambos", MN, "Según etiqueta", None),
    ("whey-post", "Whey Isolate + crema de arroz (post-entreno)", "ambos", "intra", "ambos", "Justo después de entrenar", SEGUN_MACROS,
     "Es comida: cuenta en tus macros del post-entreno (no es un extra)."),
    ("bebida-intra", "Bebida intraentreno adicional", "ambos", "intra", "ambos", INTRA, SEGUN_MACROS,
     "Carbohidrato intraentreno; puede usarse como única fuente o combinado."),
    ("electrolitos", "Total electrolitos", "ambos", "salud", "ambos", "Todos los días, repartidos en el día", "Según necesidad / sudoración", None),
    ("melatonina", "Melatonina (True Dream)", "ambos", "sueno", "ambos", NOCHE, "1-2 mg", None),
    ("cafeina-200", "Cafeína anhidra 200 mg", "ambos", "rendimiento", "ambos", PRE, "200 mg", "Solo días de entreno; evita por la tarde/noche."),
    ("preworkout", "Pre-workout", "ambos", "rendimiento", "ambos", PRE, "1 dosis", None),
    ("fat-burner", "Fat burner hardcore (termogénico)", "ambos", "quemador", "definicion", DESAY, "Según protocolo (escalado por meses)",
     "Protocolo periodizado por fases. Solo en definición."),
    ("cbd-30", "Aceite de CBD al 30%", "ambos", "salud", "ambos", NOCHE, "Según tolerancia (subir gradual)", None),
    ("nac", "NAC", "ambos", "salud", "ambos", MN, "1 cápsula", None),
    ("selenio", "Selenio (100 mcg)", "ambos", "salud", "ambos", DESAY, "1 cápsula", None),
]

# Imágenes portadas del catálogo de Calma (fullgas.org / fuentes del bundle)
IMG = {
    "creatina-hombre": "https://fullgas.org/1541-medium_default/creatina-monohidrato-200-mesh-250g.jpg",
    "creatina-mujer": "https://fullgas.org/1541-medium_default/creatina-monohidrato-200-mesh-250g.jpg",
    "omega3-hombre": "https://fullgas.org/669-large_default/omega3-180-softgel.jpg",
    "omega3-mujer": "https://fullgas.org/669-large_default/omega3-180-softgel.jpg",
    "vitamina-d3-k2": "https://fullgas.org/666-large_default/vitamina-d3-k2vital-60-softgel.jpg",
    "multivitaminico": "https://fullgas.org/1133-large_default/sport-vitamin-premium-60-caps.jpg",
    "whey-post": "https://fullgas.org/705-cart_default/100-isolate-whey-cookies-and-cream-18kg.jpg",
    "bebida-intra": "https://fullgas.org/926-large_default/shaker-fullgas-700-cc-verde.jpg",
    "electrolitos": "https://fullgas.org/1607-large_default/total-electrolitos-60-caps.jpg",
    "melatonina": "https://fullgas.org/1430-medium_default/true-dream-60-caps-19mg.jpg",
    "preworkout": "https://fullgas.org/1117-large_default/preworkout-mandarina-170g.jpg",
    "cbd-30": "https://tantrumcbd.es/wp-content/uploads/2022/06/Frontal-JESUS-30.png",
    "nac": "https://fullgas.org/1165-large_default/nac-n-acetil-l-cisteina-60-caps.jpg",
    "selenio": "https://m.media-amazon.com/images/I/51ZP21FExxL._AC_UL320_.jpg",
}


async def main():
    inserted = 0
    for i, (slug, titulo, sexo, cat, obj, cuando, cuanto, obs) in enumerate(SEED):
        doc = {
            "id": f"seed-{slug}",
            "titulo": titulo,
            "imagen": IMG.get(slug),
            "enlaces": [],
            "cuando": cuando,
            "cuanto": cuanto,
            "observaciones": obs,
            "sexo": sexo,
            "categoria": cat,
            "objetivo": obj,
            "orden": i,
            "activo": True,
            "seed": True,
        }
        await db.supplement_catalog.update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
        inserted += 1
    total = await db.supplement_catalog.count_documents({})
    print(f"Semilla OK: {inserted} ítems upsertados. Catálogo total: {total}")


if __name__ == "__main__":
    asyncio.run(main())
