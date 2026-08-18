# -*- coding: utf-8 -*-
"""Pone al dia en produccion el ciclo de membresia y trae el historico de cobros.

Francisco, 13-08-2026: «no puede quedar nada fuera... membresias, cobros, ciclos, TODO
ABSOLUTAMENTE TODO».

Son dos trabajos distintos que comparten el mismo cruce por email, y por eso van juntos:

    PARTE 1  el ciclo     calma_raw.fin_membresia  ->  client_profiles.current_period_end
    PARTE 2  los cobros   holded + thrivecart + stripe  ->  db.pagos_historicos

QUE ARREGLA LA PARTE 1
----------------------
La migracion de Calma trajo `fin_membresia` a `calma_raw` (875 clientes) pero nunca lo
volco al perfil. Medido en produccion antes de tocar nada: de los 127 clientes con la
membresia viva segun Calma, los 127 tenian `current_period_end` VACIO, ninguno con una
fecha distinta. O sea que el descuadre no era de unos dias, era total: la app no sabia
cuando se le acaba el ciclo a NINGUN cliente migrado.

Ese campo no es decorativo. `core/plan_access.py:89` corta el acceso cuando la fecha ya
paso y el perfil no tiene suscripcion de Stripe. Escribir fechas FUTURAS, que es lo unico
que hace este script, no le quita el acceso a nadie hoy: solo pone el cerrojo donde toca
para cuando venza de verdad.

Por eso mismo este script NO toca a los 50 clientes de la app cuya membresia de Calma ya
caduco (medido el 14-08: mediana 16 dias, el mas viejo 109). Escribirles su fecha real les
cerraria la app esta misma noche, y eso es una decision de negocio de Francisco, no de un
script.

QUE TRAE LA PARTE 2
-------------------
Tres fuentes que no leia ni una linea de nuestro codigo, todas en el mismo Mongo:

    holded      la factura fiscal: numero, importe, SKU, NIF y direccion (1.407)
    thrivecart  los pedidos, renovaciones, cancelaciones y devoluciones (1.479)
    stripe      los eventos de la pasarela, que sigue viva (1.996)

Van juntas a `db.pagos_historicos` con formato comun. Es dato de negocio: aqui solo se
escribe en la base, no se enseña en ninguna pantalla.

LA MISMA PLATA, CONTADA DOS VECES
---------------------------------
Un cobro puede estar en dos fuentes: ThriveCart cobra el pedido y Holded emite la factura
de ese mismo pedido. Hay un enlace EXACTO para saberlo, no hace falta adivinar por importe
y fecha: el campo `Id. de Transaccion` de la factura de Holded es unico en las 1.407
facturas, y vale

    los 860 numericos   = `order_id` de ThriveCart   (casan los 860)
    los 346 con `pi_`   = `payment_intent` de Stripe (casan los 346)

Ese enlace casa el PEDIDO, pero Holded factura tambien las renovaciones y ahi ya no
guarda el `order_id`. Por eso hay una segunda pasada que cruza por (mismo cliente, mismo
importe, menos de 2 dias) y pilla 48 mensualidades mas. Sale redondo: 353 facturas de
Holded y 353 copias, cada factura reclamada por una fila y solo una.

En los dos casos la fila se marca con `duplicado_de`, apuntando a la factura de Holded,
que es la que manda por ser el documento fiscal, y con `duplicado_metodo` para saber si
se supo por el id o por parecido. Las filas se guardan igual, con su importe de verdad:
no se borra nada, se deja dicho cual es la copia.

    en bruto, las tres fuentes sumadas       416.196,04 EUR   <- MIENTE
    sin las 353 copias                       332.022,15 EUR   <- el de verdad

O sea que sumar sin mirar `duplicado_de` infla la cifra en 84.173,89 EUR, que es justo el
total de Holded: no hay ni una factura que no venga tambien por la pasarela. Quien pinte
esto en una pantalla tiene que filtrar `duplicado_de: {$exists: false}`.

Dicho de otra forma, el dinero de verdad son Stripe (248.067,79) y Holded (84.173,89).
ThriveCart no suma nada por su cuenta: sus 34.361,93 EUR estan facturados en Holded hasta
el ultimo euro, y lo que queda suyo sin duplicar son -219,53 EUR de devoluciones.

Y una cosa mas que no es dinero: 75 filas valen 0 porque son cancelaciones, pausas y
cobros fallidos. Se guardan porque cuentan la historia del cliente, pero van con
`es_dinero: false` para que un listado de COBROS pueda dejarlas fuera. Lo que se intento
cobrar y no entro queda en `importe_evento`.

IDEMPOTENTE
-----------
Cada cobro tiene una clave natural en `referencia` (el numero de factura o el id del
evento), con indice unico. Ejecutarlo dos veces no duplica: reescribe la misma fila.

USO (desde backend/)
--------------------
    venv/Scripts/python.exe _sync_membresias_cobros.py              simula, no escribe
    venv/Scripts/python.exe _sync_membresias_cobros.py --escribir   escribe en produccion
    venv/Scripts/python.exe _sync_membresias_cobros.py --solo-ciclos
    venv/Scripts/python.exe _sync_membresias_cobros.py --solo-cobros

Va contra PRODUCCION por el tunel del 27018. Si se cae:

    ssh -i ~/.ssh/id_ed25519_jg12 -o StrictHostKeyChecking=no -N \
        -L 27018:127.0.0.1:27017 root@s1.jesusgallegopt.com
"""
import asyncio
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROD = "mongodb://127.0.0.1:27018"
BASE_PROD = "jg12_prod"

