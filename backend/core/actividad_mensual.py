"""
EL PASO 1 DEL MENSUAL: lo que ha hecho, cómo se ha sentido y lo que le falta.

Del documento «El reporte mensual» (1-09-2026). El paso 1 se llama «Actualizar tus datos
y confirmar que están bien», y su subtítulo dice de dónde sale todo:

    «Sale de tus check-in. Si algo no cuadra o te falta, lo arreglas al final.»

O sea: aquí no se le pregunta nada. Se le enseña lo que ya está guardado, y lo único que
contesta son los huecos: los días de los que la app no tiene ni un sí ni un no.

Tres bloques, y este módulo redacta los tres:

    LO QUE HAS HECHO EN LOS ÚLTIMOS 28 DÍAS
    Dietas guardadas 22 de 28 · Días que comiste de más 6 · Entrenos 13 de 16
    Cardio 7 de 12 · Movimiento 16 igual · 5 más · 7 menos · Suplementación 21 de 28

    Y CÓMO TE HAS SENTIDO
    Descanso 2,9 · Energía 3,1 · Hambre / ansiedad 3,6

    Te dejaste 3 entrenos sin registrar.   [No entrené] [Sí entrené, pero no lo marqué]
    Y 4 días de dieta.                     [No la cumplí] [Sí, pero no la guardé]

REGLA QUE MANDA SOBRE TODAS: lo que no se sabe no se cuenta. Es la misma de
`core/datos_reporte.py`, y aquí importa el doble porque este bloque es una lista de
notas. Una fila sin denominador de verdad -- cardio sin sesiones pautadas, entrenos sin
rutina cargada -- NO SALE. Inventar el denominador es escribirle un suspenso por algo que
nunca se le pidió, y eso ya pasó una vez con los entrenos (punto 41 del doc del 19-08).

Cálculo puro: no toca base de datos ni HTTP. Quien llama trae los cierres ya leídos.
"""
from typing import Any, Dict, List, Optional

# Las tres sensaciones del cierre del día, con el nombre que les pone el documento y el
# campo con el que se guardan. «Hambre / ansiedad» va con las barras porque así se lee en
# la maqueta y así se pregunta cada noche.
SENSACIONES = (
    ("descanso", "Descanso", "descanso"),
    ("energia", "Energía", "energy"),
    ("hambre", "Hambre / ansiedad", "hunger_anxiety"),
)

# Lo que puede contestar a un hueco. Son los mismos dos valores de
# `core/confirmacion_huecos.py`: lo que cambia entre los dos sitios es cómo se redacta la
# pregunta, no lo que significa la respuesta.
NO_LO_HICE = "no_lo_hice"
SI_PERO_NO_APUNTE = "si_pero_no_apunte"


def _numero(v: Any) -> str:
    """«2,9». Con coma, que es como se escriben los decimales aquí."""
    return f"{float(v):.1f}".replace(".", ",")


def _plural(n: int, singular: str, plural: str) -> str:
    return singular if n == 1 else plural


# ─────────────────────────────────────────────────────────────────────────────
# LO QUE HAS HECHO
# ─────────────────────────────────────────────────────────────────────────────

def titulo_de_actividad(dias: int, desde_el_principio: bool) -> str:
    """«LO QUE HAS HECHO EN LOS ÚLTIMOS 28 DÍAS» / «LO QUE HAS HECHO EN 120 DÍAS».

    Los dos rótulos son del documento y no son el mismo con un número cambiado: el del
    periodo corto dice «en los últimos», porque son los días que acaba de vivir; el del
    programa entero no, porque ahí «los últimos 120» sonaría a que hay unos anteriores.
    """
    if desde_el_principio:
        return f"LO QUE HAS HECHO EN {dias} DÍAS"
    return f"LO QUE HAS HECHO EN LOS ÚLTIMOS {dias} DÍAS"


