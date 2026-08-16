"""
El catálogo de planes y los ajustes de la app son SOLO de administradores.

Un entrenador no decide qué incluye un plan: de esas habilitaciones dependen el precio,
lo que ve el cliente y a qué endpoints llega. Quitarle "reportes" a un plan se lo quita a
todos sus clientes a la vez. Y en esa misma pantalla vive el interruptor que apaga una
pantalla para TODOS, más la frase del día que leen todos.

Se comprueba el cableado de verdad -- qué dependencia protege cada ruta -- y no que el
fichero contenga cierto texto: una dependencia se puede quitar dejando el import puesto.
Los dos espejos del front se comprueban aparte, porque el candado tiene que estar en las
dos puntas (el de arriba es comodidad; el que manda es este).
"""
import os

import pytest

from routes.plans import admin_router as plans_admin_router, router as plans_public_router
from routes.settings import admin_router as settings_admin_router, router as settings_router

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _guardianes(route) -> set:
    """Los nombres de todas las dependencias que protegen una ruta, a cualquier hondura."""
    nombres = set()

    def _hurgar(dependant):
        for sub in dependant.dependencies:
            if sub.call is not None:
                nombres.add(getattr(sub.call, "__name__", str(sub.call)))
            _hurgar(sub)

    _hurgar(route.dependant)
    return nombres


def _rutas(router):
    return [r for r in router.routes if hasattr(r, "dependant")]


@pytest.mark.parametrize("router,nombre", [
    (plans_admin_router, "/admin/plans"),
    (settings_admin_router, "/admin/settings"),
])
def test_todas_las_rutas_son_solo_de_admin(router, nombre):
    for route in _rutas(router):
        guardianes = _guardianes(route)
        assert "get_admin_only_user" in guardianes, (
            f"{nombre}{route.path} ({','.join(sorted(route.methods))}) no está cerrado a "
            f"los entrenadores: {sorted(guardianes) or 'sin ninguna dependencia'}")
        assert "get_admin_user" not in guardianes, (
            f"{nombre}{route.path} sigue abierto a entrenadores por get_admin_user")


def test_el_catalogo_publico_de_planes_sigue_abierto():
    """OJO: `GET /plans` NO se toca. Lo lee la app entera para saber qué incluye cada plan
    (y el propio cliente para elegir), así que cerrarlo dejaría la app sin catálogo."""
    for route in _rutas(plans_public_router):
        if route.path == "/plans":
            assert "get_admin_only_user" not in _guardianes(route)
            assert "get_current_user" not in _guardianes(route)
            return
    pytest.fail("no está la ruta pública /plans")


def test_los_ajustes_los_puede_LEER_cualquier_usuario():
    """El cliente necesita leerlos: de ahí salen la frase del día y qué pantallas están
    encendidas. Escribirlos es otra cosa, y eso ya lo cierra el test de arriba."""
    for route in _rutas(settings_router):
        if route.path.endswith("/settings/app"):
            guardianes = _guardianes(route)
            assert "get_current_user" in guardianes, "los ajustes se sirven sin sesión"
            assert "get_admin_only_user" not in guardianes, (
                "los ajustes se han cerrado al cliente: se queda sin frase del día y sin "
                "saber qué pantallas están encendidas")
            return
    pytest.fail("no está la ruta /settings/app")


# ── Los espejos del front ────────────────────────────────────────────────────

def _fuente(*partes) -> str:
    ruta = os.path.join(_RAIZ, "frontend", "src", *partes)
    with open(ruta, encoding="utf-8") as f:
        return f.read()


def test_la_ruta_de_planes_esta_cerrada_en_el_front():
    app = _fuente("App.js")
    trozo = app[app.index('path="planes"'):]
    trozo = trozo[:trozo.index("/>") if "/>" in trozo else 400]
    assert "allowedRoles={['admin']}" in trozo, (
        "un entrenador puede abrir /admin/planes escribiendo la dirección")


def test_planes_no_sale_en_el_menu_de_un_entrenador():
    nav = _fuente("pages", "AdminDashboard.jsx")
    linea = next(l for l in nav.splitlines() if "'/admin/planes'" in l)
    assert "adminOnly: true" in linea, "la entrada Planes sigue en el menú del entrenador"
