"""
La renovacion de la semana 12 (especificacion 31-07-2026, partes 1 y 3).

    "Su foto del dia 1 al lado de la de hoy, su evolucion y su resumen del ciclo.
     Tres salidas: renovar, subir de nivel, o salir a la membresia."

Lo importante de esta pantalla es QUE ORDEN tienen las cosas: primero lo que ha
conseguido, y solo despues lo que puede hacer. Al reves seria un cobro con fotos de
adorno; asi es un balance del que sale una decision.

Sobre el cobro: si no hace nada, Stripe cobra solo el dia que acaba su ciclo -- para eso
se ancla al lunes (ver core/calendario_arranque.py). Esta pantalla no es un paywall: es
donde decide si quiere cambiar algo antes de que eso pase.

Y el precio: "se congela mientras el cliente no se de de baja". Si renueva en su mismo
plan paga lo que pagaba, aunque el catalogo haya subido. Si cambia de plan, paga el del
plan nuevo.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


# Cuando se le empieza a enseñar. El documento avisa en la semana 11 ("tu ciclo acaba en
# una semana"), asi que la pantalla tiene que estar viva antes de ese aviso.
SEMANAS_ANTES_DE_AVISAR = 2


def _fecha(iso: Optional[str]) -> Optional[datetime]:
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d


def estado_del_ciclo(perfil: Dict[str, Any], ahora: Optional[datetime] = None) -> Dict[str, Any]:
    """En que punto de su ciclo esta y si toca ya enseñarle la renovacion.

    LA SEMANA SALE DE core/cycle, la misma cuenta que Mi perfil (cazado en el
    recorrido movil del 23-08: el perfil decia «semana 10 de 12» y esta pantalla
    «semana 1», porque aqui se leia `perfil["week"]`, un campo muerto que en los
    migrados vale 1 para siempre; la semana de verdad se calcula desde cycle_start).
    """
    from core.cycle import compute_cycle

    ahora = ahora or datetime.now(timezone.utc)
    fin = _fecha(perfil.get("fin_de_ciclo"))
    # Con ancla (cycle_start o created_at) manda la cuenta; sin ninguna, lo guardado.
    if perfil.get("cycle_start") or perfil.get("created_at"):
        semana = int(compute_cycle(perfil, ahora).get("week") or 1)
    else:
        semana = int(perfil.get("week") or 1)

    if not fin:
        # Los clientes de antes del calendario de arranque no tienen fin de ciclo
        # guardado: se sabe la semana, no el dia exacto del final.
        return {"conocido": False, "semana": semana, "toca_renovar": semana >= 11,
                "dias_restantes": None, "fin": None}

    dias = (fin.date() - ahora.date()).days
    return {
        "conocido": True,
        "semana": semana,
        "fin": fin.isoformat(),
        "dias_restantes": dias,
        "toca_renovar": dias <= SEMANAS_ANTES_DE_AVISAR * 7,
        "ya_vencido": dias < 0,
    }


def resumen_del_ciclo(*, reporte_primero: Optional[Dict[str, Any]],
                      reporte_ultimo: Optional[Dict[str, Any]],
                      perfil: Dict[str, Any],
                      dias_dieta: int, dias_totales: int,
                      ajustes_de_macros: int,
                      apuntes_de_peso: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Lo que ha conseguido en estas 12 semanas. Es lo primero que ve.

    El peso va en porcentaje, igual que en el informe mensual: medio kilo no significa
    lo mismo en alguien de 60 kg que en alguien de 120.
    """
    # EL PESO DE AHORA SALE DE SU SERIE, no del ultimo reporte (19-08).
    #
    # La serie es donde caen TODOS los pesajes vengan de donde vengan -- del reporte, de la
    # calculadora, del ajuste del coach -- y es de donde lee «Mis macros» (punto 30). Mirando
    # solo el ultimo reporte pasaban dos cosas: al que se peso despues de su ultimo reporte se
    # le resumia el ciclo con un peso viejo, y al que no tiene ningun reporte -- pero si
    # pesajes -- se le enseñaba el resumen sin peso y con «0 kg» de cambio.
    # Y es LA MISMA CURVA que pinta «Mis macros» -- serie mas los pesos que viajaron dentro de
    # un ajuste --, no solo la serie: si no, dos pantallas de la misma app cuentan cosas
    # distintas del mismo cliente. Y si no hay ni eso -- perfiles de antes de que existiera la
    # serie -- queda el peso suelto de la ficha, que es el que el cliente ve en su pantalla.
    from core.series_cliente import curva_de_peso

    curva = curva_de_peso((perfil or {}).get("pesos"), apuntes_de_peso)
    p0 = (reporte_primero or {}).get("weight")
    p1 = ((curva[-1]["peso"] if curva else None)
          or (reporte_ultimo or {}).get("weight")
          or (perfil or {}).get("weight"))
    # Y sin reporte de partida, el primer pesaje suyo hace de «antes»: es el mismo dato y es
    # mejor que no enseñarle nada.
    if not p0 and curva:
        p0 = curva[0]["peso"]
    cambio_pct = None
    if p0 and p1 and p0 > 0:
        cambio_pct = round((p1 - p0) / p0 * 100, 1)

    fotos_antes = [f for f in ((reporte_primero or {}).get("photos") or []) if f][:3]
    fotos_ahora = [f for f in ((reporte_ultimo or {}).get("photos") or []) if f][:3]

    return {
        "peso": {"antes": p0, "ahora": p1,
                 "cambio_kg": round(p1 - p0, 1) if (p0 and p1) else None,
                 "cambio_pct": cambio_pct},
        "grasa": {"antes": (reporte_primero or {}).get("body_fat"),
                  "ahora": perfil.get("body_fat")},
        # "Su foto del dia 1 al lado de la de hoy". Si falta alguna de las dos, no se
        # enseña la comparacion a medias: se dice que falta.
        "fotos": {"antes": fotos_antes, "ahora": fotos_ahora,
                  "comparables": bool(fotos_antes and fotos_ahora)},
        "constancia": {
            "dias_registrados": dias_dieta,
            "dias_totales": max(1, dias_totales),
            "pct": min(100, round(dias_dieta / max(1, dias_totales) * 100)),
        },
        "ajustes_de_macros": ajustes_de_macros,
    }


