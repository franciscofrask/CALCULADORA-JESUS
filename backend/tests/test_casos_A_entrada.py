# -*- coding: utf-8 -*-
"""
Seccion A -- ENTRADA Y ALTA (casos 01 a 07).

De donde sale: de la lista de 85 casos de prueba que entrego Jesus el 12-08-2026. Cada test
de aqui abajo lleva escrito el caso tal y como lo dicto el, sin traducirlo a lenguaje de
programador: si manana el codigo cambia y el caso deja de cumplirse, lo que salta en rojo es
su frase, no la mia.

Que se fija:

  01  El test de nivel (/test) se responde entero sin cuenta y sin dar el correo, y no echa
      de la app al que ya tiene la sesion abierta.
  02  /recuperar deja cambiar la contrasena y no expulsa a nadie.
  03  Al registrarse, el cuestionario inicial queda por hacer y no se puede saltar.
  04  [CRITICO] Al terminar el cuestionario salen los macros y el nombre real de la persona.
  05  [CRITICO] En /planes salen los tres niveles y el Nivel 3 se agenda por llamada, nunca
      con un boton de pagar. La membresia NO sale ahi (Jesus, 13-08: se come la entrada del
      Nivel 1; es para quien acaba un ciclo, no para quien llega de la calle).
  06  Una direccion que no existe no echa al login al que ya esta dentro.
  07  [CRITICO] El banner de "Instala 12EN12" no tapa el boton de Entrar.

COMO ESTAN HECHOS. Lo que vive en la API se prueba contra la API de verdad (backend en
REACT_APP_BACKEND_URL). Lo que solo vive en el navegador -- a que pantalla te manda el router,
que boton pinta cada plan -- se comprueba leyendo el fuente del frontend, que es el mismo
recurso que ya usa test_avisos_cliente.py para cruzar los enlaces con las rutas del router.
Lo puramente visual (que un banner tape o no tape un boton a 390 px) NO se finge aqui: va
marcado como skip para mirarlo con los ojos.

LOS DATOS QUE CREA SE BORRAN. La base es compartida: cada usuario de paso se borra al acabar
(usuario, ficha, historial de macros, respuestas del quiz, correos y enlaces de recuperacion).
"""
import os
import pathlib
import re
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"

FRONT = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src"

# Contrasena de los usuarios de paso. Ocho caracteres o mas: es lo que exige reset-password.
CLAVE = "Prueba1234"
CLAVE_NUEVA = "Prueba5678"


def fuente(relativo: str) -> str:
    """El fuente de una pantalla del frontend."""
    return (FRONT / relativo).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def mongo(api_disponible):
    """Conexion directa a la base, para dos cosas que la API no da:

      - leer el enlace de recuperacion (el token viaja por correo y en la base solo queda su
        hash, pero el cuerpo del correo se guarda entero en `correos_pendientes` cuando no
        hay SMTP configurado, que es el caso en desarrollo),
      - dejar la base como estaba al acabar.
    """
    from pymongo import MongoClient

    from core.config import DB_NAME, MONGO_URL

    cliente = MongoClient(MONGO_URL)
    try:
        yield cliente[DB_NAME]
    finally:
        cliente.close()


