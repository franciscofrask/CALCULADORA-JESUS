"""
Ajustes globales de la app: db.app_settings, UN solo documento.

Nacen del doc 16-08: "que cada pantalla nueva se pueda apagar desde el panel sin
desplegar, por si algo no está fino". Hasta ahora apagar algo para todos era una
constante en el código y un deploy (así se apagó la Rutina el 19-07); esto es el
interruptor de verdad.

Dos cosas viven aquí:
  - `pantallas`: los interruptores de las pantallas nuevas del doc. PANTALLAS es la
    lista conocida con su valor por defecto; el documento de la base solo guarda lo
    que el panel haya tocado, así que añadir un interruptor nuevo es añadirlo al
    diccionario y ya tiene valor en todos los entornos.
  - `frase_del_dia`: la frase de Inicio (T1). La escribe el panel, es la misma para
    todos, y si un día no hay nueva se queda la del día anterior (por eso se guarda
    con su fecha: Inicio decide si la enseña con o sin estreno).
  - `frases_rotacion`: el repertorio que ROTA DÍA A DÍA (26-08). La cola y el panel se
    quedan para poner una frase concreta un día concreto; la rotación es lo que hay el
    resto de los días, y no se agota nunca: se elige por la fecha, así que el mismo día
    da siempre la misma frase y todos los clientes ven la misma.

El orden de mando para saber qué frase se enseña hoy:
    frase puesta para HOY (panel o cola vencida) > la rotación de hoy > la última que
    hubo. El hueco vacío es lo único que no puede pasar (punto 103 del 25-08).
"""
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from core.database import db
from core.contexto_pruebas import usuario_actual
from core.security import get_admin_only_user, get_current_user
from core.tiempo import ahora_madrid

DOC_ID = "app"

# Los interruptores y su valor por defecto. Apagados hasta que cada tarea del doc
# 16-08 esté hecha y probada; `t2_suplementos` nace encendido porque esa pantalla ya
# existía y estaba en producción.
PANTALLAS = {
    "frase_del_dia": False,     # T1 · la frase en Inicio
    "t1_inicio_nuevo": False,   # T1 · el Inicio nuevo (Lo que toca hoy / Pendiente)
    "t2_suplementos": True,     # T2 · la pantalla de suplementos del cliente
    "t3_entreno": False,        # T3 · rutina visible + registro de sesión
    "t4_cierre_nuevo": False,   # T4 · el "¿Cómo fuiste hoy?" nuevo
    "t5_diario": False,         # T5 · el Diario en Seguimiento
    "t6_evolucion": False,      # T6 · Evolución completa (medidas + fotos) en cliente
    # T10 · los avisos del doc. Encendido de fábrica desde el bloque 10 del 19-08: la
    # tabla está completa (los dos de entrega, los once diseñados y las cuatro reglas),
    # así que el interruptor queda solo como freno de emergencia.
    "t10_avisos_nuevos": True,
    # P59 del doc 23-08: los avisos del reporte salen por CORREO, sin esperar a que el
    # cliente entre («el que no entra, no se entera» explicaba el 33 contra 1). NACE
    # APAGADO a propósito: encenderlo en prod es mandar correos de verdad a todos los
    # clientes con reporte pendiente, y eso lo decide Francisco desde el panel, no un
    # deploy. La pasada vive en core/correo_avisos.py.
    "correos_avisos": False,
}

router = APIRouter(tags=["settings"])

# SOLO ADMINISTRADORES: apagar una pantalla aquí se la quita a TODOS los clientes a la vez,
# y la frase del día la leen todos. Va con el mismo candado que el catálogo de planes, que
# es donde se edita.
admin_router = APIRouter(prefix="/admin/settings", tags=["settings"])


def _mezclar_pantallas(guardadas: Optional[Dict[str, Any]]) -> Dict[str, bool]:
    """Los defaults del código con lo tocado en el panel por encima. Solo claves
    conocidas: una clave vieja que ya no exista en PANTALLAS deja de pintarse sola."""
    tocadas = guardadas or {}
    return {clave: bool(tocadas.get(clave, defecto)) for clave, defecto in PANTALLAS.items()}


