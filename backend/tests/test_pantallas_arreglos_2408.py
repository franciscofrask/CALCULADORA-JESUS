# -*- coding: utf-8 -*-
"""Fallos 11 y 12 de la verificacion del 24-08: dos pantallas que se contradecian solas.

  11  LA FICHA DEL CLIENTE DE CORTESIA. El aviso del punto 43 solo miraba la diferencia
      entre el precio de la ficha y el ultimo cobro, y no preguntaba por la cortesia. En la
      ficha de Andres Cano Corpas se leia «Cortesia», «0,00 EUR/mes para el negocio» y justo
      debajo «La ficha dice 0,00 EUR por ciclo y lo ultimo que se le cobro fueron 291,01
      EUR». El codigo hace lo contrario de lo que decia el aviso: `importe_de_ciclo`
      devuelve 0 y «cortesia» ANTES de mirar nada mas, o sea que ese 0 es una decision
      tomada. Eran 7 fichas en produccion.

  12  LAS PESTAÑAS DE LA LISTA DE CLIENTES. Al llevar los registros sin terminar a «Fuera»
      -- lo que pidio Jesus el 24-08 --, «Fuera» empezo a contarlos y «Todos» no: «Activos
      (92) · Fuera (71) · Todos (105)», y 92 + 71 no son 105. Peor: «Todos» decia 105 y su
      tabla enseñaba 163 filas. Ahora las tres cuentan con el MISMO criterio con el que se
      filtra la tabla (`esDelAcceso`), asi que Activos y Fuera son las dos mitades disjuntas
      de Todos y suman por construccion.

Los dos arreglos son de pantalla, asi que aqui se protege lo que se puede proteger sin
navegador: que el codigo de la pantalla siga preguntando por la cortesia antes de avisar de
dinero, que las tres pestañas sigan contando por un solo sitio, y que el caso real que lo
destapo (una ficha de cortesia con un cobro antiguo detras) siga existiendo y siga saliendo
del servidor tal cual. La comprobacion visual se hizo con _guia/_repro_11_12_2408.js y
_guia/_repro_12_2408.js contra la app de dev.
"""
import os
import pathlib
import sys

import pytest
import requests

sys.path.insert(0, os.path.dirname(__file__))
from conftest import corre  # noqa: E402

from routes.admin import euros_al_mes, importe_de_ciclo  # noqa: E402

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"
FRONT = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src"

CAT = {
    "gold": {"ciclo": {"tipo": "trimestral", "semanas": 12}, "billing_cycle_weeks": 12,
             "precio": 900, "renovacion": {"automatica": True}},
}


def fuente(relativo: str) -> str:
    return (FRONT / relativo).read_text(encoding="utf-8")


def _trozo(src: str, desde: str, hasta: str) -> str:
    """El cacho de JSX entre dos marcas. Sirve para mirar UN bloque y no el fichero."""
    a = src.index(desde)
    b = src.index(hasta, a)
    return src[a:b]


# ==================== 11 · la cortesia manda sobre el aviso ====================


class TestLaFichaDeCortesiaNoSeContradice:
    def test_para_el_negocio_el_de_cortesia_cuenta_cero_aunque_pagara_antes(self):
        """La premisa del arreglo: el codigo ya decidia esto, y la pantalla lo negaba."""
        perfil = {"plan": "gold", "comp_plan": True, "price": 0}
        cobro = {"importe": 291.01, "fecha": "2026-05-04", "origen": "stripe"}
        assert importe_de_ciclo(perfil, CAT, cobro) == (0.0, "cortesia")
        assert euros_al_mes(perfil, CAT, cobro) == 0.0

    def test_el_aviso_de_descuadre_pregunta_primero_por_la_cortesia(self):
        """Que el aviso viva DENTRO de la rama de «no es cortesia», no al lado.

        Si alguien vuelve a sacar `cobro-no-cuadra` fuera de ese if, este test se pone rojo:
        es exactamente la regresion del 24-08.
        """
        bloque = _trozo(fuente("pages/ClientDetailPage.jsx"),
                        'data-testid="cobro-real"', 'data-testid="renovacion-ficha"')
        assert "cobro-no-cuadra" in bloque
        assert bloque.index("precio_cortesia ?") < bloque.index("cobro-no-cuadra"), \
            "el aviso de descuadre tiene que ir detras de la pregunta por la cortesia"

    def test_al_de_cortesia_se_le_explica_el_cero_en_vez_de_avisarle(self):
        bloque = _trozo(fuente("pages/ClientDetailPage.jsx"),
                        'data-testid="cobro-real"', 'data-testid="renovacion-ficha"')
        assert "cortesia-explicada" in bloque
        assert "plan de cortesía" in bloque  # al lado del «0,00 €/mes para el negocio»

    def test_la_cortesia_con_stripe_vivo_si_se_avisa(self):
        """Lo unico que de verdad hay que mirar en una cortesia: que Stripe siga cobrando.

        Ahi el 0 del panel si es mentira (`importe_de_ciclo` corta en la cortesia y no suma
        ese dinero). Hoy en produccion no le pasa a ninguno, y por eso conviene que salte el
        dia que pase.
        """
        bloque = _trozo(fuente("pages/ClientDetailPage.jsx"),
                        'data-testid="cobro-real"', 'data-testid="renovacion-ficha"')
        assert "cortesia-con-stripe" in bloque
        assert "renueva_solo?.via === 'stripe'" in bloque

    def test_a_la_cortesia_no_se_le_dice_que_hay_que_pedirle_el_pago(self):
        """El mismo fallo, dos lineas mas abajo: «la renovacion la confirma el» es lo que se
        lee justo antes de llamar a alguien a pedirle dinero. A este no hay que pedirle
        nada."""
        src = fuente("pages/ClientDetailPage.jsx")
        assert "renovacion-cortesia" in src
        bloque = _trozo(src, 'data-testid="renovacion-ficha"', "CicloDelCliente")
        assert bloque.index("precio_cortesia") < bloque.index("La renovación la confirma él")


