"""
Modelos Pydantic para usuarios y autenticación.
"""
import math

from pydantic import BaseModel, EmailStr, ConfigDict, Field, field_validator
from typing import Optional, Dict, List, Any, Union

# Limites de cordura para los macros del perfil. Sin ellos cualquier PUT podia
# dejar guardado un valor absurdo (p. ej. protein=1e308) que luego se pintaba
# tal cual en la ficha del cliente.
MACRO_MAX_GRAMOS = 1500
MACRO_MAX_CALORIAS = 20000


def validar_dict_macros(v):
    """Valida un dict de macros suelto (protein/carbs/fat/calories y sus alias)."""
    if v is None:
        return v
    limpio = {}
    for k, val in v.items():
        if val is None:
            continue
        try:
            num = float(val)
        except (TypeError, ValueError):
            raise ValueError(f"Macro '{k}': valor no numerico")
        if not math.isfinite(num):
            raise ValueError(f"Macro '{k}': valor no finito")
        tope = MACRO_MAX_CALORIAS if k in ("calories", "calorias") else MACRO_MAX_GRAMOS
        if num < 0 or num > tope:
            raise ValueError(f"Macro '{k}': fuera de rango (0-{tope})")
        limpio[k] = num
    return limpio


def lista_desde_texto(v):
    """Un campo de lista con un texto suelto dentro no puede tumbar la pantalla entera.

    Un perfil de producción tenía `injuries: "no"` -- alguien escribió la respuesta en vez
    de marcar la casilla -- y eso convertía GET /clients/profile en un 500 EN CADA CARGA:
    el front se lo tragaba y ese cliente navegaba sin perfil, sin plan y sin acceso, sin que
    nada se lo dijera (QA del 15-08 en producción). La respuesta correcta a «no» es una
    lista vacía.
    """
    if isinstance(v, str):
        limpio = v.strip()
        if not limpio or limpio.lower() in ("no", "ninguna", "ninguno", "nada", "n/a", "-"):
            return []
        return [limpio]
    return v

# =========================================================
# CATÁLOGO DE PLANES (fuente única)
# =========================================================
# Refleja el documento "JG - Catálogo de Planes y Membresías".
#
# Campos de cada plan:
#   name           Nombre comercial.
#   estado         activo | legacy | especial | complemento.
#                    - activo:     se vende hoy.
#                    - legacy:     ya no se vende; se respeta a quien lo tenga.
#                    - especial:   personalizado, condiciones pactadas con el CEO.
#                    - complemento: producto suelto (no es una membresía asignable).
#   asignable      True si puede asignarse como plan/membresía de un cliente.
#   ciclo          tipo (mensual|trimestral|bimestral|semestral|unico|variable) y
#                  semanas (duración del ciclo; None si es mensual indefinido o variable).
#   precio         Importe de referencia (informativo; los pagos son mock).
#   precio_nota    Detalle textual del precio tal cual el catálogo.
#   precios        Opciones estructuradas [{label, importe, periodo}].
#   responsable    Quién gestiona el plan.
#   habilitaciones Qué habilita el plan al usuario. LOS SIETE INTERRUPTORES del doc del
#   19-08 («un solo sitio enciende y apaga todo lo demás») más los que ya había:
#       calculadora     personalizado | autogestion | sin_ajuste
#       edita_macros    bool · si el cliente puede tocar sus macros. De él sale si se le
#                       enseña la pestaña «Mis macros» (fallo 08 del doc del 19-08)
#       rutina          personalizada | del_mes | ninguna | opcional
#       reportes        lista de: quincenal, mensual, semanal
#       suplementacion  ninguna | guia | protocolo (fallo 10: eran un sí/no y son dos
#                       cosas distintas; True/False viejos se leen con
#                       `suplementacion_incluida`)
#       frecuencia_ajuste  ninguna | mensual | quincenal | semanal | al_renovar (fallo 09:
#                       es la que decide a quién se le abre la ventana cada semana)
#       feedback        texto: cada cuánto le escribe su entrenador (fallo 11, mitad 1)
#       canal_contacto  texto: dónde puede preguntar (fallo 11, mitad 2)
#       videollamadas   texto/número (fallo 09)
#       grupo_privado   bool (fallo 09)
#       tiempo_respuesta  texto (fallo 09)
#       audio_feedback  bool · el audio está incluido en los programas antiguos y solo
#                       estaba marcado en cuatro (doc 19-08)
#       materiales_recursos  bool · el catálogo premium de la Membresía
#       acompanamiento  solo_app | con_entrenador | con_entrenador_y_llamadas
#       frecuencia_contacto  semanal | quincenal | mensual | ninguna (heredado; el doc lo
#                       parte en feedback + canal_contacto, se conserva para lo que ya lo lee)
#
#   HARBIZ MURIÓ (fallo 07 del doc del 19-08): la fila se quitó de las 21 fichas.
#
#   renovacion     {automatica: bool, cada: texto} · quién renueva solo y quién no (doc
#                  19-08: «este campo no es informativo — de él salen a quién avisar de que
#                  se le acaba el ciclo y a quién no molestar»). No toca el cobro: cómo se
#                  cobra lo dice el Price de Stripe; esto dice qué debe ESPERAR la app.
#   stripe_price_env  Variable .env con el Price ID de Stripe ("" si no aplica).
#   billing_cycle_weeks  Longitud del ciclo de cobro recurrente (semanas).
#   en_una_linea    Que te llevas, en una frase. Va debajo del nombre donde se elige plan.
#
#   LOS NOMBRES SON LOS DEL DOC DEL 19-08 (fallo 01): Calculadora, Gold y Premium. «El
#   método / Con seguimiento / Acompañamiento total» eran de una versión anterior y eran
#   los que veía el cliente en su ficha. El codigo del plan NO cambia: por dentro siguen
#   siendo nivel1/2/3, asi que ni los perfiles ni Stripe ni el historial se enteran.

