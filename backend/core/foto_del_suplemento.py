# -*- coding: utf-8 -*-
"""LA FOTO DEL SUPLEMENTO, RESUELTA AL SERVIR.

«Los suplementos. Yo me metí aquí y estuve probando todos y todos te llevan a la web de
Fullgas. Falta la foto. Falta la foto, Francisco. La foto no está.» (Jesús, minuto 28:22
del vídeo del 3-09.)

Medido: **5.435 de los 5.445 suplementos pautados salían sin foto.** No es que la pantalla
no sepa pintarla -- `SupplementsPage` ya pinta `item.imagen` y cae al icono de pastilla si
no hay --: es que la línea del protocolo la lleva vacía.

POR QUÉ. Al pautar, `_catalog_to_protocol_item` congela una COPIA de la ficha dentro del
protocolo, `imagen` incluida. Los 100 protocolos se guardaron antes de que se importaran las
fotos, así que la copia nació con `None` y ahí se quedó para siempre: una foto que se sube
hoy al catálogo no llega nunca a lo que ya está pautado.

Y hay una segunda capa: los `catalog_id` de los protocolos casi no existen ya en el
catálogo. De los 85 distintos que usan, 6 están en `supplement_catalog` y 9 en
`guia_suplementos`. Los nombres, en cambio, sí casan: «whey-isolate-crema-de-arroz» es
«Whey Isolate + crema de arroz». Por eso aquí se busca por id, por slug Y por nombre
normalizado, contra las tres colecciones que guardan fichas de suplemento.

Con eso se recuperan **3.669 de 5.445**. Los que se quedan sin foto es porque no existe en
ninguna parte, y son nueve: Omega 3 (hombre y mujer), Hydropeptides o MAP (tres dosis),
Ursobilane (tres) y PRO-H. Esos hay que subirlos, no hay de dónde sacarlos.

Se resuelve AL SERVIR y no se guarda, por lo mismo que el nombre y la comida (ver
`routes/supplements.get_current_protocol`): sale de datos que el coach puede cambiar mañana,
y una copia guardada se volvería a quedar vieja sin que nadie lo vea. Que es exactamente lo
que pasó.
"""
import re
import unicodedata
from typing import Any, Dict, Optional

#: Las tres colecciones con fichas de suplemento. Son pequeñas (200 + 28 + 106) y se leen
#: enteras: cualquier consulta más fina obligaría a normalizar nombres dentro de Mongo.
COLECCIONES = ("supplement_catalog", "guia_suplementos", "supplements")


def clave(texto: Optional[str]) -> str:
    """«Whey Isolate + crema de arroz» y «whey-isolate-crema-de-arroz» dan lo mismo."""
    limpio = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", limpio.lower()).strip()


async def fotos_conocidas(db) -> Dict[str, str]:
    """Todas las fotos que la casa tiene, indexadas por id, por slug y por nombre."""
    fotos: Dict[str, str] = {}
    for coleccion in COLECCIONES:
        async for ficha in db[coleccion].find({}, {"_id": 0}):
            imagen = ficha.get("imagen")
            # SOLO DIRECCIONES DE VERDAD. En el catálogo del coach hay 14 fichas con cosas
            # como `tarro.webp` o `Nueva-presentacion-de-Ursobilane_01.jpg`: rutas relativas
            # a un sitio que no es el nuestro, o sea una imagen rota en la pantalla del
            # cliente. Una foto que no carga es peor que el icono de pastilla.
            if not imagen or not str(imagen).startswith("http"):
                continue
            for k in (ficha.get("id"), ficha.get("slug"),
                      clave(ficha.get("id")), clave(ficha.get("nombre"))):
                if k:
                    fotos.setdefault(k, imagen)
    return fotos


def foto_de(item: Dict[str, Any], fotos: Dict[str, str]) -> Optional[str]:
    """La foto de esta línea del protocolo, o `None` si no la tiene nadie."""
    if item.get("imagen") and str(item["imagen"]).startswith("http"):
        return item["imagen"]           # la congelada vale si es una dirección de verdad
    for k in (item.get("catalog_id"), clave(item.get("catalog_id")), clave(item.get("titulo"))):
        if k and fotos.get(k):
            return fotos[k]
    return None


async def ponerles_la_foto(db, resuelto: Dict[str, Any]) -> None:
    """Rellena `imagen` en las líneas del protocolo, in place."""
    lineas = [it for clave_ in ("actual", "siguiente") for it in (resuelto.get(clave_) or [])]
    if not lineas:
        return
    fotos = await fotos_conocidas(db)
    for it in lineas:
        it["imagen"] = foto_de(it, fotos)
