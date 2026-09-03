"""
EL INFORME DEL MES (documento «El informe del mes», 1-09-2026).

«Lo que recibe cuando manda el reporte mensual. Las dos pantallas como tienen que quedar.»

El informe que había salía de la especificación del 31-07 y tenía ocho apartados pensados
para juzgar el mes: el ritmo de peso contra el que le toca, el cumplimiento en barras, los
macros comidos contra los objetivos. El documento nuevo lo cambia de fondo: el informe deja
de ser un veredicto y pasa a ser **el espejo de lo que ha hecho**. Diez bloques, y seis de
ellos no existían.

Dos frases del documento mandan sobre todo lo demás:

    «Se genera con los datos que ya ha dejado en la calculadora más lo que acaba de
     contestar en el reporte. Se le entrega AL ENVIAR, con el hueco del feedback vacío.»

    «El informe no le pide nada.»

Lo segundo no es una nota de estilo: es lo que separa el informe del reporte. El reporte
pregunta; el informe cuenta. Lo único que se puede tocar son los selectores de las fotos y
el botón de guardar el desayuno como plantilla.

Aquí vive el CÁLCULO PURO de los bloques nuevos: no toca base de datos ni HTTP. Quien
llama trae las dietas, los pesajes y los extras ya leídos.
"""
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Cómo se le dice su objetivo. En el reporte se marca «definición / volumen /
# mantenimiento», que son las palabras del oficio; en el informe se le habla a él.
OBJETIVO = {
    "definicion": "Bajar grasa",
    "volumen": "Ganar músculo",
    "mantenimiento": "Mantener lo conseguido",
}

# El momento del día, tal y como lo rotula la maqueta: a la izquierda la hora («Tarde»,
# «Noche», «Al terminar») y al lado el nombre de la comida.
MOMENTO_DEL_DIA = {
    "desayuno": "Mañana",
    "comida": "Mediodía",
    "merienda": "Tarde",
    "cena": "Noche",
}
MOMENTO_PERI = {"Intra": "Entrenando", "Post": "Al terminar"}

# Las diez medidas con su rótulo, los mismos que la pantalla donde se piden
# (`frontend/src/lib/medidas.js`). Están aquí y no importadas de `models.common` porque
# allí solo hay las claves, y el informe necesita cómo se llaman.
ETIQUETAS_MEDIDAS = (
    ("hombros", "Hombros"),
    ("mesoesternal", "Mesoesternal"),
    ("brazo_d", "Brazo derecho relajado"),
    ("brazo_i", "Brazo izquierdo relajado"),
    ("muslo_d", "Muslo derecho"),
    ("muslo_i", "Muslo izquierdo"),
    ("cadera", "Cadera"),
    ("cintura", "Cintura"),
    ("gemelo_d", "Gemelo derecho"),
    ("gemelo_i", "Gemelo izquierdo"),
)

DIAS_CORTOS = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")
MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre")


def _num(v: float, decimales: int = 1) -> str:
    """«78,4». Con coma, y sin el cero de más cuando es redondo."""
    t = f"{float(v):.{decimales}f}"
    if t.endswith(".0"):
        t = t[:-2]
    return t.replace(".", ",")


def _kg(v: Optional[float]) -> Optional[str]:
    return None if v is None else f"{_num(v)} kg"


def _con_signo(v: Optional[float], unidad: str = " kg") -> Optional[str]:
    """«−2,8 kg», «+1,2 kg», «0 kg». Con el menos de verdad, no un guion."""
    if v is None:
        return None
    n = round(float(v), 1)
    signo = "+" if n > 0 else "−" if n < 0 else ""
    return f"{signo}{_num(abs(n))}{unidad}"


def _enumerar(xs: Sequence[str]) -> str:
    """«pollo, arroz y aceite»: una lista dicha como se dice hablando."""
    xs = [x for x in xs if x]
    if not xs:
        return ""
    if len(xs) == 1:
        return xs[0]
    return f"{', '.join(xs[:-1])} y {xs[-1]}"


# ─────────────────────────────────────────────────────────────────────────────
# 1 · DÓNDE ESTÁS
# ─────────────────────────────────────────────────────────────────────────────

