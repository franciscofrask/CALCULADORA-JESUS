"""Cuántos días a la semana entrena el cliente.

La pregunta se retira del alta el 18-08 (bloque 5 del documento del cuestionario inicial:
«¿Cuántos días a la semana puedes entrenar? · Son siempre cuatro. El campo se rellena solo
con 4»). Hasta ese día no la hacía ninguna pantalla y el campo nacía a None, así que el
dato no existía y nadie podía darlo: en el panel de Rutinas, 158 de los 164 clientes que
pagan rutina salían como «falta saber lo básico de su entrenamiento», y ninguno de los que
el panel daba por listos era un cliente real.

Aquí viven las dos lecturas, que no son la misma pregunta:

  - `dias_guardados` es lo que hay escrito en la ficha. Sirve para saber si el dato existe
    de verdad (por ejemplo, para contar cuántos hay que rellenar).
  - `dias_de_entreno` es con cuántos días se trabaja, y nunca contesta «no lo sé».

Se separa así a propósito para que rellenar no borre la diferencia: un 4 supuesto y un 4
que dijo el cliente valen lo mismo para montar la rutina, pero no para el recuento.
"""
from typing import Any, Dict, Optional

# Cuatro. No es un relleno de emergencia: es la pauta, la misma para todos, y por eso se
# deja de preguntar.
DIAS_DE_ENTRENO_POR_DEFECTO = 4


def dias_guardados(perfil: Dict[str, Any]) -> Optional[int]:
    """Los días que constan en la ficha, o None si no consta ninguno.

    Está guardado de dos formas: `training_days` (un número) y `training_weekdays` (la
    lista de días: lunes, miércoles...). Las dos contestan a lo mismo, así que vale
    cualquiera de ellas y se cuenta la lista si es lo único que hay.
    """
    for campo in ("training_days", "training_weekdays"):
        v = (perfil or {}).get(campo)
        if isinstance(v, (list, tuple, set)):
            n = len([d for d in v if str(d).strip()])
        else:
            try:
                n = int(v)
            except (TypeError, ValueError):
                continue
        # Un 0 o una lista vacía no son «entrena cero días»: son que ahí no hay respuesta,
        # y quien contesta eso no existe. Se tratan como si el campo no estuviera.
        if n >= 1:
            return min(7, n)
    return None


def dias_de_entreno(perfil: Dict[str, Any]) -> int:
    """Con cuántos días se trabaja: los suyos si los tiene y, si no, los cuatro de siempre."""
    return dias_guardados(perfil) or DIAS_DE_ENTRENO_POR_DEFECTO