def _aplicar_modo_pruebas(pantallas: Dict[str, bool], frase: Any) -> tuple[Dict[str, bool], Any]:
    """MODO PRUEBAS POR CUENTA: si la petición viene de una cuenta marcada `es_pruebas`,
    sus anulaciones (`overrides_pantallas` y `override_frase`) pisan lo global SOLO para
    ella. Una cuenta normal no tiene marca y ve siempre lo global; nadie más se entera.

    Devuelve las pantallas y la frase ya con las anulaciones aplicadas (o tal cual si no
    hay cuenta de pruebas en esta petición)."""
    u = usuario_actual()
    if not u or not u.get("es_pruebas"):
        return pantallas, frase
    ov = u.get("overrides_pantallas") or {}
    if isinstance(ov, dict):
        pantallas = {**pantallas,
                     **{k: bool(v) for k, v in ov.items() if k in PANTALLAS}}
    fr = (u.get("override_frase") or "").strip()
    if fr:
        frase = {"texto": fr,
                 "fecha": ahora_madrid().date().isoformat(),
                 "puesta_por": "mis-pruebas"}
    return pantallas, frase


def _normalizar_rotacion(rotacion: Any) -> list[str]:
    """El repertorio como lista de textos limpios. Acepta los dos formatos con los que
    puede venir guardado -- textos pelados o diccionarios con `texto` -- y tira lo vacío,
    que si no correría el turno de todos los días siguientes."""
    textos = []
    for f in (rotacion or []):
        texto = f if isinstance(f, str) else (f or {}).get("texto")
        texto = str(texto or "").strip()
        if texto:
            textos.append(texto)
    return textos


def _frase_por_rotacion(rotacion: Any, dia: date) -> Optional[Dict[str, Any]]:
    """La frase que le toca a un día concreto del repertorio que rota.

    Se elige por la fecha, no por un contador guardado: así no hay estado que
    desincronizar, no hace falta escribir nada al leer, y dos peticiones del mismo día
    dan siempre la misma frase (para todos los clientes, que es la gracia)."""
    textos = _normalizar_rotacion(rotacion)
    if not textos:
        return None
    return {
        "texto": textos[dia.toordinal() % len(textos)],
        "fecha": dia.isoformat(),
        "puesta_por": "rotacion",
    }


async def ajustes_app(con_overrides: bool = True) -> Dict[str, Any]:
    """Los ajustes vivos, para backend y para servir al front.

    `con_overrides=True` (por defecto) aplica el modo pruebas de la cuenta que hace la
    petición. El panel global de admin lo llama con `False` para ver y editar SIEMPRE lo
    global, nunca la vista personal de nadie."""
    doc = await db.app_settings.find_one({"id": DOC_ID}, {"_id": 0}) or {}

    # La cola de frases programadas (bloque 11 del 19-08): si a alguna le ha llegado su
    # día, pasa a ser LA frase y sale de la cola. Se resuelve al leer, sin cron, igual
    # que los avisos.
    frase = doc.get("frase_del_dia")
    cola = doc.get("frases_programadas") or []
    dia = ahora_madrid().date()
    hoy = dia.isoformat()
    vencidas = [f for f in cola if f.get("fecha") and f["fecha"] <= hoy]
    if vencidas:
        frase = max(vencidas, key=lambda f: f["fecha"])
        pendientes = [f for f in cola if f.get("fecha", "") > hoy]
        await db.app_settings.update_one(
            {"id": DOC_ID},
            {"$set": {"frase_del_dia": frase, "frases_programadas": pendientes}})
        cola = pendientes

    # LA ROTACIÓN, cuando nadie ha puesto frase PARA HOY. Se calcula, no se guarda: en la
    # base sigue estando la última frase del panel, que es la red de abajo del todo si un
    # día no hubiera repertorio. Sin esto, la cola se vaciaba y el bloque desaparecía.
    if not (frase and frase.get("fecha") == hoy):
        de_rotacion = _frase_por_rotacion(doc.get("frases_rotacion"), dia)
        if de_rotacion:
            frase = de_rotacion

    pantallas = _mezclar_pantallas(doc.get("pantallas"))
    if con_overrides:
        pantallas, frase = _aplicar_modo_pruebas(pantallas, frase)

    return {
        "pantallas": pantallas,
        "frase_del_dia": frase,
        "frases_programadas": cola,
        # Cuántas frases hay rotando. El texto no viaja entero: al panel le basta el
        # número para saber si el repertorio está cargado, y al cliente no le hace falta.
        "frases_en_rotacion": len(_normalizar_rotacion(doc.get("frases_rotacion"))),
    }


