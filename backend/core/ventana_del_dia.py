# -*- coding: utf-8 -*-
"""CUANDO SE PUEDE CERRAR EL DIA, Y CUANTOS LLEVA SIN CERRAR (doc «El día», 31-08).

Hasta hoy el cierre no tenia horario: se podia rellenar a cualquier hora y la linea del
Inicio salia siempre, diciendo lo mismo el primer dia que el decimo. El documento pone las
dos cosas, y la segunda -- la ventana de la mañana -- es lo que de verdad arregla los huecos.

UNA SOLA VENTANA, NO DOS COSAS. Es la frase del propio documento y es la clave para no
montar dos mecanismos: el cierre de un dia esta abierto DESDE SU HORA HASTA LAS 15:00 DEL
DIA SIGUIENTE. De ahi sale todo lo demas.

    17:00  se abre el cierre de hoy
           (a la mañana siguiente, hasta las 15:00, todavia se puede rellenar el de ayer)
    15:00  ayer se cierra · ya no vuelve
    17:00  se abre el de hoy

Entre las 15:00 y las 17:00 no hay NINGUN dia abierto, y eso es lo que impide que se
solapen dos. El tope de arriba se resuelve solo: pidiendo la hora a partir de las 17:00 ya
queda fuera la madrugada, sin tener que poner ningun limite.

POR QUE LA MAÑANA SIGUIENTE Y NO EL REPORTE. «Porque a los siete dias no se acuerda. Y lo
que conteste de memoria no arregla el dato: lo ensucia, porque entra como si fuera igual de
bueno que el que apunto esa noche.» Un dia de distancia si se recuerda; dos semanas, no.

LA HORA ES LA DE ESPAÑA, no la del reloj del cliente. Es la regla de la casa: el reloj del
cliente decide QUE DIA vive (`dia_del_cliente`); España decide plazos y ventanas.

Y LA RACHA SOLO CUENTA LOS DIAS QUE YA SE HAN PERDIDO. Si son las once de la mañana, el de
ayer todavia se puede rellenar, asi que no cuenta como perdido: contarlo seria reñirle por
algo que aun puede hacer.
"""
from datetime import date, datetime, timedelta
from typing import Iterable, Optional, Set

#: Nunca antes de las 17:00: «antes no tiene nada que cerrar, y verla apagada todo el dia la
#: convierte en parte del decorado». El cliente puede retrasarla (turnos de noche), no
#: adelantarla.
HORA_MINIMA = 17

#: A las 15:00 se cierra el de ayer. Ya no vuelve.
HORA_LIMITE_DE_AYER = 15


def hora_de_apertura(hora_elegida: Optional[int]) -> int:
    """La hora a la que se le enciende el cierre, con el minimo de las 17:00 aplicado."""
    try:
        h = int(hora_elegida)
    except (TypeError, ValueError):
        return HORA_MINIMA
    return h if HORA_MINIMA <= h <= 23 else HORA_MINIMA


def dia_abierto(ahora_es: datetime, dia_del_cliente: date,
                hora_elegida: Optional[int] = None) -> Optional[date]:
    """El dia que se puede cerrar AHORA MISMO, o None si no hay ninguno abierto.

    `ahora_es` es la hora de España; `dia_del_cliente`, el dia que el cliente dice estar
    viviendo (su reloj). Son dos cosas distintas a proposito.
    """
    apertura = hora_de_apertura(hora_elegida)
    if ahora_es.hour >= apertura:
        return dia_del_cliente
    if ahora_es.hour < HORA_LIMITE_DE_AYER:
        return dia_del_cliente - timedelta(days=1)
    return None


def cierra_a_las(ahora_es: datetime, dia_del_cliente: date,
                 hora_elegida: Optional[int] = None) -> Optional[int]:
    """A que hora deja de poder rellenarse lo que esta abierto ahora. Siempre las 15:00 del
    dia siguiente, que es donde acaba la ventana."""
    return None if dia_abierto(ahora_es, dia_del_cliente, hora_elegida) is None else HORA_LIMITE_DE_AYER


def dias_sin_cerrar(dias_con_cierre: Iterable[str], ahora_es: datetime,
                    dia_del_cliente: date, hora_elegida: Optional[int] = None) -> int:
    """Cuantos dias seguidos lleva SIN cerrar, contando solo los ya perdidos.

    Se cuenta hacia atras desde el ultimo dia que ya no se puede recuperar:

      - por la mañana (antes de las 15:00) ayer sigue abierto, asi que se empieza en
        anteayer;
      - a partir de las 15:00 ayer ya se perdio, asi que se empieza en ayer.

    Hoy nunca cuenta: no ha terminado.
    """
    hechos: Set[str] = {str(d)[:10] for d in dias_con_cierre if d}
    # El primer dia que ya no tiene arreglo.
    atras = 2 if ahora_es.hour < HORA_LIMITE_DE_AYER else 1
    cuenta = 0
    dia = dia_del_cliente - timedelta(days=atras)
    # Un tope por si acaso: nadie necesita saber que lleva 400 dias, y evita recorrer la
    # historia entera de un cliente que nunca ha cerrado uno.
    while cuenta < 60 and dia.isoformat() not in hechos:
        cuenta += 1
        dia -= timedelta(days=1)
    return cuenta


#: Los cuatro estados de la linea del Inicio, con sus textos tal cual los escribe el
#: documento. Se devuelven desde el servidor para que la pantalla solo tenga que pintar: la
#: escalada es una regla de producto, no una decision de maquetado.
def texto_de_la_linea(racha: int, es_de_ayer: bool) -> dict:
    """Que dice la fila de «¿Cómo fuiste hoy?» segun lo que lleve sin cerrar."""
    if es_de_ayer:
        return {"titulo": "Ayer no cerraste el día",
                "detalle": "Puedes hacerlo hasta las 3 de la tarde"}
    if racha >= 7:
        # «Tu frase, sin el "hasta que vuelvas": la linea NO desaparece.» Si se quitara, se
        # queda sin el unico sitio donde se le dice y no vuelve.
        return {"titulo": "Llevas una semana sin cerrar el día",
                "detalle": "Dejo de recordártelo. Si te está costando, dímelo y lo vemos"}
    if racha >= 4:
        # Aqui se le dice lo que se pierde, y es verdad: esos dias van en blanco en su
        # reporte. Sin riña, que dos dias antes se le estaba animando.
        return {"titulo": "Llevas 4 días sin cerrar",
                "detalle": "Retómalo hoy mismo: es de donde salen tus ajustes"}
    if racha >= 2:
        # «No lo dejes hoy también» es lo que hace el trabajo: le pide el de hoy, no le riñe
        # por los de atras.
        return {"titulo": "¿Cómo fuiste hoy?",
                "detalle": f"Llevas {racha} días seguidos sin cerrar, no lo dejes hoy también"}
    return {"titulo": "¿Cómo fuiste hoy?", "detalle": "Para rellenar al final del día"}
