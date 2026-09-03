"""
LA VENTANA DEL BOTON «REVISAR» de Mis macros (tarea 7.3 del 21-08, hueco 1c del doc).

El cuestionario de ajuste (quiz_ajuste) no se pide: la app le abre la ventana al cliente
cuando toca y se la cierra cuando no. El boton se queda siempre visible; apagado, dice
cuando se enciende («Se abre el 1 de septiembre»). Esta es la funcion que decide eso.

La regla, por modo de calculadora del plan (habilitaciones.calculadora):

    autogestion     una vez al mes: abierta si su ultimo quiz_ajuste tiene mas de un mes.
                    Sin ningun quiz_ajuste hecho, abierta (es su primer ajuste).
    personalizado   cuando toca su ciclo: la semana del ciclo en la que su calendario
                    trae el reporte «mensual», que es la de la revision con su coach.
    sin_ajuste      cerrada siempre, con el motivo escrito para el cliente.

La fecha del ultimo quiz_ajuste sale de macro_history POR effective_date, NUNCA por
created_at: en las filas migradas de Calma created_at es el dia de la migracion, no el
del ajuste, y ya mordio.

Las fechas se cuentan en el dia de ESPAÑA (core/tiempo.hoy_madrid), nunca date.today():
de 00:00 a 02:00 el dia del servidor va por detras del del cliente.

Devuelve siempre {"abierta": bool, "se_abre": "YYYY-MM-DD"|None, "motivo": str}:
`se_abre` es la fecha en la que se enciende si se sabe, y `motivo` es la frase que se le
puede leer al cliente tal cual.

ANOTADO (huecos de datos, no se inventa nada):
  - En personalizado sin patron con «mensual» (o sin plan en el catalogo) la ventana se
    queda cerrada con motivo generico: no hay ciclo del que sacar la fecha.
  - `cycle_start` falta en muchos perfiles; se cae a `created_at` igual que core/cycle.
"""
from calendar import monthrange
from datetime import date, timedelta
from typing import Any, Dict, Optional

# ── Fechas ───────────────────────────────────────────────────────────────────

def un_mes_despues(d: date) -> date:
    """El mismo dia del mes siguiente, recortado si no existe (31 ene -> 28/29 feb)."""
    anio = d.year + (1 if d.month == 12 else 0)
    mes = 1 if d.month == 12 else d.month + 1
    return date(anio, mes, min(d.day, monthrange(anio, mes)[1]))


def _iso(d: Optional[date]) -> Optional[str]:
    return d.isoformat() if d else None


def _abierta(motivo: str) -> Dict[str, Any]:
    return {"abierta": True, "se_abre": None, "motivo": motivo}


def _cerrada(motivo: str, se_abre: Optional[date] = None) -> Dict[str, Any]:
    return {"abierta": False, "se_abre": _iso(se_abre), "motivo": motivo}


# ── Las tres rutas, puras (sin base): son lo que se prueba ───────────────────

def ventana_autogestion(ultimo_quiz: Optional[date], hoy: date) -> Dict[str, Any]:
    """Modo calculadora: una revision al mes, contado desde su ultimo quiz_ajuste."""
    if ultimo_quiz is None:
        return _abierta("Todavía no has hecho ninguna revisión.")
    se_abre = un_mes_despues(ultimo_quiz)
    if hoy >= se_abre:
        return _abierta("Ha pasado un mes desde tu última revisión.")
    return _cerrada("Tu revisión es una vez al mes.", se_abre)