def filas_de_actividad(dieta: Optional[Dict[str, Any]],
                       entreno: Optional[Dict[str, Any]],
                       cierres: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Las seis filas del bloque, en el orden del documento y sin las que no se sepan.

    `dieta` y `entreno` vienen de `core.datos_reporte`; `cierres` de `cierres_del_periodo`
    de este mismo módulo. Cualquiera de los tres puede faltar: entonces faltan sus filas y
    ya está, que es mejor que una fila con un guion.
    """
    dieta = dieta or {}
    entreno = entreno or {}
    cierres = cierres or {}
    filas: List[Dict[str, Any]] = []

    def pon(clave: str, etiqueta: str, valor: Optional[str]) -> None:
        if valor:
            filas.append({"clave": clave, "etiqueta": etiqueta, "valor": valor})

    # 1 · Las dietas guardadas. El denominador son los días del periodo, y ese siempre se
    #     sabe: un día sin dieta guardada es un día sin dieta guardada.
    dias = int(dieta.get("dias_periodo") or 0)
    if dias:
        pon("dietas", "Dietas guardadas", f"{int(dieta.get('dias_registrados') or 0)} de {dias}")

    # 2 · Los días que comió de más. Aquí NO hay denominador a propósito: es un recuento,
    #     no un cumplimiento, y ponerle «6 de 28» lo convertiría en una nota.
    extras = cierres.get("dias_comio_de_mas")
    if extras is not None:
        pon("extras", "Días que comiste de más", str(int(extras)))

    # 3 · Los entrenos. `previstos` es None cuando no tiene rutina cargada: sin días de
    #     entreno no hay «de los que tocaban», y la fila no sale.
    previstos = entreno.get("previstos")
    if previstos:
        pon("entrenos", "Entrenos", f"{int(entreno.get('hechos') or 0)} de {int(previstos)}")

    # 4 · El cardio. Las sesiones pautadas salen de su rutina (los días que la rutina marca
    #     cardio), que es lo único que hay: no existe un campo «sesiones por semana».
    cardio = entreno.get("cardio") or {}
    if cardio.get("previstas"):
        pon("cardio", "Cardio",
            f"{int(cardio.get('hechas') or 0)} de {int(cardio['previstas'])}")

    # 5 · El movimiento. Los tres recuentos juntos, y solo los que no son cero: «16 igual ·
    #     5 más» se lee, «16 igual · 5 más · 0 menos» es ruido.
    mov = cierres.get("movimiento") or {}
    trozos = [f"{mov[k]} {etiqueta}"
              for k, etiqueta in (("igual", "igual"), ("mas", "más"), ("menos", "menos"))
              if mov.get(k)]
    if trozos:
        pon("movimiento", "Movimiento", " · ".join(trozos))

    # 6 · La suplementación. Solo del que la tiene pautada: al que no lleva suplementos no
    #     se le enseña un «0 de 28» que no significa nada.
    sup = cierres.get("suplementacion") or {}
    if sup.get("de"):
        pon("suplementacion", "Suplementación", f"{int(sup.get('cumplidos') or 0)} de {int(sup['de'])}")

    return filas


def sensaciones_del_periodo(cierres: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """«Y CÓMO TE HAS SENTIDO»: descanso, energía y hambre, con su media y su línea.

    La media es la de los días que contestó, no la de los días del periodo: dos noches
    marcadas y veintiséis en blanco no son una media de todo el mes dividida entre 28.
    """
    sens = (cierres or {}).get("sensaciones") or {}
    salida: List[Dict[str, Any]] = []
    for clave, etiqueta, _campo in SENSACIONES:
        valores = sens.get(clave) or []
        if not valores:
            continue
        media = sum(valores) / len(valores)
        salida.append({
            "clave": clave,
            "etiqueta": etiqueta,
            "media": round(media, 1),
            "media_label": _numero(media),
            "dias": len(valores),
            # La línea de la maqueta: los valores en orden, tal cual. Quien la pinta decide
            # el color; aquí no se juzga si 2,9 de descanso es bueno o malo.
            "serie": valores,
        })
    return salida


def pie_de_las_sensaciones(desde_el_principio: bool, dias: int) -> str:
    """«Solo de estos 28 días. Lo de antes ya está cerrado.»

    Es del documento y explica una cosa concreta: las sensaciones NO se acumulan como el
    peso. Si mira el programa entero, la frase tiene que decir de qué está hablando.
    """
    if desde_el_principio:
        return f"La media de tus {dias} días. Lo de cada mes ya está cerrado."
    return f"Solo de estos {dias} días. Lo de antes ya está cerrado."


# ─────────────────────────────────────────────────────────────────────────────
# LOS HUECOS: lo único que se le pregunta en el paso 1
# ─────────────────────────────────────────────────────────────────────────────

def huecos_del_paso1(entrenos_sin_registrar: int,
                     dias_sin_dieta: int) -> List[Dict[str, Any]]:
    """Las dos tarjetas de huecos, con la frase ya escrita.

    Del documento:

        Te dejaste 3 entrenos sin registrar.  [No entrené] [Sí entrené, pero no lo marqué]
        Y 4 días de dieta.                    [No la cumplí] [Sí, pero no la guardé]

    LA SEGUNDA EMPIEZA POR «Y». Eso solo se sostiene si va detrás de la primera: cuando el
    único hueco es el de la dieta, la frase tiene que ser una frase entera. Es el mismo
    cuidado que ya se tuvo con «de los últimos 1» en `confirmacion_huecos`.

    Al que lo registró todo no se le enseña nada: devuelve la lista vacía y el paso 1 se
    acaba en el botón de confirmar.
    """
    entrenos = max(0, int(entrenos_sin_registrar or 0))
    dieta = max(0, int(dias_sin_dieta or 0))
    huecos: List[Dict[str, Any]] = []

    if entrenos:
        huecos.append({
            "tipo": "entreno",
            "dias": entrenos,
            "pregunta": (f"Te dejaste {entrenos} "
                         f"{_plural(entrenos, 'entreno', 'entrenos')} sin registrar."),
            "opciones": [
                {"value": NO_LO_HICE, "label": "No entrené"},
                {"value": SI_PERO_NO_APUNTE, "label": "Sí entrené, pero no lo marqué"},
            ],
        })

    if dieta:
        huecos.append({
            "tipo": "dieta",
            "dias": dieta,
            "pregunta": (f"Y {dieta} {_plural(dieta, 'día', 'días')} de dieta."
                         if entrenos else
                         f"Te dejaste {dieta} {_plural(dieta, 'día', 'días')} "
                         f"de dieta sin guardar."),
            "opciones": [
                {"value": NO_LO_HICE, "label": "No la cumplí"},
                {"value": SI_PERO_NO_APUNTE, "label": "Sí, pero no la guardé"},
            ],
        })

    return huecos


# ─────────────────────────────────────────────────────────────────────────────
# LOS CIERRES, CONTADOS
# ─────────────────────────────────────────────────────────────────────────────

def cierres_del_periodo(cierres: List[Dict[str, Any]],
                        dias_periodo: int,
                        tiene_suplementacion: bool) -> Dict[str, Any]:
    """Cuenta los cierres del día ya leídos: extras, movimiento, suplementos y sensaciones.

    `tiene_suplementacion` decide si la fila de suplementos existe siquiera. Es el plan
    quien lo dice, no el recuento: al que no lleva suplementos, cero días tomándolos no es
    un incumplimiento.

    EL DENOMINADOR DE LA SUPLEMENTACIÓN SON LOS DÍAS DEL PERIODO, no los días que contestó.
    El documento pone «21 de 28» con 28 días de mes, y esa es la lectura honrada: un día
    que no cerró es un día que no consta que la tomara.
    """
    cierres = cierres or []
    extras = 0
    movimiento = {"igual": 0, "mas": 0, "menos": 0}
    suplementos_si, suplementos_contestados = 0, 0
    sensaciones: Dict[str, List[float]] = {c: [] for c, _e, _campo in SENSACIONES}

    for c in cierres:
        if c.get("extras_respuesta") == "si":
            extras += 1
        mov = c.get("movimiento")
        if mov in movimiento:
            movimiento[mov] += 1
        respuesta = (c.get("suplementos") or {}).get("respuesta")
        if respuesta:
            suplementos_contestados += 1
            # «No todos» NO cuenta como tomada: la fila dice los días que siguió la pauta,
            # y medio protocolo no es la pauta. Si Jesús lo quiere al revés, es esta línea.
            if respuesta == "si":
                suplementos_si += 1
        for clave, _etiqueta, campo in SENSACIONES:
            v = c.get(campo)
            if isinstance(v, (int, float)):
                sensaciones[clave].append(float(v))

    # LA FILA DE SUPLEMENTOS SOLO SI HAY ALGO QUE CONTAR. Al que no contestó ni una noche
    # no se le escribe «0 de 28»: no es que no los tomara, es que no lo dijo, y esa fila se
    # lee como un cero pelado. Es la misma regla que deja fuera los entrenos sin rutina.
    return {
        "cierres": len(cierres),
        "dias_comio_de_mas": extras,
        "movimiento": movimiento,
        "suplementacion": ({"cumplidos": suplementos_si, "de": max(0, int(dias_periodo or 0))}
                           if tiene_suplementacion and suplementos_contestados else {}),
        "sensaciones": sensaciones,
    }


# ─────────────────────────────────────────────────────────────────────────────
# LA OTRA VERSION DEL PASO 1: LA DEL QUE NO TIENE CHECK-IN
# ─────────────────────────────────────────────────────────────────────────────
#
# «Todo lo validado antes del 1 de septiembre», «Las dos versiones del paso 1»:
#
#     «Cinco preguntas y pasas al paso 2.»
#     «No tengo todos los datos de tus check-in diarios, asi que te lo pregunto aqui.»
#     «Si perdio dias y ademas el recordatorio del dia siguiente: cinco estrellas y al
#      paso 2.»
#
# El paso 1 normal ENSEÑA lo que ya esta guardado y solo pregunta los huecos. Pero eso solo
# vale si hay algo guardado: al que apenas ha cerrado dias, ese paso le sale vacio -- filas
# sin denominador, sensaciones sin media -- y encima le pide que confirme una nada. A ese se
# le pregunta, que es lo que se hacia antes de que existieran los cierres.
#
# EL LISTON: MENOS DE LA MITAD DE LOS DIAS. No es un numero elegido para que salga bonito:
# la mitad es lo que separa «le faltan dias» (eso son los huecos, y se preguntan uno a uno)
# de «no tengo sus datos» (y entonces no hay nada que enseñar). Con menos de la mitad, las
# medias de las sensaciones tampoco describen la quincena.
def hay_datos_suficientes(cierres: int, dias_periodo: int) -> bool:
    """Si el paso 1 puede ENSEÑAR sus datos o tiene que PREGUNTARLOS."""
    dias = max(0, int(dias_periodo or 0))
    if not dias:
        return False
    return int(cierres or 0) * 2 >= dias


# Las cinco de la maqueta, en su orden y con sus palabras. Son las que el quincenal dejo de
# preguntar en el doc 16-08 («el resto ya lo ha marcado cada dia») MAS el descanso: aqui
# vuelven porque justamente no las ha marcado cada dia.
#
# Todas de 1 a 5 estrellas: «cinco estrellas y al paso 2». La suplementacion solo al que
# lleva suplementos en el plan, con el mismo criterio que la fila de la actividad.
PREGUNTAS_SIN_CHECKIN = (
    {"clave": "dieta_grado", "pregunta": "¿En qué grado has cumplido la dieta?"},
    {"clave": "entreno_grado", "pregunta": "¿Has entrenado todos los días que tocaba?"},
    {"clave": "cardio_grado", "pregunta": "¿Has cumplido con el cardio que tenías pautado?"},
    {"clave": "suplementacion_grado",
     "pregunta": "¿Has tomado la suplementación que te correspondía?",
     "solo_con": "suplementacion"},
    {"clave": "descanso_grado", "pregunta": "Descanso — ¿cómo fue?"},
)


def preguntas_sin_checkin(tiene_suplementacion: bool) -> List[Dict[str, Any]]:
    """Las preguntas del paso 1 cuando no hay cierres de los que sacar los datos."""
    return [{"clave": p["clave"], "pregunta": p["pregunta"]}
            for p in PREGUNTAS_SIN_CHECKIN
            if p.get("solo_con") != "suplementacion" or tiene_suplementacion]
