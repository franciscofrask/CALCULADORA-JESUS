"""
El catálogo tras el doc del 19-08 («Admin › Planes», los trece fallos) y que renovar no
rompa a nadie.

Lo que fija este fichero es la foto NUEVA: los que se venden son cinco -- Calculadora
(nivel1), Gold (nivel2), Premium (nivel3), El Lunes Empiezo y Mantenimiento --, los
nombres y precios son los del doc, y el que termina ciclo y no renueva aterriza en
Mantenimiento. La regla que sigue mandando de antes: a quien tiene un plan viejo no se le
cambia nada, y ninguno de los ~190 con planes legacy puede quedarse sin lo que pagó.
"""
import pytest

from models.user import (
    NIVELES,
    PLAN_CATALOG,
    codigo_de_plan,
    derive_features,
    get_plan,
    opciones_de_renovacion,
    plan_habilitaciones,
    planes_contratables,
)

# Los legacy con gente dentro que el doc del 19-08 deja quedarse.
LEGACY_CON_GENTE = ("reto12en12_gold", "gold", "silver", "bronze", "calma12",
                    "personalizado", "basica", "reto12en12", "calculadora_jp")
# Los que retira del todo (0 clientes): ya ni se pueden asignar.
RETIRADOS = ("reto12en12_silver", "reto60")


class TestLosCincoActivos:
    def test_los_nombres_del_documento(self):
        """Fallo 01: «El método / Con seguimiento / Acompañamiento total» eran de una
        versión anterior y eran los que veía el cliente en su ficha."""
        assert PLAN_CATALOG["nivel1"]["name"] == "Calculadora"
        assert PLAN_CATALOG["nivel2"]["name"] == "Gold"
        assert PLAN_CATALOG["nivel3"]["name"] == "Premium"

    @pytest.mark.parametrize("code,precio", [("nivel1", 247.0), ("nivel2", 847.0), ("nivel3", 1500.0)])
    def test_los_precios_del_documento(self, code, precio):
        """Fallo 02: ponía 297 donde son 247 y 897 donde son 847."""
        assert PLAN_CATALOG[code]["precio"] == precio

    def test_se_venden_cinco_no_cuatro(self):
        """Fallo 06: ELM y Mantenimiento suben a activos. Mantenimiento es la salida
        (solo_salida), así que lo contratable directo son los tres niveles y ELM."""
        assert set(planes_contratables()) == set(NIVELES) | {"elm"}
        assert set(planes_contratables(incluir_salida=True)) == set(NIVELES) | {"elm", "mantenimiento"}

    def test_todos_de_12_semanas(self):
        for code in NIVELES:
            assert PLAN_CATALOG[code]["ciclo"]["semanas"] == 12

    def test_la_calculadora_lleva_la_rutina_del_mes(self):
        """La ficha del doc: «Rutina: La del mes» (antes ninguna)."""
        assert plan_habilitaciones("nivel1")["rutina"] == "del_mes"
        assert plan_habilitaciones("nivel2")["rutina"] == "personalizada"
        assert plan_habilitaciones("nivel3")["rutina"] == "personalizada"

    def test_cada_nivel_reporta_a_su_ritmo(self):
        assert plan_habilitaciones("nivel1")["reportes"] == ["mensual"]
        assert "quincenal" in plan_habilitaciones("nivel2")["reportes"]
        assert "semanal" in plan_habilitaciones("nivel3")["reportes"]
        assert "quincenal" not in plan_habilitaciones("nivel3")["reportes"]

    def test_quien_edita_sus_macros(self):
        """Fallo 08, «la diferencia más importante entre unos planes y otros»: el de
        autogestión sí; al Gold y al Premium se los lleva su entrenador."""
        assert plan_habilitaciones("nivel1")["edita_macros"] is True
        assert plan_habilitaciones("elm")["edita_macros"] is True
        assert plan_habilitaciones("mantenimiento")["edita_macros"] is True
        assert plan_habilitaciones("nivel2")["edita_macros"] is False
        assert plan_habilitaciones("nivel3")["edita_macros"] is False

    def test_la_suplementacion_ya_no_es_un_si_no(self):
        """Fallo 10: la guía para los de autogestión, protocolo para el personalizado."""
        assert plan_habilitaciones("nivel1")["suplementacion"] == "guia"
        assert plan_habilitaciones("mantenimiento")["suplementacion"] == "guia"
        assert plan_habilitaciones("elm")["suplementacion"] == "guia"
        assert plan_habilitaciones("nivel2")["suplementacion"] == "protocolo"
        assert plan_habilitaciones("nivel3")["suplementacion"] == "protocolo"

    def test_harbiz_murio(self):
        """Fallo 07: la fila entera, fuera de las 21 fichas."""
        for code, p in PLAN_CATALOG.items():
            assert "harbiz" not in (p.get("habilitaciones") or {}), f"{code} aún lleva harbiz"

    def test_quien_renueva_solo_y_quien_no(self):
        """La tabla del doc: Calculadora sí (12 semanas), Gold no (recontrata), Premium
        no (por llamada), ELM y Mantenimiento sí (mensual)."""
        assert PLAN_CATALOG["nivel1"]["renovacion"]["automatica"] is True
        assert PLAN_CATALOG["nivel2"]["renovacion"]["automatica"] is False
        assert PLAN_CATALOG["nivel3"]["renovacion"]["automatica"] is False
        assert PLAN_CATALOG["elm"]["renovacion"]["automatica"] is True
        assert PLAN_CATALOG["mantenimiento"]["renovacion"]["automatica"] is True

    def test_el_premium_no_esta_duplicado(self):
        """Fallo 03: el Premium que se vende es nivel3; el especial viejo queda en legacy
        (hasta mover a sus 9) y no se vende."""
        assert PLAN_CATALOG["premium"]["estado"] == "legacy"
        assert "premium" not in planes_contratables()

    def test_la_membresia_vacia_se_borro_y_cae_en_elm(self):
        """Fallo 04: la ficha «Membresía» a 97 € sin un solo cliente duplicaba a ELM. El
        alias evita que nada que apuntara a ella se quede sin plan."""
        assert "membresia" not in PLAN_CATALOG
        assert codigo_de_plan("membresia") == "elm"

    def test_elm_ya_no_se_contradice(self):
        """Fallo 05: decía «macros por tu entrenador» y «sin entrenador» a la vez."""
        h = plan_habilitaciones("elm")
        assert h["calculadora"] == "autogestion"
        assert h["acompanamiento"] == "solo_app"

    def test_elm_sigue_siendo_mensual_recurrente(self):
        from models.user import PLAN_TYPES
        assert PLAN_TYPES["elm"]["one_time"] is False
        assert PLAN_CATALOG["elm"]["ciclo"]["tipo"] == "mensual"

    def test_el_responsable_no_se_llama_ceo(self):
        """«Trece fichas ponen CEO en el campo de responsable. Que ponga Jesús.»"""
        for code, p in PLAN_CATALOG.items():
            assert "CEO" not in (p.get("responsable") or ""), f"{code} sigue con CEO"


