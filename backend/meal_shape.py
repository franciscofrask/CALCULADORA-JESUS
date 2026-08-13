"""Perfil de FORMA de comida: de cuántas piezas se compone una comida de verdad y qué
combinaciones de familias usa Jesús en cada momento del día. APRENDIDO de db.diets.

Es la tercera pata de lo aprendido de las dietas, y la que faltaba:

    moment_profiles    CUÁNDO se come cada alimento (no propongas callos a las 8:00)
    company_profiles   QUÉ VA CON QUÉ, por parejas (ni yogur con atún)
    meal_shapes        DE QUÉ SE COMPONE una comida entera            <-- este

Las dos primeras juzgan alimentos y parejas; ninguna sabe decir que una comida ES un
conjunto de piezas. Por eso el asistente podía ofrecer doce batidos seguidos y montar un
desayuno de «copos de avena + 218 g de fiambre de jamón»: cada pieza pasaba los filtros
por separado y los macros cuadraban, que era lo único que se miraba.

Francisco, 12-08-2026, sobre las sugerencias: *«me ofreció todo yogur o batidos pero nada
de proteína real como huevos por ejemplo, u otros acompañamientos, tostadas, palta,
frutas»*. Y sobre los menús: *«no tiene sentido que solo tenga esas dos cosas, los menús
deben de tener sentido»*.

MEDIDO sobre los desayunos reales de la base (`_perfil_forma.py`), que es lo que le da la
razón y de paso da los números para arreglarlo:

    un desayuno de 3 a 6 alimentos          87,6 %
    un desayuno de 1 o 2 alimentos           7,5 %
    un desayuno de solo batidos y polvos     0,3 %   (5 de 1.441)

Y sus esqueletos, o sea de qué se componen de verdad:

    claras + huevos + pan + fiambre de pavo + aceite (+ miel)   7,6 %
    copos de avena + proteína en polvo + frutos secos           6,0 %
    yogur/lácteo + proteína en polvo + fruta                    2,9 %

Colección: db.meal_shapes
  {tipo: "_momento",  clave: "desayuno", comidas: 1441, tam: {"3": 310, ...},
   familias: {"1.1": 745, ...}, por_kcal: {"400": {"3": 40, ...}, ...}}
  {tipo: "esqueleto", clave: "desayuno", familias: ["1.1","1.2","2.1","8.1"], n: 94}

Se reconstruye con `_perfil_forma.py` (re-ejecutable); nada se escribe a mano.
"""
from typing import Dict, List, Optional, Tuple

COLECCION = "meal_shapes"

# Un esqueleto que solo ha pasado dos veces no es una forma de comer, es una casualidad.
# El corte está en apariciones absolutas y no en porcentaje a propósito: lo que interesa
# es que haya pasado de verdad unas cuantas veces, y en los momentos con menos datos un
# porcentaje dejaría entrar cualquier cosa.
MIN_APARICIONES = 5

# Comidas de un momento por debajo de las cuales no se juzga su forma: se cae al reparto
# general. Mismo criterio que el resto de perfiles (lo que no se sabe, no se inventa).
MIN_COMIDAS_MOMENTO = 100

# A cuánto se redondea el tramo de kcal al agrupar. Una comida de 250 kcal y otra de 320
# se parecen en cuántas piezas admiten; una de 250 y otra de 900, no.
TRAMO_KCAL = 100

# De cuántas piezas se compone una comida cuando no hay datos de ese momento. Es la
# mediana global de las comidas reales, no un número elegido.
PIEZAS_POR_DEFECTO = 4

# Los papeles que se cuentan por comida. Son los de `classify_food_role` (el mismo con el
# que el asistente monta), con los mixtos ya llevados a su macro dominante: un lácteo
# proteico y unos huevos son la proteína del desayuno.
ROLES = ("P", "H", "G", "V")

# El macro del que tira cada papel.
MACRO_DE_ROL = {"P": "P", "H": "H", "G": "G"}


def _mediana_de_conteo(conteo: Dict[str, int]) -> Optional[int]:
    """Mediana de una distribución guardada como {valor: veces}."""
    if not conteo:
        return None
    total = sum(conteo.values())
    if not total:
        return None
    acumulado = 0
    for k in sorted(conteo, key=lambda x: int(x)):
        acumulado += conteo[k]
        if acumulado >= total / 2:
            return int(k)
    return None


