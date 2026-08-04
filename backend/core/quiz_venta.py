"""
El quiz de venta (especificacion 31-07-2026, partes 3 y 4).

Cuatro preguntas antes de comprar. Ve su resultado SIN dar el correo -- eso es una
decision cerrada del documento (parte 10) -- y despues se le ofrece guardarlo o
recibirlo por email.

Se le enseña el nivel recomendado con sus propias palabras, los otros dos debajo, y
puede elegir otro: la recomendacion orienta, no encierra.

Sobre la logica: la tabla del documento no cubre las 256 combinaciones posibles. Cuando
encajan VARIAS reglas se aplica lo que dice, "en caso de duda, se recomienda el nivel
mayor". Cuando no encaja NINGUNA se recomienda el 2, que es el intermedio; recomendar
el 3 a todo el que se sale de la tabla seria ponerle 1.500 EUR delante a alguien que
igual solo necesita que la dieta le encaje. Esto ultimo es una decision de desarrollo,
no del documento: si Jesus prefiere otra cosa, se cambia NIVEL_POR_DEFECTO.
"""
from typing import Any, Dict, List, Optional

NIVEL_POR_DEFECTO = 2

PREGUNTAS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "texto": "¿Entrenas ahora mismo?",
        "opciones": [
            {"id": "A", "texto": "Sí, voy al gimnasio de forma regular"},
            {"id": "B", "texto": "Voy, pero sin un plan claro o de vez en cuando"},
            {"id": "C", "texto": "Ahora no, pero he entrenado en serio antes"},
            {"id": "D", "texto": "No, y nunca he entrenado de forma seria"},
        ],
    },
    {
        "id": 2,
        "texto": "¿Has llegado alguna vez a verte como querías?",
        "opciones": [
            {"id": "A", "texto": "No, nunca"},
            {"id": "B", "texto": "Llegué a verme bien, pero no supe mantenerlo"},
            {"id": "C", "texto": "Sí, y quiero recuperar aquello"},
            {"id": "D", "texto": "Estoy bien ahora, quiero afinar más"},
        ],
    },
    {
        "id": 3,
        "texto": "Cuando has intentado cuidarte, ¿qué es lo que más te ha costado?",
        "opciones": [
            {"id": "A", "texto": "No saber si lo estaba haciendo bien"},
            {"id": "B", "texto": "Que la dieta no encajaba con mi vida"},
            {"id": "C", "texto": "Empezar. Sé lo que hay que hacer, pero no arranco"},
            {"id": "D", "texto": "Mantenerlo más de unas semanas"},
        ],
    },
    {
        "id": 4,
        "texto": "¿Cuánto tiempo llevas intentándolo?",
        "opciones": [
            {"id": "A", "texto": "Menos de un año"},
            {"id": "B", "texto": "De 1 a 5 años"},
            {"id": "C", "texto": "Más de 5 años"},
            {"id": "D", "texto": "Toda la vida"},
        ],
    },
]


def _r(respuestas: Dict[int, str], n: int) -> Optional[str]:
    """La respuesta a la pregunta n, en mayuscula. Tolera claves int y str."""
    v = respuestas.get(n, respuestas.get(str(n)))
    return (v or "").strip().upper() or None


# La tabla del documento. Cada regla: (condicion, nivel, por que).
# El "por que" no es decoracion: es lo que se le enseña para que la recomendacion no
# parezca sacada de un sombrero.
def _reglas(r1, r2, r3, r4):
    return [
        (r1 == "D", 3,
         "Nunca has entrenado en serio. Empezar de cero solo, con la información que hay "
         "por ahí, es la forma más rápida de acabar dejándolo."),
        (r1 == "B" and r2 == "A", 3,
         "Vas al gimnasio pero sin plan, y nunca has llegado a verte como querías. No es "
         "cuestión de esfuerzo: te falta que alguien ordene el trabajo."),
        (r3 == "C", 3,
         "Lo que te cuesta es arrancar, no saber qué hacer. Para eso hace falta alguien "
         "detrás, no otro PDF."),
        (r1 == "A" and r2 in ("A", "B") and r3 == "A", 2,
         "Entrenas de forma regular y lo que te falta es saber si vas bien. Con alguien "
         "revisando tus números cada dos semanas, eso se acaba."),
        (r1 == "C" and r2 == "B" and r3 == "D", 2,
         "Ya has estado ahí y sabes que puedes. Lo que falla es sostenerlo, y eso se "
         "arregla con seguimiento."),
        (r1 == "A" and r2 == "D" and r3 == "B", 1,
         "Entrenas, estás bien y solo quieres afinar. Con la calculadora y los menús "
         "tienes de sobra para hacerlo tú."),
        (r1 == "A" and r2 == "C" and r3 == "B", 1,
         "Sabes lo que haces y ya has llegado antes. Lo que necesitas es una herramienta "
         "que te cuadre la comida, no que te lleven de la mano."),
    ]


def recomendar(respuestas: Dict[int, str]) -> Dict[str, Any]:
    """Devuelve el nivel recomendado y por que, sin pedir nada a cambio."""
    r1, r2, r3, r4 = (_r(respuestas, n) for n in (1, 2, 3, 4))

    encajan = [(nivel, porque) for cond, nivel, porque in _reglas(r1, r2, r3, r4) if cond]

    if not encajan:
        return {
            "nivel": NIVEL_POR_DEFECTO,
            "por_que": ("Por lo que cuentas, lo que más te va a servir es tener a alguien "
                        "revisando tus números y tu entrenamiento cada dos semanas."),
            "reglas_aplicadas": 0,
        }

    # "En caso de duda, se recomienda el nivel mayor".
    mayor = max(n for n, _ in encajan)
    porque = next(p for n, p in encajan if n == mayor)
    return {"nivel": mayor, "por_que": porque, "reglas_aplicadas": len(encajan)}


def resultado_completo(respuestas: Dict[int, str],
                       catalogo: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """El resultado tal como se le enseña: el recomendado, y los otros dos debajo.

    "Nivel recomendado con sus propias palabras, los otros dos visibles debajo, y puede
    elegir otro." La recomendacion orienta; no esconde las alternativas.
    """
    rec = recomendar(respuestas)
    code = f"nivel{rec['nivel']}"

    niveles = []
    for n in (1, 2, 3):
        c = f"nivel{n}"
        info = catalogo.get(c) or {}
        niveles.append({
            "plan": c,
            "nombre": info.get("name") or f"Nivel {n}",
            "precio": info.get("precio"),
            "recomendado": c == code,
            # El Nivel 3 se contrata por llamada, no con un boton (parte 1).
            "por_llamada": n == 3,
        })

    return {
        "recomendado": code,
        "por_que": rec["por_que"],
        "niveles": niveles,
        "respuestas": {str(k): v for k, v in respuestas.items()},
    }