@pytest.fixture(scope="module")
def alta(mongo):
    """Fabrica de usuarios de paso: `alta("Marcos Prueba")` devuelve uno recien registrado.

    Se registran por la puerta de siempre (POST /auth/register) a proposito: el estado en el
    que nace la ficha es justo lo que estan mirando los casos 03 y 04.
    """
    creados = []

    def _alta(nombre="Marcos Prueba"):
        correo = f"caso-a-{uuid.uuid4().hex[:10]}@test.com"
        r = requests.post(f"{API}/auth/register",
                          json={"email": correo, "password": CLAVE, "name": nombre}, timeout=30)
        assert r.status_code == 200, f"no se ha podido registrar: {r.status_code} {r.text[:200]}"
        datos = r.json()
        persona = {
            "email": correo,
            "password": CLAVE,
            "nombre": nombre,
            "token": datos["access_token"],
            "user_id": datos["user"]["id"],
            "cabeceras": {"Authorization": f"Bearer {datos['access_token']}"},
        }
        creados.append(persona)
        return persona

    yield _alta

    for p in creados:
        uid, correo = p["user_id"], p["email"]
        mongo.users.delete_many({"id": uid})
        mongo.client_profiles.delete_many({"user_id": uid})
        mongo.macro_history.delete_many({"user_id": uid})
        mongo.quiz_respuestas.delete_many({"user_id": uid})
        mongo.macro_revisiones.delete_many({"user_id": uid})
        mongo.diets.delete_many({"user_id": uid})
        mongo.password_resets.delete_many({"user_id": uid})
        mongo.correos_pendientes.delete_many({"para": correo})
        mongo.leads.delete_many({"email": correo})


# ---------------------------------------------------------------------------
# CASO 01 -- "Abrir /test sin cuenta y responder las seis preguntas. Espero: llega al
#            resultado sin pedir correo ni registro, y no expulsa a quien ya tenga sesion
#            abierta."
# ---------------------------------------------------------------------------

class TestCaso01ElTestDeNivelSinCuenta:

    def test_las_seis_preguntas_se_ven_sin_cuenta(self, api_disponible):
        r = requests.get(f"{API}/quiz-venta", timeout=30)
        assert r.status_code == 200, "el test de nivel pide identificarse para empezar"
        preguntas = r.json().get("preguntas") or []
        assert len(preguntas) == 6, f"Jesus cuenta seis preguntas y salen {len(preguntas)}"

    def test_el_resultado_no_pide_correo_ni_registro(self, api_disponible, mongo):
        """Se contestan las seis y sale el resultado. Sin cabecera de sesion, sin correo en el
        cuerpo, y sin que quede nadie apuntado en el CRM por haber contestado."""
        preguntas = requests.get(f"{API}/quiz-venta", timeout=30).json()["preguntas"]
        respuestas = {str(p["id"]): p["opciones"][0]["id"] for p in preguntas}

        leads_antes = mongo.leads.count_documents({})
        r = requests.post(f"{API}/quiz-venta", json={"respuestas": respuestas}, timeout=30)
        assert r.status_code == 200, f"el resultado no sale sin cuenta: {r.status_code} {r.text[:200]}"

        datos = r.json()
        assert datos.get("recomendado"), "no dice que nivel le pega"
        assert datos.get("por_que"), "no explica por que"
        assert len(datos.get("niveles") or []) == 3, "no ensena los tres niveles"
        assert mongo.leads.count_documents({}) == leads_antes, (
            "contestar el test da de alta un lead: el correo es el paso de DESPUES, no el peaje")

    def test_el_test_no_echa_al_que_ya_tiene_la_sesion_abierta(self, api_disponible):
        """El router: /test va suelto, fuera de PublicRoute. PublicRoute manda al panel a quien
        ya ha entrado alguna vez, que es justo a quien se le pasa el enlace del test."""
        app = fuente("App.js")
        m = re.search(r'path="/test"\s+element=\{([^}]*)\}', app)
        assert m, "ya no existe la ruta /test en App.js"
        elemento = m.group(1)
        assert "PublicRoute" not in elemento, (
            "/test esta dentro de PublicRoute: al que tiene sesion se le rebota al panel y "
            "pierde el test")
        assert "ProtectedRoute" not in elemento, "/test pide sesion y tiene que ser publico"

    def test_el_resultado_tambien_sale_con_la_sesion_abierta(self, api_disponible, cabeceras_cliente):
        preguntas = requests.get(f"{API}/quiz-venta", timeout=30).json()["preguntas"]
        respuestas = {str(p["id"]): p["opciones"][0]["id"] for p in preguntas}
        r = requests.post(f"{API}/quiz-venta", json={"respuestas": respuestas},
                          headers=cabeceras_cliente, timeout=30)
        assert r.status_code == 200, "con la sesion abierta el test deja de responder"
        assert r.json().get("recomendado")


