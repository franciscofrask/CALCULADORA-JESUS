"""
Trae a 12EN12 los protocolos de suplementacion que cada cliente tiene en Calma (punto 4.15).

EL PROBLEMA
-----------
El cliente que viene de Calma abre Suplementacion y se encuentra la pantalla vacia. El
catalogo ya esta (106 entradas en `db.supplements`, importadas el 19-05-2026); lo que
faltaba era QUE PROTOCOLO tiene puesto cada uno. Eso se barrio de las 145 fichas de Calma
y esta en `_calma_ref/suplementos_por_cliente.json` (fuera de git: son datos personales).

Cada linea del historico de Calma es texto plano con la fecha delante:

    "2026-8-10: Whey Isolate + crema de arroz, Hydropeptides o MAP, Creatina hombre y
     Sinefrina con termogenico mes 1 (1 capsula primeras 2 semanas y a partir de la 3 sube a 1 y 1)"

EL EMPAREJAMIENTO: DONDE ESTA DE VERDAD EL CATALOGO
---------------------------------------------------
Hay DOS colecciones y es facil confundirlas:

  - `db.supplement_catalog` (16 entradas "seed-*") es lo que edita el admin en la app. Ahi
    el titulo es el nombre canonico y generico: "Monohidrato de creatina", "Omega 3".
  - `db.supplements` (106 entradas) es el catalogo REAL importado de la web de Jesus. Ahi
    `categoria` es el nombre canonico y `nombre` es la VARIANTE concreta, con el sexo, el
    mes y la dosis pegados: "Creatina hombre", "Omega 3 hombre", "Fat burner hardcore mes 1".

Contra las 16 semillas casi nada casa (de ahi el "solo 11 de 53" que se habia medido). Contra
`db.supplements.nombre` casa TODO: la ficha de Calma y este catalogo salen de la misma lista,
asi que el texto de la ficha ES el nombre de la variante, literal. Medido sobre el historico
entero: 83 items literales distintos, 83 emparejados en la fase 1 (exacto por nombre), 0 por
categoria, 0 por reglas de raiz, 0 por excepcion, 0 sin emparejar.

Aun asi el emparejador va por fases y no por tabla, porque el dia que Jesus escriba una
variante nueva a mano ("Creatina mujer 5 g") hay que resolverla sola y no dejar el protocolo
cojo. Las fases van de mas exacta a mas tolerante:

    1. exacto por `nombre`      -> se queda la variante con SU dosis (lo que queremos)
    2. exacto por `categoria`   -> el generico; se coge la primera variante de esa categoria
    3. sin el parentesis final  -> "Selenio 1 capsula (con la cena)" -> "Selenio 1 capsula"
    4. por raiz                 -> se le quitan los sufijos de variante (sexo, "mes N",
                                   "N dosis", "N perlas", "N tomas", "Ng", "suelta",
                                   "protocolo ...") y se compara contra la raiz del catalogo
    5. EXCEPCIONES              -> lo que no sale por reglas, a mano y con el porque

TROCEAR LA LINEA
----------------
Se corta por comas y por " y ", pero solo a nivel 0 de parentesis: dentro de un parentesis
esos dos separadores son parte de la dosis ("1 y 1 las semanas 2 y 3", "subir HDL, 2 meses")
y partir por ahi rompe el nombre. Comprobado que ningun nombre del catalogo lleva coma ni
" y " fuera de parentesis, asi que no hay riesgo de partir uno por la mitad.

QUE SE ESCRIBE
--------------
El mismo formato que deja `_migrar_protocolos_suplementos.py` y que lee `routes/supplements.py`:
un documento por cliente en `db.supplement_protocols` con `versiones` = lista de
{fecha, items, nota, guardado_por, guardado_at}, resuelta por la mas reciente que no pase de
hoy. Se migra el historico ENTERO, no solo la linea vigente: ya viene versionado por fecha,
que es justo lo que el formato nuevo sabe guardar.

`nota` va a None a proposito. El campo `observaciones` de la ficha de Calma son apuntes
internos del coach ("no tiene maq de aperturas", conversaciones de soporte) y la pantalla del
cliente pinta `nota` como "Nota personal": ensenarselo seria filtrarle notas que no son suyas.

Lo que ya hubiera en 12EN12 NO se pisa: si un cliente ya tiene una version guardada en una
fecha, esa fecha se respeta y se avisa. Calma es el pasado; lo que haya tocado un coach aqui
manda.

USO
---
    venv/Scripts/python.exe _importar_suplementos_calma.py             simula, no escribe
    venv/Scripts/python.exe _importar_suplementos_calma.py --detalle   + el desglose por cliente
    venv/Scripts/python.exe _importar_suplementos_calma.py --escribir  escribe (solo en dev)

Por defecto se conecta a lo que diga `backend/.env` (dev, Atlas). Con `--url`/`--db` se puede
apuntar a otra base PERO SOLO PARA SIMULAR: escribir esta bloqueado si no es la de `.env`.
Escribir protocolos en produccion es tocar datos de clientes reales y lo autoriza Francisco.
"""
import argparse
import asyncio
import collections
import io
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv                       # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient   # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE, ".env"))

