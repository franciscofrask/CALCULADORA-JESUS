"""EL PANEL DEL EQUIPO: los arreglos del 24-08.

Cada prueba empieza por la persona a la que le pasaba:

  1. El lunes, Jenny abre el panel para decidir a quién ajusta. La tarjeta «Esta semana te
     tocan» le dice que a Fulano se le tocó el 17 de agosto, pulsa «Ver los N ordenados» y
     la tabla que se abre le dice del mismo cliente «15 de junio», en rojo. Dos fechas para
     la misma pregunta en la misma portada: la tarjeta resolvía el último ajuste contra el
     histórico y la lista mandaba el campo crudo del perfil, que la migración de Calma deja
     atrasado (medidos 52 de 200 perfiles). En la misma portada, el KPI «ajuste N» se
     contaba igual de mal: la portada pide las dos cosas a la vez y las pinta juntas.

  2. Un entrenador entra en la pestaña Membresía de cualquier cliente -- los ve todos desde
     el 13-08 --, le cambia el plan y se come un error: los tres controles de «Gestión de
     usuario» van contra endpoints de solo-admin.

  3. Un cliente marca «pregúntame en una semana» en la rutina del mes y al equipo le sale en
     «Piden comprar» como «Quiere comprar la rutina del mes»: se le llama a vender a quien
     acaba de pedir margen. ESTE SIGUE ABIERTO: aquí solo está el tipo nuevo del catálogo, y
     quien escribe el aviso (`routes/reports.py`) es de otro bloque. Ver la clase.

  4. Una tarea escrita por error se quedaba para siempre en la lista de otro: lo único que
     se podía hacer era marcarla hecha, o sea mentir en el registro que luego se lee en la
     ficha del cliente. El endpoint para borrarla existía y no lo llamaba nadie.

  5. «Fotos de progreso sin mirar» no sabe si se han mirado: nadie apunta quién ha visto una
     foto. Son las fotos de los últimos siete días y la lista se vacía sola.

Todas son puras: no hacen falta ni backend ni base de datos.
"""
from pathlib import Path

import pytest

from core.avisos_equipo import TIPOS_EQUIPO, es_de_dinero
from core.ultimo_ajuste import ajuste_de

RAIZ = Path(__file__).resolve().parents[2]
HOY = "2026-08-24"


def _fuente(ruta: str) -> str:
    return (RAIZ / ruta).read_text(encoding="utf-8")


def _trozo(ruta: str, desde: str, hasta: str) -> str:
    """El cuerpo de UNA función. Sin acotar, un arreglo que está en la de al lado da la
    prueba por buena: es justo lo que pasó con el último ajuste."""
    codigo = _fuente(ruta)
    i, j = codigo.find(desde), codigo.find(hasta)
    assert 0 < i < j, f"{ruta}: ya no están «{desde}» y «{hasta}» en ese orden"
    return codigo[i:j]


# ============ 1. UNA SOLA FECHA PARA «CUÁNDO SE LE TOCÓ POR ÚLTIMA VEZ» ============