# ---------------------------------------------------------------------------
# CASO 02 -- "Abrir /recuperar con la sesion iniciada en el movil. Espero: deja cambiar la
#            contrasena, no echa a nadie."
# ---------------------------------------------------------------------------

class TestCaso02RecuperarLaContrasena:

    def test_recuperar_no_esta_detras_de_publicroute(self, api_disponible):
        """Al enlace del correo se llega desde el movil, donde la sesion sigue abierta. Si
        /recuperar viviera dentro de PublicRoute, ese seria el unico sitio al que no puede
        entrar quien mas lo necesita."""
        app = fuente("App.js")
        m = re.search(r'path="/recuperar"\s+element=\{([^}]*)\}', app)
        assert m, "ya no existe la ruta /recuperar en App.js"
        assert "PublicRoute" not in m.group(1), (
            "/recuperar esta dentro de PublicRoute: al que tiene sesion se le echa de la "
            "pantalla que ha abierto desde el correo")

    def test_pedir_el_enlace_no_exige_sesion_ni_delata_quien_es_cliente(self, api_disponible, alta):
        # El correo que SI existe es uno de paso, no el del cliente demo: pedir el enlace deja
        # un token y un correo pendiente, y eso no se le ensucia a una cuenta compartida.
        persona = alta("Sara Prueba")
        desconocido = requests.post(f"{API}/auth/forgot-password",
                                    json={"email": f"nadie-{uuid.uuid4().hex[:8]}@test.com"},
                                    timeout=30)
        assert desconocido.status_code == 200, "pedir el enlace falla sin sesion"
        conocido = requests.post(f"{API}/auth/forgot-password",
                                 json={"email": persona["email"]}, timeout=30)
        assert conocido.status_code == 200
        assert desconocido.json() == conocido.json(), (
            "la respuesta cambia segun exista el correo: eso convierte esta pantalla en una "
            "forma de averiguar quien es cliente")

    def test_se_cambia_la_contrasena_y_la_sesion_abierta_sigue_valiendo(self, api_disponible,
                                                                       alta, mongo):
        """El caso entero: con la sesion abierta pide el enlace, lo abre, elige contrasena
        nueva y entra con ella. Y la sesion que tenia abierta no se cae por el camino."""
        persona = alta("Marcos Prueba")

        r = requests.post(f"{API}/auth/forgot-password", json={"email": persona["email"]},
                          headers=persona["cabeceras"], timeout=30)
        assert r.status_code == 200

        # El token solo existe dentro del enlace del correo (en la base se guarda su hash).
        # Sin SMTP configurado el correo se queda entero en `correos_pendientes`, que es de
        # donde se lee aqui.
        correo = mongo.correos_pendientes.find_one({"para": persona["email"],
                                                    "tipo": "recuperar_password"})
        assert correo, "no se ha generado el correo con el enlace para cambiar la contrasena"
        enlace = re.search(r"/recuperar\?token=(\S+)", correo["cuerpo"])
        assert enlace, f"el correo no lleva enlace de recuperacion: {correo['cuerpo'][:200]}"

        cambio = requests.post(f"{API}/auth/reset-password",
                               json={"token": enlace.group(1), "password": CLAVE_NUEVA},
                               timeout=30)
        assert cambio.status_code == 200, f"no deja cambiarla: {cambio.status_code} {cambio.text[:200]}"

        entrar = requests.post(f"{API}/auth/login",
                               json={"email": persona["email"], "password": CLAVE_NUEVA},
                               timeout=30)
        assert entrar.status_code == 200, "la contrasena nueva no sirve para entrar"

        yo = requests.get(f"{API}/auth/me", headers=persona["cabeceras"], timeout=30)
        assert yo.status_code == 200, (
            "cambiar la contrasena tira la sesion que ya estaba abierta: al del movil se le "
            "echa justo despues de arreglarlo")

    def test_el_enlace_no_vale_dos_veces(self, api_disponible, alta, mongo):
        """No es de la lista de Jesus, pero es lo que hace que el caso 02 sea seguro: el
        enlace del correo se gasta al usarlo."""
        persona = alta("Lucia Prueba")
        requests.post(f"{API}/auth/forgot-password", json={"email": persona["email"]}, timeout=30)
        correo = mongo.correos_pendientes.find_one({"para": persona["email"],
                                                    "tipo": "recuperar_password"})
        token = re.search(r"/recuperar\?token=(\S+)", correo["cuerpo"]).group(1)

        primera = requests.post(f"{API}/auth/reset-password",
                                json={"token": token, "password": CLAVE_NUEVA}, timeout=30)
        assert primera.status_code == 200
        segunda = requests.post(f"{API}/auth/reset-password",
                                json={"token": token, "password": "OtraMas1234"}, timeout=30)
        assert segunda.status_code == 400, "el enlace del correo sirve mas de una vez"


