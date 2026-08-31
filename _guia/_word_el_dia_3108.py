# -*- coding: utf-8 -*-
"""EL WORD DE «El día»: cada punto del documento, con la prueba de la app al lado.

El documento de Jesus se queda como esta. Esto es lo otro: por cada cosa que pedia, que
pide, que hace hoy el sistema y UNA CAPTURA de la app de verdad, sacada con
`_guia/_pruebas_el_dia_3108.js`.

Uso:  backend/venv/Scripts/python.exe _guia/_word_el_dia_3108.py
"""
import os

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOTOS = os.path.join(RAIZ, "_guia", "_pruebas_el_dia")
SALIDA = os.path.join(os.path.expanduser("~"), "Desktop", "12EN12 - El dia - punto por punto.docx")

NARANJA = RGBColor(0xC9, 0x4A, 0x0C)
GRIS = RGBColor(0x5A, 0x53, 0x4A)
VERDE = RGBColor(0x2B, 0x66, 0x42)


def sombrear(celda, color):
    tc = celda._tc.get_or_add_tcPr()
    sombra = OxmlElement("w:shd")
    sombra.set(qn("w:fill"), color)
    tc.append(sombra)


def titulo(doc, texto, tam=15, color=None, espacio_antes=14):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(espacio_antes)
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run(texto)
    r.bold = True
    r.font.size = Pt(tam)
    if color:
        r.font.color.rgb = color
    return p


def parrafo(doc, texto, tam=10, cursiva=False, color=None, antes=0, despues=4):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(antes)
    p.paragraph_format.space_after = Pt(despues)
    r = p.add_run(texto)
    r.italic = cursiva
    r.font.size = Pt(tam)
    if color:
        r.font.color.rgb = color
    return p


def etiqueta(doc, texto, color=GRIS):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(texto.upper())
    r.bold = True
    r.font.size = Pt(7.5)
    r.font.color.rgb = color
    return p


def cita(doc, texto):
    """Lo que dice el documento, literal."""
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.LEFT
    c = t.rows[0].cells[0]
    sombrear(c, "FBF1E9")
    c.text = ""
    p = c.paragraphs[0]
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(texto)
    r.italic = True
    r.font.size = Pt(9.5)
    return t


def captura(doc, fichero, ancho=3.1, pie=None):
    ruta = os.path.join(FOTOS, fichero)
    if not os.path.exists(ruta):
        parrafo(doc, f"[falta la captura {fichero}]", color=NARANJA)
        return
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    p.add_run().add_picture(ruta, width=Inches(ancho))
    if pie:
        q = doc.add_paragraph()
        q.paragraph_format.space_after = Pt(10)
        r = q.add_run(pie)
        r.font.size = Pt(8)
        r.font.color.rgb = GRIS
        r.italic = True


