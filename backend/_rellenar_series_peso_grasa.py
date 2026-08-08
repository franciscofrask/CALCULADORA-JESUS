"""
Construye las series `pesos` y `porcentajes_grasos` de los clientes que ya existen
(punto 30 del doc del 07-08), a partir de todos los sitios donde hoy hay un peso suelto.

De donde sale cada punto, y en este orden de confianza (si dos caen el mismo dia, gana el
ultimo de la lista):

  1. calma_raw.pesos / calma_raw.porcentajes_grasos  - lo que vino de la calculadora vieja
  2. macro_history                                   - por `peso_fecha` si la trae (punto 27),
                                                       si no por `effective_date`
  3. check-ins                                       - weekly y monthly traen peso
  4. reports                                         - el peso que manda el cliente en su reporte
  5. client_profiles.weight                          - el campo suelto de hoy, sin fecha: se
                                                       apunta en el ultimo dia conocido SOLO
                                                       si no hay ningun otro punto

El paso 5 es el unico que inventa: un peso sin fecha no se puede colocar. Por eso va el
ultimo y solo cuando el cliente no tiene nada mas, para no perder el dato.

Al terminar, `weight` y `body_fat` quedan valiendo el ultimo de su serie, que es la regla
del punto 30.

  python _rellenar_series_peso_grasa.py             simula, no escribe
  python _rellenar_series_peso_grasa.py --escribir  escribe
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from core.database import db                                    # noqa: E402
from core.series_cliente import actual, PESO, GRASA             # noqa: E402


def _dia(v):
    return str(v)[:10] if v else None


def _num(v, minimo, maximo):
    try:
        n = round(float(v), 1)
    except (TypeError, ValueError):
        return None
    return n if minimo <= n <= maximo else None


def _meter(destino, cid, fecha, valor, origen, minimo, maximo):
    v = _num(valor, minimo, maximo)
    f = _dia(fecha)
    if cid and v is not None and f:
        destino.setdefault(cid, {})[f] = {"fecha": f, "valor": v, "origen": origen}


async def main(escribir: bool):
    perfiles = await db.client_profiles.find(
        {}, {"_id": 0, "id": 1, "user_id": 1, "weight": 1, "body_fat": 1}).to_list(5000)
    print(f"{len(perfiles)} clientes")
    por_user = {p["user_id"]: p["id"] for p in perfiles if p.get("user_id") and p.get("id")}

    pesos, grasas = {}, {}

    # 1) Calma
    async for c in db.calma_raw.find({}, {"_id": 0, "client_id": 1, "user_id": 1,
                                          "pesos": 1, "porcentajes_grasos": 1}):
        cid = c.get("client_id") or por_user.get(c.get("user_id"))
        for x in (c.get("pesos") or []):
            _meter(pesos, cid, x.get("fecha"), x.get("valor"), "calma", 25, 300)
        for x in (c.get("porcentajes_grasos") or []):
            _meter(grasas, cid, x.get("fecha"), x.get("valor"), "calma", 3, 60)

    # 2) Historial de macros
    async for h in db.macro_history.find({}, {"_id": 0, "client_id": 1, "peso": 1,
                                              "client_weight": 1, "body_fat": 1,
                                              "peso_fecha": 1, "effective_date": 1,
                                              "created_at": 1}):
        f = h.get("peso_fecha") or h.get("effective_date") or h.get("created_at")
        peso = h.get("peso") if h.get("peso") is not None else h.get("client_weight")
        _meter(pesos, h.get("client_id"), f, peso, "ajuste", 25, 300)
        _meter(grasas, h.get("client_id"), f, h.get("body_fat"), "ajuste", 3, 60)

    # 3) Check-ins
    async for k in db.checkins.find({}, {"_id": 0, "client_id": 1, "weight": 1,
                                         "body_fat_pct": 1, "created_at": 1, "type": 1}):
        f = k.get("created_at")
        _meter(pesos, k.get("client_id"), f, k.get("weight"), f"check-in {k.get('type') or ''}".strip(), 25, 300)
        _meter(grasas, k.get("client_id"), f, k.get("body_fat_pct"), f"check-in {k.get('type') or ''}".strip(), 3, 60)

    # 4) Reportes
    async for r in db.reports.find({}, {"_id": 0, "client_id": 1, "weight": 1, "created_at": 1}):
        _meter(pesos, r.get("client_id"), r.get("created_at"), r.get("weight"), "reporte", 25, 300)

    # 5) El campo suelto, solo si no hay nada mas
    hoy = None
    sin_fecha = 0
    for p in perfiles:
        cid = p.get("id")
        if cid and not pesos.get(cid) and p.get("weight") is not None:
            if hoy is None:
                from datetime import datetime, timezone
                hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            _meter(pesos, cid, hoy, p.get("weight"), "peso sin fecha del perfil", 25, 300)
            sin_fecha += 1
        if cid and not grasas.get(cid) and p.get("body_fat") is not None:
            if hoy is None:
                from datetime import datetime, timezone
                hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            _meter(grasas, cid, hoy, p.get("body_fat"), "% graso sin fecha del perfil", 3, 60)

    # Escribir
    tocados, cambian_peso, con_dos_grasas, muestra = 0, 0, 0, []
    for p in perfiles:
        cid = p.get("id")
        if not cid:
            continue
        sp = sorted((pesos.get(cid) or {}).values(), key=lambda x: x["fecha"])
        sg = sorted((grasas.get(cid) or {}).values(), key=lambda x: x["fecha"])
        if not sp and not sg:
            continue
        ap, ag = actual(sp), actual(sg)
        cambios = {}
        if sp:
            cambios[PESO[0]] = sp
            cambios[PESO[1]] = ap["valor"] if ap else None
        if sg:
            cambios[GRASA[0]] = sg
            cambios[GRASA[1]] = ag["valor"] if ag else None
        if escribir:
            await db.client_profiles.update_one({"id": cid}, {"$set": cambios})
        tocados += 1
        if ap and p.get("weight") is not None and abs(ap["valor"] - float(p["weight"])) >= 0.1:
            cambian_peso += 1
            if len(muestra) < 8:
                muestra.append(f"  {cid[:8]}  ficha decia {p['weight']} kg  ->  {ap['valor']} kg del {ap['fecha']}  ({len(sp)} pesajes)")
        if len(sg) >= 2:
            con_dos_grasas += 1

    print("\n".join(muestra) or "  (ningun peso cambia)")
    print(f"\n{tocados} clientes con serie")
    print(f"{cambian_peso} en los que el peso actual CAMBIA (el de la ficha no era el ultimo de verdad)")
    print(f"{con_dos_grasas} con % graso en dos o mas momentos (los que puede usar el modelo)")
    print(f"{sin_fecha} clientes cuyo unico peso no tenia fecha y se apunta hoy")
    print("ESCRITO" if escribir else "SIMULACION: nada escrito (pasa --escribir)")


if __name__ == "__main__":
    asyncio.run(main("--escribir" in sys.argv))
