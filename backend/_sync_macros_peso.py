# -*- coding: utf-8 -*-
"""Trae a PRODUCCION el historial de macros, peso y % graso que falta de Calma.

Francisco, 13-08-2026: «necesitamos actualizar la base de datos de produccion con los datos
actualizados a dia de hoy, de los clientes, no puede quedar nada fuera».

Calma (Firestore) sigue vivo: Jesus le sigue tocando los macros a la gente alli mientras
12EN12 va por su cuenta. La importacion de agosto fue una foto de un dia, y desde entonces
se han quedado ajustes fuera. `_delta_calma.py` los conto; este script los trae.

    Fuente:   Firestore del proyecto jesusgallegopt, `usuarios/{email}`
    Destino:  Mongo de produccion (jg12_prod) por el tunel del 27018

QUE trae, y donde lo deja:

  1. `usuarios.macros`  ->  `db.macro_history`, una fila por (cliente, fecha de vigencia).
  2. `usuarios.pesos`   ->  `client_profiles.pesos`, la serie del punto 30.
  3. `usuarios.porcentajesGrasos` -> `client_profiles.porcentajes_grasos`, la misma serie.

Las tres reglas que no se pueden saltar, y por que:

  - **La fecha buena es `effective_date`, nunca `created_at`.** En las 3.446 filas que vinieron
    de Calma `created_at` es el dia en que se importaron -- todas el 05-08, muchas en el mismo
    milisegundo --, asi que ordenar por ahi da el ultimo ajuste a suertes. Esto ya mordio una
    vez (ver `macros_por_fecha.ultima_vigente`).

  - **La clave natural es (`client_id`, `effective_date`).** Es la misma que usa
    `core/historial_macros.py` y la que protege el indice unico parcial
    `una_por_cliente_y_fecha`. Ejecutar esto dos veces no puede duplicar nada.

  - **Lo que se hizo en 12EN12 no se pisa.** Si para ese dia ya hay fila, se deja como esta,
    venga de donde venga. Aqui solo se AÑADE lo que falta. Un ajuste que el coach hizo en la
    app es mas nuevo que el de Calma, y machacarlo seria devolverle al cliente unos macros
    que ya nadie le habia mandado.

Sobre el peso y el % graso: la serie del perfil es la que manda desde el punto 30
(`core/series_cliente.py`), y el `weight` suelto es un espejo de su ultimo punto. Por eso,
ademas de los pesajes de Calma, se recogen los pesos con fecha que ya tiene la app
-- historial de macros, check-ins y reportes -- igual que hizo `_rellenar_series_peso_grasa.py`.
Si no se recogieran, a un cliente que se peso en 12EN12 en agosto le dejariamos de peso
actual el ultimo pesaje de Calma, que puede ser de junio: seria una regresion.

Lo que este script NO hace, a proposito: no inventa fechas. `_rellenar_series_peso_grasa.py`
tenia un ultimo paso que colocaba el `weight` suelto sin fecha en el dia de hoy; eso aqui se
cuenta pero no se escribe, porque un peso sin fecha colocado en un dia que no es el suyo
ensucia justo la serie que estamos construyendo.

    venv/Scripts/python.exe _sync_macros_peso.py              simula y cuenta, NO escribe
    venv/Scripts/python.exe _sync_macros_peso.py --escribir   escribe en produccion
    venv/Scripts/python.exe _sync_macros_peso.py --vivos      solo los de membresia viva
    venv/Scripts/python.exe _sync_macros_peso.py --detalle    ademas, cliente a cliente

Si el tunel se ha caido:
    ssh -i ~/.ssh/id_ed25519_jg12 -o StrictHostKeyChecking=no -N \
        -L 27018:127.0.0.1:27017 root@s1.jesusgallegopt.com
"""
import asyncio
import contextlib
import datetime
import io
import os
import sys
import uuid

BACKEND = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND)
sys.stdout.reconfigure(encoding="utf-8")

PROD = "mongodb://127.0.0.1:27018"
BASE_PROD = "jg12_prod"

ESCRIBIR = "--escribir" in sys.argv
SOLO_VIVOS = "--vivos" in sys.argv
DETALLE = "--detalle" in sys.argv

