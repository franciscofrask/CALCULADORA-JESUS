# -*- coding: utf-8 -*-
"""LA PROMESA DEL REPORTE SE CUMPLE O SE AVISA (doc «El día», 31-08).

Al mandar su reporte, al cliente se le dice una fecha:

    «Antes del viernes tienes tus ajustes nuevos. Te aviso por aquí.»
    «Antes del sábado tienes tu informe completo con mi feedback y tus ajustes.»
    «El domingo tienes mi feedback: empiezas el lunes sabiendo qué cambia.»

Y ese «te aviso por aquí» ya funciona: al publicar el informe o al guardarle los macros le
salta su aviso. El agujero es el otro lado. SI NADIE LE CONTESTA, NO PASA NADA: el cliente
se queda esperando una fecha que ya pasó y la app no vuelve a hablarle del tema.

POR QUE NO SE LE AVISA A EL. Seria la app anunciandole que le hemos fallado, y eso no
arregla nada: no le da sus ajustes, le confirma que no los tiene. Ademas contradice al
propio documento, que dice que el unico aviso que le DA algo en vez de pedirle algo es el de
que le has contestado.

ASI QUE SE AVISA AL EQUIPO, Y ANTES DE QUE LA PROMESA VENZA. El aviso salta el mismo dia
prometido, no despues: el objetivo es que la promesa se cumpla, no dejar constancia de que
se rompio. Y va por la campanita del equipo, que es donde ya caen «Quiere la rutina del mes»
y los demas.

SIN INTERRUPTOR NINGUNO (Francisco, 31-08: «no quiero mas interruptores»). Es del equipo,
no del cliente, y no se apaga.
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

#: Cada tipo de reporte promete un dia distinto de la semana (0 = lunes).
#:   quincenal y el mensual sin feedback -> «antes del viernes»
#:   mensual con feedback                -> «antes del sabado»
#:   semanal                             -> «el domingo», que es cuando lo lee
DIA_PROMETIDO = {"quincenal": 4, "mensual": 5, "semanal": 6}

#: La hora a la que se mira, en España. A las 10:00 queda media jornada por delante: avisar a
#: las 14:55 de un «antes de las tres» es contarlo, no evitarlo.
HORA_DEL_REPASO = 10


def dia_de_la_promesa(tipo: Optional[str], mandado_el: date) -> date:
    """Que dia le prometimos contestarle, contando desde el dia en que lo mando."""
    objetivo = DIA_PROMETIDO.get((tipo or "quincenal").lower(), 4)
    adelanto = (objetivo - mandado_el.weekday()) % 7
    # Si lo manda el mismo dia prometido, la promesa es para el de la semana siguiente: no se
    # le puede prometer una respuesta para dentro de dos horas.
    return mandado_el + timedelta(days=adelanto or 7)


def vence_hoy(reporte: Dict[str, Any], hoy: date) -> bool:
    """¿Se le prometió contestar HOY y sigue sin contestarse?

    LOS MIGRADOS DE CALMA NO CUENTAN, y esto no es un detalle: en la base hay 3.414
    reportes y LOS 3.414 vienen de Calma (`calma_migrated`), sin `tipo`, sin
    `informe_estado` y alguno con fecha de 2028. Son historia, no trabajo pendiente: a esa
    gente no se le prometió nada por esta app. Sin este filtro el aviso saltaría cada semana
    con clientes de hace dos años, y un aviso que da la alarma en falso se deja de leer.
    """
    if reporte.get("calma_migrated"):
        return False
    if reporte.get("informe_estado") == "entregado":
        return False
    # Y tampoco los que ya llevan la respuesta escrita: el informe es de T9 y hay reportes
    # anteriores contestados a mano, con el feedback dentro y sin pasar por «Publicar».
    if (reporte.get("trainer_feedback") or "").strip():
        return False
    mandado = reporte.get("created_at") or reporte.get("fecha")
    if not mandado:
        return False
    try:
        cuando = date.fromisoformat(str(mandado)[:10])
    except (ValueError, TypeError):
        return False
    return dia_de_la_promesa(reporte.get("tipo"), cuando) == hoy


def texto_del_aviso(cuantos: int) -> Dict[str, str]:
    """Lo que lee el equipo. Dice a quien se le prometio y para cuando, no «hay pendientes»:
    un aviso que no dice el plazo se lee como una lista mas."""
    if cuantos == 1:
        return {"titulo": "Hoy le toca respuesta a 1 cliente",
                "mensaje": "Se le prometió respuesta para hoy y su reporte sigue sin "
                           "contestar. Está esperando."}
    return {"titulo": f"Hoy les toca respuesta a {cuantos} clientes",
            "mensaje": f"A {cuantos} se les prometió respuesta para hoy y sus reportes siguen "
                       "sin contestar. Están esperando."}


def a_quien_le_toca(reportes: List[Dict[str, Any]], hoy: date) -> List[Dict[str, Any]]:
    """Los reportes cuya promesa vence hoy y siguen sin contestar."""
    return [r for r in reportes if vence_hoy(r, hoy)]
