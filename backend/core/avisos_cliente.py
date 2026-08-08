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
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

# El tope de las condicionadas. Las de calendario no cuentan para esto.
DIAS_ENTRE_CONDICIONADAS = 7


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
                         semanas_ciclo: Optional[int] = None) -> List[Dict[str, Any]]:
    fuera: List[Dict[str, Any]] = []
    hoy = ahora.date()

    # "Tus macros son provisionales": a las 2 h de darse de alta, si aun no los ha ajustado.
    if not perfil.get("ajuste_macros_completado"):
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

    # "Mañana empiezas": el domingo de antes de arrancar.
    if arranque:
        dias_para_arrancar = (arranque.date() - hoy).days
        if dias_para_arrancar == 1:
            fuera.append({
                "clave": f"arranque:{arranque.date()}",
                "tipo": "programa",
                "titulo": "Mañana empiezas",
                "cuerpo": "Tu rutina ya está cargada.",
                "link": "/dashboard/routine",
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

    # "Tu rutina acaba el X": tres dias antes, no el dia que caduca.
    if rutina_caduca:
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
    if semanas_ciclo and semana and int(semana) == max(1, int(semanas_ciclo) - 1):
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
                         dias_sin_peso: Optional[int] = None,
                         dias_sin_dieta: Optional[int] = None,
                         semanas_sin_ajustar: Optional[int] = None,
                         reporte_sin_fotos: bool = False,
                         estancado: bool = False,
                         dias_sin_entrar: Optional[int] = None) -> List[Dict[str, Any]]:
    fuera: List[Dict[str, Any]] = []
    semana_iso = f"{ahora.isocalendar()[0]}-W{ahora.isocalendar()[1]:02d}"

    # 1) Sin fotos no hay informe: es lo que mas le cuesta al cliente y lo que mas
    #    bloquea, asi que va primero.
    if reporte_sin_fotos:
        fuera.append({
            "clave": f"sin_fotos:{semana_iso}",
            "tipo": "reporte",
            "titulo": "Sin fotos no podemos comparar",
            "cuerpo": "Te lleva un minuto y es lo que de verdad enseña lo que ha cambiado.",
            "link": "/dashboard/reports",
            "calendario": False,
        })

    # 2) La unica directa del documento. Factual, sin reproche, y el momento natural
    #    para ofrecerle que alguien le mire el caso.
    if semanas_sin_ajustar and semanas_sin_ajustar >= 2:
        fuera.append({
            "clave": f"sin_ajustar:{semana_iso}",
            "tipo": "macros",
            "titulo": f"Llevas {semanas_sin_ajustar} semanas con los mismos macros",
            "cuerpo": "Con tus datos de estas semanas podemos ajustarlos.",
            "link": "/dashboard/reports",
            "calendario": False,
        })

    # 3) Estancado, o no cumple, o el peso plano: aqui se le ofrece la revision.
    if estancado:
        fuera.append({
            "clave": f"revisar_caso:{semana_iso}",
            "tipo": "revision",
            "titulo": "¿Quieres que revisemos tu caso?",
            "cuerpo": "Le echamos un ojo a tus datos y te decimos qué tocar.",
            "link": "/dashboard",
            "calendario": False,
        })

    if dias_sin_peso is not None and dias_sin_peso >= 7:
        fuera.append({
            "clave": f"sin_peso:{semana_iso}",
            "tipo": "checkin",
            "titulo": "¿Te pesamos esta semana?",
            "cuerpo": "Con un dato nos vale.",
            "link": "/dashboard/checkins",
            "calendario": False,
        })

    if dias_sin_dieta is not None and dias_sin_dieta >= 5:
        fuera.append({
            "clave": f"sin_dieta:{semana_iso}",
            "tipo": "nutricion",
            "titulo": "¿Todo bien?",
            "cuerpo": "Cuéntanos cómo va en 30 segundos.",
            "link": "/dashboard/nutrition",
            "calendario": False,
        })

    # La mas suave de todas, y la ultima: el que lleva dos semanas sin aparecer no
    # necesita que le recuerden lo que no ha hecho.
    if dias_sin_entrar is not None and dias_sin_entrar >= 14:
        fuera.append({
            "clave": f"sin_entrar:{semana_iso}",
            "tipo": "programa",
            "titulo": "Tu plan sigue aquí",
            "cuerpo": "Retomamos cuando quieras.",
            "link": "/dashboard",
            "calendario": False,
        })

    return fuera


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