#: Planes que NO se venden desde la app: se cierran hablando por telefono.
#:
#: La pantalla de renovacion ofrecia el Nivel 3 con su precio y su flecha, o sea invitando a
#: pagar 1.500 € por dentro un plan que el propio catalogo dice que se contrata por llamada.
#: En /planes ya sale bien -- «Agendar una llamada» --, asi que la renovacion vendia lo mismo
#: mucho peor (Jesus, 11-08).
#:
#: Esto DEBERIA ser una casilla del catalogo de planes, y Jesus lo pide asi en su bloque 7:
#: mientras no exista, el criterio vive aqui, en un solo sitio y con su nombre, en vez de
#: repetido a mano por las pantallas.
PLANES_POR_LLAMADA = {"nivel3"}


def es_por_llamada(plan: Optional[str]) -> bool:
    return (plan or "").lower().strip() in PLANES_POR_LLAMADA


def _en_una_frase(info: Dict[str, Any]) -> str:
    """Que te llevas con este plan, terminado en punto. Vacio si el catalogo no lo dice."""
    frase = (info.get("en_una_linea") or "").strip()
    return f"{frase.rstrip('.')}." if frase else ""


def periodo_de_cobro(info: Dict[str, Any]) -> str:
    """"mes" si el plan se cobra al mes, "ciclo" si por ciclo. Sale del catalogo
    (ciclo.tipo), no del nombre del plan: es el dato del que Mi perfil y la renovacion
    sacan el «/mes» o el «/ciclo» (P51 del doc 23-08)."""
    tipo = ((info.get("ciclo") or {}).get("tipo") or "").lower().strip()
    return "mes" if tipo == "mensual" else "ciclo"


