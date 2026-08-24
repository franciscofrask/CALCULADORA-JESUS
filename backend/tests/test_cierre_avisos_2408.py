# -*- coding: utf-8 -*-
"""Los avisos del cliente: el cierre de los fallos del 24-08 (campanita y correo).

Los casos reales, uno por arreglo:

  1. El cliente de habitos nocturnos que entra a las 21:00 sin haber cerrado el dia. Su
     quincenal cerraba a las 20:00 del dia siguiente y el aviso de "ultimo dia" no llego a
     existir: se lo comio "Cierra tu dia", que es el unico aviso que puede volver a nacer
     manana. En la base habia 19 cierra_dia contra 1 aviso de reporte.

  2. El cliente de Mantenimiento que subio sus fotos hace un año. El aviso de "repite tus
     fotos" leia `client_photos.created_at`, una columna que esa coleccion no tiene (647
     fotos en produccion, 0 con ese campo), asi que a el no se le pedian nunca y al que no
     habia subido ninguna se le pedian siempre. Y las fotos del ALTA no cuentan: no son de
     progreso y el resto de la app las deja fuera igual.

  3. Los 194 clientes que aparecian entrados hoy: la pasada de correos evaluaba a todos
     cada 15 minutos y de paso les escribia "ultima_entrada = hoy". Con eso, el "¿Todo
     bien?" de los siete dias y la tarea del entrenador de los catorce no podian saltar.
     Y esa misma pasada tampoco puede crear condicionadas: una nacida a las 00:15 cerraba
     el dia y el aviso del reporte de las 10:00 no llegaba a existir.

  4. El cliente caducado al que "Tu ciclo ha terminado" le volvia a nacer al mes y medio:
     su clave no lleva periodo dentro y la deduplicacion solo miraba 35 dias atras. Y el
     remedio de marcarlo "unica" a secas era peor: no volvia a recibirlo NUNCA, ni despues
     de renovar y caducar otra vez. La clave lleva el vencimiento dentro.

  5. El viernes a las 12:00, la app le decia a todo el mundo "te hemos mandado el correo de
     novedades" sin que nadie hubiera mandado nada: la newsletter la manda una persona.

  6. El correo que no sale se reintenta, pero contado: sin tope, un relay caido dejaba 288
     filas en `correos_pendientes` y 288 warnings por aviso y cliente.

Todo se prueba SIN backend: las reglas son puras y lo que toca base se llama con una base
de mentira.
"""
import asyncio
import os
import sys
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.avisos_cliente import (                              # noqa: E402
    avisos_condicionados, avisos_de_calendario, avisos_de_calendario_doc, elegir_avisos)

# El bucle es el de la bateria entera (tests/conftest.py): ver ahi por que.
from conftest import corre                                     # noqa: E402

MADRID = ZoneInfo("Europe/Madrid")
AHORA = datetime.now(timezone.utc)


def _es(a, m, d, h=0, mi=0):
    return datetime(a, m, d, h, mi, tzinfo=MADRID)


def _familias(avisos):
    return [a.get("familia") for a in avisos]


# ── 1. El del reporte va DELANTE del recordatorio diario ─────────────────────

class TestElDelReporteVaPrimero:
    """«Maximo uno al dia, y por orden: primero el de entrega, despues el de
    recordatorio» (doc 19-08). El de entrega, ademas, solo es candidato SU dia."""

    # Miercoles 2026-08-05 a las 9:00 abre el quincenal; cierra el jueves a las 20:00.
    ABRE = _es(2026, 8, 5, 9)

    def _ventana(self, mandado=False):
        return [{"tipo": "quincenal", "semana": 2, "abre": self.ABRE,
                 "cierra": self.ABRE + timedelta(days=1, hours=11), "mandado": mandado}]

    def test_a_las_21_gana_el_ultimo_dia_del_quincenal(self):
        """El jueves a las 21:00, sin cerrar el dia y con el quincenal sin mandar: el que
        sale es el del reporte, que hoy es su unico dia; el de cerrar el dia vuelve manana."""
        avisos = avisos_de_calendario_doc(
            ahora_es=_es(2026, 8, 6, 21), cerro_hoy=False, ventanas=self._ventana())
        assert _familias(avisos) == ["quincenal_ultimo", "cierra_dia"]
        assert elegir_avisos(avisos, [], set(), None, AHORA)[0]["familia"] == "quincenal_ultimo"

    def test_sin_nada_del_reporte_sigue_saliendo_cerrar_el_dia(self):
        """El arreglo es de orden, no de quitar: la noche que no hay reporte que reclamar,
        el aviso de cerrar el dia sale igual que siempre."""
        avisos = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 6, 21), cerro_hoy=False)
        assert _familias(avisos) == ["cierra_dia"]

    def test_el_fin_de_ciclo_tampoco_se_lo_come(self):
        """Mismo caso con el aviso que trae la renovacion: «Tu ciclo acaba en una semana»
        es candidato siete dias, pero el de cerrar el dia nace TODOS, asi que sin este
        orden podia taparlo indefinidamente al que entra solo de noche."""
        avisos = avisos_de_calendario_doc(
            ahora_es=_es(2026, 8, 6, 21), cerro_hoy=False, cliente_id="c1",
            fin_de_ciclo=date(2026, 8, 10))
        assert _familias(avisos) == ["fin_ciclo", "cierra_dia"]