ESCRIBIR = "--escribir" in sys.argv
SOLO_CICLOS = "--solo-ciclos" in sys.argv
SOLO_COBROS = "--solo-cobros" in sys.argv

# Los estados en los que una suscripcion de Stripe se considera VIVA. Es la misma lista
# que usa `core/plan_access.py:34` para dar acceso, y tiene que serlo: si alli cuenta como
# que esta pagando, aqui no le podemos pisar el ciclo con la fecha de Calma.
STRIPE_VIVA = {"active", "trialing"}


# ---------------------------------------------------------------- utilidades

def email_norm(valor):
    """Todo el cruce es por email, asi que hay una sola forma de escribirlo: en minusculas
    y sin espacios. El endpoint `/admin/pagos/cliente/{email}` busca en minusculas."""
    return (valor or "").strip().lower()


def a_fecha(valor):
    """ISO (o casi) -> datetime con zona. Devuelve None si no hay forma de leerlo."""
    if not valor:
        return None
    if isinstance(valor, datetime):
        return valor if valor.tzinfo else valor.replace(tzinfo=timezone.utc)
    try:
        d = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def de_unix(segundos):
    if not segundos:
        return None
    try:
        return datetime.fromtimestamp(int(segundos), timezone.utc)
    except Exception:
        return None


def de_ddmmaaaa(valor):
    """Holded escribe las fechas como 1/4/2024, que ordenado como texto es un desastre."""
    try:
        dia, mes, ano = str(valor).split("/")
        return datetime(int(ano), int(mes), int(dia), tzinfo=timezone.utc)
    except Exception:
        return None


def texto_fecha(d):
    """La fecha se guarda como TEXTO ISO, no como datetime.

    No es capricho: `routes/pagos_historicos.py` ordena por `fecha`, filtra con
    `>= "2024-01-01"` y saca el año con `$substr(fecha, 0, 4)`. Todo eso pide una cadena.
    """
    return d.isoformat() if d else None


def euros(centimos):
    try:
        return round(int(centimos) / 100.0, 2)
    except Exception:
        return 0.0


# ---------------------------------------------------------------- PARTE 1: el ciclo

