"""
Quien puede escribir los macros de un cliente. Punto 4.10 de la revision del 09-08.

El catalogo de planes lleva desde hace tiempo el campo `habilitaciones.calculadora` con tres
valores:

    autogestion     el cliente se los calcula y se los ajusta el
    personalizado   hay un entrenador detras que se los pone y se los revisa
    sin_ajuste      no se tocan (la membresia de salida)

Y nadie lo miraba al guardar. Un cliente Silver -- `personalizado`, o sea de los que pagan
porque se los lleva Jesus -- tenia la pantalla «Ajustar macros» entera, con su cuestionario y
su boton de Guardar, y podia machacar lo que le hubiera puesto su entrenador sin que este se
enterase. Es justo lo contrario de lo que vende ese plan.

LA REGLA, Y POR QUE NO ES «EL PERSONALIZADO NO TOCA NADA»

Al darse de alta, un cliente de plan personalizado TIENE que poder calcular: son sus macros de
arranque, los que usa hasta que su entrenador se los revisa (y la pantalla se lo dice con esas
palabras). Cerrarle la calculadora desde el minuto uno lo dejaria sin numeros.

Lo que no puede es machacar los que ya le ha puesto una persona. Asi que la puerta se cierra
cuando se cumplen las dos cosas:

    su plan es `personalizado`   Y   sus macros ya los escribio alguien

Lo segundo se responde igual que en el punto 4.1, con `core/macros_de_quien`: mirando de donde
salio su ultimo apunte del historial. Un `quiz_alta` no cuenta como que se los puso alguien.

Los de `sin_ajuste` no ajustan nunca: ese plan no incluye ajustes, y ahi no hay matiz.
"""
from typing import Any, Dict, Optional, Tuple

from core.macros_de_quien import de_una_persona
from core.plan_access import modo_calculadora


async def puede_ajustarlos(db, perfil: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """(puede, por que no). El `por que no` esta escrito para leerselo al cliente."""
    modo = modo_calculadora(perfil.get("plan"))

    if modo == "sin_ajuste":
        return False, ("Tu plan no incluye ajustes de macros. Si quieres que te los revisemos, "
                       "escríbenos y lo vemos.")

    if modo != "personalizado":
        return True, None

    ultimo = await db.macro_history.find_one(
        {"client_id": perfil.get("id")}, {"_id": 0, "origen": 1, "changed_by": 1},
        sort=[("created_at", -1)])
    if de_una_persona(ultimo):
        return False, ("Tus macros los lleva tu entrenador: en tu plan se los ajusta él a "
                       "partir de tus reportes. Si crees que hay que moverlos, cuéntaselo por "
                       "el chat y lo revisa.")

    # Todavia nadie se los ha puesto: son los de su alta y puede recalcularlos.
    return True, None
