"""
Los avisos que la app le manda al cliente por su cuenta (especificacion 31-07-2026, parte 9).

Hasta ahora solo se le avisaba cuando el coach hacia algo: rutina nueva, macros
cambiados, feedback. Nada salia de su calendario ni de sus datos. Aqui estan los dos
grupos que pide el documento:

  - las de CALENDARIO, que van siempre porque son parte del programa,
  - las CONDICIONADAS, que solo saltan cuando sus datos lo justifican.

Tres reglas que no son de estilo:

  1. "maximo una notificacion por semana que no sea de calendario". Si en la misma
     semana se cumplen tres condiciones, sale UNA: la mas util. Por eso van ordenadas
     por prioridad y no por cuando se detectan.

  2. "todas escritas desde el alivio, no desde la exigencia". Este cliente lleva años
     oyendo que no tiene fuerza de voluntad; si la app se une a ese coro, la desinstala.
     La UNICA que va directa es "llevas X semanas con los mismos macros", porque es
     factual, no es un reproche, y es la que de verdad mueve.

  3. Cada aviso trae una `clave` unica del evento. Un aviso no se repite mientras esa
     clave siga viva, asi que da igual cuantas veces se evalue: entrar diez veces en la
     app no genera diez avisos.

DESDE EL DOC DEL 16-08 (T10, "los 19 avisos") hay ademas una cuarta regla y dos funciones
nuevas:

  4. El texto ROTA: cada aviso trae dos o tres redacciones y nunca sale la misma dos
     veces seguidas. Por eso las nuevas no traen `titulo`/`cuerpo` sino `variantes` y una
     `familia`: quien las manda (`sincronizar_avisos`) elige cual toca con
     `variante_para()`, que mira lo ultimo que se le mando de esa familia.

  - `avisos_de_calendario_doc()`: los OCHO del doc, con las horas de España.
  - `avisos_condicionados()`: las CUATRO del doc, y solo esas.

Y `avisos_de_calendario()` se queda con lo que ya habia y el doc no reescribe (macros
provisionales, el ajuste y la rutina que caduca). Todo lo nuevo va detras del interruptor
`t10_avisos_nuevos`: apagado, la app manda exactamente lo de antes.
"""
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

# El tope de las condicionadas. Las de calendario no cuentan para esto.
DIAS_ENTRE_CONDICIONADAS = 7


def rotar_variante(variantes: List[Dict[str, Any]], ultima: Optional[int]) -> Dict[str, Any]:
    """Regla 6 del doc 16-08: "cada aviso con 2 o 3 textos que rotan, y nunca el mismo
    dos veces seguidas. El mismo mensaje repetido doce semanas deja de leerse."

    `variantes` son los textos de UN aviso ({titulo, cuerpo, ...}); `ultima` es el
    índice de la variante que se le mandó la vez anterior (va guardado en la propia
    notificación, campo `variante`). Devuelve la variante que toca con su índice
    dentro, para que quien la inserte lo deje guardado y la rueda siga girando.
    """
    if not variantes:
        raise ValueError("un aviso sin textos no es un aviso")
    idx = 0 if ultima is None else (int(ultima) + 1) % len(variantes)
    return {**variantes[idx], "variante": idx}


def _dias_desde(iso: Optional[str], ahora: datetime) -> Optional[int]:
    """Dias transcurridos desde una fecha ISO. None si no hay fecha o no se entiende."""
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return max(0, (ahora - d).days)


def _fecha_es(d: datetime) -> str:
    meses = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre")
    return f"{d.day} de {meses[d.month - 1]}"


# ── Las de calendario ─────────────────────────────────────────────────────────
# Van siempre: son el programa, no un recordatorio. No consumen el cupo semanal.