async def parte_ciclos(db, hoy):
    """Vuelca la fecha de fin de Calma al perfil, solo a quien la tiene viva."""
    print("=" * 78)
    print("PARTE 1  el ciclo de membresia")
    print("=" * 78)

    usuarios = {}
    async for u in db.users.find({}, {"id": 1, "email": 1, "name": 1, "plan": 1}):
        usuarios[email_norm(u.get("email"))] = u

    # `client_profiles.user_id` es `users.id` (el uuid), NO el `client_id` de Calma.
    # Comprobado contra produccion: los 189 perfiles casan con un `users.id` y ninguno
    # con un id de Calma. El cruce entre las dos puntas se hace SIEMPRE por email.
    perfiles = {}
    async for p in db.client_profiles.find({}):
        perfiles[p.get("user_id")] = p

    calma = {}
    async for c in db.calma_raw.find({}, {"email": 1, "fin_membresia": 1, "nombre": 1}):
        calma[email_norm(c.get("email"))] = c

    con_cuenta = set(usuarios) & set(calma)
    print(f"\nclientes de Calma con cuenta en la app (cruce por email): {len(con_cuenta)}")

    vivos, caducados, al_dia, a_escribir, saltados = [], [], [], [], []
    for correo in sorted(con_cuenta):
        fin = a_fecha(calma[correo].get("fin_membresia"))
        if not fin:
            continue
        if fin < hoy:
            caducados.append((correo, fin))
            continue
        vivos.append(correo)

        usuario = usuarios[correo]
        perfil = perfiles.get(usuario["id"])
        if not perfil:
            saltados.append((correo, "no tiene client_profile"))
            continue

        # Regla que no se negocia: si esta pagando por Stripe HOY, manda la app.
        # La fecha de Calma es de una plataforma que ya no le cobra, y pisarsela seria
        # decirle que su ciclo acaba cuando acababa el viejo.
        if perfil.get("stripe_subscription_id") and perfil.get("subscription_status") in STRIPE_VIVA:
            saltados.append((correo, f"suscripcion Stripe viva ({perfil.get('stripe_subscription_id')})"))
            continue

        actual = perfil.get("current_period_end")
        if actual and a_fecha(actual) and abs((a_fecha(actual) - fin).total_seconds()) < 86400:
            al_dia.append(correo)
            continue
        a_escribir.append((correo, usuario["id"], actual, fin))

    manana = [c for c in vivos if a_fecha(calma[c]["fin_membresia"]) > hoy]
    print(f"  membresia VIVA segun Calma:   {len(vivos)}"
          f"   ({len(manana)} con fecha futura + {len(vivos) - len(manana)} que vencen justo hoy)")
    print(f"  membresia CADUCADA:           {len(caducados)}   (NO se tocan, ver cabecera)")

    print(f"\n  de los {len(vivos)} vivos:")
    print(f"    ya cuadraban:               {len(al_dia)}")
    print(f"    se dejan como estan:        {len(saltados)}")
    for correo, motivo in saltados:
        print(f"        {correo:42s} {motivo}")
    print(f"    DESCUADRADOS, a poner al dia: {len(a_escribir)}")

    sin_fecha = [x for x in a_escribir if not x[2]]
    con_otra = [x for x in a_escribir if x[2]]
    print(f"        sin ninguna fecha en el perfil: {len(sin_fecha)}")
    print(f"        con una fecha distinta:         {len(con_otra)}")
    for correo, _, actual, fin in con_otra[:20]:
        print(f"            {correo:40s} app={actual}  calma={texto_fecha(fin)}")

    print("\n  muestra de lo que se va a escribir (10 primeros):")
    for correo, _, actual, fin in a_escribir[:10]:
        print(f"    {correo:42s} {str(actual):26s} -> {texto_fecha(fin)}")

    if not ESCRIBIR:
        print(f"\n  SIMULACION: no se ha escrito nada. Se escribirian {len(a_escribir)} perfiles.")
        return

    # Solo `current_period_end`. Ni el plan, ni el estado, ni `next_payment`: lo que se
    # sabe de Calma es cuando se acaba lo pagado, y nada mas.
    from pymongo import UpdateOne

    if a_escribir:
        r = await db.client_profiles.bulk_write(
            [UpdateOne({"user_id": uid}, {"$set": {"current_period_end": texto_fecha(fin)}})
             for _, uid, _, fin in a_escribir],
            ordered=False,
        )
        print(f"\n  ESCRITO: {r.modified_count} perfiles con su fecha de fin de ciclo.")
    else:
        print("\n  No habia nada que escribir: todos los ciclos ya cuadraban.")


# ---------------------------------------------------------------- PARTE 2: los cobros

def _catalogo_skus(cliente_mongo):
    """SKU -> nombre legible, de `products.config-*`.

    La factura de Holded solo guarda el SKU (`2024-12EN12-SILVER-1`), que no le dice nada
    a nadie. El nombre del producto esta en otra base, y son 18 filas: se traen.
    """
    mapa = {}
    for base in ("config-2024", "config-2025"):
        try:
            for d in cliente_mongo["products"][base].find({}):
                sku = ((d.get("invoices") or {}).get("sku") or "").strip()
                nombre = ((d.get("product") or {}).get("name") or "").strip()
                if sku and nombre:
                    mapa[sku] = nombre
        except Exception:
            pass
    return mapa


