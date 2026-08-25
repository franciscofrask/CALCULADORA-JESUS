"""
Check-ins de seguimiento (portado de calmajp).

Tres niveles:
  - daily:   ánimo/energía/entrenó/nutrición (10 segundos)
  - weekly:  peso + cumplimiento + sueño + estrés
  - monthly: peso + %graso + medidas + progreso/retos

Incluye health score (rojo/amarillo/verde) y fotos de progreso (binario en
colección dedicada `client_photos` para no inflar los documentos de check-in).
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query, Response
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
import uuid

from bson import Binary

from core.database import db
from core.fotos import listar_fotos_de, abrir_foto, es_ref_calma
from core import fotos as fotos_core
from core.security import get_current_user, get_admin_user, assert_client_access
from core.plan_access import plan_grants_feature
from core.series_cliente import (
    DIAS_ATRAS_PARA_UN_PESAJE, actual as actual_de_serie, anotar_peso, anotar_grasa)
from core.tiempo import hoy_madrid
from models.common import CheckInCreate, CheckInResponse

router = APIRouter(tags=["checkins"])

VALID_CHECKIN_TYPES = {"daily", "weekly", "monthly"}


async def _assert_staff_client_access(user: dict, client_id: str) -> dict:
    """Carga el perfil del cliente por su id y aplica la regla de acceso staff
    (admin = todos; trainer = solo asignados). Devuelve el perfil."""
    profile = await db.client_profiles.find_one({"id": client_id}, {"_id": 0})
    assert_client_access(user, profile)
    return profile


async def _assert_staff_photo_access(user: dict, owner_user_id: str) -> None:
    """Un trainer solo ve fotos de SUS clientes; el admin, de todos."""
    if user.get("role") == "admin":
        return
    profile = await db.client_profiles.find_one({"user_id": owner_user_id}, {"_id": 0, "trainer_id": 1})
    assert_client_access(user, profile)


# ==================== HEALTH SCORE ====================

def _compute_health_score(checkins: List[dict], profile: dict) -> dict:
    """Score rojo/amarillo/verde a partir de los check-ins recientes y el estado del perfil.

    Reglas:
      - red:    sin check-in 14+ días, baja_automatica, o adherencia reciente < 50%
      - yellow: sin check-in 7-14 días, pago past_due, o adherencia 50-75%
      - green:  actividad reciente y adherencia >= 75%
    """
    now = datetime.now(timezone.utc)
    factors: list[str] = []
    level = "green"

    last_checkin_date: Optional[datetime] = None
    for c in checkins:
        try:
            dt = datetime.fromisoformat(c["created_at"].replace("Z", "+00:00"))
            if last_checkin_date is None or dt > last_checkin_date:
                last_checkin_date = dt
        except Exception:
            continue

    days_since = (now - last_checkin_date).days if last_checkin_date else 999

    if profile.get("status") == "baja_automatica":
        level = "red"
        factors.append("Baja automática por fallos de pago")
    elif last_checkin_date is None:
        level = "red"
        factors.append("Sin ningún check-in registrado todavía")
    elif days_since >= 14:
        level = "red"
        factors.append(f"Sin check-in hace {days_since} días")
    elif days_since >= 7:
        level = "yellow"
        factors.append(f"Último check-in hace {days_since} días")

    weekly = [c for c in checkins if c.get("type") == "weekly"][:4]
    if weekly:
        train_vals = [c.get("training_compliance") for c in weekly if c.get("training_compliance") is not None]
        nutr_vals = [c.get("nutrition_compliance") for c in weekly if c.get("nutrition_compliance") is not None]
        all_vals = train_vals + nutr_vals
        if all_vals:
            avg = sum(all_vals) / len(all_vals)
            if avg < 50:
                level = "red"
                factors.append(f"Adherencia media baja ({avg:.0f}%)")
            elif avg < 75 and level != "red":
                level = "yellow"
                factors.append(f"Adherencia media regular ({avg:.0f}%)")

    if profile.get("subscription_status") == "past_due" and level == "green":
        level = "yellow"
        factors.append("Pago atrasado")

    if (profile.get("payment_failure_count") or 0) >= 1 and level == "green":
        level = "yellow"
        factors.append(f"{profile['payment_failure_count']} intento(s) de cobro fallido(s)")

    return {
        "score": level,
        "factors": factors,
        "last_checkin": last_checkin_date.isoformat() if last_checkin_date else None,
        "days_since_checkin": days_since if last_checkin_date else None,
    }


# ==================== CHECK-INS ====================

async def _dieta_y_entreno_del_dia(profile: dict, fecha: str) -> Dict[str, Any]:
    """Lo que ese día ya consta en la base, para no preguntárselo.

    Sustituye a las preguntas de dieta y entreno del check-in diario (documento 7.2).

    El entrenamiento NO se deduce aquí: desde T3 tiene su propia colección (`workout_logs`,
    lo que el cliente marca en /dashboard/entreno), y esa es la fuente del "entrenaste X de
    Y". `db.routines` sigue siendo el plan -- qué le toca --, no lo que hizo, y dar por
    entrenado el día que tocaba contaría entrenos que nadie ha hecho.
    """
    out: Dict[str, Any] = {}

    dieta = await db.diets.find_one(
        {"user_id": profile.get("user_id"), "fecha": fecha}, {"_id": 0, "comidas": 1}
    )
    if dieta:
        tiene_algo = any(
            (c or {}).get("alimentos") for c in (dieta.get("comidas") or {}).values()
        )
        out["nutrition_followed"] = bool(tiene_algo)

    return out


# ==================== EL CIERRE DEL DÍA (T4) ====================
#
# "Lo primero que sale es lo que no ha marcado". El orden lo manda el documento: entreno,
# suplementos y comida sin registrar. Todo se calcula AQUÍ, en un solo sitio, para que la
# pantalla solo tenga que pintar: cada pregunta condicional necesita mirar una colección
# distinta.
#
# SE FUE LA PREGUNTA DEL EXCESO DE MACROS, Y ES A PROPÓSITO (fallo 8 del repaso del 24-08).
# El cierre preguntaba «hoy te has pasado 40 g de hidratos, ¿qué pasó?» (T4 del doc 16-08).
# Al rehacer el cierre en tarjetas con las ONCE preguntas de Jesús (doc 24-08) esa caja se
# cayó de la pantalla y nadie lo escribió, pero el servidor la siguió calculando en TODAS
# las cargas de GET /checkins/hoy: `_se_ha_pasado` resolvía los macros del día y consultaba
# db.foods alimento por alimento para un dato que ya no pintaba nadie.
#
# La decisión es que NO vuelve, y por tres motivos:
#
#   - Las once preguntas del cierre son las de Jesús, y el exceso no es ninguna de ellas.
#   - La 07, «¿Se te ha escapado algo más hoy?», cubre lo mismo por el otro lado: se le
#     pregunta por lo que comió de más, no por el gramo que le sobra.
#   - Y el gramo que le sobra ya se lo dice Nutrición, en la cabecera del día y con el
#     mismo criterio (`frontend/src/lib/exceso.js`), que es donde está mirando la comida.
#
# Con ella se van `_se_ha_pasado`, `_consumido_del_dia` y `NOMBRE_MACRO`, que no los usaba
# nadie más. Lo que SÍ se queda es el campo `exceso_nota` del check-in: hay cierres viejos
# con esa nota escrita y se conservan al reeditar.

# Las comidas del día como se llaman en `db.diets` y como se le dicen al cliente. Ojo: al
# cliente NO se le dice "cena" ni "desayuno" (decisión del 09-08); su comida se llama por
# su número, que es como la ve en Nutrición. El literal del doc, "Te queda la {comida} sin
# registrar", se rellena con esta etiqueta.
ETIQUETA_COMIDA = {
    "C1": "comida 1", "C2": "comida 2", "C3": "comida 3", "C4": "comida 4",
    "Intra": "intra-entreno", "Post": "post-entreno",
}


def _orden_de_comidas(dieta: dict) -> List[str]:
    """Las comidas de ese día en el orden en que se las encuentra en Nutrición: las
    normales, y el peri metido en el momento del entreno."""
    num = int(dieta.get("num_comidas") or 4)
    base = [f"C{i}" for i in range(1, max(1, min(num, 4)) + 1)]
    peri = {"intra_post": ["Intra", "Post"], "solo_post": ["Post"],
            "solo_intra": ["Intra"]}.get(dieta.get("opcion_peri") or "", [])
    if peri:
        momento = max(0, min(int(dieta.get("momento_entreno") or 1), len(base)))
        base = base[:momento] + peri + base[momento:]
    return base


def _comidas_sin_registrar(dieta: Optional[dict]) -> List[str]:
    """TODAS las comidas del día que se han quedado vacías, en el orden en que se comen.

    Devolvía solo la última (`vacias[-1]`) porque el cierre preguntaba por una, con su
    casilla «La hice». Desde el doc 24-08 (punto 16) el cierre abre con el aviso entero,
    «Te quedan 2 comidas sin registrar · Comida 3 · Comida 4», así que hace falta la lista
    y no la cola de la lista. Si ese día no tiene dieta montada no hay nada que avisar: no
    hay nada planificado que se le haya quedado a medias.
    """
    comidas = (dieta or {}).get("comidas") or {}
    # SIN `comidas` NO HAY DIA MONTADO, y no basta con que exista el documento: desde el
    # 24-08 apuntar un extra hace `upsert` en `db.diets`, asi que un dia al que solo le
    # pusieron «dos cañas» tiene documento y ni una comida. Sin este corte, el cierre le
    # avisaria de «cuatro comidas sin registrar» de un dia que nunca planifico.
    if not comidas:
        return []
    return [k for k in _orden_de_comidas(dieta) if not (comidas.get(k) or {}).get("alimentos")]


def _dia_del_pesaje(elegida: Optional[str], dia_del_cierre: str) -> str:
    """De qué día es el peso que acaba de apuntar.

    LA CASILLA DE PESO LLEVA FECHA (doc 24-08). El peso se archivaba con el día del
    cierre, y quien se pesaba por la mañana y lo apuntaba de madrugada -- o se pesó ayer y
    lo apunta hoy -- metía el dato en el día que no era. Con la regla del peso semanal eso
    deja de ser un detalle: la media sale de la pareja de días SEGUIDOS desde el miércoles,
    y un pesaje corrido de día rompe la pareja sin que nada avise.

    LA REGLA NO SE ESCRIBE AQUÍ (fallo 7 del repaso del 24-08). Este fichero tenía su propio
    `DIAS_ATRAS_PARA_UN_PESAJE = 14` mientras `core/series_cliente.py` declaraba 30 en una
    función que no llamaba nadie y la pantalla ofrecía 8 días: tres sitios y tres números
    para la misma decisión. Ahora la regla vive donde vive la serie y este camino -- que es
    el vivo -- la usa a través de `fecha_de_pesaje_valida`, que además ya sabe decir que no
    a una fecha del futuro y a una que no es una fecha.

    El «hoy» de la regla es EL DÍA DEL CIERRE, no el del servidor: el cierre del día se
    escribe con el reloj del cliente (bloque F), y con el del servidor un cliente en América
    se comería un «esa fecha es del futuro» con su propio hoy.

    Lo que no vale, se ignora en silencio y manda el día del cierre: una fecha rara no
    puede tumbar el cierre del día de nadie.
    """
    from core.series_cliente import fecha_de_pesaje_valida

    if not elegida:
        return dia_del_cierre
    try:
        cierre = datetime.strptime(dia_del_cierre, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return dia_del_cierre
    return fecha_de_pesaje_valida(elegida, hoy=cierre) or dia_del_cierre


async def _cierre_de_hoy(client_id: str, fecha: str) -> Optional[dict]:
    """El cierre de ESE día, si ya lo hizo.

    SE BUSCA POR `dia`, NO POR EL ÚLTIMO QUE HAYA (24-08). Esto miraba el cierre más
    reciente del cliente y comparaba SU día con el pedido, y con eso el mismo día podía
    acabar con dos filas. Pasa en la frontera de medianoche, que el bloque F permite a
    propósito: el cliente en América vive todavía el día 24 mientras en España ya es el
    25, así que su cierre de las 22:00 se guarda con `dia` 24, el de otra pestaña con el
    25, y a partir de ahí el de las 22:30 del día 24 ya no encuentra al suyo -- el más
    reciente es el del 25 -- y se inserta otra vez. Dos filas del mismo día cuentan doble
    en todo lo que lea la colección. Medido en dev: paso justo al probar esto.

    Los cierres de antes del 16-08 no llevan `dia` y hay que mirarles el `created_at`, que
    va en UTC: uno de las 23:30 de Madrid está guardado con la fecha del día siguiente.
    """
    from core.tiempo import a_madrid
    del_dia = await db.checkins.find_one(
        {"client_id": client_id, "type": "daily", "dia": fecha}, {"_id": 0},
        sort=[("created_at", -1)])
    if del_dia:
        return del_dia
    ultimo = await db.checkins.find_one(
        {"client_id": client_id, "type": "daily", "dia": {"$in": [None, ""]}}, {"_id": 0},
        sort=[("created_at", -1)])
    if not ultimo:
        return None
    cuando = a_madrid(ultimo.get("created_at"))
    return ultimo if cuando and cuando.date().isoformat() == fecha else None


@router.get("/checkins/hoy")
async def cierre_del_dia_hoy(fecha: Optional[str] = Query(None), user=Depends(get_current_user)):
    """Lo que la pantalla del cierre del día necesita saber antes de preguntar nada.

    `fecha` es el día DEL RELOJ DEL CLIENTE (bloque F, 23-08): el front lo manda y aquí
    solo se valida (`dia_del_cliente`). Sin él, el día de España, que era lo de siempre:
    a un cliente fuera de España su cierre le salía con el día equivocado.
    """
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    from core.tiempo import dia_del_cliente
    fecha = dia_del_cliente(fecha)
    hecho = await _cierre_de_hoy(profile["id"], fecha)

    # ── 1 · El entreno. Solo si hoy le tocaba y no lo ha registrado.
    from routes.workout_logs import (
        dia_de_rutina, log_del_dia, tiene_rutina_puesta, titulo_del_dia)
    from routes.settings import pantalla_activa

    entreno = None
    # ¿Tiene rutina con nosotros? (P80, doc 23-08). Sin rutina el cierre le ofrece una
    # nota de entreno libre; con rutina, su entreno va por el registro de siempre y la
    # nota libre no sale, para no tener el mismo dato en dos sitios.
    #
    # EL PDF TAMBIÉN ES RUTINA (24-08). Esto miraba solo `db.routines` con status active, y
    # al cliente que tiene la suya entregada en PDF -- que es la vía real -- el cierre le
    # seguía sacando la caja «Si entrenaste por tu cuenta, apúntalo aquí», la del que no
    # tiene rutina, mientras el panel del equipo ya decía «En PDF» del mismo cliente. Se
    # pregunta con el ayudante compartido (`tiene_rutina_puesta`) y no con otra copia del
    # criterio, que es como se quedó a medias la primera vez.
    tiene_rutina = False
    if await pantalla_activa("t3_entreno"):
        rutina = await db.routines.find_one({"client_id": profile["id"], "status": "active"}, {"_id": 0})
        tiene_rutina = await tiene_rutina_puesta(profile["id"])
        dia = dia_de_rutina(rutina, fecha)
        if dia and not await log_del_dia(profile["id"], fecha):
            entreno = {"dia_rutina": titulo_del_dia(dia)}

    # ── 2 · Los suplementos. Dos condiciones, no una:
    #
    #   a) Que su PLAN incluya suplementación. Esto faltaba (punto 06 del doc 24-08): la
    #      pregunta miraba solo si había protocolo escrito, y a cuatro clientes activos
    #      con protocolo de su etapa anterior y plan sin suplementación el cierre les
    #      preguntaba todas las noches por unos suplementos que su pantalla no les deja
    #      ni ver (`require_access("suplementacion")` en routes/supplements.py). El
    #      candado del cierre es ahora el mismo que el de la pantalla.
    #   b) Que tenga protocolo VIGENTE ese día: al que no le hemos pautado nada tampoco se
    #      le pregunta si se lo ha tomado.
    suplementos = False
    if plan_grants_feature(profile.get("plan"), "suplementacion"):
        from routes.supplements import vigente_en
        proto = await db.supplement_protocols.find_one({"client_id": profile["id"]}, {"_id": 0})
        version = vigente_en((proto or {}).get("versiones") or [], fecha)
        suplementos = bool((version or {}).get("items"))

    # ── 3 y 4 · La dieta del día: las comidas que faltan y si se ha pasado de macros.
    dieta = await db.diets.find_one({"user_id": profile.get("user_id"), "fecha": fecha}, {"_id": 0})
    pendientes = _comidas_sin_registrar(dieta)

    ultimo = actual_de_serie(profile.get("pesos"))

    return {
        "fecha": fecha,
        "hecho": bool(hecho),
        "checkin": hecho,
        "entreno": entreno,
        "tiene_rutina": tiene_rutina,
        "suplementos": suplementos,
        # La LISTA entera, para el aviso de arriba del cierre («Te quedan 2 comidas sin
        # registrar · Comida 3 · Comida 4»). Con mayúscula, que es como se lee en la
        # pantalla; la etiqueta en minúscula de `comida_pendiente` iba dentro de una frase.
        "comidas_pendientes": [
            {"key": k, "etiqueta": ETIQUETA_COMIDA.get(k, "comida").capitalize()}
            for k in pendientes
        ],
        # Se queda por compatibilidad: hay cierres guardados con `comida_pendiente` y la
        # ficha del entrenador los lee. La pantalla ya no lo usa.
        "comida_pendiente": ({"key": pendientes[-1],
                              "etiqueta": ETIQUETA_COMIDA.get(pendientes[-1], "comida")}
                             if pendientes else None),
        # LA PREGUNTA DEL EXCESO DE MACROS YA NO EXISTE, Y AQUÍ TAMPOCO SE CALCULA (fallo 8
        # del repaso del 24-08). Ver la nota larga donde vivía `_se_ha_pasado`.
        "ultimo_peso": ultimo,
        # Hasta cuántos días atrás acepta el servidor que se feche un pesaje. Se manda para
        # que el desplegable de la pantalla ofrezca exactamente lo que se acepta y la regla
        # siga estando en un solo sitio (fallo 7 del 24-08).
        "peso_dias_atras": DIAS_ATRAS_PARA_UN_PESAJE,
    }


# Lo que escribe el servidor en cada guardado y NO se hereda del cierre anterior: o se
# vuelve a calcular (`nutrition_followed` sale de la dieta de ese día, así que si hoy no hay
# dieta la respuesta es que no consta, no la de ayer) o se recoloca a mano justo encima
# (`id`, `created_at`, `trainer_feedback`).
_LO_QUE_PONE_EL_SERVIDOR = {
    "_id", "id", "client_id", "dia", "created_at", "updated_at", "trainer_feedback",
    "autorrelleno", "nutrition_followed",
}

# LO QUE EL CIERRE DEL DÍA LE PREGUNTA AL CLIENTE HOY: las once de Jesús (doc 24-08) más las
# dos cajas opcionales del final, las notas y el peso con su fecha.
#
# Esta lista existe para poder distinguir dos cosas que se veían iguales desde aquí
# (fallo 9 del repaso del 24-08):
#
#   - Un campo que el formulario SÍ pregunta y que no llega: el cliente lo ha dejado en
#     blanco al reeditar, y se queda en blanco. Es la regla de P75 («el segundo envío
#     sustituye la fila»), y es la que hace que borrar una respuesta funcione.
#   - Un campo que el formulario NO pregunta y que no llega: nadie lo ha borrado, es que
#     esta pantalla no sabe que existe. Ahí borrarlo es perder un dato del cliente.
#
# Lo segundo pasaba con `comido_hoy` y `mood`, del check-in de mayo: se guardaban y al
# reeditar el día desaparecían. Se había tapado campo a campo desde la pantalla -- que
# reenvía `cena_hecha`, `comida_pendiente`, `exceso_nota` y `entreno_nota` copiados --, y
# esos cuatro se acordaron y estos dos no.
#
# Al añadir una pregunta NUEVA al cierre hay que apuntarla aquí. Si se olvida, lo único que
# pasa es que esa respuesta no se podrá dejar en blanco reeditando; nunca se pierde nada,
# que es el error que importa.
_LO_QUE_PREGUNTA_EL_CIERRE = {
    "sensaciones", "entreno_respuesta", "entreno_estrellas", "cardio", "movimiento",
    "descanso", "energy", "hunger_anxiety", "suplementos", "extras_respuesta",
    "notas", "weight", "peso_fecha",
}


# El decorador estaba pegado a la funcion de arriba, que es una ayudante interna. Con eso, la
# ruta POST /checkins registraba a `_dieta_y_entreno_del_dia`, cuyos parametros (`profile` y
# `fecha`) FastAPI tomaba por parametros de la URL: cualquier cliente que enviaba un check-in
# recibia un 422 pidiendole una `fecha` que nadie le habia preguntado. O sea, mandar un
# check-in -- diario, semanal o mensual -- no funcionaba para nadie.
@router.post("/checkins", response_model=CheckInResponse)
async def create_checkin(data: CheckInCreate, user = Depends(get_current_user)):
    if data.type not in VALID_CHECKIN_TYPES:
        raise HTTPException(status_code=400, detail=f"Tipo invalido. Usa uno de: {VALID_CHECKIN_TYPES}")
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    # EL CIERRE DEL DÍA TIENE LLAVE PROPIA, Y NO LA DE «reportes» (decisión de Jesús,
    # 24-08). Esto exigía «reportes» para los tres tipos, así que los 81 clientes de ELM,
    # Mantenimiento, Calculadora JP y Básica -- cuyo plan no vende reportes -- entraban a
    # la pantalla (la puerta de la app ya va por `cierre_dia`, ver App.js), contestaban las
    # once preguntas y al Guardar se comían un 403. La puerta de la app no vale sin la del
    # servidor. El semanal y el mensual SÍ se venden por plan y se quedan con su llave: por
    # eso son dos y no una.
    llave = "cierre_dia" if data.type == "daily" else "reportes"
    if not plan_grants_feature(profile.get("plan"), llave):
        raise HTTPException(
            status_code=403,
            detail=("Tu plan no incluye el cierre del día." if llave == "cierre_dia"
                    else "Tu plan no incluye check-ins de seguimiento."))

    # El día DEL RELOJ DEL CLIENTE (bloque F, 23-08): lo manda el front y aquí se valida.
    # Sin él, el de España (lo de siempre). `created_at` sigue siendo el instante UTC.
    from core.tiempo import dia_del_cliente
    dia = dia_del_cliente(getattr(data, "fecha", None))

    cuerpo = data.model_dump(exclude_none=True)
    cuerpo.pop("fecha", None)   # ya viaja saneado en `dia`; dos campos con el día son ruido
    checkin = {
        "id": str(uuid.uuid4()),
        "client_id": profile["id"],
        **cuerpo,
        "dia": dia,
        "trainer_feedback": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # La dieta no se pregunta: ya consta. Preguntar por algo que el sistema sabe es
    # hacerle trabajar para nada, y encima su respuesta puede contradecir al registro.
    if data.type == "daily":
        deducido = await _dieta_y_entreno_del_dia(profile, dia)
        checkin.update(deducido)
        checkin["autorrelleno"] = list(deducido.keys())

    # EL MISMO DÍA SE SUSTITUYE, NO SE DUPLICA (P75, doc 23-08). El cierre del día es una
    # foto de SU día: si lo reenvía es que lo está corrigiendo, y dos filas del mismo día
    # contarían doble en todo lo que lea la colección. Se sustituye entero -- lo que dejó
    # en blanco al editar, se queda en blanco --, conservando el id y el `created_at` del
    # primero, y el comentario del entrenador, que es suyo y no del formulario.
    previo = await _cierre_de_hoy(profile["id"], dia) if data.type == "daily" else None
    if previo:
        checkin["id"] = previo["id"]
        checkin["created_at"] = previo["created_at"]
        checkin["trainer_feedback"] = previo.get("trainer_feedback")
        checkin["updated_at"] = datetime.now(timezone.utc).isoformat()
        # LO QUE LA PANTALLA NO PREGUNTA, NO SE BORRA (fallo 9 del repaso del 24-08).
        #
        # «Se sustituye entero» sigue valiendo para las preguntas del cierre: si el cliente
        # deja una en blanco al reeditar, se queda en blanco. El agujero era otro: los campos
        # que esta pantalla ni siquiera nombra -- `comido_hoy` y `mood`, del check-in de mayo
        # -- desaparecían al reeditar el día. Medido por API: se guarda un cierre con los dos,
        # se reenvía como lo arma la pantalla, y los dos se van.
        #
        # Se había tapado campo a campo desde el front (`cena_hecha`, `comida_pendiente`,
        # `exceso_nota` y `entreno_nota` viajan copiados de `inicial`), y eso obliga a
        # acordarse uno por uno. Aquí se tapa de raíz: lo que no es una pregunta del cierre y
        # no viene en esta petición, se conserva del día anterior. Un campo huérfano nuevo
        # queda protegido sin tocar nada.
        #
        # `model_fields_set` distingue «no lo he mandado» de «lo mando en blanco», que
        # `model_dump(exclude_none=True)` deja igual de vacíos. No hace falta para las
        # preguntas -- esas nunca se heredan -- pero sí para que un huérfano se pueda vaciar
        # a propósito el día que alguien tenga que hacerlo.
        enviados = set(data.model_fields_set)
        for campo, valor in previo.items():
            if (campo in checkin or campo in enviados
                    or campo in _LO_QUE_PREGUNTA_EL_CIERRE
                    or campo in _LO_QUE_PONE_EL_SERVIDOR):
                continue
            checkin[campo] = valor
        await db.checkins.replace_one({"id": previo["id"]}, checkin)
    else:
        await db.checkins.insert_one(checkin)

    # El peso que aporta el check-in va a la SERIE con la fecha del check-in (punto 30), y
    # el peso "actual" del perfil sale de la serie. Antes se escribia suelto en el perfil,
    # y era una de las dos vias por las que la app acababa ensenando dos pesos distintos.
    #
    # BORRAR EL PESO DEL CIERRE NO BORRA EL PESAJE, Y ES A PROPOSITO (24-08). Al reeditar,
    # el cierre se sustituye entero: si el cliente vacia la casilla del peso, la fila se
    # guarda sin peso pero el punto que ya escribio aqui SIGUE en la serie, y su grafica
    # conserva un pesaje que el cree haber quitado. Se ha dejado asi, y no por pereza:
    #
    #   - La serie tiene UN punto por dia, y ese dia puede haberlo escrito tambien un
    #     reporte, el coach o el alta (cada punto lleva su `origen`). Borrar "el del dia"
    #     desde aqui se llevaria por delante un pesaje que no es de este formulario.
    #   - Quitar un punto no existe hoy en `core/series_cliente` (solo hay `anotar_*`), y
    #     esa pieza es la que sostiene el peso actual del perfil, la curva y el ritmo de
    #     cambio: estrenarla el dia antes de que entren los clientes no toca.
    #
    # Lo que SI esta cerrado es que el cliente no pierda el dato sin querer: la pantalla
    # vuelve a pintarle el peso guardado al reabrir el cierre, aunque el cierre corto lo
    # esconda, asi que borrarlo es ahora un acto deliberado y no un efecto secundario.
    # Cuando haya que quitarlo de verdad, la puerta es Evolucion, que es de donde sale la
    # grafica. Lo cierra el equipo con Jesus: no es una decision de este arreglo.
    if data.weight is not None:
        await anotar_peso(profile["id"], data.weight, _dia_del_pesaje(data.peso_fecha, dia),
                          origen=f"check-in {data.type}")
    # El % graso del check-in mensual, si viene. La pantalla YA NO LO PIDE (punto 53 del
    # doc del 07-08: "hoy la app lo pide cada mes" y no debe): es un dato que estima Jesus
    # mirando las fotos, y solo al principio, al empezar una fase y al acabarla. Pedirselo
    # al cliente cada cuatro semanas lo convierte en ruido -- repite el mismo numero o pone
    # uno al azar -- y ese ruido entra luego en el eje respondedor.
    #
    # Se sigue aceptando por si llega de una version vieja de la app o de un check-in ya
    # guardado: si alguien se molesto en ponerlo, no se tira.
    if data.body_fat_pct is not None:
        await anotar_grasa(profile["id"], data.body_fat_pct, dia,
                           origen=f"check-in {data.type}")

    return CheckInResponse(**checkin)


@router.get("/checkins", response_model=List[CheckInResponse])
async def get_my_checkins(type: Optional[str] = None, limit: int = 30, skip: int = 0, user = Depends(get_current_user)):
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    query: Dict[str, Any] = {"client_id": profile["id"]}
    if type:
        if type not in VALID_CHECKIN_TYPES:
            raise HTTPException(status_code=400, detail="Tipo invalido")
        query["type"] = type

    checkins = await db.checkins.find(query, {"_id": 0}).sort("created_at", -1).skip(max(0, skip)).to_list(min(limit, 100))

    # EL PESO, SANEADO ANTES DE ENSEÑARLO, TAMBIEN AQUI (24-08). Esto ya se hacia en la
    # ficha del entrenador (`admin_get_client_checkins`, justo debajo) y en los reportes,
    # pero la lista que ve EL CLIENTE se quedo sin ello, que es la unica que el mira: en
    # los check-ins importados de Calma el peso vino en gramos, y son 159 filas de 18
    # clientes en produccion. Muerde dos veces:
    #
    #   - En su historial le pone «68350 kg» en su propio reporte de hace un año.
    #   - Y en el cierre del dia, donde la pantalla compara lo que escribe con el ultimo
    #     peso que sale de ESTA lista: a 8 clientes el mas reciente les viene en gramos,
    #     asi que al apuntar sus 80 kg les saltaba «tu ultimo peso fue 68350 kg, son 68270
    #     de diferencia, ¿esta bien?». Todos los dias, y por un dato que no es suyo.
    #
    # La regla vive en un solo sitio, `sanea_peso`: si no se puede arreglar devuelve None y
    # la entrada sale sin peso, que es mejor que un numero falso.
    from core.series_cliente import sanea_peso
    for c in checkins:
        if c.get("weight") is not None:
            c["weight"] = sanea_peso(c["weight"])
    return [CheckInResponse(**c) for c in checkins]


@router.get("/admin/clients/{client_id}/checkins", response_model=List[CheckInResponse])
async def admin_get_client_checkins(client_id: str, type: Optional[str] = None, limit: int = 60, user = Depends(get_admin_user)):
    await _assert_staff_client_access(user, client_id)
    query: Dict[str, Any] = {"client_id": client_id}
    if type:
        if type not in VALID_CHECKIN_TYPES:
            raise HTTPException(status_code=400, detail="Tipo invalido")
        query["type"] = type
    checkins = await db.checkins.find(query, {"_id": 0}).sort("created_at", -1).to_list(min(limit, 200))
    # EL PESO, SANEADO ANTES DE ENSEÑARLO. En los check-ins importados el peso viene en
    # gramos, y el bloque «Check-ins mensuales» de la ficha ponía «01 jun 2026 · 61250 kg».
    # Es el mismo arreglo que ya se hace con los reportes y con lo de Calma en
    # `get_client_detail`: la regla vive en un solo sitio, `sanea_peso`.
    from core.series_cliente import sanea_peso
    for c in checkins:
        if c.get("weight") is not None:
            c["weight"] = sanea_peso(c["weight"])
    return [CheckInResponse(**c) for c in checkins]


@router.post("/admin/clients/{client_id}/checkins/{checkin_id}/feedback")
async def admin_set_checkin_feedback(client_id: str, checkin_id: str, data: dict, user = Depends(get_admin_user)):
    await _assert_staff_client_access(user, client_id)
    feedback = (data or {}).get("feedback", "")
    result = await db.checkins.update_one(
        {"id": checkin_id, "client_id": client_id},
        {"$set": {"trainer_feedback": feedback}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Check-in no encontrado")

    if feedback.strip():
        profile = await db.client_profiles.find_one({"id": client_id}, {"_id": 0, "user_id": 1})
        if profile:
            from routes.notifications import notify
            await notify(profile["user_id"], "feedback", "Hemos comentado tu check-in", "/dashboard/checkins")

    return {"success": True}


@router.get("/admin/clients/{client_id}/health-score")
async def admin_get_health_score(client_id: str, user = Depends(get_admin_user)):
    profile = await db.client_profiles.find_one({"id": client_id}, {"_id": 0})
    assert_client_access(user, profile)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    checkins = await db.checkins.find(
        {"client_id": client_id, "created_at": {"$gte": cutoff}},
        {"_id": 0},
    ).sort("created_at", -1).to_list(60)
    return _compute_health_score(checkins, profile)


# La etiqueta de riesgo NO tiene ruta para el cliente, a proposito (doc del 07-08, punto 6).
#
# Habia un `GET /checkins/health-score` que se la daba a el mismo, y la pantalla de Check-ins
# se la pintaba en una tarjeta roja que ponia "En riesgo". Es una nota de gestion del
# entrenador: sirve para saber a quien hay que llamar, no para que el cliente se vea
# etiquetado. Y ademas los motivos que acompanan a la etiqueta son de cobro y de gestion
# interna ("Pago atrasado", "N intentos de cobro fallidos", "Baja automatica por fallos de
# pago"), que el cliente no tiene por que leer en su panel.
#
# Se queda solo la de arriba, `admin/clients/{client_id}/health-score`, con get_admin_user.
# Si algun dia se quiere ensenar algo al cliente sobre como va, que sea un texto pensado para
# el y con otro nombre, no esta etiqueta.


# ==================== FOTOS DE PROGRESO ====================
#
# Guardadas como bson.Binary en colección dedicada `client_photos` para no
# inflar los documentos de check-in (límite Mongo 16MB).

MAX_PHOTO_BYTES = 4 * 1024 * 1024  # 4 MB
ALLOWED_PHOTO_TYPES = {
    "image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic", "image/heif",
}


def _photo_meta(doc: dict) -> dict:
    """Quita el binario del documento - para respuestas de listado."""
    return {
        "id":           doc.get("id"),
        "client_id":    doc.get("client_id"),
        "user_id":      doc.get("user_id"),
        "filename":     doc.get("filename"),
        "content_type": doc.get("content_type"),
        "size":         doc.get("size"),
        "taken_at":     doc.get("taken_at"),
        "uploaded_at":  doc.get("uploaded_at"),
        # Sin la pose, tres fotos de un mes son tres fotos; con ella son la misma foto de
        # meses distintos, que es lo único que se puede comparar.
        "pose":         doc.get("pose"),
        "inicial":      bool(doc.get("inicial")),
    }


async def _resolve_client_id_for_user(user: dict) -> Optional[str]:
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
    return profile["id"] if profile else None


async def _guardar_foto_de_progreso(*, client_id: str, user_id: Optional[str],
                                    file: UploadFile, taken_at: Optional[str],
                                    pose: Optional[str], subida_por: Optional[str] = None) -> dict:
    """Valida y guarda una foto de progreso. La usan las dos vías: la del cliente y la del
    equipo subiéndola por él (punto 45). Las comprobaciones tienen que ser las mismas en
    las dos, y por eso están aquí y no repetidas."""
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_PHOTO_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no permitido: {content_type or 'desconocido'}. Sube JPEG, PNG, WebP o HEIC.",
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")
    if len(contents) > MAX_PHOTO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"La foto pesa {len(contents) // 1024} KB; el máximo permitido es {MAX_PHOTO_BYTES // (1024 * 1024)} MB.",
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    if taken_at:
        try:
            datetime.fromisoformat(taken_at.replace("Z", "+00:00"))
        except Exception:
            taken_at = None

    pose_norm = (pose or "").strip().lower()
    if pose_norm not in ("frente", "espalda", "perfil"):
        pose_norm = None

    # ¿Es la primera de esta pose? Esa no se borra nunca: es contra la que se compara todo
    # lo demás, y sin ella la comparativa pierde el "de dónde vengo".
    es_inicial = False
    if pose_norm:
        es_inicial = await db.client_photos.count_documents(
            {"client_id": client_id, "pose": pose_norm}) == 0
    else:
        es_inicial = await db.client_photos.count_documents({"client_id": client_id}) == 0

    doc = {
        "id":           str(uuid.uuid4()),
        "client_id":    client_id,
        "user_id":      user_id,
        "filename":     file.filename or "photo.jpg",
        "content_type": content_type,
        "size":         len(contents),
        "taken_at":     taken_at or now_iso,
        "uploaded_at":  now_iso,
        "pose":         pose_norm,
        "inicial":      es_inicial,
    }
    if subida_por:
        # Quien la subio, cuando no fue el cliente (punto 45).
        doc["subida_por"] = subida_por

    # LAS FOTOS NUEVAS NACEN EN R2 (22-08): el binario va al bucket y aqui queda solo el
    # metadato, asi Mongo deja de engordar 1-4 MB por foto. Sin R2 (dev sin claves, o R2
    # caido en ese momento), el blob se guarda como toda la vida y nada se pierde.
    clave_r2 = await fotos_core.subir_foto_nueva(
        user_id=user_id, client_id=client_id, photo_id=doc["id"],
        contenido=contents, content_type=content_type)
    if clave_r2:
        doc["en_r2"] = True
        doc["r2_key"] = clave_r2
        doc["en_r2_at"] = now_iso
    else:
        doc["data"] = Binary(contents)
    await db.client_photos.insert_one(doc)
    return doc


@router.post("/reports/photos")
async def upload_progress_photo(
    file: UploadFile = File(..., description="Foto de progreso (JPEG, PNG, WebP, HEIC). Máx 4 MB."),
    taken_at: Optional[str] = Query(None, description="Fecha ISO de la foto (por defecto ahora)."),
    pose: Optional[str] = Query(None, description="frente | espalda | perfil"),
    user = Depends(get_current_user),
):
    """El cliente sube una foto de progreso. Guardada en `client_photos`. Devuelve metadatos.

    La `pose` es lo que permite comparar: sin ella, tres fotos de un mes son tres fotos, y
    con ella son la misma foto de tres meses distintos. Se acepta vacía porque las que ya
    estaban subidas no la tienen.
    """
    client_id = await _resolve_client_id_for_user(user)
    if not client_id:
        raise HTTPException(status_code=400, detail="No se encontró el perfil de cliente.")
    doc = await _guardar_foto_de_progreso(
        client_id=client_id, user_id=user["id"], file=file, taken_at=taken_at, pose=pose)
    return _photo_meta(doc)


@router.post("/admin/clients/{client_id}/reports/photos")
async def subir_foto_por_el_cliente(
    client_id: str,
    file: UploadFile = File(..., description="Foto de progreso (JPEG, PNG, WebP, HEIC). Máx 4 MB."),
    taken_at: Optional[str] = Query(None, description="Fecha ISO de la foto (por defecto ahora)."),
    pose: Optional[str] = Query(None, description="frente | espalda | perfil"),
    user=Depends(get_admin_user),
):
    """El equipo sube una foto EN NOMBRE de un cliente (punto 45 del doc del 07-08).

    Los Premium mandan las fotos por WhatsApp y alguien del equipo las sube. Hasta ahora
    habia que hacerlo entrando con la cuenta del cliente ("subiendo las fotos con el correo
    del cliente para que se enlacen a su ficha", dice el punto), que es exactamente lo que
    no deberia hacer falta.

    Es la misma foto y va a la misma coleccion: lo unico que cambia es quien la sube, y eso
    queda anotado.
    """
    profile = await db.client_profiles.find_one({"id": client_id})
    assert_client_access(user, profile)
    doc = await _guardar_foto_de_progreso(
        client_id=client_id, user_id=profile.get("user_id"), file=file,
        taken_at=taken_at, pose=pose, subida_por=user.get("name", user.get("email", "equipo")))
    return _photo_meta(doc)


@router.get("/reports/photos")
async def list_my_photos(user = Depends(get_current_user)):
    """Lista TODAS las fotos del cliente (app + importadas de Calma), más recientes primero.

    La lista sale de `core/fotos.listar_fotos_de` (tarea 1.1): mismo formato de siempre
    para las de la app, y las de Calma con su `ref` -- que también viaja como `id`, para
    que las pantallas que piden el binario por /reports/photos/{id} las carguen igual."""
    photos = await listar_fotos_de(user)
    return {"photos": photos, "count": len(photos)}


@router.get("/reports/foto/{ref:path}")
async def get_my_photo(ref: str, user = Depends(get_current_user)):
    """Sirve el binario de UNA foto del cliente por su ref (de la app o de Calma).

    Autenticación de cliente normal: `core/fotos.abrir_foto` valida que la foto es del
    que la pide, venga de donde venga. `:path` porque la ref de Calma lleva una barra
    (carpeta/fichero)."""
    data, content_type = await abrir_foto(user, ref)
    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.get("/reports/photos/{photo_id:path}")
async def get_photo(photo_id: str, user = Depends(get_current_user)):
    """Sirve el binario de la foto. El llamante debe ser el dueño o staff.

    Las refs de Calma (calma/...) también entran por aquí: la rejilla de check-ins y las
    tres fotos del reporte piden por /reports/photos/{id} con lo que llega en la lista,
    y así cargan las importadas sin cambiar. Solo para el dueño; el staff tiene su
    endpoint de admin para las de Calma."""
    if es_ref_calma(photo_id):
        data, content_type = await abrir_foto(user, photo_id)
        return Response(
            content=data,
            media_type=content_type,
            headers={"Cache-Control": "private, max-age=3600"},
        )
    photo = await db.client_photos.find_one({"id": photo_id}, {"_id": 0})
    if not photo:
        raise HTTPException(status_code=404, detail="Foto no encontrada")

    if photo.get("user_id") != user["id"]:
        # No es el dueño: solo el admin, o el entrenador ASIGNADO a ese cliente.
        await _assert_staff_photo_access(user, photo.get("user_id"))

    # De R2 (si la foto nació allí) o del blob de Mongo; misma vía que usa el cliente por
    # /reports/foto/{ref}. Antes leía solo el blob y daba 404 con las fotos R2 sin copia.
    data, content_type = await fotos_core.leer_binario_de_foto_app(photo)

    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Cache-Control": "private, max-age=3600",
            "Content-Disposition": f'inline; filename="{photo.get("filename") or "photo"}"',
        },
    )


@router.delete("/reports/photos/{photo_id:path}")
async def delete_photo(photo_id: str, user = Depends(get_current_user)):
    """El dueño o staff borra una foto."""
    # Las importadas de Calma no se borran desde la app: son el histórico del cliente
    # y el registro vive en calma_raw, no en client_photos.
    if es_ref_calma(photo_id):
        raise HTTPException(
            status_code=400,
            detail="Esta foto viene de tu etapa anterior y no se puede borrar desde aquí.",
        )
    photo = await db.client_photos.find_one(
        {"id": photo_id},
        {"_id": 0, "user_id": 1, "client_id": 1, "inicial": 1, "en_r2": 1, "r2_key": 1, "id": 1})
    if not photo:
        raise HTTPException(status_code=404, detail="Foto no encontrada")
    if photo.get("user_id") != user["id"]:
        await _assert_staff_photo_access(user, photo.get("user_id"))
    # La inicial no se borra. Es contra la que se compara todo lo demás: sin ella la
    # comparativa se queda sin el "de dónde vengo", que es la que más dice de las cuatro.
    if photo.get("inicial"):
        raise HTTPException(
            status_code=400,
            detail="Esta es tu foto inicial y no se puede borrar: es contra la que se comparan las demás.",
        )
    # Si vive en R2, su objeto se va con ella (si R2 no responde, el documento se borra
    # igual y el objeto huerfano lo recogera una limpieza; el detalle, a consola).
    if photo.get("en_r2"):
        await fotos_core.borrar_objeto_r2(fotos_core._clave_r2_app(photo))
    await db.client_photos.delete_one({"id": photo_id})
    return {"ok": True}


@router.get("/admin/clients/{client_id}/photos")
async def admin_list_client_photos(client_id: str, user = Depends(get_admin_user)):
    """Admin/coach: lista las fotos de un cliente (metadatos, más recientes primero)."""
    await _assert_staff_client_access(user, client_id)
    cursor = db.client_photos.find({"client_id": client_id}, {"_id": 0, "data": 0}).sort("taken_at", -1)
    photos = await cursor.to_list(length=500)
    return {"photos": photos, "count": len(photos)}
