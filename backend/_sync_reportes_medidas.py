# -*- coding: utf-8 -*-
"""Las medidas corporales de Calma a produccion, y los reportes mensuales que falten.

Francisco, 13-08-2026: «necesitamos actualizar la base de datos de produccion con los datos
actualizados a dia de hoy, no puede quedar nada fuera».

QUE ARREGLA
-----------
1) LAS MEDIDAS. Cada reporte mensual de Calma trae una cadena de diez perimetros
   ("114|101|33|33|61|60|102|91|39|40"). La migracion (_migrar_calma_raw.py) las decodifica
   y las deja en `calma_raw`, pero _migrar_todos.py escribe los reportes con
   `"measurements": None` y ahi se acaba el viaje: medido hoy en produccion, de 3.151
   reportes NINGUNO tiene medidas. Son 1.622 series en calma_raw (2.043 en el Mongo del
   servidor) que hoy se tiran enteras.

2) LOS REPORTES QUE FALTAN. En el MISMO Mongo del servidor viven las bases de Calma, y
   `forms.reportesMensualesCALMA` es una fuente mas viva que la copia de Firestore: para los
   clientes de la app tiene 1.808 envios frente a los 1.664 de Firestore, y el ultimo entro
   el 11-08-2026. Se traen los que no estan.

DE DONDE SALE CADA COSA
-----------------------
    forms.reportesMensualesCALMA   Mongo del servidor, por el tunel del 27018. Fuente
                                   principal: mas envios y sigue recibiendo.
    calma_raw.formularios_mensuales  la copia de Firestore que ya esta en produccion. Se usa
                                   como segunda fuente, no para volver a bajar Firestore. Las
                                   dos coinciden en 1.663 de 1.664 claves, asi que se validan
                                   entre ellas.

POR QUE EL REPORTE NO SE BUSCA POR FECHA EXACTA
-----------------------------------------------
Los reportes de produccion NO salieron de los formularios: _migrar_todos.py los fabrico a
partir del mapa `pesos` del usuario, que es la fecha en la que Jesus apunto el peso al
revisar, no la fecha en la que el cliente mando el formulario. Medido: de 1.622 series solo
18 caen en la MISMA fecha que un reporte, 1.391 caen en el mismo mes y la distancia tipica
es de 2 a 8 dias. Emparejar por fecha exacta dejaria fuera el 99% de las medidas, y crear un
reporte nuevo por cada formulario partiria cada mes en dos puntos casi pegados en la grafica
de peso. Asi que se empareja con el reporte mas cercano dentro de 15 dias (medio mes: no
llega al envio del mes de al lado) y solo se crea reporte nuevo si no hay ninguno cerca.

Uso, desde backend/:
    venv/Scripts/python.exe _sync_reportes_medidas.py              # dry-run, no escribe
    venv/Scripts/python.exe _sync_reportes_medidas.py --escribir   # escribe de verdad
    venv/Scripts/python.exe _sync_reportes_medidas.py --detalle    # ademas, cliente a cliente

El tunel tiene que estar abierto. Si se ha caido:
    ssh -i ~/.ssh/id_ed25519_jg12 -o StrictHostKeyChecking=no -N \
        -L 27018:127.0.0.1:27017 root@s1.jesusgallegopt.com
"""
import datetime
import re
import sys
import uuid
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")
from pymongo import MongoClient

PROD = "mongodb://127.0.0.1:27018"
BASE_PROD = "jg12_prod"
BASE_CALMA = "forms"
COL_CALMA = "reportesMensualesCALMA"

ESCRIBIR = "--escribir" in sys.argv
DETALLE = "--detalle" in sys.argv

# Medio mes. Ver la cabecera: la fecha del reporte (dia en que Jesus apunto el peso) y la del
# formulario (dia en que el cliente lo mando) no coinciden casi nunca, pero la cadencia es
# mensual, asi que 15 dias no pueden alcanzar nunca al envio del mes de al lado.
VENTANA_DIAS = 15

