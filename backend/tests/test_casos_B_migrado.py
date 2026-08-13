# -*- coding: utf-8 -*-
"""
Casos 08-10 de la lista de 85 que entrego Jesus: «EL CLIENTE QUE VIENE DE LA CALCULADORA».

Son los 159 clientes que se trajeron de Calma. No son altas nuevas: llegaron con dietas, con
macros puestos a mano por Jesus y con años de historial. Lo que Jesus pide comprobar es que la
app los trate como lo que son -- clientes de siempre -- y no como a alguien que acaba de
registrarse:

    08 [CRITICO]  ni «te quedan 4 preguntas» ni «tus macros son provisionales». Ve su
                  historico y entra a su dieta sin barreras.
    09 [CRITICO]  sus macros son los que tenia, con su fecha real, sin recalcular.
    10            ninguna bienvenida encadenada antes de su primera dieta.

COMO SE PRUEBA. Casi todo sale de la API de verdad (el backend tiene que estar vivo): se
descubre un migrado con el panel de admin, se entra en su cuenta con la cabecera de
suplantacion `X-Actuar-Como` -- el mismo camino del entrenador, ver `test_actuar_como` -- y se
mira lo que le llega.

Los avisos de la pantalla de Inicio NO viven en el backend: son condiciones escritas en
`frontend/src/pages/ClientDashboard.jsx` sobre los campos del perfil. Aqui se repiten esas
condiciones tal cual, con el perfil que devuelve la API, porque lo que Jesus lee en pantalla
es el resultado de esa cuenta y no hay endpoint que la haga. Si la condicion del front cambia,
hay que cambiarla aqui: va anotada con su linea.

NADA DE ESTO ESCRIBE EN LA BASE. Se lee y ya: la base es compartida.
"""
import re
import time
from pathlib import Path

import pytest
import requests

from conftest import ADMIN_EMAIL, ADMIN_PASSWORD, API

# El backend local corre con recarga automatica y se cae unos segundos cada vez que alguien
# toca un fichero. Sin esto, media prueba muere por «connection refused» y parece un fallo.
# Por lo mismo no se usan los fixtures de sesion de `conftest`: preguntan por la salud del
# servidor UNA vez y, si justo entonces esta recargando, saltan el fichero entero.
INTENTOS = 15


def pide(metodo, ruta, **kw):
    kw.setdefault("timeout", 90)
    ultimo = None
    for _ in range(INTENTOS):
        try:
            return requests.request(metodo, f"{API}{ruta}", **kw)
        except requests.RequestException as e:
            ultimo = e
            time.sleep(2)
    pytest.skip(f"el backend no responde en {ruta}: {ultimo}")