# ── 4. Las claves de un solo uso ─────────────────────────────────────────────

class TestLasClavesDeUnSoloUso:
    """`sincronizar_avisos` deduplica mirando 35 dias atras, y estos tres avisos siguen
    siendo candidatos mucho mas tiempo con la misma clave: se marcan `unica` y se
    comprueban contra el historico entero.

    Y `unica` NO puede querer decir «este cliente no lo recibe nunca mas»: los que se
    marcan asi llevan el evento dentro de la clave, asi que lo que no se repite es el
    MISMO evento.
    """

    def _ciclo_terminado(self, **kw):
        return [a for a in avisos_de_calendario_doc(
            ahora_es=_es(2026, 8, 6, 12), cliente_id="c1", ciclo_vencido=True, **kw)
            if a["familia"] == "ciclo_terminado"][0]

    def _volvemos(self, **kw):
        return [a for a in avisos_condicionados(ahora=AHORA, **kw)
                if a["familia"] == "volvemos"][0]

    def test_ciclo_terminado_lleva_el_vencimiento_y_es_unica(self):
        aviso = self._ciclo_terminado(vencio_el=date(2026, 8, 1))
        assert aviso["clave"] == "ciclo_terminado:c1:2026-08-01"
        assert aviso.get("unica") is True

    def test_al_renovar_y_volver_a_caducar_vuelve_a_nacer(self):
        """EL CASO QUE HABRIA CAZADO LA REGRESION. Con la clave `ciclo_terminado:c1` a
        secas marcada `unica`, el que caduca, renueva y vuelve a caducar doce semanas
        despues no recibia «Tu ciclo ha terminado» la segunda vez -- ni en la campanita ni
        por correo, y es el aviso que trae el dinero --, porque nada borra `notifications`
        al renovar."""
        primero = self._ciclo_terminado(vencio_el=date(2026, 8, 1))
        segundo = self._ciclo_terminado(vencio_el=date(2026, 10, 24))
        assert primero["clave"] != segundo["clave"]
        # Y el segundo nace aunque el primero siga entero en el historico.
        assert elegir_avisos([segundo], [], {primero["clave"]}, None, AHORA) == [segundo]

    def test_sin_saber_cuando_vencio_no_se_marca_unica(self):
        """Una baja a mano no deja fecha. Ahi vale mas que se repita al mes y medio que
        callarle la renovacion para siempre."""
        aviso = self._ciclo_terminado()
        assert aviso["clave"] == "ciclo_terminado:c1"
        assert "unica" not in aviso

    def test_volvemos_lleva_la_fecha_del_aterrizaje_y_es_unica(self):
        aviso = self._volvemos(dias_en_mantenimiento=45, mantenimiento_desde="2026-07-01")
        assert aviso["clave"] == "volvemos:mantenimiento:2026-07-01"
        assert aviso.get("unica") is True

    def test_quien_se_va_de_mantenimiento_y_vuelve_recibe_el_suyo(self):
        """Mismo fallo por la otra puerta: con la clave fija y `unica`, al que sale de
        Mantenimiento y vuelve un año despues ya no se le preguntaba «¿Volvemos?»."""
        de_antes = self._volvemos(dias_en_mantenimiento=400,
                                  mantenimiento_desde="2025-06-01")
        de_ahora = self._volvemos(dias_en_mantenimiento=31,
                                  mantenimiento_desde="2026-07-20")
        assert de_antes["clave"] != de_ahora["clave"]

    def test_macros_provisionales_es_unica(self):
        """Este si es de una vez en la vida: la fecha del alta no cambia nunca."""
        perfil = {"created_at": (AHORA - timedelta(days=1)).isoformat()}
        aviso = avisos_de_calendario(perfil=perfil, ahora=AHORA,
                                     va_a_recibir_definitivos=True)[0]
        assert aviso["clave"].startswith("macros_provisionales:")
        assert aviso.get("unica") is True

    def test_los_que_llevan_la_fecha_dentro_no_la_llevan(self):
        """El de cerrar el dia se repite a proposito: su clave cambia cada dia."""
        aviso = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 6, 21), cerro_hoy=False)[0]
        assert aviso["clave"] == "cierra_dia:2026-08-06"
        assert "unica" not in aviso