def donde_estas(objetivo: Optional[str], semana: Optional[int],
                semanas_totales: Optional[int]) -> Dict[str, Any]:
    """«TU OBJETIVO Bajar grasa · TU CICLO Semana 8 de 12».

    El objetivo faltaba en el informe de antes, que solo decía la semana. Y sin objetivo la
    semana no significa nada: la octava de doce es media cosa según se esté bajando grasa o
    ganando músculo.
    """
    return {
        "objetivo": objetivo,
        "objetivo_label": OBJETIVO.get(objetivo or "") or None,
        "semana": semana,
        "semanas_totales": semanas_totales,
        # «Semana 8 de 12», o «Semana 8» a secas cuando el plan no tiene ciclo cerrado.
        "ciclo_label": (f"Semana {semana} de {semanas_totales}"
                        if semana and semanas_totales else
                        f"Semana {semana}" if semana else None),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2 · TU FEEDBACK Y TU PROGRAMA NUEVO
# ─────────────────────────────────────────────────────────────────────────────

def feedback_del_informe(texto: Optional[str], firmante: Optional[str] = None,
                         fecha_label: Optional[str] = None,
                         dia_prometido: str = "viernes",
                         hora_prometida: str = "15:00") -> Dict[str, Any]:
    """El bloque 2, en sus dos estados.

    Del documento: al enviar, «el hueco del feedback, en gris y con la hora»; cuando le
    contestas, «el mismo informe, con tu bloque arriba. No es otro documento: es éste,
    completado».

    LA HORA VA EN LA FRASE A PROPÓSITO. Sin ella («te lo mandamos pronto») el cliente no
    sabe si esperar diez minutos o dos días, y vuelve a preguntar. Con ella, la promesa se
    puede cumplir o incumplir, que es lo que la hace valer.
    """
    escrito = (texto or "").strip()
    if not escrito:
        return {
            "pendiente": True,
            "aviso": (f"En estos momentos estamos revisando tu reporte mensual. "
                      f"Antes del {dia_prometido} a las {hora_prometida} te mandamos todo."),
        }
    return {
        "pendiente": False,
        "texto": escrito,
        "firma": firmante or None,
        # Las iniciales del avatar redondo de la maqueta.
        "iniciales": "".join(p[0] for p in (firmante or "").split()[:2]).upper() or None,
        "fecha_label": fecha_label,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3 · TU PESO
# ─────────────────────────────────────────────────────────────────────────────

def _reparto_semanal(pesos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """«Porcentaje del peso total que has ido bajando por semana»: 10 · 32 · 36 · 22.

    No es cuánto pesaba cada semana: es QUÉ PARTE del cambio total pasó en cada una. Sirve
    para ver dónde se movió la cosa, que es distinto de ver la curva.

    Una semana en la que fue al revés sale en negativo, y eso es correcto: si el mes bajó
    2,8 kg y la semana 2 subió, esa semana no aportó nada, restó. Maquillarla repartiendo
    valores absolutos daría cuatro números bonitos que no suman lo que pasó.
    """
    if len(pesos) < 2:
        return []
    primero, ultimo = pesos[0], pesos[-1]
    total = float(ultimo["valor"]) - float(primero["valor"])
    if abs(total) < 0.1:
        return []      # sin cambio no hay nada que repartir

    # Cuatro tramos iguales entre el primer y el último pesaje. Se parte por días y no por
    # semanas naturales: el mes de un cliente empieza el día de su reporte, no en lunes.
    from datetime import date
    d0 = date.fromisoformat(str(primero["fecha"])[:10])
    d1 = date.fromisoformat(str(ultimo["fecha"])[:10])
    dias = max(1, (d1 - d0).days)
    cortes = [d0.toordinal() + round(dias * i / 4) for i in range(5)]

    filas: List[Dict[str, Any]] = []
    for i in range(4):
        ini, fin = cortes[i], cortes[i + 1]
        # El peso al principio y al final del tramo: el último pesaje que hay hasta cada
        # corte. Un tramo sin ningún pesaje nuevo no aporta nada, y así queda.
        def _hasta(orden: int) -> Optional[float]:
            valores = [float(p["valor"]) for p in pesos
                       if date.fromisoformat(str(p["fecha"])[:10]).toordinal() <= orden]
            return valores[-1] if valores else None

        a, b = _hasta(ini), _hasta(fin)
        parte = 0.0 if a is None or b is None else (b - a)
        filas.append({"semana": i + 1, "kg": round(parte, 2),
                      "pct": int(round(100 * parte / total))})

    # El redondeo se cuadra en el tramo que más pesa, para que sumen 100 sin inventar.
    desvio = 100 - sum(f["pct"] for f in filas)
    if desvio and filas:
        gordo = max(filas, key=lambda f: abs(f["pct"]))
        gordo["pct"] += desvio
    return filas


def peso_del_mes(pesos_periodo: List[Dict[str, Any]],
                 peso_al_empezar: Optional[float] = None) -> Dict[str, Any]:
    """El bloque 3 entero, tal y como lo enumera el documento.

    «Con qué peso empezó el mes y con cuál lo acaba, lo que pesaba el día que entró, y el
    porcentaje del peso total que ha bajado cada semana.»

    Es OTRA COSA que el bloque de peso de antes, que enseñaba el ritmo semanal en
    porcentaje y lo juzgaba contra el que le tocaba («más lento de lo que te tocaría»).
    Aquí no se juzga: se cuenta. El juicio es del feedback, que lo firma una persona.
    """
    pesos = [p for p in (pesos_periodo or [])
             if p.get("fecha") and p.get("valor") is not None]
    pesos.sort(key=lambda p: str(p["fecha"]))
    if not pesos:
        return {"hay": False}

    empieza = float(pesos[0]["valor"])
    acaba = float(pesos[-1]["valor"])
    total = round(acaba - empieza, 1)
    desde_el_principio = (round(acaba - float(peso_al_empezar), 1)
                          if peso_al_empezar is not None else None)

    return {
        "hay": True,
        "serie": pesos,
        "empezaste_label": _kg(empieza),
        "acabas_label": _kg(acaba),
        "cambio": total,
        "cambio_label": _con_signo(total),
        "al_empezar": peso_al_empezar,
        "al_empezar_label": _kg(peso_al_empezar),
        "desde_el_principio": desde_el_principio,
        "desde_el_principio_label": _con_signo(desde_el_principio),
        # El rótulo de la esquina: «−2,8 KG ESTE MES».
        "titulo_cambio": (f"{_con_signo(total)} este mes" if total else "Igual que el mes pasado"),
        "por_semana": _reparto_semanal(pesos),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4 · TUS MEDIDAS
# ─────────────────────────────────────────────────────────────────────────────

def medidas_del_informe(actuales: Optional[Dict[str, Any]],
                        mes_anterior: Optional[Dict[str, Any]],
                        primera: Optional[Dict[str, Any]],
                        etiquetas: Sequence[Tuple[str, str]],
                        objetivo: Optional[str] = None) -> Dict[str, Any]:
    """«Las diez, contra el mes pasado y contra su primera toma.»

    Dos columnas de diferencia, no los valores: lo que dice algo es el cambio. El valor
    absoluto de un perímetro solo tiene sentido comparado consigo mismo, y el cliente ya lo
    acaba de escribir en el reporte.

    EL COLOR DEPENDE DEL OBJETIVO. Menos centímetros de cintura es una buena noticia
    bajando grasa y una mala ganando músculo; pintarlo siempre de verde sería felicitar a
    alguien por lo contrario de lo que busca.
    """
    actuales = actuales or {}
    if not actuales:
        return {"hay": False}

    quiere_bajar = (objetivo or "definicion") != "volumen"
    filas = []
    for clave, etiqueta in etiquetas:
        ahora = actuales.get(clave)
        if ahora is None:
            continue
        fila = {"clave": clave, "etiqueta": etiqueta, "valor": ahora}
        for cual, fuente in (("mes", mes_anterior), ("primera", primera)):
            antes = (fuente or {}).get(clave)
            if antes is None:
                fila[cual] = None
                continue
            d = round(float(ahora) - float(antes), 1)
            fila[cual] = {
                "dif": d,
                "label": _con_signo(d, ""),
                "color": ("gris" if d == 0
                          else "verde" if (d < 0) == quiere_bajar else "rojo"),
            }
        filas.append(fila)

    return {"hay": bool(filas), "filas": filas,
            "hay_mes": any(f.get("mes") for f in filas),
            "hay_primera": any(f.get("primera") for f in filas)}


# ─────────────────────────────────────────────────────────────────────────────
# 5 · TU PORCENTAJE DE GRASA
# ─────────────────────────────────────────────────────────────────────────────

#: EL % DE GRASA ES OPCIONAL, Y SE DICE (punto 10.2 de «Todo lo que está validado», 2-09).
#:
#: Decía «Se mide al final de cada ciclo, cada 12 semanas» y sonaba a obligatorio: a una cita
#: que se pierde si no la cumples. No lo es. Su texto, tal y como lo dejó escrito:
#:
#:     «registrarlo ahora es opcional, lo puedes hacer si quieres, pero para poder sacar
#:      conclusiones es mejor hacerlo uno de cada 3 reportes (12 semanas): así comparas el
#:      inicio y el final de cada ciclo»
#:
#: Va aquí y en el botón de Evolución, que son los dos sitios donde se le habla de esto, para
#: que no cuenten dos cosas distintas. `cada_semanas` sigue mandando el número por si un plan
#: lleva otro ciclo.
def _texto_opcional(cada_semanas: int) -> str:
    return ("Registrarlo es opcional, lo puedes hacer si quieres, pero para poder sacar "
            f"conclusiones es mejor hacerlo uno de cada 3 reportes ({cada_semanas} semanas): "
            "así comparas el inicio y el final de cada ciclo.")


def grasa_del_informe(valor: Optional[float], fecha_label: Optional[str],
                      semanas_desde: Optional[int],
                      cada_semanas: int = 12) -> Dict[str, Any]:
    """El bloque del % de grasa: qué es, cuándo se midió y cuándo conviene la próxima.

    Se dice CUÁNDO se midió y cuándo toca la próxima. El informe de antes ponía el número y
    el anterior al lado, y con eso el cliente no sabía si su 18 % era de este mes o de hace
    tres, que en este dato es toda la diferencia.
    """
    if valor is None:
        return {"hay": False, "explicacion": _texto_opcional(cada_semanas)}
    faltan = None if semanas_desde is None else max(0, cada_semanas - int(semanas_desde))
    return {
        "hay": True,
        "valor": valor,
        "valor_label": f"{_num(valor)} %",
        "fecha_label": fecha_label,
        "explicacion": _texto_opcional(cada_semanas),
        "ultima": (f"La última medición: {_num(valor)} %"
                   + (f", el {fecha_label}." if fecha_label else ".")),
        # El rótulo de la esquina: «EN 4 SEMANAS», o «TOCA AHORA» si ya se cumplieron.
        "cuando": (None if faltan is None else
                   "Toca ahora" if faltan == 0 else
                   f"En {faltan} {'semana' if faltan == 1 else 'semanas'}"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 7 · LO QUE HAS HECHO
# ─────────────────────────────────────────────────────────────────────────────

def lo_que_has_hecho(dieta: Optional[Dict[str, Any]], entreno: Optional[Dict[str, Any]],
                     cierres: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Las cuatro filas del documento: dietas, entrenos, cardios y suplementación.

    Cada una con SU CONTRARIO al lado -- hechos y perdidos, sí y no --, que es como está en
    la maqueta. No son barras de porcentaje: son cuentas. Un 78 % de cumplimiento no le dice
    a nadie cuántos días se dejó, y los días sí.

    Lo que no se sabe no sale, igual que en el paso 1 del reporte: sin rutina no hay
    entrenos previstos que perder, y sin suplementación en el plan no hay pauta que romper.
    """
    dieta = dieta or {}
    entreno = entreno or {}
    cierres = cierres or {}
    filas: List[Dict[str, Any]] = []

    def pon(clave, etiqueta, valor, etiqueta2=None, valor2=None):
        filas.append({"clave": clave, "etiqueta": etiqueta, "valor": valor,
                      "etiqueta2": etiqueta2, "valor2": valor2})

    dias = int(dieta.get("dias_periodo") or 0)
    if dias:
        pon("dietas", "Dietas completas", int(dieta.get("dias_registrados") or 0),
            "de", dias)
        pon("cuadradas", "Cuadradas al 100 %", int(dieta.get("dias_cuadrados") or 0),
            "Comiste de más", cierres.get("dias_comio_de_mas"))

    previstos = entreno.get("previstos")
    if previstos:
        hechos = int(entreno.get("hechos") or 0)
        pon("entrenos", "Entrenos hechos", hechos,
            "Perdidos", max(0, int(previstos) - hechos))

    cardio = entreno.get("cardio") or {}
    if cardio.get("previstas"):
        hechas = int(cardio.get("hechas") or 0)
        pon("cardios", "Cardios hechos", hechas,
            "Perdidos", max(0, int(cardio["previstas"]) - hechas))

    sup = cierres.get("suplementacion") or {}
    if sup.get("de"):
        si = int(sup.get("cumplidos") or 0)
        pon("suplementacion", "Suplementación sí", si, "no", max(0, int(sup["de"]) - si))

    return {"hay": bool(filas), "filas": filas}


# ─────────────────────────────────────────────────────────────────────────────
# 8 · TU DÍA TIPO
# ─────────────────────────────────────────────────────────────────────────────

# Cuándo se considera que una comida «cambia casi cada día»: cuando la combinación que más
# repite no llega a un tercio de los días que tuvo esa comida. Con menos de eso, señalar
# una como «la tuya» sería quedarse con la más frecuente de un montón de casualidades.
FRACCION_PARA_SER_LA_TUYA = 1 / 3


def _texto_de_la_combinacion(items: Sequence[Dict[str, Any]]) -> str:
    """«30 g de whey y 40 g de crema de arroz», «1 yogur griego y 30 g de nueces»."""
    trozos = []
    for it in items:
        cantidad, unidad, nombre = it.get("cantidad"), it.get("unidad"), it.get("nombre")
        if not nombre:
            continue
        if cantidad is None:
            trozos.append(nombre)
        elif unidad == "ud":
            n = int(round(float(cantidad)))
            trozos.append(f"{n} {nombre}")
        else:
            trozos.append(f"{int(round(float(cantidad)))} g de {nombre}")
    return _enumerar(trozos)


def dia_tipo(comidas_por_dia: List[Dict[str, Any]]) -> Dict[str, Any]:
    """«La combinación que más repites en cada comida, y cuántos días.»

    `comidas_por_dia` es una lista de comidas ya aplanadas:
        {"clave": "Post", "momento": "peri", "nombre": "Post", "es_peri": True,
         "fecha": "2026-08-12", "items": [{"nombre": "Whey", "cantidad": 30, "unidad": "g"}]}

    La combinación se identifica por LOS ALIMENTOS, no por los gramos: la calculadora
    reajusta las cantidades cada día, así que exigir que coincidan al gramo daría 28
    combinaciones distintas siempre. Las cantidades que se enseñan son las más repetidas de
    esa combinación, que es lo que el cliente reconoce como «su desayuno».
    """
    por_comida: Dict[str, Dict[str, Any]] = {}
    for c in comidas_por_dia or []:
        clave = c.get("clave")
        if not clave or not (c.get("items") or []):
            continue
        d = por_comida.setdefault(clave, {
            "clave": clave, "nombre": c.get("nombre") or clave,
            "momento": c.get("momento"), "es_peri": bool(c.get("es_peri")),
            "dias": 0, "combinaciones": {},
        })
        d["dias"] += 1
        firma = tuple(sorted((i.get("nombre") or "").strip().lower()
                             for i in c["items"] if i.get("nombre")))
        d["combinaciones"].setdefault(firma, []).append(c["items"])

    filas: List[Dict[str, Any]] = []
    for d in por_comida.values():
        if not d["combinaciones"]:
            continue
        firma, apariciones = max(d["combinaciones"].items(), key=lambda kv: len(kv[1]))
        repite = len(apariciones)
        distintas = len(d["combinaciones"])
        fila = {"clave": d["clave"], "nombre": d["nombre"],
                "momento": (MOMENTO_PERI.get(d["clave"]) if d["es_peri"]
                            else MOMENTO_DEL_DIA.get(d["momento"] or "")),
                "dias": d["dias"], "combinaciones_distintas": distintas}

        if repite < max(2, d["dias"] * FRACCION_PARA_SER_LA_TUYA):
            fila.update({
                "varia": True,
                "texto": "Cambia casi cada día",
                "cuantos": (f"{distintas} combinaciones distintas" if distintas != 1
                            else "1 combinación"),
            })
        else:
            # Las cantidades: la mediana de cada alimento dentro de esa combinación, que
            # aguanta un día suelto con el doble mejor que la media.
            por_nombre: Dict[str, List[float]] = {}
            unidad_de: Dict[str, str] = {}
            visible: Dict[str, str] = {}
            # El id y los gramos viajan también: son lo que hace falta para volver a montar
            # la comida desde el botón «Guárdamela como plantilla». La mediana se saca de
            # los gramos por su cuenta, porque `cantidad` puede venir en unidades.
            id_de: Dict[str, Any] = {}
            gramos_de: Dict[str, List[float]] = {}
            for items in apariciones:
                for i in items:
                    n = (i.get("nombre") or "").strip()
                    if not n:
                        continue
                    clave_n = n.lower()
                    visible.setdefault(clave_n, n)
                    unidad_de.setdefault(clave_n, i.get("unidad") or "g")
                    if i.get("alimento_id") is not None:
                        id_de.setdefault(clave_n, i["alimento_id"])
                    if i.get("gramos") is not None:
                        gramos_de.setdefault(clave_n, []).append(float(i["gramos"]))
                    if i.get("cantidad") is not None:
                        por_nombre.setdefault(clave_n, []).append(float(i["cantidad"]))
            # EN EL ORDEN DE LA COMIDA, NO EN EL DEL ALFABETO. La firma va ordenada para
            # poder comparar combinaciones, pero enseñarla así le cambiaría el desayuno de
            # sitio: él lo tiene puesto en un orden y lo reconoce en ese orden.
            resumen = []
            for i in apariciones[0]:
                clave_n = (i.get("nombre") or "").strip().lower()
                if not clave_n or any(r["_clave"] == clave_n for r in resumen):
                    continue
                valores = sorted(por_nombre.get(clave_n) or [])
                gramos = sorted(gramos_de.get(clave_n) or [])
                resumen.append({"_clave": clave_n,
                                "nombre": visible.get(clave_n, clave_n),
                                "unidad": unidad_de.get(clave_n, "g"),
                                "cantidad": valores[len(valores) // 2] if valores else None,
                                "alimento_id": id_de.get(clave_n),
                                "gramos": gramos[len(gramos) // 2] if gramos else None})
            for r in resumen:
                r.pop("_clave", None)
            fila.update({
                "varia": False,
                "texto": _texto_de_la_combinacion(resumen),
                "cuantos": (f"los {d['dias']} días de entreno" if d["es_peri"] and repite == d["dias"]
                            else f"{repite} de {d['dias']} días de entreno" if d["es_peri"]
                            else f"{repite} de {d['dias']} días"),
                "items": resumen,
            })
        filas.append(fila)

    # En el orden del día, y el peri donde le toca: intra y post detrás del entreno.
    orden = {"C1": 1, "C2": 2, "C3": 3, "C4": 4, "C5": 5, "Intra": 2.4, "Post": 2.6}
    filas.sort(key=lambda f: orden.get(f["clave"], 9))
    return {"hay": bool(filas), "filas": filas}


# ─────────────────────────────────────────────────────────────────────────────
# 9 · PREFERENCIAS CONCRETAS DE ALIMENTOS
# ─────────────────────────────────────────────────────────────────────────────

CUANTAS_PREFERENCIAS = 3


def _macro_que_manda(macros: Dict[str, Any]) -> Optional[str]:
    """De qué es un alimento: proteína, hidratos o grasas.

    Por las calorías que aporta cada macro, no por los gramos: 10 g de grasa son 90 kcal y
    10 g de hidratos, 40. Contando gramos, el aceite de oliva competiría con el arroz.
    """
    p = float(macros.get("P") or 0) * 4
    h = float(macros.get("H") or 0) * 4
    g = float(macros.get("G") or 0) * 9
    if p <= 0 and h <= 0 and g <= 0:
        return None
    return max((("proteina", p), ("hidratos", h), ("grasas", g)), key=lambda x: x[1])[0]


def preferencias_de_alimentos(usos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """«Sus tres principales de proteína, hidratos y grasas, con las veces que los ha puesto.»

    `usos` es una fila por alimento y día: {"nombre", "macros": {"P","H","G"}, "fecha"}.
    Se cuenta en DÍAS y no en veces: quien pone pollo en la comida y en la cena del mismo
    día no ha comido pollo dos días.
    """
    por_grupo: Dict[str, Dict[str, Any]] = {"proteina": {}, "hidratos": {}, "grasas": {}}
    for u in usos or []:
        nombre = (u.get("nombre") or "").strip()
        if not nombre:
            continue
        grupo = _macro_que_manda(u.get("macros") or {})
        if not grupo:
            continue
        ficha = por_grupo[grupo].setdefault(nombre.lower(), {"nombre": nombre, "dias": set()})
        if u.get("fecha"):
            ficha["dias"].add(str(u["fecha"])[:10])

    salida: Dict[str, Any] = {"hay": False}
    for grupo, fichas in por_grupo.items():
        top = sorted(fichas.values(), key=lambda f: (-len(f["dias"]), f["nombre"]))
        salida[grupo] = [
            {"nombre": f["nombre"], "dias": len(f["dias"]),
             "label": f"{len(f['dias'])} {'día' if len(f['dias']) == 1 else 'días'}"}
            for f in top[:CUANTAS_PREFERENCIAS] if f["dias"]
        ]
        if salida[grupo]:
            salida["hay"] = True
    return salida


# ─────────────────────────────────────────────────────────────────────────────
# 10 · EXTRAS REGISTRADOS
# ─────────────────────────────────────────────────────────────────────────────

def extras_registrados(extras: List[Dict[str, Any]]) -> Dict[str, Any]:
    """«Seis días, y cinco cayeron en fin de semana. Lo que apuntaste: ...»

    El dato que hace pensar no es cuántos extras hubo, sino CUÁNDO. Seis repartidos por el
    mes y seis en seis fines de semana seguidos son dos meses distintos, y el cliente lo ve
    solo si se le dice.
    """
    from datetime import date

    limpios = [e for e in (extras or []) if (e.get("texto") or "").strip() and e.get("fecha")]
    if not limpios:
        return {"hay": False}
    limpios.sort(key=lambda e: str(e["fecha"]))

    lista, dias = [], set()
    en_finde = set()
    for e in limpios:
        try:
            d = date.fromisoformat(str(e["fecha"])[:10])
        except (ValueError, TypeError):
            continue
        dias.add(d.isoformat())
        if d.weekday() >= 5:
            en_finde.add(d.isoformat())
        lista.append({"fecha": d.isoformat(),
                      "dia_label": f"{DIAS_CORTOS[d.weekday()]} {d.day}",
                      "texto": (e.get("texto") or "").strip()})

    n, f = len(dias), len(en_finde)
    palabras = ("Un", "Dos", "Tres", "Cuatro", "Cinco", "Seis", "Siete", "Ocho", "Nueve", "Diez")
    def _pal(x):
        return palabras[x - 1] if 1 <= x <= len(palabras) else str(x)

    titulo = f"{_pal(n)} {'día' if n == 1 else 'días'}"
    if f:
        titulo += (f", y {'cayó' if f == 1 else 'cayeron'} en fin de semana"
                   if f == n else
                   f", y {_pal(f).lower()} {'cayó' if f == 1 else 'cayeron'} en fin de semana")
    return {"hay": True, "dias": n, "en_finde": f,
            "titulo": f"{titulo}. Lo que apuntaste:", "lista": lista}