# El orden de la cadena de Calma. Es el mismo de frontend/src/lib/medidas.js, comprobado
# campo a campo: si alguien cambia aquel orden, esta lista tiene que cambiar con el, porque
# la cadena de Calma no lleva nombres, solo posiciones.
MEDIDAS = ["hombros", "mesoesternal", "brazo_d", "brazo_i", "muslo_d",
           "muslo_i", "cadera", "cintura", "gemelo_d", "gemelo_i"]

# QUE ES UN NUMERO CREIBLE PARA CADA PERIMETRO, en centimetros.
#
# Los topes salen de mirar las 2.043 series que hay, no de un manual. Dos cosas que se ven
# en los datos y que explican por que las bandas son tan anchas:
#
#   - Hombros y mesoesternal son BIMODALES: hay quien apunta el contorno (hombros 90-140,
#     pecho 80-120) y quien apunta la anchura o el diametro (hombros 35-70, pecho 28-40).
#     Las dos formas de medir son validas para lo que sirven las medidas, que segun Jesus no
#     es que el numero sea exacto sino que se pueda comparar con el del mes pasado. Si el
#     cliente se mide siempre igual, su serie sirve. Asi que el suelo se pone donde deja de
#     ser un cuerpo, no donde deja de ser el metodo de Jesus.
#   - Lo que se pasa por arriba son erratas de tecleo de un digito de mas, y sueltas dentro
#     de una serie por lo demas buena: "134|105|39|39|655|640|102|88|39|39" tiene los dos
#     muslos en milimetros y el resto perfecto. Por eso se descarta EL VALOR y no la serie.
RANGO = {
    "hombros":      (25, 160),
    "mesoesternal": (25, 160),
    "brazo_d":      (12, 65),
    "brazo_i":      (12, 65),
    "muslo_d":      (20, 100),
    "muslo_i":      (20, 100),
    "cadera":       (40, 170),
    "cintura":      (40, 200),
    "gemelo_d":     (12, 70),
    "gemelo_i":     (12, 70),
}

# Las respuestas del formulario mensual que vale la pena guardar en el reporte. Un reporte
# con solo peso y medidas es medio reporte; estas son las preguntas de las que Jesus saca el
# ajuste del mes. Se guardan en `calma_respuestas` y no en los campos de la app porque son
# texto libre de Calma y no encajan en los enum de ReportCreate.
RESPUESTAS = ["compromiso", "objetivo", "cumplimientoDieta", "esfuerzoParaCumplirDieta",
              "cumplimientoEntrenamiento", "cumplimientoCardio", "problemasParaEntrenar",
              "descanso", "tomaDeSuplementos", "detalleSuplementos"]

FOTOS = ["fotoFrente", "fotoPerfil", "fotoEspalda"]


# ----------------------------------------------------------------------------- utilidades
def dia(v):
    """El dia (YYYY-MM-DD) de cualquiera de los formatos que hay por medio."""
    if not v:
        return None
    s = str(v)
    return s[:10] if len(s) >= 10 and s[4] == "-" and s[7] == "-" else None


def a_fecha(d):
    try:
        return datetime.date.fromisoformat(d)
    except (TypeError, ValueError):
        return None


def sanear_peso(v):
    """Un peso creible en kg, o None.

    Es la misma regla que `core/series_cliente.sanea_peso`, copiada a proposito y no
    importada: importarla arrastra `core.database`, que abre un cliente contra la base de
    DESARROLLO, y este script escribe en produccion. Si alla cambia el rango, hay que
    cambiarlo aqui.

    Lo del /1000 no es un capricho. En el formulario mensual hay clientes que apuntan el peso
    en GRAMOS: 97100, 62800, 88500, 82750. Sin esto se caian 36 envios por "no traer peso", y
    con ellos 24 series de medidas buenas. Que son gramos esta comprobado contra el mapa
    `pesos` del propio cliente: jlgb83 manda 99800 el 07-07-2025 y Jesus le apunta 99,8 kg el
    09-07-2025; carlitoscapo manda 97100 y su peso de esas semanas es 101,2.
    """
    try:
        w = float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None
    while w > 1000:
        w /= 1000.0
    if 300 < w <= 1000:
        w /= 10.0
    return round(w, 1) if 25.0 <= w <= 300.0 else None