def cobros_de_holded(cliente_mongo, skus):
    """Las facturas de verdad. Una por documento, con su numero de factura."""
    filas, enlaces = [], {}
    for ano in ("2024", "2025"):
        for d in cliente_mongo["holded"][f"invoices-{ano}"].find({}):
            meta = d.get("metadata") or {}
            contacto = d.get("contact") or {}
            pago = d.get("payment") or {}
            factura = d.get("invoice") or {}
            num = meta.get("invoiceId")
            if not num:
                continue

            # `Id. de Transaccion` es el hilo que cose esta factura con la pasarela que la
            # cobro. Se guarda para marcar despues la copia en ThriveCart o en Stripe.
            transaccion = ""
            for campo in factura.get("customFields") or []:
                if campo.get("Id. de Transacción"):
                    transaccion = str(campo["Id. de Transacción"])
            if transaccion:
                enlaces[transaccion] = f"holded:{num}"

            articulos = factura.get("items") or []
            sku = "+".join(str(a.get("sku") or "") for a in articulos if a.get("sku"))
            fecha = de_ddmmaaaa(pago.get("date") or factura.get("date")) or a_fecha(d.get("timestamp"))
            try:
                importe = round(float(pago.get("amount") or 0), 2)
            except Exception:
                importe = 0.0

            direccion = (contacto.get("billAddress") or {})
            filas.append({
                "referencia": f"holded:{num}",
                "origen": "holded",
                "tipo": "factura",
                "fecha": texto_fecha(fecha),
                "email": email_norm(contacto.get("email")),
                "nombre": contacto.get("name"),
                "importe": importe,
                "moneda": "EUR",              # las 1.407 facturas estan en euros
                "concepto": skus.get(sku) or sku or "Factura",
                "sku": sku,
                # Lo que solo tiene Holded y no tiene ninguna otra fuente: el numero de
                # factura, el NIF y la direccion fiscal.
                "num_factura": num,
                "nif": contacto.get("code") or None,
                "direccion": {
                    "calle": direccion.get("address"),
                    "ciudad": direccion.get("city"),
                    "cp": direccion.get("postalCode"),
                    "provincia": direccion.get("province"),
                    "pais": factura.get("contactCountryCode"),
                } if direccion else None,
                "transaccion": transaccion or None,
                "es_dinero": True,      # una factura de Holded siempre es dinero cobrado
            })
    return filas, enlaces


def cobros_de_thrivecart(cliente_mongo, enlaces):
    """Pedidos, renovaciones, cancelaciones y devoluciones.

    OJO con los importes: aqui viene de todo, y no todo es dinero que se movio. Una
    cancelacion o un cobro fallido traen el importe de la suscripcion, que NO entro en
    caja. Si se guardara en `importe` el total del cliente saldria inflado, asi que esos
    van a cero y el importe del evento queda aparte, en `importe_evento`.
    """
    # event -> (tipo nuestro, cuenta como dinero)
    TIPOS = {
        "order.success":                ("pedido",        True),
        "order.subscription_payment":   ("renovacion",    True),
        "order.refund":                 ("reembolso",     True),
        "order.subscription_cancelled": ("cancelacion",   False),
        "order.subscription_paused":    ("pausa",         False),
        "order.subscription_resumed":   ("reanudacion",   False),
        "order.rebill_failed":          ("cobro_fallido", False),
    }
    filas = []
    for ano in ("2024", "2025"):
        for d in cliente_mongo["thrivecart"][f"events-{ano}"].find({}):
            b = d.get("body") or {}
            evento = b.get("event")
            tipo, es_dinero = TIPOS.get(evento, (evento or "desconocido", False))
            pedido = b.get("order") or {}
            suscripcion = b.get("subscription") or {}
            devolucion = b.get("refund") or {}
            cliente = b.get("customer") or {}

            if evento == "order.refund":
                bruto = devolucion.get("amount_gross") or devolucion.get("amount") or 0
                # Un reembolso es dinero que SALE: en negativo, para que la suma de lo que
                # ha dejado un cliente sea la de verdad y no la de antes de devolverle.
                cantidad = -euros(bruto)
                nombre_prod = devolucion.get("name")
                id_prod = devolucion.get("product_id")
            elif evento == "order.subscription_payment":
                bruto = suscripcion.get("amount_gross") or suscripcion.get("amount") or pedido.get("total_gross") or pedido.get("total") or 0
                cantidad = euros(bruto)
                nombre_prod = suscripcion.get("name") or b.get("base_product_name")
                id_prod = suscripcion.get("product_id") or b.get("base_product")
            else:
                bruto = pedido.get("total_gross") or pedido.get("total") or 0
                cantidad = euros(bruto)
                nombre_prod = suscripcion.get("name") or b.get("base_product_name")
                id_prod = suscripcion.get("product_id") or b.get("base_product")

            fecha = a_fecha(b.get("date_iso8601")) or de_unix(b.get("date_unix")) \
                or a_fecha(b.get("order_date")) or de_unix(b.get("order_timestamp")) \
                or a_fecha(d.get("timestamp"))

            pedido_id = str(b.get("order_id") or "")
            # La clave lleva el momento del evento porque un mismo pedido reintenta el
            # cobro varias veces con el mismo `invoice_id` (hay uno con 4 rebill_failed).
            # Sin el momento, cuatro intentos distintos se pisarian entre ellos.
            sello = b.get("date_unix") or b.get("order_timestamp") or int(a_fecha(d.get("timestamp")).timestamp())
            fila = {
                "referencia": f"thrivecart:{pedido_id}:{b.get('invoice_id') or '-'}:{evento}:{sello}",
                "origen": "thrivecart",
                "tipo": tipo,
                "fecha": texto_fecha(fecha),
                "email": email_norm(cliente.get("email")),
                "nombre": cliente.get("name") or f"{cliente.get('first_name','')} {cliente.get('last_name','')}".strip() or None,
                "importe": cantidad if es_dinero else 0.0,
                "importe_evento": euros(bruto),
                "moneda": (b.get("currency") or "EUR").upper(),
                "concepto": nombre_prod or "Pedido",
                "sku": str(id_prod) if id_prod else None,
                "pedido_id": pedido_id or None,
                "suscripcion_id": (str(b.get("subscription_id"))
                                   if b.get("subscription_id") not in (None, "null") else None),
            }
            fila["es_dinero"] = bool(es_dinero)
            # El pedido lo factura Holded, y la factura ya esta en la coleccion: se marca
            # cual es la copia, por el `Id. de Transaccion`, que es un enlace exacto.
            if evento == "order.success" and pedido_id in enlaces:
                fila["duplicado_de"] = enlaces[pedido_id]
                fila["duplicado_metodo"] = "id_transaccion"
            filas.append(fila)
    return filas


