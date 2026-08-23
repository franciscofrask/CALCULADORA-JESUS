"""
MOTOR DE MACROS - Cuestionario de ajuste (doc de Jesus del 29-07-2026)
======================================================================
Envuelve calcular_targets() (la tabla) y aplica encima, EN ORDEN:
modificadores de hidratos -> regla dura descanso/entreno -> dieta real ->
grasa segun la dieta que trae -> suelos -> redondeo.

Reglas del doc:
- Los modificadores solo tocan los HIDRATOS de entreno y descanso, NUNCA el
  perientreno y NUNCA la proteina.
- Los porcentajes se SUMAN sobre la base de tabla (no compuestos).
- "Engordo enseguida" = VETO: anula todas las subidas de hidratos.
- El descanso NUNCA por encima del entreno (comidas contra comidas, el peri
  aparte): si se pasa, se sube el entreno hasta igualarlo.
- La dieta real MODULA, no manda: es el factor que mas pesa, pero se queda a
  +-20% de lo que dice la tabla ya modificada. Lo que se hace con ella depende
  de como le esta funcionando (matrices por objetivo). Hasta el 06-08-2026 la
  pisaba entera; Jesus lo corrigio el 15-07 y quedo pendiente de rediseñar.
  Unica excepcion, que sigue entera: quien llega comiendo menos de 75 g de HC
  en definicion recibe el arranque minimo fijo, porque eso es fisica.
- hc_e de la tabla son los hidratos de COMIDAS del dia de entreno (el peri
  va aparte en hc_pe); por eso el suelo de comidas es 60 (con peri 15 => 75).

Pendiente de Jesus: la regla de la TRT (se guarda, no se aplica).

Modulo puro: sin Mongo y sin FastAPI. La persistencia y los avisos al coach
viven en las rutas.
"""

from typing import Dict, List, Optional

from target_calculator import calcular_targets

# =========================================================
# CONSTANTES (spec "QUIZ INICIAL + MOTOR DE MACROS v2")
# =========================================================

# Modificadores de hidratos (fracciones sobre la base de tabla)
MOD_MUY_ACTIVO_ENTRENO = 0.10
MOD_MUY_ACTIVO_DESCANSO = 0.10
# Deporte extra: solo descanso, y el doc del 29-07 lo separa por objetivo. El partido del domingo
# cae en un dia marcado como descanso que en realidad es de entreno disfrazado.
MOD_DEPORTE_EXTRA_DESCANSO_DEFINICION = 0.10
MOD_DEPORTE_EXTRA_DESCANSO_VOLUMEN = 0.20
MOD_NO_ENGORDA = 0.20                    # entreno y descanso; requiere estar por debajo del umbral
# El umbral NO es el mismo para los dos, y hasta el 06-08-2026 lo era. Con el 20 % para
# todos, en mujeres el modificador estaba muerto: la tabla de ellas EMPIEZA en el 20 %, o
# sea que hacía falta estar en el extremo exacto para cobrarlo.
#
# Documento del 07-08-2026 (punto 11, suplanta a todos los anteriores por decisión de
# Francisco del mismo día): "grasa <= 20 %" SIN distinguir sexo. Sustituye al 30 % de
# mujeres del doc del 06-08. Consecuencia asumida del texto literal: la tabla de mujeres
# empieza justo en el 20 %, así que en ellas solo lo cobra quien esté en el arranque.
BF_MAX_NO_ENGORDA = {"hombre": 20.0, "mujer": 20.0}
# Documento del 07-08 (misma decisión): el +20% lo cobra SOLO "casi no lo noto" (con
# grasa <= 20%). Sustituye al doc del 29-07, que incluía también "engordo lo normal".
# `nada` es la cuarta opción del doc del 23-08 («No, nada, me cuesta mucho coger peso»):
# quien la elige no puede subir menos que quien dice «casi no», así que cobra lo mismo.
RESPUESTAS_QUE_SUBEN = ("casi_no", "nada")
TOPE_SUBIDA_ENTRENO = 0.30
TOPE_SUBIDA_DESCANSO = 0.40

