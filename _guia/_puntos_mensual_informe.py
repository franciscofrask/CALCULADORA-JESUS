# -*- coding: utf-8 -*-
"""Los puntos de «El reporte mensual» y «El informe del mes», uno a uno.

Salen de las transcripciones completas (`_reporte_mensual_artefacto_completo.md` y
`_informe_del_mes_artefacto_completo.md`), que se leyeron abriendo cada maqueta por dentro.
Cada punto lleva las frases que TIENEN QUE VERSE en la pantalla.

Se juntan con los 59 de «Todo lo validado» (`_extraer_puntos_validado.py`) en
`_puntos_todos.json`.

Uso:  ./backend/venv/Scripts/python.exe _guia/_puntos_mensual_informe.py
"""
import io
import json
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (seccion, titulo, [frases que tienen que verse], escena)
MENSUAL = [
    ("Los cuatro pasos", "La cabecera: son 4 pasos",
     ["Son 4 pasos", "Actualizar tus datos y confirmar que están bien",
      "Escuchar tus sensaciones y dudas", "Tus fotos y tus medidas",
      "Entregarte el plan nuevo con el informe y darte feedback"], "mensual-paso1"),
    ("Los cuatro pasos", "El nombre del reporte, arriba",
     ["Reporte mensual"], "mensual-paso1"),

    ("Paso 1 · Actualizar tus datos", "El rótulo y su subtítulo",
     ["Actualizar tus datos",
      "Sale de tus check-in. Si algo no cuadra o te falta, lo arreglas al final."],
     "mensual-paso1"),
    ("Paso 1 · Actualizar tus datos", "El selector de periodo",
     ["Desde tu último reporte", "Desde que empezaste", "días"], "mensual-paso1"),
    ("Paso 1 · Actualizar tus datos", "Tu peso, con su curva y su cambio",
     ["Tu peso", "kg"], "mensual-paso1"),
    ("Paso 1 · Actualizar tus datos", "Lo que has hecho, y su rótulo",
     ["Lo que has hecho en los últimos", "Dietas guardadas",
      "Días que comiste de más"], "mensual-paso1"),
    ("Paso 1 · Actualizar tus datos", "Y cómo te has sentido",
     ["Y cómo te has sentido", "Descanso", "Energía", "Hambre / ansiedad"], "mensual-paso1"),
    ("Paso 1 · Actualizar tus datos", "El pie de las sensaciones",
     ["Lo de antes ya está cerrado"], "mensual-paso1"),
    ("Paso 1 · Actualizar tus datos", "El hueco de la dieta, con sus dos respuestas",
     ["de dieta", "No la cumplí", "Sí, pero no la guardé"], "mensual-paso1"),
    ("Paso 1 · Actualizar tus datos", "Los dos botones del paso",
     ["Modificar", "Confirmar"], "mensual-paso1"),
    ("Paso 1 · Actualizar tus datos", "El selector cambia el bloque entero",
     ["Lo que has hecho en"], "mensual-periodo"),

    ("Paso 2 · Tus sensaciones y tus dudas", "El rótulo del paso",
     ["Tus sensaciones y tus dudas"], "mensual-paso2"),
    ("Paso 2 · Tus sensaciones y tus dudas", "¿Cuánto te ha costado la dieta?",
     ["¿Cuánto te ha costado la dieta?",
      "Lo que te ha costado a ti, no lo que hayas cumplido",
      "Nada, comiendo así es facilísimo",
      "Me cuesta, pero no fallo",
      "Sí, baja mis macros porque no llego por mucho que me esfuerce"], "mensual-paso2"),
    ("Paso 2 · Tus sensaciones y tus dudas", "¿Y máquinas que no tienes?",
     ["¿Y máquinas que no tienes?",
      "si ha entrado alguna nueva, dímelo", "Añadir máquina"], "mensual-paso2"),
    ("Paso 2 · Tus sensaciones y tus dudas", "El grado de compromiso",
     ["grado de compromiso con el programa hasta el momento",
      "de si has dado todo o te quedas con la sensación de haber fallado",
      "Mi compromiso es máximo",
      "He cumplido bastante bien, pero podría haberlo hecho mejor",
      "asumo mi responsabilidad y las próximas 4 semanas voy a por todas",
      "No he sido capaz de llevarlo a cabo"], "mensual-paso2"),
    ("Paso 2 · Tus sensaciones y tus dudas", "Las expectativas, de 0 a 10",
     ["¿el programa está cumpliendo tus expectativas?",
      "No, esperaba más", "Genial, mejor imposible"], "mensual-paso2"),
    ("Paso 2 · Tus sensaciones y tus dudas", "Tu objetivo ahora",
     ["Tu objetivo ahora", "¿Ha cambiado en algo respecto al mes pasado?",
      "Si dices que sí, te pregunto cuál"], "mensual-paso2"),
    ("Paso 2 · Tus sensaciones y tus dudas", "Dudas o lo que quieras contarme",
     ["Dudas o lo que quieras contarme", "Ahora es el momento y el lugar"], "mensual-paso2"),
    ("Paso 2 · Tus sensaciones y tus dudas", "Los ejercicios que dan molestias",
     ["Quita los que ya no y añade los nuevos"], "mensual-paso2"),

    ("Paso 3 · Tus fotos y tus medidas", "El rótulo y su subtítulo",
     ["Tus fotos y tus medidas", "Lo último, y es lo que más me dice a mí"], "mensual-paso3"),
    ("Paso 3 · Tus fotos y tus medidas", "El porqué de las fotos",
     ["siempre en el mismo sitio y con la misma luz que las anteriores",
      "Es lo único que me deja comparar"], "mensual-paso3"),
    ("Paso 3 · Tus fotos y tus medidas", "El plazo, en su aviso",
     ["Recuerda que tienes como fecha límite"], "mensual-paso3"),
    ("Paso 3 · Tus fotos y tus medidas", "El metro y el vídeo",
     ["Con el metro pegado y sin apretar", "Aquí tienes el vídeo"], "mensual-paso3"),
    ("Paso 3 · Tus fotos y tus medidas", "Las diez medidas",
     ["Hombros", "Mesoesternal", "Cintura", "Cadera", "Gemelo"], "mensual-paso3"),
    ("Paso 3 · Tus fotos y tus medidas", "Adónde van a parar",
     ["van a", "Mi evolución", "Ahí es donde las vas a ver comparadas"], "mensual-paso3"),
    ("Paso 3 · Tus fotos y tus medidas", "El botón de enviar",
     ["Enviar reporte"], "mensual-paso3"),

    ("Paso 4 · Tu plan nuevo y mi feedback", "El rótulo del paso",
     ["Tu plan nuevo y mi feedback directo"], "mensual-paso4"),
    ("Paso 4 · Tu plan nuevo y mi feedback", "Ya lo tienes · Tu informe del mes",
     ["Ya lo tienes", "Tu informe del mes", "análisis objetivo",
      "cuantos más datos registres, mejores informes recibirás",
      "Ver mi informe"], "mensual-paso4"),
    ("Paso 4 · Tu plan nuevo y mi feedback", "Nuevo programa y feedback",
     ["Antes del próximo", "Nuevo programa y feedback",
      "Analizamos tus respuestas, comparamos fotos y métricas",
      "para las próximas 4 semanas"], "mensual-paso4"),
    ("Paso 4 · Tu plan nuevo y mi feedback", "Y mientras tanto, mírate",
     ["Y mientras tanto, mírate"], "mensual-paso4"),
    ("Paso 4 · Tu plan nuevo y mi feedback", "Sin informe publicado, la tarjeta no sale",
     ["Ya lo tienes"], "mensual-paso4-sin"),

    ("Y si no tengo sus check-in", "El aviso de que no los tiene",
     ["No tengo todos los datos de tus check-in diarios",
      "así que te lo pregunto aquí"], None),
    ("Y si no tengo sus check-in", "Las cinco preguntas con estrellas",
     ["¿En qué grado has cumplido la dieta?",
      "¿Has entrenado todos los días que tocaba?",
      "¿Has cumplido con el cardio que tenías pautado?",
      "¿Has tomado la suplementación que te correspondía?",
      "Descanso · ¿cómo fue?"], None),
    ("Y si no tengo sus check-in", "Y el botón de continuar",
     ["Continuar"], None),
    ("Y si no tengo sus check-in", "El peso y las fotos se le piden igual",
     ["Cinco preguntas y pasas al paso 2"], None),
]

