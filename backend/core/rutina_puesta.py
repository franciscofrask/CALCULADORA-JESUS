# -*- coding: utf-8 -*-
"""UNA SOLA RESPUESTA A «¿ESTE CLIENTE TIENE RUTINA?».

Puntos 80 y 103 del artefacto «La app, pantalla por pantalla» (4-09), y Gonzalo lo volvió a
ver en producción ese mismo día: «Montalvo tiene rutina-152.pdf entregada y el cliente la ve
y la abre. La ficha, en Resumen, dice Sin rutina. Y ese contador alimenta el 131 sin rutina
del panel» ... «Es el mismo arreglo a medias: se corrigió el conteo en Rutinas y el Inicio
sigue con el suyo».

Hasta hoy la pregunta se contestaba en tres sitios con tres copias del criterio:

  - la pantalla de Rutinas: estructurada activa O PDF entregado (desde el 24-08), y «la
    lleva en su plan» mirando `habilitaciones.rutina` del catálogo, sin contar «opcional»;
  - el Inicio del panel: la misma suma desde el 28-08, pero «la lleva en su plan» mirando
    las `features` del plan en código, que sí cuenta la «opcional» de Bronze y de
    Mantenimiento. Medido en dev el 4-09: 173 «sin rutina» en el Inicio contra 154 en
    Rutinas, y los 43 de diferencia eran justo Bronze (29) y Mantenimiento (13);
  - la ficha: solo `db.routines`, así que al que tiene su PDF le decía «Sin rutina».

Aquí vive la respuesta y de aquí la leen las tres pantallas. Quien necesite saber si un
cliente tiene rutina, o a quién le falta, llama aquí y no vuelve a escribir el `find`.

El PDF cuenta como rutina porque ES la vía de entrega real («se siguen generando como hasta
ahora», bloque 11 del doc del 19-08). La estructurada manda cuando hay las dos: es la que se
abre por dentro (días y ejercicios) y la que fija la semana del reporte.
"""
from typing import Any, Dict, Iterable, List, Optional

from core.database import db

# «Opcional» NO es «incluida» (24-08): es justo lo contrario, no se la lleva, se la puede
# comprar. Es el mismo criterio de `core.rutina_del_mes.su_plan_ya_la_lleva` y de la
# pantalla de Rutinas.
MODOS_QUE_NO_LA_LLEVAN = ("ninguna", "opcional")


async def pdf_por_cliente(client_ids: Optional[Iterable[str]] = None) -> Dict[str, str]:
    """{client_id: fecha del último PDF de rutina que se le subió}.

    Agrupa EN LA BASE y con el `$project` delante del `$group` a propósito: en `rutina_pdfs`
    cada fila lleva el PDF entero dentro (hasta 15 MB), y sin la proyección la tubería
    arrastra el binario de cada uno para acabar quedándose con dos campos. Con `client_ids`
    se filtra primero: la ficha pregunta por uno solo y no tiene que recorrer los de todos.
    El índice `(client_id, uploaded_at)` lo crea `core.database.create_indexes`.
    """
    tuberia: List[Dict[str, Any]] = []
    if client_ids is not None:
        tuberia.append({"$match": {"client_id": {"$in": list(client_ids)}}})
    tuberia += [
        {"$project": {"client_id": 1, "uploaded_at": 1}},
        {"$group": {"_id": "$client_id", "ultimo": {"$max": "$uploaded_at"}}},
    ]
    fuera: Dict[str, str] = {}
    async for fila in db.rutina_pdfs.aggregate(tuberia):
        if fila.get("_id"):
            fuera[fila["_id"]] = fila.get("ultimo") or ""
    return fuera


async def rutinas_puestas(client_ids: Optional[Iterable[str]] = None) -> Dict[str, Dict[str, Any]]:
    """Lo que tiene puesto cada cliente: {client_id: {"activa": rutina o None, "pdf": fecha o None}}.

    Solo salen los que tienen ALGO; el que no está en el dict no tiene rutina. De la
    estructurada viajan los días (para contar los de entreno) y su fecha (la semana de
    rutina decide qué reporte toca, doc del 19-08). Sin `client_ids` son todos: es lo que
    piden el Inicio y Rutinas, que los quieren de golpe y no de uno en uno.
    """
    filtro: Dict[str, Any] = {"status": "active"}
    if client_ids is not None:
        filtro["client_id"] = {"$in": list(client_ids)}
    activas = await db.routines.find(
        filtro, {"_id": 0, "client_id": 1, "days": 1, "created_at": 1}).to_list(3000)
    pdfs = await pdf_por_cliente(client_ids)

    fuera: Dict[str, Dict[str, Any]] = {}
    for r in activas:
        if r.get("client_id"):
            fuera[r["client_id"]] = {"activa": r, "pdf": None}
    for cid, fecha in pdfs.items():
        fuera.setdefault(cid, {"activa": None, "pdf": None})["pdf"] = fecha or ""
    return fuera


