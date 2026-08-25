# -*- coding: utf-8 -*-
"""Los puntos 43-48 y 61 del doc de Jesus del 24-08: el panel y el dinero.

Lo que se protege aqui:

  46  Las dos cifras del negocio salen de UNA sola funcion. El MRR del Inicio del panel y
      la «Factura al mes» de Paneles > Direccion daban 20.062 EUR y 31.945 EUR de los
      mismos clientes el mismo dia. Si vuelven a discrepar, este fichero se pone rojo.
  61  «Sin entrenador» se calcula en el servidor y con el plan delante: 10 en Operaciones
      contra 83 en Clientes eran dos consultas distintas, una de ellas en el navegador.
  43  El cobro real viaja a la ficha, y el precio congelado de la ficha no se toca.
  44  El ciclo de un cliente se puede pisar desde el panel (hasta hoy no habia pantalla).
  45  Quien renueva solo se dice, y se distingue Stripe de «el plan dice que si».
  48  El boton de restablecer la contrasena esta en la ficha y avisa de lo que rompe.
"""
import os
import pathlib

import pytest
import requests

from routes.admin import (_cadencia_de_cobro, _plan_con_entrenador, _renueva_solo,
                          cobro_de, euros_al_mes, importe_de_ciclo, meses_de_cobro)

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"
FRONT = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src"

CAT = {
    "nivel3": {"ciclo": {"tipo": "trimestral", "semanas": 12}, "billing_cycle_weeks": 12,
               "precio": 1800, "habilitaciones": {"acompanamiento": "con_entrenador"},
               "renovacion": {"automatica": True}},
    "elm": {"ciclo": {"tipo": "mensual", "semanas": None}, "billing_cycle_weeks": 4,
            "precio": 97, "habilitaciones": {"acompanamiento": "solo_app"}},
}


def fuente(relativo: str) -> str:
    return (FRONT / relativo).read_text(encoding="utf-8")


def cabecera(token):
    return {"Authorization": f"Bearer {token}"}


# ==================== 43 · manda el cobro real, la ficha no se toca ====================

class TestElCobroRealManda:
    def test_montalvo_cuenta_por_lo_que_paga_no_por_lo_que_pone_la_ficha(self):
        # La ficha dice 1.500 y Stripe le cobra 250: para el negocio manda el 250.
        perfil = {"plan": "nivel3", "price": 1500}
        assert importe_de_ciclo(perfil, CAT, {"importe": 250}) == (250.0, "cobro_real")

    def test_sin_cobro_manda_el_precio_congelado_y_nunca_la_tarifa_nueva(self):
        # Jesus, 24-08: los clientes del sistema anterior conservan su precio congelado.
        perfil = {"plan": "elm", "price": 60.5}
        assert importe_de_ciclo(perfil, CAT, None) == (60.5, "ficha")

    def test_el_de_cortesia_no_paga_aunque_tenga_cobros_viejos(self):
        perfil = {"plan": "nivel3", "comp_plan": True}
        assert euros_al_mes(perfil, CAT, {"importe": 1800}) == 0.0

    def test_con_stripe_vivo_el_lapiz_del_panel_no_tapa_el_cobro(self):
        """«Como manda Stripe, la ficha tiene que leer de ahi y no dejar editarlo a mano»
        (punto 43, literal). Un importe escrito a mano por encima de una suscripcion viva
        es exactamente el panel mintiendo sobre lo que se ingresa."""
        perfil = {"plan": "nivel3", "renovacion_importe_prevision": 1500,
                  "stripe_subscription_id": "sub_1", "subscription_status": "active"}
        assert importe_de_ciclo(perfil, CAT, {"importe": 250}) == (250.0, "cobro_real")

    def test_sin_stripe_el_lapiz_sigue_mandando(self):
        """La otra mitad de la regla: «y donde no hay Stripe, el cobro que haya». El lapiz
        es para las transferencias, y ahi nadie mas sabe lo que va a pagar."""
        perfil = {"plan": "nivel3", "renovacion_importe_prevision": 1500}
        assert importe_de_ciclo(perfil, CAT, {"importe": 250}) == (1500.0, "a_mano")


