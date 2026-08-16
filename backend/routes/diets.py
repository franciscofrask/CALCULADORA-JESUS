"""
Rutas de dietas: CRUD, calendario, copiar.
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone
from typing import Optional
import calendar
import uuid

from core.database import db
from core.security import get_current_user
from core import dieta_para_ver as _para_ver
from pdf_generator import generate_diet_pdf

router = APIRouter(prefix="/diets", tags=["diets"])

import re as _re
_FECHA_RE = _re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validar_fecha(fecha: str) -> str:
    """Exige YYYY-MM-DD real. Evita 500 (y posible inyección) por fechas basura."""
    if not isinstance(fecha, str) or not _FECHA_RE.match(fecha):
        raise HTTPException(status_code=400, detail="Fecha inválida. Usa el formato YYYY-MM-DD.")
    try:
        datetime.strptime(fecha, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha inválida. Usa el formato YYYY-MM-DD.")
    return fecha


def _as_dict(v):
    return v if isinstance(v, dict) else {}


async def upsert_diet_doc(user_id: str, data: dict, quien: Optional[dict] = None) -> dict:
    """
    Construye el documento de dieta de un día y lo upserta en db.diets sobre
    (user_id, fecha). Forma única compartida por save_diet y el volcado del chatbot
    para que ambos escriban exactamente el mismo shape.

    `quien` es el usuario de la petición, para dejar anotado QUIÉN guardó este día
    (punto 4.11): «si el entrenador le monta una dieta el martes y el cliente la cambia el
    miércoles, los dos tienen que poder verlo». Se anota siempre, lo haya hecho el cliente o
    su entrenador: si solo se marcara la intervención del entrenador, un día sin marca
    querría decir dos cosas -- lo hizo el cliente, o se guardó antes de que esto existiera --
    y no habría forma de distinguirlas.
    """
    from core.actuar_como import marca_de_quien_lo_hizo

    fecha = data.get("fecha")
    diet_doc = {
        "user_id": user_id,
        "fecha": fecha,
        **(marca_de_quien_lo_hizo(quien) if quien else {}),
        "tipo_dia": data.get("tipo_dia", "entrenamiento"),
        "num_comidas": data.get("num_comidas", 4),
        "momento_entreno": data.get("momento_entreno", 1),
        "opcion_peri": data.get("opcion_peri", "intra_post"),
        "comidas": data.get("comidas", {}),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "macros_snapshot": data.get("macros_snapshot", None),
        "distribution_targets": data.get("distribution_targets", None),
        "is_cuadrado": data.get("is_cuadrado", False),
        # Calma comidaConMacrosVolcadas: which meal absorbs the day's remaining macros
        # (the others are locked). null = no volcado.
        "comida_volcada": data.get("comida_volcada", None),
    }
    # QUÉ SESIÓN DEL CHAT ES LA DUEÑA DE ESTE DÍA. De este campo depende el candado de las
    # dos pestañas (fallo 18 de Jesús), y esta función lo estaba TIRANDO: monta el
    # documento con una forma fija y `sesion_chat` no estaba en la lista, así que el
    # volcado lo mandaba y aquí se perdía. El guardado escribía None y el candado, que
    # compara con el dueño, no se activaba nunca. Salió al comprobar el volcado a mano en
    # producción, mirando la pantalla y el dato (15-08).
    #
    # Solo se toca si quien escribe lo dice: un guardado desde Nutrición no tiene sesión de
    # chat y no debe borrar la que hubiera.
    if data.get("sesion_chat"):
        diet_doc["sesion_chat"] = data["sesion_chat"]

    # UNA COMIDA QUE NO VIENE EN LA CARGA NO SE BORRA (16-08-2026).
    #
    # Este `$set` reemplazaba `comidas` entero por lo que trajera quien guardase, así que el
    # último en escribir se llevaba por delante lo que él no tuviera delante. Medido en
    # producción con la cuenta de Jesús: pedirle al chat «para mañana ponme 3 comidas» dejó
    # la Comida 4 -- ya montada, con cinco alimentos -- FUERA del reparto, y en el siguiente
    # guardado la clave `C4` desapareció del documento. El día pasó de 138 g de proteína a
    # 99 y volver a poner cuatro comidas devolvía el hueco vacío. Hubo que sacarla del backup
    # de las 04:30, porque no hay historial ni papelera.
    #
    # El mismo agujero, por otra puerta: con la pestaña de Nutrición abierta en ese día, al
    # recargar guardaba SU copia del día y borraba lo que se acabara de restaurar por detrás.
    # Dos pestañas abiertas, o el móvil y el ordenador, se pisaban igual.
    #
    # Ahora las comidas se FUSIONAN: lo que llega manda sobre esa comida, y las que no
    # llegan se quedan como estaban. Vaciar una comida sigue funcionando -- se manda con la
    # lista de alimentos vacía, y eso sí la vacía --, y un cambio de reparto ya no borra lo
    # que se sale del reparto nuevo: si mañana vuelve a cuatro comidas, su comida sigue ahí.
    #
    # `comidas_completas=true` para quien de verdad quiera reemplazar el día entero.
    conflictos = []
    if not data.get("comidas_completas"):
        previo = await db.diets.find_one({"user_id": user_id, "fecha": fecha},
                                         {"_id": 0, "comidas": 1, "macros_snapshot": 1,
                                          "updated_at": 1, "tipo_dia": 1, "num_comidas": 1,
                                          "momento_entreno": 1, "opcion_peri": 1,
                                          "distribution_targets": 1})
        anteriores = (previo or {}).get("comidas") or {}
        entrantes = dict(diet_doc.get("comidas") or {})

        # Y LA PESTAÑA VIEJA TAMPOCO PISA CON SU COPIA DE ANTES (16-08-2026).
        #
        # Fusionar salva lo que la pantalla no tiene delante, pero no lo que sí tiene: con el
        # mismo día abierto en el móvil y en el ordenador, el segundo que guardaba devolvía su
        # versión antigua de esa comida y borraba el trabajo del otro. Nadie se enteraba.
        #
        # Cada comida se sella con la hora en que se escribió. Quien guarda dice con qué
        # versión del día empezó (`base_updated_at`, la que le devolvió el servidor al
        # cargar); si una comida se tocó DESPUÉS de eso en otro sitio, la suya está vieja: se
        # conserva la del servidor y se devuelve en `conflictos` para que la pantalla lo diga
        # y recargue. Sin `base_updated_at` -- clientes viejos -- todo sigue como estaba.
        base = str(data.get("base_updated_at") or "")

        # Y EL REPARTO DEL DÍA TAMPOCO SE PISA CON UNA COPIA VIEJA (16-08-2026, en prod).
        #
        # El sello por comida salvaba los alimentos, pero la CONFIGURACIÓN del día -- cuántas
        # comidas, si es entreno o descanso, dónde va el peri, los objetivos de cada comida --
        # se escribía entera con lo que trajera quien guardase. Medido con la cuenta de
        # Francisco: le pedí al asistente «cámbialo a 3 comidas», lo hizo y lo contó bien, y
        # la pestaña de Nutrición abierta al lado devolvió su copia de antes en su siguiente
        # autoguardado: el día volvía a 4 comidas, con la Comida 4 resucitada y sus macros
        # contados dos veces. En pantalla el chat decía una cosa y Nutrición otra.
        #
        # Quien guarda con una versión anterior a la última no manda sobre el reparto: se
        # conserva el del servidor y se avisa con `_dia`, que hace recargar a la pantalla.
        # Sin `base_updated_at` (el volcado del chat, clientes viejos) todo sigue igual.
        sello_dia = str((previo or {}).get("updated_at") or "")
        if base and sello_dia and sello_dia > base:
            for campo in ("tipo_dia", "num_comidas", "momento_entreno", "opcion_peri",
                          "distribution_targets"):
                if (previo or {}).get(campo) is not None:
                    diet_doc[campo] = previo[campo]
            conflictos.append("_dia")

        if base and anteriores:
            for k, comida_previa in anteriores.items():
                if k not in entrantes:
                    continue
                sello = str((comida_previa or {}).get("_ts")
                            or (previo or {}).get("updated_at") or "")
                if sello and sello > base:
                    entrantes[k] = comida_previa
                    conflictos.append(k)
        ahora_iso = diet_doc["updated_at"]
        for k, comida in entrantes.items():
            if isinstance(comida, dict) and k not in conflictos:
                comida["_ts"] = ahora_iso
        if anteriores:
            diet_doc["comidas"] = {**anteriores, **entrantes}
        else:
            diet_doc["comidas"] = entrantes
        # EL TOTAL DEL DÍA NO SE PIERDE PORQUE GUARDE EL CHAT. Nutrición escribe aquí el
        # reparto ya sumado (`P_total`...) y el chat escribe los macros crudos del cliente,
        # que es otra cosa con otras claves. Quien lee el total -- Inicio, para enseñar el
        # mismo objetivo que Nutrición -- se quedaba sin él en cuanto el cliente hablara con
        # el asistente. Si lo que llega no trae totales, se conserva lo que hubiera.
        anterior_snap = (previo or {}).get("macros_snapshot") or {}
        nuevo_snap = diet_doc.get("macros_snapshot") or {}
        if anterior_snap.get("P_total") and not nuevo_snap.get("P_total"):
            diet_doc["macros_snapshot"] = {**anterior_snap, **nuevo_snap}

    await db.diets.update_one(
        {"user_id": user_id, "fecha": fecha},
        {"$set": diet_doc},
        upsert=True
    )
    if conflictos:
        # No es un error: se ha guardado todo lo demás. Es lo que la pantalla tiene que
        # contar y recargar, para que el cliente no crea que puso algo que no está.
        return {**diet_doc, "conflictos": conflictos}
    return diet_doc


@router.post("")
async def save_diet(data: dict, user = Depends(get_current_user)):
    """Guardar la dieta completa de un día, o solo distribution_targets si targets_only=true."""
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Cuerpo inválido")
    # Validar la fecha (YYYY-MM-DD) evita el 500 y cierra la inyección NoSQL de pasar
    # un objeto con operadores ($gt/$where/$regex) que acabaría en el filtro de Mongo.
    fecha = _validar_fecha(data.get("fecha"))

    if data.get("targets_only"):
        await db.diets.update_one(
            {"user_id": user["id"], "fecha": fecha},
            {"$set": {
                "distribution_targets": data.get("distribution_targets"),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }},
            upsert=True
        )
        return {"message": "Targets actualizados", "fecha": fecha}

    guardado = await upsert_diet_doc(user["id"], data, quien=user)

    # `updated_at` vuelve siempre: es la versión con la que la pantalla se queda trabajando
    # a partir de ahora (si no, su siguiente guardado chocaría contra el suyo propio).
    salida = {"message": "Dieta guardada", "fecha": fecha,
              "updated_at": (guardado or {}).get("updated_at")}
    conflictos = (guardado or {}).get("conflictos") or []
    if conflictos:
        salida["conflictos"] = conflictos
    return salida


# ── Dietas favoritas (Calma guardarFavorita / favoritas) - plantillas de día con NOMBRE ──
# Declaradas ANTES de /{fecha} para que "/favorites" no caiga en el path param.
@router.post("/favorites")
async def save_favorite(data: dict, user = Depends(get_current_user)):
    """Guardar el día actual como plantilla favorita con un nombre."""
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Cuerpo inválido")
    name = data.get("name")
    name = name.strip() if isinstance(name, str) else ""
    if not name:
        raise HTTPException(status_code=400, detail="Nombre requerido")
    fav = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "name": name[:60],
        "tipo_dia": data.get("tipo_dia", "entrenamiento"),
        "num_comidas": data.get("num_comidas", 4),
        "momento_entreno": data.get("momento_entreno", 1),
        "opcion_peri": data.get("opcion_peri", "intra_post"),
        "comidas": _as_dict(data.get("comidas")),
        "macros_snapshot": data.get("macros_snapshot"),
        "distribution_targets": _as_dict(data.get("distribution_targets")) or None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.diet_favorites.insert_one(dict(fav))
    return {"message": "Favorita guardada", "favorite": fav}


@router.get("/favorites")
async def list_favorites(user = Depends(get_current_user)):
    """Lista las plantillas favoritas del usuario."""
    favs = await db.diet_favorites.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return {"favorites": favs}


@router.delete("/favorites/{fav_id}")
async def delete_favorite(fav_id: str, user = Depends(get_current_user)):
    """Eliminar una plantilla favorita."""
    res = await db.diet_favorites.delete_one({"id": fav_id, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Favorita no encontrada")
    return {"message": "Favorita eliminada"}


@router.get("/recent")
async def get_recent_diets(limit: int = 14, user = Depends(get_current_user)):
    """Lista los últimos días con dieta guardada."""
    cursor = db.diets.find(
        {"user_id": user["id"]},
        {"_id": 0, "fecha": 1, "tipo_dia": 1, "num_comidas": 1, "comidas": 1, "distribution_targets": 1}
    ).sort("fecha", -1).limit(limit)
    
    diets = await cursor.to_list(length=limit)

    # Las cantidades, a gramos tambien aqui (punto 4.5). Por esta lista entra «Repetir de otro
    # dia»: si un dia migrado se sirviera con el conteo de piezas en el campo de gramos, la
    # copia se llevaria un huevo de 1 g al dia de hoy y lo dejaria guardado asi. El fallo se
    # arregla al leer, y leer es tambien esto.
    for diet in diets:
        await _normalizar_cantidades(diet)

    result = []
    for diet in diets:
        comidas_resumen = {}
        for key, meal_data in (diet.get("comidas") or {}).items():
            alimentos = meal_data.get("alimentos") or []
            if alimentos:
                nombres = [a.get("nombre", "?")[:20] for a in alimentos[:3]]
                comidas_resumen[key] = " + ".join(nombres)
                if len(alimentos) > 3:
                    comidas_resumen[key] += f" +{len(alimentos)-3}"
        
        result.append({
            "fecha": diet.get("fecha"),
            "tipo_dia": diet.get("tipo_dia", "entrenamiento"),
            "num_comidas": diet.get("num_comidas", 4),
            "comidas_resumen": comidas_resumen,
            "comidas": diet.get("comidas", {}),
            "distribution_targets": diet.get("distribution_targets", None)
        })
    
    return {"diets": result, "count": len(result)}

@router.get("/calendar/{year}/{month}")
async def get_diet_calendar(year: int, month: int, user = Depends(get_current_user)):
    """Obtener calendario de dietas del mes."""
    if not (1 <= month <= 12) or not (1900 <= year <= 2200):
        raise HTTPException(status_code=400, detail="Año o mes fuera de rango.")
    start_date = f"{year}-{month:02d}-01"
    last_day = calendar.monthrange(year, month)[1]
    end_date = f"{year}-{month:02d}-{last_day}"
    
    diets = await db.diets.find(
        {
            "user_id": user["id"],
            "fecha": {"$gte": start_date, "$lte": end_date}
        },
        {"_id": 0, "fecha": 1, "tipo_dia": 1, "comidas": 1, "is_cuadrado": 1}
    ).to_list(31)
    
    calendar_data = {}
    for diet in diets:
        fecha = diet["fecha"]
        comidas = diet.get("comidas", {})
        
        total_foods = sum(len(m.get("alimentos", [])) for m in comidas.values())
        total_comidas = len([k for k, v in comidas.items() if v.get("alimentos")])
        
        status = "empty"
        if total_foods > 0:
            num_comidas = 4
            if total_comidas >= num_comidas:
                status = "complete"
            elif total_comidas > 0:
                status = "partial"
        
        calendar_data[fecha] = {
            "tipo_dia": diet.get("tipo_dia", "entrenamiento"),
            "status": status,
            "total_comidas": total_comidas,
            "is_cuadrado": diet.get("is_cuadrado", False)
        }

    # Días con cambio de macros (Calma esDiaConCambioDeMacros): effective_date de macro_history
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
    macro_change_dates = []
    if profile:
        hist = await db.macro_history.find(
            {"client_id": profile["id"]}, {"_id": 0, "effective_date": 1, "created_at": 1}
        ).to_list(500)
        for h in hist:
            d = h.get("effective_date") or str(h.get("created_at", ""))[:10]
            if d and start_date <= d <= end_date:
                macro_change_dates.append(d)

    return {"year": year, "month": month, "days": calendar_data,
            "macro_change_dates": sorted(set(macro_change_dates))}

@router.patch("/{fecha}/targets")
async def update_diet_targets(fecha: str, data: dict, user = Depends(get_current_user)):
    """Actualizar solo distribution_targets sin tocar comidas."""
    _validar_fecha(fecha)
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Cuerpo inválido")
    targets = data.get("distribution_targets")
    if targets is not None and not isinstance(targets, dict):
        raise HTTPException(status_code=400, detail="distribution_targets debe ser un objeto.")
    await db.diets.update_one(
        {"user_id": user["id"], "fecha": fecha},
        {"$set": {
            "distribution_targets": targets,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }},
        upsert=True
    )
    return {"message": "Targets actualizados", "fecha": fecha}

@router.post("/copy-day")
async def copy_day(data: dict, user = Depends(get_current_user)):
    """Copiar el día completo (todas las comidas) de una fecha a otra."""
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Cuerpo inválido")
    source_date = _validar_fecha(data.get("fecha_origen"))
    target_date = _validar_fecha(data.get("fecha_destino"))

    source_diet = await db.diets.find_one({"user_id": user["id"], "fecha": source_date}, {"_id": 0})
    if not source_diet:
        raise HTTPException(status_code=404, detail="No hay dieta guardada para la fecha origen")

    copy_doc = {
        "user_id": user["id"],
        "fecha": target_date,
        "tipo_dia": source_diet.get("tipo_dia", "entrenamiento"),
        "num_comidas": source_diet.get("num_comidas", 4),
        "momento_entreno": source_diet.get("momento_entreno", 1),
        "opcion_peri": source_diet.get("opcion_peri", "intra_post"),
        "comidas": source_diet.get("comidas", {}),
        "macros_snapshot": source_diet.get("macros_snapshot"),
        "distribution_targets": source_diet.get("distribution_targets"),
        "is_cuadrado": source_diet.get("is_cuadrado", False),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.diets.update_one(
        {"user_id": user["id"], "fecha": target_date},
        {"$set": copy_doc},
        upsert=True
    )
    return {"message": "Día copiado", "origen": source_date, "destino": target_date}

# LO QUE HAY QUE RESOLVER PARA ENSEÑAR UN DIA GUARDADO vive en `core.dieta_para_ver`.
#
# Estaba aqui, y por eso el panel del entrenador -- que tiene su propia ruta -- devolvia el
# documento crudo de Mongo y enseñaba P0 H0 G0 y "1 g de huevo" (Jesus, 16-08). Los nombres
# de aqui se quedan porque los usa el resto del fichero y `routes/chatbot.py`.
_ids_de = _para_ver.ids_de
_normalizar_con_catalogo = _para_ver.normalizar_con_catalogo
_normalizar_cantidades = _para_ver.normalizar_cantidades
_adjuntar_urls = _para_ver.adjuntar_urls


@router.get("/{fecha}")
async def get_diet(fecha: str, user = Depends(get_current_user)):
    """Obtener la dieta guardada para una fecha."""
    diet = await db.diets.find_one(
        {"user_id": user["id"], "fecha": fecha},
        {"_id": 0}
    )
    if not diet:
        return {"fecha": fecha, "exists": False}

    await _adjuntar_urls(diet)
    diet["exists"] = True
    return diet

@router.post("/copy")
async def copy_diet(data: dict, user = Depends(get_current_user)):
    """Copiar una comida de otro día."""
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Cuerpo inválido")
    source_date = _validar_fecha(data.get("source_date"))
    target_date = _validar_fecha(data.get("target_date"))
    source_meal = data.get("source_meal")
    target_meal = data.get("target_meal")

    if not (isinstance(source_meal, str) and isinstance(target_meal, str) and source_meal and target_meal):
        raise HTTPException(status_code=400, detail="Faltan parámetros")
    
    source_diet = await db.diets.find_one(
        {"user_id": user["id"], "fecha": source_date},
        {"_id": 0}
    )
    
    if not source_diet:
        raise HTTPException(status_code=404, detail="Dieta origen no encontrada")
    
    source_comida = source_diet.get("comidas", {}).get(source_meal)
    if not source_comida:
        raise HTTPException(status_code=404, detail="Comida origen no encontrada")
    
    # Also copy distribution target for that specific meal if it exists
    source_targets = source_diet.get("distribution_targets") or {}
    source_meal_target = source_targets.get(source_meal)

    update_payload = {
        f"comidas.{target_meal}": source_comida,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    if source_meal_target:
        update_payload[f"distribution_targets.{target_meal}"] = source_meal_target

    await db.diets.update_one(
        {"user_id": user["id"], "fecha": target_date},
        {
            "$set": update_payload
        },
        upsert=True
    )
    
    return {
        "message": "Comida copiada",
        "source": f"{source_date}/{source_meal}",
        "target": f"{target_date}/{target_meal}"
    }

@router.delete("/{fecha}")
async def delete_diet(fecha: str, user = Depends(get_current_user)):
    """Eliminar una dieta."""
    result = await db.diets.delete_one({"user_id": user["id"], "fecha": fecha})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Dieta no encontrada")
    return {"message": "Dieta eliminada", "fecha": fecha}


@router.get("/{fecha}/pdf")
async def export_diet_pdf(fecha: str, user = Depends(get_current_user)):
    """Genera PDF de la dieta de un día desde NutritionPage."""
    diet = await db.diets.find_one(
        {"user_id": user["id"], "fecha": fecha},
        {"_id": 0}
    )
    if not diet:
        raise HTTPException(status_code=404, detail="No hay dieta guardada para este día")

    # Las cantidades a gramos ANTES de nada (punto 4.5). En las dietas que vinieron de Calma
    # los alimentos por unidades guardan el conteo de piezas en `cantidad_g`, y un huevo
    # aparece como "1". El resto de rutas ya normalizan al leer; el PDF se habia quedado
    # fuera, asi que para esos alimentos ensenaba "0 ud" y unos macros de un gramo de huevo.
    await _normalizar_cantidades(diet)

    comidas_raw = diet.get("comidas", {})
    if not comidas_raw:
        raise HTTPException(status_code=400, detail="La dieta está vacía")

    meal_names = {
        "C1": "Comida 1", "C2": "Comida 2", "C3": "Comida 3", "C4": "Comida 4",
        "Intra": "Intra-entreno", "Post": "Post-entreno"
    }

    tipo_dia = diet.get("tipo_dia") or "entrenamiento"

    # Objetivo del día y por comida: se recalcula con el motor a partir de los macros
    # del perfil vigentes a esa fecha, con la misma config que la dieta (así el PDF
    # muestra objetivo vs consumido, no solo lo consumido).
    objetivo_por_comida = {}
    objetivo_total = {}
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    try:
        from routes.calculator import _resolve_macros_for_date
        from macro_distribution import distribuir_macros as _dist, leer_macro, leer_peri
        if profile:
            training, rest, peri = await _resolve_macros_for_date(profile, fecha)
            base = training if tipo_dia == "entrenamiento" else rest
            if base:
                opcion_peri = diet.get("opcion_peri") or "intra_post"
                # 35/15 solo si NO hay peri configurado, y nunca en `sin_peri`; un peri a 0
                # se respeta (leer_peri/leer_macro).
                p_peri, h_peri = leer_peri(peri, opcion_peri)
                dist = _dist(
                    p_entreno=leer_macro(training, "protein", "proteinas"),
                    h_entreno=leer_macro(training, "carbs", "hidratos"),
                    g_entreno=leer_macro(training, "fat", "grasas"),
                    p_peri=p_peri,
                    h_peri=h_peri,
                    p_descanso=leer_macro(rest, "protein", "proteinas"),
                    h_descanso=leer_macro(rest, "carbs", "hidratos"),
                    g_descanso=leer_macro(rest, "fat", "grasas"),
                    tipo_dia=tipo_dia,
                    num_comidas=int(diet.get("num_comidas") or 4),
                    momento_entreno=int(diet.get("momento_entreno") or 1),
                    opcion_peri=opcion_peri,
                    single_meal=bool(diet.get("num_comidas") == 1),
                )
                objetivo_por_comida = {**dist.get("comidas", {}), **dist.get("periworkout", {})}
                res = dist.get("resumen", {})
                objetivo_total = {"P": res.get("P_total", 0), "H": res.get("H_total", 0),
                                  "G": res.get("G_total", 0)}
    except Exception:
        objetivo_por_comida, objetivo_total = {}, {}

    def _aporta_de(a, p, h, g):
        """Todo lo que aporta el alimento, de mayor a menor.

        Antes salia UN solo macro (el primero de P/H/G que contase), asi que las almendras
        aparecian como "6.9 g de proteina" y no se veian los 18.6 de grasa, que es lo que
        de verdad aportan. Ahora se listan todos los que cuentan, empezando por el mayor.
        """
        items = [(rol, valor) for rol, valor in (("P", p), ("H", h), ("G", g)) if valor > 0]
        items.sort(key=lambda x: -x[1])
        return [{"rol": rol, "valor": valor} for rol, valor in items]

    # Catalogo de los alimentos de la dieta: hace falta para saber cuales van por unidades
    # (el campo `unidad` que se guarda en la dieta viene vacio en casi todas las filas)
    # y, desde el 11-08, para poder CALCULAR los macros que no se guardaron (ver abajo).
    ids = [a.get("alimento_id") for m in comidas_raw.values()
           for a in (m.get("alimentos") or []) if a.get("alimento_id") is not None]
    catalogo = {}
    if ids:
        async for f in db.foods.find({"id": {"$in": ids}}, {"_id": 0}):
            catalogo[f["id"]] = f

    # Los macros que cuentan (calculados si el dia no los guardo) y la cantidad escrita
    # como la lee una persona ("2 ud (126 g)"). Las dos las comparte con el visor de dietas
    # del panel, que es donde faltaban.
    def _macros_de(a: dict) -> dict:
        return _para_ver.macros_de(a, catalogo)

    def _cantidad_de(a: dict) -> str:
        return _para_ver.cantidad_de(a, catalogo)

    # Build comidas list in the format pdf_generator expects
    comidas_list = []
    total_p, total_h, total_g = 0, 0, 0

    for key in ["C1", "Intra", "Post", "C2", "C3", "C4"]:
        meal_data = comidas_raw.get(key)
        if not meal_data:
            continue
        alimentos_raw = meal_data.get("alimentos", [])
        if not alimentos_raw:
            continue

        alimentos_pdf = []
        mp, mh, mg = 0, 0, 0
        for a in alimentos_raw:
            me = _macros_de(a)
            p = round(me.get("P", 0), 1)
            h = round(me.get("H", 0), 1)
            g = round(me.get("G", 0), 1)
            mp += p; mh += h; mg += g
            aporta_items = _aporta_de(a, p, h, g)
            alimentos_pdf.append({
                "nombre": a.get("nombre", "?"),
                "cantidad_txt": _cantidad_de(a),
                "aporta_items": aporta_items,
                # compatibilidad con el formato antiguo del generador
                "cantidad": a.get("cantidad_g", 0),
                "unidad": a.get("unidad") or "g",
                "rol": aporta_items[0]["rol"] if aporta_items else "P",
                "aporta": aporta_items[0]["valor"] if aporta_items else 0,
            })

        total_p += mp; total_h += mh; total_g += mg
        obj = objetivo_por_comida.get(key, {})
        comidas_list.append({
            "titulo": meal_names.get(key, key),
            "es_peri": key in ("Intra", "Post"),
            "alimentos": alimentos_pdf,
            "macros": {"P": round(mp, 1), "H": round(mh, 1), "G": round(mg, 1)},
            "objetivo": {"P": obj.get("P", 0), "H": obj.get("H", 0), "G": obj.get("G", 0)} if obj else {},
        })

    consumido = {"P": round(total_p, 1), "H": round(total_h, 1), "G": round(total_g, 1)}
    diferencia = {}
    if objetivo_total:
        diferencia = {
            "P": round(objetivo_total["P"] - consumido["P"], 1),
            "H": round(objetivo_total["H"] - consumido["H"], 1),
            "G": round(objetivo_total["G"] - consumido["G"], 1),
        }

    goal_labels = {"volumen": "Volumen", "definicion": "Definición", "definición": "Definición",
                   "mantenimiento": "Mantenimiento", "recomposicion": "Recomposición"}
    goal_raw = (profile or {}).get("goal")
    summary = {
        "tipo_dia": tipo_dia,
        "objetivo_cliente": goal_labels.get((goal_raw or "").lower(), goal_raw),
        "semana": (profile or {}).get("week"),
        "objetivo_total": objetivo_total,
        "totales": consumido,
        "diferencia": diferencia,
        "comidas": comidas_list,
    }

    user_name = user.get("name", "Cliente")
    pdf_buffer = generate_diet_pdf(summary, user_name, fecha)
    filename = f"dieta_jg12_{fecha}.pdf"

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
