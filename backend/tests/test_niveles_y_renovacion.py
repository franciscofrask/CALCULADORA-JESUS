"""
Los tres niveles nuevos y que renovar no rompa a nadie (especificacion 31-07-2026, parte 1).

Los tres niveles sustituyen a lo anterior como lo unico contratable. La regla que manda:

    "los planes actuales siguen funcionando igual para quien los tiene y dejan de poder
    contratarse. A nadie se le cambia nada." Y al renovar, se elige entre los nuevos.

Lo que mas se vigila aqui es lo segundo: hay 190 clientes con planes viejos y ninguno
puede quedarse sin acceso a lo que pago porque su plan haya pasado a legacy.
"""
import pytest

from models.user import (
    NIVELES,
    PLAN_CATALOG,
    derive_features,
    get_plan,
    opciones_de_renovacion,
    plan_habilitaciones,
    planes_contratables,
)

LEGACY_QUE_NOMBRA_EL_DOC = ("reto12en12_gold", "gold", "silver", "bronze", "elm")
# Los que el documento no nombra y se decidieron aparte (02-08-2026): dejan de venderse
# tambien, porque los tres niveles sustituyen a todo lo anterior.
LEGACY_DECIDIDOS = ("reto60", "calculadora_jp", "mantenimiento")


class TestLosTresNiveles:
    def test_existen_los_tres(self):
        for code in NIVELES:
            assert code in PLAN_CATALOG, f"falta {code}"

    @pytest.mark.parametrize("code,precio", [("nivel1", 297.0), ("nivel2", 897.0), ("nivel3", 1497.0)])
    def test_los_precios_del_documento(self, code, precio):
        assert PLAN_CATALOG[code]["precio"] == precio

    def test_todos_de_12_semanas(self):
        for code in NIVELES:
            assert PLAN_CATALOG[code]["ciclo"]["semanas"] == 12

    def test_el_1_no_lleva_rutina_y_los_otros_si(self):
        assert plan_habilitaciones("nivel1")["rutina"] == "ninguna"
        assert plan_habilitaciones("nivel2")["rutina"] == "personalizada"
        assert plan_habilitaciones("nivel3")["rutina"] == "personalizada"

    def test_el_1_reporta_al_mes_y_los_otros_cada_quince_dias(self):
        assert plan_habilitaciones("nivel1")["reportes"] == ["mensual"]
        for code in ("nivel2", "nivel3"):
            assert "quincenal" in plan_habilitaciones(code)["reportes"]

    def test_lo_que_separa_al_2_del_3(self):
        """Es lo unico que los distingue ademas del precio, y por eso se añadieron
        los dos campos de acompañamiento."""
        dos, tres = plan_habilitaciones("nivel2"), plan_habilitaciones("nivel3")
        assert dos["acompanamiento"] == "con_entrenador"
        assert tres["acompanamiento"] == "con_entrenador_y_llamadas"
        assert dos["frecuencia_contacto"] == "quincenal"
        assert tres["frecuencia_contacto"] == "semanal"

    def test_el_1_se_autogestiona(self):
        assert plan_habilitaciones("nivel1")["acompanamiento"] == "solo_app"


class TestAQuienYaTienePlanNoSeLeToca:
    """La regla que no se puede romper: hay 190 clientes con planes viejos."""

    @pytest.mark.parametrize("code", LEGACY_QUE_NOMBRA_EL_DOC)
    def test_el_plan_legacy_sigue_existiendo(self, code):
        assert get_plan(code) is not None, f"{code} ha desaparecido del catalogo"

    @pytest.mark.parametrize("code", LEGACY_QUE_NOMBRA_EL_DOC)
    def test_y_conserva_sus_habilitaciones(self, code):
        """Pasar a legacy no puede quitarle nada a quien lo tiene."""
        hab = plan_habilitaciones(code)
        assert hab, f"{code} se ha quedado sin habilitaciones"
        assert "calculadora" in hab

    def test_el_reto_gold_sigue_dando_lo_mismo_que_antes(self):
        f = derive_features(plan_habilitaciones("reto12en12_gold"))
        assert f, "el Reto Gold se ha quedado sin features"

    @pytest.mark.parametrize("code", LEGACY_QUE_NOMBRA_EL_DOC)
    def test_se_le_puede_seguir_asignando_al_que_lo_tenia(self, code):
        """`asignable` sigue en True: el admin tiene que poder arreglar el plan de un
        cliente antiguo sin obligarle a cambiar de producto."""
        assert PLAN_CATALOG[code]["asignable"] is True


