"""Perfil de compañía: qué alimentos van juntos en la misma comida, APRENDIDO de las
dietas guardadas (db.diets).

Francisco, 08-08-2026, sobre las sugerencias del asistente: *«esas sugerencias no tienen
sentido alguno, comer harina con avena? esa combinación de alimentos no tiene sentido»*.
Tenía razón, y no era un caso suelto: el sugeridor ofrecía yogur con atún, pollo con
fiambre de pavo en el desayuno, o caseína con chocolate negro. Cuadraban los macros, que
es lo único que miraba.

Qué combina con qué no lo decide nadie a mano -- eso sería la lista de palabras que
Francisco prohibió expresamente -- : lo dicen las **147.820 comidas reales** de la base,
montadas por Jesús durante años.

La medida es la ELEVACIÓN: cuántas veces coinciden dos alimentos frente a las que
coincidirían por azar, dado lo que se usa cada uno.

    1.0  ni se buscan ni se evitan
    >1   se ponen juntos más de lo esperable
    <1   se evitan

Medido sobre los menús que el asistente sacó y sobre comidas que sí tienen sentido, el
**peor par** de la comida separa unos de otros limpiamente:

    pollo + fiambre de pavo   0.14        arroz + aceite de oliva   2.59
    caseína + frutos rojos    0.25        whey + plátano            2.19
    harina de avena + copos   0.30        claras + pan de barra     1.63
    yogur + atún              0.37        copos de avena + nueces   0.65

Colección: db.company_profiles
  {tipo: "alimento",  clave: "498",  n: 24045, con: {"321": 2326, ...}}
  {tipo: "categoria", clave: "2.2",  n: 30112, con: {"5.1": 812, ...}}   # herencia
  {tipo: "_base",     clave: "_base", comidas: 147820, tam: {"1": 2662, "2": 29965, ...}}

El respaldo por categoría no es un adorno: 2.050 de los 3.211 alimentos del catálogo no
tienen usos propios suficientes, y el 95 % de ellos sí tienen categoría con datos.

Se reconstruye con `_perfil_companyia.py` (re-ejecutable); nada se escribe a mano.
"""
from typing import Dict, List, Optional, Tuple

from moment_profile import cat2_de

COLECCION = "company_profiles"

# Con menos usos que esto no hay señal: se pasa a la categoría, y si tampoco, se calla.
MIN_USOS_ALIMENTO = 30
MIN_USOS_CATEGORIA = 60

# Por debajo de esta elevación, dos alimentos no se ponen juntos en las dietas reales.
#
# El corte sale de medir (`_perfil_companyia.py --calibrar`), no de elegirlo a ojo: se
# compara el peor par de 4.000 comidas REALES con el de 4.000 comidas inventadas al azar
# con los mismos alimentos.
#
#   corte   deja fuera de las reales   deja fuera de las inventadas
#   0.20           5.2 %                        95.5 %
#   0.30           9.2 %                        95.7 %
#   0.40          14.1 %                        95.8 %
#   0.50          18.6 %                        95.9 %
#
# Se elige 0.40 porque es donde entran los cuatro casos que se veían mal de verdad -- yogur
# + atún (0.37), harina de avena + copos (0.30), caseína + frutos rojos (0.25) y pollo +
# fiambre de pavo (0.14) -- sin pagar mucho más: de 0.40 en adelante la detección ya no
# sube (95,8 -> 95,9) y los descartes de comidas legítimas casi se duplican.
#
# Ese 14 % de comidas reales que quedan por debajo no son malas: son comidas con algún par
# poco habitual. Aquí no es un veto, es una preferencia entre varias opciones, así que
# perder una de cada siete no deja al cliente sin nada que elegir.
ELEVACION_MINIMA = 0.40