async def pantalla_activa(nombre: str) -> bool:
    """El cerrojo que usan las rutas del backend. Si la base no contesta, manda el
    default del código: quedarse sin base no puede apagar lo que estaba encendido."""
    try:
        ajustes = await ajustes_app()
        return bool(ajustes["pantallas"].get(nombre, PANTALLAS.get(nombre, False)))
    except Exception:
        return bool(PANTALLAS.get(nombre, False))


@router.get("/settings/app")
async def get_app_settings(user=Depends(get_current_user)):
    """Lo que necesita el front al arrancar: interruptores y frase del día."""
    return await ajustes_app()


@admin_router.get("")
async def get_admin_settings(admin=Depends(get_admin_only_user)):
    # El panel global edita lo de TODOS: siempre lo global, sin la vista personal de nadie.
    return await ajustes_app(con_overrides=False)


@router.put("/settings/mis-pruebas")
async def guardar_mis_pruebas(payload: Dict[str, Any] = Body(...), user=Depends(get_current_user)):
    """MODO PRUEBAS POR CUENTA (solo cuentas marcadas `es_pruebas`): guarda las anulaciones
    de los interruptores y, opcional, una frase del día propia. Valen SOLO para esta cuenta
    y no tocan lo que ven los demás. Un typo en el nombre de una pantalla se ignora."""
    if not user.get("es_pruebas"):
        raise HTTPException(status_code=403, detail="Esta cuenta no tiene modo pruebas.")

    cambios: Dict[str, Any] = {}

    pantallas = payload.get("pantallas")
    if isinstance(pantallas, dict):
        # Fusiona sobre lo que ya tuviera: cada botón manda su clave sin borrar el resto.
        overrides = dict(user.get("overrides_pantallas") or {})
        for clave, valor in pantallas.items():
            if clave in PANTALLAS:
                overrides[clave] = bool(valor)
        cambios["overrides_pantallas"] = overrides

    if "frase" in payload:
        cambios["override_frase"] = str(payload.get("frase") or "").strip()

    if cambios:
        await db.users.update_one({"id": user["id"]}, {"$set": cambios})
        # Que la vista de ESTA petición ya refleje lo recién guardado.
        user.update(cambios)

    return await ajustes_app()


@router.delete("/settings/mis-pruebas")
async def limpiar_mis_pruebas(user=Depends(get_current_user)):
    """Quita todas las anulaciones de esta cuenta: vuelve a ver lo global, como todos."""
    if not user.get("es_pruebas"):
        raise HTTPException(status_code=403, detail="Esta cuenta no tiene modo pruebas.")
    await db.users.update_one(
        {"id": user["id"]},
        {"$unset": {"overrides_pantallas": "", "override_frase": ""}})
    user.pop("overrides_pantallas", None)
    user.pop("override_frase", None)
    return await ajustes_app()


# ===== ESCENARIOS DE LA PROPIA CUENTA (Fase 2, solo cuentas `es_pruebas`) =====
# Poner la cuenta del que prueba en un estado concreto (caducado, por vencer, sin plan,
# cuestionario sin completar, otro plan...) para recorrer esas pantallas SIN crear clientes
# demo. Es SU perfil, así que la primera vez se guarda una foto de los campos que se tocan
# (`pruebas_snapshot`) y «Restaurar mi cuenta» lo deja como estaba. Los estados se derivan
# al leer el perfil (acceso, renovación...), así que basta con fijar los campos crudos.

# Los únicos campos que un escenario toca (y que, por tanto, se fotografían y se restauran).
_CAMPOS_ESCENARIO = [
    "plan", "status", "checkout_status", "current_period_end", "fin_de_ciclo",
    "arranque_lunes", "access_until", "subscription_status", "questionnaire_completed",
    "ajuste_macros_completado",
]
_AUSENTE = "__ausente__"  # en la foto: el campo no existía y al restaurar hay que quitarlo

_PLANES_ESCENARIO = {"nivel1", "nivel2", "nivel3", "elm", "gold", "silver", "bronze", "mantenimiento"}


