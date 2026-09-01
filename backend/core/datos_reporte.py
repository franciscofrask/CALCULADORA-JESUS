"""
EL DATO QUE VA ANTES DE LA PREGUNTA (reglas 3 y 5 del doc 16-08).

"Primero el dato, después la pregunta. Si la app ya sabe algo, se lo dice; solo se
pregunta lo que no se puede saber."

Aquí se calcula todo lo que el reporte enseña ya masticado -- los días que registró la
dieta, los entrenos que hizo de los que tenía, el cardio, la energía de sus cierres -- y
qué bloques le tocan a ESE cliente. El formulario solo pinta.

Dos criterios que conviene no perder de vista:

  - El plan es un dato, nunca un nombre. Lo que decide los bloques son las
    `habilitaciones` de su plan (¿tiene quincenal?, ¿qué rutina lleva?), no la cadena
    "gold"/"silver"/"bronze": hay clientes con esos nombres y con nivel1/2/3, y los
    legacy se van a ir renombrando.
  - Lo que no se sabe no se cuenta. Un día sin macros resueltos no es un día mal
    cuadrado: se queda fuera del recuento y el reporte no dice nada de él.
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from core.database import db

# El margen de la calculadora (`calma_suggest.MARGEN_VALIDO`, los 4 g de Calma). Un día
# "cuadrado" aquí es lo mismo que enseña Nutrición: los tres macros dentro del margen.
# Se junta "cuadrado" y "válido" a propósito -- el doc dice "Cuadraste los macros 19
# días", y para el cliente un día dentro del margen es un día cuadrado.
from calma_suggest import MARGEN_VALIDO

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre")


def fecha_larga(iso: Optional[str]) -> Optional[str]:
    """"10 de agosto", que es como lo dice el doc. None si no hay fecha."""
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(str(iso)[:10]).date()
    except (ValueError, TypeError):
        return None
    return f"{d.day} de {MESES[d.month - 1]}"


def _dia_y_mes(iso: str, con_mes: bool) -> str:
    """"26" o "26 de agosto", segun haga falta desambiguar el mes."""
    d = datetime.fromisoformat(str(iso)[:10]).date()
    return f"{d.day} de {MESES[d.month - 1]}" if con_mes else str(d.day)


def _kilos(valor: Any) -> str:
    """«80 kg», «80,5 kg». El cero de mas no aporta nada y se lee peor."""
    texto = f"{float(valor):.1f}"
    if texto.endswith(".0"):
        texto = texto[:-2]
    return f"{texto.replace('.', ',')} kg"


def de_donde_sale_el_peso(ps: Optional[Dict[str, Any]]) -> Optional[str]:
    """La linea que va debajo del peso del reporte: de donde ha salido el numero.

    Jesus no escribio este texto -- el punto 34 del doc del 24-08 solo decide la regla --,
    asi que es la forma acordada con Francisco: la frase dice la cuenta y las fechas, y
    nada mas. El campo sigue siendo editable, y si el cliente lo cambia manda el suyo: por
    eso la linea explica el numero puesto, no lo defiende.

    LOS KILOS SOLO EN LA RAMA «ultimo» (fallo 6 del repaso del 24-08). En las ramas «pareja»
    y «media» el numero ya esta escrito en la casilla, asi que repetirlo aqui es decir dos
    veces lo mismo. En la rama «ultimo» NO: ese peso no es de esta semana y por eso la
    casilla se deja vacia a proposito, de modo que esta frase es el unico sitio donde el
    cliente puede ver cuanto pesaba. Sin los kilos se le pedia el peso sin recordarle el
    suyo, que es justo lo que hacia la linea «Ultimo registro: 80 kg, el 24 de agosto» de
    antes. Le pasa al 13,94 % de las semanas-cliente en produccion (8,65 % en los Premium).
    """
    if not ps or ps.get("valor") is None:
        return None
    fechas = ps.get("fechas") or []
    try:
        if ps.get("regla") == "pareja" and len(fechas) == 2:
            # El mes solo se nombra cuando la pareja lo cruza (31 de agosto y 1 de
            # septiembre); dentro del mismo mes, "del 26 y el 27" se lee mejor.
            cruza = str(fechas[0])[:7] != str(fechas[1])[:7]
            return (f"La media de tus pesajes del {_dia_y_mes(fechas[0], cruza)} y "
                    f"el {_dia_y_mes(fechas[1], True)}")
        if ps.get("regla") == "media":
            if len(fechas) == 1:
                return f"Tu peso del {_dia_y_mes(fechas[0], True)}"
            return f"La media de tus {len(fechas)} pesajes de esta semana"
        return (f"Tu último peso: {_kilos(ps['valor'])}, "
                f"del {_dia_y_mes(ps.get('fecha'), True)}")
    except (ValueError, TypeError, IndexError):
        return None


def _dias(d0: date, d1: date) -> List[str]:
    """Los días del periodo, en ISO, del primero al último incluidos."""
    return [(d0 + timedelta(days=n)).isoformat() for n in range((d1 - d0).days + 1)]


def _pct(hechos: float, total: float) -> Optional[int]:
    return int(round(100 * hechos / total)) if total else None


# ─────────────────────────────────────────────────────────────────────────────
# QUÉ BLOQUES LE TOCAN
# ─────────────────────────────────────────────────────────────────────────────

def perfil_de_reporte(habilitaciones: Optional[Dict[str, Any]]) -> str:
    """Cuál de los tres reportes mensuales le toca, LEYENDO SUS HABILITACIONES.

    El doc los llama Gold, Silver y Bronze porque son los planes que se los llevan hoy,
    pero lo que los distingue es lo que incluye el plan:

      - completo   quien tiene reporte quincenal: lleva entrenador encima, así que se le
                   pregunta por lesiones y por el cardio, y su entreno está registrado.
      - con_rutina quien no tiene quincenal pero sí rutina (personalizada o del mes): se
                   le confirman los días que no rellenó y se le pregunta qué tal el mes.
      - sin_rutina quien no lleva rutina en su plan: ahí va la pregunta de regularidad y
                   la rutina del mes, que es la única oferta de todo el reporte.
    """
    hab = habilitaciones or {}
    if "quincenal" in (hab.get("reportes") or []):
        return "completo"
    return "con_rutina" if hab.get("rutina") in ("personalizada", "del_mes") else "sin_rutina"


def bloques_del_mensual(perfil_rep: str, pedir_grasa: bool = False) -> List[str]:
    """Los bloques del mensual, en el orden del doc y con su numeración por plan.

    Gold 13, los otros dos 11: los que se caen son lesiones y cardio, que no van en su
    plan, y en el que no lleva rutina el bloque de entreno cambia entero.

    Y uno más cada doce semanas: el % de grasa. La pantalla del alta se lo promete al pie
    («lo repetiremos cada 12 semanas») y hasta hoy no había NINGÚN sitio donde se le
    volviera a pedir. Va detrás del peso, que es cuando está mirándose los números.
    """
    bloques = ["peso"]
    if pedir_grasa:
        bloques.append("grasa")
    bloques += ["medidas", "fotos", "dieta", "entreno"]
    if perfil_rep == "completo":
        bloques += ["lesiones", "cardio"]
    bloques += ["suplementacion", "energia", "valoracion", "objetivo", "libre", "sugerencias"]
    return bloques


# ─────────────────────────────────────────────────────────────────────────────
# LA DIETA: "25 de 28 días · 89 %" y "Cuadraste los macros 19 días"
# ─────────────────────────────────────────────────────────────────────────────

async def datos_dieta(perfil: Dict[str, Any], d0: date, d1: date) -> Dict[str, Any]:
    """Los días que registró y cómo le salieron.

    "Registrado" es que ese día tenga comida apuntada, no que exista el documento: los
    días vacíos se crean solos al abrir Nutrición y contarlos sería regalarle un 100 %.
    """
    from calma_suggest import macros_efectivos as _efectivos
    from macro_distribution import leer_macro
    from macros_por_fecha import resolver

    dias_periodo = len(_dias(d0, d1))
    dietas = await db.diets.find(
        {"user_id": perfil.get("user_id"),
         "fecha": {"$gte": d0.isoformat(), "$lte": d1.isoformat()}},
        {"_id": 0, "fecha": 1, "tipo_dia": 1, "comidas": 1},
    ).to_list(400)

    # Los alimentos de todo el periodo en una sola consulta al catálogo: `macros_efectivos`
    # falta en la mayoría de los alimentos guardados, así que hay que recalcularlos, y
    # hacerlo día a día serían 28 consultas.
    ids = {a.get("alimento_id")
           for d in dietas
           for m in (d.get("comidas") or {}).values()
           for a in (m.get("alimentos") or [])
           if a.get("alimento_id") is not None}
    catalogo: Dict[Any, Dict[str, Any]] = {}
    if ids:
        async for f in db.foods.find({"id": {"$in": list(ids)}}, {"_id": 0}):
            catalogo[f["id"]] = f

    registrados, cuadrados, corto_proteina = 0, 0, 0
    for dieta in dietas:
        total = {"P": 0.0, "H": 0.0, "G": 0.0}
        for comida in (dieta.get("comidas") or {}).values():
            for a in (comida or {}).get("alimentos") or []:
                me = a.get("macros_efectivos")
                if not (me and any((me.get(r) or 0) > 0 for r in ("P", "H", "G"))):
                    food = catalogo.get(a.get("alimento_id"))
                    try:
                        me = _efectivos(food, float(a.get("cantidad_g") or 0)) if food else (me or {})
                    except Exception:      # noqa: BLE001 · un alimento raro no tumba el mes
                        me = me or {}
                for r in ("P", "H", "G"):
                    total[r] += float((me or {}).get(r) or 0)

        if not any(v > 0 for v in total.values()):
            continue                      # día abierto y sin nada dentro: no está registrado
        registrados += 1

        # El objetivo de ESE día, con los macros que estaban vigentes entonces (nunca los
        # de hoy: en un mes puede haber habido un ajuste por medio).
        training, rest, _peri = await resolver(db, perfil, dieta.get("fecha"))
        doc = rest if dieta.get("tipo_dia") == "descanso" else training
        objetivo = {
            "P": leer_macro(doc, "protein", "proteinas"),
            "H": leer_macro(doc, "carbs", "hidratos"),
            "G": leer_macro(doc, "fat", "grasas"),
        }
        if not any(v > 0 for v in objetivo.values()):
            continue                      # sin objetivo no se juzga el día

        # EL DÍA CUADRA COMO CUADRA EN NUTRICIÓN, no con una regla propia del reporte.
        #
        # Margen de ±4 g en los tres (decisión de Francisco, 16-08), y la proteína cuenta
        # como hecha en cuanto está CUBIERTA: pasarse de proteína no es un fallo (Jesús,
        # 13-08), y por eso tampoco puede descontar un día aquí. Contándolo de otra forma,
        # el «cuadraste los macros N días» del reporte no coincidía con los días verdes que
        # el cliente ve en su calendario, sobre exactamente los mismos datos.
        proteina_hecha = total["P"] - objetivo["P"] >= -MARGEN_VALIDO
        resto_cuadrado = all(abs(objetivo[r] - total[r]) <= MARGEN_VALIDO for r in ("H", "G"))
        if proteina_hecha and resto_cuadrado:
            cuadrados += 1
        elif objetivo["P"] - total["P"] > MARGEN_VALIDO:
            corto_proteina += 1

    return {
        "dias_periodo": dias_periodo,
        "dias_registrados": registrados,
        "pct": _pct(registrados, dias_periodo),
        "dias_cuadrados": cuadrados,
        "dias_corto_proteina": corto_proteina,
    }


# ─────────────────────────────────────────────────────────────────────────────
# EL ENTRENO Y EL CARDIO: de `workout_logs` contra los días de su rutina
# ─────────────────────────────────────────────────────────────────────────────

async def datos_entreno(perfil: Dict[str, Any], d0: date, d1: date) -> Dict[str, Any]:
    """"Has entrenado 14 de 16 días", la media de estrellas y los días sin confirmar.

    Los días que TENÍA salen de la rutina activa (qué días de la semana entrena), y los
    hechos de `workout_logs`, que es lo único que dice que entrenó de verdad. Sin rutina
    cargada no hay "de los que tenías": se devuelve `previstos: None` y quien lo pinta se
    calla el dato en vez de inventarse un denominador.
    """
    from routes.workout_logs import dia_de_rutina

    rutina = await db.routines.find_one(
        {"client_id": perfil.get("id"), "status": "active"}, {"_id": 0})
    logs = await db.workout_logs.find(
        {"client_id": perfil.get("id"),
         "fecha": {"$gte": d0.isoformat(), "$lte": d1.isoformat()}},
        {"_id": 0},
    ).to_list(200)
    por_fecha = {l.get("fecha"): l for l in logs}

    dias_entreno, dias_cardio = [], []
    for f in _dias(d0, d1):
        dia = dia_de_rutina(rutina, f)
        if not dia:
            continue
        if not (dia.get("exercises") or []) and dia.get("cardio"):
            dias_cardio.append(f)
        else:
            dias_entreno.append(f)
            if dia.get("cardio"):
                dias_cardio.append(f)

    def _hechos(fechas: List[str], tipo: str) -> List[str]:
        return [f for f in fechas
                if (por_fecha.get(f) or {}).get("hecho")
                and (por_fecha.get(f, {}).get("tipo") or "entreno") == tipo]

    entrenos_hechos = _hechos(dias_entreno, "entreno")
    cardios_hechos = _hechos(dias_cardio, "cardio") or [
        f for f in dias_cardio if (por_fecha.get(f) or {}).get("hecho")]

    estrellas = [int(l["estrellas"]) for l in logs
                 if l.get("hecho") and isinstance(l.get("estrellas"), int)]
    media = round(sum(estrellas) / len(estrellas), 1) if estrellas else None

    # Los días de rutina de los que la app no tiene NADA: ni "lo hice" ni "no lo hice".
    # Son los que se le confirman ("Te faltan 2 por confirmar · el 8 y el 14 de agosto").
    sin_registrar = [f for f in dias_entreno if f not in por_fecha]

    return {
        "tiene_rutina": bool(rutina),
        "previstos": len(dias_entreno) or None,
        "hechos": len(entrenos_hechos),
        "pct": _pct(len(entrenos_hechos), len(dias_entreno)),
        "media_estrellas": media,
        "sin_registrar": sin_registrar,
        "sin_registrar_labels": [fecha_larga(f) for f in sin_registrar],
        "cardio": {
            "previstas": len(dias_cardio) or None,
            "hechas": len(cardios_hechos),
            "pct": _pct(len(cardios_hechos), len(dias_cardio)),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# LOS CIERRES DEL DÍA: la energía y cuánto se movió
# ─────────────────────────────────────────────────────────────────────────────

async def datos_de_los_cierres(perfil: Dict[str, Any], d0: date, d1: date) -> Dict[str, Any]:
    """La energía del mes y los días que se movió menos de lo habitual.

    El bloque de energía del reporte SOLO sale si la lleva baja: la media de sus cierres
    por debajo de 3. Si va bien no se le pregunta nada, que es lo que pide el doc.
    """
    cierres = await db.checkins.find(
        {"client_id": perfil.get("id"), "type": "daily",
         "created_at": {"$gte": d0.isoformat(), "$lte": d1.isoformat() + "T23:59:59"}},
        {"_id": 0, "energy": 1, "movimiento": 1, "suplementos": 1},
    ).to_list(200)

    energias = [float(c["energy"]) for c in cierres
                if isinstance(c.get("energy"), (int, float))]
    media = round(sum(energias) / len(energias), 1) if energias else None
    dias_bajos = sum(1 for e in energias if e < 3)
    movio_menos = sum(1 for c in cierres if c.get("movimiento") == "menos")

    # LOS DÍAS DE SUPLEMENTACIÓN, PARA SABER SI HAY QUE PREGUNTARLE.
    #
    # En el documento del 1-09 la pregunta de suplementos es CONDICIONAL: «Las dos del
    # centro solo salen si falló». Sin este recuento no se puede decidir, y se le acababa
    # preguntando todos los meses «¿estás tomando la que te pauté?» a quien la toma todos
    # los días y ya lo ha marcado noche a noche.
    from core.actividad_mensual import cierres_del_periodo
    from core.plan_access import plan_grants_feature
    contados = cierres_del_periodo(
        cierres, len(_dias(d0, d1)),
        tiene_suplementacion=plan_grants_feature(perfil.get("plan"), "suplementacion"))

    return {
        "cierres": len(cierres),
        "energia_media": media,
        "dias_energia_baja": dias_bajos,
        # La condición del doc: la media por debajo de 3. Sin cierres no hay dato y el
        # bloque no sale: preguntarle por una energía que no ha marcado no lleva a nada.
        "energia_baja": media is not None and media < 3,
        "dias_movio_menos": movio_menos,
        "suplementacion": contados["suplementacion"],
        "dias_periodo": len(_dias(d0, d1)),
    }


# ─────────────────────────────────────────────────────────────────────────────
# LAS LESIONES: lo que ya contó
# ─────────────────────────────────────────────────────────────────────────────

def lesiones_del_perfil(perfil: Dict[str, Any]) -> List[Dict[str, Any]]:
    """"LO QUE YA ME CONTASTE": las lesiones abiertas, con sus ejercicios vetados.

    La estructura buena es `client_profiles.lesiones` [{zona, desde, estado_mes,
    ejercicios_vetados}], que la escribe el propio reporte. Mientras un cliente no haya
    mandado ninguno, se rellena con `injuries` -- la lista de toda la vida que edita el
    entrenador en la ficha --, que es texto suelto: así el primer reporte ya sale con lo
    que sabemos de él en vez de en blanco.

    Las superadas no vuelven a salir: se preguntan una vez y se cierran.
    """
    lesiones = perfil.get("lesiones")
    if isinstance(lesiones, list) and lesiones:
        return [
            {
                "zona": l.get("zona"),
                "desde": l.get("desde"),
                "ejercicios_vetados": l.get("ejercicios_vetados") or [],
            }
            for l in lesiones
            if isinstance(l, dict) and l.get("zona") and l.get("estado_mes") != "superada"
        ]
    viejas = perfil.get("injuries")
    if isinstance(viejas, list):
        return [{"zona": str(t).strip(), "desde": None, "ejercicios_vetados": []}
                for t in viejas if str(t).strip()]
    return []


# ─────────────────────────────────────────────────────────────────────────────
# TODO JUNTO
# ─────────────────────────────────────────────────────────────────────────────

async def datos_del_reporte(perfil: Dict[str, Any], tipo: str,
                            d0: date, d1: date) -> Dict[str, Any]:
    """Lo que el formulario necesita saber antes de preguntar nada.

    El quincenal solo necesita el entreno y el último peso: sus otras tres preguntas no
    salen de ningún dato. El mensual los necesita todos.
    """
    from core.series_cliente import actual, peso_semanal

    peso = actual(perfil.get("pesos"))
    # EL PESO DE LA SEMANA, YA HECHO (punto 34 del doc del 24-08). Va en TODOS los reportes:
    # «el campo es idéntico para los cinco planes, sólo cambian los avisos». La semana es la
    # del ÚLTIMO día del periodo, que es la que el cliente está cerrando cuando rellena.
    #
    # Se calcula aquí y no en la pantalla porque la regla es una cascada de tres ramas y el
    # formulario tiene que poder decir de cuál sale sin volver a razonarla.
    semanal = peso_semanal(perfil.get("pesos"), d1)
    datos: Dict[str, Any] = {
        "periodo": {"desde": d0.isoformat(), "hasta": d1.isoformat()},
        "peso_ultimo": ({"valor": peso["valor"], "fecha": peso["fecha"],
                         "fecha_label": fecha_larga(peso["fecha"])} if peso else None),
        "peso_semanal": ({**semanal,
                          "fecha_label": fecha_larga(semanal["fecha"]),
                          "de_donde": de_donde_sale_el_peso(semanal)} if semanal else None),
        "entreno": await datos_entreno(perfil, d0, d1),
    }
    if tipo != "mensual":
        return datos

    datos["dieta"] = await datos_dieta(perfil, d0, d1)
    datos["cierres"] = await datos_de_los_cierres(perfil, d0, d1)
    datos["lesiones"] = lesiones_del_perfil(perfil)
    # «Estos son los que me diste»: las máquinas que dijo que no tiene, para que el mes que
    # viene salgan puestas y solo tenga que corregir lo que haya cambiado (doc 1-09).
    datos["maquinas"] = [m for m in (perfil.get("maquinas_no_disponibles") or [])
                         if str(m).strip()]
    return datos


# ─────────────────────────────────────────────────────────────────────────────
# LO QUE COMIÓ, DÍA A DÍA (documento «El informe del mes», 1-09-2026)
#
# Tres bloques del informe salen del mismo sitio, sus dietas guardadas: el día tipo, las
# preferencias de alimentos y los extras. Se leen de una vez porque son la misma consulta.
# ─────────────────────────────────────────────────────────────────────────────

async def comidas_y_extras_del_periodo(perfil: Dict[str, Any], d0: date,
                                       d1: date) -> Dict[str, Any]:
    """Las comidas aplanadas y los extras, listos para `core.informe_del_mes`.

    Devuelve `{"comidas": [...], "usos": [...], "extras": [...]}`:

      - `comidas`  una por comida y día, con sus alimentos y cantidades. De aquí sale «tu
                   día tipo».
      - `usos`     una por alimento y día, con sus macros. De aquí salen las preferencias.
      - `extras`   lo que apuntó fuera de la dieta, con su fecha.

    LOS DÍAS VACÍOS NO CUENTAN. Nutrición crea el documento del día al abrirlo, así que la
    base tiene dietas sin una sola comida dentro: contarlas diría que su día tipo es no
    comer nada.
    """
    from meal_moment import PERI, momento_de_comida

    dietas = await db.diets.find(
        {"user_id": perfil.get("user_id"),
         "fecha": {"$gte": d0.isoformat(), "$lte": d1.isoformat()}},
        {"_id": 0, "fecha": 1, "comidas": 1, "extras": 1, "num_comidas": 1,
         "single_meal": 1},
    ).to_list(400)

    # El catálogo de los alimentos usados, en una sola consulta: hace falta para saber si
    # un alimento se cuenta por unidades («1 yogur griego») y para los macros de los que no
    # los traen resueltos.
    ids = {a.get("alimento_id")
           for d in dietas
           for m in (d.get("comidas") or {}).values()
           for a in ((m or {}).get("alimentos") or [])
           if a.get("alimento_id") is not None}
    catalogo: Dict[Any, Dict[str, Any]] = {}
    if ids:
        async for f in db.foods.find({"id": {"$in": list(ids)}}, {"_id": 0}):
            catalogo[f["id"]] = f

    from calma_suggest import macros_efectivos as _efectivos

    comidas: List[Dict[str, Any]] = []
    usos: List[Dict[str, Any]] = []
    extras: List[Dict[str, Any]] = []

    for dieta in dietas:
        fecha = dieta.get("fecha")
        for e in (dieta.get("extras") or []):
            if (e.get("texto") or "").strip():
                extras.append({"fecha": e.get("fecha") or fecha, "texto": e["texto"]})

        num = int(dieta.get("num_comidas") or 4)
        unica = bool(dieta.get("single_meal"))
        for clave, comida in (dieta.get("comidas") or {}).items():
            alimentos = (comida or {}).get("alimentos") or []
            if not alimentos:
                continue
            items = []
            for a in alimentos:
                food = catalogo.get(a.get("alimento_id")) or {}
                nombre = (a.get("nombre") or food.get("name") or "").strip()
                if not nombre:
                    continue
                gramos = float(a.get("cantidad_g") or 0)
                # Por unidades cuando el alimento las tiene: «1 yogur griego» se entiende y
                # «125 g de yogur griego» hay que traducirlo.
                peso_ud = float(food.get("unit_weight") or food.get("peso_unidad") or 0)
                por_unidad = bool(food.get("por_unidad") or food.get("is_unit")) and peso_ud > 0
                items.append({
                    "nombre": nombre,
                    "cantidad": (round(gramos / peso_ud, 1) if por_unidad else gramos),
                    "unidad": "ud" if por_unidad else "g",
                })
                me = a.get("macros_efectivos")
                if not (me and any((me.get(r) or 0) > 0 for r in ("P", "H", "G"))):
                    try:
                        me = _efectivos(food, gramos) if food else {}
                    except Exception:      # noqa: BLE001 · un alimento raro no tumba el mes
                        me = {}
                usos.append({"nombre": nombre, "fecha": fecha, "macros": me or {}})

            if not items:
                continue
            momento = momento_de_comida(clave, num, unica)
            comidas.append({
                "clave": clave, "fecha": fecha, "items": items,
                "momento": momento, "es_peri": momento == PERI,
                # EL NOMBRE SALE DEL MOMENTO, NO DE LA CLAVE. Con tres comidas la C3 es la
                # cena y con cuatro es la merienda; llamarla siempre «Merienda» porque se
                # llama C3 le pondría la cena a media tarde.
                "nombre": (clave if momento == PERI
                           else NOMBRE_DE_COMIDA.get(momento) or clave),
            })

    return {"comidas": comidas, "usos": usos, "extras": extras}


# Cómo se llama cada comida en el informe. La app las numera («Comida 2») porque el reparto
# cambia de un día a otro; aquí se le habla de su día, y su día tiene un desayuno.
NOMBRE_DE_COMIDA = {
    "desayuno": "Desayuno", "comida": "Comida", "merienda": "Merienda", "cena": "Cena",
}


# ─────────────────────────────────────────────────────────────────────────────
# EL PASO 1 DEL MENSUAL (documento «El reporte mensual», 1-09-2026)
#
# «Sale de tus check-in. Si algo no cuadra o te falta, lo arreglas al final.»
#
# El paso 1 no pregunta: enseña. Y lo que enseña cambia entero con el selector de arriba
# -- «Desde tu último reporte» (28 días) o «Desde que empezaste» --, no solo el peso.
# ─────────────────────────────────────────────────────────────────────────────

def serie_de_pesos(perfil: Dict[str, Any], d0: Optional[date] = None,
                   d1: Optional[date] = None) -> List[Dict[str, Any]]:
    """Los pesajes del cliente, saneados y en orden, acotados al periodo si se pide.

    Sale de `client_profiles.pesos`, que es LA fuente del peso: la misma que pintan Mis
    macros y Evolución desde el 17-08. Coger el `weight` de cada reporte daba dos curvas
    distintas para el mismo cliente el mismo día.
    """
    from core.series_cliente import sanea_peso

    desde = d0.isoformat() if d0 else None
    hasta = d1.isoformat() if d1 else None
    puntos: List[Dict[str, Any]] = []
    for p in (perfil.get("pesos") or []):
        fecha, valor = str(p.get("fecha") or "")[:10], sanea_peso(p.get("valor"))
        if not fecha or valor is None:
            continue
        if (desde and fecha < desde) or (hasta and fecha > hasta):
            continue
        puntos.append({"fecha": fecha, "valor": valor})
    puntos.sort(key=lambda x: x["fecha"])
    return puntos


async def _circulos_del_peso(perfil: Dict[str, Any], d0: date, d1: date,
                             desde_el_principio: bool) -> Dict[str, Any]:
    """Los círculos de la curva y la frase que los explica.

    Dos lecturas distintas, y son del documento:

      - En los 28 días: «El círculo es el peso de tu quincenal». Uno solo, el del reporte
        intermedio, que es el único punto marcado de ese tramo.
      - En el programa entero: «Los círculos son tus reportes anteriores. El primero es tu
        cuestionario inicial».

    SIN REPORTES NO HAY CÍRCULOS NI FRASE. Explicar unos puntos que no están es peor que
    no decir nada: al que manda su primer mensual la curva le sale limpia y sin pie.
    """
    reportes = await db.reports.find(
        {"client_id": perfil.get("id"),
         "created_at": {"$gte": d0.isoformat(), "$lte": d1.isoformat() + "T23:59:59"}},
        {"_id": 0, "tipo": 1, "weight": 1, "created_at": 1},
    ).sort("created_at", 1).to_list(200)

    from core.series_cliente import sanea_peso
    puntos = [{"fecha": str(r.get("created_at") or "")[:10],
               "valor": sanea_peso(r.get("weight")),
               "que_es": "reporte"}
              for r in reportes]
    puntos = [p for p in puntos if p["fecha"] and p["valor"] is not None]

    if not desde_el_principio:
        # El quincenal del tramo. Si mandó más de uno, el último: es «tu quincenal», el que
        # tiene en la cabeza cuando abre el mensual.
        quincenales = [p for p, r in zip(puntos, reportes) if r.get("tipo") == "quincenal"]
        if not quincenales:
            return {"circulos": [], "nota": None}
        return {"circulos": quincenales[-1:],
                "nota": "El círculo es el peso de tu quincenal."}

    if not puntos:
        return {"circulos": [], "nota": None}

    # El primer círculo es el cuestionario inicial: el pesaje más antiguo de su serie, que
    # es el que dejó al darse de alta. No hay campo «peso inicial» en ninguna parte; el
    # panel lo saca igual, del primer punto de la curva (`routes/admin.py`).
    serie = serie_de_pesos(perfil)
    if serie and serie[0]["fecha"] < puntos[0]["fecha"]:
        puntos.insert(0, {**serie[0], "que_es": "cuestionario"})
    return {"circulos": puntos,
            "nota": "Los círculos son tus reportes anteriores. El primero es tu cuestionario inicial."}


async def datos_del_paso1(perfil: Dict[str, Any], d0: date, d1: date,
                          desde_el_principio: bool = False) -> Dict[str, Any]:
    """Todo el paso 1 para un periodo: el peso, lo que ha hecho, cómo se ha sentido y los huecos.

    LOS HUECOS NO VIAJAN EN EL PERIODO LARGO, y no es un olvido: «Los huecos no cambian:
    esos son siempre de los últimos 28». Van a `None` para que quien pinta sepa que tiene
    que conservar los que ya tenía en vez de vaciar el bloque.
    """
    from core.actividad_mensual import (cierres_del_periodo, filas_de_actividad,
                                        huecos_del_paso1, pie_de_las_sensaciones,
                                        sensaciones_del_periodo, titulo_de_actividad)
    from core.plan_access import plan_grants_feature

    dias = len(_dias(d0, d1))

    cierres_crudos = await db.checkins.find(
        {"client_id": perfil.get("id"), "type": "daily",
         "created_at": {"$gte": d0.isoformat(), "$lte": d1.isoformat() + "T23:59:59"}},
        {"_id": 0, "extras_respuesta": 1, "movimiento": 1, "suplementos": 1,
         "descanso": 1, "energy": 1, "hunger_anxiety": 1},
    ).to_list(400)

    dieta = await datos_dieta(perfil, d0, d1)
    entreno = await datos_entreno(perfil, d0, d1)
    cierres = cierres_del_periodo(
        cierres_crudos, dias,
        tiene_suplementacion=plan_grants_feature(perfil.get("plan"), "suplementacion"))

    pesos = serie_de_pesos(perfil, d0, d1)
    circulos = await _circulos_del_peso(perfil, d0, d1, desde_el_principio)

    return {
        "periodo": {"desde": d0.isoformat(), "hasta": d1.isoformat(), "dias": dias,
                    "desde_el_principio": desde_el_principio},
        "peso": {
            "serie": pesos,
            "actual": pesos[-1]["valor"] if pesos else None,
            "primero": pesos[0]["valor"] if pesos else None,
            # La diferencia solo con dos pesajes distintos: con uno solo, «−0,0 kg» es
            # decirle que no ha cambiado cuando lo que pasa es que no se ha pesado.
            "diferencia": (round(pesos[-1]["valor"] - pesos[0]["valor"], 1)
                           if len(pesos) > 1 else None),
            **circulos,
        },
        "actividad": {
            "titulo": titulo_de_actividad(dias, desde_el_principio),
            "filas": filas_de_actividad(dieta, entreno, cierres),
        },
        "sensaciones": {
            "filas": sensaciones_del_periodo(cierres),
            "pie": pie_de_las_sensaciones(desde_el_principio, dias),
        },
        "huecos": (None if desde_el_principio else huecos_del_paso1(
            entrenos_sin_registrar=len(entreno.get("sin_registrar") or []),
            dias_sin_dieta=max(0, dias - int(dieta.get("dias_registrados") or 0)),
        )),
    }
