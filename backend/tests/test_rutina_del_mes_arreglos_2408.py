# -*- coding: utf-8 -*-
"""Los tres arreglos de la verificacion del 24-08: fallos 13, 14 y 15.

  - 13: faltaba el indice de `db.rutina_pdfs` que el codigo prometia en dos comentarios, y
        `tiene_rutina_puesta` barre la coleccion entera en cada carga del cierre del dia.
  - 14: la compra de 57 EUR solo sabia entregar una plantilla ESTRUCTURADA marcada «la del
        mes», y en produccion hay CERO. La entrega real del negocio es un PDF.
  - 15: el cartel «Tu plan no incluye rutina · 57 EUR» delante de un cliente que SI la
        lleva, mientras carga el catalogo de planes (eso se prueba en el navegador, con
        `_guia/_repro_rutina_2408.js`; aqui solo se fija que la pantalla no lo pinte).

Sin backend y sin Mongo: base de mentira, como test_rutina_del_mes_2408.py.
"""
import copy
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import core.database as basedatos                              # noqa: E402
import core.rutina_del_mes as rm                                # noqa: E402
import routes.billing as billing                                # noqa: E402
import routes.routines as rutinas                               # noqa: E402
from core import plan_access                                    # noqa: E402
from fastapi import HTTPException                               # noqa: E402

from conftest import corre  # noqa: E402

RAIZ = os.path.join(os.path.dirname(__file__), "..", "..")


# ── Base de mentira, lo justo ────────────────────────────────────────────────

class _Coleccion:
    def __init__(self, *docs):
        self.docs = [copy.deepcopy(d) for d in docs]
        self.escrituras = []

    async def find_one(self, filtro=None, proyeccion=None, sort=None):
        for d in self.docs:
            if all(d.get(k) == v for k, v in (filtro or {}).items()):
                return copy.deepcopy(d)
        return None

    async def insert_one(self, doc):
        self.docs.append(copy.deepcopy(doc))
        self.escrituras.append(("insert", copy.deepcopy(doc)))

    async def update_one(self, filtro, cambio, **k):
        self.escrituras.append(("update", copy.deepcopy(filtro), copy.deepcopy(cambio)))
        for d in self.docs:
            if all(d.get(k2) == v for k2, v in (filtro or {}).items()):
                d.update(cambio.get("$set") or {})
                break

    async def update_many(self, filtro, cambio, **k):
        self.escrituras.append(("update_many", copy.deepcopy(filtro), copy.deepcopy(cambio)))
        for d in self.docs:
            if all(d.get(k2) == v for k2, v in (filtro or {}).items()):
                d.update(cambio.get("$set") or {})


class _Base:
    def __init__(self, **colecciones):
        for nombre, col in colecciones.items():
            setattr(self, nombre, col)

    def __getattr__(self, nombre):
        col = _Coleccion()
        setattr(self, nombre, col)
        return col


PDF_DEL_MES = {"id": "m1", "mes": "2026-08", "nombre": "La rutina de agosto de 2026",
               "filename": "agosto.pdf", "size": 58, "reparto": ["Empuje", "Tirón"],
               "semanas": 8, "subido_por": "admin-1", "vigente": True,
               "data": b"%PDF-1.4 de mentira"}
PLANTILLA = {"id": "p1", "nombre": "Agosto hombre", "del_mes": True,
             "days": [{"day": "Lunes", "is_rest": False, "exercises": []}]}


@pytest.fixture
def base(monkeypatch):
    """Monta la base y calla el aviso al cliente (tiene su propio test)."""
    def _montar(*, plantillas=(), pdf_del_mes=None, perfiles=({"id": "c1", "user_id": "u1"},)):
        b = _Base(routine_templates=_Coleccion(*plantillas),
                  rutina_mes_pdf=_Coleccion(*([pdf_del_mes] if pdf_del_mes else [])),
                  client_profiles=_Coleccion(*perfiles),
                  rutina_pdfs=_Coleccion(),
                  routines=_Coleccion())
        monkeypatch.setattr(rutinas, "db", b)

        async def _visible():
            return True

        async def _hay_hoy(user_id, tipo):
            return False

        avisados = []

        async def _avisar(user_id):
            avisados.append(user_id)

        monkeypatch.setattr(rutinas, "rutina_visible_para_el_cliente", _visible)
        monkeypatch.setattr(rutinas, "_hay_aviso_de_hoy", _hay_hoy)
        monkeypatch.setattr(rutinas, "avisar_rutina_nueva", _avisar)
        b.avisados = avisados
        return b
    return _montar