def _campos_de_escenario(nombre: str, plan: Optional[str]):
    """El juego de valores que deja la cuenta en el estado pedido; None si no se reconoce.

    CADA ESCENARIO ES AUTÓNOMO: parte de una base «activo limpio» y encima pone lo suyo, así
    no arrastra residuos del escenario anterior. Las fechas, en el día de España. El plan de
    la base se deja como está (no se toca salvo en sin_plan/cambiar_plan)."""
    hoy = ahora_madrid().date()
    def iso(dias):
        return datetime.combine(hoy + timedelta(days=dias), datetime.min.time(),
                                tzinfo=timezone.utc).isoformat()
    # Base común: cuenta activa, al día, con el cuestionario hecho y sin bloqueos de fecha.
    base = {"status": "activo", "subscription_status": "active", "checkout_status": "completed",
            "questionnaire_completed": True,
            "current_period_end": None, "fin_de_ciclo": None, "access_until": None}
    if nombre == "activo":
        return base
    if nombre == "caducado":
        # Con suscripción activa la fecha no basta: un `status` bloqueado corta el acceso antes.
        return {**base, "status": "cancelado"}
    if nombre == "sin_plan":
        return {**base, "plan": ""}
    if nombre == "pago_a_medias":
        return {**base, "status": "pendiente_pago", "checkout_status": "draft"}
    if nombre == "cuestionario_inicial":
        return {**base, "questionnaire_completed": False}
    if nombre == "ajuste_pendiente":
        # El cuestionario está hecho, pero el ajuste no, y nadie le ha puesto los macros a mano.
        # Lo de "nadie a mano" (macros_puestos_por_alguien) se fuerza al leer el perfil.
        return {**base, "questionnaire_completed": True, "ajuste_macros_completado": False}
    if nombre == "ventana_grasa":
        # Cuenta activa; que la ventana de las 12 semanas salga se fuerza al leer el perfil.
        return {**base}
    if nombre == "por_vencer":
        # A CINCO DÍAS, no a diez: el aviso «Tu ciclo acaba en una semana» solo sale a
        # siete días o menos del fin (regla 8a de avisos_cliente). Con diez, el escenario
        # caía FUERA de la ventana del aviso que se pone para ver, y la pantalla de
        # renovación salía sin que llegara ni una notificación (Francisco, 24-08).
        return {**base, "fin_de_ciclo": iso(5), "current_period_end": iso(5), "arranque_lunes": iso(-79)}
    if nombre == "cambiar_plan":
        destino = (plan or "").strip()
        return {**base, "plan": destino} if destino in _PLANES_ESCENARIO else None
    if nombre == "nuevo_con_plan":
        # Recién comprado: tiene el plan y está activo, pero aún no ha hecho el cuestionario
        # ni tiene el ajuste, así que la app le fuerza el onboarding como a un recién llegado.
        destino = (plan or "").strip()
        return ({**base, "plan": destino,
                 "questionnaire_completed": False, "ajuste_macros_completado": False}
                if destino in _PLANES_ESCENARIO else None)
    return None


async def _perfil_propio(user):
    p = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Tu cuenta no tiene ficha de cliente.")
    return p


@router.post("/settings/mis-pruebas/escenario")
async def poner_escenario(payload: Dict[str, Any] = Body(...), user=Depends(get_current_user)):
    if not user.get("es_pruebas"):
        raise HTTPException(status_code=403, detail="Esta cuenta no tiene modo pruebas.")
    nombre = str(payload.get("escenario") or "").strip()
    cambios = _campos_de_escenario(nombre, payload.get("plan"))
    if cambios is None:
        raise HTTPException(status_code=400, detail="Escenario no reconocido.")

    perfil = await _perfil_propio(user)
    set_doc: Dict[str, Any] = {campo: valor for campo, valor in cambios.items() if campo in _CAMPOS_ESCENARIO}
    # La foto, solo la primera vez: no pisar el estado real con otro de prueba.
    foto = perfil.get("pruebas_snapshot")
    if not foto:
        foto = {c: perfil.get(c, _AUSENTE) for c in _CAMPOS_ESCENARIO}
        set_doc["pruebas_snapshot"] = foto
    # EL PLAN Y EL ESCENARIO SON DOS EJES DISTINTOS: «gold» y «por vencer» se combinan.
    # Un escenario que no fija plan RESPETA EL QUE HAYA PUESTO, así se puede elegir el plan
    # con «Aplicar plan» y luego ponerle el estado encima. Solo se recupera el plan de la
    # foto cuando la cuenta se ha quedado SIN plan (viene de «sin plan»), que era el fallo
    # del 22-08: entonces todos los escenarios siguientes salían como «sin plan».
    if "plan" not in cambios:
        actual = (perfil.get("plan") or "").strip()
        original = foto.get("plan")
        if actual:
            set_doc["plan"] = perfil.get("plan")
        elif original not in (None, _AUSENTE):
            set_doc["plan"] = original
    set_doc["pruebas_escenario"] = nombre
    await db.client_profiles.update_one({"user_id": user["id"]}, {"$set": set_doc})

    # Y SE LIMPIA LA CAMPANITA, que si no el estado nuevo se queda mudo. Los avisos del
    # cliente van topados a UNO AL DÍA (doc 19-08): en cuanto le ha nacido cualquiera hoy,
    # el del estado que acabas de poner no se crea y no lo ves hasta mañana. En una cuenta
    # de laboratorio eso hace inútil el panel, así que poner un escenario borra SUS avisos
    # de cliente (falsos todos) y la siguiente pantalla los vuelve a evaluar desde cero.
    # Solo los del cliente: los del equipo son de trabajo de verdad y no se tocan.
    from routes.notifications import SOLO_DEL_CLIENTE   # aquí: notifications importa esto
    await db.notifications.delete_many({"user_id": user["id"], **SOLO_DEL_CLIENTE})
    return {"escenario": nombre}