# ==================== 46 · cada cobro vale los meses que cubre ====================

class TestMesesDeCobro:
    STRIPE_MENSUAL = {"plan": "nivel3", "stripe_subscription_id": "sub_1",
                      "subscription_status": "active",
                      "current_period_start": "2026-08-08", "current_period_end": "2026-09-08"}

    def test_el_premium_mensual_deja_lo_que_paga_al_mes(self):
        """EL CASO MONTALVO, EN DINERO. Plan trimestral en el catalogo, Stripe cobrando
        250 EUR cada mes: repartir esos 250 entre las 12 semanas del plan lo contaba a
        90,52 EUR/mes, o sea le quitaba al negocio dos tercios de ese cliente."""
        assert euros_al_mes(self.STRIPE_MENSUAL, CAT, {"importe": 250}) == 250.0

    def test_las_12_semanas_de_verdad_se_reparten_como_siempre(self):
        p = {"plan": "nivel3", "stripe_subscription_id": "sub_1",
             "subscription_status": "active",
             "current_period_start": "2026-07-24", "current_period_end": "2026-10-16"}
        assert round(euros_al_mes(p, CAT, {"importe": 847}), 2) == round(847 * 4.345 / 12, 2)

    def test_un_periodo_raro_no_se_toma_como_contrato(self):
        # 67 dias no son ni meses ni semanas justas: es un cobro movido a mano. Ahi manda
        # el ciclo del plan, que es lo unico que se sabe de verdad.
        p = {**self.STRIPE_MENSUAL, "current_period_end": "2026-10-14"}   # 67 dias
        assert round(meses_de_cobro(p, CAT["nivel3"]), 4) == round(12 / 4.345, 4)

    def test_sin_suscripcion_viva_el_periodo_no_cuenta(self):
        # `current_period_*` tambien los escribe la renovacion de la casa; sin Stripe
        # detras no describen ningun cobro.
        p = {k: v for k, v in self.STRIPE_MENSUAL.items()
             if k not in ("stripe_subscription_id", "subscription_status")}
        assert round(meses_de_cobro(p, CAT["nivel3"]), 4) == round(12 / 4.345, 4)

    def test_el_mensual_del_catalogo_sigue_valiendo_un_mes(self):
        assert meses_de_cobro({"plan": "elm"}, CAT["elm"]) == 1.0


# ==================== El correo, siempre normalizado ====================

class TestElCorreoNoSeEscapaPorUnaMayuscula:
    def test_el_mapa_de_cobros_se_lee_igual_venga_como_venga(self):
        """La ficha buscaba con `email.lower()` y la lista con el correo tal cual: al
        primero que se dé de alta con una mayuscula, la ficha le veria el cobro y el panel
        le pondria el precio de tarifa. Dos pantallas, dos numeros, otra vez."""
        cobros = {"ana@correo.com": {"importe": 300}}
        assert cobro_de(cobros, "Ana@Correo.com ") == {"importe": 300}
        assert cobro_de(cobros, None) is None


# ==================== 44 · la cadencia real contra la del plan ====================