PLAN_CATALOG = {
    # ---------------- LOS TRES NIVELES (especificacion 31-07-2026, parte 1) ----------
    # Sustituyen a lo anterior como lo unico que se puede contratar. Ciclos de 12 semanas.
    # Al que ya tiene un plan viejo no se le cambia nada: sigue igual hasta que le toque
    # renovar, y entonces elige entre estos tres (ver RENOVACION_A y planes_contratables).
    #
    # OJO: no se pueden comprar hasta que existan sus productos en Stripe. Las variables
    # de .env de abajo estan vacias a proposito: hasta que se creen, el checkout devuelve
    # un 503 con un mensaje claro en vez de cobrar mal.
    "nivel1": {
        # La ficha del doc del 19-08, campo a campo ("Calculadora · 247 € · 12 semanas").
        # OJO CON EL COBRO: el importe real sale del Price de Stripe
        # (STRIPE_PRICE_NIVEL1); cambiarlo aquí cambia el escaparate. El Price de 247 lo
        # tiene que crear Francisco en Stripe y poner su id en el .env.
        "name": "Calculadora", "en_una_linea": "Menos acompañamiento, mismo método",
        "estado": "activo", "asignable": True,
        "ciclo": {"tipo": "trimestral", "semanas": 12},
        "precio": 247.0, "precio_nota": "247€ por ciclo de 12 semanas",
        "precios": [{"label": "Ciclo", "importe": 247.0, "periodo": "12 semanas"}],
        "responsable": "Ninguno (autogestión)",
        "habilitaciones": {"calculadora": "autogestion", "edita_macros": True,
                           "frecuencia_ajuste": "mensual",
                           # «Rutina: La del mes» (antes ninguna: la ficha del doc manda).
                           "rutina": "del_mes",
                           # «El rápido, mensual — el mismo que tiene hoy ELM» (tabla del
                           # bloque 11, doc 19-08): la cadencia es mensual pero el
                           # formulario es el corto, no el de bloques.
                           "reportes": ["mensual"], "reporte_rapido": True,
                           "suplementacion": "guia",
                           "feedback": "Ninguno",
                           "canal_contacto": "Solo incidencias técnicas",
                           "videollamadas": "0", "grupo_privado": False,
                           "tiempo_respuesta": "", "audio_feedback": False,
                           "materiales_recursos": False,
                           "acompanamiento": "solo_app", "frecuencia_contacto": "ninguna"},
        # «Renovación automática: Sí · cada 12 semanas». Informa a la app (avisos, panel);
        # el modo de cobro real lo dice Stripe.
        "renovacion": {"automatica": False, "cada": "cada 12 semanas"},
        "stripe_price_env": "STRIPE_PRICE_NIVEL1", "billing_cycle_weeks": 12,
        # Doc 03-08: PAGO UNICO del ciclo en el checkout actual. La tabla del 19-08 lo
        # marca con renovación automática; cambiar el cobro a suscripción es un Price
        # recurrente en Stripe, no un flag de aquí.
        "pago_unico": True,
    },
    "nivel2": {
        # La ficha del doc del 19-08 ("Gold · 847 € · 12 semanas"). El Price de 847 lo
        # tiene que crear Francisco en Stripe.
        "name": "Gold", "en_una_linea": "Más gente encima de tus números",
        "estado": "activo", "asignable": True,
        "ciclo": {"tipo": "trimestral", "semanas": 12},
        "precio": 847.0, "precio_nota": "847€ por ciclo de 12 semanas",
        "precios": [{"label": "Ciclo", "importe": 847.0, "periodo": "12 semanas"}],
        "responsable": "Jesús",
        "habilitaciones": {"calculadora": "personalizado", "edita_macros": False,
                           "frecuencia_ajuste": "quincenal",
                           "rutina": "personalizada",
                           "reportes": ["quincenal", "mensual"],
                           "suplementacion": "protocolo",
                           "feedback": "Con cada reporte",
                           "canal_contacto": "Chat de dudas",
                           "tiempo_respuesta": "menos de 24 h",
                           "videollamadas": "0", "grupo_privado": False,
                           "audio_feedback": True, "materiales_recursos": False,
                           "acompanamiento": "con_entrenador",
                           "frecuencia_contacto": "quincenal"},
        # «Renovación automática: No · se recontrata».
        "renovacion": {"automatica": False, "cada": "se recontrata"},
        "stripe_price_env": "STRIPE_PRICE_NIVEL2", "billing_cycle_weeks": 12,
        "pago_unico": True,
    },
    "nivel3": {
        # EL PREMIUM DE VERDAD (fallo 03 del doc del 19-08): estaba por duplicado, esta
        # ficha a 1.500 € con 0 clientes y un «Premium» en especiales a 0 € con los 9.
        # Queda UNO, este, en activos; los 9 se mueven aquí con el precio que tienen
        # (script _mover_premium_a_nivel3.py, se ejecuta en prod con el OK de Francisco).
        # "Cómo se compra: por llamada". No lleva a un pago, lleva a agendar.
        "name": "Premium", "en_una_linea": "Hablamos antes de entrar",
        "estado": "activo", "asignable": True,
        "ciclo": {"tipo": "trimestral", "semanas": 12},
        "precio": 1500.0, "precio_nota": "1.500€ por ciclo de 12 semanas · se contrata por llamada",
        "precios": [{"label": "Ciclo", "importe": 1500.0, "periodo": "12 semanas"}],
        "responsable": "Jesús",
        "habilitaciones": {"calculadora": "personalizado", "edita_macros": False,
                           "frecuencia_ajuste": "semanal",
                           "rutina": "personalizada",
                           "reportes": ["semanal", "mensual"],
                           "suplementacion": "protocolo",
                           "feedback": "Semanal",
                           "canal_contacto": "Chat + WhatsApp del entrenador",
                           "tiempo_respuesta": "",
                           "videollamadas": "Una al mes · 3 por ciclo",
                           "grupo_privado": True,   # con clase en directo al mes
                           "audio_feedback": True, "materiales_recursos": False,
                           "acompanamiento": "con_entrenador_y_llamadas",
                           "frecuencia_contacto": "semanal"},
        # «Renovación automática: No · se renueva por llamada».
        "renovacion": {"automatica": False, "cada": "se renueva por llamada"},
        "stripe_price_env": "STRIPE_PRICE_NIVEL3", "billing_cycle_weeks": 12,
        "pago_unico": True,
    },
    # ---------------- ACTIVOS ----------------
    "elm": {
        # EL LUNES EMPIEZO SUBE A ACTIVOS (fallos 04 y 05 del doc del 19-08). Había una
        # ficha «Membresía» vacía a 97 € sin un solo cliente duplicándolo: se borró y esta
        # es la buena (el alias «membresia» cae aquí, para que nada que apuntara a aquella
        # se quede sin plan). Es la membresía: la entrada barata y la SALIDA del que no
        # renueva su ciclo (`solo_salida` lo pone en la pantalla de renovación).
        #
        # Y SU FICHA YA NO SE CONTRADICE: decía «macros por tu entrenador» (personalizado)
        # y «sin entrenador» a la vez. Es autogestión con ajuste automático, como dice su
        # ficha del doc, y el que lo tiene edita sus macros.
        #
        # A los 55 no se les toca el precio: hay quien paga 67 y quien paga 87 (el precio
        # de cada cliente vive en su perfil; este es el de catálogo para el que entre).
        "name": "El Lunes Empiezo", "estado": "activo", "asignable": True,
        "ciclo": {"tipo": "mensual", "semanas": None},
        "precio": 97.0, "precio_nota": "97€/mes · la membresía (antiguos 67€ u 87€ · 800€/año)",
        "precios": [{"label": "Mensual", "importe": 97.0, "periodo": "mes"},
                    {"label": "Anual", "importe": 800.0, "periodo": "año"}],
        "responsable": "Ninguno (autogestión)",
        "habilitaciones": {"calculadora": "autogestion", "edita_macros": True,
                           "frecuencia_ajuste": "al_renovar",   # si lo pide · máx. 72 h
                           "rutina": "del_mes",                 # la del mes, cada renovación
                           "reportes": [],                      # el rápido va con la renovación
                           # Si algún día su calendario trae un reporte, es el corto: «el
                           # rápido, al renovar» (tabla del bloque 11). El disparo POR
                           # RENOVACIÓN aún no existe; esto deja dicho el formulario.
                           "reporte_rapido": True,
                           "suplementacion": "guia",
                           "feedback": "Ninguno",
                           "canal_contacto": "Apartado de contacto · viernes",
                           "videollamadas": "0", "grupo_privado": False,
                           "tiempo_respuesta": "máx. 72 h", "audio_feedback": False,
                           "materiales_recursos": True,         # sí · catálogo premium
                           "acompanamiento": "solo_app", "frecuencia_contacto": "ninguna"},
        # NINGÚN PLAN RENUEVA SOLO (Francisco, 20-08): la membresía también se cobra como
        # pago único del mes y se renueva desde la app. La ficha del doc decía «Sí ·
        # mensual», pero la renovación real del negocio es manual.
        "renovacion": {"automatica": False, "cada": "mensual"},
        "pago_unico": True,
        "stripe_price_env": "STRIPE_PRICE_ELM", "billing_cycle_weeks": 4,
        # La ficha «Membresía» borrada apuntaba aquí; los perfiles de prueba que la tengan
        # escrita caen en ELM en vez de quedarse sin plan.
        "alias": ["membresia", "membresía", "Membresía"],
    },
    "reto12en12_gold": {
        # El "Reto de 1.500" del documento. Legacy. El doc del 19-08 lo manda RETIRAR
        # después de mover a sus 2 clientes (script preparado); mientras tanto se queda
        # asignable para no dejar a esos 2 sin habilitaciones.
        "name": "Reto 12en12 - Gold", "estado": "legacy", "renovable_por_los_suyos": True, "asignable": True,
        "ciclo": {"tipo": "trimestral", "semanas": 12},
        "precio": 1500.0, "precio_nota": "1.500€/trimestre o 600€/mes",
        "precios": [{"label": "Trimestral", "importe": 1500.0, "periodo": "trimestre"},
                    {"label": "Mensual", "importe": 600.0, "periodo": "mes"}],
        "responsable": "Jesús",
        # Con entrenador → no toca sus macros (regla de los legacy, doc 19-08).
        "habilitaciones": {"calculadora": "personalizado", "edita_macros": False,
                           "rutina": "personalizada",
                           "reportes": ["quincenal", "mensual"], "suplementacion": "protocolo",
                           "audio_feedback": True},
        "renovacion": {"automatica": False, "cada": "su ciclo de siempre"},
        "stripe_price_env": "STRIPE_PRICE_RETO12EN12_GOLD", "billing_cycle_weeks": 12,
    },
    "reto12en12_silver": {
        # Misma familia que el Reto Gold. Sin clientes: el doc del 19-08 lo retira.
        "name": "Reto 12en12 - Silver", "estado": "legacy", "renovable_por_los_suyos": True, "asignable": False,
        "ciclo": {"tipo": "trimestral", "semanas": 12},
        "precio": 600.0, "precio_nota": "600€/trimestre o 250€/mes · retirado (0 clientes)",
        "precios": [{"label": "Trimestral", "importe": 600.0, "periodo": "trimestre"},
                    {"label": "Mensual", "importe": 250.0, "periodo": "mes"}],
        "responsable": "José Luis",
        "habilitaciones": {"calculadora": "personalizado", "edita_macros": False,
                           "rutina": "del_mes",
                           "reportes": ["mensual"], "suplementacion": "protocolo"},
        "renovacion": {"automatica": False, "cada": "su ciclo de siempre"},
        "stripe_price_env": "STRIPE_PRICE_RETO12EN12_SILVER", "billing_cycle_weeks": 12,
    },
    "reto60": {
        # Sin clientes: el doc del 19-08 lo retira. (Y Harbiz murió: fallo 07.)
        "name": "Reto 60 días", "estado": "legacy", "renovable_por_los_suyos": True, "asignable": False,
        "ciclo": {"tipo": "bimestral", "semanas": 8},
        "precio": 547.0, "precio_nota": "547€ (pago único) · retirado (0 clientes)",
        "precios": [{"label": "Único", "importe": 547.0, "periodo": "único"}],
        "responsable": "Jesús",
        "habilitaciones": {"calculadora": "personalizado", "edita_macros": False,
                           "rutina": "del_mes",
                           "reportes": [], "suplementacion": "ninguna"},
        "renovacion": {"automatica": False, "cada": "pago único"},
        "stripe_price_env": "STRIPE_PRICE_RETO60", "billing_cycle_weeks": 8,
    },
    "calculadora_jp": {
        # Legacy. El doc del 19-08: migrar a sus 11 a Mantenimiento -- «pueden editar sus
        # macros pero sin ajuste» -- y después retirar (script preparado).
        "name": "Calculadora JP", "estado": "legacy", "renovable_por_los_suyos": True, "asignable": True,
        "ciclo": {"tipo": "mensual", "semanas": None},
        "precio": 60.0, "precio_nota": "60€/mes",
        "precios": [{"label": "Mensual", "importe": 60.0, "periodo": "mes"}],
        "responsable": "Ninguno (autogestión)",
        # Autogestión → sí toca sus macros (regla de los legacy, doc 19-08).
        "habilitaciones": {"calculadora": "autogestion", "edita_macros": True,
                           "frecuencia_ajuste": "ninguna", "rutina": "ninguna",
                           "reportes": [], "suplementacion": "ninguna"},
        "renovacion": {"automatica": False, "cada": "mensual"},
        "stripe_price_env": "STRIPE_PRICE_CALCULADORA_JP", "billing_cycle_weeks": 4,
    },
    "mantenimiento": {
        # SUBE A ACTIVOS (fallo 06 del doc del 19-08): «es donde aterriza todo el que
        # termina un ciclo y no renueva. Son cinco los que se venden, no cuatro». Su ficha
        # del doc: calculadora sí SIN ajuste — puede editar sus macros, pero nadie se los
        # revisa (frecuencia de ajuste: ninguna).
        #
        # `solo_salida`: es la salida que ofrece la pantalla de renovación al que no
        # renueva (antes lo era la «Membresía» vacía que se borró). ELM se vende por su
        # embudo; a Mantenimiento se aterriza.
        "name": "Mantenimiento", "estado": "activo", "asignable": True,
        "solo_salida": True,
        "ciclo": {"tipo": "mensual", "semanas": None},
        "precio": 60.0, "precio_nota": "60€/mes",
        "precios": [{"label": "Mensual", "importe": 60.0, "periodo": "mes"}],
        "responsable": "Jesús",
        "habilitaciones": {"calculadora": "autogestion", "edita_macros": True,
                           "frecuencia_ajuste": "ninguna",
                           "rutina": "opcional",
                           "reportes": [], "suplementacion": "guia",
                           "feedback": "Ninguno", "canal_contacto": "Ninguno",
                           "videollamadas": "0", "grupo_privado": False,
                           "tiempo_respuesta": "", "audio_feedback": False,
                           "materiales_recursos": False,
                           "acompanamiento": "solo_app", "frecuencia_contacto": "ninguna"},
        # Ningún plan renueva solo (Francisco, 20-08): también el Mantenimiento.
        "renovacion": {"automatica": False, "cada": "mensual"},
        "pago_unico": True,
        "stripe_price_env": "STRIPE_PRICE_MANTENIMIENTO", "billing_cycle_weeks": 4,
    },
    # ---------------- LEGACY (inactivos, se respetan) ----------------
    # La regla del doc del 19-08 para todos ellos: al legacy CON entrenador (Gold, Silver,
    # Bronze, Reto Gold, Personalizado y 6M) «edita sus macros: no» -- sin el campo, 68
    # personas seguían viendo una pestaña que les invita a mover unos macros que no pueden
    # mover --. A los de autogestión (Calculadora JP, Básica y CALMA 12), «sí». Y el audio
    # de feedback, que está incluido en los programas antiguos, marcado también en Silver,
    # Bronze, Premium, 6M, Personalizado y CALMA 12.
    "gold": {
        "name": "Gold (legacy)", "estado": "legacy", "renovable_por_los_suyos": True, "asignable": True,
        "ciclo": {"tipo": "trimestral", "semanas": 12},
        "precio": 450.0, "precio_nota": "450-847€/trimestre (según antigüedad)",
        "precios": [{"label": "Trimestral", "importe": 450.0, "periodo": "trimestre"}],
        "responsable": "Jesús",
        "habilitaciones": {"calculadora": "personalizado", "edita_macros": False,
                           "rutina": "personalizada",
                           "reportes": ["quincenal", "mensual"], "suplementacion": "protocolo",
                           # La tabla del bloque 11 (doc 19-08): «el feedback es solo del
                           # Gold y del Premium».
                           "feedback": "Con cada reporte",
                           "audio_feedback": True},
        "renovacion": {"automatica": False, "cada": "su ciclo de siempre"},
        "stripe_price_env": "STRIPE_PRICE_GOLD", "billing_cycle_weeks": 12,
    },
    "silver": {
        "name": "Silver (legacy)", "estado": "legacy", "renovable_por_los_suyos": True, "asignable": True,
        "ciclo": {"tipo": "trimestral", "semanas": 12},
        "precio": 267.0, "precio_nota": "267-435€/trimestre (según antigüedad)",
        "precios": [{"label": "Trimestral", "importe": 267.0, "periodo": "trimestre"}],
        "responsable": "Jesús",
        "habilitaciones": {"calculadora": "personalizado", "edita_macros": False,
                           "rutina": "del_mes",
                           "reportes": ["mensual"], "suplementacion": "protocolo",
                           # «Ninguno — recibe ajustes, no feedback» (bloque 11 del 19-08).
                           # El audio sí: es la diferencia con el Bronze.
                           "feedback": "Ninguno · recibe ajustes, no feedback",
                           "audio_feedback": True},
        "renovacion": {"automatica": False, "cada": "su ciclo de siempre"},
        "stripe_price_env": "STRIPE_PRICE_SILVER", "billing_cycle_weeks": 12,
    },
    "bronze": {
        "name": "Bronze (legacy)", "estado": "legacy", "renovable_por_los_suyos": True, "asignable": True,
        "ciclo": {"tipo": "trimestral", "semanas": 12},
        "precio": 177.0, "precio_nota": "177-397€/trimestre (según antigüedad)",
        "precios": [{"label": "Trimestral", "importe": 177.0, "periodo": "trimestre"}],
        "responsable": "Jesús",
        # Doc 16-08 (T8): el Bronze SÍ hace el reporte mensual (11 bloques) y el cierre
        # del día, que van detrás de la habilitación de reportes. Sin "mensual" aquí, un
        # bronze no podía abrir ni el reporte ni el "¿Cómo fuiste hoy?" (403 en
        # /checkins). El quincenal sigue siendo solo de quien lo tenga (gold).
        "habilitaciones": {"calculadora": "personalizado", "edita_macros": False,
                           "rutina": "opcional",
                           "reportes": ["mensual"], "suplementacion": "protocolo",
                           # La tabla del bloque 11 (doc 19-08): el Bronze no lleva ni
                           # feedback ni audio; recibe ajustes. El audio es del Silver
                           # para arriba.
                           "feedback": "Ninguno · recibe ajustes, no feedback",
                           "audio_feedback": False},
        "renovacion": {"automatica": False, "cada": "su ciclo de siempre"},
        "stripe_price_env": "STRIPE_PRICE_BRONZE", "billing_cycle_weeks": 12,
    },
    # ---------------- ESPECIALES ----------------
    "premium": {
        # FUSIONADO CON EL NUEVO PREMIUM (fallo 03 del doc del 19-08): el Premium que se
        # vende es `nivel3`, a 1.500 € por 12 semanas. Esta ficha era la de «especiales» a
        # 0 € con los 9 clientes; queda en legacy hasta que el script los mueva a nivel3
        # con el precio que tiene cada uno, y entonces se retira.
        "name": "Premium (fusionado con el nuevo)", "estado": "legacy", "renovable_por_los_suyos": True, "asignable": True,
        "ciclo": {"tipo": "variable", "semanas": None},
        "precio": 0.0, "precio_nota": "Sin precio de catálogo: manda el contrato · se fusiona con Premium (nivel3)",
        "precios": [],
        "responsable": "Jesús",
        "habilitaciones": {"calculadora": "personalizado", "edita_macros": False,
                           "rutina": "personalizada",
                           "reportes": ["semanal", "mensual"], "suplementacion": "protocolo",
                           "audio_feedback": True},
        "renovacion": {"automatica": False, "cada": "su ciclo de siempre"},
        "stripe_price_env": "", "billing_cycle_weeks": 4,
    },
    "plan_6m": {
        "name": "6M", "estado": "especial", "asignable": True,
        "ciclo": {"tipo": "semestral", "semanas": 26},
        "precio": 2500.0, "precio_nota": "2.500€ (6 meses); a veces 7 meses por 2.500€",
        "precios": [{"label": "Único", "importe": 2500.0, "periodo": "6 meses"}],
        "responsable": "Jesús",
        "habilitaciones": {"calculadora": "personalizado", "edita_macros": False,
                           "rutina": "personalizada",
                           "reportes": ["semanal", "mensual"], "suplementacion": "protocolo",
                           "audio_feedback": True},
        # «Plan Personalizado · 6M: No — manda el contrato».
        "renovacion": {"automatica": False, "cada": "manda el contrato"},
        "stripe_price_env": "", "billing_cycle_weeks": 26,
        # El «Plan 6 M (pero de 28 semanas, le regalo 1 mes)» de Calma, literal.
        "alias": ["Plan 6 M", "6M", "plan 6m"],
    },
    "calma12": {
        # CALMA 12 sale en el catálogo del equipo (bloque E del doc del 07-08) con dos
        # clientes activos, y NO estaba aquí. En la base hay perfiles con el plan escrito
        # "CalMa" tal cual, que hasta ahora no casaba con ninguna entrada del catálogo: sin
        # entrada, `plan_grants_feature` no encuentra habilitaciones y el cliente se queda
        # sin nada (ni reportes, ni suplementación, ni cadencia), y en las listas sale como
        # plan desconocido. Es el caso exacto que avisa el punto 38: la app tiene que saber
        # representarlos, no convertirlos.
        #
        # Las habilitaciones son las de un plan con coach detrás, que es lo que era. El
        # precio va vacío a propósito: el catálogo del equipo tampoco lo trae, y el que
        # manda es el del contrato de cada cliente (punto 36).
        "name": "CALMA 12", "estado": "legacy", "renovable_por_los_suyos": True, "asignable": True,
        "ciclo": {"tipo": "trimestral", "semanas": 12},
        "precio": 0.0, "precio_nota": "Sin precio de catálogo: manda el del contrato de cada cliente",
        "precios": [],
        "responsable": "Jesús",
        # De autogestión según la regla de los legacy del 19-08: «A los de autogestión
        # —Calculadora JP, Básica y CALMA 12— "sí"» (edita sus macros). Y con el audio
        # marcado, que está en su programa.
        "habilitaciones": {"calculadora": "personalizado", "edita_macros": True,
                           "rutina": "personalizada",
                           "reportes": ["mensual"], "suplementacion": "protocolo",
                           "audio_feedback": True,
                           "acompanamiento": "con_entrenador", "frecuencia_contacto": "mensual"},
        "renovacion": {"automatica": False, "cada": "su ciclo de siempre"},
        "stripe_price_env": "", "billing_cycle_weeks": 12,
        # Los perfiles migrados lo traen escrito asi, sin normalizar.
        "alias": ["CalMa", "calma", "calma_12", "calma 12"],
    },
    # ── LOS TRES QUE FALTABAN, TRAIDOS DE CALMA (17-08-2026) ─────────────────────────
    #
    # Francisco: «hay otros clientes que tienen planes que nosotros no manejamos» y «que
    # conserven la misma membresia, nada de cambios». Estos tres existen en Calma con
    # clientes activos hoy y aqui no estaban, asi que sus clientes figuraban como ELM: el
    # plan equivocado, y con el las habilitaciones equivocadas.
    #
    # Las habilitaciones NO se han elegido por el parecido del nombre: salen de los `items`
    # de la membresia de Calma, que son los 28 permisos numerados de su panel (la tabla
    # esta en su bundle, `_calma_ref/group-admin-miembros`). Medido sobre los 140 activos.
    "reto12en12": {
        # Sus items son EXACTAMENTE los de Gold, los dieciseis, uno a uno: reporte quincenal
        # (9), informe mensual (11), rutina 100 % personalizada (12), suplementacion (7),
        # ajuste cada 4 semanas (8), soporte extendido (16) y programa aerobico (19). No es
        # un plan con menos: es Gold con otro nombre comercial, y son 14 clientes activos.
        # Se le deja su nombre en vez de meterlos en "Reto 12en12 - Gold" porque lo que
        # compraron se llama asi.
        "name": "Reto 12en12", "estado": "legacy", "renovable_por_los_suyos": True, "asignable": True,
        "ciclo": {"tipo": "trimestral", "semanas": 12},
        # El doc del 19-08 los destapa: no es un plan, son los clientes Premium de José
        # Luis y de Montse, cada uno con su precio en la hoja de control de pagos. «A
        # revisar uno a uno y después retirar»: hasta esa revisión (decisión de Jesús y
        # los entrenadores, no un script) se queda tal cual.
        "precio": 0.0, "precio_nota": "Sin precio de catálogo: manda la hoja de control de pagos · a revisar uno a uno",
        "precios": [],
        "responsable": "José Luis",
        "habilitaciones": {"calculadora": "personalizado", "edita_macros": False,
                           "rutina": "personalizada",
                           "reportes": ["quincenal", "mensual"], "suplementacion": "protocolo",
                           "audio_feedback": True,
                           "acompanamiento": "con_entrenador",
                           "frecuencia_contacto": "quincenal"},
        "renovacion": {"automatica": False, "cada": "su ciclo de siempre"},
        "stripe_price_env": "", "billing_cycle_weeks": 12,
        "alias": ["Reto 12en12", "Reto12en12", "reto 12 en 12"],
    },
    "personalizado": {
        # «Plan Personalizado 500» y «550»: dos clientes, mismos items que Silver, con la
        # rutina «adaptada a tu nivel» (item 13) en vez de la 100 % personalizada y sin
        # reporte quincenal. El numero del nombre es lo que paga cada uno, y por eso el
        # precio va vacio: son dos acuerdos distintos.
        "name": "Plan Personalizado", "estado": "legacy", "renovable_por_los_suyos": True, "asignable": True,
        "ciclo": {"tipo": "trimestral", "semanas": 12},
        "precio": 0.0, "precio_nota": "Sin precio de catálogo: manda el del contrato de cada cliente",
        "precios": [],
        "responsable": "Jesús",
        "habilitaciones": {"calculadora": "personalizado", "edita_macros": False,
                           "rutina": "del_mes",
                           "reportes": ["mensual"], "suplementacion": "protocolo",
                           "audio_feedback": True,
                           "acompanamiento": "con_entrenador", "frecuencia_contacto": "mensual"},
        # «Plan Personalizado · 6M: No — manda el contrato».
        "renovacion": {"automatica": False, "cada": "manda el contrato"},
        "stripe_price_env": "", "billing_cycle_weeks": 12,
        "alias": ["Plan Personalizado 500", "Plan Personalizado 550"],
    },
    "basica": {
        # La mas pequeña de todas: sus items son DOS, el 1 y el 3. Programar dietas por
        # macros y buscador de alimentos. Ni siquiera puede editarse los macros (item 2, que
        # si tienen ELM y Calculadora JP), asi que la calculadora va en "sin_ajuste": ve lo
        # que le pongan y come con ello.
        "name": "Básica", "estado": "legacy", "renovable_por_los_suyos": True, "asignable": True,
        "ciclo": {"tipo": "mensual", "semanas": None},
        "precio": 0.0, "precio_nota": "Sin precio de catálogo: manda el del contrato de cada cliente",
        "precios": [],
        "responsable": "Ninguno (autogestión)",
        # De autogestión → edita sus macros sí (la regla de los legacy del 19-08 manda
        # sobre el item 2 de Calma que no lo incluía: al que se lleva solo no se le
        # enseña una pestaña que le prohíbe tocar). Y si edita, su calculadora es
        # autogestión: «sin ajuste» con permiso de editar es una contradicción.
        "habilitaciones": {"calculadora": "autogestion", "edita_macros": True,
                           "frecuencia_ajuste": "ninguna", "rutina": "ninguna",
                           "reportes": [], "suplementacion": "ninguna",
                           "acompanamiento": "solo_app", "frecuencia_contacto": "ninguna"},
        "renovacion": {"automatica": False, "cada": "su ciclo de siempre"},
        "stripe_price_env": "", "billing_cycle_weeks": 4,
        "alias": ["Basica", "básica"],
    },
    # ---------------- COMPLEMENTOS (no asignables como membresía) ----------------
    # «Hay dos y tienen que ser cuatro» (doc del 19-08): Rutina del Mes, Rutina
    # personalizada, Revisión de macros y Formaciones.
    "rutina_mes": {
        "name": "Rutina del Mes", "estado": "complemento", "asignable": False,
        "ciclo": {"tipo": "unico", "semanas": None},
        # DOS PRECIOS (doc 19-08): 57 EUR dentro de un plan -- el que se cobra desde el
        # reporte mensual, vive en `core/rutina_del_mes.PRECIO_EUR` y un test vigila que
        # no se separen -- y 67 EUR suelta, para el que no tiene ningún plan que la
        # incluya. «Calculadora y Bronze la llevan a 57. Suelta, cualquiera.»
        "precio": 57.0, "precio_nota": "57€ dentro de un plan · 67€ suelta",
        "precios": [{"label": "Dentro de un plan", "importe": 57.0, "periodo": "único"},
                    {"label": "Suelta", "importe": 67.0, "periodo": "único"}],
        "responsable": "Jesús",
        "habilitaciones": {"calculadora": "sin_ajuste", "rutina": "del_mes",
                           "reportes": [], "suplementacion": "ninguna"},
        "renovacion": {"automatica": False, "cada": "pago único"},
        "stripe_price_env": "", "billing_cycle_weeks": 4,
        # Las variantes de Calma que apuntan a este producto.
        "alias": ["Rutina del Mes Trimestral", "Rutina Premium Mensual"],
    },
    "rutina_personalizada": {
        # FALTABA CREARLO (doc 19-08): «Montada para esa persona · 97 € · quien quiera la
        # suya en vez de la del mes».
        "name": "Rutina personalizada", "estado": "complemento", "asignable": False,
        "ciclo": {"tipo": "unico", "semanas": None},
        "precio": 97.0, "precio_nota": "97€ (pago único) · la suya en vez de la del mes",
        "precios": [{"label": "Único", "importe": 97.0, "periodo": "único"}],
        "responsable": "Jesús",
        "habilitaciones": {"calculadora": "sin_ajuste", "rutina": "personalizada",
                           "reportes": [], "suplementacion": "ninguna"},
        "renovacion": {"automatica": False, "cada": "pago único"},
        "stripe_price_env": "", "billing_cycle_weeks": 4,
    },
    "revision_macros": {
        # FALTABA CREARLO (doc 19-08): «Incluye el ajuste a medida y el plan personalizado
        # de suplementación · 87 € · todo el que no lleve entrenador». El cobro ya está
        # montado (`core/ajuste_a_medida.py`, PRECIO_EUR = 87, punto 25); lo que no
        # existía era la ficha del catálogo, y sin ella la app no sabe a quién enseñarle
        # la oferta y a quién no. Se ofrece al terminar el alta y al final de la guía de
        # suplementación, y solo a quien no la tiene pagada.
        "name": "Revisión de macros", "estado": "complemento", "asignable": False,
        "ciclo": {"tipo": "unico", "semanas": None},
        "precio": 87.0, "precio_nota": "87€ · ajuste a medida + plan personalizado de suplementación",
        "precios": [{"label": "Único", "importe": 87.0, "periodo": "único"}],
        "responsable": "Jesús",
        "habilitaciones": {"calculadora": "sin_ajuste", "rutina": "ninguna",
                           "reportes": [], "suplementacion": "protocolo"},
        "renovacion": {"automatica": False, "cada": "pago único"},
        "stripe_price_env": "", "billing_cycle_weeks": 4,
    },
    "formaciones": {
        "name": "Formaciones / Lanzamientos", "estado": "complemento", "asignable": False,
        "ciclo": {"tipo": "unico", "semanas": None},
        "precio": 0.0, "precio_nota": "Variable (según cada lanzamiento)",
        "precios": [],
        "responsable": "Jesús",
        "habilitaciones": {"calculadora": "sin_ajuste", "rutina": "ninguna",
                           "reportes": [], "suplementacion": "ninguna"},
        "renovacion": {"automatica": False, "cada": "pago único"},
        "stripe_price_env": "", "billing_cycle_weeks": 4,
    },
    # ---------------- LO QUE YA SE VENDIÓ Y HAY QUE PODER COLGAR ----------------
    "optimizacion_hormonal": {
        # «El Plan de Optimización Hormonal a 1.000 € —que lleva Benito Velasco— va al
        # catálogo como legacy: ya se vendió y no se vende más, pero esos cobros tienen
        # que tener dónde colgar» (doc del 19-08).
        "name": "Plan de Optimización Hormonal", "estado": "legacy", "renovable_por_los_suyos": True, "asignable": False,
        "ciclo": {"tipo": "unico", "semanas": None},
        "precio": 1000.0, "precio_nota": "1.000€ · ya vendido, no se vende más",
        "precios": [{"label": "Único", "importe": 1000.0, "periodo": "único"}],
        "responsable": "José Luis",
        "habilitaciones": {"calculadora": "sin_ajuste", "rutina": "ninguna",
                           "reportes": [], "suplementacion": "ninguna"},
        "renovacion": {"automatica": False, "cada": "pago único"},
        "stripe_price_env": "", "billing_cycle_weeks": 4,
        "alias": ["Optimización Hormonal", "Optimizacion Hormonal"],
    },
    "entrenamiento_personal": {
        # Los «Entrenamiento Personal 2, 3 y 4 (1.200, 1.800 y 2.000 €)» de Calma, que no
        # existían en el catálogo nuevo: cuando se migren los 143 tienen que caer en algún
        # sitio «o pasará lo del CalMa que bloquea el alta» (doc del 19-08). Presencial de
        # los entrenadores; sin precio de catálogo, manda lo pactado.
        "name": "Entrenamiento Personal", "estado": "legacy", "renovable_por_los_suyos": True, "asignable": True,
        "ciclo": {"tipo": "variable", "semanas": None},
        "precio": 0.0, "precio_nota": "Sin precio de catálogo: 1.200-2.000€ según acuerdo",
        "precios": [],
        "responsable": "José Luis",
        "habilitaciones": {"calculadora": "personalizado", "edita_macros": False,
                           "rutina": "personalizada",
                           "reportes": ["mensual"], "suplementacion": "protocolo",
                           "acompanamiento": "con_entrenador_y_llamadas"},
        "renovacion": {"automatica": False, "cada": "manda el acuerdo"},
        "stripe_price_env": "", "billing_cycle_weeks": 4,
        "alias": ["Entrenamiento Personal 2", "Entrenamiento Personal 3",
                  "Entrenamiento Personal 4"],
    },
}

