"""
DE DÓNDE SE BAJA CUANDO SOBRA UN MACRO.

Jesús, nota de voz del 31-08-2026: «cuando recalcule, pregunte, pregunte de qué quiere bajar
la proteína, del polvo o del queso [...] es imposible que la aplicación aprenda eso, porque
te puede quedar más denso, menos denso; yo por ejemplo a la caseína hay gente que le gusta
con muy poquita leche, otra gente que le gusta con más [...] lo más sencillo es preguntar, o
sea que pregunte de dónde recalcula».

MEDIDO ANTES DE TOCAR NADA. Una comida con 60 g de aislado y 300 g de queso batido, para un
objetivo de 38 P, salía del cuadre con el aislado en 5 g y el queso intacto en 300. Y con los
mismos dos alimentos, cambiando SOLO el orden de la lista, salía el queso en 285 y el aislado
en 10. La app ya decidía; lo que no tenía era criterio: mandaba el orden de la lista.

Y no es cosa de batidos. Pollo 250 g + atún 150 g + arroz 100 g para 38 P salía con el pollo
desplomado a 60 g y el atún casi entero en 125: quien se hizo un plato de pollo con algo de
atún se encontraba un plato de atún con algo de pollo.

QUÉ SE PREGUNTA. Solo lo que la app sabe: cuánto hay de cada alimento, cuánto pone del macro
que sobra, y en cuánto se quedaría. Nada de «queda más espeso» ni «más líquido»: la app no
sabe la textura de nada, y eso es justo lo que Jesús dice que no puede aprender. En un plato
de pollo con arroz esa frase no significaría nada.

A QUIÉN SE LE PREGUNTA. Solo cuando hay que BAJAR y hay DOS O MÁS sitios de donde bajarlo. Si
solo un alimento pone ese macro no hay decisión que tomar: se baja y se dice. Y un alimento
que pone una miseria del macro no entra en la pregunta (el arroz del ejemplo pone 7 P de 90:
bajarlo no arregla la proteína y de paso te carga los hidratos).

Las cantidades las calcula `routes/calculator.py`, que es donde vive el dimensionado. Aquí
están las reglas, para poder probarlas sin levantar nada.
"""

NOMBRE_MACRO = {"P": "proteína", "H": "hidratos", "G": "grasa"}

# Por debajo de esto no se considera que sobre nada. Es el mismo umbral con el que el cuadre
# decide si avisar de un desfase: si ahí no merece la pena decirlo, aquí no merece preguntarlo.
SOBRA_MINIMA = 4.0

# Un alimento entra en la pregunta si pone al menos esta parte del macro que hay en la comida.
# Con menos, bajarlo no resuelve nada y solo estorba en la lista.
PARTE_MINIMA = 0.15


def _g(n):
    """Gramos como se escriben aquí: sin decimal si es redondo, y con coma si no."""
    n = round(float(n or 0), 1)
    entero = int(n)
    return str(entero) if abs(n - entero) < 0.05 else f"{n:.1f}".replace(".", ",")


def macro_que_sobra(servido, objetivo):
    """El macro que más se pasa del objetivo, o None si no se pasa ninguno.

    Se mira SOLO lo que sobra, no lo que falta: faltar se arregla añadiendo, y eso no es una
    decisión de dónde quitar. Un objetivo infinito (la grasa del peri, que va libre) no cuenta:
    ahí no se puede pasar nadie.
    """
    peor, cuanto = None, SOBRA_MINIMA
    for m in ("P", "H", "G"):
        obj = float(objetivo.get(m, 0) or 0)
        if obj == float("inf"):
            continue
        sobra = float(servido.get(m, 0) or 0) - obj
        if sobra > cuanto:
            peor, cuanto = m, sobra
    return peor


def de_donde_se_puede_bajar(aportes, macro):
    """Los alimentos que ponen bastante de ese macro como para que bajarlos sirva de algo.

    `aportes` es la lista de lo que el cliente tiene AHORA en la comida:
    [{"alimento_id": int, "nombre": str, "cantidad_g": float, "macros": {"P":..,"H":..,"G":..}}]

    Salen ordenados de más a menos, que es el orden en que tiene sentido leerlos.
    """
    total = sum(float((a.get("macros") or {}).get(macro, 0) or 0) for a in aportes)
    if total <= 0:
        return []
    minimo = total * PARTE_MINIMA
    candidatos = [a for a in aportes
                  if float((a.get("macros") or {}).get(macro, 0) or 0) >= minimo]
    return sorted(candidatos,
                  key=lambda a: float((a.get("macros") or {}).get(macro, 0) or 0),
                  reverse=True)


def hay_que_preguntar(servido, objetivo, aportes):
    """¿Hay algo que bajar Y más de un sitio de donde bajarlo?"""
    macro = macro_que_sobra(servido, objetivo)
    if not macro:
        return None
    if len(de_donde_se_puede_bajar(aportes, macro)) < 2:
        return None
    return macro


def factor_proporcional(sobra, aporte_de_los_candidatos):
    """Por cuánto hay que multiplicar a los candidatos para que se lleven ellos toda la sobra.

    «De los dos, en la misma proporción»: bajan todos a la vez y la comida mantiene el equilibrio
    que tenía, solo que con menos cantidad. Es la única de las tres opciones que a menudo llega
    al objetivo, porque bajar un alimento solo se topa con su mínimo pesable.
    """
    if aporte_de_los_candidatos <= 0:
        return 1.0
    return max(0.0, (aporte_de_los_candidatos - sobra) / aporte_de_los_candidatos)


def titulo(macro, sobra):
    """La pregunta. Sin adjetivos: el macro, los gramos y de dónde."""
    return f"Sobra {NOMBRE_MACRO.get(macro, macro)}: hay que bajar {_g(sobra)} g. ¿De dónde?"


def texto_de_la_opcion(nombre, cantidad_ahora, aporta, macro, queda_en, sobraria_aun):
    """Una línea de la lista. Solo hechos: lo que hay, lo que pone y en cuánto se quedaría."""
    linea = (f"{nombre} · {_g(cantidad_ahora)} g · pone {_g(aporta)} "
             f"{'g de ' + NOMBRE_MACRO.get(macro, macro)}")
    if queda_en is None:
        return linea
    detalle = f"se quedaría en {_g(queda_en)} g"
    if sobraria_aun and sobraria_aun > SOBRA_MINIMA:
        detalle += f", y aún sobrarían {_g(sobraria_aun)}"
    return f"{linea} → {detalle}"


def texto_de_la_opcion_proporcional(cantidades):
    """La tercera: bajan todos a la vez. `cantidades` = [(nombre, queda_en), ...]"""
    return "De todos, en la misma proporción → " + " · ".join(
        f"{nombre} {_g(queda)} g" for nombre, queda in cantidades)