def _que_recibe(info: Dict[str, Any]) -> str:
    """El respaldo cuando el plan no trae `en_una_linea`: la frase se saca de sus
    habilitaciones, que es lo que de verdad recibe. Antes aqui vivia «Más gente encima
    de tus números» para todo lo que costara mas, y en un plan de autogestion como ELM
    era mentira (P53 y P54 del doc 23-08)."""
    hab = info.get("habilitaciones") or {}
    piezas = []
    if (hab.get("acompanamiento") or "").startswith("con_entrenador"):
        piezas.append("Con entrenador detrás")
    else:
        piezas.append("Sin entrenador, a tu ritmo")
    rutina = hab.get("rutina")
    if rutina == "personalizada":
        piezas.append("rutina personalizada")
    elif rutina in ("del_mes", "opcional"):
        piezas.append("rutina del mes")
    reportes = hab.get("reportes") or []
    if reportes:
        piezas.append(f"reporte {reportes[0]}")
    return " · ".join(piezas) + "."


def salidas(*, plan_actual: Optional[str], opciones_catalogo: Dict[str, Any],
            catalogo: Dict[str, Dict[str, Any]], precio_alta: Optional[float],
            suscripcion_viva: bool = False) -> List[Dict[str, Any]]:
    """Las tres salidas del documento, en el orden en que se le ofrecen.

    `opciones_catalogo` es lo que devuelve models.user.opciones_de_renovacion: de ahi
    salen las reglas (si puede seguir igual, si conserva precio, cual es la de salida).

    `suscripcion_viva` es si Stripe le sigue cobrando solo. Solo importa para el plan
    antiguo reabierto: al que todavia tiene su suscripcion en pie no hay que mandarle a
    pagar otra vez (el checkout lo rechazaria, y con razon).
    """
    fuera: List[Dict[str, Any]] = []
    actual = (plan_actual or "").lower().strip()
    contratables = opciones_catalogo.get("opciones") or []

    # 1) Seguir igual. Solo si su plan se sigue vendiendo, y con SU precio.
    #
    # O si es un plan antiguo que el admin ha reabierto para los suyos (Francisco, 16-08).
    # Ese caso lleva `por_checkout`: al retirar un plan las suscripciones dejan de renovar
    # solas, asi que decirle «no tienes que hacer nada» seria mentirle y quedarse sin
    # cobrar. Va a la pasarela como cualquier otra salida.
    if opciones_catalogo.get("puede_seguir_igual") and actual in catalogo:
        info = catalogo[actual]
        precio = precio_alta if precio_alta else info.get("precio")
        legacy = bool(opciones_catalogo.get("renovacion_legacy")) and not suscripcion_viva

        # RENOVAR COBRA, salvo que haya una suscripcion viva que lo haga sola (24-08).
        #
        # `por_checkout` solo se encendia para el legacy reabierto, asi que a un cliente
        # de nivel1, nivel2, ELM o Mantenimiento se le decia «Perfecto, seguimos. No
        # tienes que hacer nada mas» y no se llamaba a nadie: llegaba el fin de ciclo y se
        # quedaba caducado creyendo que habia renovado. Dos parrafos mas arriba, la misma
        # pantalla le acaba de decir que su plan no se renueva solo.
        #
        # La regla de verdad es esa: desde el 20-08 NINGUN plan renueva solo (todos son de
        # pago unico), asi que lo unico que justifica el atajo es una suscripcion viva de
        # las de antes. Y solo se manda a la pasarela lo que se puede cobrar de verdad:
        # un plan que se sigue vendiendo y con su precio en Stripe. Los planes antiguos
        # sin precio configurado se quedan como estaban -- ese es otro arreglo, y espera
        # una decision de cuanto cobrarles.
        se_vende_hoy = (info.get("estado") == "activo"
                        and float(info.get("precio") or 0) > 0
                        and bool(info.get("stripe_price_env")))
        fuera.append({
            "tipo": "renovar",
            "plan": actual,
            "nombre": info.get("name"),
            "precio": precio,
            "periodo": periodo_de_cobro(info),
            "precio_congelado": bool(precio_alta and precio_alta != info.get("precio")),
            "por_checkout": legacy or (not suscripcion_viva and se_vende_hoy),
            # El plan que se cierra hablando tampoco se renueva solo por la pasarela: el
            # front lo lleva al chat, como hace con «Cambiar a» ese mismo plan. Sin esto,
            # al renovar se le abriria un cobro de 1.500 EUR por su cuenta.
            "por_llamada": es_por_llamada(actual),
            "titulo": "Seguir igual",
            # La duracion sale del catalogo: a un plan mensual (ELM, Mantenimiento) se le
            # decia «otras 12 semanas» con toda la cara (cazado con el P51 del 23-08).
            "detalle": ("Sigues en tu plan de siempre, con todo lo que incluye." if legacy
                        else "Otro mes con lo mismo." if periodo_de_cobro(info) == "mes"
                        else f"Otras {(info.get('ciclo') or {}).get('semanas')} semanas con lo mismo."
                        if (info.get("ciclo") or {}).get("semanas")
                        else "Otro ciclo con lo mismo."),
        })

    # 2) Cambiar de nivel. Los que no tiene, mas caros primero: subir es lo que se quiere
    #    empujar, pero sin esconder que tambien puede bajar.
    otros = sorted((c for c in contratables if c != actual),
                   key=lambda c: catalogo.get(c, {}).get("precio") or 0, reverse=True)
    for code in otros:
        info = catalogo.get(code) or {}
        fuera.append({
            "tipo": "cambiar",
            "plan": code,
            "nombre": info.get("name"),
            "precio": info.get("precio"),
            "periodo": periodo_de_cobro(info),
            "precio_congelado": False,
            "por_llamada": es_por_llamada(code),
            # «Cambiar a», no «Subir a» ni «Pasar a» (P54 del doc 23-08): son planes
            # distintos, no escalones. Desde un plan de 177 € salia «Subir a El Lunes
            # Empiezo · 97 €», que ni sube ni tiene sentido como escalera.
            "titulo": "Cambiar a " + (info.get("name") or code),
            # La frase la pone el catalogo (`en_una_linea`) y, si el plan no la trae, se
            # saca de sus habilitaciones: siempre dice QUE RECIBE, nunca compara precios.
            "detalle": _en_una_frase(info) or (
                "Hablamos antes de entrar." if es_por_llamada(code)
                else _que_recibe(info)),
        })

    # 3) Salir a la membresia. Es la ultima y se dice como lo que es, sin adornos.
    salida = opciones_catalogo.get("salida")
    if salida and salida in catalogo:
        info = catalogo[salida]
        fuera.append({
            "tipo": "salida",
            "plan": salida,
            "nombre": info.get("name"),
            "precio": info.get("precio"),
            "periodo": periodo_de_cobro(info),
            "precio_congelado": False,
            "titulo": "Dejarlo por ahora",
            "detalle": "Te quedas con la app y tus datos por "
                       f"{info.get('precio'):.0f} € al mes. Puedes volver cuando quieras."
                       if info.get("precio") else "Te quedas con la app y tus datos.",
        })

    return fuera