FICHERO = os.path.join(BASE, "..", "_calma_ref", "suplementos_por_cliente.json")

# Quien firma las versiones importadas. Se ve en el historico del admin: interesa que se
# distinga de un guardado hecho por un coach dentro de la app.
FIRMA = "Importado de Calma"

# Cuentas de Jesus, no clientes. Tienen ficha en Calma porque el sistema se probaba con
# ellas, pero su "protocolo" no es de nadie y no debe aparecer en la pantalla de nadie.
EXCLUIDOS = {
    "admin@jesusgallegopt.com",
    "hola@jesusgallegopt.com",
}

# Excepciones: nombres que no resuelve ninguna regla. Hoy esta vacia (los 83 items del
# historico casan en la fase 1) y esa es la señal de que el emparejador esta bien, no de que
# falte trabajo. Se deja para poder anotar el caso raro con su porque, como en
# `_contrastar_suplementos.py` (ahi «silimarina» = «cardo mariano», que no sale por reglas
# porque son dos palabras distintas para la misma planta).
EXCEPCIONES: dict[str, str] = {
    # "silimarina": "cardo mariano",   # ejemplo: la silimarina es el extracto del cardo
}

# Sufijos que en Calma distinguen VARIANTES del mismo suplemento. Quitarlos da la raiz, que
# es lo que casa con la `categoria` del catalogo. El orden no importa: se aplican en bucle
# hasta que no quede ninguno.
SUFIJOS_VARIANTE = [
    r"\b(hombre|mujer|hombres|mujeres)\b",              # "Creatina hombre"
    r"\bmes\s*\d+\b",                                   # "Fat burner hardcore mes 1"
    r"\bmeses?\s*\d+\b",
    r"\bprotocolo\b.*$",                                # "Cafeina anhidra mes 1 protocolo light"
    r"\bfinalizacion\b.*$",
    r"\bsubida\b|\bbajada\b",
    r"\b\d+\s*(dosis|perlas?|capsulas?|caps?|tomas?|g|gr|mg|mcg)\b",   # "Pre-workout 3 dosis"
    r"\bsuelta\s*\d*\b",                                # "Cafeina anhidra 200 mg suelta 2"
    r"\bcon dosis marcada\b",
    r"\b\d+$",                                          # numero suelto al final
]


# ── Normalizacion ────────────────────────────────────────────────────────
def norm(s: str) -> str:
    """Minusculas, sin acentos y sin puntuacion. Se conservan `+` y `%` porque distinguen
    suplementos de verdad ("Vitamina D3 + K2", "CBD 40%")."""
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+% ]", " ", s)).strip()
    # El catalogo escribe el mismo suplemento de las dos formas ("CBD 40%" y "Aceite de CBD
    # al 40 %"), asi que el espacio antes del % no puede contar.
    return re.sub(r"\s+%", "%", s)


def sexo_de(s: str) -> str | None:
    """"Creatina mujer" -> "mujer". None si el texto no dice el sexo."""
    t = norm(s)
    if re.search(r"\bmujeres?\b", t):
        return "mujer"
    if re.search(r"\bhombres?\b", t):
        return "hombre"
    return None


def sin_parentesis(s: str) -> str:
    """Quita el parentesis final, que en Calma es la explicacion de la pauta y no el nombre."""
    return re.sub(r"\s*\([^()]*\)\s*$", "", s or "").strip()


def raiz(s: str) -> str:
    """El nombre sin los sufijos que solo marcan la variante."""
    r = norm(sin_parentesis(s))
    cambio = True
    while cambio:
        cambio = False
        for pat in SUFIJOS_VARIANTE:
            nuevo = re.sub(pat, " ", r)
            nuevo = re.sub(r"\s+", " ", nuevo).strip()
            if nuevo != r and nuevo:
                r, cambio = nuevo, True
    return r


