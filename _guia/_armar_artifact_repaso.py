# -*- coding: utf-8 -*-
"""Monta el artifact del repaso de los tres documentos.

Las pruebas NO se escriben a mano: salen de `_repaso_tres_documentos.json`, que es la
salida de buscar cada frase de Jesus en el codigo. Aqui solo se pinta, y se aplican los
matices que una busqueda de texto no puede decidir sola (esta la frase pero en el sitio
equivocado, esta el mecanismo pero con otro texto...).

Uso:  ./backend/venv/Scripts/python.exe _guia/_armar_artifact_repaso.py
"""
import html
import io
import json
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOS = os.path.join(RAIZ, "_guia", "_repaso_tres_documentos.json")
SALIDA = os.path.join(RAIZ, "_guia", "_repaso_tres_documentos.html")

DOCS = {
    "validado": ("Todo lo validado antes del 1 de septiembre",
                 "Lo cerrado y validado con Jesús antes del 1 de septiembre. Dieciséis "
                 "secciones en seis bloques.",
                 "claude.ai/code/artifact/6b67e80c"),
    "mensual": ("El reporte mensual",
                "Los cuatro pasos del reporte que el cliente manda, y sus dos variantes.",
                "claude.ai/code/artifact/3b60d286"),
    "informe": ("El informe del mes",
                "Los diez bloques de lo que recibe al mandarlo, en sus dos estados.",
                "claude.ai/code/artifact/2f5f6de3"),
}

# Lo que una busqueda de texto no puede decidir. (punto) -> (estado, nota)
MATICES = {
    "El cierre: salen las sensaciones del día y el peso": (
        "parcial",
        "Las sensaciones generales SÍ salieron: en la pantalla no queda ni una mención "
        "(solo un comentario del modelo y del test diciendo que se fue). El peso NO: sigue "
        "en el cierre, en `CheckInsPage.jsx:909-944`, con su campo y su selector de día."),
    "El campo del peso, abierto todo el año": (
        "abierto",
        "El texto está escrito palabra por palabra, pero en el sitio equivocado: vive en el "
        "cierre del día (`CheckInsPage.jsx:915`) y el documento lo quiere en Mi evolución, "
        "«el único sitio donde el peso se escribe». `TusFotosYMetricas.jsx` no tiene campo "
        "de peso: sube fotos, medidas y grasa."),
    "La cola de Inicio": (
        "parcial",
        "El reporte SÍ entra en la cola (`ClientDashboard.jsx:766`), pero el ÚLTIMO: detrás "
        "del cierre del día, del perfil, de los alimentos preferentes y de los datos que "
        "falten. El documento lo quiere arriba, «porque tiene fecha de entrega»."),
    "La fila de la mañana": (
        "parcial",
        "El aviso existe y en sus días (miércoles y jueves, `avisos_cliente.py:930-966`), "
        "pero con el texto viejo: «Hoy toca pesarte y mañana también». Falta «En ayunas y "
        "después de ir al baño», la fila en Inicio y el apagado a las 12:00."),
    "El aviso del martes": (
        "abierto",
        "Hoy el primero es el del miércoles. El documento lo adelanta al martes «para que "
        "le dé tiempo a la primera pesada», y con otro texto."),
    "El aviso de la pesada que falta": (
        "abierto",
        "No existe. Es el del viernes: «Si te pesas esta mañana antes de las 10, aún entra. "
        "Si no, me quedo con la que tengo»."),
    "La semana sin reporte": (
        "abierto",
        "No existe el aviso de la semana 1."),
    "El aviso de la apertura": (
        "parcial",
        "El aviso existe (`avisos_cliente.py:670`) con el texto viejo: «Tu reporte quincenal "
        "está abierto». Falta el plazo y el empujón: «Tienes para hacerlo hasta mañana "
        "jueves a las ocho… Son dos minutos»."),
    "El recordatorio del último día": (
        "parcial",
        "Existe como «Último día para tu quincenal» (`avisos_cliente.py:686`). Falta decirle "
        "qué se pierde: «este ajuste se salta y el siguiente será en tu reporte mensual»."),
    "El fuera de plazo": (
        "abierto",
        "No existe. Es el del jueves de 20:00 a 24:00, en rojo y sin riña."),
    "La tarjeta en Hecho": (
        "parcial",
        "La tarjeta existe y cambia a «Ya lo mandaste. Lo estamos mirando». El documento "
        "pide la hora: «Te decimos algo antes del viernes a las tres de la tarde»."),
}