# Excepcion que toca proteina: farmacologia / TRT.
# Doc del 03-08: son +10 GRAMOS en el dia de descanso (antes estaba como +10%, que en un
# cliente de 225 g de proteina eran 22,5). En entreno no se toca... salvo que la subida
# rompa la regla dura de abajo, y entonces se suben otros 10 g en entreno.
MOD_FARMACOLOGIA_PROTEINA_DESCANSO_G = 10.0

# NO PROGRAMADOS AUN (guardar el dato, no aplicar):
APLICAR_HISTORIAL_DIETA = False   # +-10% por historial de dieta: en pausa, sin validar
# El +20% "no engorda" en mujeres: encendido (06-08) y se queda encendido. Con el umbral
# del 20 % que fija el doc del 07-08 volverá a aplicarse muy poco en ellas (su tabla
# empieza justo en el 20: once respuestas guardadas, cero aplicaciones en la era del
# umbral al 20). Es la consecuencia del texto literal y queda aceptada; si Jesús quiere
# reactivarlo de verdad en mujeres, el sitio es BF_MAX_NO_ENGORDA.
APLICAR_ENGORDA_EN_MUJERES = True
# TRT / farmacologia: el doc del 29-07 dejaba la regla en pausa hasta que Jesus confirmara como
# afecta. Lo confirmo el 03-08 (+10 g en descanso y la regla dura de entreno+peri), asi que se
# activa. Solo cuenta el uso ACTUAL: quien lo uso en el pasado y ya no, va con proteina normal.
APLICAR_FARMACOLOGIA = True
# El VETO ("engordo enseguida") SI aplica a ambos sexos: es lo conservador.

# Suelos (la tabla ya cumple la proteina; se dejan como red de seguridad).
# Los "macros umbral" (40 g de hidratos / 40 de grasa, max un mes) y la grasa
# de descanso 70 puntual NO los aplica el motor: son decision manual del coach.
SUELO_PROTEINA_ENTRENO = {"hombre": 160, "mujer": 120}
# Doc 29-07: el suelo del dia de entreno son 75 g totales = 60 en comidas + 15 de peri.
SUELO_HC_COMIDAS_ENTRENO = 60
SUELO_HC_DESCANSO = 50
SUELO_GRASA = 50                  # entreno y descanso

# Dieta reportada: banda de peri por HC totales del dia de entreno (doc 29-07).
BANDAS_PERI = [(300, 40), (350, 50), (400, 60), (450, 75), (float("inf"), 90)]

UMBRAL_HC_EN_LAS_ULTIMAS = 75     # < 75 g netos -> arranque minimo
PERI_EN_LAS_ULTIMAS = 15

# Cuanto puede mover la dieta que ya come, arriba o abajo, sobre lo que dice la tabla ya
# modificada.
#
# Hasta el 06-08-2026 no habia tope: si la declaraba y la confirmaba, su dieta PISABA los
# hidratos y se tiraban la tabla y todos los modificadores. Jesus lo corrigio el 15 de
# julio -- "NO manda sobre todo, es un factor mas, el que mas pesa, pero no determinante"
# -- y quedo pendiente de rediseñar.
#
# Ahora modula como los demas, que ya tenian sus topes del 30 y el 40 %. El +-20 % la deja
# siendo el factor que mas pesa (ninguno de los otros llega solo a tanto) sin que se lleve
# el calculo por delante.
#
# La excepcion del que viene comiendo muy poco NO pasa por aqui: si llega con menos de 75 g
# en definicion se le da el arranque minimo fijo, porque eso es fisica y no criterio.
TOPE_DIETA_REPORTADA = 0.20
DESCANSO_SOBRE_COMIDAS = 0.80     # doc 29-07: el descanso va un 20% por debajo de las comidas