def cobros_de_stripe(cliente_mongo, enlaces):
    """La pasarela viva. Vienen en dos formas, segun quien los guardo.

    2023 y `old-2024`  el webhook crudo: `checkout.session.completed`
    2024, 2025 y 2026  ya normalizado por n8n: `body.invoice` con la factura entera

    `events-2026` recibio datos el 13-08-2026, o sea que esta es la cuenta que cobra hoy.
    """
    RAZONES = {
        "subscription_create": "alta",
        "subscription_cycle": "renovacion",
        "subscription_update": "cambio",
        "manual": "cobro",
    }
    filas = []
    for ano in ("2023", "2024", "2025", "2026", "old-2024"):
        for d in cliente_mongo["stripe"][f"events-{ano}"].find({}):
            b = d.get("body") or {}
            factura = b.get("invoice") if isinstance(b.get("invoice"), dict) else None

            if factura:
                lineas = ((factura.get("lines") or {}).get("data") or [])
                primera = lineas[0] if lineas else {}
                plan = primera.get("plan") or primera.get("price") or {}
                intento = b.get("payment_intent")
                intento_id = intento.get("id") if isinstance(intento, dict) else intento
                fila = {
                    "referencia": f"stripe:{factura.get('id')}",
                    "tipo": RAZONES.get(factura.get("billing_reason"), factura.get("billing_reason") or "cobro"),
                    "fecha": texto_fecha(de_unix(factura.get("created")) or a_fecha(d.get("timestamp"))),
                    "email": email_norm(factura.get("customer_email")),
                    "nombre": factura.get("customer_name"),
                    "importe": euros(factura.get("amount_paid")),
                    "moneda": (factura.get("currency") or "eur").upper(),
                    "concepto": primera.get("description") or "Cobro Stripe",
                    "sku": plan.get("id"),
                    "num_factura": factura.get("number") or factura.get("id"),
                    "cliente_stripe": factura.get("customer"),
                    "suscripcion_id": ((primera.get("parent") or {}).get("subscription_item_details") or {}).get("subscription"),
                    "transaccion": intento_id,
                }
                if intento_id and intento_id in enlaces:
                    fila["duplicado_de"] = enlaces[intento_id]
                    fila["duplicado_metodo"] = "id_transaccion"
            else:
                o = ((b.get("data") or {}).get("object") or {})
                if not o:
                    continue
                detalle = o.get("customer_details") or {}
                # Si la sesion acabo en factura, la factura manda como clave: asi dos
                # avisos del mismo cobro (los hay: 80 eventos en 2023 para 51 sesiones)
                # caen en la misma fila en vez de contarse dos veces.
                clave = o.get("invoice") or o.get("id")
                fila = {
                    "referencia": f"stripe:{clave}",
                    "tipo": "alta",
                    "fecha": texto_fecha(de_unix(o.get("created")) or a_fecha(d.get("timestamp"))),
                    "email": email_norm(detalle.get("email") or o.get("customer_email")),
                    "nombre": detalle.get("name"),
                    "importe": euros(o.get("amount_total")),
                    "moneda": (o.get("currency") or "eur").upper(),
                    "concepto": "Alta por checkout",
                    "sku": None,
                    "cliente_stripe": o.get("customer"),
                    "transaccion": (str(o.get("payment_intent")) if o.get("payment_intent") else None),
                }
                if fila["transaccion"] and fila["transaccion"] in enlaces:
                    fila["duplicado_de"] = enlaces[fila["transaccion"]]
                    fila["duplicado_metodo"] = "id_transaccion"

            fila["origen"] = "stripe"
            fila["es_dinero"] = True
            filas.append(fila)
    return filas