def montar_renovacion(*, perfil: Dict[str, Any], catalogo: Dict[str, Dict[str, Any]],
                      opciones_catalogo: Dict[str, Any], resumen: Dict[str, Any],
                      ahora: Optional[datetime] = None) -> Dict[str, Any]:
    """Todo lo de la pantalla: primero lo conseguido, despues lo que puede hacer."""
    estado = estado_del_ciclo(perfil, ahora)
    # Los estados de Stripe en los que se le sigue cobrando sin que haga nada.
    suscripcion_viva = perfil.get("subscription_status") in ("active", "trialing")
    fuera = salidas(plan_actual=perfil.get("plan"), opciones_catalogo=opciones_catalogo,
                    # La MISMA cascada que el cobro (routes/billing.py): lo que tiene
                    # apuntado el perfil manda; sin ella la pantalla enseñaba el precio de
                    # catálogo y el checkout cobraba el congelado.
                    catalogo=catalogo, precio_alta=perfil.get("price") or perfil.get("precio_alta"),
                    suscripcion_viva=suscripcion_viva)
    return {
        "ciclo": estado,
        "resumen": resumen,
        "salidas": fuera,
        # «Se renueva solo» SOLO si Stripe le sigue cobrando de verdad (doc 57, repaso del
        # 21-08). Desde el 20-08 ningun plan del catalogo renueva solo, y esta frase seguia
        # saliendo para cualquier plan vivo: prometia una renovacion automatica que ya no
        # existe, justo lo contrario del aviso de «renueva antes de que acabe».
        "renueva_solo": (not estado.get("ya_vencido") and suscripcion_viva),
        "motivo_cambio": opciones_catalogo.get("motivo"),
    }
