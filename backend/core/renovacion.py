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
    """En que punto de su ciclo esta y si toca ya enseñarle la renovacion."""
    ahora = ahora or datetime.now(timezone.utc)
    fin = _fecha(perfil.get("fin_de_ciclo"))
    inicio = _fecha(perfil.get("arranque_lunes")) or _fecha(perfil.get("created_at"))

    if not fin:
        # Los clientes de antes del calendario de arranque no tienen fin de ciclo
        # guardado. Se cae a la semana del perfil, que es lo que habia.
        semana = int(perfil.get("week") or 1)
        return {"conocido": False, "semana": semana, "toca_renovar": semana >= 11,
                "dias_restantes": None, "fin": None}

    dias = (fin.date() - ahora.date()).days
    semana = max(1, ((ahora - inicio).days // 7) + 1) if inicio else int(perfil.get("week") or 1)
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
                      ajustes_de_macros: int) -> Dict[str, Any]:
    """Lo que ha conseguido en estas 12 semanas. Es lo primero que ve.

    El peso va en porcentaje, igual que en el informe mensual: medio kilo no significa
    lo mismo en alguien de 60 kg que en alguien de 120.
    """
    p0 = (reporte_primero or {}).get("weight")
    p1 = (reporte_ultimo or {}).get("weight")
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


def salidas(*, plan_actual: Optional[str], opciones_catalogo: Dict[str, Any],
            catalogo: Dict[str, Dict[str, Any]], precio_alta: Optional[float]) -> List[Dict[str, Any]]:
    """Las tres salidas del documento, en el orden en que se le ofrecen.

    `opciones_catalogo` es lo que devuelve models.user.opciones_de_renovacion: de ahi
    salen las reglas (si puede seguir igual, si conserva precio, cual es la de salida).
    """
    fuera: List[Dict[str, Any]] = []
    actual = (plan_actual or "").lower().strip()
    contratables = opciones_catalogo.get("opciones") or []

    # 1) Seguir igual. Solo si su plan se sigue vendiendo, y con SU precio.
    if opciones_catalogo.get("puede_seguir_igual") and actual in catalogo:
        info = catalogo[actual]
        precio = precio_alta if precio_alta else info.get("precio")
        fuera.append({
            "tipo": "renovar",
            "plan": actual,
            "nombre": info.get("name"),
            "precio": precio,
            "precio_congelado": bool(precio_alta and precio_alta != info.get("precio")),
            "titulo": "Seguir igual",
            "detalle": "Otras 12 semanas con lo mismo.",
        })

    # 2) Cambiar de nivel. Los que no tiene, mas caros primero: subir es lo que se quiere
    #    empujar, pero sin esconder que tambien puede bajar.
    otros = sorted((c for c in contratables if c != actual),
                   key=lambda c: catalogo.get(c, {}).get("precio") or 0, reverse=True)
    for code in otros:
        info = catalogo.get(code) or {}
        sube = (info.get("precio") or 0) > (catalogo.get(actual, {}).get("precio") or 0)
        fuera.append({
            "tipo": "cambiar",
            "plan": code,
            "nombre": info.get("name"),
            "precio": info.get("precio"),
            "precio_congelado": False,
            "por_llamada": es_por_llamada(code),
            "titulo": "Subir a " + (info.get("name") or code) if sube else "Pasar a " + (info.get("name") or code),
            "detalle": ("Hablamos antes de entrar." if es_por_llamada(code)
                        else "Mas gente encima de tus numeros." if sube
                        else "Menos acompañamiento, mismo metodo."),
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
    return {
        "ciclo": estado,
        "resumen": resumen,
        "salidas": salidas(plan_actual=perfil.get("plan"), opciones_catalogo=opciones_catalogo,
                           catalogo=catalogo, precio_alta=perfil.get("precio_alta")),
        # Si no hace nada, Stripe cobra solo: conviene decirlo para que no parezca que
        # se le va a cortar el acceso.
        "renueva_solo": not estado.get("ya_vencido"),
        "motivo_cambio": opciones_catalogo.get("motivo"),
    }