# Los «Premium 423,50 mensual · 250 a 5 semanas · 177 mensual · 200 mensual» y los ELM con
# apellido de Calma: variantes con precio propio de planes que ya existen. Caen en su plan
# por alias -- el precio de cada cliente va en su perfil, nunca en el catálogo.
ALIAS_EXTRA = {
    "premium 423,50 mensual": "premium", "premium 423.50 mensual": "premium",
    "premium 250 a 5 semanas": "premium", "premium 177 mensual": "premium",
    "premium 200 mensual": "premium",
    "lunes empiezo (anual)": "elm", "el lunes empiezo (julio)": "elm",
    "el lunes empiezo (agosto)": "elm", "lunes empiezo": "elm",
    "silver 4-trimestral": "silver",
}


def suplementacion_incluida(habilitaciones: Dict[str, Any]) -> bool:
    """Si el plan incluye algo de suplementación (la guía o el protocolo).

    El campo pasó de sí/no a tres opciones -- ninguna | guia | protocolo -- con el fallo
    10 del doc del 19-08, y los overrides guardados en la base pueden traer todavía el
    booleano viejo. «ninguna» es un texto y un texto es truthy: mirar el campo a pelo
    diría que un plan sin nada la incluye.
    """
    v = (habilitaciones or {}).get("suplementacion")
    if isinstance(v, str):
        return v.strip().lower() in ("guia", "guía", "protocolo")
    return bool(v)


