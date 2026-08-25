# -*- coding: utf-8 -*-
"""La rutina del mes del 24-08: comprarla, recibirla y entregarla a varios de golpe.

Los tres encargos de Jesus de esa noche, por dentro:

  - «que se compre directamente desde la app» -> el checkout de Stripe y sus candados,
  - «despues de pagar tiene que recibirla»    -> la rutina del mes vigente y su entrega,
  - «la personalizada se le da una personalizada, debemos agregar eso» -> el PDF en bloque.

Sin backend y sin Mongo: todo lo que toca base va con una base de mentira, igual que
test_cierre_entreno_2408.py. Lo que hace falta probar con el servidor vivo (que el panel
cuente bien y que las tres vias de subir rutina funcionen) se probo a mano contra la app.
"""
import copy
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import core.rutina_del_mes as rm                                 # noqa: E402
import routes.routines as rutinas                                # noqa: E402

# El bucle es el de la bateria entera (tests/conftest.py): ver ahi por que.
from conftest import corre  # noqa: E402


# ── Una base de mentira, lo justo ────────────────────────────────────────────

# LA BASE DE MENTIRA HABLA EL MONGO QUE SE USA, y hay que ampliarla cuando el codigo
# estrena dialecto. Paso el 24-08 por la tarde: el candado de la doble entrega se reescribio
# para resolverse DENTRO de Mongo (`{"id": ..., "rutina_mes_pedida.session_id": {"$ne": ...}}`
# y luego un `$set` de `rutina_mes_pedida.rutina_puesta`), y esta clase solo sabia comparar
# claves llanas con `==`. Resultado: seis tests en rojo con `KeyError: rutina_mes_pedida` --
# el documento no casaba con el filtro, asi que no se escribia nada -- que no denunciaban
# ningun fallo del codigo, solo que el doble no sabia el idioma nuevo. Ahora entiende:
#
#   - RUTAS CON PUNTO, en el filtro y en el `$set`/`$unset` (`a.b.c`),
#   - los dos operadores que se usan aqui, `$ne` y `$in`,
#   - y `update_one` devuelve `matched_count`/`modified_count`, que es de lo que cuelga el
#     «esta compra ya estaba apuntada» y sin lo cual el freno no se puede probar.

def _por_la_ruta(doc, ruta):
    """El valor de `a.b.c` dentro del documento, o None si por el camino no hay nada."""
    actual = doc
    for tramo in str(ruta).split("."):
        if not isinstance(actual, dict):
            return None
        actual = actual.get(tramo)
    return actual


def _casa(doc, filtro):
    """Si el documento cumple el filtro. Solo lo que se usa en estas pruebas."""
    for clave, esperado in (filtro or {}).items():
        valor = _por_la_ruta(doc, clave)
        if isinstance(esperado, dict):
            if "$ne" in esperado and valor == esperado["$ne"]:
                return False
            if "$in" in esperado and valor not in esperado["$in"]:
                return False
            continue
        if valor != esperado:
            return False
    return True


def _escribe_por_la_ruta(doc, ruta, valor):
    actual = doc
    tramos = str(ruta).split(".")
    for tramo in tramos[:-1]:
        actual = actual.setdefault(tramo, {})
    actual[tramos[-1]] = valor


def _borra_por_la_ruta(doc, ruta):
    actual = doc
    tramos = str(ruta).split(".")
    for tramo in tramos[:-1]:
        actual = actual.get(tramo)
        if not isinstance(actual, dict):
            return
    actual.pop(tramos[-1], None)


class _Escrito:
    """Lo que devuelve un update de Mongo, con lo unico que se le pregunta."""

    def __init__(self, matched, modified):
        self.matched_count = matched
        self.modified_count = modified