# ---------------------------------------------------------------------------
# CASO 03 -- "Registrarse y llegar al cuestionario inicial. Espero: no deja saltar al plan
#            sin completarlo."
# ---------------------------------------------------------------------------

class TestCaso03DelRegistroAlCuestionario:

    def test_al_registrarse_el_cuestionario_queda_por_hacer(self, api_disponible, alta):
        persona = alta("Nuria Prueba")
        r = requests.get(f"{API}/clients/profile", headers=persona["cabeceras"], timeout=30)
        assert r.status_code == 200, "el que acaba de registrarse no tiene ficha"
        ficha = r.json()
        assert not ficha.get("questionnaire_completed"), (
            "la ficha nace con el cuestionario ya dado por hecho")
        assert ficha.get("status") == "registrado", (
            f"la ficha nace en '{ficha.get('status')}' y no en 'registrado': una ficha "
            "registrada no da acceso a nada de pago, y ese es el cerrojo")
        assert not ficha.get("plan"), "la ficha nace con un plan puesto sin haber pagado"

    def test_el_panel_devuelve_al_cuestionario_a_quien_no_lo_ha_hecho(self, api_disponible):
        """Quien ha contratado y no ha rellenado el cuestionario no puede quedarse en el
        panel: el panel lo devuelve. Es lo que impide saltarselo escribiendo /dashboard."""
        dash = fuente("pages/ClientDashboard.jsx")
        i = dash.find("navigate('/questionnaire', { replace: true })")
        assert i > 0, "el panel ya no devuelve al cuestionario a quien no lo ha completado"
        condicion = dash[max(0, i - 300):i]
        assert "questionnaire_completed" in condicion, (
            "el panel manda al cuestionario sin mirar si ya esta hecho")

    def test_el_cuestionario_esta_detras_de_la_sesion(self, api_disponible):
        r = requests.post(f"{API}/clients/questionnaire",
                          json={"goal": "definicion", "weight": 80, "body_fat": 18}, timeout=30)
        assert r.status_code in (401, 403), "el cuestionario inicial se responde sin sesion"


# ---------------------------------------------------------------------------
# CASO 04 [CRITICO] -- "Terminar el cuestionario. Espero: la bienvenida ensena los macros
#                      calculados y el nombre real de la persona, no la palabra 'cliente'."
# ---------------------------------------------------------------------------

def _alta_pagada(mongo, persona, plan="nivel1"):
    """Deja a la persona como queda despues de contratar, que es cuando se le pide el
    cuestionario inicial.

    Se escribe el plan y el estado directamente en la ficha en vez de pasar por Stripe, y se
    hace exactamente lo mismo que hace el checkout real (`ensure_checkout_profile` +
    activacion): tocar `plan` y `status`. En concreto NO se toca `week`, porque el checkout
    tampoco lo toca -- la ficha ya existe desde el registro y esa rama del codigo solo
    actualiza plan, precio y estado.
    """
    mongo.client_profiles.update_one({"user_id": persona["user_id"]},
                                     {"$set": {"plan": plan, "status": "activo"}})


