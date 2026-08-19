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
    """Lo justo para `puede_ajustarlos`: el historial de macros del cliente.

    Es una LISTA y no un solo apunte desde el 12-08-2026: quién puso los macros lo decide el
    ajuste VIGENTE, y ese se elige por `effective_date` (`macros_por_fecha.ultima_vigente`).
    Antes se pedía con `find_one(sort=[("created_at", -1)])`, que en los 3.446 apuntes que
    vinieron de Calma empatan todos --  se importaron el mismo día -- y devolvía uno al azar
    de toda la historia del cliente.
    """

    def __init__(self, apuntes=None):
        if apuntes is None:
            apuntes = []
        elif isinstance(apuntes, dict):
            apuntes = [apuntes]
        self.macro_history = self._Col(apuntes)

    class _Col:
        def __init__(self, docs):
            self._docs = docs

        async def find_one(self, *a, **kw):
            return self._docs[0] if self._docs else None

        def find(self, *a, **kw):
            return self._Cursor(self._docs)

        class _Cursor:
            def __init__(self, docs):
                self._docs = docs

            async def to_list(self, _n=None):
                return list(self._docs)


HOY = "2026-08-12"
AYER = "2026-08-11"

PUSO_EL_COACH = {"origen": "coach", "changed_by": "Jesus Gallego", "effective_date": HOY}
PUSO_SU_CALCULADORA = {"origen": "coach_calculadora", "changed_by": "Jesus Gallego",
                       "effective_date": HOY}
LO_CALCULO_EL_ALTA = {"origen": "quiz_alta", "changed_by": None, "effective_date": HOY}


# CON MACROS PUESTOS, que es cuando hay algo que proteger.
#
# Desde el 17-08 la primera puerta de `puede_ajustarlos` es «sin macros no hay nada que
# proteger y sí hay alguien atrapado»: al que todavía no tiene ninguno se le deja calcular
# siempre, porque el último paso del alta es justo ese botón. Estos perfiles no traían macros,
# así que salían por esa puerta y los seis tests de la regla daban verde por el motivo
# equivocado -- o rojo, cuando la puerta se puso. Se les ponen unos: lo que se prueba aquí es
# quién puede MOVER unos macros que ya existen.
UNOS_MACROS = {"protein": 190, "carbs": 200, "fat": 60, "calories": 2100}


def perfil(plan="silver", **kw):
    return {"id": "c1", "plan": plan, "status": "activo",
            "macros_training": dict(UNOS_MACROS), **kw}


class TestLaRegla:
    def test_el_personalizado_con_coach_detras_no_puede(self):
        puede, motivo = correr(puede_ajustarlos(FakeDB(PUSO_EL_COACH), perfil()))
        assert puede is False
        # Pedia "tu entrenador". Desde el barrido de voz del 11-08 al cliente se le habla en
        # plural y esa palabra no aparece: "tus macros los llevamos nosotros". Lo que hay que
        # exigir es que el motivo exista y respete la regla, no una redaccion concreta.
        assert motivo.strip(), "sin motivo, el cliente no sabe por que no puede"
        assert "entrenador" not in motivo.lower() and "coach" not in motivo.lower(), motivo

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
        """Tras el 19-08 los `sin_ajuste` que quedan son los complementos (`rutina_mes`,
        `formaciones`...): todo plan cuyo cliente edita sus macros es autogestion.

        OJO: `mantenimiento` y `basica` YA NO lo son (doc 19-08: «edita sus macros: sí»)
        -- el cliente se lleva sus macros el mismo, lo que no hay es revision del equipo.
        Su caso esta abajo."""
        puede, motivo = correr(puede_ajustarlos(FakeDB(None), perfil(plan="formaciones")))
        assert puede is False
        assert "no incluye ajustes" in motivo

    def test_el_de_mantenimiento_se_los_lleva_el(self):
        """Fallo 06 del 19-08: Mantenimiento edita sus macros, sin ajuste del equipo."""
        puede, _ = correr(puede_ajustarlos(FakeDB(None), perfil(plan="mantenimiento")))
        assert puede is True

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
        assert e.value.detail.strip(), "un 403 sin motivo no le dice nada al cliente"
        assert "entrenador" not in e.value.detail.lower() and "coach" not in e.value.detail.lower(), \
            e.value.detail

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


# ---------------------------------------------------------------------------
# EL AJUSTE QUE MANDA ES EL VIGENTE, NO EL DE LA FILA MAS NUEVA (12-08-2026).
#
# En los 3.446 apuntes que vinieron de Calma, `created_at` es el dia en que se importaron
# -- todas el 05-08-2026, muchas en el mismo milisegundo -- y `effective_date` es el dia en
# que el ajuste entro en vigor. Pedir «el ultimo» por `created_at` devolvia uno al azar de
# toda la historia del cliente: medido, a 140 de 185 les salia mal.
#
# Aqui se nota en quien decide si el cliente puede tocarse los macros.
# ---------------------------------------------------------------------------
IMPORTADO = "2026-08-05T01:10:39.707312+00:00"


def _apunte(origen, effective_date, changed_by="Jesus Gallego"):
    return {"origen": origen, "changed_by": changed_by,
            "effective_date": effective_date, "created_at": IMPORTADO}


class TestGanaElVigente:
    def test_manda_el_de_vigencia_mas_reciente(self):
        """Su alta es de 2022 y su ultimo ajuste del coach, de julio: manda el del coach."""
        historial = [_apunte("quiz_alta", "2022-03-06", changed_by=None),
                     _apunte("coach", "2026-07-31")]
        puede, _motivo = correr(puede_ajustarlos(FakeDB(historial), perfil()))
        assert puede is False

    def test_y_al_reves_tambien(self):
        """Si lo ultimo vigente es el calculo del alta, puede tocarselos."""
        historial = [_apunte("coach", "2022-03-06"),
                     _apunte("quiz_alta", "2026-07-31", changed_by=None)]
        puede, _motivo = correr(puede_ajustarlos(FakeDB(historial), perfil()))
        assert puede is True

    def test_un_ajuste_programado_todavia_no_manda(self):
        """Hay ajustes con fecha por delante; los de una cuenta llegan a 2029."""
        historial = [_apunte("quiz_alta", "2026-07-31", changed_by=None),
                     _apunte("coach", "2029-01-08")]
        puede, _motivo = correr(puede_ajustarlos(FakeDB(historial), perfil()))
        assert puede is True