class _Coleccion:
    def __init__(self, *docs):
        self.docs = [copy.deepcopy(d) for d in docs]
        self.escrituras = []          # cada update_one/insert_one que ha entrado

    async def find_one(self, filtro=None, proyeccion=None, sort=None):
        for d in self.docs:
            if _casa(d, filtro):
                return copy.deepcopy(d)
        return None

    async def insert_one(self, doc):
        self.docs.append(copy.deepcopy(doc))
        self.escrituras.append(("insert", copy.deepcopy(doc)))

    async def update_one(self, filtro, cambio, **k):
        self.escrituras.append(("update", copy.deepcopy(filtro), copy.deepcopy(cambio)))
        for d in self.docs:
            if _casa(d, filtro):
                antes = copy.deepcopy(d)
                for ruta, valor in (cambio.get("$set") or {}).items():
                    _escribe_por_la_ruta(d, ruta, valor)
                for ruta in (cambio.get("$unset") or {}):
                    _borra_por_la_ruta(d, ruta)
                # `$addToSet` de verdad: el que ya esta no vuelve a entrar y el update sale
                # con `modified_count: 0`. Es EL candado de la doble entrega del pago, asi
                # que el doble tiene que saber hacerlo o el test lo estaria dando por bueno
                # sin probarlo (el codigo, al no recibir nada, se cae al «1» por defecto).
                for ruta, valor in (cambio.get("$addToSet") or {}).items():
                    lista = list(_por_la_ruta(d, ruta) or [])
                    if valor not in lista:
                        lista.append(valor)
                        _escribe_por_la_ruta(d, ruta, lista)
                return _Escrito(1, 0 if d == antes else 1)
        return _Escrito(0, 0)

    async def update_many(self, filtro, cambio, **k):
        self.escrituras.append(("update_many", copy.deepcopy(filtro), copy.deepcopy(cambio)))
        return _Escrito(0, 0)

    def find(self, filtro=None, proyeccion=None):
        return _Cursor(copy.deepcopy([d for d in self.docs if _casa(d, filtro)]))


class _Cursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, *a, **k):
        return self

    async def to_list(self, cuantos=None):
        return self.docs


class _Base:
    def __init__(self, **colecciones):
        for nombre, col in colecciones.items():
            setattr(self, nombre, col)

    def __getattr__(self, nombre):
        col = _Coleccion()
        setattr(self, nombre, col)
        return col


# ── EL PRECIO ────────────────────────────────────────────────────────────────

def test_la_rutina_del_mes_cuesta_57():
    """Jesus, 24-08: «la rutina del mes cuesta 57 EUR, en todos los sitios donde se diga».
    Lo que se COBRA sale de aqui, asi que aqui es donde no se puede mover."""
    assert rm.PRECIO_EUR == 57.0
    assert rm.importe_centimos() == 5700


# ── A QUIEN SE LE OFRECE ─────────────────────────────────────────────────────

class TestAQuienSeLeVende:
    """«El que ya la tiene incluida en su plan NO ve la oferta». Y «opcional» no es
    incluida: opcional quiere decir justo que se la puede comprar."""

    def _catalogo(self, monkeypatch, modo):
        async def _cat():
            return {"gold": {"habilitaciones": {"rutina": modo}}}
        monkeypatch.setattr("core.plan_access.catalogo_vivo", _cat)

    @pytest.mark.parametrize("modo", ["del_mes", "personalizada"])
    def test_al_que_la_lleva_no_se_le_vende(self, monkeypatch, modo):
        self._catalogo(monkeypatch, modo)
        assert corre(rm.su_plan_ya_la_lleva("gold")) is True

    @pytest.mark.parametrize("modo", ["ninguna", "opcional", None, ""])
    def test_al_que_no_la_lleva_si(self, monkeypatch, modo):
        self._catalogo(monkeypatch, modo)
        assert corre(rm.su_plan_ya_la_lleva("gold")) is False

    def test_un_plan_que_no_esta_en_el_catalogo_no_bloquea_la_compra(self, monkeypatch):
        self._catalogo(monkeypatch, "del_mes")
        assert corre(rm.su_plan_ya_la_lleva("un_plan_raro")) is False