# ── 5. El correo del viernes solo se anuncia si consta que salio ─────────────

class TestElCorreoDelViernes:

    VIERNES = _es(2026, 8, 7, 12)       # 2026-08-07 es viernes

    def test_sin_constancia_no_se_anuncia(self):
        assert avisos_de_calendario_doc(ahora_es=self.VIERNES,
                                        con_correo_de_novedades=False) == []

    def test_el_defecto_es_no_anunciarlo(self):
        """Todos los defectos de esa funcion son «no sale»: sin arranque no hay «Mañana
        empiezas», sin ventanas no hay reporte. Este valia True, o sea que quien llamara
        sin pasarlo le afirmaba al cliente que le habiamos mandado un correo que manda una
        persona, no la app."""
        assert avisos_de_calendario_doc(ahora_es=self.VIERNES) == []

    def test_con_la_tarea_hecha_si(self):
        avisos = avisos_de_calendario_doc(ahora_es=self.VIERNES,
                                          con_correo_de_novedades=True)
        assert _familias(avisos) == ["correo_viernes"]


# ── Lo que toca base, con una base de mentira ────────────────────────────────

class _Coleccion:
    """Lo minimo de una coleccion de Mongo para estas pruebas: devuelve el documento que
    se le da y apunta las escrituras, que es justo lo que hay que vigilar."""

    def __init__(self, doc=None):
        self.doc = doc
        self.escrituras = []

    async def find_one(self, *a, **k):
        return self.doc

    async def update_one(self, filtro, cambio, **k):
        self.escrituras.append((filtro, cambio))


class _Base:
    def __init__(self, **colecciones):
        for nombre, col in colecciones.items():
            setattr(self, nombre, col)

    def __getattr__(self, nombre):        # cualquier otra coleccion, vacia
        col = _Coleccion()
        setattr(self, nombre, col)
        return col


def _con_base(monkeypatch, base):
    import routes.notifications as notif
    monkeypatch.setattr(notif, "db", base)
    return notif


# ── 2. Las fotos se cuentan por taken_at, y las del alta no cuentan ──────────

class _Fotos:
    """`client_photos` de mentira. Aplica DOS cosas del codigo de verdad: el filtro de
    `uso` (las del alta no son de progreso) y el orden por `taken_at`."""

    def __init__(self, docs):
        self.docs = docs

    async def find_one(self, filtro, *a, **k):
        solo_progreso = filtro.get("uso") == {"$exists": False}
        valen = [d for d in self.docs if not (solo_progreso and d.get("uso"))]
        return max(valen, key=lambda d: d.get("taken_at") or "", default=None)


