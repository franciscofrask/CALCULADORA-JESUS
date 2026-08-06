"""
El quiz de venta (documento del test de nivel, 06-08-2026).

Seis preguntas antes de comprar. Ve su resultado SIN dar el correo -- eso es una
decision cerrada -- y despues se le ofrece guardarlo o recibirlo por email.

QUE DECIDE EL NIVEL
El test no clasifica personas: coloca producto. Y lo que coloca el producto es UNA
pregunta, la de las seis frases: con cual se identifica. Las demas acompañan.

  Estoy en forma pero harto del proceso   -> Nivel 1  (no le falta direccion, le falta libertad)
  Voy bien, quiero dar un salto           -> Nivel 1  (sabe hacerlo; necesita afinar, no que le lleven)
  Hago las cosas bien y no veo resultados  -> Nivel 2  (le falta que alguien mire sus numeros)
  Lo consigo y vuelvo atras                -> Nivel 2  (le falta sostenerlo, y eso se sostiene con revision)
  Nunca he estado en forma                 -> Nivel 2  (le falta guia desde el principio)
  Se lo que tendria que hacer y no lo hago -> Nivel 3  (el unico al que no le falta metodo:
                                                        le falta que alguien este encima)

Y despues, COMO MUCHO UNA SUBIDA, por lo que llegue antes:
  - fecha concreta                    sube uno
  - mas de cinco años / toda la vida  sube uno

Una, no dos. Si se acumulan, el que parte de cero con fecha y diez años acaba en Nivel
3 sin haber entrenado nunca, y esa venta se cae en la llamada.

LO QUE HABIA ANTES
Cuatro preguntas y siete combinaciones; el resto caia en Nivel 2. La pregunta del
tiempo se guardaba y no movia el nivel (se leia `r4` y no aparecia en ninguna regla), y
ninguna de las cuatro preguntaba por el acompañamiento, que es justo lo que separa los
tres niveles. De ahi la reescritura.

Las cuatro viejas se siguen preguntando y guardando: dicen cosas del cliente que sirven
luego, aunque ya no decidan el nivel por si solas.
"""
from typing import Any, Dict, List, Optional

# Con quien se identifica (P5) es lo que decide. Sin esa respuesta no hay decision, y el
# intermedio es lo unico honesto: recomendar el 3 seria ponerle 1.500 EUR delante a
# alguien que igual solo necesita que la dieta le encaje.
NIVEL_POR_DEFECTO = 2

# Las seis frases. Son los cuatro avatares de Jesus, mas el grupo del 23 % que faltaba en
# su documento (el que contesto "si, era consciente de que haciendo las cosas asi no podia
# esperar mejorar mucho mas": 21 de 92 clientes) y una sexta para el 27 % que decia que su
# esfuerzo y su resultado iban en sintonia, gente que no viene con dolor.
#
# Dos cuidados suyos al escribirlas:
#   - La de la constancia tiene que sonar a CONSTATACION, no a confesion. Escrita como
#     "me falta constancia" no la marca nadie, y es una de cada cuatro personas.
#   - El orden NO es de gravedad, a proposito: de mejor a peor la gente se para en la
#     primera que le suena un poco y no busca la suya.
FRASES: List[Dict[str, Any]] = [
    {"id": "A", "texto": "Estoy en forma, pero estoy harto del proceso. Así no puedo seguir", "nivel": 1},
    {"id": "B", "texto": "Sé perfectamente lo que tendría que hacer. Lo que no hago es hacerlo", "nivel": 3},
    {"id": "C", "texto": "Hago las cosas bien y no veo los resultados que debería", "nivel": 2},
    {"id": "D", "texto": "Voy bien, pero quiero dar un salto y no sé cómo darlo", "nivel": 1},
    {"id": "E", "texto": "Nunca he estado en forma y no sé ni por dónde se empieza", "nivel": 2},
    {"id": "F", "texto": "Lo he conseguido alguna vez, pero siempre acabo volviendo atrás", "nivel": 2},
]

