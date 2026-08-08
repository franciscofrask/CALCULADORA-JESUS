"""Búsqueda semántica del catálogo de alimentos (db.food_embeddings).

Sustituye a la tabla de sinónimos escrita a mano (query_mappings): "tostadas" encuentra
el pan tostado porque están cerca en significado, no porque alguien escribiera esa
equivalencia. Igual con "comida líquida" o "algo para llevar al trabajo", que ninguna
tabla iba a prever.

Cómo funciona:
  - Cada alimento tiene UN vector, calculado una vez por `_generar_embeddings.py` a partir
    de su nombre + la ruta de nombres de sus categorías + sus etiquetas transversales.
    Se guarda en db.food_embeddings (binario float32, ~6 KB por alimento).
  - En cada búsqueda se vectoriza el texto del cliente (una llamada a la API de OpenAI,
    ~100 ms, con caché en memoria para repetidos) y se compara por coseno contra TODO el
    catálogo con numpy. Con 3.211 alimentos son milisegundos: no hace falta base vectorial.

Mantenimiento: al crear o renombrar un alimento hay que recalcular su vector (llamar a
`indexar_alimento`). Si no, el alimento nuevo es invisible para esta búsqueda; la
generación completa (`_generar_embeddings.py`) es re-ejecutable y salta lo que no cambió.
"""
import os
import re
import unicodedata
from collections import Counter
from typing import Dict, List, Optional

import numpy as np
from bson import Binary
from openai import AsyncOpenAI

EMBED_MODEL = "text-embedding-3-small"
COLECCION = "food_embeddings"


# ---------------------------------------------------------------- erratas
def clave_fonetica(s: str) -> str:
    """Cómo suena, para casar lo escrito deprisa con el catálogo: "wevos" == "huevos",
    "poyo" == "pollo", "keso" == "queso". Son reglas de fonética española (seseo, yeísmo,
    b/v, h muda, k/qu/w), un algoritmo: aquí no hay ninguna palabra escrita a mano.

    Es la misma idea que `_clave_fonetica` del chatbot (que solo se usaba para buscar
    dentro de la comida, nunca contra el catálogo), más el pliegue w->(g)u que faltaba.
    """
    t = (s or "").lower()
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    t = t.replace("qu", "k").replace("gue", "ge").replace("gui", "gi")
    t = re.sub(r"c(?=[ei])", "s", t)              # seseo: cocido == cosido
    t = t.replace("z", "s").replace("ll", "y").replace("v", "b").replace("h", "")
    t = t.replace("w", "u")                       # "wevos" == "(h)uevos"
    t = t.replace("y", "i").replace("c", "k")
    return re.sub(r"(.)\1+", r"\1", t)


class CorrectorErratas:
    """Corrige contra el VOCABULARIO real del catálogo (datos, no una lista de pares).

    Orden por palabra: si existe en el catálogo, no se toca; si suena igual que una
    palabra del catálogo (clave fonética), se cambia por la más frecuente de ese sonido;
    y como red, el parecido ortográfico (difflib >= 0.8: "arrox" -> "arroz").
    """

    def __init__(self, vocabulario: Counter):
        self.vocab = set(vocabulario)
        self.fonetico: Dict[str, str] = {}
        # Por sonido, gana la palabra más frecuente en el catálogo ("poio" -> pollo, no polio)
        for w, _ in sorted(vocabulario.items(), key=lambda x: x[1]):
            self.fonetico[clave_fonetica(w)] = w

    @classmethod
    async def cargar(cls, db) -> "CorrectorErratas":
        vocab = Counter()
        async for f in db.foods.find({}, {"_id": 0, "nombre": 1}):
            limpio = _norm(f.get("nombre", ""))
            limpio = re.sub(r"[(),/%.\-]", " ", limpio)
            for w in limpio.split():
                if len(w) >= 4 and w.isalpha():
                    vocab[w] += 1
        return cls(vocab)

    def corregir(self, texto: str) -> str:
        """El texto con las palabras mal escritas cambiadas; igual si no hay nada que tocar."""
        import difflib
        salida = []
        for w in _norm(texto).split():
            if len(w) < 4 or not w.isalpha() or w in self.vocab:
                salida.append(w)
                continue
            son = self.fonetico.get(clave_fonetica(w))
            if son:
                salida.append(son)
                continue
            cerca = difflib.get_close_matches(w, self.vocab, n=1, cutoff=0.8)
            salida.append(cerca[0] if cerca else w)
        return " ".join(salida)


