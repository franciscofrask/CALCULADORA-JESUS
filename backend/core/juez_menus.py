# -*- coding: utf-8 -*-
"""La puerta de coherencia de los menus reales: quien la pasa se puede ofrecer.

Francisco, 14-08-2026: las opciones tienen que salir de las comidas que la gente come de
verdad -- su historial y la biblioteca --, PERO «un usuario puede armar un dia sin sentido
porque hizo una prueba, y esos menus no pueden pasar». Esta es esa puerta.

DOS CAPAS, Y EL ORDEN IMPORTA
-----------------------------
1. **La mecanica, que es gratis.** Un menu que han montado DOS O MAS personas distintas no
   es una prueba: dos desconocidos no hacen el mismo experimento. Y en el historial propio,
   lo comido en DOS FECHAS distintas tampoco: los dias de prueba no se repiten. Todo eso
   pasa solo, sin gastar una llamada.

2. **La IA, solo para el resto.** Lo que una sola persona monto una sola vez puede ser una
   comida perfectamente normal o el dia que probo a meterlo todo junto. Eso lo decide el
   modelo del chat con una pregunta simple, y el veredicto SE GUARDA (`db.menu_juicios`):
   cada combinacion se juzga UNA vez en la vida, no en cada peticion.

SI LA IA NO CONTESTA, EL MENU NO PASA. Es a proposito: mejor una opcion menos que una
tonteria delante del cliente, y el compositor de siempre sigue detras como respaldo.
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)

# Cuantos juicios nuevos puede gastar UNA peticion de menus. Cada juicio es una llamada al
# modelo (~1 s); cuatro cubren de sobra una tanda de opciones y el resto de candidatos
# esperan a la siguiente peticion, donde el cache ya trae los veredictos anteriores.
JUICIOS_POR_PETICION = 4


def firma_de(momento: str, ids: List[int]) -> str:
    """La identidad de una combinacion: el momento y QUE lleva, no cuanto.

    Las cantidades quedan fuera a proposito: la coherencia es de la combinacion (pollo con
    arroz si, crema de cacao con paella no) y los gramos se recalculan siempre al ofrecer.
    """
    return f"{(momento or '').strip().lower()}|{'-'.join(str(i) for i in sorted(set(int(x) for x in ids)))}"


def pasa_sin_juicio(clientes_distintos: int = 0, fechas_distintas: int = 0) -> bool:
    """La capa mecanica: lo repetido no es una prueba."""
    return int(clientes_distintos or 0) >= 2 or int(fechas_distintas or 0) >= 2


async def veredicto_cacheado(db, firma: str) -> Optional[bool]:
    doc = await db.menu_juicios.find_one({"firma": firma}, {"_id": 0, "vale": 1})
    return None if doc is None else bool(doc.get("vale"))


async def juzgar(db, momento: str, nombres_y_gramos: List[str], firma: str) -> bool:
    """Le pregunta al modelo si esto es una comida de verdad y guarda el veredicto.

    El prompt no lleva nombres de comida propios (los alimentos van como DATO, que es la
    misma linea que separa el prompt del agente de sus herramientas): se le pide el
    criterio de un nutricionista, no una lista de reglas.
    """
    try:
        from openai import AsyncOpenAI
        cliente = AsyncOpenAI()
        modelo = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
        respuesta = await cliente.chat.completions.create(
            model=modelo,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": (
                    "Eres el nutricionista de un metodo de comidas por macros, en espanol de "
                    "Espana. Te enseno una combinacion que un cliente monto una vez y tu "
                    "decides si es una comida que una persona serviria de verdad en ese "
                    "momento del dia, o si es un dia de prueba / un cuadre de numeros sin "
                    "sentido (postres industriales de relleno en una comida salada, tres "
                    "veces el mismo tipo de alimento, combinaciones que nadie se sirve "
                    "juntas). Las cantidades son orientativas: juzga la COMBINACION. "
                    "Responde SOLO un JSON: {\"vale\": true|false, \"motivo\": \"...\"}."
                )},
                {"role": "user", "content": (
                    f"Momento del dia: {momento}.\n"
                    "La comida:\n- " + "\n- ".join(nombres_y_gramos)
                )},
            ],
            timeout=12,
        )
        out = json.loads(respuesta.choices[0].message.content or "{}")
        vale = bool(out.get("vale"))
        # Upsert, no insert: dos peticiones a la vez pueden juzgar la misma firma, y el
        # segundo guardado no puede convertir un veredicto bueno en un fallo.
        await db.menu_juicios.update_one(
            {"firma": firma},
            {"$set": {"vale": vale,
                      "motivo": str(out.get("motivo") or "")[:300],
                      "momento": momento, "menu": nombres_y_gramos[:12],
                      "modelo": modelo,
                      "juzgado_en": datetime.now(timezone.utc).isoformat()}},
            upsert=True)
        return vale
    except Exception as e:                                    # noqa: BLE001
        # Sin veredicto no se ofrece, y NO se cachea el fallo: a la proxima se reintenta.
        logger.warning("juez de menus sin respuesta: %s", e)
        return False