def nivel_suplementacion(habilitaciones: Dict[str, Any]) -> str:
    """ninguna | guia | protocolo, tolerando el booleano viejo de los overrides.

    True viejo era «este plan lleva suplementación del coach»: se lee como protocolo,
    que es lo que era en todos los planes que lo tenían marcado.
    """
    v = (habilitaciones or {}).get("suplementacion")
    if isinstance(v, str):
        v = v.strip().lower().replace("guía", "guia")
        return v if v in ("ninguna", "guia", "protocolo") else "ninguna"
    return "protocolo" if v else "ninguna"


def derive_features(habilitaciones: Dict[str, Any]) -> List[str]:
    """Traduce la matriz de habilitaciones a la lista `features` que ya consume
    el resto del código (routines.py, frontend). Mantiene el vocabulario previo:
    rutina, macros, chat, reporte_quincenal, reporte_mensual, suplementacion, cardio, audio.
    """
    h = habilitaciones or {}
    reportes = h.get("reportes") or []
    features: List[str] = ["macros", "chat"]
    if h.get("rutina") in ("del_mes", "personalizada", "opcional"):
        features.append("rutina")
    if reportes:
        features.append("reportes")  # feature genérica: el plan incluye algún reporte/check-in
    if "quincenal" in reportes:
        features.append("reporte_quincenal")
    if "mensual" in reportes:
        features.append("reporte_mensual")
    if "semanal" in reportes:
        features.append("reporte_semanal")
    if suplementacion_incluida(h):
        features.append("suplementacion")
    if h.get("rutina") == "personalizada":
        features.append("cardio")
    # El audio con su campo propio (doc 19-08): estaba deducido del quincenal y por eso
    # solo constaba en cuatro planes cuando lo incluyen los programas antiguos. El
    # quincenal se mantiene como respaldo para overrides que no traigan el campo.
    if h.get("audio_feedback") or "quincenal" in reportes:
        features.append("audio")
    return features


# PLAN_TYPES: vista compatible con el código previo (name, price, stripe_price_env,
# billing_cycle_weeks, features) derivada del catálogo. No editar a mano: cambia PLAN_CATALOG.
PLAN_TYPES = {
    code: {
        "name": p["name"],
        "price": p["precio"],
        "stripe_price_env": p.get("stripe_price_env", ""),
        "billing_cycle_weeks": p.get("billing_cycle_weeks", 4),
        # Pago único: cobra una vez y el acceso dura el ciclo, sin renovar. Lo marca
        # `pago_unico` (los tres niveles, doc 03-08) o un precio de periodo "único"
        # (reto60 y compañía, que ya venían así).
        "one_time": bool(p.get("pago_unico")) or (p.get("precios") or [{}])[0].get("periodo") == "único",
        "features": derive_features(p.get("habilitaciones", {})),
    }
    for code, p in PLAN_CATALOG.items()
}


# Como esta escrito el plan en los perfiles migrados -> el codigo del catalogo. Los datos
# vienen de sitios distintos y no siempre normalizados ("CalMa" tal cual, con esas mayusculas),
# y un plan que no casa con el catalogo deja al cliente SIN habilitaciones: ni reportes, ni
# suplementacion, ni cadencia. Es lo que avisa el punto 38 del 07-08 -- la app tiene que saber
# representar los planes viejos, no convertirlos.
ALIAS_DE_PLAN: Dict[str, str] = {
    **{alias.lower().strip(): code
       for code, p in PLAN_CATALOG.items()
       for alias in (p.get("alias") or [])},
    **ALIAS_EXTRA,
}


def codigo_de_plan(plan: Optional[str]) -> str:
    """El codigo del catalogo para el plan de un perfil, resolviendo alias y mayusculas."""
    v = (plan or "").lower().strip()
    return ALIAS_DE_PLAN.get(v, v)


ACOMPANAMIENTO_OPCIONES = ("solo_app", "con_entrenador", "con_entrenador_y_llamadas")
FRECUENCIA_CONTACTO_OPCIONES = ("semanal", "quincenal", "mensual", "ninguna")


