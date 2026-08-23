"""Mis macros, doc del 23-08: la fecha de revisión es UNA (P25) y todo guardado de
macros pasa por el histórico (P27).

P25: la cabecera decía «Próxima revisión: 31 de agosto» (plazo del catálogo) con un
botón que se abría el 6 de septiembre (core/ventana_revision). Ahora la próxima sale
de la MISMA ventana que el botón.

P27: el PUT genérico del panel hacía $set de macros_training/rest/peri sin escribir
macro_history, que es lo que alimenta la vigencia por fecha, los avisos y el modelo
predictivo. Ese camino queda cerrado en alto (400), no en silencio.
"""
import requests

from conftest import API


def _perfil_de(cabeceras):
    r = requests.get(f"{API}/clients/profile", headers=cabeceras, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def test_25_la_proxima_revision_es_la_de_la_ventana(cabeceras_cliente):
    """Las dos fechas salen del mismo sitio: la ventana del botón Revisar."""
    perfil = _perfil_de(cabeceras_cliente)
    ventana = perfil.get("ventana_revision") or {}

    # La cabecera de Mis macros bebe de /macros/historial, no de /macros.
    r = requests.get(f"{API}/macros/historial", headers=cabeceras_cliente, timeout=30)
    assert r.status_code == 200, r.text
    datos = r.json()

    if ventana.get("abierta"):
        # Abierta: la próxima es hoy (ya puede revisar); lo que no puede es ser una
        # fecha futura inventada por otro motor.
        assert datos.get("proxima_revision"), "con la ventana abierta la cabecera se queda sin fecha"
    elif ventana.get("se_abre"):
        assert datos.get("proxima_revision") == ventana["se_abre"], (
            f"la cabecera dice {datos.get('proxima_revision')} y el botón se abre el "
            f"{ventana['se_abre']}: siguen saliendo de dos sitios")


def test_27_el_put_generico_no_traga_macros(cabeceras_admin, cabeceras_cliente):
    """Guardar macros por el PUT genérico del panel se rechaza con frase clara."""
    perfil = _perfil_de(cabeceras_cliente)
    antes = perfil.get("macros_training")

    r = requests.put(f"{API}/admin/clients/{perfil['id']}", headers=cabeceras_admin,
                     json={"macros_training": {"protein": 111, "carbs": 222, "fat": 33}},
                     timeout=30)
    assert r.status_code == 400, (
        f"el PUT genérico aceptó macros ({r.status_code}): ese camino no escribe "
        "macro_history y deja el histórico cojo")
    assert "hist" in (r.json().get("detail") or "").lower() or "Macros" in (r.json().get("detail") or "")

    despues = _perfil_de(cabeceras_cliente).get("macros_training")
    assert despues == antes, "encima de rechazarlo, los macros cambiaron"


def test_27_el_resto_de_campos_del_put_generico_siguen_vivos(cabeceras_admin, cabeceras_cliente):
    """El candado es SOLO para macros: el resto de la ficha se sigue editando igual."""
    perfil = _perfil_de(cabeceras_cliente)
    notas = perfil.get("training_notes")
    r = requests.put(f"{API}/admin/clients/{perfil['id']}", headers=cabeceras_admin,
                     json={"training_notes": "prueba P27 (se restaura)"}, timeout=30)
    assert r.status_code == 200, r.text
    # Se deja como estaba: el cliente demo es la cuenta de referencia.
    requests.put(f"{API}/admin/clients/{perfil['id']}", headers=cabeceras_admin,
                 json={"training_notes": notas or ""}, timeout=30)