class PerfilCompanyia:
    def __init__(self, alimentos: Dict[str, dict], categorias: Dict[str, dict],
                 base: Optional[dict]):
        self.alimentos = alimentos
        self.categorias = categorias
        self.base = base or {}

    @classmethod
    async def cargar(cls, db) -> "PerfilCompanyia":
        alimentos, categorias, base = {}, {}, None
        async for d in db[COLECCION].find({}, {"_id": 0}):
            if d["tipo"] == "alimento":
                alimentos[d["clave"]] = d
            elif d["tipo"] == "categoria":
                categorias[d["clave"]] = d
            elif d["tipo"] == "_base":
                base = d
        return cls(alimentos, categorias, base)

    @property
    def comidas(self) -> int:
        return int(self.base.get("comidas") or 0)

    def _elevacion_en(self, tabla: Dict[str, dict], a: str, b: str, minimo: int) -> Optional[float]:
        pa, pb = tabla.get(a), tabla.get(b)
        if not pa or not pb or pa["n"] < minimo or pb["n"] < minimo or not self.comidas:
            return None
        esperado = pa["n"] * pb["n"] / self.comidas
        if esperado <= 0:
            return None
        return pa["con"].get(b, 0) / esperado

    def elevacion(self, food_a: dict, food_b: dict) -> Optional[float]:
        """Cuánto se buscan estos dos. None cuando no hay datos: lo que no se sabe no se
        juzga, igual que en el perfil de momento."""
        ia = str(int(food_a.get("id", 0) or 0))
        ib = str(int(food_b.get("id", 0) or 0))
        if ia == ib:
            return None
        directa = self._elevacion_en(self.alimentos, ia, ib, MIN_USOS_ALIMENTO)
        if directa is not None:
            return directa
        ca, cb = cat2_de(food_a), cat2_de(food_b)
        if ca == cb:
            # Dos alimentos de la misma categoría fina sin datos propios: sin la pareja de
            # categorías consigo misma no hay nada que decir, y adivinar aquí sería
            # penalizar "dos frutas" o "dos verduras", que es normal.
            return None
        return self._elevacion_en(self.categorias, ca, cb, MIN_USOS_CATEGORIA)

    def coincidencias(self, food_a: dict, food_b: dict) -> int:
        """Cuántas VECES han estado juntos de verdad. La elevación sola no basta para
        decidir si algo acompaña a algo: con pocos usos, una coincidencia suelta ya da una
        elevación alta, y así entraba el azúcar moreno en cualquier comida."""
        ia = str(int(food_a.get("id", 0) or 0))
        ib = str(int(food_b.get("id", 0) or 0))
        pa = self.alimentos.get(ia)
        return int((pa or {}).get("con", {}).get(ib, 0))

    def peor_pareja(self, foods: List[dict]) -> Optional[Tuple[float, dict, dict]]:
        """El par que peor casa de una comida, con su elevación. None si no hay datos de
        ninguna pareja."""
        peor = None
        for i, a in enumerate(foods):
            for b in foods[i + 1:]:
                e = self.elevacion(a, b)
                if e is None:
                    continue
                if peor is None or e < peor[0]:
                    peor = (e, a, b)
        return peor

    def discordante(self, foods: List[dict]) -> Optional[Tuple[float, dict, dict]]:
        """El par que NO se pone junto en las dietas reales, si lo hay."""
        peor = self.peor_pareja(foods)
        if peor and peor[0] < ELEVACION_MINIMA:
            return peor
        return None

    def tamano_habitual(self, cobertura: float = 0.85) -> int:
        """Cuántos alimentos tiene una comida de verdad. Devuelve el número por debajo del
        cual está `cobertura` de las comidas reales (por defecto el 85 %).

        Medido: el 84,5 % de las 147.820 comidas tienen 5 alimentos o menos, y el
        sugeridor ofrecía menús de 6 y de 7."""
        tam = self.base.get("tam") or {}
        if not tam:
            return 5
        total = sum(tam.values())
        acumulado = 0
        for n in sorted(tam, key=lambda k: int(k)):
            acumulado += tam[n]
            if acumulado / total >= cobertura:
                return int(n)
        return 5
