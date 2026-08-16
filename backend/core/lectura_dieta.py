"""
Lee la dieta que trae el cliente y la traduce a macros (P10 del doc del 29-07).

Tres puertas de entrada, un solo resultado:
  - texto libre: "desayuno 80 g de avena y 4 huevos..."
  - un menu que ya tenga guardado en la calculadora
  - una foto de la dieta que le dieron

El cliente NO tiene que calcular nada: escribe o sube lo que come y aqui se traduce con las
reglas de conteo del metodo. Despues tiene que CONFIRMAR lo que hemos entendido; si no lo
confirma, este dato no entra en el calculo (manda por encima de todo lo demas, asi que no
puede colarse sin su visto bueno).
"""
import base64
import os
from typing import Dict, List, Optional

from calma_suggest import aplicar_regla_macros, macros_at
from chatbot import NutritionChatbot
from core.database import db

# Un dia de dieta con mas de esto no es un dia: es un error de lectura.
MAX_ALIMENTOS = 40


def _variantes(termino: str) -> List[str]:
    """El termino y su singular/plural, para no perder el generico por una letra.

    El cliente escribe «nueces» y quien lee la frase devuelve «nuez», que es lo correcto;
    pero el catalogo guarda «Nueces», y buscando «nuez» eso NO aparece: el unico resultado
    era «Leche de nuez (Borges)». Asi es como al cliente se le decia que desayuna una bebida
    vegetal porque habia escrito frutos secos.

    No es una lista de palabras -- eso esta prohibido en esta casa y ademas no escala --,
    son las dos reglas del plural en castellano: +s a la vocal y +es a la consonante, con la
    z que pasa a c (nuez -> nueces).
    """
    t = (termino or "").strip()
    if len(t) < 3:
        return [t] if t else []
    fuera = [t]
    if t.endswith(("s", "es")):                       # ya viene en plural: su singular
        fuera += [t[:-2], t[:-1]] if t.endswith("es") else [t[:-1]]
        if t.endswith("ces"):
            fuera.append(t[:-3] + "z")
    elif t.endswith("z"):                             # nuez -> nueces, pez -> peces
        fuera.append(t[:-1] + "ces")
    else:                                             # singular: su plural
        fuera.append(t + ("s" if t[-1] in "aeiou" else "es"))
    # Sin repetidos y sin restos de una letra.
    vistos, limpio = set(), []
    for v in fuera:
        v = v.strip()
        if len(v) >= 3 and v.lower() not in vistos:
            vistos.add(v.lower())
            limpio.append(v)
    return limpio


def _habla_de_lo_mismo(termino: str, nombre_alimento: str) -> bool:
    """Si la ficha del catalogo menciona lo que el cliente escribio.

    En castellano lo que distingue va al final: proteina de SUERO, leche de NUEZ, pechuga de
    POLLO. Asi que se mira esa ultima palabra (y su singular/plural) dentro del nombre de la
    ficha. «proteina de suero» contra «Proteina de soja» no pasa -- comparten «proteina»,
    que es justo lo que no distingue --, y «pechuga de pollo» contra «Pollo asado» si.

    Sirve para lo mismo que la regla de arriba: cuando no lo tenemos claro, se pregunta.
    """
    palabras = [p for p in (termino or "").lower().replace(",", " ").split()
                if len(p) > 2 and p not in ("del", "con", "sin", "para")]
    if not palabras:
        return True
    nombre = (nombre_alimento or "").lower()
    return any(v.lower() in nombre for v in _variantes(palabras[-1]))


async def _buscar_con_variantes(bot: NutritionChatbot, termino: str) -> List[Dict]:
    """Busca el termino y, si no sale ningun generico, lo intenta con su otra forma.

    Se para en cuanto una variante trae un generico: es la que de verdad describe lo que
    come, y no una marca que casualmente lleva esa palabra en el nombre.
    """
    primeros: List[Dict] = []
    for variante in _variantes(termino):
        encontrados = await bot.search_foods(variante, limit=6)
        if not encontrados:
            continue
        if not primeros:
            primeros = encontrados
        if any(not a.get("url") for a in encontrados):
            return encontrados
    return primeros