class TestYaNoSeVenden:
    @pytest.mark.parametrize("code", LEGACY_QUE_NOMBRA_EL_DOC)
    def test_no_estan_entre_los_contratables(self, code):
        assert code not in planes_contratables()

    @pytest.mark.parametrize("code", LEGACY_DECIDIDOS)
    def test_los_demas_tampoco_se_venden_ya(self, code):
        assert code not in planes_contratables()
        assert get_plan(code) is not None, "pero sigue existiendo para quien lo tenga"

    def test_lo_unico_contratable_son_los_tres_niveles(self):
        assert set(planes_contratables()) == set(NIVELES)


class TestLaMembresiaDeSalida:
    """"Membresia 97 EUR/mes: ya no es la entrada, es la salida para el que no renueva"."""

    def test_existe_y_cuesta_97(self):
        assert PLAN_CATALOG["membresia"]["precio"] == 97.0

    def test_no_se_puede_comprar_como_entrada(self):
        assert "membresia" not in planes_contratables()

    def test_pero_esta_disponible_como_salida(self):
        assert "membresia" in planes_contratables(incluir_salida=True)

    def test_la_renovacion_la_ofrece_como_tercera_salida(self):
        """El documento da tres salidas: renovar, subir de nivel, o salir a la membresia."""
        assert opciones_de_renovacion("nivel2")["salida"] == "membresia"

    def test_es_distinta_de_elm(self):
        """Separada a proposito: ELM arrastra precios de 67 y 87, anual de 800 y Harbiz."""
        assert PLAN_CATALOG["membresia"]["habilitaciones"]["harbiz"] is False
        assert len(PLAN_CATALOG["membresia"]["precios"]) == 1
        assert PLAN_CATALOG["elm"]["estado"] == "legacy"


class TestLaRenovacion:
    def test_el_que_viene_de_un_plan_viejo_elige_entre_los_nuevos(self):
        r = opciones_de_renovacion("reto12en12_gold")
        assert r["puede_seguir_igual"] is False
        assert set(r["opciones"]) == set(NIVELES)
        assert r["motivo"]

    def test_el_que_ya_esta_en_un_nivel_puede_seguir_igual(self):
        r = opciones_de_renovacion("nivel2")
        assert r["puede_seguir_igual"] is True
        assert r["motivo"] is None

    def test_el_que_sigue_igual_conserva_su_precio(self):
        """"El precio se congela mientras el cliente no se de de baja"."""
        assert opciones_de_renovacion("nivel1")["mantiene_precio"] is True

    def test_el_que_cambia_de_plan_paga_el_nuevo(self):
        assert opciones_de_renovacion("gold")["mantiene_precio"] is False

    def test_sin_plan_tambien_se_le_ofrecen_los_tres(self):
        r = opciones_de_renovacion(None)
        assert set(r["opciones"]) == set(NIVELES)

    def test_un_plan_que_no_existe_no_revienta(self):
        r = opciones_de_renovacion("plan_inventado")
        assert set(r["opciones"]) == set(NIVELES)
        assert r["puede_seguir_igual"] is False


class TestStripe:
    @pytest.mark.parametrize("code", NIVELES)
    def test_cada_nivel_declara_su_variable_de_precio(self, code):
        """Sin producto en Stripe no se puede cobrar. La variable tiene que estar
        declarada para que el checkout falle con un 503 claro y no cobre mal."""
        assert PLAN_CATALOG[code]["stripe_price_env"].startswith("STRIPE_PRICE_")

    def test_los_tres_cobran_cada_12_semanas(self):
        for code in NIVELES:
            assert PLAN_CATALOG[code]["billing_cycle_weeks"] == 12