# ── Los puntos, en el orden del documento ────────────────────────────────────
#
# Cada uno: donde vive en el documento, que pedia, que hace hoy y su captura.
PUNTOS = [
    ("A · EL CHECK-IN DEL DÍA", None, None, None, None, None),

    ("Todas a la vista, sin plegar nada",
     "El check-in del día › la línea bajo el título, y «Las nueve, todas a la vista»",
     "«Todas a la vista, sin plegar nada: nueve preguntas y las notas.»",
     "Se acabó el acordeón. Hasta el 31-08 iba una tarjeta encendida cada vez: se contestaba "
     "una, se plegaba con su resumen y se abría sola la siguiente. Ahora están las ocho "
     "abiertas, con sus estrellas y sus botones.\n\n"
     "Y con el acordeón se cayó el naranja de la tarjeta: marcaba «esta es la que toca», y "
     "con las ocho abiertas no distingue nada. En esta app el naranja quiere decir «te has "
     "pasado», así que ocho tarjetas naranjas se leen como ocho errores.",
     [("A0_pantalla_entera.png", 2.6, "La pantalla entera, con las ocho preguntas abiertas.")]),

    ("Fuera «Sensaciones generales del día»",
     "El check-in del día › «Las nueve, todas a la vista» (ya no está en la lista)",
     "La lista de las nueve ya no la incluye: era la primera pregunta y desaparece.",
     "Se va de la PANTALLA, no de la base. El campo se sigue guardando y el historial de "
     "quien lo tenga contestado lo sigue pintando con sus estrellitas: borrarlo del modelo "
     "dejaría meses de días sin poder enseñarse.\n\n"
     "La pantalla ahora abre directamente por «¿Entrenaste hoy?».",
     [("A1_primera_pregunta.png", 3.0, "La primera pregunta es ya «¿Entrenaste hoy?».")]),

    ("La suplementación entra en la cadena",
     "El check-in del día › «Las nueve, todas a la vista» · 5.ª línea",
     "«¿Tomaste la suplementación que tenías pautada? — Sí · No toda · No ← entra: es la que "
     "faltaba de tus once»",
     "La pregunta existía desde el 24-08 pero era CONDICIONAL: el servidor miraba que su plan "
     "incluyera suplementación y que tuviera protocolo vigente ese día, y solo entonces la "
     "pintaba. Por eso no salía en la columna «como está hoy» del documento: ese cliente no "
     "la tenía.\n\n"
     "Se le quita el candado y se le pregunta a todo el mundo, con el texto nuevo y con «No "
     "toda» en vez de «No todos».",
     [("A2_suplementacion.png", 3.0, "Con su texto nuevo y sus tres opciones.")]),

    ("El subtítulo de los extras",
     "El check-in del día › «Las nueve, todas a la vista» · 6.ª línea",
     "«¿Se te ha escapado algo más hoy? — Si no lo pusiste en el apartado de extras, ponlo "
     "ahora»",
     "Decía «Algo que comieras de más y no pusieras en el apartado “extras”», que describe. "
     "Esta pide. El campo ya llevaba al mismo sitio que los Extras del Inicio, y eso no se "
     "toca.",
     [("A3_extras.png", 3.0, "El subtítulo nuevo, debajo de la pregunta.")]),

    ("El «Te queda por contestar», entero",
     "El check-in del día › «Antes de guardar»",
     "«Lo único que cambia es el texto: sin sensaciones, que ya no existe, y sin el “y 5 "
     "más”. Las ocho enteras.»",
     "Cortaba en tres y añadía «y 5 más». Eso tenía sentido con el acordeón, porque la "
     "pantalla ya decía por dónde ibas; con las ocho abiertas, esta línea es lo único que lo "
     "dice, y un «y 5 más» obliga a releerse la pantalla para saber cuáles.",
     [("A4_pie.png", 3.1, "Las ocho, con la de la suplementación dentro.")]),

    ("El aviso de arriba, en sus dos estados",
     "El check-in del día › «Si le faltan comidas» y «Si no le falta nada»",
     "«Y el aviso de arriba, en sus dos estados. Hoy solo existe el de la izquierda: cuando "
     "no le falta nada, ese hueco se queda vacío.» · «Si “El día, todo bien” era un texto, "
     "este es su sitio: el mismo hueco, en verde.»",
     "El primero ya existía y se queda igual, palabra por palabra: «Te quedan 2 comidas sin "
     "registrar · Intra-entreno · Post-entreno · Puedes cerrarlas antes de seguir». Es "
     "también el trozo que el documento llama «Lo primero que ve» y pone entre los que no se "
     "tocan.\n\n"
     "El segundo es el nuevo. El hueco ya tenía un estado verde, pero decía «Dieta "
     "registrada» y solo salía si había dieta montada. Ese candado existía por algo: un día "
     "al que solo le apuntaron «dos cañas» tiene documento y ninguna comida, y decirle «dieta "
     "registrada» habría sido mentira. Con el texto nuevo el candado se cae, porque lo que se "
     "afirma ha cambiado: «no te queda nada por registrar» es verdad no haya comidas "
     "pendientes, haya montado dieta o no.",
     [("A5b_comidas_sin_registrar.png", 3.1,
       "Si le faltan comidas: montado un día con el intra y el post vacíos, la app los nombra."),
      ("A5_el_dia_todo_bien.png", 3.0,
       "Y si no le falta nada: el mismo hueco, en verde y con dos renglones.")]),

    ("Las notas, suyas o compartidas",
     "El check-in del día › «Las notas, suyas o compartidas»",
     "«Esto es para tu diario. Lo puedes compartir con nosotros o quedártelo para ti», con la "
     "casilla debajo. El cliente decide qué te enseña. Está bien resuelto.",
     "De los tres trozos que el documento marca como «no se tocan», este es el segundo. Se "
     "comprueba que sigue intacto: la frase, la casilla y el sitio, al final y abiertas.",
     [("A7_las_notas.png", 3.1, "Con su frase y su casilla, sin tocar.")]),

    ("Contestar ya no pliega la tarjeta",
     "El check-in del día › consecuencia de «todas a la vista»",
     "—",
     "Antes, contestar apagaba la tarjeta y encendía la siguiente. Ahora contestar solo "
     "guarda el valor: la tarjeta se queda abierta, con su tic, y se puede cambiar la "
     "respuesta sin volver a abrir nada.",
     [("A6_contestada_sigue_abierta.png", 3.0,
       "Contestada «No»: sigue abierta, con su tic y su respuesta marcada.")]),

    ("B · QUÉ PASA CUANDO DEJA DE CERRAR EL DÍA", None, None, None, None, None),

    ("Ese mismo día, desde las 17:00",
     "El check-in del día › «Ese mismo día, desde las 17:00»",
     "«Por la mañana no sale. Se enciende a las 17:00, hora de España: antes no tiene nada "
     "que cerrar, y verla apagada todo el día la convierte en parte del decorado.»",
     "La hora es la de España, no la del reloj del cliente: es la regla de la casa: su reloj "
     "decide qué día vive, España decide plazos y ventanas. Y es el mínimo, no un valor "
     "fijo: el cliente puede retrasarla desde su perfil (turnos de noche), nunca "
     "adelantarla.",
     [("B1_desde_su_hora.png", 3.1, "El estado normal, a partir de su hora.")]),

    ("Tras 2 días perdidos",
     "El check-in del día › «Tras 2 días perdidos»",
     "«¿Cómo fuiste hoy? / Llevas 2 días seguidos sin cerrar, no lo dejes hoy también». Y: "
     "«No lo dejes hoy también es lo que hace el trabajo: le pide el de hoy, no le riñe por "
     "los de atrás.»",
     "La racha cuenta SOLO los días que ya no tienen arreglo: por la mañana el de ayer sigue "
     "abierto, así que no cuenta todavía. Contarlo sería reñirle por algo que aún puede "
     "hacer.",
     [("B2_dos_dias.png", 3.1, "El título no cambia todavía; cambia lo de debajo.")]),

    ("Tras 4 días perdidos",
     "El check-in del día › «Tras 4 días perdidos»",
     "«Llevas 4 días sin cerrar / Retómalo hoy mismo: es de donde salen tus ajustes». Y: "
     "«Aquí se le dice lo que se pierde, y es verdad: cuando llegue su reporte, esos días van "
     "en blanco. Sin riña, que dos días antes le estabas animando.»",
     "Aquí cambia el título, no solo el subtítulo, y por primera vez se le dice lo que se "
     "está perdiendo.",
     [("B3_cuatro_dias.png", 3.1, "Cambia el título y dice qué se pierde.")]),

    ("Tras una semana",
     "El check-in del día › «Tras una semana»",
     "«Llevas una semana sin cerrar el día / Dejo de recordártelo. Si te está costando, "
     "dímelo y lo vemos». Y: «Tu frase, sin el “hasta que vuelvas”: la línea no desaparece. "
     "Si se quitara, se queda sin el único sitio donde se le dice y no vuelve.»",
     "A partir de la semana el texto se queda fijo: deja de escalar, pero la fila sigue ahí "
     "para siempre. A los veinte días dice lo mismo, no algo peor.\n\n"
     "Al sacar esta captura salió un fallo que no estaba en el documento: la fila recortaba "
     "el texto («Dejo de recordártelo. Si te está costando, dímelo y l…»), y esa frase es "
     "justo el trabajo. Se le quitó el recorte.",
     [("B4_una_semana.png", 3.1, "La frase entera, en tres renglones.")]),

    ("C · LA VENTANA DE LA MAÑANA", None, None, None, None, None),

    ("El día, con sus horas",
     "El día que no lo cierra › «El día, con sus horas»",
     "«17:00 — se abre el check-in de hoy. Al día siguiente, hasta las 15:00 — si ayer se "
     "quedó sin cerrar, sale el aviso y lo puede rellenar con la cabeza fresca. 15:00 — ayer "
     "se cierra. Ya no vuelve. 17:00 — se abre el de hoy. Nunca hay dos días abiertos a la "
     "vez, y entre las tres y las cinco hay dos horas de hueco justo para eso.»",
     "Es UNA SOLA VENTANA, como dice el documento: el cierre de un día está abierto desde su "
     "hora hasta las 15:00 del siguiente. De ahí sale todo lo demás, y el tope de arriba se "
     "resuelve solo.\n\n"
     "Esta captura es la franja de las 15:00 a las 17:00, con el servidor de verdad: no hay "
     "ningún día abierto, así que la fila del cierre no está en «Pendiente».",
     [("C3_sin_dia_abierto.png", 2.6,
       "Entre las 15:00 y las 17:00: en «Pendiente» no hay fila de cierre.")]),

    ("A la mañana siguiente, si ayer no lo cerró",
     "El día que no lo cierra › «A la mañana siguiente, si ayer no lo cerró»",
     "«Ayer no cerraste el día / Puedes hacerlo hasta las 3 de la tarde». Y: «Es el único "
     "sitio donde se recupera un día: al día siguiente, con la cabeza fresca. A las tres se "
     "cierra y ya no vuelve.»",
     "Es lo único del documento que no existía de ninguna forma. La fila lleva al día de "
     "AYER, no al de hoy.",
     [("C2_la_manana_siguiente.png", 3.1, "La fila de la mañana."),
      ("C2b_cierre_de_ayer.png", 3.1,
       "Y al tocarla se abre el día de ayer, no el de hoy.")]),

    ("D · LA CONFIGURACIÓN DE LOS AVISOS", None, None, None, None, None),

    ("Los siete interruptores y la hora",
     "La configuración de los avisos › «Todo encendido»",
     "Siete interruptores y un selector de hora, en cuatro grupos: el cierre del día, los "
     "reportes, el peso y cómo te aviso.",
     "Hasta hoy era UNO: «Recordarme cerrar el día · cada día a las 20:00».\n\n"
     "Y apagan de verdad, que era lo importante: «un interruptor que no hace nada enseña que "
     "la configuración miente».",
     [("D1_tarjeta.png", 3.0, "Los cuatro grupos, con sus tres frases de aviso.")]),

    ("La hora: una ventana, no dos cosas",
     "La configuración de los avisos › «La hora: una ventana, no dos cosas»",
     "«Puedes activarla a cualquier hora a partir de las 17:00. Permanecerá activa hasta las "
     "15:00 del día siguiente.» Y: «Tiene un motivo real y es tuyo: los turnos de noche. Al "
     "que sale a las dos de la mañana las 17:00 no le sirven.»",
     "El selector ofrece de las 17:00 a las 23:00 y ni una antes: no se puede cerrar un día "
     "que todavía no ha pasado. Y la frase de debajo es la que explica que la ventana de la "
     "mañana no es un mecanismo aparte, sino la misma.",
     [("D2_selector_de_hora.png", 3.1, "De 17:00 a 23:00, y la frase de la ventana.")]),

    ("Al apagar el cierre del día",
     "La configuración de los avisos › «Al apagar el cierre del día»",
     "«Si lo apagas, no podrás registrar tus datos del día, pero deberás rellenar las "
     "preguntas del reporte quincenal y del reporte mensual para poder recibir tus ajustes.» "
     "Y debajo: «Puedes volver a activarlo cuando quieras.»",
     "Se pregunta antes, con su texto literal y sus dos botones. La segunda línea no es "
     "adorno: «sin ella el interruptor parece una puerta de un solo sentido, y hay gente que "
     "no lo toca por miedo a no poder deshacerlo».\n\n"
     "Encenderlo no pregunta: volver atrás no le quita nada.",
     [("D4_dialogo_al_apagar.png", 3.1, "El diálogo, con «Dejarlo como está» y «Apagarlo».")]),

    ("Los dos del cierre del día son distintos",
     "La configuración de los avisos › «Los dos del cierre del día son distintos»",
     "«Rellenar el cierre del día apagado → la fila no sale nunca. Recordármelo si me lo "
     "salto apagado → la fila sale igual, pero no le insiste: la escalada de los 2, 4 y 7 "
     "días no salta. Hoy no puede elegir eso: o todo o nada.»",
     "Comprobado con el cliente de pruebas, que llevaba 5 días sin cerrar: con «Recordármelo» "
     "apagado, la fila vuelve a decir «Para rellenar al final del día» en vez de «Llevas 4 "
     "días sin cerrar». La escalada la apaga el servidor, no la pantalla.",
     [("D1_tarjeta.png", 3.0, "Los dos, separados, dentro del primer grupo.")]),

    ("E · EL PANEL", None, None, None, None, None),

    ("Una columna de días sin cerrar",
     "El check-in del día › «Los avisos no salen de la app», última línea",
     "«Lo que sí falta está en el panel: una columna de días sin cerrar en Clientes. Dejar de "
     "cerrar suele ser el primer síntoma, y llega antes que el impago.»",
     "La cuenta es la MISMA que la de la fila del Inicio, así que el panel y el cliente no "
     "pueden discrepar. En naranja a partir de cuatro días, que es cuando la app deja de "
     "animarle y le dice lo que se pierde.\n\n"
     "En el tope pone «+60» y no «60»: la cuenta se corta ahí y un número exacto que no es "
     "verdad es peor que uno redondo.",
     [("E1_columna_sin_cerrar.png", 6.2, "La columna «Sin cerrar», en Clientes.")]),

    ("Que se marque a quien lo apagó",
     "La configuración de los avisos › «Duda 7» y «Como te llega hoy»",
     "«Si no se marca, el que ignoró el reporte y el que tenía el aviso apagado te llegan "
     "iguales.» Y: «El que lo ignoró, en rojo. El que apagó los avisos, en gris y dicho. Su "
     "silencio no significa lo mismo.»",
     "Al que apagó el cierre no se le cuentan los días: pone «apagado». Contarlos sería el "
     "mismo error por el otro lado: no se ha dejado nada, es que no lo tiene.\n\n"
     "Y en reportes, el que lo ignoró va en naranja y el que apagó los avisos en gris, con "
     "«Avisos apagados».",
     [("E2_apagado_en_la_tabla.png", 6.2,
       "El mismo cliente con el cierre apagado: la columna lo dice en vez de contar.")]),
]