# ── Trocear la linea ─────────────────────────────────────────────────────
def trocear(texto: str) -> list[str]:
    """Parte "A, B y C" en [A, B, C] respetando los parentesis (ver cabecera)."""
    partes, buf, nivel, i = [], "", 0, 0
    while i < len(texto):
        c = texto[i]
        if c == "(":
            nivel += 1
        elif c == ")":
            nivel = max(0, nivel - 1)
        if nivel == 0 and c == ",":
            partes.append(buf)
            buf, i = "", i + 1
            continue
        if nivel == 0 and texto[i:i + 3] == " y ":
            partes.append(buf)
            buf, i = "", i + 3
            continue
        buf += c
        i += 1
    partes.append(buf)
    return [p.strip(" .;") for p in partes if p.strip(" .;")]


def parsear_linea(linea: str):
    """"2026-8-10: A, B y C" -> ("2026-08-10", ["A", "B", "C"]). None si no lleva fecha."""
    m = re.match(r"^\s*(\d{4})-(\d{1,2})-(\d{1,2})\s*:\s*(.*)$", linea or "", re.S)
    if not m:
        return None
    a, mes, dia, cuerpo = m.groups()
    return f"{int(a):04d}-{int(mes):02d}-{int(dia):02d}", trocear(cuerpo)


# ── El emparejador ───────────────────────────────────────────────────────
class Emparejador:
    """De la fase 2 en adelante se pierde la variante exacta y hay que elegir una entre
    varias ("Omega 3" tiene version de hombre y de mujer). Elegir mal el sexo es peor que no
    emparejar, asi que se desempata con el sexo que diga el propio texto y, si no lo dice,
    con el del cliente, que la ficha de Calma tambien trae."""

    def __init__(self, catalogo: list[dict]):
        self.por_nombre = {norm(s["nombre"]): s for s in catalogo}
        self.por_categoria: dict[str, list[dict]] = {}
        self.por_raiz: dict[str, list[dict]] = {}
        for s in catalogo:
            self.por_categoria.setdefault(norm(s.get("categoria") or ""), []).append(s)
            for r in {raiz(s.get("categoria") or ""), raiz(s["nombre"])}:
                if r:
                    self.por_raiz.setdefault(r, []).append(s)
        self.fases = collections.Counter()

    def _elegir(self, candidatos: list[dict], sexo: str | None) -> dict:
        """El primero que cuadre de sexo; si ninguno lo dice, el primero (el catalogo ya
        viene en el orden en que Jesus los publica)."""
        if sexo:
            for c in candidatos:
                if sexo_de(c["nombre"]) == sexo:
                    return c
        neutros = [c for c in candidatos if sexo_de(c["nombre"]) is None]
        return (neutros or candidatos)[0]

    def __call__(self, texto: str, sexo_cliente: str | None = None):
        """Devuelve (suplemento, fase) o (None, "sin_emparejar")."""
        sexo = sexo_de(texto) or sexo_cliente
        k = norm(texto)
        if k in self.por_nombre:
            self.fases["1-nombre"] += 1
            return self.por_nombre[k], "1-nombre"
        if k in self.por_categoria:
            self.fases["2-categoria"] += 1
            return self._elegir(self.por_categoria[k], sexo), "2-categoria"

        sp = norm(sin_parentesis(texto))
        if sp and sp != k:
            if sp in self.por_nombre:
                self.fases["3-sin-parentesis"] += 1
                return self.por_nombre[sp], "3-sin-parentesis"
            if sp in self.por_categoria:
                self.fases["3-sin-parentesis"] += 1
                return self._elegir(self.por_categoria[sp], sexo), "3-sin-parentesis"

        r = raiz(texto)
        if r and r in self.por_raiz:
            self.fases["4-raiz"] += 1
            return self._elegir(self.por_raiz[r], sexo), "4-raiz"

        exc = EXCEPCIONES.get(k) or EXCEPCIONES.get(sp) or EXCEPCIONES.get(r)
        if exc:
            if norm(exc) in self.por_nombre:
                self.fases["5-excepcion"] += 1
                return self.por_nombre[norm(exc)], "5-excepcion"
            if norm(exc) in self.por_categoria:
                self.fases["5-excepcion"] += 1
                return self._elegir(self.por_categoria[norm(exc)], sexo), "5-excepcion"

        self.fases["sin_emparejar"] += 1
        return None, "sin_emparejar"