class TestLaFichaDeCortesiaDeVerdad:
    """El caso real, contra el servidor: la ficha de cortesia con un cobro antiguo detras.

    Si esto deja de existir el arreglo sigue bien, pero el test se salta con motivo en vez
    de dar por bueno un caso que ya nadie ejerce.
    """

    def _una_de_cortesia_con_cobro(self):
        async def buscar():
            from core.database import db
            async for p in db.client_profiles.find({"comp_plan": True}).limit(80):
                u = await db.users.find_one({"id": p.get("user_id")}) or {}
                email = (u.get("email") or "").lower().strip()
                if not email:
                    continue
                cobro = await db.pagos_historicos.find_one(
                    {"email": email, "importe": {"$gt": 0},
                     "duplicado_de": {"$in": [None, ""]}, "es_dinero": {"$ne": False}})
                if cobro:
                    return p.get("id"), u.get("name"), cobro.get("importe")
            return None
        return corre(buscar())

    def test_el_servidor_manda_la_cortesia_y_el_cobro_viejo_juntos(self, cabeceras_admin):
        caso = self._una_de_cortesia_con_cobro()
        if not caso:
            pytest.skip("No hay ninguna ficha de cortesia con cobros antiguos en esta base.")
        client_id, nombre, importe = caso
        r = requests.get(f"{API}/admin/clients/{client_id}", headers=cabeceras_admin, timeout=60)
        assert r.status_code == 200, r.text
        perfil = r.json().get("profile") or {}
        # Los tres ingredientes del fallo 11, tal cual salen del servidor.
        assert perfil.get("precio_cortesia") is True
        assert perfil.get("ultimo_cobro") and perfil["ultimo_cobro"]["importe"] > 0
        assert perfil.get("euros_al_mes") == 0, \
            f"{nombre} es de cortesia: para el negocio cuenta 0, no {perfil.get('euros_al_mes')}"


# ==================== 12 · las pestañas suman ====================


class TestLasPestanasDeClientesSuman:
    def test_las_tres_cuentan_por_el_mismo_sitio(self):
        """«Un solo criterio, y si algun dia cambia, cambia en un sitio»
        (frontend/src/lib/cuentaClientes.js). La cuenta de la pestaña y el filtro de la
        tabla tienen que salir de la MISMA funcion: cuando fueron dos, dejaron de sumar."""
        src = fuente("pages/AdminDashboard.jsx")
        assert "const esDelAcceso = (c, cual)" in src
        assert "const delAcceso = (c) => esDelAcceso(c, acceso);" in src
        cuenta = _trozo(src, "const cuantosAcceso", "const ACCESOS")
        assert "esDelAcceso(c, cual)" in cuenta
        # La regresion en una linea: «Todos» contaba clientes y «Fuera» contaba filas.
        assert "cuentaComoCliente" not in cuenta, \
            "«Todos» no puede contar con otro criterio que «Activos» y «Fuera»"

    def test_activos_y_fuera_son_las_dos_mitades_de_todos(self):
        """Por construccion: una fila esta fuera o no lo esta, no hay tercera opcion."""
        src = fuente("pages/AdminDashboard.jsx")
        cuerpo = _trozo(src, "const esDelAcceso", "const filteredClients")
        assert "cual === 'todos' ? true" in cuerpo
        assert "cual === 'activos' ? !estaFuera(c) : estaFuera(c)" in cuerpo

    def test_los_sin_plan_siguen_en_fuera(self):
        """Jesus, 24-08: «a los que no tienen plan sacalos de la lista, ponlos en otro lado;
        a los caducados tambien, ambos en la misma lista». El arreglo de los numeros no
        podia devolverlos a «Activos»."""
        src = fuente("pages/AdminDashboard.jsx")
        assert ("const estaFuera = (c) => c.status === 'registro_incompleto' "
                "|| !c.plan || !tieneAcceso(c);") in src

    def test_se_dice_al_lado_por_que_las_pestanas_suman_mas_que_el_total(self):
        """Los numeros de las pestañas se leen antes que ninguna frase, asi que la
        diferencia con el total de clientes se explica debajo de las pestañas y con los
        numeros calculados, no clavados a mano."""
        src = fuente("pages/AdminDashboard.jsx")
        assert "cuadre-pestanas" in src
        nota = _trozo(src, 'data-testid="cuadre-pestanas"', "</p>")
        assert "sinTerminarEnVista" in nota
        assert "cuantosAcceso('todos')" in nota
        for cifra in ("92", "71", "105", "163", "58"):
            assert cifra not in nota, "nada de cifras medidas un martes y clavadas en el texto"
