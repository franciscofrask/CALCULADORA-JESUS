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


def _dia_es(d: datetime) -> str:
    """«miércoles 26». El formato que pide la última regla del doc del 19-08:

        «Ninguno promete un plazo en horas. Se dice el día -- "el miércoles 26" -- o no se
         dice nada.»

    Un aviso que dice "en 6 días" obliga al cliente a hacer la cuenta, y la hace mal: lo
    lee el jueves por la noche, cuenta desde el viernes y se le pasa.
    """
    dias = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
    return f"{dias[d.weekday()]} {d.day}"


# ── Las de calendario ─────────────────────────────────────────────────────────
# Van siempre: son el programa, no un recordatorio. No consumen el cupo semanal.

def avisos_de_calendario(*, perfil: Dict[str, Any], ahora: datetime,
                         arranque: Optional[datetime] = None,
                         proximo_ajuste: Optional[datetime] = None,
                         rutina_caduca: Optional[datetime] = None,
                         semanas_ciclo: Optional[int] = None,
                         macros_puestos_por_alguien: bool = False,
                         va_a_recibir_definitivos: bool = False,
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
    #
    # Y SOLO A QUIEN VA A RECIBIR UNOS DEFINITIVOS (punto 04 del doc del 19-08):
    #
    #     «Y dime a quién le sale. Ese mensaje promete unos definitivos, y eso solo se
    #      cumple en tres casos: plan personalizado, quien paga los 87 €, y la membresía
    #      cuando le toca pedirlos. Si le sale a alguien más, le estamos prometiendo algo
    #      que no va a recibir.»
    #
    # La tabla del apartado 10 lo cierra: sí a Gold, Silver, Bronze, Premium y a quien haya
    # pagado los 87 €; no a Mantenimiento ni a ninguno de los demás. Al de Calculadora nadie
    # le va a mandar nada el miércoles: sus macros son los que salen de su cuestionario, y
    # decirle que son provisionales es dejarle esperando una llamada que no existe.
    if (va_a_recibir_definitivos
            and not perfil.get("ajuste_macros_completado")
            and not macros_puestos_por_alguien):
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
                    # EL TEXTO ES DE JESUS Y VA LITERAL (punto 04 del doc del 19-08). Decia
                    # "Quince minutos y los tienes finos", y despues "Unas preguntas mas y
                    # los tienes finos", que era la propuesta de Francisco. Su respuesta:
                    # «"Finos" no lo digo yo. El texto es este.» Y estas dos lineas son las
                    # que escribio, tal cual.
                    "titulo": "Estos son tus macros provisionales.",
                    "cuerpo": "Unas preguntas más y recibirás los definitivos.",
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

    # El ajuste: aviso 6 dias antes, CON EL DIA (punto 06 del doc del 19-08).
    #
    #     «"Tu próximo ajuste: en 6 días" se queda y se reescribe: "Tu próximo ajuste es el
    #      miércoles 26".»
    #
    # Y el del mismo dia -- «Te tenemos los macros listos, solo faltan tus datos» -- SE CAE:
    # «dice lo mismo que el aviso de macros provisionales que acabamos de reescribir: es un
    # duplicado». Los dos le pedian lo mismo con dos redacciones distintas, y el cliente que
    # recibia los dos no sabia si eran dos encargos o uno.
    if proximo_ajuste:
        faltan = (proximo_ajuste.date() - hoy).days
        if faltan == 6:
            fuera.append({
                "clave": f"ajuste_pronto:{proximo_ajuste.date()}",
                "tipo": "reporte",
                "titulo": f"Tu próximo ajuste es el {_dia_es(proximo_ajuste)}",
                "cuerpo": None,
                "link": "/dashboard/reports",
                "calendario": True,
            })

    # "Tu rutina acaba el X": tres dias antes, no el dia que caduca. Con la Rutina apagada
    # este aviso no se manda: entero va de algo que el cliente no puede ver, y decirle
    # "renuevala" cuando no tiene donde es peor que no decirle nada.
    #
    # REESCRITO (punto 06 del doc del 19-08): «"Tu rutina acaba el 20 de agosto" se queda,
    # reescrito: "Tu rutina acaba el 20. Renuévala y sigues sin parar"». Solo el numero:
    # el aviso sale tres dias antes, asi que el mes no aporta nada y alarga el titulo.
    if rutina_caduca and rutina_visible:
        faltan = (rutina_caduca.date() - hoy).days
        if faltan == 3:
            fuera.append({
                "clave": f"rutina_caduca:{rutina_caduca.date()}",
                "tipo": "rutina",
                "titulo": f"Tu rutina acaba el {rutina_caduca.day}",
                "cuerpo": "Renuévala y sigues sin parar.",
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
                         faltan_fotos_o_medidas: Optional[List[str]] = None,
                         dias_sin_cerrar: Optional[int] = None,
                         dias_sin_entrar: Optional[int] = None,
                         dias_con_el_perfil_a_medias: Optional[int] = None,
                         dias_sin_preferencias: Optional[int] = None,
                         dias_en_mantenimiento: Optional[int] = None,
                         rutina_mes_aplazada_hasta: Optional[str] = None,
                         con_ajuste: bool = True) -> List[Dict[str, Any]]:
    """Las cuatro del doc 16-08 y una quinta del 18-08, en su orden de prioridad.

    LA QUINTA la pide Francisco el 18-08 contestando a la pregunta del documento del
    cuestionario: «Que pasa si un Gold no termina el completo. No puede quedarse en una
    tarjeta de Inicio que se ignora, porque sin fotos y medidas su entrenador no puede
    trabajar. ¿Se le avisa a los tres dias?». Si.

    Va la PRIMERA de todas: mientras no termine su perfil, su entrenador no puede ponerle
    los macros buenos ni montarle la rutina, asi que cualquier otro aviso llega antes de
    tiempo. Y sigue valiendo el tope de una condicionada por semana.

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

    # 0) EL PERFIL A MEDIAS (18-08). Tres dias, que es el plazo que pide el documento: antes
    #    de eso no ha pasado nada y meterle prisa el mismo dia es de mal gusto.
    #    Sin reproche y con el porque delante: no se le pide por pedir, se le pide porque su
    #    entrenador no puede trabajar sin eso.
    if dias_con_el_perfil_a_medias is not None and dias_con_el_perfil_a_medias >= 3:
        fuera.append({
            "clave": f"perfil_a_medias:{semana_iso}",
            "familia": "perfil_a_medias",
            "tipo": "perfil",
            "variantes": [
                # Plural siempre (punto 57 del 23-08) y fuera «montar» (punto 82).
                {"titulo": "Te falta terminar tu perfil",
                 "cuerpo": "Sin tus fotos y tus medidas no podemos ponerte los macros buenos "
                           "ni crearte la rutina."},
                {"titulo": "Nos falta lo tuyo para poder empezar",
                 "cuerpo": "Son unas preguntas, tus fotos y tus medidas. Con eso ya trabajamos."},
            ],
            "link": "/questionnaire",
            "calendario": False,
        })

    # 0.2) LA RUTINA DEL MES QUE APLAZÓ (doc 19-08): marcó «pregúntame en una semana» en el
    #    reporte, así que este aviso lo pidió él. Sale el día que él eligió, una sola vez
    #    (la clave lleva la fecha), y lleva al chat, que es donde puede contestar: su
    #    reporte ya está cerrado.
    if rutina_mes_aplazada_hasta and ahora.date().isoformat() >= rutina_mes_aplazada_hasta:
        fuera.append({
            "clave": f"rutina_mes_aplazada:{rutina_mes_aplazada_hasta}",
            "familia": "rutina_mes_aplazada",
            "tipo": "programa",
            "variantes": [
                {"titulo": "¿Te preparamos la rutina del mes?",
                 "cuerpo": "Nos dijiste que te lo preguntáramos esta semana. Escríbenos y te la dejamos lista."},
                {"titulo": "Lo de tu rutina del mes",
                 "cuerpo": "Quedamos en hablarlo esta semana. Dinos algo y te la preparamos."},
            ],
            "link": "/dashboard/messages",
            "calendario": False,
        })

    # 0.5) «HAN PASADO CUATRO SEMANAS» (doc 19-08): fotos y medidas en UN solo aviso, cada
    #    4 semanas, para los planes de autogestión -- donde no se piden, se recomiendan.
    #    Si ya hizo una de las dos, el aviso solo nombra la que falte. Antes llegaba cada
    #    semana y con otro texto, que es justo lo que el doc corrige.
    if faltan_fotos_o_medidas:
        que_falta = " y ".join(faltan_fotos_o_medidas)
        fuera.append({
            "clave": f"cuatro_semanas:{semana_iso}",
            "familia": "cuatro_semanas",
            "tipo": "seguimiento",
            "variantes": [
                {"titulo": "Han pasado cuatro semanas",
                 "cuerpo": f"Buen momento para repetir {que_falta}."},
                {"titulo": "Toca ponerse al día",
                 "cuerpo": f"Hace cuatro semanas de {que_falta}."},
            ],
            "link": "/dashboard/reports",
            "calendario": False,
        })

    # 1) Sin fotos no hay comparacion: es lo que mas le cuesta al cliente y lo que mas
    #    bloquea, asi que va primero.
    if reporte_sin_fotos:
        fuera.append({
            "clave": f"sin_fotos:{semana_iso}",
            "familia": "sin_fotos",
            "tipo": "reporte",
            "variantes": [
                # Plural siempre: lo DECIDIDO del punto 57 del 23-08 (citaba este aviso).
                {"titulo": "Sin fotos no podemos comparar",
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
    #    SOLO SI SU PLAN LLEVA AJUSTE (regla 1 del doc 19-08: «hoy al de Mantenimiento le
    #    llega "llevas 4 semanas con los mismos macros" y su plan no incluye ajuste»).
    if con_ajuste and semanas_sin_ajustar and semanas_sin_ajustar >= 2:
        # EL NÚMERO SE TOPA (punto 58 del doc del 23-08): a un cliente real migrado le
        # decía «llevas 133 semanas con los mismos macros», o sea dos años y medio
        # pagando sin que nadie le tocara nada. Pasado un ciclo entero (12 semanas) el
        # número exacto ya no informa: solo acusa.
        titulo = (f"Llevas {semanas_sin_ajustar} semanas con los mismos macros"
                  if semanas_sin_ajustar <= 12
                  else "Llevas más de 12 semanas con los mismos macros")
        fuera.append({
            "clave": f"sin_ajustar:{semana_iso}",
            "familia": "sin_ajustar",
            "tipo": "macros",
            "variantes": [
                {"titulo": titulo,
                 "cuerpo": "Con tus datos de estas semanas podemos mirarlo."},
                {"titulo": "Hace tiempo que no te ajustamos",
                 "cuerpo": "Cierra unos días seguidos y le echamos un ojo."},
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
                 "cuerpo": "Con dos toques al día nos vale."},
                {"titulo": "Te hemos perdido la pista",
                 "cuerpo": "Cinco días sin cerrar. ¿Todo bien?"},
            ],
            "link": "/dashboard/checkins",
            "calendario": False,
        })

    # 4) «¿Todo bien?» a los SIETE dias sin entrar (la tabla del doc 19-08; el 16-08 decia
    #    catorce y este manda). Sigue siendo la mas suave: el que no aparece no necesita
    #    que le recuerden lo que no ha hecho.
    if dias_sin_entrar is not None and dias_sin_entrar >= 7:
        fuera.append({
            "clave": f"sin_entrar:{semana_iso}",
            "familia": "sin_entrar",
            "tipo": "programa",
            "variantes": [
                {"titulo": "¿Todo bien?", "cuerpo": "Tu plan sigue aquí. Retomamos cuando quieras."},
                {"titulo": "Cuando quieras volver, aquí está", "cuerpo": "Sin prisa."},
            ],
            "link": "/dashboard",
            "calendario": False,
        })

    # 5) «Configura lo que comes» (tabla del doc 19-08): tres dias sin tocar las
    #    preferencias, EN TODOS LOS PLANES. Sin ellas la calculadora sugiere a ciegas.
    if dias_sin_preferencias is not None and dias_sin_preferencias >= 3:
        fuera.append({
            "clave": f"sin_preferencias:{semana_iso}",
            "familia": "sin_preferencias",
            "tipo": "perfil",
            "variantes": [
                {"titulo": "Configura lo que comes",
                 "cuerpo": "Marca lo que te gusta y lo que no, y te lo ponemos más fácil."},
                {"titulo": "Dinos qué te gusta comer",
                 "cuerpo": "Son 2 minutos y la calculadora te sugerirá mejor."},
            ],
            "link": "/dashboard/nutrition",
            "calendario": False,
        })

    # 6) «¿Volvemos?» (tabla del doc 19-08): SOLO Mantenimiento, al mes de aterrizar ahi.
    #    Una sola vez -- la clave es la fecha en que cayo al plan --, y con la puerta de
    #    vuelta delante.
    if dias_en_mantenimiento is not None and dias_en_mantenimiento >= 30:
        fuera.append({
            "clave": "volvemos:mantenimiento",
            "familia": "volvemos",
            "tipo": "programa",
            "variantes": [
                {"titulo": "¿Volvemos?",
                 "cuerpo": "Llevas un mes por tu cuenta. Si quieres que te llevemos otra vez, aquí estamos."},
                {"titulo": "Un mes ya por tu cuenta",
                 "cuerpo": "Cuando quieras retomar un plan con seguimiento, dínoslo."},
            ],
            "link": "/planes",
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
                             rutina_visible: bool = False,
                             ciclo_vencido: bool = False,
                             fin_de_ciclo: Optional[date] = None,
                             con_correo_de_novedades: bool = True) -> List[Dict[str, Any]]:
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
                {"titulo": "¿Cómo fuiste hoy?", "cuerpo": "Un minuto y lo tenemos."},
                {"titulo": "Te falta cerrar el día", "cuerpo": "Lo que no apuntas, no lo vemos."},
            ],
            "link": "/dashboard/checkins",
            "calendario": True,
        })

    for v in ventanas:
        tipo, abre, cierra = v.get("tipo"), v.get("abre"), v.get("cierra")
        if not tipo or not abre or not cierra:
            continue
        mandado = bool(v.get("mandado"))
        # «No puedo esta semana» apaga los recordatorios de ese reporte (doc 19-08): el que
        # avisó de que no puede no necesita que se le repita que no lo ha mandado. El aviso
        # de apertura no se toca: se dispara antes de que exista el aplazamiento.
        aplazado = bool(v.get("aplazado"))

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
                        {"titulo": "Cuéntanos estas dos semanas",
                         "cuerpo": "Es rápido, y con eso decidimos si te tocamos algo."},
                    ],
                    "link": "/dashboard/reports",
                    "calendario": True,
                })
            if not mandado and not aplazado and hoy == abre.date() + timedelta(days=1) and ahora_es.hour >= 9:
                fuera.append({
                    "clave": f"quincenal_ultimo:{abre.date()}",
                    "familia": "quincenal_ultimo",
                    "tipo": "reporte",
                    "variantes": [
                        {"titulo": "Último día para tu quincenal",
                         "cuerpo": "Se cierra hoy a las 20:00."},
                        {"titulo": "Hoy cierra tu quincenal",
                         "cuerpo": "A las 20:00. Sin él no sabemos cómo has ido estas dos semanas."},
                    ],
                    "link": "/dashboard/reports",
                    "calendario": True,
                })

        # El semanal (Premium/6M), calcado del quincenal (tarea 1.6), con la VENTANA DEL
        # DOC DEL 21-08 (apartado 15): abre el VIERNES a las 10:00 y cierra el SÁBADO a
        # las 10:00. La apertura anuncia desde la hora en que abre la ventana, como en el
        # quincenal. La insistencia va el sábado desde las 8:00 y no desde las 9:00: la
        # ventana cierra a las 10:00 de la mañana, y avisar a las 9:00 le dejaba una hora
        # de margen. Los textos ya prometen la hora: desde el 21-08 la ventana de estos
        # avisos y la real de envío (`_submission_window`) son la misma.
        if tipo == "semanal":
            if hoy == abre.date() and ahora_es >= abre:
                fuera.append({
                    "clave": f"semanal_abierto:{abre.date()}",
                    "familia": "semanal_abierto",
                    "tipo": "reporte",
                    "variantes": [
                        {"titulo": "Tu reporte semanal está abierto",
                         "cuerpo": "Unas breves preguntas para ajustar tu semana que viene. Tienes hasta mañana a las 10:00."},
                        {"titulo": "Toca semanal",
                         "cuerpo": "Cuatro preguntas. Tienes hasta mañana a las 10:00."},
                        {"titulo": "Cuéntanos esta semana",
                         "cuerpo": "Es rápido, y con eso decidimos si te tocamos algo."},
                    ],
                    "link": "/dashboard/reports",
                    "calendario": True,
                })
            if not mandado and not aplazado and hoy == cierra.date() and ahora_es.hour >= 8:
                fuera.append({
                    "clave": f"semanal_ultimo:{abre.date()}",
                    "familia": "semanal_ultimo",
                    "tipo": "reporte",
                    "variantes": [
                        {"titulo": "Última hora para tu semanal",
                         "cuerpo": "Se cierra hoy a las 10:00."},
                        {"titulo": "Hoy cierra tu semanal",
                         "cuerpo": "A las 10:00. Sin él no sabemos cómo has ido esta semana."},
                    ],
                    "link": "/dashboard/reports",
                    "calendario": True,
                })

        if tipo == "mensual":
            # 5 · El viernes que abre, desde su hora (el reloj del 19-08 la pone: 10:00).
            # Antes salía sin hora porque el doc del 16-08 no le ponía ninguna; avisarle
            # antes de que la ventana abra es mandarle a una puerta cerrada.
            if hoy == abre.date() and ahora_es >= abre:
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
            if not mandado and not aplazado and hoy == abre.date() + timedelta(days=2) and ahora_es.hour >= 10:
                fuera.append({
                    "clave": f"mensual_ultimo:{abre.date()}",
                    "familia": "mensual_ultimo",
                    "tipo": "reporte",
                    "variantes": [
                        {"titulo": "Último día para tu reporte mensual",
                         "cuerpo": "Se cierra mañana a las 18:00 y sin él no podemos ajustarte."},
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
            if not mandado and not aplazado and ahora_es > cierra and hoy == cierra.date() + timedelta(days=1):
                fuera.append({
                    "clave": f"reporte_no_llego:{cierra.date()}",
                    "familia": "reporte_no_llego",
                    "tipo": "reporte",
                    "variantes": [
                        # Plural siempre (punto 57 del 23-08), también en el aviso estrella.
                        {"titulo": "No nos llegó tu reporte",
                         "cuerpo": "Sin él no podemos ajustarte. Dinos si lo mandas esta semana o te lo aplazamos."},
                        {"titulo": "Se te pasó el reporte",
                         "cuerpo": "No pasa nada: dinos si lo haces esta semana y te lo volvemos a abrir."},
                    ],
                    "link": "/dashboard/reports",
                    "calendario": True,
                })

    # 8 · "Tu ciclo acaba en una semana". Desde el 20-08 NINGÚN plan renueva solo, así
    # que este aviso es la puerta de la renovación anticipada para todos. Dos caminos:
    #
    # 8a · POR FECHA, si se sabe cuándo se le acaba lo pagado (current_period_end): a 7
    #      días o menos del fin, una vez por vencimiento. Vale para el de 12 semanas y
    #      también para el mensual (ELM, Mantenimiento), que no tiene semanas de ciclo y
    #      con la regla de la penúltima semana se quedaba sin aviso.
    if fin_de_ciclo and 0 < (fin_de_ciclo - hoy).days <= 7:
        fuera.append({
            "clave": f"fin_ciclo:{cliente_id}:{fin_de_ciclo}",
            "familia": "fin_ciclo",
            "tipo": "programa",
            "variantes": [
                {"titulo": "Tu ciclo acaba en una semana",
                 "cuerpo": "Mira lo que has cambiado. Si renuevas ya, seguimos sin cortes: "
                           "el ciclo nuevo empieza donde acaba este."},
                {"titulo": "Queda una semana",
                 "cuerpo": "Compara tu primera foto con la de ahora, y deja renovado lo "
                           "que viene: no pierdes ni un día de los pagados."},
            ],
            "link": "/renovacion",
            "calendario": True,
        })
    # 8b · POR SEMANA (la penúltima, con el mensual), SOLO si no hay fecha: los perfiles
    #      viejos sin current_period_end no pueden quedarse sin enterarse.
    elif not fin_de_ciclo and semanas_ciclo and semana and int(semana) == max(1, int(semanas_ciclo) - 1):
        mensual = next((v for v in ventanas
                        if v.get("tipo") == "mensual" and v.get("semana") == semana), None)
        if not mensual or ahora_es >= mensual["abre"]:
            fuera.append({
                "clave": f"fin_ciclo:{cliente_id}:{semana}",
                "familia": "fin_ciclo",
                "tipo": "programa",
                "variantes": [
                    {"titulo": "Tu ciclo acaba en una semana",
                     "cuerpo": "Mira lo que has cambiado. Si renuevas ya, seguimos sin cortes: "
                               "el ciclo nuevo empieza donde acaba este."},
                    {"titulo": "Queda una semana",
                     "cuerpo": "Compara tu primera foto con la de ahora, y deja renovado lo "
                               "que viene: no pierdes ni un día de los pagados."},
                ],
                # A LA RENOVACIÓN, no a la evolución (Francisco, 20-08): la pantalla de
                # renovar ya enseña lo conseguido (fotos del día 1 y de hoy) y, desde ese
                # mismo día, pagar por adelantado encadena el ciclo en vez de pisarlo.
                "link": "/renovacion",
                "calendario": True,
            })

    # 9 · «Tu ciclo ha terminado», AL VENCER SIN RENOVAR (tabla del doc 19-08). Solo los
    # planes de ciclo cerrado llegan aquí (`ciclo_vencido` ya viene decidido: a los
    # mensuales que renuevan solos no les vence nada). Es de entrega -- un hecho, no una
    # prisa -- y su clave dura el vencimiento entero: no se repite cada día.
    if ciclo_vencido:
        fuera.append({
            "clave": f"ciclo_terminado:{cliente_id}",
            "familia": "ciclo_terminado",
            "tipo": "programa",
            "variantes": [
                {"titulo": "Tu ciclo ha terminado",
                 "cuerpo": "Renueva tu plan y sigues sin parar."},
                {"titulo": "Se acabaron tus 12 semanas",
                 "cuerpo": "Cuando quieras seguimos: tienes la renovación dentro."},
            ],
            "link": "/renovacion",
            "calendario": True,
        })

    # 10 · «Te hemos mandado el correo de novedades», los viernes (tabla del doc 19-08).
    # El correo se queda como correo; esto solo lo anuncia en la app. Desde mediodía, que
    # es cuando ya ha salido, y a todos los planes.
    if con_correo_de_novedades and ahora_es.weekday() == 4 and ahora_es.hour >= 12:
        fuera.append({
            "clave": f"correo_viernes:{hoy}",
            "familia": "correo_viernes",
            "tipo": "programa",
            "variantes": [
                {"titulo": "Te hemos mandado el correo de novedades",
                 "cuerpo": "Échale un ojo al correo: va lo de esta semana."},
                {"titulo": "El correo del viernes ya está fuera",
                 "cuerpo": "Mira tu bandeja: novedades de esta semana."},
            ],
            "link": None,
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
                  ahora: datetime, hubo_aviso_hoy: bool = False) -> List[Dict[str, Any]]:
    """Lo que de verdad se manda hoy: COMO MUCHO UNO (regla del doc 19-08).

        «Máximo uno al día, y por orden: primero el de entrega, después el de
         recordatorio. Si le llegan tres a la vez, no lee ninguno.»

    - `hubo_aviso_hoy` cierra el día entero: si ya le nació uno (de aquí o de un evento,
      como la entrega de macros del miércoles), lo demás espera a mañana. Lo que siga
      siendo verdad mañana saldrá mañana; lo que no, es que ya no hacía falta.
    - Con el día libre, gana la primera de CALENDARIO sin mandar (las de entrega y el
      programa). Solo si no hay ninguna entra UNA condicionada, respetando además su
      tope de una cada siete días.

    `claves_ya_enviadas` evita repetir un aviso que ya salio. `ultima_condicionada` es
    la fecha ISO de la ultima condicionada que se le mando.
    """
    if hubo_aviso_hoy:
        return []

    for aviso in calendario:
        if aviso["clave"] not in claves_ya_enviadas:
            return [aviso]

    dias = _dias_desde(ultima_condicionada, ahora)
    if dias is not None and dias < DIAS_ENTRE_CONDICIONADAS:
        return []   # esta semana ya tuvo la suya

    for aviso in condicionados:
        if aviso["clave"] not in claves_ya_enviadas:
            return [aviso]

    return []
