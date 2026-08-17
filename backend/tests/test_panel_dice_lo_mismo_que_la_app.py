"""
El panel y la app tienen que decir lo mismo del mismo cliente.

17-08-2026, Francisco: un cliente de ELM salía «Activo» en el panel y al entrar en la app
le decía que su suscripción había caducado. Su perfil tenía `status: "activo"` y el ciclo
terminado el 20 de julio. No era uno: en producción eran 60 de los 184 marcados activos.

La causa: el panel pintaba `status` a pelo, que es una etiqueta que alguien puso una vez y
no se entera de que pasa el tiempo, mientras que la puerta de la app usa
`estado_de_acceso`, que además mira cuándo se acaba lo pagado. Y para colmo la lista ni
siquiera traía `current_period_end`, así que aunque hubiera querido calcularlo no podía.

Aquí se fija que la respuesta del panel lleve el estado CALCULADO, con la misma regla.
"""
from datetime import datetime, timedelta, timezone

from core.plan_access import estado_de_acceso, has_active_access

AYER = (datetime.now(timezone.utc) - timedelta(days=28)).date().isoformat()
MANANA = (datetime.now(timezone.utc) + timedelta(days=28)).date().isoformat()


def _perfil(**extra):
    base = {"id": "p1", "user_id": "u1", "plan": "elm", "status": "activo"}
    base.update(extra)
    return base


def test_el_caso_de_carlos_el_panel_ya_no_dice_activo():
    """status activo + ciclo terminado = caducado, y lo dice igual en los dos sitios."""
    perfil = _perfil(current_period_end=AYER)
    assert has_active_access(perfil) is False
    assert estado_de_acceso(perfil) == {"activo": False, "motivo": "caducado"}


def test_con_el_ciclo_vivo_sigue_activo():
    perfil = _perfil(current_period_end=MANANA)
    assert estado_de_acceso(perfil)["activo"] is True


def test_sin_fecha_de_fin_manda_la_etiqueta():
    """Los 168 perfiles sin fecha de fin no pierden nada: ahí el estado del perfil es lo
    único que hay, y sigue mandando."""
    assert estado_de_acceso(_perfil())["activo"] is True
    assert estado_de_acceso(_perfil(status="baja"))["activo"] is False


def test_una_suscripcion_de_stripe_viva_manda_sobre_la_fecha():
    """Si Stripe dice que la suscripción está viva, una fecha vieja copiada de Calma no
    puede echarle: el que paga entra."""
    perfil = _perfil(current_period_end=AYER, stripe_subscription_id="sub_1",
                     subscription_status="active")
    assert estado_de_acceso(perfil)["activo"] is True


def test_el_motivo_distingue_al_que_nunca_empezo():
    """Al que termina se le dice que se le acabó; al que nunca contrató, otra cosa. De eso
    depende el mensaje que ve, y también la etiqueta del panel."""
    assert estado_de_acceso(_perfil(plan=None))["motivo"] == "sin_plan"
    assert estado_de_acceso(_perfil(status="pendiente_pago",
                                    checkout_status="created"))["motivo"] == "sin_pagar"
    assert estado_de_acceso(_perfil(current_period_end=AYER))["motivo"] == "caducado"


def test_la_lista_del_panel_pide_los_campos_que_hacen_falta():
    """El fallo de fondo era la proyección: sin `current_period_end` en la consulta, el
    panel no puede saber si el ciclo terminó ni queriendo. Si alguien la recorta, que se
    entere aquí y no en la cara de un cliente."""
    import inspect

    import routes.admin as admin

    fuente = inspect.getsource(admin.get_all_clients)
    for campo in ("current_period_end", "checkout_status", "status",
                  "stripe_subscription_id", "subscription_status", "access_until"):
        assert f'"{campo}": 1' in fuente, f"la lista del panel ya no pide {campo}"
    assert "estado_de_acceso(profile)" in fuente, "la lista dejó de mandar el estado calculado"