# ── YA HA PAGADO: QUE LA RECIBA ──────────────────────────────────────────────

class TestLoQuePasaAlPagar:
    """Antes de esto, pagar la rutina del mes solo dejaba un aviso en el panel para que
    alguien se la mandara a mano, y por eso hay clientes que la pagaron y no la tienen."""

    PERFIL = {"id": "c1", "name": "Marta", "user_id": "u1"}

    def _montar(self, monkeypatch, *, entrega="Rutina de agosto"):
        base = _Base(client_profiles=_Coleccion({"id": "c1"}))
        avisos = []

        async def _avisar(db, **kw):
            avisos.append(kw)

        async def _entregar(client_id, origen="compra"):
            return entrega

        monkeypatch.setattr("core.database.db", base)
        monkeypatch.setattr("core.avisos_equipo.avisar_al_equipo", _avisar)
        monkeypatch.setattr(rutinas, "entregar_la_rutina_del_mes", _entregar)
        return base, avisos

    def test_se_apunta_en_su_ficha_y_se_le_entrega(self, monkeypatch):
        base, avisos = self._montar(monkeypatch)
        assert corre(rm.activar_tras_pago(self.PERFIL, 57.0, "avanzada", session_id="cs_1")) is True

        pedida = base.client_profiles.docs[0]["rutina_mes_pedida"]
        assert pedida["cobrado"] is True and pedida["modalidad"] == "avanzada"
        assert pedida["session_id"] == "cs_1"
        assert pedida["rutina_puesta"] == "Rutina de agosto"
        assert avisos and "Rutina de agosto" in avisos[0]["mensaje"]

    def test_se_le_quita_el_aplazamiento(self, monkeypatch):
        """El que dijo «preguntame en una semana» y luego la compro seguia recibiendo el
        recordatorio «¿Te preparamos la rutina del mes?»."""
        base, _ = self._montar(monkeypatch)
        corre(rm.activar_tras_pago(self.PERFIL, 57.0, "basica", session_id="cs_2"))
        _, filtro, cambio = base.client_profiles.escrituras[-1]
        assert cambio["$unset"] == {"rutina_mes_aplazada_hasta": ""}

    def test_el_webhook_y_la_vuelta_del_pago_no_la_entregan_dos_veces(self, monkeypatch):
        """Llegan LOS DOS: Stripe avisa por su lado y el navegador sincroniza al volver.
        Sin este freno, la segunda vuelta le pone la rutina otra vez y le suena otro aviso."""
        base, avisos = self._montar(monkeypatch)
        corre(rm.activar_tras_pago(self.PERFIL, 57.0, "basica", session_id="cs_3"))
        perfil_ya = base.client_profiles.docs[0]
        assert corre(rm.activar_tras_pago(perfil_ya, 57.0, "basica", session_id="cs_3")) is False
        assert len(avisos) == 1

    def test_sin_ninguna_rutina_marcada_se_dice_que_va_a_mano(self, monkeypatch):
        """El equipo tiene que enterarse de que ese cliente ha pagado y NO tiene nada
        puesto: es la unica forma de que no se quede esperando."""
        base, avisos = self._montar(monkeypatch, entrega=None)
        corre(rm.activar_tras_pago(self.PERFIL, 57.0, "basica", session_id="cs_4"))
        assert base.client_profiles.docs[0]["rutina_mes_pedida"]["rutina_puesta"] is None
        assert "a mano" in avisos[0]["mensaje"]

    def test_una_entrega_que_revienta_no_tira_un_pago_ya_cobrado(self, monkeypatch):
        base, avisos = self._montar(monkeypatch)

        async def _revienta(client_id, origen="compra"):
            raise RuntimeError("la biblioteca no contesta")

        monkeypatch.setattr(rutinas, "entregar_la_rutina_del_mes", _revienta)
        assert corre(rm.activar_tras_pago(self.PERFIL, 57.0, "basica", session_id="cs_5")) is True
        assert base.client_profiles.docs[0]["rutina_mes_pedida"]["cobrado"] is True

    def test_una_modalidad_rara_no_se_guarda(self, monkeypatch):
        base, _ = self._montar(monkeypatch)
        corre(rm.activar_tras_pago(self.PERFIL, 57.0, "vip", session_id="cs_6"))
        assert base.client_profiles.docs[0]["rutina_mes_pedida"]["modalidad"] == "basica"


