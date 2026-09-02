# -*- coding: utf-8 -*-
"""SU DOCUMENTO ENTERO, CON LO NUESTRO DEBAJO DE CADA PUNTO.

El repaso anterior era un resumen: sus frases sueltas en una lista y nuestra captura al
lado. Se leia mal, y con razon -- «no se entiende si esta cerrado» --: una frase tachada
podia ser un fallo, un dato del cliente de su maqueta o texto que en la app vive en otra
pestaña, y las tres salian igual.

Asi que aqui va SU DOCUMENTO TAL CUAL NOS LO DIO -- sus dos columnas, sus maquetas, sus
pies, su orden -- y debajo de cada punto, una tarjeta nuestra:

    · el veredicto en cristiano (esta / esta con un matiz / no esta / cambiado despues /
      no es una pantalla),
    · la captura de la app donde se ve,
    · frase por frase, cual se ve y cual no Y POR QUE,
    · y, si el estado se forzo para poder mirarlo, que se forzo y por que.

El de «Todo lo validado antes del 1 de septiembre» va con su HTML de verdad, que lo tenemos
guardado. Los otros dos (el mensual y el informe) van con su transcripcion literal, leida
pantalla a pantalla en el navegador: de esos no tenemos el HTML.

Uso:  ./backend/venv/Scripts/python.exe _guia/_armar_artifact_suyo.py
"""
import base64
import html
import io
import json
import os
import re
import sys

from PIL import Image

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "_guia"))

from _veredictos import (ETIQUETA, HECHO, MATIZ, FALTA, DESPUES,      # noqa: E402
                         NO_PANTALLA, motivo_de)

SUYO = ("C:/Users/Administrador/Desktop/Todo lo validado antes del 1 de septiembre_files/"
        "saved_resource.html")
CAPTURAS = [os.path.join(RAIZ, "_guia", "_capturas_doce"),
            os.path.join(RAIZ, "_guia", "_capturas")]
SALIDA = os.path.join(RAIZ, "_guia", "_repaso_suyo.html")

DOCS = {
    "mensual": ("El reporte mensual", "claude.ai/code/artifact/3b60d286",
                "Los cuatro pasos del reporte que manda, y sus dos variantes."),
    "informe": ("El informe del mes", "claude.ai/code/artifact/2f5f6de3",
                "Los diez bloques de lo que recibe al mandarlo, en sus dos estados."),
}

CLASE = {HECHO: "ok", MATIZ: "matiz", FALTA: "mal", DESPUES: "despues",
         NO_PANTALLA: "gris"}


# ─────────────────────────────────────────────────────────────────────────────
# LAS PIEZAS
# ─────────────────────────────────────────────────────────────────────────────

def esc(x):
    return html.escape(str(x or ""))


def clave_de(p):
    """La clave del veredicto. Con el titulo a secas no vale: hay dos que se repiten en
    documentos distintos («El rótulo y su subtítulo» y «El rótulo del paso») y uno tapaba
    al otro."""
    return f'{p["doc"]}|{p["seccion"]}|{p["titulo"]}'


def imagen(nombre, ancho=460, calidad=64):
    """La captura, encogida y en base64. `None` si no hay."""
    if not nombre:
        return None
    for carpeta in CAPTURAS:
        ruta = os.path.join(carpeta, nombre)
        if os.path.exists(ruta):
            im = Image.open(ruta).convert("RGB")
            if im.width > ancho:
                im = im.resize((ancho, round(im.height * ancho / im.width)), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=calidad, optimize=True)
            return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    return None


def tarjeta(punto, veredicto):
    """La tarjeta nuestra que va debajo de un punto suyo."""
    estado = veredicto["estado"]
    faltan = set(veredicto.get("faltan") or [])
    lineas = []
    for f in punto.get("debe_verse") or []:
        if f in faltan:
            # Y AQUI ESTA LO QUE FALTABA: por que no se ve. Sin el motivo, un dato de su
            # maqueta y un texto que no existe se leen igual.
            por = motivo_de(f) if estado in (HECHO, MATIZ, DESPUES) else ""
            lineas.append(f'<li class="no">{esc(f)}'
                          + (f'<span class="por">{esc(por)}</span>' if por else "")
                          + "</li>")
        else:
            lineas.append(f'<li class="si">{esc(f)}</li>')

    img = imagen(veredicto.get("imagen"))
    return f"""
<div class="nuestro {CLASE[estado]}">
  <p class="chip">{esc(ETIQUETA[estado])}</p>
  <div class="dos">
    <div class="txt">
      <p class="nota">{esc(veredicto.get("nota"))}</p>
      {'<ul class="frases">' + "".join(lineas) + "</ul>" if lineas else ""}
      {f'<p class="donde">Se mira en <code>{esc(veredicto["ruta"])}</code></p>'
       if veredicto.get("ruta") else ""}
      {f'<p class="forzada"><b>Estado forzado</b> · {esc(veredicto["forzada"])}</p>'
       if veredicto.get("forzada") else ""}
    </div>
    <figure>{f'<img src="{img}" alt="Captura" loading="lazy">' if img
             else '<p class="sinfoto">Sin captura: ver el veredicto.</p>'}</figure>
  </div>
</div>"""