# La marca con la que se firma lo que escribe esta pasada. `calma_migrated` y la nota
# "Importado de Calma" son las de la migracion original: se conservan tal cual para que una
# fila traida hoy se lea igual que una traida en agosto. `calma_sync_at` es lo unico nuevo, y
# sirve para saber de que pasada vino cada fila si algun dia hay que deshacer algo.
NOTA_MIGRACION = "Importado de Calma"


def ahora_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def hoy():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------------------
# El decodificador de los macros de Calma
# ---------------------------------------------------------------------------------------
def cargar_decodificador():
    """`decode_macros` y `norm_date` de `_migrar_calma_raw.py`, sin ejecutar ese script.

    El formato de Calma es una cadena de ocho numeros separados por espacios
    (proteina/hidratos/grasa de entreno, proteina/hidratos de peri -- el peri NO lleva grasa,
    es a proposito -- y proteina/hidratos/grasa de descanso). Ese orden ya esta escrito una
    vez y no se vuelve a escribir: equivocarse en una posicion no da error, da unos macros
    plausibles y equivocados, que es el peor fallo posible aqui.

    POR QUE con este rodeo: `_migrar_calma_raw.py` llama a `asyncio.run(main())` en el propio
    modulo y `main()` mira `sys.argv`. Importarlo con NUESTROS argumentos puestos lo lanzaria
    contra la base de DESARROLLO. Se importa con `sys.argv` vaciado -- entonces imprime su
    ayuda y vuelve, sin tocar Mongo -- y con el cwd en backend/, que es donde busca
    `serviceAccountKey.json`. De paso deja `firebase_admin` inicializado, que es justo lo que
    hace falta a continuacion.
    """
    class _Papelera(io.StringIO):
        # `_migrar_calma_raw` llama a `sys.stdout.reconfigure(...)` nada mas cargarse, y un
        # StringIO pelado no tiene ese metodo. Se le pone y no hace nada.
        def reconfigure(self, **_):
            pass

    argv, cwd = sys.argv, os.getcwd()
    try:
        sys.argv = [argv[0]]
        os.chdir(BACKEND)
        with contextlib.redirect_stdout(_Papelera()):
            import _migrar_calma_raw as mig
    finally:
        sys.argv, _ = argv, os.chdir(cwd)
    return mig


def bloque(p, h, g=None):
    """Un bloque de macros con la forma exacta que ya tienen las filas migradas.

    Los nombres van por duplicado (`protein`/`proteinas`) porque la app lee unos u otros
    segun la pantalla, y `macros_por_fecha.para_el_chat()` usa los castellanos. Si aqui se
    escribiera solo la mitad, el ajuste se veria en el historial y no en el chat.
    """
    b = {"protein": p, "carbs": h, "proteinas": p, "hidratos": h}
    if g is not None:
        b["fat"] = g
        b["grasas"] = g
    b["calories"] = round(p * 4 + h * 4 + (g or 0) * 9, 1)
    return b


def bloques(dec):
    """(entreno, peri, descanso) a partir del dict decodificado, o None si no se pudo leer."""
    claves = ("p_ent", "h_ent", "g_ent", "p_peri", "h_peri", "p_desc", "h_desc", "g_desc")
    if any(dec.get(k) is None for k in claves):
        return None
    return (bloque(dec["p_ent"], dec["h_ent"], dec["g_ent"]),
            bloque(dec["p_peri"], dec["h_peri"]),
            bloque(dec["p_desc"], dec["h_desc"], dec["g_desc"]))


# ---------------------------------------------------------------------------------------
# Series de peso y % graso
# ---------------------------------------------------------------------------------------
def punto_grasa(v):
    """Un % graso creible, o None. El rango es el de `core/series_cliente.GRASA`."""
    try:
        n = round(float(v), 1)
    except (TypeError, ValueError):
        return None
    return n if 3.0 <= n <= 60.0 else None


def dia(v):
    return str(v)[:10] if v else None