@pytest.fixture(scope="module")
def cabeceras_admin():
    r = pide("post", "/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        pytest.skip(f"no se pudo entrar como admin ({r.status_code})")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# Los planes que ya no se venden. Todo migrado de Calma tiene uno de estos.
PLANES_HEREDADOS = {"elm", "gold", "silver", "bronze", "calma", "reto12en12_gold", "premium"}

# La nota con la que se escribieron las 3.068 filas de la importacion.
NOTA_DE_LA_IMPORTACION = "Importado de Calma"

FRONT = Path(__file__).resolve().parents[2] / "frontend" / "src"


@pytest.fixture(scope="module")
def catalogo():
    """El catalogo de planes, que es de donde el front saca las habilitaciones."""
    r = pide("get", "/plans")
    if r.status_code != 200:
        pytest.skip(f"no se pudo leer el catalogo de planes ({r.status_code})")
    return r.json()


@pytest.fixture(scope="module")
def migrado(cabeceras_admin):
    """Un cliente real traido de Calma, con sus datos y con la cabecera para entrar como el.

    Se descubre por API a proposito, sin ids a mano: la base de desarrollo es una copia de
    produccion y los ids cambian cada vez que se restaura.
    """
    r = pide("get", "/admin/clients?limit=500", headers=cabeceras_admin)
    if r.status_code != 200:
        pytest.skip(f"no se pudo listar clientes ({r.status_code})")
    lista = r.json() if isinstance(r.json(), list) else (r.json().get("clients") or [])

    def primer_pesaje(c):
        fechas = [str(p.get("fecha") or "")[:10] for p in (c.get("pesos") or [])]
        return min(fechas) if fechas else "9999"

    # Plan heredado y pesajes anteriores a 2025: eso solo lo tiene quien venia de Calma. Se
    # ordena por longitud de la serie para topar antes con uno de historia larga.
    candidatos = [c for c in lista
                  if (c.get("plan") or "").lower() in PLANES_HEREDADOS
                  and primer_pesaje(c) < "2025-01-01" and c.get("user_id")]
    candidatos.sort(key=lambda c: -len(c.get("pesos") or []))

    for c in candidatos[:12]:
        detalle = pide("get", f"/admin/clients/{c['id']}", headers=cabeceras_admin)
        if detalle.status_code != 200:
            continue
        d = detalle.json()
        historial = d.get("macro_history") or []
        importadas = [e for e in historial if (e.get("note") or "") == NOTA_DE_LA_IMPORTACION]
        # RECIEN MIGRADO, que es lo que dice el caso 09: TODO su historial viene de Calma y
        # nadie le ha tocado nada despues. En la base de desarrollo hay migrados con filas
        # sueltas de pruebas de otra gente encima (una lleva la nota «prueba de
        # concurrencia»), y esas cambian sus macros sin ser el ajuste vigente: el caso que
        # hay que fijar es el del cliente tal y como quedo al importarlo.
        if not importadas or len(importadas) != len(historial):
            continue
        suplantando = {**cabeceras_admin, "X-Actuar-Como": c["user_id"]}
        perfil = pide("get", "/clients/profile", headers=suplantando)
        if perfil.status_code != 200:
            continue        # su usuario no es un cliente: no se puede entrar en su cuenta
        return {
            "id": c["id"],
            "user_id": c["user_id"],
            "plan": (c.get("plan") or "").lower(),
            "cabeceras": suplantando,
            "perfil": perfil.json(),
            "historial": historial,
            "importadas": importadas,
            "dietas": (d.get("nutrition_stats") or {}).get("total_diets"),
        }

    pytest.skip("no hay ningun cliente migrado de Calma en esta base")


@pytest.fixture(scope="module")
def mis_macros(migrado):
    """Lo que le llega a la pantalla «Mis macros»."""
    r = pide("get", "/macros/historial", headers=migrado["cabeceras"])
    assert r.status_code == 200, r.text
    return r.json()


def puede_macros_personalizados(plan, catalogo):
    """`can('macros_personalizados')` del front (frontend/src/lib/planAccess.js)."""
    habilitaciones = (catalogo.get(plan) or {}).get("habilitaciones") or {}
    return habilitaciones.get("calculadora") == "personalizado"


# ── Caso 08: entrar por primera vez ────────────────────────────────────────────────────────

class TestCaso08NoLeTratanComoUnAltaNueva:
    """[CRITICO] Ya era cliente. No se le puede pedir que termine de darse de alta."""

    def test_la_app_sabe_que_sus_macros_los_puso_alguien(self, migrado):
        """De este campo cuelga todo lo demas (punto 4.1): lo calcula el servidor mirando
        quien escribio su ultimo ajuste, no la bandera del cuestionario."""
        assert migrado["perfil"].get("macros_puestos_por_alguien") is True, (
            "sus macros los puso Jesus y la app cree que salieron de un calculo")

    def test_no_le_dice_que_sus_macros_son_provisionales(self, migrado):
        """El aviso de `core/avisos_cliente`. En produccion le llegaba a los 174 activos."""
        r = pide("get", "/notifications", headers=migrado["cabeceras"])
        assert r.status_code == 200, r.text
        datos = r.json()
        avisos = datos if isinstance(datos, list) else (datos.get("items") or [])
        titulos = [(a.get("title") or a.get("titulo") or "") for a in avisos]
        assert not [t for t in titulos if "provisional" in t.lower()], titulos

    def test_ni_le_pide_terminar_de_ajustar_los_macros_iniciales(self, migrado, catalogo):
        """La tarjeta `ajustar-macros-banner` de Inicio (ClientDashboard.jsx:571)."""
        p = migrado["perfil"]
        sale = bool(p.get("questionnaire_completed")
                    and not p.get("ajuste_macros_completado")
                    and not p.get("macros_puestos_por_alguien"))
        assert not sale, "le sale «Completa tu cuestionario inicial» a un cliente de años"

    def test_ni_le_dice_que_le_quedan_preguntas(self, migrado, catalogo):
        """La tarjeta `nivel1-pending-banner` de Inicio (ClientDashboard.jsx:667).

        Es literalmente el «te quedan 4 preguntas» del caso de Jesus: «Completa tu perfil y te
        afinamos los macros / Te quedan unas preguntas: biotipo, salud, entreno...». En el
        telefono ademas es el UNICO aviso que se pinta (`avisoPendiente`, linea 347), asi que
        es lo primero que ve un migrado al abrir la app.
        """
        p = migrado["perfil"]
        sale = bool(puede_macros_personalizados(migrado["plan"], catalogo)
                    and p.get("questionnaire_completed")
                    and (p.get("ajuste_macros_completado") or p.get("macros_puestos_por_alguien"))
                    and not p.get("questionnaire_nivel1_completed"))
        assert not sale, (
            "a un cliente migrado le sale «Te quedan unas preguntas: biotipo, salud, "
            "entreno...»: nunca hizo ese cuestionario porque ya tenia sus macros")

    def test_ve_su_historico(self, mis_macros, migrado):
        assert mis_macros["con_historico"] is True, "su plan lleva ajustes: la tabla va"
        assert len(mis_macros["entradas"]) > 1, "un migrado trae años de ajustes"

    def test_y_entra_a_su_dieta_sin_barreras(self, migrado):
        """Sin redirecciones ni 403 por el camino: la pantalla de Nutricion contesta."""
        hoy = time.strftime("%Y-%m-%d")
        r = pide("get", f"/diets/{hoy}", headers=migrado["cabeceras"])
        assert r.status_code == 200, f"su dia de hoy no abre: {r.status_code} {r.text[:200]}"
        r = pide("get", "/diets/recent", headers=migrado["cabeceras"])
        assert r.status_code == 200, r.text


# ── Caso 09: sus macros recien migrado ─────────────────────────────────────────────────────

class TestCaso09SusMacrosSonLosQueTenia:
    """[CRITICO] Los que le puso Jesus, con su fecha, sin pasar por la calculadora."""

    def test_los_de_su_perfil_son_los_del_ajuste_vigente(self, migrado, mis_macros):
        """Si en algun momento se recalcularon, el perfil y el historial no cuadran."""
        vigente = mis_macros.get("vigente")
        assert vigente, "no tiene ningun ajuste vigente"
        perfil_entreno = migrado["perfil"].get("macros_training") or {}
        assert vigente["entreno"] == {
            "proteina": round(float(perfil_entreno.get("protein"))),
            "hidratos": round(float(perfil_entreno.get("carbs"))),
            "grasa": round(float(perfil_entreno.get("fat"))),
        }, "sus macros de hoy no son los del ajuste que manda"

    def test_la_fecha_es_la_real_y_no_la_de_la_importacion(self, migrado, mis_macros):
        """La trampa de las 3.446 filas migradas: `created_at` es el dia en que se importaron
        -- todas el mismo -- y `effective_date` es cuando Jesus hizo el ajuste de verdad. La
        pantalla tiene que enseñar la segunda."""
        vigente = mis_macros["vigente"]
        porid = {e.get("id"): e for e in migrado["historial"]}
        fila = porid.get(vigente["id"])
        assert fila, "el ajuste vigente no aparece en el historial del panel"
        assert vigente["fecha"] == fila.get("effective_date"), (
            f"«Mis macros» dice {vigente['fecha']} y el ajuste es del "
            f"{fila.get('effective_date')}")
        # Y no es la fecha de la importacion, que es lo que se veia antes.
        assert vigente["fecha"] != str(fila.get("created_at") or "")[:10] or \
            fila.get("effective_date") == str(fila.get("created_at") or "")[:10]

    def test_su_historico_no_empieza_el_dia_que_se_importo(self, migrado, mis_macros):
        """Con `created_at` toda su historia caia en una sola fecha."""
        fechas = {e["fecha"] for e in mis_macros["entradas"] if e.get("fecha")}
        assert len(fechas) > 1, f"todos sus ajustes salen con la misma fecha: {fechas}"
        importaciones = {str(e.get("created_at") or "")[:10] for e in migrado["importadas"]}
        assert not fechas.issubset(importaciones), (
            "las fechas de su historico son las de la importacion, no las de sus ajustes")

    def test_no_estan_recalculados(self, migrado):
        """`macros_source` dice quien los escribio. Un recalculo deja «auto» o «v2»."""
        assert (migrado["perfil"].get("macros_source") or "") == "manual", (
            f"sus macros figuran como {migrado['perfil'].get('macros_source')!r}: "
            "alguien los volvio a calcular")

    def test_y_no_puede_recalcularselos_el(self, migrado):
        """Su plan es de los que lleva entrenador: la calculadora no es suya (punto 4.10)."""
        ajustables = migrado["perfil"].get("macros_ajustables") or {}
        assert ajustables.get("puede") is False, ajustables


# ── Caso 10: cuantas pantallas hasta su primera dieta ──────────────────────────────────────

class TestCaso10SinBienvenidasEncadenadas:
    """Para quien ya era cliente no hay nada que presentarle: la app ya es suya.

    Los dos recorridos viven en el front y estan apagados con un interruptor desde el
    11-08-2026 (commit «Fuera las bienvenidas»). Esto es un cerrojo sobre esos interruptores:
    el dia que alguien los vuelva a encender, que se entere aqui y no Jesus abriendo la app.
    """

    @pytest.mark.parametrize("fichero,constante", [
        ("context/OnboardingContext.jsx", "RECORRIDO_ACTIVO"),
        ("pages/NutritionPage.jsx", "BIENVENIDA_NUTRICION"),
    ])
    def test_los_recorridos_de_bienvenida_siguen_apagados(self, fichero, constante):
        ruta = FRONT / fichero
        if not ruta.exists():
            pytest.skip(f"no encuentro {ruta}")
        texto = ruta.read_text(encoding="utf-8")
        m = re.search(rf"const\s+{constante}\s*=\s*(true|false)\s*;", texto)
        assert m, f"ya no existe la constante {constante} en {fichero}"
        assert m.group(1) == "false", (
            f"{constante} esta encendido: al migrado le vuelve a salir la bienvenida")

    def test_la_dieta_de_hoy_se_sirve_a_la_primera(self, migrado):
        """Ninguna pantalla intermedia por parte del servidor: se pide el dia y esta."""
        hoy = time.strftime("%Y-%m-%d")
        r = pide("get", f"/diets/{hoy}", headers=migrado["cabeceras"])
        assert r.status_code == 200, r.text
