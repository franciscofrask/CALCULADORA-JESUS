# -*- coding: utf-8 -*-
"""
Bloque 7 del doc de Jesus del 23-08 («La app - todo lo que esta mal»): suplementos.

    P34. Se podian pautar suplementos marcados «NO USAR» o «Suplemento obsoleto»: la
         importacion de la guia los dejo con activo=True y el selector del panel los
         ofrecia. El saneo de DATOS (_sanear_catalogo_suplementos.py) los apaga, pero
         el endpoint ya no se fia de que haya corrido: el selector filtra por si mismo.

Lo que se prueba, contra la API viva y con recursos DE PRUEBA propios (se crean y se
apagan al salir, como en test_panel_candados_2308):

  1. El selector (GET /admin/supplements/catalog sin parametros) no ofrece una ficha
     con «NO USAR» u «obsoleto» en el titulo AUNQUE este activa en la base.
  2. La pagina del catalogo (include_inactive=true) SI la ensena: ahi es donde el
     equipo la apaga o la arregla.
  3. Un cliente que YA tiene una de esas fichas en su protocolo la sigue viendo: el
     protocolo guarda su propio snapshot y el filtro del selector no lo toca.
  4. El /suggest tampoco la propone, que proponer tambien es ofrecer.
"""
import sys
import uuid
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conftest import API


def pedir(metodo, ruta, **kw):
    kw.setdefault("timeout", 30)
    return getattr(requests, metodo)(f"{API}{ruta}", **kw)


def json_ok(r, donde):
    assert r.status_code == 200, f"{donde}: {r.status_code} {r.text[:200]}"
    return r.json()


def titulos(items):
    return [i.get("titulo") for i in items]


@pytest.fixture()
def ficha_no_usar(cabeceras_admin):
    """Una ficha ACTIVA con la marca en el titulo, como las que dejo la importacion.
    Se crea para la prueba y se apaga al salir (no hay borrado fisico, igual que en
    el resto del catalogo)."""
    item = {
        "titulo": f"TEST P34 creatina vieja - NO USAR {uuid.uuid4().hex[:8]}",
        "cuando": "nunca, es de prueba", "cuanto": "0 g",
        "categoria": "guia", "activo": True,
    }
    creado = json_ok(pedir("post", "/admin/supplements/catalog",
                           headers=cabeceras_admin, json=item),
                     "/admin/supplements/catalog (alta de prueba)")
    item["id"] = creado["id"]
    yield item
    r = pedir("delete", f"/admin/supplements/catalog/{item['id']}", headers=cabeceras_admin)
    assert r.status_code == 200, "no se pudo apagar la ficha de prueba al recoger"


def test_el_selector_no_ofrece_no_usar_aunque_este_activa(cabeceras_admin, ficha_no_usar):
    """El corazon del P34: la ficha esta ACTIVA en la base (el saneo de datos aun no ha
    pasado por ella) y aun asi el selector no la ofrece."""
    selector = json_ok(pedir("get", "/admin/supplements/catalog", headers=cabeceras_admin),
                       "selector")
    assert ficha_no_usar["titulo"] not in titulos(selector), (
        "el selector sigue ofreciendo una ficha «NO USAR» activa")


def test_el_selector_tampoco_ofrece_obsoletas_ni_apagadas(cabeceras_admin):
    """Lo que el selector devuelve hoy, sea cual sea el estado de la base: ni apagadas
    ni marcas de texto («NO USAR», «obsoleto») en ninguna de sus fichas."""
    selector = json_ok(pedir("get", "/admin/supplements/catalog", headers=cabeceras_admin),
                       "selector")
    apagadas = [t for i, t in zip(selector, titulos(selector)) if i.get("activo") is not True]
    assert not apagadas, f"el selector ofrece fichas apagadas: {apagadas[:5]}"
    sucias = [t for t in titulos(selector)
              if "no usar" in (t or "").lower() or "obsolet" in (t or "").lower()]
    assert not sucias, f"el selector ofrece fichas marcadas en el titulo: {sucias[:5]}"