INFORME = [
    ("Qué es y cuándo le llega", "Se entrega al enviar, con el hueco vacío",
     ["En estos momentos estamos revisando tu reporte mensual"], "informe-enviado"),
    ("Qué es y cuándo le llega", "Y el mismo informe, completado",
     ["Jesús"], "informe-contestado"),

    ("La cabecera", "El periodo y el nombre",
     ["Tu informe mensual", "días"], "informe-enviado"),

    ("1 · Dónde estás", "Su objetivo y su ciclo",
     ["Tu objetivo", "Tu ciclo", "Semana"], "informe-enviado"),

    ("2 · Tu feedback y tu programa nuevo", "El hueco, en gris y con la hora",
     ["Antes del", "te mandamos todo"], "informe-enviado"),
    ("2 · Tu feedback y tu programa nuevo", "Y luego tu texto firmado",
     ["Has bajado 2,8 kg cumpliendo 22 de 28 días", "Jesús Gallego"], "informe-contestado"),

    ("3 · Tu peso", "Con qué empezó el mes y con cuál lo acaba",
     ["Tu peso", "Empezaste el mes en", "Lo acabas en",
      "Desde tu último reporte"], "informe-enviado"),
    ("3 · Tu peso", "Lo que pesaba el día que entró",
     ["Cuando empezaste pesabas", "Desde que empezaste"], "informe-enviado"),
    ("3 · Tu peso", "El porcentaje que ha bajado cada semana",
     ["Porcentaje del peso total que has ido bajando por semana",
      "Semana 1", "Semana 4"], "informe-enviado"),

    ("4 · Tus medidas", "Las diez, contra el mes pasado y la primera toma",
     ["Tus medidas", "Diez tomas", "Mes ant.", "1ª toma"], "informe-contestado"),

    ("5 · Tu porcentaje de grasa", "Cada 12 semanas, y cuándo se midió",
     ["Tu porcentaje de grasa", "Se mide al final de cada ciclo, cada 12 semanas",
      "La última medición"], "informe-enviado"),

    ("6 · Tus fotos", "Dos, y las elige él",
     ["Tus fotos", "Frente", "Espaldas", "Perfil"], "informe-enviado"),

    ("7 · Lo que has hecho", "Dietas, entrenos, cardios y suplementación",
     ["Lo que has hecho", "Dietas completas", "Cuadradas al 100 %",
      "Comiste de más"], "informe-enviado"),

    ("8 · Tu día tipo", "La combinación que más repite en cada comida",
     ["Tu día tipo", "La combinación que más repites en cada comida, y cuántos días"],
     "informe-enviado"),
    ("8 · Tu día tipo", "Con su momento del día y sus cantidades",
     ["Mañana", "Mediodía", "Noche"], "informe-enviado"),
    ("8 · Tu día tipo", "Y cuando cambia casi cada día",
     ["Cambia casi cada día", "combinaciones distintas"], "informe-enviado"),

    ("9 · Preferencias concretas de alimentos", "Sus tres de cada, con las veces",
     ["Preferencias concretas de alimentos",
      "las veces que las has puesto", "Proteína", "Hidratos", "Grasas"], "informe-enviado"),

    ("10 · Extras registrados", "Lo que apuntó y qué día",
     ["Extras registrados"], "informe-enviado"),

    ("La regla", "El informe no le pide nada",
     ["Tus fotos"], "informe-enviado"),
]


def main() -> None:
    puntos = []
    for doc, filas in (("mensual", MENSUAL), ("informe", INFORME)):
        for seccion, titulo, frases, escena in filas:
            puntos.append({"doc": doc, "seccion": seccion, "sub": None,
                           "titulo": titulo, "tipo": "estado", "pie": None,
                           "debe_verse": frases, "escena": escena})

    validado = json.load(io.open(os.path.join(RAIZ, "_guia", "_puntos_validado.json"),
                                 encoding="utf-8"))
    for p in validado:
        p.setdefault("escena", None)

    todos = validado + puntos
    destino = os.path.join(RAIZ, "_guia", "_puntos_todos.json")
    with io.open(destino, "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=1)

    por_doc = {}
    for p in todos:
        por_doc[p["doc"]] = por_doc.get(p["doc"], 0) + 1
    print(" · ".join(f"{k}: {v}" for k, v in por_doc.items()))
    print(f"TOTAL: {len(todos)} puntos")
    print(f"(en {destino})")


main()