# ─────────────────────────────────────────────────────────────────────────────
# EL DOCUMENTO SUYO, CON SU HTML
# ─────────────────────────────────────────────────────────────────────────────

#: El mismo corte que usa `_extraer_puntos_validado.py`, para que los puntos caigan donde
#: cayeron entonces. Si esto se toca, hay que tocar los dos.
ABRE = re.compile(
    r'<h2>(?P<h2>.*?)</h2>'
    r'|<h3>(?P<h3>.*?)</h3>'
    r'|<p class="(?P<c>rot|q|sub)"[^>]*>(?P<t>.*?)</p>', re.S)


def _texto(x):
    x = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", x or "", flags=re.S)
    x = re.sub(r"<br\s*/?>", "\n", x)
    x = re.sub(r"</(p|div|h1|h2|h3|h4|li|button)>", "\n", x)
    x = re.sub(r"<[^>]+>", " ", x)
    return html.unescape(x).replace("\xa0", " ")


def suyo_con_lo_nuestro(veredictos, puntos_por_titulo):
    """Su HTML entero, con nuestra tarjeta insertada detras de cada punto."""
    s = io.open(SUYO, encoding="utf-8", errors="replace").read()

    # Sus estilos: los cuatro bloques que van entre el <body> y el documento. El <link> a
    # la fuente de Google se cae -- el artifact no deja pedir nada fuera -- y la fuente se
    # queda en la del sistema, que es la que el propio CSS pone de respaldo.
    ini_estilos = s.find("<style>", s.find("<body>"))
    ini_doc = s.find('<div class="env">')
    estilos = s[ini_estilos:ini_doc]
    estilos = re.sub(r'<link[^>]*>', "", estilos)
    estilos = re.sub(r"<title>.*?</title>", "", estilos, flags=re.S)

    fin_doc = s.rfind("</body>")
    cortes = [(m.start(), m) for m in ABRE.finditer(s)]

    trozos, ultimo, seccion = [], ini_doc, None
    for i, (pos, m) in enumerate(cortes):
        if pos < ini_doc:
            continue
        fin = cortes[i + 1][0] if i + 1 < len(cortes) else fin_doc
        if m.group("h2") is not None:
            seccion = " ".join(_texto(m.group("h2")).split())
            continue
        if m.group("c") == "sub":
            continue
        titulo = " ".join(_texto(m.group("h3") or m.group("t")).split())
        if not titulo:
            continue
        punto = puntos_por_titulo.get((seccion, titulo))
        if not punto:
            continue
        v = veredictos.get(clave_de(punto))
        if not v:
            continue
        # Todo lo suyo hasta el final de este punto, y detras lo nuestro.
        trozos.append(s[ultimo:fin])
        trozos.append(tarjeta(punto, v))
        ultimo = fin
    trozos.append(s[ultimo:fin_doc])
    return estilos, "".join(trozos)


# ─────────────────────────────────────────────────────────────────────────────
# LOS OTROS DOS, CON SU TRANSCRIPCION
# ─────────────────────────────────────────────────────────────────────────────