def decodificar_medidas(raw):
    """La cadena de diez perimetros -> ({clave: cm}, motivo_si_se_descarta, n_valores_caidos).

    Filtro en dos pasos, y en este orden a proposito:

      1. TODOS LOS VALORES IGUALES -> fuera la serie entera. Son los "0|0|0|0|0|0|0|0|0|0"
         y "1|1|1|1|1|1|1|1|1|1" de quien relleno por rellenar para poder darle a enviar.
         Van primero porque el problema no es que el numero sea imposible, es que no es una
         medicion. Nadie tiene el gemelo y la cintura iguales.
      2. VALOR FUERA DE RANGO -> fuera EL VALOR, no la serie. Ver el comentario de RANGO:
         las erratas van sueltas dentro de series buenas, y tirar la serie entera por un
         gemelo en milimetros seria perder la cintura, que es la que mas mira Jesus.

    Si no sobrevive ningun valor, la serie se descarta.
    """
    if not raw:
        return None, "vacia", 0
    trozos = str(raw).split("|")
    if len(trozos) != 10:
        return None, "no son diez valores", 0

    crudos = []
    for t in trozos:
        try:
            crudos.append(float(t.strip().replace(",", ".")))
        except (TypeError, ValueError):
            crudos.append(None)

    numericos = [v for v in crudos if v is not None]
    if len(numericos) >= 2 and len(set(numericos)) == 1:
        return None, "todos los valores iguales", 0

    medidas, caidos = {}, 0
    for clave, v in zip(MEDIDAS, crudos):
        if v is None:
            continue
        bajo, alto = RANGO[clave]
        if bajo <= v <= alto:
            medidas[clave] = round(v, 1)
        else:
            caidos += 1
    if not medidas:
        return None, "ningun valor creible", caidos
    return medidas, None, caidos


def texto(v):
    """El texto de una respuesta de Calma, sin el "|NOTA|score" que le pega Firestore."""
    if v is None:
        return None
    s = str(v).split("|")[0].strip()
    return s or None


def libre(v):
    """Un campo de texto libre de Calma, o None si no dice nada.

    Se pasa por str antes de tocarlo porque llega a veces como numero (hay comentarios de
    cliente guardados como int, que reventaban el .strip()). Y un comentario sin una sola
    letra ni un solo numero -- hay unos cuantos que son solo "," o "." -- se trata como
    vacio: pintar una coma en la columna "Comentario cliente" es peor que dejarla en blanco.
    """
    if v is None:
        return None
    s = str(v).strip()
    return s if any(c.isalnum() for c in s) else None


# ------------------------------------------------------------------------------- fuentes
def cargar_padron(prod):
    """Los clientes que cuentan: los que tienen cuenta en la app, cruzados por email.

    El identificador de `db.reports.client_id` NO es `users.id`: es `client_profiles.id`, y
    `calma_raw.client_id` guarda ese mismo. Comprobado contra los datos: de los 177 clientes
    con cuenta, los 177 tienen `calma_raw.client_id == client_profiles.id`, cero discrepan, y
    de los 162 client_id distintos que hay en `reports` los 162 son client_profiles.id y
    NINGUNO es un users.id.
    """
    users = {}
    for u in prod.users.find({}, {"_id": 0, "id": 1, "email": 1}):
        if u.get("email"):
            users[u["email"].lower().strip()] = u["id"]

    perfiles = {p["user_id"]: p["id"] for p in
                prod.client_profiles.find({}, {"_id": 0, "id": 1, "user_id": 1})}

    padron, descuadres = {}, []
    for c in prod.calma_raw.find({"client_id": {"$ne": None}},
                                 {"_id": 0, "email": 1, "client_id": 1}):
        email = (c.get("email") or "").lower().strip()
        uid = users.get(email)
        if not uid:
            continue                       # de Calma pero sin cuenta en la app: no entra
        esperado = perfiles.get(uid)
        if esperado and esperado != c["client_id"]:
            descuadres.append(email)       # no deberia pasar, pero si pasa hay que verlo
            continue
        padron[email] = c["client_id"]
    return padron, descuadres