ORDEN = {"abierto": 0, "parcial": 1, "cerrado": 2}
ETIQUETA = {"cerrado": "Cerrado", "parcial": "A medias", "abierto": "Abierto"}

TESTS = {
    "mensual": ("backend/tests/test_paso1_mensual_0109.py", 27),
    "informe": ("backend/tests/test_informe_del_mes_0109.py", 36),
}
COMMITS = {
    "validado": ["21fcd91", "25c198f", "7a26372", "e5c7d8f", "4f441f6", "e45a6af",
                 "de2757e", "8fe06f3", "ce13047"],
    "mensual": ["fffd19c"],
    "informe": ["1b231dc"],
}


def esc(x):
    return html.escape(str(x or ""))


def main() -> None:
    datos = json.load(io.open(DATOS, encoding="utf-8"))
    for d in datos:
        if d["punto"] in MATICES:
            d["estado"], d["nota"] = MATICES[d["punto"]]
        else:
            d["nota"] = None

    cuenta = {"cerrado": 0, "parcial": 0, "abierto": 0}
    for d in datos:
        cuenta[d["estado"]] = cuenta.get(d["estado"], 0) + 1

    partes = []
    for clave, (titulo, bajada, url) in DOCS.items():
        suyos = [d for d in datos if d["doc"] == clave]
        c = {"cerrado": 0, "parcial": 0, "abierto": 0}
        for d in suyos:
            c[d["estado"]] += 1
        bloques = []
        for b in dict.fromkeys(d["bloque"] for d in suyos):
            filas = []
            for d in [x for x in suyos if x["bloque"] == b]:
                pruebas = []
                for p in d["pruebas"]:
                    for fichero, linea, texto in p["donde"][:2]:
                        pruebas.append(
                            f'<li><span class="ruta">{esc(fichero)}<b>:{linea}</b></span>'
                            f'<span class="codigo">{esc(texto[:120])}</span></li>')
                if not pruebas and d["estado"] == "abierto":
                    pruebas.append('<li class="hueco">No aparece en el código.</li>')
                # Los `nombres.jsx:12` de la nota van en monoespaciada, como las pruebas.
                nota = ""
                if d.get("nota"):
                    texto = re.sub(r"`([^`]+)`", lambda m: f"<code>{m.group(1)}</code>",
                                   esc(d["nota"]))
                    nota = f'<p class="nota">{texto}</p>'

                filas.append(f"""
        <article class="punto" data-estado="{d['estado']}">
          <div class="col-que">
            <h4>{esc(d['punto'])}</h4>
            <p class="dice">{esc(d['dice'])}</p>
          </div>
          <div class="col-prueba">
            <span class="chip chip-{d['estado']}">{ETIQUETA[d['estado']]}</span>
            <ul class="pruebas">{''.join(pruebas)}</ul>
            {nota}
          </div>
        </article>""")
            bloques.append(f"""
      <section class="bloque">
        <h3>{esc(b)}</h3>
        {''.join(filas)}
      </section>""")

        prueba_extra = []
        if clave in TESTS:
            f, n = TESTS[clave]
            prueba_extra.append(f'<span class="meta-item"><b>{n}</b> pruebas en '
                                f'<span class="ruta">{esc(f)}</span></span>')
        prueba_extra.append('<span class="meta-item">Commits: '
                            + " ".join(f'<code>{c2}</code>' for c2 in COMMITS[clave])
                            + "</span>")

        partes.append(f"""
    <section class="doc" id="{clave}">
      <header class="doc-head">
        <p class="eyebrow">{esc(url)}</p>
        <h2>{esc(titulo)}</h2>
        <p class="bajada">{esc(bajada)}</p>
        <div class="marcador">
          <span class="m m-cerrado"><b>{c['cerrado']}</b> cerrados</span>
          <span class="m m-parcial"><b>{c['parcial']}</b> a medias</span>
          <span class="m m-abierto"><b>{c['abierto']}</b> abiertos</span>
        </div>
        <p class="meta">{' · '.join(prueba_extra)}</p>
      </header>
      {''.join(bloques)}
    </section>""")

    io.open(SALIDA, "w", encoding="utf-8").write(PLANTILLA.format(
        total=len(datos), cerrados=cuenta["cerrado"], parciales=cuenta["parcial"],
        abiertos=cuenta["abierto"], cuerpo="".join(partes)))
    print(f"{len(datos)} puntos · {cuenta} · {SALIDA}")