# ── CUAL ES LA RUTINA DEL MES ────────────────────────────────────────────────

class TestLaRutinaDelMesVigente:
    """El concepto que faltaba: en la base no habia forma de preguntar cual es la de este
    mes, asi que no habia nada que entregarle al que la comprara."""

    UNA = {"id": "p1", "nombre": "Agosto hombre", "days": [
        {"day": "Lunes", "is_rest": False, "exercises": [
            {"name": "Press banca", "sets": 4, "reps": "8-10", "rest": "90s"}]},
    ]}

    def _montar(self, monkeypatch, *plantillas, perfil=True):
        base = _Base(
            routine_templates=_Coleccion(*plantillas),
            client_profiles=_Coleccion(*([{"id": "c1", "user_id": "u1"}] if perfil else [])),
            routines=_Coleccion(),
        )
        monkeypatch.setattr(rutinas, "db", base)

        async def _visible():
            return False          # el aviso al cliente tiene su propio test

        monkeypatch.setattr(rutinas, "rutina_visible_para_el_cliente", _visible)
        return base

    def test_sin_ninguna_marcada_no_hay_del_mes(self, monkeypatch):
        self._montar(monkeypatch, self.UNA)
        assert corre(rutinas.rutina_del_mes_vigente()) is None
        assert corre(rutinas.entregar_la_rutina_del_mes("c1")) is None

    def test_la_marcada_es_la_que_se_entrega(self, monkeypatch):
        base = self._montar(monkeypatch, {**self.UNA, "del_mes": True})
        assert corre(rutinas.entregar_la_rutina_del_mes("c1")) == "Agosto hombre"
        puesta = base.routines.docs[0]
        assert puesta["client_id"] == "c1" and puesta["status"] == "active"
        assert puesta["plantilla_id"] == "p1" and puesta["origen"] == "compra"
        # Se COPIA, no se enlaza: el dia que se le cambie un ejercicio no se le toca la
        # rutina a los otros veinte que la tienen puesta.
        assert puesta["days"][0]["exercises"][0]["name"] == "Press banca"

    def test_la_anterior_se_queda_inactiva(self, monkeypatch):
        base = self._montar(monkeypatch, {**self.UNA, "del_mes": True})
        corre(rutinas.entregar_la_rutina_del_mes("c1"))
        assert any(e[0] == "update_many" and e[2]["$set"] == {"status": "inactive"}
                   for e in base.routines.escrituras)

    def test_a_un_cliente_que_ya_no_esta_no_se_le_entrega_nada(self, monkeypatch):
        base = self._montar(monkeypatch, {**self.UNA, "del_mes": True}, perfil=False)
        assert corre(rutinas.entregar_la_rutina_del_mes("c1")) is None
        assert base.routines.docs == []

    def test_marcarla_desmarca_a_las_demas(self, monkeypatch):
        """Con dos marcadas, «la del mes» dejaria de significar algo."""
        base = self._montar(monkeypatch, self.UNA)
        r = corre(rutinas.marcar_la_rutina_del_mes("p1", {"del_mes": True}, user={"id": "a"}))
        assert r == {"del_mes": True, "nombre": "Agosto hombre"}
        assert any(e[0] == "update_many" and e[1] == {"id": {"$ne": "p1"}}
                   for e in base.routine_templates.escrituras)

    def test_desmarcarla_no_toca_a_las_demas(self, monkeypatch):
        base = self._montar(monkeypatch, {**self.UNA, "del_mes": True})
        r = corre(rutinas.marcar_la_rutina_del_mes("p1", {"del_mes": False}, user={"id": "a"}))
        assert r["del_mes"] is False
        assert not any(e[0] == "update_many" for e in base.routine_templates.escrituras)