def cargar_envios(prod, calma, padron):
    """Los envios mensuales de los clientes del padron: {email: {dia: envio}}.

    Union de las dos fuentes con el Mongo del servidor mandando, porque es la que sigue
    recibiendo (el ultimo envio es del 11-08-2026) y la que tiene mas: 1.808 claves frente a
    1.664 de la copia de Firestore. La clave natural es (email, dia): en el Mongo del
    servidor hay 397 documentos repetidos sobre 287 claves, y en 266 de esas 287 el duplicado
    trae LA MISMA medicion, o sea que es el mismo envio guardado varias veces, no dos envios.
    """
    envios = defaultdict(dict)
    origen = Counter()

    # 1) Mongo del servidor (principal)
    for r in calma[COL_CALMA].find({}):
        email = (r.get("email") or "").lower().strip()
        if email not in padron:
            continue
        d = dia(r.get("timestamp"))
        if not d:
            continue
        anterior = envios[email].get(d)
        envio = {
            "dia": d,
            "cuando": str(r.get("timestamp") or "").replace(" ", "T"),
            "peso": sanear_peso(r.get("peso")),
            "medidas_raw": r.get("mediciones") or None,
            "comentario": libre(r.get("comentarioCliente")),
            "respuestas": {k: texto(r.get(k)) for k in RESPUESTAS if texto(r.get(k))},
            "fotos": [r[k] for k in FOTOS if r.get(k)],
            "fuente": "forms.reportesMensualesCALMA",
        }
        # De dos copias del mismo dia se queda la que trae medidas; a igualdad, la ultima.
        if anterior and anterior.get("medidas_raw") and not envio.get("medidas_raw"):
            continue
        if anterior:
            origen["copias del mismo dia descartadas"] += 1
        envios[email][d] = envio

    # 2) calma_raw (la copia de Firestore que ya esta en produccion), solo para rellenar
    for c in prod.calma_raw.find({"client_id": {"$ne": None}},
                                 {"_id": 0, "email": 1, "formularios_mensuales": 1}):
        email = (c.get("email") or "").lower().strip()
        if email not in padron:
            continue
        for m in (c.get("formularios_mensuales") or []):
            d = m.get("fecha")
            if not d or d in envios[email]:
                continue
            envios[email][d] = {
                "dia": d,
                "cuando": m.get("fechaEnvio") or (d + "T12:00:00+00:00"),
                "peso": sanear_peso(m.get("peso")),
                "medidas_raw": (m.get("mediciones") or {}).get("raw"),
                "comentario": libre(m.get("comentarioCliente")),
                "respuestas": {k: texto((m.get(k) or {}).get("raw") if isinstance(m.get(k), dict)
                                        else m.get(k))
                               for k in RESPUESTAS if m.get(k)},
                "fotos": [f["path"] for f in (m.get("fotos") or []) if f.get("path")],
                "fuente": "calma_raw (Firestore)",
            }

    origen["reenvios del mismo formulario descartados"] = quitar_reenvios(envios)
    for porfecha in envios.values():
        for e in porfecha.values():
            origen["se quedan, de " + e["fuente"]] += 1
    return envios, origen


