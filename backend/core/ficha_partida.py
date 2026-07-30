"""
La ficha que se le entrega al cliente en el PUNTO DE PARTIDA (paso 3 del doc del 29-07).

Se le piden fotos y medidas justo despues de darle los macros, que es cuando mas motivado esta,
y a cambio se le da algo suyo: de que esta hecho hoy, cuanto musculo lleva encima para su altura,
y que le paso a la gente que empezo pareciendose a el.

Modulo puro salvo la consulta de casos parecidos; las rutas se encargan de guardar.
"""
from typing import Dict, List, Optional

import macro_casos
from target_calculator import calcular_masa_trabajo

# Referencias de indice de masa magra (FFMI normalizado a 1,80 m). Son las que se usan de forma
# estandar en composicion corporal: por debajo de 18 en hombres es poca masa para su altura; por
# encima de 22 es bastante; 25 es el techo de lo alcanzable sin ayuda para la mayoria.
TRAMOS_FFMI = {
    "hombre": [(18, "por debajo de la media"), (20, "en la media"), (22, "por encima de la media"),
               (25, "muy por encima de la media"), (99, "excepcional")],
    "mujer": [(14, "por debajo de la media"), (16, "en la media"), (18, "por encima de la media"),
              (21, "muy por encima de la media"), (99, "excepcional")],
}


def _lectura_ffmi(ffmi: Optional[float], sexo: str) -> Optional[str]:
    if ffmi is None:
        return None
    for limite, texto in TRAMOS_FFMI.get(sexo, TRAMOS_FFMI["hombre"]):
        if ffmi < limite:
            return texto
    return "excepcional"


def composicion_de(peso: float, porcentaje_graso: float, altura_cm: Optional[float],
                   sexo: str = "hombre") -> Dict:
    """
    De que esta hecho hoy: grasa, masa magra y cuanto musculo lleva para su altura.

    El indice se normaliza a 1,80 m porque en crudo penaliza a los altos y premia a los bajos:
    dos personas con la misma cantidad de musculo dan indices distintos solo por medir distinto.
    """
    comp = calcular_masa_trabajo(peso, porcentaje_graso)
    salida = {
        "peso": round(peso, 1),
        "porcentaje_graso": round(porcentaje_graso, 1),
        "masa_grasa": round(comp["masa_grasa"], 1),
        "masa_magra": round(comp["masa_magra"], 1),
        "indice_muscular": None,
        "indice_muscular_lectura": None,
        "falta_altura": altura_cm is None or altura_cm <= 0,
    }
    if altura_cm and altura_cm > 0:
        h = altura_cm / 100.0
        ffmi = comp["masa_magra"] / (h * h)
        ffmi_norm = ffmi + 6.1 * (1.8 - h)
        salida["indice_muscular"] = round(ffmi_norm, 1)
        salida["indice_muscular_lectura"] = _lectura_ffmi(ffmi_norm, sexo)
    return salida


async def referencia_de_parecidos(sexo: str, fase: str, peso: float, porcentaje_graso: float,
                                  hc_total: Optional[float] = None,
                                  excluir_client_id: Optional[str] = None) -> Optional[Dict]:
    """
    Que le paso a la gente que empezo como el: cuanto se movieron y en cuanto tiempo.

    No es una promesa ni un objetivo: es lo que de verdad les paso a clientes reales parecidos.
    Si no hay casos suficientes se devuelve None y no se enseña nada, antes que inventar una cifra.
    """
    ref = {"sexo": sexo, "fase": fase, "peso": peso, "graso": porcentaje_graso}
    if hc_total is not None:
        ref["hc_total"] = hc_total
    casos = await macro_casos.buscar_gemelos(ref, k=12, excluir_client_id=excluir_client_id)
    if len(casos) < 3:
        return None

    # Cada caso guarda cuanto se movio y en cuantos dias; el ritmo se pasa a "por mes" para que
    # los tramos de distinta duracion sean comparables entre si.
    ritmos: List[float] = []
    for c in casos:
        delta = c.get("delta_peso_pct")
        dias = c.get("dias_tramo")
        if isinstance(delta, (int, float)) and isinstance(dias, (int, float)) and dias >= 7:
            ritmos.append(float(delta) / float(dias) * 30.0)
    if len(ritmos) < 3:
        return None

    # La mediana de TODOS sale casi siempre en cero, porque mezcla a quien avanzo con quien se
    # quedo parado, y "lo normal fue moverse 0 kg al mes" no le dice nada a nadie. Se separan las
    # dos cosas: cuantos avanzaron en la direccion de su objetivo, y a que ritmo lo hicieron esos.
    # Asi el dato es util sin ser una promesa: se ve tambien cuantos no lo consiguieron.
    a_favor = [r for r in ritmos if (r < 0 if fase == "definicion" else r > 0)]
    if len(a_favor) < 3:
        return None
    a_favor.sort()
    mediana = a_favor[len(a_favor) // 2]

    return {
        "casos": len(ritmos),
        "avanzaron": len(a_favor),
        "ritmo_mediano_pct_mes": round(abs(mediana), 2),
        # En kilos sobre SU peso, que es como lo va a entender.
        "kg_mes": round(abs(peso * mediana / 100.0), 1),
        "rango_pct": [round(abs(a_favor[-1]), 2), round(abs(a_favor[0]), 2)],
    }