class TestLaUltimaFoto:
    """La coleccion `client_photos` se escribe con `taken_at` y `uploaded_at`. Leyendo
    `created_at` la fecha salia vacia y el aviso se apagaba en cuanto subia la primera."""

    HOY = date(2026, 8, 24)
    PERFIL = {"id": "c1", "plan": "mantenimiento",
              "cycle_start": "2026-01-01", "created_at": "2026-01-01"}

    def _faltan(self, monkeypatch, fotos, dias_medidas):
        notif = _con_base(monkeypatch, _Base(client_photos=_Fotos(fotos),
                                             reports=_Coleccion(None)))
        perfil = {**self.PERFIL, "medidas_sueltas": [
            {"fecha": (self.HOY - timedelta(days=dias_medidas)).isoformat()}]}
        return corre(notif._fotos_o_medidas_viejas(perfil, self.HOY))

    def _foto(self, dias, **extra):
        return {"taken_at": (self.HOY - timedelta(days=dias)).isoformat(), **extra}

    def test_con_una_foto_vieja_se_le_pide_repetirla(self, monkeypatch):
        assert self._faltan(monkeypatch, [self._foto(60)], dias_medidas=2) == ["tus fotos"]

    def test_con_una_foto_de_esta_semana_no_se_le_pide_nada_de_fotos(self, monkeypatch):
        assert self._faltan(monkeypatch, [self._foto(3)], dias_medidas=60) == ["tus medidas"]

    def test_la_foto_del_alta_no_tapa_la_falta_de_fotos_de_progreso(self, monkeypatch):
        """El de autogestion que reenvia el basico manda su foto de grasa (`uso`:
        alta_grasa) y no ha hecho ni una foto de progreso desde hace dos meses. Contando
        la del alta, se le callaba «repite tus fotos» cuatro semanas mas."""
        fotos = [self._foto(60), self._foto(1, uso="alta_grasa")]
        assert self._faltan(monkeypatch, fotos, dias_medidas=2) == ["tus fotos"]


# ── 3. Evaluar no es entrar ──────────────────────────────────────────────────

class TestLaHuellaDeEntrar:
    """`ultima_entrada` es la prueba de que el cliente abrio la app. La pasada de correos
    la escribia por el, y con eso «llevas 7 dias sin entrar» no podia saltar jamas."""

    HOY = date(2026, 8, 24)
    PERFIL = {"id": "c1", "ultima_entrada": "2026-08-10"}

    def _correr(self, monkeypatch, marcar):
        perfiles = _Coleccion(None)
        notif = _con_base(monkeypatch, _Base(client_profiles=perfiles))
        dias = corre(notif._dias_sin_entrar(self.PERFIL, self.HOY, marcar))
        return dias, perfiles.escrituras

    def test_el_cliente_entrando_deja_su_huella(self, monkeypatch):
        dias, escrituras = self._correr(monkeypatch, True)
        assert dias == 14
        assert escrituras[0][1] == {"$set": {"ultima_entrada": "2026-08-24"}}

    def test_la_pasada_de_correos_no_la_deja(self, monkeypatch):
        dias, escrituras = self._correr(monkeypatch, False)
        assert dias == 14
        assert escrituras == [], "la pasada de correos marco al cliente como entrado hoy"


class TestLaNewsletter:
    """El aviso del viernes se ata a la tarea manual de Jenny (`newsletter:{semana}`)."""

    HOY = date(2026, 8, 21)             # viernes

    def test_sin_la_tarea_hecha_es_que_no_consta(self, monkeypatch):
        notif = _con_base(monkeypatch, _Base(tareas=_Coleccion(None)))
        assert corre(notif._newsletter_de_esta_semana(self.HOY)) is False

    def test_con_la_tarea_hecha_consta(self, monkeypatch):
        notif = _con_base(monkeypatch, _Base(tareas=_Coleccion({"id": "t1"})))
        assert corre(notif._newsletter_de_esta_semana(self.HOY)) is True

    def test_los_otros_seis_dias_ni_pregunta(self, monkeypatch):
        """Esto corre en cada consulta de la campanita: el martes no hay aviso que sacar,
        asi que tampoco hay consulta que hacer."""
        tareas = _Coleccion({"id": "t1"})
        notif = _con_base(monkeypatch, _Base(tareas=tareas))
        assert corre(notif._newsletter_de_esta_semana(date(2026, 8, 18))) is False


# ── 6. La pasada de correos: el freno del reintento y quien no es ────────────

def _casa(doc, filtro):
    """El poquito de Mongo que hace falta aqui: igualdad y `$lt`."""
    for campo, valor in filtro.items():
        if isinstance(valor, dict) and "$lt" in valor:
            actual = doc.get(campo)
            if actual is None or not actual < valor["$lt"]:
                return False
        elif doc.get(campo) != valor:
            return False
    return True