# Grasa segun la dieta con la que llega el cliente (doc 29-07, paso 5). Tope 80, igual en
# entreno y en descanso. La excepcion (definicion con X < T) va 50 y 60 y se resuelve aparte.
TRAMOS_GRASA_POR_DIETA = [(60, 60), (90, 70), (float("inf"), 80)]

# Paso 4: que se hace con la dieta real segun como le esta funcionando. "X" son los hidratos de
# entreno + peri que reporta; "T" los mismos de la tabla ya modificada.
#   'x'      -> se le deja X tal cual
#   'tabla'  -> se ignora X y manda la tabla
#   'x_75'   -> el 75% de X
#   'x_-10'  -> X menos 10 g
MATRIZ_DEFINICION = {
    #  como_va          X > T      X < T
    "bien":          ("x",       "x"),
    "lento":         ("tabla",   "x_-10"),
    "mantengo":      ("x_75",    "x_-10"),
    "cogiendo_peso": ("tabla",   "x_-10"),
}
MATRIZ_VOLUMEN = {
    "bien":          ("x",       "x"),
    "lento":         ("x",       "tabla"),
    "mucha_grasa":   ("x",       "x"),
    "mantengo":      ("x",       "tabla"),
    "bajando":       ("x",       "tabla"),
}

# Humano en el bucle: si lo reportado se desvia mas de esto de lo recomendado,
# se avisa al entrenador para que revise.
UMBRAL_REVISION = 0.15

VERSION_MOTOR = 2


def redondear5(x: float) -> int:
    """Multiplo de 5 mas cercano; los .5 exactos van al par (142.5->140,
    247.5->250), que es lo que cuadra con los ejemplos de la spec."""
    return int(round(x / 5.0)) * 5


def _banda_peri(hc_totales: float) -> int:
    for limite, peri in BANDAS_PERI:
        if hc_totales <= limite:
            return peri
    return BANDAS_PERI[-1][1]


def _grasa_por_dieta(grasa_reportada: float) -> int:
    """Paso 5 del doc: la grasa de partida sale de la que ya viene comiendo."""
    for limite, grasa in TRAMOS_GRASA_POR_DIETA:
        if grasa_reportada <= limite:
            return grasa
    return TRAMOS_GRASA_POR_DIETA[-1][1]


def _nivelar_descanso(hc_entreno: float, hc_descanso: float) -> tuple:
    """
    Regla dura: los hidratos del dia de descanso NUNCA por encima de los del dia de entreno
    (comparando comidas contra comidas, el peri va aparte). Si se pasa, se sube el ENTRENO
    hasta igualar; nunca se baja el descanso, porque la subida del descanso viene de un motivo
    real (el deporte extra de ese dia).
    """
    if hc_descanso > hc_entreno:
        return hc_descanso, hc_descanso
    return hc_entreno, hc_descanso


def _acotar_a_la_tabla(total: float, T: float) -> tuple:
    """La dieta que trae puede mover el total, pero no llevarselo.

    `total` es lo que sale de aplicar la matriz a su dieta (X, el 75 % de X, X-10...) y
    `T` lo que dice la tabla ya modificada. El resultado se queda a +-TOPE_DIETA_REPORTADA
    de T.

    Devuelve (total_acotado, cuanto_se_recorto). Si no se recorto, lo segundo es None.
    """
    if not T or T <= 0:
        return total, None
    techo = T * (1 + TOPE_DIETA_REPORTADA)
    suelo = T * (1 - TOPE_DIETA_REPORTADA)
    if total > techo:
        return techo, f"+{TOPE_DIETA_REPORTADA:.0%}"
    if total < suelo:
        return suelo, f"-{TOPE_DIETA_REPORTADA:.0%}"
    return total, None