def main():
    doc = Document()
    est = doc.styles["Normal"]
    est.font.name = "Segoe UI"
    est.font.size = Pt(10)
    for s in doc.sections:
        s.left_margin = s.right_margin = Inches(0.9)
        s.top_margin = s.bottom_margin = Inches(0.8)

    # ── Portada ──
    p = doc.add_paragraph()
    r = p.add_run("12EN12 · 31 DE AGOSTO DE 2026")
    r.bold = True
    r.font.size = Pt(8)
    r.font.color.rgb = NARANJA

    t = doc.add_paragraph()
    t.paragraph_format.space_after = Pt(6)
    r = t.add_run("«El día», punto por punto")
    r.bold = True
    r.font.size = Pt(24)

    parrafo(doc,
            "El documento se queda como está. Esto es lo otro: por cada cosa que pide, qué "
            "pedía, qué hace hoy el sistema y una captura de la app de verdad.",
            tam=10.5, color=GRIS, despues=6)
    parrafo(doc,
            "Las capturas están sacadas con la app corriendo y con una cuenta de prueba, no "
            "son maquetas. Las que dependen de la hora se sacan forzando la respuesta del "
            "servidor, que es lo mismo que el navegador recibe a esa hora; la regla de las "
            "horas la prueban 30 casos automáticos con los bordes al minuto (14:59 contra "
            "15:00, y 16:59 contra 17:00).",
            tam=9, color=GRIS, despues=14)

    for punto in PUNTOS:
        nombre, donde, pedia, hace, fotos = punto[0], punto[1], punto[2], punto[3], punto[4]
        if donde is None:      # es un separador de bloque
            titulo(doc, nombre, tam=13, color=NARANJA, espacio_antes=22)
            continue

        titulo(doc, nombre, tam=12, espacio_antes=18)
        parrafo(doc, f"En el documento: {donde}", tam=8, color=GRIS, despues=6)

        if pedia and pedia != "—":
            etiqueta(doc, "lo que pide el documento")
            cita(doc, pedia)

        etiqueta(doc, "cómo está el sistema ahora")
        for trozo in (hace or "").split("\n\n"):
            parrafo(doc, trozo, tam=10)

        etiqueta(doc, "la prueba")
        for fichero, ancho, pie in (fotos or []):
            captura(doc, fichero, ancho, pie)

    # ── Cierre ──
    titulo(doc, "Lo que no se ve en una captura", tam=13, color=NARANJA, espacio_antes=24)
    parrafo(doc,
            "Dos cosas del documento no tienen pantalla que enseñar, y van aquí para que no "
            "parezcan olvidadas.", tam=10)
    parrafo(doc,
            "«Las notificaciones del móvil»: no hay interruptor porque no hay "
            "notificaciones. «Un interruptor que no hace nada enseña que la configuración "
            "miente.» Cuando existan, se añade.", tam=10)
    parrafo(doc,
            "«El aviso que falta: cuando tú le contestas»: el documento dice que no está "
            "diseñado en ninguna parte, y sí lo está. Los cinco casos que nombra ya avisan "
            "hoy, cada uno al guardarse: «Ya tienes tus macros nuevos» (y «Este mes no te "
            "toco nada» si no le tocas nada), «Ya tienes tu rutina», «Tu informe está listo», "
            "«Hemos comentado tu reporte» y el aviso del chat. Y uno más que el documento no "
            "nombra: «Hemos comentado tu check-in».", tam=10)
    parrafo(doc,
            "Lo que sí faltaba era el otro lado: al mandar el reporte se le promete una fecha "
            "—«Antes del viernes tienes tus ajustes nuevos»— y si nadie le contesta no pasa "
            "nada. Ahora salta un aviso al equipo el mismo día prometido y a las 10:00, con "
            "media jornada por delante: el objetivo es que la promesa se cumpla, no dejar "
            "constancia de que se rompió. No se le avisa a él: sería la app anunciándole que "
            "le hemos fallado, y eso no le da sus ajustes.", tam=10)

    doc.save(SALIDA)
    print("Word ->", SALIDA)


if __name__ == "__main__":
    main()
