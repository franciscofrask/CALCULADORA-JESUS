"""
El calendario de arranque (especificacion 31-07-2026, parte 2).

    "Todos los clientes arrancan en lunes, pague el dia que pague."

No es una preferencia: es lo que permite dimensionar el trabajo de la semana y, sobre
todo, que el cobro llegue antes de preparar el ciclo siguiente. Si alguien no renueva,
no se le prepara nada y no se trabaja en balde.

    DIA QUE PAGA (un miercoles, por ejemplo)
       -> se cobra el ciclo completo
       -> se ANCLA el ciclo de facturacion al lunes que le toca
       -> entra en la app inmediatamente

    SEMANA 0 (de que paga al lunes)  ... puesta a punto, no espera
    LUNES, SEMANA 1 ................. arranca el programa
    LUNES DE LA SEMANA 12 ........... Stripe cobra solo, a los 84 dias

La regla de las 48 horas: si al pagar quedan menos de 48 h para el lunes, arranca el
lunes siguiente. Hace falta porque en los niveles 2 y 3 el equipo tiene 48 h para
validar los macros, y sin ese margen se arranca sin ellos.

Los dias de la Semana 0 se le REGALAN: no se prorratean.
"""
from datetime import datetime, time, timedelta, timezone
from typing import Dict, Optional

HORAS_MINIMAS_ANTES_DEL_LUNES = 48


def _a_utc(momento: Optional[datetime] = None) -> datetime:
    ahora = momento or datetime.now(timezone.utc)
    return ahora.replace(tzinfo=timezone.utc) if ahora.tzinfo is None else ahora


def proximo_lunes(momento: Optional[datetime] = None) -> datetime:
    """El siguiente lunes a las 00:00 UTC. Si hoy ES lunes, devuelve el de hoy."""
    ahora = _a_utc(momento)
    dias = (7 - ahora.weekday()) % 7          # 0 = lunes
    lunes = datetime.combine((ahora + timedelta(days=dias)).date(), time.min, timezone.utc)
    return lunes


def lunes_de_arranque(momento: Optional[datetime] = None) -> datetime:
    """El lunes en el que arranca su programa, aplicando la regla de las 48 horas."""
    ahora = _a_utc(momento)
    lunes = proximo_lunes(ahora)
    if lunes <= ahora:                         # paga un lunes ya empezado
        lunes = lunes + timedelta(days=7)
    if (lunes - ahora) < timedelta(hours=HORAS_MINIMAS_ANTES_DEL_LUNES):
        lunes = lunes + timedelta(days=7)
    return lunes


def plan_de_arranque(momento: Optional[datetime] = None,
                     semanas_ciclo: int = 12) -> Dict[str, object]:
    """Todo lo que hace falta saber al dar de alta a alguien.

    `anchor_timestamp` es lo que se le pasa a Stripe como `billing_cycle_anchor`: el
    primer cobro es hoy y el siguiente cae a los 84 dias del lunes de arranque, no a los
    84 dias de hoy. Asi el cobro llega SIEMPRE antes de preparar el ciclo siguiente.
    """
    ahora = _a_utc(momento)
    lunes = lunes_de_arranque(ahora)
    dias_semana_cero = (lunes.date() - ahora.date()).days
    fin = lunes + timedelta(weeks=semanas_ciclo)

    return {
        "paga": ahora,
        "arranque": lunes,
        "dias_semana_cero": dias_semana_cero,
        "fin_de_ciclo": fin,
        "anchor_timestamp": int(lunes.timestamp()),
        # Si quedan menos de 48 h se le va al lunes siguiente: conviene poder decirselo.
        "salta_al_siguiente": dias_semana_cero > 7,
    }


MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")


def mensaje_de_arranque(plan: Dict[str, object]) -> str:
    """Lo que se le dice al comprar. Del documento, parte 2."""
    lunes = plan["arranque"]
    return (f"Tu programa arranca el lunes {lunes.day} de {MESES[lunes.month - 1]}. "
            "Hasta entonces, ve preparándolo todo: saca tus macros, hazte tus fotos y "
            "monta tus primeras dietas.")