def calcular_macros_v2(
    peso: float,
    sexo: str,
    porcentaje_graso: float,
    objetivo: str,
    # Las cuatro de la pantalla 5 del documento de textos. Solo 'muy_activo' suma: las otras
    # tres estan para que el cliente se reconozca y no se suba de categoria por no encontrarse.
    actividad_diaria: Optional[str] = None,   # 'sedentario'|'normal'|'moderado'|'muy_activo'
    deporte_extra: Optional[bool] = None,
    facilidad_engordar: Optional[str] = None,  # 'enseguida' | 'normal' | 'casi_no'
    dieta_reportada: Optional[Dict] = None,    # {'hc_entreno': g, 'grasa_entreno': g|None, 'texto': str}
    farmacologia: bool = False,
    historial_dietas: Optional[str] = None,    # solo se registra, no se aplica
    como_va: Optional[str] = None,             # P8: como le esta funcionando la dieta que trae
) -> Dict:
    """Los 8 numeros del metodo con la spec v2 encima de la tabla.

    Devuelve {base, macros, desglose, revision, no_aplicados, version_motor}.
    """
    base = calcular_targets(peso, sexo, porcentaje_graso, objetivo)
    sexo_norm = base["input"]["sexo"]
    obj_norm = base["input"]["objetivo"]
    bm = base["macros"]

    pr_e = bm["entreno"]["proteina"]
    hc_e = bm["entreno"]["hidratos"]
    gr_e = bm["entreno"]["grasa"]
    pr_pe = bm["perientreno"]["proteina"]
    hc_pe = bm["perientreno"]["hidratos"]
    pr_d = bm["descanso"]["proteina"]
    hc_d = bm["descanso"]["hidratos"]
    gr_d = bm["descanso"]["grasa"]

    desglose: List[Dict] = [{
        "paso": "tabla",
        "detalle": f"{sexo_norm} {base['lookup']['peso_snap']:.0f} kg / {base['lookup']['bf_snap']:.0f}% {obj_norm}",
        "valores": {"pr_e": pr_e, "hc_e": hc_e, "gr_e": gr_e, "pr_pe": pr_pe,
                    "hc_pe": hc_pe, "pr_d": pr_d, "hc_d": hc_d, "gr_d": gr_d},
    }]
    no_aplicados: Dict = {}

    # Se ha salido de la tabla: se le está dando la fila del extremo, no la suya. El
    # número es el mismo de siempre -- no hay otra fila que usar -- pero deja de ser
    # silencioso: el coach tiene que saber que ese cálculo se apoya en un tope.
    fuera_de_tabla = base["lookup"].get("fuera_de_tabla") or []
    for aviso in fuera_de_tabla:
        desglose.append({"paso": "fuera_de_tabla", "estado": "tope",
                         "detalle": aviso["detalle"]})

    # -----------------------------------------------------
    # 1) Modificadores de hidratos (sumados, luego topes y veto)
    # -----------------------------------------------------
    pct_e = 0.0
    pct_d = 0.0

    if actividad_diaria == "muy_activo":
        pct_e += MOD_MUY_ACTIVO_ENTRENO
        pct_d += MOD_MUY_ACTIVO_DESCANSO
        desglose.append({"paso": "muy_activo", "estado": "aplicado",
                         "detalle": "+10% HC entreno y descanso"})

    if deporte_extra:
        mod_dep = (MOD_DEPORTE_EXTRA_DESCANSO_VOLUMEN if obj_norm == "volumen"
                   else MOD_DEPORTE_EXTRA_DESCANSO_DEFINICION)
        pct_d += mod_dep
        desglose.append({"paso": "deporte_extra", "estado": "aplicado",
                         "detalle": f"+{mod_dep:.0%} HC solo descanso ({obj_norm})"})

    if facilidad_engordar in RESPUESTAS_QUE_SUBEN:
        umbral = BF_MAX_NO_ENGORDA.get(sexo_norm, BF_MAX_NO_ENGORDA["hombre"])
        if sexo_norm == "mujer" and not APLICAR_ENGORDA_EN_MUJERES:
            no_aplicados["engorda_mujer"] = facilidad_engordar
            desglose.append({"paso": "no_engorda", "estado": "no_aplica_mujer",
                             "detalle": "Modificador sin validar en mujeres: se guarda, no se aplica"})
        elif porcentaje_graso <= umbral:
            pct_e += MOD_NO_ENGORDA
            pct_d += MOD_NO_ENGORDA
            desglose.append({"paso": "no_engorda", "estado": "aplicado",
                             "detalle": f"+20% HC entreno y descanso ('{facilidad_engordar}' con grasa <= {umbral:.0f}%)"})
        else:
            desglose.append({"paso": "no_engorda", "estado": "no_aplica_bf",
                             "detalle": f"Requiere grasa <= {umbral:.0f}%"})

    if facilidad_engordar == "enseguida" and (pct_e > 0 or pct_d > 0):
        desglose.append({"paso": "veto_engorda_enseguida", "estado": "vetado",
                         "detalle": f"Anuladas subidas de HC (+{pct_e:.0%} entreno, +{pct_d:.0%} descanso)"})
        pct_e = 0.0
        pct_d = 0.0

    if historial_dietas and not APLICAR_HISTORIAL_DIETA:
        no_aplicados["historial_dietas"] = historial_dietas
        desglose.append({"paso": "historial_dietas", "estado": "no_aplicado",
                         "detalle": "El +-10% por historial esta en pausa: se guarda, no se aplica"})

    if pct_e > TOPE_SUBIDA_ENTRENO or pct_d > TOPE_SUBIDA_DESCANSO:
        desglose.append({"paso": "tope", "estado": "recortado",
                         "detalle": f"Tope +{TOPE_SUBIDA_ENTRENO:.0%} entreno / +{TOPE_SUBIDA_DESCANSO:.0%} descanso"})
    pct_e = min(pct_e, TOPE_SUBIDA_ENTRENO)
    pct_d = min(pct_d, TOPE_SUBIDA_DESCANSO)

    hc_e = hc_e * (1 + pct_e)
    hc_d = hc_d * (1 + pct_d)

    # Regla dura del doc 29-07: el descanso nunca por encima del entreno. Se comprueba aqui,
    # justo despues de las subidas, porque el +20% de deporte extra en volumen puede dejar el
    # dia de descanso por encima del de entreno.
    hc_e_antes = hc_e
    hc_e, hc_d = _nivelar_descanso(hc_e, hc_d)
    if hc_e > hc_e_antes:
        desglose.append({"paso": "nivelar_descanso", "estado": "aplicado",
                         "detalle": f"El descanso ({hc_d:.0f} g) superaba al entreno ({hc_e_antes:.0f} g): se sube el entreno para igualarlo"})

    # -----------------------------------------------------
    # 2) Excepcion proteina: farmacologia / TRT (+10 g SOLO descanso)
    # -----------------------------------------------------
    if farmacologia:
        if APLICAR_FARMACOLOGIA:
            pr_d = pr_d + MOD_FARMACOLOGIA_PROTEINA_DESCANSO_G
            desglose.append({"paso": "farmacologia", "estado": "aplicado",
                             "detalle": f"+{MOD_FARMACOLOGIA_PROTEINA_DESCANSO_G:.0f} g de proteina solo en descanso"})
            # Regla dura del doc 03-08: la proteina de entreno + peri tiene que quedar POR ENCIMA
            # de la de descanso. Si la subida la rompe, se suben los mismos 10 g en entreno.
            if pr_e + pr_pe <= pr_d:
                pr_e = pr_e + MOD_FARMACOLOGIA_PROTEINA_DESCANSO_G
                desglose.append({"paso": "farmacologia_nivelar_entreno", "estado": "aplicado",
                                 "detalle": (f"Entreno + peri ({pr_e - MOD_FARMACOLOGIA_PROTEINA_DESCANSO_G:.0f} + {pr_pe:.0f}) "
                                             f"ya no superaba al descanso ({pr_d:.0f}): "
                                             f"+{MOD_FARMACOLOGIA_PROTEINA_DESCANSO_G:.0f} g tambien en entreno")})
        else:
            no_aplicados["farmacologia"] = True
            desglose.append({"paso": "farmacologia", "estado": "no_aplicado",
                             "detalle": "TRT: pendiente de que Jesus confirme la regla. Se guarda, no se aplica"})

    # HC de entreno recomendados (comidas + peri) tras modificadores: es la
    # referencia contra la que se compara la dieta reportada.
    hc_recomendados = hc_e + hc_pe

    # -----------------------------------------------------
    # 3) Dieta reportada (pisa los hidratos; proteina siempre la de tabla)
    # -----------------------------------------------------
    revision = None
    hc_rep = None
    if dieta_reportada and dieta_reportada.get("hc_entreno") is not None:
        hc_rep = float(dieta_reportada["hc_entreno"])
        grasa_rep = dieta_reportada.get("grasa_entreno")
        grasa_rep = float(grasa_rep) if grasa_rep is not None else None

        # X = hidratos de entreno + peri que reporta. T = los mismos de la tabla ya modificada.
        X = hc_rep
        T = hc_recomendados
        matriz = MATRIZ_DEFINICION if obj_norm == "definicion" else MATRIZ_VOLUMEN
        # Sin la respuesta de "como te esta funcionando" no se puede decidir: se trata como el
        # caso neutro ("me mantengo"), que es el que menos supone.
        clave = como_va if como_va in matriz else "mantengo"
        if como_va and como_va not in matriz:
            no_aplicados["como_va_desconocido"] = como_va
        # En definicion la columna es X > T o X < T; los empates cuentan como "no se pasa".
        columna = 0 if X > T else 1
        accion = matriz[clave][columna]

        if obj_norm == "definicion" and hc_rep < UMBRAL_HC_EN_LAS_ULTIMAS:
            # Llega "en las ultimas": arranque minimo, se sube en el siguiente ajuste
            hc_e, gr_e = 60.0, 50.0
            hc_pe = float(PERI_EN_LAS_ULTIMAS)
            hc_d, gr_d = 50.0, 60.0
            desglose.append({"paso": "dieta_reportada", "rama": "def_ultimas",
                             "detalle": f"Reporta {hc_rep:.0f} g de HC (<{UMBRAL_HC_EN_LAS_ULTIMAS}): arranque 60/50, peri 15, descanso 50/60"})

        elif accion == "tabla":
            # Manda la tabla: no se toca nada de lo que ya venia de los modificadores.
            desglose.append({"paso": "dieta_reportada", "rama": "manda_la_tabla",
                             "detalle": f"'{clave}' con X={X:.0f} {'>' if columna == 0 else '<='} T={T:.0f}: se queda la tabla"})

        elif obj_norm == "definicion" and columna == 1:
            # X < T en definicion: come por debajo de la tabla. Arranque atado por el doc.
            total = X - 10 if accion == "x_-10" else X
            total, recorte = _acotar_a_la_tabla(total, T)
            hc_pe = float(PERI_EN_LAS_ULTIMAS)          # peri 15
            hc_e = total - hc_pe                       # el resto, a las comidas del entreno
            hc_d = hc_e * DESCANSO_SOBRE_COMIDAS       # descanso, un 20% por debajo
            gr_e, gr_d = 50.0, 60.0                    # excepcion de grasa del doc
            desglose.append({"paso": "dieta_reportada", "rama": "def_por_debajo",
                             "detalle": f"'{clave}' con X={X:.0f} < T={T:.0f}: {'X-10' if accion == 'x_-10' else 'X'} = {total:.0f}, peri 15, comidas {hc_e:.0f}, descanso -20%, grasa 50/60"})
            if recorte:
                desglose.append({"paso": "tope_dieta", "estado": "recortado",
                                 "detalle": f"Su dieta se iba mas de un {TOPE_DIETA_REPORTADA:.0%} por debajo de la tabla ({T:.0f} g): se queda en {total:.0f}"})

        else:
            # Se le pone X (entero, al 75% o menos 10) y el peri sale de X por banda.
            if accion == "x_75":
                total = X * 0.75
            elif accion == "x_-10":
                total = X - 10
            else:
                total = X
            total, recorte = _acotar_a_la_tabla(total, T)
            peri = _banda_peri(total)
            hc_pe = float(peri)
            hc_e = total - peri
            hc_d = hc_e * DESCANSO_SOBRE_COMIDAS
            desglose.append({"paso": "dieta_reportada", "rama": f"se_le_pone_{accion}",
                             "detalle": f"'{clave}' con X={X:.0f} vs T={T:.0f}: total {total:.0f}, peri {peri} por banda, comidas {hc_e:.0f}, descanso -20%"})
            if recorte:
                desglose.append({"paso": "tope_dieta", "estado": "recortado",
                                 "detalle": (f"Su dieta se iba mas de un {TOPE_DIETA_REPORTADA:.0%} de la tabla "
                                             f"({T:.0f} g): se queda en {total:.0f} ({recorte})")})

        # Paso 5 del doc: la grasa de partida sale de la que ya viene comiendo. La excepcion
        # (definicion por debajo de la tabla, que va 50/60) ya se ha fijado arriba.
        if grasa_rep is not None and not (obj_norm == "definicion" and columna == 1):
            g = float(_grasa_por_dieta(grasa_rep))
            gr_e = gr_d = g
            desglose.append({"paso": "grasa_por_dieta", "estado": "aplicado",
                             "detalle": f"Viene comiendo {grasa_rep:.0f} g de grasa: se fija en {g:.0f} en entreno y descanso"})

        # La regla dura se vuelve a comprobar: X puede dejar el entreno por debajo del descanso.
        hc_e, hc_d = _nivelar_descanso(hc_e, hc_d)

        diferencia = hc_rep - hc_recomendados
        diferencia_pct = abs(diferencia) / hc_recomendados if hc_recomendados else 0.0
        revision = {
            "requiere_revision": diferencia_pct > UMBRAL_REVISION,
            "hc_reportados": hc_rep,
            "hc_recomendados": redondear5(hc_recomendados),
            "diferencia": redondear5(diferencia),
            "diferencia_pct": round(diferencia_pct, 3),
            "umbral": UMBRAL_REVISION,
        }

    # -----------------------------------------------------
    # 4) Suelos
    # -----------------------------------------------------
    suelos_activados = []
    suelo_pr = SUELO_PROTEINA_ENTRENO[sexo_norm]
    if pr_e < suelo_pr:
        pr_e = float(suelo_pr)
        suelos_activados.append(f"proteina entreno {suelo_pr}")
    if hc_e < SUELO_HC_COMIDAS_ENTRENO:
        hc_e = float(SUELO_HC_COMIDAS_ENTRENO)
        suelos_activados.append(f"HC comidas entreno {SUELO_HC_COMIDAS_ENTRENO}")
    if hc_d < SUELO_HC_DESCANSO:
        hc_d = float(SUELO_HC_DESCANSO)
        suelos_activados.append(f"HC descanso {SUELO_HC_DESCANSO}")
    if gr_e < SUELO_GRASA:
        gr_e = float(SUELO_GRASA)
        suelos_activados.append(f"grasa entreno {SUELO_GRASA}")
    if gr_d < SUELO_GRASA:
        gr_d = float(SUELO_GRASA)
        suelos_activados.append(f"grasa descanso {SUELO_GRASA}")
    if suelos_activados:
        desglose.append({"paso": "suelos", "estado": "aplicado", "activados": suelos_activados})

    # -----------------------------------------------------
    # 5) Redondeo a multiplo de 5 (siempre el ultimo paso)
    # -----------------------------------------------------
    macros = {
        "entreno": {"proteina": redondear5(pr_e), "hidratos": redondear5(hc_e), "grasa": redondear5(gr_e)},
        "perientreno": {"proteina": redondear5(pr_pe), "hidratos": redondear5(hc_pe)},
        "descanso": {"proteina": redondear5(pr_d), "hidratos": redondear5(hc_d), "grasa": redondear5(gr_d)},
    }

    return {
        "base": base,
        "macros": macros,
        "kcal": {
            "entreno": macros["entreno"]["proteina"] * 4 + macros["entreno"]["hidratos"] * 4 + macros["entreno"]["grasa"] * 9,
            "descanso": macros["descanso"]["proteina"] * 4 + macros["descanso"]["hidratos"] * 4 + macros["descanso"]["grasa"] * 9,
        },
        "desglose": desglose,
        "revision": revision,
        "no_aplicados": no_aplicados,
        # Suelto y no solo dentro del desglose: quien enseña esto no tiene que rebuscar
        # entre quince pasos para saber si el cálculo se apoya en un tope de la tabla.
        "fuera_de_tabla": fuera_de_tabla,
        "version_motor": VERSION_MOTOR,
    }


