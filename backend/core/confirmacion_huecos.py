"""
La confirmacion de huecos (especificacion 31-07-2026, partes 6 y 7).

Sustituye a los deslizadores de cumplimiento del reporte. La idea del documento es que
el cumplimiento NO se le pregunta:

    "No registraste la dieta 4 días de los últimos 14. ¿Es porque no la hiciste, o
     porque sí la hiciste y no la apuntaste?"

    "El cumplimiento se obtiene así, no preguntándole que se puntúe. Los deslizadores se
     quedan solo para lo que no se puede deducir: cuánto le ha costado y las sensaciones."

La diferencia es de fondo. Un deslizador mide lo que el cliente CREE que ha cumplido, que
es una opinion; los dias sin registrar son un hecho, y lo unico que no sabemos de ellos es
si no lo hizo o si lo hizo y no lo apunto. Eso es lo unico que se pregunta.

Este modulo es calculo puro: no toca base de datos ni HTTP, para poder probarlo entero.
"""
from typing import Any, Dict, List, Optional

# Lo que puede contestar a un hueco.
NO_LO_HICE = "no_lo_hice"
SI_PERO_NO_APUNTE = "si_pero_no_apunte"
RESPUESTAS = (NO_LO_HICE, SI_PERO_NO_APUNTE)

# ─────────────────────────────────────────────────────────────────────────────
# EL HUECO DE ENTRENAMIENTO, APAGADO (punto 41 del doc del 19-08)
#
#     «El reporte va a decir "no registraste 16 entrenamientos". Los entrenos previstos se
#      calculan multiplicando los días de entreno. Con el cuatro por defecto empieza a
#      salir, y no hay ningún sitio donde marcar que has entrenado.
#      LA RESPUESTA: quita ese dato del reporte. Decirle a alguien que no ha entrenado
#      cuando sí ha entrenado es peor que no decirle nada.
#      Cuando exista dónde marcarlo, se vuelve a encender.»
#
# Los previstos son una MULTIPLICACIÓN (días de entreno por semana × semanas), y los
# hechos salen de `checkins.trained`, que solo se escribe si el cliente cierra el día. O
# sea: un lado inventado y el otro incompleto. El que entrena cinco veces y no cierra
# ningún día lee que no ha entrenado ni una vez.
#
# Se apaga AQUÍ y no en quien llama, para que sea una sola línea la que lo encienda el día
# que exista un registro de sesiones de verdad. Los previstos se siguen recibiendo y
# devolviendo: el dato no se pierde, solo deja de convertirse en una acusación.
SE_REGISTRAN_LOS_ENTRENOS = False


def _pct(hechos: float, total: float) -> int:
    return int(round(100 * hechos / total)) if total > 0 else 0


def huecos_del_periodo(dias_periodo: int, dias_con_dieta: int, dias_con_entreno: int,
                       entrenos_previstos: Optional[int] = None) -> Dict[str, Any]:
    """Los huecos que hay que confirmar, con la pregunta ya redactada.

    `entrenos_previstos` es cuantos entrenos TOCABAN en el periodo (no todos los dias son
    de entrenar). Si no se sabe, no se pregunta por el entreno: inventarse un hueco de
    entrenamiento contando los dias de descanso como fallos seria acusarle de algo que no
    ha pasado.
    """
    dias_periodo = max(0, int(dias_periodo or 0))
    dias_con_dieta = max(0, min(int(dias_con_dieta or 0), dias_periodo))

    huecos: List[Dict[str, Any]] = []

    sin_dieta = dias_periodo - dias_con_dieta
    if sin_dieta > 0:
        huecos.append({
            "tipo": "dieta",
            "dias": sin_dieta,
            "de": dias_periodo,
            # «de los últimos 1» no lo dice nadie (punto 4.18). Con un solo día del periodo
            # la frase entera cambia, no basta con quitarle la ese.
            "pregunta": (
                (f"Ayer no registraste la dieta. "
                 if dias_periodo == 1 else
                 f"No registraste la dieta {sin_dieta} "
                 f"{'día' if sin_dieta == 1 else 'días'} de los últimos {dias_periodo}. ")
                + "¿Es porque no la hiciste, o porque sí la hiciste y no la apuntaste?"
            ),
        })

    if entrenos_previstos and SE_REGISTRAN_LOS_ENTRENOS:
        previstos = max(0, int(entrenos_previstos))
        hechos = max(0, min(int(dias_con_entreno or 0), previstos))
        sin_entreno = previstos - hechos
        if sin_entreno > 0:
            huecos.append({
                "tipo": "entrenamiento",
                "dias": sin_entreno,
                "de": previstos,
                "pregunta": (
                    f"No registraste {sin_entreno} "
                    f"{'entrenamiento' if sin_entreno == 1 else 'entrenamientos'} de los "
                    f"{previstos} que tenías. "
                    "¿Es porque no los hiciste, o porque sí los hiciste y no los apuntaste?"
                ),
            })

    return {
        "dias_periodo": dias_periodo,
        "dias_con_dieta": dias_con_dieta,
        "dias_con_entreno": max(0, int(dias_con_entreno or 0)),
        "entrenos_previstos": entrenos_previstos,
        "huecos": huecos,
        # Sin huecos no hay nada que confirmar: lo registró todo.
        "hay_que_preguntar": bool(huecos),
    }


def cumplimiento(estado: Dict[str, Any], respuestas: Dict[str, str]) -> Dict[str, Any]:
    """El cumplimiento real, contando como hecho lo que dice que hizo sin apuntar.

    `respuestas` es {"dieta": "si_pero_no_apunte", "entrenamiento": "no_lo_hice"}. Un hueco
    sin contestar cuenta como NO hecho: es lo unico que consta.
    """
    dias = estado.get("dias_periodo") or 0
    con_dieta = estado.get("dias_con_dieta") or 0
    por_tipo = {h["tipo"]: h for h in (estado.get("huecos") or [])}

    hueco_dieta = por_tipo.get("dieta")
    if hueco_dieta and (respuestas or {}).get("dieta") == SI_PERO_NO_APUNTE:
        con_dieta += hueco_dieta["dias"]

    out = {
        "dieta_pct": _pct(con_dieta, dias),
        "dieta_dias": con_dieta,
        "dieta_de": dias,
        # De donde sale: para que el equipo no confunda esto con una opinion del cliente.
        "origen": "registro",
    }

    hueco_entreno = por_tipo.get("entrenamiento")
    previstos = estado.get("entrenos_previstos")
    # Y tampoco se saca un porcentaje de entrenamiento mientras el hueco esté apagado: sin
    # el hueco no hay forma de decir «los hice y no los apunté», así que el porcentaje sería
    # siempre el de los días que casualmente cerró.
    if previstos and SE_REGISTRAN_LOS_ENTRENOS:
        hechos = min(estado.get("dias_con_entreno") or 0, previstos)
        if hueco_entreno and (respuestas or {}).get("entrenamiento") == SI_PERO_NO_APUNTE:
            hechos += hueco_entreno["dias"]
        out.update({
            "entreno_pct": _pct(hechos, previstos),
            "entreno_hechos": hechos,
            "entreno_de": previstos,
        })

    return out


def limpiar_respuestas(datos: Any) -> Dict[str, str]:
    """Se queda solo con lo que es una respuesta valida a un hueco."""
    if not isinstance(datos, dict):
        return {}
    return {
        str(k): v for k, v in datos.items()
        if k in ("dieta", "entrenamiento") and v in RESPUESTAS
    }
