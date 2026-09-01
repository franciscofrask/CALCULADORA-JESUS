# -*- coding: utf-8 -*-
"""Monta el artifact del repaso CON LAS CAPTURAS DE LA APP.

La version anterior probaba cada punto con `git grep`. Eso no prueba nada: encontro «Te
ajusto las cantidades sin pasarme de tus macros» y esa frase solo estaba EN UN COMENTARIO,
mientras la pantalla decia otra cosa. Aqui la prueba de cada punto es su captura, sacada
de la app corriendo (`_pruebas_en_pantalla.js`).

Uso:  ./backend/venv/Scripts/python.exe _guia/_armar_artifact_pruebas.py
"""
import base64
import html
import io
import json
import os

from PIL import Image

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANTALLAS = os.path.join(RAIZ, "_guia", "_pruebas_pantalla")
SALIDA = os.path.join(RAIZ, "_guia", "_repaso_con_capturas.html")


def imagen(ruta, ancho=560, calidad=68):
    """La captura, encogida y en base64. Sin CDN: el artifact tiene que bastarse solo."""
    if not ruta or not os.path.exists(ruta):
        return None
    im = Image.open(ruta).convert("RGB")
    if im.width > ancho:
        im = im.resize((ancho, round(im.height * ancho / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=calidad, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def esc(x):
    return html.escape(str(x or ""))


# ── LO QUE DICE CADA DOCUMENTO, PARA CADA PUNTO CAPTURADO ───────────────────
DICE = {
    "llevas": ("validado", "1 · Inicio", "Abre en Llevas, no en Macros",
               "«Entra y ve 146 · 69 · 49: por dónde va hoy, y lo que le queda.»"),
    "extras-titulo": ("validado", "1 · Inicio", "Extras: qué apuntar",
                      "«Si comes algo que no está en tu dieta del día, ponlo aquí, por pequeño que sea.»"),
    "extras-o-si-no": ("validado", "1 · Inicio", "Extras: el buscador delante, la caja detrás",
                       "«o si no está», entre los dos."),
    "extras-a-mano": ("validado", "1 · Inicio", "Extras: qué pasa con lo que escribe a mano",
                      "«Lo que pongas a mano no cuenta en tus macros, simplemente queda el registro. Lo que busques, sí.»"),
    "cola": ("validado", "5 · La cola de Inicio", "La línea del día",
             "«Una línea, la del día.» El reporte, cuando toca, entra encima."),
    "numeros-nutricion": ("validado", "1 · Nutrición", "Los números de Nutrición, como los de Inicio",
                          "«44 px y el mismo estirado. Los dos sitios dicen lo mismo igual.»"),
    "comida-por-dentro": ("validado", "1 · Nutrición", "La comida por dentro, en su voz",
                          "«Te ajusto las cantidades sin pasarme de tus macros.»"),
    "cierre-suplementacion": ("validado", "3 · El día", "Entra la suplementación",
                              "«¿Tomaste la suplementación que tenías pautada?»"),
    "cierre-extras": ("validado", "3 · El día", "Y dónde ponerlo si no lo puso antes",
                      "«Si no lo pusiste en el apartado de extras, ponlo ahora»"),
    "cierre-entreno": ("validado", "3 · El día", "¿Entrenaste hoy?", "Una de las nueve."),
    "cierre-cardio": ("validado", "3 · El día", "¿Hiciste cardio?", "Una de las nueve."),
    "cierre-movimiento": ("validado", "3 · El día", "¿Te moviste lo suficiente?", "Una de las nueve."),
    "cierre-descanso": ("validado", "3 · El día", "¿Cómo descansaste la noche de ayer?", "Una de las nueve."),
    "cierre-energia": ("validado", "3 · El día", "Niveles de energía durante el día", "Una de las nueve."),
    "cierre-hambre": ("validado", "3 · El día", "Hambre / ansiedad con la dieta", "Una de las nueve."),
    "cierre-notas": ("validado", "3 · El día", "Las notas, se quedan igual",
                     "«Esto es para tu diario. Lo puedes compartir con nosotros o quedártelo para ti.»"),
    "cierre-falta": ("validado", "3 · El día", "Antes de guardar, las ocho enteras",
                     "Sin cortar con «y 5 más»."),
    "cierre-peso": ("validado", "4 · El peso", "El peso sale del cierre del día",
                    "«El campo, en Mi evolución. Es el único sitio donde el peso se escribe.»"),
    "cierre-sensaciones": ("validado", "3 · El día", "Salen las sensaciones generales del día",
                           "«Salen las sensaciones del día y el peso.»"),
    "avisos-cierre": ("validado", "4 · Avisos", "Rellenar el cierre del día",
                      "El primero de los siete interruptores, con su hora."),
    "avisos-salto": ("validado", "4 · Avisos", "Recordármelo si me lo salto",
                     "«La fila de la mañana sigue saliendo: es tu ventana para cerrar el día de ayer.»"),
    "avisos-no-apagan": ("validado", "4 · Avisos", "El quincenal y el mensual no se apagan",
                         "«son los que hacen tu ajuste. Aquí solo apagas los recordatorios.»"),
    "avisos-quincenal": ("validado", "4 · Avisos", "Recordatorio del reporte quincenal", "Uno de los siete."),
    "avisos-mensual": ("validado", "4 · Avisos", "Recordatorio del reporte mensual", "Uno de los siete."),
    "avisos-peso": ("validado", "4 · Avisos", "Recordatorios del peso", "Uno de los siete."),
    "avisos-app": ("validado", "4 · Avisos", "Avisos en la app / Por correo",
                   "«Lo que tengas pendiente seguirá saliendo en Inicio. Aquí solo apagas los avisos.»"),
    "fullgas": ("validado", "2 · Los textos", "El código de FullGas",
                "«Lo tendrás activo mientras dure tu suscripción, con un 20 % en toda la web.»"),
    "mis-suplementos-titulo": ("validado", "2 · Los textos", "El nombre: Mis suplementos",
                               "«MIS SUPLEMENTOS», y no «Tu suplementación»."),
    "guia-suplementos": ("validado", "2 · Los textos", "El texto de la guía de suplementos",
                         "«Estos son los suplementos que yo más recomiendo con pautas exactas de uso… te recomiendo empezar por los básicos.»"),
    "mis-suplementos": ("validado", "2 · Los textos", "Suplementos: sin mandar al chat",
                        "«Todavía no tienes tu plan de suplementación personalizado»"),
    "mis-suplementos-espera": ("validado", "2 · Los textos", "Y quién lo está haciendo",
                               "«Estamos en ello, te avisamos en cuanto esté.»"),
    "rutina-espera": ("validado", "2 · Los textos", "La rutina que todavía no está",
                      "«Estamos en ello, te avisamos en cuanto esté.» Sin mandarle al chat."),
    "error-carga": ("validado", "2 · Los textos", "El aviso de cuando algo falla",
                    "«Esto parece cosa nuestra, no tuya. Inténtalo una vez más y, si la cosa sigue igual, escribe por el chat.»"),
    "frase-almendras": ("validado", "2 · Las tres frases", "Almendras: «Su proteína no te cuenta»",
                        "Una de las tres que marcó como intocables."),
    "que-te-cuenta-almendras": ("validado", "2 · Las tres frases", "Lo que dice hoy la ficha de las almendras",
                                "En su sitio, la app dice «Te cuenta la grasa»."),
    "tramo": ("validado", "1 · Nutrición", "El tramo en el que está, marcado",
              "«El suyo en naranja. De un vistazo sabe que hoy no le cuenta.»"),
    "frase-pollo": ("validado", "2 · Las tres frases", "Pollo: «Te cuentan los tres»",
                    "La segunda de las tres."),
    "frase-lechuga": ("validado", "2 · Las tres frases", "Lechuga: «No te cuenta nada: come lo que quieras»",
                      "La tercera, que antes no existía."),
}

# Lo que se ve en vez de lo que pedia, cuando no coincide.
EN_SU_LUGAR = {
    "comido": None,
    "comida-por-dentro": "La pantalla dice «Ajusta las cantidades sin pasarse de tus macros», "
                         "en impersonal. Su frase existe en el código, pero solo dentro de un "
                         "comentario: el punto 193 del 27-08 la cambió y su documento del 1-09 "
                         "la vuelve a pedir.",
    "frase-almendras": "La ficha dice «Te cuenta la grasa». La coletilla «Su proteína no te "
                       "cuenta» se quitó a propósito el 27-08 (punto 147: «el “solo” ya lo dice, "
                       "y es una línea menos»), y su documento del 1-09 la marca como intocable.",
    "avisos-peso": "El interruptor está, pero se llama «Recordatorio de los días de pesada».",
    "cierre-peso": "Sigue en el cierre del día, con su campo y su selector de día.",
}

# Las capturas de pantalla completa de los otros dos documentos.
GRANDES = [
    ("mensual", "Paso 1 · Actualizar tus datos", "_guia/_mensual_4pasos/1_paso1.png",
     "La cabecera «Son 4 pasos», el selector de periodo, el peso, lo que ha hecho, cómo se "
     "ha sentido y el hueco de la dieta, con sus dos botones."),
    ("mensual", "Paso 1 · desde que empezaste", "_guia/_mensual_4pasos/2_desde_que_empezaste.png",
     "El selector cambia el bloque entero: 68 días en vez de 28, y los huecos se quedan."),
    ("mensual", "Paso 2 · Tus sensaciones y tus dudas", "_guia/_mensual_4pasos/3_paso2.png",
     "«¿Cuánto te ha costado la dieta?» con sus cuatro salidas, las máquinas, el grado de "
     "compromiso, las expectativas de 0 a 10 y «Dudas o lo que quieras contarme»."),
    ("mensual", "Paso 3 · Tus fotos y tus medidas", "_guia/_mensual_4pasos/4_paso3.png",
     "Las tres fotos con su porqué, el plazo en su aviso, las diez medidas y «van a Mi evolución»."),
    ("mensual", "Paso 4 · con el informe publicado", "_guia/_mensual_4pasos/5_paso4_con_informe.png",
     "«Ya lo tienes · Tu informe del mes», con «Ver mi informe ›», y el programa nuevo debajo."),
    ("mensual", "Paso 4 · con el informe pendiente", "_guia/_mensual_4pasos/5_paso4_sin_informe.png",
     "Sin informe que abrir, la tarjeta no sale: no se le dice «ya lo tienes» sin nada que pulsar."),
    ("informe", "Al enviarlo", "_guia/_informe_del_mes/1_al_enviarlo.png",
     "El hueco del feedback en gris y con la hora, y debajo el peso, la grasa, lo que ha "
     "hecho, su día tipo y sus alimentos."),
    ("informe", "Cuando le contestas", "_guia/_informe_del_mes/2_cuando_le_contestas.png",
     "El mismo informe con el bloque de Jesús arriba, firmado, y las diez medidas contra el "
     "mes pasado y contra su primera toma."),
]

DOCS = {
    "validado": ("Todo lo validado antes del 1 de septiembre",
                 "claude.ai/code/artifact/6b67e80c"),
    "mensual": ("El reporte mensual", "claude.ai/code/artifact/3b60d286"),
    "informe": ("El informe del mes", "claude.ai/code/artifact/2f5f6de3"),
}


def main() -> None:
    manifiesto = json.load(io.open(os.path.join(PANTALLAS, "_manifiesto.json"),
                                   encoding="utf-8"))
    # Un punto puede haberse capturado en varias escenas; manda la que lo vio.
    mejor = {}
    for m in manifiesto:
        if m["punto"] not in DICE:
            continue
        previo = mejor.get(m["punto"])
        if previo is None or (m["visto"] and not previo["visto"]):
            mejor[m["punto"]] = m

    filas_por_bloque = {}
    cuenta = {"visto": 0, "no": 0}
    for punto, m in mejor.items():
        doc, bloque, titulo, dice = DICE[punto]
        # `no_deberia`: el documento pide que ESO YA NO ESTÉ. Verlo es el fallo.
        ok = (not m["visto"]) if m["no_deberia"] else m["visto"]
        cuenta["visto" if ok else "no"] += 1
        img = imagen(os.path.join(PANTALLAS, m["imagen"])) if m.get("imagen") else None
        nota = EN_SU_LUGAR.get(punto)
        filas_por_bloque.setdefault((doc, bloque), []).append({
            "titulo": titulo, "dice": dice, "ok": ok, "img": img,
            "escena": m["escena_nombre"], "ruta": m["ruta"], "forzada": m["forzada"],
            "frase": m["frase"], "no_deberia": m["no_deberia"], "nota": nota,
        })

    partes = []
    for clave, (titulo_doc, url) in DOCS.items():
        bloques_html = []
        for (doc, bloque), filas in filas_por_bloque.items():
            if doc != clave:
                continue
            tarjetas = []
            for f in filas:
                estado = ("Visto en pantalla" if f["ok"] and not f["no_deberia"]
                          else "Ya no está" if f["ok"] else
                          "Sigue ahí" if f["no_deberia"] else "No se ve")
                clase = "ok" if f["ok"] else "mal"
                pie = (f'<p class="forzada">Estado forzado · {esc(f["forzada"])}</p>'
                       if f["forzada"] else "")
                nota = f'<p class="nota">{esc(f["nota"])}</p>' if f["nota"] else ""
                img = (f'<img src="{f["img"]}" alt="Captura de {esc(f["titulo"])}" loading="lazy">'
                       if f["img"] else '<p class="sin-foto">Sin captura: la frase no está '
                                        'en la pantalla, así que no hay nada que recortar.</p>')
                tarjetas.append(f"""
        <article class="punto {clase}">
          <div class="txt">
            <span class="chip {clase}">{estado}</span>
            <h4>{esc(f['titulo'])}</h4>
            <p class="dice">{esc(f['dice'])}</p>
            {nota}
            <p class="donde">{esc(f['escena'])} · <code>{esc(f['ruta'])}</code></p>
            {pie}
          </div>
          <figure>{img}</figure>
        </article>""")
            bloques_html.append(f'<section class="bloque"><h3>{esc(bloque)}</h3>'
                                f'{"".join(tarjetas)}</section>')

        grandes = []
        for d, nombre, ruta, texto in GRANDES:
            if d != clave:
                continue
            src = imagen(os.path.join(RAIZ, ruta.replace("/", os.sep)), ancho=430, calidad=60)
            if not src:
                continue
            grandes.append(f"""
        <figure class="grande">
          <img src="{src}" alt="{esc(nombre)}" loading="lazy">
          <figcaption><b>{esc(nombre)}</b> {esc(texto)}</figcaption>
        </figure>""")
        if grandes:
            bloques_html.append('<section class="bloque"><h3>Las pantallas, enteras</h3>'
                                f'<div class="galeria">{"".join(grandes)}</div></section>')

        if bloques_html:
            partes.append(f"""
    <section class="doc">
      <p class="eyebrow">{esc(url)}</p>
      <h2>{esc(titulo_doc)}</h2>
      {''.join(bloques_html)}
    </section>""")

    io.open(SALIDA, "w", encoding="utf-8").write(PLANTILLA.format(
        vistos=cuenta["visto"], fallan=cuenta["no"],
        total=cuenta["visto"] + cuenta["no"], cuerpo="".join(partes)))
    tam = os.path.getsize(SALIDA) / 1024 / 1024
    print(f'{cuenta["visto"]} bien · {cuenta["no"]} mal · {tam:.1f} MB · {SALIDA}')


PLANTILLA = """<title>Los tres documentos, con las capturas</title>
<style>
  :root {{
    --tinta: #17130F; --tinta-2: #5A5049; --papel: #FBF8F5; --papel-2: #F2EDE7;
    --linea: #E2D9D0; --marca: #FF671F; --verde: #1E7A4B; --rojo: #BE3227;
    --sans: ui-sans-serif, -apple-system, "Segoe UI", Roboto, sans-serif;
    --serif: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, ui-serif, serif;
    --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --tinta: #F4EFE9; --tinta-2: #A79C93; --papel: #14110E; --papel-2: #1D1915;
             --linea: #322B25; --verde: #4FBF87; --rojo: #F0736A; }}
  }}
  :root[data-theme="dark"] {{
    --tinta: #F4EFE9; --tinta-2: #A79C93; --papel: #14110E; --papel-2: #1D1915;
    --linea: #322B25; --verde: #4FBF87; --rojo: #F0736A;
  }}
  :root[data-theme="light"] {{
    --tinta: #17130F; --tinta-2: #5A5049; --papel: #FBF8F5; --papel-2: #F2EDE7;
    --linea: #E2D9D0; --verde: #1E7A4B; --rojo: #BE3227;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--papel); color: var(--tinta); font-family: var(--sans);
          font-size: 16px; line-height: 1.55; -webkit-font-smoothing: antialiased; }}
  .envoltorio {{ max-width: 1120px; margin: 0 auto; padding: 0 20px 96px; }}
  .portada {{ padding: 60px 0 36px; border-bottom: 2px solid var(--tinta); }}
  .kicker {{ font-size: 12px; font-weight: 700; letter-spacing: .16em; text-transform: uppercase;
             color: var(--marca); margin: 0 0 12px; }}
  h1 {{ font-size: clamp(32px, 5.5vw, 54px); line-height: 1; margin: 0 0 16px; font-weight: 800;
        letter-spacing: -.02em; text-wrap: balance; }}
  .entradilla {{ font-family: var(--serif); font-size: 19px; max-width: 62ch;
                 color: var(--tinta-2); margin: 0; }}
  .totales {{ display: flex; gap: 30px; margin-top: 26px; flex-wrap: wrap; }}
  .total b {{ display: block; font-size: 38px; line-height: 1; font-weight: 800;
              font-variant-numeric: tabular-nums; }}
  .total span {{ font-size: 12px; font-weight: 700; letter-spacing: .12em;
                 text-transform: uppercase; color: var(--tinta-2); }}
  .total.ok b {{ color: var(--verde); }}
  .total.mal b {{ color: var(--rojo); }}

  .doc {{ padding-top: 52px; }}
  .eyebrow {{ font-family: var(--mono); font-size: 12px; color: var(--tinta-2); margin: 0 0 6px; }}
  .doc h2 {{ font-size: clamp(26px, 4vw, 34px); font-weight: 800; letter-spacing: -.02em;
             margin: 0 0 6px; }}
  .bloque {{ margin-top: 32px; }}
  .bloque > h3 {{ font-size: 12px; font-weight: 700; letter-spacing: .14em;
                  text-transform: uppercase; color: var(--marca); margin: 0 0 4px;
                  padding-bottom: 8px; border-bottom: 1px solid var(--linea); }}

  .punto {{ display: grid; grid-template-columns: minmax(0,1fr) minmax(0,320px); gap: 18px 28px;
            padding: 22px 0; border-bottom: 1px solid var(--linea); align-items: start; }}
  .punto h4 {{ font-size: 17px; font-weight: 700; margin: 8px 0 4px; letter-spacing: -.01em; }}
  .dice {{ font-family: var(--serif); font-style: italic; color: var(--tinta-2); margin: 0;
           font-size: 15px; }}
  .nota {{ font-size: 14px; color: var(--tinta); margin: 10px 0 0; max-width: 60ch;
           border-left: 2px solid var(--rojo); padding-left: 10px; }}
  .donde {{ font-size: 12px; color: var(--tinta-2); margin: 10px 0 0; }}
  .donde code {{ font-family: var(--mono); font-size: 12px; }}
  .forzada {{ font-size: 12px; color: var(--tinta-2); margin: 4px 0 0; font-style: italic;
              max-width: 60ch; }}
  .chip {{ display: inline-block; font-size: 11px; font-weight: 700; letter-spacing: .09em;
           text-transform: uppercase; padding: 3px 10px; border-radius: 4px; color: var(--papel); }}
  .chip.ok {{ background: var(--verde); }}
  .chip.mal {{ background: var(--rojo); }}
  figure {{ margin: 0; }}
  figure img {{ width: 100%; height: auto; display: block; border-radius: 10px;
                border: 1px solid var(--linea); }}
  .sin-foto {{ font-size: 13px; color: var(--tinta-2); margin: 0; padding: 14px;
               border: 1px dashed var(--rojo); border-radius: 10px; }}

  .galeria {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
              gap: 22px; margin-top: 18px; }}
  .grande img {{ border-radius: 10px; }}
  .grande figcaption {{ font-size: 13px; color: var(--tinta-2); margin-top: 8px; }}
  .grande figcaption b {{ color: var(--tinta); display: block; }}

  @media (max-width: 780px) {{ .punto {{ grid-template-columns: 1fr; }} }}
  @media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; }} }}
</style>

<div class="envoltorio">
  <header class="portada">
    <p class="kicker">12EN12 · repaso del 1 de septiembre</p>
    <h1>Los tres documentos, con las capturas</h1>
    <p class="entradilla">
      Cada punto abierto en la app de verdad, buscado en lo que se ve y recortado de la
      pantalla. Un texto en el código no prueba nada: aquí la prueba es la foto.
    </p>
    <div class="totales">
      <div class="total"><b>{total}</b><span>puntos capturados</span></div>
      <div class="total ok"><b>{vistos}</b><span>como los pediste</span></div>
      <div class="total mal"><b>{fallan}</b><span>no coinciden</span></div>
    </div>
  </header>
  {cuerpo}
</div>
"""


main()
