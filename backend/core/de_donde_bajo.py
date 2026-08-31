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

A QUIÉN SE LE PREGUNTA. Cuando hay que bajar y hay dos o más sitios de donde bajarlo. Si solo
un alimento pone ese macro no hay decisión que tomar: se baja y se dice.

Y HAY COMIDAS QUE NO SE PUEDEN CUADRAR BAJANDO (Francisco, 31-08-2026, probándolo).
Una comida suya con catorce alimentos daba, CON TODO A SU MÍNIMO PESABLE, 57,9 P / 18,2 H /
50,2 G contra un objetivo de 47,5 / 72 / 12: 38 g de grasa de sobra aunque no quede nada que
bajar. Ahí preguntar «de dónde bajo» no ofrece ninguna salida, y la app se limitaba a decir
«no se puede cuadrar sin quitar nada: tendrías que quitar o bajar Almendras, que pone 10,6 g»
-- nombrando un alimento que ni siquiera resolvía el problema.

Su frase: «para qué me dice que quite; también me debería preguntar qué quitar, los macros
tienen que quedar cuadrados, ese es el objetivo del botón».

Así que la pregunta tiene dos formas, y la elige la aritmética:
  - si con todo en el suelo el macro CABE, se puede arreglar bajando  -> «¿de dónde bajo?»
  - si ni así cabe, bajar no puede arreglarlo                         -> «¿qué quito?»
Y se vuelve a preguntar hasta que la comida cuadre o el cliente lo deje. Esto NO rompe la
regla del 08-08 («cuadrar no quita ingredientes; lo que el cliente ha puesto lo quita el
cliente»): la app sigue sin quitar nada por su cuenta, lo quita él.

Las cantidades las calcula `routes/calculator.py`, que es donde vive el dimensionado. Aquí
están las reglas, para poder probarlas sin levantar nada.
"""

NOMBRE_MACRO = {"P": "proteína", "H": "hidratos", "G": "grasa"}

# Por debajo de esto no se considera que sobre nada. Es el mismo umbral con el que el cuadre
# decide si avisar de un desfase: si ahí no merece la pena decirlo, aquí no merece preguntarlo.
SOBRA_MINIMA = 4.0

# Cuántas opciones se enseñan como mucho. Con catorce alimentos, listarlos todos no es una
# pregunta: es un muro. Salen los que más ponen del macro, que son los que deciden.
MAXIMO_OPCIONES = 5


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


def _de(a, clave, macro):
    return float((a.get(clave) or {}).get(macro, 0) or 0)


def de_donde_se_puede_bajar(aportes, macro):
    """Los alimentos a los que bajarles la cantidad devuelve algo apreciable de ese macro.

    `aportes` es lo que el cliente tiene AHORA en la comida, con lo que pondría cada uno si se
    le bajara a su mínimo pesable:
    [{"alimento_id": int, "nombre": str, "cantidad_g": float,
      "macros": {"P":..,"H":..,"G":..}, "suelo": {"P":..,"H":..,"G":..}}]

    EL CRITERIO ES CUÁNTO PUEDE DEVOLVER, no cuánto pone. Antes entraba en la lista el que
    pusiera al menos el 15 % del macro de la comida, y eso dejaba fuera la pregunta justo
    cuando más falta hacía: en la comida de los catorce alimentos el bacon ponía la mitad de
    la grasa, así que era el ÚNICO que pasaba el corte, se quedaba en un solo candidato y no
    se preguntaba nada. Lo que importa es el margen: lo que pone ahora menos lo que pondría
    en su mínimo. Si eso no llega a 4 g, bajarlo no cambia nada y solo estorba en la lista.

    Salen ordenados de más a menos margen, que es el orden en que tiene sentido leerlos.
    """
    candidatos = [a for a in aportes
                  if _de(a, "macros", macro) - _de(a, "suelo", macro) >= SOBRA_MINIMA]
    candidatos.sort(key=lambda a: _de(a, "macros", macro) - _de(a, "suelo", macro), reverse=True)
    return candidatos[:MAXIMO_OPCIONES]


def que_se_puede_quitar(aportes, macro):
    """Los alimentos que siguen poniendo ese macro aunque estén en su mínimo.

    Son los únicos que sirven cuando bajar ya no da más de sí: si un alimento en su suelo no
    pone nada del macro, quitarlo no arregla nada.
    """
    candidatos = [a for a in aportes if _de(a, "suelo", macro) > 0.5]
    candidatos.sort(key=lambda a: _de(a, "suelo", macro), reverse=True)
    return candidatos[:MAXIMO_OPCIONES]


def bajar_no_llega(aportes, objetivo, macro):
    """¿Se pasa del objetivo AUNQUE todo esté en su mínimo pesable?

    Si se pasa, ninguna respuesta a «de dónde bajo» puede cuadrar la comida: hay que quitar.
    """
    obj = float(objetivo.get(macro, 0) or 0)
    if obj == float("inf"):
        return False
    en_el_suelo = sum(_de(a, "suelo", macro) for a in aportes)
    return (en_el_suelo - obj) > SOBRA_MINIMA


def hay_que_preguntar(servido, objetivo, aportes):
    """Qué macro toca resolver y de qué forma: (macro, "bajar"|"quitar"), o None si nada.

    None quiere decir «no hay nada que preguntar»: o no sobra, o solo hay un sitio de donde
    bajarlo y con bajarlo se arregla, que es el caso en el que la app decide sola sin
    quitarle a nadie una decisión.
    """
    macro = macro_que_sobra(servido, objetivo)
    if not macro:
        return None
    if bajar_no_llega(aportes, objetivo, macro):
        return (macro, "quitar") if que_se_puede_quitar(aportes, macro) else None
    if len(de_donde_se_puede_bajar(aportes, macro)) < 2:
        return None
    return (macro, "bajar")


def factor_proporcional(sobra, aporte_de_los_candidatos):
    """Por cuánto hay que multiplicar a los candidatos para que se lleven ellos toda la sobra.

    «De los dos, en la misma proporción»: bajan todos a la vez y la comida mantiene el equilibrio
    que tenía, solo que con menos cantidad. Es la única de las tres opciones que a menudo llega
    al objetivo, porque bajar un alimento solo se topa con su mínimo pesable.
    """
    if aporte_de_los_candidatos <= 0:
        return 1.0
    return max(0.0, (aporte_de_los_candidatos - sobra) / aporte_de_los_candidatos)


def titulo(macro, sobra, tipo="bajar"):
    """La pregunta. Sin adjetivos: el macro, los gramos y qué hay que decidir."""
    nombre = NOMBRE_MACRO.get(macro, macro)
    if tipo == "quitar":
        # Se dice POR QUÉ no vale con bajar, o «¿qué quito?» parece un capricho de la app.
        return (f"Aunque lo baje todo al mínimo, sobran {_g(sobra)} g de {nombre}. "
                f"¿Qué quito?")
    return f"Sobra {nombre}: hay que bajar {_g(sobra)} g. ¿De dónde?"


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
