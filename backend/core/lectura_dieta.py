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
        encontrados = await bot.search_foods(nombre, limit=6)
        if not encontrados:
            no_reconocidos.append(nombre)
            continue

        # Quien describe su dieta dice "pollo" o "ternera", no una marca concreta: se prefiere el
        # alimento generico (el que no tiene URL de ficha). Sin esto, "ternera" acababa en un plato
        # preparado de marca y "proteina en polvo" en cacahuete en polvo.
        alimento = dict(next((a for a in encontrados if not a.get("url")), encontrados[0]))

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