def ventana_por_ciclo(cal: Dict[str, Any], inicio_ciclo: date, hoy: date) -> Dict[str, Any]:
    """Modo personalizado: abierta la semana del ciclo en que su calendario trae el
    reporte «mensual», que es cuando se le revisan los macros con su coach.

    `cal` es lo que devuelve core/calendario_reportes.calendario_del_cliente (patron,
    duracion_semanas, semana_de_entrada); `inicio_ciclo` es su cycle_start en dia de
    España. La semana se cuenta igual que core/cycle.compute_cycle: dias de calendario
    partido por 7, envolviendo en la duracion del ciclo si la hay.
    """
    from core.calendario_reportes import reporte_de_la_semana

    patron = [p for p in (cal.get("patron") or [])]
    if "mensual" not in patron:
        # ANOTADO en el docstring del modulo: sin «mensual» en el patron no hay fecha
        # de ciclo que dar. Cerrada con la frase generica.
        return _cerrada("Tus macros se revisan con tu entrenador, en tu ciclo.")

    duracion = cal.get("duracion_semanas")

    def semana_de(transcurridas: int) -> int:
        if duracion and duracion > 0:
            return (transcurridas % duracion) + 1
        return transcurridas + 1

    transcurridas = max(0, (hoy - inicio_ciclo).days) // 7
    if reporte_de_la_semana(cal, semana_de(transcurridas)) == "mensual":
        return _abierta("Esta semana toca tu revisión de ciclo.")

    # La proxima semana con «mensual»: como mucho una vuelta entera al patron (o al
    # ciclo). El inicio de esa semana es la fecha que se le enseña en gris.
    vueltas = max(len(patron), int(duracion or 0)) or 1
    for k in range(1, vueltas + 1):
        if reporte_de_la_semana(cal, semana_de(transcurridas + k)) == "mensual":
            se_abre = inicio_ciclo + timedelta(days=7 * (transcurridas + k))
            return _cerrada("Tu revisión llega con tu ciclo.", se_abre)
    return _cerrada("Tus macros se revisan con tu entrenador, en tu ciclo.")


def ventana_sin_ajuste() -> Dict[str, Any]:
    return _cerrada("Tu plan no incluye revisiones de macros.")


# ── El orquestador: lee el perfil y elige la ruta ────────────────────────────

async def ventana_de_revision(db, perfil: Dict[str, Any],
                              hoy: Optional[date] = None,
                              catalogo: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Dado el perfil, la ventana del boton Revisar. Ver la regla en el modulo."""
    from core.plan_access import modo_calculadora
    from core.tiempo import a_madrid, hoy_madrid

    hoy = hoy or hoy_madrid()
    # CON EL CATALOGO QUE LLEGA, no en seco (2-09). Estaba anotado como pendiente en
    # `routes/users.py`: la eleccion de plan de aqui abajo ya usaba `catalogo`, pero la RAMA
    # se decidia con el catalogo de fabrica, asi que un override de la Calculadora en el panel
    # mandaba esta fecha por el camino equivocado -- autogestion contra personalizado -- y
    # entonces «Mis macros» y el boton de Seguimiento contaban cosas distintas del mismo
    # cliente. `modo_calculadora` ya aceptaba el catalogo; solo faltaba dárselo.
    modo = modo_calculadora(perfil.get("plan"), catalogo)

    if modo == "autogestion":
        # El ultimo quiz_ajuste, POR effective_date. Nunca created_at: en las filas
        # migradas es el dia de la migracion.
        ultimo = None
        if perfil.get("id"):
            filas = await db.macro_history.find(
                {"client_id": perfil["id"], "origen": "quiz_ajuste"},
                {"_id": 0, "effective_date": 1},
            ).sort("effective_date", -1).limit(1).to_list(1)
            fecha = (filas[0].get("effective_date") or "")[:10] if filas else ""
            try:
                ultimo = date.fromisoformat(fecha) if fecha else None
            except ValueError:
                ultimo = None
        return ventana_autogestion(ultimo, hoy)

    if modo == "personalizado":
        from core.calendario_reportes import calendario_del_cliente
        from models.user import PLAN_CATALOG, codigo_de_plan
        plan = (catalogo or PLAN_CATALOG).get(codigo_de_plan(perfil.get("plan"))) or {}
        cal = calendario_del_cliente(perfil, plan)
        # El ancla del ciclo, igual que core/cycle: cycle_start y, si falta, created_at.
        ancla = a_madrid(perfil.get("cycle_start")) or a_madrid(perfil.get("created_at"))
        if not ancla:
            # ANOTADO: sin fecha de inicio no hay semana de ciclo que calcular.
            return _cerrada("Tus macros se revisan con tu entrenador, en tu ciclo.")
        return ventana_por_ciclo(cal, ancla.date(), hoy)

    return ventana_sin_ajuste()