class PerfilForma:
    def __init__(self, momentos: Dict[str, dict], esqueletos: Dict[str, List[dict]]):
        self.momentos = momentos        # momento -> {comidas, tam, familias, por_kcal}
        self.esqueletos = esqueletos    # momento -> [{familias, n}, ...] de más a menos

    @classmethod
    async def cargar(cls, db) -> "PerfilForma":
        momentos, esqueletos = {}, {}
        async for d in db[COLECCION].find({}, {"_id": 0}):
            if d["tipo"] == "_momento":
                momentos[d["clave"]] = d
            elif d["tipo"] == "esqueleto":
                esqueletos.setdefault(d["clave"], []).append(d)
        for lista in esqueletos.values():
            lista.sort(key=lambda x: -int(x.get("n") or 0))
        return cls(momentos, esqueletos)

    @property
    def hay_datos(self) -> bool:
        return bool(self.momentos)

    def comidas(self, momento: str) -> int:
        return int((self.momentos.get(momento) or {}).get("comidas") or 0)

    def piezas_tipicas(self, momento: str, kcal: float = None) -> int:
        """De cuántos alimentos se compone una comida así.

        Con `kcal` se responde con las comidas reales de ESE tamaño: un desayuno de 250
        kcal y uno de 700 no llevan las mismas piezas, y repartir un hueco pequeño entre
        cinco alimentos daría raciones que nadie se pone. Sin datos del tramo se cae a la
        mediana del momento, y sin datos del momento, a la global.
        """
        perfil = self.momentos.get(momento)
        if not perfil or perfil.get("comidas", 0) < MIN_COMIDAS_MOMENTO:
            return PIEZAS_POR_DEFECTO
        piezas = None
        if kcal and kcal > 0:
            por_kcal = perfil.get("por_kcal") or {}
            tramo = int(float(kcal) // TRAMO_KCAL) * TRAMO_KCAL
            # El tramo exacto, y si tiene pocos casos, sus vecinos: así un hueco de 380
            # kcal no depende de que existan justo comidas de 300 a 399.
            for salto in (0, TRAMO_KCAL, -TRAMO_KCAL, 2 * TRAMO_KCAL, -2 * TRAMO_KCAL):
                conteo = por_kcal.get(str(tramo + salto)) or {}
                if sum(conteo.values()) >= 20:
                    piezas = _mediana_de_conteo(conteo)
                    if piezas:
                        break
        if not piezas:
            piezas = _mediana_de_conteo(perfil.get("tam") or {}) or PIEZAS_POR_DEFECTO
        # NI UNA PIEZA MÁS DE LAS QUE DA EL HUECO. Lo que queda por cubrir tiene que dar
        # para lo que pone una pieza de verdad (la mediana de las comidas reales, unas 70
        # kcal). Sin este tope, el hueco de 9,3 g de proteína y 6,2 de grasa con el que
        # Jesús ejemplificó el punto 76 -- 93 kcal, o sea un remate -- se repartía entre
        # tres piezas y les pedía 3 g de proteína a cada una: justo lo que ese punto
        # prohíbe. Un hueco pequeño se cierra con una cosa, no con media comida.
        if kcal and kcal > 0:
            por_pieza = self.kcal_por_pieza(momento)
            if por_pieza > 0:
                piezas = min(piezas, max(1, int(float(kcal) // por_pieza)))
        return max(1, piezas)

    def kcal_por_pieza(self, momento: str) -> float:
        """Cuántas kcal pone un alimento de una comida de ese momento (mediana real)."""
        perfil = self.momentos.get(momento) or {}
        return float(_mediana_de_conteo(perfil.get("kcal_pieza") or {}) or 0)

    def piezas_de_rol(self, momento: str, rol: str) -> int:
        """Cuántos alimentos hacen ESE papel en una comida real de ese momento.

        Es la pieza que faltaba para ordenar bien las sugerencias. El hueco de una comida
        no lo cubre una sola cosa ni se reparte a partes iguales: en un desayuno de Jesús
        la proteína la ponen dos piezas (claras y huevos, o proteína en polvo y lácteo),
        los hidratos una (el pan o los copos) y la grasa una (el aceite o los frutos
        secos). Sin esto, juzgar cada alimento contra el hueco ENTERO premia siempre al
        que lo cubre todo él solo, que es como salían doce batidos seguidos.

        Nunca menos de 1: un papel que se necesita lo hace por lo menos un alimento.
        """
        perfil = self.momentos.get(momento)
        if not perfil or perfil.get("comidas", 0) < MIN_COMIDAS_MOMENTO:
            return 1
        conteo = (perfil.get("roles") or {}).get(rol) or {}
        # Solo cuentan las comidas que SÍ llevan ese papel: la pregunta es «cuando hay
        # grasa aparte, cuántas piezas la ponen», no «cuántas cenas llevan grasa».
        con_el_rol = {k: v for k, v in conteo.items() if int(k) > 0}
        return max(1, _mediana_de_conteo(con_el_rol) or 1)

    def cuota(self, momento: str, rol: str, falta: float) -> float:
        """Cuánto de ese macro le toca poner a UNA pieza de ese papel."""
        return float(falta) / max(1, self.piezas_de_rol(momento, rol))

    def familias(self, momento: str) -> Dict[str, float]:
        """Familia (cat2) -> en qué proporción de las comidas de ese momento aparece."""
        perfil = self.momentos.get(momento)
        if not perfil or not perfil.get("comidas"):
            return {}
        total = float(perfil["comidas"])
        return {k: v / total for k, v in (perfil.get("familias") or {}).items()}

    def formas(self, momento: str, minimo: int = MIN_APARICIONES) -> List[Tuple[List[str], int]]:
        """Los esqueletos reales de ese momento, de más a menos usado.

        Cada uno es la lista de familias (cat2) que componían la comida: ['1.1', '1.2',
        '2.1', '8.1'] son claras, huevos, fiambre de pavo y pan. Lo que se come de verdad
        a esa hora, sin que nadie haya escrito la lista.
        """
        return [(list(d.get("familias") or []), int(d.get("n") or 0))
                for d in self.esqueletos.get(momento, [])
                if int(d.get("n") or 0) >= minimo and d.get("familias")]