class TestElUltimoAjusteDeLaLista:
    def test_manda_el_historico_cuando_el_campo_se_quedo_viejo(self):
        """El caso medido: el perfil dice el 15 de junio y su histórico, el 17 de agosto."""
        perfil = {"id": "c1", "ultimo_ajuste": "2026-06-15"}
        assert ajuste_de(perfil, {"c1": "2026-08-17"}, HOY) == "2026-08-17"

    def test_sin_historico_no_se_convierte_a_nadie_en_nunca_ajustado(self):
        # Los migrados cuyo ajuste no llegó a macro_history: si se derivara a pelo saldrían
        # los primeros de la lista del lunes, que es justo el fallo que esto vino a evitar.
        assert ajuste_de({"id": "c2", "ultimo_ajuste": "2026-05-01"}, {}, HOY) == "2026-05-01"

    def test_la_lista_de_clientes_resuelve_la_fecha_igual_que_la_tarjeta(self):
        """Si alguien vuelve a mandar el campo crudo, vuelven las dos fechas."""
        assert "await _ajustes_al_dia(profiles)" in _trozo(
            "backend/routes/admin.py", "async def get_all_clients", "async def get_client_detail"), (
            "el semáforo y la columna «Sin tocar» vuelven a leer el campo sin corregir")

    def test_y_tambien_el_kpi_de_la_portada(self):
        """El fallo que quedó abierto al arreglar solo la lista.

        La portada pide /admin/clients y /admin/dashboard-stats a la vez y los pinta juntos:
        el KPI «ajuste N» se contaba con el campo crudo del perfil (52 de 200 atrasados), o
        sea más rojos de los que hay al lado de una tabla que ya decía la fecha buena.
        """
        stats = _trozo("backend/routes/admin.py",
                       "async def get_dashboard_stats_v2", "async def get_upcoming_payments")
        assert "await _ajustes_al_dia(active_profiles)" in stats
        assert stats.find("_ajustes_al_dia") < stats.find("_semaforo_del_cliente(p, hablado_a"), (
            "la fecha hay que corregirla ANTES de contar el semáforo, no después")

    def test_la_fecha_se_resuelve_en_un_solo_sitio(self):
        """Las tres eran la misma copia de las mismas tres líneas, y arreglar una dejó las
        otras mintiendo. Ahora las tres llaman al mismo ayudante."""
        codigo = _fuente("backend/routes/admin.py")
        assert codigo.count("ultimos_ajustes_vigentes(") == 1
        assert codigo.count("await _ajustes_al_dia(") == 3


# ============ 2. «GESTIÓN DE USUARIO» ES DEL ADMIN ============

class TestGestionDeUsuarioSoloAdmin:
    def test_la_tarjeta_lleva_candado_de_rol(self):
        pagina = _fuente("frontend/src/pages/ClientDetailPage.jsx")
        i = pagina.find("Gestión de usuario</CardTitle>")
        assert i > 0, "ya no existe la tarjeta de gestión de usuario"
        antes = pagina[max(0, i - 800):i]
        assert "adminUser?.role === 'admin' && (" in antes, (
            "el entrenador vuelve a ver botones que el backend le niega con un 403")

    def test_la_baja_se_le_sigue_diciendo_al_entrenador_y_una_sola_vez(self):
        """El motivo de que su cliente no pueda entrar no puede desaparecer con la tarjeta.

        Y va escrito UNA vez: estuvo duplicado (una copia fuera para el entrenador y otra
        dentro de la tarjeta para el admin), y dos copias del mismo texto acaban diciendo
        cosas distintas en cuanto alguien retoca una.
        """
        pagina = _fuente("frontend/src/pages/ClientDetailPage.jsx")
        aviso = "Usuario dado de baja: no puede entrar en la app."
        assert pagina.count(aviso) == 1
        assert pagina.find(aviso) < pagina.find("adminUser?.role === 'admin' && ("), (
            "el aviso de baja se ha metido dentro del candado y el entrenador ya no lo ve")

    def test_los_tres_fallos_de_la_tarjeta_dicen_el_motivo(self):
        """Ninguno de los tres se come la respuesta del servidor.

        Se arreglaron el del rol y el del plan y se quedó fuera el de reactivar, que es el
        que menos se usa y el que más falta hace: si el servidor contesta «no tienes
        permiso», «No se pudo reactivar» a secas manda a mirar la red.
        """
        pagina = _fuente("frontend/src/pages/ClientDetailPage.jsx")
        assert "'Error al actualizar el plan'" not in pagina
        for por_defecto in ("No se pudo actualizar el plan", "Error al cambiar el rol",
                            "No se pudo reactivar", "No se pudo dar de baja"):
            assert f"mensajeDeError(e, '{por_defecto}')" in pagina, (
                f"«{por_defecto}» vuelve a tapar lo que contesta el servidor")


