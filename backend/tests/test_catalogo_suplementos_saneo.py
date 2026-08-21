# -*- coding: utf-8 -*-
"""El catálogo de suplementos del panel, sin basura ni duplicados (tarea 2.2, 21-08).

Lo que pasó: el volcado de la guía a `supplement_catalog` casaba solo por id, nunca por
título, así que cada semilla que ya existía salió otra vez con categoría "guia", y fichas
tituladas «NO USAR» u «obsoleto» quedaron elegibles en el selector del coach.

Aquí se prueba lo que lo cierra:
  - la normalización de títulos del script de saneo (función pura),
  - el filtro del endpoint: el selector (sin parámetros) no ofrece fichas apagadas; las
    de la guía LEGÍTIMAS siguen siendo elegibles (para eso se volcaron, bloque 08 del
    doc 19-08) porque la limpieza va por DATOS: el saneo desactiva duplicados y basura,
  - la página del catálogo (include_inactive=true) lo sigue viendo todo, que para curar
    una ficha primero hay que poder verla,
  - y el estado de la base tras el saneo: sin basura activa y sin duplicados activos.
"""
import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _sanear_catalogo_suplementos import es_basura, titulo_normalizado

from conftest import API


# ── La normalización, que es la llave del desduplicado y de la idempotencia ──

def test_normalizar_iguala_mayusculas_tildes_y_espacios():
    assert titulo_normalizado("  Proteína   WHEY  ") == "proteina whey"
    assert titulo_normalizado("PROTEINA WHEY") == titulo_normalizado("Proteína Whey")
    assert titulo_normalizado("Omega-3\t1000 mg") == "omega-3 1000 mg"


def test_normalizar_aguanta_vacios_y_none():
    assert titulo_normalizado(None) == ""
    assert titulo_normalizado("   ") == ""


def test_titulos_distintos_no_se_confunden():
    assert titulo_normalizado("Creatina monohidrato") != titulo_normalizado("Creatina HCL")


def test_la_basura_se_reconoce_por_el_titulo():
    assert es_basura("Suplemento obsoleto")
    assert es_basura("NIACINA FLUSH FREE 3 tomas - NO USAR")
    assert es_basura("niacina no usar")  # da igual cómo venga escrito
    assert not es_basura("Creatina monohidrato")
    assert not es_basura(None)


# ── El endpoint del panel ────────────────────────────────────────────────────

def _catalogo(cabeceras, sufijo=""):
    r = requests.get(f"{API}/admin/supplements/catalog{sufijo}", headers=cabeceras, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def test_el_selector_solo_ofrece_activas(cabeceras_admin):
    """Sin parámetros es lo que ve el coach al pautar: solo fichas activas. La guía
    activa SÍ entra (la limpieza de duplicados y basura va por datos, no por categoría)."""
    items = _catalogo(cabeceras_admin)
    assert items, "el selector se quedó vacío: sin catálogo no hay nada que pautar"
    apagadas = [i["titulo"] for i in items if i.get("activo") is not True]
    assert not apagadas, f"el selector ofrece fichas apagadas: {apagadas[:5]}"


def test_el_selector_no_ofrece_obsoletos_ni_no_usar(cabeceras_admin):
    """La queja literal de la tarea: «Suplemento obsoleto» y «... - NO USAR» elegibles."""
    sucias = [i["titulo"] for i in _catalogo(cabeceras_admin) if es_basura(i.get("titulo"))]
    assert not sucias, f"el selector sigue ofreciendo basura: {sucias[:5]}"


def test_la_pagina_del_catalogo_lo_sigue_viendo_todo(cabeceras_admin):
    """`include_inactive=true` es la vista de curar: la guía y las apagadas tienen que
    salir ahí, porque para desactivar una ficha primero hay que poder verla."""
    todo = _catalogo(cabeceras_admin, "?include_inactive=true")
    assert len(todo) >= len(_catalogo(cabeceras_admin))
    if not any(i.get("categoria") == "guia" for i in todo):
        pytest.skip("esta base no tiene fichas de la guía volcadas: nada que comprobar")


def test_tras_el_saneo_ninguna_guia_activa_duplica_una_semilla(cabeceras_admin):
    """El estado que deja _sanear_catalogo_suplementos.py: si una ficha de "guia" repite
    el título de una semilla, la de "guia" está apagada."""
    todo = _catalogo(cabeceras_admin, "?include_inactive=true")
    semillas = {titulo_normalizado(i.get("titulo")) for i in todo if i.get("categoria") != "guia"}
    if not any(i.get("categoria") == "guia" for i in todo):
        pytest.skip("esta base no tiene fichas de la guía volcadas: nada que comprobar")
    vivas = [i["titulo"] for i in todo
             if i.get("categoria") == "guia" and i.get("activo") is not False
             and titulo_normalizado(i.get("titulo")) in semillas]
    assert not vivas, f"duplicados de la guía todavía activos: {vivas[:5]}"
