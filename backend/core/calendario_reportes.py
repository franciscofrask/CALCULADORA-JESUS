"""
El calendario de reportes, como propiedad del PLAN y del CONTRATO (punto 44 del doc del 07-08).

Lo que habia: la cadencia estaba escrita en el codigo (`REPORT_RULES` y una funcion con tres
`if`: quincenal si la semana es par, mensual si semana % 4 == 3, semanal siempre). Los numeros
coinciden con lo que pide el documento, pero meter un plan con otro ritmo era tocar codigo, y
el ciclo de Premium no se podia expresar de ninguna manera.

LA IDEA: cada plan declara un PATRON DE SEMANAS que se repite. Eso lo modela todo, y ademas es
como lo describe Jesus para Premium -- "S1 check-in semanal, S2 check-in semanal, S3 reporte
mensual, S4 check-in semanal; en planes mas largos se sigue repitiendo esa logica".

    Gold      ["", "quincenal", "mensual", "quincenal"]   quincenal el miercoles de la 2,
                                                          mensual el viernes de la 3
    Silver    ["", "", "mensual", ""]                     solo el mensual
    Premium   ["semanal", "semanal", "mensual", "semanal"]
    ELM / Reto 60 días  []                                ninguno

El patron se repite: la semana 5 vuelve a la posicion 1, la 6 a la 2, y asi. Con el patron de
Gold, la 6 es quincenal y la 7 mensual, que es exactamente lo que hacia la regla vieja.

LA DURACION es del CONTRATO, no un supuesto: hay planes de 4 semanas y de 5. Y cambia cuando
entra el cliente en el ciclo -- los de 4 semanas entran en la semana 3 y los de 5 en la 4 --,
que es la penultima: el reporte se manda antes de terminar para poder ajustar de cara al
siguiente ciclo. Por eso `semana_de_entrada` tiene por defecto `duracion - 1`.

Todo esto se puede sobreescribir POR CLIENTE (`ciclo_semanas`, `semana_de_entrada`,
`calendario_reportes` en su perfil), porque el punto 36 manda: el contrato de cada cliente es
el que vale, y la tabla de planes es la plantilla de la que se copia.
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from core.tiempo import MADRID

# weekday(): lunes=0 ... domingo=6
DIAS = {"lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2, "jueves": 3,
        "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6}

# El dia en que se manda cada tipo, cuando el plan no dice otra cosa.
DIA_POR_DEFECTO = {"quincenal": "miercoles", "mensual": "viernes", "semanal": "domingo"}

ETIQUETA = {"quincenal": "Reporte quincenal", "mensual": "Reporte mensual",
            "semanal": "Reporte semanal"}

# El patron por defecto de un plan, deducido de los tipos de reporte que incluye. Es lo que
# hacia la regla vieja, escrito como patron: asi los 17 planes del catalogo siguen
# comportandose igual sin tener que declararlo uno a uno, y el que quiera otro ritmo solo
# tiene que poner el suyo.
def patron_por_defecto(tipos: List[str]) -> List[str]:
    tipos = [t for t in (tipos or []) if t in ETIQUETA]
    if not tipos:
        return []
    if "semanal" in tipos:
        # Premium y 6M: todas las semanas, y la 3 es la del mensual si tambien lo lleva.
        base = ["semanal"] * 4
        if "mensual" in tipos:
            base[2] = "mensual"
        return base
    patron = ["", "", "", ""]
    if "quincenal" in tipos:
        patron[1] = "quincenal"     # semana 2
        patron[3] = "quincenal"     # semana 4
    if "mensual" in tipos:
        patron[2] = "mensual"       # semana 3
    return patron


def calendario_del_plan(plan: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """{patron, dias} de un plan. Si no declara `calendario`, se deduce de sus reportes."""
    plan = plan or {}
    cal = dict(plan.get("calendario") or {})
    if not cal.get("patron"):
        tipos = ((plan.get("habilitaciones") or {}).get("reportes")) or []
        cal["patron"] = patron_por_defecto(tipos)
    dias = dict(DIA_POR_DEFECTO)
    dias.update(cal.get("dias") or {})
    cal["dias"] = dias
    return cal


def calendario_del_cliente(profile: Dict[str, Any], plan: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """El calendario que aplica a un cliente: el de su plan, salvo que su contrato diga otro.

    Devuelve tambien la duracion del ciclo y la semana en que entra, que son del contrato:
    hay clientes con ciclo de 4 semanas en un plan de 12 (es una de las 17 excepciones del
    punto 39, y ahora tiene donde vivir).
    """
    plan = plan or {}
    cal = calendario_del_plan(plan)
    propio = profile.get("calendario_reportes") or {}
    if propio.get("patron"):
        cal["patron"] = propio["patron"]
    if propio.get("dias"):
        cal["dias"] = {**cal["dias"], **propio["dias"]}

    duracion = (profile.get("ciclo_semanas")
                or (plan.get("ciclo") or {}).get("semanas")
                or plan.get("billing_cycle_weeks"))
    try:
        duracion = int(duracion) if duracion else None
    except (TypeError, ValueError):
        duracion = None

    # DESDE QUE SEMANA DEL PATRON entra este cliente. El documento dice "los de 4 semanas
    # entran cuando estan en Semana 3, y los de 5 cuando estan en Semana 4", y la frase
    # admite dos lecturas: que el patron empiece desplazado, o que las primeras semanas no
    # le toque nada.
    #
    # Se implementa como DESPLAZAMIENTO, y vacio por defecto. La otra lectura probada
    # dejaba a Gold sin ningun reporte hasta la semana 11 -- veintidos clientes en silencio
    # dos meses y medio --, y eso no puede ser lo que pide un documento cuyo ejemplo es
    # "quincenal el miercoles de la semana 2". Con el campo vacio el patron empieza en su
    # semana 1, que es lo que la app hacia hasta hoy: nadie cambia de comportamiento.
    #
    # PENDIENTE de que Jesus aclare que significa "entrar en el ciclo"; el campo ya esta y
    # es cambiar un numero.
    entrada = profile.get("semana_de_entrada")
    try:
        entrada = int(entrada) if entrada is not None else None
    except (TypeError, ValueError):
        entrada = None

    cal["duracion_semanas"] = duracion
    cal["semana_de_entrada"] = entrada
    return cal


def reporte_de_la_semana(cal: Dict[str, Any], semana: int) -> Optional[str]:
    """Que reporte toca en la semana `semana` del ciclo (1-based). None si ninguno."""
    patron = cal.get("patron") or []
    if not patron or not semana or semana < 1:
        return None
    # `semana_de_entrada` desplaza el patron: si entra en la 3, su primera semana cae en la
    # posicion 3 del patron. Vacio (lo normal) = empieza por la primera.
    desplazamiento = (cal.get("semana_de_entrada") or 1) - 1
    tipo = patron[(semana - 1 + desplazamiento) % len(patron)]
    return tipo or None


def dia_de_envio(cal: Dict[str, Any], tipo: str) -> int:
    """weekday() en que se manda ese tipo para este cliente."""
    nombre = (cal.get("dias") or {}).get(tipo) or DIA_POR_DEFECTO.get(tipo, "domingo")
    return DIAS.get(str(nombre).lower().strip(), 6)


def toca_en_la_semana(cal: Dict[str, Any], tipo: str, semana: int) -> bool:
    """¿Toca ESE tipo en esa semana? (equivalente al `_tipo_due_this_week` de antes)."""
    return reporte_de_la_semana(cal, semana) == tipo


# ── Cuándo abre y cuándo cierra cada reporte, en hora de España ───────────────
#
# Las horas son las del RELOJ del doc del 19-08 (que corrige al del 16-08): el quincenal
# del miércoles 10:00 al jueves 20:00, y el mensual del viernes 10:00 al lunes 18:00.
# Están AQUÍ, en el calendario, y no repartidas por los avisos, porque son el mismo dato
# que necesitan tres sitios: el aviso de apertura, el de último día y el de "no me llegó".
#
# OJO: la ventana con la que se ACEPTA el envío vive en `report_cadence.py`
# (`_submission_window`), con estas mismas horas desde el 19-08. Son dos cosas que tienen
# que acabar siendo una: cuando T7/T8 muevan la ventana real, que la lean de aquí.
HORAS_DEL_DOC = {
    # (hora a la que abre, días hasta el cierre, hora del cierre)
    "quincenal": (10, 1, 20),
    "mensual": (10, 3, 18),
    "semanal": (0, 0, 23),
}


def ventana_del_reporte(cal: Dict[str, Any], tipo: str,
                        inicio_semana: date) -> Optional[Dict[str, datetime]]:
    """{abre, cierra} de un reporte, en hora de España, para la semana de ciclo que
    empieza en `inicio_semana`.

    `inicio_semana` es el día en que arranca la semana de ciclo del cliente, que NO tiene
    por qué ser un lunes: el ciclo cuenta desde su fecha de alta. El día de envío (el
    miércoles del quincenal, el viernes del mensual) se busca dentro de esos siete días.
    """
    if tipo not in HORAS_DEL_DOC:
        return None
    hora_abre, dias, hora_cierra = HORAS_DEL_DOC[tipo]
    dia_envio = dia_de_envio(cal, tipo)
    abre_dia = inicio_semana + timedelta(days=(dia_envio - inicio_semana.weekday()) % 7)
    abre = datetime(abre_dia.year, abre_dia.month, abre_dia.day, hora_abre, tzinfo=MADRID)
    cierra_dia = abre_dia + timedelta(days=dias)
    cierra = datetime(cierra_dia.year, cierra_dia.month, cierra_dia.day,
                      hora_cierra, tzinfo=MADRID)
    return {"abre": abre, "cierra": cierra}