# ============ 3. APLAZAR NO ES COMPRAR ============

class TestElAplazamientoNoEsUnaVenta:
    """OJO: ESTO NO ESTÁ CERRADO, y las dos primeras pruebas no lo cierran.

    El tipo está en el catálogo y no cuenta como dinero, pero el aviso lo escribe
    `routes/reports.py` -- otro bloque -- y sigue mandándolo con `tipo="rutina_del_mes"`,
    así que en «Piden comprar» se sigue leyendo «Quiere comprar la rutina del mes». Con
    solo las dos de abajo, el fallo se quedaba vivo con la prueba en verde: la tercera es
    la que mira de verdad, y está en xfail hasta que cambie esa línea.
    """

    def test_tiene_su_propia_etiqueta_y_no_cuenta_como_dinero(self):
        tipo = TIPOS_EQUIPO["rutina_del_mes_aplazada"]
        assert tipo["etiqueta"] == "Aplazó la rutina del mes"
        assert tipo["dinero"] is False
        assert es_de_dinero("rutina_del_mes_aplazada") is False

    def test_la_compra_de_verdad_sigue_siendo_dinero(self):
        assert es_de_dinero("rutina_del_mes") is True

    @pytest.mark.xfail(reason="falta la línea de routes/reports.py (otro bloque): el "
                              "aplazamiento se sigue escribiendo con tipo rutina_del_mes")
    def test_el_aviso_del_aplazamiento_se_escribe_con_su_tipo(self):
        """La prueba que faltaba. El día que `reports.py` cambie esa línea esto pasa a
        XPASS: entonces se le quita el xfail y el caso queda cerrado de verdad."""
        codigo = _fuente("backend/routes/reports.py")
        i = codigo.find('titulo="Aplazó la rutina del mes"')
        assert i > 0, "ya no existe el aviso del aplazamiento en reports.py"
        assert 'tipo="rutina_del_mes_aplazada"' in codigo[max(0, i - 300):i], (
            "el aplazamiento se escribe con el tipo de la compra: el equipo lo ve en «Piden "
            "comprar» como «Quiere comprar la rutina del mes»")


# ============ 4. BORRAR UNA TAREA PUESTA POR ERROR ============

class TestBorrarUnaTarea:
    def test_la_pantalla_llama_al_endpoint_que_ya_existia(self):
        pagina = _fuente("frontend/src/pages/AdminTareasPage.jsx")
        assert "api.delete(`/admin/tareas/${t.id}`)" in pagina

    def test_el_boton_solo_sale_donde_el_backend_deja_borrar(self):
        """Manual y tuya, o admin: es lo que exige routes/tareas.py. Pintarlo donde va a dar
        403 es cambiar un fallo por otro."""
        pagina = _fuente("frontend/src/pages/AdminTareasPage.jsx")
        i = pagina.find("const puedeBorrar = ")
        assert i > 0
        regla = pagina[i:i + 200]
        assert "t.origen === 'manual'" in regla
        assert "t.creada_por === user?.id" in regla
        assert "user?.role === 'admin'" in regla


# ============ 5. EL RÓTULO DE LAS FOTOS DICE LO QUE HAY ============

class TestFotosNuevas:
    def test_ya_no_promete_saber_quien_las_ha_mirado(self):
        pagina = _fuente("frontend/src/pages/AdminPanelesPage.jsx")
        assert "Fotos de progreso sin mirar" not in pagina
        assert "Subidas en los últimos 7 días" in pagina

    def test_y_el_rotulo_cuadra_con_el_dato_que_manda_el_panel(self):
        # Si mañana el corte deja de ser de 7 días, el rótulo vuelve a mentir.
        panel = _fuente("backend/routes/paneles.py")
        assert "corte_fotos = (now - timedelta(days=7)).isoformat()" in panel