def quitar_reenvios(envios):
    """Quita el formulario que el cliente mando dos veces con un dia de diferencia.

    La clave (email, dia) no los pilla porque caen en dias distintos. Son 12 casos y se
    reconocen solos: mismo cliente, menos de tres dias de diferencia, MISMO peso y MISMA
    cadena de medidas (mtejero81 el 03 y el 04-08-2025 con 57,9 kg y la misma cadena;
    najarrocoronado el 12 y el 14-10-2024 con 83 kg). Eso no son dos pesajes, es darle dos
    veces a enviar. Se queda el primero, que es cuando el cliente lo mando de verdad.

    Tres dias y no mas: los envios de verdad van mes a mes, pero hay 72 pares a menos de diez
    dias con el peso o las medidas distintas, y esos SI son dos envios y se quedan los dos.
    """
    quitados = 0
    for email, porfecha in envios.items():
        dias = sorted(porfecha)
        for anterior, siguiente in zip(dias, dias[1:]):
            a, b = a_fecha(anterior), a_fecha(siguiente)
            if not a or not b or (b - a).days > 3:
                continue
            x, y = porfecha.get(anterior), porfecha.get(siguiente)
            if not x or not y:
                continue
            if x["peso"] == y["peso"] and x["medidas_raw"] == y["medidas_raw"]:
                porfecha.pop(siguiente)
                quitados += 1
    return quitados


# ---------------------------------------------------------------------------- emparejado
def emparejar(envios_cliente, reports_cliente):
    """Que envio va con que reporte. Devuelve (parejas, envios_sueltos).

    Uno a uno: primero las parejas mas cercanas en el tiempo, y a igualdad de distancia manda
    la que ademas tiene el mismo peso (el peso del formulario y el que Jesus apunto coinciden
    en 1.197 de 1.532 casos, asi que es una buena confirmacion de que es el mismo evento).
    Un reporte no puede recibir dos series de medidas.
    """
    candidatas = []
    for i, e in enumerate(envios_cliente):
        f = a_fecha(e["dia"])
        if not f:
            continue
        for j, r in enumerate(reports_cliente):
            g = a_fecha(r["dia"])
            if not g:
                continue
            distancia = abs((g - f).days)
            if distancia > VENTANA_DIAS:
                continue
            mismo_peso = (e["peso"] is not None and r.get("weight") is not None
                          and abs(e["peso"] - float(r["weight"])) < 0.05)
            candidatas.append((distancia, 0 if mismo_peso else 1, i, j))

    candidatas.sort()
    envio_usado, report_usado, parejas = set(), set(), []
    for _, _, i, j in candidatas:
        if i in envio_usado or j in report_usado:
            continue
        envio_usado.add(i)
        report_usado.add(j)
        parejas.append((envios_cliente[i], reports_cliente[j]))
    sueltos = [e for i, e in enumerate(envios_cliente) if i not in envio_usado]
    return parejas, sueltos


# --------------------------------------------------------------------- check-ins: el texto
PATRON_NOTA = re.compile(
    r"^Importado de Calma\. suplementacion=(?P<supl>.*?) cumplimiento=(?P<cumpl>.*)$",
    re.DOTALL)


def plan_comentarios(prod, padron, envios):
    """Sacar la cadena cruda del campo de comentario del cliente en los check-ins migrados.

    _migrar_todos.py (linea 280) metio en `notes` el texto
    "Importado de Calma. suplementacion=... cumplimiento=...", y CoachCheckins.jsx lo pinta
    en la columna "Comentario cliente", que es donde tendria que ir lo que escribio el
    cliente. Son 1.585 check-ins. Se parte en dos campos propios y `notes` se queda con el
    comentario de verdad del envio de ese dia, o vacio si no escribio nada.
    """
    por_cliente_dia = {}
    for email, cid in padron.items():
        for d, e in envios.get(email, {}).items():
            por_cliente_dia[(cid, d)] = e

    cambios, con_comentario = [], 0
    for ck in prod.checkins.find({"notes": {"$regex": "^Importado de Calma"}},
                                 {"_id": 0, "id": 1, "client_id": 1, "notes": 1, "created_at": 1}):
        m = PATRON_NOTA.match(ck["notes"])
        if not m:
            continue
        d = dia(ck.get("created_at"))
        comentario = None
        f = a_fecha(d)
        # El check-in se fecho con `fechaEnvio` y el envio se indexa por su dia, que a veces
        # se va uno por el huso horario. Se mira el dia y sus dos vecinos, y nada mas.
        for delta in (0, -1, 1):
            if not f:
                break
            e = por_cliente_dia.get((ck["client_id"], (f + datetime.timedelta(days=delta)).isoformat()))
            if e and e.get("comentario"):
                comentario = e["comentario"]
                break
        if comentario:
            con_comentario += 1
        cambios.append({
            "id": ck["id"],
            "notes": comentario,
            "calma_suplementacion": texto(m.group("supl")) if m.group("supl") != "None" else None,
            "calma_cumplimiento_dieta": texto(m.group("cumpl")) if m.group("cumpl") != "None" else None,
        })
    return cambios, con_comentario