# ── FALLO 13: EL INDICE QUE FALTABA ──────────────────────────────────────────

class TestElIndiceDelPdfDeRutina:
    """`db.rutina_pdfs` solo tenia `_id_`. Comprobado con explain contra produccion el
    24-08: COLLSCAN con `totalDocsExamined: 35` para un cliente SIN PDF, y eso se hace en
    cada carga del cierre del dia desde el arreglo del punto 51. Cada fila lleva el PDF
    entero dentro (15,2 MB en 35 documentos)."""

    def _fuente(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "core", "database.py"),
                  encoding="utf-8") as f:
            return f.read()

    def test_el_indice_esta_declarado(self):
        assert '_ensure("rutina_pdfs", [("client_id", 1), ("uploaded_at", -1)])' in self._fuente()

    def test_tambien_el_del_pdf_del_mes(self):
        assert '_ensure("rutina_mes_pdf"' in self._fuente()

    def test_create_indexes_los_crea_de_verdad(self, monkeypatch):
        """Que este escrito no basta: `_ensure` se traga los errores, asi que se comprueba
        que la llamada sale con la clave buena."""
        pedidos = []

        class _Col:
            def __init__(self, nombre):
                self.nombre = nombre

            async def create_index(self, keys, **opts):
                pedidos.append((self.nombre, keys))

        class _Db:
            def __getitem__(self, nombre):
                return _Col(nombre)

        monkeypatch.setattr(basedatos, "db", _Db())
        corre(basedatos.create_indexes())
        assert ("rutina_pdfs", [("client_id", 1), ("uploaded_at", -1)]) in pedidos
        assert ("rutina_mes_pdf", [("vigente", 1), ("uploaded_at", -1)]) in pedidos

    def test_la_consulta_caliente_no_se_trae_el_pdf(self):
        """`tiene_rutina_puesta` pide solo `_id`: 35 binarios de hasta 15 MB no pueden
        viajar por preguntar si tiene rutina. (workout_logs.py es de otro bloque: esto es
        el centinela de que sigue pidiendo lo justo.)"""
        with open(os.path.join(os.path.dirname(__file__), "..", "routes", "workout_logs.py"),
                  encoding="utf-8") as f:
            codigo = f.read()
        trozo = codigo.split("async def tiene_rutina_puesta(")[1].split("\nasync def ")[0]
        assert 'db.rutina_pdfs.find_one({"client_id": client_id}, {"_id": 1})' in trozo

    def test_en_routines_ninguna_consulta_de_lista_pide_el_binario(self):
        """Los `find_one` de `rutina_pdfs` que NO sirven el archivo tienen que excluir
        `data`. Los dos que si lo sirven son los endpoints de ver el PDF."""
        with open(os.path.join(os.path.dirname(__file__), "..", "routes", "routines.py"),
                  encoding="utf-8") as f:
            codigo = f.read()
        # `{"_id": 0}` a secas = se trae el binario. Solo vale en los dos que sirven el PDF.
        traen_todo = re.findall(r'db\.rutina_pdfs\.find_one\([^)]*\{"_id": 0\}[^)]*\)', codigo)
        assert len(traen_todo) == 2, traen_todo


# ── FALLO 14: LO QUE SE COMPRA SE TIENE QUE PODER ENTREGAR ───────────────────

