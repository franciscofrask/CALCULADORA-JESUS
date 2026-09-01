# -*- coding: utf-8 -*-
"""El artifact del repaso COMPLETO: los 113 puntos de los tres documentos, con su captura.

Cada punto lleva:
  - lo que el documento manda que se vea (sus frases, tal cual),
  - cuales de esas frases estaban en la pantalla y cuales no,
  - y el recorte de la app donde se ven.

Los puntos sin pantalla que mirar salen aparte: no es un hueco del repaso, es el resultado.

Uso:  ./backend/venv/Scripts/python.exe _guia/_armar_artifact_completo.py
"""
import base64
import html
import io
import json
import os

from PIL import Image

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTURAS = os.path.join(RAIZ, "_guia", "_capturas")
SALIDA = os.path.join(RAIZ, "_guia", "_repaso_completo.html")

DOCS = {
    "validado": ("Todo lo validado antes del 1 de septiembre",
                 "claude.ai/code/artifact/6b67e80c",
                 "Dieciséis secciones. Lo cerrado y validado con Jesús antes del 1 de septiembre."),
    "mensual": ("El reporte mensual", "claude.ai/code/artifact/3b60d286",
                "Los cuatro pasos del reporte que manda, y sus dos variantes."),
    "informe": ("El informe del mes", "claude.ai/code/artifact/2f5f6de3",
                "Los diez bloques de lo que recibe al mandarlo, en sus dos estados."),
}

ETIQUETA = {"ok": "Visto en pantalla", "falla": "No está",
            "sin_probar": "Sin comprobar", "sin_pantalla": "No hay pantalla"}
CLASE = {"ok": "ok", "falla": "mal", "sin_probar": "medias", "sin_pantalla": "gris"}