def completar_acompanamiento(hab: Dict[str, Any]) -> Dict[str, Any]:
    """Pone `acompanamiento` y `frecuencia_contacto` si el plan no los trae.

    Se añadieron con la especificacion del 31-07-2026, asi que ni los planes del
    catalogo ni los overrides que el admin ya tenia guardados los declaran. En vez de
    dejarlos vacios se deducen de algo que ya esta en el plan y es objetivo: la cadencia
    de reportes, que hoy ES la frecuencia con la que alguien mira a ese cliente.

    Es un punto de partida para que el panel tenga algo que enseñar, no una decision de
    negocio: en cuanto se repasen desde el panel manda lo que se ponga alli. Lo que NO
    se deduce de ningun dato existente es si el plan lleva llamadas; eso hay que
    marcarlo a mano (`con_entrenador_y_llamadas`).
    """
    hab = dict(hab or {})
    reportes = hab.get("reportes") or []

    if not hab.get("acompanamiento"):
        hab["acompanamiento"] = "con_entrenador" if reportes else "solo_app"

    if not hab.get("frecuencia_contacto"):
        for cadencia in ("semanal", "quincenal", "mensual"):
            if cadencia in reportes:
                hab["frecuencia_contacto"] = cadencia
                break
        else:
            hab["frecuencia_contacto"] = "ninguna"

    return hab


def get_plan(code: Optional[str]) -> Optional[Dict[str, Any]]:
    """Devuelve la entrada completa del catálogo (con code incluido) o None."""
    if not code:
        return None
    p = PLAN_CATALOG.get(code.lower().strip())
    if not p:
        return None
    hab = completar_acompanamiento(p.get("habilitaciones", {}))
    return {"code": code.lower().strip(), **p, "habilitaciones": hab,
            "features": derive_features(hab)}


def assignable_plan_codes() -> List[str]:
    """Códigos de planes que pueden asignarse como membresía de un cliente."""
    return [code for code, p in PLAN_CATALOG.items() if p.get("asignable")]


# Los tres niveles son lo unico que se puede contratar desde el 31-07-2026.
NIVELES = ("nivel1", "nivel2", "nivel3")


def planes_contratables(catalogo: Optional[Dict[str, Dict[str, Any]]] = None,
                        incluir_salida: bool = False) -> List[str]:
    """Lo que alguien puede contratar HOY: los planes en estado 'activo'.

    Un plan legacy sigue funcionando para quien lo tiene -- eso no se toca nunca -- pero
    no se le puede vender a nadie mas, ni siquiera al que ya lo tenia: cuando le toque
    renovar elige entre los nuevos (`opciones_de_renovacion`).

    La Membresia queda fuera salvo que se pida `incluir_salida`: no es un plan que se
    compre, es donde cae el que no renueva.
    """
    cat = catalogo or PLAN_CATALOG
    return [code for code, p in cat.items()
            if p.get("estado") == "activo" and p.get("asignable")
            and (incluir_salida or not p.get("solo_salida"))]