async def _macros_de_alimentos(bot: NutritionChatbot, extraidos: List[Dict]) -> Dict:
    """
    Busca cada alimento en el catalogo y suma sus macros CON LAS REGLAS DE CONTEO DEL METODO
    (las mismas que usan la calculadora y el asistente): la regla del 25%, las reglas por
    categoria y el ajuste por cantidad de cereales, panes y frutos secos.
    """
    total = {"proteina": 0.0, "hidratos": 0.0, "grasa": 0.0}
    detalle: List[Dict] = []
    no_reconocidos: List[str] = []

    for item in extraidos[:MAX_ALIMENTOS]:
        nombre = (item.get("nombre") or "").strip()
        if not nombre:
            continue
        encontrados = await _buscar_con_variantes(bot, nombre)
        if not encontrados:
            no_reconocidos.append(nombre)
            continue

        # Quien describe su dieta dice "pollo" o "ternera", no una marca concreta: se prefiere el
        # alimento generico (el que no tiene URL de ficha). Sin esto, "ternera" acababa en un plato
        # preparado de marca y "proteina en polvo" en cacahuete en polvo.
        generico = next((a for a in encontrados
                         if not a.get("url") and _habla_de_lo_mismo(nombre, a.get("nombre"))), None)

        # Y SI SOLO HAY MARCAS, NO SE ADIVINA. Es la regla de la casa para el asistente
        # ("los terminos genericos con tipos dispares no se adivinan, se preguntan"), y aqui
        # no hay a quien preguntar: el alta es de un tiro. Antes se cogia el primero que
        # saliera, asi que «ensalada» acababa en «Ensalada gourmet maxi (Carrefour)». Es
        # mejor decirle que eso no lo hemos entendido -- lo ve en la pantalla de confirmar y
        # lo escribe mejor -- que ponerle en la boca algo que no ha dicho.
        if generico is None:
            no_reconocidos.append(nombre)
            continue
        alimento = dict(generico)

        # Cuanto ha dicho que come. Los alimentos "por unidad" (huevos, cucharadas de aceite)
        # llevan los macros por unidad, no por 100 g: por eso la cantidad se pasa en la unidad
        # que espera el metodo y no se hace ninguna cuenta a mano.
        racion = float(alimento.get("racion") or 100) or 100.0
        por_unidad = bool(alimento.get("unidades"))
        cantidad, unidad = item.get("cantidad"), item.get("unidad")
        if cantidad is None:
            cantidad_metodo = 1.0 if por_unidad else racion
        elif unidad == "ud":
            cantidad_metodo = float(cantidad) if por_unidad else float(cantidad) * racion
        else:  # gramos
            cantidad_metodo = float(cantidad) / racion if por_unidad else float(cantidad)

        aplicar_regla_macros(alimento)          # pone a cero lo que no cuenta
        m = macros_at(alimento, cantidad_metodo)
        p, h, g = m.get("proteinas", 0.0), m.get("hidratos", 0.0), m.get("grasas", 0.0)
        total["proteina"] += p
        total["hidratos"] += h
        total["grasa"] += g
        detalle.append({
            "nombre": alimento.get("nombre"),
            "pedido": nombre,
            "cantidad_g": round(cantidad_metodo * racion if por_unidad else cantidad_metodo, 1),
            "macros": {"proteina": round(p, 1), "hidratos": round(h, 1), "grasa": round(g, 1)},
        })

    return {
        "macros": {k: int(round(v)) for k, v in total.items()},
        "alimentos": detalle,
        "no_reconocidos": no_reconocidos,
    }