def otro_documento(clave, puntos, veredictos):
    titulo, url, bajada = DOCS[clave]
    suyos = [p for p in puntos if p["doc"] == clave]
    partes = []
    for sec in dict.fromkeys(p["seccion"] for p in suyos):
        tarjetas = []
        for p in [x for x in suyos if x["seccion"] == sec]:
            v = veredictos.get(clave_de(p))
            if not v:
                continue
            suyas = "".join(f"<li>{esc(f)}</li>" for f in (p.get("debe_verse") or []))
            tarjetas.append(f"""
      <article class="punto-otro">
        <h4>{esc(p['titulo'])}</h4>
        {f'<p class="suyo-pie">{esc(p["pie"])}</p>' if p.get("pie") else ""}
        {f'<div class="suyo-maqueta"><p class="rot">Lo que dice su maqueta</p><ul>{suyas}</ul></div>'
         if suyas else ""}
        {tarjeta(p, v)}
      </article>""")
        partes.append(f'<section class="bloque"><h3>{esc(sec)}</h3>{"".join(tarjetas)}</section>')

    return f"""
<div class="otrodoc">
  <div class="cab">
    <p class="eti">{esc(url)}</p>
    <h1>{esc(titulo)}</h1>
    <p class="baj">{esc(bajada)}</p>
    <p class="baj aviso">De este documento no tenemos el HTML guardado, así que aquí va su
       <b>transcripción literal</b>, leída pantalla a pantalla en el navegador (las maquetas
       tienen su propio desplazamiento y el PDF las cortaba). Si lo guardas como guardaste
       el primero, lo pongo entero igual que aquél.</p>
  </div>
  {"".join(partes)}
</div>"""


# ─────────────────────────────────────────────────────────────────────────────

NUESTRO_CSS = """
<style>
.nuestro{margin:14px 0 30px;border-radius:14px;border:1px solid var(--linea);
 background:#12151A;padding:14px 16px 16px}
.nuestro .chip{display:inline-block;margin:0 0 10px;padding:4px 11px;border-radius:999px;
 font-size:12px;font-weight:800;letter-spacing:.04em;text-transform:uppercase}
.nuestro.ok .chip{background:rgba(95,214,139,.14);color:var(--bien)}
.nuestro.matiz .chip{background:rgba(255,133,70,.16);color:var(--marca)}
.nuestro.mal .chip{background:rgba(255,122,128,.14);color:var(--mal)}
.nuestro.despues .chip{background:rgba(148,155,166,.16);color:#C7CCD4}
.nuestro.gris .chip{background:rgba(148,155,166,.12);color:var(--mut)}
.nuestro.ok{border-left:3px solid var(--bien)}
.nuestro.matiz{border-left:3px solid var(--marca)}
.nuestro.mal{border-left:3px solid var(--mal)}
.nuestro.despues,.nuestro.gris{border-left:3px solid var(--linea2)}
.nuestro .dos{display:grid;grid-template-columns:1fr 240px;gap:18px;align-items:start}
@media(max-width:820px){.nuestro .dos{grid-template-columns:1fr}}
.nuestro .nota{margin:0 0 10px;font-size:15px;line-height:1.55;color:var(--tx)}
.nuestro .frases{margin:0;padding:0;list-style:none;font-size:13.5px;line-height:1.5}
.nuestro .frases li{padding:3px 0 3px 22px;position:relative;color:var(--mut)}
.nuestro .frases li.si:before{content:"\\2713";position:absolute;left:0;color:var(--bien);font-weight:700}
.nuestro .frases li.no:before{content:"\\2715";position:absolute;left:0;color:var(--mal);font-weight:700}
.nuestro .frases li.si{color:var(--tx)}
.nuestro .frases .por{display:block;font-size:12.5px;color:var(--mut);
 border-left:2px solid var(--linea2);padding-left:9px;margin-top:3px;font-style:italic}
.nuestro .donde{margin:10px 0 0;font-size:12.5px;color:var(--mut)}
.nuestro .donde code{background:#0C0E11;border:1px solid var(--linea);border-radius:5px;
 padding:1px 6px;font-size:12px}
.nuestro .forzada{margin:8px 0 0;font-size:12.5px;color:var(--mut);
 border-left:2px solid var(--marca);padding-left:9px}
.nuestro figure{margin:0}
.nuestro figure img{width:100%;border-radius:10px;border:1px solid var(--linea);display:block}
.nuestro .sinfoto{margin:0;font-size:12.5px;color:var(--mut);font-style:italic}

.otrodoc{max-width:1120px;margin:0 auto;padding:38px 22px 60px}
.otrodoc .cab{border-bottom:1px solid var(--linea);padding-bottom:22px;margin-bottom:26px}
.otrodoc h1{font-size:34px;margin:8px 0 10px;letter-spacing:-.02em}
.otrodoc .eti{font-size:12px;color:var(--mut);text-transform:uppercase;letter-spacing:.08em;margin:0}
.otrodoc .baj{color:var(--mut);font-size:15px;margin:0 0 6px}
.otrodoc .baj.aviso{border-left:2px solid var(--marca);padding-left:10px;font-size:14px}
.otrodoc .bloque{margin:34px 0}
.otrodoc .bloque>h3{font-size:22px;margin:0 0 6px;border-bottom:1px solid var(--linea);padding-bottom:8px}
.punto-otro{margin:22px 0}
.punto-otro h4{font-size:17px;margin:0 0 4px}
.suyo-pie{margin:0 0 10px;color:var(--mut);font-size:14px;font-style:italic}
.suyo-maqueta{border:1px solid var(--linea);border-radius:12px;background:#0F1216;padding:12px 14px}
.suyo-maqueta .rot{margin:0 0 6px;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut)}
.suyo-maqueta ul{margin:0;padding-left:18px;font-size:14px;line-height:1.55}

.resumen{max-width:1120px;margin:0 auto;padding:30px 22px 0}
.resumen .caja{border:1px solid var(--linea);border-radius:14px;background:#12151A;padding:18px 20px}
.resumen h2{margin:0 0 8px;font-size:20px}
.resumen p{margin:0 0 10px;color:var(--mut);font-size:15px;line-height:1.6}
.resumen .cuenta{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}
.resumen .cuenta span{border:1px solid var(--linea);border-radius:999px;padding:6px 13px;
 font-size:13px;font-weight:700}
.resumen .c-ok{color:var(--bien)} .resumen .c-matiz{color:var(--marca)}
.resumen .c-mal{color:var(--mal)} .resumen .c-gris{color:var(--mut)}

.num-h{font-family:ui-monospace,Consolas,monospace;color:var(--mut);margin-right:6px}
.grav{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.06em;
 padding:2px 8px;border-radius:999px;margin-left:8px;vertical-align:middle}
.g-grave{background:rgba(255,122,128,.16);color:var(--mal)}
.g-medio{background:rgba(255,133,70,.16);color:var(--marca)}
.medida{font-family:ui-monospace,Consolas,monospace;font-size:12.5px;line-height:1.55;
 background:#0F1216;border:1px solid var(--linea);border-radius:10px;padding:11px 13px;
 margin:0 0 12px;white-space:pre-wrap;overflow-x:auto;color:var(--tx)}
.cuenta-nutri{display:flex;flex-wrap:wrap;gap:9px;margin:14px 0 12px}
.cuenta-nutri span{border:1px solid var(--linea);border-radius:999px;padding:5px 12px;
 font-size:13px;font-weight:700}
.cuenta-nutri .c-ok{color:var(--bien);border-color:var(--bien)}
.cuenta-nutri .c-matiz{color:var(--marca);border-color:var(--marca)}
.cuenta-nutri .c-mal{color:var(--mal);border-color:var(--mal)}
.cuenta-nutri .c-gris{color:var(--mut)}
ul.menores{list-style:none;padding:0;margin:14px 0 0;display:grid;gap:14px}
ul.menores li{border-left:2px solid var(--linea2);padding-left:14px;font-size:14.5px}
ul.menores li.ok{border-left-color:var(--bien)}
ul.menores li.mal{border-left-color:var(--linea2)}
ul.menores .m-estado{font-size:11px;font-weight:800;text-transform:uppercase;
 letter-spacing:.06em;margin-left:8px;color:var(--mut)}
ul.menores li.ok .m-estado{color:var(--bien)}
ul.menores .m-txt{display:block;color:var(--mut);margin-top:3px}
</style>
"""