class TestLaCompraEntregaLoQueDeVerdadHay:
    """En produccion: 0 plantillas en `routine_templates`, ninguna marcada «la del mes», y
    35 PDF en `rutina_pdfs` (los 32 de agosto se entregaron asi). O sea que la unica via
    que sabia entregar la compra era la que nunca se usa."""

    def test_sin_nada_preparado_no_hay_que_entregar(self, base):
        base()
        assert corre(rutinas.hay_rutina_del_mes_que_entregar()) is False

    def test_con_el_pdf_del_mes_si_hay(self, base):
        base(pdf_del_mes=PDF_DEL_MES)
        assert corre(rutinas.hay_rutina_del_mes_que_entregar()) is True

    def test_con_una_plantilla_marcada_tambien(self, base):
        base(plantillas=[PLANTILLA])
        assert corre(rutinas.hay_rutina_del_mes_que_entregar()) is True

    def test_el_pdf_retirado_ya_no_cuenta(self, base):
        base(pdf_del_mes={**PDF_DEL_MES, "vigente": False})
        assert corre(rutinas.hay_rutina_del_mes_que_entregar()) is False

    def test_sin_plantilla_se_entrega_el_pdf(self, base):
        """EL ARREGLO: antes esto devolvia None y el cliente se quedaba sin nada."""
        b = base(pdf_del_mes=PDF_DEL_MES)
        assert corre(rutinas.entregar_la_rutina_del_mes("c1")) == "La rutina de agosto de 2026"
        suyo = b.rutina_pdfs.docs[0]
        assert suyo["client_id"] == "c1" and suyo["filename"] == "agosto.pdf"
        # Se COPIA el binario: el mes que viene se sube otro y al de agosto no se le cambia
        # la rutina debajo.
        assert bytes(suyo["data"]) == PDF_DEL_MES["data"]
        # Y viajan el reparto y las semanas, que es lo que pinta la tira de la semana.
        assert suyo["reparto"] == ["Empuje", "Tirón"] and suyo["semanas"] == 8

    def test_al_entregar_el_pdf_le_suena_el_aviso(self, base):
        b = base(pdf_del_mes=PDF_DEL_MES)
        corre(rutinas.entregar_la_rutina_del_mes("c1"))
        assert b.avisados == ["u1"]

    def test_la_plantilla_manda_sobre_el_pdf(self, base):
        """Si el equipo marca una plantilla, se entrega esa: es mejor producto (el cliente
        puede marcar series y pesos) y el PDF es el plan B."""
        b = base(plantillas=[PLANTILLA], pdf_del_mes=PDF_DEL_MES)
        assert corre(rutinas.entregar_la_rutina_del_mes("c1")) == "Agosto hombre"
        assert b.rutina_pdfs.docs == [] and len(b.routines.docs) == 1

    def test_sin_nada_preparado_sigue_devolviendo_none(self, base):
        b = base()
        assert corre(rutinas.entregar_la_rutina_del_mes("c1")) is None
        assert b.rutina_pdfs.docs == [] and b.routines.docs == []

    def test_a_un_cliente_que_ya_no_esta_no_se_le_entrega_nada(self, base):
        b = base(pdf_del_mes=PDF_DEL_MES, perfiles=())
        assert corre(rutinas.entregar_la_rutina_del_mes("c1")) is None
        assert b.rutina_pdfs.docs == []

    def test_solo_una_vigente_a_la_vez(self, base):
        """Dos PDF del mes marcados y «la del mes» deja de significar algo."""
        b = base(pdf_del_mes=PDF_DEL_MES)
        corre(rutinas._guardar_el_pdf_del_mes(b"otro", "septiembre.pdf", "admin-1", "2026-09"))
        vigentes = [d for d in b.rutina_mes_pdf.docs if d.get("vigente")]
        assert len(vigentes) == 1 and vigentes[0]["mes"] == "2026-09"

    def test_el_mes_se_lee_bonito(self):
        assert rutinas._nombre_del_mes("2026-08") == "La rutina de agosto de 2026"
        assert rutinas._nombre_del_mes("cualquier-cosa") == "La rutina del mes"

    def test_el_mes_sin_decirlo_es_el_de_hoy(self):
        assert re.fullmatch(r"\d{4}-\d{2}", rutinas._mes_limpio(None))
        assert rutinas._mes_limpio("2026-09") == "2026-09"
        assert rutinas._mes_limpio("septiembre") != "septiembre"


