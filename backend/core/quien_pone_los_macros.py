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

LOS CAMINOS DE REBOTE (segunda vuelta, 09-08)

El cerrojo se puso primero en los dos sitios donde el cliente toca sus macros A PROPOSITO:
`PUT /macros` y `POST /clients/ajustar-macros`. Pero hay cuatro mas que los reescriben de
rebote, haciendo el cliente otra cosa:

    PUT  /clients/profile           cambia su peso, sexo, grasa u objetivo -> recalcula
    POST /clients/questionnaire     repite el cuestionario del alta        -> recalcula
    POST /clients/mi-cuerpo         vuelve a pasar por «Mi cuerpo»         -> recalcula
    POST /calculator/targets/apply  calcula y aplica, sin mirar nada

Los tres primeros se guardaban con `macros_source != "manual"`, y eso NO es el mismo cerrojo:
la calculadora del panel del coach (`POST /admin/clients/{id}/calculator/apply`) deja
`macros_source: "auto"`, asi que justo los clientes a los que el coach les puso los macros
desde su calculadora quedaban abiertos. El cuarto no miraba ni eso: con un peso y un objetivo
cualquier cliente autenticado se machacaba los macros de su entrenador.

Medido en produccion el 09-08 sobre 184 perfiles activos: 180 son de plan personalizado, 176
de ellos con `macros_source: "manual"` (a salvo de los tres primeros pero NO del cuarto) y 4
con "auto" (abiertos por todos). O sea: por el camino de la calculadora estaban expuestos los
180, y por los otros tres, 4 hoy y todos los que el coach ajustara desde su calculadora a
partir de manana.

La diferencia de trato entre unos y otros es a proposito:

  - En los caminos DE PROPOSITO se devuelve 403 con el motivo escrito para el cliente.
  - En los DE REBOTE no: el cliente esta haciendo algo legitimo (apuntar su peso nuevo). Se
    le guarda lo que venia a guardar y lo unico que no pasa es el recalculo. Un 403 ahi le
    impediria actualizar su propio peso, que no es lo que dice el punto.
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
        # En plural y sin «entrenador»: al cliente no se le nombra a quien esté detrás ese
        # mes, se le habla de nosotros (repaso de Jesús, 11-08).
        return False, ("Tus macros los llevamos nosotros: en tu plan te los ajustamos a partir "
                       "de tus reportes. Si crees que hay que moverlos, dínoslo por el chat y "
                       "lo revisamos.")

    # Todavia nadie se los ha puesto: son los de su alta y puede recalcularlos.
    return True, None


async def exigir_que_pueda(db, perfil: Dict[str, Any]) -> None:
    """Cierra la puerta con un 403 y el motivo escrito para el cliente.

    Para los caminos en los que el cliente viene expresamente a tocarse los macros. En los de
    rebote no se usa esto, sino `puede_ajustarlos` a secas para saltarse el recalculo.
    """
    from fastapi import HTTPException

    puede, por_que_no = await puede_ajustarlos(db, perfil)
    if not puede:
        raise HTTPException(status_code=403, detail=por_que_no)
