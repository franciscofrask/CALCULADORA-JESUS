"""
El informe que recibe el cliente despues de su reporte mensual.

Especificacion del 31-07-2026, parte 6. Ocho apartados:

  1. donde esta en su ciclo
  2. el peso, con el ritmo EN PORCENTAJE (no en kilos)
  3. el porcentaje de grasa
  4. tres o cuatro fotos, no dos
  5. el cumplimiento, en verde y rojo
  6. los macros que le tocaban al lado de los que comio
  7. sus macros nuevos, con la explicacion
  8. como va respecto a gente de su perfil

Y dos condiciones que manda el documento:

  - "sin fotos no se genera informe": comparar es la mitad del informe, y sin la foto de
    hoy no hay nada que comparar. Se devuelve el motivo para poder pedirselas.
  - "el objetivo de ritmo sale de su perfil y no es el mismo para todos": no se puede
    felicitar igual a quien viene del 35 % de grasa que a quien esta al 12 %.

El apartado 8 (la evolucion de referencia) todavia no tiene de donde salir: es otro de
los pendientes de la parte 8 del documento. Se devuelve `disponible: False` en vez de
inventar una comparacion, para que la pantalla lo pueda ocultar sin fingir un dato.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# El interruptor del punto 41 vive en un solo sitio: mientras no haya donde marcar una
# sesion, ni el reporte pregunta por los entrenos que faltan ni el informe saca un
# porcentaje de ellos.
from core.confirmacion_huecos import SE_REGISTRAN_LOS_ENTRENOS


# ── El ritmo que le toca ──────────────────────────────────────────────────────
# En porcentaje del peso corporal POR SEMANA, que es como lo pide el documento: medio
# kilo no significa lo mismo en alguien de 60 kg que en alguien de 120.
#
# OJO: estos tramos son un punto de partida razonable (los habituales en definicion y
# volumen), NO un numero que venga del documento. Jesus tiene que validarlos; cuando lo
# haga se cambian aqui y el informe entero cambia con ellos.
RITMO_DEFINICION = (
    (30.0, 0.75, 1.25),   # de 30 % de grasa para arriba: puede permitirse mas
    (20.0, 0.50, 1.00),
    (0.0,  0.35, 0.75),   # ya esta seco: bajar deprisa aqui es perder musculo
)
RITMO_VOLUMEN = (
    (20.0, 0.10, 0.25),   # con grasa de sobra, subir despacio
    (0.0,  0.20, 0.50),
)
RITMO_RECOMPOSICION = (-0.20, 0.20)   # mantenerse es el objetivo


def ritmo_objetivo(objetivo: Optional[str], porcentaje_graso: Optional[float]) -> Dict[str, Any]:
    """Cuanto deberia moverse el peso por semana, en % del peso corporal."""
    obj = (objetivo or "").lower().strip()
    bf = float(porcentaje_graso) if porcentaje_graso is not None else 25.0

    if obj in ("volumen", "ganar_musculo", "ganar musculo"):
        for desde, minimo, maximo in RITMO_VOLUMEN:
            if bf >= desde:
                return {"min": minimo, "max": maximo, "sentido": "subir"}
    if obj in ("recomposicion", "recomposición"):
        return {"min": RITMO_RECOMPOSICION[0], "max": RITMO_RECOMPOSICION[1], "sentido": "mantener"}

    for desde, minimo, maximo in RITMO_DEFINICION:
        if bf >= desde:
            return {"min": -maximo, "max": -minimo, "sentido": "bajar"}
    return {"min": -0.75, "max": -0.35, "sentido": "bajar"}


def _semanas_entre(desde: str, hasta: str) -> float:
    """Semanas entre dos fechas ISO. Minimo 1, para no dividir por cero ni inflar el ritmo."""
    try:
        a = datetime.fromisoformat(str(desde).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(hasta).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return 4.0
    dias = abs((b - a).days)
    return max(1.0, dias / 7.0)


def evaluar_peso(peso_ahora: Optional[float], peso_antes: Optional[float],
                 desde: Optional[str], hasta: Optional[str],
                 objetivo: Optional[str], porcentaje_graso: Optional[float]) -> Dict[str, Any]:
    """El peso en porcentaje, comparado con el ritmo que le toca a EL.

    Devuelve el cambio total y el semanal (los dos en %), su franja objetivo y un
    veredicto: en_rango | lento | rapido | sin_referencia.
    """
    objetivo_ritmo = ritmo_objetivo(objetivo, porcentaje_graso)
    if not peso_ahora or not peso_antes or peso_antes <= 0:
        return {"disponible": False, "objetivo": objetivo_ritmo,
                "motivo": "Hace falta el peso de este mes y el del anterior"}

    semanas = _semanas_entre(desde, hasta) if (desde and hasta) else 4.0
    cambio_pct = (peso_ahora - peso_antes) / peso_antes * 100.0
    semanal_pct = cambio_pct / semanas

    if objetivo_ritmo["sentido"] == "mantener":
        veredicto = "en_rango" if objetivo_ritmo["min"] <= semanal_pct <= objetivo_ritmo["max"] else (
            "rapido" if abs(semanal_pct) > abs(objetivo_ritmo["max"]) else "en_rango")
    elif objetivo_ritmo["sentido"] == "bajar":
        # min y max son negativos: min es el limite rapido, max el lento.
        if semanal_pct > objetivo_ritmo["max"]:
            veredicto = "lento"
        elif semanal_pct < objetivo_ritmo["min"]:
            veredicto = "rapido"
        else:
            veredicto = "en_rango"
    else:
        if semanal_pct < objetivo_ritmo["min"]:
            veredicto = "lento"
        elif semanal_pct > objetivo_ritmo["max"]:
            veredicto = "rapido"
        else:
            veredicto = "en_rango"

    return {
        "disponible": True,
        "peso_ahora": round(float(peso_ahora), 1),
        "peso_antes": round(float(peso_antes), 1),
        "cambio_kg": round(peso_ahora - peso_antes, 1),
        "cambio_pct": round(cambio_pct, 2),
        "semanal_pct": round(semanal_pct, 2),
        "semanas": round(semanas, 1),
        "objetivo": objetivo_ritmo,
        "veredicto": veredicto,
    }


# Lo que contesta en el reporte -> porcentaje para la barra de entrenos (punto 57 del doc
# del 07-08). La app NO registra las sesiones hechas: guarda el plan de rutina, no lo que
# entreno de verdad, y el check-in diario dejo de preguntarlo en julio. Desde entonces la
# barra de entrenos del informe estaba sin fuente.
#
# "O se quita la barra, o se pregunta. Jesus prefiere preguntarla, que ya la tiene escrita
# en su formulario." Asi que la barra sale de lo que el dice, y se marca como tal: es un
# dato AUTODECLARADO y no una cuenta, y mezclarlo con lo registrado sin decirlo seria dar
# por medido algo que no lo esta.
CUMPLIMIENTO_ENTRENO_PCT = {
    "todos": 100,
    "casi_todos": 80,
    "la_mitad": 50,
    "pocos": 25,
    "ninguno": 0,
}


def evaluar_cumplimiento(dias_periodo: int, dias_dieta: int, dias_entreno: int,
                         entrenos_previstos: Optional[int] = None,
                         cumplimiento_entreno: Optional[str] = None) -> Dict[str, Any]:
    """Cumplimiento en verde y rojo, sacado de lo REGISTRADO.

    El documento saca el cumplimiento de los datos, no de preguntarle que se puntue:
    "el cumplimiento se obtiene asi, no preguntandole que se puntue".

    La EXCEPCION es el entrenamiento, porque no hay registro que valga: la app guarda el
    plan de rutina, no las sesiones hechas. Ahi manda lo que contesto en el reporte
    (`cumplimiento_entreno`), y la barra dice de donde sale.
    """
    dias_periodo = max(1, int(dias_periodo or 0))
    pct_dieta = min(100, round(dias_dieta / dias_periodo * 100))

    # LOS PREVISTOS NO SALEN (punto 41 del doc del 19-08): «quita ese dato del reporte,
    # decirle a alguien que no ha entrenado cuando si ha entrenado es peor que no decirle
    # nada». Son una multiplicacion -- dias de entreno por semana x semanas -- contra unos
    # "hechos" que solo existen si el cliente cierra el dia, asi que el porcentaje calculado
    # no mide entrenamientos: mide cierres de dia. Se apagan con el mismo interruptor que el
    # hueco del reporte, para que los dos se enciendan a la vez el dia que haya donde
    # marcar una sesion.
    previstos = entrenos_previstos if (entrenos_previstos and SE_REGISTRAN_LOS_ENTRENOS) else None
    pct_entreno = min(100, round(dias_entreno / previstos * 100)) if previstos else None
    # Lo unico que queda del entrenamiento es lo que EL dice en el reporte. Eso no es un
    # numero inventado: es su respuesta, y la barra dice que sale de ahi.
    declarado = CUMPLIMIENTO_ENTRENO_PCT.get(cumplimiento_entreno)
    if declarado is not None:
        pct_entreno = declarado

    def color(pct: Optional[int]) -> str:
        if pct is None:
            return "sin_dato"
        return "verde" if pct >= 80 else ("ambar" if pct >= 50 else "rojo")

    return {
        "dias_periodo": dias_periodo,
        "dieta": {"dias": dias_dieta, "pct": pct_dieta, "color": color(pct_dieta)},
        "entreno": {"dias": dias_entreno, "previstos": previstos,
                    "pct": pct_entreno, "color": color(pct_entreno),
                    # De donde sale el numero, para que la barra lo pueda decir: "lo dices
                    # tu" no es lo mismo que "esta contado", y darlo por medido cuando no
                    # lo esta es de las cosas que hacen que un informe deje de creerse.
                    "declarado": declarado is not None,
                    "respuesta": cumplimiento_entreno},
        # Lo que hay que preguntarle antes de rellenar: los dias sin registrar no son
        # necesariamente dias incumplidos (parte 6, "la confirmacion de huecos").
        "huecos_dieta": max(0, dias_periodo - dias_dieta),
    }


def comparar_macros(objetivo: Dict[str, Any], comido: Dict[str, Any]) -> Dict[str, Any]:
    """Los macros que le tocaban al lado de los que comio (medias del periodo)."""
    filas = []
    for clave, etiqueta in (("protein", "Proteína"), ("carbs", "Hidratos"), ("fat", "Grasa")):
        obj = float((objetivo or {}).get(clave) or 0)
        real = float((comido or {}).get(clave) or 0)
        desvio = (real - obj) / obj * 100 if obj > 0 else None
        filas.append({
            "macro": etiqueta,
            "objetivo": round(obj, 1),
            "comido": round(real, 1),
            "desvio_pct": round(desvio, 1) if desvio is not None else None,
            "color": "sin_dato" if desvio is None else (
                "verde" if abs(desvio) <= 10 else ("ambar" if abs(desvio) <= 20 else "rojo")),
        })
    return {"filas": filas}


def explicacion_del_sistema(peso: Dict[str, Any], cumplimiento: Dict[str, Any],
                            hubo_cambio_macros: bool) -> str:
    """La explicacion de los macros nuevos cuando no la escribe una persona (Nivel 1).

    Tono del documento: "todas escritas desde el alivio, no desde la exigencia". Y la
    decision ya tomada sobre el que va mal: no se le señala el incumplimiento ni se le
    ignora; se le dice que este mes no se tocan los macros y por que.
    """
    dieta_floja = cumplimiento.get("dieta", {}).get("color") == "rojo"

    if dieta_floja:
        return ("Este mes no te tocamos los macros. La dieta se ha registrado pocos días y, "
                "sin saber qué has comido de verdad, cambiar los números no arregla nada: "
                "solo tapa el problema. Empieza por registrar y el mes que viene ajustamos "
                "con datos.")

    if not peso.get("disponible"):
        return ("Nos falta tu peso para comparar. En cuanto lo tengamos, ajustamos.")

    veredicto = peso.get("veredicto")
    if veredicto == "en_rango":
        return ("Vas al ritmo que te toca, así que no hay motivo para tocar nada. "
                "Seguimos igual." if not hubo_cambio_macros else
                "Vas al ritmo que te toca. El ajuste de este mes es fino, para sostenerlo.")
    if veredicto == "lento":
        return ("Vas más lento de lo que te tocaría. Hemos ajustado los macros para "
                "desatascarlo; no hace falta que aprietes por tu cuenta.")
    if veredicto == "rapido":
        return ("Vas más rápido de lo que conviene. Bajar así se lleva por delante músculo, "
                "que es justo lo que no queremos: hemos subido para frenarlo un poco.")
    return "Seguimos con los mismos macros este mes."


# ---------------------------------------------------------------------------
# La evolucion de referencia (octavo apartado): "como va respecto a gente de su perfil".
# ---------------------------------------------------------------------------

# Por debajo de esto no se enseña nada. Con tres o cuatro personas detras, decirle a
# alguien que va "mejor que la media" es ruido disfrazado de dato, y encima permitiria
# deducir el progreso de un cliente concreto.
COHORTE_MINIMA = 8


def evolucion_de_referencia(ritmo_semanal_pct: Optional[float],
                            ritmos_cohorte: Optional[List[float]],
                            sentido: str = "bajar") -> Dict[str, Any]:
    """Donde queda su ritmo entre el de la gente con su mismo perfil.

    `ritmos_cohorte` son los cambios semanales de peso en % de OTROS clientes del mismo
    sexo, objetivo y tramo de grasa. Se devuelve un percentil y una frase, nunca datos de
    nadie: la comparacion sirve para situarse, no para cotillear.

    Con `sentido` "bajar", perder mas es ir mejor; con "subir", al reves. En mantenimiento
    no se compara: ahi "mejor" no significa nada.
    """
    if sentido == "mantener":
        return {"disponible": False,
                "motivo": "En mantenimiento no tiene sentido comparar el ritmo con nadie"}
    if ritmo_semanal_pct is None:
        return {"disponible": False, "motivo": "Hace falta el peso de este mes y el del anterior"}

    otros = [r for r in (ritmos_cohorte or []) if isinstance(r, (int, float))]
    if len(otros) < COHORTE_MINIMA:
        return {"disponible": False, "cohorte": len(otros),
                "motivo": ("Todavía no hay suficientes personas con tu perfil para comparar. "
                           "Aparecerá cuando las haya")}

    # Mejor = mas negativo al bajar, mas positivo al subir.
    if sentido == "bajar":
        peores = sum(1 for r in otros if r > ritmo_semanal_pct)
    else:
        peores = sum(1 for r in otros if r < ritmo_semanal_pct)
    percentil = int(round(100 * peores / len(otros)))

    media = sum(otros) / len(otros)
    if percentil >= 75:
        frase = "Vas por delante de la mayoría de la gente con tu perfil."
    elif percentil >= 40:
        frase = "Vas en la media de la gente con tu perfil."
    else:
        frase = ("Vas por detrás de la media de tu perfil. No es un suspenso: "
                 "el ritmo que te toca a ti es el de arriba, no el de los demás.")

    return {
        "disponible": True,
        "percentil": percentil,
        "cohorte": len(otros),
        "tu_ritmo_semanal_pct": round(ritmo_semanal_pct, 2),
        "media_cohorte_pct": round(media, 2),
        "texto": frase,
        # El aviso importa: el objetivo de cada uno sale de SU perfil (parte 6 del
        # documento). Esto es contexto, no la vara de medir.
        "nota": "Tu objetivo sigue siendo el tuyo; esto es solo para situarte.",
    }


def comparativa_de_fotos(*, reporte: Dict[str, Any],
                         reporte_anterior: Optional[Dict[str, Any]],
                         reporte_inicial: Optional[Dict[str, Any]],
                         reporte_inicio_fase: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Las CUATRO fotos del informe, cada una respondiendo a algo (documento 05-08, 3.2):

        de donde vengo · donde empezo esta fase · que he hecho este mes · como estoy hoy

    Reglas suyas:
      - La inicial no se mueve nunca de la izquierda; lo que rota es la del medio.
      - Si dos etiquetas apuntan a la MISMA foto, se ensena una sola vez con las dos
        etiquetas. Pasa el primer mes de una fase nueva, cuando nunca ha cambiado de
        fase, y en el mes 2.
      - Nunca mas de cuatro, nunca la misma dos veces.

    Con eso, el numero de fotos sale solo: mes 1 -> 1, mes 2 -> 2, mes 3 en adelante
    -> 3, y 4 solo cuando ha habido un cambio de fase que no cae en otra etiqueta.
    """
    candidatos = [
        ("inicial", "De dónde vengo", reporte_inicial),
        ("inicio_fase", "Dónde empezó esta fase", reporte_inicio_fase),
        ("mes_anterior", "Qué he hecho este mes", reporte_anterior),
        ("actual", "Cómo estoy hoy", reporte),
    ]
    salida: List[Dict[str, Any]] = []
    por_reporte: Dict[str, Dict[str, Any]] = {}
    for etiqueta, titulo, rep in candidatos:
        if not rep or not [f for f in (rep.get("photos") or []) if f]:
            continue
        clave = rep.get("id") or str(rep.get("created_at"))
        ya = por_reporte.get(clave)
        if ya:                      # misma foto que una etiqueta anterior: no se repite
            ya["etiquetas"].append(etiqueta)
            ya["titulos"].append(titulo)
            continue
        item = {
            "etiquetas": [etiqueta],
            "titulos": [titulo],
            "fecha": str(rep.get("created_at") or "")[:10],
            "peso": rep.get("weight"),
            "medidas": rep.get("measurements") or None,
            "fotos": [f for f in (rep.get("photos") or []) if f],
        }
        por_reporte[clave] = item
        salida.append(item)
    # De izquierda a derecha, en orden de tiempo: asi la inicial (la mas antigua) nunca se
    # mueve de la izquierda y la actual queda a la derecha, aunque una etiqueta del medio
    # caiga sobre una foto que ya estaba (por ejemplo el inicio de fase siendo la de hoy).
    salida.sort(key=lambda x: x["fecha"])
    return salida[:4]