def avisos_de_calendario(*, perfil: Dict[str, Any], ahora: datetime,
                         arranque: Optional[datetime] = None,
                         proximo_ajuste: Optional[datetime] = None,
                         rutina_caduca: Optional[datetime] = None,
                         semanas_ciclo: Optional[int] = None,
                         macros_puestos_por_alguien: bool = False,
                         rutina_visible: bool = False,
                         nuevos: bool = False) -> List[Dict[str, Any]]:
    """Los avisos de calendario que ya existían antes del doc 16-08.

    `nuevos` es el interruptor `t10_avisos_nuevos`: cuando está encendido, los dos que el
    doc reescribe -- "Mañana empiezas" y el fin de ciclo -- salen de
    `avisos_de_calendario_doc` con sus textos y sus variantes, y aquí se callan para que
    el cliente no reciba el mismo aviso dos veces con dos redacciones distintas.
    """
    fuera: List[Dict[str, Any]] = []
    hoy = ahora.date()

    # "Tus macros son provisionales": a las 2 h de darse de alta, si aun no los ha ajustado.
    #
    # Y SOLO SI DE VERDAD LO SON. `ajuste_macros_completado` es False para todo el que no
    # paso por NUESTRO cuestionario de ajuste, y eso incluye a los 160 clientes que vinieron
    # de Calma y a todos aquellos a los que el coach les puso los macros a mano. Medido en
    # produccion el 09-08: el aviso le llegaba a los **174 clientes activos**, 171 de ellos
    # con macros escritos por una persona y 164 con tres semanas o mas en el programa.
    #
    # O sea que la app le decia a un cliente en la semana 6, con los macros que le puso Jesus
    # la semana pasada, que sus numeros son provisionales y que se los ajuste el mismo. Es
    # justo lo contrario de lo que vende el plan con entrenador.
    #
    # Provisional es el que acaba de entrar y no ha terminado. En cuanto alguien -- el coach,
    # el equipo, la migracion -- le ha puesto unos macros, ya no lo son.
    if not perfil.get("ajuste_macros_completado") and not macros_puestos_por_alguien:
        alta = perfil.get("created_at")
        try:
            d_alta = datetime.fromisoformat(str(alta).replace("Z", "+00:00")) if alta else None
        except (ValueError, TypeError):
            d_alta = None
        if d_alta:
            if d_alta.tzinfo is None:
                d_alta = d_alta.replace(tzinfo=timezone.utc)
            if ahora - d_alta >= timedelta(hours=2):
                fuera.append({
                    "clave": f"macros_provisionales:{d_alta.date()}",
                    "tipo": "macros",
                    "titulo": "Tus macros son provisionales",
                    "cuerpo": "Quince minutos y los tienes finos.",
                    # OJO: la pantalla se llama "Ajustar macros" pero su ruta es
                    # /dashboard/macro-calculator. Aqui ponia /dashboard/ajustar-macros, que
                    # no existe, y al no existir caia en el comodin del router y echaba al
                    # cliente al login. Y este aviso lo recibe casi todo el mundo a las 2 h
                    # de darse de alta, asi que era la primera cosa que tocaban de la app.
                    "link": "/dashboard/macro-calculator",
                    "calendario": True,
                })

    # "Mañana empiezas": el domingo de antes de arrancar. Mientras la Rutina esté apagada
    # para el cliente (`rutina_visible`, que sale del interruptor t3_entreno y lo pasa
    # quien llama) no se le puede decir "tu rutina ya está cargada" ni mandarle a una
    # pantalla que no puede abrir: el aviso se queda, pero apuntando a su panel y sin
    # prometerle lo que no va a ver.
    if arranque and not nuevos:
        dias_para_arrancar = (arranque.date() - hoy).days
        if dias_para_arrancar == 1:
            fuera.append({
                "clave": f"arranque:{arranque.date()}",
                "tipo": "programa",
                "titulo": "Mañana empiezas",
                "cuerpo": "Tu rutina ya está cargada." if rutina_visible else None,
                "link": "/dashboard/routine" if rutina_visible else "/dashboard",
                "calendario": True,
            })

    # El ajuste: aviso 6 dias antes y el dia que toca.
    if proximo_ajuste:
        faltan = (proximo_ajuste.date() - hoy).days
        if faltan == 6:
            fuera.append({
                "clave": f"ajuste_pronto:{proximo_ajuste.date()}",
                "tipo": "reporte",
                "titulo": "Tu próximo ajuste: en 6 días",
                "cuerpo": None,
                "link": "/dashboard/reports",
                "calendario": True,
            })
        elif faltan == 0:
            fuera.append({
                "clave": f"ajuste_hoy:{proximo_ajuste.date()}",
                "tipo": "reporte",
                "titulo": "Te tenemos los macros listos, solo faltan tus datos",
                "cuerpo": None,
                "link": "/dashboard/reports",
                "calendario": True,
            })

    # "Tu rutina acaba el X": tres dias antes, no el dia que caduca. Con la Rutina apagada
    # este aviso no se manda: entero va de algo que el cliente no puede ver, y decirle
    # "renuevala" cuando no tiene donde es peor que no decirle nada.
    if rutina_caduca and rutina_visible:
        faltan = (rutina_caduca.date() - hoy).days
        if faltan == 3:
            fuera.append({
                "clave": f"rutina_caduca:{rutina_caduca.date()}",
                "tipo": "rutina",
                "titulo": f"Tu rutina acaba el {_fecha_es(rutina_caduca)}",
                "cuerpo": "Renuévala y sigue sin parar.",
                "link": "/dashboard/routine",
                "calendario": True,
            })

    # Semana 11: el ciclo se acaba, y es cuando toca mirar atras.
    semana = perfil.get("week")
    if not nuevos and semanas_ciclo and semana and int(semana) == max(1, int(semanas_ciclo) - 1):
        fuera.append({
            "clave": f"fin_ciclo:{perfil.get('id')}:{semana}",
            "tipo": "programa",
            "titulo": "Tu ciclo acaba en una semana",
            "cuerpo": "Mira lo que has cambiado.",
            "link": "/renovacion",
            "calendario": True,
        })

    return fuera


