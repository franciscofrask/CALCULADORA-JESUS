# -*- coding: utf-8 -*-
"""Las fichas de la guía de suplementación, TAL CUAL están en la web (doc 19-08, bloque 08).

Scrape del 20-08 con la sesión de Francisco sobre
noteconformesconmenos.com/membresia-elm/suplementacion-recomendada: las 12 opciones del
filtro una a una, más las dos fichas que solo salen en el listado completo (Citrulina y
la crema RELIEF). Los textos van literales; no hay una palabra inventada.

La regla del maquetado, comprobada ficha a ficha: el texto que aparece ENTRE el ¿Cuánto?
de una ficha y el título de la siguiente pertenece a la SIGUIENTE («Guárdalo siempre en
frío» antes de Omega 3 es del Omega 3; «4 pastillas serían 300 mg» antes del Fat burner
de 75 mg/cápsula es del Fat burner).

Escribe db.guia_suplementos (la colección que sirve GET /supplements/guia): borra y
reinserta, así que es idempotente. No toca db.supplements (los bloques de protocolo del
coach) ni el catálogo de admin.

Uso:  ./venv/Scripts/python.exe _importar_guia_web.py            # dev
      MONGO_URL=... DB_NAME=jg12_prod ... _importar_guia_web.py  # prod
"""
import asyncio
import os

from motor.motor_asyncio import AsyncIOMotorClient

FG = "https://fullgas.org/es/"