def imagen(nombre, ancho=520, calidad=68):
    ruta = os.path.join(CAPTURAS, nombre or "")
    if not nombre or not os.path.exists(ruta):
        return None
    im = Image.open(ruta).convert("RGB")
    if im.width > ancho:
        im = im.resize((ancho, round(im.height * ancho / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=calidad, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def esc(x):
    return html.escape(str(x or ""))


def main() -> None:
    puntos = json.load(io.open(os.path.join(RAIZ, "_guia", "_puntos_todos.json"),
                               encoding="utf-8"))
    manifiesto = {}
    ruta_manifiesto = os.path.join(CAPTURAS, "_manifiesto.json")
    if os.path.exists(ruta_manifiesto):
        for m in json.load(io.open(ruta_manifiesto, encoding="utf-8")):
            manifiesto[(m["doc"], m["titulo"], m["seccion"])] = m

    # EL JUICIO A MANO manda sobre el automatico: buscar la frase no sabe distinguir «no
    # esta hecho» de «era un dato del ejemplo». Ver `_revision_puntos.py`.
    revision = {}
    ruta_rev = os.path.join(RAIZ, "_guia", "_revision_puntos.json")
    if os.path.exists(ruta_rev):
        revision = json.load(io.open(ruta_rev, encoding="utf-8"))

    cuenta = {"ok": 0, "falla": 0, "sin_probar": 0, "sin_pantalla": 0}
    partes = []
    for clave, (titulo_doc, url, bajada) in DOCS.items():
        suyos = [p for p in puntos if p["doc"] == clave]
        propio = {"ok": 0, "falla": 0, "sin_probar": 0, "sin_pantalla": 0}
        secciones = []
        for sec in dict.fromkeys(p["seccion"] for p in suyos):
            tarjetas = []
            for p in [x for x in suyos if x["seccion"] == sec]:
                m = manifiesto.get((p["doc"], p["titulo"], p["seccion"]))
                nota = None
                if not p.get("escena"):
                    estado = "sin_pantalla"
                    faltan, img, forzada, ruta = p["debe_verse"], None, None, None
                elif m is None:
                    estado = "sin_probar"
                    faltan, img, forzada, ruta = p["debe_verse"], None, None, None
                else:
                    estado = "ok" if m["estado"] == "completo" else "falla"
                    faltan = m["faltan"]
                    img = imagen(m.get("imagen"))
                    forzada, ruta = m.get("forzada"), m.get("ruta")
                if p["titulo"] in revision:
                    veredicto, nota = revision[p["titulo"]]
                    estado = "ok" if veredicto.startswith("ok") else veredicto
                cuenta[estado] += 1
                propio[estado] += 1

                vistas = [f for f in p["debe_verse"] if f not in faltan]
                lista = "".join(
                    f'<li class="{"si" if f in vistas else "no"}">{esc(f)}</li>'
                    for f in p["debe_verse"])
                tarjetas.append(f"""
        <article class="punto">
          <div class="txt">
            <span class="chip {CLASE[estado]}">{ETIQUETA[estado]}</span>
            <h4>{esc(p['titulo'])}</h4>
            {f'<p class="pie">{esc(p["pie"])}</p>' if p.get("pie") else ""}
            {f'<p class="nota">{esc(nota)}</p>' if nota else ""}
            <ul class="frases">{lista}</ul>
            {f'<p class="donde"><code>{esc(ruta)}</code></p>' if ruta else ""}
            {f'<p class="forzada">Estado forzado · {esc(forzada)}</p>' if forzada else ""}
          </div>
          <figure>{f'<img src="{img}" alt="Captura de {esc(p["titulo"])}" loading="lazy">'
                  if img else '<p class="sin-foto">Sin captura.</p>'}</figure>
        </article>""")
            secciones.append(f'<section class="bloque"><h3>{esc(sec)}</h3>'
                             f'{"".join(tarjetas)}</section>')

        partes.append(f"""
    <section class="doc">
      <p class="eyebrow">{esc(url)}</p>
      <h2>{esc(titulo_doc)}</h2>
      <p class="bajada">{esc(bajada)}</p>
      <div class="marcador">
        <span class="m ok"><b>{propio['ok']}</b> vistos</span>
        <span class="m mal"><b>{propio['falla']}</b> no están</span>
        <span class="m medias"><b>{propio['sin_probar']}</b> sin comprobar</span>
        <span class="m gris"><b>{propio['sin_pantalla']}</b> sin pantalla</span>
      </div>
      {''.join(secciones)}
    </section>""")

    io.open(SALIDA, "w", encoding="utf-8").write(PLANTILLA.format(
        total=len(puntos), ok=cuenta["ok"], medias=cuenta["sin_probar"],
        mal=cuenta["falla"], gris=cuenta["sin_pantalla"], cuerpo="".join(partes)))
    print(f'{len(puntos)} puntos · {cuenta} · '
          f'{os.path.getsize(SALIDA)/1024/1024:.1f} MB')


PLANTILLA = """<title>Los tres documentos, punto por punto y con la captura</title>
<style>
  :root {{
    --tinta: #17130F; --tinta-2: #5A5049; --papel: #FBF8F5; --papel-2: #F2EDE7;
    --linea: #E2D9D0; --marca: #FF671F; --verde: #1E7A4B; --ambar: #A9660A;
    --rojo: #BE3227; --sans: ui-sans-serif, -apple-system, "Segoe UI", Roboto, sans-serif;
    --serif: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, ui-serif, serif;
    --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --tinta: #F4EFE9; --tinta-2: #A79C93; --papel: #14110E; --papel-2: #1D1915;
             --linea: #322B25; --verde: #4FBF87; --ambar: #E0A045; --rojo: #F0736A; }}
  }}
  :root[data-theme="dark"] {{
    --tinta: #F4EFE9; --tinta-2: #A79C93; --papel: #14110E; --papel-2: #1D1915;
    --linea: #322B25; --verde: #4FBF87; --ambar: #E0A045; --rojo: #F0736A;
  }}
  :root[data-theme="light"] {{
    --tinta: #17130F; --tinta-2: #5A5049; --papel: #FBF8F5; --papel-2: #F2EDE7;
    --linea: #E2D9D0; --verde: #1E7A4B; --ambar: #A9660A; --rojo: #BE3227;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--papel); color: var(--tinta); font-family: var(--sans);
          font-size: 16px; line-height: 1.55; -webkit-font-smoothing: antialiased; }}
  .envoltorio {{ max-width: 1140px; margin: 0 auto; padding: 0 20px 96px; }}
  .portada {{ padding: 58px 0 34px; border-bottom: 2px solid var(--tinta); }}
  .kicker {{ font-size: 12px; font-weight: 700; letter-spacing: .16em; text-transform: uppercase;
             color: var(--marca); margin: 0 0 12px; }}
  h1 {{ font-size: clamp(32px, 5.4vw, 54px); line-height: 1; margin: 0 0 16px; font-weight: 800;
        letter-spacing: -.02em; text-wrap: balance; }}
  .entradilla {{ font-family: var(--serif); font-size: 19px; max-width: 62ch;
                 color: var(--tinta-2); margin: 0; }}
  .totales {{ display: flex; gap: 28px; margin-top: 26px; flex-wrap: wrap; }}
  .total b {{ display: block; font-size: 36px; line-height: 1; font-weight: 800;
              font-variant-numeric: tabular-nums; }}
  .total span {{ font-size: 11.5px; font-weight: 700; letter-spacing: .1em;
                 text-transform: uppercase; color: var(--tinta-2); }}
  .total.ok b {{ color: var(--verde); }} .total.medias b {{ color: var(--ambar); }}
  .total.mal b {{ color: var(--rojo); }} .total.gris b {{ color: var(--tinta-2); }}

  .doc {{ padding-top: 52px; }}
  .eyebrow {{ font-family: var(--mono); font-size: 12px; color: var(--tinta-2); margin: 0 0 6px; }}
  .doc h2 {{ font-size: clamp(26px, 4vw, 34px); font-weight: 800; letter-spacing: -.02em;
             margin: 0 0 6px; }}
  .bajada {{ font-family: var(--serif); color: var(--tinta-2); margin: 0 0 14px; }}
  .marcador {{ display: flex; gap: 6px; flex-wrap: wrap; }}
  .m {{ font-size: 12px; font-weight: 600; padding: 4px 11px; border-radius: 999px;
        border: 1px solid var(--linea); }}
  .m.ok {{ color: var(--verde); }} .m.medias {{ color: var(--ambar); }}
  .m.mal {{ color: var(--rojo); }} .m.gris {{ color: var(--tinta-2); }}

  .bloque {{ margin-top: 30px; }}
  .bloque > h3 {{ font-size: 12px; font-weight: 700; letter-spacing: .14em;
                  text-transform: uppercase; color: var(--marca); margin: 0 0 4px;
                  padding-bottom: 8px; border-bottom: 1px solid var(--linea); }}
  .punto {{ display: grid; grid-template-columns: minmax(0,1fr) minmax(0,300px);
            gap: 18px 26px; padding: 20px 0; border-bottom: 1px solid var(--linea);
            align-items: start; }}
  .punto h4 {{ font-size: 16.5px; font-weight: 700; margin: 8px 0 4px; letter-spacing: -.01em; }}
  .pie {{ font-family: var(--serif); font-style: italic; color: var(--tinta-2); margin: 0 0 8px;
          font-size: 14.5px; max-width: 60ch; }}
  .nota {{ font-size: 14px; margin: 8px 0 0; max-width: 62ch; color: var(--tinta);
           border-left: 2px solid var(--marca); padding-left: 10px; }}
  .frases {{ list-style: none; margin: 8px 0 0; padding: 0; display: grid; gap: 3px; }}
  .frases li {{ font-size: 13.5px; padding-left: 20px; position: relative; color: var(--tinta-2); }}
  .frases li::before {{ position: absolute; left: 0; font-weight: 700; }}
  .frases li.si::before {{ content: "✓"; color: var(--verde); }}
  .frases li.no::before {{ content: "✕"; color: var(--rojo); }}
  .frases li.no {{ color: var(--rojo); }}
  .donde {{ font-size: 12px; color: var(--tinta-2); margin: 10px 0 0; }}
  .donde code {{ font-family: var(--mono); }}
  .forzada {{ font-size: 12px; color: var(--tinta-2); margin: 5px 0 0; font-style: italic;
              max-width: 62ch; }}
  .chip {{ display: inline-block; font-size: 11px; font-weight: 700; letter-spacing: .08em;
           text-transform: uppercase; padding: 3px 10px; border-radius: 4px; color: var(--papel); }}
  .chip.ok {{ background: var(--verde); }} .chip.medias {{ background: var(--ambar); }}
  .chip.mal {{ background: var(--rojo); }}
  .chip.gris {{ background: transparent; color: var(--tinta-2); border: 1px solid var(--linea); }}
  figure {{ margin: 0; }}
  figure img {{ width: 100%; height: auto; display: block; border-radius: 10px;
                border: 1px solid var(--linea); }}
  .sin-foto {{ font-size: 12.5px; color: var(--tinta-2); margin: 0; padding: 12px;
               border: 1px dashed var(--linea); border-radius: 10px; text-align: center; }}
  @media (max-width: 800px) {{ .punto {{ grid-template-columns: 1fr; }} }}
  @media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; }} }}
</style>

<div class="envoltorio">
  <header class="portada">
    <p class="kicker">12EN12 · repaso del 1 de septiembre</p>
    <h1>Los tres documentos, punto por punto</h1>
    <p class="entradilla">
      Los {total} apartados de los tres documentos, con lo que cada uno manda que se vea y
      la captura de la app donde se ve. Lo que no está, dice qué frase falta.
    </p>
    <div class="totales">
      <div class="total"><b>{total}</b><span>apartados</span></div>
      <div class="total ok"><b>{ok}</b><span>vistos en pantalla</span></div>
      <div class="total mal"><b>{mal}</b><span>no están</span></div>
      <div class="total medias"><b>{medias}</b><span>sin comprobar</span></div>
      <div class="total gris"><b>{gris}</b><span>sin pantalla que mirar</span></div>
    </div>
  </header>
  {cuerpo}
</div>
"""


main()
