"""
Las tareas que se generan solas (doc del 19-08, apartado 05, parte 3).

    «Estas no las asigna nadie: salen del calendario y de los datos. Son la diferencia
     entre una lista de tareas y un sistema — lo primero depende de que alguien se
     acuerde.»

No hay cron: se generan al consultar la lista de tareas (el mismo patrón que las alertas
de report_overdue), con un freno para no escanear la cartera entera en cada carga. La
deduplicación es la `clave` de cada tarea: mientras exista una con esa clave, no se
vuelve a crear — por eso las condiciones que se repiten llevan el periodo en la clave.

A QUIÉN VA CADA UNA. El doc reparte entre «Jenny», «su entrenador» y «Operaciones».
Jenny se busca por nombre entre el staff; si no tiene usuario, sus tareas van al primer
administrador (y el día que se le dé de alta, empiezan a caerle a ella sin tocar nada).
Operaciones es el administrador. Las del entrenador van al asignado, y si el cliente no
tiene, la tarea que salta es justamente la de asignárselo.

LO QUE AQUÍ NO ESTÁ, Y POR QUÉ:
  - «Cobrar a Luigi Mazzali · Javier Marcos · Jorge Gabas» (cobro a mano): no hay ningún
    campo que diga quién paga por transferencia; está en la hoja de control de pagos.
    Cuando ese dato viva en la ficha, se engancha aquí.
  - «Ha pedido la baja»: el flujo de pedir la baja no existe todavía (apartado «Mi plan y
    la baja» del mismo doc). `tarea_baja_pedida` queda lista para llamarla desde ahí.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core.calendario_reportes import calendario_del_cliente
from core.cartera import reportes_sin_responder
from core.semana_rutina import semana_de_rutina
from core.tareas import crear_tarea
from core.tiempo import a_madrid

# El freno: como mucho una pasada cada tantos minutos, la dispare quien la dispare.
CADA_MINUTOS = 10

# En qué semana del ciclo se avisa de la renovación: «Un cliente llega a semana 10.
# Se cobra en la 12» — dos semanas antes del final, sea el ciclo de 12 o de 8.
SEMANAS_ANTES_DE_RENOVAR = 2


async def _destinatarios(db) -> Dict[str, Optional[str]]:
    """{jenny, operaciones}: a quién van las tareas de dinero y las de operaciones."""
    jenny = None
    primer_admin = None
    async for u in db.users.find({"role": {"$in": ["admin", "trainer"]}},
                                 {"_id": 0, "id": 1, "name": 1, "role": 1}).sort("name", 1):
        nombre = (u.get("name") or "").lower()
        if "jenny" in nombre and not jenny:
            jenny = u["id"]
        if u.get("role") == "admin" and not primer_admin:
            primer_admin = u["id"]
    return {"jenny": jenny or primer_admin, "operaciones": primer_admin}


async def _toca_pasar(db, ahora: datetime) -> bool:
    doc = await db.app_state.find_one({"clave": "tareas_auto"}, {"_id": 0, "cuando": 1})
    if doc and doc.get("cuando"):
        try:
            ultima = datetime.fromisoformat(doc["cuando"])
            if ahora - ultima < timedelta(minutes=CADA_MINUTOS):
                return False
        except (ValueError, TypeError):
            pass
    await db.app_state.update_one({"clave": "tareas_auto"},
                                  {"$set": {"cuando": ahora.isoformat()}}, upsert=True)
    return True


async def generar_tareas_automaticas(db, forzar: bool = False) -> int:
    """Una pasada por la cartera. Devuelve cuántas tareas nuevas dejó."""
    ahora = datetime.now(timezone.utc)
    if not forzar and not await _toca_pasar(db, ahora):
        return 0

    from core.plan_access import has_active_access, tiene_entrenador_detras
    from models.user import codigo_de_plan, merged_catalog, PLAN_CATALOG
    from routes.plans import _overrides_by_code
    from models.user import precio_de_ciclo

    catalogo = merged_catalog(await _overrides_by_code())
    quien = await _destinatarios(db)
    jenny, operaciones = quien["jenny"], quien["operaciones"]
    if not jenny and not operaciones:
        return 0                                   # base sin staff: no hay a quién asignar

    hoy_es = (a_madrid(ahora) or ahora).date()
    mes = hoy_es.isoformat()[:7]
    semana_iso = f"{hoy_es.isocalendar()[0]}-W{hoy_es.isocalendar()[1]:02d}"

    del_equipo = await db.users.distinct("id", {"role": {"$in": ["admin", "trainer"]}})
    # Mismo criterio que _fuera_el_equipo() del panel (copia local a proposito: core no
    # importa de routes): las cuentas marcadas como de prueba no generan tareas.
    perfiles = await db.client_profiles.find(
        {"user_id": {"$nin": del_equipo}, "status": {"$in": ["activo", "pago_pendiente"]},
         "es_prueba": {"$ne": True}},
        {"_id": 0, "id": 1, "user_id": 1, "plan": 1, "price": 1, "comp_plan": 1, "week": 1,
         "trainer_id": 1, "cycle_start": 1, "created_at": 1, "current_period_end": 1,
         "subscription_status": 1, "stripe_subscription_id": 1, "access_until": 1,
         "checkout_status": 1, "status": 1, "ultimo_reporte": 1, "ultima_entrada": 1,
         "aplazamientos_seguidos": 1, "height": 1, "goal": 1, "body_fat": 1,
         "calendario_reportes": 1, "ciclo_semanas": 1, "semana_de_entrada": 1,
         # Lo que ha comprado APARTE, para el bloque de complementos de mas abajo.
         "rutina_mes_pedida": 1, "revision_suelta": 1, "ajuste_a_medida": 1},
    ).to_list(3000)

    nombres = {u["id"]: u.get("name") async for u in db.users.find(
        {"id": {"$in": [p["user_id"] for p in perfiles]}}, {"_id": 0, "id": 1, "name": 1})}

    # Rutinas activas (la semana que manda) y última foto, en bloque.
    rutina_de = {r["client_id"]: r for r in await db.routines.find(
        {"client_id": {"$in": [p["id"] for p in perfiles]}, "status": "active"},
        {"_id": 0, "client_id": 1, "created_at": 1}).to_list(3000)}
    ultima_foto: Dict[str, str] = {}
    async for f in db.client_photos.aggregate([
            {"$group": {"_id": "$client_id", "ultima": {"$max": "$created_at"}}}]):
        if f.get("_id"):
            ultima_foto[f["_id"]] = f.get("ultima") or ""

    creadas = 0

    # LO QUE YA NO APLICA SE CIERRA SOLO. El generador creaba «Asignar entrenador a X»
    # cuando faltaba el dato, pero nada la cerraba cuando el dato aparecia: la tarea
    # seguia abierta con el entrenador ya asignado. En cada pasada, la clave cuya
    # condicion ya se cumple se marca hecha por el sistema. Solo las de ESTADO (dato que
    # falta o pago que se arregla); las de contactar con periodo en la clave (se_cae,
    # no_entra, sin_fotos, renovacion...) son trabajo de personas y no se tocan.
    claves_abiertas = set(await db.tareas.distinct(
        "clave", {"hecha": False, "clave": {"$ne": None}, "origen": {"$regex": "^auto:"}}))
    por_cerrar: set = set()

    def cerrar(clave):
        if clave in claves_abiertas:
            por_cerrar.add(clave)

    def cerrar_por_prefijo(prefijo):
        por_cerrar.update(c for c in claves_abiertas if c.startswith(prefijo))

    async def tarea(**kw):
        nonlocal creadas
        if await crear_tarea(db, **kw):
            creadas += 1

    for p in perfiles:
        cid, nombre = p.get("id"), nombres.get(p.get("user_id")) or "cliente"
        plan_code = codigo_de_plan(p.get("plan"))
        plan = catalogo.get(plan_code) or {}
        entrenador = p.get("trainer_id")
        con_coach = tiene_entrenador_detras(plan_code)
        # La semana que manda: la de rutina si la tiene (bloque 02).
        sem_rutina = semana_de_rutina(rutina_de.get(cid), hoy_es)
        semana = sem_rutina if sem_rutina is not None else p.get("week")
        cal = calendario_del_cliente(p, plan)

        # ── EL DINERO («las cinco que se pagan solas») ────────────────────────
        ciclo_sem = (plan.get("ciclo") or {}).get("semanas")
        renueva_solo = bool((plan.get("renovacion") or {}).get("automatica")) \
            and p.get("subscription_status") in ("active", "trialing")
        if (ciclo_sem and p.get("week")
                and int(p["week"]) >= int(ciclo_sem) - SEMANAS_ANTES_DE_RENOVAR
                and int(p["week"]) <= int(ciclo_sem)
                and not renueva_solo):
            await tarea(a_quien=jenny, que=f"Contactar a {nombre} para renovación. "
                                          f"Se cobra en la semana {ciclo_sem}",
                        sobre_quien=cid, sobre_quien_nombre=nombre,
                        clave=f"renovacion:{cid}:{str(p.get('cycle_start'))[:10]}",
                        origen="auto:renovacion")

        if p.get("subscription_status") in ("past_due", "unpaid", "incomplete"):
            await tarea(a_quien=jenny, que=f"Problema de pago de {nombre}: contactar por WhatsApp",
                        sobre_quien=cid, sobre_quien_nombre=nombre,
                        clave=f"rebote:{cid}:{mes}", origen="auto:rebote_pago")
        else:
            cerrar_por_prefijo(f"rebote:{cid}:")   # el pago volvio a entrar

        if p.get("status") == "activo" and not has_active_access(p):
            await tarea(a_quien=jenny, que=f"{nombre} ha causado baja (venció sin renovar). "
                                          "Mandarle lo de recuperación",
                        sobre_quien=cid, sobre_quien_nombre=nombre,
                        clave=f"vencido:{cid}:{str(p.get('current_period_end') or p.get('access_until'))[:10]}",
                        origen="auto:vencido")
        elif has_active_access(p):
            cerrar_por_prefijo(f"vencido:{cid}:")  # renovo: ya no hay nada que recuperar

        if not p.get("comp_plan") and precio_de_ciclo(p, catalogo) == 0:
            await tarea(a_quien=jenny, que=f"Poner el precio de {nombre}: sale de la hoja "
                                          "de control de pagos",
                        sobre_quien=cid, sobre_quien_nombre=nombre,
                        clave=f"sin_precio:{cid}", origen="auto:sin_precio")
        else:
            cerrar(f"sin_precio:{cid}")            # el precio ya esta puesto

        # ── EL CLIENTE SE ESTÁ CAYENDO ────────────────────────────────────────
        a_su_coach = entrenador or operaciones
        if con_coach:
            debe = reportes_sin_responder(cal, semana, p.get("ultimo_reporte"), hoy_es)
            if debe is not None and debe >= 2:
                await tarea(a_quien=a_su_coach,
                            que=f"{nombre} se está cayendo: {debe} reportes seguidos sin mandar. Contactar",
                            sobre_quien=cid, sobre_quien_nombre=nombre,
                            clave=f"se_cae_reportes:{cid}:{mes}", origen="auto:se_cae")

        if int(p.get("aplazamientos_seguidos") or 0) >= 2:
            await tarea(a_quien=a_su_coach,
                        que=f"{nombre} lleva 2 aplazamientos seguidos: ya no es un imprevisto. Contactar",
                        sobre_quien=cid, sobre_quien_nombre=nombre,
                        clave=f"aplazamientos:{cid}:{int(p.get('aplazamientos_seguidos') or 0)}",
                        origen="auto:aplazamientos")

        entrada = p.get("ultima_entrada")
        if entrada:
            try:
                sin_entrar = (hoy_es - datetime.fromisoformat(str(entrada)[:10]).date()).days
            except (ValueError, TypeError):
                sin_entrar = None
            if sin_entrar is not None and sin_entrar >= 14:
                await tarea(a_quien=a_su_coach,
                            que=f"{nombre} lleva {sin_entrar} días sin entrar en la app. Contactar",
                            sobre_quien=cid, sobre_quien_nombre=nombre,
                            clave=f"no_entra:{cid}:{mes}", origen="auto:no_entra")

        if not con_coach and cid:
            foto = ultima_foto.get(cid)
            base = foto or p.get("cycle_start") or p.get("created_at")
            try:
                dias_sin_fotos = (hoy_es - datetime.fromisoformat(str(base)[:10]).date()).days if base else None
            except (ValueError, TypeError):
                dias_sin_fotos = None
            if dias_sin_fotos is not None and dias_sin_fotos >= 56:      # ocho semanas
                await tarea(a_quien=jenny,
                            que=f"{nombre} lleva 8 semanas sin fotos (autogestión): recordárselo",
                            sobre_quien=cid, sobre_quien_nombre=nombre,
                            clave=f"sin_fotos:{cid}:{mes}", origen="auto:sin_fotos")

        # ── LO QUE ESTÁ INCOMPLETO ────────────────────────────────────────────
        if con_coach and not entrenador:
            await tarea(a_quien=operaciones, que=f"Asignar entrenador a {nombre}",
                        sobre_quien=cid, sobre_quien_nombre=nombre,
                        clave=f"sin_entrenador:{cid}", origen="auto:sin_entrenador")
        else:
            cerrar(f"sin_entrenador:{cid}")        # ya tiene, o su plan no lleva coach

        faltan = [n for n, v in (("altura", p.get("height")), ("objetivo", p.get("goal")),
                                 ("% de grasa", p.get("body_fat"))) if v in (None, "", 0)]
        if faltan and cid:
            await tarea(a_quien=jenny,
                        que=f"Pedirle a {nombre} los datos que faltan: {', '.join(faltan)} "
                            "(con eso se le están calculando los macros)",
                        sobre_quien=cid, sobre_quien_nombre=nombre,
                        clave=f"sin_datos:{cid}:{mes}", origen="auto:sin_datos")
        elif cid:
            cerrar_por_prefijo(f"sin_datos:{cid}:")  # los dio: la de este mes y las viejas

        if p.get("plan") and plan_code not in PLAN_CATALOG:
            await tarea(a_quien=operaciones,
                        que=f"Asignar plan a {nombre}: el suyo («{p.get('plan')}») no existe en el catálogo",
                        sobre_quien=cid, sobre_quien_nombre=nombre,
                        clave=f"plan_inexistente:{cid}", origen="auto:plan_inexistente")
            cerrar(f"sin_plan:{cid}")
        elif not p.get("plan"):
            await tarea(a_quien=operaciones, que=f"Asignar plan a {nombre}: no tiene ninguno",
                        sobre_quien=cid, sobre_quien_nombre=nombre,
                        clave=f"sin_plan:{cid}", origen="auto:sin_plan")
            cerrar(f"plan_inexistente:{cid}")
        else:
            cerrar(f"sin_plan:{cid}")
            cerrar(f"plan_inexistente:{cid}")

        # ── LO QUE HA COMPRADO APARTE Y ESTA SIN ENTREGAR ────────────────────
        #
        # «Que no sea tedioso ir revisando ficha por ficha» (Francisco, 25-08). Un
        # complemento comprado no aparecia en ninguna lista de trabajo: se apuntaba en la
        # ficha del cliente y ahi se quedaba, asi que para saber si alguien habia pagado
        # una revision habia que abrir las fichas una a una. Ahora entra por la misma
        # puerta que todo lo demas -- la pantalla de Tareas, que ya es «lo mio, con el
        # cliente y un clic a su ficha» -- y desaparece sola en cuanto se entrega.
        #
        # Van al ENTRENADOR del cliente, que es quien las hace. Si no tiene, a operaciones:
        # una revision pagada que no se entrega es dinero cobrado sin dar el servicio, y no
        # puede quedarse esperando a que alguien le asigne entrenador.
        quien_lo_hace = entrenador or operaciones

        rutina_ap = p.get("rutina_mes_pedida") or {}
        if rutina_ap.get("cobrado") and not rutina_ap.get("rutina_puesta"):
            await tarea(a_quien=quien_lo_hace,
                        que=f"Entregar la rutina del mes a {nombre}, que ya la ha pagado",
                        sobre_quien=cid, sobre_quien_nombre=nombre,
                        clave=f"comprado_rutina:{cid}:{str(rutina_ap.get('cuando'))[:10]}",
                        origen="auto:comprado")
        elif rutina_ap.get("rutina_puesta"):
            cerrar_por_prefijo(f"comprado_rutina:{cid}:")
        # Pedida y con el cobro caido: eso es dinero, y el dinero es de operaciones.
        if rutina_ap.get("cobrado") is False and rutina_ap.get("motivo"):
            await tarea(a_quien=jenny or operaciones,
                        que=f"A {nombre} le falló el cobro de la rutina del mes "
                            f"({rutina_ap.get('motivo')})",
                        sobre_quien=cid, sobre_quien_nombre=nombre,
                        clave=f"comprado_rutina_impagada:{cid}:{str(rutina_ap.get('cuando'))[:10]}",
                        origen="auto:comprado")

        rev_ap = p.get("revision_suelta") or {}
        if rev_ap.get("pagada_at") and rev_ap.get("estado") not in ("entregado", "cancelado"):
            await tarea(a_quien=quien_lo_hace,
                        que=f"Hacerle la revisión de macros a {nombre}, que la compró suelta",
                        sobre_quien=cid, sobre_quien_nombre=nombre,
                        clave=f"comprado_revision:{cid}:{str(rev_ap.get('pagada_at'))[:10]}",
                        origen="auto:comprado")
        elif rev_ap.get("estado") in ("entregado", "cancelado"):
            cerrar_por_prefijo(f"comprado_revision:{cid}:")

        aj_ap = p.get("ajuste_a_medida") or {}
        if aj_ap.get("cobrado") and aj_ap.get("estado") not in ("entregado", "cancelado"):
            # El ajuste a medida se promete PARA UN LUNES, asi que la tarea lleva su fecha:
            # es la unica de las tres que tiene un plazo dado al cliente.
            await tarea(a_quien=quien_lo_hace,
                        que=f"Entregar el ajuste a medida de {nombre}",
                        para_cuando=aj_ap.get("para_el_lunes"),
                        sobre_quien=cid, sobre_quien_nombre=nombre,
                        clave=f"comprado_ajuste:{cid}:{str(aj_ap.get('pagado_at'))[:10]}",
                        origen="auto:comprado")
        elif aj_ap.get("estado") in ("entregado", "cancelado"):
            cerrar_por_prefijo(f"comprado_ajuste:{cid}:")

    # ── EL TRABAJO DE LA SEMANA, POR ENTRENADOR ──────────────────────────────
    #
    # CON NOMBRE Y APELLIDOS, NO UN RECUENTO (Francisco, 25-08: «esos ya son dias fijos
    # pero no tendria claro a que clientes»). Esto decia «Entregar rutinas de 7», y el
    # entrenador sabia que le tocaban siete y no cuales eran los siete: para averiguarlo
    # tenia que ir cliente por cliente mirando quien habia mandado reporte. Ahora es una
    # tarea POR CLIENTE, con `sobre_quien`, asi que desde la tarea se abre su ficha y se
    # van tachando de una en una. Es como funcionan ya las demas automaticas de este
    # fichero; estas cuatro eran las unicas que agregaban.
    #
    # El volumen aguanta: medido en produccion, la semana del 25-08 fueron 6 reportes en
    # total y todos del mismo entrenador. Si algun dia una cartera creciera hasta hacerlo
    # incomodo, la salida no es volver al recuento sino agrupar en la pantalla.
    dia = hoy_es.weekday()
    hora_es = (a_madrid(ahora) or ahora).hour
    if dia in (0, 2, 3, 4):
        desde = hoy_es - timedelta(days=(hoy_es.weekday() - 4) % 7 or 7)   # el viernes pasado
        trainer_por_cliente = {p["id"]: p.get("trainer_id") for p in perfiles if p.get("id")}
        nombre_por_cliente = {p["id"]: nombres.get(p.get("user_id")) or "cliente"
                              for p in perfiles if p.get("id")}
        # Quien ha mandado reporte esta semana, con los TIPOS que mando: uno puede haber
        # mandado el quincenal y el mensual, y el viernes solo se pide feedback del
        # quincenal.
        mandaron: Dict[str, Dict[str, Any]] = {}
        async for r in db.reports.find({"created_at": {"$gte": desde.isoformat()}},
                                       {"_id": 0, "client_id": 1, "tipo": 1, "created_at": 1}):
            cid = r.get("client_id")
            t = trainer_por_cliente.get(cid)
            if not t:
                continue
            ficha = mandaron.setdefault(cid, {"trainer": t, "tipos": set()})
            if r.get("tipo"):
                ficha["tipos"].add(r["tipo"])

        for cid, ficha in mandaron.items():
            t, nombre_cli = ficha["trainer"], nombre_por_cliente.get(cid, "cliente")
            comun = {"a_quien": t, "sobre_quien": cid, "sobre_quien_nombre": nombre_cli,
                     "origen": "auto:semana"}
            if dia == 0 and hora_es >= 18:      # lunes 18:01, al cerrar el mensual
                await tarea(**comun, que=f"Leer el reporte de {nombre_cli}, para el miércoles",
                            clave=f"semana_lunes:{cid}:{semana_iso}")
            elif dia == 2:                       # miércoles: macros y suplementación
                await tarea(**comun, que=f"Entregar macros y suplementación a {nombre_cli}",
                            clave=f"semana_miercoles:{cid}:{semana_iso}")
            elif dia == 3:                       # jueves: rutinas
                await tarea(**comun, que=f"Entregar la rutina de {nombre_cli}",
                            clave=f"semana_jueves:{cid}:{semana_iso}")
            elif dia == 4 and "quincenal" in ficha["tipos"]:
                await tarea(**comun, que=f"Dar feedback del quincenal a {nombre_cli}",
                            clave=f"semana_viernes:{cid}:{semana_iso}")

    # ── EL CALENDARIO DEL EQUIPO ─────────────────────────────────────────────
    if dia == 4:
        await tarea(a_quien=jenny, que="Mandar la newsletter y comprobar que sale bien",
                    clave=f"newsletter:{semana_iso}", origen="auto:calendario")
        await tarea(a_quien=jenny, que="Control de calidad de las conversaciones de ZeroChats",
                    clave=f"zerochats:{semana_iso}", origen="auto:calendario")
    if dia == 0:
        await tarea(a_quien=operaciones, que="Reunión con los entrenadores",
                    clave=f"reunion:{semana_iso}", origen="auto:calendario")

    # El cierre, en un solo update: las marca el sistema, igual que las creo.
    if por_cerrar:
        await db.tareas.update_many(
            {"clave": {"$in": sorted(por_cerrar)}, "hecha": False},
            {"$set": {"hecha": True, "hecha_por": None, "hecha_por_nombre": "sistema",
                      "hecha_at": ahora.isoformat()}},
        )

    return creadas


async def tarea_reporte_nuevo(db, *, client_id: str, nombre: str,
                              trainer_id: Optional[str]) -> None:
    """«Un cliente manda su reporte → Reporte nuevo de Nuria Garrido → su entrenador».
    Por evento, desde POST /reports; sin entrenador va a operaciones."""
    quien = await _destinatarios(db)
    await crear_tarea(db, a_quien=trainer_id or quien["operaciones"],
                      que=f"Reporte nuevo de {nombre}",
                      sobre_quien=client_id, sobre_quien_nombre=nombre,
                      clave=f"reporte_nuevo:{client_id}:{datetime.now(timezone.utc).date().isoformat()}",
                      origen="auto:reporte_nuevo")


async def tarea_baja_pedida(db, *, client_id: str, nombre: str, motivo: str) -> None:
    """«Ha pedido la baja. Motivo: me sale caro» → Jenny, «con tiempo de sobra para hablar
    con ella antes de que se acabe el ciclo». La llamará el flujo de la baja cuando exista
    (apartado «Mi plan y la baja»)."""
    quien = await _destinatarios(db)
    await crear_tarea(db, a_quien=quien["jenny"],
                      que=f"{nombre} ha pedido la baja. Motivo: «{motivo}». Hablar antes de que acabe su ciclo",
                      sobre_quien=client_id, sobre_quien_nombre=nombre,
                      clave=f"baja:{client_id}:{datetime.now(timezone.utc).date().isoformat()}",
                      origen="auto:baja_pedida")


async def tarea_intencion_de_baja(db, *, client_id: str, nombre: str, que: str,
                                  trainer_id: Optional[str] = None,
                                  para_hoy: bool = False) -> None:
    """El aviso AL MOMENTO del «no quiero renovar» con salida (P56 del doc 23-08): el
    cliente estuvo a punto de irse y eligió una alternativa (aplazar, revisión del plan,
    pasar a Mantenimiento). Va por el mismo canal que todo lo demás -- una tarea con su
    campanita (`crear_tarea` avisa al asignado) --, no por uno nuevo. `para_hoy` es la
    prioridad de la casa: la tarea cae en la bandeja de hoy, no en «lo que viene»."""
    quien = await _destinatarios(db)
    hoy = datetime.now(timezone.utc).date().isoformat()
    await crear_tarea(db, a_quien=trainer_id or quien["jenny"],
                      que=que,
                      para_cuando=hoy if para_hoy else None,
                      sobre_quien=client_id, sobre_quien_nombre=nombre,
                      clave=f"intencion_baja:{client_id}:{hoy}",
                      origen="auto:intencion_baja")