# ── Las condicionadas ─────────────────────────────────────────────────────────
# Solo cuando sus datos lo justifican, y como mucho UNA por semana. El orden de esta
# lista ES la prioridad: si se cumplen varias, sale la primera.

def avisos_condicionados(*, ahora: datetime,
                         semanas_sin_ajustar: Optional[int] = None,
                         reporte_sin_fotos: bool = False,
                         dias_sin_cerrar: Optional[int] = None,
                         dias_sin_entrar: Optional[int] = None) -> List[Dict[str, Any]]:
    """Las CUATRO del doc 16-08, en su orden de prioridad. Ni una mas.

    Se cayeron tres que existian antes y que el doc no recoge: "¿Quieres que revisemos tu
    caso?" (estancado), "¿Te pesamos esta semana?" (7 dias sin peso) y "¿Todo bien?" (5
    dias sin dieta). Las tres pedian por separado lo que ahora pide una sola: cerrar el
    dia. Con el tope de una condicionada por semana, tener seis candidatas solo significa
    que las de abajo no salian nunca.

    Y la tercera cambia de criterio: ya no se mira la DIETA sino el CIERRE DEL DIA
    (`checkins`). Un cliente puede llevar la dieta cuadrada en Nutricion y no haber
    cerrado un solo dia, que es lo que a Jesus le deja sin ver nada.
    """
    fuera: List[Dict[str, Any]] = []
    semana_iso = f"{ahora.isocalendar()[0]}-W{ahora.isocalendar()[1]:02d}"

    # 1) Sin fotos no hay comparacion: es lo que mas le cuesta al cliente y lo que mas
    #    bloquea, asi que va primero.
    if reporte_sin_fotos:
        fuera.append({
            "clave": f"sin_fotos:{semana_iso}",
            "familia": "sin_fotos",
            "tipo": "reporte",
            "variantes": [
                {"titulo": "Sin fotos no puedo comparar",
                 "cuerpo": "Te lleva un minuto y es lo que de verdad enseña lo que ha cambiado."},
                {"titulo": "Te faltan las fotos del reporte",
                 "cuerpo": "La báscula no lo cuenta todo."},
            ],
            "link": "/dashboard/reports",
            "calendario": False,
        })

    # 2) La unica directa del documento. Factual, sin reproche, y el momento natural
    #    para ofrecerle que alguien le mire el caso. El numero de semanas va dentro del
    #    titulo, asi que las variantes se montan con el dato ya puesto.
    if semanas_sin_ajustar and semanas_sin_ajustar >= 2:
        fuera.append({
            "clave": f"sin_ajustar:{semana_iso}",
            "familia": "sin_ajustar",
            "tipo": "macros",
            "variantes": [
                {"titulo": f"Llevas {semanas_sin_ajustar} semanas con los mismos macros",
                 "cuerpo": "Con tus datos de estas semanas puedo mirarlo."},
                {"titulo": "Hace tiempo que no te ajusto",
                 "cuerpo": "Cierra unos días seguidos y le echo un ojo."},
            ],
            "link": "/dashboard/reports",
            "calendario": False,
        })

    # 3) Cinco dias sin cerrar el dia. El titulo dice "5 dias" y se queda en cinco aunque
    #    lleve doce: es el umbral del doc, no un contador. Un numero que crece cada dia
    #    solo sirve para que el aviso pese mas cuanto peor va la cosa.
    if dias_sin_cerrar is not None and dias_sin_cerrar >= 5:
        fuera.append({
            "clave": f"sin_cerrar:{semana_iso}",
            "familia": "sin_cerrar",
            "tipo": "checkin",
            "variantes": [
                {"titulo": "Llevas 5 días sin apuntar nada",
                 "cuerpo": "Con dos toques al día me vale."},
                {"titulo": "Te he perdido la pista",
                 "cuerpo": "Cinco días sin cerrar. ¿Todo bien?"},
            ],
            "link": "/dashboard/checkins",
            "calendario": False,
        })

    # 4) La mas suave de todas, y la ultima: el que lleva dos semanas sin aparecer no
    #    necesita que le recuerden lo que no ha hecho.
    if dias_sin_entrar is not None and dias_sin_entrar >= 14:
        fuera.append({
            "clave": f"sin_entrar:{semana_iso}",
            "familia": "sin_entrar",
            "tipo": "programa",
            "variantes": [
                {"titulo": "Tu plan sigue aquí", "cuerpo": "Retomamos cuando quieras."},
                {"titulo": "Cuando quieras volver, aquí está", "cuerpo": "Sin prisa."},
            ],
            "link": "/dashboard",
            "calendario": False,
        })

    return fuera