class TestNoSeCobraLoQueNoSePuedeEntregar:
    """«Hasta que haya algo que entregar, el boton no puede cobrar a ciegas.»"""

    CATALOGO = {"plan_sin_rutina": {"habilitaciones": {"rutina": "opcional"}}}
    PERFIL = {"id": "c1", "user_id": "u1", "name": "Marta", "plan": "plan_sin_rutina"}
    USUARIO = {"id": "u1", "email": "marta@ejemplo.com"}

    @pytest.fixture
    def montado(self, monkeypatch):
        def _montar(*, pdf_del_mes=None, plantillas=()):
            b = _Base(client_profiles=_Coleccion(dict(self.PERFIL)),
                      routines=_Coleccion(),
                      routine_templates=_Coleccion(*plantillas),
                      rutina_mes_pdf=_Coleccion(*([pdf_del_mes] if pdf_del_mes else [])),
                      reports=_Coleccion())
            monkeypatch.setattr(billing, "db", b)
            monkeypatch.setattr(rutinas, "db", b)

            async def _catalogo():
                return self.CATALOGO

            monkeypatch.setattr(plan_access, "catalogo_vivo", _catalogo)

            async def _no_llegues_a_stripe(*a, **k):
                raise AssertionError("no se puede llamar a Stripe sin nada que entregar")

            monkeypatch.setattr(billing, "get_stripe_module", _no_llegues_a_stripe)
            return b
        return _montar

    def test_la_puerta_de_stripe_se_cierra(self, montado):
        montado()
        with pytest.raises(HTTPException) as e:
            corre(billing.comprar_la_rutina_del_mes({"modalidad": "basica"},
                                                    user=dict(self.USUARIO)))
        assert e.value.status_code == 409
        assert "todavía no está lista" in e.value.detail

    def test_la_puerta_de_la_tarjeta_guardada_tambien(self, montado, monkeypatch):
        montado()

        async def _no_cobres(*a, **k):
            raise AssertionError("no se puede cobrar sin nada que entregar")

        monkeypatch.setattr(rm, "cobrar", _no_cobres)
        with pytest.raises(HTTPException) as e:
            corre(rutinas.quiero_la_rutina({"modalidad": "basica"}, user=dict(self.USUARIO)))
        assert e.value.status_code == 409

    def test_con_el_pdf_del_mes_la_compra_se_abre(self, montado, monkeypatch):
        """Que el candado no se coma las ventas buenas: con algo preparado, se sigue."""
        montado(pdf_del_mes=PDF_DEL_MES)
        llegado = {}

        def _stripe():
            llegado["si"] = True
            raise RuntimeError("hasta aquí: lo que se comprueba es que se ha llegado")

        monkeypatch.setattr(billing, "get_stripe_module", _stripe)
        with pytest.raises(RuntimeError):
            corre(billing.comprar_la_rutina_del_mes({"modalidad": "basica"},
                                                    user=dict(self.USUARIO)))
        assert llegado.get("si") is True

    def test_una_cuenta_de_pruebas_si_puede_probar_el_circuito(self, montado, monkeypatch):
        """El candado es de DINERO y va despues del freno de las cuentas de laboratorio: la
        de pruebas no cobra nunca, y ya se le dice que no se le ha puesto ninguna rutina."""
        montado()
        salida = corre(billing.comprar_la_rutina_del_mes(
            {"modalidad": "basica"}, user={**self.USUARIO, "es_pruebas": True}))
        assert salida["sin_pago"] is True and salida["rutina_puesta"] is None
        assert "no se te ha puesto ninguna" in salida["mensaje"]


# ── FALLO 15: EL CARTEL EQUIVOCADO MIENTRAS CARGA ────────────────────────────

class TestLaPantallaNoOfreceALoCiegas:
    """La prueba de verdad es el navegador (`_guia/_repro_rutina_2408.js`, que reproduce el
    fallo retrasando /api/plans y comprueba que ya no sale la oferta). Esto son los
    centinelas de que la pantalla no vuelve a decidir con `myPlan` a medio cargar."""

    def _pantalla(self):
        with open(os.path.join(RAIZ, "frontend", "src", "pages", "RoutinePage.jsx"),
                  encoding="utf-8") as f:
            return f.read()

    def test_rutina_incluida_es_de_tres_estados(self):
        codigo = self._pantalla()
        assert "const planPorSaber = cargandoSesion || !Object.keys(planCatalog || {}).length;" in codigo
        assert "const rutinaIncluida = planPorSaber ? null :" in codigo

    def test_mientras_no_se_sabe_hay_esqueleto_y_no_oferta(self):
        codigo = self._pantalla()
        assert 'data-testid="rutina-plan-cargando"' in codigo
        # El esqueleto se pinta ANTES que el «Sin rutina asignada» y que la oferta.
        assert codigo.index('rutinaIncluida === null && !planTardaDemasiado') < \
               codigo.index('data-testid="quiero-mi-rutina"')

    def test_la_peticion_solo_se_pide_cuando_se_sabe_que_no_la_lleva(self):
        assert "if (rutinaIncluida !== false) return;" in self._pantalla()

    def test_la_oferta_espera_a_saber_si_hay_rutina_del_mes(self):
        codigo = self._pantalla()
        assert "/routines/rutina-del-mes/disponible" in codigo
        assert 'data-testid="rutina-del-mes-no-lista"' in codigo


def test_la_ruta_de_disponibilidad_existe():
    """La que pregunta la pantalla antes de enseñar el botón de 57 €."""
    assert "/routines/rutina-del-mes/disponible" in {r.path for r in rutinas.router.routes}


def test_las_rutas_del_pdf_del_mes_existen():
    caminos = {r.path for r in rutinas.admin_router.routes}
    assert "/admin/routines/pdf-del-mes" in caminos
    assert "/admin/routines/pdf-del-mes/info" in caminos