class _Marcas:
    """`db.correos_de_avisos`: el indice unico (user+clave) y el contador de intentos."""

    def __init__(self):
        self.docs = []

    async def create_index(self, *a, **k):
        return "user_clave_unico"

    async def insert_one(self, doc):
        if any(d["user_id"] == doc["user_id"] and d["clave"] == doc["clave"]
               for d in self.docs):
            raise RuntimeError("duplicate key")
        self.docs.append(dict(doc))

    async def find_one_and_update(self, filtro, cambio, **k):
        for d in self.docs:
            if _casa(d, filtro):
                antes = dict(d)                 # Mongo devuelve el de ANTES por defecto
                for campo, cuanto in (cambio.get("$inc") or {}).items():
                    d[campo] = d.get(campo, 0) + cuanto
                return antes
        return None

    async def update_one(self, filtro, cambio, **k):
        for d in self.docs:
            if _casa(d, filtro):
                d.update(cambio.get("$set") or {})
                return


class _Lista:
    """Una coleccion que solo tiene que devolver siempre los mismos documentos."""

    def __init__(self, docs):
        self.docs = docs

    def find(self, *a, **k):
        return self

    async def to_list(self, *a, **k):
        return list(self.docs)

    async def find_one(self, *a, **k):
        return self.docs[0] if self.docs else None


class TestLaPasadaDeCorreos:

    AVISO = {"clave": "mensual_ultimo:2026-08-21", "title": "Último día para tu reporte",
             "body": "Se cierra mañana.", "link": "/dashboard/reports"}

    def _correr(self, monkeypatch, resultados, pasadas=1):
        """Corre la pasada `pasadas` veces. `resultados` es lo que devuelve `enviar` en
        cada llamada (el ultimo se repite). Devuelve (envios, como se sincronizo)."""
        envios, sincronizadas = [], []

        async def _pantalla(_nombre):
            return True

        async def _sincronizar(_uid, **kw):
            sincronizadas.append(kw)
            return 0

        async def _correo_de(_db, _uid, email):
            return email

        async def _enviar(_db, destino, _asunto, _cuerpo, tipo="generico"):
            envios.append(destino)
            return resultados[min(len(envios) - 1, len(resultados) - 1)]

        base = _Base(correos_de_avisos=_Marcas(),
                     client_profiles=_Lista([{"user_id": "u1"}]),
                     users=_Lista([{"email": "ana@ejemplo.com", "name": "Ana"}]),
                     notifications=_Lista([self.AVISO]))
        monkeypatch.setattr("core.correo_avisos.db", base)
        monkeypatch.setattr("routes.settings.pantalla_activa", _pantalla)
        monkeypatch.setattr("routes.notifications.sincronizar_avisos", _sincronizar)
        monkeypatch.setattr("core.correo.configurado", lambda: True)
        monkeypatch.setattr("core.correo.correo_del_cliente", _correo_de)
        monkeypatch.setattr("core.correo.enviar", _enviar)

        from core.correo_avisos import pasada_de_correos_de_avisos
        for _ in range(pasadas):
            corre(pasada_de_correos_de_avisos())
        return envios, sincronizadas

    def test_un_aviso_un_correo(self, monkeypatch):
        envios, _ = self._correr(monkeypatch, [True], pasadas=4)
        assert envios == ["ana@ejemplo.com"], "la marca unica tiene que cortar la repeticion"

    def test_si_el_relay_vuelve_el_correo_acaba_saliendo(self, monkeypatch):
        """Lo que arregla el reintento: la primera pasada no sale, la segunda si, y a
        partir de ahi no se vuelve a mandar."""
        envios, _ = self._correr(monkeypatch, [False, True], pasadas=4)
        assert len(envios) == 2

    def test_el_reintento_tiene_freno(self, monkeypatch):
        """EL CASO QUE HABRIA CAZADO EL AGUJERO: con la marca borrada en cada fallo y la
        pasada cada 15 minutos, un relay caido dejaba ~288 filas en `correos_pendientes` y
        288 warnings por aviso y cliente durante los 3 dias de la ventana."""
        from core.correo_avisos import MAX_INTENTOS
        envios, _ = self._correr(monkeypatch, [False], pasadas=MAX_INTENTOS + 5)
        assert len(envios) == MAX_INTENTOS

    def test_la_pasada_no_es_el_cliente_entrando(self, monkeypatch):
        """Ni deja la huella de «ha entrado» ni crea condicionadas: una nacida a las 00:15
        cerraba el dia entero y el «tu reporte esta abierto» de las 10:00 -- candidato UN
        SOLO DIA y de las familias que van por correo -- no llegaba a existir."""
        _, sincronizadas = self._correr(monkeypatch, [True])
        assert sincronizadas == [{"marcar_entrada": False, "solo_calendario": True}]