PLANTILLA = """<title>Los tres documentos, punto por punto</title>
<style>
  :root {{
    --tinta:      #17130F;
    --tinta-2:    #5A5049;
    --papel:      #FBF8F5;
    --papel-2:    #F2EDE7;
    --linea:      #E2D9D0;
    --marca:      #FF671F;
    --verde:      #1E7A4B;
    --ambar:      #A9660A;
    --rojo:       #BE3227;
    --sans: ui-sans-serif, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
    --serif: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, ui-serif, serif;
    --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --tinta: #F4EFE9; --tinta-2: #A79C93; --papel: #14110E; --papel-2: #1D1915;
      --linea: #322B25; --verde: #4FBF87; --ambar: #E0A045; --rojo: #F0736A;
    }}
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
  body {{
    margin: 0; background: var(--papel); color: var(--tinta);
    font-family: var(--sans); font-size: 16px; line-height: 1.55;
    -webkit-font-smoothing: antialiased;
  }}
  .envoltorio {{ max-width: 1080px; margin: 0 auto; padding: 0 20px 96px; }}

  /* ── Cabecera ───────────────────────────────────────────── */
  .portada {{ padding: 64px 0 40px; border-bottom: 2px solid var(--tinta); }}
  .kicker {{
    font-size: 12px; font-weight: 700; letter-spacing: .16em; text-transform: uppercase;
    color: var(--marca); margin: 0 0 12px;
  }}
  h1 {{
    font-size: clamp(34px, 6vw, 58px); line-height: .98; margin: 0 0 16px;
    font-weight: 800; letter-spacing: -.02em; text-wrap: balance;
  }}
  .entradilla {{
    font-family: var(--serif); font-size: 19px; line-height: 1.5;
    max-width: 60ch; color: var(--tinta-2); margin: 0;
  }}

  .totales {{ display: flex; flex-wrap: wrap; gap: 8px 28px; margin: 28px 0 0; }}
  .total b {{
    display: block; font-size: 40px; line-height: 1; font-weight: 800;
    font-variant-numeric: tabular-nums; letter-spacing: -.02em;
  }}
  .total span {{
    font-size: 12px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase;
    color: var(--tinta-2);
  }}
  .total.cerrado b {{ color: var(--verde); }}
  .total.parcial b {{ color: var(--ambar); }}
  .total.abierto b {{ color: var(--rojo); }}

  /* ── Filtros ────────────────────────────────────────────── */
  .filtros {{
    position: sticky; top: 0; z-index: 5; display: flex; gap: 8px; flex-wrap: wrap;
    padding: 14px 0; background: color-mix(in srgb, var(--papel) 92%, transparent);
    backdrop-filter: blur(8px); border-bottom: 1px solid var(--linea);
  }}
  .filtros button {{
    font: inherit; font-size: 13px; font-weight: 600; cursor: pointer;
    padding: 6px 14px; border-radius: 999px; border: 1px solid var(--linea);
    background: transparent; color: var(--tinta-2);
  }}
  .filtros button[aria-pressed="true"] {{
    background: var(--tinta); color: var(--papel); border-color: var(--tinta);
  }}
  .filtros button:focus-visible {{ outline: 2px solid var(--marca); outline-offset: 2px; }}

  /* ── Documento ──────────────────────────────────────────── */
  .doc {{ padding-top: 56px; }}
  .doc-head {{ margin-bottom: 8px; }}
  .eyebrow {{
    font-family: var(--mono); font-size: 12px; color: var(--tinta-2);
    margin: 0 0 6px; letter-spacing: -.01em;
  }}
  .doc h2 {{
    font-size: clamp(26px, 4vw, 36px); font-weight: 800; letter-spacing: -.02em;
    margin: 0 0 8px; text-wrap: balance;
  }}
  .bajada {{ font-family: var(--serif); color: var(--tinta-2); margin: 0 0 16px; max-width: 62ch; }}
  .marcador {{ display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }}
  .m {{
    font-size: 12px; font-weight: 600; padding: 4px 11px; border-radius: 999px;
    border: 1px solid var(--linea);
  }}
  .m b {{ font-variant-numeric: tabular-nums; }}
  .m-cerrado {{ color: var(--verde); border-color: color-mix(in srgb, var(--verde) 40%, transparent); }}
  .m-parcial {{ color: var(--ambar); border-color: color-mix(in srgb, var(--ambar) 40%, transparent); }}
  .m-abierto {{ color: var(--rojo); border-color: color-mix(in srgb, var(--rojo) 40%, transparent); }}
  .meta {{ font-size: 13px; color: var(--tinta-2); margin: 0; }}
  .meta-item + .meta-item::before {{ content: ""; }}
  .meta code {{ font-family: var(--mono); font-size: 12px; }}

  .bloque {{ margin-top: 34px; }}
  .bloque > h3 {{
    font-size: 12px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase;
    color: var(--marca); margin: 0 0 4px; padding-bottom: 8px;
    border-bottom: 1px solid var(--linea);
  }}

  /* ── Punto ──────────────────────────────────────────────── */
  .punto {{
    display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 7fr); gap: 12px 32px;
    padding: 20px 0; border-bottom: 1px solid var(--linea);
  }}
  .punto h4 {{ font-size: 16px; font-weight: 700; margin: 0 0 4px; letter-spacing: -.01em; }}
  .dice {{
    font-family: var(--serif); font-style: italic; color: var(--tinta-2);
    margin: 0; font-size: 15px; line-height: 1.5;
  }}
  .col-prueba {{ display: flex; flex-direction: column; align-items: flex-start; gap: 8px; min-width: 0; }}
  .chip {{
    font-size: 11px; font-weight: 700; letter-spacing: .09em; text-transform: uppercase;
    padding: 3px 10px; border-radius: 4px; color: var(--papel);
  }}
  .chip-cerrado {{ background: var(--verde); }}
  .chip-parcial {{ background: var(--ambar); }}
  .chip-abierto {{ background: var(--rojo); }}

  .pruebas {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; width: 100%; }}
  .pruebas li {{
    font-family: var(--mono); font-size: 12.5px; line-height: 1.45;
    background: var(--papel-2); border-left: 2px solid var(--linea);
    padding: 7px 10px; border-radius: 0 4px 4px 0; overflow-x: auto;
  }}
  .ruta {{ display: block; color: var(--marca); }}
  .ruta b {{ font-weight: 700; }}
  .codigo {{ display: block; color: var(--tinta-2); white-space: pre; }}
  .hueco {{ font-family: var(--sans); color: var(--rojo); border-left-color: var(--rojo); }}
  .nota {{ font-size: 14px; color: var(--tinta-2); margin: 0; max-width: 62ch; }}
  .nota code {{ font-family: var(--mono); font-size: 12.5px; }}

  .punto[hidden] {{ display: none; }}

  @media (max-width: 720px) {{
    .punto {{ grid-template-columns: 1fr; gap: 10px; }}
    .portada {{ padding-top: 40px; }}
  }}
  @media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; }} }}
</style>

<div class="envoltorio">
  <header class="portada">
    <p class="kicker">12EN12 · repaso del 1 de septiembre</p>
    <h1>Los tres documentos, punto por punto</h1>
    <p class="entradilla">
      Cada punto de los tres documentos de Jesús, con la prueba de que está hecho: el
      fichero y la línea donde vive su frase. Lo que no está, dice por qué.
    </p>
    <div class="totales">
      <div class="total"><b>{total}</b><span>puntos</span></div>
      <div class="total cerrado"><b>{cerrados}</b><span>cerrados</span></div>
      <div class="total parcial"><b>{parciales}</b><span>a medias</span></div>
      <div class="total abierto"><b>{abiertos}</b><span>abiertos</span></div>
    </div>
  </header>

  <nav class="filtros" aria-label="Filtrar por estado">
    <button type="button" data-f="todo" aria-pressed="true">Todos</button>
    <button type="button" data-f="cerrado" aria-pressed="false">Cerrados</button>
    <button type="button" data-f="parcial" aria-pressed="false">A medias</button>
    <button type="button" data-f="abierto" aria-pressed="false">Abiertos</button>
  </nav>

  {cuerpo}
</div>

<script>
  const botones = document.querySelectorAll('.filtros button');
  botones.forEach((b) => b.addEventListener('click', () => {{
    const f = b.dataset.f;
    botones.forEach((o) => o.setAttribute('aria-pressed', String(o === b)));
    document.querySelectorAll('.punto').forEach((p) => {{
      p.hidden = f !== 'todo' && p.dataset.estado !== f;
    }});
    // Un bloque sin ningun punto visible sobra: si no, quedan rotulos sueltos.
    document.querySelectorAll('.bloque').forEach((s) => {{
      s.hidden = !s.querySelector('.punto:not([hidden])');
    }});
    document.querySelectorAll('.doc').forEach((s) => {{
      s.hidden = !s.querySelector('.punto:not([hidden])');
    }});
  }}));
</script>
"""


main()