# ------------------------------------------------------------------------------------ main
def main():
    cliente = MongoClient(PROD, serverSelectionTimeoutMS=8000)
    prod = cliente[BASE_PROD]
    calma = cliente[BASE_CALMA]

    print("=" * 78)
    print(f"  {'ESCRITURA' if ESCRIBIR else 'DRY-RUN (no escribe nada)'}"
          f"   ->   {BASE_PROD} por el tunel del 27018")
    print("=" * 78)

    padron, descuadres = cargar_padron(prod)
    print(f"\nClientes con cuenta en la app y datos de Calma: {len(padron)}")
    if descuadres:
        print(f"  OJO, {len(descuadres)} con client_id descuadrado, se quedan fuera: {descuadres[:5]}")

    envios, origen = cargar_envios(prod, calma, padron)
    total_envios = sum(len(v) for v in envios.values())
    print(f"Envios mensuales encontrados: {total_envios} de {len(envios)} clientes")
    for k, v in origen.most_common():
        print(f"    {k}: {v}")

    antes_reportes = prod.reports.count_documents({})
    antes_con_medidas = prod.reports.count_documents(
        {"measurements": {"$nin": [None, {}]}})
    print(f"\nAntes:  {antes_reportes} reportes, {antes_con_medidas} con medidas")

    # --- reportes que ya hay, por cliente
    reports = defaultdict(list)
    for r in prod.reports.find({}, {"_id": 0, "id": 1, "client_id": 1, "created_at": 1,
                                    "weight": 1, "measurements": 1, "measurements_origen": 1}):
        d = dia(r.get("created_at"))
        if d:
            reports[r["client_id"]].append({**r, "dia": d})

    set_medidas, nuevos = [], []
    motivos = Counter()
    caidos_sueltos = 0
    supervivientes = Counter()
    respetados = 0
    sin_peso = 0
    medidas_sin_reporte = []
    por_cliente = []

    for email, cid in sorted(padron.items()):
        mios = sorted(envios.get(email, {}).values(), key=lambda e: e["dia"])
        if not mios:
            continue
        parejas, sueltos = emparejar(mios, reports.get(cid, []))

        n_set = n_nuevo = 0
        for envio, rep in parejas:
            medidas, motivo, caidos = decodificar_medidas(envio["medidas_raw"])
            caidos_sueltos += caidos
            if motivo:
                motivos[motivo] += 1
                continue
            supervivientes[len(medidas)] += 1
            # REGLA: lo que escribio el cliente en 12EN12 no se toca. Solo se pisa lo que
            # puso una pasada anterior de este mismo script (measurements_origen == calma).
            ya = rep.get("measurements")
            if ya and rep.get("measurements_origen") != "calma":
                respetados += 1
                continue
            set_medidas.append((rep["id"], medidas, envio["medidas_raw"]))
            n_set += 1

        for envio in sueltos:
            medidas, motivo, caidos = decodificar_medidas(envio["medidas_raw"])
            caidos_sueltos += caidos
            if motivo:
                motivos[motivo] += 1
                medidas = None
            else:
                supervivientes[len(medidas)] += 1
            if envio["peso"] is None:
                # Sin peso no se crea reporte: `ReportResponse.weight` es obligatorio y un
                # reporte con weight=None revienta al leerlo por la API.
                sin_peso += 1
                if medidas:
                    medidas_sin_reporte.append((email, envio["dia"], envio["medidas_raw"]))
                continue
            nuevos.append(construir_reporte(cid, envio, medidas))
            n_nuevo += 1

        if DETALLE and (n_set or n_nuevo):
            por_cliente.append((email, len(mios), n_set, n_nuevo))

    # --- lo que se ha decidido
    print("\n" + "-" * 78)
    print("MEDIDAS")
    print("-" * 78)
    total_series = sum(1 for e_ in envios.values() for x in e_.values() if x["medidas_raw"])
    print(f"  series de medidas en el origen:            {total_series}")
    print(f"  descartadas enteras:                       {sum(motivos.values())}")
    for k, v in motivos.most_common():
        print(f"       {k}: {v}")
    print(f"  valores sueltos tirados por fuera de rango: {caidos_sueltos}")
    print(f"  series que se guardan:                     {sum(supervivientes.values())}")
    print("       reparto por medidas validas de las diez: "
          + ", ".join(f"{k}:{v}" for k, v in sorted(supervivientes.items(), reverse=True)))
    print(f"  se escriben sobre un reporte que ya existe: {len(set_medidas)}")
    print(f"  se respetan (medidas puestas desde 12EN12): {respetados}")

    print("\n" + "-" * 78)
    print("REPORTES NUEVOS")
    print("-" * 78)
    print(f"  envios sin ningun reporte a menos de {VENTANA_DIAS} dias: {len(nuevos) + sin_peso}")
    print(f"  se crean:                                  {len(nuevos)}")
    print(f"       de ellos con medidas:                 {sum(1 for r in nuevos if r.get('measurements'))}")
    print(f"  no se crean por no traer un peso creible:  {sin_peso}")
    if medidas_sin_reporte:
        print(f"  OJO: {len(medidas_sin_reporte)} series de medidas buenas se quedan fuera "
              f"por eso mismo:")
        for email, d, raw in medidas_sin_reporte[:15]:
            print(f"       {email[:36]:38s} {d}  {raw}")
    if nuevos:
        anios = Counter(r["created_at"][:4] for r in nuevos)
        print("       por anio: " + ", ".join(f"{k}:{v}" for k, v in sorted(anios.items())))

    # `ultimo_reporte` del perfil: la fecha del ultimo formulario que mando cada uno.
    #
    # No es un extra, es parte de insertar bien un reporte: la app lo escribe en el perfil
    # cada vez que se guarda uno (routes/reports.py, y core/seguimiento.py explica por que va
    # duplicado). Hoy en produccion esta VACIO en los 189 perfiles, asi que la columna «dias
    # sin reporte» del panel y el bloque «esta semana te tocan estos» no senalan a nadie. Se
    # pone la fecha del ultimo ENVIO, no la del ultimo reporte de la coleccion, porque los
    # reportes migrados salieron del mapa de pesos: son el dia en que Jesus apunto el peso,
    # no el dia en que el cliente mando nada.
    ultimos = []
    for email, cid in padron.items():
        dias_envio = sorted(envios.get(email, {}))
        if dias_envio:
            ultimos.append((cid, dias_envio[-1]))
    print(f"\n  perfiles a los que se les pone `ultimo_reporte`: {len(ultimos)}"
          f"  (hoy lo tienen {prod.client_profiles.count_documents({'ultimo_reporte': {'$ne': None}})})")

    cambios_ck, con_comentario = plan_comentarios(prod, padron, envios)
    print("\n" + "-" * 78)
    print("CHECK-INS: sacar la cadena cruda del comentario del cliente")
    print("-" * 78)
    print(f"  check-ins con 'Importado de Calma' en notes: {len(cambios_ck)}")
    print(f"       se les pone el comentario de verdad:   {con_comentario}")
    print(f"       se quedan con el comentario vacio:     {len(cambios_ck) - con_comentario}")

    if DETALLE and por_cliente:
        print("\n" + "-" * 78)
        print("POR CLIENTE (envios / medidas puestas / reportes nuevos)")
        print("-" * 78)
        for email, n, s, c in sorted(por_cliente, key=lambda x: -(x[2] + x[3]))[:40]:
            print(f"  {email[:42]:44s} {n:4d} {s:6d} {c:6d}")

    if not ESCRIBIR:
        print("\n" + "=" * 78)
        print("  DRY-RUN: no se ha escrito nada. Repite con --escribir.")
        print("=" * 78)
        return

    # --------------------------------------------------------------------------- escritura
    print("\nEscribiendo...")
    from pymongo import UpdateOne

    if set_medidas:
        ops = [UpdateOne({"id": rid},
                         {"$set": {"measurements": m,
                                   "measurements_raw": raw,
                                   "measurements_origen": "calma"}})
               for rid, m, raw in set_medidas]
        for i in range(0, len(ops), 500):
            prod.reports.bulk_write(ops[i:i + 500], ordered=False)
        print(f"  medidas escritas sobre reportes existentes: {len(ops)}")

    if nuevos:
        # Idempotente por clave natural: si ya existe un reporte con esa `calma_form_key` no
        # se vuelve a insertar. Ejecutarlo dos veces no duplica.
        claves = set(prod.reports.distinct("calma_form_key"))
        pendientes = [r for r in nuevos if r["calma_form_key"] not in claves]
        if pendientes:
            for i in range(0, len(pendientes), 500):
                prod.reports.insert_many(pendientes[i:i + 500], ordered=False)
        print(f"  reportes nuevos insertados: {len(pendientes)} "
              f"({len(nuevos) - len(pendientes)} ya estaban)")

    if ultimos:
        # Nunca hacia atras, la misma regla que core/seguimiento._adelantar: si ya hay una
        # fecha mas reciente (un reporte que mando por la app) esa manda.
        ops = [UpdateOne({"id": cid, "$or": [{"ultimo_reporte": {"$lt": d}},
                                             {"ultimo_reporte": None},
                                             {"ultimo_reporte": {"$exists": False}}]},
                         {"$set": {"ultimo_reporte": d}}) for cid, d in ultimos]
        r = prod.client_profiles.bulk_write(ops, ordered=False)
        print(f"  perfiles con `ultimo_reporte` puesto al dia: {r.modified_count}")

    if cambios_ck:
        ops = [UpdateOne({"id": c["id"]}, {"$set": {k: v for k, v in c.items() if k != "id"}})
               for c in cambios_ck]
        for i in range(0, len(ops), 500):
            prod.checkins.bulk_write(ops[i:i + 500], ordered=False)
        print(f"  check-ins con el comentario saneado: {len(ops)}")

    despues = prod.reports.count_documents({})
    despues_medidas = prod.reports.count_documents({"measurements": {"$nin": [None, {}]}})
    print("\n" + "=" * 78)
    print(f"  Antes:   {antes_reportes:5d} reportes, {antes_con_medidas:5d} con medidas")
    print(f"  Despues: {despues:5d} reportes, {despues_medidas:5d} con medidas")
    print("=" * 78)


def construir_reporte(client_id, envio, medidas):
    """Un reporte de la app a partir de un envio mensual de Calma.

    Las fotos van a `photo_urls_calma` y NO a `photos`: `photos` guarda ids de client_photos y
    de ahi tira el informe mensual, asi que meterle rutas de Storage lo romperia. Es el mismo
    campo que ya usan los check-ins migrados, o sea que las fotos no se pierden.
    """
    return {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "weight": envio["peso"],
        "measurements": medidas,
        "measurements_raw": envio["medidas_raw"] if medidas else None,
        "measurements_origen": "calma" if medidas else None,
        "photos": None,
        "photo_urls_calma": envio["fotos"] or None,
        "notes": envio["comentario"],
        "calma_respuestas": envio["respuestas"] or None,
        "trainer_feedback": None,
        "created_at": envio["cuando"] if "T" in (envio["cuando"] or "")
                      else envio["dia"] + "T12:00:00+00:00",
        "calma_migrated": True,
        "origen": "reporte mensual de Calma",
        # Clave natural del envio. Es lo que hace el script idempotente: dos ejecuciones no
        # crean dos reportes para el mismo formulario.
        "calma_form_key": f"{client_id}|{envio['dia']}",
    }


main()
