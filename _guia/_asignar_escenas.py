# -*- coding: utf-8 -*-
"""A que pantalla hay que ir para comprobar cada punto de «Todo lo validado».

Los otros dos documentos ya traen su escena. Aqui se dice la de los 59 del primero, y se
dice tambien cuando NO HAY PANTALLA que mirar: eso no es un hueco del repaso, es el
resultado (el bloque del quincenal no esta construido).

Uso:  ./backend/venv/Scripts/python.exe _guia/_asignar_escenas.py
"""
import io
import json
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FICHERO = os.path.join(RAIZ, "_guia", "_puntos_todos.json")

# titulo del apartado -> escena (o None si no hay pantalla donde mirarlo)
ESCENA = {
    # ── Inicio y Nutrición ─────────────────────────────────────────────────
    "La pantalla de Inicio, entera": "inicio",
    "Abre en Macros, y quedó en Llevas": "inicio",
    "Y así queda la pantalla al pulsar el +": "inicio-extras-abierto",
    "Extras del día — con el buscador delante": "inicio-extras-abierto",
    "Y así queda cuando ya ha apuntado algo": "inicio-extras-puestos",
    "Una comida por dentro": "nutricion-comida",
    "Los números, más altos y menos gordos": "inicio",
    "Los números de Nutrición, como los de Inicio": "nutricion",
    "El tramo en el que está, marcado": "alimento-almendras",

    # ── Los textos ─────────────────────────────────────────────────────────
    "Suplementos: el nombre y lo del chat": "suplementos-sin-protocolo",
    "La rutina sin asignar también manda al chat": "rutina",
    "«Tu plan no incluye rutina» — y debajo se la promete": "rutina-del-mes",
    "El aviso de cuando algo falla": "rutina-error",
    "El texto de la guía de suplementos": "suplementos-sin-plan",
    "El texto del código de FullGas": "suplementos",
    "Dos frases que marcaste como intocables, cambiadas": "alimentos-tres-frases",

    # ── El día ─────────────────────────────────────────────────────────────
    "El cierre del día": "cierre",
    "El aviso de arriba, si le faltan comidas": "cierre",
    "Si no le falta nada nueva": "cierre",
    "Las notas — se queda igual": "cierre",
    "Antes de guardar, hoy": "cierre",
    "Antes de guardar, como queda": "cierre",

    # ── Si no lo cierra ────────────────────────────────────────────────────
    "A la mañana siguiente, si ayer no lo cerró nueva": "inicio-ayer-sin-cerrar",
    "Tras 2 días perdidos nueva": "inicio-dos-dias",
    "Tras 4 días perdidos nueva": "inicio-cuatro-dias",
    "Tras una semana nueva": "inicio-una-semana",

    # ── Avisos y peso ──────────────────────────────────────────────────────
    "Mi perfil · Avisos nueva": "perfil",
    "Al apagar el cierre nueva": "perfil-apagar-cierre",
    "El campo, en Mi evolución nueva": "evolucion",
    "Miércoles por la mañana nueva": None,
    "Jueves por la mañana nueva": None,
    "Y a las 12:00 se apaga nueva": None,
    "Martes · el primero nueva": None,
    "Viernes · si le falta una pesada nueva": None,
    "Miércoles de la semana 1 nueva": None,

    # ── El quincenal ───────────────────────────────────────────────────────
    "Paso 1 · Confirmar nueva": "quincenal",
    "Paso 2 · Contar nueva": "quincenal",
    "Paso 3 · Recibir nueva": "quincenal",
    "Con sus check-in nueva": "quincenal",
    "Sin check-in suficientes nueva": "quincenal",
    "Pendiente": "seguimiento",
    "Hecho": "seguimiento",
    "Miércoles, a las 10:00 · cuando se abre nueva": None,
    "Jueves por la mañana · el recordatorio nueva": None,
    "Jueves, de 20:00 a 24:00 nueva": None,

    # ── La cola de Inicio ──────────────────────────────────────────────────
    "Un día cualquiera, desde las 17:00": "inicio",
    "Miércoles, desde las 10:00 nueva": "inicio-con-reporte",
    "Jueves a las 17:00, si aún no lo ha mandado nueva": "inicio-con-reporte",
    "En cuanto lo manda": "inicio",

    # ── Semana a semana ────────────────────────────────────────────────────
    # Son los avisos del ciclo, uno por dia. Los que tienen pantalla van con ella;
    # los que son un aviso de la campanita no la tienen todavia.
    "El aviso de que no toca reporte": None,
    "El aviso del peso": None,
    "La fila del peso en Inicio": None,
    "Se abre el quincenal": None,
    "El recordatorio del último día": None,
    "Cierra el quincenal": "seguimiento",
    "Si le falta una pesada": None,
    "Tú ajustas": None,
    "Se abre el mensual": "seguimiento",
    "Vuelve el mensual": None,
}


def main() -> None:
    puntos = json.load(io.open(FICHERO, encoding="utf-8"))
    sin_asignar = []
    for p in puntos:
        if p["doc"] != "validado":
            continue
        if p["titulo"] in ESCENA:
            p["escena"] = ESCENA[p["titulo"]]
        else:
            sin_asignar.append(p["titulo"])

    with io.open(FICHERO, "w", encoding="utf-8") as f:
        json.dump(puntos, f, ensure_ascii=False, indent=1)

    con, sin = 0, 0
    escenas = {}
    for p in puntos:
        if p.get("escena"):
            con += 1
            escenas[p["escena"]] = escenas.get(p["escena"], 0) + 1
        else:
            sin += 1
    print(f"{len(puntos)} puntos · {con} con pantalla · {sin} sin pantalla que mirar")
    if sin_asignar:
        print("SIN ASIGNAR:", sin_asignar)
    print("\npor escena:")
    for e, n in sorted(escenas.items(), key=lambda x: -x[1]):
        print(f"  {e:26} {n}")


main()