class TestAQuienYaTienePlanNoSeLeToca:
    """La regla que no se puede romper: hay ~190 clientes con planes viejos."""

    @pytest.mark.parametrize("code", LEGACY_CON_GENTE)
    def test_el_plan_legacy_sigue_existiendo(self, code):
        assert get_plan(code) is not None, f"{code} ha desaparecido del catalogo"

    @pytest.mark.parametrize("code", LEGACY_CON_GENTE)
    def test_y_conserva_sus_habilitaciones(self, code):
        hab = plan_habilitaciones(code)
        assert hab, f"{code} se ha quedado sin habilitaciones"
        assert "calculadora" in hab

    @pytest.mark.parametrize("code", LEGACY_CON_GENTE)
    def test_se_le_puede_seguir_asignando_al_que_lo_tenia(self, code):
        assert PLAN_CATALOG[code]["asignable"] is True

    @pytest.mark.parametrize("code", LEGACY_CON_GENTE)
    def test_pero_ya_no_se_vende(self, code):
        assert code not in planes_contratables()

    @pytest.mark.parametrize("code", RETIRADOS)
    def test_los_retirados_ni_se_asignan(self, code):
        """Fallo 12 (parte fácil): Reto Silver y Reto 60 tienen 0 clientes y se retiran."""
        assert PLAN_CATALOG[code]["asignable"] is False

    def test_los_legacy_con_entrenador_no_editan_sus_macros(self):
        """La regla del doc: sin el campo, 68 personas con entrenador seguían viendo una
        pestaña que les invita a mover unos macros que no pueden mover."""
        for code in ("gold", "silver", "bronze", "reto12en12_gold", "personalizado", "plan_6m"):
            assert plan_habilitaciones(code)["edita_macros"] is False, code

    def test_los_legacy_de_autogestion_si(self):
        for code in ("calculadora_jp", "basica", "calma12"):
            assert plan_habilitaciones(code)["edita_macros"] is True, code

    def test_el_audio_esta_marcado_donde_el_doc_lo_pide(self):
        """«Falta marcarlo en Silver, Bronze, Premium, 6M, Personalizado y CALMA 12.»"""
        for code in ("silver", "bronze", "premium", "plan_6m", "personalizado", "calma12"):
            assert "audio" in derive_features(plan_habilitaciones(code)), code