# ── Del catalogo al item del protocolo ───────────────────────────────────
def _cuando_cuanto(descripcion: str) -> tuple[str, str]:
    """"¿Cuando? X · ¿Cuanto? Y" -> ("X", "Y"). Los 106 del catalogo vienen asi."""
    d = (descripcion or "").replace("\n", " ")
    cuando = cuanto = ""
    m = re.search(r"¿Cu[áa]ndo\?\s*(.*?)(?=·|¿Cu[áa]nto\?|$)", d)
    if m:
        cuando = m.group(1).strip(" ·")
    m = re.search(r"¿Cu[áa]nto\?\s*(.*)$", d)
    if m:
        cuanto = m.group(1).strip(" ·")
    if not cuando and not cuanto:
        cuanto = d.strip()
    return cuando, cuanto


def a_item(s: dict) -> dict:
    """Snapshot del suplemento con la forma de `ProtocolItem` (models/supplements.py)."""
    enlaces = []
    for e in s.get("enlaces") or []:
        url = e.get("url") if isinstance(e, dict) else e
        if url:
            enlaces.append(url)
    # `imagen` en db.supplements es un nombre de fichero suelto ("tarro.webp"), no una URL, y
    # la pantalla lo mete tal cual en un <img src>. Meterlo daria una imagen rota en cada
    # tarjeta, asi que solo se copia si de verdad es una URL. Pendiente de decision: donde se
    # sirven esas imagenes.
    imagen = s.get("imagen") if str(s.get("imagen") or "").startswith("http") else None
    cuando, cuanto = _cuando_cuanto(s.get("descripcion"))
    return {
        "catalog_id": s.get("id"),
        "titulo": s.get("nombre") or "",
        "imagen": imagen,
        "enlaces": enlaces,
        "cuando": cuando,
        "cuanto": cuanto,
        "observaciones": s.get("notas") or None,
    }


def versiones_previas(previo: dict) -> list[dict]:
    """Lo que este cliente ya tiene guardado en 12EN12, siempre como lista de versiones.

    Ojo con los protocolos que todavia estan en el formato viejo (`actual` + `siguiente` +
    `siguiente_fecha`, sin `versiones`): `routes/supplements.py` ya solo mira `versiones`, asi
    que si importamos sin convertirlos, lo que un coach asigno aqui se queda invisible y el
    cliente pasa a ver el protocolo de Calma. Se convierten con el mismo criterio que
    `_migrar_protocolos_suplementos.py` (la fecha de `updated_at` para `actual`, la suya para
    `siguiente`) y despues las fechas de 12EN12 ganan a las de Calma.
    """
    if previo.get("versiones"):
        return list(previo["versiones"])
    out = []
    cuando = str(previo.get("updated_at") or "")[:10]
    if previo.get("actual") and cuando:
        out.append({"fecha": cuando, "items": previo["actual"], "nota": previo.get("nota"),
                    "guardado_por": None, "guardado_at": previo.get("updated_at")})
    if previo.get("siguiente") and previo.get("siguiente_fecha"):
        out.append({"fecha": str(previo["siguiente_fecha"])[:10], "items": previo["siguiente"],
                    "nota": previo.get("nota"), "guardado_por": None,
                    "guardado_at": previo.get("updated_at")})
    return sorted(out, key=lambda v: v["fecha"])


