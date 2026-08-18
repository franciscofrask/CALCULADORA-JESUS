"""
¿Los macros de este cliente los puso ALGUIEN, o salieron del calculo del alta?

Punto 4.1 de la revision del 09-08. La app usaba `ajuste_macros_completado` para decidir si
los macros de alguien son "provisionales", y esa bandera solo dice una cosa: si paso por
NUESTRO cuestionario de ajuste. No dice nada de si tiene unos macros buenos.

Medido en produccion el 09-08-2026, sobre 174 clientes activos:

    reciben "Tus macros son provisionales" ..................... 174
    ven "Completa tu cuestionario inicial" en su Inicio ........ 169
    de esos, con macros escritos por una persona .............. 171
    de esos, con tres semanas o mas en el programa ............ 164

Es decir: casi todos. Los 160 que vinieron de Calma nunca hicieron nuestro cuestionario -- ya
tenian macros, se los puso Jesus -- y la app les decia cada vez que abrian que sus numeros
eran provisionales y que se los terminaran ellos. Justo lo contrario de lo que vende un plan
con entrenador.

La pregunta buena no es "¿hizo el cuestionario?" sino "¿hay alguien detras de estos numeros?".
Y eso se responde mirando de donde salio su ultimo apunte del historial.
"""
from typing import Any, Dict, Optional

# Los origenes que NO son una persona: los calcula la app a partir de lo que contesto.
# Todo lo demas -- el coach, el equipo, la migracion de Calma, la IA revisada -- es alguien
# decidiendo, y entonces sus macros ya no son provisionales.
CALCULADOS_POR_LA_APP = ("", "quiz_alta", "quiz_ajuste")


def de_una_persona(ultimo_apunte: Optional[Dict[str, Any]]) -> bool:
    """True si el ultimo apunte del historial lo escribio alguien y no el calculo del alta.

    `ultimo_apunte` es el documento mas reciente de `macro_history` del cliente; basta con
    que traiga `origen` y `changed_by`.

    Los apuntes viejos no tienen `origen` (se empezo a guardar el 05-08), pero si tienen
    `changed_by` cuando los escribio una persona, asi que ahi se mira eso.

    MANDA EL ORIGEN CUANDO EXISTE (18-08). Esto estaba escrito con un `or`:

        origen not in CALCULADOS_POR_LA_APP or bool(changed_by)

    y el apunte del alta lleva las dos cosas -- `origen: quiz_alta` y `changed_by` con el
    NOMBRE DEL PROPIO CLIENTE, que es quien lo ha rellenado --, asi que contaba como "se los
    puso una persona". Consecuencia: todo cliente de plan con entrenador se quedaba
    ATRAPADO al terminar el alta. Su ultima pantalla es «Calcular mis macros»; el
    cuestionario se guardaba, y la llamada siguiente recibia un 403 con «tus macros los
    llevamos nosotros». Volver a pulsar daba 409, «el cuestionario ya fue completado». Sin
    macros que ver y sin forma de seguir.

    El `changed_by` solo decide cuando no hay origen, que es para lo que se puso.
    """
    if not ultimo_apunte:
        return False
    origen = ultimo_apunte.get("origen") or ""
    if origen:
        return origen not in CALCULADOS_POR_LA_APP
    return bool(ultimo_apunte.get("changed_by"))
