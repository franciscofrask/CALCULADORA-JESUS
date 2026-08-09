"""
Las preferencias de comida, en el idioma que entiende la app. Punto 4.18 del 09-08.

Lo que se veia: la pantalla de preferencias decia «7 categorias seleccionadas» y solo habia
una marcada. No era un contador roto.

Lo que hay guardado en los clientes que vinieron de Calma son CODIGOS de categoria -- '8',
'21', '2.3', '11' -- y tanto la pantalla como el filtro del backend trabajan con NOMBRES:
'panes', 'arroces', 'vacuno', 'fruta'. Nunca coinciden. La casilla pregunta por 'panes' y en
el conjunto hay un '8', asi que no se marca ninguna; la unica que aparecia marcada era la
obligatoria, que se añade a mano.

Y no es solo cosmetico. `AVOIDABLE_PREFIXES` tambien esta indexado por nombre, asi que
`AVOIDABLE_PREFIXES.get('8')` no devuelve nada: **las preferencias de esos clientes no se han
aplicado nunca**, ni al pintarlas ni al filtrar la comida. Son datos muertos desde la
migracion.

Aqui se traducen al leer. No se reescribe nada en la base: la traduccion es deterministica y
se puede hacer cada vez, asi que no hace falta tocar los datos de nadie para que empiecen a
funcionar. Cuando el cliente vuelva a guardar sus preferencias, se guardaran ya en nombres.

Se aceptan las dos formas a proposito: hay clientes con nombres (los que pasaron por la
pantalla nueva) y clientes con codigos (los migrados), y los dos tienen que funcionar.
"""
from typing import Iterable, List


def _mapa_de_codigos():
    """{codigo: nombre}, sacado del mismo sitio que usa el filtro para no tener dos verdades."""
    from routes.calculator import AVOIDABLE_PREFIXES

    fuera = {}
    for nombre, codigos in AVOIDABLE_PREFIXES.items():
        for c in codigos:
            fuera[str(c)] = nombre
    return fuera


def a_nombres(valores: Iterable) -> List[str]:
    """La lista de preferencias en NOMBRES, vengan como vengan.

    Un codigo que no existe se descarta: es una categoria que ya no esta, y arrastrarla solo
    sirve para que el contador diga un numero que no se corresponde con nada.

    Un codigo mas general que los del mapa ('2' cuando el mapa tiene 2.1, 2.2...) se abre en
    todas las que cuelgan de el: quien dijo que le gusta la carne no dijo que solo la de aves.
    """
    from routes.calculator import AVOIDABLE_PREFIXES

    codigos = _mapa_de_codigos()
    nombres, vistos = [], set()

    def añadir(n):
        if n and n not in vistos:
            vistos.add(n)
            nombres.append(n)

    for v in (valores or []):
        s = str(v).strip()
        if not s:
            continue
        if s in AVOIDABLE_PREFIXES:      # ya es un nombre
            añadir(s)
        elif s in codigos:               # es un codigo exacto
            añadir(codigos[s])
        else:                            # ¿es un codigo mas general?
            for c, n in codigos.items():
                if c.startswith(s + "."):
                    añadir(n)
    return nombres