def estado_de(puesta: Optional[Dict[str, Any]]) -> str:
    """'activa', 'pdf' o 'ninguna'. La estructurada manda si hay las dos (ver arriba)."""
    if not puesta:
        return "ninguna"
    if puesta.get("activa"):
        return "activa"
    if puesta.get("pdf") is not None:
        return "pdf"
    return "ninguna"


def tiene_rutina(puesta: Optional[Dict[str, Any]]) -> bool:
    return estado_de(puesta) != "ninguna"


async def rutina_puesta_de(client_id: str) -> Dict[str, Any]:
    """La respuesta para UN cliente, tal cual la pinta la ficha: `estado` ('activa' / 'pdf' /
    'ninguna'), `tiene`, `en_pdf` y la fecha del PDF si lo hay."""
    puesta = (await rutinas_puestas([client_id])).get(client_id)
    pdf = (puesta or {}).get("pdf")
    return {
        "estado": estado_de(puesta),
        "tiene": tiene_rutina(puesta),
        "en_pdf": pdf is not None,
        "pdf_uploaded_at": pdf or None,
    }


def modo_de_rutina(plan: Optional[str], catalogo: Dict[str, Any]) -> str:
    """Lo que dice el catálogo de este plan: 'personalizada', 'del_mes', 'opcional' o 'ninguna'."""
    from models.user import codigo_de_plan
    ficha = catalogo.get(codigo_de_plan(plan)) or {}
    return (ficha.get("habilitaciones") or {}).get("rutina") or "ninguna"


def la_lleva_en_su_plan(plan: Optional[str], catalogo: Dict[str, Any]) -> bool:
    """¿El plan le incluye la rutina? Entonces no tenerla puesta es trabajo pendiente.

    Es el criterio de la pantalla de Rutinas (y de `core.rutina_del_mes`): el modo del
    catálogo, y «ninguna» y «opcional» NO la llevan. El Inicio del panel miraba las
    `features` del plan y por eso contaba 43 tareas que no existían (ver la cabecera).
    """
    return modo_de_rutina(plan, catalogo) not in MODOS_QUE_NO_LA_LLEVAN


async def clientes_y_su_rutina(catalogo: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Cada cliente de alta con lo que tiene puesto. LA MISMA LISTA para Rutinas y para el
    Inicio: así los dos números salen de las mismas personas y del mismo criterio, y no
    pueden volver a decir cosas distintas en la misma sesión (punto 103).

    Quién entra: los perfiles que no están de baja (a quien se fue no se le pone rutina,
    punto 36 del 30-08), sin el equipo ni las cuentas de prueba (`_fuera_el_equipo`) y sin
    usuarios borrados. Del perfil viajan solo los campos que `has_active_access` necesita
    para el «solo al corriente de pago» del Inicio; los perfiles enteros, con la serie de
    pesos y lo importado de Calma dentro, tardaban siete segundos en esta misma pantalla.
    """
    from routes.admin import _fuera_el_equipo

    solo_clientes = await _fuera_el_equipo()
    perfiles = await db.client_profiles.find(
        {**solo_clientes, "status": {"$ne": "baja"}},
        {"_id": 0, "id": 1, "user_id": 1, "plan": 1, "status": 1, "access_until": 1,
         "stripe_subscription_id": 1, "subscription_status": 1, "current_period_end": 1},
    ).to_list(3000)
    uids = [p["user_id"] for p in perfiles if p.get("user_id")]
    usuarios = await db.users.find(
        {"id": {"$in": uids}, "deleted_at": None}, {"_id": 0, "id": 1, "name": 1, "email": 1}
    ).to_list(len(uids) or 1)
    umap = {u["id"]: u for u in usuarios}
    puestas = await rutinas_puestas()

    fuera: List[Dict[str, Any]] = []
    for p in perfiles:
        u = umap.get(p.get("user_id"))
        if not u:
            continue
        puesta = puestas.get(p["id"])
        r = (puesta or {}).get("activa")
        pdf = (puesta or {}).get("pdf")
        fuera.append({
            "client_id": p["id"],
            "name": u.get("name"),
            "email": u.get("email"),
            "plan": p.get("plan"),
            "has_routine": tiene_rutina(puesta),
            # Cuál de las dos tiene: la estructurada se puede abrir por dentro (días y
            # ejercicios) y el PDF no, así que la pantalla no puede tratarlos igual.
            "tiene_pdf": pdf is not None,
            "pdf_uploaded_at": pdf or None,
            "training_days": len([d for d in r.get("days", []) if not d.get("is_rest")]) if r else 0,
            "routine_created_at": r.get("created_at") if r else None,
            "la_lleva_en_su_plan": la_lleva_en_su_plan(p.get("plan"), catalogo),
            "perfil": p,
        })
    return fuera


def a_quien_le_falta(clientes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """De la lista de arriba, los que la llevan en el plan y no la tienen puesta: la tarea."""
    return [c for c in clientes if c["la_lleva_en_su_plan"] and not c["has_routine"]]