class TestCadencia:
    def test_el_premium_mensual_se_detecta(self):
        # El caso de Montalvo: plan trimestral de 12 semanas, Stripe cobrando del 8 de
        # agosto al 8 de septiembre.
        c = _cadencia_de_cobro(
            {"plan": "nivel3", "current_period_start": "2026-08-08T00:00:00+00:00",
             "current_period_end": "2026-09-08T00:00:00+00:00"}, CAT)
        assert c["real"] == "cada mes" and c["plan"] == "cada 12 semanas"
        assert c["discrepan"] is True

    def test_las_12_semanas_de_verdad_no_avisan(self):
        c = _cadencia_de_cobro(
            {"plan": "nivel3", "current_period_start": "2026-07-24",
             "current_period_end": "2026-10-16"}, CAT)
        assert c["dias_reales"] == 84 and c["discrepan"] is False

    def test_sin_periodo_de_stripe_no_se_inventa_nada(self):
        c = _cadencia_de_cobro({"plan": "nivel3"}, CAT)
        assert c["real"] is None and c["discrepan"] is False

    def test_un_trimestre_de_92_dias_no_es_otra_cadencia(self):
        """84 dias y 92 son el mismo trimestre. Con una holgura fija de 4 dias, la ficha
        avisaba de que «se le cobra cada 3 meses y su plan cuenta 12 semanas», que es la
        misma frase dicha de dos maneras: un aviso que no significa nada acaba con que
        nadie mire los que si."""
        c = _cadencia_de_cobro(
            {"plan": "nivel3", "current_period_start": "2026-07-24",
             "current_period_end": "2026-10-24"}, CAT)
        assert c["dias_reales"] == 92 and c["discrepan"] is False


# ==================== 45 · quien renueva solo ====================

class TestRenuevaSolo:
    def test_stripe_vivo_es_el_unico_que_cobra_solo(self):
        p = {"plan": "elm", "stripe_subscription_id": "sub_1", "subscription_status": "active"}
        assert _renueva_solo(p, CAT) == {"automatica": True, "via": "stripe"}

    def test_el_plan_automatico_se_dice_aparte(self):
        # No es lo mismo que Stripe le cobre solo a que su plan diga que renueva: hasta hoy
        # los dos salian del mismo color en Direccion.
        assert _renueva_solo({"plan": "nivel3"}, CAT) == {"automatica": True, "via": "plan"}

    def test_suscripcion_muerta_no_renueva(self):
        p = {"plan": "elm", "stripe_subscription_id": "sub_1", "subscription_status": "canceled"}
        assert _renueva_solo(p, CAT) == {"automatica": False, "via": None}


# ==================== 61 · el criterio de «sin entrenador» ====================

class TestSinEntrenador:
    def test_el_plan_de_autogestion_no_cuenta(self):
        assert _plan_con_entrenador(CAT["elm"]) is False
        assert _plan_con_entrenador(CAT["nivel3"]) is True

    def test_un_plan_que_no_esta_en_el_catalogo_no_apunta_trabajo_a_nadie(self):
        assert _plan_con_entrenador(None) is False
        assert _plan_con_entrenador({}) is False


# ==================== En vivo: las dos pantallas dicen lo mismo ====================

