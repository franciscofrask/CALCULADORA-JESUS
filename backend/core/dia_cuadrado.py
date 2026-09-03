# -*- coding: utf-8 -*-
"""SI UN DÍA CUADRA O NO, EN UN SOLO SITIO.

El color de Mi semana y del calendario de Nutrición salía de `diets.is_cuadrado`, una
MARCA GUARDADA. Y una marca guardada no es un estado: es lo que alguien anotó una vez.

Lo que pasaba, medido el 3-09 en dev: **42.747 días de dieta y 3 en verde**. Uno de esos 3
se pasaba 71 g de hidratos. O sea que el color fallaba en las dos direcciones y el cliente
veía naranja en todo, que es literalmente lo que reportó Gonzalo: «no hay ninguna
diferencia cuando está cuadrado y cuando no».

El motivo es que la marca solo la escribe la pantalla de Nutrición al guardar, y todas las
demás puertas la apagan o la ignoran: el chat la pone en `False` fija, el montador
automático no la toca, copiar un día se lleva la del día de origen y los tres importadores
la dejan en `False`. Con eso, un día montado con Marco nacía naranja aunque cuadrara.

**Aquí no se guarda nada: se calcula.** Con los macros que estaban vigentes ESE DÍA, no con
los de hoy, que es la trampa que ya mordió una vez: recalcular con los de hoy hacía que un
día que se cuadró en su momento dejara de estar cuadrado por el simple hecho de mirarlo.

LA REGLA ES LA DEL INFORME DEL MES, palabra por palabra, porque tiene que dar el mismo
número: margen de ±4 g (decisión de Francisco, 16-08) y la proteína cuenta como hecha en
cuanto está CUBIERTA, que pasarse de proteína no es un fallo (Jesús, 13-08). Contándolo de
otra forma, el «cuadraste los macros N días» del reporte no coincidiría con los días verdes
del calendario sobre exactamente los mismos datos.
"""
from typing import Any, Dict, List, Optional

from calma_suggest import MARGEN_VALIDO
from macro_distribution import leer_macro

__all__ = ["MARGEN_VALIDO", "cuadra", "juez_de_dias"]


def cuadra(total: Dict[str, float], objetivo: Dict[str, float]) -> Optional[bool]:
    """¿Cuadra este día? `None` cuando no hay con qué juzgarlo.

    `total` es lo que se comió (o lo que hay montado) y `objetivo` lo que tocaba, los dos
    en {P, H, G}. Sin objetivo no se juzga: decir «no cuadra» de un día del que no sabemos
    qué se le pedía es acusarle de algo que no se ha medido.
    """
    if not objetivo or not any((objetivo.get(k) or 0) > 0 for k in ("P", "H", "G")):
        return None
    proteina_hecha = (total.get("P") or 0) - (objetivo.get("P") or 0) >= -MARGEN_VALIDO
    resto = all(abs((objetivo.get(k) or 0) - (total.get(k) or 0)) <= MARGEN_VALIDO
                for k in ("H", "G"))
    return bool(proteina_hecha and resto)


async def juez_de_dias(db, perfil: Dict[str, Any]):
    """Devuelve una función `(fecha, tipo_dia, total) -> bool|None`, ya con el historial leído.

    El historial se trae UNA VEZ. `macros_por_fecha.resolver` lo relee entero en cada
    llamada, y aquí se juzgan siete días de una semana o los treinta y uno de un mes: serían
    treinta y una lecturas de lo mismo para pintar un calendario.

    La resolución es la de `macros_por_fecha.elegir_entrada`, misma regla: la última entrada
    con `effective_date <= fecha` y, si la fecha es anterior a cualquier cambio, la más
    antigua, porque el cliente ya entrenaba con esos macros antes de que se registraran.
    """
    entradas: List[Dict[str, Any]] = await db.macro_history.find(
        {"client_id": perfil.get("id")}, {"_id": 0}).to_list(500)

    def eff(e):   # las entradas antiguas no tienen effective_date: vale la de creación
        return e.get("effective_date") or str(e.get("created_at", ""))[:10]

    del_perfil_entreno = perfil.get("macros_training") or {}
    del_perfil_descanso = perfil.get("macros_rest") or {}

    def objetivo_de(fecha: Optional[str], tipo_dia: Optional[str]) -> Dict[str, float]:
        entreno, descanso = del_perfil_entreno, del_perfil_descanso
        if fecha and entradas:
            aplicables = [e for e in entradas if eff(e) and eff(e) <= fecha]
            elegida = (max(aplicables, key=lambda e: (eff(e), e.get("created_at", "")))
                       if aplicables
                       else min(entradas, key=lambda e: (eff(e), e.get("created_at", ""))))
            entreno = elegida.get("new_training") or elegida.get("training") or entreno
            descanso = elegida.get("new_rest") or elegida.get("rest") or descanso
        doc = descanso if tipo_dia == "descanso" else entreno
        return {
            "P": leer_macro(doc, "protein", "proteinas"),
            "H": leer_macro(doc, "carbs", "hidratos"),
            "G": leer_macro(doc, "fat", "grasas"),
        }

    def juzgar(fecha: Optional[str], tipo_dia: Optional[str],
               total: Dict[str, float]) -> Optional[bool]:
        # UN DÍA VACÍO NO ESTÁ DESCUADRADO, ESTÁ SIN EMPEZAR. Sin esto, el calendario
        # pintaría de aviso los días que todavía no se han montado, y la regla de la casa
        # dice lo contrario: «ir corto no es un error, es que todavía no has terminado».
        if not any((total.get(k) or 0) > 0 for k in ("P", "H", "G")):
            return None
        return cuadra(total, objetivo_de(fecha, tipo_dia))

    return juzgar