def espejo(ultimo, serie, valor_ficha):
    """El valor que debe quedar en el campo suelto (`weight`/`body_fat`), o None si no se toca.

    El campo suelto es un espejo del ultimo punto de la serie (punto 30), pero aqui hay una
    trampa: en produccion hay fichas con un peso que NO esta en ninguna serie y del que nadie
    sabe la fecha -- alguien lo escribio a mano en la app y ese camino no guarda el dia.

    Medido hoy sobre prod, son dos, y los dos irian hacia atras:

        info@rubiowellnesscoach.com   ficha 80,0 kg  ->  77,0 kg del 29-07
        jmatamoros.elite@gmail.com    ficha 83,0 kg  ->  62,0 kg del 07-07

    El segundo canta solo: el 01-07 pesaba 82 y el 07-07 aparece un 62. Es un 8 tecleado como
    6, y ponerselo de peso actual seria peor que no tocar nada.

    La regla: si el valor de la ficha aparece en algun punto de la serie, tiene fecha conocida
    y el ultimo punto le gana con todas las de la ley (ahi estan los 30 casos del punto 9, el
    de «hay dos pesos distintos en la misma app»). Si no aparece por ningun lado, es un dato
    de fecha desconocida: la serie se escribe igual, pero el campo suelto se deja como esta.
    """
    if not ultimo:
        return None
    if valor_ficha is None:
        return ultimo["valor"]
    try:
        v = float(valor_ficha)
    except (TypeError, ValueError):
        return ultimo["valor"]
    if any(abs(v - float(x["valor"])) < 0.1 for x in serie):
        return ultimo["valor"]
    return None