@pytest.mark.usefixtures("api_disponible")
class TestLasDosPantallas:
    def test_el_mrr_y_la_factura_al_mes_son_el_mismo_numero(self, token_admin):
        """EL PUNTO 46 EN UNA LINEA. Dos pantallas del mismo panel, el mismo dinero."""
        inicio = requests.get(f"{API}/admin/dashboard-stats", headers=cabecera(token_admin),
                              timeout=60).json()
        direccion = requests.get(f"{API}/admin/paneles/direccion", headers=cabecera(token_admin),
                                 timeout=60).json()
        assert inicio.get("mrr") == direccion.get("factura_mes")

    def test_direccion_cuenta_a_los_mismos_que_el_inicio(self, token_admin):
        inicio = requests.get(f"{API}/admin/dashboard-stats", headers=cabecera(token_admin),
                              timeout=60).json()
        direccion = requests.get(f"{API}/admin/paneles/direccion", headers=cabecera(token_admin),
                                 timeout=60).json()
        assert direccion["cartera"]["con_acceso"] == inicio["active_clients"]
        # Y dice cuantos se ha dejado fuera, que es lo que evita leer la bajada como una
        # caida del negocio.
        assert direccion["cartera"]["caducados_fuera"] == inicio["caducados_clients"]

    def test_los_sin_entrenador_de_operaciones_estan_todos_en_la_lista(self, token_admin):
        """Nadie a quien Operaciones apunte trabajo puede faltar en la pestana de Clientes."""
        ops = requests.get(f"{API}/admin/paneles/operaciones", headers=cabecera(token_admin),
                           timeout=60).json()
        clientes = requests.get(f"{API}/admin/clients", headers=cabecera(token_admin),
                                timeout=60).json()
        marcados = {c["id"] for c in clientes if c.get("sin_entrenador")}
        assert {c["client_id"] for c in ops["sin_entrenador"]["clientes"]} <= marcados

    def test_el_marcado_nunca_tiene_entrenador(self, token_admin):
        clientes = requests.get(f"{API}/admin/clients", headers=cabecera(token_admin),
                                timeout=60).json()
        assert not [c for c in clientes if c.get("sin_entrenador") and c.get("trainer_id")]

    def test_cada_fila_lleva_su_al_mes_y_si_renueva_sola(self, token_admin):
        clientes = requests.get(f"{API}/admin/clients", headers=cabecera(token_admin),
                                timeout=60).json()
        con_ficha = [c for c in clientes if c.get("id")]
        assert con_ficha, "sin clientes en la base de pruebas"
        for c in con_ficha[:20]:
            assert isinstance(c.get("precio_mensual"), (int, float))
            assert set(c.get("renueva_solo") or {}) == {"automatica", "via"}


# ==================== En vivo: la ficha ====================

@pytest.fixture(scope="module")
def cliente(token_admin):
    """Un cliente cualquiera con ficha, para probar contra el de verdad."""
    filas = requests.get(f"{API}/admin/clients", headers=cabecera(token_admin),
                         timeout=60).json()
    con_ficha = [c for c in filas if c.get("id")]
    if not con_ficha:
        pytest.skip("no hay clientes con ficha en esta base")
    return con_ficha[0]["id"]


@pytest.mark.usefixtures("api_disponible")
class TestLaFicha:
    def test_la_ficha_trae_el_cobro_real_y_la_cadencia(self, token_admin, cliente):
        d = requests.get(f"{API}/admin/clients/{cliente}", headers=cabecera(token_admin),
                         timeout=60).json()["profile"]
        assert "ultimo_cobro" in d and "cadencia" in d and "renueva_solo" in d
        assert set(d["cadencia"]) >= {"real", "plan", "discrepan"}
        if d["ultimo_cobro"]:
            assert d["ultimo_cobro"]["importe"] > 0

    def test_ponerle_su_propio_ciclo_y_devolverlo_al_del_plan(self, token_admin, cliente):
        """PUNTO 44: hasta hoy los tres campos existian y no habia pantalla que los tocara."""
        antes = requests.get(f"{API}/admin/clients/{cliente}", headers=cabecera(token_admin),
                             timeout=60).json()["profile"]
        try:
            r = requests.put(f"{API}/admin/clients/{cliente}/ciclo",
                             json={"ciclo_semanas": 5, "semana_de_entrada": 2},
                             headers=cabecera(token_admin), timeout=30)
            assert r.status_code == 200, r.text
            assert r.json()["ciclo_semanas"] == 5
            # Y el calendario resuelto ya cuenta con el ciclo nuevo, que es lo que mueve
            # los reportes y las ventanas.
            assert r.json()["calendario"]["duracion_semanas"] == 5
            assert r.json()["calendario"]["semana_de_entrada"] == 2
        finally:
            volver = {"ciclo_semanas": antes.get("ciclo_semanas"),
                      "semana_de_entrada": antes.get("semana_de_entrada"),
                      "calendario_reportes": antes.get("calendario_reportes")}
            requests.put(f"{API}/admin/clients/{cliente}/ciclo", json=volver,
                         headers=cabecera(token_admin), timeout=30)
        despues = requests.get(f"{API}/admin/clients/{cliente}", headers=cabecera(token_admin),
                               timeout=60).json()["profile"]
        assert despues.get("ciclo_semanas") == antes.get("ciclo_semanas")

    @pytest.mark.parametrize("cuerpo", [
        {"ciclo_semanas": 0},
        {"ciclo_semanas": 60},
        {"ciclo_semanas": "doce"},
        {"semana_de_entrada": -1},
        {"calendario_reportes": {"patron": ["", "quincenal", "lo que sea"]}},
        {"calendario_reportes": "mensual"},
    ])
    def test_un_ciclo_imposible_no_entra(self, token_admin, cliente, cuerpo):
        r = requests.put(f"{API}/admin/clients/{cliente}/ciclo", json=cuerpo,
                         headers=cabecera(token_admin), timeout=30)
        assert r.status_code == 400, r.text

    def test_el_entrenador_no_toca_el_contrato(self, token_cliente, cliente):
        # El ciclo es contrato: solo admin. Con un token que no lo es, ni se intenta.
        r = requests.put(f"{API}/admin/clients/{cliente}/ciclo", json={"ciclo_semanas": 4},
                         headers=cabecera(token_cliente), timeout=30)
        assert r.status_code in (401, 403)