@pytest.fixture(scope="module")
def recien_dado_de_alta(alta, mongo):
    """Una persona con su plan contratado y el cuestionario inicial recien enviado."""
    persona = alta("Marcos Prueba")
    _alta_pagada(mongo, persona)
    persona["respuesta"] = requests.post(
        f"{API}/clients/questionnaire", headers=persona["cabeceras"],
        json={"name": "Marcos Prueba", "goal": "definicion", "sex": "hombre",
              "weight": 80.0, "body_fat": 18.0, "height": 178.0},
        timeout=60)
    return persona


class TestCaso04LaBienvenidaTrasElCuestionario:

    def test_terminar_el_cuestionario_no_da_error(self, recien_dado_de_alta):
        r = recien_dado_de_alta["respuesta"]
        assert r.status_code == 200, (
            f"terminar el cuestionario inicial devuelve {r.status_code}. Lo que ve la persona "
            "es «Error al enviar el cuestionario» al final del alta, y ademas no se le puede "
            "volver a pasar (el segundo intento da 409)")

    def test_la_bienvenida_tiene_macros_que_ensenar(self, recien_dado_de_alta):
        """La pantalla de bienvenida pinta `profile.macros_training`; si viene vacio lo que
        sale es «Estamos terminando de calcular tus macros», que es el caso 04 sin cumplir."""
        r = requests.get(f"{API}/clients/profile", headers=recien_dado_de_alta["cabeceras"],
                         timeout=30)
        assert r.status_code == 200
        macros = r.json().get("macros_training") or {}
        proteina = macros.get("protein") or macros.get("proteinas") or 0
        assert proteina > 0, ("al terminar el cuestionario la ficha se queda sin macros: la "
                              "bienvenida no tiene nada que ensenar")

    def test_la_bienvenida_saluda_con_el_nombre_de_la_persona(self, recien_dado_de_alta):
        r = requests.get(f"{API}/auth/me", headers=recien_dado_de_alta["cabeceras"], timeout=30)
        assert r.status_code == 200
        nombre = (r.json().get("name") or "").strip()
        assert nombre == "Marcos Prueba", f"el nombre guardado es «{nombre}»"
        assert nombre.lower() != "cliente"

    def test_la_pantalla_de_bienvenida_no_llama_cliente_a_nadie(self, api_disponible):
        pantalla = fuente("pages/WelcomePage.jsx")
        assert "user?.name" in pantalla, "la bienvenida ya no saluda por el nombre"
        assert "'Cliente'" not in pantalla and '"Cliente"' not in pantalla, (
            "la bienvenida tiene «Cliente» de repuesto: si el nombre falta, saluda a una "
            "etiqueta en vez de a una persona")
        assert "macros_training" in pantalla, "la bienvenida ya no ensena los macros"

    def test_el_cuestionario_del_alta_no_se_repite(self, recien_dado_de_alta):
        """El alta se rellena una vez. Importa aqui porque es lo que hace grave cualquier
        fallo del envio: si el primer intento se guarda a medias, no hay segundo."""
        r = requests.post(f"{API}/clients/questionnaire",
                          headers=recien_dado_de_alta["cabeceras"],
                          json={"goal": "definicion", "sex": "hombre",
                                "weight": 80.0, "body_fat": 18.0},
                          timeout=30)
        assert r.status_code == 409, f"el cuestionario del alta se puede repetir ({r.status_code})"


# ---------------------------------------------------------------------------
# CASO 05 [CRITICO] -- "Entrar en /planes sin plan. Espero: salen los tres niveles y la
#                      membresia. El Nivel 3 con «Agendar una llamada», nunca con boton de
#                      pagar."
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def catalogo(api_disponible):
    """Los planes que se pueden contratar hoy, tal y como los lee la pantalla."""
    r = requests.get(f"{API}/plans?estado=activo", timeout=30)
    assert r.status_code == 200, "el catalogo de planes no responde"
    return r.json()