def _norm(s: str) -> str:
    t = (s or "").lower()
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def texto_de_alimento(food: dict, nombres_cat: Dict[str, str]) -> str:
    """El texto que representa al alimento: nombre + nombres de sus categorías + etiquetas.

    Se incluyen los NOMBRES de las categorías (no los códigos): "2.2.1" no significa nada
    para el modelo de embeddings, "Aves frescas" sí. Las etiquetas transversales (YA, POL,
    SNA...) también van con su nombre ("Listo para comer", "En Polvo"), que es justo el
    vocabulario con el que la gente pide ("algo en polvo", "listo para llevar").
    """
    partes = [str(food.get("nombre") or "").strip()]
    rutas = []
    for tok in str(food.get("categorias") or "").split("|"):
        tok = tok.strip()
        if not tok:
            continue
        if tok[0].isdigit():
            # Ruta completa de nombres: "2.2.1" -> Carnes > Aves > Aves frescas
            trozos = tok.split(".")
            ruta = [nombres_cat.get(".".join(trozos[:i + 1])) for i in range(len(trozos))]
            ruta = [r for r in ruta if r]
            if ruta:
                rutas.append(" > ".join(ruta))
        else:
            nombre = nombres_cat.get(tok)
            if nombre:
                rutas.append(nombre)
    if rutas:
        partes.append("; ".join(rutas))
    if not food.get("url"):
        partes.append("genérico, sin marca")
    return ". ".join(p for p in partes if p)


async def cargar_nombres_categorias(db) -> Dict[str, str]:
    return {c["id"]: c["nombre"] async for c in db.food_categories.find({}, {"_id": 0})}


class BusquedaSemantica:
    """Matriz de vectores del catálogo en memoria + búsqueda por coseno.

    Uso:
        bs = await BusquedaSemantica.cargar(db)
        hits = await bs.buscar("comida liquida con proteina", limite=8)
        # -> [{"id": 123, "score": 0.51}, ...]
    """

    def __init__(self, ids: List[int], matriz: np.ndarray):
        self.ids = ids
        # Normalizada por filas: el coseno queda en un producto escalar.
        normas = np.linalg.norm(matriz, axis=1, keepdims=True)
        normas[normas == 0] = 1.0
        self.matriz = matriz / normas
        self._client: Optional[AsyncOpenAI] = None
        self._cache_consultas: Dict[str, np.ndarray] = {}

    @classmethod
    async def cargar(cls, db) -> "BusquedaSemantica":
        ids, filas = [], []
        async for doc in db[COLECCION].find({}, {"_id": 0, "id": 1, "vector": 1, "dim": 1}):
            v = np.frombuffer(doc["vector"], dtype=np.float32)
            if doc.get("dim") and len(v) != doc["dim"]:
                continue  # doc corrupto: mejor fuera que reventar la matriz
            ids.append(int(doc["id"]))
            filas.append(v)
        if not filas:
            raise RuntimeError(
                "db.food_embeddings está vacío: ejecuta _generar_embeddings.py primero.")
        return cls(ids, np.vstack(filas))

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        return self._client

    async def _vector_consulta(self, texto: str) -> np.ndarray:
        clave = texto.strip().lower()
        if clave in self._cache_consultas:
            return self._cache_consultas[clave]
        resp = await self._get_client().embeddings.create(model=EMBED_MODEL, input=[texto])
        v = np.array(resp.data[0].embedding, dtype=np.float32)
        n = np.linalg.norm(v)
        if n:
            v = v / n
        # Caché simple con tope: las consultas de un chat se repiten mucho ("otras", el
        # mismo término dos veces); sin tope, una sesión eterna crecería sin freno.
        if len(self._cache_consultas) > 500:
            self._cache_consultas.clear()
        self._cache_consultas[clave] = v
        return v

    async def buscar(self, texto: str, limite: int = 8,
                     solo_ids: Optional[set] = None) -> List[dict]:
        """Los `limite` alimentos más cercanos al texto. `solo_ids` restringe el universo
        (p.ej. a las categorías permitidas del peri, o a un rol del menú)."""
        q = await self._vector_consulta(texto)
        scores = self.matriz @ q
        orden = np.argsort(-scores)
        out = []
        for i in orden:
            aid = self.ids[i]
            if solo_ids is not None and aid not in solo_ids:
                continue
            out.append({"id": aid, "score": float(scores[i])})
            if len(out) >= limite:
                break
        return out


async def indexar_alimento(db, food: dict, nombres_cat: Optional[Dict[str, str]] = None):
    """(Re)calcula el vector de UN alimento. Llamar desde el alta/edición del catálogo:
    sin esto, los alimentos nuevos no existen para la búsqueda semántica."""
    if nombres_cat is None:
        nombres_cat = await cargar_nombres_categorias(db)
    texto = texto_de_alimento(food, nombres_cat)
    client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    resp = await client.embeddings.create(model=EMBED_MODEL, input=[texto])
    v = np.array(resp.data[0].embedding, dtype=np.float32)
    await db[COLECCION].update_one(
        {"id": int(food["id"])},
        {"$set": {"id": int(food["id"]), "texto": texto, "model": EMBED_MODEL,
                  "dim": len(v), "vector": Binary(v.tobytes())}},
        upsert=True,
    )