# ─────────────────────────────────────────────────────────────────────────────
# Y LA REVISION DE NUTRICION, EN EL MISMO SITIO
# ─────────────────────────────────────────────────────────────────────────────
#
# Francisco: «a ese artifact sumale lo que arreglamos en nutricion». No son puntos de un
# documento de Jesus -- son hallazgos de un recorrido funcional --, asi que van en su propio
# bloque al final y con su propia forma: el numero, la gravedad, el estado, lo que se vio y
# lo que se hizo. Pero con LA MISMA piel que el resto, para que se lea como un solo papel.

def bloque_de_nutricion():
    from _hallazgos_nutricion import (COMMITS, ETIQUETA_ESTADO, HALLAZGOS, HECHO, ESPERA,
                                      MENORES, PENDIENTE, SIN_CERRAR)

    clase = {HECHO: "ok", ESPERA: "matiz", PENDIENTE: "mal"}
    hechos = sum(1 for h in HALLAZGOS if h[3] == HECHO) + sum(1 for m in MENORES if m[1] == HECHO)
    espera = sum(1 for h in HALLAZGOS if h[3] == ESPERA)
    pend = sum(1 for m in MENORES if m[1] == PENDIENTE)

    tarjetas = []
    for num, titulo, gravedad, estado, visto, medida, hecho in HALLAZGOS:
        tarjetas.append(f"""
      <article class="punto-otro">
        <h4><span class="num-h">{num}</span> {esc(titulo)}
            <span class="grav g-{gravedad.lower()}">{esc(gravedad)}</span></h4>
        <p class="suyo-pie">{esc(visto)}</p>
        {f'<pre class="medida">{esc(medida)}</pre>' if medida else ""}
        <div class="nuestro {clase[estado]}">
          <p class="chip">{esc(ETIQUETA_ESTADO[estado])}</p>
          <div class="txt"><p class="nota">{esc(hecho)}</p></div>
        </div>
      </article>""")

    menores = "".join(f"""
        <li class="{clase[e]}"><b>{esc(t)}</b> <span class="m-estado">{esc(ETIQUETA_ESTADO[e])}</span>
            <span class="m-txt">{esc(d)}</span></li>""" for t, e, d in MENORES)

    return f"""
<div class="otrodoc">
  <div class="cab">
    <p class="eti">claude.ai/code/artifact/7ae47ff3 · revisión funcional</p>
    <h1>La pestaña de Nutrición, función por función</h1>
    <p class="baj">Recorrido completo de la pantalla en el navegador, hecho el 1 de septiembre
       con la cuenta de Francisco. No es un documento de Jesús: es lo que se encontró al
       usarla, y lo que se hizo después.</p>
    <div class="cuenta-nutri">
      <span class="c-ok">Arreglados: {hechos}</span>
      <span class="c-matiz">Espera decisión: {espera}</span>
      <span class="c-mal">Menores pendientes: {pend}</span>
      <span class="c-gris">Sin cerrar: 1</span>
    </div>
    <p class="baj aviso">Todo lo arreglado está <b>en producción</b> desde el 2 de septiembre.
       Commits: <code>{COMMITS}</code>. Cada arreglo se comprobó <b>reproduciendo el fallo</b>,
       y donde el guion no distingue entre el antes y el después se dice.</p>
  </div>
  <section class="bloque"><h3>Los diez hallazgos con nombre y apellidos</h3>{"".join(tarjetas)}</section>
  <section class="bloque">
    <h3>Los menores</h3>
    <ul class="menores">{menores}</ul>
  </section>
  <section class="bloque">
    <h3>Sin cerrar</h3>
    <p class="suyo-pie" style="max-width:46rem">{esc(SIN_CERRAR)}</p>
  </section>
</div>"""