# ── Programa ─────────────────────────────────────────────────────────────
async def main(args):
    url_env = os.environ["MONGO_URL"]
    db_env = os.environ.get("DB_NAME", "jg12_restored")
    url, dbn = args.url or url_env, args.db or db_env

    # Escribir protocolos en produccion es tocar datos de clientes reales. El guard sigue
    # puesto: la unica forma de saltarselo es teclear la llave entera a mano, que no se
    # escribe por accidente ni se queda pegada en un historial de comandos util.
    # Francisco lo autorizo el 09-08-2026 ("escribe los suplementos, ensenalos") para la
    # importacion inicial de Calma. Cualquier otra vez hay que volver a pedirlo.
    if args.escribir and (url != url_env or dbn != db_env):
        if not args.escribir_en_produccion_autorizado:
            sys.exit("NO. --escribir solo vale contra la base de backend/.env (dev). "
                     "Escribir protocolos en produccion lo autoriza Francisco.")
        print(">>> ESCRITURA EN PRODUCCION autorizada por Francisco (09-08-2026). <<<\n")

    db = AsyncIOMotorClient(url)[dbn]
    catalogo = await db.supplements.find({}, {"_id": 0}).to_list(None)
    if not catalogo:
        sys.exit("db.supplements esta vacia: sin catalogo no hay nada que emparejar.")

    users = await db.users.find({}, {"_id": 0, "id": 1, "email": 1, "name": 1}).to_list(None)
    por_email = {(u.get("email") or "").strip().lower(): u for u in users}
    perfiles = await db.client_profiles.find({}, {"_id": 0, "id": 1, "user_id": 1}).to_list(None)
    por_user = {}
    for p in perfiles:
        por_user.setdefault(p["user_id"], p)
    previos = {d["client_id"]: d for d in
               await db.supplement_protocols.find({}, {"_id": 0}).to_list(None)}

    datos = json.load(io.open(FICHERO, encoding="utf-8-sig"))["clientes"]
    emparejar = Emparejador(catalogo)
    ahora = datetime.now(timezone.utc).isoformat()
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    plan, sin_usuario, sin_historico, sin_emparejar = [], [], [], collections.Counter()
    fechas_respetadas, legado, excluidos = [], [], []

    for email, ficha in sorted(datos.items()):
        historico = ficha.get("historico") or []
        if email.strip().lower() in EXCLUIDOS:
            if historico:
                excluidos.append((email, len(historico)))
            continue
        if not historico:
            sin_historico.append(email)
            continue
        u = por_email.get(email.strip().lower())
        perfil = por_user.get(u["id"]) if u else None
        if not perfil:
            sin_usuario.append((email, ficha.get("nombre"), len(historico)))
            continue

        # El sexo del cliente solo se usa para desempatar cuando el texto no dice la variante
        # (ver Emparejador). Con los datos de hoy no llega a hacer falta.
        sexo_cliente = sexo_de(ficha.get("sexo") or "")

        # Una version por fecha. Si Calma repite fecha, gana la ultima linea escrita.
        versiones: dict[str, dict] = {}
        for linea in historico:
            parsed = parsear_linea(linea)
            if not parsed:
                continue
            fecha, textos = parsed
            items = []
            for t in textos:
                s, fase = emparejar(t, sexo_cliente)
                if s is None:
                    sin_emparejar[t] += 1
                    continue
                items.append(a_item(s))
            if items:
                versiones[fecha] = {"fecha": fecha, "items": items, "nota": None,
                                    "guardado_por": FIRMA, "guardado_at": ahora}

        # Lo que ya haya en 12EN12 manda: esas fechas no se tocan.
        previo = previos.get(perfil["id"]) or {}
        antes = versiones_previas(previo)
        if previo and not previo.get("versiones") and antes:
            legado.append((email, [v["fecha"] for v in antes]))
        ya = {str(v.get("fecha"))[:10] for v in antes}
        choques = sorted(ya & set(versiones))
        for f in choques:
            versiones.pop(f, None)
        if choques:
            fechas_respetadas.append((email, choques))

        if not versiones:
            continue
        final = sorted(antes + list(versiones.values()), key=lambda v: str(v["fecha"])[:10])
        plan.append({"email": email, "nombre": ficha.get("nombre"), "client_id": perfil["id"],
                     "nuevas": sorted(versiones), "versiones": final,
                     "tenia_previo": bool(previo)})

    # ── Informe ──────────────────────────────────────────────────────────
    print(f"Base: {dbn} ({'.env / dev' if url == url_env else url})")
    print(f"Catalogo db.supplements: {len(catalogo)} suplementos\n")

    print(f"CLIENTES  ({len(datos)} fichas de Calma)")
    print(f"  {len(plan):3}  con protocolo que importar")
    print(f"  {len(sin_historico):3}  sin historico en Calma (nada que traer)")
    print(f"  {len(sin_usuario):3}  con historico pero SIN cliente en 12EN12")
    for e, n, c in sin_usuario:
        print(f"         - {e}  ({n}, {c} lineas)")
    print(f"  {len(excluidos):3}  excluidos por no ser clientes (cuentas de Jesus)")
    for e, c in excluidos:
        print(f"         - {e}  ({c} lineas, NO se importan)")

    total_items = sum(len(v["items"]) for p in plan for v in p["versiones"])
    nuevas = sum(len(p["nuevas"]) for p in plan)
    print(f"\nVERSIONES")
    print(f"  {nuevas:4}  versiones nuevas (una por fecha del historico)")
    print(f"  {total_items:4}  items de suplemento en total")
    if fechas_respetadas:
        print(f"  {len(fechas_respetadas):4}  clientes con fechas ya usadas en 12EN12 (se respetan):")
        for e, f in fechas_respetadas:
            print(f"         - {e}: {', '.join(f)}")
    if legado:
        print(f"  {len(legado):4}  clientes cuyo protocolo de 12EN12 estaba en el formato viejo")
        print("         (se convierte a version con fecha para que no se pierda):")
        for e, f in legado:
            print(f"         - {e}: {', '.join(f)}")

    print(f"\nEMPAREJAMIENTO (items procesados, con repeticion)")
    for fase, n in sorted(emparejar.fases.items()):
        print(f"  {n:5}  {fase}")
    if sin_emparejar:
        print(f"\n  SIN EMPAREJAR: {len(sin_emparejar)} textos distintos")
        for t, n in sin_emparejar.most_common():
            print(f"     {n:4}  {t}")
    else:
        print("\n  Sin emparejar: ninguno.")

    # Cuantos veran algo HOY: la version vigente es la ultima que no pase de hoy. Si el
    # historico entero es futuro, la pantalla sigue vacia hasta esa fecha (a proposito).
    futuros = [p for p in plan if all(str(v["fecha"])[:10] > hoy for v in p["versiones"])]
    con_futura = [p for p in plan if any(str(v["fecha"])[:10] > hoy for v in p["versiones"])]
    print(f"\nEFECTO EN LA PANTALLA (hoy {hoy})")
    print(f"  {len(plan) - len(futuros):3}  clientes verian ya su protocolo actual")
    print(f"  {len(con_futura):3}  ademas con una version futura ('Suplementacion siguiente')")
    if futuros:
        print(f"  {len(futuros):3}  solo con versiones futuras (seguirian viendo la pantalla vacia):")
        for p in futuros:
            print(f"         - {p['email']} (desde {p['versiones'][0]['fecha']})")

    # Traer un protocolo de hace tres años y presentarselo al cliente como "tu suplementacion
    # actual" no es traer un dato, es afirmar algo que probablemente ya no es verdad. Se
    # cuentan aparte para que se decida si entran o no.
    corte = f"{int(hoy[:4]) - 1}{hoy[4:]}"
    viejos = [p for p in plan if p["versiones"][-1]["fecha"] < corte]
    if viejos:
        print(f"\n  OJO: {len(viejos)} de los {len(plan)} no tocan su protocolo desde hace mas de un año")
        print(f"  (ultima version anterior a {corte}). Decidir si se importan igual:")
        for p in sorted(viejos, key=lambda p: p["versiones"][-1]["fecha"]):
            print(f"         - {p['versiones'][-1]['fecha']}  {p['email']}")

    if args.detalle:
        print("\nDESGLOSE POR CLIENTE")
        for p in plan:
            marca = " [ya tenia protocolo]" if p["tenia_previo"] else ""
            print(f"\n  {p['email']}  ->  client_id {p['client_id'][:8]}…{marca}")
            for v in p["versiones"]:
                titulos = ", ".join(i["titulo"] for i in v["items"])
                print(f"     {v['fecha']}  ({len(v['items'])}) {titulos[:150]}")

    if not args.escribir:
        print(f"\nSIMULACION: no se ha escrito nada. Escribiria {len(plan)} documentos en "
              f"db.supplement_protocols ({nuevas} versiones nuevas). Pasa --escribir.")
        return

    for p in plan:
        await db.supplement_protocols.update_one(
            {"client_id": p["client_id"]},
            {"$set": {"client_id": p["client_id"], "versiones": p["versiones"],
                      "updated_at": ahora}},
            upsert=True)
    print(f"\nESCRITO en {dbn}: {len(plan)} documentos de db.supplement_protocols.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--escribir", action="store_true", help="escribe (solo contra la base de .env)")
    ap.add_argument("--detalle", action="store_true", help="desglose cliente a cliente")
    ap.add_argument("--url", help="otra MONGO_URL, SOLO para simular")
    ap.add_argument("--db", help="otra base, SOLO para simular")
    ap.add_argument("--escribir-en-produccion-autorizado", action="store_true",
                    help="levanta el guard de produccion; solo con permiso expreso de Francisco")
    asyncio.run(main(ap.parse_args()))