def montar_informe(*, perfil: Dict[str, Any], reporte: Dict[str, Any],
                   reporte_anterior: Optional[Dict[str, Any]],
                   fotos_dia_cero: Optional[List[str]],
                   reporte_inicial: Optional[Dict[str, Any]] = None,
                   reporte_inicio_fase: Optional[Dict[str, Any]] = None,
                   ritmos_cohorte: Optional[List[float]] = None,
                   semanas_ciclo: Optional[int],
                   dias_dieta: int, dias_entreno: int, dias_periodo: int,
                   macros_comidos: Dict[str, Any],
                   macros_nuevos: Optional[Dict[str, Any]],
                   explicacion_equipo: Optional[str],
                   la_escribe_el_equipo: bool) -> Dict[str, Any]:
    """Arma los ocho apartados, CON LO QUE HAYA (punto 41 del doc del 23-08).

    Hasta ese doc «sin fotos no hay informe»: las 17 entradas del cliente se quedaban en
    «Tu informe está a una foto». La regla nueva es la contraria: el informe sale
    siempre -- peso, ciclo, cumplimiento, macros comidos, lo que se le dijo -- y la
    foto lo COMPLETA. Sin fotos, el apartado de fotos lo dice y ya está.
    """
    fotos_ahora = [f for f in (reporte.get("photos") or []) if f]

    peso = evaluar_peso(
        peso_ahora=reporte.get("weight"),
        peso_antes=(reporte_anterior or {}).get("weight"),
        desde=(reporte_anterior or {}).get("created_at"),
        hasta=reporte.get("created_at"),
        objetivo=perfil.get("goal"),
        porcentaje_graso=perfil.get("body_fat"),
    )
    cumplimiento = evaluar_cumplimiento(
        dias_periodo=dias_periodo, dias_dieta=dias_dieta, dias_entreno=dias_entreno,
        entrenos_previstos=(perfil.get("training_days") or 0) * max(1, round(dias_periodo / 7)),
        # Lo que contesto en ESTE reporte (punto 57): es la unica fuente que hay para el
        # entrenamiento, porque las sesiones hechas no se registran en ningun sitio.
        cumplimiento_entreno=reporte.get("cumplimiento_entreno"),
    )
    macros = comparar_macros(perfil.get("macros_training") or {}, macros_comidos or {})

    # Tres o cuatro fotos, no dos: las de hoy y las del dia cero, para que la comparacion
    # sea contra el punto de partida y no solo contra el mes pasado.
    fotos_antes = [f for f in (fotos_dia_cero or []) if f][:3]

    explicacion = (explicacion_equipo or "").strip() if la_escribe_el_equipo else ""
    if not explicacion and not la_escribe_el_equipo:
        explicacion = explicacion_del_sistema(peso, cumplimiento, bool(macros_nuevos))

    return {
        "generado": True,
        "ciclo": {
            "semana": perfil.get("week") or 1,
            "semanas_totales": semanas_ciclo,
            "plan": perfil.get("plan"),
        },
        "peso": peso,
        "grasa": {
            "actual": perfil.get("body_fat"),
            "anterior": (reporte_anterior or {}).get("body_fat"),
        },
        "fotos": {
            "ahora": fotos_ahora[:3], "dia_cero": fotos_antes,
            # Sin fotos el informe sale igual (P41): la pantalla lee esta marca para
            # decirlo y ofrecer subirlas, en vez de esconder el informe entero.
            "faltan": not fotos_ahora,
            # La comparativa con etiquetas (3.2). Se deja `ahora`/`dia_cero` al lado para
            # no romper lo que ya lee la pantalla vieja.
            "comparativa": comparativa_de_fotos(
                reporte=reporte, reporte_anterior=reporte_anterior,
                reporte_inicial=reporte_inicial, reporte_inicio_fase=reporte_inicio_fase),
        },
        "cumplimiento": cumplimiento,
        "macros": macros,
        "macros_nuevos": macros_nuevos,
        "explicacion": {
            "texto": explicacion,
            "la_escribe": "equipo" if la_escribe_el_equipo else "sistema",
            "pendiente": la_escribe_el_equipo and not explicacion,
        },
        # Octavo apartado: como va respecto a gente de su perfil (parte 8 del documento).
        "referencia": evolucion_de_referencia(
            peso.get("semanal_pct") if peso.get("disponible") else None,
            ritmos_cohorte,
            (peso.get("objetivo") or {}).get("sentido", "bajar"),
        ),
        "generado_at": datetime.now(timezone.utc).isoformat(),
    }