# ── Los ocho de calendario del doc 16-08 ──────────────────────────────────────
#
# Los textos son LITERALES del documento, con sus dos o tres variantes. No se retocan:
# son la voz de Jesus, y media redaccion de estas es lo unico que separa un aviso que se
# lee de un correo que no abre nadie.
#
# No hay cron ni push (decision 2 del plan): la hora fija solo decide DESDE CUANDO se
# puede ver el aviso. Por eso todas las condiciones son ">= la hora", no "a la hora": el
# cliente que entra a las 22:10 tiene que encontrarse el de las 20:00.
#
# `ahora_es` viene YA en hora de España (`ahora_madrid()`), porque todas las horas del
# doc lo son. Mongo guarda UTC y la conversion se hace en el borde, en `sincronizar_avisos`.

def avisos_de_calendario_doc(*, ahora_es: datetime,
                             cliente_id: Optional[str] = None,
                             arranque: Optional[date] = None,
                             cerro_hoy: bool = True,
                             quiere_cierre_dia: bool = True,
                             ventanas: Optional[List[Dict[str, Any]]] = None,
                             semana: Optional[int] = None,
                             semanas_ciclo: Optional[int] = None,
                             rutina_visible: bool = False) -> List[Dict[str, Any]]:
    """Los ocho del calendario. Siempre salen: no gastan el cupo de las condicionadas.

    `ventanas` son las ventanas de reporte que le tocan (la de esta semana de ciclo y la
    de la anterior, que es la que sostiene el aviso del martes), cada una con
    `{tipo, semana, abre, cierra, mandado}` y las fechas ya en hora de España.
    """
    fuera: List[Dict[str, Any]] = []
    hoy = ahora_es.date()
    ventanas = ventanas or []

    # 1 · "Mañana empiezas". El domingo de antes de arrancar, a las 19:00, y una sola vez.
    #
    # El enlace se queda en el panel mientras la Rutina esté apagada (interruptor
    # `t3_entreno`): el texto le promete que su rutina ya está cargada, pero mandarle a
    # una pantalla que no puede abrir sería peor que no mandarle a ninguna.
    if arranque and (arranque - hoy).days == 1 and ahora_es.hour >= 19:
        fuera.append({
            "clave": f"arranque:{arranque}",
            "familia": "arranque",
            "tipo": "programa",
            "variantes": [
                {"titulo": "Mañana empiezas",
                 "cuerpo": "Tu rutina y tus macros ya están cargados."},
                {"titulo": "Mañana arrancamos",
                 "cuerpo": "Lo tienes todo dentro. Nos vemos en doce semanas."},
            ],
            "link": "/dashboard/routine" if rutina_visible else "/dashboard",
            "calendario": True,
        })

    # 2 · "Cierra tu día". Cada día a las 20:00 si no lo ha cerrado. Es el único que el
    # cliente puede apagar (`profile.avisos.cierre_dia`): es diario, y un aviso diario que
    # no se puede callar acaba con la campanita silenciada entera.
    if quiere_cierre_dia and not cerro_hoy and ahora_es.hour >= 20:
        fuera.append({
            "clave": f"cierra_dia:{hoy}",
            "familia": "cierra_dia",
            "tipo": "checkin",
            "variantes": [
                {"titulo": "Cierra tu día", "cuerpo": "Dos toques y listo."},
                {"titulo": "¿Cómo fuiste hoy?", "cuerpo": "Un minuto y lo tengo."},
                {"titulo": "Te falta cerrar el día", "cuerpo": "Lo que no apuntas, no lo veo."},
            ],
            "link": "/dashboard/checkins",
            "calendario": True,
        })

    for v in ventanas:
        tipo, abre, cierra = v.get("tipo"), v.get("abre"), v.get("cierra")
        if not tipo or not abre or not cierra:
            continue
        mandado = bool(v.get("mandado"))

        # 3 y 4 · El quincenal. Quién lo tiene no se pregunta por el nombre del plan: si
        # su calendario no trae quincenal, aquí no llega ninguna ventana de ese tipo.
        if tipo == "quincenal":
            if hoy == abre.date() and ahora_es >= abre:
                fuera.append({
                    "clave": f"quincenal_abierto:{abre.date()}",
                    "familia": "quincenal_abierto",
                    "tipo": "reporte",
                    "variantes": [
                        {"titulo": "Tu reporte quincenal está abierto",
                         "cuerpo": "Unas breves preguntas para ajustar tus macros si hace falta. Hasta mañana a las 20:00."},
                        {"titulo": "Toca quincenal",
                         "cuerpo": "Cuatro preguntas. Tienes hasta mañana a las 20:00."},
                        {"titulo": "Cuéntame estas dos semanas",
                         "cuerpo": "Es rápido, y con eso decido si te toco algo."},
                    ],
                    "link": "/dashboard/reports",
                    "calendario": True,
                })
            if not mandado and hoy == abre.date() + timedelta(days=1) and ahora_es.hour >= 9:
                fuera.append({
                    "clave": f"quincenal_ultimo:{abre.date()}",
                    "familia": "quincenal_ultimo",
                    "tipo": "reporte",
                    "variantes": [
                        {"titulo": "Último día para tu quincenal",
                         "cuerpo": "Se cierra hoy a las 20:00."},
                        {"titulo": "Hoy cierra tu quincenal",
                         "cuerpo": "A las 20:00. Sin él no sé cómo has ido estas dos semanas."},
                    ],
                    "link": "/dashboard/reports",
                    "calendario": True,
                })

        if tipo == "mensual":
            # 5 · El viernes que abre. Sin hora: el doc no le pone ninguna y el mensual
            # lleva fotos y medidas, o sea que cuanto antes lo vea, mejor.
            if hoy == abre.date():
                fuera.append({
                    "clave": f"mensual_abierto:{abre.date()}",
                    "familia": "mensual_abierto",
                    "tipo": "reporte",
                    "variantes": [
                        {"titulo": "Tu reporte mensual está abierto",
                         "cuerpo": "Tus fotos, tus medidas y unas preguntas. Hasta el lunes a las 18:00."},
                        {"titulo": "Toca reporte mensual",
                         "cuerpo": "Este es el importante. Tienes hasta el lunes a las 18:00."},
                        {"titulo": "Es el momento de las fotos",
                         "cuerpo": "Tu reporte mensual está abierto hasta el lunes a las 18:00."},
                    ],
                    "link": "/dashboard/reports",
                    "calendario": True,
                })
            # 6 · El domingo a las 10:00, si sigue sin mandarlo.
            if not mandado and hoy == abre.date() + timedelta(days=2) and ahora_es.hour >= 10:
                fuera.append({
                    "clave": f"mensual_ultimo:{abre.date()}",
                    "familia": "mensual_ultimo",
                    "tipo": "reporte",
                    "variantes": [
                        {"titulo": "Último día para tu reporte mensual",
                         "cuerpo": "Se cierra mañana a las 18:00 y sin él no puedo ajustarte."},
                        {"titulo": "Mañana cierra tu mensual",
                         "cuerpo": "A las 18:00. Es el que marca lo que viene después."},
                    ],
                    "link": "/dashboard/reports",
                    "calendario": True,
                })
            # 7 · El martes de después, si se le pasó. Va solo con el MENSUAL: es el que
            # cierra el lunes a las 18:00, así que el martes es el día siguiente, y es el
            # correo que sustituye ("Reporte Mensual · No Enviado", el más abierto de
            # todos con un 18,9 %). El quincenal cierra el jueves y para el martes ya ha
            # empezado otra semana de ciclo.
            if not mandado and ahora_es > cierra and hoy == cierra.date() + timedelta(days=1):
                fuera.append({
                    "clave": f"reporte_no_llego:{cierra.date()}",
                    "familia": "reporte_no_llego",
                    "tipo": "reporte",
                    "variantes": [
                        {"titulo": "No me llegó tu reporte",
                         "cuerpo": "Sin él no puedo ajustarte. Dime si lo mandas esta semana o te lo aplazo."},
                        {"titulo": "Se te pasó el reporte",
                         "cuerpo": "No pasa nada: dime si lo haces esta semana y te lo vuelvo a abrir."},
                    ],
                    "link": "/dashboard/reports",
                    "calendario": True,
                })

    # 8 · "Tu ciclo acaba en una semana", en la penúltima y CON EL MENSUAL: el doc lo pone
    # al lado del reporte, no suelto a mitad de semana. Si esa semana no llevara mensual
    # (ningún plan de hoy está así, pero el patrón se puede configurar) sale igual: el
    # cliente tiene que enterarse de que su ciclo se acaba.
    if semanas_ciclo and semana and int(semana) == max(1, int(semanas_ciclo) - 1):
        mensual = next((v for v in ventanas
                        if v.get("tipo") == "mensual" and v.get("semana") == semana), None)
        if not mensual or ahora_es >= mensual["abre"]:
            fuera.append({
                "clave": f"fin_ciclo:{cliente_id}:{semana}",
                "familia": "fin_ciclo",
                "tipo": "programa",
                "variantes": [
                    {"titulo": "Tu ciclo acaba en una semana",
                     "cuerpo": "Mira lo que has cambiado."},
                    {"titulo": "Queda una semana",
                     "cuerpo": "Entra en tu evolución y compara la primera foto con la de ahora."},
                ],
                # A su evolución, que es lo que los dos textos le piden mirar. La pantalla
                # de renovación llega sola cuando el ciclo se acaba de verdad.
                "link": "/dashboard/reports",
                "calendario": True,
            })

    return fuera