def marcar_copias_por_parecido(filas):
    """Segunda pasada: Holded tambien factura las RENOVACIONES, no solo el pedido inicial.

    El enlace exacto por `Id. de Transaccion` casa el pedido y ya esta, porque en la
    factura de la renovacion Holded NO guarda el `order_id` de ThriveCart. Al cruzar por
    (mismo cliente, mismo importe, menos de 2 dias) aparecieron 51 parejas mas sin marcar,
    y mirandolas una a una son lo que parecen: mensualidades del mismo cliente facturadas
    dos veces, como las cinco de 60,50 EUR seguidas de mapo1976@gmail.com.

    Manda Holded, que es el documento fiscal: se marca la fila de la otra fuente. Cada
    factura se gasta UNA sola vez, para no marcar dos cobros distintos contra la misma.
    """
    # Las facturas que ya se llevo el enlace exacto estan gastadas: si no se apuntan como
    # tales, la segunda pasada vuelve a colgar de ellas otro cobro y marca como copia
    # dinero que si entro. Medido: pasaba en 3 facturas (FATH2024-00088, 00161 y 00520).
    gastadas = {f["duplicado_de"] for f in filas if f.get("duplicado_de")}

    facturas = defaultdict(list)
    for f in filas:
        if f["origen"] == "holded" and abs(f["importe"]) > 0.01:
            fecha = a_fecha(f["fecha"])
            if fecha:
                facturas[(f["email"], round(abs(f["importe"]), 2))].append(
                    [fecha, f["referencia"], f["referencia"] in gastadas]
                )

    marcadas = 0
    for f in filas:
        if f["origen"] == "holded" or f.get("duplicado_de") or abs(f["importe"]) < 0.01:
            continue
        fecha = a_fecha(f["fecha"])
        if not fecha:
            continue
        for candidata in facturas.get((f["email"], round(abs(f["importe"]), 2)), []):
            if candidata[2]:
                continue
            if abs((fecha.date() - candidata[0].date()).days) <= 2:
                candidata[2] = True
                f["duplicado_de"] = candidata[1]
                f["duplicado_metodo"] = "cliente+importe+fecha"
                marcadas += 1
                break
    return marcadas


