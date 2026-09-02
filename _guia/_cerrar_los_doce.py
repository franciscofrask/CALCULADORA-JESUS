# -*- coding: utf-8 -*-
"""LOS DOCE, CERRADOS: pasa el veredicto a «visto» y les engancha su captura nueva.

Los doce puntos que no estaban eran los doce de «Todo lo validado antes del 1 de
septiembre», el documento de dos columnas («Como esta hoy» / «Como queda»). Este guion no
decide nada: lee lo que ha salido de `_capturar_los_doce.js` -- que abre la app de verdad y
comprueba frase por frase -- y solo escribe el veredicto de los que salieron limpios.

    SI UNA ESCENA VIENE CON FRASES QUE FALTAN, EL PUNTO NO SE CIERRA. Es la unica defensa
    contra dar por bueno lo que no se ha visto, que es exactamente lo que paso con el
    primer repaso hecho a base de grep.

Uso (despues de `node _guia/_capturar_los_doce.js`):
    ./backend/venv/Scripts/python.exe _guia/_cerrar_los_doce.py
"""
import io
import json
import os
import shutil

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NUEVAS = os.path.join(RAIZ, "_guia", "_capturas_doce")
CAPTURAS = os.path.join(RAIZ, "_guia", "_capturas")

#: Que escena prueba que punto, y con que frase se cierra. Un punto puede necesitar dos
#: escenas (la fila de Inicio del miercoles y la del jueves son la MISMA fila con otro
#: texto, pero son dos puntos del documento).
CIERRES = {
    "Paso 1 · Confirmar nueva": ("quincenal-paso1", None),
    "Con sus check-in nueva": ("quincenal-paso1", None),
    "Paso 2 · Contar nueva": ("quincenal-paso2", None),
    "Paso 3 · Recibir nueva": ("quincenal-paso3", None),
    "Sin check-in suficientes nueva": ("quincenal-paso1-sin-checkin", None),
    "Miércoles, desde las 10:00 nueva": ("inicio-miercoles", None),
    "Jueves a las 17:00, si aún no lo ha mandado nueva": ("inicio-jueves", None),
    "Hecho": ("tarjeta-hecho", None),
    "Cierra el quincenal": ("tarjeta-hecho", None),
    "El campo, en Mi evolución nueva": ("evolucion-campo-peso", None),
    "Una comida por dentro": ("nutricion-comida", None),
    "Dos frases que marcaste como intocables, cambiadas": ("alimento-almendras", None),
}

#: Lo que se apunta al lado de cada uno, para que se lea POR QUE esta cerrado y no solo que
#: lo esta. Es lo que en el artifact va debajo del titulo.
NOTAS = {
    "Paso 1 · Confirmar nueva":
        "El quincenal se parte en tres pasos, con «Son 3 pasos» arriba y el suyo marcado. "
        "El paso 1 ya no pide el peso: enseña el de la semana con sus dos días y la pareja "
        "señalada, lo que ha hecho, cómo se ha sentido y los días que le falten.",
    "Con sus check-in nueva":
        "La misma pantalla, con sus datos: confirma. Y si le falta una pesada, la línea del "
        "peso se lo dice.",
    "Paso 2 · Contar nueva":
        "Las dos escalas de 0 a 10 con los extremos escritos, las molestias y el campo "
        "libre con su «Ahora es el momento y el lugar».",
    "Paso 3 · Recibir nueva":
        "El tercer paso existe y sale anunciado desde el primero. Y da una hora: el día lo "
        "dice el servidor, del mismo sitio del que vive el aviso al equipo.",
    "Sin check-in suficientes nueva":
        "Al que no tiene check-in suficientes no se le enseña una pantalla vacía: se le "
        "pregunta. Cinco estrellas y al paso 2.",
    "Miércoles, desde las 10:00 nueva":
        "El reporte entra ARRIBA y empuja al check-in hacia abajo, y el plazo se dice con "
        "palabras: «Tienes hasta mañana jueves a las ocho».",
    "Jueves a las 17:00, si aún no lo ha mandado nueva":
        "El aviso del plazo no es una fila nueva: es esta misma, cambiándole el texto. El "
        "jueves por la tarde siguen siendo dos filas, no tres.",
    "Hecho":
        "«Respondiste a tiempo y ahora nos toca a nosotros. Te decimos algo antes del "
        "viernes a las tres de la tarde, hora de España.» Y fuera el «Esta semana».",
    "Cierra el quincenal":
        "Es el texto de la tarjeta en Hecho, que ya está.",
    "El campo, en Mi evolución nueva":
        "El peso se escribe ahora en Evolución, siempre abierto, y se fue del cierre del "
        "día. Las otras dos puertas llevan aquí: la fila «Hoy toca pesarte» de Inicio y el "
        "paso 1 del quincenal.",
    "Una comida por dentro":
        "La frase vuelve a su voz. OJO: su bloque 7 («La regla de las voces») dice lo "
        "contrario de su propia maqueta y está sin resolver; manda la maqueta y la duda "
        "queda apuntada.",
    "Dos frases que marcaste como intocables, cambiadas":
        "«Su proteína no te cuenta» vuelve donde hace falta: en los alimentos que calibran, "
        "donde el «solo» se cae y con él se iba lo único que lo decía.",
}


def main() -> None:
    resultado = {r["id"]: r for r in json.load(
        io.open(os.path.join(NUEVAS, "_resultado.json"), encoding="utf-8"))}
    ruta_rev = os.path.join(RAIZ, "_guia", "_revision_puntos.json")
    rev = json.load(io.open(ruta_rev, encoding="utf-8"))

    ruta_man = os.path.join(CAPTURAS, "_manifiesto.json")
    manifiesto = json.load(io.open(ruta_man, encoding="utf-8"))
    puntos = {p["titulo"]: p for p in json.load(
        io.open(os.path.join(RAIZ, "_guia", "_puntos_todos.json"), encoding="utf-8"))}

    cerrados, sin_cerrar = [], []
    for titulo, (escena, _f) in CIERRES.items():
        r = resultado.get(escena)
        if not r:
            sin_cerrar.append((titulo, "esa escena no se ha capturado"))
            continue
        if r["faltan"] or r["sobran"]:
            sin_cerrar.append((titulo, f"faltan: {r['faltan']} · sobran: {r['sobran']}"))
            continue

        rev[titulo] = ["ok", NOTAS.get(titulo, "Visto en la app.")]
        cerrados.append(titulo)

        # La captura, a la carpeta del repaso, y su fila en el manifiesto.
        if r.get("imagen"):
            shutil.copyfile(os.path.join(NUEVAS, r["imagen"]),
                            os.path.join(CAPTURAS, r["imagen"]))
        p = puntos.get(titulo)
        if not p:
            continue
        clave = (p["doc"], p["titulo"], p["seccion"])
        manifiesto = [m for m in manifiesto
                      if (m["doc"], m["titulo"], m["seccion"]) != clave]
        manifiesto.append({**p, "escena_id": escena, "forzada": r.get("forzada"),
                           "ruta": r.get("ruta"), "faltan": [],
                           "imagen": r.get("imagen"), "estado": "completo"})

    json.dump(rev, io.open(ruta_rev, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(manifiesto, io.open(ruta_man, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print(f"cerrados: {len(cerrados)}")
    for t in cerrados:
        print("   ·", t)
    for t, por_que in sin_cerrar:
        print(f"   NO se cierra «{t}»: {por_que}")


if __name__ == "__main__":
    main()
