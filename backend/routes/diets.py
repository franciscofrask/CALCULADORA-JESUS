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
from calma_suggest import macros_reales
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


async def upsert_diet_doc(user_id: str, data: dict) -> dict:
    """
    Construye el documento de dieta de un día y lo upserta en db.diets sobre
    (user_id, fecha). Forma única compartida por save_diet y el volcado del chatbot
    para que ambos escriban exactamente el mismo shape.
    """
    fecha = data.get("fecha")
    diet_doc = {
        "user_id": user_id,
        "fecha": fecha,
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

    await db.diets.update_one(
        {"user_id": user_id, "fecha": fecha},
        {"$set": diet_doc},
        upsert=True
    )
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

    await upsert_diet_doc(user["id"], data)

    return {"message": "Dieta guardada", "fecha": fecha}


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

def _ids_de(diet: dict) -> set:
    """Los ids de alimento que aparecen en un dia."""
    ids = {
        a.get("alimento_id") if a.get("alimento_id") is not None else a.get("id")
        for comida in (diet.get("comidas") or {}).values()
        for a in ((comida or {}).get("alimentos") or [])
    }
    ids.discard(None)
    return ids


def _normalizar_con_catalogo(diet: dict, catalogo: dict) -> int:
    """Pasa a gramos las cantidades del dia. Punto 4.5 de la revision del 09-08.

    En las dietas que vinieron de Calma los alimentos POR UNIDADES guardan el CONTEO de piezas
    en `cantidad_g`: un huevo entero aparece como "1". Leido como un gramo de huevo da 0,1 de
    proteina y al pintarlo en unidades sale "0 ud", que es lo que reporto Jesus.

    Se convierte AL LEER y no en la pantalla porque por aqui pasan todas -- Nutricion, el
    asistente, el PDF, la ficha del entrenador --, y arreglarlo en una sola dejaria a las
    otras enseñando el numero malo. Y ademas era el escritor: al abrir un dia migrado, la
    pantalla recalculaba los macros con la cantidad como gramos y al guardar los dejaba
    escritos, convirtiendo un registro incompleto en uno falso.
    """
    from calculator import get_food_config
    from core.cantidad_de_dieta import normalizar_dieta

    cfgs = {}

    def config_de(alimento_id, item):
        if alimento_id not in cfgs:
            ficha = catalogo.get(alimento_id)
            cfgs[alimento_id] = get_food_config(ficha) if ficha else None
        return cfgs[alimento_id]

    return normalizar_dieta(diet, config_de)


async def _normalizar_cantidades(diet: dict) -> int:
    """Lo mismo, trayendose el catalogo que haga falta. Para las rutas que no lo tienen ya."""
    ids = _ids_de(diet)
    if not ids:
        return 0
    catalogo = {
        f["id"]: f
        async for f in db.foods.find(
            {"id": {"$in": list(ids)}},
            {"_id": 0, "id": 1, "racion": 1, "unidades": 1, "categorias": 1, "nombre": 1},
        )
    }
    return _normalizar_con_catalogo(diet, catalogo)


async def _adjuntar_urls(diet: dict) -> None:
    """
    Pone en cada alimento del dia lo que hay que resolver contra el catalogo:

      - `url`: la ficha del producto (los de marca la tienen; los genericos no).
      - `macros_reales`: lo que dice la etiqueta, para el switch de la pestaña de
        Nutricion. Es SOLO para enseñarlo: no se guarda, no cuenta y no cambia el
        reparto; lo que cuenta sigue siendo `macros_efectivos`.

    Se resuelve aqui y no al guardar por dos motivos: los dias ya guardados no lo tienen
    (de 3365 alimentos guardados, solo 95 traian los macros de etiqueta), y los alimentos
    entran por muchas puertas (buscador, chatbot, menu sugerido, copiar dia, favoritas),
    asi que guardarlo en cada una seria facil de olvidar. Ademas, si se corrige un
    alimento, los dias antiguos lo cogen solos. Es una unica consulta por dia.
    """
    comidas = diet.get("comidas") or {}
    ids = {
        a.get("alimento_id") if a.get("alimento_id") is not None else a.get("id")
        for comida in comidas.values()
        for a in ((comida or {}).get("alimentos") or [])
    }
    ids.discard(None)
    if not ids:
        return

    catalogo = {
        f["id"]: f
        async for f in db.foods.find(
            {"id": {"$in": list(ids)}},
            # `categorias` va en la proyeccion porque la necesita `get_food_config` para
            # saber si un alimento va por unidades y cuanto pesa una.
            {"_id": 0, "id": 1, "url": 1, "proteinas": 1, "hidratos": 1, "grasas": 1,
             "racion": 1, "unidades": 1, "categorias": 1},
        )
    }

    # Las cantidades, a gramos ANTES de calcular nada (punto 4.5): si no, `macros_reales`
    # saldria del numero equivocado.
    _normalizar_con_catalogo(diet, catalogo)

    for comida in comidas.values():
        for a in ((comida or {}).get("alimentos") or []):
            clave = a.get("alimento_id") if a.get("alimento_id") is not None else a.get("id")
            ficha = catalogo.get(clave)
            if not ficha:
                continue
            if ficha.get("url"):
                a["url"] = ficha["url"]
            try:
                a["macros_reales"] = macros_reales(ficha, float(a.get("cantidad_g") or 0))
            except (TypeError, ValueError):
                pass  # un alimento raro no puede tumbar la carga del dia


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
    # (el campo `unidad` que se guarda en la dieta viene vacio en casi todas las filas).
    ids = [a.get("alimento_id") for m in comidas_raw.values()
           for a in (m.get("alimentos") or []) if a.get("alimento_id") is not None]
    catalogo = {}
    if ids:
        async for f in db.foods.find({"id": {"$in": ids}},
                                     {"_id": 0, "id": 1, "unidades": 1, "racion": 1}):
            catalogo[f["id"]] = f

    def _cantidad_de(a):
        """Texto de la cantidad. En los alimentos por unidades, Jesus quiere ver las
        unidades y el peso entre parentesis: "2 ud (126 g)", no "126 g" a secas."""
        gramos = a.get("cantidad_g", 0) or 0
        food = catalogo.get(a.get("alimento_id")) or {}
        por_unidad = bool(food.get("unidades")) or a.get("unidad") == "ud"
        racion = float(food.get("racion") or a.get("racion") or 0)
        if por_unidad and racion > 0:
            uds = round(gramos / racion * 2) / 2          # medias unidades, como en la app
            uds_txt = f"{uds:.0f}" if uds == int(uds) else f"{uds:.1f}"
            return f"{uds_txt} ud ({gramos:.0f} g)"
        return f"{gramos:.0f} g"

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
            me = a.get("macros_efectivos", {})
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
