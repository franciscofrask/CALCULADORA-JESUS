"""
Rutas de dietas: CRUD, calendario, copiar.
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone
from typing import Optional
import calendar
import logging
import uuid

from core.database import db
from core.security import get_current_user
from core.tiempo import dia_del_cliente, hoy_madrid
from calma_suggest import macros_reales
from macro_distribution import objetivo_de_las_comidas
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
    # UNA FAVORITA VACÍA NO ES UNA FAVORITA (punto 15 del documento del 17-08). Se podía
    # guardar el día sin haber puesto nada, y quedaba en la lista una plantilla con «0
    # comidas» que al aplicarla no hace nada: seis de las 1.211 de producción están así. El
    # sitio de esta comprobación es aquí y no en la pantalla, porque el día se guarda desde
    # Nutrición y desde el asistente.
    comidas = _as_dict(data.get("comidas"))
    if not any((c or {}).get("alimentos") for c in comidas.values()):
        raise HTTPException(
            status_code=400,
            detail="Este día está vacío. Monta al menos una comida antes de guardarlo.")
    fav = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "name": name[:60],
        "tipo_dia": data.get("tipo_dia", "entrenamiento"),
        "num_comidas": data.get("num_comidas", 4),
        "momento_entreno": data.get("momento_entreno", 1),
        "opcion_peri": data.get("opcion_peri", "intra_post"),
        "comidas": comidas,
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
async def get_recent_diets(limit: int = 14, para: Optional[str] = None, user = Depends(get_current_user)):
    """Lista los últimos días con dieta guardada.

    `para` es el día para el que se quiere repetir (el que el cliente tiene abierto, con
    su reloj): las comidas se juzgan contra los macros vigentes de ESE día (caso 27 de
    los 85; punto 14 del doc del 23-08). Sin `para`, el día de España.
    """
    cursor = db.diets.find(
        {"user_id": user["id"]},
        {"_id": 0, "fecha": 1, "tipo_dia": 1, "num_comidas": 1, "momento_entreno": 1,
         "opcion_peri": 1, "comidas": 1, "distribution_targets": 1}
    ).sort("fecha", -1).limit(limit)

    diets = await cursor.to_list(length=limit)

    # Las cantidades, a gramos tambien aqui (punto 4.5). Por esta lista entra «Repetir de otro
    # dia»: si un dia migrado se sirviera con el conteo de piezas en el campo de gramos, la
    # copia se llevaria un huevo de 1 g al dia de hoy y lo dejaria guardado asi. El fallo se
    # arregla al leer, y leer es tambien esto.
    for diet in diets:
        await _normalizar_cantidades(diet)

    # El objetivo de cada comida PARA EL DÍA DESTINO, una vez por configuración distinta
    # (dos días guardados con 4 comidas y entreno comparten reparto: no se calcula dos veces).
    fecha_para = dia_del_cliente(para) if para else hoy_madrid().isoformat()
    repartos_por_config: dict = {}

    async def _objetivo_para(diet: dict):
        """El objetivo POR COMIDA del día destino, con la configuración de ese día guardado."""
        clave = (diet.get("tipo_dia"), diet.get("num_comidas"),
                 diet.get("momento_entreno"), diet.get("opcion_peri"))
        if clave not in repartos_por_config:
            reparto = await _reparto_del_dia(fecha_para, diet, user)
            repartos_por_config[clave] = (
                {**(reparto.get("comidas") or {}), **(reparto.get("periworkout") or {})}
                if reparto else None)
        return repartos_por_config[clave]

    result = []
    for diet in diets:
        # SOLO SE OFRECE LO QUE SE PUEDE CUADRAR (caso 27): una Comida 2 que son 20 g de
        # pollo no puede llegar a los hidratos de hoy ni escalando, asi que no se ofrece
        # para repetir. El criterio es de fuentes, no de gramos: si ningun alimento de la
        # comida aporta un macro que hoy pide de verdad (> 8 g), esa comida no tiene
        # camino al objetivo -- cuadrar (test 28) escala y completa cantidades, pero no
        # inventa alimentos que no estan.
        objetivo = await _objetivo_para(diet)
        comidas_resumen = {}
        cuadrada = {}
        for key, meal_data in (diet.get("comidas") or {}).items():
            alimentos = meal_data.get("alimentos") or []
            if not alimentos:
                continue
            objetivo_k = (objetivo or {}).get(key)
            if objetivo_k:
                servido = {m: sum(float((a.get("macros_efectivos") or {}).get(m) or 0)
                                  for a in alimentos) for m in ("P", "H", "G")}
                sin_fuente = [m for m in ("P", "H", "G")
                              if float(objetivo_k.get(m) or 0) > 8 and servido[m] <= 0]
                if sin_fuente:
                    continue
                cuadrada[key] = all(abs(servido[m] - float(objetivo_k.get(m) or 0)) <= 4
                                    for m in ("P", "H", "G"))
            nombres = [a.get("nombre", "?")[:20] for a in alimentos[:3]]
            comidas_resumen[key] = " + ".join(nombres)
            if len(alimentos) > 3:
                comidas_resumen[key] += f" +{len(alimentos)-3}"

        result.append({
            "fecha": diet.get("fecha"),
            "tipo_dia": diet.get("tipo_dia", "entrenamiento"),
            "num_comidas": diet.get("num_comidas", 4),
            "comidas_resumen": comidas_resumen,
            # Si cada comida ya cuadra tal cual con los macros del día destino (±4 g).
            "cuadrada": cuadrada,
            "comidas": diet.get("comidas", {}),
            "distribution_targets": diet.get("distribution_targets", None)
        })

    return {"diets": result, "count": len(result)}


# ── Mi semana (rediseño, tarea 5.1 del 21-08) ────────────────────────────────
# Declarada ANTES de /{fecha} para que "semana" no caiga en el path param.

# Los días como los escribe el panel en routines.days[].day; weekday() da 0 = lunes.
_DIAS_SEMANA = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")


def _dia_de_la_rutina(routine: Optional[dict], indice_semana: int) -> Optional[dict]:
    """El día de la rutina activa que cae en ese día de la semana, o None si no hay."""
    if not routine:
        return None
    from routes.workout_logs import _plano
    nombre = _DIAS_SEMANA[indice_semana]
    for d in routine.get("days") or []:
        if _plano(d.get("day")) == nombre:
            return d
    return None


def _nombre_del_entreno(dia_rutina: Optional[dict]) -> Optional[str]:
    """El grupo muscular del día si la rutina lo trae, y si no None: aquí no se inventa
    un título («Entreno de hoy» queda bien en la pantalla de hoy, no en un martes)."""
    for clave in ("grupo", "focus", "nombre", "titulo"):
        valor = str((dia_rutina or {}).get(clave) or "").strip()
        if valor:
            return valor
    return None


@router.get("/semana")
async def get_semana(inicio: Optional[str] = None, hoy_cliente: Optional[str] = None,
                     user = Depends(get_current_user)):
    """Los siete días de la semana del cliente (lunes a domingo, en hora de España),
    cada uno con el estado de su dieta y su entreno. Es lo que pinta Mi semana.

    `inicio` (opcional, YYYY-MM-DD) es cualquier día de la semana que se quiera mirar;
    sin él, la semana de hoy. El estado de cada día:

      - montada: todas las comidas principales del día tienen alimentos,
      - empezada: alguna con alimentos pero no todas,
      - sin_montar: ninguna.

    El peri (Intra/Post) no cuenta como comida, y los macros son los del motor de
    conteo único (`calibrar_dia`), los mismos que enseñan Inicio y Nutrición.
    """
    from datetime import date as _date, timedelta
    from core.tiempo import dia_del_cliente

    # `hoy_cliente` es el dia del RELOJ DEL CLIENTE (bloque F, 23-08): decide la pastilla
    # «Hoy» y la semana por defecto. Validado; sin el, el dia de España, como siempre.
    hoy = _date.fromisoformat(dia_del_cliente(hoy_cliente))
    base = hoy
    if inicio:
        base = _date.fromisoformat(_validar_fecha(inicio))
    lunes = base - timedelta(days=base.weekday())
    fechas = [(lunes + timedelta(days=i)).isoformat() for i in range(7)]

    # UNA consulta para los siete días, no siete.
    diets = {
        d["fecha"]: d
        async for d in db.diets.find(
            {"user_id": user["id"], "fecha": {"$gte": fechas[0], "$lte": fechas[6]}},
            {"_id": 0, "fecha": 1, "tipo_dia": 1, "num_comidas": 1, "comidas": 1})
    }

    # El catálogo de TODOS los alimentos de la semana, también de una vez: hace falta
    # entero (no la proyección corta) porque la calibración y el paso a gramos de los
    # días migrados de Calma necesitan los campos de macros y de unidades.
    ids = set()
    for d in diets.values():
        ids |= _ids_de(d)
    catalogo = {}
    if ids:
        async for f in db.foods.find({"id": {"$in": list(ids)}}, {"_id": 0}):
            catalogo[f["id"]] = f

    import math as _math
    for d in diets.values():
        # Cantidades NaN fuera antes de calcular nada (doc 57): el NaN se propaga a la
        # suma y el JSON no lo admite, y la semana entera respondería 500.
        for a in _para_ver.alimentos_de(d):
            v = a.get("cantidad_g")
            if isinstance(v, float) and not _math.isfinite(v):
                a["cantidad_g"] = 0
        # Y a gramos (punto 4.5): en los días migrados de Calma los alimentos por
        # unidades guardan el conteo de piezas donde van los gramos.
        _normalizar_con_catalogo(d, catalogo)

    # La rutina activa dice qué días de la semana son de entreno; los registros de
    # entreno (workout_logs, T3) dicen cuáles se hicieron. El perfil hace de puente:
    # las dos colecciones van por client_profiles.id, no por users.id.
    perfil = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
    routine = None
    if perfil.get("id"):
        routine = await db.routines.find_one(
            {"client_id": perfil["id"], "status": "active"}, {"_id": 0, "days": 1})

    # EL GRUPO DEL DÍA CUANDO LA RUTINA VA EN PDF (tarea 7.1 del 21-08): el reparto que
    # puso el entrenador al subir el PDF, colocado sobre los días que entrena el cliente
    # (training_weekdays). {0: "Empuje", 1: "Tirón", ...} o None si falta cualquiera de
    # los dos datos. Import perezoso para no atar los módulos en el arranque.
    from routes.routines import grupos_del_reparto
    grupos_pdf = await grupos_del_reparto(perfil)

    from routes.settings import pantalla_activa
    seguimiento_entrenos = await pantalla_activa("t3_entreno")
    logs = {}
    if seguimiento_entrenos and perfil.get("id"):
        async for l in db.workout_logs.find(
                {"client_id": perfil["id"], "fecha": {"$gte": fechas[0], "$lte": fechas[6]}},
                {"_id": 0, "fecha": 1, "hecho": 1}):
            logs[l["fecha"]] = bool(l.get("hecho"))

    dias = []
    montadas = empezadas = sin_montar = 0
    entrenos_total = entrenos_hechos = 0
    for i, fecha in enumerate(fechas):
        diet = diets.get(fecha)
        dia_rutina = _dia_de_la_rutina(routine, i)

        # El tipo del día: lo que diga SU dieta si está guardada (es lo que el cliente
        # dijo para ese día concreto) y, si no, lo que toque por rutina. Sin ninguna de
        # las dos, no se sabe y se dice que no se sabe.
        if diet:
            tipo = diet.get("tipo_dia") or "entrenamiento"
        elif dia_rutina is not None:
            tipo = "descanso" if dia_rutina.get("is_rest") else "entrenamiento"
        elif grupos_pdf is not None:
            # Sin dieta y sin rutina estructurada, pero con PDF + días del cliente: el
            # reparto también sabe qué días son de entreno, no solo cómo se llaman.
            tipo = "entrenamiento" if i in grupos_pdf else "descanso"
        else:
            tipo = None

        num_comidas = int((diet or {}).get("num_comidas") or 4)
        comidas = (diet or {}).get("comidas") or {}
        principales = [f"C{n}" for n in range(1, num_comidas + 1)]
        con_alimentos = sum(
            1 for k in principales if (comidas.get(k) or {}).get("alimentos"))

        if con_alimentos == 0:
            estado = "sin_montar"
            sin_montar += 1
        elif con_alimentos >= num_comidas:
            estado = "montada"
            montadas += 1
        else:
            estado = "empezada"
            empezadas += 1

        macros = {"P": 0.0, "H": 0.0, "G": 0.0}
        if diet and con_alimentos:
            macros = await _servido_de_las_comidas(diet, fichas=catalogo)

        hecho = logs.get(fecha) if seguimiento_entrenos else None
        if tipo == "entrenamiento":
            entrenos_total += 1
            if hecho:
                entrenos_hechos += 1

        dias.append({
            "fecha": fecha,
            "tipo_dia": tipo,
            "estado": estado,
            "macros": macros,
            "n_comidas_con_alimentos": con_alimentos,
            "n_comidas_total": num_comidas,
            "entreno": {
                # El nombre del grupo: el de la rutina estructurada si lo trae y, si no,
                # el del reparto del PDF (7.1 del 21-08). El front ya lo pinta si llega.
                "nombre": (_nombre_del_entreno(dia_rutina) or (grupos_pdf or {}).get(i))
                          if tipo == "entrenamiento" else None,
                # true/false solo cuando el registro de entrenos (T3) está encendido;
                # null = todavía no hay forma de saberlo.
                "hecho": hecho if (seguimiento_entrenos and tipo == "entrenamiento") else None,
            },
        })

    # Sin rutina y sin días guardados no hay forma de saber qué días entrena ESTA
    # semana: se cae a los días de entreno de la ficha (4 si no consta otra cosa).
    if entrenos_total == 0 and not routine and not diets:
        from core.dias_de_entreno import dias_de_entreno
        entrenos_total = dias_de_entreno(perfil)

    return {
        "inicio": fechas[0],
        "fin": fechas[6],
        "hoy": hoy.isoformat(),
        "dias": dias,
        "resumen": {
            "montadas": montadas,
            "empezadas": empezadas,
            "sin_montar": sin_montar,
            "entrenos_total": entrenos_total,
            # null cuando no hay seguimiento de sesiones: la pantalla enseña
            # «N entrenos» a secas en vez de un «0 de N» que nadie ha contado.
            "entrenos_hechos": entrenos_hechos if seguimiento_entrenos else None,
        },
    }


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

@router.patch("/{fecha}/comida-marcada")
async def marcar_comida(fecha: str, data: dict, user = Depends(get_current_user)):
    """La casilla por comida del Inicio nuevo (bloque 4 del doc 21-08).

    «Marcar la comida es lo que cuenta como comida»: de aquí salen Llevas y Falta del
    deslizador. Se guarda dentro de la propia comida (`comidas.{k}.marcada`) para que
    viaje con el día: la marca es del cliente en cualquier aparato, no de un navegador.
    El peri no se marca (regla 3 del diseño), así que Intra y Post se rechazan.
    """
    _validar_fecha(fecha)
    comida = data.get("comida") if isinstance(data, dict) else None
    marcada = bool(data.get("marcada")) if isinstance(data, dict) else None
    if not isinstance(comida, str) or not _re.fullmatch(r"C[1-9]", comida):
        raise HTTPException(status_code=400, detail="Dime qué comida marco (C1 a C9).")
    await db.diets.update_one(
        {"user_id": user["id"], "fecha": fecha},
        {"$set": {
            f"comidas.{comida}.marcada": marcada,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return {"fecha": fecha, "comida": comida, "marcada": marcada}


# ── Extras del día (apartado 5 y «Extras» del doc del 21-08) ─────────────────
#
# Lo que el cliente se come FUERA de su dieta -- el cumpleaños, el picoteo -- no tenía dónde
# apuntarse: o lo metía en una comida (y descuadraba el reparto) o no lo contaba (y la app
# creía que iba perfecto). Es lo que le obligaba a mentirle a la app para que le cuadrara.
#
# Los extras viven en el documento del día como lista `extras`, HERMANA de `comidas` y no
# dentro: así nadie que cuente comidas los ve. `_servido_de_las_comidas`, la calibración y
# los helpers de `core.dieta_para_ver` (`alimentos_de`, `ids_de`) recorren `diet["comidas"]`
# y solo eso, y el `$set` de `upsert_diet_doc` escribe campos con nombre, así que un guardado
# desde Nutrición o el chat tampoco los pisa. Cuentan en «Llevas» (los suma la pantalla del
# Inicio), no tocan la dieta ni el reparto, y con ellos «Falta» puede quedar en negativo y
# se dice tal cual («te has pasado de 40 g de hidratos»), no se deja en cero.
#
# Los macros son los de la ETIQUETA (`macros_reales`), calculados al añadir y guardados en
# el propio extra: un donut que no está en el método no tiene macros «efectivos» que valgan,
# y lo que hace falta saber es lo que se ha comido de verdad.


@router.post("/{fecha}/extras")
async def anadir_extra(fecha: str, data: dict, user = Depends(get_current_user)):
    """Apuntar un extra del día: un alimento del catálogo y cuánto ha sido."""
    _validar_fecha(fecha)
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Cuerpo inválido")

    # El id puede llegar como número o como texto (según la puerta por la que entre).
    alimento_id = data.get("alimento_id")
    candidatos = [alimento_id]
    if isinstance(alimento_id, str) and alimento_id.lstrip("-").isdigit():
        candidatos.append(int(alimento_id))
    food = None
    if alimento_id is not None:
        food = await db.foods.find_one({"id": {"$in": candidatos}}, {"_id": 0})
    if not food:
        raise HTTPException(status_code=404, detail="Ese alimento no está en el catálogo.")

    # La cantidad llega en gramos o, en los alimentos por unidades, en unidades: la ración
    # de la ficha dice cuánto pesa una, y aquí se pasa a gramos y no se vuelve a pensar.
    import math as _math
    racion = float(food.get("racion") or 100) or 100.0
    cantidad = data.get("cantidad_g")
    if cantidad is None and data.get("unidades") is not None:
        try:
            cantidad = float(data["unidades"]) * racion
        except (TypeError, ValueError):
            cantidad = None
    try:
        cantidad = float(cantidad)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Dime cuánto ha sido, en gramos o en unidades.")
    if not _math.isfinite(cantidad) or cantidad <= 0 or cantidad > 5000:
        raise HTTPException(status_code=400, detail="Esa cantidad no puede ser. Revísala.")

    extra = {
        "id": str(uuid.uuid4()),
        "alimento_id": food["id"],
        "nombre": food.get("nombre") or "?",
        "cantidad_g": round(cantidad, 1),
        # «2 ud (126 g)» en los de unidades, «40 g» en el resto: lo mismo que ve en su dieta.
        "cantidad_texto": _para_ver.cantidad_de(
            {"alimento_id": food["id"], "cantidad_g": cantidad}, {food["id"]: food}),
        "macros": macros_reales(food, cantidad),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    # Upsert del día si no existe, como la casilla por comida: el extra de un día sin
    # dieta montada también cuenta.
    await db.diets.update_one(
        {"user_id": user["id"], "fecha": fecha},
        {"$push": {"extras": extra},
         "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"fecha": fecha, "extra": extra}


@router.delete("/{fecha}/extras/{extra_id}")
async def quitar_extra(fecha: str, extra_id: str, user = Depends(get_current_user)):
    """Quitar un extra apuntado ese día."""
    _validar_fecha(fecha)
    # El filtro exige que el extra ESTÉ: sin esto, el `$set` de updated_at contaría como
    # modificación y borrar dos veces diría que borró las dos.
    res = await db.diets.update_one(
        {"user_id": user["id"], "fecha": fecha, "extras.id": extra_id},
        {"$pull": {"extras": {"id": extra_id}},
         "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Ese extra ya no está apuntado.")
    return {"fecha": fecha, "id": extra_id}


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

    # AVISAR ANTES DE SUSTITUIR (caso 30 de los 85; punto 14 del doc del 23-08): copiar
    # encima de un día con comidas se las llevaba por delante sin decir nada. Sin la
    # marca `sobreescribir`, un 409 con lo que hay; la pantalla pregunta y repite con
    # ella. La marca y no un simple confirm del front: cualquier otra puerta a esta
    # ruta (el chat, un script) tropieza con el mismo aviso.
    if not data.get("sobreescribir"):
        destino = await db.diets.find_one(
            {"user_id": user["id"], "fecha": target_date}, {"_id": 0, "comidas": 1})
        ocupadas = sorted(k for k, c in ((destino or {}).get("comidas") or {}).items()
                          if (c or {}).get("alimentos"))
        if ocupadas:
            raise HTTPException(status_code=409, detail={
                "ocupada": True, "comidas": ocupadas,
                "mensaje": "Ese día ya tiene comidas guardadas. Copiar encima las sustituye."})

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


async def _reparto_del_dia(fecha: str, diet: Optional[dict], user: dict) -> Optional[dict]:
    """EL OBJETIVO DEL DÍA, RESUELTO AQUÍ Y PARA TODOS.

    Nutrición no enseña `macros_snapshot.P_total`: enseña ese total menos el perientreno, que
    lleva su cuenta aparte, y lo saca del reparto VIVO de ese día (`/calculator/distribute`),
    no del snapshot guardado -- que puede ser de cuando el día era de entreno y ahora es de
    descanso. Inicio tiraba del snapshot a secas y por eso las dos pantallas decían cosas
    distintas del mismo día: 235 arriba, 225 en Nutrición.

    Se resuelve en el servidor para que haya UNA sola forma de calcularlo. La configuración
    es la del día si está guardada y, si no, la que el cliente tiene puesta -- la misma
    precedencia que aplica Nutrición al abrir la pantalla.

    Devuelve None si no se puede saber (cliente sin macros, perfil a medias): un objetivo
    inventado es peor que no dar ninguno, y quien lo pinta ya sabe vivir sin él.
    """
    from routes.calculator import distribute_macros

    if diet:
        config = {
            "tipo_dia": diet.get("tipo_dia") or "entrenamiento",
            "num_comidas": diet.get("num_comidas") or 4,
            # `?? 1` y no `or 1`: el 0 es "en ayunas" y es una respuesta, no un vacío.
            "momento_entreno": diet.get("momento_entreno") if diet.get("momento_entreno") is not None else 1,
            "opcion_peri": diet.get("opcion_peri") or "intra_post",
        }
    else:
        perfil = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
        num_comidas = perfil.get("diet_num_comidas")
        if num_comidas is None:
            num_comidas = 1 if perfil.get("single_meal_mode") else 4
        config = {
            # Sin día guardado, el tipo de día todavía no lo ha dicho nadie: Nutrición abre
            # en entreno (y marca el selector para que lo diga), y aquí se hace igual.
            "tipo_dia": "entrenamiento",
            "num_comidas": num_comidas,
            "momento_entreno": perfil.get("diet_momento_entreno", 1),
            "opcion_peri": perfil.get("diet_opcion_peri") or "intra_post",
        }

    try:
        reparto = await distribute_macros({
            "fecha": fecha,
            **config,
            "single_meal": config["num_comidas"] == 1,
        }, user)
    except HTTPException:
        return None                      # sin macros asignados todavía
    except Exception as e:               # noqa: BLE001 - el día se sirve igual
        logging.getLogger("uvicorn.error").warning(
            "no se pudo resolver el objetivo del día %s: %s", fecha, e)
        return None

    return reparto


async def _objetivo_comidas_del_dia(fecha: str, diet: Optional[dict], user: dict) -> Optional[dict]:
    """El objetivo del día (P/H/G totales de las comidas, sin el peri). Ver arriba."""
    reparto = await _reparto_del_dia(fecha, diet, user)
    return objetivo_de_las_comidas(reparto) if reparto else None


@router.get("/{fecha}")
async def get_diet(fecha: str, user = Depends(get_current_user)):
    """Obtener la dieta guardada para una fecha."""
    diet = await db.diets.find_one(
        {"user_id": user["id"], "fecha": fecha},
        {"_id": 0}
    )
    # `objetivo_comidas` viaja siempre, haya día guardado o no: es lo que tiene que enseñar
    # cualquier pantalla que hable de los macros de ese día (Inicio, T1).
    objetivo = await _objetivo_comidas_del_dia(fecha, diet, user)

    if not diet:
        return {"fecha": fecha, "exists": False, "objetivo_comidas": objetivo,
                "servido_comidas": {"P": 0.0, "H": 0.0, "G": 0.0}}

    await _adjuntar_urls(diet)
    diet["exists"] = True
    diet["objetivo_comidas"] = objetivo
    diet["servido_comidas"] = await _servido_de_las_comidas(diet)
    return diet


# Las comidas que NO entran en el presupuesto del día: el perientreno lleva su cuenta
# aparte y `objetivo_comidas` ya lo ha descontado.
_PERI = ("Intra", "Post")


async def _servido_de_las_comidas(diet: dict, fichas: Optional[dict] = None) -> dict:
    """Lo que suman las comidas regulares de este día, YA CALIBRADO.

    POR QUÉ LO CUENTA EL SERVIDOR (punto 3 del documento del 17-08).

    Inicio y Nutrición daban números distintos del mismo día. No era un redondeo: era que
    cada una lo sacaba de un sitio. Nutrición pide la calibración progresiva al cargar y
    pinta lo que le devuelve; Inicio sumaba el campo `macros_efectivos` tal y como estuviera
    guardado en la dieta. Y ese campo no siempre está: medido en producción el 17-08, en el
    día 2026-07-05 los diez alimentos guardados no lo tenían, así que Nutrición decía «Ya
    está · de 180» de proteína y la misma jornada en Inicio habría salido «Te faltan 180».

    Con esto el servidor lo cuenta una vez, con la misma función que usa el chat
    (`calibracion_dia.calibrar_dia`), y las pantallas solo pintan. Una fuente, un número.
    """
    from calibracion_dia import calibrar_dia

    comidas = diet.get("comidas") or {}
    # Vacío por si acaso: sin alimentos no hay nada que calibrar y `calibrar_dia` no
    # tiene por qué recibir un día sin comidas.
    if not comidas:
        return {"P": 0.0, "H": 0.0, "G": 0.0}

    # El orden importa: la calibración de una comida depende del acumulado de las
    # anteriores, así que se recorre en el orden cronológico del día.
    orden = [k for k in ("C1", "Intra", "Post", "C2", "C3", "C4") if k in comidas]
    orden += [k for k in comidas if k not in orden]

    NEUTRO = {"categorias": "", "proteinas": 0, "hidratos": 0, "grasas": 0, "racion": 100}
    # Los alimentos guardados llevan el id, no la ficha: hay que traerlas del catálogo o
    # la calibración no sabe de qué bloque es cada uno. Quien ya tenga el catálogo puede
    # pasarlo en `fichas` (Mi semana lo trae UNA vez para los siete días).
    if fichas is None:
        ids = {a.get("alimento_id") for k in orden for a in (comidas.get(k, {}).get("alimentos") or [])
               if a.get("alimento_id") is not None}
        fichas = {}
        if ids:
            async for f in db.foods.find({"id": {"$in": list(ids)}}, {"_id": 0}):
                fichas[f.get("id")] = f

    meals = []
    for k in orden:
        fila = [(fichas.get(a.get("alimento_id")) or NEUTRO,
                 float(a.get("cantidad_g") or a.get("cantidad") or 0))
                for a in (comidas.get(k, {}).get("alimentos") or [])]
        meals.append((k, fila))

    try:
        macros_dia, _ = calibrar_dia(meals)
    except Exception as e:                # noqa: BLE001 - el día se sirve igual
        logging.getLogger("uvicorn.error").warning(
            "no se pudo calibrar el día %s: %s", diet.get("fecha"), e)
        return {"P": 0.0, "H": 0.0, "G": 0.0}

    total = {"P": 0.0, "H": 0.0, "G": 0.0}
    for k in orden:
        if k in _PERI:
            continue
        for m in macros_dia.get(k, []):
            total["P"] += m.get("P", 0) or 0
            total["H"] += m.get("H", 0) or 0
            total["G"] += m.get("G", 0) or 0
    return {k: round(v, 1) for k, v in total.items()}

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