def textos_de(aviso: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Todos los textos posibles de un aviso, tenga variantes o uno solo.

    Lo usan las comprobaciones que miran el TONO y los enlaces: da igual cuál toque hoy,
    ninguna de las tres variantes puede sonar a reproche."""
    if aviso.get("variantes"):
        return list(aviso["variantes"])
    return [{"titulo": aviso.get("titulo"), "cuerpo": aviso.get("cuerpo")}]


def elegir_avisos(calendario: List[Dict[str, Any]], condicionados: List[Dict[str, Any]],
                  claves_ya_enviadas: set, ultima_condicionada: Optional[str],
                  ahora: datetime) -> List[Dict[str, Any]]:
    """Lo que de verdad se manda: todas las de calendario y como mucho UNA condicionada.

    `claves_ya_enviadas` evita repetir un aviso que ya salio. `ultima_condicionada` es
    la fecha ISO de la ultima condicionada que se le mando, para respetar el tope.
    """
    salida = [a for a in calendario if a["clave"] not in claves_ya_enviadas]

    dias = _dias_desde(ultima_condicionada, ahora)
    if dias is not None and dias < DIAS_ENTRE_CONDICIONADAS:
        return salida   # esta semana ya tuvo la suya

    for aviso in condicionados:
        if aviso["clave"] not in claves_ya_enviadas:
            salida.append(aviso)
            break   # una y no mas

    return salida