# ── EL PDF A VARIOS DE GOLPE ─────────────────────────────────────────────────

class _ArchivoDeMentira:
    """Un UploadFile con la trampa de verdad: `read()` solo devuelve el contenido UNA vez.

    Es exactamente lo que rompia la subida en bloque si se leyera dentro del bucle: el
    primer cliente recibia la rutina y los otros cincuenta un PDF vacio."""

    def __init__(self, contenido=b"%PDF-1.4 rutina", filename="rutina.pdf",
                 content_type="application/pdf"):
        self._contenido = contenido
        self._leido = False
        self.filename = filename
        self.content_type = content_type

    async def read(self):
        if self._leido:
            return b""
        self._leido = True
        return self._contenido


class TestSubirElPdfAVarios:
    """«La personalizada se le da una personalizada, debemos agregar eso» (Jesus, 24-08).
    En produccion hay 59 clientes con plan de rutina personalizada y 58 sin ninguna."""

    def _montar(self, monkeypatch, *clientes):
        base = _Base(
            client_profiles=_Coleccion(*[{"id": c, "user_id": "u" + c} for c in clientes]),
            rutina_pdfs=_Coleccion(),
        )
        monkeypatch.setattr(rutinas, "db", base)
        avisados = []

        async def _visible():
            return True

        async def _hay_hoy(user_id, tipo):
            return False

        async def _avisar(user_id):
            avisados.append(user_id)

        monkeypatch.setattr(rutinas, "rutina_visible_para_el_cliente", _visible)
        monkeypatch.setattr(rutinas, "_hay_aviso_de_hoy", _hay_hoy)
        monkeypatch.setattr(rutinas, "avisar_rutina_nueva", _avisar)
        return base, avisados

    def _subir(self, clientes, archivo=None, **kw):
        return corre(rutinas.subir_pdf_de_rutina_a_varios(
            file=archivo or _ArchivoDeMentira(), clientes=clientes,
            user={"id": "admin-1"}, **kw))

    def test_todos_reciben_el_PDF_entero(self, monkeypatch):
        base, _ = self._montar(monkeypatch, "c1", "c2", "c3")
        r = self._subir("c1,c2,c3")
        assert r["subidas"] == 3
        # El fallo que esto evita: el segundo y el tercero con un PDF de 0 bytes.
        assert [d["size"] for d in base.rutina_pdfs.docs] == [15, 15, 15]
        assert {d["client_id"] for d in base.rutina_pdfs.docs} == {"c1", "c2", "c3"}

    def test_a_cada_uno_le_suena_su_aviso(self, monkeypatch):
        _, avisados = self._montar(monkeypatch, "c1", "c2")
        self._subir("c1,c2")
        assert avisados == ["uc1", "uc2"]

    def test_el_reparto_y_las_semanas_van_a_todos(self, monkeypatch):
        base, _ = self._montar(monkeypatch, "c1", "c2")
        self._subir("c1,c2", reparto="Empuje, Tirón, Pierna", semanas="4")
        for d in base.rutina_pdfs.docs:
            assert d["reparto"] == ["Empuje", "Tirón", "Pierna"] and d["semanas"] == 4

    def test_el_mismo_cliente_dos_veces_es_una_sola_entrega(self, monkeypatch):
        base, _ = self._montar(monkeypatch, "c1")
        r = self._subir("c1, c1 ,c1")
        assert r["subidas"] == 1 and len(base.rutina_pdfs.docs) == 1

    def test_uno_que_ya_no_esta_no_tumba_la_entrega_de_los_demas(self, monkeypatch):
        base, _ = self._montar(monkeypatch, "c1", "c2")
        r = self._subir("c1,fantasma,c2")
        assert r["subidas"] == 2 and r["sin_perfil"] == ["fantasma"]
        assert len(base.rutina_pdfs.docs) == 2

    def test_sin_nadie_elegido_no_se_sube_nada(self, monkeypatch):
        self._montar(monkeypatch, "c1")
        with pytest.raises(Exception) as e:
            self._subir("  ,  ")
        assert e.value.status_code == 400

    def test_un_archivo_que_no_es_pdf_se_rechaza(self, monkeypatch):
        self._montar(monkeypatch, "c1")
        with pytest.raises(Exception) as e:
            self._subir("c1", archivo=_ArchivoDeMentira(filename="rutina.docx",
                                                        content_type="application/msword"))
        assert e.value.status_code == 400

    def test_no_se_le_manda_a_media_España_de_una_vez(self, monkeypatch):
        self._montar(monkeypatch, "c1")
        with pytest.raises(Exception) as e:
            self._subir(",".join(str(n) for n in range(rutinas.MAX_CLIENTES_EN_BLOQUE + 1)))
        assert e.value.status_code == 400


