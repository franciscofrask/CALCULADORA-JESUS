"""
El semaforo de la lista de clientes (punto 32 del doc del 07-08).

Lo que habia era una etiqueta EN RIESGO binaria: activo + semana >= 3 + sin reporte en 14
dias. Saltaba para 140 de 184 activos, el 76%. Una alerta que dispara para tres de cada
cuatro deja de mirarse en una semana, y ademas no dice NADA: ni si va regular o mal, ni en
que. Un cliente que lleva 15 dias sin reporte pero al que hablaste ayer y le ajustaste la
semana pasada no esta en el mismo sitio que uno al que nadie toca desde marzo.

Aqui hay CINCO estados y se aplican POR CELDA, no por fila:

    ok            va bien, no hay que hacer nada
    regular       se le pasa el plazo, todavia sin drama
    regular_malo  ya hay que mirarlo esta semana
    malo          esto no puede seguir asi
    info          no aplica o no se sabe (su plan no lleva eso, o no hay dato)

`info` no es un estado peor ni mejor: es "esta casilla no cuenta para este cliente". Al de
autogestion no se le acompana por chat, asi que pintarle el contacto en rojo todos los dias
seria ruido, no una alerta.

LOS PLAZOS SALEN DEL PLAN, no son numeros generales. Es lo que ya estaba escrito para la
columna de contacto y vale igual para todo: "al de 1.500 con llamada semanal, quince dias
es un escandalo; al de 897 con reporte quincenal, no tanto". Asi que cada celda se mide
contra la cadencia de SU plan (7, 14 o 28 dias) y no contra un 14 fijo para todos.

Los multiplicadores (1x, 1,5x, 2x) son una primera propuesta: hacen falta unos numeros para
poder ensenarlo, pero los tiene que repasar Jesus. Estan aqui arriba, juntos y con nombre,
para que cambiarlos sea una linea.
"""
from typing import Any, Dict, Optional

OK = "ok"
REGULAR = "regular"
REGULAR_MALO = "regular_malo"
MALO = "malo"
INFO = "info"

# Cuantas veces el plazo de su plan hay que pasarse para cada escalon.
DENTRO_DE_PLAZO = 1.0      # hasta aqui, ok
UN_POCO_TARDE = 1.5        # hasta aqui, regular
BASTANTE_TARDE = 2.0       # hasta aqui, regular-malo; a partir de ahi, malo


def celda(valor: Any, estado: str, texto: Optional[str] = None,
          detalle: Optional[str] = None) -> Dict[str, Any]:
    """Una celda: el valor, su estado y como se escribe. La tabla solo pinta.

    Se devuelve un OBJETO y no "valor|color" en una cadena a proposito: en cuanto haya que
    ordenar por la columna, filtrar por estado o ensenar el detalle en un tooltip, la
    cadena hay que romperla otra vez, y quien la rompe se equivoca.
    """
    return {"valor": valor, "estado": estado, "texto": texto, "detalle": detalle}


def por_plazo(dias: Optional[int], plazo: Optional[int], *, nunca: bool = False,
              texto_nunca: str = "nunca") -> Dict[str, Any]:
    """Estado de una celda de "cuanto lleva sin...", medido contra el plazo de su plan.

    OJO CON EL "NUNCA". Que algo no haya pasado nunca NO es malo por si solo: al cliente que
    entro el lunes todavia no le toca mandar su primer reporte. Marcarlo en rojo es
    exactamente el fallo de la etiqueta vieja, que saltaba para tres de cada cuatro.

    Asi que cuando no ha pasado nunca, `dias` tiene que venir contado DESDE QUE EMPEZO, y el
    estado sale de ahi igual que en los demas. Lo unico que cambia es el texto, que dice
    "nunca" en vez de los dias: la diferencia entre "hace 40 dias que no manda" y "lleva 40
    dias y no ha mandado ninguno" importa para leerlo, no para el color.
    """
    if dias is None:
        return celda(None, INFO, "-", "no hay dato")
    if not plazo:
        return celda(dias, INFO, f"{dias} d")
    if dias <= plazo * DENTRO_DE_PLAZO:
        estado = OK
    elif dias <= plazo * UN_POCO_TARDE:
        estado = REGULAR
    elif dias <= plazo * BASTANTE_TARDE:
        estado = REGULAR_MALO
    else:
        estado = MALO
    if nunca:
        return celda(dias, estado, texto_nunca, f"lleva {dias} días y no ha pasado ni una vez")
    return celda(dias, estado, f"{dias} d", f"su plazo son {plazo} días")


def no_aplica(motivo: str) -> Dict[str, Any]:
    """La casilla no cuenta para este cliente (su plan no lo incluye)."""
    return celda(None, INFO, "-", motivo)


# Los estados que cuentan como "hay que mirar esto". `info` no cuenta, que es justo lo que
# hacia inservible a la etiqueta vieja.
ATENCION = (REGULAR_MALO, MALO)


def peor(*estados: str) -> str:
    """El peor estado de una fila. Sirve para ordenar la lista por quien esta peor."""
    orden = {OK: 0, REGULAR: 1, REGULAR_MALO: 2, MALO: 3, INFO: -1}
    return max((e for e in estados if e), key=lambda e: orden.get(e, -1), default=INFO)
