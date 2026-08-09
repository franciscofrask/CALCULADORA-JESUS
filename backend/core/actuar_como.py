"""
Que el entrenador entre en las pantallas de un cliente. Punto 4.11 de la revision del 09-08.

Lo que pedia Jesus: poder abrir la calculadora de un cliente EN MODO EDICION desde su ficha
-- el mismo editor que ve el --, para revisarle el dia y dejarle algo montado. Hasta ahora la
pestaña Nutricion de la ficha era de solo lectura: se veian sus dietas, sus alimentos y sus
gramos, y no habia forma de tocar nada.

POR QUE UNA CABECERA Y NO TREINTA ENDPOINTS NUEVOS

La calculadora del cliente no es una pantalla: son las dietas, el reparto del dia, el buscador
de alimentos, el sugeridor, el recetario, la biblioteca, copiar de otro dia, el PDF... y todos
esos endpoints resuelven el cliente igual, por el token. Duplicarlos en version `/admin/...`
seria duplicar la mitad de la API, y cada arreglo futuro habria que hacerlo dos veces (que es
justo la enfermedad que este documento lleva señalando desde el punto 17: dos puertas a lo
mismo y una peor).

Asi que se resuelve donde ya se resuelve el usuario: `get_current_user`. Si la peticion trae
`X-Actuar-Como: <user_id>` y quien la manda es del equipo, se trabaja como ese cliente. Una
linea, y funciona toda la pantalla.

LOS CUATRO CERROJOS

Esto es suplantacion, asi que va con llave:

  1. Solo el equipo. Un cliente que se invente la cabecera recibe un 403.
  2. Solo hacia CLIENTES. No se puede actuar como un admin ni como otro entrenador: eso
     seria una escalada de privilegios con nombre bonito.
  3. Solo sobre los suyos. Pasa por `assert_client_access`, la misma regla que la ficha: un
     entrenador no entra en el cliente de otro.
  4. Queda anotado. Cada peticion suplantada deja rastro en `audit_log`, y lo que se guarda
     lleva quien lo guardo. Es la segunda cosa que pedia Jesus: «si el entrenador le monta una
     dieta el martes y el cliente la cambia el miercoles, los dos tienen que poder verlo».

El usuario devuelto es el del CLIENTE, para que todo lo de abajo funcione sin enterarse, pero
con `_actuando_como` dentro: quien quiera dejar rastro mira ahi.
"""
from typing import Any, Dict, Optional

CABECERA = "X-Actuar-Como"

# La marca que se le cuelga al usuario devuelto: {por_id, por_nombre}. Empieza por guion bajo
# porque no es un campo suyo, es como se pidio esta peticion.
CLAVE = "_actuando_como"


def quien_actua(user: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Si esta peticion la hace alguien del equipo por un cliente, quien. Si no, None."""
    return (user or {}).get(CLAVE)


def marca_de_quien_lo_hizo(user: Dict[str, Any]) -> Dict[str, Any]:
    """Lo que se guarda junto al dato para saber quien lo toco.

    Se guarda SIEMPRE, tanto si lo hizo el cliente como si lo hizo su entrenador: la pregunta
    de Jesus no es «¿lo toco el coach?» sino «¿quien toco esto?», y solo se puede responder si
    los dos casos dejan rastro. Si solo se marcara la intervencion del entrenador, un dia sin
    marca podria significar dos cosas -- lo hizo el cliente, o se guardo antes de existir esto
    -- y no habria forma de distinguirlas.
    """
    actor = quien_actua(user)
    if actor:
        return {"editado_por": actor.get("por_nombre") or "el equipo",
                "editado_por_id": actor.get("por_id"),
                "editado_como": "entrenador"}
    return {"editado_por": user.get("name") or user.get("email") or "el cliente",
            "editado_por_id": user.get("id"),
            "editado_como": "cliente"}