FICHAS = [
    {"nombre": "MAP o EAA´S", "secciones": ["basicos"],
     "cuando": "Durante el entreno",
     "cuanto": "La cantidad que se ajuste a los macros de proteínas que tengas asignados (normalmente entre 5 y 10 g)",
     "enlaces": [FG + "aminoacidos-esenciales-eaas/37-map-amino-esenciales-sandia-300g-8436580133487.html?fg=5"]},

    {"nombre": "Monohidrato de creatina", "secciones": ["basicos", "rendimiento"],
     "cuando": "Todos los días, con el desayuno (entrenes o no)",
     "cuanto": "1 gramo por cada 10 kg de peso (ejemplo: si pesas 70 kg, tendrías que tomar 7 g)",
     "enlaces": [FG + "creatina/346-creatina-monohidrato-200-mesh-250g-8436580134866.html?fg=5"]},

    {"nombre": "Omega 3", "secciones": ["basicos", "salud"], "subfiltros": ["Colesterol"],
     "que_es": "Guárdalo siempre en frío.",
     "cuando": "Todos los días, en dos tomas (desayuno y cena)",
     "cuanto": "2-3 perlas por toma (entre 4 y 6 g diarios)",
     "enlaces": [FG + "acidos-grasos-esenciales/19-omega3-180-softgel-8436580132398.html?fg=5"]},

    {"nombre": "Whey Isolate + crema de arroz", "secciones": ["basicos", "alimentos"],
     "cuando": "Especialmente recomendable después de entrenar, pero también lo puedes emplear en cualquier momento del día (trátalos como dos alimentos más)",
     "cuanto": "La cantidad que se ajuste a los macros que tengas asignados",
     "enlaces": [FG + "aislado-whey-90/168000-isolate-whey-cookies-and-cream08kg-8436580132954.html?fg=5"]},

    {"nombre": "Whey Isolate o Iso Micellar casein + harina de avena", "secciones": ["alimentos"],
     "cuando": "En cualquier momento del día, como una comida más",
     "cuanto": "La cantidad que se ajuste a los macros que tengas asignados",
     "enlaces": [FG + "aislado-whey-90/168-100-isolate-whey-cookies-and-cream-18kg-8436580132954.html?fg=5"]},

    {"nombre": "Amilopectina", "secciones": ["alimentos", "volumen"],
     "cuando": "Durante el entreno, aunque la ciclodextrina es mejor opción. También lo puedes utilizar en la comida postentreno de después o en cualquier momento del día como un alimento más.",
     "cuanto": "La cantidad que se ajuste a los macros de hidratos de carbono que tengas asignados",
     "enlaces": [FG + "premium-quality/215-carbolider-manzana-verde-19kg-8436580131513.html?fg=5"]},

    {"nombre": "Ciclodextrina", "secciones": ["alimentos", "volumen"],
     "cuando": "Durante el entreno, es el mejor hidrato para eso. También lo puedes utilizar en el postentreno o en cualquier otro momento del día como un alimento más, pero yo lo reservaría solo para la bebida intra.",
     "cuanto": "La cantidad que se ajuste a los macros de hidratos de carbono que tengas asignados",
     "enlaces": [FG + "hidratos-de-carbono/21-ciclodextrina-cluster-dextrin-neutro-1kg-8436580131612.html?fg=5"]},

    {"nombre": "Cafeína anhidra 100 mg", "secciones": ["definicion", "rendimiento"],
     "que_es": "Este protocolo está indicado para personas muy sensibles a la cafeína.\n"
               "No hacer la segunda toma más allá de las 6 de la tarde en ningún caso.",
     "cuando": "Todos los días, en dos tomas (al menos 5-6 horas de separación entre ambas). "
               "Si entrenas por la tarde y puedes hacer coincidir la segunda toma con el momento previo al entreno (unos 30 minutos antes) sería ideal.\n"
               "Si eres extremadamente sensible a la cafeína, puedes empezar por solo una toma la primera semana y después, si todo va bien, subir a 2 en la segunda.",
     "cuanto": "1 cápsula en cada toma la primera semana y luego ir subiendo de forma gradual según tolerancia.\n"
               "Semana 2: 2 y 1\nSemana 3 y 4: 2 y 2"},

    {"nombre": "Cafeína anhidra 200 mg", "secciones": ["definicion", "rendimiento"],
     "que_es": "Este protocolo habría que ajustarlo en función de la tolerancia de la persona a los estimulantes, lo cual es tremendamente individual.\n"
               "Como orientación general, una dosis efectiva de cafeína estaría entre 3 y 6 mg por kg de peso (por ejemplo, si pesas 100 kg, serían entre 300 y 600 mg al día)",
     "cuando": "Todos los días. La primera semana haces una sola toma (al despertar) y a partir de la segunda semana haces dos (al menos 5-6 horas de separación entre ambas).\n"
               "Si entrenas por la tarde y puedes hacer coincidir la segunda toma con el momento previo al entreno (unos 30 minutos antes) sería ideal.\n"
               "No hacer la segunda toma más allá de las 6 de la tarde en ningún caso.",
     "cuanto": "1 cápsula al despertar la primera semana y luego ir subiendo de forma gradual según tolerancia.\n"
               "Semanas 2 y 3: 1 y 1\nSemanas 4 y 5: 2 y 1\nSemanas 6 y 7: 2 y 2 (esta sería la dosis máxima)\n"
               "Semanas 8 y 9: o bien mantener la dosis, o bien iniciar la bajada de forma gradual.\n"
               "Ejemplo de cómo hacer la bajada (en caso de haber llegado a la dosis máxima):\n"
               "1 semana con 1 y 1\n1 semana con 1 (al despertar)",
     "enlaces": [FG + "preentrenamiento/284-cafeina-anhidra-200mg-60caps-8436580133517.html?fg=5"]},

    {"nombre": "Fat burner hardcore (termogénico / 75 mg cafeína por cápsula)",
     "secciones": ["definicion", "rendimiento"],
     "que_es": "Este protocolo habría que ajustarlo en función de la tolerancia de la persona a los estimulantes, lo cual es tremendamente individual.\n"
               "Como orientación general, una dosis efectiva de cafeína estaría entre 3 y 6 mg por kg de peso (por ejemplo, si pesas 100 kg, serían entre 300 y 600 mg al día).\n"
               "En el caso de este suplemento en concreto, 4 pastillas serían 300 mg.",
     "cuando": "Todos los días. La primera semana haces una sola toma (al despertar) y a partir de la segunda semana haces dos (al menos 5-6 horas de separación entre ambas).\n"
               "Si entrenas por la tarde y puedes hacer coincidir la segunda toma con el momento previo al entreno (unos 30 minutos antes) sería ideal.\n"
               "No hacer la segunda toma más allá de las 6 de la tarde en ningún caso.",
     "cuanto": "1 cápsula al despertar la primera semana y luego ir subiendo de forma gradual según tolerancia. Este es un ejemplo de un protocolo largo, para 4 meses aproximadamente:\n"
               "Semanas 2 y 3: 1 y 1\nSemanas 4 y 5: 2 y 1\nSemanas 6 y 7: 2 y 2\nSemanas 8 y 9: 3 y 2\n"
               "Semanas 10 y 11: 3 y 3 (esta sería la dosis máxima)\n"
               "Semanas 12 y 13: o bien mantener la dosis, o bien iniciar la bajada de forma gradual.\n"
               "Ejemplo de cómo hacer la bajada (en caso de haber llegado a la dosis máxima):\n"
               "1 semana con 2 y 2\n1 semana con 1 y 1\n1 semana con 1 (al despertar)",
     "enlaces": [FG + "control-de-peso/114-fat-burner-hardcore-thermogenic-formula-120-caps-8436580133289.html?fg=5"]},

    {"nombre": "Sinefrina (30 mg)", "secciones": ["definicion", "rendimiento"],
     "que_es": "Se puede combinar perfectamente con la cafeína (de hecho, sería lo ideal).",
     "cuando": "Todos los días. La primera semana haces una sola toma (al despertar) y a partir de la segunda semana haces dos (al menos 5-6 horas de separación entre ambas).\n"
               "Si entrenas por la tarde y puedes hacer coincidir la segunda toma con el momento previo al entreno (unos 30 minutos antes) sería ideal.\n"
               "No hacer la segunda toma más allá de las 6 de la tarde en ningún caso.",
     "cuanto": "1 cápsula al despertar la primera semana y luego ir subiendo de forma gradual según tolerancia.\n"
               "Semanas 2 y 3: 1 y 1\nSemanas 4 y 5: 2 y 1\nSemanas 6 y 7: 2 y 2 (esta sería la dosis máxima)\n"
               "Semanas 8 y 9: o bien mantener la dosis, o bien iniciar la bajada de forma gradual.\n"
               "Ejemplo de cómo hacer la bajada (en caso de haber llegado a la dosis máxima):\n"
               "1 semana con 1 y 1\n1 semana con 1 (al despertar)",
     "enlaces": [FG + "preentrenamiento/342-thermo-synephrine-20mg-60caps-8436580134842.html?fg=5"]},

    {"nombre": "Glicerol", "secciones": ["rendimiento"],
     "cuando": "Durante el entrenamiento, diluido en la bebida intraentreno",
     "cuanto": "5 ml",
     "enlaces": [FG + "hidratos-de-carbono/266-glicerina-glicerol-995-250ml-8436580133432.html?fg=5"]},

    {"nombre": "Pre-workout", "secciones": ["rendimiento"],
     "cuando": "Solamente los días que entrenes fuerza, unos 30 minutos antes de empezar",
     "cuanto": "2 dosificadores (12 g aproximadamente). Si toleras bien la dosis, sube a 3 a partir de la segunda semana.",
     "enlaces": [FG + "preentrenamiento/340-preworkout-mandarina-170g-8436580134521.html?fg=5"]},

    {"nombre": "Total electrolitos", "secciones": ["rendimiento"],
     "cuando": "Inmediatamente antes de entrenar",
     "cuanto": "4 cápsulas",
     "enlaces": [FG + "vitaminas-y-minerales/27-total-electrolitos-60-caps-8436580132770.html?fg=5"]},

    {"nombre": "Aceite de CBD al 40 %", "secciones": ["descanso"],
     "que_es": "1 gota de este aceite aporta 16 mg de CBD de la mayor calidad y pureza.",
     "cuando": "Todos los días, aproximadamente 1 hora antes de acostarte",
     "cuanto": "La dosis recomendada suele variar entre los 4 y los 23 mg de aceite por cada 10 kg peso, en función del grado de tolerancia de cada uno (de igual forma, puede ser necesaria incrementarla o no)"},

    {"nombre": "Melatonina", "secciones": ["descanso"],
     "cuando": "Aproximadamente 45 minutos antes de irte a la cama",
     "cuanto": "Según tolerancia. Lo suyo es empezar por una dosis baja (1,9 mg, lo que contiene una pastilla) e ir subiendo si fuera necesario hasta notar los efectos deseados (una dosis media efectiva está normalmente entre los 2 y los 6 mg).",
     "enlaces": [FG + "salud-y-bienestar/345-true-dream-60-caps-19mg-8436580134194.html?fg=5"]},

    {"nombre": "Aceite de krill", "secciones": ["salud"], "subfiltros": ["Colesterol"],
     "que_es": "Guárdalo siempre en frío.",
     "cuando": "Todos los días, en dos tomas (desayuno y cena)",
     "cuanto": "3 perlas por toma (3 g al día)",
     "enlaces": [FG + "acidos-grasos-esenciales/36-aceite-de-krill-superba-boost-60-softgel-8436580132312.html?fg=5"]},

    {"nombre": "Monacolina K", "secciones": ["salud"], "subfiltros": ["Colesterol"],
     "que_es": "Indicado para bajar los niveles de colesterol LDL",
     "cuando": "Todos los días, en el desayuno",
     "cuanto": "10 mg"},

    {"nombre": "Niacina Flush Free", "secciones": ["salud"], "subfiltros": ["Colesterol"],
     "que_es": "Indicado para subir los niveles de colesterol HDL",
     "cuando": "Todos los días, en dos tomas (desayuno y cena)",
     "cuanto": "3 g por toma (6 g al día)"},

    {"nombre": "Probiótico Megaflora 9 EVOLUTION (FullGas)", "secciones": ["salud"], "subfiltros": ["Digestivo"],
     "cuando": "En el desayuno, durante 30 días.",
     "cuanto": "2 cápsulas",
     "enlaces": [FG + "salud-y-bienestar/64-probiotico-megaflora-9-evo-60-caps-8436580132442.html?fg=5"]},

    {"nombre": "Berberina 500", "secciones": ["salud"], "subfiltros": ["Glucosa"],
     "cuando": "Todos los días, en dos tomas (desayuno y cena)",
     "cuanto": "500 mg por toma"},

    {"nombre": "NAC", "secciones": ["salud"], "subfiltros": ["Hepático"],
     "cuando": "Todos los días, en dos tomas (desayuno y cena)",
     "cuanto": "1 cápsula por toma",
     "enlaces": [FG + "salud-y-bienestar/63-nac-n-acetil-l-cisteina-60-caps-8436580130103.html?fg=5"]},

    {"nombre": "SAME + Betaína", "secciones": ["salud"], "subfiltros": ["Hepático"],
     "que_es": "Guárdalo siempre en frío.",
     "cuando": "Con el desayuno",
     "cuanto": "3 cápsulas",
     "enlaces": [FG + "salud-y-bienestar/38-same-betaina-60-caps-8436580133104.html?fg=5"]},

    {"nombre": "Silimarina", "secciones": ["salud"], "subfiltros": ["Hepático"],
     "cuando": "Todos los días, en dos tomas (desayuno y cena)",
     "cuanto": "150 mg por toma"},

    {"nombre": "Vitamina D3 + Magnesio", "secciones": ["salud"], "subfiltros": ["Salud ósea", "Sistema inmune"],
     "cuando": "Todos los días, en el desayuno",
     "cuanto": "4-6 perlas (4000-6000 ui de vitamina D3)",
     "enlaces": [FG + "vitaminas-y-minerales/502-vitamina-d3-mg-bisglicinato-120caps-8436580135795.html?fg=5"]},

    {"nombre": "Sport Vitamin Premium (complejo vitamínico)", "secciones": ["salud"], "subfiltros": ["Sistema inmune"],
     "cuando": "Todos los días, en el desayuno",
     "cuanto": "1 cápsula",
     "enlaces": [FG + "vitaminas-y-minerales/59-sport-vitamin-premium-60-caps-8436580132541.html?fg=5"]},

    # Las dos que solo salen en el listado completo de la web, sin categoría asignada allí.
    {"nombre": "Citrulina malato", "secciones": [],
     "que_es": "A ser posible, una de las tomas (los días de entreno, que sea la toma que haces antes) la acompañas de 1 Potenciator (aspartato de arginina). Tómalo sólo durante 6 semanas.",
     "cuando": "En dos tomas, mañana y noche (los días de entrenamiento haz coincidir una de las tomas con el momento previo al entreno)",
     "cuanto": "5 g por toma (10 g al día)"},

    {"nombre": "Crema RELIEF EFFECT", "secciones": [],
     "que_es": "Como con cualquier crema corporal, extiéndela sobre la zona a tratar y espera que se absorba.",
     "cuando": "Después del ejercicio, en la zona que hayas entrenado o que sientas dolorida",
     "cuanto": "La cantidad que se debe aplicar debe ser similar al tamaño de una almendra"},
]


