"""
El usuario de la petición en curso, guardado en un contextvar.

Sirve para el MODO PRUEBAS por cuenta: una cuenta marcada `es_pruebas` puede tener sus
propias anulaciones de los interruptores de pantalla (`overrides_pantallas`) que valen
SOLO para ella y no tocan lo que ven los demás. El problema es que los cerrojos de
pantalla del backend (`routes/settings.pantalla_activa`, que consultan checkins, diets,
diary, rutinas, avisos...) no reciben el usuario: son funciones sueltas.

En vez de hilar el usuario por sus once llamadas, `get_current_user` -por donde pasa toda
petición autenticada- lo deja aquí, y `ajustes_app` lo recoge para aplicar las anulaciones
de esa cuenta. Cada petición corre en su propio contexto asíncrono, así que no se pisan.

Fuera de una petición (scripts, cron, arranque) queda a None y NO se aplica ninguna
anulación: quien no es una petición de usuario ve siempre los ajustes globales.
"""
from contextvars import ContextVar
from typing import Any, Dict, Optional

_usuario_actual: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "usuario_actual", default=None
)


def fijar_usuario_actual(user: Optional[Dict[str, Any]]) -> None:
    """La deja puesta para el resto de esta petición. La llama `get_current_user`."""
    _usuario_actual.set(user)


def usuario_actual() -> Optional[Dict[str, Any]]:
    """El usuario de esta petición, o None si no venimos de una petición autenticada."""
    return _usuario_actual.get()
