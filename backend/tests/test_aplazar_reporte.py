"""
«¿No has podido hacer el programa completo estas 3 semanas? Márcalo y te lo aplazo 7 días.»

El botón guardaba la fecha en el perfil y la ventana del reporte seguía a lo suyo: al
cliente se le prometía un aplazamiento y su reporte vencía igual el lunes. Aquí se fija
que la promesa se cumple, que es lo único que importa de esta pieza.

Son pruebas de la regla, sin base ni servidor: `compute_client_report_state` recibe el
perfil y el `ahora`, así que se puede mover el reloj a mano.
"""
from datetime import datetime, timedelta, timezone

from routes.report_cadence import compute_client_report_state

# Un cliente con mensual en la semana 3 de su ciclo, que es cuando le toca.
ARRANQUE = datetime(2026, 7, 27, tzinfo=timezone.utc)      # lunes
PERFIL = {
    "id": "c1", "user_id": "u1", "plan": "nivel1",
    "cycle_start": ARRANQUE.isoformat(),
    "created_at": ARRANQUE.isoformat(),
}
CATALOGO = {"nivel1": {"habilitaciones": {"reportes": ["mensual"]},
                       "ciclo": {"semanas": 12}}}


def _estado(perfil, ahora):
    return compute_client_report_state(perfil, CATALOGO, ahora)


def _semana_con_reporte():
    """El primer momento del ciclo en el que su ventana está abierta."""
    ahora = ARRANQUE + timedelta(days=1)
    for _ in range(80):
        e = _estado(PERFIL, ahora)
        if e["due"]:
            return ahora, e
        ahora += timedelta(days=1)
    raise AssertionError("a este cliente no le toca ningún reporte en 80 días")


def test_sin_aplazar_la_ventana_es_la_de_siempre():
    _, estado = _semana_con_reporte()
    assert estado["due"] is True
    # El mensual: viernes 00:00 -> lunes 18:00, hora de España (doc 16-08).
    assert estado["window_close"] - estado["window_open"] == timedelta(days=3, hours=18)


def test_aplazar_corre_la_ventana_siete_dias():
    ahora, antes = _semana_con_reporte()
    perfil = {**PERFIL,
              "reporte_aplazado_hasta": (antes["window_close"] + timedelta(days=7)).isoformat(),
              "reporte_aplazado_tipo": "mensual"}
    despues = _estado(perfil, ahora)

    assert despues["window_open"] == antes["window_open"] + timedelta(days=7)
    assert despues["window_close"] == antes["window_close"] + timedelta(days=7)
    # Y hoy ya no puede enviarlo: se le dijo que se vuelve a abrir el viernes que viene.
    assert despues["is_open"] is False


def test_el_reporte_aplazado_sigue_siendo_suyo_la_semana_que_viene():
    """La semana siguiente su patrón puede no tocar nada. Sin guardar el tipo, el reporte
    aplazado se evaporaría y el cliente se quedaría sin mandarlo."""
    ahora, antes = _semana_con_reporte()
    hasta = antes["window_close"] + timedelta(days=7)
    perfil = {**PERFIL, "reporte_aplazado_hasta": hasta.isoformat(),
              "reporte_aplazado_tipo": "mensual"}

    dentro_de_una_semana = ahora + timedelta(days=7)
    estado = _estado(perfil, dentro_de_una_semana)
    assert "mensual" in estado["tipos"]
    assert estado["due"] is True


def test_un_aplazamiento_caducado_no_pinta_nada():
    """Pasada la fecha, se vuelve a la ventana normal: si no, un aplazamiento viejo dejaría
    el reporte abierto para siempre."""
    ahora, antes = _semana_con_reporte()
    perfil = {**PERFIL,
              "reporte_aplazado_hasta": (ahora - timedelta(days=3)).isoformat(),
              "reporte_aplazado_tipo": "mensual"}
    estado = _estado(perfil, ahora)
    assert estado["window_open"] == antes["window_open"]
    assert estado["window_close"] == antes["window_close"]