class TestCaso05LaPantallaDePlanes:

    def test_el_catalogo_trae_los_cinco_activos(self, catalogo):
        """Doc 19-08: «son cinco los que se venden, no cuatro». La «Membresía» vacía se
        borró (fallo 04): la membresía ES El Lunes Empiezo."""
        for code in ("nivel1", "nivel2", "nivel3", "elm", "mantenimiento"):
            assert code in catalogo, f"«{code}» no esta entre los planes activos"

    def test_en_la_pantalla_salen_los_tres_niveles(self, api_disponible):
        planes = fuente("pages/PlanesPage.jsx")
        m = re.search(r"const ORDEN = \[([^\]]*)\]", planes)
        assert m, "no se puede leer que planes pinta /planes"
        pintados = re.findall(r"'([^']+)'", m.group(1))
        for code in ("nivel1", "nivel2", "nivel3"):
            assert code in pintados, f"/planes no ensena «{code}»"

    def test_la_membresia_no_sale_en_la_pantalla_de_planes(self, api_disponible, catalogo):
        """Caso 05, DESEMPATADO POR JESUS el 13-08-2026.

        El caso pedia «los tres niveles y la membresia», y el codigo la escondia a proposito
        («es la salida del que no renueva, no algo que se compre»). Se dejo en rojo esperando
        a que el decidiera, y decidio que NO sale, con su motivo:

            «El Nivel 1 es tu puerta de entrada. Una membresia mas barata al lado se lo come:
            el que iba a pagar 297 paga la membresia y se queda ahi. Es para quien ya ha
            terminado un ciclo y quiere quedarse con la app, no para quien llega de la calle.»

        Sigue activa en el catalogo y marcada `solo_salida`: se vende, pero no desde aqui.
        """
        assert catalogo.get("elm", {}).get("estado") == "activo"
        planes = fuente("pages/PlanesPage.jsx")
        pintados = re.findall(r"'([^']+)'", re.search(r"const ORDEN = \[([^\]]*)\]", planes).group(1))
        # Desde el 19-08 la membresía es ELM: la decisión de Jesús aplica igual a él.
        assert "membresia" not in pintados and "elm" not in pintados, (
            "/planes ensena la membresia al lado de los niveles, y Jesus decidio que no: "
            "se come la entrada del Nivel 1")

    def test_el_nivel3_se_agenda_por_llamada(self, api_disponible):
        planes = fuente("pages/PlanesPage.jsx")
        bloque_nivel3 = planes[planes.index("nivel3: {"):planes.index("const Si =")]
        assert "porLlamada: true" in bloque_nivel3, "el Nivel 3 ya no esta marcado como de llamada"

        i = planes.index("if (plan.porLlamada)")
        rama = planes[i:planes.index("</button>", i)]
        assert "Agendar una llamada" in rama, "el boton del Nivel 3 no dice «Agendar una llamada»"
        assert "comprar(" not in rama, "el boton del Nivel 3 abre un pago"

    def test_desde_la_app_no_se_puede_abrir_un_cobro_del_nivel3(self, api_disponible, alta):
        """«Nunca con boton de pagar». En la pantalla no lo hay, pero el endpoint de cobro no
        distingue: con la sesion de cualquier cliente, POST /billing/checkout-session con
        plan nivel3 devuelve una URL de pago de Stripe. El enlace del Nivel 3 lo genera el
        equipo despues de la llamada (por la ficha del lead), no el propio cliente.
        """
        persona = alta("Alvaro Prueba")
        r = requests.post(f"{API}/billing/checkout-session", headers=persona["cabeceras"],
                          json={"plan": "nivel3", "success_path": "/planes",
                                "cancel_path": "/planes"},
                          timeout=60)
        assert not (r.status_code == 200 and r.json().get("checkout_url")), (
            "el cliente puede abrirse el pago del Nivel 3 el solo, sin la llamada")


