# -*- coding: utf-8 -*-
"""EL VEREDICTO DE LOS 113 PUNTOS, compuesto de lo que se ha mirado.

Junta tres cosas y no decide ninguna por su cuenta:

  · lo que sale de abrir la app (`_capturas/_manifiesto.json` y
    `_capturas_doce/_resultado.json`): que frases se ven y cuales no,
  · que escena prueba que punto (la tabla de aqui abajo),
  · y el juicio a mano, que es lo unico que sabe distinguir «no esta hecho» de «es un dato
    del cliente de su maqueta».

SI UNA ESCENA VIENE CON FRASES QUE FALTAN, EL PUNTO NO SE DA POR HECHO. Es la unica defensa
contra el primer repaso, el que daba cosas por cerradas mirando el codigo con grep.

Uso:  ./backend/venv/Scripts/python.exe _guia/_componer_veredictos.py
"""
import io
import json
import os
import sys
import unicodedata

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "_guia"))

from _veredictos import HECHO, MATIZ, FALTA, DESPUES, NO_PANTALLA     # noqa: E402


def llave(t):
    """El titulo reducido a letras y numeros.

    Los titulos vienen de su HTML y traen de todo: tildes, eñes, puntos medios, rayas y
    comillas angulares. Comparar eso a pelo es garantizado fallar, y fallar aqui significa
    dejar un punto sin veredicto sin que se note.
    """
    t = unicodedata.normalize("NFKD", (t or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join("".join(c if c.isalnum() else " " for c in t).split())


# ── QUE ESCENA PRUEBA QUE PUNTO, y con que frase se resume ──────────────────────────────
#
# La escena es de `_capturar_los_doce.js`. Un punto puede compartir escena con otro: la fila
# de la pesada del miercoles y la del jueves son la MISMA fila, y en su documento son dos
# puntos porque son dos dias del calendario.
DE_LA_APP = {
    # ── El quincenal en tres pasos ──
    "paso 1 · confirmar nueva": ("quincenal-paso1",
        "Los tres pasos, con «Son 3 pasos» arriba y el suyo marcado. El paso 1 ya no pide "
        "el peso: enseña el de la semana con sus dos días y la pareja señalada."),
    "con sus check-in nueva": ("quincenal-paso1",
        "La misma pantalla con sus datos: solo confirma. Y si le falta una pesada, la línea "
        "del peso se lo dice."),
    "paso 2 · contar nueva": ("quincenal-paso2",
        "Las dos escalas de 0 a 10 con los extremos escritos, las molestias y el campo libre."),
    "paso 3 · recibir nueva": ("quincenal-paso3",
        "El tercer paso existe y sale anunciado desde el primero. Y da una hora."),
    "sin check-in suficientes nueva": ("quincenal-paso1-sin-checkin",
        "Al que no tiene check-in no se le enseña una pantalla vacía: se le pregunta. Cinco "
        "estrellas y al paso 2."),

    # ── La cola de Inicio ──
    "miercoles, desde las 10:00 nueva": ("inicio-miercoles",
        "El reporte entra ARRIBA y empuja al check-in hacia abajo, y el plazo se dice con "
        "palabras: «Tienes hasta mañana jueves a las ocho»."),
    "jueves a las 17:00, si aun no lo ha mandado nueva": ("inicio-jueves",
        "El aviso del plazo no es una fila nueva: es esta misma, cambiándole el texto. "
        "Siguen siendo dos filas, no tres."),

    # ── La tarjeta ──
    "hecho": ("tarjeta-hecho",
        "«Respondiste a tiempo y ahora nos toca a nosotros. Te decimos algo antes del "
        "viernes a las tres de la tarde, hora de España.» Y fuera el «Esta semana»."),
    "cierra el quincenal": ("tarjeta-hecho", "Es el texto de la tarjeta en Hecho, que ya está."),

    # ── El peso ──
    "el campo, en mi evolucion nueva": ("evolucion-campo-peso",
        "El peso se escribe ahora en Evolución, siempre abierto, y se fue del cierre del día."),
    "miercoles por la mañana nueva": ("inicio-miercoles",
        "«Hoy toca pesarte · En ayunas y después de ir al baño», y al tocarla le abre el "
        "campo en Evolución. No existía."),
    "jueves por la mañana nueva": ("inicio-miercoles",
        "La misma fila, el segundo día de la pareja: la regla son los dos días (miércoles y "
        "jueves), y con esos dos la media sale sola."),
    "y a las 12:00 se apaga nueva": ("inicio-mediodia-sin-pesada",
        "A las 12:00 la fila desaparece: después de comer ya no es un peso en ayunas. El "
        "campo sigue abierto en Evolución para el que quiera."),

    # ── Los avisos del peso ──
    "martes · el primero nueva": ("aviso-peso-martes",
        "El aviso del martes, con su texto. No existía: aquí había uno el miércoles y otro "
        "el jueves, y su calendario pone el aviso el martes y la FILA los dos días."),
    "viernes · si le falta una pesada nueva": ("aviso-peso-viernes",
        "El rescate del viernes, con su texto. Solo a quien mandó el reporte y tiene una "
        "sola pesada. No existía."),
    "miercoles de la semana 1 nueva": ("aviso-peso-semana1",
        "El de la semana sin reporte, y solo el primer ciclo: es el que le enseña el método. "
        "No existía."),

    # ── Los avisos del reporte ──
    "miercoles, a las 10:00 · cuando se abre nueva": ("aviso-quincenal-abierto",
        "El de la apertura, con su texto. Antes rotaban tres redacciones nuestras; estas "
        "son las suyas, dicen la hora y no se rotan."),
    "jueves por la mañana · el recordatorio nueva": ("aviso-quincenal-ultimo",
        "El del último día, y le dice QUÉ SE PIERDE sin que el mensual parezca un castigo."),
    "jueves, de 20:00 a 24:00 nueva": ("aviso-quincenal-fuera-de-plazo",
        "El fuera de plazo del mismo jueves, hasta medianoche. NO EXISTÍA: el «no nos llegó» "
        "era del mensual y saltaba al día siguiente."),

    # ── Semana a semana: es su calendario, y cada fila apunta a algo de arriba ──
    "el aviso de que no toca reporte": ("aviso-peso-semana1", "El aviso de la semana 1."),
    "el aviso del peso": ("aviso-peso-martes", "El aviso del martes."),
    "la fila del peso en inicio": ("inicio-miercoles", "La fila de la pesada."),
    "se abre el quincenal": ("aviso-quincenal-abierto", "El aviso de la apertura."),
    "el recordatorio del ultimo dia": ("aviso-quincenal-ultimo", "El del último día."),
    "si le falta una pesada": ("aviso-peso-viernes", "El rescate del viernes."),

    # ── Lo que quedaba sin comprobar ──
    "y asi queda la pantalla al pulsar el +": ("inicio-extras-abierto",
        "El cuadro de extras se abre ahí mismo, sin salir de Inicio."),
    "extras del dia · con el buscador delante": ("inicio-extras-abierto",
        "El cuadro entero: el buscador delante, el «o si no está» para escribirlo a mano y "
        "la línea que avisa de que lo escrito a mano no cuenta en los macros."),
    "tras 2 dias perdidos nueva": ("inicio-dos-dias",
        "La fila cambia de texto a los dos días. La compone el servidor."),
    "tras 4 dias perdidos nueva": ("inicio-cuatro-dias",
        "A los cuatro dice lo que se pierde, y sin riña."),
    "tras una semana nueva": ("inicio-una-semana",
        "A la semana deja de recordárselo, pero la línea NO desaparece."),
    "el aviso de arriba, si le faltan comidas": ("cierre-comidas-pendientes",
        "El aviso de las comidas sin registrar, arriba del todo y antes de la primera "
        "pregunta."),
    "al apagar el cierre nueva": ("perfil-apagar-cierre",
        "El aviso que sale antes de apagarlo, con sus dos salidas."),
    "«tu plan no incluye rutina» · y debajo se la promete": ("rutina-sin-la-del-mes",
        "Una sola cosa, y la verdadera: «Todavía no está la rutina de este mes»."),
    "los ejercicios que dan molestias": ("mensual-paso2-molestias",
        "El bloque llega con los que ya dio: «Quita los que ya no y añade los nuevos»."),
    "el porcentaje que ha bajado cada semana": ("informe-peso-y-extras",
        "El reparto por semanas. No salía porque el cliente del ejemplo no cambió de peso; "
        "con un mes que baja, sale."),
    "lo que apunto y que dia": ("informe-peso-y-extras",
        "Los extras con su día. No salía porque el cliente del ejemplo no apuntó ninguno."),

    # ── El mensual sin check-in ──
    "el aviso de que no los tiene": ("mensual-paso1-sin-checkin",
        "«No tengo todos los datos de tus check-in diarios, así que te lo pregunto aquí.» "
        "NO ESTABA: esto solo se había hecho para el quincenal."),
    "las cinco preguntas con estrellas": ("mensual-paso1-sin-checkin",
        "Las cinco, con sus palabras y con cinco estrellas."),
    "y el boton de continuar": ("mensual-paso1-sin-checkin",
        "«Continuar», y apagado hasta que las contesta."),
    "el peso y las fotos se le piden igual": ("mensual-paso1-sin-checkin",
        "«Cinco preguntas y pasas al paso 2. El peso y las fotos se te piden igual»: el "
        "peso se sigue pidiendo, que ése no depende de haber apuntado nada."),
}

# ── LO QUE NO ES UNA PANTALLA ───────────────────────────────────────────────────────────
#
# Y se dice cual es, para que «no hay pantalla» deje de ser un cajon donde cabe todo.
NO_HAY_PANTALLA = {
    "tu ajustas": "No es de la app: es tu trabajo del viernes. A las 10:00 se cierra todo, "
                  "miras el reporte contra sus check-in y pones los macros nuevos.",
    "vuelve el mensual": "Es una fila de su calendario, no una pantalla: dice cuándo vuelve "
                         "a tocar el mensual.",
}


def main() -> None:
    puntos = json.load(io.open(os.path.join(RAIZ, "_guia", "_puntos_todos.json"),
                               encoding="utf-8"))
    viejo = json.load(io.open(os.path.join(RAIZ, "_guia", "_revision_puntos.json"),
                              encoding="utf-8"))
    viejo = {llave(k): v for k, v in viejo.items()}

    man = {}
    for m in json.load(io.open(os.path.join(RAIZ, "_guia", "_capturas", "_manifiesto.json"),
                               encoding="utf-8")):
        man[(m["doc"], llave(m["titulo"]), m["seccion"])] = m
    nuevo = {r["id"]: r for r in json.load(
        io.open(os.path.join(RAIZ, "_guia", "_capturas_doce", "_resultado.json"),
                encoding="utf-8"))}

    # Las dos tablas, con las claves por el mismo cedazo que los titulos.
    de_la_app = {llave(k): v for k, v in DE_LA_APP.items()}
    no_hay_pantalla = {llave(k): v for k, v in NO_HAY_PANTALLA.items()}

    fuera, sin_resolver = {}, []
    for p in puntos:
        k = llave(p["titulo"])
        v = None

        if k in de_la_app:
            escena, nota = de_la_app[k]
            r = nuevo.get(escena)
            if r and not r["faltan"] and not r["sobran"]:
                v = {"estado": HECHO, "nota": nota, "imagen": r.get("imagen"),
                     "ruta": r.get("ruta"), "forzada": r.get("forzada"),
                     # Lo que la escena NO encontró de las frases de ESTE punto.
                     "faltan": [f for f in p["debe_verse"] if f in set(r["faltan"])]}
            else:
                sin_resolver.append((p["titulo"], f"la escena {escena} no salió limpia"))
                continue

        elif k in no_hay_pantalla:
            v = {"estado": NO_PANTALLA, "nota": no_hay_pantalla[k], "faltan": p["debe_verse"]}

        else:
            # Lo de la primera pasada. Las frases que faltaban se conservan: es lo que
            # ahora lleva su motivo al lado.
            m = man.get((p["doc"], k, p["seccion"]))
            antes = viejo.get(k)
            faltan = (m or {}).get("faltan", p["debe_verse"])
            if antes and antes[0].startswith("ok"):
                v = {"estado": MATIZ if faltan else HECHO,
                     "nota": antes[1] or "Visto en la app.",
                     "imagen": (m or {}).get("imagen"), "ruta": (m or {}).get("ruta"),
                     "forzada": (m or {}).get("forzada"), "faltan": faltan}
            elif m and m["estado"] == "completo":
                v = {"estado": HECHO, "nota": "Se ve entero en la app.",
                     "imagen": m.get("imagen"), "ruta": m.get("ruta"),
                     "forzada": m.get("forzada"), "faltan": []}
            elif m:
                v = {"estado": MATIZ, "nota": (antes[1] if antes else
                                               "Se ve, pero no entero: mira las frases."),
                     "imagen": m.get("imagen"), "ruta": m.get("ruta"),
                     "forzada": m.get("forzada"), "faltan": faltan}
            else:
                sin_resolver.append((p["titulo"], "sin captura y sin veredicto"))
                continue

        fuera[f'{p["doc"]}|{p["seccion"]}|{p["titulo"]}'] = v

    ruta = os.path.join(RAIZ, "_guia", "_veredictos.json")
    json.dump(fuera, io.open(ruta, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    cuenta = {}
    for v in fuera.values():
        cuenta[v["estado"]] = cuenta.get(v["estado"], 0) + 1
    print(f"{len(fuera)} de {len(puntos)} puntos con veredicto")
    for e, n in sorted(cuenta.items()):
        print(f"   {e:18} {n}")
    for t, por_que in sin_resolver:
        print(f"   SIN RESOLVER: {t[:60]} -- {por_que}")


if __name__ == "__main__":
    main()