def main() -> None:
    puntos = json.load(io.open(os.path.join(RAIZ, "_guia", "_puntos_todos.json"),
                               encoding="utf-8"))
    veredictos = json.load(io.open(os.path.join(RAIZ, "_guia", "_veredictos.json"),
                                   encoding="utf-8"))
    por_titulo = {(p["seccion"], p["titulo"]): p for p in puntos}

    estilos, suyo = suyo_con_lo_nuestro(veredictos, por_titulo)

    cuenta = {}
    for p in puntos:
        v = veredictos.get(clave_de(p))
        if v:
            cuenta[v["estado"]] = cuenta.get(v["estado"], 0) + 1

    fichas = "".join(
        f'<span class="c-{CLASE[e]}">{ETIQUETA[e]}: {cuenta.get(e, 0)}</span>'
        for e in (HECHO, MATIZ, FALTA, DESPUES, NO_PANTALLA))

    resumen = f"""
<div class="resumen"><div class="caja">
  <h2>Sus tres documentos, punto por punto, con la app al lado</h2>
  <p>Abajo va <b>su documento entero, tal como nos lo dio</b>, y debajo de cada punto una
     tarjeta nuestra: si está en la app, la captura donde se ve, y frase por frase cuál se
     ve y cuál no <b>y por qué</b>.</p>
  <p>Una frase tachada no siempre es un fallo: puede ser un número del cliente de su
     maqueta, texto que en la app vive en otra pestaña, o algo que él mismo cambió después
     en otro documento. Cada una lo dice.</p>
  <div class="cuenta">{fichas}</div>
</div></div>"""

    otros = "".join(otro_documento(c, puntos, veredictos) for c in DOCS)

    with io.open(SALIDA, "w", encoding="utf-8") as f:
        f.write(estilos + NUESTRO_CSS + resumen + suyo + otros + bloque_de_nutricion())

    tam = os.path.getsize(SALIDA) / 1e6
    print(f"{len(puntos)} puntos · {cuenta} · {tam:.1f} MB")
    print(f"(en {SALIDA})")


if __name__ == "__main__":
    main()