@router.post("/settings/mis-pruebas/restaurar")
async def restaurar_cuenta(user=Depends(get_current_user)):
    if not user.get("es_pruebas"):
        raise HTTPException(status_code=403, detail="Esta cuenta no tiene modo pruebas.")
    perfil = await _perfil_propio(user)
    foto = perfil.get("pruebas_snapshot")
    if not foto:
        return {"escenario": None}
    set_doc: Dict[str, Any] = {}
    unset_doc: Dict[str, Any] = {"pruebas_snapshot": "", "pruebas_escenario": ""}
    for campo, valor in foto.items():
        if valor == _AUSENTE:
            unset_doc[campo] = ""
        else:
            set_doc[campo] = valor
    op: Dict[str, Any] = {"$unset": unset_doc}
    if set_doc:
        op["$set"] = set_doc
    await db.client_profiles.update_one({"user_id": user["id"]}, op)
    # Los avisos que nacieron de los estados de prueba eran de mentira: se van con ellos.
    from routes.notifications import SOLO_DEL_CLIENTE
    await db.notifications.delete_many({"user_id": user["id"], **SOLO_DEL_CLIENTE})
    return {"escenario": None}


@admin_router.put("")
async def update_admin_settings(payload: Dict[str, Any] = Body(...), admin=Depends(get_admin_only_user)):
    """Guarda interruptores y/o frase del día. Solo claves conocidas: un typo en el
    nombre de una pantalla no crea un interruptor fantasma que nadie lee."""
    cambios: Dict[str, Any] = {}

    pantallas = payload.get("pantallas")
    if isinstance(pantallas, dict):
        for clave, valor in pantallas.items():
            if clave in PANTALLAS:
                cambios[f"pantallas.{clave}"] = bool(valor)

    if "frase_del_dia" in payload:
        pedido = payload.get("frase_del_dia") or {}
        texto = str(pedido.get("texto") or "").strip()
        if texto:
            # PROGRAMABLE CON UNA SEMANA DE ANTELACIÓN (bloque 11 del doc 19-08). Sin
            # fecha (o con la de hoy) la frase entra ya, como siempre; con una fecha por
            # delante -- hasta 7 días -- se guarda en la cola y saldrá su día. La fecha
            # es la de España: la frase «de hoy» es la del día del cliente.
            hoy = ahora_madrid().date()
            fecha = str(pedido.get("fecha") or "").strip() or hoy.isoformat()
            try:
                d = date.fromisoformat(fecha)
            except ValueError:
                raise HTTPException(status_code=400, detail="La fecha de la frase no se entiende.")
            if d < hoy or (d - hoy).days > 7:
                raise HTTPException(
                    status_code=400,
                    detail="La frase se puede programar de hoy a una semana vista, no más allá.")
            frase = {"texto": texto, "fecha": d.isoformat(), "puesta_por": admin.get("id")}
            if d == hoy:
                cambios["frase_del_dia"] = frase
            else:
                doc = await db.app_settings.find_one({"id": DOC_ID}, {"_id": 0, "frases_programadas": 1}) or {}
                cola = [f for f in (doc.get("frases_programadas") or []) if f.get("fecha") != frase["fecha"]]
                cambios["frases_programadas"] = sorted(cola + [frase], key=lambda f: f["fecha"])

    if cambios:
        await db.app_settings.update_one(
            {"id": DOC_ID},
            {"$set": {**cambios,
                      "updated_at": ahora_madrid().astimezone(timezone.utc).isoformat(),
                      "updated_by": admin.get("id")}},
            upsert=True,
        )
    return await ajustes_app()
