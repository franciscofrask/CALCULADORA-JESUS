"""Perfil de momento por alimento: en qué momento del día (desayuno, almuerzo, merienda,
cena) se come de verdad cada alimento, APRENDIDO de las dietas guardadas (db.diets).

Es la pieza que faltaba para que el asistente no proponga callos a la madrileña para
desayunar: el catálogo dice qué ES cada alimento, pero no CUÁNDO se come. Eso no lo decide
nadie a mano: lo dicen las ~30.000 dietas reales de la base.

Por qué se construye desde db.diets y no desde db.meal_library (verificado el 06-08):
la biblioteca guarda solo la POSICIÓN ("Comida 3") sin el tamaño del día, y la posición
engaña: la C3 de un día de 3 comidas es la cena, la de uno de 4 es la merienda, y el 22%
de los días son de bloque único (su C1 es el día entero, no un desayuno). db.diets guarda
`num_comidas` y `single_meal`, así que cada comida se mapea a su MOMENTO con la misma
regla (`meal_moment.momento_de_comida`) con la que luego se consulta, y los bloques únicos
se excluyen porque no llevan señal de momento.

Colección: db.moment_profiles
  {tipo: "alimento", clave: "498",  conteos: {desayuno: 812, comida: 120, ...}, total: N}
  {tipo: "categoria", clave: "2.2", conteos: {...}, total: N}    # respaldo por herencia
  {tipo: "_base", clave: "_base",   conteos: {...}, total: N}    # reparto general

Uso desde las herramientas:
  perfil = await PerfilMomento.cargar(db)
  perfil.coherencia(alimento, "desayuno")   # >1 típico del momento, <1 atípico, 1.0 sin datos

Se reconstruye con `_perfil_momento.py` (re-ejecutable); nada se escribe a mano.
"""
from typing import Dict, Optional

from meal_moment import DESAYUNO, COMIDA, MERIENDA, CENA

COLECCION = "moment_profiles"
MOMENTOS_PERFIL = (DESAYUNO, COMIDA, MERIENDA, CENA)

# Con menos usos que esto no hay señal: se pasa a la categoría, y si tampoco, neutro.
MIN_EVIDENCIA_ALIMENTO = 20
MIN_EVIDENCIA_CATEGORIA = 60


def cat2_de(food: dict) -> str:
    """Categoría fina (2 niveles) del alimento: '2.2.1 | YA' -> '2.2'."""
    for tok in str(food.get("categorias") or "").split("|"):
        tok = tok.strip()
        if tok and tok[0].isdigit():
            return ".".join(tok.split(".")[:2])
    return "?"


class PerfilMomento:
    def __init__(self, alimentos: Dict[str, dict], categorias: Dict[str, dict], base: Optional[dict]):
        self.alimentos = alimentos      # clave: str(alimento_id) -> {conteos, total}
        self.categorias = categorias    # clave: cat2 -> {conteos, total}
        self.base = base                # reparto general de todos los usos

    @classmethod
    async def cargar(cls, db) -> "PerfilMomento":
        alimentos, categorias, base = {}, {}, None
        async for d in db[COLECCION].find({}, {"_id": 0}):
            if d["tipo"] == "alimento":
                alimentos[d["clave"]] = d
            elif d["tipo"] == "categoria":
                categorias[d["clave"]] = d
            elif d["tipo"] == "_base":
                base = d
        return cls(alimentos, categorias, base)

    def _ratio(self, perfil: dict, momento: str) -> float:
        """Frecuencia del alimento en ese momento, relativa al reparto general.
        1.0 = ni fu ni fa; 2.0 = el doble de típico; 0.1 = casi nunca se come ahí."""
        if not self.base or not self.base.get("total"):
            return 1.0
        p = perfil["conteos"].get(momento, 0) / max(perfil["total"], 1)
        b = self.base["conteos"].get(momento, 0) / self.base["total"]
        if b <= 0:
            return 1.0
        return p / b

    def coherencia(self, food: dict, momento: str) -> float:
        """Cuánto pega este alimento en este momento. El peri no tiene perfil (sus
        categorías permitidas ya lo acotan): devuelve neutro."""
        if momento not in MOMENTOS_PERFIL:
            return 1.0
        p = self.alimentos.get(str(int(food.get("id", 0) or 0)))
        if p and p["total"] >= MIN_EVIDENCIA_ALIMENTO:
            return self._ratio(p, momento)
        c = self.categorias.get(cat2_de(food))
        if c and c["total"] >= MIN_EVIDENCIA_CATEGORIA:
            return self._ratio(c, momento)
        return 1.0   # lo que no se sabe no se penaliza

    def usos(self, food: dict, momento: str) -> int:
        """Cuántas VECES se ha puesto este alimento en ese momento, en bruto.

        `coherencia` responde a «¿pega esto a esta hora?» y lo hace en relativo, que es lo
        que hace falta para no proponer callos a las 8:00. Pero en relativo un yogur de
        marca rara que se usó tres veces empata con las claras pasteurizadas, que están en
        media base: los dos son «cosa de desayuno». Para ELEGIR entre ellos hace falta el
        número absoluto, que es el que dice cuál usa Jesús de verdad.

        Sin datos propios devuelve 0 a propósito: aquí no se hereda de la categoría. La
        pregunta es por ESTE alimento, y heredar volvería a empatar a todo el mundo.
        """
        if momento not in MOMENTOS_PERFIL:
            return 0
        p = self.alimentos.get(str(int(food.get("id", 0) or 0)))
        if not p:
            return 0
        return int(p["conteos"].get(momento, 0))

    def tiene_datos(self, food: dict) -> bool:
        p = self.alimentos.get(str(int(food.get("id", 0) or 0)))
        if p and p["total"] >= MIN_EVIDENCIA_ALIMENTO:
            return True
        c = self.categorias.get(cat2_de(food))
        return bool(c and c["total"] >= MIN_EVIDENCIA_CATEGORIA)