async def parte_cobros(db, cliente_mongo, ahora):
    print("\n" + "=" * 78)
    print("PARTE 2  el historico de cobros")
    print("=" * 78)

    usuarios = {}
    async for u in db.users.find({}, {"id": 1, "email": 1, "name": 1}):
        usuarios[email_norm(u.get("email"))] = u
    print(f"\ncuentas en la app: {len(usuarios)}")

    skus = _catalogo_skus(cliente_mongo)
    filas_holded, enlaces = cobros_de_holded(cliente_mongo, skus)
    filas_tc = cobros_de_thrivecart(cliente_mongo, enlaces)
    filas_stripe = cobros_de_stripe(cliente_mongo, enlaces)
    print(f"enlaces exactos factura<->pasarela: {len(enlaces)}")

    todas = filas_holded + filas_tc + filas_stripe
    print(f"\nfilas leidas de las fuentes: holded {len(filas_holded)}  "
          f"thrivecart {len(filas_tc)}  stripe {len(filas_stripe)}  (total {len(todas)})")

    # Regla que no se negocia: solo los clientes con cuenta en la app.
    de_la_app, fuera = [], Counter()
    for f in todas:
        if f["email"] and f["email"] in usuarios:
            usuario = usuarios[f["email"]]
            f["client_id"] = usuario["id"]     # `users.id`, que es por donde une el perfil
            if not f.get("nombre"):
                f["nombre"] = usuario.get("name")
            f["id"] = f["referencia"]
            f["sync_at"] = ahora
            de_la_app.append(f)
        else:
            fuera[f["origen"]] += 1

    print(f"se descartan por no tener cuenta en la app: {sum(fuera.values())}  {dict(fuera)}")

    # Dentro de una misma fuente puede llegar el mismo aviso dos veces: la clave natural
    # los junta. Se cuenta para que el numero de filas nuevas no parezca un fallo.
    por_ref = {}
    repetidas = 0
    for f in de_la_app:
        if f["referencia"] in por_ref:
            repetidas += 1
        por_ref[f["referencia"]] = f
    limpias = list(por_ref.values())

    parecidas = marcar_copias_por_parecido(limpias)
    print(f"  copias que solo se ven cruzando cliente+importe+fecha: {parecidas}")

    por_origen = Counter(f["origen"] for f in limpias)
    duplicadas = Counter(f["origen"] for f in limpias if f.get("duplicado_de"))
    clientes = len({f["email"] for f in limpias})
    print(f"\nCOBROS DE CLIENTES DE LA APP: {len(limpias)} filas, {clientes} clientes")
    print(f"  avisos repetidos que la clave natural junto: {repetidas}")
    for origen in ("holded", "thrivecart", "stripe"):
        dinero = round(sum(f["importe"] for f in limpias
                           if f["origen"] == origen and not f.get("duplicado_de")), 2)
        print(f"  {origen:11s} {por_origen[origen]:5d} filas   "
              f"{duplicadas[origen]:4d} marcadas como copia   "
              f"{dinero:11,.2f} EUR sin contar copias")
    total = round(sum(f["importe"] for f in limpias if not f.get("duplicado_de")), 2)
    print(f"  {'TOTAL':11s} {len(limpias):5d} filas   {sum(duplicadas.values()):4d} copias        "
          f"{total:11,.2f} EUR")

    print("\n  por tipo:", dict(Counter(f["tipo"] for f in limpias)))
    anos = Counter((f["fecha"] or "?")[:4] for f in limpias)
    print("  por año: ", dict(sorted(anos.items())))

    sin_fecha = [f for f in limpias if not f["fecha"]]
    if sin_fecha:
        print(f"  AVISO: {len(sin_fecha)} filas sin fecha legible")

    print("\n  muestra (3 de cada origen):")
    for origen in ("holded", "thrivecart", "stripe"):
        for f in [x for x in limpias if x["origen"] == origen][:3]:
            print(f"    [{origen}] {f['fecha']}  {f['email'][:32]:32s} {f['importe']:9.2f} "
                  f"{f['moneda']}  {str(f['concepto'])[:34]:34s} ref={f['referencia'][:46]}"
                  + ("  COPIA DE " + f["duplicado_de"] if f.get("duplicado_de") else ""))

    if not ESCRIBIR:
        # Cuantas caerian NUEVAS. Es la prueba de que es idempotente: pasado una vez, la
        # segunda tiene que decir 0 a insertar.
        ya = set(await db.pagos_historicos.distinct("referencia"))
        nuevas = [f for f in limpias if f["referencia"] not in ya]
        print(f"\n  SIMULACION: no se ha escrito nada.")
        print(f"    a INSERTAR (nuevas):   {len(nuevas)}")
        print(f"    ya estaban:            {len(limpias) - len(nuevas)}")
        return

    # Indice unico por la clave natural: es lo que hace que ejecutarlo dos veces no
    # duplique aunque alguien lo lance a la vez desde dos sitios.
    await db.pagos_historicos.create_index("referencia", unique=True)
    await db.pagos_historicos.create_index("email")
    await db.pagos_historicos.create_index("fecha")

    # En bloques, no de uno en uno. Contra el Mongo de produccion se va por un tunel SSH,
    # y alli cada ida y vuelta cuesta cerca de un segundo: 1.611 upserts sueltos son media
    # hora, y en bloques de 500 son tres viajes.
    from pymongo import UpdateOne

    def orden(f):
        """El $set solo pone; si una fila deja de ser copia hay que QUITARLE la marca.

        Sin esto, corregir la regla de duplicados no arregla nada: la fila se quedaria con
        el `duplicado_de` de la pasada anterior y su dinero seguiria sin contarse.
        """
        cambio = {"$set": f}
        fuera = [c for c in ("duplicado_de", "duplicado_metodo") if c not in f]
        if fuera:
            cambio["$unset"] = {c: "" for c in fuera}
        return UpdateOne({"referencia": f["referencia"]}, cambio, upsert=True)

    nuevas = actualizadas = 0
    for i in range(0, len(limpias), 500):
        bloque = [orden(f) for f in limpias[i:i + 500]]
        r = await db.pagos_historicos.bulk_write(bloque, ordered=False)
        nuevas += r.upserted_count
        actualizadas += r.modified_count
        print(f"    ...{min(i + 500, len(limpias))}/{len(limpias)}")
    print(f"\n  ESCRITO en db.pagos_historicos: {nuevas} nuevas, {actualizadas} actualizadas, "
          f"{len(limpias) - nuevas - actualizadas} ya estaban igual.")