def multiplicadores_de(resultado: Dict) -> Dict:
    """Multiplicadores por masa de trabajo sobre los macros FINALES del motor
    (mismas claves que target_calculator, para macros_multiplicadores)."""
    mt = resultado["base"]["derivacion"]["masa_trabajo"]
    if not mt:
        return {}
    m = resultado["macros"]
    return {
        "pr_entreno": round(m["entreno"]["proteina"] / mt, 4),
        "hc_entreno": round(m["entreno"]["hidratos"] / mt, 4),
        "gr_entreno": round(m["entreno"]["grasa"] / mt, 4),
        "pr_perientreno": round(m["perientreno"]["proteina"] / mt, 4),
        "hc_perientreno": round(m["perientreno"]["hidratos"] / mt, 4),
        "pr_descanso": round(m["descanso"]["proteina"] / mt, 4),
        "hc_descanso": round(m["descanso"]["hidratos"] / mt, 4),
        "gr_descanso": round(m["descanso"]["grasa"] / mt, 4),
    }


def ajustes_to_kwargs(ajustes: Optional[Dict]) -> Dict:
    """Convierte el dict AjustesMacros (preguntas 5-8 del quiz) en los kwargs
    del motor. Tolera None y claves ausentes (perfil sin ajustes guardados)."""
    a = ajustes or {}
    dieta = None
    # La dieta que trae el cliente solo entra si la CONFIRMO (doc 29-07: "este dato manda por
    # encima de todo lo demas, asi que no puede entrar sin confirmar"). Los registros antiguos
    # no tienen el campo; para no cambiarles el calculo, la ausencia se trata como confirmada.
    confirmada = a.get("dieta_confirmada")
    # Trae una dieta de la que partir solo quien la mide (`True`) o se cuida sin medirla
    # (`parecido`). Las otras dos respuestas del documento de textos -- "sin control pero no
    # como mal" (`False`) y "como mal y desorganizado" -- no traen nada que copiar. Se
    # comprueba por valor y no con un `if a.get("sigue_dieta")` a secas, porque en Python
    # cualquier texto cuenta como verdadero y "desorganizado" habria colado como si trajera
    # una dieta medida.
    trae_dieta = a.get("sigue_dieta") is True or a.get("sigue_dieta") == "parecido"
    if trae_dieta and a.get("dieta_hc_entreno") is not None and confirmada is not False:
        dieta = {
            "hc_entreno": a.get("dieta_hc_entreno"),
            "grasa_entreno": a.get("dieta_grasa_entreno"),
            "texto": a.get("dieta_texto"),
        }
    return {
        "actividad_diaria": a.get("actividad_diaria"),
        "deporte_extra": a.get("deporte_extra"),
        "facilidad_engordar": a.get("facilidad_engordar"),
        "dieta_reportada": dieta,
        "historial_dietas": a.get("historial_dietas"),
        "como_va": a.get("como_va"),
    }
