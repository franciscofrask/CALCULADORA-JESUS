# -*- coding: utf-8 -*-
"""Los avisos del reporte por correo (P58 y P59 del doc del 23-08).

P59: la pasada de correos respeta el interruptor (apagada no toca nada), manda UNA
vez por clave de aviso (el índice único decide la carrera entre réplicas) y deja el
correo en `db.correos_pendientes` (en dev no hay SMTP: queda 'sin_enviar', que es la
prueba de qué habría salido).

P58: el «llevas N semanas con los mismos macros» se topa en 12; el aviso solo existe
para quien tiene ajuste incluido (eso ya estaba y se re-fija aquí).

Se prueban las funciones directamente (asyncio.run + Mongo de dev), sin HTTP: la
pasada es un bucle de fondo, no una ruta.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.avisos_cliente import avisos_condicionados      # noqa: E402
from core.database import db                              # noqa: E402


# UN solo bucle, y el de TODA la bateria (tests/conftest.py), no uno de este fichero: el
# cliente de Mongo (motor) queda atado al primero que lo usa, asi que dos ficheros con
# bucle propio se pisan. Solo o en tanda pequeña no se nota; el 24-08 estos tres tests
# empezaron a fallar al lanzar la bateria entera junto a otro fichero que hacia lo mismo.
from conftest import corre as correr  # noqa: E402


# ── P58: el tope del número ──────────────────────────────────────────────────

def _sin_ajustar(semanas):
    ahora = datetime.now(timezone.utc)
    avisos = avisos_condicionados(
        ahora=ahora, semanas_sin_ajustar=semanas, reporte_sin_fotos=False,
        faltan_fotos_o_medidas=None, dias_sin_cerrar=0, dias_sin_entrar=0,
        dias_con_el_perfil_a_medias=None, dias_sin_preferencias=None,
        dias_en_mantenimiento=None, rutina_mes_aplazada_hasta=None, con_ajuste=True)
    return [a for a in avisos if a["familia"] == "sin_ajustar"]


def test_58_hasta_doce_semanas_el_numero_va_tal_cual():
    aviso = _sin_ajustar(5)[0]
    assert aviso["variantes"][0]["titulo"] == "Llevas 5 semanas con los mismos macros"


def test_58_pasado_el_ciclo_el_numero_se_topa():
    aviso = _sin_ajustar(133)[0]
    assert aviso["variantes"][0]["titulo"] == "Llevas más de 12 semanas con los mismos macros"
    assert "133" not in str(aviso)


def test_58_sin_ajuste_incluido_no_hay_aviso():
    ahora = datetime.now(timezone.utc)
    avisos = avisos_condicionados(
        ahora=ahora, semanas_sin_ajustar=30, reporte_sin_fotos=False,
        faltan_fotos_o_medidas=None, dias_sin_cerrar=0, dias_sin_entrar=0,
        dias_con_el_perfil_a_medias=None, dias_sin_preferencias=None,
        dias_en_mantenimiento=None, rutina_mes_aplazada_hasta=None, con_ajuste=False)
    assert not [a for a in avisos if a["familia"] == "sin_ajustar"]


# ── P59: la pasada de correos ────────────────────────────────────────────────

async def _con_interruptor(valor):
    await db.app_settings.update_one(
        {"id": "app"}, {"$set": {"pantallas.correos_avisos": valor}}, upsert=True)


def test_59_apagada_no_manda_nada():
    async def caso():
        await _con_interruptor(False)
        from core.correo_avisos import pasada_de_correos_de_avisos
        return await pasada_de_correos_de_avisos()
    assert correr(caso()) == 0


def test_59_un_aviso_un_correo_y_nunca_dos():
    """Con el interruptor puesto, un aviso de familia de correo genera UN correo
    pendiente, y la segunda pasada no lo repite (la marca única lo corta)."""
    async def caso():
        from core.correo_avisos import FAMILIAS_CORREO, pasada_de_correos_de_avisos
        assert "reporte_no_llego" in FAMILIAS_CORREO

        # Un usuario de mentira con perfil activo y un aviso de esa familia ya creado
        # (la pasada re-sincroniza avisos, pero este es suyo con su clave propia).
        uid = f"correo-prueba-{uuid.uuid4().hex[:8]}"
        clave = f"reporte_no_llego:prueba-{uuid.uuid4().hex[:6]}"
        await db.users.insert_one({
            "id": uid, "email": f"{uid}@correo-prueba.local", "name": "Correo Prueba",
            "role": "client", "deleted_at": None})
        await db.client_profiles.insert_one({
            "id": str(uuid.uuid4()), "user_id": uid, "plan": "nivel1", "status": "activo"})
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "user_id": uid, "type": "reporte",
            "title": "No nos llegó tu reporte", "body": "Sin él no podemos ajustarte.",
            "link": "/dashboard/reports", "read": False, "clave": clave,
            "familia": "reporte_no_llego", "condicionada": False,
            "created_at": datetime.now(timezone.utc).isoformat()})

        try:
            await _con_interruptor(True)
            await pasada_de_correos_de_avisos(solo_user_id=uid)
            primera = await db.correos_pendientes.count_documents(
                {"para": f"{uid}@correo-prueba.local"})
            await pasada_de_correos_de_avisos(solo_user_id=uid)
            segunda = await db.correos_pendientes.count_documents(
                {"para": f"{uid}@correo-prueba.local"})
            return primera, segunda
        finally:
            await _con_interruptor(False)
            await db.users.delete_one({"id": uid})
            await db.client_profiles.delete_one({"user_id": uid})
            await db.notifications.delete_many({"user_id": uid})
            await db.correos_de_avisos.delete_many({"user_id": uid})
            await db.correos_pendientes.delete_many({"para": f"{uid}@correo-prueba.local"})

    primera, segunda = correr(caso())
    assert primera == 1, f"el aviso tenía que generar UN correo (salieron {primera})"
    assert segunda == 1, "la segunda pasada repitió el correo: la marca única no corta"


def test_59_las_cuentas_de_pruebas_no_reciben_correo():
    async def caso():
        from core.correo_avisos import pasada_de_correos_de_avisos
        uid = f"correo-prueba-{uuid.uuid4().hex[:8]}"
        await db.users.insert_one({
            "id": uid, "email": f"{uid}@correo-prueba.local", "name": "QA",
            "role": "client", "deleted_at": None, "es_pruebas": True})
        await db.client_profiles.insert_one({
            "id": str(uuid.uuid4()), "user_id": uid, "plan": "nivel1", "status": "activo"})
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "user_id": uid, "type": "reporte",
            "title": "No nos llegó tu reporte", "body": None, "link": None, "read": False,
            "clave": f"reporte_no_llego:qa-{uuid.uuid4().hex[:6]}",
            "familia": "reporte_no_llego", "condicionada": False,
            "created_at": datetime.now(timezone.utc).isoformat()})
        try:
            await _con_interruptor(True)
            await pasada_de_correos_de_avisos(solo_user_id=uid)
            return await db.correos_pendientes.count_documents(
                {"para": f"{uid}@correo-prueba.local"})
        finally:
            await _con_interruptor(False)
            await db.users.delete_one({"id": uid})
            await db.client_profiles.delete_one({"user_id": uid})
            await db.notifications.delete_many({"user_id": uid})
            await db.correos_de_avisos.delete_many({"user_id": uid})
    assert correr(caso()) == 0