def test_la_pagina_del_catalogo_la_sigue_viendo(cabeceras_admin, ficha_no_usar):
    """include_inactive=true es la vista de curar: la ficha marcada tiene que salir ahi,
    que para apagarla o arreglarla primero hay que poder verla."""
    todo = json_ok(pedir("get", "/admin/supplements/catalog?include_inactive=true",
                         headers=cabeceras_admin), "catalogo entero")
    assert ficha_no_usar["titulo"] in titulos(todo), (
        "la pagina del catalogo ya no ve la ficha marcada: asi no hay quien la cure")


def test_suggest_no_propone_fichas_marcadas(cabeceras_admin, ficha_no_usar):
    """Proponer tambien es ofrecer: el arranque que el panel compone para un cliente
    no puede traer una ficha marcada, aunque este activa."""
    lista = json_ok(pedir("get", "/admin/clients", headers=cabeceras_admin), "/admin/clients")
    fila = next((c for c in lista if c.get("id")), None)
    if not fila:
        pytest.skip("no hay clientes en la base de dev")
    propuesta = json_ok(pedir("post", f"/admin/supplements/suggest?client_id={fila['id']}",
                              headers=cabeceras_admin), "/suggest")
    marcadas = [i.get("titulo") for i in (propuesta.get("actual") or [])
                if "no usar" in (i.get("titulo") or "").lower()
                or "obsolet" in (i.get("titulo") or "").lower()]
    assert not marcadas, f"el /suggest propone fichas marcadas: {marcadas}"


def test_un_protocolo_ya_asignado_con_una_marcada_se_sigue_sirviendo(
        cabeceras_admin, cabeceras_cliente, ficha_no_usar):
    """El punto 3 del P34: filtrar el selector no puede romper a quien YA la tiene
    pautada. Se le anade la ficha marcada al protocolo del cliente demo, se comprueba
    que el la ve, y se deja todo como estaba."""
    lista = json_ok(pedir("get", "/admin/clients", headers=cabeceras_admin), "/admin/clients")
    # El email va dentro de `user` en la lista del panel, no en la fila.
    fila = next((c for c in lista
                 if ((c.get("user") or {}).get("email") or "").lower() == "clientedemo@test.com"), None)
    if not fila:
        pytest.skip("clientedemo@test.com no esta en esta base")
    client_id = fila["id"]

    # La foto de ANTES, para restaurar exactamente lo que habia.
    antes = json_ok(pedir("get", "/supplements/current", headers=cabeceras_cliente),
                    "/supplements/current (antes)")
    items_antes = antes.get("actual") or []
    fecha_antes = antes.get("actual_fecha")

    snapshot = {
        "catalog_id": ficha_no_usar["id"], "titulo": ficha_no_usar["titulo"],
        "cuando": ficha_no_usar["cuando"], "cuanto": ficha_no_usar["cuanto"],
    }
    guardado = json_ok(pedir("post", f"/admin/supplements/save?client_id={client_id}",
                             headers=cabeceras_admin,
                             json={"actual": items_antes + [snapshot]}),
                       "/admin/supplements/save")
    fecha_puesta = guardado.get("actual_fecha")
    try:
        despues = json_ok(pedir("get", "/supplements/current", headers=cabeceras_cliente),
                          "/supplements/current (despues)")
        assert ficha_no_usar["titulo"] in [i.get("titulo") for i in (despues.get("actual") or [])], (
            "el cliente ya no ve una ficha que tiene pautada: el filtro del selector "
            "se ha comido el protocolo")
    finally:
        # Se deja el protocolo como estaba: la misma version con sus items de antes, o
        # borrando la version si antes no habia ninguna en esa fecha.
        if items_antes and fecha_antes == fecha_puesta:
            json_ok(pedir("post", f"/admin/supplements/save?client_id={client_id}",
                          headers=cabeceras_admin,
                          json={"actual": items_antes, "actual_fecha": fecha_antes,
                                "nota": antes.get("nota")}),
                    "restaurar el protocolo")
        else:
            r = pedir("delete", f"/admin/supplements/version/{fecha_puesta}?client_id={client_id}",
                      headers=cabeceras_admin)
            assert r.status_code == 200, f"no se pudo recoger la version de prueba: {r.status_code}"
