# -*- coding: utf-8 -*-
"""
Punto 4.10: en un plan con entrenador, el cliente no se machaca sus propios macros.

La primera vuelta cerro los dos caminos por los que el cliente viene A PROPOSITO a tocarselos.
Estos tests son de la segunda, que es la que importa: los CUATRO caminos por los que se los
reescribia de rebote, haciendo otra cosa.

    PUT  /clients/profile           cambia su peso            -> recalculaba
    POST /clients/questionnaire     rellena el alta           -> recalculaba
    POST /clients/mi-cuerpo         vuelve a «Mi cuerpo»      -> recalculaba
    POST /calculator/targets/apply  aplica unos macros        -> recalculaba SIN MIRAR NADA

Los tres primeros se guardaban con `macros_source != "manual"` y eso no es el mismo cerrojo:
la calculadora del panel del coach deja "auto". El cuarto no miraba ni eso.

Medido en produccion el 09-08 sobre 184 perfiles activos: 180 de plan personalizado, 176 con
macros_source "manual" y 4 con "auto". Por el cuarto camino estaban expuestos los 180.
"""
import asyncio

import pytest

from core.macros_de_quien import de_una_persona
from core.quien_pone_los_macros import exigir_que_pueda, puede_ajustarlos


def correr(coro):
    """No hay pytest-asyncio en el repo: se corre a mano, como en el resto de tests."""
    return asyncio.run(coro)


class FakeDB:
    """Lo justo para `puede_ajustarlos`: un `macro_history.find_one` que devuelve el apunte."""

    def __init__(self, ultimo_apunte=None):
        self.macro_history = self._Col(ultimo_apunte)

    class _Col:
        def __init__(self, doc):
            self._doc = doc

        async def find_one(self, *a, **kw):
            return self._doc


PUSO_EL_COACH = {"origen": "coach", "changed_by": "Jesus Gallego"}
PUSO_SU_CALCULADORA = {"origen": "coach_calculadora", "changed_by": "Jesus Gallego"}
LO_CALCULO_EL_ALTA = {"origen": "quiz_alta", "changed_by": None}


def perfil(plan="silver", **kw):
    return {"id": "c1", "plan": plan, "status": "activo", **kw}


class TestLaRegla:
    def test_el_personalizado_con_coach_detras_no_puede(self):
        puede, motivo = correr(puede_ajustarlos(FakeDB(PUSO_EL_COACH), perfil()))
        assert puede is False
        assert "tu entrenador" in motivo

    def test_tampoco_si_se_los_puso_desde_su_calculadora(self):
        """El agujero de la segunda vuelta: por ahi `macros_source` se queda en "auto"."""
        puede, _ = correr(puede_ajustarlos(FakeDB(PUSO_SU_CALCULADORA), perfil()))
        assert puede is False

    def test_el_personalizado_recien_dado_de_alta_SI_puede(self):
        """Son sus macros de arranque. Cerrarle la calculadora le dejaria sin numeros."""
        puede, motivo = correr(puede_ajustarlos(FakeDB(LO_CALCULO_EL_ALTA), perfil()))
        assert puede is True and motivo is None

    def test_el_que_no_tiene_ni_historial_puede(self):
        puede, _ = correr(puede_ajustarlos(FakeDB(None), perfil()))
        assert puede is True

    def test_el_plan_sin_ajuste_no_ajusta_nunca(self):
        """`mantenimiento`, `rutina_mes` y `formaciones` son los `sin_ajuste` del catalogo.
        Ojo: `membresia` NO lo es -- es `autogestion` -- por mucho que sea la de salida."""
        puede, motivo = correr(puede_ajustarlos(FakeDB(None), perfil(plan="mantenimiento")))
        assert puede is False
        assert "no incluye ajustes" in motivo

    def test_y_el_de_autogestion_se_los_lleva_el(self):
        """Aunque se los haya puesto alguien: en ese plan los ajusta el cliente."""
        puede, _ = correr(puede_ajustarlos(FakeDB(PUSO_EL_COACH), perfil(plan="nivel1")))
        assert puede is True

    def test_un_plan_desconocido_no_deja_ajustar(self):
        """`modo_calculadora` devuelve 'sin_ajuste' por defecto: mejor cerrado que abierto."""
        puede, _ = correr(puede_ajustarlos(FakeDB(None), perfil(plan="lo-que-sea")))
        assert puede is False


class TestElCerrojoConMotivo:
    def test_exigir_que_pueda_levanta_403_con_el_motivo(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as e:
            correr(exigir_que_pueda(FakeDB(PUSO_EL_COACH), perfil()))
        assert e.value.status_code == 403
        assert "tu entrenador" in e.value.detail

    def test_y_deja_pasar_al_que_puede(self):
        correr(exigir_que_pueda(FakeDB(LO_CALCULO_EL_ALTA), perfil()))  # no levanta


class TestMacrosSourceNoValiaDeCerrojo:
    """El porque de la segunda vuelta, escrito como prueba.

    `macros_source` describe COMO se calcularon los macros; `de_una_persona` responde QUIEN
    los decidio. No son la misma pregunta, y usar la primera para contestar la segunda es lo
    que dejaba abiertos a los clientes ajustados desde la calculadora del panel.
    """

    def test_el_ajuste_del_coach_por_calculadora_es_de_una_persona(self):
        assert de_una_persona(PUSO_SU_CALCULADORA) is True

    def test_pero_ese_camino_deja_macros_source_en_auto(self):
        """Comprobado sobre el codigo, para que se entere el test si alguien lo cambia."""
        import pathlib
        import re

        admin = pathlib.Path(__file__).resolve().parents[1] / "routes" / "admin.py"
        texto = admin.read_text(encoding="utf-8")
        bloque = texto[texto.index("async def admin_calculator_apply"):]
        bloque = bloque[:bloque.index("macro_log")]
        assert re.search(r'"macros_source":\s*"auto"', bloque), (
            "si este camino pasa a escribir 'manual', revisa si el cerrojo del 4.10 sigue "
            "haciendo falta en los caminos de rebote")


class TestLosCuatroCaminosLoMiran:
    """Que ninguno se quede sin cerrojo por un refactor. Se comprueba sobre el codigo porque
    montar los cuatro endpoints con su Mongo cuesta mas de lo que aporta."""

    def _fuente(self, ruta):
        import pathlib
        return (pathlib.Path(__file__).resolve().parents[1] / ruta).read_text(encoding="utf-8")

    def _cuerpo(self, texto, nombre_funcion):
        i = texto.index("async def " + nombre_funcion)
        j = texto.find("\n@router.", i)
        return texto[i:j if j > 0 else len(texto)]

    @pytest.mark.parametrize("ruta,funcion", [
        ("routes/users.py", "update_client_profile"),
        ("routes/users.py", "submit_questionnaire"),
        ("routes/users.py", "calcular_mi_cuerpo"),
        ("routes/users.py", "ajustar_macros"),
    ])
    def test_los_de_users_preguntan(self, ruta, funcion):
        cuerpo = self._cuerpo(self._fuente(ruta), funcion)
        assert "puede_ajustarlos" in cuerpo, f"{funcion} no mira quien pone los macros"

    def test_la_calculadora_del_cliente_pregunta(self):
        cuerpo = self._cuerpo(self._fuente("routes/calculator.py"), "calculate_and_apply_targets")
        assert "exigir_que_pueda" in cuerpo

    def test_y_el_guardado_manual_tambien(self):
        texto = self._fuente("routes/users.py")
        i = texto.index('@router.put("/macros"')
        assert "puede_ajustarlos" in texto[i:i + 4000]
