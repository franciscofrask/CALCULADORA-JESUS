"""Puerta contra la fuerza bruta en los endpoints públicos de autenticación.

El contador vive en Mongo (colección `intentos_auth`), NO en memoria del proceso: desde
que el backend corre con dos pods, un contador por proceso dejaría pasar el doble (cada
pod contaría su mitad). En Mongo los dos pods comparten la cuenta.

Cada intento que cuenta deja una marca con su momento; la puerta cuenta las marcas
recientes de una clave y corta con 429 si pasan del límite. Las marcas caducan solas por
un índice TTL (ver `core/database.py`), así que la colección no crece.

Se usan cubos separados por CUENTA y por IP: el de cuenta frena que ataquen un correo
concreto desde muchos sitios; el de IP frena que una misma máquina barra muchos correos.
"""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request

from .database import db

COLECCION = "intentos_auth"


def ip_de(request: Request) -> str:
    """La IP real del cliente, contando con que detrás está Traefik.

    El proxy reenvía la IP original en `X-Forwarded-For` (el primero de la lista);
    `request.client.host` sería la del propio proxy, la misma para todo el mundo, y
    entonces el cubo por IP no distinguiría a nadie. Sin proxy (en local) se usa la
    directa.
    """
    reenviada = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if reenviada:
        return reenviada
    return (request.client.host if request.client else "?") or "?"


async def comprobar(clave: str, limite: int, ventana_seg: int) -> None:
    """Deja pasar, o corta con 429 si esa clave acumula demasiados intentos recientes.

    Solo MIRA; no apunta nada. La marca se pone aparte (`apuntar`), después de saber que
    el intento fue fallido, para no penalizar a quien acierta a la primera.
    """
    desde = datetime.now(timezone.utc) - timedelta(seconds=ventana_seg)
    cuantos = await db[COLECCION].count_documents({"clave": clave, "cuando": {"$gte": desde}})
    if cuantos >= limite:
        raise HTTPException(
            status_code=429,
            detail="Demasiados intentos. Espera unos minutos y vuelve a probar.",
            headers={"Retry-After": str(ventana_seg)},
        )


async def apuntar(*claves: str) -> None:
    """Deja una marca (con la hora) en cada clave dada. `cuando` es un Date real para que
    el índice TTL pueda borrarlo."""
    ahora = datetime.now(timezone.utc)
    docs = [{"clave": c, "cuando": ahora} for c in claves if c]
    if docs:
        await db[COLECCION].insert_many(docs)