def _cfg():
    if os.environ.get("MONGO_URL"):
        return os.environ["MONGO_URL"], os.environ.get("DB_NAME", "jg12_prod")
    from dotenv import dotenv_values
    cfg = dotenv_values(os.path.join(os.path.dirname(__file__), ".env"))
    return cfg["MONGO_URL"], cfg["DB_NAME"]


async def main():
    import re
    import unicodedata
    url, nombre_db = _cfg()
    db = AsyncIOMotorClient(url)[nombre_db]

    def slug(s):
        s = unicodedata.normalize("NFD", s.lower())
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
        return re.sub(r"[^a-z0-9]+", "-", s).strip("-")

    docs = []
    for i, f in enumerate(FICHAS):
        docs.append({
            "id": slug(f["nombre"]), "orden": i + 1,
            "nombre": f["nombre"],
            "que_es": f.get("que_es"), "cuando": f.get("cuando"), "cuanto": f.get("cuanto"),
            "secciones": f.get("secciones", []), "subfiltros": f.get("subfiltros", []),
            "enlaces": f.get("enlaces", []),
            "source": "web_guia_20260820",
        })

    await db.guia_suplementos.delete_many({})
    await db.guia_suplementos.insert_many(docs)
    print(f"{nombre_db}: {len(docs)} fichas de la guía escritas en db.guia_suplementos")


asyncio.run(main())
