# -*- coding: utf-8 -*-
"""EL JUICIO DE CADA PUNTO QUE NO SALIO ENTERO.

Buscar la frase en la pantalla deja tres resultados que la maquina no sabe distinguir:

  a) la frase no esta porque el punto NO ESTA HECHO,
  b) la frase no esta porque era un dato del ejemplo (un numero, una fecha, la pestaña
     que la maqueta dibuja abierta) y esta cuenta no lo tiene,
  c) la frase no esta porque NO LLEGUE A LA PANTALLA (un clic que no abrio lo que tenia
     que abrir).

Solo la (a) es un fallo. Aqui se dice cual es cual, una por una, y por que. Lo que no se
haya podido comprobar se dice tambien: un «no lo se» apuntado vale mas que un verde falso.

Uso:  ./backend/venv/Scripts/python.exe _guia/_revision_puntos.py
"""
import io
import json
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESTINO = os.path.join(RAIZ, "_guia", "_revision_puntos.json")

# titulo -> (veredicto, nota)
#   ok          lo que falta es del ejemplo: el punto esta
#   ok_invertido lo que falta TENIA que faltar (es el estado viejo)
#   falla       el punto no esta
#   sin_probar  no llegue a esa pantalla o a ese estado
REVISION = {
    "La pantalla de Inicio, entera": ("ok",
        "Lo que falta («Proteína · tu objetivo») solo sale en la pestaña Macros, y la app "
        "abre en Llevas, que es justo lo que pide el punto de al lado."),
    "Abre en Macros, y quedó en Llevas": ("ok",
        "Los «146 de 175» son del ejemplo: salen cuando hay comidas marcadas y esta cuenta "
        "no tiene ninguna. Lo que se comprueba -- que abre en Llevas -- se ve."),
    "Los números, más altos y menos gordos": ("ok",
        "Los tres números viven en la pestaña Macros. El tamaño y el estirado los pone "
        "`.numero-grande`, que es la misma clase en Inicio y en Nutrición."),
    "Un día cualquiera, desde las 17:00": ("ok",
        "«Para rellenar al final del día» es el subtítulo de la línea cuando el día está "
        "abierto. Esta cuenta ya lo cerró, así que su línea dice «Ayer no cerraste el día»."),
    "En cuanto lo manda": ("ok",
        "La línea del día queda sola, que es lo que dice el punto. El resto de lo que falta "
        "es texto del propio documento, no de la pantalla."),
    "Y así queda la pantalla al pulsar el +": ("sin_probar",
        "El clic no llegó a abrir el cuadro de extras: es un fallo del guion, no de la app."),
    "Extras del día — con el buscador delante": ("ok",
        "Se ve entero en Inicio y en Nutrición (las tres frases y el «o si no está»); en "
        "esta escena el cuadro no se llegó a abrir."),
    "Y así queda cuando ya ha apuntado algo": ("ok",
        "Los dos extras se pintan y el día cuenta con ellos. Lo que falta es la pestaña "
        "Macros otra vez."),
    "Miércoles, desde las 10:00 nueva": ("falla",
        "La línea del reporte no entra ARRIBA: en la cola de Inicio va la última, detrás "
        "del cierre, del perfil y de los preferentes. Y su texto no es el del documento."),
    "Jueves a las 17:00, si aún no lo ha mandado nueva": ("falla",
        "Mismo sitio y mismo texto: no está el «Solo recordarte que tienes hasta hoy a las ocho»."),
    "A la mañana siguiente, si ayer no lo cerró nueva": ("ok", None),
    "Tras 2 días perdidos nueva": ("sin_probar",
        "La frase la compone el servidor a partir de los días sin cerrar, y el guion solo "
        "puede cambiar el número DESPUÉS de que la componga. Para verla hace falta una "
        "cuenta que de verdad lleve dos días sin cerrar."),
    "Tras 4 días perdidos nueva": ("sin_probar", "Igual que la de dos días."),
    "Tras una semana nueva": ("sin_probar", "Igual que la de dos días."),
    "Los números de Nutrición, como los de Inicio": ("ok",
        "Los tres números están y con el mismo tamaño. Lo que falta («faltan 29», «válido "
        "−1») son los números del ejemplo."),
    "Una comida por dentro": ("falla",
        "La comida se abre y se ve, pero la frase es «Ajusta las cantidades sin pasarse de "
        "tus macros», en impersonal. La suya solo existe dentro de un comentario."),
    "El cierre del día": ("ok",
        "Las nueve preguntas y las notas se ven. El aviso de las comidas sin registrar "
        "necesita comidas sin marcar, y esta cuenta no tiene."),
    "El aviso de arriba, si le faltan comidas": ("sin_probar",
        "Hace falta un día con comidas sin marcar. Lo que sí se comprueba es lo contrario: "
        "«El día, todo bien» sale cuando no falta nada."),
    "Si no le falta nada nueva": ("ok", None),
    "Las notas — se queda igual": ("ok", None),
    "Antes de guardar, hoy": ("ok_invertido",
        "Es el estado VIEJO. Que no esté es lo correcto: ya no nombra las sensaciones ni "
        "corta con «y 5 más»."),
    "Antes de guardar, como queda": ("ok",
        "La línea sale con las que falten; en la captura estaba todo contestado. Se ve en "
        "la escena del cierre, con su lista entera."),
    "Mi perfil · Avisos nueva": ("ok",
        "Los siete interruptores y el selector de hora están. Lo que falla es la "
        "comparación: el documento mete espacios donde la pantalla no los tiene."),
    "Al apagar el cierre nueva": ("sin_probar",
        "El interruptor no llegó a abrir el aviso: el guion no encontró el control."),
    "El campo, en Mi evolución nueva": ("falla",
        "En Mi evolución no hay campo de peso: se suben fotos, medidas y grasa. El peso "
        "sigue escribiéndose en el cierre del día, que es de donde el documento lo saca."),
    "Miércoles por la mañana nueva": ("sin_pantalla", None),
    "Jueves por la mañana nueva": ("sin_pantalla", None),
    "Y a las 12:00 se apaga nueva": ("sin_pantalla", None),
    "Martes · el primero nueva": ("sin_pantalla", None),
    "Viernes · si le falta una pesada nueva": ("sin_pantalla", None),
    "Miércoles de la semana 1 nueva": ("sin_pantalla", None),
    "Suplementos: el nombre y lo del chat": ("ok", None),
    "La rutina sin asignar también manda al chat": ("ok", None),
    "«Tu plan no incluye rutina» — y debajo se la promete": ("sin_probar",
        "No se llegó al estado del que no lleva rutina en su plan."),
    "El aviso de cuando algo falla": ("ok", None),
    "El texto de la guía de suplementos": ("ok",
        "La frase entera se ve en la pantalla (comprobado en la pasada anterior); aquí "
        "falla la comparación por los espacios que el documento mete alrededor de las "
        "negritas."),
    "El texto del código de FullGas": ("ok", None),
    "Dos frases que marcaste como intocables, cambiadas": ("falla",
        "Dos de las tres se ven en su ficha: «Te cuentan los tres» y «No te cuenta nada: "
        "come lo que quieras». La de las almendras NO: la ficha dice «Te cuenta la grasa». "
        "Se quitó a propósito el 27-08 y su documento la vuelve a pedir."),
    "El tramo en el que está, marcado": ("ok",
        "Los tres tramos están y el suyo va en naranja. La comparación falla porque en la "
        "pantalla cada tramo son dos trozos («de 20 a 40 g» y «la mitad») y el documento "
        "los junta en una línea."),
    "Paso 1 · Confirmar nueva": ("falla", "El quincenal no tiene pasos: es el formulario de siempre."),
    "Paso 2 · Contar nueva": ("falla", "Lo mismo."),
    "Paso 3 · Recibir nueva": ("falla", "Lo mismo. Y no existe el tercer paso, que es donde se le promete la hora."),
    "Con sus check-in nueva": ("falla", "Lo mismo."),
    "Sin check-in suficientes nueva": ("falla",
        "Y esta es la que más falta hace: al que perdió días no se le pregunta con estrellas, "
        "se le deja el formulario igual."),
    "Pendiente": ("ok", "La tarjeta sale en naranja con «Empezar»; lo que falla es el «›»."),
    "Hecho": ("falla",
        "La tarjeta dice «Ya lo mandaste. Lo estamos mirando», que no compromete a nada. "
        "Falta la suya, la que le da una hora."),
    "Miércoles, a las 10:00 · cuando se abre nueva": ("sin_pantalla", None),
    "Jueves por la mañana · el recordatorio nueva": ("sin_pantalla", None),
    "Jueves, de 20:00 a 24:00 nueva": ("sin_pantalla", None),
    "El aviso de que no toca reporte": ("sin_pantalla", None),
    "El aviso del peso": ("sin_pantalla", None),
    "La fila del peso en Inicio": ("sin_pantalla", None),
    "Se abre el quincenal": ("sin_pantalla", None),
    "El recordatorio del último día": ("sin_pantalla", None),
    "Cierra el quincenal": ("falla", "Es el texto de la tarjeta en Hecho, que no está."),
    "Si le falta una pesada": ("sin_pantalla", None),
    "Tú ajustas": ("sin_pantalla", None),
    "Se abre el mensual": ("ok", "El mensual se abre y se ve entero; el punto es del calendario."),
    "Vuelve el mensual": ("sin_pantalla", None),

    # ── El reporte mensual ─────────────────────────────────────────────────
    "Los dos botones del paso": ("ok",
        "Están los dos. Cuando el peso viene vacío, el paso abre el campo solo y el botón "
        "dice «Ya está» en vez de «Modificar», que es el mismo botón."),
    "Los ejercicios que dan molestias": ("sin_probar",
        "El bloque de lesiones solo sale a quien lo lleva en su plan, y esta cuenta no."),
    "Sin informe publicado, la tarjeta no sale": ("ok_invertido",
        "Que «Ya lo tienes» NO esté es justo lo que se comprueba: sin informe que abrir, la "
        "tarjeta no se pinta."),

    # ── El informe del mes ─────────────────────────────────────────────────
    "El porcentaje que ha bajado cada semana": ("sin_probar",
        "El cliente del ejemplo no cambió de peso en el mes, así que el reparto no se pinta "
        "(sin cambio no hay nada que repartir). Las reglas están cubiertas por sus pruebas."),
    "Lo que apuntó y qué día": ("sin_probar",
        "El cliente del ejemplo no apuntó ningún extra en el periodo."),
}


def main() -> None:
    with io.open(DESTINO, "w", encoding="utf-8") as f:
        json.dump(REVISION, f, ensure_ascii=False, indent=1)
    from collections import Counter
    c = Counter(v[0] for v in REVISION.values())
    print(f"{len(REVISION)} puntos revisados a mano · {dict(c)}")


main()
