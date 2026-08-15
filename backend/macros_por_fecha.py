"""De dónde salen los macros objetivo de un cliente para un día concreto.

**Una sola función para toda la app.** Punto 80 del documento de Jesús (07-08-2026): *«sus
objetivos no coinciden con los de la pantalla de Nutrición»*. No coincidían, y la
diferencia no era pequeña. Para el mismo cliente y el mismo día:

    Nutrición   C1 = 47,5 P / 51 H / 12 G     220 H al día    (H entreno 170)
    Asistente   C1 = 47,5 P / 72 H / 12 G     290 H al día    (H entreno 240)

**70 g de hidratos de diferencia al día, 280 kcal.** La proteína y la grasa coincidían;
los hidratos no.

El motivo: los macros de un cliente **cambian con el tiempo** -- es el ajuste mensual del
método -- y cada cambio queda en la colección `macro_history` con su `effective_date`.
Nutrición leía de ahí (replicando `todosLosMacros` de Calma: el día usa la versión vigente
a esa fecha). El asistente leía `client_profiles.macros_training`, que es la foto suelta
del perfil y se queda vieja en cuanto hay una revisión.

Y hay revisiones: **210 de los 236 clientes** tienen historial, con 3.439 entradas.

Si algún día hace falta otra vista de lo mismo (un informe, una exportación), que llame
aquí en vez de leer el perfil por su cuenta: la tercera copia de esta lógica es la que
volvería a separarse.
"""
from typing import Optional, Tuple


async def elegir_entrada(db, profile: dict, fecha: Optional[str]) -> Optional[dict]:
    """La entrada de `macro_history` vigente para `fecha`.

    La última con `effective_date <= fecha`; si la fecha es anterior a cualquier cambio, la
    más antigua (el cliente ya entrenaba con esos macros antes de que se registraran).
    None cuando no hay historial o no hay fecha.
    """
    if not fecha:
        return None
    entries = await db.macro_history.find({"client_id": profile.get("id")}, {"_id": 0}).to_list(500)
    if not entries:
        return None

    def eff(e):   # las entradas antiguas no tienen effective_date: vale la fecha de creación
        return e.get("effective_date") or str(e.get("created_at", ""))[:10]

    aplicables = [e for e in entries if eff(e) and eff(e) <= fecha]
    return (max(aplicables, key=lambda e: (eff(e), e.get("created_at", "")))
            if aplicables else min(entries, key=lambda e: (eff(e), e.get("created_at", ""))))


async def ultima_vigente(db, client_id: str, fecha: Optional[str] = None) -> Optional[dict]:
    """El ajuste de macros que MANDA hoy (o en `fecha`). Para «el último ajuste» de alguien.

    Existe porque media app lo pedía con `find_one(sort=[("created_at", -1)])`, y eso está
    mal desde que se importó Calma: en las 3.446 filas migradas `created_at` es el día en que
    se importaron -- todas el 05-08-2026, muchas en el mismo milisegundo --, así que «la
    última» sale a suertes entre toda la historia del cliente. Uno con 176 ajustes entre 2022
    y 2029 podía recibir como «sus macros nuevos» los de hace cuatro años.

    La fecha buena es `effective_date`, que sí viajó bien (3.495 de 3.504 filas la tienen).
    Y se corta en hoy: un ajuste programado para dentro de tres semanas todavía no se le ha
    hecho.
    """
    from datetime import date as _date
    return await elegir_entrada(db, {"id": client_id}, fecha or _date.today().isoformat())


async def ultimo_cambio(db, client_id: str) -> Optional[dict]:
    """El ajuste mas reciente REGISTRADO, aunque su fecha sea de manana.

    No es lo mismo que `ultima_vigente`, que corta en hoy porque contesta «con que macros
    come hoy». Aqui la pregunta es otra: «cuando fue la ultima vez que alguien le movio los
    macros». Un ajuste guardado hoy con efecto manana ya es un cambio hecho.

    Sale del informe del 15-08 (#51): «Llevas 4 semanas con los mismos macros» a los dos
    dias de ajustarlos. Contando con la vigente, el ajuste programado no existia todavia y
    el aviso seguia saliendo. Y aqui tambien manda `effective_date`, nunca `created_at`:
    en las 3.446 filas que vinieron de Calma ese campo es el dia de la importacion.
    """
    entries = await db.macro_history.find({"client_id": client_id}, {"_id": 0}).to_list(500)
    if not entries:
        return None

    def eff(e):
        return e.get("effective_date") or str(e.get("created_at", ""))[:10]

    return max(entries, key=lambda e: (eff(e), str(e.get("created_at", ""))))


async def resolver(db, profile: dict, fecha: Optional[str]) -> Tuple[dict, dict, dict]:
    """Los macros (entreno, descanso, peri) vigentes para esa fecha.

    Sin historial o sin fecha, los del perfil: es lo que había antes y sigue valiendo para
    un cliente nuevo, que aún no tiene revisiones.
    """
    cur_training = profile.get("macros_training") or {}
    cur_rest = profile.get("macros_rest") or {}
    cur_peri = profile.get("macros_periworkout") or profile.get("macros_peri") or {}
    chosen = await elegir_entrada(db, profile, fecha)
    if not chosen:
        return cur_training, cur_rest, cur_peri
    training = chosen.get("new_training") or chosen.get("training") or cur_training
    rest = chosen.get("new_rest") or chosen.get("rest") or cur_rest
    peri = chosen.get("peri") or cur_peri     # las entradas antiguas no llevan peri
    return training, rest, peri


async def para_el_chat(db, profile: Optional[dict], fecha: Optional[str]) -> dict:
    """Lo mismo, con los nombres que usa el asistente (`p_entreno`, `h_peri`...).

    Los valores por defecto son los que ya había en `/chatbot/start` para un usuario sin
    perfil, y se conservan tal cual para no cambiar ese caso de paso.
    """
    if not profile:
        return {"p_entreno": 160, "h_entreno": 50, "g_entreno": 40,
                "p_peri": 35, "h_peri": 15,
                "p_descanso": 140, "h_descanso": 40, "g_descanso": 40}
    mt, mr, mp = await resolver(db, profile, fecha)
    return {
        "p_entreno": mt.get("proteinas", 160),
        "h_entreno": mt.get("hidratos", 50),
        "g_entreno": mt.get("grasas", 40),
        "p_peri": mp.get("proteinas", 35),
        "h_peri": mp.get("hidratos", 15),
        "p_descanso": mr.get("proteinas", 140),
        "h_descanso": mr.get("hidratos", 40),
        "g_descanso": mr.get("grasas", 40),
    }