# Por que sale ese nivel: es lo que se le enseña para que la recomendacion no parezca
# sacada de un sombrero.
#
# PENDIENTE DE JESUS. Su documento deja abiertos justo estos seis textos ("te los escribo
# yo con el mismo criterio del documento 18 y me los confirmas"). Los de aqui salen de la
# columna "Por que" de su propia tabla, que es lo mas fiel que hay hasta que los mande.
# Cuando lleguen se sustituyen aqui, y solo aqui.
PORQUE = {
    "A": "No te falta dirección: te falta libertad. Con la calculadora y los menús te lo "
         "montas tú, sin comer siempre lo mismo ni pedirle permiso a nadie.",
    "B": "No te falta método, lo sabes de sobra. Te falta que alguien esté encima, y para "
         "eso hace falta una persona, no otra app.",
    "C": "Si haces las cosas bien y no ves lo que deberías, no es cuestión de esfuerzo: "
         "hay algo en tus números que no cuadra y alguien tiene que mirarlo.",
    "D": "Sabes hacerlo. Lo que necesitas es afinar, no que te lleven de la mano.",
    "E": "Empezar de cero solo, con lo que hay por ahí, es la forma más rápida de acabar "
         "dejándolo. Te hace falta guía desde el principio.",
    "F": "Llegar ya has llegado. Lo que falla es sostenerlo, y eso se sostiene con alguien "
         "revisando cómo vas.",
}

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
        # Esta ya SI decide: C y D suben un nivel. Es la que le hace decir en voz alta
        # "llevo toda la vida con esto" justo antes de ver el precio.
        "id": 4,
        "texto": "¿Cuánto tiempo llevas intentándolo?",
        "opciones": [
            {"id": "A", "texto": "Menos de un año"},
            {"id": "B", "texto": "De 1 a 5 años"},
            {"id": "C", "texto": "Más de 5 años"},
            {"id": "D", "texto": "Toda la vida"},
        ],
    },
    {
        # La que coloca el producto. Solo se marca UNA: en el test cada pantalla de mas
        # cuesta gente, y lo de "marca todas y luego dime cual es LA tuya" va en el alta,
        # donde ya ha pagado.
        "id": 5,
        "texto": "¿Con cuál de estas te identificas más?",
        "opciones": [{"id": f["id"], "texto": f["texto"]} for f in FRASES],
    },
    {
        "id": 6,
        "texto": "¿Tienes una fecha?",
        "opciones": [
            {"id": "A", "texto": "Sí, tengo una fecha concreta en mente"},
            {"id": "B", "texto": "Más o menos, pero sin fecha fija"},
            {"id": "C", "texto": "No, cuando llegue"},
        ],
    },
]

_TIEMPO_LARGO = ("C", "D")      # mas de 5 años / toda la vida
_HAY_FECHA = ("A",)             # fecha concreta

_NIVEL_POR_FRASE = {f["id"]: f["nivel"] for f in FRASES}


def _r(respuestas: Dict[int, str], n: int) -> Optional[str]:
    """La respuesta a la pregunta n, en mayuscula. Tolera claves int y str."""
    v = respuestas.get(n, respuestas.get(str(n)))
    return (v or "").strip().upper() or None


def recomendar(respuestas: Dict[int, str]) -> Dict[str, Any]:
    """Devuelve el nivel recomendado y por que, sin pedir nada a cambio."""
    frase = _r(respuestas, 5)
    r4, r6 = _r(respuestas, 4), _r(respuestas, 6)

    base = _NIVEL_POR_FRASE.get(frase)
    if base is None:
        return {
            "nivel": NIVEL_POR_DEFECTO,
            "por_que": ("Por lo que cuentas, lo que más te va a servir es tener a alguien "
                        "revisando tus números y tu entrenamiento cada dos semanas."),
            "subida": None,
        }

    porque = PORQUE.get(frase, "")

    # UNA subida como mucho, la que llegue antes. La fecha va primero porque es la que
    # aprieta: quien tiene un día señalado no tiene tiempo de probar solo.
    subida = None
    if r6 in _HAY_FECHA:
        subida = "fecha"
    elif r4 in _TIEMPO_LARGO:
        subida = "tiempo"

    nivel = base
    if subida and base < 3:
        nivel = base + 1
        porque += (" Y como tienes una fecha, no vale con ir haciendo: toca apretar, y para "
                   "apretar hace falta alguien detrás."
                   if subida == "fecha" else
                   " Y llevas demasiado tiempo intentándolo como para volver a intentarlo "
                   "igual que las otras veces.")

    return {"nivel": nivel, "por_que": porque, "subida": subida}


def resultado_completo(respuestas: Dict[int, str],
                       catalogo: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """El resultado tal como se le enseña: el recomendado, y los otros dos debajo.

    "Nivel recomendado con sus propias palabras, los otros dos visibles debajo, y puede
    elegir otro." La recomendacion orienta; no esconde las alternativas.

    Y el Nivel 3 se PROPONE, no se impone: como va a llamada, lo elige el con los otros
    dos precios delante. Quien pide la llamada habiendo visto los tres precios viene ya
    decidido.
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
            # El Nivel 3 se contrata por llamada, no con un boton.
            "por_llamada": n == 3,
        })

    return {
        "recomendado": code,
        "por_que": rec["por_que"],
        "subida": rec["subida"],
        "niveles": niveles,
        "respuestas": {str(k): v for k, v in respuestas.items()},
    }