class TestLosPlanesDeCalmaCaenEnAlgunSitio:
    """«Cuando se migren los 143, todos estos tienen que caer en algún sitio o pasará lo
    del CalMa que bloquea el alta.»"""

    @pytest.mark.parametrize("escrito,code", [
        ("Entrenamiento Personal 2", "entrenamiento_personal"),
        ("Entrenamiento Personal 4", "entrenamiento_personal"),
        ("Premium 423,50 mensual", "premium"),
        ("Premium 177 mensual", "premium"),
        ("Lunes Empiezo (Anual)", "elm"),
        ("El lunes empiezo (Julio)", "elm"),
        ("Silver 4-Trimestral", "silver"),
        ("Plan 6 M", "plan_6m"),
        ("Rutina del Mes Trimestral", "rutina_mes"),
        ("Plan Personalizado 500", "personalizado"),
        ("CalMa", "calma12"),
    ])
    def test_cada_variante_cae_en_su_plan(self, escrito, code):
        assert codigo_de_plan(escrito) == code

    def test_la_optimizacion_hormonal_tiene_donde_colgar(self):
        """El plan de 1.000 € de Benito Velasco: ya se vendió y no se vende más, pero sus
        cobros tienen que tener dónde colgar."""
        p = PLAN_CATALOG["optimizacion_hormonal"]
        assert p["estado"] == "legacy" and p["precio"] == 1000.0
        assert "optimizacion_hormonal" not in planes_contratables()


class TestLosComplementos:
    """«Hay dos y tienen que ser cuatro.»"""

    def test_son_cuatro(self):
        comp = [c for c, p in PLAN_CATALOG.items() if p.get("estado") == "complemento"]
        assert set(comp) == {"rutina_mes", "rutina_personalizada", "revision_macros", "formaciones"}

    def test_la_rutina_del_mes_tiene_los_dos_precios(self):
        precios = {p["importe"] for p in PLAN_CATALOG["rutina_mes"]["precios"]}
        assert precios == {57.0, 67.0}

    def test_la_rutina_personalizada_a_97(self):
        assert PLAN_CATALOG["rutina_personalizada"]["precio"] == 97.0

    def test_la_revision_de_macros_cuesta_lo_que_se_cobra(self):
        """La ficha del catálogo y el cobro real (`core/ajuste_a_medida.PRECIO_EUR`) no
        pueden decir dos números distintos."""
        from core.ajuste_a_medida import PRECIO_EUR
        assert PLAN_CATALOG["revision_macros"]["precio"] == PRECIO_EUR == 87.0

    def test_la_rutina_del_mes_interna_no_se_separa_del_catalogo(self):
        """El precio que se cobra desde el reporte (57) es el «dentro de un plan»."""
        from core.rutina_del_mes import PRECIO_EUR
        assert any(p["importe"] == PRECIO_EUR for p in PLAN_CATALOG["rutina_mes"]["precios"])


class TestLaRenovacion:
    def test_el_que_viene_de_un_plan_viejo_elige_entre_los_nuevos(self):
        r = opciones_de_renovacion("reto12en12_gold")
        assert r["puede_seguir_igual"] is False
        assert set(r["opciones"]) == set(NIVELES) | {"elm"}
        assert r["motivo"]

    def test_el_que_ya_esta_en_un_nivel_puede_seguir_igual(self):
        r = opciones_de_renovacion("nivel2")
        assert r["puede_seguir_igual"] is True

    def test_la_salida_es_mantenimiento(self):
        """Doc 19-08: «Mantenimiento es donde aterriza todo el que termina un ciclo y no
        renueva» (antes lo era la Membresía vacía que se borró)."""
        assert opciones_de_renovacion("nivel2")["salida"] == "mantenimiento"

    def test_sin_plan_tambien_se_le_ofrecen_los_nuevos(self):
        r = opciones_de_renovacion(None)
        assert set(r["opciones"]) == set(NIVELES) | {"elm"}

    def test_un_plan_que_no_existe_no_revienta(self):
        r = opciones_de_renovacion("plan_fantasma_2019")
        assert r["puede_seguir_igual"] is False
        assert set(r["opciones"]) == set(NIVELES) | {"elm"}