# ---------------------------------------------------------------------------
# CASO 06 -- "Abrir una direccion que no existe con la sesion iniciada. Espero: no echa al
#            login, deja al cliente donde esta."
# ---------------------------------------------------------------------------

class TestCaso06LasDireccionesQueNoExisten:

    def test_el_comodin_no_manda_al_login_a_quien_ya_esta_dentro(self, api_disponible):
        app = fuente("App.js")
        m = re.search(r'path="\*"\s+element=\{([^}]*)\}', app)
        assert m, "ya no hay comodin para las direcciones que no existen"
        assert "ADondeSea" in m.group(1), (
            f"el comodin pinta {m.group(1).strip()}: si eso es un Navigate a /auth, un enlace "
            "roto echa de la app a un cliente con la sesion abierta")

        i = app.index("const ADondeSea")
        cuerpo = app[i:app.index("};", i)]
        assert "if (!isAuthenticated) return <Navigate to=\"/auth\"" in cuerpo, (
            "al login solo puede ir el que no ha entrado")
        assert "'/dashboard'" in cuerpo and "'/admin'" in cuerpo, (
            "al que ya esta dentro no se le deja en su sitio")

    def test_una_ruta_de_api_que_no_existe_no_cierra_la_sesion(self, api_disponible,
                                                               cabeceras_cliente):
        r = requests.get(f"{API}/esta-ruta-no-existe-{uuid.uuid4().hex[:6]}",
                         headers=cabeceras_cliente, timeout=30)
        assert r.status_code == 404, (
            f"una direccion que no existe responde {r.status_code}: con un 401 el frontend "
            "cierra la sesion y devuelve al login")
        yo = requests.get(f"{API}/auth/me", headers=cabeceras_cliente, timeout=30)
        assert yo.status_code == 200, "despues del 404 la sesion ha dejado de valer"


# ---------------------------------------------------------------------------
# CASO 07 [CRITICO] -- "Abrir el login en un movil de 390 px. Espero: el banner de «Instala
#                      12EN12» no tapa el boton de Entrar."
# ---------------------------------------------------------------------------

class TestCaso07ElBannerDeInstalar:

    def test_el_banner_no_se_pinta_en_las_pantallas_de_acceso(self, api_disponible):
        """La unica forma segura de que no tape el boton de Entrar es que ahi no exista.

        Este test existe porque el arreglo ya se escribio una vez a medias: quedaron la lista
        `FUERA_DE` y la variable `enPantallaDeAcceso`, pero la condicion nunca se aplico, asi
        que el fallo siguio vivo con toda la pinta de estar resuelto.
        """
        banner = fuente("components/InstallPrompt.jsx")

        m = re.search(r"const FUERA_DE = \[([^\]]*)\]", banner)
        assert m, "ya no existe la lista de pantallas donde el banner no se ensena"
        fuera = re.findall(r"'([^']+)'", m.group(1))
        assert "/auth" in fuera, "la pantalla de acceso no esta en la lista de excluidas"
        assert "/recuperar" in fuera, "la de recuperar la contrasena tampoco"

        visible = re.search(r"const visible = (.+);", banner)
        assert visible, "ya no se decide en un sitio si el banner se ve"
        assert "enPantallaDeAcceso" in visible.group(1), (
            "la lista FUERA_DE esta escrita pero no se usa para decidir si el banner se ve: "
            "en el movil el banner vuelve a taparle el boton de Entrar")

    @pytest.mark.skip(reason="visual: hay que mirarlo con los ojos, ver informe")
    def test_a_390_px_el_boton_de_entrar_se_puede_pulsar(self):
        """Que un elemento tape a otro depende de la altura real de la pantalla, de la fuente
        y del teclado del movil: eso no se mide desde pytest sin un navegador de verdad.
        Lo que si se puede fijar aqui es la causa (el test de arriba). La comprobacion a 390 px
        va con la extension del navegador o con los scripts de Playwright de _guia/.
        """