def opciones_de_renovacion(plan_actual: Optional[str],
                           catalogo: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Que se le ofrece a un cliente cuando acaba su ciclo.

    Regla: al renovar se elige entre los planes que se venden hoy, venga de donde venga.
    Al que esta en un plan legacy no se le cambia nada mientras dure su ciclo, pero al
    renovar no puede quedarse en el suyo porque ya no se vende.

    Devuelve tambien `mantiene_precio`: el precio se congela mientras no se de de baja
    (parte 1), asi que si renueva en su MISMO plan paga lo que pagaba. Si cambia de
    plan, paga el precio del nuevo.

    EXCEPCION: EL PLAN ANTIGUO REABIERTO PARA LOS SUYOS (Francisco, 16-08). Si el admin
    enciende `renovable_por_los_suyos` en un plan legacy, al que YA lo tiene se le deja
    seguir igual, con lo que ese plan incluye hoy y con su precio congelado. No es volver a
    vender el plan: sigue fuera de `opciones` -- de la tienda y de la lista de renovacion
    -- para todos los demas. Es solo no echar de su plan a quien lleva ahi desde antes.
    """
    cat = catalogo or PLAN_CATALOG
    actual = codigo_de_plan(plan_actual)
    info = cat.get(actual) or {}
    es_legacy = info.get("estado") in ("legacy", None) and actual not in NIVELES
    # Solo cuenta para un plan que existe y esta en legacy: encenderlo en un activo no
    # significa nada, y en un plan que no esta en el catalogo no hay nada que renovar.
    legacy_reabierto = bool(es_legacy and info and info.get("renovable_por_los_suyos"))

    return {
        "plan_actual": actual or None,
        "puede_seguir_igual": legacy_reabierto or (not es_legacy and info.get("estado") == "activo"),
        # Que su «seguir igual» es el de un plan que ya no se vende. Lo mira la pantalla de
        # renovacion: ese no renueva solo por Stripe (su suscripcion pudo cancelarse al
        # retirar el plan), asi que hay que llevarle al checkout en vez de decirle que no
        # tiene que hacer nada.
        "renovacion_legacy": legacy_reabierto,
        "opciones": planes_contratables(cat),
        # La tercera salida del documento ("renovar, subir de nivel, o salir a la
        # membresia"): no es una opcion de compra, es donde cae el que no renueva.
        "salida": next((c for c, p in cat.items()
                        if p.get("solo_salida") and p.get("estado") == "activo"), None),
        "mantiene_precio": legacy_reabierto or not es_legacy,
        "motivo": ("Tu plan ya no se ofrece: al renovar eliges entre los actuales"
                   if (es_legacy and not legacy_reabierto) else None),
    }


def puede_renovar_su_plan_legacy(plan_actual: Optional[str],
                                 catalogo: Optional[Dict[str, Dict[str, Any]]] = None) -> bool:
    """Si ESTE cliente puede renovar el plan antiguo que ya tiene.

    La usa el checkout: un plan legacy no se contrata (400 de siempre) salvo que su
    interruptor este encendido Y quien lo pide sea justo el que ya lo tiene. Vive aqui,
    junto a la regla de renovacion, para que las dos puertas no puedan decir cosas
    distintas.
    """
    return bool(opciones_de_renovacion(plan_actual, catalogo).get("renovacion_legacy"))


def plan_habilitaciones(code: Optional[str]) -> Dict[str, Any]:
    """Habilitaciones del plan (matriz). Vacío si el plan no existe."""
    p = PLAN_CATALOG.get((code or "").lower().strip())
    return completar_acompanamiento(p["habilitaciones"]) if p else {}


# Campos del catálogo que el admin puede sobrescribir desde el panel (guardados en
# db.plan_overrides). Lo demás (code, asignable, stripe_price_env) queda fijo por código.
#
# EL IMPORTE NO SE EDITA (Francisco, 16-08). `precio` y `precios` estaban aquí y no
# deberían haber estado nunca: lo que se cobra por Stripe no sale del catálogo, sale del
# Price ID de la variable de entorno (`stripe_price_env`, ver
# core/stripe_billing.get_stripe_price_id_for_plan). O sea que editar el precio en el
# panel cambiaba el escaparate -- la tarjeta del plan, la pantalla de renovación, «Mi
# perfil» -- y seguía cobrando lo de siempre, sin que nada avisara. Un precio que se puede
# escribir y no se cobra es peor que no poder escribirlo.
#
# Para cambiar un importe de verdad hay que crear el Price nuevo en Stripe (Stripe no deja
# editar importes: se archiva el viejo y se crea otro, ver setup_stripe_products.py),
# poner su id en la variable de entorno y actualizar el `precio` del catálogo aquí, en el
# código, que es donde se revisa y se despliega. `precio_nota` sí se sigue editando: es
# texto de escaparate y no lo lee ningún cobro.
PLAN_EDITABLE_FIELDS = {
    "name", "estado", "ciclo", "precio_nota",
    "responsable", "habilitaciones",
    # EL BOTÓN DEL PLAN ANTIGUO (Francisco, 16-08). Apagado por defecto. Encendido, el
    # cliente que YA tiene ese plan legacy puede renovarlo con lo que el plan incluye hoy
    # y con su precio congelado; al que no lo tiene el plan le sigue sin existir, ni en la
    # tienda ni en el checkout. Vive en el catálogo y no en un ajuste suelto porque es una
    # propiedad del plan, y así se ve al lado de su estado en el mismo sitio.
    "renovable_por_los_suyos",
    # QUIÉN RENUEVA SOLO Y QUIÉN NO (doc 19-08): {automatica: bool, cada: texto}. No es
    # informativo: de él salen a quién avisar de que se le acaba el ciclo y a quién no
    # molestar. No toca el cobro (eso es el Price de Stripe).
    "renovacion",
    # QUE INCLUYE, ESCRITO A MANO (punto 6.4 de la revision del 09-08). Hasta ahora «Tu plan
    # incluye» de Mi perfil se derivaba de la matriz de habilitaciones, y de ahi solo salen
    # frases de sistema: «Macros personalizados por tu entrenador», «Reporte quincenal». Eso
    # describe lo que la app enciende, no lo que se compro.
    #
    # Es un campo LIBRE, una linea por renglon, y solo se escribe para los cuatro planes que se
    # venden. Los antiguos se quedan con las lineas derivadas, que para lo que son -- planes
    # que ya no se contratan -- bastan.
    "que_incluye",
}


def merged_catalog(overrides_by_code: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
    """Catálogo con los overrides del admin aplicados sobre los valores por defecto.
    `overrides_by_code`: {code: {campo: valor, ...}} (normalmente leído de db.plan_overrides).
    Devuelve {code: entrada completa con `code` y `features` recalculadas}.

    LOS OVERRIDES VIEJOS DE PRECIO SE IGNORAN, NO SE BORRAN. En producción hay guardado al
    menos un override con `precio` dentro (el de `elm`), de cuando el importe se podía
    editar. El filtro de abajo ya los deja fuera solos: si el campo no está en
    PLAN_EDITABLE_FIELDS, no se copia. Manda el código, que es lo coherente -- ese importe
    nunca llegó a cobrarse, porque el cobro sale del Price de Stripe -- y el documento
    guardado se queda como está: borrarlo perdería el resto de campos que sí valen
    (nombre, nota de precio, habilitaciones) y no arregla nada.
    """
    overrides_by_code = overrides_by_code or {}
    out: Dict[str, Dict[str, Any]] = {}
    for code, base in PLAN_CATALOG.items():
        entry = {**base}
        ov = overrides_by_code.get(code) or {}
        for field, value in ov.items():
            if field not in PLAN_EDITABLE_FIELDS:
                continue
            # LAS HABILITACIONES SE MEZCLAN CLAVE A CLAVE, no de golpe (19-08). Los
            # overrides guardados antes de los interruptores nuevos traen el dict viejo
            # entero, y pisando de golpe borraban `edita_macros`, la suplementación de
            # tres valores y la renovación: el catálogo nuevo desaparecía justo en los
            # planes que alguien había tocado desde el panel.
            if field == "habilitaciones" and isinstance(value, dict):
                entry[field] = {**(base.get("habilitaciones") or {}), **value}
            else:
                entry[field] = value
        entry["code"] = code
        # Ningún plan del código lo declara: sin esto el panel no tendría qué pintar en el
        # interruptor hasta que alguien lo encendiera una vez.
        entry["renovable_por_los_suyos"] = bool(entry.get("renovable_por_los_suyos"))
        entry["habilitaciones"] = completar_acompanamiento(entry.get("habilitaciones", {}))
        # HARBIZ MURIÓ (fallo 07 del 19-08): la fila se quitó de las 21 fichas, y los
        # overrides viejos que la traen guardada no pueden resucitarla.
        entry["habilitaciones"].pop("harbiz", None)
        entry["features"] = derive_features(entry["habilitaciones"])
        out[code] = entry
    return out


def precio_de_ciclo(perfil: Dict[str, Any], catalogo: Dict[str, Any]) -> float:
    """Lo que paga este cliente cada ciclo.

    El `price` del perfil manda -- ahí van los precios pactados --, pero cuando está a cero
    o no está, el precio es el de SU PLAN en el catálogo. Eso era lo que enseñaba «0 €/ciclo»
    a clientes de pago sin cortesía marcada: los que vinieron de Calma llegaron con el campo
    a cero, y son **168 de los 174 activos**.

    Un cero SOLO se respeta cuando hay cortesía marcada (`comp_plan`), que es la casilla
    «Plan de cortesía (sin pago)» de la ficha. Sin ella, un cero no es una decisión: es un
    dato que no llegó.

    VIVE AQUÍ Y NO EN `routes/admin.py` (punto 2.4c, segunda vuelta): estaba dentro del
    módulo del panel, así que la lista del entrenador enseñaba el precio bueno y las dos
    pantallas donde lo mira quien paga -- «Mi perfil» del cliente y la pestaña Membresía de
    su ficha -- seguían con el cero. El precio de un cliente no puede depender de por qué
    endpoint se pregunte.
    """
    if perfil.get("comp_plan"):
        return 0.0
    propio = perfil.get("price")
    if propio not in (None, "", 0, 0.0):
        try:
            return float(propio)
        except (TypeError, ValueError):
            pass
    plan = (catalogo or {}).get(perfil.get("plan") or "") or {}
    try:
        return float(plan.get("precio") or 0)
    except (TypeError, ValueError):
        return 0.0


# Auth Models
class UserRegister(BaseModel):
    """Crear cuenta: correo y contraseña, nada más.

    El nombre y el teléfono eran obligatorios. Pedirle el teléfono a alguien que viene a
    por un dato gratis espanta a la mitad, y el nombre se puede pedir después, cuando ya
    tiene algo suyo delante. Siguen aceptándose porque el registro del panel los manda.
    """
    email: EmailStr
    password: str
    name: Optional[str] = None
    phone: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: str
    name: str
    phone: Optional[str] = None
    role: str
    plan: Optional[str] = None
    trainer_id: Optional[str] = None
    created_at: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# Client Profile Models
class ClientProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    user_id: str
    # OJO: plan y price son opcionales A PROPOSITO. El perfil se crea en cuanto el
    # usuario guarda sus preferencias de comida, que puede hacer ANTES de contratar
    # nada; exigirlos hacia que GET /clients/profile devolviera 500 y el frontend se
    # quedara sin perfil (sin plan, sin cuestionario inicial y con el acceso cerrado
    # aunque hubiera pagado). Sin plan = plan no contratado, que es un estado real.
    plan: Optional[str] = None
    price: Optional[float] = None
    week: int = 1
    # Ciclo calculado (ver core/cycle.py): inicio del ciclo y progreso derivado.
    cycle_start: Optional[str] = None
    cycle_number: Optional[int] = None
    cycle_total_weeks: Optional[int] = None
    status: str = "activo"
    trainer_id: Optional[str] = None
    next_payment: Optional[str] = None
    macros_training: Optional[Dict[str, float]] = None
    macros_rest: Optional[Dict[str, float]] = None
    macros_periworkout: Optional[Dict[str, float]] = None
    macros_source: Optional[str] = None
    macros_multiplicadores: Optional[Dict[str, float]] = None
    # Coach-set (Calma quiereRepartoDeComidas=false): the whole day's macros go to ONE comida.
    single_meal_mode: Optional[bool] = None
    # Lo que este cliente tiene de particular y no cabe en ningun campo (punto 39 del
    # 07-08). Sale en su ficha y salta al cobrar o al generarle algo.
    excepcion: Optional[str] = None
    # Si tiene acceso y por que no, cuando no (punto 41). Lo calcula el servidor:
    # {"activo": bool, "motivo": "sin_plan"|"sin_pagar"|"caducado"|None}.
    acceso: Optional[Dict[str, Any]] = None
    # Su % graso vigente y si toca volver a pedirlo (punto 47): {valor, fecha, semanas,
    # hay_que_pedirlo}. Se pide cada 12 semanas, no en cada ajuste.
    grasa: Optional[Dict[str, Any]] = None
    # «No quiero renovar» (doc 19-08): {motivo, motivo_clave, cuando}. Sin esto, el modelo
    # se comía la marca y a quien acababa de pedir la baja se le volvía a ofrecer el enlace.
    no_renovar: Optional[Dict[str, Any]] = None
    # Los tres ajustes que antes vivían en el navegador y se perdían al cambiar de móvil
    # (doc 19-08, bloque 07): {tema, modo_macros, vista}.
    ajustes_app: Optional[Dict[str, Any]] = None
    # Las medidas tomadas fuera del reporte (los botones de Seguimiento, doc 19-08).
    medidas_sueltas: Optional[List[Dict[str, Any]]] = None
    # ¿Sus macros los puso ALGUIEN, o salieron del calculo del alta? (punto 4.1)
    # Lo calcula el servidor mirando el ultimo apunte del historial. Sirve para no decirle a
    # un cliente al que su coach le acaba de ajustar los macros que los tiene "provisionales"
    # y que se los termine el. `ajuste_macros_completado` no vale para eso: es False para
    # todo el que no paso por NUESTRO cuestionario, y eso son 169 de los 174 activos.
    macros_puestos_por_alguien: Optional[bool] = None
    # ¿Puede el cliente ajustarse los macros? (punto 4.10): {puede, por_que_no}. Sale del
    # campo `habilitaciones.calculadora` del plan, que existia y no lo miraba nadie al
    # guardar: un cliente de plan personalizado podia machacar los de su entrenador.
    macros_ajustables: Optional[Dict[str, Any]] = None
    # Su entrenador, con nombre (punto 4.16): {id, nombre}. El cliente no tenia forma de
    # saberlo -- el listado del equipo es solo para admins -- y el chat le decia "Tu
    # Entrenador" en abstracto.
    entrenador: Optional[Dict[str, Any]] = None
    # LO QUE PAGA DE VERDAD CADA CICLO (punto 2.4c). `price` es el precio pactado y llega a
    # cero en los 168 perfiles que vinieron de Calma, asi que Mi perfil le decia «0 €/ciclo»
    # a un cliente de pago sin cortesia marcada -- «lo primero que va a ver quien reciba
    # acceso». Este campo lo resuelve el servidor con `precio_de_ciclo`: el suyo si lo tiene,
    # y si no el de su plan en el catalogo. Un cero solo se respeta con cortesia marcada.
    precio_ciclo: Optional[float] = None
    precio_cortesia: Optional[bool] = None
    # Cuando se le acaba lo pagado (punto 2.4d): {fecha, proximo_cobro, vencida}. `fecha` es
    # `current_period_end` o `fin_de_ciclo`; `proximo_cobro` es el `next_payment` de siempre,
    # que es otra cosa y era lo unico que se enseñaba.
    renovacion: Optional[Dict[str, Any]] = None
    # EL CONTRATO DE ESTE CLIENTE (punto 44 del 07-08). La duracion del ciclo NO es un
    # supuesto: hay planes de 4 semanas y de 5, y clientes con un ciclo distinto al de su
    # plan (es una de las 17 excepciones del punto 39, y aqui tiene donde vivir). Vacios =
    # se usa lo del plan.
    ciclo_semanas: Optional[int] = None
    # Desde que semana del ciclo empieza a tocarle reporte. Por defecto la penultima (los
    # de 4 semanas entran en la 3, los de 5 en la 4): se manda antes de terminar para poder
    # ajustar de cara al siguiente ciclo.
    semana_de_entrada: Optional[int] = None
    # Su calendario propio, si no sigue el de su plan: {"patron": [...], "dias": {...}}.
    calendario_reportes: Optional[Dict[str, Any]] = None
    # OJO con estos dos (punto 30 del 07-08): `weight` y `body_fat` son el ULTIMO valor de
    # sus series, calculado, no un dato que se guarde aparte. Los escribe solo
    # core/series_cliente.py; nadie mas debe ponerlos en un $set, o vuelven los dos pesos
    # distintos del punto 9. Las series llevan la fecha, que es lo que hay que ensenar al
    # lado del numero ("94 kg · hace 3 dias").
    weight: Optional[float] = None
    pesos: Optional[List[Dict[str, Any]]] = None                 # [{fecha, valor, origen}]
    height: Optional[float] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    goal: Optional[str] = None
    body_fat: Optional[float] = None
    porcentajes_grasos: Optional[List[Dict[str, Any]]] = None    # [{fecha, valor, origen}]
    equipment: Optional[List[str]] = None
    injuries: Optional[List[str]] = None
    # Observaciones del coach sobre el ENTRENAMIENTO: van con la maquinaria y las lesiones
    # porque es lo que se actualiza al leer el reporte (Jesus 05-08, punto 2.5: "el
    # entrenamiento lo llevo aparte").
    training_notes: Optional[str] = None
    training_days: Optional[int] = None
    # Cuestionario inicial obligatorio (ELM): respuestas y flag de completado.
    questionnaire_completed: Optional[bool] = None
    birthdate: Optional[str] = None
    training_experience: Optional[str] = None
    activity_level: Optional[str] = None
    biotype: Optional[str] = None
    # Motor v2: ultima version de las preguntas 5-8 (para precargar Ajustar macros).
    ajustes_macros: Optional[Dict[str, Any]] = None
    # Usa farmacos -> +10% proteina SOLO descanso. Lo fija el coach (o Nivel 1), nunca el cliente.
    farmacologia: Optional[bool] = None
    # Cuestionario Nivel 1 (perfil largo para el coach; no toca macros).
    nivel1: Optional[Dict[str, Any]] = None
    questionnaire_nivel1_completed: Optional[bool] = None
    # Cuestionario de ajuste (paso 2) hecho: hasta entonces sus macros son los provisionales
    # que salieron de las cuatro preguntas del alta.
    ajuste_macros_completado: Optional[bool] = None
    # Progreso del cuestionario, del alta o del ajuste: {respuestas, paso, flujo}. Se guarda a
    # cada respuesta para que pueda salirse y volver donde lo dejo. Se borra al terminarlo.
    ajuste_macros_progreso: Optional[Dict[str, Any]] = None
    # La oferta del final del alta para quien no lleva entrenador (doc del cuestionario,
    # 18-08): {quiere, respondido_at, cobrado}. TIENE QUE ESTAR DECLARADA AQUI: el modelo
    # ignora lo que no conoce, asi que un campo sin declarar se guarda en la base y no llega
    # nunca a la pantalla. Y de `cobrado` depende que se le abra el cuestionario completo.
    ajuste_a_medida: Optional[Dict[str, Any]] = None

    # ── LOS DOS CORREOS (bloque 6 del doc del 18-08) ────────────────────────────────
    # La app identifica al cliente por su correo: con el entra, con el cruzan los cobros de
    # Stripe y con el se enlaza su ficha. Si en el alta escribe otro distinto no se puede
    # cambiar el de acceso sin romper las tres cosas, asi que se guardan LOS DOS.
    #
    # `email_contacto` es el que escribio en el alta, y `email_preferido` dice a cual se le
    # escribe: "contacto" por defecto, porque es lo que le promete la pantalla («te
    # escribiremos a este, salvo que nos digas lo contrario»). Hasta hoy ese correo se tiraba
    # -- el alta lo pedia y no lo guardaba nadie -- y la promesa era mentira.
    #
    # OJO: el correo de recuperar la contraseña va SIEMPRE al de acceso, elija lo que elija.
    # Ese no es un aviso, es la llave de su cuenta.
    email_contacto: Optional[str] = None
    email_preferido: Optional[str] = None       # acceso | contacto

    # El dia que termino el basico. Con `questionnaire_completed` a secas no se sabe si el
    # que tiene el perfil largo a medias lleva un dia o tres semanas, que es justo lo que el
    # panel necesita para pintarlo.
    questionnaire_completed_at: Optional[str] = None

    # ── Lo que trae el básico (bloque 2 del doc del 18-08) ──────────────────────────
    # Lo contesta todo el mundo, así que vive aquí y no dentro de `nivel1`. Y por lo mismo
    # que arriba: sin declararlo, se guarda en la base y no lo ve ni la ficha del coach.
    profesion: Optional[str] = None
    como_me_conociste: Optional[str] = None
    proteinas_habituales: Optional[List[str]] = None
    # Su recorrido de peso, cada hito con su año.
    peso_maximo: Optional[float] = None
    peso_maximo_ano: Optional[int] = None
    peso_maximo_nota: Optional[str] = None
    peso_mejor_momento: Optional[float] = None
    peso_mejor_momento_ano: Optional[int] = None
    peso_mejor_momento_nota: Optional[str] = None
    foto_mejor_momento: Optional[str] = None
    peso_minimo: Optional[float] = None
    peso_minimo_ano: Optional[int] = None
    peso_minimo_nota: Optional[str] = None
    alergias: Optional[List[str]] = None
    lactosa: Optional[str] = None
    gluten: Optional[str] = None
    alergia_otra: Optional[str] = None
    dietas_previas: Optional[str] = None
    tiempo_intentandolo: Optional[str] = None
    motivo_apuntarse: Optional[str] = None
    # Punto de partida (paso 3 del doc): fotos y medidas del dia 1, que son la unica forma de
    # comparar dentro de un mes.
    punto_de_partida_hecho: Optional[bool] = None
    medidas_inicio: Optional[Dict[str, Any]] = None
    # Revision de macros comprada suelta: {estado, importe_eur, pagada_at, descuento_aplicado}.
    # Solo para quien se autogestiona; el plan con coach ya la lleva incluida.
    revision_suelta: Optional[Dict[str, Any]] = None
    # Onboarding guiado (tour de producto): progreso por usuario.
    onboarding_completed: Optional[bool] = None
    onboarding_step: Optional[str] = None
    # Checklist "Primeros pasos" del dashboard: cerrado/completado (no volver a mostrar).
    checklist_dismissed: Optional[bool] = None
    # ---- Stripe billing (suscripción) ----
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    subscription_status: Optional[str] = None        # active|trialing|past_due|canceled|incomplete|...
    checkout_status: Optional[str] = None            # draft|created|completed|attention_required
    current_period_start: Optional[str] = None
    current_period_end: Optional[str] = None
    cancel_at_period_end: Optional[bool] = None
    billing_cycle_days: Optional[int] = None
    payment_method_status: Optional[str] = None      # ok|caducada|actualizar_tarjeta
    payment_method_brand: Optional[str] = None
    payment_method_last4: Optional[str] = None
    payment_method_exp_month: Optional[int] = None
    payment_method_exp_year: Optional[int] = None
    payment_failure_count: Optional[int] = None
    last_payment_error: Optional[str] = None
    # Opcional por lo mismo que plan/price: hay perfiles creados por upsert (preferencias,
    # webhook de leads) que nunca lo escribieron.
    created_at: Optional[str] = None

    @field_validator("injuries", "equipment", mode="before")
    @classmethod
    def _texto_suelto_es_una_lista(cls, v):
        return lista_desde_texto(v)

class ClientProfileCreate(BaseModel):
    plan: str
    price: Optional[float] = None
    trainer_id: Optional[str] = None

class ClientProfileUpdate(BaseModel):
    # Los dos correos: el cliente puede cambiar a cuál se le escribe desde Mi perfil. El de
    # acceso NO se toca por aquí -- es con el que entra y con el que cruzan los cobros.
    email_contacto: Optional[str] = None
    email_preferido: Optional[str] = None       # acceso | contacto
    plan: Optional[str] = None
    price: Optional[float] = None
    week: Optional[int] = None
    status: Optional[str] = None
    trainer_id: Optional[str] = None
    macros_training: Optional[Dict[str, float]] = None
    macros_rest: Optional[Dict[str, float]] = None
    macros_periworkout: Optional[Dict[str, float]] = None
    macros_source: Optional[str] = None
    single_meal_mode: Optional[bool] = None
    # Uso ACTUAL de farmacologia -> +10 g de proteina en descanso. Solo por la ruta de
    # admin: en PUT /users/clients/profile se descarta (el cliente no se lo marca solo).
    farmacologia: Optional[bool] = None
    # RANGOS (punto 5.4). Sin esto se guardaban con un 200 tan tranquilo un peso de -80, uno
    # de 0 y uno de 5.000, y un % graso de 200. De ahi salen los pesos imposibles que aparecen
    # en el historico, y un peso malo no se queda quieto: entra en la serie, en la grafica, en
    # el calculo de macros y en lo que lee el agente para proponer el ajuste.
    #
    # Los limites son los que ya usaba la app en `core/series_cliente` para aceptar un pesaje
    # (25-300 kg y 3-60 % de grasa): si un valor no vale para la serie, tampoco vale para el
    # campo. Los macros ya validaban; esto faltaba.
    weight: Optional[float] = Field(None, ge=25, le=300)
    height: Optional[float] = Field(None, ge=100, le=250)
    age: Optional[int] = Field(None, ge=14, le=100)
    sex: Optional[str] = None
    goal: Optional[str] = None
    body_fat: Optional[float] = Field(None, ge=3, le=60)
    equipment: Optional[List[str]] = None
    injuries: Optional[List[str]] = None
    # Observaciones del coach sobre el ENTRENAMIENTO: van con la maquinaria y las lesiones
    # porque es lo que se actualiza al leer el reporte (Jesus 05-08, punto 2.5: "el
    # entrenamiento lo llevo aparte").
    training_notes: Optional[str] = None
    training_days: Optional[int] = None
    # LA EXCEPCION de este cliente (punto 39 del doc del 07-08). Texto libre a proposito:
    # hay 17 clientes con una excepcion apuntada a mano en una hoja y no se parecen entre
    # si -- uno cuya membresia paga su marido, uno que paga en efectivo, uno al que no se
    # le genera rutina, uno que no paga nada y aun asi se le hace, uno con ciclo de 4
    # semanas, otro al que se le manda el reporte por WhatsApp. Modelarlas con casillas
    # seria inventarse las categorias antes de conocerlas, y la de la numero 18 no
    # entraria. Cadena vacia = quitar la excepcion (por eso este campo se trata aparte en
    # el PUT, que descarta los None pero no los vacios).
    excepcion: Optional[str] = None
    # El contrato de este cliente (punto 44): duración del ciclo, desde qué semana le toca
    # reporte y, si hace falta, su propio calendario. Vacíos = lo que diga su plan.
    ciclo_semanas: Optional[int] = None
    semana_de_entrada: Optional[int] = None
    calendario_reportes: Optional[Dict[str, Any]] = None

    @field_validator("macros_training", "macros_rest", "macros_periworkout")
    @classmethod
    def _macros_en_rango(cls, v):
        return validar_dict_macros(v)

    @field_validator("injuries", "equipment", mode="before")
    @classmethod
    def _texto_suelto_es_una_lista(cls, v):
        return lista_desde_texto(v)

# Asignación de coach (trainer_id=None quita el coach)
class TrainerAssign(BaseModel):
    trainer_id: Optional[str] = None

# Onboarding guiado (tour de producto)
class OnboardingUpdate(BaseModel):
    step: Optional[str] = None          # id del paso actual donde quedó
    completed: Optional[bool] = None    # tour finalizado/omitido
    checklist_dismissed: Optional[bool] = None  # checklist "Primeros pasos" cerrado/completado

# Preguntas 5-8 del Nivel 0 ("Afina tus macros"): las que mueven el motor v2.
# Se guardan SIEMPRE (quiz_respuestas + perfil), se apliquen o no.
class AjustesMacros(BaseModel):
    # sedentario (muy sedentario) | normal (ligeramente activo) | moderado | muy_activo.
    # CUATRO desde el documento de textos del 06-08; los dos primeros valores se conservan
    # tal cual para no romper lo que ya contestaron los clientes de antes. Solo `muy_activo`
    # sube hidratos: los otros tres no tocan nada (doc del 07-08).
    actividad_diaria: Optional[str] = None
    deporte_extra: Optional[bool] = None
    # Las dos preguntas de seguimiento del deporte (pantalla 6 del doc de textos). No mueven
    # macros: le dicen al entrenador que hace, cuando y si puede cuadrarlo con el descanso.
    deporte_cual: Optional[str] = None
    deporte_en_descanso: Optional[Union[bool, str]] = None   # True | False | "ya"
    facilidad_engordar: Optional[str] = None    # enseguida | normal | casi_no
    apetito: Optional[str] = None               # mucho | normal | poco (pantalla 7, no mueve macros)
    cuesta_definir: Optional[str] = None        # mucho | normal | poco (se guarda, no modifica)
    # Se pregunta en el test de entrada desde el doc de textos (pantalla 3): antes vivia en
    # el cuestionario largo, que solo ven los planes con entrenador.
    training_experience: Optional[str] = None   # cero | principiante | intermedio | avanzado
    # P6. Tres respuestas, no dos: True (la sigue y la mide), False (come lo que surge) y
    # "parecido" (come siempre parecido pero no lo tiene medido), que es el caso más común
    # y el que faltaba. El "parecido" cuenta como que trae dieta -- se le pide un día tipo
    # y se lee igual -- pero queda registrado que no venía medido.
    sigue_dieta: Optional[Union[bool, str]] = None
    tiempo_dieta: Optional[str] = None          # P7: menos_1m | 1_3m | 3_6m | mas_6m (se guarda)
    # P8: decide que se hace con la dieta que trae (paso 4 del metodo). Definicion:
    # bien | lento | mantengo | cogiendo_peso. Volumen: bien | lento | mucha_grasa |
    # mantengo | bajando.
    como_va: Optional[str] = None
    # P9: no cambia el macro de arranque, marca el ritmo de los ajustes siguientes.
    # Definicion: mucho | normal | aguanto_mas. Volumen: no_puedo_mas | puedo_mas.
    hambre_saturacion: Optional[str] = None
    dieta_texto: Optional[str] = None           # P10: texto libre, se guarda tal cual
    dieta_hc_entreno: Optional[float] = None    # P10: HC totales del dia de entreno que come ahora
    dieta_grasa_entreno: Optional[float] = None # P10: grasa aproximada (opcional)
    dieta_confirmada: Optional[bool] = None     # P10: sin confirmar, la dieta NO se aplica
    historial_dietas: Optional[str] = None      # +-10%: guardar, NO aplicar (spec)
    # El biotipo y la altura se preguntan aqui desde el 06-08-2026: estaban en el perfil
    # largo, que solo ven los planes con coach, asi que el de 297 EUR no los daba nunca.
    # NO mueven macros -- el biotipo es una hipotesis de partida que el coach corrige
    # viendo como responde -- pero sin ellos no hay ni ficha ni caso parecido, y sin
    # altura no hay indice de muscularidad.
    biotype: Optional[str] = None
    height: Optional[float] = Field(default=None, ge=120, le=230)

# Cuestionario inicial (ELM) - Nivel 0
class QuestionnaireSubmit(BaseModel):
    # LA PASADA DE «NOS FALTAN COSAS TUYAS» (bloque 6 del doc del 18-08). El alta no se
    # repite, pero al que ya estaba dentro hay que poder preguntarle lo que nunca se le
    # pregunto. Con esto puesto, el endpoint acepta la segunda pasada y solo rellena huecos.
    completar: bool = False
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    goal: str  # "volumen" | "definicion"
    sex: Optional[str] = None  # "hombre" | "mujer"
    training_experience: Optional[str] = None  # cero | principiante | intermedio | avanzado
    birthdate: Optional[str] = None  # YYYY-MM-DD
    # CON RANGO, y por lo que costo verlo (18-08): sin el, una altura de 80 se GUARDABA en la
    # ficha y el error saltaba despues, al devolver el perfil ya escrito -- ese si valida --,
    # asi que el cliente veia «Revisa el campo height» con el dato malo ya dentro. Los topes
    # son los mismos que los del perfil, que es el sitio donde acaba el numero.
    height: Optional[float] = Field(default=None, ge=120, le=230)   # cm
    weight: float = Field(..., ge=25, le=300)                        # kg
    activity_level: Optional[str] = None  # sedentario | ligero | moderado | activo
    biotype: Optional[str] = None
    body_fat: float = Field(..., ge=3, le=70)                        # %
    ajustes: Optional[AjustesMacros] = None  # preguntas 5-8 del quiz nuevo

    # LO QUE TRAE EL BASICO DEL DOC DEL 18-08. Lo contesta TODO EL MUNDO, no solo quien
    # lleva entrenador, y por eso vive en el perfil y no dentro de `nivel1`: «a los que no
    # llevan plan personalizado no se les vuelve a preguntar nunca mas».
    profesion: Optional[str] = None
    como_me_conociste: Optional[str] = None
    # Las que come habitualmente, de la lista de diez del documento. Alimentan las
    # preferencias con las que se le monta el primer menu.
    proteinas_habituales: Optional[List[str]] = None
    # Su recorrido de peso, cada hito con su año: el techo, su mejor forma y lo más abajo
    # que ha estado. Sin el año no se puede calcular nada con ellos, que es justo lo que
    # pasaba cuando venían como «unos 95 hace tres años».
    peso_maximo: Optional[float] = None
    peso_maximo_ano: Optional[int] = None
    peso_maximo_nota: Optional[str] = None
    peso_mejor_momento: Optional[float] = None
    peso_mejor_momento_ano: Optional[int] = None
    peso_mejor_momento_nota: Optional[str] = None
    foto_mejor_momento: Optional[str] = None
    peso_minimo: Optional[float] = None
    peso_minimo_ano: Optional[int] = None
    peso_minimo_nota: Optional[str] = None
    # Alergias e intolerancias, con el detalle de las dos que tienen seguimiento.
    alergias: Optional[List[str]] = None
    lactosa: Optional[str] = None
    gluten: Optional[str] = None
    alergia_otra: Optional[str] = None
    dietas_previas: Optional[str] = None
    tiempo_intentandolo: Optional[str] = None
    motivo_apuntarse: Optional[str] = None
    # SI YA LE HA PAGADO A ALGUIEN, y qué tal le fue (corrección del punto 42, doc del
    # 19-08). No es lo mismo que `training_experience`: una dice cuántos años lleva
    # levantando peso, esta si ya ha estado en manos de otro y cómo acabó. Va en el
    # básico, para todos.
    #
    # `entrenador_anterior` viene del cuestionario largo de antes, donde era un texto
    # libre («quién, cuánto tiempo y por qué lo dejaste»). Ahora es «si» / «no» y el relato
    # va aparte; lo que ya está guardado como texto se queda como está y no se le vuelve a
    # preguntar a nadie que lo tenga.
    entrenador_anterior: Optional[str] = None
    entrenador_anterior_que_tal: Optional[str] = None

# Cuestionario Nivel 1 (solo planes con coach: calculadora == 'personalizado').
# Alimenta perfil, caso gemelo y estrategia; NO toca los macros.
class Nivel1Submit(BaseModel):
    biotype: Optional[str] = None
    height: Optional[float] = None              # cm
    birthdate: Optional[str] = None             # YYYY-MM-DD
    training_experience: Optional[str] = None
    peso_maximo: Optional[float] = None
    peso_minimo: Optional[float] = None
    peso_habitual: Optional[float] = None
    peso_mejor_momento: Optional[float] = None
    salud: Optional[Dict[str, Any]] = None      # {sueno, estres, medicacion, hormonal, lesiones}
    dietas_previas: Optional[str] = None
    entrenador_anterior: Optional[str] = None
    dias_entreno: Optional[int] = None
    hora_entreno: Optional[str] = None
    material: Optional[List[str]] = None
    cardio: Optional[str] = None
    alimentos_evitados: Optional[List[str]] = None
    # TEXTO O LISTA. En el cuestionario largo era un texto libre («frutos secos, marisco»);
    # desde el básico del 18-08 es un multiselect y llega una lista. Con el tipo antiguo, el
    # cliente que pasaba por el básico y luego hacía el completo recibía un 422 al enviarlo
    # -- «Error al guardar el perfil» -- y perdía las veinte respuestas de golpe.
    alergias: Optional[Union[str, List[str]]] = None
    num_comidas: Optional[int] = None
    # Bloque 4 del doc del 29-07. Ninguna toca los macros: son las que permiten emparejar al
    # cliente con los que ya han pasado por aqui.
    trt: Optional[str] = None                   # P14: si | no | antes  (la regla, pendiente de Jesus)
    zona_grasa: Optional[str] = None            # P15: abdomen | cintura | espalda_baja | pecho | piernas | reparto
    peso_maximo_cuando: Optional[str] = None    # P18
    foto_peso_maximo: Optional[str] = None      # P19 (opcional)
    mejor_definicion_cuando: Optional[str] = None   # P20; "nunca" si nunca estuvo definido
    hasta_donde: Optional[str] = None           # P21
    vario_peso_3m: Optional[str] = None         # P22
    tiempo_intentandolo: Optional[str] = None   # P23
    dieta_que_funciona: Optional[str] = None    # P24
    por_que_fallaron: Optional[str] = None      # P25
    motivo_apuntarse: Optional[str] = None      # P26

    # Bloque 3 del documento del 06-08-2026. Lo que hace falta para montarle la rutina, y
    # que faltaba: entrenar AHORA no es lo mismo que llevar años (se puede llevar diez y
    # estar parado desde marzo), y lo que NO tiene pesa tanto como lo que tiene -- una
    # rutina con jaula de sentadilla no vale si en su gimnasio no hay.
    entrena_ahora: Optional[str] = None             # si | irregular | no
    maquinas_que_faltan: Optional[str] = None
    ejercicios_imposibles: Optional[str] = None

    # Bloque 5: su suplementacion. No existia, y sin esto se le pauta a ciegas: repitiendole
    # algo que ya toma o chocando con lo que lleva.
    suplementos_ahora: Optional[str] = None
    suplementos_antes: Optional[str] = None         # ya no se pregunta (bloque 5 del 18-08)
    # Pantalla 14 del completo: lo que NO puede o NO quiere tomar. Es la unica de las dos que
    # cambia lo que se le manda.
    suplementos_veto: Optional[str] = None
    # libertad | abierto | lo_justo | no  (las fichas viejas traen `si`)
    quiere_pauta_suplementos: Optional[str] = None

    # Bloque 4: la intencion cuenta tanto como el uso. Hay que saberlo ANTES, no cuando ya
    # lo ha hecho.
    # no | pasado | frecuente | quemagrasas | ciclo  (viejos: uso | use | intencion | nunca)
    farmacologia_uso: Optional[str] = None
    farmacologia_detalle: Optional[str] = None

    # ── El completo del 18-08 · lo que faltaba ────────────────────────────────────────
    # Las pantallas 6 y 7 estaban en el cuestionario de siempre y desaparecieron por el
    # camino: hoy se le monta una rutina y una dieta sin saber si tiene una patologia que se
    # lo desaconseje o si esta medicado.
    patologia: Optional[str] = None                 # si | no
    patologia_detalle: Optional[str] = None
    medicacion: Optional[str] = None                # si | no
    medicacion_detalle: Optional[str] = None
    # Pantallas 10 y 11: el descanso, con los tramos de Jesus. Antes era un campo suelto
    # dentro de una pantalla de cinco, con tres respuestas de andar por casa.
    horas_sueno: Optional[str] = None               # min_7_30 | 6_7_30 | 5_6 | menos_5
    ayuda_dormir: Optional[str] = None
    # Pantalla 22: la lesion y sus tres detalles. Lo que va a `injuries`, que es de donde
    # lee el generador de rutinas.
    lesion: Optional[str] = None                    # si | no
    lesion_cual: Optional[str] = None
    lesion_tiempo: Optional[str] = None

    # Bloque 6: su comida. Lo que decide si los menus le encajan en la vida o los abandona
    # en tres dias. Las 36 categorias y el momento del dia van aparte, en las preferencias.
    cocina_o_rapido: Optional[str] = None           # cocinar | normal | rapido
    conserva_o_fresco: Optional[str] = None         # conserva | ambos | fresco
    come_fuera: Optional[str] = None                # no | 1_2 | 3_4 | casi_todos
    que_le_apetece: Optional[str] = None
    favoritos_y_no_gustos: Optional[str] = None
    plato_imprescindible: Optional[str] = None
    # Las intolerancias, ESTRUCTURADAS y no en texto libre: de "soy intolerante a la
    # lactosa" no se puede sacar si puede comer yogur o queso curado, y de eso depende
    # media lista de la compra. Lo mismo con celiaquia contra sensibilidad.
    lactosa: Optional[str] = None                   # bien | tolera_algo | nada
    gluten: Optional[str] = None                    # bien | sensibilidad | celiaquia

# Macros Models
class MacrosData(BaseModel):
    protein: float = Field(ge=0, le=MACRO_MAX_GRAMOS)
    carbs: float = Field(ge=0, le=MACRO_MAX_GRAMOS)
    fat: float = Field(ge=0, le=MACRO_MAX_GRAMOS)
    calories: Optional[float] = Field(default=None, ge=0, le=MACRO_MAX_CALORIAS)

class PeriMacrosData(BaseModel):
    protein: float = Field(ge=0, le=MACRO_MAX_GRAMOS)
    carbs: float = Field(ge=0, le=MACRO_MAX_GRAMOS)

class MacrosUpdate(BaseModel):
    training: MacrosData
    rest: MacrosData
    peri: Optional[PeriMacrosData] = None
    note: Optional[str] = None
    # Date-versioned macros (Calma todosLosMacros): these macros apply to diet days on/after
    # this date. Default = today. Diets before it keep the prior version.
    effective_date: Optional[str] = None
    # Calc inputs stored per change for traceability (history of how the macros were derived).
    peso: Optional[float] = Field(default=None, ge=25, le=300)
    # LA FECHA DEL PESO, que NO es la del ajuste (punto 27 del 07-08). El coach ajusta hoy
    # leyendo un reporte de hace una semana: si ese peso se archiva con la fecha del ajuste,
    # la curva de peso queda corrida y el modelo aprende de un historico falso. Aqui viaja la
    # fecha del pesaje (la del reporte). Si no viene, se usa la del ajuste, como antes.
    peso_fecha: Optional[str] = None
    porcentaje_graso: Optional[float] = Field(default=None, ge=3, le=60)
    sexo: Optional[str] = None
    objetivo: Optional[str] = None
    # Motor v2: preguntas 5-8 y desglose del calculo que origino estos macros
    # (se versionan en macro_history.motor; la revision se recalcula en servidor).
    ajustes: Optional[AjustesMacros] = None
    desglose: Optional[List[Dict[str, Any]]] = None
    # Modelo predictivo (paso 1): el POR QUE del ajuste, interno del coach. Es
    # distinto de `note`, que es el feedback que le llega al cliente.
    criterio: Optional[str] = None
    # Si este ajuste sale de una sugerencia de la IA: su id. Sirve para medir cuanto
    # la corrigio el coach (la senal de aprendizaje mas valiosa que hay).
    sugerencia_id: Optional[str] = None


class MacroEvaluacion(BaseModel):
    """Modelo predictivo (paso 1): como salio la fase que abrio un ajuste. Se
    rellena a toro pasado, cuando llega el reporte siguiente."""
    resultado: str            # buena | mala
    causa: Optional[str] = None   # ajuste (fallo del coach) | cliente (no cumplio) | otro
    nota: Optional[str] = None

    @field_validator("resultado")
    @classmethod
    def _resultado_valido(cls, v):
        if v not in ("buena", "mala"):
            raise ValueError("resultado debe ser 'buena' o 'mala'")
        return v

    @field_validator("causa")
    @classmethod
    def _causa_valida(cls, v):
        if v is not None and v not in ("ajuste", "cliente", "otro"):
            raise ValueError("causa debe ser 'ajuste', 'cliente' u 'otro'")
        return v