# ---------------------------------------------------------------------------------------
async def main(mig):
    from motor.motor_asyncio import AsyncIOMotorClient
    from core.series_cliente import actual, sanea_peso

    from firebase_admin import firestore
    fs = firestore.client()

    db = AsyncIOMotorClient(PROD)[BASE_PROD]

    # ---------------- 1) Quienes: los que tienen cuenta en la app, cruzados por email -----
    # El cruce es por email porque es lo unico que comparten las dos puntas. Y ojo con los
    # identificadores: `macro_history.client_id` es `client_profiles.id`, mientras que
    # `diets.user_id` es `users.id`. Son dos uuid distintos del mismo cliente y confundirlos
    # escribe el historial de otro. Se comprueba abajo contra datos reales antes de nada.
    perfil_por_user = {}
    async for p in db.client_profiles.find({}, {"_id": 0, "id": 1, "user_id": 1, "sex": 1,
                                                "weight": 1, "body_fat": 1,
                                                "pesos": 1, "porcentajes_grasos": 1}):
        if p.get("user_id"):
            perfil_por_user[p["user_id"]] = p

    gente = []
    async for u in db.users.find({"deleted_at": None}, {"_id": 0, "id": 1, "email": 1}):
        email = (u.get("email") or "").strip().lower()
        perfil = perfil_por_user.get(u.get("id"))
        if email and perfil and perfil.get("id"):
            gente.append({"email": email, "user_id": u["id"], "cid": perfil["id"], "perfil": perfil})

    # Comprobacion de identificadores contra datos reales: si `macro_history.client_id` no
    # cayera dentro de `client_profiles.id`, todo lo de abajo estaria escribiendo en el sitio
    # equivocado y hay que parar.
    ids_perfil = {p["id"] for p in perfil_por_user.values() if p.get("id")}
    en_historial = await db.macro_history.distinct("client_id")
    aciertos = len([x for x in en_historial if x in ids_perfil])
    print(f"macro_history.client_id -> client_profiles.id: {aciertos}/{len(en_historial)}")
    if en_historial and aciertos < len(en_historial) * 0.9:
        print("PARO: `macro_history.client_id` NO es `client_profiles.id` en esta base.")
        return

    # ---------------- 2) Lo que ya hay en produccion --------------------------------------
    # Se carga entero y en memoria (3.500 filas) porque hay que decidir cliente a cliente y
    # fecha a fecha, y 2.600 consultas sueltas por el tunel tardarian mas que traerlo todo.
    ya_hay = {}          # (client_id, fecha) -> "migracion" | "12en12"
    peso_por_fecha = {}  # client_id -> {fecha: (valor, origen)} con lo que la app ya sabe
    grasa_por_fecha = {}

    def anota(destino, cid, fecha, valor, origen, limpiar):
        v = limpiar(valor)
        f = dia(fecha)
        if cid and v is not None and f and len(f) == 10:
            destino.setdefault(cid, {})[f] = (v, origen)

    async for h in db.macro_history.find({}, {"_id": 0, "client_id": 1, "effective_date": 1,
                                              "created_at": 1, "note": 1, "calma_migrated": 1,
                                              "peso": 1, "client_weight": 1, "body_fat": 1,
                                              "porcentaje_graso": 1, "peso_fecha": 1}):
        # La fecha de vigencia, con la misma regla que `historial_macros.fecha_de_vigencia`:
        # `effective_date` y, solo si no esta, el dia de `created_at`.
        f = dia(h.get("effective_date")) or dia(h.get("created_at"))
        if h.get("client_id") and f:
            de_la_migracion = bool(h.get("calma_migrated")) or h.get("note") == NOTA_MIGRACION
            ya_hay[(h["client_id"], f)] = "migracion" if de_la_migracion else "12en12"
        fp = dia(h.get("peso_fecha")) or dia(h.get("effective_date")) or dia(h.get("created_at"))
        peso = h.get("peso") if h.get("peso") is not None else h.get("client_weight")
        anota(peso_por_fecha, h.get("client_id"), fp, peso, "ajuste", sanea_peso)
        grasa = h.get("porcentaje_graso") if h.get("porcentaje_graso") is not None else h.get("body_fat")
        anota(grasa_por_fecha, h.get("client_id"), fp, grasa, "ajuste", punto_grasa)

    colecciones = await db.list_collection_names()
    if "checkins" in colecciones:
        async for k in db.checkins.find({}, {"_id": 0, "client_id": 1, "weight": 1,
                                             "body_fat_pct": 1, "created_at": 1, "type": 1}):
            org = f"check-in {k.get('type') or ''}".strip()
            anota(peso_por_fecha, k.get("client_id"), k.get("created_at"), k.get("weight"), org, sanea_peso)
            anota(grasa_por_fecha, k.get("client_id"), k.get("created_at"), k.get("body_fat_pct"), org, punto_grasa)
    if "reports" in colecciones:
        async for r in db.reports.find({}, {"_id": 0, "client_id": 1, "weight": 1, "created_at": 1}):
            anota(peso_por_fecha, r.get("client_id"), r.get("created_at"), r.get("weight"), "reporte", sanea_peso)

    # ---------------- 3) Lo que dice Calma hoy --------------------------------------------
    print(f"\nLeyendo Firestore de {len(gente)} clientes con cuenta en la app...")
    docs = {}
    refs = [fs.collection("usuarios").document(p["email"]) for p in gente]
    for i in range(0, len(refs), 50):   # get_all por tandas: una consulta por cada 50 clientes
        for snap in fs.get_all(refs[i:i + 50]):
            if snap.exists:
                docs[snap.id.strip().lower()] = snap.to_dict() or {}

    gente = [p for p in gente if p["email"] in docs]
    if SOLO_VIVOS:
        gente = [p for p in gente if str(docs[p["email"]].get("finDeMembresia") or "")[:10] >= hoy()]
    print(f"{len(gente)} clientes cruzados por email"
          f"{' (solo membresia viva)' if SOLO_VIVOS else ''}\n")

    # ---------------- 4) El calculo: que falta --------------------------------------------
    n = {"macros_calma": 0, "macros_ya": 0, "macros_12en12": 0, "macros_ilegibles": 0,
         "macros_nuevos": 0, "macros_futuros": 0,
         "pesos_calma": 0, "pesos_ya": 0, "pesos_nuevos": 0, "pesos_malos": 0,
         "grasa_calma": 0, "grasa_ya": 0, "grasa_nuevos": 0, "grasa_malos": 0,
         "puntos_app": 0, "sin_fecha": 0,
         "peso_corregido": 0, "peso_no_tocado": 0, "grasa_no_tocada": 0}
    clientes = {"macros": set(), "pesos": set(), "grasa": set()}
    filas_nuevas, cambios_perfil, muestra_peso, muestra_macros = [], [], [], []
    aviso_peso, muestra_rotas = [], []

    for p in gente:
        u, cid, perfil = docs[p["email"]], p["cid"], p["perfil"]
        sexo = perfil.get("sex") or {"M": "hombre", "F": "mujer"}.get(u.get("sexo")) or "hombre"

        pesos_calma = u.get("pesos") or {}
        grasas_calma = u.get("porcentajesGrasos") or {}

        # --- macros
        for clave, cadena in (u.get("macros") or {}).items():
            fecha = mig.norm_date(clave)
            n["macros_calma"] += 1
            estado = ya_hay.get((cid, fecha))
            if estado:
                n["macros_ya"] += 1
                n["macros_12en12"] += 1 if estado == "12en12" else 0
                continue
            b = bloques(mig.decode_macros(cadena))
            if not b:
                # La cadena no trae los ocho numeros. Son cadenas como '190 440 60   220 400 70'
                # (seis: falta el peri entero) o '175 90 50 40  190 88 50' (siete: al peri le
                # falta un numero). Colocar los que hay adivinando cual falta no da un error:
                # da unos macros plausibles y equivocados, que es peor. Se dejan fuera, que es
                # ademas lo que hizo la importacion de agosto con estas mismas filas.
                n["macros_ilegibles"] += 1
                if len(muestra_rotas) < 6:
                    muestra_rotas.append(f"   {p['email'][:34]:36s} {fecha}  {cadena!r}"[:100])
                continue
            tr, pe, de = b
            peso = sanea_peso(pesos_calma.get(clave))
            fila = {
                "id": str(uuid.uuid4()), "client_id": cid, "user_id": p["user_id"],
                "new_training": tr, "new_rest": de,
                "training": tr, "rest": de, "peri": pe,
                "effective_date": fecha,
                "note": NOTA_MIGRACION, "changed_by": "migracion",
                "client_weight": peso, "peso": peso,
                "porcentaje_graso": punto_grasa(grasas_calma.get(clave)),
                "sexo": sexo, "created_at": ahora_iso(),
                "calma_migrated": True, "calma_sync_at": ahora_iso(),
            }
            filas_nuevas.append(fila)
            n["macros_nuevos"] += 1
            n["macros_futuros"] += 1 if fecha > hoy() else 0
            clientes["macros"].add(cid)
            if len(muestra_macros) < 8:
                muestra_macros.append(
                    f"   {p['email'][:34]:36s} {fecha}  "
                    f"{tr['proteinas']:.0f}-{tr['hidratos']:.0f}-{tr['grasas']:.0f} | "
                    f"{pe['proteinas']:.0f}-{pe['hidratos']:.0f} | "
                    f"{de['proteinas']:.0f}-{de['hidratos']:.0f}-{de['grasas']:.0f}")

        # --- peso y % graso: se monta la serie completa y se compara con la que ya hay
        serie_peso = {dia(x.get("fecha")): x for x in (perfil.get("pesos") or [])
                      if dia(x.get("fecha"))}
        serie_grasa = {dia(x.get("fecha")): x for x in (perfil.get("porcentajes_grasos") or [])
                       if dia(x.get("fecha"))}
        antes_peso, antes_grasa = len(serie_peso), len(serie_grasa)

        # El orden importa, y es el que ya fijo `_rellenar_series_peso_grasa.py`: si dos
        # fuentes caen el mismo dia manda la de la app, no la de Calma. Dos motivos. Uno, el
        # de la regla de arriba: un peso que el cliente metio en 12EN12 ese dia es lo ultimo
        # que se sabe de el y no se pisa. Y dos, que buena parte de los pesos que hoy tiene la
        # app en `macro_history` VINIERON de Calma en agosto (`_migrar_todos.py` copiaba
        # `pesos[fecha]` en cada ajuste), asi que las dos fuentes dicen lo mismo salvo cuando
        # alguien lo corrigio despues -- y esa correccion es la que tiene que ganar.
        for f, (v, org) in (peso_por_fecha.get(cid) or {}).items():
            if f not in serie_peso:
                serie_peso[f] = {"fecha": f, "valor": v, "origen": org}
                n["puntos_app"] += 1
        for f, (v, org) in (grasa_por_fecha.get(cid) or {}).items():
            if f not in serie_grasa:
                serie_grasa[f] = {"fecha": f, "valor": v, "origen": org}
                n["puntos_app"] += 1

        # Y ahora Calma, que es la fuente de esta tarea, rellenando los dias que no cubre nadie.
        nuevos_calma_peso = nuevos_calma_grasa = 0
        for clave, valor in pesos_calma.items():
            n["pesos_calma"] += 1
            f = mig.norm_date(clave)
            v = sanea_peso(valor)
            if v is None:
                n["pesos_malos"] += 1
                continue
            if f in serie_peso:
                n["pesos_ya"] += 1
                continue
            serie_peso[f] = {"fecha": f, "valor": v, "origen": "calma"}
            nuevos_calma_peso += 1
        for clave, valor in grasas_calma.items():
            n["grasa_calma"] += 1
            f = mig.norm_date(clave)
            v = punto_grasa(valor)
            if v is None:
                n["grasa_malos"] += 1
                continue
            if f in serie_grasa:
                n["grasa_ya"] += 1
                continue
            serie_grasa[f] = {"fecha": f, "valor": v, "origen": "calma"}
            nuevos_calma_grasa += 1

        n["pesos_nuevos"] += nuevos_calma_peso
        n["grasa_nuevos"] += nuevos_calma_grasa
        if nuevos_calma_peso:
            clientes["pesos"].add(cid)
        if nuevos_calma_grasa:
            clientes["grasa"].add(cid)

        # Un cliente cuyo unico peso es el suelto de la ficha se queda sin serie. No se le
        # coloca en el dia de hoy -- `_rellenar_series_peso_grasa.py` lo hacia y era el unico
        # paso suyo que inventaba una fecha --, pero se cuenta para que no pase inadvertido.
        if not serie_peso and perfil.get("weight") is not None:
            n["sin_fecha"] += 1
        if len(serie_peso) == antes_peso and len(serie_grasa) == antes_grasa:
            continue

        sp = sorted(serie_peso.values(), key=lambda x: x["fecha"])
        sg = sorted(serie_grasa.values(), key=lambda x: x["fecha"])
        ap, ag = actual(sp), actual(sg)
        cambio = {}
        if sp:
            cambio["pesos"] = sp
            w = espejo(ap, sp, perfil.get("weight"))
            if w is not None:
                cambio["weight"] = w
            elif ap:
                n["peso_no_tocado"] += 1
                aviso_peso.append(f"   {p['email'][:34]:36s} ficha {perfil.get('weight')} kg, sin fecha; "
                                  f"el ultimo de la serie es {ap['valor']} del {ap['fecha']}")
        if sg:
            cambio["porcentajes_grasos"] = sg
            bf = espejo(ag, sg, perfil.get("body_fat"))
            if bf is not None:
                cambio["body_fat"] = bf
            elif ag:
                n["grasa_no_tocada"] += 1
        cambios_perfil.append((cid, cambio))

        if cambio.get("weight") is not None and perfil.get("weight") is not None \
                and abs(cambio["weight"] - float(perfil["weight"])) >= 0.1:
            n["peso_corregido"] += 1
            if len(muestra_peso) < 8:
                muestra_peso.append(
                    f"   {p['email'][:34]:36s} la ficha decia {perfil['weight']} kg  ->  "
                    f"{ap['valor']} kg del {ap['fecha']}  ({len(sp)} pesajes)")

    # ---------------- 5) El recuento -------------------------------------------------------
    print("=" * 78)
    print(f"{'':26s}{'en Calma':>11s}{'ya cubierto':>12s}{'ilegible':>10s}{'se inserta':>12s}{'clientes':>10s}")
    print("=" * 78)
    print(f"{'ajustes de macros':26s}{n['macros_calma']:>11d}{n['macros_ya']:>12d}"
          f"{n['macros_ilegibles']:>10d}{n['macros_nuevos']:>12d}{len(clientes['macros']):>10d}")
    print(f"{'pesajes':26s}{n['pesos_calma']:>11d}{n['pesos_ya']:>12d}"
          f"{n['pesos_malos']:>10d}{n['pesos_nuevos']:>12d}{len(clientes['pesos']):>10d}")
    print(f"{'mediciones de % graso':26s}{n['grasa_calma']:>11d}{n['grasa_ya']:>12d}"
          f"{n['grasa_malos']:>10d}{n['grasa_nuevos']:>12d}{len(clientes['grasa']):>10d}")
    print("=" * 78)
    print(f"  de las fechas que ya tenian ajuste, {n['macros_12en12']} se hicieron en 12EN12: se dejan como estan")
    print(f"  {n['macros_futuros']} de los ajustes nuevos van fechados por delante de hoy "
          f"(vienen asi de Calma; `sin_futuro` ya los aparta al pintarlos)")
    print(f"  'ya cubierto' en peso y grasa = ese dia ya lo dice la app (un ajuste, un check-in o "
          f"un reporte); manda el dato de la app, no el de Calma")
    print(f"  {n['puntos_app']} puntos con fecha que la app ya tenia sueltos (ajustes, check-ins, "
          f"reportes) entran tambien en la serie")
    print(f"  {len(cambios_perfil)} perfiles cambian de serie")
    print(f"  {n['sin_fecha']} clientes se quedan sin serie porque su unico peso no tiene fecha "
          f"(no se inventa: se deja fuera)")

    if muestra_macros:
        print("\nMuestra de ajustes que entran (entreno | peri | descanso):")
        print("\n".join(muestra_macros))
    if muestra_rotas:
        print(f"\nMuestra de los {n['macros_ilegibles']} que no traen los ocho numeros (se quedan fuera):")
        print("\n".join(muestra_rotas))
    if muestra_peso:
        print(f"\n{n['peso_corregido']} clientes cuyo peso actual se CORRIGE "
              f"(el de la ficha no era el ultimo de verdad):")
        print("\n".join(muestra_peso))
    if aviso_peso:
        print(f"\n{n['peso_no_tocado']} fichas con un peso sin fecha conocida: se les monta la serie "
              f"pero NO se les toca el peso actual")
        print("\n".join(aviso_peso[:8]))

    if DETALLE:
        print("\nPor cliente (solo los que tienen algo que traer):")
        por_cliente = {}
        for f in filas_nuevas:
            por_cliente[f["client_id"]] = por_cliente.get(f["client_id"], 0) + 1
        emails = {p["cid"]: p["email"] for p in gente}
        for cid, cuantos in sorted(por_cliente.items(), key=lambda kv: -kv[1]):
            print(f"   {emails.get(cid, cid)[:40]:42s} {cuantos:4d} ajustes")

    # ---------------- 6) Escribir ----------------------------------------------------------
    if not ESCRIBIR:
        print("\nSIMULACION: no se ha escrito nada. Pasa --escribir para hacerlo de verdad.")
        return

    print("\nEscribiendo en produccion...")
    # El indice unico `una_por_cliente_y_fecha` es el cinturon: aunque este script se lanzase
    # dos veces a la vez, no puede quedar mas de una fila por cliente y fecha. `ordered=False`
    # para que un choque no aborte el resto del lote.
    from pymongo.errors import BulkWriteError
    insertadas = 0
    for i in range(0, len(filas_nuevas), 500):
        lote = filas_nuevas[i:i + 500]
        try:
            r = await db.macro_history.insert_many(lote, ordered=False)
            insertadas += len(r.inserted_ids)
        except BulkWriteError as e:
            # Un choque de clave aqui significa que otro camino escribio ese mismo dia entre
            # el recuento y ahora: la fila que ya esta es la buena y esta se descarta. El
            # resto del lote sigue entrando porque va `ordered=False`.
            insertadas += e.details.get("nInserted", 0)
            print(f"   {len(e.details.get('writeErrors', []))} filas del lote {i // 500} "
                  f"ya existian para ese cliente y fecha: se dejan las que habia")
    for cid, cambio in cambios_perfil:
        await db.client_profiles.update_one({"id": cid}, {"$set": cambio})

    print(f"\nESCRITO: {insertadas} filas en macro_history, {len(cambios_perfil)} perfiles actualizados")

    despues = await db.macro_history.count_documents({})
    con_serie = await db.client_profiles.count_documents({"pesos": {"$exists": True, "$ne": []}})
    con_grasa = await db.client_profiles.count_documents({"porcentajes_grasos": {"$exists": True, "$ne": []}})
    puntos_p = puntos_g = 0
    async for pr in db.client_profiles.find({}, {"_id": 0, "pesos": 1, "porcentajes_grasos": 1}):
        puntos_p += len(pr.get("pesos") or [])
        puntos_g += len(pr.get("porcentajes_grasos") or [])
    print(f"macro_history queda en {despues} filas")
    print(f"{con_serie} perfiles con serie de peso ({puntos_p} puntos), "
          f"{con_grasa} con serie de % graso ({puntos_g} puntos)")


# El decodificador se carga ANTES de arrancar el bucle: `_migrar_calma_raw` termina con su
# propio `asyncio.run()`, y eso no se puede llamar desde dentro de un bucle ya en marcha.
asyncio.run(main(cargar_decodificador()))
