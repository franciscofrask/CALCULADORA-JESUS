"""
Rutas de Suplementación.

Espejo del patrón de rutinas:
- Cliente lee su protocolo (GET /supplements/current).
- Admin/entrenador gestiona el catálogo (CRUD) y asigna el protocolo por cliente.
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import List, Optional

from core.database import db
from core.security import (
    get_current_user, get_admin_user, solo_admin_borra_catalogo, assert_client_access,
)
from core.plan_access import require_access
from core.tiempo import hoy_madrid
from models.supplements import (
    SupplementCatalogItem, SupplementProtocolSave, SupplementProtocolResponse,
    ProtocolItem, VersionProtocolo,
)


# ── El protocolo, versionado por fecha (punto 33 del 07-08) ──────────────
# Antes habia UN protocolo por cliente que se pisaba a si mismo: se podia asignar pero no
# quedaba registro de que tomaba en cada momento, y lo de "siguiente + siguiente_fecha" era
# un apano para poder dejar uno preparado. Ahora es una lista de versiones con fecha y se
# resuelve por la mas reciente que no pase de hoy, exactamente igual que los macros.

def _hoy() -> str:
    """El día del CLIENTE, en hora de España (doc 16-08, regla 1). Con la fecha UTC, un
    protocolo con fecha de mañana entraba en vigor a las 23:00 de esta noche: el cliente
    veía lo nuevo antes de tiempo y lo de hoy desaparecía sin que nadie tocara nada."""
    return hoy_madrid().isoformat()


def _ordenadas(versiones) -> list:
    return sorted([v for v in (versiones or []) if v.get("fecha")], key=lambda v: str(v["fecha"])[:10])


def vigente_en(versiones, fecha: Optional[str] = None) -> Optional[dict]:
    """La version que aplica en `fecha`: la mas reciente que no la pase."""
    dia = (fecha or _hoy())[:10]
    previas = [v for v in _ordenadas(versiones) if str(v["fecha"])[:10] <= dia]
    return previas[-1] if previas else None


def proxima_desde(versiones, fecha: Optional[str] = None) -> Optional[dict]:
    """La siguiente version que entrara en vigor despues de `fecha`, si la hay."""
    dia = (fecha or _hoy())[:10]
    futuras = [v for v in _ordenadas(versiones) if str(v["fecha"])[:10] > dia]
    return futuras[0] if futuras else None


def _respuesta(doc: dict) -> dict:
    """El documento como lo espera quien lo consume: `actual` y `siguiente` RESUELTOS por
    fecha, mas el historico entero por si se quiere mirar."""
    versiones = _ordenadas(doc.get("versiones"))
    hoy = vigente_en(versiones)
    prox = proxima_desde(versiones)
    return {
        "client_id": doc.get("client_id"),
        "actual": (hoy or {}).get("items") or [],
        "actual_fecha": (hoy or {}).get("fecha"),
        "siguiente": (prox or {}).get("items") or [],
        "siguiente_fecha": (prox or {}).get("fecha"),
        "nota": (hoy or {}).get("nota"),
        "versiones": versiones,
        "updated_at": doc.get("updated_at"),
    }

# ── La suplementación general ────────────────────────────────────────────
# La que se le enseña a quien todavía no tiene la suya escrita. No es una lista aparte que
# haya que mantener: es el mismo arranque que el panel le propone al coach (`/suggest`),
# la base y el intra del catálogo con la variante que le toca por sexo. Así lo que ve el
# cliente y lo que el coach va a partir de ahí son la misma cosa.
#
# El quemador NO entra: eso es una decisión de coach para una persona concreta, no algo que
# se le pone delante a alguien porque su objetivo diga "definición".

def _sexo_de(profile: dict) -> str:
    """"hombre" o "mujer", tolerante con los nombres de campo que conviven en la base."""
    crudo = str(profile.get("sexo") or profile.get("sex") or profile.get("genero") or "").lower()
    es_mujer = "muj" in crudo or "fem" in crudo or crudo in ("f", "female")
    return "mujer" if es_mujer else "hombre"


# `protocolo_generico` vivió aquí del 18-08 al 20-08: componía base + intra por sexo para
# quien no tenía la suya. El doc del 19-08 lo retiró («No es eso. Es mi guía entera»): ese
# hueco lo cubre ahora GET /supplements/guia.


# ==================== CLIENTE ====================
router = APIRouter(prefix="/supplements", tags=["supplements"])


@router.get("/current", response_model=Optional[SupplementProtocolResponse])
async def get_current_protocol(ctx=Depends(require_access("suplementacion"))):
    """Protocolo de suplementación del cliente (requiere plan con suplementación y suscripción activa).

    SIN PROTOCOLO PROPIO SE DEVUELVE LA GENERAL (Jesús, 18-08). Antes esto devolvía `None`
    y la pantalla contestaba "de momento no te hemos puesto nada", que es dejar sin nada al
    94 de cada 193 clientes que todavía no tienen el suyo escrito. Lo que él quiere es lo
    contrario: que siempre haya algo que tomar delante, la general, hasta que le pongamos
    la suya. Va marcada con `es_generica` para que nadie la confunda con una pauta personal.
    """
    profile = ctx["profile"]

    protocol = await db.supplement_protocols.find_one(
        {"client_id": profile["id"]}, {"_id": 0}
    )
    # Resuelto por fecha: el cliente ve el que le toca HOY, no el ultimo que se guardo. Un
    # protocolo dejado preparado para dentro de dos semanas no se le ensena todavia.
    resuelto = _respuesta(protocol) if protocol else {
        "client_id": profile["id"], "actual": [], "siguiente": [], "versiones": [],
    }

    # Las dos cosas que se resuelven AL SERVIR y no se guardan: con qué comida sale cada uno
    # (punto 174) y con qué nombre lo ve el cliente (el vídeo del 27-08). Ninguna se escribe en
    # la base porque las dos salen de datos que el coach puede cambiar mañana, y una copia
    # guardada se quedaría vieja sin que nadie lo vea.
    await _colocar_en_las_comidas(resuelto)
    _con_el_nombre_del_cliente(resuelto)

    # SIN PROTOCOLO PROPIO YA NO SE COMPONE NADA (doc 19-08, bloque 08). La general de
    # cinco líneas -- base + intra por sexo -- era el apaño del 18-08, y la respuesta de
    # Jesús fue clara: «No es eso. Es mi guía entera». Quien no tiene la suya ve LA GUÍA
    # (GET /supplements/guia), que es otra pantalla, no una pauta que marcar en Inicio.
    return SupplementProtocolResponse(**resuelto)


async def _colocar_en_las_comidas(resuelto: dict) -> None:
    """Rellena `en_comidas` de cada línea del protocolo, in place.

    La ficha del catálogo es donde el coach lo elige una vez para todos, así que hay que
    traérsela: las líneas del protocolo son una copia del día en que se pautó y pueden ser
    de antes de que existiera el campo. Se piden TODAS de una vez -- un protocolo son cinco o
    seis suplementos, pero esto lo llama el Inicio en cada carga.
    """
    from core.comida_del_suplemento import comidas_del_suplemento

    lineas = [it for clave in ("actual", "siguiente") for it in (resuelto.get(clave) or [])]
    if not lineas:
        return
    ids = {it.get("catalog_id") for it in lineas if it.get("catalog_id")}
    fichas = {}
    if ids:
        async for f in db.supplement_catalog.find({"id": {"$in": list(ids)}}, {"_id": 0}):
            fichas[f.get("id")] = f
    for it in lineas:
        it["en_comidas"] = comidas_del_suplemento(it, fichas.get(it.get("catalog_id")))


def _con_el_nombre_del_cliente(resuelto: dict) -> None:
    """Deja en `titulo` el nombre que tiene que ver el cliente, in place.

    «Él solamente ve Aceite de krill. No tiene que ver Aceite de krill, tres perlas» (Jesús,
    vídeo del 27-08). Lo que hay guardado es SU chuleta -- «Omega 3 hombre», «Fat burner
    hardcore mes 3» -- y le sirve para saber qué versión le puso a quién, así que en el panel
    se queda: eso lo lee `/admin/clients/{id}`, no esto.

    Aquí, y solo aquí, se corta. Son 328 de las 528 líneas vivas y las ven 97 de los 100
    clientes con protocolo. Qué se corta y por qué: core/nombre_del_suplemento.
    """
    from core.nombre_del_suplemento import nombre_para_el_cliente

    for clave in ("actual", "siguiente"):
        for it in (resuelto.get(clave) or []):
            it["titulo"] = nombre_para_el_cliente(it.get("titulo"))


@router.get("/guia")
async def guia_de_suplementacion(user=Depends(get_current_user)):
    """La guía de suplementación de Jesús, entera (doc 19-08, bloque 08).

    La ven TODOS los planes. Lo que cambia por plan es el remate:
      - plan personalizado o ajuste de 87 € cobrado, SIN protocolo propio todavía →
        el aviso de arriba («Esto es solo la guía básica...»), desde que se apunta
        hasta que recibe su plan.
      - los demás → sin promesa, y al final la oferta de la revisión de los 87 €.
        El botón va al mismo checkout que la oferta del final del alta.
    """
    from core.guia_suplementacion import (SECCIONES, DESCUENTO, partir_ficha,
                                          TEXTO_DE_LA_GUIA)
    from core.plan_access import tiene_entrenador_detras

    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0}) or {}

    # LA FUENTE BUENA es db.guia_suplementos: las fichas de la web tal cual, con sus
    # secciones (importadas el 20-08 con la sesión de Francisco). db.supplements son los
    # BLOQUES DE PROTOCOLO del coach (mes 1, mes 2, dosis...): sirven para pautar, no
    # para leerse como guía; se usan solo de repuesto si la buena está vacía.
    fichas_web = await db.guia_suplementos.find({}, {"_id": 0}).sort("orden", 1).to_list(200)
    por_seccion = {s["clave"]: [] for s in SECCIONES}
    sin_seccion = []
    if fichas_web:
        for f in fichas_web:
            ficha = {
                "id": f.get("id"), "nombre": f.get("nombre"),
                "que_es": f.get("que_es"), "cuando": f.get("cuando"), "cuanto": f.get("cuanto"),
                "notas": None,
                "enlaces": f.get("enlaces") or [],
                "imagen": f.get("imagen"),
                "subfiltros": f.get("subfiltros") or [],
            }
            secciones_de_f = [c for c in (f.get("secciones") or []) if c in por_seccion]
            if secciones_de_f:
                for c in secciones_de_f:
                    por_seccion[c].append(ficha)
            else:
                sin_seccion.append(ficha)
    else:
        fichas = await db.supplements.find({"activo": {"$ne": False}}, {"_id": 0}).to_list(500)
        for f in sorted(fichas, key=lambda x: (x.get("orden") or 999, str(x.get("nombre") or ""))):
            ficha = {
                "id": f.get("id"), "nombre": f.get("nombre"),
                **partir_ficha(f.get("descripcion")),
                "notas": (f.get("notas") or "").strip() or None,
                "enlaces": f.get("enlaces") or [],
                "imagen": f.get("imagen"),
                "subfiltros": [f.get("subfiltro")] if f.get("subfiltro") else [],
            }
            destino = por_seccion.get(f.get("seccion"))
            (destino if destino is not None else sin_seccion).append(ficha)

    va_con_plan = (tiene_entrenador_detras(profile.get("plan"))
                   or bool((profile.get("ajuste_a_medida") or {}).get("cobrado")))
    protocolo = await db.supplement_protocols.find_one({"client_id": profile.get("id")}, {"_id": 0})
    con_protocolo = bool(protocolo and _respuesta(protocolo).get("actual"))

    return {
        "secciones": [{**s, "suplementos": por_seccion[s["clave"]]} for s in SECCIONES],
        "sin_seccion": sin_seccion,
        "descuento": DESCUENTO,
        # El texto de entrada, con las tres líneas del punto 182 y ninguna más. Ver
        # `TEXTO_DE_LA_GUIA`: el de la base sigue guardado pero ya no manda.
        "texto_entrada": TEXTO_DE_LA_GUIA,
        # LOS TRES ESTADOS DE LA PANTALLA (punto 179 del 27-08). Los dos datos ya se
        # calculaban aquí para decidir el remate; ahora viajan tal cual, porque de ellos sale
        # hasta el TÍTULO («Mis suplementos» o «Suplementación», punto 180) y no solo un
        # cartel al final. Sacarlo de si la petición del protocolo dio 200 o 403 funcionaba de
        # casualidad, y una pantalla entera no puede colgar de un código de error.
        "con_plan": va_con_plan,
        "con_protocolo": con_protocolo,
        "aviso_plan_personalizado": va_con_plan and not con_protocolo,
        "oferta_87": not va_con_plan,
    }


# ==================== ADMIN ====================
admin_router = APIRouter(prefix="/admin/supplements", tags=["admin-supplements"])


# Las marcas que la importación de la guía trajo EN EL PROPIO TÍTULO («... - NO USAR»,
# «Suplemento obsoleto»). El criterio vive en _sanear_catalogo_suplementos.es_basura, que
# es quien las apaga por datos; aquí se reutiliza para que el selector tampoco las ofrezca
# mientras los datos sigan sucios (P34, doc 23-08): en prod quedaron con activo=True y el
# coach podía pautárselas a un cliente.
from _sanear_catalogo_suplementos import es_basura


def _ofrecible(ficha: dict) -> bool:
    """Si la ficha se puede OFRECER al coach para añadirla a un protocolo. No decide
    nada sobre lo ya asignado: un protocolo que la lleve se sigue sirviendo tal cual,
    porque el protocolo guarda su propio snapshot del ítem."""
    return not es_basura(ficha.get("titulo"))


# ── Catálogo (CRUD) ──────────────────────────────────────────────────────
@admin_router.get("/catalog")
async def list_catalog(include_inactive: bool = False, user=Depends(get_admin_user)):
    """Lista el catálogo de suplementos.

    Sin parámetros es el SELECTOR: lo que el coach ve al añadir un suplemento a un
    protocolo. Ahí solo entran las fichas activas Y sin la marca «NO USAR»/«obsoleto» en
    el título: la limpieza de datos (`_sanear_catalogo_suplementos.py`) las apaga, pero
    el endpoint no se fía de que ya haya corrido, que en prod se colaron activas (P34,
    doc 23-08). Las fichas legítimas de la guía siguen siendo elegibles, que para eso se
    volcaron (bloque 08 del doc 19-08).

    Con `include_inactive=true` (la página del catálogo, que es donde se cura) se devuelve
    TODO, también la basura: para apagar o arreglar una ficha primero hay que poder verla.
    """
    q = {} if include_inactive else {"activo": True}
    items = await db.supplement_catalog.find(q, {"_id": 0}).sort("orden", 1).to_list(500)
    if not include_inactive:
        items = [i for i in items if _ofrecible(i)]
    return items


@admin_router.post("/catalog")
async def create_catalog_item(item: SupplementCatalogItem, user=Depends(get_admin_user)):
    """Crea un suplemento en el catálogo."""
    doc = item.model_dump()
    await db.supplement_catalog.insert_one(doc)
    return {"message": "Suplemento creado", "id": item.id}


@admin_router.put("/catalog/{item_id}")
async def update_catalog_item(item_id: str, item: SupplementCatalogItem, user=Depends(get_admin_user)):
    """Actualiza un suplemento del catálogo."""
    doc = item.model_dump()
    doc["id"] = item_id
    # El PUT acepta `activo`, así que sin este cerrojo era la puerta de atrás del DELETE:
    # un entrenador que no puede desactivar por el DELETE lo conseguía mandando el mismo
    # documento con activo=false (P61, doc 23-08). Editar sigue abierto; apagar, no.
    if user.get("role") != "admin" and doc.get("activo") is False:
        existente = await db.supplement_catalog.find_one({"id": item_id}, {"_id": 0, "activo": 1})
        if existente and existente.get("activo") is not False:
            raise HTTPException(status_code=403, detail="Esto solo puede borrarlo el administrador")
    res = await db.supplement_catalog.update_one({"id": item_id}, {"$set": doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Suplemento no encontrado")
    return {"message": "Suplemento actualizado", "id": item_id}


@admin_router.delete("/catalog/{item_id}")
async def delete_catalog_item(item_id: str, user=Depends(solo_admin_borra_catalogo)):
    """Borrado lógico (activo=false) de un suplemento del catálogo.

    Solo admin (P61, doc 23-08): es lógico pero destructivo igual -- el suplemento
    desaparece del selector de TODOS los coaches. Asignar y quitar suplementos a un
    cliente (save / version) sigue abierto al entrenador."""
    res = await db.supplement_catalog.update_one({"id": item_id}, {"$set": {"activo": False}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Suplemento no encontrado")
    return {"message": "Suplemento desactivado", "id": item_id}


# ── Asignación del protocolo por cliente ─────────────────────────────────
@admin_router.post("/save", response_model=SupplementProtocolResponse)
async def save_protocol(client_id: str, data: SupplementProtocolSave, user=Depends(get_admin_user)):
    """Asigna/actualiza el protocolo de un cliente (upsert por client_id)."""
    profile = await db.client_profiles.find_one({"id": client_id})
    assert_client_access(user, profile)

    previo = await db.supplement_protocols.find_one({"client_id": client_id}, {"_id": 0}) or {}
    versiones = _ordenadas(previo.get("versiones"))
    quien = user.get("name", user.get("email", "coach"))
    ahora = datetime.now(timezone.utc).isoformat()

    def _guardable(item) -> dict:
        """La línea tal y como se guarda, SIN `en_comidas`.

        `en_comidas` es un calculado: lo pone el servidor al servir el protocolo y viaja a la
        pantalla, así que vuelve en el guardado. Si se dejara escrito, la base tendría el sitio
        del suplemento en dos versiones -- la guardada y la que sale de la regla -- y el día
        que cambie la ficha o el «¿Cuándo?» una de las dos se quedaría vieja sin que nadie lo
        vea. Se guarda de dónde sale (`comida` y `cuando`) y no lo que sale.
        """
        d = item.model_dump()
        d.pop("en_comidas", None)
        return d

    def _poner(fecha: str, items, nota):
        """Deja `items` como el protocolo que aplica desde `fecha`, pisando lo que hubiera
        ese dia. Las demas fechas del historico no se tocan."""
        nonlocal versiones
        dia = str(fecha)[:10]
        versiones = [v for v in versiones if str(v["fecha"])[:10] != dia]
        if items:
            versiones.append({"fecha": dia, "items": items, "nota": nota,
                              "guardado_por": quien, "guardado_at": ahora})
        versiones = _ordenadas(versiones)

    # El bloque "actual": si el coach no dice desde cuando, se respeta la fecha de la version
    # vigente. Corregir una dosis NO tiene por que abrir una version nueva; abrir una version
    # nueva es una decision, y para eso esta la fecha.
    vig = vigente_en(versiones)
    fecha_actual = (data.actual_fecha or (vig or {}).get("fecha") or _hoy())[:10]
    _poner(fecha_actual, [_guardable(i) for i in data.actual], data.nota)

    # El bloque "siguiente" es simplemente una version con fecha futura.
    if data.siguiente_fecha:
        _poner(data.siguiente_fecha, [_guardable(i) for i in data.siguiente], data.nota)

    doc = {"client_id": client_id, "versiones": versiones, "updated_at": ahora}
    await db.supplement_protocols.update_one(
        {"client_id": client_id}, {"$set": doc}, upsert=True
    )

    # SOLO SE AVISA SI HAY ALGO QUE VER (T2 del doc del 16-08: "si le cambias la
    # suplementación, le llega el aviso y AQUÍ LO VE").
    #
    # Guardar sin ningún suplemento borra la versión vigente -- es la forma de quitarle la
    # suplementación -- y aun así salía el aviso "tu protocolo se ha actualizado". El
    # cliente entraba y se encontraba "Todavía no tienes suplementación", que es
    # exactamente la queja de la que sale esta tarea. Sin nada pautado no hay novedad que
    # anunciar.
    resuelto = _respuesta(doc)
    if resuelto["actual"] or resuelto["siguiente"]:
        from routes.notifications import avisar_suplementos
        await avisar_suplementos(profile["user_id"], nota=data.nota)

    return SupplementProtocolResponse(**resuelto)


@admin_router.delete("/version/{fecha}")
async def borrar_version(client_id: str, fecha: str, user=Depends(get_admin_user)):
    """Borra una version del historico (una fecha concreta). El resto se queda."""
    profile = await db.client_profiles.find_one({"id": client_id})
    assert_client_access(user, profile)
    doc = await db.supplement_protocols.find_one({"client_id": client_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Este cliente no tiene protocolo")
    dia = str(fecha)[:10]
    versiones = [v for v in _ordenadas(doc.get("versiones")) if str(v["fecha"])[:10] != dia]
    doc = {"client_id": client_id, "versiones": versiones,
           "updated_at": datetime.now(timezone.utc).isoformat()}
    await db.supplement_protocols.update_one({"client_id": client_id}, {"$set": doc})
    return SupplementProtocolResponse(**_respuesta(doc))


def _catalog_to_protocol_item(c: dict) -> dict:
    """Snapshot de un ítem del catálogo para meterlo en el protocolo."""
    return {
        "catalog_id": c.get("id"),
        "titulo": c.get("titulo", ""),
        "imagen": c.get("imagen"),
        "enlaces": c.get("enlaces", []),
        "cuando": c.get("cuando", ""),
        "cuanto": c.get("cuanto", ""),
        "observaciones": c.get("observaciones"),
    }


@admin_router.post("/suggest")
async def suggest_protocol(client_id: str, user=Depends(get_admin_user)):
    """Propone un protocolo inicial según el perfil (sexo y objetivo).

    NO GUARDA NADA, y es la regla definitiva (P33 del doc 23-08, confirmada por
    Francisco el 23-08): auto-sugerir solo PROPONE y el coach revisa y guarda. El 21-08
    esto borró el protocolo entero de Juan porque el front sustituía con la respuesta;
    si alguien vuelve a hacer que esta ruta escriba en supplement_protocols, está
    reabriendo ese fallo."""
    profile = await db.client_profiles.find_one({"id": client_id}, {"_id": 0})
    assert_client_access(user, profile)

    # Sexo y objetivo (tolerante a distintos nombres de campo)
    sexo = _sexo_de(profile)
    objetivo = str(profile.get("objetivo") or profile.get("goal") or "").lower()
    es_definicion = "defin" in objetivo or "cut" in objetivo or "perder" in objetivo

    catalog = await db.supplement_catalog.find({"activo": True}, {"_id": 0}).sort("orden", 1).to_list(500)
    # La propuesta OFRECE, igual que el selector: nada de «NO USAR»/«obsoleto» aunque
    # sigan activas en la base (P34, doc 23-08).
    catalog = [c for c in catalog if _ofrecible(c)]

    def sexo_ok(c):
        return c.get("sexo", "ambos") in (sexo, "ambos")

    actual = []
    # Stack base + intra, con la variante de sexo correcta
    for c in catalog:
        if c.get("categoria") in ("base", "intra") and sexo_ok(c):
            actual.append(_catalog_to_protocol_item(c))
    # Definición → añadir un quemador
    if es_definicion:
        quemador = next((c for c in catalog if c.get("categoria") == "quemador" and sexo_ok(c)), None)
        if quemador:
            actual.append(_catalog_to_protocol_item(quemador))

    # Dedup por catalog_id conservando orden
    seen = set()
    dedup = []
    for it in actual:
        k = it.get("catalog_id")
        if k in seen:
            continue
        seen.add(k)
        dedup.append(it)

    return {
        "actual": dedup,
        "siguiente": [],
        "siguiente_fecha": None,
        "nota": None,
        "_meta": {"sexo": sexo, "objetivo": objetivo, "es_definicion": es_definicion},
    }