# ==================== Las pantallas dicen lo que hacen ====================

class TestLoQueSeVeEnPantalla:
    def test_la_ficha_tiene_el_boton_de_restablecer_y_avisa(self):
        """PUNTO 48: el endpoint ya existia; lo que no habia era boton ni aviso."""
        src = fuente("pages/ClientDetailPage.jsx")
        assert "reset-password" in src
        assert "restablecer-clave" in src
        # El aviso de que le rompe la clave de siempre al que vino de la plataforma
        # anterior (le borra el hash heredado de Firebase).
        assert "plataforma anterior" in src

    def test_direccion_explica_por_que_baja_la_cifra(self):
        """PUNTO 46: la factura baja de 31.945 a unos 21.000 y hay que decir por que."""
        src = fuente("pages/AdminPanelesPage.jsx")
        assert "aviso-caducados-fuera" in src
        assert "caducados_fuera" in src

    def test_clientes_explica_el_salto_de_la_pestana_sin_entrenador(self):
        """PUNTO 61: la pestana se abre por defecto y pasa de 83 filas a 10."""
        src = fuente("pages/AdminDashboard.jsx")
        assert "sin-coach-por-plan" in src
        assert "sin_entrenador" in src

    def test_la_ficha_dice_si_ha_entrado_alguna_vez(self):
        """PUNTO 48, la otra mitad: «no hay ninguna pantalla que diga quien ha entrado
        alguna vez». El dato ya viajaba a la lista y la ficha no lo enseñaba."""
        src = fuente("pages/ClientDetailPage.jsx")
        assert "ultima-entrada" in src
        assert "ultima_entrada" in src

    def test_la_ficha_dice_por_cuanto_cuenta_el_cliente_al_mes(self):
        """PUNTO 46: `euros_al_mes` se calculaba, viajaba a la ficha y no lo pintaba nadie.
        Es el numero que suma la «Factura al mes» de Direccion, cliente a cliente."""
        assert "euros-al-mes" in fuente("pages/ClientDetailPage.jsx")

    def test_direccion_no_lleva_cifras_clavadas_a_mano_en_el_texto(self):
        """El aviso de la bajada llevaba escrito «daba 11.000 € menos que esta pantalla».
        Una cifra medida un martes y clavada en el codigo envejece y acaba mintiendo desde
        la propia pantalla que explica por que no hay que fiarse de las cifras viejas."""
        aviso = fuente("pages/AdminPanelesPage.jsx").split("aviso-caducados-fuera")[1][:800]
        assert "11.000" not in aviso and "31.945" not in aviso