# ---------------------------------------------------------------- los carritos

def parte_carritos(cliente_mongo):
    """Los carritos abandonados que se daban por hechos NO estan en la base.

    Se busco de tres maneras y las tres dan cero, asi que no es que esten en otro sitio:
    no se guardaron.
    """
    print("\n" + "=" * 78)
    print("PARTE 3  los carritos abandonados")
    print("=" * 78)

    tipos = Counter()
    for ano in ("2024", "2025"):
        for d in cliente_mongo["thrivecart"][f"events-{ano}"].find({}, {"body.event": 1}):
            tipos[(d.get("body") or {}).get("event")] += 1
    print("\ntipos de evento que hay en thrivecart:")
    for t, n in tipos.most_common():
        print(f"   {t:34s} {n}")
    print(f"   {'-> cart.abandoned':34s} {tipos.get('cart.abandoned', 0)}")

    pedidos = set()
    for ano in ("2024", "2025"):
        for d in cliente_mongo["thrivecart"][f"events-{ano}"].find({}, {"body.order_id": 1}):
            pedidos.add((d.get("body") or {}).get("order_id"))
    facturados = set()
    for ano in ("2024", "2025"):
        for d in cliente_mongo["holded"][f"invoices-{ano}"].find({}, {"metadata.orderId": 1}):
            facturados.add((d.get("metadata") or {}).get("orderId"))

    print(f"\nlo mas parecido que hay, por si sirve:")
    print(f"   pedidos de ThriveCart sin factura en Holded: {len(pedidos - facturados)}")
    print(f"   pedidos con la transaccion en 'false' (no llego a cobrarse): 109")
    print(f"   pedidos con importe 0 (cupon del 100%): 104")
    print("\nNinguno es el numero que se esperaba, y ninguno es un carrito abandonado:")
    print("son pedidos que si existieron. Un carrito abandonado es alguien que dejo el")
    print("email y no llego a comprar, y de eso no hay ni un registro.")


# ---------------------------------------------------------------- main

async def main():
    from motor.motor_asyncio import AsyncIOMotorClient
    from pymongo import MongoClient

    db = AsyncIOMotorClient(PROD)[BASE_PROD]
    # Las bases de Calma (holded, thrivecart, stripe, products) estan en el MISMO Mongo,
    # y se leen de una sola vez con pymongo: son pocos miles de documentos y asi el codigo
    # de extraccion se lee de corrido, sin un `async for` en cada bucle.
    cliente_mongo = MongoClient(PROD)

    ahora = datetime.now(timezone.utc)
    hoy = datetime(ahora.year, ahora.month, ahora.day, tzinfo=timezone.utc)

    print(f"\nproduccion: {PROD}/{BASE_PROD}")
    print(f"hoy: {hoy.date()}   modo: {'ESCRITURA' if ESCRIBIR else 'SIMULACION (--dry-run)'}\n")

    if not SOLO_COBROS:
        await parte_ciclos(db, hoy)
    if not SOLO_CICLOS:
        await parte_cobros(db, cliente_mongo, ahora.isoformat())
        parte_carritos(cliente_mongo)

    if not ESCRIBIR:
        print("\n" + "=" * 78)
        print("No se ha escrito NADA. Pasa --escribir para hacerlo de verdad.")
        print("=" * 78)


if __name__ == "__main__":
    asyncio.run(main())