async def leer_de_texto(texto: str, user_id: str) -> Dict:
    """Dieta escrita a mano por el cliente."""
    bot = NutritionChatbot(session_id=f"lectura-dieta-{user_id}", db=db)
    extraidos = await bot.extract_foods(texto)
    resultado = await _macros_de_alimentos(bot, extraidos)
    resultado["origen"] = "texto"
    return resultado


async def leer_de_menu_guardado(fecha: str, user_id: str) -> Dict:
    """
    Uno de sus dias ya montados en la calculadora. Aqui no hace falta interpretar nada: los
    macros de cada alimento estan ya calculados con las reglas del metodo.
    """
    dieta = await db.diets.find_one({"user_id": user_id, "fecha": fecha}, {"_id": 0})
    if not dieta:
        return {"error": "No encontramos ese día en tu calculadora", "origen": "menu"}

    total = {"proteina": 0.0, "hidratos": 0.0, "grasa": 0.0}
    detalle = []
    for comida in (dieta.get("comidas") or {}).values():
        for a in ((comida or {}).get("alimentos") or []):
            m = a.get("macros_efectivos") or {}
            p, h, g = float(m.get("P") or 0), float(m.get("H") or 0), float(m.get("G") or 0)
            total["proteina"] += p
            total["hidratos"] += h
            total["grasa"] += g
            detalle.append({"nombre": a.get("nombre"), "cantidad_g": a.get("cantidad_g"),
                            "macros": {"proteina": round(p, 1), "hidratos": round(h, 1), "grasa": round(g, 1)}})

    return {
        "macros": {k: int(round(v)) for k, v in total.items()},
        "alimentos": detalle,
        "no_reconocidos": [],
        "origen": "menu",
        "fecha": fecha,
    }


async def leer_de_foto(imagen_b64: str, user_id: str) -> Dict:
    """
    Foto de la dieta que le dieron (un papel, una captura, una hoja de Excel).

    Se lee la imagen con el modelo y se pasa a texto; a partir de ahi es el mismo camino que la
    dieta escrita, para que las reglas de conteo sean exactamente las mismas por las tres puertas.
    """
    from openai import AsyncOpenAI

    imagen_b64 = (imagen_b64 or "").split(",")[-1]  # admite data:image/...;base64,XXXX
    try:
        base64.b64decode(imagen_b64, validate=True)
    except Exception:
        return {"error": "La imagen no se ha podido leer", "origen": "foto"}

    cliente = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    modelo = os.environ.get("OPENAI_MODEL_VISION", os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"))
    try:
        resp = await cliente.chat.completions.create(
            model=modelo,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text":
                        "Es la foto de una dieta. Transcribe SOLO los alimentos con sus cantidades, "
                        "uno por linea, en formato '<cantidad> <unidad> de <alimento>'. Si la foto no "
                        "contiene una dieta, responde exactamente: SIN DIETA."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{imagen_b64}"}},
                ],
            }],
            max_tokens=800,
        )
        transcrito = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        return {"error": f"No hemos podido leer la foto: {e}", "origen": "foto"}

    if not transcrito or "SIN DIETA" in transcrito.upper():
        return {"error": "En esa foto no vemos una dieta. Prueba a escribirla.", "origen": "foto"}

    resultado = await leer_de_texto(transcrito, user_id)
    resultado["origen"] = "foto"
    resultado["transcrito"] = transcrito
    return resultado


async def dias_disponibles(user_id: str, limite: int = 10) -> List[Dict]:
    """Los ultimos dias que tiene montados en la calculadora, para que elija uno."""
    dietas = await db.diets.find(
        {"user_id": user_id}, {"_id": 0, "fecha": 1, "comidas": 1}
    ).sort("fecha", -1).to_list(limite)

    salida = []
    for d in dietas:
        n = sum(len((c or {}).get("alimentos") or []) for c in (d.get("comidas") or {}).values())
        if n:
            salida.append({"fecha": d.get("fecha"), "alimentos": n})
    return salida