# ── QUE LE TOCA HOY AL QUE TIENE PDF (punto 69) ──────────────────────────────

class TestQueLeTocaHoyConElPdf:
    """El cabo del punto 69: `GET /workout-logs/hoy` no cuenta el PDF porque «del PDF no
    sale que dias entrena». Si sale, cuando tiene reparto y el cliente tiene sus dias."""

    PERFIL = {"id": "c1", "training_weekdays": ["lunes", "miercoles", "viernes"]}

    def _montar(self, monkeypatch, reparto):
        docs = [{"client_id": "c1", "reparto": reparto}] if reparto is not None else []
        monkeypatch.setattr(rutinas, "db", _Base(rutina_pdfs=_Coleccion(*docs)))

    def test_el_dia_que_entrena_dice_que_grupo(self, monkeypatch):
        self._montar(monkeypatch, ["Empuje", "Tirón", "Pierna"])
        # 2026-08-24 es lunes: el primero de sus dias, el primer grupo del reparto.
        assert corre(rutinas.dia_de_entreno_del_pdf(self.PERFIL, "2026-08-24")) == {
            "entrena": True, "grupo": "Empuje"}
        # Miercoles, el segundo.
        assert corre(rutinas.dia_de_entreno_del_pdf(self.PERFIL, "2026-08-26"))["grupo"] == "Tirón"

    def test_el_dia_que_descansa_lo_dice_sin_inventar(self, monkeypatch):
        self._montar(monkeypatch, ["Empuje", "Tirón", "Pierna"])
        assert corre(rutinas.dia_de_entreno_del_pdf(self.PERFIL, "2026-08-25")) == {
            "entrena": False, "grupo": None}

    def test_sin_reparto_no_se_sabe_y_se_dice_que_no_se_sabe(self, monkeypatch):
        """Es la diferencia que importa: «no se que te toca» NO es «hoy descansas». Con la
        segunda respuesta a Inicio le saldria «Entreno» los siete dias."""
        self._montar(monkeypatch, None)
        assert corre(rutinas.dia_de_entreno_del_pdf(self.PERFIL, "2026-08-24")) is None

    def test_sin_los_dias_del_cliente_tampoco_se_sabe(self, monkeypatch):
        self._montar(monkeypatch, ["Empuje"])
        assert corre(rutinas.dia_de_entreno_del_pdf({"id": "c1"}, "2026-08-24")) is None

    def test_una_fecha_rota_no_revienta(self, monkeypatch):
        self._montar(monkeypatch, ["Empuje"])
        for basura in ("", "ayer", None, "2026-13-45"):
            assert corre(rutinas.dia_de_entreno_del_pdf(self.PERFIL, basura)) is None
