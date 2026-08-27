# -*- coding: utf-8 -*-
"""La guía de suplementación de Jesús (doc 19-08, bloque 08).

«Lo que hay montado no es la guía. Es mi guía entera»: la de
noteconformesconmenos.com/membresia-elm/suplementacion-recomendada. Aquí vive su
ESTRUCTURA: las ocho categorías con su orden y sus filtros, y el descuento. Las fichas
son las de `db.supplements` (importadas de esa misma web), cada una con su `seccion`.

LO QUE FALTA POR TRAER DE LA WEB (la página está detrás del login de la membresía y la
sesión la tiene que abrir Francisco): la explicación literal de cada categoría salvo la
de Básicos -- que el propio doc cita --, el texto de entrada, y a qué sección pertenece
cada una de las fichas. Hasta entonces las explicaciones vacías NO se pintan (nada de
inventar textos de Jesús) y las fichas sin sección salen en un solo listado.
"""

# Las ocho, en el orden del doc. `subfiltros` solo en Salud. Las explicaciones son las de
# la web, LITERALES (traidas el 20-08 con la sesion de Francisco); solo se les quita el
# «Nombre:» del principio porque la pantalla ya pone el nombre encima.
#: ALIMENTOS VA ANTES QUE BASICOS (punto 186 del 27-08). «Lo primero es comida -- porque en
#: realidad son eso, alimentos -- y solo despues empiezan los suplementos de verdad. Eso baja
#: el liston: el que llega con miedo a los botes ve primero lo que ya se come.»
#: Las frases de cada una NO se tocan (punto 189).
SECCIONES = [
    {"clave": "alimentos", "nombre": "Alimentos", "orden": 1,
     "explicacion": "Porque en realidad son eso, alimentos. De hecho, en la calculadora "
                    "aparecen clasificados como tal."},
    {"clave": "basicos", "nombre": "Básicos", "orden": 2,
     "explicacion": "Los que sí o sí te recomendaría (aunque ninguno es obligatorio, "
                    "estos son los primeros que cogería)."},
    {"clave": "rendimiento", "nombre": "Rendimiento", "orden": 3,
     "explicacion": "Para mejorar la calidad de los entrenamientos. Después de los "
                    "básicos, son los siguientes que recomiendo."},
    {"clave": "salud", "nombre": "Salud", "orden": 4,
     "explicacion": "Suplementos que contribuyen al bienestar general. Están divididos "
                    "en subcategorías según el órgano principal al que ayudan o la "
                    "patología que buscan revertir.",
     "subfiltros": ["Colesterol", "Digestivo", "Glucosa", "Hepático", "Salud ósea", "Sistema inmune"]},
    {"clave": "volumen", "nombre": "Volumen", "orden": 5,
     "explicacion": "Diseñados para cuando el objetivo es subir de peso."},
    {"clave": "definicion", "nombre": "Definición", "orden": 6,
     # En la web la linea se titula «Quemadores de grasa (definición)»; el nombre de
     # catalogo del doc es Definición.
     "explicacion": "Pensados para la etapa de pérdida de grasa."},
    {"clave": "descanso", "nombre": "Descanso", "orden": 7,
     "explicacion": "Los que mejoran la calidad de tu sueño y tu recuperación."},
]

#: EL TEXTO DE ENTRADA DE LA GUIA (punto 182 del 27-08), sus tres lineas y ninguna mas.
#:
#: Hasta hoy se servia el que hay guardado en `app_state.guia_suplementacion`, importado de su
#: web, y llevaba DOS PARRAFOS QUE EL PUNTO 182 TIRA: el que vende el Catalogo Premium dentro
#: de lo que el cliente ya ha pagado, y el «*IMPORTANTE» del descuento (que ya se filtraba en
#: la pantalla, porque va justo debajo en su propio bloque). Ademas reescribio las tres que se
#: quedan, asi que no vale con recortar: el texto bueno es este.
#:
#: El de la base NO se toca -- sigue ahi, por si algun dia se quiere volver a el --, solo deja
#: de mandar.
TEXTO_DE_LA_GUIA = (
    "Estos son los suplementos que yo más recomiendo con pautas exactas de uso.\n"
    "Están organizados por categorías según su función.\n"
    "En condiciones normales, te recomiendo empezar por los básicos."
)

#: Y EL DEL QUE ESTA ESPERANDO SU PAUTA (punto 183). Va arriba del todo, en modo aviso.
#: Sin el «empieza por los basicos»: «si se lo vas a decir tu, no tiene sentido mandarle a
#: empezar por su cuenta. La guia ahi es para mirar, no para empezar.»
AVISO_ESPERANDO = "Te lo estamos preparando. Te avisamos en cuanto esté."
TEXTO_MIENTRAS_ESPERA = (
    "Mientras tanto, aquí tienes todo lo que uso y recomiendo, con pautas exactas de uso."
)

# «GALLEGOVIP de FullGas, 20 %, activo mientras dure la suscripción.»
DESCUENTO = {
    "codigo": "GALLEGOVIP",
    "tienda": "FullGas",
    "porcentaje": 20,
    "nota": "Activo mientras dure tu suscripción.",
}


def partir_ficha(descripcion: str) -> dict:
    """La descripción importada de la web, partida en Qué es · ¿Cuándo? · ¿Cuánto?.

    Las fichas de `db.supplements` traen los tres campos fundidos en una sola cadena
    («... ¿Cuándo? ... · ¿Cuánto? ...»). Se parte por los rótulos, que son los de la
    propia web; lo que vaya delante del primero es el «qué es». Si no hay rótulos, todo
    es «qué es»: no se inventa nada.
    """
    texto = (descripcion or "").strip()
    que_es, cuando, cuanto = texto, None, None
    if "¿Cuándo?" in texto:
        que_es, resto = texto.split("¿Cuándo?", 1)
        if "¿Cuánto?" in resto:
            cuando, cuanto = resto.split("¿Cuánto?", 1)
        else:
            cuando = resto
    elif "¿Cuánto?" in texto:
        que_es, cuanto = texto.split("¿Cuánto?", 1)

    limpiar = lambda s: (s or "").strip().strip("·").strip() or None
    return {"que_es": limpiar(que_es), "cuando": limpiar(cuando), "cuanto": limpiar(cuanto)}
